"""Candidate agreement distinguishes values, units, rows and date titles."""
from copy import deepcopy

import pytest

from app.domain.contracts.local_region_read import LocalRegionReadCandidate
from app.evidence.local_region_comparison import compare_local_region_read, region_ocr_fields


def _item(label="示例项目", value="4.04", unit="10⁹/L", reference="3.50--9.50", **extra):
    return {"label": label, "raw_value": value, "raw_unit": unit, "reference_text": reference,
            "time_label": None, "excerpt": f"{label} {value} {unit or ''}", "position": "区域内一行",
            "script": "printed", "legibility": "clear", "annotation_target": None, **extra}


def _compare(text, items):
    return compare_local_region_read(text, LocalRegionReadCandidate(items=items, unresolved=[]))


def _table(unit="10^9/L", value="4.04", reference="3.50--9.50", repeat=False):
    row = f"<tr><td>示例项目</td><td>{value}</td><td>{reference}</td><td>{unit}</td></tr>"
    return "<table><tr><td>项目</td><td>结果</td><td>参考范围</td><td>单位</td></tr>" + row * (2 if repeat else 1) + "</table>"


def test_clear_equivalent_value_is_only_unaccepted_transcription_candidate():
    result = _compare(_table(), [_item(value="4.040")])
    assert result["items"][0]["status"] == "consistent_transcription_candidate"
    assert result["candidate_only"] and not result["formal_adoption_authorized"]
    assert not result["source_position_verified"]
    assert not result["items"][0]["source_position_verified"]


@pytest.mark.parametrize("label_header,result_header,reference_header,unit_header", [
    ("名称", "结果", "参考范围", "单位"),
    ("检验项目", "测定结果", "参考区间", "结果单位"),
    ("项目名称", "检验结果", "参考值", "单位"),
])
def test_explicit_column_aliases_preserve_values_in_reordered_table(
    label_header, result_header, reference_header, unit_header,
):
    text = (f"<table><tr><td>{unit_header}</td><td>{reference_header}</td>"
            f"<td>No.</td><td>{label_header}</td><td>{result_header}</td></tr>"
            "<tr><td>10^9/L</td><td>3.50--9.50</td><td>1</td>"
            "<td>示例项目</td><td>4.04</td></tr></table>")
    result = _compare(text, [_item()])
    assert result["contract"] == "local-region-transcript-comparison/v7"
    assert result["items"][0]["status"] == "consistent_transcription_candidate"
    assert result["candidate_only"] and not result["source_position_verified"]


@pytest.mark.parametrize("headers", [
    ("项目", "名称", "结果", "参考范围", "单位"),
    ("项目", "结果", "参考范围", "参考值", "单位"),
    ("自定义名称", "结果", "参考范围", "单位"),
])
def test_ambiguous_or_unknown_header_is_not_guessed(headers):
    text = "<table><tr>" + "".join(f"<td>{value}</td>" for value in headers) + "</tr></table>"
    fields, gaps = region_ocr_fields(text)
    assert fields == [] and gaps


def test_name_header_does_not_erase_marker_unit_sign_or_column_shift():
    text = _table(unit="10^-9/L").replace("<td>项目</td>", "<td>名称</td>")
    fields, gaps = region_ocr_fields(text)
    assert not gaps and fields[0].raw_unit == "10^-9/L"
    assert "单位不一致或未读全" in _compare(text, [_item()])["items"][0]["reasons"]
    marked = text.replace("<td>示例项目</td>", "<td>★示例项目</td>")
    assert _compare(marked, [_item()])["items"][0]["status"] == "unresolved"
    shifted = _table(unit="", value="39.0↓", reference="40.0--75.0%").replace(
        "<td>项目</td>", "<td>名称</td>",
    )
    reasons = _compare(shifted, [_item(value="39.0↓", unit="%", reference="40.0--75.0")])["items"][0]["reasons"]
    assert "单位不一致或未读全" in reasons and "参考范围未能对应" in reasons


@pytest.mark.parametrize("header,prefix", [
    ("项目 结果 参考范围 单位", ""),
    ("No. 代号 名称 结果 参考范围 单位", "1 CODE "),
    ("序号 代码 检验项目 测定结果 参考区间 结果单位", "1 CODE "),
])
def test_explicit_plain_columns_preserve_complete_literal_row(header, prefix):
    row = prefix + "示例项目 4.04 3.50--9.50 10^9/L"
    result = _compare(header + "\n" + row, [_item(excerpt=row)])
    assert result["items"][0]["status"] == "consistent_transcription_candidate"
    assert result["items"][0]["ocr_excerpt"] == row
    assert not result["unresolved"] and not result["unmatched_ocr"]
    assert not result["source_position_verified"] and not result["formal_adoption_authorized"]


