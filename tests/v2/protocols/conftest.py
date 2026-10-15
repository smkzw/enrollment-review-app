"""tests/v2/protocols 共享夹具。"""
from __future__ import annotations

import pytest

from tests.v2.protocols.slice4_helpers import NOW


@pytest.fixture
def slice4_env(migrated_engine, session_factory):
    """迁移到 head 的临时库：返回 (session_factory, now)。"""
    return session_factory, NOW
