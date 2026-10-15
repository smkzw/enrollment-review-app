"""tests/v2/evidence 共享夹具：一次性生成确定性金标准。"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.evidence.goldset import GoldSet
from tests.v2.evidence.goldgen import build_gold_set


@pytest.fixture(scope="session")
def gold_root(tmp_path_factory) -> Path:
    """会话级金标准目录（每次测试会话重新生成，保证与源码同步）。"""
    root = tmp_path_factory.mktemp("goldset") / "gold"
    return root


@pytest.fixture(scope="session")
def gold_set(gold_root) -> GoldSet:
    return build_gold_set(gold_root)
