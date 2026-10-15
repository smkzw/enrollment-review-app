from __future__ import annotations

import json

import pytest

from app.services.page_review_job_service import PageReviewJobService, page_review_steps
from app.storage.models import JobRecord
from app.storage.repositories import EpisodeRepository
from app.workflow.errors import InvalidJobDefinitionError
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.services.test_page_review_execution import _routes


def test_page_steps_require_two_main_reads_before_reconciliation_and_coverage():
    steps = {step.step_id: step for step in page_review_steps(2)}
    assert steps["reconcile:0"].depends_on == ("read:0:main-A", "read:0:main-B")
    assert steps["reconcile:1"].depends_on == ("read:1:main-A", "read:1:main-B")
    assert steps["coverage"].depends_on == ("reconcile:0", "reconcile:1")
    with pytest.raises(InvalidJobDefinitionError):
        page_review_steps(0)


def test_enqueue_freezes_authoritative_pages_and_never_credentials(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="r3-plan")
    service = PageReviewJobService(session_factory)
    kwargs = dict(subject_id=chain["subject_id"], review_episode_id=chain["episode_id"], routes=_routes())
    first = service.enqueue(**kwargs)
    again = service.enqueue(**kwargs)
    assert first.created and not again.created
    assert first.job_id == again.job_id
    with session_factory() as session:
        payload = json.loads(session.get(JobRecord, first.job_id).payload_json)
        episode = EpisodeRepository(session).get(chain["episode_id"])
    assert payload["review_context"] == {
        "review_episode_id": episode.review_episode_id,
        "episode_revision": episode.revision,
        "stage": episode.stage.value,
        "workflow_stage_id": episode.workflow_stage_id,
        "anchor_dates": episode.model_dump(mode="json")["anchor_dates"],
    }
    assert [page["page_artifact_id"] for page in payload["pages"]] == [chain["page_artifact_id"]]
    assert payload["authority"]["complete_processing_revision_id"] == chain["complete_revision_id"]
    assert payload["clause_pack"]["rule_set_id"] == chain["authority"].rule_set_id
    assert all("api_key" not in route for route in payload["routes"].values())


def test_enqueue_rejects_subject_mismatch(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="r3-plan-scope")
    with pytest.raises(InvalidJobDefinitionError, match="不一致"):
        PageReviewJobService(session_factory).enqueue(
            subject_id="other-subject", review_episode_id=chain["episode_id"], routes=_routes())
