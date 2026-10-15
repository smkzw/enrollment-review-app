"""批量原件重新识别的只读投影：薄父记录清单与逐成员详情。

清单只核验父批次登记并分页，不读取成员与子任务，损坏记录计入
``unavailable_count``，不伪装为空成功。详情逐成员核验冻结身份、子任务归属
与完成检查点；``recorded_state`` 是批量结束时如实记录的成员终态，``state``
是子任务当前状态（后续单独重试会改变后者，不回写批量历史）。批量完成只
代表处理完成，``activated`` 恒为 False，不代表结果启用或临床接受。
"""
from datetime import UTC

from sqlalchemy import func, select

from app.services.batch_evidence_reprocessing import (
    BATCH_JOB_TYPE,
    CONTINUATION_FAILED_CODE,
    OWNER,
    material,
    owned_children,
    validate_completed_members,
)
from app.services.evidence_reprocessing import (
    _source,
    reprocessing_view,
)
from app.storage.codecs import PersistedContractInvalid
from app.storage.models import JobRecord
from app.storage.repositories import ProjectRepository, ScopeViolationError, SubjectRepository, EpisodeRepository, get_workflow_stages_by_ids
from app.workflow.jobstore import JobStore

PAGE_SIZE = 20


def recent_reprocessing_batches(session, *, project_id, offset=0):
    if offset < 0 or offset > 100000:
        raise ScopeViolationError("批量识别记录的页码超出范围")
    ProjectRepository(session).get(project_id)
    rows = list(session.scalars(select(JobRecord).where(
        JobRecord.job_type == BATCH_JOB_TYPE,
        func.json_extract(JobRecord.payload_json, "$.execution_owner") == OWNER,
        func.json_extract(JobRecord.payload_json, "$.project_id") == project_id,
    ).order_by(JobRecord.created_at.desc(), JobRecord.job_id.desc()).offset(offset).limit(PAGE_SIZE + 1)))
    items = []
    unavailable_count = 0
    for row in rows[:PAGE_SIZE]:
        try:
            _, payload = material(session, row.job_id)
            if payload["project_id"] != project_id:
                raise ScopeViolationError("批次项目归属不一致")
            created_at = row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at
            items.append({"job_id": row.job_id, "state": row.state,
                          "member_count": len(payload["members"]),
                          "created_at": created_at.isoformat()})
        except (PersistedContractInvalid, ScopeViolationError):
            unavailable_count += 1
    return {"project_id": project_id, "has_more": len(rows) > PAGE_SIZE, "offset": offset,
            "items": items, "unavailable_count": unavailable_count}


def batch_reprocessing_view(session, *, project_id, batch_id):
    row, payload = material(session, batch_id)
    if payload["project_id"] != project_id:
        raise ScopeViolationError("这批识别不属于所选研究项目")
    children = owned_children(session, batch_id, payload)
    store = JobStore(session)
    validate_completed_members(session, batch_id, payload, children)
    failure_detail = None
    if row.state in {"failed_final", "failed_retryable"}:
        for event in reversed(store.list_event_rows(batch_id)):
            if event.event.payload.get("error_code") == CONTINUATION_FAILED_CODE:
                failure_detail = event.event.payload.get("detail")
                break
    items = []
    for index, member in enumerate(payload["members"]):
        _source(session, project_id=project_id, subject_id=member["subject_id"],
            review_episode_id=member["review_episode_id"],
            snapshot_id=member["snapshot_id"], complete_id=member["complete_id"])
        child = children.get(index)
        subject = SubjectRepository(session).get(member["subject_id"])
        episode = EpisodeRepository(session).get(member["review_episode_id"])
        if subject.project_id != project_id or episode.subject_id != subject.subject_id:
            raise ScopeViolationError("批量识别的受试者登记不一致")
        stage = get_workflow_stages_by_ids(session, [episode.workflow_stage_id] if episode.workflow_stage_id else []).get(episode.workflow_stage_id)
        checkpoint = store.get_last_checkpoint(batch_id, f"member_{index}")
        if checkpoint is not None and (
                child is None
                or checkpoint[1].get("reprocess_job_id") != child[0].job_id
                or checkpoint[1].get("snapshot_id") != member["snapshot_id"]
                or checkpoint[1].get("complete_id") != member["complete_id"]):
            raise ScopeViolationError("批量识别完成记录与原件不一致")
        revision_id = None
        new_revision = False
        if child is not None and child[0].state == "completed":
            result = reprocessing_view(session, project_id=project_id, job_id=child[0].job_id)
            revision_id = result["revision_id"]
            new_revision = result["new_revision"]
        items.append({
            "subject_id": member["subject_id"],
            "subject_code": subject.subject_code,
            "node_label": stage.display_name if stage else "审核节点",
            "review_episode_id": member["review_episode_id"],
            "snapshot_id": member["snapshot_id"],
            "complete_id": member["complete_id"],
            "reprocess_job_id": child[0].job_id if child else None,
            "state": child[0].state if child else "not_started",
            "recorded_state": checkpoint[1].get("member_state") if checkpoint else None,
            "revision_id": revision_id,
            "new_revision": new_revision,
        })
    return {"job_id": batch_id, "project_id": project_id, "state": row.state,
            "activated": False, "failure_detail": failure_detail, "items": items}
