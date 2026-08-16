"""Focused tests for the deterministic official parent-rule sidecar."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from app.domain.contracts.enums import (
    AlignmentStatus,
    ApplicabilityGranularity,
    DocumentPart,
    PhaseScope,
    SourceLocatorPrecision,
    StudyPhase,
)
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityBlock,
    PhaseApplicabilityGraph,
)
from app.protocols.catalogs import CatalogValidationError, freeze_official_parent_rules
from app.protocols.docx_structure import (
    BlockKind,
    NumberingRef,
    StructureBlock,
    extract_docx_structure,
)
from app.protocols.ingestion import register_source_artifact
from app.protocols.phase_detection import build_phase_applicability_graph
from app.protocols.section_index import (
    SectionIndexError,
    build_section_index,
    formal_source_span_ids,
)


SNAPSHOT = "snapshot-official-parent-slice3"
RENDER = "render-official-parent-slice3"
FROZEN_AT = datetime(2026, 8, 14, tzinfo=timezone.utc)
REAL_PROTOCOLS = (
    (
        "MG-K10-SAR",
        Path(
            "/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/"
            "MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx"
        ),
        StudyPhase.PHASE_III,
        (7, 16),
        ("body.p536", "body.p558"),
    ),
    (
        "CMS-D001",
        Path(
            "/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/"
            "CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx"
        ),
        StudyPhase.PHASE_II,
        (6, 30),
        ("body.p628", "body.p639"),
    ),
)


def _numbering(
    num_id: int,
    abstract_num_id: int,
    *,
    num_fmt: str = "decimal",
    lvl_text: str = "%1)",
    level: int = 0,
    start: int | None = 1,
) -> NumberingRef:
    return NumberingRef(
        num_id=num_id,
        abstract_num_id=abstract_num_id,
        level=level,
        num_fmt=num_fmt,
        lvl_text=lvl_text,
        start=start,
    )


def _block(
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
        style=style,
        numbering=numbering,
    )


def _span(
    block: StructureBlock,
    *,
    locator: str = "text",
    page: int | None = None,
) -> ProtocolSourceSpan:
    common = dict(
        source_span_id=f"span-{block.source_ref}",
        snapshot_id=SNAPSHOT,
        source_ref=block.source_ref,
        document_part=DocumentPart.BODY,
        section_index=0,
        block_order=block.block_order,
        render_artifact_id=RENDER,
        render_page=page or 1,
    )
    if locator == "text":
        start = block.block_order * 100
        return ProtocolSourceSpan(
            **common,
            text_start=start,
            text_end=start + max(1, len(block.text)),
            excerpt=block.text,
            precision=SourceLocatorPrecision.TEXT_RANGE,
            alignment_status=AlignmentStatus.ALIGNED,
        )
    if locator == "page":
        return ProtocolSourceSpan(
            **common,
            precision=SourceLocatorPrecision.PAGE_ONLY,
            alignment_status=AlignmentStatus.ALIGNED,
        )
    if locator == "degraded":
        return ProtocolSourceSpan(
            **common,
            precision=SourceLocatorPrecision.PAGE_ONLY,
            alignment_status=AlignmentStatus.DEGRADED,
            degradation_reason="synthetic interpolated page hint",
        )
    raise AssertionError(f"unknown locator: {locator}")


def _fixture(
    *,
    numbering_mode: str = "normal",
    phase_overrides: dict[int, tuple[PhaseScope, ...]] | None = None,
    locator_overrides: dict[int, tuple[str, int | None]] | None = None,
    placeholder_order: int | None = None,
) -> tuple[list[StructureBlock], list[ProtocolSourceSpan], PhaseApplicabilityGraph]:
    """Build a generic Word-numbered inclusion/exclusion section.

    The parent list uses decimal ``%1)`` numbering.  Its nested subclause uses
    a separate lower-letter Word list and therefore remains inside its parent
    source range rather than becoming another official parent member.
    """

    if numbering_mode == "gap":
        first_text, second_text = "1) criterion alpha", "3) criterion beta"
    elif numbering_mode == "duplicate":
        first_text, second_text = "1) criterion alpha", "1) criterion beta"
    else:
        first_text, second_text = "criterion alpha", "criterion beta"

    texts = {
        0: "入选标准",
        1: first_text,
        2: "subcondition alpha",
        3: second_text,
        4: "排除标准",
        5: "criterion gamma",
        6: "criterion delta",
        7: "后续章节",
    }
    blocks = [
        _block(0, texts[0], style="Heading 2"),
        _block(1, texts[1], numbering=_numbering(10, 100)),
        _block(2, texts[2], numbering=_numbering(11, 101, num_fmt="lowerLetter", lvl_text="%1)")),
        _block(3, texts[3], numbering=_numbering(10, 100)),
        _block(4, texts[4], style="Heading 2"),
        _block(5, texts[5], numbering=_numbering(20, 200)),
        _block(6, texts[6], numbering=_numbering(20, 200)),
        _block(7, texts[7], style="Heading 2"),
    ]
    if placeholder_order is not None:
        blocks[placeholder_order] = blocks[placeholder_order].model_copy(update={"text": "TODO"})

    phase_overrides = phase_overrides or {}
    spans: list[ProtocolSourceSpan] = []
    graph_blocks: list[PhaseApplicabilityBlock] = []
    locator_overrides = locator_overrides or {}
    for block in blocks:
        locator, page = locator_overrides.get(block.block_order, ("text", None))
        spans.append(_span(block, locator=locator, page=page))
        graph_blocks.append(
            PhaseApplicabilityBlock(
                block_id=f"phase-{block.source_ref}",
                snapshot_id=SNAPSHOT,
                source_ref=block.source_ref,
                source_span_ids=[f"span-{block.source_ref}"],
                granularity=ApplicabilityGranularity.PARAGRAPH,
                source_order=block.block_order,
                text=block.text,
                phase_scopes=list(phase_overrides.get(block.block_order, (PhaseScope.PHASE_III,))),
            )
        )
    graph = PhaseApplicabilityGraph(
        graph_id="graph-official-parent-slice3",
        snapshot_id=SNAPSHOT,
        blocks=graph_blocks,
        detected_phase_scopes=[PhaseScope.PHASE_III],
    )
    return blocks, spans, graph


def _index(
    *,
    numbering_mode: str = "normal",
    phase_overrides: dict[int, tuple[PhaseScope, ...]] | None = None,
    locator_overrides: dict[int, tuple[str, int | None]] | None = None,
    placeholder_order: int | None = None,
):
    blocks, spans, graph = _fixture(
        numbering_mode=numbering_mode,
        phase_overrides=phase_overrides,
        locator_overrides=locator_overrides,
        placeholder_order=placeholder_order,
    )
    return build_section_index(blocks, graph, spans), blocks, spans


def _catalog(**kwargs):
    index, _blocks, _spans = _index(**kwargs)
    return freeze_official_parent_rules(
        index,
        StudyPhase.PHASE_III,
        frozen_at=FROZEN_AT,
    )


def test_official_count_numbering_and_parent_subclause_source_range():
    index, _blocks, _spans = _index()

    assert len(index.inclusion_rules) == 2
    assert len(index.exclusion_rules) == 2
    assert [rule.official_code for rule in index.inclusion_rules] == ["IN-01", "IN-02"]
    assert [rule.official_code for rule in index.exclusion_rules] == ["EX-01", "EX-02"]
    assert index.inclusion_rules[0].source_refs == ("body.p1", "body.p2")
    assert index.inclusion_rules[0].source_span_ids == ("span-body.p1", "span-body.p2")

    catalog = freeze_official_parent_rules(index, StudyPhase.PHASE_III, frozen_at=FROZEN_AT)
    assert catalog.catalog_kind.value == "official_parent_rules"
    assert [item.official_code for item in catalog.items] == ["IN-01", "IN-02", "EX-01", "EX-02"]
    assert len(catalog.items) == 4
    assert catalog.items[0].source_span_ids == ("span-body.p1", "span-body.p2")


def test_top_level_body_section_wins_over_reproduced_table_section():
    blocks, spans, graph = _fixture()
    table_blocks = [
        StructureBlock(
            source_ref="body.t9.r0.c0.p0",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=8,
            kind=BlockKind.PARAGRAPH,
            text="入选标准",
            table_path=(0, 0),
        ),
        StructureBlock(
            source_ref="body.t9.r0.c1.p0",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=9,
            kind=BlockKind.PARAGRAPH,
            text="table criterion alpha",
            numbering=_numbering(30, 300),
            table_path=(0, 1),
        ),
        StructureBlock(
            source_ref="body.t9.r1.c0.p0",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=10,
            kind=BlockKind.PARAGRAPH,
            text="排除标准",
            table_path=(1, 0),
        ),
        StructureBlock(
            source_ref="body.t9.r1.c1.p0",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=11,
            kind=BlockKind.PARAGRAPH,
            text="table criterion beta",
            numbering=_numbering(31, 301),
            table_path=(1, 1),
        ),
    ]
    blocks.extend(table_blocks)
    spans.extend(_span(block) for block in table_blocks)
    graph_blocks = list(graph.blocks)
    graph_blocks.extend(
        PhaseApplicabilityBlock(
            block_id=f"phase-{block.source_ref}",
            snapshot_id=SNAPSHOT,
            source_ref=block.source_ref,
            source_span_ids=[f"span-{block.source_ref}"],
            granularity=ApplicabilityGranularity.PARAGRAPH,
            source_order=block.block_order,
            text=block.text,
            phase_scopes=[PhaseScope.PHASE_III],
            table_path=block.table_path,
        )
        for block in table_blocks
    )
    graph = graph.model_copy(update={"blocks": graph_blocks})

    index = build_section_index(blocks, graph, spans)
    assert len(index.sections) == 1
    assert index.sections[0].inclusion_heading_ref == "body.p0"
    assert index.sections[0].exclusion_heading_ref == "body.p4"


def test_phase_isolation_keeps_selected_rules_and_shared_rules_only():
    blocks = [
        _block(0, "入选标准", style="Heading 2"),
        _block(1, "II期适用标准"),
        _block(2, "criterion phase two alpha", numbering=_numbering(10, 100)),
        _block(3, "criterion phase two beta", numbering=_numbering(10, 100)),
        _block(4, "排除标准", style="Heading 2"),
        _block(5, "II期适用标准"),
        _block(6, "criterion phase two gamma", numbering=_numbering(20, 200)),
        _block(7, "criterion phase two delta", numbering=_numbering(20, 200)),
        _block(8, "后续章节", style="Heading 2"),
    ]
    spans = [_span(block) for block in blocks]
    graph = PhaseApplicabilityGraph(
        graph_id="graph-opposite-phase-slice3",
        snapshot_id=SNAPSHOT,
        blocks=[
            PhaseApplicabilityBlock(
                block_id=f"phase-{block.source_ref}",
                snapshot_id=SNAPSHOT,
                source_ref=block.source_ref,
                source_span_ids=[f"span-{block.source_ref}"],
                granularity=ApplicabilityGranularity.PARAGRAPH,
                source_order=block.block_order,
                text=block.text,
                phase_scopes=[PhaseScope.PHASE_II],
            )
            for block in blocks
        ],
        detected_phase_scopes=[PhaseScope.PHASE_II],
    )
    index = build_section_index(blocks, graph, spans)
    with pytest.raises(CatalogValidationError) as exc_info:
        freeze_official_parent_rules(index, StudyPhase.PHASE_III, frozen_at=FROZEN_AT)
    assert exc_info.value.code in {"wrong_phase", "zero_rules"}


def test_phase_isolation_resets_parent_numbering_for_selected_phase_segment():
    blocks = [
        _block(0, "入选标准", style="Heading 2"),
        _block(1, "II期适用标准"),
        _block(2, "criterion phase two alpha", numbering=_numbering(10, 100)),
        _block(3, "criterion phase two beta", numbering=_numbering(10, 100)),
        _block(4, "III期适用标准"),
        _block(5, "criterion phase three alpha", numbering=_numbering(11, 101)),
        _block(6, "criterion phase three beta", numbering=_numbering(11, 101)),
        _block(7, "排除标准", style="Heading 2"),
        _block(8, "II期和III期共同适用标准"),
        _block(9, "criterion shared gamma", numbering=_numbering(20, 200)),
        _block(10, "criterion shared delta", numbering=_numbering(20, 200)),
        _block(11, "后续章节", style="Heading 2"),
    ]
    spans = [_span(block) for block in blocks]
    graph_blocks = [
        PhaseApplicabilityBlock(
            block_id=f"phase-{block.source_ref}",
            snapshot_id=SNAPSHOT,
            source_ref=block.source_ref,
            source_span_ids=[f"span-{block.source_ref}"],
            granularity=ApplicabilityGranularity.PARAGRAPH,
            source_order=block.block_order,
            text=block.text,
                phase_scopes=[
                    PhaseScope.PHASE_II
                    if block.block_order in {0, 1, 2, 3}
                    else PhaseScope.SHARED
                    if block.block_order in {7, 8, 9, 10, 11}
                    else PhaseScope.PHASE_III
            ],
        )
        for block in blocks
    ]
    graph = PhaseApplicabilityGraph(
        graph_id="graph-phase-segment-slice3",
        snapshot_id=SNAPSHOT,
        blocks=graph_blocks,
        detected_phase_scopes=[PhaseScope.PHASE_II, PhaseScope.PHASE_III, PhaseScope.SHARED],
    )
    index = build_section_index(blocks, graph, spans)
    catalog = freeze_official_parent_rules(index, StudyPhase.PHASE_III, frozen_at=FROZEN_AT)

    assert [item.official_code for item in catalog.items] == ["IN-01", "IN-02", "EX-01", "EX-02"]
    assert all("phase two" not in item.label for item in catalog.items)


def test_unresolved_or_mixed_phase_member_is_rejected():
    blocks = [
        _block(0, "入选标准", style="Heading 2"),
        _block(1, "II期和III期共同适用标准"),
        _block(2, "criterion shared alpha", numbering=_numbering(10, 100)),
        _block(3, "II期 criterion local beta", numbering=_numbering(10, 100)),
        _block(4, "criterion unresolved continuation", numbering=_numbering(10, 100)),
        _block(5, "排除标准", style="Heading 2"),
        _block(6, "criterion shared gamma", numbering=_numbering(20, 200)),
        _block(7, "后续章节", style="Heading 2"),
    ]
    scopes = {
        0: PhaseScope.SHARED,
        1: PhaseScope.SHARED,
        2: PhaseScope.SHARED,
        3: PhaseScope.PHASE_II,
        4: PhaseScope.UNKNOWN,
        5: PhaseScope.SHARED,
        6: PhaseScope.SHARED,
        7: PhaseScope.SHARED,
    }
    spans = [_span(block) for block in blocks]
    graph = PhaseApplicabilityGraph(
        graph_id="graph-unknown-after-local-slice3",
        snapshot_id=SNAPSHOT,
        blocks=[
            PhaseApplicabilityBlock(
                block_id=f"phase-{block.source_ref}",
                snapshot_id=SNAPSHOT,
                source_ref=block.source_ref,
                source_span_ids=[f"span-{block.source_ref}"],
                granularity=ApplicabilityGranularity.PARAGRAPH,
                source_order=block.block_order,
                text=block.text,
                phase_scopes=[scopes[block.block_order]],
            )
            for block in blocks
        ],
        detected_phase_scopes=[PhaseScope.PHASE_II, PhaseScope.SHARED, PhaseScope.UNKNOWN],
    )
    index = build_section_index(blocks, graph, spans)
    with pytest.raises(CatalogValidationError, match="phase_unresolved_or_mixed"):
        freeze_official_parent_rules(index, StudyPhase.PHASE_III, frozen_at=FROZEN_AT)


@pytest.mark.parametrize("numbering_mode", ["gap", "duplicate"])
def test_duplicate_or_non_contiguous_official_numbering_is_rejected(numbering_mode: str):
    with pytest.raises(CatalogValidationError) as exc_info:
        _catalog(numbering_mode=numbering_mode)
    assert exc_info.value.code in {"numbering_duplicate", "numbering_non_contiguous"}
    assert "官方" in str(exc_info.value)


def test_zero_rules_and_placeholder_rules_are_rejected():
    blocks, spans, graph = _fixture()
    empty_blocks = [block for block in blocks if block.block_order in {0, 4, 7}]
    empty_spans = [span for span in spans if span.block_order in {0, 4, 7}]
    empty_graph = graph.model_copy(
        update={
            "blocks": [item for item in graph.blocks if item.source_ref in {block.source_ref for block in empty_blocks}]
        }
    )
    with pytest.raises(SectionIndexError) as exc_info:
        build_section_index(empty_blocks, empty_graph, empty_spans)
    assert exc_info.value.code == "eligibility_sections_missing"

    with pytest.raises(CatalogValidationError) as exc_info:
        _catalog(placeholder_order=1)
    assert exc_info.value.code == "placeholder"


def test_degraded_or_non_unique_page_locators_never_satisfy_source_authority():
    degraded = {order: ("degraded", 9) for order in (1, 2, 3, 5, 6)}
    degraded_index, _blocks, degraded_spans = _index(locator_overrides=degraded)
    degraded_catalog = freeze_official_parent_rules(
        degraded_index, StudyPhase.PHASE_III, frozen_at=FROZEN_AT
    )
    assert degraded_catalog.items
    degraded_item_ids = {
        span_id for item in degraded_catalog.items for span_id in item.source_span_ids
    }
    assert not degraded_item_ids & formal_source_span_ids(degraded_spans)

    duplicate_page = {order: ("page", 9) for order in (1, 2, 3, 5, 6)}
    duplicate_index, _blocks, duplicate_spans = _index(locator_overrides=duplicate_page)
    duplicate_catalog = freeze_official_parent_rules(
        duplicate_index, StudyPhase.PHASE_III, frozen_at=FROZEN_AT
    )
    assert duplicate_catalog.items
    duplicate_item_ids = {
        span_id for item in duplicate_catalog.items for span_id in item.source_span_ids
    }
    assert not duplicate_item_ids & formal_source_span_ids(duplicate_spans)

    # Freezing preserves complete OOXML-backed source ranges; the existing
    # source_coverage publication gate consumes this empty formal set and
    # blocks publication. Missing structure spans still fail here.
    with pytest.raises(CatalogValidationError) as exc_info:
        freeze_official_parent_rules(
            duplicate_index,
            StudyPhase.PHASE_III,
            source_spans=[
                span for span in duplicate_spans if span.source_span_id != "span-body.p1"
            ],
            frozen_at=FROZEN_AT,
        )
    assert exc_info.value.code == "source_span_missing"


def test_catalog_ids_hash_and_default_freeze_timestamp_are_deterministic():
    first = _catalog()
    second = _catalog()
    index, _blocks, _spans = _index()
    default_timestamp_catalog = freeze_official_parent_rules(index, StudyPhase.PHASE_III)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.catalog_id == second.catalog_id
    assert first.catalog_sha256 == second.catalog_sha256
    assert first.frozen_at == FROZEN_AT
    assert default_timestamp_catalog.frozen_at == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert len(first.catalog_sha256) == 64


def _source_snapshot(path: Path) -> tuple[str, int, int, tuple[str, ...]]:
    stat = path.stat()
    return (
        hashlib.sha256(path.read_bytes()).hexdigest(),
        stat.st_size,
        stat.st_mtime_ns,
        tuple(sorted(item.name for item in path.parent.iterdir())),
    )


def _structure_span(block: StructureBlock, snapshot_id: str) -> ProtocolSourceSpan:
    return ProtocolSourceSpan(
        source_span_id=f"structure-{block.source_ref}",
        snapshot_id=snapshot_id,
        source_ref=block.source_ref,
        document_part=block.document_part,
        section_index=block.section_index,
        block_order=block.block_order,
        excerpt=block.text,
        precision=SourceLocatorPrecision.BLOCK,
        alignment_status=AlignmentStatus.UNALIGNED,
        degradation_reason="read-only real fixture uses the OOXML structure channel",
    )


@pytest.mark.parametrize(
    "label,path,selected_phase,expected_counts,expected_headings",
    REAL_PROTOCOLS,
)
def test_real_protocol_parent_catalog_exact_counts_labels_and_order(
    label: str,
    path: Path,
    selected_phase: StudyPhase,
    expected_counts: tuple[int, int],
    expected_headings: tuple[str, str],
    tmp_path: Path,
) -> None:
    if not path.is_file():
        pytest.skip(f"真实方案文件缺失：{path}")

    before = _source_snapshot(path)
    snapshot_id = f"slice3-real-{label}"
    artifact = register_source_artifact(
        path,
        source_artifact_id=snapshot_id,
        storage_root=tmp_path,
    )
    extraction = extract_docx_structure(
        path,
        snapshot_id=snapshot_id,
        source_artifact=artifact,
        output_dir=tmp_path,
    )
    material_blocks = [block for block in extraction.blocks if block.text.strip()]
    spans = [_structure_span(block, snapshot_id) for block in material_blocks]
    span_ids = {block.source_ref: f"structure-{block.source_ref}" for block in material_blocks}
    phase_graph = build_phase_applicability_graph(
        extraction.blocks,
        snapshot_id=snapshot_id,
        source_span_ids=span_ids,
    ).graph
    index = build_section_index(extraction.blocks, phase_graph, spans)
    catalog = freeze_official_parent_rules(
        index,
        selected_phase,
        frozen_at=FROZEN_AT,
    )

    assert len(index.sections) == 1
    section = index.sections[0]
    assert (section.inclusion_heading_ref, section.exclusion_heading_ref) == expected_headings
    inclusion_items = [item for item in catalog.items if item.official_code.startswith("IN-")]
    exclusion_items = [item for item in catalog.items if item.official_code.startswith("EX-")]
    assert (len(inclusion_items), len(exclusion_items)) == expected_counts
    assert [item.official_code for item in inclusion_items] == [
        f"IN-{number:02d}" for number in range(1, expected_counts[0] + 1)
    ]
    assert [item.official_code for item in exclusion_items] == [
        f"EX-{number:02d}" for number in range(1, expected_counts[1] + 1)
    ]

    spans_by_id = {span.source_span_id: span for span in spans}
    blocks_by_ref = {block.source_ref: block for block in extraction.blocks}
    parent_refs = [spans_by_id[item.source_span_ids[0]].source_ref for item in catalog.items]
    assert [item.label for item in catalog.items] == [
        " ".join(blocks_by_ref[source_ref].text.replace("：", ":").split())
        for source_ref in parent_refs
    ]
    assert [blocks_by_ref[source_ref].block_order for source_ref in parent_refs[: expected_counts[0]]] == sorted(
        blocks_by_ref[source_ref].block_order for source_ref in parent_refs[: expected_counts[0]]
    )
    assert [blocks_by_ref[source_ref].block_order for source_ref in parent_refs[expected_counts[0] :]] == sorted(
        blocks_by_ref[source_ref].block_order for source_ref in parent_refs[expected_counts[0] :]
    )
    assert any(len(rule.source_refs) > 1 for rule in section.rules), (
        "真实复杂子条款必须保留在父规则来源范围内"
    )
    assert formal_source_span_ids(spans) == frozenset()
    assert _source_snapshot(path) == before, "真实方案或源目录被目录测试改写"
