"""Read scope proposals from the exact preserved native extraction, without reruns."""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.agent_io import ProtocolDeconstructionInput
from app.domain.contracts.enums import ExtractionStatus
from app.domain.contracts.protocol_ingestion import ProtocolExtractionSnapshot, ProtocolSourceSpan
from app.domain.publication import canonical_hash
from app.protocols.docx_structure import StructureBlock
from app.protocols.review_scope import discover_review_scope
from app.storage.codecs import verify_payload_sha256
from app.storage.config import DataPaths
from app.storage.models import JobCheckpointRecord


def scope_source_snapshot(
    session: Session, source: ProtocolDeconstructionInput, current: dict | None,
) -> ProtocolExtractionSnapshot:
    """Re-deconstruction may preserve source identity in the original job only."""
    candidates = [ProtocolExtractionSnapshot.model_validate(current)] if current is not None else []
    if not candidates:
        rows = session.scalars(select(JobCheckpointRecord).where(
            JobCheckpointRecord.step_id == "extract_structure",
            JobCheckpointRecord.payload_json.contains(source.extraction_snapshot_id),
        ))
        for row in rows:
            payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
            value = payload.get("extraction_snapshot")
            if isinstance(value, dict) and value.get("snapshot_id") == source.extraction_snapshot_id:
                candidates.append(ProtocolExtractionSnapshot.model_validate(value))
    if not candidates:
        raise ValueError("没有找到本版方案保存的原生结构，不能推断审核范围。")
    identities = {canonical_hash(item.model_dump(mode="json")) for item in candidates}
    if len(identities) != 1:
        raise ValueError("同一方案结构身份对应不同内容，需核对保存的来源。")
    snapshot = candidates[0]
    if (snapshot.snapshot_id != source.extraction_snapshot_id
            or snapshot.source_sha256 != source.protocol_file_sha256
            or snapshot.status != ExtractionStatus.COMPLETED):
        raise ValueError("保存的方案结构与当前方案版本不一致。")
    return snapshot


def review_scope_view(
    *, source: ProtocolDeconstructionInput, spans: list[ProtocolSourceSpan],
    snapshot: ProtocolExtractionSnapshot, data_paths: DataPaths,
) -> dict:
    if (snapshot.snapshot_id != source.extraction_snapshot_id
            or snapshot.source_sha256 != source.protocol_file_sha256
            or snapshot.status != ExtractionStatus.COMPLETED):
        raise ValueError("审核范围与方案结构身份不一致。")
    path = data_paths.boundary.require_v2_target(data_paths.blobs_dir / snapshot.content_storage_ref)
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != snapshot.content_sha256:
        raise ValueError("保存的方案结构内容已变化，不能继续使用。")
    blocks = [StructureBlock.model_validate(item) for item in json.loads(raw)]
    discovery = discover_review_scope(source_input=source, blocks=blocks, source_spans=spans)
    payload = asdict(discovery)
    by_id = {span.source_span_id: span for span in spans}
    for candidate in payload["candidates"]:
        candidate["candidate_key"] = canonical_hash(candidate)
    for record in payload["source_records"]:
        span = by_id.get(record["source_span_id"])
        record["render_page"] = span.render_page if span else None
    return {
        "protocol_version_id": source.protocol_version_id,
        "snapshot_id": source.extraction_snapshot_id,
        "structure_sha256": snapshot.content_sha256,
        "scope_content_hash": canonical_hash(payload),
        **payload,
    }
