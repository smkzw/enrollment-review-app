from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from app.agents import protocol_semantic_transport as transport_module
from app.agents.protocol_deconstructor import (
    ProtocolDeconstructionAttempt,
    ProtocolDeconstructionRunResult,
    ProtocolSemanticRuleRepair,
    protocol_output_response_format,
)
from app.services import protocol_deconstruction_executor as executor_module
from app.protocols.deconstruction_gate import ProtocolGateIssue
from app.workflow.errors import StepFailure


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


class _FakeHTTPClient:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs):
        self.calls.append(kwargs)


def _config_probe(overrides: dict[str, str] | None = None) -> list[str]:
    env = os.environ.copy()
    for key in (
        "REVIEW_MODEL",
        "REVIEW_BACKEND",
        "REVIEW_REASONING_EFFORT",
        "DECONSTRUCT_MODEL",
        "DECONSTRUCT_BACKEND",
        "DECONSTRUCT_REASONING_EFFORT",
        "OMLX_PROTOCOL_BATCH_MAX_TOKENS",
        "MTPLX_PROTOCOL_BATCH_MAX_TOKENS",
    ):
        env.pop(key, None)
    env.update(overrides or {})
    script = (
        "from app.config import REVIEW_MODEL, REVIEW_BACKEND, "
        "DECONSTRUCT_MODEL, DECONSTRUCT_BACKEND, DECONSTRUCT_REASONING_EFFORT, "
        "OMLX_PROTOCOL_BATCH_MAX_TOKENS, MTPLX_PROTOCOL_BATCH_MAX_TOKENS; "
        "print('|'.join((REVIEW_MODEL, REVIEW_BACKEND, DECONSTRUCT_MODEL, "
        "DECONSTRUCT_BACKEND, DECONSTRUCT_REASONING_EFFORT, "
        "str(OMLX_PROTOCOL_BATCH_MAX_TOKENS), "
        "str(MTPLX_PROTOCOL_BATCH_MAX_TOKENS))))"
    )
    output = subprocess.check_output(
        [sys.executable, "-c", script], cwd=ROOT, env=env, text=True
    )
    return output.strip().split("|")


def _glm_key_probe(overrides: dict[str, str]) -> str:
    env = os.environ.copy()
    env.pop("INDEPENDENT_VLM_API_KEY", None)
    env.pop("DECONSTRUCT_GLM_API_KEY", None)
    env.update(overrides)
    output = subprocess.check_output(
        [
            sys.executable,
            "-c",
            "from app.config import DECONSTRUCT_GLM_API_KEY; "
            "print(DECONSTRUCT_GLM_API_KEY)",
        ],
        cwd=ROOT,
        env=env,
        text=True,
    )
    return output.strip()


def test_deconstruction_defaults_are_independent_from_legacy_review_defaults():
    values = _config_probe()

    assert values == [
        "mtplx-flash-next-optimized-speed",
        "mtplx",
        "mtplx-flash-next-optimized-speed",
        "mtplx",
        "medium",
        "8192",
        "16384",
    ]


def test_explicit_deconstruction_environment_overrides_are_preserved():
    values = _config_probe(
        {
            "REVIEW_MODEL": "legacy-review-model",
            "REVIEW_BACKEND": "deepseek",
            "REVIEW_REASONING_EFFORT": "max",
            "DECONSTRUCT_MODEL": "explicit-protocol-model",
            "DECONSTRUCT_BACKEND": "omlx",
            "DECONSTRUCT_REASONING_EFFORT": "high",
        }
    )

    assert values == [
        "legacy-review-model",
        "deepseek",
        "explicit-protocol-model",
        "omlx",
        "high",
        "8192",
        "16384",
    ]


def test_local_protocol_output_budgets_can_be_tuned_independently() -> None:
    values = _config_probe(
        {
            "OMLX_PROTOCOL_BATCH_MAX_TOKENS": "9216",
            "MTPLX_PROTOCOL_BATCH_MAX_TOKENS": "18432",
        }
    )

    assert values[-2:] == ["9216", "18432"]


