"""Phase 3 slice 2: metadata, phase projection and interpretation contracts."""
from __future__ import annotations

from datetime import date, datetime, timezone
from itertools import combinations

import pytest
from pydantic import ValidationError

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import (
    AlignmentStatus,
    DocumentPart,
    IdentityAuthority,
    InterpretationAuthority,
    InterpretationChangeField,
    InterpretationConflictStatus,
    InterpretationSourceType,
    MetadataSourceKind,
    PhaseScope,
    StudyPhase,
    SourceLocatorPrecision,
)
from app.domain.interpretation import (
    InterpretationAuthorityError,
    assess_interpretation_authority,
    build_interpretation_conflict,
    publication_blockers,
)
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityBlock,
    ProtocolMetadataCandidate,
    InterpretationConflict,
    InterpretationSource,
)
from app.protocols.docx_structure import BlockKind, HeaderFooterKind, StructureBlock
from app.protocols.metadata import (
    MetadataExtractionError,
    confirm_protocol_identity,
    extract_protocol_metadata,
    resolve_protocol_identity,
)
from app.protocols.phase_detection import build_phase_applicability_graph, project_single_phase


def _block(
    source_ref: str,
    text: str,
    order: int,
    *,
    part: DocumentPart = DocumentPart.BODY,
    table_path: tuple[int, ...] | None = None,
) -> StructureBlock:
    return StructureBlock(
        source_ref=source_ref,
        document_part=part,
        block_order=order,
        kind=BlockKind.PARAGRAPH,
        text=text,
        table_path=table_path,
        part_kind=HeaderFooterKind.DEFAULT if part in {DocumentPart.HEADER, DocumentPart.FOOTER} else None,
    )


def _metadata_blocks() -> list[StructureBlock]:
    return [
        _block("header.default.p0", "方案编号：P-001", 0, part=DocumentPart.HEADER),
        _block(
            "header.default.p1",
            "方案版本/日期：V2.1 / 2025年09月19日",
            1,
            part=DocumentPart.HEADER,
        ),
        _block("header.default.p2", "文件编号：TPL-09", 2, part=DocumentPart.HEADER),
        _block("header.default.p3", "版 本 号：00", 3, part=DocumentPart.HEADER),
        _block("body.p0", "临床研究方案", 4),
        _block("body.t0.r0.c0.p0", "方案编号", 5, table_path=(0, 0)),
        _block("body.t0.r0.c1.p0", "P-001", 6, table_path=(0, 1)),
        _block("body.t0.r1.c0.p0", "版本号", 7, table_path=(1, 0)),
        _block("body.t0.r1.c1.p0", "V2.1", 8, table_path=(1, 1)),
        _block("body.t0.r2.c0.p0", "版本日期", 9, table_path=(2, 0)),
        _block("body.t0.r2.c1.p0", "2025年09月19日", 10, table_path=(2, 1)),
    ]


class _DegradedHeaderSpan:
    source_span_id = "span-header"
    precision = SourceLocatorPrecision.PAGE_ONLY
    alignment_status = AlignmentStatus.DEGRADED


