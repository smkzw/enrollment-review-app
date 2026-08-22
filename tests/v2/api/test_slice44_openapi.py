"""Slice 4.4 证据处理/校对/激活/被提及资料 API OpenAPI 合同测试（WP-44C）。

断言冻结 §7.1 的正式路径存在、请求/响应事实冻结在 schema 中：

- 页读取 response 并列 raw_text / effective_text / selected_corrections /
  risk_scans / risk_reviews / locators（locator 含 precision/degradation）；
- 校对 POST 请求体携带 raw_text_sha256 / 原始范围 / base_processing_revision_id /
  expected_revision / idempotency_key / confirmation；
- 处理修订 GET response 携带 revision_kind / base_processing_revision_id /
  evidence_snapshot_id / manifest_sha256 / completion_manifest_sha256 /
  is_activatable / gates；
- 激活 POST 请求体携带 expected_revision，response 携带 event_id / from 旧新
  指针对 / resulting_episode_revision；
- 被提及资料 create/patch/confirm/dismiss/resolve/delete 全部存在且为追加写语义；
- 快照列表 DTO 携带 active_evidence_snapshot_id / active_evidence_processing_revision_id，
  快照条目携带 is_current。
"""
from __future__ import annotations

OFFICIAL_PATHS = {
    "/api/v2/ocr-pages/{ocr_page_id}",
    "/api/v2/ocr-pages/{ocr_page_id}/corrections",
    "/api/v2/ocr-pages/{ocr_page_id}/risk-reviews",
    "/api/v2/evidence-processing-revisions/{revision_id}",
    "/api/v2/evidence-processing-revisions/{revision_id}/pages/{entry_id}/image",
    "/api/v2/evidence-processing-revisions/build",
    "/api/v2/evidence-processing-revisions/{revision_id}/activate",
    "/api/v2/evidence-processing-revisions/{revision_id}/rollback",
    "/api/v2/subjects/{subject_id}/referenced-documents",
    "/api/v2/referenced-documents/{referenced_document_id}",
    "/api/v2/referenced-documents/{referenced_document_id}/confirm",
    "/api/v2/referenced-documents/{referenced_document_id}/dismiss",
    "/api/v2/referenced-documents/{referenced_document_id}/resolve",
    "/api/v2/referenced-documents/{referenced_document_id}/resolution",
}

#: 不得存在的伪路径：原地 UPDATE/DELETE 被提及资料、校对层伪装为原始识别等。
FORBIDDEN_PATHS = {
    "/api/v2/referenced-documents/{referenced_document_id}/delete",
    "/api/v2/ocr-pages/{ocr_page_id}/raw-ocr",
    "/api/v2/ocr-pages/{ocr_page_id}/effective-text",
}


def _schema(build_app) -> dict:
    app = build_app()
    return app.openapi()


def _model(schema, ref: str) -> dict:
    return schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]


def test_official_slice44_paths_exist(build_app) -> None:
    paths = _schema(build_app)["paths"]
    missing = OFFICIAL_PATHS - set(paths)
    assert not missing, f"缺少正式 Slice 4.4 路径：{missing}"


def test_forbidden_slice44_paths_do_not_exist(build_app) -> None:
    paths = _schema(build_app)["paths"]
    present = FORBIDDEN_PATHS & set(paths)
    assert not present, f"不应存在的路径：{present}"


def test_ocr_page_read_separates_raw_effective_and_risk(build_app) -> None:
    schema = _schema(build_app)
    op = schema["paths"]["/api/v2/ocr-pages/{ocr_page_id}"]["get"]
    ref = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    model = _model(schema, ref)
    props = model["properties"]
    assert set(props) >= {
        "raw_text",
        "raw_text_sha256",
        "effective_text",
        "effective_text_sha256",
        "selected_corrections",
        "risk_scans",
        "risk_reviews",
        "locators",
        "processing_revision_id",
        "is_current_revision",
    }
    # 定位条目必须诚实暴露精度与降级。
    locator_ref = props["locators"]["items"]["$ref"]
    locator_model = _model(schema, locator_ref)
    assert set(locator_model["properties"]) >= {
        "precision",
        "precision_label",
        "degradation_reason",
        "bbox",
        "coordinate_frame",
        "coordinate_transform_version",
    }


def test_correction_post_contract(build_app) -> None:
    schema = _schema(build_app)
    op = schema["paths"]["/api/v2/ocr-pages/{ocr_page_id}/corrections"]["post"]
    content = op["requestBody"]["content"]
    assert "application/json" in content
    model = _model(
        schema, content["application/json"]["schema"]["$ref"]
    )
    props = model["properties"]
    assert set(props) >= {
        "raw_text_sha256",
        "text_start",
        "text_end",
        "original_text",
        "corrected_text",
        "change_kind",
        "reason",
        "base_processing_revision_id",
        "expected_revision",
        "idempotency_key",
    }
    assert "confirmation" in props  # 关键语义变化的显式确认载荷。
    assert props["text_start"]["minimum"] == 0
    assert props["text_end"]["minimum"] == 0
    assert "minLength" not in props["original_text"]


