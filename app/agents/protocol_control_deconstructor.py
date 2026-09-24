"""Provider-neutral Agent adapter for other-protocol control candidates.

This module is deliberately separate from :mod:`protocol_deconstructor`.  The
official IN/EX Agent has a different member contract and a different identity
boundary; this adapter only accepts semantic drafts for the frozen
``ProtocolControlDispositionBatch`` produced by the Phase 5.8b planner.

The provider wire is intentionally positional and inline:

* one disposition is returned for every owned structure unit;
* candidate drafts carry their own source-structure-unit closure;
* applicability, trigger, obligation and exception expressions are separate
  DNF values;
* source span IDs and exact excerpts live on every semantic atom; and
* no provider-authored batch, candidate, atom, evidence, relation or node ID is
  accepted.

The adapter turns this wire into the worker-01 domain draft and lets the
domain-owned control hydration function assign stable identities.  It never
calls a model and never writes a project artifact.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from typing import Literal, Protocol

from pydantic import Field, ValidationError, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.repeat_scheme import RepeatEvidenceRoleReference, resolve_repeat_evidence_roles
from app.domain.contracts.control_evaluation_spec import (
    ControlAtomEvaluationSpec, validate_control_atom_evaluation,
)
from app.domain.contracts.observation_selection import ObservationPolicy
from app.protocols.supplementary_relation_contract import (
    is_cross_stage_subsequent_control_supplement,
    procedure_execution_workflow_stage_id,
)
from app.domain.contracts.protocol_controls import (
    ControlConditionAtomDraft,
    ControlConditionDnfDraft,
    ControlConditionGroupDraft,
    ControlRepeatTriggerDraft,
    validate_control_repeat_conditions,
    ControlCrossSourceRelationDraft,
    ControlMinimumEvidenceDraft,
    ControlObligationAtomDraft,
    ControlContinuingObligation,
    ControlObligationDnfDraft,
    ControlObligationGroupDraft,
    ControlRelationTargetKind,
    ControlObligationKind,
    ControlObligationModality,
    ControlTemporalScopeKind,
    CrossSourceRelationKind,
    KnownOfficialRuleTarget,
    KnownRequiredProcedureTarget,
    KnownWorkflowStageTarget,
    ProtocolControlDiscoveryBatch,
    ProtocolControlDiscoveryDecision,
    ProtocolControlDiscoveryDisposition,
    ProtocolControlBatchDisposition,
    ProtocolControlBatchDispositionHydrated,
    ProtocolControlCandidateSemanticDraft,
    ProtocolControlDispositionBatch,
    ProtocolStructureUnit,
    ProtocolControlUnitDispositionDraft,
    ReviewNodeBinding,
    ReviewNodeRole,
    StructureUnitDispositionKind,
    hydrate_protocol_control_batch_disposition,
    is_forbidden_protocol_control_code,
    stable_protocol_control_candidate_id,
)
from app.domain.contracts.enums import ReviewStage, StudyPhase
from app.domain.contracts.rules import ProspectivePeriod, TimeConstraint
from app.domain.contracts.control_evidence_policy import ControlEvidenceSourcePolicy
from app.domain.contracts.control_evidence_dependency import ControlEvidenceAtomReference


from .control_excerpt_restoration import (
    control_quote_normalize as _control_quote_normalize,
    recover_control_excerpt as _recover_control_excerpt,
    restore_source_fields,
)
from .protocol_control_source_interpretation import (
    SOURCE_INTERPRETATION_PROMPT_VERSION,
    SOURCE_TARGET_REVIEW_VERSION,
    SourceInterpretation,
    SourceStatementCoverage,
    SourceTargetReview,
    build_source_interpretation_prompt,
    build_source_target_review_prompt,
    normalize_source_excerpt,
    target_review_indexes,
    validate_source_interpretation,
    validate_source_target_review,
)

CONTROL_AGENT_WIRE_VERSION = "phase5/control-agent-wire/v26"
CONTROL_AGENT_INPUT_VERSION = "phase5/control-agent-input/v1"
CONTROL_AGENT_PROMPT_VERSION = "phase5/control-agent-prompt/v2.59"
CONTROL_DISCOVERY_INPUT_VERSION = "phase5/control-discovery-input/v1"
CONTROL_DISCOVERY_PROMPT_VERSION = "phase5/control-discovery-prompt/v3"
CONTROL_DISCOVERY_WIRE_VERSION = "phase5/control-discovery-wire/v1"
CONTROL_DISCOVERY_RESPONSE_FORMAT_NAME = "protocol_control_discovery_wire_v1"

DEFAULT_MAX_TRANSPORT_RETRIES = 1
DEFAULT_MAX_SCHEMA_REPAIRS = 2

__all__ = [
    "CONTROL_AGENT_INPUT_VERSION",
    "CONTROL_AGENT_PROMPT_VERSION",
    "CONTROL_AGENT_WIRE_VERSION",
    "CONTROL_DISCOVERY_INPUT_VERSION",
    "CONTROL_DISCOVERY_PROMPT_VERSION",
    "CONTROL_DISCOVERY_RESPONSE_FORMAT_NAME",
    "CONTROL_DISCOVERY_WIRE_VERSION",
    "DEFAULT_MAX_SCHEMA_REPAIRS",
    "DEFAULT_MAX_TRANSPORT_RETRIES",
    "DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE",
    "DEFAULT_PROTOCOL_CONTROL_DISCOVERY_PROMPT_TEMPLATE",
    "ProtocolControlAgentAttempt",
    "ProtocolControlAgentInput",
    "ProtocolControlAgentResponse",
    "ProtocolControlAgentRunResult",
    "ProtocolControlAgentRunner",
    "ProtocolControlAgentOutputValidator",
    "ProtocolControlAgentTransport",
    "ProtocolControlAgentWire",
    "ProtocolControlAgentWireCandidate",
    "ProtocolControlAgentWireConditionAtom",
    "ProtocolControlAgentWireConditionDnf",
    "ProtocolControlAgentWireConditionGroup",
    "ProtocolControlAgentWireDisposition",
    "ProtocolControlAgentWireEvidence",
    "ProtocolControlAgentWireExceptionDnf",
    "ProtocolControlAgentWireObligationAtom",
    "ProtocolControlAgentWireObligationDnf",
    "ProtocolControlAgentWireObligationGroup",
    "ProtocolControlAgentWireRelation",
    "ProtocolControlAgentWireValidationError",
    "ProtocolControlDiscoveryAgentAttempt",
    "ProtocolControlDiscoveryAgentAttemptCallback",
    "ProtocolControlDiscoveryAgentInput",
    "ProtocolControlDiscoveryAgentResponse",
    "ProtocolControlDiscoveryAgentRunResult",
    "ProtocolControlDiscoveryAgentRunner",
    "ProtocolControlDiscoveryAgentWire",
    "ProtocolControlDiscoveryAgentWireDecision",
    "ProtocolControlDiscoveryWireValidationError",
    "build_protocol_control_agent_prompt",
    "build_protocol_control_discovery_prompt",
    "build_protocol_control_discovery_repair_prompt",
    "build_protocol_control_repair_prompt",
    "bind_protocol_control_discovery_wire",
    "discovery_wire_to_protocol_control_decisions",
    "hydrate_protocol_control_agent_output",
    "hydrate_protocol_control_discovery_agent_output",
    "parse_protocol_control_agent_output",
    "parse_protocol_control_agent_wire",
    "parse_protocol_control_discovery_agent_wire",
    "protocol_control_agent_json_schema",
    "protocol_control_agent_prompt_template_sha256",
    "protocol_control_agent_response_format",
    "protocol_control_discovery_agent_json_schema",
    "protocol_control_discovery_agent_response_format",
    "protocol_control_discovery_prompt_template_sha256",
    "validate_protocol_control_agent_wire",
    "validate_protocol_control_discovery_agent_wire",
    "wire_to_protocol_control_batch_disposition",
    "wire_to_protocol_control_discovery_decisions",
    "wire_to_protocol_control_discovery_results",
]


class ProtocolControlAgentWireValidationError(ValueError):
    """A provider wire error with a bounded repair scope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        structure_unit_ids: Sequence[str] = (),
        candidate_indexes: Sequence[int] = (),
        candidate_ids: Sequence[str] = (),
        obligation_source_span_ids: Sequence[str] = (),
        error_class_codes: Sequence[str] = (),
        allow_candidate_repartition: bool = False,
        allow_source_closure_rewrite: bool = False,
        allow_post_enrollment_reclassification: bool = False,
        allow_source_insert: bool = False,
    ) -> None:
        self.code = code
        self.error_class_codes = tuple(
            dict.fromkeys((code, *error_class_codes))
        )
        self.structure_unit_ids = tuple(dict.fromkeys(structure_unit_ids))
        self.candidate_indexes = tuple(dict.fromkeys(candidate_indexes))
        self.candidate_ids = tuple(dict.fromkeys(candidate_ids))
        self.obligation_source_span_ids = tuple(
            dict.fromkeys(obligation_source_span_ids)
        )
        self.allow_candidate_repartition = allow_candidate_repartition
        self.allow_source_closure_rewrite = allow_source_closure_rewrite
        self.allow_post_enrollment_reclassification = allow_post_enrollment_reclassification
        self.allow_source_insert = allow_source_insert
        super().__init__(f"{code}: {message}")


class ProtocolControlAgentResponse(ContractModel):
    """Raw transport response retained only for adapter audit."""

    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class ProtocolControlAgentTransport(Protocol):
    """Provider-neutral transport boundary; no provider is selected here."""

    def start(self, *, prompt: str) -> ProtocolControlAgentResponse: ...

    def continue_session(
        self, *, session_id: str, prompt: str
    ) -> ProtocolControlAgentResponse: ...
class ProtocolControlDiscoveryAgentResponse(ProtocolControlAgentResponse):
    """Raw first-stage transport response retained for adapter audit."""


class ProtocolControlDiscoveryAgentTransport(Protocol):
    """Provider-neutral transport boundary for coarse discovery."""

    def start(self, *, prompt: str) -> ProtocolControlDiscoveryAgentResponse: ...

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> ProtocolControlDiscoveryAgentResponse: ...



class ProtocolControlAgentInput(ContractModel):
    """The frozen, read-only input projection sent to the control Agent."""

    schema_version: Literal[CONTROL_AGENT_INPUT_VERSION] = Field(...)
    batch_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    study_phase: StudyPhase
    owned_units: list[ProtocolStructureUnit] = Field(min_length=1)
    context_units: list[ProtocolStructureUnit] = Field(default_factory=list)
    pre_enrollment_structure_unit_ids: list[str] = Field(default_factory=list)
    owned_visit_instance_by_structure_unit_id: dict[str, str] = Field(
        default_factory=dict
    )
    known_official_targets: list[KnownOfficialRuleTarget] = Field(default_factory=list)
    known_procedure_targets: list[KnownRequiredProcedureTarget] = Field(default_factory=list)
    known_workflow_stage_targets: list[KnownWorkflowStageTarget] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_scope(self) -> "ProtocolControlAgentInput":
        owned_ids = [unit.structure_unit_id for unit in self.owned_units]
        context_ids = [unit.structure_unit_id for unit in self.context_units]
        if len(owned_ids) != len(set(owned_ids)):
            raise ValueError("Agent 输入 owned_units 不得重复")
        if len(context_ids) != len(set(context_ids)):
            raise ValueError("Agent 输入 context_units 不得重复")
        if set(owned_ids) & set(context_ids):
            raise ValueError("Agent 输入 owned/context 单元不得重叠")
        if not set(self.pre_enrollment_structure_unit_ids) <= set(owned_ids):
            raise ValueError("Agent 输入给药前结构单元必须属于 owned_units")
        if not set(self.owned_visit_instance_by_structure_unit_id) <= set(owned_ids):
            raise ValueError("Agent 输入执行访视归属只能引用 owned_units")
        return self


    @classmethod
    def from_batch(cls, batch: ProtocolControlDispositionBatch) -> "ProtocolControlAgentInput":
        return cls(
            schema_version=CONTROL_AGENT_INPUT_VERSION,
            batch_id=batch.batch_id,
            coverage_manifest_id=batch.coverage_manifest_id,
            protocol_version_id=batch.protocol_version_id,
            study_phase=batch.study_phase,
            owned_units=list(batch.owned_units),
            context_units=list(batch.context_units),
            pre_enrollment_structure_unit_ids=list(
                batch.pre_enrollment_structure_unit_ids
            ),
            owned_visit_instance_by_structure_unit_id=dict(
                batch.owned_visit_instance_by_structure_unit_id
            ),
            known_official_targets=list(batch.known_official_targets),
            known_procedure_targets=list(batch.known_procedure_targets),
            known_workflow_stage_targets=list(batch.known_workflow_stage_targets),
        )

class ProtocolControlDiscoveryAgentInput(ContractModel):
    """Bounded first-stage input; no full-manifest ID list is included."""

    schema_version: Literal[CONTROL_DISCOVERY_INPUT_VERSION] = Field(...)
    discovery_batch_id: str = Field(min_length=1)
    coverage_manifest_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    study_phase: StudyPhase
    target_units: list[ProtocolStructureUnit] = Field(min_length=1)
    context_units: list[ProtocolStructureUnit] = Field(default_factory=list)
    target_structure_unit_ids: list[str] = Field(min_length=1)
    context_structure_unit_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scope(self) -> "ProtocolControlDiscoveryAgentInput":
        target_ids = [unit.structure_unit_id for unit in self.target_units]
        context_ids = [unit.structure_unit_id for unit in self.context_units]
        if target_ids != self.target_structure_unit_ids:
            raise ValueError("发现输入 target_structure_unit_ids 必须与 target_units 一致")
        if context_ids != self.context_structure_unit_ids:
            raise ValueError("发现输入 context_structure_unit_ids 必须与 context_units 一致")
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("发现输入 target_units 不得重复")
        if len(context_ids) != len(set(context_ids)):
            raise ValueError("发现输入 context_units 不得重复")
        if set(target_ids) & set(context_ids):
            raise ValueError("发现输入 target/context 单元不得重叠")
        if any(
            unit.study_phase != self.study_phase
            for unit in (*self.target_units, *self.context_units)
        ):
            raise ValueError("发现输入结构单元期别必须与输入一致")
        return self

    @classmethod
    def from_batch(
        cls,
        batch: ProtocolControlDiscoveryBatch,
    ) -> "ProtocolControlDiscoveryAgentInput":
        return cls(
            schema_version=CONTROL_DISCOVERY_INPUT_VERSION,
            discovery_batch_id=batch.discovery_batch_id,
            coverage_manifest_id=batch.coverage_manifest_id,
            protocol_version_id=batch.protocol_version_id,
            study_phase=batch.study_phase,
            target_units=list(batch.target_units),
            context_units=list(batch.context_units),
            target_structure_unit_ids=list(batch.target_structure_unit_ids),
            context_structure_unit_ids=list(batch.context_structure_unit_ids),
        )


class _WireModel(ContractModel):
    """Explicit base keeps the provider boundary independent of domain models."""

