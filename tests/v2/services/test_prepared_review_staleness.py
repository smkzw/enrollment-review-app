"""病史更新后，旧审核准备记录必须失效。"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.services import prepared_review_intake, prepared_review_workflow
from app.services.frozen_review_calculation import EVALUATOR_VERSION
from app.services.review_runtime_ownership import OWNER, WORKFLOW_JOB_TYPE
from app.storage.repositories import ScopeViolationError


class _ContextRepository:
    evaluator_version = EVALUATOR_VERSION
    requirements_scope_version = "review-requirements-scope/v1"
    def __init__(self, _session):
        pass

    def get(self, context_id):
        return SimpleNamespace(
            context_id=context_id,
            context_sha256="context-sha",
            evaluator_version=self.evaluator_version,
            requirements_scope_version=self.requirements_scope_version,
            clause_pack=SimpleNamespace(control_publication=None),
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

    with pytest.raises(ScopeViolationError, match="当前病史.*已经更新"):
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
    monkeypatch.setattr(prepared_review_workflow, "FactAuthorityValidator", _AuthorityValidator)
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

    with pytest.raises(ScopeViolationError, match="当前病史.*已经更新"):
        prepared_review_workflow.PreparedReviewContinuation._material(
            object(), "workflow-1"
        )


@pytest.mark.parametrize("old_field", [None, "evaluator_version", "requirements_scope_version"])
def test_review_method_checked_before_new_work(monkeypatch, old_field):
    module = prepared_review_intake
    monkeypatch.setattr(module, "ReviewContextV2Repository", _ContextRepository)
    if old_field:
        monkeypatch.setattr(_ContextRepository, old_field, "old-version")
    monkeypatch.setattr(module, "FactAuthorityValidator", _AuthorityValidator)
    monkeypatch.setattr(module, "current_review_clinical_material_sha256", lambda *_: "unchanged")
    monkeypatch.setattr(module, "frozen_review_clinical_material_sha256", lambda *_: "unchanged")
    def enter():
        return module.require_prepared_review_intent(_session_factory, subject_id="subject-1",
            review_episode_id="episode-1", context_id="context-1", kind="predicate_candidates")
    if old_field:
        with pytest.raises(ScopeViolationError, match="审核方式已更新.*重新准备"):
            enter()
    else:
        assert enter().context_id == "context-1"


@pytest.mark.parametrize("entry", ["retry_command", "retry_runtime", "cancel", "scope_read"])
def test_old_method_can_be_read_or_cancelled_but_not_retried(monkeypatch, entry):
    from app.services.page_review_runtime import PageReviewRuntime
    from app.services.evidence_app_errors import EvidenceAppError

    context = _ContextRepository(None).get("context-1")
    context.evaluator_version = "old-version"
    row = SimpleNamespace(payload_json={}, payload_sha256="sha")
    result = SimpleNamespace(state="cancel_requested")
    monkeypatch.setattr(prepared_review_workflow.PreparedReviewContinuation, "_material",
                        lambda *_: (row, {}, context))
    monkeypatch.setattr(prepared_review_workflow.PreparedReviewContinuation, "_cancel_owned", lambda *_: None)
    monkeypatch.setattr(prepared_review_workflow, "JobStore",
                        lambda _: SimpleNamespace(request_cancel=lambda _: result))
    monkeypatch.setattr(prepared_review_workflow.PreparedReviewContinuation, "_children",
                        lambda *_: pytest.fail("旧方法重试不得进入子任务"))
    @contextmanager
    def transactional_factory():
        @contextmanager
        def begin():
            yield
        yield SimpleNamespace(begin=begin)
    kwargs = dict(subject_id="subject-1", review_episode_id="episode-1", workflow_id="workflow-1")
    if entry == "scope_read":
        assert prepared_review_workflow.require_workflow_scope(object(), **kwargs)[2] is context
    elif entry == "cancel":
        assert prepared_review_workflow.change_review_workflow(transactional_factory,
            **kwargs, operation="cancel") is result
    elif entry == "retry_command":
        with pytest.raises(ScopeViolationError, match="审核方式已更新"):
            prepared_review_workflow.change_review_workflow(transactional_factory, **kwargs, operation="retry")
    else:
        runtime = PageReviewRuntime(transactional_factory, None)
        monkeypatch.setattr(runtime, "_prepare", lambda: pytest.fail("旧方法不得初始化模型"))
        with pytest.raises(EvidenceAppError, match="审核方式已更新"):
            runtime.retry_review_workflow(**kwargs)


def test_old_method_continuation_preserves_success_and_records_failure_before_scheduling(
    session_factory, monkeypatch,
):
    from app.services.job_service import JobService, StepSpec
    from app.workflow.jobstore import JobStore

    context = _ContextRepository(None).get("context-1")
    context.evaluator_version = "old-version"
    job = JobService(session_factory).create_job(job_type=WORKFLOW_JOB_TYPE,
        idempotency_key="old-method-continuation", payload={"execution_owner": OWNER},
        steps=[StepSpec("candidates", "核对来源"),
               StepSpec("verification", "核对含义", depends_on=("candidates",)),
               StepSpec("ready", "汇集结果", depends_on=("verification",))])
    with session_factory() as session, session.begin():
        store = JobStore(session)
        lease = store.claim_job(job.job_id, "synthetic-owner")
        store.start_step(lease, "candidates")
        store.complete_step(lease, "candidates", checkpoint_payload={"children": {}})
        previous = store.get_last_checkpoint(job.job_id, "candidates")
        store.release_deferred(lease)
    with session_factory() as session, session.begin():
        lease = JobStore(session).claim_job(job.job_id, "synthetic-owner")
    continuation = prepared_review_workflow.PreparedReviewContinuation(
        session_factory, None, lambda: {}, worker_id="synthetic-owner")
    monkeypatch.setattr(continuation, "_material", lambda *_: (None, {}, context))
    monkeypatch.setattr(prepared_review_workflow, "require_current_review_tasks", lambda *_: None)
    monkeypatch.setattr(continuation, "_cancel_owned", lambda *_: None)
    monkeypatch.setattr(continuation, "_schedule", lambda *_: pytest.fail("旧方式不能继续读取"))
    continuation._advance([lease])
    with session_factory() as session:
        store = JobStore(session)
        assert store.get_job(job.job_id).state == "failed_final"
        steps = {step.step_id: step for step in store.list_steps(job.job_id)}
        assert steps["candidates"].state == "completed"
        assert steps["verification"].error_code == "PREPARED_REVIEW_CONTINUATION_FAILED"
        assert store.get_last_checkpoint(job.job_id, "candidates") == previous
        assert store.get_last_checkpoint(job.job_id, "ready") is None


@pytest.mark.parametrize("old_field", ["evaluator_version", "requirements_scope_version"])
def test_same_workflow_contract_with_old_method_is_not_recalculated_or_borrowed(monkeypatch, old_field):
    from app.services import eligibility_review_projection as projection, review_context_assembly
    from app.storage import review_context_repository, codecs

    authority = SimpleNamespace(review_episode_id="synthetic-episode")
    frozen = SimpleNamespace(authority=authority, evaluator_version=EVALUATOR_VERSION,
                             requirements_scope_version="review-requirements-scope/v1")
    setattr(frozen, old_field, "old-version")
    class Session:
        calls = 0
        def scalars(self, _statement):
            self.calls += 1
            if self.calls == 1:
                return [SimpleNamespace(context_id="context-1")]
            return [SimpleNamespace(payload_json="old", payload_sha256="old-sha", state="completed"),
                    SimpleNamespace(payload_json="older", payload_sha256="older-sha", state="completed")]
    reads = []
    def read_payload(body, _sha):
        reads.append(body)
        assert body == "old", "不能借用更早完成的结果"
        return {"review_context_id": "context-1", "contract": prepared_review_workflow.CONTRACT}
    monkeypatch.setattr(codecs, "verify_payload_sha256", read_payload)
    monkeypatch.setattr(review_context_repository, "ReviewContextV2Repository",
                        lambda _: SimpleNamespace(get=lambda _: frozen))
    monkeypatch.setattr(review_context_assembly, "current_review_clinical_material_sha256", lambda *_: "same")
    monkeypatch.setattr(review_context_assembly, "frozen_review_clinical_material_sha256", lambda *_: "same")
    monkeypatch.setattr(prepared_review_workflow, "require_current_review_tasks",
                        lambda *_: pytest.fail("旧核对方法不能进入当前工作稿消费者"))
    assert projection.EligibilityReviewProjectionService(artifact_store=object())._completed_work_draft(
        Session(), authority=authority, rule_set=object()) is projection._STALE_METHOD_WORK_DRAFT
    assert reads == ["old"]


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


def test_old_method_draft_does_not_break_current_page_or_borrow_older_result(monkeypatch):
    from app.services import eligibility_review_projection as projection
    from app.services import review_context_assembly
    from app.storage import review_context_repository, codecs

    authority = SimpleNamespace(review_episode_id="synthetic-episode")
    frozen = SimpleNamespace(authority=authority)
    class Session:
        calls = 0
        def scalars(self, _statement):
            self.calls += 1
            if self.calls == 1:
                return [SimpleNamespace(context_id="context-1")]
            return [SimpleNamespace(payload_json="old", payload_sha256="old-sha", state="completed"),
                    SimpleNamespace(payload_json="older", payload_sha256="older-sha", state="completed")]
    reads = []
    def read_payload(body, _sha):
        reads.append(body)
        assert body == "old", "不能借用更早完成的结果"
        return {"review_context_id": "context-1", "contract": "prepared-review-workflow/v7"}
    monkeypatch.setattr(codecs, "verify_payload_sha256", read_payload)
    monkeypatch.setattr(review_context_repository, "ReviewContextV2Repository",
                        lambda _session: SimpleNamespace(get=lambda _id: frozen))
    monkeypatch.setattr(review_context_assembly, "current_review_clinical_material_sha256", lambda *_: "same")
    monkeypatch.setattr(review_context_assembly, "frozen_review_clinical_material_sha256", lambda *_: "same")
    monkeypatch.setattr(prepared_review_workflow, "require_current_review_tasks",
                        lambda *_: pytest.fail("旧方式不应进入当前结果消费"))
    assert projection.EligibilityReviewProjectionService(artifact_store=object())._completed_work_draft(
        Session(), authority=authority, rule_set=object()) is None
    assert reads == ["old"]
