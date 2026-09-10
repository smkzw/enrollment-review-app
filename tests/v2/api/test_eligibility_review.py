"""入排审核只读投影 HTTP 作用域与 wire 契约测试。"""
from __future__ import annotations

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
    assert clause["decision"] == "professional_judgment"
    assert clause["gap_type"]
    assert "本次提交的资料中" in clause["reason"]
    assert clause["determination_mode"] == "investigator_judgment"


def test_eligibility_review_rejects_cross_subject_path(client):
    chain = _seed(client, "eligibility-api-scope")
    response = client.get(_url(chain, subject_id="subject-does-not-own-episode"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_eligibility_review_missing_episode_is_404(client):
    chain = _seed(client, "eligibility-api-missing")
    response = client.get(
        f"/api/v2/subjects/{chain['subject_id']}/review-episodes/missing"
        "/eligibility-review"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
