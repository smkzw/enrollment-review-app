"""Deterministic publication checks for protocol deconstruction drafts.

The semantic model may propose a draft, but it cannot decide that the draft is
complete. These checks compare the proposal with the confirmed identity, the
two pre-frozen catalogs and the immutable protocol source locations.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from pydantic import Field

from app.domain.contracts.agent_io import (
    ProtocolDeconstructionDraft,
    ProtocolDeconstructionInput,
)
from app.domain.contracts.common import VersionedModel
from app.domain.contracts.enums import (
    AnchorType,
    CatalogKind,
    Comparator,
    LogicalOperator,
    ProtocolPeriod,
    ReviewStage,
    TimeDirection,
)
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.domain.contracts.protocol_metadata import (
    AnchorResolutionStatement,
    InterpretationConflict,
    InterpretationSource,
)
from app.domain.contracts.protocol_drafts import ParentRuleDiff
from app.domain.contracts.rules import Rule, TimeUnit, iter_atomic_predicates
from app.domain.interpretation import (
    InterpretationAuthorityError,
    clarification_anchor_resolutions,
)
from app.domain.publication import canonical_hash
from app.protocols.section_index import formal_source_span_ids


CHECK_NAMES = (
    "identity",
    "phase_scope",
    "parent_catalog",
    "tree_integrity",
    "boolean_logic",
    "numeric_semantics",
    "temporal_semantics",
    "workflow_coverage",
    "evidence_coverage",
    "source_coverage",
    "interpretation_authority",
    "diff_integrity",
)

# 完整性检查结果会写入持久任务检查点。任何会改变问题判定语义的
# 修改都必须提升此版本，避免旧检查结果在升级后继续冒充当前结论。
DECONSTRUCTION_GATE_VERSION = "protocol-deconstruction-gate/2026-09-02.2"


class ProtocolGateIssue(VersionedModel):
    issue_code: str = Field(min_length=1)
    check_name: str = Field(min_length=1)
    level: Literal["阻止发布", "需要核对", "提醒"]
    problem: str = Field(min_length=1)
    impact: str = Field(min_length=1)
    next_action: str = Field(min_length=1)
    affected_refs: list[str] = Field(min_length=1)
    repair_scope: list[str] = Field(min_length=1)


class ProtocolGateCheckResult(VersionedModel):
    check_name: str = Field(min_length=1)
    passed: bool
    issues: list[ProtocolGateIssue] = Field(default_factory=list)


class ProtocolDraftDiffDeclaration(VersionedModel):
    added_rule_codes: list[str] = Field(default_factory=list)
    removed_rule_codes: list[str] = Field(default_factory=list)
    modified_rule_codes: list[str] = Field(default_factory=list)
    added_workflow_stage_ids: list[str] = Field(default_factory=list)
    removed_workflow_stage_ids: list[str] = Field(default_factory=list)
    modified_workflow_stage_ids: list[str] = Field(default_factory=list)
    changed_component_ids: list[str] = Field(default_factory=list)
    changed_requirement_ids: list[str] = Field(default_factory=list)
    changed_procedure_mapping_ids: list[str] = Field(default_factory=list)
    source_scope_changed: bool = False
    workflow_visit_rewritten: bool = False
    clarification_semantics_changed: bool = False
    rule_diffs: list[ParentRuleDiff] = Field(default_factory=list)


class ProtocolDeconstructionGateResult(VersionedModel):
    publishable: bool
    checks: list[ProtocolGateCheckResult] = Field(min_length=12, max_length=12)


def _issue(
    check: str,
    code: str,
    problem: str,
    refs: Sequence[str],
    *,
    impact: str = "当前草稿不能作为正式入排规则发布。",
    action: str = "请回到对应方案原文和结构化草稿逐项修正后重新检查。",
    scope: Sequence[str] | None = None,
    level: Literal["阻止发布", "需要核对", "提醒"] = "阻止发布",
) -> ProtocolGateIssue:
    return ProtocolGateIssue(
        issue_code=code,
        check_name=check,
        level=level,
        problem=problem,
        impact=impact,
        next_action=action,
        affected_refs=list(refs) or ["protocol_draft"],
        repair_scope=list(scope or refs) or ["protocol_draft"],
    )


@dataclass(frozen=True)
class _AnchorResolutionContext:
    """解释锚点解析的门禁内部视图：通过权威检查的绑定与权威拒绝问题。

    只有澄清级、标注澄清、无未解决冲突的解释来源可以解析未命名回溯锚点；
    解析本身只携带锚点身份和目标审核节点集合，不携带窗口量或方向。
    """

    bindings: tuple[tuple[InterpretationSource, AnchorResolutionStatement], ...] = ()
    authority_issues: tuple[ProtocolGateIssue, ...] = field(default=())

    @property
    def bound_rule_codes(self) -> frozenset[str]:
        return frozenset(
            code
            for _source, resolution in self.bindings
            for code in resolution.affected_rule_refs
        )

    def resolutions_for_rule(self, official_code: str) -> tuple[AnchorResolutionStatement, ...]:
        return tuple(
            resolution
            for _source, resolution in self.bindings
            if official_code in resolution.affected_rule_refs
        )


def _anchor_resolution_context(
    source_input: ProtocolDeconstructionInput,
    interpretation_conflicts: Sequence[InterpretationConflict],
) -> _AnchorResolutionContext:
    """逐来源执行确定性权威检查；解释越权失败关闭为门禁问题。"""

    bindings: list[tuple[InterpretationSource, AnchorResolutionStatement]] = []
    authority_issues: list[ProtocolGateIssue] = []
    for source in source_input.interpretation_sources:
        try:
            resolutions = clarification_anchor_resolutions(
                source, conflicts=interpretation_conflicts
            )
        except InterpretationAuthorityError as exc:
            authority_issues.append(
                _issue(
                    "interpretation_authority",
                    "INTERPRETATION_ANCHOR_REJECTED",
                    f"解释来源 {source.interpretation_source_id} 的锚点解析被拒绝：{exc}",
                    [source.interpretation_source_id],
                    action="解释材料只能澄清方案模糊处；请修正解释来源，或改用当前修订案直接修改方案原文。",
                )
            )
            continue
        bindings.extend((source, resolution) for resolution in resolutions)
    return _AnchorResolutionContext(
        bindings=tuple(bindings), authority_issues=tuple(authority_issues)
    )


def _catalog_text(rule: Rule, source_input: ProtocolDeconstructionInput) -> str:
    item = next(
        (
            item
            for item in source_input.parent_rule_catalog.items
            if item.official_code == rule.official_code
        ),
        None,
    )
    if item is None:
        return ""
    materials = {
        material.source_span_id: material.text
        for material in source_input.source_materials
    }
    return "\n".join(
        dict.fromkeys(
            [item.label]
            + [materials[span_id] for span_id in item.source_span_ids if span_id in materials]
        )
    )


def _component_text(
    rule: Rule,
    component_id: str,
    draft: ProtocolDeconstructionDraft,
    source_input: ProtocolDeconstructionInput,
) -> str:
    mapping = next(
        (
            item
            for item in draft.component_drafts
            if item.proposed_component.rule_component_id == component_id
        ),
        None,
    )
    if mapping is None:
        return _catalog_text(rule, source_input)
    if mapping.source_excerpts:
        return "\n".join(mapping.source_excerpts)
    materials = {
        material.source_span_id: material.text
        for material in source_input.source_materials
    }
    text = "\n".join(
        dict.fromkeys(
            materials[span_id]
            for span_id in mapping.source_refs
            if span_id in materials
        )
    )
    return text or _catalog_text(rule, source_input)


def _predicate_text(predicate) -> str:
    """Join exact fragments only for checks; provenance remains segmented."""

    return "\n".join(predicate.exact_source_clauses)


def _predicate_temporal_text(predicate) -> str:
    """Return the temporal meaning owned by one atomic predicate.

    Exact source clauses may repeat a complete protocol sentence so that the
    citation remains verbatim. That sentence can also contain a sibling OR
    branch or an exception. Temporal checks therefore use the predicate's
    semantic identity whenever it already names its own window or period, or
    when it has no temporal meaning at all. The wider exact clause is consulted
    only for an underspecified temporal identity such as ``计划接种活疫苗``.
    """

    text = _predicate_text(predicate)
    identity = "\n".join(
        dict.fromkeys(
            part.strip()
            for part in (predicate.source_term, predicate.attribute)
            if part and part.strip()
        )
    )
    binding_terms = {
        _normalized(part)
        for part in (predicate.source_term, predicate.attribute)
        if part and _normalized(part)
    }
    pattern = re.compile(
        r"(?:^|[、，；。\n])(?P<label>[^、，；。\n（）()]{1,40})"
        r"(?P<note>[（(][^）)]*\d+(?:\.\d+)?\s*个?(?:天|日|周|月|年)[^）)]*[）)])"
    )

    def retain_or_remove(match: re.Match[str]) -> str:
        label = _normalized(match.group("label"))
        following_segment = re.split(
            r"[、，；。\n]", text[match.end() :].lstrip("、，；。\n"), maxsplit=1
        )[0]
        if any(label and label in term for term in binding_terms) or any(
            term in _normalized(following_segment) for term in binding_terms
        ):
            return match.group(0)
        prefix = match.group(0)[0] if match.group(0)[0] in "、，；。" else ""
        return prefix + match.group("label")

    cleaned_source = pattern.sub(retain_or_remove, text)
    compact_identity = re.sub(r"\s+", "", identity)
    identity_owns_window = bool(_source_time_quantities(identity)) or bool(
        re.search(
            r"(?:随机|筛选|基线|知情同意|首次给药|首剂|"
            r"第一次给药|研究药物给药|试验药物给药|"
            r"末次给药|最后一次给药|研究完成|研究结束)(?:前|后|时)",
            compact_identity,
        )
    )
    identity_owns_period = any(
        marker in compact_identity
        for marker in ("研究期间", "治疗期间", "筛选/导入期", "筛选导入期")
    )
    if identity_owns_window or identity_owns_period:
        return identity
    normalized_attribute = _normalized(predicate.attribute)
    clauses = predicate.exact_source_clauses
    has_direct_non_temporal_clause = any(
        normalized_attribute
        and normalized_attribute in _normalized(clause)
        and not _source_time_quantities(clause)
        and not re.search(
            r"(?:随机|筛选|基线|给药|研究完成|研究结束)(?:前|后|时)",
            re.sub(r"\s+", "", clause),
        )
        for clause in clauses
    )
    has_broader_temporal_clause = any(
        normalized_attribute
        and normalized_attribute in _normalized(clause)
        and (
            bool(_source_time_quantities(clause))
            or bool(
                re.search(
                    r"(?:随机|筛选|基线|给药|研究完成|研究结束)(?:前|后|时)",
                    re.sub(r"\s+", "", clause),
                )
            )
        )
        for clause in clauses
    )
    if has_direct_non_temporal_clause and has_broader_temporal_clause:
        return identity
    return cleaned_source


def _is_population_scoped_any(expression) -> bool:
    if expression.kind != "logical" or expression.operator != LogicalOperator.ANY:
        return False
    branch_populations: list[frozenset[str]] = []
    for child in expression.children:
        populations = {
            predicate.applicable_population
            for predicate in iter_atomic_predicates(child)
            if predicate.applicable_population
        }
        if not populations:
            return False
        branch_populations.append(frozenset(populations))
    return len(set(branch_populations)) == len(branch_populations)


def _any_branches_preserve_internal_conjunction(expression) -> bool:
    """Allow alternatives whose own compound requirement stays atomic or ALL."""

    if expression.kind != "logical" or expression.operator != LogicalOperator.ANY:
        return False
    for child in expression.children:
        if child.kind == "logical" and child.operator == LogicalOperator.ALL:
            continue
        if child.kind != "predicate":
            return False
        source = _normalized(_predicate_text(child.predicate))
        attribute = _normalized(child.predicate.attribute)
        conjunctions = ("且", "并且", "同时")
        if not any(token in source for token in conjunctions):
            return False
        if not any(token in attribute for token in conjunctions):
            return False
    return True


def _any_is_same_event_time_alternatives(expression, source: str) -> bool:
    """Allow explicit alternative windows for one unchanged clinical event."""

    if (
        expression.kind != "logical"
        or expression.operator != LogicalOperator.ANY
        or "或" not in source
    ):
        return False
    identities: list[str] = []
    constraints: list[str] = []
    for child in expression.children:
        if child.kind != "predicate" or child.time_constraint is None:
            return False
        identities.append(_normalized(child.predicate.attribute))
        constraints.append(
            canonical_hash(child.time_constraint.model_dump(mode="json"))
        )
    return bool(
        identities
        and len(set(identities)) == 1
        and len(set(constraints)) == len(constraints)
    )


def _source_requires_investigator_judgment(text: str) -> bool:
    """Distinguish the investigator as decision-maker from other roles.

    Phrases such as ``与研究者进行良好沟通`` name the investigator as the
    other party, not as the professional assessor.  Only an explicit judgment
    verb bound to the investigator creates this obligation.
    """

    compact = re.sub(r"\s+", "", text)
    judgment = r"(?:评估|评定|判断|判定|认为|认定|确定|决定|确认|同意)"
    return bool(
        re.search(
            rf"(?:由|经|需由|须由|应由|根据)?研究者(?:进行)?{judgment}",
            compact,
        )
        or re.search(rf"{judgment}(?:应|需)?(?:由|经)研究者", compact)
        or re.search(rf"研究者的?{judgment}", compact)
    )


def _localized_open_list_exception_requires_exclusivity(text: str) -> bool:
    """Identify a local carve-out inside a non-exhaustive example list."""

    compact = re.sub(r"\s+", "", text)
    return bool(
        re.search(r"(?:包括但不限于|但不限于|例如|例如包括|如[：:])", compact)
        and re.search(r"[（(][^）)]*(?:除外|除非|例外)[^）)]*[）)]", compact)
    )


def _exception_asserts_exclusivity(expression) -> bool:
    """A component-wide exception is safe only when no sibling trigger coexists."""

    exclusivity_tokens = ("唯一", "仅有", "只有", "单独", "除此之外无", "除该项外无")
    return any(
        token
        in _normalized(f"{predicate.attribute}\n{_predicate_text(predicate)}")
        for predicate in iter_atomic_predicates(expression)
        for token in exclusivity_tokens
    )


def _branch_source_anchors(expression, source: str) -> list[tuple[int, int, str]]:
    """Locate branch-owned clinical terms without using whole-clause overlap."""

    compact_source = re.sub(r"\s+", "", source)
    candidates: list[str] = []
    for predicate in iter_atomic_predicates(expression):
        candidates.extend(
            item
            for item in (
                predicate.source_term,
                predicate.attribute,
                *predicate.exact_source_clauses,
            )
            if item and len(re.sub(r"\s+", "", item)) >= 2
        )
        values = predicate.value if isinstance(predicate.value, list) else []
        candidates.extend(
            str(item)
            for item in values
            if isinstance(item, str) and len(re.sub(r"\s+", "", item)) >= 2
        )
    anchors: list[tuple[int, int, str]] = []
    for candidate in dict.fromkeys(candidates):
        compact_candidate = re.sub(r"\s+", "", candidate)
        start = compact_source.find(compact_candidate)
        if start >= 0:
            anchors.append((start, start + len(compact_candidate), compact_candidate))
    return anchors


def _branches_have_source_disjunction(expression, source: str) -> bool:
    """Verify that sibling branches are individually named around a real OR."""

    if expression.kind != "logical" or expression.operator == LogicalOperator.NOT:
        return False
    compact_source = re.sub(r"\s+", "", source)
    branch_anchors = [
        _branch_source_anchors(child, compact_source) for child in expression.children
    ]
    if any(not anchors for anchors in branch_anchors):
        return False
    for first in branch_anchors[0]:
        paths = [(first, first[0], first[1], [first[2]])]
        for anchors in branch_anchors[1:]:
            next_paths = []
            for path, start, end, terms in paths:
                for anchor in anchors:
                    if anchor[0] < end:
                        continue
                    next_paths.append(
                        (anchor, start, anchor[1], [*terms, anchor[2]])
                    )
            paths = next_paths
            if not paths:
                break
        for _last, start, end, terms in paths:
            if all(term in {"筛选", "筛选期", "基线", "基线期"} for term in terms):
                continue
            between = compact_source[start:end]
            if re.search(r"(?:和/或|及/或|或(?!以上|等于))", between):
                return True
            # 原文以“满足以下条件之一/任一”显式引导替代关系时，各分支之间的
            # 分隔可以由顿号、逗号或分号承担；分支本身仍必须逐一定名于原文。
            if _ALTERNATIVE_LEAD_IN.search(compact_source) and re.search(
                r"[、，；。;,\n]", between
            ):
                return True
    return False


def _walk_expressions(rule: Rule):
    for component in rule.components:
        yield component.expression
        if component.exception_expression is not None:
            yield component.exception_expression


def _walk_expression_tree(expression):
    yield expression
    if expression.kind == "logical":
        for child in expression.children:
            yield from _walk_expression_tree(child)


def _negated_predicates(expression):
    """Yield predicates whose truth value is inverted by an immediate NOT."""

    if expression.kind != "logical":
        return
    if expression.operator == LogicalOperator.NOT:
        yield from iter_atomic_predicates(expression.children[0])
        return
    for child in expression.children:
        yield from _negated_predicates(child)


def _source_supports_predicate_negation(predicate) -> bool:
    """Require an explicit absence construction bound to the asserted object.

    Result words such as ``阴性`` and lexical prefixes inside terms such as
    ``不良事件`` or ``非特异性抗体`` are categorical content, not a
    license to invert an arbitrary predicate.
    """

    source = re.sub(r"\s+", "", _predicate_text(predicate))
    terms = list(
        dict.fromkeys(
            re.sub(r"\s+", "", term)
            for term in (predicate.source_term, predicate.attribute)
            if term and len(re.sub(r"\s+", "", term)) >= 2
        )
    )
    if not source or not terms:
        return False
    prefixes = (
        "无",
        "没有",
        "否认",
        "未见",
        "未发现",
        "未发生",
        "未患",
        "未使用",
        "未接受",
        "未接种",
        "未参加",
        "未签署",
        "未完成",
        "未进行",
        "不具备",
        "不符合",
        "不满足",
        "不存在",
    )
    suffixes = (
        "不存在",
        "未发生",
        "未完成",
        "未签署",
        "不符合",
        "不满足",
        "不具备",
    )
    for term in terms:
        escaped = re.escape(term)
        if any(
            re.search(re.escape(prefix) + r"[^，；。\n]{0,8}" + escaped, source)
            for prefix in prefixes
        ):
            return True
        if any(
            re.search(escaped + r"[^，；。\n]{0,4}" + re.escape(suffix), source)
            for suffix in suffixes
        ):
            return True
    return False


def _source_supports_negative_comparator(predicate) -> bool:
    """Bind NE/NOT_IN to an explicit comparison against the stated value."""

    source = re.sub(r"\s+", "", _predicate_text(predicate))
    if not source:
        return False
    if predicate.comparator == Comparator.NE:
        rendered = str(predicate.value)
        if isinstance(predicate.value, float) and predicate.value.is_integer():
            rendered = str(int(predicate.value))
        return rendered in source and bool(
            re.search(r"(?:≠|不等于|不是)", source)
        )
    if predicate.comparator != Comparator.NOT_IN:
        return True
    values = predicate.value if isinstance(predicate.value, list) else []
    for value in values:
        if not isinstance(value, str):
            continue
        compact_value = re.sub(r"\s+", "", value)
        if not compact_value or compact_value not in source:
            continue
        if re.search(
            r"(?:不属于|不在|不包括|不含|不是|非)"
            r"[^，；。\n]{0,4}"
            + re.escape(compact_value),
            source,
        ):
            return True
    return False


def _exception_applies_to_trigger(text: str, trigger_clauses: Sequence[str]) -> bool:
    exception_matches = list(
        re.finditer(r"[（(][^）)]*(?:除外|除非|例外)[^）)]*[）)]", text)
    )
    for clause in trigger_clauses:
        start = text.find(clause)
        if start < 0:
            continue
        end = start + len(clause)
        for match in exception_matches:
            if start <= match.start() and "或" not in text[end : match.start()]:
                return True
            if match.start() <= start < match.end():
                return True
    return False


def _root_operators(rule: Rule) -> set[LogicalOperator]:
    return {
        expression.operator
        for expression in _walk_expressions(rule)
        if expression.kind == "logical"
    }


def _normalized(text: str) -> str:
    return re.sub(r"[\s，。；：、（）()【】\[\]]+", "", text).lower()


def _substantive_obligation_segments(text: str) -> list[str]:
    """Split one official parent rule into independently material obligations.

    This is deliberately narrower than general Chinese sentence segmentation.
    We split top-level clinical clauses and explicit conjunctions while keeping
    parenthetical examples and OR alternatives together. Structural lead-ins
    are ignored because they do not create an independently assessable fact.
    """

    segments: list[str] = []
    current: list[str] = []
    depth = 0
    index = 0
    conjunctions = ("并且", "同时", "而且", "且")
    while index < len(text):
        char = text[index]
        if char in "（(":
            depth += 1
        elif char in "）)" and depth:
            depth -= 1
        if depth == 0 and char in "，；。\n":
            candidate = "".join(current).strip()
            if candidate:
                segments.append(candidate)
            current = []
            index += 1
            continue
        matched = next(
            (
                token
                for token in conjunctions
                if depth == 0 and text.startswith(token, index)
            ),
            None,
        )
        if matched:
            candidate = "".join(current).strip()
            if candidate:
                segments.append(candidate)
            current = []
            index += len(matched)
            continue
        current.append(char)
        index += 1
    candidate = "".join(current).strip()
    if candidate:
        segments.append(candidate)

    # 结构引导语只允许封闭的引导词表：主语、助动词、满足/符合、“以下/下列”、
    # 量词（所有/全部/各项/任一/之一）和条件、标准等空泛名词。任何临床内容词
    # 都无法全匹配，因此实质性条件不会被该正则吞掉（fail-closed）。
    structural = re.compile(
        r"^(?:受试者|患者|志愿者|男性|女性|男女性|男女|两性|成人|儿童)*"
        r"(?:均)?(?:必须|应|需|需要)?(?:同时)?(?:均须|均需|均应)?"
        r"(?:满足|符合|具备|达到)(?:以下|下列|下述|如下)"
        r"(?:所有|全部|各项|任一|任何一|任意一)?(?:之一|项|条|个)?(?:的)?"
        r"(?:入选|排除|纳入|除外)?(?:条件|标准|要求|情形|情况|条款)?"
        r"(?:之一|任一项|任意一项|任何一项|一项或多项)?"
        r"(?:方可入组|方可参加|才能入组|即可|者)?(?:入组)?$|"
        r"^(?:包括(?:以下|下列|如下)?(?:情形|情况|条件|要求)?|"
        r"包括但不限于|如下|具体如下|除外标准|入选标准|排除标准)$|"
        r"^(?:正在)?(?:使用|接受|具有|患有|存在)(?:或有)?"
        r"(?:以下|下列)(?:治疗|用药|疾病|病史|情况|条件|情形)(?:史)?"
        r"(?:或(?:治疗|用药|疾病|病史|情况|条件|情形)(?:史)?)?$|"
        r"^(?:或者)?(?:以下|下列|如下)列出的(?:相关)?(?:疾病|病史|情况|条件|情形)$|"
        r"^根据[^，；。]{1,40}(?:推断|判断|评估)$|"
        r"^(?:整个|全程)?(?:研究|试验|治疗|用药|随访)期间(?:从.{1,80})?$|"
        r"^(?:预筛|筛选|导入|基线|随机|首次给药)(?:期|访视)?(?:时)?"
        r"(?:(?:和|与|及|或|、)(?:预筛|筛选|导入|基线|随机|首次给药)(?:期|访视)?(?:时)?)+"
        r"(?:必须|应|需|需要)?(?:满足|符合|具备|达到)(?:以下|下列|下述|如下)"
        r"(?:条件|标准|要求|情形|情况|条款)$"
    )
    stage_only = re.compile(
        r"^(?:在)?(?:预筛|筛选|导入|基线|随机|首次给药|签署icf|知情同意)"
        r"(?:期|访视)?(?:前|后|时|当日)?$"
    )
    # 非限制性人群描述：人口学属性名词 + “不限/均可/无特殊要求”等非限制谓语，
    # 或“无论/不论 + 属性”的让步短语。这些描述不产生可核对的实质性条件，
    # 不得据此要求模型虚构男/女等分类原子（与提示合同一致）。
    nonrestrictive = re.compile(
        r"^(?:不论|无论|不管)?(?:性别|年龄|男女性|男女|两性|种族|民族|婚姻状况|婚姻|宗教信仰|宗教|职业|地域)"
        r"(?:(?:和|与|及|或|、)?(?:性别|年龄|男女性|男女|两性|种族|民族|婚姻状况|婚姻|宗教信仰|宗教|职业|地域))*"
        r"(?:均)?(?:不限|无限制|不作限制|无特殊要求|均可)"
        r"(?:参加|参与|纳入|入组)?(?:本|该)?(?:研究)?$|"
        r"^不限(?:性别|年龄|男女性|男女|两性|种族|民族|婚姻状况)$|"
        r"^(?:不论|无论|不管)(?:其)?(?:性别|男女性|男女|两性|种族|民族)(?:如何|怎样|为何)?"
        r"(?:均)?(?:可|可以|皆可)?(?:参与|纳入|入组|参加)?(?:本|该)?(?:研究)?$|"
        r"^(?:可以|可|允许)(?:纳入|入组|参加)(?:本|该)?研究$"
    )
    return list(
        dict.fromkeys(
            segment
            for segment in segments
            if len(_normalized(segment)) >= 3
            and not structural.fullmatch(_normalized(segment))
            and not stage_only.fullmatch(_normalized(segment))
            and not nonrestrictive.fullmatch(_normalized(segment))
        )
    )


def _longest_common_run(first: str, second: str) -> int:
    """Return the longest contiguous shared run without fuzzy semantics."""

    if not first or not second:
        return 0
    previous = [0] * (len(second) + 1)
    longest = 0
    for left in first:
        current = [0]
        for position, right in enumerate(second, start=1):
            value = previous[position - 1] + 1 if left == right else 0
            current.append(value)
            longest = max(longest, value)
        previous = current
    return longest


def _predicate_binds_obligation(predicate, segment: str) -> bool:
    """Require both a verbatim locator and a semantic identity for a clause."""

    normalized_segment = _normalized(segment)
    clauses = [_normalized(clause) for clause in predicate.exact_source_clauses]
    if not normalized_segment or not clauses:
        return False
    locator_overlaps = any(
        clause in normalized_segment
        or normalized_segment in clause
        or _longest_common_run(clause, normalized_segment) >= 4
        for clause in clauses
    )
    if not locator_overlaps:
        return False

    terms = [predicate.source_term, predicate.attribute]
    if isinstance(predicate.value, str):
        terms.append(predicate.value)
    elif isinstance(predicate.value, list):
        terms.extend(value for value in predicate.value if isinstance(value, str))
    semantic_terms = [_normalized(term) for term in terms if term and _normalized(term)]
    if any(
        term in normalized_segment
        or normalized_segment in term
        or _longest_common_run(term, normalized_segment) >= 2
        for term in semantic_terms
        if len(term) >= 2
    ):
        return True
    if predicate.requires_professional_judgment and "研究者" in normalized_segment:
        return True
    values = predicate.value if isinstance(predicate.value, list) else [predicate.value]
    source_numbers = _numeric_tokens(segment)
    return any(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and _numeric_value_in_tokens(value, source_numbers)
        for value in values
    )


def _categorical_values_are_source_terms(predicate) -> bool:
    """Reject character fragments while preserving explicit short enumerations."""

    values = predicate.value if isinstance(predicate.value, list) else []
    if predicate.comparator not in {Comparator.IN, Comparator.NOT_IN} or not values:
        return True
    if not all(isinstance(value, str) and value.strip() for value in values):
        return False
    source = re.sub(r"\s+", "", _predicate_text(predicate))
    compact_values = [re.sub(r"\s+", "", value) for value in values]
    if not source or any(value not in source for value in compact_values):
        return False

    # One-character categories are valid only when the protocol itself lists
    # them as alternatives, for example "男或女" or "A/B". This prevents
    # a model from turning "斑块状" into the invented set ["斑", "块"].
    if any(len(value) == 1 for value in compact_values):
        if len(compact_values) < 2:
            return False
        separator = r"(?:或|、|/|和|及|与)"
        patterns = (
            separator.join(re.escape(value) for value in compact_values),
            separator.join(re.escape(value) for value in reversed(compact_values)),
        )
        return any(re.search(pattern, source) for pattern in patterns)

    source_term = re.sub(r"\s+", "", predicate.source_term or "")
    for value in compact_values:
        if source_term and value == source_term:
            continue
        start = source.find(value)
        following = source[start + len(value) : start + len(value) + 1]
        if following in {"状", "型", "类"} and not value.endswith(("状", "型", "类")):
            return False
    return True


# 明确的替代关系引导语：只有“之一/任一/任何一项”等替代连接语直接绑定在
# 条件、标准、项、条等结构名词上时才成立。“常见类型之一”这类非结构用法
# 不匹配，保持实质条件的 fail-closed。
_ALTERNATIVE_LEAD_IN = re.compile(
    r"(?:条件|标准|要求|情形|情况|条款|项|条|者)之一"
    r"|(?:以下|下列|如下|下述)[^，。；；\n]{0,6}之一"
    r"|(?:\d+|[一二两三四五六七八九十百]+)(?:种|类|项|个|条)?[^，。；\n]{0,12}之一"
    r"|任选其一|满足其一|符合其一"
    r"|一项或多项|至少一项|至少一条|任一条|任意一项|任意一条|任何一条"
)


def _has_unambiguous_disjunction(text: str) -> bool:
    normalized = _normalized(text)
    if any(
        token in normalized
        for token in ("任一", "任何一项", "至少一项", "和/或", "及/或")
    ):
        return True
    if _ALTERNATIVE_LEAD_IN.search(normalized):
        return True
    if re.search(r"[，；;。]\s*或", text):
        return True
    return bool(
        re.search(
            r"[A-Za-z][A-Za-z0-9α-ωΑ-Ω-]{1,11}或"
            r"[A-Za-z][A-Za-z0-9α-ωΑ-Ω-]{1,11}",
            text,
        )
    )


def _numeric_tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", text))
    roman_values = {
        "Ⅰ": "1",
        "Ⅱ": "2",
        "Ⅲ": "3",
        "Ⅳ": "4",
        "Ⅴ": "5",
    }
    tokens.update(value for marker, value in roman_values.items() if marker in text)
    return tokens


def _numeric_value_in_tokens(value: int | float, tokens: set[str]) -> bool:
    return format(value, "g") in {format(float(token), "g") for token in tokens}


def _unit_matches_source(unit: str, text: str) -> bool:
    """Match a canonical unit only against general linguistic equivalents."""

    normalized_unit = _normalized(unit)
    normalized_text = _normalized(text)
    if not normalized_unit or normalized_unit == "unitless":
        return True
    if normalized_unit in normalized_text:
        return True
    aliases = {
        "year": ("年", "周岁", "岁"),
        "years": ("年", "周岁", "岁"),
        "month": ("个月", "月"),
        "months": ("个月", "月"),
        "week": ("周", "星期"),
        "weeks": ("周", "星期"),
        "day": ("天", "日"),
        "days": ("天", "日"),
    }
    return any(marker in normalized_text for marker in aliases.get(normalized_unit, ()))


def _source_time_quantities(text: str) -> set[tuple[int, TimeUnit]]:
    """Extract explicit duration quantities without flattening calendar units."""

    unit_by_marker = {
        "天": TimeUnit.DAY,
        "日": TimeUnit.DAY,
        "周": TimeUnit.WEEK,
        "星期": TimeUnit.WEEK,
        "个月": TimeUnit.MONTH,
        "年": TimeUnit.YEAR,
        "day": TimeUnit.DAY,
        "days": TimeUnit.DAY,
        "week": TimeUnit.WEEK,
        "weeks": TimeUnit.WEEK,
        "month": TimeUnit.MONTH,
        "months": TimeUnit.MONTH,
        "year": TimeUnit.YEAR,
        "years": TimeUnit.YEAR,
    }
    pattern = r"(?<![\d.])(\d+)\s*(个月|天|日|周|星期|年|days?|weeks?|months?|years?)"
    return {
        (int(value), unit_by_marker[marker.lower()])
        for value, marker in re.findall(pattern, text, flags=re.IGNORECASE)
    }


def _source_validity_windows(text: str) -> set[tuple[int, TimeUnit]]:
    """提取“可接受 N 时间内的检查结果”这类资料时效。"""

    unit_map = {
        "天": TimeUnit.DAY,
        "日": TimeUnit.DAY,
        "周": TimeUnit.WEEK,
        "星期": TimeUnit.WEEK,
        "个月": TimeUnit.MONTH,
        "月": TimeUnit.MONTH,
        "年": TimeUnit.YEAR,
    }
    compact = re.sub(r"\s+", "", text)
    return {
        (int(match.group("value")), unit_map[match.group("unit")])
        for match in re.finditer(
            r"可接受(?P<value>\d+)(?P<unit>星期|个月|天|日|周|月|年)内(?:的)?"
            r"[^\uff0c\u3002\uff1b\uff1a\uff09)]{0,40}?(?:检查)?结果",
            compact,
        )
    }


def _source_validity_specs(
    text: str,
) -> set[tuple[int, TimeUnit, str]]:
    """提取括号中资料时效及其直接限定的检查名称。"""

    unit_map = {
        "天": TimeUnit.DAY,
        "日": TimeUnit.DAY,
        "周": TimeUnit.WEEK,
        "星期": TimeUnit.WEEK,
        "个月": TimeUnit.MONTH,
        "月": TimeUnit.MONTH,
        "年": TimeUnit.YEAR,
    }
    compact = re.sub(r"\s+", "", text)
    specs: set[tuple[int, TimeUnit, str]] = set()
    pattern = re.compile(
        r"(?P<subject>[^，。；：（()]{1,20})[（(]可接受"
        r"(?P<value>\d+)(?P<unit>星期|个月|天|日|周|月|年)内(?:的)?"
        r"(?P<result>[^，。；：()）]{0,30}?)(?:检查)?结果[）)]"
    )
    for match in pattern.finditer(compact):
        subject = _normalized(match.group("subject"))
        result = _normalized(match.group("result"))
        named_item = result or subject
        if named_item:
            specs.add(
                (
                    int(match.group("value")),
                    unit_map[match.group("unit")],
                    named_item,
                )
            )
    return specs


def _requirement_matches_validity_spec(requirement, named_item: str) -> bool:
    fact = _normalized(requirement.fact_type)
    item = _normalized(named_item)
    if len(item) < 2 or len(fact) < 2:
        return False
    return item in fact or fact in item


def _time_bound_matches_source(value: int, unit: TimeUnit, text: str) -> bool:
    source_quantities = _source_time_quantities(text)
    if (value, unit) in source_quantities:
        return True
    # Weeks are exactly seven days. This is the only unit conversion accepted
    # here without an explicit source-side day quantity; month/year conversion
    # is intentionally never inferred from a fixed number of days.
    return unit == TimeUnit.DAY and any(
        source_value * 7 == value and source_unit == TimeUnit.WEEK
        for source_value, source_unit in source_quantities
    )


def _source_frequency_specs(text: str) -> set[tuple[int, TimeUnit, int, str]]:
    """Extract explicit rolling frequency definitions from exact source text."""

    unit_by_marker = {
        "天": TimeUnit.DAY,
        "日": TimeUnit.DAY,
        "周": TimeUnit.WEEK,
        "星期": TimeUnit.WEEK,
        "个月": TimeUnit.MONTH,
        "月": TimeUnit.MONTH,
        "年": TimeUnit.YEAR,
    }
    specs: set[tuple[int, TimeUnit, int, str]] = set()
    history_pattern = re.compile(
        r"(?P<duration>\d+)\s*(?P<duration_unit>天|日|周|星期|个月|月|年)内"
        r"[^，。；]{0,24}?(?:发生|出现|发作|复发)\s*"
        r"(?P<count>\d+)\s*次"
    )
    occurrence_day_pattern = re.compile(
        r"(?P<duration>\d+)\s*(?P<duration_unit>天|日|周|星期|个月|月|年)"
        r"\s*(?:内)?\s*(?:≥|大于或等于|不低于|至少)\s*"
        r"(?P<count>\d+)\s*(?:天|日)"
    )
    every_period_day_pattern = re.compile(
        r"每\s*(?P<duration_unit>周|星期|个月|月|年)"
        r"[^，。；]{0,12}?(?:≥|大于或等于|不低于|至少)\s*"
        r"(?P<count>\d+)\s*(?:天|日)"
    )
    for match in history_pattern.finditer(text):
        specs.add(
            (
                int(match.group("duration")),
                unit_by_marker[match.group("duration_unit")],
                int(match.group("count")),
                "次",
            )
        )
    for match in occurrence_day_pattern.finditer(text):
        specs.add(
            (
                int(match.group("duration")),
                unit_by_marker[match.group("duration_unit")],
                int(match.group("count")),
                "天",
            )
        )
    for match in every_period_day_pattern.finditer(text):
        specs.add(
            (
                1,
                unit_by_marker[match.group("duration_unit")],
                int(match.group("count")),
                "天",
            )
        )
    return specs


def _frequency_repair_action() -> str:
    return (
        "先区分数值结构缺失与原文绑定缺失。若 occurrence_window.duration、次数阈值或"
        " minimum_count 已正确，不要反复改写这些值；为同一谓词补全逐字 source_clause"
        "（或 source_clauses），片段须包含该事件及其频次定义，并用 source_term 保留原文事件名称。"
        "若数值结构缺失，次数用数值谓词或 occurrence_window.minimum_count，周期内天数用天数阈值；"
        "均用 occurrence_window.duration 保留观察周期。频次只约束原文直接限定的事件或示例分支，"
        "不得套到无关兄弟分支，不得新增或改写原文。"
    )


def _predicate_preserves_frequency(
    predicate, spec: tuple[int, TimeUnit, int, str]
) -> bool:
    duration, duration_unit, minimum, count_unit = spec
    frequency_clauses = [
        clause
        for clause in predicate.exact_source_clauses
        if spec in _source_frequency_specs(clause)
    ]
    binding = _normalized(predicate.source_term or predicate.attribute)
    binding_without_possession = re.sub(r"^有", "", binding)
    binding_terms = {
        binding,
        re.sub(r"(?:发生次数|发作次数|复发次数|既往史|现病史|病史|天数)$", "", binding),
        binding_without_possession,
        re.sub(
            r"(?:发生次数|发作次数|复发次数|既往史|现病史|病史|天数)$",
            "",
            binding_without_possession,
        ),
    }
    binding_terms.discard("")
    if not any(
        any(term in _normalized(clause) for term in binding_terms)
        for clause in frequency_clauses
    ):
        return False
    window = predicate.occurrence_window
    if window is None or (
        window.duration.value != duration or window.duration.unit != duration_unit
    ):
        return False
    if count_unit == "次":
        return bool(
            (
                isinstance(predicate.value, (int, float))
                and not isinstance(predicate.value, bool)
                and predicate.unit == "次"
                and int(predicate.value) == minimum
            )
            or window.minimum_count == minimum
        )
    return bool(
        isinstance(predicate.value, (int, float))
        and not isinstance(predicate.value, bool)
        and predicate.unit in {"天", "日", "day", "days"}
        and int(predicate.value) == minimum
    )


def _source_comparators(text: str) -> set[Comparator]:
    """Return unambiguous comparator classes explicitly expressed in source."""
    found: set[Comparator] = set()
    patterns = (
        (Comparator.GTE, r"≥|大于或等于|不低于|至少"),
        (Comparator.LTE, r"≤|小于或等于|不超过|至多"),
        (Comparator.GT, r"(?<![≥>])>(?!=)|超过|(?<!或等于)大于"),
        (Comparator.LT, r"(?<![≤<])<(?!=)|低于|(?<!或等于)小于"),
    )
    for comparator, pattern in patterns:
        if re.search(pattern, text):
            found.add(comparator)
    return found


def _rule_map(draft: ProtocolDeconstructionDraft) -> dict[str, Rule]:
    return {rule.rule_id: rule for rule in draft.proposed_rules}


class ProtocolDeconstructionGate:
    """Run all twelve checks and return Chinese, repair-scoped issues."""

    def evaluate(
        self,
        source_input: ProtocolDeconstructionInput,
        draft: ProtocolDeconstructionDraft,
        *,
        source_spans: Mapping[str, ProtocolSourceSpan],
        interpretation_conflicts: Sequence[InterpretationConflict] = (),
        previous_draft: ProtocolDeconstructionDraft | None = None,
        declared_diff: ProtocolDraftDiffDeclaration | None = None,
    ) -> ProtocolDeconstructionGateResult:
        issues: dict[str, list[ProtocolGateIssue]] = {name: [] for name in CHECK_NAMES}

        self._identity(source_input, draft, issues["identity"])
        self._phase_scope(source_input, draft, issues["phase_scope"])
        self._parent_catalog(source_input, draft, issues["parent_catalog"])
        self._tree_integrity(draft, issues["tree_integrity"])
        self._boolean_logic(source_input, draft, issues["boolean_logic"])
        self._numeric_semantics(source_input, draft, issues["numeric_semantics"])
        anchor_context = _anchor_resolution_context(
            source_input, interpretation_conflicts
        )
        self._temporal_semantics(
            source_input, draft, issues["temporal_semantics"], anchor_context
        )
        self._workflow_coverage(source_input, draft, issues["workflow_coverage"])
        self._evidence_coverage(draft, issues["evidence_coverage"])
        self._source_coverage(source_input, draft, source_spans, issues["source_coverage"])
        self._interpretation_authority(
            interpretation_conflicts,
            issues["interpretation_authority"],
            anchor_context.authority_issues,
        )
        self._diff_integrity(
            draft, previous_draft, declared_diff, issues["diff_integrity"]
        )

        checks = [
            ProtocolGateCheckResult(
                check_name=name,
                passed=not issues[name],
                issues=issues[name],
            )
            for name in CHECK_NAMES
        ]
        publishable = not any(
            issue.level in {"阻止发布", "需要核对"}
            for result in checks
            for issue in result.issues
        )
        return ProtocolDeconstructionGateResult(publishable=publishable, checks=checks)

    @staticmethod
    def _identity(source_input, draft, issues):
        identity = source_input.identity_decision
        expected_date = str(identity.official_date.value) if identity.official_date else ""
        actual = draft.protocol_metadata
        mismatches = []
        if draft.project_id != source_input.project_id:
            mismatches.append("project_id")
        if draft.protocol_version_id != source_input.protocol_version_id:
            mismatches.append("protocol_version_id")
        if actual.protocol_code_candidate != identity.protocol_code:
            mismatches.append("方案编号")
        if actual.version_candidate != identity.official_version:
            mismatches.append("方案版本")
        if actual.date_candidate != expected_date:
            mismatches.append("方案日期")
        if mismatches:
            issues.append(
                _issue(
                    "identity",
                    "PROTOCOL_IDENTITY_MISMATCH",
                    "草稿中的" + "、".join(mismatches) + "与已确认方案身份不一致。",
                    [draft.draft_id],
                    scope=["protocol_metadata"],
                )
            )

    @staticmethod
    def _phase_scope(source_input, draft, issues):
        wrong = [
            rule.official_code
            for rule in draft.proposed_rules
            if rule.study_phase != source_input.selected_phase
        ]
        if draft.selected_phase != source_input.selected_phase or wrong:
            issues.append(
                _issue(
                    "phase_scope",
                    "STUDY_PHASE_SCOPE_MISMATCH",
                    "草稿包含未选研究期别的规则或期别标识。",
                    wrong or [draft.draft_id],
                    action="请只保留本次已确认期别及明确共同适用的原文内容。",
                )
            )
        allowed = set(source_input.allowed_source_span_ids)
        outside = sorted(
            {
                span_id
                for mapping in (
                    *draft.parent_catalog_mappings,
                    *draft.procedure_catalog_mappings,
                )
                for span_id in mapping.source_span_ids
                if span_id not in allowed
            }
        )
        if outside:
            issues.append(
                _issue(
                    "phase_scope",
                    "SOURCE_OUTSIDE_PHASE_PROJECTION",
                    "草稿引用了本次单期投影之外的方案片段。",
                    outside,
                )
            )

    @staticmethod
    def _parent_catalog(source_input, draft, issues):
        catalog = source_input.parent_rule_catalog
        expected = [item.item_id for item in sorted(catalog.items, key=lambda item: item.position)]
        mappings = draft.parent_catalog_mappings
        actual = [item.catalog_item_id for item in mappings]
        if actual != expected:
            issues.append(
                _issue(
                    "parent_catalog",
                    "PARENT_CATALOG_NOT_EXACTLY_COVERED",
                    "父规则目录的数量、顺序或成员未被草稿逐项完整覆盖。",
                    sorted(set(expected) ^ set(actual)) or expected,
                    action="请按冻结目录顺序逐条恢复，不能删除、补造或合并父规则。",
                )
            )
        rules = _rule_map(draft)
        for item, mapping in zip(sorted(catalog.items, key=lambda value: value.position), mappings):
            rule = rules.get(mapping.proposed_rule_id)
            if rule is None or rule.official_code != item.official_code:
                issues.append(
                    _issue(
                        "parent_catalog",
                        "PARENT_RULE_CODE_MISMATCH",
                        f"冻结条目 {item.item_id} 未映射到相同官方编号的父规则。",
                        [item.item_id, mapping.proposed_rule_id],
                    )
                )
            # 父规则映射的来源必须等于冻结目录项自身来源，不能任意换绑其他
            # 目录/跨期来源；换绑即破坏「目录成员不可增删、来源不可张冠李戴」。
            if tuple(sorted(mapping.source_span_ids)) != tuple(
                sorted(item.source_span_ids)
            ):
                issues.append(
                    _issue(
                        "parent_catalog",
                        "PARENT_MAPPING_SOURCE_MISMATCH",
                        f"冻结条目 {item.item_id} 的目录映射来源与目录项来源不一致。",
                        [item.item_id, *mapping.source_span_ids],
                        action="请让父规则映射的 source_span_ids 与冻结目录项完全一致，"
                        "不得借用其他父规则、跨期片段或降级提示来源。",
                    )
                )

    @staticmethod
    def _tree_integrity(draft, issues):
        if not draft.proposed_rules:
            issues.append(
                _issue(
                    "tree_integrity",
                    "ZERO_RULE_DRAFT",
                    "草稿没有任何入选或排除父规则。",
                    [draft.draft_id],
                )
            )
            return
        rule_ids = {rule.rule_id for rule in draft.proposed_rules}
        mapped = [item.proposed_rule_id for item in draft.parent_catalog_mappings]
        if set(mapped) != rule_ids or len(mapped) != len(rule_ids):
            issues.append(
                _issue(
                    "tree_integrity",
                    "RULE_TREE_MAPPING_MISMATCH",
                    "父规则树与目录映射不是一一对应。",
                    sorted(rule_ids ^ set(mapped)) or sorted(rule_ids),
                )
            )
        display_codes = [
            component.display_code
            for rule in draft.proposed_rules
            for component in rule.components
        ]
        if len(display_codes) != len(set(display_codes)):
            issues.append(
                _issue(
                    "tree_integrity",
                    "DUPLICATE_COMPONENT_CODE",
                    "子规则显示编号重复，父子层级无法唯一定位。",
                    display_codes,
                )
            )
        predicate_ids = [
            predicate.predicate_id
            for rule in draft.proposed_rules
            for component in rule.components
            for expression in (
                component.expression,
                component.exception_expression,
            )
            if expression is not None
            for predicate in iter_atomic_predicates(expression)
        ]
        duplicate_predicate_ids = sorted(
            predicate_id
            for predicate_id, count in Counter(predicate_ids).items()
            if count > 1
        )
        if duplicate_predicate_ids:
            issues.append(
                _issue(
                    "tree_integrity",
                    "DUPLICATE_PREDICATE_ID",
                    "不同规则条件使用了相同的内部身份，无法形成稳定的正式规则集。",
                    duplicate_predicate_ids,
                    action="请保持条件原文和逻辑不变，为每个原子条件建立唯一且稳定的身份。",
                )
            )
        components = {
            component.rule_component_id: component
            for rule in draft.proposed_rules
            for component in rule.components
        }
        component_drafts = {
            item.proposed_component.rule_component_id: item
            for item in draft.component_drafts
        }
        if len(component_drafts) != len(draft.component_drafts):
            issues.append(
                _issue(
                    "tree_integrity",
                    "DUPLICATE_COMPONENT_DRAFT",
                    "子规则来源映射中存在重复的子规则。",
                    sorted(component_drafts) or [draft.draft_id],
                )
            )
        if set(component_drafts) != set(components):
            issues.append(
                _issue(
                    "tree_integrity",
                    "COMPONENT_DRAFT_COVERAGE_MISMATCH",
                    "子规则来源映射没有逐项覆盖规则树中的全部子规则。",
                    sorted(set(component_drafts) ^ set(components))
                    or sorted(components),
                    action="请为每个子规则保留一条 component_drafts 映射，不能留空或漏项。",
                )
            )
        mismatched_components = sorted(
            component_id
            for component_id in set(component_drafts) & set(components)
            if component_drafts[component_id].proposed_component
            != components[component_id]
        )
        if mismatched_components:
            issues.append(
                _issue(
                    "tree_integrity",
                    "COMPONENT_DRAFT_CONTENT_MISMATCH",
                    "子规则来源映射中的结构内容与规则树不一致。",
                    mismatched_components,
                    action="请让 component_drafts 中的 proposed_component 与规则树中的同一子规则完全一致。",
                )
            )
        wrong_parent_refs = sorted(
            component.rule_component_id
            for rule in draft.proposed_rules
            for component in rule.components
            if component.parent_rule_id != rule.rule_id
        )
        if wrong_parent_refs:
            issues.append(
                _issue(
                    "tree_integrity",
                    "COMPONENT_PARENT_RULE_MISMATCH",
                    "部分子规则没有指向其实际所在的父规则。",
                    wrong_parent_refs,
                    action="请恢复子规则与官方父规则的一一归属，不能借用其他父规则 ID。",
                )
            )
        wrong_requirement_refs = sorted(
            requirement.requirement_id
            for rule in draft.proposed_rules
            for component in rule.components
            for requirement in component.evidence_requirements
            if requirement.rule_component_id != component.rule_component_id
        )
        if wrong_requirement_refs:
            issues.append(
                _issue(
                    "tree_integrity",
                    "EVIDENCE_REQUIREMENT_COMPONENT_MISMATCH",
                    "部分资料要求没有指向其实际所属的子规则。",
                    wrong_requirement_refs,
                )
            )
        wrong_parent_codes = sorted(
            component_id
            for component_id, item in component_drafts.items()
            for rule in draft.proposed_rules
            if component_id in {
                component.rule_component_id for component in rule.components
            }
            and item.parent_official_code != rule.official_code
        )
        if wrong_parent_codes:
            issues.append(
                _issue(
                    "tree_integrity",
                    "COMPONENT_PARENT_CODE_MISMATCH",
                    "部分子规则来源映射使用了错误的官方父规则编号。",
                    wrong_parent_codes,
                )
            )

    @staticmethod
    def _boolean_logic(source_input, draft, issues):
        for rule in draft.proposed_rules:
            for component in rule.components:
                text = _component_text(
                    rule,
                    component.rule_component_id,
                    draft,
                    source_input,
                )
                normalized = _normalized(text)
                has_and = any(
                    token in normalized
                    for token in ("且", "并且", "同时", "均需", "全部")
                )
                has_or = _has_unambiguous_disjunction(text) or any(
                    _branches_have_source_disjunction(node, text)
                    for node in _walk_expression_tree(component.expression)
                    if node.kind == "logical"
                )
                expression = component.expression
                expressions = [component.expression]
                if component.exception_expression is not None:
                    expressions.append(component.exception_expression)
                for candidate_expression in expressions:
                    for predicate in _negated_predicates(candidate_expression):
                        if _source_supports_predicate_negation(predicate):
                            continue
                        issues.append(
                            _issue(
                                "boolean_logic",
                                "NEGATION_NOT_BOUND_TO_SOURCE",
                                f"{component.display_code} 的否定逻辑没有与原文中被断言的对象直接绑定。",
                                [predicate.predicate_id],
                                action=(
                                    "请只在原文直接表达‘无、未、否认、不存在’等对该对象的否定时使用逻辑否定；"
                                    "‘阴性’、‘不良事件’、‘非特异性’等应保留为原文分类或术语，不得据此反转整个条件。"
                                ),
                            )
                        )
                    for predicate in iter_atomic_predicates(candidate_expression):
                        if predicate.comparator not in {
                            Comparator.NE,
                            Comparator.NOT_IN,
                        } or _source_supports_negative_comparator(predicate):
                            continue
                        issues.append(
                            _issue(
                                "boolean_logic",
                                "NEGATIVE_COMPARATOR_NOT_BOUND_TO_SOURCE",
                                f"{component.display_code} 的否定比较没有与原文中的比较值直接绑定。",
                                [predicate.predicate_id],
                                action=(
                                    "ne 只能对应原文明确的‘≠/不等于’；not_in 必须直接对应‘不属于、不在、不包括、非’及其后的具体分类值。"
                                ),
                            )
                        )
                unsupported_any = any(
                    node.kind == "logical"
                    and node.operator == LogicalOperator.ANY
                    and not _is_population_scoped_any(node)
                    and not (
                        has_or and _any_branches_preserve_internal_conjunction(node)
                    )
                    and not _any_is_same_event_time_alternatives(node, text)
                    and not _branches_have_source_disjunction(node, text)
                    for node in _walk_expression_tree(expression)
                )
                if (
                    has_and
                    and not has_or
                    and unsupported_any
                ):
                    issues.append(
                        _issue(
                            "boolean_logic",
                            "CONJUNCTION_CHANGED_TO_DISJUNCTION",
                            f"{component.display_code} 原文仅表达并列同时满足，草稿却使用了任一满足。",
                            [component.rule_component_id],
                        )
                    )
                elif unsupported_any:
                    issues.append(
                        _issue(
                            "boolean_logic",
                            "DISJUNCTION_NOT_BOUND_TO_SOURCE",
                            f"{component.display_code} 的任一满足分支没有与原文中各分支及其‘或/任一’连接语直接绑定。",
                            [component.rule_component_id],
                            action=(
                                "请让每个任一满足分支分别对应原文中的完整条件；"
                                "顿号、逗号和普通并列列举只是术语清单，原文没有明确‘或/任一/之一’时不得拆成替代分支或补写‘或’；"
                                "‘筛选或基线’是审核节点，‘2次或以上’是次数阈值，都不能单独作为触发条件的替代路径。"
                            ),
                        )
                    )
                if (
                    has_or
                    and not has_and
                    and expression.kind == "logical"
                    and expression.operator == LogicalOperator.ALL
                    and not any(
                        node.kind == "logical"
                        and node.operator == LogicalOperator.ANY
                        for node in _walk_expression_tree(expression)
                    )
                ):
                    issues.append(
                        _issue(
                            "boolean_logic",
                            "DISJUNCTION_CHANGED_TO_CONJUNCTION",
                            f"{component.display_code} 原文表达任选其一，草稿却要求全部满足。",
                            [component.rule_component_id],
                        )
                    )
                trigger_clauses = [
                    clause
                    for predicate in iter_atomic_predicates(component.expression)
                    for clause in predicate.exact_source_clauses
                ]
                has_exception = _exception_applies_to_trigger(
                    text, trigger_clauses
                ) or any(
                    token in _normalized("\n".join(trigger_clauses))
                    for token in ("除外", "除非", "但不包括", "例外")
                )
                if has_exception and component.exception_expression is None:
                    issues.append(
                        _issue(
                            "boolean_logic",
                            "EXCEPTION_NOT_STRUCTURED",
                            f"{component.display_code} 原文含例外条件，但草稿没有独立例外表达式。",
                            [component.rule_component_id],
                        )
                    )
                if component.exception_expression is not None:
                    parenthetical_exceptions = list(
                        re.finditer(
                            r"[（(][^）)]*(?:除外|除非|例外)[^）)]*[）)]",
                            text,
                        )
                    )
                    trigger_positions = [
                        text.find(clause)
                        for clause in trigger_clauses
                        if clause and text.find(clause) >= 0
                    ]
                    if parenthetical_exceptions and trigger_positions:
                        trigger_start = min(trigger_positions)
                        misplaced = any(
                            trigger_start >= match.end()
                            and "或" in text[match.end() : trigger_start + 1]
                            for match in parenthetical_exceptions
                        )
                        if misplaced:
                            issues.append(
                                _issue(
                                    "boolean_logic",
                                    "EXCEPTION_SCOPE_CHANGED",
                                    f"{component.display_code} 把前一并列分支中的括号例外错误套到了后续分支。",
                                    [component.rule_component_id],
                                    action="括号内例外只作用于括号紧邻的触发分支；请从后续‘或’分支删除该例外，并保留原分支自己的例外。",
                                )
                            )
                    if (
                        _localized_open_list_exception_requires_exclusivity(text)
                        and not _exception_asserts_exclusivity(
                            component.exception_expression
                        )
                    ):
                        issues.append(
                            _issue(
                                "boolean_logic",
                                "LOCAL_EXCEPTION_MAY_WAIVE_CONCURRENT_TRIGGER",
                                f"{component.display_code} 的局部例外可能错误豁免同时存在的其他触发情况。",
                                [component.rule_component_id],
                                action=(
                                    "开放列举中的括号例外只排除其紧邻实例。若保留组件级例外，"
                                    "请明确结构化为该例外是唯一相关情况；否则拆分为不会互相豁免的独立触发组件。"
                                ),
                            )
                        )
                    if (
                        parenthetical_exceptions
                        and component.expression.kind == "logical"
                        and component.expression.operator == LogicalOperator.ANY
                    ):
                        issues.append(
                            _issue(
                                "boolean_logic",
                                "EXCEPTION_SCOPE_CHANGED",
                                f"{component.display_code} 的组件级括号例外会错误作用于全部任选分支。",
                                [component.rule_component_id],
                                action="请把带括号例外的触发分支拆成独立子组件，并把后续‘或’分支放入不带该例外的兄弟子组件。",
                            )
                        )
                if not _source_requires_investigator_judgment(text):
                    continue
                predicates = list(iter_atomic_predicates(component.expression))
                if component.exception_expression is not None:
                    predicates.extend(
                        iter_atomic_predicates(component.exception_expression)
                    )
                if not any(item.requires_professional_judgment for item in predicates):
                    issues.append(
                        _issue(
                            "boolean_logic",
                            "INVESTIGATOR_JUDGMENT_DROPPED",
                            f"{component.display_code} 的并列条件含研究者判断，草稿未保留专业判断谓词。",
                            [component.rule_component_id],
                        )
                    )

    @staticmethod
    def _numeric_semantics(source_input, draft, issues):
        for rule in draft.proposed_rules:
            for component in rule.components:
                component_draft = next(
                    (
                        item
                        for item in draft.component_drafts
                        if item.proposed_component.rule_component_id
                        == component.rule_component_id
                    ),
                    None,
                )
                has_precise_excerpt = bool(
                    component_draft and component_draft.source_excerpts
                )
                text = _component_text(
                    rule,
                    component.rule_component_id,
                    draft,
                    source_input,
                )
                expressions = [component.expression]
                if component.exception_expression is not None:
                    expressions.append(component.exception_expression)
                for expression in expressions:
                    for predicate in iter_atomic_predicates(expression):
                        predicate_text = (
                            _predicate_text(predicate) if has_precise_excerpt else text
                        )
                        source_numbers = _numeric_tokens(predicate_text)
                        source_comparators = _source_comparators(predicate_text)
                        normalized = _normalized(predicate_text)
                        predicate_values = (
                            predicate.value
                            if isinstance(predicate.value, list)
                            else [predicate.value]
                        )
                        has_numeric_value = any(
                            isinstance(value, (int, float))
                            and not isinstance(value, bool)
                            for value in predicate_values
                        )
                        frequency_specs = _source_frequency_specs(predicate_text)
                        is_structured_frequency = bool(frequency_specs) and any(
                            _predicate_preserves_frequency(predicate, spec)
                            for spec in frequency_specs
                        )
                        if (
                            has_numeric_value
                            and len(source_comparators) == 1
                            and predicate.comparator not in source_comparators
                        ):
                            issues.append(
                                _issue(
                                    "numeric_semantics",
                                    "COMPARATOR_CHANGED",
                                    f"{component.display_code} 的比较方向与原文不一致。",
                                    [predicate.predicate_id],
                                )
                            )
                        for value in predicate_values:
                            if isinstance(value, (int, float)) and not isinstance(
                                value, bool
                            ):
                                rendered = str(value)
                                if rendered not in source_numbers:
                                    issues.append(
                                        _issue(
                                            "numeric_semantics",
                                            "NUMERIC_VALUE_NOT_IN_SOURCE",
                                            f"{component.display_code} 的数值 {rendered} 无法在本子项原文中核对。",
                                            [predicate.predicate_id],
                                        )
                                    )
                        if (
                            has_numeric_value
                            and has_precise_excerpt
                            and not is_structured_frequency
                        ):
                            source_term = _normalized(predicate.source_term or "")
                            if not source_term or source_term not in normalized:
                                issues.append(
                                    _issue(
                                        "numeric_semantics",
                                        "METRIC_NOT_IN_SOURCE",
                                        f"{component.display_code} 的数值条件未绑定本子项原文中可核对的指标名称。",
                                        [predicate.predicate_id],
                                        action="请在 source_term 逐字填写本数值的原文指标名，避免把兄弟子项的检验指标套入当前阈值。",
                                    )
                                )
                            else:
                                metric_identity = _normalized(
                                    f"{predicate.subject}{predicate.attribute}"
                                )
                                normalized_unit = _normalized(predicate.unit or "")
                                binds_metric_identity = bool(metric_identity) and (
                                    source_term in metric_identity
                                    or metric_identity in source_term
                                )
                                if (
                                    source_term == normalized_unit
                                    or not binds_metric_identity
                                ):
                                    issues.append(
                                        _issue(
                                            "numeric_semantics",
                                            "METRIC_SOURCE_TERM_NOT_METRIC",
                                            f"{component.display_code} 的原文指标词未绑定当前被测对象。",
                                            [predicate.predicate_id],
                                            action="请在 source_term 填写原文指标名，例如‘年龄’、‘病史’、‘ALT’；不得填‘岁’、‘月’、‘ULN’等单位或阈值。",
                                        )
                                    )
                        elif not has_precise_excerpt:
                            attribute = _normalized(predicate.attribute)
                            if (
                                re.fullmatch(r"[a-z][a-z0-9_-]{1,15}", attribute)
                                and attribute not in normalized
                            ):
                                issues.append(
                                    _issue(
                                        "numeric_semantics",
                                        "METRIC_NOT_IN_SOURCE",
                                        f"{component.display_code} 使用了本子项原文未出现的指标 {predicate.attribute}。",
                                        [predicate.predicate_id],
                                        action="请核对指标名称，避免把同一父规则其他子项的检验项目套入本子项阈值；若原文多个阈值共用前置指标名称，请用 source_clauses 分别绑定含指标名称的逐字片段和当前阈值片段。",
                                    )
                                )
                        unit = predicate.unit or ""
                        if has_numeric_value and unit == "__missing_from_agent__":
                            issues.append(
                                _issue(
                                    "numeric_semantics",
                                    "NUMERIC_UNIT_MISSING",
                                    f"{component.display_code} 的数值条件未声明单位或无量纲。",
                                    [predicate.predicate_id],
                                    action="请按原文填写 unit；评分、分级等无量纲数值显式填 unitless。",
                                )
                            )
                        elif not _unit_matches_source(unit, predicate_text):
                            issues.append(
                                _issue(
                                    "numeric_semantics",
                                    "UNIT_NOT_IN_SOURCE",
                                    f"{component.display_code} 的单位 {predicate.unit} 无法在本子项原文中核对。",
                                    [predicate.predicate_id],
                                )
                            )

    @staticmethod
    def _temporal_semantics(source_input, draft, issues, anchor_context=None):
        if anchor_context is None:
            anchor_context = _AnchorResolutionContext()
        anchor_markers = {
            AnchorType.RANDOMIZATION_DATE: ("随机前", "随机后", "随机时"),
            AnchorType.BASELINE_DATE: (
                "基线前",
                "基线后",
                "基线访视前",
                "基线访视后",
            ),
            AnchorType.SCREENING_DATE: (
                "筛选前",
                "筛选后",
                "筛选访视前",
                "筛选访视后",
            ),
            AnchorType.ICF_DATE: (
                "知情同意前",
                "知情同意后",
                "签署ICF时",
            ),
            AnchorType.FIRST_DOSE_DATE: (
                "首次给药前",
                "首次给药后",
                "首剂前",
                "首剂后",
                "第一次给药前",
                "第一次给药后",
            ),
            AnchorType.STUDY_DRUG_ADMINISTRATION_DATE: (
                "研究药物给药前",
                "研究药物给药后",
                "试验药物给药前",
                "试验药物给药后",
            ),
            AnchorType.LAST_DOSE_DATE: (
                "末次给药后",
                "最后一次给药后",
            ),
            AnchorType.STUDY_COMPLETION_DATE: (
                "研究完成后",
                "研究结束后",
            ),
        }
        resolved_component_bindings: dict[
            tuple[str, str], list[AnchorResolutionStatement]
        ] = {}
        rules_with_unanchored_lookback: set[str] = set()
        for rule in draft.proposed_rules:
            for component in rule.components:
                component_text = _component_text(
                    rule,
                    component.rule_component_id,
                    draft,
                    source_input,
                )
                roots = [component.expression]
                if component.exception_expression is not None:
                    roots.append(component.exception_expression)
                component_draft = next(
                    (
                        item
                        for item in draft.component_drafts
                        if item.proposed_component.rule_component_id
                        == component.rule_component_id
                    ),
                    None,
                )
                has_precise_excerpt = bool(
                    component_draft and component_draft.source_excerpts
                )
                atomic_expressions = [
                    expression
                    for root in roots
                    for expression in _walk_expression_tree(root)
                    if expression.kind == "predicate"
                ]
                component_frequency_specs = _source_frequency_specs(component_text)
                missing_frequency_specs = {
                    spec
                    for spec in component_frequency_specs
                    if not any(
                        _predicate_preserves_frequency(expression.predicate, spec)
                        for expression in atomic_expressions
                    )
                }
                if missing_frequency_specs:
                    rendered = "、".join(
                        f"{duration}{unit.value}内至少{minimum}{count_unit}"
                        for duration, unit, minimum, count_unit in sorted(
                            missing_frequency_specs,
                            key=lambda item: (item[1].value, item[0], item[2], item[3]),
                        )
                    )
                    issues.append(
                        _issue(
                            "temporal_semantics",
                            "FREQUENCY_WINDOW_NOT_STRUCTURED",
                            f"{component.display_code} 原文中的频次定义 {rendered} 没有形成直接绑定原文的可计算结构。",
                            [component.rule_component_id],
                            action=_frequency_repair_action(),
                        )
                    )
                compact_component_text = re.sub(r"\s+", "", component_text)
                required_stages: set[ReviewStage] = set()
                if re.search(r"筛选(?:期|访视)?时", compact_component_text) or re.search(
                    r"筛选(?:期|访视)?(?:或|和|及|与|、)基线(?:期|访视)?时",
                    compact_component_text,
                ):
                    required_stages.add(ReviewStage.SCREENING)
                if re.search(r"基线(?:期|访视)?时", compact_component_text):
                    required_stages.add(ReviewStage.BASELINE)
                baseline_decision_anchors = {
                    AnchorType.BASELINE_DATE,
                    AnchorType.RANDOMIZATION_DATE,
                    AnchorType.FIRST_DOSE_DATE,
                    AnchorType.STUDY_DRUG_ADMINISTRATION_DATE,
                }
                if any(
                    expression.time_constraint is not None
                    and expression.time_constraint.anchor_type
                    in baseline_decision_anchors
                    and expression.time_constraint.direction
                    in {TimeDirection.BEFORE, TimeDirection.ON}
                    for expression in atomic_expressions
                ):
                    required_stages.add(ReviewStage.BASELINE)
                actual_stages = {
                    requirement.due_stage
                    for requirement in component.evidence_requirements
                }
                missing_stages = required_stages - actual_stages
                if missing_stages:
                    stage_names = {
                        ReviewStage.SCREENING: "筛选期",
                        ReviewStage.BASELINE: "基线",
                    }
                    issues.append(
                        _issue(
                            "temporal_semantics",
                            "REVIEW_STAGE_REQUIREMENT_MISSING",
                            f"{component.display_code} 未分别建立"
                            + "、".join(
                                stage_names[stage]
                                for stage in sorted(
                                    missing_stages, key=lambda item: item.value
                                )
                            )
                            + "的资料核对要求。",
                            [component.rule_component_id],
                            action="请保留一个原子条件，并为原文明确要求的每个审核阶段分别建立 due_stage 资料要求；以基线、随机或首次给药为锚点的前置条件必须在基线节点完成最终复核，筛选期提前关注不能替代该节点；不要复制原子条件或添加日期约束。",
                        )
                    )
                component_validity_specs = _source_validity_specs(component_text)
                predicate_validity_windows = {
                    window
                    for expression in atomic_expressions
                    for window in _source_validity_windows(
                        _predicate_text(expression.predicate)
                    )
                }
                for value, unit, named_item in sorted(
                    component_validity_specs,
                    key=lambda item: (item[1].value, item[0], item[2]),
                ):
                    if (value, unit) in predicate_validity_windows:
                        continue
                    matching_requirements = [
                        requirement
                        for requirement in component.evidence_requirements
                        if _requirement_matches_validity_spec(requirement, named_item)
                    ]
                    expected_validity_stages = required_stages or {
                        requirement.due_stage for requirement in matching_requirements
                    }
                    missing_validity_stages = [
                        stage
                        for stage in expected_validity_stages
                        if not any(
                            requirement.due_stage == stage
                            and requirement.source_validity_window is not None
                            and requirement.source_validity_window.value == value
                            and requirement.source_validity_window.unit == unit
                            for requirement in matching_requirements
                        )
                    ]
                    if not expected_validity_stages or missing_validity_stages:
                        stage_names = {
                            ReviewStage.PRE_SCREENING: "预筛选期",
                            ReviewStage.SCREENING: "筛选期",
                            ReviewStage.RUN_IN: "筛选/导入期",
                            ReviewStage.BASELINE: "基线",
                        }
                        unit_names = {
                            TimeUnit.DAY: "天",
                            TimeUnit.WEEK: "周",
                            TimeUnit.MONTH: "个月",
                            TimeUnit.YEAR: "年",
                        }
                        missing_text = "、".join(
                            f"{stage_names.get(stage, stage.value)}{value}{unit_names[unit]}"
                            for stage in sorted(
                                missing_validity_stages, key=lambda item: item.value
                            )
                        )
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "SOURCE_VALIDITY_WINDOW_MISSING",
                                f"{component.display_code} 的{named_item}检查结果时效未按具体资料和审核节点完整保留"
                                + (f"：{missing_text}" if missing_text else "")
                                + "。",
                                [component.rule_component_id],
                                action="请为原文点名的检查在每个审核节点分别建立资料要求，并逐项保留可接受的检查结果时效；不得把时效绑定到同条规则中的其他检查。",
                            )
                        )
                if not _has_unambiguous_disjunction(component_text):
                    source_quantities = _source_time_quantities(component_text)
                    source_quantities -= {
                        (value, unit)
                        for value, unit, _named_item in component_validity_specs
                    }
                    bound_quantities = {
                        quantity
                        for expression in atomic_expressions
                        for quantity in _source_time_quantities(
                            _predicate_text(expression.predicate)
                        )
                    }
                    dropped_quantities = sorted(
                        source_quantities - bound_quantities,
                        key=lambda item: (item[1].value, item[0]),
                    )
                    if dropped_quantities:
                        rendered = "、".join(
                            f"{value}{unit.value}"
                            for value, unit in dropped_quantities
                        )
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "TIME_QUALIFIER_DROPPED",
                                f"{component.display_code} 原文中的时间限定 {rendered} 没有绑定任何原子条件。",
                                [component.rule_component_id],
                                action="请把该时间限定及其直接限定的事件逐字绑定到原子条件；若原文没有命名回溯锚点，继续保留时间范围并标记为待确认，不得删除限定语。",
                            )
                        )
                for expression in atomic_expressions:
                    predicate = expression.predicate
                    predicate_text = (
                        _predicate_temporal_text(predicate)
                        if has_precise_excerpt
                        else component_text
                    )
                    expected = {
                        anchor
                        for anchor, markers in anchor_markers.items()
                        if any(marker in predicate_text for marker in markers)
                    }
                    component_expected = {
                        anchor
                        for anchor, markers in anchor_markers.items()
                        if any(marker in component_text for marker in markers)
                    }
                    constraint = expression.time_constraint
                    has_before = any(
                        marker.endswith("前") and marker in predicate_text
                        for markers in anchor_markers.values()
                        for marker in markers
                    )
                    has_on = any(
                        marker.endswith("时") and marker in predicate_text
                        for markers in anchor_markers.values()
                        for marker in markers
                    )
                    has_after = any(
                        marker.endswith("后") and marker in predicate_text
                        for markers in anchor_markers.values()
                        for marker in markers
                    )
                    has_explicit_window = bool(
                        _source_time_quantities(predicate_text)
                    ) or bool(
                        re.search(
                            r"\d+(?:\.\d+)?\s*个?药物?半衰期",
                            predicate_text,
                        )
                    )
                    predicate_frequency_specs = _source_frequency_specs(predicate_text)
                    is_frequency_definition = bool(predicate_frequency_specs)
                    source_validity_windows = _source_validity_windows(predicate_text)
                    predicate_validity_specs = _source_validity_specs(predicate_text)
                    is_future_plan_window = any(
                        marker in predicate_text
                        for marker in (
                            "计划",
                            "治疗期间",
                            "研究完成后",
                            "研究结束后",
                            "末次给药后",
                            "最后一次给药后",
                        )
                    )
                    contextual_text = f"{predicate_text}\n{component_text}"
                    has_multiple_review_anchors = bool(
                        re.search(
                            r"筛选(?:期|访视)?(?:或|和|及|与|、)"
                            r"基线(?:期|访视)?时",
                            contextual_text,
                        )
                    )
                    has_contextual_review_anchor = (
                        not has_multiple_review_anchors
                        and bool(
                            re.search(
                                r"(?:筛选|基线)(?:期|访视)?时",
                                contextual_text,
                            )
                        )
                    )
                    is_unanchored_lookback = (
                        has_explicit_window
                        and not expected
                        and not component_expected
                        and not has_contextual_review_anchor
                        and "内" in predicate_text
                        and not is_frequency_definition
                        and not source_validity_windows
                        and not is_future_plan_window
                    )
                    if is_unanchored_lookback:
                        rules_with_unanchored_lookback.add(rule.official_code)
                    occurrence_window = predicate.occurrence_window
                    prospective_window = predicate.prospective_window
                    prospective_period = predicate.prospective_period
                    if source_validity_windows:
                        normalized_predicate_text = _normalized(predicate_text)
                        matching_requirements = [
                            requirement
                            for requirement in component.evidence_requirements
                            if (
                                any(
                                    value == validity_value
                                    and unit == validity_unit
                                    and _requirement_matches_validity_spec(
                                        requirement, named_item
                                    )
                                    for validity_value, validity_unit, named_item
                                    in predicate_validity_specs
                                )
                                or (
                                    not predicate_validity_specs
                                    and len(_normalized(requirement.fact_type)) >= 2
                                    and _normalized(requirement.fact_type)
                                    in normalized_predicate_text
                                )
                            )
                        ]
                        expected_validity_stages = required_stages or {
                            requirement.due_stage
                            for requirement in matching_requirements
                        }
                        missing_validity: list[str] = []
                        stage_names = {
                            ReviewStage.PRE_SCREENING: "预筛选期",
                            ReviewStage.SCREENING: "筛选期",
                            ReviewStage.RUN_IN: "筛选/导入期",
                            ReviewStage.BASELINE: "基线",
                        }
                        unit_names = {
                            TimeUnit.DAY: "天",
                            TimeUnit.WEEK: "周",
                            TimeUnit.MONTH: "个月",
                            TimeUnit.YEAR: "年",
                        }
                        for stage in sorted(
                            expected_validity_stages, key=lambda item: item.value
                        ):
                            for value, unit in sorted(
                                source_validity_windows,
                                key=lambda item: (item[1].value, item[0]),
                            ):
                                if not any(
                                    requirement.due_stage == stage
                                    and requirement.source_validity_window is not None
                                    and requirement.source_validity_window.value == value
                                    and requirement.source_validity_window.unit == unit
                                    for requirement in matching_requirements
                                ):
                                    missing_validity.append(
                                        f"{stage_names.get(stage, stage.value)}{value}{unit_names[unit]}"
                                    )
                        if not expected_validity_stages or missing_validity:
                            issues.append(
                                _issue(
                                    "temporal_semantics",
                                    "SOURCE_VALIDITY_WINDOW_MISSING",
                                    f"{component.display_code} 的检查结果时效未按具体资料和审核节点完整保留"
                                    + (
                                        "：" + "、".join(missing_validity)
                                        if missing_validity
                                        else ""
                                    )
                                    + "。",
                                    [predicate.predicate_id],
                                    action="请为该项检查在原文指定的每个审核节点分别建立资料要求，并逐项保留可接受的检查结果时效；不得用同一条规则中的其他检查代替。",
                                )
                            )
                    if is_frequency_definition:
                        frequency_valid = all(
                            _predicate_preserves_frequency(predicate, spec)
                            for spec in predicate_frequency_specs
                        )
                        if not frequency_valid:
                            issues.append(
                                _issue(
                                    "temporal_semantics",
                                    "FREQUENCY_WINDOW_NOT_STRUCTURED",
                                    f"{component.display_code} 的发生次数和频率周期没有形成可计算结构。",
                                    [predicate.predicate_id],
                                    action="若频率本身是触发条件，请用数值谓词保存次数及‘次’单位；若频率是宽泛病史条件中的括号定义，请在 occurrence_window.minimum_count 保存最小次数。两种情况都用 occurrence_window.duration 逐字保留周期。",
                                )
                            )
                    elif occurrence_window is not None:
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "FREQUENCY_WINDOW_NOT_IN_SOURCE",
                                f"{component.display_code} 为非频率条件添加了发生周期。",
                                [predicate.predicate_id],
                            )
                        )
                    future_anchors = {
                        AnchorType.STUDY_DRUG_ADMINISTRATION_DATE,
                        AnchorType.LAST_DOSE_DATE,
                        AnchorType.STUDY_COMPLETION_DATE,
                    }
                    expected_future = expected & future_anchors
                    if expected_future and has_explicit_window:
                        prospective_valid = (
                            prospective_window is not None
                            and prospective_window.anchor_type in expected_future
                            and _time_bound_matches_source(
                                prospective_window.upper_bound.value,
                                prospective_window.upper_bound.unit,
                                predicate_text,
                            )
                        )
                        if not prospective_valid:
                            issues.append(
                                _issue(
                                    "temporal_semantics",
                                    "PROSPECTIVE_WINDOW_NOT_STRUCTURED",
                                    f"{component.display_code} 的未来计划截止范围没有形成可计算结构。",
                                    [predicate.predicate_id],
                                    action="请拆分未来计划分支，并用 prospective_window 保存研究药物给药日、研究完成日或末次给药日及原文时长。",
                                )
                            )
                    elif prospective_window is not None:
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "PROSPECTIVE_WINDOW_NOT_IN_SOURCE",
                                f"{component.display_code} 为原文未给出的未来计划添加了截止范围。",
                                [predicate.predicate_id],
                            )
                        )
                    expected_periods: set[ProtocolPeriod] = set()
                    if "治疗期间" in predicate_text:
                        expected_periods.add(ProtocolPeriod.TREATMENT_PERIOD)
                    if "研究期间" in predicate_text:
                        expected_periods.add(ProtocolPeriod.STUDY_PERIOD)
                    if expected_periods:
                        period_valid = (
                            prospective_period is not None
                            and prospective_period.period in expected_periods
                        )
                        if not period_valid:
                            issues.append(
                                _issue(
                                    "temporal_semantics",
                                    "PROSPECTIVE_PERIOD_NOT_STRUCTURED",
                                    f"{component.display_code} 的未来计划适用期间没有形成明确结构。",
                                    [predicate.predicate_id],
                                    action="请拆分未来计划分支，并用 prospective_period 保存 treatment_period 或 study_period。",
                                )
                            )
                    elif prospective_period is not None:
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "PROSPECTIVE_PERIOD_NOT_IN_SOURCE",
                                f"{component.display_code} 为原文未给出的未来计划添加了适用期间。",
                                [predicate.predicate_id],
                            )
                        )
                    if (
                        (has_before or has_after)
                        and has_explicit_window
                        and constraint is None
                        and prospective_window is None
                        and not expected_future
                    ):
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "TIME_ANCHOR_MISSING",
                                f"{component.display_code} 的原子条件含明确时间锚点，草稿却没有时间约束。",
                                [predicate.predicate_id],
                            )
                        )
                        continue
                    if (
                        constraint is None and is_unanchored_lookback
                    ):
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "TIME_ANCHOR_UNRESOLVED",
                                f"{component.display_code} 写明了既往回溯范围，但方案片段没有说明从哪个日期回溯。",
                                [predicate.predicate_id],
                                action="不得把该范围静默当成无限期病史，也不得自行猜测筛选日或随机日；请保留为待确认的方案解释问题。频率定义和未来计划不属于这种回溯缺口。",
                            )
                        )
                        continue
                    if constraint is None:
                        continue
                    stage_only_constraint = (
                        constraint.direction.value == "on"
                        and constraint.anchor_type
                        in {AnchorType.SCREENING_DATE, AnchorType.BASELINE_DATE}
                        and bool(required_stages)
                    )
                    if stage_only_constraint:
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "REVIEW_STAGE_USED_AS_DATE_CONSTRAINT",
                                f"{component.display_code} 把审核阶段误建成了日期约束。",
                                [predicate.predicate_id, constraint.anchor_type.value],
                                action="请删除该 time_constraint，只保留一个原子条件，并用 screening、baseline 等 due_stage 资料要求表达各审核阶段。",
                            )
                        )
                        continue
                    review_node_binding_ok = False
                    if constraint.anchor_type == AnchorType.REVIEW_NODE_DATE:
                        if expected or component_expected:
                            issues.append(
                                _issue(
                                    "temporal_semantics",
                                    "INTERPRETATION_ANCHOR_REJECTED",
                                    f"{component.display_code} 的原文已命名时间锚点，不得改用审核节点日期锚点替代。",
                                    [predicate.predicate_id],
                                    action="命名锚点以方案原文为准；审核节点日期锚点只用于原文确实未命名回溯锚点的条款。",
                                )
                            )
                            continue
                        review_node_binding_ok = (
                            ProtocolDeconstructionGate._evaluate_review_node_constraint(
                                rule,
                                component,
                                component_draft,
                                predicate.predicate_id,
                                constraint,
                                anchor_context,
                                resolved_component_bindings,
                                issues,
                            )
                        )
                        if not review_node_binding_ok:
                            continue
                    if not expected and not review_node_binding_ok:
                        direction_suffix = {
                            "before": "前",
                            "after": "后",
                            "on": "时",
                        }[constraint.direction.value]
                        shared_direction_matches = any(
                            marker.endswith(direction_suffix)
                            and marker in component_text
                            for marker in anchor_markers.get(
                                constraint.anchor_type, ()
                            )
                        )
                        if (
                            constraint.anchor_type in component_expected
                            and constraint.anchor_type != AnchorType.EVENT_DATE
                            and shared_direction_matches
                        ):
                            issues.append(
                                _issue(
                                    "temporal_semantics",
                                    "SHARED_TIME_QUALIFIER_NOT_BOUND",
                                    f"{component.display_code} 的日期约束来自组件共享限定语，但当前原子条件没有逐字绑定该限定语。",
                                    [predicate.predicate_id],
                                    action="请保留正确的 time_constraint，并把父级或并列分支共享的时间限定语与当前分支文字分别逐字填入 source_clauses；不得删除正确时间窗，也不得把不连续片段拼成一句。",
                                )
                            )
                            continue
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "TIME_CONSTRAINT_NOT_IN_SOURCE",
                                f"{component.display_code} 为原文未给出日期锚点的原子条件添加了时间约束。",
                                [predicate.predicate_id],
                                action="请删除凭空添加的日期锚点或时间窗；‘研究期间计划/需要’是未来意图，不等于方案已给出随机日后的事件日期。",
                            )
                        )
                        continue
                    if constraint.anchor_type not in expected:
                        if review_node_binding_ok:
                            pass
                        else:
                            issues.append(
                                _issue(
                                    "temporal_semantics",
                                    "TIME_ANCHOR_CHANGED",
                                    f"{component.display_code} 的时间锚点与当前原子条件原文不一致。",
                                    [
                                        predicate.predicate_id,
                                        constraint.anchor_type.value,
                                    ],
                                    action="请按当前原子条件保留随机、基线、筛选或知情同意的实际锚点，不能互相替代。",
                                )
                            )
                    if has_before and not has_on and constraint.direction.value != "before":
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "TIME_DIRECTION_CHANGED",
                                f"{component.display_code} 的时间方向与本子项原文“前”不一致。",
                                [predicate.predicate_id],
                            )
                        )
                    if has_on and not has_before and constraint.direction.value != "on":
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "TIME_DIRECTION_CHANGED",
                                f"{component.display_code} 的时间方向与本子项原文“时”不一致。",
                                [predicate.predicate_id],
                            )
                        )
                    if (
                        has_after
                        and not has_before
                        and not has_on
                        and constraint.direction.value != "after"
                    ):
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "TIME_DIRECTION_CHANGED",
                                f"{component.display_code} 的时间方向与本子项原文“后”不一致。",
                                [predicate.predicate_id],
                            )
                        )
                    source_numbers = _numeric_tokens(predicate_text)
                    time_bounds = (
                        (constraint.lower_bound_days, TimeUnit.DAY, "下界"),
                        (constraint.upper_bound_days, TimeUnit.DAY, "上界"),
                        (
                            constraint.lower_bound.value
                            if constraint.lower_bound is not None
                            else None,
                            constraint.lower_bound.unit
                            if constraint.lower_bound is not None
                            else None,
                            "下界",
                        ),
                        (
                            constraint.upper_bound.value
                            if constraint.upper_bound is not None
                            else None,
                            constraint.upper_bound.unit
                            if constraint.upper_bound is not None
                            else None,
                            "上界",
                        ),
                    )
                    for value, unit, bound_name in time_bounds:
                        if value is None or unit is None:
                            continue
                        if _time_bound_matches_source(value, unit, predicate_text):
                            continue
                        if not _numeric_value_in_tokens(value, source_numbers):
                            issues.append(
                                _issue(
                                    "temporal_semantics",
                                    "TIME_BOUND_NOT_IN_SOURCE",
                                    f"{component.display_code} 的{bound_name}数值 {value} 无法在本子项原文中核对。",
                                    [predicate.predicate_id],
                                )
                            )
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "TIME_BOUND_UNIT_CHANGED",
                                f"{component.display_code} 的{bound_name} {value}{unit.value}与本子项原文时间单位不一致。",
                                [predicate.predicate_id],
                                action="请保留方案原文的天、周、月或年单位；只有周与日的严格七日等价可核对，月和年不得换算成固定天数。",
                            )
                        )
                    if (
                        constraint.half_life_multiplier is not None
                        and not _numeric_value_in_tokens(
                            constraint.half_life_multiplier, source_numbers
                        )
                    ):
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                "TIME_BOUND_NOT_IN_SOURCE",
                                f"{component.display_code} 的半衰期倍数 {constraint.half_life_multiplier} 无法在本子项原文中核对。",
                                [predicate.predicate_id],
                            )
                        )
        ProtocolDeconstructionGate._verify_anchor_resolution_coverage(
            draft,
            anchor_context,
            rules_with_unanchored_lookback,
            resolved_component_bindings,
            issues,
        )

    @staticmethod
    def _evaluate_review_node_constraint(
        rule,
        component,
        component_draft,
        predicate_id,
        constraint,
        anchor_context,
        resolved_bindings,
        issues,
    ) -> bool:
        """审核节点日期锚点只在合法解释解析绑定下可发布；越权失败关闭。

        返回 True 表示绑定有效，调用方仍需继续执行逐字窗口核验；返回 False
        表示已生成失败关闭问题。
        """

        refs = [component.rule_component_id, predicate_id]
        if constraint.direction != TimeDirection.BEFORE:
            issues.append(
                _issue(
                    "temporal_semantics",
                    "INTERPRETATION_ANCHOR_REJECTED",
                    f"{component.display_code} 的审核节点日期锚点只能以 before 方向表达既往回溯。",
                    refs,
                    action="请保留唯一正式原子条件，并使用 direction=before 与原文逐字时长；不得改为 after 或 on。",
                )
            )
            return False
        candidates = anchor_context.resolutions_for_rule(rule.official_code)
        if not candidates:
            issues.append(
                _issue(
                    "temporal_semantics",
                    "INTERPRETATION_ANCHOR_REJECTED",
                    f"{component.display_code} 使用了审核节点日期锚点，但没有来源明确的解释材料解析该未命名回溯锚点。",
                    refs,
                    action="没有解释来源时必须保留待确认的回溯缺口，不得自行使用审核节点日期锚点。",
                )
            )
            return False
        component_source_refs = (
            set(component_draft.source_refs) if component_draft is not None else set()
        )
        matched = [
            resolution
            for resolution in candidates
            if component_source_refs & set(resolution.ambiguous_source_refs)
        ]
        if not matched:
            issues.append(
                _issue(
                    "temporal_semantics",
                    "INTERPRETATION_ANCHOR_REJECTED",
                    f"{component.display_code} 的方案来源定位与解释解析声明的歧义来源不匹配。",
                    sorted(
                        {resolution.resolution_id for resolution in candidates}
                    )
                    + refs,
                    action="解释只能解析其声明的原歧义条款；请核对解析绑定的方案来源定位与该原子条件来源是否一致。",
                )
            )
            return False
        resolved_bindings[(rule.official_code, component.rule_component_id)] = matched
        return True

    @staticmethod
    def _verify_anchor_resolution_coverage(
        draft,
        anchor_context,
        rules_with_unanchored_lookback,
        resolved_bindings,
        issues,
    ) -> None:
        """解析声明的规则必须有未命名回溯缺口、目标节点必须存在，且绑定组件的
        资料要求必须覆盖全部目标审核节点。"""

        if not anchor_context.bindings:
            return
        stage_values = {stage.stage for stage in draft.proposed_workflow_stages}
        rules_by_code = {rule.official_code: rule for rule in draft.proposed_rules}
        for _source, resolution in anchor_context.bindings:
            for code in resolution.affected_rule_refs:
                refs = [resolution.resolution_id, code]
                if code not in rules_by_code:
                    issues.append(
                        _issue(
                            "temporal_semantics",
                            "INTERPRETATION_ANCHOR_REJECTED",
                            f"解释解析 {resolution.resolution_id} 声明的父规则 {code} 不在本次草稿中。",
                            refs,
                        )
                    )
                    continue
                if code not in rules_with_unanchored_lookback:
                    issues.append(
                        _issue(
                            "temporal_semantics",
                            "INTERPRETATION_ANCHOR_REJECTED",
                            f"解释解析 {resolution.resolution_id} 声明 {code} 存在未命名回溯锚点，"
                            "但该条款的解构结果没有未命名回溯缺口；解释与方案不一致。",
                            refs,
                            action="解释材料只能澄清确实模糊的条款；请核对方案原文或撤回该解析。",
                        )
                    )
                missing_stages = [
                    stage
                    for stage in resolution.target_review_stages
                    if stage not in stage_values
                ]
                if missing_stages:
                    rendered = "、".join(
                        sorted(stage.value for stage in missing_stages)
                    )
                    issues.append(
                        _issue(
                            "temporal_semantics",
                            "INTERPRETATION_ANCHOR_REJECTED",
                            f"解释解析 {resolution.resolution_id} 声明的目标审核节点 {rendered} 在草稿流程中不存在。",
                            refs,
                            action="请只声明本次方案流程中已有的审核节点，不得为解析虚构审核节点。",
                        )
                    )
        components_by_id = {
            component.rule_component_id: component
            for rule in draft.proposed_rules
            for component in rule.components
        }
        for (rule_code, component_id), matched in sorted(resolved_bindings.items()):
            component = components_by_id.get(component_id)
            if component is None:
                continue
            required_stages = {
                stage
                for resolution in matched
                for stage in resolution.target_review_stages
            }
            actual_stages = {
                requirement.due_stage
                for requirement in component.evidence_requirements
            }
            missing = required_stages - actual_stages
            if missing:
                rendered = "、".join(sorted(stage.value for stage in missing))
                issues.append(
                    _issue(
                        "temporal_semantics",
                        "INTERPRETATION_ANCHOR_REQUIREMENT_MISSING",
                        f"{component.display_code} 的资料要求未覆盖解释解析声明的全部目标审核节点（缺 {rendered}）。",
                        [component.rule_component_id, rule_code],
                        action="请在该组件下为解释声明的每个目标审核节点分别建立 due_stage 资料要求；"
                        "它们是同一核对义务的逐节点实例，不得复制原子条件。",
                    )
                )

    @staticmethod
    def _workflow_coverage(source_input, draft, issues):
        expected = [
            item.item_id
            for item in sorted(
                source_input.required_procedure_catalog.items,
                key=lambda item: item.position,
            )
        ]
        actual = [item.catalog_item_id for item in draft.procedure_catalog_mappings]
        if actual != expected:
            issues.append(
                _issue(
                    "workflow_coverage",
                    "PROCEDURE_CATALOG_NOT_EXACTLY_COVERED",
                    "基线及以前必做项目录没有按访视实例逐项完整覆盖。",
                    sorted(set(expected) ^ set(actual)) or expected,
                    action="请恢复缺失访视实例；同一检查在筛选和基线执行时必须保留两项。",
                )
            )
        stages = {
            item.workflow_stage_id: item for item in draft.proposed_workflow_stages
        }
        if len(stages) != len(draft.proposed_workflow_stages):
            issues.append(
                _issue(
                    "workflow_coverage",
                    "DUPLICATE_WORKFLOW_STAGE",
                    "审核节点存在重复标识，无法唯一归集应核对项目。",
                    sorted(stages) or [draft.draft_id],
                )
            )
        # 节点身份 = (审核阶段, 访视实例)：同一 ReviewStage 下多个访视实例
        # 各自有独立节点，不能由最后一个节点覆盖。访视实例缺失的节点不能
        # 承载冻结必做项目（目录项必带 visit_instance）。
        visit_keys: dict[tuple[str, str | None], str] = {}
        for stage in stages.values():
            key = (stage.stage.value, stage.visit_instance)
            prior = visit_keys.get(key)
            if prior is not None:
                issues.append(
                    _issue(
                        "workflow_coverage",
                        "DUPLICATE_VISIT_NODE_IDENTITY",
                        f"审核节点 {prior} 与 {stage.workflow_stage_id} 具有相同"
                        "（审核阶段, 访视实例）身份，无法区分两个访视。",
                        [prior, stage.workflow_stage_id],
                        action="请为同一阶段的每个访视实例保留独立 visit_instance；"
                        "同一检查在筛选与基线分别执行时必须保留两个节点。",
                    )
                )
            visit_keys[key] = stage.workflow_stage_id
        catalog_items = {
            item.item_id: item for item in source_input.required_procedure_catalog.items
        }
        for mapping in draft.procedure_catalog_mappings:
            stage = stages.get(mapping.proposed_workflow_stage_id)
            if stage is None:
                issues.append(
                    _issue(
                        "workflow_coverage",
                        "WORKFLOW_STAGE_NOT_FOUND",
                        "必做项目映射到了不存在的审核节点。",
                        [mapping.catalog_item_id, mapping.proposed_workflow_stage_id],
                    )
                )
                continue
            catalog_item = catalog_items.get(mapping.catalog_item_id)
            if catalog_item is None:
                continue
            if catalog_item.review_stage != stage.stage:
                issues.append(
                    _issue(
                        "workflow_coverage",
                        "PROCEDURE_REVIEW_STAGE_MISMATCH",
                        f"必做项目 {mapping.catalog_item_id} 的冻结审核阶段与草稿节点不一致。",
                        [mapping.catalog_item_id, mapping.proposed_workflow_stage_id],
                        action="请将必做项目映射到与冻结目录 review_stage 完全一致的审核节点，筛选项目不能映射到基线节点。",
                    )
                )
            if stage.visit_instance != catalog_item.visit_instance:
                issues.append(
                    _issue(
                        "workflow_coverage",
                        "PROCEDURE_VISIT_INSTANCE_MISMATCH",
                        f"必做项目 {mapping.catalog_item_id} 的冻结访视实例"
                        f"（{catalog_item.visit_instance}）与草稿节点"
                        f"（{stage.visit_instance or '未声明'}）不一致。",
                        [mapping.catalog_item_id, mapping.proposed_workflow_stage_id],
                        action="请把必做项目映射到访视实例与冻结目录完全一致的审核节点；"
                        "同一操作在不同访视执行时必须保留各自实例，不能合并或错配。",
                    )
                )

        # 到期闭包：每个资料要求必须恰好列在一个节点，且节点阶段与要求 due_stage
        # 一致；流程资料要求必须列在其目录映射指向的同一节点。
        requirements = {
            requirement.requirement_id: requirement
            for rule in draft.proposed_rules
            for component in rule.components
            for requirement in component.evidence_requirements
        }
        procedure_requirement_objects = {
            item.proposed_requirement.requirement_id: item.proposed_requirement
            for item in draft.evidence_requirement_drafts
            if item.procedure_catalog_item_id is not None
        }
        requirements.update(procedure_requirement_objects)
        for mapping in draft.procedure_catalog_mappings:
            for requirement_id in mapping.proposed_requirement_ids:
                if requirement_id not in requirements:
                    requirements[requirement_id] = None  # 占位：存在性由 evidence_coverage 把关
        node_by_requirement: dict[str, str] = {}
        for stage in draft.proposed_workflow_stages:
            for requirement_id in stage.due_requirement_ids:
                requirement = requirements.get(requirement_id)
                if (
                    requirement is not None
                    and stage.stage != requirement.due_stage
                ):
                    issues.append(
                        _issue(
                            "workflow_coverage",
                            "REQUIREMENT_DUE_STAGE_MISMATCH",
                            f"资料要求 {requirement_id} 的 due_stage 是 "
                            f"{requirement.due_stage.value}，却列在 "
                            f"{stage.workflow_stage_id}（{stage.stage.value}）节点。",
                            [requirement_id, stage.workflow_stage_id],
                            action="请把资料要求放入与其 due_stage 一致的审核节点；"
                            "筛选期要求不能放入基线节点。",
                        )
                    )
                prior_node = node_by_requirement.get(requirement_id)
                if prior_node is not None:
                    issues.append(
                        _issue(
                            "workflow_coverage",
                            "DUPLICATE_WORKFLOW_REQUIREMENT",
                            "同一资料核对要求在审核节点中重复出现，无法确定唯一到期节点。",
                            [prior_node, stage.workflow_stage_id, requirement_id],
                            action="请保证每个资料核对要求只在其 due_stage 对应的一个审核节点中出现一次。",
                        )
                    )
                node_by_requirement[requirement_id] = stage.workflow_stage_id
        for requirement_id in sorted(requirements):
            if requirement_id not in node_by_requirement:
                issues.append(
                    _issue(
                        "workflow_coverage",
                        "REQUIREMENT_WITHOUT_DUE_NODE",
                        f"资料要求 {requirement_id} 没有出现在任何审核节点。",
                        [requirement_id],
                        action="请把每个资料核对要求放入其 due_stage 对应的唯一审核节点。",
                    )
                )
                continue
        # 流程资料要求必须与目录映射同节点（映射指向的节点即到期节点）。
        for mapping in draft.procedure_catalog_mappings:
            for requirement_id in mapping.proposed_requirement_ids:
                listed_node = node_by_requirement.get(requirement_id)
                if (
                    listed_node is not None
                    and listed_node != mapping.proposed_workflow_stage_id
                ):
                    issues.append(
                        _issue(
                            "workflow_coverage",
                            "PROCEDURE_REQUIREMENT_WRONG_NODE",
                            f"流程资料要求 {requirement_id} 列在 {listed_node}，"
                            f"但其目录映射指向 {mapping.proposed_workflow_stage_id}。",
                            [mapping.catalog_item_id, requirement_id, listed_node],
                            action="流程资料要求必须列在其必做项目目录映射指向的同一审核节点。",
                        )
                    )
        # 空节点（未承载任何资料核对要求）是孤立节点。
        orphan_stages = sorted(
            stage_id
            for stage_id in stages
            if stage_id not in node_by_requirement.values()
        )
        if orphan_stages:
            issues.append(
                _issue(
                    "workflow_coverage",
                    "ORPHAN_WORKFLOW_STAGE",
                    "审核节点没有承载任何资料核对要求，无法归集应核对项目。",
                    orphan_stages,
                    action="请删除孤立节点或把对应访视的资料要求放入其中。",
                )
            )

    @staticmethod
    def _evidence_coverage(draft, issues):
        missing = [
            component.rule_component_id
            for rule in draft.proposed_rules
            for component in rule.components
            if not component.evidence_requirements
        ]
        if missing:
            issues.append(
                _issue(
                    "evidence_coverage",
                    "RULE_COMPONENT_WITHOUT_EVIDENCE_REQUIREMENT",
                    "部分规则组件没有说明需要核对的资料或判断。",
                    missing,
                )
            )
        prejudged_descriptions = sorted(
            requirement.requirement_id
            for rule in draft.proposed_rules
            for component in rule.components
            for requirement in component.evidence_requirements
            if re.search(
                r"(?:确认|证明|判定|确保).{0,80}"
                r"(?:不存在|无异常|无不可接受|符合|满足|不符合|触发|未触发|排除)",
                requirement.description,
            )
        )
        if prejudged_descriptions:
            issues.append(
                _issue(
                    "evidence_coverage",
                    "EVIDENCE_DESCRIPTION_PREJUDGES_RESULT",
                    "部分资料要求在核对证据前已经预设通过或不通过结论。",
                    prejudged_descriptions,
                    action="请只写需要核对的资料、检查或研究者评估，不得预先写成不存在、无异常、符合或不触发。",
                )
            )
        component_requirement_ids = {
            requirement.requirement_id
            for rule in draft.proposed_rules
            for component in rule.components
            for requirement in component.evidence_requirements
        }
        drafted_requirements = {
            item.proposed_requirement.requirement_id
            for item in draft.evidence_requirement_drafts
        }
        if len(drafted_requirements) != len(draft.evidence_requirement_drafts):
            issues.append(
                _issue(
                    "evidence_coverage",
                    "DUPLICATE_EVIDENCE_REQUIREMENT_DRAFT",
                    "必做项目资料要求的来源映射存在重复。",
                    sorted(drafted_requirements) or [draft.draft_id],
                )
            )
        component_draft_ids = {
            item.proposed_component.rule_component_id: item.draft_component_id
            for item in draft.component_drafts
        }
        component_requirement_drafts = {
            item.proposed_requirement.requirement_id: item
            for item in draft.evidence_requirement_drafts
            if item.draft_component_id is not None
        }
        missing_component_drafts = sorted(
            component_requirement_ids - set(component_requirement_drafts)
        )
        extra_component_drafts = sorted(
            set(component_requirement_drafts) - component_requirement_ids
        )
        if missing_component_drafts or extra_component_drafts:
            issues.append(
                _issue(
                    "evidence_coverage",
                    "COMPONENT_REQUIREMENT_DRAFT_COVERAGE_MISMATCH",
                    "子规则资料要求与其来源映射没有逐项一一对应。",
                    missing_component_drafts + extra_component_drafts,
                )
            )
        requirements_by_id = {
            requirement.requirement_id: requirement
            for rule in draft.proposed_rules
            for component in rule.components
            for requirement in component.evidence_requirements
        }
        mismatched_drafts = sorted(
            requirement_id
            for requirement_id, item in component_requirement_drafts.items()
            if requirement_id in requirements_by_id
            and (
                item.proposed_requirement != requirements_by_id[requirement_id]
                or item.draft_component_id
                != component_draft_ids.get(
                    requirements_by_id[requirement_id].rule_component_id or ""
                )
            )
        )
        if mismatched_drafts:
            issues.append(
                _issue(
                    "evidence_coverage",
                    "COMPONENT_REQUIREMENT_DRAFT_BINDING_MISMATCH",
                    "部分子规则资料要求的内容或子规则来源绑定不一致。",
                    mismatched_drafts,
                )
            )
        procedure_requirement_drafts = {
            item.proposed_requirement.requirement_id: item
            for item in draft.evidence_requirement_drafts
            if item.procedure_catalog_item_id is not None
        }
        mapped_procedure_requirement_ids = [
            requirement_id
            for mapping in draft.procedure_catalog_mappings
            for requirement_id in mapping.proposed_requirement_ids
        ]
        duplicate_procedure_requirement_ids = sorted(
            requirement_id
            for requirement_id, count in Counter(
                mapped_procedure_requirement_ids
            ).items()
            if count > 1
        )
        if duplicate_procedure_requirement_ids:
            issues.append(
                _issue(
                    "evidence_coverage",
                    "DUPLICATE_PROCEDURE_REQUIREMENT_MAPPING",
                    "同一流程资料要求被多个必做项目重复引用。",
                    duplicate_procedure_requirement_ids,
                    action="请保证每个流程资料要求只绑定一个冻结必做项目。",
                )
            )
        expected_draft_requirement_ids = component_requirement_ids | set(
            mapped_procedure_requirement_ids
        )
        missing_draft_requirements = sorted(
            expected_draft_requirement_ids - drafted_requirements
        )
        orphan_draft_requirements = sorted(
            drafted_requirements - expected_draft_requirement_ids
        )
        if missing_draft_requirements or orphan_draft_requirements:
            issues.append(
                _issue(
                    "evidence_coverage",
                    "EVIDENCE_REQUIREMENT_DRAFT_COVERAGE_MISMATCH",
                    "资料要求来源映射与规则组件及流程必做项目没有逐项完整对应。",
                    missing_draft_requirements + orphan_draft_requirements,
                    action="请删除孤立来源映射并补齐缺失映射；每个资料要求必须且只能有一条来源映射。",
                )
            )
        for mapping in draft.procedure_catalog_mappings:
            unknown = sorted(
                set(mapping.proposed_requirement_ids)
                - set(procedure_requirement_drafts)
            )
            if unknown:
                issues.append(
                    _issue(
                        "evidence_coverage",
                        "PROCEDURE_REQUIREMENT_NOT_FOUND",
                        "必做项目映射到了不存在的资料要求。",
                        [mapping.catalog_item_id, *unknown],
                    )
                )
            without_source_mapping = sorted(
                set(mapping.proposed_requirement_ids)
                - set(procedure_requirement_drafts)
            )
            if without_source_mapping:
                issues.append(
                    _issue(
                        "evidence_coverage",
                        "PROCEDURE_REQUIREMENT_SOURCE_MAPPING_MISSING",
                        "必做项目的资料要求没有逐项保留来源映射。",
                        [mapping.catalog_item_id, *without_source_mapping],
                        action="请在 evidence_requirement_drafts 中逐项补齐该必做项目资料要求及其正式来源。",
                    )
                )
            wrong_catalog_bindings = sorted(
                requirement_id
                for requirement_id in mapping.proposed_requirement_ids
                if requirement_id in procedure_requirement_drafts
                and procedure_requirement_drafts[
                    requirement_id
                ].procedure_catalog_item_id
                != mapping.catalog_item_id
            )
            if wrong_catalog_bindings:
                issues.append(
                    _issue(
                        "evidence_coverage",
                        "PROCEDURE_REQUIREMENT_BINDING_MISMATCH",
                        "必做项目资料要求绑定到了其他目录项。",
                        [mapping.catalog_item_id, *wrong_catalog_bindings],
                    )
                )

    @staticmethod
    def _source_coverage(source_input, draft, source_spans, issues):
        allowed = set(source_input.allowed_source_span_ids)
        formal_ids = formal_source_span_ids(source_spans.values())
        catalog_items = (
            *source_input.parent_rule_catalog.items,
            *source_input.required_procedure_catalog.items,
        )
        for item in catalog_items:
            formal = [span_id for span_id in item.source_span_ids if span_id in formal_ids]
            if not formal:
                issues.append(
                    _issue(
                        "source_coverage",
                        "CATALOG_ITEM_WITHOUT_FORMAL_SOURCE",
                        f"冻结目录项 {item.item_id} 只有降级提示或没有正式原文定位。",
                        [item.item_id, *item.source_span_ids],
                        action="请定位到对应具体条款或操作原文；章标题和插值页不能作为唯一依据。",
                    )
                )
        refs = []
        for item in draft.component_drafts:
            refs.extend(item.source_refs)
        for item in draft.evidence_requirement_drafts:
            refs.extend(item.source_refs)
        for item in (*draft.parent_catalog_mappings, *draft.procedure_catalog_mappings):
            refs.extend(item.source_span_ids)
        invalid = sorted(
            {ref for ref in refs if ref not in allowed or ref not in formal_ids}
        )
        if invalid:
            issues.append(
                _issue(
                    "source_coverage",
                    "DRAFT_SOURCE_NOT_FORMALLY_LOCATED",
                    "草稿中的规则、流程或资料要求含无效、跨期或仅为提示的来源定位。",
                    invalid,
                )
            )
        procedure_catalog_sources = {
            item.item_id: tuple(sorted(item.source_span_ids))
            for item in source_input.required_procedure_catalog.items
        }
        procedure_source_mismatches = []
        for mapping in draft.procedure_catalog_mappings:
            expected_refs = procedure_catalog_sources.get(mapping.catalog_item_id)
            if (
                expected_refs is None
                or tuple(sorted(mapping.source_span_ids)) != expected_refs
            ):
                procedure_source_mismatches.append(mapping.catalog_item_id)
        if procedure_source_mismatches:
            issues.append(
                _issue(
                    "source_coverage",
                    "PROCEDURE_MAPPING_SOURCE_MISMATCH",
                    "部分必做项目映射没有精确保留其冻结访视目录来源。",
                    sorted(set(procedure_source_mismatches)),
                    action="请让每个必做项目只绑定其自身冻结目录项的完整来源片段；"
                    "不得遗漏本访视来源，也不得夹带其他访视的方案片段。",
                )
            )
        materials = {
            material.source_span_id: material.text
            for material in source_input.source_materials
        }
        component_refs_by_parent: dict[str, set[str]] = {}
        for item in draft.component_drafts:
            component_refs_by_parent.setdefault(
                item.parent_official_code, set()
            ).update(item.source_refs)

        for item in source_input.parent_rule_catalog.items:
            expected_refs = list(item.source_span_ids)
            if expected_refs:
                first_text = materials.get(expected_refs[0], "")
                if _normalized(first_text).rstrip(":") == _normalized(
                    item.label
                ).rstrip(":"):
                    # The first span can be a structural lead-in such as
                    # "患有以下疾病史". It supplies context but does not itself
                    # need a duplicate child component. Every subsequent
                    # substantive span still represents a semantic obligation.
                    expected_refs = expected_refs[1:]
            covered_refs = component_refs_by_parent.get(item.official_code or "", set())
            missing_refs = [
                span_id
                for span_id in expected_refs
                if _normalized(materials.get(span_id, ""))
                not in {"", "注", "备注", "说明"}
                and span_id not in covered_refs
            ]
            if missing_refs:
                official_code = item.official_code or item.item_id
                issues.append(
                    _issue(
                        "source_coverage",
                        "PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING",
                        f"{official_code} 原文中的列举项、注释或限定条件没有进入任何子规则。",
                        [official_code, *sorted(set(missing_refs))],
                        action="请逐段核对该父规则冻结的正式原文，为每个实质性分支、时间窗、阈值、例外和注释建立对应子规则并保留来源定位；不能只结构化‘包括以下情况’等引导语。",
                        scope=[official_code],
                    )
                )

        rules_by_code = {rule.official_code: rule for rule in draft.proposed_rules}
        for item in source_input.parent_rule_catalog.items:
            official_code = item.official_code or item.item_id
            rule = rules_by_code.get(item.official_code or "")
            if rule is None:
                continue
            parent_texts = [
                materials[span_id]
                for span_id in item.source_span_ids
                if span_id in materials and _normalized(materials[span_id])
            ]
            if not parent_texts and item.label:
                parent_texts = [item.label]
            obligations = [
                segment
                for text in parent_texts
                for segment in _substantive_obligation_segments(text)
            ]
            predicates = [
                predicate
                for expression in _walk_expressions(rule)
                for predicate in iter_atomic_predicates(expression)
            ]
            uncovered = [
                segment
                for segment in dict.fromkeys(obligations)
                if not any(
                    _predicate_binds_obligation(predicate, segment)
                    for predicate in predicates
                )
            ]
            if uncovered:
                issues.append(
                    _issue(
                        "source_coverage",
                        "PARENT_RULE_OBLIGATION_NOT_COVERED",
                        f"{official_code} 原文中有实质性条件没有进入可判定的原子条件。",
                        [
                            official_code,
                            *[f"未承接：{segment[:80]}" for segment in uncovered],
                        ],
                        action=(
                            "请逐项保留父条款中的病史时长、疾病状态、时间窗、数值阈值、"
                            "研究者判断及其他并列要求；每项必须由原子条件的指标名或分类词与逐字原文共同承接，"
                            "仅引用整句原文不代表已完成解构。"
                        ),
                        scope=[official_code],
                    )
                )
        invalid_excerpts = []
        missing_excerpts = []
        for item in draft.component_drafts:
            if not item.source_excerpts:
                missing_excerpts.append(
                    item.proposed_component.rule_component_id
                )
                continue
            mapped_text = "\n".join(
                materials[ref] for ref in item.source_refs if ref in materials
            )
            if any(excerpt not in mapped_text for excerpt in item.source_excerpts):
                invalid_excerpts.append(item.proposed_component.rule_component_id)
        if invalid_excerpts:
            issues.append(
                _issue(
                    "source_coverage",
                    "COMPONENT_EXCERPT_NOT_IN_SOURCE",
                    "部分子规则的原文摘录不是所引正式来源中的连续原文。",
                    invalid_excerpts,
                    action="请从所引方案片段逐字复制当前子规则对应的最小完整原文，不得改写；若当前子项继承父级引导段的时间锚点、主语或限定语，请同时引用父级与子项来源，并在 source_excerpts 中分成多个逐字片段，禁止拼成原文不存在的新句子。",
                )
            )
        if missing_excerpts:
            issues.append(
                _issue(
                    "source_coverage",
                    "COMPONENT_EXCERPT_MISSING",
                    "部分子规则没有可逐字核对的方案原文摘录。",
                    missing_excerpts,
                    action="请为每个子规则保存至少一段来自所引正式来源的逐字原文；不能只保留页码或来源 ID。",
                )
            )
        invalid_clauses = []
        for rule in draft.proposed_rules:
            for component in rule.components:
                component_draft = next(
                    (
                        item
                        for item in draft.component_drafts
                        if item.proposed_component.rule_component_id
                        == component.rule_component_id
                    ),
                    None,
                )
                if component_draft is None or not component_draft.source_excerpts:
                    continue
                component_text = "\n".join(component_draft.source_excerpts)
                expressions = [component.expression]
                if component.exception_expression is not None:
                    expressions.append(component.exception_expression)
                for expression in expressions:
                    for predicate in iter_atomic_predicates(expression):
                        clauses = predicate.exact_source_clauses
                        if not clauses or any(
                            clause not in component_text for clause in clauses
                        ):
                            invalid_clauses.append(predicate.predicate_id)
        if invalid_clauses:
            issues.append(
                _issue(
                    "source_coverage",
                    "PREDICATE_CLAUSE_NOT_IN_SOURCE",
                    "部分原子条件没有绑定所属子规则中可逐字核对的原文子句。",
                    sorted(set(invalid_clauses)),
                    action="请逐字绑定直接支撑当前原子条件的原文；连续子句使用 source_clause。不连续的共同前缀、当前分支和共同尾句必须用 source_clauses 分段保存，例如‘随机前12周/4周’的4周分支应分别保存‘随机前’与‘4周’，不得拼成原文不存在的‘随机前4周’。",
                )
            )
        fragmented_categories = []
        for rule in draft.proposed_rules:
            for expression in _walk_expressions(rule):
                for predicate in iter_atomic_predicates(expression):
                    if not _categorical_values_are_source_terms(predicate):
                        fragmented_categories.append(predicate.predicate_id)
        if fragmented_categories:
            issues.append(
                _issue(
                    "source_coverage",
                    "CATEGORICAL_VALUE_NOT_WHOLE_SOURCE_TERM",
                    "部分分类值不是方案原文中可独立核对的完整分类词。",
                    sorted(set(fragmented_categories)),
                    action=(
                        "请把分类值按原文完整词项保留，不得拆成单个字或截断类型后缀；"
                        "单字分类只在原文明示枚举时允许，例如‘男或女’或‘A/B’。"
                    ),
                )
            )
        parent_sources = {
            item.official_code: set(item.source_span_ids)
            for item in source_input.parent_rule_catalog.items
        }
        outside_parent = []
        for item in draft.component_drafts:
            allowed_parent_refs = parent_sources.get(item.parent_official_code, set())
            if not set(item.source_refs) <= allowed_parent_refs:
                outside_parent.append(item.proposed_component.rule_component_id)
        if outside_parent:
            issues.append(
                _issue(
                    "source_coverage",
                    "COMPONENT_SOURCE_OUTSIDE_PARENT",
                    "部分子规则引用了其所属官方父规则之外的方案片段。",
                    outside_parent,
                    action="请只保留当前官方父规则下直接支撑该子规则的来源，不得借用其他父规则。",
                )
            )
        # 资料要求来源绑定：组件要求只能引用其所属组件来源；流程要求只能
        # 引用其必做项目映射来源。来源张冠李戴会破坏逐条可追溯性。
        component_sources = {
            item.draft_component_id: set(item.source_refs)
            for item in draft.component_drafts
        }
        misplaced_requirement_sources = []
        for item in draft.evidence_requirement_drafts:
            if item.draft_component_id is not None:
                allowed_refs = component_sources.get(item.draft_component_id, set())
                if not set(item.source_refs) <= allowed_refs:
                    misplaced_requirement_sources.append(
                        item.proposed_requirement.requirement_id
                    )
            elif item.procedure_catalog_item_id is not None:
                mapping = next(
                    (
                        candidate
                        for candidate in draft.procedure_catalog_mappings
                        if candidate.catalog_item_id == item.procedure_catalog_item_id
                    ),
                    None,
                )
                if mapping is None or not set(item.source_refs) <= set(
                    mapping.source_span_ids
                ):
                    misplaced_requirement_sources.append(
                        item.proposed_requirement.requirement_id
                    )
        if misplaced_requirement_sources:
            issues.append(
                _issue(
                    "source_coverage",
                    "REQUIREMENT_SOURCE_OUTSIDE_ORIGIN",
                    "部分资料要求引用了其所属组件或必做项目之外的方案片段。",
                    sorted(set(misplaced_requirement_sources)),
                    action="请让每条资料要求只引用其所属子规则组件或必做项目目录映射的"
                    "来源片段，不得借用其他组件或访视的来源。",
                )
            )
        # 子规则资料要求与流程资料要求：来源必须属于其对应组件来源/允许范围。
        component_refs = {
            item.proposed_component.rule_component_id: set(item.source_refs)
            for item in draft.component_drafts
        }
        requirement_to_component = {
            requirement.requirement_id: component.rule_component_id
            for rule in draft.proposed_rules
            for component in rule.components
            for requirement in component.evidence_requirements
        }
        requirement_refs_by_component: dict[str, list[str]] = {}
        requirement_refs_by_procedure: dict[str, list[str]] = {}
        for item in draft.evidence_requirement_drafts:
            if item.draft_component_id is not None:
                component_id = next(
                    (
                        draft_item.proposed_component.rule_component_id
                        for draft_item in draft.component_drafts
                        if draft_item.draft_component_id == item.draft_component_id
                    ),
                    None,
                )
                if component_id is not None:
                    requirement_refs_by_component.setdefault(
                        component_id, []
                    ).extend(item.source_refs)
            else:
                requirement_refs_by_procedure.setdefault(
                    item.procedure_catalog_item_id or "", []
                ).extend(item.source_refs)
        requirement_outside_component = sorted(
            component_id
            for component_id, refs in requirement_refs_by_component.items()
            if refs and component_id in component_refs
            and not set(refs) <= component_refs[component_id]
        )
        if requirement_outside_component:
            issues.append(
                _issue(
                    "source_coverage",
                    "REQUIREMENT_SOURCE_OUTSIDE_COMPONENT",
                    "部分子规则资料要求的来源超出其所属子规则来源范围。",
                    requirement_outside_component,
                    action="资料要求只能引用直接支撑其所属子规则的方案片段，"
                    "不得借用其他组件或父规则之外的来源。",
                )
            )
        procedure_catalog_refs = {
            item.item_id: set(item.source_span_ids)
            for item in source_input.required_procedure_catalog.items
        }
        procedure_requirement_outside = sorted(
            catalog_item_id
            for catalog_item_id, refs in requirement_refs_by_procedure.items()
            if refs
            and catalog_item_id in procedure_catalog_refs
            and not set(refs) <= procedure_catalog_refs[catalog_item_id]
        )
        if procedure_requirement_outside:
            issues.append(
                _issue(
                    "source_coverage",
                    "PROCEDURE_REQUIREMENT_SOURCE_OUTSIDE_CATALOG",
                    "部分流程资料要求的来源超出其必做项目录项的来源范围。",
                    procedure_requirement_outside,
                    action="流程资料要求只能引用其所属必做项目录项的访视/操作原文，"
                    "不得借用其他目录项或组件来源。",
                )
            )
        # 资料要求自身若被换绑到其他组件（draft_component_id 与规则树组件不一致）
        # 由 evidence_coverage 的 COMPONENT_REQUIREMENT_DRAFT_BINDING_MISMATCH 把关；
        # 此处补充：requirement 来源还必须在 allowed 范围内（上方 DRAFT_SOURCE_NOT_FORMALLY_LOCATED 已覆盖）。

    @staticmethod
    def _interpretation_authority(conflicts, issues, anchor_authority_issues=()):
        for issue in anchor_authority_issues:
            issues.append(issue)
        blocking = [item.conflict_id for item in conflicts if item.blocks_publication]
        if blocking:
            issues.append(
                _issue(
                    "interpretation_authority",
                    "INTERPRETATION_CONFLICT_OPEN",
                    "解释材料与方案或当前修订案存在未解决冲突。",
                    blocking,
                    action="解释材料只能澄清模糊处；请取得当前修订案或保留冲突并停止发布。",
                )
            )

    @staticmethod
    def _diff_integrity(draft, previous, declared, issues):
        if draft.draft_revision == 1:
            # “第 1 稿”只表示当前草稿链的起点。首次解构没有正式
            # 基线；重新解构的第 1 稿则必须与当前正式版比较。后者不是
            # 同一草稿链的后继，因此 content.previous_draft_id 仍应为空。
            if previous is None and declared is None:
                return
            if previous is None or declared is None:
                issues.append(
                    _issue(
                        "diff_integrity",
                        "INITIAL_REVISION_DIFF_BASE_INCOMPLETE",
                        "重新解构首稿的正式基线与结构化差异不完整。",
                        [draft.draft_id],
                    )
                )
                return
        elif (
            previous is None
            or declared is None
            or draft.previous_draft_id != previous.draft_id
        ):
            issues.append(
                _issue(
                    "diff_integrity",
                    "DRAFT_DIFF_BASE_MISSING",
                    "修订稿缺少可重建的前序草稿或结构化差异。",
                    [draft.draft_id],
                )
            )
            return
        # 发布重建与草稿服务共用唯一差异算法；声明必须覆盖组件、资料要求、
        # 流程映射和来源范围，不能只校验父规则/节点后让被篡改的子差异混入。
        from app.services.protocol_draft_service import compute_draft_diff

        actual = compute_draft_diff(previous, draft)
        expected = ProtocolDraftDiffDeclaration(
            **actual.model_dump(mode="python")
        )
        if declared != expected:
            issues.append(
                _issue(
                    "diff_integrity",
                    "DECLARED_DIFF_NOT_REPRODUCIBLE",
                    "显示的新增、删除或修改与两稿结构化内容不一致。",
                    [previous.draft_id, draft.draft_id],
                    action="请由结构差异重新生成变更清单，不要解析模型摘要文字。",
                )
            )
