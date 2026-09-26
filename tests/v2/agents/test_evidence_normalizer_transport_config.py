from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.agents import deepseek_evidence_normalizer_transport as transport_module
from app.domain.contracts.agents import ModelConfigContract
from app.agents.evidence_normalizer import (
    SUPPORTED_EVIDENCE_NORMALIZER_PROVIDERS,
    evidence_normalizer_json_schema,
    validate_evidence_normalizer_model_config,
)


ROOT = Path(__file__).resolve().parents[3]
_BIGMODEL_CODING_PLAN_URL = "https://open.bigmodel.cn/api/coding/paas/v4"


class _FakeOpenAI:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs):
        self.calls.append(kwargs)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: None))


def test_cms_normalizer_uses_provider_route_before_stale_role_route(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setenv("CMS_ROUTER_BASE_URL", "http://127.0.0.1:20128/v1")
    monkeypatch.setenv("CMS_ROUTER_API_KEY", "cms-key")
    monkeypatch.setenv("EVIDENCE_NORMALIZER_BASE_URL", "https://old.example/v1")
    monkeypatch.setenv("EVIDENCE_NORMALIZER_API_KEY", "old-key")
    transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="cms-router", model="deepseek-latest-cloud",
    )
    assert _FakeOpenAI.calls[-1]["api_key"] == "cms-key"
    assert _FakeOpenAI.calls[-1]["base_url"] == "http://127.0.0.1:20128/v1"


def test_ollama_normalizer_never_reuses_old_role_credentials(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setenv("EVIDENCE_NORMALIZER_BASE_URL", "http://old-gateway.example/v1")
    monkeypatch.setenv("EVIDENCE_NORMALIZER_API_KEY", "old-normalizer-key")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OLLAMA_API_KEY"):
        transport_module.DeepSeekEvidenceNormalizerTransport(
            backend="ollama-cloud", model="deepseek-v4.1-flash",
        )
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-only-key")
    transport = transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="ollama-cloud", model="deepseek-v4.1-flash",
    )
    assert _FakeOpenAI.calls[-1]["api_key"] == "ollama-only-key"
    assert _FakeOpenAI.calls[-1]["base_url"] == "https://ollama.com/v1"
    assert "response_format" not in transport._completion_kwargs([{"role": "user", "content": "诊断"}])


def test_ollama_normalizer_frozen_factory_keeps_text_mode(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-only-key")
    config = ModelConfigContract(
        model_config_id="ollama-normalizer", provider="ollama-cloud",
        model="deepseek-v4.1-flash", reasoning_effort="high",
        parameters={"max_tokens": 65536},
    )
    transport = transport_module.evidence_normalizer_transport_from_model_config(config)
    kwargs = transport._completion_kwargs([{"role": "user", "content": "诊断"}])
    assert kwargs["reasoning_effort"] == "high"
    assert "response_format" not in kwargs
    assert "temperature" not in kwargs


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = tuple(chunks)
        self.closed = False

    def __iter__(self):
        return iter(self._chunks)

    def close(self):
        self.closed = True


@pytest.mark.parametrize("model,finish", [("glm-5.3-flash", "stop"), ("wrong", "stop"), (None, "stop"), ("glm-5.3-flash", None)])
def test_glm_stream_closes_and_checks_actual_model(model, finish):
    stream = _FakeStream([_stream_chunk(content="{}", model=model, finish=finish)])
    transport = transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="zhipu-coding-plan", model="glm-5.3-flash",
        client=_glm_stream_client(lambda **kwargs: stream),
    )
    if model == "glm-5.3-flash" and finish == "stop":
        assert transport.start(prompt="test").text == "{}"
    else:
        with pytest.raises(Exception):
            transport.start(prompt="test")
    assert stream.closed


def _stream_chunk(*, content=None, reasoning=None, finish=None,
                  model="glm-5.3-flash", chunk_id="chatcmpl-glm-1", usage=None):
    """构造一个 OpenAI SDK 风格的流式块；usage 仅块（choices 为空）也支持。"""
    has_choice = content is not None or reasoning is not None or finish is not None
    return SimpleNamespace(
        model=model,
        id=chunk_id,
        usage=(
            SimpleNamespace(model_dump=lambda: dict(usage)) if usage else None
        ),
        choices=(
            [SimpleNamespace(finish_reason=finish,
                             delta=SimpleNamespace(content=content,
                                                   reasoning_content=reasoning))]
            if has_choice else []
        ),
    )


