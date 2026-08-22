"""证据处理只读进度 API 与 SSE page_progress 回放（Slice 4.3，worker_03）。

- ``GET /api/v2/jobs/{job_id}/evidence-progress`` 只读投影持久 OCR 运行状态，
  返回中文业务进度，不暴露内部列名/日志；任务不存在返回 404 信封；
- SSE 只回放持久 ``page_progress`` 事件（after_seq/Last-Event-ID 语义），
  断开不取消任务。
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from app.domain.contracts.enums import (
    JobEventType,
    OcrRunStatus,
    SnapshotMemberOrigin,
    SnapshotStatus,
    UploadMode,
)
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    EvidenceSnapshotMember,
    SourceBlob,
    SourceDocumentVersion,
)
from app.domain.contracts.evidence_processing import OCRRun
from app.domain.contracts.evidence_upload import EVIDENCE_PROCESSING_JOB_TYPE
from app.domain.publication import evidence_snapshot_collection_hash
from app.evidence.ocr_adapter import TextOnlyOcrAdapter
from app.services.job_service import JobService, StepSpec
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)
from app.storage.ocr_repositories import (
    OCRProfileRepository,
    OcrRunRepository,
)
from app.storage.repositories import persist_fixture
from app.workflow.jobstore import JobStore
from tests.v2.api.conftest import parse_sse_frames
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

FIXED_UTC = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)


def _seed_scope(sf) -> tuple[str, str, str]:
    with sf() as session, session.begin():
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        return (
            fixture.project.project_id,
            fixture.subject.subject_id,
            fixture.review_episode.review_episode_id,
        )


def _seed_evidence(sf, scope: tuple[str, str, str], job_id: str) -> str:
    """播种 blob/版本/快照/OCR 运行（运行绑定任务），返回 ocr_run_id。"""
    project_id, subject_id, episode_id = scope
    digest = hashlib.sha256(b"content").hexdigest()
    blob = SourceBlob(
        source_blob_id=digest,
        sha256=digest,
        byte_size=7,
        media_type="image/png",
        storage_ref=f"blobs/{digest}",
        created_at=FIXED_UTC,
    )
    version = SourceDocumentVersion(
        source_document_version_id="doc-prog",
        logical_document_id="logical-prog",
        source_blob_sha256=digest,
        file_name="化验单.png",
        media_type="image/png",
        page_count=None,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        version_number=1,
        created_at=FIXED_UTC,
        created_by="tester",
    )
    member = EvidenceSnapshotMember(
        member_id="m-prog",
        snapshot_id="snap-prog",
        logical_document_id="logical-prog",
        source_document_version_id="doc-prog",
        origin=SnapshotMemberOrigin.ADDED,
    )
    snapshot = EvidenceSnapshot(
        evidence_snapshot_id="snap-prog",
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        members=[member],
        collection_sha256=evidence_snapshot_collection_hash(
            members=[("logical-prog", "doc-prog")]
        ),
        status=SnapshotStatus.STAGED,
        created_at=FIXED_UTC,
        created_by="tester",
    )
    with sf() as session, session.begin():
        BlobRepository(session).get_or_create_by_sha256(blob)
        SourceDocumentRepository(session).create_version(version)
        EvidenceSnapshotRepository(session).create_full(snapshot)
        profile = OCRProfileRepository(session).get_or_create(
            TextOnlyOcrAdapter().profile(created_at=FIXED_UTC)
        )
        run = OCRRun(
            ocr_run_id="run-prog",
            source_document_version_id="doc-prog",
            ocr_profile_id=profile.ocr_profile_id,
            ocr_profile_sha256=profile.profile_sha256,
            job_id=job_id,
            status=OcrRunStatus.RUNNING,
            page_total=5,
            page_succeeded=2,
            page_failed=1,
            started_at=FIXED_UTC,
            completed_at=None,
            created_at=FIXED_UTC,
        )
        OcrRunRepository(session).create(run)
    return "run-prog"


def _create_job(
    sf,
    scope: tuple[str, str, str] | None = None,
    *,
    snapshot_id: str = "snap-prog",
    idempotency_key: str = "progress-key",
) -> str:
    if scope is None:
        scope = _seed_scope(sf)
    project_id, subject_id, episode_id = scope
    result = JobService(sf).create_job(
        idempotency_key=idempotency_key,
        job_type=EVIDENCE_PROCESSING_JOB_TYPE,
        payload={
            "snapshot_id": snapshot_id,
            "project_id": project_id,
            "subject_id": subject_id,
            "review_episode_id": episode_id,
            "upload_mode": "full",
        },
        steps=[
            StepSpec(
                step_id="evidence_processing",
                name="evidence_processing",
                max_attempts=3,
                retryable=True,
            )
        ],
    )
    return result.job_id


def _seed_three_file_snapshot(sf, scope: tuple[str, str, str]) -> str:
    project_id, subject_id, episode_id = scope
    definitions = [
        ("doc-three-2", "logical-three-2", "化验单.pdf", 5),
        ("doc-three-1", "logical-three-1", "既往病历.pdf", 3),
        ("doc-three-3", "logical-three-3", "影像报告.pdf", 8),
    ]
    members = []
    versions = []
    blobs = []
    for doc_id, logical_id, file_name, page_count in definitions:
        digest = hashlib.sha256(doc_id.encode()).hexdigest()
        blobs.append(
            SourceBlob(
                source_blob_id=digest,
                sha256=digest,
                byte_size=1,
                media_type="application/pdf",
                storage_ref=f"blobs/{digest}",
                created_at=FIXED_UTC,
            )
        )
        versions.append(
            SourceDocumentVersion(
                source_document_version_id=doc_id,
                logical_document_id=logical_id,
                source_blob_sha256=digest,
                file_name=file_name,
                media_type="application/pdf",
                page_count=page_count,
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=episode_id,
                version_number=1,
                created_at=FIXED_UTC,
                created_by="tester",
            )
        )
        members.append(
            EvidenceSnapshotMember(
                member_id=f"m-{doc_id}",
                snapshot_id="snap-three",
                logical_document_id=logical_id,
                source_document_version_id=doc_id,
                origin=SnapshotMemberOrigin.ADDED,
            )
        )
    snapshot = EvidenceSnapshot(
        evidence_snapshot_id="snap-three",
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        upload_mode=UploadMode.FULL,
        members=members,
        collection_sha256=evidence_snapshot_collection_hash(
            members=[(member.logical_document_id, member.source_document_version_id) for member in members]
        ),
        status=SnapshotStatus.STAGED,
        created_at=FIXED_UTC,
        created_by="tester",
    )
    with sf() as session, session.begin():
        for blob, version in zip(blobs, versions):
            BlobRepository(session).get_or_create_by_sha256(blob)
            SourceDocumentRepository(session).create_version(version)
        EvidenceSnapshotRepository(session).create_full(snapshot)
    return snapshot.evidence_snapshot_id


def _append_file_progress(
    sf,
    job_id: str,
    *,
    total_pages: int,
    version_id: str,
    file_name: str,
    page_total: int,
    page_succeeded: int,
    page_failed: int = 0,
) -> None:
    with sf() as session, session.begin():
        store = JobStore(session)
        store.append_event(
            store.make_event(
                job_id=job_id,
                event_type=JobEventType.PAGE_PROGRESS,
                progress_completed=page_succeeded,
                progress_total=total_pages,
                payload={
                    "进度说明": f"已处理第 {page_succeeded} 页，共 {total_pages} 页",
                    "资料": {
                        "资料标识": version_id,
                        "资料名称": file_name,
                        "页面总数": page_total,
                        "已完成": page_succeeded,
                        "失败页数": page_failed,
                        "状态说明": "需要处理" if page_failed else "正在处理",
                    },
                },
            )
        )


def test_progress_projects_all_candidate_files_and_grows_per_page(build_app, client):
    """第二份资料逐页提交时总数递增，第三份尚未建运行仍显示等待处理。"""
    sf = client.app.state.session_factory
    scope = _seed_scope(sf)
    snapshot_id = _seed_three_file_snapshot(sf, scope)
    job_id = _create_job(sf, scope, snapshot_id=snapshot_id, idempotency_key="three-files")
    with sf() as session, session.begin():
        store = JobStore(session)
        store.append_event(
            store.make_event(
                job_id=job_id,
                event_type=JobEventType.PAGE_PROGRESS,
                progress_total=16,
                payload={
                    "进度说明": "页面清单已建立",
                    "资料进度": [
                        {"资料标识": "doc-three-1", "资料名称": "既往病历.pdf", "页面总数": 3, "已完成": 0, "失败页数": 0, "状态说明": "等待处理"},
                        {"资料标识": "doc-three-2", "资料名称": "化验单.pdf", "页面总数": 5, "已完成": 0, "失败页数": 0, "状态说明": "等待处理"},
                        {"资料标识": "doc-three-3", "资料名称": "影像报告.pdf", "页面总数": 8, "已完成": 0, "失败页数": 0, "状态说明": "等待处理"},
                    ],
                },
            )
        )

    _append_file_progress(
        sf, job_id, total_pages=16, version_id="doc-three-2", file_name="化验单.pdf", page_total=5, page_succeeded=1
    )
    first = client.get(f"/api/v2/jobs/{job_id}/evidence-progress").json()
    assert first["total_pages"] == 16
    assert first["completed_pages"] == 1
    assert len(first["files"]) == 3
    assert [item["file_name"] for item in first["files"]] == [
        "化验单.pdf",
        "既往病历.pdf",
        "影像报告.pdf",
    ]
    assert next(item for item in first["files"] if item["source_document_version_id"] == "doc-three-3")["status_label"] == "等待处理"

    _append_file_progress(
        sf, job_id, total_pages=16, version_id="doc-three-2", file_name="化验单.pdf", page_total=5, page_succeeded=2
    )
    second = client.get(f"/api/v2/jobs/{job_id}/evidence-progress").json()
    assert second["completed_pages"] == 2

    # 旧失败尝试由新页快照替代，不得与最终 16 页重复累计。
    _append_file_progress(
        sf, job_id, total_pages=16, version_id="doc-three-2", file_name="化验单.pdf", page_total=5, page_succeeded=2, page_failed=1
    )
    for version_id, file_name, page_total in (
        ("doc-three-1", "既往病历.pdf", 3),
        ("doc-three-2", "化验单.pdf", 5),
        ("doc-three-3", "影像报告.pdf", 8),
    ):
        _append_file_progress(
            sf, job_id, total_pages=16, version_id=version_id, file_name=file_name, page_total=page_total, page_succeeded=page_total
        )
    final = client.get(f"/api/v2/jobs/{job_id}/evidence-progress").json()
    assert final["total_pages"] == 16
    assert final["completed_pages"] == 16
    assert final["failed_pages"] == 0
    assert final["pending_pages"] == 0


def test_mixed_native_and_visual_routes_keep_full_processing_note(build_app, client):
    """混合原生文字/视觉资料完成后仍不能显示“无需额外图像识别”。"""
    sf = client.app.state.session_factory
    scope = _seed_scope(sf)
    snapshot_id = _seed_three_file_snapshot(sf, scope)
    job_id = _create_job(sf, scope, snapshot_id=snapshot_id, idempotency_key="mixed-routes")
    with sf() as session, session.begin():
        profile = OCRProfileRepository(session).get_or_create(
            TextOnlyOcrAdapter().profile(created_at=FIXED_UTC)
        )
        OcrRunRepository(session).create(
            OCRRun(
                ocr_run_id="run-mixed-visual",
                source_document_version_id="doc-three-2",
                ocr_profile_id=profile.ocr_profile_id,
                ocr_profile_sha256=profile.profile_sha256,
                job_id=job_id,
                status=OcrRunStatus.SUCCEEDED,
                page_total=5,
                page_succeeded=5,
                page_failed=0,
                started_at=FIXED_UTC,
                completed_at=FIXED_UTC,
                created_at=FIXED_UTC,
            )
        )
    for version_id, file_name, page_total in (
        ("doc-three-1", "既往病历.pdf", 3),
        ("doc-three-2", "化验单.pdf", 5),
        ("doc-three-3", "影像报告.pdf", 8),
    ):
        _append_file_progress(
            sf,
            job_id,
            total_pages=16,
            version_id=version_id,
            file_name=file_name,
            page_total=page_total,
            page_succeeded=page_total,
        )

    body = client.get(f"/api/v2/jobs/{job_id}/evidence-progress").json()
    assert body["completed_pages"] == 16
    assert "直接读取" not in body["scope_note"]
    assert "图像识别" in body["scope_note"]


def test_evidence_progress_endpoint_returns_chinese_progress(build_app, client):
    sf = client.app.state.session_factory
    scope = _seed_scope(sf)
    job_id = _create_job(sf, scope)
    _seed_evidence(sf, scope, job_id)

    resp = client.get(f"/api/v2/jobs/{job_id}/evidence-progress")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_pages"] == 5
    assert body["completed_pages"] == 2
    assert body["failed_pages"] == 1
    assert body["pending_pages"] == 2
    assert body["job_state_label"] in {"正在处理", "等待处理"}
    assert len(body["files"]) == 1
    file_view = body["files"][0]
    assert file_view["file_name"] == "化验单.png"
    assert file_view["status_label"] == "正在处理"
    # 不暴露内部列名/运行日志。
    assert "ocr" not in "".join(body.keys())
    assert "job_id" in body


def test_evidence_progress_unknown_job_404(client) -> None:
    resp = client.get("/api/v2/jobs/missing/evidence-progress")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_sse_replays_page_progress_events_with_chinese_payload(build_app, client):
    from app.api.v2.jobs import _sse_stream

    sf = client.app.state.session_factory
    job_id = _create_job(sf)
    with sf() as session, session.begin():
        store = JobStore(session)
        store.append_event(
            store.make_event(
                job_id=job_id,
                event_type=JobEventType.PAGE_PROGRESS,
                progress_completed=2,
                progress_total=5,
                payload={"进度说明": "已处理第 2 页，共 5 页", "文件": "化验单.png"},
            )
        )

    service = client.app.state.job_service
    seen: list[tuple[int | None, str | None, dict | None]] = []
    for chunk in _sse_stream(
        service,
        job_id,
        after_seq=1,
        poll_interval=0.005,
        heartbeat_seconds=0.05,
    ):
        for seq, event, data in parse_sse_frames([chunk]):
            if event == "page_progress":
                seen.append((seq, event, data))
        if seen:
            break

    assert len(seen) == 1
    seq, event, data = seen[0]
    assert event == "page_progress"
    assert seq == 2
    assert data is not None
    assert data["payload"]["进度说明"] == "已处理第 2 页，共 5 页"


def test_evidence_progress_dedups_retry_runs(build_app, client):
    """自动/人工重试会产生新 OCR 运行：每个资料版本只投影最新权威运行，不重复累计。"""
    from datetime import timedelta

    sf = client.app.state.session_factory
    scope = _seed_scope(sf)
    job_id = _create_job(sf, scope)
    _seed_evidence(sf, scope, job_id)  # run-prog: 5 页，2 成功 1 失败
    # 追加同资料版本的重试运行（更新的 created_at / 更大的 run_id）。
    with sf() as session, session.begin():
        profile = OCRProfileRepository(session).get_or_create(
            TextOnlyOcrAdapter().profile(created_at=FIXED_UTC)
        )
        run2 = OCRRun(
            ocr_run_id="run-prog-retry",
            source_document_version_id="doc-prog",
            ocr_profile_id=profile.ocr_profile_id,
            ocr_profile_sha256=profile.profile_sha256,
            job_id=job_id,
            status=OcrRunStatus.SUCCEEDED,
            page_total=5,
            page_succeeded=5,
            page_failed=0,
            started_at=FIXED_UTC + timedelta(seconds=60),
            completed_at=FIXED_UTC + timedelta(seconds=90),
            created_at=FIXED_UTC + timedelta(seconds=60),
        )
        OcrRunRepository(session).create(run2)

    resp = client.get(f"/api/v2/jobs/{job_id}/evidence-progress")
    assert resp.status_code == 200
    body = resp.json()
    # 只投影最新运行：5/5 完成，而非 5+5 或两次运行叠加。
    assert body["total_pages"] == 5
    assert body["completed_pages"] == 5
    assert body["failed_pages"] == 0
    assert len(body["files"]) == 1
    assert body["files"][0]["status_label"] == "已完成"


def test_evidence_progress_txt_only_uses_all_page_progress(build_app, client):
    """TXT/native 无 OCR 运行：主进度仍按全部资料页显示完成。"""
    sf = client.app.state.session_factory
    scope = _seed_scope(sf)
    job_id = _create_job(sf, scope)  # 无任何 OCR 运行
    with sf() as session, session.begin():
        store = JobStore(session)
        store.append_event(
            store.make_event(
                job_id=job_id,
                event_type=JobEventType.PAGE_PROGRESS,
                progress_completed=1,
                progress_total=1,
                payload={"进度说明": "已直接读取 1 页"},
            )
        )

    resp = client.get(f"/api/v2/jobs/{job_id}/evidence-progress")
    assert resp.status_code == 200
    body = resp.json()
    assert body["files"] == []
    assert body["total_pages"] == 1
    assert body["completed_pages"] == 1
    assert "直接读取" in body["scope_note"]
    assert "图像识别" in body["scope_note"]


def test_cancel_queued_evidence_job_projects_snapshot_status(build_app, client) -> None:
    """通用 Job 取消也必须收敛尚未开始的证据候选快照。"""
    sf = client.app.state.session_factory
    scope = _seed_scope(sf)
    job_id = _create_job(sf, scope)
    _seed_evidence(sf, scope, job_id)

    response = client.post(f"/api/v2/jobs/{job_id}/cancel")
    assert response.status_code == 200
    assert response.json()["state"] == "cancelled"

    with sf() as session:
        assert (
            EvidenceSnapshotRepository(session).current_status("snap-prog")
            == SnapshotStatus.CANCELLED
        )
