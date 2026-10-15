"""Explicit preparation attempts over immutable, already active source material."""
from dataclasses import replace
from typing import Literal

from pydantic import Field, model_serializer
from sqlalchemy import func, select, text

from app.domain.contracts.common import ContractModel
from app.domain.contracts.enums import SnapshotStatus
from app.domain.contracts.evidence_upload import DIRECT_VISION_PREPARATION
from app.domain.publication import canonical_hash
from app.evidence.ocr_adapter import TextOnlyOcrAdapter
from app.services.evidence_app_errors import EvidenceAppError, is_database_busy_error
from app.services.evidence_processing_executor import (
    EVIDENCE_PROCESSING_MAX_ATTEMPTS, create_evidence_processing_executor,
)
from app.services.job_service import CreateJobResult, JobService, StepSpec
from app.storage.codecs import PersistedContractInvalid, verify_payload_sha256
from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.models import JobRecord
from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository
from app.storage.repositories import EpisodeRepository
from app.workflow.runner import StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.states import TERMINAL_JOB_STATES

JOB_TYPE = "evidence_reprocess"
CONTRACT = "evidence-reprocess/v1"


class ReprocessingError(EvidenceAppError):
    status_code = 409
    code = "EVIDENCE_REPROCESS_REJECTED"
    title = "暂不能重新识别本次资料"
    recovery = "请刷新资料页面，核对当前资料和处理情况后再试。原件和原审核记录未改变。"


class ReprocessingInput(ContractModel):
    contract: Literal["evidence-reprocess/v1"] = CONTRACT
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    previous_complete_revision_id: str = Field(min_length=1)
    previous_base_revision_id: str = Field(min_length=1)
    collection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_namespace: str = Field(pattern=r"^[0-9a-f]{64}$")
    batch_job_id: str | None = Field(default=None, min_length=1)
    preparation_policy: Literal["original-page-images/v1"] | None = None

    @model_serializer(mode="wrap")
    def serialize_without_batch(self, handler):
        """单份提交载荷不含批量归属键，保持既有载荷哈希与幂等完全兼容。"""
        data = handler(self)
        if self.batch_job_id is None:
            data.pop("batch_job_id", None)
        if self.preparation_policy is None:
            data.pop("preparation_policy", None)
        return data


def _source(session, *, project_id, subject_id, review_episode_id, snapshot_id, complete_id):
    snapshot = EvidenceSnapshotRepository(session).get(snapshot_id)
    complete = CompleteEvidenceProcessingRevisionRepository(session).get(complete_id)
    base = EvidenceProcessingRevisionRepository(session).get(complete.base_processing_revision_id)
    for item in (snapshot, complete, base):
        if (item.project_id, item.subject_id, item.review_episode_id) != (project_id, subject_id, review_episode_id):
            raise ReprocessingError("所选资料不属于当前受试者和审核节点。")
    if complete.evidence_snapshot_id != snapshot_id or base.evidence_snapshot_id != snapshot_id:
        raise ReprocessingError("原识别版本与所选原件不一致。")
    return snapshot, complete, base


def pending_reprocessing_conflict(session, *, snapshot_id, batch_job_id):
    """返回与给定归属冲突的进行中识别任务；无冲突返回 None。

    ``batch_job_id=None``（单份提交）与任何进行中任务冲突；批量成员只与
    不属于本批的任务冲突，绝不占用或取消独立提交的任务。载荷无法核实的
    进行中任务按冲突处理，不默认其为本批成员。
    """
    pending = session.scalars(select(JobRecord).where(
        JobRecord.job_type == JOB_TYPE,
        JobRecord.state.not_in(TERMINAL_JOB_STATES),
        func.json_extract(JobRecord.payload_json, "$.snapshot_id") == snapshot_id,
    )).all()
    for row in pending:
        if batch_job_id is None:
            return row
        try:
            source = verify_payload_sha256(row.payload_json, row.payload_sha256)
        except PersistedContractInvalid:
            return row
        if source.get("batch_job_id") != batch_job_id:
            return row
    return None