@pytest.mark.parametrize("text", [
    "示例项目 4.04 3.50--9.50 10^9/L",
    "自定义名称 结果 参考范围 单位\n示例项目 4.04 3.50--9.50 10^9/L",
    "项目 结果 参考范围 单位\n示例项目 4.04 10^9/L 3.50--9.50",
    "项目 结果 参考范围 单位\n示例项目4.04 3.50--9.50 10^9/L",
    "项目 结果 参考范围 单位\n说明文字\n示例项目 4.04 3.50--9.50 10^9/L",
    "项目 结果 参考范围 单位\n示例项目 4.04 3.50--9.50",
    "项目 结果 参考范围 单位\n示例项目 4.04 3.50--9.50 10^9/L\n示例项目 4.04 3.50--9.50 10^9/L",
])
def test_plain_column_ambiguity_is_not_filled_from_neighbor(text):
    assert _compare(text, [_item()])["items"][0]["status"] == "unresolved"


def test_missing_plain_unit_is_unresolved_even_when_both_readers_omit_it():
    text = "项目 结果 参考范围 单位\n示例项目 4.04 3.50--9.50"
    result = _compare(text, [_item(unit=None)])
    assert "单位列未完整读取" in result["items"][0]["reasons"]
    assert result["unresolved"]


def test_plain_marker_omission_in_display_requires_the_complete_literal_row():
    row = "1 CODE ★示例项目 4.04 3.50--9.50 10^9/L"
    source = "No. 代号 名称 结果 参考范围 单位\n" + row
    assert _compare(source, [_item(excerpt=row)])["items"][0]["status"] == "consistent_transcription_candidate"
    for change in ({"excerpt": row.replace("★", "")}, {"raw_value": "4.05"},
                   {"raw_unit": "10^-9/L"}, {"raw_value": "4.04↑"}):
        item = _item(excerpt=row)
        item.update(change)
        assert _compare(source, [item])["items"][0]["status"] == "unresolved"
    for marker in ("疑似", "↑"):
        marked = source.replace("★", marker)
        assert _compare(marked, [_item(excerpt=row.replace("★", marker))])["items"][0]["status"] == "unresolved"


@pytest.mark.parametrize("missing_unit_header", [False, True])
def test_repeated_numbered_headers_keep_each_group_literal_and_unknown_columns(missing_unit_header):
    header = "No. 代号 名称 结果 参考范围 单位 No. 代号 名称 结果 参考范围"
    if not missing_unit_header:
        header += " 单位"
    first = "7 CODE_A ★示例项目 4.04 3.50--9.50 10^9/L"
    second = "21 CODE_B 另一项目 2 1--3 mg/L"
    result = _compare(header + "\n" + first + " " + second, [
        _item(excerpt=first), _item("另一项目", "2", "mg/L", "1--3", excerpt=second),
    ])
    assert result["items"][0]["status"] == "consistent_transcription_candidate"
    assert result["items"][0]["ocr_excerpt"] == first
    assert result["items"][1]["status"] == ("unresolved" if missing_unit_header else "consistent_transcription_candidate")
    assert bool(result["unresolved"]) == missing_unit_header
    if missing_unit_header:
        assert second in result["unresolved"][0]
        assert result["items"][1]["ocr_excerpt"] is None
    else:
        assert result["items"][1]["ocr_excerpt"] == second
    assert not result["formal_adoption_authorized"] and not result["source_position_verified"]


def test_repeated_headers_do_not_merge_equal_labels_or_borrow_units():
    header = "序号 代码 检验项目 测定结果 参考区间 结果单位 " * 2
    first = "1 A 示例项目 4.04 3.50--9.50"
    second = "2 B 示例项目 4.04 3.50--9.50 10^9/L"
    result = _compare(header + "\n" + first + " " + second, [_item()])
    assert result["items"][0]["status"] == "unresolved"
    assert result["unresolved"] and "项目不能唯一对应" in result["items"][0]["reasons"]
    fields, _ = region_ocr_fields(header + "\n" + first + " " + second)
    assert fields[0].raw_unit is None and fields[0].requires_review
    assert fields[1].raw_unit == "10^9/L"


