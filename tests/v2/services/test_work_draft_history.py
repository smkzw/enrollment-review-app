"""Frozen working history uses saved consumers, never current evaluation or signing."""
from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import ComponentDecision, ReviewStage, RuleKind, StudyPhase
from app.domain.contracts.evidence_locator import EvidenceLocatorArtifact
from app.domain.contracts.protocol_ingestion import FrozenProtocolCatalog, FrozenCatalogItem, CatalogKind
from app.domain.contracts.review import ReviewRun
from app.domain.contracts.review_context_v2 import ReviewContextSnapshotV2
from app.domain.contracts.rules import EvidenceRequirement, WorkflowStage
from app.projections.evidence_expectation_templates import project_evidence_expectation_templates
from app.domain.contracts.work_draft import WorkDraftItem, WorkDraftEvidenceRef, WorkDraftSourceRef, WorkDraftSourcePage
from app.domain.publication import canonical_hash
from app.services import review_history_service as history
from tests.v2.services.test_receipt_verified_work_draft_consumer import _synthetic_material, _aligned_review_context, NOW


@pytest.fixture
def frozen_history(monkeypatch):
    authority, rules, _, fact, episode, _ = _synthetic_material()
    rules = rules.model_copy(update={"verification_only": True})
    context = _aligned_review_context(authority=authority, rule_set=rules, clinical_fact=fact, episode=episode)
    catalog_data = dict(catalog_id="procedures", snapshot_id="protocol-source", catalog_kind=CatalogKind.REQUIRED_PROCEDURES,
        study_phase=StudyPhase.PHASE_III, frozen_at=NOW, frozen_by="builder", items=[dict(item_id="procedure",
        kind="required_procedure", official_code="REQ-01", label="检查", visit_instance="baseline",
        review_stage="baseline", position=0, source_span_ids=["procedure-source"], source_excerpts=["基线检查原文"])])
    catalog_data["items"] = tuple(FrozenCatalogItem.model_validate(item) for item in catalog_data["items"])
    catalog_data["catalog_sha256"] = canonical_hash(FrozenProtocolCatalog.model_construct(**catalog_data).model_dump(mode="json", exclude={"catalog_sha256"}))
    catalog = FrozenProtocolCatalog.model_validate(catalog_data)
    text = fact.assertion_basis.assertion_text
    page = WorkDraftSourcePage(source_document_version_id="doc", page_artifact_id="page", page_number=1,
        effective_text=text, effective_text_sha256=sha256(text.encode()).hexdigest(), extraction_complete=True)
    requirement = EvidenceRequirement(requirement_id="check", procedure_catalog_item_id="procedure", fact_type="procedure",
        due_stage=ReviewStage.BASELINE, description="基线检查")
    stages = [*context.workflow_stages, WorkflowStage(workflow_stage_id="baseline", stage=ReviewStage.BASELINE,
        display_name="基线期", due_requirement_ids=[requirement.requirement_id])]
    templates = project_evidence_expectation_templates(rule_set=rules, workflow_stages=stages, procedure_requirements=[requirement], created_at=NOW)
    data = context.model_dump(mode="json", exclude={"context_sha256"}) | dict(work_draft=True,
        workflow_stages=[stage.model_dump(mode="json") for stage in stages],
        expectation_templates=[template.model_dump(mode="json") for template in sorted(templates, key=lambda item: item.template_id)],
        ancestor_snapshot_ids=[authority.evidence_snapshot_v2_id], source_pages=[page.model_dump(mode="json")],
        procedure_catalog=catalog.model_dump(mode="json"), procedure_requirements=[requirement.model_dump(mode="json")])
    context = ReviewContextSnapshotV2.model_validate(data | {"context_sha256": canonical_hash(data)})
    run = ReviewRun(schema_version="review/v2", run_kind="work_draft", review_run_id=context.review_run_id,
        context_id=context.context_id, review_episode_id=authority.review_episode_id, episode_revision=authority.episode_revision,
        protocol_version_id=authority.protocol_version_id, rule_set_revision=authority.rule_set_revision,
        evidence_snapshot_v2_id=authority.evidence_snapshot_v2_id,
        complete_processing_revision_id=authority.complete_processing_revision_id, started_at=NOW, completed_at=NOW)
    locator = EvidenceLocatorArtifact(locator_id=fact.locator_ids[0], source_document_version_id="doc", page_artifact_id="page",
        page_number=1, excerpt=text, source_layer="native_text", source_text_sha256=sha256(text.encode()).hexdigest(),
        target_id="target", precision="text_range", text_start=0, text_end=len(text), authenticity="degraded",
        degradation_reason="no_bbox", locator_algorithm_version="synthetic", created_at=NOW)
    scopes = [(rules.rules[0].official_code, None, rules.rules[0].kind, rules.rules[0].source_text),
        *[(c.official_code, c.rule_component_id, c.kind, c.source_text) for c in context.clause_pack.clauses],
        *[(c.official_code, c.clause_id, c.kind, c.source_text) for c in context.clause_pack.restricted_clauses],
        ("REQ-01", None, RuleKind.REQUIRED_PROCEDURE, "基线检查原文")]
    rows = [WorkDraftItem(item_id=f"item-{i}", review_run_id=run.review_run_id, official_code=code,
        rule_component_id=component, rule_kind=kind, title="冻结要求", source_text=source,
        decision=ComponentDecision.INDETERMINATE, reason_text="当时尚未核清", input_hash="a" * 64)
        for i, (code, component, kind, source) in enumerate(scopes)]
    rows[1] = rows[1].model_copy(update=dict(decision=ComponentDecision.EXCLUSION_NOT_TRIGGERED, confidence="low",
        reason_text="原文支持本次未触发", evidence_refs=[WorkDraftEvidenceRef(fact_id=fact.fact_id, locator_id=locator.locator_id,
            source_document_version_id="doc", page_artifact_id="page", page_number=1, excerpt=text)],
        source_read_refs=[WorkDraftSourceRef(source_document_version_id="doc", page_artifact_id="page", page_number=1,
            excerpt=text, disposition="mentioned")]))
    from app.storage.work_draft_repository import WorkDraftRepository
    from app.storage.evidence_repositories import SourceDocumentRepository, EvidenceSnapshotRepository
    monkeypatch.setattr(history, "get_rule_set", lambda *args: rules)
    monkeypatch.setattr(WorkDraftRepository, "list_for_run", lambda *args: rows)
    monkeypatch.setattr(history.FactAuthorityValidator, "validate_locators", lambda *args: None)
    monkeypatch.setattr(history.EvidenceLocatorRepository, "get_many", lambda *args: [locator])
    monkeypatch.setattr(EvidenceSnapshotRepository, "get", lambda *args: SimpleNamespace(members=[SimpleNamespace(source_document_version_id="doc")]))
    documents = {"doc": SimpleNamespace(project_id=authority.project_id, subject_id=authority.subject_id, file_name="原报告.pdf")}
    monkeypatch.setattr(SourceDocumentRepository, "get_many", lambda *args: documents)
    return run, context, rows, locator, documents


