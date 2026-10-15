"""Work-draft policy for sealed supplied-record search, not factual denial."""
from app.domain.contracts.enums import TruthValue
from app.domain.expression import EvaluationResult


def calculate_history_not_seen(row, purpose, *, time_constraint=None, anchor_dates=None):
    if (row.get("status") != "not_seen" or row.get("candidate_mentions_present") is not False
            or not row.get("scope_sha256") or not row.get("summary_sha256")
            or not row.get("page_keys") or purpose is None
            or purpose.target_kind != "event_history"
            or purpose.record_obligation != "not_required_by_source"
            or purpose.proposition_direction != row.get("proposition_direction")):
        return None
    if time_constraint is not None and not (anchor_dates or {}).get(time_constraint.anchor_type):
        return EvaluationResult(truth=TruthValue.UNKNOWN, reason_codes=["date_or_anchor_missing"])
    # This is the proposition's direction, before any enclosing NOT/exclusion.
    direction = purpose.proposition_direction
    if direction not in {"event_present", "event_absent"}:
        return None
    return EvaluationResult(truth=TruthValue.FALSE if direction == "event_present" else TruthValue.TRUE,
                            reason_codes=["supplied_records_history_not_seen"])
