import openpyxl
import json

from scripts.audit_fact_gold import audit


def test_inventory_preserves_zero_and_does_not_accept_free_text(tmp_path):
    path = tmp_path / "gold.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "关键事实金标"
    sheet.append(["page_id", "subject", "field", "value", "excerpt", "GT裁决(保留/修正/删除/新增)"])
    sheet.append(["p", "s", "f", 0, "f 0", "保留"])
    sheet.append(["p", "s", "f", 1, "f 1", "以图像为准"])
    sheet.append(["p", "s", "f", None, None, "删除"])
    workbook.save(path)
    before = path.read_bytes()
    result = audit(path)
    assert result["explicit_retained_rows"] == 1
    assert result["historical_non_deleted_rows"] == 2
    assert result["issues"] == [{"sheet_row": 3, "reasons": ["unstructured_decision"]}]
    assert not result["clinical_acceptance"]
    assert path.read_bytes() == before
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    for name, verdict in (("one", "新增"), ("two", "删除")):
        (reviews / f"{name}.json").write_text(json.dumps({"subject": "s", "facts": [
            {"page_id": "p", "field": "f", "value": 1, "verdict": verdict}
        ]}))
    traced = audit(path, reviews)
    candidates = traced["issues"][0]["review_candidates"]
    assert {candidate["verdict"] for candidate in candidates} == {"新增", "删除"}
    assert all(len(candidate["review_sha256"]) == 64 for candidate in candidates)
    assert not traced["clinical_acceptance"]
    assert path.read_bytes() == before