def test_protocol_glm_reuses_independent_vlm_key_when_not_overridden() -> None:
    assert _glm_key_probe(
        {"INDEPENDENT_VLM_API_KEY": "shared-zhipu-key"}
    ) == "shared-zhipu-key"


def test_protocol_glm_key_can_override_independent_vlm_key() -> None:
    assert _glm_key_probe(
        {
            "INDEPENDENT_VLM_API_KEY": "shared-zhipu-key",
            "DECONSTRUCT_GLM_API_KEY": "semantic-only-key",
        }
    ) == "semantic-only-key"


def test_omlx_transport_uses_local_endpoint_and_does_not_require_deepseek_key(
    monkeypatch,
):
    _FakeOpenAI.calls.clear()
    _FakeHTTPClient.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module.httpx, "Client", _FakeHTTPClient)
    monkeypatch.setattr(transport_module, "DECONSTRUCT_BACKEND", "omlx")
    monkeypatch.setattr(
        transport_module, "OMLX_BASE_URL", "http://127.0.0.1:8001/v1/"
    )
    monkeypatch.setattr(transport_module, "OMLX_API_KEY", "")
    monkeypatch.setattr(transport_module, "DEEPSEEK_API_KEY", "")

    transport = transport_module.DeepSeekProtocolAgentTransport(
        model="Qwen3.8-27B-oQ8e-fp16-mtp"
    )

    assert _FakeOpenAI.calls == [
        {
            "base_url": "http://127.0.0.1:8001/v1",
            "api_key": "local-omlx",
            "timeout": 600.0,
            "max_retries": 0,
            "http_client": _FakeOpenAI.calls[0]["http_client"],
        }
    ]
    assert isinstance(_FakeOpenAI.calls[0]["http_client"], _FakeHTTPClient)
    assert _FakeHTTPClient.calls == [{"trust_env": False}]
    kwargs = transport._completion_kwargs([{"role": "user", "content": "方案"}])
    assert kwargs["model"] == "Qwen3.8-27B-oQ8e-fp16-mtp"
    assert transport_module.OMLX_PROTOCOL_BATCH_MAX_TOKENS == 8192
    assert kwargs["max_tokens"] == transport_module.OMLX_PROTOCOL_BATCH_MAX_TOKENS
    assert kwargs["max_tokens"] < 60000
    assert kwargs["temperature"] == 0.0
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["json_schema"]["name"] == (
        "protocol_semantic_batch_wire_candidate"
    )
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert kwargs["response_format"]["json_schema"]["schema"] == (
        transport_module.decoding_response_format(protocol_output_response_format(
            "semantic_candidate", compact=True
        ))["json_schema"]["schema"]
    )
    repair_kwargs = transport._completion_kwargs(
        [{"role": "user", "content": "修正"}],
        output_kind="semantic_rule_repair",
    )
    assert repair_kwargs["response_format"]["json_schema"]["name"] == (
        "protocol_semantic_batch_wire_repair"
    )
    assert repair_kwargs["response_format"]["json_schema"]["strict"] is True
    assert repair_kwargs["response_format"]["json_schema"]["schema"] == (
        transport_module.decoding_response_format(protocol_output_response_format(
            "semantic_rule_repair", compact=True
        ))["json_schema"]["schema"]
    )
    assert "reasoning_effort" not in kwargs
    assert "extra_body" not in kwargs


def test_mtplx_transport_has_its_own_quality_output_budget() -> None:
    transport = transport_module.DeepSeekProtocolAgentTransport(
        client=object(),
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=60000,
    )

    kwargs = transport._completion_kwargs([{"role": "user", "content": "方案"}])

    assert kwargs["max_tokens"] == transport_module.MTPLX_PROTOCOL_BATCH_MAX_TOKENS
    assert kwargs["max_tokens"] > transport_module.OMLX_PROTOCOL_BATCH_MAX_TOKENS
    assert kwargs["extra_body"] == {"generation_mode": "ar"}


