"""Bounded source-to-candidate comparison for split protocol statements."""

from __future__ import annotations

import json
import hashlib
import re
from dataclasses import asdict
from typing import Literal

from pydantic import Field, StrictBool, model_serializer, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.control_evidence_policy import has_explicit_evidence_policy
from app.domain.contracts.rules import TimeConstraint
from app.protocols.control_scope_sources import resolve_ancestor_scope_citation, validate_scope_citations


SOURCE_CANDIDATE_ALIGNMENT_VERSION = "phase5/control-source-candidate-alignment/v8"
EVIDENCE_POLICY_ALIGNMENT_VERSION = "phase5/control-evidence-policy-alignment/v2"
NATIVE_TABLE_ALIGNMENT_CONTEXT_VERSION = "native-table-review-scope/v3"
NATIVE_ROW_ACTION_COVERAGE_VERSION = "native-row-action-coverage/v2"
CANDIDATE_SOURCE_CLOSURE_CONTEXT_VERSION = "candidate-source-closure-context/v1"
SOURCE_CANDIDATE_QUOTE_SCOPE_VERSION = "statement-grounded-candidate-quotes/v1"
SOURCE_CONDITIONAL_GROUP_ALIGNMENT_VERSION = "source-conditional-group-alignment/v1"
SOURCE_REPEAT_COUNT_ALIGNMENT_VERSION = "source-repeat-count-alignment/v1"
SOURCE_EVENT_INTERVAL_ALIGNMENT_VERSION = "source-event-interval-alignment/v1"


class SourceCandidateAlignmentValidationError(ValueError):
    pass


class CandidateNumericAlignmentError(SourceCandidateAlignmentValidationError):
    def __init__(self, *, item, candidate, atoms, source_refs, repeat_scheme_only=False):
        paths = [(item.candidate_index, group_index, atom_index)
                 for group_index, group in enumerate(candidate.obligation_expression.groups)
                 for atom_index, atom in enumerate(group.atoms)
                 if atom in atoms and any(_NUMBER.search(quote)
                     and (repeat_scheme_only or any(re.search(pattern, quote) for pattern, _ in _COMPARISON_WORDS))
                     for quote in atom.source_excerpts)]
        self.error_detail = {
            "reason": "repeat_scheme_missing" if repeat_scheme_only else "numeric_predicate_missing",
            "source_refs": list(source_refs),
            "atom_paths": [list(path) for path in paths],
            "required_source_excerpt": item.source_excerpt,
        }
        super().__init__("动作次数缺少有源复查合同，不能宣布完整" if repeat_scheme_only else
                         "数值原文缺少可核验的比较条件，不能宣布完整")


class EvidencePolicyCheckError(SourceCandidateAlignmentValidationError):
    """A source-policy mismatch, scoped to the unchanged candidate field."""

    code = "EVIDENCE_POLICY_UNJUSTIFIED"

    def __init__(self, message, *, item, evidence_index, dimension, reason, policy=None):
        field = {
            "contemporaneous_objective_source": "source_policy/requires_contemporaneous_objective_source",
            "screening_record_transcription": "source_policy/allows_screening_record_transcription",
            "result_validity": "source_policy/result_validity_status",
            "required_source_types": "required_source_types",
        }[dimension]
        self.error_detail = {
            "code": self.code,
            "statement_ids": [item.statement_index],
            "candidate_indexes": [item.candidate_index],
            "json_path": f"/candidate_drafts/{item.candidate_index}/minimum_evidence/{evidence_index}/{field}",
            "source_refs": list(policy.source_span_ids) if policy else [],
            "retry_class": "source_semantic_review",
            "affected_dependents": [item.candidate_index],
            "evidence_index": evidence_index,
            "dimension": dimension,
            "reason": reason,
        }
        if dimension == "result_validity":
            self.error_detail["related_paths"] = [
                f"/candidate_drafts/{item.candidate_index}/minimum_evidence/{evidence_index}/source_policy/result_validity_constraint",
            ]
        if reason == "out_of_scope":
            self.error_detail["json_path"] = f"/candidate_drafts/{item.candidate_index}/minimum_evidence"
        super().__init__(message)


def evidence_policy_alignment_pairs(interpretation, coverage, wire):
    """Select literal action candidates whose policy is not proved by the quote alone."""
    pairs = set()
    for entry in coverage:
        if entry.status not in {"expressed", "semantically_aligned", "candidate_linked"}:
            continue
        statement = interpretation.statements[entry.statement_index]
        if "action" not in statement.decision_functions:
            continue
        for index in entry.action_candidate_indexes:
            if any(has_explicit_evidence_policy(row) for row in wire.candidate_drafts[index].minimum_evidence):
                pairs.add((entry.statement_index, index))
    return sorted(pairs)


def require_evidence_policy_alignment(batch, interpretation, coverage, wire, alignment):
    pairs = set(evidence_policy_alignment_pairs(interpretation, coverage, wire))
    if not pairs:
        return
    proven = reusable_proven_alignment_items(batch, interpretation, coverage, wire, alignment)
    if not pairs <= {(item.statement_index, item.candidate_index) for item in proven}:
        raise SourceCandidateAlignmentValidationError("资料来源限制缺少绑定当前候选与原文的核对证明")


def reviewed_source_type_mismatch_paths(batch, interpretation, coverage, wire, alignment):
    """Select a field repair, never apply the reviewer's proposed clinical value."""
    proven = reusable_proven_alignment_items(
        batch, interpretation, coverage, wire, alignment, require_positive=False,
    )
    paths = set()
    for item in proven:
        if item.decision != "incomplete":
            continue
        for check in item.evidence_policy_checks:
            if check.dimension != "required_source_types":
                continue
            evidence = wire.candidate_drafts[item.candidate_index].minimum_evidence[check.evidence_index]
            if frozenset(check.source_types) != frozenset(evidence.required_source_types):
                paths.add((item.candidate_index, check.evidence_index))
    return tuple(sorted(paths))

_COMPARISON_WORDS = (
    (r"(?:≥|>=|大于等于|不小于|至少|最少|不少于|不低于|以上)", "gte"),
    (r"(?:≤|<=|小于等于|不大于|不多于|至多|最多|不超过|不高于|以下)", "lte"),
    (r"(?:>(?!=)|(?<!不)大于(?!等于)|(?<!不)多于|(?<!不)超过|(?<!不)高于)", "gt"),
    (r"(?:<(?!=)|(?<!不)小于(?!等于)|(?<!不)少于|(?<!不)低于)", "lt"),
)
_NUMBER = re.compile(r"(?<![\d.])\d+(?:\.\d+)?(?![\d.])")
_QUANTIFIER_GROUPS = {
    "all": ("全部", "所有", "每"),
    "any": ("任一", "任何", "至少一"),
}
_ANCHOR_WORDS = (("知情", "icf_date"), ("筛选", "screening_date"),
                 ("基线", "baseline_date"), ("随机", "randomization_date"),
                 ("首次给药", "first_dose_date"), ("末次给药", "last_dose_date"),
                 ("研究结束", "study_completion_date"))