def test_revision_get_carries_kind_hashes_gates_and_activatable(build_app) -> None:
    schema = _schema(build_app)
    op = schema["paths"][
        "/api/v2/evidence-processing-revisions/{revision_id}"
    ]["get"]
    ref = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    model = _model(schema, ref)
    props = model["properties"]
    assert set(props) >= {
        "revision_kind",
        "revision_kind_label",
        "evidence_snapshot_id",
        "base_processing_revision_id",
        "manifest_sha256",
        "completion_manifest_sha256",
        "pages",
        "is_activatable",
        "is_current",
        "gates",
    }
    gate_ref = props["gates"]["items"]["$ref"]
    gate_model = _model(schema, gate_ref)
    assert set(gate_model["properties"]) >= {
        "gate",
        "gate_label",
        "status",
        "status_label",
        "detail",
    }
    page_ref = props["pages"]["items"]["$ref"]
    page_model = _model(schema, page_ref)
    assert set(page_model["properties"]) >= {
        "entry_id",
        "position",
        "source_document_version_id",
        "page_number",
        "page_artifact_id",
        "ocr_page_id",
        "status",
        "status_label",
        "failure_reason",
        "image_available",
        "page_width",
        "page_height",
    }


def test_revision_page_image_contract(build_app) -> None:
    schema = _schema(build_app)
    operation = schema["paths"][
        "/api/v2/evidence-processing-revisions/{revision_id}/pages/{entry_id}/image"
    ]["get"]
    assert "image/png" in operation["responses"]["200"]["content"]


def test_activate_post_contract(build_app) -> None:
    schema = _schema(build_app)
    op = schema["paths"][
        "/api/v2/evidence-processing-revisions/{revision_id}/activate"
    ]["post"]
    body_model = _model(
        schema, op["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    )
    assert "expected_revision" in body_model["properties"]
    assert "idempotency_key" in body_model["properties"]  # 稳定幂等键（§7.1）
    ref = op["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    event_model = _model(schema, ref)
    props = event_model["properties"]
    assert set(props) >= {
        "event_id",
        "event_kind",
        "from_snapshot_id",
        "from_revision_id",
        "to_snapshot_id",
        "to_revision_id",
        "resulting_episode_revision",
    }


def test_referenced_document_paths_shape_only(build_app) -> None:
    """OpenAPI 只断言路径/字段形状；追加写历史行为由行为测试断言（§8.5）。"""
    schema = _schema(build_app)
    paths = schema["paths"]
    assert "post" in paths["/api/v2/subjects/{subject_id}/referenced-documents"]
    assert "patch" in paths["/api/v2/referenced-documents/{referenced_document_id}"]
    assert "post" in paths["/api/v2/referenced-documents/{referenced_document_id}/confirm"]
    assert "post" in paths["/api/v2/referenced-documents/{referenced_document_id}/dismiss"]
    assert "post" in paths["/api/v2/referenced-documents/{referenced_document_id}/resolve"]
    assert "delete" in paths["/api/v2/referenced-documents/{referenced_document_id}/resolution"]
    # 所有写命令携带稳定幂等键（追加写不原地 UPDATE/DELETE）。
    create_model = _model(
        schema,
        paths["/api/v2/subjects/{subject_id}/referenced-documents"]["post"][
            "requestBody"
        ]["content"]["application/json"]["schema"]["$ref"],
    )
    assert "idempotency_key" in create_model["properties"]
    assert "expected_revision" in create_model["properties"]
    # 被提及资料响应携带状态/来源/满足状态。
    resp_ref = paths["/api/v2/subjects/{subject_id}/referenced-documents"]["post"][
        "responses"
    ]["201"]["content"]["application/json"]["schema"]["$ref"]
    model = _model(schema, resp_ref)
    props = model["properties"]
    assert set(props) >= {
        "referenced_document_id",
        "description",
        "origin",
        "origin_label",
        "status",
        "status_label",
        "trigger_locator_id",
        "revision",
        "resolution",
    }


def test_snapshot_list_exposes_pointer_and_is_current(build_app) -> None:
    schema = _schema(build_app)
    op = schema["paths"][
        "/api/v2/subjects/{subject_id}/evidence-snapshots"
    ]["get"]
    ref = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    list_model = _model(schema, ref)
    assert set(list_model["properties"]) >= {
        "active_evidence_snapshot_id",
        "active_evidence_processing_revision_id",
        "items",
    }
    item_ref = list_model["properties"]["items"]["items"]["$ref"]
    item_model = _model(schema, item_ref)
    assert "is_current" in item_model["properties"]


def test_episode_dto_exposes_active_pair(build_app) -> None:
    schema = _schema(build_app)
    episode_ref = None
    for name, model in schema["components"]["schemas"].items():
        if model.get("title") == "EpisodeDTO":
            episode_ref = name
            break
    assert episode_ref is not None
    props = schema["components"]["schemas"][episode_ref]["properties"]
    assert set(props) >= {
        "active_evidence_snapshot_id",
        "active_evidence_processing_revision_id",
    }
