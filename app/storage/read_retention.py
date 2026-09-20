"""Bounded ORM retention during one synchronous read, never validation caching."""

from collections import deque
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import event
from sqlalchemy.orm import Session


@contextmanager
def retain_read_records(session: Session, *, capacity: int = 4096) -> Iterator[None]:
    """Reduce weak-identity-map reloads without retaining records across reads.

    Only use in a read-owned session. Repository validation still runs on every
    access. Eviction merely permits an additional database read, not a shortcut.
    """
    if capacity < 1:
        raise ValueError("Read retention capacity must be positive")
    retained: deque[object] = deque(session.identity_map.values(), maxlen=capacity)

    def loaded(_session: Session, instance: object) -> None:
        retained.append(instance)

    event.listen(session, "loaded_as_persistent", loaded)
    try:
        yield
    finally:
        event.remove(session, "loaded_as_persistent", loaded)
        retained.clear()
