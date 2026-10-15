"""Independent adversarial coverage for Phase 5 graded runtime routing.

These cases do not call live providers and do not restore any prior job.
They attack the single-GLM default route, whole-attempt fallback isolation
on explicitly declared multi-candidate chains, explicit short-route specs,
and project-specific hardcoding in the shared routing and fresh-run identity
sources.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents import protocol_semantic_model_router as router
from app.agents.protocol_deconstructor import ProtocolAgentCallError
from app.agents.protocol_semantic_model_router import (
    GRADE_COMPLEX,
    GRADE_SHORT,
    ProtocolSemanticGradeDecision,
    ProtocolSemanticRouteCandidate,
    classify_protocol_semantic_task_grade,
    semantic_repair_limit_for_candidate,
    select_protocol_semantic_route_candidates,
)
from app.domain.contracts.agents import PromptVersion
from app.domain.contracts.enums import AgentNode
from app.protocols.deconstruction_gate import ProtocolGateIssue
from app.services import protocol_deconstruction_executor as executor_module
from app.services.protocol_deconstruction_executor import (
    ProtocolDeconstructionExecutorConfig,
    _run_semantic_generation_with_routing,
)
from app.workflow.runner import StepContext

ROOT = Path(__file__).resolve().parents[3]

_PRODUCTION_SOURCES = (
    ROOT / "app" / "agents" / "protocol_semantic_model_router.py",
    ROOT / "app" / "services" / "protocol_deconstruction_executor.py",
    ROOT / "app" / "config.py",
    ROOT / "tools" / "phase5_acceptance" / "fresh_runtime.py",
    ROOT / "tools" / "phase5_acceptance" / "input_manifest.py",
    ROOT / "tools" / "phase5_acceptance" / "run_packet.py",
)

# Assembled so a naive copy of this list into production still needs joining.
_BANNED_PRODUCTION_TOKENS = (
    "D" + "001",
    "SA" + "R",
    "31" + "001",
    "SA" + "01025",
    "MG-" + "K10",
    "IL-" + "17",
    "EX-" + "06",
    "IN-" + "01",
    "package" + "20",
    "第" + "20包",
    "阿帕" + "替尼",
    "卡瑞" + "利珠",
    "Nivo" + "lumab",
    "Pembro" + "lizumab",
    "重症肌" + "无力",
    "银屑" + "病",
    "FEV" + "1",
    "EC" + "OG",
    "RECI" + "ST",
)


def _prompt_version() -> PromptVersion:
    return PromptVersion(
        prompt_version_id="fresh-subject-route-adv",
        node=AgentNode.PROTOCOL_DECONSTRUCTOR,
        template_sha256="a" * 64,
        schema_version_id="fresh-subject-route-adv/v1",
    )


def _step_context(job_id: str) -> StepContext:
    return StepContext(
        job_id=job_id,
        job_type="protocol_deconstruction",
        job_payload={},
        step_id="generate",
        name="generate",
        attempt=1,
        last_checkpoint_id=None,
        last_checkpoint=None,
        max_attempts=3,
    )


def _accepted_result(session_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        status="可以进入审阅",
        same_session_id=session_id,
        attempts=[
            SimpleNamespace(
                attempt=1,
                session_id=session_id,
                raw_output_sha256="b" * 64,
                outcome="通过完整性检查",
                issues=[],
            )
        ],
        final_draft=SimpleNamespace(candidate_id=f"cand-{session_id}"),
        final_gate_result=SimpleNamespace(publishable=True),
    )


def _failed_result(session_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        status="需要核对",
        same_session_id=session_id,
        attempts=[
            SimpleNamespace(
                attempt=1,
                session_id=session_id,
                raw_output_sha256="c" * 64,
                outcome="输出格式无效",
                issues=[
                    ProtocolGateIssue(
                        issue_code="SCHEMA_INVALID",
                        check_name="fresh_subject_runtime_routing",
                        level="阻止发布",
                        problem="整次尝试失败，必须丢弃后换供应商",
                        impact="当前候选不可接受",
                        next_action="切换下一模型候选并重新整次尝试",
                        affected_refs=["semantic_route"],
                        repair_scope=["semantic_route"],
                    )
                ],
            )
        ],
        final_draft=SimpleNamespace(candidate_id=f"draft-{session_id}"),
        final_gate_result=SimpleNamespace(publishable=False),
    )


def _patch_graded_defaults(monkeypatch) -> None:
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_COMPLEX", "")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_SHORT", "")
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_PROVIDER", "zhipu-coding-plan")
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_MODEL", "glm-5.3-flash")
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_REASONING_EFFORT", "high")
    monkeypatch.setattr(executor_module, "DECONSTRUCT_ROUTE_MODE", "graded")


def _complex_candidates() -> list[ProtocolSemanticRouteCandidate]:
    return select_protocol_semantic_route_candidates(GRADE_COMPLEX)


# 显式声明的多候选链（等价于显式路由规格）：默认链不再自动包含第三模型，
# 但整次尝试隔离、修复预算与审计语义必须继续覆盖显式多候选场景。
def _declared_complex_candidates() -> list[ProtocolSemanticRouteCandidate]:
    return [
        ProtocolSemanticRouteCandidate(
            "zhipu-coding-plan", "glm-5.3-flash", "high"
        ),
        ProtocolSemanticRouteCandidate(
            "mtplx", "mtplx-qwen38-27b-optimized-quality", "medium"
        ),
        ProtocolSemanticRouteCandidate("deepseek", "deepseek-v4-flash", "high"),
    ]


def _declared_short_candidates() -> list[ProtocolSemanticRouteCandidate]:
    return [
        ProtocolSemanticRouteCandidate(
            "mtplx", "mtplx-qwen38-27b-optimized-quality", "medium"
        ),
        ProtocolSemanticRouteCandidate("deepseek", "deepseek-v4-flash", "high"),
    ]


def _run_routed(
    monkeypatch,
    data_paths,
    *,
    job_id: str,
    decision: ProtocolSemanticGradeDecision,
    candidates: list[ProtocolSemanticRouteCandidate],
    runner_factory,
):
    monkeypatch.setattr(
        executor_module,
        "_grade_generate_task",
        lambda package, prompt_template: (decision, candidates),
    )
    monkeypatch.setattr(
        executor_module, "candidate_availability_error", lambda candidate: None
    )
    monkeypatch.setattr(
        executor_module,
        "build_transport_for_candidate",
        lambda candidate: SimpleNamespace(
            _backend=candidate.backend,
            _model=candidate.model,
            _reasoning_effort=candidate.reasoning_effort,
            candidate_bucket={"merged": [f"partial-from-{candidate.backend}"]},
        ),
    )
    monkeypatch.setattr(executor_module, "ProtocolDeconstructorRunner", runner_factory)
    return _run_semantic_generation_with_routing(
        context=_step_context(job_id),
        config=ProtocolDeconstructionExecutorConfig(
            data_paths=data_paths, session_factory=object  # type: ignore[arg-type]
        ),
        package=SimpleNamespace(source_input=object(), source_spans=()),  # type: ignore[arg-type]
        prompt_version=_prompt_version(),
    )


def test_complex_default_chain_is_single_glm_high_candidate(
    monkeypatch,
):
    _patch_graded_defaults(monkeypatch)
    decision = classify_protocol_semantic_task_grade(
        parent_rule_count=4,
        prompt_text="复杂方案语义解构 " * 80,
        batch_total=3,
    )
    identities = [item.identity for item in _complex_candidates()]
    assert decision.grade == GRADE_COMPLEX
    # 默认复杂路由只声明 GLM high：无隐式 MTPLX/DeepSeek 第三模型回退。
    assert identities == ["zhipu-coding-plan:glm-5.3-flash:high"]


def test_short_prompt_default_chain_is_same_single_glm_candidate(
    monkeypatch,
):
    _patch_graded_defaults(monkeypatch)
    decision = classify_protocol_semantic_task_grade(
        parent_rule_count=1,
        prompt_text="短提示",
        batch_total=1,
        short_prompt_max_input_tokens=4096,
    )
    candidates = select_protocol_semantic_route_candidates(decision.grade)
    assert decision.grade == GRADE_SHORT
    assert [item.identity for item in candidates] == [
        "zhipu-coding-plan:glm-5.3-flash:high",
    ]


def test_complex_exhausted_fallback_keeps_whole_attempt_isolation(
    monkeypatch, data_paths
):
    _patch_graded_defaults(monkeypatch)
    decision = ProtocolSemanticGradeDecision(
        grade=GRADE_COMPLEX,
        parent_rule_count=6,
        token_estimate=2400,
        batch_total=3,
        short_prompt_max_input_tokens=4096,
        reasons=("parent_rule_count_gt_1", "batch_total_gt_1"),
    )
    candidates = _declared_complex_candidates()
    transport_ids: list[int] = []
    session_ids: list[str] = []
    merged_seen: list[list[str]] = []

    def _build(candidate: ProtocolSemanticRouteCandidate):
        transport = SimpleNamespace(
            _backend=candidate.backend,
            _model=candidate.model,
            _reasoning_effort=candidate.reasoning_effort,
            candidate_bucket={"merged": [f"partial-from-{candidate.backend}"]},
        )
        transport_ids.append(id(transport))
        return transport

    monkeypatch.setattr(executor_module, "build_transport_for_candidate", _build)
    monkeypatch.setattr(
        executor_module,
        "_grade_generate_task",
        lambda package, prompt_template: (decision, candidates),
    )
    monkeypatch.setattr(
        executor_module, "candidate_availability_error", lambda candidate: None
    )

    class _FailAll:
        def __init__(self, gate=None, max_semantic_repairs=None):
            self.max_semantic_repairs = max_semantic_repairs

        def run(self, *args, **kwargs):
            transport = kwargs["transport"]
            merged_seen.append(list(transport.candidate_bucket["merged"]))
            session_id = f"session-{transport._backend}-{id(transport)}"
            session_ids.append(session_id)
            if transport._backend == "deepseek":
                raise ProtocolAgentCallError(session_id, "DeepSeek 整次尝试失败")
            result = _failed_result(session_id)
            transport.candidate_bucket["merged"].append(f"leak-{transport._backend}")
            return result

    monkeypatch.setattr(executor_module, "ProtocolDeconstructorRunner", _FailAll)
    _result, audit = _run_semantic_generation_with_routing(
        context=_step_context("job-adv-exhausted"),
        config=ProtocolDeconstructionExecutorConfig(
            data_paths=data_paths, session_factory=object  # type: ignore[arg-type]
        ),
        package=SimpleNamespace(source_input=object(), source_spans=()),  # type: ignore[arg-type]
        prompt_version=_prompt_version(),
    )

    assert [item["backend"] for item in audit["attempts"]] == [
        "zhipu-coding-plan",
        "mtplx",
        "deepseek",
    ]
    assert [item["outcome"] for item in audit["attempts"]] == [
        "failed",
        "failed",
        "failed",
    ]
    assert all(item["discarded_merged_candidate"] is True for item in audit["attempts"])
    assert audit["final_outcome"] == "exhausted"
    assert audit["final_identity"] is None
    assert len(set(transport_ids)) == 3
    assert len(set(session_ids)) == 3
    assert merged_seen == [
        ["partial-from-zhipu-coding-plan"],
        ["partial-from-mtplx"],
        ["partial-from-deepseek"],
    ]
    assert audit["attempts"][0]["semantic_repair_limit"] is None
    assert audit["attempts"][1]["semantic_repair_limit"] == 0
    assert audit["attempts"][2]["semantic_repair_limit"] == 1
    persisted = json.loads(
        (
            data_paths.blobs_dir
            / "protocol-semantic-route-audits"
            / "job-adv-exhausted"
            / "route-audit.json"
        ).read_text(encoding="utf-8")
    )
    assert persisted["audit_contract"] == "protocol-semantic-route-audit/v1"
    assert persisted["attempts"][0]["backend"] == "zhipu-coding-plan"


def test_complex_glm_failure_falls_back_to_mtplx_then_deepseek_accepts(
    monkeypatch, data_paths
):
    _patch_graded_defaults(monkeypatch)
    decision = ProtocolSemanticGradeDecision(
        grade=GRADE_COMPLEX,
        parent_rule_count=3,
        token_estimate=1800,
        batch_total=2,
        short_prompt_max_input_tokens=4096,
        reasons=("parent_rule_count_gt_1", "batch_total_gt_1"),
    )
    # 显式声明的多候选链仍然支持整次尝试顺序回退。
    candidates = _declared_complex_candidates()

    class _GlmThenMtplxFail:
        def __init__(self, gate=None, max_semantic_repairs=None):
            self.max_semantic_repairs = max_semantic_repairs

        def run(self, *args, **kwargs):
            transport = kwargs["transport"]
            session_id = f"session-{transport._backend}"
            if transport._backend == "deepseek":
                return _accepted_result(session_id)
            return _failed_result(session_id)

    _result, audit = _run_routed(
        monkeypatch,
        data_paths,
        job_id="job-adv-glm-mtplx-fail",
        decision=decision,
        candidates=candidates,
        runner_factory=_GlmThenMtplxFail,
    )
    assert [item["outcome"] for item in audit["attempts"]] == [
        "failed",
        "failed",
        "accepted",
    ]
    assert audit["final_identity"] == "deepseek:deepseek-v4-flash:high"
    assert audit["attempts"][0]["discarded_merged_candidate"] is True
    assert audit["attempts"][1]["discarded_merged_candidate"] is True
    assert audit["attempts"][2]["discarded_merged_candidate"] is False


def test_short_task_mtplx_failure_falls_back_to_deepseek_without_glm(
    monkeypatch, data_paths
):
    _patch_graded_defaults(monkeypatch)
    decision = ProtocolSemanticGradeDecision(
        grade=GRADE_SHORT,
        parent_rule_count=1,
        token_estimate=12,
        batch_total=1,
        short_prompt_max_input_tokens=4096,
        reasons=("all_short_gates_passed",),
    )
    # 显式声明短提示链（等价于 DECONSTRUCT_ROUTE_SHORT 覆盖）。
    candidates = _declared_short_candidates()

    class _ShortFallback:
        def __init__(self, gate=None, max_semantic_repairs=None):
            self.max_semantic_repairs = max_semantic_repairs

        def run(self, *args, **kwargs):
            transport = kwargs["transport"]
            if transport._backend == "mtplx":
                return _failed_result("session-mtplx-short")
            return _accepted_result("session-deepseek-short")

    _result, audit = _run_routed(
        monkeypatch,
        data_paths,
        job_id="job-adv-short-fallback",
        decision=decision,
        candidates=candidates,
        runner_factory=_ShortFallback,
    )
    backends = [item["backend"] for item in audit["attempts"]]
    assert backends == ["mtplx", "deepseek"]
    assert "zhipu-coding-plan" not in backends
    assert audit["final_identity"] == "deepseek:deepseek-v4-flash:high"
    assert audit["attempts"][0]["semantic_repair_limit"] == 1
    assert audit["attempts"][1]["semantic_repair_limit"] == 1


def test_repair_budget_keeps_glm_unlimited_and_bounds_fallbacks(monkeypatch):
    _patch_graded_defaults(monkeypatch)
    glm, mtplx, deepseek = _declared_complex_candidates()
    assert semantic_repair_limit_for_candidate(glm, GRADE_COMPLEX) is None
    assert semantic_repair_limit_for_candidate(mtplx, GRADE_COMPLEX) == 0
    assert semantic_repair_limit_for_candidate(deepseek, GRADE_COMPLEX) == 1
    short_mtplx, short_deepseek = _declared_short_candidates()
    assert semantic_repair_limit_for_candidate(short_mtplx, GRADE_SHORT) == 1
    assert semantic_repair_limit_for_candidate(short_deepseek, GRADE_SHORT) == 1


def test_production_routing_and_identity_sources_have_no_project_literals():
    for path in _PRODUCTION_SOURCES:
        text = path.read_text(encoding="utf-8")
        for token in _BANNED_PRODUCTION_TOKENS:
            assert token not in text, f"{path} contains banned token {token!r}"
        assert "parent_rule_count" in path.read_text(encoding="utf-8") or path.name != (
            "protocol_semantic_model_router.py"
        )


def test_fresh_runtime_module_stays_study_agnostic():
    source = (ROOT / "tools" / "phase5_acceptance" / "fresh_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "failed_final" in source
    assert "job_id" in source
    assert "model_configs" in source
    for token in _BANNED_PRODUCTION_TOKENS:
        assert token not in source


def test_live_unpatched_defaults_pin_single_glm_high_identity():
    """Attack live module defaults, not only monkeypatched constants."""

    # 当前生产默认：pinned 单一 GLM high 身份，两个级别都解析到同一候选，
    # 没有隐式第三模型。
    assert router.DECONSTRUCT_ROUTE_MODE == "pinned"
    expected = (
        f"{router.DECONSTRUCT_BACKEND}:{router.DECONSTRUCT_MODEL}:"
        f"{router.DECONSTRUCT_REASONING_EFFORT}"
    )
    complex_ids = [
        item.identity for item in select_protocol_semantic_route_candidates(GRADE_COMPLEX)
    ]
    short_ids = [
        item.identity for item in select_protocol_semantic_route_candidates(GRADE_SHORT)
    ]
    assert complex_ids == [expected]
    assert short_ids == [expected]
    assert expected == "zhipu-coding-plan:glm-5.3-flash:high"