def _source_fragment(source: str, scope: str, excerpt: str) -> str | None:
    if excerpt in source:
        return excerpt
    if scope and excerpt.startswith(scope):
        fragment = excerpt[len(scope):].lstrip("，,：:")
        if fragment and fragment in source:
            return fragment
    return None


def _split_obligations_cover_source(source: str, scope: str, atoms) -> bool:
    """Require literal, nonoverlapping coverage; only AND joiners may be implicit."""

    covered = [False] * len(source)
    first_start = len(source)
    first_atom = None
    for atom in atoms:
        fragments = {
            fragment for quote in atom.source_excerpts
            if (fragment := _source_fragment(source, scope, quote)) is not None
        }
        if len(fragments) != 1:
            return False
        fragment = next(iter(fragments))
        if source.count(fragment) != 1:
            return False
        start = source.index(fragment)
        if start < first_start:
            first_start, first_atom = start, atom
        if any(covered[start:start + len(fragment)]):
            return False
        covered[start:start + len(fragment)] = [True] * len(fragment)
    prefix = source[:first_start].strip("，,。；;：: ")
    if prefix:
        rendered = (
            getattr(first_atom, "statement", ""),
            getattr(getattr(first_atom, "evaluation", None), "proposition", ""),
        )
        if not any(prefix in value for value in rendered if isinstance(value, str)):
            return False
        covered[:first_start] = [True] * first_start
    remainder = "".join(char for char, present in zip(source, covered, strict=True)
                        if not present).strip("，,。；;：: ")
    return remainder in {"", "且", "并且", "同时"}


def _conditioned_obligations_cover_source(source, scope, candidate, group, atoms, selected_atoms):
    """A literal common trigger may carry the prefix, never the consequence."""
    if candidate.trigger_expression is None:
        return False
    from .protocol_control_source_interpretation import normalize_source_excerpt

    fragments = [fragment for atom in atoms for quote in atom.source_excerpts
                 if (fragment := _source_fragment(source, scope, normalize_source_excerpt(quote))) is not None]
    if not fragments or any(source.count(fragment) != 1 for fragment in fragments):
        return False
    offset = min(source.index(fragment) for fragment in fragments)
    prefix = source[:offset].strip("，,。；;：: ")
    branches = candidate.trigger_expression.groups
    indexes = group.applies_to_trigger_branch_indexes
    if (not prefix or not indexes or any(index >= len(branches) for index in indexes)):
        return False
    if not all(any(atom in selected_atoms and normalize_source_excerpt(atom.statement) == prefix
                   for atom in branches[index].atoms) for index in indexes):
        return False
    relevant = [branch for branch in branches if any(
        atom in selected_atoms and normalize_source_excerpt(atom.statement) == prefix for atom in branch.atoms)]
    if not all(any(all(atom in branch.atoms for atom in branches[index].atoms)
                   for index in indexes) for branch in relevant):
        return False
    return _split_obligations_cover_source(source[offset:], scope, atoms)


def _common_trigger_preserves_visit_time(batch, statement, candidate, selected_atoms):
    from .protocol_control_source_interpretation import (
        normalize_source_excerpt, source_has_single_visit_anchor, source_visit_scope_matches,
    )
    if (statement.unresolved or not source_has_single_visit_anchor(statement)
            or candidate.trigger_expression is None):
        return False
    word = normalize_source_excerpt(statement.time_words[0])
    if _NUMBER.search(word):
        return False
    def carries_visit(atom):
        text = normalize_source_excerpt(atom.statement)
        if not text.startswith(word):
            return False
        remainder = text[len(word):]
        # A visit label must be a separate scope, not the prefix of a different window.
        return not remainder or bool(re.match(r"^[，,；;：:、。]|^(?:如|若|当|如果)", remainder))

    if not all(any(atom in selected_atoms and carries_visit(atom)
                   for atom in branch.atoms) for branch in candidate.trigger_expression.groups):
        return False
    stages = {stage.workflow_stage_id: stage for stage in batch.known_workflow_stage_targets}
    nodes = [node for node in candidate.review_node_bindings if node.role.value == "decide_at_node"]
    return bool(nodes) and all(
        (stage := stages.get(node.workflow_stage_id)) is not None
        and node.review_stage == stage.review_stage
        and bool(stage.source_span_ids) and bool(stage.source_excerpts)
        and source_visit_scope_matches(word, normalize_source_excerpt(stage.display_name))
        for node in nodes
    )


def _matches_time_anchor_direction(word: str, atoms, *, source: str = "") -> bool:
    from .protocol_control_source_interpretation import normalize_source_excerpt

    anchors = {anchor for label, anchor in _ANCHOR_WORDS if label in word}
    directions = ({"before"} if "前" in word and "后" not in word else
                  {"after"} if "后" in word and "前" not in word else
                  {"on"} if "进入" in word else set())
    if not anchors and len(directions) == 1 and len(word) > 2 and source and not _NUMBER.search(word):
        # Prove source representation only; never substitute a named visit date.
        # The existing interval consumer keeps this software capability gap UNKNOWN.
        return any(
            (constraint := getattr(atom, "time_constraint", None)) is not None
            and constraint.anchor_type.value == "event_date"
            and constraint.direction.value in directions
            and all(getattr(constraint, field) is None for field in (
                "lower_bound_days", "upper_bound_days", "lower_bound", "upper_bound",
                "half_life_multiplier", "combined_window_selection"))
            and (spec := getattr(atom, "evaluation", None)) is not None
            and spec.determination_mode == "semantic" and spec.time_purpose == "interval_condition"
            and word in normalize_source_excerpt(atom.statement)
            and word in normalize_source_excerpt(spec.proposition or "")
            and word in source
            and any(normalize_source_excerpt(quote) == source for quote in atom.source_excerpts)
            and any(normalize_source_excerpt(quote) == source for quote in spec.source_excerpts)
            for atom in atoms
        )
    return len(anchors) == 1 and len(directions) == 1 and any(
        constraint.anchor_type.value in anchors and constraint.direction.value in directions
        for atom in atoms
        if (constraint := getattr(atom, "time_constraint", None)) is not None
    )


