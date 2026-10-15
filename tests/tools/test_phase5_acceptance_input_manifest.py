"""Deterministic tests for Phase 5.8 input manifest / isolation copy tool.

Uses only temporary synthetic trees. Does not read external clinical sources.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.phase5_acceptance.input_manifest import (
    Decision,
    InputManifestError,
    ManifestMode,
    build_manifest,
    classify_path,
    execute_copy_plan,
    main,
    run_inventory,
    sha256_file,
    verify_source_immutability,
)


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def test_classify_uses_explicit_photo_and_archive_policy() -> None:
    assert classify_path(Path("note.pdf"))[1] is Decision.INCLUDE
    assert classify_path(Path("scan.JPG"))[1] is Decision.INCLUDE
    assert classify_path(Path("scan.JPG"))[0] == "photo"
    assert classify_path(Path("bundle.zip"))[1] is Decision.INCLUDE
    assert classify_path(Path("bundle.tar.gz"))[1] is Decision.INCLUDE
    assert classify_path(Path("bundle.TAR.GZ"))[0] == "archive"
    assert classify_path(Path("scan.JPG"), exclude_kinds={"photo"})[1] is Decision.EXCLUDE
    assert classify_path(Path("bundle.zip"), exclude_kinds={"archive"})[1] is Decision.EXCLUDE
    assert classify_path(Path(".DS_Store"))[1] is Decision.EXCLUDE
    assert classify_path(Path("~$protocol.docx"))[1] is Decision.EXCLUDE


def test_manifest_only_default_records_hashes_and_reasons(tmp_path: Path) -> None:
    source = tmp_path / "source_a"
    pdf = _write(source / "subj" / "lab.pdf", b"%PDF-lab")
    photo = _write(source / "subj" / "photo.jpeg", b"\xff\xd8fake")
    archive = _write(source / "pack.zip", b"PK\x03\x04")

    manifest = build_manifest([source], exclude_kinds={"photo", "archive"})
    assert manifest["mode"] == ManifestMode.MANIFEST.value
    assert manifest["destination"] is None
    assert manifest["copy_plan"] == []
    assert manifest["summary"]["total_files"] == 3
    assert manifest["summary"]["included_files"] == 1
    assert manifest["summary"]["excluded_files"] == 2

    by_rel = {entry["relative_path"]: entry for entry in manifest["entries"]}
    assert by_rel["subj/lab.pdf"]["decision"] == "include"
    assert by_rel["subj/lab.pdf"]["sha256"] == _sha(b"%PDF-lab")
    assert by_rel["subj/lab.pdf"]["size_bytes"] == pdf.stat().st_size
    assert by_rel["subj/lab.pdf"]["file_type"] == "pdf"
    assert "included" in by_rel["subj/lab.pdf"]["reason"]

    assert by_rel["subj/photo.jpeg"]["decision"] == "exclude"
    assert by_rel["subj/photo.jpeg"]["file_type"] == "photo"
    assert by_rel["subj/photo.jpeg"]["sha256"] == _sha(b"\xff\xd8fake")
    assert photo.exists()

    assert by_rel["pack.zip"]["decision"] == "exclude"
    assert by_rel["pack.zip"]["file_type"] == "archive"
    assert archive.exists()


def test_exact_include_path_does_not_read_or_copy_unselected_files(tmp_path: Path) -> None:
    source = tmp_path / "protocol_source"
    selected = _write(source / "protocol.docx", b"protocol")
    unselected = _write(source / "manual.xlsx", b"manual")
    destination = tmp_path / "isolated"

    manifest = run_inventory(
        [source],
        mode=ManifestMode.COPY,
        destination=destination,
        output=tmp_path / "selected-manifest.json",
        include_paths={"protocol.docx"},
        perform_copy=True,
    )

    assert manifest["summary"]["included_files"] == 1
    assert manifest["summary"]["excluded_files"] == 0
    assert [row["relative_path"] for row in manifest["entries"]] == ["protocol.docx"]
    assert (destination / source.name / "protocol.docx").read_bytes() == selected.read_bytes()
    assert not (destination / source.name / "manual.xlsx").exists()
    assert unselected.is_file()


def test_missing_or_escaping_include_path_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source_include"
    _write(source / "protocol.docx", b"protocol")

    with pytest.raises(InputManifestError, match="were not found"):
        build_manifest([source], include_paths={"missing.docx"})
    with pytest.raises(InputManifestError, match="relative paths"):
        build_manifest([source], include_paths={"../protocol.docx"})


def test_destination_rejected_inside_source(tmp_path: Path) -> None:
    source = tmp_path / "source_b"
    _write(source / "a.pdf", b"pdf")
    nested = source / "isolation"
    nested.mkdir()

    with pytest.raises(InputManifestError, match="must be disjoint"):
        build_manifest([source], mode=ManifestMode.COPY, destination=nested)


def test_destination_rejected_when_it_contains_source(tmp_path: Path) -> None:
    destination = tmp_path / "acceptance"
    source = destination / "source"
    _write(source / "a.pdf", b"pdf")

    with pytest.raises(InputManifestError, match="must be disjoint"):
        build_manifest([source], mode=ManifestMode.COPY, destination=destination)


def test_copy_mode_requires_explicit_destination(tmp_path: Path) -> None:
    source = tmp_path / "source_c"
    _write(source / "a.pdf", b"pdf")
    with pytest.raises(InputManifestError, match="requires an explicit destination"):
        build_manifest([source], mode=ManifestMode.COPY)


def test_manifest_mode_rejects_destination_argument(tmp_path: Path) -> None:
    source = tmp_path / "source_d"
    dest = tmp_path / "dest"
    _write(source / "a.pdf", b"pdf")
    with pytest.raises(InputManifestError, match="only valid with explicit copy mode"):
        build_manifest([source], mode=ManifestMode.MANIFEST, destination=dest)


def test_copy_preserves_relative_paths_and_verifies_hashes(tmp_path: Path) -> None:
    source = tmp_path / "source_e"
    dest = tmp_path / "isolation"
    payload = b"clinical-doc-bytes"
    _write(source / "center" / "subject" / "report.pdf", payload)
    _write(source / "center" / "subject" / "snap.png", b"png")

    manifest = run_inventory(
        [source],
        mode=ManifestMode.COPY,
        destination=dest,
        output=tmp_path / "manifest.json",
        label="synthetic-copy",
        verify_sources=True,
        perform_copy=True,
        exclude_kinds={"photo", "archive"},
    )

    assert manifest["source_immutability"]["verified"] is True
    assert manifest["copy_verification"]["verified"] is True
    assert len(manifest["copy_plan"]) == 1

    copied = dest / source.name / "center" / "subject" / "report.pdf"
    assert copied.is_file()
    assert sha256_file(copied) == _sha(payload)
    assert not (dest / source.name / "center" / "subject" / "snap.png").exists()

    # Sources unchanged.
    original = source / "center" / "subject" / "report.pdf"
    assert original.read_bytes() == payload
    assert (source / "center" / "subject" / "snap.png").is_file()

    saved = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert saved["label"] == "synthetic-copy"
    assert saved["summary"]["copy_plan_entries"] == 1


def test_source_immutability_detects_mutation(tmp_path: Path) -> None:
    source = tmp_path / "source_f"
    path = _write(source / "doc.pdf", b"v1")
    manifest = build_manifest([source])
    path.write_bytes(b"v2-mutated")
    result = verify_source_immutability(manifest)
    assert result["verified"] is False
    assert result["checks"][0]["ok"] is False


def test_execute_copy_refuses_write_into_source(tmp_path: Path) -> None:
    source = tmp_path / "source_g"
    _write(source / "doc.pdf", b"x")
    manifest = {
        "mode": "copy",
        "destination": str(source / "nested"),
        "source_roots": [str(source)],
        "copy_plan": [
            {
                "source_path": str(source / "doc.pdf"),
                "destination_path": str(source / "nested" / "doc.pdf"),
                "relative_path": "nested/doc.pdf",
                "sha256": _sha(b"x"),
            }
        ],
    }
    with pytest.raises(InputManifestError, match="must be disjoint"):
        execute_copy_plan(manifest)


def test_manifest_output_rejected_inside_source(tmp_path: Path) -> None:
    source = tmp_path / "source_output"
    _write(source / "doc.pdf", b"x")

    with pytest.raises(InputManifestError, match="output must not be inside"):
        run_inventory([source], output=source / "manifest.json")


def test_tampered_copy_plan_cannot_escape_destination(tmp_path: Path) -> None:
    source = tmp_path / "source_tamper"
    destination = tmp_path / "destination_tamper"
    _write(source / "doc.pdf", b"x")
    manifest = build_manifest(
        [source],
        mode=ManifestMode.COPY,
        destination=destination,
    )
    manifest["copy_plan"][0]["destination_path"] = str(tmp_path / "escaped.pdf")

    with pytest.raises(InputManifestError, match="escapes declared destination"):
        execute_copy_plan(manifest)


def test_nested_source_roots_rejected(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    child = parent / "child"
    _write(parent / "a.pdf", b"a")
    _write(child / "b.pdf", b"b")
    with pytest.raises(InputManifestError, match="must not nest"):
        build_manifest([parent, child])


def test_cli_manifest_only_and_copy_plan(tmp_path: Path) -> None:
    source = tmp_path / "source_h"
    _write(source / "keep.docx", b"docx")
    _write(source / "drop.rar", b"rar")
    output = tmp_path / "out" / "manifest.json"

    code = main(
        [
            "--source",
            str(source),
            "--output",
            str(output),
            "--label",
            "cli-manifest",
            "--exclude-kind",
            "archive",
        ]
    )
    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mode"] == "manifest"
    assert payload["summary"]["included_files"] == 1
    assert payload["summary"]["excluded_files"] == 1
    assert payload["source_immutability"]["verified"] is True

    dest = tmp_path / "copy_dest"
    output2 = tmp_path / "out" / "copy-manifest.json"
    code = main(
        [
            "--source",
            str(source),
            "--mode",
            "copy",
            "--destination",
            str(dest),
            "--output",
            str(output2),
            "--execute-copy",
            "--exclude-kind",
            "archive",
        ]
    )
    assert code == 0
    copied = dest / source.name / "keep.docx"
    assert copied.read_bytes() == b"docx"
    assert not (dest / source.name / "drop.rar").exists()
