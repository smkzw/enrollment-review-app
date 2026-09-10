import asyncio

import httpx
import pytest

from app.llm import gemini_oauth


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    gemini_oauth._cache.clear()
    for name in ("GEMINI_REFRESH_TOKEN", "GEMINI_OAUTH_CLIENT_ID", "GEMINI_OAUTH_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)


def test_access_only_is_supported():
    assert asyncio.run(gemini_oauth.access_token("explicit")) == "explicit"


def test_refresh_is_cached_without_reading_personal_config(monkeypatch):
    for name in ("GEMINI_REFRESH_TOKEN", "GEMINI_OAUTH_CLIENT_ID", "GEMINI_OAUTH_CLIENT_SECRET"):
        monkeypatch.setenv(name, "test")
    calls = []
    def respond(request):
        calls.append(request)
        assert request.url == "https://oauth2.googleapis.com/token"
        assert b"grant_type=refresh_token" in request.content
        return httpx.Response(200, json={"access_token": "new", "expires_in": 3600})
    client = httpx.AsyncClient
    monkeypatch.setattr(gemini_oauth.httpx, "AsyncClient", lambda **kw: client(transport=httpx.MockTransport(respond), **kw))
    assert asyncio.run(gemini_oauth.access_token("old")) == "new"
    assert asyncio.run(gemini_oauth.access_token("old")) == "new"
    assert len(calls) == 1
    gemini_oauth.invalidate()
    assert asyncio.run(gemini_oauth.access_token("old")) == "new"
    assert len(calls) == 2


def test_partial_refresh_configuration_fails(monkeypatch):
    monkeypatch.setenv("GEMINI_REFRESH_TOKEN", "test")
    with pytest.raises(RuntimeError, match="不完整"):
        asyncio.run(gemini_oauth.access_token("expired"))
