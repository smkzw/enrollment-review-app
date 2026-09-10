"""Project already reconciled, object-specific clinical-meaning annotations.

Caller must rebuild source sets from persisted primary reviews and coverage.
No free-standing proof DTO, no inference of absence from empty handwriting,
and no inference of printed clinical analysis from a document category.
"""

from app.domain.contracts.page_review import HandwritingKind
from app.domain.page_normalization import normalize_text
from app.domain.page_review_evidence_sources import PageVisualEvidenceSourceSet
from app.projections.page_review_visual_locators import project_visual_locators


def written_judgment_locator_ids(
    source_set: PageVisualEvidenceSourceSet, *, asserted_object: str,
) -> frozenset[str]:
    """Return exact locators, never an eligibility decision or absence proof.

    Generic notes and signatures need a separate semantic applicability review.
    An accepted CS/NCS annotation is usable only for its explicit source object.
    """
    source_set = PageVisualEvidenceSourceSet.model_validate(source_set.model_dump())
    target = normalize_text(asserted_object)
    if not target:
        return frozenset()
    accepted = {
        source.handwriting_source_id for source in source_set.handwriting_sources
        if source.kind == HandwritingKind.CS_NCS_JUDGMENT
        and all(
            reading.observation.context is not None
            and normalize_text(reading.observation.context.target_text) == target
            for reading in source.readings
        )
    }
    return frozenset(
        locator.locator_id for locator in project_visual_locators(source_set)
        if locator.target_id in accepted
    )
