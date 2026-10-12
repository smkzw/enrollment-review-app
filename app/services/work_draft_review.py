"""One durable work-draft job consumes the frozen input; no clinical signature."""
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.domain.contracts.review import ReviewRun
from app.domain.contracts.work_draft import SystemIssue, WorkDraftEvidenceRef, WorkDraftItem
from app.domain.publication import canonical_hash
from app.graph.subject_graph import work_draft_steps
from app.services.fact_normalization_command_service import authority_from_active_episode
from app.services.review_preparation_command import prepare_review
from app.services.work_draft_calculation import calculate_work_component, calculate_procedures, compose_parent
from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
from app.storage.idempotency import IdempotencyRepository
from app.storage.models import ReviewRunRecord
from app.storage.repositories import AppendRepository, REVIEW_RUN_CONFIG, ScopeViolationError, get_rule_set
from app.storage.review_context_repository import ReviewContextV2Repository
from app.storage.work_draft_repository import WorkDraftRepository
from app.workflow.jobstore import JobStore
from app.workflow.runner import PreparedStepResult

JOB_TYPE = "work_draft_review"
CALCULATION_VERSION = "work-draft/0.2.0-v12"


def enqueue_normalized_work_draft(session, *, authority, run_id):
    """Queue only: an unavailable review consumer cannot undo successful fact publication."""
    key = canonical_hash({"normalization_run_id": run_id, "authority": authority.model_dump(mode="json"),
                          "calculation_version": CALCULATION_VERSION})
    receipt, created = IdempotencyRepository(session).resolve(scope="automatic-work-draft",
        idempotency_key=key, submitted_hash=key, result_type="work_draft_job", result_id=uuid4().hex)
    if created:
        store = JobStore(session)
        store.create_job(job_id=receipt.result_id, job_type=JOB_TYPE, progress_total=4,
            payload={"normalization_run_id": run_id, "authority": authority.model_dump(mode="json"),
                     "subject_id": authority.subject_id, "review_episode_id": authority.review_episode_id,
                     "calculation_version": CALCULATION_VERSION})
        for step, depends_on in work_draft_steps():
            store.create_step(job_id=receipt.result_id, step_id=step,
                name={"calculate": "核对确定性条件", "semantic": "登记待核实判断",
                      "compose": "合并条款结果", "save": "保存工作稿"}[step], depends_on=depends_on)
    return {"job_id": receipt.result_id}


def _fact_refs(session, frozen, artifact_store=None):
    repo = EvidenceLocatorRepository(session)
    from app.domain.gates.fact_evidence_closure import _localized_locator_text
    from app.storage.fact_authority import FactAuthorityValidator
    revision = FactAuthorityValidator(session, artifact_store).validate_frozen_source(frozen.authority)
    result = {}
    for fact in frozen.facts:
        refs = []
        primary_failed = False
        for locator_id in fact.locator_ids:
            locator = repo.get(locator_id)
            localized = _localized_locator_text(session, locator, revision)
            excerpt = (fact.assertion_basis.assertion_text if fact.assertion_basis is not None
                and fact.assertion_basis.locator_id == locator_id else localized)
            if localized is None and (fact.assertion_basis is None or fact.assertion_basis.locator_id != locator_id):
                continue
            if not excerpt or localized is None or excerpt not in localized:
                if fact.assertion_basis is not None and fact.assertion_basis.locator_id == locator_id:
                    primary_failed = True
                continue
            refs.append(WorkDraftEvidenceRef(fact_id=fact.fact_id, locator_id=locator_id,
                source_document_version_id=locator.source_document_version_id,
                page_artifact_id=locator.page_artifact_id, page_number=locator.page_number, excerpt=excerpt))
        if refs and not primary_failed:
            result[fact.fact_id] = refs
    return result


