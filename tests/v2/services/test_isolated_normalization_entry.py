from unittest.mock import Mock

import pytest

from scripts.run_isolated_page_revision import normalize_selected_job, verify_frozen_readers


@pytest.mark.parametrize("budget", [12000, 16384, 65535, None, True])
def test_low_normalizer_budget_rejected(budget):
    from scripts.run_isolated_page_revision import verify_normalizer_budget
    with pytest.raises(ValueError, match="65536"):
        verify_normalizer_budget(budget)


@pytest.mark.parametrize("budget", [65536, 131072])
def test_normalizer_budget_preserved(budget):
    from scripts.run_isolated_page_revision import verify_normalizer_budget
    assert verify_normalizer_budget(budget) == budget


@pytest.mark.parametrize("budget,changed", [(65536, False), (12000, False), (65536, True)])
def test_frozen_readers_match_explicit_configuration(budget, changed):
    from app.llm.page_review_harness import require_page_reader_routes
    from app.services.page_review_job_service import route_identity
    routes = require_page_reader_routes({"INDEPENDENT_VLM_API_KEY": "test",
                                        "PAGE_REVIEW_MAIN_B_PROVIDER": "mtplx",
                                        "PAGE_REVIEW_MAIN_B_MODEL": "mtplx-flash-next-optimized-speed",
                                        "PAGE_REVIEW_MAIN_B_BASE_URL": "http://127.0.0.1:8002/v1",
                                        "PAGE_REVIEW_MAX_TOKENS": str(budget)})
    payload = {"routes": {lane.value: route_identity(route) for lane, route in routes.items()}}
    if changed:
        payload["routes"]["main-B"]["model"] = "unexpected-model"
    if budget < 65536 or changed:
        with pytest.raises(ValueError):
            verify_frozen_readers(payload, routes)
    else:
        result = verify_frozen_readers(payload, routes)
        assert set(result) == {"main-A", "main-B"}
        assert all("api_key" not in reader for reader in result.values())


@pytest.mark.parametrize("status", [200, 201, 409, 503])
def test_only_fresh_formal_job_is_run(status):
    client, runner, save = Mock(), Mock(), Mock()
    client.post.return_value.status_code = status
    client.post.return_value.json.return_value = {"job_id": "new-normalization"}
    client.get.return_value.json.return_value = {"state": "completed"}
    receipt = {"clinical_acceptance": False, "claims_complete": False}
    base = "/api/v2/subjects/s/review-episodes/e/page-review-jobs"
    if status == 201:
        normalize_selected_job(client, runner, base, receipt, save)
        runner.run_job.assert_called_once_with("new-normalization")
        client.get.assert_called_once_with("/api/v2/jobs/new-normalization")
    else:
        with pytest.raises(RuntimeError, match="No fresh"):
            normalize_selected_job(client, runner, base, receipt, save)
        runner.run_job.assert_not_called()
    client.post.assert_called_once_with(
        "/api/v2/subjects/s/review-episodes/e/fact-normalization-jobs", json={})
    assert receipt["normalization_submission_status"] == status
    assert receipt["clinical_acceptance"] is False
    assert receipt["claims_complete"] is False
    assert save.called


def test_retryable_failure_does_not_spin_or_redispatch():
    client, runner, save = Mock(), Mock(), Mock()
    client.post.return_value.status_code = 201
    client.post.return_value.json.return_value = {"job_id": "normalization"}
    client.get.return_value.json.return_value = {"state": "failed_retryable"}
    receipt = {"claims_complete": False}
    with pytest.raises(RuntimeError, match="formal retry endpoint"):
        normalize_selected_job(client, runner, "/page-review-jobs", receipt, save)
    runner.run_job.assert_called_once_with("normalization")
    assert client.post.call_count == 1
    assert receipt["normalization_status"]["state"] == "failed_retryable"
    assert receipt["claims_complete"] is False
