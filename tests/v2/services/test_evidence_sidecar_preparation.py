"""风险/定位准备与增量沿用的跨版本回归。"""

from __future__ import annotations

from app.domain.contracts.enums import (
    OcrRiskLevel,
    OcrRiskReviewDecision,
    PageArtifactStatus,
    SnapshotMemberOrigin,
    SnapshotStatus,
    UploadMode,
)
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    EvidenceSnapshotMember,
    SourceDocumentMetadataRevision,
)
from app.domain.contracts.evidence_locator import CorrectionRecord, OCRRiskReview
from app.domain.contracts.evidence_processing import (
    EvidenceProcessingRevision,
    EvidenceProcessingRevisionPage,
)
from app.domain.publication import (
    evidence_processing_manifest_hash,
    evidence_snapshot_collection_hash,
)
from app.evidence.risk import OCR_RISK_RULE_VERSION
from app.services.evidence_activation_service import EvidenceActivationService
from app.services.evidence_revision_workflow import (
    EvidenceRevisionBuildRequest,
    EvidenceRevisionWorkflow,
)
from app.services.evidence_sidecar_preparation import (
    EvidenceSidecarPreparationService,
    SOURCE_LINE_TARGET_PREFIX,
)
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    CorrectionRepository,
    OCRRiskReviewRepository,
    OCRRiskScanRepository,
)
from app.storage.evidence_locator_models import (
    EvidenceLocatorArtifactRecord,
    OCRRiskReviewRecord,
)
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentMetadataRevisionRepository,
    SourceDocumentRepository,
)
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrPageRepository,
    PageArtifactRepository,
)
from tests.v2.storage.test_ocr_repositories import (
    FIXED_UTC,
    make_artifact,
    make_blob,
    make_ocr_page,
    make_version,
    sha,
)
from tests.v2.storage.test_slice44_repositories import RAW_TEXT, _correction, _seed_metadata