class EvidencePolicyCheck(ContractModel):
    evidence_index: int = Field(ge=0)
    dimension: Literal["contemporaneous_objective_source", "screening_record_transcription",
                       "result_validity", "required_source_types"]
    boolean_value: StrictBool | None = None
    validity_status: Literal["specified", "not_specified", "unknown"] | None = None
    validity_constraint: TimeConstraint | None = None
    source_types: list[str] | None = None
    source_span_id: str = Field(min_length=1)
    source_excerpt: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dimension(self):
        if not self.source_span_id.strip() or not self.source_excerpt.strip():
            raise ValueError("资料要求核对的位置和摘录不得为空白")
        if self.dimension == "result_validity":
            if (self.validity_status is None or self.boolean_value is not None
                    or self.source_types is not None
                    or (self.validity_status == "specified") != (self.validity_constraint is not None)):
                raise ValueError("有效期核对须明确状态并保留对应约束，不得混入其他维度")
        elif self.dimension == "required_source_types":
            if (self.source_types is None or any(not value.strip() for value in self.source_types)
                    or self.boolean_value is not None or self.validity_status is not None
                    or self.validity_constraint is not None):
                raise ValueError("资料种类核对须使用明确列表，不得混入其他维度")
        elif (self.validity_status is not None or self.validity_constraint is not None
              or self.source_types is not None):
            raise ValueError("原件与转述核对只使用真、假或未知")
        return self


class SourceCandidateAlignmentItem(ContractModel):
    statement_index: int = Field(ge=0)
    candidate_index: int = Field(ge=0)
    decision: Literal["fully_expressed", "incomplete", "uncertain"]
    source_excerpt: str = Field(min_length=1)
    candidate_atom_quotes: list[str] = Field(default_factory=list)
    unresolved_dimensions: list[str] = Field(default_factory=list)
    evidence_policy_checks: list[EvidencePolicyCheck] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def preserve_ordinary_identity(self, handler):
        body = handler(self)
        if not self.evidence_policy_checks:
            body.pop("evidence_policy_checks", None)
        return body

    @model_validator(mode="after")
    def require_grounded_positive(self) -> "SourceCandidateAlignmentItem":
        if self.decision == "fully_expressed" and (
            not self.candidate_atom_quotes or self.unresolved_dimensions
        ):
            raise ValueError("完整表达须列出候选原句且不得保留未核维度")
        return self


class SourceCandidateAlignmentProof(ContractModel):
    statement_index: int = Field(ge=0)
    candidate_index: int = Field(ge=0)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_text: str = Field(min_length=1)


class SourceCandidateAlignment(ContractModel):
    version: Literal[SOURCE_CANDIDATE_ALIGNMENT_VERSION]
    items: list[SourceCandidateAlignmentItem] = Field(min_length=1)
    # Application-owned proof, never requested from the semantic reader.
    proofs: list[SourceCandidateAlignmentProof] = Field(default_factory=list)


def candidate_alignment_response_format() -> dict[str, object]:
    schema = SourceCandidateAlignment.model_json_schema()
    schema["properties"].pop("proofs")
    schema.get("$defs", {}).pop("SourceCandidateAlignmentProof", None)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_candidate_alignment_v8_policy_v2",
            "strict": True,
            "schema": schema,
        },
    }


def _candidate_source_closure(batch, candidate):
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    unknown = set(candidate.source_structure_unit_ids) - units.keys()
    if unknown:
        raise ValueError("候选核对来源闭包越出本批授权原文")
    return [unit.model_dump(mode="json") for unit in batch.owned_units
            if unit.structure_unit_id in candidate.source_structure_unit_ids]


def _statement_grounded_atoms(unit, statement, candidate):
    from app.agents.protocol_control_source_interpretation import normalize_source_excerpt

    source = normalize_source_excerpt(statement.quoted_text)
    scope = normalize_source_excerpt(statement.scope_quote or "")
    unit_text = normalize_source_excerpt(unit.excerpt)
    return [atom
        for expression in (candidate.applicability_expression, candidate.trigger_expression,
                           candidate.obligation_expression, candidate.exception_expression)
        if expression is not None
        for group in expression.groups for atom in group.atoms
        if (set(atom.source_span_ids) & set(unit.source_span_ids)
            and atom.source_excerpts
            and all(normalize_source_excerpt(quote) in unit_text for quote in atom.source_excerpts)
            and any(_source_fragment(source, scope, normalize_source_excerpt(quote)) is not None
                    or source in normalize_source_excerpt(quote)
                    for quote in atom.source_excerpts))]


def _independent_source_obligation_groups(unit, statement, interpretation, coverage,
                                        candidate, candidate_index, selected_atoms):
    """Keep unscoped alternatives strict; scoped source siblings activate separately.

    This is only literal/source and activation evidence, not approval of another
    statement's meaning. Its own source coverage and review remain mandatory.
    """
    groups = candidate.obligation_expression.groups
    if candidate.trigger_expression is None or candidate.exception_expression is not None:
        return []
    branches = candidate.trigger_expression.groups
    selected_groups = [group for group in groups if any(atom in selected_atoms for atom in group.atoms)]
    if not selected_groups or any(not group.applies_to_trigger_branch_indexes for group in groups):
        return []
    if any(index >= len(branches) for group in groups for index in group.applies_to_trigger_branch_indexes):
        return []
    by_statement = {entry.statement_index: entry for entry in coverage}
    others = []
    for index, other in enumerate(interpretation.statements):
        entry = by_statement.get(index)
        if (other != statement and other.structure_unit_id == statement.structure_unit_id
                and not other.unresolved and entry is not None
                and entry.structure_unit_id == other.structure_unit_id
                and entry.status in {"candidate_linked", "semantically_aligned", "expressed"}
                and candidate_index in entry.action_candidate_indexes
                and (entry.status != "expressed" or candidate_index in entry.candidate_indexes)):
            others.append(other)
    other_atoms = [atom for other in others for atom in _statement_grounded_atoms(unit, other, candidate)]
    current_atoms = _statement_grounded_atoms(unit, statement, candidate)
    from .protocol_control_source_interpretation import normalize_source_excerpt
    source_parts = re.split("[，,]", normalize_source_excerpt(statement.quoted_text), maxsplit=1)
    source_conditions = [atom for branch in branches for atom in branch.atoms
                         if atom in selected_atoms and atom in current_atoms
                         and len(source_parts) == 2
                         and normalize_source_excerpt(atom.statement) == source_parts[0]]
    independent = []
    for group in groups:
        if group in selected_groups:
            continue
        if (not all(atom in other_atoms and atom not in current_atoms for atom in group.atoms)
                or any(set(group.applies_to_trigger_branch_indexes)
                       == set(selected.applies_to_trigger_branch_indexes) for selected in selected_groups)):
            continue
        # Every sibling route must still activate a group carrying this source
        # requirement. Exact condition-atom inclusion proves implication; no
        # word matching, inferred mutually-exclusive states or OR shortcut.
        if all(any(
            all(atom in [*branches[index].atoms, *source_conditions]
                for atom in branches[selected_index].atoms)
            for selected in selected_groups for selected_index in selected.applies_to_trigger_branch_indexes
        ) for index in group.applies_to_trigger_branch_indexes):
            independent.append(group)
    return independent


