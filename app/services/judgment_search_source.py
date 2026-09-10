"""研究者书面判断检索范围的只读构建器（CANDIDATE 检索前置，未接产品临床链路）。

``build_judgment_search_scope`` 从既有仓储与校验器只读构建冻结检索页域：

1. 活动权威核对：复用 ``FactAuthorityValidator`` 完整校验快照、审核节点
   修订号、规则作用域及成对活动指针，陈旧权威直接拒绝，不另写简化校验。
2. requirement 归属：``list_expectation_templates``（既有已验证边界）按权威元组的
   ``rule_set_id + rule_set_revision`` 取冻结期望模板，requirement 必须恰好命中
   一条；缺失、跨规则集或重复命中均为有界错误。
3. 完整修订闭包由 ``CompleteEvidenceProcessingRevisionRepository.get`` 在读取时
   全量执行（页清单精确等于每个快照成员资料版本的持久化页集合、逐页终态成功
   页产物 + 终态成功 OCR 页、逐资料链头元数据、逐页风险扫描、定位闭包、清单与
   完成清单哈希重算）。本构建器**不复刻**该大校验器，也不因名字假设完整；
   上述保证以仓储代码为准（``_verify_page_closure`` / ``_verify_terminal_successful_pages``
   等），读取即验证。
4. 逐清单页经 ``PageArtifactRepository.get`` 解码页产物并做防御性身份再核对
   （资料版本/页码与清单条目一致、页图哈希非空）。缺失页图或外来身份产生有界
   错误，绝不虚构哈希、绝不静默省略页。
5. 范围成员与哈希全部来自 ``app.domain.contracts.judgment_search`` 的稳定排序与
   内容寻址函数；范围覆盖**当前活动完整修订的全部清单页**——不做任何页状态、
   日期、文件类别或对账采信过滤。

``prepare_judgment_search_target`` 在同一只读边界上追加目标准备：返回
``(scope, target_text)``——scope 每次准备都经 ``build_judgment_search_scope``
重新完整校验（无缓存可信标记），target 是**当前已发布来源**的规范化 JSON：

- 只包含精确命中的父规则（含 ``source_text`` 逐字原文）与所选子组件
  （title/expression/exception_expression）、该条 ``EvidenceRequirement`` 全文
  （含 description）与模板/规则集/方案版本身份及模板投影哈希；绝不携带完整
  RuleSet/ClausePack。
- description 只是指向原文的指针：已发布 description（例如"研究者评估上述疾病
  是否可能影响受试者的疗效和安全性判断"这类措辞）不是权限，不得据此硬编码任何
  研究、疾病或 ID；target 原样保留发布内容，不概括、不改写、不推断省略的阈值
  或日期，当前或未来模型输出都不是权威。
- 一致性按显式 ID 核对（不做标题匹配），并逐条复用 ``save_expectation_templates``
  写边界的同一语义合同做只读重核：(a) 模板与已发布 requirement 的资料语义
  **全量**一致——due_stage、fact_type、required_source_types（集合语义）、
  requires_contemporaneous_objective_source、allows_screening_record_transcription
  与 description 全部相等，绝不只比部分字段，也绝不把分歧的模板字段从 target
  里悄悄省略；(b) 模板所引审核节点必须真实存在、命名空间正确、属于规则集的
  方案版本/期别、节点 stage 等于到期阶段且 requirement 确在
  ``due_requirement_ids`` 中（``get_workflow_stages_by_ids``/原生仓储读取，
  不发明节点、不忽略缺失节点）；(c) 选中路径做**精确结构相等**三重核对——
  已加载 RuleSet 内的父规则必须逐字段等于 ``get_rule`` 结果、其中的所选组件
  必须等于 ``get_rule_component`` 结果、组件内的该条 requirement 必须等于
  ``get_evidence_requirement`` 结果，规范化行与包围载荷的自洽漂移一律拒绝。
  (c) 只验证选中路径，不声称覆盖整棵规则树；任一不符即拒绝，绝无
  description-only 降级。
- 支持边界：当前只支持**子规则来源** requirement。流程必做项目目录来源
  （``rule_component_id=None``）的已发布原生原文不在规则集与方案来源记录行内
  （``ProtocolSourceRecord`` 仅含定位与哈希，无逐字文本），其精确解析属方案
  文档读取链路——本函数对其显式抛有界不支持错误，**绝不虚构父组件**，
  也绝不以 description 顶替原文。

诚实边界：

- 本构建器只证明「活动修订供给了这些页」，**不证明也不声明**临床要求的全部外部
  资料都已供给；``JudgmentSearchCoverageSummary.source_scope_verified`` 恒为
  ``False``。目标准备同样不是跨引用已全部语义消解的证明，不是 D2 缺失生产者，
  也不是任何临床批准。
- 本模块只读：不写库、不提交、不调用模型、不产生时间戳；不输出
  professional_judgment 缺口或任何临床采信结论。
- 完整修订的仓储闭包保证清单页均为终态成功页产物 + 终态成功 OCR 页
  （含有效渲染页图）；因此「OCR 失败但有渲染图」的页在当前完整修订合同下
  不会出现。本构建器不按状态过滤——若未来修订合同允许此类页，只要页产物
  身份一致且携带真实页图哈希，本构建器原样纳入范围。
"""
from __future__ import annotations

