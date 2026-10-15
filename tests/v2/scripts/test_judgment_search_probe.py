import asyncio
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_harness import PageCompletion
from scripts import run_judgment_search_probe as probe
from tests.v2.llm.test_judgment_search_batch_reader import (
    _IMAGE, _batch_text, _page_input, _route, _scope,
)


def setup_probe(tmp_path, monkeypatch, *, fail_second=False):
    args = SimpleNamespace(mode="prepare", output=tmp_path / "probe",
        runtime=tmp_path / "source", source_job="job", requirement="req-a",
        additional_requirement=["req-b"], page_artifact="pa-1")

    def source(runtime, job, requirement, page):
        return _scope(requirement), requirement + " assessment", _page_input(), _IMAGE

    routes = {
        PageReviewLane.MAIN_A: replace(_route(), model="glm-5.3-flash", max_tokens=65536),
        PageReviewLane.MAIN_B: replace(_route(PageReviewLane.MAIN_B,
            "google-antigravity", "gemini-3.7-flash"), max_tokens=65536),
    }
    calls = []

    async def resolve(route):
        return route

    async def complete(route, messages, budget):
        calls.append(route.lane)
        if fail_second and route.lane == PageReviewLane.MAIN_B:
            raise RuntimeError("offline")
        return PageCompletion(text=_batch_text({"req-a": ("not_found", []),
            "req-b": ("not_found", [])}), finish_reason="stop", usage={},
            response_model=route.model, response_id=route.lane.value)

    monkeypatch.setattr(probe, "prepare_source", source)
    monkeypatch.setattr(probe, "require_page_reader_routes", lambda: routes)
    monkeypatch.setattr(probe, "resolve_route_model", resolve)
    monkeypatch.setattr(probe, "direct_completion", complete)
    return args, calls


@pytest.mark.parametrize("fail_second", [False, True])
def test_batch_probe_roundtrip_and_failed_lane_coverage(tmp_path, monkeypatch, fail_second):
    args, calls = setup_probe(tmp_path, monkeypatch, fail_second=fail_second)
    asyncio.run(probe.run(args))
    assert calls == []
    args.mode = "execute"
    asyncio.run(probe.run(args))
    assert set(calls) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}
    assert len(calls) == 2
    attempt = args.output / "attempt"
    results = json.loads((attempt / "summary.json").read_text())
    assert sum(r["candidate_received"] for r in results) == (1 if fail_second else 2)
    for index in range(2):
        coverage = json.loads((attempt / f"target-{index}.coverage.json").read_text())
        expected = "coverage_incomplete" if fail_second else "all_supplied_pages_searched_without_candidate"
        assert coverage["status"] == expected
        assert coverage["product_acceptance"] is False
    with pytest.raises(FileExistsError):
        asyncio.run(probe.run(args))
    assert len(calls) == 2


def test_duplicate_target_rejected_before_output_or_calls(tmp_path, monkeypatch):
    args, calls = setup_probe(tmp_path, monkeypatch)
    args.additional_requirement = ["req-a"]
    with pytest.raises(ValueError, match="重复"):
        asyncio.run(probe.run(args))
    assert calls == []
    assert not args.output.exists()
