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
    assert result["contract"] == "local-region-transcript-comparison/v3"
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


@pytest.mark.parametrize("source", [
    "<table><tr><td colspan='2'>项目</td><td>结果</td></tr></table>",
    "<table><tr><td>项目</td><td>结果</td>",
    "<table><tr><td>项目</td><td>结果</td><td>单位</td></tr></table>",
    "片段中有4.04，但没有项目和位置。",
])
def test_unsupported_layout_or_unlabelled_value_retains_unresolved(source):
    result = _compare(source, [_item()])
    assert result["items"][0]["status"] == "unresolved" and result["unresolved"]
