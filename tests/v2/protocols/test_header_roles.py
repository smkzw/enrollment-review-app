"""页眉/页脚角色保留：同一部件被 default/first/even 不同角色引用时不得折叠角色。"""
from __future__ import annotations

from app.protocols.docx_structure import HeaderFooterKind, extract_docx_structure
from app.protocols.ingestion import register_source_artifact
from .helpers import build_shared_role_header_docx


def test_same_header_part_preserves_each_role(tmp_path):
    path = tmp_path / "shared-role.docx"
    build_shared_role_header_docx(path)
    artifact = register_source_artifact(
        path, source_artifact_id="shared-role", storage_root=tmp_path
    )
    ext = extract_docx_structure(
        path, snapshot_id="shared-role-snap", source_artifact=artifact, output_dir=tmp_path
    )

    headers = [b for b in ext.blocks if b.document_part.value == "header"]
    by_kind: dict[str, list] = {}
    for b in headers:
        by_kind.setdefault(b.part_kind.value, []).append(b)

    # 同一部件在 default 与 first 两种角色下都必须保留各自条目
    assert "default" in by_kind, by_kind.keys()
    assert "first" in by_kind, by_kind.keys()
    assert "SHARED_ROLE_H" in "".join(b.text for b in by_kind["default"])
    assert "SHARED_ROLE_H" in "".join(b.text for b in by_kind["first"])
    # 两种角色的 part_kind 不同，去重不得把 first 折叠进 default
    assert HeaderFooterKind("default") in {b.part_kind for b in by_kind["default"]}
    assert HeaderFooterKind("first") in {b.part_kind for b in by_kind["first"]}
