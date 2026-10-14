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
from app.domain.contracts.protocol_drafts import ReviewScopeProposal
from app.domain.publication import canonical_hash
from app.protocols.docx_structure import StructureBlock, native_source_text
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


def load_scope_structure(snapshot: ProtocolExtractionSnapshot, data_paths: DataPaths) -> list[StructureBlock]:
    path = data_paths.boundary.require_v2_target(data_paths.blobs_dir / snapshot.content_storage_ref)
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != snapshot.content_sha256:
        raise ValueError("保存的方案结构内容已变化，不能继续使用。")
    return [StructureBlock.model_validate(item) for item in json.loads(raw)]


def validate_scope_proposal(proposal: ReviewScopeProposal, view: dict,
                            source: ProtocolDeconstructionInput, spans: list[ProtocolSourceSpan],
                            blocks: list[StructureBlock]) -> None:
    if proposal.scope_content_hash != view["scope_content_hash"]:
        raise ValueError("方案范围已变化，请重新核对后保存。")
    optional = {item["candidate_key"] for item in view["candidates"]
                if item["scope_kind"] in {"referenced_source", "medication_section"}}
    included = set(proposal.included_candidate_keys)
    excluded = {item.candidate_key for item in proposal.exclusions}
    if included | excluded != optional or included & excluded:
        raise ValueError("每处补充范围都需保留，或说明移除理由；不能改动固定入排标准与必做项目。")
    records = {item["source_span_id"]: item for item in view["source_records"]}
    for candidate in view["candidates"]:
        if candidate["candidate_key"] in included and (not candidate["source_span_ids"] or any(
            span_id not in records or records[span_id]["identity_status"] != "ok"
            for span_id in candidate["source_span_ids"]
        )):
            raise ValueError("所选章节有未核清的来源位置，尚不能保存为有效选择。")
    codes = {item.official_code for item in source.parent_rule_catalog.items}
    diagnostics = {item["diagnostic_key"]: item for item in view["diagnostics"]}
    for addition in proposal.additions:
        if set(addition.official_codes) - codes:
            raise ValueError("新增范围关联了本版方案不存在的入排条款。")
        for key in addition.resolves_references:
            diagnostic = diagnostics.get(key)
            if (diagnostic is None or diagnostic["kind"] not in {"reference_unresolved", "reference_ambiguous"}
                    or not set(diagnostic["related_official_codes"]) <= set(addition.official_codes)):
                raise ValueError("指定原文与本次待定位引用或对应条款不一致。")
        rows = scope_addition_sources(addition.source_span_ids, source, spans, blocks)
        if not any(row["raw_text"].strip() for row in rows):
            raise ValueError("新增范围没有可读原文。")


def scope_addition_sources(ids, source, spans, blocks) -> list[dict]:
    by_id = {span.source_span_id: span for span in spans}
    by_ref = {block.source_ref: block for block in blocks}
    rows = []
    for span_id in dict.fromkeys(ids):
        span = by_id.get(span_id)
        block = by_ref.get(span.source_ref) if span else None
        if (span is None or block is None or span.snapshot_id != source.extraction_snapshot_id
                or span.block_order != block.block_order or span.document_part != block.document_part
                or span.section_index != block.section_index or span.table_path != block.table_path
                or (span.excerpt and span.excerpt not in native_source_text(block, by_ref))):
            raise ValueError("新增范围的原文、位置或方案版本不能核实。")
        rows.append({"source_span_id": span_id, "raw_text": native_source_text(block, by_ref),
                     "render_page": span.render_page, "identity_status": "ok"})
    return rows


def review_scope_view(
    *, source: ProtocolDeconstructionInput, spans: list[ProtocolSourceSpan],
    snapshot: ProtocolExtractionSnapshot, data_paths: DataPaths, additional_ids=(),
) -> dict:
    if (snapshot.snapshot_id != source.extraction_snapshot_id
            or snapshot.source_sha256 != source.protocol_file_sha256
            or snapshot.status != ExtractionStatus.COMPLETED):
        raise ValueError("审核范围与方案结构身份不一致。")
    blocks = load_scope_structure(snapshot, data_paths)
    discovery = discover_review_scope(source_input=source, blocks=blocks, source_spans=spans)
    payload = asdict(discovery)
    by_id = {span.source_span_id: span for span in spans}
    for candidate in payload["candidates"]:
        candidate["candidate_key"] = canonical_hash(candidate)
    for diagnostic in payload["diagnostics"]:
        diagnostic["diagnostic_key"] = canonical_hash(diagnostic)
    for record in payload["source_records"]:
        span = by_id.get(record["source_span_id"])
        record["render_page"] = span.render_page if span else None
    return {
        "protocol_version_id": source.protocol_version_id,
        "snapshot_id": source.extraction_snapshot_id,
        "structure_sha256": snapshot.content_sha256,
        "scope_content_hash": canonical_hash(payload),
        "additional_source_records": scope_addition_sources(additional_ids, source, spans, blocks),
        **payload,
    }
