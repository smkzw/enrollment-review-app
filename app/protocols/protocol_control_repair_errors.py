"""Map publication gate findings to bounded ProtocolControlAgent repair scope."""

from __future__ import annotations

from typing import Any

from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentWireValidationError,
)

# Gate codes that require splitting one hydrated candidate into several while
# conserving the complete authorized source-structure-unit union.
CANDIDATE_REPARTITION_GATE_CODES = frozenset(
    {
        "ACTION_TARGET_SCOPE_MISMATCH",
        "MIXED_DECISION_STAGE_CONTROL",
        "MIXED_TRIGGER_DECISION_STAGES",
        "BASELINE_VALUE_SCOPE_MIXED",
        "MIXED_OBLIGATION_KIND_SCOPE",
    }
)

# Gate codes that authorize merge/split/rewrite of every candidate sharing one
# source-structure-unit closure while conserving the complete source union.
SOURCE_CLOSURE_REWRITE_GATE_CODES = frozenset(
    {"CONDITIONAL_EXEMPTION_SCOPE_SPLIT"}
)

# These findings require regrouping one candidate's full expression while its
# candidate count and frozen source key remain fixed. Atom-position repair is
# too narrow; candidate repartition is too broad.
CANDIDATE_EXPRESSION_REPAIR_GATE_CODES = frozenset(
    {"CONDITIONAL_EXEMPTION_BINDING_MISSING"}
)

SOURCE_INSERT_GATE_CODES = frozenset({"ENROLLMENT_PROHIBITION_UNCOVERED"})


def gate_issue_allows_candidate_repartition(issue: Any) -> bool:
    return getattr(issue, "code", None) in CANDIDATE_REPARTITION_GATE_CODES


def gate_issue_allows_source_closure_rewrite(issue: Any) -> bool:
    return getattr(issue, "code", None) in SOURCE_CLOSURE_REWRITE_GATE_CODES


def publication_repair_error(
    *,
    issues: list[Any],
    candidate_by_id: dict[str, Any],
    control_to_candidate: dict[str, str | None],
    default_structure_unit_ids: list[str],
) -> ProtocolControlAgentWireValidationError:
    allow_candidate_repartition = any(
        gate_issue_allows_candidate_repartition(issue) for issue in issues
    )
    allow_source_closure_rewrite = any(
        gate_issue_allows_source_closure_rewrite(issue) for issue in issues
    )
    allow_source_insert = any(
        issue.code in SOURCE_INSERT_GATE_CODES for issue in issues
    )
    if allow_source_insert:
        repair_scope_issues = [
            issue for issue in issues if issue.code in SOURCE_INSERT_GATE_CODES
        ]
        allow_candidate_repartition = False
        allow_source_closure_rewrite = False
    elif allow_source_closure_rewrite:
        repair_scope_issues = [
            issue
            for issue in issues
            if gate_issue_allows_source_closure_rewrite(issue)
        ]
        allow_candidate_repartition = False
    elif allow_candidate_repartition:
        repair_scope_issues = [
            issue
            for issue in issues
            if gate_issue_allows_candidate_repartition(issue)
        ]
    else:
        repair_scope_issues = issues
    candidate_ids: list[str] = []
    structure_unit_ids: list[str] = []
    obligation_source_span_ids: list[str] = []
    messages = [
        f"{issue.code}: {issue.message}"
        for issue in (repair_scope_issues if allow_source_insert else issues)
    ]

    def candidate_for_entity(entity_id: str | None) -> str | None:
        if not entity_id:
            return None
        if entity_id in candidate_by_id:
            return entity_id
        owner = entity_id.split("/", 1)[0]
        if owner in candidate_by_id:
            return owner
        return control_to_candidate.get(entity_id)

    for issue in repair_scope_issues:
        issue_candidate_ids = list(getattr(issue, "candidate_ids", ()) or ())
        issue_structure_unit_ids = list(
            getattr(issue, "structure_unit_ids", ()) or ()
        )
        if not issue_candidate_ids:
            owner = candidate_for_entity(issue.entity_id)
            if owner is not None:
                issue_candidate_ids.append(owner)
                if not issue_structure_unit_ids:
                    issue_structure_unit_ids.extend(
                        candidate_by_id[owner].frozen_structure_unit_ids
                    )
        if gate_issue_allows_source_closure_rewrite(issue) and not issue_candidate_ids:
            candidate_id = candidate_for_entity(issue.entity_id)
            candidate = candidate_by_id.get(candidate_id or "")
            if candidate is not None:
                issue_candidate_ids.append(candidate.control_candidate_id)
                if not issue_structure_unit_ids:
                    issue_structure_unit_ids.extend(
                        candidate.frozen_structure_unit_ids
                    )
        if issue.code not in (
            CANDIDATE_EXPRESSION_REPAIR_GATE_CODES
            | SOURCE_CLOSURE_REWRITE_GATE_CODES
        ):
            obligation_source_span_ids.extend(
                getattr(issue, "obligation_source_span_ids", ()) or ()
            )
        if issue_candidate_ids or issue_structure_unit_ids:
            candidate_ids.extend(issue_candidate_ids)
            structure_unit_ids.extend(issue_structure_unit_ids)
            continue
        candidate_id = candidate_for_entity(issue.entity_id)
        candidate = candidate_by_id.get(candidate_id or "")
        if candidate is not None:
            candidate_ids.append(candidate.control_candidate_id)
            structure_unit_ids.extend(candidate.frozen_structure_unit_ids)
        else:
            structure_unit_ids.extend(default_structure_unit_ids)
    return ProtocolControlAgentWireValidationError(
        "PUBLICATION_GATE_REJECTED",
        "\n".join(messages),
        structure_unit_ids=structure_unit_ids,
        candidate_ids=candidate_ids,
        obligation_source_span_ids=(
            []
            if allow_candidate_repartition or allow_source_closure_rewrite
            else obligation_source_span_ids
        ),
        error_class_codes=[issue.code for issue in issues],
        allow_candidate_repartition=allow_candidate_repartition,
        allow_source_closure_rewrite=allow_source_closure_rewrite,
        allow_source_insert=allow_source_insert,
    )


