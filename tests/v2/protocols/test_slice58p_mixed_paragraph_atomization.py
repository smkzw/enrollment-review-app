"""Slice 5.8p: source-replayable atomization of mixed-phase paragraphs."""

from __future__ import annotations

import pytest

from app.domain.contracts.enums import (
    ApplicabilityGranularity,
    DocumentPart,
    PhaseScope,
    StudyPhase,
)
from app.domain.contracts.protocol_controls import ProtocolStructureUnit
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityBlock,
    PhaseApplicabilityGraph,
    PhaseProjection,
)
from app.protocols.docx_structure import BlockKind, StructureBlock
from app.protocols.full_protocol_coverage import build_full_protocol_coverage_manifest


_SHA = "a" * 64
_SNAPSHOT = "snapshot:slice58p"
_GRAPH = "graph:slice58p"
_PROTOCOL = "protocol:slice58p-v1"
_MIXED_REF = "body.p1"
_MIXED_SPAN = "span:body.p1"


def _paragraph(order: int, source_ref: str, text: str) -> StructureBlock:
    return StructureBlock(
        source_ref=source_ref,
        document_part=DocumentPart.BODY,
        section_index=0,
        block_order=order,
        kind=BlockKind.PARAGRAPH,
        text=text,
    )


def _phase_block(
    block: StructureBlock,
    scopes: list[PhaseScope],
    *,
    span_id: str | None = None,
) -> PhaseApplicabilityBlock:
    return PhaseApplicabilityBlock(
        block_id=f"phase:{block.source_ref}",
        snapshot_id=_SNAPSHOT,
        source_ref=block.source_ref,
        source_span_ids=[span_id or f"span:{block.source_ref}"],
        granularity=ApplicabilityGranularity.PARAGRAPH,
        source_order=block.block_order,
        text=block.text,
        phase_scopes=scopes,
    )


def _inputs(
    *,
    selected_phase: StudyPhase = StudyPhase.PHASE_II,
    text: str | None = None,
    mixed_scope: list[PhaseScope] | None = None,
) -> tuple[list[StructureBlock], PhaseApplicabilityGraph, PhaseProjection]:
    anchor = _paragraph(0, "body.p0", "研究设计与审核安排")
    mixed = _paragraph(
        1,
        _MIXED_REF,
        text
        or (
            "Ⅱ期和Ⅲ期均需在筛选期签署知情同意书并在基线完成"
            "实验室检查；"
            "Ⅱ期参与者在第12周完成主要疗效评估；"
            "Ⅲ期参与者在第16周完成主要疗效评估。"
        ),
    )
    phase_blocks = [
        _phase_block(anchor, [PhaseScope.SHARED]),
        _phase_block(mixed, mixed_scope or [PhaseScope.MIXED], span_id=_MIXED_SPAN),
    ]
    graph = PhaseApplicabilityGraph(
        graph_id=_GRAPH,
        snapshot_id=_SNAPSHOT,
        blocks=phase_blocks,
        detected_phase_scopes=sorted(
            {scope for block in phase_blocks for scope in block.phase_scopes},
            key=lambda scope: scope.value,
        ),
    )
    projection = PhaseProjection(
        projection_id=f"projection:{selected_phase.value}",
        graph_id=_GRAPH,
        selected_phase=selected_phase,
        blocks=[phase_blocks[0]],
    )
    return [anchor, mixed], graph, projection


def _build(**kwargs):
    blocks, graph, projection = _inputs(**kwargs)
    return build_full_protocol_coverage_manifest(
        blocks,
        projection,
        graph,
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        snapshot_id=_SNAPSHOT,
    )


def _mixed_units(manifest) -> list[ProtocolStructureUnit]:
    return [
        unit
        for unit in manifest.units
        if _MIXED_REF in unit.member_source_refs
    ]