def test_metadata_priority_template_separation_and_generic_confirmation() -> None:
    result = extract_protocol_metadata(
        _metadata_blocks(),
        snapshot_id="snap-metadata",
        file_name="P-999 临床研究方案.docx",
        source_spans={"header.default.p0": _DegradedHeaderSpan()},
    )

    protocol_codes = [
        item
        for item in result.candidates
        if item.field_category.value == "protocol_code"
    ]
    header_code = next(item for item in protocol_codes if item.source_kind == MetadataSourceKind.HEADER_FOOTER)
    assert header_code.priority_rank < min(item.priority_rank for item in protocol_codes if item is not header_code)
    assert header_code.identity_authority == IdentityAuthority.HIGH
    assert header_code.locator_precision == SourceLocatorPrecision.PAGE_ONLY
    assert header_code.source_alignment_status == AlignmentStatus.DEGRADED
    assert header_code.source_span_id == "span-header"

    template_fields = {
        item.field_category.value
        for item in result.candidates
        if item.source_kind == MetadataSourceKind.HEADER_FOOTER
    }
    assert {"template_code", "template_version"} <= template_fields
    assert "template_code" not in {item.field_category.value for item in protocol_codes}

    # A lower-priority filename fallback is retained as evidence but does not
    # conflict with an agreed formal protocol-code layer.
    assert not any(
        item.field_category.value == "protocol_code" for item in result.conflicts
    )
    filename_code = next(
        item
        for item in protocol_codes
        if item.source_kind == MetadataSourceKind.FILENAME
    )
    assert filename_code.is_fallback is True
    assert filename_code.conflict_group_id is None

    same_authority = extract_protocol_metadata(
        _metadata_blocks()
        + [_block("header.default.p-conflict", "方案编号：P-002", 11, part=DocumentPart.HEADER)],
        snapshot_id="snap-metadata-conflict",
        file_name="P-999 临床研究方案.docx",
    )
    code_conflict = next(
        item for item in same_authority.conflicts if item.field_category.value == "protocol_code"
    )
    assert set(code_conflict.normalized_values) == {"P-001", "P-002"}
    assert all(
        not item.is_fallback
        for item in same_authority.candidates
        if item.candidate_id in code_conflict.candidate_ids
    )

    pending = resolve_protocol_identity(
        result,
        identity_decision_id="identity-1",
        study_phase=StudyPhase.PHASE_II,
    )
    assert pending.status.value == "needs_confirmation"
    assert pending.project_name is None, "通用标题不能自动成为项目名称"
    assert pending.protocol_code == "P-001"
    assert pending.project_code == "P"

    confirmed = confirm_protocol_identity(
        result,
        pending,
        protocol_code="P-001",
        project_name="确认后的真实项目",
        official_version="V2.1",
        official_date=DateValue(value=date(2025, 9, 19), precision="day"),
        study_phase=StudyPhase.PHASE_II,
        confirmed_by="reviewer",
        confirmed_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
    )
    assert confirmed.confirmation_required is False
    assert confirmed.status.value == "confirmed"
    assert confirmed.project_name == "确认后的真实项目"
    assert confirmed.conflict_ids == []

    conflict_pending = resolve_protocol_identity(
        same_authority,
        identity_decision_id="identity-conflict",
        study_phase=StudyPhase.PHASE_II,
    )
    assert conflict_pending.conflict_ids == [code_conflict.conflict_id]
    conflict_confirmed = confirm_protocol_identity(
        same_authority,
        conflict_pending.model_copy(update={"resolved_conflict_ids": ["prior-conflict"]}),
        protocol_code="P-002",
        project_name="真实项目",
        official_version="V2.1",
        official_date=DateValue(value=date(2025, 9, 19), precision="day"),
        study_phase=StudyPhase.PHASE_II,
        confirmed_by="reviewer",
        confirmed_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
    )
    assert conflict_confirmed.conflict_ids == []
    assert conflict_confirmed.resolved_conflict_ids == [
        "prior-conflict",
        code_conflict.conflict_id,
    ]
    chosen = {
        item.candidate_id
        for item in same_authority.candidates
        if item.field_category.value == "protocol_code" and item.normalized_value == "P-002"
    }
    assert chosen <= set(conflict_confirmed.selected_candidate_ids)
    with pytest.raises(MetadataExtractionError, match="必须明确选中"):
        confirm_protocol_identity(
            same_authority,
            conflict_pending,
            protocol_code="P-003",
            project_name="真实项目",
            official_version="V2.1",
            official_date=DateValue(value=date(2025, 9, 19), precision="day"),
            study_phase=StudyPhase.PHASE_II,
            confirmed_by="reviewer",
            confirmed_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
        )


