"""Focused service-entry regressions for graded protocol-semantic routing.

These tests lock the production generate path, default config, and run-audit
loader so complex/short grading and whole-attempt isolation actually take
effect at the V2 service entry. No live provider calls. No project-specific
fixtures or study/protocol/disease/drug literals.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import hashlib
import json

import pytest

from app.agents.protocol_deconstructor import ProtocolAgentCallError
from app.agents.protocol_semantic_model_router import (
    GRADE_SHORT,
    ProtocolSemanticRouteAudit,
    ProtocolSemanticRouteAttemptRecord,
    ProtocolSemanticRouteCandidate,
    ProtocolSemanticGradeDecision,
    assert_no_project_specific_hardcoding,
    dumps_route_audit,
    service_entry_semantic_route_snapshot,
)
from app.services import protocol_deconstruction_executor as executor_module
from app.services.protocol_deconstruction_executor import (
    ProtocolDeconstructionExecutorConfig,
    load_persisted_route_audit,
)
from app.services.protocol_workbench_service import ProtocolWorkbenchService


ROOT = Path(__file__).resolve().parents[3]
ROUTER_SOURCE = ROOT / "app" / "agents" / "protocol_semantic_model_router.py"
EXECUTOR_SOURCE = ROOT / "app" / "services" / "protocol_deconstruction_executor.py"
WORKBENCH_SOURCE = ROOT / "app" / "services" / "protocol_workbench_service.py"
APP_SOURCE = ROOT / "app" / "api" / "v2" / "app.py"
ENV_EXAMPLE = ROOT / ".env.example"
LAUNCHER = ROOT / "scripts" / "start_enrollment_review.command"
SERVICE_SCRIPT = ROOT / "scripts" / "run_enrollment_review_service.sh"


def test_service_entry_snapshot_uses_single_glm_high_default_chain(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.agents.protocol_semantic_model_router.DECONSTRUCT_ROUTE_MODE",
        "graded",
    )
    monkeypatch.setattr(
        "app.agents.protocol_semantic_model_router.DECONSTRUCT_ROUTE_COMPLEX",
        "",
    )
    monkeypatch.setattr(
        "app.agents.protocol_semantic_model_router.DECONSTRUCT_ROUTE_SHORT",
        "",
    )
    monkeypatch.setattr(
        "app.agents.protocol_semantic_model_router.DECONSTRUCT_GLM_MODEL",
        "glm-5.3-flash",
    )
    monkeypatch.setattr(
        "app.agents.protocol_semantic_model_router.DECONSTRUCT_GLM_REASONING_EFFORT",
        "high",
    )
    snapshot = service_entry_semantic_route_snapshot()
    assert snapshot["route_mode"] == "graded"
    # 默认链只声明当前配置的 GLM high，无隐式第三模型回退。
    assert snapshot["complex_identities"] == [
        "cms-router:glm-5.3-flash:high",
    ]
    assert snapshot["short_identities"] == [
        "cms-router:glm-5.3-flash:high",
    ]
    assert snapshot["injected_transport_bypasses_grading"] is True


def test_production_executor_config_does_not_inject_transport():
    config = ProtocolDeconstructionExecutorConfig(
        data_paths=SimpleNamespace(),  # type: ignore[arg-type]
        session_factory=SimpleNamespace(),  # type: ignore[arg-type]
    )
    assert config.transport is None
    assert config.transport_factory is None
    source = APP_SOURCE.read_text(encoding="utf-8")
    marker = "default_executors = {"
    block = source.split(marker, 1)[1].split("EVIDENCE_PROCESSING_JOB_TYPE", 1)[0]
    assert "create_protocol_deconstruction_executor(" in block
    assert "ProtocolDeconstructionExecutorConfig(" in block
    assert "data_paths=paths" in block
    assert "session_factory=session_factory" in block
    assert "transport=" not in block
    assert "transport_factory=" not in block


def test_load_persisted_route_audit_is_job_scoped(data_paths):
    config = ProtocolDeconstructionExecutorConfig(
        data_paths=data_paths,
        session_factory=SimpleNamespace(),  # type: ignore[arg-type]
    )
    job_a = "job-audit-a"
    job_b = "job-audit-b"
    audit = ProtocolSemanticRouteAudit(
        job_id=job_a,
        route_mode="graded",
        grade_decision=ProtocolSemanticGradeDecision(
            grade="complex_protocol_semantic",
            parent_rule_count=4,
            token_estimate=9000,
            batch_total=4,
            short_prompt_max_input_tokens=4096,
            reasons=("parent_rule_count_gt_1",),
        ),
        ordered_candidates=[
            ProtocolSemanticRouteCandidate(
                backend="zhipu-coding-plan",
                model="glm-5.3-flash",
                reasoning_effort="high",
            )
        ],
        final_identity="zhipu-coding-plan:glm-5.3-flash:high",
        final_outcome="accepted",
    )
    target = (
        data_paths.blobs_dir
        / "protocol-semantic-route-audits"
        / job_a
        / "route-audit.json"
    )
    data_paths.boundary.atomic_write_bytes(target, dumps_route_audit(audit))

    loaded = load_persisted_route_audit(config, job_a)
    assert loaded is not None
    assert loaded["job_id"] == job_a
    assert loaded["final_identity"] == "zhipu-coding-plan:glm-5.3-flash:high"
    assert load_persisted_route_audit(config, job_b) is None


def test_feedback_revision_uses_short_route_and_fresh_transport(monkeypatch):
    calls: list[str] = []
    candidates = [
        ProtocolSemanticRouteCandidate(
            backend="mtplx",
            model="mtplx-qwen38-27b-optimized-quality",
            reasoning_effort="medium",
        ),
        ProtocolSemanticRouteCandidate(
            backend="deepseek",
            model="deepseek-v4-flash",
            reasoning_effort="high",
        ),
    ]

    import app.agents.protocol_semantic_model_router as router_mod
    import app.agents.protocol_deconstructor as deconstructor

    monkeypatch.setattr(
        router_mod,
        "select_protocol_semantic_route_candidates",
        lambda grade, route_mode=None: candidates,
    )
    monkeypatch.setattr(router_mod, "resolve_route_mode", lambda raw=None: "graded")
    monkeypatch.setattr(
        router_mod, "candidate_availability_error", lambda candidate: None
    )

    def _build(candidate):
        calls.append(f"build:{candidate.identity}")
        return SimpleNamespace(identity=candidate.identity)

    def _revise(source_input, current_draft, **kwargs):
        transport = kwargs["transport"]
        calls.append(f"revise:{transport.identity}")
        if transport.identity.startswith("mtplx:"):
            raise ProtocolAgentCallError("session-mtplx-fail", "短提示候选失败")
        return SimpleNamespace(draft_id="revised")

    monkeypatch.setattr(router_mod, "build_transport_for_candidate", _build)
    monkeypatch.setattr(deconstructor, "revise_protocol_draft_from_feedback", _revise)

    result = ProtocolWorkbenchService._revise_feedback_with_model(
        SimpleNamespace(),
        SimpleNamespace(),
        target_rule_code="RULE-1",
        feedback_note="请按原文修正该父规则",
    )
    assert result.draft_id == "revised"
    assert calls == [
        "build:mtplx:mtplx-qwen38-27b-optimized-quality:medium",
        "revise:mtplx:mtplx-qwen38-27b-optimized-quality:medium",
        "build:deepseek:deepseek-v4-flash:high",
        "revise:deepseek:deepseek-v4-flash:high",
    ]


def test_feedback_provider_and_outer_retry_share_saved_allowance(monkeypatch):
    from app.agents import protocol_deconstructor as author
    from app.agents import protocol_semantic_model_router as router
    from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport
    from app.llm.logical_call_budget import LogicalCallBudget

    source = SimpleNamespace(protocol_file_sha256="a" * 64, extraction_snapshot_id="frozen-input")
    run_id = hashlib.sha256(json.dumps({
        "source": source.protocol_file_sha256, "snapshot": source.extraction_snapshot_id,
        "role": "official-run-budget/v1",
    }, sort_keys=True).encode()).hexdigest()
    saved = {}
    store = SimpleNamespace(
        load_call_budget=lambda key: saved.get(key),
        store_call_budget=lambda value: saved.__setitem__(value["logical_task_id"], value),
    )
    parent = LogicalCallBudget("existing-parent", max_requests=3, max_output_tokens=32768,
                              persist=store.store_call_budget)
    parent.reserve(request_sha256="old-parent-read", max_tokens=8192)
    run = LogicalCallBudget(run_id, max_requests=4, max_output_tokens=32768,
                           contract_sha256="old-contract", persist=store.store_call_budget)
    run.reserve(request_sha256="old-run-read", max_tokens=8192)
    candidates = [ProtocolSemanticRouteCandidate(backend="cms-router", model=f"model-{i}", reasoning_effort="high")
                  for i in range(2)]
    built, closed = [], []

    def build(candidate):
        built.append(candidate.model)
        client = SimpleNamespace(close=lambda: closed.append(candidate.model))
        return DeepSeekProtocolAgentTransport(client=client, backend="cms-router", model=candidate.model,
                                             max_tokens=8192, reasoning_effort="high")

    def revise(_source, _draft, **kwargs):
        transport = kwargs["transport"]
        assert kwargs["preserve_review_items"] is True
        transport.configure_logical_task(logical_task_id="existing-parent", max_requests=3)
        transport._reserve_completion({"model": transport._model, "max_tokens": 8192})
        if transport._model == "model-0":
            raise ProtocolAgentCallError("failed-first", "模型返回不可读取答案")
        return SimpleNamespace(draft_id="saved-scope-candidate")

    monkeypatch.setattr(router, "select_protocol_semantic_route_candidates", lambda *a, **kw: candidates)
    monkeypatch.setattr(router, "candidate_availability_error", lambda candidate: None)
    monkeypatch.setattr(router, "build_transport_for_candidate", build)
    monkeypatch.setattr(author, "revise_protocol_draft_from_feedback", revise)
    assert ProtocolWorkbenchService._revise_feedback_with_model(
        source, SimpleNamespace(), "EX-01", "只改指定描述", preserve_review_items=True, budget_store=store,
    ).draft_id == "saved-scope-candidate"
    assert saved[run_id]["requests_used"] == 3
    assert saved["existing-parent"]["requests_used"] == 3
    with pytest.raises(ProtocolAgentCallError) as error:
        ProtocolWorkbenchService._revise_feedback_with_model(
            source, SimpleNamespace(), "EX-01", "第二次候选恢复不能续发额度",
            preserve_review_items=True, budget_store=store,
        )
    assert error.value.error_code == "LOGICAL_BUDGET_EXHAUSTED"
    assert saved[run_id]["requests_used"] == 3
    assert built == closed == ["model-0", "model-1", "model-0"]


@pytest.mark.parametrize("saved", [None, {}, {"requests_used": 1}])
def test_feedback_missing_or_invalid_budget_stops_before_model(monkeypatch, saved):
    from app.agents import protocol_semantic_model_router as router
    store = SimpleNamespace(load_call_budget=lambda key: saved, store_call_budget=lambda value: None)
    monkeypatch.setattr(router, "build_transport_for_candidate", lambda candidate: pytest.fail("must not build"))
    source = SimpleNamespace(protocol_file_sha256="a" * 64, extraction_snapshot_id="frozen-input")
    with pytest.raises(ProtocolAgentCallError) as error:
        ProtocolWorkbenchService._revise_feedback_with_model(source, SimpleNamespace(), "EX-01", "修订", budget_store=store)
    assert error.value.error_code == ("BUDGET_RECORD_MISSING" if saved is None else "BUDGET_RECORD_INVALID")


@pytest.mark.parametrize("code", ["MODEL_IDENTITY_MISMATCH", "STREAM_INTERRUPTED", "TRANSPORT_TIMEOUT",
    "SOURCE_REFERENCE_ASSEMBLY_PERSISTENCE_FAILED"])
def test_feedback_hard_failure_does_not_switch_model(monkeypatch, code):
    from app.agents import protocol_deconstructor as author
    from app.agents import protocol_semantic_model_router as router
    candidates = [ProtocolSemanticRouteCandidate(backend="cms-router", model=f"model-{i}", reasoning_effort="high")
                  for i in range(2)]
    built = []
    monkeypatch.setattr(router, "select_protocol_semantic_route_candidates", lambda *a, **kw: candidates)
    monkeypatch.setattr(router, "candidate_availability_error", lambda candidate: None)
    monkeypatch.setattr(router, "build_transport_for_candidate",
                        lambda candidate: built.append(candidate.model) or SimpleNamespace())

    def revise(*args, **kwargs):
        raise ProtocolAgentCallError("failed-before-fallback", "不可自动重新发送", error_code=code)

    monkeypatch.setattr(author, "revise_protocol_draft_from_feedback", revise)
    with pytest.raises(ProtocolAgentCallError) as error:
        ProtocolWorkbenchService._revise_feedback_with_model(SimpleNamespace(), SimpleNamespace(), "EX-01", "修订")
    assert error.value.error_code == code
    assert built == ["model-0"]


@pytest.mark.parametrize("failure_code", [None, "STREAM_INTERRUPTED"])
def test_feedback_close_failure_does_not_replace_read_outcome(monkeypatch, caplog, failure_code):
    from app.agents import protocol_deconstructor as author
    from app.agents import protocol_semantic_model_router as router
    candidate = ProtocolSemanticRouteCandidate(backend="cms-router", model="synthetic-model", reasoning_effort="high")
    monkeypatch.setattr(router, "select_protocol_semantic_route_candidates", lambda *a, **kw: [candidate])
    monkeypatch.setattr(router, "candidate_availability_error", lambda candidate: None)

    def fail_close():
        raise OSError("synthetic close failure")

    monkeypatch.setattr(router, "build_transport_for_candidate",
                        lambda candidate: SimpleNamespace(_client=SimpleNamespace(close=fail_close)))

    def revise(*args, **kwargs):
        if failure_code:
            raise ProtocolAgentCallError("synthetic-call", "原读取失败", error_code=failure_code)
        return SimpleNamespace(draft_id="read-success")

    monkeypatch.setattr(author, "revise_protocol_draft_from_feedback", revise)
    if failure_code:
        with pytest.raises(ProtocolAgentCallError) as error:
            ProtocolWorkbenchService._revise_feedback_with_model(SimpleNamespace(), SimpleNamespace(), "EX-01", "修订")
        assert error.value.error_code == failure_code
    else:
        result = ProtocolWorkbenchService._revise_feedback_with_model(SimpleNamespace(), SimpleNamespace(), "EX-01", "修订")
        assert result.draft_id == "read-success"
    assert "方案修订连接关闭未完成" in caplog.text


def test_env_example_and_launcher_do_not_treat_mtplx_as_complex_primary():
    env_text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "DECONSTRUCT_ROUTE_MODE=pinned" in env_text
    assert "glm-5.3-flash" in env_text
    assert "deepseek-v4.1-flash" in env_text
    assert "DECONSTRUCT_GLM_PROVIDER=cms-router" in env_text
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert "SHOULD_AUTOSTART_MTPLX" in launcher
    assert "跳过自动启动 MTPLX" in launcher
    assert "ENROLLMENT_START_MTPLX" in launcher
    service = SERVICE_SCRIPT.read_text(encoding="utf-8")
    assert "DECONSTRUCT_ROUTE_MODE" in service
    assert "DECONSTRUCT_GLM_MODEL" in service
    assert "scripts.run_v2_desktop" in service
    assert "app.main:app" not in service


def test_service_entry_sources_have_no_project_specific_hardcoding():
    for path in (
        ROUTER_SOURCE,
        EXECUTOR_SOURCE,
        WORKBENCH_SOURCE,
        APP_SOURCE,
        ENV_EXAMPLE,
        LAUNCHER,
        SERVICE_SCRIPT,
    ):
        assert_no_project_specific_hardcoding(path.read_text(encoding="utf-8"))


def test_generate_path_still_uses_shared_router_snapshot_not_deconstruct_backend_pin(
    monkeypatch,
):
    monkeypatch.setattr(executor_module, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(
        "app.agents.protocol_semantic_model_router.DECONSTRUCT_ROUTE_MODE",
        "graded",
    )
    monkeypatch.setattr(
        "app.agents.protocol_semantic_model_router.DECONSTRUCT_ROUTE_COMPLEX",
        "",
    )
    snapshot = service_entry_semantic_route_snapshot()
    source = EXECUTOR_SOURCE.read_text(encoding="utf-8")
    assert "_run_semantic_generation_with_routing" in source
    assert "select_protocol_semantic_route_candidates" in source
    assert snapshot["complex_identities"][0].startswith("cms-router:")
    assert snapshot["short_grade"] == GRADE_SHORT


@pytest.mark.parametrize("code", [
    "BUDGET_RECORD_MISSING", "BUDGET_RECORD_INVALID", "LOGICAL_BUDGET_EXHAUSTED",
    "MODEL_IDENTITY_MISMATCH", "STREAM_INTERRUPTED", "TRANSPORT_TIMEOUT",
    "SEMANTIC_CACHE_INVALID",
])
@pytest.mark.parametrize("returned_failure", [False, True])
def test_initial_generate_terminal_cause_stops_next_provider_and_keeps_audit(
    data_paths, monkeypatch, code, returned_failure,
):
    candidates = [ProtocolSemanticRouteCandidate(
        backend="cms-router", model=f"synthetic-{number}", reasoning_effort="high",
    ) for number in (1, 2)]
    monkeypatch.setattr(executor_module, "resolve_route_mode", lambda *args: "graded")
    decision = ProtocolSemanticGradeDecision(
        grade="short_prompt_semantic", parent_rule_count=1, token_estimate=100,
        batch_total=1, short_prompt_max_input_tokens=4096, reasons=("synthetic_test",),
    )
    monkeypatch.setattr(executor_module, "_grade_generate_task", lambda *args, **kwargs: (decision, candidates))
    monkeypatch.setattr(executor_module, "candidate_availability_error", lambda candidate: None)
    monkeypatch.setattr(executor_module, "semantic_repair_limit_for_candidate", lambda *args: 1)
    builds = []

    def build(candidate):
        builds.append(candidate.identity)
        return SimpleNamespace()

    monkeypatch.setattr(executor_module, "build_transport_for_candidate", build)
    result = SimpleNamespace(
        status="需要核对", same_session_id="synthetic-first-call", final_draft=None,
        final_gate_result=None, attempts=[SimpleNamespace(
            outcome="会话异常", issues=[], call_metadata={"error_code": code},
        )],
    )

    class Runner:
        def __init__(self, **kwargs):
            pass

        def run(self, *args, **kwargs):
            if returned_failure:
                return result
            raise ProtocolAgentCallError("synthetic-first-call", "不可自动重放", error_code=code)

    monkeypatch.setattr(executor_module, "ProtocolDeconstructorRunner", Runner)
    config = ProtocolDeconstructionExecutorConfig(data_paths=data_paths, session_factory=SimpleNamespace())
    call = lambda: executor_module._run_semantic_generation_with_routing(
        context=SimpleNamespace(job_id="synthetic-terminal-generate"), config=config,
        package=SimpleNamespace(source_input=SimpleNamespace(), source_spans={}),
        prompt_version=SimpleNamespace(),
    )
    if returned_failure:
        actual, audit = call()
        assert actual is result and not audit["attempts"][0]["discarded_merged_candidate"]
    else:
        with pytest.raises(ProtocolAgentCallError) as caught:
            call()
        assert caught.value.error_code == code
    assert builds == [candidates[0].identity]
    saved = load_persisted_route_audit(config, "synthetic-terminal-generate")
    assert saved["final_outcome"] == "stopped"
    assert saved["final_identity"] == candidates[0].identity
    assert [attempt["error_class"] for attempt in saved["attempts"]] == [code]


def test_initial_generate_declared_nonterminal_route_still_reaches_next_provider(data_paths, monkeypatch):
    candidates = [ProtocolSemanticRouteCandidate(
        backend="cms-router", model=f"synthetic-{number}", reasoning_effort="high",
    ) for number in (1, 2)]
    monkeypatch.setattr(executor_module, "resolve_route_mode", lambda *args: "graded")
    decision = ProtocolSemanticGradeDecision(
        grade="short_prompt_semantic", parent_rule_count=1, token_estimate=100,
        batch_total=1, short_prompt_max_input_tokens=4096, reasons=("synthetic_test",),
    )
    monkeypatch.setattr(executor_module, "_grade_generate_task", lambda *args, **kwargs: (decision, candidates))
    monkeypatch.setattr(executor_module, "candidate_availability_error", lambda candidate: None)
    monkeypatch.setattr(executor_module, "semantic_repair_limit_for_candidate", lambda *args: 1)
    monkeypatch.setattr(executor_module, "build_transport_for_candidate", lambda candidate: SimpleNamespace(identity=candidate.identity))
    calls = []
    accepted = SimpleNamespace(status="可以进入审阅", same_session_id="synthetic-second-call",
                               final_draft=object(), final_gate_result=SimpleNamespace(publishable=True))

    class Runner:
        def __init__(self, **kwargs):
            pass

        def run(self, *args, **kwargs):
            calls.append(kwargs["transport"].identity)
            if len(calls) == 1:
                raise ProtocolAgentCallError("synthetic-first-call", "已声明的可替代连接失败")
            return accepted

    monkeypatch.setattr(executor_module, "ProtocolDeconstructorRunner", Runner)
    config = ProtocolDeconstructionExecutorConfig(data_paths=data_paths, session_factory=SimpleNamespace())
    result, audit = executor_module._run_semantic_generation_with_routing(
        context=SimpleNamespace(job_id="synthetic-declared-generate"), config=config,
        package=SimpleNamespace(source_input=SimpleNamespace(), source_spans={}), prompt_version=SimpleNamespace(),
    )
    assert result is accepted and calls == [candidate.identity for candidate in candidates]
    assert audit["final_outcome"] == "accepted"


@pytest.mark.parametrize(("outcome", "cause", "expected"), [
    ("stopped", "MODEL_IDENTITY_MISMATCH", "MODEL_IDENTITY_MISMATCH"),
    ("accepted", None, "SEMANTIC_ROUTE_AUDIT_WRITE_FAILED"),
])
def test_route_audit_write_failure_is_explicit_and_keeps_primary_cause(
    data_paths, monkeypatch, outcome, cause, expected,
):
    from app.workflow.errors import StepFailure

    candidate = ProtocolSemanticRouteCandidate(
        backend="cms-router", model="synthetic-model", reasoning_effort="high",
    )
    audit = ProtocolSemanticRouteAudit(
        job_id="audit-storage-failure", route_mode="pinned", grade_decision=None,
        ordered_candidates=[candidate], final_identity=candidate.identity,
        final_outcome=outcome, attempts=[ProtocolSemanticRouteAttemptRecord(
            route_attempt=1, grade=GRADE_SHORT, backend=candidate.backend,
            model=candidate.model, reasoning_effort=candidate.reasoning_effort,
            outcome="failed" if cause else "accepted",
            error_class=cause,
        )],
    )

    def fail_save(*args, **kwargs):
        raise OSError("synthetic storage failure")

    monkeypatch.setattr(type(data_paths.boundary), "atomic_write_bytes", fail_save)
    config = ProtocolDeconstructionExecutorConfig(data_paths=data_paths, session_factory=SimpleNamespace())
    with pytest.raises(StepFailure) as caught:
        executor_module._persist_route_audit(config, "audit-storage-failure", audit)
    assert caught.value.error_code == expected
    assert caught.value.retryable is False
    saved = caught.value.diagnostic_checkpoint["semantic_route_audit_failure"]
    assert saved["storage_error_type"] == "OSError"
    assert saved["audit"]["final_outcome"] == outcome
