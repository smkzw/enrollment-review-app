import pytest

from app.domain.contracts.evidence_normalizer import EvidenceNormalizerOutput, EvidenceNormalizerUnresolvedItem
from app.services.fact_normalization_executor import FactNormalizationExecutorConfig, create_fact_normalization_executor
from app.services.fact_normalization_job_service import FactNormalizationJobService
from app.storage.fact_repositories import FactNormalizationUnresolvedItemRepository
from app.storage.models import JobRecord
from app.storage.codecs import verify_payload_sha256
from app.workflow.runner import JobRunner
from tests.v2.services.test_fact_normalization_persistence import _seed_chain


def create(factory, chain, *, accounting):
    return FactNormalizationJobService(factory).create_or_reuse_from_source(
        authority=chain["authority"], prompt_version_id=chain["prompt_version_id"],
        model_config_id=chain["model_config_id"], created_by="test",
        account_source_text=accounting)


def test_new_accounting_has_distinct_identity_and_recovery_preserves_issues(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="text-accounting")
    legacy = create(session_factory, chain, accounting=False)
    current = create(session_factory, chain, accounting=True)
    assert current.run_id != legacy.run_id
    from app.workflow.errors import InvalidJobDefinitionError
    with pytest.raises(InvalidJobDefinitionError):
        FactNormalizationJobService(session_factory).create_or_reuse_from_source(
            authority=chain["authority"], prompt_version_id=chain["prompt_version_id"],
            model_config_id=chain["model_config_id"], created_by="test",
            account_source_text=True, page_review_coverage_id="not-a-text-result")
    calls = []

    def transport(evidence):
        calls.append(evidence.call_id)
        return EvidenceNormalizerOutput(run_id=evidence.run_id, call_id=evidence.call_id,
            logical_document_id=evidence.logical_document_id, page_numbers=evidence.page_numbers,
            unresolved_items=[EvidenceNormalizerUnresolvedItem(code="reading_uncertain",
                message="原文需要进一步核对。", reason="不补写检查结果。", affected_pages=evidence.page_numbers)])

    runner = JobRunner(session_factory, {"fact_normalization": create_fact_normalization_executor(
        FactNormalizationExecutorConfig(session_factory=session_factory, transport_fn=transport))}, worker_id="text-test")
    assert runner.run_job(current.job_id)
    with session_factory() as session:
        saved = FactNormalizationUnresolvedItemRepository(session).list_by_run(current.run_id)
        assert len(saved) > 1
        assert any(item.item.source_text_range for item in saved)
        hashes = [item.model_dump(mode="json") for item in saved]
        legacy_payload = verify_payload_sha256(session.get(JobRecord, legacy.job_id).payload_json,
                                               session.get(JobRecord, legacy.job_id).payload_sha256)
        assert "text_accounting_policy" not in legacy_payload
    assert create(session_factory, chain, accounting=True).job_id == current.job_id
    assert not runner.run_job(current.job_id)
    with session_factory() as session:
        assert [item.model_dump(mode="json") for item in
                FactNormalizationUnresolvedItemRepository(session).list_by_run(current.run_id)] == hashes
    assert len(calls) == 1