def test_filename_fallback_separates_code_version_date_and_preserves_project_code() -> None:
    result = extract_protocol_metadata(
        [_block("body.p0", "临床研究方案", 0)],
        snapshot_id="filename-only",
        file_name="CMS-D001_v1.2_2025-12-21.docx",
    )
    values = {
        item.field_category.value: item.normalized_value
        for item in result.candidates
        if item.source_kind == MetadataSourceKind.FILENAME
        and item.field_category.value != "document_title"
    }
    assert values == {
        "protocol_code": "CMS-D001",
        "protocol_version": "1.2",
        "protocol_date": "2025-12-21",
    }

    explicit = extract_protocol_metadata(
        _metadata_blocks() + [_block("body.p20", "项目代号：STUDY-ALPHA", 20)],
        snapshot_id="explicit-project-code",
    )
    pending = resolve_protocol_identity(
        explicit,
        identity_decision_id="identity-project-code",
        study_phase=StudyPhase.PHASE_II,
    )
    confirmed = confirm_protocol_identity(
        explicit,
        pending,
        project_code="STUDY-ALPHA",
        protocol_code="P-001",
        project_name="真实项目",
        official_version="V2.1",
        official_date=DateValue(value=date(2025, 9, 19), precision="day"),
        study_phase=StudyPhase.PHASE_II,
        confirmed_by="reviewer",
        confirmed_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
    )
    assert confirmed.project_code == "STUDY-ALPHA"


def test_month_precision_conflict_confirmation_and_unknown_date_error() -> None:
    blocks = _metadata_blocks() + [
        _block(
            "header.default.p-date-a",
            "方案日期：2025年09月",
            30,
            part=DocumentPart.HEADER,
        ),
        _block(
            "header.default.p-date-b",
            "方案日期：2025年10月",
            31,
            part=DocumentPart.HEADER,
        ),
    ]
    result = extract_protocol_metadata(blocks, snapshot_id="month-conflict")
    pending = resolve_protocol_identity(
        result,
        identity_decision_id="month-identity",
        study_phase=StudyPhase.PHASE_II,
    )
    date_conflict = next(
        item
        for item in result.conflicts
        if item.field_category.value == "protocol_date"
    )
    confirmed = confirm_protocol_identity(
        result,
        pending,
        protocol_code="P-001",
        project_name="真实项目",
        official_version="V2.1",
        official_date=DateValue(value=date(2025, 9, 1), precision="month"),
        study_phase=StudyPhase.PHASE_II,
        confirmed_by="reviewer",
        confirmed_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
    )
    assert date_conflict.conflict_id in confirmed.resolved_conflict_ids
    with pytest.raises(MetadataExtractionError, match="年、月或日精度"):
        confirm_protocol_identity(
            result,
            pending,
            protocol_code="P-001",
            project_name="真实项目",
            official_version="V2.1",
            official_date=DateValue(value=None, precision="unknown"),
            study_phase=StudyPhase.PHASE_II,
            confirmed_by="reviewer",
            confirmed_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
        )


def _phase_blocks() -> list[StructureBlock]:
    return [
        _block("body.p0", "Ⅱ期和Ⅲ期相同的共同检查", 0),
        _block("body.p1", "Ⅱ期专属入组标准", 1),
        _block("body.p2", "Ⅲ期专属入组标准", 2),
        _block("body.p3", "Ⅱ期与Ⅲ期相同的共享随访要求", 3),
        _block("body.t0.r0.c0.p0", "访视", 4, table_path=(0, 0)),
        _block("body.t0.r0.c1.p0", "筛选", 5, table_path=(0, 1)),
        _block("body.t0.r0.c2.p0", "基线", 6, table_path=(0, 2)),
        _block("body.t0.r1.c0.p0", "项目", 7, table_path=(1, 0)),
        _block("body.t0.r1.c1.p0", "Ⅱ期筛选检查", 8, table_path=(1, 1)),
        _block("body.t0.r1.c2.p0", "Ⅲ期基线检查", 9, table_path=(1, 2)),
    ]


