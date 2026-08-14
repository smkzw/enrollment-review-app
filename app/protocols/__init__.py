"""方案文档提取层（Phase 3 切片 1）。

设计书 §4.1「文档提取器」的结构通道与渲染通道边界：

- ``ingestion``        原始文件登记、SHA-256、MIME/格式检查；
- ``docx_structure``   DOCX 段落/表格/嵌套表格/编号/页眉页脚/section/修订标记；
- ``rendering``        受控 LibreOffice 派生物 PDF 与 manifest；
- ``source_alignment`` 结构块到渲染页/文本范围对齐。

本层只产出 :mod:`app.domain.contracts.protocol_ingestion` 中的不可变合同，
不承载规则语义或发布权威，不写数据库（持久化由上层服务注入仓储完成）。
"""
from __future__ import annotations

from .docx_structure import (
    BlockKind,
    HeaderFooterKind,
    NumberingRef,
    StructureBlock,
    StructureExtraction,
    block_set_hash,
    extract_docx_structure,
    parse_numbering,
    serialize_blocks,
)
from .ingestion import (
    ProtocolFileKind,
    SourceIngestionError,
    compute_sha256,
    detect_format,
    register_source_artifact,
    utc_now,
)
from .rendering import (
    RenderResult,
    build_render_artifact,
    libreoffice_version,
    locate_libreoffice,
    pdf_page_count,
    pdf_page_texts,
    render_to_pdf,
)
from .source_alignment import (
    AlignmentResult,
    align_blocks,
    find_block_by_ref,
    verify_excerpt_against_blocks,
)

__all__ = [
    "AlignmentResult",
    "BlockKind",
    "HeaderFooterKind",
    "NumberingRef",
    "ProtocolFileKind",
    "RenderResult",
    "SourceIngestionError",
    "StructureBlock",
    "StructureExtraction",
    "align_blocks",
    "block_set_hash",
    "build_render_artifact",
    "compute_sha256",
    "detect_format",
    "extract_docx_structure",
    "find_block_by_ref",
    "libreoffice_version",
    "locate_libreoffice",
    "parse_numbering",
    "pdf_page_count",
    "pdf_page_texts",
    "register_source_artifact",
    "render_to_pdf",
    "serialize_blocks",
    "utc_now",
    "verify_excerpt_against_blocks",
]
