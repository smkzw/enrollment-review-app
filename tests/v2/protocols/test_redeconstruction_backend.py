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
    ProtocolDraftRevisionRepository,
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
