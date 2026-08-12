"""In-process guards for long-running subject workflows."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import HTTPException

from app.shared import validate_storage_id


_LOCKS: dict[tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)


async def acquire_subject_processing_lock(project_code: str, subject_id: str) -> tuple[str, str]:
    """Acquire a non-reentrant subject workflow lock or raise 409."""
    key = (
        validate_storage_id(project_code, "项目编号"),
        validate_storage_id(subject_id, "受试者ID"),
    )
    lock = _LOCKS[key]
    if lock.locked():
        raise HTTPException(status_code=409, detail=f"受试者 {key[1]} 正在处理中，请等待完成后再试")
    await lock.acquire()
    return key


def release_subject_processing_lock(key: tuple[str, str] | None) -> None:
    if not key:
        return
    lock = _LOCKS.get(key)
    if lock and lock.locked():
        lock.release()
