"""Regressions for the independent protocol-control Agent MTPLX transport.

These tests exercise config identity, strict control Schema selection (never the
official IN/EX Schema), same-session history restore/continue, length retries,
and bounded error behavior.  They inject fake clients and never call a live
model or write clinical artifacts.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents import protocol_control_agent_transport as transport_module
from app.agents.protocol_control_agent_transport import (
    CONTROL_RESPONSE_FORMAT_NAME,
    MTPLX_PROTOCOL_BATCH_MAX_TOKENS,
    OMLX_PROTOCOL_BATCH_MAX_TOKENS,
    OpenAICompatibleProtocolControlAgentTransport,
    ProtocolControlAgentCallError,
    protocol_control_transport_from_environment,
    protocol_control_transport_from_model_config,
)
from app.agents.protocol_control_deconstructor import (
    CONTROL_AGENT_WIRE_VERSION,
    ProtocolControlAgentRunner,
    ProtocolControlAgentWire,
    ProtocolControlAgentWireCandidate,
    ProtocolControlAgentWireConditionAtom,
    ProtocolControlAgentWireConditionDnf,
    ProtocolControlAgentWireConditionGroup,
    ProtocolControlAgentWireDisposition,
    ProtocolControlAgentWireEvidence,
    ProtocolControlAgentWireExceptionDnf,
    ProtocolControlAgentWireObligationAtom,
    ProtocolControlAgentWireObligationDnf,
    ProtocolControlAgentWireObligationGroup,
    protocol_control_agent_response_format,
)
from app.agents.protocol_deconstructor import protocol_output_response_format
from app.domain.contracts.enums import PhaseScope, ReviewStage, StudyPhase
from app.domain.contracts.protocol_controls import (
    ControlObligationKind,
    KnownOfficialRuleTarget,
    KnownWorkflowStageTarget,
    ProtocolControlDispositionBatch,
    ProtocolStructureUnit,
    ReviewNodeRole,
    StructureUnitDispositionKind,
)


ROOT = Path(__file__).resolve().parents[3]


class _FakeOpenAI:
    calls: list[dict[str, object]] = []

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float,
        max_retries: int,
        http_client: object | None = None,
    ):
        self.calls.append(
            {
                "base_url": base_url,
                "api_key": api_key,
                "timeout": timeout,
                "max_retries": max_retries,
                "http_client": http_client,
            }
        )
        # Real OpenAI-compatible clients answer /v1/models; the identity gate
        # needs this capability when the transport builds its own client.
        self.models = SimpleNamespace(
            list=lambda: SimpleNamespace(data=[SimpleNamespace(id=None)])
        )


class _FakeHTTPClient:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs):
        self.calls.append(kwargs)


class FakeCompletions:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        output = next(self.outputs)
        if isinstance(output, tuple):
            content, finish_reason = output
        else:
            content, finish_reason = output, "stop"
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=finish_reason,
                    message=SimpleNamespace(content=content),
                )
            ]
        )


def _client(outputs):
    completions = FakeCompletions(outputs)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def _config_probe(overrides: dict[str, str] | None = None) -> list[str]:
    env = os.environ.copy()
    for key in (
        "PROTOCOL_CONTROL_BACKEND",
        "PROTOCOL_CONTROL_MODEL",
        "PROTOCOL_CONTROL_REASONING_EFFORT",
        "PROTOCOL_CONTROL_MAX_TOKENS",
        "DECONSTRUCT_BACKEND",
        "DECONSTRUCT_MODEL",
        "DECONSTRUCT_REASONING_EFFORT",
        "MTPLX_PROTOCOL_BATCH_MAX_TOKENS",
        "MTPLX_MODEL",
        "MTPLX_REASONING_EFFORT",
    ):
        env.pop(key, None)
    env.update(overrides or {})
    script = (
        "from app.config import ("
        "PROTOCOL_CONTROL_BACKEND, PROTOCOL_CONTROL_MODEL, "
        "PROTOCOL_CONTROL_REASONING_EFFORT, PROTOCOL_CONTROL_MAX_TOKENS, "
        "DECONSTRUCT_BACKEND, DECONSTRUCT_MODEL, DECONSTRUCT_REASONING_EFFORT, "
        "MTPLX_PROTOCOL_BATCH_MAX_TOKENS); "
        "print('|'.join(("
        "PROTOCOL_CONTROL_BACKEND, PROTOCOL_CONTROL_MODEL, "
        "PROTOCOL_CONTROL_REASONING_EFFORT, str(PROTOCOL_CONTROL_MAX_TOKENS), "
        "DECONSTRUCT_BACKEND, DECONSTRUCT_MODEL, DECONSTRUCT_REASONING_EFFORT, "
        "str(MTPLX_PROTOCOL_BATCH_MAX_TOKENS))))"
    )
    output = subprocess.check_output(
        [sys.executable, "-c", script], cwd=ROOT, env=env, text=True
    )
    return output.strip().split("|")


def _unit(unit_id: str, order: int, span_id: str, excerpt: str) -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=f"generic.body.p{order}",
        member_source_refs=[f"generic.body.p{order}"],
        source_span_ids=[span_id],
        unit_kind="paragraph",
        heading_path=["其他方案控制"],
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.SHARED],
        excerpt=excerpt,
    )


def _batch() -> ProtocolControlDispositionBatch:
    owned = [
        _unit("su-01", 1, "span:01", "其他控制：年龄至少18岁"),
        _unit("su-02", 2, "span:02", "其他控制：筛选时记录末次用药日期"),
    ]
    return ProtocolControlDispositionBatch(
        batch_id="pcb-generic-01",
        coverage_manifest_id="manifest:generic-01",
        protocol_version_id="protocol:generic-01",
        study_phase=StudyPhase.PHASE_II,
        batch_number=1,
        batch_total=1,
        owned_units=owned,
        context_units=[],
        owned_structure_unit_ids=["su-01", "su-02"],
        context_structure_unit_ids=[],
        owned_source_span_ids=["span:01", "span:02"],
        context_source_span_ids=[],
        known_official_targets=[
            KnownOfficialRuleTarget(
                catalog_item_id="official-item-1",
                official_code="EX-01",
                label="既有官方排除标准",
                position=0,
                source_span_ids=["span:official"],
            )
        ],
        known_workflow_stage_targets=[
            KnownWorkflowStageTarget(
                workflow_stage_id="stage:screening:one",
                review_stage=ReviewStage.SCREENING,
                display_name="筛选期审核一",
                visit_instance="screening-1",
            )
        ],
    )


def _condition(
    statement: str,
    span_id: str,
    excerpt: str,
) -> ProtocolControlAgentWireConditionAtom:
    return ProtocolControlAgentWireConditionAtom(
        statement=statement,
        source_span_ids=[span_id],
        source_excerpts=[excerpt],
        time_constraint=None,
        requires_professional_judgment=False,
    )


def _candidate() -> ProtocolControlAgentWireCandidate:
    return ProtocolControlAgentWireCandidate(
        title="年龄资料控制",
        applicable_population="拟入组受试者",
        applicability_expression=ProtocolControlAgentWireConditionDnf(
            groups=[
                ProtocolControlAgentWireConditionGroup(
                    atoms=[_condition("年龄条件", "span:01", "年龄至少18岁")]
                )
            ]
        ),
        trigger_expression=None,
        obligation_expression=ProtocolControlAgentWireObligationDnf(
            groups=[
                ProtocolControlAgentWireObligationGroup(
                    atoms=[
                        ProtocolControlAgentWireObligationAtom(
                            kind=ControlObligationKind.REACH_CONDITION,
                            statement="年龄达到18岁",
                            time_constraint=None,
                            prospective_period=None,
                            source_span_ids=["span:01"],
                            source_excerpts=["年龄至少18岁"],
                            requires_professional_judgment=False,
                        )
                    ]
                )
            ]
        ),
        exception_expression=ProtocolControlAgentWireExceptionDnf(
            groups=[
                ProtocolControlAgentWireConditionGroup(
                    atoms=[_condition("无例外", "span:01", "年龄至少18岁")]
                )
            ]
        ),
        review_node_bindings=[
            {
                "workflow_stage_id": "stage:screening:one",
                "review_stage": ReviewStage.SCREENING,
                "role": ReviewNodeRole.DECIDE_AT_NODE,
                "guidance": None,
            }
        ],
        minimum_evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="demographics",
                description="核对年龄资料",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["原始资料"],
            )
        ],
        source_structure_unit_ids=["su-01"],
        source_span_ids=["span:01"],
        cross_source_relations=[],
    )


def _valid_wire_text() -> str:
    wire = ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[
            ProtocolControlAgentWireDisposition(
                structure_unit_id="su-01",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes=None,
            ),
            ProtocolControlAgentWireDisposition(
                structure_unit_id="su-02",
                disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes="仅作补充语境，不形成控制候选",
            ),
        ],
        candidate_drafts=[_candidate()],
    )
    return wire.model_dump_json()


def test_protocol_control_defaults_use_exact_mtplx_product_route() -> None:
    values = _config_probe()

    assert values == [
        "mtplx",
        "mtplx-flash-next-optimized-speed",
        "medium",
        "60000",
        "mtplx",
        "mtplx-flash-next-optimized-speed",
        "medium",
        "16384",
    ]


def test_protocol_control_environment_is_independent_from_official_deconstruct() -> None:
    values = _config_probe(
        {
            "DECONSTRUCT_BACKEND": "deepseek",
            "DECONSTRUCT_MODEL": "deepseek-v4-flash",
            "DECONSTRUCT_REASONING_EFFORT": "max",
            "PROTOCOL_CONTROL_BACKEND": "mtplx",
            "PROTOCOL_CONTROL_MODEL": "mtplx-qwen38-27b-optimized-quality",
            "PROTOCOL_CONTROL_REASONING_EFFORT": "medium",
            "PROTOCOL_CONTROL_MAX_TOKENS": "18432",
        }
    )

    assert values[:4] == [
        "mtplx",
        "mtplx-qwen38-27b-optimized-quality",
        "medium",
        "18432",
    ]
    assert values[4:7] == ["deepseek", "deepseek-v4-flash", "max"]


def test_mtplx_client_disables_proxy_inheritance_and_uses_control_schema(
    monkeypatch,
) -> None:
    _FakeOpenAI.calls.clear()
    _FakeHTTPClient.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module.httpx, "Client", _FakeHTTPClient)
    monkeypatch.setattr(transport_module, "PROTOCOL_CONTROL_BACKEND", "mtplx")
    monkeypatch.setattr(
        transport_module, "PROTOCOL_CONTROL_MODEL", "mtplx-qwen38-27b-optimized-quality"
    )
    monkeypatch.setattr(transport_module, "PROTOCOL_CONTROL_REASONING_EFFORT", "medium")
    monkeypatch.setattr(transport_module, "PROTOCOL_CONTROL_MAX_TOKENS", 60000)
    monkeypatch.setattr(transport_module, "MTPLX_BASE_URL", "http://127.0.0.1:8002")
    monkeypatch.setattr(transport_module, "MTPLX_API_KEY", "")
    monkeypatch.delenv("MTPLX_API_KEY", raising=False)
    monkeypatch.delenv("OMLX_API_KEY", raising=False)

    transport = protocol_control_transport_from_environment()
    kwargs = transport._completion_kwargs([{"role": "user", "content": "控制批次"}])
    official = protocol_output_response_format("semantic_candidate", compact=True)

    assert _FakeOpenAI.calls == [
        {
            "base_url": "http://127.0.0.1:8002/v1",
            "api_key": "local-mtplx",
            "timeout": 600.0,
            "max_retries": 0,
            "http_client": _FakeOpenAI.calls[0]["http_client"],
        }
    ]
    assert isinstance(_FakeOpenAI.calls[0]["http_client"], _FakeHTTPClient)
    assert _FakeHTTPClient.calls == [{"trust_env": False}]
    assert transport.backend == "mtplx"
    assert transport.model == "mtplx-qwen38-27b-optimized-quality"
    assert transport.reasoning_effort == "medium"
    assert transport.max_tokens == MTPLX_PROTOCOL_BATCH_MAX_TOKENS
    assert kwargs["temperature"] == 0.0
    assert kwargs["reasoning_effort"] == "medium"
    assert kwargs["extra_body"] == {"generation_mode": "ar"}
    assert kwargs["response_format"]["json_schema"]["name"] == CONTROL_RESPONSE_FORMAT_NAME
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert kwargs["response_format"] == protocol_control_agent_response_format()
    assert kwargs["response_format"]["json_schema"]["name"] != (
        official["json_schema"]["name"]
    )
    assert kwargs["response_format"]["json_schema"]["schema"] != (
        official["json_schema"]["schema"]
    )


def test_mtplx_output_budget_clamps_to_product_batch_cap() -> None:
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=object(),
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=60000,
    )

    assert transport.max_tokens == MTPLX_PROTOCOL_BATCH_MAX_TOKENS
    assert transport.max_tokens > OMLX_PROTOCOL_BATCH_MAX_TOKENS


def test_injected_official_inex_schema_is_rejected_visibly() -> None:
    official = protocol_output_response_format("semantic_candidate", compact=True)

    with pytest.raises(ValueError, match="非控制 Schema"):
        OpenAICompatibleProtocolControlAgentTransport(
            client=object(),
            backend="mtplx",
            model="mtplx-qwen38-27b-optimized-quality",
            response_format=official,
        )


def test_unsupported_backend_fails_instead_of_silent_semantic_fallback() -> None:
    with pytest.raises(ValueError, match="不支持模型供应商"):
        OpenAICompatibleProtocolControlAgentTransport(
            client=object(),
            backend="unknown-semantic",
            model="must-not-run",
        )


def test_factory_preserves_frozen_model_identity_without_substitution() -> None:
    transport = protocol_control_transport_from_model_config(
        {
            "provider": "mtplx",
            "model": "mtplx-qwen38-27b-optimized-quality",
            "reasoning_effort": "medium",
            "parameters": {
                "max_tokens": 60000,
                "temperature": 0.0,
                "base_url": "http://127.0.0.1:8002",
            },
        },
        client=object(),
    )

    kwargs = transport._completion_kwargs([{"role": "user", "content": "控制"}])
    assert transport.backend == "mtplx"
    assert kwargs["model"] == "mtplx-qwen38-27b-optimized-quality"
    assert kwargs["reasoning_effort"] == "medium"
    assert kwargs["temperature"] == 0.0
    assert kwargs["max_tokens"] == MTPLX_PROTOCOL_BATCH_MAX_TOKENS
    assert kwargs["response_format"]["json_schema"]["name"] == (
        CONTROL_RESPONSE_FORMAT_NAME
    )


def test_same_session_history_and_restore_continue_keep_one_session_id() -> None:
    client, completions = _client(['{"first":1}', '{"second":2}', '{"third":3}'])
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        reasoning_effort="medium",
        max_tokens=16384,
    )

    first = transport.start(prompt="冻结控制输入")
    second = transport.continue_session(
        session_id=first.session_id,
        prompt="同会话修复",
    )

    assert first.session_id.startswith("protocol-control-chat-")
    assert second.session_id == first.session_id
    assert completions.calls[0]["response_format"]["json_schema"]["name"] == (
        CONTROL_RESPONSE_FORMAT_NAME
    )
    assert completions.calls[0]["reasoning_effort"] == "medium"
    assert completions.calls[0]["temperature"] == 0.0
    assert [item["role"] for item in completions.calls[1]["messages"]] == [
        "user",
        "assistant",
        "user",
    ]
    assert completions.calls[1]["messages"][1]["content"] == '{"first":1}'
    assert len(transport.history(first.session_id)) == 4

    restored_client, restored_completions = _client(['{"third":3}'])
    restored = OpenAICompatibleProtocolControlAgentTransport(
        client=restored_client,
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=16384,
    )
    restored.restore_history(
        session_id=first.session_id,
        messages=transport.history(first.session_id),
    )
    resumed = restored.continue_session(
        session_id=first.session_id,
        prompt="重启后继续修复",
    )
    assert resumed.session_id == first.session_id
    assert len(restored_completions.calls[0]["messages"]) == 5
    assert len(restored.history(first.session_id)) == 6


def test_unknown_session_is_rejected_instead_of_starting_fresh() -> None:
    client, _completions = _client([])
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=16384,
    )

    with pytest.raises(ProtocolControlAgentCallError, match="找不到原协议控制 Agent 会话"):
        transport.continue_session(session_id="missing", prompt="修复")


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "assistant", "content": "无首轮请求"}],
        [
            {"role": "user", "content": "请求"},
            {"role": "user", "content": "角色顺序错误"},
        ],
        [{"role": "user", "content": "尚无模型响应"}],
    ],
)
def test_invalid_persisted_history_is_rejected(messages) -> None:
    client, _completions = _client([])
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=16384,
    )
    with pytest.raises(ValueError, match="持久会话|只能从"):
        transport.restore_history(session_id="persisted-session", messages=messages)


def test_length_finish_reason_retries_once_then_succeeds_in_same_call() -> None:
    client, completions = _client(
        [
            ('{"partial":true', "length"),
            ('{"complete":true}', "stop"),
        ]
    )
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=16384,
    )

    response = transport.start(prompt="冻结控制输入")

    assert response.text == '{"complete":true}'
    assert len(completions.calls) == 2
    assert "长度上限" in completions.calls[1]["messages"][-1]["content"]
    assert CONTROL_RESPONSE_FORMAT_NAME in completions.calls[1]["messages"][-1]["content"]
    assert "不要重复分析" in completions.calls[1]["messages"][-1]["content"]
    # In-call length retries are ephemeral; durable history stays user/assistant.
    assert transport.history(response.session_id) == (
        {"role": "user", "content": "冻结控制输入"},
        {"role": "assistant", "content": '{"complete":true}'},
    )
    assert '{"partial":true' not in json.dumps(
        transport.history(response.session_id), ensure_ascii=False
    )

    restored_client, restored_completions = _client(['{"continued":true}'])
    restored = OpenAICompatibleProtocolControlAgentTransport(
        client=restored_client,
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=16384,
    )
    restored.restore_history(
        session_id=response.session_id,
        messages=transport.history(response.session_id),
    )
    resumed = restored.continue_session(
        session_id=response.session_id,
        prompt="同会话继续修复",
    )
    assert resumed.session_id == response.session_id
    assert resumed.text == '{"continued":true}'
    assert restored.history(response.session_id) == (
        {"role": "user", "content": "冻结控制输入"},
        {"role": "assistant", "content": '{"complete":true}'},
        {"role": "user", "content": "同会话继续修复"},
        {"role": "assistant", "content": '{"continued":true}'},
    )
    assert restored_completions.calls[0]["messages"][:2] == list(
        transport.history(response.session_id)
    )


def test_two_length_failures_raise_visible_call_error_without_silent_fallback() -> None:
    client, completions = _client(
        [
            ('{"truncated":1', "length"),
            ('{"truncated":2', "length"),
        ]
    )
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=16384,
    )

    with pytest.raises(ProtocolControlAgentCallError, match="连续两次未返回可读取的 JSON") as exc:
        transport.start(prompt="冻结控制输入")

    assert len(completions.calls) == 2
    assert "长度上限" in str(exc.value)
    assert "truncated" not in str(exc.value)
    assert exc.value.session_id.startswith("protocol-control-chat-")
    with pytest.raises(ProtocolControlAgentCallError, match="找不到协议控制 Agent 会话"):
        transport.history(exc.value.session_id)


def test_empty_body_is_retried_once_with_control_schema_instruction() -> None:
    client, completions = _client(
        [
            (None, "stop"),
            ('{"ok":true}', "stop"),
        ]
    )
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=16384,
    )

    response = transport.start(prompt="冻结控制输入")

    assert response.text == '{"ok":true}'
    assert len(completions.calls) == 2
    assert CONTROL_RESPONSE_FORMAT_NAME in completions.calls[1]["messages"][-1]["content"]
    assert "不要重复分析" in completions.calls[1]["messages"][-1]["content"]
    # Empty-body internal retry must not produce consecutive user turns.
    assert transport.history(response.session_id) == (
        {"role": "user", "content": "冻结控制输入"},
        {"role": "assistant", "content": '{"ok":true}'},
    )

    restored_client, restored_completions = _client(['{"after-empty":true}'])
    restored = OpenAICompatibleProtocolControlAgentTransport(
        client=restored_client,
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=16384,
    )
    restored.restore_history(
        session_id=response.session_id,
        messages=transport.history(response.session_id),
    )
    resumed = restored.continue_session(
        session_id=response.session_id,
        prompt="空正文后继续修复",
    )
    assert resumed.session_id == response.session_id
    assert resumed.text == '{"after-empty":true}'
    assert [item["role"] for item in restored.history(response.session_id)] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert restored_completions.calls[0]["messages"][0]["content"] == "冻结控制输入"
    assert restored_completions.calls[0]["messages"][1]["content"] == '{"ok":true}'
    assert restored_completions.calls[0]["messages"][2]["content"] == "空正文后继续修复"


def test_runner_uses_real_transport_same_session_repair_without_inex_schema() -> None:
    invalid = json.dumps(
        {"wire_version": CONTROL_AGENT_WIRE_VERSION, "dispositions": []},
        ensure_ascii=False,
    )
    valid = _valid_wire_text()
    client, completions = _client([invalid, valid])
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        reasoning_effort="medium",
        max_tokens=16384,
    )

    result = ProtocolControlAgentRunner(max_schema_repairs=1).run(_batch(), transport)

    assert result.status == "已解析"
    assert result.session_id is not None
    assert len(result.attempts) == 2
    assert result.attempts[0].outcome == "schema_invalid"
    assert result.attempts[1].outcome == "parsed"
    assert len(completions.calls) == 2
    assert all(
        call["response_format"]["json_schema"]["name"] == CONTROL_RESPONSE_FORMAT_NAME
        for call in completions.calls
    )
    assert all(
        call["response_format"]["json_schema"]["name"]
        != protocol_output_response_format("semantic_candidate", compact=True)[
            "json_schema"
        ]["name"]
        for call in completions.calls
    )
    assert all(call["temperature"] == 0.0 for call in completions.calls)
    assert all(call["reasoning_effort"] == "medium" for call in completions.calls)
    assert [item["role"] for item in completions.calls[1]["messages"]] == [
        "user",
        "assistant",
        "user",
    ]
    assert completions.calls[1]["messages"][0]["content"] == completions.calls[0][
        "messages"
    ][0]["content"]
    assert "pcb-generic-01" in completions.calls[1]["messages"][-1]["content"]


def test_runner_bounds_transport_failures_without_switching_schema_or_model() -> None:
    class _FailingTransport(OpenAICompatibleProtocolControlAgentTransport):
        def start(self, *, prompt: str):
            raise ProtocolControlAgentCallError(
                "protocol-control-chat-fail",
                "协议控制模型请求失败：ConnectionError: refused",
            )

    transport = _FailingTransport(
        client=object(),
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=16384,
    )
    result = ProtocolControlAgentRunner(max_transport_retries=0).run(_batch(), transport)

    assert result.status == "需要核对"
    assert result.attempts[0].outcome == "transport_failed"
    assert "ConnectionError" in result.attempts[0].issues[0]
    assert transport.uses_control_response_format is True
    assert transport.response_format_sha256 == (
        OpenAICompatibleProtocolControlAgentTransport(
            client=object(),
            backend="mtplx",
            model="mtplx-qwen38-27b-optimized-quality",
            max_tokens=16384,
        ).response_format_sha256
    )


def test_runner_does_not_duplicate_request_after_uncertain_timeout() -> None:
    class _TimedOutTransport:
        calls = 0

        def start(self, *, prompt: str):
            self.calls += 1
            raise ProtocolControlAgentCallError(
                "protocol-control-chat-timeout",
                "协议控制模型请求超时",
                uncertain_completion=True,
            )

        def continue_session(self, *, session_id: str, prompt: str):
            raise AssertionError("首次请求超时后不得盲目续提")

    transport = _TimedOutTransport()
    result = ProtocolControlAgentRunner(max_transport_retries=3).run(
        _batch(), transport
    )

    assert transport.calls == 1
    assert result.status == "需要核对"
    assert len(result.attempts) == 1
    assert result.attempts[0].outcome == "transport_failed"


def test_transport_handles_server_500_internal_error_with_session_and_error_details() -> None:
    class _FailingCompletions:
        def create(self, **kwargs):
            raise RuntimeError(
                "InternalServerError: Error code: 500 - {'error': {'message': 'internal server error; see the MTPLX server log (request_id=e0c906e5d034)', 'type': 'server_error', 'code': 'internal_error'}}"
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=_FailingCompletions()))
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=fake_client,
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
    )
    with pytest.raises(ProtocolControlAgentCallError) as exc_info:
        transport.start(prompt="测试输入")

    assert exc_info.value.session_id.startswith("protocol-control-chat-")
    assert "internal server error" in str(exc_info.value)
    assert "e0c906e5d034" in str(exc_info.value)