def _glm_stream_client(create):
    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )


@pytest.mark.parametrize("second_fails", [False, True])
def test_completion_receipts_preserve_length_retry_and_failure(second_fails):
    receipts, budgets = [], []
    def create(**kwargs):
        budgets.append(kwargs["max_tokens"])
        if len(budgets) == 2 and second_fails:
            raise TimeoutError("private request details must not enter receipt")
        if len(budgets) == 1:
            return _FakeStream([_stream_chunk(content="partial", finish="length")])
        return _FakeStream([_stream_chunk(
            content="{}", finish="stop", usage={"total_tokens": 10})])
    client = _glm_stream_client(create)
    transport = transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="zhipu-coding-plan", model="glm-5.3-flash", reasoning_effort="high",
        max_tokens=1024, client=client, receipt_callback=receipts.append)
    if second_fails:
        with pytest.raises(transport_module.EvidenceNormalizerAgentCallError):
            transport.start(prompt="private source prompt")
    else:
        assert transport.start(prompt="private source prompt").text == "{}"
    assert budgets == [1024, 2048]
    assert len(receipts) == 2
    assert receipts[0]["raw_text"] == "partial"
    assert receipts[0]["finish_reason"] == "length"
    assert receipts[1].get("error_type") == ("TimeoutError" if second_fails else None)
    assert all(r["elapsed_seconds"] >= 0 for r in receipts)
    assert "private" not in json.dumps(receipts)


def _config(*, provider: str, model: str, reasoning_effort: str = "medium"):
    return ModelConfigContract(
        model_config_id=f"cfg-{provider}",
        provider=provider,
        model=model,
        reasoning_effort=reasoning_effort,
        parameters={"max_tokens": 4321, "temperature": 0.1},
    )


def test_deepseek_factory_uses_frozen_model_and_reasoning_without_substitution(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module, "DEEPSEEK_API_KEY", "configured")
    monkeypatch.setattr(transport_module, "DEEPSEEK_BASE_URL", "https://example.invalid")

    transport = transport_module.evidence_normalizer_transport_from_model_config(
        _config(provider="deepseek", model="deepseek-v4-flash", reasoning_effort="max")
    )

    assert _FakeOpenAI.calls == [
        {"api_key": "configured", "base_url": "https://example.invalid"}
    ]
    kwargs = transport._completion_kwargs([{"role": "user", "content": "测试"}])
    assert kwargs["model"] == "deepseek-v4-flash"
    assert kwargs["reasoning_effort"] == "max"
    assert kwargs["max_tokens"] == 4321
    assert kwargs["temperature"] == 0.1
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "extra_body" not in kwargs


def test_omlx_factory_uses_frozen_model_and_normalizes_v1_url_once(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module, "OMLX_BASE_URL", "http://127.0.0.1:8000/v1/")
    monkeypatch.setattr(transport_module, "OMLX_API_KEY", "")

    transport = transport_module.evidence_normalizer_transport_from_model_config(
        _config(provider="omlx", model="local-evidence-model")
    )

    assert _FakeOpenAI.calls == [
        {"api_key": "local-omlx", "base_url": "http://127.0.0.1:8000/v1"}
    ]
    kwargs = transport._completion_kwargs([{"role": "user", "content": "测试"}])
    assert kwargs["model"] == "local-evidence-model"
    assert kwargs["reasoning_effort"] == "medium"
    assert kwargs["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "evidence_normalizer_output",
            "strict": True,
            "schema": evidence_normalizer_json_schema(),
        },
    }
    assert "extra_body" not in kwargs


def test_factory_omits_temperature_when_frozen_config_uses_vendor_default(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module, "MTPLX_BASE_URL", "http://127.0.0.1:8002")
    monkeypatch.setattr(transport_module, "MTPLX_API_KEY", "")
    config = ModelConfigContract(
        model_config_id="cfg-mtplx-default-sampling",
        provider="mtplx",
        model="mtplx-flash-next-optimized-speed",
        reasoning_effort="medium",
        parameters={"max_tokens": 4321},
    )

    import app.llm.mtplx_model_lifecycle as _lifecycle
    monkeypatch.setattr(_lifecycle, "mtplx_deployment_fingerprint",
                        lambda *args, **kwargs: None)
    transport = transport_module.evidence_normalizer_transport_from_model_config(
        config
    )

    kwargs = transport._completion_kwargs([{"role": "user", "content": "测试"}])
    assert "temperature" not in kwargs


