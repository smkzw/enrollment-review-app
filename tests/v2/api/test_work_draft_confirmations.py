"""Synthetic saved decisions -> explicit confirmation -> append-only real Job/history.

No model/clinical data. Protocol input assembly is a typed synthetic boundary;
storage, source closure, API, Job and history are real. This does not test protocol
publication or the medical correctness of starting decisions, nor prove M2.
"""
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from sqlalchemy import select, func

from app.domain.contracts.enums import ComponentDecision as D, RuleKind
from app.domain.contracts.review import ReviewRun
from app.domain.contracts.work_draft import WorkDraftItem, WorkDraftEvidenceRef
from app.domain.publication import canonical_hash
from app.services.review_preparation_command import prepare_review
from app.services.work_draft_review import CALCULATION_VERSION, JOB_TYPE
from app.storage.models import WorkDraftAcknowledgementRecord, ReviewRunRecord
from app.storage.repositories import AppendRepository, REVIEW_RUN_CONFIG
from app.storage.work_draft_repository import WorkDraftRepository
from app.workflow.runner import JobRunner
from tests.v2.storage.test_fact_correction_repository import _seed_valid_chain, _create_fact_with_candidate

NOW = datetime(2026, 10, 14, tzinfo=UTC)


def seed_saved_work_draft(client, monkeypatch):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_valid_chain(session, "ack-source")
        fact = _create_fact_with_candidate(session, chain, "ack-fact", "ack-publish", "ack-call", "ack-gate", "ack-candidate",
                                           include_source_candidates=True)
        from app.domain.contracts.review_context_v2 import ReviewContextSnapshotV2
        from app.domain.contracts.protocol_ingestion import FrozenProtocolCatalog, FrozenCatalogItem, CatalogKind
        from app.domain.contracts.rules import EvidenceRequirement, WorkflowStage
        from app.projections.evidence_expectation_templates import project_evidence_expectation_templates
        from app.domain.contracts.work_draft import WorkDraftSourcePage
        from app.projections.clause_pack import project_clause_pack
        from app.storage.repositories import EpisodeRepository, SubjectRepository, get_rule_set, PROTOCOL_DOC_CONFIG
        rules = get_rule_set(session, chain["authority"].rule_set_id, chain["authority"].rule_set_revision)
        pack = project_clause_pack(rules)
        catalog_data = dict(catalog_id="synthetic-procedures", snapshot_id="synthetic-protocol",
            catalog_kind=CatalogKind.REQUIRED_PROCEDURES, study_phase=pack.study_phase,
            frozen_at=NOW, frozen_by="synthetic", items=(FrozenCatalogItem(item_id="synthetic-procedure", kind="required_procedure",
                official_code="REQ-99", label="合成检查", review_stage="screening", visit_instance="screening", position=0,
                source_span_ids=["synthetic-source"], source_excerpts=["合成检查原文"]),))
        catalog = FrozenProtocolCatalog(**catalog_data, catalog_sha256=canonical_hash(
            FrozenProtocolCatalog.model_construct(**catalog_data).model_dump(mode="json", exclude={"catalog_sha256"})))
        protocol = AppendRepository(session, PROTOCOL_DOC_CONFIG).get(chain["authority"].protocol_version_id)
        episode = EpisodeRepository(session).get(chain["review_episode_id"])
        grouped = {}
        for clause in pack.clauses:
            for required in clause.evidence_requirements:
                grouped.setdefault(required.due_stage, []).append(required.requirement_id)
        grouped.setdefault(episode.stage, [])
        stages = tuple(WorkflowStage(workflow_stage_id=episode.workflow_stage_id if stage == episode.stage else f"synthetic-{stage.value}",
            stage=stage, display_name=stage.value, due_requirement_ids=ids) for stage, ids in grouped.items())
        requirement = EvidenceRequirement(requirement_id="synthetic-procedure-requirement", procedure_catalog_item_id="synthetic-procedure",
            fact_type="procedure", due_stage=stages[0].stage, description="合成检查")
        stages = (stages[0].model_copy(update={"due_requirement_ids": [*stages[0].due_requirement_ids, requirement.requirement_id]}), *stages[1:])
        templates = tuple(sorted(project_evidence_expectation_templates(rule_set=rules, workflow_stages=list(stages),
            procedure_requirements=[requirement], created_at=NOW), key=lambda row: row.template_id))
        text = fact.assertion_basis.assertion_text
        def assemble(session, _store, **kwargs):
            episode = EpisodeRepository(session).get(kwargs["review_episode_id"])
            data = dict(context_id=kwargs["context_id"], review_run_id=kwargs["review_run_id"],
                authority=chain["authority"], review_episode=episode,
                subject=SubjectRepository(session).get(chain["subject_id"]), project_name="Synthetic confirmation",
                project_revision=1, protocol_document=protocol, rule_set_sha256=canonical_hash(rules.model_dump(mode="json")),
                clause_pack=pack, clause_pack_sha256=pack.clause_pack_sha256,
                protocol_integrity_gate_result_id=protocol.integrity_gate_result_id,
                evaluator_version=kwargs["evaluator_version"], requirements_scope_version="review-requirements-scope/v1",
                workflow_stages=stages, expectation_templates=templates,
                facts=(fact,), created_at=kwargs["created_at"], work_draft=True,
                ancestor_snapshot_ids=(chain["snapshot_id"],), procedure_catalog=catalog, procedure_requirements=(requirement,),
                source_pages=(WorkDraftSourcePage(source_document_version_id=chain["doc_id"], page_artifact_id=chain["page_artifact_id"],
                    page_number=1, effective_text=text, effective_text_sha256=sha256(text.encode()).hexdigest(), extraction_complete=True),))
            pending = ReviewContextSnapshotV2.model_construct(**data, context_sha256="0" * 64)
            return ReviewContextSnapshotV2(**data, context_sha256=canonical_hash(pending.model_dump(mode="json", exclude={"context_sha256"})))
        monkeypatch.setattr("app.services.review_preparation_command.assemble_review_context", assemble)
        monkeypatch.setattr("app.services.review_context_assembly.assemble_review_context", assemble)
        frozen = prepare_review(session, client.app.state.artifact_store, subject_id=chain["subject_id"],
            review_episode_id=chain["review_episode_id"], expected_authority=chain["authority"],
            idempotency_key="synthetic-saved-work-draft", work_draft=True, evaluator_version=CALCULATION_VERSION)
        run = ReviewRun(schema_version="review/v2", run_kind="work_draft", review_run_id=frozen.review_run_id,
            context_id=frozen.context_id, review_episode_id=chain["review_episode_id"], episode_revision=chain["authority"].episode_revision,
            protocol_version_id=chain["authority"].protocol_version_id, rule_set_revision=chain["authority"].rule_set_revision,
            evidence_snapshot_v2_id=chain["authority"].evidence_snapshot_v2_id,
            complete_processing_revision_id=chain["authority"].complete_processing_revision_id, started_at=NOW, completed_at=NOW)
        AppendRepository(session, REVIEW_RUN_CONFIG).save(run)
        ref = WorkDraftEvidenceRef(fact_id=fact.fact_id, locator_id=chain["locator_id"],
            source_document_version_id=chain["doc_id"], page_artifact_id=chain["page_artifact_id"], page_number=1,
            excerpt=fact.assertion_basis.assertion_text)
        from app.storage.repositories import get_rule_set
        rules = get_rule_set(session, chain["authority"].rule_set_id, chain["authority"].rule_set_revision)
        scopes = [(rule.official_code, None, rule.kind, rule.source_text) for rule in rules.rules]
        scopes.extend((clause.official_code, clause.rule_component_id, clause.kind, clause.source_text) for clause in frozen.clause_pack.clauses)
        scopes.extend((clause.official_code, clause.clause_id, clause.kind, clause.source_text) for clause in frozen.clause_pack.restricted_clauses)
        scopes.append(("REQ-99", None, RuleKind.REQUIRED_PROCEDURE, "合成检查原文"))
        rows = []
        for index, (code, component, kind, source) in enumerate(scopes):
            row = WorkDraftItem(item_id=f"{run.review_run_id}:synthetic:{index}", review_run_id=run.review_run_id,
                official_code=code, rule_component_id=component, rule_kind=kind, title=source, source_text=source,
                decision=D.EXCLUSION_NOT_TRIGGERED if kind == RuleKind.EXCLUSION else D.INCLUSION_MET,
                confidence="low", confidence_reason="合成来源提示", reason_text="合成已保存结论；仅用于核实谱系测试。",
                evidence_refs=[ref], input_hash=canonical_hash({"source": source, "component": component, "fact": fact.model_dump(mode="json")}))
            rows.append(WorkDraftRepository(session).save(row))
        rows = WorkDraftRepository(session).list_for_run(run.review_run_id)
    return factory, chain, frozen, run, rows


