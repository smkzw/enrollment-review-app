"""Retain verified source dispositions and isolate unexecutable statements."""

from __future__ import annotations

import hashlib
import json

from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentRunResult,
    hydrate_protocol_control_agent_output,
    source_statement_coverage,
    validate_protocol_control_agent_wire,
)
from app.agents.protocol_control_candidate_alignment import (
    reusable_proven_alignment_items,
    validate_candidate_alignment,
)
from app.agents.protocol_control_source_interpretation import (
    SourceInterpretation,
    SourceStatementCoverage,
    SourceDefinitionConsumers,
    SOURCE_DEFINITION_CONSUMER_VERSION,
    validate_source_definition_consumers,
    validate_restricted_definition_consumers,
    validate_source_interpretation,
    validate_source_target_review,
)
from app.domain.contracts.protocol_controls import (
    ProtocolControlBatchDispositionHydrated,
    ProtocolControlCandidate,
    ProtocolControlDispositionBatch,
    ProtocolControlUnitDisposition,
    RestrictedProtocolControlStatement,
    RestrictedStatementIndependentExcerpt,
    RestrictedStatementScopeProof,
    StructureUnitDispositionKind,
)
from app.protocols.protocol_control_gate import (
    candidate_cites_unit_quote,
    check_protocol_control_batch_candidates,
    locate_source_quote_offsets,
    source_statement_context_is_self_contained,
    source_statement_is_standalone_action,
    source_statement_ranges_cover_unit,
)
from app.protocols.source_time_fragments import intraday_time_fragments
from app.agents.protocol_control_stage_compiler import requires_temporal_resolution


TEMPORAL_RESTRICTION_VERSION = "source-temporal-restricted-disposition/v2"
WHOLE_UNIT_RESTRICTION_VERSION = "source-whole-unit-restricted-disposition/v2"
# Procedure retention changes the current gate, not previously compiled rules.
PROCEDURE_RESTRICTION_VALIDATION_VERSION = "procedure-source-restricted-retention/v3"
RESTRICTED_DEFINITION_VALIDATION_VERSION = "restricted-definition-registration-validation/v1"
PROCEDURE_SOURCE_CONTEXT_VERSION = "procedure-source-context-completeness/v3"
CITATION_CLOSURE_RESTRICTION_VALIDATION_VERSION = "source-citation-restricted-retention/v1"


def _coverage_matches_current_proofs(batch, result) -> bool:
    """Failure checkpoints use draft indexes; only verified pairs can change status."""
    raw = source_statement_coverage(batch, result.source_interpretation, result.partial_wire)
    alignment = result.source_candidate_alignment
    if alignment is None:
        return result.source_statement_coverage == raw
    try:
        validate_candidate_alignment(batch, result.source_interpretation, raw, result.partial_wire, alignment)
        proven = reusable_proven_alignment_items(
            batch, result.source_interpretation, raw, result.partial_wire, alignment,
        )
    except (ValueError, TypeError, KeyError, IndexError, StopIteration):
        return False
    if len(proven) != sum(item.decision == "fully_expressed" for item in alignment.items):
        return False
    accepted = {}
    for item in proven:
        accepted.setdefault(item.statement_index, item.candidate_index)
    expected = [entry.model_copy(update={"status": "semantically_aligned",
        "candidate_indexes": [accepted[entry.statement_index]]})
        if entry.statement_index in accepted else entry for entry in raw]
    return result.source_statement_coverage == expected


def _citation_restricted_units(units, candidates, seed):
    """Restrict every citation-connected candidate, never infer medical dependency."""
    restricted = set(seed)
    owned_spans = {span for unit in units.values() for span in unit.source_span_ids}
    while True:
        spans = {span for unit_id in restricted for span in units[unit_id].source_span_ids}
        expanded = set(restricted)
        for candidate in candidates:
            cited = set(candidate.frozen_structure_unit_ids)
            if cited & restricted or set(candidate.source_span_ids) & spans:
                if not cited <= set(units) or not set(candidate.source_span_ids) <= owned_spans:
                    return None
                expanded.update(cited)
                expanded.update(unit_id for unit_id, unit in units.items()
                    if set(unit.source_span_ids) & set(candidate.source_span_ids))
        if expanded == restricted:
            return restricted
        restricted = expanded


def _unit_statements_cover_source(unit, interpretation, indexes) -> bool:
    ranges = [locate_source_quote_offsets(unit.excerpt, interpretation.statements[index].quoted_text)
              for index in indexes]
    if any(bounds is None for bounds in ranges):
        return False
    ordered = sorted(ranges)
    if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
        return False
    scopes = [locate_source_quote_offsets(unit.excerpt, interpretation.statements[index].scope_quote)
              for index in indexes if interpretation.statements[index].scope_quote is not None
              and interpretation.statements[index].scope_context_unit_id is None]
    if any(bounds is None for bounds in scopes):
        return False
    extra = []
    for bounds in sorted(set(scopes)):
        if any(start <= bounds[0] and bounds[1] <= end for start, end in ranges):
            continue
        if any(start < bounds[1] and bounds[0] < end for start, end in ranges):
            return False
        extra.append(bounds)
    return source_statement_ranges_cover_unit(
        unit.excerpt, [*ranges, *extra], allow_joining_punctuation=True,
    )