def source_declares_uncompared_action_count(statement) -> bool:
    from .protocol_control_source_interpretation import normalize_source_excerpt
    source = normalize_source_excerpt(statement.quoted_text)
    numbers = set(_NUMBER.findall(source))
    return bool("action" in statement.decision_functions
                and "threshold" not in statement.decision_functions and len(numbers) == 1
                and f"{next(iter(numbers))}次" in source
                and re.search(r"复查|复测|复验|复检|重测|重复(?:测量|检查|检验|检测)|再次(?:测量|检查|检验|检测)|retest|recheck|repeat(?:ed)?(?:measurements?|tests?|examinations?)", source, re.IGNORECASE)
                and not any(re.search(pattern, source) for pattern, _direction in _COMPARISON_WORDS))


def _source_repeat_count_is_preserved(unit, statement, source, numbers, directions, predicates, atoms):
    """A declared repeat count is not a measurement-comparison predicate.

    This proves only the source count's representation. Permission, trigger,
    acquisition qualification and result use remain with the repeat consumers.
    """
    if len(numbers) != 1 or directions or predicates:
        return False
    from app.domain.contracts.repeat_scheme import RepeatScheme, validate_repeat_source
    from .protocol_control_source_interpretation import normalize_source_excerpt

    number = next(iter(numbers))
    if f"{number}次" not in source:
        return False
    schemes = []
    for atom in atoms:
        evaluation = atom.evaluation
        if evaluation is None or evaluation.repeat_scheme is None:
            continue
        scheme = RepeatScheme.model_validate(evaluation.repeat_scheme.model_dump(mode="json"))
        scheme.require_current_extraction()
        validate_repeat_source(scheme, evaluation.source_span_ids, evaluation.source_excerpts)
        if ((scheme.permission == "required" and statement.force not in {"required", "conditional"})
                or (scheme.permission == "optional" and statement.force in {"required", "prohibited"})
                or (scheme.permission == "forbidden" and statement.force != "prohibited")):
            return False
        if (scheme.count_status == "specified" and str(scheme.maximum_repeats) == number
                and set(scheme.source_span_ids) <= set(unit.source_span_ids)
                and any(source == normalize_source_excerpt(quote) for quote in scheme.source_excerpts)):
            schemes.append(scheme)
    return len(schemes) == 1


def build_candidate_alignment_prompt(batch, interpretation, wire, pairs) -> str:
    from app.protocols.procedure_catalog import schedule_column_scope

    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    selected = []
    for statement_index, candidate_index in pairs:
        statement = interpretation.statements[statement_index]
        candidate = wire.candidate_drafts[candidate_index]
        selected.append({
            "statement_index": statement_index,
            "candidate_index": candidate_index,
            "candidate_quote_scope_version": SOURCE_CANDIDATE_QUOTE_SCOPE_VERSION,
            "required_source_excerpt": statement.quoted_text,
            "source_statement": statement.model_dump(mode="json"),
            "source_unit": units[statement.structure_unit_id].excerpt,
            "candidate_source_closure": _candidate_source_closure(batch, candidate),
            "bound_visit_sources": [stage.model_dump(mode="json")
                for stage in batch.known_workflow_stage_targets
                if any(node.workflow_stage_id == stage.workflow_stage_id
                       for node in candidate.review_node_bindings)],
            "native_table_source": units[statement.structure_unit_id].model_dump(mode="json")
                if units[statement.structure_unit_id].table_context is not None else None,
            **({"native_review_scope": {
                "version": NATIVE_TABLE_ALIGNMENT_CONTEXT_VERSION,
                "workflow_stage_sources": [stage.model_dump(mode="json")
                    for stage in batch.known_workflow_stage_targets],
                "marked_columns": [asdict(column) for column in schedule_column_scope(
                    units[statement.structure_unit_id], batch.context_units)],
                "read_only_context_sources": [unit.model_dump(mode="json")
                    for unit in batch.context_units],
                "referenced_table_notes": batch.table_footnote_context_links,
            }} if units[statement.structure_unit_id].table_context is not None else {}),
            "allowed_candidate_atom_quotes": list(dict.fromkeys(
                atom.statement for atom in _statement_grounded_atoms(
                    units[statement.structure_unit_id], statement, candidate))),
            "candidate": candidate.model_dump(mode="json"),
        })
    native_scope_instruction = (
        "native_review_scope 给出宿主冻结的入排审核节点、逐列标记与原始只读上下文，不是采信或完整覆盖结论。"
        "先逐列从真实表头和单元格核对，再比较候选在当前入排审核范围的表达。"
        "at_or_before_baseline 的动作不能遗漏；明确 after_baseline 的标记仍保留原文，"
        "但不是要求当前候选新增后续治疗访视的入排判断。unresolved 的列不能因候选没有绑定就排除。"
        "若原文要求当前节点承诺或准备后续持续义务，或后续记录是当前判断的依赖，仍须保留该有源关系；"
        "不能仅因发生在基线后就删除它。"
        "脚注、同列/合并表头和当前时期的例外仍须核查，缺失或关系不明时具体列为未核，不能凭派生列标签补来源。"
        "source_statement 是前一步解释而非权威原文；它说缺表头时须检查 read_only_context_sources，"
        "不能把已有原始表头忽略后继续声称原文没有节点。候选的通用记录主体并非自动新增人群筛选条件；"
        "核对的是实际适用对象、范围与条件，不要求把无新限制的语法主语也逐字写在表格格内。"
        "特定亚组、对象改变或新的限制仍必须有原文依据，不以系统通用主体代替它。"
    ) if any("native_review_scope" in item for item in selected) else ""
    return (
        "你只核同一冻结方案原文与已有候选的语义对应，不新增条款，不判断受试者。"
        "此前的核对仅说明官方条款和访视目录未完整覆盖本句，不能据此断言本候选也未覆盖。"
        "逐项判断候选中已经写出的条件、对象、全称/数量、时间、否定、后果、例外和证据政策，"
        "是否完整表达本条要求，并核查它与候选其余有源要求的关系。多原子合取可以表达一句话。"
        "candidate_source_closure 是候选实际引用的授权原始结构单元，不是新的医学解释或采信结论。"
        "本条之外的条件或义务若来自该闭包中的其他原文，不能仅因本句没有重述就判为新增；"
        "须核共同前置、子项、例外及各自作用域，不得把无关邻句的限制借给本条。"
        "逐项完整仍只证明指定 statement_index；兄弟要求须各自处置，不因同一候选关联而自动完成。"
        "证据政策 action_completion 仅证明操作已经完成，不证明检查结果正常或达到入排阈值；"
        "原文若另有结果条件，不得用操作完成替代该条件；原文只要求完成操作时，也不得新增结果正常要求。"
        "required_source_types 是原文明文限定的可接受资料种类，不是建议示例；"
        "原文未限定时应为空列表。逐项核对候选的资料种类、同期原件、转述及有效期限制，"
        "不得因义务句子逐字相同就忽略新增的资料限制；无源新增限制选 incomplete，"
        "只有原文无法判清才选 uncertain。description 中明确标作示例的记录种类不构成硬限制。"
        "evidence_policy_checks 按 minimum_evidence 原顺序填写 evidence_index。先独立读原文政策，再比较候选，不能照抄候选值；"
        "对有明确资料种类、原件/转述布尔声明或有效期约束的行，逐项核 contemporaneous_objective_source、"
        "screening_record_transcription、result_validity；资料种类非空时另核 required_source_types。"
        "布尔只填 boolean_value 真/假/null，有效期填 validity_status 及仅 specified 时的完整 validity_constraint，"
        "资料种类填 source_types，其余值字段为 null。每项用该行 source_policy 内对应 span 和逐字摘录；"
        "本句未提及不等于全方案无限制，未查清用 null/unknown。无声明且全未知的行不额外核，列表为空。"
        "只有各维度都有源、无重复遗漏且与草稿一致（包括未知与未知）才可 fully_expressed；"
        "不一致列出具体维度，不能修改草稿或补写来源。相等只是核对一致，不代表患者符合或正式采用。"
        "仅当本句的‘任一项’等回指在同一冻结来源单元中有唯一明确的先行要求时，"
        "可引用该要求解释所指对象；不得借标题、其他来源单元或不明确的邻句新增条件。"
        "只有上述所有适用维度与原文一致，才选 fully_expressed；有确定差额选 incomplete，"
        "无法从冻结原文与候选判清选 uncertain。不得因为候选引用了同一来源或看起来临床合理就选完整。"
        "source_excerpt 必须逐字复制 required_source_excerpt，不得从 source_unit 补入前后文字；"
        "bound_visit_sources 仅说明候选绑定的冻结访视及其原始表头来源；"
        "同一标记列的时期、访视名、周数和日数可共同标识一次访视，不因短语数量判作多个访视。"
        "这不证明动作、脚注、例外、结果条件或资料限制已完整表达，仍须逐项核查；"
        "不得把另一列或缺出处的访视标签借给当前动作。"
        + native_scope_instruction
        + "candidate_atom_quotes 只能从 allowed_candidate_atom_quotes 原样选完整句，不得改写、补词或只摘短词。"
        "完整候选及其来源闭包用于核对关系，不授权把本条之外的候选原句填入本条引句；其他要求仍分别核对。"
        "不完整或不确定时列出具体 unresolved_dimensions；仅返回符合 Schema 的 JSON。\n"
        f"待核对应：{json.dumps(selected, ensure_ascii=False, sort_keys=True)}"
    )


