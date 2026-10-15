"""DOCX / legacy DOC -> PDF 的 LibreOffice 无头转换适配器（Slice 4.3，worker_02）。

生产路径用 ``soffice --headless --convert-to pdf`` 把 DOCX/DOC 字节转为可渲染
PDF 字节。``converter_version`` 是稳定转换器/版本身份，参与 DOCX/DOC 页的派生
输入身份（``paging.derived_doc_input_sha256``）：同内容同版本必须复用同一页身份
与 OCR 缓存（P4-R03），版本变化必须改变页身份。

错误契约：``DocConversionError.message`` 只含**已净化的稳定中文领域措辞**
（可进入失败页原因）；退出码、stderr 与内部异常细节放入 ``technical_detail``，
归 worker_03 尝试/任务技术记录，绝不进入领域失败文本。

本模块只做转换与错误归类，不参与 OCR/门禁/存储；测试注入确定性 fake 转换器。
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.evidence.paging import DocConversionError

_UNKNOWN_VERSION = "libreoffice/unknown"


class LibreOfficeDocConverter:
    """基于 LibreOffice 无头命令的 DOCX/DOC 转换器。"""

    def __init__(self, soffice_bin: str | None = None) -> None:
        self.soffice_bin = soffice_bin or shutil.which("soffice")
        self.converter_version = self._detect_version()

    def _detect_version(self) -> str:
        """探测 soffice 版本作为稳定转换器身份；失败时显式 unknown。"""
        if not self.soffice_bin:
            return _UNKNOWN_VERSION
        try:
            result = subprocess.run(
                [self.soffice_bin, "--version"],
                capture_output=True,
                timeout=15,
                check=False,
            )
        except Exception:  # noqa: BLE001 - 版本探测失败不影响转换主路径
            return _UNKNOWN_VERSION
        if result.returncode != 0:
            return _UNKNOWN_VERSION
        first = result.stdout.decode("utf-8", errors="replace").strip().splitlines()
        return f"libreoffice/{first[0]}" if first else _UNKNOWN_VERSION

    def convert_to_pdf(self, content: bytes, *, suffix: str) -> bytes:
        if not self.soffice_bin:
            raise DocConversionError(
                "文档转换不可用，缺少文档转换程序",
                technical_detail="soffice binary not on PATH",
            )
        with tempfile.TemporaryDirectory(prefix="phase4-doc-convert-") as tmp:
            source = Path(tmp) / f"input{suffix}"
            source.write_bytes(content)
            result = subprocess.run(
                [
                    self.soffice_bin,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    tmp,
                    str(source),
                ],
                capture_output=True,
                timeout=120,
                check=False,
            )
            output = Path(tmp) / "input.pdf"
            if result.returncode != 0 or not output.is_file():
                stderr = result.stderr.decode("utf-8", errors="replace").strip()
                raise DocConversionError(
                    "文档转换失败，无法生成可处理页面",
                    technical_detail=(
                        f"exit={result.returncode}"
                        + (f" stderr={stderr}" if stderr else "")
                    ),
                )
            return output.read_bytes()
