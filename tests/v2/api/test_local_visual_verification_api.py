"""Product API enqueue/result are scoped; no model is called by an endpoint."""
import pytest
from app.services.local_visual_verification import LOCAL_VISUAL_JOB_TYPE
from app.services.selective_vision_postprocess_job_service import SelectiveVisionPostprocessJobService
from tests.v2.services.test_local_visual_job import _seed


@pytest.mark.parametrize("read_format", ["transcript", "structured_candidate"])
def test_product_region_entry_is_persisted_without_approving_page(client, read_format):
    factory = client.app.state.session_factory
    seeded = _seed(factory, client.app.state.data_paths)
    base = f"/api/v2/evidence-processing-revisions/{seeded['revision_id']}/pages/{seeded['page_artifact_id']}/local-verification"
    assert client.get(base).json()["found"] is False
    body = {"x0": 2, "y0": 3, "x1": 30, "y1": 40, "clockwise_degrees": 90, "read_format": read_format}
    response = client.post(base, json=body)
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert client.post(base, json=body).json()["job_id"] == job_id
    task = client.get(base).json()
    assert task["state"] == "queued" and task["observation_text"] is None
    assert task["candidate_only"] is True and task["coverage_scope"] == "region_only"
    assert LOCAL_VISUAL_JOB_TYPE in client.app.state.job_executors
    assert not SelectiveVisionPostprocessJobService(factory).get_revision_task(seeded["revision_id"]).found
    assert client.post(f"/api/v2/jobs/{job_id}/cancel").status_code == 200
    assert client.get(base).json()["state"] == "cancelled"
    assert client.post(base, json={**body, "x0": True}).status_code == 422
    assert client.post(base, json={**body, "x1": 61}).status_code == 409
    other = base.replace(seeded["page_artifact_id"], "other-page")
    assert client.post(other, json=body).status_code == 409
