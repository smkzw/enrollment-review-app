"""Exact written-source linkage for published cross-chapter requirements."""
from dataclasses import dataclass

from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.judgment_search import JudgmentSearchCoverageSummary
from app.domain.publication import canonical_hash
from app.projections.control_evidence_requirements import project_control_evidence_requirements
from app.services.judgment_fact_linkage import JudgmentExcerptLink, judgment_source_index


@dataclass(frozen=True)
class ControlJudgmentExcerptLink(JudgmentExcerptLink):
    protocol_control_id: str | None
    evidence_key: str | None
    atom_refs: tuple[tuple, ...]


def load_prepared_control_judgment_links(session, artifact_store, *, context_id, source):
    from app.services.review_candidate_scope import require_prepared_candidate_scope
    from app.services.review_judgment_provenance import verify_frozen_judgment_search_result
    from app.storage.review_context_repository import ReviewContextV2Repository

    source = ControlBindingFrozenInput.model_validate(source)
    context = ReviewContextV2Repository(session).get(context_id)
    require_prepared_candidate_scope(session, context_id, source.evidence_input, control_input=source)
    links = []
    for search in context.judgment_search_results:
        verify_frozen_judgment_search_result(session, artifact_store,
                                            authority=context.authority, frozen=search)
        links.extend(link_control_judgment_excerpts(search.summary, source))
    return tuple(links)


def link_control_judgment_excerpts(summary, source):
    """Requires receipt-verified sources; missing atom references remain unassigned."""
    summary = JudgmentSearchCoverageSummary.model_validate(summary.model_dump(mode="json"))
    source = ControlBindingFrozenInput.model_validate(source.model_dump(mode="json"))
    requirements = [item for item in project_control_evidence_requirements(source.publication)
                    if item.requirement_id == summary.requirement_id
                    and item.workflow_stage_id == source.evidence_input.episode.workflow_stage_id]
    if len(requirements) > 1:
        raise ValueError("判断摘录未对应到唯一的方案补充资料要求")
    requirement = requirements[0] if requirements else None
    refs = (() if requirement is None else tuple(sorted(
        item.key for item in requirement.atom_refs)))
    index = judgment_source_index(source.evidence_input)
    rows = []
    for found_index, found in enumerate(summary.found_candidates):
        for excerpt_index, excerpt in enumerate(found.candidates):
            key = (found.source_document_version_id, found.page_artifact_id,
                   found.page_number, excerpt.text)
            matches = tuple(sorted(set(index.get(key, ())))) if requirement is not None else ()
            candidate_sha = canonical_hash({"found": found.model_dump(mode="json"), "excerpt_index": excerpt_index})
            rows.append(ControlJudgmentExcerptLink(
                linkage_id=canonical_hash({"version": "control-judgment-fact-linkage/v1",
                    "scope": summary.scope_sha256, "requirement": summary.requirement_id,
                    "source": source.frozen_input_sha256, "candidate": candidate_sha,
                    "found_index": found_index, "matches": matches, "atom_refs": refs}),
                requirement_id=summary.requirement_id, predicate_ids=(),
                found_candidate_index=found_index, excerpt_index=excerpt_index,
                candidate_sha256=candidate_sha, matches=matches,
                status=("requirement_outside_binding_scope" if requirement is None else
                        "unique_source_match" if len(matches) == 1 else
                        "no_source_match" if not matches else "ambiguous_source_match"),
                protocol_control_id=None if requirement is None else requirement.protocol_control_id,
                evidence_key=None if requirement is None else requirement.evidence_key, atom_refs=refs,
            ))
    return tuple(rows)
