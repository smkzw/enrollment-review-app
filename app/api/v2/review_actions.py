"""Documented manual handling, separate from clinical reassessment."""
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.services.evidence_app_errors import translate_storage_error
from app.services.review_action_command import record_action_response

router = APIRouter(prefix="/api/v2", tags=["v2-review-actions"])


class ActionResponseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    operation: Literal["close_manual", "reopen"]
    reason: str = Field(min_length=1)
    locator_ids: list[str] = Field(default_factory=list)
    response_snapshot_id: str | None = Field(default=None, min_length=1)
    response_processing_revision_id: str | None = Field(default=None, min_length=1)
    expected_episode_revision: int | None = Field(default=None, ge=1)
    idempotency_key: str = Field(min_length=1)


class ActionResponseDTO(BaseModel):
    action_id: str
    transition_id: str
    record_revision: int


@router.post("/subjects/{subject_id}/review-episodes/{review_episode_id}/actions/{action_id}/responses",
             response_model=ActionResponseDTO)
def save_response(subject_id: str, review_episode_id: str, action_id: str,
                  body: ActionResponseRequest, request: Request) -> ActionResponseDTO:
    try:
        with request.app.state.session_factory() as session, session.begin():
            result = record_action_response(session, subject_id=subject_id,
                review_episode_id=review_episode_id, action_id=action_id, **body.model_dump())
    except Exception as exc:
        translated = translate_storage_error(exc)
        if translated is not None:
            raise translated from exc
        raise
    return ActionResponseDTO(action_id=result.action_id, transition_id=result.transition_id,
        record_revision=result.record_revision)
