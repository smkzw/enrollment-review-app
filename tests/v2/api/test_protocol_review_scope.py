"""Scope API reads preserved source, never restarts deconstruction or publishes it."""
from hashlib import sha256
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.domain.contracts.enums import AlignmentStatus, ExtractionStatus, SourceLocatorPrecision
from app.domain.contracts.protocol_ingestion import ExtractionCoverage, ProtocolExtractionSnapshot, ProtocolSourceSpan
from app.protocols.docx_structure import BlockKind, StructureBlock
from app.services.protocol_workbench_service import PROTOCOL_DECONSTRUCTION_STEPS
from app.storage.models import JobRecord, ProtocolDraftRevisionRecord, RuleSetRecord
from app.storage.repositories import JobRepository
from tests.v2.protocols.slice4_helpers import NOW, confirmed_fixture


def preserved_scope(app, data_paths, *, original_job=False, unresolved=False, medication_text=None):
    source, draft, spans = confirmed_fixture()
    if unresolved:
        referenced = source.parent_rule_catalog.items[0].source_span_ids[0]
        source = source.model_copy(update={"source_materials": [item.model_copy(update={"text": item.text + "（参见9.8节）"})
            if item.source_span_id == referenced else item for item in source.source_materials]})
    spans = dict(spans)
    materials = {item.source_span_id: item for item in source.source_materials}
    blocks = [StructureBlock(source_ref=span.source_ref, document_part=span.document_part,
        block_order=span.block_order, kind=BlockKind.PARAGRAPH,
        text=materials[span_id].text if span_id in materials else span.excerpt or "",
        table_path=span.table_path, section_index=span.section_index)
        for span_id, span in spans.items()]
    heading = StructureBlock(source_ref="body.p400", document_part="body", block_order=400,
        kind=BlockKind.PARAGRAPH, text="合并用药", outline_level=0)
    sentence = StructureBlock(source_ref="body.p401", document_part="body", block_order=401,
        kind=BlockKind.PARAGRAPH, text=medication_text or "筛选期间的治疗要求以本节为准。")
    blocks.extend([heading, sentence])
    for block in (heading, sentence):
        span_id = f"{source.extraction_snapshot_id}::{block.source_ref}"
        spans[span_id] = ProtocolSourceSpan(source_span_id=span_id,
            snapshot_id=source.extraction_snapshot_id, source_ref=block.source_ref,
            document_part=block.document_part, block_order=block.block_order,
            precision=SourceLocatorPrecision.BLOCK, alignment_status=AlignmentStatus.ALIGNED)
    raw = json.dumps([block.model_dump(mode="json") for block in blocks]).encode()
    digest = sha256(raw).hexdigest()
    storage_ref = f"blobs/protocol_blocks/{digest}.json"
    path = data_paths.blobs_dir / storage_ref
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    snapshot = ProtocolExtractionSnapshot(snapshot_id=source.extraction_snapshot_id,
        source_artifact_id="source-synthetic", source_sha256=source.protocol_file_sha256,
        parser_name="docx-ooxml", parser_version="test", status=ExtractionStatus.COMPLETED,
        coverage=ExtractionCoverage(paragraph_count=len(blocks), table_count=0, section_count=1,
            header_detected=False, footer_detected=False, nested_table_count=0, tracked_change_count=0),
        content_sha256=digest, content_storage_ref=storage_ref, created_at=NOW)
    service = app.state.protocol_workbench_service
    with app.state.session_factory() as session, session.begin():
        repo = JobRepository(session)
        repo.create_job(job_id="scope-current", job_type="protocol_deconstruction",
            payload={"session_kind": "first_deconstruction"})
        for step in PROTOCOL_DECONSTRUCTION_STEPS:
            repo.create_step(job_id="scope-current", step_id=step.step_id, name=step.name,
                depends_on=step.depends_on, waiting_user_kind=step.waiting_user_kind)
    service.seed_review_session("scope-current", source_input=source, draft=draft, source_spans=spans)
    target = "scope-current"
    if original_job:
        target = "scope-original"
        with app.state.session_factory() as session, session.begin():
            repo = JobRepository(session)
            repo.create_job(job_id=target, job_type="protocol_deconstruction", state="completed")
            repo.create_step(job_id=target, step_id="extract_structure", name="原结构", state="completed")
    with app.state.session_factory() as session, session.begin():
        JobRepository(session).create_checkpoint(checkpoint_id="scope-structure",
            job_id=target, step_id="extract_structure",
            payload={"extraction_snapshot": snapshot.model_dump(mode="json")})
    return source, snapshot, path


def frozen_counts(app):
    with app.state.session_factory() as session:
        return [session.scalar(select(func.count()).select_from(model))
                for model in (JobRecord, ProtocolDraftRevisionRecord, RuleSetRecord)]


