"""受控 LibreOffice 渲染：DOCX -> 只读 PDF 派生物与 manifest。

- 固定版本 LibreOffice 无界面渲染，记录渲染器版本、参数、PDF 哈希与页数；
- 渲染页语义为「本次渲染第 N 页」，不冒充原作者环境中的绝对分页；
- 失败/降级保留结构化原因（:class:`ProtocolRenderArtifact.render_error`）。

PDF 页数与逐页文本由 pdfplumber（MIT 许可）读取。Phase 3 spike 实测
pdfplumber 0.11.10 在两份真实方案上页数与 PyMuPDF 完全一致，且来源对齐的
「未命中」块显著减少，故替换原 PyMuPDF 单一路径；遗留管线（``app/pipeline``）
继续使用 PyMuPDF，不在本切片范围。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pdfplumber

from app.domain.contracts.enums import RenderStatus
from app.domain.contracts.protocol_ingestion import (
    ProtocolRenderArtifact,
    ProtocolSourceArtifact,
)
from .ingestion import compute_sha256, utc_now

RENDERER_NAME = "libreoffice"
_DEFAULT_TIMEOUT = 300
_RENDER_STORAGE_PREFIX = "blobs/protocol_renders"

_ENV_LIBREOFFICE_BIN = "LIBREOFFICE_BIN"
_CANDIDATE_BINS = (
    "soffice",
    "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/opt/homebrew/bin/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
)


class RenderingError(RuntimeError):
    """LibreOffice 定位失败或渲染异常。"""


@dataclass(frozen=True)
class RenderResult:
    """一次渲染的中立结果：路径、哈希、页数、状态与结构化原因。"""

    pdf_path: Path | None
    pdf_sha256: str | None
    page_count: int | None
    status: RenderStatus
    render_error: str | None


def locate_libreoffice(bin_override: str | Path | None = None) -> Path:
    """定位 soffice 可执行文件；找不到抛 :class:`RenderingError`。"""
    if bin_override is not None:
        candidate = Path(bin_override)
        if candidate.is_file():
            return candidate
        raise RenderingError(f"指定的 LibreOffice 可执行文件不存在：{candidate}")

    env_bin = os.environ.get(_ENV_LIBREOFFICE_BIN)
    if env_bin:
        candidate = Path(env_bin)
        if candidate.is_file():
            return candidate

    for name in _CANDIDATE_BINS:
        if Path(name).is_file():
            return Path(name)
        found = shutil.which(name)
        if found:
            return Path(found)
    raise RenderingError(
        "未找到 LibreOffice（soffice）。请安装 LibreOffice 或设置 "
        f"{_ENV_LIBREOFFICE_BIN} 指向可执行文件。"
    )


def libreoffice_version(bin: str | Path | None = None) -> str:
    """返回 LibreOffice 版本字符串，如 ``26.2.5.2``。"""
    soffice = locate_libreoffice(bin)
    proc = subprocess.run(
        [str(soffice), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    line = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    if not line:
        raise RenderingError("无法读取 LibreOffice 版本信息。")
    # 形如 "LibreOffice 26.2.5.2 cd7284b4..."
    parts = line.split()
    if len(parts) >= 2 and parts[0].lower() == "libreoffice":
        return parts[1]
    return parts[0] if parts else line


def render_to_pdf(
    docx_path: str | Path,
    out_dir: str | Path,
    *,
    source_artifact: ProtocolSourceArtifact,
    bin: str | Path | None = None,
    renderer_version: str | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> RenderResult:
    """用受控 LibreOffice 将 DOCX 渲染为 PDF，返回 :class:`RenderResult`。

    源 DOCX 只读；PDF 仅写入 ``out_dir``。每次渲染使用独立用户配置目录，
    避免并发实例互相锁定。
    """
    source = Path(docx_path)
    if not source.is_file():
        raise RenderingError(f"待渲染文件不存在：{source}")
    actual_sha256 = compute_sha256(source)
    if actual_sha256 != source_artifact.sha256:
        raise RenderingError(
            "待渲染方案与登记文件哈希不一致，已停止渲染；请重新登记原始方案。"
        )
    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    soffice = locate_libreoffice(bin)
    version = renderer_version or libreoffice_version(soffice)

    # 渲染到本次专属的空目录，绝不把 out_dir（可能含陈旧/无关 PDF）当作
    # 产物来源；渲染完成后按精确文件名原子移动到 out_dir。这保证陈旧目录
    # 中的任何既有 PDF 都不可能被误选为本次渲染产物。
    with tempfile.TemporaryDirectory(prefix="lo_profile_") as profile_dir, \
            tempfile.TemporaryDirectory(prefix="lo_render_") as render_dir:
        render_dir_path = Path(render_dir)
        command = [
            str(soffice),
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(render_dir_path),
            f"-env:UserInstallation={Path(profile_dir).as_uri()}",
            str(source),
        ]
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return RenderResult(
                pdf_path=None,
                pdf_sha256=None,
                page_count=None,
                status=RenderStatus.FAILED,
                render_error=f"LibreOffice 渲染超时（>{timeout}s）",
            )

        stderr_tail = (proc.stderr or "").strip()
        expected_name = f"{source.stem}.pdf"
        produced = sorted(render_dir_path.glob("*.pdf"))
        pdf_path: Path | None = None
        for candidate in produced:
            if candidate.name == expected_name:
                pdf_path = candidate
                break
        if pdf_path is None and len(produced) == 1:
            # 目录里恰好只有一个全新产物时，接受唯一文件（文件名被渲染器改写的边界）。
            pdf_path = produced[0]

        if proc.returncode != 0 or pdf_path is None:
            reason = stderr_tail[-2000:] or f"LibreOffice 退出码 {proc.returncode}"
            return RenderResult(
                pdf_path=None,
                pdf_sha256=None,
                page_count=None,
                status=RenderStatus.FAILED,
                render_error=f"渲染失败（退出码 {proc.returncode}）：{reason}",
            )

        pdf_sha256 = compute_sha256(pdf_path)
        final_pdf = out_dir_path / _RENDER_STORAGE_PREFIX / f"{pdf_sha256}.pdf"
        final_pdf.parent.mkdir(parents=True, exist_ok=True)
        if final_pdf.is_file() and compute_sha256(final_pdf) == pdf_sha256:
            pdf_path.unlink()
        else:
            os.replace(pdf_path, final_pdf)
        pdf_path = final_pdf
        try:
            page_count = pdf_page_count(pdf_path)
        except RenderingError as exc:
            return RenderResult(
                pdf_path=pdf_path,
                pdf_sha256=pdf_sha256,
                page_count=None,
                status=RenderStatus.DEGRADED,
                render_error=f"渲染产物已生成但页数不可读：{exc}",
            )

        if page_count is not None and page_count < 1:
            return RenderResult(
                pdf_path=None,
                pdf_sha256=None,
                page_count=None,
                status=RenderStatus.FAILED,
                render_error=f"渲染产物页数为 {page_count}，不足 1 页，视为渲染失败",
            )

        if version and stderr_tail and _has_font_warning(stderr_tail):
            return RenderResult(
                pdf_path=pdf_path,
                pdf_sha256=pdf_sha256,
                page_count=page_count,
                status=RenderStatus.DEGRADED,
                render_error=f"渲染存在字体替换警告：{stderr_tail[-500:]}",
            )

        return RenderResult(
            pdf_path=pdf_path,
            pdf_sha256=pdf_sha256,
            page_count=page_count,
            status=RenderStatus.SUCCEEDED,
            render_error=None,
        )


def _has_font_warning(stderr_text: str) -> bool:
    lowered = stderr_text.lower()
    return ("warning" in lowered and "font" in lowered) or "font substitution" in lowered


def build_render_artifact(
    result: RenderResult,
    *,
    render_artifact_id: str,
    source_artifact: ProtocolSourceArtifact,
    renderer_version: str,
    storage_ref: str | None = None,
    render_params: dict | None = None,
    created_at: datetime | None = None,
) -> ProtocolRenderArtifact:
    """把 :class:`RenderResult` 装配为不可变 manifest 合同。

    ``storage_ref`` 为派生 PDF 的存储引用；渲染成功时由上层指定（缺省为 PDF
    路径），失败/降级不强制。渲染页语义即本次渲染页。
    """
    ref = storage_ref
    if ref is None and result.pdf_path is not None:
        ref = str(result.pdf_path.resolve())
    return ProtocolRenderArtifact(
        render_artifact_id=render_artifact_id,
        source_artifact_id=source_artifact.source_artifact_id,
        source_sha256=source_artifact.sha256,
        renderer=RENDERER_NAME,
        renderer_version=renderer_version,
        render_params=render_params
        or {"convert_to": "pdf", "headless": True, "norestore": True},
        pdf_sha256=result.pdf_sha256,
        page_count=result.page_count,
        status=result.status,
        storage_ref=ref,
        render_error=result.render_error,
        created_at=created_at or utc_now(),
    )


def pdf_page_count(pdf_path: str | Path) -> int:
    """读取 PDF 页数（pdfplumber）。"""
    path = Path(pdf_path)
    if not path.is_file():
        raise RenderingError(f"PDF 不存在：{path}")
    try:
        with pdfplumber.open(str(path)) as doc:
            return len(doc.pages)
    except Exception as exc:  # pdfminer.six 抛出多种底层异常
        raise RenderingError(f"PDF 读取失败：{exc}") from exc


def pdf_page_texts(pdf_path: str | Path) -> list[str]:
    """读取 PDF 逐页文本（pdfplumber），供来源对齐使用。"""
    path = Path(pdf_path)
    if not path.is_file():
        raise RenderingError(f"PDF 不存在：{path}")
    try:
        with pdfplumber.open(str(path)) as doc:
            return [(page.extract_text() or "") for page in doc.pages]
    except Exception as exc:
        raise RenderingError(f"PDF 文本读取失败：{exc}") from exc
