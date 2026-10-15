"""幂等仓储：同键同内容复用同一结果，同键不同内容明确冲突。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.domain.publication import canonical_hash
from app.storage.idempotency import (
    IdempotencyConflict,
    IdempotencyRepository,
    request_hash,
)


def test_same_key_same_hash_returns_single_record(session) -> None:
    repo = IdempotencyRepository(session)
    payload = {"job": "ingest", "project_id": "p1", "document_ids": ["d1", "d2"]}
    digest = request_hash(payload)
    first, created = repo.resolve(
        scope="job:create",
        idempotency_key="ingest:p1:v1",
        submitted_hash=digest,
        result_type="job",
        result_id="job-1",
    )
    assert created is True
    second, created_again = repo.resolve(
        scope="job:create",
        idempotency_key="ingest:p1:v1",
        submitted_hash=digest,
        result_type="job",
        result_id="job-1",
    )
    assert created_again is False
    assert second.result_id == first.result_id == "job-1"
    session.commit()
    rows = session.query(__import__("app.storage.models", fromlist=["IdempotencyRecordRow"]).IdempotencyRecordRow).all()
    assert len(rows) == 1


def test_same_key_different_hash_is_conflict(session) -> None:
    repo = IdempotencyRepository(session)
    digest_a = request_hash({"document_ids": ["d1"]})
    digest_b = request_hash({"document_ids": ["d2"]})
    repo.resolve(
        scope="document:ingest",
        idempotency_key="doc:v1",
        submitted_hash=digest_a,
        result_type="document",
        result_id="document-1",
    )
    with pytest.raises(IdempotencyConflict) as caught:
        repo.resolve(
            scope="document:ingest",
            idempotency_key="doc:v1",
            submitted_hash=digest_b,
            result_type="document",
            result_id="document-2",
        )
    assert caught.value.code == "IDEMPOTENCY_CONFLICT"
    assert caught.value.existing_sha256 == digest_a
    assert caught.value.submitted_sha256 == digest_b
    # 冲突不产生第二条记录
    session.commit()
    rows = session.query(__import__("app.storage.models", fromlist=["IdempotencyRecordRow"]).IdempotencyRecordRow).all()
    assert len(rows) == 1


def test_same_key_in_different_scopes_are_independent(session) -> None:
    repo = IdempotencyRepository(session)
    digest = request_hash({"x": 1})
    repo.resolve(scope="job:create", idempotency_key="k1", submitted_hash=digest, result_type="job", result_id="job-1")
    repo.resolve(scope="action:create", idempotency_key="k1", submitted_hash=digest, result_type="action", result_id="action-1")
    session.commit()
    assert repo.get("job:create", "k1").result_id == "job-1"
    assert repo.get("action:create", "k1").result_id == "action-1"
    assert repo.get("missing", "k1") is None


def test_request_hash_matches_domain_canonical_hash(session) -> None:
    payload = {"a": [1, 2], "b": {"c": "中文"}}
    assert request_hash(payload) == canonical_hash(payload)


def test_duplicate_scope_key_violates_unique_constraint(session) -> None:
    """直接绕过仓储插入同键记录也会被唯一约束拒绝。"""
    from app.storage.models import IdempotencyRecordRow

    session.add(
        IdempotencyRecordRow(
            scope="s",
            idempotency_key="k",
            request_sha256="a" * 64,
            result_type="t",
            result_id="r1",
            status="committed",
            created_at=__import__("datetime").datetime(2026, 8, 14),
        )
    )
    session.add(
        IdempotencyRecordRow(
            scope="s",
            idempotency_key="k",
            request_sha256="b" * 64,
            result_type="t",
            result_id="r2",
            status="committed",
            created_at=__import__("datetime").datetime(2026, 8, 14),
        )
    )
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError, match="UNIQUE"):
        session.commit()


def test_unique_race_with_same_payload_reuses_committed_result(session, monkeypatch) -> None:
    """唯一键竞态若内容相同，应复用赢家结果而不是误报冲突。"""
    from app.storage.models import IdempotencyRecordRow

    digest = request_hash({"document_ids": ["d1"]})
    session.add(
        IdempotencyRecordRow(
            scope="document:ingest",
            idempotency_key="race-key",
            request_sha256=digest,
            result_type="document",
            result_id="document-winner",
            status="committed",
            created_at=__import__("datetime").datetime(2026, 8, 14),
        )
    )
    session.commit()

    repo = IdempotencyRepository(session)
    real_get = repo.get
    calls = 0

    def miss_once(scope: str, key: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return real_get(scope, key)

    monkeypatch.setattr(repo, "get", miss_once)
    record, created = repo.resolve(
        scope="document:ingest",
        idempotency_key="race-key",
        submitted_hash=digest,
        result_type="document",
        result_id="document-loser",
    )
    assert created is False
    assert record.result_id == "document-winner"


def test_concurrent_same_key_same_payload_has_one_winner_without_errors(session_factory) -> None:
    """真实并发争抢同一键：只有一个赢家，其余复用且不破坏各自事务。"""
    digest = request_hash({"document_ids": ["d1"]})

    def submit(index: int) -> tuple[str, bool]:
        with session_factory() as current:
            with current.begin():
                record, created = IdempotencyRepository(current).resolve(
                    scope="document:ingest",
                    idempotency_key="concurrent-key",
                    submitted_hash=digest,
                    result_type="document",
                    result_id=f"document-{index}",
                )
                return record.result_id, created

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(8)))

    assert sum(created for _result_id, created in results) == 1
    assert len({result_id for result_id, _created in results}) == 1
