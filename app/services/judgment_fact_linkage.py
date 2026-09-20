"""Exact source linkage for judgment excerpts, not semantic qualification."""
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from app.domain.contracts.judgment_search import JudgmentSearchCoverageSummary
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.domain.publication import canonical_hash


@dataclass(frozen=True)
class JudgmentExcerptLink:
    linkage_id: str
    requirement_id: str
    predicate_ids: tuple[str, ...]
    found_candidate_index: int
    excerpt_index: int
    candidate_sha256: str
    matches: tuple[tuple[str, str], ...]
    status: Literal["unique_source_match", "no_source_match", "ambiguous_source_match",
                    "requirement_outside_binding_scope"]


def load_prepared_judgment_links(session, artifact_store, *, context_id: str):
    """Rebuild source links from persisted preparation and original search receipts."""
    from app.services.predicate_binding_input import build_predicate_binding_frozen_input
    from app.services.review_candidate_scope import require_prepared_candidate_scope
    from app.services.review_judgment_provenance import verify_frozen_judgment_search_result
    from app.storage.review_context_repository import ReviewContextV2Repository

    context = ReviewContextV2Repository(session).get(context_id)
    source = build_predicate_binding_frozen_input(session, context.authority.review_episode_id)
    require_prepared_candidate_scope(session, context_id, source)
    links = []
    for search in context.judgment_search_results:
        verify_frozen_judgment_search_result(
            session, artifact_store, authority=context.authority, frozen=search,
        )
        links.extend(link_judgment_excerpts(search.summary, source))
    return tuple(links)


def judgment_source_index(source: PredicateBindingFrozenInput):
    """Index exact existing assertion sources; no semantic matching or correction."""
    locators = {item.locator_id: item for item in source.locators}
    index: dict[tuple[str, str, int, str], list[tuple[str, str]]] = {}
    for fact in source.facts:
        basis = fact.assertion_basis
        if basis is None or basis.locator_id not in fact.locator_ids:
            continue
        locator = locators.get(basis.locator_id)
        if (locator is None or basis.asserted_object != fact.asserted_object
                or basis.source_text_sha256 != locator.source_text_sha256
                or basis.assertion_text != locator.excerpt):
            continue
        key = (locator.source_document_version_id, locator.page_artifact_id,
               locator.page_number, locator.excerpt)
        index.setdefault(key, []).append((fact.fact_id, locator.locator_id))
    return index


def link_judgment_excerpts(
    summary: JudgmentSearchCoverageSummary, source: PredicateBindingFrozenInput,
) -> tuple[JudgmentExcerptLink, ...]:
    """Call after receipt/source verification; exact linkage is not clinical truth."""
    summary = JudgmentSearchCoverageSummary.model_validate(summary.model_dump(mode="json"))
    source = PredicateBindingFrozenInput.model_validate(source.model_dump(mode="json"))
    requirements = [requirement for component in source.components
                    for requirement in component.evidence_requirements
                    if requirement.requirement_id == summary.requirement_id]
    if len(requirements) > 1:
        raise ValueError("判断摘录未对应到本次审核唯一的资料要求")
    index = judgment_source_index(source)
    rows = []
    for found_index, found in enumerate(summary.found_candidates):
        for excerpt_index, excerpt in enumerate(found.candidates):
            key = (found.source_document_version_id, found.page_artifact_id,
                   found.page_number, excerpt.text)
            matches = tuple(sorted(set(index.get(key, ())))) if requirements else ()
            candidate_sha = canonical_hash({"found": found.model_dump(mode="json"),
                                            "excerpt_index": excerpt_index})
            rows.append(JudgmentExcerptLink(
                linkage_id=canonical_hash({
                    "version": "judgment-fact-linkage/v1", "scope": summary.scope_sha256,
                    "requirement": summary.requirement_id, "source": source.frozen_input_sha256,
                    "found_index": found_index, "candidate": candidate_sha,
                    "excerpt_sha256": sha256(excerpt.text.encode("utf-8")).hexdigest(),
                    "matches": matches,
                }),
                requirement_id=summary.requirement_id,
                predicate_ids=tuple(sorted(requirements[0].predicate_ids)) if requirements else (),
                found_candidate_index=found_index, excerpt_index=excerpt_index,
                candidate_sha256=candidate_sha, matches=matches,
                status=("requirement_outside_binding_scope" if not requirements else
                        "unique_source_match" if len(matches) == 1 else
                        "no_source_match" if not matches else "ambiguous_source_match"),
            ))
    return tuple(rows)
