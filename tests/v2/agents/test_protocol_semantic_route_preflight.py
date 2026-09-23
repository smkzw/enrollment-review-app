"""Fault-injection tests for ENROLLMENT_ENV_FILE and semantic route preflight.

No live network. Secrets must never appear in failure text or audit payloads.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import app.agents.protocol_semantic_model_router as router
import app.config as app_config
from app.agents.protocol_semantic_model_router import ProtocolSemanticRouteCandidate
from app.agents.protocol_semantic_route_preflight import (
    ProtocolSemanticRoutePreflightError,
    candidate_endpoint_url,
    preflight_protocol_semantic_routes,
    sanitize_preflight_text,
)
from app.config import (
    ENROLLMENT_ENV_FILE_VAR,
    load_enrollment_env_file,
    parse_env_file_values,
    resolve_enrollment_env_file,
)

ROOT = Path(__file__).resolve().parents[3]
SECRET = "sk-test-preflight-secret-do-not-leak-0123456789"


@pytest.fixture(autouse=True)
def _reset_process_route_after_test(monkeypatch):
    # Most legacy cases in this module exercise the original direct GLM route.
    # Provider-specific cases below declare their route explicitly.
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_PROVIDER", "zhipu-coding-plan")
    router.reset_active_protocol_semantic_routes()
    yield
    router.reset_active_protocol_semantic_routes()


def _subprocess_config_snippet(env: dict[str, str], script: str) -> str:
    return subprocess.check_output(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
    )


def test_parse_env_file_strips_quotes(tmp_path: Path):
    path = tmp_path / "sample.env"
    path.write_text(
        "FOO='bar'\nBAR=\"baz\"\n# comment\nEMPTY=\n",
        encoding="utf-8",
    )
    values = parse_env_file_values(path)
    assert values["FOO"] == "bar"
    assert values["BAR"] == "baz"
    assert values["EMPTY"] == ""


def test_resolve_enrollment_env_file_requires_explicit_path(tmp_path: Path):
    missing = tmp_path / "missing.env"
    with pytest.raises(RuntimeError, match="显式环境文件不存在") as caught:
        resolve_enrollment_env_file(
            environ={ENROLLMENT_ENV_FILE_VAR: str(missing)},
            default_env_path=tmp_path / "unused.env",
        )
    assert SECRET not in str(caught.value)
    assert str(missing) in str(caught.value)


def test_load_enrollment_env_file_setdefault_and_glm_mapping(tmp_path: Path):
    path = tmp_path / "enrollment.env"
    path.write_text(
        "INDEPENDENT_VLM_API_KEY=shared-from-file\n"
        "DECONSTRUCT_GLM_API_KEY=\n"
        "ALREADY_SET=from-file\n",
        encoding="utf-8",
    )
    environ = {
        ENROLLMENT_ENV_FILE_VAR: str(path),
        "ALREADY_SET": "from-process",
    }
    loaded = load_enrollment_env_file(environ=environ, default_env_path=tmp_path / "nope")
    assert loaded == path.resolve()
    assert environ["ALREADY_SET"] == "from-process"
    assert environ["INDEPENDENT_VLM_API_KEY"] == "shared-from-file"


def test_subprocess_loads_enrollment_env_file_into_deconstruct_glm_key(tmp_path: Path):
    path = tmp_path / "worktree.env"
    path.write_text(
        f"INDEPENDENT_VLM_API_KEY={SECRET}\nDECONSTRUCT_GLM_API_KEY=\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    for key in (
        "DECONSTRUCT_GLM_API_KEY",
        "INDEPENDENT_VLM_API_KEY",
        ENROLLMENT_ENV_FILE_VAR,
    ):
        env.pop(key, None)
    env[ENROLLMENT_ENV_FILE_VAR] = str(path)
    # Force a clean import path by using -c in a subprocess.
    output = _subprocess_config_snippet(
        env,
        "from app.config import DECONSTRUCT_GLM_API_KEY, ENROLLMENT_ENV_FILE; "
        "print(ENROLLMENT_ENV_FILE); "
        "print('yes' if bool(DECONSTRUCT_GLM_API_KEY) else 'no'); "
        "print(str(len(DECONSTRUCT_GLM_API_KEY)))",
    )
    lines = output.strip().splitlines()
    assert lines[0] == str(path.resolve())
    assert lines[1] == "yes"
    assert int(lines[2]) == len(SECRET)
    assert SECRET not in output


def test_missing_glm_key_fails_closed_without_third_model_substitution(monkeypatch):
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_API_KEY", "")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_COMPLEX", "")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_SHORT", "")
    monkeypatch.setattr(app_config, "DEEPSEEK_API_KEY", SECRET)
    monkeypatch.setattr(app_config, "DECONSTRUCT_GLM_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", SECRET)
    monkeypatch.setenv("DECONSTRUCT_GLM_API_KEY", "")

    # 默认链只声明 GLM：GLM 凭据缺失时即使 DeepSeek 凭据在环，也不得隐式
    # 切换第三模型——预检显式失败并给出中文指引。
    with pytest.raises(ProtocolSemanticRoutePreflightError) as caught:
        preflight_protocol_semantic_routes(
            mode="degrade",
            probe_endpoints=False,
            raise_on_error=True,
        )
    message = str(caught.value)
    assert "启动失败" in message
    assert "均不可执行" in message
    assert SECRET not in message
    report = caught.value.report
    assert report.complex_declared_identities == [
        "zhipu-coding-plan:glm-5.3-flash:high"
    ]
    assert report.complex_executable_identities == []
    assert report.degraded is True
    assert SECRET not in str(report.as_audit_dict())


def test_explicit_route_spec_restores_degrade_path_with_other_provider(
    monkeypatch,
):
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_API_KEY", "")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(
        router,
        "DECONSTRUCT_ROUTE_COMPLEX",
        "mtplx:mtplx-flash-next-optimized-speed:xhigh",
    )
    monkeypatch.setattr(
        router,
        "DECONSTRUCT_ROUTE_SHORT",
        "mtplx:mtplx-flash-next-optimized-speed:xhigh",
    )
    monkeypatch.setattr(app_config, "DECONSTRUCT_GLM_API_KEY", "")
    monkeypatch.setenv("DECONSTRUCT_GLM_API_KEY", "")

    # 显式路由规格命名了其他模型：声明链全部可执行，预检按声明链放行，
    # 缺失的 GLM 凭据不会触发隐式第三模型替换。
    report = preflight_protocol_semantic_routes(
        mode="degrade",
        probe_endpoints=False,
        raise_on_error=True,
    )
    assert report.complex_declared_identities == [
        "mtplx:mtplx-flash-next-optimized-speed:xhigh"
    ]
    assert report.complex_executable_identities == [
        "mtplx:mtplx-flash-next-optimized-speed:xhigh"
    ]
    assert report.blocking_errors == []
    assert SECRET not in str(report.as_audit_dict())


def test_missing_credentials_fail_closed_in_strict_mode(monkeypatch):
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_API_KEY", "")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_COMPLEX", "")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_SHORT", "")
    monkeypatch.setattr(app_config, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(app_config, "DECONSTRUCT_GLM_API_KEY", "")
    monkeypatch.setattr(app_config, "INDEPENDENT_VLM_API_KEY", SECRET)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("DECONSTRUCT_GLM_API_KEY", "")
    # Keep a unique secret in the environment to prove redaction if raised text
    # somehow interpolates env values.
    monkeypatch.setenv("INDEPENDENT_VLM_API_KEY", SECRET)

    with pytest.raises(ProtocolSemanticRoutePreflightError) as caught:
        preflight_protocol_semantic_routes(
            mode="strict",
            probe_endpoints=False,
            raise_on_error=True,
        )
    message = str(caught.value)
    assert "启动失败" in message
    assert "不可执行" in message
    assert SECRET not in message
    assert SECRET not in str(caught.value.report.as_audit_dict())


def test_endpoint_fault_injection_does_not_touch_network(monkeypatch):
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_API_KEY", "configured-glm-key")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_COMPLEX", "")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_SHORT", "")
    monkeypatch.setattr(app_config, "DEEPSEEK_API_KEY", "configured-deepseek-key")
    monkeypatch.setenv("DECONSTRUCT_GLM_API_KEY", "configured-glm-key")
    monkeypatch.setattr(app_config, "DECONSTRUCT_GLM_API_KEY", "configured-glm-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "configured-deepseek-key")
    monkeypatch.setenv("DECONSTRUCT_GLM_API_KEY", "configured-glm-key")
    monkeypatch.setenv("INDEPENDENT_VLM_API_KEY", SECRET)

    probed: list[str] = []

    def _fake_prober(url: str) -> tuple[bool, str]:
        probed.append(url)
        return False, f"端点不可达（注入故障）；secret={SECRET}"

    with pytest.raises(ProtocolSemanticRoutePreflightError) as caught:
        preflight_protocol_semantic_routes(
            mode="degrade",
            probe_endpoints=True,
            endpoint_prober=_fake_prober,
            raise_on_error=True,
        )
    assert probed, "expected injectable prober to run"
    message = str(caught.value)
    assert "启动失败" in message
    assert "均不可执行" in message or "端点" in message
    assert SECRET not in message
    for item in caught.value.report.complex_candidates:
        assert item.executable is False
        assert item.endpoint_status == "unreachable"
        assert SECRET not in (item.detail or "")


def test_create_app_preflight_failure_is_chinese_and_secret_free(
    data_paths,
    monkeypatch,
):
    from fastapi.testclient import TestClient

    from app.api.v2.app import create_app

    monkeypatch.setattr(router, "DECONSTRUCT_GLM_API_KEY", "")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_COMPLEX", "")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_SHORT", "")
    monkeypatch.setattr(app_config, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(app_config, "DECONSTRUCT_GLM_API_KEY", "")
    monkeypatch.setattr(app_config, "INDEPENDENT_VLM_API_KEY", SECRET)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("DECONSTRUCT_GLM_API_KEY", "")
    monkeypatch.setenv("INDEPENDENT_VLM_API_KEY", SECRET)
    monkeypatch.setenv("ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT", "1")
    monkeypatch.setenv("ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT_MODE", "strict")
    monkeypatch.setenv("ENROLLMENT_SEMANTIC_ENDPOINT_PREFLIGHT", "0")

    app = create_app(
        data_paths=data_paths,
        run_runner=False,
        semantic_route_preflight=True,
    )
    with pytest.raises(ProtocolSemanticRoutePreflightError) as caught:
        with TestClient(app):
            pass
    assert "启动失败" in str(caught.value)
    assert SECRET not in str(caught.value)


def test_create_app_persists_successful_preflight_audit(data_paths, monkeypatch):
    import json
    from fastapi.testclient import TestClient

    from app.api.v2.app import create_app

    monkeypatch.setattr(router, "DECONSTRUCT_GLM_API_KEY", "configured-glm-key")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_COMPLEX", "")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_SHORT", "")
    monkeypatch.setattr(app_config, "DEEPSEEK_API_KEY", "configured-deepseek-key")
    monkeypatch.setenv("DECONSTRUCT_GLM_API_KEY", "configured-glm-key")

    app = create_app(
        data_paths=data_paths,
        run_runner=False,
        semantic_route_preflight=True,
        semantic_route_endpoint_prober=lambda _url: (True, "端点可达"),
    )
    with TestClient(app):
        audit_path = (
            data_paths.root / "runtime" / "protocol-semantic-route-preflight.json"
        )
        payload = json.loads(audit_path.read_text(encoding="utf-8"))
        assert payload["audit_contract"] == "protocol-semantic-route-preflight/v1"
        assert payload["complex_executable_identities"]
        assert "configured-glm-key" not in str(payload)


def test_candidate_availability_still_mentions_glm_key_name_only(monkeypatch):
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_API_KEY", "")
    detail = router.candidate_availability_error(
        ProtocolSemanticRouteCandidate(
            backend="zhipu-coding-plan",
            model="glm-5.3-flash",
            reasoning_effort="high",
        )
    )
    assert detail is not None
    assert "DECONSTRUCT_GLM_API_KEY" in detail
    assert SECRET not in detail


@pytest.mark.parametrize(
    ("provider", "model", "base_env", "base_url"),
    (
        ("cms-router", "glm-5.3-flash", "CMS_ROUTER_BASE_URL", "http://127.0.0.1:20128"),
        ("opencode-go", "deepseek-v4.1-flash", "OPENCODE_BASE_URL", "https://models.example.test/api"),
    ),
)
def test_candidate_endpoint_uses_shared_provider_profile(
    monkeypatch,
    provider,
    model,
    base_env,
    base_url,
):
    monkeypatch.setenv(base_env, base_url)
    endpoint = candidate_endpoint_url(
        ProtocolSemanticRouteCandidate(
            backend=provider,
            model=model,
            reasoning_effort="high",
        )
    )
    assert endpoint == base_url + "/v1"


def test_cms_router_preflight_uses_declared_endpoint(monkeypatch):
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(
        router,
        "DECONSTRUCT_ROUTE_COMPLEX",
        "cms-router:glm-5.3-flash:high",
    )
    monkeypatch.setattr(
        router,
        "DECONSTRUCT_ROUTE_SHORT",
        "cms-router:another-glm-alias:low",
    )
    monkeypatch.setenv("CMS_ROUTER_API_KEY", "configured-cms-router-key")
    monkeypatch.setenv("CMS_ROUTER_BASE_URL", "http://127.0.0.1:20128/v1")

    report = preflight_protocol_semantic_routes(
        mode="strict",
        probe_endpoints=True,
        endpoint_prober=lambda url: (url == "http://127.0.0.1:20128/v1", "可达"),
    )

    assert report.blocking_errors == []
    assert report.complex_executable_identities == [
        "cms-router:glm-5.3-flash:high"
    ]
    assert report.short_executable_identities == [
        "cms-router:another-glm-alias:low"
    ]
