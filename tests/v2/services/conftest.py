"""Slice 4.4 服务测试共享夹具。

从 WP-44A 仓储测试模块复用 ``seeded`` / ``artifact_store`` / ``revision_stack``
夹具。这些名字只用于 pytest fixture 依赖解析，不在此处作为值使用，因此以
``# noqa: F401`` 抑制 Ruff 未使用导入告警。
"""
from tests.v2.storage.test_slice44_repositories import (  # noqa: F401
    artifact_store,
    revision_stack,
    seeded,
)
