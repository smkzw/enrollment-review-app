"""标识值的保真检查；不依据疾病、项目或临床阈值分类。"""
from __future__ import annotations

import re
import unicodedata


def validate_identifier_value(raw, canonical, unit, assertion_text: str | None) -> None:
    if not isinstance(raw, str) or not raw.strip() or canonical != raw or unit is not None:
        raise ValueError("标识编号须用原样字符串保存，规范值与原值相同且无单位")
    if not assertion_text or raw not in assertion_text:
        raise ValueError("标识编号必须逐字出现在断言原句中")
    normalized = unicodedata.normalize("NFKC", raw)
    # 含小数或指数的纯数值不能仅凭模型标签改成编号。
    if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", normalized) and any(c in normalized for c in ".eE"):
        raise ValueError("标识编号呈测量数值形式，请保留为数值并核对单位")
    if normalized.isdecimal():
        source = unicodedata.normalize("NFKC", assertion_text)
        if re.search(r"(?<!\w)" + re.escape(normalized) + r"\s*[A-Za-zµμ%²³]", source):
            raise ValueError("标识编号原句含紧随数值的单位或字母，需核对其类型")
