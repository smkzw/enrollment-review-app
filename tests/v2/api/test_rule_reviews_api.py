from fastapi.testclient import TestClient
from tests.v2.api.test_protocols_api import _create_protocol_job, _seed_review_job


def test_review_api_stale_revoke_settings_operator_and_publication(build_app, monkeypatch):
    monkeypatch.setenv("ENROLLMENT_OPERATOR_NAME", "王医学经理")
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        job = _create_protocol_job(client, key="reviews-api")
        _seed_review_job(app, job, wait_at="publish")
        url = f"/api/v2/protocol/deconstructions/{job}"
        view = client.get(url + "/draft/reviews").json()
        assert view["operator_name"] == "王医学经理" and not view["all_reviewed"]
        assert client.get(url).json()["operator_name"] == "王医学经理"
        rejected = client.post(url + "/publish", json={"idempotency_key": "missing-reviews"})
        assert rejected.status_code == 409
        first = view["entries"][0]
        request = {"expected_revision_id": view["draft_revision_id"],
                   "rule_content_hash": "f" * 64, "reviewer_kind": "builder_verification"}
        assert client.post(url + f"/draft/rules/{first['official_code']}/review", json=request).status_code == 409
        request["rule_content_hash"] = first["rule_content_hash"]
        for entry in view["entries"]:
            request["rule_content_hash"] = entry["rule_content_hash"]
            request["note"] = "excluded" if entry["kind"] == "procedure" else None
            request["result_variables"] = ["eos"] if entry["kind"] == "procedure" else []
            response = client.post(url + f"/draft/rules/{entry['official_code']}/review", json=request)
            assert response.status_code == 200, response.text
        body = response.json()
        assert body["all_reviewed"]
        assert all(item["reviewed_by"] == "构建者（验证）" for item in body["history"])
        request.update(rule_content_hash=first["rule_content_hash"], note=None, result_variables=[])
        path = url + f"/draft/rules/{first['official_code']}/review"
        revoked = client.request("DELETE", path, json=request)
        assert revoked.status_code == 200 and not revoked.json()["all_reviewed"]
        assert client.post(path, json=request).json()["all_reviewed"]
        published = client.post(url + "/publish", json={"idempotency_key": "approved", "actor": "伪造名称"})
        assert published.status_code == 200, published.text
        assert published.json()["verification_only"] is True
        assert client.get(url).json()["verification_only"] is True
        assert client.post(path, json=request).status_code == 409
