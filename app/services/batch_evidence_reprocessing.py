"""同一项目内多份原件的批量重新识别后台，复用既有 JobStore 与维护回路。

边界（与单份重新识别一致）：
- 批量完成只代表处理完成，不是结果启用，更不是临床或入组结论；
- 子任务沿用 ``evidence_reprocess`` 任务类型与既有执行器，原始识别结果、
  原件与缓存全部保留，新修订不自动启用；
- 成员按提交顺序逐个创建子任务，父任务通过 ``release_deferred`` 等待子任务
  终态，不占用模型工作租约等待，也不新增表、线程或调度器；
- 成员子任务终态失败/取消如实记入父任务检查点后继续下一成员；创建子任务或
  来源/识别方式核验失败则显式停止未开始成员，已完成成员保持冻结。
"""
import logging

from sqlalchemy import and_, func, select, text

from app.domain.publication import canonical_hash
from app.domain.contracts.evidence_upload import DIRECT_VISION_PREPARATION
from app.services.evidence_reprocessing import (
    CONTRACT as REPROCESS_CONTRACT,
    JOB_TYPE as REPROCESS_JOB_TYPE,
    ReprocessingError,
    _source,
    create_reprocessing_child_in_session,
    pending_reprocessing_conflict,
)
from app.services.job_service import JobService, StepSpec
from app.services.evidence_app_errors import is_database_busy_error
from app.storage.codecs import PersistedContractInvalid, verify_payload_sha256
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.models import JobRecord
from app.storage.repositories import EpisodeRepository, ScopeViolationError
from app.domain.contracts.enums import SnapshotStatus
from app.workflow.errors import LeaseLostError
from app.workflow.jobstore import JobStore
from app.workflow.recovery import recover_expired_jobs
from app.workflow.states import TERMINAL_JOB_STATES

BATCH_JOB_TYPE = "batch_evidence_reprocess"
CONTRACT = "batch-evidence-reprocess/v1"
OWNER = "batch-evidence-reprocess/v1"
TERMINAL = set(TERMINAL_JOB_STATES)
MEMBER_KEYS = {"subject_id", "review_episode_id", "snapshot_id", "complete_id"}
CONTINUATION_FAILED_CODE = "BATCH_REPROCESS_CONTINUATION_FAILED"
logger = logging.getLogger(__name__)


class BatchReprocessingError(ReprocessingError):
    code = "EVIDENCE_REPROCESS_BATCH_REJECTED"


def material(session, batch_id):
    row = JobStore(session).get_job(batch_id)
    payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
    if (row.job_type != BATCH_JOB_TYPE or payload.get("contract") != CONTRACT
            or payload.get("execution_owner") != OWNER
            or not isinstance(payload.get("project_id"), str)
            or not isinstance(payload.get("profile_sha256"), str)
            or payload.get("preparation_policy") not in (None, DIRECT_VISION_PREPARATION)
            or not isinstance(payload.get("members"), list)):
        raise ScopeViolationError("批量识别记录不完整")
    members = payload["members"]
    if (not 1 <= len(members) <= 50 or any(not isinstance(item, dict) or set(item) != MEMBER_KEYS
            or any(not isinstance(value, str) or not value.strip() for value in item.values()) for item in members)
            or len({item["review_episode_id"] for item in members}) != len(members)):
        raise ScopeViolationError("批量识别成员记录不完整")
    return row, payload


def owned_children(session, batch_id, payload, *, for_cancellation=False):
    """核对每个子任务的批量归属与冻结成员身份，返回 {成员序号: (行, 载荷)}。

    归属无法核实的成员在取消路径跳过并保留，停止其他可证实归属的成员；
    其余路径显式失败，不用空成功掩盖。
    """
    found = {}
    members = {(item.get("subject_id"), item.get("review_episode_id"),
                item.get("snapshot_id"), item.get("complete_id")): index
               for index, item in enumerate(payload["members"])}
    rows = session.scalars(select(JobRecord).where(
        JobRecord.job_type == REPROCESS_JOB_TYPE,
        func.json_extract(JobRecord.payload_json, "$.batch_job_id") == batch_id,
    ))
    for row in rows:
        try:
            source = verify_payload_sha256(row.payload_json, row.payload_sha256)
            key = (source.get("subject_id"), source.get("review_episode_id"),
                   source.get("snapshot_id"), source.get("previous_complete_revision_id"))
            index = members.get(key)
            if (index is None or source.get("contract") != REPROCESS_CONTRACT
                    or source.get("project_id") != payload["project_id"]
                    or source.get("batch_job_id") != batch_id
                    or source.get("profile_sha256") != payload["profile_sha256"]
                    or source.get("preparation_policy") != payload.get("preparation_policy")
                    or source.get("attempt_namespace") != _member_namespace(batch_id, payload["members"][index])
                    or index in found):
                raise ScopeViolationError("批量识别的关联记录不一致，未更改其识别")
        except (PersistedContractInvalid, ScopeViolationError):
            if not for_cancellation:
                raise
            logger.exception("保留无法核实归属的批量成员，停止其他已核实成员")
            continue
        found[index] = (row, source)
    return found


