"""Bounded source-to-candidate comparison for split protocol statements."""

from __future__ import annotations

import json
import hashlib
import re
from typing import Literal

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel


SOURCE_CANDIDATE_ALIGNMENT_VERSION = "phase5/control-source-candidate-alignment/v8"


class SourceCandidateAlignmentValidationError(ValueError):
    pass

_COMPARISON_WORDS = (
    (r"(?:≥|>=|大于等于|不小于|至少|不少于|不低于|以上)", "gte"),
    (r"(?:≤|<=|小于等于|不大于|不多于|至多|不超过|不高于|以下)", "lte"),
    (r"(?:>(?!=)|(?<!不)大于(?!等于)|(?<!不)超过|(?<!不)高于)", "gt"),
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


def _matches_time_anchor_direction(word: str, atoms) -> bool:
    anchors = {anchor for label, anchor in _ANCHOR_WORDS if label in word}
    directions = ({"before"} if "前" in word and "后" not in word else
                  {"after"} if "后" in word and "前" not in word else
                  {"on"} if "进入" in word else set())
    return len(anchors) == 1 and len(directions) == 1 and any(
        constraint.anchor_type.value in anchors and constraint.direction.value in directions
        for atom in atoms
        if (constraint := getattr(atom, "time_constraint", None)) is not None
    )


class SourceCandidateAlignmentItem(ContractModel):
    statement_index: int = Field(ge=0)
    candidate_index: int = Field(ge=0)
    decision: Literal["fully_expressed", "incomplete", "uncertain"]
    source_excerpt: str = Field(min_length=1)
    candidate_atom_quotes: list[str] = Field(default_factory=list)
    unresolved_dimensions: list[str] = Field(default_factory=list)

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
            "name": "protocol_control_candidate_alignment_v8",
            "strict": True,
            "schema": schema,
        },
    }


def build_candidate_alignment_prompt(batch, interpretation, wire, pairs) -> str:
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    selected = []
    for statement_index, candidate_index in pairs:
        statement = interpretation.statements[statement_index]
        candidate = wire.candidate_drafts[candidate_index]
        selected.append({
            "statement_index": statement_index,
            "candidate_index": candidate_index,
            "required_source_excerpt": statement.quoted_text,
            "source_statement": statement.model_dump(mode="json"),
            "source_unit": units[statement.structure_unit_id].excerpt,
            "allowed_candidate_atom_quotes": [
                atom.statement
                for expression in (candidate.applicability_expression,
                                   candidate.trigger_expression,
                                   candidate.obligation_expression,
                                   candidate.exception_expression)
                if expression is not None
                for group in expression.groups for atom in group.atoms
            ],
            "candidate": candidate.model_dump(mode="json"),
        })
    return (
        "你只核同一冻结方案原文与已有候选的语义对应，不新增条款，不判断受试者。"
        "此前的核对仅说明官方条款和访视目录未完整覆盖本句，不能据此断言本候选也未覆盖。"
        "逐项判断候选中已经写出的条件、对象、全称/数量、时间、否定、后果、例外和证据政策，"
        "是否共同且仅共同表达本句原文。多原子合取可以表达一句话。"
        "仅当本句的‘任一项’等回指在同一冻结来源单元中有唯一明确的先行要求时，"
        "可引用该要求解释所指对象；不得借标题、其他来源单元或不明确的邻句新增条件。"
        "只有上述所有适用维度与原文一致，才选 fully_expressed；有确定差额选 incomplete，"
        "无法从冻结原文与候选判清选 uncertain。不得因为候选引用了同一来源或看起来临床合理就选完整。"
        "source_excerpt 必须逐字复制 required_source_excerpt，不得从 source_unit 补入前后文字；"
        "candidate_atom_quotes 只能从 allowed_candidate_atom_quotes 原样选完整句，不得改写、补词或只摘短词。"
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
                           "source_unit": unit.model_dump(mode="json")}),
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
            if response.proofs or len(matches) != 1 or matches[0] != item:
                continue
        except (SourceCandidateAlignmentValidationError, ValueError, TypeError, KeyError,
                IndexError, StopIteration):
            continue
        kept.append(item)
    return kept


