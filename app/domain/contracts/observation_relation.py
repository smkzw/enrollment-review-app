"""Source-local observation relationships, never permission or result selection."""
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from app.domain.publication import canonical_hash
from .binding_qualification import BindingQualificationPairContext
from .common import ContractModel
from .repeat_scheme import RepeatScheme
from .rules import WorkflowStage

OBSERVATION_RELATION_VERSION = "observation-relation/v5"


class ObservationRelationContext(ContractModel):
    version: Literal["observation-relation/v1", "observation-relation/v2", "observation-relation/v3", "observation-relation/v4", "observation-relation/v5"] = "observation-relation/v1"
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_job_id: str = Field(min_length=1)
    frozen_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scheme: RepeatScheme
    members: list[BindingQualificationPairContext] = Field(min_length=1)
    auxiliary_members: list[BindingQualificationPairContext] = Field(default_factory=list)
    workflow_stage: WorkflowStage | None = None

    @property
    def source_members(self):
        return [*self.members, *self.auxiliary_members]

    @model_serializer(mode="wrap")
    def preserve_legacy_context(self, handler):
        value = handler(self)
        if self.version == "observation-relation/v1":
            value.pop("version", None)
        if self.version not in {"observation-relation/v3", "observation-relation/v4", "observation-relation/v5"}:
            value.pop("auxiliary_members", None)
        if self.workflow_stage is None:
            value.pop("workflow_stage", None)
        return value

    @model_validator(mode="after")
    def validate_group(self):
        if self.version in {"observation-relation/v4", "observation-relation/v5"}:
            if (self.workflow_stage is None
                    or self.workflow_stage.workflow_stage_id != self.members[0].episode.get("workflow_stage_id")
                    or self.workflow_stage.stage != self.members[0].episode.get("stage")):
                raise ValueError("观察核对须带本次审核的正式流程名称与节点身份")
        elif self.workflow_stage is not None:
            raise ValueError("旧观察核对不能补入未保存的流程说明")
        ids = [item.pair_id for item in self.members]
        if ids != sorted(set(ids)):
            raise ValueError("复查关系的原文配对须排序且不得重复")
        auxiliary_ids = [item.pair_id for item in self.auxiliary_members]
        if (self.version not in {"observation-relation/v3", "observation-relation/v4", "observation-relation/v5"} and self.auxiliary_members
                or auxiliary_ids != sorted(set(auxiliary_ids)) or set(ids) & set(auxiliary_ids)):
            raise ValueError("辅助原文须独立排序，不能重复或补入历史核对")
        for item in self.auxiliary_members:
            if (item.identity_sha256 == self.identity_sha256
                    or (item.candidate_job_id, item.frozen_input_sha256)
                    != (self.candidate_job_id, self.frozen_input_sha256)
                    or any(getattr(item, key) != getattr(self.members[0], key)
                           for key in ("episode", "comparison_sha256", "candidate_family", "identity_field"))):
                raise ValueError("辅助原文须来自本次同类候选及节点，不能混入其他要求的结果值")
        if any((item.identity_sha256, item.candidate_job_id, item.frozen_input_sha256)
               != (self.identity_sha256, self.candidate_job_id, self.frozen_input_sha256)
               for item in self.members):
            raise ValueError("复查对应不能混合不同要求、任务或资料版本")
        for field in ("episode", "condition", "parent_source_context", "comparison_sha256",
                      "candidate_family", "identity_field"):
            if len({canonical_hash(getattr(item, field)) for item in self.members}) != 1:
                raise ValueError("复查对应的节点、要求或原始候选范围不一致")
        for identity, content in (("fact_id", "fact"), ("locator_id", "locator")):
            seen = {}
            for member in self.source_members:
                key, value = getattr(member, identity), getattr(member, content)
                if key in seen and seen[key] != value:
                    raise ValueError("同一原文或事实身份出现不同内容，不能覆盖后继续核实")
                seen[key] = value
        material = self.model_dump(mode="json", exclude={"pair_id"})
        if self.pair_id != canonical_hash({"version": self.version, **material}):
            raise ValueError("复查关系核实身份与完整原文不一致")
        return self


class ObservationRelationQuote(ContractModel):
    fact_id: str = Field(min_length=1)
    locator_id: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)

    @model_validator(mode="after")
    def nonblank(self):
        if any(not value.strip() for value in (self.fact_id, self.locator_id, self.excerpt)):
            raise ValueError("复查对应的原文引用不得为空白")
        return self


class ObservationRelationLink(ContractModel):
    left_fact_id: str = Field(min_length=1)
    right_fact_id: str = Field(min_length=1)
    relation: Literal["repeat_of", "same_acquisition"]
    reference_kind: Literal["initial_observation", "preceding_observation", "unspecified"] | None = None
    quotes: list[ObservationRelationQuote] = Field(min_length=1)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def distinct_observations(self):
        if self.left_fact_id == self.right_fact_id or not self.explanation.strip():
            raise ValueError("观察关系须指向不同记录并说明原文依据")
        if self.relation == "same_acquisition" and self.reference_kind is not None:
            raise ValueError("同次检查关系不能夹带复查回指类型")
        return self

    @model_serializer(mode="wrap")
    def preserve_legacy_reference(self, handler):
        value = handler(self)
        if self.reference_kind is None:
            value.pop("reference_kind", None)
        return value

    def agreement_key(self):
        ids = (self.left_fact_id, self.right_fact_id)
        key = (self.relation, *(sorted(ids) if self.relation == "same_acquisition" else ids))
        return (*key, self.reference_kind) if self.reference_kind is not None else key