def test_phase_graph_has_paragraph_row_column_and_strict_single_phase_projection() -> None:
    result = build_phase_applicability_graph(_phase_blocks(), snapshot_id="snap-phase")
    granularities = {item.granularity.value for item in result.graph.blocks}
    assert granularities == {"paragraph", "table_row", "visit_column"}
    visit_columns = [item for item in result.graph.blocks if item.granularity.value == "visit_column"]
    assert {item.visit_column for item in visit_columns} == {0, 1, 2}
    assert all(item.source_ref.endswith(f"c{item.visit_column}") for item in visit_columns)

    for selected in (StudyPhase.PHASE_II, StudyPhase.PHASE_III):
        projection = project_single_phase(result.graph, selected)
        assert projection.blocks
        assert all(
            tuple(item.phase_scopes)
            in {
                (PhaseScope.PHASE_II if selected == StudyPhase.PHASE_II else PhaseScope.PHASE_III,),
                (PhaseScope.SHARED,),
            }
            for item in projection.blocks
        )
        comparison_text = " ".join(item.projection_text or "" for item in projection.blocks)
        assert "与Ⅲ期相同" not in comparison_text
        assert "与Ⅱ期相同" not in comparison_text
        source_by_id = {item.block_id: item for item in result.graph.blocks}
        assert all(item.text == source_by_id[item.block_id].text for item in projection.blocks)
        assert any(item.cross_phase_comparison for item in projection.blocks)

    # Combinatorial property-style check: no selected-phase projection may
    # admit a block whose only scope is the opposite phase.
    for scopes in combinations(
        (PhaseScope.PHASE_II, PhaseScope.PHASE_III, PhaseScope.SHARED), 2
    ):
        blocks = [
            PhaseApplicabilityBlock(
                block_id=f"b-{index}",
                snapshot_id="property-snap",
                source_ref=f"body.property.{index}",
                source_span_ids=[f"span-{index}"],
                granularity="paragraph",
                source_order=index,
                text="适用条款",
                phase_scopes=list(scopes),
            )
            for index in range(2)
        ]
        blocks.append(
            PhaseApplicabilityBlock(
                block_id="b-shared",
                snapshot_id="property-snap",
                source_ref="body.property.shared",
                source_span_ids=["span-shared"],
                granularity="paragraph",
                source_order=3,
                text="共享条款",
                phase_scopes=[PhaseScope.SHARED],
            )
        )
        from app.domain.contracts.protocol_metadata import PhaseApplicabilityGraph

        graph = PhaseApplicabilityGraph(
            graph_id=f"graph-{scopes[0].value}-{scopes[1].value}",
            snapshot_id="property-snap",
            blocks=blocks,
            detected_phase_scopes=list(scopes),
        )
        for selected, opposite in (
            (StudyPhase.PHASE_II, PhaseScope.PHASE_III),
            (StudyPhase.PHASE_III, PhaseScope.PHASE_II),
        ):
            projection = project_single_phase(graph, selected)
            selected_only = [item for item in projection.blocks if item.phase_scopes == [opposite]]
            assert selected_only == []


def test_large_table_local_scope_does_not_promote_mixed_column_or_row() -> None:
    """A giant table must not become shared from one local comparison cell."""

    cells = [
        ("body.t0.r0.c0.p0", "访视"),
        ("body.t0.r0.c1.p0", "Ⅱ期"),
        ("body.t0.r0.c2.p0", "Ⅲ期"),
        ("body.t0.r1.c0.p0", "项目1"),
        ("body.t0.r1.c1.p0", "Ⅱ期标准"),
        ("body.t0.r1.c2.p0", "Ⅲ期标准"),
        ("body.t0.r2.c0.p0", "项目2"),
        ("body.t0.r2.c1.p0", "Ⅲ期标准"),
        ("body.t0.r2.c2.p0", "共同程序"),
        ("body.t0.r3.c0.p0", "项目3"),
        ("body.t0.r3.c1.p0", "Ⅱ期和Ⅲ期相同"),
        ("body.t0.r3.c2.p0", "共同程序"),
    ]
    blocks = [
        _block(
            ref,
            text,
            index,
            table_path=(
                int(ref.split(".r")[1].split(".")[0]),
                int(ref.split(".c")[1].split(".")[0]),
            ),
        )
        for index, (ref, text) in enumerate(cells)
    ]
    result = build_phase_applicability_graph(blocks, snapshot_id="large-table")
    graph = result.graph
    mixed_column = next(item for item in graph.blocks if item.source_ref == "body.t0.c1")
    mixed_row = next(item for item in graph.blocks if item.source_ref == "body.t0.r1")
    assert mixed_column.phase_scopes == [PhaseScope.MIXED]
    assert mixed_row.phase_scopes == [PhaseScope.MIXED]
    assert mixed_column.is_shared is False
    assert mixed_column.child_block_ids
    assert set(mixed_column.source_span_ids) == {
        item.source_span_ids[0]
        for item in graph.blocks
        if item.block_id in mixed_column.child_block_ids
    }
    for selected in (StudyPhase.PHASE_II, StudyPhase.PHASE_III):
        projection = project_single_phase(graph, selected)
        refs = {item.source_ref for item in projection.blocks}
        assert "body.t0.c1" not in refs
        assert "body.t0.r1" not in refs
        assert all(
            tuple(item.phase_scopes)
            in {
                (PhaseScope.PHASE_II if selected == StudyPhase.PHASE_II else PhaseScope.PHASE_III,),
                (PhaseScope.SHARED,),
            }
            for item in projection.blocks
        )


