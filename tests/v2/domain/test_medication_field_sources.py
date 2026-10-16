from datetime import UTC, date, datetime
from hashlib import sha256

import pytest

from app.domain.contracts.facts import MedicationExposureCandidateV2, PartialDateRange
from app.domain.contracts.medication_source import (
    MedicationFieldSource, medication_field_source_errors, source_date_bounds,
)


TEXT = "2025-04-12口服药物甲10mg一次。"


def exposure_with_sources(locator_id="loc-1", source_hash=None):
    sources = [("medication_name", "actual_use", "药物甲"),
        ("start_range", "single_use", "2025-04-12"),
        ("duration_status", "status_single", "一次"),
        ("dose", "use_detail", "10"), ("unit", "use_detail", "mg")]
    return MedicationExposureCandidateV2(candidate_id="e1", run_id="run-1", call_id="call-1",
        medication_name="药物甲", dose="10", unit="mg", duration_status="single",
        start_range=PartialDateRange(source_text="2025-04-12", precision="day",
            lower_bound=date(2025, 4, 12), upper_bound=date(2025, 4, 12)),
        fact_candidate_ids=["f1"], locator_ids=[locator_id], candidate_source_semantics="既往原始资料",
        model_uncertainty=0.1, created_at=datetime(2026, 8, 22, tzinfo=UTC),
        field_sources=[MedicationFieldSource(field=field, role=role, locator_id=locator_id,
            object_text="药物甲", value_text=value, excerpt=TEXT,
            source_text_sha256=source_hash or sha256(TEXT.encode()).hexdigest())
            for field, role, value in sources])


@pytest.mark.parametrize("text,precision,lower,upper", [
    ("2024年2月29日", "day", date(2024, 2, 29), date(2024, 2, 29)),
    ("２０２４．０２．ＵＫ", "month", date(2024, 2, 1), date(2024, 2, 29)),
    ("2023.UK.UK", "year", date(2023, 1, 1), date(2023, 12, 31)),
    ("2025/04", "month", date(2025, 4, 1), date(2025, 4, 30)),
])
def test_written_calendar_precision_is_preserved(text, precision, lower, upper):
    assert source_date_bounds(text) == (precision, lower, upper)


@pytest.mark.parametrize("text", ["2025-02-29", "2025.UK.12", "2025-04-12至2025-04-15", "去年4月", "", "2025-13"])
def test_dates_do_not_borrow_or_guess_components(text):
    with pytest.raises(ValueError):
        source_date_bounds(text)


def test_full_field_proposal_is_nonmutating_and_legacy_payload_stays_unchanged():
    candidate = exposure_with_sources()
    before = candidate.model_dump_json()
    assert medication_field_source_errors(candidate) == []
    assert candidate.model_dump_json() == before
    legacy = candidate.model_copy(update={"field_sources": []})
    assert "field_sources" not in legacy.model_dump(mode="json")
    assert MedicationExposureCandidateV2.model_validate_json(legacy.model_dump_json()) == legacy


@pytest.mark.parametrize("fault", ["wrong_role", "wrong_drug", "different_value", "date_precision",
    "missing_unit", "extra_field", "duplicate", "foreign_locator", "wrong_status", "record_date_as_start"])
def test_wrong_field_binding_or_precision_does_not_qualify(fault):
    candidate = exposure_with_sources()
    sources = list(candidate.field_sources)
    if fault == "wrong_role" or fault == "record_date_as_start":
        sources[1] = sources[1].model_copy(update={"role": "recorded_at"})
    elif fault == "wrong_drug":
        sources[1] = sources[1].model_copy(update={"object_text": "药物乙"})
    elif fault == "different_value":
        candidate = candidate.model_copy(update={"dose": "20"})
    elif fault == "date_precision":
        candidate = candidate.model_copy(update={"start_range": PartialDateRange(
            precision="month", lower_bound=date(2025, 4, 1), upper_bound=date(2025, 4, 30))})
    elif fault == "missing_unit":
        sources = sources[:-1]
    elif fault == "extra_field":
        sources.append(sources[-1].model_copy(update={"field": "frequency"}))
    elif fault == "duplicate":
        sources.append(sources[-1])
    elif fault == "foreign_locator":
        sources[0] = sources[0].model_copy(update={"locator_id": "other"})
    elif fault == "wrong_status":
        sources[2] = sources[2].model_copy(update={"role": "status_ongoing"})
    candidate = candidate.model_copy(update={"field_sources": sources})
    assert medication_field_source_errors(candidate)


def test_record_date_does_not_certify_an_unwritten_clock_time():
    candidate = exposure_with_sources()
    source = candidate.field_sources[1].model_copy(update={"field": "record_time", "role": "recorded_at"})
    candidate = candidate.model_copy(update={"record_time": datetime(2025, 4, 12, tzinfo=UTC),
        "field_sources": [*candidate.field_sources, source]})
    assert not medication_field_source_errors(candidate)
    candidate = candidate.model_copy(update={"record_time": datetime(2025, 4, 12, 12, tzinfo=UTC)})
    assert medication_field_source_errors(candidate)


def test_unknown_duration_does_not_require_a_fabricated_unknown_quote():
    from app.domain.contracts.enums import DurationStatus

    candidate = exposure_with_sources()
    candidate = candidate.model_copy(update={"duration_status": DurationStatus.UNKNOWN,
        "field_sources": [item.model_copy(update={"role": "use_start"}) if item.field == "start_range" else item
            for item in candidate.field_sources if item.field != "duration_status"]})
    before = candidate.model_dump_json()
    assert not medication_field_source_errors(candidate)
    assert candidate.model_dump_json() == before


