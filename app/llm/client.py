"""LLM client – wraps two backends behind a unified async interface.

Backends
--------
1. oMLX  (local, OpenAI-compatible) – OCR / vision tasks
2. DeepSeek (remote)               – review / reasoning tasks

Both use ``openai.AsyncOpenAI`` since they expose an OpenAI-compatible API.
"""

from __future__ import annotations

import re
import asyncio
import base64
import logging
import os
from pathlib import Path
from typing import AsyncIterator, List, Optional

import httpx
from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, RateLimitError

from app.config import (
    OMLX_BASE_URL,
    OMLX_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_API_KEY,
    MINIMAX_BASE_URL,
    MINIMAX_API_KEY,
    MINIMAX_MODEL,
    OCR_MODEL_LONG,
    OCR_MODEL_SHORT,
    OCR_LONG_PAGE_THRESHOLD,
    OCR_BACKEND,
    REVIEW_MODEL,
    REVIEW_BACKEND,
    REVIEW_REASONING_EFFORT,
    DECONSTRUCT_BACKEND,
    DECONSTRUCT_MODEL,
    DECONSTRUCT_REASONING_EFFORT,
    DECONSTRUCT_MAX_TOKENS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5  # seconds, multiplied by attempt number


# ---------------------------------------------------------------------------
# Client singletons (created lazily)
# ---------------------------------------------------------------------------
_omlx_client: Optional[AsyncOpenAI] = None
_deepseek_client: Optional[AsyncOpenAI] = None
_minimax_client: Optional[AsyncOpenAI] = None


def _get_omlx_client() -> AsyncOpenAI:
    """Return (and cache) an AsyncOpenAI pointing at the local oMLX server."""
    global _omlx_client
    if _omlx_client is None:
        _omlx_client = AsyncOpenAI(
            base_url=OMLX_BASE_URL.rstrip("/") + "/v1",
            api_key=os.getenv("OMLX_API_KEY", OMLX_API_KEY),
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
    return _omlx_client


def _get_deepseek_client() -> AsyncOpenAI:
    """Return (and cache) an AsyncOpenAI pointing at DeepSeek."""
    global _deepseek_client
    if _deepseek_client is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY)
        if not api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is not set. "
                "Export it as an environment variable or add it to .env"
            )
        _deepseek_client = AsyncOpenAI(
            base_url=DEEPSEEK_BASE_URL.rstrip("/") + "/v1",
            api_key=api_key,
            timeout=httpx.Timeout(180.0, connect=10.0),
        )
    return _deepseek_client


def _get_minimax_client() -> AsyncOpenAI:
    """Return (and cache) an AsyncOpenAI pointing at MiniMax M3."""
    global _minimax_client
    if _minimax_client is None:
        api_key = os.getenv("MINIMAX_API_KEY", MINIMAX_API_KEY)
        if not api_key:
            raise RuntimeError(
                "MINIMAX_API_KEY is not set. "
                "Export it as an environment variable or add it to .env"
            )
        # MiniMax: HTTP/1.1, no proxy
        http_client = httpx.AsyncClient(
            http1=True,
            http2=False,
            proxy=None,  # bypass system proxy
            trust_env=False,  # ignore env proxy vars
            timeout=httpx.Timeout(180.0, connect=10.0),
        )
        _minimax_client = AsyncOpenAI(
            base_url=MINIMAX_BASE_URL,
            api_key=api_key,
            http_client=http_client,
        )
    return _minimax_client


def _get_ocr_client() -> AsyncOpenAI:
    """Return the client selected by OCR_BACKEND."""
    if OCR_BACKEND == "minimax":
        return _get_minimax_client()
    return _get_omlx_client()


def _get_ocr_model() -> str:
    """Return the model name selected by OCR_BACKEND."""
    if OCR_BACKEND == "minimax":
        return MINIMAX_MODEL
    return OCR_MODEL_LONG


def _get_review_client() -> AsyncOpenAI:
    """Return the client selected by REVIEW_BACKEND."""
    if REVIEW_BACKEND == "omlx":
        return _get_omlx_client()
    return _get_deepseek_client()


def _get_deconstruct_client() -> AsyncOpenAI:
    """Return the client selected by DECONSTRUCT_BACKEND."""
    if DECONSTRUCT_BACKEND == "omlx":
        return _get_omlx_client()
    return _get_deepseek_client()


def _normalized_review_reasoning_effort() -> str | None:
    """Return a supported DeepSeek thinking effort for formal review calls."""
    if REVIEW_REASONING_EFFORT in {"", "default", "auto"}:
        return None
    if REVIEW_REASONING_EFFORT in {"high", "max"}:
        return REVIEW_REASONING_EFFORT
    logger.warning(
        "Unsupported REVIEW_REASONING_EFFORT=%s; using provider default",
        REVIEW_REASONING_EFFORT,
    )
    return None