def clinical_repair_error(issues: list[Any]) -> ProtocolControlAgentWireValidationError:
    return ProtocolControlAgentWireValidationError(
        "CLINICAL_REJECT_GATE_REJECTED",
        "\n".join(f"{issue.code}: {issue.message}" for issue in issues),
        structure_unit_ids=[
            unit_id for issue in issues for unit_id in issue.structure_unit_ids
        ],
        error_class_codes=[issue.code for issue in issues],
    )


def combined_repair_error(
    *errors: ProtocolControlAgentWireValidationError,
) -> ProtocolControlAgentWireValidationError:
    """Expose all independently detected defects to one bounded repair pass."""

    active = [error for error in errors if error is not None]
    allow_candidate_repartition = any(
        error.allow_candidate_repartition for error in active
    )
    allow_source_closure_rewrite = any(
        error.allow_source_closure_rewrite for error in active
    )
    allow_source_insert = any(error.allow_source_insert for error in active)
    if allow_source_insert:
        repair_scope_errors = [error for error in active if error.allow_source_insert]
        allow_candidate_repartition = False
        allow_source_closure_rewrite = False
    elif allow_source_closure_rewrite:
        repair_scope_errors = [
            error for error in active if error.allow_source_closure_rewrite
        ]
        allow_candidate_repartition = False
    elif allow_candidate_repartition:
        repair_scope_errors = [
            error for error in active if error.allow_candidate_repartition
        ]
    else:
        repair_scope_errors = active
    return ProtocolControlAgentWireValidationError(
        "OUTPUT_VALIDATION_REJECTED",
        "\n".join(str(error) for error in active),
        structure_unit_ids=sorted(
            {
                unit_id
                for error in repair_scope_errors
                for unit_id in error.structure_unit_ids
            }
        ),
        candidate_ids=sorted(
            {
                candidate_id
                for error in repair_scope_errors
                for candidate_id in error.candidate_ids
            }
        ),
        obligation_source_span_ids=(
            []
            if allow_candidate_repartition or allow_source_closure_rewrite
            else sorted(
                {
                    span_id
                    for error in active
                    for span_id in error.obligation_source_span_ids
                }
            )
        ),
        error_class_codes=[
            code for error in active for code in error.error_class_codes
        ],
        allow_candidate_repartition=allow_candidate_repartition,
        allow_source_closure_rewrite=allow_source_closure_rewrite,
        allow_source_insert=allow_source_insert,
    )


def replay_validation_error(
    *,
    publication_report: Any,
    clinical_issues: list[Any],
    candidate_by_id: dict[str, Any],
    control_to_candidate: dict[str, str | None],
    default_structure_unit_ids: list[str],
) -> ProtocolControlAgentWireValidationError | None:
    """Return one complete repair scope for the current hydrated output."""

    errors: list[ProtocolControlAgentWireValidationError] = []
    if not publication_report.accepted:
        errors.append(
            publication_repair_error(
                issues=list(publication_report.issues),
                candidate_by_id=candidate_by_id,
                control_to_candidate=control_to_candidate,
                default_structure_unit_ids=default_structure_unit_ids,
            )
        )
    # A gold-set expectation may reject final acceptance, but feeding that
    # expectation back as a repair instruction would disclose the answer and
    # can coerce the Agent into inventing a control.
    repairable_clinical_issues = [
        issue for issue in clinical_issues if issue.code != "CONTROL_DELTA_DROPPED"
    ]
    if repairable_clinical_issues:
        errors.append(clinical_repair_error(repairable_clinical_issues))
    return combined_repair_error(*errors) if errors else None
