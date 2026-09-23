"""OpenAI-compatible transport retaining one protocol-deconstruction conversation."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4

import httpx
from app.llm.generation_completion import local_early_length
from app.llm.omlx_schema_compat import decoding_response_format
from openai import (
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from app.config import (
    DECONSTRUCT_BACKEND,
    DECONSTRUCT_API_KEY,
    DECONSTRUCT_BASE_URL,
    DECONSTRUCT_GLM_API_KEY,
    DECONSTRUCT_GLM_BASE_URL,
    DECONSTRUCT_GLM_MODEL,
    DECONSTRUCT_GLM_REASONING_EFFORT,
    DECONSTRUCT_MAX_TOKENS,
    DECONSTRUCT_MODEL,
    DECONSTRUCT_REASONING_EFFORT,
    OMLX_PROTOCOL_BATCH_MAX_TOKENS,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    OMLX_API_KEY,
    OMLX_BASE_URL,
    MTPLX_API_KEY,
    MTPLX_BASE_URL,
    MTPLX_PROTOCOL_BATCH_MAX_TOKENS,
)
from app.llm.provider_profiles import (
    REMOTE_OPENAI_PROVIDERS,
    provider_default_headers,
    resolve_openai_connection,
)

from .protocol_deconstructor import (
    ProtocolAgentCallError,
    ProtocolAgentResponse,
    ProtocolOutputKind,
    protocol_output_response_format,
)


SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS = frozenset(
    {
        "deepseek",
        "omlx",
        "mtplx",
        "mtplx-api",
        "mlx-serve",
        "zhipu-coding-plan",
        "glm",
        "cms-router",
        "cms-smk",
        "opencode-go",
    }
)
_DEEPSEEK_BACKENDS = frozenset({"deepseek"})
_MTPLX_BACKENDS = frozenset({"mtplx", "mtplx-api"})
_ZHIPU_BACKENDS = frozenset({"zhipu-coding-plan", "glm"})
_MLX_SERVE_BACKENDS = frozenset({"mlx-serve"})
# 现场实测（2026-09-18，Flash-Next/xgrammar）：MTPLX 的语法引擎无法编译方案
# wire 合同——number/深层嵌套 items 会被判 unsatisfiable 或生成含 look-ahead
# 的正则后被自身拒绝。对这类后端改为“合同入提示词”，响应仍走宿主严格校验。
_GRAMMAR_INCOMPATIBLE_BACKENDS = frozenset({"mtplx"})
_LOCAL_STRUCTURED_BACKENDS = frozenset(
    {"omlx", *_MTPLX_BACKENDS, *_MLX_SERVE_BACKENDS}
)
_SUPPORTED_GLM53_REASONING_EFFORTS = frozenset({"low", "high", "max"})

# mlx-serve local OpenAI-compatible server keeps an independent connection
# profile: it is never relabeled as omlx and never inherits the oMLX or MTPLX
# endpoint or model identity.  The model must be configured explicitly; there
# is no silent cross-provider default.  (Connection constants live here because
# this backend is transport-owned; app/config.py keeps the existing profiles.)
MLX_SERVE_BASE_URL = os.getenv("MLX_SERVE_BASE_URL", "http://127.0.0.1:11234").strip()
MLX_SERVE_API_KEY = os.getenv("MLX_SERVE_API_KEY", "")
MLX_SERVE_MODEL = os.getenv("MLX_SERVE_MODEL", "").strip()


def _unwrap_complete_json_fence(text: str) -> str:
    """Remove only a complete Markdown fence around one JSON response.

    Provider/model changes must not require prompt-specific parsers.  This
    compatibility step changes no JSON bytes inside the fence and deliberately
    rejects prose prefixes, suffixes, partial fences, and guessed repairs.
    """

    stripped = text.strip()
    lines = stripped.splitlines()
    if (
        len(lines) >= 3
        and lines[0].strip().lower() in {"```json", "```"}
        and lines[-1].strip() == "```"
    ):
        return "\n".join(lines[1:-1]).strip()
    return stripped
MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS = int(
    os.getenv("MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", "8192")
)

logger = logging.getLogger(__name__)

# Transient provider-side failures are retried against the identical request
# payload, so a retry can never change the logical session or model routing.
# Timeouts are deliberately excluded: they surface as TRANSPORT_TIMEOUT and
# the segment runner recovers them with a fresh transport at most once.
TRANSPORT_TRANSIENT_MAX_ATTEMPTS = 3
TRANSPORT_TRANSIENT_RETRY_BACKOFF_SECONDS = 2.0
# One length-finish retry may raise the output budget once, but the shared
# reasoning+content budget never exceeds this ceiling (R3 design §6.1).
PROTOCOL_LENGTH_RETRY_MAX_TOKENS = 131072
_TRANSPORT_TIMEOUT_ERRORS: tuple[type[Exception], ...] = (
    APITimeoutError,
    httpx.TimeoutException,
    TimeoutError,
)
_TRANSIENT_RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
    InternalServerError,
    RateLimitError,
    APIConnectionError,
    httpx.TransportError,
)


def _quota_exhausted(error: Exception, backend: str) -> bool:
    if backend not in _ZHIPU_BACKENDS or not isinstance(error, RateLimitError):
        return False
    body = error.body
    if not isinstance(body, Mapping):
        return False
    detail = body.get("error", body)
    # https://docs.bigmodel.cn/cn/api/api-code: quota windows, not rate throttling.
    return isinstance(detail, Mapping) and str(detail.get("code")) in {"1308", "1310"}


def _with_v1_suffix(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/v1") else normalized + "/v1"


def _normalize_zhipu_coding_plan_base_url(base_url: str) -> str:
    """Keep Coding Plan ``.../paas/v4`` paths; do not append a stray ``/v1``."""

    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("GLM 方案解构服务地址不能为空")
    if normalized.endswith("/v1") and "/paas/v4" in normalized:
        normalized = normalized[: -len("/v1")].rstrip("/")
    return normalized


def _map_glm_reasoning_effort(effort: str) -> dict[str, Any]:
    selected = str(effort or "").strip().lower()
    if selected in {"", "default", "auto"}:
        selected = DECONSTRUCT_GLM_REASONING_EFFORT or "high"
    if selected not in _SUPPORTED_GLM53_REASONING_EFFORTS:
        raise ValueError(
            "GLM 方案解构推理强度仅支持 low/high/max，"
            f"当前值={selected or '空值'}"
        )
    return {
        "reasoning_effort": selected,
        "extra_body": {
            "thinking": {
                "type": "enabled",
                "clear_thinking": False,
            }
        },
    }


class DeepSeekProtocolAgentTransport:
    """Keep repair calls in the same logical chat history.

    All supported providers expose a stateless OpenAI-compatible endpoint.
    The local session ID therefore identifies an immutable message history held
    by this transport; every repair sends the complete prior user/assistant
    exchange.  A repair can never silently become a fresh prompt.
    """

    def __init__(
        self,
        *,
        client: Any | None = None,
        backend: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        provider_defaults: bool = True,
        compact_wire: bool | None = None,
        bounded_batch_context: bool | None = None,
    ) -> None:
        # Preserve the historical class behavior for direct callers that pass a
        # DeepSeek model but omit the newly introduced backend selector.  The
        # The application path passes backend explicitly; direct callers can
        # still select a historical DeepSeek model by name.
        inferred_backend = (
            "deepseek"
            if model is not None and model.strip().lower().startswith("deepseek")
            else "mtplx"
            if model is not None and model.strip().lower().startswith("mtplx-")
            else "zhipu-coding-plan"
            if model is not None and model.strip().lower().startswith("glm-")
            else None
        )
        selected_backend = (
            backend or inferred_backend or DECONSTRUCT_BACKEND
        ).strip().lower()
        if selected_backend not in SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS:
            raise ValueError(
                f"当前方案解构不支持模型供应商 {selected_backend or '空值'}"
            )
        selected_model = model if model is not None else (
            DECONSTRUCT_GLM_MODEL
            if selected_backend in _ZHIPU_BACKENDS
            else MLX_SERVE_MODEL
            if selected_backend in _MLX_SERVE_BACKENDS
            else DECONSTRUCT_MODEL
        )
        if selected_backend in _MLX_SERVE_BACKENDS and not selected_model.strip():
            raise ValueError(
                "mlx-serve 方案解构模型必须显式配置："
                "请设置 MLX_SERVE_MODEL 或显式传入 model，"
                "不会回退到 oMLX/MTPLX 的默认模型。"
            )
        # ``provider_defaults`` only removes the product-side sampling overrides
        # (temperature) so the platform's own default
        # sampling applies.  Prompts and the strict output schema are never
        # changed by this flag.  New direct calls default to the provider
        # sampling defaults (R3 design §6.1: 不传 temperature); an explicit
        # ``provider_defaults=False`` keeps the historical product-side
        # overrides for frozen legacy identities.
        self._provider_defaults = bool(provider_defaults)
        if compact_wire is not None and (
            type(compact_wire) is not bool
            or selected_backend not in _LOCAL_STRUCTURED_BACKENDS
        ):
            raise ValueError("输出合同选择仅适用于本地方案解构，且必须为布尔值")
        self._compact_wire = compact_wire
        selected_reasoning_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else (
                DECONSTRUCT_GLM_REASONING_EFFORT
                if selected_backend in _ZHIPU_BACKENDS
                else DECONSTRUCT_REASONING_EFFORT
            )
        )
        selected_max_tokens = (
            max_tokens if max_tokens is not None else DECONSTRUCT_MAX_TOKENS
        )
        if selected_backend in _ZHIPU_BACKENDS or selected_model.lower().startswith("glm-"):
            # Validate against GLM vocabulary before storing.
            _map_glm_reasoning_effort(selected_reasoning_effort)
        elif selected_reasoning_effort not in {
            "",
            "default",
            "auto",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        }:
            raise ValueError("方案解构推理强度不是受支持的值")
        if selected_max_tokens < 8192:
            raise ValueError("方案解构输出上限不能低于 8192 tokens")
        self._backend = selected_backend
        self._model = selected_model
        self._reasoning_effort = selected_reasoning_effort
        # Only an explicitly requested effort is forwarded on the oMLX /
        # mlx-serve wire (including xhigh); an env-inherited default must not
        # silently change the legacy request shape of existing product runs.
        self._reasoning_effort_requested = (
            selected_reasoning_effort
            if reasoning_effort is not None
            and selected_reasoning_effort not in {"", "default", "auto"}
            else None
        )
        local_cap = (
            MTPLX_PROTOCOL_BATCH_MAX_TOKENS
            if selected_backend in _MTPLX_BACKENDS
            else MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS
            if selected_backend in _MLX_SERVE_BACKENDS
            else OMLX_PROTOCOL_BATCH_MAX_TOKENS
        )
        if (
            selected_backend in _LOCAL_STRUCTURED_BACKENDS
            and selected_max_tokens > local_cap
        ):
            # An explicitly requested budget above the configured platform cap
            # must fail before any request; never silently min() shrink it.
            cap_env = (
                "MTPLX_PROTOCOL_BATCH_MAX_TOKENS"
                if selected_backend in _MTPLX_BACKENDS
                else "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS"
                if selected_backend in _MLX_SERVE_BACKENDS
                else "OMLX_PROTOCOL_BATCH_MAX_TOKENS"
            )
            raise ValueError(
                f"显式请求的方案解构输出预算 {selected_max_tokens} tokens 超过"
                f"平台批次上限 {cap_env}={local_cap}；请调高上限或降低请求，"
                "不会静默压缩显式请求。"
            )
        self._max_tokens = selected_max_tokens
        self._output_budget_limit = (
            min(local_cap, PROTOCOL_LENGTH_RETRY_MAX_TOKENS)
            if selected_backend in _LOCAL_STRUCTURED_BACKENDS
            else PROTOCOL_LENGTH_RETRY_MAX_TOKENS
        )
        if self._max_tokens < 8192:
            raise ValueError("方案解构批次输出上限不能低于 8192 tokens")
        if client is not None:
            self._client = client
        else:
            if selected_backend in _DEEPSEEK_BACKENDS:
                selected_api_key = DEEPSEEK_API_KEY if api_key is None else api_key
                selected_base_url = DEEPSEEK_BASE_URL if base_url is None else base_url
                if not selected_api_key:
                    raise ValueError("DeepSeek 方案解构服务尚未配置")
                resolved_base_url = _with_v1_suffix(selected_base_url)
            elif selected_backend in _MTPLX_BACKENDS:
                selected_api_key = MTPLX_API_KEY if api_key is None else api_key
                selected_base_url = MTPLX_BASE_URL if base_url is None else base_url
                selected_api_key = selected_api_key or "local-mtplx"
                resolved_base_url = _with_v1_suffix(selected_base_url)
            elif selected_backend in _MLX_SERVE_BACKENDS:
                selected_api_key = MLX_SERVE_API_KEY if api_key is None else api_key
                selected_base_url = MLX_SERVE_BASE_URL if base_url is None else base_url
                # mlx-serve is local and does not require a secret, but the
                # OpenAI client still needs a non-empty placeholder key.
                selected_api_key = selected_api_key or "local-mlx-serve"
                resolved_base_url = _with_v1_suffix(selected_base_url)
            elif selected_backend in _ZHIPU_BACKENDS:
                selected_api_key = (
                    DECONSTRUCT_GLM_API_KEY if api_key is None else api_key
                )
                selected_base_url = (
                    DECONSTRUCT_GLM_BASE_URL if base_url is None else base_url
                )
                if not selected_api_key:
                    raise ValueError("GLM 方案解构服务尚未配置")
                resolved_base_url = _normalize_zhipu_coding_plan_base_url(
                    selected_base_url
                )
            elif selected_backend in REMOTE_OPENAI_PROVIDERS:
                resolved_base_url, selected_api_key = resolve_openai_connection(
                    selected_backend,
                    base_url=base_url or DECONSTRUCT_BASE_URL,
                    api_key=api_key or DECONSTRUCT_API_KEY,
                    role_base_url_env="DECONSTRUCT_BASE_URL",
                    role_api_key_env="DECONSTRUCT_API_KEY",
                )
            else:
                selected_api_key = OMLX_API_KEY if api_key is None else api_key
                selected_base_url = OMLX_BASE_URL if base_url is None else base_url
                # oMLX is local and does not require a secret, but the OpenAI
                # client still needs a non-empty placeholder key.
                selected_api_key = selected_api_key or "local-omlx"
                resolved_base_url = _with_v1_suffix(selected_base_url)
            client_options: dict[str, Any] = {}
            if selected_backend in _LOCAL_STRUCTURED_BACKENDS:
                # Local inference must never be routed through a system HTTP
                # proxy. A proxy can return an early 502 while oMLX continues
                # generating, leaving the product with a false transport
                # failure and an orphaned expensive request.
                client_options["http_client"] = httpx.Client(trust_env=False)
            elif selected_backend in _ZHIPU_BACKENDS:
                # Match Independent VLM: do not inherit ambient HTTP_PROXY for
                # BigModel Coding Plan calls.
                client_options["http_client"] = httpx.Client(trust_env=False)
            default_headers = provider_default_headers(
                selected_backend,
                session_id=f"enrollment-review-protocol:{uuid4().hex}",
            )
            if default_headers is not None:
                client_options["default_headers"] = default_headers
            self._client = OpenAI(
                base_url=resolved_base_url,
                api_key=selected_api_key,
                timeout=600.0,
                max_retries=0,
                **client_options,
            )
        self._histories: dict[str, list[dict[str, str]]] = {}
        self._output_scope: dict[str, Any] = {}
        self._bounded_batch_context = bounded_batch_context

    def configure_output_scope(
        self,
        *,
        official_codes: Sequence[str],
        allowed_source_span_ids: Sequence[str],
        component_limit: int,
        group_limit: int,
        atom_limit: int,
        requirement_limit: int,
    ) -> None:
        """Constrain strict output to the current frozen semantic batch."""
        self._output_scope = {
            "official_codes": tuple(official_codes),
            "allowed_source_span_ids": tuple(allowed_source_span_ids),
            "component_limit": component_limit,
            "group_limit": group_limit,
            "atom_limit": atom_limit,
            "requirement_limit": requirement_limit,
        }

    def semantic_cache_identity(
        self,
        *,
        output_kind: ProtocolOutputKind,
    ) -> str:
        """Hash the provider/model/schema contract without credentials."""

        kwargs = self._completion_kwargs([], output_kind=output_kind)
        kwargs.pop("messages", None)
        payload = {
            "backend": self._backend,
            "model": self._model,
            "reasoning_effort": self._reasoning_effort,
            "request": kwargs,
        }
        from app.llm.mtplx_model_lifecycle import mtplx_deployment_identity

        deployment = mtplx_deployment_identity(
            self._backend, str(getattr(self._client, "base_url", "")),
            self._model, self._reasoning_effort,
        )
        if deployment:
            payload["deployment"] = deployment
        if self._bounded_batch_context is not None:
            payload["batch_context_policy"] = {
                "version": "explicit-batch-context/v1",
                "bounded": self._bounded_batch_context,
            }
        return hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    @property
    def uses_compact_wire_contract(self) -> bool:
        return (self._backend in _LOCAL_STRUCTURED_BACKENDS
                if self._compact_wire is None else self._compact_wire)

    @property
    def supports_bounded_batch_context(self) -> bool:
        if self._bounded_batch_context is not None:
            return self._bounded_batch_context
        return self._backend in _LOCAL_STRUCTURED_BACKENDS

    @property
    def supports_parent_rule_segmentation(self) -> bool:
        """Declare semantic segmentation separately from the wire format."""

        return self._backend in {
            *_LOCAL_STRUCTURED_BACKENDS,
            *_ZHIPU_BACKENDS,
            "cms-router",
            "cms-smk",
            "opencode-go",
            "deepseek",
        }

    def _completion_kwargs(
        self,
        messages: list[dict[str, str]],
        *,
        output_kind: ProtocolOutputKind = "semantic_candidate",
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        if output_kind not in {"semantic_candidate", "semantic_rule_repair"}:
            raise ValueError(f"未知的方案解构输出类型：{output_kind}")
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens if max_tokens is None else max_tokens,
            "response_format": {"type": "json_object"},
        }
        if (
            self._backend in _LOCAL_STRUCTURED_BACKENDS
            and self._backend not in _GRAMMAR_INCOMPATIBLE_BACKENDS
        ):
            kwargs["response_format"] = protocol_output_response_format(
                output_kind,
                compact=self.uses_compact_wire_contract,
                **self._output_scope,
            )
            if self._backend == "omlx":
                kwargs["response_format"] = decoding_response_format(kwargs["response_format"])
        if (
            self._backend in _DEEPSEEK_BACKENDS
            and self._model.startswith("deepseek-v4")
        ):
            if self._reasoning_effort not in {"", "default", "auto"}:
                kwargs["reasoning_effort"] = self._reasoning_effort
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        elif self._backend == "opencode-go":
            if self._reasoning_effort not in {"", "default", "auto"}:
                kwargs["reasoning_effort"] = self._reasoning_effort
        elif self._backend in {"cms-router", "cms-smk"}:
            if self._reasoning_effort not in {"", "default", "auto"}:
                kwargs["reasoning_effort"] = self._reasoning_effort
        elif self._backend in _MTPLX_BACKENDS:
            if self._reasoning_effort not in {"", "default", "auto"}:
                kwargs["reasoning_effort"] = self._reasoning_effort
            if not self._provider_defaults:
                kwargs["temperature"] = 0.0
            # Strict-schema compatibility is independent of sampling defaults.
            # Speculative decoding can advance ahead of the grammar state.
            kwargs["extra_body"] = {"generation_mode": "ar"}
        elif self._backend in _ZHIPU_BACKENDS:
            glm_thinking = _map_glm_reasoning_effort(self._reasoning_effort)
            kwargs["reasoning_effort"] = glm_thinking["reasoning_effort"]
            kwargs["extra_body"] = glm_thinking["extra_body"]
            if not self._provider_defaults:
                kwargs["temperature"] = 0.1
        elif self._backend in {*_MLX_SERVE_BACKENDS, "omlx"}:
            # oMLX and mlx-serve send the requested reasoning effort verbatim
            # (including xhigh) instead of silently dropping it; an effort that
            # merely came from ambient env defaults is not sent.
            if self._reasoning_effort_requested is not None:
                kwargs["reasoning_effort"] = self._reasoning_effort_requested
            if not self._provider_defaults:
                kwargs["temperature"] = 0.0
        elif not self._provider_defaults:
            kwargs["temperature"] = 0.1
        return kwargs

    def _accumulate_stream(self, stream: Any) -> Any:
        """把流式响应重组为下游已知的非流式对象（content/finish_reason/usage）。

        全模型统一 streaming（2026-09-18 用户指令）：本地/远端路由器对长生成
        的 per-request 空闲超时不再掐断深度思考；usage 依赖
        stream_options.include_usage，不支持的服务端自动降级重试。
        """
        from types import SimpleNamespace

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        finish_reason: str | None = None
        usage: Any = None
        for chunk in stream:
            if getattr(chunk, "usage", None) is not None:
                usage = chunk.usage
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            choice = choices[0]
            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue
            piece = getattr(delta, "content", None)
            if piece:
                content_parts.append(piece)
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                reasoning_parts.append(reasoning)
        message = SimpleNamespace(
            content="".join(content_parts),
            reasoning_content="".join(reasoning_parts),
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason=finish_reason or "未提供")],
            usage=usage,
        )

    def _send_completion(
        self,
        request_messages: list[dict[str, str]],
        *,
        output_kind: ProtocolOutputKind,
        max_tokens: int | None = None,
    ) -> Any:
        """Send one HTTP completion with bounded transient-error retries.

        Every attempt resends the identical request payload, so a retry can
        never mutate session history or switch the model route.  Only
        transient 5xx/429/connection failures are retried; timeouts and any
        other failure surface immediately through the existing boundary.
        """
        kwargs = self._completion_kwargs(
            request_messages,
            output_kind=output_kind,
            max_tokens=max_tokens,
        )
        last_exc: Exception | None = None
        for attempt in range(1, TRANSPORT_TRANSIENT_MAX_ATTEMPTS + 1):
            try:
                from app.llm.mtplx_model_lifecycle import sync_mtplx_model_session

                with sync_mtplx_model_session(
                    self._backend, str(getattr(self._client, "base_url", "")),
                    self._model, self._reasoning_effort,
                ):
                    kwargs["stream"] = True
                    kwargs.setdefault("stream_options", {"include_usage": True})
                    try:
                        stream = self._client.chat.completions.create(**kwargs)
                        return self._accumulate_stream(stream)
                    except Exception as stream_opt_exc:
                        if "stream_options" not in str(stream_opt_exc):
                            raise
                        kwargs.pop("stream_options", None)
                        stream = self._client.chat.completions.create(**kwargs)
                        return self._accumulate_stream(stream)
            except _TRANSPORT_TIMEOUT_ERRORS:
                raise
            except _TRANSIENT_RETRYABLE_ERRORS as exc:
                if _quota_exhausted(exc, self._backend):
                    raise
                last_exc = exc
                if attempt >= TRANSPORT_TRANSIENT_MAX_ATTEMPTS:
                    break
                wait = TRANSPORT_TRANSIENT_RETRY_BACKOFF_SECONDS * attempt
                logger.warning(
                    "方案解构模型服务出现暂态传输错误（第%d/%d次尝试），%.1f秒后重试：%s",
                    attempt,
                    TRANSPORT_TRANSIENT_MAX_ATTEMPTS,
                    wait,
                    exc,
                )
                time.sleep(wait)
        assert last_exc is not None
        raise last_exc

    def _complete(
        self,
        messages: list[dict[str, str]],
        *,
        output_kind: ProtocolOutputKind,
    ) -> str:
        request_messages = [dict(message) for message in messages]
        diagnostics: list[str] = []
        length_attempts = 0
        malformed_attempts = 0
        # One logical request carries one shared reasoning+content budget; a
        # single length-finish retry may raise it once, capped, never silently.
        request_budget = self._max_tokens
        for attempt in range(2):
            response = self._send_completion(
                request_messages,
                output_kind=output_kind,
                max_tokens=request_budget,
            )
            choice = response.choices[0]
            message = choice.message
            text = message.content or ""
            reasoning_chars = len(getattr(message, "reasoning_content", "") or "")
            finish_reason = getattr(choice, "finish_reason", None) or "未提供"
            if finish_reason == "length":
                if local_early_length(self._backend, getattr(response, "usage", None), request_budget):
                    raise RuntimeError(
                        "方案解构模型在额度用尽前停止，结果不完整；不扩大额度或重复原请求，需核查运行原因"
                    )
                length_attempts += 1
                diagnostics.append(
                    f"第{attempt + 1}次结束原因=length（请求预算{request_budget} tokens），"
                    f"输出已被长度上限截断，"
                    f"正文长度={len(text) if isinstance(text, str) else 0}"
                )
                if attempt == 0:
                    retry_budget = min(
                        request_budget * 2,
                        PROTOCOL_LENGTH_RETRY_MAX_TOKENS,
                    )
                    if retry_budget <= request_budget:
                        break
                    if retry_budget > self._output_budget_limit:
                        diagnostics.append("扩大后的输出额度超过本地服务上限，未发送重试")
                        break
                    if retry_budget > request_budget:
                        diagnostics.append(
                            f"第2次请求预算提升至{retry_budget} tokens"
                            "（思考与正文共享额度，最多一次）"
                        )
                    request_budget = retry_budget
                    request_messages = [
                        *request_messages,
                        {
                            "role": "user",
                            "content": (
                                "上一请求的输出达到长度上限，正文不可作为完整JSON使用。"
                                "请不要重复分析，立即按上一请求指定的结构重新输出完整JSON对象，"
                                "不要附加解释。只处理原请求指定的1-3个父规则，"
                                "返回最小完整图；不要重复节点、组件、source_excerpts或其他批次内容。"
                            ),
                        },
                    ]
                    continue
                continue
            if text.strip():
                json_text = _unwrap_complete_json_fence(text)
                try:
                    parsed = json.loads(json_text)
                except json.JSONDecodeError as exc:
                    malformed_attempts += 1
                    diagnostics.append(
                        f"第{attempt + 1}次结束原因={finish_reason}，JSON无法解析，"
                        f"错误位置=第{exc.lineno}行第{exc.colno}列"
                    )
                    if attempt == 0:
                        request_messages = [
                            *request_messages,
                            {"role": "assistant", "content": text},
                            {
                                "role": "user",
                                "content": (
                                    "上一回包的JSON语法不完整，无法解析。"
                                    f"解析错误在第{exc.lineno}行第{exc.colno}列。"
                                    "请不要重复分析，只按原结构输出语法完整的JSON对象；"
                                    "不要附加解释，不要省略逗号、引号、括号或必填字段。"
                                ),
                            },
                        ]
                        continue
                    continue
                if not isinstance(parsed, dict):
                    malformed_attempts += 1
                    diagnostics.append(
                        f"第{attempt + 1}次结束原因={finish_reason}，JSON顶层不是对象"
                    )
                    if attempt == 0:
                        request_messages = [
                            *request_messages,
                            {"role": "assistant", "content": text},
                            {
                                "role": "user",
                                "content": (
                                    "上一回包顶层不是JSON对象。请不要重复分析，"
                                    "只按原请求的结构输出一个完整JSON对象，不要附加解释。"
                                ),
                            },
                        ]
                        continue
                    continue
                return json_text
            diagnostics.append(
                f"第{attempt + 1}次结束原因={finish_reason}，推理内容长度={reasoning_chars}"
            )
            if attempt == 0:
                request_messages = [
                    *request_messages,
                    {
                        "role": "user",
                        "content": (
                            "上一请求只产生了内部推理，没有返回可读取的JSON正文。"
                            "请不要重复分析，立即严格按上一请求指定的结构输出完整JSON对象，"
                            "不要附加解释。"
                        ),
                    },
                ]
        if length_attempts:
            raise RuntimeError(
                "方案解构模型连续2次未返回完整JSON，输出被长度上限截断（"
                + "；".join(diagnostics)
                + "）"
            )
        if malformed_attempts:
            raise RuntimeError(
                "方案解构模型连续2次未返回可解析的JSON对象（"
                + "；".join(diagnostics)
                + "）"
            )
        raise RuntimeError(
            "方案解构模型连续2次返回空正文（" + "；".join(diagnostics) + "）"
        )

    def _wire_contract_prompt(self, prompt: str, output_kind: ProtocolOutputKind) -> str:
        """语法约束不可用的后端：把 wire 合同 JSON 并入提示词，替代 response_format。

        嵌入版做瘦身（去 $defs、两三层后只留类型形状）：完整合同会显著改变
        prefill 长度形态，实测触发 Flash-Next qsa_prefill Metal kernel 的
        JIT 编译缺陷（服务端 500）；字段级约束由提示词散文合同与宿主严格
        校验共同保证。
        """

        if (
            self._backend not in _GRAMMAR_INCOMPATIBLE_BACKENDS
            or not self.uses_compact_wire_contract
        ):
            return prompt
        schema = protocol_output_response_format(
            output_kind,
            compact=True,
            **self._output_scope,
        )["json_schema"]["schema"]

        def slim(node: Any, depth: int) -> Any:
            if isinstance(node, list):
                return [slim(item, depth) for item in node]
            if not isinstance(node, dict):
                return node
            if "$ref" in node:
                return {"type": "object"}
            if depth >= 3:
                shallow: dict[str, Any] = {}
                if "type" in node:
                    shallow["type"] = node["type"]
                if "enum" in node:
                    shallow["enum"] = node["enum"]
                return shallow
            out: dict[str, Any] = {}
            for key, value in node.items():
                if key in {"title", "default", "$defs"}:
                    continue
                out[key] = slim(value, depth + 1)
            return out

        contract_json = json.dumps(slim(schema, 0), ensure_ascii=False)
        return (
            prompt
            + "\n\n【输出 JSON 合同（本服务语法约束不可用，以下合同取代服务端携带）】"
            + "你的整段响应必须是一个符合该 JSON Schema 的 JSON 对象；"
            + "宿主会按完整合同逐字段严格校验，任何多余或缺失字段都会被拒绝：\n"
            + contract_json
        )

    def start(
        self,
        *,
        prompt: str,
        output_kind: ProtocolOutputKind = "semantic_candidate",
    ) -> ProtocolAgentResponse:
        session_id = f"protocol-chat-{uuid4().hex}"
        history = [{"role": "user", "content": self._wire_contract_prompt(prompt, output_kind)}]
        self._histories[session_id] = history
        try:
            text = self._complete(history, output_kind=output_kind)
        except (APITimeoutError, httpx.TimeoutException, TimeoutError) as exc:
            raise ProtocolAgentCallError(
                session_id,
                str(exc),
                error_code="TRANSPORT_TIMEOUT",
            ) from exc
        except Exception as exc:
            raise ProtocolAgentCallError(
                session_id, str(exc),
                error_code="QUOTA_EXHAUSTED" if _quota_exhausted(exc, self._backend)
                else "SEMANTIC_CALL_FAILED",
            ) from exc
        history.append({"role": "assistant", "content": text})
        self._histories[session_id] = history
        return ProtocolAgentResponse(session_id=session_id, text=text)

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
        output_kind: ProtocolOutputKind = "semantic_candidate",
    ) -> ProtocolAgentResponse:
        if session_id not in self._histories:
            raise ValueError("找不到原方案解构会话，不能脱离上下文继续修正")
        history = [
            *self._histories[session_id],
            {"role": "user", "content": self._wire_contract_prompt(prompt, output_kind)},
        ]
        self._histories[session_id] = history
        try:
            text = self._complete(history, output_kind=output_kind)
        except (APITimeoutError, httpx.TimeoutException, TimeoutError) as exc:
            raise ProtocolAgentCallError(
                session_id,
                str(exc),
                error_code="TRANSPORT_TIMEOUT",
            ) from exc
        except Exception as exc:
            raise ProtocolAgentCallError(
                session_id, str(exc),
                error_code="QUOTA_EXHAUSTED" if _quota_exhausted(exc, self._backend)
                else "SEMANTIC_CALL_FAILED",
            ) from exc
        history.append({"role": "assistant", "content": text})
        self._histories[session_id] = history
        return ProtocolAgentResponse(session_id=session_id, text=text)

    def restore_history(
        self, *, session_id: str, messages: Sequence[Mapping[str, str]]
    ) -> None:
        """Restore one persisted stateless conversation without changing it."""

        if session_id in self._histories:
            raise ValueError("方案解构会话已存在，不能用持久记录覆盖")
        history = [dict(message) for message in messages]
        if not history or history[0].get("role") != "user":
            raise ValueError("持久方案解构会话必须从用户请求开始")
        expected_role = "user"
        for message in history:
            if message.get("role") != expected_role or not message.get("content", "").strip():
                raise ValueError("持久方案解构会话角色顺序或正文无效")
            expected_role = "assistant" if expected_role == "user" else "user"
        if history[-1]["role"] != "assistant":
            raise ValueError("只能从已有模型响应的完整方案解构会话恢复")
        self._histories[session_id] = history

    def compact_session_history(self, *, session_id: str, context: str) -> None:
        """Replace accumulated batch history with a bounded audit anchor."""

        if session_id not in self._histories:
            raise ValueError("找不到方案解构会话，不能压缩历史")
        if not context.strip():
            raise ValueError("方案解构会话压缩锚点不能为空")
        if len(context) > 12000:
            raise ValueError("方案解构会话压缩锚点超过 12000 字符操作上限")
        self._histories[session_id] = [
            {"role": "user", "content": context},
            {"role": "assistant", "content": "已保留冻结上下文和批次身份。"},
        ]

    def history(self, session_id: str) -> tuple[Mapping[str, str], ...]:
        """Expose a read-only copy for audit persistence and tests."""
        if session_id not in self._histories:
            raise ValueError("找不到方案解构会话")
        return tuple(dict(message) for message in self._histories[session_id])


# Keep the old import path stable while exposing the provider-neutral name to
# new callers.
OpenAICompatibleProtocolAgentTransport = DeepSeekProtocolAgentTransport
