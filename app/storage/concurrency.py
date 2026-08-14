"""乐观并发：expected-revision 更新与字段差异信封。

两层防护：

1. 应用服务显式执行 expected-revision 检查（本模块），冲突时抛
   :class:`StaleRevisionError`，携带当前 revision、提交 revision 与字段差异，
   供 API 输出中文冲突信封，绝不静默覆盖；
2. SQLAlchemy mapper versioning（可变根的 ``version_id_col``）兜底，检查与
   flush 之间被其他会话提交时以 ``StaleDataError`` 暴露，同样转换为
   :class:`StaleRevisionError`。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.storage.codecs import mirror_json, utc_now


@dataclass(frozen=True)
class FieldChange:
    """单个字段的并发编辑差异（current=库中现值，submitted=提交值）。"""

    current: Any
    submitted: Any

    def as_dict(self) -> dict[str, Any]:
        return {"current": self.current, "submitted": self.submitted}


class StaleRevisionError(RuntimeError):
    """expected-revision 不匹配：后提交者收到当前值与字段差异。"""

    code = "STALE_REVISION"

    def __init__(
        self,
        *,
        entity_type: str,
        entity_id: str,
        expected_revision: int,
        current_revision: int,
        field_diff: dict[str, FieldChange],
        current_record: BaseModel | None = None,
    ) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.expected_revision = expected_revision
        self.current_revision = current_revision
        self.field_diff = field_diff
        self.current_record = current_record
        changed = ", ".join(sorted(field_diff)) or "（无声明字段差异）"
        super().__init__(
            f"{entity_type} {entity_id} 版本冲突：提交 revision {expected_revision}，"
            f"当前 revision {current_revision}；差异字段：{changed}"
        )

    def as_dict(self) -> dict[str, Any]:
        """API 冲突信封的序列化形态（不含 SQL/堆栈/日志词）。"""
        envelope: dict[str, Any] = {
            "code": self.code,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "expected_revision": self.expected_revision,
            "current_revision": self.current_revision,
            "field_diff": {
                field: change.as_dict() for field, change in sorted(self.field_diff.items())
            },
        }
        if self.current_record is not None:
            envelope["current_record"] = self.current_record.model_dump(mode="json")
        return envelope


def compute_field_diff(
    current_contract: BaseModel,
    submitted_changes: dict[str, Any],
    mutable_fields: set[str],
) -> dict[str, FieldChange]:
    """计算当前合同与提交修改在声明可变字段上的差异（JSON 规范化比较）。"""
    current_payload = current_contract.model_dump(mode="json")
    field_diff: dict[str, FieldChange] = {}
    for field in sorted(mutable_fields):
        if field not in submitted_changes:
            continue
        current_value = current_payload.get(field)
        submitted_value = submitted_changes.get(field)
        if mirror_json(current_value) != mirror_json(submitted_value):
            field_diff[field] = FieldChange(current=current_value, submitted=submitted_value)
    return field_diff


def apply_revisioned_update(
    session: Session,
    record_cls: type,
    contract_type: type[BaseModel],
    pk_value: str,
    expected_revision: int,
    changes: dict[str, Any],
    *,
    column_builder,
    mutable_fields: set[str],
    entity_type: str,
    scope: dict[str, Any] | None = None,
) -> tuple[BaseModel, Any]:
    """通用可变根更新：revision 检查 -> 合同重建 -> 列重算 -> 写入。

    ``column_builder(payload, scope)`` 接收新合同的 JSON payload 与可选
    scope 派生列；version_id 由 ORM 自动递增；flush 时若被并发会话抢先提交，
    转换为带差异信封的 :class:`StaleRevisionError`。
    """
    from app.storage.codecs import decode_contract, encode_contract
    from app.storage.repositories import NotFoundError

    record = session.get(record_cls, pk_value)
    if record is None:
        raise NotFoundError(f"{entity_type} {pk_value} 不存在")
    current_contract = decode_contract(
        contract_type, record.payload_json, record.payload_sha256
    )
    checked_revision = record.revision
    if checked_revision != expected_revision:
        raise StaleRevisionError(
            entity_type=entity_type,
            entity_id=pk_value,
            expected_revision=expected_revision,
            current_revision=checked_revision,
            field_diff=compute_field_diff(current_contract, changes, mutable_fields),
            current_record=current_contract,
        )
    merged = {**current_contract.model_dump(mode="json"), **changes}
    new_contract = contract_type.model_validate(merged)
    # RevisionedModel 的 payload 必须与 version_id 即将递增后的列一致（+1），
    # 一次 flush 完成，避免二次 UPDATE 再次触发 version_id 递增。
    if "revision" in merged:
        final_contract = contract_type.model_validate(
            {**merged, "revision": checked_revision + 1}
        )
    else:
        final_contract = new_contract
    columns = column_builder(final_contract.model_dump(mode="json"), scope)
    for name, value in columns.items():
        setattr(record, name, value)
    record.payload_json, record.payload_sha256 = encode_contract(final_contract)
    record.updated_at = utc_now()
    try:
        session.flush()
    except StaleDataError as exc:
        session.rollback()
        current_row = session.get(record_cls, pk_value)
        if current_row is None:
            raise StaleRevisionError(
                entity_type=entity_type,
                entity_id=pk_value,
                expected_revision=expected_revision,
                current_revision=checked_revision,
                field_diff={},
                current_record=None,
            ) from exc
        actual_contract = decode_contract(
            contract_type,
            current_row.payload_json,
            current_row.payload_sha256,
        )
        raise StaleRevisionError(
            entity_type=entity_type,
            entity_id=pk_value,
            expected_revision=expected_revision,
            current_revision=current_row.revision,
            field_diff=compute_field_diff(actual_contract, changes, mutable_fields),
            current_record=actual_contract,
        ) from exc
    # 无 revision 字段的合同（如 EvidenceExpectation）以列作为并发令牌，payload 不变。
    return final_contract, record
