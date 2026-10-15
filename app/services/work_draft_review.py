"""One durable work-draft job consumes the frozen input; no clinical signature."""
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select

from app.domain.contracts.review import ReviewRun
from app.domain.contracts.enums import ComponentDecision
from app.domain.contracts.work_draft import (SystemIssue, WorkDraftEvidenceRef, WorkDraftItem,
    WorkDraftAcknowledgement, acknowledgement_input_hash)
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
CALCULATION_VERSION = "work-draft/0.2.0-v34"


def confirmation_allowed(item, items):
    from app.services.work_draft_calculation import DETERMINATE
    return (item.rule_component_id is None and item.decision in DETERMINATE and item.confidence == "low"
        and item.system_issue is None and bool(item.evidence_refs or item.source_read_refs)
        and not any(ref.disposition == "unresolved" for ref in item.source_read_refs)
        and all(child.system_issue is None and child.decision in DETERMINATE | {
            ComponentDecision.NOT_DUE, ComponentDecision.NOT_APPLICABLE}
            for child in items if child.official_code == item.official_code and child.rule_component_id is not None))


def _apply_confirmations(items, confirmations, evaluator_version):
    matches = {record.input_hash: record for record in confirmations}
    result = []
    for item in items:
        record = matches.get(acknowledgement_input_hash(item, evaluator_version))
        if record and confirmation_allowed(item, items):
            item = WorkDraftItem.model_validate(item.model_dump(mode="json") | {
                "confidence": "high", "confidence_reason": "医学经理已核实本条依据" if record.actor_kind == "medical_manager"
                    else "构建者验证已核实，非正式医学审定",
                "acknowledgement_id": record.acknowledgement_id, "confirmation_kind": record.actor_kind})
        result.append(item)
    return result


def _reusable_source_reads(session, store, frozen, targets, model, artifact_store):
    from app.storage.models import JobRecord
    from app.storage.codecs import verify_payload_sha256
    from app.services.work_draft_semantics import revalidate_saved_source_read, targets_for_review
    from app.services.review_context_assembly import clinical_source_scope_is_compatible
    from app.storage.repositories import PROTOCOL_DOC_CONFIG, list_workflow_stages_for_rule_set
    accepted, proofs = {}, {}
    prior_jobs = session.scalars(select(JobRecord).where(JobRecord.job_type == JOB_TYPE,
        JobRecord.state.in_({"completed", "cancelled"}),
        func.json_extract(JobRecord.payload_json, "$.review_episode_id") == frozen.authority.review_episode_id
        ).order_by(JobRecord.created_at.desc())).all()
    for job in prior_jobs:
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        if not payload.get("context_id"):
            continue
        previous = ReviewContextV2Repository(session).get(payload["context_id"])
        if previous.source_pages != frozen.source_pages:
            continue
        previous_targets = None
        if previous.authority != frozen.authority:
            old_rules = get_rule_set(session, previous.authority.rule_set_id, previous.authority.rule_set_revision)
            current_rules = get_rule_set(session, frozen.authority.rule_set_id, frozen.authority.rule_set_revision)
            protocols = AppendRepository(session, PROTOCOL_DOC_CONFIG)
            if not clinical_source_scope_is_compatible(previous.authority, frozen.authority, old_rules, current_rules,
                    protocols.get(previous.authority.protocol_version_id), protocols.get(frozen.authority.protocol_version_id)):
                continue
            old_stages = list_workflow_stages_for_rule_set(session, old_rules.rule_set_id, old_rules.revision)
            current_stages = list_workflow_stages_for_rule_set(session, current_rules.rule_set_id, current_rules.revision)
            old_stage = next((s for s in old_stages if s.workflow_stage_id == previous.review_episode.workflow_stage_id), None)
            current_stage = next((s for s in current_stages if s.workflow_stage_id == frozen.review_episode.workflow_stage_id), None)
            excluded = {"workflow_stage_id", "due_requirement_ids"}
            if (old_stage is None or current_stage is None
                    or old_stage.model_dump(exclude=excluded) != current_stage.model_dump(exclude=excluded)):
                continue
            previous_targets = targets_for_review(previous, old_rules)
        for step in store.list_steps(job.job_id):
            if not step.step_id.startswith("semantic"):
                continue
            checkpoint = store.get_last_checkpoint(job.job_id, step.step_id)
            if checkpoint is None:
                continue
            rows, origins = revalidate_saved_source_read(checkpoint[1], frozen, targets, model, artifact_store,
                previous_targets=previous_targets)
            for key, row in rows.items():
                if key not in accepted:
                    accepted[key] = row
                    proofs[key] = {**origins[key], "job_id": job.job_id, "step_id": step.step_id,
                        "checkpoint_sha256": canonical_hash(checkpoint[1])}
    return accepted, proofs


