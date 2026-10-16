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


def test_report_dates_come_from_frozen_node_not_live_settings(frozen_history):
    from datetime import date
    from app.domain.contracts.common import DateValue
    from app.domain.contracts.enums import AnchorType, DatePrecision, ReviewStage
    from app.api.v2.review_history import _context_dto
    _, context, _, _, _ = frozen_history
    original = context.model_dump_json()
    key = AnchorType.BASELINE_DATE if context.review_episode.stage == ReviewStage.BASELINE else AnchorType.SCREENING_DATE
    episode = context.review_episode.model_copy(update={"anchor_dates": {
        key: DateValue(value=date(2025, 8, 8), precision=DatePrecision.DAY)},
        "evidence_cutoff_date": date(2025, 8, 15)})
    saved = context.model_copy(update={"review_episode": episode})
    dto = _context_dto(saved)
    assert dto.node_start_date == date(2025, 8, 8)
    assert dto.evidence_cutoff_date == date(2025, 8, 15)
    assert context.model_dump_json() == original


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


@pytest.mark.parametrize("position", ["current", "wrong_document", "wrong_artifact", "wrong_page", "missing", "absent"])
def test_rejected_fact_navigation_requires_exact_current_page_and_does_not_adopt(frozen_history, monkeypatch, position):
    from app.services.review_context_assembly import _fact_closure_issues
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository

    run, context, rows, locator, _ = frozen_history
    before = context.model_dump_json(), [row.model_dump_json() for row in rows]
    values = {"wrong_document": {"source_document_version_id": "other-doc"},
        "wrong_artifact": {"page_artifact_id": "other-page"}, "wrong_page": {"page_number": 2}}
    candidate_locator = locator.model_copy(update=values.get(position, {}))
    calls = []
    def get(_, key):
        calls.append(key)
        return None if position == "missing" else candidate_locator
    monkeypatch.setattr(EvidenceLocatorRepository, "get_or_none", get)
    rejected = SimpleNamespace(locator_ids=[] if position == "absent" else [locator.locator_id])
    manifest = SimpleNamespace(manifest=[context.source_pages[0]])
    issue, = _fact_closure_issues(None, manifest, [(rejected, ["EX-01"]), (rejected, ["IN-01", "EX-01"])])
    assert issue.affected_codes == ["EX-01", "IN-01"]
    assert calls == ([] if position == "absent" else [locator.locator_id])
    assert issue.kind == "fact_closure_failed"
    assert (issue.source_document_version_id, issue.page_artifact_id, issue.page_number) == (
        ("doc", "page", 1) if position == "current" else (None, None, None))
    # The saved history consumes the issue, not a replacement fact or conclusion.
    run_with_issue = run.model_copy(update={"system_issues": [issue]})
    result = history._work_draft_detail(None, run_with_issue, context, "completed")
    assert result.work_draft.system_issues == (issue,)
    assert result.work_draft.component_clauses[0].decision == "exclusion_not_triggered"
    assert before == (context.model_dump_json(), [row.model_dump_json() for row in rows])


def test_rejected_fact_navigation_keeps_unlocated_scope_and_propagates_corruption(frozen_history, monkeypatch):
    from app.services.review_context_assembly import _fact_closure_issues
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
    from app.storage.repositories import RepositoryError

    _, context, _, locator, _ = frozen_history
    missing = SimpleNamespace(locator_ids=["missing"])
    known = SimpleNamespace(locator_ids=[locator.locator_id])
    monkeypatch.setattr(EvidenceLocatorRepository, "get_or_none", lambda _, key: locator if key == locator.locator_id else None)
    manifest = SimpleNamespace(manifest=[context.source_pages[0]])
    issues = _fact_closure_issues(None, manifest, [(known, ["EX-01"]), (missing, [])])
    assert len(issues) == 2 and any(issue.page_number is None and not issue.affected_codes for issue in issues)
    same_page = _fact_closure_issues(None, manifest, [(known, ["EX-01"]), (known, [])])
    assert len(same_page) == 2 and any(not issue.affected_codes and issue.page_number == 1 for issue in same_page)
    assert _fact_closure_issues(None, manifest, []) == []
    def broken(*args):
        raise RepositoryError("合成定位正文损坏")
    monkeypatch.setattr(EvidenceLocatorRepository, "get_or_none", broken)
    with pytest.raises(RepositoryError, match="损坏"):
        _fact_closure_issues(None, manifest, [(known, [])])


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


def test_medication_rows_are_required_in_their_own_frozen_report_and_never_official_codes(frozen_history):
    from tests.v2.protocols.test_medication_restrictions import frozen_medications, build
    from app.services.work_draft_medications import calculate_medications
    run, context, rows, _, _ = frozen_history
    rules = history.get_rule_set(None, context.authority.rule_set_id, run.rule_set_revision)
    selection, view, proposal = frozen_medications()
    rules.scope_supplement = build(proposal, selection, view)
    context = context.model_copy(update={"medication_exposures": ()})
    medication, = calculate_medications(context, rules, evidence_refs={})
    rows.append(medication)
    result = history._work_draft_detail(None, run, context, "completed")
    assert result.work_draft.clauses[-1].rule_code == "用药01"
    assert result.work_draft.clauses[-1].rule_kind == "medication"
    rows.pop()
    with pytest.raises(history.ReviewHistoryIncompleteError, match="缺失"):
        history._work_draft_detail(None, run, context, "completed")


