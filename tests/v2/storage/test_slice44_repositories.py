"""Slice 4.4 追加仓储确定性测试（WP-44A，运行于 head=0010）。

覆盖：定位旁路工件身份幂等/真实性；风险扫描三元组幂等与冲突；风险核对；校对
supersede 链与原文范围回验；被提及资料两层修订链；激活事件连续序号；处理候选
状态机（终态/非法转换/幂等键冲突/状态投影）；完整处理修订闭包（base 页清单逐项
相等、旁路引用作用域、校对重叠冲突、base/complete 辨别读取、关联镜像校验）。
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import delete, select

from app.domain.contracts.enums import (
    ActivationEventKind,
    DisambiguationOutcome,
    EvidenceProcessingCandidateStatus,
    LocatorPrecision,
    LocatorSourceLayer,
    OcrRiskKind,
    OcrRiskReviewDecision,
    ReferencedDocumentResolutionStatus,
    SnapshotMemberOrigin,
    SnapshotStatus,
)
from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    EvidenceSnapshotMember,
)
from app.domain.contracts.evidence_locator import (
    CompleteEvidenceProcessingRevision,
    CorrectionRecord,
    EvidenceActivationEvent,
    EvidenceLocatorArtifact,
    EvidenceProcessingCandidate,
    EvidenceProcessingCandidateEvent,
    OCRRiskReview,
    OCRRiskScan,
    ReferencedDocumentResolutionRevision,
    ReferencedDocumentRevision,
    activation_command_hash,
    locator_anchor_hash,
    processing_candidate_input_hash,
)
from app.domain.contracts.evidence_processing import EvidenceProcessingRevision
from app.domain.contracts.ocr import CoordinateFrame, OcrRiskFlag
from app.domain.publication import (
    evidence_processing_manifest_hash,
    evidence_snapshot_collection_hash,
)
from app.storage.codecs import PersistedContractInvalid
from app.storage.evidence_locator_models import (
    EvidenceProcessingCandidateRecord,
    OCRRiskFlagRecord,
    OCRRiskScanRecord,
)
from app.storage.evidence_locator_repositories import (
    CandidateIdempotencyConflictError,
    CandidateStateTransitionError,
    CompleteEvidenceProcessingRevisionRepository,
    CorrectionOverlapError,
    CorrectionRepository,
    EvidenceActivationEventRepository,
    EvidenceLocatorRepository,
    EvidenceProcessingCandidateRepository,
    LocatorIdentityError,
    OcrRevisionKindError,
    OCRRiskReviewRepository,
    OCRRiskScanRepository,
    ReferencedDocumentRepository,
    RevisionClosureError,
    RiskScanConflictError,
    Slice44RepositoryError,
)
from app.storage.evidence_models import (
    SourceDocumentVersionV2Record,
)
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentMetadataRevisionRepository,
    SourceDocumentRepository,
)
from app.storage.ocr_models import (
    EvidenceProcessingRevisionPageRecord,
    EvidenceProcessingRevisionRecord,
    OCRPageRecord,
)
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrPageRepository,
    OCRProfileRepository,
    PageArtifactRepository,
)
from app.storage.repositories import DuplicateRecordError, InvalidReferenceError
from tests.v2.storage.test_ocr_repositories import (
    FIXED_UTC,
    make_artifact,
    make_blob,
    make_ocr_page,
    make_profile,
    make_version,
    sha,
)

RAW_TEXT = "ALT 5.6 mmol/L 且 AST 3.5 mmol/L"


@pytest.fixture
def seeded(session_factory):
    """head 库会话 + fixture；每个测试独立回滚。"""
    from app.storage.repositories import persist_fixture
    from tests.v2.storage.test_repositories_roundtrip import FIXTURES

    with session_factory() as session:
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        session.commit()
        yield session, fixture
        session.rollback()


@pytest.fixture
def artifact_store(data_paths):
    """同一临时数据根上的内容寻址工件库（供原生文本/坐标真实性证明）。"""
    from app.evidence.artifacts import ArtifactStore

    return ArtifactStore(data_paths)


@pytest.fixture
def revision_stack(seeded, artifact_store):
    """blob/资料版本(单页)/快照/Profile/页产物/OCR 页（原文=RAW_TEXT）+ base 修订 rev-1。"""
    from app.domain.contracts.enums import PageArtifactStatus
    from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
    from app.domain.publication import evidence_processing_manifest_hash
    from app.storage.ocr_repositories import (
        EvidenceProcessingRevisionRepository,
        OcrPageRepository,
        OCRProfileRepository,
        PageArtifactRepository,
    )

    session, fixture = seeded
    project_id, subject_id, episode_id = (
        fixture.project.project_id,
        fixture.subject.subject_id,
        fixture.review_episode.review_episode_id,
    )
    scope = (project_id, subject_id, episode_id)
    blob = make_blob(b"pdf-bytes")
    BlobRepository(session).get_or_create_by_sha256(blob)
    version = make_version(
        version_id="doc-1", logical_id="log-1", blob_sha=blob.sha256, scope=scope,
        page_count=1,  # 单页资料：快照成员页数必须与页清单精确一致（Fix 1）
    )
    SourceDocumentRepository(session).create_version(version)
    snapshot = EvidenceSnapshot(
        evidence_snapshot_id="snap-1",
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode="full",
        prior_snapshot_id=None,
        comparison_snapshot_id=None,
        members=[
            EvidenceSnapshotMember(
                member_id="m-1",
                snapshot_id="snap-1",
                logical_document_id="log-1",
                source_document_version_id="doc-1",
                origin=SnapshotMemberOrigin.ADDED,
            )
        ],
        collection_sha256=evidence_snapshot_collection_hash(
            members=[("log-1", "doc-1")]
        ),
        status=SnapshotStatus.STAGED,
        created_at=FIXED_UTC,
        created_by="tester",
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
    PageArtifactRepository(session).get_or_create(make_artifact(version_id="doc-1"))
    OcrPageRepository(session).create(
        make_ocr_page(
            page_id="op-1",
            artifact_id="pa-1",
            raw_text=RAW_TEXT,
            profile_sha=profile.profile_sha256,
        )
    )
    session.flush()
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
    keys = {
        "project_id": project_id,
        "subject_id": subject_id,
        "episode_id": episode_id,
        "entry": entry,
        "manifest_hash": manifest_hash,
        "fixture": fixture,
        "artifact_store": artifact_store,
    }
    EvidenceProcessingRevisionRepository(session).create(
        EvidenceProcessingRevision(
            evidence_processing_revision_id="rev-1",
            evidence_snapshot_id="snap-1",
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            manifest=[entry],
            manifest_sha256=manifest_hash,
            status="ready",
            is_activatable=False,
            created_at=FIXED_UTC,
            created_by="tester",
        )
    )
    session.flush()
    return session, fixture, keys


# --------------------------------------------------------------------------- 定位


def _locator(keys, **overrides):
    base = {
        "locator_id": "loc-1",
        "page_artifact_id": "pa-1",
        "ocr_page_id": "op-1",
        "source_document_version_id": "doc-1",
        "page_number": 1,
        "source_layer": "raw_ocr",
        "source_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "target_id": "target-1",
        "precision": "text_range",
        "text_start": 0,
        "text_end": 5,
        "excerpt": "ALT 5",
        "disambiguation": "unique_match",
        "locator_algorithm_version": "v1",
        "authenticity": "degraded",
        "degradation_reason": "text-only 路线无真实坐标",
        "created_at": FIXED_UTC,
    }
    base.update(overrides)
    return EvidenceLocatorArtifact(**base)


def test_locator_append_and_roundtrip(revision_stack):
    session, _fixture, keys = revision_stack
    repo = EvidenceLocatorRepository(session)
    repo.create(_locator(keys))
    got = repo.get("loc-1")
    assert got.target_id == "target-1"
    assert got.source_layer == LocatorSourceLayer.RAW_OCR


def test_locator_get_or_none_replays_source_proof(revision_stack):
    """可选读取与强制读取必须执行相同的同源文本回放校验。"""
    session, _fixture, keys = revision_stack
    repo = EvidenceLocatorRepository(session)
    repo.create(_locator(keys))
    page = session.get(OCRPageRecord, "op-1")
    page.raw_text = "ALT 6.5 mmol/L 且 AST 3.5 mmol/L"
    session.flush()
    with pytest.raises(LocatorIdentityError, match="摘录与 OCRPage.raw_text"):
        repo.get_or_none("loc-1")


def test_locator_raw_ocr_hash_must_match_ocr_page(revision_stack):
    session, _fixture, keys = revision_stack
    repo = EvidenceLocatorRepository(session)
    with pytest.raises(LocatorIdentityError, match="raw_ocr 哈希"):
        repo.create(_locator(keys, source_text_sha256="b" * 64))


def test_locator_occurrence_identity_collision_rejected(revision_stack):
    """同页同来源同目标同算法版本的同 occurrence 只能有一个 locator_id。"""
    session, _fixture, keys = revision_stack
    repo = EvidenceLocatorRepository(session)
    repo.create(_locator(keys))
    with pytest.raises(LocatorIdentityError, match="身份碰撞"):
        repo.create(_locator(keys, locator_id="loc-2"))


def test_locator_duplicate_id_rejected(revision_stack):
    session, _fixture, keys = revision_stack
    repo = EvidenceLocatorRepository(session)
    repo.create(_locator(keys))
    with pytest.raises(DuplicateRecordError, match="已存在"):
        repo.create(_locator(keys))


def test_locator_bbox_requires_same_source_sidecar(revision_stack):
    """bbox 必须携带同源坐标 sidecar 哈希（合同级拒绝无 sidecar 的 bbox）。"""
    session, _fixture, keys = revision_stack
    repo = EvidenceLocatorRepository(session)
    frame = CoordinateFrame(
        space="page_image_pixels",
        page_width=595.0,
        page_height=842.0,
        rotation=0,
        transform_version="t/v1",
    )
    with pytest.raises(Exception) as exc:
        repo.create(
            _locator(
                keys,
                locator_id="loc-bbox",
                precision="bbox",
                bbox=BoundingBox(x0=1, y0=1, x1=50, y1=50),
                coordinate_frame=frame,
                authenticity="authenticated",
                sidecar_sha256=None,
                text_start=None,
                text_end=None,
                excerpt=None,
            )
        )
    assert "sidecar" in str(exc.value)


def test_locator_effective_text_requires_revision(revision_stack):
    session, _fixture, keys = revision_stack
    repo = EvidenceLocatorRepository(session)
    with pytest.raises(Exception) as exc:
        repo.create(
            _locator(
                keys,
                locator_id="loc-eff",
                source_layer="effective_text",
                processing_revision_id=None,
                effective_text_sha256=None,
            )
        )
    assert "处理修订" in str(exc.value)


# --------------------------------------------------------------------------- 风险扫描


def _flag(risk_id="r1", *, kind="numeric_value", level="blocking", text="5.6",
          start=4, end=7, rule_version="rules/v1"):
    return OcrRiskFlag(
        risk_id=risk_id,
        kind=kind,
        level=level,
        text=text,
        text_start=start,
        text_end=end,
        detail=None,
        rule_version=rule_version,
    )


def _scan(keys, **overrides):
    from app.domain.publication import canonical_hash

    values = {
        "scan_id": "scan-1",
        "ocr_page_id": "op-1",
        "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "scanner_rule_version": "rules/v1",
        "coverage_status": "complete",
        "created_at": FIXED_UTC,
    }
    values.update(overrides)
    # flag 的 rule_version 必须与扫描的 scanner_rule_version 一致（扫描器版本镜像）。
    flags = values.get("flags") or [_flag(rule_version=values["scanner_rule_version"])]
    values["flags"] = flags
    values["flags_sha256"] = canonical_hash(
        [
            {
                "risk_id": f.risk_id,
                "kind": f.kind.value,
                "level": f.level.value,
                "text": f.text,
                "text_start": f.text_start,
                "text_end": f.text_end,
                "detail": f.detail,
                "rule_version": f.rule_version,
            }
            for f in sorted(flags, key=lambda f: f.risk_id)
        ]
    )
    return OCRRiskScan(**values)


def test_risk_scan_idempotent_triple(revision_stack):
    session, _fixture, keys = revision_stack
    repo = OCRRiskScanRepository(session)
    first, created = repo.get_or_create(_scan(keys))
    assert created is True
    second, created_again = repo.get_or_create(_scan(keys))
    assert created_again is False and second.scan_id == first.scan_id
    got = repo.get("scan-1")
    assert got.flags[0].kind == OcrRiskKind.NUMERIC_VALUE


def test_risk_scan_same_triple_conflicting_flags_rejected(revision_stack):
    session, _fixture, keys = revision_stack
    repo = OCRRiskScanRepository(session)
    repo.get_or_create(_scan(keys))
    different = _scan(keys, scan_id="scan-2", flags=[_flag(text="3.5", start=0, end=3)])
    with pytest.raises(RiskScanConflictError, match="哈希不一致"):
        repo.get_or_create(different)


def test_risk_scan_new_rule_version_creates_new_scan(revision_stack):
    session, _fixture, keys = revision_stack
    repo = OCRRiskScanRepository(session)
    repo.get_or_create(_scan(keys))
    v2 = _scan(keys, scan_id="scan-2", scanner_rule_version="rules/v2")
    repo.get_or_create(v2)
    assert {s.scan_id for s in repo.list_by_page("op-1")} == {"scan-1", "scan-2"}


def test_risk_scan_raw_hash_mismatch_rejected(revision_stack):
    session, _fixture, keys = revision_stack
    repo = OCRRiskScanRepository(session)
    with pytest.raises(RiskScanConflictError, match="raw_text_sha256"):
        repo.get_or_create(_scan(keys, raw_text_sha256="c" * 64))


def test_risk_review_append_only(revision_stack):
    session, _fixture, keys = revision_stack
    repo = OCRRiskScanRepository(session)
    repo.get_or_create(_scan(keys))
    reviews = OCRRiskReviewRepository(session)
    review = OCRRiskReview(
        review_id="rv-1",
        risk_flag_id="scan-1:r1",
        decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
        reason="已核对",
        actor="user",
        base_processing_revision_id="rev-1",
        expected_revision=1,
        created_at=FIXED_UTC,
    )
    reviews.create(review)
    got = reviews.get("rv-1")
    assert got.decision == OcrRiskReviewDecision.CONFIRMED_AS_READ
    with pytest.raises(DuplicateRecordError, match="已存在"):
        reviews.create(review)
    with pytest.raises(InvalidReferenceError, match="不存在"):
        reviews.create(
            OCRRiskReview(
                review_id="rv-2",
                risk_flag_id="no-such-flag",
                decision=OcrRiskReviewDecision.NOT_APPLICABLE,
                reason="r",
                actor="user",
                base_processing_revision_id="rev-1",
                expected_revision=1,
                created_at=FIXED_UTC,
            )
        )


# --------------------------------------------------------------------------- 校对


def _correction(keys, **overrides):
    base = {
        "correction_id": "corr-1",
        "ocr_page_id": "op-1",
        "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "text_start": 4,
        "text_end": 7,
        "original_text": "5.6",
        "corrected_text": "5.60",
        "change_kind": "decimal",
        "requires_confirmation": True,
        "confirmation_actor": "user",
        "confirmation_at": FIXED_UTC,
        "reason": "确认小数点",
        "actor": "user",
        "base_processing_revision_id": "rev-1",
        "affected_scope": [],
        "created_at": FIXED_UTC,
    }
    base.update(overrides)
    return CorrectionRecord(**base)


def test_correction_append_and_supersede_chain(revision_stack):
    session, _fixture, keys = revision_stack
    repo = CorrectionRepository(session)
    repo.create(_correction(keys))
    repo.create(
        _correction(
            keys,
            correction_id="corr-2",
            supersedes_correction_id="corr-1",
        )
    )
    got = repo.get("corr-2")
    assert got.supersedes_correction_id == "corr-1"
    assert len(repo.list_by_page("op-1")) == 2


def test_correction_same_occurrence_cannot_create_second_root(revision_stack):
    """同一基础修订、OCR 页和原文范围只能有一条校对链。"""
    session, _fixture, keys = revision_stack
    repo = CorrectionRepository(session)
    repo.create(_correction(keys, correction_id="corr-root-a"))
    with pytest.raises(CorrectionOverlapError, match="不能创建第二个起始版本"):
        repo.create(
            _correction(
                keys,
                correction_id="corr-root-b",
                corrected_text="5.600",
            )
        )


def test_insertion_same_position_requires_explicit_current_head_supersede(revision_stack):
    session, _fixture, keys = revision_stack
    repo = CorrectionRepository(session)
    insert_at = len(RAW_TEXT)
    repo.create(
        _correction(
            keys,
            correction_id="insert-root",
            text_start=insert_at,
            text_end=insert_at,
            original_text="",
            corrected_text=" 2026-08-19",
            change_kind="date",
        )
    )

    with pytest.raises(CorrectionOverlapError, match="不能创建第二个起始版本"):
        repo.create(
            _correction(
                keys,
                correction_id="insert-second-root",
                text_start=insert_at,
                text_end=insert_at,
                original_text="",
                corrected_text=" 2026-08-20",
                change_kind="date",
            )
        )

    successor = repo.create(
        _correction(
            keys,
            correction_id="insert-successor",
            text_start=insert_at,
            text_end=insert_at,
            original_text="",
            corrected_text=" 2026-08-20",
            change_kind="date",
            supersedes_correction_id="insert-root",
        )
    )
    assert successor.supersedes_correction_id == "insert-root"
    chain = repo.list_by_page("op-1")
    assert [item.correction_id for item in chain if item.text_start == insert_at] == [
        "insert-root",
        "insert-successor",
    ]


def test_correction_original_text_must_match_raw_range(revision_stack):
    session, _fixture, keys = revision_stack
    repo = CorrectionRepository(session)
    with pytest.raises(CorrectionOverlapError, match="原文本"):
        repo.create(
            _correction(
                keys, original_text="5.60", text_end=8, corrected_text="5.600"
            )
        )


def test_correction_cannot_supersede_cross_page(revision_stack):
    """跨页替代必须拒绝：op-2 不在 base 修订页清单中（同闭包证明失败）。"""
    session, _fixture, keys = revision_stack
    repo = CorrectionRepository(session)
    repo.create(_correction(keys))
    # 第二页 OCR 页 + 校对：其页不在 base 修订页清单 → 无法锚定同闭包，拒绝。
    profile = OCRProfileRepository(session).get_or_create(make_profile())
    PageArtifactRepository(session).get_or_create(
        make_artifact(artifact_id="pa-2", version_id="doc-1", page_number=1,
                      page_input="6" * 64)
    )
    OcrPageRepository(session).create(
        make_ocr_page(
            page_id="op-2",
            artifact_id="pa-2",
            page_number=1,
            raw_text="second page",
            page_input="6" * 64,
            profile_sha=profile.profile_sha256,
        )
    )
    session.flush()
    with pytest.raises(Slice44RepositoryError, match="不在 base 修订 .* 的页清单中"):
        repo.create(
            _correction(
                keys,
                correction_id="corr-x",
                ocr_page_id="op-2",
                raw_text_sha256=sha(b"second page"),
                text_start=0,
                text_end=5,
                original_text="secon",
                supersedes_correction_id="corr-1",
            )
        )


# --------------------------------------------------------------------------- 被提及资料


def _referenced(keys, **overrides):
    base = {
        "revision_id": "rd-1",
        "referenced_document_id": "doc-ref",
        "project_id": keys["project_id"],
        "subject_id": keys["subject_id"],
        "review_episode_id": keys["episode_id"],
        "description": "检查报告",
        "origin": "manual",
        "status": "proposed",
        "revision": 1,
        "created_at": FIXED_UTC,
        "created_by": "user",
    }
    base.update(overrides)
    if base["revision"] > 1 and "reason" not in overrides:
        base["reason"] = "追加修订"
    return ReferencedDocumentRevision(**base)


def test_referenced_document_revision_chain(revision_stack):
    session, _fixture, keys = revision_stack
    repo = ReferencedDocumentRepository(session)
    repo.create_revision(_referenced(keys))
    repo.create_revision(
        _referenced(
            keys,
            revision_id="rd-2",
            revision=2,
            supersedes_revision_id="rd-1",
        )
    )
    got = repo.get_revision("rd-2")
    assert got.revision == 2 and got.supersedes_revision_id == "rd-1"
    # 跳过链号 → 拒绝
    with pytest.raises(CandidateStateTransitionError, match="修订号应为"):
        repo.create_revision(
            _referenced(keys, revision_id="rd-3", revision=4, supersedes_revision_id="rd-2")
        )


def test_referenced_document_resolution_requires_member_document(revision_stack):
    session, _fixture, keys = revision_stack
    repo = ReferencedDocumentRepository(session)
    # 无登记修订链时，任何满足修订都是孤儿 → 拒绝
    with pytest.raises(InvalidReferenceError, match="没有任何登记修订链"):
        repo.create_resolution(
            ReferencedDocumentResolutionRevision(
                resolution_revision_id="res-0",
                referenced_document_id="doc-ref",
                status="unresolved",
                revision=1,
                created_at=FIXED_UTC,
                created_by="user",
            )
        )
    # 先建立登记修订链，再校验 provided 必须引用存在的资料版本。
    repo.create_revision(_referenced(keys))
    with pytest.raises(InvalidReferenceError, match="资料版本不存在"):
        repo.create_resolution(
            ReferencedDocumentResolutionRevision(
                resolution_revision_id="res-1",
                referenced_document_id="doc-ref",
                status="provided",
                source_document_version_id="doc-missing",
                revision=1,
                created_at=FIXED_UTC,
                created_by="user",
            )
        )
    repo.create_resolution(
        ReferencedDocumentResolutionRevision(
            resolution_revision_id="res-2",
            referenced_document_id="doc-ref",
            status="unresolved",
            revision=1,
            created_at=FIXED_UTC,
            created_by="user",
        )
    )
    got = repo.get_resolution("res-2")
    assert got.status == ReferencedDocumentResolutionStatus.UNRESOLVED


def test_referenced_document_resolution_rejects_other_subject_at_repository_boundary(
    revision_stack,
):
    """即使绕过服务层，仓储也不得把另一受试者的资料登记为已提供。"""
    from app.storage.evidence_locator_models import (
        ReferencedDocumentResolutionRevisionRecord,
    )
    from app.storage.repositories import EpisodeRepository, SubjectRepository

    session, fixture, keys = revision_stack
    SubjectRepository(session).save(
        fixture.subject.model_copy(
            update={"subject_id": "subject-other", "subject_code": "OTHER"}
        )
    )
    EpisodeRepository(session).save(
        fixture.review_episode.model_copy(
            update={
                "review_episode_id": "episode-other-subject",
                "subject_id": "subject-other",
                "evidence_snapshot_id": "legacy-other-subject",
            }
        )
    )
    other_blob = make_blob(b"other-subject-document")
    BlobRepository(session).get_or_create_by_sha256(other_blob)
    SourceDocumentRepository(session).create_version(
        make_version(
            version_id="doc-other-subject",
            logical_id="log-other-subject",
            blob_sha=other_blob.sha256,
            scope=(keys["project_id"], "subject-other", "episode-other-subject"),
            page_count=1,
        )
    )
    repo = ReferencedDocumentRepository(session)
    repo.create_revision(_referenced(keys))

    with pytest.raises(Slice44RepositoryError, match="其他项目、受试者或审核节点"):
        repo.create_resolution(
            ReferencedDocumentResolutionRevision(
                resolution_revision_id="res-cross-subject",
                referenced_document_id="doc-ref",
                status="provided",
                source_document_version_id="doc-other-subject",
                revision=1,
                created_at=FIXED_UTC,
                created_by="user",
            )
        )
    assert session.get(
        ReferencedDocumentResolutionRevisionRecord, "res-cross-subject"
    ) is None


# --------------------------------------------------------------------------- 激活事件


def _activation_event(keys, **overrides):
    base = {
        "event_id": "evt-1",
        "review_episode_id": keys["episode_id"],
        "activation_seq": 1,
        "event_kind": "rollback",
        "from_snapshot_id": None,
        "from_revision_id": None,
        "to_snapshot_id": "snap-1",
        "to_revision_id": "complete-1",
        "reason": "发布",
        "actor": "user",
        "expected_revision": 1,
        "resulting_episode_revision": 2,
        "created_at": FIXED_UTC,
    }
    base.update(overrides)
    base["resulting_episode_revision"] = base["expected_revision"] + 1
    base["command_sha256"] = activation_command_hash(
        event_kind=ActivationEventKind(base["event_kind"]),
        candidate_id=base.get("candidate_id"),
        target_snapshot_id=base["to_snapshot_id"],
        target_revision_id=base["to_revision_id"],
        expected_revision=base["expected_revision"],
        actor=base["actor"],
        reason=base["reason"],
        job_id=base.get("job_id"),
    )
    return EvidenceActivationEvent(**base)


def test_activation_event_cannot_be_appended_without_pointer_switch(revision_stack):
    session, _fixture, keys = revision_stack
    CompleteEvidenceProcessingRevisionRepository(session).create(
        _closed_revision(keys, session)
    )
    repo = EvidenceActivationEventRepository(session)
    with pytest.raises(Slice44RepositoryError, match="不能单独追加"):
        repo.append(_activation_event(keys))
    assert repo.list_by_episode(keys["episode_id"]) == []


def test_activation_event_requires_existing_target(revision_stack):
    session, _fixture, keys = revision_stack
    repo = EvidenceActivationEventRepository(session)
    with pytest.raises(InvalidReferenceError, match="目标处理修订"):
        repo.append_and_switch(_activation_event(keys, to_revision_id="no-such-rev"))


def test_activation_event_rejects_base_revision_target(revision_stack):
    """仓储本身必须拒绝 base，不能只依赖上层激活服务。"""
    session, _fixture, keys = revision_stack
    repo = EvidenceActivationEventRepository(session)
    with pytest.raises(InvalidReferenceError, match="不是可激活的完整处理版本"):
        repo.append_and_switch(_activation_event(keys, to_revision_id="rev-1"))


def test_activation_event_rejects_processing_candidate_direct_bypass(revision_stack):
    """直接调用仓储也不能把尚未就绪的生产候选伪装为成功启用。"""
    session, _fixture, keys = revision_stack
    CompleteEvidenceProcessingRevisionRepository(session).create(
        _closed_revision(keys, session)
    )
    with pytest.raises(InvalidReferenceError, match="尚未就绪"):
        EvidenceActivationEventRepository(session).append_and_switch(
            _activation_event(
                keys,
                event_kind="activate",
                candidate_id="producer-complete-1",
            )
        )


def test_activation_event_rejects_rollback_without_historical_activation(
    revision_stack,
):
    """直接调用仓储也不能回滚到从未启用过的版本对。"""
    session, _fixture, keys = revision_stack
    CompleteEvidenceProcessingRevisionRepository(session).create(
        _closed_revision(keys, session)
    )
    with pytest.raises(Slice44RepositoryError, match="没有历史激活记录"):
        EvidenceActivationEventRepository(session).append_and_switch(
            _activation_event(keys)
        )


def test_activation_event_rejects_stale_source_pair(revision_stack):
    """事件声明的来源版本对必须与审核节点当前权威指针逐项一致。"""
    session, _fixture, keys = revision_stack
    with pytest.raises(Slice44RepositoryError, match="来源版本对"):
        EvidenceActivationEventRepository(session).append_and_switch(
            _activation_event(
                keys,
                from_snapshot_id="stale-snapshot",
                from_revision_id="stale-revision",
            )
        )


# --------------------------------------------------------------------------- 处理候选


def _candidate(keys, **overrides):
    base = {
        "candidate_id": "cand-1",
        "evidence_snapshot_id": "snap-1",
        "base_processing_revision_id": "rev-1",
        "project_id": keys["project_id"],
        "subject_id": keys["subject_id"],
        "review_episode_id": keys["episode_id"],
        "expected_revision": 1,
        "idempotency_key": "key-1",
        "scanner_rule_version": "slice4.0/v1",
        "selected_locator_ids": [],
        "candidate_input_sha256": "e" * 64,
        "status": "staged",
        "created_by": "user",
        "created_at": FIXED_UTC,
    }
    base.update(overrides)
    if "candidate_input_sha256" not in overrides:
        base["candidate_input_sha256"] = processing_candidate_input_hash(
            evidence_snapshot_id=base["evidence_snapshot_id"],
            base_processing_revision_id=base["base_processing_revision_id"],
            expected_revision=base["expected_revision"],
            scanner_rule_version=base["scanner_rule_version"],
            selected_locator_ids=base["selected_locator_ids"],
        )
    return EvidenceProcessingCandidate(**base)


def _candidate_event(candidate_id, seq, from_status, kind, to_status, **overrides):
    base = {
        "candidate_id": candidate_id,
        "seq": seq,
        "from_status": from_status,
        "to_status": to_status,
        "event_kind": kind,
        "actor": "user",
        "reason": "r",
        "created_at": FIXED_UTC,
    }
    if kind in {"all_gates_passed", "activate"}:
        base["complete_revision_id"] = "complete-1"
    base.update(overrides)
    return EvidenceProcessingCandidateEvent(**base)


def test_candidate_full_lifecycle(revision_stack):
    session, _fixture, keys = revision_stack
    repo = EvidenceProcessingCandidateRepository(session)
    producer = _candidate(keys, scanner_rule_version="rules/v1")
    created = repo.create(
        producer,
        _candidate_event("cand-1", 1, "staged", "worker_start", "processing"),
    )
    CompleteEvidenceProcessingRevisionRepository(session).create(
        _closed_revision(
            keys,
            session,
            producer_candidate_id=producer.candidate_id,
            candidate_input_sha256=producer.candidate_input_sha256,
        )
    )
    assert created.status == EvidenceProcessingCandidateStatus.PROCESSING
    repo.append_event(
        _candidate_event("cand-1", 2, "processing", "all_gates_passed", "ready")
    )
    repo.append_event(_candidate_event("cand-1", 3, "ready", "activate", "active"))
    got = repo.get("cand-1")
    assert got.status == EvidenceProcessingCandidateStatus.ACTIVE
    # 终态不可再转换（合约状态表无出边；仓储终态检查兜底）
    from pydantic import ValidationError

    with pytest.raises((CandidateStateTransitionError, ValidationError)):
        repo.append_event(
            _candidate_event("cand-1", 4, "active", "retry", "processing")
        )


def test_candidate_cannot_bind_complete_produced_by_another_candidate(revision_stack):
    """候选输入即使相同，也不能绑定另一候选生成的完整修订。"""
    session, _fixture, keys = revision_stack
    repo = EvidenceProcessingCandidateRepository(session)
    producer_a = _candidate(
        keys,
        candidate_id="producer-a",
        idempotency_key="producer-a-key",
        scanner_rule_version="rules/v1",
    )
    producer_b = _candidate(
        keys,
        candidate_id="producer-b",
        idempotency_key="producer-b-key",
        scanner_rule_version="rules/v1",
    )
    for producer in (producer_a, producer_b):
        repo.create(
            producer,
            _candidate_event(
                producer.candidate_id,
                1,
                "staged",
                "worker_start",
                "processing",
            ),
        )
    CompleteEvidenceProcessingRevisionRepository(session).create(
        _closed_revision(
            keys,
            session,
            producer_candidate_id=producer_a.candidate_id,
            candidate_input_sha256=producer_a.candidate_input_sha256,
        )
    )
    with pytest.raises(InvalidReferenceError, match="由自身冻结输入生成"):
        repo.append_event(
            _candidate_event(
                producer_b.candidate_id,
                2,
                "processing",
                "all_gates_passed",
                "ready",
                complete_revision_id="complete-1",
            )
        )


def test_candidate_invalid_transition_rejected(revision_stack):
    """候选当前状态与事件起始状态不一致时拒绝（合约合法但仓储状态机拒绝）。"""
    session, _fixture, keys = revision_stack
    repo = EvidenceProcessingCandidateRepository(session)
    repo.create(
        _candidate(keys),
        _candidate_event("cand-1", 1, "staged", "worker_start", "processing"),
    )
    # 合约层面 ready--activate-->active 合法，但候选当前是 processing → 拒绝
    with pytest.raises(CandidateStateTransitionError, match="当前状态为 processing"):
        repo.append_event(
            _candidate_event("cand-1", 2, "ready", "activate", "active")
        )


def test_candidate_idempotency_same_input_replays(revision_stack):
    session, _fixture, keys = revision_stack
    repo = EvidenceProcessingCandidateRepository(session)
    repo.create(
        _candidate(keys),
        _candidate_event("cand-1", 1, "staged", "worker_start", "processing"),
    )
    replayed = repo.create(
        _candidate(keys),
        _candidate_event("cand-1", 1, "staged", "worker_start", "processing"),
    )
    assert replayed.candidate_id == "cand-1"
    # 同键不同输入 → 冲突
    with pytest.raises(CandidateIdempotencyConflictError, match="不同输入"):
        repo.create(
            _candidate(keys, candidate_id="cand-2", expected_revision=2),
            _candidate_event("cand-2", 1, "staged", "worker_start", "processing"),
        )


def test_candidate_status_projection_must_match_latest_event(revision_stack):
    session, _fixture, keys = revision_stack
    repo = EvidenceProcessingCandidateRepository(session)
    repo.create(
        _candidate(keys),
        _candidate_event("cand-1", 1, "staged", "worker_start", "processing"),
    )
    record = session.get(EvidenceProcessingCandidateRecord, "cand-1")
    record.status = "ready"  # 与最新事件 to_status=processing 漂移
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="状态列与最新事件目标不一致"):
        repo.get("cand-1")


def test_latest_candidate_by_snapshot_uses_persisted_order(revision_stack):
    session, _fixture, keys = revision_stack
    repo = EvidenceProcessingCandidateRepository(session)
    first = _candidate(keys, candidate_id="cand-1", idempotency_key="candidate-key-1")
    second = _candidate(keys, candidate_id="cand-2", idempotency_key="candidate-key-2")
    repo.create(first)
    repo.create(second)

    latest = repo.latest_by_snapshot(first.evidence_snapshot_id)

    assert latest is not None
    assert latest.candidate_id == "cand-2"
    assert repo.latest_by_snapshot("missing-snapshot") is None


# --------------------------------------------------------------------------- 完整处理修订


def _complete_revision(keys, session, **overrides):
    values = {
        "evidence_processing_revision_id": "complete-1",
        "evidence_snapshot_id": "snap-1",
        "project_id": keys["project_id"],
        "subject_id": keys["subject_id"],
        "review_episode_id": keys["episode_id"],
        "base_processing_revision_id": "rev-1",
        "manifest": [keys["entry"]],
        "manifest_sha256": keys["manifest_hash"],
        "locator_ids": [],
        "risk_scan_ids": [],
        "risk_review_ids": [],
        "correction_ids": [],
        "metadata_revision_ids": [],
        "referenced_document_revision_ids": [],
        "resolution_revision_ids": [],
        "completion_manifest_sha256": "e" * 64,
        "created_at": FIXED_UTC,
        "created_by": "tester",
    }
    values.update(overrides)
    producer_id = values.setdefault(
        "producer_candidate_id",
        f"producer-{values['evidence_processing_revision_id']}",
    )
    producer_record = session.get(EvidenceProcessingCandidateRecord, producer_id)
    if producer_record is None:
        base_revision = EvidenceProcessingRevisionRepository(session).get(
            values["base_processing_revision_id"]
        )
        base_pages = {entry.page_artifact_id for entry in base_revision.manifest}
        selected_locator_ids = []
        for locator_id in values["locator_ids"]:
            locator = EvidenceLocatorRepository(
                session, keys.get("artifact_store")
            ).get(locator_id)
            if locator.page_artifact_id in base_pages:
                selected_locator_ids.append(locator_id)
        scanner_rule_version = "slice4.0/v1"
        if values["risk_scan_ids"]:
            scanner_rule_version = OCRRiskScanRepository(session).get(
                values["risk_scan_ids"][0]
            ).scanner_rule_version
        producer = _candidate(
            keys,
            candidate_id=producer_id,
            idempotency_key=f"key-{producer_id}",
            base_processing_revision_id=values["base_processing_revision_id"],
            scanner_rule_version=scanner_rule_version,
            selected_locator_ids=selected_locator_ids,
        )
        EvidenceProcessingCandidateRepository(
            session, keys.get("artifact_store")
        ).create(
            producer,
            _candidate_event(
                producer_id, 1, "staged", "worker_start", "processing"
            ),
        )
        values.setdefault("candidate_input_sha256", producer.candidate_input_sha256)
    else:
        producer = EvidenceProcessingCandidateRepository(
            session, keys.get("artifact_store")
        ).get(producer_id)
        values.setdefault("candidate_input_sha256", producer.candidate_input_sha256)
    # 闭包清单哈希必须由仓储按 DB 子工件 canonical payload hash 重算（合同只校验格式）。
    rev = CompleteEvidenceProcessingRevision(**values)
    repo = CompleteEvidenceProcessingRevisionRepository(
        session, keys.get("artifact_store")
    )
    return rev.model_copy(update={"completion_manifest_sha256": repo.manifest_sha256_for(rev)})


def _incomplete_revision(keys, **overrides):
    """负面测试用：不重算闭包哈希（缺/错子引用时仓储门禁在哈希前失败）。"""
    values = {
        "evidence_processing_revision_id": "complete-1",
        "evidence_snapshot_id": "snap-1",
        "project_id": keys["project_id"],
        "subject_id": keys["subject_id"],
        "review_episode_id": keys["episode_id"],
        "base_processing_revision_id": "rev-1",
        "producer_candidate_id": "producer-incomplete",
        "candidate_input_sha256": "c" * 64,
        "manifest": [keys["entry"]],
        "manifest_sha256": keys["manifest_hash"],
        "locator_ids": [],
        "risk_scan_ids": [],
        "risk_review_ids": [],
        "correction_ids": [],
        "metadata_revision_ids": [],
        "referenced_document_revision_ids": [],
        "resolution_revision_ids": [],
        "completion_manifest_sha256": "e" * 64,
        "created_at": FIXED_UTC,
        "created_by": "tester",
    }
    values.update(overrides)
    return CompleteEvidenceProcessingRevision(**values)


def _seed_metadata(session, keys):
    """为 doc-1 追加一条元数据修订，返回其 id。"""
    from app.domain.contracts.evidence_ingestion import (
        SourceDocumentMetadataRevision,
    )

    repository = SourceDocumentMetadataRevisionRepository(session)
    existing = repository.head("doc-1")
    if existing is not None:
        return existing.metadata_revision_id
    revision = SourceDocumentMetadataRevision(
        metadata_revision_id="mdr-1",
        source_document_version_id="doc-1",
        document_type="lab",
        source_party="hospital",
        reason="确认资料类型",
        is_auto_suggestion=False,
        revision=1,
        created_at=FIXED_UTC,
        created_by="tester",
    )
    repository.append(revision)
    return "mdr-1"


def _seed_scan_and_review(session, keys, *, review=True, flag_level="blocking"):
    """为 op-1 建立风险扫描（默认含一个 blocking flag），可选建立核对。"""
    scan, _created = OCRRiskScanRepository(session).get_or_create(_scan(keys))
    review_ids = []
    if review:
        OCRRiskReviewRepository(session).create(
            OCRRiskReview(
                review_id="rv-1",
                risk_flag_id="scan-1:r1",
                decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
                reason="已核对",
                actor="user",
                base_processing_revision_id="rev-1",
                expected_revision=1,
                created_at=FIXED_UTC,
            )
        )
        review_ids.append("rv-1")
    return scan.scan_id, review_ids


def _closed_revision(keys, session, *, review=True, **overrides):
    """构建满足结构闭包的正例完整修订（元数据 + 每页一个扫描 + blocking 核对）。"""
    metadata_id = _seed_metadata(session, keys)
    scan_id, review_ids = _seed_scan_and_review(session, keys, review=review)
    base = {
        "metadata_revision_ids": [metadata_id],
        "risk_scan_ids": [scan_id],
        "risk_review_ids": review_ids,
    }
    base.update(overrides)
    return _complete_revision(keys, session, **base)


def test_complete_revision_create_and_decode(revision_stack):
    """正例：满足结构闭包后完整修订可冻结且可激活。"""
    session, _fixture, keys = revision_stack
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    rev = _closed_revision(keys, session)
    created = repo.create(rev)
    assert created.revision_kind == "complete"
    assert created.is_activatable is True
    got = repo.get("complete-1")
    assert got.base_processing_revision_id == "rev-1"
    assert got.manifest[0].page_artifact_id == "pa-1"
    assert got.metadata_revision_ids == ["mdr-1"]
    assert got.risk_scan_ids == ["scan-1"]
    assert got.risk_review_ids == ["rv-1"]


def test_complete_revision_cannot_omit_current_correction(revision_stack):
    """当前有效校对属于有效文本闭包，不能由候选清单静默省略。"""
    session, _fixture, keys = revision_stack
    CorrectionRepository(session).create(
        _correction(keys, correction_id="corr-current")
    )
    revision = _closed_revision(keys, session)
    with pytest.raises(RevisionClosureError, match="全部当前有效校对"):
        CompleteEvidenceProcessingRevisionRepository(session).create(revision)


def test_complete_revision_cannot_omit_current_referenced_document(revision_stack):
    """审核节点内当前被提及资料及其满足状态必须完整冻结。"""
    session, _fixture, keys = revision_stack
    references = ReferencedDocumentRepository(session)
    references.create_revision(_referenced(keys, revision_id="rd-current"))
    references.create_resolution(
        ReferencedDocumentResolutionRevision(
            resolution_revision_id="res-current",
            referenced_document_id="doc-ref",
            status="unresolved",
            revision=1,
            created_at=FIXED_UTC,
            created_by="user",
        )
    )
    revision = _closed_revision(keys, session)
    with pytest.raises(RevisionClosureError, match="全部当前被提及资料"):
        CompleteEvidenceProcessingRevisionRepository(session).create(revision)


def test_complete_revision_must_equal_base_manifest(revision_stack):
    """完整修订页清单必须逐项等于 base 修订（不得换页/换 OCR/隐藏失败页）。"""
    session, _fixture, keys = revision_stack
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
    from app.domain.publication import evidence_processing_manifest_hash

    other_entry = EvidenceProcessingRevisionPage(
        entry_id="e1",
        position=1,
        source_document_version_id="doc-1",
        page_number=1,
        original_frame=None,
        page_artifact_id="pa-1",
        ocr_page_id="op-999",  # 与 base 的 op-1 不同
        status="succeeded",
    )
    other_hash = evidence_processing_manifest_hash(
        entries=[("doc-1", 1, None, "pa-1", "op-999", "succeeded")]
    )
    rev = _closed_revision(
        keys,
        session,
        manifest=[other_entry],
        manifest_sha256=other_hash,
    )
    with pytest.raises(RevisionClosureError, match="逐项等于 base"):
        repo.create(rev)


def test_complete_revision_rejects_missing_metadata(revision_stack):
    """缺逐资料元数据修订时闭包不完整 → 拒绝冻结。"""
    session, _fixture, keys = revision_stack
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    rev = _incomplete_revision(keys)
    with pytest.raises(RevisionClosureError, match="元数据修订"):
        repo.create(rev)


def test_complete_revision_rejects_missing_scan(revision_stack):
    """每页必须恰好一个选中的风险扫描；缺扫描 → 拒绝。"""
    session, _fixture, keys = revision_stack
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    metadata_id = _seed_metadata(session, keys)
    rev = _incomplete_revision(keys, metadata_revision_ids=[metadata_id])
    with pytest.raises(RevisionClosureError, match="风险扫描"):
        repo.create(rev)


def test_complete_revision_rejects_unresolved_blocking(revision_stack):
    """blocking 风险未由选中核对/覆盖校对解除 → 拒绝冻结。"""
    session, _fixture, keys = revision_stack
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    metadata_id = _seed_metadata(session, keys)
    scan_id, _reviews = _seed_scan_and_review(session, keys, review=False)
    rev = _incomplete_revision(
        keys, metadata_revision_ids=[metadata_id], risk_scan_ids=[scan_id]
    )
    with pytest.raises(RevisionClosureError, match="未由选中的有效核对或覆盖校对解除"):
        repo.create(rev)


def test_complete_revision_rejects_unconfirmed_key_correction(revision_stack):
    """选中的关键校对未完成二次确认 → 拒绝冻结。"""
    session, _fixture, keys = revision_stack
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    metadata_id = _seed_metadata(session, keys)
    scan_id, _reviews = _seed_scan_and_review(session, keys, review=False)
    CorrectionRepository(session).create(
        _correction(
            keys,
            correction_id="corr-1",
            requires_confirmation=True,
            confirmation_actor=None,
            confirmation_at=None,
        )
    )
    rev = _incomplete_revision(
        keys,
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        correction_ids=["corr-1"],
    )
    with pytest.raises(RevisionClosureError, match="未完成二次确认"):
        repo.create(rev)


def test_complete_revision_rejects_missing_locator(revision_stack):
    """闭包完整但引用了不存在的定位 → 拒绝。"""
    session, _fixture, keys = revision_stack
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    metadata_id = _seed_metadata(session, keys)
    scan_id, review_ids = _seed_scan_and_review(session, keys)
    rev = _incomplete_revision(
        keys,
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        risk_review_ids=review_ids,
        locator_ids=["no-such-loc"],
    )
    with pytest.raises((RevisionClosureError, InvalidReferenceError), match="不存在"):
        repo.create(rev)


def test_complete_revision_rejects_overlapping_corrections(revision_stack):
    """完整修订只选有效校对；同一范围不得同时选中替代链前项与后继。"""
    session, _fixture, keys = revision_stack
    corrections = CorrectionRepository(session)
    corrections.create(
        _correction(
            keys,
            correction_id="corr-a",
            text_start=4,
            text_end=7,
            original_text="5.6",
            corrected_text="5.6X",
            change_kind="other_text",
            requires_confirmation=False,
            confirmation_actor=None,
            confirmation_at=None,
        )
    )
    # corr-b 替代 corr-a：必须绑定同页同 raw 哈希同原始范围（[4,7]）。
    corrections.create(
        _correction(
            keys,
            correction_id="corr-b",
            text_start=4,
            text_end=7,
            original_text="5.6",
            corrected_text="5.6Y",
            change_kind="other_text",
            requires_confirmation=False,
            confirmation_actor=None,
            confirmation_at=None,
            supersedes_correction_id="corr-a",
        )
    )
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    # 同时选中前项与后继（同范围重叠）→ 拒绝。
    metadata_id = _seed_metadata(session, keys)
    scan_id, _reviews = _seed_scan_and_review(session, keys, review=False)
    rev = _complete_revision(
        keys, session,
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        correction_ids=["corr-a", "corr-b"],
    )
    with pytest.raises(RevisionClosureError, match="不是当前链头"):
        repo.create(rev)
    # 单独选中后继 corr-b（替代链完整、覆盖 blocking flag [4,7]）→ 合法。
    ok = _complete_revision(
        keys, session,
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        correction_ids=["corr-b"],
    )
    repo.create(ok)


def test_complete_revision_discriminated_read_dispatch(revision_stack):
    """base 修订只能由 base 仓储读取；complete 修订只能由 complete 仓储读取。"""
    from app.storage.ocr_repositories import OcrIdentityError

    session, _fixture, keys = revision_stack
    base_repo = EvidenceProcessingRevisionRepository(session)
    complete_repo = CompleteEvidenceProcessingRevisionRepository(session)
    base_repo.get("rev-1")
    with pytest.raises(OcrRevisionKindError, match="不是 complete"):
        complete_repo.get("rev-1")
    complete_repo.create(_closed_revision(keys, session))
    complete_repo.get("complete-1")
    with pytest.raises(OcrIdentityError, match="不是 base"):
        base_repo.get("complete-1")
    assert [r.evidence_processing_revision_id for r in base_repo.list_by_snapshot("snap-1")] == ["rev-1"]
    assert [r.evidence_processing_revision_id for r in complete_repo.list_by_snapshot("snap-1")] == ["complete-1"]


def test_complete_revision_assoc_mirror_tamper_rejected(revision_stack):
    """关联子表与 payload 不一致（多行/换绑）在读取时被拒绝。"""
    session, _fixture, keys = revision_stack
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    repo.create(_closed_revision(keys, session))
    from app.storage.evidence_locator_models import ProcessingRevisionLocatorRecord

    # 先落一个真实定位，再向关联表插入 payload 未选中的额外行（换绑/多行）。
    _locator(keys, locator_id="loc-extra")
    # 需要一个真实的同 occurrence 定位才能落关联行；这里直接构造并写 locator。
    locator = _locator(keys, locator_id="loc-extra", text_start=0, text_end=5)
    EvidenceLocatorRepository(session).create(locator)
    session.execute(
        ProcessingRevisionLocatorRecord.__table__.insert().values(
            revision_id="complete-1", position=1, locator_id="loc-extra"
        )
    )
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="子表与 payload 不一致"):
        repo.get("complete-1")


# ---------------------------------------------------------------------------
# WP-44A 修复回归：活动指针 / bbox 真实性 / occurrence 身份 / 风险锚定 /
# 校对替代 / 被提及资料作用域 / 完整修订闭包
# ---------------------------------------------------------------------------


def _seed_native_page(session, keys, artifact_store, *, page_id="op-native",
                      artifact_id="pa-native", raw_text=RAW_TEXT):
    """建立带真实内容寻址原生文本+坐标工件的页产物与 OCR 页。

    坐标字符按确定性 schema 构造：每个字符的 start 偏移与文本对应，
    bbox 由字符并集按阅读顺序覆盖目标范围。
    """
    from app.evidence.pdf_native import (
        NativeChar,
        NativePage,
        NativeWord,
        serialize_native_coordinates,
    )
    from app.storage.ocr_repositories import (
        OcrPageRepository,
        PageArtifactRepository,
    )

    chars = tuple(
        NativeChar(text=ch, x0=10.0 + i * 5.0, y0=50.0, x1=15.0 + i * 5.0, y1=60.0,
                   start=i)
        for i, ch in enumerate(raw_text)
    )
    words = (NativeWord(text=raw_text, x0=10.0, y0=50.0, x1=15.0 + len(raw_text) * 5.0,
                        y1=60.0),)
    native_page = NativePage(
        page_number=1,
        text=raw_text,
        chars=chars,
        words=words,
        page_width=595.0,
        page_height=842.0,
        rotation=0,
    )
    native_text = raw_text.encode("utf-8")
    text_sha = sha(native_text)
    coords_bytes = serialize_native_coordinates(native_page)
    coords_sha = sha(coords_bytes)
    artifact_store.put("native_text", native_text)
    artifact_store.put("native_coordinates", coords_bytes)

    PageArtifactRepository(session).get_or_create(
        make_artifact(
            artifact_id=artifact_id, version_id="doc-1", page_number=1,
            page_input="d" * 64,
            native_text_sha256=text_sha,
            native_coordinates_sha256=coords_sha,
        )
    )
    profile = OCRProfileRepository(session).get_or_create(make_profile())
    OcrPageRepository(session).create(
        make_ocr_page(
            page_id=page_id,
            artifact_id=artifact_id,
            raw_text=raw_text,
            page_input="d" * 64,
            profile_sha=profile.profile_sha256,
        )
    )
    session.flush()
    keys["native_coords_sha"] = coords_sha
    keys["native_text_sha"] = text_sha
    return page_id, artifact_id


def _native_bbox_locator(keys, *, page_id="op-native", artifact_id="pa-native",
                         sidecar=None, start=4, end=7, excerpt="5.6",
                         bbox=None, **overrides):
    """原生 bbox 定位：范围 [4,7) 覆盖 '5.6'（字符 start 4,5,6）。

    默认 bbox 与重算结果一致：字符 start=4..6 的 x0=30..45, y0=50, y1=60。
    """
    sidecar = sidecar or keys.get("native_coords_sha")
    frame = CoordinateFrame(
        space="pdf_points",
        page_width=595.0,
        page_height=842.0,
        rotation=0,
        transform_version="t/v1",
    )
    base = {
        "locator_id": "loc-bbox-native",
        "page_artifact_id": artifact_id,
        "ocr_page_id": page_id,
        "source_document_version_id": "doc-1",
        "page_number": 1,
        "source_layer": "native_text",
        "source_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "target_id": "target-bbox",
        "precision": "bbox",
        "bbox": bbox or BoundingBox(x0=30.0, y0=50.0, x1=45.0, y1=60.0),
        "coordinate_frame": frame,
        "sidecar_sha256": sidecar,
        "text_start": start,
        "text_end": end,
        "excerpt": excerpt,
        "disambiguation": "unique_match",
        "locator_algorithm_version": "v1",
        "authenticity": "authenticated",
        "created_at": FIXED_UTC,
    }
    base.update(overrides)
    return _locator(keys, **base)


# --- Finding 1: 活动指针只能由激活事务修改 ---


def test_episode_save_rejects_active_pointers(revision_stack):
    """通用 save 不得建立非空活动指针对。"""
    from app.domain.contracts.review import ReviewEpisode as Ep
    from app.storage.repositories import EpisodeRepository, RepositoryError

    session, _fixture, keys = revision_stack
    episode = Ep(
        review_episode_id="ep-new",
        subject_id=keys["subject_id"],
        project_id=keys["project_id"],
        rule_set_id="ruleset-1",
        study_phase="phase_iii",
        stage="screening",
        protocol_version_id="protocol-v1",
        rule_set_revision=1,
        evidence_snapshot_id="snap-legacy",
        active_evidence_snapshot_id="snap-1",
        active_evidence_processing_revision_id="rev-1",
        anchor_dates={},
    )
    with pytest.raises(RepositoryError, match="不得建立活动版本指针"):
        EpisodeRepository(session).save(episode)


def test_episode_update_rejects_active_pointers_even_to_base(revision_stack):
    """通用 update 不得把活动指针改成 base 修订（尤其不得指向 base 修订激活）。"""
    from app.storage.repositories import (
        EpisodeRepository,
        RepositoryError,
        ReviewEpisodeRecord,
    )

    session, _fixture, keys = revision_stack
    repo = EpisodeRepository(session)
    record = session.get(ReviewEpisodeRecord, keys["episode_id"])
    current_revision = record.revision
    with pytest.raises(RepositoryError, match="不得修改活动版本指针"):
        repo.update(
            keys["episode_id"],
            current_revision,
            {
                "active_evidence_snapshot_id": "snap-1",
                "active_evidence_processing_revision_id": "rev-1",
            },
        )
    # 更新其他合法字段仍可（指针未被污染）。
    repo.update(keys["episode_id"], current_revision, {"stage": "baseline"})


# --- Finding 2: bbox 必须绑定同源坐标 sidecar 与范围 ---


def test_locator_bbox_raw_ocr_rejected(revision_stack):
    """raw_ocr 是 text-only 路线，无机器坐标 sidecar → bbox 一律拒绝。"""
    session, _fixture, keys = revision_stack
    repo = EvidenceLocatorRepository(session)
    frame = CoordinateFrame(
        space="pdf_points", page_width=595.0, page_height=842.0, rotation=0,
        transform_version="t/v1",
    )
    with pytest.raises(LocatorIdentityError, match="raw_ocr bbox 需要真实机器坐标"):
        repo.create(
            _locator(
                keys,
                locator_id="loc-raw-bbox",
                precision="bbox",
                bbox=BoundingBox(x0=10, y0=50, x1=25, y1=60),
                coordinate_frame=frame,
                sidecar_sha256="f" * 64,
                text_start=4,
                text_end=7,
                excerpt="5.6",
                authenticity="authenticated",
            )
        )


def test_locator_bbox_native_requires_artifact_store(revision_stack):
    """native bbox 需要内容寻址 ArtifactStore 证明；无 store 拒绝。"""
    session, _fixture, keys = revision_stack
    # 直接构造带 native_text 哈希的 locator（页产物无 native 哈希），证明必须注入 store。
    repo = EvidenceLocatorRepository(session)  # 未注入 artifact_store
    with pytest.raises(LocatorIdentityError, match="ArtifactStore"):
        repo.create(
            _locator(
                keys,
                locator_id="loc-native-no-store",
                source_layer="native_text",
                source_text_sha256=sha(RAW_TEXT.encode("utf-8")),
            )
        )


def test_locator_bbox_frame_mismatch_rejected(revision_stack, artifact_store):
    """bbox 坐标系/页尺寸/旋转/变换版本必须与持久化 PageArtifact 一致。"""
    session, _fixture, keys = revision_stack
    page_id, artifact_id = _seed_native_page(session, keys, artifact_store)
    repo = EvidenceLocatorRepository(session, artifact_store)
    bad_frame = CoordinateFrame(
        space="page_image_pixels",
        page_width=999.0,
        page_height=842.0,
        rotation=0,
        transform_version="t/v1",
    )
    with pytest.raises(LocatorIdentityError, match="坐标系/页尺寸/旋转/变换版本"):
        repo.create(
            _native_bbox_locator(
                keys, page_id=page_id, artifact_id=artifact_id, coordinate_frame=bad_frame,
                sidecar=keys["native_coords_sha"],
            )
        )


def test_locator_bbox_range_excerpt_must_match_native_text(revision_stack, artifact_store):
    """native bbox 范围/摘录必须逐字等于原生文本工件对应切片。"""
    session, _fixture, keys = revision_stack
    page_id, artifact_id = _seed_native_page(session, keys, artifact_store)
    repo = EvidenceLocatorRepository(session, artifact_store)
    # 摘录错文本 → 拒绝
    with pytest.raises(LocatorIdentityError, match="摘录"):
        repo.create(
            _native_bbox_locator(
                keys, page_id=page_id, artifact_id=artifact_id,
                sidecar=keys["native_coords_sha"], excerpt="5.7",
            )
        )
    # 范围越出原文 → 拒绝
    with pytest.raises(LocatorIdentityError, match="越出"):
        repo.create(
            _native_bbox_locator(
                keys, page_id=page_id, artifact_id=artifact_id,
                sidecar=keys["native_coords_sha"],
                start=0, end=999, excerpt="ALT 5.6 mmol/L 且 AST 3.5 mmol/L",
            )
        )


def test_locator_bbox_authenticated_valid_native(revision_stack, artifact_store):
    """真实原生文本+坐标工件 + 帧一致 + 字符映射重算 bbox → authenticated 合法。"""
    session, _fixture, keys = revision_stack
    page_id, artifact_id = _seed_native_page(session, keys, artifact_store)
    repo = EvidenceLocatorRepository(session, artifact_store)
    ok = repo.create(
        _native_bbox_locator(
            keys, page_id=page_id, artifact_id=artifact_id,
            sidecar=keys["native_coords_sha"],
        )
    )
    assert ok.precision == LocatorPrecision.BBOX
    assert ok.authenticity.value == "authenticated"


def test_locator_bbox_native_wrong_sidecar_rejected(revision_stack, artifact_store):
    """native bbox 的 sidecar 哈希必须等于页产物原生坐标 sidecar（错哈希拒绝）。"""
    session, _fixture, keys = revision_stack
    page_id, artifact_id = _seed_native_page(session, keys, artifact_store)
    repo = EvidenceLocatorRepository(session, artifact_store)
    with pytest.raises(LocatorIdentityError, match="坐标 sidecar 哈希"):
        repo.create(
            _native_bbox_locator(
                keys, page_id=page_id, artifact_id=artifact_id,
                sidecar="9" * 64,
            )
        )


def test_locator_bbox_native_tampered_artifact_rejected(revision_stack, artifact_store):
    """原生坐标工件字节被篡改（哈希复核失败）→ 拒绝。"""
    session, _fixture, keys = revision_stack
    page_id, artifact_id = _seed_native_page(session, keys, artifact_store)
    repo = EvidenceLocatorRepository(session, artifact_store)
    # 篡改存储中的坐标工件字节（同路径覆写为不同字节 → 哈希复核失败）。
    target = keys["artifact_store"].data_paths.root / "artifacts" / "native_coordinates" / keys["native_coords_sha"]
    target.write_bytes(b"tampered")
    with pytest.raises(LocatorIdentityError, match="内容与引用哈希不一致|内容哈希与引用不一致"):
        repo.create(
            _native_bbox_locator(
                keys, page_id=page_id, artifact_id=artifact_id,
                sidecar=keys["native_coords_sha"],
            )
        )


def test_locator_bbox_native_wrong_bbox_rejected(revision_stack, artifact_store):
    """声明的 bbox 与字符映射重算结果不一致 → 拒绝（不信任自报坐标）。"""
    session, _fixture, keys = revision_stack
    page_id, artifact_id = _seed_native_page(session, keys, artifact_store)
    repo = EvidenceLocatorRepository(session, artifact_store)
    with pytest.raises(LocatorIdentityError, match="重算结果不一致"):
        repo.create(
            _native_bbox_locator(
                keys, page_id=page_id, artifact_id=artifact_id,
                sidecar=keys["native_coords_sha"],
                bbox=BoundingBox(x0=500, y0=500, x1=590, y1=840),
            )
        )


def test_locator_effective_text_requires_complete_revision(revision_stack):
    """effective_text 定位必须绑定完整处理修订；base 修订永不可作为投影来源（WP-44B）。"""
    session, _fixture, keys = revision_stack
    repo = EvidenceLocatorRepository(session)
    with pytest.raises(OcrRevisionKindError, match="不是 complete 修订"):
        repo.create(
            _locator(
                keys,
                locator_id="loc-eff",
                source_layer="effective_text",
                processing_revision_id="rev-1",
                effective_text_sha256=sha(RAW_TEXT.encode("utf-8")),
            )
        )


def test_locator_effective_text_binds_complete_revision_projection(revision_stack):
    """effective_text 定位绑定完整修订后由投影引擎确定性回验（WP-44B 正例）。"""
    session, _fixture, keys = revision_stack
    from app.evidence.effective_text import project_effective_text

    # 构造一个完整修订（含元数据 + 扫描 + 校对链头）。
    CorrectionRepository(session).create(
        _correction(keys, correction_id="corr-eff", text_start=4, text_end=7,
                    original_text="5.6", corrected_text="5.60", change_kind="decimal")
    )
    revision = _closed_revision(keys, session, correction_ids=["corr-eff"])
    created = CompleteEvidenceProcessingRevisionRepository(session).create(revision)
    projection = project_effective_text(RAW_TEXT, [CorrectionRepository(session).get("corr-eff")])
    locator = _locator(
        keys,
        locator_id="loc-eff-ok",
        source_layer="effective_text",
        ocr_page_id="op-1",
        text_start=4,
        text_end=9,
        excerpt=projection.effective_text[4:9],
        source_text_sha256=projection.effective_text_sha256,
        processing_revision_id=created.evidence_processing_revision_id,
        effective_text_sha256=projection.effective_text_sha256,
        authenticity="degraded",
        degradation_reason="有效文本投影无机器坐标 sidecar",
    )
    got = EvidenceLocatorRepository(session).create(locator)
    assert got.source_layer == "effective_text"
    assert got.precision == "text_range"


def test_complete_revision_rejects_stale_effective_text_locator_projection(revision_stack):
    """旧定位若不再匹配新校对投影，不能被换绑到新的完整修订。"""
    session, _fixture, keys = revision_stack
    from app.evidence.effective_text import project_effective_text

    corrections = CorrectionRepository(session)
    corrections.create(
        _correction(
            keys,
            correction_id="corr-eff",
            text_start=4,
            text_end=7,
            original_text="5.6",
            corrected_text="5.60",
            change_kind="decimal",
        )
    )
    first = CompleteEvidenceProcessingRevisionRepository(session).create(
        _closed_revision(keys, session, correction_ids=["corr-eff"])
    )
    projection = project_effective_text(RAW_TEXT, [corrections.get("corr-eff")])
    EvidenceLocatorRepository(session).create(
        _locator(
            keys,
            locator_id="loc-eff-stale",
            source_layer="effective_text",
            ocr_page_id="op-1",
            text_start=4,
            text_end=9,
            excerpt=projection.effective_text[4:9],
            source_text_sha256=projection.effective_text_sha256,
            processing_revision_id=first.evidence_processing_revision_id,
            effective_text_sha256=projection.effective_text_sha256,
            authenticity="degraded",
            degradation_reason="有效文本投影无机器坐标 sidecar",
        )
    )
    corrections.create(
        _correction(
            keys,
            correction_id="corr-eff-2",
            text_start=4,
            text_end=7,
            original_text="5.6",
            corrected_text="5.600",
            change_kind="decimal",
            supersedes_correction_id="corr-eff",
        )
    )
    second = _complete_revision(
        keys,
        session,
        evidence_processing_revision_id="complete-2",
        metadata_revision_ids=first.metadata_revision_ids,
        risk_scan_ids=first.risk_scan_ids,
        risk_review_ids=first.risk_review_ids,
        correction_ids=["corr-eff-2"],
        locator_ids=["loc-eff-stale"],
    )
    with pytest.raises(RevisionClosureError, match="投影不一致"):
        CompleteEvidenceProcessingRevisionRepository(session).create(second)


# --- Finding 3: occurrence 身份必须基于具体范围 ---


def test_locator_two_identical_strings_different_ranges_coexist(revision_stack):
    """同页两处相同文本：不同可信 range 可各自定位，互不碰撞。"""
    session, _fixture, keys = revision_stack
    # 第二页产物/OCR 页：原文含两处相同文本。
    from app.storage.ocr_repositories import (
        OcrPageRepository,
        PageArtifactRepository,
    )

    PageArtifactRepository(session).get_or_create(
        make_artifact(
            artifact_id="pa-occ", version_id="doc-1", page_number=1,
            page_input="7" * 64,
        )
    )
    profile = OCRProfileRepository(session).get_or_create(make_profile())
    OcrPageRepository(session).create(
        make_ocr_page(
            page_id="op-occ",
            artifact_id="pa-occ",
            raw_text="5.6 mmol 且 5.6 mmol/L",
            page_input="7" * 64,
            profile_sha=profile.profile_sha256,
        )
    )
    session.flush()
    raw_sha = sha("5.6 mmol 且 5.6 mmol/L".encode())
    repo = EvidenceLocatorRepository(session)
    # 第一处 5.6 在 [0,3]
    repo.create(
        _locator(
            keys,
            locator_id="occ-1",
            page_artifact_id="pa-occ",
            ocr_page_id="op-occ",
            source_text_sha256=raw_sha,
            target_id="t-a",
            text_start=0,
            text_end=3,
            excerpt="5.6",
        )
    )
    # 第二处 5.6 在 [11,14]（同文本不同范围）→ 可共存
    repo.create(
        _locator(
            keys,
            locator_id="occ-2",
            page_artifact_id="pa-occ",
            ocr_page_id="op-occ",
            source_text_sha256=raw_sha,
            target_id="t-b",
            text_start=11,
            text_end=14,
            excerpt="5.6",
        )
    )
    assert repo.get("occ-1").target_id == "t-a"
    assert repo.get("occ-2").target_id == "t-b"


def test_locator_same_occurrence_under_target_alias_rejected(revision_stack):
    """同一 occurrence（同页/同层/同哈希/同范围/同算法）不得换 target 别名重复持久化。"""
    session, _fixture, keys = revision_stack
    repo = EvidenceLocatorRepository(session)
    repo.create(_locator(keys))
    with pytest.raises(LocatorIdentityError, match="身份碰撞"):
        repo.create(_locator(keys, locator_id="loc-alias", target_id="another-alias"))


# --- Finding 4: 风险 flag 必须锚定 raw OCR ---


def test_risk_scan_wrong_text_flag_rejected(revision_stack):
    session, _fixture, keys = revision_stack
    repo = OCRRiskScanRepository(session)
    with pytest.raises(RiskScanConflictError, match="与 OCRPage 原文对应范围不一致"):
        repo.get_or_create(_scan(keys, flags=[_flag(text="5.7", start=4, end=7)]))


def test_risk_scan_out_of_range_flag_rejected(revision_stack):
    session, _fixture, keys = revision_stack
    repo = OCRRiskScanRepository(session)
    # 范围 [4,40) 超出 RAW_TEXT（29 字符），text 长度与范围一致以满足合同校验。
    with pytest.raises(RiskScanConflictError, match="越出"):
        repo.get_or_create(
            _scan(keys, flags=[_flag(text="X" * 36, start=4, end=40)])
        )


def test_risk_scan_flag_hash_drift_rejected_on_readback(revision_stack):
    """回读时 flag 行 raw 哈希/规则版本与扫描漂移 → 拒绝。"""
    session, _fixture, keys = revision_stack
    repo = OCRRiskScanRepository(session)
    repo.get_or_create(_scan(keys))

    row = session.get(OCRRiskFlagRecord, "scan-1:r1")
    row.raw_text_sha256 = "b" * 64
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="raw_text_sha256"):
        repo.get("scan-1")


def test_risk_scan_composite_sentence_raw_text_unchanged(revision_stack):
    """冻结复合句扫描前后 OCRPage.raw_text/hash 逐字不变，只产生风险 flag。"""
    sentence = "ALT > 3×ULN 且 AST > 3×ULN，或总胆红素 > 2×ULN。"
    session, _fixture, keys = revision_stack
    from app.storage.ocr_repositories import (
        OcrPageRepository,
        PageArtifactRepository,
    )

    PageArtifactRepository(session).get_or_create(
        make_artifact(
            artifact_id="pa-comp", version_id="doc-1", page_number=1,
            page_input="8" * 64,
        )
    )
    profile = OCRProfileRepository(session).get_or_create(make_profile())
    OcrPageRepository(session).create(
        make_ocr_page(
            page_id="op-comp",
            artifact_id="pa-comp",
            raw_text=sentence,
            page_input="8" * 64,
            profile_sha=profile.profile_sha256,
        )
    )
    session.flush()
    raw_sha = sha(sentence.encode("utf-8"))
    scan = _scan(
        keys,
        scan_id="scan-composite",
        ocr_page_id="op-comp",
        raw_text_sha256=raw_sha,
        flags=[
            _flag(risk_id="num-1", kind="numeric_value", text="3", start=6, end=7),
            _flag(risk_id="unit-1", kind="unit", level="informational", text="ULN",
                  start=8, end=11, rule_version="rules/v1"),
        ],
    )
    repo = OCRRiskScanRepository(session)
    repo.get_or_create(scan)
    # 扫描前后 OCRPage 原文与哈希逐字不变（旁路不写回原 OCR）。
    ocr = session.get(OCRPageRecord, "op-comp")
    assert ocr.raw_text == sentence
    assert ocr.raw_text_sha256 == raw_sha
    got = repo.get("scan-composite")
    assert got.flags_sha256 is not None
    assert {f.kind.value for f in got.flags} == {"numeric_value", "unit"}


# --- Finding 5: 校对替代必须绑定同页同范围；base 修订校验 ---


def test_correction_supersede_must_bind_same_range(revision_stack):
    session, _fixture, keys = revision_stack
    repo = CorrectionRepository(session)
    repo.create(_correction(keys))
    with pytest.raises(CorrectionOverlapError, match="text_start"):
        repo.create(
            _correction(
                keys,
                correction_id="corr-2",
                text_start=6,
                text_end=9,
                original_text="6 m",
                corrected_text="6.0",
                supersedes_correction_id="corr-1",
            )
        )


def test_correction_base_revision_must_be_base_kind(revision_stack):
    """校对锚定的 base_processing_revision_id 必须是 base 修订（不能是 complete）。"""
    session, _fixture, keys = revision_stack
    complete = CompleteEvidenceProcessingRevisionRepository(session)
    complete.create(_closed_revision(keys, session))
    repo = CorrectionRepository(session)
    from app.storage.evidence_locator_repositories import Slice44RepositoryError

    with pytest.raises(Slice44RepositoryError, match="必须是 base 修订"):
        repo.create(
            _correction(
                keys,
                correction_id="corr-x",
                base_processing_revision_id="complete-1",
            )
        )


def test_risk_review_base_revision_must_be_base_kind(revision_stack):
    session, _fixture, keys = revision_stack
    complete = CompleteEvidenceProcessingRevisionRepository(session)
    complete.create(_closed_revision(keys, session))
    from app.storage.evidence_locator_repositories import Slice44RepositoryError

    scan = OCRRiskScanRepository(session)
    scan.get_or_create(_scan(keys))
    with pytest.raises(Slice44RepositoryError, match="必须是 base 修订"):
        OCRRiskReviewRepository(session).create(
            OCRRiskReview(
                review_id="rv-x",
                risk_flag_id="scan-1:r1",
                decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
                reason="r",
                actor="user",
                base_processing_revision_id="complete-1",
                expected_revision=1,
                created_at=FIXED_UTC,
            )
        )


# --- Finding 6: 被提及资料作用域 ---


def test_referenced_document_trigger_cross_scope_rejected(revision_stack):
    """触发定位与被提及资料跨审核节点 → 拒绝。"""
    from app.domain.contracts.review import ReviewEpisode as Ep
    from app.storage.repositories import EpisodeRepository

    session, _fixture, keys = revision_stack
    fixture = keys["fixture"]
    episode_template = fixture.review_episode
    # 建立第二个审核节点（同 project/subject）及其资料版本与定位。
    other_episode = Ep(
        review_episode_id="ep-other",
        subject_id=episode_template.subject_id,
        project_id=episode_template.project_id,
        rule_set_id=episode_template.rule_set_id,
        study_phase=episode_template.study_phase,
        stage=episode_template.stage,
        protocol_version_id=episode_template.protocol_version_id,
        rule_set_revision=episode_template.rule_set_revision,
        evidence_snapshot_id=episode_template.evidence_snapshot_id,
        anchor_dates={},
    )
    EpisodeRepository(session).save(other_episode)
    from app.domain.contracts.evidence_ingestion import (
        SourceBlob as SB,
    )
    from app.domain.contracts.evidence_ingestion import (
        SourceDocumentVersion as SDV,
    )

    blob2 = SB(
        source_blob_id="2" * 64, sha256="2" * 64, byte_size=1,
        media_type="application/pdf", storage_ref="blobs/" + "2" * 64,
        created_at=FIXED_UTC,
    )
    BlobRepository(session).get_or_create_by_sha256(blob2)
    SourceDocumentRepository(session).create_version(
        SDV(
            source_document_version_id="doc-other",
            logical_document_id="log-other",
            source_blob_sha256="2" * 64,
            file_name="other.pdf",
            media_type="application/pdf",
            page_count=1,
            project_id=keys["project_id"],
            subject_id=keys["subject_id"],
            review_episode_id="ep-other",
            version_number=1,
            created_at=FIXED_UTC,
            created_by="tester",
        )
    )
    PageArtifactRepository(session).get_or_create(
        make_artifact(
            artifact_id="pa-other", version_id="doc-other", page_input="9" * 64
        )
    )
    profile = OCRProfileRepository(session).get_or_create(make_profile())
    OcrPageRepository(session).create(
        make_ocr_page(
            page_id="op-other",
            artifact_id="pa-other",
            raw_text=RAW_TEXT,
            page_input="9" * 64,
            profile_sha=profile.profile_sha256,
        )
    )
    session.flush()
    EvidenceLocatorRepository(session).create(
        _locator(
            keys,
            locator_id="loc-other-episode",
            page_artifact_id="pa-other",
            ocr_page_id="op-other",
            source_document_version_id="doc-other",
            source_text_sha256=sha(RAW_TEXT.encode("utf-8")),
            text_start=0,
            text_end=5,
            excerpt="ALT 5",
        )
    )
    repo = ReferencedDocumentRepository(session)
    with pytest.raises(Slice44RepositoryError, match="不属于同一 project/subject/review episode"):
        repo.create_revision(
            _referenced(keys, trigger_locator_id="loc-other-episode")
        )


def test_referenced_document_provided_must_be_current_snapshot_member(
    revision_stack, session_factory
):
    """仓储写入时即拒绝不属于当前活动快照的同作用域资料。"""
    from app.services.evidence_activation_service import EvidenceActivationService

    session, _fixture, keys = revision_stack
    complete = CompleteEvidenceProcessingRevisionRepository(session).create(
        _closed_revision(keys, session)
    )
    candidate_repo = EvidenceProcessingCandidateRepository(session)
    candidate = candidate_repo.get(complete.producer_candidate_id)
    candidate_repo.append_event(
        _candidate_event(
            candidate.candidate_id,
            2,
            "processing",
            "all_gates_passed",
            "ready",
            complete_revision_id=complete.evidence_processing_revision_id,
        )
    )
    EvidenceSnapshotRepository(session).transition_status(
        "snap-1",
        event="all_gates_passed",
        new_status=SnapshotStatus.READY,
        actor="tester",
        reason="处理闭包已完成",
    )
    session.commit()
    EvidenceActivationService(session_factory).activate(
        target_snapshot_id="snap-1",
        target_revision_id=complete.evidence_processing_revision_id,
        expected_revision=1,
        actor="tester",
        reason="建立当前活动资料版本",
        candidate_id=candidate.candidate_id,
    )
    session.expire_all()

    ref_repo = ReferencedDocumentRepository(session)
    ref_repo.create_revision(_referenced(keys))
    ref_repo.create_revision(
        _referenced(keys, revision_id="rd-2", revision=2, supersedes_revision_id="rd-1")
    )
    # doc-2 是真实资料但【不是】 snap-1 快照成员 / 页清单成员。
    from app.domain.contracts.evidence_ingestion import (
        SourceBlob as SB,
    )
    from app.domain.contracts.evidence_ingestion import (
        SourceDocumentVersion as SDV,
    )

    blob2 = SB(
        source_blob_id="3" * 64, sha256="3" * 64, byte_size=1,
        media_type="application/pdf", storage_ref="blobs/" + "3" * 64,
        created_at=FIXED_UTC,
    )
    BlobRepository(session).get_or_create_by_sha256(blob2)
    SourceDocumentRepository(session).create_version(
        SDV(
            source_document_version_id="doc-2", logical_document_id="log-2",
            source_blob_sha256="3" * 64, file_name="y.pdf",
            media_type="application/pdf", page_count=1,
            project_id=keys["project_id"], subject_id=keys["subject_id"],
            review_episode_id=keys["episode_id"], version_number=1,
            created_at=FIXED_UTC, created_by="tester",
        )
    )
    session.flush()
    with pytest.raises(Slice44RepositoryError, match="当前活动资料快照中的成员"):
        ref_repo.create_resolution(
            ReferencedDocumentResolutionRevision(
                resolution_revision_id="res-1",
                referenced_document_id="doc-ref",
                status="provided",
                source_document_version_id="doc-2",
                revision=1,
                created_at=FIXED_UTC,
                created_by="user",
            )
        )
    from app.storage.evidence_locator_models import (
        ReferencedDocumentResolutionRevisionRecord,
    )

    assert session.get(ReferencedDocumentResolutionRevisionRecord, "res-1") is None


# ---------------------------------------------------------------------------
# WP-44A 修复回归（Pass 2）：页数闭包 / occurrence 身份 / 工件真实性 /
# 风险闭包 base 绑定 / 被提及资料链头 / 闭包哈希子 payload / SQL CHECK / 原子性
# ---------------------------------------------------------------------------


def _seed_two_page_revision(session, keys):
    """把 base 修订扩展为两页（doc-1 page_count=2 + 第二页产物/OCR），返回新 base id。"""
    from app.domain.contracts.enums import PageArtifactStatus
    from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
    from app.domain.publication import evidence_processing_manifest_hash

    # 更新 doc-1 page_count=2（列 + payload 同步，避免镜像校验拒绝）
    from app.storage.codecs import encode_contract

    document = session.get(SourceDocumentVersionV2Record, "doc-1")
    document.page_count = 2
    payload = json.loads(document.payload_json)
    payload["page_count"] = 2
    document.payload_json, document.payload_sha256 = encode_contract(
        _rehydrate_document(payload)
    )
    PageArtifactRepository(session).get_or_create(
        make_artifact(
            artifact_id="pa-2b", version_id="doc-1", page_number=2,
            page_input="4" * 64,
        )
    )
    profile = OCRProfileRepository(session).get_or_create(make_profile())
    OcrPageRepository(session).create(
        make_ocr_page(
            page_id="op-2b", artifact_id="pa-2b", page_number=2,
            raw_text="second page", page_input="4" * 64,
            profile_sha=profile.profile_sha256,
        )
    )
    session.flush()
    entry2 = EvidenceProcessingRevisionPage(
        entry_id="e2", position=2, source_document_version_id="doc-1",
        page_number=2, original_frame=None, page_artifact_id="pa-2b",
        ocr_page_id="op-2b", status=PageArtifactStatus.SUCCEEDED,
    )
    manifest_hash = evidence_processing_manifest_hash(
        entries=[
            ("doc-1", 1, None, "pa-1", "op-1", PageArtifactStatus.SUCCEEDED.value),
            ("doc-1", 2, None, "pa-2b", "op-2b", PageArtifactStatus.SUCCEEDED.value),
        ]
    )
    base2 = EvidenceProcessingRevision(
        evidence_processing_revision_id="rev-2p",
        evidence_snapshot_id="snap-1",
        project_id=keys["project_id"], subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"],
        manifest=[keys["entry"], entry2],
        manifest_sha256=manifest_hash,
        status="ready", is_activatable=False,
        created_at=FIXED_UTC, created_by="tester",
    )
    EvidenceProcessingRevisionRepository(session).create(base2)
    session.flush()
    return "rev-2p", entry2, manifest_hash


def test_complete_revision_rejects_missing_second_page(revision_stack):
    """page_count=2 但页清单只有第 1 页 → 缺页闭包拒绝（Fix 1 反例）。"""
    session, _fixture, keys = revision_stack
    from app.storage.codecs import encode_contract as _enc

    # base 修订只有 1 页；把 doc-1 page_count 改成 2（列 + payload 同步）但清单仍 1 页。
    document = session.get(SourceDocumentVersionV2Record, "doc-1")
    document.page_count = 2
    payload = json.loads(document.payload_json)
    payload["page_count"] = 2
    document.payload_json, document.payload_sha256 = _enc(
        _rehydrate_document(payload)
    )
    session.flush()
    metadata_id = _seed_metadata(session, keys)
    scan_id, review_ids = _seed_scan_and_review(session, keys)
    rev = _incomplete_revision(
        keys,
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        risk_review_ids=review_ids,
    )
    with pytest.raises(RevisionClosureError, match="期望页集合|page_count"):
        CompleteEvidenceProcessingRevisionRepository(session).create(rev)


def _rehydrate_document(payload):
    """把 payload dict 还原为合同对象（用 encode_contract 生成一致 payload/hash）。"""
    from app.domain.contracts.evidence_ingestion import SourceDocumentVersion

    return SourceDocumentVersion.model_validate(payload)


def test_complete_revision_two_page_closure_ok(revision_stack):
    """两页 base 修订 + 两页完整修订 + 每页扫描/核对 → 闭包通过。"""
    session, _fixture, keys = revision_stack
    _, entry2, manifest_hash = _seed_two_page_revision(session, keys)
    # 第二页的扫描 + 核对（blocking flag 需解除）；核对 base 必须是 rev-2p。
    second_scan = _scan(
        keys, scan_id="scan-2p", ocr_page_id="op-2b",
        raw_text_sha256=sha(b"second page"),
        flags=[_flag(risk_id="r1", text="second page"[0:7], start=0, end=7,
                     rule_version="rules/v1")],
    )
    OCRRiskScanRepository(session).get_or_create(second_scan)
    OCRRiskReviewRepository(session).create(
        OCRRiskReview(
            review_id="rv-2p", risk_flag_id="scan-2p:r1",
            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
            reason="已核对", actor="user",
            base_processing_revision_id="rev-2p", expected_revision=1,
            created_at=FIXED_UTC,
        )
    )
    metadata_id = _seed_metadata(session, keys)
    # 第一页的扫描 + 核对 base 也必须是 rev-2p（跨 base 选择拒绝）。
    scan1, _ = _seed_scan_and_review(session, keys, review=False)
    OCRRiskReviewRepository(session).create(
        OCRRiskReview(
            review_id="rv-1-2p", risk_flag_id="scan-1:r1",
            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
            reason="已核对", actor="user",
            base_processing_revision_id="rev-2p", expected_revision=1,
            created_at=FIXED_UTC,
        )
    )
    values = {
        "evidence_processing_revision_id": "complete-2p",
        "base_processing_revision_id": "rev-2p",
        "manifest": [keys["entry"], entry2],
        "manifest_sha256": manifest_hash,
        "metadata_revision_ids": [metadata_id],
        "risk_scan_ids": [scan1, "scan-2p"],
        "risk_review_ids": ["rv-1-2p", "rv-2p"],
    }
    rev = _complete_revision(keys, session, **values)
    created = CompleteEvidenceProcessingRevisionRepository(session).create(rev)
    assert created.is_activatable is True
    assert len(created.manifest) == 2


def test_complete_revision_scope_mismatch_rejected(revision_stack):
    """完整修订与快照/base 的 project/subject 不一致 → 拒绝（Fix 1 作用域）。"""
    session, _fixture, keys = revision_stack
    metadata_id = _seed_metadata(session, keys)
    scan_id, review_ids = _seed_scan_and_review(session, keys)
    rev = _complete_revision(
        keys, session,
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        risk_review_ids=review_ids,
    )
    cross = rev.model_copy(update={"project_id": "project-other"})
    with pytest.raises(RevisionClosureError, match="作用域"):
        CompleteEvidenceProcessingRevisionRepository(session).create(cross)


def test_locator_page_excerpt_distinct_anchors_coexist(revision_stack):
    """不同摘录/锚点哈希的 page_excerpt 互不碰撞；同锚点精确别名碰撞。"""
    session, _fixture, keys = revision_stack
    repo = EvidenceLocatorRepository(session)
    def _ex(locator_id, anchor, excerpt):
        return _locator(
            keys,
            locator_id=locator_id,
            page_artifact_id="pa-1", ocr_page_id="op-1",
            source_document_version_id="doc-1", page_number=1,
            source_layer="raw_ocr",
            source_text_sha256=sha(RAW_TEXT.encode("utf-8")),
            precision="page_excerpt", disambiguation="repeated_text_degraded",
            degradation_reason="多处相同文本", authenticity="degraded",
            excerpt=excerpt, anchor_hash=anchor, text_start=None, text_end=None,
        )
    a = locator_anchor_hash(
        page_artifact_id="pa-1",
        source_layer=LocatorSourceLayer.RAW_OCR,
        source_text_sha256=sha(RAW_TEXT.encode("utf-8")),
        precision=LocatorPrecision.PAGE_EXCERPT,
        target_id="target-1",
        excerpt="ALT",
        disambiguation=DisambiguationOutcome.REPEATED_TEXT_DEGRADED,
        degradation_reason="多处相同文本",
    )
    b = locator_anchor_hash(
        page_artifact_id="pa-1",
        source_layer=LocatorSourceLayer.RAW_OCR,
        source_text_sha256=sha(RAW_TEXT.encode("utf-8")),
        precision=LocatorPrecision.PAGE_EXCERPT,
        target_id="target-1",
        excerpt="AST",
        disambiguation=DisambiguationOutcome.REPEATED_TEXT_DEGRADED,
        degradation_reason="多处相同文本",
    )
    repo.create(_ex("ex-a", a, "ALT"))
    repo.create(_ex("ex-b", b, "AST"))
    # 同一摘录/锚点 + 不同 locator_id → 身份碰撞
    with pytest.raises(LocatorIdentityError, match="身份碰撞"):
        repo.create(_ex("ex-a2", a, "ALT"))


def test_locator_page_excerpt_must_exist_in_source_text(revision_stack):
    """摘录及其哈希不能自证；摘录必须能在所绑定的同源文本中回放。"""
    session, _fixture, keys = revision_stack
    excerpt = "原文中不存在的摘录"
    locator = _locator(
        keys,
        locator_id="ex-missing",
        precision="page_excerpt",
        disambiguation="repeated_text_degraded",
        degradation_reason="无法稳定消歧",
        excerpt=excerpt,
        anchor_hash=locator_anchor_hash(
            page_artifact_id="pa-1",
            source_layer=LocatorSourceLayer.RAW_OCR,
            source_text_sha256=sha(RAW_TEXT.encode("utf-8")),
            precision=LocatorPrecision.PAGE_EXCERPT,
            target_id="target-1",
            excerpt=excerpt,
            disambiguation=DisambiguationOutcome.REPEATED_TEXT_DEGRADED,
            degradation_reason="无法稳定消歧",
        ),
        text_start=None,
        text_end=None,
    )
    with pytest.raises(LocatorIdentityError, match="回放证明"):
        EvidenceLocatorRepository(session).create(locator)


def test_locator_page_only_distinct_targets_coexist(revision_stack):
    """不同目标/降级证明的 page_only 互不碰撞；同目标精确别名碰撞。"""
    session, _fixture, keys = revision_stack
    repo = EvidenceLocatorRepository(session)
    def _po(locator_id, target):
        reason = "目标未找到"
        return _locator(
            keys,
            locator_id=locator_id,
            page_artifact_id="pa-1", ocr_page_id="op-1",
            source_document_version_id="doc-1", page_number=1,
            source_layer="raw_ocr",
            source_text_sha256=sha(RAW_TEXT.encode("utf-8")),
            precision="page_only", disambiguation="not_found",
            degradation_reason=reason, authenticity="degraded",
            target_id=target,
            anchor_hash=locator_anchor_hash(
                page_artifact_id="pa-1",
                source_layer=LocatorSourceLayer.RAW_OCR,
                source_text_sha256=sha(RAW_TEXT.encode("utf-8")),
                precision=LocatorPrecision.PAGE_ONLY,
                target_id=target,
                excerpt=None,
                disambiguation=DisambiguationOutcome.NOT_FOUND,
                degradation_reason=reason,
            ),
            text_start=None, text_end=None, excerpt=None,
        )
    repo.create(_po("po-a", "tgt-a"))
    repo.create(_po("po-b", "tgt-b"))
    with pytest.raises(LocatorIdentityError, match="身份碰撞"):
        repo.create(_po("po-a2", "tgt-a"))


def test_locator_native_text_range_artifact_proof(revision_stack, artifact_store):
    """native_text 的 text_range 必须读取真实工件字节并回验范围（Fix 3）。"""
    session, _fixture, keys = revision_stack
    page_id, artifact_id = _seed_native_page(session, keys, artifact_store)
    repo = EvidenceLocatorRepository(session, artifact_store)
    ok = repo.create(
        _locator(
            keys,
            locator_id="loc-native-range",
            page_artifact_id=artifact_id, ocr_page_id=page_id,
            source_layer="native_text",
            source_text_sha256=keys["native_text_sha"],
            precision="text_range", text_start=4, text_end=7, excerpt="5.6",
            authenticity="degraded", degradation_reason="text-only 无坐标",
        )
    )
    assert ok.precision == LocatorPrecision.TEXT_RANGE
    # 工件字节被篡改 → 读取复核失败
    target = keys["artifact_store"].data_paths.root / "artifacts" / "native_text" / keys["native_text_sha"]
    target.write_bytes(b"tampered")
    with pytest.raises(LocatorIdentityError, match="内容与引用哈希不一致"):
        repo.create(
            _locator(
                keys,
                locator_id="loc-native-range2",
                page_artifact_id=artifact_id, ocr_page_id=page_id,
                source_layer="native_text",
                source_text_sha256=keys["native_text_sha"],
                precision="text_range", text_start=0, text_end=3, excerpt="ALT",
                authenticity="degraded", degradation_reason="text-only 无坐标",
            )
        )


def test_candidate_with_native_locator_uses_artifact_store_proof(
    revision_stack, artifact_store
):
    """候选冻结原生定位时必须沿用上层工件库完成真实性回验。"""
    session, _fixture, keys = revision_stack
    page_id, artifact_id = _seed_native_page(session, keys, artifact_store)
    locator = EvidenceLocatorRepository(session, artifact_store).create(
        _native_bbox_locator(keys, page_id=page_id, artifact_id=artifact_id)
    )
    entry = keys["entry"].model_copy(
        update={
            "entry_id": "entry-native",
            "page_artifact_id": artifact_id,
            "ocr_page_id": page_id,
        }
    )
    manifest_hash = evidence_processing_manifest_hash(
        entries=[
            (
                entry.source_document_version_id,
                entry.page_number,
                entry.original_frame,
                entry.page_artifact_id,
                entry.ocr_page_id,
                entry.status.value,
            )
        ]
    )
    EvidenceProcessingRevisionRepository(session).create(
        EvidenceProcessingRevision(
            evidence_processing_revision_id="rev-native",
            evidence_snapshot_id="snap-1",
            project_id=keys["project_id"],
            subject_id=keys["subject_id"],
            review_episode_id=keys["episode_id"],
            manifest=[entry],
            manifest_sha256=manifest_hash,
            status="ready",
            is_activatable=False,
            created_at=FIXED_UTC,
            created_by="tester",
        )
    )
    candidate = _candidate(
        keys,
        candidate_id="cand-native",
        idempotency_key="key-native",
        base_processing_revision_id="rev-native",
        selected_locator_ids=[locator.locator_id],
    )
    with pytest.raises(LocatorIdentityError, match="ArtifactStore"):
        EvidenceProcessingCandidateRepository(session).create(candidate)

    created = EvidenceProcessingCandidateRepository(
        session, artifact_store
    ).create(candidate)
    assert created.selected_locator_ids == [locator.locator_id]


def test_risk_closure_cross_base_review_rejected(revision_stack):
    """选中的风险核对 base 修订 ≠ 完整修订 base → 拒绝（Fix 4 反例）。"""
    session, _fixture, keys = revision_stack
    metadata_id = _seed_metadata(session, keys)
    scan_id, _review_ids = _seed_scan_and_review(session, keys, review=False)
    # 用另一个 base 修订的核对（跨 base 选择）。
    rev_other = EvidenceProcessingRevision(
        evidence_processing_revision_id="rev-other",
        evidence_snapshot_id="snap-1",
        project_id=keys["project_id"], subject_id=keys["subject_id"],
        review_episode_id=keys["episode_id"],
        manifest=[keys["entry"]], manifest_sha256=keys["manifest_hash"],
        status="ready", is_activatable=False,
        created_at=FIXED_UTC, created_by="tester",
    )
    EvidenceProcessingRevisionRepository(session).create(rev_other)
    OCRRiskReviewRepository(session).create(
        OCRRiskReview(
            review_id="rv-cross", risk_flag_id="scan-1:r1",
            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
            reason="r", actor="user",
            base_processing_revision_id="rev-other", expected_revision=1,
            created_at=FIXED_UTC,
        )
    )
    rev = _incomplete_revision(
        keys,
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        risk_review_ids=["rv-cross"],
    )
    with pytest.raises(RevisionClosureError, match="base 修订必须等于本完整修订的 base"):
        CompleteEvidenceProcessingRevisionRepository(session).create(rev)


def test_risk_closure_duplicate_review_per_flag_rejected(revision_stack):
    """同一 flag 只能选中一个有效核对（重复决策拒绝）。"""
    session, _fixture, keys = revision_stack
    metadata_id = _seed_metadata(session, keys)
    scan_id, _ = _seed_scan_and_review(session, keys, review=True)
    OCRRiskReviewRepository(session).create(
        OCRRiskReview(
            review_id="rv-dup", risk_flag_id="scan-1:r1",
            decision=OcrRiskReviewDecision.NOT_APPLICABLE,
            reason="dup", actor="user",
            base_processing_revision_id="rev-1", expected_revision=1,
            created_at=FIXED_UTC,
        )
    )
    rev = _incomplete_revision(
        keys,
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        risk_review_ids=["rv-1", "rv-dup"],
    )
    with pytest.raises(RevisionClosureError, match="只能选中一个有效核对"):
        CompleteEvidenceProcessingRevisionRepository(session).create(rev)


def test_correction_branch_chain_rejected(revision_stack):
    """校对替代必须指向当前链头；分支/跳链拒绝（Fix 4）。"""
    session, _fixture, keys = revision_stack
    repo = CorrectionRepository(session)
    repo.create(_correction(keys, correction_id="corr-a"))
    repo.create(
        _correction(
            keys, correction_id="corr-b",
            supersedes_correction_id="corr-a",
        )
    )
    # corr-c 也想替代 corr-a（已被 corr-b 替代）→ 分支拒绝
    with pytest.raises(CorrectionOverlapError, match="当前链头"):
        repo.create(
            _correction(
                keys, correction_id="corr-c",
                supersedes_correction_id="corr-a",
            )
        )


def test_referenced_document_and_resolution_branches_rejected(revision_stack):
    """登记链和满足链都只能从当前链头追加，旧头不得产生第二分支。"""
    session, _fixture, keys = revision_stack
    repo = ReferencedDocumentRepository(session)
    repo.create_revision(_referenced(keys, revision_id="rd-a"))
    repo.create_revision(
        _referenced(
            keys,
            revision_id="rd-b",
            revision=2,
            supersedes_revision_id="rd-a",
        )
    )
    with pytest.raises(CandidateStateTransitionError, match="当前链头"):
        repo.create_revision(
            _referenced(
                keys,
                revision_id="rd-c",
                revision=3,
                supersedes_revision_id="rd-a",
            )
        )

    repo.create_resolution(
        ReferencedDocumentResolutionRevision(
            resolution_revision_id="res-a",
            referenced_document_id="doc-ref",
            status="unresolved",
            revision=1,
            created_at=FIXED_UTC,
            created_by="user",
        )
    )
    repo.create_resolution(
        ReferencedDocumentResolutionRevision(
            resolution_revision_id="res-b",
            referenced_document_id="doc-ref",
            status="unresolved",
            revision=2,
            supersedes_resolution_revision_id="res-a",
            created_at=FIXED_UTC,
            created_by="user",
        )
    )
    with pytest.raises(CandidateStateTransitionError, match="当前链头"):
        repo.create_resolution(
            ReferencedDocumentResolutionRevision(
                resolution_revision_id="res-c",
                referenced_document_id="doc-ref",
                status="unresolved",
                revision=3,
                supersedes_resolution_revision_id="res-a",
                created_at=FIXED_UTC,
                created_by="user",
            )
        )


def test_correction_stale_head_rejected(revision_stack):
    """替代非链头的旧校对（跳过当前头）→ 拒绝。"""
    session, _fixture, keys = revision_stack
    repo = CorrectionRepository(session)
    repo.create(_correction(keys, correction_id="corr-a"))
    repo.create(
        _correction(
            keys, correction_id="corr-b",
            supersedes_correction_id="corr-a",
        )
    )
    # corr-c 跳过 corr-b 直接替代 corr-a（陈旧选择）→ 拒绝
    with pytest.raises(CorrectionOverlapError, match="当前链头"):
        repo.create(
            _correction(
                keys, correction_id="corr-c",
                supersedes_correction_id="corr-a",
            )
        )


def test_referenced_doc_confirmed_requires_resolution(revision_stack):
    """confirmed 登记资料必须同时选中链头满足修订（缺满足修订 = 闭包不完整，Fix 5）。"""
    session, _fixture, keys = revision_stack
    ref_repo = ReferencedDocumentRepository(session)
    # 先建一个同 episode 的真实定位作为触发。
    locator = _locator(keys, locator_id="loc-ref-trigger", text_start=0, text_end=5)
    EvidenceLocatorRepository(session).create(locator)
    ref_repo.create_revision(
        _referenced(keys, status="confirmed", trigger_locator_id="loc-ref-trigger")
    )
    metadata_id = _seed_metadata(session, keys)
    scan_id, review_ids = _seed_scan_and_review(session, keys)
    rev = _incomplete_revision(
        keys,
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        risk_review_ids=review_ids,
        locator_ids=["loc-ref-trigger"],
        referenced_document_revision_ids=["rd-1"],
        resolution_revision_ids=[],  # 缺满足修订
    )
    with pytest.raises(RevisionClosureError, match="缺少选中的满足修订"):
        CompleteEvidenceProcessingRevisionRepository(session).create(rev)


def test_referenced_doc_stale_head_selection_rejected(revision_stack):
    """选中非链头登记修订（已存在后继）→ 拒绝（Fix 5）。"""
    session, _fixture, keys = revision_stack
    ref_repo = ReferencedDocumentRepository(session)
    ref_repo.create_revision(_referenced(keys, revision_id="rd-a"))
    ref_repo.create_revision(
        _referenced(keys, revision_id="rd-b", revision=2, supersedes_revision_id="rd-a")
    )
    ref_repo.create_resolution(
        ReferencedDocumentResolutionRevision(
            resolution_revision_id="res-b", referenced_document_id="doc-ref",
            status="unresolved", revision=1, created_at=FIXED_UTC, created_by="user",
        )
    )
    metadata_id = _seed_metadata(session, keys)
    scan_id, review_ids = _seed_scan_and_review(session, keys)
    # 选中旧链头 rd-a（rd-b 已是链头）→ 拒绝
    rev = _incomplete_revision(
        keys,
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        risk_review_ids=review_ids,
        referenced_document_revision_ids=["rd-a"],
        resolution_revision_ids=["res-b"],
    )
    with pytest.raises(RevisionClosureError, match="不是链头"):
        CompleteEvidenceProcessingRevisionRepository(session).create(rev)


def test_manifest_hash_child_payload_drift_rejected(revision_stack):
    """子工件 payload 漂移（ID 不变）→ 闭包哈希重算不一致，读取拒绝（Fix 7）。"""
    session, _fixture, keys = revision_stack
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    repo.create(_closed_revision(keys, session))
    # 篡改选中扫描的 payload（同 ID 不同 payload → 哈希漂移）。
    scan_record = session.get(OCRRiskScanRecord, "scan-1")
    scan_record.payload_json = '{"drift":true}'
    session.flush()
    with pytest.raises((RevisionClosureError, PersistedContractInvalid), match="不一致|漂移|payload"):
        repo.get("complete-1")


def test_sql_epr_kind_shape_check_enforced(revision_stack):
    """base 行携带 complete 形态（is_activatable=1/非空 base 指针）→ 数据库 CHECK 拒绝。"""
    session, _fixture, _keys = revision_stack
    from sqlalchemy.exc import IntegrityError

    base_row = session.get(EvidenceProcessingRevisionRecord, "rev-1")
    base_row.is_activatable = True  # base 行不允许 is_activatable=1
    with pytest.raises(IntegrityError, match="CHECK|ck_epr"):
        session.flush()
    session.rollback()


def test_sql_revision_kind_check_enforced(revision_stack):
    """revision_kind 只能是 base/complete → 非法值被数据库拒绝。"""
    session, _fixture, _keys = revision_stack
    from sqlalchemy.exc import IntegrityError

    base_row = session.get(EvidenceProcessingRevisionRecord, "rev-1")
    base_row.revision_kind = "bogus"
    with pytest.raises(IntegrityError, match="CHECK|ck_epr"):
        session.flush()
    session.rollback()


def test_complete_revision_failed_create_leaves_no_partial_rows(revision_stack):
    """闭包失败不得留下 root/page/association 半成品（Fix 6 原子性）。"""
    session, _fixture, keys = revision_stack
    from app.storage.evidence_locator_models import ProcessingRevisionLocatorRecord
    from app.storage.ocr_models import EvidenceProcessingRevisionPageRecord

    # 缺元数据 → create 失败
    rev = _incomplete_revision(keys)
    with pytest.raises(RevisionClosureError):
        CompleteEvidenceProcessingRevisionRepository(session).create(rev)
    session.rollback()
    from app.storage.ocr_models import EvidenceProcessingRevisionRecord as EPR

    assert session.get(EPR, "complete-1") is None
    page_rows = session.execute(
        select(EvidenceProcessingRevisionPageRecord).where(
            EvidenceProcessingRevisionPageRecord.revision_id == "complete-1"
        )
    ).scalars().all()
    assert page_rows == []
    loc_rows = session.execute(
        select(ProcessingRevisionLocatorRecord).where(
            ProcessingRevisionLocatorRecord.revision_id == "complete-1"
        )
    ).scalars().all()
    assert loc_rows == []


def test_complete_revision_readback_failure_rolls_back_savepoint(
    revision_stack, monkeypatch
):
    """写入后读回验证失败，即使调用方继续 commit 也不能留下半闭包根。"""
    session, _fixture, keys = revision_stack
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    revision = _closed_revision(keys, session)

    def fail_readback(_contract):
        raise RuntimeError("injected readback failure")

    monkeypatch.setattr(repo, "_verify_assoc_mirror", fail_readback)
    with pytest.raises(RuntimeError, match="injected"):
        repo.create(revision)
    session.commit()
    assert session.get(EvidenceProcessingRevisionRecord, "complete-1") is None
    assert session.execute(
        select(EvidenceProcessingRevisionPageRecord).where(
            EvidenceProcessingRevisionPageRecord.revision_id == "complete-1"
        )
    ).scalars().all() == []


def test_complete_revision_missing_persisted_page_rejected_on_read(revision_stack):
    """根 payload 不能自证页闭包；删除实际页子表后历史读取必须失败。"""
    session, _fixture, keys = revision_stack
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    repo.create(_closed_revision(keys, session))
    session.execute(
        delete(EvidenceProcessingRevisionPageRecord).where(
            EvidenceProcessingRevisionPageRecord.revision_id == "complete-1"
        )
    )
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="实际页子表"):
        repo.get("complete-1")


def test_complete_revision_locator_must_bind_selected_page_artifact(revision_stack):
    """同资料同页的另一 PageArtifact/OCRPage 也不能替换 base 清单所选页。"""
    session, _fixture, keys = revision_stack
    profile = OCRProfileRepository(session).get_or_create(make_profile())
    PageArtifactRepository(session).get_or_create(
        make_artifact(
            artifact_id="pa-alt",
            version_id="doc-1",
            page_number=1,
            page_input="6" * 64,
        )
    )
    OcrPageRepository(session).create(
        make_ocr_page(
            page_id="op-alt",
            artifact_id="pa-alt",
            page_number=1,
            raw_text=RAW_TEXT,
            page_input="6" * 64,
            profile_sha=profile.profile_sha256,
        )
    )
    EvidenceLocatorRepository(session).create(
        _locator(
            keys,
            locator_id="loc-alt-page",
            page_artifact_id="pa-alt",
            ocr_page_id="op-alt",
        )
    )
    metadata_id = _seed_metadata(session, keys)
    scan_id, review_ids = _seed_scan_and_review(session, keys)
    revision = _complete_revision(
        keys,
        session,
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        risk_review_ids=review_ids,
        locator_ids=["loc-alt-page"],
    )
    with pytest.raises(RevisionClosureError, match="定位页产物不在页清单"):
        CompleteEvidenceProcessingRevisionRepository(session).create(revision)


def test_complete_revision_rejects_stale_correction_head(revision_stack):
    """新完整修订只能冻结当前有效校对，已被替代的校对不能再次入选。"""
    session, _fixture, keys = revision_stack
    corrections = CorrectionRepository(session)
    corrections.create(_correction(keys, correction_id="corr-a"))
    corrections.create(
        _correction(
            keys,
            correction_id="corr-b",
            supersedes_correction_id="corr-a",
        )
    )
    metadata_id = _seed_metadata(session, keys)
    scan_id, _ = _seed_scan_and_review(session, keys, review=False)
    revision = _complete_revision(
        keys,
        session,
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        correction_ids=["corr-a"],
    )
    with pytest.raises(RevisionClosureError, match="不是当前链头"):
        CompleteEvidenceProcessingRevisionRepository(session).create(revision)


def test_complete_revision_history_survives_later_chain_successors(revision_stack):
    """后续校对/元数据/被提及资料修订不得破坏旧完整修订的精确回放。"""
    from app.domain.contracts.evidence_ingestion import SourceDocumentMetadataRevision

    session, _fixture, keys = revision_stack
    locators = EvidenceLocatorRepository(session)
    locators.create(_locator(keys, locator_id="loc-history"))
    corrections = CorrectionRepository(session)
    corrections.create(_correction(keys, correction_id="corr-history-1"))
    references = ReferencedDocumentRepository(session)
    references.create_revision(
        _referenced(
            keys,
            revision_id="rd-history-1",
            status="confirmed",
            trigger_locator_id="loc-history",
        )
    )
    references.create_resolution(
        ReferencedDocumentResolutionRevision(
            resolution_revision_id="res-history-1",
            referenced_document_id="doc-ref",
            status="unresolved",
            revision=1,
            created_at=FIXED_UTC,
            created_by="user",
        )
    )
    metadata_id = _seed_metadata(session, keys)
    scan_id, _ = _seed_scan_and_review(session, keys, review=False)
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    revision = _complete_revision(
        keys,
        session,
        locator_ids=["loc-history"],
        correction_ids=["corr-history-1"],
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=[scan_id],
        referenced_document_revision_ids=["rd-history-1"],
        resolution_revision_ids=["res-history-1"],
    )
    repo.create(revision)

    corrections.create(
        _correction(
            keys,
            correction_id="corr-history-2",
            supersedes_correction_id="corr-history-1",
        )
    )
    SourceDocumentMetadataRevisionRepository(session).append(
        SourceDocumentMetadataRevision(
            metadata_revision_id="mdr-2",
            source_document_version_id="doc-1",
            document_type="lab",
            source_party="hospital",
            reason="后续修订",
            is_auto_suggestion=False,
            revision=2,
            supersedes_metadata_revision_id="mdr-1",
            created_at=FIXED_UTC,
            created_by="tester",
        )
    )
    references.create_revision(
        _referenced(
            keys,
            revision_id="rd-history-2",
            status="confirmed",
            trigger_locator_id="loc-history",
            revision=2,
            supersedes_revision_id="rd-history-1",
        )
    )
    references.create_resolution(
        ReferencedDocumentResolutionRevision(
            resolution_revision_id="res-history-2",
            referenced_document_id="doc-ref",
            status="unresolved",
            revision=2,
            supersedes_resolution_revision_id="res-history-1",
            created_at=FIXED_UTC,
            created_by="user",
        )
    )
    replayed = repo.get("complete-1")
    assert replayed.correction_ids == ["corr-history-1"]
    assert replayed.metadata_revision_ids == ["mdr-1"]
    assert replayed.referenced_document_revision_ids == ["rd-history-1"]


def test_sql_review_base_fk_not_null(revision_stack):
    """风险核对 base_processing_revision_id 必须非空（数据库 NOT NULL）。"""
    session, _fixture, _keys = revision_stack
    from sqlalchemy.exc import IntegrityError

    from app.storage.evidence_locator_models import OCRRiskReviewRecord

    OCRRiskScanRepository(session).get_or_create(_scan(_keys))
    session.add(
        OCRRiskReviewRecord(
            review_id="rv-nullbase",
            risk_flag_id="scan-1:r1",
            decision="confirmed_as_read",
            reason="r",
            actor="user",
            base_processing_revision_id=None,
            expected_revision=1,
            payload_json="{}",
            payload_sha256="e" * 64,
            created_at=FIXED_UTC,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_sql_correction_base_fk_not_null(revision_stack):
    """校对 base_processing_revision_id 必须非空（数据库 NOT NULL）。"""
    session, _fixture, _keys = revision_stack
    from sqlalchemy.exc import IntegrityError

    from app.storage.evidence_locator_models import CorrectionRecordRecord

    session.add(
        CorrectionRecordRecord(
            correction_id="corr-nullbase",
            ocr_page_id="op-1",
            raw_text_sha256=sha(RAW_TEXT.encode("utf-8")),
            text_start=4,
            text_end=7,
            original_text="5.6",
            corrected_text="5.60",
            change_kind="decimal",
            requires_confirmation=True,
            confirmation_actor="user",
            confirmation_at=FIXED_UTC,
            reason="r",
            actor="user",
            base_processing_revision_id=None,
            supersedes_correction_id=None,
            affected_scope_json=[],
            payload_json="{}",
            payload_sha256="e" * 64,
            created_at=FIXED_UTC,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_sql_correction_same_occurrence_root_is_unique(revision_stack):
    """并发旁路也不能绕过同一原文范围单根约束。"""
    session, _fixture, keys = revision_stack
    from sqlalchemy.exc import IntegrityError

    from app.storage.evidence_locator_models import CorrectionRecordRecord

    CorrectionRepository(session).create(
        _correction(keys, correction_id="corr-root-db-a")
    )
    session.add(
        CorrectionRecordRecord(
            correction_id="corr-root-db-b",
            ocr_page_id="op-1",
            raw_text_sha256=sha(RAW_TEXT.encode("utf-8")),
            text_start=4,
            text_end=7,
            original_text="5.6",
            corrected_text="5.600",
            change_kind="decimal",
            requires_confirmation=True,
            confirmation_actor="user",
            confirmation_at=FIXED_UTC,
            reason="r",
            actor="user",
            base_processing_revision_id="rev-1",
            supersedes_correction_id=None,
            affected_scope_json=[],
            payload_json="{}",
            payload_sha256="e" * 64,
            created_at=FIXED_UTC,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_manifest_hash_order_sensitivity_per_family(revision_stack):
    """每个关联家族的 ID 顺序漂移都改变闭包哈希（Fix 7 顺序敏感）。"""
    session, _fixture, keys = revision_stack
    repo = CompleteEvidenceProcessingRevisionRepository(session)
    # 建立两页闭包后，比较不同顺序的闭包哈希。
    _, entry2, manifest_hash = _seed_two_page_revision(session, keys)
    second_scan = _scan(
        keys, scan_id="scan-2p", ocr_page_id="op-2b",
        raw_text_sha256=sha(b"second page"),
        flags=[_flag(risk_id="r1", text="second page"[0:7], start=0, end=7,
                     rule_version="rules/v1")],
    )
    OCRRiskScanRepository(session).get_or_create(second_scan)
    OCRRiskReviewRepository(session).create(
        OCRRiskReview(
            review_id="rv-2p", risk_flag_id="scan-2p:r1",
            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
            reason="已核对", actor="user",
            base_processing_revision_id="rev-2p", expected_revision=1,
            created_at=FIXED_UTC,
        )
    )
    metadata_id = _seed_metadata(session, keys)
    scan1, _ = _seed_scan_and_review(session, keys, review=False)
    OCRRiskReviewRepository(session).create(
        OCRRiskReview(
            review_id="rv-1-2p", risk_flag_id="scan-1:r1",
            decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
            reason="已核对", actor="user",
            base_processing_revision_id="rev-2p", expected_revision=1,
            created_at=FIXED_UTC,
        )
    )
    base_rev = {
        "evidence_processing_revision_id": "complete-ord",
        "base_processing_revision_id": "rev-2p",
        "manifest": [keys["entry"], entry2],
        "manifest_sha256": manifest_hash,
        "metadata_revision_ids": [metadata_id],
        "risk_scan_ids": [scan1, "scan-2p"],
        "risk_review_ids": ["rv-1-2p", "rv-2p"],
    }
    rev = _complete_revision(keys, session, **base_rev)
    swapped = rev.model_copy(
        update={"risk_scan_ids": ["scan-2p", scan1], "risk_review_ids": ["rv-2p", "rv-1-2p"]}
    )
    assert rev.completion_manifest_sha256 != repo.manifest_sha256_for(swapped)
    # 子 payload 漂移且 payload_sha256 同步更新（同 ID 不同 payload hash）→ 闭包哈希变化。
    scan_row = session.get(OCRRiskScanRecord, scan1)
    original_json, original_sha = scan_row.payload_json, scan_row.payload_sha256
    drifted_json = json.dumps({"drift": True})
    scan_row.payload_json = drifted_json
    scan_row.payload_sha256 = sha(drifted_json.encode("utf-8"))
    session.flush()
    try:
        assert repo.manifest_sha256_for(rev) != rev.completion_manifest_sha256
    finally:
        scan_row.payload_json = original_json
        scan_row.payload_sha256 = original_sha
        session.flush()
