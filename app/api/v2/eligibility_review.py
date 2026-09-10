"""入排审核只读投影 API。

路由只做受试者/审核节点作用域核对、会话边界和 DTO 协议转换；条款装配与
确定性求值全部由 ``EligibilityReviewProjectionService`` 完成。
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.services.evidence_app_errors import translate_storage_error
from app.services.eligibility_review_projection import (
    EligibilityReviewProjection,
    EligibilityReviewProjectionService,
)

router = APIRouter(prefix="/api/v2", tags=["v2-eligibility-review"])


class EligibilityFactRefDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str = Field(min_length=1)
    locator_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)


class EligibilityClauseDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_code: str = Field(pattern=r"^(IN|EX|REQ)-\d{2}$")
    rule_kind: Literal["inclusion", "exclusion", "required_procedure"]
    text_summary: str = Field(min_length=1)
    parent_rule_code: str | None = Field(default=None, pattern=r"^(IN|EX|REQ)-\d{2}$")
    decision: Literal[
        "inclusion_met",
        "inclusion_not_met",
        "requirement_met",
        "requirement_not_met",
        "exclusion_triggered",
        "exclusion_not_triggered",
        "professional_judgment",
        "conflict",
        "not_due",
        "not_applicable",
    ]
    decision_label: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    fact_refs: list[EligibilityFactRefDTO] = Field(default_factory=list)
    gap_type: str | None = Field(default=None, min_length=1)
    determination_mode: Literal[
        "deterministic", "semantic", "investigator_judgment"
    ]


class EligibilityReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    evidence_snapshot_v2_id: str = Field(min_length=1)
    complete_processing_revision_id: str = Field(min_length=1)
    clauses: list[EligibilityClauseDTO] = Field(min_length=1)


def _read(request: Request):
    return request.app.state.evidence_api_read_service


def _service(request: Request) -> EligibilityReviewProjectionService:
    return request.app.state.eligibility_review_projection_service


def _raise_translated(exc: Exception) -> None:
    translated = translate_storage_error(exc)
    if translated is not None:
        raise translated from exc
    raise exc


@router.get(
    "/subjects/{subject_id}/review-episodes/{review_episode_id}/eligibility-review",
    response_model=EligibilityReviewResponse,
)
def get_eligibility_review(
    subject_id: str, review_episode_id: str, request: Request
) -> EligibilityReviewResponse:
    """读取当前活动资料下的入排条款投影；不启动正式 ReviewRun。"""
    _read(request).require_subject_episode(subject_id, review_episode_id)
    with request.app.state.session_factory() as session:
        try:
            projection: EligibilityReviewProjection = _service(request).project(
                session, review_episode_id
            )
        except Exception as exc:  # noqa: BLE001 - 读取边界统一翻译
            _raise_translated(exc)
            raise
    return EligibilityReviewResponse.model_validate(projection.to_dict())


__all__ = [
    "EligibilityClauseDTO",
    "EligibilityFactRefDTO",
    "EligibilityReviewResponse",
    "get_eligibility_review",
    "router",
]
