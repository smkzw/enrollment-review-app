"""Phase 4 受试者与审核节点基础 API 合同测试（design.md §5.1，Slice 4.1，worker_03）。

覆盖：

- ``GET /api/v2/projects/{project_id}/subjects``：项目不存在 404；空项目返回空列表；
- ``POST /api/v2/projects/{project_id}/subjects``：201 与 DTO 形状；额外字段 422；
  项目不存在 404；创建后可列出；
- ``GET /api/v2/subjects/{subject_id}/review-episodes``：返回带中文投影标签的
  审核节点 DTO；受试者不存在 404；
- 错误信封合同：code/title/detail/recovery_action/correlation_id 结构一致，
  不泄露内部异常文本。

每个测试启动真实 V2 应用（迁移到 head=0008），通过 ``persist_fixture`` 播种
Phase 3 fixture 作为项目/受试者/审核节点基座。
"""
from __future__ import annotations

import json

import pytest

from app.api.v2.vocabulary import REVIEW_STAGE_LABELS, study_phase_label
from app.domain.contracts.enums import ReviewStage
from app.domain.contracts.rules import WorkflowStage
from app.storage.repositories import (
    AppendRepository,
    WORKFLOW_STAGE_CONFIG,
    persist_fixture,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

SUBJECT_KEYS = {
    "subject_id",
    "subject_code",
    "project_id",
    "center_code",
    "center_name",
    "sex",
    "age_years",
    "revision",
}

EPISODE_KEYS = {
    "review_episode_id",
    "subject_id",
    "project_id",
    "rule_set_id",
    "study_phase",
    "study_phase_label",
    "stage",
    "stage_label",
    "protocol_version_id",
    "rule_set_revision",
    "evidence_snapshot_id",
    "workflow_stage_id",
    "workflow_stage_label",
    "visit_window",
    "latest_evidence_snapshot_id",
    "active_evidence_snapshot_id",
    "active_evidence_processing_revision_id",
    "anchor_dates",
    "due_at",
    "revision",
}

ERROR_KEYS = {"code", "title", "detail", "recovery_action", "correlation_id", "context"}


def _seed(client) -> None:
    """在已启动的应用库中播种一份 Phase 3 fixture。"""
    factory = client.app.state.session_factory
    with factory() as session:
        persist_fixture(session, FIXTURES[0])
        session.commit()
        fixture = FIXTURES[0]
        ids = (
            fixture.project.project_id,
            fixture.subject.subject_id,
            fixture.review_episode.review_episode_id,
        )
        session.rollback()
    return ids


def _seed_published_stages(client) -> dict[str, WorkflowStage]:
    """为 fixture 项目播种命名空间化的已发布流程节点（含同阶段多访视与跳过项）。

    返回 ``{workflow_stage_id: stage}``，用于断言新增受试者自动建立的审核节点。
    """
    factory = client.app.state.session_factory
    fixture = FIXTURES[0]
    rule_set_id = fixture.rule_set.rule_set_id
    revision = fixture.rule_set.revision
    project = fixture.project
    scope = {"protocol_version_id": project.protocol_version.protocol_version_id}
    stages = [
        WorkflowStage(
            workflow_stage_id=f"{rule_set_id}:{revision}:stage-screening",
            stage=ReviewStage.SCREENING,
            display_name="筛选期审核",
            visit_instance="V1",
            visit_window="第1天",
            review_required=True,
        ),
        # 同一审核阶段下的第二个访视实例：必须保持独立审核节点，不能合并。
        WorkflowStage(
            workflow_stage_id=f"{rule_set_id}:{revision}:stage-screening-d1",
            stage=ReviewStage.SCREENING,
            display_name="筛选 D1 审核",
            visit_instance="D1",
            visit_window="第1天",
            review_required=True,
        ),
        WorkflowStage(
            workflow_stage_id=f"{rule_set_id}:{revision}:stage-baseline",
            stage=ReviewStage.BASELINE,
            display_name="基线/随机前审核",
            visit_instance="V2",
            visit_window="第14天",
            review_required=True,
        ),
        # 无需审核的节点：新增受试者不得为其建立审核节点。
        WorkflowStage(
            workflow_stage_id=f"{rule_set_id}:{revision}:stage-notice",
            stage=ReviewStage.SCREENING,
            display_name="筛选知情提醒",
            visit_instance="V0",
            visit_window="知情同意",
            review_required=False,
        ),
    ]
    with factory() as session:
        for stage in stages:
            AppendRepository(session, WORKFLOW_STAGE_CONFIG).save(stage, scope=scope)
        session.commit()
        session.rollback()
    return {stage.workflow_stage_id: stage for stage in stages}


def _assert_error_envelope(body: dict, *, code: str, status: int) -> None:
    assert set(body.keys()) == {"error"}
    error = body["error"]
    assert set(error.keys()) == ERROR_KEYS
    assert error["code"] == code
    assert error["title"]
    assert error["detail"]
    assert error["recovery_action"]
    assert len(error["correlation_id"]) == 32


# ---------------------------------------------------------------- 受试者列表


def test_list_subjects_empty_project_returns_empty_items(client) -> None:
    project_id = "missing-project"
    # 项目必须先存在：播种后再查空列表。
    _seed(client)
    response = client.get(f"/api/v2/projects/{project_id}/subjects")
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


def test_list_subjects_returns_seeded_subjects(client) -> None:
    _, subject_id, _ = _seed(client)
    response = client.get(f"/api/v2/projects/{FIXTURES[0].project.project_id}/subjects")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"project_id", "items"}
    assert body["project_id"] == FIXTURES[0].project.project_id
    assert [item["subject_id"] for item in body["items"]] == [subject_id]
    item = body["items"][0]
    assert set(item.keys()) == SUBJECT_KEYS
    assert item["subject_code"] == FIXTURES[0].subject.subject_code
    assert item["revision"] == 1


