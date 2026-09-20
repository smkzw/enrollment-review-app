"""Validate the prebuilt same-origin product, not the static trial bundle."""
import hashlib
import json
from pathlib import Path


def require_product_frontend(directory: Path) -> Path:
    root = directory.resolve()
    try:
        manifest = json.loads((root / "product-build.json").read_text(encoding="utf-8"))
        if (not isinstance(manifest, dict)
                or manifest.get("version") != "enrollment-product-build/v1"
                or manifest.get("interface_trial") is not False
                or manifest.get("protocol_stub") is not False
                or manifest.get("api_base") != ""
                or manifest.get("asset_base") != "/"):
            raise ValueError("not a same-origin product build")
        files = manifest["files"]
        if not isinstance(files, dict) or "index.html" not in files:
            raise ValueError("missing entry")
        for name, expected_hash in files.items():
            path = (root / name).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError("missing build member")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                raise ValueError("changed build member")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(
            "正式界面文件不完整或版本不符，请重新构建正式版本；不会用试用页面替代。"
        ) from exc
    return root
