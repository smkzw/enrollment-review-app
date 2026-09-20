"""Phase 5 fresh acceptance runtime directory + identity gate.

Prepares an empty V2 data root and refuses contaminated runtimes before a
representative-subject acceptance entry is treated as new.

Gate rules are project-agnostic:

* require a fresh-marker file;
* refuse databases that already carry jobs or other business state;
* refuse any ``failed_final`` / ``failed`` / ``cancelled`` job identity;
* refuse opaque forbidden job ids and model identities supplied by contract;
* only allow hash-verified immutable isolation manifests as reusable inputs;
* never modify source clinical trees or migrate an old failed database.

The tool does not encode disease, drug, protocol, or subject semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "phase5.fresh_runtime.v1"
CONTRACT_SCHEMA_VERSION = "phase5.fresh_runtime_contract.v1"
FRESH_MARKER_NAME = ".phase5_fresh_acceptance"
RUNTIME_IDENTITY_NAME = "runtime-identity.json"
DB_FILENAME = "enrollment-review-v2.sqlite3"
DEFAULT_MARKER_TEXT = (
    "Phase 5 isolated acceptance database marker. "
    "No legacy project or prior failed runtime may be reused.\n"
)

# Tables that prove the database already carries acceptance/business state.
BUSINESS_STATE_TABLES: tuple[str, ...] = (
    "jobs",
    "job_steps",
    "job_events",
    "job_checkpoints",
    "projects",
    "subjects",
    "review_episodes",
    "protocol_projects",
    "clinical_facts",
    "patient_profile_revisions",
)

CONFIGURATION_TABLES: tuple[str, ...] = ("model_configs", "prompt_versions")

TERMINAL_POLLUTED_JOB_STATES = frozenset(
    {"failed", "failed_final", "cancelled", "succeeded"}
)


class FreshRuntimeError(RuntimeError):
    """Fresh runtime identity gate failed with a Chinese diagnostic."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise FreshRuntimeError(f"无法读取 JSON：{path}（{exc}）") from exc
    except json.JSONDecodeError as exc:
        raise FreshRuntimeError(f"JSON 无法解析：{path}（{exc}）") from exc
    if not isinstance(payload, dict):
        raise FreshRuntimeError(f"JSON 顶层必须是对象：{path}")
    return payload


def _normalize_model_identity(
    provider: str, model: str, reasoning_effort: str | None = None
) -> dict[str, str]:
    identity = {
        "provider": str(provider).strip().lower(),
        "model": str(model).strip().lower(),
    }
    effort = (reasoning_effort or "").strip().lower()
    if effort:
        identity["reasoning_effort"] = effort
    return identity


def _model_identity_key(identity: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(identity.get("provider", "")).strip().lower(),
        str(identity.get("model", "")).strip().lower(),
        str(identity.get("reasoning_effort", "")).strip().lower(),
    )


@dataclass(frozen=True)
class FreshRuntimeContract:
    """Opaque deny-list + required manifests for one fresh acceptance entry."""

    path: Path | None
    forbidden_job_ids: frozenset[str]
    forbidden_model_identities: tuple[dict[str, str], ...]
    required_manifests: tuple[Path, ...]
    notes: tuple[str, ...]

    @classmethod
    def load(cls, path: Path | None) -> "FreshRuntimeContract":
        if path is None:
            return cls(
                path=None,
                forbidden_job_ids=frozenset(),
                forbidden_model_identities=(),
                required_manifests=(),
                notes=(),
            )
        payload = _read_json(path)
        schema = payload.get("schema_version")
        if schema != CONTRACT_SCHEMA_VERSION:
            raise FreshRuntimeError(
                "fresh runtime 合同 schema_version 必须为 "
                f"{CONTRACT_SCHEMA_VERSION}，实际为 {schema!r}：{path}"
            )
        forbidden_jobs = {
            str(item).strip()
            for item in payload.get("forbidden_job_ids", [])
            if str(item).strip()
        }
        forbidden_models: list[dict[str, str]] = []
        for raw in payload.get("forbidden_model_identities", []):
            if not isinstance(raw, Mapping):
                raise FreshRuntimeError(
                    f"forbidden_model_identities 条目必须是对象：{path}"
                )
            provider = str(raw.get("provider", "")).strip()
            model = str(raw.get("model", "")).strip()
            if not provider or not model:
                raise FreshRuntimeError(
                    f"forbidden_model_identities 需要 provider 与 model：{path}"
                )
            forbidden_models.append(
                _normalize_model_identity(
                    provider,
                    model,
                    str(raw.get("reasoning_effort", "")).strip() or None,
                )
            )
        manifests: list[Path] = []
        for raw in payload.get("required_manifests", []):
            candidate = Path(str(raw)).expanduser()
            if not candidate.is_absolute():
                candidate = (path.parent / candidate).resolve()
            else:
                candidate = candidate.resolve()
            manifests.append(candidate)
        notes = tuple(str(item) for item in payload.get("notes", []) if str(item).strip())
        return cls(
            path=path.resolve(),
            forbidden_job_ids=frozenset(forbidden_jobs),
            forbidden_model_identities=tuple(forbidden_models),
            required_manifests=tuple(manifests),
            notes=notes,
        )


