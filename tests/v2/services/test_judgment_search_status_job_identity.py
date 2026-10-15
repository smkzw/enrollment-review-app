"""Both task views must select their own results, not the authority's newest run."""
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from app.services import judgment_search_status as status
from tests.v2.services.test_judgment_search_results import _scope_two


@pytest.mark.parametrize("reader", [
    status.judgment_search_job_status, status.judgment_search_job_results,
])
def test_task_view_never_borrows_other_task_results(monkeypatch, reader):
    authority = _scope_two().authority
    job_id = "unfinished-search"
    calls = []

    class Repository:
        def __init__(self, session):
            pass

        def latest_for_authority(self, selected_authority, *, job_id=None):
            calls.append((selected_authority, job_id))
            assert job_id == "unfinished-search"
            return {}

    monkeypatch.setattr(status, "JudgmentSearchSummaryRepository", Repository)
    monkeypatch.setattr(status, "store_steps", lambda *args: [])
    monkeypatch.setattr(status, "_load_job", lambda *args, **kwargs: (
        SimpleNamespace(state="running"),
        {"authority": authority.model_dump(mode="json"), "pages": [],
         "requirements": [{"requirement_id": "judgment-required"}]},
    ))
    result = reader(
        lambda: nullcontext(object()), subject_id=authority.subject_id,
        review_episode_id=authority.review_episode_id, job_id=job_id,
    )
    assert calls == [(authority, job_id)]
    if reader is status.judgment_search_job_results:
        assert result["results"][0]["status"] is None
    else:
        assert result["requirement_results"] == []
