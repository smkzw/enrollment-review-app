"""Deterministic regressions for graded protocol-semantic model routing.

Coverage (no live provider calls, no project-specific fixtures):
- default complex chain order
- short-task classification and MTPLX-first candidates
- explicit fallback / skip triggers with Chinese diagnostics
- provider-switch candidate isolation (discard + fresh transport)
- cache keys / identities do not reuse across models
- router/executor sources stay free of study/protocol hardcoding
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents import protocol_semantic_transport as transport_module
from app.agents import protocol_semantic_model_router as router
from app.agents.protocol_deconstructor import (
    ProtocolAgentCallError,
    _semantic_batch_cache_key,
)
from app.agents.protocol_semantic_model_router import (
    GRADE_COMPLEX,
    GRADE_SHORT,
    ProtocolSemanticGradeDecision,
    ProtocolSemanticRouteCandidate,
    assert_no_project_specific_hardcoding,
    candidate_availability_error,
    classify_protocol_semantic_task_grade,
    dumps_route_audit,
    resolve_route_mode,
    route_failure_detail,
    semantic_repair_limit_for_candidate,
    select_protocol_semantic_route_candidates,
    summarize_run_result_for_route,
)
from app.domain.contracts.agents import PromptVersion
from app.domain.contracts.enums import AgentNode
from app.protocols.deconstruction_gate import ProtocolGateIssue
from app.services import protocol_deconstruction_executor as executor_module
from app.services.protocol_deconstruction_executor import (
    ProtocolDeconstructionExecutorConfig,
    _ProtocolSemanticBatchFileCache,
    _run_semantic_generation_with_routing,
)
from app.workflow.runner import StepContext


ROOT = Path(__file__).resolve().parents[3]
ROUTER_SOURCE = ROOT / "app" / "agents" / "protocol_semantic_model_router.py"
EXECUTOR_SOURCE = ROOT / "app" / "services" / "protocol_deconstruction_executor.py"


def _prompt_version() -> PromptVersion:
    return PromptVersion(
        prompt_version_id="protocol-semantic-route-test",
        node=AgentNode.PROTOCOL_DECONSTRUCTOR,
        template_sha256="a" * 64,
        schema_version_id="protocol-semantic-route-test/v1",
    )


def _step_context(job_id: str = "job-route-test") -> StepContext:
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


def _accepted_result(session_id: str = "session-accepted") -> SimpleNamespace:
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


def _failed_result(
    *,
    session_id: str,
    outcome: str = "输出格式无效",
    problem: str = "模型输出结构无效，需显式切换下一候选",
) -> SimpleNamespace:
    return SimpleNamespace(
        status="需要核对",
        same_session_id=session_id,
        attempts=[
            SimpleNamespace(
                attempt=1,
                session_id=session_id,
                raw_output_sha256="c" * 64,
                outcome=outcome,
                issues=[
                    ProtocolGateIssue(
                        issue_code="SCHEMA_INVALID",
                        check_name="semantic_model_routing",
                        level="阻止发布",
                        problem=problem,
                        impact="当前候选不可接受",
                        next_action="切换下一模型候选并重新整次尝试",
                        affected_refs=["semantic_route"],
                        repair_scope=["semantic_route"],
                    )
                ],
            )
        ],
        final_draft=None,
        final_gate_result=SimpleNamespace(publishable=False),
    )


def test_default_complex_route_is_single_glm_high_candidate(monkeypatch):
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_COMPLEX", "")
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_PROVIDER", "zhipu-coding-plan")
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_MODEL", "glm-5.3-flash")
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_REASONING_EFFORT", "high")

    decision = classify_protocol_semantic_task_grade(
        parent_rule_count=3,
        prompt_text="复杂方案语义解构提示 " * 40,
        batch_total=3,
    )
    candidates = select_protocol_semantic_route_candidates(decision.grade)

    assert decision.grade == GRADE_COMPLEX
    # 默认复杂路由只有 GLM high：不存在隐式第三模型回退。
    assert [item.identity for item in candidates] == [
        "zhipu-coding-plan:glm-5.3-flash:high",
    ]


def test_invalid_glm_profile_is_not_silently_replaced(monkeypatch):
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_PROVIDER", "misspelled-provider")
    with pytest.raises(ValueError, match="不能静默替换"):
        router._default_glm_candidate()


def test_explicit_route_spec_keeps_ordered_fallback_chain(monkeypatch):
    """显式 DECONSTRUCT_ROUTE_COMPLEX 仍支持多候选整次尝试链。"""

    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(
        router,
        "DECONSTRUCT_ROUTE_COMPLEX",
        "zhipu-coding-plan:glm-5.3-flash:high,"
        "mtplx:mtplx-flash-next-optimized-speed:xhigh",
    )

    candidates = select_protocol_semantic_route_candidates(GRADE_COMPLEX)

    assert [item.identity for item in candidates] == [
        "zhipu-coding-plan:glm-5.3-flash:high",
        "mtplx:mtplx-flash-next-optimized-speed:xhigh",
    ]


def test_short_prompt_task_defaults_to_glm_high_without_third_model(monkeypatch):
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_SHORT", "")
    monkeypatch.setattr(router, "DECONSTRUCT_SHORT_PROMPT_MAX_INPUT_TOKENS", 4096)
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_MODEL", "glm-5.3-flash")
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_REASONING_EFFORT", "high")

    decision = classify_protocol_semantic_task_grade(
        parent_rule_count=1,
        prompt_text="短提示小任务",
        batch_total=1,
    )
    candidates = select_protocol_semantic_route_candidates(decision.grade)

    assert decision.grade == GRADE_SHORT
    assert "all_short_gates_passed" in decision.reasons
    # 默认短提示路由同样只选 GLM high，不隐式切换 MTPLX/DeepSeek。
    assert [item.identity for item in candidates] == [
        "zhipu-coding-plan:glm-5.3-flash:high",
    ]


def test_explicit_short_route_spec_keeps_mtplx_first_legacy_chain(monkeypatch):
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(
        router,
        "DECONSTRUCT_ROUTE_SHORT",
        "mtplx:mtplx-flash-next-optimized-speed:xhigh,"
        "deepseek:deepseek-v4-flash:high",
    )

    candidates = select_protocol_semantic_route_candidates(GRADE_SHORT)

    assert [item.identity for item in candidates] == [
        "mtplx:mtplx-flash-next-optimized-speed:xhigh",
        "deepseek:deepseek-v4-flash:high",
    ]


def test_route_repair_budgets_keep_primary_quality_and_bound_fallback_latency():
    glm = ProtocolSemanticRouteCandidate(
        "zhipu-coding-plan", "glm-5.3-flash", "high"
    )
    mtplx = ProtocolSemanticRouteCandidate(
        "mtplx", "mtplx-qwen38-27b-optimized-quality", "medium"
    )
    deepseek = ProtocolSemanticRouteCandidate(
        "deepseek", "deepseek-v4-flash", "high"
    )

    assert semantic_repair_limit_for_candidate(glm, GRADE_COMPLEX) is None
    assert semantic_repair_limit_for_candidate(mtplx, GRADE_COMPLEX) == 0
    assert semantic_repair_limit_for_candidate(mtplx, GRADE_SHORT) == 1
    assert semantic_repair_limit_for_candidate(deepseek, GRADE_COMPLEX) == 1


@pytest.mark.parametrize(
    ("parent_rule_count", "prompt_text", "batch_total", "expected_reason"),
    [
        (2, "短", 1, "parent_rule_count_gt_1"),
        (1, "x" * 20000, 1, "token_estimate_gt_short_limit"),
        (1, "短", 2, "batch_total_gt_1"),
    ],
)
def test_short_gates_fail_closed_to_complex(
    parent_rule_count: int,
    prompt_text: str,
    batch_total: int,
    expected_reason: str,
    monkeypatch,
):
    monkeypatch.setattr(router, "DECONSTRUCT_SHORT_PROMPT_MAX_INPUT_TOKENS", 64)
    decision = classify_protocol_semantic_task_grade(
        parent_rule_count=parent_rule_count,
        prompt_text=prompt_text,
        batch_total=batch_total,
        short_prompt_max_input_tokens=64,
    )
    assert decision.grade == GRADE_COMPLEX
    assert expected_reason in decision.reasons


def test_missing_glm_key_returns_explicit_chinese_skip_reason(monkeypatch):
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_API_KEY", "")
    candidate = ProtocolSemanticRouteCandidate(
        backend="zhipu-coding-plan",
        model="glm-5.3-flash",
        reasoning_effort="high",
    )
    detail = candidate_availability_error(candidate)
    assert detail is not None
    assert "DECONSTRUCT_GLM_API_KEY" in detail
    assert "显式跳过" in detail
    assert "GLM" in detail


def test_chinese_diagnostics_for_route_mode_and_failure_detail():
    with pytest.raises(ValueError, match="仅支持 graded/pinned"):
        resolve_route_mode("auto")

    failed = _failed_result(session_id="sess-zh", problem="输出格式无效，需继续回退")
    outcome, error_class, session_id = summarize_run_result_for_route(failed)
    assert outcome == "failed"
    assert error_class == "SCHEMA_INVALID"
    assert session_id == "sess-zh"
    assert "输出格式无效" in route_failure_detail(failed)


def test_non_publishable_draft_is_not_accepted_by_route():
    result = _accepted_result(session_id="session-gate-failed")
    result.status = "需要核对"
    result.final_gate_result = SimpleNamespace(publishable=False)

    outcome, error_class, session_id = summarize_run_result_for_route(result)

    assert outcome == "failed"
    assert error_class == "RUN_NEEDS_REVIEW"
    assert session_id == "session-gate-failed"


def test_graded_fallback_skips_unavailable_glm_then_accepts_next(
    monkeypatch, data_paths
):
    monkeypatch.setattr(executor_module, "DECONSTRUCT_ROUTE_MODE", "graded")
    decision = ProtocolSemanticGradeDecision(
        grade=GRADE_COMPLEX,
        parent_rule_count=4,
        token_estimate=1200,
        batch_total=2,
        short_prompt_max_input_tokens=4096,
        reasons=("parent_rule_count_gt_1", "batch_total_gt_1"),
    )
    candidates = [
        ProtocolSemanticRouteCandidate("zhipu-coding-plan", "glm-5.3-flash", "high"),
        ProtocolSemanticRouteCandidate(
            "mtplx", "mtplx-qwen38-27b-optimized-quality", "medium"
        ),
        ProtocolSemanticRouteCandidate("deepseek", "deepseek-v4-flash", "high"),
    ]
    monkeypatch.setattr(
        executor_module,
        "_grade_generate_task",
        lambda package, prompt_template: (decision, candidates),
    )
    monkeypatch.setattr(
        executor_module,
        "candidate_availability_error",
        lambda candidate: (
            "GLM 方案解构服务尚未配置（缺少 DECONSTRUCT_GLM_API_KEY）；"
            "已显式跳过该候选并继续尝试下一模型。"
            if candidate.backend.startswith("zhipu")
            else None
        ),
    )

    built: list[str] = []

    def _fake_build(candidate: ProtocolSemanticRouteCandidate):
        built.append(candidate.identity)
        return SimpleNamespace(
            _backend=candidate.backend,
            _model=candidate.model,
            _reasoning_effort=candidate.reasoning_effort,
        )

    monkeypatch.setattr(executor_module, "build_transport_for_candidate", _fake_build)

    run_backends: list[str] = []

    class _FakeRunner:
        def __init__(self, gate=None, max_semantic_repairs=None):
            self.gate = gate
            self.max_semantic_repairs = max_semantic_repairs

        def run(self, *args, **kwargs):
            transport = kwargs["transport"]
            run_backends.append(transport._backend)
            if transport._backend == "mtplx":
                return _accepted_result(session_id="session-mtplx")
            return _failed_result(session_id=f"session-{transport._backend}")

    monkeypatch.setattr(executor_module, "ProtocolDeconstructorRunner", _FakeRunner)

    config = ProtocolDeconstructionExecutorConfig(
        data_paths=data_paths, session_factory=object  # type: ignore[arg-type]
    )
    package = SimpleNamespace(source_input=object(), source_spans=())
    result, audit = _run_semantic_generation_with_routing(
        context=_step_context("job-fallback-1"),
        config=config,
        package=package,  # type: ignore[arg-type]
        prompt_version=_prompt_version(),
    )

    assert result.final_draft is not None
    assert built == ["mtplx:mtplx-qwen38-27b-optimized-quality:medium"]
    assert run_backends == ["mtplx"]
    assert audit["final_outcome"] == "accepted"
    assert audit["final_identity"] == "mtplx:mtplx-qwen38-27b-optimized-quality:medium"
    assert audit["attempts"][0]["outcome"] == "skipped_unavailable"
    assert audit["attempts"][0]["error_class"] == "PROVIDER_UNAVAILABLE"
    assert "显式跳过" in audit["attempts"][0]["detail"]
    assert audit["attempts"][1]["outcome"] == "accepted"
    audit_path = (
        data_paths.blobs_dir
        / "protocol-semantic-route-audits"
        / "job-fallback-1"
        / "route-audit.json"
    )
    assert audit_path.is_file()
    persisted = json.loads(audit_path.read_text(encoding="utf-8"))
    assert persisted["audit_contract"] == "protocol-semantic-route-audit/v1"
    assert persisted["final_identity"] == audit["final_identity"]


def test_provider_switch_discards_failed_candidate_and_uses_fresh_transport(
    monkeypatch, data_paths
):
    monkeypatch.setattr(executor_module, "DECONSTRUCT_ROUTE_MODE", "graded")
    decision = ProtocolSemanticGradeDecision(
        grade=GRADE_COMPLEX,
        parent_rule_count=5,
        token_estimate=2048,
        batch_total=3,
        short_prompt_max_input_tokens=4096,
        reasons=("parent_rule_count_gt_1", "batch_total_gt_1"),
    )
    candidates = [
        ProtocolSemanticRouteCandidate("zhipu-coding-plan", "glm-5.3-flash", "high"),
        ProtocolSemanticRouteCandidate(
            "mtplx", "mtplx-qwen38-27b-optimized-quality", "medium"
        ),
    ]
    monkeypatch.setattr(
        executor_module,
        "_grade_generate_task",
        lambda package, prompt_template: (decision, candidates),
    )
    monkeypatch.setattr(
        executor_module, "candidate_availability_error", lambda candidate: None
    )

    transport_ids: list[int] = []
    session_ids: list[str] = []

    def _fake_build(candidate: ProtocolSemanticRouteCandidate):
        transport = SimpleNamespace(
            _backend=candidate.backend,
            _model=candidate.model,
            _reasoning_effort=candidate.reasoning_effort,
            candidate_bucket={"merged": [f"partial-from-{candidate.backend}"]},
        )
        transport_ids.append(id(transport))
        return transport

    monkeypatch.setattr(executor_module, "build_transport_for_candidate", _fake_build)

    class _FakeRunner:
        def __init__(self, gate=None, max_semantic_repairs=None):
            self.gate = gate
            self.max_semantic_repairs = max_semantic_repairs

        def run(self, *args, **kwargs):
            transport = kwargs["transport"]
            # Simulate a provider-local merged candidate; must not leak to next.
            session_id = f"session-{transport._backend}-{id(transport)}"
            session_ids.append(session_id)
            if transport._backend == "zhipu-coding-plan":
                transport.candidate_bucket["merged"].append("glm-batch-1")
                raise ProtocolAgentCallError(
                    session_id, "GLM 整次尝试失败，需丢弃已合并候选"
                )
            # Next provider starts clean: only its own marker exists.
            assert transport.candidate_bucket["merged"] == [
                "partial-from-mtplx"
            ], "provider switch must not reuse prior merged candidate state"
            return _accepted_result(session_id=session_id)

    monkeypatch.setattr(executor_module, "ProtocolDeconstructorRunner", _FakeRunner)

    config = ProtocolDeconstructionExecutorConfig(
        data_paths=data_paths, session_factory=object  # type: ignore[arg-type]
    )
    result, audit = _run_semantic_generation_with_routing(
        context=_step_context("job-isolate-1"),
        config=config,
        package=SimpleNamespace(source_input=object(), source_spans=()),  # type: ignore[arg-type]
        prompt_version=_prompt_version(),
    )

    assert result.final_draft is not None
    assert len(transport_ids) == 2
    assert transport_ids[0] != transport_ids[1]
    assert session_ids[0] != session_ids[1]
    assert audit["attempts"][0]["outcome"] == "failed"
    assert audit["attempts"][0]["discarded_merged_candidate"] is True
    assert audit["attempts"][0]["error_class"] == "SEMANTIC_CALL_FAILED"
    assert audit["attempts"][1]["outcome"] == "accepted"
    assert audit["attempts"][1]["discarded_merged_candidate"] is False
    assert audit["final_identity"].startswith("mtplx:")


def test_route_continues_after_non_publishable_draft(monkeypatch, data_paths):
    monkeypatch.setattr(executor_module, "DECONSTRUCT_ROUTE_MODE", "graded")
    decision = ProtocolSemanticGradeDecision(
        grade=GRADE_COMPLEX,
        parent_rule_count=2,
        token_estimate=1200,
        batch_total=2,
        short_prompt_max_input_tokens=4096,
        reasons=("parent_rule_count_gt_1",),
    )
    candidates = [
        ProtocolSemanticRouteCandidate("zhipu-coding-plan", "glm-5.3-flash", "high"),
        ProtocolSemanticRouteCandidate("deepseek", "deepseek-v4-flash", "high"),
    ]
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
        ),
    )

    class _FakeRunner:
        def __init__(self, gate=None, max_semantic_repairs=None):
            self.gate = gate
            self.max_semantic_repairs = max_semantic_repairs

        def run(self, *args, **kwargs):
            transport = kwargs["transport"]
            result = _accepted_result(session_id=f"session-{transport._backend}")
            if transport._backend.startswith("zhipu"):
                result.status = "需要核对"
                result.final_gate_result = SimpleNamespace(publishable=False)
            return result

    monkeypatch.setattr(executor_module, "ProtocolDeconstructorRunner", _FakeRunner)

    result, audit = _run_semantic_generation_with_routing(
        context=_step_context("job-non-publishable-fallback"),
        config=ProtocolDeconstructionExecutorConfig(
            data_paths=data_paths, session_factory=object  # type: ignore[arg-type]
        ),
        package=SimpleNamespace(source_input=object(), source_spans=()),  # type: ignore[arg-type]
        prompt_version=_prompt_version(),
    )

    assert result.final_gate_result.publishable is True
    assert [item["outcome"] for item in audit["attempts"]] == [
        "failed",
        "accepted",
    ]
    assert audit["attempts"][0]["discarded_merged_candidate"] is True
    assert audit["attempts"][0]["semantic_repair_limit"] is None
    assert audit["attempts"][1]["semantic_repair_limit"] == 1
    assert audit["final_identity"] == "deepseek:deepseek-v4-flash:high"


def test_semantic_cache_identity_and_batch_keys_do_not_reuse_across_models():
    glm = transport_module.DeepSeekProtocolAgentTransport(
        client=object(),
        backend="zhipu-coding-plan",
        model="glm-5.3-flash",
        reasoning_effort="high",
        api_key="test-glm-key",
    )
    mtplx = transport_module.DeepSeekProtocolAgentTransport(
        client=object(),
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        reasoning_effort="medium",
    )
    deepseek = transport_module.DeepSeekProtocolAgentTransport(
        client=object(),
        backend="deepseek",
        model="deepseek-v4-flash",
        reasoning_effort="high",
        api_key="test-deepseek-key",
    )

    identities = {
        "glm": glm.semantic_cache_identity(output_kind="semantic_candidate"),
        "mtplx": mtplx.semantic_cache_identity(output_kind="semantic_candidate"),
        "deepseek": deepseek.semantic_cache_identity(output_kind="semantic_candidate"),
    }
    assert len(set(identities.values())) == 3

    prompt = "同一提示不得跨模型复用缓存"
    batch_id = "batch-1"
    rule_codes = ["R1"]
    keys = {
        name: _semantic_batch_cache_key(
            transport,
            prompt=prompt,
            batch_id=batch_id,
            rule_codes=rule_codes,
        )
        for name, transport in {
            "glm": glm,
            "mtplx": mtplx,
            "deepseek": deepseek,
        }.items()
    }
    assert None not in keys.values()
    assert len(set(keys.values())) == 3


def test_batch_file_cache_is_key_isolated_across_model_identities(data_paths):
    cache = _ProtocolSemanticBatchFileCache(data_paths, "job-cache-iso")
    key_a = hashlib.sha256(b"model-a-identity").hexdigest()
    key_b = hashlib.sha256(b"model-b-identity").hexdigest()
    assert key_a != key_b

    cache.store(key_a, '{"candidate_id":"from-model-a"}')
    assert cache.load(key_a) == '{"candidate_id":"from-model-a"}'
    assert cache.load(key_b) is None


def test_batch_file_cache_records_parent_segment_contract(data_paths):
    cache = _ProtocolSemanticBatchFileCache(data_paths, "job-segment-contract")
    key = hashlib.sha256(b"one-parent-segment").hexdigest()
    response_text = '{"candidate_id":"segment-result"}'

    cache.store(
        key,
        response_text,
        cache_contract="protocol-semantic-parent-segment/v1",
    )

    payload = json.loads(cache._path(key).read_text(encoding="utf-8"))
    assert payload["cache_contract"] == "protocol-semantic-parent-segment/v1"
    assert cache.load(key) == response_text


def test_pinned_mode_returns_single_deconstruct_pin(monkeypatch):
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "pinned")
    monkeypatch.setattr(router, "DECONSTRUCT_BACKEND", "mtplx")
    monkeypatch.setattr(router, "DECONSTRUCT_MODEL", "mtplx-qwen38-27b-optimized-quality")
    monkeypatch.setattr(router, "DECONSTRUCT_REASONING_EFFORT", "medium")

    candidates = select_protocol_semantic_route_candidates(
        GRADE_COMPLEX, route_mode="pinned"
    )
    assert len(candidates) == 1
    assert candidates[0].identity == (
        "mtplx:mtplx-qwen38-27b-optimized-quality:medium"
    )


def test_route_audit_dump_is_stable_json_bytes():
    decision = ProtocolSemanticGradeDecision(
        grade=GRADE_SHORT,
        parent_rule_count=1,
        token_estimate=12,
        batch_total=1,
        short_prompt_max_input_tokens=4096,
        reasons=("all_short_gates_passed",),
    )
    audit = router.ProtocolSemanticRouteAudit(
        job_id="job-audit",
        route_mode="graded",
        grade_decision=decision,
        ordered_candidates=[
            ProtocolSemanticRouteCandidate(
                "mtplx", "mtplx-qwen38-27b-optimized-quality", "medium"
            )
        ],
        final_identity="mtplx:mtplx-qwen38-27b-optimized-quality:medium",
        final_outcome="accepted",
    )
    payload = json.loads(dumps_route_audit(audit).decode("utf-8"))
    assert payload["audit_contract"] == "protocol-semantic-route-audit/v1"
    assert payload["grade_decision"]["grade"] == GRADE_SHORT
    assert payload["final_outcome"] == "accepted"


def test_router_and_executor_sources_have_no_project_specific_hardcoding():
    assert_no_project_specific_hardcoding(ROUTER_SOURCE.read_text(encoding="utf-8"))
    assert_no_project_specific_hardcoding(EXECUTOR_SOURCE.read_text(encoding="utf-8"))

    # Classifier/route selection APIs must remain count/token based only.
    source = ROUTER_SOURCE.read_text(encoding="utf-8")
    assert "parent_rule_count" in source
    assert "token_estimate" in source
    assert "batch_total" in source