def verify_manifest_inputs(manifest_paths: Sequence[Path]) -> dict[str, Any]:
    """Re-hash isolation copies and require verified immutable manifests."""
    if not manifest_paths:
        raise FreshRuntimeError(
            "新验收运行入口必须绑定至少一个哈希验证后的不可变隔离输入清单。"
        )
    reports: list[dict[str, Any]] = []
    for manifest_path in manifest_paths:
        payload = _read_json(manifest_path)
        schema = payload.get("schema_version")
        if schema != "phase5.input_manifest.v1":
            raise FreshRuntimeError(
                "输入清单 schema_version 必须为 phase5.input_manifest.v1，"
                f"实际为 {schema!r}：{manifest_path}"
            )
        immutability = payload.get("source_immutability") or {}
        copy_verification = payload.get("copy_verification") or {}
        if immutability.get("verified") is not True:
            raise FreshRuntimeError(
                f"输入清单未通过源不可变复验：{manifest_path}"
            )
        if payload.get("mode") == "copy" and copy_verification.get("verified") is not True:
            raise FreshRuntimeError(
                f"copy 模式清单未通过副本校验：{manifest_path}"
            )
        summary = payload.get("summary") or {}
        if int(summary.get("run_artifact_files") or 0) > 0:
            raise FreshRuntimeError(
                f"输入清单包含运行产物指纹，禁止作为新验收输入：{manifest_path}"
            )
        mismatches: list[dict[str, str]] = []
        checked = 0
        for item in payload.get("copy_plan") or []:
            if not isinstance(item, Mapping):
                continue
            destination = Path(str(item.get("destination_path", "")))
            expected = str(item.get("sha256", "")).strip().lower()
            relative = str(item.get("relative_path", destination.name))
            if not destination.exists():
                mismatches.append(
                    {
                        "relative_path": relative,
                        "reason": "destination_missing",
                        "destination_path": str(destination),
                    }
                )
                continue
            actual = _sha256_file(destination)
            checked += 1
            if actual != expected:
                mismatches.append(
                    {
                        "relative_path": relative,
                        "reason": "sha256_mismatch",
                        "expected_sha256": expected,
                        "actual_sha256": actual,
                    }
                )
        if mismatches:
            raise FreshRuntimeError(
                "隔离输入哈希复验失败："
                + ", ".join(
                    f"{row['relative_path']}({row['reason']})" for row in mismatches[:5]
                )
            )
        reports.append(
            {
                "manifest_path": str(manifest_path.resolve()),
                "label": payload.get("label"),
                "mode": payload.get("mode"),
                "source_immutability_verified": True,
                "copy_verification_verified": bool(copy_verification.get("verified")),
                "copy_files_rehashed": checked,
                "run_artifact_files": 0,
            }
        )
    return {
        "verified": True,
        "manifest_count": len(reports),
        "manifests": reports,
    }


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _count_rows(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def inspect_runtime_database(db_path: Path) -> dict[str, Any]:
    """Read-only inspect a V2 sqlite database for identity pollution signals."""
    if not db_path.exists():
        return {
            "exists": False,
            "db_path": str(db_path),
            "job_ids": [],
            "job_states": [],
            "model_identities": [],
            "business_state_counts": {},
            "configuration_state_counts": {},
            "pollution_reasons": [],
        }
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise FreshRuntimeError(f"无法只读打开运行库：{db_path}（{exc}）") from exc
    try:
        tables = _table_names(connection)
        job_ids: list[str] = []
        job_states: list[dict[str, str]] = []
        if "jobs" in tables:
            for job_id, state, error_code in connection.execute(
                "SELECT job_id, state, COALESCE(error_code, '') FROM jobs"
            ):
                job_ids.append(str(job_id))
                job_states.append(
                    {
                        "job_id": str(job_id),
                        "state": str(state),
                        "error_code": str(error_code),
                    }
                )
        model_identities: list[dict[str, str]] = []
        if "model_configs" in tables:
            for provider, model, effort in connection.execute(
                "SELECT provider, model, COALESCE(reasoning_effort, '') "
                "FROM model_configs"
            ):
                model_identities.append(
                    _normalize_model_identity(str(provider), str(model), str(effort) or None)
                )
        business_state_counts: dict[str, int] = {}
        for table in BUSINESS_STATE_TABLES:
            if table in tables:
                count = _count_rows(connection, table)
                if count:
                    business_state_counts[table] = count
        configuration_state_counts: dict[str, int] = {}
        for table in CONFIGURATION_TABLES:
            if table in tables:
                count = _count_rows(connection, table)
                if count:
                    configuration_state_counts[table] = count
        pollution_reasons: list[str] = []
        if business_state_counts:
            pollution_reasons.append(
                "database_has_business_state:"
                + ",".join(
                    f"{name}={count}" for name, count in sorted(business_state_counts.items())
                )
            )
        for row in job_states:
            if row["state"] in TERMINAL_POLLUTED_JOB_STATES:
                pollution_reasons.append(
                    f"database_has_terminal_job:{row['job_id']}:{row['state']}"
                )
        # A newly migrated service registers prompt/model configuration before
        # the first job. Configuration rows alone are not prior business state;
        # they become part of an old run identity only once a job exists.
        if model_identities and job_ids:
            pollution_reasons.append(
                "database_has_model_configs:"
                + ",".join(
                    f"{item['provider']}/{item['model']}"
                    + (
                        f":{item['reasoning_effort']}"
                        if item.get("reasoning_effort")
                        else ""
                    )
                    for item in model_identities
                )
            )
        return {
            "exists": True,
            "db_path": str(db_path.resolve()),
            "job_ids": job_ids,
            "job_states": job_states,
            "model_identities": model_identities,
            "business_state_counts": business_state_counts,
            "configuration_state_counts": configuration_state_counts,
            "pollution_reasons": pollution_reasons,
        }
    finally:
        connection.close()


def validate_runtime_identity(
    runtime_root: Path,
    *,
    contract: FreshRuntimeContract | None = None,
    manifest_paths: Sequence[Path] | None = None,
    require_fresh_marker: bool = True,
) -> dict[str, Any]:
    """Validate that ``runtime_root`` is acceptable as a new acceptance data dir."""
    root = runtime_root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FreshRuntimeError(f"运行目录不存在或不是目录：{root}")

    blocking: list[str] = []
    marker_path = root / FRESH_MARKER_NAME
    if require_fresh_marker and not marker_path.exists():
        blocking.append(f"missing_fresh_marker:{FRESH_MARKER_NAME}")

    active_contract = contract or FreshRuntimeContract.load(None)
    manifests = list(manifest_paths or ())
    if not manifests:
        manifests = list(active_contract.required_manifests)
    manifest_report = verify_manifest_inputs(manifests)

    db_path = root / DB_FILENAME
    inspection = inspect_runtime_database(db_path)
    blocking.extend(inspection["pollution_reasons"])

    for job_id in inspection["job_ids"]:
        if job_id in active_contract.forbidden_job_ids:
            blocking.append(f"forbidden_job_id_present:{job_id}")

    forbidden_model_keys = {
        _model_identity_key(item) for item in active_contract.forbidden_model_identities
    }
    for identity in inspection["model_identities"] if inspection["job_ids"] else ():
        key = _model_identity_key(identity)
        # Exact triple match, or provider+model match when contract omits effort.
        if key in forbidden_model_keys or (
            key[0],
            key[1],
            "",
        ) in forbidden_model_keys:
            blocking.append(
                "forbidden_model_identity_present:"
                f"{identity['provider']}/{identity['model']}"
                + (
                    f":{identity['reasoning_effort']}"
                    if identity.get("reasoning_effort")
                    else ""
                )
            )

    if blocking:
        raise FreshRuntimeError(
            "运行目录身份门禁拒绝：" + "; ".join(blocking)
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "validated_at": _utc_now(),
        "ok": True,
        "runtime_root": str(root),
        "fresh_marker_path": str(marker_path) if marker_path.exists() else None,
        "fresh_marker_present": marker_path.exists(),
        "database": inspection,
        "manifests": manifest_report,
        "contract_path": str(active_contract.path) if active_contract.path else None,
        "forbidden_job_ids_checked": sorted(active_contract.forbidden_job_ids),
        "forbidden_model_identities_checked": list(
            active_contract.forbidden_model_identities
        ),
    }
    return report


def prepare_fresh_runtime(
    runtime_root: Path,
    *,
    contract: FreshRuntimeContract | None = None,
    manifest_paths: Sequence[Path] | None = None,
    marker_text: str = DEFAULT_MARKER_TEXT,
    allow_nonempty_without_db: bool = False,
) -> dict[str, Any]:
    """Create a new empty runtime root and refuse to adopt a polluted database."""
    root = runtime_root.expanduser().resolve()
    active_contract = contract or FreshRuntimeContract.load(None)
    manifests = list(manifest_paths or ())
    if not manifests:
        manifests = list(active_contract.required_manifests)
    manifest_report = verify_manifest_inputs(manifests)

    root.mkdir(parents=True, exist_ok=True)
    db_path = root / DB_FILENAME
    if db_path.exists():
        # Never migrate/repair an old DB into a "fresh" acceptance root.
        inspection = inspect_runtime_database(db_path)
        if inspection["pollution_reasons"] or inspection["job_ids"] or inspection[
            "model_identities"
        ]:
            raise FreshRuntimeError(
                "目标运行目录已存在业务状态数据库，禁止就地复用或迁移；"
                "请改用全新空目录。污染信号："
                + "; ".join(inspection["pollution_reasons"] or ["non_empty_database"])
            )
        raise FreshRuntimeError(
            f"目标运行目录已存在 {DB_FILENAME}；新验收必须使用不含旧库的全新目录。"
        )

    if not allow_nonempty_without_db:
        unexpected = [
            path.name
            for path in root.iterdir()
            if path.name
            not in {
                FRESH_MARKER_NAME,
                RUNTIME_IDENTITY_NAME,
                "backups",
                "blobs",
                ".migration.lock",
            }
        ]
        if unexpected:
            raise FreshRuntimeError(
                "目标运行目录不是空目录，拒绝写入新鲜标记："
                + ", ".join(sorted(unexpected)[:8])
            )

    marker_path = root / FRESH_MARKER_NAME
    marker_path.write_text(marker_text, encoding="utf-8")
    (root / "backups").mkdir(exist_ok=True)
    (root / "blobs").mkdir(exist_ok=True)

    identity = {
        "schema_version": SCHEMA_VERSION,
        "prepared_at": _utc_now(),
        "runtime_root": str(root),
        "fresh_marker_path": str(marker_path),
        "database_path": str(db_path),
        "database_must_be_absent_until_service_start": True,
        "reuse_policy": {
            "old_failed_database_reuse": "forbidden",
            "old_job_id_reuse": "forbidden",
            "old_model_config_reuse": "forbidden",
            "immutable_isolation_inputs_only": True,
        },
        "manifests": manifest_report,
        "contract_path": str(active_contract.path) if active_contract.path else None,
        "forbidden_job_ids": sorted(active_contract.forbidden_job_ids),
        "forbidden_model_identities": list(active_contract.forbidden_model_identities),
        "notes": list(active_contract.notes),
        "env": {
            "ENROLLMENT_V2_DATA_DIR": str(root),
        },
    }
    identity_path = root / RUNTIME_IDENTITY_NAME
    identity_path.write_text(
        json.dumps(identity, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Validate the freshly prepared root (DB absent is OK).
    validation = validate_runtime_identity(
        root,
        contract=active_contract,
        manifest_paths=manifests,
        require_fresh_marker=True,
    )
    return {
        "ok": True,
        "prepared": identity,
        "validation": validation,
        "identity_path": str(identity_path),
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare/validate a fresh Phase 5 acceptance runtime root."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="Create a new empty runtime root")
    prepare.add_argument("--runtime-root", required=True, type=Path)
    prepare.add_argument("--contract", type=Path, default=None)
    prepare.add_argument(
        "--manifest",
        action="append",
        default=[],
        type=Path,
        help="Hash-verified isolation manifest (repeatable)",
    )
    prepare.add_argument(
        "--allow-nonempty-without-db",
        action="store_true",
        help="Allow pre-existing marker/identity files while still refusing databases",
    )

    validate = sub.add_parser("validate", help="Validate an existing runtime root")
    validate.add_argument("--runtime-root", required=True, type=Path)
    validate.add_argument("--contract", type=Path, default=None)
    validate.add_argument(
        "--manifest",
        action="append",
        default=[],
        type=Path,
        help="Hash-verified isolation manifest (repeatable)",
    )

    inspect_cmd = sub.add_parser(
        "inspect-db", help="Read-only inspect a runtime database for pollution"
    )
    inspect_cmd.add_argument("--db", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "inspect-db":
            report = inspect_runtime_database(Path(args.db))
            print(json.dumps({"ok": True, "database": report}, ensure_ascii=False, indent=2))
            return 0

        contract = FreshRuntimeContract.load(args.contract)
        manifests = list(args.manifest)
        if args.command == "prepare":
            result = prepare_fresh_runtime(
                Path(args.runtime_root),
                contract=contract,
                manifest_paths=manifests,
                allow_nonempty_without_db=bool(args.allow_nonempty_without_db),
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "validate":
            result = validate_runtime_identity(
                Path(args.runtime_root),
                contract=contract,
                manifest_paths=manifests,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        raise FreshRuntimeError(f"未知命令：{args.command}")
    except FreshRuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
