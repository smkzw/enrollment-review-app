"""页面视觉核验任务的修订级 HTTP 查询与人工控制合同。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.selective_vision_postprocess_job_service import (
    SelectiveVisionPostprocessJobService,
)
from tests.v2.services.test_selective_vision_postfreeze_orchestration import (
    _seed_frozen_revision,
)
from tests.v2.services.test_selective_vision_user_control import (
    _seed_complete_revision_alias,
)


def test_complete_revision_reads_and_cancels_base_visual_task(
    build_app, data_paths
) -> None:
    app = build_app()
    with TestClient(app) as client:
        seeded = _seed_frozen_revision(
            app.state.session_factory,
            data_paths,
            revision_id="rev-svo-api-base",
        )
        complete_revision_id = "rev-svo-api-complete"
        _seed_complete_revision_alias(
            app.state.session_factory,
            seeded["revision_id"],
            complete_revision_id,
        )
        service = SelectiveVisionPostprocessJobService(app.state.session_factory)
        enqueued = service.enqueue_for_revision(seeded["revision_id"])

        response = client.get(
            f"/api/v2/evidence-processing-revisions/{complete_revision_id}/selective-vision-task"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["evidence_processing_revision_id"] == complete_revision_id
        assert body["job_id"] == enqueued.job_id
        assert body["state_label"] == "等待处理"
        assert body["can_cancel"] is True
        assert body["can_retry"] is False

        cancelled = client.post(
            f"/api/v2/evidence-processing-revisions/{complete_revision_id}/selective-vision-task/cancel"
        )
        assert cancelled.status_code == 200
        assert cancelled.json() == {
            "job_id": enqueued.job_id,
            "state": "cancelled",
            "state_label": "已停止",
            "changed": True,
        }


def test_revision_visual_task_actions_return_stable_chinese_errors(
    build_app, data_paths
) -> None:
    app = build_app()
    with TestClient(app) as client:
        seeded = _seed_frozen_revision(
            app.state.session_factory,
            data_paths,
            revision_id="rev-svo-api-errors",
        )
        SelectiveVisionPostprocessJobService(
            app.state.session_factory
        ).enqueue_for_revision(seeded["revision_id"])

        retry = client.post(
            f"/api/v2/evidence-processing-revisions/{seeded['revision_id']}/selective-vision-task/retry"
        )
        assert retry.status_code == 409
        error = retry.json()["error"]
        assert error["code"] == "JOB_STATE_CONFLICT"
        assert error["title"] == "任务状态不允许该操作"
        assert error["recovery_action"]

        missing = client.get(
            "/api/v2/evidence-processing-revisions/missing/selective-vision-task"
        )
        assert missing.status_code == 404
        missing_error = missing.json()["error"]
        assert missing_error["code"] == "NOT_FOUND"
        assert missing_error["title"] == "记录不存在"