@pytest.mark.parametrize("original_job", [False, True])
def test_scope_api_uses_same_snapshot_from_current_or_original_job_without_writes(build_app, data_paths, original_job):
    with TestClient(build_app()) as client:
        app = client.app
        source, snapshot, _ = preserved_scope(app, data_paths, original_job=original_job)
        before = frozen_counts(app)
        first = client.get("/api/v2/protocol/deconstructions/scope-current/draft/review-scope")
        assert first.status_code == 200, first.text
        view = first.json()
        assert view["snapshot_id"] == source.extraction_snapshot_id
        assert view["structure_sha256"] == snapshot.content_sha256
        assert view["clinical_adoption_applied"] is False
        medications = [item for item in view["candidates"] if item["scope_kind"] == "medication_section"]
        assert len(medications) == 1
        assert medications[0]["clinically_confirmed"] is False
        by_id = {item["source_span_id"]: item for item in view["source_records"]}
        assert by_id[medications[0]["source_span_ids"][-1]]["raw_text"] == "筛选期间的治疗要求以本节为准。"
        assert client.get(first.request.url).json() == view
        assert frozen_counts(app) == before


@pytest.mark.parametrize("fault", ["hash", "missing", "snapshot", "project"])
def test_scope_api_rejects_missing_or_wrong_source_instead_of_empty_success(build_app, data_paths, fault):
    with TestClient(build_app()) as client:
        app = client.app
        source, snapshot, path = preserved_scope(app, data_paths)
        if fault == "hash":
            path.write_bytes(b"[]")
        elif fault == "missing":
            path.unlink()
        elif fault == "snapshot":
            changed = snapshot.model_copy(update={"snapshot_id": "another-snapshot"})
            with app.state.session_factory() as session, session.begin():
                JobRepository(session).create_checkpoint(checkpoint_id="wrong-scope-structure",
                    job_id="scope-current", step_id="extract_structure",
                    payload={"extraction_snapshot": changed.model_dump(mode="json")})
        else:
            with app.state.session_factory() as session, session.begin():
                JobRepository(session).create_checkpoint(checkpoint_id="wrong-scope-project",
                    job_id="scope-current", step_id="freeze_deconstruction_input",
                    payload={"source_input": source.model_copy(update={"project_id": "another-project"}).model_dump(mode="json")})
        before = frozen_counts(app)
        response = client.get("/api/v2/protocol/deconstructions/scope-current/draft/review-scope")
        assert response.status_code == 409, response.text
        assert "REVIEW_SCOPE_SOURCE_UNAVAILABLE" in response.text
        assert frozen_counts(app) == before


def scope_proposal(view):
    return {"scope_content_hash": view["scope_content_hash"], "included_candidate_keys": [item["candidate_key"]
        for item in view["candidates"] if item["scope_kind"] in {"referenced_source", "medication_section"}],
        "exclusions": [], "additions": []}


def test_scope_selection_appends_history_preserves_rules_and_cannot_silently_publish(build_app, data_paths):
    from app.storage.repositories import ProtocolDraftRevisionRepository
    with TestClient(build_app()) as client:
        app = client.app
        preserved_scope(app, data_paths)
        path = "/api/v2/protocol/deconstructions/scope-current/draft"
        before = client.get(path).json()
        view = client.get(path + "/review-scope").json()
        assert view["editable"] and view["selection"] is None
        with app.state.session_factory() as session:
            row = session.get(ProtocolDraftRevisionRecord, before["revision_id"])
            old_payload = (row.payload_json, row.payload_sha256)
        proposal = scope_proposal(view)
        source = client.get(path + "/review-scope/sources", params={"q": "合并用药"})
        assert source.status_code == 200, source.text
        option, = source.json()["items"]
        assert len(option["source_span_ids"]) == 2
        proposal["additions"] = [{"scope_kind": "referenced_source", "source_span_ids": option["source_span_ids"],
            "official_codes": [view["candidates"][0]["official_codes"][0]], "reason": "由原文明确引用本章节。", "resolves_references": []}]
        saved = client.put(path + "/review-scope", json={"expected_revision_id": before["revision_id"], "proposal": proposal})
        assert saved.status_code == 200, saved.text
        result = saved.json()
        assert result["draft_revision_id"] != before["revision_id"]
        assert result["selection"]["additions"] == proposal["additions"]
        assert result["clinical_adoption_applied"] is False
        assert len(result["additional_source_records"]) == 2
        after = client.get(path).json()
        assert after["review_scope_pending"] is True
        for field in ("proposed_rules", "component_drafts", "proposed_workflow_stages", "source_refs", "variable_definitions"):
            assert after["content"].get(field) == before["content"].get(field)
        counts = frozen_counts(app)
        replay = client.put(path + "/review-scope", json={"expected_revision_id": result["draft_revision_id"], "proposal": proposal})
        assert replay.status_code == 200, replay.text
        assert replay.json()["draft_revision_id"] == result["draft_revision_id"]
        assert frozen_counts(app) == counts
        stale = client.put(path + "/review-scope", json={"expected_revision_id": before["revision_id"], "proposal": proposal})
        assert stale.status_code == 409
        publication = client.post("/api/v2/protocol/deconstructions/scope-current/publish", json={"idempotency_key": "scope-not-adopted"})
        assert publication.status_code == 409, publication.text
        assert "review_scope_not_applied" in publication.text.lower()
        assert frozen_counts(app) == counts
        with app.state.session_factory() as session:
            row = session.get(ProtocolDraftRevisionRecord, before["revision_id"])
            assert (row.payload_json, row.payload_sha256) == old_payload
            assert ProtocolDraftRevisionRepository(session).get(after["revision_id"]).review_scope_selection is not None