def test_mixed_paragraph_preserves_shared_screening_baseline_and_phase_specific_clauses():
    manifest = _build()
    fragments = _mixed_units(manifest)

    assert len(fragments) == 3
    assert [tuple(unit.phase_scopes) for unit in fragments] == [
        (PhaseScope.SHARED,),
        (PhaseScope.PHASE_II,),
        (PhaseScope.PHASE_III,),
    ]
    by_scope = {tuple(unit.phase_scopes): unit for unit in fragments}
    assert "筛选" in by_scope[(PhaseScope.SHARED,)].excerpt
    assert "基线" in by_scope[(PhaseScope.SHARED,)].excerpt
    assert "第12周" in by_scope[(PhaseScope.PHASE_II,)].excerpt
    assert "第16周" in by_scope[(PhaseScope.PHASE_III,)].excerpt
    assert "筛选" not in by_scope[(PhaseScope.PHASE_II,)].excerpt
    assert "基线" not in by_scope[(PhaseScope.PHASE_II,)].excerpt
    assert "筛选" not in by_scope[(PhaseScope.PHASE_III,)].excerpt
    assert "基线" not in by_scope[(PhaseScope.PHASE_III,)].excerpt
    assert "第16周" not in by_scope[(PhaseScope.PHASE_II,)].excerpt
    assert "第12周" not in by_scope[(PhaseScope.PHASE_III,)].excerpt


@pytest.mark.parametrize("selected_phase", [StudyPhase.PHASE_II, StudyPhase.PHASE_III])
def test_atomized_phase_arrangements_keep_selected_phase_metadata(selected_phase):
    manifest = _build(selected_phase=selected_phase)

    assert all(unit.study_phase == selected_phase for unit in manifest.units)
    fragments = _mixed_units(manifest)
    assert {tuple(unit.phase_scopes) for unit in fragments} == {
        (PhaseScope.SHARED,),
        (PhaseScope.PHASE_II,),
        (PhaseScope.PHASE_III,),
    }


def test_atomized_fragments_are_exact_source_replays_with_one_underlying_member():
    blocks, _graph, _projection = _inputs()
    source_text = next(block.text for block in blocks if block.source_ref == _MIXED_REF)
    fragments = _mixed_units(_build())

    assert all(unit.member_source_refs == [_MIXED_REF] for unit in fragments)
    assert all(unit.source_span_ids == [_MIXED_SPAN] for unit in fragments)
    assert all(unit.excerpt in source_text for unit in fragments)
    assert len({member for unit in fragments for member in unit.member_source_refs}) == 1
    assert len({span for unit in fragments for span in unit.source_span_ids}) == 1


def test_atomized_identity_and_order_are_deterministic_without_duplicate_units():
    first = _build()
    second = _build()

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    unit_ids = [unit.structure_unit_id for unit in first.units]
    source_refs = [unit.source_ref for unit in first.units]
    assert len(unit_ids) == len(set(unit_ids))
    assert len(source_refs) == len(set(source_refs))
    assert [unit.source_order for unit in first.units] == sorted(
        unit.source_order for unit in first.units
    )


def test_single_scope_paragraph_is_not_atomized():
    manifest = _build(
        text="筛选期签署知情同意书并在基线完成实验室检查。",
        mixed_scope=[PhaseScope.SHARED],
    )
    units = _mixed_units(manifest)

    assert len(units) == 1
    assert units[0].excerpt == "筛选期签署知情同意书并在基线完成实验室检查。"


@pytest.mark.parametrize(
    "text",
    [
        (
            "Ⅲ期参与者接受基于Ⅱ期结果推荐的20 mg、40 mg或安慰剂治疗，"
            "并按研究者判断完成后续访视。"
        ),
        (
            "第1、2周（Ⅱ期安排）、第3、4周（Ⅲ期安排）均完成实验室检查。"
        ),
    ],
)
def test_one_strong_mixed_clause_keeps_ratios_doses_and_visit_lists_intact(text):
    units = _mixed_units(_build(text=text))

    assert len(units) == 1
    assert units[0].source_ref == _MIXED_REF
    assert tuple(units[0].phase_scopes) == (PhaseScope.MIXED,)
    assert units[0].excerpt == text


