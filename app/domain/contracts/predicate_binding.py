"""R01 绑定链冻结输入合同（设计 §17.1.1 第 1 步；纯校验，无存储）。

本模块只冻结“供后续受限候选任务消费”的确定性输入结构，**不是**已验证绑定，
更不是任何临床结论：

- ``FrozenPredicateIdentity``    单个原子谓词的完整已发布身份：触发/例外角色、
                                 组件上下文、逐字原文定位（``exact_source_clauses``）
                                 与表达式时间约束，按内容寻址；
- ``FrozenRuleComponent``        一个规则组件的冻结身份：触发与例外谓词分别列出，
                                 已发布资料要求全文随组件提供（仅候选收窄用，
                                 ``fact_type`` 索引不是语义证明）；
- ``FrozenFactRecord``           当前已校正事实头：对象/值/单位/日期/极性与定位；
- ``FrozenLocatorIdentity``      经仓储来源核验的定位身份（原文摘录/哈希/精度）；
- ``PredicateBindingFrozenInput`` 冻结输入整体：``frozen_input_sha256`` 对全部内容
                                 寻址；同内容不同顺序得到同一哈希。

硬边界（与设计 §17.1.1 一致）：

- 冻结输入不携带模型候选、不带“已验证绑定”状态、不带任何求值结论；
- 不存在于此输入的事实、条件或摘录，下游一律拒绝；
- 同一事实可出现在输入中供多个条件使用；同一稳定身份出现两条记录是身份冲突，
  构造即拒绝（不含“旧修订静默保留”）；
- 谓词逐字原文取自已发布合同；缺失时保留为空并明确为未核实，非空但不属于父规则原文时拒绝冻结，不猜值、不造摘录。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from app.domain.publication import canonical_hash

from .common import ContractModel, ScalarValue
from .enums import (
    FactPolarity,
    LocatorAuthenticity,
    LocatorPrecision,
    LocatorSourceLayer,
    ProfileLane,
    RuleKind,
    SourceStrength,
    StudyPhase,
)
from .facts import AssertionBasis, FactAuthority, PartialDateRange
from .review import ReviewEpisode
from .rules import AtomicPredicate, EvidenceRequirement, TimeConstraint, RuleExpression, RepeatTriggerCondition
from .rules import validate_repeat_trigger_conditions

__all__ = [
    "FrozenFactRecord",
    "FrozenLocatorIdentity",
    "FrozenPredicateIdentity",
    "FrozenRuleComponent",
    "PredicateBindingFrozenInput",
    "PredicateBindingRole",
    "predicate_binding_frozen_input_sha256",
    "predicate_component_identity_sha256",
    "predicate_identity_sha256",
]

_SHA256 = r"^[0-9a-f]{64}$"

PredicateBindingRole = Literal["trigger", "exception", "repeat_trigger"]

_PREDICATE_IDENTITY = "predicate_binding_predicate/v1"
_COMPONENT_IDENTITY = "predicate_binding_component/v1"
_FROZEN_INPUT_IDENTITY = "predicate_binding_frozen_input/v1"


def _expression_material(expression: RuleExpression | None) -> dict | None:
    if expression is None:
        return None
    material = expression.model_dump(mode="json")
    if expression.kind == "logical":
        # Only commutative ALL/ANY and unary NOT may be order-normalized.
        if expression.operator.value not in {"all", "any", "not"}:
            raise ValueError("不支持对该逻辑算子进行顺序归一")
        material["children"] = sorted(
            (_expression_material(child) for child in expression.children),
            key=canonical_hash,
        )
    return material


def iter_binding_atoms(expression: RuleExpression):
    if expression.kind == "predicate":
        yield expression
    else:
        for child in expression.children:
            yield from iter_binding_atoms(child)


def predicate_identity_sha256(
    *,
    role: str,
    rule_component_id: str,
    parent_rule_id: str,
    official_code: str,
    predicate: AtomicPredicate,
    time_constraint: TimeConstraint | None,
) -> str:
    """单个原子谓词的内容寻址身份（含组件上下文与逐字原文定位）。"""
    return canonical_hash(
        {
            "identity": _PREDICATE_IDENTITY,
            "role": role,
            "rule_component_id": rule_component_id,
            "parent_rule_id": parent_rule_id,
            "official_code": official_code,
            "predicate": predicate.model_dump(mode="json"),
            "time_constraint": (
                time_constraint.model_dump(mode="json")
                if time_constraint is not None
                else None
            ),
        }
    )


class FrozenPredicateIdentity(ContractModel):
    """触发/例外谓词的冻结身份；原文不足显式标记未核实，不猜值。"""

    predicate_id: str = Field(min_length=1)
    role: PredicateBindingRole
    rule_component_id: str = Field(min_length=1)
    parent_rule_id: str = Field(min_length=1)
    official_code: str = Field(pattern=r"^(IN|EX|REQ)-\d{2}$")
    predicate: AtomicPredicate
    time_constraint: TimeConstraint | None = None
    predicate_identity_sha256: str = Field(pattern=_SHA256)
    source_status: Literal["verbatim", "unverified"] | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> "FrozenPredicateIdentity":
        if self.predicate.predicate_id != self.predicate_id:
            raise ValueError("冻结谓词 ID 必须与已发布谓词一致")
        expected = predicate_identity_sha256(
            role=self.role,
            rule_component_id=self.rule_component_id,
            parent_rule_id=self.parent_rule_id,
            official_code=self.official_code,
            predicate=self.predicate,
            time_constraint=self.time_constraint,
        )
        if self.predicate_identity_sha256 != expected:
            raise ValueError("冻结谓词身份哈希与内容不一致")
        expected_source_status = (
            "verbatim" if self.predicate.exact_source_clauses else "unverified"
        )
        if self.source_status is None:
            object.__setattr__(self, "source_status", expected_source_status)
        elif self.source_status != expected_source_status:
            raise ValueError("原文核实标记与实际原文字段不一致")
        return self

    def _identity_material(self) -> dict:
        """组件层哈希材料：本谓词条目，不含本层哈希（各层独立可复验）。"""
        return self.model_dump(
            mode="json", exclude={"predicate_identity_sha256", "source_status"}
        )


def predicate_component_identity_sha256(
    *,
    rule_component_id: str,
    parent_rule_id: str,
    official_code: str,
    kind: RuleKind,
    display_code: str,
    title: str,
    rule_source_text: str,
    expression: RuleExpression,
    exception_expression: RuleExpression | None,
    evidence_requirements: list[EvidenceRequirement],
    trigger_predicates: list[FrozenPredicateIdentity],
    exception_predicates: list[FrozenPredicateIdentity],
    repeat_trigger_conditions: list[RepeatTriggerCondition] | None = None,
) -> str:
    """规则组件的内容寻址身份；触发与例外分别进入哈希材料。"""
    return canonical_hash(
        {
            **({"repeat_trigger_conditions": _repeat_condition_material(repeat_trigger_conditions)}
               if repeat_trigger_conditions else {}),
            "identity": _COMPONENT_IDENTITY,
            "rule_component_id": rule_component_id,
            "parent_rule_id": parent_rule_id,
            "official_code": official_code,
            "kind": kind.value,
            "display_code": display_code,
            "title": title,
            "rule_source_text": rule_source_text,
            "expression": _expression_material(expression),
            "exception_expression": _expression_material(exception_expression),
            "evidence_requirements": [
                item.model_dump(mode="json")
                for item in sorted(
                    evidence_requirements, key=lambda item: item.requirement_id
                )
            ],
            "trigger_predicates": [
                item._identity_material()
                for item in sorted(
                    trigger_predicates, key=lambda item: item.predicate_id
                )
            ],
            "exception_predicates": [
                item._identity_material()
                for item in sorted(
                    exception_predicates, key=lambda item: item.predicate_id
                )
            ],
        }
    )


def _repeat_condition_material(conditions):
    return [{"condition_id": item.condition_id, "expression": _expression_material(item.expression),
             **({"predicate_evidence_roles": {
                 key: role.model_dump(mode="json") for key, role in sorted(item.predicate_evidence_roles.items())
             }} if item.predicate_evidence_roles else {})}
            for item in sorted(conditions, key=lambda item: item.condition_id)]


class FrozenRuleComponent(ContractModel):
    """一个规则组件的冻结身份；已发布要求全文随组件提供，不是语义证明。"""

    rule_component_id: str = Field(min_length=1)
    parent_rule_id: str = Field(min_length=1)
    official_code: str = Field(pattern=r"^(IN|EX|REQ)-\d{2}$")
    kind: RuleKind
    display_code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    rule_source_text: str = Field(min_length=1)
    expression: RuleExpression
    exception_expression: RuleExpression | None = None
    repeat_trigger_conditions: list[RepeatTriggerCondition] = Field(default_factory=list)
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    trigger_predicates: list[FrozenPredicateIdentity] = Field(min_length=1)
    exception_predicates: list[FrozenPredicateIdentity] = Field(
        default_factory=list
    )
    component_identity_sha256: str = Field(pattern=_SHA256)

    @property
    def repeat_trigger_predicates(self) -> tuple[FrozenPredicateIdentity, ...]:
        # Derive from the hashed expression; do not persist a second editable copy.
        return tuple(
            FrozenPredicateIdentity(
                predicate_id=atom.predicate.predicate_id,
                role="repeat_trigger",
                rule_component_id=self.rule_component_id,
                parent_rule_id=self.parent_rule_id,
                official_code=self.official_code,
                predicate=atom.predicate,
                time_constraint=atom.time_constraint,
                predicate_identity_sha256=predicate_identity_sha256(
                    role="repeat_trigger",
                    rule_component_id=self.rule_component_id,
                    parent_rule_id=self.parent_rule_id,
                    official_code=self.official_code,
                    predicate=atom.predicate,
                    time_constraint=atom.time_constraint,
                ),
            )
            for condition in self.repeat_trigger_conditions
            for atom in iter_binding_atoms(condition.expression)
        )

    @property
    def binding_predicates(self) -> tuple[FrozenPredicateIdentity, ...]:
        """Conditions needing evidence, not the final eligibility expression."""
        return (*self.trigger_predicates, *self.exception_predicates,
                *self.repeat_trigger_predicates)

    @model_serializer(mode="wrap")
    def preserve_legacy_repeat_conditions(self, handler):
        value = handler(self)
        if not self.repeat_trigger_conditions:
            value.pop("repeat_trigger_conditions", None)
        return value

    @model_validator(mode="after")
    def validate_component(self) -> "FrozenRuleComponent":
        validate_repeat_trigger_conditions(self.expression, self.exception_expression, self.repeat_trigger_conditions)
        trigger_predicates = tuple(self.trigger_predicates)
        exception_predicates = tuple(self.exception_predicates)
        for expression, entries in (
            (self.expression, trigger_predicates),
            (self.exception_expression, exception_predicates),
        ):
            atoms = list(iter_binding_atoms(expression)) if expression else []
            actual = {a.predicate.predicate_id: (a.predicate, a.time_constraint) for a in atoms}
            if len(actual) != len(atoms) or actual != {
                item.predicate_id: (item.predicate, item.time_constraint) for item in entries
            }:
                raise ValueError("冻结表达式与谓词清单不一致")
        for expected_role, predicates in (
            ("trigger", trigger_predicates),
            ("exception", exception_predicates),
            ("repeat_trigger", self.repeat_trigger_predicates),
        ):
            for item in predicates:
                if item.role != expected_role:
                    raise ValueError(
                        f"冻结谓词 {item.predicate_id} 的角色与组件字段不一致"
                    )
                if item.rule_component_id != self.rule_component_id:
                    raise ValueError(
                        f"冻结谓词 {item.predicate_id} 未绑定所在规则组件"
                    )
                if (
                    item.parent_rule_id != self.parent_rule_id
                    or item.official_code != self.official_code
                ):
                    raise ValueError(
                        f"冻结谓词 {item.predicate_id} 的父规则身份与组件不一致"
                    )
                clauses = item.predicate.exact_source_clauses
                if clauses and any(
                    clause not in self.rule_source_text for clause in clauses
                ):
                    raise ValueError(
                        f"冻结谓词 {item.predicate_id} 的原文定位不属于已发布规则原文"
                    )

        predicate_ids = [
            item.predicate_id
            for item in self.binding_predicates
        ]
        if len(predicate_ids) != len(set(predicate_ids)):
            raise ValueError("组件内触发/例外谓词身份不得重复")
        requirement_ids = [
            item.requirement_id for item in self.evidence_requirements
        ]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("组件内资料要求身份不得重复")
        if any(
            item.rule_component_id != self.rule_component_id
            for item in self.evidence_requirements
        ):
            raise ValueError("资料要求必须绑定所在组件")
        component_predicate_ids = {
            item.predicate_id
            for item in self.binding_predicates
        }
        for requirement in self.evidence_requirements:
            if not requirement.predicate_ids:
                continue
            unknown = [
                predicate_id
                for predicate_id in requirement.predicate_ids
                if predicate_id not in component_predicate_ids
            ]
            if unknown:
                raise ValueError("冻结资料要求引用了本组件不存在的谓词")
        expected = predicate_component_identity_sha256(
            rule_component_id=self.rule_component_id,
            parent_rule_id=self.parent_rule_id,
            official_code=self.official_code,
            kind=self.kind,
            display_code=self.display_code,
            title=self.title,
            rule_source_text=self.rule_source_text,
            expression=self.expression,
            exception_expression=self.exception_expression,
            repeat_trigger_conditions=self.repeat_trigger_conditions,
            evidence_requirements=sorted(
                self.evidence_requirements, key=lambda item: item.requirement_id
            ),
            trigger_predicates=sorted(
                self.trigger_predicates, key=lambda item: item.predicate_id
            ),
            exception_predicates=sorted(
                self.exception_predicates, key=lambda item: item.predicate_id
            ),
        )
        if self.component_identity_sha256 != expected:
            raise ValueError("冻结组件身份哈希与内容不一致")
        return self

    def _identity_material(self) -> dict:
        """组件层哈希材料：谓词/要求列表按身份排序，保证乱序同哈希。"""
        material = self.model_dump(
            mode="json", exclude={"component_identity_sha256"}
        )
        material["expression"] = _expression_material(self.expression)
        if self.repeat_trigger_conditions:
            material["repeat_trigger_conditions"] = _repeat_condition_material(self.repeat_trigger_conditions)
        material["exception_expression"] = _expression_material(self.exception_expression)
        material["evidence_requirements"] = sorted(
            material["evidence_requirements"],
            key=lambda item: item["requirement_id"],
        )
        for key in ("trigger_predicates", "exception_predicates"):
            material[key] = sorted(
                [
                    item._identity_material()
                    for item in (
                        self.trigger_predicates
                        if key == "trigger_predicates"
                        else self.exception_predicates
                    )
                ],
                key=lambda item: item["predicate_id"],
            )
        return material


class FrozenFactRecord(ContractModel):
    """当前已校正事实头：对象/值/单位/日期/极性与定位集合。

    不含 run/gate 等过程元数据；``fact_id + stable_identity + revision`` 足以回溯
    持久化记录。``stable_identity`` 由既有发布合同推导，包含被断言对象——
    不同对象同值不会被合并。
    """

    fact_id: str = Field(min_length=1)
    stable_identity: str = Field(pattern=_SHA256)
    revision: int = Field(ge=1)
    fact_type: str = Field(min_length=1)
    profile_lane: ProfileLane
    asserted_object: str = Field(min_length=1)
    polarity: FactPolarity
    value: ScalarValue | None = None
    unit: str | None = None
    source_strength: SourceStrength
    date_range: PartialDateRange | None = None
    record_time: datetime | None = None
    locator_ids: list[str] = Field(min_length=1)
    assertion_basis: AssertionBasis | None = None

    @model_validator(mode="after")
    def validate_fact_record(self) -> "FrozenFactRecord":
        if self.locator_ids != sorted(set(self.locator_ids)):
            raise ValueError("冻结事实定位必须排序且不得重复")
        if (
            self.polarity != FactPolarity.UNKNOWN
            and self.value is None
        ):
            raise ValueError("肯定或否定冻结事实必须携带被断言值")
        return self


class FrozenLocatorIdentity(ContractModel):
    """经 ``EvidenceLocatorRepository`` 来源核验后的定位身份快照。"""

    locator_id: str = Field(min_length=1)
    page_artifact_id: str = Field(min_length=1)
    ocr_page_id: str | None = None
    source_document_version_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    source_layer: LocatorSourceLayer
    source_text_sha256: str = Field(pattern=_SHA256)
    precision: LocatorPrecision
    authenticity: LocatorAuthenticity
    target_id: str = Field(min_length=1)
    text_start: int | None = Field(default=None, ge=0)
    text_end: int | None = Field(default=None, ge=0)
    excerpt: str | None = None
    degradation_reason: str | None = None
    processing_revision_id: str | None = None


class FrozenSourceDocumentIdentity(ContractModel):
    """Upload metadata, not a clinical classification or source acceptance."""

    source_document_version_id: str = Field(min_length=1)
    source_blob_sha256: str = Field(pattern=_SHA256)
    file_name: str = Field(min_length=1)
    media_type: str = Field(min_length=1)


def predicate_binding_frozen_input_sha256(
    *,
    authority: FactAuthority,
    episode: ReviewEpisode,
    rule_set_id: str,
    rule_set_revision: int,
    protocol_version_id: str,
    study_phase: StudyPhase,
    components: list[FrozenRuleComponent],
    facts: list[FrozenFactRecord],
    locators: list[FrozenLocatorIdentity],
    documents: list[FrozenSourceDocumentIdentity] | None = None,
) -> str:
    """冻结输入整体的内容寻址身份；同内容不同顺序同一哈希。"""
    return canonical_hash(
        {
            "identity": (_FROZEN_INPUT_IDENTITY if documents is None
                         else "predicate-binding-frozen-input/v2"),
            **({} if documents is None else {"documents": [
                item.model_dump(mode="json") for item in sorted(
                    documents, key=lambda item: item.source_document_version_id)
            ]}),
            "authority": authority.model_dump(mode="json"),
            "episode": episode.model_dump(mode="json"),
            "rule_set_id": rule_set_id,
            "rule_set_revision": rule_set_revision,
            "protocol_version_id": protocol_version_id,
            "study_phase": study_phase.value,
            "components": [
                item._identity_material()
                for item in sorted(
                    components, key=lambda item: item.rule_component_id
                )
            ],
            "facts": [
                item.model_dump(mode="json")
                for item in sorted(
                    facts,
                    key=lambda item: (item.stable_identity, item.fact_id),
                )
            ],
            "locators": [
                item.model_dump(mode="json")
                for item in sorted(locators, key=lambda item: item.locator_id)
            ],
        }
    )


class PredicateBindingFrozenInput(ContractModel):
    """绑定链第 1 步冻结输入；不是已验证绑定，不是临床判断。"""

    binding_input_version: Literal[
        "predicate-binding-frozen-input/v1", "predicate-binding-frozen-input/v2"
    ] = (
        "predicate-binding-frozen-input/v1"
    )
    authority: FactAuthority
    episode: ReviewEpisode
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    protocol_version_id: str = Field(min_length=1)
    study_phase: StudyPhase
    components: list[FrozenRuleComponent] = Field(min_length=1)
    facts: list[FrozenFactRecord] = Field(default_factory=list)
    locators: list[FrozenLocatorIdentity] = Field(default_factory=list)
    documents: list[FrozenSourceDocumentIdentity] | None = None
    frozen_input_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_frozen_input(self) -> "PredicateBindingFrozenInput":
        if (self.binding_input_version == "predicate-binding-frozen-input/v2") != (
            self.documents is not None
        ):
            raise ValueError("冻结输入版本与文件来源清单不一致")
        if self.documents is not None:
            document_ids = [item.source_document_version_id for item in self.documents]
            if len(document_ids) != len(set(document_ids)):
                raise ValueError("冻结文件来源身份不得重复")
            if set(document_ids) != {
                locator.source_document_version_id for locator in self.locators
            }:
                raise ValueError("冻结文件来源必须完整对应定位引用，不得遗漏或夹带文件")
        for name in ("project_id", "subject_id", "review_episode_id", "rule_set_id", "rule_set_revision", "protocol_version_id"):
            if getattr(self.episode, name) != getattr(self.authority, name):
                raise ValueError("冻结审核节点与事实权威不一致")
        if (
            self.episode.active_evidence_snapshot_id != self.authority.evidence_snapshot_v2_id
            or self.episode.active_evidence_processing_revision_id != self.authority.complete_processing_revision_id
            or self.episode.study_phase != self.study_phase
            or self.episode.revision != self.authority.episode_revision
        ):
            raise ValueError("冻结审核节点活动资料或研究期别不一致")
        if (
            self.rule_set_id != self.authority.rule_set_id
            or self.rule_set_revision != self.authority.rule_set_revision
            or self.protocol_version_id != self.authority.protocol_version_id
        ):
            raise ValueError(
                "冻结输入规则集身份与权威元组不一致：拒绝跨权威组装"
            )
        component_ids = [item.rule_component_id for item in self.components]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("冻结输入内组件身份不得重复")
        predicate_ids = [
            item.predicate_id
            for component in self.components
            for item in component.binding_predicates
        ]
        if len(predicate_ids) != len(set(predicate_ids)):
            raise ValueError("冻结输入内谓词身份不得重复")
        fact_ids = [item.fact_id for item in self.facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("冻结输入内事实记录 ID 不得重复")
        stable_identities = [item.stable_identity for item in self.facts]
        if len(stable_identities) != len(set(stable_identities)):
            raise ValueError(
                "冻结输入内同一稳定身份出现多条记录：重复身份冲突，拒绝冻结"
            )
        locator_ids = [item.locator_id for item in self.locators]
        if len(locator_ids) != len(set(locator_ids)):
            raise ValueError("冻结输入内定位身份不得重复")
        referenced_locators = {
            locator_id
            for fact in self.facts
            for locator_id in fact.locator_ids
        }
        if not referenced_locators.issubset(set(locator_ids)):
            missing = sorted(referenced_locators - set(locator_ids))
            raise ValueError(f"冻结事实引用了不在冻结输入内的定位：{missing}")
        if set(locator_ids) - referenced_locators:
            unused = sorted(set(locator_ids) - referenced_locators)
            raise ValueError(f"冻结输入携带了无事实引用的定位：{unused}")
        expected = predicate_binding_frozen_input_sha256(
            authority=self.authority,
            episode=self.episode,
            rule_set_id=self.rule_set_id,
            rule_set_revision=self.rule_set_revision,
            protocol_version_id=self.protocol_version_id,
            study_phase=self.study_phase,
            components=self.components,
            facts=self.facts,
            locators=self.locators,
            documents=self.documents,
        )
        if self.frozen_input_sha256 != expected:
            raise ValueError("冻结输入内容哈希与内容不一致")
        return self
