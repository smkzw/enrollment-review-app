"""Phase 5 representative-subject acceptance run packet exporter.

Read-only export that turns one isolated representative-subject run into a
machine-checkable verification packet. The only inputs are:

- an isolation root containing the run's SQLite database (standard V2 layout,
  ``enrollment-review-v2.sqlite3``) and optionally the isolated source copies;
- a content-hash input manifest produced by
  :mod:`tools.phase5_acceptance.input_manifest` (raw file paths + SHA-256).

The packet explicitly records the five acceptance anchors required by the
representative-subject harness:

1. ``isolation``            — isolation data root and database path;
2. ``source_fingerprints``  — read-only raw source paths + content hashes,
                              isolated-copy recheck, and blob<->manifest closure;
3. ``run_authority``        — frozen authority tuple, active episode pointers,
                              snapshot/complete-processing-revision identity,
                              and the normalization runs (prompt/model identity);
4. ``statistics``           — candidate / gate / published / expectation /
                              patient-profile statistics;
5. ``per_event_source_checks`` — one source-verification item per Profile item
                              (fact/event/exposure/conflict/expectation) with
                              every locator resolved to file + page + excerpt +
                              hashes as recorded by the run.

The exporter is generic: it never interprets disease, drug, score, date, or
project-number semantics, never writes to the database (opened ``mode=ro``),
never reads credential values, and never claims clinical acceptance. Structural
ledger evidence remains the job of :mod:`tools.phase5_acceptance.ledger`.

The database must not be mid-write while exporting: stop the V2 service first
so the SQLite WAL is checkpointed, otherwise the read-only open fails loudly
instead of silently returning stale rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from tools.phase5_acceptance.input_manifest import run_artifact_name_hint
except ImportError:  # direct-file execution without the repo root on sys.path
    from input_manifest import run_artifact_name_hint  # type: ignore[no-redef]

RUN_PACKET_SCHEMA_VERSION = "phase5.run_packet/v1"
DB_FILENAME = "enrollment-review-v2.sqlite3"
BLOB_DIRNAME = "blobs"
HASH_ALGORITHM = "sha256"

# Payload-bearing tables whose canonical JSON must hash to payload_sha256.
_PAYLOAD_TABLES = (
    "patient_profile_revisions_v2",
    "evidence_locator_artifacts",
    "clinical_facts_v2",
    "clinical_events_v2",
    "medication_exposures_v2",
    "clinical_conflict_groups_v2",
    "fact_normalization_runs",
)

# Primary-key column per table, shared by the payload sweep and lookups.
_PUBLISHED_ID_COLUMNS = {
    "clinical_facts_v2": "fact_id",
    "clinical_events_v2": "event_id",
    "medication_exposures_v2": "exposure_id",
    "clinical_conflict_groups_v2": "conflict_group_id",
    "patient_profile_revisions_v2": "patient_profile_revision_id",
    "evidence_locator_artifacts": "locator_id",
    "fact_normalization_runs": "run_id",
}

# Generic per-kind verification instructions. These are kind-level checklists
# only; no clinical, project, or protocol semantics may appear here.
VERIFICATION_INSTRUCTIONS: dict[str, tuple[str, ...]] = {
    "fact": (
        "对照定位原文摘录核对极性、被断言对象、规范值与单位是否与原件一致",
        "确认每个定位的页码、摘录与来源文本哈希属于同一原件版本",
    ),
    "event": (
        "对照定位原文摘录核对事件类型、起止范围、持续状态与记录时间",
        "确认事件引用的事实条目均出现在本数据包并已逐条核对",
    ),
    "exposure": (
        "对照定位原文摘录核对名称、剂量、频次、途径、起止范围与持续状态",
        "确认暴露引用的事实条目均出现在本数据包并已逐条核对",
    ),
    "conflict": (
        "并列核对各成员的来源定位，确认系统未自动择优或隐藏任何一方",
        "确认冲突组仍处于未解决状态且解决修订为 0",
    ),
    "expectation": (
        "对照资料实际情况核对覆盖状态与细分缺口类型是否如实",
        "已覆盖状态必须能回溯到本数据包中已核对的定位或事实",
    ),
}

# Generic Profile-item clinical fields copied verbatim into check items.
_CLINICAL_FIELD_WHITELIST = (
    "polarity",
    "asserted_object",
    "value",
    "unit",
    "start_range",
    "end_range",
    "duration_status",
    "event_type",
    "medication_name",
    "category",
    "indication",
    "dose",
    "frequency",
    "route",
    "fact_ids",
    "conflict_member_kind",
    "conflict_member_ids",
    "conflict_resolution_revision",
    "template_id",
    "expectation_status",
    "gap_type",
    "gap_detail",
    "provenance_followup",
    "provenance_reason",
    "requirement_ids",
)

_ENTITY_TABLE_BY_KIND = {
    "fact": ("clinical_facts_v2", "fact_id"),
    "event": ("clinical_events_v2", "event_id"),
    "exposure": ("medication_exposures_v2", "exposure_id"),
}


class RunPacketError(ValueError):
    """Contract or safety violation for the run packet exporter."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _open_read_only(database_path: Path) -> sqlite3.Connection:
    if not database_path.is_file():
        raise RunPacketError(f"isolated database not found: {database_path}")
    try:
        conn = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:  # pragma: no cover - platform dependent
        raise RunPacketError(
            f"cannot open isolated database read-only: {exc}; "
            "stop the V2 service so the WAL is checkpointed, then retry"
        ) from exc
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _require_tables(conn: sqlite3.Connection) -> list[str]:
    missing = [
        table
        for table in (
            "review_episodes",
            "source_blobs",
            "source_document_versions_v2",
            "evidence_snapshots_v2",
            "evidence_processing_revisions",
            "evidence_locator_artifacts",
            "processing_revision_locators",
            "processing_revision_corrections",
            "correction_records",
            "ocr_pages",
            "page_artifacts",
            "fact_corrections",
            "fact_evidence_locator_links",
            "fact_normalization_runs",
            "fact_normalization_candidates",
            "fact_gate_results",
            "fact_normalization_unresolved_items",
            "clinical_facts_v2",
            "clinical_events_v2",
            "medication_exposures_v2",
            "clinical_conflict_groups_v2",
            "evidence_expectations_v2",
            "patient_profile_revisions_v2",
        )
        if not _table_exists(conn, table)
    ]
    return missing


