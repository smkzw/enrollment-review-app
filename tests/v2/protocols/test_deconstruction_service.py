"""Focused tests for deterministic protocol-deconstruction input assembly.

The real-protocol cases render and align the original DOCX files without
writing beside them; all derived artifacts go to pytest's temporary directory.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
from pathlib import Path

import pytest

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import (
    AlignmentStatus,
    ApplicabilityGranularity,
    DatePrecision,
    DocumentPart,
    ExtractionStatus,
    MetadataResolutionStatus,
    PhaseScope,
    SourceLocatorPrecision,
    StudyPhase,
    ReviewStage,
)
from app.domain.contracts.protocol_ingestion import (
    ProtocolExtractionSnapshot,
    ProtocolSourceArtifact,
    ProtocolSourceSpan,
)
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityBlock,
    PhaseApplicabilityGraph,
    ProtocolIdentityDecision,
    StudyPhaseSelection,
)
from app.protocols.deconstruction_service import (
    ProtocolDeconstructionInputAssembler,
    ProtocolDeconstructionInputAssemblyError,
)
from app.protocols.docx_structure import (
    BlockKind,
    NumberingRef,
    StructureBlock,
    StructureExtraction,
    extract_docx_structure,
)
from app.protocols.ingestion import register_source_artifact
from app.protocols.metadata import extract_protocol_metadata, resolve_protocol_identity
from app.protocols.phase_detection import build_phase_applicability_graph
from app.protocols.rendering import pdf_page_texts, render_to_pdf
from app.protocols.section_index import formal_source_span_ids
from app.protocols.source_alignment import align_blocks


NOW = datetime(2026, 8, 14, tzinfo=timezone.utc)
SYNTHETIC_SNAPSHOT = "snapshot-deconstruction-input"
SYNTHETIC_SHA = "a" * 64
SYNTHETIC_RENDER = "render-deconstruction-input"


@dataclass(frozen=True)
class _SyntheticFixture:
    artifact: ProtocolSourceArtifact
    extraction: StructureExtraction
    spans: tuple[ProtocolSourceSpan, ...]
    phase_graph: PhaseApplicabilityGraph
    identity: ProtocolIdentityDecision
    selection: StudyPhaseSelection


def _paragraph(
    order: int,
    text: str,
    *,
    numbering: NumberingRef | None = None,
    style: str | None = None,
) -> StructureBlock:
    return StructureBlock(
        source_ref=f"body.p{order}",
        document_part=DocumentPart.BODY,
        section_index=0,
        block_order=order,
        kind=BlockKind.PARAGRAPH,
        text=text,
        numbering=numbering,
        style=style,
    )


def _table_cell(order: int, row: int, col: int, text: str) -> StructureBlock:
    return StructureBlock(
        source_ref=f"body.t0.r{row}.c{col}.p0",
        document_part=DocumentPart.BODY,
        section_index=0,
        block_order=order,
        kind=BlockKind.PARAGRAPH,
        text=text,
        table_path=(row, col),
    )


def _synthetic_blocks() -> tuple[StructureBlock, ...]:
    parent_numbering = NumberingRef(
        num_id=11,
        level=0,
        abstract_num_id=101,
        num_fmt="decimal",
        lvl_text="%1)",
        start=1,
    )
    exclusion_numbering = NumberingRef(
        num_id=20,
        level=0,
        abstract_num_id=200,
        num_fmt="decimal",
        lvl_text="%1)",
        start=1,
    )
    blocks = [
        _paragraph(0, "入选标准", style="Heading 2"),
        _paragraph(1, "III期适用标准"),
        _paragraph(2, "年龄≥18岁", numbering=parent_numbering),
        _paragraph(3, "能够完成研究要求", numbering=parent_numbering),
        _paragraph(4, "II期适用标准"),
        _paragraph(5, "仅II期条件", numbering=parent_numbering),
        _paragraph(6, "排除标准", style="Heading 2"),
        _paragraph(7, "II期和III期共同适用标准"),
        _paragraph(8, "活动性感染", numbering=exclusion_numbering),
        _paragraph(9, "研究者判断存在不可接受风险", numbering=exclusion_numbering),
        _paragraph(10, "研究设计", style="Heading 2"),
        _paragraph(11, "II期专属研究设计说明"),
        StructureBlock(
            source_ref="body.t0",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=12,
            kind=BlockKind.TABLE,
            text="",
            table_rows=3,
            table_cols=3,
        ),
        _table_cell(13, 0, 0, "检查项目"),
        _table_cell(14, 0, 1, "筛选期"),
        _table_cell(15, 0, 2, "基线期"),
        _table_cell(16, 1, 0, "访视"),
        _table_cell(17, 1, 1, "V1"),
        _table_cell(18, 1, 2, "V2"),
        _table_cell(19, 2, 0, "血生化检查"),
        _table_cell(20, 2, 1, "X"),
        _table_cell(21, 2, 2, "X"),
    ]
    return tuple(blocks)


def _synthetic_phase_graph(blocks: tuple[StructureBlock, ...]) -> PhaseApplicabilityGraph:
    scopes = {
        0: (PhaseScope.SHARED,),
        1: (PhaseScope.PHASE_III,),
        2: (PhaseScope.PHASE_III,),
        3: (PhaseScope.PHASE_III,),
        4: (PhaseScope.PHASE_II,),
        5: (PhaseScope.PHASE_II,),
        6: (PhaseScope.SHARED,),
        7: (PhaseScope.SHARED,),
        8: (PhaseScope.SHARED,),
        9: (PhaseScope.SHARED,),
        10: (PhaseScope.SHARED,),
        11: (PhaseScope.PHASE_II,),
    }
    graph_blocks: list[PhaseApplicabilityBlock] = []
    for block in blocks:
        scope = scopes.get(block.block_order, (PhaseScope.SHARED,))
        graph_blocks.append(
            PhaseApplicabilityBlock(
                block_id=f"phase-{block.source_ref}",
                snapshot_id=SYNTHETIC_SNAPSHOT,
                source_ref=block.source_ref,
                source_span_ids=[f"span-{block.source_ref}"],
                granularity=ApplicabilityGranularity.PARAGRAPH,
                source_order=block.block_order,
                text=block.text or "研究流程表",
                phase_scopes=list(scope),
                table_path=block.table_path,
            )
        )
    return PhaseApplicabilityGraph(
        graph_id="graph-deconstruction-input",
        snapshot_id=SYNTHETIC_SNAPSHOT,
        blocks=graph_blocks,
        detected_phase_scopes=[
            PhaseScope.PHASE_II,
            PhaseScope.PHASE_III,
            PhaseScope.SHARED,
        ],
    )


def _synthetic_spans(blocks: tuple[StructureBlock, ...]) -> tuple[ProtocolSourceSpan, ...]:
    spans: list[ProtocolSourceSpan] = []
    for block in blocks:
        source_span_id = f"span-{block.source_ref}"
        common = dict(
            source_span_id=source_span_id,
            snapshot_id=SYNTHETIC_SNAPSHOT,
            source_ref=block.source_ref,
            document_part=block.document_part,
            section_index=block.section_index,
            block_order=block.block_order,
            table_path=block.table_path,
            table_row=block.table_path[-2] if block.table_path else None,
            table_col=block.table_path[-1] if block.table_path else None,
        )
        if block.text:
            start = block.block_order * 10
            spans.append(
                ProtocolSourceSpan(
                    **common,
                    render_artifact_id=SYNTHETIC_RENDER,
                    render_page=1,
                    text_start=start,
                    text_end=start + len(block.text),
                    excerpt=block.text,
                    precision=SourceLocatorPrecision.TEXT_RANGE,
                    alignment_status=AlignmentStatus.ALIGNED,
                )
            )
        else:
            spans.append(
                ProtocolSourceSpan(
                    **common,
                    precision=SourceLocatorPrecision.BLOCK,
                    alignment_status=AlignmentStatus.UNALIGNED,
                    degradation_reason="表格结构根节点仅保留结构上下文",
                )
            )
    return tuple(spans)


def _synthetic_fixture() -> _SyntheticFixture:
    blocks = _synthetic_blocks()
    artifact = ProtocolSourceArtifact(
        source_artifact_id="artifact-deconstruction-input",
        file_name="synthetic-protocol.docx",
        sha256=SYNTHETIC_SHA,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=1,
        storage_ref="blobs/protocol_sources/synthetic.docx",
        uploaded_at=NOW,
    )
    snapshot = ProtocolExtractionSnapshot(
        snapshot_id=SYNTHETIC_SNAPSHOT,
        source_artifact_id=artifact.source_artifact_id,
        source_sha256=artifact.sha256,
        parser_name="synthetic",
        parser_version="1",
        status=ExtractionStatus.COMPLETED,
        coverage={
            "paragraph_count": len(blocks) - 1,
            "table_count": 1,
            "section_count": 1,
            "nested_table_count": 0,
        },
        content_sha256="b" * 64,
        content_storage_ref="blobs/protocol_blocks/synthetic.json",
        created_at=NOW,
    )
    identity = ProtocolIdentityDecision(
        identity_decision_id="identity-deconstruction-input",
        snapshot_id=SYNTHETIC_SNAPSHOT,
        project_name="合成研究",
        project_code="SYNTHETIC",
        protocol_code="SYN-001",
        official_version="V1.0",
        official_date=DateValue(value=date(2026, 8, 14), precision=DatePrecision.DAY),
        study_phase=StudyPhase.PHASE_III,
        selected_candidate_ids=["identity-candidate"],
        status=MetadataResolutionStatus.CONFIRMED,
        confirmation_required=False,
        confirmed_by="测试确认人",
        confirmed_at=NOW,
    )
    selection = StudyPhaseSelection(
        selection_id="selection-deconstruction-input",
        snapshot_id=SYNTHETIC_SNAPSHOT,
        selected_phase=StudyPhase.PHASE_III,
        candidate_ids=["phase-candidate"],
        status=MetadataResolutionStatus.CONFIRMED,
        confirmed_by="测试确认人",
        confirmed_at=NOW,
    )
    return _SyntheticFixture(
        artifact=artifact,
        extraction=StructureExtraction(blocks=blocks, snapshot=snapshot),
        spans=_synthetic_spans(blocks),
        phase_graph=_synthetic_phase_graph(blocks),
        identity=identity,
        selection=selection,
    )


def _assemble(fixture: _SyntheticFixture, *, spans=None):
    return ProtocolDeconstructionInputAssembler(frozen_at=NOW).assemble(
        project_id="project-deconstruction-input",
        protocol_version_id="protocol-version-deconstruction-input",
        source_artifact=fixture.artifact,
        extraction=fixture.extraction,
        source_spans=fixture.spans if spans is None else spans,
        phase_graph=fixture.phase_graph,
        identity_decision=fixture.identity,
        phase_selection=fixture.selection,
    )


def test_assembly_is_minimal_catalog_complete_and_runner_ready():
    fixture = _synthetic_fixture()
    package = _assemble(fixture)
    source_input = package.source_input

    catalog_source_ids = {
        span_id
        for catalog in (package.parent_rule_catalog, package.required_procedure_catalog)
        for item in catalog.items
        for span_id in item.source_span_ids
    }
    material_ids = {item.source_span_id for item in source_input.source_materials}
    assert material_ids == catalog_source_ids
    assert set(source_input.allowed_source_span_ids) == catalog_source_ids
    assert set(package.source_spans) == {span.source_span_id for span in fixture.spans}
    assert source_input.parent_rule_catalog is package.parent_rule_catalog
    assert source_input.required_procedure_catalog is package.required_procedure_catalog
    assert source_input.phase_projection_id == package.projection.projection_id
    assert len(package.parent_rule_catalog.items) == 4
    assert len(package.required_procedure_catalog.items) == 2
    assert all(item.review_stage is None for item in package.parent_rule_catalog.items)
    assert [item.review_stage for item in package.required_procedure_catalog.items] == [
        ReviewStage.SCREENING,
        ReviewStage.BASELINE,
    ]

    blocks_by_ref = {block.source_ref: block for block in fixture.extraction.blocks}
    assert all(
        item.text == blocks_by_ref[item.source_ref].text
        for item in source_input.source_materials
    )
    assert "span-body.p11" not in material_ids
    assert "span-body.p5" not in material_ids
    with pytest.raises(TypeError):
        package.source_spans["new-span"] = fixture.spans[0]  # type: ignore[index]


def test_assembly_keeps_confirmed_phase_isolated_from_opposite_phase_materials():
    fixture = _synthetic_fixture()
    package = _assemble(fixture)
    source_input = package.source_input

    assert source_input.selected_phase == StudyPhase.PHASE_III
    assert all(
        tuple(block.phase_scopes) in {(PhaseScope.PHASE_III,), (PhaseScope.SHARED,)}
        for block in package.projection.blocks
    )
    material_text = "\n".join(item.text for item in source_input.source_materials)
    assert "仅II期条件" not in material_text
    assert "II期专属研究设计说明" not in material_text
    assert [item.official_code for item in package.parent_rule_catalog.items] == [
        "IN-01",
        "IN-02",
        "EX-01",
        "EX-02",
    ]


def test_assembly_fails_when_a_catalog_item_has_only_degraded_source():
    fixture = _synthetic_fixture()
    degraded_refs = {"body.p2", "body.p3", "body.p8", "body.p9"}
    degraded: list[ProtocolSourceSpan] = []
    for span in fixture.spans:
        if span.source_ref not in degraded_refs:
            degraded.append(span)
            continue
        degraded.append(
            span.model_copy(
                update={
                    "render_artifact_id": "degraded-render",
                    "render_page": 7,
                    "text_start": None,
                    "text_end": None,
                    "excerpt": None,
                    "precision": SourceLocatorPrecision.PAGE_ONLY,
                    "alignment_status": AlignmentStatus.DEGRADED,
                    "degradation_reason": "只作页面提示",
                }
            )
        )

    with pytest.raises(ProtocolDeconstructionInputAssemblyError) as exc_info:
        _assemble(fixture, spans=tuple(degraded))
    assert exc_info.value.code == "catalog_item_without_formal_source"
    assert "正式" in str(exc_info.value)


REAL_PROTOCOLS = (
    (
        "MG-K10-SAR",
        Path(
            "/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/"
            "MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx"
        ),
        StudyPhase.PHASE_III,
        (7, 16),
        41,
    ),
    (
        "CMS-D001",
        Path(
            "/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/"
            "CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx"
        ),
        StudyPhase.PHASE_II,
        (6, 30),
        50,
    ),
)


def _source_snapshot(path: Path) -> tuple[str, int, int, tuple[str, ...]]:
    stat = path.stat()
    return (
        hashlib.sha256(path.read_bytes()).hexdigest(),
        stat.st_size,
        stat.st_mtime_ns,
        tuple(sorted(item.name for item in path.parent.iterdir())),
    )


@pytest.mark.parametrize(
    "label,path,selected_phase,expected_parent_counts,expected_procedure_count",
    REAL_PROTOCOLS,
)
def test_real_protocol_input_assembly_is_read_only_and_phase_scoped(
    label: str,
    path: Path,
    selected_phase: StudyPhase,
    expected_parent_counts: tuple[int, int],
    expected_procedure_count: int,
    tmp_path: Path,
) -> None:
    """Slow real-DOCX regression: MG III has 7/16 and D001 II has 6/30."""

    if not path.is_file():
        pytest.skip(f"真实方案文件缺失：{path}")
    before = _source_snapshot(path)

    artifact = register_source_artifact(
        path,
        source_artifact_id=f"deconstruction-input-{label}",
        storage_root=tmp_path,
    )
    extraction = extract_docx_structure(
        path,
        snapshot_id=f"deconstruction-input-{label}-snapshot",
        source_artifact=artifact,
        output_dir=tmp_path,
    )
    rendered = render_to_pdf(path, tmp_path / "rendered", source_artifact=artifact)
    assert rendered.status.value == "succeeded", rendered.render_error
    assert rendered.pdf_path is not None
    alignment = align_blocks(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
        render_artifact_id=f"deconstruction-input-{label}-render",
        page_texts=pdf_page_texts(rendered.pdf_path),
    )
    phase_detection = build_phase_applicability_graph(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
        source_span_ids={span.source_ref: span.source_span_id for span in alignment.spans},
    )
    metadata = extract_protocol_metadata(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
        file_name=path.name,
    )
    identity = resolve_protocol_identity(
        metadata,
        identity_decision_id=f"deconstruction-input-{label}-identity",
        study_phase=selected_phase,
    )
    selection = StudyPhaseSelection(
        selection_id=f"deconstruction-input-{label}-selection",
        snapshot_id=extraction.snapshot.snapshot_id,
        selected_phase=selected_phase,
        candidate_ids=[
            candidate.candidate_id
            for candidate in phase_detection.phase_candidates
            if selected_phase == StudyPhase.PHASE_II
            and PhaseScope.PHASE_II in candidate.phase_scopes
            or selected_phase == StudyPhase.PHASE_III
            and PhaseScope.PHASE_III in candidate.phase_scopes
        ][:1]
        or [f"deconstruction-input-{label}-phase-candidate"],
        status=MetadataResolutionStatus.CONFIRMED,
        confirmed_by="真实回归测试确认人",
        confirmed_at=NOW,
    )

    package = ProtocolDeconstructionInputAssembler(frozen_at=NOW).assemble(
        project_id=f"project-{label}",
        protocol_version_id=f"protocol-version-{label}",
        source_artifact=artifact,
        extraction=extraction,
        alignment=alignment,
        phase_detection=phase_detection,
        identity_decision=identity,
        phase_selection=selection,
    )

    parent_items = package.parent_rule_catalog.items
    inclusion_count = sum(
        item.official_code is not None and item.official_code.startswith("IN-")
        for item in parent_items
    )
    exclusion_count = sum(
        item.official_code is not None and item.official_code.startswith("EX-")
        for item in parent_items
    )
    assert (inclusion_count, exclusion_count) == expected_parent_counts
    assert len(package.required_procedure_catalog.items) == expected_procedure_count
    assert package.source_input.selected_phase == selected_phase
    assert package.source_input.protocol_file_sha256 == artifact.sha256

    formal_ids = formal_source_span_ids(package.source_spans.values())
    catalog_source_ids = {
        span_id
        for catalog in (package.parent_rule_catalog, package.required_procedure_catalog)
        for item in catalog.items
        for span_id in item.source_span_ids
    }
    material_ids = {item.source_span_id for item in package.source_input.source_materials}
    assert material_ids == catalog_source_ids
    assert material_ids == set(package.source_input.allowed_source_span_ids)
    assert all(
        set(item.source_span_ids) <= formal_ids
        for catalog in (package.parent_rule_catalog, package.required_procedure_catalog)
        for item in catalog.items
    )
    assert all(item.review_stage is None for item in package.parent_rule_catalog.items)
    assert all(item.review_stage is not None for item in package.required_procedure_catalog.items)
    assert all(
        material.source_span_id in package.source_spans
        for material in package.source_input.source_materials
    )
    assert _source_snapshot(path) == before
