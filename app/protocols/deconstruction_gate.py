"""Deterministic publication checks for protocol deconstruction drafts.

The semantic model may propose a draft, but it cannot decide that the draft is
complete. These checks compare the proposal with the confirmed identity, the
two pre-frozen catalogs and the immutable protocol source locations.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
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
    RuleKind,
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
from app.protocols.definition_scope_check import nested_example_definitions
from app.protocols.official_source_scope import (
    FrozenParentScopeError,
    frozen_parent_scope_fragments,
)
from app.protocols.official_scope_review import OfficialScopeReviewError, OfficialScopeUnresolvedError, reviewed_scope_stages
from app.protocols.section_index import formal_source_span_ids
from app.protocols.source_time_fragments import (
    STUDY_PERIOD_SOURCE_PATTERN,
    TREATMENT_PERIOD_SOURCE_PATTERN,
    frozen_review_stage_aliases,
)


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
DECONSTRUCTION_GATE_VERSION = "protocol-deconstruction-gate/2026-10-04.51"


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


def _source_review_stages(fragments: Iterable[str], *, stage_aliases=None) -> set[ReviewStage]:
    """Detect existing node cues within each source fragment, not across fragments."""
    stages: set[ReviewStage] = set()
    for fragment in fragments:
        text = re.sub(r"\s+", "", fragment)
        if re.search(r"筛选(?:期|访视)?时", text) or re.search(
            r"筛选(?:期|访视)?(?:或|和|及|与|、)基线(?:期|访视)?时", text
        ):
            stages.add(ReviewStage.SCREENING)
        if re.search(r"基线(?:期|访视)?时", text):
            stages.add(ReviewStage.BASELINE)
        if re.search(r"导入(?:期|访视)?时", text):
            stages.add(ReviewStage.RUN_IN)
    return {(stage_aliases or {}).get(stage, stage) for stage in stages}


def _shared_period_lead_in(predicate, component_source: str) -> str:
    """Bind ordered exact fragments inside one explicitly named period scope."""
    clauses = predicate.exact_source_clauses
    if len(clauses) < 2:
        return ""
    lead = clauses[0]
    source = re.sub(r"\s+", "", component_source)
    prefix = re.sub(r"\s+", "", lead)
    period_pattern = re.compile(r"(?:整个)?(?:研究|治疗)期间[（(][^）)]+[）)]")
    if not period_pattern.fullmatch(prefix):
        return ""
    periods = list(period_pattern.finditer(source))
    for position, match in enumerate(periods):
        if match.group() != prefix or (
            match.start() and source[match.start() - 1] not in "；;。，,:："
        ):
            continue
        limit = periods[position + 1].start() if position + 1 < len(periods) else len(source)
        offset = match.end()
        for clause in clauses[1:]:
            fragment = re.sub(r"\s+", "", clause)
            index = source.find(fragment, offset, limit)
            if not fragment or index < 0:
                break
            offset = index + len(fragment)
        else:
            return lead
    return ""


def _predicate_temporal_text(predicate, component_source: str = "") -> str:
    """Return the temporal meaning owned by one atomic predicate.

    Exact source clauses may repeat a complete protocol sentence so that the
    citation remains verbatim. That sentence can also contain a sibling OR
    branch or an exception. Temporal checks therefore use the predicate's
    semantic identity whenever it already names its own window or period, or
    when it has no temporal meaning at all. The wider exact clause is consulted
    only for an underspecified temporal identity such as ``计划接种活疫苗``.
    """

    text = _predicate_text(predicate)
    shared_period = _shared_period_lead_in(predicate, component_source)
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
        if shared_period and _normalized(match.group(0)) == _normalized(shared_period):
            return match.group(0)
        label = _normalized(match.group("label"))
        scoped_list = re.split(r"[：:]", match.group("note"), maxsplit=1)
        named_terms = (
            [_normalized(part) for part in re.split(r"[、，；。\n]", scoped_list[1])]
            if len(scoped_list) == 2 else []
        )
        named_in_list = (
            any(
                part[offset : offset + 8] in term
                for part in named_terms
                for term in binding_terms
                for offset in range(max(0, len(part) - 7))
            )
        )
        if named_in_list:
            prefix = match.group(0)[0] if match.group(0)[0] in "、，；。" else ""
            return prefix + match.group("note")
        same_clause_suffix = text[match.end() :].split("\n", 1)[0]
        following_segment = re.split(
            r"[、，；。]", same_clause_suffix.lstrip("、，；。"), maxsplit=1
        )[0]
        if any(label and label in term for term in binding_terms) or (
            len(scoped_list) == 1
            and any(term in _normalized(following_segment) for term in binding_terms)
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
    identity_owns_period = bool(
        STUDY_PERIOD_SOURCE_PATTERN.search(identity)
        or TREATMENT_PERIOD_SOURCE_PATTERN.search(identity)
    ) or any(
        marker in compact_identity
        for marker in ("筛选/导入期", "筛选导入期")
    )
    identity_quantities = _source_time_quantities(identity)
    parenthetical_quantities = set().union(*(
        _source_time_quantities(match.group(0))
        for match in re.finditer(r"[（(][^）)]*[）)]", identity)
    ))
    if (
        identity_quantities
        and identity_quantities <= parenthetical_quantities
        and _source_time_quantities(text) - identity_quantities
    ):
        identity_owns_window = False
        identity_owns_period = False
    if identity_owns_period and not identity_owns_window and shared_period:
        return shared_period + "\n" + identity
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


def _source_population_identity(value: str | None) -> str | None:
    population = (value or "").strip()
    if population.startswith(("（", "(")):
        qualifier = re.fullmatch(r"(?:（([^（）()]+)）|\(([^（）()]+)\))", population)
        if qualifier is None:
            return None
        population = next(group for group in qualifier.groups() if group is not None).strip()
    return population or None


def _is_population_scoped_any(expression) -> bool:
    if expression.kind != "logical" or expression.operator != LogicalOperator.ANY:
        return False
    branch_populations: list[frozenset[str]] = []
    for child in expression.children:
        populations = set()
        for predicate in iter_atomic_predicates(child):
            if predicate.applicable_population is None:
                continue
            population = _source_population_identity(predicate.applicable_population)
            if population is None:
                return False
            populations.add(population)
        if not populations:
            return False
        branch_populations.append(frozenset(populations))
    return len(set(branch_populations)) == len(branch_populations)


def _population_source_bound(expression) -> bool:
    """Keep an exact qualifier tied to its adjacent calendar window, not a sibling's."""
    predicate = expression.predicate
    population = _source_population_identity(predicate.applicable_population)
    if not population:
        return False

    def exact_prefix(clause: str) -> bool:
        stripped = clause.strip()
        if stripped.startswith(("（", "(")):
            parenthesis = re.fullmatch(r"(?:（([^（）()]+)）|\(([^（）()]+)\))", stripped)
            return parenthesis is not None and next(
                group for group in parenthesis.groups() if group is not None
            ).strip() == population
        return stripped.startswith(population)

    has_exact_prefix = any(
        exact_prefix(clause)
        for clause in predicate.exact_source_clauses
    )
    notes = [
        match
        for clause in predicate.exact_source_clauses
        for match in re.finditer(
            r"(?P<quantity>\d+\s*(?:个月|星期|天|日|周|月|年|days?|weeks?|months?|years?))"
            r"\s*(?:内\s*)?[（(](?P<qualifier>[^（）()]+)[）)]",
            clause, flags=re.IGNORECASE,
        )
        if population in match.group("qualifier")
    ]
    if not notes:
        return has_exact_prefix
    if any(match.group("qualifier").strip() != population for match in notes):
        return False
    quantities = [_source_time_quantities(match.group("quantity")) for match in notes]
    if any(len(quantity) != 1 for quantity in quantities):
        return False
    pairs = set().union(*quantities)
    # A source qualifier is still not an executable applicability decision.
    # Only a uniquely bound window may enter the existing explicit gap path.
    constraint = expression.time_constraint
    if len(pairs) != 1 or constraint is None:
        return False
    if constraint.upper_bound is not None:
        bound = (constraint.upper_bound.value, constraint.upper_bound.unit)
    elif constraint.upper_bound_days is not None:
        bound = (constraint.upper_bound_days, TimeUnit.DAY)
    else:
        return False
    source_value, source_unit = next(iter(pairs))
    return bound == (source_value, source_unit) or (
        source_unit == TimeUnit.WEEK and bound == (source_value * 7, TimeUnit.DAY)
    )


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


