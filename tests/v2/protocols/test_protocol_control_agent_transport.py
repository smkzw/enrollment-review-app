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
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents import protocol_control_agent_transport as transport_module
from app.agents import protocol_control_discovery_transport as discovery_module
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
from app.agents.protocol_control_discovery_transport import (
    protocol_control_discovery_transport_from_model_config,
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


@pytest.fixture(autouse=True)
def _fake_client_tests_do_not_require_a_running_mtplx(monkeypatch):
    @contextmanager
    def fake_model_session(*_args, **_kwargs):
        yield None

    monkeypatch.setattr(
        "app.llm.mtplx_model_lifecycle.sync_mtplx_model_session", fake_model_session
    )


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
        if kwargs.get("stream"):
            return iter([
                SimpleNamespace(choices=[SimpleNamespace(
                    finish_reason=finish_reason,
                    delta=SimpleNamespace(content=content),
                )])
            ])
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
        evaluation=_evaluation(statement, span_id, excerpt),
        source_span_ids=[span_id],
        source_excerpts=[excerpt],
        time_constraint=None,
        requires_professional_judgment=False,
    )


def _evaluation(statement: str, span_id: str, excerpt: str) -> dict:
    return {
        "determination_mode": "semantic",
        "proposition": statement,
        "time_purpose": "not_applicable",
        "repeat_scheme": None,
        "observation_policy": {
            "mode": "unresolved",
            "scope": "样例未说明采用哪次记录",
            "source_span_ids": [span_id],
            "source_excerpts": [excerpt],
        },
        "source_span_ids": [span_id],
        "source_excerpts": [excerpt],
    }


def _candidate() -> ProtocolControlAgentWireCandidate:
    return ProtocolControlAgentWireCandidate(
        title="年龄资料控制",
        repeat_trigger_conditions=[],
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
                            evaluation={
                                **_evaluation("年龄达到18岁", "span:01", "年龄至少18岁"),
                                "determination_mode": "deterministic",
                                "operation": "value_comparison",
                                "operand_attribute": "value",
                                "predicate": {
                                    "predicate_id": "age-threshold",
                                    "subject": "受试者",
                                    "attribute": "年龄",
                                    "comparator": "gte",
                                    "value": 18,
                                    "unit": "岁",
                                    "source_clause": "年龄至少18岁",
                                },
                            },
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
                workflow_stage_ids=["stage:screening:one"],
                source_policy={
                    "requires_contemporaneous_objective_source": None,
                    "allows_screening_record_transcription": None,
                    "result_validity_status": "not_specified",
                    "result_validity_constraint": None,
                    "source_span_ids": ["span:01"],
                    "source_excerpts": ["年龄至少18岁"],
                },
                atom_refs=[{"layer": "obligation", "group_index": 0, "atom_index": 0}],
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


def test_protocol_control_defaults_use_current_independent_product_routes() -> None:
    values = _config_probe()

    assert values == [
        "cms-router",
        "deepseek-latest-cloud",
        "high",
        "65536",
        "cms-router",
        "glm-5.3-flash",
        "high",
        "131072",
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
    # env 继承预算 60000 在平台上限内原样生效，不被静默压缩。
    assert transport.max_tokens == 60000
    # 未显式配置 temperature 时保留供应商采样默认：不发送 temperature。
    assert "temperature" not in kwargs
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


def test_mtplx_explicit_budget_within_cap_is_kept_not_clamped() -> None:
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=object(),
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=60000,
    )

    # 显式 60000 在平台上限内原样生效；不静默 min() 压缩，也不抬高。
    assert transport.max_tokens == 60000


def test_explicit_budget_above_platform_cap_fails_without_silent_shrink() -> None:
    with pytest.raises(ValueError, match="不会静默压缩显式请求"):
        OpenAICompatibleProtocolControlAgentTransport(
            client=object(),
            backend="mtplx",
            model="mtplx-qwen38-27b-optimized-quality",
            max_tokens=MTPLX_PROTOCOL_BATCH_MAX_TOKENS + 1,
        )


def test_control_transport_omits_temperature_unless_explicitly_configured() -> None:
    def build_kwargs(temperature):
        transport = OpenAICompatibleProtocolControlAgentTransport(
            client=object(),
            backend="mtplx",
            model="mtplx-qwen38-27b-optimized-quality",
            max_tokens=16384,
            temperature=temperature,
        )
        return transport._completion_kwargs([{"role": "user", "content": "控制"}])

    # 未配置 → 供应商采样默认（不发 temperature）；显式 0 与显式非零原样发送。
    assert "temperature" not in build_kwargs(None)
    assert build_kwargs(0.0)["temperature"] == 0.0
    assert build_kwargs(0.7)["temperature"] == 0.7


def test_opencode_control_transport_uses_json_object_wire_and_keeps_strict_contract() -> None:
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=object(),
        backend="opencode-go",
        model="deepseek-v4.1-flash",
        reasoning_effort="high",
        max_tokens=65536,
    )

    kwargs = transport._completion_kwargs([{"role": "user", "content": "控制"}])

    assert transport.response_format_mode == "json_object"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert transport.response_format_sha256 == (
        OpenAICompatibleProtocolControlAgentTransport(
            client=object(),
            backend="cms-router",
            model="glm-5.3-flash",
            max_tokens=65536,
        ).response_format_sha256
    )


