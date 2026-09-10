"""Startup / job-entry preflight for declared protocol-semantic routes.

Validates that declared graded/pinned candidates are credentialed and, when
requested, that their endpoints accept a TCP probe. Failure messages stay in
Chinese and never include secret values. Network probes are injectable so tests
can fault-inject without touching the real network.
"""
from __future__ import annotations

import os
import socket
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

from app.agents.protocol_semantic_model_router import (
    GRADE_COMPLEX,
    GRADE_SHORT,
    ProtocolSemanticRouteCandidate,
    ProtocolSemanticRouteMode,
    ProtocolSemanticTaskGrade,
    candidate_availability_error,
    activate_protocol_semantic_routes,
    reset_active_protocol_semantic_routes,
    resolve_route_mode,
    select_protocol_semantic_route_candidates,
)
from app.config import (
    DECONSTRUCT_GLM_BASE_URL,
    DEEPSEEK_BASE_URL,
    ENROLLMENT_ENV_FILE_VAR,
    MTPLX_BASE_URL,
    OMLX_BASE_URL,
)

PreflightMode = Literal["degrade", "strict"]
EndpointProber = Callable[[str], tuple[bool, str]]

_SECRET_ENV_NAMES = (
    "DECONSTRUCT_GLM_API_KEY",
    "INDEPENDENT_VLM_API_KEY",
    "DEEPSEEK_API_KEY",
    "MTPLX_API_KEY",
    "OMLX_API_KEY",
    "MINIMAX_API_KEY",
)


@dataclass(frozen=True)
class ProtocolSemanticCandidatePreflight:
    grade: ProtocolSemanticTaskGrade | str
    identity: str
    backend: str
    model: str
    reasoning_effort: str
    credential_status: Literal["configured", "missing"]
    endpoint_status: Literal["reachable", "unreachable", "not_probed", "unconfigured"]
    endpoint_url: str | None
    detail: str | None = None
    executable: bool = False

    def as_audit_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProtocolSemanticRoutePreflightReport:
    """Non-secret summary of declared vs executable semantic routes."""

    route_mode: ProtocolSemanticRouteMode | str
    mode: PreflightMode
    endpoint_probe_enabled: bool
    env_file_var: str = ENROLLMENT_ENV_FILE_VAR
    env_file_configured: bool = False
    complex_candidates: list[ProtocolSemanticCandidatePreflight] = field(
        default_factory=list
    )
    short_candidates: list[ProtocolSemanticCandidatePreflight] = field(
        default_factory=list
    )
    complex_declared_identities: list[str] = field(default_factory=list)
    short_declared_identities: list[str] = field(default_factory=list)
    complex_executable_identities: list[str] = field(default_factory=list)
    short_executable_identities: list[str] = field(default_factory=list)
    degraded: bool = False
    blocking_errors: list[str] = field(default_factory=list)

    def as_audit_dict(self) -> dict[str, Any]:
        return {
            "audit_contract": "protocol-semantic-route-preflight/v1",
            "route_mode": self.route_mode,
            "mode": self.mode,
            "endpoint_probe_enabled": self.endpoint_probe_enabled,
            "env_file_var": self.env_file_var,
            "env_file_configured": self.env_file_configured,
            "complex_declared_identities": list(self.complex_declared_identities),
            "short_declared_identities": list(self.short_declared_identities),
            "complex_executable_identities": list(self.complex_executable_identities),
            "short_executable_identities": list(self.short_executable_identities),
            "degraded": self.degraded,
            "blocking_errors": list(self.blocking_errors),
            "complex_candidates": [
                item.as_audit_dict() for item in self.complex_candidates
            ],
            "short_candidates": [
                item.as_audit_dict() for item in self.short_candidates
            ],
        }


class ProtocolSemanticRoutePreflightError(RuntimeError):
    """Chinese fail-closed startup / job-entry error without secrets."""

    def __init__(self, message: str, *, report: ProtocolSemanticRoutePreflightReport):
        super().__init__(sanitize_preflight_text(message))
        self.report = report