def validate_completed_members(session, batch_id, payload, owned):
    store = JobStore(session)
    steps = {item.step_id: item for item in store.list_steps(batch_id)}
    if set(steps) != {f"member_{index}" for index in range(len(payload["members"]))}:
        raise ScopeViolationError("批量识别步骤与原件清单不一致")
    for index, member in enumerate(payload["members"]):
        step = steps[f"member_{index}"]
        if step.state != "completed":
            continue
        checkpoint = store.get_last_checkpoint(batch_id, step.step_id)
        child = owned.get(index)
        if (checkpoint is None or child is None
                or checkpoint[1].get("reprocess_job_id") != child[0].job_id
                or checkpoint[1].get("snapshot_id") != member["snapshot_id"]
                or checkpoint[1].get("complete_id") != member["complete_id"]
                or checkpoint[1].get("member_state") not in TERMINAL
                or checkpoint[1].get("activated") is not False):
            raise ScopeViolationError("批量识别的已完成记录不能与原件核对，未继续处理")


def cancel_owned(session, batch_id, payload):
    store = JobStore(session)
    for row, _source in owned_children(session, batch_id, payload, for_cancellation=True).values():
        if row.state not in TERMINAL:
            store.request_cancel(row.job_id)


def enqueue_reprocessing_batch(session_factory, adapter, *, project_id, members, request_key):
    """创建批量重新识别父任务；同项目 1–50 个不同节点，幂等键为请求键。

    提交前逐成员核对原件归属、当前资料指针与进行中任务冲突；成员身份
    {subject_id, review_episode_id, snapshot_id, complete_id} 与当前识别方式
    冻结进父任务载荷，子任务创建时再次原子复核。
    """
    if not isinstance(request_key, str) or not request_key.strip():
        raise BatchReprocessingError("本次批量操作信息不完整，请重新发起。")
    if not isinstance(members, list) or not 1 <= len(members) <= 50:
        raise BatchReprocessingError("请一次选择1至50份资料重新识别。")
    frozen = []
    seen_episodes = set()
    seen_snapshots = set()
    seen_completes = set()
    for item in members:
        if (not isinstance(item, dict) or set(item) != MEMBER_KEYS
                or any(not isinstance(value, str) or not value.strip()
                       for value in item.values())):
            raise BatchReprocessingError("批量成员资料不完整，请刷新后重新选择。")
        if (item["review_episode_id"] in seen_episodes or item["snapshot_id"] in seen_snapshots
                or item["complete_id"] in seen_completes):
            raise BatchReprocessingError("同一审核节点不能在本批中重复提交。")
        seen_episodes.add(item["review_episode_id"])
        seen_snapshots.add(item["snapshot_id"])
        seen_completes.add(item["complete_id"])
        frozen.append(dict(item))
    payload = {"contract": CONTRACT, "execution_owner": OWNER, "project_id": project_id,
               "profile_sha256": adapter.profile_fingerprint, "members": frozen,
               "preparation_policy": DIRECT_VISION_PREPARATION}
    with session_factory() as session, session.begin():
        session.execute(text("BEGIN IMMEDIATE"))
        result = JobService(session_factory).create_job_in_session(session,
            job_type=BATCH_JOB_TYPE, payload=payload,
            idempotency_key=f"{CONTRACT}:{project_id}:{request_key}",
            steps=[StepSpec(f"member_{index}", f"重新识别第{index + 1}份资料",
                depends_on=(() if index == 0 else (f"member_{index - 1}",))) for index in range(len(frozen))])
        if not result.created:
            return result
        for member in frozen:
            _source(session, project_id=project_id, subject_id=member["subject_id"],
                review_episode_id=member["review_episode_id"],
                snapshot_id=member["snapshot_id"], complete_id=member["complete_id"])
            episode = EpisodeRepository(session).get(member["review_episode_id"])
            if (episode.active_evidence_snapshot_id != member["snapshot_id"]
                    or episode.active_evidence_processing_revision_id != member["complete_id"]
                    or EvidenceSnapshotRepository(session).current_status(
                        member["snapshot_id"]) != SnapshotStatus.ACTIVE):
                raise BatchReprocessingError("所选资料中存在已变化的当前版本，请刷新后重新选择。")
            if pending_reprocessing_conflict(session, snapshot_id=member["snapshot_id"],
                                             batch_job_id=None) is not None:
                raise BatchReprocessingError("所选资料中已有正在进行的重新识别，请待其结束后再发起批量。")
        return result