def validate_candidate_alignment(batch, interpretation, coverage, wire, alignment) -> None:
    """Check identity and literal support; the model remains responsible for semantics."""
    from app.agents.protocol_control_source_interpretation import (
        normalize_source_excerpt,
        simple_visit_action_preserves_time,
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
        entry = by_statement.get(item.statement_index)
        if (entry is None or entry.structure_unit_id != statement.structure_unit_id
                or entry.status not in {"candidate_linked", "semantically_aligned"}
                or item.candidate_index not in entry.action_candidate_indexes
                or statement.structure_unit_id not in candidate.source_structure_unit_ids
                or normalize_source_excerpt(item.source_excerpt) != normalize_source_excerpt(statement.quoted_text)):
            raise ValueError("候选语义核对未绑定本条原文与已有动作候选")
        unit = units[statement.structure_unit_id]
        atoms = [atom for expression in (
            candidate.applicability_expression, candidate.trigger_expression,
            candidate.obligation_expression, candidate.exception_expression,
        ) if expression is not None for group in expression.groups for atom in group.atoms]
        obligation_atoms = [atom for group in candidate.obligation_expression.groups
                            for atom in group.atoms]
        source = normalize_source_excerpt(statement.quoted_text)
        scope = normalize_source_excerpt(statement.scope_quote or "")
        grounded_atoms = [atom for atom in atoms if (
            set(atom.source_span_ids) & set(unit.source_span_ids)
            and atom.source_excerpts
            and all(normalize_source_excerpt(quote) in normalize_source_excerpt(unit.excerpt)
                    for quote in atom.source_excerpts)
            and any(_source_fragment(source, scope, normalize_source_excerpt(quote)) is not None
                    or source in normalize_source_excerpt(quote)
                    for quote in atom.source_excerpts)
        )]
        selected_atoms = [atom for atom in grounded_atoms if any(
            normalize_source_excerpt(quote) in {
                normalize_source_excerpt(value) for value in (
                    getattr(atom, "statement", None),
                    getattr(getattr(atom, "evaluation", None), "proposition", None),
                ) if isinstance(value, str)
            } for quote in item.candidate_atom_quotes
        )]
        if (len(selected_atoms) < len(set(item.candidate_atom_quotes))
                or any(not normalize_source_excerpt(quote) for quote in item.candidate_atom_quotes)):
            raise ValueError("候选语义核对引用了未由本条来源支持的候选原句")
        if item.decision == "fully_expressed":
            if not any(atom in obligation_atoms for atom in selected_atoms):
                raise ValueError("候选未引用承担本条要求的义务原子")
            if any(not any(atom in selected_atoms for atom in group.atoms)
                   for group in candidate.obligation_expression.groups):
                raise ValueError("候选存在未覆盖本条要求的另一义务分支")
            obligation_selected = [atom for atom in selected_atoms if atom in obligation_atoms]
            if not any(source in normalize_source_excerpt(quote)
                       for atom in obligation_selected for quote in atom.source_excerpts):
                if not any(_split_obligations_cover_source(source, scope, group.atoms)
                           for group in candidate.obligation_expression.groups
                           if all(atom in obligation_selected for atom in group.atoms)):
                    raise ValueError("候选义务摘录未按原文保留完整合取内容")
            functions = set(statement.decision_functions)
            if functions & {"definition", "calculation_input", "exception", "unclassified"}:
                raise ValueError("定义、计算输入或例外不能仅凭候选文字核对宣布完整")
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
            if statement.exception_words and normalize_source_excerpt(statement.exception_words) not in rendered:
                raise ValueError("候选未逐项保留来源时点或例外")
            for word in statement.time_words:
                normalized_word = normalize_source_excerpt(word)
                if normalized_word in rendered:
                    continue
                if (normalized_word not in scope or _NUMBER.search(normalized_word)
                        or not _matches_time_anchor_direction(normalized_word, selected_atoms)):
                    raise ValueError("候选未逐项保留来源时点或例外")
            if "time_validity" in functions and not simple_visit_action_preserves_time(
                batch, statement, candidate
            ):
                for word in statement.time_words:
                    if not _matches_time_anchor_direction(word, selected_atoms):
                        raise ValueError("候选时间锚点或方向未由原文逐项证明")
            numbers = set(_NUMBER.findall(source))
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
            if numbers:
                directions = {direction for pattern, direction in _COMPARISON_WORDS
                              if re.search(pattern, source)}
                predicates = [atom.evaluation.predicate for atom in selected_atoms
                              if getattr(atom, "evaluation", None) is not None
                              and atom.evaluation.predicate is not None]
                if len(numbers) != 1 or len(directions) != 1 or not predicates:
                    raise ValueError("数值原文不能由模糊比较条件宣布完整")
                for predicate in predicates:
                    clauses = [normalize_source_excerpt(value)
                               for value in predicate.exact_source_clauses]
                    if (predicate.comparator.value not in directions
                            or str(predicate.value) not in numbers
                            or not any(source in clause for clause in clauses)
                            or (predicate.unit and normalize_source_excerpt(predicate.unit) not in source)):
                        raise ValueError("候选比较方向、数值或单位与原文不一致")
