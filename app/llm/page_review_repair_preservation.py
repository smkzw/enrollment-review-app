"""Offline preservation check for format rereads; not wired into live readers."""

from collections import Counter
from dataclasses import dataclass
import json

from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.page_review import PageReviewPayload
from app.llm.page_review_format_repair import (
    PageResponseFormatError,
    evaluate_page_review_response,
)

REPAIR_PRESERVATION_VERSION = "page-repair-preservation/v2"


@dataclass(frozen=True)
class RepairPreservationResult:
    original_parseable: bool
    protected_observations: int
    uncheckable_observations: int
    missing_or_changed_observations: int
    additional_or_changed_observations: int


def _signature(observation) -> str:
    # IDs may be renumbered during formatting; clinical content and context may not.
    return json.dumps(observation.model_dump(mode="json", exclude={"observation_id"}),
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def check_repair_preservation(
    previous_response: str,
    corrected: PageReviewPayload,
    *,
    clause_pack: ClausePack,
) -> RepairPreservationResult:
    """Compare independently valid observations, without declaring either read true.

    Invalid observations are counted, not repaired or silently made authoritative.
    Full clinical context and multiplicity are preserved even for equal normalized keys.
    Clause direction changes are outside this observation-preservation check.
    """
    from app.llm.page_review_harness import PageReviewHarnessError, extract_json_object

    try:
        raw = extract_json_object(previous_response)
    except PageReviewHarnessError:
        return RepairPreservationResult(False, 0, 0, 0, 0)

    protected = uncheckable = missing = additional = 0
    for field in ("facts", "handwriting"):
        entries = raw.get(field)
        if not isinstance(entries, list):
            uncheckable += 1
            continue
        originals = Counter()
        for entry in entries:
            candidate = {"has_eligibility_value": True, "facts": [],
                         "handwriting": [], "clause_signals": []}
            candidate[field] = [entry]
            try:
                evaluated = evaluate_page_review_response(
                    json.dumps(candidate, ensure_ascii=False),
                    clause_pack=clause_pack, review_focus=None,
                )
            except (PageResponseFormatError, ValueError, TypeError):
                uncheckable += 1
                continue
            observation = getattr(evaluated.payload, field)[0]
            originals[_signature(observation)] += 1
            protected += 1
        replacements = Counter(_signature(item) for item in getattr(corrected, field))
        missing += sum((originals - replacements).values())
        additional += sum((replacements - originals).values())
    return RepairPreservationResult(True, protected, uncheckable, missing, additional)
