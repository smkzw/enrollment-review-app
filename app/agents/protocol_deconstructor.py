"""Bounded, same-session adapter for the protocol deconstruction Agent."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Literal, Protocol

from pydantic import Field, ValidationError

from app.domain.contracts.agent_io import (
    EvidenceRequirementDraft,
    ParentRuleCatalogMapping,
    ProtocolDeconstructionDraft,
    ProtocolDeconstructionInput,
    ProtocolMetadataDraft,
    ProtocolSemanticDeconstructionCandidate,
    ProtocolSemanticRuleRepair,
    SemanticEvidenceRequirement,
    SemanticRule,
    SemanticRuleComponent,
    ProcedureCatalogMapping,
    RuleComponentDraft,
)
from app.domain.contracts.agents import PromptVersion
from app.domain.contracts.common import VersionedModel
from app.domain.contracts.enums import AgentNode, ReviewStage, RuleKind
from app.domain.contracts.normalization import CoverageSummary, UnresolvedItem
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.domain.contracts.protocol_metadata import InterpretationConflict
from app.domain.contracts.rules import (
    EvidenceRequirement,
    Rule,
    RuleComponent,
    WorkflowStage,
    iter_atomic_predicates,
)
from app.protocols.deconstruction_gate import (
    ProtocolDeconstructionGate,
    ProtocolDeconstructionGateResult,
    ProtocolGateIssue,
)


class ProtocolAgentResponse(VersionedModel):
    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class ProtocolAgentCallError(RuntimeError):
    """Transport failure that retains the logical session for audit recovery."""

    def __init__(self, session_id: str, message: str):
        super().__init__(message)
        self.session_id = session_id


class ProtocolAgentTransport(Protocol):
    def start(self, *, prompt: str) -> ProtocolAgentResponse: ...

    def continue_session(
        self, *, session_id: str, prompt: str
    ) -> ProtocolAgentResponse: ...


class ProtocolDeconstructionAttempt(VersionedModel):
    # 实际上限由 ProtocolDeconstructorRunner 的结构修复和按冻结
    # 父规则数量计算的语义修复预算决定。运行记录不再复制一个
    # 会随预算演进而失效的静态上限。
    attempt: int = Field(ge=1)
    session_id: str = Field(min_length=1)
    raw_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: Literal["通过完整性检查", "需要定向修正", "输出格式无效", "会话异常"]
    draft_id: str | None = None
    issues: list[ProtocolGateIssue] = Field(default_factory=list)


class ProtocolDeconstructionRunResult(VersionedModel):
    status: Literal["可以进入审阅", "需要核对"]
    same_session_id: str = Field(min_length=1)
    attempts: list[ProtocolDeconstructionAttempt] = Field(min_length=1)
    final_draft: ProtocolDeconstructionDraft | None = None
    final_gate_result: ProtocolDeconstructionGateResult | None = None


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_SYSTEM_CONTRACT = (
    "你正在解构一份已确认期别的研究方案。只处理本次输入中的研究期别；"
    "不要解释或比较另一研究期别。官方父规则目录和基线及以前必做项目录均已冻结，"
    "不得增加、删除、合并或调换成员。复杂条款可拆成子组件，但父规则官方编号和数量"
    "必须保持不变。必须保留原文中的且/或/例外、研究者复合判断、指标、阈值、单位、"
    "每个原子条件的 predicate_id 在整份草稿中必须唯一；相同的研究者判断若分别属于"
    "多个子项，也要使用不同而稳定的 predicate_id，不得跨子项复用身份。"
    "随机/基线/筛选时间锚点和每一个访视实例。每个 RuleComponent 都会独立接受审核："
    "同一个排除触发条件中由‘且/同时’连接的必要条件必须保留在同一组件的 ALL 表达式中，"
    "不能拆成任一条件单独触发；由‘或/任一’连接的替代条件使用 ANY，或仅在每个分支本身"
    "就是完整独立触发条件时拆成多个组件。例外必须放入对应组件的 exception_expression，"
    "不能改写成普通触发条件。只引用 allowed_source_span_ids。"
    "你只输出 proposed_rules 及其语义组件、资料要求。每个子组件内的"
    "source_span_ids 只填直接支撑该子组件的来源，source_excerpts 中的每一项都必须是"
    "该子组件来源里逐字存在的连续片段；若子组件语义由不连续的上位限定语、并列分支和结尾"
    "共同构成，应按原文顺序填写多个片段，不得把不连续文字拼成方案中不存在的新句子；"
    "若编号子项继承父级引导段中的时间锚点、主语或触发限定语，source_span_ids 必须同时引用"
    "父级引导段和当前子项，source_excerpts 分别保存父级与子项逐字片段，谓词也用 source_clauses"
    "分别绑定这些片段；不得只引用子项后再把父级文字补写进摘录。"
    "括号内的除外、除非或例外只作用于括号紧邻的触发分支，不得复制到括号之后由‘或’"
    "连接的兄弟分支。若原文以‘N天/周/月/年内’直接限定既往事件，但未点名筛选、随机、"
    "基线、知情同意或首次给药等回溯锚点，不得自行猜测或省略时间范围，应放入 "
    "unresolved_items 等待确认。若‘N年内发生N次’本身就是触发条件，应在数值谓词中保留次数"
    "并用 occurrence_window 保存频率周期；若它是较宽病史条件括号内的定义或示例，保留布尔"
    "病史谓词，并用 occurrence_window.minimum_count 与 duration 保存最小次数和周期。不得把"
    "频率定义误报为回溯锚点不明。若原文以‘N周≥N天’或‘每周至少N天’定义发生天数，"
    "数值谓词保留天数阈值和‘天/日’单位，并用 occurrence_window.duration 保留观察周期。"
    "频次定义只绑定其直接限定的事件或示例分支，不得套到同一父条款的其他兄弟病史。"
    "‘计划在治疗期间或研究完成后"
    "N周内’等未来计划应拆分并列分支；治疗期间或研究期间的分支分别用 prospective_period "
    "保存 treatment_period 或 study_period；研究完成后或末次给药后的分支分别用 "
    "prospective_window 保存 study_completion_date、last_dose_date 或 "
    "study_drug_administration_date 及原文时长，其中原文未指明首次或末次、"
    "仅写‘研究药物给药后’时才用 study_drug_administration_date，不得误写成"
    "回溯锚点待确认。"
    "不得把同一父规则的全部来源不加区分地套给每个子组件。父规则映射、流程必做项目、"
    "审核节点、方案身份、rule_id、parent_rule_id、rule_component_id、display_code、"
    "requirement_id、rule_component_id 绑定、规则类型和研究期别均由系统确定性装配，"
    "不得在语义草稿中重复生成。"
    "每个数值谓词必须在 source_term 仅填写原文中的指标名称，unit 保留原文单位；"
    "若多个阈值共用前置指标名称，每个阈值谓词的 source_clauses 都必须包含一个带该指标名称的"
    "逐字片段和其自身阈值片段，使该阈值仍能独立核对；"
    "非数值谓词省略 source_term，不要用它重复整个原文子句。"
    "每个原子谓词必须用 source_clause 逐字复制直接支撑该谓词的最小连续原文子句；"
    "若语义由不连续的上位限定语、并列分支和结尾共同构成，改用 source_clauses 依原文顺序"
    "列出多个逐字片段，不得把不连续文字拼成方案中不存在的新句子；source_clause 与"
    "source_clauses 只能使用一种。"
    "评分、分级等无量纲数值显式填 unitless。time_constraint 是 expression 中与 predicate"
    "并列的字段，不得放入 predicate 内；筛选时、基线时等审核节点用资料要求的 due_stage "
    "表达。同一条件在筛选和基线都要核对时，只保留一个原子条件，并分别建立 due_stage 为"
    "screening 和 baseline 的资料要求；不得为表示审核阶段而复制原子条件。time_constraint "
    "主要用于‘随机前/基线前/筛选前/首次给药前’等相对日期窗；首次给药前必须使用"
    "first_dose_date，不能用笼统的 event_date。只能依据该谓词的逐字原文片段设置时间锚点和"
    "时间窗，不得把同一子规则中其他分支的‘随机前’套入当前谓词，也不得为‘研究期间计划/需要’"
    "凭空添加天数或日期锚点。时间窗必须使用 upper_bound/lower_bound 并保留原文的 day/week/month/year"
    "单位，不得把周、月、年换算成 *_days；‘前N周/月内’不要额外输出原文未写的零日下界。"
    "exception_expression 只能作为子组件字段，不得放入 expression 内；逻辑操作符只用 all/any/not。"
    "资料要求的 due_stage 必须依据当前条款逐字可见的审核时点或冻结流程确定，不得为了"
    "‘再次确认’而把每个条件惯性复制到筛选、导入和基线；原文只要求一个节点时只建立一个"
    "资料要求。若某阶段没有必做项目录条目但条款明确写有该阶段，仍保留该 due_stage，系统会"
    "确定性建立审核节点。包含‘随机前N时间内或计划在研究期间’的并列条款必须拆成各自完整"
    "分支：回溯分支使用 time_constraint，未来计划分支使用 prospective_period。"
    "资料要求 description 只描述需要核对的资料或需要完成的评估，不得预设审核结果；"
    "不要写‘确认不存在’‘确认无异常’‘确认符合’‘确认不触发’等结论性措辞。"
    "若原文允许使用‘N天/周/月/年内的某项检查结果’，这是资料时效而不是"
    "临床事件回溯：必须为该项检查在原文指定的每个 due_stage 分别建立资料要求，"
    "并用 source_validity_window 保留原文时长和 day/week/month/year 单位；不得把它写成"
    "谓词 time_constraint，也不得用同组件的其他检查资料代替。"
    "JSON 实例不得复制 Schema 的 $defs、properties "
    "等定义字段；ALL/ANY 必须至少"
    "包含两个子表达式，只有一个子表达式时直接输出该子表达式。"
    "输出必须是一个严格符合指定 JSON Schema 的 JSON 对象，不要输出 Markdown、说明、"
    "日志或额外文字。"
)


def protocol_prompt_template_sha256(prompt_template: str) -> str:
    """Hash every behavioral instruction, not only the caller's prefix."""
    return _sha256(prompt_template.strip() + "\n\n" + _SYSTEM_CONTRACT)


