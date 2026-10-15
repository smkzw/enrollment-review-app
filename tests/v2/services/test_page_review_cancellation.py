import asyncio
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from app.services import page_review_cancellation as cancellation
from app.workflow.errors import StepFailure
from app.llm.page_review_admission import PageReviewAdmission
from app.domain.contracts.page_review import PageReviewLane
from tests.v2.services.test_page_review_execution import _routes


def setup_status(monkeypatch, cancelled=False):
    status = SimpleNamespace(cancel_requested=cancelled, state="running")
    monkeypatch.setattr(cancellation, "JobStore", lambda _: SimpleNamespace(job_status=lambda _: status))
    return status


def test_cancelled_job_never_starts_request(monkeypatch):
    setup_status(monkeypatch, True)

    async def operation():
        pytest.fail("cancelled job must not dispatch")

    with pytest.raises(StepFailure):
        asyncio.run(cancellation.run_cancellable(operation, nullcontext, "job"))


def test_cancellation_interrupts_and_releases_request(monkeypatch):
    status = setup_status(monkeypatch)
    released = []

    async def operation():
        try:
            status.cancel_requested = True
            await asyncio.Event().wait()
        finally:
            released.append(True)

    with pytest.raises(StepFailure):
        asyncio.run(cancellation.run_cancellable(operation, nullcontext, "job", poll_seconds=0.001))
    assert released == [True]


def test_completed_result_is_preserved_when_cancellation_arrives(monkeypatch):
    status = setup_status(monkeypatch)

    async def operation():
        status.cancel_requested = True
        return {"saved": True}

    assert asyncio.run(cancellation.run_cancellable(operation, nullcontext, "job")) == {"saved": True}


def test_request_error_not_hidden(monkeypatch):
    setup_status(monkeypatch)

    async def operation():
        raise ValueError("request failure")

    with pytest.raises(ValueError, match="request failure"):
        asyncio.run(cancellation.run_cancellable(operation, nullcontext, "job"))


def test_cancelled_waiter_does_not_dispatch_after_local_slot_frees(monkeypatch):
    from dataclasses import replace

    status = setup_status(monkeypatch)
    routes = _routes()
    route = replace(routes[PageReviewLane.MAIN_B], provider="mlx-serve")
    routes[PageReviewLane.MAIN_B] = route

    async def scenario():
        release = asyncio.Event()
        entered = []

        async def completion(*_):
            entered.append(True)
            await release.wait()

        admission = PageReviewAdmission(routes, completion=completion)
        active = asyncio.create_task(admission(route, [], 65536))
        await asyncio.sleep(0)
        waiter = asyncio.create_task(cancellation.run_cancellable(
            lambda: admission(route, [], 65536), nullcontext, "job", poll_seconds=0.001))
        await asyncio.sleep(0)
        status.cancel_requested = True
        with pytest.raises(StepFailure):
            await waiter
        release.set()
        await active
        assert entered == [True]
        await asyncio.wait_for(admission(route, [], 65536), timeout=1)
        assert entered == [True, True]

    asyncio.run(scenario())
