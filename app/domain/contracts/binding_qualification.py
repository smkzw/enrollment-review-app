"""Versioned source-qualification records for candidate bindings (design §17.1.1 step 3).

Statuses that must never collapse:

- ``structurally_valid`` — deterministic ID/hash/value/locator/body checks passed;
- ``dual_agreement`` — both lanes share the same structured judgment dimensions;
- ``authorized_clinical_adoption`` / ``clinically_qualified`` — always false here.

Free-text unresolved reasons are provenance per lane, never part of agreement keys.
Schema or dual agreement alone never authorizes clinical adoption.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.domain.publication import canonical_hash

from .common import ContractModel, ScalarValue

_SHA256 = r"^[0-9a-f]{64}$"
_LANES = ("main-A", "main-B")

BINDING_QUALIFICATION_PAIR_VERSION = "binding-qualification-pair/v2"
BINDING_QUALIFICATION_SUMMARY_VERSION = "binding-qualification-summary/v2"
BINDING_QUALIFICATION_PROMPT_VERSION = "binding-qualification/v5"
BINDING_QUALIFICATION_BATCH_VERSION = "binding-qualification-batch/v1"

CandidateFamily = Literal["predicate", "control"]
SourcePolicyStatus = Literal["present", "missing", "unattributed", "ambiguous"]
SourceAdmissibility = Literal["admissible", "inadmissible", "unresolved"]
ObjectMatch = Literal["supported", "uncertain", "rejected"]
AttributeMatch = Literal[
    "direct", "derivation_operand", "context_only", "uncertain", "rejected"
]
DenialScope = Literal["compatible", "uncertain", "incompatible"]
TemporalRole = Literal[
    "event_date", "record_time", "not_applicable", "uncertain", "mismatched"
]
DirectOperandUsable = Literal["usable", "not_usable", "unresolved"]


def binding_qualification_pair_id(
    *,
    candidate_job_id: str,
    frozen_input_sha256: str,
    identity_field: str,
    identity_sha256: str,
    fact_id: str,
    fact_attribute: str,
    locator_id: str,
    candidate_batch_sha256: str | None,
) -> str:
    return canonical_hash({
        "identity": "binding-qualification-pair-id/v2",
        "candidate_job_id": candidate_job_id,
        "frozen_input_sha256": frozen_input_sha256,
        "identity_field": identity_field,
        "identity_sha256": identity_sha256,
        "fact_id": fact_id,
        "fact_attribute": fact_attribute,
        "locator_id": locator_id,
        "candidate_batch_sha256": candidate_batch_sha256,
    })


def _require_lanes(mapping: dict) -> None:
    if tuple(sorted(mapping)) != tuple(sorted(_LANES)):
        raise ValueError("资格核对必须且只能包含 main-A 与 main-B 两路")


class BindingQualificationLaneDeclaration(ContractModel):
    """Provenance-only candidate labels; never shown to peer models."""

    object_correspondence: Literal["supported", "uncertain"] | None = None
    attribute_correspondence: (
        Literal["direct", "derivation_operand", "context_only", "uncertain"] | None
    ) = None
    proposed: bool = False


class BindingQualificationPairContext(ContractModel):
    """Pair-scoped frozen material for qualification; peer labels stay provenance-only."""

    pair_id: str = Field(pattern=_SHA256)
    identity_field: Literal["predicate_identity_sha256", "atom_identity_sha256"]
    identity_sha256: str = Field(pattern=_SHA256)
    candidate_family: CandidateFamily
    candidate_job_id: str = Field(min_length=1)
    candidate_job_type: str = Field(min_length=1)
    candidate_contract: str = Field(min_length=1)
    frozen_input_sha256: str = Field(pattern=_SHA256)
    candidate_batch_sha256: str | None = Field(default=None, pattern=_SHA256)
    comparison_sha256: str = Field(pattern=_SHA256)
    fact_id: str = Field(min_length=1)
    fact_attribute: Literal["value", "date_range", "record_time", "assertion_basis"]
    locator_id: str = Field(min_length=1)
    condition: dict
    fact: dict
    locator: dict
    document: dict | None = None
    episode: dict
    parent_source_context: dict
    source_policies: list[dict] = Field(default_factory=list)
    source_policy_status: SourcePolicyStatus
    required_source_types: list[str] = Field(default_factory=list)
    lane_declarations: dict[str, BindingQualificationLaneDeclaration]
    candidate_receipt_sha256s: dict[str, list[str]]

    @model_validator(mode="after")
    def validate_pair_context(self) -> "BindingQualificationPairContext":
        expected = binding_qualification_pair_id(
            candidate_job_id=self.candidate_job_id,
            frozen_input_sha256=self.frozen_input_sha256,
            identity_field=self.identity_field,
            identity_sha256=self.identity_sha256,
            fact_id=self.fact_id,
            fact_attribute=self.fact_attribute,
            locator_id=self.locator_id,
            candidate_batch_sha256=self.candidate_batch_sha256,
        )
        if self.pair_id != expected:
            raise ValueError("资格核对配对身份与冻结内容不一致")
        _require_lanes(self.lane_declarations)
        _require_lanes(self.candidate_receipt_sha256s)
        if self.source_policy_status == "missing" and self.source_policies:
            raise ValueError("来源政策缺失时不得附带政策内容")
        if self.source_policy_status != "missing" and not self.source_policies:
            raise ValueError("来源政策存在或未归属时必须保留完整政策材料")
        if self.fact.get("fact_id") != self.fact_id:
            raise ValueError("配对事实正文与 fact_id 不一致")
        if self.locator.get("locator_id") != self.locator_id:
            raise ValueError("配对定位正文与 locator_id 不一致")
        return self


class BindingQualificationBatch(ContractModel):
    """Deterministic pair batch; references are deduplicated in prompts."""

    version: Literal["binding-qualification-batch/v1"] = BINDING_QUALIFICATION_BATCH_VERSION
    frozen_input_sha256: str = Field(pattern=_SHA256)
    candidate_job_id: str = Field(min_length=1)
    pair_ids: list[str] = Field(min_length=1)
    identity_sha256s: list[str] = Field(min_length=1)
    fact_ids: list[str] = Field(min_length=1)
    locator_ids: list[str] = Field(min_length=1)
    batch_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_batch(self) -> "BindingQualificationBatch":
        for field in ("pair_ids", "identity_sha256s", "fact_ids", "locator_ids"):
            values = getattr(self, field)
            if values != sorted(set(values)):
                raise ValueError(f"资格分批 {field} 必须排序且不重复")
        material = self.model_dump(mode="json", exclude={"batch_sha256", "version"})
        if canonical_hash({"identity": BINDING_QUALIFICATION_BATCH_VERSION, **material}) != self.batch_sha256:
            raise ValueError("资格分批哈希与内容不一致")
        return self


class BindingQualificationJudgment(ContractModel):
    """One lane's structured recheck; explanation/reasons stay private to that lane."""

    pair_id: str = Field(pattern=_SHA256)
    source_admissibility: SourceAdmissibility
    object_match: ObjectMatch
    attribute_match: AttributeMatch
    denial_scope: DenialScope
    temporal_role: TemporalRole
    direct_operand_usable: DirectOperandUsable
    unresolved_reasons: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_judgment(self) -> "BindingQualificationJudgment":
        if any(not item.strip() for item in self.unresolved_reasons):
            raise ValueError("未核实原因不得为空字符串")
        needs_reason = (
            self.source_admissibility == "unresolved"
            or self.object_match in {"uncertain", "rejected"}
            or self.attribute_match in {
                "uncertain", "rejected", "context_only", "derivation_operand",
            }
            or self.denial_scope != "compatible"
            or self.temporal_role in {"uncertain", "mismatched"}
            or self.direct_operand_usable != "usable"
        )
        if needs_reason and not self.unresolved_reasons:
            raise ValueError("未通过或未核实的资格判断必须保留具体原因")
        return self

    def public_agreement_key(self) -> tuple:
        """Structured dimensions only; free-text reasons never decide agreement."""
        return (
            self.source_admissibility,
            self.object_match,
            self.attribute_match,
            self.denial_scope,
            self.temporal_role,
            self.direct_operand_usable,
        )