import json

from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.judgment_search import (
    JudgmentSearchPageIdentity,
    JudgmentSearchScope,
    judgment_search_scope_sha256,
)
from app.domain.contracts.ocr import PageArtifact
from app.storage.ocr_repositories import PageArtifactRepository
from app.storage.models import WorkflowStageRecord
from app.storage.repositories import (
    get_evidence_requirement,
    get_rule,
    get_rule_component,
    get_rule_set,
    get_workflow_stages_by_ids,
    list_expectation_templates,
)
from app.storage.fact_authority import FactAuthorityError, FactAuthorityValidator

__all__ = [
    "JudgmentSearchSourceError",
    "build_judgment_search_scope",
    "prepare_judgment_search_target",
    "scope_page_identity",
]


class JudgmentSearchSourceError(ValueError):
    """来源范围构建的有界错误：活动指针、requirement 模板或页身份不一致。

    活动权威校验发现的来源闭包错误由本异常保留 cause 链；其后仓储读取的
    编解码与闭包错误原样传播。本模块不吞错、不降级、不省略页。
    """


def scope_page_identity(
    entry: EvidenceProcessingRevisionPage,
    artifact: PageArtifact,
) -> JudgmentSearchPageIdentity:
    """把一条清单页与解码后的页产物绑定为范围页身份（纯函数）。

    防御性再核对：完整修订读取闭包已验证页产物存在、终态成功与归属一致；
    此处按同一事实再核对一次（不信任任何单一读取路径），页图哈希缺失或
    外来身份一律有界报错，绝不虚构哈希或静默省略页。不读取、不依赖
    ``entry.status``——范围不按页状态过滤。
    """
    if (
        artifact.page_artifact_id,
        artifact.source_document_version_id,
        artifact.page_number,
    ) != (entry.page_artifact_id, entry.source_document_version_id, entry.page_number):
        raise JudgmentSearchSourceError(
            f"页产物 {artifact.page_artifact_id} 与清单条目 {entry.entry_id} 的"
            "资料版本/页码不一致：来源页身份冲突，拒绝纳入范围"
        )
    if not artifact.page_image_sha256:
        raise JudgmentSearchSourceError(
            f"清单条目 {entry.entry_id}（{entry.source_document_version_id} 第"
            f"{entry.page_number} 页）的页产物缺少页图哈希：拒绝虚构哈希或"
            "静默省略该页"
        )
    return JudgmentSearchPageIdentity(
        source_document_version_id=entry.source_document_version_id,
        page_artifact_id=entry.page_artifact_id,
        page_number=entry.page_number,
        page_image_sha256=artifact.page_image_sha256,
    )


