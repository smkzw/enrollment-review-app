"""幂等仓储：作用域 idempotency key + 请求哈希。

语义（PRD §幂等、并发与 stale）：

- 同 ``(scope, idempotency_key)`` 且请求哈希相同 -> 返回首次提交的同一结果；
- 同键不同哈希 -> 抛 :class:`IdempotencyConflict`，明确冲突，绝不静默复用；
- 记录与结果必须在同一个外层写事务中提交（由应用服务持有事务边界）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.publication import canonical_hash
from app.storage.codecs import utc_now
from app.storage.models import IdempotencyRecordRow

STATUS_COMMITTED = "committed"


@dataclass(frozen=True)
class IdempotencyRecord:
    scope: str
    idempotency_key: str
    request_sha256: str
    result_type: str
    result_id: str
    status: str
    created_at: datetime


class IdempotencyConflict(RuntimeError):
    """同幂等键提交了不同内容：明确冲突，调用方不得复用旧结果。"""

    code = "IDEMPOTENCY_CONFLICT"

    def __init__(
        self,
        *,
        scope: str,
        idempotency_key: str,
        existing_sha256: str,
        submitted_sha256: str,
    ) -> None:
        self.scope = scope
        self.idempotency_key = idempotency_key
        self.existing_sha256 = existing_sha256
        self.submitted_sha256 = submitted_sha256
        super().__init__(
            f"幂等键 {scope}:{idempotency_key} 已绑定不同请求内容"
            f"（已有 {existing_sha256}，提交 {submitted_sha256}）"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "scope": self.scope,
            "idempotency_key": self.idempotency_key,
            "existing_request_sha256": self.existing_sha256,
            "submitted_request_sha256": self.submitted_sha256,
        }


def request_hash(payload: object) -> str:
    """与领域一致的 canonical 请求哈希。"""
    return canonical_hash(payload)


def _to_record(row: IdempotencyRecordRow) -> IdempotencyRecord:
    return IdempotencyRecord(
        scope=row.scope,
        idempotency_key=row.idempotency_key,
        request_sha256=row.request_sha256,
        result_type=row.result_type,
        result_id=row.result_id,
        status=row.status,
        created_at=row.created_at,
    )


class IdempotencyRepository:
    """``(scope, idempotency_key)`` 唯一；同键同哈希返回原结果。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, scope: str, idempotency_key: str) -> IdempotencyRecord | None:
        row = (
            self.session.query(IdempotencyRecordRow)
            .filter(
                IdempotencyRecordRow.scope == scope,
                IdempotencyRecordRow.idempotency_key == idempotency_key,
            )
            .one_or_none()
        )
        return _to_record(row) if row is not None else None

    def resolve(
        self,
        *,
        scope: str,
        idempotency_key: str,
        submitted_hash: str,
        result_type: str,
        result_id: str,
    ) -> tuple[IdempotencyRecord, bool]:
        """返回 ``(record, created)``；同键同哈希复用，同键异哈希抛冲突。

        必须在与结果写入相同的外层事务中调用。并发重复插入（唯一约束）同样
        映射为 :class:`IdempotencyConflict`，并要求调用方以新事务重试。
        """
        existing = self.get(scope, idempotency_key)
        if existing is not None:
            if existing.request_sha256 != submitted_hash:
                raise IdempotencyConflict(
                    scope=scope,
                    idempotency_key=idempotency_key,
                    existing_sha256=existing.request_sha256,
                    submitted_sha256=submitted_hash,
                )
            return existing, False
        row = IdempotencyRecordRow(
            scope=scope,
            idempotency_key=idempotency_key,
            request_sha256=submitted_hash,
            result_type=result_type,
            result_id=result_id,
            status=STATUS_COMMITTED,
            created_at=utc_now(),
        )
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            message = str(exc.orig) if exc.orig is not None else str(exc)
            if "UNIQUE" in message.upper():
                committed = self.get(scope, idempotency_key)
                if committed is not None and committed.request_sha256 == submitted_hash:
                    return committed, False
                raise IdempotencyConflict(
                    scope=scope,
                    idempotency_key=idempotency_key,
                    existing_sha256=(
                        committed.request_sha256
                        if committed is not None
                        else "(并发提交记录暂不可读)"
                    ),
                    submitted_sha256=submitted_hash,
                ) from exc
            raise
        return _to_record(row), True
