"""只读读取补充审核要求作业的状态与可随方案发布的检查点。

本模块读取已持久化的 Job/步骤/检查点及定义核对原答工件：不调用模型、
不读取原始方案文件、不运行执行器、不写入任何记录、不做状态迁移。

只有同时满足以下条件才给出"可发布检查点"与候选数量：作业已完成、没有被
取消、发布门禁步骤已完成，且该步骤最终检查点的原样摘要、执行版本、门禁
版本、结果种类、接受标记、覆盖清单身份与候选身份闭包全部核对通过。其余
情况一律不给出检查点，也绝不猜测数量；已完成却无法核对的记录按既有应用
错误约定拒绝，不能显示成"已就绪"。

候选包只是"随方案发布"的输入：它不是已发布的正式控制目录，也不构成任何
临床批准或入排结论。
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.protocol_controls import (
    ProtocolControlBatchDispositionHydrated,
    ProtocolControlBatchPlan,
    ProtocolControlCandidate,
    ProtocolSectionCoverageManifest,
    RestrictedProtocolControlStatement,
)
from app.domain.contracts.rules import RuleSet, WorkflowStage
from app.protocols.protocol_control_gate import CONTROL_PUBLICATION_GATE_VERSION
from app.services.protocol_control_catalog_publication import (
    SourceCalculationGap, _verified_calculation_release, source_calculation_gaps,
    require_saved_definition_scope,
)
from app.services.evidence_app_errors import (
    AppNotFoundError,
    EvidenceAppError,
    app_error_boundary,
)
from app.services.protocol_control_executor import (
    CANDIDATE_CONTROL_PACKAGE_RESULT_KIND,
    FORMAL_CATALOG_STATUS_NOT_MATERIALIZED,
    PROTOCOL_CONTROL_EXECUTION_VERSION,
    PROTOCOL_CONTROL_JOB_TYPE,
    STEP_GATE,
)
from app.storage.codecs import verify_payload_sha256
from app.storage.models import JobCheckpointRecord, JobStepRecord
from app.storage.repositories import ProtocolDraftRevisionRepository, RepositoryError, ScopeViolationError
from app.workflow.errors import JobNotFoundError
from app.workflow.jobstore import JobStore
from app.workflow.states import TERMINAL_JOB_STATES

#: 面向用户的整理状态中文说明；只描述能否随方案发布，绝不表述临床结论。
PROTOCOL_CONTROL_STATUS_LABELS = {
    "candidate_ready": "补充审核要求已整理，仍需核对发布条件",
    "processing": "正在整理补充审核要求",
    "stopped": "补充审核要求整理未完成",
}

_STOPPED_REASON_LABELS = {
    "PROTOCOL_CONTROL_SOURCE_TARGET_REVIEW_UNRESOLVED":
        "原文已保存，仍需核清它与审核要求的对应关系",
    "PROTOCOL_CONTROL_SOURCE_REQUIREMENT_CONSUMER_UNAVAILABLE":
        "原文支持的补充要求尚未接通可靠核验，由系统建设继续处理",
    "PROTOCOL_CONTROL_SOURCE_REQUIREMENT_INSERTION_LIMIT_REACHED":
        "本次补充要求修订尚未完成，已核清的部分仍保留",
    "PROTOCOL_CONTROL_SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED":
        "已找到原文，仍需核实整理出的要求是否忠实表达其含义",
    "PROTOCOL_CONTROL_DEFINITION_SCOPE_INVALID":
        "定义影响哪些要求尚未核清，已保存原文和本次核对记录",
    "PROTOCOL_CONTROL_DEFINITION_SCOPE_TRANSPORT_FAILED":
        "定义影响范围的读取连接中断，已完成内容保留，可按原范围重试",
    "PROTOCOL_CONTROL_DEFINITION_SCOPE_COMPLETION_UNCERTAIN":
        "本次读取连接中断，尚不能确认是否完成，不会立即重复发送",
    "PROTOCOL_CONTROL_LOGICAL_BUDGET_EXHAUSTED":
        "本次读取已达到约定次数，已有内容保留，尚未完成的部分仍需处理",
    "PROTOCOL_CONTROL_BUDGET_RECORD_INVALID":
        "读取范围已变化或原调用记录不完整，未继续发送；原结果保留，需重新建立整理任务",
    "PROTOCOL_CONTROL_BUDGET_INVALID":
        "本次整理缺少有效的读取次数约定，尚未发送请求",
    "PROTOCOL_CONTROL_BUDGET_UNSUPPORTED":
        "当前读取服务无法遵守约定次数，尚未发送请求",
    "PROTOCOL_CONTROL_DEFINITION_SCOPE_UNAVAILABLE":
        "当前读取服务无法核对定义的影响范围，已完成内容保留",
    "PROTOCOL_CONTROL_CHECKPOINT_MISSING":
        "前一步保存的内容缺失，未继续整理，需先恢复原记录",
    "PROTOCOL_CONTROL_CHECKPOINT_INVALID":
        "已保存内容与当前原文或核对依据不一致，未继续采用，原记录保留",
}

_JOB_NOT_FOUND_DETAIL = (
    "找不到对应的补充审核要求任务，可能任务编号有误，或该任务不属于补充审核要求。"
)


class ProtocolControlCheckpointInvalidError(EvidenceAppError):
    """作业声称已完成，但它保存的候选包无法用当前冻结合同核对通过。"""

    status_code = 409
    code = "PROTOCOL_CONTROL_CHECKPOINT_INVALID"
    title = "补充审核要求的整理结果不可用于发布"
    recovery = "请返回方案整理查看处理情况；已经保存的任务记录不会因此被覆盖。"

    def __init__(self) -> None:
        super().__init__("这次整理保存的结果没有通过完整性核对，系统不会把它当作发布依据。")


@dataclass(frozen=True)
class ProtocolControlExecutionStatus:
    """一次只读读取的结果；只有 ``candidate_ready`` 才带可发布检查点。"""

    job_id: str
    state: str
    source_job_id: str
    status: str
    status_label: str
    publishable_checkpoint_id: str | None
    candidate_count: int | None


@dataclass(frozen=True)
class ProtocolControlRequirementsView:
    job_id: str
    source_job_id: str
    checkpoint_id: str
    candidates: tuple[ProtocolControlCandidate, ...]
    workflow_stages: tuple[WorkflowStage, ...]
    relation_target_labels: Mapping[str, str]
    calculation_gaps: tuple[SourceCalculationGap, ...]
    restricted_statements: tuple[RestrictedProtocolControlStatement, ...]


@app_error_boundary
def protocol_control_requirements(
    session_factory: sessionmaker[Session], *, job_id: str,
) -> ProtocolControlRequirementsView:
    """Return the exact completed candidate version for pre-publication review."""
    status = protocol_control_execution_status(session_factory, job_id=job_id)
    if status.publishable_checkpoint_id is None:
        raise ProtocolControlCheckpointInvalidError()
    with session_factory() as session:
        job = JobStore(session).get_job(job_id)
        if job.state != "completed" or job.cancel_requested:
            raise ProtocolControlCheckpointInvalidError()
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        checkpoint_id, _ = _verified_candidate_package(session, job_id=job_id, payload=payload)
        if checkpoint_id != status.publishable_checkpoint_id:
            raise ProtocolControlCheckpointInvalidError()
        row = session.get(JobCheckpointRecord, checkpoint_id)
        if row is None or payload.get("source_deconstruction_job_id") != status.source_job_id:
            raise ProtocolControlCheckpointInvalidError()
        checkpoint = verify_payload_sha256(row.payload_json, row.payload_sha256)
        plan, batches = _validated_batch_results(checkpoint)
        manifest = ProtocolSectionCoverageManifest.model_validate(payload.get("coverage_manifest"))
        source_order = {item.structure_unit_id: item.source_order for item in manifest.units}
        all_candidates = [candidate for batch in batches for candidate in batch.candidates]
        if any(not set(item.frozen_structure_unit_ids).issubset(source_order) for item in all_candidates):
            raise ProtocolControlCheckpointInvalidError()
        candidates = tuple(sorted(
            all_candidates,
            key=lambda item: (min(source_order[key] for key in item.frozen_structure_unit_ids),
                              item.control_candidate_id),
        ))
        restricted = [statement for batch in batches for statement in batch.restricted_statements]
        restricted_ids = [item.restricted_statement_id for item in restricted]
        units_by_id = {unit.structure_unit_id: unit for unit in manifest.units}
        if (len(restricted_ids) != len(set(restricted_ids))
                or any(item.source_structure_unit_id not in source_order for item in restricted)
                or any(not set(item.dependency_refs).issubset(restricted_ids) for item in restricted)):
            raise ProtocolControlCheckpointInvalidError()
        for item in restricted:
            unit = units_by_id[item.source_structure_unit_id]
            if (item.source_span_ids != sorted(unit.source_span_ids)
                    or not any(item.source_quote in text
                               for text in [unit.excerpt, *unit.heading_path])):
                raise ProtocolControlCheckpointInvalidError()
        restricted_statements = tuple(sorted(
            restricted,
            key=lambda item: (source_order[item.source_structure_unit_id],
                              item.source_statement_index, item.restricted_statement_id),
        ))
        if any(item.semantics is None for item in candidates):
            raise ProtocolControlCheckpointInvalidError()
        workflow_stages = tuple(WorkflowStage.model_validate(item)
                                for item in payload.get("workflow_stages", []))
        target_labels = {
            f"control_candidate:{item.control_candidate_id}": item.title for item in candidates
        }
        target_labels.update({f"workflow_stage:{item.workflow_stage_id}": item.display_name
                              for item in workflow_stages})
        for batch in plan.batches:
            for target in batch.known_procedure_targets:
                key = f"required_procedure:{target.catalog_item_id}"
                value = f"{target.visit_instance}：{target.label}"
                if key in target_labels and target_labels[key] != value:
                    raise ProtocolControlCheckpointInvalidError()
                target_labels[key] = value
        calculation_gaps = source_calculation_gaps(JobStore(session), job_id)
        try:
            revision_id = payload.get("draft_revision_id")
            if not isinstance(revision_id, str) or not revision_id:
                raise ValueError("方案草稿修订身份缺失")
            revision = ProtocolDraftRevisionRepository(session).get(revision_id)
            if (revision.content_sha256 != payload.get("draft_content_sha256")
                    or revision.protocol_version_id != manifest.protocol_version_id
                    or revision.study_phase != manifest.study_phase):
                raise ValueError("方案草稿修订与补充审核要求不一致")
            rule_set = RuleSet(
                rule_set_id=f"preview:{revision.protocol_version_id}",
                protocol_version_id=revision.protocol_version_id,
                study_phase=revision.study_phase,
                rules=revision.content.proposed_rules,
                revision=1,
            )
            released = _verified_calculation_release(
                checkpoint, plan, batches, manifest, rule_set, calculation_gaps,
            )
        except (RepositoryError, ValidationError, ValueError, TypeError) as exc:
            raise ProtocolControlCheckpointInvalidError() from exc
        return ProtocolControlRequirementsView(
            job_id=job_id, source_job_id=status.source_job_id, checkpoint_id=checkpoint_id,
            candidates=candidates,
            workflow_stages=workflow_stages, relation_target_labels=target_labels,
            restricted_statements=restricted_statements,
            calculation_gaps=tuple(
                gap for gap in calculation_gaps
                if (gap.batch_number, gap.statement_index) not in released
            ),
        )


@app_error_boundary
def protocol_control_execution_status(
    session_factory: sessionmaker[Session],
    *,
    job_id: str,
) -> ProtocolControlExecutionStatus:
    """读取一个补充审核要求任务的状态；缺失或类型不符按既有 404 约定处理。"""

    with session_factory() as session:
        store = JobStore(session)
        try:
            job = store.get_job(job_id)
        except JobNotFoundError as exc:
            raise AppNotFoundError(_JOB_NOT_FOUND_DETAIL) from exc
        if job.job_type != PROTOCOL_CONTROL_JOB_TYPE:
            raise AppNotFoundError(_JOB_NOT_FOUND_DETAIL)
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        source_job_id = payload.get("source_deconstruction_job_id")
        if (
            payload.get("execution_version") != PROTOCOL_CONTROL_EXECUTION_VERSION
            or not isinstance(source_job_id, str)
            or not source_job_id
        ):
            # 冻结内容与当前执行合同不一致：任何状态都不能作为发布依据。
            raise ProtocolControlCheckpointInvalidError()

        checkpoint_id: str | None = None
        candidate_count: int | None = None
        if job.state == "completed" and not job.cancel_requested:
            checkpoint_id, candidate_count = _verified_candidate_package(
                session, job_id=job_id, payload=payload
            )
            status = "candidate_ready"
        else:
            if job.state == "completed":
                # 已完成却仍带未处理的停止请求：状态自相矛盾，不给出检查点。
                raise ProtocolControlCheckpointInvalidError()
            status = (
                "stopped"
                if job.state in TERMINAL_JOB_STATES or job.state == "waiting_user"
                else "processing"
            )
        return ProtocolControlExecutionStatus(
            job_id=job_id,
            state=job.state,
            source_job_id=source_job_id,
            status=status,
            status_label=(
                _STOPPED_REASON_LABELS.get(job.error_code, PROTOCOL_CONTROL_STATUS_LABELS[status])
                if status == "stopped" else PROTOCOL_CONTROL_STATUS_LABELS[status]
            ),
            publishable_checkpoint_id=checkpoint_id,
            candidate_count=candidate_count,
        )


def _verified_candidate_package(
    session: Session,
    *,
    job_id: str,
    payload: Mapping[str, Any],
) -> tuple[str, int]:
    """核对发布门禁检查点；任何一处不一致都拒绝，绝不降级成"未就绪"。"""

    step = session.get(JobStepRecord, (job_id, STEP_GATE))
    if step is None or step.state != "completed":
        raise ProtocolControlCheckpointInvalidError()
    found = JobStore(session).get_last_checkpoint(job_id, STEP_GATE)
    if found is None:
        raise ProtocolControlCheckpointInvalidError()
    checkpoint_id, checkpoint = found
    record = session.get(JobCheckpointRecord, checkpoint_id)
    if record is None or (record.job_id, record.step_id) != (job_id, STEP_GATE):
        raise ProtocolControlCheckpointInvalidError()

    manifest = payload.get("coverage_manifest")
    manifest_id = manifest.get("manifest_id") if isinstance(manifest, Mapping) else None
    if (
        not isinstance(manifest_id, str)
        or not manifest_id
        or checkpoint.get("stage") != "gate"
        or checkpoint.get("attempt") != step.attempt
        or checkpoint.get("accepted") is not True
        or checkpoint.get("gate_version") != CONTROL_PUBLICATION_GATE_VERSION
        or checkpoint.get("result_kind") != CANDIDATE_CONTROL_PACKAGE_RESULT_KIND
        or checkpoint.get("formal_catalog_status") != FORMAL_CATALOG_STATUS_NOT_MATERIALIZED
        or checkpoint.get("coverage_manifest_id") != manifest_id
    ):
        raise ProtocolControlCheckpointInvalidError()

    plan, dispositions = _validated_batch_results(checkpoint)
    if len(dispositions) != len(plan.batches) or {
        item.batch_id for item in dispositions
    } != {batch.batch_id for batch in plan.batches}:
        raise ProtocolControlCheckpointInvalidError()
    all_candidate_ids = [candidate.control_candidate_id
                         for item in dispositions for candidate in item.candidates]
    candidate_ids = sorted(set(all_candidate_ids))
    if (
        len(all_candidate_ids) != len(candidate_ids)
        or checkpoint.get("candidate_ids") != candidate_ids
        or checkpoint.get("publication_plan_id") != plan.plan_id
    ):
        raise ProtocolControlCheckpointInvalidError()
    try:
        require_saved_definition_scope(session, source_job_id=job_id, payload=payload, result=checkpoint)
    except (ScopeViolationError, ValidationError, ValueError, TypeError, KeyError) as exc:
        raise ProtocolControlCheckpointInvalidError() from exc
    return checkpoint_id, len(candidate_ids)


def _validated_batch_results(
    checkpoint: Mapping[str, Any],
) -> tuple[ProtocolControlBatchPlan, tuple[ProtocolControlBatchDispositionHydrated, ...]]:
    rows = checkpoint.get("batch_dispositions")
    if not isinstance(rows, list) or not rows:
        raise ProtocolControlCheckpointInvalidError()
    try:
        plan = ProtocolControlBatchPlan.model_validate(checkpoint.get("publication_plan"))
        dispositions = tuple(
            ProtocolControlBatchDispositionHydrated.model_validate(item) for item in rows
        )
    except (ValidationError, ValueError) as exc:
        raise ProtocolControlCheckpointInvalidError() from exc
    return plan, dispositions


__all__ = [
    "PROTOCOL_CONTROL_STATUS_LABELS",
    "ProtocolControlCheckpointInvalidError",
    "ProtocolControlExecutionStatus",
    "protocol_control_execution_status",
    "protocol_control_requirements",
    "ProtocolControlRequirementsView",
]
