"""Shared application admission across job threads and their asyncio loops."""

import asyncio
import threading

from app.llm.page_review_harness import direct_completion


def _admission_key(route):
    if route.provider in {"mlx-serve", "mtplx-gui", "mtplx", "omlx"}:
        return ("local", "shared")
    return (route.provider, route.model)


class PageReviewAdmission:
    def __init__(self, routes, *, completion=direct_completion):
        self.completion = completion
        limits = {}
        for route in routes.values():
            key = _admission_key(route)
            limit = 1 if key == ("local", "shared") else route.max_concurrency
            limits[key] = min(limits.get(key, limit), limit)
        self._slots = {key: threading.BoundedSemaphore(limit) for key, limit in limits.items()}

    async def __call__(self, route, messages, max_tokens):
        slots = self._slots[_admission_key(route)]
        # No background acquire: cancellation cannot leave a later orphaned lease.
        while not slots.acquire(blocking=False):
            await asyncio.sleep(0.02)
        try:
            return await self.completion(route, messages, max_tokens)
        finally:
            slots.release()