def test_control_response_format_mode_can_be_explicitly_overridden() -> None:
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=object(),
        backend="cms-router",
        model="glm-5.3-flash",
        max_tokens=65536,
        response_format_mode="text",
    )

    kwargs = transport._completion_kwargs([{"role": "user", "content": "控制"}])

    assert transport.response_format_mode == "text"
    assert "response_format" not in kwargs


def test_control_length_retry_budget_capped_at_131072() -> None:
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
        max_tokens=100000,
    )

    transport.start(prompt="冻结控制输入")

    budgets = [call["max_tokens"] for call in completions.calls]
    # length 只重试一次：100000*2 封顶 131072，不静默翻倍到 200000。
    assert budgets == [100000, 131072]


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
    # 冻结配置显式给出的 temperature=0 是真实请求值，原样发送。
    assert kwargs["temperature"] == 0.0
    assert kwargs["max_tokens"] == 60000
    assert kwargs["response_format"]["json_schema"]["name"] == (
        CONTROL_RESPONSE_FORMAT_NAME
    )


def test_alternate_provider_does_not_inherit_active_role_endpoint_or_key(
    monkeypatch,
) -> None:
    _FakeOpenAI.calls.clear()
    monkeypatch.setenv("PROTOCOL_CONTROL_BASE_URL", "https://active.example/v1")
    monkeypatch.setenv("PROTOCOL_CONTROL_API_KEY", "active-only-key")
    monkeypatch.setenv("PROTOCOL_CONTROL_DISCOVERY_BASE_URL", "https://active.example/v1")
    monkeypatch.setenv("PROTOCOL_CONTROL_DISCOVERY_API_KEY", "active-only-key")
    monkeypatch.setenv("CMS_ROUTER_BASE_URL", "http://127.0.0.1:20128/v1")
    monkeypatch.setenv("CMS_ROUTER_API_KEY", "cms-only-key")
    monkeypatch.setattr(transport_module, "PROTOCOL_CONTROL_BACKEND", "opencode-go")
    monkeypatch.setattr(discovery_module, "PROTOCOL_CONTROL_DISCOVERY_BACKEND", "opencode-go")
    monkeypatch.setattr(discovery_module, "OpenAI", _FakeOpenAI)
    frozen = {
        "provider": "cms-router",
        "model": "glm-5.3-flash",
        "reasoning_effort": "high",
        "parameters": {"max_tokens": 65536},
    }

    deep = protocol_control_transport_from_model_config(
        frozen,
        _client_factory=_FakeOpenAI,
    )
    discovery = protocol_control_discovery_transport_from_model_config(frozen)

    assert deep.base_url == discovery.base_url == "http://127.0.0.1:20128/v1"
    assert [call["api_key"] for call in _FakeOpenAI.calls] == [
        "cms-only-key", "cms-only-key"
    ]


def test_candidate_repair_changes_only_response_schema_in_same_session() -> None:
    client, completions = _client(['{"wire":1}', '{"candidate_draft":{}}'])
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="cms-router",
        model="deepseek-latest-cloud",
        reasoning_effort="high",
        max_tokens=16384,
    )
    transport._stream_completion = lambda fake_client, kwargs: fake_client.chat.completions.create(**kwargs)

    first = transport.start(prompt="冻结控制输入")
    repaired = transport.continue_candidate(
        session_id=first.session_id, prompt="只修一个候选"
    )

    assert repaired.session_id == first.session_id
    assert completions.calls[0]["response_format"]["json_schema"]["name"] == CONTROL_RESPONSE_FORMAT_NAME
    assert completions.calls[1]["response_format"]["json_schema"]["name"] == "protocol_control_candidate_repair_v1"
    assert [item["role"] for item in completions.calls[1]["messages"]] == [
        "user", "assistant", "user"
    ]
    assert len(transport.history(first.session_id)) == 4