def _member_namespace(batch_id, member):
    return canonical_hash({"contract": REPROCESS_CONTRACT, "batch_job_id": batch_id, **member})


def _create_member_child(session_factory, adapter, *, batch_job_id, member_index):
    """原子创建一个批量成员子任务：同一 BEGIN IMMEDIATE 内复核父批次取消
    请求、成员归属、识别方式与原件当前状态，再落库。"""
    with session_factory() as session:
        session.execute(text("BEGIN IMMEDIATE"))
        try:
            row, payload = material(session, batch_job_id)
            if row.cancel_requested or row.state not in {"queued", "running"}:
                raise BatchReprocessingError("批量识别已停止或已结束，未继续创建新的识别任务。")
            if not 0 <= member_index < len(payload["members"]):
                raise ScopeViolationError("批量识别步骤与所选资料不一致")
            member = payload["members"][member_index]
            result = create_reprocessing_child_in_session(session_factory, adapter, session,
                project_id=payload["project_id"], subject_id=member["subject_id"],
                review_episode_id=member["review_episode_id"],
                snapshot_id=member["snapshot_id"], complete_id=member["complete_id"],
                attempt_namespace=_member_namespace(batch_job_id, member),
                batch_job_id=batch_job_id, expected_profile_sha256=payload["profile_sha256"],
                preparation_policy=payload.get("preparation_policy"))
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise


def cancel_batch_children(session_factory, batch_id):
    with session_factory() as session, session.begin():
        row = JobStore(session).get_job(batch_id)
        if row.job_type != BATCH_JOB_TYPE:
            return False
        if not row.cancel_requested:
            return True
        _, payload = material(session, batch_id)
        cancel_owned(session, batch_id, payload)
        return True


def change_reprocessing_batch(session_factory, adapter, *, project_id, batch_id, operation):
    with session_factory() as session, session.begin():
        row, payload = material(session, batch_id)
        if payload["project_id"] != project_id:
            raise ScopeViolationError("这批识别不属于所选研究项目")
        store = JobStore(session)
        if operation == "cancel":
            result = store.request_cancel(batch_id)
            cancel_owned(session, batch_id, payload)
            return result
        if operation != "retry" or row.cancel_requested:
            raise ScopeViolationError("已停止的批量识别不能重试，请重新发起新的批量识别")
        if payload["profile_sha256"] != adapter.profile_fingerprint:
            raise ScopeViolationError("识别方式已改变，不能混用新旧设置继续本批识别")
        return store.retry_failed(batch_id)


class BatchReprocessingRetryService:
    def __init__(self, session_factory, adapter):
        self.session_factory = session_factory
        self.adapter = adapter

    def retry(self, batch_id):
        with self.session_factory() as session:
            _, payload = material(session, batch_id)
        return change_reprocessing_batch(self.session_factory, self.adapter,
            project_id=payload["project_id"], batch_id=batch_id, operation="retry")


