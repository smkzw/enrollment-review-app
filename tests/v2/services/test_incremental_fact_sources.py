"""Synthetic immutable source chains, not clinical acceptance or model gold."""
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.contracts.enums import SnapshotStatus
from app.domain.contracts.evidence_ingestion import EvidenceSnapshot, EvidenceSnapshotMember
from app.domain.contracts.evidence_locator import (
    EvidenceProcessingCandidate, EvidenceProcessingCandidateEvent,
    ProcessingCandidateAttemptManifest, processing_candidate_input_hash,
)
from app.domain.publication import evidence_processing_manifest_hash, evidence_snapshot_collection_hash
from app.services.patient_profile_service import PatientProfileService
from app.storage.codecs import encode_contract
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository, EvidenceProcessingCandidateRepository,
)
from app.storage.evidence_models import EvidenceSnapshotV2Record
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.models import ReviewEpisodeRecord
from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository
from tests.v2.services.test_fact_correction_job import _variable_rule_revision, _publish_fact
from tests.v2.storage.test_fact_correction_repository import _seed_valid_chain
from tests.v2.storage.test_fact_repositories import _update_episode

NOW = datetime(2026, 10, 14, tzinfo=UTC)


def _incremental_source(session, old, added, *, change_metadata=False, retained_only=False):
    """Compose two real Phase4 repository fixtures under one owner; no fake completion row."""
    snapshots = EvidenceSnapshotRepository(session)
    before = snapshots.get(old["snapshot_id"])
    # Fixture seed already sets the active pointer; reflect it in its status mirror.
    active = before.model_copy(update={"status": SnapshotStatus.ACTIVE})
    row = session.get(EvidenceSnapshotV2Record, before.evidence_snapshot_id)
    row.status = active.status.value
    row.payload_json, row.payload_sha256 = encode_contract(active)
    members = [EvidenceSnapshotMember(member_id="inc-old", snapshot_id="inc-snapshot",
        logical_document_id=old["logical_document_id"], source_document_version_id=old["doc_id"], origin="inherited"),
        EvidenceSnapshotMember(member_id="inc-added", snapshot_id="inc-snapshot",
        logical_document_id=added["logical_document_id"], source_document_version_id=added["doc_id"], origin="added")]
    if retained_only:
        members = members[:1]
    snapshot = snapshots.create_incremental(EvidenceSnapshot(evidence_snapshot_id="inc-snapshot",
        project_id=before.project_id, subject_id=before.subject_id, review_episode_id=before.review_episode_id,
        prior_snapshot_id=before.evidence_snapshot_id, comparison_snapshot_id=before.evidence_snapshot_id,
        upload_mode="incremental", members=members,
        collection_sha256=evidence_snapshot_collection_hash(members=[(item.logical_document_id,
            item.source_document_version_id) for item in members]), status="staged", created_by="test", created_at=NOW))
    complete_repo = CompleteEvidenceProcessingRevisionRepository(session)
    previous, additional = (complete_repo.get(chain["complete_revision_id"]) for chain in (old, added))
    additions = [] if retained_only else [additional]
    metadata_ids = list(previous.metadata_revision_ids)
    if change_metadata:
        from app.storage.evidence_repositories import SourceDocumentMetadataRevisionRepository
        metadata = SourceDocumentMetadataRevisionRepository(session)
        original = metadata.get(metadata_ids[0])
        revised = original.model_copy(update={"metadata_revision_id": "inc-metadata", "revision": original.revision + 1,
            "supersedes_metadata_revision_id": original.metadata_revision_id, "document_type": "另一类资料"})
        metadata.append(revised)
        metadata_ids = [revised.metadata_revision_id]
    manifest = [item.model_copy(update={"entry_id": f"inc-page-{index}", "position": index})
        for index, item in enumerate([*previous.manifest, *(item for row in additions for item in row.manifest)], 1)]
    manifest_sha = evidence_processing_manifest_hash(entries=[(item.source_document_version_id, item.page_number,
        item.original_frame, item.page_artifact_id, item.ocr_page_id, item.status.value) for item in manifest])
    base = EvidenceProcessingRevisionRepository(session).get(old["base_revision_id"]).model_copy(update={
        "evidence_processing_revision_id": "inc-base", "evidence_snapshot_id": snapshot.evidence_snapshot_id,
        "manifest": manifest, "manifest_sha256": manifest_sha})
    EvidenceProcessingRevisionRepository(session).create(base)
    locators = sorted([*previous.locator_ids, *(item for row in additions for item in row.locator_ids)])
    attempt = ProcessingCandidateAttemptManifest(metadata_revision_ids=sorted([*metadata_ids,
        *(item for row in additions for item in row.metadata_revision_ids)]),
        risk_scan_ids=sorted([*previous.risk_scan_ids, *(item for row in additions for item in row.risk_scan_ids)]),
        locator_ids=locators)
    authority = old["authority"]
    candidate_sha = processing_candidate_input_hash(evidence_snapshot_id=snapshot.evidence_snapshot_id,
        base_processing_revision_id=base.evidence_processing_revision_id, expected_revision=authority.episode_revision,
        scanner_rule_version="facts-test/v1", selected_locator_ids=locators, attempt_manifest=attempt)
    candidate = EvidenceProcessingCandidate(candidate_id="inc-producer", evidence_snapshot_id=snapshot.evidence_snapshot_id,
        base_processing_revision_id=base.evidence_processing_revision_id, project_id=authority.project_id,
        subject_id=authority.subject_id, review_episode_id=authority.review_episode_id,
        expected_revision=authority.episode_revision, idempotency_key="inc-key", scanner_rule_version="facts-test/v1",
        selected_locator_ids=locators, attempt_manifest=attempt, candidate_input_sha256=candidate_sha,
        status="staged", created_by="test", created_at=NOW)
    EvidenceProcessingCandidateRepository(session).create(candidate, EvidenceProcessingCandidateEvent(
        candidate_id=candidate.candidate_id, seq=1, from_status="staged", to_status="processing", event_kind="worker_start",
        actor="test", reason="合成增量来源测试", attempt_manifest=attempt, attempt_input_sha256=candidate_sha, created_at=NOW))
    complete = previous.model_copy(update={"evidence_processing_revision_id": "inc-complete",
        "evidence_snapshot_id": snapshot.evidence_snapshot_id, "base_processing_revision_id": base.evidence_processing_revision_id,
        "producer_candidate_id": candidate.candidate_id, "candidate_input_sha256": candidate_sha,
        "manifest": manifest, "manifest_sha256": manifest_sha, "locator_ids": locators,
        "metadata_revision_ids": attempt.metadata_revision_ids, "risk_scan_ids": attempt.risk_scan_ids})
    complete = complete.model_copy(update={"completion_manifest_sha256": complete_repo.manifest_sha256_for(complete)})
    complete_repo.create(complete)
    current = authority.model_copy(update={"evidence_snapshot_v2_id": snapshot.evidence_snapshot_id,
        "complete_processing_revision_id": complete.evidence_processing_revision_id})
    _update_episode(session, session.get(ReviewEpisodeRecord, authority.review_episode_id),
        revision=current.episode_revision, rule_set_revision=current.rule_set_revision,
        active_evidence_snapshot_id=current.evidence_snapshot_v2_id,
        active_evidence_processing_revision_id=current.complete_processing_revision_id)
    return current


