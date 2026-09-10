from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from app.agents import deepseek_evidence_normalizer_transport as evidence_transport
from app.agents import protocol_semantic_transport as protocol_transport
from app.agents import phase_applicability_transport as phase_transport
from app.domain.contracts.agents import ModelConfigContract
from app.llm import client as llm_client
from scripts.probe_mtplx_semantic_route import _strict_completion_payload


ROOT = Path(__file__).resolve().parents[3]
MTPLX_DEFAULT_BASE_URL = "http://127.0.0.1:8002"
# Use a separate explicit URL in injected-client tests so those tests cannot
# accidentally inherit the live oMLX endpoint or an application's .env file.
MTPLX_BASE_URL = "http://127.0.0.1:8002"
MTPLX_MODEL = "mtplx-flash-next-optimized-speed"


class _RecordingOpenAI:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs):
        self.calls.append(kwargs)


def _config_probe() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "REVIEW_BACKEND",
        "REVIEW_MODEL",
        "REVIEW_REASONING_EFFORT",
        "DECONSTRUCT_BACKEND",
        "DECONSTRUCT_MODEL",
        "DECONSTRUCT_REASONING_EFFORT",
        "EVIDENCE_NORMALIZER_PROVIDER",
        "EVIDENCE_NORMALIZER_MODEL",
        "EVIDENCE_NORMALIZER_REASONING_EFFORT",
        "PHASE_APPLICABILITY_BACKEND",
        "PHASE_APPLICABILITY_MODEL",
        "PHASE_APPLICABILITY_REASONING_EFFORT",
        "MTPLX_BASE_URL",
        "MTPLX_MODEL",
        "MTPLX_REASONING_EFFORT",
    ):
        env.pop(key, None)
    script = """
import json
from app.config import (
    DECONSTRUCT_BACKEND, DECONSTRUCT_MODEL, DECONSTRUCT_REASONING_EFFORT,
    EVIDENCE_NORMALIZER_PROVIDER, EVIDENCE_NORMALIZER_MODEL,
    EVIDENCE_NORMALIZER_REASONING_EFFORT, EVIDENCE_NORMALIZER_MAX_TOKENS,
    EVIDENCE_NORMALIZER_MAX_PAGES_PER_CALL, MTPLX_BASE_URL, MTPLX_MODEL,
    MTPLX_REASONING_EFFORT, OCR_BACKEND, OCR_MODEL_LONG, REVIEW_BACKEND,
    REVIEW_MODEL, REVIEW_REASONING_EFFORT, OMLX_BASE_URL,
)
from app.agents.phase_applicability_transport import (
    PHASE_APPLICABILITY_BACKEND, PHASE_APPLICABILITY_MODEL,
    PHASE_APPLICABILITY_REASONING_EFFORT,
)
names = (
    "DECONSTRUCT_BACKEND", "DECONSTRUCT_MODEL", "DECONSTRUCT_REASONING_EFFORT",
    "EVIDENCE_NORMALIZER_PROVIDER", "EVIDENCE_NORMALIZER_MODEL",
    "EVIDENCE_NORMALIZER_REASONING_EFFORT", "EVIDENCE_NORMALIZER_MAX_TOKENS",
    "EVIDENCE_NORMALIZER_MAX_PAGES_PER_CALL", "MTPLX_BASE_URL", "MTPLX_MODEL",
    "MTPLX_REASONING_EFFORT", "OCR_BACKEND", "OCR_MODEL_LONG", "OMLX_BASE_URL",
    "PHASE_APPLICABILITY_BACKEND", "PHASE_APPLICABILITY_MODEL",
    "PHASE_APPLICABILITY_REASONING_EFFORT", "REVIEW_BACKEND", "REVIEW_MODEL",
    "REVIEW_REASONING_EFFORT",
)
scope = globals()
print(json.dumps({name: scope[name] for name in names}, ensure_ascii=False))
"""
    output = subprocess.check_output(
        [sys.executable, "-c", script], cwd=ROOT, env=env, text=True
    )
    payload = json.loads(output)
    names = (
        "DECONSTRUCT_BACKEND",
        "DECONSTRUCT_MODEL",
        "DECONSTRUCT_REASONING_EFFORT",
        "EVIDENCE_NORMALIZER_PROVIDER",
        "EVIDENCE_NORMALIZER_MODEL",
        "EVIDENCE_NORMALIZER_REASONING_EFFORT",
        "EVIDENCE_NORMALIZER_MAX_TOKENS",
        "EVIDENCE_NORMALIZER_MAX_PAGES_PER_CALL",
        "MTPLX_BASE_URL",
        "MTPLX_MODEL",
        "MTPLX_REASONING_EFFORT",
        "OCR_BACKEND",
        "OCR_MODEL_LONG",
        "OMLX_BASE_URL",
        "PHASE_APPLICABILITY_BACKEND",
        "PHASE_APPLICABILITY_MODEL",
        "PHASE_APPLICABILITY_REASONING_EFFORT",
        "REVIEW_BACKEND",
        "REVIEW_MODEL",
        "REVIEW_REASONING_EFFORT",
    )
    return {name: str(payload[name]) for name in names}