def _uses_deepseek_thinking_for_review(model: str) -> bool:
    """DeepSeek V4 review models expose provider-native thinking controls."""
    return REVIEW_BACKEND == "deepseek" and model.startswith("deepseek-v4")


def _normalized_deconstruct_reasoning_effort() -> str | None:
    if DECONSTRUCT_REASONING_EFFORT in {"", "default", "auto"}:
        return None
    if DECONSTRUCT_REASONING_EFFORT in {"high", "max"}:
        return DECONSTRUCT_REASONING_EFFORT
    logger.warning(
        "Unsupported DECONSTRUCT_REASONING_EFFORT=%s; using provider default",
        DECONSTRUCT_REASONING_EFFORT,
    )
    return None


def _deconstruct_completion_kwargs(
    *, model: str, messages: list[dict], temperature: float, max_tokens: int
) -> dict:
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if DECONSTRUCT_BACKEND == "deepseek" and model.startswith("deepseek-v4"):
        effort = _normalized_deconstruct_reasoning_effort()
        if effort:
            kwargs["reasoning_effort"] = effort
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
    else:
        kwargs["temperature"] = temperature
    return kwargs


def _review_completion_kwargs(
    *,
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    stream: bool = False,
) -> dict:
    """Build review-completion kwargs without leaking DeepSeek-only params to oMLX."""
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if stream:
        kwargs["stream"] = True

    if _uses_deepseek_thinking_for_review(model):
        effort = _normalized_review_reasoning_effort()
        if effort:
            kwargs["reasoning_effort"] = effort
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
    else:
        kwargs["temperature"] = temperature
    return kwargs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _encode_image(image_path: str | Path) -> str:
    """Read an image file and return a data-URL string for the vision API."""
    path = Path(image_path)
    data = path.read_bytes()
    suffix = path.suffix.lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}
    ext = mime.get(suffix, "jpeg")
    b64 = base64.b64encode(data).decode()
    return f"data:image/{ext};base64,{b64}"


def _build_vision_message(prompt: str, image_paths: List[str | Path]) -> dict:
    """Build a multimodal user message with one or more images."""
    content: list = [{"type": "text", "text": prompt}]
    for img in image_paths:
        content.append({
            "type": "image_url",
            "image_url": {"url": _encode_image(img)},
        })
    return {"role": "user", "content": content}


