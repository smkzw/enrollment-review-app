from __future__ import annotations

from typing import Literal
from datetime import datetime

from pydantic import Field, model_validator

from .common import ContractModel, DateValue, ScalarValue, VersionedModel
from .enums import (
    ExpectationStatus,
    FactPolarity,
    GapType,
    LocatorPrecision,
    ProfileLane,
    ReviewStage,
    UploadMode,
)


class BoundingBox(ContractModel):
    x0: float = Field(ge=0)
    y0: float = Field(ge=0)
    x1: float = Field(gt=0)
    y1: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_bounds(self) -> "BoundingBox":
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("bbox 右下角必须大于左上角")
        return self


class EvidenceSpan(VersionedModel):
    evidence_span_id: str = Field(min_length=1)
    source_document_version_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    precision: LocatorPrecision
    bbox: BoundingBox | None = None
    text_start: int | None = Field(default=None, ge=0)
    text_end: int | None = Field(default=None, ge=0)
    excerpt: str | None = None
    locator_algorithm_version: str = Field(min_length=1)
    anchor_hash: str | None = None
    match_confidence: float | None = Field(default=None, ge=0, le=1)
    degradation_reason: str | None = None

    @model_validator(mode="after")
    def validate_locator(self) -> "EvidenceSpan":
        if self.precision == LocatorPrecision.BBOX and self.bbox is None:
            raise ValueError("bbox 定位必须提供坐标")
        if self.precision != LocatorPrecision.BBOX and self.bbox is not None:
            raise ValueError("非 bbox 定位不能携带坐标")
        if self.precision == LocatorPrecision.TEXT_RANGE:
            if self.text_start is None or self.text_end is None or self.text_end <= self.text_start:
                raise ValueError("text_range 必须提供有效字符范围")
        elif self.text_start is not None or self.text_end is not None:
            raise ValueError("非 text_range 定位不能携带字符范围")
        if self.precision == LocatorPrecision.PAGE_EXCERPT and not self.excerpt:
            raise ValueError("page_excerpt 必须提供页面摘录")
        if self.precision == LocatorPrecision.PAGE_ONLY and self.excerpt is not None:
            raise ValueError("page_only 不能携带伪精确页面摘录")
        if self.precision == LocatorPrecision.PAGE_ONLY and not self.degradation_reason:
            raise ValueError("page_only 必须说明定位降级原因")
        return self


class SourceDocumentVersion(VersionedModel):
    source_document_version_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_type: str = Field(min_length=1)
    source_party: str = Field(min_length=1)
    upload_mode: UploadMode
    review_stage: ReviewStage


class EvidenceSnapshot(VersionedModel):
    evidence_snapshot_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    source_document_version_ids: list[str] = Field(min_length=1)
    upload_mode: UploadMode
    prior_snapshot_id: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_upload_lineage(self) -> "EvidenceSnapshot":
        if self.upload_mode == UploadMode.INCREMENTAL and self.prior_snapshot_id is None:
            raise ValueError("增量快照必须引用前一 EvidenceSnapshot")
        if self.upload_mode == UploadMode.FULL and self.prior_snapshot_id is not None:
            raise ValueError("全量快照不能静默继承前一快照")
        return self


class EvidenceExpectation(VersionedModel):
    expectation_id: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    status: ExpectationStatus
    evidence_span_ids: list[str] = Field(default_factory=list)
    gap_type: GapType | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "EvidenceExpectation":
        if self.status in {ExpectationStatus.OBSERVED, ExpectationStatus.OBSERVED_WEAK}:
            if not self.evidence_span_ids:
                raise ValueError("已观察证据必须引用 EvidenceSpan")
        if self.status == ExpectationStatus.OBSERVED and self.gap_type not in {
            None,
            GapType.PROVENANCE_FOLLOWUP,
        }:
            raise ValueError("完整证据不能携带阻断缺口")
        if self.status == ExpectationStatus.OBSERVED_WEAK and self.gap_type not in {
            GapType.PROVENANCE_FOLLOWUP,
            GapType.OCR_OR_PARSE_RISK,
            GapType.HISTORICAL_SOURCE_UNAVAILABLE,
        }:
            raise ValueError("较弱证据必须说明溯源、解析或历史来源风险")
        if self.status == ExpectationStatus.NOT_DUE and self.gap_type != GapType.FUTURE_STAGE_NOT_DUE:
            raise ValueError("尚未到期必须使用 future_stage_not_due")
        if self.status == ExpectationStatus.ABSENT and self.gap_type not in {
            GapType.RECORD_INCOMPLETE,
            GapType.DESCRIPTION_INSUFFICIENT,
            GapType.REQUIRED_PROCEDURE_NOT_DONE,
            GapType.RESULT_FIELDS_MISSING,
            GapType.DATE_OR_ANCHOR_MISSING,
        }:
            raise ValueError("未观察到的到期证据必须使用具体当前缺口")
        if (
            self.status == ExpectationStatus.REFERENCED_MISSING
            and self.gap_type != GapType.REFERENCED_FILE_MISSING
        ):
            raise ValueError("已引用未提供必须使用 referenced_file_missing")
        return self


class ClinicalFact(VersionedModel):
    fact_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    fact_type: str = Field(min_length=1)
    value: ScalarValue | None = None
    unit: str | None = None
    polarity: FactPolarity
    certainty: float = Field(ge=0, le=1)
    effective_date: DateValue | None = None
    evidence_span_ids: list[str] = Field(min_length=1)
    conflict_group_id: str | None = None

    @model_validator(mode="after")
    def validate_polarity_value(self) -> "ClinicalFact":
        if self.polarity in {FactPolarity.AFFIRMED, FactPolarity.NEGATED} and self.value is None:
            raise ValueError("肯定或否定事实必须携带被断言的 typed value")
        if (
            isinstance(self.value, (int, float))
            and not isinstance(self.value, bool)
            and not self.unit
        ):
            raise ValueError("数值事实必须声明单位；无量纲值显式使用 unitless")
        return self


class PatientProfileEvent(VersionedModel):
    event_id: str = Field(min_length=1)
    lane: ProfileLane
    event_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    start_date: DateValue | None = None
    end_date: DateValue | None = None
    fact_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(min_length=1)
    related_rule_component_ids: list[str] = Field(default_factory=list)
    risk_labels: list[str] = Field(default_factory=list)
    is_abnormal: bool = False
    is_critical: bool = False
    has_trend_change: bool = False


class PatientProfile(VersionedModel):
    patient_profile_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    events: list[PatientProfileEvent]
    highlighted_event_ids: list[str] = Field(default_factory=list)
    missing_expectation_ids: list[str] = Field(default_factory=list)
    stale: bool = False


class ReferencedDocument(VersionedModel):
    referenced_document_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    referenced_by_evidence_span_id: str = Field(min_length=1)
    provided: bool = False


class ConflictGroup(VersionedModel):
    conflict_group_id: str = Field(min_length=1)
    fact_ids: list[str] = Field(min_length=2)
    affected_rule_component_ids: list[str] = Field(min_length=1)
    resolved: bool = False
    resolution_evidence_span_ids: list[str] = Field(default_factory=list)
