"""Alembic 迁移编排：迁移锁、一致备份、升级/降级、失败恢复与启动验证。

启动契约：V2 写服务必须先通过 :func:`upgrade_or_fail` 拿到经过验证的
Engine/Session 工厂，任何一步失败都必须中止启动；迁移前的一致备份与
``restore`` 命令保证失败后可回退。

备份流程（每次迁移前）：

1. 获取本机迁移锁；
2. passive checkpoint 后用 ``sqlite3.Connection.backup()`` 生成一致备份；
3. 对备份执行 ``PRAGMA integrity_check``，写清单（源版本/大小/SHA-256）；
4. Alembic 升级/降级；随后验证 PRAGMA、schema/metadata 一致性与基础读写；
5. 任一步失败即中止，原库与备份保留，提供显式恢复命令。
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import alembic.command
import alembic.config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, UniqueConstraint, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.storage.config import REPO_ROOT, DataPaths, resolve_data_paths, verify_sqlite_runtime
from app.storage.db import (
    BUSY_TIMEOUT_MS,
    Base,
    build_engine,
    build_session_factory,
    check_engine_pragmas,
)

logger = logging.getLogger(__name__)

DEFAULT_ALEMBIC_INI = REPO_ROOT / "alembic.ini"
DEFAULT_SCRIPT_LOCATION = REPO_ROOT / "app" / "storage" / "migrations"


class MigrationLockHeld(RuntimeError):
    """迁移锁被其他进程持有。"""


class BackupIntegrityError(RuntimeError):
    """备份或数据库完整性校验失败。"""


class MigrationFailure(RuntimeError):
    """迁移未完成或未通过启动验证，禁止继续启动写服务。"""


class MigrationLock:
    """本机迁移锁：``fcntl.flock`` 非阻塞排他锁。"""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._handle: Any = None

    def acquire(self) -> "MigrationLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.lock_path.open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise MigrationLockHeld(
                "另一个迁移或恢复进程正在运行，无法获得本机迁移锁；"
                "请等待其完成或确认没有残留进程后重试。"
            ) from exc
        self._handle = handle
        return self

    def release(self) -> None:
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "MigrationLock":
        return self.acquire()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.release()


@dataclass(frozen=True)
class BackupRecord:
    path: Path
    manifest_path: Path
    created_at_utc: str
    source_revision: str
    size_bytes: int
    sha256: str
    integrity: str


@dataclass(frozen=True)
class UpgradeResult:
    backup: BackupRecord | None
    from_revision: str
    to_revision: str


class MigrationManager:
    """迁移编排器：备份、升级/降级、恢复与启动级验证。"""

    def __init__(
        self,
        paths: DataPaths,
        *,
        alembic_ini_path: Path = DEFAULT_ALEMBIC_INI,
        script_location: Path | None = None,
        metadata: MetaData | None = None,
    ) -> None:
        self.paths = paths
        self.alembic_ini_path = alembic_ini_path
        self.script_location = script_location
        self.metadata = metadata if metadata is not None else Base.metadata

    # ------------------------------------------------------------------ 版本

    @staticmethod
    def read_revision(db_path: Path) -> str:
        """读取当前 schema 版本；无版本表时返回 ``base``。"""
        connection = sqlite3.connect(str(db_path), timeout=BUSY_TIMEOUT_MS / 1000)
        try:
            try:
                rows = connection.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchall()
            except sqlite3.OperationalError as exc:
                if "no such table" in str(exc):
                    return "base"
                raise MigrationFailure(f"无法读取当前 schema 版本：{exc}") from exc
        finally:
            connection.close()
        if len(rows) > 1:
            raise MigrationFailure(
                "alembic_version 存在多行版本记录，数据库处于不一致状态，已停止迁移。"
            )
        return str(rows[0][0]) if rows else "base"

    # ------------------------------------------------------------------ 备份

    def create_backup(self) -> BackupRecord | None:
        """对当前数据库创建一致备份并校验完整性；首次初始化（无库文件）返回 None。"""
        db_path = self.paths.db_path
        if not db_path.exists():
            logger.info("数据库文件不存在，跳过迁移前备份（首次初始化）")
            return None
        self.paths.ensure_directories()
        source_revision = self.read_revision(db_path)
        created_at = datetime.now(timezone.utc)
        stamp = created_at.strftime("%Y%m%dT%H%M%S%fZ")
        backup_path = self.paths.backups_dir / f"{stamp}-{source_revision}.sqlite3"
        backup_path = self.paths.boundary.require_v2_target(backup_path)
        source = sqlite3.connect(str(db_path), timeout=BUSY_TIMEOUT_MS / 1000)
        try:
            source.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            source.execute("PRAGMA wal_checkpoint(PASSIVE)")
            destination = sqlite3.connect(str(backup_path))
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
        record = BackupRecord(
            path=backup_path,
            manifest_path=Path(f"{backup_path}.json"),
            created_at_utc=created_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            source_revision=source_revision,
            size_bytes=backup_path.stat().st_size,
            sha256=self._sha256(backup_path),
            integrity=self._integrity_check(backup_path),
        )
        self._write_manifest(record)
        logger.info(
            "迁移前备份完成：%s（源版本 %s，%d 字节）",
            backup_path.name,
            source_revision,
            record.size_bytes,
        )
        return record

    # ------------------------------------------------------------- 升级/降级

    def upgrade(self, revision: str = "head") -> UpgradeResult:
        with MigrationLock(self.paths.migration_lock_path):
            return self._upgrade_locked(revision)

    def _upgrade_locked(self, revision: str) -> UpgradeResult:
        self.paths.ensure_directories()
        current_revision = self.read_revision(self.paths.db_path) if self.paths.db_path.exists() else "base"
        target_revision = self._resolve_target_revision(revision)
        if current_revision == target_revision:
            self._verify_migrated_database(require_revision=True, check_metadata=True)
            return UpgradeResult(
                backup=None,
                from_revision=current_revision,
                to_revision=current_revision,
            )
        backup = self.create_backup()
        from_revision = backup.source_revision if backup else "base"
        try:
            alembic.command.upgrade(self._alembic_config(), revision)
        except Exception as exc:
            raise MigrationFailure(
                "数据库迁移失败，V2 写服务不会启动。原数据库保持迁移前状态"
                + (f"，可从备份 {backup.path.name} 恢复" if backup else "（首次初始化无备份）")
                + "。"
            ) from exc
        self._verify_migrated_database(require_revision=True, check_metadata=True)
        to_revision = self.read_revision(self.paths.db_path)
        return UpgradeResult(backup=backup, from_revision=from_revision, to_revision=to_revision)

    def downgrade(self, revision: str) -> UpgradeResult:
        with MigrationLock(self.paths.migration_lock_path):
            self.paths.ensure_directories()
            backup = self.create_backup()
            from_revision = backup.source_revision if backup else "base"
            try:
                alembic.command.downgrade(self._alembic_config(), revision)
            except Exception as exc:
                raise MigrationFailure(
                    "数据库降级失败，V2 写服务不会启动。原数据库保持降级前状态"
                    + (f"，可从备份 {backup.path.name} 恢复" if backup else "")
                    + "。"
                ) from exc
            # 降级后的 schema 不代表当前 ORM metadata（head），只做 PRAGMA 与基础读写验证
            self._verify_migrated_database(
                require_revision=revision != "base", check_metadata=False
            )
            to_revision = self.read_revision(self.paths.db_path)
            return UpgradeResult(backup=backup, from_revision=from_revision, to_revision=to_revision)

    # ------------------------------------------------------------------ 恢复

    def restore(self, backup_path: Path) -> BackupRecord:
        """从经过完整性校验的备份恢复数据库（创建/覆盖主库并清除残留 WAL）。"""
        backup_path = Path(backup_path)
        if not backup_path.is_file():
            raise MigrationFailure(f"备份文件不存在：{backup_path}")
        self._integrity_check(backup_path)
        manifest_path = Path(f"{backup_path}.json")
        verified_manifest: dict[str, Any] | None = None
        backup_sha256 = self._sha256(backup_path)
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                expected_size = int(manifest["size_bytes"])
                expected_sha256 = str(manifest["sha256"])
                expected_integrity = str(manifest["integrity"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise BackupIntegrityError("备份清单内容不完整或格式错误，拒绝恢复。") from exc
            if expected_size != backup_path.stat().st_size:
                raise BackupIntegrityError("备份清单中的文件大小与备份文件不一致，拒绝恢复。")
            if expected_sha256 != backup_sha256:
                raise BackupIntegrityError("备份清单中的 SHA-256 与备份文件不一致，拒绝恢复。")
            if expected_integrity != "ok":
                raise BackupIntegrityError("备份清单未记录完整性校验通过，拒绝恢复。")
            verified_manifest = manifest
        self.paths.ensure_directories()
        db_path = self.paths.boundary.require_v2_target(self.paths.db_path)
        with MigrationLock(self.paths.migration_lock_path):
            target = sqlite3.connect(str(db_path), timeout=BUSY_TIMEOUT_MS / 1000)
            try:
                source = sqlite3.connect(str(backup_path))
                try:
                    source.backup(target)
                finally:
                    source.close()
            finally:
                target.close()
            for stale in (Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
                stale.unlink(missing_ok=True)
        self._integrity_check(db_path)
        restored_revision = self.read_revision(db_path)
        if verified_manifest is not None:
            return BackupRecord(
                path=backup_path,
                manifest_path=manifest_path,
                created_at_utc=str(verified_manifest["created_at_utc"]),
                source_revision=str(verified_manifest["source_revision"]),
                size_bytes=int(verified_manifest["size_bytes"]),
                sha256=backup_sha256,
                integrity=str(verified_manifest["integrity"]),
            )
        return BackupRecord(
            path=backup_path,
            manifest_path=manifest_path,
            created_at_utc="",
            source_revision=restored_revision,
            size_bytes=backup_path.stat().st_size,
            sha256=backup_sha256,
            integrity="ok",
        )

    # ------------------------------------------------------------------ 验证

    def verify(self) -> list[str]:
        """对当前数据库运行启动级验证，返回问题清单（空表示通过）。"""
        if not self.paths.db_path.exists():
            return ["数据库文件不存在，尚未初始化"]
        engine = build_engine(self.paths.db_path)
        try:
            try:
                check_engine_pragmas(engine)
            except Exception as exc:  # PragmaError 等
                return [str(exc)]
            problems = verify_schema_matches_metadata(engine, self.metadata)
            try:
                self._verify_basic_read_write(engine, require_revision=True)
            except Exception as exc:  # MigrationFailure
                problems.append(f"基础读写验证失败：{exc}")
            return problems
        finally:
            engine.dispose()

    def _verify_migrated_database(self, *, require_revision: bool, check_metadata: bool) -> None:
        engine = build_engine(self.paths.db_path)
        try:
            check_engine_pragmas(engine)
            if check_metadata:
                problems = verify_schema_matches_metadata(engine, self.metadata)
                if problems:
                    raise MigrationFailure(
                        "迁移后 schema 与 ORM metadata 不一致：" + "；".join(problems)
                    )
            self._verify_basic_read_write(engine, require_revision=require_revision)
        finally:
            engine.dispose()

    @staticmethod
    def _verify_basic_read_write(engine: Engine, *, require_revision: bool) -> None:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TEMP TABLE v2_startup_verify (value TEXT NOT NULL)"
            )
            connection.exec_driver_sql(
                "INSERT INTO v2_startup_verify (value) VALUES ('ok')"
            )
            value = connection.exec_driver_sql(
                "SELECT value FROM v2_startup_verify"
            ).scalar_one()
            if value != "ok":
                raise MigrationFailure("迁移后基础读写验证失败：写入与读回不一致。")
            if require_revision:
                rows = connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalars().all()
                if len(rows) != 1:
                    raise MigrationFailure(
                        "迁移后 alembic_version 异常，V2 写服务不会启动。"
                    )

    # ------------------------------------------------------------------ 工具

    def _alembic_config(self) -> alembic.config.Config:
        script_location = self.script_location or DEFAULT_SCRIPT_LOCATION
        if self.alembic_ini_path.exists():
            config = alembic.config.Config(str(self.alembic_ini_path))
        else:
            config = alembic.config.Config()
        config.set_main_option("sqlalchemy.url", f"sqlite:///{self.paths.db_path}")
        config.set_main_option("script_location", str(script_location))
        return config

    def _resolve_target_revision(self, revision: str) -> str:
        script = ScriptDirectory.from_config(self._alembic_config())
        if revision == "head":
            heads = script.get_heads()
            if len(heads) != 1:
                raise MigrationFailure(
                    "迁移脚本存在多个 head，无法确定唯一目标版本，V2 写服务不会启动。"
                )
            return str(heads[0])
        resolved = script.get_revision(revision)
        if resolved is None:
            raise MigrationFailure(f"找不到目标数据库版本 {revision}，V2 写服务不会启动。")
        return str(resolved.revision)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _integrity_check(db_path: Path) -> str:
        try:
            connection = sqlite3.connect(str(db_path))
        except sqlite3.Error as exc:
            raise BackupIntegrityError(f"无法打开备份或数据库文件 {db_path}：{exc}") from exc
        try:
            try:
                row = connection.execute("PRAGMA integrity_check").fetchone()
            except sqlite3.Error as exc:
                raise BackupIntegrityError(
                    f"完整性校验失败：{db_path} -> {exc}"
                ) from exc
        finally:
            connection.close()
        result = row[0] if row else ""
        if result != "ok":
            raise BackupIntegrityError(f"完整性校验失败：{db_path} -> {result}。")
        return "ok"

    def _write_manifest(self, record: BackupRecord) -> None:
        payload = json.dumps(
            {
                "backup_file": record.path.name,
                "created_at_utc": record.created_at_utc,
                "source_revision": record.source_revision,
                "size_bytes": record.size_bytes,
                "sha256": record.sha256,
                "integrity": record.integrity,
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        self.paths.boundary.atomic_write_bytes(record.manifest_path, payload)


def upgrade_or_fail(
    paths: DataPaths | None = None,
    *,
    metadata: MetaData | None = None,
    script_location: Path | None = None,
) -> tuple[DataPaths, Engine, sessionmaker[Session]]:
    """V2 写服务启动入口：迁移到 head 并返回验证过的 Engine/Session 工厂。

    任何一步失败都会抛出异常并中止启动，绝不返回未验证的连接。
    """
    verify_sqlite_runtime()
    paths = paths or resolve_data_paths()
    manager = MigrationManager(paths, metadata=metadata, script_location=script_location)
    manager.upgrade("head")
    engine = build_engine(paths.db_path)
    try:
        return paths, engine, build_session_factory(engine)
    except Exception:
        engine.dispose()
        raise


def _normalize_type(type_name: str) -> str:
    return "".join(type_name.split()).upper()


def verify_schema_matches_metadata(engine: Engine, metadata: MetaData) -> list[str]:
    """对比实际 schema 与 ORM metadata，返回差异清单（空表示一致）。"""
    problems: list[str] = []
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())
    expected_tables = set(metadata.tables)
    for table_name in sorted(expected_tables - actual_tables):
        problems.append(f"缺少表 {table_name}")
    for table_name in sorted(actual_tables - expected_tables):
        if table_name != "alembic_version":
            problems.append(f"存在未映射的表 {table_name}")
    for table_name in sorted(expected_tables & actual_tables):
        table = metadata.tables[table_name]
        problems.extend(_verify_table_columns(engine, inspector, table))
        problems.extend(_verify_table_constraints(inspector, table))
    return problems


def _verify_table_columns(engine: Engine, inspector: Any, table: Any) -> list[str]:
    problems: list[str] = []
    reflected = {column["name"]: column for column in inspector.get_columns(table.name)}
    for column in table.columns:
        if column.name not in reflected:
            problems.append(f"表 {table.name} 缺少列 {column.name}")
            continue
        info = reflected[column.name]
        expected_type = _normalize_type(str(column.type.compile(engine.dialect)))
        actual_type = _normalize_type(str(info["type"]))
        if expected_type and actual_type != expected_type:
            problems.append(
                f"表 {table.name} 列 {column.name} 类型不一致："
                f"metadata={expected_type}，schema={actual_type}"
            )
        if bool(info["nullable"]) != bool(column.nullable):
            problems.append(
                f"表 {table.name} 列 {column.name} 可空性不一致："
                f"metadata={column.nullable}，schema={bool(info['nullable'])}"
            )
    for name in reflected:
        if name not in table.c:
            problems.append(f"表 {table.name} 存在未映射列 {name}")
    return problems


def _verify_table_constraints(inspector: Any, table: Any) -> list[str]:
    problems: list[str] = []

    reflected_pk = set(inspector.get_pk_constraint(table.name).get("constrained_columns") or [])
    expected_pk = {column.name for column in table.primary_key.columns}
    if reflected_pk != expected_pk:
        problems.append(
            f"表 {table.name} 主键不一致：metadata={sorted(expected_pk)}，"
            f"schema={sorted(reflected_pk)}"
        )

    expected_uniques = {
        frozenset(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    for column in table.columns:
        if column.unique:
            expected_uniques.add(frozenset((column.name,)))
    reflected_uniques = {
        frozenset(item.get("column_names") or [])
        for item in inspector.get_unique_constraints(table.name)
    }
    if reflected_uniques != expected_uniques:
        problems.append(
            f"表 {table.name} 唯一约束不一致：metadata={sorted(map(sorted, expected_uniques))}，"
            f"schema={sorted(map(sorted, reflected_uniques))}"
        )

    expected_fks = {
        (constraint.referred_table.name, tuple(constraint.column_keys),
         tuple(element.column.name for element in constraint.elements))
        for constraint in table.foreign_key_constraints
    }
    reflected_fks = {
        (item["referred_table"], tuple(item["constrained_columns"]),
         tuple(item["referred_columns"]))
        for item in inspector.get_foreign_keys(table.name)
    }
    if reflected_fks != expected_fks:
        problems.append(f"表 {table.name} 外键不一致：metadata={sorted(expected_fks)}，schema={sorted(reflected_fks)}")

    expected_indexes = {
        index.name: tuple(index.columns.keys())
        for index in table.indexes
        if index.name is not None
    }
    reflected_indexes = {
        item["name"]: tuple(item.get("column_names") or [])
        for item in inspector.get_indexes(table.name)
    }
    if reflected_indexes != expected_indexes:
        problems.append(
            f"表 {table.name} 索引不一致：metadata={sorted(expected_indexes)}，"
            f"schema={sorted(reflected_indexes)}"
        )
    return problems
