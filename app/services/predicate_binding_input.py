"""R01 绑定链冻结输入构建器（设计 §17.1.1 第 1 步；只读，未接消费链）。

``build_predicate_binding_frozen_input`` 从既有仓储与校验器只读构建供后续受限
候选任务消费的冻结输入（见 ``app.domain.contracts.predicate_binding``）：

1. 活动权威：复用 ``authority_from_active_episode``（成对活动指针 + 完整校验），
   并按 ``FactAuthorityValidator.validate_and_get_revision`` 在同一事务内重验——
   不缓存任何“已验证”标记；节点/快照/完整修订或修订号漂移即拒绝（旧修订拒绝）。
2. 规则组件：复用 ``get_rule_set`` 按权威元组的 ``rule_set_id + rule_set_revision``
   读取已发布规则集，并用 ``project_clause_pack``/``verify_clause_pack`` 复验
   ClausePack 身份；方案/修订不一致（跨权威）即拒绝。触发/例外谓词按表达式
   位置确定性导出（predicate_id 在 RuleSet 内唯一），原文取
   ``exact_source_clauses`` 与父规则 ``source_text`` 逐字内容；谓词缺原文时明确
   保留为未核实，非空原文不属于已发布规则时拒绝，不猜值、不造摘录。
3. 已校正事实头：复用 ``current_fact_heads``（同稳定身份取当前修订、同修订号
   冲突 fail-closed、校正排除集不复活旧值）。调用方显式传入事实时同样走该选择，
   且逐条核对权威元组相等——跨 authority 事实显式拒绝。
4. 定位来源核验：复用 ``EvidenceLocatorRepository.get_many``（逐条重验哈希/摘录/
   范围锚定，缺失即 ``NotFoundError``、伪造/篡改即 ``LocatorIdentityError``），
   再按 ``FactAuthorityValidator.validate_locators`` 拒绝跨审核节点/跨快照/跨
   处理修订的定位引用。

诚实边界：

- 本构建器只产出冻结输入：**不**产生候选、不验证语义对应、不输出已验证绑定，
  ``fact_type``/``FactRuleLink`` 式索引仅随已发布要求原文进入输入供下游收窄，
  不是语义证明；
- 每次构建都在当前数据库状态上重新校验与重新计算内容哈希；同内容不同顺序
  得到同一 ``frozen_input_sha256``，任何内容漂移都会改变哈希并在合同层被拒绝；
- 只读：不写库、不提交、不调用模型、不产生时间戳、不产生任何临床结论。
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.domain.contracts.predicate_binding import (
    predicate_component_identity_sha256,
    FrozenFactRecord,
    FrozenLocatorIdentity,
    FrozenPredicateIdentity,
    FrozenRuleComponent,
    FrozenSourceDocumentIdentity,
    PredicateBindingFrozenInput,
    predicate_binding_frozen_input_sha256,
    predicate_identity_sha256,
    iter_binding_atoms,
)
from app.domain.contracts.rules import (
    RuleComponent,
    Rule,
    RuleSet,
)
from app.projections.clause_pack import (
    ClausePackProjectionError,
    project_clause_pack,
    verify_clause_pack,
)
from app.domain.contracts.facts import ClinicalFactV2
from app.services.fact_normalization_command_service import (
    authority_from_active_episode,
)
from app.storage.active_facts import current_fact_heads
from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
from app.storage.evidence_repositories import SourceDocumentRepository
from app.storage.fact_authority import (
    FactAuthorityError,
    FactAuthorityValidator,
)
from app.storage.repositories import EpisodeRepository, get_rule_set

__all__ = [
    "PredicateBindingInputError",
    "build_predicate_binding_frozen_input",
]


class PredicateBindingInputError(ValueError):
    """冻结输入构建的有界错误：权威、规则集或事实作用域不一致。

    活动权威校验失败包装为本异常并保留 cause 链；仓储读取的定位缺失、伪造、
    跨节点与重复身份冲突错误原样传播（异常类型即拒绝原因）。
    """


def _frozen_component(component: RuleComponent, rule: Rule) -> FrozenRuleComponent:
    rule_component_id = component.rule_component_id
    trigger: list[FrozenPredicateIdentity] = []
    exception: list[FrozenPredicateIdentity] = []
    for role, expression in (
        ("trigger", component.expression),
        ("exception", component.exception_expression),
    ):
        if expression is None:
            continue
        target = trigger if role == "trigger" else exception
        for atomic in iter_binding_atoms(expression):
            predicate = atomic.predicate
            target.append(
                FrozenPredicateIdentity(
                    predicate_id=predicate.predicate_id,
                    role=role,
                    rule_component_id=rule_component_id,
                    parent_rule_id=component.parent_rule_id,
                    official_code=rule.official_code,
                    predicate=predicate,
                    time_constraint=atomic.time_constraint,
                    predicate_identity_sha256=predicate_identity_sha256(
                        role=role,
                        rule_component_id=rule_component_id,
                        parent_rule_id=component.parent_rule_id,
                        official_code=rule.official_code,
                        predicate=predicate,
                        time_constraint=atomic.time_constraint,
                    ),
                )
            )
    if not trigger:
        raise PredicateBindingInputError(
            f"规则组件 {rule_component_id} 的触发表达式不含原子谓词，拒绝冻结"
        )
    return FrozenRuleComponent(
        rule_component_id=rule_component_id,
        parent_rule_id=component.parent_rule_id,
        official_code=rule.official_code,
        kind=rule.kind,
        display_code=component.display_code,
        title=component.title,
        rule_source_text=rule.source_text,
        expression=component.expression,
        exception_expression=component.exception_expression,
        repeat_trigger_conditions=list(component.repeat_trigger_conditions),
        evidence_requirements=list(component.evidence_requirements),
        trigger_predicates=trigger,
        exception_predicates=exception,
        component_identity_sha256=predicate_component_identity_sha256(
            rule_component_id=rule_component_id,
            parent_rule_id=component.parent_rule_id,
            official_code=rule.official_code,
            kind=rule.kind,
            display_code=component.display_code,
            title=component.title,
            rule_source_text=rule.source_text,
            expression=component.expression,
            exception_expression=component.exception_expression,
            repeat_trigger_conditions=list(component.repeat_trigger_conditions),
            evidence_requirements=list(component.evidence_requirements),
            trigger_predicates=trigger,
            exception_predicates=exception,
        ),
    )


def _frozen_fact(fact: ClinicalFactV2) -> FrozenFactRecord:
    return FrozenFactRecord(
        fact_id=fact.fact_id,
        stable_identity=fact.stable_identity,
        revision=fact.revision,
        fact_type=fact.fact_type,
        profile_lane=fact.profile_lane,
        asserted_object=fact.asserted_object,
        polarity=fact.polarity,
        value=fact.value,
        unit=fact.unit,
        source_strength=fact.source_strength,
        date_range=fact.date_range,
        record_time=fact.record_time,
        locator_ids=list(fact.locator_ids),
        assertion_basis=fact.assertion_basis,
    )


def build_predicate_binding_frozen_input(
    session: Session,
    review_episode_id: str,
    *,
    component_ids: Sequence[str] | None = None,
    fact_heads: Sequence[ClinicalFactV2] | None = None,
) -> PredicateBindingFrozenInput:
    """只读构建当前审核节点的谓词绑定冻结输入（见模块 docstring）。

    ``component_ids`` 缺省冻结规则集全部组件；给定时逐个核对存在且不重复。
    ``fact_heads`` 缺省从仓储读取当前已校正事实头；给定时仍经
    ``current_fact_heads`` 选择，并与仓储当前集合逐项核对，不允许改值或漏项。
    """
    authority = authority_from_active_episode(session, review_episode_id)
    episode = EpisodeRepository(session).get(review_episode_id)
    try:
        revision = FactAuthorityValidator(session).validate_and_get_revision(
            authority
        )
    except FactAuthorityError as exc:
        raise PredicateBindingInputError(
            f"活动权威已变化或修订号陈旧，拒绝构建冻结输入：{exc}"
        ) from exc
    if (
        revision.evidence_processing_revision_id
        != authority.complete_processing_revision_id
        or revision.review_episode_id != authority.review_episode_id
        or revision.evidence_snapshot_id != authority.evidence_snapshot_v2_id
    ):
        raise PredicateBindingInputError(
            "完整修订作用域与权威元组不一致，拒绝跨节点构建冻结输入"
        )

    rule_set: RuleSet = get_rule_set(
        session, authority.rule_set_id, authority.rule_set_revision
    )
    if (
        rule_set.rule_set_id != authority.rule_set_id
        or rule_set.revision != authority.rule_set_revision
        or rule_set.protocol_version_id != authority.protocol_version_id
    ):
        raise PredicateBindingInputError(
            f"规则集 {rule_set.rule_set_id} revision {rule_set.revision} 的身份/方案"
            f"版本 {rule_set.protocol_version_id} 与权威元组"
            f" {authority.rule_set_id}/{authority.rule_set_revision}/"
            f"{authority.protocol_version_id} 不一致，拒绝跨权威冻结"
        )
    try:
        clause_pack = project_clause_pack(rule_set)
        verify_clause_pack(clause_pack)
    except ClausePackProjectionError as exc:
        raise PredicateBindingInputError(
            "已发布 RuleSet 无法形成可复验 ClausePack，拒绝冻结"
        ) from exc
    components_by_id = {
        component.rule_component_id: (rule, component)
        for rule in rule_set.rules
        for component in rule.components
    }
    clause_component_ids = {
        clause.rule_component_id for clause in clause_pack.clauses
    }
    if clause_component_ids != set(components_by_id):
        raise PredicateBindingInputError(
            "已发布 RuleSet 与 ClausePack 组件集合不一致，拒绝冻结"
        )
    if component_ids is None:
        selected = sorted(components_by_id)
    else:
        selected = list(component_ids)
        if len(selected) != len(set(selected)):
            raise PredicateBindingInputError("所选组件身份重复，拒绝冻结")
        missing = [item for item in selected if item not in components_by_id]
        if missing:
            raise PredicateBindingInputError(
                f"组件 {missing} 不在规则集 {rule_set.rule_set_id} revision "
                f"{rule_set.revision} 内，拒绝冻结不存在的组件"
            )
        selected.sort()
    frozen_components = [
        _frozen_component(components_by_id[item][1], components_by_id[item][0])
        for item in selected
    ]

    for fact in fact_heads or ():
        if fact.authority != authority:
            raise PredicateBindingInputError(
                f"事实 {fact.fact_id} 的权威元组与当前审核节点不一致："
                "拒绝跨 authority 冻结"
            )
    facts = current_fact_heads(session, authority, facts=fact_heads)
    frozen_facts = [_frozen_fact(fact) for fact in facts]

    locator_ids = sorted(
        {locator_id for fact in facts for locator_id in fact.locator_ids}
    )
    locators_by_id = {
        locator.locator_id: locator
        for locator in EvidenceLocatorRepository(session).get_many(locator_ids)
    }
    if locator_ids:
        FactAuthorityValidator(session).validate_locators(authority, locator_ids)
    if fact_heads is not None:
        published = current_fact_heads(session, authority)
        if facts != published:
            raise PredicateBindingInputError(
                "传入事实与当前已发布事实集合不一致，拒绝改值、漏项或未发布内容"
            )
    frozen_locators = [
        FrozenLocatorIdentity(
            locator_id=locator.locator_id,
            page_artifact_id=locator.page_artifact_id,
            ocr_page_id=locator.ocr_page_id,
            source_document_version_id=locator.source_document_version_id,
            page_number=locator.page_number,
            source_layer=locator.source_layer,
            source_text_sha256=locator.source_text_sha256,
            precision=locator.precision,
            authenticity=locator.authenticity,
            target_id=locator.target_id,
            text_start=locator.text_start,
            text_end=locator.text_end,
            excerpt=locator.excerpt,
            degradation_reason=locator.degradation_reason,
            processing_revision_id=locator.processing_revision_id,
        )
        for locator_id, locator in locators_by_id.items()
    ]

    documents = []
    document_repository = SourceDocumentRepository(session)
    for document_id in sorted({item.source_document_version_id for item in frozen_locators}):
        document = document_repository.get(document_id)
        if (document.project_id, document.subject_id) != (authority.project_id, authority.subject_id):
            raise PredicateBindingInputError("文件来源不属于当前项目和受试者")
        documents.append(FrozenSourceDocumentIdentity(
            source_document_version_id=document.source_document_version_id,
            source_blob_sha256=document.source_blob_sha256,
            file_name=document.file_name,
            media_type=document.media_type,
        ))

    return PredicateBindingFrozenInput(
        binding_input_version="predicate-binding-frozen-input/v2",
        authority=authority,
        episode=episode,
        rule_set_id=authority.rule_set_id,
        rule_set_revision=authority.rule_set_revision,
        protocol_version_id=authority.protocol_version_id,
        study_phase=rule_set.study_phase,
        components=frozen_components,
        facts=frozen_facts,
        locators=frozen_locators,
        documents=documents,
        frozen_input_sha256=predicate_binding_frozen_input_sha256(
            authority=authority,
            episode=episode,
            rule_set_id=authority.rule_set_id,
            rule_set_revision=authority.rule_set_revision,
            protocol_version_id=authority.protocol_version_id,
            study_phase=rule_set.study_phase,
            components=frozen_components,
            facts=frozen_facts,
            locators=frozen_locators,
            documents=documents,
        ),
    )