class BatchReprocessingContinuation:
    def __init__(self, session_factory, adapter, *, worker_id):
        self.session_factory = session_factory
        self.adapter = adapter
        self.worker_id = worker_id

    def __call__(self, runner):
        recover_expired_jobs(self.session_factory, now=runner.now, job_scope=and_(
            JobRecord.job_type == BATCH_JOB_TYPE,
            func.json_extract(JobRecord.payload_json, "$.execution_owner") == OWNER,
        ))
        with self.session_factory() as session, session.begin():
            cancelled = list(session.scalars(select(JobRecord.job_id).where(
                JobRecord.job_type == BATCH_JOB_TYPE, JobRecord.cancel_requested.is_(True),
                func.json_extract(JobRecord.payload_json, "$.execution_owner") == OWNER,
            )))
            for batch_id in cancelled:
                try:
                    _, payload = material(session, batch_id)
                    cancel_owned(session, batch_id, payload)
                except (PersistedContractInvalid, ScopeViolationError):
                    logger.exception("批量识别记录无法核实，保留该记录并继续处理其他任务")
            batch_id = session.scalar(select(JobRecord.job_id).where(
                JobRecord.job_type == BATCH_JOB_TYPE, JobRecord.state == "queued",
                func.json_extract(JobRecord.payload_json, "$.execution_owner") == OWNER,
            ).order_by(JobRecord.updated_at, JobRecord.job_id).limit(1))
            if batch_id is None:
                return
            lease = JobStore(session, lease_ttl=runner.lease_ttl).claim_job(batch_id, self.worker_id)
        if lease is None:
            return
        with runner.lease_heartbeat(lease) as lease_ref:
            self._advance(lease_ref)

    def _advance(self, lease_ref):
        batch_id = lease_ref[0].job_id
        step_id = None
        member_index = None
        member = None
        try:
            with self.session_factory() as session:
                store = JobStore(session)
                row, payload = material(session, batch_id)
                step = store.next_runnable_step(batch_id)
                step_id = step.step_id if step else None
                if {item.step_id for item in store.list_steps(batch_id)} != {
                    f"member_{index}" for index in range(len(payload["members"]))
                }:
                    raise ScopeViolationError("批量识别步骤与所选资料不一致")
                if step_id is None:
                    raise ScopeViolationError("批量识别缺少可处理步骤")
                member_index = int(step_id.removeprefix("member_"))
                member = payload["members"][member_index]
                owned = owned_children(session, batch_id, payload)
                validate_completed_members(session, batch_id, payload, owned)
                existing = owned.get(member_index)
                child_id = existing[0].job_id if existing else None
            if child_id is None:
                child_id = _create_member_child(self.session_factory, self.adapter,
                    batch_job_id=batch_id, member_index=member_index).job_id
            with self.session_factory() as session, session.begin():
                store = JobStore(session)
                row, payload = material(session, batch_id)
                owned = owned_children(session, batch_id, payload)
                child_row = owned.get(member_index)
                if child_row is None or child_row[0].job_id != child_id:
                    raise ScopeViolationError("批量识别关联已变化")
                child = child_row[0]
                if row.cancel_requested:
                    store.cancel_at_boundary(lease_ref[0])
                    cancel_owned(session, batch_id, payload)
                elif child.state not in TERMINAL:
                    store.release_deferred(lease_ref[0])
                else:
                    store.start_step(lease_ref[0], step_id)
                    store.complete_step(lease_ref[0], step_id, checkpoint_payload={
                        "reprocess_job_id": child_id,
                        "snapshot_id": member["snapshot_id"],
                        "complete_id": member["complete_id"],
                        "member_state": child.state, "activated": False,
                    })
                    if all(item.state == "completed" for item in store.list_steps(batch_id)):
                        store.finish_success(lease_ref[0])
                    else:
                        store.release_deferred(lease_ref[0])
        except LeaseLostError:
            logger.info("批量识别衔接租约已释放，保留记录等待恢复", exc_info=True)
        except Exception as exc:
            logger.exception("批量识别衔接未完成")
            with self.session_factory() as session, session.begin():
                store = JobStore(session)
                if store.get_job(batch_id).cancel_requested:
                    store.cancel_at_boundary(lease_ref[0])
                    _, payload = material(session, batch_id)
                    cancel_owned(session, batch_id, payload)
                elif is_database_busy_error(exc):
                    store.release_deferred(lease_ref[0])
                elif step_id is not None:
                    store.start_step(lease_ref[0], step_id)
                    store.fail_step(lease_ref[0], step_id, retryable=False,
                        error_code=CONTINUATION_FAILED_CODE,
                        detail=str(exc) if isinstance(exc, (ScopeViolationError, ReprocessingError))
                        else "批量识别暂未完成，已保留先前记录")
                else:
                    store.finish_failure(lease_ref[0])