def enqueue_normalized_work_draft(session, *, authority, run_id):
    """Queue only: an unavailable review consumer cannot undo successful fact publication."""
    from app.services.work_draft_semantics import runtime_model
    model = runtime_model()
    confirmations = WorkDraftRepository(session).list_acknowledgements(authority.review_episode_id)
    key = canonical_hash({"normalization_run_id": run_id, "authority": authority.model_dump(mode="json"),
                          "calculation_version": CALCULATION_VERSION, "semantic_model": model.model_dump(mode="json"),
                          **({"acknowledgements": [row.model_dump(mode="json") for row in confirmations]} if confirmations else {})})
    receipt, created = IdempotencyRepository(session).resolve(scope="automatic-work-draft",
        idempotency_key=key, submitted_hash=key, result_type="work_draft_job", result_id=uuid4().hex)
    if created:
        store = JobStore(session)
        store.create_job(job_id=receipt.result_id, job_type=JOB_TYPE, progress_total=4,
            payload={"normalization_run_id": run_id, "authority": authority.model_dump(mode="json"),
                     "subject_id": authority.subject_id, "review_episode_id": authority.review_episode_id,
                     "calculation_version": CALCULATION_VERSION, "semantic_model": model.model_dump(mode="json"),
                     **({"acknowledgement_ids": [row.acknowledgement_id for row in confirmations]} if confirmations else {})})
        for step, depends_on in work_draft_steps():
            store.create_step(job_id=receipt.result_id, step_id=step,
                name={"calculate": "核对确定性条件", "semantic": "核对病历原文与条件关系",
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

    def confirm(self, *, subject_id, review_episode_id, review_run_id, item_id, actor_kind):
        from app.storage.repositories import EpisodeRepository
        from app.storage.models import JobRecord
        from app.storage.codecs import verify_payload_sha256
        with self.session_factory() as session, session.begin():
            episode = EpisodeRepository(session).get(review_episode_id)
            if episode.subject_id != subject_id:
                raise ScopeViolationError("审核节点不属于当前受试者")
            if actor_kind not in {"medical_manager", "builder_verification"}:
                raise ScopeViolationError("核实身份无效")
            repository = WorkDraftRepository(session)
            ack_id = "work-draft-confirmation:" + canonical_hash({"episode": review_episode_id,
                "run": review_run_id, "item": item_id, "actor_kind": actor_kind})[:32]
            existing = repository.acknowledgements.get_or_none(ack_id)
            if existing is not None:
                return self.status(subject_id=subject_id, review_episode_id=review_episode_id,
                    job_id=existing.work_draft_job_id, session=session)
            run, baseline = self._current_base(session, subject_id, review_episode_id, review_run_id)
            latest = session.scalars(select(ReviewRunRecord.review_run_id).where(
                ReviewRunRecord.review_episode_id == review_episode_id, ReviewRunRecord.run_kind == "work_draft")
                .order_by(ReviewRunRecord.created_at.desc())).first()
            if latest != review_run_id:
                raise ScopeViolationError("工作稿已更新，请打开最新版本后核实")
            for job in session.scalars(select(JobRecord).where(JobRecord.job_type.in_({JOB_TYPE, "fact_normalization", "fact_correction"}),
                    JobRecord.state.in_({"queued", "running", "failed_retryable"}))):
                data = verify_payload_sha256(job.payload_json, job.payload_sha256)
                if (data.get("review_episode_id") or (data.get("authority") or {}).get("review_episode_id")) == review_episode_id:
                    raise ScopeViolationError("本次资料或工作稿正在更新，请完成后核实")
            items = repository.list_for_run(review_run_id)
            target = next((item for item in items if item.item_id == item_id), None)
            if target is None or not confirmation_allowed(target, items):
                raise ScopeViolationError("本条仍有未完成的核对，不能用已核实替代缺失、矛盾或系统问题")
            rules = get_rule_set(session, baseline.authority.rule_set_id, baseline.authority.rule_set_revision)
            if rules.verification_only is not False and actor_kind != "builder_verification":
                raise ScopeViolationError("验证用规则只能记录构建者验证，不能冒充正式医学核实")
            frozen = prepare_review(session, self.artifact_store, subject_id=subject_id, review_episode_id=review_episode_id,
                expected_authority=baseline.authority, idempotency_key=ack_id, work_draft=True, evaluator_version=CALCULATION_VERSION)
            excluded = {"context_id", "review_run_id", "created_at", "context_sha256"}
            if frozen.model_dump(mode="json", exclude=excluded) != baseline.model_dump(mode="json", exclude=excluded):
                raise ScopeViolationError("核实期间资料已变化，请先更新工作稿")
            job_id = uuid4().hex
            confirmation = WorkDraftAcknowledgement(acknowledgement_id=ack_id, review_episode_id=review_episode_id,
                official_code=target.official_code, input_hash=acknowledgement_input_hash(target, baseline.evaluator_version),
                base_review_run_id=review_run_id, base_item_id=item_id, work_draft_job_id=job_id,
                actor_kind=actor_kind, created_at=datetime.now(UTC))
            repository.acknowledgements.save(confirmation)
            store = JobStore(session)
            store.create_job(job_id=job_id, job_type=JOB_TYPE, progress_total=3,
                payload={"subject_id": subject_id, "review_episode_id": review_episode_id,
                    "review_run_id": frozen.review_run_id, "context_id": frozen.context_id,
                    "calculation_version": CALCULATION_VERSION, "acknowledgement_base_run_id": review_run_id,
                    "base_items_sha256": canonical_hash([item.model_dump(mode="json") for item in items]),
                    "acknowledgement_ids": [ack_id], "semantic_batches": []})
            for step, dependencies in work_draft_steps(0):
                store.create_step(job_id=job_id, step_id=step, depends_on=dependencies,
                    name={"calculate": "核实当前依据", "compose": "更新核实结果", "save": "保存新版工作稿"}[step])
            return self.status(subject_id=subject_id, review_episode_id=review_episode_id, job_id=job_id, session=session)

    def _current_base(self, session, subject_id, review_episode_id, review_run_id):
        from app.services.review_context_assembly import assemble_review_context
        run = AppendRepository(session, REVIEW_RUN_CONFIG).get(review_run_id)
        if run.run_kind != "work_draft" or run.review_episode_id != review_episode_id or run.completed_at is None:
            raise ScopeViolationError("所选记录不是该节点已保存的工作稿")
        frozen = ReviewContextV2Repository(session).get(run.context_id)
        if frozen.authority.subject_id != subject_id or frozen.evaluator_version != CALCULATION_VERSION:
            raise ScopeViolationError("本条审核对象或核对方式已变化，请先更新工作稿")
        current = assemble_review_context(session, self.artifact_store, review_episode_id=review_episode_id,
            review_run_id=frozen.review_run_id, evaluator_version=CALCULATION_VERSION,
            created_at=frozen.created_at, context_id=frozen.context_id, work_draft=True)
        if current.context_sha256 != frozen.context_sha256:
            raise ScopeViolationError("本次资料或方案已变化，请先更新工作稿")
        from app.services.review_history_service import _work_draft_detail, ReviewHistoryIncompleteError
        try:
            _work_draft_detail(session, run, frozen, "completed")
        except ReviewHistoryIncompleteError as exc:
            raise ScopeViolationError("原工作稿或其依据不完整，不能记录已核实") from exc
        return run, frozen

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
            from app.services.patient_profile_service import PatientProfileService
            from app.storage.fact_authority import FactAuthorityValidator
            profile = PatientProfileService()
            previous_profile = profile.latest(session, review_episode_id)
            reproject_profile = (previous_profile is not None and previous_profile.status.value == "stale"
                    and FactAuthorityValidator(session, self.artifact_store).rule_revision_source_is_reusable(
                        previous_profile.authority, authority))
            from app.services.review_context_assembly import assemble_review_context
            preview = assemble_review_context(session, self.artifact_store, review_episode_id=review_episode_id,
                review_run_id="pending", evaluator_version=CALCULATION_VERSION,
                created_at=datetime.now(UTC), work_draft=True)
            from app.services.work_draft_semantics import runtime_model, targets_for_review, source_batches
            rule_set = get_rule_set(session, authority.rule_set_id, authority.rule_set_revision)
            targets = targets_for_review(preview, rule_set)
            model = runtime_model() if targets else None
            reusable, _ = _reusable_source_reads(session, JobStore(session), preview, targets, model,
                self.artifact_store) if targets else ({}, {})
            batches = source_batches(targets, reusable)
            confirmations = WorkDraftRepository(session).list_acknowledgements(review_episode_id)
            identity = canonical_hash({"authority": authority.model_dump(mode="json"),
                "rule_set_sha256": preview.rule_set_sha256,
                "clinical_facts": [item.model_dump(mode="json") for item in preview.facts],
                "system_issues": [item.model_dump(mode="json") for item in preview.system_issues],
                "source_pages": [item.model_dump(mode="json") for item in preview.source_pages],
                "evidence_cutoff_date": preview.review_episode.model_dump(mode="json").get("evidence_cutoff_date"),
                "calculation_version": CALCULATION_VERSION,
                "semantic_model": model.model_dump(mode="json") if model else None,
                "semantic_targets": targets,
                **({"acknowledgements": [row.model_dump(mode="json") for row in confirmations]} if confirmations else {})})
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
                             "calculation_version": CALCULATION_VERSION, "input_hash": identity,
                             **({"acknowledgement_ids": [row.acknowledgement_id for row in confirmations]} if confirmations else {}),
                             "semantic_model": model.model_dump(mode="json") if model else None,
                             "semantic_batches": batches}, progress_total=3 + len(batches))
                for step, depends_on in work_draft_steps(len(batches)):
                    store.create_step(job_id=receipt.result_id, step_id=step,
                        name="核对病历原文与条件关系" if step.startswith("semantic") else
                            {"calculate": "核对确定性条件", "compose": "合并条款结果", "save": "保存工作稿"}[step],
                        depends_on=depends_on)
            if reproject_profile:
                # Finish expensive read-only planning before acquiring a write
                # lock for this deterministic view; no source reread is needed.
                profile.generate(session, authority=authority, include_rule_revision_sources=True)
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
        return self._update_episode_date(subject_id=subject_id, review_episode_id=review_episode_id,
            value=value, expected_revision=expected_revision, cutoff=False)

    def update_evidence_cutoff(self, *, subject_id, review_episode_id, value, expected_revision):
        return self._update_episode_date(subject_id=subject_id, review_episode_id=review_episode_id,
            value=value, expected_revision=expected_revision, cutoff=True)

    def _update_episode_date(self, *, subject_id, review_episode_id, value, expected_revision, cutoff):
        from app.domain.contracts.common import DateValue
        from app.domain.contracts.enums import AnchorType, DatePrecision, ReviewStage
        from app.storage.repositories import EpisodeRepository
        from app.storage.models import JobRecord
        from app.storage.codecs import verify_payload_sha256
        with self.session_factory() as session, session.begin():
            episode = EpisodeRepository(session).get(review_episode_id)
            if episode.subject_id != subject_id:
                raise ScopeViolationError("审核节点不属于当前受试者")
            for job in session.scalars(select(JobRecord).where(JobRecord.job_type.in_({"fact_normalization", "fact_correction", JOB_TYPE}),
                    JobRecord.state.in_({"queued", "running", "failed_retryable"}))):
                data = verify_payload_sha256(job.payload_json, job.payload_sha256)
                owner = data.get("review_episode_id") or (data.get("authority") or {}).get("review_episode_id")
                if owner == review_episode_id:
                    raise ScopeViolationError("当前资料或工作稿正在整理，请完成后再修改日期；不会停止已有处理。")
            if cutoff:
                anchor_type = AnchorType.BASELINE_DATE if episode.stage == ReviewStage.BASELINE else AnchorType.SCREENING_DATE
                anchor = episode.anchor_dates.get(anchor_type)
                if value is not None and anchor is not None and anchor.value is not None and value < anchor.value:
                    raise ScopeViolationError("资料截至日不能早于本节点开始日")
                return EpisodeRepository(session).update(review_episode_id, expected_revision,
                    {"evidence_cutoff_date": value}).revision
            key = AnchorType.BASELINE_DATE if episode.stage == ReviewStage.BASELINE else AnchorType.SCREENING_DATE
            anchors = dict(episode.anchor_dates)
            if episode.evidence_cutoff_date is not None and value > episode.evidence_cutoff_date:
                raise ScopeViolationError("本节点开始日不能晚于资料截至日")
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
            if payload.get("acknowledgement_base_run_id"):
                baseline_run, baseline = self._current_base(session, payload["subject_id"], payload["review_episode_id"],
                    payload["acknowledgement_base_run_id"])
                if frozen.authority != baseline.authority:
                    raise ScopeViolationError("核实记录的资料范围已变化")
                if context.step_id == "calculate":
                    items = WorkDraftRepository(session).list_for_run(baseline_run.review_run_id)
                    if canonical_hash([item.model_dump(mode="json") for item in items]) != payload["base_items_sha256"]:
                        raise ScopeViolationError("原工作稿内容已变化，未复制旧结论")
                    if any(not item.item_id.startswith(baseline_run.review_run_id + ":") for item in items):
                        raise ScopeViolationError("原条目身份不属于本次工作稿")
                    items = [WorkDraftItem.model_validate(item.model_dump(mode="json") | {
                        "item_id": frozen.review_run_id + item.item_id[len(baseline_run.review_run_id):],
                        "review_run_id": frozen.review_run_id}) for item in items]
                    return {"items": [item.model_dump(mode="json") for item in items],
                        "source_issues": [issue.model_dump(mode="json") for issue in baseline_run.system_issues
                            if issue not in frozen.system_issues]}
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
                    from app.services.eligibility_review_projection import _restricted_clause_projection
                    limitation = _restricted_clause_projection(clause)
                    issue = SystemIssue(kind="component_unstructured", affected_codes=[clause.official_code],
                        detail=limitation.reason, alternative=limitation.action_detail)
                    items.append(WorkDraftItem(item_id=f"{frozen.review_run_id}:{clause.clause_id}",
                        review_run_id=frozen.review_run_id, official_code=clause.official_code,
                        rule_component_id=clause.clause_id, rule_kind=clause.kind, title=clause.title,
                        source_text=clause.source_text, reason_text=issue.detail, system_issue=issue,
                        input_hash=canonical_hash(clause.model_dump(mode="json"))))
                return {"items": [item.model_dump(mode="json") for item in items],
                    "source_issues": [issue.model_dump(mode="json") for issue in source_issues]}
            if context.step_id.startswith("semantic"):
                from app.domain.contracts.agents import ModelConfigContract
                from app.services.work_draft_semantics import read_source_relations, runtime_model, targets_for_review
                batches = payload.get("semantic_batches") or [targets_for_review(frozen, rule_set)]
                for prior in store.list_steps(context.job_id):
                    if prior.step_id == context.step_id or not prior.step_id.startswith("semantic"):
                        continue
                    checkpoint = store.get_last_checkpoint(context.job_id, prior.step_id)
                    if checkpoint and checkpoint[1].get("provider_blocked"):
                        return {"results": {}, "calls": [], "provider_blocked": True,
                            "blocked_by_step": prior.step_id, "error": "病例核对模型访问受限，本批未重复请求。"}
                index = int(context.step_id.split(":")[1]) if ":" in context.step_id else 0
                model = ModelConfigContract.model_validate(payload["semantic_model"]) if payload.get("semantic_model") else runtime_model()
                # Verify original full request groups before selecting this batch;
                # regrouping targets must not invalidate otherwise identical reads.
                reused, proofs = _reusable_source_reads(session, store, frozen,
                    targets_for_review(frozen, rule_set), model, self.artifact_store)
                batch_ids = {target["target_id"] for target in batches[index]}
                reused = {key: row for key, row in reused.items() if key in batch_ids}
                proofs = {key: proof for key, proof in proofs.items() if key in batch_ids}
                # No database transaction is held while the product model reads sources.
                session.close()
                return read_source_relations(frozen, batches[index], model, self.artifact_store,
                    reused=reused, reuse_proofs=proofs)
            calculated = store.get_last_checkpoint(context.job_id, "calculate")
            if calculated is None:
                raise ScopeViolationError("缺少已保存的组件计算结果")
            items = [WorkDraftItem.model_validate(value) for value in calculated[1]["items"]]
            if context.step_id == "compose":
                confirmations = [WorkDraftRepository(session).acknowledgements.get(key)
                    for key in payload.get("acknowledgement_ids", ())]
                if any(row.review_episode_id != frozen.authority.review_episode_id for row in confirmations):
                    raise ScopeViolationError("核实记录不属于本次审核节点")
                if payload.get("acknowledgement_base_run_id"):
                    return {"items": [item.model_dump(mode="json") for item in _apply_confirmations(items, confirmations, frozen.evaluator_version)]}
                from app.services.work_draft_semantics import targets_for_review
                source_results, failed_components, provider_blocked_components = {}, {}, set()
                response_disagreement_components = set()
                for step in store.list_steps(context.job_id):
                    if not step.step_id.startswith("semantic"):
                        continue
                    checkpoint = store.get_last_checkpoint(context.job_id, step.step_id)
                    if checkpoint is None:
                        raise ScopeViolationError("缺少本批次已保存的原文核对结果")
                    source_results.update(checkpoint[1].get("results", {}))
                    batches = payload.get("semantic_batches") or [targets_for_review(frozen, rule_set)]
                    index = int(step.step_id.split(":")[1]) if ":" in step.step_id else 0
                    disagreed_ids = {key for key, proof in checkpoint[1].get("reuse_proofs", {}).items()
                        if proof.get("conflicting_raw_response_refs")}
                    for target in batches[index]:
                        if target["target_id"] in disagreed_ids:
                            response_disagreement_components.add(target["component_id"])
                            failed_components[target["component_id"]] = "读取意见未一致"
                    if checkpoint[1].get("error"):
                        failed_ids = set(checkpoint[1].get("error_target_ids", [target["target_id"] for target in batches[index]]))
                        failed_components.update({target["component_id"]: checkpoint[1]["error"]
                            for target in batches[index] if target["target_id"] in failed_ids})
                        if checkpoint[1].get("provider_blocked"):
                            provider_blocked_components.update(target["component_id"] for target in batches[index]
                                if target["target_id"] in failed_ids)
                refs = _fact_refs(session, frozen, self.artifact_store)
                frame = frozen.model_copy(update={"facts": tuple(fact for fact in frozen.facts if fact.fact_id in refs),
                    "system_issues": (*frozen.system_issues, *(SystemIssue.model_validate(issue)
                        for issue in calculated[1].get("source_issues", ())))})
                items = [calculate_work_component(clause, frame, rule_set, evidence_refs=refs,
                    source_results=source_results) for clause in frozen.clause_pack.clauses]
                items.extend(calculate_procedures(frame, rule_set, evidence_refs=refs, source_results=source_results))
                for item in items:
                    key = item.rule_component_id
                    if item.rule_kind.value == "required_procedure":
                        if frozen.procedure_catalog is None:
                            raise ScopeViolationError("检查条目缺少本次冻结流程目录")
                        key = next((procedure.item_id for procedure in frozen.procedure_catalog.items
                            if item.item_id == f"{frozen.review_run_id}:procedure:{procedure.item_id}"), None)
                        if key is None:
                            raise ScopeViolationError("检查条目未对应本次冻结流程目录")
                    if key in failed_components and item.decision not in {
                            ComponentDecision.NOT_DUE, ComponentDecision.NOT_APPLICABLE}:
                        from app.services.work_draft_calculation import DETERMINATE
                        if item.decision not in DETERMINATE:
                            item.decision = None
                            item.confidence = None
                            item.confidence_reason = None
                            blocked = key in provider_blocked_components
                            item.system_issue = SystemIssue(kind="model_unavailable" if blocked else "model_output_invalid",
                                affected_codes=[item.official_code],
                                detail="两次读取对本要求的理解不一致，尚未完成核对；不表示病历资料相互矛盾。"
                                    if key in response_disagreement_components else
                                    "病例核对模型访问受限，尚未完成本条病历核对。" if blocked else
                                    "本条原文核对未完成；已有其他独立结论和原件均保留。",
                                alternative="模型恢复或启用已批准连接后只核未完成范围；原件和已核结果保留。")
                            item.reason_text = item.system_issue.detail
                            item.reason_parts = []
                items.extend(WorkDraftItem.model_validate(value) for value in calculated[1]["items"]
                    if (value.get("system_issue") or {}).get("kind") == "component_unstructured")
                for rule in rule_set.rules:
                    if rule.kind.value == "required_procedure":
                        continue
                    children = [item for item in items if item.official_code == rule.official_code]
                    items.append(compose_parent(rule, children, frozen.review_run_id))
                items = _apply_confirmations(items, confirmations, frozen.evaluator_version)
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
