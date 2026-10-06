"""Subcrop agreement is not inferred from shared text or a model's box alone."""
from copy import deepcopy

import pytest

from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.local_region_read import LocalRegionRelativeBox, LocalizedRegionReadCandidate, parse_local_region_read
from app.evidence.local_region_position_trial import compare_single_field_subcrop, proposed_field_bbox


def _candidate():
    return {"items": [{"label": "年龄", "raw_value": "50岁", "raw_unit": "岁",
                       "reference_text": None, "time_label": None, "excerpt": "年龄：50岁",
                       "position": "一行", "script": "printed", "legibility": "clear",
                       "annotation_target": None, "proposed_bbox": {"x0": 0, "y0": 0, "x1": 1000, "y1": 1000}}],
            "unresolved": []}


def test_outward_rounding_keeps_source_edges_and_nonzero_area():
    assert proposed_field_bbox(BoundingBox(x0=10, y0=20, x1=21, y1=33),
                               LocalRegionRelativeBox(x0=1, y0=1, x1=999, y1=999)).model_dump() == {
                                   "x0": 10, "y0": 20, "x1": 21, "y1": 33}


@pytest.mark.parametrize("box", [
    {"x0": True, "y0": 0, "x1": 1000, "y1": 1000},
    {"x0": 0.5, "y0": 0, "x1": 1000, "y1": 1000},
    {"x0": 1000, "y0": 0, "x1": 1000, "y1": 1000},
    {"x0": 0, "y0": 0, "x1": 1001, "y1": 1000},
])
def test_invalid_proposal_never_silently_clips_or_coerces(box):
    with pytest.raises(ValueError):
        LocalRegionRelativeBox.model_validate(box)


@pytest.mark.parametrize("text", ["年龄：50岁", "年龄：５０岁", "年龄：50.0岁"])
def test_source_faithful_numeric_variants_only_make_isolated_candidate(text):
    result = compare_single_field_subcrop(text, LocalizedRegionReadCandidate.model_validate(_candidate()), 0)
    assert result["single_field_transcription_agreement"]
    assert not result["source_position_verified"] and not result["formal_adoption_authorized"]


@pytest.mark.parametrize("text,change", [
    ("年龄：51岁", {}), ("年龄：50岁\n另一日期：2026-10-01", {}),
    ("年龄：50岁\n对象不明确", {}), ("年龄：50岁", {"script": "handwritten"}),
    ("年龄：50岁", {"proposed_bbox": None}), ("年龄：50岁", {"legibility": "partial"}),
])
def test_wrong_row_extra_content_handwriting_or_missing_box_stays_unresolved(text, change):
    data = deepcopy(_candidate())
    data["items"][0].update(change)
    assert not compare_single_field_subcrop(text, LocalizedRegionReadCandidate.model_validate(data), 0)["single_field_transcription_agreement"]


def test_default_parser_does_not_accept_new_position_field_without_opt_in():
    import json
    text = "source_ref=region:fixture\n" + json.dumps(_candidate(), ensure_ascii=False)
    with pytest.raises(ValueError):
        parse_local_region_read(text, source_ref="region:fixture")
    assert parse_local_region_read(text, source_ref="region:fixture", read_format="localized_candidate").items[0].proposed_bbox is not None


@pytest.mark.parametrize("extra", ["outside", "column", "both"])
def test_table_residual_cannot_be_erased_to_claim_one_complete_field(extra):
    extra_header = "<th>标志</th>" if extra in {"column", "both"} else ""
    extra_cell = "<td>↑</td>" if extra_header else ""
    text = ("<table><tr><th>项目</th><th>结果</th><th>参考范围</th><th>单位</th>"
            + extra_header + "</tr><tr><td>年龄</td><td>50</td><td></td><td>岁</td>"
            + extra_cell + "</tr></table>" + ("血压：120/80" if extra in {"outside", "both"} else ""))
    assert not compare_single_field_subcrop(text, LocalizedRegionReadCandidate.model_validate(_candidate()), 0)["single_field_transcription_agreement"]


def test_clean_one_row_table_remains_usable_without_unmapped_content():
    text = "<table><tr><th>项目</th><th>结果</th><th>参考范围</th><th>单位</th></tr><tr><td>年龄</td><td>50</td><td></td><td>岁</td></tr></table>"
    assert compare_single_field_subcrop(text, LocalizedRegionReadCandidate.model_validate(_candidate()), 0)["single_field_transcription_agreement"]


@pytest.mark.parametrize("value", ["5<br>0", "<p>5</p><p>0</p>"])
def test_multivalue_cell_cannot_become_a_verified_single_field(value):
    text = ("<table><tr><th>项目</th><th>结果</th><th>参考范围</th><th>单位</th></tr>"
            f"<tr><td>年龄</td><td>{value}</td><td></td><td>岁</td></tr></table>")
    result = compare_single_field_subcrop(text, LocalizedRegionReadCandidate.model_validate(_candidate()), 0)
    assert not result["single_field_transcription_agreement"] and result["reasons"]
    assert result["comparison_contract"] == "local-region-transcript-comparison/v7"
    assert not result["source_position_verified"] and not result["formal_adoption_authorized"]