def _alignment_digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _alignment_input_identity(batch, interpretation, wire, item):
    statement = interpretation.statements[item.statement_index]
    unit = next(unit for unit in batch.owned_units
                if unit.structure_unit_id == statement.structure_unit_id)
    candidates = wire.candidate_drafts if hasattr(wire, "candidate_drafts") else wire.candidates
    selected = candidates[item.candidate_index]
    candidate = selected.semantics if hasattr(selected, "semantics") else selected
    if candidate is None:
        raise ValueError("候选对应证明缺少完整候选")
    return (
        _alignment_digest({"protocol_version_id": batch.protocol_version_id,
                           "coverage_manifest_id": batch.coverage_manifest_id,
                           "statement": statement.model_dump(mode="json"),
                           "source_unit": unit.model_dump(mode="json"),
                           **({"conditional_group_alignment": SOURCE_CONDITIONAL_GROUP_ALIGNMENT_VERSION,
                               "same_unit_statements": [row.model_dump(mode="json")
                                   for row in interpretation.statements
                                   if row.structure_unit_id == statement.structure_unit_id]}
                              if candidate.trigger_expression is not None
                              and len(candidate.obligation_expression.groups) > 1 else {}),
                           **({"repeat_count_alignment": SOURCE_REPEAT_COUNT_ALIGNMENT_VERSION}
                              if any(atom.evaluation is not None and atom.evaluation.repeat_scheme is not None
                                     for group in candidate.obligation_expression.groups for atom in group.atoms)
                              else {}),
                           **({"event_interval_alignment": SOURCE_EVENT_INTERVAL_ALIGNMENT_VERSION}
                              if any(atom.time_constraint is not None and atom.time_constraint.anchor_type.value == "event_date"
                                     and atom.evaluation is not None and atom.evaluation.determination_mode == "semantic"
                                     and atom.evaluation.time_purpose == "interval_condition"
                                     and all(getattr(atom.time_constraint, field) is None for field in (
                                         "lower_bound_days", "upper_bound_days", "lower_bound", "upper_bound",
                                         "half_life_multiplier", "combined_window_selection"))
                                     for group in candidate.obligation_expression.groups for atom in group.atoms)
                              else {}),
                           **({"candidate_source_closure_version": CANDIDATE_SOURCE_CLOSURE_CONTEXT_VERSION,
                               "candidate_source_closure": _candidate_source_closure(batch, candidate)}
                              if len(candidate.source_structure_unit_ids) > 1 else {}),
                           **({"native_visit_correspondence": "v1",
                               "native_review_scope": NATIVE_TABLE_ALIGNMENT_CONTEXT_VERSION,
                               "context_units": [row.model_dump(mode="json") for row in batch.context_units],
                               "referenced_table_notes": batch.table_footnote_context_links,
                               "workflow_stage_sources": [stage.model_dump(mode="json")
                                   for stage in batch.known_workflow_stage_targets],
                               "bound_visit_sources": [stage.model_dump(mode="json")
                                   for stage in batch.known_workflow_stage_targets
                                   if any(node.workflow_stage_id == stage.workflow_stage_id
                                          for node in candidate.review_node_bindings)]}
                              if unit.table_context is not None else {}),
                           **({"evidence_policy_review": EVIDENCE_POLICY_ALIGNMENT_VERSION}
                              if any(has_explicit_evidence_policy(row) for row in candidate.minimum_evidence)
                              else {})}),
        _alignment_digest(candidate.model_dump(mode="json")),
    )