def test_parallel_phase_clauses_split_at_explicit_phase_handoff_without_breaking_ratios():
    text = (
        "筛选合格的Ⅱ期参与者按照1:1:1随机接受低、中、高剂量，"
        "Ⅲ期参与者按照2:2:1随机接受试验药低剂量、高剂量或安慰剂。"
    )
    units = _mixed_units(_build(text=text))

    assert len(units) == 2
    assert [tuple(unit.phase_scopes) for unit in units] == [
        (PhaseScope.PHASE_II,),
        (PhaseScope.PHASE_III,),
    ]
    assert "1:1:1" in units[0].excerpt
    assert "2:2:1" in units[1].excerpt
    assert "Ⅲ期" not in units[0].excerpt
    assert "Ⅱ期" not in units[1].excerpt
    assert "".join(unit.excerpt for unit in units) == text


def test_parallel_phase_handoff_allows_repeated_subject_prefix_before_phase_marker():
    text = (
        "筛选合格的Ⅱ期参与者按照1:1:1随机接受低、中、高剂量，"
        "筛选合格的Ⅲ期参与者按照2:2:1随机接受试验药、"
        "基于Ⅱ期结果确定的推荐剂量或安慰剂。"
    )
    units = _mixed_units(_build(text=text))

    assert len(units) == 2
    assert [tuple(unit.phase_scopes) for unit in units] == [
        (PhaseScope.PHASE_II,),
        (PhaseScope.PHASE_III,),
    ]
    assert "1:1:1" in units[0].excerpt
    assert "2:2:1" in units[1].excerpt
    assert "".join(unit.excerpt for unit in units) == text


def test_same_phase_comma_does_not_create_a_false_handoff():
    text = "Ⅱ期参与者完成筛选，Ⅱ期参与者继续完成基线检查。"
    units = _mixed_units(_build(text=text))

    assert len(units) == 1
    assert units[0].excerpt == text


def test_parallel_hba1c_visit_requirements_split_but_causal_cross_phase_sentence_does_not():
    parallel = (
        "糖化血红蛋白Ⅱ期仅在筛选、12周访视时检测，"
        "Ⅲ期仅在筛选、16周、52周访视进行。"
    )
    parallel_units = _mixed_units(_build(text=parallel))
    assert len(parallel_units) == 2
    assert [tuple(unit.phase_scopes) for unit in parallel_units] == [
        (PhaseScope.PHASE_II,),
        (PhaseScope.PHASE_III,),
    ]
    assert "".join(unit.excerpt for unit in parallel_units) == parallel

    causal = (
        "该分析基于累积的II期研究数据，由IDMC提供正式建议："
        "包括能否继续进行Ⅲ期临床研究以及推荐Ⅲ期剂量。"
    )
    causal_units = _mixed_units(_build(text=causal))
    assert len(causal_units) == 1
    assert causal_units[0].excerpt == causal


def test_adjacent_complete_clauses_with_the_same_scope_are_coalesced():
    text = (
        "Ⅱ期参与者完成筛选。"
        "Ⅱ期参与者在第12周完成主要疗效评估；"
        "Ⅲ期参与者在第16周完成主要疗效评估。"
    )
    units = _mixed_units(_build(text=text))

    assert len(units) == 2
    assert [tuple(unit.phase_scopes) for unit in units] == [
        (PhaseScope.PHASE_II,),
        (PhaseScope.PHASE_III,),
    ]
    assert units[0].excerpt == "Ⅱ期参与者完成筛选。Ⅱ期参与者在第12周完成主要疗效评估；"
    assert units[1].excerpt == "Ⅲ期参与者在第16周完成主要疗效评估。"
    assert "".join(unit.excerpt for unit in units) == text


def test_atomized_ranges_replay_leading_and_repeated_strong_separators():
    text = "；；Ⅱ期参与者完成筛选；；Ⅲ期参与者完成基线。"
    units = _mixed_units(_build(text=text))

    assert len(units) == 2
    assert "".join(unit.excerpt for unit in units) == text
    assert all(unit.excerpt.strip("。！？!?；;\n ") for unit in units)
