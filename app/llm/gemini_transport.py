"""google-antigravity Gemini native HTTP vision transport (product-owned).

从已验证的直连传输迁移（scripts/benchmark_direct_transports.py 的
google-antigravity 分支）。产品运行时不读取任何个人 harness、OMP/Hermes
或 home 配置：凭据只来自显式 env / product route，绝不写入日志。
传输保持采样默认：请求体不含 temperature。
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Mapping

import httpx

from app.llm.page_review_harness import PAGE_REVIEW_TIMEOUT_SECONDS, PageCompletion
from app.llm.gemini_oauth import access_token, invalidate

ANTIGRAVITY_USER_AGENT = (
    "antigravity/hub/2.8.0 (aidev_client; os_type=darwin; arch=arm64; cl=963137146)"
)
STREAM_PATH = "/v1internal:streamGenerateContent?alt=sse"
_ALLOWED_EFFORTS = {"low", "high"}
_FINISH_MAP = {
    "STOP": "stop",
    "completed": "stop",
    "MAX_TOKENS": "length",
    "SAFETY": "content_filter",
    "RECITATION": "content_filter",
    "BLOCKLIST": "content_filter",
    "PROHIBITED_CONTENT": "content_filter",
    "SPII": "content_filter",
}


class GeminiTransportError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(
        str(item.get("text", "")) for item in content if item.get("type") == "text"
    )


def _inline_image(data_url: str) -> dict[str, Any]:
    head, separator, data = data_url.partition(",")
    if not head.startswith("data:") or ";" not in head or not separator or not data:
        raise ValueError("页图像必须是 base64 内嵌数据")
    return {"inlineData": {"mimeType": head[5:].split(";", 1)[0], "data": data}}


def build_gemini_request(
    route, messages: list[dict[str, Any]], max_tokens: int
) -> dict[str, Any]:
    """单阶段主读消息 → 原生 streamGenerateContent 请求体。

    system 消息合并进 systemInstruction；user/assistant 分别映射为
    user/model 角色，不重写任何其他角色标签。
    """
    if route.reasoning_effort not in _ALLOWED_EFFORTS:
        raise ValueError(
            f"Gemini 判读 reasoning effort 仅支持 {sorted(_ALLOWED_EFFORTS)}"
        )
    if not route.project_id:
        raise ValueError("缺少 GEMINI_PROJECT_ID，拒绝发送 Gemini 请求")
    system_texts: list[str] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        if role not in {"system", "user", "assistant"}:
            raise ValueError(f"不支持的主读消息角色 {role!r}；拒绝改写角色标签")
        if role == "system":
            system_texts.append(_message_text(message.get("content")))
            continue
        content = message.get("content")
        parts: list[dict[str, Any]] = []
        for item in (
            content if isinstance(content, list) else [{"type": "text", "text": content}]
        ):
            if item.get("type") == "text":
                parts.append({"text": str(item.get("text", ""))})
            elif item.get("type") == "image_url":
                parts.append(_inline_image(item["image_url"]["url"]))
            else:
                raise ValueError(f"不支持的消息部件类型 {item.get('type')!r}")
        contents.append(
            {"role": "model" if role == "assistant" else "user", "parts": parts}
        )
    return {
        "project": route.project_id,
        "model": f"{route.model}-{route.reasoning_effort}",
        "userAgent": "antigravity",
        "requestType": "agent",
        "requestId": str(uuid.uuid4()),
        "request": {
            "contents": contents,
            "systemInstruction": {
                "role": "user",
                "parts": [{"text": "\n".join(system_texts)}],
            },
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "thinkingConfig": {
                    "thinkingLevel": route.reasoning_effort.upper(),
                    "includeThoughts": True,
                },
            },
        },
    }


def _absorb_event(
    event: Any,
    state: dict[str, Any],
) -> None:
    if not isinstance(event, dict):
        raise GeminiTransportError("Gemini 响应格式异常，拒绝采信部分结果")
    if event.get("error") or event.get("type") == "error":
        raise GeminiTransportError("Gemini 流返回错误，拒绝采信部分结果")
    value = event.get("response", event)
    if not isinstance(value, Mapping):
        raise GeminiTransportError("Gemini 响应格式异常，拒绝采信部分结果")
    if value.get("error"):
        raise GeminiTransportError("Gemini 流返回错误，拒绝采信部分结果")
    usage = value.get("usageMetadata")
    if isinstance(usage, Mapping):
        state["usage"] = dict(usage)
    state["model_version"] = value.get("modelVersion") or state["model_version"]
    state["response_id"] = value.get("responseId") or state["response_id"]
    for candidate in value.get("candidates", []) or []:
        state["finish"] = candidate.get("finishReason") or state["finish"]
        content = candidate.get("content") or {}
        for part in content.get("parts", []) or []:
            if part.get("thought"):
                state["thought"].append(part.get("text", ""))
            else:
                state["text"].append(part.get("text", ""))
    block = (value.get("promptFeedback") or {}).get("blockReason")
    if block and state["finish"] is None:
        state["finish"] = "SAFETY"


async def direct_gemini_completion(
    route, messages: list[dict[str, Any]], max_tokens: int
) -> PageCompletion:
    """Stream the native Gemini endpoint; a broken stream is never accepted."""
    body = build_gemini_request(route, messages, max_tokens)
    headers = {
        "Authorization": f"Bearer {await access_token(route.api_key)}",
        "User-Agent": ANTIGRAVITY_USER_AGENT,
    }
    url = route.base_url.rstrip("/") + STREAM_PATH
    state: dict[str, Any] = {
        "text": [], "thought": [], "usage": {},
        "model_version": None, "response_id": None, "finish": None,
    }
    try:
        async with httpx.AsyncClient(
            trust_env=False,
            timeout=httpx.Timeout(PAGE_REVIEW_TIMEOUT_SECONDS, connect=15),
        ) as client:
            async with client.stream("POST", url, headers=headers, json=body) as response:
                if response.status_code != 200:
                    if response.status_code == 401:
                        invalidate()
                    raw = (await response.aread()).decode(errors="replace")
                    raise GeminiTransportError(
                        f"Gemini 端点返回 HTTP {response.status_code}：{raw[:400]}",
                        status_code=response.status_code,
                    )
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    _absorb_event(json.loads(payload), state)
    except GeminiTransportError:
        raise
    except httpx.HTTPError as exc:
        raise GeminiTransportError(
            f"Gemini SSE 流中断：{type(exc).__name__}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise GeminiTransportError(
            "Gemini SSE 事件不是有效 JSON，拒绝采信部分结果"
        ) from exc

    if state["finish"] not in _FINISH_MAP:
        raise GeminiTransportError("Gemini 未完整结束本次判读，请重试")
    if not state["model_version"] and _FINISH_MAP[state["finish"]] != "content_filter":
        raise GeminiTransportError("Gemini 未返回实际模型标识，拒绝采信")
    if state["model_version"] is not None and state["model_version"] not in {route.model, body["model"]}:
        raise GeminiTransportError(
            f"Gemini 响应模型身份 {state['model_version']} 与配置 {route.model} 不一致，拒绝采信"
        )
    finish = _FINISH_MAP.get(state["finish"], state["finish"])
    text = "".join(state["text"])
    thought = "".join(state["thought"])
    return PageCompletion(
        text=text,
        finish_reason=finish,
        usage=state["usage"],
        response_model=state["model_version"],
        response_id=state["response_id"],
        output_lengths={
            "content_characters": len(text),
            "reasoning_content_characters": len(thought),
        },
    )


__all__ = [
    "GeminiTransportError",
    "direct_gemini_completion",
    "build_gemini_request",
]
