from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import Column, DateTime, MetaData, String, Table

from app.storage.db import Base, build_engine, check_engine_pragmas
from app.storage.migrate import (
    BackupIntegrityError,
    MigrationFailure,
    MigrationManager,
    upgrade_or_fail,
    verify_schema_matches_metadata,
)

from .conftest import REPO_ROOT

TEMP_ENV_PY = '''\
from alembic import context
from sqlalchemy import engine_from_config, pool

from app.storage.db import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
'''

DEMO_0001 = '''\
"""demo 基线

Revision ID: demo01
Revises:
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "demo01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "demo_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("value", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("demo_items")
'''

BOOM_0002 = '''\
"""模拟迁移中途失败

Revision ID: demo02
Revises: demo01
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op

revision: str = "demo02"
down_revision: Union[str, None] = "demo01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("SELECT this_sql_fails")


def downgrade() -> None:
    pass
'''

MISMATCH_0002 = '''\
"""模拟迁移成功但结构校验失败

Revision ID: demo02
Revises: demo01
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "demo02"
down_revision: Union[str, None] = "demo01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unexpected_table",
        sa.Column("id", sa.Integer(), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("unexpected_table")
'''

BROKEN_0001 = '''\
"""模拟首次迁移中途失败

Revision ID: broken01
Revises:
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op

revision: str = "broken01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TABLE partial_item (id INTEGER PRIMARY KEY)")
    op.execute("SELECT this_sql_fails")


def downgrade() -> None:
    pass
'''


def _demo_metadata() -> MetaData:
    metadata = MetaData()
    Table(
        "demo_items",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("value", String(255), nullable=False),
        Column("created_at", DateTime(), nullable=False),
    )
    return metadata


def write_temp_migrations(tmp_path: Path) -> Path:
    location = tmp_path / "migrations"
    (location / "versions").mkdir(parents=True)
    (location / "env.py").write_text(TEMP_ENV_PY, encoding="utf-8")
    (location / "versions" / "demo01_create.py").write_text(DEMO_0001, encoding="utf-8")
    return location


# ---------------------------------------------------------------- 基线迁移


def test_empty_database_upgrade_downgrade_upgrade_cycle(data_paths):
    manager = MigrationManager(data_paths)

    first = manager.upgrade("head")
    assert first.from_revision == "base"
    assert first.to_revision == "0003"
    assert first.backup is None  # 空库首次初始化无备份

    engine = build_engine(data_paths.db_path)
    assert manager.verify() == []
    engine.dispose()

    manager.downgrade("base")
    assert manager.read_revision(data_paths.db_path) == "base"

    second = manager.upgrade("head")
    assert second.from_revision == "base"
    assert second.to_revision == "0003"
    assert second.backup is not None
    assert second.backup.source_revision == "base"
    assert second.backup.integrity == "ok"

    manifest = json.loads(second.backup.manifest_path.read_text(encoding="utf-8"))
    assert manifest["sha256"] == second.backup.sha256
    assert manifest["size_bytes"] == second.backup.path.stat().st_size
    assert manifest["source_revision"] == "base"

    engine = build_engine(data_paths.db_path)
    try:
        assert verify_schema_matches_metadata(engine, Base.metadata) == []
    finally:
        engine.dispose()


def test_upgraded_database_connection_contract(data_paths):
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        pragmas = check_engine_pragmas(engine)
        assert pragmas["foreign_keys"] == 1
        assert pragmas["journal_mode"] == "wal"
        assert pragmas["synchronous"] == 2
        assert pragmas["busy_timeout"] == 10000
    finally:
        engine.dispose()


def test_noop_upgrade_verifies_without_creating_redundant_backup(data_paths):
    manager = MigrationManager(data_paths)
    first = manager.upgrade("head")
    assert first.to_revision == "0003"
    before = sorted(data_paths.backups_dir.glob("*.sqlite3"))

    second = manager.upgrade("head")

    assert second.from_revision == "0003"
    assert second.to_revision == "0003"
    assert second.backup is None
    assert sorted(data_paths.backups_dir.glob("*.sqlite3")) == before


# ---------------------------------------------------------------- 失败注入


def test_failed_migration_preserves_original_database_and_backup(data_paths, tmp_path):
    location = write_temp_migrations(tmp_path)
    (location / "versions" / "demo02_boom.py").write_text(BOOM_0002, encoding="utf-8")
    manager = MigrationManager(
        data_paths, script_location=location, metadata=_demo_metadata()
    )

    first = manager.upgrade("demo01")
    assert first.to_revision == "demo01"
    assert first.backup is None  # 空库初始化

    engine = build_engine(data_paths.db_path)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO demo_items (id, value, created_at) "
            "VALUES ('a', 'x', '2026-08-14T00:00:00Z')"
        )
    engine.dispose()

    # 迁移中途失败：必须中止且原库保持 demo01 与既有数据
    with pytest.raises(MigrationFailure):
        manager.upgrade("head")
    assert manager.read_revision(data_paths.db_path) == "demo01"
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            value = connection.exec_driver_sql(
                "SELECT value FROM demo_items WHERE id = 'a'"
            ).scalar_one()
            assert value == "x"
    finally:
        engine.dispose()

    # 失败前的一致备份存在且通过完整性校验，清单完整
    backups = sorted(data_paths.backups_dir.glob("*.sqlite3"))
    assert len(backups) == 1
    manifest = json.loads(Path(f"{backups[0]}.json").read_text(encoding="utf-8"))
    assert manifest["integrity"] == "ok"
    assert manifest["source_revision"] == "demo01"
    assert manifest["sha256"]

    # 写服务启动入口不得成功
    with pytest.raises(MigrationFailure):
        upgrade_or_fail(
            data_paths, metadata=_demo_metadata(), script_location=location
        )