def create_reprocessing_child_in_session(session_factory, adapter, session, *, project_id,
                                         subject_id, review_episode_id, snapshot_id,
                                         complete_id, attempt_namespace,
                                         batch_job_id=None, expected_profile_sha256=None,
                                         preparation_policy=DIRECT_VISION_PREPARATION):
    """在调用方 ``BEGIN IMMEDIATE`` 事务内创建（或复用）一个重新识别任务。

    单份提交与批量成员共用同一条创建链：核对原件归属、当前资料指针与识别
    设置后落库。``batch_job_id`` 标记批量归属并写入子任务载荷；批量路径另传
    ``expected_profile_sha256``（父批次冻结的识别方式），仅在需要新建子任务时
    与当前适配器比对，已存在的子任务不受轮询期间识别方式变化影响。调用方
    负责提交或回滚。
    """
    snapshot, _, base = _source(session, project_id=project_id, subject_id=subject_id,
        review_episode_id=review_episode_id, snapshot_id=snapshot_id, complete_id=complete_id)
    payload = ReprocessingInput(
        project_id=project_id, subject_id=subject_id, review_episode_id=review_episode_id,
        snapshot_id=snapshot_id, previous_complete_revision_id=complete_id,
        previous_base_revision_id=base.evidence_processing_revision_id,
        collection_sha256=snapshot.collection_sha256, previous_manifest_sha256=base.manifest_sha256,
        profile_sha256=(expected_profile_sha256 if expected_profile_sha256 is not None
                        else adapter.profile_fingerprint),
        attempt_namespace=attempt_namespace, batch_job_id=batch_job_id,
        preparation_policy=preparation_policy,
    ).model_dump(mode="json")
    existing = session.scalars(select(JobRecord).where(
        JobRecord.job_type == JOB_TYPE,
        func.json_extract(JobRecord.payload_json, "$.attempt_namespace") == attempt_namespace,
    )).all()
    if existing:
        if len(existing) != 1 or verify_payload_sha256(existing[0].payload_json, existing[0].payload_sha256) != payload:
            raise ReprocessingError("这次操作已关联其他资料或识别设置，请重新发起。")
        return CreateJobResult(existing[0].job_id, existing[0].state, False)
    if (expected_profile_sha256 is not None
            and adapter.profile_fingerprint != expected_profile_sha256):
        raise ReprocessingError("识别方式已改变，不能按原批量设置继续识别未处理的资料。")
    episode = EpisodeRepository(session).get(review_episode_id)
    if (episode.active_evidence_snapshot_id != snapshot_id
            or episode.active_evidence_processing_revision_id != complete_id
            or EvidenceSnapshotRepository(session).current_status(snapshot_id) != SnapshotStatus.ACTIVE):
        raise ReprocessingError("当前资料版本已变化，请刷新后重新选择。")
    if pending_reprocessing_conflict(session, snapshot_id=snapshot_id, batch_job_id=batch_job_id) is not None:
        if batch_job_id is None:
            raise ReprocessingError("这份资料正在重新识别，请先查看已有处理记录。")
        raise ReprocessingError("这份资料已有其他识别任务正在进行，本批未继续该成员，已保留先前记录。")
    return JobService(session_factory).create_job_in_session(session,
        idempotency_key=f"{CONTRACT}:{attempt_namespace}", job_type=JOB_TYPE, payload=payload,
        steps=[StepSpec("evidence_processing", "重新识别原件",
            max_attempts=EVIDENCE_PROCESSING_MAX_ATTEMPTS, retryable=True)])


def enqueue_reprocessing(session_factory, adapter, *, project_id, subject_id,
                         review_episode_id, snapshot_id, complete_id, request_key):
    if not isinstance(request_key, str) or not request_key.strip():
        raise ReprocessingError("本次操作信息不完整，请重新打开资料页面。")
    namespace = canonical_hash({"contract": CONTRACT, "project_id": project_id, "request_key": request_key})
    with session_factory() as session:
        session.execute(text("BEGIN IMMEDIATE"))
        try:
            result = create_reprocessing_child_in_session(session_factory, adapter, session,
                project_id=project_id, subject_id=subject_id, review_episode_id=review_episode_id,
                snapshot_id=snapshot_id, complete_id=complete_id, attempt_namespace=namespace)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise


