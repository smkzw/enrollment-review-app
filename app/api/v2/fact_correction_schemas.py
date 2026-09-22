"""人工事实修订 HTTP 契约（薄 DTO，无存储）。"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.contracts.enums import DatePrecision
from app.domain.contracts.fact_corrections import FactCorrectionImpactScope, FactCorrectionV2
from app.domain.planning.fact_correction_impact import NODE_RECOMPUTE_MESSAGE
from app.services.fact_correction_service import FactCorrectionPreview

SCOPE_KIND_LABELS = {
    "local": "仅重新整理受影响信息",
    "node": NODE_RECOMPUTE_MESSAGE,
}

TARGET_KIND_LABELS = {
    "fact": "事实记录",
    "event": "事件记录",
    "exposure": "用药或治疗暴露",
}


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FactCorrectionDateRangeRequest(_StrictModel):
    source_text: str | None
    precision: DatePrecision | None
    lower_bound: date | None
    upper_bound: date | None


class FactCorrectionRequest(_StrictModel):
    target_kind: Literal["fact", "event", "exposure"]
    target_id: str = Field(min_length=1)
    locator_ids: list[str] = Field(min_length=1)
    reason: str | None = None
    operator_id: str | None = None
    fact_type: str | None = None
    supported_requirement_ids: list[str] | None = None
    polarity: str | None = None
    asserted_object: str | None = None
    value: Any | None = None
    unit: str | None = None
    date_range: FactCorrectionDateRangeRequest | None = None
    profile_lane: str | None = None
    event_type: str | None = None
    start_range: FactCorrectionDateRangeRequest | None = None
    end_range: FactCorrectionDateRangeRequest | None = None
    duration_status: str | None = None
    fact_ids: list[str] | None = None
    medication_name: str | None = None
    category: str | None = None
    indication: str | None = None
    dose: str | None = None
    frequency: str | None = None
    route: str | None = None


class FactCorrectionImpactDTO(_StrictModel):
    scope_kind: str
    scope_kind_label: str
    fallback_reason: str | None = None
    affected_locator_ids: list[str] = Field(default_factory=list)
    affected_document_ids: list[str] = Field(default_factory=list)
    affected_fact_ids: list[str] = Field(default_factory=list)
    affected_event_ids: list[str] = Field(default_factory=list)
    affected_exposure_ids: list[str] = Field(default_factory=list)
    affected_conflict_group_ids: list[str] = Field(default_factory=list)
    affected_rule_link_ids: list[str] = Field(default_factory=list)
    affected_expectation_ids: list[str] = Field(default_factory=list)
    affected_profile_revision_ids: list[str] = Field(default_factory=list)


class FactCorrectionSiblingDTO(_StrictModel):
    fact_id: str = Field(min_length=1)
    fact_type: str = Field(min_length=1)
    polarity: str = Field(min_length=1)
    value: Any = None
    unit: str | None = None


class FactCorrectionPreviewDTO(_StrictModel):
    target_kind: str
    target_kind_label: str
    target_id: str
    locator_ids: list[str]
    old_snapshot: dict[str, Any]
    new_snapshot: dict[str, Any]
    impact: FactCorrectionImpactDTO
    sibling_facts: list[FactCorrectionSiblingDTO] = Field(default_factory=list)


class FactCorrectionSubmitDTO(_StrictModel):
    job_id: str
    correction_id: str
    created: bool
    state: str
    state_label: str
    recovery_action: str


class FactCorrectionRecordDTO(_StrictModel):
    correction_id: str
    target_kind: str
    target_kind_label: str
    target_id: str
    new_entity_id: str
    patient_profile_revision_id: str
    patient_profile_revision: int = Field(ge=1)
    reason: str
    operator_id: str
    locator_ids: list[str]
    corrected_at: datetime
    old_snapshot: dict[str, Any]
    new_snapshot: dict[str, Any]
    impact: FactCorrectionImpactDTO


class FactCorrectionHistoryDTO(_StrictModel):
    subject_id: str
    review_episode_id: str
    items: list[FactCorrectionRecordDTO]


def request_updates(body: FactCorrectionRequest) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True, mode="json")
    for key in ("target_kind", "target_id", "locator_ids", "reason", "operator_id"):
        payload.pop(key, None)
    return payload


def impact_dto(scope: FactCorrectionImpactScope) -> FactCorrectionImpactDTO:
    return FactCorrectionImpactDTO(
        scope_kind=scope.scope_kind,
        scope_kind_label=SCOPE_KIND_LABELS.get(scope.scope_kind, scope.scope_kind),
        fallback_reason=scope.fallback_reason,
        affected_locator_ids=list(scope.affected_locator_ids),
        affected_document_ids=list(scope.affected_document_ids),
        affected_fact_ids=list(scope.affected_fact_ids),
        affected_event_ids=list(scope.affected_event_ids),
        affected_exposure_ids=list(scope.affected_exposure_ids),
        affected_conflict_group_ids=list(scope.affected_conflict_group_ids),
        affected_rule_link_ids=list(scope.affected_rule_link_ids),
        affected_expectation_ids=list(scope.affected_expectation_ids),
        affected_profile_revision_ids=list(scope.affected_profile_revision_ids),
    )


def preview_dto(preview: FactCorrectionPreview) -> FactCorrectionPreviewDTO:
    return FactCorrectionPreviewDTO(
        target_kind=preview.target_kind,
        target_kind_label=TARGET_KIND_LABELS.get(preview.target_kind, preview.target_kind),
        target_id=preview.target_id,
        locator_ids=list(preview.locator_ids),
        old_snapshot=preview.old_snapshot,
        new_snapshot=preview.new_snapshot,
        impact=impact_dto(preview.impact_scope),
        sibling_facts=[
            FactCorrectionSiblingDTO.model_validate(s) for s in preview.sibling_facts
        ],
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def correction_dto(
    contract: FactCorrectionV2,
    *,
    patient_profile_revision_id: str,
    patient_profile_revision: int,
) -> FactCorrectionRecordDTO:
    return FactCorrectionRecordDTO(
        correction_id=contract.correction_id,
        target_kind=contract.target_kind,
        target_kind_label=TARGET_KIND_LABELS.get(contract.target_kind, contract.target_kind),
        target_id=contract.target_id,
        new_entity_id=contract.new_entity_id,
        patient_profile_revision_id=patient_profile_revision_id,
        patient_profile_revision=patient_profile_revision,
        reason=contract.reason,
        operator_id=contract.operator_id,
        locator_ids=list(contract.locator_ids),
        corrected_at=_as_utc(contract.corrected_at),
        old_snapshot=dict(json.loads(contract.old_snapshot_json)),
        new_snapshot=dict(json.loads(contract.new_snapshot_json)),
        impact=impact_dto(contract.impact_scope),
    )
