#!/usr/bin/env python3
"""Bind matrix source anchors to a frozen structure-unit manifest.

The resolver is deliberately source-identity neutral.  It never selects a
unit by source reference alone, and it never falls back to ordering, title
similarity, or a "best" candidate.  A match requires the frozen unit's source
reference (or an explicitly listed member reference) and a verbatim excerpt
contained in that unit.  Zero or multiple matches are hard errors.

This file is a research-artifact generator.  It does not read a protocol
document, infer clinical phase, or change claims_complete.  Phase and
disposition gaps are reported for human/parent-agent acceptance.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import json
import os
import tempfile
from typing import Any, Mapping, Sequence


class SourceClosureMappingError(ValueError):
    """A deterministic failure while binding an anchor to frozen source."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        row_id: str | None = None,
        anchor_id: str | None = None,
        source_ref: str | None = None,
        candidate_ids: Sequence[str] = (),
    ) -> None:
        self.code = code
        self.row_id = row_id
        self.anchor_id = anchor_id
        self.source_ref = source_ref
        self.candidate_ids = tuple(candidate_ids)
        context = ", ".join(
            value
            for value in (
                f"row={row_id}" if row_id else "",
                f"anchor={anchor_id}" if anchor_id else "",
                f"source_ref={source_ref}" if source_ref else "",
            )
            if value
        )
        suffix = f" ({context})" if context else ""
        super().__init__(f"{code}{suffix}: {message}")


def _as_nonempty_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceClosureMappingError("MANIFEST_FIELD_INVALID", f"{field} 必须是非空字符串")
    return value


def _unit_source_refs(unit: Mapping[str, Any]) -> tuple[str, ...]:
    canonical = _as_nonempty_string(unit.get("source_ref"), field="unit.source_ref")
    members = unit.get("member_source_refs", ())
    if members is None:
        members = ()
    if not isinstance(members, (list, tuple)):
        raise SourceClosureMappingError(
            "MANIFEST_FIELD_INVALID",
            "unit.member_source_refs 必须是数组",
        )
    refs = {canonical}
    for member in members:
        refs.add(_as_nonempty_string(member, field="unit.member_source_refs[]"))
    return tuple(sorted(refs))


def build_source_index(
    manifest_payload: Mapping[str, Any],
) -> tuple[dict[str, tuple[Mapping[str, Any], ...]], dict[str, Mapping[str, Any]]]:
    """Build indexes without collapsing colliding references.

    The values are tuples rather than one selected unit specifically so an
    ambiguous source reference remains observable to the caller.
    """

    units = manifest_payload.get("units")
    if not isinstance(units, list) or not units:
        raise SourceClosureMappingError("MANIFEST_EMPTY", "冻结全文清单 units 不能为空")

    by_ref: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_id: dict[str, Mapping[str, Any]] = {}
    for unit in units:
        if not isinstance(unit, Mapping):
            raise SourceClosureMappingError("MANIFEST_UNIT_INVALID", "冻结全文清单单元必须是对象")
        unit_id = _as_nonempty_string(unit.get("structure_unit_id"), field="unit.structure_unit_id")
        if unit_id in by_id:
            raise SourceClosureMappingError("MANIFEST_UNIT_DUPLICATE", f"结构单元身份重复：{unit_id}")
        _as_nonempty_string(unit.get("excerpt"), field="unit.excerpt")
        heading = unit.get("heading_path")
        if not isinstance(heading, list) or not heading or any(
            not isinstance(item, str) or not item.strip() for item in heading
        ):
            raise SourceClosureMappingError(
                "MANIFEST_FIELD_INVALID",
                f"结构单元标题路径无效：{unit_id}",
            )
        spans = unit.get("source_span_ids")
        if not isinstance(spans, list) or not spans or any(
            not isinstance(item, str) or not item.strip() for item in spans
        ):
            raise SourceClosureMappingError(
                "MANIFEST_FIELD_INVALID",
                f"结构单元来源片段无效：{unit_id}",
            )
        by_id[unit_id] = unit
        for source_ref in _unit_source_refs(unit):
            by_ref[source_ref].append(unit)
    return {key: tuple(value) for key, value in by_ref.items()}, by_id


