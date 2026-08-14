from __future__ import annotations

from pathlib import Path

import pytest

from app.storage.config import DataPaths, resolve_data_paths
from app.storage.db import build_engine
from app.storage.migrate import MigrationManager

REPO_ROOT = Path(__file__).resolve().parents[3]


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
def manager(data_paths) -> MigrationManager:
    return MigrationManager(data_paths)
