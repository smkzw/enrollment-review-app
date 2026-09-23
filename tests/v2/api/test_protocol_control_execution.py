"""Public start-contract checks for protocol-control execution."""
from __future__ import annotations

import hashlib

from tests.v2.services.test_protocol_control_execution import _seed_frozen_source


_ENDPOINT = "/api/v2/protocol/control-executions"


def test_start_is_idempotent_and_hides_engineering_parameters(client):
    seed = _seed_frozen_source(
        client.app.state.data_paths,
        client.app.state.session_factory,
        key="api-control-start",
    )
    body = {
        "source_job_id": seed.source_job_id,
        "idempotency_key": "api-control-idempotency",
    }
    # This API test checks creation and idempotency, not live model availability.
    client.app.state.protocol_control_job_service.route_identity_factory = (
        lambda stage: hashlib.sha256(stage.encode("utf-8")).hexdigest()
    )

    first = client.post(_ENDPOINT, json=body)
    assert first.status_code == 201
    first_payload = first.json()
    assert first_payload["created"] is True
    assert first_payload["source_job_id"] == seed.source_job_id

    second = client.post(_ENDPOINT, json=body)
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["created"] is False
    assert second_payload["job_id"] == first_payload["job_id"]
    assert second_payload["snapshot_id"] == first_payload["snapshot_id"]
    assert second_payload["manifest_id"] == first_payload["manifest_id"]

    invalid = client.post(
        _ENDPOINT,
        json={
            **body,
            "max_deep_units_per_batch": 1,
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_REQUEST"