class BindingQualificationLanePayload(ContractModel):
    results: list[BindingQualificationJudgment]


class BindingQualificationStructuralCheck(ContractModel):
    """Deterministic reference/body/shape checks; never clinical or semantic adoption."""

    pair_id: str = Field(pattern=_SHA256)
    structurally_valid: bool
    reasons: list[str] = Field(default_factory=list)
    pending_checks: list[str] = Field(default_factory=list)
    source_policy_status: SourcePolicyStatus
    referenced_value: ScalarValue | list[ScalarValue] | None = None
    referenced_unit: str | None = None
    referenced_date_precision: str | None = None
    referenced_record_time: str | None = None
    locator_excerpt_sha256: str | None = Field(default=None, pattern=_SHA256)
    source_strength: str | None = None
    operand_shape: str | None = None
    body_matches_frozen: bool

    @model_validator(mode="after")
    def validate_structural(self) -> "BindingQualificationStructuralCheck":
        if self.structurally_valid and self.reasons:
            raise ValueError("结构通过时不得保留失败原因")
        if not self.structurally_valid and not self.reasons:
            raise ValueError("结构未通过时必须保留失败原因")
        if any(not item.strip() for item in self.reasons):
            raise ValueError("结构核对原因不得为空字符串")
        if self.structurally_valid and not self.body_matches_frozen:
            raise ValueError("结构通过必须证明配对正文与冻结材料一致")
        return self


