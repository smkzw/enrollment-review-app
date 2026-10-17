from fastapi.testclient import TestClient
from tests.v2.api.test_protocols_api import _create_protocol_job, _seed_review_job


def test_binding_save_is_append_only_and_stale_scope_is_rejected(build_app):
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        job = _create_protocol_job(client, key="variable-api")
        _seed_review_job(app, job, wait_at="publish")
        url = f"/api/v2/protocol/deconstructions/{job}/draft/variables"
        view = client.get(url).json()
        original = client.get(url.removesuffix("/variables")).json()
        first = view["predicates"][0]
        context = view["source_context"][first["component_id"]]
        parent = next(rule for rule in original["content"]["proposed_rules"] if rule["official_code"] == first["official_code"])
        assert context["parent_source_text"] == parent["source_text"]
        payload = {"expected_revision_id": view["draft_revision_id"], "proposal": {
            "variables": [], "bindings": [{"component_id": first["component_id"], "predicate_id": first["predicate_id"],
                "requirement_id": first["requirements"][0]["requirement_id"], "variable_id": "age"}]}}
        response = client.put(url, json=payload)
        assert response.status_code == 200, response.text
        updated = client.get(url).json()
        assert updated["draft_revision_id"] != view["draft_revision_id"]
        assert updated["predicates"][0]["variable_id"] == "age"
        assert original["revision_number"] + 1 == response.json()["revision_number"]
        assert client.put(url, json=payload).status_code == 409
        payload["expected_revision_id"] = updated["draft_revision_id"]
        payload["proposal"]["bindings"][0]["variable_id"] = "sex"
        assert client.put(url, json=payload).status_code == 409
