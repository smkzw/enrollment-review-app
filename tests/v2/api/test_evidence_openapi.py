"""V2 证据 API OpenAPI 合同测试（Slice 4.2，worker_02 复核轮）。

断言设计书 §5.2/§5.3 冻结的正式路径存在、首轮自创别名路径不存在，且内容类型
正确（预览 multipart、确认 JSON）。任何兼容别名都不允许保留，避免文档/OpenAPI/
前端出现第二套合同。
"""
from __future__ import annotations

OFFICIAL_PATHS = {
    "/api/v2/subjects/{subject_id}/evidence-upload-previews",
    "/api/v2/evidence-upload-previews/{preview_id}",
    "/api/v2/evidence-upload-previews/{preview_id}/commit",
    "/api/v2/subjects/{subject_id}/evidence-snapshots",
    "/api/v2/evidence-snapshots/{snapshot_id}",
    "/api/v2/source-document-versions/{source_document_version_id}/metadata",
}

#: 首轮未发布的自创别名路径，必须不存在（已从设计书删除的自创子树）。
SELF_INVENTED_PATHS = {
    "/api/v2/subjects/{subject_id}/evidence/previews",
    "/api/v2/subjects/{subject_id}/evidence/previews/{preview_id}",
    "/api/v2/subjects/{subject_id}/evidence/commits",
    "/api/v2/subjects/{subject_id}/evidence/snapshots",
    "/api/v2/subjects/{subject_id}/evidence/snapshots/{snapshot_id}",
    "/api/v2/evidence-upload-previews/{preview_id}/commits",
    "/api/v2/evidence-upload-previews/{preview_id}/previews",
}


def _schema(build_app) -> dict:
    app = build_app()
    return app.openapi()


def test_official_evidence_paths_exist(build_app) -> None:
    paths = _schema(build_app)["paths"]
    missing = OFFICIAL_PATHS - set(paths)
    assert not missing, f"缺少正式证据路径：{missing}"


def test_self_invented_evidence_paths_do_not_exist(build_app) -> None:
    paths = _schema(build_app)["paths"]
    present = SELF_INVENTED_PATHS & set(paths)
    assert not present, f"自创别名路径不应存在：{present}"


def test_preview_create_uses_multipart(build_app) -> None:
    schema = _schema(build_app)
    op = schema["paths"][
        "/api/v2/subjects/{subject_id}/evidence-upload-previews"
    ]["post"]
    content = op["requestBody"]["content"]
    assert "multipart/form-data" in content
    # 提交的字段：审核节点/上传方式/基准修订号/操作人 + 文件列表。
    schema_ref = content["multipart/form-data"]["schema"]
    props = schema["components"]["schemas"][schema_ref["$ref"].rsplit("/", 1)[-1]][
        "properties"
    ]
    assert set(props) >= {
        "review_episode_id",
        "upload_mode",
        "base_revision",
        "files",
    }


def test_commit_uses_json_without_preview_id_field(build_app) -> None:
    schema = _schema(build_app)
    op = schema["paths"][
        "/api/v2/evidence-upload-previews/{preview_id}/commit"
    ]["post"]
    content = op["requestBody"]["content"]
    assert "application/json" in content
    assert "multipart/form-data" not in content
    schema_ref = content["application/json"]["schema"]
    model = schema["components"]["schemas"][schema_ref["$ref"].rsplit("/", 1)[-1]]
    props = model["properties"]
    assert "preview_id" not in props  # preview_id 由路径唯一确定。
    assert set(props) >= {
        "preview_sha256",
        "upload_mode",
        "base_revision",
        "idempotency_key",
        "resolutions",
    }


def test_commit_response_carries_three_truthful_flags(build_app) -> None:
    schema = _schema(build_app)
    op = schema["paths"][
        "/api/v2/evidence-upload-previews/{preview_id}/commit"
    ]["post"]
    ref = op["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    model = schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    props = model["properties"]
    assert {"created", "replayed", "duplicate"} <= set(props)
    assert all(props[name]["type"] == "boolean" for name in ("created", "replayed", "duplicate"))
    assert "job_id" in props
