"""方案文档提取层领域契约（Phase 3 切片 1）。

与设计书 §3.1「文档与来源」一致，覆盖解构流水线在发布前必经的五个边界：

- ``ProtocolSourceArtifact``     原始方案文件登记与哈希（不可变）；
- ``ProtocolRenderArtifact``     受控 LibreOffice 渲染派生物与 manifest；
- ``ProtocolSourceSpan``         结构块到渲染页/文本范围的来源定位；
- ``ProtocolExtractionSnapshot`` 一次结构提取的不可变结果与覆盖统计；
- ``FrozenProtocolCatalog``      Agent 调用前冻结的官方父规则目录与
                                按访视实例拆分的基线及以前必做项目录。

这些契约只描述结构通道与渲染通道，不承载规则语义或发布权威；
发布权威仍由 ``ProtocolAuthorityRecord`` / ``ProtocolDocumentVersion`` 等持有。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from .common import ContractModel, VersionedModel
from .enums import (
    AlignmentStatus,
    CatalogItemKind,
    CatalogKind,
    DocumentPart,
    ExtractionStatus,
    RenderStatus,
    ReviewStage,
    SourceLocatorPrecision,
    StudyPhase,
)
from .evidence import BoundingBox

_SHA256 = r"^[0-9a-f]{64}$"


class ProtocolSourceArtifact(VersionedModel):
    """原始方案文件身份、SHA-256、MIME、大小、存储引用与上传时间（不可变）。"""

    source_artifact_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    sha256: str = Field(pattern=_SHA256)
    mime_type: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    storage_ref: str = Field(min_length=1)
    uploaded_at: datetime


class ProtocolRenderArtifact(VersionedModel):
    """受控渲染派生物：渲染器版本、参数、PDF 哈希、页数与状态（不可变）。

    渲染页语义为「本次渲染第 N 页」，不冒充原作者环境中的绝对分页。
    """

    render_artifact_id: str = Field(min_length=1)
    source_artifact_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=_SHA256)
    renderer: str = Field(min_length=1)
    renderer_version: str = Field(min_length=1)
    render_params: dict = Field(default_factory=dict)
    pdf_sha256: str | None = Field(default=None, pattern=_SHA256)
    # 成功的 PDF 渲染至少 1 页；0 页或 None 仅允许出现在失败/降级（页数不可读）态。
    page_count: int | None = Field(default=None, ge=1)
    status: RenderStatus
    storage_ref: str | None = None
    render_error: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_status(self) -> "ProtocolRenderArtifact":
        if self.status == RenderStatus.SUCCEEDED:
            if (
                self.pdf_sha256 is None
                or self.page_count is None
                or self.storage_ref is None
            ):
                raise ValueError("渲染成功必须提供 PDF 哈希、页数与存储引用")
            if self.render_error is not None:
                raise ValueError("渲染成功不应携带渲染错误说明")
        if self.status == RenderStatus.DEGRADED:
            if self.pdf_sha256 is None or self.storage_ref is None:
                raise ValueError("降级渲染必须提供 PDF 哈希与存储引用")
            if not self.render_error:
                raise ValueError("降级渲染必须说明降级原因")
        if self.status == RenderStatus.FAILED:
            if self.pdf_sha256 is not None:
                raise ValueError("渲染失败不应携带 PDF 哈希")
            if self.page_count is not None:
                raise ValueError("渲染失败不应携带页数")
            if not self.render_error:
                raise ValueError("渲染失败必须说明失败原因")
        return self


class ProtocolSourceSpan(VersionedModel):
    """规则/流程/证据要求回溯到方案原文的定位（不可变）。

    结构通道（文档部件、块顺序、嵌套表格路径）始终保留；``table_path`` 保存
    完整祖先 ``(row, col, ...)`` 链以表示嵌套表格位置，``table_row``/``table_col``
    仅为其最内层坐标的镜像。渲染通道（渲染页、文本范围、坐标、摘录）在可用时
    提供，失败时降级为 block 定位并说明原因。
    """

    source_span_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    document_part: DocumentPart
    section_index: int | None = Field(default=None, ge=0)
    block_order: int = Field(ge=0)
    table_path: tuple[int, ...] | None = None
    table_row: int | None = Field(default=None, ge=0)
    table_col: int | None = Field(default=None, ge=0)
    render_artifact_id: str | None = None
    render_page: int | None = Field(default=None, ge=1)
    text_start: int | None = Field(default=None, ge=0)
    text_end: int | None = Field(default=None, ge=0)
    bbox: BoundingBox | None = None
    excerpt: str | None = None
    precision: SourceLocatorPrecision
    alignment_status: AlignmentStatus
    degradation_reason: str | None = None

    @model_validator(mode="after")
    def validate_table_path(self) -> "ProtocolSourceSpan":
        if self.table_path is None:
            if self.table_row is not None or self.table_col is not None:
                raise ValueError("无 table_path 时不能携带 table_row/table_col")
            return self
        if len(self.table_path) % 2 != 0:
            raise ValueError("table_path 必须由 (row, col) 对组成")
        if any(v < 0 for v in self.table_path):
            raise ValueError("table_path 坐标必须非负")
        if len(self.table_path) < 2:
            raise ValueError("table_path 至少应含一对 (row, col)")
        if (
            self.table_row != self.table_path[-2]
            or self.table_col != self.table_path[-1]
        ):
            raise ValueError("table_row/table_col 必须等于 table_path 的最内层坐标")
        return self

    @model_validator(mode="after")
    def validate_locator(self) -> "ProtocolSourceSpan":
        if self.precision == SourceLocatorPrecision.BBOX and self.bbox is None:
            raise ValueError("bbox 定位必须提供坐标")
        if self.precision != SourceLocatorPrecision.BBOX and self.bbox is not None:
            raise ValueError("非 bbox 定位不能携带坐标")
        if self.precision in (
            SourceLocatorPrecision.TEXT_RANGE,
            SourceLocatorPrecision.BBOX,
        ):
            if (
                self.text_start is None
                or self.text_end is None
                or self.text_end <= self.text_start
            ):
                raise ValueError("text_range/bbox 定位必须提供有效字符范围")
        elif self.text_start is not None or self.text_end is not None:
            raise ValueError("非 text_range 定位不能携带字符范围")
        if self.precision == SourceLocatorPrecision.PAGE_EXCERPT and not self.excerpt:
            raise ValueError("page_excerpt 必须提供页面摘录")
        if (
            self.precision == SourceLocatorPrecision.PAGE_ONLY
            and self.excerpt is not None
        ):
            raise ValueError("page_only 不能携带伪精确页面摘录")
        if (self.render_page is None) != (self.render_artifact_id is None):
            raise ValueError("渲染页与渲染派生物引用必须成对出现")
        if self.alignment_status == AlignmentStatus.UNALIGNED:
            if self.render_artifact_id is not None or self.render_page is not None:
                raise ValueError("未对齐跨度不能携带渲染定位")
            if not self.degradation_reason:
                raise ValueError("未对齐必须说明降级原因")
        if (
            self.alignment_status == AlignmentStatus.DEGRADED
            and not self.degradation_reason
        ):
            raise ValueError("降级对齐必须说明降级原因")
        return self


class ExtractionCoverage(ContractModel):
    """结构提取覆盖统计：非 LLM 完整性证据的一部分。"""

    paragraph_count: int = Field(ge=0)
    table_count: int = Field(ge=0)
    section_count: int = Field(ge=0)
    nested_table_count: int = Field(ge=0)
    header_detected: bool = False
    footer_detected: bool = False
    tracked_change_count: int = Field(default=0, ge=0)


class ExtractionAnomaly(ContractModel):
    """结构提取异常：空结果、覆盖不全、未接受修订等必须显式记录，不得伪装成功。"""

    anomaly_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    message: str = Field(min_length=1)
    scope_ref: str | None = None


class ProtocolExtractionSnapshot(VersionedModel):
    """一次结构提取的不可变结果、解析器版本、覆盖统计、异常与派生物引用。

    ``content_sha256`` 为规范化块集（完整内容工件）的 SHA-256，
    ``content_storage_ref`` 指向该块集的存储位置；两者让任何来源摘录都能
    相对该文件哈希逐字核验，计数本身不足以证明摘录属于该文件哈希。
    """

    snapshot_id: str = Field(min_length=1)
    source_artifact_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=_SHA256)
    parser_name: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    status: ExtractionStatus
    coverage: ExtractionCoverage
    anomalies: list[ExtractionAnomaly] = Field(default_factory=list)
    render_artifact_ids: list[str] = Field(default_factory=list)
    content_sha256: str = Field(pattern=_SHA256)
    content_storage_ref: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_snapshot(self) -> "ProtocolExtractionSnapshot":
        if self.status == ExtractionStatus.FAILED:
            if self.coverage.paragraph_count > 0 or self.coverage.table_count > 0:
                raise ValueError("失败提取不应携带非零覆盖统计")
        if len(self.render_artifact_ids) != len(set(self.render_artifact_ids)):
            raise ValueError("派生物引用不得重复")
        return self


def optional_source_excerpts_for_spans(
    source_span_ids: Sequence[str],
    *,
    by_id: Mapping[str, ProtocolSourceSpan],
    by_ref: Mapping[str, ProtocolSourceSpan] | None = None,
    blocks_by_ref: Mapping[str, object] | None = None,
) -> tuple[str | None, ...]:
    """Return immutable source text, retaining ``None`` for structural spans.

    A formally aligned span may be only an exact page fragment when one DOCX
    paragraph crosses a rendered page.  The span remains the physical locator;
    catalog prompts receive the complete extracted source block when available.
    """

    excerpts: list[str | None] = []
    for span_id in source_span_ids:
        span = by_id.get(span_id)
        if span is None and by_ref is not None:
            span = by_ref.get(span_id)
        if span is None:
            return ()
        text = None
        if blocks_by_ref is not None:
            block = blocks_by_ref.get(span.source_ref)
            text = getattr(block, "text", None) if block is not None else None
        if not (text and str(text).strip()):
            text = span.excerpt
        excerpts.append(str(text) if text and str(text).strip() else None)
    return tuple(excerpts) if any(excerpt is not None for excerpt in excerpts) else ()


def frozen_catalog_content_hash(catalog: Any) -> str:
    """Hash catalog content while preserving legacy empty-excerpt artifacts."""

    from app.domain.publication import canonical_hash

    payload = catalog.model_dump(mode="json", exclude={"catalog_sha256"})
    for item in payload.get("items", []):
        if not item.get("source_excerpts"):
            item.pop("source_excerpts", None)
    return canonical_hash(payload)


class FrozenCatalogItem(ContractModel):
    """冻结目录项：稳定 ID、原文范围与来源片段（期别继承自所属目录）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str = Field(min_length=1)
    kind: CatalogItemKind
    official_code: str | None = None
    label: str = Field(min_length=1)
    visit_instance: str | None = None
    review_stage: ReviewStage | None = None
    position: int = Field(ge=0)
    source_span_ids: tuple[str, ...] = Field(min_length=1)
    source_excerpts: tuple[str | None, ...] = ()

    @model_validator(mode="after")
    def validate_source_excerpts(self) -> "FrozenCatalogItem":
        if self.source_excerpts and len(self.source_excerpts) != len(
            self.source_span_ids
        ):
            raise ValueError("目录项来源摘录必须与来源定位一一对应")
        if self.source_excerpts and not any(
            excerpt is not None for excerpt in self.source_excerpts
        ):
            raise ValueError("目录项至少需要一段可核验的来源摘录")
        if self.source_excerpts and any(
            excerpt is not None and not excerpt.strip()
            for excerpt in self.source_excerpts
        ):
            raise ValueError("目录项来源摘录不得为空")
        return self