def create_reprocessing_executor(config):
    original = config.adapter or TextOnlyOcrAdapter()

    def execute(context):
        try:
            data = ReprocessingInput.model_validate(context.job_payload)
            if context.job_type != JOB_TYPE or data.profile_sha256 != original.profile_fingerprint:
                raise ReprocessingError("识别方式已改变，不能混用设置继续处理。")
            with config.session_factory() as session:
                snapshot, _, base = _source(session, project_id=data.project_id, subject_id=data.subject_id,
                    review_episode_id=data.review_episode_id, snapshot_id=data.snapshot_id,
                    complete_id=data.previous_complete_revision_id)
                if (snapshot.collection_sha256 != data.collection_sha256
                        or base.evidence_processing_revision_id != data.previous_base_revision_id
                        or base.manifest_sha256 != data.previous_manifest_sha256):
                    raise ReprocessingError("本次处理记录不能与原件核对，已保留原识别结果。")
        except Exception as exc:
            if is_database_busy_error(exc):
                raise StepFailure(retryable=True, error_code="EVIDENCE_REPROCESS_DATABASE_BUSY",
                    detail="资料暂时正在保存，稍后将重新核对。原资料和报告未改变。") from exc
            raise StepFailure(retryable=False, error_code="EVIDENCE_REPROCESS_SOURCE_INVALID",
                detail="原件关联或识别方式无法核对，本次未继续识别。原资料和报告已保留。") from exc
        executor = create_evidence_processing_executor(replace(config,
            adapter=original.for_attempt(data.attempt_namespace), manage_snapshot_status=False))
        result = executor(context)
        return {**result, "reprocessing_contract": CONTRACT,
            "previous_complete_revision_id": data.previous_complete_revision_id,
            "attempt_namespace": data.attempt_namespace, "activated": False}

    return execute


def reprocessing_view(session, *, project_id, job_id):
    store = JobStore(session)
    row = store.get_job(job_id)
    data = ReprocessingInput.model_validate(verify_payload_sha256(row.payload_json, row.payload_sha256))
    if row.job_type != JOB_TYPE or data.project_id != project_id:
        raise ReprocessingError("这次识别不属于当前研究项目。")
    _source(session, project_id=data.project_id, subject_id=data.subject_id,
        review_episode_id=data.review_episode_id, snapshot_id=data.snapshot_id,
        complete_id=data.previous_complete_revision_id)
    revision_id = None
    checkpoint = store.get_last_checkpoint(job_id, "evidence_processing")
    if row.state == "completed":
        if (checkpoint is None or checkpoint[1].get("attempt_namespace") != data.attempt_namespace
                or checkpoint[1].get("reprocessing_contract") != CONTRACT
                or checkpoint[1].get("activated") is not False):
            raise ReprocessingError("识别完成记录不完整，请保留原资料并联系维护人员。")
        revision_id = checkpoint[1].get("revision_id")
        if not isinstance(revision_id, str) or not revision_id:
            raise ReprocessingError("未能找到本次识别结果。")
        revision = EvidenceProcessingRevisionRepository(session).get(revision_id)
        if (revision.evidence_snapshot_id, revision.project_id, revision.subject_id, revision.review_episode_id) != (
                data.snapshot_id, data.project_id, data.subject_id, data.review_episode_id):
            raise ReprocessingError("识别结果与所选原件不一致。")
    return {"job_id": job_id, "project_id": project_id, "subject_id": data.subject_id,
        "review_episode_id": data.review_episode_id, "snapshot_id": data.snapshot_id,
        "previous_complete_revision_id": data.previous_complete_revision_id,
        "state": row.state, "revision_id": revision_id,
        "new_revision": revision_id is not None and revision_id != data.previous_base_revision_id}


class ReprocessingRetryService:
    def __init__(self, session_factory, adapter):
        self.session_factory = session_factory
        self.adapter = adapter

    def retry(self, job_id):
        with self.session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            try:
                row = JobStore(session).get_job(job_id)
                data = ReprocessingInput.model_validate(verify_payload_sha256(row.payload_json, row.payload_sha256))
                if row.job_type != JOB_TYPE or data.profile_sha256 != self.adapter.profile_fingerprint:
                    raise ReprocessingError("识别方式已改变，请重新发起识别。")
                if data.batch_job_id is not None and JobStore(session).get_job(data.batch_job_id).cancel_requested:
                    raise ReprocessingError("这批识别已停止；如需再次识别，请单独重新发起。")
                episode = EpisodeRepository(session).get(data.review_episode_id)
                if (episode.active_evidence_snapshot_id != data.snapshot_id
                        or episode.active_evidence_processing_revision_id != data.previous_complete_revision_id):
                    raise ReprocessingError("当前资料已更新，请刷新后重新选择需要识别的资料。")
                others = session.scalars(select(JobRecord).where(
                    JobRecord.job_type == JOB_TYPE, JobRecord.job_id != job_id,
                    JobRecord.state.not_in(TERMINAL_JOB_STATES),
                    func.json_extract(JobRecord.payload_json, "$.snapshot_id") == data.snapshot_id,
                )).all()
                if others:
                    raise ReprocessingError("这份资料已有其他识别正在进行，暂未重试。")
                result = JobStore(session).retry_failed(job_id)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise
