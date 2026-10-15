"""R3 single-stage page review, reconciliation, and coverage contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import (
    ConfigDict,
    Field,
    StrictInt,
    ValidationInfo,
    field_validator,
    model_serializer,
    model_validator,
)

from .common import ContractModel, VersionedModel
from .enums import StableEnum
from .evidence import BoundingBox
from .reading_view import ReadingViewBinding
from .source_policy import SourcePolicyKind, VerificationStatus

_SHA256 = r"^[0-9a-f]{64}$"
PAGE_REVIEW_CONTRACT_VERSION = "page-review/v6"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PageReviewLane(StableEnum):
    MAIN_A = "main-A"
    MAIN_B = "main-B"
    HANDWRITING_C = "handwriting-C"


class EvidenceSignal(StableEnum):
    FOR = "evidence_for"
    AGAINST = "evidence_against"
    MENTIONS = "mentions"
    NONE = "none"


class HandwritingKind(StableEnum):
    SIGNATURE_INITIALS_DATE = "signature_initials_date"
    CS_NCS_JUDGMENT = "cs_ncs_judgment"
    NOTE = "note"
    TABLE_CELL = "table_cell"
    OTHER = "other"


class PageDisposition(StableEnum):
    ACCEPTED = "accepted"
    DISCARDED_NO_ELIGIBILITY_VALUE = "discarded_no_eligibility_value"
    FAILED_PENDING_REREAD = "failed_pending_reread"


class PageRegion(ContractModel):
    excerpt: str = Field(min_length=1)
    bbox: BoundingBox | None = None


class ObservationContext(ContractModel):
    """Source-written association, not an inferred clinical determination."""

    target_text: str = Field(min_length=1)
    time_text: str | None = Field(default=None, min_length=1)
    location_text: str | None = Field(default=None, min_length=1)
    polarity: Literal["asserted", "negated", "uncertain", "not_stated"] = "not_stated"


class PageFactObservation(ContractModel):
    observation_id: str = Field(min_length=1)
    field_name: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)
    raw_value: str = Field(min_length=1)
    normalized_value: str = Field(min_length=1)
    normalized_unit: str | None = None
    normalization_key: str = Field(min_length=1)
    region: PageRegion
    context: ObservationContext | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def validate_normalization(self) -> "PageFactObservation":
        from app.domain.page_normalization import fact_normalization_key

        key, value, unit = fact_normalization_key(self.field_name, self.raw_value,
            context=self.context.model_dump() if self.context is not None else None)
        if (self.normalization_key, self.normalized_value, self.normalized_unit) != (
            key,
            value,
            unit,
        ):
            raise ValueError("事实规范值或归一化键与确定性规范化结果不一致")
        return self


class _Version5PageFactObservation(PageFactObservation):
    @model_validator(mode="after")
    def validate_normalization(self):
        from app.domain.page_normalization import fact_normalization_key
        expected = fact_normalization_key(self.field_name, self.raw_value, version5=True,
            context=self.context.model_dump() if self.context is not None else None)
        if (self.normalization_key, self.normalized_value, self.normalized_unit) != expected:
            raise ValueError("历史 v5 规范值不一致，不能还原")
        return self


class _Version4PageFactObservation(PageFactObservation):
    @model_validator(mode="after")
    def validate_normalization(self):
        from app.domain.page_normalization import fact_normalization_key
        expected = fact_normalization_key(self.field_name, self.raw_value, version4=True,
            context=self.context.model_dump() if self.context is not None else None)
        if (self.normalization_key, self.normalized_value, self.normalized_unit) != expected:
            raise ValueError("历史 v4 规范值不一致，不能还原")
        return self


class _Version3PageFactObservation(PageFactObservation):
    @model_validator(mode="after")
    def validate_normalization(self):
        from app.domain.page_normalization import fact_normalization_key
        expected = fact_normalization_key(self.field_name, self.raw_value, version3=True,
            context=self.context.model_dump() if self.context is not None else None)
        if (self.normalization_key, self.normalized_value, self.normalized_unit) != expected:
            raise ValueError("历史 v3 规范值不一致，不能还原")
        return self


class _LegacyPageFactObservation(PageFactObservation):
    """Read-only compatibility for unversioned float and early Decimal receipts."""

    @model_validator(mode="after")
    def validate_normalization(self) -> "_LegacyPageFactObservation":
        if self.context is not None:
            raise ValueError("历史版本没有关联字段，不得增写")
        from app.domain.page_normalization import fact_normalization_key

        key, value, unit = fact_normalization_key(self.field_name, self.raw_value, legacy=True)
        candidates = {(key, value, unit)}
        try:
            old_value = format(float(value), "g")
        except ValueError:
            pass
        else:
            old_key = "|".join((key.split("|", 1)[0], old_value, unit or ""))
            candidates.add((old_key, old_value, unit))
        if (self.normalization_key, self.normalized_value, self.normalized_unit) not in candidates:
            raise ValueError("历史事实规范值不符合已知版本，不能还原")
        return self


class _Version2PageFactObservation(PageFactObservation):
    @model_validator(mode="after")
    def validate_normalization(self) -> "_Version2PageFactObservation":
        if self.context is not None:
            raise ValueError("历史版本没有关联字段，不得增写")
        from app.domain.page_normalization import fact_normalization_key

        expected = fact_normalization_key(self.field_name, self.raw_value, legacy=True)
        if (self.normalization_key, self.normalized_value, self.normalized_unit) != expected:
            raise ValueError("历史 v2 规范值不一致，不能还原")
        return self


class ClauseEvidenceSignal(ContractModel):
    model_config = ConfigDict(json_schema_extra={
        "if": {"properties": {"signal": {"const": "none"}}, "required": ["signal"]},
        "then": {"properties": {"region": {"type": "null"}}},
        "else": {"required": ["region"], "properties": {"region": {"type": "object"}}},
    })
    clause_id: str = Field(min_length=1)
    signal: EvidenceSignal
    region: PageRegion | None = None

    @model_validator(mode="after")
    def require_signal_excerpt(self) -> "ClauseEvidenceSignal":
        if self.signal == EvidenceSignal.NONE and self.region is not None:
            raise ValueError("无证据信号不得携带摘录")
        if self.signal != EvidenceSignal.NONE and self.region is None:
            raise ValueError("非空证据信号必须携带原文摘录")
        return self


class HandwritingObservation(ContractModel):
    observation_id: str = Field(min_length=1)
    kind: HandwritingKind
    raw_text: str = Field(min_length=1)
    normalized_text: str = Field(min_length=1)
    normalization_key: str = Field(min_length=1)
    region: PageRegion
    context: ObservationContext | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def validate_normalization(self) -> "HandwritingObservation":
        from app.domain.page_normalization import handwriting_normalization_key

        key, normalized = handwriting_normalization_key(self.kind.value, self.raw_text,
            context=self.context.model_dump() if self.context is not None else None)
        if (self.normalization_key, self.normalized_text) != (key, normalized):
            raise ValueError(
                "手写规范文字或归一化键与确定性规范化结果不一致"
            )
        return self


class _Version3HandwritingObservation(HandwritingObservation):
    @model_validator(mode="after")
    def validate_normalization(self):
        from app.domain.page_normalization import handwriting_normalization_key
        expected = handwriting_normalization_key(self.kind.value, self.raw_text, version3=True,
            context=self.context.model_dump() if self.context is not None else None)
        if (self.normalization_key, self.normalized_text) != expected:
            raise ValueError("历史手写规范值不一致，不能还原")
        return self


class PageReviewPayload(ContractModel):
    """Strict model-written fields for either main reading lane."""

    has_eligibility_value: bool
    facts: list[PageFactObservation]
    clause_signals: list[ClauseEvidenceSignal]
    handwriting: list[HandwritingObservation]

    @model_validator(mode="after")
    def validate_empty_page(self) -> "PageReviewPayload":
        if not self.has_eligibility_value and (
            self.facts or self.clause_signals or self.handwriting
        ):
            raise ValueError("判定无入排价值的页面不得携带观察结果")
        if self.has_eligibility_value and not (
            self.facts or self.clause_signals or self.handwriting
        ):
            raise ValueError("判定有入排价值的页面必须携带观察结果")
        return self


class PageReviewRecord(VersionedModel):
    contract_version: Literal["page-review/v1", "page-review/v2", "page-review/v3", "page-review/v4", "page-review/v5", "page-review/v6"] = PAGE_REVIEW_CONTRACT_VERSION
    page_review_id: str = Field(min_length=1)
    page_artifact_id: str = Field(min_length=1)
    source_document_version_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    page_image_sha256: str = Field(pattern=_SHA256)
    reading_view: ReadingViewBinding | None = Field(default=None, exclude_if=lambda value: value is None)
    clause_pack_id: str = Field(pattern=r"^clause-pack:[0-9a-f]{32}$")
    clause_pack_sha256: str = Field(pattern=_SHA256)
    lane: PageReviewLane
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    reasoning_effort: Literal["low", "medium", "high", "xhigh", "max"]
    endpoint_base_url: str = Field(min_length=1)
    fallback_used: bool
    finish_reason: str | None = None
    usage: dict[str, int | float] = Field(default_factory=dict)
    prompt_version: str = Field(min_length=1)
    response_sha256: str = Field(pattern=_SHA256)
    has_eligibility_value: bool
    facts: list[PageFactObservation]
    clause_signals: list[ClauseEvidenceSignal]
    handwriting: list[HandwritingObservation]
    created_at: datetime = Field(default_factory=_utc_now)

    @field_validator("facts", mode="wrap")
    @classmethod
    def read_facts_for_version(cls, value, handler, info: ValidationInfo):
        legacy_type = {"page-review/v1": _LegacyPageFactObservation,
                       "page-review/v2": _Version2PageFactObservation,
                       "page-review/v3": _Version3PageFactObservation,
                       "page-review/v4": _Version4PageFactObservation,
                       "page-review/v5": _Version5PageFactObservation}.get(info.data.get("contract_version"))
        if legacy_type and isinstance(value, list):
            return [legacy_type.model_validate(
                item.model_dump() if isinstance(item, PageFactObservation) else item
            ) for item in value]
        # Do not let an already validated legacy subclass bypass v2 validation.
        if isinstance(value, list):
            value = [item.model_dump() if isinstance(item, PageFactObservation) else item for item in value]
        return handler(value)

    @field_validator("handwriting", mode="wrap")
    @classmethod
    def read_handwriting_for_version(cls, value, handler, info: ValidationInfo):
        if isinstance(value, list):
            value = [item.model_dump() if isinstance(item, HandwritingObservation) else item for item in value]
            if info.data.get("contract_version") in {"page-review/v1", "page-review/v2", "page-review/v3"}:
                return [_Version3HandwritingObservation.model_validate(item) for item in value]
        return handler(value)

    @model_validator(mode="after")
    def validate_lane_scope(self) -> "PageReviewRecord":
        if self.reading_view is not None and (
            self.reading_view.source_page_artifact_id != self.page_artifact_id
            or self.reading_view.source_image_sha256 != self.page_image_sha256
        ):
            raise ValueError("阅读视图与判读记录的原始页面不一致")
        if self.reading_view is not None:
            for observation in (*self.facts, *self.handwriting, *self.clause_signals):
                box = observation.region.bbox
                if box is not None and (
                    box.x1 > self.reading_view.source_width
                    or box.y1 > self.reading_view.source_height
                ):
                    raise ValueError("判读记录中的摘录位置超出原始页面")
        # Main-reader defaults are enforced by route construction, not historical receipts.
        if not self.has_eligibility_value and (
            self.facts or self.clause_signals or self.handwriting
        ):
            raise ValueError("判定无入排价值的页面不得携带观察结果")
        if self.has_eligibility_value and not (
            self.facts or self.clause_signals or self.handwriting
        ):
            raise ValueError("判定有入排价值的页面必须携带观察结果")
        for items, label in (
            (self.facts, "事实观察"),
            (self.handwriting, "手写观察"),
        ):
            identities = [item.observation_id for item in items]
            if len(identities) != len(set(identities)):
                raise ValueError(f"{label}身份不得重复")
        return self


class ReconciliationConflict(ContractModel):
    field_name: str = Field(min_length=1)
    normalization_keys: list[str] = Field(min_length=1)
    page_review_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)


class PageLaneFailure(ContractModel):
    lane: PageReviewLane
    failure_kind: str = Field(min_length=1)


_THIRD_READ_FIELDS = (
    "handwriting_reader_triggered",
    "missing_optional_lanes",
    "optional_lane_failures",
)


class PageReconciliation(VersionedModel):
    contract_version: Literal[
        "page-reconciliation/v1",
        "page-reconciliation/v2",
        "page-reconciliation/v3",
        "page-reconciliation/v4",
    ] = "page-reconciliation/v4"
    association_text_sha256: str | None = Field(default=None, pattern=_SHA256, exclude_if=lambda value: value is None)
    reconciliation_id: str = Field(min_length=1)
    page_artifact_id: str = Field(min_length=1)
    clause_pack_sha256: str = Field(pattern=_SHA256)
    page_review_ids: list[str] = Field(min_length=2)
    accepted_fact_keys: list[str] = Field(default_factory=list)
    fact_conflicts: list[ReconciliationConflict] = Field(default_factory=list)
    accepted_clause_signals: list[ClauseEvidenceSignal] = Field(default_factory=list)
    signal_conflicts: list[ReconciliationConflict] = Field(default_factory=list)
    accepted_handwriting: list[HandwritingObservation] = Field(default_factory=list)
    handwriting_conflicts: list[ReconciliationConflict] = Field(default_factory=list)
    dropped_deterministic_signal_clause_ids: list[str] = Field(default_factory=list)
    # The three fields below exist only so persisted receipts from the retired
    # handwriting third read keep decoding byte-stable; the current version
    # never writes or accepts them.
    handwriting_reader_triggered: bool = False
    missing_optional_lanes: list[PageReviewLane] = Field(default_factory=list)
    optional_lane_failures: list[PageLaneFailure] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="before")
    @classmethod
    def reject_third_read_fields_in_current_version(cls, data):
        if isinstance(data, dict) and data.get("contract_version") == "page-reconciliation/v4":
            present = [field for field in _THIRD_READ_FIELDS if field in data]
            if present:
                raise ValueError(f"当前对账版本不记录第三读缺席状态：{'、'.join(present)}")
        return data

    @model_serializer(mode="wrap")
    def serialize_without_third_read_fields(self, handler):
        payload = dict(handler(self))
        if self.contract_version == "page-reconciliation/v4":
            for field in _THIRD_READ_FIELDS:
                payload.pop(field, None)
        return payload

    @model_validator(mode="after")
    def validate_association_version(self):
        if self.association_text_sha256 is not None and self.contract_version not in {
            "page-reconciliation/v3", "page-reconciliation/v4",
        }:
            raise ValueError("历史对账版本不得附加新的来源关联依据")
        return self

    @field_validator("accepted_handwriting", mode="wrap")
    @classmethod
    def read_accepted_handwriting_for_version(cls, value, handler, info: ValidationInfo):
        if isinstance(value, list):
            value = [item.model_dump() if isinstance(item, HandwritingObservation) else item for item in value]
            if info.data.get("contract_version") == "page-reconciliation/v1":
                return [_Version3HandwritingObservation.model_validate(item) for item in value]
        return handler(value)

    @model_validator(mode="after")
    def validate_sources(self) -> "PageReconciliation":
        if len(self.page_review_ids) != len(set(self.page_review_ids)):
            raise ValueError("页级对账不得重复引用同一读道记录")
        if not self.handwriting_reader_triggered and self.missing_optional_lanes:
            raise ValueError("手写专项读未触发时不得记录读道缺席")
        if {item.lane for item in self.optional_lane_failures} - set(
            self.missing_optional_lanes
        ):
            raise ValueError("只能为已缺席的可选读道记录失败原因")
        return self


class PageCoverageEntry(ContractModel):
    page_artifact_id: str = Field(min_length=1)
    source_document_version_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    disposition: PageDisposition
    reconciliation_id: str | None = Field(default=None, min_length=1)
    discard_reason: str | None = Field(default=None, min_length=1)
    lane_failures: list[PageLaneFailure] = Field(default_factory=list)
    #: WP02新增：来源政策标签（native_text/ocr_primary/single_visual等）。
    #: 非None时表示该页由单来源（非双读）流程处理，reconciliation_id可为空。
    source_policy_kind: SourcePolicyKind | None = Field(default=None)
    source_policy_verification: VerificationStatus | None = Field(default=None)

    @model_validator(mode="after")
    def validate_disposition(self) -> "PageCoverageEntry":
        if (self.source_policy_kind is None) != (self.source_policy_verification is None):
            raise ValueError("来源方式与核实状态必须同时提供")
        has_verified_single_source = (
            self.source_policy_kind is not None
            and self.source_policy_verification in (
                VerificationStatus.CROSS_VERIFIED,
                VerificationStatus.TARGETED_VERIFIED,
                VerificationStatus.MANUAL_CONFIRMED,
            )
        )
        if self.disposition == PageDisposition.ACCEPTED:
            if self.reconciliation_id is None and not has_verified_single_source:
                raise ValueError("已采信页面必须绑定对账记录或声明已验证来源政策")
            if self.discard_reason or self.lane_failures:
                raise ValueError("已采信页面不得携带舍弃或失败字段")
        elif self.disposition == PageDisposition.DISCARDED_NO_ELIGIBILITY_VALUE:
            if not self.discard_reason:
                raise ValueError("无入排价值舍弃必须说明理由")
            if self.reconciliation_id or self.lane_failures:
                raise ValueError("舍弃页面不得携带采信或失败字段")
        else:
            if not self.lane_failures:
                raise ValueError("失败页面必须保留原读道与失败类别")
            if self.reconciliation_id or self.discard_reason:
                raise ValueError("失败页面不得伪装为采信或舍弃")
            lanes = [item.lane for item in self.lane_failures]
            if len(lanes) != len(set(lanes)):
                raise ValueError("失败页面不得重复记录同一读道")
        return self


class SubjectPageCoverage(VersionedModel):
    contract_version: Literal["subject-page-coverage/v1"] = "subject-page-coverage/v1"
    execution_versions: dict[str, str] = Field(default_factory=dict, exclude_if=lambda value: not value)
    main_reader_identity_sha256: str | None = Field(default=None, pattern=_SHA256, exclude_if=lambda value: value is None)
    predecessor_coverage_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    reading_rotations: dict[str, StrictInt] = Field(default_factory=dict, exclude_if=lambda value: not value)
    coverage_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    evidence_processing_revision_id: str = Field(min_length=1)
    clause_pack_sha256: str = Field(pattern=_SHA256)
    expected_page_artifact_ids: list[str] = Field(min_length=1)
    entries: list[PageCoverageEntry] = Field(min_length=1)
    created_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def validate_page_closure(self) -> "SubjectPageCoverage":
        expected = self.expected_page_artifact_ids
        if (set(self.reading_rotations) - set(expected)
                or any(angle not in (90, 180, 270) for angle in self.reading_rotations.values())):
            raise ValueError("阅读方向必须对应覆盖范围内页面且为直角旋转")
        actual = [item.page_artifact_id for item in self.entries]
        if len(expected) != len(set(expected)):
            raise ValueError("预期页清单不得重复")
        if len(actual) != len(set(actual)):
            raise ValueError("页覆盖处置不得重复")
        if set(actual) != set(expected):
            raise ValueError("每一预期页必须且只能有一条覆盖处置")
        return self


__all__ = [
    "ClauseEvidenceSignal",
    "EvidenceSignal",
    "HandwritingKind",
    "HandwritingObservation",
    "PageCoverageEntry",
    "PageDisposition",
    "PageFactObservation",
    "PageLaneFailure",
    "PageReconciliation",
    "PageRegion",
    "PageReviewLane",
    "PageReviewPayload",
    "PageReviewRecord",
    "ReconciliationConflict",
    "SubjectPageCoverage",
]
