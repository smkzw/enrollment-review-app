"""病史更新后，旧审核准备记录必须失效。"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.services import prepared_review_intake, prepared_review_workflow
from app.services.review_runtime_ownership import OWNER, WORKFLOW_JOB_TYPE
from app.storage.repositories import ScopeViolationError


class _ContextRepository:
    def __init__(self, _session):
        pass

    def get(self, context_id):
        return SimpleNamespace(
            context_id=context_id,
            context_sha256="context-sha",
            authority=SimpleNamespace(
                subject_id="subject-1",
                review_episode_id="episode-1",
            ),
        )


class _AuthorityValidator:
    def __init__(self, _session):
        pass

    def validate(self, _authority):
        return None


@contextmanager
def _session_factory():
    yield object()


def test_updated_clinical_material_rejects_new_step_from_old_context(monkeypatch):
    monkeypatch.setattr(prepared_review_intake, "ReviewContextV2Repository", _ContextRepository)
    monkeypatch.setattr(prepared_review_intake, "FactAuthorityValidator", _AuthorityValidator)
    monkeypatch.setattr(
        prepared_review_intake,
        "current_review_clinical_material_sha256",
        lambda _session, _authority: "current-material",
    )
    monkeypatch.setattr(
        prepared_review_intake,
        "frozen_review_clinical_material_sha256",
        lambda _context: "frozen-material",
    )

    with pytest.raises(ScopeViolationError, match="当前病史已经更新"):
        prepared_review_intake.require_prepared_review_intent(
            _session_factory,
            subject_id="subject-1",
            review_episode_id="episode-1",
            context_id="context-1",
            kind="predicate_candidates",
        )


def test_updated_clinical_material_rejects_resuming_old_workflow(monkeypatch):
    job = SimpleNamespace(
        job_type=WORKFLOW_JOB_TYPE,
        payload_json={},
        payload_sha256="payload-sha",
    )
    monkeypatch.setattr(
        prepared_review_workflow,
        "JobStore",
        lambda _session: SimpleNamespace(get_job=lambda _workflow_id: job),
    )
    monkeypatch.setattr(
        prepared_review_workflow,
        "verify_payload_sha256",
        lambda _payload, _sha: {
            "contract": prepared_review_workflow.CONTRACT,
            "execution_owner": OWNER,
            "review_context_id": "context-1",
            "review_context_sha256": "context-sha",
        },
    )
    monkeypatch.setattr(prepared_review_workflow, "ReviewContextV2Repository", _ContextRepository)
    monkeypatch.setattr(
        prepared_review_workflow,
        "current_review_clinical_material_sha256",
        lambda _session, _authority: "current-material",
    )
    monkeypatch.setattr(
        prepared_review_workflow,
        "frozen_review_clinical_material_sha256",
        lambda _context: "frozen-material",
    )

    with pytest.raises(ScopeViolationError, match="当前病史已经更新"):
        prepared_review_workflow.PreparedReviewContinuation._material(
            object(), "workflow-1"
        )