def test_saved_history_reads_all_parents_children_and_procedures_without_signing(frozen_history):
    run, context, rows, _, _ = frozen_history
    before = canonical_hash(context.model_dump(mode="json")), [canonical_hash(row.model_dump(mode="json")) for row in rows]
    result = history._work_draft_detail(None, run, context, "completed")
    assert result.assessments == result.actions == ()
    assert len(result.work_draft.clauses) == 2
    assert len(result.work_draft.component_clauses) == 2
    assert result.work_draft.component_clauses[0].decision == "exclusion_not_triggered"
    assert result.work_draft.component_clauses[0].confidence == "low"
    assert result.source_file_names == {"doc": "原报告.pdf"}
    assert before == (canonical_hash(context.model_dump(mode="json")), [canonical_hash(row.model_dump(mode="json")) for row in rows])


@pytest.mark.parametrize("damage", ["missing", "duplicate", "extra", "wrong_run", "wrong_source", "wrong_kind", "wrong_fact", "wrong_position", "wrong_excerpt", "wrong_page_excerpt", "wrong_patient"])
def test_history_rejects_incomplete_or_wrong_frozen_sources(frozen_history, damage):
    run, context, rows, _, documents = frozen_history
    if damage == "missing": rows.pop()
    elif damage == "duplicate": rows.append(rows[0])
    elif damage == "extra": rows.append(rows[0].model_copy(update={"official_code": "EX-99"}))
    elif damage == "wrong_patient": documents["doc"].subject_id = "other-patient"
    elif damage == "wrong_fact": rows[1] = rows[1].model_copy(update={"evidence_refs": [rows[1].evidence_refs[0].model_copy(update={"fact_id": "missing"})]})
    elif damage == "wrong_position": rows[1] = rows[1].model_copy(update={"evidence_refs": [rows[1].evidence_refs[0].model_copy(update={"page_number": 2})]})
    elif damage == "wrong_excerpt": rows[1] = rows[1].model_copy(update={"evidence_refs": [rows[1].evidence_refs[0].model_copy(update={"excerpt": "编造值"})]})
    elif damage == "wrong_page_excerpt": rows[1] = rows[1].model_copy(update={"source_read_refs": [rows[1].source_read_refs[0].model_copy(update={"excerpt": "编造字句"})]})
    else:
        field, value = {"wrong_run": ("review_run_id", "other-run"), "wrong_source": ("source_text", "新改原文"), "wrong_kind": ("rule_kind", RuleKind.INCLUSION)}[damage]
        rows[0] = rows[0].model_copy(update={field: value})
    with pytest.raises(history.ReviewHistoryIncompleteError):
        history._work_draft_detail(None, run, context, "completed")


def test_formal_completed_history_still_requires_formal_assessments(monkeypatch, frozen_history):
    run, context, _, _, _ = frozen_history
    run = run.model_copy(update={"run_kind": "formal"})
    monkeypatch.setattr(history, "_require_subject_episode", lambda *args: context.review_episode)
    monkeypatch.setattr(history.AppendRepository, "get", lambda *args: run)
    monkeypatch.setattr(history, "_load_frozen_context", lambda *args: context)
    monkeypatch.setattr(history, "_pinned_clause_identities", lambda *args: {"component-a": object()})
    monkeypatch.setattr(history, "_stored_assessments", lambda *args: ({}, ()))
    with pytest.raises(history.ReviewHistoryIncompleteError, match="缺少 1"):
        history.get_run(None, context.authority.subject_id, run.review_episode_id, run.review_run_id)


