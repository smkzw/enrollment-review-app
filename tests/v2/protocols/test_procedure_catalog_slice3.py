"""Focused structural tests for the Phase 3 required-procedure sidecar."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from app.domain.contracts.enums import (
    AlignmentStatus,
    ApplicabilityGranularity,
    CatalogItemKind,
    DocumentPart,
    PhaseScope,
    SourceLocatorPrecision,
    StudyPhase,
)
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentInput,
    build_protocol_control_agent_prompt,
)
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityBlock,
    PhaseApplicabilityGraph,
    PhaseProjection,
)
from app.protocols.docx_structure import BlockKind, NumberingRef, StructureBlock
from app.protocols.docx_structure import extract_docx_structure
from app.protocols.full_protocol_coverage import build_full_protocol_coverage_manifest
from app.protocols.ingestion import register_source_artifact
from app.protocols.phase_detection import (
    build_phase_applicability_graph,
    project_single_phase,
)
from app.protocols.procedure_catalog import (
    ProcedureCatalogError,
    build_required_procedure_catalog,
    derive_review_stage,
)
from app.protocols.protocol_control_planning import plan_protocol_control_batches
from app.protocols.catalogs import freeze_official_parent_rules
from app.protocols.rendering import pdf_page_texts, render_to_pdf
from app.protocols.section_index import build_section_index, formal_source_span_ids
from app.protocols.source_alignment import align_blocks, verify_excerpt_against_page


SNAPSHOT = "snapshot-procedure"
RENDER = "render-procedure"
FROZEN_AT = datetime(2026, 8, 14, tzinfo=timezone.utc)

REAL_PROCEDURE_PROTOCOLS = [
    (
        "MG-K10-SAR",
        Path(
            "/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/"
            "MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx"
        ),
        StudyPhase.PHASE_III,
        "body.t3",
        (7, 16),
        {"run_in": 25, "baseline": 16},
        {
            "筛选/导入期* / V1 / NA / D-7~D-1": 25,
            "双盲治疗期 / V2（基线） / W0 / D1": 16,
        },
    ),
    (
        "CMS-D001",
        Path(
            "/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/"
            "CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx"
        ),
        StudyPhase.PHASE_II,
        "body.t5",
        (6, 30),
        {"screening": 23, "baseline": 27},
        {
            "筛选期(D-28~D-1) / 筛选 / W-4~W-1 / D-28~D-1 / -": 23,
            "筛选期(D-28~D-1) / 基线 / D≤-7 / -": 15,
            "治疗期 / W0 / D1 / -": 12,
        },
    ),
]


def _source_snapshot(path: Path) -> tuple[str, int, int, tuple[str, ...]]:
    stat = path.stat()
    return (
        hashlib.sha256(path.read_bytes()).hexdigest(),
        stat.st_size,
        stat.st_mtime_ns,
        tuple(sorted(item.name for item in path.parent.iterdir())),
    )


def _root(*, rows: int, cols: int) -> StructureBlock:
    return StructureBlock(
        source_ref="body.t0",
        document_part=DocumentPart.BODY,
        section_index=0,
        block_order=0,
        kind=BlockKind.TABLE,
        text="",
        table_rows=rows,
        table_cols=cols,
    )


def _cell(order: int, row: int, col: int, text: str) -> StructureBlock:
    return StructureBlock(
        source_ref=f"body.t0.r{row}.c{col}.p0",
        document_part=DocumentPart.BODY,
        section_index=0,
        block_order=order,
        kind=BlockKind.PARAGRAPH,
        text=text,
        table_path=(row, col),
    )


def _span(block: StructureBlock, *, page_only: bool = False) -> ProtocolSourceSpan:
    common = dict(
        source_span_id=f"span:{block.source_ref}",
        snapshot_id=SNAPSHOT,
        source_ref=block.source_ref,
        document_part=DocumentPart.BODY,
        block_order=block.block_order,
        table_path=block.table_path,
        table_row=block.table_path[-2] if block.table_path else None,
        table_col=block.table_path[-1] if block.table_path else None,
        render_artifact_id=RENDER,
        render_page=1,
        alignment_status=AlignmentStatus.ALIGNED,
    )
    if page_only:
        return ProtocolSourceSpan(
            **common,
            precision=SourceLocatorPrecision.PAGE_ONLY,
        )
    text_start = block.block_order
    return ProtocolSourceSpan(
        **common,
        text_start=text_start,
        text_end=text_start + max(1, len(block.text)),
        excerpt=block.text,
        precision=SourceLocatorPrecision.TEXT_RANGE,
    )


def _matrix(
    rows: list[list[str]],
    *,
    cols: int | None = None,
    page_only_refs: set[str] | None = None,
) -> tuple[list[StructureBlock], list[ProtocolSourceSpan]]:
    width = cols or max(len(row) for row in rows)
    blocks = [_root(rows=len(rows), cols=width)]
    order = 1
    for row_index, row in enumerate(rows):
        for col_index, text in enumerate(row):
            if text == "":
                continue
            block = _cell(order, row_index, col_index, text)
            blocks.append(block)
            order += 1
    page_only_refs = page_only_refs or set()
    spans = [
        _span(block, page_only=block.source_ref in page_only_refs)
        for block in blocks
        if block.kind == BlockKind.PARAGRAPH
    ]
    return blocks, spans


def _projection(
    blocks: list[StructureBlock],
    *,
    phase: StudyPhase = StudyPhase.PHASE_III,
    included_refs: set[str] | None = None,
    phase_scopes: dict[str, list[PhaseScope]] | None = None,
) -> PhaseProjection:
    included_refs = included_refs or {
        block.source_ref for block in blocks if block.kind == BlockKind.PARAGRAPH
    }
    phase_scopes = phase_scopes or {}
    projected: list[PhaseApplicabilityBlock] = []
    for block in blocks:
        if block.kind != BlockKind.PARAGRAPH or block.source_ref not in included_refs:
            continue
        projected.append(
            PhaseApplicabilityBlock(
                block_id=f"phase:{block.source_ref}",
                snapshot_id=SNAPSHOT,
                source_ref=block.source_ref,
                source_span_ids=[f"span:{block.source_ref}"],
                granularity=ApplicabilityGranularity.PARAGRAPH,
                source_order=block.block_order,
                text=block.text,
                phase_scopes=phase_scopes.get(block.source_ref, [PhaseScope.SHARED]),
                table_path=block.table_path,
            )
        )
    return PhaseProjection(
        projection_id=f"projection:{phase.value}",
        graph_id="graph:procedure",
        selected_phase=phase,
        blocks=projected,
    )


def _build(
    blocks: list[StructureBlock],
    spans: list[ProtocolSourceSpan],
    projection: PhaseProjection,
):
    return build_required_procedure_catalog(
        blocks,
        phase_projection=projection,
        source_spans=spans,
        frozen_at=FROZEN_AT,
    )


def test_merged_header_like_matrix_keeps_original_visit_text_and_structural_rows():
    blocks, spans = _matrix(
        [
            ["操作项目", "预筛选期", "", "筛选期", "基线期", "治疗期"],
            ["访视", "V0", "V1", "V2", "V3", "V4"],
            ["知情同意", "X", "", "", "", ""],
            ["人口学与病史", "", "", "X", "X", "X"],
            ["实验室检查", "", "", "X", "X", "X"],
        ],
        cols=6,
    )
    catalog = _build(blocks, spans, _projection(blocks))

    assert catalog.study_phase == StudyPhase.PHASE_III
    assert [item.label for item in catalog.items] == [
        "知情同意",
        "人口学与病史",
        "人口学与病史",
        "实验室检查",
        "实验室检查",
    ]
    assert catalog.items[0].visit_instance == "预筛选期 / V0"
    assert all("治疗期" not in (item.visit_instance or "") for item in catalog.items)
    assert all(item.source_span_ids for item in catalog.items)
    assert derive_review_stage(catalog.items[0].visit_instance or "") is not None


def test_display_footnotes_are_removed_without_damaging_scientific_notation():
    blocks, spans = _matrix(
        [
            ["检查项目", "治疗期^2^6", "随访期"],
            ["访视", "V2（基线^2）", "V3"],
            ["胸片（正侧位）^14", "X", ""],
            ["ANC<1.2×10^9/L", "X", ""],
        ],
        cols=3,
    )

    catalog = _build(blocks, spans, _projection(blocks))

    assert [item.label for item in catalog.items] == [
        "胸片（正侧位）",
        "ANC<1.2×10^9/L",
    ]
    assert {item.visit_instance for item in catalog.items} == {"治疗期 / V2（基线）"}


def test_flow_display_footnotes_attach_numbered_note_sources_before_label_cleanup():
    blocks, spans = _matrix(
        [
            ["检查项目", "筛选期", "基线期^2"],
            ["访视", "V1", "V2"],
            ["血生化^3", "X", "X"],
            ["ANC<1.2×10^9/L", "X", ""],
        ],
        cols=3,
    )
    next_order = max(block.block_order for block in blocks) + 1
    blocks.extend(
        [
            StructureBlock(
                source_ref=f"body.p{index}",
                document_part=DocumentPart.BODY,
                section_index=0,
                block_order=next_order + index,
                kind=BlockKind.PARAGRAPH,
                text=text,
                numbering=NumberingRef(
                    num_id=7,
                    level=0,
                    start=1,
                    num_fmt="decimal",
                    lvl_text="%1.",
                ),
            )
            for index, text in enumerate(
                ["签署知情同意", "基线访视合并规则", "血生化应空腹采样"],
                start=1,
            )
        ]
    )
    spans.extend(
        _span(block) for block in blocks if block.source_ref.startswith("body.p")
    )

    catalog = _build(blocks, spans, _projection(blocks))
    baseline_biochemistry = next(
        item
        for item in catalog.items
        if item.label == "血生化" and "基线期" in (item.visit_instance or "")
    )
    screening_biochemistry = next(
        item
        for item in catalog.items
        if item.label == "血生化" and "筛选期" in (item.visit_instance or "")
    )
    scientific_notation = next(
        item for item in catalog.items if item.label == "ANC<1.2×10^9/L"
    )

    assert "span:body.p2" in baseline_biochemistry.source_span_ids
    assert "span:body.p3" in baseline_biochemistry.source_span_ids
    assert "基线访视合并规则" in baseline_biochemistry.source_excerpts
    assert "血生化应空腹采样" in baseline_biochemistry.source_excerpts
    assert "span:body.p2" not in screening_biochemistry.source_span_ids
    assert "span:body.p3" in screening_biochemistry.source_span_ids
    assert all(
        not span_id.startswith("span:body.p")
        for span_id in scientific_notation.source_span_ids
    )


def test_visit_header_note_named_for_one_operation_does_not_pollute_sibling_rows():
    blocks, spans = _matrix(
        [
            ["检查项目", "筛选期", "基线期^2^3"],
            ["访视", "V1", "V2"],
            ["血生化", "X", "X"],
            ["生命体征", "X", "X"],
        ],
        cols=3,
    )
    next_order = max(block.block_order for block in blocks) + 1
    blocks.extend(
        StructureBlock(
            source_ref=f"body.p{index}",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=next_order + index,
            kind=BlockKind.PARAGRAPH,
            text=text,
            numbering=NumberingRef(
                num_id=7,
                level=0,
                start=1,
                num_fmt="decimal",
                lvl_text="%1.",
            ),
        )
        for index, text in enumerate(
            ["签署知情同意", "基线访视合并规则", "血生化应空腹采样"],
            start=1,
        )
    )
    spans.extend(
        _span(block) for block in blocks if block.source_ref.startswith("body.p")
    )

    catalog = _build(blocks, spans, _projection(blocks))
    baseline_biochemistry = next(
        item
        for item in catalog.items
        if item.label == "血生化" and "基线期" in (item.visit_instance or "")
    )
    baseline_vital_signs = next(
        item
        for item in catalog.items
        if item.label == "生命体征" and "基线期" in (item.visit_instance or "")
    )

    assert "span:body.p2" in baseline_biochemistry.source_span_ids
    assert "span:body.p3" in baseline_biochemistry.source_span_ids
    assert "span:body.p2" in baseline_vital_signs.source_span_ids
    assert "span:body.p3" not in baseline_vital_signs.source_span_ids
    assert "血生化应空腹采样" not in baseline_vital_signs.source_excerpts


def test_flow_display_footnotes_stop_before_a_later_numbered_section():
    blocks, spans = _matrix(
        [
            ["检查项目", "筛选期", "基线期^2"],
            ["访视", "V1", "V2"],
            ["血生化^3", "X", "X"],
        ],
        cols=3,
    )
    next_order = max(block.block_order for block in blocks) + 1
    notes = [
        ("body.p1", "签署知情同意", 7),
        ("body.p2", "基线访视合并规则", 7),
        ("body.p3", "血生化应空腹采样", 7),
        ("body.p4", "后续章节中的无关编号条目", 8),
    ]
    blocks.extend(
        StructureBlock(
            source_ref=source_ref,
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=next_order + index,
            kind=BlockKind.PARAGRAPH,
            text=text,
            numbering=NumberingRef(
                num_id=num_id,
                level=0,
                start=1,
                num_fmt="decimal",
                lvl_text="%1.",
            ),
        )
        for index, (source_ref, text, num_id) in enumerate(notes)
    )
    spans.extend(
        _span(block) for block in blocks if block.source_ref.startswith("body.p")
    )

    catalog = _build(blocks, spans, _projection(blocks))
    baseline_biochemistry = next(
        item
        for item in catalog.items
        if item.label == "血生化" and "基线期" in (item.visit_instance or "")
    )

    assert "span:body.p2" in baseline_biochemistry.source_span_ids
    assert "span:body.p3" in baseline_biochemistry.source_span_ids
    assert "span:body.p4" not in baseline_biochemistry.source_span_ids
    assert "后续章节中的无关编号条目" not in baseline_biochemistry.source_excerpts


def test_same_operation_at_screening_and_baseline_is_not_text_deduplicated():
    blocks, spans = _matrix(
        [
            ["检查项目", "筛选期", "基线期", "随访期"],
            ["访视", "V1", "V2", "V3"],
            ["实验室检查", "X", "X", "X"],
            ["合并用药核查", "(X)", "X", ""],
            ["再次入排核查", "", "X", ""],
        ],
        cols=4,
    )
    catalog = _build(blocks, spans, _projection(blocks))

    lab_items = [item for item in catalog.items if item.label == "实验室检查"]
    assert len(lab_items) == 2
    assert {item.visit_instance for item in lab_items} == {
        "筛选期 / V1",
        "基线期 / V2",
    }
    assert len({item.item_id for item in lab_items}) == 2
    assert len([item for item in catalog.items if item.label == "合并用药核查"]) == 2


def test_sparse_visit_rows_do_not_forward_fill_and_randomization_sets_baseline_anchor():
    blocks, spans = _matrix(
        [
            ["项目", "筛选期", "", "治疗期", "", "安全性随访", "提前退出"],
            ["", "筛选", "基线", "", "V3", "V4(EOS)", ""],
            ["访视(周)", "W-4", "", "W0", "W2", "W8", ""],
            ["访视(天)", "D-28", "D≤-7", "D1", "D15", "D57", "末次给药后7天内"],
            ["入排标准审核", "X", "X", "X", "", "", ""],
            ["随机", "", "", "X", "", "", ""],
            ["服用试验用药品", "", "", "X", "", "", ""],
            ["不良事件", "", "", "X", "", "", ""],
            ["实验室检查", "X", "X", "X", "X", "X", "X"],
        ],
        cols=7,
    )

    catalog = _build(blocks, spans, _projection(blocks))

    assert [item.label for item in catalog.items] == [
        "入排标准审核",
        "入排标准审核",
        "入排标准审核",
        "实验室检查",
        "实验室检查",
        "实验室检查",
    ]
    assert [item.visit_instance for item in catalog.items[:3]] == [
        "筛选期 / 筛选 / W-4 / D-28",
        "筛选期 / 基线 / D≤-7",
        "治疗期 / W0 / D1",
    ]
    assert all("V3" not in (item.visit_instance or "") for item in catalog.items)
    assert all("EOS" not in (item.visit_instance or "") for item in catalog.items)
    assert derive_review_stage("双盲治疗期 / V2（基线） / D1") is not None
    assert derive_review_stage("提前退出 / V7(EOS) / W12 / D85") is None


def test_phase_graph_projection_is_the_only_phase_isolation_signal():
    blocks, spans = _matrix(
        [
            ["检查项目", "筛选期", "筛选期", "基线期"],
            ["访视", "II期", "III期", "III期"],
            ["同名检查", "X", "X", "X"],
        ],
        cols=4,
    )
    scopes: dict[str, list[PhaseScope]] = {}
    for block in blocks:
        if block.kind != BlockKind.PARAGRAPH:
            continue
        if ".c0." in block.source_ref:
            scopes[block.source_ref] = [PhaseScope.SHARED]
        elif ".c1." in block.source_ref:
            scopes[block.source_ref] = [PhaseScope.PHASE_II]
        else:
            scopes[block.source_ref] = [PhaseScope.PHASE_III]
    graph_blocks = [
        PhaseApplicabilityBlock(
            block_id=f"phase:{block.source_ref}",
            snapshot_id=SNAPSHOT,
            source_ref=block.source_ref,
            source_span_ids=[f"span:{block.source_ref}"],
            granularity=ApplicabilityGranularity.PARAGRAPH,
            source_order=block.block_order,
            text=block.text,
            phase_scopes=scopes[block.source_ref],
            table_path=block.table_path,
        )
        for block in blocks
        if block.kind == BlockKind.PARAGRAPH
    ]
    graph = PhaseApplicabilityGraph(
        graph_id="graph:procedure",
        snapshot_id=SNAPSHOT,
        blocks=graph_blocks,
        detected_phase_scopes=[
            PhaseScope.PHASE_II,
            PhaseScope.PHASE_III,
            PhaseScope.SHARED,
        ],
    )

    catalog = build_required_procedure_catalog(
        blocks,
        phase_graph=graph,
        selected_phase=StudyPhase.PHASE_III,
        source_spans=spans,
        frozen_at=FROZEN_AT,
    )
    assert len(catalog.items) == 2
    assert {item.visit_instance for item in catalog.items} == {
        "筛选期 / III期",
        "基线期 / III期",
    }
    assert all(" / II期" not in item.visit_instance for item in catalog.items)


@pytest.mark.parametrize(
    "mutation, expected_code",
    [
        ("empty", "flow_table_empty"),
        ("placeholder", "operation_placeholder"),
        ("unresolved_visit", "visit_unresolved"),
        ("degraded_source", "source_coverage_missing"),
    ],
)
def test_structural_flow_failures_block_catalog(mutation: str, expected_code: str):
    rows = [
        ["检查项目", "筛选期", "基线期", "治疗期"],
        ["访视", "V1", "V2", "V3"],
        ["实验室检查", "X", "X", "X"],
    ]
    if mutation == "empty":
        rows = [
            ["检查项目", "筛选期", "基线期", "治疗期"],
            ["访视", "V1", "V2", "V3"],
            ["实验室检查", "", "", "X"],
        ]
    elif mutation == "placeholder":
        rows[2][0] = "待核对"
    elif mutation == "unresolved_visit":
        rows[0][1] = "访视一"
    blocks, spans = _matrix(rows, cols=4)
    if mutation == "degraded_source":
        for degraded in tuple(
            span
            for span in spans
            if "r0.c2" in span.source_ref or "r1.c2" in span.source_ref
        ):
            spans[spans.index(degraded)] = degraded.model_copy(
                update={
                    "alignment_status": AlignmentStatus.DEGRADED,
                    "degradation_reason": "插值页提示",
                }
            )
    with pytest.raises(ProcedureCatalogError) as exc_info:
        _build(blocks, spans, _projection(blocks))
    assert exc_info.value.code == expected_code


def test_aligned_page_only_is_formal_but_degraded_page_only_is_not():
    blocks, spans = _matrix(
        [
            ["检查项目", "筛选期", "基线期"],
            ["访视", "V1", "V2"],
            ["体格检查", "X", "X"],
        ],
        cols=3,
        page_only_refs={"body.t0.r1.c2.p0"},
    )
    catalog = _build(blocks, spans, _projection(blocks))
    assert len(catalog.items) == 2

    for page_only in tuple(
        span
        for span in spans
        if span.source_ref.endswith("r0.c2.p0") or span.source_ref.endswith("r1.c2.p0")
    ):
        spans[spans.index(page_only)] = page_only.model_copy(
            update={
                "alignment_status": AlignmentStatus.DEGRADED,
                "degradation_reason": "仅作页面提示",
            }
        )
    with pytest.raises(ProcedureCatalogError, match="source_coverage_missing"):
        _build(blocks, spans, _projection(blocks))


def test_duplicate_aligned_page_only_is_not_formal_source_coverage():
    blocks, spans = _matrix(
        [
            ["检查项目", "筛选期", "基线期"],
            ["访视", "V1", "V2"],
            ["体格检查", "X", "X"],
        ],
        cols=3,
        page_only_refs={
            "body.t0.r0.c1.p0",
            "body.t0.r0.c2.p0",
            "body.t0.r1.c1.p0",
            "body.t0.r1.c2.p0",
        },
    )

    with pytest.raises(ProcedureCatalogError, match="source_coverage_missing"):
        _build(blocks, spans, _projection(blocks))


@pytest.mark.parametrize(
    "label,path,selected_phase,expected_root,expected_parent_counts,expected_stage_counts,expected_counts",
    REAL_PROCEDURE_PROTOCOLS,
)
def test_real_protocol_required_procedure_catalog_is_read_only_and_phase_isolated(
    label: str,
    path: Path,
    selected_phase: StudyPhase,
    expected_root: str,
    expected_parent_counts: tuple[int, int],
    expected_stage_counts: dict[str, int],
    expected_counts: dict[str, int],
    tmp_path: Path,
) -> None:
    """Exercise the actual render/alignment/phase/catalog chain, not snapshots."""

    if not path.is_file():
        pytest.skip(f"真实方案文件缺失：{path}")
    before = _source_snapshot(path)
    artifact = register_source_artifact(
        path,
        source_artifact_id=f"slice3-procedure-{label}",
        storage_root=tmp_path,
    )
    extraction = extract_docx_structure(
        path,
        snapshot_id=f"slice3-procedure-{label}-snapshot",
        source_artifact=artifact,
        output_dir=tmp_path,
    )
    rendered = render_to_pdf(path, tmp_path / "rendered", source_artifact=artifact)
    assert rendered.status.value == "succeeded", rendered.render_error
    assert rendered.pdf_path is not None
    page_texts = pdf_page_texts(rendered.pdf_path)
    aligned = align_blocks(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
        render_artifact_id=f"slice3-procedure-{label}-render",
        page_texts=page_texts,
    )
    graph = build_phase_applicability_graph(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
        source_span_ids={
            span.source_ref: span.source_span_id for span in aligned.spans
        },
    ).graph
    projection = project_single_phase(graph, selected_phase)
    parent_catalog = freeze_official_parent_rules(
        build_section_index(extraction.blocks, graph, aligned.spans),
        selected_phase,
        frozen_at=FROZEN_AT,
    )
    catalog = build_required_procedure_catalog(
        extraction.blocks,
        phase_projection=projection,
        source_spans=aligned.spans,
        frozen_at=FROZEN_AT,
    )

    if label == "CMS-D001":
        scoring_items = [
            item
            for item in catalog.items
            if item.label in {"PASI评分", "PGA评分", "BSA评分", "DLQI评分"}
            and item.visit_instance == "治疗期 / W0 / D1 / -"
        ]
        assert len(scoring_items) == 4
        assert all(
            "不良事件于D1启动给药后开始记录"
            not in " ".join(item.source_excerpts)
            for item in scoring_items
        )

    assert Counter(item.visit_instance for item in catalog.items) == expected_counts
    assert all(item.review_stage is not None for item in catalog.items)
    assert (
        Counter(item.review_stage.value for item in catalog.items)
        == expected_stage_counts
    )
    spans_by_id = {span.source_span_id: span for span in aligned.spans}
    for item in (*parent_catalog.items, *catalog.items):
        assert item.source_excerpts
        assert len(item.source_excerpts) == len(item.source_span_ids)
        assert any(excerpt is not None for excerpt in item.source_excerpts)
        blocks_by_ref = {block.source_ref: block for block in extraction.blocks}
        assert all(
            excerpt is None
            or excerpt
            == (
                (
                    blocks_by_ref[spans_by_id[source_span_id].source_ref].text
                    if item.kind == CatalogItemKind.REQUIRED_PROCEDURE
                    else spans_by_id[source_span_id].excerpt
                )
                or spans_by_id[source_span_id].excerpt
            )
            for source_span_id, excerpt in zip(
                item.source_span_ids,
                item.source_excerpts,
                strict=True,
            )
        )

    coverage = build_full_protocol_coverage_manifest(
        extraction.blocks,
        projection,
        graph,
        protocol_version_id=f"{label}:real-direct-upload",
        protocol_document_sha256=before[0],
        snapshot_id=extraction.snapshot.snapshot_id,
        manifest_id=f"manifest:{label}:real-direct-upload",
    )
    control_plan = plan_protocol_control_batches(
        coverage,
        parent_catalog,
        catalog,
    )
    agent_input = ProtocolControlAgentInput.from_batch(control_plan.batches[0])
    prompt = build_protocol_control_agent_prompt(agent_input)
    assert agent_input.known_official_targets
    assert agent_input.known_procedure_targets
    assert all(target.source_excerpts for target in agent_input.known_official_targets)
    assert all(target.source_excerpts for target in agent_input.known_procedure_targets)
    assert agent_input.known_official_targets[0].source_excerpts[0] in prompt

    if label == "CMS-D001":
        ex20 = next(
            target
            for target in agent_input.known_official_targets
            if target.official_code == "EX-20"
        )
        ex20_text = "".join(ex20.source_excerpts)
        assert (
            "丙氨酸转氨酶（ALT）或天冬氨酸转氨酶（AST）或总胆红素≥1.5×ULN" in ex20_text
        )
        assert "经研究者评估如果参与研究将可能对参与者构成不可接受的风险" in ex20_text
        assert "γ-谷氨酰转移酶" not in ex20_text
        assert ex20.source_excerpts[0] in prompt

    formal_ids = formal_source_span_ids(aligned.spans)
    inclusion_count = sum(
        item.official_code.startswith("IN-") for item in parent_catalog.items
    )
    exclusion_count = sum(
        item.official_code.startswith("EX-") for item in parent_catalog.items
    )
    assert (inclusion_count, exclusion_count) == expected_parent_counts
    assert all(set(item.source_span_ids) & formal_ids for item in parent_catalog.items)
    assert all(
        verify_excerpt_against_page(span, page_texts[span.render_page - 1])
        for span in aligned.spans
        if span.source_span_id in formal_ids
        and span.precision == SourceLocatorPrecision.TEXT_RANGE
    )
    item_source_refs = {
        spans_by_id[source_span_id].source_ref
        for item in catalog.items
        for source_span_id in item.source_span_ids
    }
    assert item_source_refs
    table_source_refs = {
        source_ref
        for source_ref in item_source_refs
        if source_ref == expected_root or source_ref.startswith(expected_root + ".")
    }
    note_source_refs = item_source_refs - table_source_refs
    assert table_source_refs
    assert all(
        (block := blocks_by_ref[source_ref]).numbering is not None
        and block.numbering.level == 0
        for source_ref in note_source_refs
    )
    if label == "CMS-D001":
        assert "body.p325" in note_source_refs
    assert not any(source_ref.startswith("body.t6") for source_ref in item_source_refs)
    assert all(
        any(
            spans_by_id[source_span_id].alignment_status == AlignmentStatus.ALIGNED
            and spans_by_id[source_span_id].precision
            == SourceLocatorPrecision.TEXT_RANGE
            for source_span_id in item.source_span_ids
        )
        for item in catalog.items
    )

    labels = [item.label for item in catalog.items]
    assert not any(label.startswith("随机") for label in labels)
    if label == "MG-K10-SAR":
        assert "胸片（正侧位）" in labels
    assert not any("试验用药品" in label for label in labels)
    assert not any("日记卡发放" in label or "日记卡回收" in label for label in labels)
    assert not any("日志卡分发" in label or "日志卡回收" in label for label in labels)
    assert not any(
        "D1" in (item.visit_instance or "")
        and ("不良事件" in item.label or "注射部位反应" in item.label)
        for item in catalog.items
    )
    assert _source_snapshot(path) == before


def test_catalog_ids_hash_and_default_freeze_timestamp_are_stable():
    blocks, spans = _matrix(
        [
            ["检查项目", "筛选期", "基线期"],
            ["访视", "V1", "V2"],
            ["生命体征", "X", "X"],
        ],
        cols=3,
    )
    projection = _projection(blocks)
    first = build_required_procedure_catalog(blocks, projection, spans)
    second = build_required_procedure_catalog(blocks, projection, spans)
    assert first.catalog_id == second.catalog_id
    assert first.catalog_sha256 == second.catalog_sha256
    assert [item.item_id for item in first.items] == [
        item.item_id for item in second.items
    ]
