import asyncio
import threading
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.llm.page_review_admission import PageReviewAdmission
from app.domain.contracts.page_review import PageReviewLane
from tests.v2.services.test_page_review_execution import _routes


def test_local_platforms_share_one_slot():
    routes = _routes()
    routes[PageReviewLane.MAIN_B] = replace(routes[PageReviewLane.MAIN_B], provider="mlx-serve")
    active = peak = 0

    async def completion(*_args):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1

    async def scenario():
        admission = PageReviewAdmission(routes, completion=completion)
        await asyncio.gather(*(admission(routes[PageReviewLane.MAIN_B], [], 1024) for _ in range(6)))

    asyncio.run(scenario())
    assert peak == 1
    assert active == 0


def test_shared_limit_across_job_threads():
    routes = _routes()
    route = routes[PageReviewLane.MAIN_A]
    active = peak = 0
    lock = threading.Lock()
    barrier = threading.Barrier(6)

    async def completion(*_args):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.05)
        with lock:
            active -= 1

    admission = PageReviewAdmission(routes, completion=completion)

    def run(_):
        barrier.wait(timeout=5)
        asyncio.run(admission(route, [], 1024))

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(run, range(6)))
    assert peak == route.max_concurrency
    assert active == 0


def test_cancelled_waiter_and_failed_call_release_capacity():
    routes = _routes()
    route = routes[PageReviewLane.MAIN_A]

    async def scenario():
        entered = 0
        release = asyncio.Event()

        async def completion(*_args):
            nonlocal entered
            entered += 1
            await release.wait()
            raise ValueError("controlled failure")

        admission = PageReviewAdmission(routes, completion=completion)
        running = [asyncio.create_task(admission(route, [], 1024)) for _ in range(route.max_concurrency)]
        await asyncio.sleep(0)
        assert entered == route.max_concurrency
        waiter = asyncio.create_task(admission(route, [], 1024))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        release.set()
        results = await asyncio.gather(*running, return_exceptions=True)
        assert all(isinstance(result, ValueError) for result in results)
        with pytest.raises(ValueError):
            await asyncio.wait_for(admission(route, [], 1024), timeout=1)
        assert entered == route.max_concurrency + 1

    asyncio.run(scenario())
