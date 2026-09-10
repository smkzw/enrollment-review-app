"""Interrupt page work on durable cancellation without discarding completed reads."""

import asyncio
from contextlib import suppress

from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore


async def run_cancellable(operation, session_factory, job_id, *, poll_seconds=0.25):
    def cancelled():
        with session_factory() as session:
            status = JobStore(session).job_status(job_id)
            return status.cancel_requested or status.state in {"cancel_requested", "cancelled"}

    def stopped():
        return StepFailure(retryable=True, error_code="PAGE_REVIEW_CANCEL_REQUESTED",
                           detail="已停止资料判读，已完成的结果会保留。")

    if cancelled():
        raise stopped()
    task = asyncio.create_task(operation())
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=poll_seconds)
            if done:
                return task.result()
            if cancelled():
                raise stopped()
    finally:
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await task
