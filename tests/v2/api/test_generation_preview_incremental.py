"""生成期间逐批只读预览：持久化、水合与工作台读取的最小行为闭环。

不调用模型：候选由冻结输入确定性构造，仅覆盖 P0.P1 的宿主侧新增行为
（批进度落盘、事件、部分水合、预览端点与完成后的让位语义）。
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.agents.protocol_deconstructor import (
    hydrate_semantic_preview,
    semantic_candidate_from_draft,
)
from app.domain.contracts.agent_io import (
    ProtocolDeconstructionInput,
    ProtocolSemanticDeconstructionCandidate,
    SemanticEvidenceRequirement,
    SemanticRule,
    SemanticRuleComponent,
)
from app.domain.contracts.enums import (
    CatalogItemKind,
    Comparator,
    ReviewStage,
    StudyPhase,
)
from app.domain.contracts.rules import AtomicExpression, AtomicPredicate
from app.services.protocol_deconstruction_executor import (
    ProtocolDeconstructionExecutorConfig,
    _persist_semantic_batch_progress,
    _semantic_preview_path,
    create_protocol_deconstruction_executor,
)
from app.services.protocol_workbench_service import (
    PROTOCOL_DECONSTRUCTION_JOB_TYPE,
)
from app.workflow.runner import JobRunner
from tests.v2.api.protocol_e2e_helpers import (
    build_pipeline_e2e_docx,
    page_texts_from_blocks,
)
from tests.v2.protocols.slice4_helpers import confirmed_fixture

pytestmark = pytest.mark.usefixtures("_stable_semantic_route_preflight_env")


def _partial_candidate_for_input(
    source_input: ProtocolDeconstructionInput,
) -> ProtocolSemanticDeconstructionCandidate:
    """按 build_passing_draft_json 的确定性规则构造候选，但去掉最后一个父规则。"""
    materials = {
        material.source_span_id: material.text
        for material in source_input.source_materials
    }
    parent_items = [
        item
        for item in source_input.parent_rule_catalog.items
        if item.kind == CatalogItemKind.PARENT_RULE and item.official_code
    ]
    assert len(parent_items) >= 2, "测试方案应至少有两条父规则"
    proposed_rules: list[SemanticRule] = []
    for item in parent_items[:-1]:
        span_id = item.source_span_ids[0]
        excerpt = materials.get(span_id, item.label)
        proposed_rules.append(
            SemanticRule(
                official_code=item.official_code,
                components=[
                    SemanticRuleComponent(
                        title=item.label,
                        expression=AtomicExpression(
                            predicate=AtomicPredicate(
                                predicate_id=f"predicate-{item.official_code.lower()}",
                                subject="受试者",
                                attribute="方案条件",
                                source_term=item.label,
                                source_clause=excerpt,
                                comparator=Comparator.EQ,
                                value=True,
                                unit=None,
                            )
                        ),
                        evidence_requirements=[
                            SemanticEvidenceRequirement(
                                fact_type="方案要求事实",
                                required_source_types=["clinical_record"],
                                due_stage=ReviewStage.SCREENING,
                                description="核对正式原始资料和研究者记录",
                            )
                        ],
                        source_span_ids=[span_id],
                        source_excerpts=[excerpt],
                    )
                ],
            )
        )
    return ProtocolSemanticDeconstructionCandidate(
        candidate_id=uuid.uuid4().hex,
        proposed_rules=proposed_rules,
        created_by_agent_call_id="generation-preview-test",
    )


def test_hydrate_semantic_preview_keeps_pending_codes() -> None:
    source_input, draft, _spans = confirmed_fixture()
    full_candidate = semantic_candidate_from_draft(draft)

    full_draft, pending = hydrate_semantic_preview(source_input, full_candidate)
    assert pending == []
    assert len(full_draft.proposed_rules) == len(full_candidate.proposed_rules)

    partial_candidate = full_candidate.model_copy(
        update={"proposed_rules": full_candidate.proposed_rules[:-1]}
    )
    partial_draft, pending_codes = hydrate_semantic_preview(
        source_input, partial_candidate
    )
    dropped = full_candidate.proposed_rules[-1].official_code
    assert pending_codes == [dropped]
    assert [rule.official_code for rule in partial_draft.proposed_rules] == [
        rule.official_code for rule in partial_candidate.proposed_rules
    ]
    # 预览对象仍是完整草稿合同形状，但 revision 身份不得被误当作已保存草稿。
    assert partial_draft.draft_revision == 1
    assert partial_draft.source_refs, "预览草稿必须保留有源引用"


def test_anchor_wire_source_excerpts_recovers_deterministic_superset() -> None:
    """真实 SAR 避孕条款失败形态：模型整句超引 → 宿主回收为条件自身片段。"""
    from app.agents.protocol_deconstructor import _anchor_wire_source_excerpts

    clause = "有生育能力的女性受试者及其伴侣同意采取高效的避孕措施"
    full_sentence = (
        "整个研究期间（从签署ICF到研究药物给药后6个月），"
        "有生育能力的女性受试者及其伴侣同意采取高效的避孕措施，"
        "男性受试者及其伴侣同意采取有效的避孕措施且无捐献精子（男性）或卵子（女性）的计划；"
    )
    # 唯一包含的超集：确定性回收。
    assert _anchor_wire_source_excerpts([full_sentence], [clause]) == [clause]
    # 逐字命中与引号规范化命中保持不变/恢复。
    assert _anchor_wire_source_excerpts([clause], [clause]) == [clause]
    # 词级差异不回收；多片段超集取唯一最长的条件片段作为最具体锚点。
    assert _anchor_wire_source_excerpts(["完全不同的文字"], [clause]) == ["完全不同的文字"]
    other = "男性受试者及其伴侣同意采取有效的避孕措施"
    assert _anchor_wire_source_excerpts([full_sentence], [clause, other]) == [clause]
    # 等长并列的歧义片段：不猜，保持原样交给严格门禁。
    twin_a, twin_b = "甲条件片段等长", "乙条件片段等长"
    twin_excerpt = "总述：甲条件片段等长；乙条件片段等长。"
    assert _anchor_wire_source_excerpts(
        [twin_excerpt], [twin_a, twin_b]
    ) == [twin_excerpt]


def test_generation_preview_endpoint_serves_partial_then_yields_to_final(
    build_app,
) -> None:
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        import io
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
            docx_path = Path(handle.name)
        build_pipeline_e2e_docx(docx_path)
        files = {
            "file": (
                "preview-protocol.docx",
                io.BytesIO(docx_path.read_bytes()),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        docx_path.unlink(missing_ok=True)
        created = client.post(
            "/api/v2/protocol/deconstructions",
            files=files,
            data={"idempotency_key": "preview-1", "actor": "测试用户"},
        )
        assert created.status_code == 201, created.text
        job_id = created.json()["job_id"]

        def make_executor() -> JobRunner:
            executor = create_protocol_deconstruction_executor(
                ProtocolDeconstructionExecutorConfig(
                    data_paths=app.state.data_paths,
                    session_factory=app.state.session_factory,
                    page_texts_builder=page_texts_from_blocks,
                )
            )
            return JobRunner(
                app.state.session_factory,
                {PROTOCOL_DECONSTRUCTION_JOB_TYPE: executor},
                worker_id="preview-test-runner",
                poll_interval=0.01,
            )

        # 首段让语义提供方确定性不可用，避免任何真实网络调用；
        # freeze 完成后 generate 进入 failed_retryable，任务停在没有草稿的状态。
        import app.services.protocol_deconstruction_executor as executor_module

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(executor_module, "DEEPSEEK_API_KEY", "")
        monkeypatch.setattr(executor_module, "DECONSTRUCT_BACKEND", "deepseek")
        monkeypatch.setattr(executor_module, "DECONSTRUCT_ROUTE_MODE", "pinned")

        runner = make_executor()
        for _ in range(10):
            session = client.get(
                f"/api/v2/protocol/deconstructions/{job_id}"
            ).json()
            if session.get("awaiting_user") == "identity":
                break
            runner.run_job(job_id)
        else:
            pytest.fail("任务未到达身份确认")

        confirmed = client.post(
            f"/api/v2/protocol/deconstructions/{job_id}/identity/confirm",
            json={
                "protocol_code": "E2E-001",
                "project_name": "E2E 测试研究",
                "official_version": "V1.0",
                "official_date_value": "2026-08-17",
                "official_date_precision": "day",
                "study_phase": StudyPhase.PHASE_II.value,
                "actor": "测试用户",
            },
        )
        assert confirmed.status_code == 200, confirmed.text

        # 冻结完成后、生成尚未产出草稿：预览端点先报告尚未有批次。
        runner.run_job(job_id)
        empty = client.get(
            f"/api/v2/protocol/deconstructions/{job_id}/draft/generation-preview"
        )
        assert empty.status_code == 200, empty.text
        assert empty.json()["available"] is False
        assert empty.json()["reason"] in {"not_started", "no_batch_ready"}

        # 用冻结输入构造部分候选并按逐批进度持久化（1/2 批）。
        service = app.state.protocol_workbench_service
        merged = service._merged_payload(job_id)
        source_input = ProtocolDeconstructionInput.model_validate(
            merged["source_input"]
        )
        partial = _partial_candidate_for_input(source_input)
        expected_pending = [
            item.official_code
            for item in source_input.parent_rule_catalog.items
            if item.kind == CatalogItemKind.PARENT_RULE and item.official_code
        ][-1]
        config = ProtocolDeconstructionExecutorConfig(
            data_paths=app.state.data_paths,
            session_factory=app.state.session_factory,
        )
        _persist_semantic_batch_progress(config, job_id, 1, 2, partial)
        assert _semantic_preview_path(app.state.data_paths, job_id).is_file()

        preview = client.get(
            f"/api/v2/protocol/deconstructions/{job_id}/draft/generation-preview"
        )
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["available"] is True
        assert body["preview_only"] is True
        assert body["batch_index"] == 1 and body["batch_total"] == 2
        assert body["pending_codes"] == [expected_pending]
        assert body["content"]["proposed_rules"], "预览必须携带有源规则内容"
        assert body["content"]["proposed_rules"][0]["components"][0]["title"]

        # 任务事件中应能查到逐批进度（B2 计量锚点；SSE 端点为流式，测试直接读库）。
        from app.workflow.jobstore import JobStore as _JobStore

        with app.state.session_factory() as session:
            rows = _JobStore(session).list_event_rows(job_id)
        semantic_events = [
            row for row in rows if row.event.event_type == "semantic_batch_progress"
        ]
        assert semantic_events, "逐批进度事件未写入任务事件流"


def test_generation_preview_yields_after_final_draft(build_app) -> None:
    """生成完成、正式草稿 revision 存在后，预览端点让位给正式草稿视图。

    基线的 build_passing_draft_json 只能驱动单批收集；合成方案按 16K 输入
    预算会被计划器拆成两批（属已记录的预存测试债）。本测试在测试作用域内
    放大批次输入预算恢复单批打包，不改变产品行为。
    """
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        import io
        import tempfile
        from pathlib import Path

        import app.agents.protocol_deconstructor as deconstructor_module
        from tests.v2.api.protocol_e2e_helpers import build_passing_draft_json

        with pytest.MonkeyPatch.context() as planner_patch:
            planner_patch.setattr(
                deconstructor_module, "SEMANTIC_BATCH_MAX_INPUT_TOKENS", 10_000_000
            )
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
                docx_path = Path(handle.name)
            build_pipeline_e2e_docx(docx_path)
            files = {
                "file": (
                    "preview-final-protocol.docx",
                    io.BytesIO(docx_path.read_bytes()),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            }
            docx_path.unlink(missing_ok=True)
            created = client.post(
                "/api/v2/protocol/deconstructions",
                files=files,
                data={"idempotency_key": "preview-final-1", "actor": "测试用户"},
            )
            assert created.status_code == 201, created.text
            job_id = created.json()["job_id"]

            executor = create_protocol_deconstruction_executor(
                ProtocolDeconstructionExecutorConfig(
                    data_paths=app.state.data_paths,
                    session_factory=app.state.session_factory,
                    page_texts_builder=page_texts_from_blocks,
                    draft_response_builder=build_passing_draft_json,
                )
            )
            runner = JobRunner(
                app.state.session_factory,
                {PROTOCOL_DECONSTRUCTION_JOB_TYPE: executor},
                worker_id="preview-final-runner",
                poll_interval=0.01,
            )
            for _ in range(10):
                session = client.get(
                    f"/api/v2/protocol/deconstructions/{job_id}"
                ).json()
                if session.get("awaiting_user") == "identity":
                    break
                runner.run_job(job_id)
            else:
                pytest.fail("任务未到达身份确认")

            confirmed = client.post(
                f"/api/v2/protocol/deconstructions/{job_id}/identity/confirm",
                json={
                    "protocol_code": "E2E-001",
                    "project_name": "E2E 测试研究",
                    "official_version": "V1.0",
                    "official_date_value": "2026-08-17",
                    "official_date_precision": "day",
                    "study_phase": StudyPhase.PHASE_II.value,
                    "actor": "测试用户",
                },
            )
            assert confirmed.status_code == 200, confirmed.text

            for _ in range(10):
                session = client.get(
                    f"/api/v2/protocol/deconstructions/{job_id}"
                ).json()
                if session.get("awaiting_user") == "review":
                    break
                runner.run_job(job_id)
            else:
                pytest.fail("任务未在候选执行器推进后到达审阅等待")

            final_preview = client.get(
                f"/api/v2/protocol/deconstructions/{job_id}/draft/generation-preview"
            )
            assert final_preview.status_code == 200, final_preview.text
            assert final_preview.json()["available"] is False
            assert final_preview.json()["reason"] == "final_draft_ready"

