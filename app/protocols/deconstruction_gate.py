"""Deterministic publication checks for protocol deconstruction drafts.

The semantic model may propose a draft, but it cannot decide that the draft is
complete. These checks compare the proposal with the confirmed identity, the
two pre-frozen catalogs and the immutable protocol source locations.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
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
)
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.domain.contracts.protocol_metadata import InterpretationConflict
from app.domain.contracts.rules import Rule, TimeUnit, iter_atomic_predicates
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
    """Exclude a sibling item's parenthetical time note from this predicate."""

    text = _predicate_text(predicate)
    binding_text = _normalized(
        "\n".join(
            part
            for part in (predicate.source_term, predicate.attribute)
            if part
        )
    )
    pattern = re.compile(
        r"(?:^|[、，；。\n])(?P<label>[^、，；。\n（）()]{1,40})"
        r"(?P<note>[（(][^）)]*\d+(?:\.\d+)?\s*个?(?:天|日|周|月|年)[^）)]*[）)])"
    )

    def retain_or_remove(match: re.Match[str]) -> str:
        label = _normalized(match.group("label"))
        if label and label in binding_text:
            return match.group(0)
        prefix = match.group(0)[0] if match.group(0)[0] in "、，；。" else ""
        return prefix + match.group("label")

    return pattern.sub(retain_or_remove, text)


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


def _has_unambiguous_disjunction(text: str) -> bool:
    normalized = _normalized(text)
    if any(
        token in normalized
        for token in ("任一", "任何一项", "至少一项", "和/或", "及/或")
    ):
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
    binding_terms = {
        binding,
        re.sub(r"(?:发生次数|发作次数|复发次数|既往史|现病史|病史|天数)$", "", binding),
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


def _diff_sets(previous, current, key):
    old = {key(item): canonical_hash(item) for item in previous}
    new = {key(item): canonical_hash(item) for item in current}
    return (
        sorted(new.keys() - old.keys()),
        sorted(old.keys() - new.keys()),
        sorted(item for item in old.keys() & new.keys() if old[item] != new[item]),
    )


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
        self._temporal_semantics(source_input, draft, issues["temporal_semantics"])
        self._workflow_coverage(source_input, draft, issues["workflow_coverage"])
        self._evidence_coverage(draft, issues["evidence_coverage"])
        self._source_coverage(source_input, draft, source_spans, issues["source_coverage"])
        self._interpretation_authority(
            interpretation_conflicts, issues["interpretation_authority"]
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
            if set(mapping.source_span_ids) != set(item.source_span_ids):
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
                has_or = _has_unambiguous_disjunction(text)
                expression = component.expression
                if (
                    has_and
                    and not has_or
                    and expression.kind == "logical"
                    and expression.operator == LogicalOperator.ANY
                    and not _is_population_scoped_any(expression)
                    and not _any_branches_preserve_internal_conjunction(expression)
                ):
                    issues.append(
                        _issue(
                            "boolean_logic",
                            "CONJUNCTION_CHANGED_TO_DISJUNCTION",
                            f"{component.display_code} 原文仅表达并列同时满足，草稿却使用了任一满足。",
                            [component.rule_component_id],
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
                if "研究者" not in text or not has_and:
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
                        if has_numeric_value and has_precise_excerpt:
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
    def _temporal_semantics(source_input, draft, issues):
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
            AnchorType.LAST_DOSE_DATE: (
                "末次给药后",
                "最后一次给药后",
            ),
            AnchorType.STUDY_COMPLETION_DATE: (
                "研究完成后",
                "研究结束后",
            ),
        }
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
                            action="请把频次周期和阈值绑定到其直接限定的事件或示例分支：次数用数值谓词或 occurrence_window.minimum_count，周期内天数用天数阈值；两者均用 occurrence_window.duration 保留观察周期，不得套到无关兄弟分支。",
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
                            action="请保留一个原子条件，并为原文明确要求的每个审核阶段分别建立 due_stage 资料要求；不要复制原子条件或添加日期约束。",
                        )
                    )
                if not _has_unambiguous_disjunction(component_text):
                    source_quantities = _source_time_quantities(component_text)
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
                    is_unanchored_lookback = (
                        has_explicit_window
                        and not expected
                        and not component_expected
                        and "内" in predicate_text
                        and not is_frequency_definition
                        and not is_future_plan_window
                    )
                    occurrence_window = predicate.occurrence_window
                    prospective_window = predicate.prospective_window
                    prospective_period = predicate.prospective_period
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
                                    action="请拆分未来计划分支，并用 prospective_window 保存研究完成日或末次给药日及原文时长。",
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
                    if not expected:
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
        materials = {
            material.source_span_id: material.text
            for material in source_input.source_materials
        }
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
    def _interpretation_authority(conflicts, issues):
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
            if previous is not None or declared is not None:
                issues.append(
                    _issue(
                        "diff_integrity",
                        "FIRST_DRAFT_HAS_DIFF_BASE",
                        "首稿不应携带前序差异基线。",
                        [draft.draft_id],
                    )
                )
            return
        if previous is None or declared is None or draft.previous_draft_id != previous.draft_id:
            issues.append(
                _issue(
                    "diff_integrity",
                    "DRAFT_DIFF_BASE_MISSING",
                    "修订稿缺少可重建的前序草稿或结构化差异。",
                    [draft.draft_id],
                )
            )
            return
        rule_diff = _diff_sets(previous.proposed_rules, draft.proposed_rules, lambda item: item.official_code)
        workflow_diff = _diff_sets(
            previous.proposed_workflow_stages,
            draft.proposed_workflow_stages,
            lambda item: item.workflow_stage_id,
        )
        expected = ProtocolDraftDiffDeclaration(
            added_rule_codes=rule_diff[0],
            removed_rule_codes=rule_diff[1],
            modified_rule_codes=rule_diff[2],
            added_workflow_stage_ids=workflow_diff[0],
            removed_workflow_stage_ids=workflow_diff[1],
            modified_workflow_stage_ids=workflow_diff[2],
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