def test_multi_candidate_repair_uses_selected_schema_in_same_session() -> None:
    client, completions = _client(['{"wire":1}', '{"candidate_drafts":[]}'])
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="cms-router",
        model="deepseek-latest-cloud",
        max_tokens=16384,
    )

    first = transport.start(prompt="冻结控制输入")
    repaired = transport.continue_candidates(
        session_id=first.session_id, prompt="仅修订两个候选"
    )

    assert repaired.session_id == first.session_id
    assert completions.calls[1]["response_format"]["json_schema"]["name"] == (
        "protocol_control_candidates_repair_v1"
    )
    assert [item["role"] for item in transport.history(first.session_id)] == [
        "user", "assistant", "user", "assistant"
    ]


def test_local_repairs_send_only_frozen_source_and_keep_fallback_history() -> None:
    client, completions = _client([
        '{"wire":1}', '{"atom":{}}', '{"items":[]}', '{"items":[]}', '{"candidate_draft":{}}',
    ])
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="cms-router",
        model="deepseek-latest-cloud",
        max_tokens=16384,
    )
    first = transport.start(prompt="完整冻结批次")
    history = transport.history(first.session_id)
    transport.continue_atom(session_id=first.session_id, prompt="冻结的原子及其来源")

    assert completions.calls[1]["messages"] == [
        {"role": "user", "content": "冻结的原子及其来源"}
    ]
    assert completions.calls[1]["response_format"]["json_schema"]["name"] == (
        "protocol_control_atom_repair_v1"
    )
    assert transport.history(first.session_id) == history

    transport.continue_observation_policies(
        session_id=first.session_id, prompt="冻结的义务原子观察选择"
    )
    assert completions.calls[2]["messages"] == [
        {"role": "user", "content": "冻结的义务原子观察选择"}
    ]
    assert completions.calls[2]["response_format"]["json_schema"]["name"] == (
        "protocol_control_observation_repair_v1"
    )
    assert transport.history(first.session_id) == history

    transport.continue_time_operands(
        session_id=first.session_id, prompt="冻结原子及日期来源"
    )
    assert completions.calls[3]["messages"] == [
        {"role": "user", "content": "冻结原子及日期来源"}
    ]
    assert completions.calls[3]["response_format"]["json_schema"]["name"] == (
        "protocol_control_time_operand_repair_v1"
    )
    assert transport.history(first.session_id) == history

    transport.continue_candidate(session_id=first.session_id, prompt="候选级回退")
    assert [item["content"] for item in completions.calls[4]["messages"]] == [
        "完整冻结批次", '{"wire":1}', "候选级回退",
    ]


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
    # 未显式配置 temperature：保留供应商采样默认，请求中不出现 temperature。
    assert "temperature" not in completions.calls[0]
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
    # length 只重试一次：共享思考+正文预算 16384 → 32768。
    assert [call["max_tokens"] for call in completions.calls] == [16384, 32768]
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


@pytest.mark.parametrize("mode", ["json_object", "text"])
def test_length_retry_without_provider_json_schema_keeps_wire_contract(mode: str) -> None:
    client, completions = _client(
        [('{"partial":true', "length"), ('{"complete":true}', "stop")]
    )
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="cms-router",
        model="deepseek-latest-cloud",
        max_tokens=16384,
        response_format_mode=mode,
    )

    response = transport.start(prompt="冻结控制输入")

    assert response.text == '{"complete":true}'
    assert [call["max_tokens"] for call in completions.calls] == [16384, 32768]
    assert CONTROL_RESPONSE_FORMAT_NAME in completions.calls[1]["messages"][-1]["content"]
    assert completions.calls[0].get("response_format") == (
        {"type": "json_object"} if mode == "json_object" else None
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
    # This fixture isolates the full-wire retry; source inventory has its own tests.
    transport.start_source_interpretation = None

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
    # 未显式配置 temperature：两次调用都保留供应商采样默认。
    assert all("temperature" not in call for call in completions.calls)
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


def test_source_target_review_uses_its_own_small_schema() -> None:
    client, completions = _client(['{"version":"phase5/control-source-target-review/v7","items":[]}'])
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        reasoning_effort="medium",
        max_tokens=16384,
    )
    response = transport.start_source_target_review(prompt="核对冻结来源与目标")
    assert response.text.startswith('{"version":')
    assert completions.calls[0]["response_format"]["json_schema"]["name"] == (
        "protocol_control_source_target_review_v7"
    )
    assert "temperature" not in completions.calls[0]


