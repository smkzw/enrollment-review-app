from __future__ import annotations

import asyncio
import base64
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from openai import APIStatusError, AuthenticationError

from app.llm import independent_vlm as vlm


ROOT = Path(__file__).resolve().parents[3]
CODING_PLAN_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"
LEGACY_PAAS_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

# Acceptance boundary (worker_03):
# ACCEPT — Coding Plan endpoint/model/thinking contract, source-locator fidelity,
#          fail-closed remote classification, isolation from OCR/semantic routes.
# REJECT — OMP DB coupling, project-specific clinical hardcoding, silent OCR/semantic
#          fallback, treating VLM text as an enrollment verdict.
# LIVE   — optional; requires INDEPENDENT_VLM_LIVE=1 and a Coding Plan API key;
#          responses must be desensitized in assertions/logs.


def _config_probe(overrides: dict[str, str] | None = None) -> list[str]:
    env = os.environ.copy()
    for key in (
        "INDEPENDENT_VLM_PROVIDER",
        "INDEPENDENT_VLM_BASE_URL",
        "INDEPENDENT_VLM_API_KEY",
        "INDEPENDENT_VLM_MODEL",
        "INDEPENDENT_VLM_REASONING_EFFORT",
        "INDEPENDENT_VLM_MAX_TOKENS",
        "REVIEW_BACKEND",
        "OCR_BACKEND",
    ):
        env.pop(key, None)
    env.update(overrides or {})
    script = (
        "from app.config import ("
        "INDEPENDENT_VLM_PROVIDER, INDEPENDENT_VLM_BASE_URL, "
        "INDEPENDENT_VLM_MODEL, INDEPENDENT_VLM_REASONING_EFFORT, "
        "INDEPENDENT_VLM_MAX_TOKENS, REVIEW_BACKEND, OCR_BACKEND"
        "); "
        "print('|'.join(("
        "INDEPENDENT_VLM_PROVIDER, INDEPENDENT_VLM_BASE_URL, "
        "INDEPENDENT_VLM_MODEL, INDEPENDENT_VLM_REASONING_EFFORT, "
        "str(INDEPENDENT_VLM_MAX_TOKENS), REVIEW_BACKEND, OCR_BACKEND"
        ")))"
    )
    output = subprocess.check_output(
        [sys.executable, "-c", script], cwd=ROOT, env=env, text=True
    )
    return output.strip().split("|")


def test_independent_vlm_defaults_use_direct_coding_plan_and_stay_isolated():
    values = _config_probe()
    assert values == [
        "zhipu-coding-plan",
        CODING_PLAN_BASE_URL,
        "glm-5.3-flash",
        "high",
        "65536",
        "mtplx",
        "omlx",
    ]
    assert values[1] != LEGACY_PAAS_BASE_URL
    assert vlm.CODING_PLAN_BASE_URL == CODING_PLAN_BASE_URL


def test_independent_vlm_env_overrides_do_not_rewrite_semantic_or_ocr_defaults():
    values = _config_probe(
        {
            "INDEPENDENT_VLM_PROVIDER": "bigmodel",
            "INDEPENDENT_VLM_BASE_URL": CODING_PLAN_BASE_URL,
            "INDEPENDENT_VLM_MODEL": "glm-5.3-flash",
            "INDEPENDENT_VLM_REASONING_EFFORT": "max",
            "INDEPENDENT_VLM_MAX_TOKENS": "4096",
            "REVIEW_BACKEND": "deepseek",
            "OCR_BACKEND": "minimax",
        }
    )
    assert values == [
        "bigmodel",
        CODING_PLAN_BASE_URL,
        "glm-5.3-flash",
        "max",
        "4096",
        "deepseek",
        "minimax",
    ]


def test_high_reasoning_effort_maps_to_thinking_enabled():
    mapped = vlm.map_reasoning_effort_to_thinking("high")
    assert mapped["reasoning_effort"] == "high"
    assert mapped["extra_body"] == {
        "thinking": {"type": "enabled", "clear_thinking": False}
    }


def test_unsupported_reasoning_effort_fails_closed():
    with pytest.raises(vlm.IndependentVlmConfigError, match="Unsupported"):
        vlm.map_reasoning_effort_to_thinking("medium")