async def _retry(coro_factory, *, retries: int = MAX_RETRIES, label: str = "call"):
    """Run *coro_factory()* with retries on transient errors."""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return await coro_factory()
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            last_exc = exc
            wait = RETRY_BACKOFF * attempt
            logger.warning(
                "%s failed (attempt %d/%d): %s – retrying in %.1fs",
                label, attempt, retries, exc, wait,
            )
            await asyncio.sleep(wait)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def ocr_image(
    image_path: str | Path,
    prompt: str = "请识别图片中的所有文字内容，保持原始格式。",
    model: str | None = None,
) -> str:
    """Send a single image to the oMLX vision model and return the text response.

    Parameters
    ----------
    image_path : path to the image file
    prompt : instruction for the model
    model : override OCR_MODEL from config
    """
    client = _get_ocr_client()
    msg = _build_vision_message(prompt, [image_path])

    async def _call():
        resp = await client.chat.completions.create(
            model=model or _get_ocr_model(),
            messages=[msg],
            max_tokens=4096,
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""

    return await _retry(_call, label="ocr_image")


async def ocr_images(
    image_paths: List[str | Path],
    prompt: str = "请识别图片中的所有文字内容，保持原始格式。",
    model: str | None = None,
) -> str:
    """Send multiple images in a single vision request."""
    client = _get_ocr_client()
    msg = _build_vision_message(prompt, image_paths)

    async def _call():
        resp = await client.chat.completions.create(
            model=model or _get_ocr_model(),
            messages=[msg],
            max_tokens=8192,
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""

    return await _retry(_call, label="ocr_images")


async def review_chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 12000,
    stream: bool = False,
) -> str | AsyncIterator[str]:
    """Send a chat completion request to the review backend.

    When *stream* is ``True`` returns an async iterator of text chunks (SSE).
    Otherwise returns the full text.
    """
    client = _get_review_client()
    use_model = model or REVIEW_MODEL

    if stream:
        return _stream_review(client, messages, use_model, temperature, max_tokens)

    async def _call():
        resp = await client.chat.completions.create(
            **_review_completion_kwargs(
                model=use_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
        return resp.choices[0].message.content or ""

    return await _retry(_call, label="review_chat")


async def _stream_review(
    client: AsyncOpenAI,
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int,
) -> AsyncIterator[str]:
    """Yield text chunks from a streaming chat completion."""
    stream = await client.chat.completions.create(
        **_review_completion_kwargs(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content


# ---------------------------------------------------------------------------
# Convenience: direct text completion (no images)
# ---------------------------------------------------------------------------

async def omlx_chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 8192,
) -> str:
    """Plain text chat against the local oMLX server."""
    client = _get_omlx_client()

    async def _call():
        resp = await client.chat.completions.create(
            model=model or REVIEW_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""

    return await _retry(_call, label="omlx_chat")


# ---------------------------------------------------------------------------
# Base64 OCR (used by pipeline/ocr.py)
# ---------------------------------------------------------------------------

def _choose_ocr_model(total_pages: int) -> str:
    """Choose OCR model based on document page count.
    
    Both LONG and SHORT default to PaddleOCR-VL-1.6 in current config.
    The threshold-based selection enables future model differentiation.
    """
    if total_pages >= OCR_LONG_PAGE_THRESHOLD:
        return OCR_MODEL_LONG
    return OCR_MODEL_SHORT


async def call_vision_ocr(
    image_b64: str,
    prompt: str = "请识别图片中的所有文字内容，保持原始格式。",
    model: str | None = None,
    total_pages: int = 1,
) -> str:
    """Send a base64-encoded image to OCR and return text.
    
    Uses configured OCR backend with model selection based on document length.
    Actual models determined by OCR_MODEL_LONG / OCR_MODEL_SHORT config.
    """
    client = _get_omlx_client()
    selected_model = model or _choose_ocr_model(total_pages)
    
    msg = {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
            },
        ],
    }

    async def _call():
        resp = await client.chat.completions.create(
            model=selected_model,
            messages=[msg],
            max_tokens=4096,
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""

    raw = await _retry(_call, label=f"ocr_{selected_model}")
    # Strip PaddleOCR 1.5 LOC tokens: <|LOC_123|> (harmless for 1.6)
    raw = re.sub(r'<\|LOC_\d+\|>', '', raw)
    # Collapse multiple blank lines
    raw = re.sub(r'\n\s*\n', '\n', raw).strip()
    return raw


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

async def check_omlx() -> bool:
    """Return True if oMLX server is reachable."""
    try:
        client = _get_omlx_client()
        await client.models.list()
        return True
    except Exception:
        return False


async def check_deepseek() -> bool:
    """Return True if DeepSeek API is reachable and key is set."""
    api_key = os.getenv("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY)
    if not api_key:
        return False
    try:
        client = _get_deepseek_client()
        await client.models.list()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Protocol deconstruction (uses dedicated backend)
# ---------------------------------------------------------------------------

async def deconstruct_chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = DECONSTRUCT_MAX_TOKENS,
) -> str:
    """Send a chat completion using the deconstruction backend."""
    client = _get_deconstruct_client()
    use_model = model or DECONSTRUCT_MODEL

    async def _call():
        resp = await client.chat.completions.create(
            **_deconstruct_completion_kwargs(
                model=use_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        )
        return resp.choices[0].message.content or ""

    return await _retry(_call, label="deconstruct_chat")


# ---------------------------------------------------------------------------
# Baidu OCR (handwriting recognition)
# ---------------------------------------------------------------------------

_baidu_token: Optional[str] = None
_baidu_token_expiry: float = 0

BAIDU_OCR_APP_ID = os.getenv("BAIDU_OCR_APP_ID", "")
BAIDU_OCR_API_KEY = os.getenv("BAIDU_OCR_API_KEY", "")
BAIDU_OCR_SECRET_KEY = os.getenv("BAIDU_OCR_SECRET_KEY", "")


async def _get_baidu_token() -> str:
    """Get Baidu OCR access token."""
    global _baidu_token, _baidu_token_expiry
    
    import time
    if _baidu_token and time.time() < _baidu_token_expiry:
        return _baidu_token
    
    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={BAIDU_OCR_API_KEY}&client_secret={BAIDU_OCR_SECRET_KEY}"
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, timeout=10)
        data = resp.json()
        _baidu_token = data.get("access_token", "")
        _baidu_token_expiry = time.time() + data.get("expires_in", 2592000) - 60
        return _baidu_token


async def baidu_ocr_handwriting(image_b64: str) -> str:
    """Use Baidu OCR handwriting recognition API.
    
    Returns extracted text from handwriting.
    """
    token = await _get_baidu_token()
    url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting?access_token={token}"
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"image": image_b64}
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, data=data, timeout=30)
        result = resp.json()
        
        if "words_result" in result:
            words = [item["words"] for item in result["words_result"]]
            return "\n".join(words)
        elif "error_msg" in result:
            logger.warning("Baidu OCR error: %s", result["error_msg"])
            return ""
        return ""


async def check_baidu_ocr() -> bool:
    """Return True if Baidu OCR credentials are configured."""
    return bool(BAIDU_OCR_API_KEY and BAIDU_OCR_SECRET_KEY)
