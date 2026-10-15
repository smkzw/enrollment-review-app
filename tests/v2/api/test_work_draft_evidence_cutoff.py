"""Declared same-node source range is independent of the protocol's time anchor."""
from datetime import date

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import AnchorType, DatePrecision
from app.storage.repositories import EpisodeRepository
from app.workflow.jobstore import JobStore
from tests.v2.storage.test_fact_correction_repository import _seed_valid_chain


def test_cutoff_roundtrip_preserves_anchor_and_rejects_stale_or_early_change(client):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_valid_chain(session, "cutoff-source")
        repository = EpisodeRepository(session)
        episode = repository.get(chain["review_episode_id"])
        episode = repository.update(episode.review_episode_id, episode.revision, {"anchor_dates": {
            AnchorType.SCREENING_DATE: DateValue(value=date(2025, 8, 8), precision=DatePrecision.DAY)}})
        original = episode.model_dump(mode="json")
        assert "evidence_cutoff_date" not in original
    endpoint = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{episode.review_episode_id}/evidence-cutoff"
    body = {"evidence_cutoff_date": "2025-08-15", "expected_revision": episode.revision}
    saved = client.put(endpoint, json=body)
    assert saved.status_code == 200, saved.text
    revision = saved.json()["revision"]
    assert revision == episode.revision + 1
    with factory() as session:
        updated = EpisodeRepository(session).get(episode.review_episode_id)
        assert updated.evidence_cutoff_date == date(2025, 8, 15)
        assert updated.anchor_dates == episode.anchor_dates
    listing = client.get(f"/api/v2/subjects/{chain['subject_id']}/review-episodes")
    assert listing.status_code == 200, listing.text
    assert next(row for row in listing.json()["items"] if row["review_episode_id"] == episode.review_episode_id)["evidence_cutoff_date"] == "2025-08-15"
    assert client.put(endpoint, json=body).status_code == 409
    assert client.put(endpoint, json={**body, "expected_revision": revision, "evidence_cutoff_date": "2025-08-07"}).status_code in {409, 422}
    with factory() as session, session.begin():
        JobStore(session).create_job(job_id="active-cutoff-job", job_type="fact_correction",
            payload={"review_episode_id": episode.review_episode_id}, progress_total=1)
    assert client.put(endpoint, json={**body, "expected_revision": revision, "evidence_cutoff_date": "2025-08-16"}).status_code == 409
    with factory() as session:
        assert EpisodeRepository(session).get(episode.review_episode_id) == updated