@pytest.mark.parametrize("declared,unit,written,valid", [
    ("10", "mg", "10mg", True), ("10.0", "mg", "10 mg", True),
    ("20", "mg", "10mg", False), ("10", "g", "10mg", False),
    ("0.01", "g", "10mg", False), ("10", None, "10mg", False),
    ("Infinity", "mg", "Infinitymg", False), ("10", "mg", "10-20mg", False),
])
def test_compound_dose_requires_the_same_finite_number_and_separately_sourced_unit(declared, unit, written, valid):
    candidate = exposure_with_sources()
    text = TEXT.replace("10mg", written)
    sources = [item.model_copy(update={"excerpt": text,
        **({"value_text": written} if item.field == "dose" else {}),
        **({"value_text": unit} if item.field == "unit" and unit is not None else {})})
        for item in candidate.field_sources if item.field != "unit" or unit is not None]
    candidate = candidate.model_copy(update={"dose": declared, "unit": unit, "field_sources": sources})
    before = candidate.model_dump_json()
    assert (not medication_field_source_errors(candidate)) == valid
    assert candidate.model_dump_json() == before


@pytest.mark.parametrize("kind,expected", [("date", "accepted"), ("output_repetition", "blocked"), ("negation_polarity", "blocked")])
@pytest.mark.parametrize("fault", [None, "wrong_hash", "fake_quote", "duplicate_quote", "wrong_role",
    "unannotated", "legacy", "aligned_ongoing"])
def test_field_proof_checks_original_not_just_a_policy_or_page(monkeypatch, kind, expected, fault):
    from types import SimpleNamespace
    from app.domain.gates import fact_evidence_closure as module
    from app.domain.contracts.ocr import OcrRiskFlag
    from app.domain.contracts.enums import LocatorPrecision, LocatorSourceLayer
    from tests.v2.domain.test_fact_evidence_closure import _make_revision

    candidate = exposure_with_sources()
    text = TEXT
    if fault == "wrong_hash":
        candidate.field_sources[0] = candidate.field_sources[0].model_copy(update={"source_text_sha256": "b" * 64})
    elif fault == "fake_quote":
        candidate.field_sources[0] = candidate.field_sources[0].model_copy(update={"excerpt": TEXT + "未记录文字"})
    elif fault == "duplicate_quote":
        text += "\n" + TEXT
    elif fault == "wrong_role":
        candidate.field_sources[1] = candidate.field_sources[1].model_copy(update={"role": "recorded_at"})
    elif fault == "unannotated":
        candidate = candidate.model_copy(update={"field_sources": []})
    elif fault == "aligned_ongoing":
        from app.domain.contracts.enums import DurationStatus
        candidate = candidate.model_copy(update={"duration_status": DurationStatus.ONGOING})
        candidate.field_sources[2] = candidate.field_sources[2].model_copy(update={
            "role": "status_ongoing", "value_text": "药物甲"})
    locator = SimpleNamespace(locator_id="loc-1", page_artifact_id="pa-1", ocr_page_id="op-1",
        source_text_sha256=sha256(TEXT.encode()).hexdigest(), source_layer=LocatorSourceLayer.RAW_OCR,
        precision=LocatorPrecision.TEXT_RANGE, text_start=0, text_end=len(TEXT))
    monkeypatch.setattr(module, "_fetch_cached", lambda *_args: locator)
    monkeypatch.setattr(module, "_localized_locator_text", lambda *_args, **_kwargs: text)
    revision = _make_revision(manifest_entries=[("doc-1", 1, "pa-1", "op-1")], locator_ids=["loc-1"])
    if fault != "legacy":
        revision = revision.model_copy(update={"source_qualification_mode": "scoped_text_v1"})
    flag = OcrRiskFlag(risk_id="r1", kind=kind, level="blocking", text="2025-04-12",
        text_start=0, text_end=10, rule_version="synthetic-v1")
    outcome, reasons, _ = module.validate_blocking_ocr_for_candidate(None, candidate, revision,
        prepared_context=([], {"op-1": [("scan", flag)]}, set(), []))
    assert outcome.value == ("blocked" if fault else expected)
    assert bool(reasons) == (outcome.value == "blocked")


def test_negation_outside_a_clipped_quote_is_not_downgraded(monkeypatch):
    from types import SimpleNamespace
    from app.domain.gates import fact_evidence_closure as module
    from app.domain.contracts.ocr import OcrRiskFlag
    from app.domain.contracts.enums import LocatorPrecision, LocatorSourceLayer
    from tests.v2.domain.test_fact_evidence_closure import _make_revision

    source = "否认" + TEXT
    candidate = exposure_with_sources(source_hash=sha256(source.encode()).hexdigest())
    locator = SimpleNamespace(locator_id="loc-1", page_artifact_id="pa-1", ocr_page_id="op-1",
        source_text_sha256=sha256(source.encode()).hexdigest(), source_layer=LocatorSourceLayer.RAW_OCR,
        precision=LocatorPrecision.TEXT_RANGE, text_start=2, text_end=len(source))
    monkeypatch.setattr(module, "_fetch_cached", lambda *_args: locator)
    monkeypatch.setattr(module, "_localized_locator_text", lambda *_args, **_kwargs: TEXT)
    revision = _make_revision(manifest_entries=[("doc-1", 1, "pa-1", "op-1")], locator_ids=["loc-1"])
    revision = revision.model_copy(update={"source_qualification_mode": "scoped_text_v1"})
    flag = OcrRiskFlag(risk_id="neg", kind="negation_polarity", level="blocking", text="否认",
        text_start=0, text_end=2, rule_version="synthetic-v1")
    outcome, reasons, _ = module.validate_blocking_ocr_for_candidate(None, candidate, revision,
        prepared_context=([], {"op-1": [("scan", flag)]}, set(), []))
    assert outcome.value == "blocked"
    assert any("极性" in reason for reason in reasons)
