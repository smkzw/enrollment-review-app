"""逐页路由与不可变页产物生成（Slice 4.3，worker_02）。

对一份来源文件，本模块把分页（``paging``）、渲染（``render``）、原生文本/坐标
提取（``pdf_native``）与不可变工件落盘（``artifacts``）组装为真实的有序页产物：

- ``decide_route_detailed`` 逐页**一次性**决定路线（TXT -> ``SOURCE_TEXT``；PDF 页含真实文本层 ->
  ``NATIVE_PDF_TEXT`` / ``RENDERED_PDF_TEXT``，无文本层或探测失败 -> ``VISION_OCR``，
  相应 PDF 文本路线），并返回非用户可见的技术诊断（内部异常细节）；
- ``build_page_artifact`` 接受可选的预计算路线，避免二次探测；原生页保存原生
  文本/坐标工件，TXT 保存原生文本（无坐标），计算派生哈希，产出 ``PageArtifact``
  合同并经仓储去重持久化；失败页显式失败，全部几何/输入为 ``None``，失败页 ID
  与 ``derivative_sha256`` 由失败类别/原因确定性派生；
- ``_build_page_artifact_detailed`` 返回 ``(页产物, 最终生效路线, 技术诊断)``：
  若原生路线下原生提取失败，最终生效路线降级为 ``VISION_OCR``（该页仍会走 OCR，
  绝不出现「既无原生文本又无 OCR」的页面）；
- ``process_source`` 每页只调用一次 ``decide_route_detailed``，把预计算路线传入
  页产物构建，用**最终生效路线**驱动 OCR，并从不可变工件库按 ``page_image_sha256``
  读回页图字节交给识别（只渲染一次）；任一台词的识别失败不吞掉兄弟页。

字段语义（worker_01 冻结）：``PageArtifact.page_input_sha256`` 是**稳定渲染/解码
输入身份**；``OCRPage.page_input_sha256`` 是**实际送入 OCR 的页图字节哈希**
（== ``PageArtifact.page_image_sha256``）。失败页无页图，绝不允许绑定 OCRPage。

技术诊断（``PageInput.technical_detail`` / ``PageArtifactOutcome.technical_detail``）
是**非用户可见**的内部字段：转换/解码/探测/原生提取异常细节供 worker_03 写入
尝试/任务技术记录，绝不进入 ``PageArtifact.failure_reason`` 或任何用户可见中文。

本模块不实现页工作租约、共享 oMLX 门禁、运行/尝试或重试取消：那些由
worker_03 的执行器在调用 ``decide_route`` / ``build_page_artifact`` /
``adapter.prepare`` / ``adapter.finalize`` 时用租约与门禁包住，并通过
``persist`` 注入提交门禁。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from app.domain.contracts.enums import ExtractionRoute, PageArtifactStatus
from app.domain.contracts.ocr import OCRPage, PageArtifact
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.evidence.coordinates import COORDINATE_TRANSFORM_VERSION
from app.evidence.fingerprint import (
    page_artifact_identity_hash,
    page_derivative_hash,
)
from app.evidence.ocr_adapter import InferenceResult, TextOnlyOcrAdapter
from app.evidence.paging import PageInput, page_source_document
from app.evidence.pdf_native import (
    NativePage,
    extract_native_page,
    serialize_native_coordinates,
)
from app.evidence.render import RENDERER_VERSION, render_page_image
from app.evidence.text import decode_text_bytes
from app.storage.ocr_repositories import PageArtifactRepository

__all__ = [
    "DECODER_VERSION_BY_KIND",
    "PageArtifactOutcome",
    "PageProcessorError",
    "build_page_artifact",
    "decide_route",
    "decide_route_detailed",
    "process_source",
]

#: 解码器身份：任一解码行为（PDF 原生提取/图片解码/文本解码/DOC 转换）变化
#: 必须提升对应版本，否则同一输入会复用同一解码身份却得到不同页产物。
DECODER_VERSION_BY_KIND = {
    "pdf": "slice4.3/pdfplumber/v1",
    "docx": "slice4.3/libreoffice/v1",
    "doc": "slice4.3/libreoffice/v1",
    "image": "slice4.3/pillow/v1",
    "tiff": "slice4.3/pillow/v1",
    "text": "slice4.3/text/v1",
}

_VISION_ROUTES = frozenset({ExtractionRoute.VISION_OCR})
_ROUTE_NOT_PROVIDED = object()


class PageProcessorError(RuntimeError):
    """页产物生成领域错误基类。

    ``message`` 为稳定中文（可进入用户可见路径）；``technical_detail`` 为内部
    异常细节（供 worker_03 技术记录），绝不进入 ``PageArtifact.failure_reason``。
    """

    def __init__(self, message: str, *, technical_detail: str | None = None) -> None:
        super().__init__(message)
        self.technical_detail = technical_detail


@dataclass(frozen=True)
class PageArtifactOutcome:
    """一页的处理产物：不可变页产物 + （视觉页的）OCRPage + 内部技术诊断。

    ``route`` 是**最终生效路线**（原生提取失败后可能降级为 ``VISION_OCR``）；
    ``technical_detail`` 是非用户可见的内部异常细节（供 worker_03 技术记录）。
    """

    page_artifact: PageArtifact
    ocr_page: OCRPage | None = None
    route: ExtractionRoute | None = None
    technical_detail: str | None = None


def decide_route_detailed(page_input: PageInput) -> tuple[ExtractionRoute | None, str | None]:
    """逐页一次性决定识别路线，并返回内部技术诊断（异常细节，非用户可见）。

    - ``text`` -> ``SOURCE_TEXT``（TXT 由确定性文本解码路线处理）；
    - ``image``/``tiff`` -> ``VISION_OCR``；
    - ``pdf``/``docx``/``doc``（后两者转出的 PDF）-> 逐页探测文本层：
      非空 -> ``NATIVE_PDF_TEXT``（pdf）/ ``RENDERED_PDF_TEXT``（docx/doc），
      空或探测异常 -> ``VISION_OCR``（扫描页，见设计 §7.1）。
    """
    if page_input.expects_failure:
        return None, page_input.technical_detail
    kind = page_input.media_kind
    if kind == "text":
        return ExtractionRoute.SOURCE_TEXT, None
    if kind in {"image", "tiff"}:
        return ExtractionRoute.VISION_OCR, None
    # pdf / docx / doc：探测该页是否有真实文本层。
    if page_input.render_source is None:
        return None, "页缺少渲染源，无法决定路线"
    try:
        native = extract_native_page(page_input.render_source, page_input.page_number - 1)
    except Exception as exc:  # noqa: BLE001 - 文本层探测失败按设计降级为扫描页
        # 探测异常细节只作为内部诊断，用户可见降级不泄露异常。
        return ExtractionRoute.VISION_OCR, f"{type(exc).__name__}: {exc}"
    if native.text.strip():
        return (
            (ExtractionRoute.NATIVE_PDF_TEXT if kind == "pdf" else ExtractionRoute.RENDERED_PDF_TEXT),
            None,
        )
    return ExtractionRoute.VISION_OCR, None


def decide_route(page_input: PageInput) -> ExtractionRoute | None:
    """逐页决定识别路线（便捷包装，见 ``decide_route_detailed``）。"""
    return decide_route_detailed(page_input)[0]


def _extract_native(page_input: PageInput) -> NativePage:
    """提取页的原生文本/坐标；失败时抛确定性错误（技术细节随异常携带）。"""
    if page_input.render_source is None:
        raise PageProcessorError(
            f"页 {page_input.page_number} 缺少渲染源，无法提取原生文本"
        )
    try:
        return extract_native_page(page_input.render_source, page_input.page_number - 1)
    except Exception as exc:
        raise PageProcessorError(
            f"页 {page_input.page_number} 原生文本提取失败",
            technical_detail=f"{type(exc).__name__}: {exc}",
        ) from exc


def _failed_artifact_fingerprint(page_input: PageInput) -> str:
    """失败页的稳定失败类别/原因指纹（参与 ID 与派生哈希）。"""
    return canonical_hash(
        {
            "failed_page": "page_artifact_failure/v1",
            "media_kind": page_input.media_kind,
            "original_frame": page_input.original_frame,
            "failure_reason": page_input.failure_reason,
        }
    )


def _page_artifact_id(
    source_document_version_id: str,
    page_input: PageInput,
    *,
    renderer_version: str,
    decoder_version: str,
    transform_version: str,
) -> str:
    """确定性页产物 ID。

    失败页：来源版本 + 页码 + 失败类别/原因指纹（同失败重试幂等复用同 ID，
    实质不同失败得到不同 ID，互不碰撞）；失败页无渲染/解码版本。
    成功页：来源版本 + 页码 + ``page_artifact_identity_hash``（含渲染器/解码器/
    坐标变换版本）—— 同 来源+页码+输入+配置 复用同一 ID，任一版本变化产生新 ID。
    """
    if page_input.expects_failure:
        failure_fp = _failed_artifact_fingerprint(page_input)[:16]
        return (
            f"pa-{source_document_version_id[:24]}-"
            f"{page_input.page_number}-fail-{failure_fp}"
        )
    identity = page_artifact_identity_hash(
        source_document_version_id=source_document_version_id,
        page_number=page_input.page_number,
        original_frame=page_input.original_frame,
        input_sha256=page_input.input_sha256 or "",
        renderer_version=renderer_version,
        decoder_version=decoder_version,
        coordinate_transform_version=transform_version,
    )[:24]
    return f"pa-{source_document_version_id[:24]}-{page_input.page_number}-{identity}"


def build_page_artifact(
    *,
    page_input: PageInput,
    source_document_version_id: str,
    source_sha256: str,
    artifact_store: ArtifactStore,
    renderer_version: str = RENDERER_VERSION,
    decoder_version: str | None = None,
    transform_version: str = COORDINATE_TRANSFORM_VERSION,
    route: ExtractionRoute | None | object = _ROUTE_NOT_PROVIDED,
    persist: Callable[[PageArtifact], PageArtifact] | None = None,
) -> PageArtifact:
    """渲染、保存不可变工件并构造/持久化一页的 ``PageArtifact`` 合同。

    失败页显式失败：不渲染、不保存工件，``page_input_sha256``/``page_width``/
    ``page_height``/``rotation`` 全部为 ``None``，失败页 ID 与 ``derivative_sha256``
    由失败类别/原因确定性派生。成功页逐页渲染并保存页图；原生页额外保存原生
    文本与坐标工件；TXT 保存原生文本（无坐标）。``route`` 为可选的预计算路线
    （避免二次探测）；未提供时内部只探测一次。
    """
    artifact, _route, _detail = _build_page_artifact_detailed(
        page_input=page_input,
        source_document_version_id=source_document_version_id,
        source_sha256=source_sha256,
        artifact_store=artifact_store,
        renderer_version=renderer_version,
        decoder_version=decoder_version,
        transform_version=transform_version,
        route=route,
        persist=persist,
    )
    return artifact


def _build_page_artifact_detailed(
    *,
    page_input: PageInput,
    source_document_version_id: str,
    source_sha256: str,
    artifact_store: ArtifactStore,
    renderer_version: str = RENDERER_VERSION,
    decoder_version: str | None = None,
    transform_version: str = COORDINATE_TRANSFORM_VERSION,
    route: ExtractionRoute | None | object = _ROUTE_NOT_PROVIDED,
    persist: Callable[[PageArtifact], PageArtifact] | None = None,
) -> tuple[PageArtifact, ExtractionRoute | None, str | None]:
    """``build_page_artifact`` 的内部实现：额外返回最终生效路线与内部技术诊断。"""
    effective_decoder = decoder_version or DECODER_VERSION_BY_KIND[page_input.media_kind]
    artifact_id = _page_artifact_id(
        source_document_version_id,
        page_input,
        renderer_version=renderer_version,
        decoder_version=effective_decoder,
        transform_version=transform_version,
    )

    if page_input.expects_failure:
        # 失败页：无真实渲染/解码输入、无页宽高、无旋转 —— 全部 None，绝不填充伪值。
        artifact = PageArtifact(
            page_artifact_id=artifact_id,
            source_document_version_id=source_document_version_id,
            page_number=page_input.page_number,
            original_frame=page_input.original_frame,
            source_sha256=source_sha256,
            page_input_sha256=None,
            page_image_sha256=None,
            native_text_sha256=None,
            native_coordinates_sha256=None,
            page_width=None,
            page_height=None,
            rotation=None,
            renderer_version=None,
            decoder_version=None,
            derivative_sha256=page_derivative_hash(
                page_image_sha256=None,
                native_text_sha256=None,
                native_coordinates_sha256=None,
                renderer_version=None,
                decoder_version=None,
                coordinate_transform_version=transform_version,
                failure_reason=page_input.failure_reason,
            ),
            coordinate_transform_version=transform_version,
            status=PageArtifactStatus.FAILED,
            failure_reason=page_input.failure_reason,
        )
        if persist is not None:
            return persist(artifact), None, page_input.technical_detail
        return artifact, None, page_input.technical_detail

    # 只探测/决定一次路线（调用方预计算后传入；未传则在内部决定一次）。
    effective_route = (
        decide_route(page_input) if route is _ROUTE_NOT_PROVIDED else route
    )
    if effective_route is not None and not isinstance(effective_route, ExtractionRoute):
        raise PageProcessorError("页面识别路线无效，无法继续处理")
    rendered = render_page_image(page_input, renderer_version=renderer_version)
    image_artifact = artifact_store.put("page_image", rendered.image_bytes)
    input_sha256 = page_input.input_sha256
    assert input_sha256 is not None  # 成功页必然携带渲染输入身份

    technical_detail: str | None = None
    native_text_sha: str | None = None
    native_coords_sha: str | None = None
    native: NativePage | None = None
    if page_input.media_kind == "text":
        # TXT 保留原文真相：存为原生文本工件，无坐标；页图供查看。
        assert page_input.render_source is not None  # 成功页必然携带渲染源
        decoded = decode_text_bytes(page_input.render_source)
        native_text_sha = artifact_store.put(
            "native_text", decoded.text.encode("utf-8")
        ).sha256
    elif effective_route in {ExtractionRoute.NATIVE_PDF_TEXT, ExtractionRoute.RENDERED_PDF_TEXT}:
        try:
            native = _extract_native(page_input)
        except PageProcessorError as exc:
            # 原生提取失败：降级为扫描页（VISION_OCR），该页仍会走 OCR，
            # 绝不出现「既无原生文本又无 OCR」的页面。技术细节只作内部诊断。
            technical_detail = exc.technical_detail
            effective_route = ExtractionRoute.VISION_OCR
            native = None
        if native is not None:
            native_text_sha = artifact_store.put(
                "native_text", native.text.encode("utf-8")
            ).sha256
            native_coords_sha = artifact_store.put(
                "native_coordinates", serialize_native_coordinates(native)
            ).sha256

    if native is not None:
        page_width, page_height, rotation = native.page_width, native.page_height, native.rotation
    else:
        page_width, page_height, rotation = (
            float(rendered.width),
            float(rendered.height),
            0,
        )

    artifact = PageArtifact(
        page_artifact_id=artifact_id,
        source_document_version_id=source_document_version_id,
        page_number=page_input.page_number,
        original_frame=page_input.original_frame,
        source_sha256=source_sha256,
        page_input_sha256=input_sha256,
        page_image_sha256=image_artifact.sha256,
        native_text_sha256=native_text_sha,
        native_coordinates_sha256=native_coords_sha,
        page_width=page_width,
        page_height=page_height,
        rotation=rotation,
        renderer_version=renderer_version,
        decoder_version=effective_decoder,
        derivative_sha256=page_derivative_hash(
            page_image_sha256=image_artifact.sha256,
            native_text_sha256=native_text_sha,
            native_coordinates_sha256=native_coords_sha,
            renderer_version=renderer_version,
            decoder_version=effective_decoder,
            coordinate_transform_version=transform_version,
        ),
        coordinate_transform_version=transform_version,
        status=PageArtifactStatus.SUCCEEDED,
        failure_reason=None,
    )
    if persist is not None:
        return persist(artifact), effective_route, technical_detail
    return artifact, effective_route, technical_detail


def process_source(
    *,
    session,
    content: bytes,
    media_kind: str,
    source_sha256: str,
    source_document_version_id: str,
    artifact_store: ArtifactStore,
    adapter: TextOnlyOcrAdapter,
    inference: Callable[[dict[str, Any], bytes], InferenceResult],
    persist_ocr_page: Callable[[OCRPage], object],
    doc_converter=None,
    persist_page_artifact: Callable[[PageArtifact], PageArtifact] | None = None,
) -> list[PageArtifactOutcome]:
    """串联整份来源文件：分页 -> 逐页页产物 -> 视觉页识别，产出有序结果。

    每页只探测一次路线（``decide_route_detailed``），把预计算路线传入页产物构建，
    用最终生效路线（原生提取失败降级为 VISION）驱动 OCR。视觉页的 OCR 输入**恰好
    是**不可变存储的页图字节：只渲染一次，按 ``page_image_sha256`` 从
    ``ArtifactStore`` 读回并传入识别，绝不重渲染；``OCRPage.page_input_sha256``
    即该页图字节哈希（== ``PageArtifact.page_image_sha256``）。失败页不产生 OCRPage。
    页工作租约与共享门禁由 worker_03 组合。
    """
    plan = page_source_document(
        content=content,
        media_kind=media_kind,
        source_sha256=source_sha256,
        doc_converter=doc_converter,
    )
    repo = PageArtifactRepository(session)
    persist_artifact = persist_page_artifact or repo.get_or_create
    outcomes: list[PageArtifactOutcome] = []
    for page_input in plan.pages:
        probe_route, probe_detail = decide_route_detailed(page_input)
        artifact, effective_route, build_detail = _build_page_artifact_detailed(
            page_input=page_input,
            source_document_version_id=source_document_version_id,
            source_sha256=source_sha256,
            artifact_store=artifact_store,
            route=probe_route,
            persist=persist_artifact,
        )
        technical_detail = build_detail or probe_detail
        ocr_page: OCRPage | None = None
        if not page_input.expects_failure and effective_route in _VISION_ROUTES:
            page_image_sha = artifact.page_image_sha256
            assert page_image_sha is not None  # 视觉成功页必然携带页图哈希
            page_image_bytes = artifact_store.read_by_sha("page_image", page_image_sha)
            if sha256(page_image_bytes).hexdigest() != page_image_sha:
                raise PageProcessorError(
                    f"页 {artifact.page_number} 的存储页图字节与页产物哈希不一致"
                )
            recognition = adapter.recognize(
                session=session,
                artifact_store=artifact_store,
                source_sha256=source_sha256,
                page_number=artifact.page_number,
                page_artifact_id=artifact.page_artifact_id,
                page_input_sha256=page_image_sha,
                page_image_bytes=page_image_bytes,
                inference=inference,
                persist=persist_ocr_page,
            )
            ocr_page = recognition.ocr_page
            technical_detail = recognition.technical_detail or technical_detail
        outcomes.append(
            PageArtifactOutcome(
                page_artifact=artifact,
                ocr_page=ocr_page,
                route=effective_route,
                technical_detail=technical_detail,
            )
        )
    return outcomes