def test_completion_kwargs_keep_provider_sampling_defaults():
    kwargs = vlm.independent_vlm_completion_kwargs(
        messages=[{"role": "user", "content": "ping"}],
        model="glm-5.3-flash",
        reasoning_effort="high",
    )
    assert kwargs["model"] == "glm-5.3-flash"
    assert kwargs["reasoning_effort"] == "high"
    assert "temperature" not in kwargs
    assert "top_p" not in kwargs
    assert kwargs["extra_body"]["thinking"]["type"] == "enabled"
    assert kwargs["extra_body"]["thinking"]["clear_thinking"] is False


def test_normalize_base_url_keeps_coding_paas_v4_without_openai_v1_suffix():
    assert (
        vlm.normalize_independent_vlm_base_url(f"{CODING_PLAN_BASE_URL}/")
        == CODING_PLAN_BASE_URL
    )
    assert (
        vlm.normalize_independent_vlm_base_url(f"{CODING_PLAN_BASE_URL}/v1")
        == CODING_PLAN_BASE_URL
    )
    assert (
        vlm.normalize_independent_vlm_base_url(f"{LEGACY_PAAS_BASE_URL}/v1")
        == LEGACY_PAAS_BASE_URL
    )


def test_require_config_fails_closed_without_api_key(monkeypatch):
    monkeypatch.setenv("INDEPENDENT_VLM_PROVIDER", "zhipu-coding-plan")
    monkeypatch.setenv("INDEPENDENT_VLM_API_KEY", "")
    monkeypatch.setattr(vlm, "INDEPENDENT_VLM_API_KEY", "")
    with pytest.raises(vlm.IndependentVlmConfigError, match="API_KEY"):
        vlm.require_independent_vlm_config()


def test_require_config_returns_coding_plan_contract(monkeypatch):
    monkeypatch.setenv("INDEPENDENT_VLM_PROVIDER", "zhipu-coding-plan")
    monkeypatch.setenv("INDEPENDENT_VLM_BASE_URL", CODING_PLAN_BASE_URL)
    monkeypatch.setenv("INDEPENDENT_VLM_API_KEY", "test-key")
    monkeypatch.setenv("INDEPENDENT_VLM_MODEL", "glm-5.3-flash")
    monkeypatch.setattr(vlm, "INDEPENDENT_VLM_API_KEY", "test-key")
    cfg = vlm.require_independent_vlm_config()
    assert cfg == {
        "provider": "zhipu-coding-plan",
        "api_key": "test-key",
        "model": "glm-5.3-flash",
        "base_url": CODING_PLAN_BASE_URL,
    }


def test_build_page_vision_messages_preserve_raw_page_and_source_ref():
    page = vlm.PageVisionInput(
        source_ref="body.p803",
        page_ordinal=1,
        media_type="image/png",
        image_bytes=b"\x89PNG\r\n\x1a\n",
        locator_hint="table-cell:r1c2",
    )
    messages = vlm.build_page_vision_messages(
        "请核验本页原文并回源定位。",
        [page],
        system_prompt="vision verifier",
    )
    assert messages[0] == {"role": "system", "content": "vision verifier"}
    user = messages[1]
    assert user["role"] == "user"
    content = user["content"]
    assert content[0]["type"] == "text"
    assert "请核验本页原文并回源定位。" in content[0]["text"]
    fidelity = content[1]["text"]
    assert "SOURCE LOCATOR FIDELITY CONTRACT" in fidelity
    assert "body.p803" in fidelity
    anchor = content[2]["text"]
    assert "source_ref=body.p803" in anchor
    assert "page_ordinal=1" in anchor
    assert "LOCATOR_HINT table-cell:r1c2" in anchor
    image = content[3]
    assert image["type"] == "image_url"
    assert image["image_url"]["url"].startswith("data:image/png;base64,")


