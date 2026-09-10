"""Slice 5.7 人工事实修订 HTTP 合同。"""

from __future__ import annotations

from datetime import UTC, datetime

from app.services.fact_correction_job_service import FACT_CORRECTION_JOB_TYPE
from app.services.patient_profile_service import PatientProfileService
from app.storage.models import ReviewEpisodeRecord
from tests.v2.storage.test_fact_correction_repository import (
    _create_fact_with_candidate,
    _seed_valid_chain,
)
from tests.v2.storage.test_fact_repositories import _update_episode

NOW = datetime(2026, 8, 23, 8, 0, 0, tzinfo=UTC)


def test_v2_app_registers_fact_correction_executor(client):
    assert FACT_CORRECTION_JOB_TYPE in client.app.state.job_executors


def test_preview_and_submit_and_history_are_chinese_and_idempotent(client):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_valid_chain(session, "api-corr")
        fact = _create_fact_with_candidate(
            session,
            chain,
            fact_id=f"{chain['run_id']}-fact-api",
            run_id=f"{chain['run_id']}-api",
            call_id=f"{chain['call_id']}-api",
            gate_id=f"{chain['run_id']}-gate-api",
            cand_id=f"{chain['run_id']}-cand-api",
        )
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        subject_id = chain["subject_id"]
        episode_id = chain["review_episode_id"]
        fact_id = fact.fact_id
        locator_id = chain["locator_id"]

    base = (
        f"/api/v2/subjects/{subject_id}/review-episodes/{episode_id}/fact-corrections"
    )
    body = {
        "target_kind": "fact",
        "target_id": fact_id,
        "locator_ids": [locator_id],
        "value": "130/80",
        "reason": "核对原文后更正血压值",
        "operator_id": "监查员甲",
    }
    preview = client.post(f"{base}/preview", json=body)
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["target_kind_label"] == "事实记录"
    assert payload["old_snapshot"]["value"] == "120/80"
    assert payload["new_snapshot"]["value"] == "130/80"
    assert payload["impact"]["scope_kind_label"]
    assert "affected_conflict_group_ids" in payload["impact"]
    raw = preview.text
    for forbidden in ("inclusion_met", "exclusion_triggered", "verdict", "enrollment"):
        assert forbidden not in raw

    created = client.post(base, json=body)
    assert created.status_code == 201, created.text
    created_body = created.json()
    assert created_body["created"] is True
    assert created_body["state_label"]
    assert "无需操作" in created_body["recovery_action"] or created_body["recovery_action"]

    reused = client.post(base, json=body)
    assert reused.status_code == 200, reused.text
    assert reused.json()["job_id"] == created_body["job_id"]
    assert reused.json()["created"] is False

    from app.workflow.runner import JobRunner

    runner = JobRunner(
        factory,
        client.app.state.job_executors,
        worker_id="api-w1",
    )
    assert runner.run_job(created_body["job_id"]) is True
    history = client.get(base)
    assert history.status_code == 200, history.text
    items = history.json()["items"]
    assert len(items) == 1
    assert items[0]["reason"] == "核对原文后更正血压值"
    assert items[0]["target_kind_label"] == "事实记录"
    assert items[0]["patient_profile_revision_id"]
    assert items[0]["patient_profile_revision"] == 2
    assert "affected_conflict_group_ids" in items[0]["impact"]
    assert "verdict" not in history.text
    # F6/Q3：历史存档必须是与预览一致的完整语义快照，不能只剩展示片段。
    for key in (
        "fact_type",
        "profile_lane",
        "polarity",
        "asserted_object",
        "value",
        "unit",
        "date_range",
        "source_strength",
        "supported_requirement_ids",
    ):
        assert key in items[0]["old_snapshot"]
        assert key in items[0]["new_snapshot"]
        assert items[0]["old_snapshot"][key] == payload["old_snapshot"][key]
        assert items[0]["new_snapshot"][key] == payload["new_snapshot"][key]
    assert items[0]["old_snapshot"]["value"] == "120/80"
    assert items[0]["new_snapshot"]["value"] == "130/80"

    # F1/Q1：patient_profile_revision_id 绑定本次修订生成的档案（含新值），不是修订前档案。
    generated_profile = client.get(
        f"/api/v2/subjects/{subject_id}/patient-profile-revisions/"
        f"{items[0]['patient_profile_revision_id']}"
    )
    assert generated_profile.status_code == 200, generated_profile.text
    generated_body = generated_profile.json()
    assert generated_body["revision"] == 2
    fact_items = [
        item
        for lane in generated_body["lanes"]
        for item in lane["items"]
        if item["kind"] == "fact" and item["source_id"] == items[0]["new_entity_id"]
    ]
    assert len(fact_items) == 1
    assert fact_items[0]["value"] == "130/80"
    assert set(items[0]["locator_ids"]).issubset(set(fact_items[0]["locator_ids"]))
    locator_by_id = {
        loc["locator_id"]: loc for loc in generated_body["evidence_locators"]
    }
    for locator_id in items[0]["locator_ids"]:
        loc = locator_by_id[locator_id]
        assert loc["page_number"] >= 1
        assert loc["page_artifact_id"]
        assert loc["source_document_version_id"]

    missing_reason = dict(body)
    missing_reason.pop("reason")
    rejected = client.post(base, json=missing_reason)
    assert rejected.status_code in {422, 409}
    assert "error" in rejected.json()
    assert rejected.json()["error"]["title"]
    assert "sqlalchemy" not in rejected.text.lower()

    # 完成后再次提交相同请求：复用已完成 Job，不新建。
    after_done = client.post(base, json=body)
    assert after_done.status_code == 200, after_done.text
    assert after_done.json()["job_id"] == created_body["job_id"]
    assert after_done.json()["created"] is False
    assert after_done.json()["state"] == "completed"

    frozen_profile_id = items[0]["patient_profile_revision_id"]
    frozen_profile_revision = items[0]["patient_profile_revision"]
    with factory() as session, session.begin():
        episode = session.get(ReviewEpisodeRecord, episode_id)
        _update_episode(session, episode, revision=2)

    history_after_bump = client.get(base)
    assert history_after_bump.status_code == 200, history_after_bump.text
    bumped_items = history_after_bump.json()["items"]
    assert len(bumped_items) == 1
    assert bumped_items[0]["patient_profile_revision_id"] == frozen_profile_id
    assert bumped_items[0]["patient_profile_revision"] == frozen_profile_revision


