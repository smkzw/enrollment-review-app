"""Independent adversarial coverage for oversized parent-rule segmentation.

These cases are project-neutral synthetic samples. They do not restore D001/SAR
jobs and do not treat implementer self-reports as acceptance evidence.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents.protocol_deconstructor import (
    ProtocolAgentCallError,
    ProtocolAgentResponse,
    _collect_parent_segment,
    _collect_initial_semantic_response,
    _parse_semantic_candidate,
)
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
    ParentRuleSegment,
    ParentSegmentationThresholds,
    clamp_parent_segment_concurrency,
    merge_parent_rule_segments,
    plan_parent_rule_segments,
    validate_segment_source_closure,
)
from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture
from tests.v2.protocols.test_protocol_deconstructor_adapter_slice3 import (
    CompactFakeTransport,
    MemoryBatchCache,
    _semantic_candidate,
    _wire_candidate,
)

ROOT = Path(__file__).resolve().parents[3]
SEGMENTATION_MODULE = ROOT / "app" / "protocols" / "parent_rule_semantic_segmentation.py"
DECONSTRUCTOR_MODULE = ROOT / "app" / "agents" / "protocol_deconstructor.py"
CONFIG_MODULE = ROOT / "app" / "config.py"

_PROJECT_SPECIFIC_LITERALS = (
    "D001",
    "SAR",
    "EX-06",
    "IN-01",
    "ALT",
    "AST",
    "ULN",
    "ECOG",
    "RECIST",
    "Nivolumab",
    "Pembrolizumab",
    "阿帕替尼",
    "卡瑞利珠",
)


def _thresholds(**overrides) -> ParentSegmentationThresholds:
    base = dict(
        enabled=True,
        soft_input_tokens=1,
        min_source_spans=4,
        min_obligations=3,
        max_concurrency=2,
        # Existing planner inheritance / merge suites assert 1:1 bodies unless a
        # packing-specific test overrides these ceilings.
        segment_soft_tokens=0,
        max_units_per_segment=1,
    )
    base.update(overrides)
    return ParentSegmentationThresholds(**base)


def _materials(spans: list[tuple[str, str]]):
    return [
        SimpleNamespace(source_span_id=span_id, text=text)
        for span_id, text in spans
    ]


def _parent(
    *,
    official_code: str,
    spans: list[tuple[str, str]],
) -> FrozenCatalogItem:
    span_ids = tuple(span_id for span_id, _ in spans)
    excerpts = tuple(text for _, text in spans)
    return FrozenCatalogItem(
        item_id=f"parent:{official_code.lower()}",
        kind=CatalogItemKind.PARENT_RULE,
        official_code=official_code,
        label=f"synthetic parent {official_code}",
        position=0,
        source_span_ids=span_ids,
        source_excerpts=excerpts,
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
    candidate_id: str = "cand-seg",
    agent_call_id: str = "call-seg",
    warnings: list[UnresolvedItem] | None = None,
    unresolved: list[UnresolvedItem] | None = None,
) -> ProtocolSemanticDeconstructionCandidate:
    return ProtocolSemanticDeconstructionCandidate(
        candidate_id=candidate_id,
        created_by_agent_call_id=agent_call_id,
        proposed_rules=[
            SemanticRule(official_code=official_code, components=components)
        ],
        structural_warnings=list(warnings or []),
        unresolved_items=list(unresolved or []),
    )


def _closed_blocks(count: int = 4) -> list[tuple[str, str]]:
    return [
        (f"span-body-{index}", f"{index}. 条件块{index}成立。")
        for index in range(1, count + 1)
    ]


def _segmented_collection_input():
    """Reuse gate fixture wiring, but replace clinical body text with neutrals."""

    source_input, draft, _spans = _fixture()
    base_candidate = _semantic_candidate(source_input, draft)
    parent = source_input.parent_rule_catalog.items[1]
    bodies = [f"{index}. 条件块{index}成立。" for index in range(1, 5)]
    span_ids = [f"span-body-{index}" for index in range(1, 5)]
    template = next(
        item for item in source_input.source_materials if item.source_span_id == "span-ex"
    )
    materials = [
        item for item in source_input.source_materials if item.source_span_id != "span-ex"
    ] + [
        template.model_copy(
            update={"source_span_id": span_id, "text": body, "block_order": 20 + index}
        )
        for index, (span_id, body) in enumerate(zip(span_ids, bodies, strict=True))
    ]
    parent = parent.model_copy(
        update={
            "label": "synthetic multi-block parent",
            "source_span_ids": tuple(span_ids),
            "source_excerpts": tuple(bodies),
        }
    )
    source_input = source_input.model_copy(
        update={
            "allowed_source_span_ids": [
                span_id
                for span_id in source_input.allowed_source_span_ids
                if span_id != "span-ex"
            ]
            + span_ids,
            "source_materials": materials,
            "parent_rule_catalog": source_input.parent_rule_catalog.model_copy(
                update={"items": (parent,)}
            ),
        }
    )
    return source_input, parent, base_candidate


def test_clamp_parent_segment_concurrency_defaults_and_hard_cap():
    assert clamp_parent_segment_concurrency(2) == 2
    assert clamp_parent_segment_concurrency(1) == 1
    assert clamp_parent_segment_concurrency(99) == 3
    assert clamp_parent_segment_concurrency(0) == 1
    assert clamp_parent_segment_concurrency(-5) == 1
    assert clamp_parent_segment_concurrency(True) == 2  # type: ignore[arg-type]
    assert clamp_parent_segment_concurrency("2") == 2  # type: ignore[arg-type]
    assert clamp_parent_segment_concurrency(8, hard_cap=3) == 3


def test_planner_inherits_parent_lead_in_on_every_safe_segment():
    spans = [("span-lead", "须同时满足以下条件："), *_closed_blocks(4)]
    parent = _parent(official_code="PR-ALPHA", spans=spans)
    plan = plan_parent_rule_segments(
        parent,
        source_materials=_materials(spans),
        token_estimate=100,
        thresholds=_thresholds(min_source_spans=4),
    )

    assert plan is not None
    assert len(plan.segments) == 4
    assert all(
        segment.source_span_ids[0] == "span-lead" for segment in plan.segments
    )
    assert [segment.body_source_span_ids for segment in plan.segments] == [
        (f"span-body-{index}",) for index in range(1, 5)
    ]
    assert [segment.segment_id for segment in plan.segments] == [
        f"PR-ALPHA#segment-{index:02d}-of-04" for index in range(1, 5)
    ]


@pytest.mark.parametrize(
    "binder_prefix",
    ["且", "并且", "同时", "以及", "或", "或者", "除外", "除非", "但", "但不"],
)
def test_planner_collapses_leading_and_or_exception_binders(binder_prefix: str):
    bodies = _closed_blocks(4)
    bodies[1] = (
        bodies[1][0],
        f"{binder_prefix}{bodies[1][1]}",
    )
    parent = _parent(official_code="PR-BIND", spans=bodies)
    assert (
        plan_parent_rule_segments(
            parent,
            source_materials=_materials(bodies),
            token_estimate=100,
            thresholds=_thresholds(),
        )
        is None
    )


def test_planner_collapses_unbalanced_parenthetical_exception_scope():
    bodies = _closed_blocks(4)
    bodies[2] = (bodies[2][0], "条件块3成立（除外条件未闭合。")
    parent = _parent(official_code="PR-PAREN", spans=bodies)
    assert (
        plan_parent_rule_segments(
            parent,
            source_materials=_materials(bodies),
            token_estimate=100,
            thresholds=_thresholds(),
        )
        is None
    )


def test_planner_collapses_cross_segment_continuation_without_terminator():
    bodies = _closed_blocks(4)
    bodies[0] = (bodies[0][0], "条件块1成立，仍在延续")
    parent = _parent(official_code="PR-CONT", spans=bodies)
    assert (
        plan_parent_rule_segments(
            parent,
            source_materials=_materials(bodies),
            token_estimate=100,
            thresholds=_thresholds(),
        )
        is None
    )


def test_planner_never_splits_single_oversized_span_or_disabled_flag():
    huge = [("span-only", "条件甲成立。" * 5000)]
    parent = _parent(official_code="PR-HUGE", spans=huge)
    assert (
        plan_parent_rule_segments(
            parent,
            source_materials=_materials(huge),
            token_estimate=50_000,
            thresholds=_thresholds(min_source_spans=1, min_obligations=1),
        )
        is None
    )

    spans = _closed_blocks(4)
    enabled_parent = _parent(official_code="PR-OFF", spans=spans)
    assert (
        plan_parent_rule_segments(
            enabled_parent,
            source_materials=_materials(spans),
            token_estimate=100,
            thresholds=_thresholds(enabled=False),
        )
        is None
    )


def test_validate_segment_source_closure_requires_body_and_forbids_escape():
    spans = [("span-lead", "须同时满足以下条件："), *_closed_blocks(3)]
    parent = _parent(official_code="EX-77", spans=spans)
    plan = plan_parent_rule_segments(
        parent,
        source_materials=_materials(spans),
        token_estimate=100,
        thresholds=_thresholds(min_source_spans=4, min_obligations=3),
    )
    assert plan is not None
    segment = plan.segments[0]
    assert segment.source_span_ids == ("span-lead", "span-body-1")

    ok = _candidate(
        official_code="EX-77",
        components=[
            _component(
                title="body-1",
                span_ids=["span-lead", "span-body-1"],
                excerpts=["须同时满足以下条件：", "1. 条件块1成立。"],
            )
        ],
    )
    validate_segment_source_closure(ok, segment)

    escaped = _candidate(
        official_code="EX-77",
        components=[
            _component(
                title="escaped",
                span_ids=["span-lead", "span-body-1", "span-body-2"],
                excerpts=[
                    "须同时满足以下条件：",
                    "1. 条件块1成立。",
                    "2. 条件块2成立。",
                ],
            )
        ],
    )
    with pytest.raises(ValueError, match="闭包之外"):
        validate_segment_source_closure(escaped, segment)

    missing_body = _candidate(
        official_code="EX-77",
        components=[
            _component(
                title="lead-only",
                span_ids=["span-lead"],
                excerpts=["须同时满足以下条件："],
            )
        ],
    )
    with pytest.raises(ValueError, match="未引用其正文来源"):
        validate_segment_source_closure(missing_body, segment)

    warning_escape = _candidate(
        official_code="EX-77",
        components=[
            _component(
                title="body-1",
                span_ids=["span-lead", "span-body-1"],
                excerpts=["须同时满足以下条件：", "1. 条件块1成立。"],
            )
        ],
        warnings=[
            UnresolvedItem(
                code="SYNTHETIC_WARNING",
                affected_scope=["EX-77"],
                source_refs=["span-body-3"],
            )
        ],
    )
    with pytest.raises(ValueError, match="闭包之外"):
        validate_segment_source_closure(warning_escape, segment)


def test_merge_is_deterministic_ordered_and_assigns_system_identity():
    spans = [("span-lead", "须同时满足以下条件："), *_closed_blocks(3)]
    parent = _parent(official_code="EX-78", spans=spans)
    plan = plan_parent_rule_segments(
        parent,
        source_materials=_materials(spans),
        token_estimate=100,
        thresholds=_thresholds(min_source_spans=4, min_obligations=3),
    )
    assert plan is not None

    segment_candidates = []
    for segment in plan.segments:
        body_id = segment.body_source_span_ids[0]
        body_text = next(text for span_id, text in spans if span_id == body_id)
        segment_candidates.append(
            _candidate(
                official_code="EX-78",
                candidate_id=f"temp:{body_id}",
                agent_call_id=f"temp-call:{body_id}",
                components=[
                    _component(
                        title=body_id,
                        span_ids=list(segment.source_span_ids),
                        excerpts=[
                            next(text for span_id, text in spans if span_id == span)
                            for span in segment.source_span_ids
                        ],
                    )
                ],
            )
        )

    merged_a = merge_parent_rule_segments(
        segment_candidates,
        plan=plan,
        candidate_id="final-candidate",
        agent_call_id="final-call",
    )
    merged_b = merge_parent_rule_segments(
        segment_candidates,
        plan=plan,
        candidate_id="final-candidate",
        agent_call_id="final-call",
    )

    assert merged_a.candidate_id == merged_b.candidate_id == "final-candidate"
    assert merged_a.created_by_agent_call_id == merged_b.created_by_agent_call_id == "final-call"
    assert [rule.official_code for rule in merged_a.proposed_rules] == ["EX-78"]
    assert [component.title for component in merged_a.proposed_rules[0].components] == [
        component.title for component in merged_b.proposed_rules[0].components
    ]
    assert [component.title for component in merged_a.proposed_rules[0].components] == [
        segment.body_source_span_ids[0] for segment in plan.segments
    ]

    with pytest.raises(ValueError, match="数量与冻结计划不一致"):
        merge_parent_rule_segments(
            segment_candidates[:1],
            plan=plan,
            candidate_id="final-candidate",
            agent_call_id="final-call",
        )

    wrong_code = list(segment_candidates)
    wrong_code[0] = _candidate(
        official_code="EX-99",
        components=segment_candidates[0].proposed_rules[0].components,
    )
    with pytest.raises(ValueError, match="其他官方父规则"):
        merge_parent_rule_segments(
            wrong_code,
            plan=plan,
            candidate_id="final-candidate",
            agent_call_id="final-call",
        )


def test_collection_respects_concurrency_hard_cap_and_merges_one_parent(monkeypatch):
    source_input, _parent, base_candidate = _segmented_collection_input()
    base_rule = next(
        rule for rule in base_candidate.proposed_rules if rule.official_code == "EX-01"
    )
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENTATION_ENABLED", True)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_SOFT_INPUT_TOKENS", 1)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_MAX_UNITS_PER_SEGMENT", 1)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_SOFT_TOKENS", 0)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_MIN_SOURCE_SPANS", 4)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_MIN_OBLIGATIONS", 3)
    # Config asks for 99; clamp must hard-cap at 3.
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_MAX_CONCURRENCY", 99)

    lock = threading.Lock()
    state = {"active": 0, "peak": 0, "starts": 0, "session_ids": set()}

    class SegmentTransport:
        uses_compact_wire_contract = True

        def configure_output_scope(self, **_scope):
            pass

        def semantic_cache_identity(self, *, output_kind):
            return f"segment-test:{output_kind}"

        def start(self, *, prompt, output_kind="semantic_candidate"):
            assert output_kind == "semantic_candidate"
            payload = json.loads(prompt.split("输入：", 1)[1])
            assert "兄弟分段" in prompt
            span_ids = payload["allowed_source_span_ids"]
            body_id = span_ids[-1]
            body = next(
                item["text"]
                for item in payload["source_materials"]
                if item["source_span_id"] == body_id
            )
            component = base_rule.components[0].model_copy(
                update={"source_span_ids": [body_id], "source_excerpts": [body]},
                deep=True,
            )
            candidate = base_candidate.model_copy(
                update={
                    "candidate_id": "segment-candidate:" + body_id,
                    "created_by_agent_call_id": "segment-call:" + body_id,
                    "proposed_rules": [
                        base_rule.model_copy(update={"components": [component]})
                    ],
                },
                deep=True,
            )
            with lock:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
                state["starts"] += 1
            time.sleep(0.05)
            with lock:
                state["active"] -= 1
                state["session_ids"].add("session:" + body_id)
            return ProtocolAgentResponse(
                session_id="session:" + body_id,
                text=json.dumps(
                    _wire_candidate(candidate, batch_id=payload["batch_id"]),
                    ensure_ascii=False,
                ),
            )

        def continue_session(self, **_kwargs):
            raise AssertionError("valid segments must not need repair")

    primary = CompactFakeTransport([])
    response, error = _collect_initial_semantic_response(
        source_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=primary,
        transport_factory=SegmentTransport,
        batch_size=3,
    )
    merged = _parse_semantic_candidate(response.text)

    assert error is None
    assert state["active"] == 0
    assert state["starts"] == 4
    assert state["peak"] <= 3
    assert state["peak"] == 3
    assert primary.start_prompts == []
    assert [rule.official_code for rule in merged.proposed_rules] == ["EX-01"]
    assert len(merged.proposed_rules[0].components) == 4
    assert {
        component.source_span_ids[0] for component in merged.proposed_rules[0].components
    } == {f"span-body-{index}" for index in range(1, 5)}


def test_segment_failure_falls_back_once_to_whole_parent(monkeypatch):
    source_input, parent, base_candidate = _segmented_collection_input()
    base_rule = next(
        rule for rule in base_candidate.proposed_rules if rule.official_code == "EX-01"
    )
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENTATION_ENABLED", True)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_SOFT_INPUT_TOKENS", 1)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_MAX_UNITS_PER_SEGMENT", 1)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_SOFT_TOKENS", 0)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_MIN_SOURCE_SPANS", 4)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_MIN_OBLIGATIONS", 3)

    class FailingSegmentTransport:
        uses_compact_wire_contract = True

        def configure_output_scope(self, **_scope):
            pass

        def semantic_cache_identity(self, *, output_kind):
            return output_kind

        def start(self, **_kwargs):
            raise RuntimeError("segment unavailable")

    whole_component = base_rule.components[0].model_copy(
        update={
            "source_span_ids": list(parent.source_span_ids),
            "source_excerpts": list(parent.source_excerpts),
        },
        deep=True,
    )
    whole = base_candidate.model_copy(
        update={
            "proposed_rules": [
                base_rule.model_copy(update={"components": [whole_component]}, deep=True)
            ]
        },
        deep=True,
    )
    primary = CompactFakeTransport(
        [
            ProtocolAgentResponse(
                session_id="whole-parent",
                text=json.dumps(_wire_candidate(whole), ensure_ascii=False),
            )
        ]
    )
    response, error = _collect_initial_semantic_response(
        source_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=primary,
        transport_factory=FailingSegmentTransport,
        batch_size=3,
    )

    assert error is None
    assert response.session_id == "whole-parent"
    assert len(primary.start_prompts) == 1


def test_noncompact_glm_style_transport_can_collect_and_checkpoint_one_segment():
    source_input, parent, base_candidate = _segmented_collection_input()
    base_rule = next(
        rule
        for rule in base_candidate.proposed_rules
        if rule.official_code == parent.official_code
    )
    body_id = parent.source_span_ids[0]
    body = parent.source_excerpts[0]
    component = base_rule.components[0].model_copy(
        update={"source_span_ids": [body_id], "source_excerpts": [body]},
        deep=True,
    )
    candidate = base_candidate.model_copy(
        update={
            "candidate_id": "segment-candidate",
            "created_by_agent_call_id": "segment-call",
            "proposed_rules": [
                base_rule.model_copy(update={"components": [component]}, deep=True)
            ],
        },
        deep=True,
    )
    segment = ParentRuleSegment(
        parent_official_code=parent.official_code or "EX-01",
        segment_id="EX-01#segment-01-of-04",
        source_span_ids=(body_id,),
        body_source_span_ids=(body_id,),
    )
    cache = MemoryBatchCache()
    starts = 0

    class GlmStyleTransport:
        supports_parent_rule_segmentation = True
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return f"glm-style:{output_kind}"

        def start(self, *, prompt, output_kind="semantic_candidate"):
            nonlocal starts
            starts += 1
            assert output_kind == "semantic_candidate"
            assert segment.segment_id in prompt
            return ProtocolAgentResponse(
                session_id="glm-segment-session",
                text=candidate.model_dump_json(),
            )

        def continue_session(self, **_kwargs):
            raise AssertionError("valid noncompact output must not need repair")

    result = _collect_parent_segment(
        source_input,
        prompt_template="按冻结方案原文进行结构化解构。",
        segment=segment,
        transport_factory=GlmStyleTransport,
        batch_cache=cache,
    )
    assert result.proposed_rules[0].official_code == parent.official_code
    assert starts == 1
    assert len(cache.items) == 1

    cached = _collect_parent_segment(
        source_input,
        prompt_template="按冻结方案原文进行结构化解构。",
        segment=segment,
        transport_factory=GlmStyleTransport,
        batch_cache=cache,
    )
    assert cached == result
    assert starts == 1


def test_segment_timeout_retries_once_with_same_identity_then_checkpoints():
    source_input, parent, base_candidate = _segmented_collection_input()
    base_rule = next(
        rule
        for rule in base_candidate.proposed_rules
        if rule.official_code == parent.official_code
    )
    body_id = parent.source_span_ids[0]
    body = parent.source_excerpts[0]
    component = base_rule.components[0].model_copy(
        update={"source_span_ids": [body_id], "source_excerpts": [body]},
        deep=True,
    )
    candidate = base_candidate.model_copy(
        update={
            "candidate_id": "retry-candidate",
            "created_by_agent_call_id": "retry-call",
            "proposed_rules": [
                base_rule.model_copy(update={"components": [component]}, deep=True)
            ],
        },
        deep=True,
    )
    segment = ParentRuleSegment(
        parent_official_code=parent.official_code or "EX-01",
        segment_id="EX-01#segment-01-of-04",
        source_span_ids=(body_id,),
        body_source_span_ids=(body_id,),
    )
    calls = 0

    class RetryTransport:
        supports_parent_rule_segmentation = True
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return f"stable-glm:{output_kind}"

        def start(self, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ProtocolAgentCallError(
                    "timed-out-session",
                    "read timed out",
                    error_code="TRANSPORT_TIMEOUT",
                )
            return ProtocolAgentResponse(
                session_id="retry-session",
                text=candidate.model_dump_json(),
            )

        def continue_session(self, **_kwargs):
            raise AssertionError("valid retry output must not need repair")

    cache = MemoryBatchCache()
    result = _collect_parent_segment(
        source_input,
        prompt_template="按冻结方案原文进行结构化解构。",
        segment=segment,
        transport_factory=RetryTransport,
        batch_cache=cache,
    )
    assert result.candidate_id == "retry-candidate"
    assert calls == 2
    assert len(cache.items) == 1



def test_planner_keeps_citation_bracket_truncated_body_as_own_closed_unit():
    """Unmatched square citation brackets are non-logical and must not fail-close."""

    spans = [
        ("span-lead", "正在使用或有以下治疗史："),
        ("span-a", "条件甲成立；"),
        ("span-b", "条件乙成立；"),
        (
            "span-cite",
            "条件丙成立且引用未闭合标注[详见附录X",
        ),
        ("span-d", "条件丁成立；"),
        ("span-e", "条件戊成立。"),
    ]
    parent = _parent(official_code="PR-CITE", spans=spans)
    plan = plan_parent_rule_segments(
        parent,
        source_materials=_materials(spans),
        token_estimate=100,
        thresholds=_thresholds(max_units_per_segment=1, segment_soft_tokens=0),
    )
    assert plan is not None
    bodies = [segment.body_source_span_ids for segment in plan.segments]
    assert ("span-cite",) in bodies
    assert all(segment.source_span_ids[0] == "span-lead" for segment in plan.segments)
    # Must not glue the citation-truncated body onto the next sibling.
    assert ("span-cite", "span-d") not in bodies


def test_planner_still_fail_closes_unmatched_round_parenthesis_scope():
    spans = [
        ("span-lead", "符合以下任一项标准："),
        ("span-a", "条件甲成立；"),
        ("span-b", "条件乙成立；"),
        ("span-open", "条件丙成立（除外条件未闭合"),
        ("span-d", "条件丁成立；"),
        ("span-e", "条件戊成立。"),
    ]
    parent = _parent(official_code="PR-ROUND", spans=spans)
    assert (
        plan_parent_rule_segments(
            parent,
            source_materials=_materials(spans),
            token_estimate=100,
            thresholds=_thresholds(),
        )
        is None
    )


def test_planner_fail_closes_reversed_round_parenthesis_order():
    spans = [
        ("span-lead", "须满足以下条件："),
        ("span-a", "条件甲成立；"),
        ("span-b", "条件乙）说明（；"),
        ("span-c", "条件丙成立；"),
        ("span-d", "条件丁成立；"),
    ]
    parent = _parent(official_code="PR-ROUND-ORDER", spans=spans)

    assert (
        plan_parent_rule_segments(
            parent,
            source_materials=_materials(spans),
            token_estimate=100,
            thresholds=_thresholds(),
        )
        is None
    )


def test_planner_packs_at_most_three_closed_units_per_segment():
    spans = [("span-lead", "须同时满足以下条件："), *_closed_blocks(11)]
    parent = _parent(official_code="PR-PACK", spans=spans)
    plan = plan_parent_rule_segments(
        parent,
        source_materials=_materials(spans),
        token_estimate=100,
        thresholds=_thresholds(
            min_source_spans=4,
            min_obligations=3,
            segment_soft_tokens=50_000,
            max_units_per_segment=3,
        ),
    )
    assert plan is not None
    assert len(plan.segments) == 4
    sizes = [len(segment.body_source_span_ids) for segment in plan.segments]
    assert sizes == [3, 3, 3, 2]
    assert all(segment.source_span_ids[0] == "span-lead" for segment in plan.segments)
    assert all(len(segment.body_source_span_ids) <= 3 for segment in plan.segments)


def test_planner_inherits_long_nested_header_by_structural_order():
    spans = [
        ("span-root", "符合下列任一项长期限定说明且不得依赖标题字数："),
        ("span-a", "条件甲成立；"),
        ("span-b", "条件乙成立；"),
        ("span-c", "条件丙成立；"),
        (
            "span-nested",
            "补充说明：本分支适用于延长后的结构性嵌套限定标题而不依赖短标签：",
        ),
        ("span-d", "补充条件丁成立。"),
        ("span-e", "补充条件戊成立。"),
    ]
    # The nested header above ends with colon and is itself a qualifier; keep it
    # as a single qualifier span with a long label.
    spans[4] = (
        "span-nested",
        "补充说明本分支适用于延长后的结构性嵌套限定标题而不依赖短标签：",
    )
    parent = _parent(official_code="PR-NEST", spans=spans)
    plan = plan_parent_rule_segments(
        parent,
        source_materials=_materials(spans),
        token_estimate=100,
        thresholds=_thresholds(max_units_per_segment=1, segment_soft_tokens=0),
    )
    assert plan is not None
    by_body = {segment.body_source_span_ids: segment.source_span_ids for segment in plan.segments}
    assert by_body[("span-a",)][0] == "span-root"
    assert "span-nested" not in by_body[("span-a",)]
    assert by_body[("span-d",)][:2] == ("span-root", "span-nested")
    assert by_body[("span-e",)][:2] == ("span-root", "span-nested")


def test_planner_replaces_peer_nested_header_under_same_root():
    spans = [
        ("span-root", "符合以下任一项标准："),
        ("span-a", "条件甲成立；"),
        ("span-b", "条件乙成立；"),
        ("span-note-1", "注一："),
        ("span-c", "补充条件丙成立。"),
        ("span-note-2", "注二："),
        ("span-d", "补充条件丁成立。"),
        ("span-e", "补充条件戊成立。"),
    ]
    parent = _parent(official_code="PR-PEER", spans=spans)
    plan = plan_parent_rule_segments(
        parent,
        source_materials=_materials(spans),
        token_estimate=100,
        thresholds=_thresholds(max_units_per_segment=1, segment_soft_tokens=0),
    )
    assert plan is not None
    by_body = {segment.body_source_span_ids: segment.source_span_ids for segment in plan.segments}
    assert by_body[("span-c",)][:2] == ("span-root", "span-note-1")
    assert "span-note-1" not in by_body[("span-d",)]
    assert by_body[("span-d",)][:2] == ("span-root", "span-note-2")
    assert by_body[("span-e",)][:2] == ("span-root", "span-note-2")


def test_planner_plans_frozen_probe_parent_with_citation_noise_readonly():
    """Readonly frozen probe package: citation-truncated body stays plannable."""

    package = (
        ROOT
        / "artifacts"
        / "phase5-acceptance"
        / "20260901"
        / "glm-semantic-route-probe-ex06-20260901"
        / "source-package.json"
    )
    payload = json.loads(package.read_text(encoding="utf-8"))
    catalog_items = payload["source_input"]["parent_rule_catalog"]["items"]
    materials = payload["source_input"]["source_materials"]

    def _has_citation_noise(item: dict) -> bool:
        for excerpt in item.get("source_excerpts") or []:
            text = excerpt or ""
            if text.count("[") != text.count("]") and text.count("（") == text.count("）"):
                return True
        return False

    target = next(
        item
        for item in catalog_items
        if len(item.get("source_span_ids") or ()) >= 8 and _has_citation_noise(item)
    )
    parent = FrozenCatalogItem(
        item_id=target["item_id"],
        kind=CatalogItemKind.PARENT_RULE,
        official_code=target["official_code"],
        label=target.get("label") or target["official_code"],
        position=int(target.get("position") or 0),
        source_span_ids=tuple(target["source_span_ids"]),
        source_excerpts=tuple(target["source_excerpts"]),
    )
    source_materials = [
        SimpleNamespace(source_span_id=item["source_span_id"], text=item["text"])
        for item in materials
    ]
    plan = plan_parent_rule_segments(
        parent,
        source_materials=source_materials,
        token_estimate=100,
        thresholds=_thresholds(
            min_source_spans=4,
            min_obligations=3,
            segment_soft_tokens=50_000,
            max_units_per_segment=3,
        ),
    )
    assert plan is not None
    assert len(plan.segments) == 4
    assert all(len(segment.body_source_span_ids) <= 3 for segment in plan.segments)
    assert sum(len(segment.body_source_span_ids) for segment in plan.segments) == 11
    # Qualifiers only; no body glue across the citation-truncated span.
    body_groups = [segment.body_source_span_ids for segment in plan.segments]
    flat = [span for group in body_groups for span in group]
    assert len(flat) == len(set(flat))


def test_segmentation_modules_contain_no_project_specific_hardcoding():
    haystacks = [
        SEGMENTATION_MODULE.read_text(encoding="utf-8"),
        CONFIG_MODULE.read_text(encoding="utf-8"),
    ]
    # Only the new parent-segment helpers inside the deconstructor are in scope.
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
