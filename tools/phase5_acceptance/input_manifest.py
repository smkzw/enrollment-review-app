"""Phase 5.8 read-only source inventory, content-hash manifest, and isolation copy.

Default mode is manifest-only. Copy requires an explicit ``--mode copy`` /
``mode="copy"`` flag. The tool never deletes, rewrites, or writes into source
trees; destinations inside any source root are rejected.

Each entry records whether the file looks like an obvious prior-run artifact
(run database, bytecode cache, JSON-lines transcript, or a JSON export carrying
a known pipeline ``schema_version`` marker) via ``run_artifact`` /
``run_artifact_reason``. Detection is generic and never changes include/exclude
decisions; downstream acceptance gates (``run_packet``) reject manifests that
fingerprint prior-run outputs as raw inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping, Sequence

MANIFEST_SCHEMA_VERSION = "phase5.input_manifest.v1"
HASH_ALGORITHM = "sha256"
CHUNK_SIZE = 1024 * 1024

PHOTO_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".jpe",
        ".jfif",
        ".png",
        ".gif",
        ".bmp",
        ".tif",
        ".tiff",
        ".webp",
        ".heic",
        ".heif",
        ".raw",
        ".cr2",
        ".nef",
        ".arw",
        ".dng",
        ".orf",
        ".rw2",
    }
)
ARCHIVE_EXTENSIONS = frozenset(
    {
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".tgz",
        ".gz",
        ".bz2",
        ".xz",
        ".cab",
        ".lz",
        ".lzma",
        ".zst",
    }
)
# Compound archive suffixes checked before single suffixes.
COMPOUND_ARCHIVE_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst")
EXCLUDABLE_KINDS = frozenset({"photo", "archive"})

# Obvious prior-run artifacts (project-agnostic): run databases, machine
# bytecode, JSON-lines transcripts. Recorded per manifest entry so downstream
# acceptance gates can reject manifests that fingerprint old run outputs
# instead of raw subject files.
RUN_ARTIFACT_DATABASE_EXTENSIONS = frozenset(
    {".sqlite3", ".sqlite", ".db3", ".db", ".sqlite-wal", ".sqlite-shm"}
)
RUN_ARTIFACT_BYTECODE_EXTENSIONS = frozenset({".pyc", ".pyo"})
RUN_ARTIFACT_TRANSCRIPT_EXTENSIONS = frozenset({".jsonl"})
RUN_ARTIFACT_PYCACHE_DIRNAME = "__pycache__"
# JSON exports of this system's own pipelines carry a schema_version marker
# with these prefixes; any such file in a source tree is a prior-run export.
_RUN_ARTIFACT_SCHEMA_PREFIXES = ("phase4.", "phase5.")
_RUN_ARTIFACT_JSON_READ_LIMIT = 1024 * 1024


def run_artifact_name_hint(path: Path) -> str | None:
    """Name-based prior-run artifact hint for ``path`` (no file content read).

    Returns a short reason string when the name is an obvious prior-run
    artifact (run database, bytecode cache, JSON-lines transcript), else None.
    """
    suffix = path.suffix.lower()
    if suffix in RUN_ARTIFACT_DATABASE_EXTENSIONS:
        return f"run database file ({suffix})"
    if suffix in RUN_ARTIFACT_BYTECODE_EXTENSIONS:
        return "machine bytecode cache"
    if suffix in RUN_ARTIFACT_TRANSCRIPT_EXTENSIONS:
        return "JSON-lines transcript export"
    if RUN_ARTIFACT_PYCACHE_DIRNAME in path.parts:
        return "bytecode cache directory"
    return None


def run_artifact_content_hint(path: Path) -> str | None:
    """Content-based prior-run export detection for small JSON files.

    Reads at most 1 MiB; a JSON object whose ``schema_version`` carries a
    known pipeline marker prefix is a prior-run export (input manifest, run
    packet, ledger, or other tool export). Unreadable/unparsable files are
    not flagged here.
    """
    if path.suffix.lower() != ".json":
        return None
    try:
        with path.open("rb") as handle:
            head = handle.read(_RUN_ARTIFACT_JSON_READ_LIMIT)
        payload = json.loads(head.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    schema_version = payload.get("schema_version")
    if isinstance(schema_version, str) and schema_version.startswith(
        _RUN_ARTIFACT_SCHEMA_PREFIXES
    ):
        return f"prior-run pipeline export (schema_version={schema_version})"
    return None


def is_run_artifact(path: Path) -> str | None:
    """Return the prior-run artifact reason for ``path``, or None.

    Combines the name-based hint with content-based JSON export detection.
    Purely generic: no project, protocol, or clinical semantics.
    """
    return run_artifact_name_hint(path) or run_artifact_content_hint(path)


class ManifestMode(str, Enum):
    MANIFEST = "manifest"
    COPY = "copy"


class Decision(str, Enum):
    INCLUDE = "include"
    EXCLUDE = "exclude"


@dataclass(frozen=True)
class ManifestEntry:
    relative_path: str
    source_root: str
    sha256: str
    size_bytes: int
    file_type: str
    decision: str
    reason: str
    run_artifact: bool = False
    run_artifact_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class InputManifestError(ValueError):
    """Contract or safety violation for the Phase 5.8 input manifest tool."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _resolve_existing_dir(path: Path | str, *, label: str) -> Path:
    resolved = Path(path).expanduser().resolve(strict=False)
    if not resolved.exists():
        raise InputManifestError(f"{label} does not exist: {resolved}")
    if not resolved.is_dir():
        raise InputManifestError(f"{label} is not a directory: {resolved}")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _normalize_include_paths(items: Iterable[str]) -> frozenset[str]:
    normalized: set[str] = set()
    for item in items:
        raw = str(item).replace("\\", "/")
        path = Path(raw)
        if not raw or path.is_absolute() or ".." in path.parts:
            raise InputManifestError("include paths must be non-empty relative paths")
        value = path.as_posix()
        if value.startswith("./"):
            value = value[2:]
        if not value or value == ".":
            raise InputManifestError("include paths must be non-empty relative paths")
        normalized.add(value)
    return frozenset(normalized)


