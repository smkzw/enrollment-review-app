"""V2 持久化运维命令：数据路径、运行时检查、迁移、备份与恢复。

用法::

    python -m app.storage.cli paths
    python -m app.storage.cli check-runtime
    python -m app.storage.cli backup
    python -m app.storage.cli upgrade [--revision head]
    python -m app.storage.cli downgrade <revision>
    python -m app.storage.cli restore <backup-file>
    python -m app.storage.cli verify
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from app.storage.config import (
    DataDirError,
    SQLiteRuntimeTooOld,
    resolve_data_paths,
    verify_sqlite_runtime,
)
from app.storage.migrate import (
    BackupIntegrityError,
    MigrationFailure,
    MigrationLockHeld,
    MigrationManager,
)

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.storage.cli", description="V2 持久化运维命令"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("paths", help="输出 V2 数据目录布局")
    subparsers.add_parser("check-runtime", help="校验运行时 SQLite 版本门禁")
    subparsers.add_parser("backup", help="创建迁移前一致备份")
    upgrade_parser = subparsers.add_parser("upgrade", help="备份后迁移到指定版本（默认 head）")
    upgrade_parser.add_argument("--revision", default="head")
    downgrade_parser = subparsers.add_parser("downgrade", help="备份后降级到指定版本")
    downgrade_parser.add_argument("revision")
    restore_parser = subparsers.add_parser("restore", help="从已验证备份恢复数据库")
    restore_parser.add_argument("backup")
    subparsers.add_parser("verify", help="校验 PRAGMA、schema 与基础读写")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        return _dispatch(args)
    except (
        DataDirError,
        SQLiteRuntimeTooOld,
        MigrationFailure,
        MigrationLockHeld,
        BackupIntegrityError,
    ) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "paths":
        paths = resolve_data_paths()
        print(
            json.dumps(
                {
                    "root": str(paths.root),
                    "db_path": str(paths.db_path),
                    "backups_dir": str(paths.backups_dir),
                    "blobs_dir": str(paths.blobs_dir),
                    "migration_lock_path": str(paths.migration_lock_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "check-runtime":
        verify_sqlite_runtime()
        print("SQLite 运行时版本满足 V2 持久化基线。")
        return 0
    if args.command == "backup":
        paths = resolve_data_paths()
        record = MigrationManager(paths).create_backup()
        if record is None:
            print("数据库文件不存在（首次初始化前），未创建备份。")
        else:
            print(f"备份完成：{record.path}")
        return 0
    if args.command == "upgrade":
        paths = resolve_data_paths()
        result = MigrationManager(paths).upgrade(args.revision)
        print(f"迁移完成：{result.from_revision} -> {result.to_revision}")
        if result.backup:
            print(f"备份：{result.backup.path}")
        return 0
    if args.command == "downgrade":
        paths = resolve_data_paths()
        result = MigrationManager(paths).downgrade(args.revision)
        print(f"降级完成：{result.from_revision} -> {result.to_revision}")
        if result.backup:
            print(f"备份：{result.backup.path}")
        return 0
    if args.command == "restore":
        paths = resolve_data_paths()
        record = MigrationManager(paths).restore(Path(args.backup))
        print(f"恢复完成：数据库版本 {record.source_revision}")
        return 0
    if args.command == "verify":
        paths = resolve_data_paths()
        problems = MigrationManager(paths).verify()
        if problems:
            for problem in problems:
                print(f"[失败] {problem}")
            return 1
        print("验证通过：PRAGMA、schema 与基础读写均符合基线。")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