@pytest.mark.parametrize("row", [
    "1 A 示例项目4.04 3.50--9.50 10^9/L 2 B 另项 2 1--3 mg/L",
    "1 A 示例项目 4.04 10^9/L 3.50--9.50 2 B 另项 2 1--3 mg/L",
    "1 A 示例项目 4.04 3.50--9.50 10^9/L 另项 2 1--3 mg/L",
    "1 A 示例项目 4.04 3.50--9.50 10^9/L 2 B 另项 无法辨认",
    "1 A 示例项目 4.04 3.50--9.50 10^9/L 2 B 另项 2 1--3 mg/L 3 C 三项 5 1--6 mg/L",
])
def test_repeated_header_row_requires_one_complete_partition(row):
    header = "No. 代号 名称 结果 参考范围 单位 " * 2
    fields, gaps = region_ocr_fields(header + "\n" + row)
    assert not fields and gaps


def test_group_table_scope_ends_before_prose_or_unknown_header():
    header = "No. 代号 名称 结果 参考范围 单位 " * 2
    rows = "1 A 示例项目 4.04 3.50--9.50 10^9/L 2 B 另项 2 1--3 mg/L"
    fields, gaps = region_ocr_fields(header + "\n" + rows + "\n说明文字\n" + rows)
    assert len(fields) == 2 and gaps
    fields, gaps = region_ocr_fields("No. 代号 名称 结果 参考范围 单位\n"
                                   "No. 代号 名称 未知列 参考范围 单位\n"
                                   "1 A 示例项目 4.04 3.50--9.50 10^9/L")
    assert not fields and gaps


def test_incomplete_header_same_label_still_blocks_uniqueness():
    source = ("No. 代号 名称 结果 参考范围 单位 No. 代号 名称 结果 参考范围\n"
              "1 A 示例项目 4.04 3.50--9.50 10^9/L 2 B 示例项目 2 1--3 mg/L")
    result = _compare(source, [_item(excerpt="1 A 示例项目 4.04 3.50--9.50 10^9/L")])
    assert result["items"][0]["status"] == "unresolved"
    assert result["items"][0]["ocr_excerpt"] is None
    assert "项目不能唯一对应" in result["items"][0]["reasons"]
    assert "2 B 示例项目" in result["unresolved"][0]


@pytest.mark.parametrize("header,row", [
    ("No. 代号 名称 结果 参考范围 单位", "1 A 未完整项目 2 B 示例项目 2 1--3 mg/L"),
    ("No. 代号 名称 结果 参考范围 单位 " * 2,
     "1 A 未完整项目 2 B 项乙 2 1--3 mg/L 3 C 项丙 3 2--4 mg/L"),
])
def test_damaged_numbered_object_cannot_consume_next_complete_object(header, row):
    fields, gaps = region_ocr_fields(header + "\n" + row)
    assert not fields and gaps


def test_numeric_words_in_name_are_not_always_new_row_boundaries():
    row = "1 A 示例 2 亚型项目 4.04 3.50--9.50 10^9/L"
    result = _compare("No. 代号 名称 结果 参考范围 单位\n" + row,
                      [_item("示例 2 亚型项目", excerpt=row)])
    assert result["items"][0]["status"] == "consistent_transcription_candidate"


def test_extra_header_only_table_is_preserved_as_unread_source():
    text = _table() + "<table><tr><th>项目</th><th>结果</th><th>参考范围</th><th>单位</th></tr></table>"
    result = _compare(text, [_item()])
    assert result["items"][0]["status"] == "consistent_transcription_candidate"
    assert any("只有列名" in gap for gap in result["unresolved"])


@pytest.mark.parametrize("unit,canonical", [("×10¹²/L", "x10^12/L"), ("X10^9/L", "10⁹/L")])
def test_superscript_and_case_unit_variants_preserve_exponent(unit, canonical):
    assert _compare(_table(unit=unit), [_item(unit=canonical)])["items"][0]["status"] == "consistent_transcription_candidate"


def test_number_in_label_and_signed_exponent_never_get_silently_truncated():
    item = _item("β2示例指标", "2.5", "×10^-9/L", None)
    result = _compare("β2示例指标：2.5×10^-9/L", [item])
    assert result["items"][0]["ocr_excerpt"] == "β2示例指标：2.5×10^-9/L"
    assert _compare("β2示例指标：2.5×10^-9/L", [_item("示例指标", "2.5", "×10^-9/L", None)])["items"][0]["status"] == "unresolved"


