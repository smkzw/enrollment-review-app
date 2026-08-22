from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ocr_page_cache_hash(
    *,
    source_sha256: str,
    page_number: int,
    ocr_profile_sha256: str,
    page_input_sha256: str,
    layout_parser_version: str | None,
    coordinate_transform_version: str,
) -> str:
    """Return the content-addressed identity of one OCR page computation.

    This identity belongs to the domain contract so both the pure adapter helper
    and ``OCRPage`` validation use the same canonical payload.  File names and
    timestamps are deliberately excluded.
    """
    return hashlib.sha256(
        canonical_hash(
            {
                "cache": "ocr_page_cache/v1",
                "source_sha256": source_sha256,
                "page_number": page_number,
                "ocr_profile_sha256": ocr_profile_sha256,
                "page_input_sha256": page_input_sha256,
                "layout_parser_version": layout_parser_version,
                "coordinate_transform_version": coordinate_transform_version,
            }
        ).encode("utf-8")
    ).hexdigest()


def evidence_snapshot_collection_hash(*, members: list[tuple[str, str]]) -> str:
    """Return the content identity of an evidence snapshot's active member set.

    Identity is over ``(logical_document_id, source_document_version_id)`` pairs
    so the same raw content referenced under different subjects or logical
    documents never collides. The computation is order-independent (members are
    sorted) and excludes file names and timestamps, so re-confirming the same
    member set yields the same hash — the basis for duplicate-set no-op.
    """
    payload = [
        {
            "member": "evidence_snapshot_member/v1",
            "logical_document_id": logical,
            "source_document_version_id": version,
        }
        for logical, version in sorted(members)
    ]
    return canonical_hash(payload)


def evidence_processing_manifest_hash(
    *,
    entries: list[tuple[str, int, str | None, str, str | None, str]],
) -> str:
    """Return the content identity of a basic evidence processing revision's
    ordered page manifest.

    Each entry is ``(source_document_version_id, page_number, original_frame,
    page_artifact_id, ocr_page_id, status)``. The computation is
    **order-preserving** (the manifest follows the user-confirmed document order,
    keeps each document's pages contiguous and ascending, and rejects duplicate
    pages), so any reordering, duplicated page, or swapped artifact/OCR identity
    changes the hash and is rejected on replay. File names and timestamps are
    deliberately excluded.
    """
    payload = [
        {
            "manifest_entry": "evidence_processing_revision_page/v1",
            "source_document_version_id": source,
            "page_number": page_number,
            "original_frame": original_frame,
            "page_artifact_id": page_artifact_id,
            "ocr_page_id": ocr_page_id,
            "status": status,
        }
        for (
            source,
            page_number,
            original_frame,
            page_artifact_id,
            ocr_page_id,
            status,
        ) in entries
    ]
    return canonical_hash(payload)


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


def _build_gate_owned_model[PublishedModel: BaseModel](
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