def test_failed_first_migration_removes_partial_database(data_paths, tmp_path):
    """首次迁移没有旧库可备份时，失败后应恢复为“数据库不存在”。"""
    location = tmp_path / "broken-migrations"
    (location / "versions").mkdir(parents=True)
    (location / "env.py").write_text(TEMP_ENV_PY, encoding="utf-8")
    (location / "versions" / "broken01.py").write_text(
        BROKEN_0001, encoding="utf-8"
    )
    manager = MigrationManager(data_paths, script_location=location)

    with pytest.raises(MigrationFailure, match="已清除未完成的数据库"):
        manager.upgrade("head")

    assert not data_paths.db_path.exists()
    assert not Path(f"{data_paths.db_path}-wal").exists()
    assert not Path(f"{data_paths.db_path}-shm").exists()


def test_post_migration_verification_failure_restores_backup(data_paths, tmp_path):
    """DDL 已提交但 metadata 校验失败时，也自动恢复迁移前数据库。"""
    location = write_temp_migrations(tmp_path)
    manager = MigrationManager(
        data_paths, script_location=location, metadata=_demo_metadata()
    )
    manager.upgrade("demo01")
    engine = build_engine(data_paths.db_path)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO demo_items (id, value, created_at) "
            "VALUES ('kept', 'before', '2026-08-14T00:00:00Z')"
        )
    engine.dispose()

    (location / "versions" / "demo02_mismatch.py").write_text(
        MISMATCH_0002, encoding="utf-8"
    )
    with pytest.raises(MigrationFailure, match="已自动恢复"):
        manager.upgrade("head")

    assert manager.read_revision(data_paths.db_path) == "demo01"
    connection = sqlite3.connect(data_paths.db_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "unexpected_table" not in tables
        assert connection.execute(
            "SELECT value FROM demo_items WHERE id = 'kept'"
        ).fetchone()[0] == "before"
    finally:
        connection.close()


# ------------------------------------------------------------------ 恢复


def test_restore_recovers_revision_and_data(data_paths, tmp_path):
    location = write_temp_migrations(tmp_path)
    manager = MigrationManager(
        data_paths, script_location=location, metadata=_demo_metadata()
    )
    manager.upgrade("demo01")

    engine = build_engine(data_paths.db_path)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO demo_items (id, value, created_at) "
            "VALUES ('a', 'x', '2026-08-14T00:00:00Z')"
        )
    engine.dispose()

    backup = manager.create_backup()
    assert backup is not None
    assert backup.source_revision == "demo01"

    # 破坏主库：降级到空基线
    manager.downgrade("base")
    assert manager.read_revision(data_paths.db_path) == "base"

    record = manager.restore(backup.path)
    assert record.source_revision == "demo01"
    assert manager.read_revision(data_paths.db_path) == "demo01"

    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            value = connection.exec_driver_sql(
                "SELECT value FROM demo_items WHERE id = 'a'"
            ).scalar_one()
            assert value == "x"
    finally:
        engine.dispose()


def test_restore_rejects_corrupt_backup_without_touching_live_database(data_paths):
    manager = MigrationManager(data_paths)
    bogus = data_paths.backups_dir / "bogus.sqlite3"
    bogus.write_bytes(b"not a sqlite database")
    with pytest.raises(BackupIntegrityError):
        manager.restore(bogus)
    assert not data_paths.db_path.exists()


def test_restore_rejects_manifest_mismatch_before_touching_live_database(data_paths):
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    live_before = data_paths.db_path.read_bytes()
    backup = manager.create_backup()
    assert backup is not None

    manifest = json.loads(backup.manifest_path.read_text(encoding="utf-8"))
    manifest["sha256"] = "0" * 64
    backup.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(BackupIntegrityError):
        manager.restore(backup.path)
    assert data_paths.db_path.read_bytes() == live_before


def test_restore_rejects_missing_backup(data_paths):
    manager = MigrationManager(data_paths)
    with pytest.raises(MigrationFailure):
        manager.restore(data_paths.backups_dir / "missing.sqlite3")


# ---------------------------------------------------------------- 迁移锁


def test_migration_lock_rejects_concurrent_holder(data_paths):
    from app.storage.migrate import MigrationLock, MigrationLockHeld

    with MigrationLock(data_paths.migration_lock_path):
        with pytest.raises(MigrationLockHeld):
            MigrationLock(data_paths.migration_lock_path).acquire()


# -------------------------------------------------------- schema 一致性检查


def test_verify_schema_matches_metadata_detects_drift(data_paths):
    engine = build_engine(data_paths.db_path)
    try:
        metadata = MetaData()
        Table(
            "demo_items",
            metadata,
            Column("id", String(36), primary_key=True),
            Column("value", String(255), nullable=False),
        )
        metadata.create_all(engine)

        matching = verify_schema_matches_metadata(engine, metadata)
        assert matching == []

        drifted = MetaData()
        Table(
            "demo_items",
            drifted,
            Column("id", String(36), primary_key=True),
            Column("value", String(255), nullable=False),
            Column("extra", String(64), nullable=True),
        )
        problems = verify_schema_matches_metadata(engine, drifted)
        assert any("extra" in problem for problem in problems)
        assert any("缺少列" in problem for problem in problems)
    finally:
        engine.dispose()