def test_prepared_step_can_queue_real_work_draft_and_freeze_input(client, monkeypatch):
    """Real start/prepare/JobStore under the runner; typed synthetic source assembly only.

    Semantic selection is empty in this transaction-boundary test; no model,
    correction approval, or child clinical calculation is simulated as passed.
    """
    from app.services import review_context_assembly, review_preparation_command
    from app.services.work_draft_review import WorkDraftReviewService
    from app.storage.review_context_repository import ReviewContextV2Repository
    from app.storage.codecs import verify_payload_sha256
    from app.workflow.jobstore import JobStore
    from app.workflow.runner import PreparedStepResult
    factory, chain, _, old_run, _ = seed_saved_work_draft(client, monkeypatch)
    assemble = review_context_assembly.assemble_review_context
    def source_assembly(session, store, **kwargs):
        kwargs.setdefault("context_id", "synthetic-preview")
        return assemble(session, store, **kwargs)
    monkeypatch.setattr(review_context_assembly, "assemble_review_context", source_assembly)
    monkeypatch.setattr(review_preparation_command, "assemble_review_context", source_assembly)
    monkeypatch.setattr("app.services.work_draft_semantics.targets_for_review", lambda *args: [])
    with factory() as session, session.begin():
        store = JobStore(session)
        store.create_job(job_id="actual-child-queue-parent", job_type="synthetic-queue", progress_total=1)
        store.create_step(job_id="actual-child-queue-parent", step_id="work_draft", name="启动更新结果")
    def execute(context):
        checkpoint = {}
        def queue(session):
            child = WorkDraftReviewService(factory, client.app.state.artifact_store).start(
                subject_id=chain["subject_id"], review_episode_id=chain["review_episode_id"], session=session)
            checkpoint["work_draft_job_id"] = child["job_id"]
        return PreparedStepResult(checkpoint=checkpoint, apply=queue)
    assert JobRunner(factory, {"synthetic-queue": execute}, worker_id="synthetic-owner").run_job("actual-child-queue-parent")
    with factory() as session:
        store = JobStore(session)
        assert store.get_job("actual-child-queue-parent").state == "completed"
        _, checkpoint = store.get_last_checkpoint("actual-child-queue-parent", "work_draft")
        child = store.get_job(checkpoint["work_draft_job_id"])
        assert child.job_type == JOB_TYPE and child.state == "queued"
        payload = verify_payload_sha256(child.payload_json, child.payload_sha256)
        context = ReviewContextV2Repository(session).get(payload["context_id"])
        assert context.work_draft and context.authority == chain["authority"]
        assert context.review_run_id != old_run.review_run_id
        assert AppendRepository(session, REVIEW_RUN_CONFIG).get(old_run.review_run_id) == old_run