def test_same_table_cell_inherits_nearest_phase_or_shared_criteria_lead_in() -> None:
    blocks = [
        _block("body.t0.r0.c0.p0", "入选标准", 0, table_path=(0, 0)),
        _block("body.t0.r0.c1.p0", "Ⅱ期符合下列所有标准的受试者才能入选", 1, table_path=(0, 1)),
        _block("body.t0.r0.c1.p1", "Ⅱ期条款一", 2, table_path=(0, 1)),
        _block("body.t0.r0.c1.p2", "Ⅲ期符合下列所有标准的受试者才能入选", 3, table_path=(0, 1)),
        _block("body.t0.r0.c1.p3", "Ⅲ期条款一", 4, table_path=(0, 1)),
        _block("body.t0.r1.c0.p0", "排除标准", 5, table_path=(1, 0)),
        _block(
            "body.t0.r1.c1.p0",
            "Ⅱ期和Ⅲ期中符合以下任一标准的受试者将从研究中排除",
            6,
            table_path=(1, 1),
        ),
        _block("body.t0.r1.c1.p1", "对研究药物或其辅料过敏", 7, table_path=(1, 1)),
    ]
    graph = build_phase_applicability_graph(blocks, snapshot_id="cell-context").graph
    by_ref = {item.source_ref: item for item in graph.blocks if not item.is_aggregate}
    assert by_ref["body.t0.r0.c1.p1"].phase_scopes == [PhaseScope.PHASE_II]
    assert by_ref["body.t0.r0.c1.p3"].phase_scopes == [PhaseScope.PHASE_III]
    assert by_ref["body.t0.r1.c1.p0"].phase_scopes == [PhaseScope.SHARED]
    assert by_ref["body.t0.r1.c1.p1"].phase_scopes == [PhaseScope.SHARED]
    for selected in (StudyPhase.PHASE_II, StudyPhase.PHASE_III):
        refs = {item.source_ref for item in project_single_phase(graph, selected).blocks}
        assert "body.t0.r1.c1.p1" in refs

    bare = [
        _block("body.t1.r0.c0.p0", "共同排除标准", 20, table_path=(0, 0)),
        _block("body.t1.r0.c0.p1", "对研究药物过敏", 21, table_path=(0, 0)),
    ]
    bare_graph = build_phase_applicability_graph(bare, snapshot_id="bare-shared").graph
    bare_by_ref = {item.source_ref: item for item in bare_graph.blocks if not item.is_aggregate}
    assert bare_by_ref["body.t1.r0.c0.p0"].phase_scopes == [PhaseScope.SHARED]
    assert bare_by_ref["body.t1.r0.c0.p1"].phase_scopes == [PhaseScope.SHARED]


def test_visit_table_inherits_single_phase_from_its_structural_heading() -> None:
    blocks = [
        _block("body.p0", "表 1 Ⅱ期临床研究阶段流程表", 0),
        _block("body.t0", "", 1),
        _block("body.t0.r0.c0.p0", "访视", 2, table_path=(0, 0)),
        _block("body.t0.r0.c1.p0", "筛选", 3, table_path=(0, 1)),
        _block("body.t0.r1.c0.p0", "入排标准审核", 4, table_path=(1, 0)),
        _block("body.t0.r1.c1.p0", "X", 5, table_path=(1, 1)),
    ]

    graph = build_phase_applicability_graph(blocks, snapshot_id="phase-heading-table").graph
    atomic = {item.source_ref: item for item in graph.blocks if not item.is_aggregate}

    assert atomic["body.t0.r1.c0.p0"].phase_scopes == [PhaseScope.PHASE_II]
    assert atomic["body.t0.r1.c1.p0"].phase_scopes == [PhaseScope.PHASE_II]
    phase_ii_refs = {
        item.source_ref for item in project_single_phase(graph, StudyPhase.PHASE_II).blocks
    }
    assert "body.t0.c1" in phase_ii_refs
    assert not any(
        item.phase_scopes == [PhaseScope.PHASE_III] for item in graph.blocks
    )


