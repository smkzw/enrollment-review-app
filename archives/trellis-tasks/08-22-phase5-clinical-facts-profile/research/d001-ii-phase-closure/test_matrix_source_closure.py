from __future__ import annotations

import json
from pathlib import Path

import pytest

from map_matrix_source_closure import (
    SourceClosureMappingError,
    build_source_index,
    map_matrix_payload,
    resolve_source_unit,
)


ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "coverage_manifest.json"
CROSS_SECTION_PATH = ROOT.parent / "d001-ii-cross-section-controls.json"
MERGED_MATRIX_PATH = ROOT.parent / "d001-ii-control-matrix.json"


def _payloads() -> tuple[dict, dict]:
    return (
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8")),
        json.loads(CROSS_SECTION_PATH.read_text(encoding="utf-8")),
    )


def test_mapping_closes_real_source_identity_without_phase_promotion() -> None:
    manifest, matrix = _payloads()
    relation_targets = json.loads(MERGED_MATRIX_PATH.read_text(encoding="utf-8"))
    mapped, summary = map_matrix_payload(
        matrix,
        manifest,
        relation_target_payload=relation_targets,
    )

    assert summary["source_closure"]["accepted"] is True
    assert summary["relation_closure"]["accepted"] is True
    assert summary["relation_closure"]["external_relation_target_count"] == 16
    assert summary["phase_closure"]["accepted"] is False
    assert summary["full_claims_complete_allowed"] is False
    assert summary["manual_clinical_acceptance_required"] is True
    assert mapped["claims_complete"] is False
    assert mapped["coverage_manifest_id"] == manifest["manifest_id"]
    assert mapped["snapshot_id"] == manifest["snapshot_id"]
    assert mapped["protocol_version_id"] == manifest["protocol_version_id"]
    assert mapped["protocol_document_sha256"] == manifest["protocol_document_sha256"]

    anchors = [
        anchor
        for row in mapped["rows"]
        for anchor in row["source_anchors"]
    ]
    assert len(anchors) == 47
    assert all(not anchor["structure_unit_id"].startswith("su-cross-") for anchor in anchors)
    assert all(anchor["source_span_ids"] for anchor in anchors)
    assert all(anchor["heading_path_zh"] != ["其他章节控制", row["title_zh"]]
               for row in mapped["rows"]
               for anchor in row["source_anchors"])


def test_merged_matrix_has_no_external_relation_targets() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    matrix = json.loads(MERGED_MATRIX_PATH.read_text(encoding="utf-8"))

    _, summary = map_matrix_payload(matrix, manifest)

    assert summary["relation_closure"]["accepted"] is True
    assert summary["relation_closure"]["external_relation_target_count"] == 0


def test_resolver_rejects_source_ref_only_ambiguity() -> None:
    manifest, matrix = _payloads()
    by_ref, _ = build_source_index(manifest)
    anchor = matrix["rows"][1]["source_anchors"][0]
    first = next(
        unit for unit in manifest["units"] if unit["source_ref"] == anchor["source_ref"]
    )
    duplicate = dict(first)
    duplicate["structure_unit_id"] = "synthetic-duplicate"
    duplicate["excerpt"] = first["excerpt"]
    ambiguous = dict(by_ref)
    ambiguous[anchor["source_ref"]] = tuple(by_ref[anchor["source_ref"]]) + (duplicate,)

    with pytest.raises(SourceClosureMappingError) as caught:
        resolve_source_unit(anchor, ambiguous, row_id=matrix["rows"][1]["matrix_row_id"])
    assert caught.value.code == "SOURCE_UNIT_AMBIGUOUS"
    assert set(caught.value.candidate_ids) == {first["structure_unit_id"], "synthetic-duplicate"}


def test_resolver_does_not_fuzzy_select_by_source_ref() -> None:
    manifest, matrix = _payloads()
    by_ref, _ = build_source_index(manifest)
    anchor = matrix["rows"][1]["source_anchors"][0]
    wrong = dict(anchor)
    wrong["verbatim_excerpt"] = "not present in the frozen unit"

    with pytest.raises(SourceClosureMappingError) as caught:
        resolve_source_unit(wrong, by_ref, row_id=matrix["rows"][1]["matrix_row_id"])
    assert caught.value.code == "SOURCE_UNIT_UNMATCHED"