def test_source_scope_correction_uses_bounded_schema() -> None:
    client, completions = _client(['{"version":"phase5/control-source-scope-correction/v1",'
                                    '"structure_unit_id":"su-01","scope_quote":null,'
                                    '"affected_stage":null,"time_words":[],"unresolved":null}'])
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client, backend="mtplx", model="mtplx-qwen38-27b-optimized-quality",
        reasoning_effort="medium", max_tokens=16384,
    )
    response = transport.correct_source_scope(prompt="核对单条冻结来源")
    assert '"su-01"' in response.text
    assert completions.calls[0]["response_format"]["json_schema"]["name"] == (
        "protocol_control_source_scope_correction_v1"
    )


def test_runner_bounds_transport_failures_without_switching_schema_or_model() -> None:
    class _FailingTransport(OpenAICompatibleProtocolControlAgentTransport):
        def start_source_interpretation(self, *, prompt: str):
            raise ProtocolControlAgentCallError(
                "protocol-control-chat-fail",
                "协议控制模型请求失败：ConnectionError: refused",
            )

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


# ---------------------------------------------------------------------------
# GLM（zhipu-coding-plan）协议控制路由：连接档案、GLM 词表与采样默认
# ---------------------------------------------------------------------------


_BIGMODEL_CODING_PLAN_URL = "https://open.bigmodel.cn/api/coding/paas/v4"


def test_control_glm_backend_uses_coding_plan_profile_and_glm_wire(monkeypatch) -> None:
    _FakeOpenAI.calls.clear()
    _FakeHTTPClient.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module.httpx, "Client", _FakeHTTPClient)
    monkeypatch.setattr(transport_module, "PROTOCOL_CONTROL_BACKEND", "zhipu-coding-plan")
    monkeypatch.setattr(transport_module, "PROTOCOL_CONTROL_MODEL", "glm-5.3-flash")
    monkeypatch.setattr(transport_module, "PROTOCOL_CONTROL_REASONING_EFFORT", "high")
    monkeypatch.setattr(transport_module, "PROTOCOL_CONTROL_MAX_TOKENS", 65536)
    monkeypatch.setattr(
        transport_module, "PROTOCOL_CONTROL_GLM_BASE_URL", f"{_BIGMODEL_CODING_PLAN_URL}/"
    )
    monkeypatch.setattr(transport_module, "PROTOCOL_CONTROL_GLM_API_KEY", "glm-key")
    _FakeHTTPClient.calls.clear()

    transport = protocol_control_transport_from_environment()

    # Coding Plan 的 .../paas/v4 路径原样保留，不追加 /v1；直连不走系统代理。
    assert _FakeOpenAI.calls[0]["base_url"] == _BIGMODEL_CODING_PLAN_URL
    assert _FakeOpenAI.calls[0]["api_key"] == "glm-key"
    assert _FakeHTTPClient.calls == [{"trust_env": False}]
    kwargs = transport._completion_kwargs([{"role": "user", "content": "控制"}])
    assert kwargs["model"] == "glm-5.3-flash"
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["max_tokens"] == 65536
    assert "temperature" not in kwargs
    assert kwargs["extra_body"] == {
        "thinking": {"type": "enabled", "clear_thinking": False}
    }
    assert kwargs["response_format"]["json_schema"]["name"] == CONTROL_RESPONSE_FORMAT_NAME
    # GLM 路由不带 MTPLX 的 AR 兼容措施。
    assert kwargs["extra_body"] != {"generation_mode": "ar"}


def test_control_glm_backend_rejects_unsupported_effort_instead_of_mapping_down() -> None:
    with pytest.raises(ValueError, match="low/high/max"):
        OpenAICompatibleProtocolControlAgentTransport(
            client=object(),
            backend="zhipu-coding-plan",
            model="glm-5.3-flash",
            reasoning_effort="xhigh",
            api_key="glm-key",
        )


def test_control_glm_backend_requires_credential_before_any_request(
    monkeypatch,
) -> None:
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module, "PROTOCOL_CONTROL_BACKEND", "zhipu-coding-plan")
    monkeypatch.setattr(transport_module, "PROTOCOL_CONTROL_GLM_API_KEY", "")

    with pytest.raises(ValueError, match="尚未配置 api_key"):
        protocol_control_transport_from_environment()

    assert _FakeOpenAI.calls == []
