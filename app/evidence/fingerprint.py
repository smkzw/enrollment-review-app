"""OCR 配置指纹与页级缓存键（纯确定性函数）。

缓存身份只由内容字节与决定性输入决定，禁止文件名或 mtime 参与：
- ``build_profile_fingerprint`` 冻结 OCRProfile 的识别身份字段；
- ``build_ocr_cache_key`` 冻结页级缓存唯一键，任一决定性输入变化必然产生新键。
"""
from __future__ import annotations

from typing import Any

from app.domain.publication import canonical_hash, ocr_page_cache_hash


def build_profile_fingerprint(
    *,
    extraction_route: str,
    provider: str,
    model_id: str,
    model_revision: str,
    prompt_sha256: str | None,
    parser_version: str,
    render_params_sha256: str | None,
    request_params_sha256: str | None,
    layout_parser_version: str | None,
    coordinate_transform_version: str,
) -> str:
    """按识别身份字段计算 OCRProfile 稳定指纹（与合同校验一致）。"""
    return canonical_hash(
        {
            "profile": "ocr_profile/v1",
            "extraction_route": extraction_route,
            "provider": provider,
            "model_id": model_id,
            "model_revision": model_revision,
            "prompt_sha256": prompt_sha256,
            "parser_version": parser_version,
            "render_params_sha256": render_params_sha256,
            "request_params_sha256": request_params_sha256,
            "layout_parser_version": layout_parser_version,
            "coordinate_transform_version": coordinate_transform_version,
        }
    )


def build_ocr_cache_key(
    *,
    source_sha256: str,
    page_number: int,
    ocr_profile_sha256: str,
    page_input_sha256: str,
    layout_parser_version: str | None = None,
    coordinate_transform_version: str,
) -> str:
    """页级 OCR 缓存唯一键。

    ``layout_parser_version`` 与 ``coordinate_transform_version`` 参与键值，
    保证布局解析器或坐标变换升级后不会错误命中旧坐标缓存。
    """
    return ocr_page_cache_hash(
        source_sha256=source_sha256,
        page_number=page_number,
        ocr_profile_sha256=ocr_profile_sha256,
        page_input_sha256=page_input_sha256,
        layout_parser_version=layout_parser_version,
        coordinate_transform_version=coordinate_transform_version,
    )


def content_sha256(payload: Any) -> str:
    """对规范化 JSON 载荷计算 SHA-256（用于页图/派生文本等工件）。"""
    return canonical_hash(payload)


def page_derivative_hash(
    *,
    page_image_sha256: str | None,
    native_text_sha256: str | None,
    native_coordinates_sha256: str | None,
    renderer_version: str | None,
    decoder_version: str | None,
    coordinate_transform_version: str,
    failure_reason: str | None = None,
) -> str:
    """页派生信息的内容身份：任一派生内容或版本变化必然产生新哈希。

    只覆盖页产物自身的派生内容与处理版本（渲染器/解码器/坐标变换），
    不包含来源身份（source/page_number 已由 PageArtifact 身份列单独冻结）。
    失败页无任何派生内容，此时 ``failure_reason`` 参与哈希，使 ``derivative_sha256``
    成为**确定性失败/配置指纹**，而不是声称存在页图的派生哈希；成功页保持
    只含内容/版本的旧载荷，哈希不受影响。
    """
    payload: dict[str, Any] = {
        "derivative": "page_artifact_derivative/v1",
        "page_image_sha256": page_image_sha256,
        "native_text_sha256": native_text_sha256,
        "native_coordinates_sha256": native_coordinates_sha256,
        "renderer_version": renderer_version,
        "decoder_version": decoder_version,
        "coordinate_transform_version": coordinate_transform_version,
    }
    if failure_reason is not None:
        payload["failure_reason"] = failure_reason
    return canonical_hash(payload)


def page_artifact_identity_hash(
    *,
    source_document_version_id: str,
    page_number: int,
    original_frame: str | None,
    input_sha256: str,
    renderer_version: str,
    decoder_version: str,
    coordinate_transform_version: str,
) -> str:
    """页产物成功身份的确定性复合哈希。

    成功页产物身份必须包含渲染器/解码器/坐标变换版本（P4-R03 决定性输入），
    而不仅是来源/页码/页输入：同一 来源+页码+输入+配置 复用同一 ID，任一版本
    变化必然产生新 ID。失败页无渲染/解码版本，走独立的失败类别/原因指纹。
    """
    return canonical_hash(
        {
            "page_artifact_identity": "page_artifact_identity/v2",
            "source_document_version_id": source_document_version_id,
            "page_number": page_number,
            "original_frame": original_frame,
            "input_sha256": input_sha256,
            "renderer_version": renderer_version,
            "decoder_version": decoder_version,
            "coordinate_transform_version": coordinate_transform_version,
        }
    )