def procedure_correspondence_source_gaps(batch, interpretation, wire, review) -> list[str]:
    """Locate missing source context, not a guessed qualifier or a clinical gap.

    Callers must first verify the actual saved source and review receipts. A
    failed procedure mapping cannot reuse an incomplete source seed to claim
    whole-unit restriction; it needs a new, bounded source read instead.
    """
    dispositions = {item.structure_unit_id: item for item in wire.dispositions}
    affected = {interpretation.statements[item.statement_index].structure_unit_id
                for item in review.items if item.decision == "unresolved"}
    return sorted(unit.structure_unit_id for unit in batch.owned_units
                  if unit.structure_unit_id in affected
                  and dispositions[unit.structure_unit_id].disposition
                  == StructureUnitDispositionKind.REQUIRED_PROCEDURE
                  and not _unit_statements_cover_source(unit, interpretation, [
                      index for index, statement in enumerate(interpretation.statements)
                      if statement.structure_unit_id == unit.structure_unit_id
                  ]))


def procedure_correspondence_scope_indexes(batch, interpretation, wire, review) -> tuple[int, ...] | None:
    """Select context-only recovery, without supplying the missing meaning.

    The existing scope contract cannot add actions or amend exceptions. A
    missing tail or a multi-statement unit needs a different source recovery.
    """
    gaps = set(procedure_correspondence_source_gaps(batch, interpretation, wire, review))
    indexes = []
    for unit in batch.owned_units:
        if unit.structure_unit_id not in gaps:
            continue
        statements = [(index, statement) for index, statement in enumerate(interpretation.statements)
                      if statement.structure_unit_id == unit.structure_unit_id]
        if len(statements) != 1:
            return None
        index, statement = statements[0]
        bounds = locate_source_quote_offsets(unit.excerpt, statement.quoted_text)
        if (bounds is None or bounds[0] == 0
                or not source_statement_ranges_cover_unit(
                    unit.excerpt, [(0, bounds[1])], allow_joining_punctuation=True,
                )):
            return None
        indexes.append(index)
    return tuple(sorted(indexes))


def _temporal_restriction_indexes(
    batch: ProtocolControlDispositionBatch,
    result: ProtocolControlAgentRunResult,
    *,
    whole_unit: bool = False,
) -> set[int] | None:
    """Prove the typed compiler failure range; no inference from error prose."""

    attempt = result.attempts[-1]
    detail = attempt.error_detail
    interpretation = result.source_interpretation
    review = result.source_target_review
    if (set(attempt.error_classes) != {"TEMPORAL_SCOPE_UNRESOLVED"}
            or not isinstance(detail, dict) or interpretation is None or review is None
            or detail.get("code") != "TEMPORAL_SCOPE_UNRESOLVED"
            or detail.get("json_path") != "/items"
            or detail.get("retry_class") != "temporal_scope_review"):
        return None
    ids = detail.get("statement_ids")
    if (not isinstance(ids, list) or not ids
            or any(type(index) is not int or index < 0
                   or index >= len(interpretation.statements) for index in ids)
            or ids != sorted(set(ids))
            or detail.get("affected_dependents") != ids):
        return None
    indexes = set(ids)
    additional = {item.statement_index for item in review.items
                  if item.decision == "additional_requirement"}
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    temporal_units = {interpretation.statements[index].structure_unit_id for index in indexes}
    # A typed unsupported clock can restrict its whole procedure unit, not an
    # unrelated additional requirement. Literal whole-unit coverage is checked
    # by the caller before any disposition can be saved.
    related_additional = whole_unit and indexes <= additional and all(
        interpretation.statements[index].structure_unit_id in temporal_units
        and "action" in interpretation.statements[index].decision_functions
        and not set(interpretation.statements[index].decision_functions)
        & {"definition", "calculation_input"}
        and not interpretation.statements[index].unresolved
        for index in additional - indexes
    )
    spans = sorted({span for index in ids
                    for span in units[interpretation.statements[index].structure_unit_id].source_span_ids})
    if ((additional != indexes and not related_additional) or detail.get("source_refs") != spans
            or (not whole_unit and any(item.decision not in {
                "covered_by_official", "covered_by_procedure", "additional_requirement",
            } for item in review.items))):
        return None
    for index in ids:
        statement = interpretation.statements[index]
        recommendation_in_required_unit = (
            whole_unit and statement.force == "recommended" and result.partial_wire is not None
            and any(item.structure_unit_id == statement.structure_unit_id
                    and item.disposition == StructureUnitDispositionKind.REQUIRED_PROCEDURE
                    for item in result.partial_wire.dispositions)
            and any(other != index
                    and interpretation.statements[other].structure_unit_id == statement.structure_unit_id
                    and interpretation.statements[other].force in {"required", "prohibited"}
                    and "action" in interpretation.statements[other].decision_functions
                    for other in additional)
        )
        source_action = ("action" in statement.decision_functions
                         and "definition" not in statement.decision_functions
                         and (statement.force in {"required", "prohibited"}
                              or recommendation_in_required_unit))
        if (statement.unresolved
                or not (source_action if whole_unit else source_statement_is_standalone_action(statement))
                or (not whole_unit and not source_statement_context_is_self_contained(statement))
                or not requires_temporal_resolution(interpretation, index)):
            return None
    return indexes


