"""Open an existing compatible store without migrations or job recovery."""
from __future__ import annotations

import sqlite3

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.engine import Engine

from app.storage.config import DataPaths, resolve_data_paths
from app.storage.db import BUSY_TIMEOUT_MS, Base, build_session_factory
from app.storage.migrate import resolve_head_revision, verify_schema_matches_metadata
from app.storage import models as _models  # Register the current mapped schema.


def open_read_only(
    paths: DataPaths | None = None,
) -> tuple[DataPaths, Engine, sessionmaker[Session]]:
    paths = paths or resolve_data_paths()
    if not paths.db_path.is_file():
        raise RuntimeError("尚无已保存的资料，无法以仅查看方式打开；请先正常启动系统。")

    def connect():
        connection = sqlite3.connect(
            paths.db_path.resolve().as_uri() + "?mode=ro", uri=True,
            check_same_thread=False, timeout=BUSY_TIMEOUT_MS / 1000,
        )
        try:
            connection.execute("PRAGMA query_only = ON")
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        except BaseException:
            connection.close()
            raise

    engine = create_engine("sqlite://", creator=connect)
    try:
        with engine.connect() as connection:
            revisions = connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalars().all()
        if revisions != [resolve_head_revision()]:
            raise RuntimeError("现有资料版本与程序不一致；仅查看方式不会升级资料，请先完成正常启动。")
        if verify_schema_matches_metadata(engine, Base.metadata):
            raise RuntimeError("现有资料结构与程序不一致，不能读取；系统没有修改原资料。")
        return paths, engine, build_session_factory(engine)
    except BaseException:
        engine.dispose()
        raise