def resolve_source_unit(
    anchor: Mapping[str, Any],
    by_ref: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    row_id: str | None = None,
) -> Mapping[str, Any]:
    """Resolve one anchor by exact source reference and excerpt containment."""

    source_ref = _as_nonempty_string(anchor.get("source_ref"), field="anchor.source_ref")
    excerpt = _as_nonempty_string(
        anchor.get("verbatim_excerpt"),
        field="anchor.verbatim_excerpt",
    )
    anchor_id = anchor.get("source_anchor_id")
    candidates = tuple(by_ref.get(source_ref, ()))
    matches = tuple(
        unit
        for unit in candidates
        if excerpt in str(unit.get("excerpt", ""))
    )
    candidate_ids = tuple(
        str(unit.get("structure_unit_id"))
        for unit in matches
        if unit.get("structure_unit_id")
    )
    if not matches:
        code = "SOURCE_UNIT_UNMATCHED" if candidates else "SOURCE_REF_UNKNOWN"
        raise SourceClosureMappingError(
            code,
            "冻结清单中不存在同时满足 source_ref 与逐字摘录的唯一结构单元",
            row_id=row_id,
            anchor_id=anchor_id if isinstance(anchor_id, str) else None,
            source_ref=source_ref,
            candidate_ids=tuple(
                str(unit.get("structure_unit_id"))
                for unit in candidates
                if unit.get("structure_unit_id")
            ),
        )
    if len(matches) != 1:
        raise SourceClosureMappingError(
            "SOURCE_UNIT_AMBIGUOUS",
            "source_ref 命中多个逐字摘录相同的冻结结构单元；禁止模糊择优",
            row_id=row_id,
            anchor_id=anchor_id if isinstance(anchor_id, str) else None,
            source_ref=source_ref,
            candidate_ids=candidate_ids,
        )
    return matches[0]


def _manifest_binding_fields(manifest: Mapping[str, Any]) -> dict[str, Any]:
    fields = {}
    for key in (
        "manifest_id",
        "snapshot_id",
        "protocol_version_id",
        "protocol_document_sha256",
    ):
        fields[key] = _as_nonempty_string(manifest.get(key), field=f"manifest.{key}")
    return fields


def _row_relation_audit(
    rows: Sequence[Mapping[str, Any]],
    *,
    external_row_ids: Sequence[str] = (),
) -> dict[str, Any]:
    row_ids = [str(row.get("matrix_row_id", "")) for row in rows]
    local_row_ids = set(row_ids)
    external_row_id_set = set(external_row_ids)
    row_id_set = local_row_ids.union(external_row_id_set)
    used_external_target_ids: set[str] = set()
    issues: list[dict[str, Any]] = []
    seen_unordered: set[tuple[str, str, str]] = set()
    relation_counts: Counter[str] = Counter()
    for row in rows:
        row_id = str(row.get("matrix_row_id", ""))
        row_relation_keys: set[tuple[str, str]] = set()
        relations = row.get("cross_source_relations", ())
        if not isinstance(relations, list):
            issues.append({"code": "RELATION_LIST_INVALID", "row_id": row_id})
            continue
        for relation in relations:
            if not isinstance(relation, Mapping):
                issues.append({"code": "RELATION_INVALID", "row_id": row_id})
                continue
            kind = str(relation.get("kind", ""))
            target_id = str(relation.get("target_row_id", ""))
            relation_counts[kind] += 1
            key = (kind, target_id)
            if key in row_relation_keys:
                issues.append(
                    {
                        "code": "RELATION_DUPLICATE",
                        "row_id": row_id,
                        "target_row_id": target_id,
                        "relation_kind": kind,
                    }
                )
            row_relation_keys.add(key)
            if target_id not in row_id_set:
                issues.append(
                    {
                        "code": "RELATION_TARGET_UNKNOWN",
                        "row_id": row_id,
                        "target_row_id": target_id,
                    }
                )
            elif target_id in external_row_id_set and target_id not in local_row_ids:
                used_external_target_ids.add(target_id)
            if target_id == row_id:
                issues.append({"code": "RELATION_SELF", "row_id": row_id})
            unordered = (kind, *sorted((row_id, target_id)))
            if unordered in seen_unordered:
                issues.append(
                    {
                        "code": "RELATION_DUPLICATE_UNORDERED",
                        "row_id": row_id,
                        "target_row_id": target_id,
                        "relation_kind": kind,
                    }
                )
            seen_unordered.add(unordered)
            if kind == "substantive_conflict" and not relation.get("resolution_zh"):
                issues.append(
                    {
                        "code": "UNRESOLVED_SUBSTANTIVE_CONFLICT",
                        "row_id": row_id,
                        "target_row_id": target_id,
                    }
                )
    identities = [str(row.get("source_identity", "")) for row in rows]
    duplicate_identities = sorted(
        identity for identity, count in Counter(identities).items() if identity and count > 1
    )
    for identity in duplicate_identities:
        issues.append({"code": "SOURCE_IDENTITY_DUPLICATE", "source_identity": identity})
    return {
        "accepted": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "relation_counts": dict(sorted(relation_counts.items())),
        "row_count": len(rows),
        "external_relation_target_count": len(used_external_target_ids),
    }


