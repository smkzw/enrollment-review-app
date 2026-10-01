"""Focused checks for the R1 definition-consumer producer step.

The producer is the one bounded prompt/transport/parse call that turns a frozen
calculation definition into a consumer declaration inside a deep batch run.
These checks pin its fail-closed contract: a batch with a calculation
definition either produces a source-bound declaration or reports the batch for
review; a declaration may only reference frozen candidates, frozen atom
positions and frozen official identities; and no scope completeness is ever
claimed at this layer. They inject deterministic transport doubles and never
call a live model or write a clinical artifact.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.agents.protocol_control_agent_transport import (
    CONTROL_RESPONSE_FORMAT_NAME,
    OpenAICompatibleProtocolControlAgentTransport,
    ProtocolControlAgentCallError,
)
from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentResponse,
    ProtocolControlAgentRunner,
    declare_source_definition_consumers,
)
from app.agents.protocol_control_source_interpretation import (
    SOURCE_DEFINITION_CONSUMER_PROMPT_VERSION,
    SOURCE_DEFINITION_CONSUMER_VERSION,
    SOURCE_INTERPRETATION_VERSION,
    SOURCE_TARGET_REVIEW_VERSION,
    SourceDefinitionAtomConsumer,
    SourceDefinitionConsumerItem,
    SourceDefinitionConsumers,
    SourceTargetReview,
    source_definition_consumers_response_format,
)
from tests.v2.protocols.test_slice58c_control_deconstructor import (
    _batch as _deep_batch,
    _candidate as _wire_candidate,
    _source_inventory,
    _wire as _deep_wire,
)

DEFINITION_QUOTE = "体质指数（BMI）＝体重（kg）÷身高²（m²）"
CONSUMER_EXCERPT = "筛选期访视1必须记录体重与身高"
OFFICIAL_CODE = "IN-01"
OFFICIAL_EXCERPT = "筛选期访视1必须记录体重与身高并计算体质指数"
RULE_COMPONENT_ID = "component-in-01"
PREDICATE_ID = "predicate-in-01"


def _statement(
    *,
    functions: tuple[str, ...] = ("definition", "calculation_input"),
    unit_id: str = "su-method",
) -> SimpleNamespace:
    return SimpleNamespace(
        structure_unit_id=unit_id,
        quoted_text=DEFINITION_QUOTE,
        scope_quote=None,
        force="descriptive",
        decision_functions=list(functions),
        unresolved=[],
    )


def _interpretation(
    *, functions: tuple[str, ...] = ("definition", "calculation_input"),
) -> SimpleNamespace:
    return SimpleNamespace(statements=[_statement(functions=functions)])


def _unit(unit_id: str = "su-method") -> SimpleNamespace:
    return SimpleNamespace(
        structure_unit_id=unit_id,
        source_span_ids=["span:method"],
        excerpt=DEFINITION_QUOTE,
        heading_path=["5.2 计算方法"],
    )


def _candidate(candidate_id: str = "pcc-consumer") -> SimpleNamespace:
    atom = SimpleNamespace(
        source_excerpts=[CONSUMER_EXCERPT], continuing_obligation=None,
    )
    obligation = SimpleNamespace(groups=[SimpleNamespace(atoms=[atom])])
    return SimpleNamespace(
        control_candidate_id=candidate_id,
        semantics=SimpleNamespace(
            title="体重与身高记录",
            applicability_expression=None,
            trigger_expression=None,
            obligation_expression=obligation,
            exception_expression=None,
            repeat_trigger_conditions=[],
        ),
    )


def _output() -> SimpleNamespace:
    return SimpleNamespace(candidates=[_candidate()])


def _batch(official_targets: tuple[SimpleNamespace, ...] = ()) -> SimpleNamespace:
    return SimpleNamespace(
        batch_id="batch-a",
        owned_units=[_unit()],
        context_units=[],
        known_official_targets=list(official_targets),
        known_procedure_targets=[],
    )


def _official_target() -> SimpleNamespace:
    return SimpleNamespace(
        official_code=OFFICIAL_CODE,
        label="筛选测量项",
        source_excerpts=[OFFICIAL_EXCERPT],
    )


def _control_text() -> str:
    return SourceDefinitionConsumers(
        version=SOURCE_DEFINITION_CONSUMER_VERSION,
        items=[SourceDefinitionConsumerItem(
            statement_index=0,
            consumers=[SourceDefinitionAtomConsumer(
                candidate_index=0,
                layer="obligation",
                group_index=0,
                atom_index=0,
                consumer_excerpt=CONSUMER_EXCERPT,
                relation_note=None,
            )],
            unresolved_aspects=[],
        )],
    ).model_dump_json()


def _official_text(
    *,
    official_code: str = OFFICIAL_CODE,
    predicate_id: str = PREDICATE_ID,
) -> str:
    return SourceDefinitionConsumers(
        version=SOURCE_DEFINITION_CONSUMER_VERSION,
        items=[SourceDefinitionConsumerItem(
            statement_index=0,
            consumers=[SourceDefinitionAtomConsumer(
                consumer_kind="official_predicate",
                official_code=official_code,
                rule_component_id=RULE_COMPONENT_ID,
                predicate_id=predicate_id,
                consumer_excerpt=OFFICIAL_EXCERPT,
                relation_note=None,
            )],
            unresolved_aspects=[],
        )],
    ).model_dump_json()


class _ScriptedReader:
    """Transport double for the single bounded producer call."""

    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    def start_source_definition_consumers(self, *, prompt: str):
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, BaseException):
            raise output
        assert isinstance(output, ProtocolControlAgentResponse)
        return output


class _NoStepTransport:
    """A transport without the declaration reader (e.g. an older adapter)."""

    def start(self, *, prompt: str):  # pragma: no cover - must not be reached
        raise AssertionError("producer step must not fall back to the wire call")

    def continue_session(self, *, session_id: str, prompt: str):  # pragma: no cover
        raise AssertionError("producer step must not fall back to the wire call")


def _declare(
    transport: object,
    *,
    interpretation: SimpleNamespace | None = ...,  # type: ignore[assignment]
    batch: SimpleNamespace | None = None,
    identities: dict[str, tuple[tuple[str, str], ...]] | None = None,
):
    attempts: list[object] = []
    result = declare_source_definition_consumers(
        batch if batch is not None else _batch(),
        transport,
        _interpretation() if interpretation is ... else interpretation,
        _output(),
        attempts,
        official_predicate_identities=identities,
    )
    return result, attempts


# -- the step is only asked when a definition exists ------------------------


def test_step_is_skipped_without_a_calculation_definition() -> None:
    reader = _ScriptedReader([])
    result, attempts = _declare(
        reader, interpretation=_interpretation(functions=("action",)),
    )
    assert result == (None, False)
    assert reader.prompts == []
    assert attempts == []


def test_step_is_skipped_without_a_frozen_interpretation() -> None:
    reader = _ScriptedReader([])
    result, attempts = _declare(reader, interpretation=None)
    assert result == (None, False)
    assert reader.prompts == []
    assert attempts == []


# -- a bounded declaration populates the run --------------------------------


def test_valid_control_atom_declaration_populates_the_run() -> None:
    reader = _ScriptedReader([
        ProtocolControlAgentResponse(session_id="session:def", text=_control_text()),
    ])
    (declaration, failed), attempts = _declare(reader)
    assert failed is False
    assert declaration is not None
    assert declaration.items[0].consumers[0].candidate_index == 0
    assert attempts[-1].outcome == "parsed"
    assert attempts[-1].session_id == "session:def"


def test_prompt_exposes_only_frozen_atoms_and_denies_unlisted_identities() -> None:
    reader = _ScriptedReader([
        ProtocolControlAgentResponse(session_id="session:def", text=_control_text()),
    ])
    (declaration, failed), _attempts = _declare(reader)
    assert failed is False
    prompt = reader.prompts[0]
    assert SOURCE_DEFINITION_CONSUMER_PROMPT_VERSION in prompt
    # The definition quote and the consumer atom's own excerpt are the only
    # two anchors the model may combine; the prompt must show both verbatim.
    assert DEFINITION_QUOTE in prompt
    assert CONSUMER_EXCERPT in prompt
    # Without a frozen identity index the prompt must forbid, not invite,
    # an official predicate declaration.
    assert "本批未提供冻结官方条件身份" in prompt


def test_frozen_identity_index_admits_the_declared_official_predicate() -> None:
    reader = _ScriptedReader([
        ProtocolControlAgentResponse(session_id="session:def", text=_official_text()),
    ])
    identities = {OFFICIAL_CODE: ((RULE_COMPONENT_ID, PREDICATE_ID),)}
    (declaration, failed), attempts = _declare(
        reader,
        batch=_batch(official_targets=(_official_target(),)),
        identities=identities,
    )
    assert failed is False
    assert declaration is not None
    consumer = declaration.items[0].consumers[0]
    assert (consumer.rule_component_id, consumer.predicate_id) == (
        RULE_COMPONENT_ID, PREDICATE_ID,
    )
    assert PREDICATE_ID in reader.prompts[0]


# -- every failure stays fail-closed ----------------------------------------


def test_missing_declaration_reader_blocks_the_batch() -> None:
    (declaration, failed), attempts = _declare(_NoStepTransport())
    assert declaration is None
    assert failed is True
    attempt = attempts[-1]
    assert attempt.outcome == "transport_failed"
    assert attempt.error_classes == ["SOURCE_DEFINITION_CONSUMER_TRANSPORT_FAILED"]
    assert attempt.session_id == "definition-consumer-unavailable"


def test_transport_failure_blocks_the_batch() -> None:
    reader = _ScriptedReader([
        ProtocolControlAgentCallError("session:def-error", "connection refused"),
    ])
    (declaration, failed), attempts = _declare(reader)
    assert declaration is None
    assert failed is True
    attempt = attempts[-1]
    assert attempt.outcome == "transport_failed"
    assert attempt.session_id == "session:def-error"
    assert attempt.error_classes == ["SOURCE_DEFINITION_CONSUMER_INVALID"]


def test_unparsable_output_never_becomes_a_record() -> None:
    reader = _ScriptedReader([
        ProtocolControlAgentResponse(session_id="session:def", text="显然不是JSON"),
    ])
    (declaration, failed), attempts = _declare(reader)
    assert declaration is None
    assert failed is True
    attempt = attempts[-1]
    assert attempt.outcome == "publication_invalid"
    assert attempt.raw_output_text == "显然不是JSON"
    assert attempt.error_classes == ["SOURCE_DEFINITION_CONSUMER_INVALID"]


def test_wrong_version_never_becomes_a_record() -> None:
    stale = _control_text().replace(
        SOURCE_DEFINITION_CONSUMER_VERSION,
        "phase5/control-source-definition-consumer/v1",
    )
    reader = _ScriptedReader([
        ProtocolControlAgentResponse(session_id="session:def", text=stale),
    ])
    (declaration, failed), _attempts = _declare(reader)
    assert declaration is None
    assert failed is True


def test_invented_official_identity_blocks_the_batch() -> None:
    # The parent code is a frozen official target here, but the finer
    # (rule_component_id, predicate_id) identity has no frozen index: equal
    # wording must not substitute for the identity.
    reader = _ScriptedReader([
        ProtocolControlAgentResponse(session_id="session:def", text=_official_text()),
    ])
    (declaration, failed), attempts = _declare(
        reader, batch=_batch(official_targets=(_official_target(),)),
    )
    assert declaration is None
    assert failed is True
    attempt = attempts[-1]
    assert attempt.outcome == "publication_invalid"
    assert attempt.error_detail is not None
    assert attempt.error_detail["code"] == "SOURCE_DEFINITION_CONSUMER_IDENTITY_UNPROVEN"


def test_unknown_official_code_blocks_the_batch() -> None:
    reader = _ScriptedReader([
        ProtocolControlAgentResponse(
            session_id="session:def", text=_official_text(official_code="IN-99"),
        ),
    ])
    identities = {"IN-99": ((RULE_COMPONENT_ID, PREDICATE_ID),)}
    (declaration, failed), attempts = _declare(reader, identities=identities)
    assert declaration is None
    assert failed is True
    attempt = attempts[-1]
    assert attempt.error_detail is not None
    assert attempt.error_detail["code"] == "SOURCE_DEFINITION_CONSUMER_SCOPE_INVALID"


def test_empty_declaration_parses_without_claiming_a_relation() -> None:
    # An empty declaration is a valid "nothing provable" answer; the block
    # stays because scope completeness is only ever decided downstream.
    text = json.dumps(
        {"version": SOURCE_DEFINITION_CONSUMER_VERSION, "items": []},
    )
    reader = _ScriptedReader([
        ProtocolControlAgentResponse(session_id="session:def", text=text),
    ])
    (declaration, failed), _attempts = _declare(reader)
    assert failed is False
    assert declaration is not None
    assert declaration.items == []


# -- transport adapter -------------------------------------------------------


class _FakeCompletions:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = iter(outputs)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = next(self.outputs)
        return iter([
            SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop",
                delta=SimpleNamespace(content=content),
            )]),
        ])


def _stream_transport(outputs: list[str], *, mode: str):
    completions = _FakeCompletions(outputs)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="deepseek",
        model="opaque-control-model",
        max_tokens=8192,
        response_format_mode=mode,
    )
    return transport, completions


def test_consumer_step_uses_its_own_strict_schema() -> None:
    text = json.dumps(
        {"version": SOURCE_DEFINITION_CONSUMER_VERSION, "items": []},
    )
    transport, completions = _stream_transport([text], mode="json_schema")
    response = transport.start_source_definition_consumers(
        prompt="冻结计算定义与冻结候选",
    )
    assert response.text == text
    assert response.session_id.startswith("protocol-control-definition-")
    kwargs = completions.calls[0]
    sent_format = kwargs["response_format"]
    assert sent_format == source_definition_consumers_response_format()
    assert sent_format["json_schema"]["strict"] is True
    # The consumer step must never reuse the candidate wire Schema.
    assert sent_format["json_schema"]["name"] != CONTROL_RESPONSE_FORMAT_NAME


def test_consumer_step_pins_schema_text_when_mode_is_not_json_schema() -> None:
    text = json.dumps(
        {"version": SOURCE_DEFINITION_CONSUMER_VERSION, "items": []},
    )
    transport, completions = _stream_transport([text], mode="text")
    response = transport.start_source_definition_consumers(
        prompt="冻结计算定义与冻结候选",
    )
    assert response.text == text
    kwargs = completions.calls[0]
    assert "response_format" not in kwargs
    prompt = kwargs["messages"][0]["content"]
    assert "本次请求未向模型服务传递严格结构约束" in prompt
    assert SOURCE_DEFINITION_CONSUMER_VERSION in prompt


def test_consumer_step_rejects_a_blank_prompt() -> None:
    transport, _completions = _stream_transport([], mode="json_schema")
    with pytest.raises(ValueError, match="来源定义消费登记提示不能为空"):
        transport.start_source_definition_consumers(prompt="   ")


# -- full deep-run reachability ------------------------------------------------


DEEP_QUOTE = "筛选前说明年龄记录来源"


def _deep_fixtures():
    batch = _deep_batch().model_copy(deep=True)
    batch.owned_units[0].excerpt = f"其他控制：年龄至少18岁；{DEEP_QUOTE}"
    batch.known_official_targets[0].source_excerpts = [DEEP_QUOTE]
    inventory = _source_inventory({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": "su-01",
            "quoted_text": DEEP_QUOTE,
            "force": "required",
            "time_words": ["筛选前"],
            "decision_functions": ["definition", "calculation_input"],
        }],
        "units_without_statement": ["su-02"],
    })
    return batch, inventory


class _DeepTransport:
    """Full deep-run double: interpretation, review, then the consumer step."""

    def __init__(self, *, declaration: str | None) -> None:
        self.declaration = declaration
        self.decl_prompts: list[str] = []
        self.review_calls = 0

    def start(self, *, prompt: str) -> ProtocolControlAgentResponse:
        return ProtocolControlAgentResponse(
            session_id="wire-1",
            text=_deep_wire(candidate=_wire_candidate()).model_dump_json(),
        )

    def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
        _fixture_batch, inventory = _deep_fixtures()
        return ProtocolControlAgentResponse(
            session_id="source-1", text=inventory.model_dump_json(),
        )

    def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
        self.review_calls += 1
        covered = self.review_calls == 2
        review = SourceTargetReview.model_validate({
            "version": SOURCE_TARGET_REVIEW_VERSION,
            "items": [{
                "statement_index": 0,
                "decision": "covered_by_official" if covered else "unresolved",
                "target_id": "EX-01" if covered else None,
                "source_action_excerpt": "说明年龄记录来源",
                "target_action_excerpt": "说明年龄记录来源" if covered else None,
                "source_time_excerpt": "筛选前",
                "target_time_excerpt": "筛选前" if covered else None,
                "unresolved_aspects": [] if covered else ["尚未确认对应目标"],
            }],
        })
        return ProtocolControlAgentResponse(
            session_id=f"target-{self.review_calls}",
            text=review.model_dump_json(),
        )

    def start_source_definition_consumers(
        self, *, prompt: str,
    ) -> ProtocolControlAgentResponse:
        assert self.declaration is not None
        self.decl_prompts.append(prompt)
        return ProtocolControlAgentResponse(session_id="def-1", text=self.declaration)


class _DeepTransportWithoutDeclaration(_DeepTransport):
    """The same deep run without any consumer declaration capability."""

    start_source_definition_consumers = None


def _deep_declaration() -> str:
    return json.dumps({
        "version": SOURCE_DEFINITION_CONSUMER_VERSION,
        "items": [{
            "statement_index": 0,
            "consumers": [{
                "consumer_kind": "control_atom",
                "candidate_index": 0,
                "layer": "obligation",
                "group_index": 0,
                "atom_index": 0,
                "condition_id": None,
                "official_code": None,
                "rule_component_id": None,
                "predicate_id": None,
                "consumer_excerpt": "年龄至少18岁",
                "relation_note": None,
            }],
            "unresolved_aspects": [],
        }],
    })


def test_full_deep_run_populates_the_declaration_from_frozen_identities() -> None:
    batch, _inventory = _deep_fixtures()
    transport = _DeepTransport(declaration=_deep_declaration())
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert result.status == "已解析"
    assert len(transport.decl_prompts) == 1
    # The prompt hands the reader the frozen definition quote and the frozen
    # candidate atom excerpt, and nothing else.
    assert DEEP_QUOTE in transport.decl_prompts[0]
    assert "年龄至少18岁" in transport.decl_prompts[0]
    consumers = result.source_definition_consumers
    assert consumers is not None
    assert consumers.items[0].consumers[0].candidate_index == 0


def test_full_deep_run_without_the_declaration_reader_is_not_accepted() -> None:
    batch, _inventory = _deep_fixtures()
    transport = _DeepTransportWithoutDeclaration(declaration=None)
    result = ProtocolControlAgentRunner().run(batch, transport)
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.source_definition_consumers is None
    last = result.attempts[-1]
    assert last.outcome == "transport_failed"
    assert last.error_classes == ["SOURCE_DEFINITION_CONSUMER_TRANSPORT_FAILED"]
