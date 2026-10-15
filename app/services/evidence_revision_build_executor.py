"""完整资料版本的持久后台任务执行器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.domain.contracts.enums import EvidenceProcessingCandidateStatus
from app.evidence.artifacts import ArtifactStore
from app.services.evidence_revision_workflow import (
    BuildNeedsAttentionError,
    BuildRetryableFailureError,
    EvidenceRevisionWorkflow,
)
from app.storage.evidence_locator_models import EvidenceProcessingCandidateRecord
from app.workflow.errors import StepAwaitingUser, StepFailure
from app.workflow.runner import StepContext, StepExecutor

EVIDENCE_REVISION_BUILD_JOB_TYPE = "evidence_revision_build"
EVIDENCE_REVISION_BUILD_STEP_ID = "build_revision"


@dataclass(frozen=True)
class EvidenceRevisionBuildExecutorConfig:
    session_factory: sessionmaker
    artifact_store: ArtifactStore


def create_evidence_revision_build_executor(
    config: EvidenceRevisionBuildExecutorConfig,
) -> StepExecutor:
    workflow = EvidenceRevisionWorkflow(
        config.session_factory, artifact_store=config.artifact_store
    )

    def execute(context: StepContext) -> dict[str, Any]:
        candidate_id = str(context.job_payload.get("candidate_id") or "")
        if not candidate_id:
            raise StepFailure(
                retryable=False,
                error_code="REVISION_BUILD_INPUT_INVALID",
                detail="资料版本任务缺少目标，请重新提交核对。",
            )
        existing = workflow.get_candidate(candidate_id)
        if existing.status in {
            EvidenceProcessingCandidateStatus.READY,
            EvidenceProcessingCandidateStatus.ACTIVE,
        }:
            return {
                "candidate_id": existing.candidate_id,
                "complete_revision_id": existing.complete_revision_id,
                "status": existing.status.value,
            }
        workflow.begin_attempt(candidate_id, actor="资料处理服务")
        try:
            candidate = workflow.run_build(candidate_id)
        except BuildNeedsAttentionError as exc:
            raise StepAwaitingUser(
                awaiting_user="evidence_review",
                checkpoint={
                    "candidate_id": candidate_id,
                    "status": "needs_attention",
                },
            ) from exc
        except BuildRetryableFailureError as exc:
            raise StepFailure(
                retryable=True,
                error_code="REVISION_BUILD_RETRYABLE",
                detail="资料版本暂未生成，系统将从已保存进度继续处理。",
            ) from exc
        return {
            "candidate_id": candidate.candidate_id,
            "complete_revision_id": candidate.complete_revision_id,
            "status": "ready",
        }

    return execute


def cancel_revision_candidate_for_job(
    session_factory: sessionmaker,
    job_id: str,
    artifact_store: ArtifactStore | None = None,
) -> None:
    """任务取消后把对应未完成候选收敛为取消态。"""
    with session_factory() as session:
        row = session.execute(
            select(EvidenceProcessingCandidateRecord).where(
                EvidenceProcessingCandidateRecord.job_id == job_id
            )
        ).scalars().first()
    if row is None:
        return
    workflow = EvidenceRevisionWorkflow(
        session_factory, artifact_store=artifact_store
    )
    with session_factory() as session:
        from app.storage.evidence_locator_repositories import (
            EvidenceProcessingCandidateRepository,
        )

        candidate = EvidenceProcessingCandidateRepository(
            session, artifact_store
        ).get(row.candidate_id)
    if candidate.status in {
        EvidenceProcessingCandidateStatus.STAGED,
        EvidenceProcessingCandidateStatus.PROCESSING,
        EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE,
        EvidenceProcessingCandidateStatus.NEEDS_ATTENTION,
    }:
        workflow.cancel(
            candidate.candidate_id,
            actor="资料处理服务",
            reason="用户取消资料版本任务",
        )
