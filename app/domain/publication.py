from __future__ import annotations

import hashlib
import json
from typing import Any, TypeVar

from pydantic import BaseModel


PublishedModel = TypeVar("PublishedModel", bound=BaseModel)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def publication_fingerprint(
    *,
    entity_type: str,
    gate_result_id: str,
    payload: dict[str, Any],
) -> str:
    return canonical_hash(
        {
            "publication_contract": "deterministic_gate/v1",
            "entity_type": entity_type,
            "gate_result_id": gate_result_id,
            "payload": payload,
        }
    )


def _build_gate_owned_model(
    model_type: type[PublishedModel],
    *,
    entity_type: str,
    gate_result_id: str,
    data: dict[str, Any],
) -> PublishedModel:
    draft = model_type.model_construct(
        **data,
        gate_result_id=gate_result_id,
        publication_fingerprint="0" * 64,
    )
    payload = draft.model_dump(mode="json", exclude={"publication_fingerprint"})
    fingerprint = publication_fingerprint(
        entity_type=entity_type,
        gate_result_id=gate_result_id,
        payload=payload,
    )
    return model_type.model_validate(
        {
            **data,
            "gate_result_id": gate_result_id,
            "publication_fingerprint": fingerprint,
        }
    )