@pytest.mark.parametrize("change,reason", [
    ({"raw_unit": "10^-9/L"}, "单位"),
    ({"raw_unit": None}, "单位"),
    ({"raw_value": "-4.04"}, "数值"),
    ({"raw_value": ">4.04"}, "数值"),
    ({"raw_value": "4.04↓"}, "异常标记"),
    ({"reference_text": "40.0--75.0%"}, "参考范围"),
    ({"script": "handwritten", "annotation_target": None}, "字迹"),
    ({"legibility": "partial"}, "字迹"),
    ({"raw_value": None}, "未读到"),
])
def test_changed_meaning_or_uncertainty_never_becomes_agreement(change, reason):
    result = _compare(_table(), [_item(**change)])
    assert result["items"][0]["status"] == "unresolved"
    assert any(reason in item for item in result["items"][0]["reasons"])


def test_real_failure_shape_negative_exponent_and_reference_unit_shift():
    assert _compare(_table(unit="10^-9/L"), [_item()])["items"][0]["status"] == "unresolved"
    result = _compare(_table(unit="", value="39.0↓", reference="40.0--75.0%"),
                      [_item(value="39.0↓", unit="%", reference="40.0--75.0")])
    reasons = result["items"][0]["reasons"]
    assert "单位不一致或未读全" in reasons and "参考范围未能对应" in reasons


@pytest.mark.parametrize("duplicate", ["ocr", "visual"])
def test_same_label_multiple_positions_not_unique_observation(duplicate):
    result = _compare(_table(repeat=duplicate == "ocr"), [_item()] * (2 if duplicate == "visual" else 1))
    assert all(item["status"] == "unresolved" for item in result["items"])


def test_clear_field_survives_unrelated_unclear_cropped_item():
    items = [_item("年龄", "52岁", "岁", None),
             _item(None, None, None, None, legibility="unclear", excerpt="残笔")]
    result = _compare("年龄：52岁", items)
    assert [item["status"] for item in result["items"]] == ["consistent_transcription_candidate", "unresolved"]


def test_three_date_roles_remain_distinct_and_counterfactual_changes_result():
    source = "采样时间：2025-08-15 9:46接收时间：2025-08-15 9:54报告时间：2025-08-15 10:12"
    items = [_item(label, value, None, None, time_label=label) for label, value in (
        ("采样时间", "2025-08-15 09:46"), ("接收时间", "2025-08-15 09:54"),
        ("报告时间", "2025-08-15 10:12"),
    )]
    result = _compare(source, items)
    assert all(item["status"] == "consistent_transcription_candidate" for item in result["items"])
    changed = deepcopy(items)
    changed[0]["raw_value"] = changed[2]["raw_value"]
    assert _compare(source, changed)["items"][0]["status"] == "unresolved"
    changed = deepcopy(items)
    changed[0]["time_label"] = "报告时间"
    assert _compare(source, changed)["items"][0]["status"] == "unresolved"


@pytest.mark.parametrize("source,value", [
    ("示例结果：阴性", "阴性"),
    ("示例结果：未见异常", "未见异常"),
    ("示例结果：可疑，建议复查", "可疑，建议复查"),
    ("示例结果：<0.5", "<0.50"),
])
def test_explicit_literal_value_is_preserved_without_medical_interpretation(source, value):
    fields, gaps = region_ocr_fields(source)
    assert not gaps and len(fields) == 1
    assert fields[0].excerpt == source
    result = _compare(source, [_item("示例结果", value, None, None)])
    assert result["items"][0]["status"] == "consistent_transcription_candidate"
    assert result["candidate_only"] and not result["formal_adoption_authorized"]
    assert not result["source_position_verified"]


@pytest.mark.parametrize("source,value", [
    ("示例结果：阴性", "阳性"),
    ("示例结果：可疑，建议复查", "可疑"),
    ("示例结果：未见异常", "正常"),
    ("示例结果：<0.5", "0.5"),
])
def test_literal_counterfactuals_are_not_normalized_to_agreement(source, value):
    assert _compare(source, [_item("示例结果", value, None, None)])["items"][0]["status"] == "unresolved"


