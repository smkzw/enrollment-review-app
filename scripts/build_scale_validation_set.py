"""Build an isolated scale-validation set from a folder of real evidence files.

The set is always written to a unique directory outside every checkout. Page
counts come from the same PDF/image decoder used by the product: one page for a
normal image, one page per TIFF frame, and a known count for HEIC only when the
installed decoder can actually open it. An unknown count is recorded and makes
the set ineligible for a completeness run.

Usage:
    python scripts/build_scale_validation_set.py --dir <真实资料文件夹> \
        [--out-root ~/wp08-scale-sets]
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from app.domain.contracts.enums import PageArtifactStatus
from app.evidence.paging import page_source_document
from app.services.evidence_upload_service import detect_file_format


MEDIA_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".tiff", ".tif"}
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/heic",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _source_roots() -> tuple[Path, ...]:
    current = _repo_root().resolve()
    roots = [current]
    if current.parent.name == ".worktrees":
        roots.append(current.parent.parent.resolve())
    return tuple(roots)


def _contains_symlink(path: Path) -> bool:
    absolute = path.expanduser().absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.exists() and current.is_symlink():
            return True
    return False


def _inside(candidate: Path, root: Path) -> bool:
    return candidate == root or root in candidate.parents


def _resolve_output_root(candidate: Path) -> Path:
    requested = candidate.expanduser()
    if _contains_symlink(requested):
        raise SystemExit(f"输出目录不得经过符号链接: {requested}")
    resolved = requested.resolve(strict=False)
    if any(_inside(resolved, root) for root in _source_roots()):
        raise SystemExit(f"输出目录不得位于源码或工作树内: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    if resolved.is_symlink():
        raise SystemExit(f"输出目录不得是符号链接: {resolved}")
    return resolved


def _new_run_dir(root: Path) -> Path:
    for _ in range(10):
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        candidate = root / f"scale-set-{stamp}-{uuid4().hex[:8]}"
        try:
            candidate.mkdir(mode=0o700)
        except FileExistsError:
            continue
        return candidate
    raise SystemExit("无法建立唯一的规模验证目录")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _page_count(
    content: bytes, file_name: str, digest: str
) -> tuple[int | None, str | None, str]:
    detected = detect_file_format(file_name, content)
    if not detected.supported or detected.kind not in {"pdf", "image"}:
        return None, detected.reason or "正式上传入口不支持该文件", detected.media_type
    plan = page_source_document(
        content=content,
        media_kind=detected.kind,
        source_sha256=digest,
    )
    failures = [page for page in plan.pages if page.status == PageArtifactStatus.FAILED]
    if failures:
        detail = failures[0].technical_detail or failures[0].failure_reason or "无法确定页数"
        return None, detail, detected.media_type
    if plan.page_total < 1:
        return None, "文件中没有可处理页面", detected.media_type
    return plan.page_total, None, detected.media_type


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="真实证据文件所在文件夹")
    parser.add_argument(
        "--out-root",
        default=os.environ.get("SCALE_SET_DIR", str(Path.home() / "wp08-scale-sets")),
        help="源码树外的规模验证根目录；每次自动建立唯一子目录",
    )
    args = parser.parse_args()

    src_dir = Path(args.dir).expanduser().resolve()
    if not src_dir.is_dir():
        raise SystemExit(f"资料文件夹不存在: {src_dir}")
    media = sorted(
        path for path in src_dir.iterdir()
        if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES
    )
    skipped = sorted(
        path.name for path in src_dir.iterdir()
        if path.is_file() and path.suffix.lower() not in MEDIA_SUFFIXES
    )
    if not media:
        raise SystemExit("该文件夹没有可识别的证据文件（PDF、JPG、PNG、HEIC、TIFF）")

    out_dir = _new_run_dir(_resolve_output_root(Path(args.out_root)))
    set_dir = out_dir / "set"
    set_dir.mkdir(mode=0o700)

    files: list[dict[str, object]] = []
    total_pages = 0
    unknown_pages: list[dict[str, str]] = []
    for position, src in enumerate(media, 1):
        content = src.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        suffix = src.suffix.lower()
        pages, page_error, media_type = _page_count(content, src.name, digest)
        destination = set_dir / f"{digest}{suffix}"
        if destination.exists():
            if sha256_file(destination) != digest:
                raise SystemExit(f"内容寻址冲突: {destination}")
        else:
            shutil.copy2(src, destination)
        if sha256_file(destination) != digest:
            raise SystemExit(f"暂存副本复核不一致: {destination}")
        source_id = f"evidence-{position:04d}"
        files.append({
            "source_id": source_id,
            "upload_name": f"{source_id}{suffix}",
            "media_type": media_type if pages is not None else MIME_TYPES[suffix],
            "page_count": pages,
            "page_count_status": "known" if pages is not None else "unknown",
            "byte_size": len(content),
            "sha256": digest,
            "staged_path": str(destination),
        })
        if pages is None:
            unknown_pages.append({"source_id": source_id, "reason": page_error or "无法确定页数"})
        else:
            total_pages += pages

    inventory_complete = not unknown_pages
    manifest = {
        "set_version": "wp08-scale-set/v3",
        "created_at": datetime.now(UTC).isoformat(),
        "staged_dir": str(set_dir),
        "total_files": len(files),
        "known_pages": total_pages,
        "page_inventory_complete": inventory_complete,
        "unknown_page_files": unknown_pages,
        "skipped_non_evidence_file_count": len(skipped),
        "files": files,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "files": len(files),
        "known_pages": total_pages,
        "page_inventory_complete": inventory_complete,
        "unknown_page_files": unknown_pages,
        "staged_dir": str(set_dir),
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
    }, ensure_ascii=False, indent=2))
    if not inventory_complete:
        print("资料中存在无法确认页数的文件；清单已保留，但不得据此宣称完整或启动规模验收。")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