def _seed_incremental(session, *, before_incremental=None, change_metadata=False, targeted=False, linked_entities=False, retained_only=False):
    from unittest.mock import patch
    from app.storage.repositories import SubjectRepository, EpisodeRepository
    old = _seed_valid_chain(session, "retained")
    # Shared fixture seed otherwise tries to reinsert this owner's subject.
    # Only that seed setup is reused; all new material goes through repositories.
    with patch.object(SubjectRepository, "save", lambda repo, row: repo.get(row.subject_id)), \
            patch.object(EpisodeRepository, "save", lambda repo, row: repo.get(row.review_episode_id)):
        added = _seed_valid_chain(session, "added")
    _update_episode(session, session.get(ReviewEpisodeRecord, old["authority"].review_episode_id),
        active_evidence_snapshot_id=old["snapshot_id"], active_evidence_processing_revision_id=old["complete_revision_id"])
    if targeted:
        from app.storage.repositories import get_rule_set, save_rule_set
        from app.domain.variables.dictionary import VariableDef
        rules = get_rule_set(session, old["authority"].rule_set_id, 1)
        requirements = [row for rule in rules.rules for component in rule.components for row in component.evidence_requirements]
        assert requirements
        selected = requirements[0].requirement_id
        rules = rules.model_copy(update={"revision": 2,
            "variable_definitions": [VariableDef(variable_id="source_test", label_zh="合成记录", value_type="boolean", domain="history")],
            "rules": [rule.model_copy(update={"components": [component.model_copy(update={
                "evidence_requirements": [row.model_copy(update={"variable_id": "source_test"})
                    if row.requirement_id == selected else row for row in component.evidence_requirements]})
                for component in rule.components]}) for rule in rules.rules]})
        save_rule_set(session, rules)
        old["authority"] = old["authority"].model_copy(update={"episode_revision": 2, "rule_set_revision": 2})
        _update_episode(session, session.get(ReviewEpisodeRecord, old["authority"].review_episode_id), revision=2, rule_set_revision=2)
    else:
        old["authority"] = _variable_rule_revision(session, old, 2)
    fact = _publish_fact(session, old, include_source_candidates=True)
    if linked_entities:
        from app.storage.fact_repositories import FactNormalizationCandidateRepository
        from tests.v2.services.test_patient_profile_service import _event_via_candidate, _exposure_via_candidate
        source = FactNormalizationCandidateRepository(session).get(fact.source_candidate_ids[0])
        source_chain = {**old, "run_id": fact.run_id, "call_id": source.call_id}
        _event_via_candidate(session, source_chain, "retained-event", fact_candidate_ids=fact.source_candidate_ids, fact_ids=[fact.fact_id])
        _exposure_via_candidate(session, source_chain, "retained-exposure", fact_candidate_ids=fact.source_candidate_ids, fact_ids=[fact.fact_id])
    original = PatientProfileService().generate(session, authority=old["authority"])
    if before_incremental:
        before_incremental(old)
    current = _incremental_source(session, old, added, change_metadata=change_metadata, retained_only=retained_only)
    return old, added, current, fact, original