def test_date_only_lines_keep_event_and_report_roles_separate():
    source = "采集日期：2025年8月15日\n报告日期：2025/08/16"
    items = [_item("采集日期", "2025-08-15", None, None, time_label="采集日期"),
             _item("报告日期", "2025-08-16", None, None, time_label="报告日期")]
    result = _compare(source, items)
    assert not result["unresolved"] and not result["unmatched_ocr"]
    assert all(item["status"] == "consistent_transcription_candidate" for item in result["items"])
    changed = deepcopy(items)
    changed[0]["time_label"] = "报告日期"
    assert _compare(source, changed)["items"][0]["status"] == "unresolved"


def test_duplicate_literal_fields_and_unlabelled_prose_remain_visible():
    result = _compare("示例结果：阴性\n示例结果：阴性\n边缘文字未读清", [_item("示例结果", "阴性", None, None)])
    assert result["items"][0]["status"] == "unresolved"
    assert len(result["unmatched_ocr"]) == 0
    assert any("边缘文字未读清" in gap for gap in result["unresolved"])


@pytest.mark.parametrize("source", ["10:12", "示例结果：", "：阴性", "结论：建议：复查"])
def test_clock_empty_field_and_ambiguous_nested_labels_are_not_literal_fields(source):
    fields, gaps = region_ocr_fields(source)
    assert gaps
    assert not any(field.raw_value == "阴性" for field in fields)


@pytest.mark.parametrize("source", [
    "<table><tr><td colspan='2'>项目</td><td>结果</td></tr></table>",
    "<table><tr><td>项目</td><td>结果</td>",
    "<table><tr><td>项目</td><td>结果</td><td>单位</td></tr></table>",
    "片段中有4.04，但没有项目和位置。",
])
def test_unsupported_layout_or_unlabelled_value_retains_unresolved(source):
    result = _compare(source, [_item()])
    assert result["items"][0]["status"] == "unresolved" and result["unresolved"]


@pytest.mark.parametrize("value", ["5<br>2", "5<br/>2", "<p>5</p><p>2</p>", "<div>5</div><div>2</div>"])
def test_separate_cell_blocks_never_fuse_into_a_new_numeric_candidate(value):
    result = _compare(_table(value=value), [_item(value="52")])
    assert result["items"][0]["status"] == "unresolved"
    assert any("5\n2" in gap for gap in result["unresolved"])
    assert not result["formal_adoption_authorized"]


@pytest.mark.parametrize("value", ["<p>4.04</p>", "4.<strong>04</strong>", "<div>4.04<br></div>"])
def test_single_block_and_inline_formatting_preserve_a_real_result(value):
    result = _compare(_table(value=value), [_item()])
    assert result["items"][0]["status"] == "consistent_transcription_candidate"
    assert not result["unresolved"]


@pytest.mark.parametrize("column,content", [
    ("label", "示例<br>项目"), ("reference", "3.50<br>9.50"),
    ("unit", "10<sup>9</sup>/L"), ("unit", "10<sub>9</sub>/L"),
])
def test_ambiguous_cell_does_not_block_an_unrelated_complete_row(column, content):
    text = _table()
    needle = {"label": "示例项目", "reference": "3.50--9.50", "unit": "10^9/L"}[column]
    text = text.replace(f"<td>{needle}</td>", f"<td>{content}</td>")
    text = text.replace("</table>", "<tr><td>另项</td><td>2</td><td></td><td>mg/L</td></tr></table>")
    result = _compare(text, [_item(), _item("另项", "2", "mg/L", None)])
    assert result["items"][0]["status"] == "unresolved"
    assert result["items"][1]["status"] == "consistent_transcription_candidate"
    assert any(content.replace("<br>", "\n") in gap for gap in result["unresolved"])


def test_each_separate_table_uses_its_own_column_identity():
    second = ("<table><tr><td>单位</td><td>参考值</td><td>结果</td><td>名称</td></tr>"
              "<tr><td>mg/L</td><td></td><td>2</td><td>另项</td></tr></table>")
    result = _compare(_table() + second, [_item(), _item("另项", "2", "mg/L", None)])
    assert not result["unresolved"] and not result["unmatched_ocr"]
    assert all(item["status"] == "consistent_transcription_candidate" for item in result["items"])
    changed = _compare(_table() + second, [_item(), _item("另项", "3", "mg/L", None)])
    assert changed["items"][1]["status"] == "unresolved"


def test_unsupported_separate_header_preserves_a_valid_table_and_the_gap():
    other = "<table><tr><td>备注</td></tr><tr><td>未读清</td></tr></table>"
    result = _compare(_table() + other, [_item()])
    assert result["items"][0]["status"] == "consistent_transcription_candidate"
    assert result["unresolved"]