def bind_candidate_alignment(batch, interpretation, coverage, wire, alignment, response_text):
    """Freeze the exact input and actual JSON response after validation, not on resume."""
    if alignment.proofs:
        raise ValueError("模型不得提供程序拥有的候选对应证明")
    parsed = SourceCandidateAlignment.model_validate_json(response_text)
    if parsed != alignment or parsed.proofs:
        raise ValueError("候选对应证明未绑定实际模型返回")
    validate_candidate_alignment(batch, interpretation, coverage, wire, alignment)
    proofs = []
    for item in alignment.items:
        source_hash, candidate_hash = _alignment_input_identity(batch, interpretation, wire, item)
        proofs.append(SourceCandidateAlignmentProof(
            statement_index=item.statement_index, candidate_index=item.candidate_index,
            source_sha256=source_hash, candidate_sha256=candidate_hash,
            response_sha256=hashlib.sha256(response_text.encode("utf-8")).hexdigest(),
            response_text=response_text,
        ))
    return alignment.model_copy(update={"proofs": proofs})


def bind_partial_candidate_alignment(batch, interpretation, coverage, wire, alignment,
                                     response_text, expected_pairs):
    """Keep valid individual decisions bound to the unchanged complete response."""
    from .protocol_control_source_interpretation import normalize_source_excerpt

    parsed = SourceCandidateAlignment.model_validate_json(response_text)
    pairs = [(item.statement_index, item.candidate_index) for item in parsed.items]
    if (parsed != alignment or parsed.proofs
            or parsed.version != SOURCE_CANDIDATE_ALIGNMENT_VERSION
            or len(set(pairs)) != len(pairs) or set(pairs) != set(expected_pairs)
            or any(index >= len(interpretation.statements) for index, _ in pairs)):
        raise ValueError("候选核对回答的身份、范围或原始内容不一致")
    candidates = wire.candidate_drafts if hasattr(wire, "candidate_drafts") else wire.candidates
    if any(index >= len(candidates) for _, index in pairs):
        raise ValueError("候选核对回答越出冻结候选范围")
    by_statement = {entry.statement_index: entry for entry in coverage}
    for item in parsed.items:
        statement = interpretation.statements[item.statement_index]
        entry = by_statement.get(item.statement_index)
        selected = candidates[item.candidate_index]
        candidate = selected.semantics if hasattr(selected, "semantics") else selected
        if (candidate is None or entry is None
                or entry.structure_unit_id != statement.structure_unit_id
                or item.candidate_index not in entry.action_candidate_indexes
                or statement.structure_unit_id not in candidate.source_structure_unit_ids
                or normalize_source_excerpt(item.source_excerpt) != normalize_source_excerpt(statement.quoted_text)):
            raise ValueError("候选核对回答的来源身份不一致")
    items, proofs, failures = [], [], []
    for item in parsed.items:
        single = SourceCandidateAlignment(version=parsed.version, items=[item])
        try:
            validate_candidate_alignment(batch, interpretation, coverage, wire, single)
        except ValueError as exc:
            unit = next(unit for unit in batch.owned_units
                        if unit.structure_unit_id == interpretation.statements[item.statement_index].structure_unit_id)
            failures.append({
                "code": "SOURCE_CANDIDATE_ALIGNMENT_INVALID",
                "statement_ids": [item.statement_index],
                "candidate_indexes": [item.candidate_index],
                "json_path": f"/source_candidate_alignment/items/{pairs.index((item.statement_index, item.candidate_index))}",
                "source_refs": list(unit.source_span_ids),
                "retry_class": "source_semantic_review",
                "affected_dependents": [item.candidate_index],
                "message": str(exc),
                **getattr(exc, "error_detail", {}),
            })
            continue
        source_hash, candidate_hash = _alignment_input_identity(batch, interpretation, wire, item)
        items.append(item)
        proofs.append(SourceCandidateAlignmentProof(
            statement_index=item.statement_index, candidate_index=item.candidate_index,
            source_sha256=source_hash, candidate_sha256=candidate_hash,
            response_sha256=hashlib.sha256(response_text.encode("utf-8")).hexdigest(),
            response_text=response_text,
        ))
    bound = SourceCandidateAlignment(version=parsed.version, items=items, proofs=proofs) if items else None
    return bound, failures


def alignment_with_items(alignment, items):
    pairs = {(item.statement_index, item.candidate_index) for item in items}
    return SourceCandidateAlignment(version=SOURCE_CANDIDATE_ALIGNMENT_VERSION, items=list(items),
        proofs=[proof for proof in alignment.proofs
                if (proof.statement_index, proof.candidate_index) in pairs])


def reusable_proven_alignment_items(batch, interpretation, coverage, wire, alignment,
                                   *, require_positive=True):
    """Reuse only unique, response-bound decisions for unchanged full inputs."""

    if alignment is None or alignment.version != SOURCE_CANDIDATE_ALIGNMENT_VERSION:
        return []
    kept: list[SourceCandidateAlignmentItem] = []
    for item in alignment.items:
        if require_positive and item.decision != "fully_expressed":
            continue
        pair = item.statement_index, item.candidate_index
        if sum((entry.statement_index, entry.candidate_index) == pair
               for entry in alignment.items) != 1:
            continue
        proofs = [proof for proof in alignment.proofs
                  if (proof.statement_index, proof.candidate_index) == pair]
        if len(proofs) != 1:
            continue
        proof = proofs[0]
        single = SourceCandidateAlignment(
            version=SOURCE_CANDIDATE_ALIGNMENT_VERSION, items=[item],
        )
        try:
            validate_candidate_alignment(batch, interpretation, coverage, wire, single)
            if _alignment_input_identity(batch, interpretation, wire, item) != (
                    proof.source_sha256, proof.candidate_sha256):
                continue
            if hashlib.sha256(proof.response_text.encode("utf-8")).hexdigest() != proof.response_sha256:
                continue
            response = SourceCandidateAlignment.model_validate_json(proof.response_text)
            matches = [entry for entry in response.items
                       if (entry.statement_index, entry.candidate_index) == pair]
            response_pairs = [(entry.statement_index, entry.candidate_index) for entry in response.items]
            if (response.proofs or response.version != SOURCE_CANDIDATE_ALIGNMENT_VERSION
                    or len(response_pairs) != len(set(response_pairs))
                    or len(matches) != 1 or matches[0] != item):
                continue
        except (SourceCandidateAlignmentValidationError, ValueError, TypeError, KeyError,
                IndexError, StopIteration):
            continue
        kept.append(item)
    return kept


