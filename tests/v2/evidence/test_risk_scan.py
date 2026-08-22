"""风险扫描种子集测试：冻结矩阵、漏检 0、页面级误报 ≤10%。"""
from __future__ import annotations

from app.domain.contracts.enums import OcrRiskKind, OcrRiskLevel
from app.evidence import (
    evaluate_risk_seed,
    risk,
    scan_ocr_risks,
    text,
    would_block_activation,
)
from app.evidence.risk import (
    allows_risk_review,
    correction_covers_risk,
    critical_semantics_changed,
)


def test_frozen_risk_level_matrix() -> None:
    blocking = {
        OcrRiskKind.NEGATION_POLARITY,
        OcrRiskKind.NUMERIC_VALUE,
        OcrRiskKind.DECIMAL_POINT,
        OcrRiskKind.UNIT,
        OcrRiskKind.DATE,
        OcrRiskKind.OUTPUT_REPETITION,
    }
    for kind, level in risk.OCR_RISK_LEVEL_MATRIX.items():
        expected = (
            OcrRiskLevel.BLOCKING if kind in blocking else OcrRiskLevel.INFORMATIONAL
        )
        assert level == expected, kind


def test_risk_categories_detected() -> None:
    flags = scan_ocr_risks("否认高血压病史，血肌酐 76.1 umol/L，日期 2026-08-19。")
    kinds = {f.kind for f in flags}
    assert OcrRiskKind.NEGATION_POLARITY in kinds
    assert OcrRiskKind.NUMERIC_VALUE in kinds
    assert OcrRiskKind.DECIMAL_POINT in kinds
    assert OcrRiskKind.UNIT in kinds
    assert OcrRiskKind.DATE in kinds
    assert would_block_activation(flags)


def test_correction_semantic_delta_detects_content_not_declared_category() -> None:
    assert critical_semantics_changed(
        "",
        "参与者否认2026-03-10使用过药物，剂量5 mg/dL。",
    )
    assert critical_semantics_changed("满足A且B", "满足A或B")
    assert not critical_semantics_changed("ALT", "丙氨酸氨基转移酶")


def test_risk_ranges_do_not_duplicate_date_or_decimal_text() -> None:
    text = "未见异常，结果 76.1 mg/dL，日期 2026-08-19。"
    flags = scan_ocr_risks(text)
    decimal_flags = [flag for flag in flags if flag.kind == OcrRiskKind.DECIMAL_POINT]
    assert len(decimal_flags) == 1
    assert (decimal_flags[0].text, decimal_flags[0].text_start, decimal_flags[0].text_end) == (
        ".",
        text.index("."),
        text.index(".") + 1,
    )
    polarity_flags = [flag for flag in flags if flag.kind == OcrRiskKind.NEGATION_POLARITY]
    assert [flag.text for flag in polarity_flags] == ["未见异常"]
    date_range = next(flag for flag in flags if flag.kind == OcrRiskKind.DATE)
    assert not any(
        flag.kind in {OcrRiskKind.NUMERIC_VALUE, OcrRiskKind.DECIMAL_POINT}
        and date_range.text_start <= flag.text_start
        and flag.text_end <= date_range.text_end
        for flag in flags
    )


def test_date_components_not_double_flagged_as_numeric(gold_set) -> None:
    flags = scan_ocr_risks("于2026年8月19日完成访视。")
    kinds = {f.kind for f in flags}
    assert OcrRiskKind.DATE in kinds
    # 日期整体只算 DATE，其内部数字不再重复标记为数值风险。
    numeric = [f for f in flags if f.kind in {OcrRiskKind.NUMERIC_VALUE, OcrRiskKind.DECIMAL_POINT}]
    assert numeric == []


def test_compatibility_date_characters_are_detected_without_changing_offsets() -> None:
    text = "知情同意日期：2026年08⽉21⽇。"
    flags = scan_ocr_risks(text)
    date = next(flag for flag in flags if flag.kind == OcrRiskKind.DATE)
    assert date.text == "2026年08⽉21⽇"
    assert text[date.text_start : date.text_end] == date.text
    assert not any(
        flag.kind in {OcrRiskKind.NUMERIC_VALUE, OcrRiskKind.DECIMAL_POINT}
        and date.text_start <= flag.text_start
        and flag.text_end <= date.text_end
        for flag in flags
    )


def test_report_identifiers_pagination_and_dotted_datetime_are_not_split_into_risks() -> None:
    text = (
        "年龄:64岁 门诊号:330859 样本号:260511TSP00023 "
        "结果0.00 参考区间0-6 采集时间:2026.05.11 11:11 第1页,共1页"
    )
    flags = scan_ocr_risks(text)
    numeric_texts = [
        flag.text for flag in flags if flag.kind == OcrRiskKind.NUMERIC_VALUE
    ]
    assert numeric_texts == ["64", "0.00", "0", "6"]
    date = next(flag for flag in flags if flag.kind == OcrRiskKind.DATE)
    assert date.text == "2026.05.11 11:11"
    assert not any(
        identifier in [flag.text for flag in flags]
        for identifier in ("330859", "260511", "00023")
    )