def test_build_page_vision_messages_preserve_multi_page_source_refs():
    pages = [
        vlm.PageVisionInput(
            source_ref="page.a1",
            page_ordinal=1,
            image_bytes=b"page-a",
        ),
        vlm.PageVisionInput(
            source_ref="page.b2",
            page_ordinal=2,
            media_type="image/jpeg",
            image_bytes=b"page-b",
        ),
    ]
    messages = vlm.build_page_vision_messages("multi-page check", pages)
    content = messages[0]["content"]
    fidelity = content[1]["text"]
    assert "page.a1" in fidelity and "page.b2" in fidelity
    anchors = [part["text"] for part in content if part.get("type") == "text"]
    assert any("source_ref=page.a1" in text for text in anchors)
    assert any("source_ref=page.b2" in text for text in anchors)
    images = [part for part in content if part.get("type") == "image_url"]
    assert len(images) == 2
    assert images[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert images[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_source_locator_fidelity_rejects_invented_refs():
    with pytest.raises(vlm.IndependentVlmSourceFidelityError, match="invented"):
        vlm.assert_source_locator_fidelity(
            "所见内容位于 source_ref=body.p999",
            allowed_source_refs=["body.p803"],
        )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "来源：source_ref = `synthetic.selective.page1`，page_ordinal = 1",
            {"synthetic.selective.page1"},
        ),
        (
            "source_ref：body.p803；页面清晰",
            {"body.p803"},
        ),
        (
            "source_ref='资料页.一'，请人工确认",
            {"资料页.一"},
        ),
        (
            "- **source_ref**：synthetic.selective.page1（原样保留）",
            {"synthetic.selective.page1"},
        ),
    ],
)
def test_extract_claimed_source_refs_accepts_chinese_punctuation_and_markdown(
    text, expected
):
    assert vlm.extract_claimed_source_refs(text) == expected


def test_source_locator_fidelity_accepts_allowed_refs():
    vlm.assert_source_locator_fidelity(
        "定位: source_ref=body.p803 page_ordinal=1",
        allowed_source_refs=["body.p803"],
        require_claim=True,
    )


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 429):
        self.status_code = status_code
        self._payload = payload
        self.request = SimpleNamespace()
        self.headers: dict[str, str] = {}

    def json(self):
        return self._payload


def test_classify_remote_failure_balance_code_1113_disables_route():
    exc = APIStatusError(
        message="Error code: 1113",
        response=_FakeResponse(
            {"error": {"code": "1113", "message": "余额不足"}},
            status_code=429,
        ),
        body={"error": {"code": "1113", "message": "余额不足"}},
    )
    classified = vlm.classify_remote_failure(exc)
    assert isinstance(classified, vlm.IndependentVlmBalanceError)
    assert classified.disabled is True
    assert classified.failure_kind == "balance_insufficient"
    assert classified.provider_code == "1113"


def test_classify_remote_failure_auth_disables_route():
    # AuthenticationError requires a response in openai>=2; synthesize via status.
    response = _FakeResponse(
        {"error": {"message": "Invalid API key", "code": "401"}},
        status_code=401,
    )
    exc = AuthenticationError(
        message="Invalid API key",
        response=response,
        body={"error": {"message": "Invalid API key", "code": "401"}},
    )
    classified = vlm.classify_remote_failure(exc)
    assert classified.disabled is True
    assert classified.failure_kind == "auth"


def test_classify_remote_failure_quota_disables_route():
    exc = APIStatusError(
        message="Rate limit exceeded",
        response=_FakeResponse(
            {"error": {"code": "1302", "message": "Rate limit exceeded"}},
            status_code=429,
        ),
        body={"error": {"code": "1302", "message": "Rate limit exceeded"}},
    )
    classified = vlm.classify_remote_failure(exc)
    assert classified.disabled is True
    assert classified.failure_kind == "quota"
    assert classified.provider_code == "1302"


def test_classify_remote_failure_generic_remote_error_disables_route():
    exc = APIStatusError(
        message="upstream unavailable",
        response=_FakeResponse(
            {"error": {"code": "500", "message": "upstream unavailable"}},
            status_code=500,
        ),
        body={"error": {"code": "500", "message": "upstream unavailable"}},
    )
    classified = vlm.classify_remote_failure(exc)
    assert classified.disabled is True
    assert classified.failure_kind == "remote_error"


def test_independent_vlm_chat_balance_insufficient_fail_closed(monkeypatch):
    class _Completions:
        async def create(self, **kwargs):
            raise APIStatusError(
                message="余额不足",
                response=_FakeResponse(
                    {"error": {"code": 1113, "message": "余额不足"}},
                    status_code=429,
                ),
                body={"error": {"code": 1113, "message": "余额不足"}},
            )

    class _Client:
        def __init__(self):
            self.chat = SimpleNamespace(completions=_Completions())

    monkeypatch.setattr(vlm, "get_independent_vlm_client", lambda: _Client())

    with pytest.raises(vlm.IndependentVlmBalanceError) as exc_info:
        asyncio.run(
            vlm.independent_vlm_chat(
                [{"role": "user", "content": "ping"}],
                enforce_source_fidelity=False,
            )
        )
    assert exc_info.value.disabled is True
    assert "disabled" in str(exc_info.value).lower()


