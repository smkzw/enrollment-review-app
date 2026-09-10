"""Refresh explicitly configured product OAuth credentials without personal tools."""

import os
import threading
import time

import httpx

_cache: dict[tuple[str, str, str], tuple[str, float]] = {}
_lock = threading.Lock()


def invalidate() -> None:
    key = tuple(os.environ.get(name, "").strip() for name in (
        "GEMINI_REFRESH_TOKEN", "GEMINI_OAUTH_CLIENT_ID", "GEMINI_OAUTH_CLIENT_SECRET",
    ))
    with _lock:
        _cache.pop(key, None)


async def access_token(fallback: str) -> str:
    refresh = os.environ.get("GEMINI_REFRESH_TOKEN", "").strip()
    if not refresh:
        return fallback
    client_id = os.environ.get("GEMINI_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GEMINI_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Gemini 授权刷新配置不完整")
    key = (refresh, client_id, client_secret)
    with _lock:
        cached = _cache.get(key)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    async with httpx.AsyncClient(trust_env=False, timeout=30) as client:
        response = await client.post("https://oauth2.googleapis.com/token", data={
            "grant_type": "refresh_token", "refresh_token": refresh,
            "client_id": client_id, "client_secret": client_secret,
        })
    if response.status_code != 200:
        raise RuntimeError(f"Gemini 授权刷新失败（HTTP {response.status_code}），请重新授权")
    payload = response.json()
    token = payload.get("access_token")
    expires = payload.get("expires_in")
    if not isinstance(token, str) or not token or not isinstance(expires, (int, float)) or expires <= 0:
        raise RuntimeError("Gemini 授权刷新响应不完整")
    with _lock:
        _cache[key] = (token, time.monotonic() + max(0, expires - 300))
    return token
