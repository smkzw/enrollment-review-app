"""V2 证据上传预览/确认/快照 API 合同测试（Slice 4.2，worker_02）。

覆盖设计书 §5.2/§5.3 与 prd.md 验收：

- 正式 6 条路径（不含自创别名；OpenAPI 断言见 ``test_evidence_openapi.py``）；
- 上传预览（multipart + 显式 upload_mode/base_revision）与中文逐文件类别/原因/下一步；
- 作用域派生与重验：跨项目/跨受试者/跨审核节点一律 404；全局 GET/DELETE/commit
  从记录推导作用域，不信任客户端摘要或文件名；
- 取消幂等且只清理预览自有暂存；清理失败返回 ``PREVIEW_CLEANUP_FAILED`` 中文信封，
  预览保持“正在取消”、commit 被拒，重试成功后“已取消”且目录消失；
- 确认三标志互斥可解释：新建 ``created=True, replayed=False, duplicate=False``
  （201）；同幂等键回放 ``replayed=True`` 且保留原 duplicate 事实（200）；跨预览
  同集合 ``duplicate=True, replayed=False``（200）；
- 同名异内容必须显式处置（新版本/并列保留），缺失处置 422；
- 不支持格式 422；暂存文件漂移/缺失 409 且全有或全无回滚；
- 快照列表/详情与中文状态/来源标签；跨对象列表 404；
- 中文错误信封结构一致，不泄露内部哈希/枚举/路径。

任何用例都不触发 OCR。
"""
from __future__ import annotations

import shutil

from sqlalchemy import func, select, text