def test_retained_original_fact_is_visible_with_real_new_snapshot_and_exact_source(session):
    from app.domain.contracts.patient_profile_v2 import profile_items
    from app.storage.patient_profile_repository import PatientProfileRevisionRepository
    from app.storage.fact_authority import FactAuthorityValidator
    old, added, current, fact, original = _seed_incremental(session)
    validator = FactAuthorityValidator(session)
    assert validator.retained_source_documents(old["authority"], current) == {old["doc_id"]}
    assert PatientProfileService()._published_facts(session, current) == []
    profile = PatientProfileService().generate(session, authority=current, include_rule_revision_sources=True)
    assert [item.source_id for item in profile_items(profile)] == [fact.fact_id]
    assert PatientProfileService().fact_source_readings(session, profile, fact.fact_id)
    assert PatientProfileService().fact_display_metadata(session, profile)[fact.fact_id]
    assert PatientProfileRevisionRepository(session).get(original.patient_profile_revision_id) == original
    # Added document is not a previous read merely because it is in today's manifest.
    assert not validator.retained_source_documents(added["authority"], current)


@pytest.mark.parametrize("field,value", [("subject_id", "wrong-subject"), ("review_episode_id", "wrong-episode"),
    ("rule_set_id", "wrong-rules")])
def test_retained_source_never_crosses_owner_or_rules(session, field, value):
    from app.storage.fact_authority import FactAuthorityValidator
    old, _, current, _, _ = _seed_incremental(session)
    assert not FactAuthorityValidator(session).retained_source_documents(old["authority"], current.model_copy(update={field: value}))


def test_changed_variables_do_not_relabel_old_records(session):
    from app.storage.fact_authority import FactAuthorityValidator
    old, _, current, fact, _ = _seed_incremental(session)
    changed = _variable_rule_revision(session, {**old, "authority": current}, 3, variable_change=True)
    assert not FactAuthorityValidator(session).retained_fact_source_is_reusable(fact, changed)
    assert PatientProfileService()._published_facts(session, changed, include_rule_revision_sources=True) == []


def test_new_metadata_does_not_reuse_old_classification(session):
    from app.storage.fact_authority import FactAuthorityValidator
    old, _, current, fact, _ = _seed_incremental(session, change_metadata=True)
    assert not FactAuthorityValidator(session).retained_fact_source_is_reusable(fact, current)
    assert PatientProfileService()._published_facts(session, current, include_rule_revision_sources=True) == []


def test_retained_profile_includes_original_linked_history_and_medication(session):
    from app.domain.contracts.patient_profile_v2 import profile_items
    _, _, current, fact, _ = _seed_incremental(session, linked_entities=True)
    profile = PatientProfileService().generate(session, authority=current, include_rule_revision_sources=True)
    assert {row.source_id for row in profile_items(profile)} == {fact.fact_id, "retained-event", "retained-exposure"}


