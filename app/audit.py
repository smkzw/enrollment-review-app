"""Append-only audit ledger helpers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.shared import PROJECTS_DIR, project_dir, validate_storage_id


def _write_entry(path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_audit(project_code: str, event: str, user: str = "", **kwargs: Any) -> None:
    """Write system and project audit events without interrupting the user action."""
    try:
        code = validate_storage_id(project_code, "项目编号")
        entry = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "project_code": code,
            "event": str(event or "").strip(),
            "auth_user": str(user or "").strip(),
            **kwargs,
        }
        _write_entry(PROJECTS_DIR / "_system" / "audit_ledger.jsonl", entry)
        if code != "_system":
            _write_entry(project_dir(code) / "audit_ledger.jsonl", entry)
    except Exception:
        return