def test_omlx_wire_schema_is_small_flat_and_kind_specific():
    wire = transport_module.protocol_output_response_format(
        "semantic_candidate", compact=True
    )["json_schema"]["schema"]
    repair = transport_module.protocol_output_response_format(
        "semantic_rule_repair", compact=True
    )["json_schema"]["schema"]
    encoded_wire = json.dumps(wire, ensure_ascii=False)

    # The provider schema is intentionally explicit rather than using the
    # formal model's polymorphic definitions.  Its compactness contract is
    # semantic: flat DNF arrays, no graph references, and no polymorphic
    # combinators.  Requiring fewer serialized characters is not stable when
    # common atom fields are repeated for the three strict atom shapes.
    assert all(token not in encoded_wire for token in ("anyOf", "allOf", "oneOf"))
    assert all(
        token not in encoded_wire
        for token in (
            "node_id",
            "children",
            "root_node_id",
            "predicate_id",
            "existence_predicate_nodes",
            "all_any_logical_nodes",
        )
    )
    assert wire["properties"]["wire_version"] == {"const": "dnf-v1"}
    assert repair["properties"]["wire_version"] == {"const": "dnf-v1"}
    assert "proposed_rules" in wire["properties"]
    assert "replacement_rules" in repair["properties"]
    assert "proposed_rules" not in repair["properties"]
    assert "unit_match_policy" not in encoded_wire
    assert set(wire["$defs"]) == {
        "wire_source_locator",
        "wire_time_constraint",
        "wire_dnf_group",
    }
    assert wire["$defs"]["wire_dnf_group"] == repair["$defs"]["wire_dnf_group"]

    rule_schema = wire["properties"]["proposed_rules"]["items"]
    component_schema = rule_schema["properties"]["components"]["items"]
    assert "expression" in component_schema["required"]
    assert "exception_expression" in component_schema["properties"]
    group_schema = wire["$defs"]["wire_dnf_group"]
    assert set(group_schema["required"]) == {
        "existence_atoms",
        "scalar_atoms",
        "set_atoms",
    }
    assert all(
        group_schema["properties"][name]["items"]["additionalProperties"] is False
        for name in ("existence_atoms", "scalar_atoms", "set_atoms")
    )
    existence_schema = group_schema["properties"]["existence_atoms"]["items"]
    scalar_schema = group_schema["properties"]["scalar_atoms"]["items"]
    set_schema = group_schema["properties"]["set_atoms"]["items"]
    assert "unit" not in existence_schema["required"]
    assert {"comparator", "value", "unit"} <= set(scalar_schema["required"])
    assert {"comparator", "values", "unit"} <= set(set_schema["required"])
    assert "negated" in existence_schema["required"]
    assert "negated" in scalar_schema["required"]
    assert "negated" in set_schema["required"]
    assert scalar_schema["properties"]["comparator"]["enum"] == [
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
    ]
    assert set_schema["properties"]["comparator"]["enum"] == ["in", "not_in"]
    assert "comparator" not in existence_schema["properties"]
    assert "value" not in existence_schema["properties"]
    assert "values" not in existence_schema["properties"]
    locator_schema = wire["$defs"]["wire_source_locator"]
    assert locator_schema["additionalProperties"] is False
    assert locator_schema["minProperties"] == 1
    assert locator_schema["maxProperties"] == 1
    assert set(("anchor_type", "direction", "allow_partial_date")) <= set(
        wire["$defs"]["wire_time_constraint"]["required"]
    )

    def schema_nodes(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from schema_nodes(child)
        elif isinstance(value, list):
            for child in value:
                yield from schema_nodes(child)

    assert all(
        node.get("maxItems") != 128
        for schema in (wire, repair)
        for node in schema_nodes(schema)
    )


def test_deepseek_transport_requires_key_only_when_explicitly_selected(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module, "DEEPSEEK_API_KEY", "configured")
    monkeypatch.setattr(
        transport_module, "DEEPSEEK_BASE_URL", "https://example.invalid/v1/"
    )

    transport = transport_module.DeepSeekProtocolAgentTransport(
        backend="deepseek",
        model="deepseek-v4-flash",
        reasoning_effort="max",
    )

    assert _FakeOpenAI.calls[0]["base_url"] == "https://example.invalid/v1"
    assert _FakeOpenAI.calls[0]["max_retries"] == 0
    kwargs = transport._completion_kwargs([{"role": "user", "content": "方案"}])
    assert kwargs["reasoning_effort"] == "max"
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
    assert "temperature" not in kwargs
    repair_kwargs = transport._completion_kwargs(
        [{"role": "user", "content": "修正"}],
        output_kind="semantic_rule_repair",
    )
    assert repair_kwargs["response_format"] == {"type": "json_object"}


def test_transport_rejects_unknown_output_kind():
    transport = transport_module.DeepSeekProtocolAgentTransport(
        client=object(),
        backend="omlx",
        model="Qwen3.8-27B-oQ8e-fp16-mtp",
    )

    with pytest.raises(ValueError, match="未知的方案解构输出类型"):
        transport._completion_kwargs(
            [{"role": "user", "content": "方案"}],
            output_kind="unexpected",  # type: ignore[arg-type]
        )


def test_executor_selects_omlx_without_deepseek_key(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module, "OMLX_BASE_URL", "http://127.0.0.1:8001")
    monkeypatch.setattr(transport_module, "OMLX_API_KEY", "")
    monkeypatch.setattr(executor_module, "DECONSTRUCT_BACKEND", "omlx")
    monkeypatch.setattr(executor_module, "DEEPSEEK_API_KEY", "")

    transport = executor_module._resolve_transport(
        SimpleNamespace(transport=None, transport_factory=None)
    )

    assert transport._backend == "omlx"
    assert _FakeOpenAI.calls[0]["api_key"] == "local-omlx"
    assert _FakeOpenAI.calls[0]["base_url"] == "http://127.0.0.1:8001/v1"


def test_executor_fails_closed_for_unknown_backend(monkeypatch):
    monkeypatch.setattr(executor_module, "DECONSTRUCT_BACKEND", "unexpected")

    with pytest.raises(StepFailure) as caught:
        executor_module._resolve_transport(
            SimpleNamespace(transport=None, transport_factory=None)
        )

    assert caught.value.error_code == "SEMANTIC_PROVIDER_UNSUPPORTED"
    assert caught.value.retryable is False


def test_executor_requires_deepseek_key_only_for_deepseek(monkeypatch):
    monkeypatch.setattr(executor_module, "DECONSTRUCT_BACKEND", "deepseek")
    monkeypatch.setattr(executor_module, "DEEPSEEK_API_KEY", "")

    with pytest.raises(StepFailure) as caught:
        executor_module._resolve_transport(
            SimpleNamespace(transport=None, transport_factory=None)
        )

    assert caught.value.error_code == "SEMANTIC_PROVIDER_UNAVAILABLE"
    assert caught.value.retryable is True


def test_missing_draft_error_retains_bounded_actionable_diagnostics():
    issue = ProtocolGateIssue(
        issue_code="AGENT_OUTPUT_SCHEMA_INVALID",
        check_name="tree_integrity",
        level="阻止发布",
        problem="proposed_rules 缺少冻结目录中的父规则",
        impact="草稿不能进入审阅",
        next_action="请在同一会话中返回完整语义候选",
        affected_refs=["protocol_draft"],
        repair_scope=["protocol_draft_json"],
    )
    result = ProtocolDeconstructionRunResult(
        status="需要核对",
        same_session_id="session-1",
        attempts=[
            ProtocolDeconstructionAttempt(
                attempt=1,
                session_id="session-1",
                raw_output_sha256="a" * 64,
                outcome="输出格式无效",
                issues=[issue],
            )
        ],
    )

    detail = executor_module._semantic_failure_detail(result)

    assert "AGENT_OUTPUT_SCHEMA_INVALID" in detail
    assert "请在同一会话中返回完整语义候选" in detail
    assert len(detail) < 4000
