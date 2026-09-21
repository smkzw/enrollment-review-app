"""Build a WP08 scale-validation set from a user-provided folder of real files.

Verifies every PDF (page count via fitz, sha256, size), stages an immutable
copy, and writes manifest.json. The folder is user-provided real evidence —
the script only inventories and stages; it never fabricates properties.

Usage:
    python scripts/build_scale_validation_set.py --dir <真实资料文件夹> \
        [--out runs/execution/wp08-scale-validation]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def pdf_pages(path: Path) -> int:
    import fitz

    with fitz.open(path) as doc:
        return len(doc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="真实证据PDF所在文件夹")
    parser.add_argument("--out", default="runs/execution/wp08-scale-validation")
    args = parser.parse_args()

    src_dir = Path(args.dir)
    pdfs = sorted(p for p in src_dir.iterdir() if p.suffix.lower() == ".pdf")
    if not pdfs:
        raise SystemExit("该文件夹没有PDF文件")

    out_dir = Path(args.out)
    set_dir = out_dir / "set"
    set_dir.mkdir(parents=True, exist_ok=True)

    files = []
    total_pages = 0
    for src in pdfs:
        data = src.read_bytes()
        pages = pdf_pages(src)
        sha = hashlib.sha256(data).hexdigest()
        dst = set_dir / src.name
        shutil.copy2(src, dst)
        files.append({
            "file_name": src.name,
            "pdf_pages": pages,
            "byte_size": len(data),
            "sha256": sha,
            "staged_path": str(dst),
        })
        total_pages += pages

    manifest = {
        "set_version": "wp08-scale-set/v1",
        "source_dir": str(src_dir),
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
        "staged": str(set_dir),
        "manifest": str(out_dir / "manifest.json"),
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
