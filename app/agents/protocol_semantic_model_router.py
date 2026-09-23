"""Project-agnostic graded model routing for protocol semantic deconstruction.

The default graded route for both complex and short protocol-semantic work is
the configured GLM-5.3-Flash profile alone. MTPLX/DeepSeek candidates are only
used when an explicit ``DECONSTRUCT_ROUTE_COMPLEX``/``DECONSTRUCT_ROUTE_SHORT``
spec or a pinned route names them; the default chain never silently substitutes
a third model when GLM is unavailable. Provider switches across explicit
candidates are whole-attempt only: no cross-model session continuation,
candidate merge, or silent fallback. Routing decisions must not hardcode
study/protocol IDs.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.config import (
    DECONSTRUCT_BACKEND,
    DECONSTRUCT_GLM_API_KEY,
    DECONSTRUCT_GLM_MODEL,
    DECONSTRUCT_GLM_PROVIDER,
    DECONSTRUCT_GLM_REASONING_EFFORT,
    DECONSTRUCT_MODEL,
    DECONSTRUCT_REASONING_EFFORT,
    DECONSTRUCT_ROUTE_COMPLEX,
    DECONSTRUCT_ROUTE_MODE,
    DECONSTRUCT_ROUTE_SHORT,
    DECONSTRUCT_SHORT_PROMPT_MAX_INPUT_TOKENS,
)
from app.protocols.adaptive_batch_budget import estimate_text_tokens

ProtocolSemanticTaskGrade = Literal[
    "complex_protocol_semantic",
    "short_prompt_semantic",
]
ProtocolSemanticRouteMode = Literal["graded", "pinned"]

GRADE_COMPLEX: ProtocolSemanticTaskGrade = "complex_protocol_semantic"
GRADE_SHORT: ProtocolSemanticTaskGrade = "short_prompt_semantic"

_ACTIVE_ROUTE_IDENTITIES: dict[ProtocolSemanticTaskGrade, frozenset[str]] | None = None


@dataclass(frozen=True)
class ProtocolSemanticRouteCandidate:
    """One ordered provider/model/effort candidate for a route attempt."""

    backend: str
    model: str
    reasoning_effort: str

    @property
    def identity(self) -> str:
        return f"{self.backend}:{self.model}:{self.reasoning_effort}"

    def as_audit_dict(self) -> dict[str, str]:
        return {
            "backend": self.backend,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "identity": self.identity,
        }


@dataclass(frozen=True)
class ProtocolSemanticGradeDecision:
    grade: ProtocolSemanticTaskGrade
    parent_rule_count: int
    token_estimate: int
    batch_total: int
    short_prompt_max_input_tokens: int
    reasons: tuple[str, ...] = ()

    def as_audit_dict(self) -> dict[str, Any]:
        return {
            "grade": self.grade,
            "parent_rule_count": self.parent_rule_count,
            "token_estimate": self.token_estimate,
            "batch_total": self.batch_total,
            "short_prompt_max_input_tokens": self.short_prompt_max_input_tokens,
            "reasons": list(self.reasons),
        }


@dataclass
class ProtocolSemanticRouteAttemptRecord:
    route_attempt: int
    grade: ProtocolSemanticTaskGrade | str
    backend: str
    model: str
    reasoning_effort: str
    outcome: str
    error_class: str | None = None
    detail: str | None = None
    session_id: str | None = None
    cache_hits: int = 0
    accepted_batches: int = 0
    semantic_repair_limit: int | None = None
    discarded_merged_candidate: bool = False

    def as_audit_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProtocolSemanticRouteAudit:
    """Job-scoped explicit routing ledger for one generate attempt."""

    job_id: str
    route_mode: ProtocolSemanticRouteMode | str
    grade_decision: ProtocolSemanticGradeDecision | None
    ordered_candidates: list[ProtocolSemanticRouteCandidate] = field(
        default_factory=list
    )
    attempts: list[ProtocolSemanticRouteAttemptRecord] = field(default_factory=list)
    final_identity: str | None = None
    final_outcome: str | None = None

    def as_audit_dict(self) -> dict[str, Any]:
        return {
            "audit_contract": "protocol-semantic-route-audit/v1",
            "job_id": self.job_id,
            "route_mode": self.route_mode,
            "grade_decision": (
                None
                if self.grade_decision is None
                else self.grade_decision.as_audit_dict()
            ),
            "ordered_candidates": [
                item.as_audit_dict() for item in self.ordered_candidates
            ],
            "attempts": [item.as_audit_dict() for item in self.attempts],
            "final_identity": self.final_identity,
            "final_outcome": self.final_outcome,
        }


def resolve_route_mode(raw: str | None = None) -> ProtocolSemanticRouteMode:
    selected = (raw if raw is not None else DECONSTRUCT_ROUTE_MODE).strip().lower()
    if selected not in {"graded", "pinned"}:
        raise ValueError(
            f"DECONSTRUCT_ROUTE_MODE 仅支持 graded/pinned，当前值={selected or '空值'}"
        )
    return selected  # type: ignore[return-value]


def classify_protocol_semantic_task_grade(
    *,
    parent_rule_count: int,
    prompt_text: str,
    batch_total: int,
    short_prompt_max_input_tokens: int | None = None,
) -> ProtocolSemanticGradeDecision:
    """Classify at session-start / run-entry only (never mid-continue_session)."""

    if parent_rule_count < 0:
        raise ValueError("parent_rule_count 不能为负数")
    if batch_total < 1:
        raise ValueError("batch_total 必须 >= 1")
    max_tokens = (
        DECONSTRUCT_SHORT_PROMPT_MAX_INPUT_TOKENS
        if short_prompt_max_input_tokens is None
        else short_prompt_max_input_tokens
    )
    if max_tokens < 1:
        raise ValueError("short_prompt_max_input_tokens 必须为正数")
    token_estimate = estimate_text_tokens(prompt_text)
    reasons: list[str] = []
    is_short = True
    if parent_rule_count > 1:
        is_short = False
        reasons.append("parent_rule_count_gt_1")
    if token_estimate > max_tokens:
        is_short = False
        reasons.append("token_estimate_gt_short_limit")
    if batch_total > 1:
        is_short = False
        reasons.append("batch_total_gt_1")
    if is_short:
        reasons.append("all_short_gates_passed")
        grade: ProtocolSemanticTaskGrade = GRADE_SHORT
    else:
        if not reasons:
            reasons.append("default_complex")
        grade = GRADE_COMPLEX
    return ProtocolSemanticGradeDecision(
        grade=grade,
        parent_rule_count=parent_rule_count,
        token_estimate=token_estimate,
        batch_total=batch_total,
        short_prompt_max_input_tokens=max_tokens,
        reasons=tuple(reasons),
    )


def _parse_route_spec(raw: str) -> list[ProtocolSemanticRouteCandidate]:
    text = raw.strip()
    if not text:
        return []
    candidates: list[ProtocolSemanticRouteCandidate] = []
    for part in text.split(","):
        item = part.strip()
        if not item:
            continue
        pieces = [piece.strip() for piece in item.split(":")]
        if len(pieces) != 3 or not all(pieces):
            raise ValueError(
                "路由规格必须是 backend:model:effort 逗号分隔列表，"
                f"无效项={item!r}"
            )
        backend, model, effort = pieces
        candidates.append(
            ProtocolSemanticRouteCandidate(
                backend=backend.lower(),
                model=model,
                reasoning_effort=effort.lower(),
            )
        )
    return candidates


def _default_glm_candidate() -> list[ProtocolSemanticRouteCandidate]:
    """The single default semantic candidate: the configured GLM profile.

    Both grades share it. There is no implicit MTPLX/DeepSeek fallback: other
    models enter a route only through an explicit route spec or pinned config,
    and an unavailable GLM candidate is skipped/reported, never replaced.
    """

    glm_backend = (DECONSTRUCT_GLM_PROVIDER or "zhipu-coding-plan").strip().lower()
    if glm_backend not in {"zhipu-coding-plan", "glm", "cms-router", "cms-smk"}:
        raise ValueError("GLM 服务连接类型配置无效，不能静默替换")
    return [
        ProtocolSemanticRouteCandidate(
            backend=glm_backend,
            model=DECONSTRUCT_GLM_MODEL or "glm-5.3-flash",
            reasoning_effort=DECONSTRUCT_GLM_REASONING_EFFORT or "high",
        )
    ]


def _default_complex_candidates() -> list[ProtocolSemanticRouteCandidate]:
    return _default_glm_candidate()


def _default_short_candidates() -> list[ProtocolSemanticRouteCandidate]:
    return _default_glm_candidate()


def _pinned_candidate() -> ProtocolSemanticRouteCandidate:
    return ProtocolSemanticRouteCandidate(
        backend=DECONSTRUCT_BACKEND.strip().lower(),
        model=DECONSTRUCT_MODEL,
        reasoning_effort=DECONSTRUCT_REASONING_EFFORT,
    )


def select_protocol_semantic_route_candidates(
    grade: ProtocolSemanticTaskGrade,
    *,
    route_mode: ProtocolSemanticRouteMode | None = None,
) -> list[ProtocolSemanticRouteCandidate]:
    mode = resolve_route_mode(None if route_mode is None else route_mode)
    if mode == "pinned":
        candidates = [_pinned_candidate()]
    elif grade == GRADE_SHORT:
        override = _parse_route_spec(DECONSTRUCT_ROUTE_SHORT)
        candidates = override or _default_short_candidates()
    elif grade == GRADE_COMPLEX:
        override = _parse_route_spec(DECONSTRUCT_ROUTE_COMPLEX)
        candidates = override or _default_complex_candidates()
    else:
        raise ValueError(f"未知任务分级：{grade}")
    if _ACTIVE_ROUTE_IDENTITIES is None:
        return candidates
    allowed = _ACTIVE_ROUTE_IDENTITIES.get(grade, frozenset())
    return [item for item in candidates if item.identity in allowed]


def activate_protocol_semantic_routes(
    *,
    complex_identities: list[str],
    short_identities: list[str],
) -> None:
    """Freeze this service process to candidates proven executable at startup."""

    global _ACTIVE_ROUTE_IDENTITIES
    _ACTIVE_ROUTE_IDENTITIES = {
        GRADE_COMPLEX: frozenset(complex_identities),
        GRADE_SHORT: frozenset(short_identities),
    }


def reset_active_protocol_semantic_routes() -> None:
    """Clear process-local startup routing; used on app shutdown and in tests."""

    global _ACTIVE_ROUTE_IDENTITIES
    _ACTIVE_ROUTE_IDENTITIES = None


def candidate_availability_error(
    candidate: ProtocolSemanticRouteCandidate,
) -> str | None:
    """Return an explicit Chinese skip reason when a candidate cannot start."""

    backend = candidate.backend.strip().lower()
    if backend in {"zhipu-coding-plan", "glm", "cms-router", "cms-smk", "opencode-go"}:
        from app.llm.provider_profiles import resolve_openai_connection

        try:
            resolve_openai_connection(
                backend,
                role_base_url_env="DECONSTRUCT_BASE_URL",
                role_api_key_env="DECONSTRUCT_API_KEY",
            )
        except ValueError as exc:
            return f"方案解构服务尚未配置（{exc}）；已显式跳过该候选。"
        return None
    if backend == "deepseek":
        from app.config import DEEPSEEK_API_KEY

        if not (DEEPSEEK_API_KEY or "").strip():
            return (
                "DeepSeek 方案解构服务尚未配置（缺少 DEEPSEEK_API_KEY）；"
                "已显式跳过该候选并继续尝试下一模型。"
            )
        return None
    if backend in {"mtplx", "mtplx-api", "omlx"}:
        return None
    return f"当前方案解构不支持模型供应商 {backend or '空值'}"


def build_transport_for_candidate(candidate: ProtocolSemanticRouteCandidate) -> Any:
    """Construct a fresh transport for one whole route attempt."""

    from app.agents.protocol_semantic_transport import (
        OpenAICompatibleProtocolAgentTransport,
        SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS,
    )

    backend = candidate.backend.strip().lower()
    if backend not in SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS:
        raise ValueError(f"当前方案解构不支持模型供应商 {backend or '空值'}")
    availability = candidate_availability_error(candidate)
    if availability is not None:
        raise ValueError(availability)
    return OpenAICompatibleProtocolAgentTransport(
        backend=backend,
        model=candidate.model,
        reasoning_effort=candidate.reasoning_effort,
    )


def semantic_repair_limit_for_candidate(
    candidate: ProtocolSemanticRouteCandidate,
    grade: ProtocolSemanticTaskGrade,
) -> int | None:
    """Bound fallback latency without changing the ordered model route.

    GLM remains the complex-task primary and keeps the runner's full fair-repair
    budget. MTPLX gets one repair for genuinely short work, but a complex-task
    fallback is evaluated from one whole candidate and then yields to DeepSeek.
    DeepSeek gets one targeted repair before the route closes.
    """

    backend = candidate.backend.strip().lower()
    if backend == "mtplx":
        return 1 if grade == GRADE_SHORT else 0
    if backend == "deepseek":
        return 1
    return None


def summarize_run_result_for_route(
    result: Any,
) -> tuple[str, str | None, str | None]:
    """Map a runner result to route outcome / error_class / session_id."""

    session_id = getattr(result, "same_session_id", None)
    gate_result = getattr(result, "final_gate_result", None)
    gate_publishable = bool(
        gate_result is not None and getattr(gate_result, "publishable", False)
    )
    if (
        getattr(result, "status", None) == "可以进入审阅"
        and getattr(result, "final_draft", None) is not None
        and gate_publishable
    ):
        return "accepted", None, session_id
    attempts = list(getattr(result, "attempts", []) or [])
    if not attempts:
        return "empty_result", "EMPTY_RESULT", session_id
    last = attempts[-1]
    outcome = getattr(last, "outcome", "") or "需要核对"
    error_class = "RUN_NEEDS_REVIEW"
    if outcome == "会话异常":
        error_class = "SESSION_ANOMALY"
    elif outcome == "输出格式无效":
        error_class = "SCHEMA_INVALID"
    call_codes = {getattr(issue, "issue_code", "") for issue in getattr(last, "issues", [])}
    if "AGENT_CALL_QUOTA_EXHAUSTED" in call_codes:
        error_class = "QUOTA_EXHAUSTED"
    elif "AGENT_CALL_TRANSPORT_TIMEOUT" in call_codes:
        error_class = "TRANSPORT_TIMEOUT"
    elif "AGENT_CALL_FAILED" in call_codes:
        error_class = "SEMANTIC_CALL_FAILED"
    detail_parts: list[str] = []
    for issue in list(getattr(last, "issues", []) or [])[:3]:
        problem = " ".join(str(getattr(issue, "problem", "")).split())[:240]
        if problem:
            detail_parts.append(problem)
    # detail is recovered by callers from error_class/outcome; keep tuple lean.
    _ = "；".join(detail_parts) if detail_parts else outcome
    return "failed", error_class, session_id


def route_failure_detail(result: Any) -> str:
    attempts = list(getattr(result, "attempts", []) or [])
    if not attempts:
        return "模型路由尝试未返回可用结果"
    last = attempts[-1]
    detail_parts: list[str] = []
    for issue in list(getattr(last, "issues", []) or [])[:3]:
        problem = " ".join(str(getattr(issue, "problem", "")).split())[:240]
        if problem:
            detail_parts.append(problem)
    if detail_parts:
        return "；".join(detail_parts)
    return str(getattr(last, "outcome", "") or "需要核对")


def dumps_route_audit(audit: ProtocolSemanticRouteAudit) -> bytes:
    return json.dumps(
        audit.as_audit_dict(),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8")


def service_entry_semantic_route_snapshot() -> dict[str, Any]:
    """Describe the production default chain selected at service entry.

    Service entry uses this same selector: graded mode, no injected transport,
    whole-attempt isolation. The snapshot never includes credentials.
    """

    mode = resolve_route_mode()
    complex_candidates = select_protocol_semantic_route_candidates(
        GRADE_COMPLEX, route_mode=mode
    )
    short_candidates = select_protocol_semantic_route_candidates(
        GRADE_SHORT, route_mode=mode
    )
    return {
        "route_mode": mode,
        "complex_grade": GRADE_COMPLEX,
        "short_grade": GRADE_SHORT,
        "complex_identities": [item.identity for item in complex_candidates],
        "short_identities": [item.identity for item in short_candidates],
        "injected_transport_bypasses_grading": True,
    }


def assert_no_project_specific_hardcoding(source: str) -> None:
    """Deterministic helper for tests: reject study/protocol id literals.

    Tokens are assembled at runtime so this helper source itself does not
    contain the banned literals as contiguous substrings.
    """

    banned = (
        "d" + "001",
        "D" + "001",
        "package" + "75",
        "slice" + "61",
        "il-" + "17a",
        "IL-" + "17A",
    )
    for token in banned:
        if token in source:
            raise AssertionError(
                "protocol_semantic_model_router must stay project-agnostic; "
                f"found hardcoding token {token!r}"
            )


__all__ = [
    "GRADE_COMPLEX",
    "GRADE_SHORT",
    "ProtocolSemanticGradeDecision",
    "ProtocolSemanticRouteAttemptRecord",
    "ProtocolSemanticRouteAudit",
    "ProtocolSemanticRouteCandidate",
    "ProtocolSemanticRouteMode",
    "ProtocolSemanticTaskGrade",
    "assert_no_project_specific_hardcoding",
    "build_transport_for_candidate",
    "candidate_availability_error",
    "classify_protocol_semantic_task_grade",
    "dumps_route_audit",
    "resolve_route_mode",
    "route_failure_detail",
    "semantic_repair_limit_for_candidate",
    "select_protocol_semantic_route_candidates",
    "service_entry_semantic_route_snapshot",
    "summarize_run_result_for_route",
]