def test_visit_table_for_both_phases_is_shared_without_cross_phase_noise() -> None:
    blocks = [
        _block("body.p0", "研究日程表（Ⅱ期/Ⅲ期）", 0),
        _block("body.t0", "", 1),
        _block("body.t0.r0.c0.p0", "访视", 2, table_path=(0, 0)),
        _block("body.t0.r0.c1.p0", "基线", 3, table_path=(0, 1)),
        _block("body.t0.r1.c0.p0", "入排标准审核", 4, table_path=(1, 0)),
        _block("body.t0.r1.c1.p0", "X", 5, table_path=(1, 1)),
    ]

    graph = build_phase_applicability_graph(blocks, snapshot_id="shared-heading-table").graph
    atomic = {item.source_ref: item for item in graph.blocks if not item.is_aggregate}

    assert atomic["body.t0.r1.c0.p0"].phase_scopes == [PhaseScope.SHARED]
    assert atomic["body.t0.r1.c1.p0"].phase_scopes == [PhaseScope.SHARED]
    for selected in (StudyPhase.PHASE_II, StudyPhase.PHASE_III):
        projection = project_single_phase(graph, selected)
        assert "body.t0.c1" in {item.source_ref for item in projection.blocks}
        assert all("与另一研究期别" not in (item.projection_text or "") for item in projection.blocks)


def test_nearby_phase_narrative_does_not_retag_following_visit_table() -> None:
    blocks = [
        _block("body.p0", "Ⅱ期受试者完成后将进行阶段性分析。", 0),
        _block("body.p1", "受试者访视安排说明", 1),
        _block("body.t0", "", 2),
        _block("body.t0.r0.c0.p0", "访视", 3, table_path=(0, 0)),
        _block("body.t0.r0.c1.p0", "筛选", 4, table_path=(0, 1)),
        _block("body.t0.r1.c0.p0", "入排标准审核", 5, table_path=(1, 0)),
        _block("body.t0.r1.c1.p0", "X", 6, table_path=(1, 1)),
    ]

    graph = build_phase_applicability_graph(blocks, snapshot_id="narrative-table").graph
    atomic = {item.source_ref: item for item in graph.blocks if not item.is_aggregate}

    assert atomic["body.t0.r1.c0.p0"].phase_scopes == [PhaseScope.UNKNOWN]
    assert atomic["body.t0.r1.c1.p0"].phase_scopes == [PhaseScope.UNKNOWN]


def test_single_phase_common_wording_does_not_leak_and_projection_text_is_derived_only() -> None:
    blocks = [
        _block("body.p0", "Ⅲ期共同适用标准", 0),
        _block("body.p1", "Ⅲ期要求一", 1),
        _block("body.p2", "两期均需签署知情同意书", 2),
    ]
    graph = build_phase_applicability_graph(blocks, snapshot_id="single-phase-common").graph
    assert graph.blocks[0].phase_scopes == [PhaseScope.PHASE_III]
    phase_ii = project_single_phase(graph, StudyPhase.PHASE_II)
    assert [item.source_ref for item in phase_ii.blocks] == ["body.p2"]
    mixed_graph = build_phase_applicability_graph(
        [_block("body.p0", "Ⅱ期共同排除标准，Ⅲ期专属要求", 0)],
        snapshot_id="mixed-common-wording",
    ).graph
    assert mixed_graph.blocks[0].phase_scopes == [PhaseScope.MIXED]
    with pytest.raises(ValidationError, match="仅跨期原文块"):
        PhaseApplicabilityBlock(
            block_id="forged-projection",
            snapshot_id="single-phase-common",
            source_ref="body.p2",
            source_span_ids=["body.p2"],
            granularity="paragraph",
            source_order=2,
            text="Ⅲ期专属条款",
            phase_scopes=[PhaseScope.PHASE_III],
            projection_text="伪造的Ⅱ期显示",
        )