def _any_is_source_scoped_longer_washout(expression, source: str) -> bool:
    """A named subclass may have a longer washout than its parent treatment."""

    if (expression.kind != "logical" or expression.operator != LogicalOperator.ANY
            or len(expression.children) != 2):
        return False
    first, second = expression.children
    if first.kind != "predicate" or second.kind != "predicate":
        return False
    short, long = first.time_constraint, second.time_constraint
    if short is None or long is None or short.upper_bound is None or long.upper_bound is None:
        return False
    if (short.anchor_type != long.anchor_type or short.direction != TimeDirection.BEFORE
            or long.direction != TimeDirection.BEFORE
            or short.upper_bound.unit != long.upper_bound.unit
            or short.upper_bound.value >= long.upper_bound.value):
        return False
    parent = _normalized(first.predicate.attribute)
    subclass = _normalized(second.predicate.attribute)
    if len(parent) < 6 or not subclass.startswith(parent) or len(subclass) == len(parent):
        return False
    compact = re.sub(r"\s+", "", source)
    unit = {TimeUnit.DAY: "(?:天|日)", TimeUnit.WEEK: "(?:周|星期)",
            TimeUnit.MONTH: "(?:个月|月)", TimeUnit.YEAR: "年"}.get(short.upper_bound.unit)
    if unit is None:
        return False
    pattern = (rf"{short.upper_bound.value}{unit}内[^。；;]{{0,160}}?"
               rf"[（(](?:以下|其中)[^）)]{{0,60}}?(?:需|应|必须)洗脱"
               rf"{long.upper_bound.value}{unit}")
    return bool(re.search(pattern, compact)) and all(
        any(_normalized(clause) in _normalized(source)
            for clause in child.predicate.exact_source_clauses)
        for child in (first, second)
    )


def _shared_named_anchor_lead_in(predicate, component_text: str) -> str:
    """Use an exact shared lead-in for the anchor, never sibling durations."""

    pattern = re.compile(
        r"^(?:随机|筛选|基线|知情同意|首次给药|首剂|研究药物给药)"
        r"(?:前|后|时)[^。；;\n]{0,60}?(?:以下|下列|任一|任何一种)"
    )
    return "\n".join(
        clause for clause in predicate.exact_source_clauses
        if pattern.search(re.sub(r"\s+", "", clause))
        and _normalized(clause) in _normalized(component_text)
    )


def _requires_observation_policy(predicate) -> bool:
    """Require a policy only when the source declares how records are selected."""

    if any((predicate.occurrence_window, predicate.repeat_scheme,
            predicate.prospective_window, predicate.prospective_period,
            predicate.semantic_proposition)):
        return False
    source = _normalized(_predicate_text(predicate))
    return bool(
        re.search(r"(?:最近|最早|最新|末次|首次|任意|任一)一次(?:[^。；;]{0,25})?(?:结果|检查|测量|记录)", source)
        or re.search(r"(?:所有|全部|每次)(?:[^。；;]{0,25})?(?:结果|检查|测量|记录)", source)
        or re.search(r"(?:复查|重测)(?:[^。；;]{0,35})?(?:结果|数值)(?:[^。；;]{0,20})?(?:为准|采用|选取)", source)
        or re.search(r"(?:复查|重测)(?:[^。；;]{0,35})?(?:采用|选取|以)(?:[^。；;]{0,20})?(?:结果|数值)", source)
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
            rf"(?:由|经|需由|须由|应由|根据)?研究者(?:进行)?(?:书面)?{judgment}",
            compact,
        )
        or re.search(rf"{judgment}(?:应|需)?(?:由|经)研究者", compact)
        or re.search(rf"研究者的?{judgment}", compact)
    )


