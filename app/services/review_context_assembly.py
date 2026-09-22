"""Source-bound inputs for a new review; no model calls or implicit publication."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.domain.contracts.review_context_v2 import ReviewContextSnapshotV2
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.services.published_clause_pack import project_published_clause_pack
from app.services.fact_normalization_command_service import authority_from_active_episode
from app.services.patient_profile_service import PatientProfileService
from app.services.review_judgment_provenance import freeze_judgment_search_result
from app.services.review_protocol_source import load_review_protocol_source
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.fact_rule_link_repository import FactRuleLinkV2Repository
from app.storage.judgment_search_repository import JudgmentSearchSummaryRepository
from app.storage.repositories import EpisodeRepository, ProjectRepository, SubjectRepository


def review_clinical_material_sha256(
    *,
    facts,
    fact_rule_links,
    events,
    medication_exposures,
    expectations,
    conflict_groups,
) -> str:
    """Content identity of the mutable clinical heads frozen into a review context."""
    return canonical_hash({
        "identity": "review-clinical-material/v1",
        "facts": [item.model_dump(mode="json") for item in facts],
        "fact_rule_links": [item.model_dump(mode="json") for item in fact_rule_links],
        "events": [item.model_dump(mode="json") for item in events],
        "medication_exposures": [item.model_dump(mode="json") for item in medication_exposures],
        "expectations": [item.model_dump(mode="json") for item in expectations],
        "conflict_groups": [item.model_dump(mode="json") for item in conflict_groups],
    })


def current_review_clinical_material_sha256(session: Session, authority) -> str:
    """Rebuild the current clinical-head identity without creating a new context."""
    profile = PatientProfileService()
    facts = tuple(sorted(profile._published_facts(session, authority), key=lambda item: item.fact_id))
    links_by_fact = FactRuleLinkV2Repository(session).list_for_facts(
        [item.fact_id for item in facts], facts=facts,
    )
    links = tuple(sorted(
        (link for values in links_by_fact.values() for link in values),
        key=lambda item: item.link_id,
    ))
    return review_clinical_material_sha256(
        facts=facts,
        fact_rule_links=links,
        events=tuple(sorted(profile._published_events(session, authority), key=lambda item: item.event_id)),
        medication_exposures=tuple(sorted(
            profile._published_exposures(session, authority), key=lambda item: item.exposure_id,
        )),
        expectations=tuple(sorted(
            profile._latest_expectations(session, authority), key=lambda item: item.template_id,
        )),
        conflict_groups=tuple(sorted(
            profile._published_conflicts(session, authority), key=lambda item: item.conflict_group_id,
        )),
    )


def frozen_review_clinical_material_sha256(context: ReviewContextSnapshotV2) -> str:
    """Read the same clinical-head identity from an immutable review context."""
    return review_clinical_material_sha256(
        facts=context.facts,
        fact_rule_links=context.fact_rule_links,
        events=context.events,
        medication_exposures=context.medication_exposures,
        expectations=context.expectations,
        conflict_groups=context.conflict_groups,
    )


def assemble_review_context(
    session: Session, artifact_store: ArtifactStore, *, review_episode_id: str,
    review_run_id: str, evaluator_version: str, created_at: datetime,
    context_id: str | None = None,
) -> ReviewContextSnapshotV2:
    """Caller owns one transaction and stores this before its preallocated run.

    Current heads and search choices are selected only here, never when rendering
    an older report. Incomplete searches are included, not filtered as failures.
    """
    authority = authority_from_active_episode(session, review_episode_id)
    validator = FactAuthorityValidator(session)
    validator.validate(authority)
    episode = EpisodeRepository(session).get(review_episode_id)
    subject = SubjectRepository(session).get(authority.subject_id)
    project = ProjectRepository(session).get(authority.project_id)
    protocol = load_review_protocol_source(session, authority)
    pack = project_published_clause_pack(session, protocol.rule_set)
    profile = PatientProfileService()
    facts = profile._published_facts(session, authority)
    links_by_fact = FactRuleLinkV2Repository(session).list_for_facts(
        [item.fact_id for item in facts], facts=facts,
    )
    events = profile._published_events(session, authority)
    exposures = profile._published_exposures(session, authority)
    conflicts = profile._published_conflicts(session, authority)
    expectations = profile._latest_expectations(session, authority)
    profile._validate_referential_closure(
        facts=facts, events=events, exposures=exposures,
        conflicts=conflicts, expectations=expectations,
    )
    locator_ids = sorted({
        locator_id for item in (*facts, *events, *exposures, *conflicts, *expectations)
        for locator_id in item.locator_ids
    })
    validator.validate_locators(authority, locator_ids)
    entries = JudgmentSearchSummaryRepository(session).latest_entries_for_authority(authority)
    searches = [
        freeze_judgment_search_result(
            session, artifact_store, authority=authority, summary_id=entry.summary_id,
        )
        for entry in entries.values()
    ]
    data = {
        "context_id": context_id if context_id is not None else f"review-context-v2:{uuid4().hex}",
        "review_run_id": review_run_id, "authority": authority,
        "review_episode": episode,
        "subject": subject, "project_name": project.project_name,
        "project_revision": project.revision,
        "protocol_document": protocol.protocol_document,
        "rule_set_sha256": canonical_hash(protocol.rule_set.model_dump(mode="json")),
        "clause_pack_sha256": pack.clause_pack_sha256,
        "clause_pack": pack,
        "protocol_integrity_gate_result_id": protocol.integrity_gate.gate_result_id,
        "evaluator_version": evaluator_version,
        "requirements_scope_version": "review-requirements-scope/v1",
        "workflow_stages": protocol.workflow_stages,
        "facts": tuple(sorted(facts, key=lambda item: item.fact_id)),
        "fact_rule_links": tuple(sorted(
            (link for links in links_by_fact.values() for link in links),
            key=lambda item: item.link_id,
        )),
        "events": tuple(sorted(events, key=lambda item: item.event_id)),
        "medication_exposures": tuple(sorted(exposures, key=lambda item: item.exposure_id)),
        "expectation_templates": tuple(sorted(protocol.expectation_templates, key=lambda item: item.template_id)),
        "expectations": tuple(sorted(expectations, key=lambda item: item.template_id)),
        "conflict_groups": tuple(sorted(conflicts, key=lambda item: item.conflict_group_id)),
        "judgment_search_results": tuple(sorted(searches, key=lambda item: item.summary_id)),
        "created_at": created_at,
    }
    draft = ReviewContextSnapshotV2.model_construct(**data, context_sha256="0" * 64)
    return ReviewContextSnapshotV2(
        **data,
        context_sha256=canonical_hash(draft.model_dump(mode="json", exclude={"context_sha256"})),
    )