@pytest.mark.parametrize(
    "texts,expected",
    [
        (
            [
                "Ⅱ/Ⅲ期操作无缝适应性设计",
                "同一受试者队列连续跨期",
                "继续纳入新的Ⅲ期受试者",
            ],
            False,
        ),
        (["Ⅱ/Ⅲ期操作无缝", "剂量选择衔接", "同一受试者队列连续跨期"], False),
        (["Ⅱ/Ⅲ期无缝适应性设计", "同一受试者队列连续跨期"], True),
        (["Ⅱ/Ⅲ期无缝适应性设计", "连续跨期"], False),
    ],
)
def test_only_explicit_same_cohort_design_can_create_seamless_candidate(texts, expected) -> None:
    blocks = [_block(f"body.seamless.{index}", text, index) for index, text in enumerate(texts)]
    result = build_phase_applicability_graph(blocks, snapshot_id=f"seamless-{expected}")
    assert bool(result.graph.seamless_candidates) is expected
    if expected:
        assert result.graph.seamless_candidates[0].requires_second_confirmation is True
        assert any(item.design_type.value == "seamless_candidate" for item in result.phase_candidates)
        assert project_single_phase(result.graph, StudyPhase.SEAMLESS_II_III).blocks
    else:
        with pytest.raises(ValueError, match="无缝候选"):
            project_single_phase(result.graph, StudyPhase.SEAMLESS_II_III)


def _interpretation_source(source_type: InterpretationSourceType, *, amendment: bool = False) -> InterpretationSource:
    return InterpretationSource(
        interpretation_source_id=f"source-{source_type.value}-{amendment}",
        protocol_version_id="protocol-v1",
        source_type=source_type,
        file_sha256="a" * 64,
        source_version="1.0",
        source_ref="body.p10",
        excerpt="来源摘录",
        explanation="说明方案模糊处",
        clarifies_ambiguity=True,
        is_current_amendment=amendment,
        formal_change_summary="正式修订阈值" if amendment else None,
    )


def test_interpretation_authority_and_conflict_block_publication() -> None:
    amendment = _interpretation_source(InterpretationSourceType.AMENDMENT, amendment=True)
    assert amendment.authority == InterpretationAuthority.FORMAL_REQUIREMENT
    amendment_assessment = assess_interpretation_authority(
        amendment,
        protocol_is_ambiguous=False,
        requested_changes=[InterpretationChangeField.THRESHOLD],
    )
    assert amendment_assessment.allowed is True
    assert amendment_assessment.clarification_only is False

    qa = _interpretation_source(InterpretationSourceType.QA)
    allowed = assess_interpretation_authority(qa, protocol_is_ambiguous=True)
    assert allowed.allowed is True
    assert allowed.authority == InterpretationAuthority.CLARIFICATION_ONLY
    assert allowed.clarification_only is True

    denied = assess_interpretation_authority(
        qa,
        protocol_is_ambiguous=True,
        requested_changes=[InterpretationChangeField.BOOLEAN_LOGIC],
    )
    assert denied.allowed is False
    assert "boolean_logic" in denied.forbidden_changes
    with pytest.raises(InterpretationAuthorityError):
        from app.domain.interpretation import validate_interpretation_authority

        validate_interpretation_authority(
            qa,
            protocol_is_ambiguous=True,
            requested_changes=[InterpretationChangeField.DUE_STAGE],
        )

    conflict = build_interpretation_conflict(
        conflict_id="conflict-1",
        source=qa,
        affected_rule_refs=["IN-01"],
        protocol_source_refs=["body.p20"],
        reason="解释材料与方案阈值不一致",
        impact="无法安全发布",
    )
    assert conflict.blocks_publication is True
    assert publication_blockers([conflict]) == ["conflict-1"]
    resolved = conflict.model_copy(
        update={
            "status": InterpretationConflictStatus.RESOLVED_BY_CURRENT_AMENDMENT,
            "blocks_publication": False,
            "resolved_by_amendment_source_id": amendment.interpretation_source_id,
            "resolved_at": datetime(2026, 8, 14, tzinfo=timezone.utc),
        }
    )
    assert publication_blockers([resolved]) == []
