"""DeepSeek transport retaining one protocol-deconstruction conversation."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4

from openai import OpenAI

from app.config import (
    DECONSTRUCT_MAX_TOKENS,
    DECONSTRUCT_MODEL,
    DECONSTRUCT_REASONING_EFFORT,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
)

from .protocol_deconstructor import ProtocolAgentCallError, ProtocolAgentResponse


class DeepSeekProtocolAgentTransport:
    """Keep repair calls in the same logical chat history.

    DeepSeek's OpenAI-compatible endpoint is stateless.  The local session ID
    therefore identifies an immutable message history held by this transport;
    every repair sends the complete prior user/assistant exchange.  A repair
    can never silently become a fresh prompt.
    """

    def __init__(
        self,
        *,
        client: Any | None = None,
        model: str = DECONSTRUCT_MODEL,
        reasoning_effort: str = DECONSTRUCT_REASONING_EFFORT,
        max_tokens: int = DECONSTRUCT_MAX_TOKENS,
    ) -> None:
        if reasoning_effort not in {"", "default", "auto", "high", "max"}:
            raise ValueError("方案解构推理强度只允许 default、high 或 max")
        if max_tokens < 8192:
            raise ValueError("方案解构输出上限不能低于 8192 tokens")
        self._client = client or OpenAI(
            base_url=DEEPSEEK_BASE_URL.rstrip("/") + "/v1",
            api_key=DEEPSEEK_API_KEY,
            timeout=600.0,
        )
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._max_tokens = max_tokens
        self._histories: dict[str, list[dict[str, str]]] = {}

    def _completion_kwargs(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
        }
        if self._model.startswith("deepseek-v4"):
            if self._reasoning_effort not in {"", "default", "auto"}:
                kwargs["reasoning_effort"] = self._reasoning_effort
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            kwargs["temperature"] = 0.1
        return kwargs

    def _complete(self, messages: list[dict[str, str]]) -> str:
        request_messages = [dict(message) for message in messages]
        diagnostics: list[str] = []
        for attempt in range(2):
            response = self._client.chat.completions.create(
                **self._completion_kwargs(request_messages)
            )
            choice = response.choices[0]
            message = choice.message
            text = message.content or ""
            if text.strip():
                return text
            reasoning_chars = len(getattr(message, "reasoning_content", "") or "")
            finish_reason = getattr(choice, "finish_reason", None) or "未提供"
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
        raise RuntimeError(
            "方案解构模型连续2次返回空正文（" + "；".join(diagnostics) + "）"
        )

    def start(self, *, prompt: str) -> ProtocolAgentResponse:
        session_id = f"protocol-chat-{uuid4().hex}"
        history = [{"role": "user", "content": prompt}]
        self._histories[session_id] = history
        try:
            text = self._complete(history)
        except Exception as exc:
            raise ProtocolAgentCallError(session_id, str(exc)) from exc
        history.append({"role": "assistant", "content": text})
        self._histories[session_id] = history
        return ProtocolAgentResponse(session_id=session_id, text=text)

    def continue_session(
        self, *, session_id: str, prompt: str
    ) -> ProtocolAgentResponse:
        if session_id not in self._histories:
            raise ValueError("找不到原方案解构会话，不能脱离上下文继续修正")
        history = [*self._histories[session_id], {"role": "user", "content": prompt}]
        self._histories[session_id] = history
        try:
            text = self._complete(history)
        except Exception as exc:
            raise ProtocolAgentCallError(session_id, str(exc)) from exc
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

    def history(self, session_id: str) -> tuple[Mapping[str, str], ...]:
        """Expose a read-only copy for audit persistence and tests."""
        if session_id not in self._histories:
            raise ValueError("找不到方案解构会话")
        return tuple(dict(message) for message in self._histories[session_id])
