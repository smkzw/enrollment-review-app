"""0019 选择性视觉观察侧车迁移。

覆盖：
- 升级创建 ``selective_vision_observations`` 与关键约束/索引/外键；
- 空库可降级回 0018；
- 含不可变历史时拒绝有损降级；
- 新表登记进 ``PHASE5_V2_TABLES``，避免污染 0007-0012 历史 metadata 快照。
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text

from app.domain.contracts.selective_vision_observation import (
    SELECTIVE_VISION_PROMPT_VERSION,
    SelectiveVisionObservationRecord,
    SelectiveVisionObservationStatus,
    build_observation_identity_sha256,
    build_prompt_sha256,
    build_risk_reasons_sha256,
)
from app.domain.publication import evidence_processing_manifest_hash
from app.storage.codecs import encode_contract, to_utc_naive
from app.storage.db import build_engine
from app.storage.migrate import MigrationFailure, MigrationManager, resolve_head_revision
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrPageRepository,
    OCRProfileRepository,
    PageArtifactRepository,
)
from app.storage.selective_vision_observation_models import SelectiveVisionObservationORM
from app.storage.repositories import persist_fixture
from tests.v2.storage.test_migration_0008 import PHASE5_V2_TABLES
from tests.v2.storage.test_ocr_repositories import (
    FIXED_UTC,
    make_artifact,
    make_blob,
    make_ocr_page,
    make_profile,
    make_revision,
    make_snapshot,
    make_version,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES
from app.domain.contracts.enums import SnapshotMemberOrigin, SnapshotStatus
from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
from app.domain.contracts.enums import PageArtifactStatus
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)


_MIGRATION_0019_TABLES = frozenset({"selective_vision_observations"})
_IMAGE_SHA = "b" * 64
_PROMPT_SHA = build_prompt_sha256(
    prompt_version=SELECTIVE_VISION_PROMPT_VERSION,
    system_prompt="sys",
    user_prompt="user",
)
_REASONS = ["scan_or_image_only"]
_REASONS_SHA = build_risk_reasons_sha256(_REASONS)
_IDENTITY = build_observation_identity_sha256(
    page_artifact_id="pa-1",
    page_image_sha256=_IMAGE_SHA,
    plan_version=SELECTIVE_VISION_PROMPT_VERSION,
    model_id="test-vlm",
    prompt_sha256=_PROMPT_SHA,
    risk_reasons_sha256=_REASONS_SHA,
)


def test_0019_tables_are_registered_for_historical_metadata_snapshots() -> None:
    """后续 Phase 5 表不得污染 0007-0012 的历史 metadata 校验。"""
    assert _MIGRATION_0019_TABLES <= PHASE5_V2_TABLES


def test_0019_adds_observation_table_and_empty_downgrade(data_paths):
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    assert manager.read_revision(data_paths.db_path) == resolve_head_revision()

    engine = build_engine(data_paths.db_path)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "selective_vision_observations" in tables
        cols = {c["name"] for c in inspector.get_columns("selective_vision_observations")}
        assert {
            "observation_id",
            "page_artifact_id",
            "source_document_version_id",
            "source_ref",
            "page_ordinal",
            "page_image_sha256",
            "ocr_page_id",
            "ocr_raw_text_sha256",
            "plan_version",
            "risk_reasons_json",
            "risk_reasons_sha256",
            "model_id",
            "prompt_version",
            "prompt_sha256",
            "status",
            "observation_text",
            "finish_reason",
            "usage_json",
            "failure_kind",
            "observation_identity_sha256",
            "payload_json",
            "payload_sha256",
            "created_at",
        } <= cols
        fks = inspector.get_foreign_keys("selective_vision_observations")
        referred = {fk["referred_table"] for fk in fks}
        assert "page_artifacts" in referred
        assert "source_document_versions_v2" in referred
        assert "ocr_pages" in referred
        checks = {
            item["name"] or ""
            for item in inspector.get_check_constraints("selective_vision_observations")
        }
        assert any("ck_svo_status" in name for name in checks)
        assert any("ck_svo_status_payload" in name for name in checks)
        assert any("ck_svo_ocr_pair" in name for name in checks)
        indexes = {idx["name"] for idx in inspector.get_indexes("selective_vision_observations")}
        assert "uq_svo_identity_succeeded" in indexes
        assert "ix_svo_page_artifact_id" in indexes
    finally:
        engine.dispose()

    manager.downgrade("0018")
    engine = build_engine(data_paths.db_path)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "selective_vision_observations" not in tables
        assert "fact_correction_commits" in tables
        assert manager.read_revision(data_paths.db_path) == "0018"
    finally:
        engine.dispose()

    manager.upgrade("head")
    assert manager.read_revision(data_paths.db_path) == resolve_head_revision()


def _seed_page_stack(session, fixture) -> dict[str, str]:
    project_id = fixture.project.project_id
    subject_id = fixture.subject.subject_id
    episode_id = fixture.review_episode.review_episode_id
    scope = (project_id, subject_id, episode_id)
    blob = make_blob(b"pdf-bytes-0019")
    BlobRepository(session).get_or_create_by_sha256(blob)
    version = make_version(
        version_id="doc-1", logical_id="log-1", blob_sha=blob.sha256, scope=scope
    )
    SourceDocumentRepository(session).create_version(version)
    snapshot = make_snapshot(
        snapshot_id="snap-1",
        scope=scope,
        members=[("log-1", "doc-1", SnapshotMemberOrigin.ADDED)],
    )
    EvidenceSnapshotRepository(session).create_full(snapshot)
    EvidenceSnapshotRepository(session).transition_status(
        "snap-1",
        event="worker_start",
        new_status=SnapshotStatus.PROCESSING,
        actor="tester",
        reason="start",
    )
    profile = OCRProfileRepository(session).get_or_create(make_profile())
    PageArtifactRepository(session).get_or_create(
        make_artifact(version_id="doc-1", page_image=_IMAGE_SHA, page_input=_IMAGE_SHA)
    )
    page = OcrPageRepository(session).create(
        make_ocr_page(
            page_id="op-1",
            artifact_id="pa-1",
            profile_sha=profile.profile_sha256,
            page_input=_IMAGE_SHA,
        )
    )
    entry = EvidenceProcessingRevisionPage(
        entry_id="e1",
        position=1,
        source_document_version_id="doc-1",
        page_number=1,
        original_frame=None,
        page_artifact_id="pa-1",
        ocr_page_id="op-1",
        status=PageArtifactStatus.SUCCEEDED,
    )
    manifest_hash = evidence_processing_manifest_hash(
        entries=[("doc-1", 1, None, "pa-1", "op-1", PageArtifactStatus.SUCCEEDED.value)]
    )
    EvidenceProcessingRevisionRepository(session).create(
        make_revision(
            {
                "project_id": project_id,
                "subject_id": subject_id,
                "episode_id": episode_id,
                "entry": entry,
                "manifest_hash": manifest_hash,
            }
        )
    )
    session.flush()
    return {
        "ocr_page_id": page.ocr_page_id,
        "raw_text_sha256": page.raw_text_sha256,
    }


def test_0019_downgrade_refuses_populated_observations(
    data_paths, session_factory, migrated_engine
):
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    with session_factory() as session, session.begin():
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        seeded = _seed_page_stack(session, fixture)
        record = SelectiveVisionObservationRecord(
            observation_id="svo-m19-1",
            page_artifact_id="pa-1",
            source_document_version_id="doc-1",
            source_ref="pa-1",
            page_ordinal=1,
            page_image_sha256=_IMAGE_SHA,
            ocr_page_id=seeded["ocr_page_id"],
            ocr_raw_text_sha256=seeded["raw_text_sha256"],
            plan_version=SELECTIVE_VISION_PROMPT_VERSION,
            risk_reasons=list(_REASONS),
            risk_reasons_sha256=_REASONS_SHA,
            model_id="test-vlm",
            prompt_version=SELECTIVE_VISION_PROMPT_VERSION,
            prompt_sha256=_PROMPT_SHA,
            status=SelectiveVisionObservationStatus.SUCCEEDED,
            observation_text="source_ref=pa-1\nvisible content",
            finish_reason="stop",
            usage={"prompt_tokens": 1},
            failure_kind=None,
            observation_identity_sha256=_IDENTITY,
            created_at=FIXED_UTC,
        )
        payload_json, payload_sha256 = encode_contract(record)
        session.add(
            SelectiveVisionObservationORM(
                observation_id=record.observation_id,
                page_artifact_id=record.page_artifact_id,
                source_document_version_id=record.source_document_version_id,
                source_ref=record.source_ref,
                page_ordinal=record.page_ordinal,
                page_image_sha256=record.page_image_sha256,
                ocr_page_id=record.ocr_page_id,
                ocr_raw_text_sha256=record.ocr_raw_text_sha256,
                plan_version=record.plan_version,
                risk_reasons_json=list(record.risk_reasons),
                risk_reasons_sha256=record.risk_reasons_sha256,
                model_id=record.model_id,
                prompt_version=record.prompt_version,
                prompt_sha256=record.prompt_sha256,
                status=record.status.value,
                observation_text=record.observation_text,
                finish_reason=record.finish_reason,
                usage_json=dict(record.usage),
                failure_kind=record.failure_kind,
                observation_identity_sha256=record.observation_identity_sha256,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(record.created_at),
            )
        )

    migrated_engine.dispose()
    with pytest.raises(MigrationFailure, match="0019"):
        manager.downgrade("0018")
    assert manager.read_revision(data_paths.db_path) == resolve_head_revision()

    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM selective_vision_observations")
            ).scalar_one()
        assert count == 1
    finally:
        engine.dispose()