def _receipt_transport_factory(requests, *, fail_after=None):
    """Real product transport and receipts, synthetic model response, no network."""
    import json
    from types import SimpleNamespace
    from app.agents.deepseek_evidence_normalizer_transport import DeepSeekEvidenceNormalizerTransport
    def factory(model, *, receipt_callback, request_callback):
        def complete(**body):
            if fail_after is not None and len(requests) >= fail_after:
                requests.append(["synthetic-transport-failed"])
                raise TimeoutError("synthetic failure on added material")
            prompt = body["messages"][0]["content"]
            payload = json.JSONDecoder().raw_decode(prompt.split("本次输入：", 1)[1])[0]
            locators = payload["locators"]
            if payload.get("locator_columns"):
                locators = [dict(zip(payload["locator_columns"], row)) for row in locators]
            requests.append([row["locator_id"] for row in locators])
            candidates = []
            for index, row in enumerate(locators):
                text = row["localized_text"]
                name = "ALT" if text.startswith("ALT") else "AST"
                candidates.append({"candidate_ref": f"f{index}", "assertion_scope": "observed_state",
                    "fact_type": "检验结果", "profile_lane": "test_exam_score", "polarity": "affirmed",
                    "asserted_object": name, "raw_value": text, "canonical_value": text,
                    "unit": None, "date_range": None, "record_time": None, "variable_id": None,
                    "locator_ids": [row["locator_id"]], "candidate_source_semantics": "同期客观结果",
                    "assertion_basis": {"asserted_object": name, "assertion_text": text,
                        "locator_id": row["locator_id"], "contextual_qualifiers": []}, "model_uncertainty": 0.01})
            answer = json.dumps({"schema_version": "phase5/normalizer-draft/v5", "fact_candidates": candidates,
                "event_candidates": [], "exposure_candidates": [], "actual_exposure_fact_refs": [],
                "non_exposure_medication_fact_refs": [], "unresolved_items": []}, ensure_ascii=False)
            return SimpleNamespace(model=model.model, id="synthetic-response", usage=None,
                choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=answer))])
        return DeepSeekEvidenceNormalizerTransport(backend="omlx", model=model.model,
            client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=complete))),
            receipt_callback=receipt_callback, request_callback=request_callback)
    return factory