def _phase_audit(
    rows: Sequence[Mapping[str, Any]],
    units_by_id: Mapping[str, Mapping[str, Any]],
    selected_phase: str,
) -> dict[str, Any]:
    selected_scope = selected_phase
    unresolved_scopes = {"unknown", "mixed", "seamless_candidate"}
    issues: list[dict[str, Any]] = []
    row_scope_summary: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("matrix_row_id", ""))
        row_scopes: set[str] = set()
        unit_ids: list[str] = []
        for anchor in row.get("source_anchors", ()):
            unit_id = str(anchor.get("structure_unit_id", ""))
            unit_ids.append(unit_id)
            unit = units_by_id.get(unit_id)
            if unit is not None:
                row_scopes.update(str(scope) for scope in unit.get("phase_scopes", ()))
        disposition = str(row.get("phase_disposition", ""))
        row_issues: list[str] = []
        if row_scopes.intersection(unresolved_scopes):
            row_issues.append("PHASE_UNRESOLVED")
        if disposition == "cross_phase_shared" and "shared" not in row_scopes:
            row_issues.append("PHASE_SHARED_SOURCE_MISSING")
        if disposition == "selected_phase_applicable" and not (
            selected_scope in row_scopes or "shared" in row_scopes
        ):
            row_issues.append("PHASE_SELECTED_SOURCE_MISSING")
        if row_issues:
            for code in row_issues:
                issues.append(
                    {
                        "code": code,
                        "row_id": row_id,
                        "structure_unit_ids": unit_ids,
                        "phase_scopes": sorted(row_scopes),
                    }
                )
        row_scope_summary.append(
            {
                "row_id": row_id,
                "phase_disposition": disposition,
                "phase_scopes": sorted(row_scopes),
                "issues": row_issues,
            }
        )
    return {
        "accepted": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "rows": row_scope_summary,
    }