def _compact_schema() -> str:
    return json.dumps(
        ProtocolSemanticDeconstructionCandidate.model_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _compact_repair_schema() -> str:
    return json.dumps(
        ProtocolSemanticRuleRepair.model_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def build_protocol_deconstruction_prompt(
    source_input: ProtocolDeconstructionInput,
    *,
    prompt_template: str,
    requested_rule_codes: Sequence[str] | None = None,
) -> str:
    """Build one auditable prompt from frozen input, without hidden free text."""
    payload = source_input.model_dump(mode="json")
    batch_instruction = ""
    if requested_rule_codes is not None:
        batch_instruction = (
            "\n系统将按冻结目录顺序分批接收语义结果。本次 proposed_rules 必须且只能"
            f"返回这些官方父规则：{list(requested_rule_codes)}；保持给定顺序。"
            "这是传输分批，不是删除其他父规则；后续批次必须沿用相同 candidate_id。\n"
        )
    return (
        f"{prompt_template.strip()}\n\n"
        f"{_SYSTEM_CONTRACT}\n\n"
        f"{batch_instruction}"
        f"输入：{json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n\n"
        f"输出结构：{_compact_schema()}"
    )


def _next_batch_prompt(
    rule_codes: Sequence[str],
    *,
    batch_number: int,
    batch_total: int,
    candidate_id: str,
) -> str:
    return (
        f"继续返回冻结目录的第 {batch_number}/{batch_total} 批语义结果。"
        f"candidate_id 必须继续使用 {candidate_id!r}；proposed_rules 必须且只能"
        f"按顺序返回 {list(rule_codes)}。不得重复前批，不得提前返回后批，不得省略本批父规则。"
        "输出完整 JSON 对象，不要附加说明。输出结构："
        + _compact_schema()
    )


def _batch_schema_repair_prompt(
    rule_codes: Sequence[str],
    *,
    candidate_id: str | None,
    problem: str,
) -> str:
    identity = (
        f"candidate_id 必须继续使用 {candidate_id!r}；" if candidate_id else ""
    )
    return (
        "本批输出无法按冻结目录合并。"
        + identity
        + f"proposed_rules 必须且只能按顺序返回 {list(rule_codes)}。"
        + f"具体问题：{problem[:12000]}。"
        + "仅修正本批 JSON 结构和列出的父规则，不要返回其他批次或说明文字。输出结构："
        + _compact_schema()
    )


def _repair_prompt(
    issues: Sequence[ProtocolGateIssue],
    *,
    attempt: int,
    parsed_draft_available: bool,
    replacement_rule_codes: Sequence[str] = (),
) -> str:
    repair_items = [
        {
            "问题代码": issue.issue_code,
            "问题": issue.problem,
            "影响范围": issue.affected_refs,
            "只允许修正": issue.repair_scope,
            "下一步": issue.next_action,
        }
        for issue in issues
    ]
    if parsed_draft_available and replacement_rule_codes:
        instruction = (
            "已有完整语义草稿通过结构解析。本次只能返回 ProtocolSemanticRuleRepair，"
            "candidate_id 必须与前稿一致；replacement_rules 必须且只能完整替换以下"
            "父规则。replacement_unresolved_items 和 replacement_structural_warnings 也只填本次父规则"
            "修订后仍然真实存在的事项；已解决的不得残留，非本次父规则的不得重复返回。"
            f"官方父规则：{list(replacement_rule_codes)}。不要返回整份草稿，不要返回未列出的父规则；"
            "系统会保持其他父规则完全不变。"
        )
    else:
        instruction = (
            "前一响应从未成功解析为完整草稿，因此不存在可保留的空草稿。"
            "请使用原会话中的冻结目录和方案原文，重新输出包含全部官方父规则"
            "及全部子规则的完整语义草稿；严禁输出空列表、错误占位符或部分草稿。"
        )
    schema_suffix = (
        "\n局部修正输出结构：" + _compact_repair_schema()
        if parsed_draft_available and replacement_rule_codes
        else ""
    )
    return (
        f"这是同一会话的第 {attempt} 次定向修正。"
        + instruction
        + "不得通过删除目录项、改官方编号、改来源或改访视实例规避问题。"
        "重新输出完整 JSON 对象，不要附加说明："
        + json.dumps(repair_items, ensure_ascii=False, sort_keys=True)
        + schema_suffix
    )


def _validation_error_summary(exc: ValidationError) -> str:
    """Preserve every actionable schema error without echoing huge inputs."""

    errors = []
    for error in exc.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in error["loc"])
        errors.append(f"{location}: {error['msg']}")
    return "；".join(errors)


def _normalize_model_json(value):
    """Apply only semantics-preserving JSON-instance normalization."""

    if isinstance(value, list):
        return [_normalize_model_json(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized = {
        key: _normalize_model_json(item)
        for key, item in value.items()
        if not (key == "$defs" and item == {})
    }
    expression = normalized.get("expression")
    if (
        isinstance(expression, dict)
        and "exception_expression" in expression
        and normalized.get("exception_expression") is None
    ):
        normalized["exception_expression"] = expression.pop(
            "exception_expression"
        )
    if normalized.get("operator") == "and":
        normalized["operator"] = "all"
    elif normalized.get("operator") == "or":
        normalized["operator"] = "any"
    numeric_value = normalized.get("value")
    source_clause = normalized.get("source_clause")
    source_clauses = normalized.get("source_clauses")
    if (
        isinstance(source_clause, str)
        and isinstance(source_clauses, list)
        and source_clause in source_clauses
    ):
        normalized["source_clause"] = None
    if (
        "comparator" in normalized
        and isinstance(numeric_value, (int, float))
        and not isinstance(numeric_value, bool)
        and not normalized.get("unit")
    ):
        normalized["unit"] = "__missing_from_agent__"
    if normalized.get("lower_bound_days") == 0:
        normalized["lower_bound_days"] = None
    if (
        set(normalized) == {"kind", "operator", "children"}
        and normalized.get("kind") == "logical"
        and normalized.get("operator") in {"all", "any"}
        and isinstance(normalized.get("children"), list)
        and len(normalized["children"]) == 1
    ):
        return normalized["children"][0]
    return normalized


_STAGE_DISPLAY_NAMES = {
    ReviewStage.PRE_SCREENING: "预筛选审核",
    ReviewStage.SCREENING: "筛选期审核",
    ReviewStage.RUN_IN: "筛选/导入期审核",
    ReviewStage.BASELINE: "基线审核",
}


_RULE_KIND_BY_PREFIX = {
    "IN": RuleKind.INCLUSION,
    "EX": RuleKind.EXCLUSION,
}


def _neutral_evidence_description(
    description: str,
    *,
    fact_type: str,
    due_stage: ReviewStage,
) -> str:
    if re.search(
        r"(?:确认|证明|判定|确保).{0,80}"
        r"(?:不存在|无异常|无不可接受|符合|满足|不符合|触发|未触发|排除)",
        description,
    ):
        return f"{_STAGE_DISPLAY_NAMES[due_stage]}：核对{fact_type}"
    return description


def _component_display_code(official_code: str, index: int, total: int) -> str:
    if total == 1:
        return official_code
    suffix = chr(ord("a") + index) if index < 26 else f"-{index + 1:02d}"
    return f"{official_code}{suffix}"


def _locator_projection(text: str) -> tuple[str, list[int]]:
    projected: list[str] = []
    indexes: list[int] = []
    for index, original in enumerate(text):
        for char in unicodedata.normalize("NFKC", original).lower():
            if char.isspace() or unicodedata.category(char).startswith("P"):
                continue
            projected.append(char)
            indexes.append(index)
    return "".join(projected), indexes


def _recover_exact_excerpt(excerpt: str, sources: Sequence[str]) -> str:
    """Recover original characters only when a punctuation-insensitive hit is unique."""

    for source in sources:
        if excerpt in source:
            return excerpt
    projected_excerpt, _ = _locator_projection(excerpt)
    if not projected_excerpt:
        return excerpt
    matches: list[tuple[str, int, int]] = []
    for source in sources:
        projected_source, indexes = _locator_projection(source)
        start = projected_source.find(projected_excerpt)
        while start >= 0:
            end = start + len(projected_excerpt)
            matches.append((source, indexes[start], indexes[end - 1] + 1))
            start = projected_source.find(projected_excerpt, start + 1)
    if len(matches) != 1:
        return excerpt
    source, start, end = matches[0]
    return source[start:end]


def _recover_exact_fragments(excerpt: str, sources: Sequence[str]) -> list[str]:
    """Split a fabricated shared-prefix clause only when two exact pieces are unique."""

    recovered = _recover_exact_excerpt(excerpt, sources)
    if any(recovered in source for source in sources):
        return [recovered]
    candidates: set[tuple[str, str]] = set()
    for split_at in range(2, len(excerpt) - 1):
        left, right = excerpt[:split_at], excerpt[split_at:]
        if len(right) < 2:
            continue
        for source in sources:
            left_start = source.find(left)
            while left_start >= 0:
                right_start = source.find(right, left_start + len(left))
                if right_start >= 0:
                    candidates.add((left, right))
                left_start = source.find(left, left_start + 1)
    if len(candidates) == 1:
        return list(next(iter(candidates)))
    return [excerpt]


def _visit_slug(visit: str) -> str:
    """访视实例的稳定短标识（前 8 位 SHA-256），用于多访视节点 id。"""
    import hashlib

    return hashlib.sha256(visit.encode("utf-8")).hexdigest()[:8]


def _hydrate_semantic_candidate(
    source_input: ProtocolDeconstructionInput,
    candidate: ProtocolSemanticDeconstructionCandidate,
) -> ProtocolDeconstructionDraft:
    """Assemble catalog-owned structure without asking the Agent to copy it."""

    semantic_rules_by_code = {
        rule.official_code: rule for rule in candidate.proposed_rules
    }
    expected_codes = [
        item.official_code
        for item in sorted(
            source_input.parent_rule_catalog.items,
            key=lambda value: value.position,
        )
    ]
    actual_codes = [rule.official_code for rule in candidate.proposed_rules]
    if actual_codes != expected_codes:
        raise ValueError(
            "语义草稿必须按冻结目录顺序逐项完整覆盖父规则；"
            f"应为 {expected_codes}，实际为 {actual_codes}"
        )
    source_materials = {
        material.source_span_id: material.text
        for material in source_input.source_materials
    }
    parent_mappings: list[ParentRuleCatalogMapping] = []
    proposed_rules: list[Rule] = []
    component_drafts: list[RuleComponentDraft] = []
    requirement_drafts: list[EvidenceRequirementDraft] = []
    stage_requirements: dict[ReviewStage, list[str]] = {}
    used_predicate_ids: set[str] = set()
    for item in sorted(
        source_input.parent_rule_catalog.items, key=lambda value: value.position
    ):
        semantic_rule = semantic_rules_by_code.get(item.official_code or "")
        rule_id = f"rule:{item.official_code}" if semantic_rule is not None else None
        parent_mappings.append(
            ParentRuleCatalogMapping(
                catalog_item_id=item.item_id,
                proposed_rule_id=(
                    rule_id if rule_id is not None else f"missing:{item.official_code}"
                ),
                source_span_ids=list(item.source_span_ids),
            )
        )
        if semantic_rule is None or item.official_code is None:
            continue
        components: list[RuleComponent] = []
        for component_index, semantic_component in enumerate(
            semantic_rule.components
        ):
            component_id = f"component:{item.official_code}:{component_index + 1:02d}"
            source_span_ids = list(semantic_component.source_span_ids)
            mapped_source_texts = [
                source_materials[span_id]
                for span_id in source_span_ids
                if span_id in source_materials
            ]
            source_excerpts = [
                _recover_exact_excerpt(excerpt, mapped_source_texts)
                for excerpt in semantic_component.source_excerpts
            ]
            expression = semantic_component.expression.model_copy(deep=True)
            exception_expression = (
                semantic_component.exception_expression.model_copy(deep=True)
                if semantic_component.exception_expression is not None
                else None
            )
            excerpt_sources = ["\n".join(source_excerpts)]
            for root in (expression, exception_expression):
                if root is None:
                    continue
                for predicate_index, predicate in enumerate(
                    iter_atomic_predicates(root), start=1
                ):
                    original_predicate_id = predicate.predicate_id
                    if original_predicate_id in used_predicate_ids:
                        candidate_id = (
                            f"{original_predicate_id}:{component_id}:"
                            f"{predicate_index:02d}"
                        )
                        suffix = 2
                        while candidate_id in used_predicate_ids:
                            candidate_id = (
                                f"{original_predicate_id}:{component_id}:"
                                f"{predicate_index:02d}:{suffix}"
                            )
                            suffix += 1
                        predicate.predicate_id = candidate_id
                    used_predicate_ids.add(predicate.predicate_id)
                    if predicate.source_clause:
                        fragments = _recover_exact_fragments(
                            predicate.source_clause, excerpt_sources
                        )
                        if len(fragments) == 1:
                            predicate.source_clause = fragments[0]
                        else:
                            predicate.source_clause = None
                            predicate.source_clauses = fragments
                    if predicate.source_clauses:
                        predicate.source_clauses = [
                            fragment
                            for clause in predicate.source_clauses
                            for fragment in _recover_exact_fragments(
                                clause, excerpt_sources
                            )
                        ]
            evidence_requirements = [
                EvidenceRequirement(
                    requirement_id=f"requirement:{component_id}:{index + 1:02d}",
                    rule_component_id=component_id,
                    fact_type=requirement.fact_type,
                    required_source_types=requirement.required_source_types,
                    allows_screening_record_transcription=(
                        requirement.allows_screening_record_transcription
                    ),
                    requires_contemporaneous_objective_source=(
                        requirement.requires_contemporaneous_objective_source
                    ),
                    due_stage=requirement.due_stage,
                    source_validity_window=requirement.source_validity_window,
                    description=_neutral_evidence_description(
                        requirement.description,
                        fact_type=requirement.fact_type,
                        due_stage=requirement.due_stage,
                    ),
                )
                for index, requirement in enumerate(
                    semantic_component.evidence_requirements
                )
            ]
            component = RuleComponent(
                rule_component_id=component_id,
                parent_rule_id=rule_id,
                display_code=_component_display_code(
                    item.official_code,
                    component_index,
                    len(semantic_rule.components),
                ),
                title=semantic_component.title,
                expression=expression,
                exception_expression=exception_expression,
                evidence_requirements=evidence_requirements,
            )
            components.append(component)
            draft_component_id = f"draft-component:{component_id}"
            component_drafts.append(
                RuleComponentDraft(
                    draft_component_id=draft_component_id,
                    parent_official_code=item.official_code,
                    proposed_component=component,
                    source_refs=source_span_ids,
                    source_excerpts=source_excerpts,
                )
            )
            for requirement in component.evidence_requirements:
                stage_requirements.setdefault(requirement.due_stage, []).append(
                    requirement.requirement_id
                )
                requirement_drafts.append(
                    EvidenceRequirementDraft(
                        draft_requirement_id=(
                            f"draft-requirement:{requirement.requirement_id}"
                        ),
                        draft_component_id=draft_component_id,
                        proposed_requirement=requirement,
                        source_refs=source_span_ids,
                    )
                )
        rule_source_text = "\n".join(
            source_materials[span_id]
            for span_id in item.source_span_ids
            if span_id in source_materials
        )
        proposed_rules.append(
            Rule(
                rule_id=rule_id,
                official_code=item.official_code,
                kind=_RULE_KIND_BY_PREFIX[item.official_code[:2]],
                source_text=rule_source_text or item.label,
                study_phase=source_input.selected_phase,
                components=components,
            )
        )

    procedure_mappings: list[ProcedureCatalogMapping] = []
    # 按（审核阶段, 访视实例）分组：同一阶段多个访视实例各自独立节点，
    # 不能由最后一个节点覆盖；单实例阶段保留兼容节点 id（stage:<stage>）。
    visit_groups: dict[tuple[str, str], list] = {}
    for item in sorted(
        source_input.required_procedure_catalog.items,
        key=lambda value: value.position,
    ):
        visit_groups.setdefault(
            (item.review_stage.value, item.visit_instance or ""), []
        ).append(item)
    stage_visit_count = {
        stage_value: sum(1 for group in visit_groups if group[0] == stage_value)
        for stage_value in {group[0] for group in visit_groups}
    }
    stage_first_node: dict[str, str] = {}
    workflow_stages: list[WorkflowStage] = []
    for (stage_value, visit), items in visit_groups.items():
        stage = ReviewStage(stage_value)
        multi_visit = stage_visit_count[stage_value] > 1
        node_id = (
            f"stage:{stage_value}"
            if not multi_visit
            else f"stage:{stage_value}:{_visit_slug(visit)}"
        )
        stage_first_node.setdefault(stage_value, node_id)
        display_name = _STAGE_DISPLAY_NAMES[stage]
        if multi_visit:
            display_name = f"{display_name}（{visit}）"
        node_requirement_ids: list[str] = []
        for item in items:
            if item.review_stage is None:
                raise ValueError(f"必做项目缺少审核阶段：{item.item_id}")
            requirement_id = f"requirement:{item.item_id}"
            requirement = EvidenceRequirement(
                requirement_id=requirement_id,
                procedure_catalog_item_id=item.item_id,
                fact_type="方案规定的访视操作或结果",
                due_stage=item.review_stage,
                description=f"{item.visit_instance}：{item.label}",
            )
            requirement_drafts.append(
                EvidenceRequirementDraft(
                    draft_requirement_id=f"draft-{requirement_id}",
                    procedure_catalog_item_id=item.item_id,
                    proposed_requirement=requirement,
                    source_refs=list(item.source_span_ids),
                )
            )
            procedure_mappings.append(
                ProcedureCatalogMapping(
                    catalog_item_id=item.item_id,
                    proposed_requirement_ids=[requirement_id],
                    proposed_workflow_stage_id=node_id,
                    source_span_ids=list(item.source_span_ids),
                )
            )
            node_requirement_ids.append(requirement_id)
        workflow_stages.append(
            WorkflowStage(
                workflow_stage_id=node_id,
                stage=stage,
                display_name=display_name,
                visit_instance=visit or None,
                due_requirement_ids=node_requirement_ids,
            )
        )

    # 组件资料要求（无访视实例）确定性挂到其 due_stage 的第一个访视节点。
    workflow_stages_by_id = {
        stage.workflow_stage_id: stage for stage in workflow_stages
    }
    for stage, requirement_ids in stage_requirements.items():
        node_id = stage_first_node.get(stage.value)
        if node_id is None:
            # A rule can explicitly name a review point even when the schedule
            # table has no standalone procedure row there. Preserve that point
            # instead of silently orphaning its evidence requirements.
            node_id = f"stage:{stage.value}"
            stage_first_node[stage.value] = node_id
            workflow_stages_by_id[node_id] = WorkflowStage(
                workflow_stage_id=node_id,
                stage=stage,
                display_name=_STAGE_DISPLAY_NAMES[stage],
                due_requirement_ids=[],
            )
        listed = workflow_stages_by_id[node_id]
        workflow_stages_by_id[node_id] = listed.model_copy(
            update={
                "due_requirement_ids": [
                    *listed.due_requirement_ids,
                    *requirement_ids,
                ]
            }
        )
    workflow_stages = list(workflow_stages_by_id.values())
    catalog_position = {
        item.item_id: item.position
        for item in source_input.required_procedure_catalog.items
    }
    # Visit grouping determines workflow nodes, but the immutable procedure
    # mapping list must retain the protocol catalog's source order.
    procedure_mappings.sort(key=lambda item: catalog_position[item.catalog_item_id])
    identity = source_input.identity_decision
    source_refs = list(source_input.allowed_source_span_ids)
    return ProtocolDeconstructionDraft(
        draft_id=f"draft:{candidate.candidate_id}",
        project_id=source_input.project_id,
        protocol_version_id=source_input.protocol_version_id,
        selected_phase=source_input.selected_phase,
        draft_revision=1,
        proposed_rules=proposed_rules,
        proposed_workflow_stages=workflow_stages,
        protocol_metadata=ProtocolMetadataDraft(
            protocol_code_candidate=identity.protocol_code,
            title_candidate=identity.project_name,
            version_candidate=identity.official_version,
            date_candidate=(
                str(identity.official_date.value) if identity.official_date else "未知"
            ),
            study_phase_candidates=[source_input.selected_phase.value],
            source_refs=source_refs,
        ),
        component_drafts=component_drafts,
        evidence_requirement_drafts=requirement_drafts,
        parent_catalog_mappings=parent_mappings,
        procedure_catalog_mappings=procedure_mappings,
        coverage=CoverageSummary(processed_refs=source_refs),
        structural_warnings=candidate.structural_warnings,
        unresolved_items=candidate.unresolved_items,
        source_refs=source_refs,
        created_by_agent_call_id=candidate.created_by_agent_call_id,
    )


def semantic_candidate_from_draft(
    draft: ProtocolDeconstructionDraft,
) -> ProtocolSemanticDeconstructionCandidate:
    """Recover the semantic layer needed to resume a persisted repair session."""

    mappings = {
        item.proposed_component.rule_component_id: item
        for item in draft.component_drafts
    }
    semantic_rules: list[SemanticRule] = []
    for rule in draft.proposed_rules:
        components: list[SemanticRuleComponent] = []
        for component in rule.components:
            mapping = mappings.get(component.rule_component_id)
            if mapping is None:
                raise ValueError(
                    f"规则组件缺少语义草稿来源映射：{component.rule_component_id}"
                )
            components.append(
                SemanticRuleComponent(
                    title=component.title,
                    expression=component.expression.model_copy(deep=True),
                    exception_expression=(
                        component.exception_expression.model_copy(deep=True)
                        if component.exception_expression is not None
                        else None
                    ),
                    evidence_requirements=[
                        SemanticEvidenceRequirement(
                            fact_type=requirement.fact_type,
                            required_source_types=requirement.required_source_types,
                            allows_screening_record_transcription=(
                                requirement.allows_screening_record_transcription
                            ),
                            requires_contemporaneous_objective_source=(
                                requirement.requires_contemporaneous_objective_source
                            ),
                            due_stage=requirement.due_stage,
                            source_validity_window=requirement.source_validity_window,
                            description=requirement.description,
                        )
                        for requirement in component.evidence_requirements
                    ],
                    source_span_ids=mapping.source_refs,
                    source_excerpts=mapping.source_excerpts,
                )
            )
        semantic_rules.append(
            SemanticRule(official_code=rule.official_code, components=components)
        )
    candidate_id = draft.draft_id.removeprefix("draft:")
    return ProtocolSemanticDeconstructionCandidate(
        candidate_id=candidate_id,
        proposed_rules=semantic_rules,
        structural_warnings=draft.structural_warnings,
        unresolved_items=draft.unresolved_items,
        created_by_agent_call_id=draft.created_by_agent_call_id,
    )


def revise_protocol_draft_from_feedback(
    source_input: ProtocolDeconstructionInput,
    current_draft: ProtocolDeconstructionDraft,
    *,
    target_rule_code: str,
    feedback_note: str,
    transport: ProtocolAgentTransport,
) -> ProtocolDeconstructionDraft:
    """依据一条明确的原文理解纠错，局部重新解构指定父规则。

    反馈是输入资料，不是发布权威。返回内容必须使用当前
    candidate_id，且只能替换指定官方父规则；其他规则由程序原样保留。
    """

    note = feedback_note.strip()
    if not note:
        raise ValueError("原文理解纠错必须写明具体问题和期望修正")
    current = semantic_candidate_from_draft(current_draft)
    current_codes = [rule.official_code for rule in current.proposed_rules]
    if target_rule_code not in current_codes:
        raise ValueError(f"当前草稿中找不到入排标准 {target_rule_code}")
    target = next(
        rule for rule in current.proposed_rules if rule.official_code == target_rule_code
    )
    prompt = (
        "你正在根据医学监查员指出的原文理解错误，局部修正已有方案"
        "解构草稿。用户反馈不能改变方案权威；仅当给定方案原文支持时"
        "才能修正。你必须只返回 ProtocolSemanticRuleRepair JSON，"
        f"candidate_id 必须为 {current.candidate_id!r}，replacement_rules 必须且只能"
        f"包含 {target_rule_code}。不得修改官方编号、增删其他父规则或伪造来源。\n\n"
        "本次是最小范围纠错，不是重写整条规则。除用户明确指出且方案原文支持修改的字段外，"
        "目标规则中现有的子项、谓词、ALL/ANY/NOT 逻辑、数值和单位、频次结构、时间限定、"
        "例外、资料要求、应完成阶段、来源片段及全部稳定 ID 都必须逐字段原样保留。"
        "输出前必须把 replacement_rules 与当前目标规则逐字段比较；任何无关变化都要撤销。\n\n"
        f"用户指出的问题：{note}\n\n"
        f"当前目标规则：{target.model_dump_json()}\n\n"
        f"冻结的方案输入：{source_input.model_dump_json()}\n\n"
        f"输出结构：{_compact_repair_schema()}"
    )
    response = transport.start(prompt=prompt)
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            repair = _parse_semantic_repair(response.text)
            revised = _apply_semantic_repair(
                current,
                repair,
                expected_codes=[target_rule_code],
            )
            hydrated = _hydrate_semantic_candidate(source_input, revised)
            # 局部修订必须追加到当前不可变草稿链；语义候选 ID 只是模型会话
            # 身份，不能反向生成一个新的 draft_id。
            return hydrated.model_copy(
                update={
                    "draft_id": current_draft.draft_id,
                    "draft_revision": current_draft.draft_revision,
                    "previous_draft_id": current_draft.previous_draft_id,
                }
            )
        except Exception as exc:
            last_error = exc
            if attempt == 1:
                break
            response = transport.continue_session(
                session_id=response.session_id,
                prompt=(
                    "上一响应无法作为指定父规则的局部修订读取。"
                    f"问题：{str(exc)[:12000]}。请只返回符合下列结构的 JSON："
                    + _compact_repair_schema()
                ),
            )
    raise ProtocolAgentCallError(
        response.session_id,
        f"反馈修订经过一次结构纠正后仍无法读取：{last_error}",
    )


def _parse_semantic_candidate(text: str) -> ProtocolSemanticDeconstructionCandidate:
    payload = _normalize_model_json(json.loads(text))
    try:
        return ProtocolSemanticDeconstructionCandidate.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(_validation_error_summary(exc)) from exc


def _validate_semantic_batch(
    candidate: ProtocolSemanticDeconstructionCandidate,
    *,
    expected_codes: Sequence[str],
    expected_candidate_id: str | None,
) -> None:
    actual_codes = [rule.official_code for rule in candidate.proposed_rules]
    if actual_codes != list(expected_codes):
        raise ValueError(
            "本批官方父规则与冻结顺序不一致；"
            f"应为 {list(expected_codes)}，实际为 {actual_codes}"
        )
    if (
        expected_candidate_id is not None
        and candidate.candidate_id != expected_candidate_id
    ):
        raise ValueError("后续批次不得更换 candidate_id")


def _merge_semantic_batches(
    batches: Sequence[ProtocolSemanticDeconstructionCandidate],
) -> ProtocolSemanticDeconstructionCandidate:
    first = batches[0]
    return ProtocolSemanticDeconstructionCandidate(
        candidate_id=first.candidate_id,
        proposed_rules=[
            rule for batch in batches for rule in batch.proposed_rules
        ],
        structural_warnings=[
            item for batch in batches for item in batch.structural_warnings
        ],
        unresolved_items=[
            item for batch in batches for item in batch.unresolved_items
        ],
        created_by_agent_call_id=first.created_by_agent_call_id,
    )


def _parse_semantic_repair(text: str) -> ProtocolSemanticRuleRepair:
    payload = _normalize_model_json(json.loads(text))
    try:
        return ProtocolSemanticRuleRepair.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(_validation_error_summary(exc)) from exc


def _apply_semantic_repair(
    candidate: ProtocolSemanticDeconstructionCandidate,
    repair: ProtocolSemanticRuleRepair,
    *,
    expected_codes: Sequence[str],
) -> ProtocolSemanticDeconstructionCandidate:
    if repair.candidate_id != candidate.candidate_id:
        raise ValueError("局部修正不得更换 candidate_id")
    actual_codes = [rule.official_code for rule in repair.replacement_rules]
    if set(actual_codes) != set(expected_codes) or len(actual_codes) != len(
        expected_codes
    ):
        raise ValueError(
            "局部修正必须且只能替换指定父规则；"
            f"应为 {list(expected_codes)}，实际为 {actual_codes}"
        )
    replacements = {rule.official_code: rule for rule in repair.replacement_rules}
    selected = set(expected_codes)
    for item in (
        *repair.replacement_structural_warnings,
        *repair.replacement_unresolved_items,
    ):
        if not set(item.affected_scope) <= selected:
            raise ValueError("局部修正返回了指定父规则之外的待确认事项")

    def outside_selected(item: UnresolvedItem) -> bool:
        return set(item.affected_scope).isdisjoint(selected)

    merged = candidate.model_copy(
        update={
            "proposed_rules": [
                replacements.get(rule.official_code, rule)
                for rule in candidate.proposed_rules
            ],
            "structural_warnings": [
                item for item in candidate.structural_warnings if outside_selected(item)
            ]
            + repair.replacement_structural_warnings,
            "unresolved_items": [
                item for item in candidate.unresolved_items if outside_selected(item)
            ]
            + repair.replacement_unresolved_items,
        },
        deep=True,
    )
    return ProtocolSemanticDeconstructionCandidate.model_validate(
        merged.model_dump(mode="json")
    )


def _affected_rule_codes(
    draft: ProtocolDeconstructionDraft,
    issues: Sequence[ProtocolGateIssue],
    *,
    fallback_all: bool = True,
) -> list[str]:
    refs = {ref for issue in issues for ref in issue.affected_refs}
    affected: list[str] = []
    for rule in draft.proposed_rules:
        identifiers = {rule.rule_id, rule.official_code}
        for component in rule.components:
            identifiers.update(
                {
                    component.rule_component_id,
                    component.display_code,
                }
            )
            expressions = [component.expression]
            if component.exception_expression is not None:
                expressions.append(component.exception_expression)
            for expression in expressions:
                identifiers.update(
                    predicate.predicate_id
                    for predicate in iter_atomic_predicates(expression)
                )
        if identifiers & refs:
            affected.append(rule.official_code)
    if affected or not fallback_all:
        return affected
    return [rule.official_code for rule in draft.proposed_rules]


def _repair_issues_for_rules(
    draft: ProtocolDeconstructionDraft,
    issues: Sequence[ProtocolGateIssue],
    selected_codes: Sequence[str],
) -> list[ProtocolGateIssue]:
    selected = set(selected_codes)
    allowed_refs: set[str] = set()
    for rule in draft.proposed_rules:
        if rule.official_code not in selected:
            continue
        allowed_refs.update({rule.rule_id, rule.official_code})
        for component in rule.components:
            allowed_refs.update(
                {component.rule_component_id, component.display_code}
            )
            expressions = [component.expression]
            if component.exception_expression is not None:
                expressions.append(component.exception_expression)
            for expression in expressions:
                allowed_refs.update(
                    predicate.predicate_id
                    for predicate in iter_atomic_predicates(expression)
                )

    scoped: list[ProtocolGateIssue] = []
    for issue in issues:
        affected_refs = [ref for ref in issue.affected_refs if ref in allowed_refs]
        if not affected_refs:
            continue
        repair_scope = [ref for ref in issue.repair_scope if ref in allowed_refs]
        scoped.append(
            issue.model_copy(
                update={
                    "affected_refs": affected_refs,
                    "repair_scope": repair_scope or affected_refs,
                }
            )
        )
    return scoped


def _select_repair_rule_codes(
    draft: ProtocolDeconstructionDraft,
    issues: Sequence[ProtocolGateIssue],
    attempt_counts: Mapping[str, int],
    *,
    limit: int,
) -> list[str]:
    """Give every affected parent a repair turn before repeatedly revisiting one."""

    affected = _affected_rule_codes(draft, issues, fallback_all=False)
    official_order = {
        rule.official_code: index for index, rule in enumerate(draft.proposed_rules)
    }
    return sorted(
        affected,
        key=lambda code: (attempt_counts.get(code, 0), official_order[code]),
    )[:limit]


def _issue_severity_by_rule(
    draft: ProtocolDeconstructionDraft,
    issues: Sequence[ProtocolGateIssue],
) -> dict[str, tuple[int, int, int]]:
    counts: dict[str, list[int]] = {
        rule.official_code: [0, 0, 0] for rule in draft.proposed_rules
    }
    for issue in issues:
        for code in _affected_rule_codes(draft, [issue], fallback_all=False):
            if issue.level == "阻止发布":
                counts[code][0] += 1
            elif issue.level == "需要核对":
                counts[code][1] += 1
            counts[code][2] += 1
    return {code: tuple(values) for code, values in counts.items()}


def regressing_rule_codes(
    previous_draft: ProtocolDeconstructionDraft,
    previous_issues: Sequence[ProtocolGateIssue],
    revised_draft: ProtocolDeconstructionDraft,
    revised_issues: Sequence[ProtocolGateIssue],
    selected_codes: Sequence[str],
) -> set[str]:
    previous = _issue_severity_by_rule(previous_draft, previous_issues)
    revised = _issue_severity_by_rule(revised_draft, revised_issues)
    previous_fingerprints = _issue_fingerprints_by_rule(
        previous_draft, previous_issues
    )
    revised_fingerprints = _issue_fingerprints_by_rule(revised_draft, revised_issues)
    return {
        code
        for code in selected_codes
        if revised.get(code, (0, 0, 0)) > previous.get(code, (0, 0, 0))
        or (
            revised.get(code, (0, 0, 0)) == previous.get(code, (0, 0, 0))
            and revised_fingerprints.get(code, set())
            != previous_fingerprints.get(code, set())
        )
    }


def _issue_fingerprints_by_rule(
    draft: ProtocolDeconstructionDraft,
    issues: Sequence[ProtocolGateIssue],
) -> dict[str, set[tuple[str, tuple[str, ...]]]]:
    fingerprints: dict[str, set[tuple[str, tuple[str, ...]]]] = {
        rule.official_code: set() for rule in draft.proposed_rules
    }
    for issue in issues:
        for code in _affected_rule_codes(draft, [issue], fallback_all=False):
            fingerprints[code].add(
                (issue.issue_code, tuple(sorted(issue.affected_refs)))
            )
    return fingerprints


def _restore_candidate_rules(
    revised: ProtocolSemanticDeconstructionCandidate,
    previous: ProtocolSemanticDeconstructionCandidate,
    restore_codes: set[str],
) -> ProtocolSemanticDeconstructionCandidate:
    previous_by_code = {rule.official_code: rule for rule in previous.proposed_rules}
    return revised.model_copy(
        update={
            "proposed_rules": [
                previous_by_code[rule.official_code]
                if rule.official_code in restore_codes
                else rule
                for rule in revised.proposed_rules
            ]
        },
        deep=True,
    )


def _parse_protocol_draft(
    text: str,
    source_input: ProtocolDeconstructionInput | None = None,
) -> ProtocolDeconstructionDraft:
    payload = json.loads(text)
    normalized = _normalize_model_json(payload)
    if "candidate_id" in normalized:
        if source_input is None:
            raise ValueError("语义候选必须绑定冻结的方案解构输入")
        candidate = _parse_semantic_candidate(text)
        return _hydrate_semantic_candidate(source_input, candidate)
    try:
        return ProtocolDeconstructionDraft.model_validate(normalized)
    except ValidationError as exc:
        raise ValueError(_validation_error_summary(exc)) from exc


def _format_issue(message: str) -> ProtocolGateIssue:
    return ProtocolGateIssue(
        issue_code="AGENT_OUTPUT_SCHEMA_INVALID",
        check_name="tree_integrity",
        level="阻止发布",
        problem="模型返回的结构化草稿无法读取：" + message[:12000],
        impact="当前输出不能进入方案审阅，也不能自动修成看似合理的规则。",
        next_action="请在同一会话中仅修正输出结构，并重新返回完整草稿。",
        affected_refs=["protocol_draft"],
        repair_scope=["protocol_draft_json"],
    )


def _collect_initial_semantic_response(
    source_input: ProtocolDeconstructionInput,
    *,
    prompt_template: str,
    transport: ProtocolAgentTransport,
    batch_size: int,
) -> tuple[ProtocolAgentResponse, str | None]:
    expected_codes = [
        item.official_code
        for item in sorted(
            source_input.parent_rule_catalog.items,
            key=lambda item: item.position,
        )
        if item.official_code is not None
    ]
    batches = [
        expected_codes[index : index + batch_size]
        for index in range(0, len(expected_codes), batch_size)
    ]
    if len(batches) <= 1:
        return (
            transport.start(
                prompt=build_protocol_deconstruction_prompt(
                    source_input,
                    prompt_template=prompt_template,
                )
            ),
            None,
        )

    response = transport.start(
        prompt=build_protocol_deconstruction_prompt(
            source_input,
            prompt_template=prompt_template,
            requested_rule_codes=batches[0],
        )
    )
    session_id = response.session_id
    collected: list[ProtocolSemanticDeconstructionCandidate] = []
    candidate_id: str | None = None
    for batch_index, rule_codes in enumerate(batches, start=1):
        batch_candidate: ProtocolSemanticDeconstructionCandidate | None = None
        problem = ""
        for schema_attempt in range(2):
            try:
                batch_candidate = _parse_semantic_candidate(response.text)
                _validate_semantic_batch(
                    batch_candidate,
                    expected_codes=rule_codes,
                    expected_candidate_id=candidate_id,
                )
            except Exception as exc:
                problem = str(exc)
                if schema_attempt == 1:
                    return response, (
                        f"第 {batch_index}/{len(batches)} 批经过一次结构修复后仍无法合并："
                        + problem
                    )
                try:
                    response = transport.continue_session(
                        session_id=session_id,
                        prompt=_batch_schema_repair_prompt(
                            rule_codes,
                            candidate_id=candidate_id,
                            problem=problem,
                        ),
                    )
                except Exception as exc:
                    return response, (
                        f"第 {batch_index}/{len(batches)} 批结构修复调用未完成：{exc}"
                    )
                if response.session_id != session_id:
                    return response, "分批结构修复切换了会话，已停止"
                continue
            break
        if batch_candidate is None:
            return response, problem or "本批没有可合并的语义结果"
        if candidate_id is None:
            candidate_id = batch_candidate.candidate_id
        collected.append(batch_candidate)
        if batch_index == len(batches):
            break
        try:
            response = transport.continue_session(
                session_id=session_id,
                prompt=_next_batch_prompt(
                    batches[batch_index],
                    batch_number=batch_index + 1,
                    batch_total=len(batches),
                    candidate_id=candidate_id,
                ),
            )
        except Exception as exc:
            return response, (
                f"第 {batch_index + 1}/{len(batches)} 批调用未完成：{exc}"
            )
        if response.session_id != session_id:
            return response, "分批语义解构切换了会话，已停止"

    merged = _merge_semantic_batches(collected)
    return ProtocolAgentResponse(
        session_id=session_id,
        text=merged.model_dump_json(),
    ), None


class ProtocolDeconstructorRunner:
    """Run bounded structural retries and isolated parent-rule repairs."""

    MAX_SCHEMA_REPAIRS = 2
    MAX_LOCAL_SCHEMA_REPAIRS = 1
    # Real mixed-phase protocols have needed fourteen isolated parent repairs
    # after a structurally valid first draft. The runtime also grants at least
    # one turn per frozen parent so fair rotation cannot starve a late rule.
    MAX_SEMANTIC_REPAIRS = 16
    MAX_RULES_PER_REPAIR = 3
    INITIAL_RULE_BATCH_SIZE = 3

    def __init__(self, gate: ProtocolDeconstructionGate | None = None):
        self._gate = gate or ProtocolDeconstructionGate()

    def run(
        self,
        source_input: ProtocolDeconstructionInput,
        *,
        prompt_version: PromptVersion,
        prompt_template: str,
        transport: ProtocolAgentTransport,
        source_spans: Mapping[str, ProtocolSourceSpan],
        interpretation_conflicts: Sequence[InterpretationConflict] = (),
    ) -> ProtocolDeconstructionRunResult:
        if prompt_version.node != AgentNode.PROTOCOL_DECONSTRUCTOR:
            raise ValueError("提示词版本不属于方案解构节点")
        if prompt_version.template_sha256 != protocol_prompt_template_sha256(
            prompt_template
        ):
            raise ValueError("提示词正文与已登记版本哈希不一致")

        try:
            response, collection_error = _collect_initial_semantic_response(
                source_input,
                prompt_template=prompt_template,
                transport=transport,
                batch_size=self.INITIAL_RULE_BATCH_SIZE,
            )
        except Exception as exc:
            session_id = getattr(exc, "session_id", "protocol-call-unavailable")
            issue = _format_issue(f"方案解构调用未完成：{exc}")
            return ProtocolDeconstructionRunResult(
                status="需要核对",
                same_session_id=session_id,
                attempts=[
                    ProtocolDeconstructionAttempt(
                        attempt=1,
                        session_id=session_id,
                        raw_output_sha256=_sha256(str(exc)),
                        outcome="会话异常",
                        issues=[issue],
                    )
                ],
            )
        session_id = response.session_id
        attempts: list[ProtocolDeconstructionAttempt] = []
        final_draft: ProtocolDeconstructionDraft | None = None
        final_gate: ProtocolDeconstructionGateResult | None = None
        current_candidate: ProtocolSemanticDeconstructionCandidate | None = None
        replacement_rule_codes: list[str] = []
        semantic_repair_counts: dict[str, int] = {}

        if collection_error is not None:
            issue = _format_issue(collection_error)
            return ProtocolDeconstructionRunResult(
                status="需要核对",
                same_session_id=session_id,
                attempts=[
                    ProtocolDeconstructionAttempt(
                        attempt=1,
                        session_id=session_id,
                        raw_output_sha256=_sha256(response.text),
                        outcome="输出格式无效",
                        issues=[issue],
                    )
                ],
            )

        attempt_number = 0
        schema_repairs = 0
        semantic_repairs = 0
        local_schema_repairs = 0
        semantic_repair_limit = max(
            self.MAX_SEMANTIC_REPAIRS,
            len(source_input.parent_rule_catalog.items),
        )
        while True:
            attempt_number += 1
            raw_hash = _sha256(response.text)
            candidate_for_attempt: ProtocolSemanticDeconstructionCandidate | None = None
            parsed_response = False
            try:
                if current_candidate is not None and replacement_rule_codes:
                    repair = _parse_semantic_repair(response.text)
                    candidate_for_attempt = _apply_semantic_repair(
                        current_candidate,
                        repair,
                        expected_codes=replacement_rule_codes,
                    )
                    draft = _hydrate_semantic_candidate(
                        source_input, candidate_for_attempt
                    )
                else:
                    payload = json.loads(response.text)
                    if "candidate_id" in payload:
                        candidate_for_attempt = _parse_semantic_candidate(
                            response.text
                        )
                        draft = _hydrate_semantic_candidate(
                            source_input, candidate_for_attempt
                        )
                    else:
                        draft = _parse_protocol_draft(response.text, source_input)
            except Exception as exc:
                issues = [_format_issue(str(exc))]
                attempts.append(
                    ProtocolDeconstructionAttempt(
                        attempt=attempt_number,
                        session_id=session_id,
                        raw_output_sha256=raw_hash,
                        outcome="输出格式无效",
                        issues=issues,
                    )
                )
            else:
                parsed_response = True
                gate_result = self._gate.evaluate(
                    source_input,
                    draft,
                    source_spans=source_spans,
                    interpretation_conflicts=interpretation_conflicts,
                )
                issues = [issue for check in gate_result.checks for issue in check.issues]
                if (
                    current_candidate is not None
                    and candidate_for_attempt is not None
                    and replacement_rule_codes
                    and final_draft is not None
                    and final_gate is not None
                ):
                    previous_issues = [
                        issue for check in final_gate.checks for issue in check.issues
                    ]
                    regressing_codes = regressing_rule_codes(
                        final_draft,
                        previous_issues,
                        draft,
                        issues,
                        replacement_rule_codes,
                    )
                    if regressing_codes:
                        candidate_for_attempt = _restore_candidate_rules(
                            candidate_for_attempt,
                            current_candidate,
                            regressing_codes,
                        )
                        draft = _hydrate_semantic_candidate(
                            source_input, candidate_for_attempt
                        )
                        gate_result = self._gate.evaluate(
                            source_input,
                            draft,
                            source_spans=source_spans,
                            interpretation_conflicts=interpretation_conflicts,
                        )
                        issues = [
                            issue
                            for check in gate_result.checks
                            for issue in check.issues
                        ]
                final_draft = draft
                final_gate = gate_result
                if candidate_for_attempt is not None:
                    current_candidate = candidate_for_attempt
                    replacement_rule_codes = _select_repair_rule_codes(
                        draft,
                        issues,
                        semantic_repair_counts,
                        limit=self.MAX_RULES_PER_REPAIR,
                    )
                attempts.append(
                    ProtocolDeconstructionAttempt(
                        attempt=attempt_number,
                        session_id=session_id,
                        raw_output_sha256=raw_hash,
                        outcome=(
                            "通过完整性检查"
                            if gate_result.publishable
                            else "需要定向修正"
                        ),
                        draft_id=draft.draft_id,
                        issues=issues,
                    )
                )
                if gate_result.publishable:
                    return ProtocolDeconstructionRunResult(
                        status="可以进入审阅",
                        same_session_id=session_id,
                        attempts=attempts,
                        final_draft=draft,
                        final_gate_result=gate_result,
                    )

            if not parsed_response and current_candidate is not None:
                if local_schema_repairs >= self.MAX_LOCAL_SCHEMA_REPAIRS:
                    break
                local_schema_repairs += 1
                repair_issues = issues
            elif current_candidate is None:
                if schema_repairs >= self.MAX_SCHEMA_REPAIRS:
                    break
                schema_repairs += 1
                repair_issues = issues
            else:
                local_schema_repairs = 0
                if (
                    semantic_repairs >= semantic_repair_limit
                    or not replacement_rule_codes
                ):
                    break
                semantic_repairs += 1
                for code in replacement_rule_codes:
                    semantic_repair_counts[code] = (
                        semantic_repair_counts.get(code, 0) + 1
                    )
                repair_issues = _repair_issues_for_rules(
                    draft,
                    issues,
                    replacement_rule_codes,
                )
            try:
                response = transport.continue_session(
                    session_id=session_id,
                    prompt=_repair_prompt(
                        repair_issues,
                        attempt=attempt_number,
                        parsed_draft_available=current_candidate is not None,
                        replacement_rule_codes=replacement_rule_codes,
                    ),
                )
            except Exception as exc:
                attempts.append(
                    ProtocolDeconstructionAttempt(
                        attempt=attempt_number + 1,
                        session_id=getattr(exc, "session_id", session_id),
                        raw_output_sha256=_sha256(str(exc)),
                        outcome="会话异常",
                        issues=[_format_issue(f"定向修正调用未完成：{exc}")],
                    )
                )
                break
            if response.session_id != session_id:
                attempts.append(
                    ProtocolDeconstructionAttempt(
                        attempt=attempt_number + 1,
                        session_id=response.session_id,
                        raw_output_sha256=_sha256(response.text),
                        outcome="会话异常",
                        issues=[
                            _format_issue(
                                "定向修正返回了新的会话，已停止，避免丢失原上下文。"
                            )
                        ],
                    )
                )
                break

        return ProtocolDeconstructionRunResult(
            status="需要核对",
            same_session_id=session_id,
            attempts=attempts,
            final_draft=final_draft,
            final_gate_result=final_gate,
        )