def _validate_evidence_policy_checks(candidate, item) -> None:
    """Validate reviewed dimensions and provenance, not infer their meaning."""
    expected = {}
    for index, evidence in enumerate(candidate.minimum_evidence):
        if not has_explicit_evidence_policy(evidence):
            continue
        policy = evidence.source_policy
        if policy is None:
            raise ValueError("资料要求缺少明确来源政策")
        expected[index, "contemporaneous_objective_source"] = policy.requires_contemporaneous_objective_source
        expected[index, "screening_record_transcription"] = policy.allows_screening_record_transcription
        expected[index, "result_validity"] = (policy.result_validity_status, policy.result_validity_constraint)
        if evidence.required_source_types:
            expected[index, "required_source_types"] = frozenset(evidence.required_source_types)
    seen = set()
    for check in item.evidence_policy_checks:
        key = check.evidence_index, check.dimension
        if key in seen or key not in expected:
            policy = (candidate.minimum_evidence[check.evidence_index].source_policy
                      if check.evidence_index < len(candidate.minimum_evidence) else None)
            raise EvidencePolicyCheckError(
                "资料要求核对重复、越界或不属于本次明确声明", item=item,
                evidence_index=check.evidence_index, dimension=check.dimension,
                reason="duplicate" if key in seen else "out_of_scope", policy=policy,
            )
        seen.add(key)
        policy = candidate.minimum_evidence[check.evidence_index].source_policy
        if not any(span == check.source_span_id and check.source_excerpt.strip() in excerpt
                   for span, excerpt in zip(policy.source_span_ids, policy.source_excerpts, strict=True)):
            raise EvidencePolicyCheckError(
                "资料要求核对摘录不属于该维度引用的政策来源", item=item,
                evidence_index=check.evidence_index, dimension=check.dimension,
                reason="source_mismatch", policy=policy,
            )
        value = (frozenset(check.source_types) if check.dimension == "required_source_types" else
                 (check.validity_status, check.validity_constraint) if check.dimension == "result_validity" else
                 check.boolean_value)
        if item.decision == "fully_expressed" and value != expected[key]:
            raise EvidencePolicyCheckError(
                "资料要求核对与草稿声明不一致，不能作为完整表达证明", item=item,
                evidence_index=check.evidence_index, dimension=check.dimension,
                reason="value_mismatch", policy=policy,
            )
    if item.decision == "fully_expressed" and seen != set(expected):
        index, dimension = sorted(set(expected) - seen)[0]
        raise EvidencePolicyCheckError(
            "资料要求核对遗漏明确声明的维度", item=item,
            evidence_index=index, dimension=dimension, reason="missing_dimension",
            policy=candidate.minimum_evidence[index].source_policy,
        )


