"""V2 持久化配置：数据根目录、路径布局与 SQLite 运行时门禁。

数据根解析顺序：

1. 环境变量 ``ENROLLMENT_V2_DATA_DIR``（相对路径按仓库根解析）；
2. 默认 ``<repo>/data_v2``。

布局::

    <root>/enrollment-review-v2.sqlite3   主数据库
    <root>/backups/                       迁移前一致备份与清单
    <root>/blobs/                         大对象目录（本阶段仅边界）
    <root>/.migration.lock                本机迁移锁

旧系统数据根（``projects/`` 等）受写边界保护，V2 数据根不得与其重叠。
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.storage.boundaries import ProtectedPathError, WriteBoundary

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_DATA_DIR = "ENROLLMENT_V2_DATA_DIR"
DEFAULT_DATA_ROOT = REPO_ROOT / "data_v2"
DB_FILENAME = "enrollment-review-v2.sqlite3"
BACKUPS_DIRNAME = "backups"
BLOBS_DIRNAME = "blobs"
MIGRATION_LOCK_FILENAME = ".migration.lock"

# SQLite 3.51.3 修复了官方披露的 WAL-reset 并发竞态；低于该版本不得启动 V2 写服务。
MIN_SQLITE_VERSION: tuple[int, int, int] = (3, 51, 3)

# 声明为只读的 legacy 数据根；V2 数据根不得与其重叠。
LEGACY_DATA_ROOTS: tuple[Path, ...] = (REPO_ROOT / "projects",)


class DataDirError(RuntimeError):
    """V2 数据目录配置不合法，附带中文说明。"""


class SQLiteRuntimeTooOld(RuntimeError):
    """运行时 SQLite 版本低于 WAL 正确性基线，V2 写服务拒绝启动。"""


def runtime_sqlite_version() -> tuple[int, int, int]:
    """当前 Python 运行时内置 SQLite 的版本号。"""
    info = sqlite3.sqlite_version_info
    return (info[0], info[1], info[2])


def verify_sqlite_runtime(version: tuple[int, ...] | None = None) -> None:
    """验证运行时 SQLite 满足 WAL 正确性基线，不合格时抛出中文错误。"""
    actual = tuple(version) if version is not None else runtime_sqlite_version()
    if actual < MIN_SQLITE_VERSION:
        raise SQLiteRuntimeTooOld(
            "当前 Python 内置 SQLite 版本为 "
            f"{'.'.join(map(str, actual))}，低于 V2 持久化所需的最低版本 "
            f"{'.'.join(map(str, MIN_SQLITE_VERSION))}。为保证 WAL 模式的数据安全，"
            "V2 写服务不会启动。请升级 Python 运行时或改用满足版本要求的解释器后重试。"
        )


def resolve_data_root(
    env_override: str | None = None,
    legacy_roots: tuple[Path, ...] | list[Path] | None = None,
) -> Path:
    """解析 V2 数据根目录并验证其与 legacy 数据根不重叠。"""
    value = env_override if env_override is not None else os.environ.get(ENV_DATA_DIR)
    root = Path(value).expanduser() if value else DEFAULT_DATA_ROOT
    if not root.is_absolute():
        root = REPO_ROOT / root
    root = root.resolve()
    protected = tuple(legacy_roots) if legacy_roots is not None else LEGACY_DATA_ROOTS
    try:
        WriteBoundary.create(root, protected)
    except ProtectedPathError as exc:
        raise DataDirError(f"V2 数据目录 {root} 与受保护的旧系统目录重叠：{exc}") from exc
    return root


@dataclass(frozen=True)
class DataPaths:
    """V2 数据目录内的固定路径布局。"""

    root: Path
    db_path: Path
    backups_dir: Path
    blobs_dir: Path
    migration_lock_path: Path
    boundary: WriteBoundary

    def ensure_directories(self) -> None:
        for directory in (self.root, self.backups_dir, self.blobs_dir):
            directory.mkdir(parents=True, exist_ok=True)


def resolve_data_paths(
    env_override: str | None = None,
    legacy_roots: tuple[Path, ...] | list[Path] | None = None,
) -> DataPaths:
    """解析 V2 数据目录布局；数据根与 legacy 目录重叠时抛出中文错误。"""
    root = resolve_data_root(env_override, legacy_roots)
    protected = tuple(legacy_roots) if legacy_roots is not None else LEGACY_DATA_ROOTS
    return DataPaths(
        root=root,
        db_path=root / DB_FILENAME,
        backups_dir=root / BACKUPS_DIRNAME,
        blobs_dir=root / BLOBS_DIRNAME,
        migration_lock_path=root / MIGRATION_LOCK_FILENAME,
        boundary=WriteBoundary.create(root, protected),
    )
