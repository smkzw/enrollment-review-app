"""Slice 4.4 证据处理 / 校对 / 激活 / 被提及资料 API 合同测试（WP-44C）。

覆盖冻结 §7.1 请求/响应事实与稳定中文错误信封：

- 页接口并列 raw_text / effective_text / 所选校对 / 风险扫描与核对 / 定位精度与
  降级；校对层绝不命名为“原始识别”（§7.1、§2.2）；
- 校对 POST 必须带原识别哈希、原始范围、base 处理修订、预期审核节点修订号、
  幂等键；关键语义变化必须带显式确认载荷，缺确认 422；预期修订号不匹配 409 并
  保留提交值与服务端差异；同幂等键同请求回放、异请求冲突（§8.3、§7.1）；
- 处理修订 GET 返回 kind / base ID / 快照 ID / 清单 hashes / activatable / 逐门禁；
- 激活/回滚带预期修订号，返回事件 ID、旧/新指针对与新审核节点修订号；幂等回放
  同一事件；base 修订永不可激活（§8.4、§5.2/§5.3）；
- 被提及资料 create/patch/confirm/dismiss/resolve/delete 全部追加不可变修订，
  确定性候选不自动 confirmed；resolve/delete 不原地更新（§4.5、§8.5）；
- current 只来自审核节点成对活动指针；快照列表 ``is_current`` 不按状态/时间推断
  （§5.5、§8.4 反例 3/4）；
- 中文错误信封稳定区分 STALE_REVISION / REVIEW_PENDING / NON_COMPLETE_REVISION /
  IDEMPOTENCY_CONFLICT / SCOPE_MISMATCH / ROLLBACK_TARGET_INVALID 等。
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.api.v2.vocabulary import (
    correction_change_kind_label,
    locator_precision_label,
    ocr_risk_level_label,
    referenced_document_origin_label,
    referenced_document_status_label,
    revision_kind_label,
)
from app.domain.contracts.enums import (
    LocatorSourceLayer,
    OcrRiskReviewDecision,
    ProcessingRevisionStatus,
    SnapshotStatus,
    UploadMode,
)
from app.domain.contracts.evidence_processing import EvidenceProcessingRevision
from app.domain.publication import evidence_processing_manifest_hash
from app.services.evidence_locator_service import (
    EvidenceLocatorService,
    LocatorRequest,
)
from app.services.evidence_risk_service import EvidenceRiskScanService
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    CorrectionRepository,
    EvidenceProcessingCandidateRepository,
    OCRRiskReviewRepository,
    OCRRiskScanRepository,
)
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrPageRepository,
)
from app.storage.repositories import EpisodeRepository, persist_fixture
from app.workflow.runner import JobRunner
from tests.v2.storage.test_ocr_repositories import (
    FIXED_UTC,
    make_artifact,
    make_blob,
    make_ocr_page,
    make_profile,
    make_version,
    sha,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES
from tests.v2.storage.test_slice44_repositories import (
    RAW_TEXT,
    _candidate,
    _candidate_event,
    _closed_revision,
    _complete_revision,
    _correction,
    _flag,
    _locator,
    _scan,
    _seed_metadata,
    _seed_scan_and_review,
)

ERROR_KEYS = {"code", "title", "detail", "recovery_action", "correlation_id", "context"}
OCR_PAGE_ID = "op-1"
REV1 = "rev-1"
SNAP1 = "snap-1"
COMPLETE1 = "complete-1"


def _run_revision_job(client, job_id: str) -> None:
    """用新的 runner 实例推进持久任务，模拟 HTTP 进程返回后的后台恢复。"""
    runner = JobRunner(
        client.app.state.session_factory,
        client.app.state.job_executors,
        on_cancelled=client.app.state.job_cancelled_callback,
    )
    assert runner.run_job(job_id) is True


def _assert_envelope(body: dict, *, code: str, status: int) -> dict:
    assert set(body.keys()) == {"error"}
    error = body["error"]
    assert set(error.keys()) == ERROR_KEYS
    assert error["code"] == code
    return error


# ------------------------------------------------------------------ 播种


def _seed_scope(client) -> tuple[str, str, str]:
    fixture = FIXTURES[0]
    with client.app.state.session_factory() as session:
        persist_fixture(session, fixture)
        session.commit()
    return (
        fixture.project.project_id,
        fixture.subject.subject_id,
        fixture.review_episode.review_episode_id,
    )


def _seed_api_stack(client, *, with_native_text: bool = False) -> dict:
    """blob / 资料版本(单页) / 快照(processing) / Profile / 页产物 / OCR 页 / base 修订 rev-1。"""
    from app.domain.contracts.enums import PageArtifactStatus, SnapshotMemberOrigin
    from app.domain.contracts.evidence_ingestion import (
        EvidenceSnapshot,
        EvidenceSnapshotMember,
    )
    from app.domain.contracts.evidence_processing import (
        EvidenceProcessingRevisionPage,
    )
    from app.domain.publication import (
        evidence_snapshot_collection_hash,
    )
    from app.storage.evidence_repositories import (
        BlobRepository,
        EvidenceSnapshotRepository,
        SourceDocumentRepository,
    )
    from app.storage.ocr_repositories import (
        OCRProfileRepository,
        PageArtifactRepository,
    )

    project_id, subject_id, episode_id = _seed_scope(client)
    scope = (project_id, subject_id, episode_id)
    with client.app.state.session_factory() as session, session.begin():
        blob = make_blob(b"pdf-bytes")
        BlobRepository(session).get_or_create_by_sha256(blob)
        version = make_version(
            version_id="doc-1",
            logical_id="log-1",
            blob_sha=blob.sha256,
            scope=scope,
            page_count=1,
        )
        SourceDocumentRepository(session).create_version(version)
        snapshot = EvidenceSnapshot(
            evidence_snapshot_id=SNAP1,
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            upload_mode=UploadMode.FULL,
            prior_snapshot_id=None,
            comparison_snapshot_id=None,
            members=[
                EvidenceSnapshotMember(
                    member_id="m-1",
                    snapshot_id=SNAP1,
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
            SNAP1,
            event="worker_start",
            new_status=SnapshotStatus.PROCESSING,
            actor="tester",
            reason="start",
        )
        page_buffer = BytesIO()
        Image.new("RGB", (595, 842), "white").save(page_buffer, format="PNG")
        page_image = client.app.state.artifact_store.put(
            "page_image", page_buffer.getvalue()
        )
        profile = OCRProfileRepository(session).get_or_create(make_profile())
        native_text_sha256 = None
        if with_native_text:
            native_text_sha256 = client.app.state.artifact_store.put(
                "native_text", RAW_TEXT.encode("utf-8")
            ).sha256
        PageArtifactRepository(session).get_or_create(
            make_artifact(
                version_id="doc-1",
                page_input=page_image.sha256,
                page_image=page_image.sha256,
                native_text_sha256=native_text_sha256,
            )
        )
        OcrPageRepository(session).create(
            make_ocr_page(
                page_id=OCR_PAGE_ID,
                artifact_id="pa-1",
                raw_text=RAW_TEXT,
                profile_sha=profile.profile_sha256,
                page_input=page_image.sha256,
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
            ocr_page_id=OCR_PAGE_ID,
            status=PageArtifactStatus.SUCCEEDED,
        )
        manifest_hash = evidence_processing_manifest_hash(
            entries=[
                ("doc-1", 1, None, "pa-1", OCR_PAGE_ID, PageArtifactStatus.SUCCEEDED.value)
            ]
        )
        EvidenceProcessingRevisionRepository(session).create(
            EvidenceProcessingRevision(
                evidence_processing_revision_id=REV1,
                evidence_snapshot_id=SNAP1,
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=episode_id,
                manifest=[entry],
                manifest_sha256=manifest_hash,
                status=ProcessingRevisionStatus.READY,
                is_activatable=False,
                created_at=FIXED_UTC,
                created_by="tester",
            )
        )
        _seed_metadata(session, {})
    return {
        "project_id": project_id,
        "subject_id": subject_id,
        "episode_id": episode_id,
        "entry": entry,
        "manifest_hash": manifest_hash,
        "artifact_store": client.app.state.artifact_store,
    }


def _episode_revision(client, episode_id: str) -> int:
    with client.app.state.session_factory() as session:
        return EpisodeRepository(session).get(episode_id).revision


def _ready_snapshot(session, keys) -> None:
    EvidenceSnapshotRepository(session).transition_status(
        SNAP1,
        event="all_gates_passed",
        new_status=SnapshotStatus.READY,
        actor="tester",
        reason="就绪",
    )


def _make_candidate_ready(session, producer_id: str, revision_id: str) -> None:
    """把生产候选推进到 READY（补充 all_gates_passed 事件）。"""
    repo = EvidenceProcessingCandidateRepository(session)
    candidate = repo.get(producer_id)
    repo.append_event(
        _candidate_event(
            candidate.candidate_id,
            len(repo.get_events(candidate.candidate_id)) + 1,
            "processing",
            "all_gates_passed",
            "ready",
            complete_revision_id=revision_id,
        )
    )


def _seed_ready_complete(client, *, correction_ids=()) -> dict:
    """stack + READY 快照 + 完整修订 complete-1（元数据/扫描/核对）+ READY 候选。"""
    keys = _seed_api_stack(client)
    with client.app.state.session_factory() as session, session.begin():
        _ready_snapshot(session, keys)
        revision = _closed_revision(
            keys, session, correction_ids=list(correction_ids)
        )
        created = CompleteEvidenceProcessingRevisionRepository(session).create(revision)
        _make_candidate_ready(
            session, created.producer_candidate_id, created.evidence_processing_revision_id
        )
    return keys


def _seed_second_complete(client, keys, first, *, revision_id="complete-2"):
    """复用首份修订闭包（元数据/扫描/核对），仅新增校对链头，构建第二份完整修订。"""
    with client.app.state.session_factory() as session, session.begin():
        producer_id = f"producer-{revision_id}"
        producer_repo = EvidenceProcessingCandidateRepository(session)
        producer = _candidate(
            keys,
            candidate_id=producer_id,
            idempotency_key=f"key-{producer_id}",
            expected_revision=_episode_revision_from_session(
                session, keys["episode_id"]
            ),
            scanner_rule_version="rules/v1",
        )
        producer_repo.create(
            producer,
            _candidate_event(producer_id, 1, "staged", "worker_start", "processing"),
        )
        revision = _complete_revision(
            keys,
            session,
            evidence_processing_revision_id=revision_id,
            producer_candidate_id=producer_id,
            candidate_input_sha256=producer.candidate_input_sha256,
            metadata_revision_ids=list(first.metadata_revision_ids),
            risk_scan_ids=list(first.risk_scan_ids),
            risk_review_ids=list(first.risk_review_ids),
        )
        created = CompleteEvidenceProcessingRevisionRepository(session).create(revision)
        _make_candidate_ready(session, producer_id, created.evidence_processing_revision_id)


def _episode_revision_from_session(session, episode_id: str) -> int:
    return EpisodeRepository(session).get(episode_id).revision


# ---------------------------------------------------------------- 页读取


def test_ocr_page_read_raw_vs_effective_never_mixed(client) -> None:
    """页接口并列原文与校对层；校对后文本绝不叫“原始识别”。"""
    _seed_api_stack(client)
    body = client.get(f"/api/v2/ocr-pages/{OCR_PAGE_ID}").json()
    assert body["ocr_page_id"] == OCR_PAGE_ID
    assert body["raw_text"] == RAW_TEXT
    assert body["raw_text_sha256"] == sha(RAW_TEXT.encode("utf-8"))
    # 校对层与原文是不同的字段，且没有字段名把校对层伪装成原始识别。
    assert "raw_text" in body and "effective_text" in body
    assert body["raw_text"] != body["effective_text"]
    assert not any("原始" in key for key in body)
    # 未激活且未指定处理修订：无校对层。
    assert body["processing_revision_id"] is None
    assert body["effective_text"] is None
    assert body["is_current_revision"] is False


def test_ocr_page_effective_text_with_selected_correction(client) -> None:
    """指定完整处理修订时返回校对层 + 所选校对 ID + 风险扫描/核对。"""
    keys = _seed_api_stack(client)
    with client.app.state.session_factory() as session, session.begin():
        CorrectionRepository(session).create(_correction(keys))
        revision = _closed_revision(keys, session, correction_ids=["corr-1"])
        created = CompleteEvidenceProcessingRevisionRepository(session).create(revision)
        _make_candidate_ready(
            session, created.producer_candidate_id, created.evidence_processing_revision_id
        )
    body = client.get(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}",
        params={"processing_revision_id": COMPLETE1},
    ).json()
    assert body["processing_revision_id"] == COMPLETE1
    assert body["effective_text"] == "ALT 5.60 mmol/L 且 AST 3.5 mmol/L"
    assert body["effective_text_sha256"] == sha(
        "ALT 5.60 mmol/L 且 AST 3.5 mmol/L".encode()
    )
    assert body["is_current_revision"] is False  # 未激活
    assert [c["correction_id"] for c in body["selected_corrections"]] == ["corr-1"]
    assert body["selected_corrections"][0]["corrected_text"] == "5.60"
    assert body["selected_corrections"][0]["change_kind"] == "decimal"
    assert (
        body["selected_corrections"][0]["change_kind_label"]
        == correction_change_kind_label("decimal")
    )
    # 风险扫描 + 核对。
    assert len(body["risk_scans"]) == 1
    assert body["risk_scans"][0]["flags"][0]["level_label"] == ocr_risk_level_label(
        "blocking"
    )
    assert [r["decision"] for r in body["risk_reviews"]] == ["confirmed_as_read"]


def test_activated_native_locator_revision_keeps_ocr_page_readable(client) -> None:
    """真实原文定位进入完整闭包后，启用与页级有效文本投影必须使用同一原件存储。"""
    keys = _seed_api_stack(client, with_native_text=True)
    locator = EvidenceLocatorService(
        client.app.state.session_factory, client.app.state.artifact_store
    ).create_locator(
        LocatorRequest(
            page_artifact_id="pa-1",
            ocr_page_id=OCR_PAGE_ID,
            source_layer=LocatorSourceLayer.NATIVE_TEXT,
            source_text_sha256=sha(RAW_TEXT.encode("utf-8")),
            target_id="native-risk",
            target_text_start=4,
            target_text_end=7,
            excerpt="5.6",
        )
    )
    with client.app.state.session_factory() as session, session.begin():
        _ready_snapshot(session, keys)
        revision = _closed_revision(
            keys, session, locator_ids=[locator.locator_id]
        )
        created = CompleteEvidenceProcessingRevisionRepository(
            session, client.app.state.artifact_store
        ).create(revision)
        _make_candidate_ready(
            session,
            created.producer_candidate_id,
            created.evidence_processing_revision_id,
        )

    activated = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate",
        json={
            "expected_revision": _episode_revision(client, keys["episode_id"]),
            "idempotency_key": "activate-native-locator",
            "actor": "测试用户",
            "reason": "完成原件定位核对",
            "candidate_id": created.producer_candidate_id,
        },
    )
    assert activated.status_code == 201, activated.text

    page = client.get(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}",
        params={"processing_revision_id": COMPLETE1},
    )
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["is_current_revision"] is True
    assert body["effective_text"] == RAW_TEXT
    assert [item["locator_id"] for item in body["locators"]] == [
        locator.locator_id
    ]


def test_ocr_page_base_revision_is_readable_but_not_current(client) -> None:
    """base 修订用于启用前核对原文；可读不等于可激活。"""
    _seed_api_stack(client)
    resp = client.get(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}",
        params={"processing_revision_id": REV1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["processing_revision_id"] == REV1
    assert body["raw_text"] == RAW_TEXT
    assert body["effective_text"] is None
    assert body["selected_corrections"] == []
    assert body["is_current_revision"] is False


def test_ocr_page_missing_404(client) -> None:
    _seed_api_stack(client)
    resp = client.get("/api/v2/ocr-pages/does-not-exist")
    assert resp.status_code == 404
    _assert_envelope(resp.json(), code="NOT_FOUND", status=404)


def test_ocr_page_locator_precision_and_degradation(client) -> None:
    """定位降级是数据而非错误：返回诚实精度 + 降级原因。"""
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository

    keys = _seed_api_stack(client)
    with client.app.state.session_factory() as session, session.begin():
        EvidenceLocatorRepository(session).create(_locator(keys))
    body = client.get(f"/api/v2/ocr-pages/{OCR_PAGE_ID}").json()
    assert len(body["locators"]) == 1
    loc = body["locators"][0]
    assert loc["precision"] == "text_range"
    assert loc["precision_label"] == locator_precision_label("text_range")
    assert loc["degradation_reason"] == "text-only 路线无真实坐标"


# ---------------------------------------------------------------- 校对


def test_correction_create_and_replay(client) -> None:
    keys = _seed_api_stack(client)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "text_start": 4,
        "text_end": 7,
        "original_text": "5.6",
        "corrected_text": "5.6 mmol/L",
        "change_kind": "other_text",
        "reason": "补充单位说明",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-corr-1",
        "actor": "测试用户",
        "confirmation": {"actor": "复核人", "at": "2026-08-19T12:00:00Z"},
    }
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["created"] is True
    assert created["correction"]["change_kind"] == "other_text"
    assert created["correction"]["correction_id"]

    replay = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["created"] is False
    assert replay.json()["correction"]["correction_id"] == created["correction"][
        "correction_id"
    ]


def test_source_anchored_insertion_create_and_read_keeps_raw_ocr(client) -> None:
    keys = _seed_api_stack(client)
    expected = _episode_revision(client, keys["episode_id"])
    insert_at = len(RAW_TEXT)
    body = {
        "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "text_start": insert_at,
        "text_end": insert_at,
        "original_text": "",
        "corrected_text": " 漏识别原文",
        "change_kind": "other_text",
        "reason": "补入当前页末尾漏识别文字",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-insert-1",
        "actor": "测试用户",
    }
    response = client.post(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body
    )
    assert response.status_code == 201, response.text
    correction = response.json()["correction"]
    assert correction["text_start"] == correction["text_end"] == insert_at
    assert correction["original_text"] == ""
    assert correction["corrected_text"] == " 漏识别原文"

    page = client.get(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}",
        params={"processing_revision_id": REV1},
    ).json()
    assert page["raw_text"] == RAW_TEXT


def test_correction_blocking_kind_requires_confirmation(client) -> None:
    """关键语义变化（数值/小数点/单位/日期/极性/连接词）缺二次确认 -> 422。"""
    keys = _seed_api_stack(client)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "text_start": 4,
        "text_end": 7,
        "original_text": "5.6",
        "corrected_text": "5.60",
        "change_kind": "decimal",
        "reason": "补小数点",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-decimal",
        "actor": "测试用户",
    }
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body)
    assert resp.status_code == 422
    _assert_envelope(
        resp.json(), code="CORRECTION_CONFIRMATION_REQUIRED", status=422
    )


def test_source_anchored_key_insertion_requires_confirmation(client) -> None:
    keys = _seed_api_stack(client)
    expected = _episode_revision(client, keys["episode_id"])
    insert_at = len(RAW_TEXT)
    body = {
        "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "text_start": insert_at,
        "text_end": insert_at,
        "original_text": "",
        "corrected_text": " 2026-08-19",
        "change_kind": "date",
        "reason": "补入漏识别日期",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-insert-date",
        "actor": "测试用户",
    }
    response = client.post(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body
    )
    assert response.status_code == 422
    _assert_envelope(
        response.json(), code="CORRECTION_CONFIRMATION_REQUIRED", status=422
    )


def test_correction_blocking_with_confirmation_ok(client) -> None:
    keys = _seed_api_stack(client)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "text_start": 4,
        "text_end": 7,
        "original_text": "5.6",
        "corrected_text": "5.60",
        "change_kind": "decimal",
        "reason": "补小数点",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-decimal-conf",
        "actor": "测试用户",
        "confirmation": {"actor": "复核人", "at": "2026-08-19T12:00:00Z"},
    }
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body)
    assert resp.status_code == 201, resp.text
    assert resp.json()["correction"]["requires_confirmation"] is True
    assert resp.json()["correction"]["confirmation_actor"] == "复核人"


def test_correction_wrong_raw_hash_rejected(client) -> None:
    keys = _seed_api_stack(client)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "raw_text_sha256": "b" * 64,
        "text_start": 0,
        "text_end": 5,
        "original_text": "ALT 5",
        "corrected_text": "ALT 6",
        "change_kind": "other_text",
        "reason": "测试",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-hash",
    }
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body)
    assert resp.status_code == 422
    _assert_envelope(resp.json(), code="CORRECTION_RANGE_MISMATCH", status=422)


def test_correction_stale_revision_preserves_submitted_and_diff(client) -> None:
    """预期修订号不匹配 -> 409，context 保留提交值与服务端差异。"""
    keys = _seed_api_stack(client)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "text_start": 4,
        "text_end": 7,
        "original_text": "5.6",
        "corrected_text": "5.6 mmol/L",
        "change_kind": "other_text",
        "reason": "补充单位说明",
        "base_processing_revision_id": REV1,
        "expected_revision": expected + 5,  # 已过期
        "idempotency_key": "key-stale",
    }
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=body)
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="STALE_REVISION", status=409)
    ctx = error["context"]
    assert ctx["expected_revision"] == expected + 5
    assert ctx["current_revision"] == expected
    assert ctx["submitted"]["text_start"] == 4
    assert ctx["submitted"]["corrected_text"] == "5.6 mmol/L"
    assert ctx["field_diff"]["revision"]["current"] == expected
    assert ctx["field_diff"]["revision"]["submitted"] == expected + 5


def test_correction_same_key_different_request_conflicts(client) -> None:
    """同幂等键异请求 -> 409 IDEMPOTENCY_CONFLICT。"""
    keys = _seed_api_stack(client)
    expected = _episode_revision(client, keys["episode_id"])
    first = {
        "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
        "text_start": 4,
        "text_end": 7,
        "original_text": "5.6",
        "corrected_text": "5.6 mmol/L",
        "change_kind": "other_text",
        "reason": "补充单位说明",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-conflict",
        "confirmation": {"actor": "复核人", "at": "2026-08-19T12:00:00Z"},
    }
    assert (
        client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=first).status_code
        == 201
    )
    second = dict(first, corrected_text="5.60")
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections", json=second)
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="IDEMPOTENCY_CONFLICT", status=409)


# ---------------------------------------------------------------- 风险核对


def _seed_scan_and_review_ctx(client, keys):
    """在提交事务中播种 scan-1 + review rv-1，返回 scan_id。"""
    with client.app.state.session_factory() as session, session.begin():
        scan_id, _review_ids = _seed_scan_and_review(session, keys)
        return scan_id


def test_risk_review_create_and_replay(client) -> None:
    keys = _seed_api_stack(client)
    scan_id = _seed_scan_and_review_ctx(client, keys)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "risk_flag_id": f"{scan_id}:r1",
        "decision": "not_applicable",
        "reason": "该数值不适用",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-rv-1",
    }
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-reviews", json=body)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["created"] is True
    assert created["review"]["decision"] == "not_applicable"

    replay = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-reviews", json=body)
    assert replay.status_code == 200
    assert replay.json()["created"] is False
    assert replay.json()["review"]["review_id"] == created["review"]["review_id"]


def test_risk_review_stale_revision_409(client) -> None:
    keys = _seed_api_stack(client)
    scan_id = _seed_scan_and_review_ctx(client, keys)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "risk_flag_id": f"{scan_id}:r1",
        "decision": "confirmed_as_read",
        "reason": "已核对",
        "base_processing_revision_id": REV1,
        "expected_revision": expected + 3,
        "idempotency_key": "key-rv-stale",
    }
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-reviews", json=body)
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="STALE_REVISION", status=409)


# ---------------------------------------------------------------- 完整修订


def _seed_metadata_helper(client, keys) -> None:
    with client.app.state.session_factory() as session, session.begin():
        from app.storage.evidence_repositories import (
            SourceDocumentMetadataRevisionRepository,
        )

        if SourceDocumentMetadataRevisionRepository(session).head("doc-1") is None:
            _seed_metadata(session, keys)


def _seed_reviews_for_blocking(client, scan_id) -> None:
    from app.domain.contracts.evidence_locator import OCRRiskReview

    session_factory = client.app.state.session_factory
    with session_factory() as session:
        scan = OCRRiskScanRepository(session).get(scan_id)
        flags = list(scan.flags)
    with session_factory() as session, session.begin():
        repo = OCRRiskReviewRepository(session)
        for flag in flags:
            if flag.level.value != "blocking":
                continue
            repo.create(
                OCRRiskReview(
                    review_id=f"rv-api-{scan_id}-{flag.risk_id}",
                    risk_flag_id=f"{scan_id}:{flag.risk_id}",
                    decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
                    reason="已核对",
                    actor="tester",
                    base_processing_revision_id=REV1,
                    expected_revision=0,
                    created_at=FIXED_UTC,
                )
            )


def _seed_all_but_one_blocking_review(client, scan_id) -> str:
    """核对除一个阻断风险外的全部条目，返回留给 API 恢复动作的风险编号。"""
    from app.domain.contracts.evidence_locator import OCRRiskReview

    session_factory = client.app.state.session_factory
    with session_factory() as session:
        scan = OCRRiskScanRepository(session).get(scan_id)
        blocking = [flag for flag in scan.flags if flag.level.value == "blocking"]
    assert blocking
    remaining = blocking[0]
    with session_factory() as session, session.begin():
        repo = OCRRiskReviewRepository(session)
        for flag in blocking[1:]:
            repo.create(
                OCRRiskReview(
                    review_id=f"rv-api-partial-{scan_id}-{flag.risk_id}",
                    risk_flag_id=f"{scan_id}:{flag.risk_id}",
                    decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
                    reason="已核对",
                    actor="tester",
                    base_processing_revision_id=REV1,
                    expected_revision=0,
                    created_at=FIXED_UTC,
                )
            )
    return f"{scan_id}:{remaining.risk_id}"


def _seed_all_but_two_blocking_reviews(client, scan_id) -> list[str]:
    """核对除两个阻断风险外的条目，用于证明逐项保存不会反复重跑。"""
    from app.domain.contracts.evidence_locator import OCRRiskReview

    session_factory = client.app.state.session_factory
    with session_factory() as session:
        scan = OCRRiskScanRepository(session).get(scan_id)
        blocking = [flag for flag in scan.flags if flag.level.value == "blocking"]
    assert len(blocking) >= 2
    with session_factory() as session, session.begin():
        repo = OCRRiskReviewRepository(session)
        for flag in blocking[2:]:
            repo.create(
                OCRRiskReview(
                    review_id=f"rv-api-two-{scan_id}-{flag.risk_id}",
                    risk_flag_id=f"{scan_id}:{flag.risk_id}",
                    decision=OcrRiskReviewDecision.CONFIRMED_AS_READ,
                    reason="已核对",
                    actor="tester",
                    base_processing_revision_id=REV1,
                    expected_revision=0,
                    created_at=FIXED_UTC,
                )
            )
    return [f"{scan_id}:{flag.risk_id}" for flag in blocking[:2]]


def test_build_revision_ready_and_replay(client) -> None:
    """请求原子排队；新 runner 按冻结输入生成 READY 完整修订。"""
    keys = _seed_api_stack(client)
    _seed_metadata_helper(client, keys)
    scan = EvidenceRiskScanService(client.app.state.session_factory).scan_page(OCR_PAGE_ID)
    _seed_reviews_for_blocking(client, scan.scan_id)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "evidence_snapshot_id": SNAP1,
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-build-1",
        "actor": "测试用户",
    }
    resp = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["candidate_status"] == "staged"
    assert created["candidate_event_seq"] == 0
    assert created["complete_revision_id"] is None
    assert created["created"] is True
    assert created["revision"] is None
    assert client.app.state.job_service.get_job_state(created["job_id"]) == "queued"
    candidate_status = client.get(
        f"/api/v2/evidence-processing-candidates/{created['candidate_id']}"
    )
    assert candidate_status.status_code == 200
    assert candidate_status.json() == {
        "candidate_id": created["candidate_id"],
        "job_id": created["job_id"],
        "candidate_status": "staged",
        "candidate_status_label": "待处理",
        "candidate_event_seq": 0,
        "complete_revision_id": None,
    }
    with client.app.state.session_factory() as session:
        queued = EvidenceProcessingCandidateRepository(session).get(
            created["candidate_id"]
        )
        assert queued.status.value == "staged"
        assert EvidenceProcessingCandidateRepository(session).get_events(
            created["candidate_id"]
        ) == []

    _run_revision_job(client, created["job_id"])
    assert client.app.state.job_service.get_job_state(created["job_id"]) == "completed"
    completed_candidate = client.get(
        f"/api/v2/evidence-processing-candidates/{created['candidate_id']}"
    ).json()
    assert completed_candidate["candidate_status"] == "ready"
    assert completed_candidate["candidate_event_seq"] == 2
    assert completed_candidate["complete_revision_id"] is not None

    replay = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert replay.status_code == 200, replay.text
    completed = replay.json()
    assert completed["candidate_id"] == created["candidate_id"]
    assert completed["job_id"] == created["job_id"]
    assert completed["candidate_status"] == "ready"
    assert completed["candidate_event_seq"] == 2
    assert completed["complete_revision_id"] is not None
    revision = completed["revision"]
    assert revision["revision_kind"] == "complete"
    assert revision["revision_kind_label"] == revision_kind_label("complete")
    assert revision["base_processing_revision_id"] == REV1
    assert revision["is_activatable"] is True
    assert revision["manifest_sha256"]
    assert revision["completion_manifest_sha256"]
    assert revision["pages"] == [
        {
            "entry_id": "e1",
            "position": 1,
            "source_document_version_id": "doc-1",
            "page_number": 1,
            "original_frame": None,
            "page_artifact_id": "pa-1",
            "ocr_page_id": OCR_PAGE_ID,
            "status": "succeeded",
            "status_label": "页面已就绪",
            "failure_reason": None,
            "image_available": True,
            "page_width": 595.0,
            "page_height": 842.0,
        }
    ]
    assert {g["status"] for g in revision["gates"]} == {"passed"}
    assert revision["is_current"] is False  # 未激活

def test_build_revision_pending_review(client) -> None:
    """未核对阻断风险由后台发现，任务持久暂停且同命令回放给出继续核对。"""
    keys = _seed_api_stack(client)
    _seed_metadata_helper(client, keys)  # 有元数据但无核对/校对
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "evidence_snapshot_id": SNAP1,
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-build-pending",
        "actor": "测试用户",
    }
    resp = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert resp.status_code == 201
    created = resp.json()
    assert created["candidate_status"] == "staged"

    _run_revision_job(client, created["job_id"])
    assert client.app.state.job_service.get_job_state(created["job_id"]) == "waiting_user"
    with client.app.state.session_factory() as session:
        candidate = EvidenceProcessingCandidateRepository(session).get(
            created["candidate_id"]
        )
        assert candidate.status.value == "needs_attention"

    replay = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert replay.status_code == 409
    error = _assert_envelope(replay.json(), code="REVIEW_PENDING", status=409)
    assert error["context"]["candidate_status"] == "needs_attention"
    assert error["context"]["candidate_id"] == created["candidate_id"]


def test_waiting_revision_resumes_same_candidate_after_risk_review(client) -> None:
    """补充核对更新冻结清单，任务重新排队；后台取得租约后才再次处理中。"""
    keys = _seed_api_stack(client)
    _seed_metadata_helper(client, keys)
    scan = EvidenceRiskScanService(client.app.state.session_factory).scan_page(OCR_PAGE_ID)
    remaining_flag_id = _seed_all_but_one_blocking_review(client, scan.scan_id)
    expected = _episode_revision(client, keys["episode_id"])
    build_body = {
        "evidence_snapshot_id": SNAP1,
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-build-resume",
        "actor": "测试用户",
    }
    created = client.post(
        "/api/v2/evidence-processing-revisions/build", json=build_body
    ).json()
    _run_revision_job(client, created["job_id"])
    with client.app.state.session_factory() as session:
        repo = EvidenceProcessingCandidateRepository(session)
        events = repo.get_events(created["candidate_id"])
        assert repo.get(created["candidate_id"]).status.value == "needs_attention"

    review_body = {
        "risk_flag_id": remaining_flag_id,
        "decision": "confirmed_as_read",
        "reason": "已对照原件核对",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-review-resume",
        "target_candidate_id": created["candidate_id"],
        "expected_candidate_event_seq": len(events),
    }
    resumed_response = client.post(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-reviews", json=review_body
    )
    assert resumed_response.status_code == 201, resumed_response.text
    resumed = resumed_response.json()
    assert resumed["candidate_id"] == created["candidate_id"]
    assert resumed["job_id"] == created["job_id"]
    assert resumed["candidate_status"] == "staged"
    assert client.app.state.job_service.get_job_state(created["job_id"]) == "queued"

    _run_revision_job(client, created["job_id"])
    with client.app.state.session_factory() as session:
        repo = EvidenceProcessingCandidateRepository(session)
        candidate = repo.get(
            created["candidate_id"]
        )
        assert candidate.status.value == "ready", [
            (event.event_kind.value, event.reason)
            for event in repo.get_events(created["candidate_id"])
        ]
        assert candidate.complete_revision_id is not None
    assert client.app.state.job_service.get_job_state(created["job_id"]) == "completed"


def test_partial_risk_review_stays_waiting_without_rebuilding_candidate(client) -> None:
    keys = _seed_api_stack(client)
    _seed_metadata_helper(client, keys)
    scan = EvidenceRiskScanService(client.app.state.session_factory).scan_page(OCR_PAGE_ID)
    remaining = _seed_all_but_two_blocking_reviews(client, scan.scan_id)
    expected = _episode_revision(client, keys["episode_id"])
    created = client.post(
        "/api/v2/evidence-processing-revisions/build",
        json={
            "evidence_snapshot_id": SNAP1,
            "base_processing_revision_id": REV1,
            "expected_revision": expected,
            "idempotency_key": "key-build-partial-review",
            "actor": "测试用户",
        },
    ).json()
    _run_revision_job(client, created["job_id"])
    with client.app.state.session_factory() as session:
        repo = EvidenceProcessingCandidateRepository(session)
        event_count = len(repo.get_events(created["candidate_id"]))

    response = client.post(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-reviews",
        json={
            "risk_flag_id": remaining[0],
            "decision": "confirmed_as_read",
            "reason": "已对照原件核对",
            "base_processing_revision_id": REV1,
            "expected_revision": expected,
            "idempotency_key": "key-review-partial-no-rebuild",
            "target_candidate_id": created["candidate_id"],
            "expected_candidate_event_seq": event_count,
        },
    )
    assert response.status_code == 201, response.text
    partial = response.json()
    assert partial["candidate_status"] == "needs_attention"
    assert partial["candidate_event_seq"] == event_count
    assert partial["complete_revision_id"] is None
    assert client.app.state.job_service.get_job_state(created["job_id"]) == "waiting_user"
    with client.app.state.session_factory() as session:
        repo = EvidenceProcessingCandidateRepository(session)
        assert len(repo.get_events(created["candidate_id"])) == event_count

    second_response = client.post(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-reviews",
        json={
            "risk_flag_id": remaining[1],
            "decision": "confirmed_as_read",
            "reason": "已继续对照原件核对",
            "base_processing_revision_id": REV1,
            "expected_revision": expected,
            "idempotency_key": "key-review-second-same-candidate",
            "target_candidate_id": partial["candidate_id"],
            "expected_candidate_event_seq": partial["candidate_event_seq"],
        },
    )
    assert second_response.status_code == 201, second_response.text
    resumed = second_response.json()
    assert resumed["candidate_id"] == created["candidate_id"]
    assert resumed["candidate_status"] == "staged"
    assert resumed["candidate_event_seq"] == event_count + 1
    assert resumed["complete_revision_id"] is None
    assert client.app.state.job_service.get_job_state(created["job_id"]) == "queued"


def test_queued_revision_does_not_absorb_later_correction(client) -> None:
    """候选排队后新增旁路记录，不得漂移进已冻结的构建输入。"""
    keys = _seed_api_stack(client)
    _seed_metadata_helper(client, keys)
    scan = EvidenceRiskScanService(client.app.state.session_factory).scan_page(OCR_PAGE_ID)
    _seed_reviews_for_blocking(client, scan.scan_id)
    body = {
        "evidence_snapshot_id": SNAP1,
        "base_processing_revision_id": REV1,
        "expected_revision": _episode_revision(client, keys["episode_id"]),
        "idempotency_key": "key-build-frozen-sidecars",
    }
    created = client.post(
        "/api/v2/evidence-processing-revisions/build", json=body
    ).json()
    with client.app.state.session_factory() as session, session.begin():
        CorrectionRepository(session).create(
            _correction(keys, correction_id="corr-after-queue")
        )

    _run_revision_job(client, created["job_id"])
    with client.app.state.session_factory() as session:
        candidate = EvidenceProcessingCandidateRepository(session).get(
            created["candidate_id"]
        )
        events = EvidenceProcessingCandidateRepository(session).get_events(
            created["candidate_id"]
        )
        assert candidate.status.value == "ready", [
            (event.event_kind.value, event.reason) for event in events
        ]
        complete = CompleteEvidenceProcessingRevisionRepository(
            session, client.app.state.artifact_store
        )
        assert candidate.complete_revision_id is not None
        complete = complete.get(candidate.complete_revision_id)
        assert complete.correction_ids == []


def test_cancelled_queued_revision_keeps_current_pointers_unchanged(client) -> None:
    keys = _seed_api_stack(client)
    _seed_metadata_helper(client, keys)
    body = {
        "evidence_snapshot_id": SNAP1,
        "base_processing_revision_id": REV1,
        "expected_revision": _episode_revision(client, keys["episode_id"]),
        "idempotency_key": "key-build-cancel",
    }
    created = client.post(
        "/api/v2/evidence-processing-revisions/build", json=body
    ).json()
    before = client.app.state.evidence_api_read_service.episode_pointer(
        keys["episode_id"]
    )
    outcome = client.app.state.job_service.cancel(created["job_id"])
    assert outcome.state == "cancelled"
    with client.app.state.session_factory() as session:
        candidate = EvidenceProcessingCandidateRepository(session).get(
            created["candidate_id"]
        )
        assert candidate.status.value == "cancelled"
    after = client.app.state.evidence_api_read_service.episode_pointer(
        keys["episode_id"]
    )
    assert after == before


def test_correction_enqueue_failure_rolls_back_sidecar_candidate_job_and_identity(
    client, monkeypatch
) -> None:
    """任务创建失败时，校对及其构建链不得留下任何半成品记录。"""
    from sqlalchemy import func, select

    from app.services.job_service import JobService
    from app.storage.evidence_locator_models import (
        CorrectionRecordRecord,
        EvidenceProcessingCandidateRecord,
    )
    from app.storage.models import IdempotencyRecordRow, JobRecord

    keys = _seed_api_stack(client)
    expected = _episode_revision(client, keys["episode_id"])
    with client.app.state.session_factory() as session:
        before_counts = {
            "corrections": session.scalar(
                select(func.count()).select_from(CorrectionRecordRecord)
            ),
            "candidates": session.scalar(
                select(func.count()).select_from(EvidenceProcessingCandidateRecord)
            ),
            "jobs": session.scalar(select(func.count()).select_from(JobRecord)),
            "identities": session.scalar(
                select(func.count()).select_from(IdempotencyRecordRow)
            ),
        }

    def _fail_job_create(*_args, **_kwargs):
        raise RuntimeError("注入任务创建失败")

    monkeypatch.setattr(JobService, "create_job_in_session", _fail_job_create)
    import pytest

    with pytest.raises(RuntimeError, match="注入任务创建失败"):
        client.post(
            f"/api/v2/ocr-pages/{OCR_PAGE_ID}/corrections",
            json={
                "raw_text_sha256": sha(RAW_TEXT.encode("utf-8")),
                "text_start": 4,
                "text_end": 7,
                "original_text": "5.6",
                "corrected_text": "5.60",
                "change_kind": "other_text",
                "reason": "核对小数位",
                "base_processing_revision_id": REV1,
                "expected_revision": expected,
                "idempotency_key": "key-atomic-rollback",
                "confirmation": {
                    "actor": "复核人",
                    "at": "2026-08-19T12:00:00Z",
                },
            },
        )

    with client.app.state.session_factory() as session:
        assert session.scalar(
            select(func.count()).select_from(CorrectionRecordRecord)
        ) == before_counts["corrections"]
        assert (
            session.scalar(select(func.count()).select_from(EvidenceProcessingCandidateRecord))
            == before_counts["candidates"]
        )
        assert session.scalar(select(func.count()).select_from(JobRecord)) == before_counts["jobs"]
        assert session.scalar(
            select(func.count()).select_from(IdempotencyRecordRow)
        ) == before_counts["identities"]


def test_build_revision_stale_409(client) -> None:
    keys = _seed_api_stack(client)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "evidence_snapshot_id": SNAP1,
        "base_processing_revision_id": REV1,
        "expected_revision": expected + 2,
        "idempotency_key": "key-build-stale",
    }
    resp = client.post("/api/v2/evidence-processing-revisions/build", json=body)
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="STALE_REVISION", status=409)


def test_revision_get_base_and_complete(client) -> None:
    _seed_ready_complete(client)
    # base 修订：kind=base，不可激活，逐门禁为不适用。
    base = client.get(f"/api/v2/evidence-processing-revisions/{REV1}").json()
    assert base["revision_kind"] == "base"
    assert base["revision_kind_label"] == revision_kind_label("base")
    assert base["is_activatable"] is False
    assert base["base_processing_revision_id"] is None
    assert base["risk_flag_count"] == 1
    assert base["pending_risk_flag_count"] == 0
    assert {g["status"] for g in base["gates"]} == {"not_applicable", "passed"}
    # complete 修订：kind=complete，可激活，逐门禁通过。
    complete = client.get(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}"
    ).json()
    assert complete["revision_kind"] == "complete"
    assert complete["is_activatable"] is True
    assert complete["base_processing_revision_id"] == REV1
    assert complete["evidence_snapshot_id"] == SNAP1
    assert complete["risk_flag_count"] == 1
    assert complete["pending_risk_flag_count"] == 0
    assert {g["status"] for g in complete["gates"]} == {"passed"}


def test_revision_get_missing_404(client) -> None:
    _seed_api_stack(client)
    resp = client.get("/api/v2/evidence-processing-revisions/does-not-exist")
    assert resp.status_code == 404
    _assert_envelope(resp.json(), code="NOT_FOUND", status=404)


def test_revision_page_image_returns_frozen_png_and_dimensions(client) -> None:
    """页图只按处理修订冻结清单读取，并返回不可变缓存与固有尺寸。"""
    _seed_api_stack(client)
    response = client.get(
        f"/api/v2/evidence-processing-revisions/{REV1}/pages/e1/image"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert response.headers["x-page-width"] == "595.0"
    assert response.headers["x-page-height"] == "842.0"
    assert response.headers["etag"]
    with Image.open(BytesIO(response.content)) as image:
        assert image.size == (595, 842)


def test_revision_page_image_rejects_entry_outside_frozen_manifest(client) -> None:
    _seed_api_stack(client)
    response = client.get(
        f"/api/v2/evidence-processing-revisions/{REV1}/pages/not-in-revision/image"
    )
    assert response.status_code == 404
    _assert_envelope(response.json(), code="NOT_FOUND", status=404)


# ---------------------------------------------------------------- 激活 / 回滚


def _activate_body(client, keys, *, expected_revision=None, idempotency_key=None, **overrides):
    base = {
        "expected_revision": expected_revision or _episode_revision(
            client, keys["episode_id"]
        ),
        "idempotency_key": idempotency_key or "key-act-1",
        "actor": "测试用户",
        "reason": "发布资料版本",
    }
    base.update(overrides)
    return base


def test_activate_sets_pointers_and_current_projection(client) -> None:
    """激活返回事件/旧新指针对/新修订号；快照列表 is_current 只来自指针。"""
    keys = _seed_ready_complete(client)
    episode_id = keys["episode_id"]
    expected = _episode_revision(client, episode_id)

    # 激活前：快照列表 is_current=False（无指针，即使快照 READY）。
    listed = client.get(
        f"/api/v2/subjects/{keys['subject_id']}/evidence-snapshots",
        params={"review_episode_id": episode_id},
    ).json()
    assert listed["active_evidence_snapshot_id"] is None
    assert listed["items"][0]["is_current"] is False
    persisted_candidate = listed["items"][0]["latest_processing_candidate"]
    assert persisted_candidate["candidate_id"] == "producer-complete-1"
    assert persisted_candidate["job_id"] is None
    assert persisted_candidate["candidate_status"] == "ready"
    assert persisted_candidate["complete_revision_id"] == COMPLETE1

    body = _activate_body(client, keys, expected_revision=expected)
    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body
    )
    assert resp.status_code == 201, resp.text
    event = resp.json()
    assert event["event_kind"] == "activate"
    assert event["from_snapshot_id"] is None
    assert event["to_snapshot_id"] == SNAP1
    assert event["to_revision_id"] == COMPLETE1
    assert event["resulting_episode_revision"] == expected + 1
    assert event["snapshot_status_transitioned"] is True

    # 审核节点 DTO 暴露两个活动 ID。
    episode = client.get(f"/api/v2/subjects/{keys['subject_id']}/review-episodes").json()[
        "items"
    ][0]
    assert episode["active_evidence_snapshot_id"] == SNAP1
    assert episode["active_evidence_processing_revision_id"] == COMPLETE1

    # 快照列表 is_current 只来自指针。
    listed = client.get(
        f"/api/v2/subjects/{keys['subject_id']}/evidence-snapshots",
        params={"review_episode_id": episode_id},
    ).json()
    assert listed["active_evidence_snapshot_id"] == SNAP1
    assert listed["active_evidence_processing_revision_id"] == COMPLETE1
    assert listed["items"][0]["is_current"] is True

    # 处理修订 is_current。
    revision = client.get(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}"
    ).json()
    assert revision["is_current"] is True


def test_activate_idempotent_replay(client) -> None:
    """同一命令幂等回放返回同一事件，不重复激活。"""
    keys = _seed_ready_complete(client)
    body = _activate_body(client, keys)
    first = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body
    )
    assert first.status_code == 201
    replay = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["event_id"] == first.json()["event_id"]
    # 只产生一条激活事件。
    with client.app.state.session_factory() as session:
        from app.storage.evidence_locator_repositories import (
            EvidenceActivationEventRepository,
        )
        assert len(
            EvidenceActivationEventRepository(session).list_by_episode(
                keys["episode_id"]
            )
        ) == 1


def test_activate_base_revision_rejected(client) -> None:
    """base 修订永不可激活 -> 409 NON_COMPLETE_REVISION。"""
    keys = _seed_api_stack(client)
    body = _activate_body(client, keys)
    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{REV1}/activate", json=body
    )
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="NON_COMPLETE_REVISION", status=409)


def test_activate_stale_expected_409(client) -> None:
    """预期修订号过期但命令未执行过 -> 409 保留提交值 + 服务端差异。"""
    keys = _seed_ready_complete(client)
    expected = _episode_revision(client, keys["episode_id"])
    body = _activate_body(client, keys, expected_revision=expected + 7)
    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/activate", json=body
    )
    assert resp.status_code == 409
    error = _assert_envelope(resp.json(), code="STALE_REVISION", status=409)
    ctx = error["context"]
    assert ctx["current_revision"] == expected
    assert ctx["submitted"]["expected_revision"] == expected + 7


def test_rollback_to_historical_pair(client) -> None:
    """回滚追加 rollback 事件并切换到历史指针对。"""
    keys = _seed_ready_complete(client)
    session_factory = client.app.state.session_factory
    # 激活 complete-1。
    activate(client, keys, COMPLETE1, "key-act-1")
    # 构建并激活 complete-2。
    with session_factory() as session, session.begin():
        first = CompleteEvidenceProcessingRevisionRepository(session).get(COMPLETE1)
    _seed_second_complete(client, keys, first)
    activate(client, keys, "complete-2", "key-act-2")
    expected = _episode_revision(client, keys["episode_id"])

    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/rollback",
        json={
            "expected_revision": expected,
            "idempotency_key": "key-rollback-1",
            "actor": "测试用户",
            "reason": "回滚到历史版本",
        },
    )
    assert resp.status_code == 201, resp.text
    event = resp.json()
    assert event["event_kind"] == "rollback"
    assert event["from_snapshot_id"] == SNAP1
    assert event["from_revision_id"] == "complete-2"
    assert event["to_snapshot_id"] == SNAP1
    assert event["to_revision_id"] == COMPLETE1
    assert event["resulting_episode_revision"] == expected + 1

    episode = client.get(f"/api/v2/subjects/{keys['subject_id']}/review-episodes").json()[
        "items"
    ][0]
    assert episode["active_evidence_processing_revision_id"] == COMPLETE1


def test_rollback_current_or_never_activated_409(client) -> None:
    """回滚到当前版本 -> 409 ROLLBACK_TARGET_INVALID。"""
    keys = _seed_ready_complete(client)
    activate(client, keys, COMPLETE1, "key-act-rollback")
    expected = _episode_revision(client, keys["episode_id"])
    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{COMPLETE1}/rollback",
        json={"expected_revision": expected, "idempotency_key": "key-rb-current",
              "actor": "u", "reason": "回滚当前"},
    )
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="ROLLBACK_TARGET_INVALID", status=409)


def activate(client, keys, revision_id: str, key: str | None = None) -> None:
    body = _activate_body(
        client, keys, idempotency_key=key or f"key-{revision_id}"
    )
    resp = client.post(
        f"/api/v2/evidence-processing-revisions/{revision_id}/activate", json=body
    )
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------- 被提及资料


def test_referenced_document_full_lifecycle_append_only(client) -> None:
    """create -> confirm -> revise -> dismiss -> resolve/delete 全部追加修订。"""
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository

    keys = _seed_ready_complete(client)
    activate(client, keys, COMPLETE1, "key-refdoc-current-pair")
    subject_id = keys["subject_id"]
    episode_id = keys["episode_id"]
    episode_rev = _episode_revision(client, episode_id)
    with client.app.state.session_factory() as session, session.begin():
        EvidenceLocatorRepository(session).create(_locator(keys))

    # 登记（手工，proposed）：携带审核节点预期修订号 + 幂等键。
    resp = client.post(
        f"/api/v2/subjects/{subject_id}/referenced-documents",
        json={
            "review_episode_id": episode_id,
            "expected_revision": episode_rev,
            "idempotency_key": "key-refdoc-create-1",
            "description": "既往心电图",
            "document_type": "lab",
            "source_party": "外院",
            "actor": "测试用户",
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    ref_id = created["referenced_document_id"]
    assert created["status"] == "proposed"
    assert created["status_label"] == referenced_document_status_label("proposed")
    assert created["origin"] == "manual"
    assert created["origin_label"] == referenced_document_origin_label("manual")
    assert created["resolution"] is None
    assert created["revision"] == 1

    # 确定性候选绝不自动 confirmed。
    det = client.post(
        f"/api/v2/subjects/{subject_id}/referenced-documents",
        json={
            "review_episode_id": episode_id,
            "expected_revision": episode_rev,
            "idempotency_key": "key-refdoc-create-2",
            "description": "检验报告",
            "origin": "deterministic_candidate",
            "pattern_version": "pattern/v1",
            "actor": "测试用户",
        },
    ).json()
    assert det["status"] == "proposed"
    assert det["origin"] == "deterministic_candidate"

    # 确认：必须可回放触发定位；expected_revision = 登记链头 revision(1)。
    confirmed = client.post(
        f"/api/v2/referenced-documents/{ref_id}/confirm",
        json={
            "expected_revision": 1,
            "idempotency_key": "key-refdoc-confirm-1",
            "trigger_locator_id": "loc-1",
            "reason": "原文明确提及",
            "actor": "u",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["revision"] == 2
    assert confirmed.json()["trigger_locator_id"] == "loc-1"

    # 确认缺触发定位 -> 404（触发定位不存在）。
    bad = client.post(
        f"/api/v2/referenced-documents/{ref_id}/confirm",
        json={
            "expected_revision": 2,
            "idempotency_key": "key-refdoc-confirm-bad",
            "trigger_locator_id": "loc-missing",
            "reason": "x",
            "actor": "u",
        },
    )
    assert bad.status_code == 404  # 触发定位不存在

    # 修改：追加新修订，保留状态与触发定位；expected_revision = 当前链头(2)。
    revised = client.patch(
        f"/api/v2/referenced-documents/{ref_id}",
        json={
            "expected_revision": 2,
            "idempotency_key": "key-refdoc-revise-1",
            "description": "既往心电图报告",
            "document_type": "report",
            "source_party": "外院",
            "reason": "补全类型",
            "actor": "u",
        },
    )
    assert revised.status_code == 200
    assert revised.json()["description"] == "既往心电图报告"
    assert revised.json()["status"] == "confirmed"
    assert revised.json()["revision"] == 3

    # 解除：追加 dismissed 修订，历史仍在；expected_revision = 当前链头(3)。
    dismissed = client.post(
        f"/api/v2/referenced-documents/{ref_id}/dismiss",
        json={
            "expected_revision": 3,
            "idempotency_key": "key-refdoc-dismiss-1",
            "reason": "经核实非必要",
            "actor": "u",
        },
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"
    assert dismissed.json()["revision"] == 4

    # 重新确认后可关联已上传文件（provided 满足修订）。
    client.post(
        f"/api/v2/referenced-documents/{ref_id}/confirm",
        json={
            "expected_revision": 4,
            "idempotency_key": "key-refdoc-confirm-2",
            "trigger_locator_id": "loc-1",
            "reason": "再次确认",
            "actor": "u",
        },
    )
    resolved = client.post(
        f"/api/v2/referenced-documents/{ref_id}/resolve",
        json={
            "expected_revision": 0,  # 尚无满足修订链头
            "idempotency_key": "key-refdoc-resolve-1",
            "status": "provided",
            "source_document_version_id": "doc-1",
            "actor": "u",
        },
    )
    assert resolved.status_code == 201
    assert resolved.json()["status"] == "provided"
    assert resolved.json()["source_document_version_id"] == "doc-1"

    # 解除关联：追加 unresolved，不删除旧满足关系。
    unres = client.delete(
        f"/api/v2/referenced-documents/{ref_id}/resolution",
        params={
            "expected_revision": 1,
            "idempotency_key": "key-refdoc-unresolve-1",
        },
    )
    assert unres.status_code == 200
    assert unres.json()["status"] == "unresolved"
    assert unres.json()["source_document_version_id"] is None

    # 列表：当前链头 + 当前满足状态。
    listed = client.get(
        f"/api/v2/subjects/{subject_id}/referenced-documents",
        params={"review_episode_id": episode_id},
    ).json()
    assert listed["subject_id"] == subject_id
    by_id = {item["referenced_document_id"]: item for item in listed["items"]}
    assert ref_id in by_id
    assert by_id[ref_id]["status"] == "confirmed"  # dismiss 后被再次确认
    assert by_id[ref_id]["resolution"]["status"] == "unresolved"


def test_referenced_document_list_cross_subject_404(client) -> None:
    keys = _seed_api_stack(client)
    resp = client.get(
        "/api/v2/subjects/no-such/referenced-documents",
        params={"review_episode_id": keys["episode_id"]},
    )
    assert resp.status_code == 404
    _assert_envelope(resp.json(), code="NOT_FOUND", status=404)


def test_referenced_document_resolve_unbound_rejected(client) -> None:
    """provided 必须绑定快照成员资料版本；缺失 -> 404。"""
    keys = _seed_api_stack(client)
    subject_id = keys["subject_id"]
    episode_id = keys["episode_id"]
    episode_rev = _episode_revision(client, episode_id)
    created = client.post(
        f"/api/v2/subjects/{subject_id}/referenced-documents",
        json={
            "review_episode_id": episode_id,
            "expected_revision": episode_rev,
            "idempotency_key": "key-refdoc-create-3",
            "description": "检验报告",
        },
    ).json()
    ref_id = created["referenced_document_id"]
    resp = client.post(
        f"/api/v2/referenced-documents/{ref_id}/resolve",
        json={
            "expected_revision": 0,
            "idempotency_key": "key-refdoc-resolve-bad",
            "status": "provided",
            "source_document_version_id": "no-such-doc",
        },
    )
    assert resp.status_code == 404
    _assert_envelope(resp.json(), code="NOT_FOUND", status=404)


# ---------------------------------------------------------------- 页级原子风险核对


def _seed_two_flag_unreviewed_scan(client, keys) -> str:
    """播种 scan-1（blocking r1 + informational r2），无既有核对，返回 scan_id。"""
    from app.storage.evidence_locator_repositories import OCRRiskScanRepository

    with client.app.state.session_factory() as session, session.begin():
        scan, _created = OCRRiskScanRepository(session).get_or_create(
            _scan(
                keys,
                flags=[
                    _flag(risk_id="r1", kind="numeric_value", level="blocking"),
                    _flag(
                        risk_id="r2",
                        kind="unit",
                        level="informational",
                        text="mmol/L",
                        start=8,
                        end=14,
                    ),
                ],
            )
        )
        return scan.scan_id


def test_page_risk_review_create_and_replay(client) -> None:
    keys = _seed_api_stack(client)
    scan_id = _seed_two_flag_unreviewed_scan(client, keys)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "scan_id": scan_id,
        "decision": "confirmed_as_read",
        "reason": "对照原件后本页一次确认",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-prv-1",
    }
    resp = client.post(f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-page-reviews", json=body)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["created"] is True
    assert created["page_review"]["covered_flag_ids"] == ["scan-1:r1", "scan-1:r2"]
    assert {r["risk_flag_id"] for r in created["reviews"]} == {
        "scan-1:r1",
        "scan-1:r2",
    }

    replay = client.post(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-page-reviews", json=body
    )
    assert replay.status_code == 200
    assert replay.json()["created"] is False
    assert (
        replay.json()["page_review"]["page_review_id"]
        == created["page_review"]["page_review_id"]
    )


def test_page_risk_review_no_pending_422(client) -> None:
    keys = _seed_api_stack(client)
    scan_id = _seed_two_flag_unreviewed_scan(client, keys)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "scan_id": scan_id,
        "decision": "confirmed_as_read",
        "reason": "整页确认",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-prv-1",
    }
    assert (
        client.post(
            f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-page-reviews", json=body
        ).status_code
        == 201
    )
    resp = client.post(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-page-reviews",
        json={**body, "idempotency_key": "key-prv-2"},
    )
    assert resp.status_code == 422


def test_page_risk_review_same_key_different_request_409(client) -> None:
    keys = _seed_api_stack(client)
    scan_id = _seed_two_flag_unreviewed_scan(client, keys)
    expected = _episode_revision(client, keys["episode_id"])
    body = {
        "scan_id": scan_id,
        "decision": "confirmed_as_read",
        "reason": "整页确认",
        "base_processing_revision_id": REV1,
        "expected_revision": expected,
        "idempotency_key": "key-prv-conflict",
    }
    assert (
        client.post(
            f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-page-reviews", json=body
        ).status_code
        == 201
    )
    conflict = client.post(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-page-reviews",
        json={**body, "decision": "not_applicable"},
    )
    assert conflict.status_code == 409
    _assert_envelope(conflict.json(), code="IDEMPOTENCY_CONFLICT", status=409)


def test_page_risk_review_stale_revision_409(client) -> None:
    keys = _seed_api_stack(client)
    scan_id = _seed_two_flag_unreviewed_scan(client, keys)
    expected = _episode_revision(client, keys["episode_id"])
    resp = client.post(
        f"/api/v2/ocr-pages/{OCR_PAGE_ID}/risk-page-reviews",
        json={
            "scan_id": scan_id,
            "decision": "confirmed_as_read",
            "reason": "整页确认",
            "base_processing_revision_id": REV1,
            "expected_revision": expected + 3,
            "idempotency_key": "key-prv-stale",
        },
    )
    assert resp.status_code == 409
    _assert_envelope(resp.json(), code="STALE_REVISION", status=409)
