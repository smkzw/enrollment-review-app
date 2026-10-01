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
