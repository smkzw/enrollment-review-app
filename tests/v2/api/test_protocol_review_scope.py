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


def preserved_scope(app, data_paths, *, original_job=False):
    source, draft, spans = confirmed_fixture()
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
        kind=BlockKind.PARAGRAPH, text="筛选期间的治疗要求以本节为准。")
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