def test_mtplx_factory_uses_json_object_so_mtp_remains_available(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module, "MTPLX_BASE_URL", "http://127.0.0.1:8002")
    monkeypatch.setattr(transport_module, "MTPLX_API_KEY", "")

    import app.llm.mtplx_model_lifecycle as _lifecycle
    monkeypatch.setattr(_lifecycle, "mtplx_deployment_fingerprint",
                        lambda *args, **kwargs: None)
    transport = transport_module.evidence_normalizer_transport_from_model_config(
        _config(provider="mtplx", model="mtplx-flash-next-optimized-speed")
    )

    kwargs = transport._completion_kwargs([{"role": "user", "content": "测试"}])
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "extra_body" not in kwargs


def test_factory_rejects_unknown_provider_instead_of_falling_back():
    with pytest.raises(ValueError, match="不支持模型供应商"):
        transport_module.evidence_normalizer_transport_from_model_config(
            _config(provider="unknown", model="must-not-run")
        )


# ---------------------------------------------------------------------------
# zhipu-coding-plan / GLM-5.3-Flash route (supplier-neutral access)
# ---------------------------------------------------------------------------


def test_supported_providers_include_zhipu_route_for_registration():
    assert "zhipu-coding-plan" in SUPPORTED_EVIDENCE_NORMALIZER_PROVIDERS


def test_zhipu_factory_uses_frozen_glm_route_and_bigmodel_endpoint(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(
        transport_module,
        "EVIDENCE_NORMALIZER_GLM_API_KEY",
        "glm-key",
    )
    monkeypatch.setattr(
        transport_module,
        "EVIDENCE_NORMALIZER_GLM_BASE_URL",
        f"{_BIGMODEL_CODING_PLAN_URL}/",
    )

    transport = transport_module.evidence_normalizer_transport_from_model_config(
        _config(
            provider="zhipu-coding-plan",
            model="glm-5.3-flash",
            reasoning_effort="high",
        )
    )

    assert len(_FakeOpenAI.calls) == 1
    client_kwargs = _FakeOpenAI.calls[0]
    assert client_kwargs["api_key"] == "glm-key"
    # Coding Plan 的 .../paas/v4 路径必须原样保留，不得追加 /v1。
    assert client_kwargs["base_url"] == _BIGMODEL_CODING_PLAN_URL
    assert client_kwargs["max_retries"] == 0
    assert client_kwargs["timeout"] == 600.0
    http_client = client_kwargs["http_client"]
    assert isinstance(http_client, httpx.Client)
    assert http_client.trust_env is False
    http_client.close()

    kwargs = transport._completion_kwargs([{"role": "user", "content": "测试"}])
    assert kwargs["model"] == "glm-5.3-flash"
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["extra_body"] == {
        "thinking": {"type": "enabled", "clear_thinking": False}
    }
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["max_tokens"] == 4321
    # 冻结配置显式给出的采样温度必须原样进入请求。
    assert kwargs["temperature"] == 0.1


def test_zhipu_factory_uses_vendor_default_sampling_when_config_omits_it(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module, "EVIDENCE_NORMALIZER_GLM_API_KEY", "glm-key")
    monkeypatch.setattr(
        transport_module, "EVIDENCE_NORMALIZER_GLM_BASE_URL", _BIGMODEL_CODING_PLAN_URL
    )
    config = ModelConfigContract(
        model_config_id="cfg-zhipu-default-sampling",
        provider="zhipu-coding-plan",
        model="glm-5.3-flash",
        reasoning_effort="low",
        parameters={"max_tokens": 4321},
    )

    transport = transport_module.evidence_normalizer_transport_from_model_config(config)

    kwargs = transport._completion_kwargs([{"role": "user", "content": "测试"}])
    assert kwargs["reasoning_effort"] == "low"
    assert "temperature" not in kwargs


def test_length_finish_reason_retries_once_with_double_output_budget():
    calls = []
    streams = iter(
        [
            _FakeStream([_stream_chunk(content='{"partial":', finish="length")]),
            _FakeStream([_stream_chunk(
                content='{"complete":true}', finish="stop")]),
        ]
    )

    def create(**kwargs):
        calls.append(kwargs)
        assert kwargs["stream"] is True
        return next(streams)

    transport = transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="zhipu-coding-plan",
        api_key="glm-key",
        base_url=_BIGMODEL_CODING_PLAN_URL,
        model="glm-5.3-flash",
        reasoning_effort="low",
        max_tokens=100,
        response_format={"type": "json_object"},
        client=_glm_stream_client(create),
    )

    response = transport.start(prompt="请输出完整 JSON")

    assert response.text == '{"complete":true}'
    assert [call["max_tokens"] for call in calls] == [100, 200]