class BindingQualificationPairRecord(ContractModel):
    """Durable per-pair outcome; clinical adoption stays unauthorized."""

    version: Literal["binding-qualification-pair/v2"] = BINDING_QUALIFICATION_PAIR_VERSION
    pair_id: str = Field(pattern=_SHA256)
    identity_field: Literal["predicate_identity_sha256", "atom_identity_sha256"]
    identity_sha256: str = Field(pattern=_SHA256)
    candidate_family: CandidateFamily
    candidate_job_id: str = Field(min_length=1)
    frozen_input_sha256: str = Field(pattern=_SHA256)
    comparison_sha256: str = Field(pattern=_SHA256)
    qualification_batch_sha256: str | None = Field(default=None, pattern=_SHA256)
    candidate_batch_sha256: str | None = Field(default=None, pattern=_SHA256)
    fact_id: str = Field(min_length=1)
    fact_attribute: Literal["value", "date_range", "record_time", "assertion_basis"]
    locator_id: str = Field(min_length=1)
    structural: BindingQualificationStructuralCheck
    lane_judgments: dict[str, BindingQualificationJudgment | None]
    lane_receipt_sha256s: dict[str, list[str]]
    lane_unresolved_reasons: dict[str, list[str]]
    structurally_valid: bool
    dual_agreement: bool
    semantic_dimensions_rechecked: list[str]
    remaining_unverified: list[str] = Field(default_factory=list)
    authorized_clinical_adoption: Literal[False] = False
    clinically_qualified: Literal[False] = False
    accepted: Literal[False] = False
    unresolved_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_record(self) -> "BindingQualificationPairRecord":
        if self.structurally_valid != self.structural.structurally_valid:
            raise ValueError("配对结构状态与结构核对结果不一致")
        if self.structural.pair_id != self.pair_id:
            raise ValueError("结构核对配对身份与记录不一致")
        _require_lanes(self.lane_judgments)
        _require_lanes(self.lane_receipt_sha256s)
        _require_lanes(self.lane_unresolved_reasons)
        if self.authorized_clinical_adoption or self.clinically_qualified or self.accepted:
            raise ValueError("资格阶段不得授权临床采信或正式采用")
        for lane, judgment in self.lane_judgments.items():
            if judgment is not None and judgment.pair_id != self.pair_id:
                raise ValueError("判断配对身份与父记录不一致")
            expected = [] if judgment is None else list(judgment.unresolved_reasons)
            if self.lane_unresolved_reasons.get(lane) != expected:
                raise ValueError("各路未核实原因必须与判断正文一致")
        if self.dual_agreement:
            judgments = [item for item in self.lane_judgments.values() if item is not None]
            if len(judgments) != 2:
                raise ValueError("双路一致需要两路完整判断")
            if {item.public_agreement_key() for item in judgments} != {judgments[0].public_agreement_key()}:
                raise ValueError("标记为双路一致时结构化维度必须相同")
        if any(not item.strip() for item in (*self.unresolved_reasons, *self.remaining_unverified)):
            raise ValueError("未核实原因不得为空字符串")
        return self


class BindingQualificationIdentityRecord(ContractModel):
    identity_field: Literal["predicate_identity_sha256", "atom_identity_sha256"]
    identity_sha256: str = Field(pattern=_SHA256)
    candidate_batch_sha256: str | None = Field(default=None, pattern=_SHA256)
    status: Literal["no_candidates_in_supplied_input", "candidates_present"]
    unresolved_reasons: list[str] = Field(default_factory=list)
    pair_ids: list[str] = Field(default_factory=list)
    accepted: Literal[False] = False
    authorized_clinical_adoption: Literal[False] = False
    clinically_qualified: Literal[False] = False