def test_independent_vlm_page_chat_enforces_source_fidelity(monkeypatch):
    page = vlm.PageVisionInput(
        source_ref="body.p803",
        page_ordinal=1,
        image_bytes=b"abc",
    )

    class _Message:
        content = "claim source_ref=body.forged"
        reasoning_content = None

        def model_dump(self):
            return {"role": "assistant", "content": self.content}

    class _Choice:
        message = _Message()
        finish_reason = "stop"

    class _Resp:
        choices = [_Choice()]
        model = "glm-5.3-flash"
        usage = SimpleNamespace(
            completion_tokens=3, prompt_tokens=5, total_tokens=8
        )

    class _Completions:
        async def create(self, **kwargs):
            assert kwargs["extra_body"]["thinking"]["type"] == "enabled"
            assert kwargs["reasoning_effort"] == "high"
            return _Resp()

    class _Client:
        def __init__(self):
            self.chat = SimpleNamespace(completions=_Completions())

    monkeypatch.setattr(vlm, "get_independent_vlm_client", lambda: _Client())

    with pytest.raises(vlm.IndependentVlmSourceFidelityError, match="invented"):
        asyncio.run(
            vlm.independent_vlm_page_chat(
                "核验", [page], reasoning_effort="high"
            )
        )


def test_independent_vlm_page_chat_requires_source_ref_claim(monkeypatch):
    page = vlm.PageVisionInput(
        source_ref="body.p803",
        page_ordinal=1,
        image_bytes=b"abc",
    )

    message = SimpleNamespace(content="页面文字清晰，但未引用来源。", reasoning_content=None)
    choice = SimpleNamespace(message=message, finish_reason="stop")
    response = SimpleNamespace(choices=[choice], model="glm-5.3-flash", usage=None)

    class _Completions:
        async def create(self, **kwargs):
            return response

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=_Completions())
    )
    monkeypatch.setattr(vlm, "get_independent_vlm_client", lambda: client)

    with pytest.raises(vlm.IndependentVlmSourceFidelityError, match="omitted"):
        asyncio.run(vlm.independent_vlm_page_chat("核验", [page]))


def test_check_independent_vlm_false_without_key(monkeypatch):
    monkeypatch.setenv("INDEPENDENT_VLM_API_KEY", "")
    monkeypatch.setattr(vlm, "INDEPENDENT_VLM_API_KEY", "")
    assert asyncio.run(vlm.check_independent_vlm()) is False


def test_check_independent_vlm_true_with_key(monkeypatch):
    monkeypatch.setenv("INDEPENDENT_VLM_API_KEY", "test-key")
    monkeypatch.setenv("INDEPENDENT_VLM_PROVIDER", "zhipu-coding-plan")
    monkeypatch.setenv("INDEPENDENT_VLM_REASONING_EFFORT", "high")
    monkeypatch.setattr(vlm, "INDEPENDENT_VLM_API_KEY", "test-key")
    assert asyncio.run(vlm.check_independent_vlm()) is True


def test_adapter_has_no_project_specific_hardcoding():
    """Independent VLM must stay protocol-agnostic (no D001 / trial IDs)."""
    sources = [
        ROOT / "app" / "llm" / "independent_vlm.py",
        ROOT / "app" / "config.py",
        ROOT / ".env.example",
        Path(__file__),
    ]
    banned = re.compile(
        r"\b(D001|NCT\d+|package8\d|slice61|KZ[-_]?\d+|入排结论|受试者审核结论)\b",
        re.IGNORECASE,
    )
    for path in sources:
        text = path.read_text(encoding="utf-8")
        # Allow this test's own banned-pattern definition line only.
        if path == Path(__file__):
            continue
        match = banned.search(text)
        assert match is None, f"project-specific hardcoding in {path}: {match.group(0)}"