def test_length_retry_budget_is_capped_at_131072():
    """length 只重试一次，思考+正文共享预算封顶 131072，不静默翻倍。"""

    calls = []
    streams = iter(
        [
            _FakeStream([_stream_chunk(content='{"partial":', finish="length")]),
            _FakeStream([_stream_chunk(
                content='{"complete":true}', finish="stop")]),
        ]
    )

    def create(**kwargs):
        calls.append(kwargs)
        return next(streams)

    transport = transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="zhipu-coding-plan",
        api_key="glm-key",
        base_url=_BIGMODEL_CODING_PLAN_URL,
        model="glm-5.3-flash",
        reasoning_effort="low",
        max_tokens=100000,
        response_format={"type": "json_object"},
        client=_glm_stream_client(create),
    )

    response = transport.start(prompt="请输出完整 JSON")

    assert response.text == '{"complete":true}'
    # 100000*2 > 131072：重试请求封顶 131072。
    assert [call["max_tokens"] for call in calls] == [100000, 131072]


# ---------------------------------------------------------------------------
# GLM 流式传输：严格组装、有界截止与部分输出拒绝
# ---------------------------------------------------------------------------


def test_glm_stream_normal_completion_separates_thought_content_usage_identity():
    receipts = []

    def create(**kwargs):
        assert kwargs["stream"] is True
        assert kwargs["stream_options"] == {"include_usage": True}
        return _FakeStream(
            [
                _stream_chunk(reasoning='{"候选'),
                _stream_chunk(reasoning="整理}..."),
                _stream_chunk(content='{"normalized"'),
                _stream_chunk(content=":true}"),
                _stream_chunk(finish="stop"),
                _stream_chunk(
                    usage={
                        "prompt_tokens": 12,
                        "completion_tokens": 34,
                        "total_tokens": 46,
                    }
                ),
            ]
        )

    transport = transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="zhipu-coding-plan",
        api_key="glm-key",
        base_url=_BIGMODEL_CODING_PLAN_URL,
        model="glm-5.3-flash",
        reasoning_effort="high",
        max_tokens=100,
        response_format={"type": "json_object"},
        client=_glm_stream_client(create),
        receipt_callback=receipts.append,
    )

    response = transport.start(prompt="private source prompt")

    assert response.text == '{"normalized":true}'
    # 会话语义保持不变：助手原文进入历史，修复轮可继续。
    assert transport.history(response.session_id)[-1]["content"] == '{"normalized":true}'
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["mode"] == "stream"
    # 实际模型身份被捕获，且提示词不进小票。
    assert receipt["response_model"] == "glm-5.3-flash"
    assert receipt["response_id"] == "chatcmpl-glm-1"
    assert receipt["requested_model"] == "glm-5.3-flash"
    assert receipt["finish_reason"] == "stop"
    assert receipt["raw_text"] == '{"normalized":true}'
    assert receipt["thought_characters"] == len('{"候选整理}...')
    assert receipt["usage"] == {
        "prompt_tokens": 12,
        "completion_tokens": 34,
        "total_tokens": 46,
    }
    assert receipt["elapsed_seconds"] >= 0
    assert "partial_result" not in receipt
    assert "private" not in json.dumps(receipts)