class BindingQualificationSummary(ContractModel):
    version: Literal["binding-qualification-summary/v2"] = (
        BINDING_QUALIFICATION_SUMMARY_VERSION
    )
    prompt_version: Literal["binding-qualification/v2", "binding-qualification/v3", "binding-qualification/v4", "binding-qualification/v5"] = (
        BINDING_QUALIFICATION_PROMPT_VERSION
    )
    candidate_family: CandidateFamily
    candidate_job_id: str = Field(min_length=1)
    candidate_job_type: str = Field(min_length=1)
    candidate_contract: str = Field(min_length=1)
    frozen_input_sha256: str = Field(pattern=_SHA256)
    comparison_sha256: str = Field(pattern=_SHA256)
    batches: list[BindingQualificationBatch] = Field(default_factory=list)
    pair_records: list[BindingQualificationPairRecord]
    identity_records: list[BindingQualificationIdentityRecord]
    accepted: Literal[False] = False
    authorized_clinical_adoption: Literal[False] = False
    clinically_qualified: Literal[False] = False
    summary_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_summary(self) -> "BindingQualificationSummary":
        if self.accepted or self.authorized_clinical_adoption or self.clinically_qualified:
            raise ValueError("资格汇总不得声明临床采信或正式采用")
        pair_ids = [item.pair_id for item in self.pair_records]
        if len(pair_ids) != len(set(pair_ids)):
            raise ValueError("资格汇总不得重复同一配对")
        for record in self.pair_records:
            if (
                record.candidate_job_id != self.candidate_job_id
                or record.frozen_input_sha256 != self.frozen_input_sha256
                or record.comparison_sha256 != self.comparison_sha256
                or record.candidate_family != self.candidate_family
            ):
                raise ValueError("配对记录必须闭合到汇总的任务与冻结范围")
        batch_pairs = [pair_id for batch in self.batches for pair_id in batch.pair_ids]
        if len(batch_pairs) != len(set(batch_pairs)) or set(batch_pairs) != set(pair_ids):
            raise ValueError("资格分批必须完整覆盖且不超过汇总配对")
        for batch in self.batches:
            if (batch.candidate_job_id != self.candidate_job_id
                    or batch.frozen_input_sha256 != self.frozen_input_sha256):
                raise ValueError("资格分批不属于本次来源任务")
            for record in self.pair_records:
                if record.pair_id in batch.pair_ids and record.qualification_batch_sha256 != batch.batch_sha256:
                    raise ValueError("资格记录与实际分批不一致")
        scopes = [(item.identity_field, item.identity_sha256, item.candidate_batch_sha256)
                  for item in self.identity_records]
        if len(scopes) != len(set(scopes)):
            raise ValueError("条件在同一来源批次内不得重复")
        accounted = []
        indexed = {item.pair_id: item for item in self.pair_records}
        for item in self.identity_records:
            if (item.status == "candidates_present") != bool(item.pair_ids):
                raise ValueError("条件对应状态与配对清单不一致")
            for pair_id in item.pair_ids:
                record = indexed.get(pair_id)
                if record is None or (record.identity_field, record.identity_sha256,
                                      record.candidate_batch_sha256) != (
                    item.identity_field, item.identity_sha256, item.candidate_batch_sha256
                ):
                    raise ValueError("条件清单引用了其他条件或来源批次的配对")
                accounted.append(pair_id)
        if len(accounted) != len(set(accounted)) or set(accounted) != set(pair_ids):
            raise ValueError("条件清单须完整且唯一地覆盖本次配对")
        material = self.model_dump(mode="json", exclude={"summary_sha256"})
        if canonical_hash(material) != self.summary_sha256:
            raise ValueError("资格汇总哈希与内容不一致")
        return self


def binding_qualification_summary_hash(summary: dict) -> str:
    material = dict(summary)
    material.pop("summary_sha256", None)
    return canonical_hash(material)


def binding_qualification_batch_hash(batch: dict) -> str:
    material = dict(batch)
    material.pop("batch_sha256", None)
    material.pop("version", None)
    return canonical_hash({"identity": BINDING_QUALIFICATION_BATCH_VERSION, **material})
