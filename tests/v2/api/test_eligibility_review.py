"""入排审核只读投影 HTTP 作用域与 wire 契约测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.v2.eligibility_review import EligibilityReviewResponse
from tests.v2.storage.test_fact_repositories import _seed_chain


def _seed(client, prefix: str = "eligibility-api"):
    with client.app.state.session_factory() as session:
        chain = _seed_chain(session, prefix)
        session.commit()
        return chain


def _url(chain, subject_id: str | None = None) -> str:
    return (
        f"/api/v2/subjects/{subject_id or chain['subject_id']}"
        f"/review-episodes/{chain['episode_id']}/eligibility-review"
    )


def test_eligibility_review_returns_current_read_only_wire(client):
    chain = _seed(client)
    response = client.get(_url(chain))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["unassigned_conflicts"] == []
    assert body["evidence_snapshot_v2_id"] == chain["snapshot_id"]
    assert body["complete_processing_revision_id"] == chain["complete_revision_id"]
    assert body["subject_id"] == chain["subject_id"]
    assert body["review_episode_id"] == chain["episode_id"]
    assert {item["rule_code"] for item in body["clauses"]} >= {
        "IN-01",
        "EX-02",
        "REQ-01",
    }
    clause = next(item for item in body["clauses"] if item["rule_code"] == "EX-02")
    assert clause["decision"] == "indeterminate"
    assert clause["gap_type"] == "observation_unverified"
    assert clause["gap_type"]
    assert "资料尚未完成核实" in clause["reason"]
    assert "尚未完成" in clause["reason"]
    assert "未见" not in clause["reason"]
    assert clause["rule_component_id"]
    assert clause["determination_mode"] == "investigator_judgment"

    # One official criterion may contain multiple independently selectable items.
    body["clauses"].append({**clause, "rule_component_id": "distinct-component"})
    EligibilityReviewResponse.model_validate(body)
    body["clauses"][-1]["rule_component_id"] = clause["rule_component_id"]
    with pytest.raises(ValidationError, match="重复的审核要点身份"):
        EligibilityReviewResponse.model_validate(body)


def test_eligibility_review_rejects_cross_subject_path(client):
    chain = _seed(client, "eligibility-api-scope")
    response = client.get(_url(chain, subject_id="subject-does-not-own-episode"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize("kind", ["event", "exposure"])
def test_unassigned_conflict_reaches_http_without_changing_clause_decisions(client, kind):
    from datetime import UTC, datetime
    from app.domain.contracts.enums import DurationStatus
    from app.domain.contracts.facts import ClinicalConflictGroupV2
    from app.services.eligibility_review_projection import EligibilityReviewProjectionService
    from app.storage.fact_repositories import ClinicalConflictGroupV2Repository
    from tests.v2.storage.test_fact_correction_repository import _seed_valid_chain
    from tests.v2.services.test_fact_correction_job import _publish_event, _publish_exposure, _day
    from tests.v2.services.test_eligibility_review_projection import _publish_age_fact

    with client.app.state.session_factory() as session:
        chain = _seed_valid_chain(session, f"wire-{kind}-conflict")
        fact = _publish_age_fact(session, chain, value=20, suffix="age")
        before = EligibilityReviewProjectionService().project(session, chain["episode_id"])
        publish = _publish_event if kind == "event" else _publish_exposure
        members = [publish(session, chain, fact, suffix=str(index), start=_day(day), duration=DurationStatus.ONGOING)
                   for index, day in enumerate(["2026-01-01", "2026-03-01"])]
        ids = sorted(getattr(item, f"{kind}_id") for item in members)
        group_id = f"{chain['run_id']}-conflict"
        ClinicalConflictGroupV2Repository(session).create(ClinicalConflictGroupV2(
            conflict_group_id=group_id, run_id=members[0].run_id, gate_id=members[0].gate_id,
            authority=chain["authority"], member_kind=kind, **{f"{kind}_ids": ids},
            locator_ids=[chain["locator_id"]], created_at=datetime(2026, 8, 23, tzinfo=UTC),
        ))
        session.commit()
    response = client.get(_url(chain))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["unassigned_conflicts"] == [{"conflict_group_id": group_id, "member_kind": kind, "member_ids": ids}]
    assert [(item["decision"], item["gap_type"]) for item in body["clauses"]] == [
        (item.decision, item.gap_type) for item in before.clauses
    ]
    body["unassigned_conflicts"].append(body["unassigned_conflicts"][0])
    with pytest.raises(ValidationError, match="重复的争议记录"):
        EligibilityReviewResponse.model_validate(body)


def test_eligibility_review_missing_episode_is_404(client):
    chain = _seed(client, "eligibility-api-missing")
    response = client.get(
        f"/api/v2/subjects/{chain['subject_id']}/review-episodes/missing"
        "/eligibility-review"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_incomplete_source_closure_is_not_a_generic_error_or_clinical_gap(client, monkeypatch):
    from app.services.eligibility_review_projection import EligibilityReviewProjectionError

    chain = _seed(client, "eligibility-source-closure")
    def incomplete(*args):
        raise EligibilityReviewProjectionError("private-fact-id missing private-locator-id")
    monkeypatch.setattr(client.app.state.eligibility_review_projection_service, "project", incomplete)
    response = client.get(_url(chain))
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "REVIEW_SOURCE_INCOMPLETE"
    assert "已有资料已保留" in error["detail"]
    assert "无需重复上传" in error["recovery_action"]
    assert "private-" not in response.text
    assert "clauses" not in response.json()
