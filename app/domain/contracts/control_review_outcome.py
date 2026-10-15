"""Source-linked control results, separate from official eligibility decisions."""
from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from .common import ContractModel
from .enums import TruthValue
from .protocol_controls import ControlObligationKind, ControlObligationModality
from .proposition_evidence import PropositionPairGap
from .observation_selection import OrderedObservationAudit
from .evaluation_result import RepeatAtomEvaluation, FrequencyAtomEvaluation


class ControlObligationOutcome(ContractModel):
    obligation_id: str
    obligation_group_id: str
    identity_sha256: str
    statement: str
    proposition: str | None
    kind: ControlObligationKind
    modality: ControlObligationModality
    activation_route: Literal["default_remaining", "exception_replacement"]
    trigger_branch_ids: list[str]
    exception_group_ids: list[str]
    activation: TruthValue
    observation_truth: TruthValue
    status: Literal["fulfilled", "unfulfilled", "unverified", "not_applicable"]
    unresolved_atom_identities: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    used_fact_ids: list[str]
    locator_ids: list[str]
    observation_reason_codes: list[str]
    protocol_span_ids: list[str]
    protocol_excerpts: list[str | None]
    unverified_evidence: list[PropositionPairGap] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def preserve_legacy_payload(self, handler):
        result = handler(self)
        if not self.unverified_evidence:
            result.pop("unverified_evidence", None)
        return result

    @model_validator(mode="after")
    def validate_status(self):
        expected = (
            "not_applicable" if self.activation == TruthValue.FALSE
            else "unverified" if TruthValue.UNKNOWN in (self.activation, self.observation_truth)
            else "fulfilled" if self.observation_truth == TruthValue.TRUE else "unfulfilled"
        )
        if self.status != expected:
            raise ValueError("补充要求状态与保存的条件结果不一致")
        if len(self.protocol_span_ids) != len(self.protocol_excerpts):
            raise ValueError("补充要求原文定位不完整")
        return self


class ControlReviewOutcome(ContractModel):
    version: Literal["control-review-outcome/v1", "control-review-outcome/v2", "control-review-outcome/v3", "control-review-outcome/v4", "control-review-outcome/v5"] = "control-review-outcome/v5"
    protocol_control_id: str
    control_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frozen_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selections_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted: Literal[False] = False
    obligations: list[ControlObligationOutcome]
    unresolved_atoms: dict[str, list[str]]
    observation_ordering: dict[str, OrderedObservationAudit] = Field(default_factory=dict)
    repeat_evaluations: dict[str, RepeatAtomEvaluation] = Field(default_factory=dict)
    frequency_evaluations: dict[str, FrequencyAtomEvaluation] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def serialize_ordering(self, handler):
        result = handler(self)
        if self.version not in {"control-review-outcome/v3", "control-review-outcome/v4", "control-review-outcome/v5"}:
            result.pop("observation_ordering", None)
        if not self.repeat_evaluations:
            result.pop("repeat_evaluations", None)
        if not self.frequency_evaluations:
            result.pop("frequency_evaluations", None)
        return result

    @model_validator(mode="after")
    def preserve_legacy_evidence_boundary(self):
        if self.version in {"control-review-outcome/v3", "control-review-outcome/v4", "control-review-outcome/v5"} and any(
            "selected_fact_ids" not in audit.model_fields_set for audit in self.observation_ordering.values()
        ):
            raise ValueError("新版检查选择依据须明确记录采用的事实，不能推补旧记录")
        if self.version not in {"control-review-outcome/v3", "control-review-outcome/v4", "control-review-outcome/v5"} and self.observation_ordering:
            raise ValueError("旧审核记录不能补入新版检查选择依据")
        if self.version not in {"control-review-outcome/v4", "control-review-outcome/v5"} and self.repeat_evaluations:
            raise ValueError("旧审核记录不能补入新的复查求值")
        if self.version != "control-review-outcome/v5" and self.frequency_evaluations:
            raise ValueError("旧审核记录不能补入新的频次计算")
        if set(self.frequency_evaluations) & set(self.repeat_evaluations):
            raise ValueError("同一条件不能混用频次与复查计算")
        if self.version == "control-review-outcome/v1" and any(item.unverified_evidence for item in self.obligations):
            raise ValueError("旧审核记录不能补入新版原文疑问")
        return self


class ReviewControlSnapshot(ContractModel):
    """A persisted report part; its publication receipt is verified by storage.

    The nested calculation flag stays false: saving a report does not promote
    its source calculation into an independent clinical approval.
    """
    version: Literal["review-control-snapshot/v1"] = "review-control-snapshot/v1"
    review_run_id: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selections_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    gate_result_id: str = Field(min_length=1)
    outcomes: list[ControlReviewOutcome]
    created_at: datetime

    @model_validator(mode="after")
    def validate_snapshot(self):
        if self.created_at.tzinfo is None or self.created_at.utcoffset() != timedelta(0):
            raise ValueError("审核保存时间必须使用明确的UTC时间")
        ids = [item.protocol_control_id for item in self.outcomes]
        if len(ids) != len(set(ids)):
            raise ValueError("同次审核的补充要求不得重复")
        if len({(item.frozen_input_sha256, item.selections_sha256) for item in self.outcomes}) > 1:
            raise ValueError("补充要求结果不得混用不同资料或核对批次")
        return self
