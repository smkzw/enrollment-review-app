"""Focused service-entry regressions for graded protocol-semantic routing.

These tests lock the production generate path, default config, and run-audit
loader so complex/short grading and whole-attempt isolation actually take
effect at the V2 service entry. No live provider calls. No project-specific
fixtures or study/protocol/disease/drug literals.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.agents.protocol_deconstructor import ProtocolAgentCallError
from app.agents.protocol_semantic_model_router import (
    GRADE_SHORT,
    ProtocolSemanticRouteAudit,
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
    # 默认链只声明 GLM high：无隐式 MTPLX/DeepSeek 第三模型回退。
    assert snapshot["complex_identities"] == [
        "zhipu-coding-plan:glm-5.3-flash:high",
    ]
    assert snapshot["short_identities"] == [
        "zhipu-coding-plan:glm-5.3-flash:high",
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


def test_env_example_and_launcher_do_not_treat_mtplx_as_complex_primary():
    env_text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "DECONSTRUCT_ROUTE_MODE=graded" in env_text
    assert "glm-5.3-flash" in env_text
    assert "deepseek-v4-flash" in env_text
    assert "不要把" in env_text and "生产主路由" in env_text
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert "SHOULD_AUTOSTART_MTPLX" in launcher
    assert "跳过自动启动 MTPLX" in launcher
    assert "ENROLLMENT_START_MTPLX" in launcher
    service = SERVICE_SCRIPT.read_text(encoding="utf-8")
    assert "DECONSTRUCT_ROUTE_MODE" in service
    assert "DECONSTRUCT_GLM_MODEL" in service


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
    assert snapshot["complex_identities"][0].startswith("zhipu-coding-plan:")
    assert snapshot["short_grade"] == GRADE_SHORT
