"""人工事实修订执行器：规划检查点与租约写栅栏内的原子提交。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.fact_corrections import FactCorrectionImpactScope
from app.domain.planning.fact_correction_impact import FactReplacementSignature
from app.services.fact_correction_service import (
    FactCorrectionError,
    FactCorrectionStaleError,
    FactCorrectionValidationError,
    apply_prepared_fact_correction,
    plan_correction_impact,
    prepared_from_payload,
    prepared_to_payload,
)
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import PreparedStepResult, StepContext, StepExecutor

from .fact_correction_job_service import (
    FACT_CORRECTION_APPLY_STEP_ID,
    FACT_CORRECTION_PLAN_STEP_ID,
)

STALE_AUTHORITY_CODE = "STALE_AUTHORITY"
VALIDATION_CODE = "FACT_CORRECTION_INVALID"
APPLY_FAILED_CODE = "FACT_CORRECTION_APPLY_FAILED"


@dataclass(frozen=True)
class FactCorrectionExecutorConfig:
    session_factory: sessionmaker[Session]


def _prepared_from_context(context: StepContext):
    return prepared_from_payload(context.job_payload["prepared"])


def _scope_from_checkpoint(checkpoint: dict[str, Any] | None) -> FactCorrectionImpactScope | None:
    if not checkpoint:
        return None
    raw = checkpoint.get("impact_scope")
    if not isinstance(raw, dict):
        return None
    return FactCorrectionImpactScope.model_validate(raw)


def _plan_scope_for_apply(
    session_factory: sessionmaker[Session],
    context: StepContext,
) -> FactCorrectionImpactScope | None:
    """Apply 步骤的 last_checkpoint 只属于本步骤；首次执行必须读取 plan 检查点。"""
    planned = _scope_from_checkpoint(context.last_checkpoint)
    if planned is not None:
        return planned
    with session_factory() as session:
        plan_ckpt = JobStore(session).get_last_checkpoint(
            context.job_id, FACT_CORRECTION_PLAN_STEP_ID
        )
    if plan_ckpt is None:
        return None
    return _scope_from_checkpoint(plan_ckpt[1])


def create_fact_correction_executor(
    config: FactCorrectionExecutorConfig,
) -> StepExecutor:
    session_factory = config.session_factory

    def execute_plan(context: StepContext) -> dict[str, Any]:
        prepared = _prepared_from_context(context)
        replacement = None
        if prepared.replacement is not None:
            replacement = FactReplacementSignature(
                fact_type=prepared.replacement["fact_type"],
                supported_requirement_ids=tuple(
                    prepared.replacement["supported_requirement_ids"]
                ),
            )
        try:
            with session_factory() as session:
                scope = plan_correction_impact(
                    session,
                    authority=prepared.authority,
                    target_kind=prepared.target_kind,
                    target_id=prepared.target_id,
                    replacement=replacement,
                )
        except FactCorrectionStaleError as exc:
            raise StepFailure(
                retryable=False,
                error_code=STALE_AUTHORITY_CODE,
                detail=str(exc),
            ) from exc
        except FactCorrectionValidationError as exc:
            raise StepFailure(
                retryable=False,
                error_code=VALIDATION_CODE,
                detail=str(exc),
            ) from exc
        return {
            "correction_id": prepared.correction_id,
            "impact_scope": scope.model_dump(mode="json"),
            "prepared": prepared_to_payload(prepared),
        }

    def execute_apply(context: StepContext) -> PreparedStepResult:
        prepared = _prepared_from_context(context)
        planned_scope = _plan_scope_for_apply(session_factory, context)
        if planned_scope is None:
            planned_scope = _scope_from_checkpoint(execute_plan(context))

        checkpoint: dict[str, Any] = {
            "correction_id": prepared.correction_id,
            "new_entity_id": prepared.new_entity_id,
            "impact_scope": None
            if planned_scope is None
            else planned_scope.model_dump(mode="json"),
            "patient_profile_revision_id": None,
        }

        def apply(session: Session) -> None:
            try:
                result = apply_prepared_fact_correction(
                    session, prepared, impact_scope=planned_scope
                )
            except FactCorrectionStaleError as exc:
                raise StepFailure(
                    retryable=False,
                    error_code=STALE_AUTHORITY_CODE,
                    detail=str(exc),
                ) from exc
            except FactCorrectionValidationError as exc:
                raise StepFailure(
                    retryable=False,
                    error_code=VALIDATION_CODE,
                    detail=str(exc),
                ) from exc
            except FactCorrectionError as exc:
                raise StepFailure(
                    retryable=False,
                    error_code=APPLY_FAILED_CODE,
                    detail=str(exc),
                ) from exc
            checkpoint["impact_scope"] = result.impact_scope.model_dump(mode="json")
            checkpoint["new_entity_id"] = result.new_entity_id
            checkpoint["patient_profile_revision_id"] = result.profile_revision_id

        return PreparedStepResult(checkpoint=checkpoint, apply=apply)

    def execute(context: StepContext):
        if context.step_id == FACT_CORRECTION_PLAN_STEP_ID:
            return execute_plan(context)
        if context.step_id == FACT_CORRECTION_APPLY_STEP_ID:
            return execute_apply(context)
        raise StepFailure(
            retryable=False,
            error_code="UNKNOWN_STEP",
            detail="当前修订步骤无法识别。",
        )

    return execute