def test_glm_stream_length_retry_still_incomplete_rejects_partial_output():
    receipts, budgets = [], []

    def create(**kwargs):
        budgets.append(kwargs["max_tokens"])
        return _FakeStream([_stream_chunk(content='{"partial":', finish="length")])

    transport = transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="zhipu-coding-plan",
        api_key="glm-key",
        base_url=_BIGMODEL_CODING_PLAN_URL,
        model="glm-5.3-flash",
        reasoning_effort="low",
        max_tokens=100,
        response_format={"type": "json_object"},
        client=_glm_stream_client(create),
        receipt_callback=receipts.append,
    )

    with pytest.raises(
        transport_module.EvidenceNormalizerAgentCallError, match="未完整结束"
    ):
        transport.start(prompt="private source prompt")

    assert budgets == [100, 200]
    assert all(receipt["finish_reason"] == "length" for receipt in receipts)
    # 失败小票保留部分输出诊断，但部分结果绝不作为成功返回。
    assert receipts[1]["raw_text"] == '{"partial":'


def test_glm_stream_error_rejects_partial_and_keeps_failure_receipt():
    receipts = []

    class _BrokenStream:
        def __iter__(self):
            yield _stream_chunk(content='{"norm')
            raise httpx.RemoteProtocolError("connection interrupted")

    def create(**kwargs):
        return _BrokenStream()

    transport = transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="zhipu-coding-plan",
        api_key="glm-key",
        base_url=_BIGMODEL_CODING_PLAN_URL,
        model="glm-5.3-flash",
        reasoning_effort="low",
        max_tokens=100,
        response_format={"type": "json_object"},
        client=_glm_stream_client(create),
        receipt_callback=receipts.append,
    )

    with pytest.raises(
        transport_module.EvidenceNormalizerAgentCallError,
        match="connection interrupted",
    ):
        transport.start(prompt="private source prompt")

    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["error_type"] == "RemoteProtocolError"
    assert receipt["finish_reason"] is None
    assert receipt["raw_text"] == '{"norm'
    assert receipt["partial_result"] is True
    assert receipt["elapsed_seconds"] >= 0
    assert "private" not in json.dumps(receipts)


def test_glm_stream_missing_finish_rejects_partial_output():
    receipts = []

    def create(**kwargs):
        return _FakeStream([_stream_chunk(content='{"complete":true}')])

    transport = transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="zhipu-coding-plan",
        api_key="glm-key",
        base_url=_BIGMODEL_CODING_PLAN_URL,
        model="glm-5.3-flash",
        reasoning_effort="low",
        max_tokens=100,
        response_format={"type": "json_object"},
        client=_glm_stream_client(create),
        receipt_callback=receipts.append,
    )

    with pytest.raises(
        transport_module.EvidenceNormalizerAgentCallError, match="finish_reason"
    ):
        transport.start(prompt="private source prompt")

    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["error_type"] == "RuntimeError"
    assert receipt["finish_reason"] is None
    assert receipt["raw_text"] == '{"complete":true}'
    assert receipt["partial_result"] is True


def test_glm_stream_assembly_enforces_bounded_limits_between_chunks():
    def run(clock, chunks):
        state = transport_module._new_glm_stream_state()
        stream = _FakeStream([_stream_chunk(content="a") for _ in range(chunks)])
        transport_module._assemble_glm_stream(stream, state, clock=clock)

    # 总时长上限：每块间隔都不超 600s，但累计超过 1200s（600+600+100）。
    total_ticks = iter([0.0, 0.0, 600.0, 1200.0, 1300.0])
    with pytest.raises(RuntimeError, match="总时长"):
        run(lambda: next(total_ticks), chunks=4)

    # 块间不活动上限：两块之间间隔超过 600s。
    inactivity_ticks = iter([0.0, 0.0, 700.0])
    with pytest.raises(RuntimeError, match="不活动"):
        run(lambda: next(inactivity_ticks), chunks=2)


def test_zhipu_factory_fails_closed_without_credential(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module, "EVIDENCE_NORMALIZER_GLM_API_KEY", "")

    with pytest.raises(ValueError) as excinfo:
        transport_module.evidence_normalizer_transport_from_model_config(
            _config(
                provider="zhipu-coding-plan",
                model="glm-5.3-flash",
                reasoning_effort="high",
            )
        )

    message = str(excinfo.value)
    assert "缺少 EVIDENCE_NORMALIZER_GLM_API_KEY" in message
    assert "不会静默替换供应商或模型" in message
    # 凭据预检必须发生在任何客户端构建之前。
    assert _FakeOpenAI.calls == []