def classify_path(
    path: Path,
    *,
    exclude_kinds: Iterable[str] = (),
) -> tuple[str, Decision, str]:
    """Return ``(file_type, decision, reason)`` for a filesystem path."""
    name = path.name
    lower_name = name.lower()
    excluded = frozenset(exclude_kinds)
    unknown = excluded - EXCLUDABLE_KINDS
    if unknown:
        raise InputManifestError(f"unknown exclude kinds: {sorted(unknown)}")

    if lower_name == ".ds_store" or lower_name.startswith("._") or lower_name.startswith("~$"):
        return ("system", Decision.EXCLUDE, "excluded operating-system or temporary file")

    for compound in COMPOUND_ARCHIVE_SUFFIXES:
        if lower_name.endswith(compound):
            decision = Decision.EXCLUDE if "archive" in excluded else Decision.INCLUDE
            return ("archive", decision, f"{decision.value} archive suffix {compound}")

    suffix = path.suffix.lower()
    if suffix in PHOTO_EXTENSIONS:
        decision = Decision.EXCLUDE if "photo" in excluded else Decision.INCLUDE
        return ("photo", decision, f"{decision.value} photo suffix {suffix}")
    if suffix in ARCHIVE_EXTENSIONS:
        decision = Decision.EXCLUDE if "archive" in excluded else Decision.INCLUDE
        return ("archive", decision, f"{decision.value} archive suffix {suffix}")
    if suffix:
        file_type = suffix.lstrip(".")
    else:
        file_type = "unknown"
    return (
        file_type,
        Decision.INCLUDE,
        "included clinical/source document candidate",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(source_root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(source_root, followlinks=False):
        # Stable walk order for reproducible manifests.
        dirnames.sort()
        filenames.sort()
        current = Path(dirpath)
        for filename in filenames:
            candidate = current / filename
            if candidate.is_symlink():
                continue
            if not candidate.is_file():
                continue
            yield candidate


def inventory_source_root(
    source_root: Path | str,
    *,
    exclude_kinds: Iterable[str] = (),
    include_paths: Iterable[str] = (),
) -> list[ManifestEntry]:
    root = _resolve_existing_dir(source_root, label="source root")
    selected_paths = _normalize_include_paths(include_paths)
    entries: list[ManifestEntry] = []
    if selected_paths:
        selected_files = [root / relative for relative in sorted(selected_paths)]
        missing = [path.relative_to(root).as_posix() for path in selected_files if not path.is_file()]
        if missing:
            raise InputManifestError(f"explicitly selected paths were not found: {missing}")
        file_paths: Iterable[Path] = selected_files
    else:
        file_paths = _iter_files(root)
    for file_path in file_paths:
        relative = file_path.relative_to(root).as_posix()
        file_type, decision, reason = classify_path(
            file_path,
            exclude_kinds=exclude_kinds,
        )
        size_bytes = file_path.stat().st_size
        artifact_reason = is_run_artifact(file_path)
        entries.append(
            ManifestEntry(
                relative_path=relative,
                source_root=str(root),
                sha256=sha256_file(file_path),
                size_bytes=size_bytes,
                file_type=file_type,
                decision=decision.value,
                reason=reason,
                run_artifact=artifact_reason is not None,
                run_artifact_reason=artifact_reason,
            )
        )
    return entries


def build_manifest(
    source_roots: Sequence[Path | str],
    *,
    mode: ManifestMode | str = ManifestMode.MANIFEST,
    destination: Path | str | None = None,
    label: str | None = None,
    exclude_kinds: Iterable[str] = (),
    include_paths: Iterable[str] = (),
) -> dict[str, object]:
    """Inventory one or more source roots into a content-hash manifest.

    ``mode`` defaults to manifest-only. Copy planning requires
    ``ManifestMode.COPY`` and a destination that is outside every source root.
    """
    resolved_mode = ManifestMode(mode)
    excluded_kinds = frozenset(exclude_kinds)
    selected_paths = _normalize_include_paths(include_paths)
    unknown_exclusions = excluded_kinds - EXCLUDABLE_KINDS
    if unknown_exclusions:
        raise InputManifestError(
            f"unknown exclude kinds: {sorted(unknown_exclusions)}"
        )
    roots = [_resolve_existing_dir(root, label="source root") for root in source_roots]
    if not roots:
        raise InputManifestError("at least one source root is required")

    # Detect overlapping roots to keep relative paths unambiguous per root.
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            if _is_relative_to(left, right) or _is_relative_to(right, left):
                raise InputManifestError(
                    f"source roots must not nest: {left} and {right}"
                )

    dest: Path | None = None
    if resolved_mode is ManifestMode.COPY:
        if destination is None:
            raise InputManifestError("copy mode requires an explicit destination")
        dest = Path(destination).expanduser().resolve(strict=False)
        for root in roots:
            if (
                dest == root
                or _is_relative_to(dest, root)
                or _is_relative_to(root, dest)
            ):
                raise InputManifestError(
                    "destination and source roots must be disjoint: "
                    f"destination={dest}; source={root}"
                )
    elif destination is not None:
        raise InputManifestError(
            "destination is only valid with explicit copy mode; "
            "default mode is manifest-only"
        )

    entries: list[ManifestEntry] = []
    for root in roots:
        entries.extend(
            inventory_source_root(
                root,
                exclude_kinds=excluded_kinds,
                include_paths=selected_paths,
            )
        )

    included = [entry for entry in entries if entry.decision == Decision.INCLUDE.value]
    excluded = [entry for entry in entries if entry.decision == Decision.EXCLUDE.value]

    copy_plan: list[dict[str, str]] = []
    if resolved_mode is ManifestMode.COPY and dest is not None:
        for entry in included:
            source_file = Path(entry.source_root) / entry.relative_path
            # Preserve relative path under a per-root directory named after the
            # source root basename to avoid collisions across multiple roots.
            root_key = Path(entry.source_root).name
            target = dest / root_key / entry.relative_path
            copy_plan.append(
                {
                    "source_path": str(source_file),
                    "destination_path": str(target),
                    "relative_path": f"{root_key}/{entry.relative_path}",
                    "sha256": entry.sha256,
                }
            )

    payload: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "created_at": _utc_now_iso(),
        "label": label,
        "mode": resolved_mode.value,
        "hash_algorithm": HASH_ALGORITHM,
        "selection_policy": {
            "exclude_kinds": sorted(excluded_kinds),
            "include_paths": sorted(selected_paths),
            "always_excluded": ["operating_system_metadata", "temporary_office_files"],
        },
        "source_roots": [str(root) for root in roots],
        "destination": str(dest) if dest is not None else None,
        "summary": {
            "total_files": len(entries),
            "included_files": len(included),
            "excluded_files": len(excluded),
            "copy_plan_entries": len(copy_plan),
            "run_artifact_files": sum(
                1 for entry in entries if entry.run_artifact
            ),
        },
        "entries": [entry.to_dict() for entry in entries],
        "copy_plan": copy_plan,
        "source_immutability": {
            "policy": "sources_are_read_only; tool never deletes or rewrites source files",
            "verified": False,
            "checks": [],
        },
    }
    return payload


def verify_source_immutability(manifest: Mapping[str, object]) -> dict[str, object]:
    """Re-hash every inventoried source file and compare to the manifest."""
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise InputManifestError("manifest entries missing or invalid")

    checks: list[dict[str, object]] = []
    all_ok = True
    for raw in entries:
        if not isinstance(raw, Mapping):
            raise InputManifestError("manifest entry must be an object")
        relative_path = str(raw["relative_path"])
        source_root = Path(str(raw["source_root"]))
        expected_sha = str(raw["sha256"])
        expected_size = int(raw["size_bytes"])
        path = source_root / relative_path
        if not path.is_file():
            all_ok = False
            checks.append(
                {
                    "relative_path": relative_path,
                    "source_root": str(source_root),
                    "ok": False,
                    "error": "source file missing during immutability check",
                }
            )
            continue
        actual_size = path.stat().st_size
        actual_sha = sha256_file(path)
        ok = actual_sha == expected_sha and actual_size == expected_size
        if not ok:
            all_ok = False
        checks.append(
            {
                "relative_path": relative_path,
                "source_root": str(source_root),
                "ok": ok,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "expected_size_bytes": expected_size,
                "actual_size_bytes": actual_size,
            }
        )

    result = {
        "policy": "sources_are_read_only; tool never deletes or rewrites source files",
        "verified": all_ok,
        "checked_at": _utc_now_iso(),
        "checks": checks,
    }
    return result


def execute_copy_plan(manifest: Mapping[str, object]) -> dict[str, object]:
    """Copy included files per the manifest plan and verify destination hashes.

    Sources are opened read-only via ``shutil.copy2`` semantics without deleting
    or rewriting source files. Destination parent directories are created as needed.
    """
    if manifest.get("mode") != ManifestMode.COPY.value:
        raise InputManifestError("execute_copy_plan requires mode=copy")
    destination = manifest.get("destination")
    if not destination:
        raise InputManifestError("copy plan missing destination")
    dest_root = Path(str(destination)).expanduser().resolve(strict=False)
    source_roots = [Path(str(item)) for item in manifest.get("source_roots", [])]
    for root in source_roots:
        if (
            dest_root == root
            or _is_relative_to(dest_root, root)
            or _is_relative_to(root, dest_root)
        ):
            raise InputManifestError(
                "destination and source roots must be disjoint: "
                f"destination={dest_root}; source={root}"
            )

    plan = manifest.get("copy_plan")
    if not isinstance(plan, list):
        raise InputManifestError("copy_plan missing or invalid")

    results: list[dict[str, object]] = []
    all_ok = True
    for item in plan:
        if not isinstance(item, Mapping):
            raise InputManifestError("copy_plan entry must be an object")
        source_path = Path(str(item["source_path"]))
        destination_path = Path(str(item["destination_path"]))
        expected_sha = str(item["sha256"])

        if not any(
            source_path == root or _is_relative_to(source_path, root)
            for root in source_roots
        ):
            raise InputManifestError(
                f"copy source is outside declared source roots: {source_path}"
            )
        if not _is_relative_to(destination_path, dest_root):
            raise InputManifestError(
                f"copy destination escapes declared destination: {destination_path}"
            )

        for root in source_roots:
            if destination_path == root or _is_relative_to(destination_path, root):
                raise InputManifestError(
                    "refusing to write destination inside a source root: "
                    f"{destination_path}"
                )

        if not source_path.is_file():
            all_ok = False
            results.append(
                {
                    "source_path": str(source_path),
                    "destination_path": str(destination_path),
                    "ok": False,
                    "error": "source file missing before copy",
                }
            )
            continue

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        # copy2 preserves metadata but does not alter the source file.
        shutil.copy2(source_path, destination_path)
        actual_sha = sha256_file(destination_path)
        ok = actual_sha == expected_sha
        if not ok:
            all_ok = False
        results.append(
            {
                "source_path": str(source_path),
                "destination_path": str(destination_path),
                "relative_path": str(item.get("relative_path", "")),
                "ok": ok,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "size_bytes": destination_path.stat().st_size,
            }
        )

    return {
        "verified": all_ok,
        "copied_at": _utc_now_iso(),
        "results": results,
    }


def write_manifest_json(manifest: Mapping[str, object], output_path: Path | str) -> Path:
    path = Path(output_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path.resolve(strict=False)


def run_inventory(
    source_roots: Sequence[Path | str],
    *,
    mode: ManifestMode | str = ManifestMode.MANIFEST,
    destination: Path | str | None = None,
    output: Path | str | None = None,
    label: str | None = None,
    verify_sources: bool = True,
    perform_copy: bool = False,
    exclude_kinds: Iterable[str] = (),
    include_paths: Iterable[str] = (),
) -> dict[str, object]:
    """Build a manifest, optionally verify sources, and optionally execute copy."""
    resolved_mode = ManifestMode(mode)
    if perform_copy and resolved_mode is not ManifestMode.COPY:
        raise InputManifestError("perform_copy requires explicit mode=copy")

    manifest = build_manifest(
        source_roots,
        mode=resolved_mode,
        destination=destination,
        label=label,
        exclude_kinds=exclude_kinds,
        include_paths=include_paths,
    )

    if output is not None:
        output_resolved = Path(output).expanduser().resolve(strict=False)
        for source_root in manifest["source_roots"]:
            root = Path(str(source_root))
            if output_resolved == root or _is_relative_to(output_resolved, root):
                raise InputManifestError(
                    f"manifest output must not be inside a source root: {output_resolved}"
                )

    if verify_sources:
        immutability = verify_source_immutability(manifest)
        manifest["source_immutability"] = immutability
        if not immutability["verified"]:
            raise InputManifestError("source immutability verification failed")

    copy_verification: dict[str, object] | None = None
    if perform_copy:
        copy_verification = execute_copy_plan(manifest)
        manifest["copy_verification"] = copy_verification
        if not copy_verification["verified"]:
            raise InputManifestError("copied file hash verification failed")

    if output is not None:
        write_manifest_json(manifest, output)
    return manifest


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 5.8 read-only source inventory and isolation copy planner. "
            "Default mode writes a content-hash manifest only; copy requires "
            "--mode copy and never writes into source trees."
        )
    )
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        dest="sources",
        help="Source root directory (repeatable). Accepted at runtime only.",
    )
    parser.add_argument(
        "--mode",
        choices=[ManifestMode.MANIFEST.value, ManifestMode.COPY.value],
        default=ManifestMode.MANIFEST.value,
        help="manifest (default) or explicit copy",
    )
    parser.add_argument(
        "--destination",
        default=None,
        help="Isolation copy destination (required for --mode copy)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Workspace-relative or absolute path for the JSON manifest",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Optional label for the inventory run",
    )
    parser.add_argument(
        "--exclude-kind",
        action="append",
        choices=sorted(EXCLUDABLE_KINDS),
        default=[],
        help=(
            "Explicit file category to exclude from the isolation copy "
            "(repeatable: photo, archive). No clinical file category is excluded by default."
        ),
    )
    parser.add_argument(
        "--include-path",
        action="append",
        default=[],
        help=(
            "Exact POSIX-style path relative to each source root to include "
            "(repeatable). Unselected files are not read or recorded."
        ),
    )
    parser.add_argument(
        "--execute-copy",
        action="store_true",
        help=(
            "Actually perform the isolation copy after planning. "
            "Requires --mode copy. Default is plan-only even in copy mode."
        ),
    )
    parser.add_argument(
        "--skip-source-verify",
        action="store_true",
        help="Skip post-inventory source re-hash (not recommended)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        manifest = run_inventory(
            args.sources,
            mode=args.mode,
            destination=args.destination,
            output=args.output,
            label=args.label,
            verify_sources=not args.skip_source_verify,
            perform_copy=args.execute_copy,
            exclude_kinds=args.exclude_kind,
            include_paths=args.include_path,
        )
    except InputManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    summary = manifest.get("summary", {})
    print(
        json.dumps(
            {
                "ok": True,
                "mode": manifest.get("mode"),
                "output": args.output,
                "summary": summary,
                "source_immutability_verified": (
                    (manifest.get("source_immutability") or {}).get("verified")
                ),
                "copy_verified": (
                    (manifest.get("copy_verification") or {}).get("verified")
                    if "copy_verification" in manifest
                    else None
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