def _restricted_capability_batch(
    batch: ProtocolControlDispositionBatch,
    result: ProtocolControlAgentRunResult,
) -> ProtocolControlBatchDispositionHydrated | None:
    """Retain whole frozen units for a proven unsupported clock consumer.

    This is deliberately not a fallback for invalid Schema or source semantics.
    Only disjoint, single-statement units may be isolated; the remaining real
    candidates must pass the unchanged gate and literal coverage checks.
    """
    wire = result.capability_wire
    interpretation = result.source_interpretation
    attempt = result.attempts[-1]
    if (wire is None or interpretation is None or result.final_output is not None
            or result.status != "需要核对" or attempt.outcome != "publication_invalid"
            or "TIME_PRECISION_UNSUPPORTED" not in attempt.error_classes
            or set(attempt.error_classes) - {"TIME_PRECISION_UNSUPPORTED", "PUBLICATION_GATE_REJECTED"}
            or result.source_definition_consumers is not None
            or any(item.unresolved or "calculation_input" in item.decision_functions
                   for item in interpretation.statements)):
        return None
    validate_source_interpretation(batch, interpretation)
    wire = validate_protocol_control_agent_wire(wire, batch)
    original = hydrate_protocol_control_agent_output(wire, batch)
    issues = check_protocol_control_batch_candidates(batch, original)
    if not issues or any(issue.code != "TIME_PRECISION_UNSUPPORTED" for issue in issues):
        return None
    failed = {
        candidate.control_candidate_id
        for candidate in original.candidates
        if any(issue.entity_id is not None
               and issue.entity_id.startswith(candidate.control_candidate_id + "/")
               and set(issue.obligation_source_span_ids) <= set(candidate.source_span_ids)
               for issue in issues)
    }
    if len(failed) != len(issues):
        return None
    restricted_units = {
        unit_id for candidate in original.candidates
        if candidate.control_candidate_id in failed
        for unit_id in candidate.frozen_structure_unit_ids
    }
    # A failed candidate spanning several source units cannot establish which
    # independent requirements are safe to keep executable.
    if any(len(candidate.frozen_structure_unit_ids) != 1
           for candidate in original.candidates if candidate.control_candidate_id in failed):
        return None
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    restricted_spans = {span for unit_id in restricted_units for span in units[unit_id].source_span_ids}
    retained = [candidate for candidate in original.candidates
                if candidate.control_candidate_id not in failed]
    if any(set(candidate.frozen_structure_unit_ids) & restricted_units
           or set(candidate.source_span_ids) & restricted_spans for candidate in retained):
        return None
    coverage = source_statement_coverage(batch, interpretation, wire)
    dispositions = {item.structure_unit_id: item for item in original.dispositions}
    by_unit: dict[str, list[int]] = {}
    for index, statement in enumerate(interpretation.statements):
        by_unit.setdefault(statement.structure_unit_id, []).append(index)
    restrictions = []
    for unit_id, indexes in by_unit.items():
        if unit_id not in restricted_units:
            if any(coverage[index].status != "expressed" for index in indexes):
                return None
            if dispositions[unit_id].disposition != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE:
                return None
            continue
        if len(indexes) != 1:
            return None
        index = indexes[0]
        statement = interpretation.statements[index]
        unit = units[unit_id]
        if (statement.quoted_text != unit.excerpt or statement.scope_quote is not None
                or not intraday_time_fragments(statement.quoted_text)):
            return None
        digest = hashlib.sha256(json.dumps(
            [batch.batch_id, unit_id, index, "consumer_unavailable"],
            ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()[:24]
        restrictions.append(RestrictedProtocolControlStatement(
            restricted_statement_id=f"restricted:{digest}",
            source_structure_unit_id=unit_id, source_statement_index=index,
            source_quote=unit.excerpt, source_span_ids=sorted(unit.source_span_ids),
            limitation_kind="consumer_unavailable",
            unresolved_dimensions=["当前系统尚不支持原文所需的小时或分钟精度计算"],
            time_words=list(statement.time_words),
            exception_words=statement.exception_words,
            affected_stage=statement.affected_stage,
            decision_functions=list(statement.decision_functions),
            source_force=statement.force,
        ))
    if {item.source_structure_unit_id for item in restrictions} != restricted_units:
        return None
    if any(dispositions[unit_id].disposition not in {
        StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
        StructureUnitDispositionKind.PHASE_EXCLUDED,
        StructureUnitDispositionKind.POST_TREATMENT_EXECUTION,
        StructureUnitDispositionKind.NON_ENROLLMENT_EXECUTION,
    } for unit_id in interpretation.units_without_statement):
        return None
    output = original.model_copy(update={
        "candidates": retained,
        "dispositions": [ProtocolControlUnitDisposition(
            structure_unit_id=item.structure_unit_id,
            disposition=StructureUnitDispositionKind.RESTRICTED_SOURCE,
        ) if item.structure_unit_id in restricted_units else item
            for item in original.dispositions],
        "restricted_statements": sorted(
            restrictions, key=lambda item: (item.source_structure_unit_id, item.source_statement_index),
        ),
    })
    output = ProtocolControlBatchDispositionHydrated.model_validate(output.model_dump(mode="json"))
    return None if check_protocol_control_batch_candidates(batch, output) else output


def _coexisting_statement_proofs(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    coverage: dict[int, SourceStatementCoverage],
    unit_id: str,
    indexes: list[int],
    restricted_indexes: set[int],
    disposition: ProtocolControlUnitDisposition,
    candidates: list[ProtocolControlCandidate],
    *,
    temporal_indexes: frozenset[int] = frozenset(),
) -> dict[int, RestrictedStatementScopeProof] | None:
    """Prove that one frozen unit keeps an executable candidate beside restricted statements.

    Literal, disjoint ranges are necessary, not a semantic-equivalence proof. Shared
    qualifiers outside an action require a separate relationship review; they cannot
    enter this narrow self-contained path. Every independent statement must be
    located in the frozen excerpt and cited verbatim by a candidate bound to the same
    unit, and no candidate may cite a restricted statement. A missing link means the
    unit stays wholly restricted instead of silently keeping the rest of the unit.
    """

    unit = next(
        item for item in batch.owned_units if item.structure_unit_id == unit_id
    )
    if (disposition.disposition != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
            or not candidates):
        return None
    independent_indexes = [index for index in indexes if index not in restricted_indexes]
    if not independent_indexes:
        return None
    ranges = [locate_source_quote_offsets(unit.excerpt, interpretation.statements[index].quoted_text)
              for index in indexes]
    if any(bounds is None for bounds in ranges) or not source_statement_ranges_cover_unit(
        unit.excerpt, [bounds for bounds in ranges if bounds is not None],
    ):
        return None
    independent: list[tuple[int, str, tuple[int, int], list[str]]] = []
    for index in independent_indexes:
        statement = interpretation.statements[index]
        if (statement.unresolved or coverage[index].status != "expressed"
                or not source_statement_context_is_self_contained(statement)
                or not source_statement_is_standalone_action(statement)):
            return None
        offsets = locate_source_quote_offsets(unit.excerpt, statement.quoted_text)
        if offsets is None:
            return None
        citing = sorted(
            candidate.control_candidate_id
            for candidate in candidates
            if candidate_cites_unit_quote(candidate, unit, statement.quoted_text)
        )
        if not citing:
            return None
        independent.append((index, statement.quoted_text, offsets, citing))
    if any(
        candidate_cites_unit_quote(
            candidate, unit, interpretation.statements[index].quoted_text
        )
        for candidate in candidates
        for index in sorted(restricted_indexes)
    ):
        return None
    digest = hashlib.sha256(unit.excerpt.encode("utf-8")).hexdigest()
    proofs: dict[int, RestrictedStatementScopeProof] = {}
    for index in sorted(restricted_indexes):
        statement = interpretation.statements[index]
        if ((not statement.unresolved and index not in temporal_indexes)
                or not source_statement_context_is_self_contained(statement)
                or not source_statement_is_standalone_action(statement)):
            return None
        offsets = locate_source_quote_offsets(unit.excerpt, statement.quoted_text)
        if offsets is None:
            return None
        excerpts = []
        for entry_index, quote, entry_offsets, citing in independent:
            if interpretation.statements[entry_index].scope_context_unit_id is not None:
                # Existing same-unit independence proofs do not prove borrowed
                # label dependencies; retain the whole unit until they do.
                return None
            if entry_offsets[0] < offsets[1] and offsets[0] < entry_offsets[1]:
                return None
            excerpts.append(RestrictedStatementIndependentExcerpt(
                statement_index=entry_index,
                source_quote=quote,
                source_start=entry_offsets[0],
                source_end=entry_offsets[1],
                candidate_control_ids=list(citing),
                scope_quote=interpretation.statements[entry_index].scope_quote,
                time_words=list(interpretation.statements[entry_index].time_words),
                exception_words=interpretation.statements[entry_index].exception_words,
                affected_stage=interpretation.statements[entry_index].affected_stage,
                decision_functions=list(interpretation.statements[entry_index].decision_functions),
                source_force=interpretation.statements[entry_index].force,
            ))
        proofs[index] = RestrictedStatementScopeProof(
            unit_excerpt_sha256=digest,
            restricted_source_start=offsets[0],
            restricted_source_end=offsets[1],
            independent_excerpts=excerpts,
        )
    return proofs


def _whole_unit_restriction(
    batch: ProtocolControlDispositionBatch,
    result: ProtocolControlAgentRunResult,
) -> ProtocolControlBatchDispositionHydrated | None:
    """Retain every source point when independence inside a unit is unproven.

    This is not repair of bad semantics or failed transport. A valid source and
    author output with unresolved target correspondence may become non-executable
    in whole frozen units. Definitions still require the existing local/global
    dependency closure; this function never supplies that closure.
    """
    if (result.partial_wire is None
            or (result.source_definition_consumers is not None
                and not result.restricted_source_definition_consumer_attempts)
            or set(result.attempts[-1].error_classes) not in (
                {"SOURCE_TARGET_REVIEW_UNRESOLVED"}, {"TEMPORAL_SCOPE_UNRESOLVED"},
            )):
        return None
    interpretation = result.source_interpretation
    review = result.source_target_review
    original = hydrate_protocol_control_agent_output(result.partial_wire, batch)
    if (check_protocol_control_batch_candidates(batch, original)
            or not _coverage_matches_current_proofs(batch, result)):
        return None
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    reviewed = {item.statement_index: item for item in review.items}
    uncertain = [item for item in review.items if item.decision == "unresolved"]
    temporal_indexes = set()
    if set(result.attempts[-1].error_classes) == {"TEMPORAL_SCOPE_UNRESOLVED"}:
        proven = _temporal_restriction_indexes(batch, result, whole_unit=True)
        if proven is None:
            return None
        temporal_indexes = proven
    if ((not uncertain and not temporal_indexes)
            or any(not item.unresolved_aspects for item in uncertain)):
        return None
    uncertain_indexes = {item.statement_index for item in uncertain}
    restricted_indexes = uncertain_indexes | temporal_indexes
    restricted_units = {interpretation.statements[index].structure_unit_id
                        for index in restricted_indexes}
    seed_units = set(restricted_units)
    restricted_units = _citation_restricted_units(units, original.candidates, seed_units)
    if restricted_units is None:
        return None
    citation_expanded = restricted_units != seed_units
    by_unit: dict[str, list[int]] = {}
    for index, statement in enumerate(interpretation.statements):
        by_unit.setdefault(statement.structure_unit_id, []).append(index)
    dispositions = {item.structure_unit_id: item for item in original.dispositions}
    procedure_units = {unit_id for unit_id in restricted_units
                       if dispositions[unit_id].disposition
                       == StructureUnitDispositionKind.REQUIRED_PROCEDURE}
    if (not procedure_units and not citation_expanded
            and not any(len(by_unit.get(unit_id, [])) > 1 for unit_id in restricted_units)):
        return None
    if any(unit_id not in by_unit for unit_id in restricted_units):
        return None
    coverage = {item.statement_index: item for item in result.source_statement_coverage}
    for unit_id, indexes in by_unit.items():
        if unit_id in restricted_units:
            if dispositions[unit_id].disposition not in {
                StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                StructureUnitDispositionKind.REQUIRED_PROCEDURE,
            }:
                return None
            # A valid target ID in an unresolved review is a comparison, not
            # coverage. Keep the whole procedure unit non-executable; do not
            # turn a missing correspondence into source ambiguity or approval.
            if unit_id in procedure_units and any(
                index not in reviewed or reviewed[index].decision not in {
                    "unresolved", "covered_by_procedure", "background_context",
                    "definition_dependency", "additional_requirement",
                } or (reviewed[index].decision == "additional_requirement"
                      and not uncertain_indexes.intersection(indexes)
                      and not (len(indexes) > 1 and temporal_indexes.intersection(indexes))) for index in indexes
            ):
                return None
            # This covers context, not independence or semantic equivalence.
            if not _unit_statements_cover_source(units[unit_id], interpretation, indexes):
                return None
            continue
        for index in indexes:
            statement = interpretation.statements[index]
            item = reviewed.get(index)
            if statement.unresolved:
                return None
            if item is None:
                if (coverage[index].status not in {"expressed", "semantically_aligned"}
                        and dispositions[unit_id].disposition not in {
                            StructureUnitDispositionKind.POST_TREATMENT_EXECUTION,
                            StructureUnitDispositionKind.NON_ENROLLMENT_EXECUTION,
                            StructureUnitDispositionKind.PHASE_EXCLUDED,
                            StructureUnitDispositionKind.ADMINISTRATIVE_STATISTICAL_BACKGROUND,
                        }):
                    return None
            elif item.decision == "additional_requirement":
                if coverage[index].status not in {"expressed", "semantically_aligned"}:
                    return None
            elif item.decision not in {
                "covered_by_official", "covered_by_procedure", "definition_dependency",
                "potential_same_requirement", "background_context", "cited_external_rationale",
            }:
                return None
    removed = [candidate for candidate in original.candidates
               if set(candidate.frozen_structure_unit_ids) & restricted_units]
    # A shared candidate cannot be removed without limiting its other source
    # units as well. No guessed dependency expansion is performed here.
    if any(not set(candidate.frozen_structure_unit_ids) <= restricted_units for candidate in removed):
        return None
    retained = [candidate for candidate in original.candidates if candidate not in removed]
    restricted_spans = {span for unit_id in restricted_units for span in units[unit_id].source_span_ids}
    if any(set(candidate.source_span_ids) & restricted_spans for candidate in retained):
        return None
    statements = []
    for unit_id in sorted(restricted_units):
        citation_only = unit_id not in seed_units
        temporal_only = unit_id in seed_units and not uncertain_indexes.intersection(by_unit[unit_id])
        correspondence_only = unit_id in procedure_units and all(
            not interpretation.statements[index].unresolved
            and (reviewed[index].decision != "unresolved"
                 or reviewed[index].unresolved_cause == "target_correspondence")
            for index in by_unit[unit_id]
        )
        aspects = list(dict.fromkeys(
            aspect for index in by_unit[unit_id]
            for aspect in [*interpretation.statements[index].unresolved,
                           *(reviewed[index].unresolved_aspects if index in reviewed else ())]
        ))
        for index in by_unit[unit_id]:
            source = interpretation.statements[index]
            digest = hashlib.sha256(json.dumps(
                [batch.batch_id, unit_id, index], ensure_ascii=False, separators=(",", ":"),
            ).encode("utf-8")).hexdigest()[:24]
            statements.append(RestrictedProtocolControlStatement(
                restricted_statement_id=f"restricted:{digest}",
                source_structure_unit_id=unit_id, source_statement_index=index,
                source_quote=source.quoted_text, source_span_ids=sorted(units[unit_id].source_span_ids),
                limitation_kind=("consumer_unavailable" if citation_only or temporal_only or correspondence_only
                                 else "interpretation_unresolved"),
                unresolved_dimensions=[
                    ("本条与尚未核清内容共同使用同一段依据，暂不能可靠区分各自影响；暂不用于判断"
                     if citation_only else
                     "同一原文单元的持续期或跨节点要求尚未完成核对，未证明各要求可独立采用；本单元整体保留待核"
                     if temporal_only else
                     "本条另有要求尚未完成装配，且未证明与同单元未决要求独立；完整来源保留但暂不能用于判断"
                     if index in reviewed and reviewed[index].decision == "additional_requirement" else
                     "系统尚未证明本条与具体操作或访视的对应关系；本单元整体暂不能用于判断"
                     if correspondence_only and reviewed[index].decision == "unresolved" else
                     "本条对应关系已有核对，但尚未证明它与同单元未决要求独立；本单元整体暂不能用于判断"
                     if correspondence_only else
                     "同一原文单元的对应关系尚未核清，未证明各要求可独立采用；本单元整体保留待核"),
                    *aspects,
                ],
                scope_quote=source.scope_quote, scope_context_unit_id=source.scope_context_unit_id,
                time_words=list(source.time_words), exception_words=source.exception_words,
                affected_stage=source.affected_stage, decision_functions=list(source.decision_functions),
                source_force=source.force,
            ))
    output = ProtocolControlBatchDispositionHydrated(
        batch_id=batch.batch_id, coverage_manifest_id=batch.coverage_manifest_id,
        owned_structure_unit_ids=list(batch.owned_structure_unit_ids),
        owned_source_span_ids=list(batch.owned_source_span_ids),
        dispositions=[ProtocolControlUnitDisposition(
            structure_unit_id=item.structure_unit_id,
            disposition=StructureUnitDispositionKind.RESTRICTED_SOURCE,
        ) if item.structure_unit_id in restricted_units else item for item in original.dispositions],
        candidates=retained, restricted_statements=sorted(
            statements, key=lambda item: (item.source_structure_unit_id, item.source_statement_index),
        ),
    )
    if check_protocol_control_batch_candidates(batch, output):
        return None
    return output


def _validate_restricted_definition_registration(
    batch: ProtocolControlDispositionBatch,
    result: ProtocolControlAgentRunResult,
    output: ProtocolControlBatchDispositionHydrated,
) -> None:
    """Recheck the actual registration without changing the source disposition."""
    if result.source_definition_consumers is not None:
        attempts = result.restricted_source_definition_consumer_attempts
        if len(attempts) != 1:
            raise ValueError("受限定义登记缺少唯一实际回答")
        attempt = attempts[0]
        raw = attempt.raw_output_text
        if (attempt.outcome != "parsed" or not isinstance(raw, str)
                or len(raw) != attempt.raw_output_chars
                or hashlib.sha256(raw.encode("utf-8")).hexdigest() != attempt.raw_output_sha256):
            raise ValueError("受限定义登记原答与实际回执不一致")
        declaration = SourceDefinitionConsumers.model_validate_json(raw)
        if (declaration.version != SOURCE_DEFINITION_CONSUMER_VERSION
                or declaration != result.source_definition_consumers):
            raise ValueError("受限定义登记字段与实际原答不一致")
        validate_source_definition_consumers(batch, result.source_interpretation, declaration)
        validate_restricted_definition_consumers(
            batch, result.source_interpretation, declaration, output.restricted_statements,
        )


def _restricted_statement_batch_from_review(
    batch: ProtocolControlDispositionBatch,
    result: ProtocolControlAgentRunResult,
) -> ProtocolControlBatchDispositionHydrated | None:
    """Keep validated independent dispositions and restrict only unresolved units.

    A unit whose statements are partly unresolved keeps its executable candidate only
    when a statement-level source proof shows the two requirements occupy disjoint
    verbatim ranges of the frozen excerpt; otherwise the whole unit stays restricted.
    """

    if result.capability_wire is not None:
        return _restricted_capability_batch(batch, result)

    interpretation = result.source_interpretation
    review = result.source_target_review
    last_attempt = result.attempts[-1]
    if (result.status != "需要核对" or result.final_output is not None
            or interpretation is None or review is None
            or last_attempt.outcome != "publication_invalid"
            or not set(last_attempt.error_classes) & {
                "SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED",
                "SOURCE_TARGET_REVIEW_UNRESOLVED",
                "TEMPORAL_SCOPE_UNRESOLVED",
            }):
        return None
    validate_source_interpretation(batch, interpretation)
    if not interpretation.statements:
        return None
    if sorted(item.statement_index for item in result.source_statement_coverage) != list(
        range(len(interpretation.statements))
    ):
        return None
    validate_source_target_review(
        batch, interpretation, result.source_statement_coverage, review,
    )
    covered = {"covered_by_official", "covered_by_procedure"}
    temporal_indexes = _temporal_restriction_indexes(batch, result) or set()
    has_wire = result.partial_wire is not None
    if has_wire:
        if ((result.source_definition_consumers is not None
             and not result.restricted_source_definition_consumer_attempts)
                or any("calculation_input" in item.decision_functions
                       for item in interpretation.statements)
                or any(item.decision not in covered | {"unresolved"}
                       and not (item.decision == "additional_requirement"
                                and item.statement_index in temporal_indexes)
                       for item in review.items)):
            return None
        original = hydrate_protocol_control_agent_output(result.partial_wire, batch)
        if not _coverage_matches_current_proofs(batch, result):
            return None
    else:
        if (interpretation.units_without_statement
                or any(not item.unresolved for item in interpretation.statements)
                or {item.statement_index for item in review.items}
                != set(range(len(interpretation.statements)))
                or any(item.decision in covered for item in review.items)
                or any(item.decision not in {"unresolved", "additional_requirement"}
                       for item in review.items)):
            return None
        original = None
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    reviewed = {item.statement_index: item for item in review.items}
    by_unit: dict[str, list[int]] = {}
    for index, source in enumerate(interpretation.statements):
        by_unit.setdefault(source.structure_unit_id, []).append(index)
    unresolved_indexes = {index for index, item in reviewed.items()
                          if item.decision in {"unresolved", "additional_requirement"}}
    if not unresolved_indexes:
        return None
    proofs: dict[int, RestrictedStatementScopeProof] = {}
    if has_wire:
        dispositions = {item.structure_unit_id: item for item in original.dispositions}
        coverage = {item.statement_index: item for item in result.source_statement_coverage}
        candidates_by_unit: dict[str, list[ProtocolControlCandidate]] = {}
        for candidate in original.candidates:
            for unit_id in candidate.frozen_structure_unit_ids:
                candidates_by_unit.setdefault(unit_id, []).append(candidate)
        unresolved_units = {interpretation.statements[index].structure_unit_id
                            for index in unresolved_indexes}
        proven_units: set[str] = set()
        for unit_id, indexes in by_unit.items():
            restricted_indexes = {index for index in indexes
                                  if index in unresolved_indexes}
            independent_indexes = [index for index in indexes
                                   if index not in restricted_indexes]
            if restricted_indexes:
                proved = _coexisting_statement_proofs(
                    batch, interpretation, coverage, unit_id, indexes,
                    restricted_indexes, dispositions[unit_id],
                    candidates_by_unit.get(unit_id, []),
                    temporal_indexes=frozenset(temporal_indexes),
                )
                if proved is None:
                    if (len(indexes) != 1 or indexes[0] not in unresolved_indexes
                            or (not interpretation.statements[indexes[0]].unresolved
                                and indexes[0] not in temporal_indexes)
                            or (indexes[0] in temporal_indexes
                                and interpretation.statements[indexes[0]].quoted_text
                                != units[unit_id].excerpt)):
                        return None
                    continue
                proofs.update(proved)
                proven_units.add(unit_id)
            if any(index in reviewed and interpretation.statements[index].unresolved
                   for index in independent_indexes):
                return None
            disposition = dispositions[unit_id]
            for index in independent_indexes:
                decision = reviewed.get(index)
                if decision is None:
                    if disposition.disposition == StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE:
                        if (coverage[index].status != "expressed"
                                or interpretation.statements[index].unresolved):
                            return None
                    elif disposition.disposition not in {
                        StructureUnitDispositionKind.POST_TREATMENT_EXECUTION,
                        StructureUnitDispositionKind.NON_ENROLLMENT_EXECUTION,
                        StructureUnitDispositionKind.PHASE_EXCLUDED,
                    }:
                        return None
                elif decision.decision == "covered_by_official":
                    if (disposition.disposition != StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY
                            or disposition.linked_official_code != decision.target_id):
                        return None
                elif (disposition.disposition != StructureUnitDispositionKind.REQUIRED_PROCEDURE
                      or decision.target_id not in (
                          disposition.linked_procedure_catalog_item_ids
                          or [disposition.linked_procedure_catalog_item_id]
                      )):
                    return None
        if any(dispositions[unit_id].disposition not in {
            StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
            StructureUnitDispositionKind.PHASE_EXCLUDED,
            StructureUnitDispositionKind.POST_TREATMENT_EXECUTION,
            StructureUnitDispositionKind.NON_ENROLLMENT_EXECUTION,
        } for unit_id in interpretation.units_without_statement):
            return None
        # A candidate may share a proven unit's spans; every other unresolved unit
        # keeps the unchanged intersection protection.
        unproven_units = unresolved_units - proven_units
        unproven_spans = {span_id for unit_id in unproven_units
                          for span_id in units[unit_id].source_span_ids}
        if any(set(candidate.frozen_structure_unit_ids) & unproven_units
               or set(candidate.source_span_ids) & unproven_spans
               for candidate in original.candidates):
            return None
    statements = []
    for index, source in enumerate(interpretation.statements):
        if index not in unresolved_indexes:
            continue
        unit = units[source.structure_unit_id]
        digest = hashlib.sha256(json.dumps(
            [batch.batch_id, source.structure_unit_id, index],
            ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()[:24]
        aspects = list(dict.fromkeys([
            *source.unresolved,
            *(reviewed[index].unresolved_aspects if index in reviewed else ()),
        ]))
        statements.append(RestrictedProtocolControlStatement(
            restricted_statement_id=f"restricted:{digest}",
            source_structure_unit_id=source.structure_unit_id,
            source_statement_index=index,
            source_quote=source.quoted_text,
            source_span_ids=sorted(unit.source_span_ids),
            limitation_kind=("consumer_unavailable" if index in temporal_indexes
                             else "interpretation_unresolved"),
            unresolved_dimensions=(
                ["当前系统尚未完成本条持续期或跨节点时间要求的核对，不能用于判定", *aspects]
                if index in temporal_indexes else aspects
            ),
            independent_scope_proof=proofs.get(index),
            scope_quote=source.scope_quote,
            scope_context_unit_id=source.scope_context_unit_id,
            time_words=list(source.time_words),
            exception_words=source.exception_words,
            affected_stage=source.affected_stage,
            decision_functions=list(source.decision_functions),
            source_force=source.force,
        ))
    restricted_ids = {item.source_structure_unit_id for item in statements
                      if item.independent_scope_proof is None}
    original_by_unit = (
        {item.structure_unit_id: item for item in original.dispositions}
        if original is not None else {}
    )
    output = ProtocolControlBatchDispositionHydrated(
        batch_id=batch.batch_id,
        coverage_manifest_id=batch.coverage_manifest_id,
        owned_structure_unit_ids=list(batch.owned_structure_unit_ids),
        owned_source_span_ids=list(batch.owned_source_span_ids),
        dispositions=[
            ProtocolControlUnitDisposition(
                structure_unit_id=unit_id,
                disposition=StructureUnitDispositionKind.RESTRICTED_SOURCE,
            ) if unit_id in restricted_ids else original_by_unit[unit_id]
            for unit_id in batch.owned_structure_unit_ids
        ] if has_wire else [ProtocolControlUnitDisposition(
            structure_unit_id=unit_id,
            disposition=StructureUnitDispositionKind.RESTRICTED_SOURCE,
        ) for unit_id in batch.owned_structure_unit_ids],
        restricted_statements=sorted(
            statements,
            key=lambda item: (item.source_structure_unit_id, item.source_statement_index),
        ),
        candidates=list(original.candidates) if original is not None else [],
    )
    # A source review is not a substitute for the executable candidate contract.
    if check_protocol_control_batch_candidates(batch, output):
        return None
    return output


def restricted_batch_from_review(
    batch: ProtocolControlDispositionBatch,
    result: ProtocolControlAgentRunResult,
) -> ProtocolControlBatchDispositionHydrated | None:
    if not result.attempts:
        return None
    if result.capability_wire is None and (
        not result.attempts[-1].error_classes
        or set(result.attempts[-1].error_classes) - {
            "SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED",
            "SOURCE_TARGET_REVIEW_UNRESOLVED",
            "TEMPORAL_SCOPE_UNRESOLVED",
        }
    ):
        # An invalid/partial review is a recovery diagnostic, not a faithful
        # non-executable requirement. Do not validate it as an adopted review.
        return None
    output = _restricted_statement_batch_from_review(batch, result)
    if output is not None:
        _validate_restricted_definition_registration(batch, result, output)
        return output
    if (result.status != "需要核对" or result.final_output is not None
            or result.source_interpretation is None or result.source_target_review is None
            or not result.attempts or result.attempts[-1].outcome != "publication_invalid"
            or result.capability_wire is not None):
        return None
    validate_source_interpretation(batch, result.source_interpretation)
    if sorted(item.statement_index for item in result.source_statement_coverage) != list(
        range(len(result.source_interpretation.statements))
    ):
        return None
    validate_source_target_review(
        batch, result.source_interpretation, result.source_statement_coverage,
        result.source_target_review,
    )
    output = _whole_unit_restriction(batch, result)
    if output is not None:
        _validate_restricted_definition_registration(batch, result, output)
    return output