from app.api.v2.vocabulary import (
    item_status_label,
    preview_status_label,
    snapshot_member_origin_label,
    snapshot_status_label,
    upload_mode_label,
)
from app.domain.contracts.enums import SnapshotStatus
from app.domain.contracts.review import Project, ReviewEpisode, Subject
from app.storage.codecs import encode_contract
from app.storage.evidence_models import EvidenceSnapshotV2Record
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.repositories import (
    EpisodeRepository,
    ProjectRepository,
    SubjectRepository,
    persist_fixture,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

PDF_HEAD = b"%PDF-1.7\n"

ERROR_KEYS = {"code", "title", "detail", "recovery_action", "correlation_id", "context"}

PREVIEWS_BASE = "/api/v2/evidence-upload-previews"


def pdf(content: bytes, name: str = "report.pdf"):
    return ("files", (name, PDF_HEAD + content, "application/pdf"))


def _seed(client) -> tuple[str, str, str]:
    """在已启动的应用库中播种一份 Phase 3 fixture 作为作用域基座。"""
    factory = client.app.state.session_factory
    with factory() as session:
        persist_fixture(session, FIXTURES[0])
        session.commit()
        fixture = FIXTURES[0]
        return (
            fixture.project.project_id,
            fixture.subject.subject_id,
            fixture.review_episode.review_episode_id,
        )


def _seed_cross_project(client) -> tuple[str, str, str]:
    """创建独立项目/受试者/审核节点（复用已播种协议与规则集），用于跨项目测试。"""
    fixture = FIXTURES[0]
    with client.app.state.session_factory() as session, session.begin():
        project = Project(
            project_id="project-cross-p2",
            project_code="CROSS-P2",
            project_name="跨项目二",
            study_phase=fixture.project.study_phase,
            protocol_version=fixture.project.protocol_version,
            rule_set_id=fixture.project.rule_set_id,
        )
        ProjectRepository(session).save(
            project, rule_set_revision=fixture.rule_set.revision
        )
        subject = Subject(
            subject_id="subject-cross-p2",
            subject_code="S-CROSS-P2",
            project_id=project.project_id,
        )
        SubjectRepository(session).save(subject)
        episode = ReviewEpisode(
            review_episode_id="episode-cross-p2",
            subject_id=subject.subject_id,
            project_id=project.project_id,
            rule_set_id=fixture.review_episode.rule_set_id,
            study_phase=fixture.review_episode.study_phase,
            stage=fixture.review_episode.stage,
            protocol_version_id=fixture.review_episode.protocol_version_id,
            rule_set_revision=fixture.review_episode.rule_set_revision,
            evidence_snapshot_id=fixture.review_episode.evidence_snapshot_id,
            anchor_dates=fixture.review_episode.anchor_dates,
            due_at=fixture.review_episode.due_at,
        )
        EpisodeRepository(session).save(episode)
        return project.project_id, subject.subject_id, episode.review_episode_id


def _episode_revision(client, episode_id: str) -> int:
    with client.app.state.session_factory() as session:
        return EpisodeRepository(session).get(episode_id).revision


def _upload(
    client,
    subject_id: str,
    episode_id: str,
    files,
    *,
    mode: str = "full",
    base_revision: int | None = None,
    actor: str = "测试用户",
):
    if base_revision is None:
        base_revision = _episode_revision(client, episode_id)
    data = {
        "review_episode_id": episode_id,
        "upload_mode": mode,
        "base_revision": base_revision,
        "actor": actor,
    }
    return client.post(
        f"/api/v2/subjects/{subject_id}/evidence-upload-previews",
        data=data,
        files=files,
    )


def _commit(
    client,
    preview: dict,
    key: str,
    *,
    resolutions: dict[str, str] | None = None,
    base_revision: int | None = None,
    preview_sha256: str | None = None,
    upload_mode: str | None = None,
    actor: str = "测试用户",
):
    body = {
        "preview_sha256": preview_sha256 or preview["preview_sha256"],
        "upload_mode": upload_mode or preview["upload_mode"],
        "base_revision": (
            base_revision
            if base_revision is not None
            else preview["base_revision"]
        ),
        "idempotency_key": key,
        "actor": actor,
        "resolutions": resolutions or {},
    }
    return client.post(
        f"{PREVIEWS_BASE}/{preview['preview_id']}/commit", json=body
    )


def _activate(client, snapshot_id: str) -> None:
    """测试脚手架：模拟 Slice 4.4 激活后的状态（快照 ACTIVE + 审核节点活动指针对）。

    上传/提交只消费审核节点活动指针；因此除标记快照 ACTIVE 外，还要以最小 ORM 行
    建立 base/complete 修订对满足外键与形态 CHECK，并写入审核节点成对指针。
    """
    from datetime import UTC, datetime

    from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision
    from app.domain.contracts.evidence_processing import EvidenceProcessingRevision
    from app.domain.publication import evidence_processing_manifest_hash
    from app.storage.models import ReviewEpisodeRecord
    from app.storage.ocr_models import EvidenceProcessingRevisionRecord

    fixed = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)
    with client.app.state.session_factory() as session, session.begin():
        repo = EvidenceSnapshotRepository(session)
        contract = repo.get(snapshot_id)
        activated = contract.model_copy(update={"status": SnapshotStatus.ACTIVE})
        payload_json, payload_sha256 = encode_contract(activated)
        row = session.get(EvidenceSnapshotV2Record, snapshot_id)
        row.status = SnapshotStatus.ACTIVE.value
        row.payload_json = payload_json
        row.payload_sha256 = payload_sha256

        base_id = f"base-{snapshot_id}"
        complete_id = f"complete-{snapshot_id}"
        empty_manifest = evidence_processing_manifest_hash(entries=[])
        if session.get(EvidenceProcessingRevisionRecord, complete_id) is None:
            from app.storage.codecs import to_utc_naive

            base_contract = EvidenceProcessingRevision(
                evidence_processing_revision_id=base_id,
                evidence_snapshot_id=snapshot_id,
                project_id=contract.project_id,
                subject_id=contract.subject_id,
                review_episode_id=contract.review_episode_id,
                manifest=[], manifest_sha256=empty_manifest,
                created_at=fixed, created_by="scaffold",
            )
            bj, bsh = encode_contract(base_contract)
            session.add(
                EvidenceProcessingRevisionRecord(
                    evidence_processing_revision_id=base_id,
                    evidence_snapshot_id=snapshot_id,
                    project_id=contract.project_id,
                    subject_id=contract.subject_id,
                    review_episode_id=contract.review_episode_id,
                    manifest_sha256=empty_manifest, status="ready",
                    is_activatable=False, revision_kind="base",
                    created_by="scaffold", created_at=to_utc_naive(fixed),
                    payload_json=bj, payload_sha256=bsh,
                )
            )
            complete_contract = CompleteEvidenceProcessingRevision(
                evidence_processing_revision_id=complete_id,
                evidence_snapshot_id=snapshot_id,
                project_id=contract.project_id,
                subject_id=contract.subject_id,
                review_episode_id=contract.review_episode_id,
                base_processing_revision_id=base_id,
                producer_candidate_id=f"scaffold-producer-{snapshot_id}",
                candidate_input_sha256="f" * 64,
                manifest=[], manifest_sha256=empty_manifest,
                completion_manifest_sha256="0" * 64,
                created_at=fixed, created_by="scaffold",
            )
            cj, csh = encode_contract(complete_contract)
            session.add(
                EvidenceProcessingRevisionRecord(
                    evidence_processing_revision_id=complete_id,
                    evidence_snapshot_id=snapshot_id,
                    project_id=contract.project_id,
                    subject_id=contract.subject_id,
                    review_episode_id=contract.review_episode_id,
                    manifest_sha256=empty_manifest, status="ready",
                    is_activatable=True, revision_kind="complete",
                    base_processing_revision_id=base_id,
                    producer_candidate_id=f"scaffold-producer-{snapshot_id}",
                    candidate_input_sha256="f" * 64,
                    completion_manifest_sha256="0" * 64,
                    created_by="scaffold", created_at=to_utc_naive(fixed),
                    payload_json=cj, payload_sha256=csh,
                )
            )
        episode = EpisodeRepository(session).get(contract.review_episode_id)
        new_episode = episode.model_copy(
            update={
                "active_evidence_snapshot_id": snapshot_id,
                "active_evidence_processing_revision_id": complete_id,
            }
        )
        ep_payload, ep_sha = encode_contract(new_episode)
        episode_row = session.get(ReviewEpisodeRecord, contract.review_episode_id)
        episode_row.active_evidence_snapshot_id = snapshot_id
        episode_row.active_evidence_processing_revision_id = complete_id
        episode_row.payload_json = ep_payload
        episode_row.payload_sha256 = ep_sha


