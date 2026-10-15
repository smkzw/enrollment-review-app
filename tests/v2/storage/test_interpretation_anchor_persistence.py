"""解释来源锚点解析的持久化往返与旧记录兼容测试（词汇中立）。

覆盖：
- ``InterpretationSource`` 携带锚点解析时经 ``payload_json`` 完整往返，
  镜像列不感知新字段；
- 旧记录缺少锚点解析字段时按空列表读取；
- 解释冲突记录追加写与读取。
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.contracts.enums import (
    AnchorResolutionMode,
    InterpretationConflictStatus,
    InterpretationSourceType,
    ReviewStage,
)
from app.domain.contracts.common import DateValue
from app.domain.contracts.protocol_metadata import (
    AnchorResolutionStatement,
    InterpretationConflict,
    InterpretationSource,
)
from app.storage.models import ProtocolDocumentVersionRecord
from app.storage.repositories import (
    list_interpretation_conflicts,
    list_interpretation_sources,
    save_interpretation_conflict,
    save_interpretation_source,
)


_NOW = datetime(2026, 9, 1, 12, 0, 0)


@pytest.fixture
def protocol_version(session):
    """最小方案版本父记录，满足解释来源外键。"""

    session.add(
        ProtocolDocumentVersionRecord(
            protocol_version_id="protocol-v1",
            protocol_code="SYN-001",
            official_version="V1.0",
            official_date_value=_NOW,
            official_date_precision="day",
            sha256="c" * 64,
            integrity_manifest_sha256="d" * 64,
            authority_record_sha256="e" * 64,
            authority_confirmation_id="authority-confirmed",
            authority_gate_result_id="authority-gate",
            integrity_gate_result_id="integrity-gate",
            payload_json="{}",
            payload_sha256="0" * 64,
            created_at=_NOW,
        )
    )
    session.flush()
    return "protocol-v1"


def _resolution() -> AnchorResolutionStatement:
    return AnchorResolutionStatement(
        resolution_id="res-1",
        affected_rule_refs=["EX-01"],
        ambiguous_source_refs=["span-ex"],
        target_review_stages=[ReviewStage.SCREENING, ReviewStage.BASELINE],
        resolution_mode=AnchorResolutionMode.CURRENT_REVIEW_NODE_DATE,
    )


def _source(protocol_version_id: str) -> InterpretationSource:
    return InterpretationSource(
        interpretation_source_id="interp-1",
        protocol_version_id=protocol_version_id,
        source_type=InterpretationSourceType.QA,
        file_sha256="b" * 64,
        source_version="V1",
        source_date=DateValue(value=_NOW.date(), precision="day"),
        source_ref="qa-ref-1",
        excerpt="问：既往2个月内的疾病史从哪一天起算？",
        explanation="未命名回溯锚点按当前审核节点日期计算，逐节点独立评判。",
        applies_to_rule_refs=["EX-01"],
        clarifies_ambiguity=True,
        anchor_resolutions=[_resolution()],
    )


def test_interpretation_source_round_trips_anchor_resolutions(session, protocol_version):
    source = _source(protocol_version)
    saved = save_interpretation_source(session, source)
    assert saved.interpretation_source_id == "interp-1"

    loaded = list_interpretation_sources(session, protocol_version)
    assert len(loaded) == 1
    restored = loaded[0]
    assert restored.authority.value == "clarification_only"
    assert len(restored.anchor_resolutions) == 1
    resolution = restored.anchor_resolutions[0]
    assert resolution == _resolution()


def test_legacy_row_without_anchor_field_reads_as_empty_list(session, protocol_version):
    """旧形状解释来源（payload_json 无 anchor_resolutions 字段）按空列表读取。"""

    legacy = InterpretationSource(
        interpretation_source_id="interp-legacy",
        protocol_version_id=protocol_version,
        source_type=InterpretationSourceType.MEDICAL_INTERPRETATION,
        file_sha256="b" * 64,
        source_ref="note-ref-1",
        excerpt="医学意见摘录",
        explanation="既往历史条件在正式条款中未命名锚点，待正式修订。",
        applies_to_rule_refs=["EX-01"],
        clarifies_ambiguity=True,
    )
    assert legacy.anchor_resolutions == []
    save_interpretation_source(session, legacy)
    loaded = list_interpretation_sources(session, protocol_version)
    by_id = {item.interpretation_source_id: item for item in loaded}
    assert by_id["interp-legacy"].anchor_resolutions == []


def test_interpretation_conflict_round_trip(session, protocol_version):
    save_interpretation_source(session, _source(protocol_version))
    conflict = InterpretationConflict(
        conflict_id="conflict-1",
        protocol_version_id=protocol_version,
        interpretation_source_id="interp-1",
        affected_rule_refs=["EX-01"],
        protocol_source_refs=["span-ex"],
        reason="解释与方案正式条款冲突",
        impact="相关条款停在需要核对状态",
        status=InterpretationConflictStatus.OPEN,
        blocks_publication=True,
    )
    save_interpretation_conflict(session, conflict)
    loaded = list_interpretation_conflicts(session, protocol_version)
    assert [item.conflict_id for item in loaded] == ["conflict-1"]
    assert loaded[0].blocks_publication is True