class FrozenProtocolCatalog(VersionedModel):
    """Agent 调用前冻结的只读目录（不可变）。

    ``official_parent_rules`` 目录项为官方父规则；``required_procedures`` 目录项
    按研究期别与访视实例拆分基线及以前的必做项目录。Agent、用户反馈和修复
    回路均不得增删目录成员。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    catalog_kind: CatalogKind
    study_phase: StudyPhase
    items: tuple[FrozenCatalogItem, ...] = Field(min_length=1)
    frozen_at: datetime
    frozen_by: str = Field(min_length=1)
    catalog_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_catalog(self) -> "FrozenProtocolCatalog":
        from app.domain.publication import canonical_hash

        expected = frozen_catalog_content_hash(self)
        current_shape_hash = canonical_hash(
            self.model_dump(mode="json", exclude={"catalog_sha256"})
        )
        if self.catalog_sha256 not in {expected, current_shape_hash}:
            raise ValueError("FrozenProtocolCatalog 哈希与目录内容不一致")
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("目录项 ID 必须唯一")
        positions = [item.position for item in self.items]
        if len(positions) != len(set(positions)):
            raise ValueError("目录项 position 必须唯一")
        for item in self.items:
            if self.catalog_kind == CatalogKind.OFFICIAL_PARENT_RULES:
                if item.kind != CatalogItemKind.PARENT_RULE:
                    raise ValueError("官方父规则目录只能包含 parent_rule 项")
                if not item.official_code:
                    raise ValueError("官方父规则目录项必须提供 official_code")
                if item.review_stage is not None:
                    raise ValueError("官方父规则目录项不能携带审核阶段")
            else:
                if item.kind != CatalogItemKind.REQUIRED_PROCEDURE:
                    raise ValueError("必做项目录只能包含 required_procedure 项")
                if not item.visit_instance:
                    raise ValueError("必做项目录项必须提供 visit_instance")
                if item.review_stage is None:
                    raise ValueError("必做项目录项必须提供结构化审核阶段")
            if len(item.source_span_ids) != len(set(item.source_span_ids)):
                raise ValueError("目录项来源片段引用不得重复")
        return self