def _activate_full_baseline(
    client,
    subject_id: str,
    episode_id: str,
    files,
    *,
    key: str = "key-base",
) -> dict:
    resp = _upload(client, subject_id, episode_id, files)
    assert resp.status_code == 201, resp.text
    preview = resp.json()
    commit_resp = _commit(client, preview, key)
    assert commit_resp.status_code == 201, commit_resp.text
    result = commit_resp.json()
    _activate(client, result["evidence_snapshot_id"])
    return result


def _count(client, table: str) -> int:
    with client.app.state.session_factory() as session:
        return int(
            session.execute(select(func.count()).select_from(text(table))).scalar_one()
        )


def _staging_files(data_paths, preview_id: str) -> list:
    """预览自有暂存目录中的文件（storage_ref 属内部细节，不暴露给 API）。"""
    staging_dir = data_paths.root / "staging" / preview_id
    if not staging_dir.is_dir():
        return []
    return sorted(p for p in staging_dir.iterdir() if p.is_file())


def _assert_error_envelope(body: dict, *, code: str, status: int) -> None:
    assert set(body.keys()) == {"error"}
    error = body["error"]
    assert set(error.keys()) == ERROR_KEYS
    assert error["code"] == code
    assert error["title"]
    assert error["detail"]
    assert error["recovery_action"]
    assert len(error["correlation_id"]) == 32
    # 不泄露内部哈希/枚举/实现词。
    assert "sha256" not in error["detail"].lower()
    assert "staging/" not in error["detail"]


# ---------------------------------------------------------------- 上传预览


def test_create_preview_returns_chinese_dto(client) -> None:
    project_id, subject_id, episode_id = _seed(client)
    response = _upload(
        client, subject_id, episode_id, [pdf(b"one"), pdf(b"two", name="lab.pdf")]
    )
    assert response.status_code == 201, response.text
    preview = response.json()
    assert preview["project_id"] == project_id  # 服务端从审核节点派生项目。
    assert preview["subject_id"] == subject_id
    assert preview["review_episode_id"] == episode_id
    assert preview["upload_mode"] == "full"
    assert preview["upload_mode_label"] == upload_mode_label("full")
    assert preview["status"] == "staged"
    assert preview["status_label"] == preview_status_label("staged")
    assert len(preview["preview_sha256"]) == 64
    assert preview["created_by"] == "测试用户"
    assert len(preview["items"]) == 2
    for item in preview["items"]:
        assert item["status"] == "added"
        assert item["status_label"] == item_status_label("added")
        assert item["reason"]  # 中文原因
        assert item["next_action"]  # 中文下一步
        assert item["processing_hint"] == "process_new"
        assert item["processing_hint_label"]
        assert item["byte_size"] > 0
        assert item["file_name"]


def test_create_preview_rejects_wrong_episode(client) -> None:
    _, subject_id, _ = _seed(client)
    response = _upload(
        client, subject_id, "does-not-exist", [pdf(b"x")], base_revision=1
    )
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


def test_create_preview_rejects_wrong_subject(client) -> None:
    _, _seed_subject, episode_id = _seed(client)
    other_subject = FIXTURES[1].subject.subject_id  # 同项目不同受试者
    response = _upload(client, other_subject, episode_id, [pdf(b"x")])
    assert response.status_code == 404  # 审核节点不属于该受试者。
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


def test_create_preview_rejects_wrong_project_subject(client) -> None:
    _, _, episode_id = _seed(client)
    _, cross_subject, _ = _seed_cross_project(client)
    # 跨项目受试者使用另一项目的审核节点 -> 404。
    response = _upload(client, cross_subject, episode_id, [pdf(b"x")])
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


def test_global_get_preview_derives_scope_from_record(client) -> None:
    _, subject_id, episode_id = _seed(client)
    preview = _upload(client, subject_id, episode_id, [pdf(b"x")]).json()
    response = client.get(f"{PREVIEWS_BASE}/{preview['preview_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["preview_id"] == preview["preview_id"]
    assert body["subject_id"] == subject_id
    assert body["review_episode_id"] == episode_id
    assert body["items"][0]["file_name"] == "report.pdf"


def test_global_preview_get_and_delete_missing_404(client) -> None:
    _seed(client)
    response = client.get(f"{PREVIEWS_BASE}/does-not-exist")
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="PREVIEW_NOT_FOUND", status=404)
    response = client.delete(f"{PREVIEWS_BASE}/does-not-exist")
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="PREVIEW_NOT_FOUND", status=404)