def _require_nonblank_requirement_id(requirement_id: str) -> str:
    stripped = requirement_id.strip()
    if not stripped:
        raise JudgmentSearchSourceError("requirement_id 不得为空白")
    return stripped


def build_judgment_search_scope(
    session,
    authority: FactAuthority,
    requirement_id: str,
) -> JudgmentSearchScope:
    """只读构建冻结检索页域（见模块 docstring 的核对顺序与诚实边界）。"""
    requirement_id = _require_nonblank_requirement_id(requirement_id)

    try:
        revision = FactAuthorityValidator(session).validate_and_get_revision(authority)
    except FactAuthorityError as exc:
        raise JudgmentSearchSourceError(
            f"审核节点作用域、活动指针或修订号不一致，无法核对检索范围：{exc}"
        ) from exc

    templates = [
        template
        for template in list_expectation_templates(
            session, authority.rule_set_id, authority.rule_set_revision
        )
        if template.requirement_id == requirement_id
    ]
    if len(templates) != 1:
        raise JudgmentSearchSourceError(
            f"requirement {requirement_id} 在规则集 {authority.rule_set_id}"
            f" revision {authority.rule_set_revision} 的冻结期望模板命中 "
            f"{len(templates)} 条（缺失、跨规则集或重复），拒绝构建范围"
        )

    if (
        revision.evidence_processing_revision_id
        != authority.complete_processing_revision_id
        or revision.project_id != authority.project_id
        or revision.subject_id != authority.subject_id
        or revision.review_episode_id != authority.review_episode_id
        or revision.evidence_snapshot_id != authority.evidence_snapshot_v2_id
    ):
        raise JudgmentSearchSourceError(
            "FactAuthority 与完整修订作用域不一致，拒绝跨节点构建范围"
        )
    if not revision.manifest:
        raise JudgmentSearchSourceError(
            "完整修订清单为空，无法构建非空检索页域"
        )

    artifact_repository = PageArtifactRepository(session)
    pages = [
        scope_page_identity(entry, artifact_repository.get(entry.page_artifact_id))
        for entry in revision.manifest
    ]
    # 合同要求成员按 (资料版本, 页工件, 页码) 确定性排序；清单序保证文档连续、
    # 页码升序，但页工件 ID 不保证随页码单调，这里按合同序显式排序。
    pages.sort(key=lambda page: page.order_key)
    return JudgmentSearchScope(
        authority=authority,
        requirement_id=requirement_id,
        pages=tuple(pages),
        scope_sha256=judgment_search_scope_sha256(
            authority=authority,
            requirement_id=requirement_id,
            pages=tuple(pages),
        ),
    )


