"""切片 6 重新解构后端：目标项目持久化、正式版本投影、同谱系同期别发布编排。

覆盖执行合同验证项：

- 重新解构任务持久保存目标项目（会话投影保持 target_project 谱系/期别）；
- 项目正式版本读取：``list_official_projects`` 与 ``get_project_official_version``；
- 同谱系同期别发布编排复用既有发布事务：同一项目追加新的不可变规则版本，
  旧正式版本保持可读；幂等重放不重复写入；
- 跨方案/跨期文件阻止发布并给出中文下一步（发布事务层确定性校验）；
- 取消/保存草稿不改变正式版本。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.domain.contracts.agent_io import ProtocolDeconstructionInput
from app.domain.contracts.enums import (
    AnchorResolutionMode,
    InterpretationSourceType,
    JobEventType,
    ReviewStage,
    StudyPhase,
)
from app.domain.contracts.protocol_metadata import (
    AnchorResolutionStatement,
    InterpretationSource,
)
from app.services.protocol_draft_service import ProtocolDraftService
from app.services.protocol_publication_service import (
    ProtocolPublicationRequest,
    ProtocolPublicationService,
)
from app.protocols.deconstruction_gate import (
    CHECK_NAMES,
    DECONSTRUCTION_GATE_VERSION,
    ProtocolDeconstructionGateResult,
    ProtocolGateCheckResult,
    ProtocolGateIssue,
)
from app.domain.contracts.protocol_drafts import DraftFeedbackKind
from app.domain.contracts.normalization import UnresolvedItem
from app.services.protocol_workbench_service import (
    ProtocolWorkbenchError,
    ProtocolWorkbenchService,
)
from app.storage.repositories import list_interpretation_sources
from app.workflow.jobstore import JobStore


class AlwaysPublishableGate:
    """恒可通过门禁：隔离发布事务内的谱系/期别校验本身。"""

    def evaluate(self, *args, **kwargs):
        return ProtocolDeconstructionGateResult(
            publishable=True,
            checks=[
                ProtocolGateCheckResult(check_name=name, passed=True)
                for name in CHECK_NAMES
            ],
        )


class CountingPublishableGate(AlwaysPublishableGate):
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, *args, **kwargs):
        self.calls += 1
        return super().evaluate(*args, **kwargs)


class InterpretationAwareGate(AlwaysPublishableGate):
    def evaluate(self, source_input, *args, **kwargs):
        if source_input.interpretation_sources:
            return super().evaluate(source_input, *args, **kwargs)
        issue = ProtocolGateIssue(
            issue_code="INTERPRETATION_REQUIRED",
            check_name="interpretation_authority",
            level="阻止发布",
            problem="尚未登记解释材料。",
            impact="当前草稿不能发布。",
            next_action="请登记解释材料。",
            affected_refs=["IN-01"],
            repair_scope=["IN-01"],
        )
        return ProtocolDeconstructionGateResult(
            publishable=False,
            checks=[
                ProtocolGateCheckResult(
                    check_name=name,
                    passed=name != "interpretation_authority",
                    issues=[issue] if name == "interpretation_authority" else [],
                )
                for name in CHECK_NAMES
            ],
        )


class FeedbackRegressionGate:
    """目标规则被无关重写时增加阻断问题。"""

    def evaluate(self, _source_input, draft, **_kwargs):
        target = draft.proposed_rules[1].components[0]
        issue_count = 2 if target.title == "引入无关变化" else 1
        issues = [
            ProtocolGateIssue(
                issue_code=f"TARGET_ISSUE_{index}",
                check_name="tree_integrity",
                level="阻止发布",
                problem=f"目标规则问题 {index}",
                impact="当前草稿不能发布。",
                next_action="请最小范围修订。",
                affected_refs=[target.rule_component_id],
                repair_scope=[target.rule_component_id],
            )
            for index in range(1, issue_count + 1)
        ]
        return ProtocolDeconstructionGateResult(
            publishable=False,
            checks=[
                ProtocolGateCheckResult(
                    check_name=name,
                    passed=name != "tree_integrity",
                    issues=issues if name == "tree_integrity" else [],
                )
                for name in CHECK_NAMES
            ],
        )
from app.storage.repositories import (
    JobRepository,
    ProtocolDraftRevisionRepository,
    get_project_row,
    list_rule_set_revisions,
)

from tests.v2.protocols.slice4_helpers import confirmed_fixture

# JobStore 持久化列使用 UTC naive；测试服务时间必须与运行时一致。
NAIVE_NOW = datetime(2026, 8, 17, tzinfo=timezone.utc).replace(tzinfo=None)


def _make_service(
    session_factory, data_paths, gate=None, feedback_reviser=None
) -> ProtocolWorkbenchService:
    return ProtocolWorkbenchService(
        session_factory,
        data_paths=data_paths,
        now=lambda: NAIVE_NOW,
        gate=gate,
        feedback_reviser=feedback_reviser,
    )


def _write_minimal_docx(data_paths, name: str) -> Path:
    directory = data_paths.root / "uploads"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(b"\x00" * 32)
    return path


def _publish_first(factory, source_input, draft, spans, key="redo-first"):
    with factory() as session:
        with session.begin():
            revision = ProtocolDraftService(session).save_initial_draft(
                draft, actor="医学监查员", created_at=NAIVE_NOW
            )
    service = ProtocolPublicationService(factory, now=lambda: NAIVE_NOW)
    return service.publish(
        ProtocolPublicationRequest(
            idempotency_key=key,
            draft_revision_id=revision.revision_id,
            source_input=source_input,
            source_spans=spans,
            actor="医学监查员",
            published_at=NAIVE_NOW,
        )
    )


def _revised_fixture(
    new_version: str = "protocol-version-2", *, phase=None, protocol=None
) -> tuple:
    """新修订案：默认同谱系（TEST-001）同期别（II 期）的新内部版本。

    可注入跨方案（``protocol``）或跨期（``phase``）用于发布拒绝测试。
    使用全新 draft_id，避免与首次解构保存的首稿冲突。

    交叉方案/期别只改变草稿侧语义（方案编号候选 / 所选期别），目标项目侧的谱系
    与期别保持不变；source_input 仍与草稿候选一致，确保身份/期别合同可解析。
    """
    source_input, draft, spans = confirmed_fixture()
    metadata = draft.protocol_metadata.model_copy(
        update={"version_candidate": "V2.0"}
    )
    draft = draft.model_copy(
        update={
            "protocol_version_id": new_version,
            "draft_id": f"draft-redo-{new_version}",
            "protocol_metadata": metadata,
        }
    )
    # 新版上传：内部版本 id 与官方版本号随新版本变化（同谱系同期别）。
    source_input = source_input.model_copy(deep=True)
    source_input.protocol_version_id = new_version
    source_input.identity_decision = source_input.identity_decision.model_copy(
        update={"official_version": "V2.0"}
    )
    if protocol is not None:
        # 交叉方案：草稿与输入同时改为另一方案编号候选，保持身份合同自洽，
        # 由发布事务内的谱系校验拒绝（cross_protocol）。
        draft = draft.model_copy(
            update={
                "protocol_metadata": metadata.model_copy(
                    update={"protocol_code_candidate": protocol}
                )
            }
        )
        source_input = source_input.model_copy(
            update={
                "identity_decision": source_input.identity_decision.model_copy(
                    update={"protocol_code": protocol}
                )
            }
        )
    if phase is not None:
        # 交叉期别只改变草稿侧所选期别与规则期别；source_input 保持目标项目
        # 期别不变，与既有发布测试一致（由 AlwaysPublishableGate 隔离谱系检查）。
        draft = draft.model_copy(
            update={
                "selected_phase": phase,
                "proposed_rules": [
                    rule.model_copy(update={"study_phase": phase})
                    for rule in draft.proposed_rules
                ],
            }
        )
    return source_input, draft, spans


def _start_redeconstruction(
    service: ProtocolWorkbenchService,
    project_id: str,
    data_paths,
    *,
    key: str = "redo-upload-1",
):
    docx = _write_minimal_docx(data_paths, f"redo-{project_id}-{key}.docx")
    return service.start_re_deconstruction(
        upload_path=docx,
        original_name=docx.name,
        project_id=project_id,
        idempotency_key=key,
        actor="医学监查员",
    )


def _seed_review(service, job_id, source_input, draft, spans, *, wait_at="publish"):
    service.seed_review_session(
        job_id,
        source_input=source_input,
        draft=draft,
        source_spans=spans,
        wait_at=wait_at,
    )


def _publish_first_with_source_context(
    service, data_paths, source_input, draft, spans
):
    docx = _write_minimal_docx(data_paths, "first-with-source-context-helper.docx")
    started = service.start_first_deconstruction(
        upload_path=docx,
        original_name=docx.name,
        idempotency_key="first-with-source-context-helper",
        actor="医学监查员",
    )
    service.seed_review_session(
        started.job_id,
        source_input=source_input,
        draft=draft,
        source_spans=spans,
        wait_at="publish",
    )
    return service.publish_first_project(
        started.job_id,
        idempotency_key="publish-with-source-context-helper",
        actor="医学监查员",
    )


def test_redeconstruction_start_persists_target_project(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    service = _make_service(factory, data_paths)
    source_input, draft, spans = confirmed_fixture()
    first = _publish_first(factory, source_input, draft, spans)
    assert first.project_id == "project-1"

    result = _start_redeconstruction(service, "project-1", data_paths)
    assert result.created is True

    session_view = service.get_session(result.job_id)
    assert session_view.session_kind == "re_deconstruction"
    assert session_view.target_project_id == "project-1"
    assert session_view.target_project_code == "TEST"
    assert session_view.target_protocol_code == "TEST-001"
    assert session_view.target_study_phase == StudyPhase.PHASE_II.value
    assert session_view.target_study_phase_label == "II 期"
    assert session_view.target_official_version == "V1.0"
    assert session_view.target_rule_set_revision == 1

    # 幂等：同键同目标项目复用原任务
    repeat = _start_redeconstruction(
        service, "project-1", data_paths, key="redo-upload-1"
    )
    assert repeat.created is False
    assert repeat.job_id == result.job_id


def test_redeconstruction_unknown_project_rejected(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    service = _make_service(factory, data_paths)
    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        _start_redeconstruction(service, "missing-project", data_paths)
    assert exc_info.value.code == "PROJECT_NOT_FOUND"
    assert "找不到正式项目" in exc_info.value.title

def test_protocol_upload_rejects_formats_without_source_preserving_extraction(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    service = _make_service(factory, data_paths)
    unsupported = data_paths.root / "protocol.txt"
    unsupported.write_text("not a DOCX or native PDF", encoding="utf-8")

    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        service.start_first_deconstruction(
            upload_path=unsupported,
            original_name="protocol.txt",
            idempotency_key="unsupported-txt",
        )

    assert exc_info.value.code == "UNSUPPORTED_PROTOCOL_FILE"
    assert "请以 DOCX 重新上传正式方案" in exc_info.value.recovery

def test_protocol_upload_rejects_pdf_after_entry_decommission(
    slice4_env, data_paths
) -> None:
    """方案 PDF 上传入口已下线：PDF 必须在上传门禁被拒绝，不创建任务。"""
    factory, _now = slice4_env
    service = _make_service(factory, data_paths)
    pdf = data_paths.root / "protocol.pdf"
    pdf.write_bytes(b"%PDF-1.7 decommissioned entry check")

    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        service.start_first_deconstruction(
            upload_path=pdf,
            original_name="protocol.pdf",
            idempotency_key="pdf-decommissioned",
        )

    assert exc_info.value.code == "UNSUPPORTED_PROTOCOL_FILE"
    assert "方案 PDF 上传入口已下线" in exc_info.value.detail

def test_redeconstruction_rejects_publish_when_formal_baseline_has_advanced(
    slice4_env, data_paths
) -> None:
    """并行任务只能发布到启动时读取的正式规则版，旧基线不得覆盖新正式版。"""
    factory, _now = slice4_env
    service = _make_service(factory, data_paths, gate=AlwaysPublishableGate())
    source_input, draft, spans = confirmed_fixture()
    published = _publish_first(factory, source_input, draft, spans)
    task_a = _start_redeconstruction(
        service, published.project_id, data_paths, key="parallel-redo-a"
    )
    task_b = _start_redeconstruction(
        service, published.project_id, data_paths, key="parallel-redo-b"
    )
    source_a, draft_a, spans_a = _revised_fixture("parallel-version-a")
    source_b, draft_b, spans_b = _revised_fixture("parallel-version-b")
    _seed_review(service, task_a.job_id, source_a, draft_a, spans_a, wait_at="publish")
    _seed_review(service, task_b.job_id, source_b, draft_b, spans_b, wait_at="publish")
    service.publish_re_deconstruction(
        task_b.job_id,
        idempotency_key="parallel-publish-b",
        actor="医学监查员",
    )

    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        service.publish_re_deconstruction(
            task_a.job_id,
            idempotency_key="parallel-publish-a",
            actor="医学监查员",
        )
    assert exc_info.value.code == "PUBLICATION_LINEAGE_REJECTED"
    assert "当前正式规则版本已被" in exc_info.value.detail
    assert service.get_project_official_version(published.project_id).publication_count == 2


def test_feedback_redeconstruction_starts_from_formal_draft_without_upload(
    slice4_env, data_paths
) -> None:
    """无新版文件时复用正式发布任务的来源上下文，候选稿与正式稿初始无差异。"""
    factory, _now = slice4_env
    service = _make_service(factory, data_paths, gate=AlwaysPublishableGate())
    source_input, draft, spans = confirmed_fixture()
    docx = _write_minimal_docx(data_paths, "first-with-source-context.docx")
    started = service.start_first_deconstruction(
        upload_path=docx,
        original_name=docx.name,
        idempotency_key="first-with-source-context",
        actor="医学监查员",
    )
    service.seed_review_session(
        started.job_id,
        source_input=source_input,
        draft=draft,
        source_spans=spans,
        wait_at="publish",
    )
    published = service.publish_first_project(
        started.job_id,
        idempotency_key="publish-with-source-context",
        actor="医学监查员",
    )
    interpretation = InterpretationSource(
        interpretation_source_id="source-node-relative",
        protocol_version_id=published.protocol_version_id,
        source_type=InterpretationSourceType.MEDICAL_INTERPRETATION,
        file_sha256="8" * 64,
        source_ref="medical-note:1",
        excerpt="既往时间窗未写明起算日期。",
        explanation="按当前审核节点日期逐节点独立核对。",
        applies_to_rule_refs=["IN-01"],
        clarifies_ambiguity=True,
        anchor_resolutions=[
            AnchorResolutionStatement(
                resolution_id="resolution-node-relative",
                affected_rule_refs=["IN-01"],
                ambiguous_source_refs=["span-in"],
                target_review_stages=[ReviewStage.SCREENING, ReviewStage.BASELINE],
                resolution_mode=AnchorResolutionMode.CURRENT_REVIEW_NODE_DATE,
            )
        ],
    )

    result = service.start_feedback_re_deconstruction(
        project_id=published.project_id,
        idempotency_key="feedback-from-formal",
        interpretation_sources=[interpretation],
        actor="医学监查员",
    )
    assert result.created is True
    session_view = service.get_session(result.job_id)
    assert session_view.state == "waiting_user"
    assert session_view.awaiting_user == "review"
    assert session_view.target_project_id == published.project_id
    comparison = service.get_draft_comparison(result.job_id)
    assert comparison.baseline.revision_id != comparison.candidate.revision_id
    assert comparison.diff["added_rule_codes"] == []
    assert comparison.diff["removed_rule_codes"] == []
    assert comparison.diff["modified_rule_codes"] == []
    assert all(not item["added"] and not item["removed"] for item in comparison.diff["rule_diffs"])
    rebound_input = ProtocolDeconstructionInput.model_validate(
        service._merged_payload(result.job_id)["source_input"]
    )
    assert len(rebound_input.interpretation_sources) == 1
    assert rebound_input.interpretation_sources[0].protocol_version_id == (
        rebound_input.protocol_version_id
    )
    assert rebound_input.interpretation_sources[0].interpretation_source_id != (
        interpretation.interpretation_source_id
    )

    replay = service.start_feedback_re_deconstruction(
        project_id=published.project_id,
        idempotency_key="feedback-from-formal",
        interpretation_sources=[interpretation],
        actor="医学监查员",
    )
    assert replay.created is False
    assert replay.job_id == result.job_id

    republished = service.publish_re_deconstruction(
        result.job_id,
        idempotency_key="feedback-from-formal-publish",
        actor="医学监查员",
    )
    assert republished.project_id == published.project_id
    assert republished.rule_set_revision == 2
    with factory() as session:
        stored = list_interpretation_sources(
            session, republished.protocol_version_id
        )
    assert len(stored) == 1
    assert stored[0].anchor_resolutions[0].target_review_stages == [
        ReviewStage.SCREENING,
        ReviewStage.BASELINE,
    ]
    current = service.get_project_official_version(published.project_id)
    assert current.project.official_version == "V1.0"
    assert current.publication_count == 2


def test_feedback_redeconstruction_fails_closed_without_formal_source_context(
    slice4_env, data_paths
) -> None:
    """旧正式项目只有规则而没有原始方案定位时，不得生成无来源反馈草稿。"""
    factory, _now = slice4_env
    service = _make_service(factory, data_paths)
    source_input, draft, spans = confirmed_fixture()
    published = _publish_first(
        factory,
        source_input,
        draft,
        spans,
        key="formal-without-job-context",
    )
    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        service.start_feedback_re_deconstruction(
            project_id=published.project_id,
            idempotency_key="feedback-without-context",
            actor="医学监查员",
        )
    assert exc_info.value.code == "FORMAL_SOURCE_CONTEXT_MISSING"
    assert "上传新版方案" in exc_info.value.recovery


def test_source_error_feedback_creates_real_local_revision(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    source_input, draft, spans = confirmed_fixture()

    def revise(_source_input, current_draft, target_rule_code, feedback_note):
        assert target_rule_code == "EX-01"
        assert feedback_note == "原文要求同时满足两个条件，请重新核对。"
        revised = current_draft.model_copy(deep=True)
        revised.proposed_rules[1].components[0].title = "按原文重新核对后的条件"
        revised.component_drafts[1].proposed_component.title = "按原文重新核对后的条件"
        return revised

    service = _make_service(
        factory,
        data_paths,
        gate=InterpretationAwareGate(),
        feedback_reviser=revise,
    )
    started = service.start_first_deconstruction(
        upload_path=_write_minimal_docx(data_paths, "feedback-revision.docx"),
        original_name="feedback-revision.docx",
        idempotency_key="feedback-revision-first",
        actor="医学监查员",
    )
    service.seed_review_session(
        started.job_id,
        source_input=source_input,
        draft=draft,
        source_spans=spans,
        wait_at="await_review",
    )
    before = service.get_draft_detail(started.job_id)

    after = service.apply_feedback(
        started.job_id,
        expected_revision_id=before.revision.revision_id,
        feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
        target_rule_code="EX-01",
        feedback_note="原文要求同时满足两个条件，请重新核对。",
        actor="医学监查员",
    )

    assert after.revision.revision_number == before.revision.revision_number + 1
    assert after.revision.content.proposed_rules[1].components[0].title == "按原文重新核对后的条件"
    assert after.revision.diff.modified_rule_codes == ["EX-01"]

    # 反馈修订会向生成/完整性步骤追加局部检查点。重启后必须
    # 继续从该步骤早期检查点恢复方案输入和来源定位，不得被
    # 后写的 draft_revision_id 局部更新遮蔽。
    restarted = _make_service(
        factory,
        data_paths,
        gate=AlwaysPublishableGate(),
        feedback_reviser=revise,
    )
    sources = restarted.get_sources(started.job_id)
    assert sources["snapshot_id"] == source_input.extraction_snapshot_id
    assert sources["selected_phase"] == source_input.selected_phase.value
    assert sources["source_spans"] == {
        key: value.model_dump(mode="json") for key, value in spans.items()
    }
    assert restarted.get_draft_detail(started.job_id).revision.revision_id == (
        after.revision.revision_id
    )


def test_active_draft_interpretation_registration_revises_and_publishes(
    slice4_env, data_paths
) -> None:
    """活动草稿登记解释材料后，语义修订读取同一来源并随版本原子发布。"""
    factory, _now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    seen_source_ids: list[str] = []

    def revise(current_input, current_draft, target_rule_code, _feedback_note):
        assert target_rule_code == "IN-01"
        seen_source_ids.extend(
            item.interpretation_source_id
            for item in current_input.interpretation_sources
        )
        revised = current_draft.model_copy(deep=True)
        revised.proposed_rules[0].components[0].title = "按解释材料重新核对后的条件"
        revised.component_drafts[0].proposed_component.title = (
            "按解释材料重新核对后的条件"
        )
        return revised

    service = _make_service(
        factory,
        data_paths,
        gate=AlwaysPublishableGate(),
        feedback_reviser=revise,
    )
    started = service.start_first_deconstruction(
        upload_path=_write_minimal_docx(data_paths, "active-source-registration.docx"),
        original_name="active-source-registration.docx",
        idempotency_key="active-source-registration-first",
        actor="医学监查员",
    )
    service.seed_review_session(
        started.job_id,
        source_input=source_input,
        draft=draft,
        source_spans=spans,
        wait_at="await_review",
    )
    before = service.get_draft_detail(started.job_id)
    interpretation = InterpretationSource(
        interpretation_source_id="source-active-draft",
        protocol_version_id=source_input.protocol_version_id,
        source_type=InterpretationSourceType.MEDICAL_INTERPRETATION,
        file_sha256="b" * 64,
        source_ref="medical-note:active-draft",
        excerpt="既往时间窗未写明起算日期。",
        explanation="按当前审核节点日期逐节点独立核对。",
        applies_to_rule_refs=["IN-01"],
        clarifies_ambiguity=True,
        anchor_resolutions=[
            AnchorResolutionStatement(
                resolution_id="resolution-active-draft",
                affected_rule_refs=["IN-01"],
                ambiguous_source_refs=["span-in"],
                target_review_stages=[ReviewStage.SCREENING, ReviewStage.BASELINE],
                resolution_mode=AnchorResolutionMode.CURRENT_REVIEW_NODE_DATE,
            )
        ],
    )

    registered = service.register_interpretation_sources(
        started.job_id,
        expected_revision_id=before.revision.revision_id,
        idempotency_key="active-source-registration",
        interpretation_sources=[interpretation],
        actor="医学监查员",
    )
    assert registered["draft_revision_id"] == before.revision.revision_id
    assert registered["protocol_version_id"] == source_input.protocol_version_id
    assert [
        item["interpretation_source_id"]
        for item in registered["interpretation_sources"]
    ] == ["source-active-draft"]
    assert registered["source_materials"]["span-in"]["text"] == "年龄≥18岁"
    assert service.get_session(started.job_id).awaiting_user == "review"
    with factory() as session:
        event_types = [
            row.event.event_type
            for row in JobStore(session).list_event_rows(started.job_id)
        ]
    assert JobEventType.USER_UPDATED in event_types
    assert service.get_draft_detail(started.job_id).revision.revision_id == (
        before.revision.revision_id
    )
    assert service.get_integrity(started.job_id).publishable

    replay = service.register_interpretation_sources(
        started.job_id,
        expected_revision_id=before.revision.revision_id,
        idempotency_key="active-source-registration",
        interpretation_sources=[interpretation],
        actor="医学监查员",
    )
    assert replay["interpretation_sources"] == registered["interpretation_sources"]

    after = service.apply_feedback(
        started.job_id,
        expected_revision_id=before.revision.revision_id,
        feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
        target_rule_code="IN-01",
        feedback_note="原文需要结合解释材料重新核对。",
        actor="医学监查员",
    )
    assert seen_source_ids == ["source-active-draft"]
    assert after.revision.revision_number == before.revision.revision_number + 1
    assert after.revision.diff.modified_rule_codes == ["IN-01"]

    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        service.register_interpretation_sources(
            started.job_id,
            expected_revision_id=before.revision.revision_id,
            idempotency_key="active-source-registration-stale",
            interpretation_sources=[interpretation],
            actor="医学监查员",
        )
    assert exc_info.value.code == "STALE_REVISION"

    published = service.publish_first_project(
        started.job_id,
        idempotency_key="active-source-registration-publish",
        actor="医学监查员",
    )
    with factory() as session:
        stored = list_interpretation_sources(
            session, published.protocol_version_id
        )
    assert [item.interpretation_source_id for item in stored] == [
        "source-active-draft"
    ]
    assert stored[0].anchor_resolutions[0].target_review_stages == [
        ReviewStage.SCREENING,
        ReviewStage.BASELINE,
    ]


def test_source_error_feedback_rejects_target_rule_gate_regression(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    source_input, draft, spans = confirmed_fixture()

    def revise(_source_input, current_draft, _target_rule_code, _feedback_note):
        revised = current_draft.model_copy(deep=True)
        revised.proposed_rules[1].components[0].title = "引入无关变化"
        revised.component_drafts[1].proposed_component.title = "引入无关变化"
        return revised

    service = _make_service(
        factory,
        data_paths,
        gate=FeedbackRegressionGate(),
        feedback_reviser=revise,
    )
    started = service.start_first_deconstruction(
        upload_path=_write_minimal_docx(data_paths, "feedback-regression.docx"),
        original_name="feedback-regression.docx",
        idempotency_key="feedback-regression-first",
        actor="医学监查员",
    )
    service.seed_review_session(
        started.job_id,
        source_input=source_input,
        draft=draft,
        source_spans=spans,
        wait_at="await_review",
    )
    before = service.get_draft_detail(started.job_id)

    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        service.apply_feedback(
            started.job_id,
            expected_revision_id=before.revision.revision_id,
            feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
            target_rule_code="EX-01",
            feedback_note="只修复当前完整性问题。",
            actor="医学监查员",
        )

    assert exc_info.value.code == "FEEDBACK_REVISION_FAILED"
    assert service.get_draft_detail(started.job_id).revision.revision_id == (
        before.revision.revision_id
    )


def test_default_feedback_reviser_retries_one_rejected_candidate(
    slice4_env, data_paths
) -> None:
    """默认模型候选首次引入新问题时，携带门禁原因重试一次。"""

    factory, _now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    notes: list[str] = []

    def revise(_source_input, current_draft, _target_rule_code, feedback_note):
        notes.append(feedback_note)
        revised = current_draft.model_copy(deep=True)
        title = "引入无关变化" if len(notes) == 1 else "按原文完成局部修订"
        revised.proposed_rules[1].components[0].title = title
        revised.component_drafts[1].proposed_component.title = title
        return revised

    service = _make_service(
        factory,
        data_paths,
        gate=FeedbackRegressionGate(),
    )
    # 保留默认修订器的自动恢复策略，仅用可控候选替代外部调用。
    service.feedback_reviser = revise
    started = service.start_first_deconstruction(
        upload_path=_write_minimal_docx(data_paths, "feedback-retry.docx"),
        original_name="feedback-retry.docx",
        idempotency_key="feedback-retry-first",
        actor="医学监查员",
    )
    service.seed_review_session(
        started.job_id,
        source_input=source_input,
        draft=draft,
        source_spans=spans,
        wait_at="await_review",
    )
    before = service.get_draft_detail(started.job_id)

    after = service.apply_feedback(
        started.job_id,
        expected_revision_id=before.revision.revision_id,
        feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
        target_rule_code="EX-01",
        feedback_note="只修复当前完整性问题。",
        actor="医学监查员",
    )

    assert len(notes) == 2
    assert "上一个候选稿未通过" in notes[1]
    assert "TARGET_ISSUE_2" in notes[1]
    assert after.revision.revision_number == before.revision.revision_number + 1
    assert after.revision.content.proposed_rules[1].components[0].title == (
        "按原文完成局部修订"
    )


def test_source_error_feedback_may_only_close_selected_rule_unresolved_item(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    draft = draft.model_copy(
        update={
            "unresolved_items": [
                UnresolvedItem(code="RESOLVED", affected_scope=["IN-01"]),
                UnresolvedItem(code="KEEP", affected_scope=["EX-01"]),
            ]
        }
    )

    def revise(_source_input, current_draft, target_rule_code, _feedback_note):
        assert target_rule_code == "IN-01"
        return current_draft.model_copy(
            update={
                "unresolved_items": [
                    item
                    for item in current_draft.unresolved_items
                    if target_rule_code not in item.affected_scope
                ]
            },
            deep=True,
        )

    service = _make_service(
        factory,
        data_paths,
        gate=AlwaysPublishableGate(),
        feedback_reviser=revise,
    )
    started = service.start_first_deconstruction(
        upload_path=_write_minimal_docx(data_paths, "feedback-close-item.docx"),
        original_name="feedback-close-item.docx",
        idempotency_key="feedback-close-item-first",
        actor="医学监查员",
    )
    service.seed_review_session(
        started.job_id,
        source_input=source_input,
        draft=draft,
        source_spans=spans,
        wait_at="await_review",
    )
    before = service.get_draft_detail(started.job_id)

    after = service.apply_feedback(
        started.job_id,
        expected_revision_id=before.revision.revision_id,
        feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
        target_rule_code="IN-01",
        feedback_note="原文时间范围已明确，关闭旧待确认事项。",
        actor="医学监查员",
    )

    assert after.revision.revision_number == before.revision.revision_number + 1
    assert [item.code for item in after.revision.content.unresolved_items] == ["KEEP"]
    assert after.revision.diff.modified_rule_codes == []


def test_failed_source_error_feedback_keeps_current_revision(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    source_input, draft, spans = confirmed_fixture()

    def fail_revision(*_args):
        raise RuntimeError("模型未返回可读取结果")

    service = _make_service(
        factory,
        data_paths,
        feedback_reviser=fail_revision,
    )
    started = service.start_first_deconstruction(
        upload_path=_write_minimal_docx(data_paths, "feedback-failure.docx"),
        original_name="feedback-failure.docx",
        idempotency_key="feedback-failure-first",
        actor="医学监查员",
    )
    service.seed_review_session(
        started.job_id,
        source_input=source_input,
        draft=draft,
        source_spans=spans,
        wait_at="await_review",
    )
    before = service.get_draft_detail(started.job_id)

    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        service.apply_feedback(
            started.job_id,
            expected_revision_id=before.revision.revision_id,
            feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
            target_rule_code="EX-01",
            feedback_note="请核对原文。",
            actor="医学监查员",
        )

    assert exc_info.value.code == "FEEDBACK_REVISION_FAILED"
    current = service.get_draft_detail(started.job_id)
    assert current.revision.revision_id == before.revision.revision_id


def test_source_error_feedback_rejects_noop_or_changes_outside_selected_rule(
    slice4_env, data_paths
) -> None:
    """原文纠错不得用无变化结果冒充修订，也不得顺带修改其他父规则。"""

    factory, _now = slice4_env
    source_input, draft, spans = confirmed_fixture()

    for mode in ("noop", "other-rule", "hidden-reparent", "cross-parent-id-reuse"):
        def invalid_revise(_source_input, current_draft, _target, _note, mode=mode):
            revised = current_draft.model_copy(deep=True)
            if mode == "other-rule":
                revised.proposed_rules[0].components[0].title = "错误地修改了其他规则"
            elif mode == "hidden-reparent":
                revised.proposed_rules[1].components[0].title = "目标规则确有变化"
                revised.proposed_rules[0].components[0].parent_rule_id = "rule-ex"
            elif mode == "cross-parent-id-reuse":
                target = revised.proposed_rules[1].components[0]
                target.rule_component_id = (
                    revised.proposed_rules[0].components[0].rule_component_id
                )
                target.title = "目标规则确有变化"
                target_binding = next(
                    item
                    for item in revised.component_drafts
                    if item.parent_official_code == "EX-01"
                )
                target_binding.proposed_component = target.model_copy(deep=True)
            return revised

        service = _make_service(
            factory,
            data_paths,
            feedback_reviser=invalid_revise,
        )
        started = service.start_first_deconstruction(
            upload_path=_write_minimal_docx(data_paths, f"feedback-invalid-{mode}.docx"),
            original_name=f"feedback-invalid-{mode}.docx",
            idempotency_key=f"feedback-invalid-{mode}",
            actor="医学监查员",
        )
        case_draft = draft.model_copy(update={"draft_id": f"draft-feedback-invalid-{mode}"})
        service.seed_review_session(
            started.job_id,
            source_input=source_input,
            draft=case_draft,
            source_spans=spans,
            wait_at="await_review",
        )
        before = service.get_draft_detail(started.job_id)

        with pytest.raises(ProtocolWorkbenchError) as exc_info:
            service.apply_feedback(
                started.job_id,
                expected_revision_id=before.revision.revision_id,
                feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
                target_rule_code="EX-01",
                feedback_note="只修订选中的规则。",
                actor="医学监查员",
            )

        assert exc_info.value.code == "FEEDBACK_REVISION_FAILED"
        assert service.get_draft_detail(started.job_id).revision.revision_id == before.revision.revision_id


def test_clarification_feedback_records_note_without_changing_rules(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    source_input, draft, spans = confirmed_fixture()

    def must_not_run(*_args):
        raise AssertionError("补充解释不应调用规则修订")

    service = _make_service(
        factory,
        data_paths,
        feedback_reviser=must_not_run,
    )
    started = service.start_first_deconstruction(
        upload_path=_write_minimal_docx(data_paths, "clarification.docx"),
        original_name="clarification.docx",
        idempotency_key="clarification-first",
        actor="医学监查员",
    )
    service.seed_review_session(
        started.job_id,
        source_input=source_input,
        draft=draft,
        source_spans=spans,
        wait_at="await_review",
    )
    before = service.get_draft_detail(started.job_id)

    after = service.apply_feedback(
        started.job_id,
        expected_revision_id=before.revision.revision_id,
        feedback_kind=DraftFeedbackKind.CLARIFICATION,
        target_rule_code="IN-01",
        feedback_note="该条按医学组解释记录，不改变方案阈值。",
        actor="医学监查员",
    )

    assert after.revision.content == before.revision.content.model_copy(
        update={
            "draft_revision": after.revision.revision_number,
            "previous_draft_id": before.revision.content.draft_id,
        }
    )
    assert after.revision.diff.modified_rule_codes == []
    assert after.revision.feedback_note == "IN-01：该条按医学组解释记录，不改变方案阈值。"
    integrity = service.get_integrity(started.job_id)
    assert integrity.publishable is True
    assert integrity.blocking_count == 0


def test_redeconstruction_clarification_keeps_integrity_publishable(
    slice4_env, data_paths
) -> None:
    """正式版本反馈修订后，等价结构差异不能因模型类型不同被误判。"""
    factory, _now = slice4_env
    service = _make_service(factory, data_paths)
    source_input, draft, spans = confirmed_fixture()
    published = _publish_first_with_source_context(
        service, data_paths, source_input, draft, spans
    )
    started = service.start_feedback_re_deconstruction(
        project_id=published.project_id,
        idempotency_key="redo-clarification-integrity",
        actor="医学监查员",
    )
    before = service.get_draft_detail(started.job_id)
    service.apply_feedback(
        started.job_id,
        expected_revision_id=before.revision.revision_id,
        feedback_kind=DraftFeedbackKind.CLARIFICATION,
        target_rule_code="IN-01",
        feedback_note="仅记录审阅说明，不改变方案语义。",
        actor="医学监查员",
    )

    integrity = service.get_integrity(started.job_id)
    assert integrity.publishable is True
    assert integrity.blocking_count == 0


def test_integrity_recomputes_and_persists_when_gate_version_is_stale(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    gate = CountingPublishableGate()
    service = _make_service(factory, data_paths, gate=gate)
    source_input, draft, spans = confirmed_fixture()
    started = service.start_first_deconstruction(
        upload_path=_write_minimal_docx(data_paths, "stale-gate.docx"),
        original_name="stale-gate.docx",
        idempotency_key="stale-gate-first",
        actor="医学监查员",
    )
    service.seed_review_session(
        started.job_id,
        source_input=source_input,
        draft=draft,
        source_spans=spans,
        wait_at="await_review",
    )
    gate.calls = 0
    with factory() as session:
        with session.begin():
            JobRepository(session).create_checkpoint(
                checkpoint_id="stale-gate-checkpoint",
                job_id=started.job_id,
                step_id="integrity_check",
                payload={
                    "gate_result": AlwaysPublishableGate().evaluate().model_dump(
                        mode="json"
                    ),
                    "gate_version": "protocol-deconstruction-gate/old",
                    "publishable": True,
                },
            )

    integrity = service.get_integrity(started.job_id)

    assert integrity.publishable is True
    assert gate.calls == 1
    merged = service._merged_payload(started.job_id)
    assert merged["gate_version"] == DECONSTRUCTION_GATE_VERSION


def test_project_official_version_projection_reads_published_chain(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    service = _make_service(factory, data_paths)
    source_input, draft, spans = confirmed_fixture()
    _publish_first(factory, source_input, draft, spans)

    listed = service.list_official_projects()
    assert len(listed) == 1
    project = listed[0]
    assert project.project_id == "project-1"
    assert project.project_code == "TEST"
    assert project.protocol_code == "TEST-001"
    assert project.official_version == "V1.0"
    assert project.rule_set_revision == 1

    projection = service.get_project_official_version("project-1")
    assert projection.project.project_code == "TEST"
    assert projection.publication_count == 1
    assert len(projection.versions) == 1
    version = projection.versions[0]
    assert version.rule_set_revision == 1
    assert version.protocol_version_id == "protocol-version-1"
    assert version.official_version == "V1.0"
    assert version.rule_count == 2
    assert version.sha256 == "a" * 64

    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        service.get_project_official_version("missing-project")
    assert exc_info.value.code == "PROJECT_NOT_FOUND"


def test_redeconstruction_publish_appends_new_immutable_rule_version(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    service = _make_service(factory, data_paths)
    source_input, draft, spans = confirmed_fixture()
    first = _publish_first(factory, source_input, draft, spans)
    assert first.rule_set_revision == 1
    assert first.rule_set_id == "ruleset:protocol-version-1:phase_ii"

    result = _start_redeconstruction(service, "project-1", data_paths)
    revised_input, revised_draft, revised_spans = _revised_fixture()
    _seed_review(service, result.job_id, revised_input, revised_draft, revised_spans)
    view = service.publish_re_deconstruction(
        result.job_id,
        idempotency_key="redo-pub-v2",
        actor="医学监查员",
    )
    assert view.replay is False
    assert view.project_id == "project-1"
    assert view.protocol_version_id == "protocol-version-2"
    assert view.rule_set_id == first.rule_set_id
    assert view.rule_set_revision == 2

    # 旧正式版本保持可读；新 revision 追加在同一项目
    with factory() as session:
        project, revision = get_project_row(session, "project-1")
        assert revision == 2
        assert project.protocol_version.official_version == "V2.0"
        revisions = list_rule_set_revisions(session, project.rule_set_id)
        assert [item[0] for item in revisions] == [1, 2]
        assert revisions[0][1].official_version == "V1.0"
        assert revisions[1][1].official_version == "V2.0"

    # 幂等重放不重复写入且返回同一结果
    replay_view = service.publish_re_deconstruction(
        result.job_id,
        idempotency_key="redo-pub-v2",
        actor="医学监查员",
    )
    assert replay_view.replay is True
    assert replay_view.rule_set_revision == 2


def test_redeconstruction_cross_protocol_rejected_chinese_next_step(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    service = _make_service(factory, data_paths)
    source_input, draft, spans = confirmed_fixture()
    _publish_first(factory, source_input, draft, spans)

    result = _start_redeconstruction(service, "project-1", data_paths)
    wrong_input, wrong_draft, wrong_spans = _revised_fixture(
        protocol="OTHER-001"
    )
    _seed_review(service, result.job_id, wrong_input, wrong_draft, wrong_spans)
    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        service.publish_re_deconstruction(
            result.job_id,
            idempotency_key="redo-cross-protocol",
            actor="医学监查员",
        )
    assert exc_info.value.code == "PUBLICATION_LINEAGE_REJECTED"
    assert "方案谱系或期别与目标项目不一致" in exc_info.value.title
    assert "同一方案" in exc_info.value.recovery


def test_redeconstruction_cross_phase_rejected(slice4_env, data_paths) -> None:
    factory, _now = slice4_env
    # 跨期草稿本身会被确定性 phase_scope 门禁拒绝；用恒可通过门禁隔离发布
    # 事务内的谱系/期别校验，验证同谱系同期别编排的 cross_phase 中文下一步。
    service = _make_service(factory, data_paths, gate=AlwaysPublishableGate())
    source_input, draft, spans = confirmed_fixture()
    _publish_first(factory, source_input, draft, spans)

    result = _start_redeconstruction(service, "project-1", data_paths)
    wrong_input, wrong_draft, wrong_spans = _revised_fixture(
        phase=StudyPhase.PHASE_III
    )
    # 恒可通过门禁：seed_review_session 缓存可发布 gate_result，
    # 发布事务内再以 same gate 复跑并命中 cross_phase。
    _seed_review(service, result.job_id, wrong_input, wrong_draft, wrong_spans)
    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        service.publish_re_deconstruction(
            result.job_id,
            idempotency_key="redo-cross-phase",
            actor="医学监查员",
        )
    assert exc_info.value.code == "PUBLICATION_LINEAGE_REJECTED"
    assert "同一方案" in exc_info.value.recovery


def test_redeconstruction_save_and_cancel_do_not_change_formal_version(
    slice4_env, data_paths
) -> None:
    factory, _now = slice4_env
    service = _make_service(factory, data_paths)
    source_input, draft, spans = confirmed_fixture()
    _publish_first(factory, source_input, draft, spans)

    # 取消重新解构会话：草稿取消后正式版本仍为 revision 1
    result = _start_redeconstruction(service, "project-1", data_paths)
    revised_input, revised_draft, revised_spans = _revised_fixture()
    _seed_review(
        service,
        result.job_id,
        revised_input,
        revised_draft,
        revised_spans,
        wait_at="await_review",
    )
    merged = service._merged_payload(result.job_id)
    revision = service._load_draft_revision(merged)
    service.cancel_draft(
        result.job_id,
        expected_revision_id=revision.revision_id,
    )
    with factory() as session:
        _project, project_revision = get_project_row(session, "project-1")
        assert project_revision == 1

    # 发布成功后正式版本为 V2.0（新不可变规则版本），不影响旧记录
    result2 = _start_redeconstruction(
        service, "project-1", data_paths, key="redo-upload-2"
    )
    revised_input2, revised_draft2, revised_spans2 = _revised_fixture(
        new_version="protocol-version-3"
    )
    _seed_review(
        service, result2.job_id, revised_input2, revised_draft2, revised_spans2
    )
    view = service.publish_re_deconstruction(
        result2.job_id,
        idempotency_key="redo-pub-save-cancel",
        actor="医学监查员",
    )
    assert view.rule_set_revision == 2
    with factory() as session:
        _project, project_revision = get_project_row(session, "project-1")
        assert project_revision == 2


def test_redeconstruction_identity_confirm_guard_blocks_mismatched_lineage() -> None:
    """身份确认时若新版方案与目标项目谱系/期别不一致，立即给出中文下一步。"""
    service = object.__new__(ProtocolWorkbenchService)
    redo_merged = {
        "session_kind": "re_deconstruction",
        "target_protocol_code": "TEST-001",
        "target_study_phase": StudyPhase.PHASE_II.value,
    }
    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        ProtocolWorkbenchService._validate_redeconstruction_lineage(
            redo_merged,
            protocol_code="OTHER-001",
            study_phase=StudyPhase.PHASE_II,
        )
    assert exc_info.value.code == "REDECONSTRUCTION_LINEAGE_MISMATCH"
    assert "方案编号" in exc_info.value.detail
    assert "同一方案编号" in exc_info.value.recovery

    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        ProtocolWorkbenchService._validate_redeconstruction_lineage(
            redo_merged,
            protocol_code="TEST-001",
            study_phase=StudyPhase.PHASE_III,
        )
    assert exc_info.value.code == "REDECONSTRUCTION_LINEAGE_MISMATCH"
    assert "研究期别" in exc_info.value.detail

    # 首次解构不触发谱系守卫
    first_merged = {"session_kind": "first_deconstruction"}
    ProtocolWorkbenchService._validate_redeconstruction_lineage(
        first_merged,
        protocol_code="ANY-001",
        study_phase=StudyPhase.PHASE_III,
    )


# ---------------------------------------------------------------------------
# 正式基线差异（Slice 6 阻断项回归）
# ---------------------------------------------------------------------------


def _threshold_bump_draft(baseline_draft, *, new_version="protocol-version-2"):
    """复制正式基线草稿并只改一条阈值（IN-01 年龄 18 -> 20），首稿相对基线的
    八类差异应只出现逻辑变化，而不是“全部新增”。"""
    changed = baseline_draft.model_copy(deep=True)
    changed = changed.model_copy(
        update={
            "draft_id": f"draft-redo-{new_version}",
            "protocol_version_id": new_version,
            "protocol_metadata": changed.protocol_metadata.model_copy(
                update={"version_candidate": "V2.0"}
            ),
        }
    )
    predicate = changed.proposed_rules[0].components[0].expression.predicate
    return changed.model_copy(
        update={
            "proposed_rules": [
                changed.proposed_rules[0].model_copy(
                    update={
                        "components": [
                            changed.proposed_rules[0].components[0].model_copy(
                                update={
                                    "expression": changed.proposed_rules[0]
                                    .components[0]
                                    .expression.model_copy(
                                        update={
                                            "predicate": predicate.model_copy(
                                                update={"value": 20}
                                            )
                                        }
                                    )
                                }
                            )
                        ]
                    }
                ),
                *changed.proposed_rules[1:],
            ]
        }
    )


def test_redeconstruction_first_revision_uses_formal_baseline_not_all_added(
    slice4_env, data_paths
) -> None:
    """首稿 diff 以当前正式（已发布）草稿为基线，而不是 None -> 全部新增。

    只改一条阈值时，八类差异只含该规则的逻辑变化，IN/EX 父规则均非新增。
    """
    factory, _now = slice4_env
    source_input, baseline_draft, spans = confirmed_fixture()
    _publish_first(factory, source_input, baseline_draft, spans)

    with factory() as session:
        baseline_revision = ProtocolDraftRevisionRepository(
            session
        ).find_published_by_protocol_version("protocol-version-1")[0]

    changed_draft = _threshold_bump_draft(baseline_draft)
    with factory() as session:
        with session.begin():
            service = ProtocolDraftService(session)
            revision = service.save_initial_draft(
                changed_draft,
                actor="医学监查员",
                created_at=NAIVE_NOW,
                baseline=baseline_revision.content,
            )
    assert revision.revision_number == 1
    diff = revision.diff
    # 不是全部新增：父规则新增列表为空
    assert diff.added_rule_codes == []
    assert diff.removed_rule_codes == []
    assert diff.modified_rule_codes == ["IN-01"]
    # rule_diffs：IN-01 存在、非 added，逻辑类变化引出 IN-01a
    by_code = {item.official_code: item for item in diff.rule_diffs}
    assert set(by_code) == {"IN-01", "EX-01"}
    assert by_code["IN-01"].added is False
    assert by_code["IN-01"].removed is False
    assert by_code["EX-01"].added is False
    assert any(
        change.stable_ref == "IN-01a" for change in by_code["IN-01"].logic_changes
    )
    assert by_code["EX-01"].logic_changes == []
    # 采用基线而非 None：流程节点不是新增
    assert diff.added_workflow_stage_ids == []


def test_redeconstruction_first_revision_empty_when_formal_unchanged(
    slice4_env, data_paths
) -> None:
    """正式版本未变时，八类差异应全空（基线 = 当前正式草稿）。"""
    factory, _now = slice4_env
    source_input, baseline_draft, spans = confirmed_fixture()
    _publish_first(factory, source_input, baseline_draft, spans)

    with factory() as session:
        baseline_revision = ProtocolDraftRevisionRepository(
            session
        ).find_published_by_protocol_version("protocol-version-1")[0]

    identical = baseline_draft.model_copy(
        update={
            "draft_id": "draft-identical",
            "protocol_version_id": "protocol-version-2",
        }
    )
    with factory() as session:
        with session.begin():
            service = ProtocolDraftService(session)
            revision = service.save_initial_draft(
                identical,
                actor="医学监查员",
                created_at=NAIVE_NOW,
                baseline=baseline_revision.content,
            )
    diff = revision.diff
    assert diff.added_rule_codes == []
    assert diff.modified_rule_codes == []
    assert diff.added_workflow_stage_ids == []
    for entry in diff.rule_diffs:
        item = entry.model_dump()
        for key in (
            "original_text_changes",
            "logic_changes",
            "time_window_changes",
            "exception_changes",
            "evidence_changes",
            "due_stage_changes",
        ):
            assert item[key] == []
        assert item["added_component_refs"] == []
        assert item["removed_component_refs"] == []


def test_redeconstruction_comparison_endpoint_uses_formal_baseline(
    slice4_env, data_paths
) -> None:
    """工作台比较投影：基线来自已发布草稿 revision，候选为链头，八类差异正确。"""
    factory, _now = slice4_env
    service = _make_service(factory, data_paths)
    source_input, baseline_draft, spans = confirmed_fixture()
    _publish_first(factory, source_input, baseline_draft, spans)

    result = _start_redeconstruction(service, "project-1", data_paths)
    changed_input, changed_draft, changed_spans = _revised_fixture()
    changed_draft = _threshold_bump_draft(changed_draft)
    _seed_review(
        service, result.job_id, changed_input, changed_draft, changed_spans
    )
    comparison = service.get_draft_comparison(result.job_id)
    assert comparison.baseline.is_formal_baseline is True
    assert comparison.candidate.is_formal_baseline is False
    assert comparison.baseline.protocol_version_id == "protocol-version-1"
    assert comparison.baseline.rule_count == 2
    assert comparison.candidate.rule_count == 2
    by_code = {item["official_code"]: item for item in comparison.diff["rule_diffs"]}
    assert by_code["IN-01"]["added"] is False
    assert by_code["IN-01"]["added_component_refs"] == []
    assert any(
        change["stable_ref"] == "IN-01a"
        for change in by_code["IN-01"]["logic_changes"]
    )
    assert comparison.source_bound is True


def test_redeconstruction_comparison_fails_closed_when_baseline_missing(
    slice4_env, data_paths
) -> None:
    """目标项目没有已发布草稿 revision 时，比较必须 fail-closed 并给中文恢复。"""
    factory, _now = slice4_env
    service = _make_service(factory, data_paths)

    # 已发布项目存在但正式版本没有对应草稿 revision：基线缺失 fail-closed
    source_input, baseline_draft, spans = confirmed_fixture()
    _publish_first(factory, source_input, baseline_draft, spans)
    with factory() as session:
        from sqlalchemy import delete

        from app.storage.models import ProtocolDraftRevisionRecord

        session.execute(
            delete(ProtocolDraftRevisionRecord).where(
                ProtocolDraftRevisionRecord.status == "published"
            )
        )
        session.commit()
    result = _start_redeconstruction(
        service, "project-1", data_paths, key="baseline-missing"
    )
    revised_input, revised_draft, revised_spans = _revised_fixture()
    _seed_review(
        service, result.job_id, revised_input, revised_draft, revised_spans
    )
    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        service.get_draft_comparison(result.job_id)
    assert exc_info.value.code.startswith("FORMAL_BASELINE")
    assert "基线" in exc_info.value.detail
    assert exc_info.value.recovery


def test_redeconstruction_comparison_fails_closed_on_inconsistent_baseline(
    slice4_env, data_paths
) -> None:
    """正式版本对应多条内容不一致的已发布 revision 时 fail-closed。

    通过真实仓储保存第二条内容不同的已发布 revision（哈希有效），
    使同一 protocol_version_id 出现两份内容不一致的发布记录。
    """
    from app.domain.contracts.protocol_drafts import DraftRevisionStatus

    factory, _now = slice4_env
    source_input, baseline_draft, spans = confirmed_fixture()
    _publish_first(factory, source_input, baseline_draft, spans)
    with factory() as session:
        with session.begin():
            forged = baseline_draft.model_copy(deep=True)
            forged = forged.model_copy(
                update={
                    "draft_id": "draft-forged",
                    "protocol_version_id": "protocol-version-1",
                    "protocol_metadata": forged.protocol_metadata.model_copy(
                        update={"version_candidate": "V9.9"}
                    ),
                }
            )
            service = ProtocolDraftService(session)
            revision = service.save_initial_draft(
                forged, actor="医学监查员", created_at=NAIVE_NOW
            )
            published = revision.model_copy(
                update={"status": DraftRevisionStatus.PUBLISHED}
            )
            ProtocolDraftRevisionRepository(session).update_status(published)
            session.commit()

    service = _make_service(factory, data_paths)
    result = _start_redeconstruction(service, "project-1", data_paths)
    revised_input, revised_draft, revised_spans = _revised_fixture()
    _seed_review(
        service, result.job_id, revised_input, revised_draft, revised_spans
    )
    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        service.get_draft_comparison(result.job_id)
    assert exc_info.value.code == "FORMAL_BASELINE_INCONSISTENT"
    assert "不一致" in exc_info.value.detail
    assert exc_info.value.recovery


def test_redeconstruction_uses_latest_formal_revision_after_republish(
    slice4_env, data_paths
) -> None:
    """重新发布 v2 后，下一次重新解构以 v2（最新正式 revision）为基线。"""
    from app.services.protocol_draft_service import resolve_formal_baseline_revision

    factory, _now = slice4_env
    service = _make_service(factory, data_paths)
    source_input, baseline_draft, spans = confirmed_fixture()
    _publish_first(factory, source_input, baseline_draft, spans)

    # 发布 v2（版本/日期变化，规则同正式基线，可通过门禁）
    result = _start_redeconstruction(service, "project-1", data_paths)
    v2_input, v2_draft, v2_spans = _revised_fixture(
        new_version="protocol-version-2"
    )
    _seed_review(service, result.job_id, v2_input, v2_draft, v2_spans)
    v2_view = service.publish_re_deconstruction(
        result.job_id,
        idempotency_key="redo-pub-v2",
        actor="医学监查员",
    )
    assert v2_view.rule_set_revision == 2

    # 下一次重新解构：正式基线必须是最新 v2 revision，而不是 v1
    with factory() as session:
        baseline = resolve_formal_baseline_revision(
            session=session, project_id="project-1"
        )
    assert baseline.protocol_version_id == "protocol-version-2"

    # 新草稿与 v2 基线比较：基线为 v2，版本未变时八类逻辑差异为空
    result2 = _start_redeconstruction(
        service, "project-1", data_paths, key="redo-after-v2"
    )
    unchanged_input, unchanged_draft, unchanged_spans = _revised_fixture(
        new_version="protocol-version-3"
    )
    _seed_review(
        service,
        result2.job_id,
        unchanged_input,
        unchanged_draft,
        unchanged_spans,
    )
    comparison = service.get_draft_comparison(result2.job_id)
    assert comparison.baseline.protocol_version_id == "protocol-version-2"
    by_code = {item["official_code"]: item for item in comparison.diff["rule_diffs"]}
    assert by_code["IN-01"]["added"] is False
    assert by_code["IN-01"]["logic_changes"] == []