@pytest.mark.parametrize("fault", ["scope_hash", "missing_reason", "unknown_source", "unknown_code", "fixed_catalog", "cancel"])
def test_scope_selection_rejects_bad_choices_without_new_revision(build_app, data_paths, fault):
    with TestClient(build_app()) as client:
        app = client.app
        preserved_scope(app, data_paths)
        path = "/api/v2/protocol/deconstructions/scope-current/draft/review-scope"
        view = client.get(path).json()
        proposal = scope_proposal(view)
        if fault == "scope_hash":
            proposal["scope_content_hash"] = "0" * 64
        elif fault == "missing_reason":
            proposal["included_candidate_keys"] = []
        elif fault == "fixed_catalog":
            proposal["included_candidate_keys"].append(view["candidates"][0]["candidate_key"])
        elif fault == "cancel":
            with app.state.session_factory() as session, session.begin():
                session.get(JobRecord, "scope-current").cancel_requested = True
        else:
            ids = ["other-snapshot::body.p400"] if fault == "unknown_source" else view["candidates"][0]["source_span_ids"]
            proposal["additions"] = [{"scope_kind": "referenced_source", "source_span_ids": ids,
                "official_codes": ["IN-99" if fault == "unknown_code" else view["candidates"][0]["official_codes"][0]], "reason": "原文指定"}]
        before = frozen_counts(app)
        response = client.put(path, json={"expected_revision_id": view["draft_revision_id"], "proposal": proposal})
        assert response.status_code == 409, response.text
        assert frozen_counts(app) == before


def test_exclusion_reason_and_edit_restore_keep_scope_choice_and_history(build_app, data_paths):
    from app.services.protocol_draft_service import ProtocolDraftService
    from app.storage.repositories import ProtocolDraftRevisionRepository
    with TestClient(build_app()) as client:
        app = client.app
        preserved_scope(app, data_paths)
        path = "/api/v2/protocol/deconstructions/scope-current/draft"
        view = client.get(path + "/review-scope").json()
        proposal = scope_proposal(view)
        removed = proposal["included_candidate_keys"].pop()
        proposal["exclusions"] = [{"candidate_key": removed, "reason": "本次先不纳入，保留原章节待补核对。"}]
        saved = client.put(path + "/review-scope", json={"expected_revision_id": view["draft_revision_id"], "proposal": proposal})
        assert saved.status_code == 200, saved.text
        draft = client.get(path).json()
        edited = client.put(path, json={"expected_revision_id": draft["revision_id"], "draft": draft["content"]})
        assert edited.status_code == 200, edited.text
        assert edited.json()["review_scope_pending"] is True
        with app.state.session_factory() as session, session.begin():
            repo = ProtocolDraftRevisionRepository(session)
            old = repo.get(saved.json()["draft_revision_id"])
            new = repo.get(edited.json()["revision_id"])
            assert old.review_scope_selection == new.review_scope_selection
            restored = ProtocolDraftService(session).restore_draft(draft_id=old.draft_id,
                restore_from_revision_id=old.revision_id, expected_revision_id=new.revision_id,
                actor="构建者（验证）", created_at=NOW)
            assert restored.review_scope_selection == old.review_scope_selection


def test_manual_assignment_consumes_only_the_selected_unresolved_reference(build_app, data_paths):
    with TestClient(build_app()) as client:
        app = client.app
        preserved_scope(app, data_paths, unresolved=True)
        path = "/api/v2/protocol/deconstructions/scope-current/draft/review-scope"
        view = client.get(path).json()
        diagnostic, = [item for item in view["diagnostics"] if item["kind"] == "reference_unresolved"]
        assert diagnostic["resolved_by_manual_selection"] is False
        medication = next(item for item in view["candidates"] if item["scope_kind"] == "medication_section")
        proposal = scope_proposal(view)
        proposal["additions"] = [{"scope_kind": "referenced_source", "source_span_ids": medication["source_span_ids"],
            "official_codes": diagnostic["related_official_codes"], "reason": "本次手工指定对应的原文范围。",
            "resolves_references": [diagnostic["diagnostic_key"]]}]
        saved = client.put(path, json={"expected_revision_id": view["draft_revision_id"], "proposal": proposal})
        assert saved.status_code == 200, saved.text
        result = saved.json()
        assert result["diagnostics"][0]["resolved_by_manual_selection"] is True
        assert result["clinical_adoption_applied"] is False
        assert client.get(path).json()["diagnostics"][0]["resolved_by_manual_selection"] is True
        proposal["additions"][0]["resolves_references"] = ["not-a-real-reference"]
        before = frozen_counts(app)
        rejected = client.put(path, json={"expected_revision_id": result["draft_revision_id"], "proposal": proposal})
        assert rejected.status_code == 409, rejected.text
        assert frozen_counts(app) == before