def _localized_open_list_exception_requires_exclusivity(
    trigger_clauses: Sequence[str],
) -> bool:
    """Identify a carve-out inside the same broad, non-exhaustive trigger.

    A component can cite a shared parent lead-in and a separate, specific list
    item.  Combining those two locators would incorrectly make a local
    exception on the specific item look like an exception to the whole list.
    The exclusivity safeguard therefore applies only when one exact trigger
    clause itself contains both the open-list wording and the carve-out.
    """

    return any(
        re.search(
            r"(?:包括但不限于|但不限于|例如|例如包括|如[：:])",
            compact,
        )
        and re.search(
            r"[（(][^）)]*(?:除外|除非|例外)[^）)]*[）)]",
            compact,
        )
        for clause in trigger_clauses
        if (compact := re.sub(r"\s+", "", clause))
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


def _parenthetical_stack_at(source: str, position: int) -> tuple[int, ...]:
    stack: list[int] = []
    for index, char in enumerate(source[:position]):
        if char in "（(":
            stack.append(index)
        elif char in "）)" and stack:
            stack.pop()
    return tuple(stack)


def _source_separator_in_shared_scope(
    source: str, left: tuple[int, int, str], right: tuple[int, int, str],
) -> str:
    """Only connectors at the scope shared by both branches authorize an OR."""

    left_scope = _parenthetical_stack_at(source, left[0])
    right_scope = _parenthetical_stack_at(source, right[0])
    shared: list[int] = []
    for left_open, right_open in zip(left_scope, right_scope):
        if left_open != right_open:
            break
        shared.append(left_open)
    stack = list(_parenthetical_stack_at(source, left[1]))
    visible: list[str] = []
    for index in range(left[1], right[0]):
        char = source[index]
        if char in "（(":
            stack.append(index)
        elif char in "）)" and stack:
            stack.pop()
        elif stack == shared:
            visible.append(char)
    if (left[1] > 0
            and source[left[1] - 1] in "、，；;,"
            and _parenthetical_stack_at(source, left[1] - 1) == tuple(shared)):
        visible.insert(0, source[left[1] - 1])
    return "".join(visible)


def _branches_have_source_disjunction(expression, source: str) -> bool:
    """Verify that sibling branches are individually named around a real OR."""

    if expression.kind != "logical" or expression.operator == LogicalOperator.NOT:
        return False
    compact_source = re.sub(r"\s+", "", source)
    normalized_source = _normalized(source)
    open_list = compact_source.find("包括但不限于")
    quantified_open_list = (
        open_list >= 0
        and bool(re.search(
            r"任何[^；。\n]{0,80}(?:异常|情况|事件|发现|结果)[^；。\n]{0,80}$",
            compact_source[:open_list],
        ))
        and not re.search(r"(?:全部|均需|均须|同时满足)", compact_source[:open_list])
    )
    if expression.operator == LogicalOperator.ANY and len(expression.children) == 2:
        children = expression.children
        if all(child.kind == "predicate" for child in children):
            left, right = (
                _normalized(re.sub(r"[（(](?:如|例如)[^）)]*[）)]$", "",
                                   child.predicate.attribute))
                for child in children
            )
            prefix = 0
            while (prefix < min(len(left), len(right))
                   and left[prefix] == right[prefix]):
                prefix += 1
            common = 0
            while (common < min(len(left), len(right)) - prefix
                   and left[-common - 1] == right[-common - 1]):
                common += 1
            if prefix >= 2 and common >= 2:
                first, second = left[prefix:len(left) - common], right[prefix:len(right) - common]
                suffix = left[-common:]
                shared_prefix = left[:prefix]
                shared_negation = any(
                    token in shared_prefix
                    for token in ("没有", "否认", "未见", "未发现", "未发生", "未患",
                                  "未使用", "未接受", "未完成", "未进行", "不存在",
                                  "不具备", "不符合", "不满足")
                ) or shared_prefix.endswith("无") or suffix.endswith(
                    ("均无", "皆无", "不存在", "未发生", "未完成")
                )
                stage_terms = {"预筛", "预筛期", "筛选", "筛选期", "导入", "导入期",
                               "基线", "基线期", "随机", "随机期", "首次给药", "首次给药期"}
                if (len(first) >= 2 and len(second) >= 2
                        and not shared_negation
                        and not {first, second} <= stage_terms
                        and not second.startswith(("以上", "以下", "等于", "更多", "更少"))):
                    for repeat_length in range(common + 1):
                        repeated, trailing = suffix[:repeat_length], suffix[repeat_length:]
                        shared_phrase = f"{left[:prefix]}{first}{repeated}或{second}{repeated}{trailing}"
                        if (any(shared_phrase in re.sub(r"\s+", "", line) for line in source.splitlines())
                                and all(
                                    any(shared_phrase in re.sub(r"\s+", "", line)
                                        for clause in child.predicate.exact_source_clauses
                                        for line in clause.splitlines())
                                    for child in children)):
                            return True
            if common >= 4:
                suffix = left[-common:]
                first, second = left[:-common], right[:-common]
                shared_phrase = f"{first}或{second}{suffix}"
                if (len(first) >= 2 and len(second) >= 2
                        and shared_phrase in normalized_source
                        and all(
                            any(shared_phrase in _normalized(clause)
                                for clause in child.predicate.exact_source_clauses)
                            for child in children
                        )):
                    return True
    child_clauses = [
        [
            _normalized(clause)
            for predicate in iter_atomic_predicates(child)
            for clause in predicate.exact_source_clauses
            if _normalized(clause) and _normalized(clause) in normalized_source
        ]
        for child in expression.children
    ]
    # Chinese source locators commonly let adjacent alternatives both own the
    # connector ("A或" / "或B").  That overlap is stronger evidence than a
    # separator search and must not be rejected merely because the anchors
    # share the same character position.  Identical whole-sentence locators do
    # not pass this check because the connector is not at a branch boundary.
    if child_clauses and all(child_clauses):
        connector_owned = all(
            any(clause.endswith(("或", "和/或", "及/或")) for clause in left)
            or any(clause.startswith(("或", "和/或", "及/或")) for clause in right)
            for left, right in zip(child_clauses, child_clauses[1:])
        )
        if connector_owned:
            return True
    branch_anchors = [
        _branch_source_anchors(child, compact_source) for child in expression.children
    ]
    if any(not anchors for anchors in branch_anchors):
        return False
    for first in branch_anchors[0]:
        paths = [([first], [first[2]])]
        for anchors in branch_anchors[1:]:
            next_paths = []
            for path, terms in paths:
                for anchor in anchors:
                    if anchor[0] < path[-1][1]:
                        continue
                    next_paths.append(
                        ([*path, anchor], [*terms, anchor[2]])
                    )
            paths = next_paths
            if not paths:
                break
        for path, terms in paths:
            if all(term in {"筛选", "筛选期", "基线", "基线期"} for term in terms):
                continue
            separators = [
                _source_separator_in_shared_scope(compact_source, left, right)
                for left, right in zip(path, path[1:])
            ]
            if any(
                not right[2].startswith(("以上", "以下", "等于", "更多", "更少"))
                and (
                re.search(r"(?:和/或|及/或)", separator)
                or any(
                    not separator[match.end():].startswith(("以上", "等于"))
                    for match in re.finditer("或", separator)
                )
                )
                for (left, right), separator in zip(zip(path, path[1:]), separators)
            ):
                return True
            # 原文以“满足以下条件之一/任一”显式引导替代关系时，各分支之间的
            # 分隔可以由顿号、逗号或分号承担；分支本身仍必须逐一定名于原文。
            scoped_lead_in = any(
                (
                    match.end() <= path[0][0]
                    and _parenthetical_stack_at(compact_source, path[0][0])[:len(
                        _parenthetical_stack_at(compact_source, match.start())
                    )] == _parenthetical_stack_at(compact_source, match.start())
                    and not re.search(r"[。；;]", compact_source[match.end():path[0][0]])
                ) or (
                    match.start() >= path[-1][1]
                    and _parenthetical_stack_at(compact_source, match.start())
                    == _parenthetical_stack_at(compact_source, path[-1][0])
                    and not re.search(r"[、，；。:：;,]", compact_source[path[-1][1]:match.start()])
                )
                for match in _ALTERNATIVE_LEAD_IN.finditer(compact_source)
            )
            if scoped_lead_in and separators and all(
                re.fullmatch(r"(?:[、，；;,]|和|及|与)+", separator)
                for separator in separators
            ):
                return True
            if quantified_open_list and all(
                anchor[0] >= open_list + len("包括但不限于")
                for anchor in path
            # Punctuation must connect every branch at their shared scope;
            # nested notes and sentence boundaries are not alternative evidence.
            ) and separators and all(
                re.fullmatch(r"、+", separator) for separator in separators
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
            between = _normalized(text[end : match.start()])
            if start <= match.start() and not between:
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


def _scoped_population_notes(text: str) -> list[str]:
    notes: list[str] = []
    for match in re.finditer(r"[（(](?:注[：:])?[^（）()]*[）)]", text):
        note = match.group()
        interior = re.sub(r"^注[：:]", "", note[1:-1].strip()).strip()
        scoped = re.search(
            r"(?:若|如果|仅|只|对于|其中)[^）)]{0,120}(?:参与者|受试者|患者)",
            interior,
        ) or re.match(
            r"与[^，。；：:]{1,80}的[^，。；：:]{0,20}(?:参与者|受试者|患者)",
            interior,
        )
        if scoped:
            notes.append(note)
    return notes


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
        r"(?:(?:和|与|及|或|、)(?:预筛|筛选|导入|基线|随机|首次给药)(?:期|访视)?(?:时)?)*"
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

    # Concessive and scope-preserving qualifiers are not independent clinical
    # entities.  When an exact source clause contains the complete qualifier,
    # its owning predicate already preserves that obligation.  Requiring a
    # second invented predicate (for example one whose attribute is merely
    # "even if ...") would damage the clinical rule rather than decompose it.
    if normalized_segment.startswith(
        ("即使", "即便", "无论", "不论", "例如但不限于", "包括但不限于", "但不限于")
    ) and any(normalized_segment in clause for clause in clauses):
        return True

    terms = [predicate.source_term, predicate.attribute, predicate.semantic_proposition]
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


def _qualifier_is_structured(rule: Rule, segment: str) -> bool:
    """A cited qualifier is covered only when its corresponding rule field exists."""

    normalized = _normalized(segment)
    cited = [
        component
        for component in rule.components
        if any(
            normalized in _normalized(clause)
            for predicate in iter_atomic_predicates(component.expression)
            for clause in predicate.exact_source_clauses
        )
    ]
    if not cited:
        return False

    stage = re.fullmatch(
        r"(筛选|基线)(?:访视|期)?(?:和|或|及|与)(筛选|基线)(?:访视|期)?时|"
        r"(筛选|基线)(?:访视|期)?时(?:存在下列任一感染者)?",
        normalized,
    )
    if stage:
        if len(cited) != len(rule.components):
            return False
        required = {
            ReviewStage.SCREENING if name == "筛选" else ReviewStage.BASELINE
            for name in stage.groups() if name in {"筛选", "基线"}
        }
        return all(
            required <= {item.due_stage for item in component.evidence_requirements}
            for component in cited
        )

    time_match = re.fullmatch(
        r"(首次给药|首剂)(前|后)(\d+)(天|日|周|星期|个月|年)内",
        normalized,
    )
    if time_match:
        anchor, direction, value, unit = time_match.groups()
        expected_anchor = AnchorType.FIRST_DOSE_DATE
        expected_direction = TimeDirection.BEFORE if direction == "前" else TimeDirection.AFTER
        return all(
            any(
                (constraint := expression.time_constraint) is not None
                and constraint.anchor_type == expected_anchor
                and constraint.direction == expected_direction
                and (
                    (constraint.upper_bound is not None
                     and constraint.upper_bound.value == int(value)
                     and _unit_matches_source(constraint.upper_bound.unit.value, unit))
                    or (constraint.upper_bound_days == int(value) and unit in {"天", "日"})
                )
                for expression in _walk_expression_tree(component.expression)
                if expression.kind == "predicate"
            )
            for component in cited
        )

    repeat = re.fullmatch(r"可进行(\d+)次复测", normalized)
    if repeat:
        return any(
            predicate.repeat_scheme is not None
            and predicate.repeat_scheme.permission == "optional"
            and predicate.repeat_scheme.maximum_repeats == int(repeat.group(1))
            and any(
                normalized in _normalized(excerpt)
                for excerpt in predicate.repeat_scheme.source_excerpts
            )
            for component in cited
            for predicate in iter_atomic_predicates(component.expression)
        )
    return False


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
    r"|(?:以下|下列|如下|下述)[^，。；\n]{0,8}任何一(?:种|类|项|条)?"
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
    tokens = set(re.findall(
        r"(?<![A-Za-z0-9.])[-+−]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][-+]?\d+)?",
        text,
    ))
    tokens = {token.replace(",", "").replace("−", "-") for token in tokens}
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
    if normalized_unit in normalized_text and (
        not re.search(r"[a-z]", normalized_unit)
        or re.search(r"(?<![a-z])" + re.escape(normalized_unit) + r"(?![a-z])", normalized_text)
    ):
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
    """Recognize numeric frequency shapes, never infer their period semantics."""

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
        r"(?:≥|至少|不低于|大于或等于)?\s*"
        r"(?P<count>\d+)\s*次"
    )
    count_before_event_pattern = re.compile(
        r"(?P<duration>\d+)\s*(?P<duration_unit>天|日|周|星期|个月|月|年)内"
        r"[^，。；]{0,12}?(?:≥|至少|不低于|大于或等于)\s*"
        r"(?P<count>\d+)\s*次\s*(?:发生|出现|发作|复发|感染)"
    )
    occurrence_day_pattern = re.compile(
        r"(?P<duration>\d+)\s*(?P<duration_unit>天|日|周|星期|个月|月|年)"
        r"\s*(?:内)?\s*(?:≥|大于或等于|不低于|至少)\s*"
        r"(?P<count>\d+)\s*(?:天|日)"
    )
    every_period_day_pattern = re.compile(
        r"每\s*(?P<duration>\d+)?\s*(?P<duration_unit>天|日|周|星期|个月|月|年)"
        r"[^，。；]{0,12}?(?:≥|大于或等于|不低于|至少)\s*"
        r"(?P<count>\d+)\s*(?P<count_unit>天|日|次)"
    )
    for match in (*history_pattern.finditer(text), *count_before_event_pattern.finditer(text)):
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
                int(match.group("duration") or "1"),
                unit_by_marker[match.group("duration_unit")],
                int(match.group("count")),
                "次" if match.group("count_unit") == "次" else "天",
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


def _predicate_frequency_bindings(predicate) -> set[str]:
    """A literal locator supplements, rather than replaces, semantic identity."""

    bindings = {_normalized(predicate.attribute)}
    term = _normalized(predicate.source_term or "")
    if term and any(term in _normalized(clause) for clause in predicate.exact_source_clauses):
        bindings.add(term)
    bindings.discard("")
    return bindings


def _predicate_preserves_frequency(
    predicate, spec: tuple[int, TimeUnit, int, str]
) -> bool:
    duration, duration_unit, minimum, count_unit = spec
    frequency_clauses = [
        clause
        for clause in predicate.exact_source_clauses
        if spec in _source_frequency_specs(clause)
    ]
    # 语义身份可能带频次分母前缀（如“1周内无任何白天户外活动的天数”），而逐字
    # 子句只写“定义为1周≥4天…”；剥离前导周期短语与尾部“的/天数”后再核对绑定词
    # （EX-04 反例，2026-09-18 会商）。
    def _strip_binding_suffix(text: str) -> str:
        return re.sub(
            r"(?:发生次数|发作次数|复发次数|既往史|现病史|病史|的?天数|的)$", "", text
        )

    binding_terms = set()
    for binding in _predicate_frequency_bindings(predicate):
        variants = (
            binding,
            re.sub(r"^有", "", binding),
            re.sub(r"^\d+\s*(?:个?天|个?日|周|星期|个月|月|年)内", "", binding),
        )
        binding_terms.update(variants)
        binding_terms.update(_strip_binding_suffix(item) for item in variants)
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


def _frequency_window_on_example_head(predicate, component_source: str = "") -> bool:
    window = predicate.occurrence_window
    if window is None:
        return False
    bindings = _predicate_frequency_bindings(predicate)
    for clause in dict.fromkeys((*predicate.exact_source_clauses, component_source)):
        for _head, member, definition in nested_example_definitions(clause):
            member_binding = _normalized(member)
            if not member_binding or any(member_binding in binding for binding in bindings):
                continue
            if any(
                window.duration.value == duration
                and window.duration.unit == unit
                and (
                    window.minimum_count == count
                    or (
                        predicate.unit == count_unit
                        and predicate.value == count
                    )
                )
                for duration, unit, count, count_unit in _source_frequency_specs(definition)
            ):
                return True
    return False


def _frozen_nested_frequency_definitions(
    component_id: str,
    draft: ProtocolDeconstructionDraft,
    source_input: ProtocolDeconstructionInput,
):
    mapping = next(
        (item for item in draft.component_drafts
         if item.proposed_component.rule_component_id == component_id),
        None,
    )
    if mapping is None:
        return []
    materials = {item.source_span_id: item.text for item in source_input.source_materials}
    return [
        (head, member, definition)
        for ref in mapping.source_refs
        for head, member, definition in nested_example_definitions(materials.get(ref, ""))
        if _source_frequency_specs(definition)
    ]


def _source_proves_unsupported_member_frequency(excerpts: Sequence[str]) -> bool:
    return any(
        _source_frequency_specs(definition)
        for excerpt in excerpts
        for _head, _member, definition in nested_example_definitions(excerpt)
    )


def _source_proves_unsupported_whole_requirement(restricted, rule, item, materials) -> bool:
    """Allow a whole source-bound requirement to remain unresolved, not a fragment."""

    if (rule.components or len(rule.restricted_components) != 1
            or len(restricted.source_excerpts) != 1
            or set(restricted.source_span_ids) != set(item.source_span_ids)):
        return False
    excerpt = restricted.source_excerpts[0]
    source = _normalized(excerpt)
    outside_notes = excerpt
    for note in _scoped_population_notes(excerpt):
        outside_notes = outside_notes.replace(note, "")
    if (_has_explicit_quantity(outside_notes)
            or (_numeric_tokens(outside_notes) and _source_comparators(outside_notes))):
        return False
    return bool(
        source == _normalized(rule.source_text)
        and (
            _localized_open_list_exception_requires_exclusivity([excerpt])
            or re.search(
                r"[（(](?:注[：:])?[^）)]{0,80}(?:若|如果|仅|只|对于|与|其中|符合)"
                r"[^）)]{1,80}(?:参与者|受试者|患者)[^）)]{0,50}(?:必须|需|应|须)",
                excerpt,
            )
        )
        and all(_normalized(materials.get(ref, "")) in source
                for ref in item.source_span_ids)
    )


def _source_proves_unsupported_scoped_branch(
    restricted, rule, source_texts: Sequence[str],
) -> bool:
    """Accept a complete conditional note beside executable siblings, never a fragment."""

    if not rule.components:
        return False
    excerpts = [_normalized(text) for text in restricted.source_excerpts]
    for note in _scoped_population_notes(rule.source_text):
        normalized = _normalized(note)
        if (not any(note in text for text in source_texts)
                or not re.search(r"(?:必须|需|应|须)", note)
                or _source_comparators(note)
                or _has_explicit_quantity(note)
                or not any(text == normalized for text in excerpts)
                or not all(text and text in normalized for text in excerpts)):
            continue
        if any(
            normalized == _normalized(clause)
            for component in rule.components
            for root in (component.expression, component.exception_expression)
            if root is not None
            for predicate in iter_atomic_predicates(root)
            for clause in predicate.exact_source_clauses
        ):
            continue
        if any(
            other is not restricted
            and normalized in {_normalized(text) for text in other.source_excerpts}
            for other in rule.restricted_components
        ):
            continue
        return True
    return False


def _restricted_component_capability_proof(restricted, rule, item, materials) -> str | None:
    """Recognize only existing source-proven limitations, not model self-reports."""
    if _source_proves_unsupported_member_frequency(restricted.source_excerpts):
        return "nested_member_frequency"
    mapped_texts = [materials.get(ref, "") for ref in restricted.source_span_ids]
    if _source_proves_unsupported_scoped_branch(restricted, rule, mapped_texts):
        return "scoped_population_note"
    if _source_proves_unsupported_whole_requirement(restricted, rule, item, materials):
        return "whole_scoped_requirement"
    return None


def _has_explicit_quantity(text: str) -> bool:
    """Distinguish clinical quantities from section numbers and identifiers."""

    return bool(re.search(
        r"(?:\d+(?:\.\d+)?|[一二两三四五六七八九十百千]+)\s*"
        r"(?:次|天|日|周|星期|个月|月|年|岁|小时|分钟|条|项|个|级|分|倍|%|％|mg|g|kg|mL|L|IU|U/L|℃)",
        text,
        flags=re.IGNORECASE,
    ))


def _frequency_definition_required_as_sibling(expression, definitions) -> bool:
    if expression.kind != "logical":
        return False
    if expression.operator == LogicalOperator.ALL:
        child_predicates = [list(iter_atomic_predicates(child)) for child in expression.children]
        for head, member, definition in definitions:
            parent = _normalized(head)
            member_binding = _normalized(member)
            if not parent or not member_binding:
                continue
            parent_branches = {
                index for index, predicates in enumerate(child_predicates)
                if any(binding.startswith(parent)
                       for item in predicates for binding in _predicate_frequency_bindings(item))
            }
            member_branches = {
                index for index, predicates in enumerate(child_predicates)
                if any(
                    any(member_binding in binding for binding in _predicate_frequency_bindings(item))
                    and any(_predicate_preserves_frequency(item, spec)
                            for spec in _source_frequency_specs(definition))
                    for item in predicates
                )
            }
            if any(left != right for left in parent_branches for right in member_branches):
                return True
    return any(
        _frequency_definition_required_as_sibling(child, definitions)
        for child in expression.children
    )


def _source_comparators(text: str) -> set[Comparator]:
    """Return unambiguous comparator classes explicitly expressed in source."""
    found: set[Comparator] = set()
    patterns = (
        (Comparator.GTE, r"≥|>=|大于或等于|不低于|至少|\bat\s+least\b|\bgreater\s+than\s+or\s+equal\s+to\b"),
        (Comparator.LTE, r"≤|<=|小于或等于|不超过|至多|\bat\s+most\b|\bless\s+than\s+or\s+equal\s+to\b"),
        (Comparator.GT, r"(?<![≥>])>(?!=)|(?<!不)超过|大于(?!或等于)|\bgreater\s+than\b(?!\s+or\s+equal)|\bmore\s+than\b"),
        (Comparator.LT, r"(?<![≤<])<(?!=)|(?<!不)低于|小于(?!或等于)|\bless\s+than\b(?!\s+or\s+equal)"),
    )
    for comparator, pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            found.add(comparator)
    return found


def _rule_map(draft: ProtocolDeconstructionDraft) -> dict[str, Rule]:
    return {rule.rule_id: rule for rule in draft.proposed_rules}


class ProtocolDeconstructionGate:
    """Run all twelve checks and return Chinese, repair-scoped issues."""

    def __init__(self, *, artifact_reader=None):
        self.artifact_reader = artifact_reader

    def evaluate(
        self,
        source_input: ProtocolDeconstructionInput,
        draft: ProtocolDeconstructionDraft,
        *,
        source_spans: Mapping[str, ProtocolSourceSpan],
        interpretation_conflicts: Sequence[InterpretationConflict] = (),
        previous_draft: ProtocolDeconstructionDraft | None = None,
        declared_diff: ProtocolDraftDiffDeclaration | None = None,
        scope_review_reader=None,
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
            source_input, draft, issues["temporal_semantics"], anchor_context,
            scope_review_reader=scope_review_reader or self.artifact_reader,
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
            for component in (*rule.components, *rule.restricted_components)
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
            parent_source = _catalog_text(rule, source_input)
            local_open_exception_segments = [
                segment for segment in re.split(r"[；;\n]", parent_source)
                if _localized_open_list_exception_requires_exclusivity([segment])
            ]
            has_sibling_exception = any(
                item.exception_expression is not None for item in rule.components
            )
            for component in rule.components:
                text = _component_text(
                    rule,
                    component.rule_component_id,
                    draft,
                    source_input,
                )
                population_predicates = [
                    predicate
                    for root in (component.expression, component.exception_expression)
                    if root is not None
                    for predicate in iter_atomic_predicates(root)
                    if predicate.applicable_population is not None
                ]
                if population_predicates:
                    source_bound = all(
                        _population_source_bound(node)
                        for root in (component.expression, component.exception_expression)
                        if root is not None
                        for node in _walk_expression_tree(root)
                        if node.kind == "predicate"
                        and node.predicate.applicable_population is not None
                    )
                    supported_position = (
                        not any(predicate.applicable_population is not None
                                for predicate in iter_atomic_predicates(component.exception_expression))
                        if component.exception_expression is not None else True
                    ) and all(
                        _is_population_scoped_any(node)
                        for node in _walk_expression_tree(component.expression)
                        if node.kind == "logical" and node.operator == LogicalOperator.ANY
                        and any(predicate.applicable_population is not None
                                for predicate in iter_atomic_predicates(node))
                    )
                    if not source_bound or not supported_position:
                        issues.append(_issue(
                            "boolean_logic", "APPLICABLE_POPULATION_SOURCE_UNBOUND",
                            f"{component.display_code} 的适用人群尚未逐字绑定当前条件，或其条件关系尚不支持局部未决。",
                            [predicate.predicate_id for predicate in population_predicates],
                            action="保留适用人群及对应条件的完整逐字原文；不得借用兄弟条件的人群文字，也不得把未经核实的人群当作不适用或已满足。",
                        ))
                    else:
                        issues.append(_issue(
                            "boolean_logic",
                            "APPLICABLE_POPULATION_NOT_EVALUATED",
                            f"{component.display_code} 指定了适用人群，但当前审核计算尚不能核实人群条件。",
                            [predicate.predicate_id for predicate in population_predicates],
                            level="提醒",
                            impact="完整要求可供工作稿采用，但本条人群适用性保持未决，不能自动给出确定入排结论。",
                            action=(
                                "请在审核结果中保留具体适用范围未决及方案定位；"
                                "完成本例有源适用性核对前，不得把本条件当作已满足、不适用或未触发。"
                            ),
                        ))
                normalized = _normalized(text)
                has_and = any(
                    token in normalized
                    for token in ("且", "并且", "同时", "均需", "全部")
                )
                predicate_source = "\n".join(
                    clause
                    for predicate in iter_atomic_predicates(component.expression)
                    for clause in predicate.exact_source_clauses
                    if _normalized(clause) and _normalized(clause) in normalized
                )
                has_or = _has_unambiguous_disjunction(predicate_source) or any(
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
                    and not _any_is_source_scoped_longer_washout(node, text)
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
                    and _branches_have_source_disjunction(expression, text)
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
                component_has_local_open_exception = any(
                    _normalized(clause) in _normalized(segment)
                    for segment in local_open_exception_segments
                    for clause in trigger_clauses
                    if len(_normalized(clause)) >= 6
                )
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
                            action=(
                                "请核对例外究竟作用于本条件还是共享原文中的相邻分支。"
                                "属于本条件时结构化例外；只属于相邻分支时，"
                                "将本条件的逐字来源片段缩窄到完整适用分支，保留父规则原文和相邻分支。"
                            ),
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
                        (
                            _localized_open_list_exception_requires_exclusivity(trigger_clauses)
                            or (
                                component_has_local_open_exception
                                and any(
                                    item.comparator == Comparator.EXISTS
                                    for item in iter_atomic_predicates(component.exception_expression)
                                )
                            )
                        )
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
                elif (
                    component_has_local_open_exception
                    and has_sibling_exception
                    and any(
                        "包括但不限于" in _normalized(predicate.attribute)
                        or "但不限于" in _normalized(predicate.attribute)
                        for predicate in iter_atomic_predicates(component.expression)
                    )
                ):
                    issues.append(
                        _issue(
                            "boolean_logic",
                            "LOCAL_EXCEPTION_REENTERED_OPEN_LIST",
                            f"{component.display_code} 仍保留可覆盖局部例外的开放上位条件，却没有本分支的例外约束。",
                            [component.rule_component_id],
                            action="请核对开放上位条件会否重新纳入被括号排除的对象；若会，应以有源的排他条件约束该分支，且不得豁免同时存在的其他触发情况。",
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
                        has_bound_assessment = any(
                            predicate.predicate_id in requirement.predicate_ids
                            and "investigator_assessment" in requirement.required_source_types
                            for requirement in component.evidence_requirements
                        )
                        if (has_numeric_value and predicate.requires_professional_judgment
                                and not has_bound_assessment):
                            issues.append(_issue(
                                "numeric_semantics", "NUMERIC_JUDGMENT_SOURCE_UNBOUND",
                                f"{component.display_code} 的数值条件被标为研究者判断，但没有对应的书面评估资料要求。",
                                [predicate.predicate_id],
                                action="核对原文要求的判断对象；医生评定的数值需逐项绑定评估记录，客观数值与另行作出的临床判断不得相互代替。",
                            ))
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
    def _temporal_semantics(source_input, draft, issues, anchor_context=None, *, scope_review_reader=None):
        stage_aliases = frozen_review_stage_aliases(source_input)
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
            try:
                parent_scope = frozen_parent_scope_fragments(
                    source_input, rule.official_code,
                    scope_has_stages=lambda text: bool(_source_review_stages([text])),
                    is_substantive=lambda text: bool(_substantive_obligation_segments(text)),
                )
            except FrozenParentScopeError as exc:
                issues.append(_issue(
                    "temporal_semantics", exc.code,
                    f"{rule.official_code} 的冻结来源身份不完整，不能核对总标题作用范围。",
                    list(exc.source_refs),
                    action="请核对冻结来源和官方目录身份；这不是研究者医学判断事项。",
                ))
                parent_scope = ()
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
                frozen_definitions = _frozen_nested_frequency_definitions(
                    component.rule_component_id, draft, source_input
                )
                for head, member, definition in frozen_definitions:
                    parent = _normalized(head)
                    member_binding = _normalized(member)
                    quoted_scopes = [
                        _normalized(excerpt)
                        for excerpt in (component_draft.source_excerpts if component_draft else ())
                    ]
                    if any(
                        binding.startswith(parent) or member_binding in binding
                        for item in atomic_expressions
                        for binding in _predicate_frequency_bindings(item.predicate)
                    ) or any(
                        len(quote) >= 4 and (
                            parent in quote or quote in parent or member_binding in quote
                        )
                        for quote in quoted_scopes
                    ):
                        component_frequency_specs.update(_source_frequency_specs(definition))
                if any(
                    _frequency_definition_required_as_sibling(root, frozen_definitions)
                    for root in roots
                ):
                    issues.append(_issue(
                        "temporal_semantics",
                        "FREQUENCY_DEFINITION_SCOPE_UNVERIFIED",
                        f"{component.display_code} 把列举项的频次定义变成上位条件的必备条件。",
                        [component.rule_component_id],
                        action="请保留列举项的定义作用域，不得以该列举项频次收窄上位条件。",
                    ))
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
                stage_fragments = (
                    component_draft.source_excerpts if has_precise_excerpt
                    else [component_text]
                )
                required_stages = _source_review_stages(stage_fragments, stage_aliases=stage_aliases)
                source_cued_stages = set(required_stages)
                predicate_clauses = [
                    clause for expression in atomic_expressions
                    for clause in expression.predicate.exact_source_clauses
                ]
                direct_stages = _source_review_stages(predicate_clauses, stage_aliases=stage_aliases)
                unbound_shared_stages: set[ReviewStage] = set()
                omitted_parent_scope = [
                    item for item in parent_scope
                    if not any(_normalized(item.excerpt.rstrip("：:")) in _normalized(clause)
                               for clause in stage_fragments)
                    and _source_review_stages([item.excerpt], stage_aliases=stage_aliases) - source_cued_stages
                ]
                for item in omitted_parent_scope:
                    unbound_shared_stages.update(_source_review_stages([item.excerpt], stage_aliases=stage_aliases))
                if direct_stages:
                    for fragment in stage_fragments:
                        # Existing structural classification only diagnoses a
                        # missing binding. It never authorizes dropping a stage.
                        if _substantive_obligation_segments(fragment.rstrip("：:")):
                            continue
                        if any(_normalized(fragment) in _normalized(clause)
                               for clause in predicate_clauses):
                            continue
                        unbound_shared_stages.update(
                            _source_review_stages([fragment], stage_aliases=stage_aliases) - direct_stages
                        )
                try:
                    reviewed_stages = reviewed_scope_stages(
                        source_input, draft, rule, component, parent_scope, scope_review_reader,
                        heading_stages=[stage.value for stage in _source_review_stages([item.excerpt for item in parent_scope], stage_aliases=stage_aliases)],
                    )
                except OfficialScopeReviewError as exc:
                    reviewed_stages = None
                    unresolved_scope = isinstance(exc, OfficialScopeUnresolvedError)
                    issues.append(_issue(
                        "temporal_semantics", exc.code,
                        (f"{component.display_code} 的总标题作用范围仍有待核实：" + "；".join(exc.dimensions)
                         if unresolved_scope else f"{component.display_code} 的总标题核对记录与当前原文或条件不一致，不能采用。"),
                        [component.rule_component_id],
                        action=("请核对所列具体作用范围；当前疑问不能沿用旧版已核清结果。" if unresolved_scope
                                else "请核对本次原文、条件和原始核对回答；旧记录不能替代当前核对。"),
                    ))
                if reviewed_stages is not None:
                    required_stages = reviewed_stages
                    source_cued_stages = set(reviewed_stages)
                    direct_stages = set(reviewed_stages)
                    omitted_parent_scope = []
                    unbound_shared_stages.clear()
                baseline_decision_anchors = {
                    AnchorType.BASELINE_DATE,
                    AnchorType.RANDOMIZATION_DATE,
                    AnchorType.FIRST_DOSE_DATE,
                    AnchorType.STUDY_DRUG_ADMINISTRATION_DATE,
                }
                has_final_review_anchor = any(
                    expression.time_constraint is not None
                    and expression.time_constraint.anchor_type
                    in baseline_decision_anchors
                    and expression.time_constraint.direction
                    in {TimeDirection.BEFORE, TimeDirection.ON}
                    for expression in atomic_expressions
                )
                if has_final_review_anchor:
                    required_stages.add(ReviewStage.BASELINE)
                # A disputed heading cannot create downstream validity duties.
                # Keep the scope failure and independently bound child/final nodes.
                validity_stages = (
                    (source_cued_stages if omitted_parent_scope else direct_stages)
                    | ({ReviewStage.BASELINE} if has_final_review_anchor else set())
                    if unbound_shared_stages else required_stages
                )
                actual_stages = {
                    requirement.due_stage
                    for requirement in component.evidence_requirements
                }
                missing_stages = required_stages - actual_stages
                unsupported_stages = (
                    (actual_stages & {
                        ReviewStage.SCREENING, ReviewStage.RUN_IN, ReviewStage.BASELINE,
                    }) - required_stages
                    if source_cued_stages else set()
                )
                if unbound_shared_stages:
                    issues.append(_issue(
                        "temporal_semantics", "REVIEW_STAGE_SCOPE_UNVERIFIED",
                        f"{component.display_code} 的总标题与子项审核节点尚未核清作用范围。",
                        [component.rule_component_id],
                        action=(
                            "请先核对总标题是否要求每个子项在所有节点满足，还是分别描述各节点的要求；"
                            "真正统辖本子项的限定语须与条件分别逐字绑定，只有上下文作用的文字不得作为本项义务。"
                            "核清前不要仅为消除提示新增审核节点，也不要删除实际共同要求；测量时点不等于审核节点。"
                        ),
                    ))
                elif missing_stages:
                    stage_names = {
                        ReviewStage.SCREENING: "筛选期",
                        ReviewStage.RUN_IN: "导入期",
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
                if unsupported_stages and not unbound_shared_stages:
                    issues.append(_issue(
                        "temporal_semantics", "REVIEW_STAGE_ADDITIONAL_SCOPE_UNVERIFIED",
                        f"{component.display_code} 的部分资料核对节点尚无本子项来源支持。",
                        [component.rule_component_id],
                        action=(
                            "请区分原文规定的测量节点、资料采集节点和最终审核节点；"
                            "新增节点须有共同限定、最终复核或解释来源依据，不能为保持旧资料要求数量而保留。"
                            "若只是旧稿误添的要求，可在限定范围修订中删除该要求；"
                            "不得删除真实共同要求、阈值、计算定义或其他子项。"
                        ),
                    ))
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
                    expected_validity_stages = (
                        validity_stages if unbound_shared_stages else
                        validity_stages or {
                            requirement.due_stage for requirement in matching_requirements
                        }
                    )
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
                    if missing_validity_stages or (
                        not expected_validity_stages and not unbound_shared_stages
                    ):
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
                        _predicate_temporal_text(predicate, component_text)
                        if has_precise_excerpt
                        else component_text
                    )
                    anchor_text = predicate_text + "\n" + _shared_named_anchor_lead_in(
                        predicate, component_text
                    )
                    expected = {
                        anchor
                        for anchor, markers in anchor_markers.items()
                        if any(marker in anchor_text for marker in markers)
                    }
                    component_expected = {
                        anchor
                        for anchor, markers in anchor_markers.items()
                        if any(marker in component_text for marker in markers)
                    }
                    constraint = expression.time_constraint
                    has_before = any(
                        marker.endswith("前") and marker in anchor_text
                        for markers in anchor_markers.values()
                        for marker in markers
                    )
                    has_on = any(
                        marker.endswith("时") and marker in anchor_text
                        for markers in anchor_markers.values()
                        for marker in markers
                    )
                    has_after = any(
                        marker.endswith("后") and marker in anchor_text
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
                    if not predicate_frequency_specs and predicate.occurrence_window is not None:
                        # 语义身份常省略频次分母（如“无任何白天户外活动的天数”，而
                        # “1周≥4天”留在逐字来源里）。结构化 occurrence_window 已保存时，
                        # 用完整逐字来源重新识别频次形态，并仍以
                        # _predicate_preserves_frequency 严格核对绑定词、周期与次数；
                        # 不匹配保持为空 → 维持 fail-closed，且该 duration 不再被
                        # 误判为无锚回溯（EX-04 反例，2026-09-18 会商）。
                        clause_frequency_specs = _source_frequency_specs(
                            "\n".join(predicate.exact_source_clauses)
                        )
                        if clause_frequency_specs:
                            predicate_frequency_specs = {
                                spec
                                for spec in clause_frequency_specs
                                if _predicate_preserves_frequency(predicate, spec)
                            }
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
                    if _frequency_window_on_example_head(predicate, component_text):
                        issues.append(_issue(
                            "temporal_semantics",
                            "FREQUENCY_DEFINITION_SCOPE_UNVERIFIED",
                            f"{component.display_code} 把列举项括号内的发生频次附到了更宽的上位条件，适用对象未核清。",
                            [predicate.predicate_id],
                            action="请核对频次是否仅定义列举中的具体情况；不得把该频次加到整个上位条件。不能证明作用范围时保留待核，不得作为已核规则发布。",
                        ))
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
                        expected_validity_stages = (
                            validity_stages if unbound_shared_stages else
                            validity_stages or {
                                requirement.due_stage
                                for requirement in matching_requirements
                            }
                        )
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
                        if missing_validity or (
                            not expected_validity_stages and not unbound_shared_stages
                        ):
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
                    if occurrence_window is not None and occurrence_window.scope is None:
                        issues.append(_issue(
                            "temporal_semantics", "FREQUENCY_SCOPE_NOT_DECLARED",
                            f"{component.display_code} 的计数期间尚未明确区分。",
                            [predicate.predicate_id],
                            action="按方案逐字声明 occurrence_window.scope；不能确定期间划分或量词时保留 unresolved 和具体疑问，不得默认滚动或日历期间。",
                        ))
                    if (occurrence_window is not None and occurrence_window.scope is not None
                            and occurrence_window.scope.quantifier in {"any", "every"}
                            and occurrence_window.horizon is None):
                        issues.append(_issue(
                            "temporal_semantics", "FREQUENCY_HORIZON_NOT_DECLARED",
                            f"{component.display_code} 的多个计数期间覆盖范围尚未声明。",
                            [predicate.predicate_id],
                            action="按方案保留统计范围及逐字依据；未明范围填写unresolved，不得借用上传资料起止日或擅设不限期间。",
                        ))
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
                                    action="若频率本身是触发条件，请由该事件的谓词保存次数和周期；若是列举项括号内的定义，频次只能附着于该列举项，不得成为上位条件的限制。不能明确作用范围时保留待核。",
                                )
                            )
                    elif occurrence_window is not None:
                        issues.append(
                            _issue(
                                "temporal_semantics",
                                    "FREQUENCY_SOURCE_FORM_UNVERIFIED",
                                    f"{component.display_code} 的发生周期尚未通过原文对应核对。",
                                    [predicate.predicate_id],
                                    action="保留完整频次原文并核对周期、量词及次数或天数；当前形式识别未匹配不等于原文没有该要求，不得为通过检查而删除频次限制。",
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
                    if TREATMENT_PERIOD_SOURCE_PATTERN.search(predicate_text):
                        expected_periods.add(ProtocolPeriod.TREATMENT_PERIOD)
                    if STUDY_PERIOD_SOURCE_PATTERN.search(predicate_text):
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
        for rule in draft.proposed_rules:
            for restricted in rule.restricted_components:
                refs.extend(restricted.source_span_ids)
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

        rules_by_code = {rule.official_code: rule for rule in draft.proposed_rules}
        valid_restricted_by_parent: dict[str, list] = {}
        for item in source_input.parent_rule_catalog.items:
            code = item.official_code or ""
            rule = rules_by_code.get(code)
            if rule is None:
                continue
            for restricted in rule.restricted_components:
                mapped_texts = [materials.get(ref, "") for ref in restricted.source_span_ids]
                source_valid = (
                    set(restricted.source_span_ids) <= set(item.source_span_ids)
                    and set(restricted.source_span_ids) <= formal_ids
                    and all(any(excerpt in text for text in mapped_texts)
                            for excerpt in restricted.source_excerpts)
                )
                if not source_valid:
                    issues.append(_issue(
                        "source_coverage", "RESTRICTED_COMPONENT_SOURCE_INVALID",
                        f"{code} 的待处理要求未能逐字对应当前方案来源。",
                        [code, restricted.rule_component_id], scope=[code],
                    ))
                    continue
                if (restricted.limitation_kind == "consumer_unavailable"
                        and _restricted_component_capability_proof(
                            restricted, rule, item, materials) is None):
                    issues.append(_issue(
                        "source_coverage", "RESTRICTED_COMPONENT_CAPABILITY_UNPROVEN",
                        f"{code} 的原文位置已对应，但尚不能核实所报审核能力缺口的范围。",
                        [code, restricted.rule_component_id], scope=[code],
                        action="请保留已明确且可独立判断的条件，核对实际缺少的表达或计算能力；"
                        "不能仅凭模型声明撤下要求，也不要求研究者替程序补判。",
                    ))
                    continue
                valid_restricted_by_parent.setdefault(code, []).append(restricted)
                component_refs_by_parent.setdefault(code, set()).update(restricted.source_span_ids)

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
            headings = frozen_parent_scope_fragments(
                source_input, official_code,
                scope_has_stages=lambda text: bool(_source_review_stages([text])),
                is_substantive=lambda text: bool(_substantive_obligation_segments(text)),
            )
            obligations = []
            for text in parent_texts:
                # A structurally identified stage lead-in supplies scope, not
                # another clinical predicate. Its relationship is checked above.
                for heading in headings:
                    if text.startswith(heading.excerpt):
                        text = text[len(heading.excerpt):]
                for segment in _substantive_obligation_segments(text):
                    obligations.append(segment)
                    obligations.extend(
                        note for note in _scoped_population_notes(segment)
                        if note != segment
                    )
            predicates = [
                predicate
                for expression in _walk_expressions(rule)
                for predicate in iter_atomic_predicates(expression)
            ]
            covered_by_restriction: set[str] = set()
            for restricted in valid_restricted_by_parent.get(official_code, []):
                if (restricted.limitation_kind == "consumer_unavailable"
                        and _source_proves_unsupported_whole_requirement(
                            restricted, rule, item, materials
                        )):
                    covered_by_restriction.update(obligations)
                    continue
                matches = [
                    segment for segment in obligations
                    if any(_normalized(segment) == _normalized(excerpt)
                           for excerpt in restricted.source_excerpts)
                ]
                scoped_note = _source_proves_unsupported_scoped_branch(
                    restricted, rule, parent_texts
                )
                if (len(matches) != 1
                        or (len(restricted.source_excerpts) != 1 and not scoped_note)
                        or matches[0] in covered_by_restriction
                        or (not scoped_note and any(
                            _predicate_binds_obligation(predicate, matches[0])
                            for predicate in predicates
                        ))):
                    issues.append(_issue(
                        "source_coverage", "RESTRICTED_COMPONENT_SCOPE_INVALID",
                        f"{official_code} 的待核范围没有唯一对应一项未被条件承接的原文要求。",
                        [official_code, restricted.rule_component_id], scope=[official_code],
                    ))
                    continue
                if (restricted.limitation_kind == "interpretation_unresolved"
                        and _numeric_tokens(matches[0])
                        and _source_comparators(matches[0])):
                    issues.append(_issue(
                        "source_coverage", "RESTRICTED_COMPONENT_SWALLOWS_NUMERIC_BOUND",
                        f"{official_code} 的数值界限和比较方向在原文中已明确，不能仅以含义待核撤下该条件。",
                        [official_code, restricted.rule_component_id], scope=[official_code],
                        action="请保留有原文依据的数值条件；如确有例外或适用范围不明，单独定位原文并核对，不得把整条界限改为待澄清。",
                    ))
                    continue
                covered_by_restriction.add(matches[0])
            uncovered = []
            for segment in dict.fromkeys(obligations):
                if segment in covered_by_restriction:
                    continue
                if segment in _scoped_population_notes(segment):
                    covered = any(
                        predicate.applicable_population is not None
                        and any(
                            _normalized(segment) == _normalized(clause)
                            for clause in predicate.exact_source_clauses
                        )
                        for predicate in predicates
                    )
                else:
                    covered = _qualifier_is_structured(rule, segment) or any(
                        _predicate_binds_obligation(predicate, segment)
                        for predicate in predicates
                    )
                if not covered:
                    uncovered.append(segment)
            # A lead-in names the parent condition; it is not a second test when
            # every actual listed requirement is already represented.
            if len(obligations) > 2 and len(predicates) > 1:
                uncovered = [
                    segment for segment in uncovered
                    if not (
                        (lead := _normalized(segment)).startswith("符合")
                        and lead.endswith("标准")
                        and lead in _normalized(rule.source_text)
                        and ("任一" not in lead or rule.kind == RuleKind.EXCLUSION)
                        and all(
                            other == segment
                            or other in covered_by_restriction
                            or _qualifier_is_structured(rule, other)
                            or any(_predicate_binds_obligation(predicate, other)
                                   for predicate in predicates)
                            for other in obligations
                        )
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
                            *[f"未承接：{segment}" for segment in uncovered],
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
        invalid_observation_policies = []
        invalid_repeat_sources = []
        invalid_half_life_sources = []
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
                    invalid_repeat_sources.extend(
                        predicate.predicate_id
                        for root in (component.expression, component.exception_expression) if root is not None
                        for predicate in iter_atomic_predicates(root) if predicate.repeat_scheme is not None
                    )
                    if any(node.time_constraint is not None and node.time_constraint.half_life_evidence is not None
                           for root in (component.expression, component.exception_expression) if root is not None
                           for node in _walk_expression_tree(root) if node.kind == "predicate"):
                        invalid_half_life_sources.append(component.rule_component_id)
                    continue
                component_text = "\n".join(component_draft.source_excerpts)
                expressions = [component.expression]
                if component.exception_expression is not None:
                    expressions.append(component.exception_expression)
                for expression in expressions:
                    for node in _walk_expression_tree(expression):
                        if node.kind != "predicate":
                            continue
                        evidence = node.time_constraint.half_life_evidence if node.time_constraint else None
                        if evidence is not None and (
                            evidence.source_span_id not in component_draft.source_refs
                            or evidence.source_span_id not in allowed & formal_ids
                            or evidence.source_excerpt not in materials.get(evidence.source_span_id, "")
                            or not any(evidence.source_excerpt in excerpt for excerpt in component_draft.source_excerpts)
                            or not any(evidence.applies_to_quote in clause for clause in node.predicate.exact_source_clauses)
                        ):
                            invalid_half_life_sources.append(node.predicate.predicate_id)
                    for predicate in iter_atomic_predicates(expression):
                        policy = predicate.observation_policy
                        repeat = predicate.repeat_scheme
                        if repeat is not None and any(
                            span not in component_draft.source_refs or span not in allowed & formal_ids
                            or excerpt not in materials.get(span, "")
                            or not any(excerpt in clause for clause in predicate.exact_source_clauses)
                            for span, excerpt in zip(repeat.source_span_ids, repeat.source_excerpts, strict=True)
                        ):
                            invalid_repeat_sources.append(predicate.predicate_id)
                        if policy is None:
                            if _requires_observation_policy(predicate):
                                invalid_observation_policies.append(predicate.predicate_id)
                        elif (policy.selection is not None and policy.selection.window_order is None) or any(
                            span_id not in component_draft.source_refs
                            or excerpt not in materials.get(span_id, "")
                            for span_id, excerpt in zip(
                                policy.source_span_ids, policy.source_excerpts,
                            )
                        ):
                            invalid_observation_policies.append(predicate.predicate_id)
                        clauses = predicate.exact_source_clauses
                        if not clauses or any(
                            clause not in component_text for clause in clauses
                        ):
                            invalid_clauses.append(predicate.predicate_id)
        if invalid_repeat_sources:
            issues.append(_issue(
                "source_coverage", "REPEAT_SCHEME_SOURCE_UNVERIFIED",
                "部分复查要求尚未对应到本条条件的方案原文。",
                sorted(set(invalid_repeat_sources)),
                action="核对复查许可、条件、次数、期限及结果采用方式的逐字来源；不得从病例检查顺序补推方案要求。",
            ))
        if invalid_half_life_sources:
            issues.append(_issue(
                "source_coverage", "HALF_LIFE_SOURCE_UNVERIFIED",
                "部分洗脱要求的半衰期数值缺少与本项适用对象一致的正式原文依据。",
                sorted(set(invalid_half_life_sources)),
                action="核对本项所引方案原文、适用对象及数值单位；没有明确时长时保留倍数要求，不填写推测数值。",
            ))
        if invalid_observation_policies:
            issues.append(_issue(
                "source_coverage", "OBSERVATION_POLICY_SOURCE_UNVERIFIED",
                "方案明确规定的多次结果采用方式尚未结构化，或已有采用规则的原文与来源不符。",
                sorted(set(invalid_observation_policies)),
                action="仅将方案明确规定的最近一次、任一次、全部或复查结果采用方式逐字绑定；未规定时不要编造。当前若有多条合格记录，资料对应须保留待核，不得默取最新或有利值。",
            ))
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
        # 来源摘录检查不证明命题语义；其含义仍须经单独核实。
        # 有逐字摘录的组件已由 PREDICATE_CLAUSE_NOT_IN_SOURCE 覆盖，此处只补该
        # 检查看不到的情形，不重复报告同一缺陷。
        unclosed_proposition_predicates: list[str] = []
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
                expressions = [component.expression]
                if component.exception_expression is not None:
                    expressions.append(component.exception_expression)
                propositional_atoms = [
                    predicate
                    for expression in expressions
                    for predicate in iter_atomic_predicates(expression)
                    if predicate.semantic_proposition is not None
                ]
                if not propositional_atoms:
                    continue
                for predicate in propositional_atoms:
                    proposition = predicate.semantic_proposition or ""
                    cited = "\n".join(predicate.exact_source_clauses)
                    if re.search(
                        r"(?:方案原文|原文|上位条件|上位疾病|例示|列举|分支|任一满足|"
                        r"谓词|消费者|\bANY\b|\bALL\b)",
                        proposition, flags=re.IGNORECASE,
                    ):
                        issues.append(_issue(
                            "source_coverage", "SEMANTIC_PROPOSITION_RULE_COMMENTARY",
                            "语义核对内容在解释方案结构，不能由受试者病历证明。",
                            [predicate.predicate_id],
                            action="请将方案结构关系留在规则来源核对中；语义命题仅描述可从本例原始资料核实的临床事实。",
                        ))
                    if (_numeric_tokens(proposition) - _numeric_tokens(cited)
                            or _source_comparators(proposition) - _source_comparators(cited)):
                        issues.append(_issue(
                            "source_coverage", "SEMANTIC_PROPOSITION_UNSOURCED_BOUND",
                            "语义核对内容增加了所引原文没有的数值或比较方向。",
                            [predicate.predicate_id],
                            action="仅保留逐字来源支持的数值和方向；不明确的组合关系须保留待核，不能自行补足。",
                        ))
                if component_draft is not None and component_draft.source_excerpts:
                    continue
                mapped_texts = [
                    materials.get(ref, "")
                    for ref in (
                        component_draft.source_refs
                        if component_draft is not None
                        else ()
                    )
                ]
                unclosed_proposition_predicates.extend(
                    predicate.predicate_id
                    for predicate in propositional_atoms
                    if not predicate.exact_source_clauses
                    or any(
                        not any(clause in text for text in mapped_texts)
                        for clause in predicate.exact_source_clauses
                    )
                )
        if unclosed_proposition_predicates:
            issues.append(
                _issue(
                    "source_coverage",
                    "SEMANTIC_PROPOSITION_SOURCE_NOT_CLOSED",
                    "部分条件缺少可逐字核对的方案原文依据。",
                    sorted(set(unclosed_proposition_predicates)),
                    action="请核对本项条件对应的方案原文，不以摘要、改写或其他条款的内容代替。",
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
