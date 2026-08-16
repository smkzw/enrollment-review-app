"""Read-only identity/phase regression on the two real protocol fixtures."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from app.domain.contracts.enums import (
    ApplicabilityGranularity,
    PhaseScope,
    ProtocolMetadataField,
    StudyPhase,
)
from app.protocols.docx_structure import extract_docx_structure
from app.protocols.ingestion import register_source_artifact
from app.protocols.metadata import extract_protocol_metadata, resolve_protocol_identity
from app.protocols.phase_detection import build_phase_applicability_graph, project_single_phase


REAL_PROTOCOLS = [
    (
        "MG-K10-SAR",
        Path(
            "/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/"
            "MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx"
        ),
        "MG-K10-SAR-001",
        "V2.1",
        "2025-09-19",
        StudyPhase.PHASE_III,
    ),
    (
        "CMS-D001",
        Path(
            "/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/"
            "CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx"
        ),
        "D001-02-002",
        "1.0",
        "2025-12-10",
        StudyPhase.PHASE_II,
    ),
]


def _opposite_phase_marker(text: str, selected_phase: StudyPhase) -> bool:
    opposite = "Ⅲ" if selected_phase == StudyPhase.PHASE_II else "Ⅱ"
    alternate = "III" if selected_phase == StudyPhase.PHASE_II else "II"
    return bool(
        re.search(rf"(?:{opposite}|{alternate})\s*期", text, re.I)
    )


def _snapshot(path: Path) -> tuple[str, int, int, tuple[str, ...]]:
    stat = path.stat()
    return (
        hashlib.sha256(path.read_bytes()).hexdigest(),
        stat.st_size,
        stat.st_mtime_ns,
        tuple(sorted(item.name for item in path.parent.iterdir())),
    )


@pytest.mark.parametrize("label,path,expected_code,expected_version,expected_date,selected_phase", REAL_PROTOCOLS)
def test_real_protocol_metadata_phase_is_read_only(
    label,
    path: Path,
    expected_code: str,
    expected_version: str,
    expected_date: str,
    selected_phase: StudyPhase,
    tmp_path,
) -> None:
    if not path.is_file():
        pytest.skip(f"真实方案文件缺失：{path}")

    before = _snapshot(path)
    artifact = register_source_artifact(
        path,
        source_artifact_id=f"slice2-{label}",
        storage_root=tmp_path,
    )
    extraction = extract_docx_structure(
        path,
        snapshot_id=f"slice2-{label}-snapshot",
        source_artifact=artifact,
        output_dir=tmp_path,
    )
    metadata = extract_protocol_metadata(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
        file_name=path.name,
    )

    formal_code = [
        item
        for item in metadata.candidates
        if item.field_category == ProtocolMetadataField.PROTOCOL_CODE
        and not item.is_fallback
    ]
    formal_version = [
        item
        for item in metadata.candidates
        if item.field_category == ProtocolMetadataField.PROTOCOL_VERSION
        and not item.is_fallback
    ]
    formal_date = [
        item
        for item in metadata.candidates
        if item.field_category == ProtocolMetadataField.PROTOCOL_DATE
        and not item.is_fallback
    ]
    assert formal_code and {item.normalized_value for item in formal_code} == {expected_code}
    assert formal_version and {item.candidate_value for item in formal_version} == {expected_version}
    assert {item.normalized_value for item in formal_version} == {expected_version.lstrip("Vv")}
    assert formal_date and expected_date in {item.normalized_value for item in formal_date}

    decision = resolve_protocol_identity(
        metadata,
        identity_decision_id=f"slice2-{label}-identity",
        study_phase=selected_phase,
    )
    assert decision.protocol_code == expected_code
    assert decision.official_version == expected_version
    assert decision.official_date is not None
    assert not any(
        item.field_category in {
            ProtocolMetadataField.PROTOCOL_CODE,
            ProtocolMetadataField.PROTOCOL_VERSION,
            ProtocolMetadataField.PROTOCOL_DATE,
        }
        for item in metadata.conflicts
    ), f"{label} 正式身份字段不应因低优先级候选产生冲突"
    if label == "CMS-D001":
        assert {item.normalized_value for item in formal_code} == {"D001-02-002"}
        assert {
            item.candidate_value
            for item in metadata.candidates
            if item.field_category == ProtocolMetadataField.TEMPLATE_VERSION
        } == {"00"}
        assert {
            item.candidate_value
            for item in metadata.candidates
            if item.field_category == ProtocolMetadataField.PROTOCOL_VERSION
            and not item.is_fallback
        } == {"1.0"}
        assert {
            item.normalized_value
            for item in metadata.candidates
            if item.field_category == ProtocolMetadataField.PROTOCOL_VERSION
            and item.is_fallback
        } == {"1.0"}
        assert {
            item.normalized_value
            for item in metadata.candidates
            if item.field_category == ProtocolMetadataField.PROTOCOL_DATE
            and item.is_fallback
        } == {"2025-12-21"}
        assert not any(
            item.field_category == ProtocolMetadataField.PROTOCOL_CODE
            and item.is_fallback
            and item.conflict_group_id
            for item in metadata.candidates
        )
        assert decision.status.value == "confirmed"
        assert decision.confirmation_required is False
        assert decision.conflict_ids == []

    phase = build_phase_applicability_graph(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
    )
    assert phase.graph.blocks
    assert phase.graph.seamless_candidates == [], (
        f"{label} 的操作无缝/新受试者措辞不应生成同一受试者无缝候选"
    )
    projection = project_single_phase(phase.graph, selected_phase)
    assert projection.blocks
    graph_by_id = {item.block_id: item for item in phase.graph.blocks}
    selected_scope = (
        PhaseScope.PHASE_II
        if selected_phase == StudyPhase.PHASE_II
        else PhaseScope.PHASE_III
    )
    allowed_scopes = {(selected_scope,), (PhaseScope.SHARED,)}
    assert all(tuple(block.phase_scopes) in allowed_scopes for block in projection.blocks)
    assert any(tuple(block.phase_scopes) == (PhaseScope.SHARED,) for block in projection.blocks)
    assert all(
        not (
            block.is_aggregate
            and set(block.phase_scopes) & {PhaseScope.MIXED, PhaseScope.UNKNOWN}
        )
        for block in projection.blocks
    )
    assert all(
        block.text == graph_by_id[block.block_id].text for block in projection.blocks
    ), f"{label} 投影不得覆盖 graph 原始 source text"
    assert all(
        not _opposite_phase_marker(block.projection_text or block.text, selected_phase)
        for block in projection.blocks
    ), f"{label} {selected_phase.value} 派生投影仍含对侧期别污染"
    if label == "MG-K10-SAR":
        shared_exclusion = [
            block
            for block in phase.graph.blocks
            if not block.is_aggregate and "随机前4天内使用过抗组胺药物" in block.text
        ]
        assert shared_exclusion
        assert all(block.phase_scopes == [PhaseScope.SHARED] for block in shared_exclusion)
        projected_ids = {block.block_id for block in projection.blocks}
        assert all(block.block_id in projected_ids for block in shared_exclusion)
        flow_blocks = [
            block
            for block in projection.blocks
            if block.is_aggregate and block.source_ref.startswith("body.t3.c")
        ]
        assert len(flow_blocks) == 9
        assert all(block.phase_scopes == [PhaseScope.SHARED] for block in flow_blocks)
    if label == "CMS-D001":
        projected_refs = {
            block.source_ref for block in projection.blocks if block.is_aggregate
        }
        assert len([ref for ref in projected_refs if ref.startswith("body.t5.c")]) == 10
        assert not any(ref.startswith("body.t6.") for ref in projected_refs)
    for block in projection.blocks:
        if block.is_aggregate:
            child_ids = set(block.child_block_ids)
            assert child_ids
            assert child_ids <= set(graph_by_id)
            assert set(block.source_span_ids) <= {
                span_id
                for child_id in child_ids
                for span_id in graph_by_id[child_id].source_span_ids
            }

    after = _snapshot(path)
    assert after == before, "真实方案、源文件 mtime 或源目录未被元信息/期别提取改写"