class WorkDraftReviewService:
    def __init__(self, session_factory, artifact_store):
        self.session_factory, self.artifact_store = session_factory, artifact_store

    def start(self, *, subject_id, review_episode_id, session=None):
        if session is None:
            with self.session_factory() as session, session.begin():
                return self.start(subject_id=subject_id, review_episode_id=review_episode_id, session=session)
        with session.begin_nested():
            from app.storage.repositories import EpisodeRepository, get_project_row
            episode = EpisodeRepository(session).get(review_episode_id)
            if episode.subject_id != subject_id:
                raise ScopeViolationError("审核节点不属于所选受试者")
            from app.storage.models import JobRecord
            from app.storage.codecs import verify_payload_sha256
            project, revision = get_project_row(session, episode.project_id)
            if (episode.protocol_version_id, episode.rule_set_id, episode.rule_set_revision) != (
                    project.protocol_version.protocol_version_id, project.rule_set_id, revision):
                for job in session.scalars(select(JobRecord).where(
                        JobRecord.job_type.in_({"fact_normalization", JOB_TYPE}),
                        JobRecord.state.in_({"queued", "running", "failed_retryable"}))):
                    data = verify_payload_sha256(job.payload_json, job.payload_sha256)
                    owner = data.get("review_episode_id") or (data.get("authority") or {}).get("review_episode_id")
                    if owner == review_episode_id:
                        raise ScopeViolationError("当前资料或工作稿正在整理，请完成后更新；已有结果会保留。")
            EpisodeRepository(session).adopt_published_rule_set(review_episode_id, episode.revision)
            authority = authority_from_active_episode(session, review_episode_id)
            if authority.subject_id != subject_id:
                raise ScopeViolationError("审核节点不属于所选受试者")
            from app.storage.fact_repositories import FactNormalizationRunRepository
            running = [run for run in FactNormalizationRunRepository(session).list_by_episode(review_episode_id)
                       if run.authority == authority and run.status.value in {"created", "queued", "running"}]
            if running:
                raise ScopeViolationError("当前资料仍在整理，请完成后生成工作稿；已有读取结果会保留。")
            from app.services.review_context_assembly import assemble_review_context
            preview = assemble_review_context(session, self.artifact_store, review_episode_id=review_episode_id,
                review_run_id="pending", evaluator_version=CALCULATION_VERSION,
                created_at=datetime.now(UTC), work_draft=True)
            identity = canonical_hash({"authority": authority.model_dump(mode="json"),
                "rule_set_sha256": preview.rule_set_sha256,
                "clinical_facts": [item.model_dump(mode="json") for item in preview.facts],
                "system_issues": [item.model_dump(mode="json") for item in preview.system_issues],
                "source_pages": [item.model_dump(mode="json") for item in preview.source_pages],
                "calculation_version": CALCULATION_VERSION})
            receipt, created = IdempotencyRepository(session).resolve(scope=f"work-draft:{review_episode_id}",
                idempotency_key=identity, submitted_hash=identity, result_type="work_draft_job", result_id=uuid4().hex)
            store = JobStore(session)
            if created:
                frozen = prepare_review(session, self.artifact_store, subject_id=subject_id,
                    review_episode_id=review_episode_id, expected_authority=authority,
                    idempotency_key=identity, work_draft=True, evaluator_version=CALCULATION_VERSION)
                store.create_job(job_id=receipt.result_id, job_type=JOB_TYPE,
                    payload={"context_id": frozen.context_id, "review_run_id": frozen.review_run_id,
                             "review_episode_id": review_episode_id, "subject_id": subject_id,
                             "calculation_version": CALCULATION_VERSION, "input_hash": identity}, progress_total=4)
                for step, depends_on in work_draft_steps():
                    store.create_step(job_id=receipt.result_id, step_id=step,
                        name={"calculate": "核对确定性条件", "semantic": "登记待核实判断",
                              "compose": "合并条款结果", "save": "保存工作稿"}[step], depends_on=depends_on)
            return self.status(subject_id=subject_id, review_episode_id=review_episode_id,
                               job_id=receipt.result_id, session=session)

    def status(self, *, subject_id, review_episode_id, job_id, session=None):
        if session is None:
            with self.session_factory() as session:
                return self.status(subject_id=subject_id, review_episode_id=review_episode_id, job_id=job_id, session=session)
        from app.storage.codecs import verify_payload_sha256
        store = JobStore(session)
        job = store.get_job(job_id)
        data = verify_payload_sha256(job.payload_json, job.payload_sha256)
        if job.job_type != JOB_TYPE or (data["subject_id"], data["review_episode_id"]) != (subject_id, review_episode_id):
            raise ScopeViolationError("本次工作稿不属于所选受试者节点")
        saved = store.get_last_checkpoint(job_id, "save") if job.state == "completed" else None
        return {"job_id": job_id, "state": job.state,
                "review_run_id": saved[1]["review_run_id"] if saved else None}

    def update_anchor(self, *, subject_id, review_episode_id, value, expected_revision):
        """User-entered node date; never fills dates inside clinical facts."""
        from app.domain.contracts.common import DateValue
        from app.domain.contracts.enums import AnchorType, DatePrecision, ReviewStage
        from app.storage.repositories import EpisodeRepository
        from app.storage.models import JobRecord
        from app.storage.codecs import verify_payload_sha256
        with self.session_factory() as session, session.begin():
            episode = EpisodeRepository(session).get(review_episode_id)
            if episode.subject_id != subject_id:
                raise ScopeViolationError("审核节点不属于当前受试者")
            for job in session.scalars(select(JobRecord).where(JobRecord.job_type.in_({"fact_normalization", JOB_TYPE}),
                    JobRecord.state.in_({"queued", "running", "failed_retryable"}))):
                data = verify_payload_sha256(job.payload_json, job.payload_sha256)
                owner = data.get("review_episode_id") or (data.get("authority") or {}).get("review_episode_id")
                if owner == review_episode_id:
                    raise ScopeViolationError("当前资料或工作稿正在整理，请完成后再修改节点日期；不会停止已有处理。")
            key = AnchorType.BASELINE_DATE if episode.stage == ReviewStage.BASELINE else AnchorType.SCREENING_DATE
            anchors = dict(episode.anchor_dates)
            anchors[key] = DateValue(value=value, precision=DatePrecision.DAY, source_text="构建者或审核人员从原件核对后填写")
            return EpisodeRepository(session).update(review_episode_id, expected_revision, {"anchor_dates": anchors}).revision

    def execute(self, context):
        payload = context.job_payload
        if payload.get("context_id") is None:
            from app.domain.contracts.facts import FactAuthority
            from app.storage.fact_repositories import FactNormalizationRunRepository
            with self.session_factory() as session, session.begin():
                authority = FactAuthority.model_validate(payload["authority"])
                source_run = FactNormalizationRunRepository(session).get(payload["normalization_run_id"])
                if source_run.authority != authority or source_run.status.value not in {"succeeded", "partial"}:
                    raise ScopeViolationError("病例整理尚未完成或不属于本次工作稿")
                prepared = prepare_review(session, self.artifact_store,
                    subject_id=authority.subject_id, review_episode_id=authority.review_episode_id,
                    expected_authority=authority, idempotency_key=f"automatic:{context.job_id}",
                    work_draft=True, evaluator_version=CALCULATION_VERSION)
                payload = {**payload, "context_id": prepared.context_id, "review_run_id": prepared.review_run_id}
        with self.session_factory() as session:
            if context.job_type != JOB_TYPE or payload["calculation_version"] != CALCULATION_VERSION:
                raise ScopeViolationError("本次工作稿计算方式不一致，请保留旧结果")
            frozen = ReviewContextV2Repository(session).get(payload["context_id"])
            if not frozen.work_draft or frozen.review_run_id != payload["review_run_id"]:
                raise ScopeViolationError("工作稿与冻结输入不一致")
            current = authority_from_active_episode(session, frozen.authority.review_episode_id)
            if current != frozen.authority:
                raise ScopeViolationError("资料版本已变化，原工作稿不改写，请重新开始审核")
            rule_set = get_rule_set(session, frozen.authority.rule_set_id, frozen.authority.rule_set_revision)
            if canonical_hash(rule_set.model_dump(mode="json")) != frozen.rule_set_sha256:
                raise ScopeViolationError("本次方案内容指纹不一致")
            store = JobStore(session)
            if context.step_id == "calculate":
                refs = _fact_refs(session, frozen, self.artifact_store)
                missing_refs = [fact for fact in frozen.facts if fact.fact_id not in refs]
                source_issues = [SystemIssue(kind="fact_closure_failed", affected_codes=sorted({clause.official_code
                    for clause in frozen.clause_pack.clauses if any(req.variable_id == fact.variable_id
                        and fact.variable_id is not None for req in clause.evidence_requirements)}),
                    detail="这条记录的摘录尚不能逐字对应原件，未用于本次判断。",
                    alternative="请对照原件核对；其余已有独立依据的结果继续保留。") for fact in missing_refs]
                calculation_frame = frozen.model_copy(update={"facts": tuple(fact for fact in frozen.facts if fact.fact_id in refs),
                    "system_issues": (*frozen.system_issues, *source_issues)})
                items = [calculate_work_component(clause, calculation_frame, rule_set, evidence_refs=refs)
                         for clause in frozen.clause_pack.clauses]
                items.extend(calculate_procedures(calculation_frame, rule_set, evidence_refs=refs))
                for clause in frozen.clause_pack.restricted_clauses:
                    issue = SystemIssue(kind="component_unstructured", affected_codes=[clause.official_code],
                        detail="本条部分要求尚不能由系统完整核对。", alternative="请对照所列方案原文核对该子项。")
                    items.append(WorkDraftItem(item_id=f"{frozen.review_run_id}:{clause.clause_id}",
                        review_run_id=frozen.review_run_id, official_code=clause.official_code,
                        rule_component_id=clause.clause_id, rule_kind=clause.kind, title=clause.title,
                        source_text=clause.source_text, reason_text=issue.detail, system_issue=issue,
                        input_hash=canonical_hash(clause.model_dump(mode="json"))))
                return {"items": [item.model_dump(mode="json") for item in items],
                    "source_issues": [issue.model_dump(mode="json") for issue in source_issues]}
            if context.step_id == "semantic":
                return {"semantic_results": [], "implementation": "WP5_pending"}
            calculated = store.get_last_checkpoint(context.job_id, "calculate")
            if calculated is None:
                raise ScopeViolationError("缺少已保存的组件计算结果")
            items = [WorkDraftItem.model_validate(value) for value in calculated[1]["items"]]
            if context.step_id == "compose":
                for rule in rule_set.rules:
                    if rule.kind.value == "required_procedure":
                        continue
                    children = [item for item in items if item.official_code == rule.official_code]
                    items.append(compose_parent(rule, children, frozen.review_run_id))
                return {"items": [item.model_dump(mode="json") for item in items]}
            if context.step_id != "save":
                raise ScopeViolationError("未知工作稿步骤")
            composed = store.get_last_checkpoint(context.job_id, "compose")
            if composed is None:
                raise ScopeViolationError("缺少完整条款结果")
            items = [WorkDraftItem.model_validate(value) for value in composed[1]["items"]]
            issues = list(frozen.system_issues) + [SystemIssue.model_validate(value)
                for value in calculated[1].get("source_issues", ())]
            for item in items:
                if item.system_issue is not None and item.system_issue not in issues:
                    issues.append(item.system_issue)
            previous_ids = session.scalars(select(ReviewRunRecord.review_run_id).where(
                ReviewRunRecord.review_episode_id == frozen.authority.review_episode_id,
                ReviewRunRecord.run_kind == "work_draft").order_by(ReviewRunRecord.created_at.desc())).all()
            previous_id = next((key for key in previous_ids if key != frozen.review_run_id), None)
            run = ReviewRun(schema_version="review/v2", run_kind="work_draft", system_issues=issues,
                review_run_id=frozen.review_run_id, review_episode_id=frozen.authority.review_episode_id,
                protocol_version_id=frozen.authority.protocol_version_id, rule_set_revision=frozen.authority.rule_set_revision,
                evidence_snapshot_v2_id=frozen.authority.evidence_snapshot_v2_id,
                complete_processing_revision_id=frozen.authority.complete_processing_revision_id,
                started_at=frozen.created_at, completed_at=datetime.now(UTC),
                episode_revision=frozen.authority.episode_revision, context_id=frozen.context_id,
                supersedes_review_run_id=previous_id)
        def apply(session):
            repository = AppendRepository(session, REVIEW_RUN_CONFIG)
            if repository.get_or_none(run.review_run_id) is None:
                repository.save(run)
            repo = WorkDraftRepository(session)
            for item in items:
                repo.save(item)
        return PreparedStepResult(checkpoint={"review_run_id": run.review_run_id, "item_count": len(items),
            "system_issue_count": len(issues)}, apply=apply)
