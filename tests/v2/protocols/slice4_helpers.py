"""切片 4 共享夹具：已确认身份的 Gate 测试草稿。"""
from __future__ import annotations

from datetime import datetime, timezone

from app.domain.contracts.enums import MetadataResolutionStatus

from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture

NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)
SHA = "a" * 64


def confirmed_fixture():
    """Gate 测试草稿 + 已确认身份/期别；返回 (source_input, draft, source_spans)。"""
    source_input, draft, source_spans = _fixture()
    source_input.identity_decision = source_input.identity_decision.model_copy(
        update={"status": MetadataResolutionStatus.CONFIRMED}
    )
    source_input.phase_selection = source_input.phase_selection.model_copy(
        update={"status": MetadataResolutionStatus.CONFIRMED}
    )
    return source_input, draft, source_spans
