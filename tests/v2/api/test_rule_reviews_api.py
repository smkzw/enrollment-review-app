from fastapi.testclient import TestClient
from tests.v2.api.test_protocols_api import _create_protocol_job, _seed_review_job


def test_batch_review_is_atomic_current_scoped_and_retry_idempotent(build_app):
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        job = _create_protocol_job(client, key="batch-reviews")
        _seed_review_job(app, job, wait_at="publish")
        url = f"/api/v2/protocol/deconstructions/{job}/draft/reviews"
        view = client.get(url).json()
        items = [{"official_code": entry["official_code"], "rule_content_hash": entry["rule_content_hash"],
                  "note": "excluded" if entry["kind"] == "procedure" else None,
                  "result_variables": ["eos"] if entry["kind"] == "procedure" else []}
                 for entry in view["entries"]]
        body = {"expected_revision_id": view["draft_revision_id"], "reviewer_kind": "builder_verification", "entries": items}
        broken = {**body, "entries": [*items[:-1], {**items[-1], "rule_content_hash": "f" * 64}]}
        assert client.post(url, json=broken).status_code == 409
        assert client.get(url).json()["history"] == []
        assert client.post(url, json={**body, "entries": [items[0], items[0]]}).status_code == 409
        assert client.post(url, json={**body, "expected_revision_id": "missing"}).status_code >= 400
        assert client.post(url, json={**body, "entries": []}).status_code == 422
        response = client.post(url, json=body)
        assert response.status_code == 200, response.text
        saved = response.json()
        assert saved["all_reviewed"] and len(saved["history"]) == len(items)
        assert all(item["reviewer_kind"] == "builder_verification" for item in saved["history"])
        assert client.post(url, json=body).json()["history"] == saved["history"]
        assert all(item["review"]["note"] == "excluded" for item in saved["entries"] if item["kind"] == "procedure")
        changed = {**body, "entries": [*items[:-1], {**items[-1], "result_variables": ["does-not-exist"]}]}
        assert client.post(url, json=changed).status_code == 409
        assert client.get(url).json()["history"] == saved["history"]


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
