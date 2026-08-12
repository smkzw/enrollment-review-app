#!/usr/bin/env python3
"""Reparse persisted review reports and update subject verdict metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import PROJECTS_DIR
from app.report_backfill import backfill_project_reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Project code, e.g. D001-02-II")
    parser.add_argument("--phase", default="full", help="Review phase id, e.g. screening_run_in")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    parser.add_argument("--output", default="", help="Optional JSON summary path")
    args = parser.parse_args()

    project_path = PROJECTS_DIR / args.project
    result = backfill_project_reports(
        project_path,
        project_code=args.project,
        phase=args.phase,
        dry_run=args.dry_run,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
