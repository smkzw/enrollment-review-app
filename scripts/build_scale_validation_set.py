"""Build a WP08 scale-validation set from a user-provided folder of real files.

F07 hardening:
- Staged copies land OUTSIDE the repo source tree by default (repo must keep
  only a de-identified manifest and technical metrics; real clinical files
  never enter a trackable path).
- All common evidence media types are inventoried (pdf/jpg/jpeg/png/heic/
  tiff/tif), not just PDFs; PDF page counts verified via fitz.
- Staging is content-addressed (sha256-named), never overwrites, and each
  staged copy is re-hashed before the manifest is written.

Usage:
    python scripts/build_scale_validation_set.py --dir <真实资料文件夹> \
        [--out runs/execution/wp08-scale-validation]
    # 若 --out 落在仓库源码树内，脚本会自动改写到数据根之外并提示。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

MEDIA_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".tiff", ".tif"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def pdf_pages(path: Path) -> int | None:
    if path.suffix.lower() != ".pdf":
        return None
    import fitz

    with fitz.open(path) as doc:
        return len(doc)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _escape_repo_path(candidate: Path) -> Path:
    resolved = candidate.resolve()
    repo = _repo_root().resolve()
    if repo in resolved.parents or resolved == repo:
        safe = Path(os.environ.get("SCALE_SET_DIR", str(Path.home() / "wp08-scale-sets"))) / candidate.name
        safe.mkdir(parents=True, exist_ok=True)
        print(f"[F07] 拒绝把真实资料写入源码树，已改用源码树外路径: {safe}")
        return safe
    return resolved


def main() -> int:
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="真实证据文件所在文件夹")
    parser.add_argument("--out", default="runs/execution/wp08-scale-validation")
    args = parser.parse_args()

    src_dir = Path(args.dir)
    if not src_dir.is_dir():
        raise SystemExit(f"资料文件夹不存在: {src_dir}")
    media = sorted(
        p for p in src_dir.iterdir()
        if p.is_file() and p.suffix.lower() in MEDIA_SUFFIXES
    )
    skipped = [p.name for p in src_dir.iterdir()
               if p.is_file() and p.suffix.lower() not in MEDIA_SUFFIXES]
    if not media:
        raise SystemExit("该文件夹没有可识别的证据文件（pdf/jpg/png/heic/tiff）")
    if skipped:
        print(f"[warn] 忽略非证据文件 {len(skipped)} 个: {skipped[:5]}...")

    out_dir = _escape_repo_path(Path(args.out))
    set_dir = out_dir / "set"
    set_dir.mkdir(parents=True, exist_ok=True)

    files = []
    total_pages = 0
    unreadable: list[dict] = []
    for src in media:
        pages = None
        if src.suffix.lower() == ".pdf":
            try:
                pages = pdf_pages(src)
            except Exception as exc:
                unreadable.append({"file": src.name, "reason": f"pdf打开失败: {exc}"})
                continue
        data = src.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        dst = set_dir / f"{sha[:16]}{src.suffix.lower()}"
        if dst.exists():
            if sha256_file(dst) != sha:
                raise SystemExit(f"内容寻址冲突: {dst}")
        else:
            shutil.copy2(src, dst)
        if sha256_file(dst) != sha:
            raise SystemExit(f"暂存副本复核不一致: {dst}")
        files.append({
            "file_name": src.name,
            "media_type": src.suffix.lower().lstrip("."),
            "pdf_pages": pages,
            "byte_size": len(data),
            "sha256": sha,
            "staged_path": str(dst),
        })
        if pages:
            total_pages += pages

    if unreadable:
        raise SystemExit(f"有 {len(unreadable)} 个文件无法打开，整集拒绝（不静默忽略）: {unreadable}")

    manifest = {
        "set_version": "wp08-scale-set/v2",
        "source_dir": str(src_dir),
        "staged_dir": str(set_dir),
        "total_files": len(files),
        "total_pages": total_pages,
        "files": files,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({
        "files": len(files),
        "pages": total_pages,
        "staged_dir": str(set_dir),
        "manifest": str(out_dir / "manifest.json"),
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