def sanitize_preflight_text(
    text: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Remove any accidental secret substrings from operator-facing text."""

    env = os.environ if environ is None else environ
    cleaned = str(text or "")
    for name in _SECRET_ENV_NAMES:
        secret = str(env.get(name, "") or "").strip()
        if len(secret) >= 8 and secret in cleaned:
            cleaned = cleaned.replace(secret, f"<{name}>")
    return cleaned


def _truthy(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def resolve_preflight_mode(raw: str | None = None) -> PreflightMode:
    selected = (
        raw
        if raw is not None
        else os.getenv("ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT_MODE", "degrade")
    )
    normalized = str(selected or "degrade").strip().lower()
    if normalized in {"strict", "fail_closed", "fail-closed"}:
        return "strict"
    if normalized in {"degrade", "explicit_degrade", "explicit-degrade"}:
        return "degrade"
    raise ValueError(
        "语义路由预检模式仅支持 degrade/strict，"
        f"当前值={normalized or '空值'}"
    )


def candidate_endpoint_url(candidate: ProtocolSemanticRouteCandidate) -> str | None:
    backend = candidate.backend.strip().lower()
    if backend in {"zhipu-coding-plan", "glm"}:
        return (DECONSTRUCT_GLM_BASE_URL or "").strip() or None
    if backend == "deepseek":
        return (DEEPSEEK_BASE_URL or "").strip() or None
    if backend in {"mtplx", "mtplx-api"}:
        return (MTPLX_BASE_URL or "").strip() or None
    if backend == "omlx":
        return (OMLX_BASE_URL or "").strip() or None
    return None


def default_tcp_endpoint_prober(url: str, *, timeout_seconds: float = 2.0) -> tuple[bool, str]:
    """Probe host:port reachability without sending credentials."""

    raw = (url or "").strip()
    if not raw:
        return False, "端点地址为空"
    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    host = parsed.hostname
    if not host:
        return False, "端点地址缺少主机名"
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True, "端点端口可达"
    except OSError as exc:
        return False, f"端点不可达（{host}:{port}）：{exc.__class__.__name__}"


def _evaluate_candidate(
    candidate: ProtocolSemanticRouteCandidate,
    *,
    grade: ProtocolSemanticTaskGrade,
    probe_endpoints: bool,
    endpoint_prober: EndpointProber,
) -> ProtocolSemanticCandidatePreflight:
    credential_error = candidate_availability_error(candidate)
    endpoint_url = candidate_endpoint_url(candidate)
    if credential_error is not None:
        return ProtocolSemanticCandidatePreflight(
            grade=grade,
            identity=candidate.identity,
            backend=candidate.backend,
            model=candidate.model,
            reasoning_effort=candidate.reasoning_effort,
            credential_status="missing",
            endpoint_status="unconfigured",
            endpoint_url=endpoint_url,
            detail=sanitize_preflight_text(credential_error),
            executable=False,
        )
    if not probe_endpoints:
        return ProtocolSemanticCandidatePreflight(
            grade=grade,
            identity=candidate.identity,
            backend=candidate.backend,
            model=candidate.model,
            reasoning_effort=candidate.reasoning_effort,
            credential_status="configured",
            endpoint_status="not_probed",
            endpoint_url=endpoint_url,
            detail="凭据已配置；本次未探测端点连通性",
            executable=True,
        )
    if not endpoint_url:
        detail = f"{candidate.identity} 未配置服务地址"
        return ProtocolSemanticCandidatePreflight(
            grade=grade,
            identity=candidate.identity,
            backend=candidate.backend,
            model=candidate.model,
            reasoning_effort=candidate.reasoning_effort,
            credential_status="configured",
            endpoint_status="unconfigured",
            endpoint_url=None,
            detail=detail,
            executable=False,
        )
    ok, reason = endpoint_prober(endpoint_url)
    detail = sanitize_preflight_text(reason)
    return ProtocolSemanticCandidatePreflight(
        grade=grade,
        identity=candidate.identity,
        backend=candidate.backend,
        model=candidate.model,
        reasoning_effort=candidate.reasoning_effort,
        credential_status="configured",
        endpoint_status="reachable" if ok else "unreachable",
        endpoint_url=endpoint_url,
        detail=detail,
        executable=bool(ok),
    )


def _grade_errors(
    *,
    grade_label: str,
    declared: Sequence[ProtocolSemanticCandidatePreflight],
    executable_identities: Sequence[str],
    mode: PreflightMode,
) -> list[str]:
    errors: list[str] = []
    if not declared:
        errors.append(f"{grade_label}未声明任何语义路由候选")
        return errors
    if not executable_identities:
        errors.append(
            f"{grade_label}声明路由均不可执行。"
            f"请设置 {ENROLLMENT_ENV_FILE_VAR} 指向含凭据的环境文件，"
            "或在启动前显式注入所需密钥/端点后重试。"
        )
        return errors
    if mode == "strict":
        missing = [item for item in declared if not item.executable]
        for item in missing:
            status = item.detail or (
                "凭据未配置" if item.credential_status == "missing" else "端点不可用"
            )
            errors.append(
                f"{grade_label}声明候选 {item.identity} 不可执行：{status}"
            )
    return errors


def preflight_protocol_semantic_routes(
    *,
    route_mode: ProtocolSemanticRouteMode | str | None = None,
    mode: PreflightMode | str | None = None,
    probe_endpoints: bool | None = None,
    endpoint_prober: EndpointProber | None = None,
    raise_on_error: bool = True,
    environ: Mapping[str, str] | None = None,
) -> ProtocolSemanticRoutePreflightReport:
    """Validate declared semantic routes before service/job start."""

    reset_active_protocol_semantic_routes()
    env = os.environ if environ is None else environ
    resolved_mode = resolve_preflight_mode(
        None if mode is None else str(mode)
    )
    resolved_route_mode = resolve_route_mode(
        None if route_mode is None else route_mode
    )
    endpoint_enabled = (
        bool(probe_endpoints)
        if probe_endpoints is not None
        else _truthy(env.get("ENROLLMENT_SEMANTIC_ENDPOINT_PREFLIGHT"), True)
    )
    prober = endpoint_prober or default_tcp_endpoint_prober
    complex_declared = select_protocol_semantic_route_candidates(
        GRADE_COMPLEX, route_mode=resolved_route_mode
    )
    short_declared = select_protocol_semantic_route_candidates(
        GRADE_SHORT, route_mode=resolved_route_mode
    )
    complex_results = [
        _evaluate_candidate(
            candidate,
            grade=GRADE_COMPLEX,
            probe_endpoints=endpoint_enabled,
            endpoint_prober=prober,
        )
        for candidate in complex_declared
    ]
    short_results = [
        _evaluate_candidate(
            candidate,
            grade=GRADE_SHORT,
            probe_endpoints=endpoint_enabled,
            endpoint_prober=prober,
        )
        for candidate in short_declared
    ]
    complex_executable = [item.identity for item in complex_results if item.executable]
    short_executable = [item.identity for item in short_results if item.executable]
    env_file_configured = bool(str(env.get(ENROLLMENT_ENV_FILE_VAR, "") or "").strip())
    report = ProtocolSemanticRoutePreflightReport(
        route_mode=resolved_route_mode,
        mode=resolved_mode,
        endpoint_probe_enabled=endpoint_enabled,
        env_file_configured=env_file_configured,
        complex_candidates=complex_results,
        short_candidates=short_results,
        complex_declared_identities=[item.identity for item in complex_declared],
        short_declared_identities=[item.identity for item in short_declared],
        complex_executable_identities=complex_executable,
        short_executable_identities=short_executable,
        degraded=(
            complex_executable != [item.identity for item in complex_declared]
            or short_executable != [item.identity for item in short_declared]
        ),
    )
    report.blocking_errors.extend(
        _grade_errors(
            grade_label="复杂方案语义路由",
            declared=complex_results,
            executable_identities=complex_executable,
            mode=resolved_mode,
        )
    )
    report.blocking_errors.extend(
        _grade_errors(
            grade_label="短提示语义路由",
            declared=short_results,
            executable_identities=short_executable,
            mode=resolved_mode,
        )
    )
    report.blocking_errors = [
        sanitize_preflight_text(item, environ=env) for item in report.blocking_errors
    ]
    if report.blocking_errors and raise_on_error:
        joined = "；".join(report.blocking_errors)
        raise ProtocolSemanticRoutePreflightError(
            "【启动失败】方案语义路由预检未通过：" + joined,
            report=report,
        )
    if not report.blocking_errors:
        activate_protocol_semantic_routes(
            complex_identities=report.complex_executable_identities,
            short_identities=report.short_executable_identities,
        )
    return report


def should_run_semantic_route_preflight(
    *,
    environ: Mapping[str, str] | None = None,
    explicit: bool | None = None,
) -> bool:
    if explicit is not None:
        return bool(explicit)
    env = os.environ if environ is None else environ
    return _truthy(env.get("ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT"), True)


__all__ = [
    "EndpointProber",
    "PreflightMode",
    "ProtocolSemanticCandidatePreflight",
    "ProtocolSemanticRoutePreflightError",
    "ProtocolSemanticRoutePreflightReport",
    "candidate_endpoint_url",
    "default_tcp_endpoint_prober",
    "preflight_protocol_semantic_routes",
    "resolve_preflight_mode",
    "sanitize_preflight_text",
    "should_run_semantic_route_preflight",
]
