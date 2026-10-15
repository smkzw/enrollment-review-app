"""Append explicit event/exposure reference revisions after source-only fact growth."""

from app.domain.publication import canonical_hash
from app.storage.fact_repositories import (
    ClinicalEventV2Repository, MedicationExposureV2Repository,
)


def append_source_reference_successors(session, *, authority, run_id, facts, created_at):
    from app.services.patient_profile_service import PatientProfileService

    replacements = {
        fact.inherited_from_fact_id: fact.fact_id
        for fact in facts if fact.inherited_from_fact_id is not None
    }
    profile = PatientProfileService()
    outputs = []
    for entities, repository, id_field in (
        (profile._published_events(session, authority), ClinicalEventV2Repository(session), "event_id"),
        (profile._published_exposures(session, authority), MedicationExposureV2Repository(session), "exposure_id"),
    ):
        appended = []
        for prior in entities:
            fact_ids = sorted({replacements.get(item, item) for item in prior.fact_ids})
            if fact_ids == prior.fact_ids:
                continue
            prior_id = getattr(prior, id_field)
            identity = canonical_hash({
                "contract": "source-reference-successor/v1", "run_id": run_id,
                "prior": prior.model_dump(mode="json"), "fact_ids": fact_ids,
            })
            successor = type(prior).model_validate({
                **prior.model_dump(),
                id_field: f"source-successor:{identity}",
                "run_id": run_id, "revision": prior.revision + 1,
                "created_at": created_at, "source_revision_of": prior_id,
                "fact_ids": fact_ids,
            })
            appended.append(repository.create(successor))
        outputs.append(appended)
    from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
    from app.storage.fact_repositories import ClinicalFactV2Repository
    fact_repository = ClinicalFactV2Repository(session)
    for prior in profile._latest_expectations(session, authority):
        fact_ids = sorted({replacements.get(item, item) for item in prior.coverage_fact_ids})
        if fact_ids == prior.coverage_fact_ids:
            continue
        identity = canonical_hash({
            "contract": "source-reference-successor/v1",
            "prior": prior.model_dump(mode="json"), "fact_ids": fact_ids,
        })
        successor = type(prior).model_validate({
            **prior.model_dump(), "expectation_id": f"source-successor:{identity}",
            "source_revision_of": prior.expectation_id,
            "revision": prior.revision + 1, "created_at": created_at,
            "coverage_fact_ids": fact_ids,
            "locator_ids": sorted({
                locator for fact_id in fact_ids
                for locator in fact_repository.get(fact_id).locator_ids
            }),
        })
        EvidenceExpectationV2Repository(session).project(successor)
    return tuple(outputs)