def validate_candidate_alignment(batch, interpretation, coverage, wire, alignment) -> None:
    """Check identity and literal support; the model remains responsible for semantics."""
    from app.agents.protocol_control_source_interpretation import (
        normalize_source_excerpt,
        simple_visit_action_preserves_time,
        native_schedule_visit_scope_is_preserved,
        native_schedule_action_cell_is_preserved,
        shared_prohibition_preserves_source,
    )

    if alignment.version != SOURCE_CANDIDATE_ALIGNMENT_VERSION:
        raise ValueError("候选语义核对版本不一致")
    by_statement = {entry.statement_index: entry for entry in coverage}
    candidates = (wire.candidate_drafts if hasattr(wire, "candidate_drafts")
                  else wire.candidates)
    seen = set()
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    for item in alignment.items:
        key = item.statement_index, item.candidate_index
        if key in seen or item.statement_index >= len(interpretation.statements) or item.candidate_index >= len(candidates):
            raise ValueError("候选语义核对身份重复或越出冻结范围")
        seen.add(key)
        statement = interpretation.statements[item.statement_index]
        selected = candidates[item.candidate_index]
        candidate = selected.semantics if hasattr(selected, "semantics") else selected
        if candidate is None:
            raise ValueError("候选语义核对缺少已水合候选")
        _validate_evidence_policy_checks(candidate, item)
        entry = by_statement.get(item.statement_index)
        if (entry is None or entry.structure_unit_id != statement.structure_unit_id
                or entry.status not in {"candidate_linked", "semantically_aligned", "expressed"}
                or (entry.status == "expressed" and item.candidate_index not in entry.candidate_indexes)
                or item.candidate_index not in entry.action_candidate_indexes
                or statement.structure_unit_id not in candidate.source_structure_unit_ids
                or normalize_source_excerpt(item.source_excerpt) != normalize_source_excerpt(statement.quoted_text)):
            raise ValueError("候选语义核对未绑定本条原文与已有动作候选")
        unit = units[statement.structure_unit_id]
        if item.decision == "fully_expressed" and statement.unresolved and unit.table_context is not None:
            raise ValueError("表格来源仍有未核清范围，动作文字对应不能代替来源核对")
        native_visit_scope = native_schedule_visit_scope_is_preserved(batch, statement, candidate)
        validate_scope_citations(
            candidate.review_node_bindings,
            [units[unit_id] for unit_id in candidate.source_structure_unit_ids],
            [*batch.owned_units, *batch.context_units],
        )
        if (item.decision == "fully_expressed" and statement.scope_quote
                and not native_visit_scope):
            expected_scope = resolve_ancestor_scope_citation(
                unit, statement.scope_quote, [*batch.owned_units, *batch.context_units],
            )
            if expected_scope is not None and not any(
                node.scope_citation == expected_scope for node in candidate.review_node_bindings
            ):
                raise ValueError("候选审核时期缺少对应原文标题的物理来源")
        obligation_atoms = [atom for group in candidate.obligation_expression.groups
                            for atom in group.atoms]
        source = normalize_source_excerpt(statement.quoted_text)
        scope = normalize_source_excerpt(statement.scope_quote or "")
        grounded_atoms = _statement_grounded_atoms(unit, statement, candidate)
        supported_quotes = {
            normalize_source_excerpt(value) for atom in grounded_atoms
            for value in (atom.statement, getattr(getattr(atom, "evaluation", None), "proposition", None))
            if isinstance(value, str)
        }
        selected_atoms = [atom for atom in grounded_atoms if any(
            normalize_source_excerpt(quote) in {
                normalize_source_excerpt(value) for value in (
                    getattr(atom, "statement", None),
                    getattr(getattr(atom, "evaluation", None), "proposition", None),
                ) if isinstance(value, str)
            } for quote in item.candidate_atom_quotes
        )]
        if any(not normalize_source_excerpt(quote)
               or normalize_source_excerpt(quote) not in supported_quotes
               for quote in item.candidate_atom_quotes):
            raise ValueError("候选语义核对引用了未由本条来源支持的候选原句")
        if item.decision == "fully_expressed":
            if not any(atom in obligation_atoms for atom in selected_atoms):
                raise ValueError("候选未引用承担本条要求的义务原子")
            independent_groups = _independent_source_obligation_groups(
                unit, statement, interpretation, coverage, candidate, item.candidate_index,
                selected_atoms,
            )
            relevant_groups = [group for group in candidate.obligation_expression.groups
                               if group not in independent_groups]
            if any(not any(atom in selected_atoms for atom in group.atoms)
                   for group in relevant_groups):
                raise ValueError("候选存在未覆盖本条要求的另一义务分支")
            obligation_selected = [atom for atom in selected_atoms if atom in obligation_atoms]
            for group in relevant_groups:
                group_selected = [atom for atom in group.atoms if atom in obligation_selected]
                action_cell_preserved = native_visit_scope and native_schedule_action_cell_is_preserved(
                    batch, statement, unit, group_selected,
                )
                if action_cell_preserved or (native_visit_scope and any(
                    normalize_source_excerpt(atom.statement) == source for atom in group_selected
                )) or any(source in normalize_source_excerpt(quote)
                          for atom in group_selected for quote in atom.source_excerpts):
                    continue
                if (not _split_obligations_cover_source(source, scope, group_selected)
                        and not _conditioned_obligations_cover_source(
                            source, scope, candidate, group, group_selected, selected_atoms)):
                    raise ValueError("候选义务摘录未按原文保留完整合取内容")
            functions = set(statement.decision_functions)
            if (functions & {"definition", "calculation_input", "unclassified"}
                    or ("exception" in functions and "action" not in functions)):
                raise ValueError("定义、计算输入或例外不能仅凭候选文字核对宣布完整")
            if "exception" in functions and (not statement.exception_words
                                              or candidate.exception_expression is not None):
                raise ValueError("未明例外或独立例外层不能仅凭动作文字对应宣布完整")
            if statement.force == "prohibited" and not any(
                str(getattr(getattr(atom, "kind", None), "value", getattr(atom, "kind", None)))
                .startswith("prohibit_")
                for atom in selected_atoms
            ):
                raise ValueError("禁止性原文缺少对应禁止义务")
            if candidate.exception_expression is not None and not statement.exception_words:
                raise ValueError("候选携带原文未说明的例外")
            rendered = " ".join(
                normalize_source_excerpt(value) for atom in selected_atoms
                for value in (getattr(atom, "statement", None),
                              getattr(getattr(atom, "evaluation", None), "proposition", None))
                if isinstance(value, str)
            )
            numbers = set(_NUMBER.findall(source))
            directions = {direction for pattern, direction in _COMPARISON_WORDS
                          if re.search(pattern, source)}
            predicates = [atom.evaluation.predicate for atom in selected_atoms
                          if getattr(atom, "evaluation", None) is not None
                          and atom.evaluation.predicate is not None]
            if (source_declares_uncompared_action_count(statement) and len(obligation_selected) == 1
                    and obligation_selected[0].evaluation is not None
                    and obligation_selected[0].evaluation.repeat_scheme is None and not predicates):
                raise CandidateNumericAlignmentError(item=item, candidate=candidate, atoms=obligation_selected,
                    source_refs=unit.source_span_ids, repeat_scheme_only=True)
            if len(numbers) == 1 and len(directions) == 1 and not predicates:
                raise CandidateNumericAlignmentError(
                    item=item, candidate=candidate, atoms=obligation_selected,
                    source_refs=unit.source_span_ids,
                )
            shared_prohibition_time = any(
                shared_prohibition_preserves_source(statement, atom) for atom in obligation_selected
            )
            common_trigger_time = _common_trigger_preserves_visit_time(
                batch, statement, candidate, selected_atoms)
            if statement.exception_words and normalize_source_excerpt(statement.exception_words) not in rendered:
                raise ValueError("候选未逐项保留来源时点或例外")
            for word in statement.time_words:
                normalized_word = normalize_source_excerpt(word)
                if normalized_word in rendered:
                    continue
                if shared_prohibition_time:
                    continue
                if (normalized_word in scope
                        and simple_visit_action_preserves_time(batch, statement, candidate)):
                    continue
                if (normalized_word not in scope or _NUMBER.search(normalized_word)
                        or not _matches_time_anchor_direction(normalized_word, selected_atoms, source=source)):
                    raise ValueError("候选未逐项保留来源时点或例外")
            if "time_validity" in functions and not shared_prohibition_time and not common_trigger_time and not simple_visit_action_preserves_time(
                batch, statement, candidate
            ):
                for word in statement.time_words:
                    if not _matches_time_anchor_direction(word, selected_atoms, source=source):
                        raise ValueError("候选时间锚点或方向未由原文逐项证明")
            if "threshold" in functions and not numbers:
                source_modes = {mode for mode, words in _QUANTIFIER_GROUPS.items()
                                if any(word in source for word in words)}
                statements = [normalize_source_excerpt(atom.statement)
                              for atom in selected_atoms]
                propositions = [normalize_source_excerpt(atom.evaluation.proposition)
                                for atom in selected_atoms
                                if getattr(atom, "evaluation", None) is not None]
                statement_modes = {mode for mode, words in _QUANTIFIER_GROUPS.items()
                                   if any(word in value for value in statements for word in words)}
                proposition_modes = {mode for mode, words in _QUANTIFIER_GROUPS.items()
                                     if any(word in value for value in propositions for word in words)}
                if (len(source_modes) != 1 or statement_modes != source_modes
                        or (proposition_modes and not source_modes <= proposition_modes)):
                    raise ValueError("候选数量范围未在对应原句中保留")
            repeat_count_preserved = source_declares_uncompared_action_count(statement) and (
                _source_repeat_count_is_preserved(
                    unit, statement, source, numbers, directions, predicates, obligation_selected,
                )
            )
            if numbers and not repeat_count_preserved and not (native_visit_scope and source in rendered
                                and "threshold" not in functions and not directions):
                if len(numbers) != 1 or len(directions) != 1 or not predicates:
                    raise ValueError("数值原文不能由模糊比较条件宣布完整")
                conditioned_consequences = []
                for group in relevant_groups:
                    group_selected = [atom for atom in group.atoms if atom in obligation_selected]
                    if not _conditioned_obligations_cover_source(
                            source, scope, candidate, group, group_selected, selected_atoms):
                        conditioned_consequences = []
                        break
                    fragments = [_source_fragment(source, scope, normalize_source_excerpt(quote))
                                 for atom in group_selected for quote in atom.source_excerpts]
                    offset = min(source.index(fragment) for fragment in fragments if fragment is not None)
                    conditioned_consequences.append(source[offset:].strip("，,。；;：: "))
                for predicate in predicates:
                    clauses = [normalize_source_excerpt(value)
                               for value in predicate.exact_source_clauses]
                    # Only a proved common trigger may be omitted; retain the entire consequence.
                    comparison_source_preserved = any(source in clause or (
                        conditioned_consequences and clause in source
                        and all(consequence in clause for consequence in conditioned_consequences)
                    ) for clause in clauses)
                    if (predicate.comparator.value not in directions
                            or str(predicate.value) not in numbers
                            or not comparison_source_preserved
                            or (predicate.unit and normalize_source_excerpt(predicate.unit) not in source)):
                        raise ValueError("候选比较方向、数值或单位与原文不一致")