@pytest.mark.parametrize("case", ["normal", "other_model", "receipt_damage", "new_page_failed", "cancelled", "all_retained"])
def test_incremental_product_job_reads_only_added_page_and_preserves_saved_sources(session_factory, data_paths, monkeypatch, case):
    from app.evidence.artifacts import ArtifactStore
    from app.services import fact_normalization_executor as executor_module
    from app.services.fact_normalization_job_service import FactNormalizationJobService
    from app.services.fact_normalization_source_adapter import retained_normalization_reads
    from app.workflow.jobstore import JobStore
    from app.workflow.runner import JobRunner
    from app.storage.codecs import verify_payload_sha256
    from app.domain.contracts.patient_profile_v2 import profile_items
    requests, jobs = [], []
    artifacts = ArtifactStore(data_paths)
    prepared_result, causes = executor_module.PreparedStepResult, []
    def observed_result(**kwargs):
        apply = kwargs["apply"]
        def observed_apply(session):
            try:
                return apply(session)
            except Exception as exc:
                causes.append(repr(exc.__cause__ or exc))
                raise
        return prepared_result(**{**kwargs, "apply": observed_apply})
    monkeypatch.setattr(executor_module, "PreparedStepResult", observed_result)
    monkeypatch.setattr(executor_module, "evidence_normalizer_transport_from_model_config",
        _receipt_transport_factory(requests, fail_after=1 if case == "new_page_failed" else None))
    service = FactNormalizationJobService(session_factory)
    runner = JobRunner(session_factory, {"fact_normalization": executor_module.create_fact_normalization_executor(
        executor_module.FactNormalizationExecutorConfig(session_factory=session_factory, artifact_store=artifacts))},
        backoff=lambda _: timedelta(0))
    def read_old(chain):
        session.commit()
        job = service.create_or_reuse_from_source(authority=chain["authority"], prompt_version_id=chain["prompt_version_id"],
            model_config_id=chain["model_config_id"], created_by="synthetic-builder")
        jobs.append(job)
        assert runner.run_job(job.job_id)
        assert service.get_job(job.job_id)["state"] == "completed"
    with session_factory() as session:
        old, added, current, old_fact, original = _seed_incremental(session, before_incremental=read_old,
            targeted=True, retained_only=case == "all_retained")
        session.commit()
        proofs = retained_normalization_reads(session, authority=current, prompt_version_id=old["prompt_version_id"],
            model_config_id=old["model_config_id"], prompt_template=service.prompt_template, artifact_store=artifacts)
        assert len(proofs) == 1
        assert proofs[0]["source_document_version_id"] == old["doc_id"]
        initial = JobStore(session).get_job(jobs[0].job_id)
        initial_identity = (initial.payload_json, initial.payload_sha256, initial.state)
    model_id = old["model_config_id"]
    if case == "receipt_damage":
        from app.evidence.artifacts import ArtifactIntegrityError
        path = data_paths.root / "artifacts" / "raw_request" / proofs[0]["request_artifact_sha256"]
        path.write_bytes(b"synthetic damaged request")
        with pytest.raises(ArtifactIntegrityError):
            service.create_or_reuse_from_source(authority=current, prompt_version_id=old["prompt_version_id"],
                model_config_id=model_id, created_by="synthetic-builder")
        assert len(requests) == 1
        return
    if case == "other_model":
        from app.storage.repositories import AppendRepository, MODEL_CONFIG_CONFIG
        with session_factory() as session, session.begin():
            config = AppendRepository(session, MODEL_CONFIG_CONFIG).get(model_id)
            config = config.model_copy(update={"model_config_id": "new-synthetic-route", "model": "other-synthetic-model"})
            AppendRepository(session, MODEL_CONFIG_CONFIG).save(config)
            model_id = config.model_config_id
    job = service.create_or_reuse_from_source(authority=current, prompt_version_id=old["prompt_version_id"],
        model_config_id=model_id, created_by="synthetic-builder")
    with session_factory() as session:
        payload = verify_payload_sha256(JobStore(session).get_job(job.job_id).payload_json, JobStore(session).get_job(job.job_id).payload_sha256)
        assert [row["logical_document_id"] for row in payload["calls"]] == ([] if case == "all_retained" else [added["logical_document_id"]])
        assert payload["retained_reads"] == proofs
        if case == "cancelled":
            assert JobStore(session).request_cancel(job.job_id).state == "cancelled"
            session.commit()
            assert len(requests) == 1
            return
    assert runner.run_job(job.job_id)
    if case == "new_page_failed":
        assert service.get_job(job.job_id)["state"] == "failed_retryable"
        runner._maintenance()  # Same worker retry admission as the desktop's serve loop.
        assert runner.run_job(job.job_id)
    assert service.get_job(job.job_id)["state"] == "completed", causes
    expected_requests = 1 if case == "all_retained" else 3 if case == "new_page_failed" else 2
    assert len(requests) == expected_requests  # Only the failed new page uses its one retry.
    with session_factory() as session:
        profile = PatientProfileService().latest(session, current.review_episode_id)
        assert profile.authority == current
        ids = {item.source_id for item in profile_items(profile)}
        assert old_fact.fact_id in ids and len(ids) == (3 if case in {"all_retained", "new_page_failed"} else 5)
        assert PatientProfileService().fact_source_readings(session, profile, old_fact.fact_id)
        assert PatientProfileService().fact_display_metadata(session, profile)
        checkpoint = JobStore(session).get_last_checkpoint(job.job_id, "finalize")[1]
        assert checkpoint["unread_page_refs"] == ([f"{added['logical_document_id']}:1"] if case == "new_page_failed" else [])
        queued = JobStore(session).get_job(checkpoint["work_draft_job_id"])
        assert queued.job_type == "work_draft_review" and queued.state == "queued"
        previous = JobStore(session).get_job(jobs[0].job_id)
        assert (previous.payload_json, previous.payload_sha256, previous.state) == initial_identity
    assert service.create_or_reuse_from_source(authority=current, prompt_version_id=old["prompt_version_id"],
        model_config_id=model_id, created_by="synthetic-builder").job_id == job.job_id
    assert len(requests) == expected_requests


