"""tests/v2 共享夹具：临时 V2 数据根 + 迁移到 head 的真实文件数据库。

``tests/v2/storage/conftest.py`` 为 storage 子目录提供同名夹具（行为一致，
就近覆盖本文件），其余子目录（workflow/api）使用这里的定义。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.storage.config import DataPaths, resolve_data_paths
from app.storage.db import build_engine
from app.storage.migrate import MigrationManager

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def data_paths(tmp_path, monkeypatch) -> DataPaths:
    """指向临时目录的 V2 数据路径布局。"""
    monkeypatch.setenv("ENROLLMENT_V2_DATA_DIR", str(tmp_path / "data_v2"))
    paths = resolve_data_paths()
    paths.ensure_directories()
    return paths


@pytest.fixture
def engine(data_paths):
    engine = build_engine(data_paths.db_path)
    yield engine
    engine.dispose()


@pytest.fixture
def migrated_engine(data_paths):
    """迁移到 head 的临时库 Engine。"""
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(migrated_engine):
    from app.storage.db import build_session_factory

    return build_session_factory(migrated_engine)


@pytest.fixture
def session(session_factory):
    """单测试事务会话：测试结束时回滚，不污染临时库。"""
    with session_factory() as current:
        yield current
        current.rollback()
