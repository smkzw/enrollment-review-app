"""Receipt-verified qualification selections for frozen calculation (design §17.1.1).

Completed dual-lane qualification is never itself clinical adoption. Formal use of
those records as calculation selections requires an explicit version-bound
authorization from the owning service. Dual agreement of rejected or unresolved
judgments never becomes usable fact truth.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_serializer, model_validator

from app.domain.publication import canonical_hash

from .binding_qualification import CandidateFamily, BINDING_QUALIFICATION_PROMPT_VERSION
from .common import ContractModel
from .observation_selection import OrderedObservationAudit

_SHA256 = r"^[0-9a-f]{64}$"

QUALIFIED_BINDING_SELECTION_VERSION = "qualified-binding-selection/v5"
QUALIFICATION_ADOPTION_AUTHORIZATION_VERSION = "qualification-adoption-authorization/v5"
QUALIFIED_BINDING_CONSUMER_ALGORITHM = "qualified-binding-selection-consumer/v31"


class JudgmentContentAdoption(ContractModel):
    job_id: str = Field(min_length=1)
    summary_logical_sha256: str = Field(pattern=_SHA256)
    summary_artifact_sha256: str = Field(pattern=_SHA256)
    evaluation_sha256: str = Field(pattern=_SHA256)


class PropositionEvidenceAdoption(JudgmentContentAdoption):
    """Same immutable evidence-reference shape, a separately evaluated purpose."""


class ObservationRelationAdoption(JudgmentContentAdoption):
    """Source correspondence only; not permission to replace an observation."""


class FrequencyEvidenceAdoption(JudgmentContentAdoption):
    """Evaluated original frequency statements, not an enrollment decision."""


class QualificationAdoptionAuthorization(ContractModel):
    """Owning-service gate for formal calculation use; never auto-discovered."""

    version: Literal["qualification-adoption-authorization/v1", "qualification-adoption-authorization/v2", "qualification-adoption-authorization/v3", "qualification-adoption-authorization/v4", "qualification-adoption-authorization/v5"] = (
        QUALIFICATION_ADOPTION_AUTHORIZATION_VERSION
    )
    authorization_id: str = Field(min_length=1)
    authorizing_service: str = Field(min_length=1)
    qualification_job_id: str = Field(min_length=1)
    qualification_job_type: Literal["binding_qualification"] = "binding_qualification"
    qualification_contract: Literal["binding-qualification-job/v2"] = (
        "binding-qualification-job/v2"
    )
    qualification_prompt_version: Literal["binding-qualification/v2", "binding-qualification/v3", "binding-qualification/v4", "binding-qualification/v5"] = (
        BINDING_QUALIFICATION_PROMPT_VERSION
    )
    qualification_summary_version: Literal["binding-qualification-summary/v2"] = (
        "binding-qualification-summary/v2"
    )
    consumer_algorithm_version: Literal["qualified-binding-selection-consumer/v1", "qualified-binding-selection-consumer/v2", "qualified-binding-selection-consumer/v3", "qualified-binding-selection-consumer/v4", "qualified-binding-selection-consumer/v5", "qualified-binding-selection-consumer/v6", "qualified-binding-selection-consumer/v7", "qualified-binding-selection-consumer/v8", "qualified-binding-selection-consumer/v9", "qualified-binding-selection-consumer/v10", "qualified-binding-selection-consumer/v11", "qualified-binding-selection-consumer/v12", "qualified-binding-selection-consumer/v13", "qualified-binding-selection-consumer/v14", "qualified-binding-selection-consumer/v15", "qualified-binding-selection-consumer/v16", "qualified-binding-selection-consumer/v17", "qualified-binding-selection-consumer/v18", "qualified-binding-selection-consumer/v19", "qualified-binding-selection-consumer/v20", "qualified-binding-selection-consumer/v21", "qualified-binding-selection-consumer/v22", "qualified-binding-selection-consumer/v23", "qualified-binding-selection-consumer/v24", "qualified-binding-selection-consumer/v25", "qualified-binding-selection-consumer/v26", "qualified-binding-selection-consumer/v27", "qualified-binding-selection-consumer/v28", "qualified-binding-selection-consumer/v29", "qualified-binding-selection-consumer/v30", "qualified-binding-selection-consumer/v31"] = (
        QUALIFIED_BINDING_CONSUMER_ALGORITHM
    )
    candidate_family: CandidateFamily
    frozen_input_sha256: str = Field(pattern=_SHA256)
    comparison_sha256: str = Field(pattern=_SHA256)
    summary_logical_sha256: str = Field(pattern=_SHA256)
    summary_artifact_sha256: str = Field(pattern=_SHA256)
    route_identities: dict[str, dict] = Field(min_length=2)
    approved_evaluation_evidence_sha256: str = Field(pattern=_SHA256)
    judgment_content: JudgmentContentAdoption | None = None
    proposition_evidence: PropositionEvidenceAdoption | None = None
    observation_relation: ObservationRelationAdoption | None = None
    frequency_evidence: FrequencyEvidenceAdoption | None = None

    @model_serializer(mode="wrap")
    def serialize_proposition_evidence(self, handler):
        value = handler(self)
        if self.frequency_evidence is None:
            value.pop("frequency_evidence", None)
        if self.observation_relation is None:
            value.pop("observation_relation", None)
        if self.version not in {"qualification-adoption-authorization/v4", "qualification-adoption-authorization/v5"}:
            value.pop("proposition_evidence", None)
        return value

    @model_validator(mode="after")
    def validate_authorization(self) -> "QualificationAdoptionAuthorization":
        if self.frequency_evidence is not None and (
                self.consumer_algorithm_version != QUALIFIED_BINDING_CONSUMER_ALGORITHM
                or self.version != QUALIFICATION_ADOPTION_AUTHORIZATION_VERSION):
            raise ValueError("频次依据必须绑定当前采用方法，不能补写历史授权")
        if self.observation_relation is not None and (
                self.consumer_algorithm_version not in {"qualified-binding-selection-consumer/v17", "qualified-binding-selection-consumer/v18", "qualified-binding-selection-consumer/v19", "qualified-binding-selection-consumer/v20", "qualified-binding-selection-consumer/v21", "qualified-binding-selection-consumer/v22", "qualified-binding-selection-consumer/v23", "qualified-binding-selection-consumer/v24", "qualified-binding-selection-consumer/v25", "qualified-binding-selection-consumer/v26", "qualified-binding-selection-consumer/v27", "qualified-binding-selection-consumer/v28", QUALIFIED_BINDING_CONSUMER_ALGORITHM}
                or self.version != QUALIFICATION_ADOPTION_AUTHORIZATION_VERSION):
            raise ValueError("历史授权不能补入本次复查对应依据")
        if self.proposition_evidence is not None and (
            self.version not in {"qualification-adoption-authorization/v4", "qualification-adoption-authorization/v5"}
            or (self.version == "qualification-adoption-authorization/v4" and self.candidate_family != "control")
        ):
            raise ValueError("原文含义采用须绑定支持本类条件的授权版本")
        if self.judgment_content is not None and (
            self.version == "qualification-adoption-authorization/v1"
            or (self.version == "qualification-adoption-authorization/v2" and self.candidate_family != "predicate")
        ):
            raise ValueError("书面判断采用须使用支持当前要求类型的授权版本")
        if set(self.route_identities) != {"main-A", "main-B"}:
            raise ValueError("采信授权必须绑定 main-A 与 main-B 路由身份")
        for lane, identity in self.route_identities.items():
            if not isinstance(identity, dict) or not identity:
                raise ValueError(f"{lane} 路由身份不得为空")
            required = {"provider", "base_url", "model", "reasoning_effort", "max_tokens"}
            if not required.issubset(identity):
                raise ValueError(f"{lane} 路由身份缺少模型或额度字段")
        if not self.authorizing_service.strip() or not self.authorization_id.strip():
            raise ValueError("采信授权必须由明确的服务与授权编号签发")
        return self


class QualifiedBindingRejectedPair(ContractModel):
    pair_id: str = Field(pattern=_SHA256)
    identity_sha256: str = Field(pattern=_SHA256)
    fact_id: str = Field(min_length=1)
    reasons: list[str] = Field(min_length=1)


class QualifiedBindingIdentityOutcome(ContractModel):
    identity_field: Literal["predicate_identity_sha256", "atom_identity_sha256"]
    identity_sha256: str = Field(pattern=_SHA256)
    status: Literal["usable", "unresolved"]
    fact_ids: list[str] = Field(default_factory=list)
    usable_pair_ids: list[str] = Field(default_factory=list)
    unresolved_reasons: list[str] = Field(default_factory=list)
    observation_ordering: OrderedObservationAudit | None = None

    @model_serializer(mode="wrap")
    def serialize_ordering(self, handler):
        value = handler(self)
        if self.observation_ordering is None:
            value.pop("observation_ordering", None)
        return value

    @model_validator(mode="after")
    def validate_outcome(self) -> "QualifiedBindingIdentityOutcome":
        if len(self.fact_ids) != len(set(self.fact_ids)):
            raise ValueError("可用事实不得重复")
        if len(self.usable_pair_ids) != len(set(self.usable_pair_ids)):
            raise ValueError("可用配对不得重复")
        if (self.observation_ordering is not None
                and "selected_fact_ids" in self.observation_ordering.model_fields_set
                and set(self.fact_ids) != set(self.observation_ordering.selected_fact_ids)):
            raise ValueError("采用的事实与检查选择依据不一致")
        if self.observation_ordering is not None and set(self.fact_ids).intersection(
            item.fact_id for item in self.observation_ordering.not_selected
        ):
            raise ValueError("未采用的观察记录不得同时作为采用依据")
        if self.status == "usable":
            if not self.fact_ids or self.unresolved_reasons:
                raise ValueError("可用条件必须有事实且不得保留未核实原因")
        else:
            if self.fact_ids:
                raise ValueError("未核实条件不得带入可用事实")
            if not self.unresolved_reasons:
                raise ValueError("未核实条件必须保留具体原因")
        return self


class QualifiedBindingSelectionMaterial(ContractModel):
    """Serializable selection accounting; sealed runtime input wraps this."""

    version: Literal["qualified-binding-selection/v1", "qualified-binding-selection/v2", "qualified-binding-selection/v3", "qualified-binding-selection/v4", "qualified-binding-selection/v5"] = QUALIFIED_BINDING_SELECTION_VERSION
    consumer_algorithm_version: Literal["qualified-binding-selection-consumer/v1", "qualified-binding-selection-consumer/v2", "qualified-binding-selection-consumer/v3", "qualified-binding-selection-consumer/v4", "qualified-binding-selection-consumer/v5", "qualified-binding-selection-consumer/v6", "qualified-binding-selection-consumer/v7", "qualified-binding-selection-consumer/v8", "qualified-binding-selection-consumer/v9", "qualified-binding-selection-consumer/v10", "qualified-binding-selection-consumer/v11", "qualified-binding-selection-consumer/v12", "qualified-binding-selection-consumer/v13", "qualified-binding-selection-consumer/v14", "qualified-binding-selection-consumer/v15", "qualified-binding-selection-consumer/v16", "qualified-binding-selection-consumer/v17", "qualified-binding-selection-consumer/v18", "qualified-binding-selection-consumer/v19", "qualified-binding-selection-consumer/v20", "qualified-binding-selection-consumer/v21", "qualified-binding-selection-consumer/v22", "qualified-binding-selection-consumer/v23", "qualified-binding-selection-consumer/v24", "qualified-binding-selection-consumer/v25", "qualified-binding-selection-consumer/v26", "qualified-binding-selection-consumer/v27", "qualified-binding-selection-consumer/v28", "qualified-binding-selection-consumer/v29", "qualified-binding-selection-consumer/v30", "qualified-binding-selection-consumer/v31"] = (
        QUALIFIED_BINDING_CONSUMER_ALGORITHM
    )
    candidate_family: CandidateFamily
    qualification_job_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorizing_service: str = Field(min_length=1)
    frozen_input_sha256: str = Field(pattern=_SHA256)
    comparison_sha256: str = Field(pattern=_SHA256)
    summary_logical_sha256: str = Field(pattern=_SHA256)
    summary_artifact_sha256: str = Field(pattern=_SHA256)
    approved_evaluation_evidence_sha256: str = Field(pattern=_SHA256)
    identity_outcomes: list[QualifiedBindingIdentityOutcome]
    rejected_pairs: list[QualifiedBindingRejectedPair] = Field(default_factory=list)
    predicate_fact_ids_by_component: dict[str, dict[str, list[str]]] | None = None
    control_selections: dict[str, list[str]] | None = None
    review_context_id: str | None = Field(default=None, min_length=1)
    review_context_sha256: str | None = Field(default=None, pattern=_SHA256)
    judgment_content: JudgmentContentAdoption | None = None
    content_supported_pair_ids: list[str] = Field(default_factory=list)
    verified_judgment_requirement_ids: list[str] = Field(default_factory=list)
    proposition_evidence: PropositionEvidenceAdoption | None = None
    proposition_relations: list[dict] = Field(default_factory=list)
    unresolved_proposition_pairs: list[dict] = Field(default_factory=list)
    observation_relation: ObservationRelationAdoption | None = None
    observation_relations: list[dict] = Field(default_factory=list)
    frequency_evidence: FrequencyEvidenceAdoption | None = None
    frequency_statements: list[dict] = Field(default_factory=list)
    accepted: Literal[False] = False
    authorized_clinical_adoption: Literal[False] = False
    clinically_qualified: Literal[False] = False
    selection_sha256: str = Field(pattern=_SHA256)

    @model_serializer(mode="wrap")
    def serialize_proposition_results(self, handler):
        value = handler(self)
        if self.frequency_evidence is None:
            value.pop("frequency_evidence", None)
            value.pop("frequency_statements", None)
        if self.observation_relation is None:
            value.pop("observation_relation", None)
            value.pop("observation_relations", None)
        if self.version not in {"qualified-binding-selection/v3", "qualified-binding-selection/v4", "qualified-binding-selection/v5"}:
            for key in ("proposition_evidence", "proposition_relations", "unresolved_proposition_pairs"):
                value.pop(key, None)
        return value

    @model_validator(mode="after")
    def validate_material(self) -> "QualifiedBindingSelectionMaterial":
        if self.frequency_statements and self.frequency_evidence is None:
            raise ValueError("频次声明缺少已评测的原文核实依据")
        if self.frequency_evidence is not None and (
                self.consumer_algorithm_version != QUALIFIED_BINDING_CONSUMER_ALGORITHM
                or self.version != QUALIFIED_BINDING_SELECTION_VERSION
                or self.review_context_id is None):
            raise ValueError("频次依据必须绑定当前方法与审核资料，不能补写历史")
        if self.observation_relations and self.observation_relation is None:
            raise ValueError("复查对应缺少本次已评测的原文核实依据")
        if self.observation_relation is not None and (
                self.consumer_algorithm_version not in {"qualified-binding-selection-consumer/v17", "qualified-binding-selection-consumer/v18", "qualified-binding-selection-consumer/v19", "qualified-binding-selection-consumer/v20", "qualified-binding-selection-consumer/v21", "qualified-binding-selection-consumer/v22", "qualified-binding-selection-consumer/v23", "qualified-binding-selection-consumer/v24", "qualified-binding-selection-consumer/v25", "qualified-binding-selection-consumer/v26", "qualified-binding-selection-consumer/v27", "qualified-binding-selection-consumer/v28", QUALIFIED_BINDING_CONSUMER_ALGORITHM}
                or self.version != QUALIFIED_BINDING_SELECTION_VERSION or self.review_context_id is None):
            raise ValueError("复查对应必须绑定当前方法与审核资料，不能补写历史")
        if (self.review_context_id is None) != (self.review_context_sha256 is None):
            raise ValueError("审核准备身份及内容指纹必须同时保留")
        if self.judgment_content is not None and self.review_context_id is None:
            raise ValueError("书面判断依据必须绑定具体审核准备")
        if self.accepted or self.authorized_clinical_adoption or self.clinically_qualified:
            raise ValueError("选择消费不得声明临床采信或正式采用")
        identities = [item.identity_sha256 for item in self.identity_outcomes]
        if len(identities) != len(set(identities)):
            raise ValueError("条件身份结果不得重复")
        if self.candidate_family == "predicate":
            if self.predicate_fact_ids_by_component is None or self.control_selections is not None:
                raise ValueError("谓词资格选择必须且只能提供组件条件清单")
        else:
            if self.control_selections is None or self.predicate_fact_ids_by_component is not None:
                raise ValueError("控制资格选择必须且只能提供原子选择清单")
        material = self.model_dump(mode="json", exclude={"selection_sha256"})
        if self.consumer_algorithm_version in {"qualified-binding-selection-consumer/v11", "qualified-binding-selection-consumer/v12", "qualified-binding-selection-consumer/v13", "qualified-binding-selection-consumer/v14", "qualified-binding-selection-consumer/v15", "qualified-binding-selection-consumer/v16", "qualified-binding-selection-consumer/v17", "qualified-binding-selection-consumer/v18", "qualified-binding-selection-consumer/v19", "qualified-binding-selection-consumer/v20", "qualified-binding-selection-consumer/v21", "qualified-binding-selection-consumer/v22", "qualified-binding-selection-consumer/v23", "qualified-binding-selection-consumer/v24", "qualified-binding-selection-consumer/v25", "qualified-binding-selection-consumer/v26", "qualified-binding-selection-consumer/v27", "qualified-binding-selection-consumer/v28", "qualified-binding-selection-consumer/v29", "qualified-binding-selection-consumer/v30", QUALIFIED_BINDING_CONSUMER_ALGORITHM} and any(
            item.observation_ordering is not None
            and "selected_fact_ids" not in item.observation_ordering.model_fields_set
            for item in self.identity_outcomes
        ):
            raise ValueError("当前选择方法必须明确记录所采用的事实，不能补推历史记录")
        if self.version not in {"qualified-binding-selection/v4", "qualified-binding-selection/v5"} and any(
            item.observation_ordering is not None for item in self.identity_outcomes
        ):
            raise ValueError("历史选择不能补入观察排序记录")
        if self.version not in {"qualified-binding-selection/v3", "qualified-binding-selection/v4", "qualified-binding-selection/v5"}:
            if self.proposition_evidence or self.proposition_relations or self.unresolved_proposition_pairs:
                raise ValueError("历史选择不能补入原文含义核实结果")
            for key in ("proposition_evidence", "proposition_relations", "unresolved_proposition_pairs"):
                material.pop(key, None)
        elif (self.proposition_relations or self.unresolved_proposition_pairs) and self.proposition_evidence is None:
            raise ValueError("原文关系记录缺少已核实的方法依据")
        if self.proposition_evidence is not None and (
                self.review_context_id is None
                or (self.version != "qualified-binding-selection/v5" and self.candidate_family != "control")):
            raise ValueError("原文含义依据必须绑定支持本类条件的审核准备")
        if self.version == "qualified-binding-selection/v1":
            if (self.judgment_content or self.content_supported_pair_ids or self.verified_judgment_requirement_ids
                    or self.review_context_id is not None):
                raise ValueError("历史选择不能补入新判断依据")
            for key in ("judgment_content", "content_supported_pair_ids", "verified_judgment_requirement_ids",
                        "review_context_id", "review_context_sha256"):
                material.pop(key)
        elif (self.content_supported_pair_ids or self.verified_judgment_requirement_ids) and self.judgment_content is None:
            raise ValueError("正面判断选择缺少已核实的内容依据")
        if canonical_hash(material) != self.selection_sha256:
            raise ValueError("资格选择哈希与内容不一致")
        return self


def qualified_binding_selection_hash(material: dict) -> str:
    payload = dict(material)
    payload.pop("selection_sha256", None)
    return canonical_hash(payload)