@pytest.mark.parametrize("value", ["阴性", "可疑，建议复查", "2026年10月1日"])
def test_complete_literal_subcrop_remains_unadopted_candidate(value):
    data = _candidate()
    data["items"][0].update(label="示例结果", raw_value=value, raw_unit=None, excerpt="示例结果：" + value)
    candidate = LocalizedRegionReadCandidate.model_validate(data)
    outcome = compare_single_field_subcrop("示例结果：" + value, candidate, 0)
    assert outcome["single_field_transcription_agreement"]
    assert not outcome["formal_adoption_authorized"] and not outcome["source_position_verified"]
    assert not compare_single_field_subcrop("示例结果：" + value + "\n另一项目：阴性", candidate, 0)["single_field_transcription_agreement"]


def test_explicit_header_and_one_row_are_only_a_subcrop_candidate():
    data = _candidate()
    row = "示例项目 2 1--3 mg/L"
    data["items"][0].update(label="示例项目", raw_value="2", raw_unit="mg/L",
                           reference_text="1--3", excerpt=row)
    candidate = LocalizedRegionReadCandidate.model_validate(data)
    text = "项目 结果 参考范围 单位\n" + row
    result = compare_single_field_subcrop(text, candidate, 0)
    assert result["single_field_transcription_agreement"]
    assert not result["source_position_verified"] and not result["formal_adoption_authorized"]
    for extra in ("\n对象不明确", "\n另项 2 1--3 mg/L"):
        assert not compare_single_field_subcrop(text + extra, candidate, 0)["single_field_transcription_agreement"]


@pytest.mark.parametrize("second_header", [" 单位", ""])
def test_two_groups_cannot_be_called_one_complete_subcrop(second_header):
    data = _candidate()
    row = "1 A 年龄 50 18--65 岁"
    data["items"][0].update(raw_value="50", reference_text="18--65", excerpt=row)
    text = ("No. 代号 名称 结果 参考范围 单位 No. 代号 名称 结果 参考范围"
            + second_header + "\n" + row + " 2 B 另项 2 1--3 mg/L")
    result = compare_single_field_subcrop(text, LocalizedRegionReadCandidate.model_validate(data), 0)
    assert not result["single_field_transcription_agreement"]
    assert not result["source_position_verified"] and not result["formal_adoption_authorized"]


@pytest.mark.parametrize("text", [
    "No. 代号 名称 结果 参考范围 单位\n1 A 未完整项目 2 B 示例项目 2 1--3 mg/L",
    "<table><tr><th>项目</th><th>结果</th><th>参考范围</th><th>单位</th></tr>"
    "<tr><td>年龄</td><td>50</td><td></td><td>岁</td></tr></table>"
    "<table><tr><th>项目</th><th>结果</th><th>参考范围</th><th>单位</th></tr></table>",
])
def test_swallowed_object_and_header_only_table_do_not_prove_subcrop_coverage(text):
    data = _candidate()
    if text.startswith("No."):
        data["items"][0].update(label="未完整项目 2 B 示例项目", raw_value="2", raw_unit="mg/L",
                               reference_text="1--3", excerpt=text.split("\n")[1])
    result = compare_single_field_subcrop(text, LocalizedRegionReadCandidate.model_validate(data), 0)
    assert not result["single_field_transcription_agreement"]
    assert not result["source_position_verified"] and not result["formal_adoption_authorized"]


def _headerless_candidate():
    data = _candidate()
    data["items"][0].update(label="CODE 示例项目", raw_value="2", raw_unit="mg/L",
                           reference_text="1--3", excerpt="7  CODE  示例项目  2  1--3  mg/L")
    data["unresolved"] = ["序号是否完整尚待核对"]
    return data


def test_complete_headerless_transcript_is_not_field_or_clinical_qualification():
    data = _headerless_candidate()
    result = compare_single_field_subcrop(
        "7 CODE 示例项目 2 1--3 mg/L", LocalizedRegionReadCandidate.model_validate(data), 0,
    )
    assert result["literal_crop_transcription_agreement"]
    assert not result["single_field_transcription_agreement"]
    assert not result["field_assignment_verified"]
    assert result["status"] == "unresolved" and result["reasons"]
    assert not result["source_position_verified"] and not result["formal_adoption_authorized"]


@pytest.mark.parametrize("text,change", [
    ("7 CODE 示例项目 3 1--3 mg/L", {}),
    ("7 CODE 示例项目 2 1--3 g/L", {}),
    ("CODE 示例项目 2 1--3 mg/L", {}),
    ("7 CODE 示例项目 2 1--3 mg/L\n另一项目 2 mg/L", {}),
    ("7 CODE 示例项目 2 1--3 mg/L", {"script": "handwritten"}),
    ("7 CODE 示例项目 2 1--3 mg/L", {"legibility": "partial"}),
    ("7 CODE 示例项目 2 1--3 mg/L", {"annotation_target": "另一个项目"}),
    ("7 CODE 示例项目 2 1--3 mg/L", {"proposed_bbox": None}),
])
def test_literal_witness_does_not_drop_source_content_or_unreadable_state(text, change):
    data = _headerless_candidate()
    data["items"][0].update(change)
    result = compare_single_field_subcrop(text, LocalizedRegionReadCandidate.model_validate(data), 0)
    assert not result["literal_crop_transcription_agreement"]


def test_one_crop_transcript_is_not_witness_for_multiple_candidate_objects():
    data = _headerless_candidate()
    data["items"].append(deepcopy(data["items"][0]))
    result = compare_single_field_subcrop(
        "7 CODE 示例项目 2 1--3 mg/L", LocalizedRegionReadCandidate.model_validate(data), 0,
    )
    assert not result["literal_crop_transcription_agreement"]