# ---------------------------------------------------------------- 取消


def test_cancel_is_idempotent_and_cleans_staging(client, data_paths) -> None:
    _, subject_id, episode_id = _seed(client)
    preview = _upload(client, subject_id, episode_id, [pdf(b"one")]).json()
    preview_id = preview["preview_id"]
    staged_files = _staging_files(data_paths, preview_id)
    assert staged_files, "预览必须写入自有暂存文件"

    response = client.delete(f"{PREVIEWS_BASE}/{preview_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["status_label"] == preview_status_label("cancelled")
    assert not _staging_files(data_paths, preview_id), "取消必须清理预览自有暂存"

    # 再次取消幂等，返回已取消预览。
    response = client.delete(f"{PREVIEWS_BASE}/{preview_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_cleanup_failure_is_honest_and_retryable(
    client, data_paths
) -> None:
    """故障注入：首次取消清理失败 -> 500 中文信封、保持“正在取消”、commit 被拒。"""
    _, subject_id, episode_id = _seed(client)
    preview = _upload(client, subject_id, episode_id, [pdf(b"one")]).json()
    preview_id = preview["preview_id"]
    staging_dir = data_paths.root / "staging" / preview_id
    assert staging_dir.is_dir()
    # 确定性故障注入：把暂存目录换成普通文件，使 rmtree 必然失败。
    preserved = data_paths.root / "staging" / f".{preview_id}.preserved"
    staging_dir.rename(preserved)
    staging_dir.write_bytes(b"blocker-file")

    first = client.delete(f"{PREVIEWS_BASE}/{preview_id}")
    assert first.status_code == 500
    error = first.json()["error"]
    assert error["code"] == "PREVIEW_CLEANUP_FAILED"
    assert error["title"]
    assert error["recovery_action"]
    # 不泄露内部路径/哈希/内部异常文本。
    assert "staging/" not in error["detail"]
    assert "blocker-file" not in error["detail"]
    assert "sha256" not in error["detail"].lower()
    # 失败清理不得触碰真实暂存内容。
    assert preserved.is_dir()

    # GET 显示“正在取消”。
    status_resp = client.get(f"{PREVIEWS_BASE}/{preview_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "cancel_pending"
    assert status_resp.json()["status_label"] == preview_status_label(
        "cancel_pending"
    )

    # commit 被拒绝（残缺预览不可确认）。
    commit_resp = _commit(client, preview, "key-cleanup-fail")
    assert commit_resp.status_code == 409
    _assert_error_envelope(
        commit_resp.json(), code="PREVIEW_STATE_CONFLICT", status=409
    )

    # 解除阻塞：移除冒充文件 -> 第二次取消成功，状态“已取消”且目录消失。
    staging_dir.unlink()
    second = client.delete(f"{PREVIEWS_BASE}/{preview_id}")
    assert second.status_code == 200
    assert second.json()["status"] == "cancelled"
    assert second.json()["status_label"] == preview_status_label("cancelled")
    assert not staging_dir.exists()
    shutil.rmtree(preserved, ignore_errors=True)  # 测试恢复


def test_commit_cancelled_preview_rejected(client) -> None:
    _, subject_id, episode_id = _seed(client)
    preview = _upload(client, subject_id, episode_id, [pdf(b"one")]).json()
    preview_id = preview["preview_id"]
    client.delete(f"{PREVIEWS_BASE}/{preview_id}")
    response = _commit(client, preview, "key-cancel-commit")
    assert response.status_code == 409
    _assert_error_envelope(
        response.json(), code="PREVIEW_STATE_CONFLICT", status=409
    )


def test_cancel_committed_preview_rejected(client) -> None:
    _, subject_id, episode_id = _seed(client)
    preview = _upload(client, subject_id, episode_id, [pdf(b"one")]).json()
    commit_resp = _commit(client, preview, "key-commit")
    assert commit_resp.status_code == 201
    preview_id = preview["preview_id"]
    response = client.delete(f"{PREVIEWS_BASE}/{preview_id}")
    assert response.status_code == 409
    _assert_error_envelope(
        response.json(), code="PREVIEW_STATE_CONFLICT", status=409
    )


# ---------------------------------------------------------------- 确认


def test_commit_creates_candidate_snapshot_and_job(client) -> None:
    _, subject_id, episode_id = _seed(client)
    preview = _upload(
        client, subject_id, episode_id, [pdf(b"one"), pdf(b"two", name="lab.pdf")]
    ).json()
    response = _commit(client, preview, "key-created")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created"] is True
    assert body["replayed"] is False
    assert body["duplicate"] is False
    assert body["job_id"]
    assert body["evidence_snapshot_id"]
    assert body["commit_id"]
    assert body["preview_id"] == preview["preview_id"]
    assert body["upload_mode"] == "full"
    assert body["upload_mode_label"] == upload_mode_label("full")
    snapshot = body["snapshot"]
    assert snapshot["evidence_snapshot_id"] == body["evidence_snapshot_id"]
    assert snapshot["status"] == "staged"
    assert snapshot["status_label"] == snapshot_status_label("staged")
    assert len(snapshot["members"]) == 2
    assert all(
        member["origin"] == "added"
        and member["origin_label"] == snapshot_member_origin_label("added")
        for member in snapshot["members"]
    )
    assert set(snapshot["members"][0].keys()) == {
        "member_id",
        "snapshot_id",
        "logical_document_id",
        "source_document_version_id",
        "file_name",
        "media_type",
        "version_number",
        "origin",
        "origin_label",
        "metadata_head",
    }
    # 持久任务可查询。
    job_response = client.get(f"/api/v2/jobs/{body['job_id']}")
    assert job_response.status_code == 200
    assert job_response.json()["job_id"] == body["job_id"]


def test_commit_idempotent_replay_same_key(client) -> None:
    _, subject_id, episode_id = _seed(client)
    preview = _upload(client, subject_id, episode_id, [pdf(b"one")]).json()
    first = _commit(client, preview, "key-same").json()
    assert first["created"] is True
    assert first["replayed"] is False
    assert first["job_id"]
    # 同幂等键再次提交 -> 回放既有结果，不创建新快照/新任务。
    response = _commit(client, preview, "key-same")
    assert response.status_code == 200
    body = response.json()
    assert body["created"] is False
    assert body["replayed"] is True
    assert body["duplicate"] is False  # 原确认不是重复集合 no-op。
    assert body["commit_id"] == first["commit_id"]
    assert body["evidence_snapshot_id"] == first["evidence_snapshot_id"]
    assert body["job_id"] == first["job_id"]


def test_source_document_metadata_is_visible_append_only_and_idempotent(client) -> None:
    _, subject_id, episode_id = _seed(client)
    preview = _upload(client, subject_id, episode_id, [pdf(b"one")]).json()
    committed = _commit(client, preview, "key-metadata-source").json()
    member = committed["snapshot"]["members"][0]
    initial = member["metadata_head"]
    assert initial["revision"] == 1
    assert initial["is_auto_suggestion"] is True
    assert initial["document_type"]
    assert initial["source_party"]

    version_id = member["source_document_version_id"]
    payload = {
        "document_type": initial["document_type"],
        "source_party": initial["source_party"],
        "reason": "已与原文件标题和内容核对。",
        "expected_metadata_revision": 1,
        "idempotency_key": "key-metadata-confirm",
        "actor": "医学监查员",
    }
    created = client.patch(
        f"/api/v2/source-document-versions/{version_id}/metadata", json=payload
    )
    assert created.status_code == 201, created.text
    revised = created.json()["metadata"]
    assert revised["revision"] == 2
    assert revised["is_auto_suggestion"] is False
    assert revised["supersedes_metadata_revision_id"] == initial["metadata_revision_id"]

    replay = client.patch(
        f"/api/v2/source-document-versions/{version_id}/metadata", json=payload
    )
    assert replay.status_code == 200
    assert replay.json()["metadata"]["metadata_revision_id"] == revised[
        "metadata_revision_id"
    ]

    stale = client.patch(
        f"/api/v2/source-document-versions/{version_id}/metadata",
        json={**payload, "document_type": "其他资料", "idempotency_key": "key-stale"},
    )
    assert stale.status_code == 409
    _assert_error_envelope(stale.json(), code="STALE_REVISION", status=409)

    unchanged = client.patch(
        f"/api/v2/source-document-versions/{version_id}/metadata",
        json={
            **payload,
            "expected_metadata_revision": 2,
            "idempotency_key": "key-unchanged",
        },
    )
    assert unchanged.status_code == 422
    _assert_error_envelope(unchanged.json(), code="METADATA_UNCHANGED", status=422)


def test_commit_different_key_on_committed_preview_rejected(client) -> None:
    _, subject_id, episode_id = _seed(client)
    preview = _upload(client, subject_id, episode_id, [pdf(b"one")]).json()
    assert _commit(client, preview, "key-a").status_code == 201
    response = _commit(client, preview, "key-b")
    assert response.status_code == 409  # 预览已确认，跨键重复确认被拒绝。
    _assert_error_envelope(
        response.json(), code="PREVIEW_STATE_CONFLICT", status=409
    )


def test_duplicate_member_set_reuses_existing_snapshot(client) -> None:
    _, subject_id, episode_id = _seed(client)
    job_baseline = _count(client, "jobs")
    files = [pdf(b"one"), pdf(b"two", name="lab.pdf")]
    p1 = _upload(client, subject_id, episode_id, files).json()
    first = _commit(client, p1, "key-set-1").json()
    assert first["created"] is True
    assert first["duplicate"] is False
    # 相同内容的新预览（不同 preview_id/幂等键）-> 复用既有快照，不建新 Job。
    p2 = _upload(client, subject_id, episode_id, files).json()
    response = _commit(client, p2, "key-set-2")
    assert response.status_code == 200
    body = response.json()
    assert body["created"] is False
    assert body["replayed"] is False  # 跨预览同集合 no-op，不是请求回放。
    assert body["duplicate"] is True
    assert body["evidence_snapshot_id"] == first["evidence_snapshot_id"]
    assert body["job_id"] is None  # 重复集合 no-op 不创建新任务。
    # 全有或全无：仅一个快照、一个确认（非重复）、一个任务。
    assert _count(client, "evidence_snapshots_v2") == 1
    assert _count(client, "evidence_upload_commits") == 2
    assert _count(client, "jobs") == job_baseline + 1


def test_replay_preserves_duplicate_fact(client) -> None:
    """同键回放保留原确认是否重复的事实：先重复 no-op，再回放仍 duplicate。"""
    _, subject_id, episode_id = _seed(client)
    files = [pdf(b"one")]
    p1 = _upload(client, subject_id, episode_id, files).json()
    created = _commit(client, p1, "key-dup-1").json()
    assert created["created"] is True and created["duplicate"] is False
    # 跨预览同集合 -> duplicate no-op。
    p2 = _upload(client, subject_id, episode_id, files).json()
    dup = _commit(client, p2, "key-dup-2").json()
    assert dup["created"] is False and dup["replayed"] is False
    assert dup["duplicate"] is True
    # 回放 key-dup-2：replayed=True 且保留原 duplicate=True 事实。
    replay = _commit(client, p2, "key-dup-2")
    assert replay.status_code == 200
    body = replay.json()
    assert body["created"] is False
    assert body["replayed"] is True
    assert body["duplicate"] is True
    assert body["commit_id"] == dup["commit_id"]
    assert body["evidence_snapshot_id"] == created["evidence_snapshot_id"]
    assert body["job_id"] is None


def test_commit_concurrent_same_collection_converges(client) -> None:
    """双标签页并发确认同一内容集合：恰好一个快照、一个非重复确认、一个任务。"""
    from concurrent.futures import ThreadPoolExecutor

    _, subject_id, episode_id = _seed(client)
    job_baseline = _count(client, "jobs")
    files = [pdf(b"one"), pdf(b"two", name="lab.pdf")]
    p1 = _upload(client, subject_id, episode_id, files).json()
    p2 = _upload(client, subject_id, episode_id, files).json()
    outcomes: list[dict] = []
    errors: list[Exception] = []

    def run(preview: dict, key: str) -> None:
        try:
            response = _commit(client, preview, key)
            outcomes.append(
                {"status": response.status_code, "body": response.json()}
            )
        except Exception as exc:  # noqa: BLE001 - 并发反例测试收集任意失败
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(run, p1, "key-conc-1"),
            pool.submit(run, p2, "key-conc-2"),
        ]
        for future in futures:
            future.result(timeout=60)

    assert not errors, f"并发确认出现未预期异常：{errors}"
    assert len(outcomes) == 2
    created = [o for o in outcomes if o["body"]["created"]]
    duplicate = [o for o in outcomes if o["body"]["duplicate"]]
    assert len(created) == 1 and len(duplicate) == 1
    assert created[0]["status"] == 201
    assert duplicate[0]["status"] == 200
    assert duplicate[0]["body"]["replayed"] is False  # 并发收敛是重复集合，不是回放。
    assert (
        created[0]["body"]["evidence_snapshot_id"]
        == duplicate[0]["body"]["evidence_snapshot_id"]
    )
    # 并发收敛：恰好一个快照、一个非重复确认、一个初始任务。
    assert _count(client, "evidence_snapshots_v2") == 1
    assert _count(client, "evidence_upload_commits") == 2
    assert _count(client, "jobs") == job_baseline + 1


# ---------------------------------------------------------- 补充与冲突处置


def test_incremental_conflict_requires_resolution_and_new_version(client) -> None:
    _, subject_id, episode_id = _seed(client)
    _activate_full_baseline(client, subject_id, episode_id, [pdf(b"X")])
    # 同名不同内容 -> conflict。
    preview = _upload(
        client, subject_id, episode_id, [pdf(b"Y", name="report.pdf")],
        mode="incremental",
    ).json()
    item = preview["items"][0]
    assert item["status"] == "conflict"
    assert item["status_label"] == item_status_label("conflict")
    assert item["processing_hint"] == "require_resolution"
    # 未提供处置 -> 422。
    missing = _commit(client, preview, "key-conflict-nor")
    assert missing.status_code == 422
    _assert_error_envelope(
        missing.json(), code="MISSING_RESOLUTION", status=422
    )
    # 显式“作为原资料的新版本” -> 递增版本号并替代前序。
    response = _commit(
        client,
        preview,
        "key-conflict-newver",
        resolutions={item["item_id"]: "new_version"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created"] is True
    assert body["resolutions"][0]["resolution"] == "new_version"
    assert body["resolutions"][0]["resolution_label"]
    assert body["resolutions"][0]["supersedes_version_id"]
    member = body["snapshot"]["members"][0]
    assert member["origin"] == "replaced"
    assert member["version_number"] == 2
    assert member["file_name"] == "report.pdf"


def test_incremental_conflict_keep_parallel_new_document(client) -> None:
    _, subject_id, episode_id = _seed(client)
    baseline = _activate_full_baseline(
        client, subject_id, episode_id, [pdf(b"X")]
    )
    original_logical = baseline["snapshot"]["members"][0]["logical_document_id"]
    preview = _upload(
        client, subject_id, episode_id, [pdf(b"Y", name="report.pdf")],
        mode="incremental",
    ).json()
    item = preview["items"][0]
    response = _commit(
        client,
        preview,
        "key-conflict-parallel",
        resolutions={item["item_id"]: "keep_parallel"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    members = body["snapshot"]["members"]
    assert [member["origin"] for member in members] == ["inherited", "added"]
    inherited, added = members
    assert inherited["logical_document_id"] == original_logical
    assert added["logical_document_id"] != original_logical
    assert added["version_number"] == 1


def test_unsupported_format_shows_reason_and_rejects_commit(client) -> None:
    _, subject_id, episode_id = _seed(client)
    response = _upload(
        client, subject_id, episode_id, [("files", ("a.zip", b"PK\x03\x04rest", "application/zip"))]
    )
    assert response.status_code == 201, response.text
    preview = response.json()
    item = preview["items"][0]
    assert item["status"] == "unsupported"
    assert item["status_label"] == item_status_label("unsupported")
    assert item["reason"]  # 中文原因
    assert item["next_action"]
    # 全不支持 -> 无可确认文件 -> 422。
    commit = _commit(client, preview, "key-unsupported")
    assert commit.status_code == 422
    _assert_error_envelope(commit.json(), code="EMPTY_SELECTION", status=422)


def test_stale_preview_rejected_after_base_changed(client) -> None:
    _, subject_id, episode_id = _seed(client)
    # 预览 P 生成时无有效基准。
    p = _upload(client, subject_id, episode_id, [pdf(b"X")]).json()
    # 提交并激活另一完整快照，使有效基准变化。
    q = _upload(client, subject_id, episode_id, [pdf(b"Y", name="other.pdf")]).json()
    q_result = _commit(client, q, "key-other").json()
    _activate(client, q_result["evidence_snapshot_id"])
    # 原预览 P 的基准已过期 -> 409。
    response = _commit(client, p, "key-stale")
    assert response.status_code == 409
    _assert_error_envelope(
        response.json(), code="STALE_BASE_REVISION", status=409
    )


def test_changed_staging_file_rejected_and_rolled_back(client, data_paths) -> None:
    _, subject_id, episode_id = _seed(client)
    preview = _upload(client, subject_id, episode_id, [pdf(b"X")]).json()
    staged = _staging_files(data_paths, preview["preview_id"])
    assert len(staged) == 1
    staged[0].write_bytes(PDF_HEAD + b"CHANGED")  # 暂存内容与预览指纹不一致。
    response = _commit(client, preview, "key-changed")
    assert response.status_code == 409
    _assert_error_envelope(response.json(), code="STAGING_CORRUPTED", status=409)
    assert _count(client, "evidence_snapshots_v2") == 0
    assert _count(client, "evidence_upload_commits") == 0


def test_all_or_nothing_rollback_on_missing_staged_file(client, data_paths) -> None:
    _, subject_id, episode_id = _seed(client)
    preview = _upload(
        client, subject_id, episode_id, [pdf(b"X"), pdf(b"Y", name="lab.pdf")]
    ).json()
    job_baseline = _count(client, "jobs")
    # 删除一个暂存文件 -> 确认在事务内失败，不留任何快照/确认/任务/幂等。
    staged_files = _staging_files(data_paths, preview["preview_id"])
    assert len(staged_files) == 2
    staged_files[0].unlink()
    response = _commit(client, preview, "key-rollback")
    assert response.status_code == 409
    _assert_error_envelope(response.json(), code="STAGING_CORRUPTED", status=409)
    assert _count(client, "evidence_snapshots_v2") == 0
    assert _count(client, "evidence_upload_commits") == 0
    assert _count(client, "jobs") == job_baseline
    # 预览保持 STAGED（事务回滚，未推进状态）。
    fresh = client.get(f"{PREVIEWS_BASE}/{preview['preview_id']}")
    assert fresh.status_code == 200
    assert fresh.json()["status"] == "staged"


def test_commit_preview_sha256_mismatch_rejected(client) -> None:
    _, subject_id, episode_id = _seed(client)
    preview = _upload(client, subject_id, episode_id, [pdf(b"X")]).json()
    response = _commit(
        client, preview, "key-baddigest",
        preview_sha256="0" * 64,
    )
    assert response.status_code == 409
    _assert_error_envelope(
        response.json(), code="PREVIEW_DIGEST_MISMATCH", status=409
    )


def test_commit_extra_preview_id_rejected(client) -> None:
    """preview_id 由路径唯一确定，请求体再提交会被 422 拒绝（extra_forbidden）。"""
    _, subject_id, episode_id = _seed(client)
    preview = _upload(client, subject_id, episode_id, [pdf(b"X")]).json()
    body = {
        "preview_id": "client-claimed-id",
        "preview_sha256": preview["preview_sha256"],
        "upload_mode": preview["upload_mode"],
        "base_revision": preview["base_revision"],
        "idempotency_key": "key-extra",
    }
    response = client.post(
        f"{PREVIEWS_BASE}/{preview['preview_id']}/commit", json=body
    )
    assert response.status_code == 422
    _assert_error_envelope(response.json(), code="INVALID_REQUEST", status=422)


# ---------------------------------------------------------------- 快照查询


def test_snapshot_list_and_detail(client) -> None:
    _, subject_id, episode_id = _seed(client)
    preview = _upload(
        client, subject_id, episode_id, [pdf(b"one"), pdf(b"two", name="lab.pdf")]
    ).json()
    commit = _commit(client, preview, "key-list").json()
    snapshot_id = commit["evidence_snapshot_id"]

    listed = client.get(
        f"/api/v2/subjects/{subject_id}/evidence-snapshots",
        params={"review_episode_id": episode_id},
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body["subject_id"] == subject_id
    assert body["review_episode_id"] == episode_id
    assert [s["evidence_snapshot_id"] for s in body["items"]] == [snapshot_id]

    detail = client.get(f"/api/v2/evidence-snapshots/{snapshot_id}")
    assert detail.status_code == 200
    snap = detail.json()
    assert snap["evidence_snapshot_id"] == snapshot_id
    assert snap["project_id"] == FIXTURES[0].project.project_id
    assert snap["subject_id"] == subject_id  # 作用域从快照记录推导。
    assert snap["upload_mode"] == "full"
    assert len(snap["members"]) == 2
    assert set(snap.keys()) == {
        "evidence_snapshot_id",
        "project_id",
        "subject_id",
        "review_episode_id",
        "upload_mode",
        "upload_mode_label",
        "prior_snapshot_id",
        "comparison_snapshot_id",
        "status",
        "status_label",
        "is_current",
        "base_processing_revision_id",
        "upload_job_id",
        "latest_processing_candidate",
        "members",
        "collection_sha256",
        "created_at",
        "created_by",
    }
    assert snap["upload_job_id"] == commit["job_id"]
    assert snap["latest_processing_candidate"] is None


def test_snapshot_list_rejects_wrong_episode(client) -> None:
    _, subject_id, _ = _seed(client)
    response = client.get(
        f"/api/v2/subjects/{subject_id}/evidence-snapshots",
        params={"review_episode_id": "does-not-exist"},
    )
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


def test_snapshot_detail_missing_404(client) -> None:
    _seed(client)
    response = client.get("/api/v2/evidence-snapshots/does-not-exist")
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


def test_full_mode_preview_lists_omitted_prior_members(client) -> None:
    """完整资料模式展示上一快照有、本次未选择的遗漏成员（含中文原因/下一步）。"""
    _, subject_id, episode_id = _seed(client)
    _activate_full_baseline(
        client,
        subject_id,
        episode_id,
        [pdf(b"X"), pdf(b"Y", name="lab.pdf")],
    )
    # 本次只选择 report.pdf(X)：lab.pdf(Y) 成为遗漏。
    preview = _upload(client, subject_id, episode_id, [pdf(b"X")]).json()
    statuses = [item["status"] for item in preview["items"]]
    assert "full_snapshot_omission" in statuses
    omitted = next(
        item for item in preview["items"] if item["status"] == "full_snapshot_omission"
    )
    assert omitted["file_name"] == "lab.pdf"
    assert omitted["status_label"] == item_status_label("full_snapshot_omission")
    assert omitted["reason"]  # 中文原因：上一快照有、本次未选择。
    assert omitted["next_action"]
    assert omitted["logical_document_id"]
    assert omitted["existing_version_id"]
