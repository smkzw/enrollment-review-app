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

from app.domain.contracts.enums import StudyPhase
from app.services.protocol_draft_service import ProtocolDraftService
from app.services.protocol_publication_service import (
    ProtocolPublicationRequest,
    ProtocolPublicationService,
)
from app.protocols.deconstruction_gate import (
    CHECK_NAMES,
    ProtocolDeconstructionGateResult,
    ProtocolGateCheckResult,
)
from app.services.protocol_workbench_service import (
    ProtocolWorkbenchError,
    ProtocolWorkbenchService,
)


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
from app.storage.repositories import (
    get_project_row,
    list_rule_set_revisions,
)

from tests.v2.protocols.slice4_helpers import confirmed_fixture

# JobStore 持久化列使用 UTC naive；测试服务时间必须与运行时一致。
NAIVE_NOW = datetime(2026, 8, 17, tzinfo=timezone.utc).replace(tzinfo=None)


def _make_service(
    session_factory, data_paths, gate=None
) -> ProtocolWorkbenchService:
    return ProtocolWorkbenchService(
        session_factory,
        data_paths=data_paths,
        now=lambda: NAIVE_NOW,
        gate=gate,
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
    assert session_view.target_project_code == "TEST-001"
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
    assert project.project_code == "TEST-001"
    assert project.protocol_code == "TEST-001"
    assert project.official_version == "V1.0"
    assert project.rule_set_revision == 1

    projection = service.get_project_official_version("project-1")
    assert projection.project.project_code == "TEST-001"
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