def _assert_strict_json_schema(kwargs: dict[str, object]) -> None:
    response_format = kwargs["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"
    schema = response_format["json_schema"]
    assert isinstance(schema, dict)
    assert schema["strict"] is True
    assert isinstance(schema["schema"], dict)


def _patch_mtplx_constants(monkeypatch, module) -> None:
    monkeypatch.setattr(module, "MTPLX_BASE_URL", MTPLX_BASE_URL, raising=False)
    monkeypatch.setattr(module, "MTPLX_API_KEY", "", raising=False)


def test_default_routes_keep_glm_normalizer_separate_from_mtplx_and_omlx() -> None:
    values = _config_probe()
    assert values["MTPLX_BASE_URL"] == MTPLX_DEFAULT_BASE_URL
    assert values["MTPLX_MODEL"] == MTPLX_MODEL
    assert values["MTPLX_REASONING_EFFORT"] == "medium"
    for name in (
        "DECONSTRUCT_BACKEND",
        "PHASE_APPLICABILITY_BACKEND",
        "REVIEW_BACKEND",
    ):
        assert values[name] == "mtplx"
    for prefix in ("DECONSTRUCT", "PHASE_APPLICABILITY", "REVIEW"):
        assert values[f"{prefix}_MODEL"] == MTPLX_MODEL
        assert values[f"{prefix}_REASONING_EFFORT"] == "medium"
    assert values["EVIDENCE_NORMALIZER_PROVIDER"] == "zhipu-coding-plan"
    assert values["EVIDENCE_NORMALIZER_MODEL"] == "glm-5.3-flash"
    assert values["EVIDENCE_NORMALIZER_REASONING_EFFORT"] == "high"
    assert values["OCR_BACKEND"] == "omlx"
    assert values["OCR_MODEL_LONG"] != MTPLX_MODEL
    assert values["OMLX_BASE_URL"] != MTPLX_BASE_URL
    assert values["EVIDENCE_NORMALIZER_MAX_TOKENS"] == "65536"
    assert values["EVIDENCE_NORMALIZER_MAX_PAGES_PER_CALL"] == "2"


def test_protocol_transport_uses_only_explicit_mtplx_and_strict_wire(monkeypatch) -> None:
    _RecordingOpenAI.calls.clear()
    monkeypatch.setattr(protocol_transport, "OpenAI", _RecordingOpenAI)
    _patch_mtplx_constants(monkeypatch, protocol_transport)
    monkeypatch.setattr(protocol_transport, "DECONSTRUCT_BACKEND", "mtplx")
    monkeypatch.setattr(protocol_transport, "DECONSTRUCT_MODEL", MTPLX_MODEL)
    monkeypatch.setattr(protocol_transport, "DECONSTRUCT_REASONING_EFFORT", "medium")

    transport = protocol_transport.DeepSeekProtocolAgentTransport(backend="mtplx")
    assert transport._backend == "mtplx"
    assert transport._model == MTPLX_MODEL
    assert _RecordingOpenAI.calls[0]["base_url"] == f"{MTPLX_BASE_URL}/v1"
    assert _RecordingOpenAI.calls[0]["api_key"] != "deepseek"
    kwargs = transport._completion_kwargs([{"role": "user", "content": "probe"}])
    assert kwargs["model"] == MTPLX_MODEL
    assert kwargs["reasoning_effort"] == "medium"
    assert kwargs["max_tokens"] == protocol_transport.MTPLX_PROTOCOL_BATCH_MAX_TOKENS
    _assert_strict_json_schema(kwargs)
    assert kwargs["extra_body"] == {"generation_mode": "ar"}


def test_phase_transport_preserves_mtplx_identity_without_remote_or_omlx_fallback(
    monkeypatch,
):
    _RecordingOpenAI.calls.clear()
    monkeypatch.setattr(phase_transport, "OpenAI", _RecordingOpenAI)
    _patch_mtplx_constants(monkeypatch, phase_transport)
    config = ModelConfigContract(
        model_config_id="mtplx-phase-config",
        provider="mtplx",
        model=MTPLX_MODEL,
        reasoning_effort="medium",
        parameters={"max_tokens": 8192, "base_url": MTPLX_BASE_URL},
    )
    transport = phase_transport.phase_applicability_transport_from_model_config(config)
    assert transport.backend == "mtplx"
    assert transport.model == MTPLX_MODEL
    assert transport.base_url == f"{MTPLX_BASE_URL}/v1"
    kwargs = transport._completion_kwargs([{"role": "user", "content": "probe"}])
    assert kwargs["model"] == MTPLX_MODEL
    assert kwargs["reasoning_effort"] == "medium"
    _assert_strict_json_schema(kwargs)
    assert kwargs["extra_body"] == {"generation_mode": "ar"}


def test_evidence_normalizer_factory_preserves_mtplx_identity_and_mtp_wire(monkeypatch) -> None:
    _RecordingOpenAI.calls.clear()
    monkeypatch.setattr(evidence_transport, "OpenAI", _RecordingOpenAI)
    _patch_mtplx_constants(monkeypatch, evidence_transport)
    config = ModelConfigContract(
        model_config_id="mtplx-normalizer-config",
        provider="mtplx",
        model=MTPLX_MODEL,
        reasoning_effort="medium",
        parameters={"max_tokens": 8192, "temperature": 0.0},
    )
    transport = evidence_transport.evidence_normalizer_transport_from_model_config(config)
    assert _RecordingOpenAI.calls[0]["base_url"] == f"{MTPLX_BASE_URL}/v1"
    kwargs = transport._completion_kwargs([{"role": "user", "content": "probe"}])
    assert kwargs["model"] == MTPLX_MODEL
    assert kwargs["reasoning_effort"] == "medium"
    assert kwargs["temperature"] == 0.0
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "extra_body" not in kwargs


def test_real_probe_payload_is_strict_and_echoes_exact_route_identity() -> None:
    payload = _strict_completion_payload(MTPLX_MODEL, "medium")
    assert payload["model"] == MTPLX_MODEL
    assert payload["reasoning_effort"] == "medium"
    assert payload["max_tokens"] == 512
    assert MTPLX_MODEL in payload["messages"][1]["content"]
    _assert_strict_json_schema(payload)
    schema = payload["response_format"]["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["route"]["enum"] == [MTPLX_MODEL]


def test_legacy_review_kwargs_carry_mtplx_reasoning_without_deepseek_body(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "REVIEW_BACKEND", "mtplx")
    monkeypatch.setattr(llm_client, "REVIEW_REASONING_EFFORT", "medium")
    kwargs = llm_client._review_completion_kwargs(
        model=MTPLX_MODEL,
        messages=[{"role": "user", "content": "probe"}],
        temperature=0.3,
        max_tokens=128,
    )
    assert kwargs["model"] == MTPLX_MODEL
    assert kwargs["reasoning_effort"] == "medium"
    assert "extra_body" not in kwargs


def test_legacy_client_selection_has_no_silent_remote_or_ocr_fallback(monkeypatch) -> None:
    semantic_client = object()
    ocr_client = object()

    monkeypatch.setattr(llm_client, "_get_mtplx_client", lambda: semantic_client)
    monkeypatch.setattr(llm_client, "_get_omlx_client", lambda: ocr_client)
    monkeypatch.setattr(
        llm_client,
        "_get_deepseek_client",
        lambda: (_ for _ in ()).throw(AssertionError("DeepSeek fallback invoked")),
    )
    monkeypatch.setattr(llm_client, "REVIEW_BACKEND", "mtplx")
    monkeypatch.setattr(llm_client, "DECONSTRUCT_BACKEND", "mtplx")
    monkeypatch.setattr(llm_client, "OCR_BACKEND", "omlx")

    assert llm_client._get_review_client() is semantic_client
    assert llm_client._get_deconstruct_client() is semantic_client
    assert llm_client._get_ocr_client() is ocr_client


def test_startup_script_has_dual_service_identity_checks_and_is_shell_valid() -> None:
    script_path = ROOT / "scripts" / "start_enrollment_review.command"
    script = script_path.read_text(encoding="utf-8")
    subprocess.run(["/bin/zsh", "-n", str(script_path)], check=True)
    for token in (
        "MTPLX_BASE_URL",
        "mtplx-flash-next-optimized-speed",
        "MTPLX_URL",
        "/v1/models",
        "oMLX",
        "mtplx",
        "medium",
    ):
        assert token in script
    assert "oMLX 未就绪" in script
    assert "MTPLX 未就绪" in script
    assert script.index("oMLX") != script.index("MTPLX")


def test_mtplx_service_wrapper_is_shell_valid_and_forwards_frozen_identity() -> None:
    script_path = ROOT / "scripts" / "run_mtplx_service.sh"
    script = script_path.read_text(encoding="utf-8")
    subprocess.run(["/bin/zsh", "-n", str(script_path)], check=True)
    for token in (
        "quickstart",
        "--host",
        "--port",
        "--model",
        "--model-id",
        "--reasoning-effort",
        "--no-stats-footer",
        "mtplx-flash-next-optimized-speed",
        "medium",
    ):
        assert token in script


# Qwen3.8-27B family identities retired from the MTPLX product route
# (docs/REARCHITECTURE_FINAL_DESIGN_20260812.md: "Qwen3.8-27B 暂不进入现行
# 产品路由"). Test fixtures may keep them as parameterization and
# forbidden-identity anchors; route-defining surfaces may not.
LEGACY_MTPLX_27B_IDENTITIES = (
    "mtplx-qwen38-27b-optimized-quality",
    "pocketaihub-qwen3.8-27b-abliterated-mtplx-optimized-speed",
)

_LEGACY_ROUTE_SURFACES = (
    ".env.example",
    "scripts/probe_mtplx_semantic_route.py",
    "scripts/run_enrollment_review_service.sh",
    "scripts/run_mtplx_service.sh",
    "scripts/run_phase5_first_batch_probe.py",
    "scripts/start_enrollment_review.command",
)


def test_route_model_defaults_never_use_legacy_27b_identity() -> None:
    values = _config_probe()
    for name in (
        "MTPLX_MODEL",
        "DECONSTRUCT_MODEL",
        "EVIDENCE_NORMALIZER_MODEL",
        "PHASE_APPLICABILITY_MODEL",
        "REVIEW_MODEL",
    ):
        assert values[name] not in LEGACY_MTPLX_27B_IDENTITIES, (
            f"{name} fell back to a legacy Qwen3.8-27B identity: {values[name]}"
        )


def test_route_defining_surfaces_carry_no_legacy_27b_identity() -> None:
    scanned = list(_LEGACY_ROUTE_SURFACES) + [
        str(path.relative_to(ROOT)) for path in sorted((ROOT / "app").rglob("*.py"))
    ]
    assert len(scanned) > len(_LEGACY_ROUTE_SURFACES), "app/ scan lost its targets"
    for rel in scanned:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for identity in LEGACY_MTPLX_27B_IDENTITIES:
            assert identity not in text, (
                f"legacy MTPLX Qwen3.8-27B identity re-introduced in {rel}: {identity}"
            )


def test_phase5_probe_harness_defaults_to_mtplx_without_changing_ocr() -> None:
    script = (ROOT / "scripts" / "run_phase5_first_batch_probe.py").read_text(
        encoding="utf-8"
    )
    assert "default=MTPLX_BASE_URL" in script
    assert "default=MTPLX_MODEL" in script
    assert "default=MTPLX_REASONING_EFFORT" in script
    assert 'default="mtplx"' in script
    assert 'backend="omlx"' not in script
