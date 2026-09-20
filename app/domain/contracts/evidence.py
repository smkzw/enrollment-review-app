from __future__ import annotations

from typing import Literal
from datetime import datetime

from pydantic import ConfigDict, Field, model_serializer, model_validator

from .common import ContractModel, DateValue, ScalarValue, VersionedModel
from .rules import TimeQuantity, TimeConstraint
from .control_evidence_origin import ControlEvidenceOrigin
from .enums import (
    ExpectationStatus,
    FactPolarity,
    GapType,
    LocatorPrecision,
    ProfileLane,
    ReviewStage,
    StudyPhase,
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


class EvidenceExpectationTemplate(VersionedModel):
    """无受试者的资料核对期望模板投影（Phase 3 切片 4）。

    从已发布的 RuleSet/workflow 确定性投影，不含任何 subject/review-episode
    状态；``template_id`` 与 ``projection_sha256`` 均由稳定身份字段计算，
    同一 RuleSet revision 的同一 requirement 永远得到同一模板。
    模板覆盖 EvidenceRequirement 下游执行所需的全部字段：fact_type、
    due_stage、required_source_types、允许筛选记录转录、要求同期客观来源、
    来源有效期与描述文本。Phase 4/5 创建 ReviewEpisode 时再由此模板投影具体受试者期望。
    """

    template_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    requirement_id: str = Field(min_length=1)
    due_stage: ReviewStage
    study_phase: StudyPhase
    workflow_stage_id: str = Field(min_length=1)
    fact_type: str = Field(min_length=1)
    required_source_types: list[str] = Field(default_factory=list)
    requires_contemporaneous_objective_source: bool | None = False
    allows_screening_record_transcription: bool | None = True
    source_validity_window: TimeQuantity | None = None
    control_origin: ControlEvidenceOrigin | None = None
    control_validity_status: Literal["specified", "not_specified", "unknown"] | None = None
    control_validity_constraint: TimeConstraint | None = None
    description: str = Field(min_length=1)
    projection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @model_serializer(mode="wrap")
    def serialize_validity(self, handler):
        """Preserve legacy payload hashes, not only the inner projection hash."""
        data = handler(self)
        if self.source_validity_window is None:
            data.pop("source_validity_window", None)
        for name in ("control_origin", "control_validity_status", "control_validity_constraint"):
            if getattr(self, name) is None:
                data.pop(name, None)
        return data

    @model_validator(mode="after")
    def validate_template_identity(self) -> "EvidenceExpectationTemplate":
        from app.domain.publication import canonical_hash

        if self.control_origin is not None:
            if self.control_origin.workflow_stage_id != self.workflow_stage_id:
                raise ValueError("补充资料模板的审核访视与来源不一致")
            if self.control_validity_status is None or self.source_validity_window is not None:
                raise ValueError("补充资料模板须保留独立有效期状态")
            if (self.control_validity_status == "specified") != (self.control_validity_constraint is not None):
                raise ValueError("补充资料模板的有效期状态与时间约束不一致")
        elif (
            self.control_validity_status is not None
            or self.control_validity_constraint is not None
            or self.requires_contemporaneous_objective_source is None
            or self.allows_screening_record_transcription is None
        ):
            raise ValueError("补充资料模板状态缺少对应控制来源")
        expected_projection = canonical_hash(
            {
                **expectation_validity_projection_fields(
                    self.source_validity_window,
                    control_origin=self.control_origin,
                    control_validity_status=self.control_validity_status,
                    control_validity_constraint=self.control_validity_constraint,
                ),
                "rule_set_id": self.rule_set_id,
                "rule_set_revision": self.rule_set_revision,
                "requirement_id": self.requirement_id,
                "due_stage": self.due_stage.value,
                "study_phase": self.study_phase.value,
                "workflow_stage_id": self.workflow_stage_id,
                "fact_type": self.fact_type,
                "required_source_types": sorted(set(self.required_source_types)),
                "requires_contemporaneous_objective_source": (
                    self.requires_contemporaneous_objective_source
                ),
                "allows_screening_record_transcription": (
                    self.allows_screening_record_transcription
                ),
                "description": self.description,
            }
        )
        if self.projection_sha256 != expected_projection:
            raise ValueError("EvidenceExpectationTemplate 投影哈希与身份字段不一致")
        expected_id = (
            "expectation-template:"
            + canonical_hash(
                {
                    "rule_set_id": self.rule_set_id,
                    "rule_set_revision": self.rule_set_revision,
                    "requirement_id": self.requirement_id,
                }
            )[:32]
        )
        if self.template_id != expected_id:
            raise ValueError("EvidenceExpectationTemplate 模板 ID 与稳定身份不一致")
        return self


def expectation_validity_projection_fields(
    window: TimeQuantity | None,
    *,
    control_origin: ControlEvidenceOrigin | None = None,
    control_validity_status: str | None = None,
    control_validity_constraint: TimeConstraint | None = None,
) -> dict:
    """Keep legacy hashes exact; bind explicit source validity in the v2 payload."""
    if control_origin is not None:
        return {
            "projection": "evidence_expectation_template/v3",
            "control_origin": control_origin.model_dump(mode="json"),
            "control_validity_status": control_validity_status,
            "control_validity_constraint": (
                control_validity_constraint.model_dump(mode="json")
                if control_validity_constraint is not None else None
            ),
        }
    if window is None:
        return {"projection": "evidence_expectation_template/v1"}
    return {
        "projection": "evidence_expectation_template/v2",
        "source_validity_window": window.model_dump(mode="json"),
    }


class ClinicalFact(VersionedModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"polarity": {"const": "unknown"}},
                        "required": ["polarity"],
                    },
                    "then": {
                        "properties": {
                            "value": {"type": "null"},
                            "unit": {"type": "null"},
                        }
                    },
                }
            ]
        },
    )
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
        if self.polarity == FactPolarity.UNKNOWN:
            if self.value is not None or self.unit is not None:
                raise ValueError("未知极性事实不能携带 typed value 或单位")
            return self
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
