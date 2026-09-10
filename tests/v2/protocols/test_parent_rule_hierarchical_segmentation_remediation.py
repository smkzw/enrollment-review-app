"""Independent hierarchical / frozen planning coverage for parent-rule segmentation.

Remediation-focused cases only. Synthetic samples stay project-neutral. Frozen
catalog inputs are loaded read-only and never rewritten on disk.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domain.contracts.agent_io import (
    ProtocolSemanticDeconstructionCandidate,
    SemanticEvidenceRequirement,
    SemanticRule,
    SemanticRuleComponent,
)
from app.domain.contracts.enums import CatalogItemKind, Comparator, ReviewStage
from app.domain.contracts.normalization import UnresolvedItem
from app.domain.contracts.protocol_ingestion import FrozenCatalogItem
from app.domain.contracts.rules import AtomicExpression, AtomicPredicate
from app.protocols.parent_rule_semantic_segmentation import (
    ParentSegmentationThresholds,
    merge_parent_rule_segments,
    plan_parent_rule_segments,
    validate_segment_source_closure,
)

ROOT = Path(__file__).resolve().parents[3]
SEGMENTATION_MODULE = ROOT / "app" / "protocols" / "parent_rule_semantic_segmentation.py"
DECONSTRUCTOR_MODULE = ROOT / "app" / "agents" / "protocol_deconstructor.py"
CONFIG_MODULE = ROOT / "app" / "config.py"
FROZEN_CATALOG = (
    ROOT
    / "artifacts"
    / "phase5-slice60zo-laboratory-package70-71-dryrun-20260828"
    / "catalogs"
    / "official_parent_rules.json"
)

_PROJECT_SPECIFIC_LITERALS = (
    "D001",
    "SAR",
    "EX-06",
    "EX-09",
    "EX-18",
    "EX-20",
    "EX-22",
    "IN-01",
    "IN-04",
    "ALT",
    "AST",
    "ULN",
    "ECOG",
    "RECIST",
    "CKD-EPI",
    "Nivolumab",
    "Pembrolizumab",
    "阿帕替尼",
    "卡瑞利珠",
    "结核",
    "银屑病",
)


def _thresholds(**overrides) -> ParentSegmentationThresholds:
    base = dict(
        enabled=True,
        soft_input_tokens=1,
        min_source_spans=4,
        min_obligations=3,
        max_concurrency=2,
        segment_soft_tokens=3_500,
        # Structural tests default to one unit per segment so qualifier and
        # source-closure assertions are independent from packing policy.
        max_units_per_segment=1,
    )
    base.update(overrides)
    return ParentSegmentationThresholds(**base)


def _materials(spans: list[tuple[str, str]]):
    return [SimpleNamespace(source_span_id=span_id, text=text) for span_id, text in spans]


def _parent(*, official_code: str, spans: list[tuple[str, str]]) -> FrozenCatalogItem:
    return FrozenCatalogItem(
        item_id=f"parent:{official_code.lower()}",
        kind=CatalogItemKind.PARENT_RULE,
        official_code=official_code,
        label=f"synthetic hierarchical parent {official_code}",
        position=0,
        source_span_ids=tuple(span_id for span_id, _ in spans),
        source_excerpts=tuple(text for _, text in spans),
    )


def _plan(
    spans: list[tuple[str, str]],
    *,
    official_code: str = "PR-HIER",
    **threshold_overrides,
):
    parent = _parent(official_code=official_code, spans=spans)
    thresholds = dict(min_source_spans=min(4, len(spans)))
    thresholds.update(threshold_overrides)
    return plan_parent_rule_segments(
        parent,
        source_materials=_materials(spans),
        token_estimate=10_000,
        thresholds=_thresholds(**thresholds),
    )


def _component(*, title: str, span_ids: list[str], excerpts: list[str]) -> SemanticRuleComponent:
    expression = AtomicExpression(
        kind="predicate",
        predicate=AtomicPredicate(
            predicate_id=f"pred:{title}",
            subject="对象",
            attribute="条件",
            source_term="条件",
            source_clause=excerpts[0],
            comparator=Comparator.EQ,
            value=True,
            unit=None,
        ),
    )
    return SemanticRuleComponent(
        title=title,
        expression=expression,
        exception_expression=None,
        evidence_requirements=[
            SemanticEvidenceRequirement(
                fact_type="synthetic_fact",
                description="synthetic evidence requirement",
                due_stage=ReviewStage.SCREENING,
            )
        ],
        source_span_ids=span_ids,
        source_excerpts=excerpts,
    )


def _candidate(
    *,
    official_code: str,
    components: list[SemanticRuleComponent],
    warnings: list[UnresolvedItem] | None = None,
) -> ProtocolSemanticDeconstructionCandidate:
    return ProtocolSemanticDeconstructionCandidate(
        candidate_id="cand-hier",
        created_by_agent_call_id="call-hier",
        proposed_rules=[SemanticRule(official_code=official_code, components=components)],
        structural_warnings=list(warnings or []),
        unresolved_items=[],
    )


def _load_frozen_parent(official_code: str) -> tuple[FrozenCatalogItem, list[tuple[str, str]]]:
    payload = json.loads(FROZEN_CATALOG.read_text(encoding="utf-8"))
    item = next(entry for entry in payload["items"] if entry["official_code"] == official_code)
    spans = list(zip(item["source_span_ids"], item["source_excerpts"], strict=True))
    parent = FrozenCatalogItem(
        item_id=item["item_id"],
        kind=CatalogItemKind.PARENT_RULE,
        official_code=item["official_code"],
        label=item.get("label") or official_code,
        position=item.get("position") or 0,
        source_span_ids=tuple(item["source_span_ids"]),
        source_excerpts=tuple(item["source_excerpts"]),
    )
    return parent, spans


def test_neutral_hierarchical_note_header_inherits_nested_qualifiers():
    spans = [
        ("span-lead", "须同时满足以下条件："),
        ("span-a", "条件块甲成立；"),
        ("span-b", "条件块乙成立；"),
        ("span-c", "条件块丙成立；"),
        ("span-note", "注："),
        ("span-d", "补充说明丁成立。"),
        ("span-e", "补充说明戊成立。"),
    ]
    plan = _plan(spans, official_code="PR-NOTE", segment_soft_tokens=0)

    assert plan is not None
    assert len(plan.segments) == 5
    assert [segment.body_source_span_ids for segment in plan.segments] == [
        ("span-a",),
        ("span-b",),
        ("span-c",),
        ("span-d",),
        ("span-e",),
    ]
    assert all(segment.source_span_ids[0] == "span-lead" for segment in plan.segments)
    assert plan.segments[0].source_span_ids == ("span-lead", "span-a")
    assert plan.segments[3].source_span_ids == ("span-lead", "span-note", "span-d")
    assert plan.segments[4].source_span_ids == ("span-lead", "span-note", "span-e")
    assert all("span-note" not in segment.body_source_span_ids for segment in plan.segments)


def test_neutral_small_batch_packing_keeps_identical_qualifier_stack():
    spans = [
        ("span-lead", "须同时满足以下条件："),
        ("span-1", "短项一成立；"),
        ("span-2", "短项二成立；"),
        ("span-3", "短项三成立；"),
        ("span-note", "注："),
        ("span-4", "短注四成立。"),
        ("span-5", "短注五成立。"),
        ("span-6", "短注六成立。"),
    ]
    packed = _plan(
        spans,
        official_code="PR-PACK",
        segment_soft_tokens=50,
        max_units_per_segment=3,
    )
    assert packed is not None
    assert len(packed.segments) >= 2
    for segment in packed.segments:
        bodies = segment.body_source_span_ids
        if any(body in {"span-1", "span-2", "span-3"} for body in bodies):
            assert "span-note" not in segment.source_span_ids
            assert all(body in {"span-1", "span-2", "span-3"} for body in bodies)
        else:
            assert segment.source_span_ids[:2] == ("span-lead", "span-note")
            assert all(body in {"span-4", "span-5", "span-6"} for body in bodies)


def test_abnormal_punctuation_variants_still_plan_or_fail_closed():
    mixed = [
        ("span-lead", "Meet all of the following:"),
        ("span-1", "项一（alias one）成立；"),
        ("span-2", "项二【bracket】成立；"),
        ("span-3", "项三成立；"),
        ("span-4", "项四成立；"),
    ]
    plan = _plan(mixed, official_code="PR-PUNCT", segment_soft_tokens=0)
    assert plan is not None
    assert len(plan.segments) == 4
    assert all(segment.source_span_ids[0] == "span-lead" for segment in plan.segments)

    open_scope = [
        ("span-lead", "须满足："),
        ("span-1", "项一成立；"),
        ("span-2", "项二成立；"),
        ("span-3", "项三（未闭合别名"),
        ("span-4", "项四是新的并列项；"),
    ]
    assert _plan(open_scope, official_code="PR-OPEN") is None

    binder = [
        ("span-lead", "须满足："),
        ("span-1", "项一成立；"),
        ("span-2", "并且项二成立；"),
        ("span-3", "项三成立；"),
        ("span-4", "项四成立；"),
    ]
    assert _plan(binder, official_code="PR-BIND2") is None


def test_colon_list_items_without_terminators_are_closed_units():
    spans = [
        ("span-lead", "筛选时存在以下异常："),
        ("span-1", "指标甲＜1"),
        ("span-2", "指标乙＜2"),
        ("span-3", "指标丙＜3"),
        ("span-4", "指标丁（Alias Delta，AD）≤4（使用公开公式，Public Formula，PF，详见附录）；"),
        ("span-5", "指标戊≥5；"),
    ]
    plan = _plan(spans, official_code="PR-LAB", segment_soft_tokens=0, min_obligations=3)
    assert plan is not None
    assert len(plan.segments) == 5
    assert [segment.body_source_span_ids for segment in plan.segments] == [
        ("span-1",),
        ("span-2",),
        ("span-3",),
        ("span-4",),
        ("span-5",),
    ]


def test_lawful_continuation_can_close_open_paren_across_spans():
    spans = [
        ("span-lead", "须满足："),
        ("span-1", "项一成立；"),
        ("span-2", "项二成立；"),
        ("span-3", "项三（Alias"),
        ("span-3b", " continued）成立；"),
        ("span-4", "项四成立；"),
    ]
    plan = _plan(spans, official_code="PR-CONT-OK", segment_soft_tokens=0, min_source_spans=5)
    assert plan is not None
    assert ("span-3", "span-3b") in [
        segment.body_source_span_ids for segment in plan.segments
    ]


def test_nested_qualifier_source_closure_and_merge():
    spans = [
        ("span-lead", "须同时满足以下条件："),
        ("span-a", "条件块甲成立；"),
        ("span-b", "条件块乙成立；"),
        ("span-c", "条件块丙成立；"),
        ("span-note", "注："),
        ("span-d", "补充说明丁成立。"),
        ("span-e", "补充说明戊成立。"),
    ]
    plan = _plan(spans, official_code="EX-88", segment_soft_tokens=0)
    assert plan is not None
    nested = next(
        segment for segment in plan.segments if segment.body_source_span_ids == ("span-d",)
    )
    assert nested.source_span_ids == ("span-lead", "span-note", "span-d")

    ok = _candidate(
        official_code="EX-88",
        components=[
            _component(
                title="nested-d",
                span_ids=list(nested.source_span_ids),
                excerpts=["须同时满足以下条件：", "注：", "补充说明丁成立。"],
            )
        ],
    )
    validate_segment_source_closure(ok, nested)

    escaped = _candidate(
        official_code="EX-88",
        components=[
            _component(
                title="escape",
                span_ids=["span-lead", "span-note", "span-d", "span-a"],
                excerpts=["须同时满足以下条件：", "注：", "补充说明丁成立。", "条件块甲成立；"],
            )
        ],
    )
    with pytest.raises(ValueError, match="闭包之外"):
        validate_segment_source_closure(escaped, nested)

    segment_candidates = []
    for segment in plan.segments:
        body_id = segment.body_source_span_ids[0]
        segment_candidates.append(
            _candidate(
                official_code="EX-88",
                components=[
                    _component(
                        title=body_id,
                        span_ids=list(segment.source_span_ids),
                        excerpts=[
                            next(text for span_id, text in spans if span_id == source_id)
                            for source_id in segment.source_span_ids
                        ],
                    )
                ],
            )
        )
    merged = merge_parent_rule_segments(
        segment_candidates,
        plan=plan,
        candidate_id="final-hier",
        agent_call_id="final-hier-call",
    )
    assert merged.candidate_id == "final-hier"
    assert [component.title for component in merged.proposed_rules[0].components] == [
        "span-a",
        "span-b",
        "span-c",
        "span-d",
        "span-e",
    ]


def test_readonly_frozen_ex09_plans_with_nested_note_inheritance():
    parent, spans = _load_frozen_parent("EX-09")
    before = FROZEN_CATALOG.read_bytes()
    plan = plan_parent_rule_segments(
        parent,
        source_materials=_materials(spans),
        token_estimate=10_000,
        thresholds=_thresholds(
            min_source_spans=4,
            min_obligations=3,
            max_units_per_segment=3,
        ),
    )
    after = FROZEN_CATALOG.read_bytes()

    assert before == after
    assert plan is not None
    assert len(plan.segments) == 3
    lead = next(span_id for span_id, _ in spans if span_id.endswith("body.p649"))
    note = next(span_id for span_id, _ in spans if span_id.endswith("body.p654"))
    first_bodies = (
        next(span_id for span_id, _ in spans if span_id.endswith("body.p650")),
        next(span_id for span_id, _ in spans if span_id.endswith("body.p651")),
        next(span_id for span_id, _ in spans if span_id.endswith("body.p652")),
    )
    remaining_root_body = next(
        span_id for span_id, _ in spans if span_id.endswith("body.p653")
    )
    second_bodies = (
        next(span_id for span_id, _ in spans if span_id.endswith("body.p655")),
        next(span_id for span_id, _ in spans if span_id.endswith("body.p656")),
    )
    assert plan.segments[0].source_span_ids == (lead, *first_bodies)
    assert plan.segments[0].body_source_span_ids == first_bodies
    assert plan.segments[1].source_span_ids == (lead, remaining_root_body)
    assert plan.segments[1].body_source_span_ids == (remaining_root_body,)
    assert plan.segments[2].source_span_ids == (lead, note, *second_bodies)
    assert plan.segments[2].body_source_span_ids == second_bodies
    assert note not in plan.segments[0].body_source_span_ids
    assert note not in plan.segments[1].body_source_span_ids
    assert note not in plan.segments[2].body_source_span_ids


def test_readonly_frozen_ex20_truncated_open_paren_fail_closes():
    parent, spans = _load_frozen_parent("EX-20")
    before = FROZEN_CATALOG.read_bytes()
    plan = plan_parent_rule_segments(
        parent,
        source_materials=_materials(spans),
        token_estimate=10_000,
        thresholds=_thresholds(min_source_spans=4, min_obligations=3),
    )
    after = FROZEN_CATALOG.read_bytes()

    assert before == after
    truncated = next(text for span_id, text in spans if span_id.endswith("body.p681"))
    assert "（" in truncated and truncated.count("（") != truncated.count("）")
    assert plan is None


def test_readonly_frozen_ex20_with_in_memory_closed_overlay_plans():
    """Positive EX-20-like path without rewriting the frozen catalog on disk."""

    parent, spans = _load_frozen_parent("EX-20")
    closed_p681 = (
        "估算的肾小球滤过率（estimated Glomerular filtration rate，eGFR）"
        "≤60mL/min/1.73 m^2（使用慢性肾脏病流行病学协作方程，"
        "Chronic Kidney Disease Epidemiology Collaboration equation，"
        "CKD-EPI，详见附录2）；"
    )
    overlay = [
        (span_id, closed_p681 if span_id.endswith("body.p681") else text)
        for span_id, text in spans
    ]
    overlay_parent = parent.model_copy(
        update={"source_excerpts": tuple(text for _, text in overlay)}
    )
    before = FROZEN_CATALOG.read_bytes()
    plan = plan_parent_rule_segments(
        overlay_parent,
        source_materials=_materials(overlay),
        token_estimate=10_000,
        thresholds=_thresholds(min_source_spans=4, min_obligations=3, segment_soft_tokens=0),
    )
    after = FROZEN_CATALOG.read_bytes()

    assert before == after
    assert plan is not None
    assert len(plan.segments) == 8
    lead = next(span_id for span_id, _ in overlay if span_id.endswith("body.p675"))
    assert all(segment.source_span_ids[0] == lead for segment in plan.segments)
    assert all(len(segment.body_source_span_ids) == 1 for segment in plan.segments)


@pytest.mark.parametrize(
    "official_code,expected_segments",
    [("IN-04", 3), ("EX-18", 8), ("EX-22", 4)],
)
def test_readonly_frozen_still_plannable_parents(official_code: str, expected_segments: int):
    parent, spans = _load_frozen_parent(official_code)
    plan = plan_parent_rule_segments(
        parent,
        source_materials=_materials(spans),
        token_estimate=10_000,
        thresholds=_thresholds(
            min_source_spans=4,
            min_obligations=3,
            segment_soft_tokens=0,
        ),
    )
    assert plan is not None
    assert len(plan.segments) == expected_segments
    lead = spans[0][0]
    assert all(segment.source_span_ids[0] == lead for segment in plan.segments)
    assert all(lead not in segment.body_source_span_ids for segment in plan.segments)


def test_existing_fail_close_paths_remain_under_hierarchical_planner():
    binders = [
        ("span-1", "1. 条件块1成立。"),
        ("span-2", "并且2. 条件块2成立。"),
        ("span-3", "3. 条件块3成立。"),
        ("span-4", "4. 条件块4成立。"),
    ]
    assert _plan(binders, official_code="PR-OLD-BIND") is None

    unbalanced = [
        ("span-1", "1. 条件块1成立。"),
        ("span-2", "2. 条件块2成立。"),
        ("span-3", "3. 条件块3成立（除外未闭合。"),
        ("span-4", "4. 条件块4成立。"),
    ]
    assert _plan(unbalanced, official_code="PR-OLD-PAREN") is None

    continuation = [
        ("span-1", "条件块1成立，仍在延续"),
        ("span-2", "条件块2成立。"),
        ("span-3", "条件块3成立。"),
        ("span-4", "条件块4成立。"),
    ]
    assert _plan(continuation, official_code="PR-OLD-CONT") is None

    disabled = [
        ("span-lead", "须满足："),
        ("span-1", "1. 条件块1成立。"),
        ("span-2", "2. 条件块2成立。"),
        ("span-3", "3. 条件块3成立。"),
    ]
    assert _plan(disabled, official_code="PR-OLD-OFF", enabled=False) is None


def test_hierarchical_modules_contain_no_project_specific_hardcoding():
    haystacks = [
        SEGMENTATION_MODULE.read_text(encoding="utf-8"),
        CONFIG_MODULE.read_text(encoding="utf-8"),
    ]
    deconstructor = DECONSTRUCTOR_MODULE.read_text(encoding="utf-8")
    helper_match = re.search(
        r"def _parent_segmentation_thresholds\([\s\S]*?\ndef _collect_initial_semantic_response\(",
        deconstructor,
    )
    assert helper_match is not None
    haystacks.append(helper_match.group(0))

    for text in haystacks:
        for literal in _PROJECT_SPECIFIC_LITERALS:
            assert literal not in text, f"found project-specific literal {literal!r}"
