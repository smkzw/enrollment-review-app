from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import GateOutcome, LocatorPrecision, LocatorSourceLayer, OcrRiskKind, OcrRiskLevel
from app.domain.contracts.ocr import OcrRiskFlag
from app.domain.gates import fact_evidence_closure as gate
from app.evidence.risk import blocking_risk_is_resolved


@pytest.mark.parametrize("layer,ocr_id,start,end,precision,expected", [
    (LocatorSourceLayer.RAW_OCR, "ocr", 0, 3, LocatorPrecision.TEXT_RANGE, GateOutcome.ACCEPTED),
    (LocatorSourceLayer.RAW_OCR, "ocr", 4, 7, LocatorPrecision.TEXT_RANGE, GateOutcome.BLOCKED),
    (LocatorSourceLayer.EFFECTIVE_TEXT, "ocr", 0, 3, LocatorPrecision.TEXT_RANGE, GateOutcome.BLOCKED),
    (LocatorSourceLayer.NATIVE_TEXT, None, 0, 3, LocatorPrecision.TEXT_RANGE, GateOutcome.BLOCKED),
    (LocatorSourceLayer.RAW_OCR, "ocr", None, None, LocatorPrecision.PAGE_EXCERPT, GateOutcome.BLOCKED),
    (LocatorSourceLayer.RAW_OCR, "ocr", None, None, LocatorPrecision.PAGE_ONLY, GateOutcome.BLOCKED),
    (LocatorSourceLayer.RAW_OCR, "different", 0, 3, LocatorPrecision.TEXT_RANGE, GateOutcome.BLOCKED),
])
def test_risk_coordinates_are_raw_only(monkeypatch, layer, ocr_id, start, end, precision, expected):
    locator = SimpleNamespace(page_artifact_id="page", ocr_page_id=ocr_id, source_layer=layer,
        text_start=start, text_end=end, precision=precision)
    monkeypatch.setattr(gate, "_fetch_cached", lambda *_args: locator)
    flag = SimpleNamespace(risk_id="risk", kind=OcrRiskKind.NUMERIC_VALUE, text_start=4, text_end=7)
    revision = SimpleNamespace(source_qualification_mode="scoped_text_v1",
        manifest=[SimpleNamespace(page_artifact_id="page", ocr_page_id="ocr")])
    candidate = SimpleNamespace(locator_ids=["loc"], canonical_value=True)
    result = gate.validate_blocking_ocr_for_candidate(None, candidate, revision,
        prepared_context=([], {"ocr": [("scan", flag)]}, set(), []))
    assert result[0] == expected


@pytest.mark.parametrize("fields", [
    {"canonical_value": 5.6}, {"canonical_value": "151"}, {"unit": "g/L"},
    {"start_range": "unlocated"}, {"date_range": "unlocated"}, {"dose": "one"},
    {"assertion_basis": SimpleNamespace(assertion_text="procedure completed 2025/08/08")},
])
def test_unlocated_value_dependency_cannot_escape_via_clear_quote(fields):
    assert gate._has_unlocated_value_dependencies(SimpleNamespace(**fields))


def test_confirmed_partial_token_correction_has_one_resolution_rule():
    flag = OcrRiskFlag(risk_id="r", kind=OcrRiskKind.NUMERIC_VALUE, level=OcrRiskLevel.BLOCKING,
        text_start=4, text_end=7, text="5.6", rule_version="test/v1")
    assert blocking_risk_is_resolved(flag, reviewed=False, correction_ranges=[(5, 5)], page_text_length=20)
    assert not blocking_risk_is_resolved(flag, reviewed=False, correction_ranges=[(4, 4)], page_text_length=20)
    repeated = flag.model_copy(update={"kind": OcrRiskKind.OUTPUT_REPETITION})
    assert not blocking_risk_is_resolved(repeated, reviewed=True, correction_ranges=[], page_text_length=20)
    assert blocking_risk_is_resolved(repeated, reviewed=False, correction_ranges=[(0, 20)], page_text_length=20)