def test_incremental_reuses_unchanged_reviews_and_corrections_on_new_base(
    revision_stack, session_factory
):
    session, _fixture, keys = revision_stack
    session.commit()
    preparation = EvidenceSidecarPreparationService(
        session_factory, keys["artifact_store"]
    )

    with session_factory() as current, current.begin():
        _seed_metadata(current, keys)
    preparation.prepare("rev-1")
    with session_factory() as current, current.begin():
        scans = OCRRiskScanRepository(current).list_by_page("op-1")
        scan = next(
            item for item in scans if item.scanner_rule_version == OCR_RISK_RULE_VERSION
        )
        for flag in scan.flags:
            if flag.level == OcrRiskLevel.BLOCKING:
                OCRRiskReviewRepository(current).create(
                    OCRRiskReview(
                        review_id=f"rv-prior-{flag.risk_id}",
                        risk_flag_id=f"{scan.scan_id}:{flag.risk_id}",
                        decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
                        reason="已与原文核对",
                        actor="tester",
                        base_processing_revision_id="rev-1",
                        expected_revision=1,
                        created_at=FIXED_UTC,
                    )
                )
        CorrectionRepository(current).create(_correction(keys))
        raw_ocr_locators = current.query(EvidenceLocatorArtifactRecord).all()
        assert raw_ocr_locators
        source_line_locators = [
            item
            for item in raw_ocr_locators
            if item.target_id.startswith(SOURCE_LINE_TARGET_PREFIX)
        ]
        assert source_line_locators
        assert any(item.excerpt in RAW_TEXT for item in source_line_locators)
        assert all(item.source_layer == "raw_ocr" for item in raw_ocr_locators)
        assert all(item.precision == "text_range" for item in raw_ocr_locators)
        assert all(item.bbox_x0 is None for item in raw_ocr_locators)
        assert all(item.bbox_y0 is None for item in raw_ocr_locators)
        assert all(item.bbox_x1 is None for item in raw_ocr_locators)
        assert all(item.bbox_y1 is None for item in raw_ocr_locators)

    workflow = EvidenceRevisionWorkflow(session_factory, keys["artifact_store"])
    first_candidate = workflow.start(
        EvidenceRevisionBuildRequest(
            evidence_snapshot_id="snap-1",
            base_processing_revision_id="rev-1",
            project_id=keys["project_id"],
            subject_id=keys["subject_id"],
            review_episode_id=keys["episode_id"],
            expected_revision=1,
            idempotency_key="build-prior",
            created_by="tester",
        )
    )
    first_built = workflow.run_build(first_candidate.candidate_id)
    with session_factory() as current:
        complete = CompleteEvidenceProcessingRevisionRepository(
            current, keys["artifact_store"]
        ).get(first_built.complete_revision_id)
        source_line_ids = {
            item.locator_id
            for item in current.query(EvidenceLocatorArtifactRecord).all()
            if item.target_id.startswith(SOURCE_LINE_TARGET_PREFIX)
        }
    assert source_line_ids <= set(complete.locator_ids)
    EvidenceActivationService(session_factory, keys["artifact_store"]).activate(
        target_snapshot_id="snap-1",
        target_revision_id=first_built.complete_revision_id,
        expected_revision=1,
        actor="tester",
        reason="启用上一资料版本",
        candidate_id=first_built.candidate_id,
    )

    new_text = "clinical narrative without structured values"
    new_blob = make_blob(b"new-document")
    with session_factory() as current, current.begin():
        scope = (keys["project_id"], keys["subject_id"], keys["episode_id"])
        BlobRepository(current).get_or_create_by_sha256(new_blob)
        SourceDocumentRepository(current).create_version(
            make_version(
                version_id="doc-2",
                logical_id="log-2",
                blob_sha=new_blob.sha256,
                scope=scope,
                page_count=1,
            )
        )
        profile_sha256 = OcrPageRepository(current).get("op-1").ocr_profile_sha256
        PageArtifactRepository(current).get_or_create(
            make_artifact(
                artifact_id="pa-2",
                version_id="doc-2",
                source_sha=new_blob.sha256,
                page_input="8" * 64,
                page_image="8" * 64,
            )
        )
        OcrPageRepository(current).create(
            make_ocr_page(
                page_id="op-2",
                artifact_id="pa-2",
                raw_text=new_text,
                page_input="8" * 64,
                source_sha=new_blob.sha256,
                profile_sha=profile_sha256,
            )
        )
        SourceDocumentMetadataRevisionRepository(current).append(
            SourceDocumentMetadataRevision(
                metadata_revision_id="mdr-2",
                source_document_version_id="doc-2",
                document_type="other",
                source_party="hospital",
                reason="确认资料类型",
                is_auto_suggestion=False,
                revision=1,
                created_at=FIXED_UTC,
                created_by="tester",
            )
        )
        members = [
            EvidenceSnapshotMember(
                member_id="m-2-inherited",
                snapshot_id="snap-2",
                logical_document_id="log-1",
                source_document_version_id="doc-1",
                origin=SnapshotMemberOrigin.INHERITED,
            ),
            EvidenceSnapshotMember(
                member_id="m-2-added",
                snapshot_id="snap-2",
                logical_document_id="log-2",
                source_document_version_id="doc-2",
                origin=SnapshotMemberOrigin.ADDED,
            ),
        ]
        EvidenceSnapshotRepository(current).create_incremental(
            EvidenceSnapshot(
                evidence_snapshot_id="snap-2",
                project_id=keys["project_id"],
                subject_id=keys["subject_id"],
                review_episode_id=keys["episode_id"],
                upload_mode=UploadMode.INCREMENTAL,
                prior_snapshot_id="snap-1",
                comparison_snapshot_id="snap-1",
                members=members,
                collection_sha256=evidence_snapshot_collection_hash(
                    members=[
                        (item.logical_document_id, item.source_document_version_id)
                        for item in members
                    ]
                ),
                status=SnapshotStatus.STAGED,
                created_at=FIXED_UTC,
                created_by="tester",
            )
        )
        EvidenceSnapshotRepository(current).transition_status(
            "snap-2",
            event="worker_start",
            new_status=SnapshotStatus.PROCESSING,
            actor="tester",
            reason="处理增量资料",
        )
        entries = [
            EvidenceProcessingRevisionPage(
                entry_id="e2-1",
                position=1,
                source_document_version_id="doc-1",
                page_number=1,
                page_artifact_id="pa-1",
                ocr_page_id="op-1",
                status=PageArtifactStatus.SUCCEEDED,
            ),
            EvidenceProcessingRevisionPage(
                entry_id="e2-2",
                position=2,
                source_document_version_id="doc-2",
                page_number=1,
                page_artifact_id="pa-2",
                ocr_page_id="op-2",
                status=PageArtifactStatus.SUCCEEDED,
            ),
        ]
        manifest_hash = evidence_processing_manifest_hash(
            entries=[
                (
                    item.source_document_version_id,
                    item.page_number,
                    item.original_frame,
                    item.page_artifact_id,
                    item.ocr_page_id,
                    item.status.value,
                )
                for item in entries
            ]
        )
        EvidenceProcessingRevisionRepository(current).create(
            EvidenceProcessingRevision(
                evidence_processing_revision_id="rev-2",
                evidence_snapshot_id="snap-2",
                project_id=keys["project_id"],
                subject_id=keys["subject_id"],
                review_episode_id=keys["episode_id"],
                manifest=entries,
                manifest_sha256=manifest_hash,
                created_at=FIXED_UTC,
                created_by="tester",
            )
        )

    preparation.prepare("rev-2")
    with session_factory() as current:
        review_rows = current.query(OCRRiskReviewRecord).filter_by(
            base_processing_revision_id="rev-2"
        ).all()
        carried_reviews = [
            OCRRiskReviewRepository(current).get(item.review_id) for item in review_rows
        ]
        carried_corrections = [
            item
            for item in CorrectionRepository(current).list_by_page("op-1")
            if item.base_processing_revision_id == "rev-2"
        ]
    assert carried_reviews
    assert all(item.actor == "系统沿用" for item in carried_reviews)
    assert len(carried_corrections) == 1
    assert carried_corrections[0].corrected_text == "5.60"

    second_candidate = workflow.start(
        EvidenceRevisionBuildRequest(
            evidence_snapshot_id="snap-2",
            base_processing_revision_id="rev-2",
            project_id=keys["project_id"],
            subject_id=keys["subject_id"],
            review_episode_id=keys["episode_id"],
            expected_revision=2,
            idempotency_key="build-incremental",
            created_by="tester",
        )
    )
    second_built = workflow.run_build(second_candidate.candidate_id)
    assert second_built.complete_revision_id is not None
