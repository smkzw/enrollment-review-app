"""Attribute verified searched absence to explicit published control references."""
from app.domain.contracts.enums import GapType
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.projections.control_evidence_requirements import (
    project_control_evidence_requirements, shared_control_requirements,
)
from app.services.eligibility_review_projection import _expectation_views, requirement_summary_gaps


def missing_control_judgments(frozen, selections):
    publication = frozen.clause_pack.control_publication
    if publication is None:
        return frozenset()
    episode = frozen.review_episode
    requirements = [item for item in project_control_evidence_requirements(publication)
                    if item.workflow_stage_id == episode.workflow_stage_id
                    and item.due_stage == episode.stage
                    and "investigator_assessment" in {
                        value.strip().casefold() for value in item.required_source_types}]
    current_ids = {item.requirement_id for item in requirements}
    templates = {item.template_id: item for item in frozen.expectation_templates}
    gaps = requirement_summary_gaps(
        [item for item in shared_control_requirements(publication) if item.requirement_id in current_ids],
        episode_stage=episode.stage, workflow_stage_id=episode.workflow_stage_id,
        summaries={item.summary.requirement_id: item.summary for item in frozen.judgment_search_results},
        templates_by_requirement={item.requirement_id: item for item in templates.values()},
        expectations=_expectation_views(frozen.expectations, templates),
    )
    missing = set()
    for identity in project_control_atom_identities(publication):
        if not identity.atom.requires_professional_judgment or selections.get(identity.identity_sha256):
            continue
        candidates = [item for item in requirements if item.protocol_control_id == identity.protocol_control_id]
        # An unattributed requirement cannot establish which judgment is absent.
        if any(not item.atom_refs for item in candidates):
            continue
        key = (identity.layer, identity.group_index, identity.atom_index)
        linked = [item for item in candidates if key in {ref.key for ref in item.atom_refs}]
        if linked and all(gaps.get(item.requirement_id) == GapType.PROFESSIONAL_JUDGMENT for item in linked):
            missing.add(identity.identity_sha256)
    return frozenset(missing)