def test_zhipu_base_url_strips_stray_v1_suffix_keeping_paas_v4(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module, "EVIDENCE_NORMALIZER_GLM_API_KEY", "glm-key")
    monkeypatch.setattr(
        transport_module,
        "EVIDENCE_NORMALIZER_GLM_BASE_URL",
        f"{_BIGMODEL_CODING_PLAN_URL}/v1",
    )

    transport_module.evidence_normalizer_transport_from_model_config(
        _config(
            provider="zhipu-coding-plan",
            model="glm-5.3-flash",
            reasoning_effort="high",
        )
    )

    assert _FakeOpenAI.calls[0]["base_url"] == _BIGMODEL_CODING_PLAN_URL


def test_zhipu_factory_rejects_reasoning_effort_outside_glm_vocabulary(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(transport_module, "EVIDENCE_NORMALIZER_GLM_API_KEY", "glm-key")
    monkeypatch.setattr(
        transport_module, "EVIDENCE_NORMALIZER_GLM_BASE_URL", _BIGMODEL_CODING_PLAN_URL
    )

    with pytest.raises(ValueError, match="仅支持 low/high/max"):
        transport_module.evidence_normalizer_transport_from_model_config(
            _config(
                provider="zhipu-coding-plan",
                model="glm-5.3-flash",
                reasoning_effort="medium",
            )
        )

    assert _FakeOpenAI.calls == []


def test_zhipu_transport_maps_default_effort_to_configured_glm_default(monkeypatch):
    monkeypatch.setattr(
        transport_module, "EVIDENCE_NORMALIZER_GLM_REASONING_EFFORT", "max"
    )
    transport = transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="zhipu-coding-plan",
        api_key="glm-key",
        base_url=_BIGMODEL_CODING_PLAN_URL,
        model="glm-5.3-flash",
        reasoning_effort="",
        max_tokens=4321,
        response_format={"type": "json_object"},
    )

    kwargs = transport._completion_kwargs([{"role": "user", "content": "测试"}])
    assert kwargs["reasoning_effort"] == "max"
    assert kwargs["extra_body"] == {
        "thinking": {"type": "enabled", "clear_thinking": False}
    }


def test_validator_accepts_zhipu_provider_and_rejects_non_glm_effort():
    for effort in ("low", "high", "max"):
        validate_evidence_normalizer_model_config(
            _config(
                provider="zhipu-coding-plan",
                model="glm-5.3-flash",
                reasoning_effort=effort,
            ),
            require_normalizer_role=False,
        )
    for effort in ("medium", "xhigh", "default"):
        with pytest.raises(ValueError, match="仅支持 low/high/max"):
            validate_evidence_normalizer_model_config(
                _config(
                    provider="zhipu-coding-plan",
                    model="glm-5.3-flash",
                    reasoning_effort=effort,
                ),
                require_normalizer_role=False,
            )
    # 现有非 GLM 供应商不受 GLM 词表约束。
    validate_evidence_normalizer_model_config(
        _config(
            provider="mtplx",
            model="mtplx-flash-next-optimized-speed",
            reasoning_effort="medium",
        ),
        require_normalizer_role=False,
    )


def test_glm_credential_reuse_chain_and_defaults_via_config_probe():
    """凭据复用：Normalizer 密钥留空时按 DECONSTRUCT_GLM_API_KEY 复用。"""

    script = """
import json
from app.config import (
    EVIDENCE_NORMALIZER_GLM_API_KEY,
    EVIDENCE_NORMALIZER_GLM_BASE_URL,
    EVIDENCE_NORMALIZER_GLM_MODEL,
    EVIDENCE_NORMALIZER_GLM_REASONING_EFFORT,
)
print(json.dumps({
    "api_key": EVIDENCE_NORMALIZER_GLM_API_KEY,
    "base_url": EVIDENCE_NORMALIZER_GLM_BASE_URL,
    "model": EVIDENCE_NORMALIZER_GLM_MODEL,
    "effort": EVIDENCE_NORMALIZER_GLM_REASONING_EFFORT,
}, ensure_ascii=False))
"""

    def probe(extra_env: dict[str, str]) -> dict[str, str]:
        env = os.environ.copy()
        for name in (
            "EVIDENCE_NORMALIZER_GLM_API_KEY",
            "EVIDENCE_NORMALIZER_GLM_BASE_URL",
            "EVIDENCE_NORMALIZER_GLM_MODEL",
            "EVIDENCE_NORMALIZER_GLM_REASONING_EFFORT",
            "DECONSTRUCT_GLM_API_KEY",
            "INDEPENDENT_VLM_API_KEY",
        ):
            env.pop(name, None)
        env.update(extra_env)
        return json.loads(  # type: ignore[no-any-return]
            subprocess.check_output(
                [sys.executable, "-c", script], cwd=ROOT, env=env, text=True
            )
        )

    # 默认端点/模型与已批准的 zhipu-coding-plan GLM-5.3-Flash 路由一致。
    defaults = probe({})
    assert defaults["base_url"] == _BIGMODEL_CODING_PLAN_URL
    assert defaults["model"] == "glm-5.3-flash"
    assert defaults["effort"] == "high"
    assert defaults["api_key"] == ""

    # 密钥留空时复用 DECONSTRUCT_GLM_API_KEY（其自身回退 INDEPENDENT_VLM_API_KEY）。
    reused = probe({"INDEPENDENT_VLM_API_KEY": "reuse-key"})
    assert reused["api_key"] == "reuse-key"

    # 显式配置的 Normalizer 密钥优先，不被其他任务的密钥覆盖。
    own = probe(
        {
            "EVIDENCE_NORMALIZER_GLM_API_KEY": "own-key",
            "DECONSTRUCT_GLM_API_KEY": "deconstruct-key",
        }
    )
    assert own["api_key"] == "own-key"


