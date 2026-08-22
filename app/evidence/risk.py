"""确定性 OCR 风险扫描与冻结的阻断等级矩阵（Slice 4.0 验收基线）。

风险扫描只决定该页是否需要核对及发布门禁是否可继续，不修改文义、不产生
临床事实。冻结矩阵见 ``OCR_RISK_LEVEL_MATRIX``：可能改变极性、关键数值、
小数点、单位或日期解释的风险为 ``BLOCKING``（未核对阻止激活）；纯提示性
风险为 ``INFORMATIONAL``（随处理修订保留但不阻断）。

本模块是 Slice 4.0 的种子扫描器：用于冻结等级矩阵、运行种子集漏检/误报
度量；4.4 会在此基线上扩展支配范围、参考区间与跨页矛盾检测。
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256

from app.domain.contracts.enums import OcrRiskKind, OcrRiskLevel
from app.domain.contracts.ocr import OcrRiskFlag

OCR_RISK_RULE_VERSION = "slice4.6/v2"

# 冻结的风险等级矩阵（PRD P4-R08 / 验收 P4-AC07）。
OCR_RISK_LEVEL_MATRIX: dict[OcrRiskKind, OcrRiskLevel] = {
    OcrRiskKind.NEGATION_POLARITY: OcrRiskLevel.BLOCKING,
    OcrRiskKind.NUMERIC_VALUE: OcrRiskLevel.BLOCKING,
    OcrRiskKind.DECIMAL_POINT: OcrRiskLevel.BLOCKING,
    OcrRiskKind.UNIT: OcrRiskLevel.BLOCKING,
    OcrRiskKind.DATE: OcrRiskLevel.BLOCKING,
    OcrRiskKind.REPEATED_TEXT: OcrRiskLevel.INFORMATIONAL,
    OcrRiskKind.OUTPUT_REPETITION: OcrRiskLevel.BLOCKING,
    OcrRiskKind.LOW_CONFIDENCE: OcrRiskLevel.INFORMATIONAL,
}

_SEVERE_REPETITION_MIN_COUNT = 8
_SEVERE_REPETITION_MIN_SHARE = 0.30

# 否定/肯定极性标记（未配对 无/有 等易误报词，避免页面级误报超限）。
# 复合短语先匹配，避免“未见异常”同时拆成两个同类风险片段。
_POLARITY_RE = re.compile(
    r"(未见(?:异常)?|否认|确认|可见|阴性|阳性|正常|异常|"
    r"未使用|已使用|未接受|已接受|未接种|已接种)"
)

# 数值：整数或小数；含小数点时额外标记 DECIMAL_POINT。
_NUMERIC_RE = re.compile(r"\d+(?:\.\d+)?")

# 临床单位（不含 年/月/日/天/周/月/岁 等日期/年龄上下文词）。
_UNIT_RE = re.compile(
    r"(mg/dL|mg/dl|ug/L|μg/L|µg/L|U/L|u/L|IU/L|mmol/L|umol/L|μmol/L|µmol/L|"
    r"ng/mL|pg/mL|g/L|mmHg|cmH2O|%)"
)

# 完整/部分日期：ISO 短横/斜杠或中文年月日。
_DATE_RE = re.compile(
    r"((?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2})(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?"
    r"|(?:\d{4}年\d{1,2}月\d{1,2}日)"
    r"|(?:\d{4}[-/.]\d{1,2})"
    r"|(?:\d{4}年\d{1,2}月))"
)

_IDENTIFIER_VALUE_RE = re.compile(
    r"(?:门诊号|住院号|病历号|样本号|床号|报告号|申请号|编号|ID|No\.?)"
    r"\s*[:：]?\s*[A-Za-z0-9._/-]+",
    flags=re.IGNORECASE,
)

# 校对变化中的逻辑连接词不属于 OCR 页风险项，但“且/或”“任一/全部”等
# 变化会直接改变规则或病历陈述的逻辑含义，必须与其它关键语义一起进入确认门禁。
_SEMANTIC_CONNECTOR_RE = re.compile(
    r"(并且|以及|同时|任一|任意|全部|所有|至少|至多|且|或|和)"
)


@dataclass(frozen=True)
class _Match:
    kind: OcrRiskKind
    text: str
    start: int
    end: int
    detail: str | None = None


def _risk_id(kind: OcrRiskKind, start: int, end: int) -> str:
    digest = sha256(
        f"{kind.value}:{start}:{end}:{OCR_RISK_RULE_VERSION}".encode()
    ).hexdigest()
    return f"risk-{digest[:16]}"


def _scan_polarity(text: str) -> list[_Match]:
    return [
        _Match(OcrRiskKind.NEGATION_POLARITY, m.group(0), m.start(), m.end())
        for m in _POLARITY_RE.finditer(text)
    ]


def _scan_numeric(text: str) -> list[_Match]:
    matches: list[_Match] = []
    identifier_ranges = [
        (match.start(), match.end()) for match in _IDENTIFIER_VALUE_RE.finditer(text)
    ]
    for m in _NUMERIC_RE.finditer(text):
        prefix = text[max(0, m.start() - 16) : m.start()]
        suffix = text[m.end() : m.end() + 8]
        if any(start <= m.start() and m.end() <= end for start, end in identifier_ranges):
            continue
        if re.search(r"(?:第|共)\s*$", prefix) and re.match(r"\s*页", suffix):
            continue
        matches.append(_Match(OcrRiskKind.NUMERIC_VALUE, m.group(0), m.start(), m.end()))
        if "." in m.group(0):
            decimal_start = m.start() + m.group(0).index(".")
            matches.append(
                _Match(
                    OcrRiskKind.DECIMAL_POINT,
                    ".",
                    decimal_start,
                    decimal_start + 1,
                    detail="含小数点的数值，小数点位置影响数量级解释",
                )
            )
    return matches


def _scan_unit(text: str) -> list[_Match]:
    return [
        _Match(OcrRiskKind.UNIT, m.group(0), m.start(), m.end())
        for m in _UNIT_RE.finditer(text)
    ]


def _scan_date(text: str) -> list[_Match]:
    # OCR 常混入“⽉/⽇”等康熙部首或兼容字。逐字符规范化且只接受
    # 一对一替换，既可识别日期，又保持所有原始字符位置可回放。
    shadow = "".join(
        normalized if len(normalized := unicodedata.normalize("NFKC", char)) == 1 else char
        for char in text
    )
    return [
        _Match(OcrRiskKind.DATE, text[m.start() : m.end()], m.start(), m.end())
        for m in _DATE_RE.finditer(shadow)
    ]


def _scan_repeated_text(text: str) -> list[_Match]:
    seen: dict[str, int] = {}
    first_index: dict[str, int] = {}
    for match in re.finditer(r"^[^\n]+$", text, flags=re.MULTILINE):
        line = match.group(0).strip()
        if len(line) < 4:
            continue
        if line in seen:
            if seen[line] == 1:
                start = first_index[line]
                end = start + len(line)
                return [
                    _Match(
                        OcrRiskKind.REPEATED_TEXT,
                        line,
                        start,
                        end,
                        detail="页面存在完全重复的文本行，可能影响定位消歧与阅读顺序",
                    )
                ]
        else:
            seen[line] = 1
            first_index[line] = match.start() + (len(match.group(0)) - len(match.group(0).lstrip()))
    return []


def _scan_output_repetition(text: str) -> list[_Match]:
    """Detect model-output loops that make the whole page unreliable.

    Ordinary duplicated headers remain informational. A line must repeat at
    least eight times and occupy at least 30% of non-empty lines before this
    page-level quality guard fires. The single blocking item deliberately
    replaces token-level risks: numbers inside a hallucinated loop must not
    become hundreds of manual review tasks.
    """
    lines: list[tuple[str, str, int, int]] = []
    for match in re.finditer(r"^[^\n]+$", text, flags=re.MULTILINE):
        raw_line = match.group(0)
        line = raw_line.strip()
        if len(line) < 4:
            continue
        offset = len(raw_line) - len(raw_line.lstrip())
        start = match.start() + offset
        comparison_line = re.sub(r"^\d+\s*[.)、．]\s*", "", line).strip()
        if len(comparison_line) < 4:
            continue
        lines.append((comparison_line, line, start, start + len(line)))
    if not lines:
        return []

    counts = Counter(comparison_line for comparison_line, _, _, _ in lines)
    comparison_line, count = counts.most_common(1)[0]
    if (
        count < _SEVERE_REPETITION_MIN_COUNT
        or count / len(lines) < _SEVERE_REPETITION_MIN_SHARE
    ):
        return []
    _, line, start, end = next(
        item for item in lines if item[0] == comparison_line
    )
    return [
        _Match(
            OcrRiskKind.OUTPUT_REPETITION,
            text[start:end],
            start,
            end,
            detail=(
                f"同一文本行重复出现{count}次，已超过页面质量阈值。"
                "本页识别结果可能失真，请重新识别或对照原件校对整页后再继续。"
            ),
        )
    ]


def _deduplicate_overlapping_matches(matches: list[_Match]) -> list[_Match]:
    """Keep the longest first match when one risk category overlaps itself."""
    accepted: list[_Match] = []
    for match in sorted(matches, key=lambda item: (item.start, -(item.end - item.start))):
        if any(
            item.kind == match.kind
            and item.start < match.end
            and match.start < item.end
            for item in accepted
        ):
            continue
        accepted.append(match)
    return accepted


def scan_ocr_risks(text: str, *, rule_version: str = OCR_RISK_RULE_VERSION) -> list[OcrRiskFlag]:
    """扫描文本并返回结构化风险项（按出现顺序，kind 稳定）。"""
    if rule_version != OCR_RISK_RULE_VERSION:
        raise ValueError(f"不支持的扫描规则版本: {rule_version}")
    severe_repetition = _scan_output_repetition(text)
    if severe_repetition:
        match = severe_repetition[0]
        return [
            OcrRiskFlag(
                risk_id=_risk_id(match.kind, match.start, match.end),
                kind=match.kind,
                level=OCR_RISK_LEVEL_MATRIX[match.kind],
                text=match.text,
                text_start=match.start,
                text_end=match.end,
                detail=match.detail,
                rule_version=rule_version,
            )
        ]

    matches: list[_Match] = []
    matches.extend(_deduplicate_overlapping_matches(_scan_polarity(text)))
    matches.extend(_scan_numeric(text))
    matches.extend(_scan_unit(text))
    matches.extend(_scan_date(text))
    matches.extend(_scan_repeated_text(text))
    # 日期整体已作为 DATE 风险标记；其内部数字不再重复作为数值/小数风险。
    date_ranges = [(m.start, m.end) for m in matches if m.kind == OcrRiskKind.DATE]
    matches = [
        m
        for m in matches
        if m.kind not in {OcrRiskKind.NUMERIC_VALUE, OcrRiskKind.DECIMAL_POINT}
        or not any(ds <= m.start and m.end <= de for ds, de in date_ranges)
    ]
    matches.sort(key=lambda m: (m.start, m.end, m.kind.value))

    flags: list[OcrRiskFlag] = []
    for m in matches:
        flags.append(
            OcrRiskFlag(
                risk_id=_risk_id(m.kind, m.start, m.end),
                kind=m.kind,
                level=OCR_RISK_LEVEL_MATRIX[m.kind],
                text=m.text,
                text_start=m.start,
                text_end=m.end,
                detail=m.detail,
                rule_version=rule_version,
            )
        )
    return flags


def would_block_activation(risk_items: list[OcrRiskFlag]) -> bool:
    """任一 BLOCKING 风险未核对时阻止证据处理修订激活。"""
    return any(item.level == OcrRiskLevel.BLOCKING for item in risk_items)


def allows_risk_review(flag: OcrRiskFlag) -> bool:
    """Whether a user decision can resolve this risk without replacing text."""
    return flag.kind != OcrRiskKind.OUTPUT_REPETITION


def correction_covers_risk(
    flag: OcrRiskFlag,
    *,
    correction_text_start: int,
    correction_text_end: int,
    page_text_length: int,
) -> bool:
    """Apply the risk-specific correction closure rule.

    Token risks are resolved only when the normalized changed range overlaps the
    token. An insertion must be strictly inside the token; inserting immediately
    before or after a token does not alter it. Severe model output
    repetition invalidates the page as a whole, so only a whole-page correction
    can resolve it.
    """
    if flag.kind == OcrRiskKind.OUTPUT_REPETITION:
        return correction_text_start == 0 and correction_text_end == page_text_length
    if correction_text_start == correction_text_end:
        return flag.text_start < correction_text_start < flag.text_end
    return max(correction_text_start, flag.text_start) < min(
        correction_text_end, flag.text_end
    )


def critical_semantics_changed(original_text: str, corrected_text: str) -> bool:
    """校对前后是否改变了需逐字确认的临床语义元素。

    用户选择的变化类别是审计说明，不是安全门禁的唯一依据。这里比较实际
    文本中的极性、数值、小数点、单位、日期和逻辑连接词多重集合；补入整行
    漏识别文字时同样适用，避免误选“其他文字”绕过关键确认。
    """

    def signature(text: str) -> Counter[tuple[str, str]]:
        values: Counter[tuple[str, str]] = Counter(
            (flag.kind.value, flag.text)
            for flag in scan_ocr_risks(text)
            if flag.level == OcrRiskLevel.BLOCKING
        )
        values.update(
            ("semantic_connector", match.group(0))
            for match in _SEMANTIC_CONNECTOR_RE.finditer(text)
        )
        return values

    return signature(original_text) != signature(corrected_text)