def test_adapter_does_not_import_omp_or_semantic_ocr_backends():
    text = (ROOT / "app" / "llm" / "independent_vlm.py").read_text(encoding="utf-8")
    assert "models.db" not in text
    assert "auth_credentials" not in text
    assert "from app.agents" not in text
    assert "import app.agents" not in text
    # Isolation is about imports/backends, not prose mentioning OCR/semantic routes.
    for banned_import in (
        "from app.ocr",
        "import app.ocr",
        "from app.agents",
        "import mtplx",
        "import deepseek",
        "import minimax",
        "import omlx",
    ):
        assert banned_import not in text


def _tiny_png_bytes() -> bytes:
    # 1x1 PNG; no clinical content.
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def _resolve_live_api_key() -> str | None:
    return os.getenv("INDEPENDENT_VLM_API_KEY", "").strip() or None


def test_live_coding_plan_vision_connectivity_desensitized(monkeypatch):
    """Real Coding Plan vision call; skipped unless explicitly enabled.

    Acceptance for LIVE:
    - Endpoint must be Coding Plan ``/api/coding/paas/v4``
    - Request carries thinking.enabled + image_url data URL
    - Failures classify as disabled remote errors (no silent OCR/semantic fallback)
    - Assertions only keep length/model/failure_kind (no raw clinical text, no key)
    """
    if os.getenv("INDEPENDENT_VLM_LIVE", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        pytest.skip("Set INDEPENDENT_VLM_LIVE=1 to run real Coding Plan connectivity")

    api_key = _resolve_live_api_key()
    if not api_key:
        pytest.skip(
            "No explicit INDEPENDENT_VLM_API_KEY available"
        )

    monkeypatch.setenv("INDEPENDENT_VLM_PROVIDER", "zhipu-coding-plan")
    monkeypatch.setenv("INDEPENDENT_VLM_BASE_URL", CODING_PLAN_BASE_URL)
    monkeypatch.setenv("INDEPENDENT_VLM_API_KEY", api_key)
    monkeypatch.setenv("INDEPENDENT_VLM_MODEL", "glm-5.3-flash")
    monkeypatch.setenv("INDEPENDENT_VLM_REASONING_EFFORT", "high")
    monkeypatch.setattr(vlm, "INDEPENDENT_VLM_API_KEY", api_key)
    monkeypatch.setattr(vlm, "INDEPENDENT_VLM_BASE_URL", CODING_PLAN_BASE_URL)
    monkeypatch.setattr(vlm, "INDEPENDENT_VLM_MODEL", "glm-5.3-flash")
    vlm.reset_independent_vlm_client()

    page = vlm.PageVisionInput(
        source_ref="synthetic.page1",
        page_ordinal=1,
        media_type="image/png",
        image_bytes=_tiny_png_bytes(),
    )
    prompt = (
        "Reply with exactly one short English word describing whether an image "
        "was received. Also include source_ref=synthetic.page1. No other claims."
    )

    try:
        result = asyncio.run(
            vlm.independent_vlm_page_chat(
                prompt,
                [page],
                # Thinking consumes output budget on Coding Plan; keep headroom.
                max_tokens=512,
                reasoning_effort="high",
            )
        )
    except vlm.IndependentVlmRemoteError as exc:
        assert exc.disabled is True
        assert exc.failure_kind in {
            "balance_insufficient",
            "auth",
            "quota",
            "remote_error",
        }
        assert api_key not in str(exc)
        pytest.fail(
            "Coding Plan live connectivity failed: "
            f"kind={exc.failure_kind}, status={exc.status_code}, "
            f"provider_code={exc.provider_code}"
        )

    model = str(result.model or "")
    text = result.text or ""
    reasoning = result.reasoning_content or ""
    finish_reason = result.finish_reason
    # Keep only desensitized scalars in assertions (avoid dumping raw model text).
    assert model
    assert "glm" in model.lower()
    assert isinstance(text, str)
    assert isinstance(reasoning, str)
    assert api_key not in text
    assert api_key not in reasoning
    # Connectivity accepts either visible content or non-empty reasoning_content
    # when thinking consumed part of the completion budget.
    assert (len(text) > 0) or (len(reasoning) > 0)
    assert len(text) <= 4000
    assert len(reasoning) <= 20000
    assert finish_reason in {None, "stop", "length"}
    if text:
        vlm.assert_source_locator_fidelity(
            text,
            allowed_source_refs=["synthetic.page1"],
            require_claim=False,
        )