def test_schema_enforcement_capability_is_true_only_for_json_schema_transports(monkeypatch):
    """受限解码传输不再需要提示内嵌 Schema；json_object 路由必须保留。"""
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)

    monkeypatch.setattr(transport_module, "OMLX_API_KEY", "")
    monkeypatch.setattr(transport_module, "OMLX_BASE_URL", "http://127.0.0.1:8000")
    omlx = transport_module.evidence_normalizer_transport_from_model_config(
        _config(provider="omlx", model="local-evidence-model")
    )
    assert omlx.enforces_output_json_schema is True

    monkeypatch.setattr(transport_module, "MTPLX_API_KEY", "")
    monkeypatch.setattr(transport_module, "MTPLX_BASE_URL", "http://127.0.0.1:8002")
    import app.llm.mtplx_model_lifecycle as _lifecycle
    monkeypatch.setattr(_lifecycle, "mtplx_deployment_fingerprint",
                        lambda *args, **kwargs: None)
    mtplx = transport_module.evidence_normalizer_transport_from_model_config(
        _config(provider="mtplx", model="mtplx-flash-next-optimized-speed")
    )
    assert mtplx.enforces_output_json_schema is False

    monkeypatch.setattr(transport_module, "DEEPSEEK_API_KEY", "configured")
    monkeypatch.setattr(transport_module, "DEEPSEEK_BASE_URL", "https://example.invalid")
    deepseek = transport_module.evidence_normalizer_transport_from_model_config(
        _config(provider="deepseek", model="deepseek-v4-flash")
    )
    assert deepseek.enforces_output_json_schema is False

    monkeypatch.setattr(transport_module, "EVIDENCE_NORMALIZER_GLM_API_KEY", "glm-key")
    monkeypatch.setattr(
        transport_module, "EVIDENCE_NORMALIZER_GLM_BASE_URL", _BIGMODEL_CODING_PLAN_URL
    )
    glm = transport_module.evidence_normalizer_transport_from_model_config(
        _config(provider="zhipu-coding-plan", model="glm-5.3-flash", reasoning_effort="high")
    )
    assert glm.enforces_output_json_schema is False


def test_explicit_json_schema_response_format_declares_enforcement(monkeypatch):
    _FakeOpenAI.calls.clear()
    monkeypatch.setattr(transport_module, "OpenAI", _FakeOpenAI)
    transport = transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="omlx",
        api_key="local-omlx",
        base_url="http://127.0.0.1:8000/v1",
        model="local-evidence-model",
        response_format={"type": "json_object"},
    )
    assert transport.enforces_output_json_schema is False
    transport = transport_module.DeepSeekEvidenceNormalizerTransport(
        backend="omlx",
        api_key="local-omlx",
        base_url="http://127.0.0.1:8000/v1",
        model="local-evidence-model",
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "evidence_normalizer_output",
                "strict": True,
                "schema": evidence_normalizer_json_schema(),
            },
        },
    )
    assert transport.enforces_output_json_schema is True
