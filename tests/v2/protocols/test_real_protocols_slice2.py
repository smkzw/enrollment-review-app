"""Read-only identity/phase regression on the two real protocol fixtures."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.domain.contracts.enums import (
    ApplicabilityGranularity,
    PhaseScope,
    ProtocolMetadataField,
    StudyPhase,
)
from app.protocols.docx_structure import extract_docx_structure
from app.protocols.full_protocol_coverage import build_full_protocol_coverage_manifest
from app.protocols.ingestion import register_source_artifact
from app.protocols.metadata import extract_protocol_metadata, resolve_protocol_identity
from app.protocols.phase_applicability_planning import (
    PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
    PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY,
    plan_phase_applicability_batches,
)
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

LOCAL_D001_COPY = Path(
    "artifacts/phase5-acceptance/20260823/isolated-inputs/d001/protocol/"
    "test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx"
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


def test_local_d001_rebuild_quantifies_cross_heading_packing_and_preserves_table_5(tmp_path):
    """Rebuild the isolated D001 copy without mutating its source artifact."""
    path = LOCAL_D001_COPY.resolve()
    if not path.is_file():
        pytest.skip(f"工作区内 D001 只读副本缺失：{path}")

    before = _snapshot(path)
    artifact = register_source_artifact(
        path,
        source_artifact_id="slice58d-local-d001",
        storage_root=tmp_path,
    )
    extraction = extract_docx_structure(
        path,
        snapshot_id="slice58d-local-d001-snapshot",
        source_artifact=artifact,
        output_dir=tmp_path / "structure",
    )
    phase = build_phase_applicability_graph(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
    )
    phase_by_ref = {
        block.source_ref: block
        for block in phase.graph.blocks
        if not block.is_aggregate
    }
    # D001's III chapter contains ordinary references back to the II chapter.
    # Those references must remain III under the enclosing structural context;
    # an explicit II heading remains II.
    assert phase_by_ref["body.p839"].phase_scopes == [PhaseScope.PHASE_II]
    assert all(
        phase_by_ref[source_ref].phase_scopes == [PhaseScope.PHASE_III]
        for source_ref in ("body.p937", "body.p938", "body.p940", "body.p978")
    )
    assert all(
        phase_by_ref[source_ref].phase_scopes == [PhaseScope.PHASE_II]
        for source_ref in ("body.p314", "body.p315", "body.p341")
    )
    assert all(
        phase_by_ref[source_ref].phase_scopes == [PhaseScope.PHASE_III]
        for source_ref in ("body.p345", "body.p346", "body.p372")
    )
    assert phase_by_ref["body.t4.r4.c1.p9"].phase_scopes == [PhaseScope.PHASE_II]
    assert all(
        phase_by_ref[source_ref].phase_scopes == [PhaseScope.PHASE_III]
        for source_ref in (
            "body.t4.r4.c1.p20",
            "body.t4.r4.c1.p24",
            "body.t4.r4.c1.p28",
            "body.t4.r4.c1.p33",
            "body.p547",
            "body.p548",
            "body.p552",
            "body.p564",
        )
    )
    projection = project_single_phase(phase.graph, StudyPhase.PHASE_II)
    manifest = build_full_protocol_coverage_manifest(
        extraction.blocks,
        projection,
        phase.graph,
        protocol_version_id="D001-02-002:v1.0:phase-ii",
        protocol_document_sha256=before[0],
        snapshot_id=extraction.snapshot.snapshot_id,
        manifest_id="slice58d-local-d001-manifest",
        priority_keywords=(
            "入选",
            "排除",
            "筛选",
            "基线",
            "首次给药",
            "随机",
            "结核",
            "妊娠",
            "合并用药",
            "洗脱",
            "复测",
            "有效期",
        ),
    )
    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=12,
        context_radius=1,
        batch_packing_policy=PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
    )
    # The statistics hypothesis lead-in is III-phase content through the
    # nested "multiplicity adjustment" heading; the sibling sample-size
    # heading closes that inherited context before the II-phase branch.
    assert all(
        phase_by_ref[source_ref].phase_scopes == [PhaseScope.PHASE_III]
        for source_ref in (
            "body.p1172",
            "body.p1173",
            "body.p1174",
            "body.p1175",
            "body.p1176",
            "body.p1177",
            "body.p1178",
        )
    )
    assert phase_by_ref["body.p1179"].phase_scopes == [PhaseScope.UNKNOWN]
    assert all(
        phase_by_ref[source_ref].phase_scopes == [PhaseScope.PHASE_II]
        for source_ref in ("body.p1180", "body.p1181")
    )
    same_heading_plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=12,
        context_radius=1,
        batch_packing_policy=PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY,
    )

    assert len(extraction.blocks) == 3581
    assert len(phase.graph.blocks) == 3405
    assert len(manifest.units) == 1848
    # The typed III-phase hypothesis lead-in resolves five formerly UNKNOWN
    # units out of the selected II-phase target set.
    assert len(plan.expected_structure_unit_ids) == 1240
    assert len(same_heading_plan.packages) == 210
    assert len(plan.packages) == 131
    assert len(plan.packages) < len(same_heading_plan.packages)
    assert plan.expected_structure_unit_ids == same_heading_plan.expected_structure_unit_ids
    assert [
        unit.structure_unit_id
        for package in plan.packages
        for unit in package.owned_units
    ] == plan.expected_structure_unit_ids
    assert all(len(package.owned_units) <= 12 for package in plan.packages)
    package_32 = next(package for package in plan.packages if package.package_ordinal == 32)
    assert len(package_32.owned_units) == 12
    assert len({unit.structure_unit_id for unit in package_32.owned_units}) == 12

    table_5 = [unit for unit in manifest.units if unit.source_ref.startswith("body.t5.r")]
    assert [unit.source_ref for unit in table_5] == [f"body.t5.r{row}" for row in range(39)]
    member_refs = [ref for unit in table_5 for ref in unit.member_source_refs]
    assert len(member_refs) == 241
    assert len(set(member_refs)) == 241
    assert all(unit.phase_scopes == [PhaseScope.PHASE_II] for unit in table_5)

    table_5_projection = [
        block for block in projection.blocks if block.source_ref.startswith("body.t5.c")
    ]
    assert {block.source_ref for block in table_5_projection} == {
        f"body.t5.c{column}" for column in range(10)
    }

    assert _snapshot(path) == before, "D001 只读重建不得改写源文件或源目录"