def test_confirmation_api_real_job_history_and_repeat_are_append_only(client, monkeypatch):
    factory, chain, frozen, old_run, old_items = seed_saved_work_draft(client, monkeypatch)
    subject, episode = chain["subject_id"], chain["review_episode_id"]
    target = next(item for item in old_items if item.rule_component_id is None)
    endpoint = f"/api/v2/subjects/{subject}/review-episodes/{episode}/work-draft-confirmations"
    body = {"review_run_id": old_run.review_run_id, "item_id": target.item_id, "confirmed": True, "actor_kind": "builder_verification"}
    # Confirmation cannot call semantic inference or regenerate the baseline.
    monkeypatch.setattr("app.services.work_draft_semantics.runtime_model", lambda: pytest.fail("no model for confidence-only update"))
    response = client.post(endpoint, json=body)
    assert response.status_code == 200, response.text
    queued = response.json()
    assert queued["state"] == "queued" and queued["review_run_id"] is None
    assert client.post(endpoint, json=body).json() == queued
    runner = JobRunner(factory, client.app.state.job_executors, worker_id="ack-test")
    assert runner.run_job(queued["job_id"])
    result = client.get(f"/api/v2/subjects/{subject}/review-episodes/{episode}/work-draft-jobs/{queued['job_id']}").json()
    assert result["state"] == "completed" and result["review_run_id"] != old_run.review_run_id
    with factory() as session:
        repository = WorkDraftRepository(session)
        new_items = repository.list_for_run(result["review_run_id"])
        new = next(item for item in new_items if item.official_code == target.official_code and item.rule_component_id is None)
        assert new.confidence == "high" and new.confirmation_kind == "builder_verification"
        assert new.decision == target.decision and new.evidence_refs == target.evidence_refs
        assert repository.list_for_run(old_run.review_run_id) == old_items
        assert len(new_items) == len(old_items)
        for original, updated in zip(old_items, new_items):
            if original.item_id == target.item_id:
                continue
            assert updated.model_dump(exclude={"item_id", "review_run_id"}) == original.model_dump(exclude={"item_id", "review_run_id"})
        run = AppendRepository(session, REVIEW_RUN_CONFIG).get(result["review_run_id"])
        assert run.supersedes_review_run_id == old_run.review_run_id
        assert session.scalar(select(func.count()).select_from(WorkDraftAcknowledgementRecord)) == 1
    history = client.get(f"/api/v2/subjects/{subject}/review-episodes/{episode}/review-runs/{result['review_run_id']}")
    assert history.status_code == 200, history.text
    assert client.post(endpoint, json=body).json()["job_id"] == queued["job_id"]


def test_confirmation_requires_explicit_action_and_current_subject(client, monkeypatch):
    _, chain, _, run, items = seed_saved_work_draft(client, monkeypatch)
    endpoint = f"/api/v2/subjects/{chain['subject_id']}/review-episodes/{chain['review_episode_id']}/work-draft-confirmations"
    body = {"review_run_id": run.review_run_id, "item_id": items[0].item_id, "confirmed": True, "actor_kind": "builder_verification"}
    for override in [{"confirmed": False}, {"confirmed": "true"}, {"actor_kind": "agent"},
                     {"actor_kind": "medical_manager"}, {"item_id": "other-item"}]:
        response = client.post(endpoint, json={**body, **override})
        assert response.status_code in {409, 422}, response.text
    wrong = endpoint.replace(chain["subject_id"], "not-this-subject")
    assert client.post(wrong, json=body).status_code in {404, 422}
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(WorkDraftAcknowledgementRecord)) == 0
        assert session.scalar(select(func.count()).select_from(ReviewRunRecord).where(ReviewRunRecord.run_kind == "work_draft")) == 1
