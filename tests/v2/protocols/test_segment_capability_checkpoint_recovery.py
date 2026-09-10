"""Adversarial coverage for parent-rule segment capability, checkpoint, and recovery.

Independent from planner/merge suites in ``test_parent_rule_semantic_segmentation``.
Synthetic inputs only; no D001/SAR restoration; no implementer self-report acceptance.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

import pytest

from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport
from app.agents.protocol_deconstructor import (
    ProtocolAgentCallError,
    ProtocolAgentResponse,
    ProtocolParentSegmentError,
    _collect_initial_semantic_response,
    _collect_parent_segment,
    _parse_semantic_candidate,
)
from app.domain.contracts.agent_io import (
    ProtocolSemanticDeconstructionCandidate,
    SemanticRule,
)
from app.protocols.parent_rule_semantic_segmentation import (
    ParentRuleSegment,
    clamp_parent_segment_concurrency,
)
from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture
from tests.v2.protocols.test_protocol_deconstructor_adapter_slice3 import (
    CompactFakeTransport,
    MemoryBatchCache,
    _semantic_candidate,
)

ROOT = Path(__file__).resolve().parents[3]
TRANSPORT_MODULE = ROOT / "app" / "agents" / "protocol_semantic_transport.py"
DECONSTRUCTOR_MODULE = ROOT / "app" / "agents" / "protocol_deconstructor.py"
EXECUTOR_MODULE = ROOT / "app" / "services" / "protocol_deconstruction_executor.py"
SEGMENTATION_MODULE = ROOT / "app" / "protocols" / "parent_rule_semantic_segmentation.py"

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


def _segmented_collection_input():
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


def _segment_candidate(
    *,
    base_candidate: ProtocolSemanticDeconstructionCandidate,
    base_rule: SemanticRule,
    body_id: str,
    body: str,
    official_code: str,
) -> ProtocolSemanticDeconstructionCandidate:
    component = base_rule.components[0].model_copy(
        update={"source_span_ids": [body_id], "source_excerpts": [body]},
        deep=True,
    )
    return base_candidate.model_copy(
        update={
            "candidate_id": f"segment-candidate:{body_id}",
            "created_by_agent_call_id": f"segment-call:{body_id}",
            "proposed_rules": [
                base_rule.model_copy(
                    update={"official_code": official_code, "components": [component]}
                )
            ],
        },
        deep=True,
    )


def _payload_from_segment_prompt(prompt: str) -> dict:
    """Non-compact segment prompts may append prose after the JSON payload."""

    tail = prompt.split("输入：", 1)[1].strip()
    payload, _end = json.JSONDecoder().raw_decode(tail)
    return payload


def _enable_segmentation_config(monkeypatch, *, max_concurrency: int = 2) -> None:
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENTATION_ENABLED", True)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_SOFT_INPUT_TOKENS", 1)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_MAX_UNITS_PER_SEGMENT", 1)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_SOFT_TOKENS", 0)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_MIN_SOURCE_SPANS", 4)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_MIN_OBLIGATIONS", 3)
    monkeypatch.setattr("app.config.DECONSTRUCT_PARENT_SEGMENT_MAX_CONCURRENCY", max_concurrency)


def test_glm_transport_declares_segmentation_independent_from_compact_wire():
    glm = DeepSeekProtocolAgentTransport(
        client=object(),
        backend="zhipu-coding-plan",
        model="glm-5.3-flash",
        api_key="test-key",
    )
    assert glm.uses_compact_wire_contract is False
    assert glm.supports_parent_rule_segmentation is True


def test_glm_style_transport_enters_parent_segmentation_path(monkeypatch):
    source_input, parent, base_candidate = _segmented_collection_input()
    base_rule = next(
        rule for rule in base_candidate.proposed_rules if rule.official_code == parent.official_code
    )
    _enable_segmentation_config(monkeypatch)

    class GlmSegmentTransport:
        supports_parent_rule_segmentation = True
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return f"glm-adversarial:{output_kind}"

        def start(self, *, prompt, output_kind="semantic_candidate"):
            payload = _payload_from_segment_prompt(prompt)
            assert "兄弟分段" in prompt
            body_id = payload["allowed_source_span_ids"][-1]
            body = next(
                item["text"]
                for item in payload["source_materials"]
                if item["source_span_id"] == body_id
            )
            candidate = _segment_candidate(
                base_candidate=base_candidate,
                base_rule=base_rule,
                body_id=body_id,
                body=body,
                official_code=parent.official_code or "EX-01",
            )
            return ProtocolAgentResponse(
                session_id=f"glm-session:{body_id}",
                text=candidate.model_dump_json(),
            )

        def continue_session(self, **_kwargs):
            raise AssertionError("valid glm segments must not need repair")

    primary = CompactFakeTransport([])
    response, error = _collect_initial_semantic_response(
        source_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=primary,
        transport_factory=GlmSegmentTransport,
        batch_size=3,
    )

    assert error is None
    assert primary.start_prompts == []
    merged = _parse_semantic_candidate(response.text)
    assert len(merged.proposed_rules[0].components) == 4


def test_non_segment_transport_skips_parent_segmentation(monkeypatch):
    source_input, parent, base_candidate = _segmented_collection_input()
    base_rule = next(
        rule for rule in base_candidate.proposed_rules if rule.official_code == parent.official_code
    )
    _enable_segmentation_config(monkeypatch)
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

    class DeepSeekStyleTransport:
        supports_parent_rule_segmentation = False
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return output_kind

        def start(self, *, prompt, output_kind="semantic_candidate"):
            assert "兄弟分段" not in prompt
            return ProtocolAgentResponse(
                session_id="deepseek-whole",
                text=whole.model_dump_json(),
            )

    transport = DeepSeekStyleTransport()
    response, error = _collect_initial_semantic_response(
        source_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=transport,
        transport_factory=DeepSeekStyleTransport,
        batch_size=3,
    )

    assert error is None
    assert response.session_id == "deepseek-whole"


def test_successful_segment_is_reused_from_checkpoint():
    source_input, parent, base_candidate = _segmented_collection_input()
    base_rule = next(
        rule for rule in base_candidate.proposed_rules if rule.official_code == parent.official_code
    )
    body_id = parent.source_span_ids[0]
    body = parent.source_excerpts[0]
    segment = ParentRuleSegment(
        parent_official_code=parent.official_code or "EX-01",
        segment_id="EX-01#segment-01-of-04",
        source_span_ids=(body_id,),
        body_source_span_ids=(body_id,),
    )
    cache = MemoryBatchCache()
    starts = 0

    class StableTransport:
        supports_parent_rule_segmentation = True
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return f"stable:{output_kind}"

        def start(self, **_kwargs):
            nonlocal starts
            starts += 1
            candidate = _segment_candidate(
                base_candidate=base_candidate,
                base_rule=base_rule,
                body_id=body_id,
                body=body,
                official_code=parent.official_code or "EX-01",
            )
            return ProtocolAgentResponse(
                session_id="checkpoint-session",
                text=candidate.model_dump_json(),
            )

    _collect_parent_segment(
        source_input,
        prompt_template="按正式方案原文进行结构化解构。",
        segment=segment,
        transport_factory=StableTransport,
        batch_cache=cache,
    )
    assert starts == 1
    assert len(cache.items) == 1

    _collect_parent_segment(
        source_input,
        prompt_template="按正式方案原文进行结构化解构。",
        segment=segment,
        transport_factory=StableTransport,
        batch_cache=cache,
    )
    assert starts == 1


def test_only_failed_segment_is_retried_while_successful_segments_reuse_checkpoint(
    monkeypatch,
):
    source_input, parent, base_candidate = _segmented_collection_input()
    base_rule = next(
        rule for rule in base_candidate.proposed_rules if rule.official_code == parent.official_code
    )
    _enable_segmentation_config(monkeypatch)
    cache = MemoryBatchCache()
    calls_by_body: dict[str, int] = {}
    lock = threading.Lock()
    failing_body = "span-body-1"

    class PartialFailureTransport:
        supports_parent_rule_segmentation = True
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return f"partial-failure:{output_kind}"

        def start(self, *, prompt, output_kind="semantic_candidate"):
            payload = _payload_from_segment_prompt(prompt)
            body_id = payload["allowed_source_span_ids"][-1]
            with lock:
                calls_by_body[body_id] = calls_by_body.get(body_id, 0) + 1
            if body_id == failing_body and calls_by_body[body_id] == 1:
                raise ProtocolAgentCallError(
                    "timeout-session",
                    "read timed out",
                    error_code="TRANSPORT_TIMEOUT",
                )
            body = next(
                item["text"]
                for item in payload["source_materials"]
                if item["source_span_id"] == body_id
            )
            candidate = _segment_candidate(
                base_candidate=base_candidate,
                base_rule=base_rule,
                body_id=body_id,
                body=body,
                official_code=parent.official_code or "EX-01",
            )
            return ProtocolAgentResponse(
                session_id=f"session:{body_id}",
                text=candidate.model_dump_json(),
            )

        def continue_session(self, **_kwargs):
            raise AssertionError("valid segments must not need repair")

    primary = CompactFakeTransport([])
    response, error = _collect_initial_semantic_response(
        source_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=primary,
        transport_factory=PartialFailureTransport,
        batch_cache=cache,
        batch_size=3,
    )

    assert error is None
    assert calls_by_body[failing_body] == 2
    for body_id in (f"span-body-{index}" for index in range(2, 5)):
        assert calls_by_body[body_id] == 1
    merged = _parse_semantic_candidate(response.text)
    assert len(merged.proposed_rules[0].components) == 4

    before_retry = dict(calls_by_body)
    response_retry, error_retry = _collect_initial_semantic_response(
        source_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=primary,
        transport_factory=PartialFailureTransport,
        batch_cache=cache,
        batch_size=3,
    )
    assert error_retry is None
    assert calls_by_body == before_retry
    assert _parse_semantic_candidate(response_retry.text) == merged


@pytest.mark.parametrize(
    "drift_field,mutator",
    [
        (
            "prompt_template",
            lambda source_input, template: (
                source_input,
                template + "\n附加说明不得改变分段身份。",
            ),
        ),
        (
            "protocol_file_sha256",
            lambda source_input, template: (
                source_input.model_copy(
                    update={"protocol_file_sha256": source_input.protocol_file_sha256 + "-drift"}
                ),
                template,
            ),
        ),
        (
            "semantic_cache_identity",
            None,
        ),
    ],
)
def test_cache_identity_drift_invalidates_segment_checkpoint(
    drift_field: str,
    mutator,
):
    source_input, parent, base_candidate = _segmented_collection_input()
    base_rule = next(
        rule for rule in base_candidate.proposed_rules if rule.official_code == parent.official_code
    )
    body_id = parent.source_span_ids[0]
    body = parent.source_excerpts[0]
    segment = ParentRuleSegment(
        parent_official_code=parent.official_code or "EX-01",
        segment_id="EX-01#segment-01-of-04",
        source_span_ids=(body_id,),
        body_source_span_ids=(body_id,),
    )
    cache = MemoryBatchCache()
    identity_version = {"value": 1}
    starts = 0

    class DriftAwareTransport:
        supports_parent_rule_segmentation = True
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return f"drift:{identity_version['value']}:{output_kind}"

        def start(self, **_kwargs):
            nonlocal starts
            starts += 1
            candidate = _segment_candidate(
                base_candidate=base_candidate,
                base_rule=base_rule,
                body_id=body_id,
                body=body,
                official_code=parent.official_code or "EX-01",
            )
            return ProtocolAgentResponse(
                session_id="drift-session",
                text=candidate.model_dump_json(),
            )

    template = "按正式方案原文进行结构化解构。"
    _collect_parent_segment(
        source_input,
        prompt_template=template,
        segment=segment,
        transport_factory=DriftAwareTransport,
        batch_cache=cache,
    )
    assert starts == 1

    if drift_field == "semantic_cache_identity":
        identity_version["value"] = 2
        drifted_source_input = source_input
        drifted_template = template
    else:
        drifted_source_input, drifted_template = mutator(source_input, template)

    _collect_parent_segment(
        drifted_source_input,
        prompt_template=drifted_template,
        segment=segment,
        transport_factory=DriftAwareTransport,
        batch_cache=cache,
    )
    assert starts == 2


def test_timeout_is_classified_separately_from_schema_invalid():
    source_input, parent, _base_candidate = _segmented_collection_input()
    body_id = parent.source_span_ids[0]
    segment = ParentRuleSegment(
        parent_official_code=parent.official_code or "EX-01",
        segment_id="EX-01#segment-01-of-04",
        source_span_ids=(body_id,),
        body_source_span_ids=(body_id,),
    )

    class TimeoutTransport:
        supports_parent_rule_segmentation = True
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return output_kind

        def start(self, **_kwargs):
            raise ProtocolAgentCallError(
                "timeout-session",
                "read timed out",
                error_code="TRANSPORT_TIMEOUT",
            )

    with pytest.raises(ProtocolParentSegmentError) as timeout_exc:
        _collect_parent_segment(
            source_input,
            prompt_template="按正式方案原文进行结构化解构。",
            segment=segment,
            transport_factory=TimeoutTransport,
            batch_cache=None,
        )
    assert timeout_exc.value.error_code == "TRANSPORT_TIMEOUT"

    class SchemaTransport:
        supports_parent_rule_segmentation = True
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return output_kind

        def start(self, **_kwargs):
            return ProtocolAgentResponse(session_id="schema-session", text='{"broken":')

        def continue_session(self, **_kwargs):
            raise ProtocolAgentCallError(
                "schema-session",
                "repair failed",
                error_code="SCHEMA_INVALID",
            )

    with pytest.raises(ProtocolParentSegmentError) as schema_exc:
        _collect_parent_segment(
            source_input,
            prompt_template="按正式方案原文进行结构化解构。",
            segment=segment,
            transport_factory=SchemaTransport,
            batch_cache=None,
        )
    assert schema_exc.value.error_code == "SCHEMA_INVALID"


def test_double_timeout_fails_closed_without_publishing_segment():
    source_input, parent, _base_candidate = _segmented_collection_input()
    body_id = parent.source_span_ids[0]
    segment = ParentRuleSegment(
        parent_official_code=parent.official_code or "EX-01",
        segment_id="EX-01#segment-01-of-04",
        source_span_ids=(body_id,),
        body_source_span_ids=(body_id,),
    )
    calls = 0

    class AlwaysTimeoutTransport:
        supports_parent_rule_segmentation = True
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return output_kind

        def start(self, **_kwargs):
            nonlocal calls
            calls += 1
            raise ProtocolAgentCallError(
                "timeout-session",
                "read timed out",
                error_code="TRANSPORT_TIMEOUT",
            )

    with pytest.raises(ProtocolParentSegmentError):
        _collect_parent_segment(
            source_input,
            prompt_template="按正式方案原文进行结构化解构。",
            segment=segment,
            transport_factory=AlwaysTimeoutTransport,
            batch_cache=MemoryBatchCache(),
        )
    assert calls == 2


def test_segment_schema_repair_names_required_body_source_ids():
    source_input, parent, base_candidate = _segmented_collection_input()
    body_id = parent.source_span_ids[0]
    segment = ParentRuleSegment(
        parent_official_code=parent.official_code or "EX-01",
        segment_id="EX-01#segment-01-of-04",
        source_span_ids=(body_id,),
        body_source_span_ids=(body_id,),
    )
    repair_prompts: list[str] = []
    base_rule = next(
        rule
        for rule in base_candidate.proposed_rules
        if rule.official_code == segment.parent_official_code
    )
    repaired_candidate = _segment_candidate(
        base_candidate=base_candidate,
        base_rule=base_rule,
        body_id=body_id,
        body=parent.source_excerpts[0],
        official_code=segment.parent_official_code,
    )

    class RepairTransport:
        supports_parent_rule_segmentation = True
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return output_kind

        def start(self, **_kwargs):
            return ProtocolAgentResponse(session_id="repair-session", text='{"broken":')

        def continue_session(self, *, prompt, **_kwargs):
            repair_prompts.append(prompt)
            return ProtocolAgentResponse(
                session_id="repair-session",
                text=repaired_candidate.model_dump_json(),
            )

    _collect_parent_segment(
        source_input,
        prompt_template="按正式方案原文进行结构化解构。",
        segment=segment,
        transport_factory=RepairTransport,
        batch_cache=None,
    )

    assert repair_prompts
    assert body_id in repair_prompts[0]
    assert "不得只引用父级限定语" in repair_prompts[0]


def test_segment_collection_respects_concurrency_hard_cap(monkeypatch):
    source_input, parent, base_candidate = _segmented_collection_input()
    base_rule = next(
        rule for rule in base_candidate.proposed_rules if rule.official_code == parent.official_code
    )
    _enable_segmentation_config(monkeypatch, max_concurrency=99)

    lock = threading.Lock()
    state = {"active": 0, "peak": 0}

    class ConcurrentTransport:
        supports_parent_rule_segmentation = True
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return f"concurrency:{output_kind}"

        def start(self, *, prompt, output_kind="semantic_candidate"):
            payload = _payload_from_segment_prompt(prompt)
            body_id = payload["allowed_source_span_ids"][-1]
            body = next(
                item["text"]
                for item in payload["source_materials"]
                if item["source_span_id"] == body_id
            )
            with lock:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            time.sleep(0.03)
            with lock:
                state["active"] -= 1
            candidate = _segment_candidate(
                base_candidate=base_candidate,
                base_rule=base_rule,
                body_id=body_id,
                body=body,
                official_code=parent.official_code or "EX-01",
            )
            return ProtocolAgentResponse(
                session_id=f"session:{body_id}",
                text=candidate.model_dump_json(),
            )

    primary = CompactFakeTransport([])
    response, error = _collect_initial_semantic_response(
        source_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=primary,
        transport_factory=ConcurrentTransport,
        batch_size=3,
    )

    assert error is None
    assert state["peak"] <= clamp_parent_segment_concurrency(99)
    assert state["peak"] == 3
    assert len(_parse_semantic_candidate(response.text).proposed_rules[0].components) == 4


def test_partial_segment_failure_does_not_publish_merged_parent(monkeypatch):
    source_input, parent, base_candidate = _segmented_collection_input()
    base_rule = next(
        rule for rule in base_candidate.proposed_rules if rule.official_code == parent.official_code
    )
    _enable_segmentation_config(monkeypatch)
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

    class HardFailTransport:
        supports_parent_rule_segmentation = True
        uses_compact_wire_contract = False

        def semantic_cache_identity(self, *, output_kind):
            return output_kind

        def start(self, **_kwargs):
            raise ProtocolAgentCallError(
                "hard-fail",
                "segment permanently unavailable",
                error_code="SEMANTIC_CALL_FAILED",
            )

    primary = CompactFakeTransport(
        [
            ProtocolAgentResponse(
                session_id="whole-parent-fallback",
                text=whole.model_dump_json(),
            )
        ]
    )
    response, error = _collect_initial_semantic_response(
        source_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=primary,
        transport_factory=HardFailTransport,
        batch_size=3,
    )

    assert error is None
    assert response.session_id == "whole-parent-fallback"
    assert len(primary.start_prompts) == 1


def test_segmentation_recovery_modules_contain_no_project_specific_hardcoding():
    deconstructor = DECONSTRUCTOR_MODULE.read_text(encoding="utf-8")
    helper_match = re.search(
        r"def _parent_segmentation_thresholds\([\s\S]*?\ndef _collect_initial_semantic_response\(",
        deconstructor,
    )
    assert helper_match is not None
    haystacks = [
        TRANSPORT_MODULE.read_text(encoding="utf-8"),
        EXECUTOR_MODULE.read_text(encoding="utf-8"),
        SEGMENTATION_MODULE.read_text(encoding="utf-8"),
        helper_match.group(0),
    ]
    for text in haystacks:
        for literal in _PROJECT_SPECIFIC_LITERALS:
            assert literal not in text, f"found project-specific literal {literal!r}"