def test_unknown_nested_date_range_keys_are_rejected(client):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_valid_chain(session, "api-strict-date")
        fact = _create_fact_with_candidate(
            session,
            chain,
            fact_id=f"{chain['run_id']}-fact-strict",
            run_id=f"{chain['run_id']}-strict",
            call_id=f"{chain['call_id']}-strict",
            gate_id=f"{chain['run_id']}-gate-strict",
            cand_id=f"{chain['run_id']}-cand-strict",
        )
        PatientProfileService().generate(
            session, authority=chain["authority"], created_at=NOW, generated_at=NOW
        )
        subject_id = chain["subject_id"]
        episode_id = chain["review_episode_id"]
        fact_id = fact.fact_id
        locator_id = chain["locator_id"]

    base = (
        f"/api/v2/subjects/{subject_id}/review-episodes/{episode_id}/fact-corrections"
    )
    for field in ("date_range", "start_range", "end_range"):
        body = {
            "target_kind": "fact",
            "target_id": fact_id,
            "locator_ids": [locator_id],
            "reason": "核对日期",
            "operator_id": "监查员甲",
            field: {
                "source_text": "2026-03-01",
                "precision": "day",
                "lower_bound": "2026-03-01",
                "upper_bound": "2026-03-01",
                "unexpected_anchor": "smuggled",
            },
        }
        for endpoint in (f"{base}/preview", base):
            response = client.post(endpoint, json=body)
            assert response.status_code == 422, response.text
            envelope = response.json()["error"]
            assert envelope["code"] == "INVALID_REQUEST"
            assert envelope["title"]
            assert "unexpected_anchor" in response.text or "不识别" in response.text
            assert "sqlalchemy" not in response.text.lower()
