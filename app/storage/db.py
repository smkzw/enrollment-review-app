"""SQLAlchemy 基础设施：声明基类、命名约定、Engine/Session 工厂与连接 PRAGMA 合同。

每个连接的运行时合同（设置并验证）::

    PRAGMA foreign_keys = ON
    PRAGMA journal_mode = WAL
    PRAGMA synchronous  = FULL
    PRAGMA busy_timeout = 10000

SQLite 只有一个写者，所有写事务必须短小；应用服务在最外层持有
``with session.begin()``。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.storage.config import verify_sqlite_runtime

logger = logging.getLogger(__name__)

BUSY_TIMEOUT_MS = 10_000

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}

# PRAGMA 名 -> 期望的运行时值（PRAGMA 查询返回的形态）
EXPECTED_PRAGMAS: dict[str, Any] = {
    "foreign_keys": 1,
    "journal_mode": "wal",
    "synchronous": 2,  # 2 == FULL
    "busy_timeout": BUSY_TIMEOUT_MS,
}

_PRAGMA_STATEMENTS = (
    "PRAGMA foreign_keys = ON",
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = FULL",
    f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}",
)


class PragmaError(RuntimeError):
    """连接 PRAGMA 合同未满足时抛出，阻止以不安全连接继续服务。"""


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def apply_connection_pragmas(dbapi_connection: Any, connection_record: Any = None) -> None:
    """连接建立时设置 PRAGMA 合同并立即验证。"""
    cursor = dbapi_connection.cursor()
    try:
        for statement in _PRAGMA_STATEMENTS:
            cursor.execute(statement)
    finally:
        cursor.close()
    verify_connection_pragmas(dbapi_connection)


# Backward-compatible private alias for the focused tests and any existing imports.
_apply_connection_pragmas = apply_connection_pragmas


def read_connection_pragmas(dbapi_connection: Any) -> dict[str, Any]:
    """读取连接的当前 PRAGMA 运行时值。"""
    cursor = dbapi_connection.cursor()
    try:
        values: dict[str, Any] = {}
        for name in EXPECTED_PRAGMAS:
            cursor.execute(f"PRAGMA {name}")
            values[name] = cursor.fetchone()[0]
        return values
    finally:
        cursor.close()


def verify_connection_pragmas(dbapi_connection: Any) -> None:
    """验证连接 PRAGMA 合同，不满足时抛出中文错误。"""
    values = read_connection_pragmas(dbapi_connection)
    problems = [
        f"{name} 期望 {expected}，实际 {values.get(name)}"
        for name, expected in EXPECTED_PRAGMAS.items()
        if values.get(name) != expected
    ]
    if problems:
        raise PragmaError(
            "SQLite 连接未满足 V2 持久化安全基线：" + "；".join(problems) + "。"
        )


def check_engine_pragmas(engine: Engine) -> dict[str, Any]:
    """通过一条真实连接验证 Engine 的 PRAGMA 合同，返回实测值。"""
    with engine.connect() as connection:
        return read_connection_pragmas(connection.connection.driver_connection)


def build_engine(db_path: Path, *, echo: bool = False) -> Engine:
    """构造经过运行时版本门禁和 PRAGMA 合同保护的 SQLAlchemy Engine。"""
    verify_sqlite_runtime()
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=echo,
        connect_args={
            "check_same_thread": False,
            "timeout": BUSY_TIMEOUT_MS / 1000.0,
        },
    )
    event.listen(engine, "connect", apply_connection_pragmas)
    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@dataclass(frozen=True)
class WalHealth:
    """WAL 观测信息；本阶段保留默认自动 checkpoint，只观测不调度。"""

    journal_mode: str
    wal_size_bytes: int | None
    checkpoint_pages: int | None
    checkpoint_busy: int | None
    checkpoint_log: int | None


def wal_health(engine: Engine) -> WalHealth:
    """观测 WAL 大小并执行一次 passive checkpoint（不改变调度策略）。"""
    with engine.connect() as connection:
        mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()
        busy, log, checkpointed = connection.exec_driver_sql(
            "PRAGMA wal_checkpoint(PASSIVE)"
        ).one()
    wal_path = _wal_file(engine)
    wal_size = wal_path.stat().st_size if wal_path.exists() else 0
    return WalHealth(
        journal_mode=str(mode),
        wal_size_bytes=wal_size,
        checkpoint_pages=int(checkpointed),
        checkpoint_busy=int(busy),
        checkpoint_log=int(log),
    )


def _wal_file(engine: Engine) -> Path:
    database = Path(str(engine.url.database))
    return database.with_name(database.name + "-wal")
