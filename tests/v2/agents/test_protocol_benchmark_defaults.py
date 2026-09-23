"""方案解构传输的横评默认设置离线回归（无模型调用）。

覆盖：

- mlx-serve 显式本地结构化后端：独立身份（绝不伪装成 oMLX）、显式
  URL/模型配置、本地批次上限、占位密钥与本地直连（不走系统代理）；
- oMLX / mlx-serve 按请求原样传递 reasoning_effort（含 xhigh），空值或
  default/auto 不发送；GLM 后端仍只接受 low/high/max；
- ``provider_defaults`` 可选开关：仅去掉产品侧 temperature，保留 MTPLX
  generation_mode=ar 兼容措施，提示词与严格输出 Schema 不变；新直连缺省
  开启（不传 temperature，遵循供应商采样默认）；显式
  ``provider_defaults=False`` 保留历史产品侧覆盖；
- ``provider_defaults`` 改变语义缓存身份，避免跨采样设置复用缓存。
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace
from unittest.mock import Mock

from app.agents import protocol_semantic_transport as transport_module
from app.agents.protocol_semantic_transport import (
    DeepSeekProtocolAgentTransport,
    _unwrap_complete_json_fence,
)


USER_MESSAGE = [{"role": "user", "content": "横评离线回归提示"}]


def test_only_complete_json_fence_is_unwrapped_without_content_repair():
    payload = '{"source_text":"原文\"A\"","value":0}'
    assert _unwrap_complete_json_fence(f"```json\n{payload}\n```") == payload
    assert _unwrap_complete_json_fence(f"说明\n{payload}") == f"说明\n{payload}"
    assert _unwrap_complete_json_fence(f"```json\n{payload}") == f"```json\n{payload}"


def test_local_early_length_does_not_repeat_request(monkeypatch):
    monkeypatch.setattr(
        transport_module, "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", 131072
    )
    transport = _build("mlx-serve", model="test-model", max_tokens=12000)
    response = SimpleNamespace(
        usage=SimpleNamespace(completion_tokens=100),
        choices=[SimpleNamespace(finish_reason="length",
                                 message=SimpleNamespace(content="{}"))],
    )
    send = Mock(return_value=response)
    monkeypatch.setattr(transport, "_send_completion", send)
    with pytest.raises(RuntimeError, match="额度用尽前"):
        transport._complete(USER_MESSAGE, output_kind="semantic_candidate")
    assert send.call_count == 1


def _build(backend: str, **kwargs) -> DeepSeekProtocolAgentTransport:
    # Wire-format replay fixtures specify their historical budget explicitly;
    # they do not exercise new production deployment defaults.
    base: dict = {"client": object(), "backend": backend, "max_tokens": 8192}
    base.update(kwargs)
    return DeepSeekProtocolAgentTransport(**base)


def _kwargs(transport: DeepSeekProtocolAgentTransport) -> dict:
    return transport._completion_kwargs(list(USER_MESSAGE))


def test_mlx_serve_backend_uses_explicit_url_model_and_local_wire_contract(
    monkeypatch,
):
    monkeypatch.setattr(transport_module, "MLX_SERVE_BASE_URL", "http://127.0.0.1:11234")
    monkeypatch.setattr(transport_module, "MLX_SERVE_API_KEY", "")
    monkeypatch.setattr(transport_module, "MLX_SERVE_MODEL", "hub/qwen3-xhigh-test")
    # 显式 131072 请求必须在上限内原样生效，超限会显式拒绝而非静默压缩。
    monkeypatch.setattr(
        transport_module, "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", 131072
    )
    # 不注入 client：验证真实 OpenAI 客户端构造（仅构造，不联网）。
    transport = DeepSeekProtocolAgentTransport(
        backend="mlx-serve",
        reasoning_effort="xhigh",
        max_tokens=131072,
    )

    assert transport._backend == "mlx-serve"
    assert transport._model == "hub/qwen3-xhigh-test"
    assert transport._max_tokens == 131072
    assert transport.uses_compact_wire_contract is True
    assert transport.supports_parent_rule_segmentation is True
    # 本地服务：显式 /v1 端点 + 占位密钥 + 不继承系统代理。
    assert str(transport._client.base_url).rstrip("/") == "http://127.0.0.1:11234/v1"
    assert transport._client.api_key == "local-mlx-serve"
    assert transport._client._client.trust_env is False


def test_mlx_serve_is_never_renamed_to_omlx_in_cache_identity():
    mlx = _build(
        "mlx-serve",
        model="hub/qwen3-xhigh-test",
        reasoning_effort="xhigh",
    )
    omlx = _build("omlx", model="omlx-model", reasoning_effort="xhigh")

    assert mlx._backend != "omlx"
    assert (
        mlx.semantic_cache_identity(output_kind="semantic_candidate")
        != omlx.semantic_cache_identity(output_kind="semantic_candidate")
    )


def test_mlx_serve_requires_explicit_model_without_cross_provider_fallback(
    monkeypatch,
):
    monkeypatch.setattr(transport_module, "MLX_SERVE_MODEL", "")
    with pytest.raises(ValueError, match="MLX_SERVE_MODEL"):
        _build("mlx-serve")

    explicit = _build("mlx-serve", model="hub/qwen3-xhigh-test")
    assert explicit._model == "hub/qwen3-xhigh-test"


@pytest.mark.parametrize("backend", ["omlx", "mlx-serve"])
def test_local_backends_send_requested_reasoning_effort_including_xhigh(
    backend: str, monkeypatch
):
    monkeypatch.setattr(transport_module, "MLX_SERVE_MODEL", "hub/qwen3-xhigh-test")
    transport = _build(backend, model="any-model", reasoning_effort="xhigh")
    kwargs = _kwargs(transport)
    assert kwargs["reasoning_effort"] == "xhigh"


@pytest.mark.parametrize("backend", ["omlx", "mlx-serve"])
@pytest.mark.parametrize("unset", ["", "default", "auto"])
def test_local_backends_omit_reasoning_effort_when_unset(
    backend: str, unset: str, monkeypatch
):
    monkeypatch.setattr(transport_module, "MLX_SERVE_MODEL", "hub/qwen3-xhigh-test")
    transport = _build(backend, model="any-model", reasoning_effort=unset)
    assert "reasoning_effort" not in _kwargs(transport)


def test_glm_backend_still_rejects_xhigh():
    with pytest.raises(ValueError, match="low/high/max"):
        _build(
            "zhipu-coding-plan",
            model="glm-5.3-flash",
            reasoning_effort="xhigh",
            api_key="test-key",
        )


def test_default_keeps_provider_sampling_and_explicit_false_keeps_legacy(
    monkeypatch,
):
    monkeypatch.setattr(transport_module, "MLX_SERVE_MODEL", "hub/qwen3-xhigh-test")

    omlx = _kwargs(_build("omlx", model="omlx-model"))
    mlx = _kwargs(_build("mlx-serve", model="hub/qwen3-xhigh-test"))
    mtplx = _kwargs(_build("mtplx", model="mtplx-model"))

    # 新直连缺省 provider_defaults=True：不发送 temperature。
    assert "temperature" not in omlx
    assert "extra_body" not in omlx
    assert "temperature" not in mlx
    assert "extra_body" not in mlx
    assert "temperature" not in mtplx
    assert mtplx["extra_body"] == {"generation_mode": "ar"}
    # 严格输出 Schema 与提示词在默认路径下保持不变。
    for kwargs in (omlx, mlx, mtplx):
        assert kwargs["response_format"]["type"] == "json_schema"
        assert kwargs["response_format"]["json_schema"]["strict"] is True
        assert kwargs["messages"] == USER_MESSAGE

    legacy_omlx = _kwargs(_build("omlx", model="omlx-model", provider_defaults=False))
    legacy_mtplx = _kwargs(
        _build("mtplx", model="mtplx-model", provider_defaults=False)
    )
    # 显式 provider_defaults=False 保留历史产品侧采样覆盖。
    assert legacy_omlx["temperature"] == 0.0
    assert legacy_mtplx["temperature"] == 0.0
    assert legacy_mtplx["extra_body"] == {"generation_mode": "ar"}


def test_provider_defaults_true_removes_local_sampling_but_keeps_schema(monkeypatch):
    monkeypatch.setattr(transport_module, "MLX_SERVE_MODEL", "hub/qwen3-xhigh-test")

    omlx = _kwargs(_build("omlx", model="omlx-model", provider_defaults=True))
    mlx = _kwargs(
        _build(
            "mlx-serve",
            model="hub/qwen3-xhigh-test",
            reasoning_effort="xhigh",
            provider_defaults=True,
        )
    )
    mtplx = _kwargs(_build("mtplx", model="mtplx-model", provider_defaults=True))

    for kwargs in (omlx, mlx, mtplx):
        assert "temperature" not in kwargs
        # 提示词与严格 Schema 不受采样开关影响。
        assert kwargs["messages"] == USER_MESSAGE
        assert kwargs["response_format"]["type"] == "json_schema"
        assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert mlx["reasoning_effort"] == "xhigh"
    assert "extra_body" not in omlx
    assert "extra_body" not in mlx
    assert mtplx["extra_body"] == {"generation_mode": "ar"}


def test_glm_branch_honors_provider_defaults_flag():
    default_sampling = _kwargs(
        _build(
            "zhipu-coding-plan",
            model="glm-5.3-flash",
            reasoning_effort="high",
            api_key="test-key",
        )
    )
    assert "temperature" not in default_sampling
    assert default_sampling["extra_body"]["thinking"]["type"] == "enabled"

    legacy = _kwargs(
        _build(
            "zhipu-coding-plan",
            model="glm-5.3-flash",
            reasoning_effort="high",
            api_key="test-key",
            provider_defaults=False,
        )
    )
    assert legacy["temperature"] == 0.1
    assert legacy["extra_body"]["thinking"]["type"] == "enabled"


def test_provider_defaults_changes_semantic_cache_identity(monkeypatch):
    monkeypatch.setattr(transport_module, "MLX_SERVE_MODEL", "hub/qwen3-xhigh-test")
    legacy = _build("mtplx", model="mtplx-model", provider_defaults=False)
    platform = _build("mtplx", model="mtplx-model", provider_defaults=True)

    assert (
        legacy.semantic_cache_identity(output_kind="semantic_candidate")
        != platform.semantic_cache_identity(output_kind="semantic_candidate")
    )
