from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import Column, ForeignKey, MetaData, String, Table, text
from sqlalchemy.exc import IntegrityError

from app.storage.config import SQLiteRuntimeTooOld
from app.storage.db import (
    EXPECTED_PRAGMAS,
    BUSY_TIMEOUT_MS,
    PragmaError,
    _apply_connection_pragmas,
    build_engine,
    build_session_factory,
    check_engine_pragmas,
    verify_connection_pragmas,
    wal_health,
)


def _fk_metadata() -> MetaData:
    metadata = MetaData()
    Table(
        "test_parents",
        metadata,
        Column("id", String(36), primary_key=True),
    )
    Table(
        "test_children",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("parent_id", String(36), ForeignKey("test_parents.id"), nullable=False),
    )
    return metadata


def test_engine_connection_pragmas_enforced(engine):
    pragmas = check_engine_pragmas(engine)
    assert pragmas == EXPECTED_PRAGMAS
    assert pragmas["foreign_keys"] == 1
    assert pragmas["journal_mode"] == "wal"
    assert pragmas["synchronous"] == 2  # FULL
    assert pragmas["busy_timeout"] == BUSY_TIMEOUT_MS


def test_wal_mode_persists_and_recovers_across_connections(data_paths):
    engine = build_engine(data_paths.db_path)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    engine.dispose()

    raw = sqlite3.connect(str(data_paths.db_path))
    try:
        assert raw.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        raw.close()

    # 手动破坏为 DELETE 后，重建 Engine 应恢复 WAL 合同
    raw = sqlite3.connect(str(data_paths.db_path))
    try:
        assert raw.execute("PRAGMA journal_mode = DELETE").fetchone()[0] == "delete"
    finally:
        raw.close()

    engine = build_engine(data_paths.db_path)
    assert check_engine_pragmas(engine)["journal_mode"] == "wal"
    engine.dispose()


def test_foreign_keys_actually_enforced(engine):
    metadata = _fk_metadata()
    metadata.create_all(engine)
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO test_children (id, parent_id) VALUES ('c1', 'missing')")
            )


def test_raw_connection_without_pragmas_does_not_enforce_fk(data_paths):
    engine = build_engine(data_paths.db_path)
    _fk_metadata().create_all(engine)
    engine.dispose()
    raw = sqlite3.connect(str(data_paths.db_path))
    try:
        # 默认连接 foreign_keys=OFF：孤儿行可插入，说明强制来自我们的 PRAGMA 合同
        raw.execute("INSERT INTO test_children (id, parent_id) VALUES ('c2', 'missing')")
        raw.commit()
        count = raw.execute("SELECT COUNT(*) FROM test_children").fetchone()[0]
        assert count == 1
    finally:
        raw.close()


def test_pragma_deviation_detected_on_raw_connection(tmp_path):
    connection = sqlite3.connect(str(tmp_path / "pragma.db"))
    try:
        _apply_connection_pragmas(connection, None)
        verify_connection_pragmas(connection)
        connection.execute("PRAGMA foreign_keys = OFF")
        with pytest.raises(PragmaError):
            verify_connection_pragmas(connection)
    finally:
        connection.close()


def test_build_engine_rejects_old_sqlite_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr("app.storage.config.sqlite3.sqlite_version_info", (3, 51, 2))
    with pytest.raises(SQLiteRuntimeTooOld):
        build_engine(tmp_path / "unused.sqlite3")


def test_session_factory_transactional_round_trip(engine):
    metadata = _fk_metadata()
    metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory() as session:
        with session.begin():
            session.execute(text("INSERT INTO test_parents (id) VALUES ('p1')"))
    with factory() as session:
        count = session.execute(text("SELECT COUNT(*) FROM test_parents")).scalar_one()
        assert count == 1


def test_wal_health_reports_mode_and_checkpoint(engine):
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        connection.exec_driver_sql("INSERT INTO t (v) VALUES ('x')")
    health = wal_health(engine)
    assert health.journal_mode == "wal"
    assert health.wal_size_bytes is not None and health.wal_size_bytes >= 0
    assert health.checkpoint_busy in (0, 1)
    assert health.checkpoint_log is not None
    assert health.checkpoint_pages is not None
