"""OpenAI-compatible transport for Evidence Normalizer (bounded, same-session).

绑定 Evidence Normalizer 的模型选择与单会话修复历史，保持与其他语义 Agent
的隔离；provider 只决定 OpenAI-compatible connection profile。
GLM（zhipu-coding-plan）请求使用可观测流式传输：逐块累积、思考/正文分离、
严格完整结束校验；模型、提示词与校验行为与非流式路径保持一致。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from time import monotonic
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import httpx
from openai import OpenAI

from app.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    EVIDENCE_NORMALIZER_GLM_API_KEY,
    EVIDENCE_NORMALIZER_GLM_BASE_URL,
    EVIDENCE_NORMALIZER_GLM_REASONING_EFFORT,
    EVIDENCE_NORMALIZER_MAX_TOKENS,
    EVIDENCE_NORMALIZER_MODEL,
    EVIDENCE_NORMALIZER_PROVIDER,
    EVIDENCE_NORMALIZER_REASONING_EFFORT,
    EVIDENCE_NORMALIZER_TEMPERATURE,
    MTPLX_API_KEY,
    MTPLX_BASE_URL,
    OMLX_API_KEY,
    OMLX_BASE_URL,
)
from app.domain.contracts.agents import ModelConfigContract
from .evidence_normalizer import (
    EvidenceNormalizerAgentCallError,
    EvidenceNormalizerAgentResponse,
    SUPPORTED_GLM_NORMALIZER_REASONING_EFFORTS,
    ZHIPU_EVIDENCE_NORMALIZER_BACKENDS,
    evidence_normalizer_json_schema,
)


def _with_v1_suffix(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("证据规范化模型服务 base_url 不能为空")
    return normalized if normalized.endswith("/v1") else normalized + "/v1"


def _normalize_zhipu_coding_plan_base_url(base_url: str) -> str:
    """Keep Coding Plan ``.../paas/v4`` paths; do not append a stray ``/v1``."""

    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("GLM 证据规范化服务地址不能为空")
    if normalized.endswith("/v1") and "/paas/v4" in normalized:
        normalized = normalized[: -len("/v1")].rstrip("/")
    return normalized


def _map_glm_normalizer_reasoning_effort(effort: str) -> dict[str, Any]:
    """Map the frozen effort onto GLM-5.3-Flash's low/high/max vocabulary."""

    selected = str(effort or "").strip().lower()
    if selected in {"", "default", "auto"}:
        selected = EVIDENCE_NORMALIZER_GLM_REASONING_EFFORT or "high"
    if selected not in SUPPORTED_GLM_NORMALIZER_REASONING_EFFORTS:
        raise ValueError(
            "GLM 证据规范化推理强度仅支持 low/high/max，"
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


# GLM 流式传输的硬上限：块间不活动 600s（与客户端读超时一致）、
# 整条流总时长 1200s。两者都只在“块与块之间”检查，粒度说明见
# _assemble_glm_stream 的 docstring。
GLM_STREAM_INACTIVITY_LIMIT_SECONDS = 600.0
GLM_STREAM_TOTAL_LIMIT_SECONDS = 1200.0

# length 结束原因只重试一次，思考+正文共享预算最多抬升到该上限（R3 §6.1）。
EVIDENCE_NORMALIZER_LENGTH_RETRY_MAX_TOKENS = 131072


def _new_glm_stream_state() -> dict[str, Any]:
    return {
        "content_parts": [],
        "thought_parts": [],
        "usage": {},
        "response_model": None,
        "response_id": None,
        "finish": None,
    }


def _absorb_glm_stream_chunk(
    chunk: Any,
    state: dict[str, Any],
    *,
    allow_model_identity_change: bool = False,
) -> None:
    """累加单个 OpenAI SDK 流式块：思考/正文/usage 分离并记录实际模型身份。"""
    if chunk is None:
        return
    if getattr(chunk, "error", None):
        raise RuntimeError("GLM 流式响应包含服务错误，拒绝采信")
    model = getattr(chunk, "model", None)
    if model:
        if state["response_model"] and state["response_model"] != model:
            if not allow_model_identity_change:
                raise RuntimeError("GLM 流式响应模型身份发生变化")
            import logging

            logging.getLogger(__name__).warning(
                "网关在流中切换上游模型：%s -> %s（按网关多路上游记录，继续采信）",
                state["response_model"], model,
            )
        state["response_model"] = model
    chunk_id = getattr(chunk, "id", None)
    if chunk_id:
        state["response_id"] = chunk_id
    usage = getattr(chunk, "usage", None)
    if usage is not None:
        dumped = usage.model_dump() if hasattr(usage, "model_dump") else None
        if dumped:
            state["usage"] = dict(dumped)
    for choice in getattr(chunk, "choices", None) or []:
        delta = getattr(choice, "delta", None)
        if delta is not None:
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                state["thought_parts"].append(reasoning)
            content = getattr(delta, "content", None)
            if content:
                state["content_parts"].append(content)
        finish = getattr(choice, "finish_reason", None)
        if finish:
            state["finish"] = finish


def _assemble_glm_stream(
    stream: Any,
    state: dict[str, Any],
    *,
    clock: Callable[[], float] = monotonic,
    inactivity_limit: float = GLM_STREAM_INACTIVITY_LIMIT_SECONDS,
    total_limit: float = GLM_STREAM_TOTAL_LIMIT_SECONDS,
    allow_model_identity_change: bool = False,
) -> None:
    """严格组装 GLM 流式块；任何不完整都抛错，绝不返回部分结果。

    截止时间粒度（如实说明）：不活动与总时长上限都只能在“块与块之间”检查；
    同步迭代器在单个块上最多阻塞到客户端读超时（600s），因此实际总时长最多
    可能超出 total_limit 一个不活动窗口，块内挂起由客户端读超时兜底。

    ``allow_model_identity_change`` 供网关路由（cms-router 等）使用：网关
    会在流中途把请求切换到另一个上游，模型字段随之变化；此时记录最终身份
    并继续，不视为致命错误（2026-09-19 实测 deepseek 网关流）。
    """
    started = clock()
    last_activity = started
    for chunk in stream:
        now = clock()
        if now - last_activity > inactivity_limit:
            raise RuntimeError(
                f"GLM 流式响应块间隔超过 {inactivity_limit:g}s 不活动上限，拒绝继续等待"
            )
        if now - started > total_limit:
            raise RuntimeError(
                f"GLM 流式响应总时长超过 {total_limit:g}s 上限，拒绝继续等待"
            )
        _absorb_glm_stream_chunk(
            chunk, state, allow_model_identity_change=allow_model_identity_change,
        )
        last_activity = now
    if state["finish"] is None:
        raise RuntimeError("GLM 流式响应缺少 finish_reason，拒绝采信部分结果")


class DeepSeekEvidenceNormalizerTransport:
    """保持同一逻辑会话的 Evidence Normalizer 传输适配器（有界）。

    - 每个 start 创建新的 session_id 并记录首轮 prompt；
    - continue_session 在同一 session_id 上追加用户修复 prompt；
    - 使用同步 OpenAI 客户端，与现有 DeepSeekProtocolAgentTransport 行为一致；
    - 不隐藏传输失败的 session_id，便于审计恢复。
    """

    def __init__(
        self,
        *,
        backend: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: Mapping[str, Any] | None = None,
        client: Any | None = None,
        receipt_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._receipt_callback = receipt_callback
        selected_backend = (backend or EVIDENCE_NORMALIZER_PROVIDER).strip().lower()
        if selected_backend not in {
            "deepseek",
            "deepseek-api",
            "mtplx",
            "mtplx-api",
            "omlx",
            "local-omlx",
            "zhipu-coding-plan",
        }:
            raise ValueError(f"当前证据规范化任务不支持模型供应商 {selected_backend}")
        selected_reasoning_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else EVIDENCE_NORMALIZER_REASONING_EFFORT
        ).strip().lower()
        if selected_reasoning_effort not in {
            "",
            "default",
            "auto",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        }:
            raise ValueError("reasoning_effort 不是受支持的推理强度")
        if selected_backend in ZHIPU_EVIDENCE_NORMALIZER_BACKENDS:
            # GLM-5.3-Flash only accepts low/high/max; ""/default/auto resolve
            # to the configured GLM default. Fail here, before any request.
            _map_glm_normalizer_reasoning_effort(selected_reasoning_effort)
        self._backend = selected_backend
        self._model = (model if model is not None else EVIDENCE_NORMALIZER_MODEL).strip()
        self._reasoning_effort = selected_reasoning_effort
        self._max_tokens = (
            max_tokens if max_tokens is not None else EVIDENCE_NORMALIZER_MAX_TOKENS
        )
        self._temperature = (
            temperature if temperature is not None else EVIDENCE_NORMALIZER_TEMPERATURE
        )
        self._response_format = dict(response_format) if response_format is not None else None
        if client is not None:
            self._client = client
        else:
            if selected_backend in {"deepseek", "deepseek-api"}:
                selected_api_key = DEEPSEEK_API_KEY if api_key is None else api_key
                selected_base_url = DEEPSEEK_BASE_URL if base_url is None else base_url
                if not selected_api_key:
                    raise ValueError("DeepSeek 证据规范化服务尚未配置")
            elif selected_backend in {"mtplx", "mtplx-api"}:
                selected_api_key = MTPLX_API_KEY if api_key is None else api_key
                selected_base_url = MTPLX_BASE_URL if base_url is None else base_url
                selected_api_key = selected_api_key or "local-mtplx"
            elif selected_backend in ZHIPU_EVIDENCE_NORMALIZER_BACKENDS:
                selected_api_key = (
                    EVIDENCE_NORMALIZER_GLM_API_KEY if api_key is None else api_key
                )
                selected_base_url = (
                    EVIDENCE_NORMALIZER_GLM_BASE_URL if base_url is None else base_url
                )
                # Credential precheck reuse: same BigModel account chain as the
                # protocol-semantic GLM route; fail closed before any request
                # instead of silently substituting another provider.
                if not selected_api_key:
                    raise ValueError(
                        "GLM 证据规范化服务尚未配置"
                        "（缺少 EVIDENCE_NORMALIZER_GLM_API_KEY；"
                        "留空时按 DECONSTRUCT_GLM_API_KEY/"
                        "INDEPENDENT_VLM_API_KEY 复用同一 BigModel 凭据）"
                    )
            else:
                selected_api_key = OMLX_API_KEY if api_key is None else api_key
                selected_base_url = OMLX_BASE_URL if base_url is None else base_url
                selected_api_key = selected_api_key or "local-omlx"
            if selected_backend in {"mtplx", "mtplx-api", "omlx", "local-omlx"}:
                resolved_base_url = _with_v1_suffix(selected_base_url)
            elif selected_backend in ZHIPU_EVIDENCE_NORMALIZER_BACKENDS:
                resolved_base_url = _normalize_zhipu_coding_plan_base_url(
                    selected_base_url
                )
            else:
                resolved_base_url = selected_base_url
            client_options: dict[str, Any] = {}
            if selected_backend in ZHIPU_EVIDENCE_NORMALIZER_BACKENDS:
                # Match the approved protocol-semantic GLM route: do not inherit
                # ambient HTTP_PROXY for BigModel Coding Plan calls, and keep
                # retry bounding inside the normalizer runner (no stacked client
                # retries on an expensive long request).
                client_options["http_client"] = httpx.Client(trust_env=False)
                client_options["timeout"] = 600.0
                client_options["max_retries"] = 0
            self._client = OpenAI(
                api_key=selected_api_key,
                base_url=resolved_base_url,
                **client_options,
            )
        self._histories: dict[str, list[dict[str, str]]] = {}

    @property
    def enforces_output_json_schema(self) -> bool:
        """传输层是否已在 ``response_format`` 中用 JSON Schema 受限解码。

        为真时 Runner 构建的提示不再内嵌同一份 Schema（消除重复 Schema）；
        ``json_object`` 路由（DeepSeek/MTPLX/GLM）返回假，Schema 仍完整内嵌。
        """
        return (
            self._response_format is not None
            and self._response_format.get("type") == "json_schema"
        )

    def _completion_kwargs(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
        }
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        if self._response_format is not None:
            kwargs["response_format"] = self._response_format
        if self._reasoning_effort not in {"", "default", "auto"}:
            kwargs["reasoning_effort"] = self._reasoning_effort
        if (
            self._backend in {"mtplx", "mtplx-api"}
            and self._response_format is not None
            and self._response_format.get("type") == "json_schema"
        ):
            kwargs["extra_body"] = {"generation_mode": "ar"}
        if self._backend in ZHIPU_EVIDENCE_NORMALIZER_BACKENDS:
            glm_request = _map_glm_normalizer_reasoning_effort(self._reasoning_effort)
            kwargs["reasoning_effort"] = glm_request["reasoning_effort"]
            kwargs["extra_body"] = glm_request["extra_body"]
        return kwargs

    def _request(self, kwargs):
        started = monotonic()
        receipt = {"started_at": datetime.now(timezone.utc).isoformat(),
                   "provider": self._backend, "requested_model": self._model,
                   "max_tokens": kwargs["max_tokens"],
                   "reasoning_effort": kwargs.get("reasoning_effort")}
        try:
            from app.llm.mtplx_model_lifecycle import sync_mtplx_model_session

            with sync_mtplx_model_session(
                self._backend, str(getattr(self._client, "base_url", "")),
                self._model, self._reasoning_effort,
            ):
                result = self._client.chat.completions.create(**kwargs)
            choice = result.choices[0] if result.choices else None
            usage = getattr(result, "usage", None)
            receipt.update(response_model=getattr(result, "model", None),
                           response_id=getattr(result, "id", None),
                           finish_reason=getattr(choice, "finish_reason", None),
                           raw_text=getattr(getattr(choice, "message", None), "content", None),
                           usage=usage.model_dump() if usage is not None else {})
            return result
        except Exception as exc:
            receipt.update(error_type=type(exc).__name__, status_code=getattr(exc, "status_code", None))
            raise
        finally:
            receipt["elapsed_seconds"] = round(monotonic() - started, 3)
            if self._receipt_callback is not None:
                self._receipt_callback(receipt)

    def _request_stream(self, kwargs, *, strict_model_check: bool = True):
        """流式执行一次 GLM 请求：逐块观测，失败小票保留部分输出诊断。

        ``strict_model_check`` 供经网关路由的请求放宽：路由器会回填上游真实
        模型名（如 cms-deepseek-flash → deepseek-flash），身份仍记录在小票。
        """
        started = monotonic()
        receipt = {"mode": "stream",
                   "started_at": datetime.now(timezone.utc).isoformat(),
                   "provider": self._backend, "requested_model": self._model,
                   "max_tokens": kwargs["max_tokens"],
                   "reasoning_effort": kwargs.get("reasoning_effort")}
        state = _new_glm_stream_state()
        stream = None
        try:
            stream = self._client.chat.completions.create(**kwargs)
            _assemble_glm_stream(
                stream, state, allow_model_identity_change=not strict_model_check,
            )
            if strict_model_check and str(state["response_model"] or "").lower() != self._model.lower():
                raise RuntimeError("GLM 实际响应模型与请求模型不一致")
            content = "".join(state["content_parts"])
            thought = "".join(state["thought_parts"])
            receipt.update(response_model=state["response_model"],
                           response_id=state["response_id"],
                           finish_reason=state["finish"],
                           raw_text=content or None,
                           thought_characters=len(thought),
                           usage=dict(state["usage"]))
            return SimpleNamespace(
                model=state["response_model"], id=state["response_id"],
                usage=dict(state["usage"]),
                choices=[SimpleNamespace(
                    finish_reason=state["finish"],
                    message=SimpleNamespace(content=content),
                )],
            )
        except Exception as exc:
            # 小票不得携带请求细节：错误消息只进服务日志，小票仅记类型。
            import logging

            logging.getLogger(__name__).warning(
                "规范化流式调用失败（%s）：%.300s", type(exc).__name__, str(exc),
            )
            receipt.update(
                error_type=type(exc).__name__,
                status_code=getattr(exc, "status_code", None),
                finish_reason=state["finish"],
                raw_text="".join(state["content_parts"]) or None,
                thought_characters=len("".join(state["thought_parts"])),
                usage=dict(state["usage"]),
                partial_result=True,
            )
            raise
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
            receipt["elapsed_seconds"] = round(monotonic() - started, 3)
            if self._receipt_callback is not None:
                self._receipt_callback(receipt)

    def _streaming_completion(self, kwargs):
        """GLM 流式补全：length 重试一次并抬升预算（上限 131072）；仅接受 stop。"""
        stream_kwargs = dict(kwargs)
        stream_kwargs["stream"] = True
        stream_kwargs["stream_options"] = {"include_usage": True}
        completion = self._request_stream(stream_kwargs)
        if completion.choices and completion.choices[0].finish_reason == "length":
            retry_kwargs = dict(stream_kwargs)
            retry_kwargs["max_tokens"] = min(
                int(kwargs["max_tokens"]) * 2,
                EVIDENCE_NORMALIZER_LENGTH_RETRY_MAX_TOKENS,
            )
            if retry_kwargs["max_tokens"] > kwargs["max_tokens"]:
                completion = self._request_stream(retry_kwargs)
        finish = completion.choices[0].finish_reason if completion.choices else None
        if finish != "stop":
            raise RuntimeError(
                f"GLM 流式响应未完整结束（finish_reason={finish!r}），拒绝采信部分结果"
            )
        return completion

    def _complete(self, messages: list[dict[str, str]]) -> str:
        request_messages = [dict(message) for message in messages]
        kwargs = self._completion_kwargs(request_messages)
        try:
            if self._backend in ZHIPU_EVIDENCE_NORMALIZER_BACKENDS:
                completion = self._streaming_completion(kwargs)
            elif self._backend in {"deepseek", "deepseek-api"}:
                # 云端网关（cms-router）对长生成有短超时，非流式会在首字前被
                # 504 截断；与 GLM 道一致统一流式累积（2026-09-19 用户指令）。
                completion = self._request_stream(
                    {**kwargs, "stream": True,
                     "stream_options": {"include_usage": True}},
                    strict_model_check=False,
                )
            else:
                completion = self._request(kwargs)
                if completion.choices and completion.choices[0].finish_reason == "length":
                    retry_kwargs = dict(kwargs)
                    retry_kwargs["max_tokens"] = min(
                        int(kwargs["max_tokens"]) * 2,
                        EVIDENCE_NORMALIZER_LENGTH_RETRY_MAX_TOKENS,
                    )
                    if retry_kwargs["max_tokens"] > kwargs["max_tokens"]:
                        completion = self._request(retry_kwargs)
                finish = completion.choices[0].finish_reason if completion.choices else None
                if finish != "stop":
                    raise RuntimeError(
                        f"模型响应未完整结束（finish_reason={finish!r}），拒绝采信部分结果"
                    )
        except Exception as exc:  # noqa: BLE001
            raise EvidenceNormalizerAgentCallError(session_id="", message=str(exc)) from exc
        if not completion.choices or not completion.choices[0].message or completion.choices[0].message.content is None:
            raise EvidenceNormalizerAgentCallError(session_id="", message="模型返回空内容")
        text = completion.choices[0].message.content.strip()
        if not text:
            raise EvidenceNormalizerAgentCallError(session_id="", message="模型返回空字符串")
        return text

    def start(self, *, prompt: str) -> EvidenceNormalizerAgentResponse:
        session_id = f"evidence-normalizer-chat-{uuid4().hex}"
        messages = [{"role": "user", "content": prompt}]
        try:
            text = self._complete(messages)
        except EvidenceNormalizerAgentCallError as exc:
            exc.session_id = session_id
            raise
        self._histories[session_id] = messages + [{"role": "assistant", "content": text}]
        return EvidenceNormalizerAgentResponse(session_id=session_id, text=text)

    def continue_session(
        self, *, session_id: str, prompt: str
    ) -> EvidenceNormalizerAgentResponse:
        if session_id not in self._histories:
            raise EvidenceNormalizerAgentCallError(session_id=session_id, message="未找到对应会话历史")
        history = self._histories[session_id]
        messages = history + [{"role": "user", "content": prompt}]
        try:
            text = self._complete(messages)
        except EvidenceNormalizerAgentCallError as exc:
            exc.session_id = session_id
            raise
        self._histories[session_id] = messages + [{"role": "assistant", "content": text}]
        return EvidenceNormalizerAgentResponse(session_id=session_id, text=text)

    def restore_history(
        self, *, session_id: str, messages: Sequence[Mapping[str, str]]
    ) -> None:
        history: list[dict[str, str]] = []
        for message in messages:
            if set(message.keys()) != {"role", "content"}:
                raise ValueError("历史消息必须仅包含 role 与 content")
            if message["role"] not in {"user", "assistant", "system"}:
                raise ValueError("历史消息 role 仅支持 user/assistant/system")
            history.append({"role": str(message["role"]), "content": str(message["content"])})
        self._histories[session_id] = history

    def history(self, session_id: str) -> tuple[Mapping[str, str], ...]:
        if session_id not in self._histories:
            raise EvidenceNormalizerAgentCallError(session_id=session_id, message="未找到对应会话历史")
        return tuple(dict(message) for message in self._histories[session_id])


OpenAICompatibleEvidenceNormalizerTransport = DeepSeekEvidenceNormalizerTransport


def evidence_normalizer_transport_from_model_config(
    model_config: ModelConfigContract,
    *, receipt_callback: Callable[[dict[str, Any]], None] | None = None,
) -> DeepSeekEvidenceNormalizerTransport:
    """按已冻结模型配置创建 OpenAI 兼容传输，不静默替换供应商或模型。"""
    provider = model_config.provider.strip().lower()
    parameters = model_config.parameters
    max_tokens = int(parameters.get("max_tokens", EVIDENCE_NORMALIZER_MAX_TOKENS))
    raw_temperature = parameters.get(
        "temperature", EVIDENCE_NORMALIZER_TEMPERATURE
    )
    temperature = None if raw_temperature is None else float(raw_temperature)
    if provider in {"deepseek", "deepseek-api"}:
        if not DEEPSEEK_API_KEY:
            raise ValueError("DeepSeek 语义服务尚未配置")
        return DeepSeekEvidenceNormalizerTransport(
            backend=provider,
            receipt_callback=receipt_callback,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            model=model_config.model,
            reasoning_effort=model_config.reasoning_effort,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
    if provider in {"mtplx", "mtplx-api"}:
        from app.llm.mtplx_model_lifecycle import mtplx_deployment_fingerprint

        deployment = mtplx_deployment_fingerprint(
            provider, _with_v1_suffix(MTPLX_BASE_URL), model_config.model,
            model_config.reasoning_effort,
        )
        if model_config.parameters.get("mtplx_deployment_sha256") != deployment:
            raise ValueError("本次整理的模型加载配置已改变，请新建整理任务，历史结果仍保留")
        return DeepSeekEvidenceNormalizerTransport(
            backend=provider,
            receipt_callback=receipt_callback,
            api_key=MTPLX_API_KEY or "local-mtplx",
            base_url=_with_v1_suffix(MTPLX_BASE_URL),
            model=model_config.model,
            reasoning_effort=model_config.reasoning_effort,
            max_tokens=max_tokens,
            temperature=temperature,
            # MTPLX 的严格受限解码会关闭 MTP，页级长结构输出耗时显著增加。
            # Schema 仍完整进入提示，并由本地 Pydantic/来源闭包门禁强校验。
            response_format={"type": "json_object"},
        )
    if provider in {"omlx", "local-omlx"}:
        return DeepSeekEvidenceNormalizerTransport(
            backend=provider,
            receipt_callback=receipt_callback,
            api_key=OMLX_API_KEY or "local-omlx",
            base_url=_with_v1_suffix(OMLX_BASE_URL),
            model=model_config.model,
            reasoning_effort=model_config.reasoning_effort,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "evidence_normalizer_output",
                    "strict": True,
                    "schema": evidence_normalizer_json_schema(),
                },
            },
        )
    if provider == "zhipu-coding-plan":
        if not EVIDENCE_NORMALIZER_GLM_API_KEY:
            raise ValueError(
                "GLM 证据规范化服务尚未配置"
                "（缺少 EVIDENCE_NORMALIZER_GLM_API_KEY；"
                "留空时按 DECONSTRUCT_GLM_API_KEY/"
                "INDEPENDENT_VLM_API_KEY 复用同一 BigModel 凭据）；"
                "已拒绝创建传输，不会静默替换供应商或模型。"
            )
        return DeepSeekEvidenceNormalizerTransport(
            backend=provider,
            receipt_callback=receipt_callback,
            api_key=EVIDENCE_NORMALIZER_GLM_API_KEY,
            base_url=EVIDENCE_NORMALIZER_GLM_BASE_URL,
            model=model_config.model,
            reasoning_effort=model_config.reasoning_effort,
            max_tokens=max_tokens,
            temperature=temperature,
            # BigModel Coding Plan 端点与已批准的方案语义 GLM 路由一致，
            # 使用 json_object；结构仍由本地 Pydantic/来源闭包门禁强校验。
            response_format={"type": "json_object"},
        )
    raise ValueError(f"当前证据规范化任务不支持模型供应商 {model_config.provider}")