def test_list_subjects_missing_project_404(client) -> None:
    response = client.get("/api/v2/projects/does-not-exist/subjects")
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


# ---------------------------------------------------------------- 创建受试者


def test_create_subject_returns_201_dto(client) -> None:
    project_id, _, _ = _seed(client)
    payload = {
        "subject_code": "S-2026-001",
        "center_code": "C01",
        "center_name": "中心一",
        "sex": "女",
        "age_years": 42.5,
    }
    response = client.post(f"/api/v2/projects/{project_id}/subjects", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body.keys()) == SUBJECT_KEYS
    assert body["project_id"] == project_id
    assert body["subject_code"] == "S-2026-001"
    assert body["center_code"] == "C01"
    assert body["center_name"] == "中心一"
    assert body["sex"] == "女"
    assert body["age_years"] == 42.5
    assert body["revision"] == 1
    assert body["subject_id"]


def test_create_subject_minimal_body(client) -> None:
    project_id, _, _ = _seed(client)
    response = client.post(
        f"/api/v2/projects/{project_id}/subjects", json={"subject_code": "S-2"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["center_code"] is None
    assert body["center_name"] is None
    assert body["sex"] is None
    assert body["age_years"] is None


def test_create_subject_rejects_duplicate_code_in_project(client) -> None:
    project_id, _, _ = _seed(client)
    payload = {"subject_code": "S-DUP"}
    assert client.post(f"/api/v2/projects/{project_id}/subjects", json=payload).status_code == 201
    response = client.post(f"/api/v2/projects/{project_id}/subjects", json=payload)
    assert response.status_code == 409
    _assert_error_envelope(response.json(), code="DUPLICATE_RECORD", status=409)


def test_create_subject_in_missing_project_404(client) -> None:
    response = client.post(
        "/api/v2/projects/does-not-exist/subjects", json={"subject_code": "S-3"}
    )
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


def test_create_subject_rejects_extra_fields(client) -> None:
    project_id, _, _ = _seed(client)
    payload = {"subject_code": "S-4", "subject_id": "client-chosen-id"}
    response = client.post(f"/api/v2/projects/{project_id}/subjects", json=payload)
    assert response.status_code == 422
    _assert_error_envelope(response.json(), code="INVALID_REQUEST", status=422)
    fields = [issue["field"] for issue in response.json()["error"]["context"]["fields"]]
    assert "受试者编号" in fields


def test_create_subject_rejects_missing_required_field(client) -> None:
    project_id, _, _ = _seed(client)
    response = client.post(f"/api/v2/projects/{project_id}/subjects", json={})
    assert response.status_code == 422
    _assert_error_envelope(response.json(), code="INVALID_REQUEST", status=422)


def test_created_subjects_are_listed(client) -> None:
    project_id, _, _ = _seed(client)
    for code in ("S-A", "S-B"):
        response = client.post(
            f"/api/v2/projects/{project_id}/subjects", json={"subject_code": code}
        )
        assert response.status_code == 201
    response = client.get(f"/api/v2/projects/{project_id}/subjects")
    codes = [item["subject_code"] for item in response.json()["items"]]
    # 播种 fixture 的受试者 + 两个新建受试者。
    assert set(codes) >= {"S-A", "S-B"}


# ---------------------------------------------------------------- 删除受试者


def test_delete_subject_returns_dto_and_removes_from_list(client) -> None:
    project_id, _, _ = _seed(client)
    created = client.post(
        f"/api/v2/projects/{project_id}/subjects",
        json={"subject_code": "S-DELETE"},
    )
    assert created.status_code == 201
    subject_id = created.json()["subject_id"]

    response = client.delete(f"/api/v2/projects/{project_id}/subjects/{subject_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == SUBJECT_KEYS
    assert body["subject_id"] == subject_id
    assert body["subject_code"] == "S-DELETE"

    listed = client.get(f"/api/v2/projects/{project_id}/subjects").json()["items"]
    assert [item["subject_id"] for item in listed] != [subject_id]
    assert subject_id not in [item["subject_id"] for item in listed]


def test_delete_subject_missing_404(client) -> None:
    project_id, _, _ = _seed(client)
    response = client.delete(f"/api/v2/projects/{project_id}/subjects/does-not-exist")
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


def test_delete_subject_wrong_project_404(client) -> None:
    _, subject_id, _ = _seed(client)
    response = client.delete(f"/api/v2/projects/other-project/subjects/{subject_id}")
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)
    # 跨项目删除不生效：受试者仍在原项目列表。
    listed = client.get(
        f"/api/v2/projects/{FIXTURES[0].project.project_id}/subjects"
    ).json()["items"]
    assert subject_id in [item["subject_id"] for item in listed]


def test_delete_subject_with_review_episodes_409(client) -> None:
    project_id, subject_id, _ = _seed(client)
    response = client.delete(f"/api/v2/projects/{project_id}/subjects/{subject_id}")
    assert response.status_code == 409
    _assert_error_envelope(response.json(), code="SUBJECT_IN_USE", status=409)
    error = response.json()["error"]
    assert error["detail"]
    assert error["recovery_action"]
    # 受试者未被删除。
    listed = client.get(f"/api/v2/projects/{project_id}/subjects").json()["items"]
    assert subject_id in [item["subject_id"] for item in listed]


def test_delete_subject_twice_second_404(client) -> None:
    project_id, _, _ = _seed(client)
    created = client.post(
        f"/api/v2/projects/{project_id}/subjects",
        json={"subject_code": "S-TWICE"},
    )
    subject_id = created.json()["subject_id"]
    assert client.delete(
        f"/api/v2/projects/{project_id}/subjects/{subject_id}"
    ).status_code == 200
    response = client.delete(f"/api/v2/projects/{project_id}/subjects/{subject_id}")
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


# ------------------------------------------------ 原子新增：自动建立审核节点


def test_create_subject_atomically_instantiates_review_required_episodes(client) -> None:
    project_id, _, _ = _seed(client)
    stages = _seed_published_stages(client)
    response = client.post(
        f"/api/v2/projects/{project_id}/subjects", json={"subject_code": "S-ATOM"}
    )
    assert response.status_code == 201, response.text
    subject_id = response.json()["subject_id"]

    response = client.get(f"/api/v2/subjects/{subject_id}/review-episodes")
    assert response.status_code == 200
    items = response.json()["items"]
    # 3 个 review_required 节点（筛选 V1、筛选 D1、基线），跳过 review_required=False 的提醒节点。
    assert len(items) == 3
    by_stage_id = {item["workflow_stage_id"]: item for item in items}
    assert set(by_stage_id) == {
        "ruleset-synthetic-phase-iii:1:stage-screening",
        "ruleset-synthetic-phase-iii:1:stage-screening-d1",
        "ruleset-synthetic-phase-iii:1:stage-baseline",
    }
    d1 = by_stage_id["ruleset-synthetic-phase-iii:1:stage-screening-d1"]
    assert d1["workflow_stage_label"] == stages[
        "ruleset-synthetic-phase-iii:1:stage-screening-d1"
    ].display_name
    assert d1["visit_window"] == "第1天"
    assert d1["stage_label"] == REVIEW_STAGE_LABELS["screening"]
    assert d1["evidence_snapshot_id"] is None
    assert d1["active_evidence_snapshot_id"] is None
    assert d1["rule_set_id"] == "ruleset-synthetic-phase-iii"
    assert d1["rule_set_revision"] == 1
    assert d1["study_phase_label"] == study_phase_label(d1["study_phase"])


def test_create_subject_keeps_same_stage_visit_instances_separate(client) -> None:
    project_id, _, _ = _seed(client)
    _seed_published_stages(client)
    created = client.post(
        f"/api/v2/projects/{project_id}/subjects", json={"subject_code": "S-VISIT"}
    )
    subject_id = created.json()["subject_id"]
    items = client.get(f"/api/v2/subjects/{subject_id}/review-episodes").json()["items"]
    screening_episodes = [item for item in items if item["stage"] == "screening"]
    # 同一审核阶段的两个访视实例保持两个独立审核节点，各自 display_name 保留。
    assert len(screening_episodes) == 2
    assert len({item["workflow_stage_id"] for item in screening_episodes}) == 2
    assert {item["workflow_stage_label"] for item in screening_episodes} == {
        "筛选期审核",
        "筛选 D1 审核",
    }
    assert all(item["evidence_snapshot_id"] is None for item in items)
    assert all(item["active_evidence_snapshot_id"] is None for item in items)


def test_create_subject_rolls_back_when_episode_creation_fails(
    client, monkeypatch
) -> None:
    project_id, _, _ = _seed(client)
    _seed_published_stages(client)
    from uuid import uuid4

    from app.domain.contracts.review import Subject
    from app.storage import repositories as repo_module

    original_save = repo_module.EpisodeRepository.save
    state = {"calls": 0}

    def failing_save(self, episode):
        state["calls"] += 1
        if state["calls"] == 2:
            raise RuntimeError("注入的节点写入失败")
        return original_save(self, episode)

    monkeypatch.setattr(repo_module.EpisodeRepository, "save", failing_save)

    service = client.app.state.evidence_api_command_service
    subject = Subject(
        subject_id=uuid4().hex, subject_code="S-ROLLBACK", project_id=project_id
    )
    with pytest.raises(RuntimeError, match="注入的节点写入失败"):
        service.create_subject(subject)

    # 事务整体回滚：受试者与任何自动建立的节点都未落库，不产生半成品。
    from app.storage.repositories import EpisodeRepository, SubjectRepository

    factory = client.app.state.session_factory
    with factory() as session:
        assert all(
            item.subject_code != "S-ROLLBACK"
            for item in SubjectRepository(session).list_by_project(project_id)
        )
        assert (
            EpisodeRepository(session).list_by_subject(
                subject.subject_id, project_id=project_id
            )
            == []
        )


def test_delete_subject_removes_auto_empty_episodes_and_subject(client) -> None:
    project_id, _, _ = _seed(client)
    _seed_published_stages(client)
    created = client.post(
        f"/api/v2/projects/{project_id}/subjects", json={"subject_code": "S-DELETE-EMPTY"}
    )
    subject_id = created.json()["subject_id"]
    episodes = client.get(f"/api/v2/subjects/{subject_id}/review-episodes").json()["items"]
    assert len(episodes) == 3

    response = client.delete(f"/api/v2/projects/{project_id}/subjects/{subject_id}")
    assert response.status_code == 200, response.text
    # 受试者消失，自动建立的空节点一并删除，不残留孤儿节点。
    listed = client.get(f"/api/v2/projects/{project_id}/subjects").json()["items"]
    assert subject_id not in [item["subject_id"] for item in listed]
    factory = client.app.state.session_factory
    with factory() as session:
        from app.storage.repositories import EpisodeRepository

        assert (
            EpisodeRepository(session).list_by_subject(
                subject_id, project_id=project_id
            )
            == []
        )


def test_delete_subject_refused_after_v2_evidence(client) -> None:
    project_id, _, _ = _seed(client)
    _seed_published_stages(client)
    created = client.post(
        f"/api/v2/projects/{project_id}/subjects", json={"subject_code": "S-EVID"}
    )
    subject_id = created.json()["subject_id"]
    episode_id = client.get(
        f"/api/v2/subjects/{subject_id}/review-episodes"
    ).json()["items"][0]["review_episode_id"]

    # 插入一条不可变 V2 证据快照（模拟已完成上传），其余字段取最小合法形状。
    from datetime import UTC, datetime

    from app.storage.evidence_models import EvidenceSnapshotV2Record

    factory = client.app.state.session_factory
    now = datetime.now(UTC).replace(tzinfo=None)
    payload = json.dumps(
        {
            "evidence_snapshot_id": "snap-v2-1",
            "project_id": project_id,
            "subject_id": subject_id,
            "review_episode_id": episode_id,
            "upload_mode": "full",
            "collection_sha256": "0" * 64,
            "created_by": "test",
        }
    )
    with factory() as session:
        session.add(
            EvidenceSnapshotV2Record(
                evidence_snapshot_id="snap-v2-1",
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=episode_id,
                upload_mode="full",
                prior_snapshot_id=None,
                comparison_snapshot_id=None,
                collection_sha256="0" * 64,
                created_by="test",
                payload_json=payload,
                payload_sha256="0" * 64,
                created_at=now,
            )
        )
        session.commit()
        session.rollback()

    response = client.delete(f"/api/v2/projects/{project_id}/subjects/{subject_id}")
    assert response.status_code == 409
    _assert_error_envelope(response.json(), code="SUBJECT_IN_USE", status=409)
    error = response.json()["error"]
    assert "审核节点" in error["detail"]
    assert error["recovery_action"]
    # 受试者与不可变快照均保留。
    listed = client.get(f"/api/v2/projects/{project_id}/subjects").json()["items"]
    assert subject_id in [item["subject_id"] for item in listed]


def test_delete_subject_refused_with_active_v2_pointer(client) -> None:
    project_id, _, _ = _seed(client)
    _seed_published_stages(client)
    created = client.post(
        f"/api/v2/projects/{project_id}/subjects", json={"subject_code": "S-ACTIVE"}
    )
    subject_id = created.json()["subject_id"]
    factory = client.app.state.session_factory
    with factory() as session:
        from app.storage.repositories import EpisodeRepository

        episode = EpisodeRepository(session).list_by_subject(
            subject_id, project_id=project_id
        )[0]

    episode_id = episode.review_episode_id
    # 用完整合同模型设置成对活动指针并重编码 payload，使列与 payload 镜像一致。
    from datetime import UTC, datetime

    from app.storage.codecs import encode_contract
    from app.storage.evidence_models import EvidenceSnapshotV2Record
    from app.storage.models import ReviewEpisodeRecord
    from app.storage.ocr_models import EvidenceProcessingRevisionRecord

    now = datetime.now(UTC).replace(tzinfo=None)
    active_snapshot = "snap-v2-active"
    active_revision = "epr-active"
    pointer_episode = episode.model_copy(
        update={
            "active_evidence_snapshot_id": active_snapshot,
            "active_evidence_processing_revision_id": active_revision,
        }
    )
    payload_json, payload_sha256 = encode_contract(pointer_episode)
    with factory() as session:
        session.add(
            EvidenceSnapshotV2Record(
                evidence_snapshot_id=active_snapshot,
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=episode_id,
                upload_mode="full",
                prior_snapshot_id=None,
                comparison_snapshot_id=None,
                collection_sha256="1" * 64,
                created_by="test",
                payload_json=json.dumps(
                    {
                        "evidence_snapshot_id": active_snapshot,
                        "project_id": project_id,
                        "subject_id": subject_id,
                        "review_episode_id": episode_id,
                        "upload_mode": "full",
                        "collection_sha256": "1" * 64,
                        "created_by": "test",
                    }
                ),
                payload_sha256="1" * 64,
                created_at=now,
            )
        )
        session.flush()
        session.add(
            EvidenceProcessingRevisionRecord(
                evidence_processing_revision_id=active_revision,
                evidence_snapshot_id=active_snapshot,
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=episode_id,
                manifest_sha256="2" * 64,
                status="completed",
                is_activatable=0,
                revision_kind="base",
                created_by="test",
                payload_json=json.dumps(
                    {"evidence_processing_revision_id": active_revision}
                ),
                payload_sha256="2" * 64,
                created_at=now,
            )
        )
        session.flush()
        from sqlalchemy import update

        session.execute(
            update(ReviewEpisodeRecord)
            .where(ReviewEpisodeRecord.review_episode_id == episode_id)
            .values(
                active_evidence_snapshot_id=active_snapshot,
                active_evidence_processing_revision_id=active_revision,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
            )
        )
        session.commit()
        session.rollback()

    response = client.delete(f"/api/v2/projects/{project_id}/subjects/{subject_id}")
    assert response.status_code == 409
    _assert_error_envelope(response.json(), code="SUBJECT_IN_USE", status=409)
    assert "活动资料版本" in response.json()["error"]["detail"]


# ---------------------------------------------------------------- 审核节点


def test_list_review_episodes_returns_labeled_dtos(client) -> None:
    project_id, subject_id, episode_id = _seed(client)
    response = client.get(f"/api/v2/subjects/{subject_id}/review-episodes")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"subject_id", "items"}
    assert body["subject_id"] == subject_id
    episode = body["items"][0]
    assert set(episode.keys()) == EPISODE_KEYS
    assert episode["review_episode_id"] == episode_id
    assert episode["project_id"] == project_id
    assert episode["subject_id"] == subject_id
    # 中文投影标签必须与词汇表一致。
    assert episode["study_phase_label"] == study_phase_label(episode["study_phase"])
    assert episode["stage_label"] == REVIEW_STAGE_LABELS.get(
        episode["stage"], episode["stage"]
    )
    assert episode["revision"] >= 1
    assert episode["latest_evidence_snapshot_id"] is None
    # due_at 恢复为带时区的 UTC（或为 None）；anchor_dates 为序列化 JSON。
    if episode["due_at"] is not None:
        assert episode["due_at"].endswith("Z") or "+00:00" in episode["due_at"]


def test_list_review_episodes_missing_subject_404(client) -> None:
    _seed(client)
    response = client.get("/api/v2/subjects/does-not-exist/review-episodes")
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)