class ProtocolControlDiscoveryWireValidationError(ValueError):
    """A first-stage provider wire error with bounded repair scope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        structure_unit_ids: Sequence[str] = (),
    ) -> None:
        self.code = code
        self.structure_unit_ids = tuple(dict.fromkeys(structure_unit_ids))
        super().__init__(f"{code}: {message}")


class ProtocolControlDiscoveryAgentWireDecision(_WireModel):
    """One coarse routing decision without any provider-created identity."""

    structure_unit_id: str = Field(min_length=1)
    disposition: ProtocolControlDiscoveryDisposition
    required_context_structure_unit_ids: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_context_scope(
        self,
    ) -> "ProtocolControlDiscoveryAgentWireDecision":
        if self.structure_unit_id in self.required_context_structure_unit_ids:
            raise ValueError("发现输出单元不得将自身声明为上下文")
        if any(
            not value.strip()
            for value in self.required_context_structure_unit_ids
        ):
            raise ValueError("发现输出所需上下文结构单元不得为空")
        if len(self.required_context_structure_unit_ids) != len(
            set(self.required_context_structure_unit_ids)
        ):
            raise ValueError("发现输出所需上下文结构单元不得重复")
        if self.required_context_structure_unit_ids != sorted(
            self.required_context_structure_unit_ids
        ):
            raise ValueError("发现输出所需上下文结构单元必须按 ID 排序")
        if (
            self.disposition
            in {
                ProtocolControlDiscoveryDisposition.CONTEXT_ONLY,
                ProtocolControlDiscoveryDisposition.NON_CONTROL,
            }
            and self.required_context_structure_unit_ids
        ):
            raise ValueError("context_only/non_control 处置不得反向声明所服务的单元")
        return self


class ProtocolControlDiscoveryAgentWire(_WireModel):
    """Provider output for one bounded discovery batch."""

    wire_version: Literal[CONTROL_DISCOVERY_WIRE_VERSION] = Field(...)
    decisions: list[ProtocolControlDiscoveryAgentWireDecision] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_unique_units(self) -> "ProtocolControlDiscoveryAgentWire":
        ids = [item.structure_unit_id for item in self.decisions]
        if len(ids) != len(set(ids)):
            raise ValueError("发现输出每个结构单元只能有一条粗筛处置")
        return self




def _validate_parallel_sources(
    source_span_ids: Sequence[str],
    source_excerpts: Sequence[str],
    *,
    label: str,
) -> None:
    if not source_span_ids or not source_excerpts:
        raise ValueError(f"{label} 必须提供直接来源定位和精确摘录")
    if len(source_span_ids) != len(source_excerpts):
        raise ValueError(f"{label} 的 source_span_ids 与 source_excerpts 必须一一对应")
    if any(not value.strip() for value in source_span_ids):
        raise ValueError(f"{label} 的 source_span_ids 不得为空")
    if any(not value.strip() for value in source_excerpts):
        raise ValueError(f"{label} 的 source_excerpts 不得为空")


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ProtocolControlAgentWireConditionAtom(_WireModel):
    """One inline condition atom; identity is intentionally absent."""

    statement: str = Field(min_length=1)
    evaluation: ControlAtomEvaluationSpec
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)
    time_constraint: TimeConstraint | None = Field(...)
    requires_professional_judgment: bool = Field(...)

    @model_validator(mode="after")
    def validate_sources(self) -> "ProtocolControlAgentWireConditionAtom":
        if self.evaluation.version != "control-atom-evaluation/v4" or "repeat_scheme" not in self.evaluation.model_fields_set:
            raise ValueError("当前解构须显式说明复查要求；没有要求填null，不沿用旧规格")
        if self.evaluation.repeat_scheme is not None:
            self.evaluation.repeat_scheme.require_current_extraction()
        validate_control_atom_evaluation(self, require_explicit=True)
        _validate_parallel_sources(
            self.source_span_ids,
            self.source_excerpts,
            label="条件原子",
        )
        return self


class ProtocolControlAgentWireConditionGroup(_WireModel):
    """A DNF conjunction: all inline atoms in this group must hold.

    Exception drafts may list:
    - ``waives_trigger_branch_indexes`` as ordinals into the trigger DNF;
    - ``activates_obligation_group_indexes`` as ordinals into the obligation DNF
      for replacement consequences when the condition holds.

    Applicability/trigger drafts must leave both lists empty.
    """

    atoms: list[ProtocolControlAgentWireConditionAtom] = Field(min_length=1)
    waives_trigger_branch_indexes: list[int] = Field(default_factory=list)
    activates_obligation_group_indexes: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scope_indexes(self) -> "ProtocolControlAgentWireConditionGroup":
        if self.waives_trigger_branch_indexes:
            if any(index < 0 for index in self.waives_trigger_branch_indexes):
                raise ValueError("例外触发分支序位必须为非负整数")
            if list(self.waives_trigger_branch_indexes) != sorted(
                set(self.waives_trigger_branch_indexes)
            ):
                raise ValueError("例外触发分支序位必须按升序排列且不得重复")
        if self.activates_obligation_group_indexes:
            if any(index < 0 for index in self.activates_obligation_group_indexes):
                raise ValueError("例外激活义务组序位必须为非负整数")
            if list(self.activates_obligation_group_indexes) != sorted(
                set(self.activates_obligation_group_indexes)
            ):
                raise ValueError("例外激活义务组序位必须按升序排列且不得重复")
        return self


class ProtocolControlAgentWireConditionDnf(_WireModel):
    """A non-empty DNF: groups are alternative paths."""

    groups: list[ProtocolControlAgentWireConditionGroup] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_groups(self) -> "ProtocolControlAgentWireConditionDnf":
        fingerprints = {
            _stable_json(group.model_dump(mode="json")) for group in self.groups
        }
        if len(fingerprints) != len(self.groups):
            raise ValueError("条件 DNF 不得包含重复替代组")
        return self


class ProtocolControlAgentWireContinuingObligation(_WireModel):
    statement: str = Field(min_length=1)
    prospective_period: ProspectivePeriod
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)
    status: Literal["not_due_at_review_node"] = Field(...)

    @model_validator(mode="after")
    def validate_sources(self) -> "ProtocolControlAgentWireContinuingObligation":
        _validate_parallel_sources(
            self.source_span_ids, self.source_excerpts, label="后续持续义务"
        )
        return self


class ProtocolControlAgentWireObligationAtom(_WireModel):
    """One typed obligation atom with direct source evidence."""

    kind: ControlObligationKind
    evaluation: ControlAtomEvaluationSpec
    statement: str = Field(min_length=1)
    time_constraint: TimeConstraint | None = Field(...)
    prospective_period: ProspectivePeriod | None = Field(...)
    continuing_obligation: ProtocolControlAgentWireContinuingObligation | None = None
    modality: ControlObligationModality = ControlObligationModality.MANDATORY
    temporal_scope: ControlTemporalScopeKind | None = None
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)
    requires_professional_judgment: bool = Field(...)

    @model_validator(mode="after")
    def validate_sources(self) -> "ProtocolControlAgentWireObligationAtom":
        if self.evaluation.version != "control-atom-evaluation/v4" or "repeat_scheme" not in self.evaluation.model_fields_set:
            raise ValueError("当前解构须显式说明复查要求；没有要求填null，不沿用旧规格")
        if self.evaluation.repeat_scheme is not None:
            self.evaluation.repeat_scheme.require_current_extraction()
        validate_control_atom_evaluation(self, require_explicit=True)
        if self.modality == ControlObligationModality.BEST_EFFORT and self.kind in (
            ControlObligationKind.PROHIBIT_EVENT,
            ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
        ):
            raise ValueError("尽力完成不得用于禁止类义务")
        if self.modality == ControlObligationModality.RECOMMENDED and self.kind in (
            ControlObligationKind.PROHIBIT_EVENT,
            ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
        ):
            raise ValueError("建议完成不得用于禁止类义务")
        if self.temporal_scope == ControlTemporalScopeKind.CALENDAR_LOOKBACK:
            if self.time_constraint is None:
                raise ValueError("日历回顾范围必须提供结构化时间窗")
        elif self.temporal_scope is not None and self.time_constraint is not None:
            raise ValueError("非日历回顾范围不得附加统一日历窗")
        _validate_parallel_sources(
            self.source_span_ids,
            self.source_excerpts,
            label="义务原子",
        )
        if self.continuing_obligation is not None:
            ControlObligationAtomDraft(
                kind=self.kind,
                evaluation=self.evaluation,
                statement=self.statement,
                time_constraint=self.time_constraint,
                prospective_period=self.prospective_period,
                continuing_obligation=(ControlContinuingObligation(
                    **self.continuing_obligation.model_dump()
                ) if self.continuing_obligation is not None else None),
                modality=self.modality,
                temporal_scope=self.temporal_scope,
                source_span_ids=self.source_span_ids,
                source_excerpts=self.source_excerpts,
                requires_professional_judgment=self.requires_professional_judgment,
            )
        if (
            self.kind == ControlObligationKind.COMPLETE_OR_VERIFY
            and self.time_constraint is not None
        ):
            if (
                self.evaluation.determination_mode != "semantic"
                or self.evaluation.time_purpose != "interval_condition"
            ):
                raise ValueError(
                    "具体操作持续期只能按带命名锚点的语义核对保存；"
                    "不得以单次值比较证明全程完成，也不得混入访视或结果有效期"
                )
        if self.kind == ControlObligationKind.COMPLETE_BEFORE_ANCHOR:
            if self.time_constraint is None:
                raise ValueError("节点前完成义务必须提供命名时间锚点")
            if self.time_constraint.direction != "before":
                raise ValueError("节点前完成义务的方向必须为 before")
        if (
            self.kind == ControlObligationKind.VERIFY_RESULT_VALIDITY
            and self.time_constraint is None
        ):
            raise ValueError("结果有效期义务必须提供结构化时间约束")
        return self


class _ObservationPolicyRepairItem(_WireModel):
    group_index: int = Field(ge=0)
    atom_index: int = Field(ge=0)
    policy: ObservationPolicy


class _ObservationPolicyRepair(_WireModel):
    items: list[_ObservationPolicyRepairItem] = Field(min_length=1)


class _EvidenceSourcePolicyRepair(_WireModel):
    policy: ControlEvidenceSourcePolicy


class _TimeOperandRepairItem(_WireModel):
    group_index: int = Field(ge=0)
    atom_index: int = Field(ge=0)
    attribute: Literal["date_range", "record_time", "unresolved"]


class _TimeOperandRepair(_WireModel):
    items: list[_TimeOperandRepairItem] = Field(min_length=1)


class ProtocolControlAgentWireObligationGroup(_WireModel):
    """Obligation conjunction optionally paired to trigger-branch ordinals."""

    atoms: list[ProtocolControlAgentWireObligationAtom] = Field(min_length=1)
    applies_to_trigger_branch_indexes: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_apply_indexes(self) -> "ProtocolControlAgentWireObligationGroup":
        if self.applies_to_trigger_branch_indexes:
            if any(index < 0 for index in self.applies_to_trigger_branch_indexes):
                raise ValueError("义务触发分支序位必须为非负整数")
            if list(self.applies_to_trigger_branch_indexes) != sorted(
                set(self.applies_to_trigger_branch_indexes)
            ):
                raise ValueError("义务触发分支序位必须按升序排列且不得重复")
        return self


class ProtocolControlAgentWireObligationDnf(_WireModel):
    groups: list[ProtocolControlAgentWireObligationGroup] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_groups(self) -> "ProtocolControlAgentWireObligationDnf":
        fingerprints = {
            _stable_json(group.model_dump(mode="json")) for group in self.groups
        }
        if len(fingerprints) != len(self.groups):
            raise ValueError("义务 DNF 不得包含重复替代组")
        return self


class ProtocolControlAgentWireExceptionDnf(ProtocolControlAgentWireConditionDnf):
    """Exception DNF remains a separate inline layer."""


class ProtocolControlAgentWireNode(_WireModel):
    """A node binding must carry an explicit role, never a free-form label."""

    workflow_stage_id: str = Field(min_length=1)
    review_stage: ReviewStage
    role: ReviewNodeRole
    guidance: str | None = Field(..., min_length=1)


class ProtocolControlAgentWireEvidence(_WireModel):
    """Evidence description; it is not an Agent-owned evidence identity."""

    fact_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    due_stage: ReviewStage
    required_source_types: list[str] = Field(...)
    workflow_stage_ids: list[str] = Field(min_length=1)
    source_policy: ControlEvidenceSourcePolicy
    atom_refs: list[ControlEvidenceAtomReference] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_source_types(self) -> "ProtocolControlAgentWireEvidence":
        if any(not value.strip() for value in self.required_source_types):
            raise ValueError("最低证据资料类型不得包含空字符串")
        if any(not value.strip() for value in self.workflow_stage_ids) or len(self.workflow_stage_ids) != len(set(self.workflow_stage_ids)):
            raise ValueError("最低证据节点身份不得为空或重复")
        return self


class ProtocolControlAgentWireRelation(_WireModel):
    """One proposal to one planner-declared external target."""

    kind: CrossSourceRelationKind
    external_target_kind: ControlRelationTargetKind
    external_target_id: str = Field(min_length=1)
    candidate_side: Literal["left", "right"]
    affected_workflow_stage_id: str | None = Field(..., min_length=1)
    notes: str | None = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_target_shape(self) -> "ProtocolControlAgentWireRelation":
        if self.external_target_kind not in {
            ControlRelationTargetKind.OFFICIAL_RULE,
            ControlRelationTargetKind.REQUIRED_PROCEDURE,
            ControlRelationTargetKind.WORKFLOW_STAGE,
        }:
            raise ValueError("关系提案只能指向规划器声明的官方规则、流程必做项或冻结流程节点")
        if self.external_target_kind == ControlRelationTargetKind.OFFICIAL_RULE:
            if not re.fullmatch(r"(IN|EX)-\d{2}", self.external_target_id):
                raise ValueError("关系提案官方目标必须是既有 IN/EX 编号")
        elif is_forbidden_protocol_control_code(self.external_target_id):
            raise ValueError("关系提案流程目标不得使用伪官方控制编号")
        if (
            self.kind == CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT
            and self.external_target_kind
            == ControlRelationTargetKind.REQUIRED_PROCEDURE
        ):
            if self.affected_workflow_stage_id is None:
                raise ValueError("补充流程必做项必须声明首次受影响的冻结审核节点")
        elif self.affected_workflow_stage_id is not None:
            raise ValueError("只有补充流程必做项可以声明受影响审核节点")
        return self


class ProtocolControlAgentWireRepeatTrigger(_WireModel):
    condition_id: str = Field(min_length=1)
    expression: ProtocolControlAgentWireConditionDnf
    evidence_roles: list[RepeatEvidenceRoleReference] = Field(...)

    @model_validator(mode="after")
    def require_complete_evidence_roles(self):
        resolve_repeat_evidence_roles(self.evidence_roles, [
            [f"{i}:{j}" for j, _ in enumerate(group.atoms)]
            for i, group in enumerate(self.expression.groups)
        ], require_complete=True)
        return self


class ProtocolControlAgentWireCandidate(_WireModel):
    """Inline candidate semantics without candidate/control identities."""

    title: str = Field(min_length=1)
    applicable_population: str = Field(min_length=1)
    applicability_expression: ProtocolControlAgentWireConditionDnf | None = Field(...)
    trigger_expression: ProtocolControlAgentWireConditionDnf | None = Field(...)
    obligation_expression: ProtocolControlAgentWireObligationDnf = Field(...)
    exception_expression: ProtocolControlAgentWireExceptionDnf | None = Field(...)
    repeat_trigger_conditions: list[ProtocolControlAgentWireRepeatTrigger] = Field(...)
    review_node_bindings: list[ProtocolControlAgentWireNode] = Field(min_length=1)
    minimum_evidence: list[ProtocolControlAgentWireEvidence] = Field(min_length=1)
    source_structure_unit_ids: list[str] = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    cross_source_relations: list[ProtocolControlAgentWireRelation] = Field(...)

    @model_validator(mode="before")
    @classmethod
    def canonicalize_source_id_sets(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for field in ("source_structure_unit_ids", "source_span_ids"):
            ids = normalized.get(field)
            if isinstance(ids, list) and all(isinstance(item, str) for item in ids):
                normalized[field] = sorted(set(ids))
        return normalized

    @model_validator(mode="after")
    def validate_scope(self) -> "ProtocolControlAgentWireCandidate":
        validate_control_repeat_conditions(self)
        conditions = {item.condition_id: item for item in self.repeat_trigger_conditions}
        for expression in (self.applicability_expression, self.trigger_expression,
                           self.obligation_expression, self.exception_expression):
            for group in expression.groups if expression is not None else ():
                for atom in group.atoms:
                    scheme = atom.evaluation.repeat_scheme if atom.evaluation is not None else None
                    if scheme is not None and scheme.permission == "investigator_discretion":
                        permission = conditions[scheme.permission_condition_id]
                        if not any(item.requires_professional_judgment for branch in permission.expression.groups
                                   for item in branch.atoms):
                            raise ValueError("研究者复查许可须保留书面判断条件，不得改成普通语义或签名条件")
        _require_sorted_unique(self.source_structure_unit_ids, "候选 source_structure_unit_ids")
        _require_sorted_unique(self.source_span_ids, "候选 source_span_ids")
        node_keys = [
            (item.workflow_stage_id, item.review_stage.value, item.role.value)
            for item in self.review_node_bindings
        ]
        if len(node_keys) != len(set(node_keys)):
            raise ValueError("候选审核节点作用不得重复")
        node_locations = [
            (item.workflow_stage_id, item.review_stage.value)
            for item in self.review_node_bindings
        ]
        if len(node_locations) != len(set(node_locations)):
            raise ValueError("同一审核节点不得绑定多个不同作用")
        relation_keys = [
            (
                item.kind.value,
                item.external_target_kind.value,
                item.external_target_id,
                item.candidate_side,
                item.affected_workflow_stage_id,
            )
            for item in self.cross_source_relations
        ]
        if len(relation_keys) != len(set(relation_keys)):
            raise ValueError("候选关系提案不得重复")
        atom_spans: set[str] = set()
        for expression in (
            self.applicability_expression,
            self.trigger_expression,
            self.exception_expression,
        ):
            if expression is not None:
                atom_spans.update(
                    span_id
                    for group in expression.groups
                    for atom in group.atoms
                    for span_id in atom.source_span_ids
                )
        atom_spans.update(
            span_id
            for group in self.obligation_expression.groups
            for atom in group.atoms
            for span_id in atom.source_span_ids
        )
        if not atom_spans <= set(self.source_span_ids):
            raise ValueError("候选 source_span_ids 必须覆盖全部原子直接来源")
        return self


class ProtocolControlAgentWireDisposition(_WireModel):
    """Disposition for one frozen owned unit; no candidate index/reference."""

    structure_unit_id: str = Field(min_length=1)
    disposition: StructureUnitDispositionKind
    linked_official_code: str | None = Field(...)
    linked_procedure_catalog_item_id: str | None = Field(...)
    linked_procedure_catalog_item_ids: list[str] = Field(...)
    notes: str | None = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_links(self) -> "ProtocolControlAgentWireDisposition":
        _require_sorted_unique(
            self.linked_procedure_catalog_item_ids,
            "linked_procedure_catalog_item_ids",
        )
        if (
            self.linked_procedure_catalog_item_id is not None
            and self.linked_procedure_catalog_item_ids
        ):
            raise ValueError("流程必做处置不得同时使用单项目标和多项目标字段")
        procedure_target_ids = self.linked_procedure_catalog_item_ids or (
            [self.linked_procedure_catalog_item_id]
            if self.linked_procedure_catalog_item_id is not None
            else []
        )
        if self.linked_official_code is not None:
            if not re.fullmatch(r"(IN|EX)-\d{2}", self.linked_official_code):
                raise ValueError("结构单元只能链接既有 IN/EX 编号")
            if self.disposition != StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY:
                raise ValueError("只有官方入排处置可以链接 IN/EX")
        if procedure_target_ids:
            if self.disposition != StructureUnitDispositionKind.REQUIRED_PROCEDURE:
                raise ValueError("只有流程必做处置可以链接流程目录项")
        if (
            self.disposition == StructureUnitDispositionKind.REQUIRED_PROCEDURE
            and not procedure_target_ids
        ):
            raise ValueError("流程必做处置必须链接一个或多个访视级流程目录项")
        return self


class ProtocolControlAgentWire(_WireModel):
    """Strict, reference-free provider output for one planned batch."""

    wire_version: Literal[CONTROL_AGENT_WIRE_VERSION] = Field(...)
    dispositions: list[ProtocolControlAgentWireDisposition] = Field(min_length=1)
    candidate_drafts: list[ProtocolControlAgentWireCandidate] = Field(...)

    @model_validator(mode="after")
    def validate_unique_dispositions(self) -> "ProtocolControlAgentWire":
        ids = [item.structure_unit_id for item in self.dispositions]
        if len(ids) != len(set(ids)):
            raise ValueError("每个 owned 结构单元只能有一条处置")
        fingerprints = {
            _stable_json(item.model_dump(mode="json")) for item in self.candidate_drafts
        }
        if len(fingerprints) != len(self.candidate_drafts):
            raise ValueError("候选语义草稿不得重复")
        return self


class _PostTreatmentAtomRef(_WireModel):
    group_index: int = Field(ge=0)
    atom_index: int = Field(ge=0)


class _PostTreatmentScopeRepair(_WireModel):
    """A semantic deletion decision; unchanged atoms stay owned by the prior wire."""

    removed_atoms: list[_PostTreatmentAtomRef] = Field(min_length=1)
    removed_unit_dispositions: list[ProtocolControlAgentWireDisposition] = Field(min_length=1)
    title: str = Field(min_length=1)
    review_node_bindings: list[ProtocolControlAgentWireNode] = Field(min_length=1)
    minimum_evidence: list[ProtocolControlAgentWireEvidence] = Field(min_length=1)
    cross_source_relations: list[ProtocolControlAgentWireRelation]


# Descriptive aliases make the adapter discoverable without introducing a
# second implementation or a compatibility import from the official Agent.
ProtocolControlAgentWireNodeBinding = ProtocolControlAgentWireNode
ProtocolControlAgentWireBatch = ProtocolControlAgentWire


def _require_sorted_unique(values: Sequence[str], label: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError(f"{label} 不得包含空 ID")
    if list(values) != sorted(set(values)):
        raise ValueError(f"{label} 必须按 ID 排序且不得重复")


def _validation_error_summary(exc: ValidationError) -> str:
    pieces: list[str] = []
    for error in exc.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in error["loc"])
        pieces.append(f"{location}: {error['msg']}")
    return "；".join(pieces)


_FORBIDDEN_PROVIDER_KEYS = frozenset(
    {
        "schema_version",
        "batch_id",
        "discovery_batch_id",
        "coverage_manifest_id",
        "manifest_structure_unit_ids",
        "manifest_structure_unit_count",
        "manifest_structure_unit_ids_sha256",
        "expected_structure_unit_ids",
        "target_structure_unit_ids",
        "context_structure_unit_ids",
        "candidate_id",
        "control_candidate_id",
        "candidate_ref",
        "condition_atom_id",
        "obligation_id",
        "atom_id",
        "predicate_id",
        "evidence_key",
        "relation_id",
        "node_id",
        "root_node_id",
        "created_by_agent_call_id",
        "candidate_draft_indexes",
        "linked_control_candidate_id",
        "linked_control_candidate_ids",
    }
)


def _find_forbidden_provider_key(value: object, path: str = "") -> tuple[str, str] | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            # This schema-local comparison label is not a published atom ID.
            local_predicate = key == "predicate_id" and re.fullmatch(
                r"(?:candidate_drafts\[\d+\]\."
                r"(?:(?:applicability|trigger|obligation|exception)_expression|"
                r"repeat_trigger_conditions\[\d+\]\.expression)"
                r"\.groups\[\d+\]\.atoms\[\d+\]|atom)\.evaluation\.predicate",
                path,
            ) is not None
            if key in _FORBIDDEN_PROVIDER_KEYS and not local_predicate:
                return key, f"{path}.{key}" if path else key
            found = _find_forbidden_provider_key(child, f"{path}.{key}" if path else key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_forbidden_provider_key(child, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def parse_protocol_control_agent_wire(text: str) -> ProtocolControlAgentWire:
    """Parse only the provider wire; context-dependent checks happen later."""

    if not text or not text.strip():
        raise ProtocolControlAgentWireValidationError("EMPTY_OUTPUT", "模型返回空输出")
    stripped = text.strip()
    if stripped.startswith("```"):
        raise ProtocolControlAgentWireValidationError(
            "MARKDOWN_OUTPUT",
            "模型输出不得包含 Markdown 代码块",
        )
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ProtocolControlAgentWireValidationError(
            "INVALID_JSON",
            f"模型输出不是合法 JSON：{exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise ProtocolControlAgentWireValidationError(
            "TOP_LEVEL_NOT_OBJECT",
            "模型输出顶层必须是 JSON 对象",
        )
    forbidden = _find_forbidden_provider_key(payload)
    if forbidden is not None:
        key, path = forbidden
        raise ProtocolControlAgentWireValidationError(
            "PROVIDER_ID_FORBIDDEN",
            f"provider 不得生成系统身份字段 {path}（{key}）",
        )
    _collapse_exact_duplicate_day_bounds(payload)
    try:
        return ProtocolControlAgentWire.model_validate(payload)
    except ValidationError as exc:
        raise ProtocolControlAgentWireValidationError(
            "WIRE_SCHEMA_INVALID",
            _validation_error_summary(exc),
        ) from exc


def _collapse_exact_duplicate_day_bounds(value: object) -> None:
    """Remove only identical day bounds expressed twice in a provider wire."""

    if isinstance(value, list):
        for child in value:
            _collapse_exact_duplicate_day_bounds(child)
        return
    if not isinstance(value, dict):
        return
    constraint = value.get("time_constraint")
    if isinstance(constraint, dict):
        for prefix in ("lower", "upper"):
            days_key = f"{prefix}_bound_days"
            quantity_key = f"{prefix}_bound"
            days = constraint.get(days_key)
            quantity = constraint.get(quantity_key)
            if (
                type(days) is int
                and isinstance(quantity, dict)
                and quantity.get("unit") == "day"
                and type(quantity.get("value")) is int
                and quantity["value"] == days
            ):
                constraint.pop(quantity_key)
    for child in value.values():
        _collapse_exact_duplicate_day_bounds(child)
def parse_protocol_control_discovery_agent_wire(
    text: str,
) -> ProtocolControlDiscoveryAgentWire:
    """Parse one bounded first-stage provider output."""

    if not text or not text.strip():
        raise ProtocolControlDiscoveryWireValidationError(
            "EMPTY_OUTPUT",
            "发现阶段模型返回空输出",
        )
    stripped = text.strip()
    if stripped.startswith("```"):
        raise ProtocolControlDiscoveryWireValidationError(
            "MARKDOWN_OUTPUT",
            "发现阶段模型输出不得包含 Markdown 代码块",
        )
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ProtocolControlDiscoveryWireValidationError(
            "INVALID_JSON",
            f"发现阶段模型输出不是合法 JSON：{exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise ProtocolControlDiscoveryWireValidationError(
            "TOP_LEVEL_NOT_OBJECT",
            "发现阶段模型输出顶层必须是 JSON 对象",
        )
    forbidden = _find_forbidden_provider_key(payload)
    if forbidden is not None:
        key, path = forbidden
        raise ProtocolControlDiscoveryWireValidationError(
            "PROVIDER_ID_FORBIDDEN",
            f"发现阶段 provider 不得生成系统身份字段 {path}（{key}）",
        )
    decisions = payload.get("decisions")
    if isinstance(decisions, list):
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            context_ids = decision.get("required_context_structure_unit_ids")
            if isinstance(context_ids, list) and all(
                isinstance(value, str) for value in context_ids
            ):
                # This reference closure is set-like. The system owns its
                # canonical order; duplicates and semantic errors still fail
                # in the typed validator below.
                decision["required_context_structure_unit_ids"] = sorted(
                    context_ids
                )
    try:
        return ProtocolControlDiscoveryAgentWire.model_validate(payload)
    except ValidationError as exc:
        raise ProtocolControlDiscoveryWireValidationError(
            "WIRE_SCHEMA_INVALID",
            _validation_error_summary(exc),
        ) from exc


def validate_protocol_control_discovery_agent_wire(
    wire: ProtocolControlDiscoveryAgentWire,
) -> ProtocolControlDiscoveryAgentWire:
    """Revalidate one parsed discovery wire at the provider boundary."""

    try:
        return ProtocolControlDiscoveryAgentWire.model_validate(
            wire.model_dump(mode="json")
        )
    except ValidationError as exc:
        raise ProtocolControlDiscoveryWireValidationError(
            "WIRE_SCHEMA_INVALID",
            _validation_error_summary(exc),
        ) from exc


def wire_to_protocol_control_discovery_decisions(
    wire: ProtocolControlDiscoveryAgentWire,
) -> tuple[ProtocolControlDiscoveryDecision, ...]:
    wire = validate_protocol_control_discovery_agent_wire(wire)
    return tuple(
        ProtocolControlDiscoveryDecision(
            structure_unit_id=decision.structure_unit_id,
            disposition=decision.disposition,
            required_context_structure_unit_ids=list(
                decision.required_context_structure_unit_ids
            ),
            rationale=decision.rationale,
        )
        for decision in wire.decisions
    )
def bind_protocol_control_discovery_wire(
    wire: ProtocolControlDiscoveryAgentWire,
    batch: ProtocolControlDiscoveryBatch | ProtocolControlDiscoveryAgentInput,
) -> tuple[ProtocolControlDiscoveryDecision, ...]:
    """Bind one wire response to the system-owned batch scope.

    The provider may echo frozen structure-unit IDs, but it cannot choose the
    batch, create identities, omit targets, or widen the read-only context.
    Stable manifest closure remains the planner's responsibility.
    """

    wire = validate_protocol_control_discovery_agent_wire(wire)
    discovery_input = (
        batch
        if isinstance(batch, ProtocolControlDiscoveryAgentInput)
        else ProtocolControlDiscoveryAgentInput.from_batch(batch)
    )
    expected_ids = list(discovery_input.target_structure_unit_ids)
    actual_ids = [decision.structure_unit_id for decision in wire.decisions]
    expected_set = set(expected_ids)
    actual_set = set(actual_ids)
    if actual_ids != expected_ids:
        missing = [unit_id for unit_id in expected_ids if unit_id not in actual_set]
        extra = [unit_id for unit_id in actual_ids if unit_id not in expected_set]
        raise ProtocolControlDiscoveryWireValidationError(
            "BATCH_SCOPE_MISMATCH",
            "发现输出必须按冻结 target_units 原文顺序逐项闭合；"
            f"missing={missing}, extra={extra}",
            structure_unit_ids=tuple(dict.fromkeys((*missing, *extra))),
        )

    available_context_ids = expected_set | set(discovery_input.context_structure_unit_ids)
    for decision in wire.decisions:
        out_of_scope = [
            context_id
            for context_id in decision.required_context_structure_unit_ids
            if context_id not in available_context_ids
        ]
        if out_of_scope:
            raise ProtocolControlDiscoveryWireValidationError(
                "CONTEXT_SCOPE_ESCAPE",
                "发现输出所需上下文不得越出当前冻结批次可见范围："
                + "、".join(out_of_scope),
                structure_unit_ids=(decision.structure_unit_id, *out_of_scope),
            )
    bound_decisions = wire_to_protocol_control_discovery_decisions(wire)
    required_context_ids = {
        context_id
        for decision in bound_decisions
        if decision.disposition in {
            ProtocolControlDiscoveryDisposition.CANDIDATE,
            ProtocolControlDiscoveryDisposition.UNCERTAIN,
        }
        for context_id in decision.required_context_structure_unit_ids
    }
    return tuple(
        ProtocolControlDiscoveryDecision(
            structure_unit_id=expected_id,
            disposition=(
                ProtocolControlDiscoveryDisposition.CONTEXT_ONLY
                if expected_id in required_context_ids
                and decision.disposition == ProtocolControlDiscoveryDisposition.NON_CONTROL
                else decision.disposition
            ),
            required_context_structure_unit_ids=list(
                decision.required_context_structure_unit_ids
            ),
            rationale=(
                decision.rationale
                + "；原输出标为 non_control，但同批候选明确引用为必要上下文，"
                "系统仅保留上下文，不生成独立审核要求。"
                if expected_id in required_context_ids
                and decision.disposition == ProtocolControlDiscoveryDisposition.NON_CONTROL
                else decision.rationale
            ),
        )
        for expected_id, decision in zip(
            expected_ids, bound_decisions, strict=True
        )
    )


def hydrate_protocol_control_discovery_agent_output(
    text: str,
    batch: ProtocolControlDiscoveryBatch | ProtocolControlDiscoveryAgentInput,
) -> tuple[ProtocolControlDiscoveryDecision, ...]:
    """Parse and bind one discovery response without creating identities."""

    try:
        wire = parse_protocol_control_discovery_agent_wire(text)
        return bind_protocol_control_discovery_wire(wire, batch)
    except ProtocolControlDiscoveryWireValidationError:
        raise
    except (ValidationError, ValueError) as exc:
        raise ProtocolControlDiscoveryWireValidationError(
            "OUTPUT_INVALID",
            str(exc),
        ) from exc



discovery_wire_to_protocol_control_decisions = (
    wire_to_protocol_control_discovery_decisions
)

def wire_to_protocol_control_discovery_results(
    wires: Sequence[ProtocolControlDiscoveryAgentWire],
) -> tuple[tuple[ProtocolControlDiscoveryDecision, ...], ...]:
    """Bind parsed provider outputs to the planned batch order."""

    return tuple(
        wire_to_protocol_control_discovery_decisions(wire)
        for wire in wires
    )


def protocol_control_discovery_agent_json_schema() -> dict[str, object]:
    return deepcopy(ProtocolControlDiscoveryAgentWire.model_json_schema())


def protocol_control_discovery_agent_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": CONTROL_DISCOVERY_RESPONSE_FORMAT_NAME,
            "strict": True,
            "schema": protocol_control_discovery_agent_json_schema(),
        },
    }

def protocol_control_discovery_prompt_template_sha256(
    prompt_template: str,
) -> str:
    payload = "\n\n".join(
        (
            CONTROL_DISCOVERY_PROMPT_VERSION,
            prompt_template.strip(),
            _DISCOVERY_SYSTEM_CONTRACT,
            _stable_json(protocol_control_discovery_agent_json_schema()),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()




def protocol_control_agent_json_schema() -> dict[str, object]:
    """Return the strict schema used in the prompt/provider response format."""

    schema = deepcopy(ProtocolControlAgentWire.model_json_schema())
    from app.domain.contracts.observation_selection import ObservationOrdering
    if "ObservationOrdering" in schema.get("$defs", {}):
        schema["$defs"]["ObservationOrdering"] = ObservationOrdering.provider_json_schema()
    if "RepeatScheme" in schema.get("$defs", {}):
        schema["$defs"]["RepeatScheme"]["properties"]["version"] = {
            "type": "string", "const": "repeat-scheme/v4",
        }

    def normalize_provider_schema(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                normalize_provider_schema(item)
            return
        if not isinstance(value, dict):
            return
        # MTPLX strict output does not implement conditional JSON Schema.
        # Hydration still enforces these TimeConstraint rules in Python.
        for key in ("if", "then", "else"):
            value.pop(key, None)
        properties = value.get("properties")
        if isinstance(properties, dict) and properties:
            value["required"] = list(properties)
        for child in value.values():
            normalize_provider_schema(child)

    normalize_provider_schema(schema)
    return schema


def protocol_control_agent_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_agent_wire_v1",
            "strict": True,
            "schema": protocol_control_agent_json_schema(),
        },
    }


def protocol_control_candidate_repair_response_format() -> dict[str, object]:
    """Ask for one candidate only; the system retains the rest of the wire."""

    original = protocol_control_agent_json_schema()
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_candidate_repair_v1",
            "strict": True,
            "schema": {
                "$defs": original["$defs"],
                "type": "object",
                "properties": {
                    "candidate_draft": {
                        "$ref": "#/$defs/ProtocolControlAgentWireCandidate"
                    }
                },
                "required": ["candidate_draft"],
                "additionalProperties": False,
            },
        },
    }


def protocol_control_post_treatment_repair_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_post_treatment_repair_v1",
            "strict": True,
            "schema": _PostTreatmentScopeRepair.model_json_schema(),
        },
    }


def protocol_control_atom_repair_response_format() -> dict[str, object]:
    """Restrict a structural repair to one obligation atom."""

    original = protocol_control_agent_json_schema()
    definitions = original["$defs"]
    reachable: set[str] = set()
    pending: list[str] = ["ProtocolControlAgentWireObligationAtom"]
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        definition = definitions[name]
        stack: list[object] = [definition]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                ref = value.get("$ref")
                if isinstance(ref, str) and ref.startswith("#/$defs/"):
                    pending.append(ref.removeprefix("#/$defs/"))
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_atom_repair_v1",
            "strict": True,
            "schema": {
                "$defs": {name: definitions[name] for name in definitions if name in reachable},
                "type": "object",
                "properties": {
                    "atom": {"$ref": "#/$defs/ProtocolControlAgentWireObligationAtom"}
                },
                "required": ["atom"],
                "additionalProperties": False,
            },
        },
    }


def protocol_control_observation_repair_response_format() -> dict[str, object]:
    """Only observation-selection policies, not rewritten obligations."""

    schema = _ObservationPolicyRepair.model_json_schema()

    def require_properties(value: object) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict):
                value["required"] = list(properties)
            for child in value.values():
                require_properties(child)
        elif isinstance(value, list):
            for child in value:
                require_properties(child)

    require_properties(schema)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_observation_repair_v1",
            "strict": True,
            "schema": schema,
        },
    }


def protocol_control_evidence_source_repair_response_format() -> dict[str, object]:
    """One evidence-source policy, without the surrounding candidate."""

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_evidence_source_repair_v1",
            "strict": True,
            "schema": _EvidenceSourcePolicyRepair.model_json_schema(),
        },
    }


def protocol_control_time_operand_repair_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_time_operand_repair_v1",
            "strict": True,
            "schema": _TimeOperandRepair.model_json_schema(),
        },
    }


def protocol_control_candidates_repair_response_format() -> dict[str, object]:
    """Return only the selected candidate drafts in frozen index order."""

    original = protocol_control_agent_json_schema()
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_candidates_repair_v1",
            "strict": True,
            "schema": {
                "$defs": original["$defs"],
                "type": "object",
                "properties": {
                    "candidate_drafts": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/ProtocolControlAgentWireCandidate"},
                    }
                },
                "required": ["candidate_drafts"],
                "additionalProperties": False,
            },
        },
    }


DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE = (
    "请对本次冻结的方案结构单元逐项完成其他方案控制候选审阅，并严格返回指定 JSON。"
)
DEFAULT_PROTOCOL_CONTROL_DISCOVERY_PROMPT_TEMPLATE = (
    "请对本次发现批次中的结构单元完成高召回粗筛，并严格返回指定 JSON。"
)

_DISCOVERY_SYSTEM_CONTRACT = (
    "你是原始方案结构清单的高召回候选发现助手，不是深度语义解构助手。"
    "只对输入中的 target_units 做粗筛；context_units 仅供理解标题路径、表格语境、交叉引用和相邻原文，"
    "不得处置、不得作为候选来源，也不得转移 target_units 的所有权。"
    "每个 target_structure_unit_id 必须恰好返回一条 decision，disposition 只能是 candidate、context_only、"
    "non_control 或 uncertain，并用 rationale 简要说明处置依据。candidate 表示该单元可能独立规定、补充或改变"
    "预筛、筛选、导入、基线、随机或首次给药前的适用人群、条件、动作、时间、阈值、例外、所需资料或判定方式；"
    "它既包括正式入选/排除条款，也包括流程表、检查评估、合并用药/治疗、访视安排、操作方法、附录和其他章节中"
    "可能影响入排审核的控制要求。候选必须由该单元自身当前有效的规范内容支持；仅指向相关章节不等于"
    "该单元自身规定了要求。context_only 表示该单元本身不形成独立控制，但必须与另一 candidate 或 uncertain"
    "单元共同阅读。non_control 表示该单元没有独立的当前入排审核控制内容，包括治疗后执行、行政统计、"
    "纯背景及无需作为其他候选上下文的导航性文字；"
    "中心、研究者或申办方的研究启动准备、人员培训、授权、文件归档、监查稽查或系统管理义务，若未明确约束某一"
    "受试者的资格判断、节点放行或个例证据，应标为 non_control。‘研究启动前’或‘任何研究操作前’只说明项目或中心"
    "义务的时序，不能单独将其变成受试者入排控制。若同一 target_unit 还包含明确的受试者层面控制，应标为 candidate；"
    "当前原文不足以区分义务对象时标为 uncertain。目录标题和页码仅是定位指针：如需帮助理解另一候选"
    "则作 context_only，否则作 non_control，不得因为所指章节可能有要求就把目录项本身标为 candidate 或"
    "uncertain。修订记录若仅描述曾经修改或优化某项标准，而没有写出当前生效的受试者要求，也不独立产生"
    "候选；若原文确实载有当前生效的完整要求，按其实际内容处置。摘要或背景中真正陈述了当前筛选、导入、"
    "基线或给药前条件时仍可为 candidate，不得仅因位于摘要而排除。"
    "被其他单元声明为必要上下文时不得标为 non_control。uncertain 表示当前可见原文不足以可靠区分前三类，必须进入"
    "深度分析。候选发现必须保持高召回：不能依据关键词、优先级、章节名称、单一命中或文本长度过滤结构单元；"
    "不能因为内容未出现在‘入选标准’或‘排除标准’章节就降低等级；有潜在规范内容但条件、对象或适用期别"
    "确实无法从已给来源判清时使用 uncertain，不得把临床不确定默认为 non_control；纯导航或历史叙述"
    "缺少规范内容不是临床不确定。"
    "wire_version 必须固定为 phase5/control-discovery-wire/v1；"
    "只有 candidate 或 uncertain 可以用 required_context_structure_unit_ids 正向列出完成其深析所需的"
    "其他单元；context_only 或 non_control 的该字段必须为空，不得反向列出它服务的候选。"
    "required_context_structure_unit_ids 只能引用本输入已提供的 target_units 或 context_units 的结构单元身份，"
    "该列表按结构单元 ID 升序排列且不得重复，"
    "不得创建候选、批次、控制或其他稳定身份，不得输出额外字段。只返回一个完整 JSON 对象。"
)

_CONTROL_AGENT_SYSTEM_CONTRACT = (
    "你是其他方案控制候选语义解构助手，不是官方 IN/EX 解构助手。"
    "每个条件和义务原子都须填写evaluation：proposition明确本原子成立的含义，不是最终入排结论；"
    "按原文区分deterministic、semantic和investigator_judgment，不按义务kind自动选择。"
    "确定性值比较用value_comparison和predicate，比较必须直接表达本原子成立，不依靠后续按禁令名称取反；"
    "使用value_comparison时evaluation.operand_attribute必须为value；日期属性只能用time_constraint计算，"
    "研究者书面判断不能伪装成值比较。"
    "每个值比较的 evaluation.predicate 必须填写 source_clause 或 source_clauses，逐字保留比较依据；"
    "该片段还必须完整包含在同一 evaluation.source_excerpts 中，不能仅填 source_term。"
    "predicate_id仅为本规格内局部标识，不是控制或事实身份。日期约束计算用time_constraint，"
    "并明确使用date_range还是record_time，不能把记录日期冒充事件日期。"
    "evaluation.version使用control-atom-evaluation/v4。值比较、语义或研究者判断如附有时间条件，"
    "须另用time_operand_attribute声明核对时间的日期属性，后续代码独立核算时间，不由语义关系代替。"
    "单独时间计算只用operand_attribute，没有附加时间条件时time_operand_attribute为null。"
    "time_purpose区分事件筛选范围、临床间隔条件和来源有效期；不能区分时保留unresolved，"
    "没有时间约束才写not_applicable；带时间约束的新义务须区分通用访视安排、结果有效期、"
    "以及具体治疗或操作的持续期。具体治疗/操作持续期用complete_or_verify，"
    "evaluation.determination_mode=semantic、time_purpose=interval_condition，"
    "原文命名锚点和期间写入time_constraint；proposition须保留动作、对象与完整持续要求，"
    "不能凭单次记录或仅凭药名值比较证明持续期完成。"
    "每个原子的来源定位只能用source_clause与source_clauses之一，"
    "不得同时填两类。求值规格必须说明观察选择规则（一次、任一次或全部记录），"
    "原文不足时明确标unverified；确定性求值必须声明computation方式，"
    "semantic与investigator_judgment模式不得夹带任何computation字段。语义或研究者判断模式operation和predicate均为null。"
    "语义任务不能确定所需事实属性时operand_attribute为null，不为填字段虚构操作数。"
    "未找到记录不等于事件未发生；不要用任意占位值加ne比较器表示无病史，也不要反向解释exists。"
    "source_span_ids和source_excerpts必须逐项取自本原子的原文；比较的阈值、单位和方向均须有原文依据。"
    "有发生次数或发生天数期间时，用predicate.occurrence_window保存duration/minimum_count及scope，"
    "scope.version=occurrence-scope/v4，kind区分anchored_lookback、calendar_period、anchored_period、"
    "any_consecutive、unresolved，quantifier按原文为single/every/any/unresolved；仅锚定型填anchor_type。"
    "明确回溯时长但未命名锚点用unanchored_lookback、single、anchor_type=null，实际由当前"
    "筛选/基线应用政策分别回溯，不把应用政策伪装为方案原文命名日期。"
    "source_excerpts保留本条件逐字依据，不把每月默认成日历月；不明确时填写unresolved及具体原因。"
    "scope.start_inclusive/end_inclusive按原文保留统计期间是否含起止当天，未能从方案确定填null，"
    "不得默认两个端点均包含。"
    "多个期间另填occurrence_window.horizon，原文起止日期用explicit_dates、命名节点对用anchor_span、"
    "明示相对统计范围用relative_window；原文明示不限期间才用unbounded，不明用unresolved并保留"
    "疑问及逐字依据。single的horizon为null，不从外层时间筛选自动借用。scope.boundary_periods"
    "按原文为full_only/include_partial/unresolved，任一或每一期间均须核对，不按比例折算阈值。"
    "日历周起始星期仅明确时写calendar_week_start，否则null，非周周期也为null。周期长度沿用"
    "duration；每30天不等于任意连续30天，未明对齐不能改成滑动。"
    "连续或锚定期间以scope.duration_basis保留calendar_span（日历跨度如4周为28个日历日、"
    "两端均计入）或boundary_offset（从边界偏移时长，再依原文开闭决定计入）；未明用unresolved，"
    "其他期间为null。不得把4周日历跨度算成29天或强行半开以掩盖未明定义。"
    "频次期间已声明时evaluation.observation_policy和repeat_scheme均为null，不把计数简化为观察选择；"
    "其与复查的先后规则尚无结构表达时保留完整原文并报告未决。其他求值模式须observation_policy，"
    "保存原文限定的观察范围scope、逐字来源和mode："
    "single是明确的一项观察，any是该范围任一次满足，all是该范围每一次均满足。"
    "不能依据病例恰好只有一项或多项来反推方案规则。任一模式如原文明示采用最近或最早一次，"
    "在single政策下提供selection：criterion为latest/earliest，ordering_attribute为date_range。"
    "日期选择不证明内容或研究者判断适用，仍须逐原文核实。条件性复查触发/授权/独立时限/替代或聚合尚不能表示时，"
    "用unresolved并在scope保留完整要求；不以次数证明复查许可，不简化为any/all。"
    "观察政策只写在evaluation.observation_policy，内层predicate.observation_policy省略或null。"
    "复查采用要求只写在evaluation.repeat_scheme，内层predicate.repeat_scheme填null；没有该要求也显式填null。"
    "复查方案使用repeat-scheme/v4；multi_initial_result仅在原文明示多组初查的结果采用顺序时填写："
    "per_initial_then_all或per_initial_then_any表示每组先按复查规则采用结果，再要求各组全部或任一满足；"
    "保留对应source_excerpts。原文未涉及填null，涉及但先后顺序不明填unresolved。"
    "不得从已有observation_policy、记录数量、日期或有利结果推断这种顺序。"
    "条件性复查通过trigger_condition_id引用本候选repeat_trigger_conditions"
    "中的局部condition_id，每项expression保留完整条件DNF；没有时填空数组。该条件不属于四层控制逻辑，"
    "明确要求研究者许可时，用permission_condition_id引用该数组中的另一完整许可命题，不能与触发条件"
    "共用编号；investigator_discretion必须提供此引用。许可保留决定者、检查对象、原文限定时间，"
    "要求明确同意或决定复查的书面内容，而不是签名或普通病情判断。原文无额外批准要求时填null。"
    "其中研究者作出同意或决定的原子须requires_professional_judgment=true，"
    "evaluation.determination_mode=investigator_judgment，保留具体许可命题；其他事实子条件维持其原类型。"
    "触发条件的作用范围不得从time_limit.reference推断。附加条件"
    "逐原子填写evidence_roles，以零起算group_index/atom_index引用expression.groups中的atoms；"
    "evidence_role.role按原文填写initial_observation、preceding_observation、target_observation、external_context或unresolved，"
    "source_excerpts保留支持取证范围的逐字原文；许可针对本次复查时使用target_observation，仅用于许可条件，"
    "须明确检查对象，不因日期接近推断适用，不将单次许可扩展到其他复查。初查/前次检验与外部用药背景分别标明。"
    "原文未明填unresolved，不把混合条件树套同一检查范围，不用本次复查结果证明自身触发。附加条件"
    "不能激活、豁免或替代入排分支，其原子evaluation.repeat_scheme必须为null。明确次数同时声明"
    "count_scope为per_initial_acquisition/per_current_episode/unresolved；合并结果同时声明"
    "result_combine为sum/mean/minimum/maximum/all/any/unresolved，同时声明result_population："
    "initial_and_repeats包含初查及复查、repeats_only仅复查；原文未明或是其他范围用unresolved，"
    "不猜范围或默认取最佳值。非combine的result_population填null。"
    "no_repeat_result_use独立按原文填写retain_initial（明示可采用初查）、no_result（明示必须有复查才可采用）"
    "或unresolved（无明确规定/无法确定）；不能因optional或未见记录推断退回初查，也不证明复查未发生或资料齐全。"
    "原文明示触发条件不成立可用初查时用retain_initial_when_trigger_false，必须引用完整trigger_condition_id；"
    "未核实和缺记录不表示条件不成立。"
    "保留逐字来源、许可/必做/禁止/研究者决定、触发条件、次数、期限和结果采用方式；未规定与未核实须区分。"
    "不能以日期先后推断复查关系，不能默认一次、无限次或最后/最有利结果；明确最后一次才用use_last_repeat，"
    "仅明确以复查为准用use_single_repeat，尚不能表达的限制保留原文并标unresolved。"
    "原文未规定结果采用方式时result_use为not_specified；有相关措辞但未核清为unresolved。"
    "期限明确初查/前次检查/方案节点参照及开闭边界，月年不换成固定天数；条件与研究者许可不在解构时判真。"
    "selection须明确window_order：within_window先限时间范围再选记录，before_window_check先选记录再核时间，"
    "not_applicable仅在无时间约束时使用；原文不能确定顺序则unresolved，不默认改选更旧的有效记录。"
    "这些模式表达本原子proposition，不按入选、排除或义务类别自动交换量词。"
    "资料存在、签名存在、行动已办结均不证明履约；不得为强行确定性计算改写或简化要求。"
    "你只处理本次输入中owned_units的结构单元；context_units仅作只读上下文，不能处置、不能转移所有权。"
    "只读上下文可以帮助解释术语、访视和重复关系，但它本身不是已发布目标；只有输入中明确列出的"
    "known_official_targets、known_procedure_targets 或 known_workflow_stage_targets，且当前处置或候选"
    "建立了相应链接时，才能据此判定某项内容已被覆盖。只读上下文出现相似或重复表述，不能单独作为"
    "丢弃 owned_unit 中独立人群、条件、动作、时间、阈值、例外或完成强度的理由。"
    "每个 owned_unit 必须恰好有一条 disposition。可以有 0 个候选；但没有候选时，"
    "凡不是已链接冻结官方 IN/EX 或流程必做目标的非候选处置，都必须给出明确、具体的非控制理由，"
    "不能仅返回空数组。"
    "本项目期别已经由上游冻结；原文明确仅属于其他期别的内容不得成为本期候选。首次给药后或"
    "治疗期内才执行、且不影响筛选/基线入排判定的检查或随访，应处置为 post_treatment_execution，"
    "不得绑定到筛选或基线审核节点。"
    "但章节标题写作‘治疗期’不能单独证明该访视内每项操作均发生在首次给药后。若同一访视的来源顺序"
    "显示某项操作位于入排复核、随机或首次给药之前，或冻结目录提供了对应的给药前节点，应按给药前"
    "入排流程核对，不得处置为 post_treatment_execution。"
    "筛选、导入、基线、随机或首次给药前需要关注的操作要求，即使其偏离本身不直接触发入排失败，"
    "仍属于入排审核控制点；应保留为相应强度的候选并绑定真实审核节点，不得因它不是排除条件，或"
    "同一要求也适用于治疗期访视，就处置为 post_treatment_execution、non_enrollment_execution 或普通说明。"
    "若同一句要求同时覆盖某审核节点前和该节点后的持续期间，当前节点的候选命题和求值只包含截至该节点"
    "已经发生、能够从当前资料核实的部分；节点后的持续义务可在来源和后续说明中保留，但不得并入"
    "本节点的确定性命题、不得要求当前受试者证明未来没有发生变化。不得因此丢掉节点前已有的限制；"
    "后续持续义务本身不构成另一个当前入排节点的补充流程关系，也不得为它单设当前真假命题或最低证据；"
    "仅当原文另有在后续入排节点到期且可核的增量要求时，才单独建立后续节点候选和关系。"
    "若原文无法区分两个期间，保留未决边界，不把未来状态写成已满足。"
    "必须先区分义务对象是个例受试者，还是中心、研究者、申办方及研究组织。研究启动准备、人员方案培训、授权、"
    "文件归档、监查稽查或系统管理等组织层义务，若未明确约束某一受试者的资格判断、节点放行或个例证据，应按原文"
    "处置为 non_enrollment_execution 或 administrative_statistical_background，不得建立候选。‘研究启动前’或"
    "‘任何研究操作前’只说明组织义务的时序，不能单独把它变成受试者入排控制，也不得仅因时点或名称相似就关联"
    "required_procedure 或 workflow_stage。若同一 owned_unit 同时包含组织义务和明确的受试者层面控制，单元处置为"
    "other_control_candidate，但候选只能引用并表达受试者层面的真实增量，不能把组织义务带入候选。"
    "pre_enrollment_structure_unit_ids 是系统根据冻结访视顺序确认的给药前单元，严禁将其中任何单元"
    "处置为 post_treatment_execution；应与对应的给药前流程目标核对是否已覆盖。"
    "owned_visit_instance_by_structure_unit_id 是系统对已知流程必做事项冻结的实际执行访视，不是原文中"
    "‘自筛选/上次访视以来’这类回顾区间起点。映射中的单元必须处置为 required_procedure，不能降级成"
    "普通补充说明；且只能绑定该实际执行访视和原文明示的执行访视，既不能漏绑，也不能额外绑定同阶段的其他访视。"
    "访视表中只有项目名称、脚注号和 X 勾选的单元，X 只表示该项目在对应列安排，"
    "不能由 X 推出额外的持续期、阈值、前后时间窗或条件。先按单元格坐标核对列位，"
    "再核对该项目是否已由同来源的冻结流程目标覆盖；已覆盖且本格无增量要求时链接已有目标，"
    "未覆盖时说明其真实流程含义，不得凭项目名称补造控制。脚注或其他章节的独立规范内容"
    "须在各自来源单元保留，不能因为本格只有 X 就忽略它们。"
    "其他章节可以对官方入组/排除标准作补充、重复表述或进一步解释，也可以产生新的方案控制"
    "候选，但它们不会因此成为新的 IN/EX，绝不能新建、改号、合并或重命名官方 IN/EX，"
    "也不能把流程必做目录项伪装成 IN/EX。候选与正式发布控制分离；本次只返回候选语义。"
    "核对已知目标是否覆盖时只能依据其 source_excerpts 的实际规定；目录名称只证明有此事项，"
    "不自动覆盖原文另写的药物、剂量、用法、持续期、时间窗或复核条件。未覆盖的受试者层面细节须保留增量候选，"
    "不能仅因目录同名就全部降为 required_procedure；也不能将治疗持续期误写为通用访视安排。"
    "一个候选可覆盖多个 owned_units，也可在同一批次产生多个候选。适用人群、触发条件、"
    "义务和例外必须保持四个独立层次：每层 DNF 的一个 group 表示组内全部条件共同成立，"
    "多个 group 表示替代路径；不得把且改成或，不得把例外混入触发条件。义务可同时包含"
    "完成/核对、访视安排/核对、结果有效期核对、基线值选取、达到条件、禁止事件、"
    "禁止药物或治疗暴露、必须记录和必须专业评估。带 time_constraint 的新义务不得继续使用"
    "complete_or_verify：访视何时进行或能否合并使用 schedule_or_verify_visit；已有检查结果"
    "在某锚点前多久内有效使用 verify_result_validity；以哪一次结果作为基线值使用"
    "select_baseline_value。"
    "原文的义务语气必须保真：‘可进行/允许进行’表示可选操作，不得改写成无条件必做；次数上限仍须逐字保留。"
    "‘无需/不要求执行’表示免除该要求，不表示禁止执行；不得使用 prohibit_event 强化原文，"
    "应以完成/核对适用人群及豁免状态表达。若免予后果受结果有效期限制，"
    "必须在同一义务组中并列两个原子：用 verify_result_validity 表达有效期并仅由它"
    "携带 time_constraint；用不携带 time_constraint 的 complete_or_verify 表达免予状态。"
    "不得将结果有效期虚构成 trigger，不得把两个原子拆成替代义务组，最低证据只证明"
    "有效期条件成立，不要求证明被免予的操作未发生。免予原子不得抄入或重述"
    "无条件检查执行清单，以免把免予重新强化为必做操作。"
    "常规检查、操作或记录本身是义务，不能仅因需要执行就写成触发条件。"
    "若某项检查、操作或记录对全部适用人群无条件必做，trigger_expression 必须为 null，"
    "义务组的 applies_to_trigger_branch_indexes 必须为空；不得为了连接义务而虚构触发分支。"
    "原文只列出一组条件及其后续操作时，也必须把该条件放入触发层，并让义务显式绑定该分支。"
    "但条件若只是研究者应告知、说明、提醒或确认参与者知晓的指令内容，当前控制动作是完成该沟通，"
    "不是假定条件事件已经发生。此时用无条件 complete_or_verify 保留完整条件指令，不得把被告知的"
    "未来条件改成筛选或基线已经发生的 trigger；只有原文直接规定当前控制动作本身在条件成立后才执行时，"
    "才建立 trigger_expression 并绑定后果义务。must_record 只用于原文明示必须记录、记载或形成病历记录的动作，"
    "不得把告知、说明、提醒、联系或讨论仅因需要留痕就改写成 must_record。"
    "义务完成强度区分明确必做、建议与尽力遵循三档，项目无关。modality=mandatory 表示明确必做；"
    "同一句混有必做和建议动作时，分别建立原子并从直接来源中逐字截取各自支持片段；"
    "必做原子的 source_excerpts 不得连带包含建议措辞，建议原子保留建议片段。"
    "原文使用‘建议’或同义措辞时必须使用 modality=recommended；原文使用‘尽可能’、‘在可获得范围内’、"
    "‘尽量’、‘尽力’或同义措辞时必须使用 modality=best_effort。资料收集的 best_effort 只能搭配"
    "must_record，不得强化为必须获得完整资料；其他非禁止类义务的 recommended 与 best_effort 保持"
    "原强度，不得硬化为 mandatory，也不得因此丢弃控制点；禁止事件或禁止用药/治疗暴露不得使用"
    "recommended 或 best_effort。每个收集原子只允许一种 temporal_scope：明确的近N天/周/月/年回顾窗使用"
    "最低证据描述若涉及 recommended 或 best_effort 义务对应的动作，也必须明确写出‘建议项’、‘尽量’或"
    "同等强度说明；最低证据是核对所需资料，不得借‘应包含’、‘需证明’等措辞把非强制动作升级为必达条件。"
    "中文原文‘建议参与者完成某准备动作’中的‘建议’是完成强度，动作仍是参与者实际准备。"
    "审核指引和最低证据必须核对是否实际完成该准备动作；禁止写成‘是否建议参与者’、‘已建议参与者’或"
    "‘建议已告知’。建议项没有记录时不得单独生成证据不足，可写明仅在记录存在时核对，未记录不单独构成缺口。"
    "calendar_lookback 并同时填写命名锚点的 time_constraint；要求保留完整病程、诊断至今历程或尽可能完整"
    "专项治疗史时使用 full_history 且不得附加统一日历窗；要求按各项正式入排条款规定窗口审查时使用"
    "official_rule_defined，不得把某个通用固定时长复制到各条 IN/EX；要求问询自筛选、基线或上次访视以来"
    "新增情况时使用 since_previous_visit，不得虚构固定天数。一个原文段同时含上述多个范围时必须拆成"
    "多个 must_record 原子，并让每个原子只引用直接支持该范围的最小连续摘录。资料收集不完整、既往源文件"
    "不可得或描述不足属于证据缺口，不得在本控制中改写成官方排除标准已触发。"
    "原文列出多组不同"
    "条件及各自对应的后续操作时，必须分别建立触发分支和仅适用于该分支的义务组；不得把"
    "多个条件合成一个笼统触发后要求全部后续操作，也不得为修复输出形状而删除原条件。"
    "同一段落中多个条件共享一个后果（例如都适用同一结果有效窗）时，仍须保留多个触发分支；"
    "可以用一个义务组的 applies_to_trigger_branch_indexes 同时列出这些分支序位。每个触发原子"
    "只引用直接支撑该分支的最小连续原文，不得把跨分号或句号的多组条件整段塞进一个原子。"
    "applicability_expression 只表达适用人群，不得用检查安排、结果有效窗或审核节点充当人群。"
    "条件成立后改用较短时间窗或其他后果时，条件原子本身不得携带该后果的时间窗；必须把"
    "默认后果和替代后果写成两个义务组，并由例外条件组的"
    "activates_obligation_group_indexes 激活替代义务组。此时"
    "waives_trigger_branch_indexes 表示默认后果被替代的触发分支范围，不表示无条件取消整条"
    "控制；默认义务组、替代义务组的 applies_to_trigger_branch_indexes 与例外组的"
    "waives_trigger_branch_indexes 必须使用完全相同的分支序位。"
    "时间要求必须完整结构化：相对首次给药、随机、基线等锚点的起始窗口写入 time_constraint；"
    "同一禁止原文若同时覆盖当前入排节点以前和其后的治疗或研究期间，禁止把整个未来期间写入当前节点的求值命题。"
    "当前禁止原子只写截至绑定节点可核的事实，prospective_period=null；将后续禁止写入同原子的"
    "continuing_obligation，保留相同的直接来源定位和逐字摘录、原文支持的 prospective_period，"
    "status=not_due_at_review_node。后续记录没有当前节点的真假命题，不得据此判定已遵守或已违反。"
    "若无法从原文和冻结节点区分当前与后续，保持待核，不得改作研究者判断或治疗后事项来绕过。"
    "原文要求义务持续至试验结束、整个研究期间或治疗期间时，还必须分别写入"
    "prospective_period=study_period 或 treatment_period。起始窗口与持续期间可以同时存在，"
    "共同表示同一义务的完整覆盖范围，不得只把持续终点留在标题、说明或摘录中。"
    "原文为‘从签署知情同意起至末次给药后N天/周/月’的完整区间时，持续义务使用"
    "prospective_period=study_period，并把末次给药后的尾段写成 anchor_type=last_dose_date、"
    "direction=after、upper_bound=N；不得把N误写成相对 icf_date 的上限。若已知目标已经完整覆盖"
    "持续使用或达到条件本身，只保留该区间内真正新增的禁止、沟通或记录义务，不得重复目标义务。"
    "沟通、确认、告知、讨论或病历记录动作不得继承被沟通内容本身的持续期。若研究期间、治疗期间、"
    "持续至某时点或末次给药后若干时间出现在被告知、被确认知晓理解或被同意遵守的内容中，"
    "它只描述沟通对象应遵守的行为或状态，不得写入沟通、确认或记录原子的 prospective_period 或"
    "time_constraint，也不得为补期间把该措辞粘贴到无关原子的 source_excerpts。只有原文直接要求"
    "沟通、确认或记录动作本身在某期间反复执行或持续有效时，才为该动作结构化期间。"
    "原文明确写出N天、N周、N个月或N年时，必须把同一数值和单位写入 time_constraint 的"
    "lower_bound 或 upper_bound；不得只给锚点和方向而把数值留空。time_constraint 中的"
    "边界开闭必须逐字保留：‘超过/>N’使用 lower_bound=N 且 lower_bound_inclusive=false；"
    "‘至少/≥N’使用 lower_bound=N 且 lower_bound_inclusive=true；‘少于/<N’使用"
    "upper_bound=N 且 upper_bound_inclusive=false；‘不超过/≤N/N以内’使用 upper_bound=N"
    "且 upper_bound_inclusive=true。比较较早事件与较晚命名锚点时，应把较早事件写成相对"
    "较晚锚点的 before 时间约束，不得因两个日期同时出现而省略 time_constraint。"
    "同一来源先给出通用访视、时间窗或基线值规则，随后又为明确列出的项目规定更严格或更精确"
    "节点时，后者是前者的明确特例。不得把通用窗口传播到这些特例项目，也不得在最低证据或"
    "跨来源关系中声称特例项目可按较宽窗口完成。冻结流程目标若已在精确节点覆盖特例项目，"
    "新候选只保留尚未覆盖的通用规则，并通过 further_explanation 说明层级，不重复建立特例义务。"
    "schedule_or_verify_visit 的 cross_source_relations 必须关联本候选 review_node_bindings 中相同身份的"
    "workflow_stage；仅写审核节点而不建立关系不构成完整的访视安排。"
    "通用访视安排必须关联 known_workflow_stage_targets 中的 workflow_stage，不得把通用时间窗分别挂到"
    "各个 required_procedure。通用基线值选取原则关联 workflow_stage；只针对一个明确检查项的"
    "特例才关联该 required_procedure。一个候选不得同时混合通用原则和具体检查项特例。"
    "half_life_evidence只承载本原子正式方案原文明示的单一半衰期时长与适用对象，"
    "source_span_id/source_excerpt须属于本原子来源；duration_quote逐字保留数值单位，"
    "applies_to_quote逐字保留适用对象。不得凭记忆、药名、其他人群或范围端点补值；"
    "原文只规定倍数但未给时长时该字段为null，仍保留倍数要求。"
    "日历时长、半衰期倍数和 prospective_period 都必须在该原子自己的 source_excerpts 中"
    "逐字找到直接支持；需要同时引用时间单元和项目单元时，按一一对应规则同时列出。"
    "条件只缩短起始窗口、不改变持续终点时，替代义务仍必须保留原持续期间，"
    "并在该替代义务自己的 source_excerpts 中同时引用缩短后起始窗口和"
    "未改变的持续终点原文，不得只引用缩短条件却自行填入 prospective_period。"
    "同一表格中药物或治疗类别、时间窗、条件例外不同的独立行，默认分别建立候选；只有它们"
    "共享同一触发与后果结构时才可合并。activates_obligation_group_indexes 使用完整义务组数组的"
    "从0开始序位，必须指向替代义务组本身，不能误填默认义务组或触发分支序位。"
    "表格行的 excerpt 可能省略空格；须按 member_source_refs 中的 .r行.c列 坐标与同表表头列号对齐。"
    "未出现的列是空单元格，不得把后面非空格的值左移到较早访视；列位或合并单元格无法核实时保留待核，"
    "不得根据非空值个数猜测访视。"
    "每个原子必须直接给出数量"
    "完全相等、位置一一对应的"
    "source_span_ids 与 source_excerpts；同一来源定位需要提供多个摘录时，必须为每个摘录"
    "重复填写该 source_span_id。摘录必须是输入"
    "owned_units 原文 excerpt 中逐字连续存在的片段，不得拼写、改写、推断或引用 context。"
    "每个审核节点必须明确 workflow_stage_id、review_stage 与 role（提前关注、本节点判定或"
    "后续节点复核），且 workflow_stage_id 只能从输入的 known_workflow_stage_targets 冻结目录"
    "中选择；必须逐字回显所选目录项的 review_stage，不得发明、改写或新建节点身份。相同"
    "ReviewStage 下不同 visit_instance 仍是不同的冻结节点，不能合并。若本批没有冻结流程节点"
    "目录，则不得输出任何候选审核节点。相对首次给药、随机或基线等后续锚点的最终判定必须"
    "绑定对应的后续决定节点；若冻结目录同时存在普通基线和首次给药前复核，首次给药锚点必须绑定"
    "首次给药前复核，不得因二者同属 baseline 而退化为普通基线。较早筛选节点只能标记为提前关注，不能同时作最终判定。"
    "审核指引 guidance 只说明如何核对已经结构化的原始义务，不得把原文动作替换成另一动作。"
    "例如原文要求参与者实际静息时，应核对静息事实，不得改写成确认研究者已经告知参与者。"
    "评分量表、检查或测量的方法学段落，若补充了已知流程目标未包含的评估维度、"
    "计分或测量方法、量程及解释方向、操作规范或引用的评估手册，这些内容会影响入排结果"
    "的可重复核对，不是普通背景说明。必须只为已知目标未覆盖的方法学增量建立"
    "supplementary_requirement 候选并关联对应流程目标；不得重复造出‘必须完成该检查’，"
    "也不得把量表量程或理论取值范围改写为入排阈值。"
    "不同检查、量表或评分方法若关联不同流程目标，或适用的冻结访视集合不同，必须分成独立候选；"
    "不得因为它们同属一个专章或共享最终审核阶段，就合并后把某项方法扩展到其他项目的访视。"
    "方法或操作细节段落没有重复列出访视，不表示它只适用于最早访视。若只读上下文明确同一检查"
    "在多个入排阶段执行，且原文没有把该方法限定到单一访视，应为所有相关冻结节点保留核对；"
    "supplementary_requirement 的首次受影响节点不等于该方法的唯一适用节点。只读上下文只用于"
    "解释适用范围，不得成为候选的直接来源摘录。"
    "方案正文、方案附录、评分细则、操作规范、评估手册或SOP是控制规则的权威依据，不是某名受试者"
    "完成该控制所需补充的个例证据。minimum_evidence.required_source_types 只能列受试者层面的实际记录，"
    "例如已完成的评分表、检查报告、病历记录或研究者评估记录；不得把方案、附录、评分细则、操作规范、"
    "评估手册或SOP列为个例最低证据，也不得因此制造证据不足。可在义务、审核指引或关系说明中保留"
    "‘按附录/SOP执行’的规则要求。requires_professional_judgment 仅在该原子本身需要研究者、医生或其他"
    "专业人员作判断时设为 true；患者自填/自评问卷、机械计分、范围核对或资料是否存在的核对不得仅因"
    "需要审核就设为 true，也不得为纯患者自填/自评工具额外要求研究者评估记录。医生评分、研究者临床判断"
    "等原文明示或工具固有的专业评估保持 true。该布尔不表示需另写研究者声明；诊断或评分记录"
    "本身可承载专业评估。仅在方案要求研究者对特定对象作判断时，才为对应 minimum_evidence"
    "指定 investigator_assessment，并明确对象、节点及可接受记录；不得扩散到同组件内客观检查"
    "或一般病史的其他最低证据。义务陈述若保留‘见附录’、‘按SOP’、‘按手册’等权威引用，"
    "该义务自己的 source_excerpts 必须同时包含直接支持该引用的连续原文；不得只引用方法描述却在陈述中补写引用。"
    "原文要求在计划访视、各计划访视或计划的访视点执行告知、核对或记录时，候选义务和直接摘录必须"
    "保留该访视作用域；审核节点只能选择当前 known_workflow_stage_targets 中实际冻结的节点，"
    "并在其中所有具有 visit_instance 的冻结访视节点分别作本节点判定；每个决定节点均须有"
    "该阶段到期的最低证据。不得发明未冻结的治疗期访视，也不得为了避开节点不足而把计划访视改写成"
    "仅在单一访视执行或删除该控制。"
    "一个候选只表达一个最终决定阶段的完整控制语义。同一来源同时包含筛选期应完成的操作和"
    "基线/随机/首次给药前才可最终判断的有效窗时，必须按最终决定阶段拆成多个候选；不得用一个候选同时承载"
    "筛选完成与后续有效性判定。如果冻结官方规则或流程必做目标已完整覆盖检查或操作本身，新候选只保留未被覆盖的"
    "时间有效性、条件后果或其他增量要求，通过关系关联原目标，不得重复造一条‘必须检查’。每个本节点判定"
    "必须至少有一项 due_stage 与该 review_stage 一致的最低证据。最低证据必须"
    "说明 fact_type、description、due_stage 和 workflow_stage_ids。workflow_stage_ids须逐一选择本候选已绑定的"
    "冻结节点，期别与due_stage一致，表示在哪些具体访视核对此项证据，不能仅凭同属一个阶段概括所有访视。"
    "核对节点不等于资料生成日期：既往记录可以支持后续判断，病史回溯窗口不等于检查结果有效期。"
    "每项证据的source_policy分别说明是否要求同期客观原件、是否允许筛选病历转述；"
    "原文未能明确支持真或假时填null，不凭资料类型、疾病或常识补值。"
    "result_validity_status为specified时保留原文完整有效期约束；明确未另规定时为not_specified，"
    "尚无法确定时为unknown，两者的result_validity_constraint均为null，不把未规定说成无限有效。"
    "source_policy须携带与该证据要求有关且一一对应的source_span_ids和逐字source_excerpts；"
    "每项最低证据还须用atom_refs说明它用于核实哪个原子：layer从applicability、trigger、"
    "obligation、exception或repeat_trigger选择；repeat_trigger须同时提供condition_id，"
    "定位本候选旁置复查条件，其他层不得提供condition_id；group_index及atom_index均为相应表达式中的零基序位。"
    "一项资料可对应多个原子，但不能只因资料类型相同而关联。核实适用人群、触发和例外的"
    "资料也须明确关联，不能等到条件已成立才去收集用于确定条件的资料；此关联不表示条件成立。"
    "不得把病史事件回溯期、禁药洗脱期抄作报告有效期。跨来源关系只能"
    "从输入的 known_official_targets、known_procedure_targets 或 known_workflow_stage_targets 中选择目标，"
    "不得发明目标。"
    "补充流程必做目标时，affected_workflow_stage_id 表示本条增量首次构成可发布入排判定的冻结节点。"
    "同阶段补充必须选择被补充流程必做项执行访视对应的唯一冻结节点；若增量义务仅为后续锚点的"
    "结果有效窗或基线值选取等后续控制，且最终判定只能在更晚的基线/随机/首次给药前节点完成，"
    "则 affected_workflow_stage_id 必须选择该最终判定节点，而非流程必做执行访视；procedure 仍通过"
    "external_target_id 指向执行访视目标。候选必须在 affected 节点作本节点判定，最低证据也必须在"
    "该节点所属阶段到期；较早执行访视只能 early_attention，不能对后续锚点作 decide_at_node。"
    "同阶段普通补充不得用更晚访视目标承接较早筛选影响。"
    "官方规则关系及非补充流程关系的 affected_workflow_stage_id 必须为 null。"
    "资料收集原文同时指定筛选和基线时，筛选与基线冻结节点都必须分别使用 decide_at_node，并各有同阶段"
    "资料收集原文同时指定筛选和后续审核阶段时，筛选与后续审核阶段可合并只表示相同评估可不重复，不得删除后续节点的完成核对。后续节点只核对自上次"
    "访视以来的增量时，应另建 since_previous_visit 收集原子，不得在基线重新要求完整病史。"
    "owned 单元只有在其全部临床语义（包括条件、时间窗、阈值、次数、例外和后果）均被目标"
    "只读摘录完整覆盖时，才可直接处置为 official_eligibility 或 required_procedure。只要"
    "owned 单元增加、收紧或改变任一语义，就必须处置为 other_control_candidate，并通过"
    "cross_source_relations 关联原目标；不能用宽泛的‘属于同一流程’吞并新增控制要求。"
    "对检查项目、药物、治疗、病史、事件或其他枚举清单，必须将 owned 原文与已知目标摘录逐项比对；"
    "标题、类别或流程名称相同不代表清单完全相同。只要 owned 原文多出任何一项，就必须把未覆盖项保留在新候选义务中。"
    "对解释、告知、讨论、评估、确认、签署、记录、采集、检查等独立动作谓词，"
    "必须逐个与已知目标摘录比对；流程名称或最终完成状态相同，不代表其前置动作已被覆盖。"
    "只有目标摘录明确覆盖每个动作谓词，才能将整个单元直接处置到该目标；"
    "若仅部分覆盖，单元必须处置为 other_control_candidate，候选义务只保留未覆盖的动作，"
    "并以 supplementary_requirement 关系关联已知目标，不得重复已覆盖动作。"
    "原文明确要求解释、告知、评估、确认、签署、记录或采集等一般动作在某命名节点前完成时，"
    "使用 complete_before_anchor，time_constraint 必须保留该命名锚点且 direction=before；"
    "这不是访视安排，不得改写为 schedule_or_verify_visit。"
    "措辞、举例范围或表述粒度不同本身不构成控制增量；只有适用人群、条件、动作、时间窗、阈值、"
    "逻辑关系或例外范围发生实质变化时，才可建立 supplementary_requirement。"
    "已知官方或流程目标携带 source_excerpts 时，这些摘录仅是只读权威上下文；"
    "其中 null 表示对应来源只是表格根等纯结构定位，没有可逐字摘录文本，不得据此补写原文。"
    "不得将其当作新候选的直接来源。official_rule 关系的 external_target_id "
    "必须回显 official_code，不能回显 catalog_item_id；"
    "required_procedure 关系才回显对应 catalog_item_id。任一候选引用的每个"
    "source_structure_unit_id 都必须在 dispositions 中处置为 other_control_candidate；"
    "official_eligibility 或 required_procedure 单元不得同时作为候选来源。"
    "所有要求排序的 ID 列表必须按完整 ID 字典序排列且不得重复。"
    "provider 不得输出 batch_id、candidate/control/atom/evidence/relation/node 稳定 ID、"
    "候选位置索引或任何额外字段；系统会在水合时注入身份。仅evaluation.predicate内的predicate_id"
    "是比较规格必需的局部标识，可按Schema提供，不代表正式条款或事实身份。只输出完整 JSON，"
    "不得输出 Markdown、日志、说明或发布结论。"
    "一个 owned 单元的全部语义若由多个访视级流程目标共同覆盖，必须处置为 required_procedure，"
    "并在 linked_procedure_catalog_item_ids 中完整列出每个目标；不得只保留最早或最后一个访视。"
    "链接目标只覆盖其 visit_instance 指明的访视；即使多个目标携带相同的跨访视来源摘录，也不得据此"
    "把未列入链接目标的访视宣称为已覆盖。含未覆盖后续访视的混合单元不能"
    "处置为 required_procedure，应按其对入排审核的真实作用选择支持说明或增量候选。"
    "新输出始终令兼容字段 linked_procedure_catalog_item_id 为 null。"
    "输出前按以下顺序自检：1）other_control_candidate 的 linked_official_code 为 null，"
    "linked_procedure_catalog_item_id 为 null 且 linked_procedure_catalog_item_ids 为空，只在候选 cross_source_relations 中关联已知目标；"
    "2）同一 DNF 的合取组内不得出现重复原子，DNF 不得出现重复组，candidate_drafts 不得出现重复候选；"
    "3）凡含 first_dose_date、randomization_date 或 baseline_date 锚点，最终判定节点和最低证据"
    "due_stage 均必须是 baseline，screening 若保留只能是 early_attention；"
    "4）一个来源既有筛选期操作、又有首次给药/随机/基线有效性判定时，按最终决定阶段分成两个候选。"
    "5）枚举清单必须逐项比对已知目标，目标缺少的任何项必须留在增量候选中。"
    "清单增量必须写入 obligation_expression 的义务陈述；标题、说明、最低证据或审核指引提到清单，"
    "都不能代替正式义务保留这些项目。"
    "6）每个 supplementary_requirement 候选必须至少保留一个已知目标未覆盖的义务增量；"
    "若条件操作本身已被目标完整覆盖、只有时间有效性或其他共用后果是新增内容，删除重复操作候选，"
    "但在新增后果候选中保留各条件触发分支，并让共用增量义务显式绑定全部分支。"
    "7）若 owned 单元的全部语义已被某个已知官方规则或流程目标完整覆盖，必须直接处置到该目标；"
    "不得以‘维持完整控制链’、‘概括性重述’或‘进一步说明’为理由重复创建候选。"
    "8）‘不得随机/不得给药’描述锚点事件本身时使用 direction=on；只有原文明确描述事件前窗口时才使用 before。"
    "9）每条补充流程关系的 affected_workflow_stage_id 必须与候选本节点判定和最低证据到期阶段一致；"
    "同阶段补充时 affected 还必须与被补充流程必做访视一致；跨阶段后续控制补充时 affected 为最终判定节点，"
    "procedure 执行访视由 external_target_id 隐式确定。"
    "10）原文若要求在计划访视执行，所有具有 visit_instance 的冻结访视节点都必须分别作本节点判定，"
    "并具备该阶段到期的最低证据；不得只保留一个访视或发明目录外访视。"
    "11）每个资料收集原子逐项核对 modality 与 temporal_scope；日历回顾、完整历程、正式条款自有窗口、"
    "访视间增量不得合并到同一原子，也不得把资料缺口写成排除成立。"
    "12）逐个核对独立动作谓词；不得用签署、记录或检查的完成状态替代未被目标摘录明确覆盖的"
    "解释、告知、讨论、评估、确认或采集动作。"
)

_CONTROL_REPAIR_CONTRACT = (
    "这是同一会话内的定向修复。只修复下方列出的冻结批次、结构单元和候选范围；不要替换"
    "已经接受的批次，不要扩展到其他批次，不要删除未被指出且仍然有效的候选语义。"
    "provider 不得生成任何稳定 ID。"
    "修复时必须用修正后的项替换错误项，不得在原数组后追加修正版；返回前删除完全重复的 DNF 组和候选。"
)


def _repair_problem_guidance(problem: str) -> str:
    if "ENROLLMENT_PROHIBITION_UNCOVERED" in problem:
        return (
            "本轮重点：逐字核对所指来源片段中的阶段和禁止行为。若该要求在当前入排节点"
            "需要核实，补齐有来源的控制候选及对应单元链接；若确由已有官方条款或流程事项覆盖，"
            "仅按冻结目标的原文与来源作真实链接，不得凭标题相似、表格符号或疾病常识跳过。"
            "不要为了通过校验发明阈值、时窗或临床结论。"
        )
    if "WIRE_SCHEMA_INVALID" in problem or "CANDIDATE_REPAIR_INVALID" in problem:
        guidance: list[str] = []
        if "后续持续义务只适用于禁止类原子" in problem:
            guidance.append(
                "后续持续义务不能挂在完成、给药或记录原子上。逐项核对当前动作和未来限制的直接原文："
                "只有原文确有独立的后续禁止要求，才在有直接来源的禁止原子中表达；"
                "否则删除无据的后续禁止描述。不得借相邻句子补药量、日期或未来义务。"
            )
        if "确定性求值须声明计算方式" in problem:
            guidance.append(
                "逐个核对所报原子的原文含义：仅可按来源确定计算的原子用 deterministic 并填写相应 operation；"
                "语义核对或研究者书面判断的 operation 和 predicate 均为 null。不得为通过结构校验改变临床含义。"
            )
        if "数值谓词必须声明单位" in problem:
            guidance.append(
                "数值谓词的单位按直接原文填写；原文确为无量纲数值时显式写 unitless，不能凭项目或疾病猜单位。"
            )
        if "求值规格须说明观察选择规则" in problem:
            guidance.append(
                "观察选择只依据方案原文；明示一次/任一/全部才写对应模式，原文不足则显式标未核实，"
                "不得按已上传病例记录数推断。"
            )
        if "已有时间约束不能在求值规格中忽略" in problem:
            guidance.append(
                "若该原子确有逐字支持的时间约束，求值规格须说明该时间条件的用途和对应日期属性；"
                "若时间词属于另一动作，应收窄本原子的摘录并删除无据时间约束，不能仅改标记绕过校验。"
            )
        if guidance:
            return "本轮仅修复校验所指原子：" + "".join(guidance)
    """Add only the structural guidance needed for the reported gate failure."""

    value_operand_error = "普通值比较不能冒充日期间隔或书面判断计算" in problem
    missing_time_error = "未给出时间约束，不能声明已确定其计算用途" in problem
    if value_operand_error or missing_time_error:
        guidance = []
        if value_operand_error:
            guidance.append(
                "本轮重点：仅对原文确有明确数值、单位和比较方向的原子使用 "
                "evaluation.operation=value_comparison；其 evaluation.operand_attribute 必须为 value，"
                "predicate 须保留原文比较条件。日期间隔和研究者书面判断不得为通过格式校验伪装成数值比较。"
            )
        if missing_time_error:
            guidance.append(
                "本轮重点：原子没有 time_constraint 时，evaluation.time_purpose 只能是 "
                "not_applicable 或 unresolved，不得凭访视背景推造日期计算。"
                "若原文确有明确时间限制，先在同一原子中逐字保留并结构化 time_constraint，"
                "再说明计算用途；不得为了让规格通过而补造原文没有的时限。"
            )
        return "".join(guidance)
    if "比较条件必须保留求值规格内的逐字原文" in problem:
        return (
            "本轮重点：值比较须在 evaluation.predicate.source_clause 或 source_clauses 中"
            "填写实际比较依据的逐字连续片段，并确保每片段包含在同一 evaluation.source_excerpts 中。"
            "source_term 不能代替 predicate 的逐字来源；不得为凑校验改写原文或虚构比较条件。"
        )
    if "未来计划窗只允许研究药物给药日、末次给药日或研究完成日" in problem:
        return (
            "本轮重点：prospective_window 只适用于原文明确以研究药物给药日、"
            "末次给药日或研究完成日为锚点的未来期限。筛选、基线和随机日期不能放入"
            "prospective_window；应按原文使用相应的命名时间约束或期间，"
            "无法确定时保留未核实，不得替换锚点。"
        )
    if "FABRICATED_EXCERPT" in problem:
        return (
            "本轮重点：原子摘录（source_excerpts）必须从授权结构单元的冻结原文（excerpt）中逐字复制连续文本片段，"
            "标点、引号和空格均保持原样；不得改写、摘要、同义替换、跨单元拼接或擅自补全；"
            "source_span_ids 与 source_excerpts 必须按位置一一对应且属于对应结构单元；"
            "无法逐字核验的摘录不得输出。"
        )
    if "SOURCE_SCOPE_ESCAPE" in problem:
        return (
            "本轮重点：所有原子引用的来源定位（source_span_ids）必须属于本批授权结构单元的来源闭包，"
            "不得引用 owned 之外或当前候选未声明的来源片段。"
        )
    if "MIXED_OBLIGATION_KIND_SCOPE" in problem:
        return (
            "本轮重点：将访视安排与结果有效期分别建候选；两项义务各自保留原文定位。"
            "访视安排关联冻结流程节点，结果有效期只关联受影响的具体检查项；"
            "拆分不得删除原有义务或扩大来源范围。"
        )
    if "PROSPECTIVE_PERIOD_HOLDER_INVALID" in problem:
        return (
            "本轮重点：当前节点的确定性核对原子不得自行携带 prospective_period。"
            "若同一禁止原文还有未来持续要求，应把当前可核命题与同源 continuing_obligation 分开保存；"
            "不能辨清时保留需要核对，不得删除当前义务或提前证明未来遵守。"
        )
    if "VISIT_SCHEDULE_" in problem:
        return (
            "本轮重点：访视合并、访视间隔或访视时间窗使用 schedule_or_verify_visit，"
            "cross_source_relations 必须包含 external_target_kind=workflow_stage，"
            "external_target_id 必须等于本候选 review_node_bindings 中对应节点的 workflow_stage_id；"
            "仅绑定审核节点而把 cross_source_relations 留空仍不合格。"
            "删除把同一通用时间窗分别挂到各检查项的关系；不得为凑关系发明节点。"
        )
    if "确定性求值须声明计算方式，其他模式不得夹带计算方式" in problem:
        return (
            "本轮重点：只有能由明确操作数、比较方式及来源计算的原子才使用 deterministic，"
            "并填写相应 computation；需要结合记录语义核实动作是否完成时使用 semantic，"
            "且 computation、operation、predicate 均为 null。不得为通过格式校验虚构计算方式。"
        )
    if "RESULT_VALIDITY_" in problem:
        return (
            "本轮重点：已有检查结果在命名锚点前的有效窗使用 verify_result_validity，"
            "并以 supplementary_requirement 精确关联受影响的 required_procedure。"
            "若有效窗相对首次给药/随机/基线锚点且流程必做在较早访视执行，affected_workflow_stage_id"
            "必须选择最终判定节点，screening 仅 early_attention。"
        )
    if "BASELINE_VALUE_SCOPE_" in problem:
        return (
            "本轮重点：基线值选取使用 select_baseline_value。通用原则关联 workflow_stage；"
            "具体检查项特例单独建候选并关联对应 required_procedure，不得在同一候选中混合两种范围。"
            "须从首次请求的冻结目标原文核对项目与访视，在 cross_source_relations 中保存精确目标，"
            "不能只在标题提及，也不能关联不受此原则影响的检查。"
        )
    if "ACTION_TARGET_SCOPE_MISMATCH" in problem:
        return (
            "本轮重点：按每项动作实际适用的冻结流程目标拆分候选。一个候选中的全部来源动作必须"
            "具有相同的目标集合；只适用于较早节点的动作不得与跨节点动作合并，也不得绑定到更晚节点。"
        )
    if "CANDIDATE_OBLIGATION_ACTION_UNCOVERED" in problem:
        return (
            "本轮重点：把校验指出的未覆盖独立动作写回 obligation_expression，"
            "并保留原文的完成强度和最小连续摘录。标题、处置说明、最低证据和审核指引"
            "不能代替正式义务；不要删除候选内其他仍有效的义务。"
        )
    if "ACTION_INCREMENT_RELATION_UNDERSTATED" in problem:
        return (
            "本轮重点：候选包含已知流程必做项未覆盖的独立动作时，关系类型必须使用"
            "supplementary_requirement，并填写该增量首次影响的冻结审核节点；"
            "不得仅标记为 further_explanation。"
        )
    if "USER_FACING_ITEM_COUNT_MISMATCH" in problem:
        return (
            "本轮重点：审核指引和最低证据中出现的‘N项’必须与正式义务的项目计数一致。"
            "不要因一个项目包含多个子测量值，就在用户可见文字中改变项目总数。"
        )
    if "REVIEW_GUIDANCE_ACTION_INVENTED" in problem:
        return (
            "本轮重点：审核指引只能说明如何核对原义务，不得新增或替换动作。"
            "原文要求实际完成、达到或保持某状态时，直接核对该事实；"
            "不得改写为告知、说明、提醒或其他原文没有要求的沟通动作。"
        )
    if "MINIMUM_EVIDENCE_MODALITY_DROPPED" in problem:
        return (
            "本轮重点：最低证据若描述建议或尽力完成义务对应的动作，必须显式保留原强度。"
            "可要求核对记录，但不得把建议项或尽力项写成必须达到、必须证明的条件。"
        )
    if "MINIMUM_EVIDENCE_AUTHORITY_SOURCE_CONFLATED" in problem:
        return (
            "本轮重点：方案、附录、评分细则、操作规范、评估手册和SOP属于规则依据，不是受试者个例证据。"
            "从 minimum_evidence.required_source_types 删除这些权威依据，只保留实际评分表、检查报告、病历记录、"
            "研究者评估记录等受试者层面资料；规则引用仍保留在义务、审核指引或关系说明中。"
        )
    if "SELF_REPORTED_TOOL_MARKED_PROFESSIONAL" in problem:
        return (
            "本轮重点：患者自填或自评问卷不属于研究者专业判断。将相应原子的 requires_professional_judgment"
            "设为 false；只有医生评分、研究者临床判断或其他确需专业人员判断的原子才设为 true。"
        )
    if "SELF_REPORTED_TOOL_RESEARCHER_EVIDENCE" in problem:
        return (
            "本轮重点：纯患者自填或自评问卷的个例证据是已完成问卷及其可核对记录，不得额外要求研究者评估记录。"
            "只有存在独立研究者判断义务时，才把研究者评估记录列为最低证据。"
        )
    if "AUTHORITY_REFERENCE_SOURCE_DROPPED" in problem:
        return (
            "本轮重点：义务陈述保留附录、SOP、手册或评分细则引用时，该义务自己的 source_excerpts 必须"
            "包含直接支持该引用的连续原文；如拆分原子，应把引用句作为同一原子的另一条摘录并重复来源定位。"
        )
    if "PARTICIPANT_PREPARATION_RECAST_AS_ADVICE" in problem:
        return (
            "本轮重点：建议强度修饰参与者实际完成的准备动作。审核指引和最低证据应写成"
            "‘如有记录，核对参与者是否实际静息、休息或完成相应准备（建议项；未记录不单独构成缺口）’；"
            "禁止使用‘是否建议参与者’、‘已建议参与者’或‘建议已告知’。"
        )
    if "RECORD_PRECISION_COMPRESSED" in problem:
        return (
            "本轮重点：原文明示记录单位、整数或小数位数时，必须使用独立 must_record 原子，"
            "逐字保留单位和精度；不得用 complete_or_verify 或完成测量概括记录要求。"
        )
    if "具体操作持续期只能按带命名锚点的语义核对保存" in problem:
        return (
            "本轮重点：具体治疗或操作的持续期可用 complete_or_verify，"
            "但 evaluation 必须是 semantic、time_purpose=interval_condition，"
            "同时保存原文命名的 time_constraint 和完整持续要求。"
            "不能用一次药名值比较证明疗程完成；访视安排和结果有效期仍分别使用其专门类型。"
        )
    if "CONDITIONAL_BRANCH_MAPPING_INVALID" in problem:
        return (
            "本轮重点：先区分当前动作本身受条件触发，还是当前动作仅为告知、说明或记录一项条件指令。"
            "前者必须把每组条件各自保留为触发分支；多个真实条件共享同一后果时，用一个义务组绑定全部触发分支；"
            "后者用无条件 complete_or_verify"
            "保留完整指令，不得假定被告知的未来条件已在当前节点发生。must_record 仅保留原文明示的记录动作。"
        )
    if "PLANNED_VISIT_SCOPE_DROPPED" in problem:
        return (
            "本轮重点：原文要求在计划访视执行时，逐一绑定 known_workflow_stage_targets 中所有具有"
            " visit_instance 的冻结访视节点并分别作本节点判定，为每个决定节点补齐对应阶段的最低证据。不得只保留"
            "单一访视，也不得发明目录外节点。"
        )
    if "DECISION_STAGE_EVIDENCE_MISSING" in problem:
        return (
            "本轮重点：每个本节点判定所对应的 review_stage 都必须至少有一项同阶段到期的最低证据；"
            "补充事实类型、可接受证据说明和 due_stage，不得删除决定节点来绕过证据要求。"
        )
    if "ROUTINE_OBLIGATION_MISLABELED_AS_TRIGGER" in problem:
        return (
            "本轮重点：期间、时点或常规检查安排不是触发条件。无条件操作应将 trigger_expression 设为 null；"
            "若该操作仅在首次给药后或研究期间执行且不影响入排，应删除候选并将单元处置为"
            " post_treatment_execution。"
        )
    if "MIXED_DECISION_STAGE_CONTROL" in problem:
        return (
            "本轮重点：按最终决定阶段拆成两个独立候选；当前节点完成的检查/操作与后续节点核对的"
            "结果有效期不得留在同一候选中。不得因此重复建立已由已知目标覆盖的操作候选。"
            "后续阶段的新增有效性或其他后果若只适用于原条件成立者，仍须保留原条件分支并绑定新增后果。"
        )
    if "MIXED_TRIGGER_DECISION_STAGES" in problem:
        return (
            "本轮重点：把筛选时触发与基线/随机/首次给药前触发拆成不同候选。"
            "筛选候选在 screening 本节点判定，后续候选在对应 baseline 节点判定；不得把筛选失败降为提前关注。"
        )
    if "ANCHOR_WORKFLOW_STAGE_MISMATCH" in problem:
        return (
            "本轮重点：按冻结访视身份选择最终判定节点。若已有首次给药前复核或随机访视专门节点，"
            "不得仅因 review_stage 相同而改绑普通基线节点。"
        )
    if "PROCEDURE_AFFECTED_STAGE_MISMATCH" in problem:
        if "跨阶段" in problem:
            return (
                "本轮重点：先核对来源是否确有后续入排节点需要核实的增量。若有，"
                "affected_workflow_stage_id 指向该后续最终判定节点，"
                "external_target_id 保持原流程执行访视；当前节点只作提前关注。"
                "若原文只要求当前行为持续到治疗期，不要另建未来当前真假命题。"
            )
        return (
            "本轮重点：这是同阶段流程补充，affected_workflow_stage_id 应与"
            "external_target_id 对应流程必做项的实际执行访视一致；"
            "同时核对本节点判定与最低证据的到期节点。不得为了凑关系改写原文时点。"
        )
    if (
        "EARLY_DECISION_FOR_FUTURE_ANCHOR" in problem
        or "AFFECTED_STAGE_DECISION_MISSING" in problem
    ):
        return (
            "本轮重点：跨阶段有效窗或后续锚点控制补充时，affected_workflow_stage_id 必须选择"
            "与后续锚点一致的最终判定节点（如基线/首次给药前复核），external_target_id 仍指向"
            "流程必做执行访视；screening 只能 early_attention，decide_at_node 和最低证据必须在"
            "affected 决定节点。同阶段普通补充不得借用此路径。若原文只是当前要求在治疗期继续维持，"
            "未来部分只保留为同一当前禁止原子的未到期持续义务，不要为未来期间另建补充关系、"
            "当前真假命题或最低证据；仅原文另有后续入排节点可核增量时才建立独立候选。"
        )
    if "PROCEDURE_VISIT_SCOPE_UNCOVERED" in problem:
        return (
            "本轮重点：required_procedure 只能覆盖链接目录项 visit_instance 明确列出的访视。"
            "同一来源摘录还包含未链接的后续访视时，不得声称整个单元已被流程目标完整覆盖。"
        )
    if "DNF_DUPLICATE_ATOM" in problem:
        return "本轮重点：删除同一合取组内语义和来源完全相同的重复原子，只保留一项。"
    if "EXCEPTION_LAYER_MISSING" in problem:
        return (
            "本轮重点：把除非、除外或例外条件移入 exception_expression；"
            "义务只保留默认后果，并用例外作用域精确指向被豁免的触发分支。"
        )
    if "OPTIONAL_ACTION_MODALITY_DROPPED" in problem:
        return (
            "本轮重点：原文仅允许或可执行的操作必须在义务陈述中保留可选语气，"
            "不得把可选操作改写成必做操作；次数上限和适用条件也必须逐字保留。"
        )
    if "RECOMMENDED_MODALITY_DROPPED" in problem:
        return (
            "本轮重点：同一来源句若同时含明确必做和建议动作，应拆为不同义务原子。"
            "每个原子的 source_excerpts 只逐字摘录支持该原子强度的连续片段；"
            "必做原子不能连带引用后续的建议措辞，建议原子须保留建议原文并使用 recommended。"
            "不得把明确剂量、频次等必做要求降为建议，也不得把建议动作写成必须完成。"
        )
    if "RECOMMENDED_MODALITY_" in problem:
        return (
            "本轮重点：原文含‘建议’或同义措辞的原子必须使用 modality=recommended，"
            "且只引用直接支持建议强度的最小连续摘录；没有该措辞的原子不得自行升格为建议完成。"
        )
    if "BEST_EFFORT_MODALITY_" in problem:
        return (
            "本轮重点：原文含‘尽可能’、‘尽量’或同义措辞的原子必须使用 modality=best_effort，"
            "且只引用直接支持尽力强度的最小连续摘录；没有该措辞的原子不得自行降级为尽力完成；"
            "资料收集的 best_effort 只能搭配 must_record。"
        )
    if "COLLECTION_TEMPORAL_SCOPE" in problem:
        return (
            "本轮重点：把资料收集中的日历回顾窗、完整病程/完整专项治疗史、按正式入排条款自有窗口、"
            "自上次访视以来增量更新拆成独立 must_record 原子。分别使用 calendar_lookback、full_history、"
            "official_rule_defined、since_previous_visit；只有 calendar_lookback 携带 time_constraint。"
        )
    if "COLLECTION_VISIT_CLOSURE_MISSING" in problem:
        return (
            "本轮重点：原文明示筛选和/或基线收集时，保留筛选与基线两个冻结节点的 decide_at_node，"
            "并为两个阶段各提供最低证据。访视可合并只影响是否重复执行，不删除节点完成核对。"
        )
    if "COLLECTION_INTERVAL_REVIEW_NODE_MISSING" in problem:
        return (
            "本轮重点：自筛选、基线或上次访视以来的增量问询使用 since_previous_visit，"
            "并绑定相应后续冻结节点作本节点判定，不得只保留筛选节点。"
        )
    if "EXEMPTION_MODALITY_OVERSTATED" in problem:
        return (
            "本轮重点：‘无需/不要求’是豁免，不是禁止事件。不得使用 prohibit_event；"
            "用 complete_or_verify 核对适用人群及其无需执行该操作的状态，并只保留目标未覆盖的增量分支。"
        )
    if "CONDITIONAL_EXEMPTION_BINDING_MISSING" in problem:
        return (
            "本轮重点：原文的‘无需/不要求/可免除’若受同句条件或时间窗限制，"
            "必须在同一候选的同一义务组中并列 verify_result_validity 和 complete_or_verify："
            "前者携带有效期 time_constraint，后者只表达免予状态且 time_constraint=null。"
            "不得把有效期改成 trigger，不得把两者拆成替代义务组，也不得删除免予后果。"
            "免予原子不得抄入无条件检查执行清单。最低证据只保留结果日期与命名锚点，"
            "删除‘确认未重复/未再次执行’证据。"
        )
    if "CONDITIONAL_EXEMPTION_SCOPE_SPLIT" in problem:
        return (
            "本轮重点：同一来源中的检查要求、结果有效期和条件性无需再次检查属于一个语义范围。"
            "不得把检查项目拆成兄弟候选中的无条件筛选执行义务；应核对符合有效期的既有结果，"
            "并在同一候选中保留有效期条件与无需再次检查后果。若来源确含互不相关动作，先保持来源局部性，"
            "不得借拆分削弱原文条件。"
        )
    if "EXEMPTION_EVIDENCE_OVERSTATED" in problem:
        return (
            "本轮重点：豁免表示该操作在条件成立时不是必须，不表示操作禁止发生。"
            "最低证据只保留用于证明豁免条件成立的资料，删除‘确认未重复/未再次执行’"
            "之类把豁免强化为禁止的证据要求。"
        )
    if "PROHIBITED_EVENT_ANCHOR_MISMATCH" in problem:
        return (
            "本轮重点：不得随机或不得给药的禁止事件使用对应锚点的 direction=on；"
            "前置窗口只写在另有直接原文支持的条件或例外中。"
        )
    if "POST_ENROLLMENT_PROCEDURE_MISCLASSIFIED" in problem:
        return (
            "本轮重点：治疗期或明确在首次给药后才执行的检查不是筛选/基线入排候选；"
            "从签署知情同意开始并贯穿研究期的义务不能仅因 prospective_period=study_period 被删除。"
            "逐个核对授权原文单元：只有完全属于给药后执行的单元才可从候选移出，"
            "并明确处置为 post_treatment_execution、说明原文依据；"
            "同段或其他单元中真实的入排增量必须保留在候选，不能整段删除。"
        )
    if "FUTURE_PROHIBITION_DECIDED_EARLY" in problem:
        return (
            "本轮重点：当前禁止原子的 statement 和 evaluation.proposition 均只陈述截至决定节点可核的行为，"
            "不得在这两个当前节点字段中夹带后续期间名称或后续遵守要求；"
            "prospective_period=null；把原文支持的后续禁止另存同原子的 continuing_obligation，"
            "保留同一直接来源、期间及未到期状态，不为后续义务填写当前节点真假命题。"
            "不得删除节点前已有的禁止要求、改成研究者判断或凭空补一份未来承诺。"
            "若当前时点与后续时段不能从原文和冻结访视区分，保留未核边界，不生成当前已满足的候选。"
        )
    if "PRE_ENROLLMENT_PROCEDURE_MISCLASSIFIED" in problem:
        return (
            "本轮重点：该结构单元已由冻结访视顺序确认发生在入排复核、随机或首次给药边界之前，"
            "不得仅凭章节标题处置为治疗后事项。请与同访视的给药前流程目标核对并返回真实处置。"
        )
    if "PROCEDURE_VISIT_SCOPE_OVERBOUND" in problem:
        return (
            "本轮重点：流程目标必须匹配该原文单元的实际执行访视。‘自筛选/上次访视以来’只表示回顾区间起点，"
            "不表示在该起点访视执行；不得因访视可合并、review_stage 相同或摘录覆盖多个访视而额外绑定其他节点。"
        )
    if "KNOWN_PROCEDURE_DISPOSITION_MISMATCH" in problem:
        return (
            "本轮重点：该单元已由冻结流程识别为本节点必做事项，必须处置为 required_procedure 并绑定精确访视目标；"
            "不得为了绕开访视闭包检查而改为 supporting_or_supplement、非控制或治疗后事项。"
        )
    if "PROCEDURE_SEMANTIC_FAMILY_UNCOVERED" in problem:
        return (
            "本轮重点：同一原文并列出现多个资料家族时，逐个核对该精确访视下的冻结流程目标。"
            "例如病史与诊治/治疗史不能相互替代；只链接原文明示且目录中实际存在的家族，不新增目录目标。"
        )
    if "TIME_ANCHOR_GUESSED_FROM_SCREENING" in problem:
        return (
            "本轮重点：同一句含筛选和首次给药/随机两个时点时，拆成独立时间分支。"
            "筛选分支只引用直接包含筛选时点的最小连续摘录并使用 screening_date；"
            "后续分支只引用直接包含首次给药/随机时点的最小连续摘录并使用对应锚点，不能让一个分支摘录夹带另一个时点。"
        )
    if "TIME_ANCHOR_MISSING" in problem:
        return (
            "先核对报错原子的最小逐字摘录：如果时间词只属于同一结构单元的另一动作，"
            "应收窄该原子的摘录并保留另一动作的独立候选，不能替无时限的计算或记录动作补造锚点。"
            "本轮重点：每个时间性原子必须使用原文直接命名的锚点。混合多个时点时拆成独立分支并分别引用最小连续摘录；"
            "一般动作明确在命名节点前完成时使用 complete_before_anchor，保留该锚点且 direction=before；"
            "具体治疗或操作须持续一段期间时使用 complete_or_verify + semantic + interval_condition，"
            "保留命名锚点和完整持续要求；单次记录不能证明疗程完成。"
            "‘从签署知情同意起至末次给药后N天/周/月’使用 study_period，并把尾段结构化为"
            "last_dose_date、after、upper_bound=N，不得改用 icf_date 加N。"
            "比较较早事件与较晚命名锚点时，把较早事件写成相对较晚锚点的 before 时间约束；"
            "错误信息已给出具体原子编号和原句，须逐条补齐而不是只修第一个时间分支。"
            "同时逐字保存大于/小于及边界是否包含。首次给药后的研究执行事项不得为了补锚点而保留为入排候选。"
        )
    if "VISIT_SCHEDULE_TARGET_TOO_NARROW" in problem:
        return (
            "本轮重点：先核对原文的时间限制究竟约束访视安排、结果有效期，还是治疗/用药持续期。"
            "只有通用访视时间窗才使用 schedule_or_verify_visit 并关联冻结 workflow_stage；"
            "针对具体治疗或操作的持续期用 complete_or_verify + semantic + interval_condition，"
            "保留命名锚点、完整期间和逐字来源；不得为凑节点改写为访视安排，"
            "也不能因同名目录项而丢弃增量要求。"
        )
    if "附时间条件的核对须单独声明日期属性" in problem:
        return (
            "本轮重点：若值比较、语义核对或研究者判断原子确有 time_constraint，"
            "evaluation.time_operand_attribute 必须声明该时间条件核对的日期属性；"
            "原文不能确定日期属性时保留未解决，不得凭空指定事件日期或记录日期。"
        )
    if (
        "TIME_CALENDAR_BOUND_UNSUPPORTED" in problem
        or "TIME_CALENDAR_BOUND_MISSING" in problem
    ):
        return (
            "本轮重点：逐个核对报错义务原子的直接摘录。摘录含明确日历时长时，"
            "在该原子 time_constraint 保存原文支持的数值、单位、比较方向和实际修饰的锚点；"
            "摘录不含该时长时，删除无依据的结构化数值，不得借用同单元其他动作或其他原子的时长。"
            "同一义务含起点与终点时分别核对，不凭空补零天边界。"
        )
    if "TIME_BOUND_COMPARATOR_MISMATCH" in problem:
        return (
            "本轮重点：逐字保留时间边界。超过/>N 使用下界N且不含N；至少/≥N使用下界N且包含N；"
            "少于/<N使用上界N且不含N；不超过/≤N/N以内使用上界N且包含N。不得把开区间改成闭区间。"
        )
    if "PROSPECTIVE_PERIOD_MISSING" in problem:
        return (
            "本轮重点：先判断持续期约束的是当前动作，还是当前动作所告知、确认或记录的内容。"
            "沟通、确认或记录原子不得因‘告知研究期间需持续’而补 prospective_period，也不得粘贴"
            "被沟通的期间摘录来支持无关原子。若义务自身确为入排控制且原文要求贯穿研究或治疗期，"
            "结构化保存对应 prospective_period；"
            "若只是首次给药后的检查或随访，则删除候选并使用 post_treatment_execution。"
        )
    if "PROSPECTIVE_PERIOD_UNSUPPORTED" in problem:
        return (
            "本轮重点：删除没有由该动作直接来源支持的 prospective_period。告知、确认、讨论或记录"
            "‘研究期间需持续’只说明被沟通内容的期间，不说明沟通或记录动作持续；不得把该内容摘录"
            "粘贴到其他义务原子。只有动作自身明确贯穿研究或治疗期时才保留期间。"
        )
    if "CONTROL_DELTA_DROPPED" in problem:
        return (
            "本轮重点：逐项比较该 owned 单元与已知目标摘录，只为目标确实未覆盖的人群、条件、动作、时间、阈值或例外建立增量候选；"
            "若 owned 单元是评分、检查或测量方法，还必须比较评估维度、计分方法、量程与解释方向、操作规范及评估手册；"
            "已覆盖部分通过关系关联，不得重复，纯措辞或举例粒度差异也不得当作增量。"
        )
    if "CONTROL_DELTA_COMPONENT_DROPPED" in problem:
        return (
            "本轮重点：保留原文直接规定的全部记录或执行要素。逐项补回错误信息中列出的缺失要素，"
            "但不得改变该单元的处置类型、适用阶段、必做或可选语气，也不得把资料记录义务升格为入排不通过条件。"
        )
    if "CONTROL_DUPLICATE_RETAINED" in problem:
        return (
            "本轮重点：该单元的入排相关内容已被已知目标完整覆盖。删除其候选，"
            "按实际剩余内容处置为 required_procedure、post_treatment_execution 或其他非候选类型。"
        )
    if "COVERED_BRANCH_DUPLICATED" in problem:
        return (
            "本轮重点：删除已知目标已经覆盖的人群分支，只在增量候选中保留目标未覆盖的分支及其直接后果。"
        )
    if "CANDIDATE_MISSING" in problem:
        return (
            "本轮重点：处置为 other_control_candidate 的每个结构单元都必须至少由一个候选草稿引用。"
            "若该单元仍有真实入排增量，补充只包含未覆盖人群、条件、动作、时点或例外的候选；"
            "若没有真实增量，则删除候选处置，按原文改为 required_procedure、supporting_or_supplement、"
            "post_treatment_execution 或其他真实非候选处置。不得只在 notes 中描述候选。"
        )
    return ""


def _prompt_wire_schema() -> dict[str, Any]:
    """Omit generated display titles, retaining every validation and clinical description."""

    def without_titles(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: without_titles(item) for key, item in value.items() if key != "title"}
        if isinstance(value, list):
            return [without_titles(item) for item in value]
        return value

    return without_titles(protocol_control_agent_json_schema())


def protocol_control_agent_prompt_template_sha256(prompt_template: str) -> str:
    payload = "\n\n".join(
        (
            CONTROL_AGENT_PROMPT_VERSION,
            SOURCE_INTERPRETATION_PROMPT_VERSION,
            SOURCE_TARGET_REVIEW_VERSION,
            prompt_template.strip(),
            _CONTROL_AGENT_SYSTEM_CONTRACT,
            _CONTROL_REPAIR_CONTRACT,
            _stable_json(_prompt_wire_schema()),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_protocol_control_agent_prompt(
    batch: ProtocolControlDispositionBatch | ProtocolControlAgentInput,
    *,
    prompt_template: str = DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE,
    include_schema: bool = True,
    source_interpretation: SourceInterpretation | None = None,
) -> str:
    """Build a deterministic prompt from one planner batch or frozen input."""

    frozen_input = (
        batch
        if isinstance(batch, ProtocolControlAgentInput)
        else ProtocolControlAgentInput.from_batch(batch)
    )
    schema_block = (
        f"输出结构：{_stable_json(_prompt_wire_schema())}\n\n"
        if include_schema
        else "输出严格遵循本次请求随附的 JSON Schema；不得新增字段。\n\n"
    )
    return (
        f"{prompt_template.strip()}\n\n"
        f"{_CONTROL_AGENT_SYSTEM_CONTRACT}\n\n"
        f"{schema_block}"
        f"本次冻结输入：{_stable_json(frozen_input.model_dump(mode='json'))}\n\n"
        + (
            "已逐字定位的来源陈述（仅供核对，不替代原文或结构门禁）："
            f"{_stable_json(source_interpretation.model_dump(mode='json'))}\n\n"
            if source_interpretation is not None else ""
        )
        +
        "来源清单中的 time_words 仅是逐段原文，不是审核结论。"
        "同句涉及本节点及后续期间时，结合冻结审核节点分别表达可核事实与未到期持续义务；"
        "当前义务不得借用其他句子的数值时长，不能把后续禁令提前判为已遵守。"
        "原文或节点关系不能确定时保留未核实，不按当前或将来猜定。\n\n"
        "表格中的 X 标记须按 member_cell_paths 列位置与同表前置阶段、访视和时间行逐列核对；"
        "不能按压缩文本中 X 的顺序推断节点。无法对应时保留未核实，不得造访视或时间窗。\n\n"
        "按 owned_units 原文顺序逐项处理；每个 owned_unit 必须返回一条 disposition，"
        "候选可为 0 到 N。若候选不存在，必须逐单元写出非控制 disposition 和理由。只返回一个完整 JSON 对象。"
    )

def build_protocol_control_discovery_prompt(
    batch: ProtocolControlDiscoveryBatch | ProtocolControlDiscoveryAgentInput,
    *,
    prompt_template: str = DEFAULT_PROTOCOL_CONTROL_DISCOVERY_PROMPT_TEMPLATE,
) -> str:
    """Build a bounded first-stage prompt from one discovery batch."""

    discovery_input = (
        batch
        if isinstance(batch, ProtocolControlDiscoveryAgentInput)
        else ProtocolControlDiscoveryAgentInput.from_batch(batch)
    )
    return (
        f"{prompt_template.strip()}\n\n"
        f"{_DISCOVERY_SYSTEM_CONTRACT}\n\n"
        f"输出结构：{_stable_json(protocol_control_discovery_agent_json_schema())}\n\n"
        f"本次发现输入：{_stable_json(discovery_input.model_dump(mode='json'))}\n\n"
        "按 target_units 原文顺序逐项返回一条 decision；context_units 只能阅读。"
        "候选与不确定单元必须保留其结构单元身份，不能被粗筛遗漏或合并。只返回一个完整 JSON 对象。"
    )
def build_protocol_control_discovery_repair_prompt(
    batch: ProtocolControlDiscoveryBatch | ProtocolControlDiscoveryAgentInput,
    *,
    problem: str,
    structure_unit_ids: Sequence[str] | None = None,
) -> str:
    """Build a bounded same-session repair prompt for discovery output."""

    discovery_input = (
        batch
        if isinstance(batch, ProtocolControlDiscoveryAgentInput)
        else ProtocolControlDiscoveryAgentInput.from_batch(batch)
    )
    expected_ids = list(discovery_input.target_structure_unit_ids)
    requested_ids = list(structure_unit_ids or expected_ids)
    unknown_ids = set(requested_ids) - set(expected_ids)
    if unknown_ids:
        raise ValueError(
            "发现定向修复结构单元不属于当前冻结 target_units："
            + "、".join(sorted(unknown_ids))
        )
    return (
        "这是同一发现会话内的有限结构修复，不是重新分析。"
        "系统已冻结批次身份、target_units、context_units 和原文顺序；"
        "只修复下列目标或其直接作用域中的 Schema/闭包错误："
        f"{json.dumps(requested_ids, ensure_ascii=False)}。"
        "不得改变未授权目标的处置或理由，不得创建批次、候选或其他稳定身份，"
        "不得输出额外字段。必须返回当前批次全部 target_units 的完整 JSON，"
        "disposition 只能是 candidate、context_only、non_control、uncertain，"
        "required_context_structure_unit_ids 只能引用当前输入可见结构单元，"
        "并按结构单元 ID 升序排列且不得重复。"
        "沿用首次请求的输出结构，只返回包含 wire_version 和 decisions 的单个 JSON 对象；"
        "不要回显输出结构、$defs 或额外的 JSON 对象。"
        f"\n冻结发现批次：{discovery_input.discovery_batch_id}\n"
        f"结构化问题：{problem[:12000]}\n"
        f"本次发现输入：{_stable_json(discovery_input.model_dump(mode='json'))}"
    )



def build_protocol_control_repair_prompt(
    batch: ProtocolControlDispositionBatch,
    *,
    problem: str,
    structure_unit_ids: Sequence[str] | None = None,
    candidate_ids: Sequence[str] | None = None,
    candidate_indexes: Sequence[int] | None = None,
    obligation_source_span_ids: Sequence[str] | None = None,
    candidate_only: bool = False,
    candidates_only: bool = False,
    source_insert: bool = False,
    source_insert_candidate_only: bool = False,
    baseline_wire_sha256: str | None = None,
) -> str:
    """Build a same-session repair prompt with an explicit bounded scope."""

    unit_ids = list(structure_unit_ids or batch.owned_structure_unit_ids)
    unknown_units = set(unit_ids) - set(batch.owned_structure_unit_ids)
    if unknown_units:
        raise ValueError(f"定向修复结构单元不属于本批次：{sorted(unknown_units)}")
    authorized_unit_ids = set(unit_ids)
    authorized_sources = [
        {
            "structure_unit_id": unit.structure_unit_id,
            "source_ref": unit.source_ref,
            "source_span_ids": unit.source_span_ids,
            "excerpt": unit.excerpt,
        }
        for unit in batch.owned_units
        if unit.structure_unit_id in authorized_unit_ids
    ]
    frozen_workflow_targets = [
        {
            "workflow_stage_id": target.workflow_stage_id,
            "review_stage": target.review_stage.value,
            "display_name": target.display_name,
        }
        for target in batch.known_workflow_stage_targets
    ]
    frozen_target_index = {
        "official": [
            {
                "official_code": target.official_code,
                "catalog_item_id": target.catalog_item_id,
                "label": target.label,
            }
            for target in batch.known_official_targets
        ],
        "procedures": [
            {
                "catalog_item_id": target.catalog_item_id,
                "label": target.label,
                "visit_instance": target.visit_instance,
                "review_stage": target.review_stage.value,
            }
            for target in batch.known_procedure_targets
        ],
    }
    guidance = _repair_problem_guidance(problem)
    guidance_block = f"{guidance}\n" if guidance else ""
    insert_guidance = (
        "这是遗漏要求的来源限定补入，不是改写旧候选。旧候选必须按原顺序逐字保留，"
        "旧处置除授权结构单元外不得改变；只可在 candidate_drafts 末尾新增引用授权原文的候选。"
        "若原文不足以支持候选，不得编造医学要求，应保持失败待核。"
        f"上一轮完整输出摘要：{baseline_wire_sha256}。\n"
        if source_insert else ""
    )
    return (
        f"{_CONTROL_REPAIR_CONTRACT}\n"
        f"{guidance_block}"
        f"{insert_guidance}"
        f"冻结批次：{batch.batch_id}\n"
        f"结构单元范围：{json.dumps(unit_ids, ensure_ascii=False)}\n"
        f"授权结构单元原文与来源定位："
        f"{json.dumps(authorized_sources, ensure_ascii=False)}\n"
        f"冻结审核节点目录（仅可引用，不得新增）："
        f"{json.dumps(frozen_workflow_targets, ensure_ascii=False)}\n"
        "冻结目标索引（只帮助定位；是否覆盖仍须核对首轮输入中的目标原文）："
        f"{json.dumps(frozen_target_index, ensure_ascii=False)}\n"
        f"系统候选身份范围：{json.dumps(list(candidate_ids or []), ensure_ascii=False)}\n"
        f"义务原文定位范围："
        f"{json.dumps(list(obligation_source_span_ids or []), ensure_ascii=False)}\n"
        f"候选草稿位置（仅用于诊断，不得原样输出）："
        f"{json.dumps(list(candidate_indexes or []), ensure_ascii=False)}\n"
        f"校验问题：{problem[:12000]}\n"
        + (
            "只返回一个有原文支持的新增候选，系统保留原候选和范围外处置；"
            "仅返回包含 candidate_draft 的 JSON 对象，严格遵守本请求随附的单候选 JSON Schema。"
            if source_insert_candidate_only
            else "只修复指定的一个候选；系统保留其他候选、处置及其来源。"
            "仅返回包含 candidate_draft 的 JSON 对象，严格遵守本请求随附的单候选 JSON Schema。"
            if candidate_only
            else "只修复指定位置的候选，按候选草稿位置的升序返回同样数量的 candidate_drafts；"
            "系统保留其余候选、全部处置及来源。不得补造、删除或调换候选；"
            "仅返回包含 candidate_drafts 的 JSON 对象，严格遵守本请求随附的修订 JSON Schema。"
            if candidates_only
            else "仍须返回本批全部 owned_units 的完整 disposition 和本批完整候选集合。"
            "请在同一会话内仅返回修复后的完整 wire JSON，严格遵守本请求随附的 JSON Schema；"
            "若当前传输仅支持 JSON 对象，则沿用首轮提示中的输出结构。"
        )
    )


def _candidate_source_texts(
    batch: ProtocolControlDispositionBatch,
    source_structure_unit_ids: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    candidate_unit_ids = set(source_structure_unit_ids)
    source_texts: dict[str, list[str]] = {}
    for unit in batch.owned_units:
        if unit.structure_unit_id not in candidate_unit_ids:
            continue
        for span_id in unit.source_span_ids:
            source_texts.setdefault(span_id, []).append(unit.excerpt)
    return {key: tuple(value) for key, value in source_texts.items()}


def _validate_exact_atom_sources(
    candidate: ProtocolControlAgentWireCandidate,
    *,
    batch: ProtocolControlDispositionBatch,
) -> ProtocolControlAgentWireCandidate:
    source_texts = _candidate_source_texts(
        batch,
        candidate.source_structure_unit_ids,
    )
    allowed_spans = set(source_texts)

    # Deterministic typographic restoration: only quote glyphs, unique contiguous.
    # Performed after runner parse, before strict hydration; preserves raw output hash
    # at the attempt layer and does not consume the global repair budget.
    # Only single/double curved ↔ straight quotes are normalized; all other
    # characters (words, digits, units, comparators, general punctuation, whitespace)
    # remain strict. Restoration succeeds only when the normalized excerpt occurs
    # exactly once within the authorized source texts for its specific span_id.
    candidate = ProtocolControlAgentWireCandidate.model_validate(
        restore_source_fields(candidate.model_dump(mode="json"), source_texts)
    )

    expressions = (
        ("applicability", candidate.applicability_expression),
        ("trigger", candidate.trigger_expression),
        ("exception", candidate.exception_expression),
        *(("repeat_trigger", item.expression) for item in candidate.repeat_trigger_conditions),
    )
    # Strict verbatim check after deterministic restoration.
    for layer, expression in expressions:
        if expression is None:
            continue
        atoms = [atom for group in expression.groups for atom in group.atoms]
        for atom_index, atom in enumerate(atoms):
            for span_id, excerpt in zip(atom.source_span_ids, atom.source_excerpts):
                if span_id not in allowed_spans:
                    raise ProtocolControlAgentWireValidationError(
                        "SOURCE_SCOPE_ESCAPE",
                        f"{layer} 原子引用了本批 owned 之外的来源：{span_id}",
                        structure_unit_ids=candidate.source_structure_unit_ids,
                    )
                if not any(excerpt in source for source in source_texts.get(span_id, ())):
                    raise ProtocolControlAgentWireValidationError(
                        "FABRICATED_EXCERPT",
                        f"{layer} 原子 {atom_index} 的摘录不是来源 {span_id} 的连续原文",
                        structure_unit_ids=candidate.source_structure_unit_ids,
                    )

    for group in candidate.obligation_expression.groups:
        for atom_index, atom in enumerate(group.atoms):
            for span_id, excerpt in zip(atom.source_span_ids, atom.source_excerpts):
                if span_id not in allowed_spans:
                    raise ProtocolControlAgentWireValidationError(
                        "SOURCE_SCOPE_ESCAPE",
                        f"obligation 原子引用了本批 owned 之外的来源：{span_id}",
                        structure_unit_ids=candidate.source_structure_unit_ids,
                    )
                if not any(excerpt in source for source in source_texts.get(span_id, ())):
                    raise ProtocolControlAgentWireValidationError(
                        "FABRICATED_EXCERPT",
                        f"obligation 原子 {atom_index} 的摘录不是来源 {span_id} 的连续原文",
                        structure_unit_ids=candidate.source_structure_unit_ids,
                    )


    return candidate


def _validate_known_targets(
    candidate: ProtocolControlAgentWireCandidate,
    *,
    batch: ProtocolControlDispositionBatch,
) -> None:
    official_codes = {item.official_code for item in batch.known_official_targets}
    procedures = {
        item.catalog_item_id: item for item in batch.known_procedure_targets
    }
    workflow_by_id = {
        item.workflow_stage_id: item for item in batch.known_workflow_stage_targets
    }
    for relation in candidate.cross_source_relations:
        if relation.external_target_kind == ControlRelationTargetKind.OFFICIAL_RULE:
            if relation.external_target_id not in official_codes:
                raise ProtocolControlAgentWireValidationError(
                    "UNKNOWN_OFFICIAL_TARGET",
                    f"关系提案引用了本批未知官方目标：{relation.external_target_id}",
                    structure_unit_ids=candidate.source_structure_unit_ids,
                )
            continue
        if relation.external_target_kind == ControlRelationTargetKind.WORKFLOW_STAGE:
            if relation.external_target_id not in workflow_by_id:
                raise ProtocolControlAgentWireValidationError(
                    "UNKNOWN_WORKFLOW_STAGE_TARGET",
                    f"关系提案引用了本批未知流程节点：{relation.external_target_id}",
                    structure_unit_ids=candidate.source_structure_unit_ids,
                )
            continue
        procedure = procedures.get(relation.external_target_id)
        if procedure is None:
            raise ProtocolControlAgentWireValidationError(
                "UNKNOWN_PROCEDURE_TARGET",
                f"关系提案引用了本批未知流程目标：{relation.external_target_id}",
                structure_unit_ids=candidate.source_structure_unit_ids,
            )
        if relation.kind != CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT:
            continue
        affected_id = relation.affected_workflow_stage_id
        affected = workflow_by_id.get(affected_id or "")
        if affected is None:
            raise ProtocolControlAgentWireValidationError(
                "UNKNOWN_AFFECTED_WORKFLOW_STAGE",
                "补充流程必做项引用了未知的受影响审核节点",
                structure_unit_ids=candidate.source_structure_unit_ids,
            )
        execution_id = procedure_execution_workflow_stage_id(
            procedure, batch.known_workflow_stage_targets
        )
        cross_stage = is_cross_stage_subsequent_control_supplement(
            obligation_expression=candidate.obligation_expression,
            procedure=procedure,
            affected_workflow_stage_id=affected_id,
            workflow_targets=batch.known_workflow_stage_targets,
        )
        if cross_stage:
            if execution_id == affected_id:
                raise ProtocolControlAgentWireValidationError(
                    "PROCEDURE_AFFECTED_STAGE_MISMATCH",
                    "跨阶段后续控制补充的受影响审核节点必须晚于流程必做执行访视",
                    structure_unit_ids=candidate.source_structure_unit_ids,
                )
        elif execution_id != affected_id:
            raise ProtocolControlAgentWireValidationError(
                "PROCEDURE_AFFECTED_STAGE_MISMATCH",
                "补充关系的受影响审核节点与所引用流程必做访视不一致",
                structure_unit_ids=candidate.source_structure_unit_ids,
            )
        if not any(
            node.workflow_stage_id == affected_id
            and node.role == ReviewNodeRole.DECIDE_AT_NODE
            for node in candidate.review_node_bindings
        ):
            raise ProtocolControlAgentWireValidationError(
                "AFFECTED_STAGE_DECISION_MISSING",
                "补充流程必做项必须在其受影响审核节点作本节点判定",
                structure_unit_ids=candidate.source_structure_unit_ids,
            )
        if not any(
            item.due_stage == affected.review_stage
            for item in candidate.minimum_evidence
        ):
            raise ProtocolControlAgentWireValidationError(
                "AFFECTED_STAGE_EVIDENCE_MISSING",
                "补充流程必做项的最低证据不得晚于受影响审核节点",
                structure_unit_ids=candidate.source_structure_unit_ids,
            )


def _validate_temporal_obligation_scope(
    candidate: ProtocolControlAgentWireCandidate,
) -> None:
    kinds = {
        atom.kind
        for group in candidate.obligation_expression.groups
        for atom in group.atoms
    }
    relation_target_kinds = {
        relation.external_target_kind for relation in candidate.cross_source_relations
    }
    node_ids = {
        node.workflow_stage_id for node in candidate.review_node_bindings
    }
    workflow_relation_ids = {
        relation.external_target_id
        for relation in candidate.cross_source_relations
        if relation.external_target_kind == ControlRelationTargetKind.WORKFLOW_STAGE
    }
    if ControlObligationKind.SCHEDULE_OR_VERIFY_VISIT in kinds:
        if ControlRelationTargetKind.REQUIRED_PROCEDURE in relation_target_kinds:
            raise ProtocolControlAgentWireValidationError(
                "VISIT_SCHEDULE_TARGET_TOO_NARROW",
                "访视安排规则必须指向冻结流程节点，不得把通用访视时间窗传播到单个检查项",
                structure_unit_ids=candidate.source_structure_unit_ids,
            )
        if not workflow_relation_ids or not workflow_relation_ids.issubset(node_ids):
            raise ProtocolControlAgentWireValidationError(
                "VISIT_SCHEDULE_WORKFLOW_TARGET_MISSING",
                "访视安排规则必须关联本候选已绑定的冻结流程节点",
                structure_unit_ids=candidate.source_structure_unit_ids,
            )
    if ControlObligationKind.VERIFY_RESULT_VALIDITY in kinds:
        if not any(
            relation.kind == CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT
            and relation.external_target_kind
            == ControlRelationTargetKind.REQUIRED_PROCEDURE
            for relation in candidate.cross_source_relations
        ):
            raise ProtocolControlAgentWireValidationError(
                "RESULT_VALIDITY_PROCEDURE_TARGET_MISSING",
                "结果有效期必须补充到受影响的冻结流程必做项",
                structure_unit_ids=candidate.source_structure_unit_ids,
            )
    if ControlObligationKind.SELECT_BASELINE_VALUE in kinds:
        scoped_targets = relation_target_kinds.intersection(
            {
                ControlRelationTargetKind.REQUIRED_PROCEDURE,
                ControlRelationTargetKind.WORKFLOW_STAGE,
            }
        )
        if not scoped_targets:
            raise ProtocolControlAgentWireValidationError(
                "BASELINE_VALUE_SCOPE_MISSING",
                "基线值选取原则必须明确关联通用流程节点或精确检查项",
                structure_unit_ids=candidate.source_structure_unit_ids,
            )
        if len(scoped_targets) > 1:
            raise ProtocolControlAgentWireValidationError(
                "BASELINE_VALUE_SCOPE_MIXED",
                "通用基线值原则与具体检查项特例必须分成不同候选",
                structure_unit_ids=candidate.source_structure_unit_ids,
            )


def _validate_workflow_stage_bindings(
    candidate: ProtocolControlAgentWireCandidate,
    *,
    batch: ProtocolControlDispositionBatch,
    candidate_index: int,
) -> None:
    targets = {
        item.workflow_stage_id: item
        for item in batch.known_workflow_stage_targets
    }
    if not targets:
        raise ProtocolControlAgentWireValidationError(
            "WORKFLOW_TARGET_CATALOG_MISSING",
            "本批没有冻结 workflow_stage 目录，候选不得输出审核节点绑定",
            structure_unit_ids=candidate.source_structure_unit_ids,
            candidate_indexes=[candidate_index],
        )
    for node in candidate.review_node_bindings:
        target = targets.get(node.workflow_stage_id)
        if target is None:
            raise ProtocolControlAgentWireValidationError(
                "UNKNOWN_WORKFLOW_STAGE_TARGET",
                f"候选 {candidate_index} 选择了本批未知 workflow_stage_id："
                f"{node.workflow_stage_id}",
                structure_unit_ids=candidate.source_structure_unit_ids,
                candidate_indexes=[candidate_index],
            )
        if node.review_stage != target.review_stage:
            raise ProtocolControlAgentWireValidationError(
                "WORKFLOW_REVIEW_STAGE_MISMATCH",
                f"workflow_stage_id {node.workflow_stage_id} 的 review_stage 必须与冻结目录一致："
                f"{target.review_stage.value}",
                structure_unit_ids=candidate.source_structure_unit_ids,
                candidate_indexes=[candidate_index],
            )


def validate_protocol_control_agent_wire(
    wire: ProtocolControlAgentWire,
    batch: ProtocolControlDispositionBatch,
) -> ProtocolControlAgentWire:
    """Return a validated copy after deterministic source-glyph restoration."""

    wire = wire.model_copy(deep=True)

    disposition_ids = [item.structure_unit_id for item in wire.dispositions]
    expected_ids = list(batch.owned_structure_unit_ids)
    if set(disposition_ids) != set(expected_ids):
        missing = sorted(set(expected_ids) - set(disposition_ids))
        extra = sorted(set(disposition_ids) - set(expected_ids))
        raise ProtocolControlAgentWireValidationError(
            "PARTIAL_BATCH",
            f"批次处置必须覆盖全部 owned_units；missing={missing}, extra={extra}",
            structure_unit_ids=(*missing, *extra),
        )

    disposition_by_unit = {item.structure_unit_id: item for item in wire.dispositions}
    known_official_codes = {item.official_code for item in batch.known_official_targets}
    known_procedure_ids = {item.catalog_item_id for item in batch.known_procedure_targets}
    for unit_id, disposition in disposition_by_unit.items():
        procedure_target_ids = disposition.linked_procedure_catalog_item_ids or (
            [disposition.linked_procedure_catalog_item_id]
            if disposition.linked_procedure_catalog_item_id is not None
            else []
        )
        if disposition.disposition == StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY:
            if disposition.linked_official_code is None:
                raise ProtocolControlAgentWireValidationError(
                    "OFFICIAL_TARGET_MISSING",
                    f"官方入排处置缺少已知 IN/EX 目标：{unit_id}",
                    structure_unit_ids=[unit_id],
                )
            if disposition.linked_official_code not in known_official_codes:
                raise ProtocolControlAgentWireValidationError(
                    "UNKNOWN_OFFICIAL_TARGET",
                    f"处置引用了本批未知官方目标：{disposition.linked_official_code}",
                    structure_unit_ids=[unit_id],
                )
        elif disposition.disposition == StructureUnitDispositionKind.REQUIRED_PROCEDURE:
            if not procedure_target_ids:
                raise ProtocolControlAgentWireValidationError(
                    "PROCEDURE_TARGET_MISSING",
                    f"流程必做处置缺少已知目录目标：{unit_id}",
                    structure_unit_ids=[unit_id],
                )
            unknown_procedure_ids = sorted(
                set(procedure_target_ids) - known_procedure_ids
            )
            if unknown_procedure_ids:
                raise ProtocolControlAgentWireValidationError(
                    "UNKNOWN_PROCEDURE_TARGET",
                    "处置引用了本批未知流程目标：" + ",".join(unknown_procedure_ids),
                    structure_unit_ids=[unit_id],
                )
        elif disposition.linked_official_code or procedure_target_ids:
            raise ProtocolControlAgentWireValidationError(
                "DISPOSITION_LINK_MISMATCH",
                f"非对应处置不得携带官方或流程目标：{unit_id}",
                structure_unit_ids=[unit_id],
            )
        requires_non_control_reason = disposition.disposition not in {
            StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
            StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY,
            StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        }
        if requires_non_control_reason:
            if not disposition.notes or not disposition.notes.strip():
                raise ProtocolControlAgentWireValidationError(
                    "NON_CONTROL_REASON_MISSING",
                    f"无候选处置必须给出明确非控制理由：{unit_id}",
                    structure_unit_ids=[unit_id],
                )

    owned_units = set(expected_ids)
    units_by_id = {unit.structure_unit_id: unit for unit in batch.owned_units}
    owned_spans = set(batch.owned_source_span_ids)
    fingerprints: set[str] = set()
    for candidate_index, candidate in enumerate(wire.candidate_drafts):
        if not set(candidate.source_structure_unit_ids) <= owned_units:
            raise ProtocolControlAgentWireValidationError(
                "CANDIDATE_UNIT_SCOPE_ESCAPE",
                f"候选 {candidate_index} 引用了本批之外的结构单元",
                structure_unit_ids=candidate.source_structure_unit_ids,
                candidate_indexes=[candidate_index],
            )
        if not set(candidate.source_span_ids) <= owned_spans:
            raise ProtocolControlAgentWireValidationError(
                "CANDIDATE_SOURCE_SCOPE_ESCAPE",
                f"候选 {candidate_index} 引用了本批之外的来源片段",
                structure_unit_ids=candidate.source_structure_unit_ids,
                candidate_indexes=[candidate_index],
            )
        candidate_owned_spans = {
            span_id
            for unit_id in candidate.source_structure_unit_ids
            for span_id in units_by_id[unit_id].source_span_ids
        }
        if not set(candidate.source_span_ids) <= candidate_owned_spans:
            raise ProtocolControlAgentWireValidationError(
                "CANDIDATE_SOURCE_UNIT_SCOPE_ESCAPE",
                f"候选 {candidate_index} 的 source_span_ids 必须来自其 source_structure_unit_ids 的来源闭包",
                structure_unit_ids=candidate.source_structure_unit_ids,
                candidate_indexes=[candidate_index],
            )
        candidate = _validate_exact_atom_sources(candidate, batch=batch)
        wire.candidate_drafts[candidate_index] = candidate
        fingerprint = _stable_json(candidate.model_dump(mode="json"))
        if fingerprint in fingerprints:
            raise ProtocolControlAgentWireValidationError(
                "DUPLICATE_CANDIDATE",
                f"候选 {candidate_index} 与已有候选完全重复",
                structure_unit_ids=candidate.source_structure_unit_ids,
                candidate_indexes=[candidate_index],
            )
        fingerprints.add(fingerprint)
        if any(
            disposition_by_unit[unit_id].disposition
            != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
            for unit_id in candidate.source_structure_unit_ids
        ):
            raise ProtocolControlAgentWireValidationError(
                "CANDIDATE_DISPOSITION_MISMATCH",
                f"候选 {candidate_index} 的来源结构单元必须处置为其他控制候选",
                structure_unit_ids=candidate.source_structure_unit_ids,
                candidate_indexes=[candidate_index],
            )
        _validate_workflow_stage_bindings(
            candidate,
            batch=batch,
            candidate_index=candidate_index,
        )
        try:
            _validate_known_targets(candidate, batch=batch)
        except ProtocolControlAgentWireValidationError as exc:
            if exc.candidate_indexes:
                raise
            raise ProtocolControlAgentWireValidationError(
                exc.code,
                str(exc).removeprefix(f"{exc.code}: "),
                structure_unit_ids=exc.structure_unit_ids,
                candidate_indexes=[candidate_index],
                candidate_ids=exc.candidate_ids,
                obligation_source_span_ids=exc.obligation_source_span_ids,
                error_class_codes=exc.error_class_codes,
                allow_candidate_repartition=exc.allow_candidate_repartition,
                allow_source_closure_rewrite=exc.allow_source_closure_rewrite,
                allow_post_enrollment_reclassification=exc.allow_post_enrollment_reclassification,
                allow_source_insert=exc.allow_source_insert,
            ) from exc
        _validate_temporal_obligation_scope(candidate)

    candidate_units = {
        unit_id
        for candidate in wire.candidate_drafts
        for unit_id in candidate.source_structure_unit_ids
    }
    for unit_id, disposition in disposition_by_unit.items():
        if disposition.disposition == StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE:
            if unit_id not in candidate_units:
                raise ProtocolControlAgentWireValidationError(
                    "CANDIDATE_MISSING",
                    f"其他控制候选处置没有对应候选草稿：{unit_id}",
                    structure_unit_ids=[unit_id],
                )
    return wire


def _condition_dnf_to_domain(
    value: ProtocolControlAgentWireConditionDnf | None,
    *,
    allow_exception_scopes: bool = False,
) -> ControlConditionDnfDraft | None:
    if value is None:
        return None
    groups: list[ControlConditionGroupDraft] = []
    for group in value.groups:
        if (
            group.waives_trigger_branch_indexes
            or group.activates_obligation_group_indexes
        ) and not allow_exception_scopes:
            raise ValueError("适用性/触发 DNF 不得携带例外作用域或激活义务组序位")
        groups.append(
            ControlConditionGroupDraft(
                atoms=[
                    ControlConditionAtomDraft(
                        statement=atom.statement,
                        evaluation=atom.evaluation,
                        source_span_ids=list(atom.source_span_ids),
                        source_excerpts=list(atom.source_excerpts),
                        time_constraint=atom.time_constraint,
                        requires_professional_judgment=atom.requires_professional_judgment,
                    )
                    for atom in group.atoms
                ],
                waives_trigger_branch_indexes=list(
                    group.waives_trigger_branch_indexes
                ),
                activates_obligation_group_indexes=list(
                    group.activates_obligation_group_indexes
                ),
            )
        )
    return ControlConditionDnfDraft(groups=groups)


def _obligation_dnf_to_domain(
    value: ProtocolControlAgentWireObligationDnf,
) -> ControlObligationDnfDraft:
    return ControlObligationDnfDraft(
        groups=[
            ControlObligationGroupDraft(
                atoms=[
                    ControlObligationAtomDraft(
                        kind=atom.kind,
                        evaluation=atom.evaluation,
                        statement=atom.statement,
                        time_constraint=atom.time_constraint,
                        prospective_period=atom.prospective_period,
                        continuing_obligation=(ControlContinuingObligation(
                            **atom.continuing_obligation.model_dump()
                        ) if atom.continuing_obligation is not None else None),
                        modality=atom.modality,
                        temporal_scope=atom.temporal_scope,
                        source_span_ids=list(atom.source_span_ids),
                        source_excerpts=list(atom.source_excerpts),
                        requires_professional_judgment=atom.requires_professional_judgment,
                    )
                    for atom in group.atoms
                ],
                applies_to_trigger_branch_indexes=list(
                    group.applies_to_trigger_branch_indexes
                ),
            )
            for group in value.groups
        ]
    )


def _candidate_to_domain(
    candidate: ProtocolControlAgentWireCandidate,
) -> ProtocolControlCandidateSemanticDraft:
    return ProtocolControlCandidateSemanticDraft(
        title=candidate.title,
        applicable_population=candidate.applicable_population,
        applicability_expression=_condition_dnf_to_domain(
            candidate.applicability_expression
        ),
        trigger_expression=_condition_dnf_to_domain(candidate.trigger_expression),
        obligation_expression=_obligation_dnf_to_domain(candidate.obligation_expression),
        exception_expression=_condition_dnf_to_domain(
            candidate.exception_expression,
            allow_exception_scopes=True,
        ),
        repeat_trigger_conditions=[ControlRepeatTriggerDraft(
            condition_id=item.condition_id, expression=_condition_dnf_to_domain(item.expression),
            evidence_roles=list(item.evidence_roles),
        ) for item in candidate.repeat_trigger_conditions],
        review_node_bindings=[
            ReviewNodeBinding(
                workflow_stage_id=item.workflow_stage_id,
                review_stage=item.review_stage,
                role=item.role,
                guidance=item.guidance,
            )
            for item in candidate.review_node_bindings
        ],
        minimum_evidence=[
            ControlMinimumEvidenceDraft(
                fact_type=item.fact_type,
                description=item.description,
                due_stage=item.due_stage,
                required_source_types=list(item.required_source_types),
                workflow_stage_ids=list(item.workflow_stage_ids),
                source_policy=item.source_policy,
                atom_refs=list(item.atom_refs),
            )
            for item in candidate.minimum_evidence
        ],
        source_structure_unit_ids=list(candidate.source_structure_unit_ids),
        source_span_ids=list(candidate.source_span_ids),
        cross_source_relations=[
            ControlCrossSourceRelationDraft(
                kind=item.kind,
                external_target_kind=item.external_target_kind,
                external_target_id=item.external_target_id,
                candidate_side=item.candidate_side,
                affected_workflow_stage_id=item.affected_workflow_stage_id,
                notes=item.notes,
            )
            for item in candidate.cross_source_relations
        ],
    )


def wire_to_protocol_control_batch_disposition(
    wire: ProtocolControlAgentWire,
    batch: ProtocolControlDispositionBatch,
) -> ProtocolControlBatchDisposition:
    """Validate and inject only planner batch fields into the domain draft."""

    if wire.wire_version != CONTROL_AGENT_WIRE_VERSION:
        raise ProtocolControlAgentWireValidationError(
            "WIRE_VERSION_INVALID",
            f"不支持的 wire_version：{wire.wire_version}",
        )
    try:
        wire = validate_protocol_control_agent_wire(wire, batch)
        candidates = [_candidate_to_domain(item) for item in wire.candidate_drafts]
        candidate_indexes_by_unit = {
            unit_id: [
                index
                for index, candidate in enumerate(wire.candidate_drafts)
                if unit_id in candidate.source_structure_unit_ids
            ]
            for unit_id in batch.owned_structure_unit_ids
        }
        by_unit = {item.structure_unit_id: item for item in wire.dispositions}
        dispositions = [
            ProtocolControlUnitDispositionDraft(
                structure_unit_id=unit_id,
                disposition=by_unit[unit_id].disposition,
                linked_official_code=by_unit[unit_id].linked_official_code,
                linked_procedure_catalog_item_id=by_unit[unit_id].linked_procedure_catalog_item_id,
                linked_procedure_catalog_item_ids=list(
                    by_unit[unit_id].linked_procedure_catalog_item_ids
                ),
                candidate_draft_indexes=(
                    candidate_indexes_by_unit[unit_id]
                    if by_unit[unit_id].disposition
                    == StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
                    else []
                ),
                notes=by_unit[unit_id].notes,
            )
            for unit_id in batch.owned_structure_unit_ids
        ]
        return ProtocolControlBatchDisposition(
            batch_id=batch.batch_id,
            coverage_manifest_id=batch.coverage_manifest_id,
            owned_structure_unit_ids=list(batch.owned_structure_unit_ids),
            owned_source_span_ids=list(batch.owned_source_span_ids),
            dispositions=dispositions,
            candidate_drafts=candidates,
        )
    except ProtocolControlAgentWireValidationError:
        raise
    except (ValidationError, ValueError) as exc:
        raise ProtocolControlAgentWireValidationError(
            "DOMAIN_DRAFT_INVALID",
            str(exc),
        ) from exc


def hydrate_protocol_control_agent_output(
    value: str | ProtocolControlAgentWire,
    batch: ProtocolControlDispositionBatch,
) -> ProtocolControlBatchDispositionHydrated:
    """Parse/validate a wire and let the control domain assign stable IDs."""

    wire = parse_protocol_control_agent_wire(value) if isinstance(value, str) else value
    draft = wire_to_protocol_control_batch_disposition(wire, batch)
    try:
        return hydrate_protocol_control_batch_disposition(batch, draft)
    except (ValidationError, ValueError) as exc:
        raise ProtocolControlAgentWireValidationError(
            "HYDRATION_INVALID",
            str(exc),
        ) from exc


def parse_protocol_control_agent_output(
    text: str,
    batch: ProtocolControlDispositionBatch,
    *,
    hydrate: bool = True,
) -> ProtocolControlBatchDispositionHydrated | ProtocolControlBatchDisposition:
    """Convenience parser; hydrated output is the safe default."""

    wire = parse_protocol_control_agent_wire(text)
    draft = wire_to_protocol_control_batch_disposition(wire, batch)
    if hydrate:
        try:
            return hydrate_protocol_control_batch_disposition(batch, draft)
        except (ValidationError, ValueError) as exc:
            raise ProtocolControlAgentWireValidationError(
                "HYDRATION_INVALID",
                str(exc),
            ) from exc
    return draft


class ProtocolControlDiscoveryAgentAttempt(ContractModel):
    """One bounded discovery transport or schema-validation attempt."""

    attempt: int = Field(ge=1)
    session_id: str = Field(min_length=1)
    raw_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: Literal["parsed", "schema_invalid", "transport_failed"]
    output: list[ProtocolControlDiscoveryDecision] | None = None
    issues: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_classes: list[str] = Field(default_factory=list)
    rejected_structure_unit_ids: list[str] = Field(default_factory=list)


ProtocolControlDiscoveryAgentAttemptCallback = Callable[
    [ProtocolControlDiscoveryAgentAttempt], None
]


class ProtocolControlDiscoveryAgentRunResult(ContractModel):
    """Bounded discovery result; closure remains a deterministic planner step."""

    status: Literal["已解析", "需要核对"]
    discovery_batch_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    attempts: list[ProtocolControlDiscoveryAgentAttempt] = Field(min_length=1)
    final_output: list[ProtocolControlDiscoveryDecision] | None = None

    @property
    def batch_id(self) -> str:
        """Compatibility view for callers handling deep and discovery runs."""

        return self.discovery_batch_id

    @property
    def final_decisions(
        self,
    ) -> tuple[ProtocolControlDiscoveryDecision, ...] | None:
        return (
            tuple(self.final_output)
            if self.final_output is not None
            else None
        )


class ProtocolControlDiscoveryAgentRunner:
    """Run one discovery batch with bounded same-session schema repair.

    The runner only accepts a complete, in-scope batch response.  It does not
    infer dispositions, create identities, or close the full manifest; those
    responsibilities stay in deterministic planner code.
    """

    def __init__(
        self,
        *,
        max_transport_retries: int = DEFAULT_MAX_TRANSPORT_RETRIES,
        max_schema_repairs: int = DEFAULT_MAX_SCHEMA_REPAIRS,
    ) -> None:
        if max_transport_retries < 0 or max_schema_repairs < 0:
            raise ValueError("重试上限必须为非负整数")
        self._max_transport_retries = max_transport_retries
        self._max_schema_repairs = max_schema_repairs

    def run(
        self,
        batch: ProtocolControlDiscoveryBatch | ProtocolControlDiscoveryAgentInput,
        transport: ProtocolControlDiscoveryAgentTransport,
        *,
        prompt_template: str = DEFAULT_PROTOCOL_CONTROL_DISCOVERY_PROMPT_TEMPLATE,
        accepted_batch_ids: Sequence[str] = (),
        on_attempt: ProtocolControlDiscoveryAgentAttemptCallback | None = None,
    ) -> ProtocolControlDiscoveryAgentRunResult:
        discovery_input = (
            batch
            if isinstance(batch, ProtocolControlDiscoveryAgentInput)
            else ProtocolControlDiscoveryAgentInput.from_batch(batch)
        )
        batch_id = discovery_input.discovery_batch_id
        if batch_id in set(accepted_batch_ids):
            raise ValueError(f"已接受发现批次不得被同会话修复替换：{batch_id}")

        attempts: list[ProtocolControlDiscoveryAgentAttempt] = []

        def record_attempt(attempt: ProtocolControlDiscoveryAgentAttempt) -> None:
            attempts.append(attempt)
            if on_attempt is not None:
                on_attempt(attempt)

        session_id: str | None = None
        raw_text: str | None = None
        prompt = build_protocol_control_discovery_prompt(
            discovery_input,
            prompt_template=prompt_template,
        )
        transport_failures = 0
        while True:
            try:
                response = (
                    transport.start(prompt=prompt)
                    if session_id is None
                    else transport.continue_session(
                        session_id=session_id,
                        prompt=prompt,
                    )
                )
                if session_id is not None and response.session_id != session_id:
                    raise RuntimeError("同会话发现修复不得更换 session_id")
                session_id = response.session_id
                raw_text = response.text
                break
            except Exception as exc:  # noqa: BLE001 - transport boundary
                attempt_id = len(attempts) + 1
                sid = session_id or f"transport-failed-{attempt_id}"
                record_attempt(
                    ProtocolControlDiscoveryAgentAttempt(
                        attempt=attempt_id,
                        session_id=sid,
                        raw_output_sha256=_sha256(str(exc)),
                        outcome="transport_failed",
                        issues=[str(exc)[:2000]],
                    )
                )
                transport_failures += 1
                if (
                    getattr(exc, "uncertain_completion", False)
                    or session_id is not None
                    or transport_failures > self._max_transport_retries
                ):
                    return ProtocolControlDiscoveryAgentRunResult(
                        status="需要核对",
                        discovery_batch_id=batch_id,
                        session_id=sid,
                        attempts=attempts,
                    )

        assert session_id is not None and raw_text is not None
        repairs = 0
        invalid_fingerprints: dict[tuple[str, str, str], int] = {}
        while True:
            try:
                decisions = list(
                    hydrate_protocol_control_discovery_agent_output(
                        raw_text,
                        discovery_input,
                    )
                )
                record_attempt(
                    ProtocolControlDiscoveryAgentAttempt(
                        attempt=len(attempts) + 1,
                        session_id=session_id,
                        raw_output_sha256=_sha256(raw_text),
                        outcome="parsed",
                        output=decisions,
                    )
                )
                return ProtocolControlDiscoveryAgentRunResult(
                    status="已解析",
                    discovery_batch_id=batch_id,
                    session_id=session_id,
                    attempts=attempts,
                    final_output=decisions,
                )
            except Exception as exc:  # noqa: BLE001 - bounded validation boundary
                error = (
                    exc
                    if isinstance(exc, ProtocolControlDiscoveryWireValidationError)
                    else ProtocolControlDiscoveryWireValidationError(
                        "OUTPUT_INVALID",
                        str(exc),
                    )
                )
                raw_output_sha256 = _sha256(raw_text)
                invalid_fingerprint = (
                    raw_output_sha256,
                    error.code,
                    str(error)[:2000],
                )
                invalid_fingerprints[invalid_fingerprint] = (
                    invalid_fingerprints.get(invalid_fingerprint, 0) + 1
                )
                no_progress = invalid_fingerprints[invalid_fingerprint] >= 2
                expected_ids = set(discovery_input.target_structure_unit_ids)
                rejected_ids = [
                    unit_id
                    for unit_id in error.structure_unit_ids
                    if unit_id in expected_ids
                ]
                if not rejected_ids:
                    rejected_ids = list(discovery_input.target_structure_unit_ids)
                record_attempt(
                    ProtocolControlDiscoveryAgentAttempt(
                        attempt=len(attempts) + 1,
                        session_id=session_id,
                        raw_output_sha256=raw_output_sha256,
                        outcome="schema_invalid",
                        issues=(
                            [str(error)[:2000]]
                            if not no_progress
                            else [
                                str(error)[:2000],
                                "连续返回相同无效结果，本发现批次停止自动修复并转为需要核对",
                            ]
                        ),
                        error_code=error.code,
                        error_classes=[error.code],
                        rejected_structure_unit_ids=rejected_ids,
                    )
                )
                if no_progress or repairs >= self._max_schema_repairs:
                    return ProtocolControlDiscoveryAgentRunResult(
                        status="需要核对",
                        discovery_batch_id=batch_id,
                        session_id=session_id,
                        attempts=attempts,
                    )

                repairs += 1
                repair_prompt = build_protocol_control_discovery_repair_prompt(
                    discovery_input,
                    problem=str(error),
                    structure_unit_ids=rejected_ids,
                )
                try:
                    response = transport.continue_session(
                        session_id=session_id,
                        prompt=repair_prompt,
                    )
                    if response.session_id != session_id:
                        raise RuntimeError("同会话发现修复不得更换 session_id")
                    raw_text = response.text
                except Exception as exc2:  # noqa: BLE001 - transport boundary
                    record_attempt(
                        ProtocolControlDiscoveryAgentAttempt(
                            attempt=len(attempts) + 1,
                            session_id=session_id,
                            raw_output_sha256=_sha256(str(exc2)),
                            outcome="transport_failed",
                            issues=[str(exc2)[:2000]],
                            rejected_structure_unit_ids=rejected_ids,
                        )
                    )
                    return ProtocolControlDiscoveryAgentRunResult(
                        status="需要核对",
                        discovery_batch_id=batch_id,
                        session_id=session_id,
                        attempts=attempts,
                    )

class ProtocolControlAgentAttempt(ContractModel):
    attempt: int = Field(ge=1)
    session_id: str = Field(min_length=1)
    raw_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_output_chars: int | None = Field(default=None, ge=0)
    raw_output_text: str | None = Field(default=None, exclude=True)
    outcome: Literal[
        "parsed",
        "schema_invalid",
        "publication_invalid",
        "transport_failed",
    ]
    output: ProtocolControlBatchDispositionHydrated | None = None
    issues: list[str] = Field(default_factory=list)
    error_classes: list[str] = Field(default_factory=list)
    rejected_structure_unit_ids: list[str] = Field(default_factory=list)
    rejected_candidate_ids: list[str] = Field(default_factory=list)



class ProtocolControlAgentRunResult(ContractModel):
    status: Literal["已解析", "需要核对"]
    batch_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    attempts: list[ProtocolControlAgentAttempt] = Field(min_length=1)
    final_output: ProtocolControlBatchDispositionHydrated | None = None
    source_interpretation: SourceInterpretation | None = None
    source_statement_coverage: list[SourceStatementCoverage] = Field(default_factory=list)
    source_target_review: SourceTargetReview | None = None


def source_statement_coverage(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    wire: ProtocolControlAgentWire,
) -> list[SourceStatementCoverage]:
    """Record literal source-to-output links without inferring clinical equivalence."""

    unit_spans = {
        unit.structure_unit_id: set(unit.source_span_ids)
        for unit in batch.owned_units
    }
    dispositions = {item.structure_unit_id: item for item in wire.dispositions}
    entries: list[SourceStatementCoverage] = []
    for index, statement in enumerate(interpretation.statements):
        linked_candidates: list[int] = []
        unit_candidates: list[int] = []
        matched_roles: set[str] = set()
        for candidate_index, candidate in enumerate(wire.candidate_drafts):
            if statement.structure_unit_id not in candidate.source_structure_unit_ids:
                continue
            unit_candidates.append(candidate_index)
            expressions = (
                ("applicability", candidate.applicability_expression),
                ("trigger", candidate.trigger_expression),
                ("obligation", candidate.obligation_expression),
                ("exception", candidate.exception_expression),
            )
            candidate_roles: set[str] = set()
            quote = normalize_source_excerpt(statement.quoted_text)
            for role, expression in expressions:
                if expression is None:
                    continue
                for group in expression.groups:
                    for atom in group.atoms:
                        if not set(atom.source_span_ids) & unit_spans[statement.structure_unit_id]:
                            continue
                        if any(
                            quote in normalize_source_excerpt(excerpt)
                            for excerpt in atom.source_excerpts
                        ):
                            candidate_roles.add(role)
                        if role == "obligation" and atom.continuing_obligation is not None:
                            continuing = atom.continuing_obligation
                            if set(continuing.source_span_ids) & unit_spans[statement.structure_unit_id] and any(
                                quote in normalize_source_excerpt(excerpt)
                                for excerpt in continuing.source_excerpts
                            ):
                                candidate_roles.add("continuing")
            matched_roles.update(candidate_roles)
            if (
                candidate_roles & {"obligation", "continuing"}
                if statement.force in {"required", "prohibited", "recommended"}
                else candidate_roles
            ):
                linked_candidates.append(candidate_index)
        disposition = dispositions[statement.structure_unit_id]
        quote = normalize_source_excerpt(statement.quoted_text)
        exact_official_matches = sorted({
            target.official_code for target in batch.known_official_targets
            if quote and any(
                excerpt is not None and quote in normalize_source_excerpt(excerpt)
                for excerpt in target.source_excerpts
            )
        })
        exact_procedure_matches = sorted({
            target.catalog_item_id for target in batch.known_procedure_targets
            if quote and any(
                excerpt is not None and quote in normalize_source_excerpt(excerpt)
                for excerpt in target.source_excerpts
            )
        })
        status = (
            "expressed" if linked_candidates else
            "candidate_linked" if unit_candidates else
            "linked_only" if disposition.disposition in {
                StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY,
                StructureUnitDispositionKind.REQUIRED_PROCEDURE,
            } else "not_located"
        )
        entries.append(SourceStatementCoverage(
            statement_index=index,
            structure_unit_id=statement.structure_unit_id,
            disposition=disposition.disposition.value,
            status=status,
            candidate_indexes=linked_candidates,
            linked_candidate_indexes=unit_candidates,
            matched_roles=sorted(matched_roles),
            linked_official_code=disposition.linked_official_code,
            linked_procedure_target_ids=(
                disposition.linked_procedure_catalog_item_ids
                or ([disposition.linked_procedure_catalog_item_id]
                    if disposition.linked_procedure_catalog_item_id else [])
            ),
            exact_official_excerpt_matches=exact_official_matches,
            exact_procedure_excerpt_matches=exact_procedure_matches,
        ))
    return entries


ProtocolControlAgentOutputValidator = Callable[
    [ProtocolControlBatchDispositionHydrated],
    None,
]


def _error_class_codes(error: ProtocolControlAgentWireValidationError) -> tuple[str, ...]:
    """Return structured error classes without parsing user-facing text."""

    return tuple(sorted(error.error_class_codes))


def _validate_bounded_output_repair(
    previous: ProtocolControlBatchDispositionHydrated,
    current: ProtocolControlBatchDispositionHydrated,
    *,
    mutable_structure_unit_ids: set[str],
    mutable_candidate_source_keys: set[tuple[str, ...]] | None = None,
    mutable_candidate_source_union: set[str] | None = None,
    allow_candidate_repartition: bool = False,
    allow_source_closure_rewrite: bool = False,
) -> None:
    """Reject semantic drift outside the deterministic repair scope."""

    mutable_candidate_source_keys = mutable_candidate_source_keys or set()
    mutable_candidate_source_union = mutable_candidate_source_union or set()
    closure_rewrite = allow_candidate_repartition or allow_source_closure_rewrite

    def normalized_dispositions(
        output: ProtocolControlBatchDispositionHydrated,
    ) -> dict[str, dict[str, object]]:
        source_key_by_candidate_id = {
            candidate.control_candidate_id: tuple(
                candidate.frozen_structure_unit_ids
            )
            for candidate in output.candidates
        }
        normalized: dict[str, dict[str, object]] = {}
        for item in output.dispositions:
            if item.structure_unit_id in mutable_structure_unit_ids:
                continue
            payload = item.model_dump(mode="json")
            payload["linked_control_candidate_ids"] = sorted(
                source_key_by_candidate_id[candidate_id]
                for candidate_id in item.linked_control_candidate_ids
            )
            normalized[item.structure_unit_id] = payload
        return normalized

    previous_dispositions = normalized_dispositions(previous)
    current_dispositions = normalized_dispositions(current)
    changed_units = {
        unit_id
        for unit_id in previous_dispositions.keys() | current_dispositions.keys()
        if previous_dispositions.get(unit_id) != current_dispositions.get(unit_id)
    }

    def frozen_candidates(
        output: ProtocolControlBatchDispositionHydrated,
    ) -> dict[str, tuple[str, ...]]:
        result: dict[str, tuple[str, ...]] = {}
        for candidate in output.candidates:
            source_units = tuple(candidate.frozen_structure_unit_ids)
            candidate_is_mutable = source_units in mutable_candidate_source_keys or (
                closure_rewrite
                and bool(set(source_units) & mutable_candidate_source_union)
                and set(source_units) <= mutable_candidate_source_union
            )
            if (
                not candidate_is_mutable
                and (
                    mutable_candidate_source_keys
                    or set(source_units).isdisjoint(mutable_structure_unit_ids)
                )
            ):
                result[_stable_json(candidate.model_dump(mode="json"))] = source_units
        return result

    previous_candidates = frozen_candidates(previous)
    current_candidates = frozen_candidates(current)
    if previous_candidates.keys() != current_candidates.keys():
        for payload in previous_candidates.keys() ^ current_candidates.keys():
            changed_units.update(
                unit_id
                for unit_id in (
                    previous_candidates.get(payload) or current_candidates.get(payload) or ()
                )
                if unit_id not in mutable_structure_unit_ids
            )

    if changed_units:
        raise ProtocolControlAgentWireValidationError(
            "REPAIR_SCOPE_ESCAPE",
            "定向修订改动了未被上一轮问题授权的候选或处置；"
            "必须恢复这些单元的上一轮内容，只修复原问题范围",
            structure_unit_ids=sorted(changed_units),
        )


def _restore_bounded_wire_repair(
    previous: ProtocolControlAgentWire,
    current: ProtocolControlAgentWire,
    *,
    mutable_structure_unit_ids: set[str],
    mutable_candidate_source_keys: set[tuple[str, ...]] | None = None,
    mutable_candidate_indexes: set[int] | None = None,
    mutable_candidate_source_union: set[str] | None = None,
    mutable_obligation_source_span_ids: set[str] | None = None,
    allow_candidate_repartition: bool = False,
    allow_source_closure_rewrite: bool = False,
    allow_post_enrollment_reclassification: bool = False,
    allow_source_insert: bool = False,
) -> tuple[ProtocolControlAgentWire, bool]:
    """Restore immutable wire entries before hydration and gate validation."""

    mutable_candidate_source_keys = mutable_candidate_source_keys or set()
    mutable_candidate_indexes = mutable_candidate_indexes or set()
    mutable_candidate_source_union = mutable_candidate_source_union or set()
    closure_rewrite = allow_candidate_repartition or allow_source_closure_rewrite
    mutable_obligation_source_span_ids = (
        mutable_obligation_source_span_ids or set()
    )
    if allow_source_insert:
        if not mutable_structure_unit_ids or not mutable_obligation_source_span_ids:
            raise ProtocolControlAgentWireValidationError(
                "REPAIR_SCOPE_ESCAPE", "来源补入缺少明确的结构单元或原文定位"
            )
        prior = previous.candidate_drafts
        if current.candidate_drafts[:len(prior)] != prior or len(current.candidate_drafts) <= len(prior):
            raise ProtocolControlAgentWireValidationError(
                "REPAIR_SCOPE_ESCAPE", "来源补入只能在旧候选后新增候选，不得改写或删除旧候选"
            )
        old_dispositions = {item.structure_unit_id: item for item in previous.dispositions}
        if [item.structure_unit_id for item in current.dispositions] != [
            item.structure_unit_id for item in previous.dispositions
        ] or any(
            item != old_dispositions[item.structure_unit_id]
            for item in current.dispositions
            if item.structure_unit_id not in mutable_structure_unit_ids
        ):
            raise ProtocolControlAgentWireValidationError(
                "REPAIR_SCOPE_ESCAPE", "来源补入改动了范围外的结构单元处置"
            )
        for candidate in current.candidate_drafts[len(prior):]:
            if not set(candidate.source_structure_unit_ids) <= mutable_structure_unit_ids or not (
                set(candidate.source_span_ids) & mutable_obligation_source_span_ids
            ) or not set(candidate.source_span_ids) <= mutable_obligation_source_span_ids:
                raise ProtocolControlAgentWireValidationError(
                    "REPAIR_SCOPE_ESCAPE", "新增候选没有绑定授权结构单元和原文定位"
                )
        return current, False
    previous_dispositions = {
        item.structure_unit_id: item for item in previous.dispositions
    }
    dispositions = [
        item
        if item.structure_unit_id in mutable_structure_unit_ids
        else previous_dispositions[item.structure_unit_id]
        for item in current.dispositions
    ]

    if mutable_obligation_source_span_ids:
        if closure_rewrite or not mutable_candidate_source_keys:
            raise ProtocolControlAgentWireValidationError(
                "REPAIR_SCOPE_ESCAPE",
                "义务原子定向修订必须绑定候选来源，"
                "且不得同时改变候选分区",
            )
        previous_by_key: dict[
            tuple[str, ...], list[ProtocolControlAgentWireCandidate]
        ] = {}
        current_by_key: dict[
            tuple[str, ...], list[ProtocolControlAgentWireCandidate]
        ] = {}
        for candidate in previous.candidate_drafts:
            previous_by_key.setdefault(
                tuple(candidate.source_structure_unit_ids), []
            ).append(candidate)
        for candidate in current.candidate_drafts:
            current_by_key.setdefault(
                tuple(candidate.source_structure_unit_ids), []
            ).append(candidate)
        candidates = []
        for previous_candidate in previous.candidate_drafts:
            key = tuple(previous_candidate.source_structure_unit_ids)
            if key not in mutable_candidate_source_keys:
                candidates.append(previous_candidate)
                continue
            if (
                len(previous_by_key.get(key, ())) != 1
                or len(current_by_key.get(key, ())) != 1
            ):
                raise ProtocolControlAgentWireValidationError(
                    "REPAIR_SCOPE_ESCAPE",
                    "义务原子定向修订时候选对应关系不唯一",
                    structure_unit_ids=list(key),
                )
            current_candidate = current_by_key[key][0]
            previous_groups = previous_candidate.obligation_expression.groups
            current_groups = current_candidate.obligation_expression.groups
            if len(previous_groups) != len(current_groups):
                raise ProtocolControlAgentWireValidationError(
                    "REPAIR_SCOPE_ESCAPE",
                    "义务原子定向修订不得拆分、合并或重排义务组",
                    structure_unit_ids=list(key),
                )
            restored_groups: list[ProtocolControlAgentWireObligationGroup] = []
            covered_span_ids: set[str] = set()
            for previous_group, current_group in zip(
                previous_groups, current_groups, strict=True
            ):
                if (
                    previous_group.applies_to_trigger_branch_indexes
                    != current_group.applies_to_trigger_branch_indexes
                ):
                    raise ProtocolControlAgentWireValidationError(
                        "REPAIR_SCOPE_ESCAPE",
                        "义务原子定向修订不得改变义务组的触发分支范围",
                        structure_unit_ids=list(key),
                    )
                previous_atoms = {
                    tuple(atom.source_span_ids): atom for atom in previous_group.atoms
                }
                current_atoms = {
                    tuple(atom.source_span_ids): atom for atom in current_group.atoms
                }
                if (
                    len(previous_atoms) != len(previous_group.atoms)
                    or len(current_atoms) != len(current_group.atoms)
                    or previous_atoms.keys() != current_atoms.keys()
                ):
                    raise ProtocolControlAgentWireValidationError(
                        "REPAIR_SCOPE_ESCAPE",
                        "义务原子定向修订需要唯一且不变的原文定位；"
                        "拆分、合并或重复定位时必须人工核对",
                        structure_unit_ids=list(key),
                    )
                atoms: list[ProtocolControlAgentWireObligationAtom] = []
                for source_key, previous_atom in previous_atoms.items():
                    source_ids = set(source_key)
                    intersects = bool(
                        source_ids & mutable_obligation_source_span_ids
                    )
                    if (
                        intersects
                        and not source_ids <= mutable_obligation_source_span_ids
                    ):
                        raise ProtocolControlAgentWireValidationError(
                            "REPAIR_SCOPE_ESCAPE",
                            "授权原文定位与多来源义务原子交叉，不能自动局部修订",
                            structure_unit_ids=list(key),
                        )
                    if intersects:
                        atoms.append(current_atoms[source_key])
                        covered_span_ids.update(source_ids)
                    else:
                        atoms.append(previous_atom)
                restored_groups.append(previous_group.model_copy(update={"atoms": atoms}))
            expected_span_ids = mutable_obligation_source_span_ids & set(
                previous_candidate.source_span_ids
            )
            if covered_span_ids != expected_span_ids:
                raise ProtocolControlAgentWireValidationError(
                    "REPAIR_SCOPE_ESCAPE",
                    "义务原子定向修订未完整覆盖授权原文定位",
                    structure_unit_ids=list(key),
                )
            candidates.append(
                previous_candidate.model_copy(
                    update={
                        "obligation_expression": (
                            previous_candidate.obligation_expression.model_copy(
                                update={"groups": restored_groups}
                            )
                        )
                    }
                )
            )
    elif closure_rewrite:
        if not mutable_candidate_source_union:
            raise ProtocolControlAgentWireValidationError(
                "REPAIR_SCOPE_ESCAPE",
                "候选重分区缺少完整的来源闭包，不能自动修订",
            )
        frozen_candidates = [
            candidate
            for candidate in previous.candidate_drafts
            if tuple(candidate.source_structure_unit_ids)
            not in mutable_candidate_source_keys
        ]
        mutable_candidates = [
            candidate
            for candidate in current.candidate_drafts
            if set(candidate.source_structure_unit_ids)
            <= mutable_candidate_source_union
            and bool(
                set(candidate.source_structure_unit_ids)
                & mutable_candidate_source_union
            )
        ]
        current_union = {
            unit_id
            for candidate in mutable_candidates
            for unit_id in candidate.source_structure_unit_ids
        }
        crossing_candidates = [
            candidate
            for candidate in current.candidate_drafts
            if set(candidate.source_structure_unit_ids) & mutable_candidate_source_union
            and not set(candidate.source_structure_unit_ids)
            <= mutable_candidate_source_union
        ]
        dropped_units = mutable_candidate_source_union - current_union
        permitted_drop = (
            allow_post_enrollment_reclassification
            and bool(dropped_units)
            and dropped_units <= {item.structure_unit_id for item in dispositions}
            and all(
                item.disposition == StructureUnitDispositionKind.POST_TREATMENT_EXECUTION
                and item.notes
                for item in dispositions
                if item.structure_unit_id in dropped_units
            )
        )
        if (
            crossing_candidates
            or not current_union <= mutable_candidate_source_union
            or (dropped_units and not permitted_drop)
        ):
            raise ProtocolControlAgentWireValidationError(
                "REPAIR_SCOPE_ESCAPE",
                "候选重分区必须保留授权来源，或将移出单元明确处置为治疗后执行；"
                "不得与范围外候选交叉",
                structure_unit_ids=sorted(mutable_candidate_source_union),
            )
        candidates = [*frozen_candidates, *mutable_candidates]
    elif mutable_candidate_indexes:
        if len(previous.candidate_drafts) != len(current.candidate_drafts):
            raise ProtocolControlAgentWireValidationError(
                "REPAIR_SCOPE_ESCAPE",
                "定向修订不得增删候选；候选拆分或合并必须由对应问题明确授权",
            )
        if any(
            index < 0 or index >= len(previous.candidate_drafts)
            for index in mutable_candidate_indexes
        ):
            raise ProtocolControlAgentWireValidationError(
                "REPAIR_SCOPE_ESCAPE",
                "定向修订候选位置超出上一轮范围",
            )
        remaining_current = list(current.candidate_drafts)
        mutable_source_keys = {
            tuple(previous.candidate_drafts[index].source_structure_unit_ids)
            for index in mutable_candidate_indexes
        }
        for index, previous_candidate in enumerate(previous.candidate_drafts):
            if index in mutable_candidate_indexes:
                continue
            previous_source_key = tuple(
                previous_candidate.source_structure_unit_ids
            )
            matches = [
                candidate
                for candidate in remaining_current
                if (
                    candidate == previous_candidate
                    if previous_source_key in mutable_source_keys
                    else tuple(candidate.source_structure_unit_ids)
                    == previous_source_key
                )
            ]
            expected_match_count = (
                1 if previous_source_key in mutable_source_keys else None
            )
            if not matches or (
                expected_match_count is not None
                and len(matches) != expected_match_count
            ):
                raise ProtocolControlAgentWireValidationError(
                    "REPAIR_SCOPE_ESCAPE",
                    "定向修订改动了未获授权的同源候选，或候选对应关系不唯一",
                    structure_unit_ids=list(
                        previous_candidate.source_structure_unit_ids
                    ),
                )
            remaining_current.remove(matches[0])
        previous_mutable = [
            previous.candidate_drafts[index]
            for index in sorted(mutable_candidate_indexes)
        ]
        previous_source_keys = sorted(
            tuple(candidate.source_structure_unit_ids)
            for candidate in previous_mutable
        )
        current_source_keys = sorted(
            tuple(candidate.source_structure_unit_ids)
            for candidate in remaining_current
        )
        if previous_source_keys != current_source_keys:
            raise ProtocolControlAgentWireValidationError(
                "REPAIR_SCOPE_ESCAPE",
                "定向修订不得改变获授权候选的来源范围",
                structure_unit_ids=sorted(
                    {
                        unit_id
                        for candidate in [*previous_mutable, *remaining_current]
                        for unit_id in candidate.source_structure_unit_ids
                    }
                ),
            )
        replacements_by_source: dict[
            tuple[str, ...], list[ProtocolControlAgentWireCandidate]
        ] = {}
        for candidate in remaining_current:
            replacements_by_source.setdefault(
                tuple(candidate.source_structure_unit_ids), []
            ).append(candidate)
        for values in replacements_by_source.values():
            values.sort(key=lambda candidate: _stable_json(candidate.model_dump(mode="json")))
        candidates = []
        for index, previous_candidate in enumerate(previous.candidate_drafts):
            if index not in mutable_candidate_indexes:
                candidates.append(previous_candidate)
                continue
            candidates.append(
                replacements_by_source[
                    tuple(previous_candidate.source_structure_unit_ids)
                ].pop(0)
            )
    elif mutable_candidate_source_keys:
        previous_by_key: dict[tuple[str, ...], list[ProtocolControlAgentWireCandidate]] = {}
        current_by_key: dict[tuple[str, ...], list[ProtocolControlAgentWireCandidate]] = {}
        for candidate in previous.candidate_drafts:
            previous_by_key.setdefault(
                tuple(candidate.source_structure_unit_ids), []
            ).append(candidate)
        for candidate in current.candidate_drafts:
            current_by_key.setdefault(
                tuple(candidate.source_structure_unit_ids), []
            ).append(candidate)
        mutable_source_union = {
            unit_id
            for key in mutable_candidate_source_keys
            for unit_id in key
        }
        unexpected_partition_keys = [
            key
            for key in current_by_key
            if key not in previous_by_key and set(key) & mutable_source_union
        ]
        if unexpected_partition_keys:
            raise ProtocolControlAgentWireValidationError(
                "REPAIR_SCOPE_ESCAPE",
                "定向修订新增了候选来源分区，但当前问题未授权候选拆分或合并",
                structure_unit_ids=sorted(
                    {
                        unit_id
                        for key in unexpected_partition_keys
                        for unit_id in key
                    }
                ),
            )
        for key in mutable_candidate_source_keys:
            if len(previous_by_key.get(key, ())) != 1 or len(current_by_key.get(key, ())) != 1:
                raise ProtocolControlAgentWireValidationError(
                    "REPAIR_SCOPE_ESCAPE",
                    "定向修订候选发生拆分、合并或对应关系不唯一，不能自动保留",
                    structure_unit_ids=list(key),
                )
        candidates = [
            (
                current_by_key[key][0]
                if key in mutable_candidate_source_keys
                else candidate
            )
            for candidate in previous.candidate_drafts
            for key in [tuple(candidate.source_structure_unit_ids)]
        ]
    else:
        mutable_candidates: list[ProtocolControlAgentWireCandidate] = []
        for candidate in current.candidate_drafts:
            source_units = set(candidate.source_structure_unit_ids)
            if source_units <= mutable_structure_unit_ids:
                mutable_candidates.append(candidate)
            elif source_units & mutable_structure_unit_ids:
                raise ProtocolControlAgentWireValidationError(
                    "REPAIR_SCOPE_ESCAPE",
                    "定向修订不得将授权单元与范围外单元合并成新候选",
                    structure_unit_ids=sorted(source_units - mutable_structure_unit_ids),
                )

        frozen_candidates = [
            candidate
            for candidate in previous.candidate_drafts
            if set(candidate.source_structure_unit_ids).isdisjoint(
                mutable_structure_unit_ids
            )
        ]
        candidates = [*frozen_candidates, *mutable_candidates]
    # ponytail: skip sort when repair scope is wire-position keyed; title/json
    # sort would swap same-source siblings and break candidate_indexes identity.
    if not mutable_candidate_indexes:
        candidates = sorted(
            candidates,
            key=lambda item: (
                tuple(item.source_structure_unit_ids),
                item.title,
                _stable_json(item.model_dump(mode="json")),
            ),
        )
    restored = current.model_copy(
        update={
            "dispositions": dispositions,
            "candidate_drafts": candidates,
        }
    )
    return restored, restored != current


def _candidate_ids_from_wire(
    wire: ProtocolControlAgentWire | None,
    batch: ProtocolControlDispositionBatch,
) -> list[str]:
    if wire is None:
        return []
    ids: list[str] = []
    for candidate in wire.candidate_drafts:
        try:
            domain_candidate = _candidate_to_domain(candidate)
        except (ValidationError, ValueError):
            # A parsed wire can still fail a stricter domain-draft check (for
            # example, an empty optional guidance string).  There is no
            # accepted system candidate identity to expose for that draft;
            # keep repair bounded to the batch/unit scope instead of allowing
            # diagnostic ID derivation to mask the original rejection.
            continue
        fingerprint = hashlib.sha256(
            _stable_json((domain_candidate.model_dump(mode="json"),)).encode("utf-8")
        ).hexdigest()[:24]
        ids.append(
            stable_protocol_control_candidate_id(
                batch.coverage_manifest_id,
                batch.batch_id,
                candidate.source_structure_unit_ids,
                fingerprint,
                0,
            )
        )
    return ids


def _merge_candidate_repair(
    raw_text: str,
    baseline: ProtocolControlAgentWire | Mapping[str, Any],
    index: int,
) -> ProtocolControlAgentWire:
    """Replace one draft while keeping every other model field unchanged."""

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ProtocolControlAgentWireValidationError("INVALID_JSON", str(exc)) from exc
    if not isinstance(payload, dict) or set(payload) != {"candidate_draft"}:
        raise ProtocolControlAgentWireValidationError(
            "CANDIDATE_REPAIR_SHAPE_INVALID", "单候选修订只接受 candidate_draft"
        )
    forbidden = _find_forbidden_provider_key(
        {"candidate_drafts": [payload["candidate_draft"]]}
    )
    if forbidden is not None:
        raise ProtocolControlAgentWireValidationError(
            "PROVIDER_ID_FORBIDDEN", f"模型不得填写系统身份 {forbidden[1]}"
        )
    try:
        _collapse_exact_duplicate_day_bounds(payload["candidate_draft"])
        if isinstance(baseline, ProtocolControlAgentWire) and 0 <= index < len(baseline.candidate_drafts):
            _restore_unchanged_time_operands(
                payload["candidate_draft"], baseline.candidate_drafts[index]
            )
        candidate = ProtocolControlAgentWireCandidate.model_validate(
            payload["candidate_draft"]
        )
        merged = (
            baseline.model_dump(mode="json")
            if isinstance(baseline, ProtocolControlAgentWire)
            else deepcopy(dict(baseline))
        )
        if not 0 <= index < len(merged["candidate_drafts"]):
            raise ValueError("单候选修订位置不属于原始批次")
        if not isinstance(baseline, ProtocolControlAgentWire):
            original = merged["candidate_drafts"][index]
            if any(
                candidate.model_dump(mode="json")[field] != original.get(field)
                for field in ("source_structure_unit_ids", "source_span_ids")
            ):
                raise ValueError("单候选修订不得改变原始来源范围")
        merged["candidate_drafts"][index] = candidate.model_dump(mode="json")
        return ProtocolControlAgentWire.model_validate(merged)
    except (ValidationError, ValueError) as exc:
        raise ProtocolControlAgentWireValidationError(
            "CANDIDATE_REPAIR_INVALID", _validation_error_summary(exc)
            if isinstance(exc, ValidationError) else str(exc),
        ) from exc


def _restore_unchanged_time_operands(
    draft: dict[str, Any], previous: ProtocolControlAgentWireCandidate
) -> None:
    """Retain a checked date attribute only for an unchanged source/time obligation."""

    prior_atoms = [
        atom.model_dump(mode="json")
        for group in previous.obligation_expression.groups
        for atom in group.atoms
    ]
    for group in draft.get("obligation_expression", {}).get("groups", []):
        for atom in group.get("atoms", []):
            evaluation = atom.get("evaluation")
            if (
                not isinstance(evaluation, dict)
                or evaluation.get("time_operand_attribute") is not None
                or not isinstance(atom.get("time_constraint"), dict)
            ):
                continue
            try:
                current_time = TimeConstraint.model_validate(atom["time_constraint"])
            except ValidationError:
                continue
            matches = [
                old for old in prior_atoms
                if old.get("time_constraint") is not None
                and TimeConstraint.model_validate(old["time_constraint"]) == current_time
                and all(atom.get(field) == old.get(field) for field in (
                    "kind", "modality", "temporal_scope", "prospective_period",
                    "continuing_obligation", "source_span_ids", "source_excerpts",
                    "requires_professional_judgment",
                ))
                and all(evaluation.get(field) == (old.get("evaluation") or {}).get(field)
                        for field in (
                            "determination_mode", "operation", "predicate",
                            "operand_attribute", "time_purpose", "observation_policy",
                            "repeat_scheme", "source_span_ids", "source_excerpts",
                        ))
                and evaluation.get("version", "control-atom-evaluation/v4")
                == (old.get("evaluation") or {}).get("version", "control-atom-evaluation/v4")
            ]
            if len(matches) == 1:
                old_attribute = (matches[0].get("evaluation") or {}).get("time_operand_attribute")
                if old_attribute in {"date_range", "record_time"}:
                    evaluation["time_operand_attribute"] = old_attribute


def _parse_repartition_with_checked_time(
    raw_text: str, previous: ProtocolControlAgentWire
) -> ProtocolControlAgentWire:
    """Keep prior checked time fields when a bounded source regrouping preserves an atom."""

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return parse_protocol_control_agent_wire(raw_text)
    if isinstance(payload, dict) and isinstance(payload.get("candidate_drafts"), list):
        for draft in payload["candidate_drafts"]:
            if not isinstance(draft, dict):
                continue
            source_ids = set(draft.get("source_structure_unit_ids") or ())
            matches = [
                candidate for candidate in previous.candidate_drafts
                if source_ids and source_ids <= set(candidate.source_structure_unit_ids)
            ]
            if len(matches) == 1:
                _restore_unchanged_time_operands(draft, matches[0])
    return parse_protocol_control_agent_wire(json.dumps(payload, ensure_ascii=False))


def _build_post_treatment_repair_prompt(
    batch: ProtocolControlDispositionBatch,
    previous: ProtocolControlAgentWire,
    index: int,
    problem: str,
) -> str:
    candidate = previous.candidate_drafts[index]
    units = [
        {"structure_unit_id": unit.structure_unit_id, "excerpt": unit.excerpt,
         "source_span_ids": unit.source_span_ids}
        for unit in batch.owned_units
        if unit.structure_unit_id in candidate.source_structure_unit_ids
    ]
    atoms = [
        {"group_index": group_index, "atom_index": atom_index,
         "kind": atom.kind.value, "statement": atom.statement,
         "source_span_ids": atom.source_span_ids, "source_excerpts": atom.source_excerpts}
        for group_index, group in enumerate(candidate.obligation_expression.groups)
        for atom_index, atom in enumerate(group.atoms)
    ]
    return (
        "这是同一方案Agent对一个混合来源候选的有界修订。逐个核原文单元和义务原子；"
        "只列出确属入排节点之后执行而必须移走的原子坐标。未列出的原子由系统原样保留，"
        "包括已核时间、求值与原文，不要重写它们。仅当一个原文单元没有任何仍有效的当前节点"
        "要求时，才在 removed_unit_dispositions 中将其明确处置为 post_treatment_execution；"
        "仍含筛选/导入/基线限制的单元必须留下。移出的单元在 notes 中给出原文短摘录及理由。"
        "重写剩余候选的 title、review_node_bindings、minimum_evidence、cross_source_relations，"
        "不得继续要求本次证明治疗后才发生的事实。最低证据 atom_refs 使用移除后各组的新序位。"
        "不确定应保留失败待核，不得猜测阶段或删除整段。只返回请求结构的JSON。\n"
        f"校验问题：{problem[:1800]}\n"
        f"原文单元：{_stable_json(units)}\n"
        f"原候选原子：{_stable_json(atoms)}\n"
        f"原候选其余字段：{_stable_json({'title': candidate.title, 'review_node_bindings': [x.model_dump(mode='json') for x in candidate.review_node_bindings], 'minimum_evidence': [x.model_dump(mode='json') for x in candidate.minimum_evidence], 'cross_source_relations': [x.model_dump(mode='json') for x in candidate.cross_source_relations]})}"
    )


def _merge_post_treatment_scope_repair(
    raw_text: str,
    previous: ProtocolControlAgentWire,
    index: int,
    batch: ProtocolControlDispositionBatch,
) -> ProtocolControlAgentWire:
    try:
        repair = _PostTreatmentScopeRepair.model_validate_json(raw_text)
        old = previous.candidate_drafts[index]
        removed = {(item.group_index, item.atom_index) for item in repair.removed_atoms}
        if len(removed) != len(repair.removed_atoms):
            raise ValueError("移出原子定位不得重复")
        old_atoms = {
            (group_index, atom_index)
            for group_index, group in enumerate(old.obligation_expression.groups)
            for atom_index, _ in enumerate(group.atoms)
        }
        if not removed < old_atoms:
            raise ValueError("只可移出原候选的部分原子，至少保留一项")
        groups = []
        for group_index, group in enumerate(old.obligation_expression.groups):
            atoms = [atom for atom_index, atom in enumerate(group.atoms)
                     if (group_index, atom_index) not in removed]
            if not atoms:
                raise ValueError("不能留下空义务组并改变原条件逻辑")
            groups.append(group.model_copy(update={"atoms": atoms}))
        removed_units = {item.structure_unit_id for item in repair.removed_unit_dispositions}
        if len(removed_units) != len(repair.removed_unit_dispositions):
            raise ValueError("移出单元不得重复")
        if not removed_units <= set(old.source_structure_unit_ids) or any(
            item.disposition != StructureUnitDispositionKind.POST_TREATMENT_EXECUTION
            or not item.notes
            for item in repair.removed_unit_dispositions
        ):
            raise ValueError("移出单元必须属于原候选并明确给出治疗后处置及依据")
        unit_spans = {
            unit.structure_unit_id: set(unit.source_span_ids)
            for unit in batch.owned_units
        }
        removed_spans = set().union(*(unit_spans[unit_id] for unit_id in removed_units)) if removed_units else set()
        retained_atoms = [atom for group in groups for atom in group.atoms]
        if any(set(atom.source_span_ids) & removed_spans for atom in retained_atoms):
            raise ValueError("移出单元仍被保留的义务引用")
        if any(set(evidence.source_policy.source_span_ids) & removed_spans
               for evidence in repair.minimum_evidence):
            raise ValueError("新最低证据仍引用移出的原文单元")
        retained_source_ids = sorted(set(old.source_span_ids) - removed_spans)
        candidate = old.model_copy(update={
            "title": repair.title,
            "obligation_expression": old.obligation_expression.model_copy(update={"groups": groups}),
            "review_node_bindings": repair.review_node_bindings,
            "minimum_evidence": repair.minimum_evidence,
            "cross_source_relations": repair.cross_source_relations,
            "source_structure_unit_ids": sorted(set(old.source_structure_unit_ids) - removed_units),
            "source_span_ids": retained_source_ids,
        })
        updated = previous.model_dump(mode="json")
        updated["candidate_drafts"][index] = candidate.model_dump(mode="json")
        disposition_by_unit = {item.structure_unit_id: item for item in repair.removed_unit_dispositions}
        updated["dispositions"] = [
            disposition_by_unit.get(item.structure_unit_id, item).model_dump(mode="json")
            for item in previous.dispositions
        ]
        return ProtocolControlAgentWire.model_validate(updated)
    except (ValidationError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProtocolControlAgentWireValidationError(
            "POST_TREATMENT_REPAIR_INVALID",
            _validation_error_summary(exc) if isinstance(exc, ValidationError) else str(exc),
        ) from exc


def _merge_source_candidate_insert(
    raw_text: str,
    baseline: ProtocolControlAgentWire,
    *,
    authorized_unit_ids: set[str],
) -> ProtocolControlAgentWire:
    """Append one model-authored candidate; derive only its bookkeeping links."""

    try:
        payload = json.loads(raw_text)
        if not isinstance(payload, dict) or set(payload) != {"candidate_draft"}:
            raise ValueError("来源补入只接受 candidate_draft")
        _collapse_exact_duplicate_day_bounds(payload["candidate_draft"])
        candidate = ProtocolControlAgentWireCandidate.model_validate(payload["candidate_draft"])
        if not set(candidate.source_structure_unit_ids) <= authorized_unit_ids:
            raise ValueError("新增候选超出授权原文单元")
        previous_by_unit = {item.structure_unit_id: item for item in baseline.dispositions}
        if any(
            previous_by_unit[unit_id].disposition not in {
                StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
                StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
            }
            for unit_id in candidate.source_structure_unit_ids
        ):
            raise ValueError("已有正式条款或流程处置不能被单候选补入覆盖")
        updated = baseline.model_dump(mode="json")
        updated["candidate_drafts"].append(candidate.model_dump(mode="json"))
        for item in updated["dispositions"]:
            if item["structure_unit_id"] in candidate.source_structure_unit_ids:
                item["disposition"] = StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value
                item["notes"] = None
        return ProtocolControlAgentWire.model_validate(updated)
    except (KeyError, ValidationError, ValueError) as exc:
        raise ProtocolControlAgentWireValidationError(
            "SOURCE_INSERT_INVALID",
            _validation_error_summary(exc) if isinstance(exc, ValidationError) else str(exc),
        ) from exc


def _invalid_candidate_payload(raw_text: str) -> tuple[dict[str, Any], tuple[int, ...]] | None:
    """Retain dispositions and valid siblings when drafts fail wire validation."""

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or set(payload) != {
        "wire_version", "dispositions", "candidate_drafts"
    } or payload["wire_version"] != CONTROL_AGENT_WIRE_VERSION:
        return None
    if _find_forbidden_provider_key(payload) is not None:
        return None
    dispositions = payload["dispositions"]
    drafts = payload["candidate_drafts"]
    if not isinstance(dispositions, list) or not dispositions or not isinstance(drafts, list):
        return None
    try:
        validated = [ProtocolControlAgentWireDisposition.model_validate(item) for item in dispositions]
    except (ValidationError, ValueError):
        return None
    if len({item.structure_unit_id for item in validated}) != len(validated):
        return None
    invalid_indexes: list[int] = []
    for index, draft in enumerate(drafts):
        if not isinstance(draft, dict) or any(
            not isinstance(draft.get(field), list)
            or not draft[field]
            or not all(isinstance(item, str) and item.strip() for item in draft[field])
            or draft[field] != sorted(set(draft[field]))
            for field in ("source_structure_unit_ids", "source_span_ids")
        ):
            return None
        try:
            ProtocolControlAgentWireCandidate.model_validate(draft)
        except (ValidationError, ValueError):
            invalid_indexes.append(index)
    return (payload, tuple(invalid_indexes)) if invalid_indexes else None


def _single_invalid_candidate_payload(raw_text: str) -> tuple[dict[str, Any], int] | None:
    result = _invalid_candidate_payload(raw_text)
    return (result[0], result[1][0]) if result is not None and len(result[1]) == 1 else None


def _invalid_obligation_atom_path(
    error: ProtocolControlAgentWireValidationError,
    baseline: Mapping[str, Any],
    candidate_index: int,
) -> tuple[int, int, int] | None:
    """Find one malformed atom without treating sibling errors as its repair scope."""

    cause = error.__cause__
    if not isinstance(cause, ValidationError):
        return None
    locations = [tuple(item["loc"]) for item in cause.errors(include_url=False)]
    paths: set[tuple[int, int, int]] = set()
    for location in locations:
        if (
            len(location) < 8
            or location[0] != "candidate_drafts"
            or not isinstance(location[1], int)
            or location[2:4] != ("obligation_expression", "groups")
            or not isinstance(location[4], int)
            or location[5] != "atoms"
            or not isinstance(location[6], int)
            or location[7] not in {"evaluation", "time_constraint"}
        ):
            return None
        paths.add((location[1], location[4], location[6]))
    if len(paths) != 1:
        return None
    path = next(iter(paths))
    if path[0] != candidate_index:
        return None
    try:
        atom = baseline["candidate_drafts"][path[0]]["obligation_expression"]["groups"][path[1]]["atoms"][path[2]]
    except (KeyError, IndexError, TypeError):
        return None
    frozen_fields = (
        "kind", "statement", "modality", "temporal_scope", "source_span_ids",
        "source_excerpts", "requires_professional_judgment", "prospective_period",
        "continuing_obligation",
    )
    return path if isinstance(atom, dict) and all(field in atom for field in frozen_fields) else None


def _invalid_observation_policy_paths(
    error: ProtocolControlAgentWireValidationError,
    baseline: Mapping[str, Any],
    candidate_index: int,
) -> tuple[tuple[int, int], ...]:
    """Select only same-candidate atoms whose sole missing field is selection policy."""

    cause = error.__cause__
    if not isinstance(cause, ValidationError):
        return ()
    paths: set[tuple[int, int]] = set()
    for item in cause.errors(include_url=False):
        location = tuple(item["loc"])
        if (
            len(location) < 7
            or location[:4] != (
                "candidate_drafts", candidate_index, "obligation_expression", "groups"
            )
            or not isinstance(location[4], int)
            or location[5] != "atoms"
            or not isinstance(location[6], int)
        ):
            return ()
        group_index, atom_index = location[4], location[6]
        try:
            atom = baseline["candidate_drafts"][candidate_index]["obligation_expression"]["groups"][group_index]["atoms"][atom_index]
            evaluation = atom["evaluation"]
        except (KeyError, IndexError, TypeError):
            return ()
        if not isinstance(evaluation, dict) or evaluation.get("observation_policy") is not None:
            return ()
        paths.add((group_index, atom_index))
    return tuple(sorted(paths)) if len(paths) > 1 else ()


def _merge_observation_policy_repair(
    raw_text: str,
    baseline: Mapping[str, Any],
    candidate_index: int,
    paths: tuple[tuple[int, int], ...],
) -> ProtocolControlAgentWire:
    """Only replace selected observation policies; retain all other model fields."""

    try:
        repair = _ObservationPolicyRepair.model_validate_json(raw_text)
        returned = [(item.group_index, item.atom_index) for item in repair.items]
        if sorted(returned) != list(paths):
            raise ValueError("观察采用说明的原子位置与授权范围不一致")
        merged = deepcopy(dict(baseline))
        candidate = merged["candidate_drafts"][candidate_index]
        for item in repair.items:
            atom = candidate["obligation_expression"]["groups"][item.group_index]["atoms"][item.atom_index]
            atom["evaluation"]["observation_policy"] = item.policy.model_dump(mode="json")
        return ProtocolControlAgentWire.model_validate(merged)
    except (ValidationError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProtocolControlAgentWireValidationError(
            "OBSERVATION_REPAIR_INVALID",
            _validation_error_summary(exc) if isinstance(exc, ValidationError) else str(exc),
        ) from exc


def _build_observation_policy_repair_prompt(
    baseline: Mapping[str, Any],
    candidate_index: int,
    paths: tuple[tuple[int, int], ...],
    problem: str,
) -> str:
    candidate = baseline["candidate_drafts"][candidate_index]
    atoms = [
        {
            "group_index": group_index,
            "atom_index": atom_index,
            "atom": candidate["obligation_expression"]["groups"][group_index]["atoms"][atom_index],
        }
        for group_index, atom_index in paths
    ]
    return (
        "仅为列出的义务原子补充观察采用说明，不重写义务、阈值、时间、例外或来源。"
        "方案明确规定单次、任一、全部或最近/最早时才选择对应方式；"
        "原文不足时使用 unresolved 并说明范围，不得猜测。"
        "每项的来源只能从相应原子的 source_span_ids 与 source_excerpts 成对选取；"
        "旁边的段落不是本次可引用来源。若原子来源不足以确定采用方式，填 unresolved；"
        "只返回 items 列表，位置须一一对应。\n"
        f"校验问题：{problem[:3000]}\n"
        f"需修原子：{_stable_json(atoms)}\n"
    )


def _invalid_evidence_source_policy_path(
    error: ProtocolControlAgentWireValidationError,
    baseline: Mapping[str, Any],
    candidate_index: int,
) -> tuple[int, int] | None:
    cause = error.__cause__
    if not isinstance(cause, ValidationError):
        return None
    paths: set[tuple[int, int]] = set()
    for item in cause.errors(include_url=False):
        location = tuple(item["loc"])
        if (
            len(location) < 4
            or location[:2] != ("candidate_drafts", candidate_index)
            or location[2] != "minimum_evidence"
            or not isinstance(location[3], int)
            or location[4:5] != ("source_policy",)
        ):
            return None
        paths.add((candidate_index, location[3]))
    if len(paths) != 1:
        return None
    path = next(iter(paths))
    try:
        evidence = baseline["candidate_drafts"][path[0]]["minimum_evidence"][path[1]]
    except (KeyError, IndexError, TypeError):
        return None
    return path if isinstance(evidence, dict) else None


def _build_evidence_source_policy_repair_prompt(
    batch: ProtocolControlDispositionBatch,
    baseline: Mapping[str, Any],
    path: tuple[int, int],
    problem: str,
) -> str:
    candidate = baseline["candidate_drafts"][path[0]]
    evidence = candidate["minimum_evidence"][path[1]]
    source_texts = _candidate_source_texts(batch, candidate["source_structure_unit_ids"])
    return (
        "仅修订这一项最低证据的资料来源要求 source_policy，不改写证据、义务、期别、时间或其他候选。"
        "source_span_ids 与 source_excerpts 必须成对，摘录必须是相应冻结原文中的连续文字；"
        "原文未明确是否要求同期客观原件或允许筛选病历转述时填 null，未明确结果有效期时"
        "填 not_specified，不得补造期限。只返回 policy。\n"
        f"校验问题：{problem[:2000]}\n"
        f"需修证据：{_stable_json(evidence)}\n"
        f"授权原文：{_stable_json(source_texts)}\n"
    )


def _merge_evidence_source_policy_repair(
    raw_text: str,
    baseline: Mapping[str, Any],
    path: tuple[int, int],
    batch: ProtocolControlDispositionBatch,
) -> ProtocolControlAgentWire:
    try:
        repair = _EvidenceSourcePolicyRepair.model_validate_json(raw_text)
        merged = deepcopy(dict(baseline))
        candidate = merged["candidate_drafts"][path[0]]
        source_texts = _candidate_source_texts(batch, candidate["source_structure_unit_ids"])
        for span_id, excerpt in zip(
            repair.policy.source_span_ids, repair.policy.source_excerpts, strict=True
        ):
            if not any(excerpt in text for text in source_texts.get(span_id, ())):
                raise ValueError("资料来源要求的摘录不属于授权原文")
        candidate["minimum_evidence"][path[1]]["source_policy"] = repair.policy.model_dump(mode="json")
        return ProtocolControlAgentWire.model_validate(merged)
    except (ValidationError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProtocolControlAgentWireValidationError(
            "EVIDENCE_SOURCE_REPAIR_INVALID",
            _validation_error_summary(exc) if isinstance(exc, ValidationError) else str(exc),
        ) from exc


def _invalid_time_operand_paths(
    error: ProtocolControlAgentWireValidationError,
    baseline: Mapping[str, Any],
    candidate_index: int,
) -> tuple[tuple[int, int], ...]:
    cause = error.__cause__
    if not isinstance(cause, ValidationError):
        return ()
    paths: set[tuple[int, int]] = set()
    for item in cause.errors(include_url=False):
        location = tuple(item["loc"])
        if (
            item["type"] != "control_time_operand_missing"
            or len(location) != 7
            or location[:4] != (
                "candidate_drafts", candidate_index, "obligation_expression", "groups"
            )
            or not isinstance(location[4], int)
            or location[5] != "atoms"
            or not isinstance(location[6], int)
        ):
            return ()
        paths.add((location[4], location[6]))
    for group_index, atom_index in paths:
        try:
            atom = baseline["candidate_drafts"][candidate_index]["obligation_expression"]["groups"][group_index]["atoms"][atom_index]
            if atom["time_constraint"] is None or atom["evaluation"].get("time_operand_attribute") is not None:
                return ()
        except (KeyError, IndexError, TypeError):
            return ()
    return tuple(sorted(paths))


def _build_time_operand_repair_prompt(
    baseline: Mapping[str, Any],
    candidate_index: int,
    paths: tuple[tuple[int, int], ...],
) -> str:
    candidate = baseline["candidate_drafts"][candidate_index]
    atoms = [
        {
            "group_index": group_index,
            "atom_index": atom_index,
            "atom": candidate["obligation_expression"]["groups"][group_index]["atoms"][atom_index],
        }
        for group_index, atom_index in paths
    ]
    return (
        "只为列出的义务原子选择时间核对使用的日期属性：事件所属期间用 date_range，"
        "记录形成或检查发生的单日日期用 record_time。"
        "不得更改原文、时间锚点、期限、义务和其他字段；若不能从原子来源判断，不得猜测。"
        "仅返回 items，位置须一一对应。\n"
        f"需修原子：{_stable_json(atoms)}\n"
    )


def _merge_time_operand_repair(
    raw_text: str,
    baseline: Mapping[str, Any],
    candidate_index: int,
    paths: tuple[tuple[int, int], ...],
) -> ProtocolControlAgentWire:
    try:
        repair = _TimeOperandRepair.model_validate_json(raw_text)
        if sorted((item.group_index, item.atom_index) for item in repair.items) != list(paths):
            raise ValueError("时间日期属性的原子位置与授权范围不一致")
        if any(item.attribute == "unresolved" for item in repair.items):
            raise ProtocolControlAgentWireValidationError(
                "TIME_OPERAND_UNRESOLVED", "原文不足以确定核对日期属性，保留未核实"
            )
        merged = deepcopy(dict(baseline))
        candidate = merged["candidate_drafts"][candidate_index]
        for item in repair.items:
            atom = candidate["obligation_expression"]["groups"][item.group_index]["atoms"][item.atom_index]
            atom["evaluation"]["time_operand_attribute"] = item.attribute
        return ProtocolControlAgentWire.model_validate(merged)
    except ProtocolControlAgentWireValidationError:
        raise
    except (ValidationError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProtocolControlAgentWireValidationError(
            "TIME_OPERAND_REPAIR_INVALID",
            _validation_error_summary(exc) if isinstance(exc, ValidationError) else str(exc),
        ) from exc


def _merge_obligation_atom_repair(
    raw_text: str, baseline: Mapping[str, Any], path: tuple[int, int, int]
) -> ProtocolControlAgentWire:
    """Splice a checked atom into the original batch; all siblings remain byte-identical."""

    try:
        payload = json.loads(raw_text)
        if not isinstance(payload, dict) or set(payload) != {"atom"}:
            raise ValueError("义务原子修订只接受 atom")
        if _find_forbidden_provider_key(payload) is not None:
            raise ValueError("义务原子修订不得填写系统身份")
        candidate_index, group_index, atom_index = path
        merged = deepcopy(dict(baseline))
        original = merged["candidate_drafts"][candidate_index]["obligation_expression"]["groups"][group_index]["atoms"][atom_index]
        replacement = ProtocolControlAgentWireObligationAtom.model_validate(payload["atom"])
        replacement_json = replacement.model_dump(mode="json")
        for field in (
            "kind", "statement", "modality", "temporal_scope",
            "source_span_ids", "source_excerpts", "requires_professional_judgment",
            "prospective_period", "continuing_obligation",
        ):
            if field not in original or replacement_json[field] != original[field]:
                raise ValueError(f"义务原子修订不得改变 {field}")
        merged["candidate_drafts"][candidate_index]["obligation_expression"]["groups"][group_index]["atoms"][atom_index] = replacement_json
        return ProtocolControlAgentWire.model_validate(merged)
    except (json.JSONDecodeError, ValidationError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProtocolControlAgentWireValidationError(
            "ATOM_REPAIR_INVALID",
            _validation_error_summary(exc) if isinstance(exc, ValidationError) else str(exc),
        ) from exc


def _build_obligation_atom_repair_prompt(
    batch: ProtocolControlDispositionBatch,
    baseline: Mapping[str, Any],
    path: tuple[int, int, int],
    problem: str,
) -> str:
    candidate_index, group_index, atom_index = path
    candidate = baseline["candidate_drafts"][candidate_index]
    atom = candidate["obligation_expression"]["groups"][group_index]["atoms"][atom_index]
    owned_ids = set(candidate["source_structure_unit_ids"])
    sources = [
        {
            "structure_unit_id": unit.structure_unit_id,
            "heading_path": unit.heading_path,
            "excerpt": unit.excerpt,
        }
        for unit in batch.owned_units
        if unit.structure_unit_id in owned_ids
    ]
    return (
        "仅修订一个已有义务原子的结构，不新增临床含义。"
        "原句、义务类型、强度、来源定位、后续义务和研究者判断属性必须原样保留；"
        "只能根据冻结原文修订求值和时间字段。若原文无法支持修订，不得猜测。"
        "只返回含 atom 的 JSON，其他候选、原子和处置由系统原样保留。\n"
        f"问题：{problem}\n"
        f"原子位置：候选{candidate_index}／义务组{group_index}／原子{atom_index}\n"
        f"原子原稿：{_stable_json(atom)}\n"
        f"冻结来源：{_stable_json(sources)}"
    )


def _merge_candidate_repairs(
    raw_text: str,
    baseline: ProtocolControlAgentWire | Mapping[str, Any],
    indexes: Sequence[int],
) -> ProtocolControlAgentWire:
    try:
        payload = json.loads(raw_text)
        if not isinstance(payload, dict) or set(payload) != {"candidate_drafts"}:
            raise ValueError("多候选修订只接受 candidate_drafts")
        drafts = payload["candidate_drafts"]
        if not isinstance(drafts, list) or len(drafts) != len(indexes):
            raise ValueError("修订候选数量与授权位置不一致")
        if _find_forbidden_provider_key(payload) is not None:
            raise ValueError("修订候选不得填写系统身份")
        merged = (
            baseline.model_dump(mode="json")
            if isinstance(baseline, ProtocolControlAgentWire)
            else deepcopy(dict(baseline))
        )
        if list(indexes) != sorted(set(indexes)) or any(
            index < 0 or index >= len(merged["candidate_drafts"]) for index in indexes
        ):
            raise ValueError("修订候选位置不属于原始批次")
        for index, draft in zip(indexes, drafts, strict=True):
            candidate = ProtocolControlAgentWireCandidate.model_validate(draft)
            if not isinstance(baseline, ProtocolControlAgentWire):
                original = merged["candidate_drafts"][index]
                if any(
                    candidate.model_dump(mode="json")[field] != original.get(field)
                    for field in ("source_structure_unit_ids", "source_span_ids")
                ):
                    raise ValueError("多候选修订不得调换候选或改变原始来源范围")
            merged["candidate_drafts"][index] = candidate.model_dump(mode="json")
        return ProtocolControlAgentWire.model_validate(merged)
    except (json.JSONDecodeError, ValidationError, ValueError, KeyError) as exc:
        raise ProtocolControlAgentWireValidationError(
            "CANDIDATE_REPAIR_INVALID",
            _validation_error_summary(exc) if isinstance(exc, ValidationError) else str(exc),
        ) from exc


class ProtocolControlAgentRunner:
    """Bounded same-session parser/repair loop for one planned batch.

    Repair budget contract for serial multi-class repairs (串行修订类预算合同):

    1. The total number of schema repair rounds is strictly bounded by
       ``max_schema_repairs`` (default ``DEFAULT_MAX_SCHEMA_REPAIRS`` = 2).
       The budget is shared across structure and publication errors. Once a
       parsed output passes those checks, a source-target review may authorize
       one separate, source-scoped insertion. It cannot grant another schema
       repair or repeat an unsuccessful insertion.
    2. The loop always terminates (no infinite loop): the ``repairs``
       counter increases monotonically against the strict bound, and an
       identical invalid result (raw text sha256 + error code + message)
       observed for the second time triggers the ``no_progress`` early
       stop before the remaining budget is consumed.
    3. Transport calls are bounded: one initial call, at most
       ``max_transport_retries`` (default ``DEFAULT_MAX_TRANSPORT_RETRIES``
       = 1) retries, one call per schema repair round, and at most one
       source-scoped insertion call.
    4. Invariant output: given the same transport response sequence, every
       attempt (including its ``error_classes`` accounting), the status and
       the final output are fully deterministic; rerunning the same
       sequence reproduces the identical result field for field.
    """

    def __init__(
        self,
        *,
        max_transport_retries: int = DEFAULT_MAX_TRANSPORT_RETRIES,
        max_schema_repairs: int = DEFAULT_MAX_SCHEMA_REPAIRS,
    ) -> None:
        if max_transport_retries < 0 or max_schema_repairs < 0:
            raise ValueError("重试上限必须为非负整数")
        self._max_transport_retries = max_transport_retries
        self._max_schema_repairs = max_schema_repairs

    def run(
        self,
        batch: ProtocolControlDispositionBatch,
        transport: ProtocolControlAgentTransport,
        *,
        prompt_template: str = DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE,
        accepted_batch_ids: Sequence[str] = (),
        output_validator: ProtocolControlAgentOutputValidator | None = None,
    ) -> ProtocolControlAgentRunResult:
        if batch.batch_id in set(accepted_batch_ids):
            raise ValueError(f"已接受批次不得被同会话修复替换：{batch.batch_id}")

        attempts: list[ProtocolControlAgentAttempt] = []
        session_id: str | None = None
        raw_text: str | None = None
        source_interpretation: SourceInterpretation | None = None
        source_reader = getattr(transport, "start_source_interpretation", None)
        if callable(source_reader):
            source_response: ProtocolControlAgentResponse | None = None
            try:
                source_response = source_reader(
                    prompt=build_source_interpretation_prompt(batch)
                )
                source_interpretation = SourceInterpretation.model_validate_json(
                    source_response.text
                )
                validate_source_interpretation(batch, source_interpretation)
            except Exception as exc:  # noqa: BLE001 - product transport/schema boundary
                source_session_id = (
                    getattr(exc, "session_id", None)
                    or (source_response.session_id if source_response is not None else None)
                    or "source-interpretation-invalid"
                )
                return ProtocolControlAgentRunResult(
                    status="需要核对",
                    batch_id=batch.batch_id,
                    session_id=source_session_id,
                    attempts=[ProtocolControlAgentAttempt(
                        attempt=1,
                        session_id=source_session_id,
                        raw_output_sha256=_sha256(
                            source_response.text if source_response is not None else str(exc)
                        ),
                        raw_output_chars=(
                            len(source_response.text) if source_response is not None else None
                        ),
                        outcome=(
                            "transport_failed" if source_response is None
                            else "schema_invalid"
                        ),
                        issues=[f"有源陈述核对未通过：{str(exc)[:1800]}"],
                    )],
                )
        prompt = build_protocol_control_agent_prompt(
            batch,
            prompt_template=prompt_template,
            include_schema=getattr(transport, "response_format_mode", None) != "json_schema",
            source_interpretation=source_interpretation,
        )
        transport_failures = 0
        while True:
            try:
                response = (
                    transport.start(prompt=prompt)
                    if session_id is None
                    else transport.continue_session(session_id=session_id, prompt=prompt)
                )
                if session_id is not None and response.session_id != session_id:
                    raise RuntimeError("同会话修复不得更换 session_id")
                session_id = response.session_id
                raw_text = response.text
                break
            except Exception as exc:  # noqa: BLE001 - transport boundary
                attempt_id = len(attempts) + 1
                sid = session_id or f"transport-failed-{attempt_id}"
                attempts.append(
                    ProtocolControlAgentAttempt(
                        attempt=attempt_id,
                        session_id=sid,
                        raw_output_sha256=_sha256(str(exc)),
                        outcome="transport_failed",
                        issues=[str(exc)[:2000]],
                    )
                )
                transport_failures += 1
                if getattr(exc, "uncertain_completion", False) or (
                    transport_failures > self._max_transport_retries
                ):
                    return ProtocolControlAgentRunResult(
                        status="需要核对",
                        batch_id=batch.batch_id,
                        session_id=sid,
                        attempts=attempts,
                        source_interpretation=source_interpretation,
                    )

        assert session_id is not None and raw_text is not None
        repairs = 0
        source_insert_repairs = 0
        invalid_fingerprint_counts: dict[tuple[str, str, str], int] = {}
        repair_baseline: ProtocolControlBatchDispositionHydrated | None = None
        repair_baseline_wire: ProtocolControlAgentWire | None = None
        repair_baseline_raw: dict[str, Any] | None = None
        candidate_repair_indexes: tuple[int, ...] = ()
        mutable_structure_unit_ids: set[str] = set()
        mutable_candidate_source_keys: set[tuple[str, ...]] = set()
        mutable_candidate_indexes: set[int] = set()
        mutable_candidate_source_union: set[str] = set()
        mutable_obligation_source_span_ids: set[str] = set()
        allow_candidate_repartition = False
        allow_source_closure_rewrite = False
        allow_post_enrollment_reclassification = False
        allow_source_insert = False
        source_insert_candidate_only = False
        latest_source_target_review: SourceTargetReview | None = None
        validated_target_coverage: dict[int, SourceStatementCoverage] = {}
        latest_source_statement_coverage: list[SourceStatementCoverage] = []
        candidate_repair_index: int | None = None
        post_treatment_repair_index: int | None = None
        atom_repair_path: tuple[int, int, int] | None = None
        time_operand_repair_paths: tuple[tuple[int, int], ...] = ()
        time_operand_repair_candidate: int | None = None
        observation_repair_paths: tuple[tuple[int, int], ...] = ()
        observation_repair_candidate: int | None = None
        evidence_source_repair_path: tuple[int, int] | None = None
        while True:
            wire: ProtocolControlAgentWire | None = None
            output: ProtocolControlBatchDispositionHydrated | None = None
            bounded_restore_applied = False
            invalid_outcome: Literal["schema_invalid", "publication_invalid"] = (
                "schema_invalid"
            )
            try:
                wire = (
                    _merge_post_treatment_scope_repair(
                        raw_text, repair_baseline_wire, post_treatment_repair_index, batch
                    )
                    if post_treatment_repair_index is not None and repair_baseline_wire is not None
                    else
                    _merge_time_operand_repair(
                        raw_text, repair_baseline_raw, time_operand_repair_candidate,
                        time_operand_repair_paths,
                    )
                    if time_operand_repair_candidate is not None and repair_baseline_raw is not None
                    else _merge_evidence_source_policy_repair(
                        raw_text, repair_baseline_raw, evidence_source_repair_path, batch
                    )
                    if evidence_source_repair_path is not None and repair_baseline_raw is not None
                    else _merge_observation_policy_repair(
                        raw_text,
                        repair_baseline_raw,
                        observation_repair_candidate,
                        observation_repair_paths,
                    )
                    if observation_repair_candidate is not None and repair_baseline_raw is not None
                    else _merge_obligation_atom_repair(
                        raw_text, repair_baseline_raw, atom_repair_path
                    )
                    if atom_repair_path is not None and repair_baseline_raw is not None
                    else
                    _merge_source_candidate_insert(
                        raw_text,
                        repair_baseline_wire,
                        authorized_unit_ids=mutable_structure_unit_ids,
                    )
                    if source_insert_candidate_only and repair_baseline_wire is not None
                    else
                    _merge_candidate_repairs(
                        raw_text,
                        repair_baseline_wire or repair_baseline_raw,
                        candidate_repair_indexes,
                    )
                    if candidate_repair_indexes
                    and (repair_baseline_wire is not None or repair_baseline_raw is not None)
                    else
                    _merge_candidate_repair(
                        raw_text,
                        repair_baseline_wire or repair_baseline_raw,
                        candidate_repair_index,
                    )
                    if candidate_repair_index is not None
                    and (repair_baseline_wire is not None or repair_baseline_raw is not None)
                    else _parse_repartition_with_checked_time(raw_text, repair_baseline_wire)
                    if allow_post_enrollment_reclassification and repair_baseline_wire is not None
                    else parse_protocol_control_agent_wire(raw_text)
                )
                repair_baseline_raw = None
                post_treatment_repair_index = None
                time_operand_repair_paths = ()
                time_operand_repair_candidate = None
                atom_repair_path = None
                observation_repair_paths = ()
                observation_repair_candidate = None
                evidence_source_repair_path = None
                if repair_baseline_wire is not None:
                    wire, bounded_restore_applied = _restore_bounded_wire_repair(
                        repair_baseline_wire,
                        wire,
                        mutable_structure_unit_ids=mutable_structure_unit_ids,
                        mutable_candidate_source_keys=mutable_candidate_source_keys,
                        mutable_candidate_indexes=mutable_candidate_indexes,
                        mutable_candidate_source_union=mutable_candidate_source_union,
                        mutable_obligation_source_span_ids=(
                            mutable_obligation_source_span_ids
                        ),
                        allow_candidate_repartition=allow_candidate_repartition,
                        allow_source_closure_rewrite=allow_source_closure_rewrite,
                        allow_post_enrollment_reclassification=allow_post_enrollment_reclassification,
                        allow_source_insert=allow_source_insert,
                    )
                output = hydrate_protocol_control_agent_output(wire, batch)
                if output_validator is not None:
                    invalid_outcome = "publication_invalid"
                    if repair_baseline is not None:
                        _validate_bounded_output_repair(
                            repair_baseline,
                            output,
                            mutable_structure_unit_ids=mutable_structure_unit_ids,
                            mutable_candidate_source_keys=mutable_candidate_source_keys,
                            mutable_candidate_source_union=mutable_candidate_source_union,
                            allow_candidate_repartition=allow_candidate_repartition,
                            allow_source_closure_rewrite=allow_source_closure_rewrite,
                        )
                    try:
                        output_validator(output)
                    except ProtocolControlAgentWireValidationError:
                        raise
                    except Exception as exc:  # noqa: BLE001 - validation boundary
                        raise ProtocolControlAgentWireValidationError(
                            "POST_HYDRATION_INVALID",
                            str(exc),
                        ) from exc
                attempts.append(
                    ProtocolControlAgentAttempt(
                        attempt=len(attempts) + 1,
                        session_id=session_id,
                        raw_output_sha256=_sha256(raw_text),
                        raw_output_chars=len(raw_text),
                        outcome="parsed",
                        output=output,
                        issues=(
                            ["已由系统原样保留定向修订范围外的上一轮内容"]
                            if bounded_restore_applied
                            else []
                        ),
                    )
                )
                coverage = (
                    source_statement_coverage(batch, source_interpretation, wire)
                    if source_interpretation is not None and wire is not None else []
                )
                latest_source_statement_coverage = coverage
                target_review: SourceTargetReview | None = None
                reviewer = getattr(transport, "start_source_target_review", None)
                review_indexes = (
                    target_review_indexes(source_interpretation, coverage)
                    if source_interpretation is not None else []
                )
                if source_interpretation is not None and review_indexes:
                    review_response: ProtocolControlAgentResponse | None = None
                    unresolved_indexes: list[int] = []
                    try:
                        previous_covered = {
                            item.statement_index: item
                            for item in (latest_source_target_review.items
                                         if latest_source_target_review is not None else [])
                            if item.decision in {"covered_by_official", "covered_by_procedure"}
                        }
                        current_coverage = {
                            entry.statement_index: entry for entry in coverage
                        }
                        def target_inputs(entry: SourceStatementCoverage) -> tuple[object, ...]:
                            return (
                                entry.status,
                                entry.disposition,
                                entry.linked_official_code,
                                tuple(entry.linked_procedure_target_ids),
                            )

                        reusable = [
                            previous_covered[index]
                            for index in review_indexes
                            if index in previous_covered
                            and index in validated_target_coverage
                            and target_inputs(validated_target_coverage[index])
                            == target_inputs(current_coverage[index])
                        ]
                        reusable_indexes = {item.statement_index for item in reusable}
                        pending_coverage = [
                            entry for entry in coverage
                            if entry.statement_index not in reusable_indexes
                        ]
                        pending_items = []
                        if target_review_indexes(source_interpretation, pending_coverage):
                            if not callable(reviewer):
                                raise RuntimeError("逐项来源核对服务不可用，不能跳过未闭合陈述")
                            review_response = reviewer(prompt=build_source_target_review_prompt(
                                batch, source_interpretation, pending_coverage
                            ))
                            pending_review = SourceTargetReview.model_validate_json(review_response.text)
                            validate_source_target_review(
                                batch, source_interpretation, pending_coverage, pending_review
                            )
                            pending_items = pending_review.items
                        target_review = SourceTargetReview(
                            version=SOURCE_TARGET_REVIEW_VERSION,
                            items=sorted([*reusable, *pending_items], key=lambda item: item.statement_index),
                        )
                        validate_source_target_review(
                            batch, source_interpretation, coverage, target_review
                        )
                        latest_source_target_review = target_review
                        validated_target_coverage = {
                            entry.statement_index: entry for entry in coverage
                            if entry.statement_index in review_indexes
                        }
                        unresolved_indexes = [
                            item.statement_index for item in target_review.items
                            if item.decision == "unresolved"
                        ]
                        if unresolved_indexes:
                            raise ValueError(
                                "来源陈述尚未逐项闭合：" + ",".join(map(str, unresolved_indexes))
                            )
                        additional = [
                            item for item in target_review.items
                            if item.decision == "additional_requirement"
                        ]
                        if additional:
                            if output_validator is None or source_insert_repairs >= 1:
                                raise ValueError("增量要求需要受限补入，当前修订能力或次数不足")
                            item = additional[0]
                            statement = source_interpretation.statements[item.statement_index]
                            unit = next(unit for unit in batch.owned_units
                                        if unit.structure_unit_id == statement.structure_unit_id)
                            attempts.append(ProtocolControlAgentAttempt(
                                attempt=len(attempts) + 1,
                                session_id=review_response.session_id,
                                raw_output_sha256=_sha256(review_response.text),
                                raw_output_chars=len(review_response.text),
                                raw_output_text=review_response.text,
                                outcome="publication_invalid",
                                output=output,
                                issues=["逐项核对发现原文支持的增量要求，进入来源限定补入"],
                                error_classes=["SOURCE_TARGET_ADDITIONAL_REQUIREMENT"],
                            ))
                            raise ProtocolControlAgentWireValidationError(
                                "SOURCE_TARGET_ADDITIONAL_REQUIREMENT",
                                f"第{item.statement_index}条原文要求未由已有目标完整覆盖："
                                f"{statement.quoted_text}；差异：{'；'.join(item.unresolved_aspects)}",
                                structure_unit_ids=[unit.structure_unit_id],
                                obligation_source_span_ids=list(unit.source_span_ids),
                                allow_source_insert=True,
                            )
                    except ProtocolControlAgentWireValidationError:
                        raise
                    except Exception as exc:  # noqa: BLE001 - source/target acceptance boundary
                        review_session = (
                            getattr(exc, "session_id", None)
                            or (review_response.session_id if review_response else None)
                            or "source-target-review-invalid"
                        )
                        attempts.append(ProtocolControlAgentAttempt(
                            attempt=len(attempts) + 1,
                            session_id=review_session,
                            raw_output_sha256=_sha256(
                                review_response.text if review_response else str(exc)
                            ),
                            raw_output_chars=(
                                len(review_response.text) if review_response else None
                            ),
                            raw_output_text=(review_response.text if review_response else None),
                            outcome=("publication_invalid" if review_response else "transport_failed"),
                            output=output,
                            issues=[f"逐项来源与已有目标核对未通过：{str(exc)[:1800]}"],
                            error_classes=[
                                "SOURCE_TARGET_REVIEW_UNRESOLVED"
                                if unresolved_indexes or (
                                    target_review is not None and any(
                                        item.decision == "additional_requirement"
                                        for item in target_review.items
                                    )
                                )
                                else "SOURCE_TARGET_REVIEW_INVALID"
                                if review_response is not None
                                else "SOURCE_TARGET_REVIEW_TRANSPORT_FAILED"
                            ],
                        ))
                        return ProtocolControlAgentRunResult(
                            status="需要核对",
                            batch_id=batch.batch_id,
                            session_id=session_id,
                            attempts=attempts,
                            source_interpretation=source_interpretation,
                            source_statement_coverage=coverage,
                            source_target_review=target_review,
                        )
                return ProtocolControlAgentRunResult(
                    status="已解析",
                    batch_id=batch.batch_id,
                    session_id=session_id,
                    attempts=attempts,
                    final_output=output,
                    source_interpretation=source_interpretation,
                    source_statement_coverage=coverage,
                    source_target_review=target_review,
                )
            except Exception as exc:  # noqa: BLE001 - bounded validation boundary
                previous_atom_repair_path = atom_repair_path
                previous_time_operand_repair_candidate = time_operand_repair_candidate
                previous_observation_repair_candidate = observation_repair_candidate
                previous_evidence_source_repair_path = evidence_source_repair_path
                atom_repair_path = None
                time_operand_repair_paths = ()
                time_operand_repair_candidate = None
                observation_repair_paths = ()
                observation_repair_candidate = None
                evidence_source_repair_path = None
                error = (
                    exc
                    if isinstance(exc, ProtocolControlAgentWireValidationError)
                    else ProtocolControlAgentWireValidationError(
                        "OUTPUT_INVALID",
                        str(exc),
                    )
                )
                candidate_ids = _candidate_ids_from_wire(wire, batch)
                raw_output_sha256 = _sha256(raw_text)
                invalid_fingerprint = (
                    raw_output_sha256,
                    error.code,
                    str(error)[:2000],
                )
                invalid_fingerprint_counts[invalid_fingerprint] = (
                    invalid_fingerprint_counts.get(invalid_fingerprint, 0) + 1
                )
                no_progress = invalid_fingerprint_counts[invalid_fingerprint] >= 2
                repair_scope_unknown = bool(
                    set(error.structure_unit_ids) - set(batch.owned_structure_unit_ids)
                )
                repair_candidate_indexes = set(error.candidate_indexes)
                if previous_atom_repair_path is not None:
                    repair_candidate_indexes.add(previous_atom_repair_path[0])
                if previous_time_operand_repair_candidate is not None:
                    repair_candidate_indexes.add(previous_time_operand_repair_candidate)
                if previous_observation_repair_candidate is not None:
                    repair_candidate_indexes.add(previous_observation_repair_candidate)
                if previous_evidence_source_repair_path is not None:
                    repair_candidate_indexes.add(previous_evidence_source_repair_path[0])
                if wire is None and error.code == "WIRE_SCHEMA_INVALID" and repair_baseline_raw is None:
                    salvage = _invalid_candidate_payload(raw_text)
                    if salvage is not None:
                        repair_baseline_raw, invalid_indexes = salvage
                        repair_candidate_indexes.update(invalid_indexes)
                        if len(invalid_indexes) == 1:
                            atom_repair_path = _invalid_obligation_atom_path(
                                error,
                                repair_baseline_raw,
                                invalid_indexes[0],
                            )
                            if atom_repair_path is None:
                                observation_repair_paths = _invalid_observation_policy_paths(
                                    error, repair_baseline_raw, invalid_indexes[0]
                                )
                                time_operand_repair_paths = _invalid_time_operand_paths(
                                    error, repair_baseline_raw, invalid_indexes[0]
                                )
                                if time_operand_repair_paths:
                                    time_operand_repair_candidate = invalid_indexes[0]
                                elif observation_repair_paths:
                                    observation_repair_candidate = invalid_indexes[0]
                                else:
                                    evidence_source_repair_path = _invalid_evidence_source_policy_path(
                                        error, repair_baseline_raw, invalid_indexes[0]
                                    )
                elif repair_baseline_raw is not None and candidate_repair_index is not None:
                    repair_candidate_indexes.add(candidate_repair_index)
                elif repair_baseline_raw is not None and candidate_repair_indexes:
                    repair_candidate_indexes.update(candidate_repair_indexes)
                if output is not None and output_validator is not None:
                    candidate_source_by_id = {
                        candidate.control_candidate_id: tuple(
                            candidate.frozen_structure_unit_ids
                        )
                        for candidate in output.candidates
                    }
                    candidate_span_ids_by_id = {
                        candidate.control_candidate_id: set(candidate.source_span_ids)
                        for candidate in output.candidates
                    }
                    unknown_candidate_ids = set(error.candidate_ids) - set(
                        candidate_source_by_id
                    )
                    wire_candidate_ids = _candidate_ids_from_wire(wire, batch)
                    candidate_indexes_by_id = {
                        candidate_id: index
                        for index, candidate_id in enumerate(wire_candidate_ids)
                    }
                    unknown_candidate_index_ids = set(error.candidate_ids) - set(
                        candidate_indexes_by_id
                    )
                    repair_candidate_indexes.update(
                        candidate_indexes_by_id[candidate_id]
                        for candidate_id in error.candidate_ids
                        if candidate_id in candidate_indexes_by_id
                    )
                    selected_candidate_span_ids = {
                        span_id
                        for candidate_id in error.candidate_ids
                        for span_id in candidate_span_ids_by_id.get(candidate_id, set())
                    }
                    selected_candidate_source_keys = {
                        candidate_source_by_id[candidate_id]
                        for candidate_id in error.candidate_ids
                        if candidate_id in candidate_source_by_id
                    }
                    closure_candidate_source_keys = set(
                        selected_candidate_source_keys
                    )
                    if (
                        error.allow_candidate_repartition
                        or error.allow_source_closure_rewrite
                    ):
                        all_candidate_source_keys = set(candidate_source_by_id.values())
                        changed = True
                        while changed:
                            changed = False
                            closure_union = {
                                unit_id
                                for key in closure_candidate_source_keys
                                for unit_id in key
                            }
                            for key in all_candidate_source_keys:
                                if (
                                    key not in closure_candidate_source_keys
                                    and set(key) & closure_union
                                ):
                                    closure_candidate_source_keys.add(key)
                                    changed = True
                    closure_candidate_source_union = {
                        unit_id
                        for key in closure_candidate_source_keys
                        for unit_id in key
                    }
                    source_closure_authority = set(error.structure_unit_ids)
                    source_closure_authority_escape = (
                        error.allow_source_closure_rewrite
                        and (
                            not source_closure_authority
                            or not closure_candidate_source_union
                            or not closure_candidate_source_union
                            <= source_closure_authority
                        )
                    )
                    unknown_obligation_spans = set(
                        error.obligation_source_span_ids
                    ) - selected_candidate_span_ids
                    insert_source_spans = {
                        span_id
                        for unit in batch.owned_units
                        if unit.structure_unit_id in error.structure_unit_ids
                        for span_id in unit.source_span_ids
                    }
                    insert_scope_valid = (
                        error.allow_source_insert
                        and not error.candidate_ids
                        and bool(error.structure_unit_ids)
                        and bool(error.obligation_source_span_ids)
                        and set(error.obligation_source_span_ids) <= insert_source_spans
                    )
                    repair_scope_unknown = (
                        repair_scope_unknown
                        or bool(unknown_candidate_ids)
                        or bool(unknown_candidate_index_ids)
                        or (bool(unknown_obligation_spans) and not insert_scope_valid)
                        or bool(
                            error.obligation_source_span_ids
                            and not error.candidate_ids
                            and not insert_scope_valid
                        )
                        or (error.allow_source_insert and not insert_scope_valid)
                        or source_closure_authority_escape
                        or not (error.candidate_ids or error.structure_unit_ids)
                    )
                    if error.code != "REPAIR_SCOPE_ESCAPE" and not repair_scope_unknown:
                        repair_baseline = output
                        repair_baseline_wire = wire
                        if (
                            error.allow_candidate_repartition
                            or error.allow_source_closure_rewrite
                        ):
                            mutable_candidate_source_keys = set(
                                closure_candidate_source_keys
                            )
                            mutable_candidate_source_union = set(
                                closure_candidate_source_union
                            )
                            mutable_candidate_indexes = set()
                        else:
                            mutable_candidate_source_keys = (
                                selected_candidate_source_keys
                            )
                            mutable_candidate_source_union = set()
                            source_key_counts: dict[tuple[str, ...], int] = {}
                            for source_key in candidate_source_by_id.values():
                                source_key_counts[source_key] = (
                                    source_key_counts.get(source_key, 0) + 1
                                )
                            # Source closure is the stable identity when it is
                            # unique. Wire position is needed only for siblings
                            # that genuinely share the same source closure.
                            mutable_candidate_indexes = (
                                set(repair_candidate_indexes)
                                if any(
                                    source_key_counts.get(source_key, 0) > 1
                                    for source_key in selected_candidate_source_keys
                                )
                                else set()
                            )
                        allow_candidate_repartition = (
                            error.allow_candidate_repartition
                        )
                        allow_source_closure_rewrite = (
                            error.allow_source_closure_rewrite
                        )
                        allow_post_enrollment_reclassification = (
                            error.allow_post_enrollment_reclassification
                        )
                        allow_source_insert = error.allow_source_insert
                        mutable_obligation_source_span_ids = set(
                            error.obligation_source_span_ids
                        )
                        mutable_structure_unit_ids = set(error.structure_unit_ids)
                        if (
                            error.allow_candidate_repartition
                            or error.allow_source_closure_rewrite
                        ):
                            mutable_structure_unit_ids.update(
                                mutable_candidate_source_union
                            )
                elif (
                    wire is not None
                    and output is None
                    and len(repair_candidate_indexes) == 1
                    and not repair_scope_unknown
                    and not error.allow_candidate_repartition
                    and not error.allow_source_closure_rewrite
                    and not error.allow_source_insert
                    and len(wire.dispositions) == len(batch.owned_structure_unit_ids)
                    and {item.structure_unit_id for item in wire.dispositions}
                    == set(batch.owned_structure_unit_ids)
                ):
                    index = next(iter(repair_candidate_indexes))
                    if 0 <= index < len(wire.candidate_drafts):
                        candidate_source = set(
                            wire.candidate_drafts[index].source_structure_unit_ids
                        )
                        if candidate_source and set(error.structure_unit_ids) <= candidate_source:
                            repair_baseline_wire = wire
                            mutable_candidate_indexes = {index}
                            mutable_structure_unit_ids = set(error.structure_unit_ids)
                attempts.append(
                    ProtocolControlAgentAttempt(
                        attempt=len(attempts) + 1,
                        session_id=session_id,
                        raw_output_sha256=raw_output_sha256,
                        raw_output_chars=len(raw_text),
                        raw_output_text=raw_text,
                        outcome=invalid_outcome,
                        issues=(
                            [
                                str(error)[:2000],
                                "连续返回相同无效结果，"
                                "本批次停止自动修订并转为需要核对",
                            ]
                            if no_progress
                            else [str(error)[:2000]]
                        ),
                        error_classes=list(_error_class_codes(error)),
                        rejected_structure_unit_ids=list(
                            error.structure_unit_ids or batch.owned_structure_unit_ids
                        ),
                        rejected_candidate_ids=list(error.candidate_ids or candidate_ids),
                    )
                )
                if (
                    no_progress
                    or error.code == "TIME_OPERAND_UNRESOLVED"
                    or repair_scope_unknown
                    or source_insert_repairs >= 1
                    or (not error.allow_source_insert and repairs >= self._max_schema_repairs)
                ):
                    if repair_scope_unknown:
                        attempts[-1].issues.append(
                            "校验问题缺少完整的机器可读修订范围，"
                            "本批次停止自动修订并转为需要核对"
                        )
                    return ProtocolControlAgentRunResult(
                        status="需要核对",
                        batch_id=batch.batch_id,
                        session_id=session_id,
                        attempts=attempts,
                        source_interpretation=source_interpretation,
                        source_statement_coverage=latest_source_statement_coverage,
                        source_target_review=latest_source_target_review,
                    )
                if error.allow_source_insert:
                    source_insert_repairs += 1
                else:
                    repairs += 1
                atom_only = (
                    atom_repair_path is not None
                    and repair_baseline_raw is not None
                    and callable(getattr(transport, "continue_atom", None))
                )
                if not atom_only:
                    atom_repair_path = None
                time_operand_only = (
                    time_operand_repair_candidate is not None
                    and bool(time_operand_repair_paths)
                    and repair_baseline_raw is not None
                    and callable(getattr(transport, "continue_time_operands", None))
                )
                if not time_operand_only:
                    time_operand_repair_candidate = None
                    time_operand_repair_paths = ()
                observation_only = (
                    observation_repair_candidate is not None
                    and bool(observation_repair_paths)
                    and repair_baseline_raw is not None
                    and callable(getattr(transport, "continue_observation_policies", None))
                )
                if not observation_only:
                    observation_repair_candidate = None
                    observation_repair_paths = ()
                evidence_source_only = (
                    evidence_source_repair_path is not None
                    and repair_baseline_raw is not None
                    and callable(getattr(transport, "continue_evidence_source_policy", None))
                )
                if not evidence_source_only:
                    evidence_source_repair_path = None
                candidate_only = (
                    not atom_only and not time_operand_only and not observation_only and not evidence_source_only
                    and (repair_baseline_wire is not None or repair_baseline_raw is not None)
                    and len(repair_candidate_indexes) == 1
                    and not allow_candidate_repartition
                    and not allow_source_closure_rewrite
                    and not allow_source_insert
                    and callable(getattr(transport, "continue_candidate", None))
                )
                candidates_only = (
                    (repair_baseline_wire is not None or repair_baseline_raw is not None)
                    and len(repair_candidate_indexes) > 1
                    and not allow_candidate_repartition
                    and not allow_source_closure_rewrite
                    and not allow_source_insert
                    and callable(getattr(transport, "continue_candidates", None))
                )
                source_insert_candidate_only = (
                    allow_source_insert
                    and repair_baseline_wire is not None
                    and callable(getattr(transport, "continue_candidate", None))
                    and all(
                        item.disposition in {
                            StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
                            StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                        }
                        for item in repair_baseline_wire.dispositions
                        if item.structure_unit_id in mutable_structure_unit_ids
                    )
                )
                candidate_repair_index = (
                    next(iter(repair_candidate_indexes)) if candidate_only else None
                )
                candidate_repair_indexes = (
                    tuple(sorted(repair_candidate_indexes)) if candidates_only else ()
                )
                post_treatment_only = (
                    allow_post_enrollment_reclassification
                    and repair_baseline_wire is not None
                    and len(repair_candidate_indexes) == 1
                    and not any(
                        index not in repair_candidate_indexes
                        and bool(
                            set(candidate.source_structure_unit_ids)
                            & set(repair_baseline_wire.candidate_drafts[
                                next(iter(repair_candidate_indexes))
                            ].source_structure_unit_ids)
                        )
                        for index, candidate in enumerate(repair_baseline_wire.candidate_drafts)
                    )
                    and callable(getattr(transport, "continue_post_treatment_repair", None))
                )
                post_treatment_repair_index = (
                    next(iter(repair_candidate_indexes)) if post_treatment_only else None
                )
                repair_prompt = build_protocol_control_repair_prompt(
                    batch,
                    problem=str(error),
                    structure_unit_ids=(
                        error.structure_unit_ids or batch.owned_structure_unit_ids
                    ),
                    candidate_ids=error.candidate_ids or candidate_ids,
                    candidate_indexes=sorted(repair_candidate_indexes),
                    obligation_source_span_ids=error.obligation_source_span_ids,
                    candidate_only=candidate_only,
                    candidates_only=candidates_only,
                    source_insert=allow_source_insert,
                    source_insert_candidate_only=source_insert_candidate_only,
                    baseline_wire_sha256=(
                        _sha256(_stable_json(repair_baseline_wire.model_dump(mode="json")))
                        if allow_source_insert and repair_baseline_wire is not None
                        else None
                    ),
                )
                if time_operand_only and repair_baseline_raw is not None and time_operand_repair_candidate is not None:
                    repair_prompt = _build_time_operand_repair_prompt(
                        repair_baseline_raw, time_operand_repair_candidate,
                        time_operand_repair_paths,
                    )
                elif atom_only and repair_baseline_raw is not None and atom_repair_path is not None:
                    repair_prompt = _build_obligation_atom_repair_prompt(
                        batch, repair_baseline_raw, atom_repair_path, str(error)
                    )
                elif observation_only and repair_baseline_raw is not None and observation_repair_candidate is not None:
                    repair_prompt = _build_observation_policy_repair_prompt(
                        repair_baseline_raw,
                        observation_repair_candidate,
                        observation_repair_paths,
                        str(error),
                    )
                elif evidence_source_only and repair_baseline_raw is not None and evidence_source_repair_path is not None:
                    repair_prompt = _build_evidence_source_policy_repair_prompt(
                        batch, repair_baseline_raw, evidence_source_repair_path, str(error)
                    )
                elif post_treatment_only and post_treatment_repair_index is not None:
                    repair_prompt = _build_post_treatment_repair_prompt(
                        batch, repair_baseline_wire, post_treatment_repair_index, str(error)
                    )
                try:
                    if post_treatment_only:
                        response = transport.continue_post_treatment_repair(
                            session_id=session_id, prompt=repair_prompt
                        )
                    elif time_operand_only:
                        response = transport.continue_time_operands(
                            session_id=session_id, prompt=repair_prompt
                        )
                    elif atom_only:
                        response = transport.continue_atom(
                            session_id=session_id, prompt=repair_prompt
                        )
                    elif observation_only:
                        response = transport.continue_observation_policies(
                            session_id=session_id, prompt=repair_prompt
                        )
                    elif evidence_source_only:
                        response = transport.continue_evidence_source_policy(
                            session_id=session_id, prompt=repair_prompt
                        )
                    elif candidate_only or source_insert_candidate_only:
                        response = transport.continue_candidate(
                            session_id=session_id, prompt=repair_prompt
                        )
                    elif candidates_only:
                        response = transport.continue_candidates(
                            session_id=session_id, prompt=repair_prompt
                        )
                    else:
                        response = transport.continue_session(
                            session_id=session_id, prompt=repair_prompt
                        )
                    if response.session_id != session_id:
                        raise RuntimeError("同会话修复不得更换 session_id")
                    raw_text = response.text
                except Exception as exc2:  # noqa: BLE001 - transport boundary
                    attempts.append(
                        ProtocolControlAgentAttempt(
                            attempt=len(attempts) + 1,
                            session_id=session_id,
                            raw_output_sha256=_sha256(str(exc2)),
                            outcome="transport_failed",
                            issues=[str(exc2)[:2000]],
                            rejected_structure_unit_ids=list(
                                error.structure_unit_ids or batch.owned_structure_unit_ids
                            ),
                            rejected_candidate_ids=list(error.candidate_ids or candidate_ids),
                        )
                    )
                    return ProtocolControlAgentRunResult(
                        status="需要核对",
                        batch_id=batch.batch_id,
                        session_id=session_id,
                        attempts=attempts,
                        source_interpretation=source_interpretation,
                        source_statement_coverage=latest_source_statement_coverage,
                        source_target_review=latest_source_target_review,
                    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
