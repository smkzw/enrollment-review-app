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


@pytest.mark.parametrize(
    ("job_state", "material_changed", "expected_stale"),
    [("completed", True, True), ("running", True, False),
     ("running", False, False), ("failed_final", False, False)],
)
def test_read_projection_marks_only_completed_old_work_draft_stale(
    monkeypatch, job_state, material_changed, expected_stale,
):
    from app.services import eligibility_review_projection as projection_module
    from app.services import review_context_assembly
    from app.storage import review_context_repository

    authority = SimpleNamespace(review_episode_id="episode-1")
    frozen = SimpleNamespace(authority=authority)
    class _Session:
        def __init__(self):
            self.calls = 0

        def scalars(self, _statement):
            self.calls += 1
            if self.calls == 1:
                return [SimpleNamespace(context_id="context-1")]
            return [SimpleNamespace(
                job_type=WORKFLOW_JOB_TYPE, payload_json={}, payload_sha256="sha",
                state=job_state, job_id="job-1",
            )]

    monkeypatch.setattr(
        review_context_repository, "ReviewContextV2Repository",
        lambda _session: SimpleNamespace(get=lambda _id: frozen),
    )
    monkeypatch.setattr(
        review_context_assembly, "current_review_clinical_material_sha256",
        lambda _session, _authority: "current",
    )
    monkeypatch.setattr(
        review_context_assembly, "frozen_review_clinical_material_sha256",
        lambda _context: "old" if material_changed else "current",
    )
    from app.storage import codecs
    monkeypatch.setattr(codecs, "verify_payload_sha256", lambda _payload, _sha: {
        "review_context_id": "context-1",
    })
    monkeypatch.setattr(
        prepared_review_workflow, "require_current_review_tasks",
        lambda _payload: pytest.fail("旧资料或未完成任务不得当作当前工作稿核验"),
    )
    result = projection_module.EligibilityReviewProjectionService(
        artifact_store=object(),
    )._completed_work_draft(_Session(), authority=authority, rule_set=object())
    assert (result is projection_module._STALE_WORK_DRAFT) is expected_stale