def prepare_judgment_search_target(
    session,
    authority: FactAuthority,
    requirement_id: str,
) -> tuple[JudgmentSearchScope, str]:
    """只读准备 ``(scope, target_text)``：冻结页域 + 当前已发布来源的规范化目标。

    scope 每次准备都经 ``build_judgment_search_scope`` 完整重校验（无缓存可信
    标记，不另做整修订重读）。target 只含精确命中的父规则逐字原文、所选子组件、
    该条已发布 requirement 全文与模板/规则集/方案身份——详见模块 docstring 的
    一致性核对、支持边界与诚实边界。返回的 target 是后续候选读器的检索对象，
    不是跨引用已全部语义消解的证明。
    """
    requirement_id = _require_nonblank_requirement_id(requirement_id)
    scope = build_judgment_search_scope(session, authority, requirement_id)

    rule_set = get_rule_set(session, authority.rule_set_id, authority.rule_set_revision)
    if rule_set.protocol_version_id != authority.protocol_version_id:
        raise JudgmentSearchSourceError(
            f"规则集 {rule_set.rule_set_id} revision {rule_set.revision} 的方案版本"
            f" {rule_set.protocol_version_id} 与权威元组 "
            f"{authority.protocol_version_id} 不一致，拒绝准备目标"
        )
    templates = [
        template
        for template in list_expectation_templates(
            session, authority.rule_set_id, authority.rule_set_revision
        )
        if template.requirement_id == requirement_id
    ]
    if len(templates) != 1:
        raise JudgmentSearchSourceError(
            f"requirement {requirement_id} 的冻结期望模板命中 {len(templates)} 条，"
            "拒绝准备目标"
        )
    template = templates[0]
    published = get_evidence_requirement(
        session, authority.rule_set_id, authority.rule_set_revision, requirement_id
    )
    # 模板↔已发布 requirement 语义全量一致：逐字复用 save_expectation_templates
    # 写边界的同一语义合同（due_stage/fact_type/required_source_types 集合语义/
    # 两个来源标志/description），此处只读重核；分歧绝不从 target 中悄悄省略。
    expected_semantics = {
        "due_stage": published.due_stage,
        "fact_type": published.fact_type,
        "required_source_types": sorted(set(published.required_source_types)),
        "requires_contemporaneous_objective_source": (
            published.requires_contemporaneous_objective_source
        ),
        "allows_screening_record_transcription": (
            published.allows_screening_record_transcription
        ),
        "description": published.description,
    }
    actual_semantics = {
        "due_stage": template.due_stage,
        "fact_type": template.fact_type,
        "required_source_types": sorted(set(template.required_source_types)),
        "requires_contemporaneous_objective_source": (
            template.requires_contemporaneous_objective_source
        ),
        "allows_screening_record_transcription": (
            template.allows_screening_record_transcription
        ),
        "description": template.description,
    }
    if actual_semantics != expected_semantics or template.study_phase != rule_set.study_phase:
        raise JudgmentSearchSourceError(
            f"requirement {requirement_id} 的冻结期望模板与已发布要求语义不一致，"
            "拒绝以模板顶替发布内容"
        )
    if published.rule_component_id is None:
        # 流程必做来源在进入规则工作流核对前即显式拒绝：其原生原文不在规则集与
        # 方案来源记录行内，任何工作流核对都无法替代逐字原文解析。
        raise JudgmentSearchSourceError(
            f"requirement {requirement_id} 为流程必做项目目录来源"
            f"（procedure_catalog_item_id={published.procedure_catalog_item_id}）："
            "其已发布原生原文不在规则集与方案来源记录行内，精确解析属方案文档"
            "读取链路，当前尚不支持；拒绝虚构父组件或以 description 顶替原文"
        )
    # 审核节点核对（与写边界同语义的只读重核）：实存、命名空间、方案版本/期别、
    # 节点阶段等于到期阶段、requirement 确在 due_requirement_ids。
    if not template.workflow_stage_id.startswith(
        f"{authority.rule_set_id}:{authority.rule_set_revision}:"
    ):
        raise JudgmentSearchSourceError(
            f"requirement {requirement_id} 的冻结期望模板所引审核节点不属于该"
            "规则集 revision，拒绝准备目标"
        )
    stage_row = session.get(WorkflowStageRecord, template.workflow_stage_id)
    if stage_row is None:
        raise JudgmentSearchSourceError(
            f"requirement {requirement_id} 的冻结期望模板所引审核节点"
            f" {template.workflow_stage_id} 不存在，拒绝准备目标"
        )
    if (
        stage_row.protocol_version_id != rule_set.protocol_version_id
        or stage_row.study_phase != rule_set.study_phase
    ):
        raise JudgmentSearchSourceError(
            f"requirement {requirement_id} 的冻结期望模板所引审核节点不属于该"
            "规则集的方案版本/期别，拒绝准备目标"
        )
    stages = get_workflow_stages_by_ids(session, [template.workflow_stage_id])
    stage_contract = stages.get(template.workflow_stage_id)
    if stage_contract is None:
        raise JudgmentSearchSourceError(
            f"审核节点 {template.workflow_stage_id} 行存在但合同无法解码，拒绝准备目标"
        )
    if (
        requirement_id not in stage_contract.due_requirement_ids
        or stage_contract.stage != template.due_stage
    ):
        raise JudgmentSearchSourceError(
            f"requirement {requirement_id} 未在所引审核节点按期到期，拒绝准备目标"
        )

    component = get_rule_component(
        session, authority.rule_set_id, authority.rule_set_revision,
        published.rule_component_id,
    )
    rule = get_rule(
        session, authority.rule_set_id, authority.rule_set_revision,
        component.parent_rule_id,
    )
    if component.rule_component_id not in {
        item.rule_component_id for item in rule.components
    }:
        raise JudgmentSearchSourceError(
            f"所选组件 {component.rule_component_id} 不属于父规则 {rule.rule_id}，"
            "拒绝准备目标"
        )
    if rule.study_phase != rule_set.study_phase:
        raise JudgmentSearchSourceError(
            f"父规则 {rule.rule_id} 期别与规则集期别不一致，拒绝准备目标"
        )
    # 选中路径精确结构相等（三重）：规范化行与包围载荷的自洽漂移一律拒绝。
    # 只验证选中路径本身，不声称覆盖整棵规则树。
    ruleset_rule = next(
        (item for item in rule_set.rules if item.rule_id == rule.rule_id), None
    )
    if ruleset_rule is None or ruleset_rule != rule:
        raise JudgmentSearchSourceError(
            f"已加载规则集内的父规则 {rule.rule_id} 与已发布规则行不一致"
            "（载荷漂移），拒绝准备目标"
        )
    component_in_rule = next(
        (
            item for item in rule.components
            if item.rule_component_id == component.rule_component_id
        ),
        None,
    )
    if component_in_rule is None or component_in_rule != component:
        raise JudgmentSearchSourceError(
            f"父规则 {rule.rule_id} 内的所选组件 {component.rule_component_id} "
            "与已发布组件行不一致（载荷漂移），拒绝准备目标"
        )
    requirement_in_component = next(
        (
            item for item in component.evidence_requirements
            if item.requirement_id == requirement_id
        ),
        None,
    )
    if requirement_in_component is None or requirement_in_component != published:
        raise JudgmentSearchSourceError(
            f"组件 {component.rule_component_id} 内的资料要求 {requirement_id} "
            "与已发布要求行不一致（载荷漂移），拒绝准备目标"
        )

    target = {
        "identity": "judgment_search_target/v1",
        "rule_set": {
            "rule_set_id": rule_set.rule_set_id,
            "revision": rule_set.revision,
            "protocol_version_id": rule_set.protocol_version_id,
            "study_phase": rule_set.study_phase.value,
        },
        "template": {
            "template_id": template.template_id,
            "projection_sha256": template.projection_sha256,
            "requirement_id": template.requirement_id,
            "due_stage": template.due_stage.value,
            "study_phase": template.study_phase.value,
            "workflow_stage_id": template.workflow_stage_id,
            "fact_type": template.fact_type,
        },
        "rule": {
            "rule_id": rule.rule_id,
            "official_code": rule.official_code,
            "kind": rule.kind.value,
            "study_phase": rule.study_phase.value,
            # 父规则已发布原文，逐字保留：不概括、不改写、不推断省略的阈值/日期。
            "source_text": rule.source_text,
        },
        "component": {
            "rule_component_id": component.rule_component_id,
            "parent_rule_id": component.parent_rule_id,
            "display_code": component.display_code,
            "title": component.title,
            "expression": component.expression.model_dump(mode="json"),
            "exception_expression": (
                component.exception_expression.model_dump(mode="json")
                if component.exception_expression is not None
                else None
            ),
        },
        "requirement": published.model_dump(mode="json"),
    }
    # 规范化 JSON：sort_keys 确定性序列化，随实际目标内容确定性变化。
    target_text = json.dumps(
        target, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return scope, target_text