def test_success_label_without_original_receipt_cannot_skip_file(session_factory):
    from app.services.fact_normalization_job_service import FactNormalizationJobService
    from app.services.fact_normalization_source_adapter import retained_normalization_reads
    from app.storage.codecs import verify_payload_sha256
    from app.workflow.jobstore import JobStore
    with session_factory() as session:
        old, added, current, _, _ = _seed_incremental(session, targeted=True)
        session.commit()
        service = FactNormalizationJobService(session_factory)
        assert retained_normalization_reads(session, authority=current, prompt_version_id=old["prompt_version_id"],
            model_config_id=old["model_config_id"], prompt_template=service.prompt_template) == []
    job = service.create_or_reuse_from_source(authority=current, prompt_version_id=old["prompt_version_id"],
        model_config_id=old["model_config_id"], created_by="synthetic-builder")
    with session_factory() as session:
        row = JobStore(session).get_job(job.job_id)
        payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
        assert "retained_reads" not in payload
        assert {row["logical_document_id"] for row in payload["calls"]} == {old["logical_document_id"], added["logical_document_id"]}


@pytest.mark.parametrize("linked_entities", [False, True])
def test_fact_can_be_corrected_after_real_source_retention_without_reviving_old_entity(session_factory, linked_entities, monkeypatch):
    from app.services.fact_correction_job_service import FactCorrectionJobService
    from app.services.fact_correction_executor import FactCorrectionExecutorConfig, create_fact_correction_executor
    from app.storage.fact_correction_repository import FactCorrectionRepository
    from app.storage.fact_repositories import ClinicalFactV2Repository
    from app.workflow.runner import JobRunner
    from app.workflow.jobstore import JobStore
    from app.domain.contracts.patient_profile_v2 import profile_items
    from app.services import fact_correction_executor as executor_module
    apply = executor_module.apply_prepared_fact_correction
    causes = []
    def observed_apply(*args, **kwargs):
        try:
            return apply(*args, **kwargs)
        except Exception as exc:
            causes.append(repr(exc.__cause__ or exc))
            raise
    monkeypatch.setattr(executor_module, "apply_prepared_fact_correction", observed_apply)
    with session_factory() as session:
        _, _, current, target, _ = _seed_incremental(session, linked_entities=linked_entities)
        session.commit()
    service = FactCorrectionJobService(session_factory)
    job = service.create_or_reuse_job(authority=current, target_kind="fact", target_id=target.fact_id,
        locator_ids=target.locator_ids, reason="合成原件核对", operator_id="synthetic-builder",
        updates={"value": "130/80"}, created_by="synthetic-builder", created_at=NOW)
    runner = JobRunner(session_factory, {"fact_correction": create_fact_correction_executor(
        FactCorrectionExecutorConfig(session_factory=session_factory))})
    assert runner.run_job(job.job_id)
    with session_factory() as session:
        assert JobStore(session).get_job(job.job_id).state == "completed", causes
        records = FactCorrectionRepository(session).list_by_review_episode(current.review_episode_id)
        assert len(records) == 1
        new = ClinicalFactV2Repository(session).get(records[0].new_entity_id)
        assert new.value == "130/80" and new.authority == current
        assert ClinicalFactV2Repository(session).get(target.fact_id) == target
        items = profile_items(PatientProfileService().latest(session, current.review_episode_id))
        assert {row.source_id for row in items if row.kind.value == "fact"} == {new.fact_id}
        if linked_entities:
            assert len(items) == 3
            assert not {"retained-event", "retained-exposure"} & {row.source_id for row in items}
            from app.storage.fact_repositories import ClinicalEventV2Repository, MedicationExposureV2Repository
            for kind, id_field, repository in (
                ("event", "event_id", ClinicalEventV2Repository),
                ("exposure", "exposure_id", MedicationExposureV2Repository),
            ):
                entities = repository(session).list_by_episode(current.review_episode_id)
                prior = next(row for row in entities if getattr(row, id_field) == f"retained-{kind}")
                successor = next(row for row in entities if row.authority == current)
                assert PatientProfileService._cascade_source_ids(session, [prior, successor], kind, id_field) == {getattr(prior, id_field)}
                # Same page or wording cannot stand in for the actual correction dependency.
                for changed in (
                    {"source_candidate_ids": ["another-reading"]},
                    {"gate_ids": ["another-gate"], "gate_id": "another-gate"},
                    {"fact_ids": prior.fact_ids},
                    {"locator_ids": ["another-location"]},
                ):
                    unrelated = successor.model_copy(update=changed)
                    assert not PatientProfileService._cascade_source_ids(session, [prior, unrelated], kind, id_field)
