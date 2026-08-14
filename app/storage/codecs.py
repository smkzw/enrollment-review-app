"""Pydantic 合同 <-> canonical JSON/hash 编解码。

- 编码：``model_dump(mode="json")`` 的 canonical 序列化文本（sort_keys +
  紧凑分隔符）与 SHA-256 同时落库；哈希与 :func:`app.domain.publication.canonical_hash`
  的算法一致，可跨层核对。
- 解码：先校验 payload 哈希，再用对应合同类型严格还原（extra=forbid）。
  哈希不一致、JSON 损坏或 Pydantic 校验失败统一抛
  :class:`PersistedContractInvalid`，阻止发布，绝不返回空对象。
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

ContractT = TypeVar("ContractT", bound=BaseModel)


class PersistedContractInvalid(RuntimeError):
    """存储内容无法还原为已验证合同（哈希不一致或校验失败）。"""


def dump_payload(model: BaseModel) -> dict[str, Any]:
    """合同 JSON 形态（枚举->机器值、日期->ISO、嵌套字典/列表）。"""
    return model.model_dump(mode="json")


def encode_contract(model: BaseModel) -> tuple[str, str]:
    """编码合同为 (payload_json, payload_sha256)。"""
    text = json.dumps(
        dump_payload(model), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def encode_value(value: Any) -> tuple[str, str]:
    """编码任意 JSON 化值（如 RuleExpression）为 (json_text, sha256)。"""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_payload_sha256(payload_json: str, payload_sha256: str) -> dict[str, Any]:
    """校验 payload 哈希并解析 JSON；失败抛 :class:`PersistedContractInvalid`。"""
    actual = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    if actual != payload_sha256:
        raise PersistedContractInvalid(
            f"payload 哈希不一致（存储 {payload_sha256}，实际 {actual}），拒绝还原合同"
        )
    try:
        return json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise PersistedContractInvalid("payload JSON 无法解析，拒绝还原合同") from exc


def decode_contract(
    model_type: type[ContractT], payload_json: str, payload_sha256: str
) -> ContractT:
    """哈希校验 + 严格 Pydantic 还原；任何不一致都抛异常，不返回空对象。"""
    payload = verify_payload_sha256(payload_json, payload_sha256)
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise PersistedContractInvalid(
            f"payload 校验失败，拒绝还原 {model_type.__name__} 合同：{exc}"
        ) from exc


def utc_now() -> datetime:
    """当前 UTC 时间（naive，SQLite 列存储约定）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_naive(value: datetime | None) -> datetime | None:
    """带时区时间归一化为 UTC naive；naive 原样返回。"""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def parse_datetime_column(text: str) -> datetime:
    """把 payload 里的 ISO 文本解析为 UTC naive datetime 列值。"""
    normalized = text.replace("Z", "+00:00")
    return to_utc_naive(datetime.fromisoformat(normalized))


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def mirror_json(value: Any) -> str:
    """把列值/合同字段值规范化为可比较的 JSON 文本。"""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default
    )


def payload_get(payload: dict[str, Any], path: str) -> Any:
    """按点路径取 payload 字段（如 ``official_date.precision``）。"""
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            raise PersistedContractInvalid(f"payload 路径 {path} 不存在，拒绝还原合同")
        current = current.get(part)
    return current


def check_column_mirrors(
    entity_name: str, record: Any, payload: dict[str, Any], mirrors: dict[str, str]
) -> None:
    """交叉校验规范化列与 hash 验证过的 payload，防止两者漂移。"""
    for column_attr, payload_path in mirrors.items():
        column_value = getattr(record, column_attr)
        payload_value = payload_get(payload, payload_path)
        if mirror_json(column_value) != mirror_json(payload_value):
            raise PersistedContractInvalid(
                f"{entity_name} 列 {column_attr} 与已验证 payload 不一致，拒绝还原合同"
            )