def _source_closure_audit(
    rows: Sequence[Mapping[str, Any]],
    units_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    anchor_count = 0
    mapped_unit_ids: set[str] = set()
    for row in rows:
        row_id = str(row.get("matrix_row_id", ""))
        orders: list[int] = []
        for anchor in row.get("source_anchors", ()):
            anchor_count += 1
            anchor_id = str(anchor.get("source_anchor_id", ""))
            unit_id = str(anchor.get("structure_unit_id", ""))
            unit = units_by_id.get(unit_id)
            if unit is None:
                issues.append({"code": "SOURCE_UNIT_UNKNOWN", "row_id": row_id, "anchor_id": anchor_id})
                continue
            mapped_unit_ids.add(unit_id)
            if anchor.get("source_ref") != unit.get("source_ref"):
                issues.append({"code": "SOURCE_REF_MISMATCH", "row_id": row_id, "anchor_id": anchor_id})
            if anchor.get("heading_path_zh") != unit.get("heading_path"):
                issues.append({"code": "SOURCE_HEADING_PATH_MISMATCH", "row_id": row_id, "anchor_id": anchor_id})
            anchor_spans = set(anchor.get("source_span_ids", ()))
            unit_spans = set(unit.get("source_span_ids", ()))
            if anchor_spans != unit_spans:
                issues.append({"code": "SOURCE_SPAN_CLOSURE_MISMATCH", "row_id": row_id, "anchor_id": anchor_id})
            if str(anchor.get("verbatim_excerpt", "")) not in str(unit.get("excerpt", "")):
                issues.append({"code": "VERBATIM_EXCERPT_NOT_FOUND", "row_id": row_id, "anchor_id": anchor_id})
            order = unit.get("source_order")
            if not isinstance(order, int):
                issues.append({"code": "SOURCE_ORDER_INVALID", "row_id": row_id, "anchor_id": anchor_id})
            else:
                orders.append(order)
        if orders != sorted(orders):
            issues.append({"code": "SOURCE_ANCHOR_ORDER_MISMATCH", "row_id": row_id})
    return {
        "accepted": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "anchor_count": anchor_count,
        "unique_frozen_unit_count": len(mapped_unit_ids),
    }


def map_matrix_payload(
    matrix_payload: Mapping[str, Any],
    manifest_payload: Mapping[str, Any],
    *,
    relation_target_payload: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a source-bound matrix copy and deterministic audit summary."""

    if not isinstance(matrix_payload, Mapping):
        raise SourceClosureMappingError("MATRIX_INVALID", "矩阵必须是对象")
    rows = matrix_payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise SourceClosureMappingError("MATRIX_EMPTY", "矩阵 rows 不能为空")
    manifest_fields = _manifest_binding_fields(manifest_payload)
    selected_phase = _as_nonempty_string(matrix_payload.get("selected_phase"), field="matrix.selected_phase")
    manifest_phase = _as_nonempty_string(manifest_payload.get("study_phase"), field="manifest.study_phase")
    if selected_phase != manifest_phase:
        raise SourceClosureMappingError(
            "STUDY_PHASE_MISMATCH",
            "矩阵选定期别与冻结清单不一致；映射器不替换期别",
        )
    by_ref, units_by_id = build_source_index(manifest_payload)
    output = json.loads(json.dumps(matrix_payload, ensure_ascii=False))
    output.update(
        {
            "coverage_manifest_id": manifest_fields["manifest_id"],
            "snapshot_id": manifest_fields["snapshot_id"],
            "protocol_version_id": manifest_fields["protocol_version_id"],
            "protocol_document_sha256": manifest_fields["protocol_document_sha256"],
        }
    )
    replacement_count = 0
    span_replacement_count = 0
    heading_rebinding_count = 0
    ref_canonicalization_count = 0
    for row in output["rows"]:
        if not isinstance(row, dict):
            raise SourceClosureMappingError("MATRIX_ROW_INVALID", "矩阵行必须是对象")
        row_id = str(row.get("matrix_row_id", ""))
        anchors = row.get("source_anchors")
        if not isinstance(anchors, list) or not anchors:
            raise SourceClosureMappingError("MATRIX_SOURCE_ANCHORS_EMPTY", "矩阵行来源锚点不能为空", row_id=row_id)
        for anchor in anchors:
            if not isinstance(anchor, dict):
                raise SourceClosureMappingError("MATRIX_ANCHOR_INVALID", "矩阵来源锚点必须是对象", row_id=row_id)
            old_id = anchor.get("structure_unit_id")
            old_spans = tuple(anchor.get("source_span_ids", ()))
            old_heading = anchor.get("heading_path_zh")
            old_ref = anchor.get("source_ref")
            unit = resolve_source_unit(anchor, by_ref, row_id=row_id)
            canonical_ref = unit["source_ref"]
            anchor["structure_unit_id"] = unit["structure_unit_id"]
            anchor["source_ref"] = canonical_ref
            anchor["heading_path_zh"] = list(unit["heading_path"])
            anchor["source_span_ids"] = list(unit["source_span_ids"])
            replacement_count += int(old_id != unit["structure_unit_id"])
            span_replacement_count += int(old_spans != tuple(anchor["source_span_ids"]))
            heading_rebinding_count += int(old_heading != anchor["heading_path_zh"])
            ref_canonicalization_count += int(old_ref != canonical_ref)

    source_audit = _source_closure_audit(output["rows"], units_by_id)
    external_row_ids: tuple[str, ...] = ()
    if relation_target_payload is not None:
        target_rows = relation_target_payload.get("rows")
        if not isinstance(target_rows, list):
            raise SourceClosureMappingError(
                "RELATION_TARGET_MATRIX_INVALID",
                "关系目标矩阵 rows 必须是数组",
            )
        external_row_ids = tuple(
            str(row.get("matrix_row_id"))
            for row in target_rows
            if isinstance(row, Mapping) and row.get("matrix_row_id")
        )
    relation_audit = _row_relation_audit(
        output["rows"],
        external_row_ids=external_row_ids,
    )
    phase_audit = _phase_audit(output["rows"], units_by_id, selected_phase)
    claims_complete = bool(output.get("claims_complete", False))
    manifest_complete = bool(manifest_payload.get("claims_full_coverage", False))
    disposition_count = len(manifest_payload.get("dispositions", ())) if isinstance(
        manifest_payload.get("dispositions", ()), list
    ) else 0
    full_claims_complete_allowed = bool(
        source_audit["accepted"]
        and relation_audit["accepted"]
        and phase_audit["accepted"]
        and manifest_complete
        and disposition_count > 0
    )
    if claims_complete and not full_claims_complete_allowed:
        raise SourceClosureMappingError(
            "CLAIMS_COMPLETE_UNSAFE",
            "输入矩阵声明完整，但冻结来源/期别/处置闭包尚未满足；拒绝降级或伪造绑定",
        )
    summary = {
        "schema_version": "phase5/control-matrix-source-closure/v1",
        "matrix_id": output.get("matrix_id"),
        "coverage_manifest_id": manifest_fields["manifest_id"],
        "snapshot_id": manifest_fields["snapshot_id"],
        "protocol_version_id": manifest_fields["protocol_version_id"],
        "protocol_document_sha256": manifest_fields["protocol_document_sha256"],
        "row_count": len(output["rows"]),
        "claims_complete_input": claims_complete,
        "claims_complete_output": bool(output.get("claims_complete", False)),
        "full_claims_complete_allowed": full_claims_complete_allowed,
        "mapping": {
            "source_identity_replacement_count": replacement_count,
            "source_span_replacement_count": span_replacement_count,
            "heading_rebinding_count": heading_rebinding_count,
            "source_ref_canonicalization_count": ref_canonicalization_count,
        },
        "source_closure": source_audit,
        "relation_closure": relation_audit,
        "phase_closure": phase_audit,
        "manifest_claims_full_coverage": manifest_complete,
        "manifest_disposition_count": disposition_count,
        "manual_clinical_acceptance_required": True,
        "clinical_acceptance_note": "映射器不替代人工期别、关系和临床语义验收；未决项必须保持阻断。",
    }
    return output, summary


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = handle.name
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--relation-target-matrix",
        type=Path,
        help="Optional enclosing matrix whose row identities close external relation targets.",
    )
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    relation_target = (
        json.loads(args.relation_target_matrix.read_text(encoding="utf-8"))
        if args.relation_target_matrix is not None
        else None
    )
    mapped, summary = map_matrix_payload(
        matrix,
        manifest,
        relation_target_payload=relation_target,
    )
    _write_json(args.output, mapped)
    _write_json(args.report, summary)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "report": str(args.report),
                "source_closure_accepted": summary["source_closure"]["accepted"],
                "relation_closure_accepted": summary["relation_closure"]["accepted"],
                "phase_closure_accepted": summary["phase_closure"]["accepted"],
                "full_claims_complete_allowed": summary["full_claims_complete_allowed"],
                "source_identity_replacement_count": summary["mapping"]["source_identity_replacement_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