def _row(conn: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> Any:
    return conn.execute(sql, params).fetchone()


def _rows(conn: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> list[Any]:
    return conn.execute(sql, params).fetchall()


def _payload_obj(row: sqlite3.Row, *, table: str, row_id: str, gaps: list[dict]) -> Any:
    """Verify payload_json hashes to payload_sha256 and parse it."""
    payload_json = row["payload_json"] if "payload_json" in row.keys() else None
    payload_sha = row["payload_sha256"] if "payload_sha256" in row.keys() else None
    if payload_json is None or payload_sha is None:
        return None
    actual = hashlib.sha256(str(payload_json).encode("utf-8")).hexdigest()
    if actual != payload_sha:
        gaps.append(
            {
                "code": "payload_hash_mismatch",
                "detail": f"{table}:{row_id} payload_sha256 mismatch",
            }
        )
        return None
    return json.loads(payload_json)


# --------------------------------------------------------------------------- sections


def _resolve_episode(
    conn: sqlite3.Connection, review_episode_id: str | None
) -> sqlite3.Row:
    episodes = _rows(
        conn,
        "SELECT review_episode_id, project_id, subject_id, stage, study_phase,"
        " revision, rule_set_id, rule_set_revision, protocol_version_id,"
        " active_evidence_snapshot_id, active_evidence_processing_revision_id"
        " FROM review_episodes ORDER BY review_episode_id",
    )
    if not episodes:
        raise RunPacketError("no review episodes in isolated database")
    if review_episode_id is None:
        if len(episodes) != 1:
            found = [row["review_episode_id"] for row in episodes]
            raise RunPacketError(
                "isolated database holds multiple review episodes; "
                f"select one explicitly: {found}"
            )
        return episodes[0]
    for row in episodes:
        if row["review_episode_id"] == review_episode_id:
            return row
    found = [row["review_episode_id"] for row in episodes]
    raise RunPacketError(
        f"review episode {review_episode_id!r} not found; found: {found}"
    )


def _determine_authority(
    conn: sqlite3.Connection, episode: sqlite3.Row, gaps: list[dict]
) -> tuple[dict[str, Any], str]:
    """Frozen authority: latest succeeded Profile, else published rows, else pointers."""
    profile_row = _row(
        conn,
        "SELECT patient_profile_revision_id, revision, payload_json, payload_sha256,"
        " created_at FROM patient_profile_revisions_v2"
        " WHERE review_episode_id = ? AND status = 'succeeded'"
        " ORDER BY revision DESC LIMIT 1",
        (episode["review_episode_id"],),
    )
    if profile_row is not None:
        payload = _payload_obj(
            profile_row,
            table="patient_profile_revisions_v2",
            row_id=profile_row["patient_profile_revision_id"],
            gaps=gaps,
        )
        if payload is not None and isinstance(payload.get("authority"), dict):
            return dict(payload["authority"]), "patient_profile_revision"

    for table in ("clinical_facts_v2", "clinical_events_v2", "medication_exposures_v2"):
        id_column = _PUBLISHED_ID_COLUMNS[table]
        row = _row(
            conn,
            f"SELECT {id_column} AS entity_id, payload_json, payload_sha256 FROM"
            f" {table} WHERE review_episode_id = ?"
            " ORDER BY created_at DESC LIMIT 1",
            (episode["review_episode_id"],),
        )
        if row is not None:
            payload = _payload_obj(
                row, table=table, row_id=str(row["entity_id"]), gaps=gaps
            )
            if payload is not None and isinstance(payload.get("authority"), dict):
                return dict(payload["authority"]), "published_entities"

    if (
        episode["active_evidence_snapshot_id"] is None
        or episode["active_evidence_processing_revision_id"] is None
    ):
        gaps.append(
            {
                "code": "no_run_authority",
                "detail": (
                    "no succeeded profile, no published entities, and the episode "
                    "has no active evidence pointers; nothing to verify"
                ),
            }
        )
        return {}, "episode_active_pointers"
    return {
        "project_id": episode["project_id"],
        "subject_id": episode["subject_id"],
        "review_episode_id": episode["review_episode_id"],
        "episode_revision": episode["revision"],
        "protocol_version_id": episode["protocol_version_id"],
        "rule_set_id": episode["rule_set_id"],
        "rule_set_revision": episode["rule_set_revision"],
        "evidence_snapshot_v2_id": episode["active_evidence_snapshot_id"],
        "complete_processing_revision_id": episode[
            "active_evidence_processing_revision_id"
        ],
    }, "episode_active_pointers"


def _build_run_authority(
    conn: sqlite3.Connection,
    episode: sqlite3.Row,
    frozen: dict[str, Any],
    authority_source: str,
    gaps: list[dict],
) -> dict[str, Any]:
    frozen_snapshot_id = frozen.get("evidence_snapshot_v2_id")
    frozen_revision_id = frozen.get("complete_processing_revision_id")

    snapshot_payload: dict[str, Any] | None = None
    if frozen_snapshot_id:
        row = _row(
            conn,
            "SELECT evidence_snapshot_id, upload_mode, collection_sha256,"
            " prior_snapshot_id, payload_json, payload_sha256"
            " FROM evidence_snapshots_v2 WHERE evidence_snapshot_id = ?",
            (frozen_snapshot_id,),
        )
        if row is None:
            gaps.append(
                {
                    "code": "snapshot_missing",
                    "detail": f"frozen snapshot {frozen_snapshot_id} not in database",
                }
            )
        else:
            payload = _payload_obj(
                row, table="evidence_snapshots_v2", row_id=frozen_snapshot_id, gaps=gaps
            )
            snapshot_payload = {
                "evidence_snapshot_id": row["evidence_snapshot_id"],
                "upload_mode": row["upload_mode"],
                "collection_sha256": row["collection_sha256"],
                "prior_snapshot_id": row["prior_snapshot_id"],
                "member_count": len(payload.get("members", [])) if payload else None,
            }

    complete: dict[str, Any] | None = None
    if frozen_revision_id:
        row = _row(
            conn,
            "SELECT evidence_processing_revision_id, revision_kind,"
            " base_processing_revision_id, manifest_sha256, status,"
            " is_activatable, completion_manifest_sha256"
            " FROM evidence_processing_revisions WHERE evidence_processing_revision_id = ?",
            (frozen_revision_id,),
        )
        if row is None:
            gaps.append(
                {
                    "code": "processing_revision_missing",
                    "detail": (
                        f"frozen complete revision {frozen_revision_id} not in database"
                    ),
                }
            )
        else:
            complete = {
                "evidence_processing_revision_id": row["evidence_processing_revision_id"],
                "revision_kind": row["revision_kind"],
                "base_processing_revision_id": row["base_processing_revision_id"],
                "manifest_sha256": row["manifest_sha256"],
                "completion_manifest_sha256": row["completion_manifest_sha256"],
                "status": row["status"],
                "is_activatable": bool(row["is_activatable"]),
            }

    runs: list[dict[str, Any]] = []
    run_rows = _rows(
        conn,
        "SELECT r.run_id, r.status, r.prompt_version_id, r.model_config_id,"
        " r.input_scope_sha256, r.created_by, r.evidence_snapshot_v2_id,"
        " r.complete_processing_revision_id, r.episode_revision,"
        " p.node AS prompt_node, p.template_sha256 AS prompt_template_sha256,"
        " p.schema_version_id AS prompt_schema_version_id,"
        " m.provider AS model_provider, m.model AS model_name,"
        " m.reasoning_effort AS model_reasoning_effort"
        " FROM fact_normalization_runs r"
        " LEFT JOIN prompt_versions p ON p.prompt_version_id = r.prompt_version_id"
        " LEFT JOIN model_configs m ON m.model_config_id = r.model_config_id"
        " WHERE r.review_episode_id = ? ORDER BY r.run_id",
        (episode["review_episode_id"],),
    )
    if not run_rows:
        gaps.append(
            {
                "code": "no_normalization_run",
                "detail": (
                    "no fact normalization run recorded for the review episode; "
                    "candidates cannot be produced"
                ),
            }
        )
    for row in run_rows:
        runs.append(
            {
                "run_id": row["run_id"],
                "status": row["status"],
                "prompt_version_id": row["prompt_version_id"],
                "prompt_node": row["prompt_node"],
                "prompt_template_sha256": row["prompt_template_sha256"],
                "prompt_schema_version_id": row["prompt_schema_version_id"],
                "model_config_id": row["model_config_id"],
                "model_provider": row["model_provider"],
                "model_name": row["model_name"],
                "model_reasoning_effort": row["model_reasoning_effort"],
                "input_scope_sha256": row["input_scope_sha256"],
                "created_by": row["created_by"],
                "matches_frozen_authority": (
                    row["evidence_snapshot_v2_id"] == frozen_snapshot_id
                    and row["complete_processing_revision_id"] == frozen_revision_id
                    and row["episode_revision"] == frozen.get("episode_revision")
                ),
            }
        )

    pointers_match = (
        episode["active_evidence_snapshot_id"] == frozen_snapshot_id
        and episode["active_evidence_processing_revision_id"] == frozen_revision_id
        and episode["revision"] == frozen.get("episode_revision")
    )
    if not pointers_match:
        gaps.append(
            {
                "code": "authority_pointer_mismatch",
                "detail": (
                    "frozen authority differs from the episode active pointers; "
                    "the exported projection may be stale for the current node"
                ),
            }
        )
    if runs and not any(run["matches_frozen_authority"] for run in runs):
        gaps.append(
            {
                "code": "no_normalization_run_matching_authority",
                "detail": (
                    "no fact normalization run in the isolated database matches "
                    "the frozen authority; published entities cannot be traced "
                    "to a normalization run of this authority"
                ),
            }
        )

    return {
        "authority_source": authority_source,
        "frozen": frozen,
        "episode": {
            "review_episode_id": episode["review_episode_id"],
            "project_id": episode["project_id"],
            "subject_id": episode["subject_id"],
            "stage": episode["stage"],
            "study_phase": episode["study_phase"],
            "revision": episode["revision"],
            "rule_set_id": episode["rule_set_id"],
            "rule_set_revision": episode["rule_set_revision"],
            "protocol_version_id": episode["protocol_version_id"],
            "active_evidence_snapshot_id": episode["active_evidence_snapshot_id"],
            "active_evidence_processing_revision_id": episode[
                "active_evidence_processing_revision_id"
            ],
        },
        "authority_matches_active_pointers": pointers_match,
        "snapshot": snapshot_payload,
        "complete_processing_revision": complete,
        "normalization_runs": runs,
    }


def _authority_where(frozen: Mapping[str, Any]) -> tuple[str, list[Any]]:
    """WHERE fragment matching normalized authority columns of published tables."""
    clauses = []
    params: list[Any] = []
    for column, key in (
        ("project_id", "project_id"),
        ("subject_id", "subject_id"),
        ("review_episode_id", "review_episode_id"),
        ("episode_revision", "episode_revision"),
        ("evidence_snapshot_v2_id", "evidence_snapshot_v2_id"),
        ("complete_processing_revision_id", "complete_processing_revision_id"),
    ):
        if frozen.get(key) is not None:
            clauses.append(f"{column} = ?")
            params.append(frozen[key])
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _build_statistics(
    conn: sqlite3.Connection,
    episode: sqlite3.Row,
    frozen: Mapping[str, Any],
    profile_payload: Mapping[str, Any] | None,
    profile_meta: Mapping[str, Any] | None,
) -> dict[str, Any]:
    episode_id = episode["review_episode_id"]

    candidate_rows = _rows(
        conn,
        "SELECT candidate_kind, COUNT(*) AS n FROM fact_normalization_candidates c"
        " JOIN fact_normalization_runs r ON r.run_id = c.run_id"
        " WHERE r.review_episode_id = ? GROUP BY candidate_kind",
        (episode_id,),
    )
    by_kind = {row["candidate_kind"]: row["n"] for row in candidate_rows}

    unresolved = _row(
        conn,
        "SELECT COUNT(*) AS n FROM fact_normalization_unresolved_items u"
        " JOIN fact_normalization_runs r ON r.run_id = u.run_id"
        " WHERE r.review_episode_id = ?",
        (episode_id,),
    )["n"]

    gate_rows = _rows(
        conn,
        "SELECT outcome, COUNT(*) AS n FROM fact_gate_results g"
        " JOIN fact_normalization_runs r ON r.run_id = g.run_id"
        " WHERE r.review_episode_id = ? GROUP BY outcome",
        (episode_id,),
    )
    gate_by_outcome = {row["outcome"]: row["n"] for row in gate_rows}
    rejected_reasons = [
        reason
        for row in _rows(
            conn,
            "SELECT g.reasons_json FROM fact_gate_results g"
            " JOIN fact_normalization_runs r ON r.run_id = g.run_id"
            " WHERE r.review_episode_id = ? AND g.outcome != 'accepted'",
            (episode_id,),
        )
        for reason in (json.loads(row["reasons_json"] or "[]") or [])
    ][:20]

    where, params = _authority_where(frozen)
    published = {}
    for label, table in (
        ("facts", "clinical_facts_v2"),
        ("events", "clinical_events_v2"),
        ("exposures", "medication_exposures_v2"),
        ("conflict_groups", "clinical_conflict_groups_v2"),
    ):
        published[label] = (
            _row(conn, f"SELECT COUNT(*) AS n FROM {table}{where}", params)["n"]
            if where
            else 0
        )

    expectation_status: dict[str, int] = {}
    expectation_gap: dict[str, int] = {}
    if where:
        for row in _rows(
            conn,
            "SELECT status, COUNT(*) AS n FROM evidence_expectations_v2"
            f"{where} GROUP BY status",
            params,
        ):
            expectation_status[row["status"]] = row["n"]
        for row in _rows(
            conn,
            "SELECT gap_type, COUNT(*) AS n FROM evidence_expectations_v2"
            f"{where} AND gap_type IS NOT NULL GROUP BY gap_type",
            params,
        ):
            expectation_gap[row["gap_type"]] = row["n"]

    revision_count = _row(
        conn,
        "SELECT COUNT(*) AS n FROM patient_profile_revisions_v2 WHERE review_episode_id = ?",
        (episode_id,),
    )["n"]
    latest_profile = _row(
        conn,
        "SELECT patient_profile_revision_id, revision, status, generated_at"
        " FROM patient_profile_revisions_v2"
        " WHERE review_episode_id = ? ORDER BY revision DESC LIMIT 1",
        (episode_id,),
    )

    lane_counts: dict[str, int] = {}
    if profile_payload is not None:
        for section in profile_payload.get("lanes", []):
            lane = section.get("lane")
            if lane is not None:
                lane_counts[str(lane)] = len(section.get("items", []))

    return {
        "candidates": {
            "total": sum(by_kind.values()),
            "by_kind": by_kind,
        },
        "unresolved_items": unresolved,
        "gate_results": {
            "total": sum(gate_by_outcome.values()),
            "by_outcome": gate_by_outcome,
            "rejected_or_blocked_reasons_sample": rejected_reasons,
        },
        "published": published,
        "expectations": {
            "total": sum(expectation_status.values()),
            "by_status": expectation_status,
            "by_gap_type": expectation_gap,
        },
        "profile": {
            "revision_count": revision_count,
            "latest": (
                {
                    "patient_profile_revision_id": latest_profile[
                        "patient_profile_revision_id"
                    ],
                    "revision": latest_profile["revision"],
                    "status": latest_profile["status"],
                    "generated_at": latest_profile["generated_at"],
                    "pending_review_count": profile_payload.get("pending_review_count")
                    if profile_payload
                    else None,
                }
                if latest_profile is not None
                else None
            ),
            "succeeded_basis": dict(profile_meta) if profile_meta else None,
            "lane_item_counts": lane_counts,
        },
    }


def _build_documents(
    conn: sqlite3.Connection,
    episode: sqlite3.Row,
    manifest_entries_by_sha: Mapping[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Doc versions of this episode joined to manifest fingerprints by blob hash."""
    rows = _rows(
        conn,
        "SELECT v.source_document_version_id, v.logical_document_id, v.file_name,"
        " v.version_number, v.media_type, v.page_count, v.source_blob_sha256,"
        " b.byte_size FROM source_document_versions_v2 v"
        " JOIN source_blobs b ON b.sha256 = v.source_blob_sha256"
        " WHERE v.review_episode_id = ? ORDER BY v.source_document_version_id",
        (episode["review_episode_id"],),
    )
    documents = []
    consumed_shas: set[str] = set()
    for row in rows:
        sha = row["source_blob_sha256"]
        consumed_shas.add(sha)
        matches = manifest_entries_by_sha.get(sha, [])
        documents.append(
            {
                "source_document_version_id": row["source_document_version_id"],
                "logical_document_id": row["logical_document_id"],
                "file_name": row["file_name"],
                "version_number": row["version_number"],
                "media_type": row["media_type"],
                "page_count": row["page_count"],
                "blob_sha256": sha,
                "byte_size": row["byte_size"],
                "manifest_matches": [
                    {
                        "relative_path": entry["relative_path"],
                        "source_root": entry["source_root"],
                        "size_bytes": entry["size_bytes"],
                    }
                    for entry in matches
                ],
            }
        )
    return documents, sorted(consumed_shas)


def _build_source_fingerprints(
    manifest: Mapping[str, Any],
    *,
    isolation_root: Path,
    consumed_shas: Sequence[str],
    documents: Sequence[Mapping[str, Any]],
    gaps: list[dict],
) -> dict[str, Any]:
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise RunPacketError(
            "input manifest has no entries; the packet input must be raw file "
            "paths with content hashes from tools.phase5_acceptance.input_manifest"
        )
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for raw in entries:
        if not isinstance(raw, Mapping) or not raw.get("sha256"):
            raise RunPacketError("manifest entry missing sha256 content hash")
        if raw.get("decision") == "include":
            if not raw.get("relative_path"):
                raise RunPacketError(
                    "manifest entry missing relative_path; the packet input must "
                    "be raw file paths with content hashes"
                )
            included.append(
                {
                    "relative_path": raw["relative_path"],
                    "source_root": raw.get("source_root"),
                    "sha256": raw["sha256"],
                    "size_bytes": raw.get("size_bytes"),
                    "file_type": raw.get("file_type"),
                    "run_artifact": bool(raw.get("run_artifact")),
                    "run_artifact_reason": raw.get("run_artifact_reason"),
                }
            )
        else:
            excluded.append(
                {
                    "relative_path": raw["relative_path"],
                    "reason": raw.get("reason"),
                }
            )

    # Prior-run artifact scan: manifests produced before run-artifact recording
    # still get the name-based subset so legacy manifests cannot smuggle obvious
    # run outputs (databases, bytecode, transcripts) into the acceptance input.
    run_artifact_entries: list[dict[str, Any]] = []
    for entry in included:
        reason = entry["run_artifact_reason"]
        if not entry["run_artifact"] and reason is None:
            reason = run_artifact_name_hint(Path(entry["relative_path"]))
        if reason:
            run_artifact_entries.append(
                {
                    "relative_path": entry["relative_path"],
                    "reason": reason,
                }
            )
    if run_artifact_entries:
        sample = ", ".join(
            f"{item['relative_path']} ({item['reason']})"
            for item in run_artifact_entries[:5]
        )
        gaps.append(
            {
                "code": "manifest_contains_run_artifacts",
                "detail": (
                    f"{len(run_artifact_entries)} included manifest file(s) are "
                    f"obvious prior-run outputs: {sample}; the acceptance input "
                    "must be raw subject files only"
                ),
            }
        )

    by_sha: dict[str, list[dict[str, Any]]] = {}
    for entry in included:
        by_sha.setdefault(entry["sha256"], []).append(entry)

    # Blob closure: every consumed blob must match a fingerprinted raw source.
    matched_shas: set[str] = set()
    for document in documents:
        sha = document["blob_sha256"]
        if sha in by_sha:
            matched_shas.add(sha)
        else:
            gaps.append(
                {
                    "code": "source_not_fingerprinted",
                    "detail": (
                        f"document {document['source_document_version_id']} "
                        f"({document['file_name']}) consumed blob {sha} that is "
                        "absent from the input manifest; cross-case or stale-input "
                        "pollution cannot be ruled out"
                    ),
                }
            )
    unused = sorted(
        entry["relative_path"]
        for entry in included
        if entry["sha256"] not in matched_shas
        and entry["sha256"] not in set(consumed_shas)
    )

    # Manifest provenance gate: the packet only stands on a manifest whose
    # source immutability was verified and that planned isolated copies.
    immutability = manifest.get("source_immutability") or {}
    immutability_verified = immutability.get("verified") is True
    if not immutability_verified:
        gaps.append(
            {
                "code": "manifest_not_verified",
                "detail": (
                    "input manifest source_immutability.verified is not true; "
                    "the packet refuses to stand on unverified source fingerprints"
                ),
            }
        )

    copy_plan = manifest.get("copy_plan")
    if not isinstance(copy_plan, list) or not copy_plan:
        copy_plan = []
        gaps.append(
            {
                "code": "isolated_copies_absent",
                "detail": (
                    "input manifest has no copy plan; no isolated copy exists to "
                    "verify sources against"
                ),
            }
        )

    # Isolated-copy recheck: re-hash copies that live under the isolation root.
    recheck: dict[str, Any] | None = None
    if copy_plan:
        results: list[dict[str, Any]] = []
        ok_count = 0
        root_resolved = isolation_root.resolve()
        for item in copy_plan:
            dest = Path(str(item.get("destination_path", "")))
            record = {
                "relative_path": item.get("relative_path"),
                "destination_path": str(dest),
                "expected_sha256": item.get("sha256"),
            }
            try:
                inside = dest.resolve().is_relative_to(root_resolved)
            except ValueError:
                inside = False
            if not inside:
                record.update({"status": "outside_isolation_root"})
                results.append(record)
                gaps.append(
                    {
                        "code": "isolated_copy_outside_root",
                        "detail": (
                            f"isolated copy destination is outside the isolation "
                            f"root: {dest}"
                        ),
                    }
                )
                continue
            if not dest.is_file():
                record.update({"status": "missing"})
                gaps.append(
                    {
                        "code": "isolated_copy_missing",
                        "detail": f"isolated copy missing: {dest}",
                    }
                )
                results.append(record)
                continue
            actual = _sha256_file(dest)
            ok = actual == item.get("sha256")
            ok_count += 1 if ok else 0
            if not ok:
                gaps.append(
                    {
                        "code": "isolated_copy_hash_mismatch",
                        "detail": (
                            f"isolated copy drifted from manifest hash: {dest} "
                            f"(expected {item.get('sha256')}, found {actual})"
                        ),
                    }
                )
            record.update(
                {
                    "status": "ok" if ok else "hash_mismatch",
                    "actual_sha256": actual,
                }
            )
            results.append(record)
        recheck = {
            "checked": len(results),
            "verified_ok": ok_count,
            "results": results,
        }

    return {
        "manifest_schema_version": manifest.get("schema_version"),
        "manifest_label": manifest.get("label"),
        "hash_algorithm": HASH_ALGORITHM,
        "source_roots": list(manifest.get("source_roots") or []),
        "included_files": included,
        "excluded_files": excluded,
        "manifest_source_immutability_verified": immutability_verified,
        "manifest_copy_verification": manifest.get("copy_verification"),
        "isolated_copy_recheck": recheck,
        "run_artifact_entries": run_artifact_entries,
        "unused_manifest_files": unused,
    }


def _episode_ocr_pages(
    conn: sqlite3.Connection, episode_id: str
) -> dict[str, dict[str, Any]]:
    """OCR pages of this episode's documents, keyed by ocr_page_id."""
    rows = _rows(
        conn,
        "SELECT p.ocr_page_id, p.raw_text, p.raw_text_sha256, p.page_artifact_id,"
        " p.page_number FROM ocr_pages p"
        " JOIN page_artifacts a ON a.page_artifact_id = p.page_artifact_id"
        " JOIN source_document_versions_v2 v"
        "   ON v.source_document_version_id = a.source_document_version_id"
        " WHERE v.review_episode_id = ?",
        (episode_id,),
    )
    return {
        row["ocr_page_id"]: {
            "raw_text": row["raw_text"],
            "raw_text_sha256": row["raw_text_sha256"],
            "page_artifact_id": row["page_artifact_id"],
            "page_number": row["page_number"],
        }
        for row in rows
    }


def _revision_corrections(
    conn: sqlite3.Connection, revision_id: Any
) -> dict[str, list[dict[str, Any]]]:
    """Corrections selected by a complete processing revision, grouped by page.

    Mirrors the authoritative selection (the revision's frozen closure) without
    touching the application projection engine's write path.
    """
    if not revision_id:
        return {}
    rows = _rows(
        conn,
        "SELECT c.correction_id, c.ocr_page_id, c.raw_text_sha256,"
        " c.text_start, c.text_end, c.original_text, c.corrected_text"
        " FROM correction_records c"
        " JOIN processing_revision_corrections pc"
        "   ON pc.correction_id = c.correction_id"
        " WHERE pc.revision_id = ?"
        " ORDER BY c.ocr_page_id, c.text_start, c.text_end, c.correction_id",
        (revision_id,),
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["ocr_page_id"], []).append(dict(row))
    return grouped


def _project_effective_text(
    raw_text: str, corrections: Sequence[Mapping[str, Any]]
) -> tuple[str, str]:
    """Deterministic splice of anchored corrections over the immutable raw text.

    Same ordering and anchoring rules as the application's projection engine:
    corrections anchor the same raw text, apply at original offsets sorted by
    (start, end, id), and must actually change the text. Returns
    ``(effective_text, sha256)``; raises ValueError when the stored corrections
    cannot rebuild a projection (bad anchor, no-op, or overlap).
    """
    for item in corrections:
        if item["raw_text_sha256"] != _sha256_text(raw_text):
            raise ValueError("correction anchors a different raw_text_sha256")
        start, end = item["text_start"], item["text_end"]
        if not (0 <= start < end <= len(raw_text)):
            raise ValueError("correction range out of raw text bounds")
        if raw_text[start:end] != item["original_text"]:
            raise ValueError("correction original_text does not match raw slice")
        if item["corrected_text"] == item["original_text"]:
            raise ValueError("correction does not change the text")
    ordered = sorted(
        corrections,
        key=lambda item: (item["text_start"], item["text_end"], item["correction_id"]),
    )
    for previous, current in zip(ordered, ordered[1:]):
        prev_insert = previous["text_start"] == previous["text_end"]
        curr_insert = current["text_start"] == current["text_end"]
        if prev_insert and curr_insert:
            if previous["text_start"] == current["text_start"]:
                raise ValueError("two insertions at the same position")
        elif previous["text_start"] < current["text_end"] and (
            current["text_start"] < previous["text_end"]
        ):
            raise ValueError("overlapping correction ranges")
    parts: list[str] = []
    cursor = 0
    for item in ordered:
        parts.append(raw_text[cursor : item["text_start"]])
        parts.append(item["corrected_text"])
        cursor = item["text_end"]
    parts.append(raw_text[cursor:])
    effective = "".join(parts)
    return effective, _sha256_text(effective)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_locator_page_coherence(
    row: sqlite3.Row,
    *,
    pages_by_id: Mapping[str, Mapping[str, Any]],
    corrections_by_page: Mapping[str, Sequence[Mapping[str, Any]]],
    gaps: list[dict],
) -> None:
    """Verify raw_ocr/effective_text locators against the recorded OCR page.

    Mirrors the repository's identity semantics (read-only): source text hash
    must match the page's text layer, page binding must agree, and the excerpt
    must replay at its character range inside that text. ``native_text``
    locators are verified by the application's native-coordinate gate and are
    out of scope here.
    """
    layer = row["source_layer"]
    if layer not in ("raw_ocr", "effective_text"):
        return
    locator_id = row["locator_id"]
    ocr_page_id = row["ocr_page_id"]
    if not ocr_page_id or ocr_page_id not in pages_by_id:
        gaps.append(
            {
                "code": "locator_ocr_page_missing",
                "detail": (
                    f"{layer} locator {locator_id} has no recorded OCR page "
                    f"(ocr_page_id={ocr_page_id!r}) to verify its text against"
                ),
            }
        )
        return
    page = pages_by_id[ocr_page_id]
    if page["page_artifact_id"] != row["page_artifact_id"] or page[
        "page_number"
    ] != row["page_number"]:
        gaps.append(
            {
                "code": "locator_page_binding_mismatch",
                "detail": (
                    f"locator {locator_id} page binding disagrees with OCR page "
                    f"{ocr_page_id}"
                ),
            }
        )

    if layer == "raw_ocr":
        text = page["raw_text"]
        if row["source_text_sha256"] != page["raw_text_sha256"]:
            gaps.append(
                {
                    "code": "locator_source_text_hash_mismatch",
                    "detail": (
                        f"raw_ocr locator {locator_id} source_text_sha256 does "
                        f"not match OCR page {ocr_page_id} raw_text_sha256"
                    ),
                }
            )
    else:
        try:
            effective, effective_sha = _project_effective_text(
                page["raw_text"], list(corrections_by_page.get(ocr_page_id, ()))
            )
        except ValueError as exc:
            gaps.append(
                {
                    "code": "locator_projection_unrebuildable",
                    "detail": (
                        f"effective text for OCR page {ocr_page_id} cannot be "
                        f"rebuilt from the frozen revision's corrections: {exc}"
                    ),
                }
            )
            return
        text = effective
        if row["source_text_sha256"] != effective_sha:
            gaps.append(
                {
                    "code": "locator_source_text_hash_mismatch",
                    "detail": (
                        f"effective_text locator {locator_id} source_text_sha256 "
                        f"does not match the rebuilt projection of OCR page "
                        f"{ocr_page_id}"
                    ),
                }
            )
        if row["effective_text_sha256"] and row["effective_text_sha256"] != effective_sha:
            gaps.append(
                {
                    "code": "locator_source_text_hash_mismatch",
                    "detail": (
                        f"effective_text locator {locator_id} effective_text_sha256 "
                        f"does not match the rebuilt projection of OCR page "
                        f"{ocr_page_id}"
                    ),
                }
            )

    start, end = row["text_start"], row["text_end"]
    excerpt = row["excerpt"]
    if start is not None and end is not None:
        if not (0 <= start < end <= len(text)) or (
            excerpt is not None and text[start:end] != excerpt
        ):
            gaps.append(
                {
                    "code": "locator_excerpt_not_in_page_text",
                    "detail": (
                        f"locator {locator_id} excerpt/character range does not "
                        f"replay inside the recorded text of OCR page {ocr_page_id}"
                    ),
                }
            )
    elif excerpt:
        if excerpt not in text:
            gaps.append(
                {
                    "code": "locator_excerpt_not_in_page_text",
                    "detail": (
                        f"locator {locator_id} excerpt cannot be found inside the "
                        f"recorded text of OCR page {ocr_page_id}"
                    ),
                }
            )


def _locator_details(
    conn: sqlite3.Connection,
    locator_ids: Sequence[str],
    *,
    documents_by_id: Mapping[str, Mapping[str, Any]],
    frozen_revision_id: Any,
    pages_by_id: Mapping[str, Mapping[str, Any]],
    corrections_by_page: Mapping[str, Sequence[Mapping[str, Any]]],
    gaps: list[dict],
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    revision_locators: set[str] = set()
    if frozen_revision_id:
        revision_locators = {
            row["locator_id"]
            for row in _rows(
                conn,
                "SELECT locator_id FROM processing_revision_locators"
                " WHERE revision_id = ?",
                (frozen_revision_id,),
            )
        }
    for locator_id in sorted(set(locator_ids)):
        row = _row(
            conn,
            "SELECT locator_id, source_document_version_id, ocr_page_id,"
            " page_artifact_id, page_number, source_layer, precision,"
            " source_text_sha256, effective_text_sha256, excerpt, text_start,"
            " text_end, bbox_x0, bbox_y0, bbox_x1, bbox_y1, coordinate_space,"
            " sidecar_sha256, anchor_hash, authenticity, disambiguation,"
            " degradation_reason, processing_revision_id, payload_json,"
            " payload_sha256 FROM evidence_locator_artifacts WHERE locator_id = ?",
            (locator_id,),
        )
        if row is None:
            gaps.append(
                {
                    "code": "locator_missing_in_db",
                    "detail": f"locator {locator_id} referenced by the profile is absent",
                }
            )
            continue
        _payload_obj(
            row,
            table="evidence_locator_artifacts",
            row_id=locator_id,
            gaps=gaps,
        )
        document = documents_by_id.get(row["source_document_version_id"])
        if document is None:
            gaps.append(
                {
                    "code": "locator_document_out_of_scope",
                    "detail": (
                        f"locator {locator_id} points at document "
                        f"{row['source_document_version_id']} outside this episode"
                    ),
                }
            )
        if revision_locators and locator_id not in revision_locators:
            gaps.append(
                {
                    "code": "locator_not_in_processing_revision",
                    "detail": (
                        f"locator {locator_id} is not part of frozen complete "
                        f"processing revision {frozen_revision_id}"
                    ),
                }
            )
        _check_locator_page_coherence(
            row,
            pages_by_id=pages_by_id,
            corrections_by_page=corrections_by_page,
            gaps=gaps,
        )
        bbox = None
        if row["bbox_x0"] is not None:
            bbox = {
                "x0": row["bbox_x0"],
                "y0": row["bbox_y0"],
                "x1": row["bbox_x1"],
                "y1": row["bbox_y1"],
                "coordinate_space": row["coordinate_space"],
                "sidecar_sha256": row["sidecar_sha256"],
            }
        details.append(
            {
                "locator_id": locator_id,
                "source_document_version_id": row["source_document_version_id"],
                "ocr_page_id": row["ocr_page_id"],
                "file_name": document["file_name"] if document else None,
                "logical_document_id": document["logical_document_id"]
                if document
                else None,
                "manifest_relative_paths": [
                    match["relative_path"]
                    for match in (document or {}).get("manifest_matches", [])
                ],
                "page_number": row["page_number"],
                "source_layer": row["source_layer"],
                "precision": row["precision"],
                "excerpt": row["excerpt"],
                "text_start": row["text_start"],
                "text_end": row["text_end"],
                "bbox": bbox,
                "source_text_sha256": row["source_text_sha256"],
                "anchor_hash": row["anchor_hash"],
                "authenticity": row["authenticity"],
                "disambiguation": row["disambiguation"],
                "degradation_reason": row["degradation_reason"],
            }
        )
    return details


def _build_per_event_checks(
    conn: sqlite3.Connection,
    episode: sqlite3.Row,
    profile_payload: Mapping[str, Any],
    *,
    documents: Sequence[Mapping[str, Any]],
    frozen: Mapping[str, Any],
    pages_by_id: Mapping[str, Mapping[str, Any]],
    corrections_by_page: Mapping[str, Sequence[Mapping[str, Any]]],
    gaps: list[dict],
) -> list[dict[str, Any]]:
    documents_by_id = {document["source_document_version_id"]: document for document in documents}
    frozen_revision_id = frozen.get("complete_processing_revision_id")
    episode_id = episode["review_episode_id"]
    authority_where, authority_params = _authority_where(frozen)

    link_rows = _rows(
        conn,
        "SELECT entity_kind, entity_id, locator_id FROM fact_evidence_locator_links",
    )
    links_by_entity: dict[tuple[str, str], set[str]] = {}
    for row in link_rows:
        links_by_entity.setdefault(
            (row["entity_kind"], row["entity_id"]), set()
        ).add(row["locator_id"])

    # Authority-scoped published rows plus episode-wide ids: a profile item is
    # only supported when its entity was published under the frozen authority,
    # at the chain-head revision, and not superseded by a manual correction.
    published_rows: dict[str, dict[str, dict[str, Any]]] = {}
    episode_ids: dict[str, set[str]] = {}
    head_revision: dict[tuple[str, str], int] = {}
    for kind, (table, id_column) in _ENTITY_TABLE_BY_KIND.items():
        rows_by_id = {
            row[id_column]: {
                "revision": row["revision"],
                "stable_identity": row["stable_identity"],
            }
            for row in _rows(
                conn,
                f"SELECT {id_column}, stable_identity, revision FROM {table}"
                f"{authority_where}",
                authority_params,
            )
        }
        published_rows[kind] = rows_by_id
        episode_ids[kind] = {
            row[0]
            for row in _rows(
                conn,
                f"SELECT {id_column} FROM {table} WHERE review_episode_id = ?",
                (episode_id,),
            )
        }
    superseded_ids = {
        row["target_id"]
        for row in _rows(
            conn,
            "SELECT target_id FROM fact_corrections WHERE review_episode_id = ?",
            (episode_id,),
        )
    }
    for kind, rows_by_id in published_rows.items():
        for row_id, row in rows_by_id.items():
            if row_id in superseded_ids:
                continue
            key = (kind, row["stable_identity"])
            if row["revision"] > head_revision.get(key, 0):
                head_revision[key] = row["revision"]

    checks: list[dict[str, Any]] = []
    for section in profile_payload.get("lanes", []):
        lane = section.get("lane")
        for item in section.get("items", []):
            kind = str(item.get("kind"))
            source_id = str(item.get("source_id"))
            locator_ids = sorted(item.get("locator_ids") or [])

            entity_links = links_by_entity.get((kind, source_id))
            links_match: bool | None = None
            if entity_links is None:
                if locator_ids:
                    links_match = False
                    gaps.append(
                        {
                            "code": "entity_links_absent",
                            "detail": (
                                f"{kind} {source_id} carries locators but has no "
                                "published entity-locator link rows at all"
                            ),
                        }
                    )
            else:
                links_match = entity_links == set(locator_ids)
                if not links_match:
                    gaps.append(
                        {
                            "code": "entity_link_locator_mismatch",
                            "detail": (
                                f"{kind} {source_id}: profile locators {locator_ids} "
                                f"differ from published links {sorted(entity_links)}"
                            ),
                        }
                    )

            published_present: bool | None = None
            published_revision: int | None = None
            chain_head_revision: int | None = None
            if kind in _ENTITY_TABLE_BY_KIND:
                row = published_rows[kind].get(source_id)
                published_present = row is not None
                if row is not None:
                    published_present = True
                    published_revision = row["revision"]
                    chain_head_revision = head_revision.get(
                        (kind, row["stable_identity"])
                    )
                    if source_id in superseded_ids:
                        gaps.append(
                            {
                                "code": "stale_revision_in_profile",
                                "detail": (
                                    f"{kind} {source_id} is superseded by a manual "
                                    "correction but still shown in the profile"
                                ),
                            }
                        )
                    elif (
                        chain_head_revision is not None
                        and row["revision"] < chain_head_revision
                    ):
                        gaps.append(
                            {
                                "code": "stale_revision_in_profile",
                                "detail": (
                                    f"{kind} {source_id} shows revision "
                                    f"{row['revision']} below the chain head "
                                    f"{chain_head_revision} of its stable identity"
                                ),
                            }
                        )
                elif source_id in episode_ids[kind]:
                    gaps.append(
                        {
                            "code": "profile_item_authority_mismatch",
                            "detail": (
                                f"{kind} {source_id} exists in this episode only "
                                "under a different authority than the frozen one; "
                                "cross-snapshot or cross-node pollution is likely"
                            ),
                        }
                    )
                else:
                    gaps.append(
                        {
                            "code": "profile_item_without_published_row",
                            "detail": (
                                f"{kind} {source_id} shown in profile has no "
                                "published row in the isolated database"
                            ),
                        }
                    )

            clinical_fields = {
                field: item.get(field)
                for field in _CLINICAL_FIELD_WHITELIST
                if item.get(field) is not None
            }
            if not locator_ids and kind in (
                "fact",
                "event",
                "exposure",
                "conflict",
            ):
                gaps.append(
                    {
                        "code": "profile_item_without_locator",
                        "detail": (
                            f"{kind} {source_id} carries no source locator; "
                            "published entities must be source-locatable"
                        ),
                    }
                )
            checks.append(
                {
                    "item_id": item.get("item_id"),
                    "kind": kind,
                    "source_id": source_id,
                    "source_revision": item.get("source_revision"),
                    "lane": lane,
                    "title": item.get("title"),
                    "subtitle": item.get("subtitle"),
                    "record_time": item.get("record_time"),
                    "source_strength": item.get("source_strength"),
                    "clinical_fields": clinical_fields,
                    "locator_ids": locator_ids,
                    "locators": _locator_details(
                        conn,
                        locator_ids,
                        documents_by_id=documents_by_id,
                        frozen_revision_id=frozen_revision_id,
                        pages_by_id=pages_by_id,
                        corrections_by_page=corrections_by_page,
                        gaps=gaps,
                    ),
                    "entity_links_match": links_match,
                    "published_row_present": published_present,
                    "published_revision": published_revision,
                    "chain_head_revision": chain_head_revision,
                    "verification_instructions": list(
                        VERIFICATION_INSTRUCTIONS.get(kind, ())
                    ),
                }
            )
    return checks


# --------------------------------------------------------------------------- entry


def build_run_packet(
    isolation_root: Path | str,
    manifest: Mapping[str, Any],
    *,
    review_episode_id: str | None = None,
    database_path: Path | str | None = None,
    case_labels: Mapping[str, str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the representative-subject acceptance run packet (read-only)."""
    root = Path(isolation_root).expanduser().resolve(strict=False)
    if not root.is_dir():
        raise RunPacketError(f"isolation root is not a directory: {root}")
    db = (
        Path(database_path).expanduser().resolve(strict=False)
        if database_path is not None
        else root / DB_FILENAME
    )

    gaps: list[dict[str, str]] = []
    conn = _open_read_only(db)
    try:
        missing_tables = _require_tables(conn)
        if missing_tables:
            raise RunPacketError(
                f"isolated database is missing V2 tables {missing_tables}; "
                "not a Phase 5 isolated run database"
            )
        # Global payload integrity sweep over the tables the packet relies on.
        for table in _PAYLOAD_TABLES:
            if not _table_exists(conn, table):
                continue
            id_column = _PUBLISHED_ID_COLUMNS[table]
            for row in _rows(
                conn,
                f"SELECT {id_column} AS rid, payload_json, payload_sha256 FROM {table}",
            ):
                actual = hashlib.sha256(
                    str(row["payload_json"]).encode("utf-8")
                ).hexdigest()
                if actual != row["payload_sha256"]:
                    gaps.append(
                        {
                            "code": "payload_hash_mismatch",
                            "detail": f"{table}:{row['rid']} payload_sha256 mismatch",
                        }
                    )

        episode = _resolve_episode(conn, review_episode_id)
        frozen, authority_source = _determine_authority(conn, episode, gaps)
        run_authority = _build_run_authority(
            conn, episode, frozen, authority_source, gaps
        )

        profile_payload = None
        profile_meta = None
        profile_row = _row(
            conn,
            "SELECT patient_profile_revision_id, revision, generated_at,"
            " payload_json, payload_sha256 FROM patient_profile_revisions_v2"
            " WHERE review_episode_id = ? AND status = 'succeeded'"
            " ORDER BY revision DESC LIMIT 1",
            (episode["review_episode_id"],),
        )
        if profile_row is not None:
            payload = _payload_obj(
                profile_row,
                table="patient_profile_revisions_v2",
                row_id=profile_row["patient_profile_revision_id"],
                gaps=gaps,
            )
            if payload is not None:
                profile_payload = payload
                profile_meta = {
                    "patient_profile_revision_id": profile_row[
                        "patient_profile_revision_id"
                    ],
                    "revision": profile_row["revision"],
                    "generated_at": profile_row["generated_at"],
                }
        if profile_payload is None:
            gaps.append(
                {
                    "code": "no_succeeded_profile",
                    "detail": (
                        "no succeeded patient profile revision for the episode; "
                        "per-event source checks cannot be produced"
                    ),
                }
            )

        statistics = _build_statistics(
            conn, episode, frozen, profile_payload, profile_meta
        )

        manifest_by_sha: dict[str, list[dict[str, Any]]] = {}
        for raw in manifest.get("entries") or []:
            if isinstance(raw, Mapping) and raw.get("decision") == "include":
                manifest_by_sha.setdefault(str(raw["sha256"]), []).append(dict(raw))

        documents, consumed_shas = _build_documents(conn, episode, manifest_by_sha)
        pages_by_id = _episode_ocr_pages(conn, episode["review_episode_id"])
        corrections_by_page = _revision_corrections(
            conn, frozen.get("complete_processing_revision_id")
        )
        source_fingerprints = _build_source_fingerprints(
            manifest,
            isolation_root=root,
            consumed_shas=consumed_shas,
            documents=documents,
            gaps=gaps,
        )

        per_event_checks: list[dict[str, Any]] = []
        if profile_payload is not None:
            per_event_checks = _build_per_event_checks(
                conn,
                episode,
                profile_payload,
                documents=documents,
                frozen=frozen,
                pages_by_id=pages_by_id,
                corrections_by_page=corrections_by_page,
                gaps=gaps,
            )

        if frozen:
            authority_where, authority_params = _authority_where(frozen)
            if all(
                _row(
                    conn,
                    f"SELECT COUNT(*) AS n FROM {table}{authority_where}",
                    authority_params,
                )["n"]
                == 0
                for table in (
                    "clinical_facts_v2",
                    "clinical_events_v2",
                    "medication_exposures_v2",
                )
            ):
                gaps.append(
                    {
                        "code": "no_published_entities",
                        "detail": (
                            "the frozen authority has zero published facts, events and "
                            "exposures; an empty case is not a verifiable acceptance run"
                        ),
                    }
                )
    finally:
        conn.close()

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for gap in gaps:
        key = (gap["code"], gap["detail"])
        if key not in seen:
            seen.add(key)
            deduped.append(gap)
    gaps = deduped

    blocking_codes = {
        "payload_hash_mismatch",
        "source_not_fingerprinted",
        "manifest_not_verified",
        "isolated_copies_absent",
        "isolated_copy_outside_root",
        "isolated_copy_missing",
        "isolated_copy_hash_mismatch",
        "manifest_contains_run_artifacts",
        "locator_missing_in_db",
        "locator_document_out_of_scope",
        "locator_not_in_processing_revision",
        "locator_ocr_page_missing",
        "locator_page_binding_mismatch",
        "locator_source_text_hash_mismatch",
        "locator_excerpt_not_in_page_text",
        "locator_projection_unrebuildable",
        "entity_links_absent",
        "entity_link_locator_mismatch",
        "profile_item_without_published_row",
        "profile_item_authority_mismatch",
        "stale_revision_in_profile",
        "profile_item_without_locator",
        "authority_pointer_mismatch",
        "no_succeeded_profile",
        "no_published_entities",
        "no_run_authority",
        "no_normalization_run",
        "no_normalization_run_matching_authority",
        "snapshot_missing",
        "processing_revision_missing",
    }
    blocking = [gap for gap in gaps if gap["code"] in blocking_codes]

    return {
        "schema_version": RUN_PACKET_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now_iso(),
        "case_labels": dict(case_labels or {}),
        "clinical_acceptance": {
            "claimed": False,
            "note": (
                "本数据包只提供结构化核对材料，不构成医学验收结论；"
                "逐事件人工核对仍由人工完成"
            ),
        },
        "isolation": {
            "isolation_root": str(root),
            "database_path": str(db),
            "database_opened_read_only": True,
            "blob_directory": str(root / BLOB_DIRNAME),
        },
        "source_fingerprints": source_fingerprints,
        "run_authority": run_authority,
        "statistics": statistics,
        "documents": documents,
        "per_event_source_checks": per_event_checks,
        "verification_gaps": gaps,
        "packet_disposition": "blocked" if blocking else "verifiable",
        "blocking_gaps": blocking,
    }


def write_run_packet(packet: Mapping[str, Any], output_path: Path | str) -> Path:
    path = Path(output_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(packet, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path.resolve(strict=False)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export a representative-subject acceptance run packet from an "
            "isolated Phase 5 run. Read-only; never claims clinical acceptance."
        )
    )
    parser.add_argument(
        "--isolation-root",
        required=True,
        help="Isolated run data root containing enrollment-review-v2.sqlite3",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="JSON content-hash input manifest from tools.phase5_acceptance.input_manifest",
    )
    parser.add_argument(
        "--database",
        default=None,
        help="Optional explicit database path (default: <isolation-root>/"
        + DB_FILENAME
        + ")",
    )
    parser.add_argument(
        "--review-episode-id",
        default=None,
        help="Required when the isolated database holds multiple review episodes",
    )
    parser.add_argument(
        "--case-label",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Opaque case labels recorded verbatim (repeatable); no semantics applied",
    )
    parser.add_argument("--output", required=True, help="Output packet JSON path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    case_labels: dict[str, str] = {}
    for item in args.case_label:
        if "=" not in item:
            print(f"error: --case-label expects KEY=VALUE, got {item!r}", file=sys.stderr)
            return 2
        key, _, value = item.partition("=")
        case_labels[key] = value
    try:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        packet = build_run_packet(
            args.isolation_root,
            manifest,
            review_episode_id=args.review_episode_id,
            database_path=args.database,
            case_labels=case_labels,
        )
    except (RunPacketError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    output = write_run_packet(packet, args.output)
    summary = packet.get("statistics", {})
    print(
        json.dumps(
            {
                "ok": packet.get("packet_disposition") == "verifiable",
                "output": str(output),
                "disposition": packet.get("packet_disposition"),
                "review_episode_id": packet.get("run_authority", {})
                .get("episode", {})
                .get("review_episode_id"),
                "per_event_source_checks": len(
                    packet.get("per_event_source_checks", [])
                ),
                "published": summary.get("published"),
                "candidates": summary.get("candidates"),
                "blocking_gap_count": len(packet.get("blocking_gaps", [])),
            },
            ensure_ascii=False,
        )
    )
    return 0 if packet.get("packet_disposition") == "verifiable" else 2


if __name__ == "__main__":
    raise SystemExit(main())