def test_compact_lab_analyte_values_are_not_mistaken_for_identifiers() -> None:
    flags = scan_ocr_risks("ALT32.5U/L AST28.0U/L 血红蛋白128g/L")
    numeric_texts = [
        flag.text for flag in flags if flag.kind == OcrRiskKind.NUMERIC_VALUE
    ]
    assert numeric_texts == ["32.5", "28.0", "128"]


def test_repeated_text_is_informational() -> None:
    flags = scan_ocr_risks("再次确认：受试者已签署知情同意书。\n再次确认：受试者已签署知情同意书。")
    repeated = [f for f in flags if f.kind == OcrRiskKind.REPEATED_TEXT]
    assert repeated
    assert repeated[0].level == OcrRiskLevel.INFORMATIONAL
    # 只有提示性风险不阻断激活。
    assert not would_block_activation([repeated[0]])


def test_pathological_output_repetition_becomes_one_page_level_blocker() -> None:
    text = "\n".join(
        ["1. 姓名：测试", "2. 检验项目：肌酸激酶"]
        + [f"{index}. 结果：≤197" for index in range(3, 13)]
    )

    flags = scan_ocr_risks(text)

    assert len(flags) == 1
    assert flags[0].kind == OcrRiskKind.OUTPUT_REPETITION
    assert flags[0].level == OcrRiskLevel.BLOCKING
    assert "重复出现10次" in (flags[0].detail or "")
    assert would_block_activation(flags)


def test_frequent_but_non_pathological_headers_keep_normal_risk_scanning() -> None:
    text = "\n".join(
        ["报告标题"] * 7
        + [f"检验项目{i}：结果 {i}.0 mg/dL" for i in range(20)]
    )

    flags = scan_ocr_risks(text)

    assert not any(flag.kind == OcrRiskKind.OUTPUT_REPETITION for flag in flags)
    assert any(flag.kind == OcrRiskKind.NUMERIC_VALUE for flag in flags)


def test_output_repetition_requires_whole_page_correction() -> None:
    text = "\n".join(f"{index}. 结果：≤197" for index in range(1, 11))
    flag = scan_ocr_risks(text)[0]

    assert not allows_risk_review(flag)
    assert not correction_covers_risk(
        flag,
        correction_text_start=flag.text_start,
        correction_text_end=flag.text_end,
        page_text_length=len(text),
    )
    assert correction_covers_risk(
        flag,
        correction_text_start=0,
        correction_text_end=len(text),
        page_text_length=len(text),
    )


def test_token_risk_requires_actual_normalized_overlap() -> None:
    flag = next(
        item
        for item in scan_ocr_risks("ALT 5.6 mmol/L")
        if item.kind == OcrRiskKind.NUMERIC_VALUE
    )

    assert not correction_covers_risk(
        flag,
        correction_text_start=0,
        correction_text_end=1,
        page_text_length=14,
    )
    assert not correction_covers_risk(
        flag,
        correction_text_start=flag.text_end,
        correction_text_end=flag.text_end,
        page_text_length=14,
    )
    assert not correction_covers_risk(
        flag,
        correction_text_start=flag.text_start,
        correction_text_end=flag.text_start,
        page_text_length=14,
    )
    assert correction_covers_risk(
        flag,
        correction_text_start=flag.text_start + 1,
        correction_text_end=flag.text_start + 1,
        page_text_length=14,
    )


def test_clean_pages_not_flagged(gold_set) -> None:
    flags_by_page = {}
    for page in gold_set.pages:
        if page.gold_page_id.startswith("risk-clean"):
            flags_by_page[page.gold_page_id] = scan_ocr_risks(page.expected_text or "")
    assert all(not flags for flags in flags_by_page.values())


def test_risk_seed_metric_miss_zero_and_fp_within_ten_percent(gold_set, gold_root) -> None:
    """种子集验收：关键风险漏检 0、页面级误报率 ≤10%（P4-AC07）。"""
    from app.evidence import extract_native_page

    flags_by_page: dict[str, list] = {}
    scoped: list[str] = []
    for page in gold_set.pages:
        if page.expects_failure or page.expected_text is None:
            continue
        scoped.append(page.gold_page_id)
        if page.route is None:
            decoded = text.decode_text_bytes((gold_root / page.file_ref).read_bytes())
            page_text = decoded.text
        elif page.route.value == "native_pdf_text":
            native = extract_native_page(gold_root / page.file_ref, page.page_number - 1)
            page_text = native.text
        else:
            # Vision/rendered routes are not an OCR capability claim here; use
            # the independently authored gold transcription to test the risk
            # scanner's frozen categories across every eligible page.
            page_text = page.expected_text
        flags_by_page[page.gold_page_id] = scan_ocr_risks(page_text)
    result = evaluate_risk_seed(gold_set, flags_by_page, page_ids=scoped)
    assert result.miss_count == 0, "关键风险漏检必须为 0"
    assert result.fp_rate <= 0.10, f"页面级误报率 {result.fp_rate:.2%} 超过 10%"
    assert result.total_gold_kinds == 26
    assert result.clean_pages == 13
    assert result.risk_pages == 10
    assert result.processed_pages == result.eligible_pages == 23
    assert result.unprocessed_page_ids == ()