class ObservationOrigin(ContractModel):
    fact_id: str = Field(min_length=1)
    role: Literal["initial", "repeat", "unresolved"]
    quotes: list[ObservationRelationQuote]
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_source(self):
        if not self.fact_id.strip() or not self.explanation.strip():
            raise ValueError("检查次序须保留记录身份及原文说明")
        if self.role != "unresolved" and not self.quotes:
            raise ValueError("初查或复查归属须有明确原文，不能仅据日期推断")
        if any(item.fact_id != self.fact_id for item in self.quotes):
            raise ValueError("检查次序说明须引用本条记录的原文")
        return self


class AuxiliaryObservationAssociation(ContractModel):
    auxiliary_pair_id: str = Field(min_length=1)
    observation_fact_id: str = Field(min_length=1)
    auxiliary_excerpt: str = Field(min_length=1)
    observation_quotes: list[ObservationRelationQuote] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    shared_scope_excerpt: str | None = Field(default=None, min_length=1)

    @model_serializer(mode="wrap")
    def preserve_legacy_scope(self, handler):
        value = handler(self)
        if self.shared_scope_excerpt is None:
            value.pop("shared_scope_excerpt", None)
        return value

    @model_validator(mode="after")
    def require_association_source(self):
        if any(not value.strip() for value in (
            self.auxiliary_pair_id, self.observation_fact_id, self.auxiliary_excerpt, self.explanation
        )) or any(quote.fact_id != self.observation_fact_id for quote in self.observation_quotes):
            raise ValueError("辅助归属须明确对应检查并保留两端原文")
        if self.shared_scope_excerpt is not None and not self.shared_scope_excerpt.strip():
            raise ValueError("多次检查共用依据须保留明确覆盖范围的原文")
        return self

    def agreement_key(self):
        return self.auxiliary_pair_id, self.observation_fact_id


class ObservationEpisodeMembership(ContractModel):
    """Source-stated visit membership, never inferred from upload ownership."""
    fact_id: str = Field(min_length=1)
    membership: Literal["current_episode", "other_episode", "unresolved"]
    quotes: list[ObservationRelationQuote]
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_membership_source(self):
        if not self.fact_id.strip() or not self.explanation.strip():
            raise ValueError("检查节点归属须保留记录身份及原文说明")
        if self.membership != "unresolved" and not self.quotes:
            raise ValueError("明确检查节点归属须有原文依据，不能按上传位置推断")
        if any(quote.fact_id != self.fact_id for quote in self.quotes):
            raise ValueError("检查节点归属须引用本条记录原文")
        return self


class ObservationRelationResult(ContractModel):
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_fact_ids: list[str]
    links: list[ObservationRelationLink]
    origins: list[ObservationOrigin] | None = None
    unresolved_notes: list[str]
    reviewed_auxiliary_pair_ids: list[str] | None = None
    auxiliary_associations: list[AuxiliaryObservationAssociation] | None = None
    auxiliary_unresolved_notes: list[str] | None = None
    episode_memberships: list[ObservationEpisodeMembership] | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_origins(self, handler):
        value = handler(self)
        if self.origins is None:
            value.pop("origins", None)
        for key in ("reviewed_auxiliary_pair_ids", "auxiliary_associations", "auxiliary_unresolved_notes", "episode_memberships"):
            if getattr(self, key) is None:
                value.pop(key, None)
        return value

    @model_validator(mode="after")
    def unique_coverage(self):
        if self.reviewed_fact_ids != sorted(set(self.reviewed_fact_ids)):
            raise ValueError("已核对的观察记录须完整列出且不得重复")
        if self.episode_memberships is not None:
            ids = [item.fact_id for item in self.episode_memberships]
            if len(ids) != len(set(ids)) or not set(ids) <= set(self.reviewed_fact_ids):
                raise ValueError("检查节点归属不得重复或超出本次核对记录")
        keys = [link.agreement_key() for link in self.links]
        if len(set(keys)) != len(keys):
            raise ValueError("同一观察关系不得重复声明")
        if self.origins is not None:
            ids = [item.fact_id for item in self.origins]
            if len(ids) != len(set(ids)) or set(ids) != set(self.reviewed_fact_ids):
                raise ValueError("检查次序说明须逐项覆盖已核对记录且不得重复")
        if any(not note.strip() for note in self.unresolved_notes):
            raise ValueError("待核实原因不得为空白")
        if (self.reviewed_auxiliary_pair_ids is None) != (self.auxiliary_associations is None):
            raise ValueError("辅助原文核对范围与归属结果须同时保存")
        if (self.reviewed_auxiliary_pair_ids is None) != (self.auxiliary_unresolved_notes is None):
            raise ValueError("辅助原文疑问须与核对范围同时保存")
        if any(not note.strip() for note in self.auxiliary_unresolved_notes or ()):
            raise ValueError("辅助原文待核实原因不得为空白")
        if self.reviewed_auxiliary_pair_ids is not None:
            if self.reviewed_auxiliary_pair_ids != sorted(set(self.reviewed_auxiliary_pair_ids)):
                raise ValueError("辅助原文核对范围须排序且不得重复")
            keys = [item.agreement_key() for item in self.auxiliary_associations]
            if len(keys) != len(set(keys)) or any(key[0] not in self.reviewed_auxiliary_pair_ids for key in keys):
                raise ValueError("辅助归属不能重复或超出已核对原文")
        return self


class ObservationRelationPayload(ContractModel):
    results: list[ObservationRelationResult]

    @model_validator(mode="after")
    def unique_groups(self):
        ids = [item.pair_id for item in self.results]
        if len(ids) != len(set(ids)):
            raise ValueError("同一要求的观察关系结果不得重复")
        return self