def test_replay_rejects_missing_remainder_and_unknown_policy(session_factory):
    from sqlalchemy import select, delete
    from app.storage.facts_models import FactNormalizationUnresolvedItemRecord
    from app.storage.fact_repositories import FactNormalizationCallRepository
    from app.services.fact_normalization_executor import _validate_saved_text_accounting
    from app.workflow.errors import StepFailure

    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="text-accounting-replay")
    current = create(session_factory, chain, accounting=True)
    def transport(evidence):
        return EvidenceNormalizerOutput(run_id=evidence.run_id, call_id=evidence.call_id,
            logical_document_id=evidence.logical_document_id, page_numbers=evidence.page_numbers,
            unresolved_items=[EvidenceNormalizerUnresolvedItem(code="reading_uncertain",
                message="待核对", reason="原文保留", affected_pages=evidence.page_numbers)])
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, transport_fn=transport))
    assert JobRunner(session_factory, {"fact_normalization": executor}, worker_id="replay-test").run_job(current.job_id)
    with session_factory() as session, session.begin():
        job = session.get(JobRecord, current.job_id)
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        rows = session.execute(select(FactNormalizationUnresolvedItemRecord).where(
            FactNormalizationUnresolvedItemRecord.run_id == current.run_id,
            FactNormalizationUnresolvedItemRecord.code == "source_text_not_accounted")).scalars().all()
        session.execute(delete(FactNormalizationUnresolvedItemRecord).where(
            FactNormalizationUnresolvedItemRecord.unresolved_item_id == rows[0].unresolved_item_id))
        with pytest.raises(StepFailure, match="核对"):
            _validate_saved_text_accounting(session, payload, chain["authority"], current.run_id,
                FactNormalizationCallRepository(session).list_by_run(current.run_id))
    from app.workflow.runner import StepContext
    payload["text_accounting_policy"] = "normalizer-text-accounting/unsupported"
    with pytest.raises(StepFailure) as exc:
        executor(StepContext(job_id=current.job_id, job_type="fact_normalization",
            job_payload=payload, step_id="finalize", name="test", attempt=1,
            last_checkpoint_id=None, last_checkpoint=None, max_attempts=1))
    assert exc.value.error_code == "NORMALIZATION_POLICY_INVALID"


def _exercise_api_paginated_issues(client):
    from app.storage.models import ReviewEpisodeRecord
    from tests.v2.storage.test_fact_repositories import _update_episode

    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="text-accounting-api")
    current = create(factory, chain, accounting=False)
    path = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['episode_id']}/fact-normalization-jobs/{current.job_id}/unresolved"
    assert client.get(path).status_code == 409
    def transport(evidence):
        return EvidenceNormalizerOutput(run_id=evidence.run_id, call_id=evidence.call_id,
            logical_document_id=evidence.logical_document_id, page_numbers=evidence.page_numbers,
            unresolved_items=[EvidenceNormalizerUnresolvedItem(code="reading_uncertain",
                message=f"第{index}项待核对", reason="原件已保留", affected_pages=evidence.page_numbers)
                for index in range(250)])
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=factory, transport_fn=transport))
    assert JobRunner(factory, {"fact_normalization": executor}, worker_id="api-test").run_job(current.job_id)
    all_items = []
    content_sha256 = None
    for offset in range(0, 250, 50):
        params = {"offset": offset, "limit": 50}
        if content_sha256 is not None:
            params["expected_content_sha256"] = content_sha256
        response = client.get(path, params=params)
        assert response.status_code == 200, response.text
        body = response.json()
        content_sha256 = body["content_sha256"]
        assert body["total"] == 250 and body["is_current"]
        assert body["text_accounting_applied"] is False
        assert body["has_more"] == (offset < 200)
        all_items.extend(body["items"])
    assert len({item["item_id"] for item in all_items}) == 250
    assert all(item["kind"] == "reading_uncertainty" for item in all_items)
    assert client.get(path, params={"offset": 50}).status_code == 409
    assert client.get(path, params={"offset": 50, "expected_content_sha256": "0" * 64}).status_code == 409
    assert all(item["sources"][0]["source_document_version_id"] == chain["doc_id"] for item in all_items)
    with factory() as session, session.begin():
        episode = session.get(ReviewEpisodeRecord, chain["episode_id"])
        _update_episode(session, episode, active_evidence_processing_revision_id=None,
                        active_evidence_snapshot_id=None)
    assert client.get(path).json()["is_current"] is False
    assert client.get(path.replace(chain["subject_id"], "not-the-subject", 1)).status_code == 404
    assert client.get(path, params={"limit": 201}).status_code == 422
