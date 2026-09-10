from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.contracts.page_review import PageReviewRecord
from app.domain.page_normalization import fact_normalization_key
from app.domain.page_reconciliation import PageReconciliationError, reconcile_page_reviews
from app.storage.codecs import decode_contract, encode_contract, encode_value
from tests.v2.domain.test_page_review_contracts import _review_payload


def _legacy_payload():
    payload = PageReviewRecord(**_review_payload()).model_dump(mode="json")
    payload["contract_version"] = "page-review/v1"
    fact = payload["facts"][0]
    fact.pop("context", None)
    fact.update(field_name="test", raw_value="1.234567", normalized_value="1.23457",
                normalized_unit=None, normalization_key="test|1.23457|")
    return payload


def test_old_rounded_record_remains_readable_without_changing_encoded_bytes():
    text, digest = encode_value(_legacy_payload())
    record = decode_contract(PageReviewRecord, text, digest)
    assert record.facts[0].raw_value == "1.234567"
    assert record.facts[0].normalized_value == "1.23457"
    assert encode_contract(record) == (text, digest)


def test_new_records_reject_old_rounded_keys():
    payload = _legacy_payload()
    payload["contract_version"] = "page-review/v2"
    with pytest.raises(ValidationError):
        PageReviewRecord.model_validate(payload)


def test_legacy_reader_does_not_accept_arbitrary_keys():
    payload = _legacy_payload()
    payload["facts"][0]["normalization_key"] = "invented"
    with pytest.raises(ValidationError):
        PageReviewRecord.model_validate(payload)


def test_legacy_records_cannot_silently_enter_new_reconciliation():
    a = PageReviewRecord.model_validate(_legacy_payload())
    b = PageReviewRecord.model_validate({**_legacy_payload(), "page_review_id": "b", "lane": "main-B"})
    with pytest.raises(PageReconciliationError, match="版本"):
        reconcile_page_reviews([a, b], determination_modes={})


@pytest.mark.parametrize("version", ["page-review/v1", "page-review/v2"])
def test_early_decimal_record_remains_byte_stable(version):
    payload = PageReviewRecord(**_review_payload()).model_dump(mode="json")
    payload["contract_version"] = version
    for fact in payload["facts"]:
        fact.pop("context", None)
        key, value, unit = fact_normalization_key(fact["field_name"], fact["raw_value"], legacy=True)
        fact.update(normalization_key=key, normalized_value=value, normalized_unit=unit)
    text, digest = encode_value(payload)
    assert encode_contract(decode_contract(PageReviewRecord, text, digest)) == (text, digest)


def test_default_new_contract_is_v6_and_legacy_objects_do_not_bypass_it():
    assert PageReviewRecord(**_review_payload()).contract_version == "page-review/v6"
    old = PageReviewRecord.model_validate(_legacy_payload())
    with pytest.raises(ValidationError):
        PageReviewRecord(**{**_review_payload(), "facts": old.facts})


def test_v5_per_microliter_receipt_remains_byte_stable():
    payload = PageReviewRecord(**_review_payload()).model_dump(mode="json")
    payload["contract_version"] = "page-review/v5"
    fact = payload["facts"][0]
    fact["raw_value"] = "0 /μL"
    key, value, unit = fact_normalization_key(fact["field_name"], fact["raw_value"],
        context=fact.get("context"), version5=True)
    fact.update(normalization_key=key, normalized_value=value, normalized_unit=unit)
    text, digest = encode_value(payload)
    assert encode_contract(decode_contract(PageReviewRecord, text, digest)) == (text, digest)
    with pytest.raises(ValidationError):
        PageReviewRecord.model_validate({**payload, "contract_version": "page-review/v6"})


def test_v4_arrow_before_unit_receipt_remains_byte_stable():
    payload = PageReviewRecord(**_review_payload()).model_dump(mode="json")
    payload["contract_version"] = "page-review/v4"
    fact = payload["facts"][0]
    fact["raw_value"] = "9.1↑ %"
    key, value, unit = fact_normalization_key(fact["field_name"], fact["raw_value"],
        context=fact.get("context"), version4=True)
    fact.update(normalization_key=key, normalized_value=value, normalized_unit=unit)
    text, digest = encode_value(payload)
    assert encode_contract(decode_contract(PageReviewRecord, text, digest)) == (text, digest)
    with pytest.raises(ValidationError):
        PageReviewRecord.model_validate({**payload, "contract_version": "page-review/v5"})


@pytest.mark.parametrize("raw,expected", [
    ("9.1↑ %", ("9.1", "%")),
    ("≤４.２０↓ mmol/L", ("≤4.2", "mmol/l")),
    ("0↓ %", ("0", "%")),
    ("1↑2 %", ("1↑2%", None)),
    ("升高↑ %", ("升高↑%", None)),
])
def test_v5_numeric_annotation_grammar(raw, expected):
    from app.domain.page_normalization import normalize_scalar
    assert normalize_scalar(raw) == expected


def test_legacy_facts_still_reject_extra_fields():
    payload = _legacy_payload()
    payload["facts"][0]["exclusion_triggered"] = True
    with pytest.raises(ValidationError):
        PageReviewRecord.model_validate(payload)


def test_v3_timestamp_keys_remain_byte_stable_and_cannot_enter_v4():
    payload = PageReviewRecord(**_review_payload()).model_dump(mode="json")
    payload["contract_version"] = "page-review/v3"
    fact = payload["facts"][0]
    fact["raw_value"] = "2025-08-15 9:46"
    fact["context"] = {"target_text": "采样时间", "time_text": "2025-08-15 9:46",
                       "location_text": None, "polarity": "asserted"}
    key, value, unit = fact_normalization_key(fact["field_name"], fact["raw_value"],
                                            context=fact["context"], version3=True)
    fact.update(normalization_key=key, normalized_value=value, normalized_unit=unit)
    text, digest = encode_value(payload)
    assert encode_contract(decode_contract(PageReviewRecord, text, digest)) == (text, digest)
    with pytest.raises(ValidationError):
        PageReviewRecord.model_validate({**payload, "contract_version": "page-review/v4"})


def test_historical_reconciliation_handwriting_timestamp_is_byte_stable():
    from app.domain.contracts.page_review import PageReconciliation
    from app.domain.page_normalization import handwriting_normalization_key
    context = {"target_text": "检查项目", "time_text": "2025-08-15 9:46",
               "location_text": None, "polarity": "asserted"}
    key, normalized = handwriting_normalization_key("note", "复核", context=context, version3=True)
    payload = PageReconciliation(reconciliation_id="old-result", page_artifact_id="page",
        clause_pack_sha256="a" * 64, page_review_ids=["a", "b"]).model_dump(mode="json")
    payload["contract_version"] = "page-reconciliation/v1"
    # Stored receipts from the retired third read always carried these columns.
    payload["handwriting_reader_triggered"] = False
    payload["missing_optional_lanes"] = []
    payload["optional_lane_failures"] = []
    payload["accepted_handwriting"] = [{"observation_id": "note-1", "kind": "note",
        "raw_text": "复核", "normalized_text": normalized, "normalization_key": key,
        "region": {"excerpt": "复核", "bbox": None}, "context": context}]
    text, digest = encode_value(payload)
    assert encode_contract(decode_contract(PageReconciliation, text, digest)) == (text, digest)
    with pytest.raises(ValidationError):
        PageReconciliation.model_validate({**payload, "contract_version": "page-reconciliation/v2"})


def test_retired_third_read_reconciliation_receipt_remains_byte_stable():
    from app.domain.contracts.page_review import PageReconciliation
    payload = PageReconciliation(reconciliation_id="third-read-result", page_artifact_id="page",
        clause_pack_sha256="a" * 64, page_review_ids=["a", "b"]).model_dump(mode="json")
    payload["contract_version"] = "page-reconciliation/v3"
    payload["handwriting_reader_triggered"] = True
    payload["missing_optional_lanes"] = ["handwriting-C"]
    payload["optional_lane_failures"] = [{"lane": "handwriting-C", "failure_kind": "endpoint"}]
    text, digest = encode_value(payload)
    decoded = decode_contract(PageReconciliation, text, digest)
    assert decoded.handwriting_reader_triggered is True
    assert decoded.missing_optional_lanes == ["handwriting-C"]
    assert encode_contract(decoded) == (text, digest)
    with pytest.raises(ValidationError, match="第三读"):
        PageReconciliation.model_validate({**payload, "contract_version": "page-reconciliation/v4"})


def test_new_reconciliation_drops_third_read_fields_and_dual_main_output_stays_v4():
    from app.domain.contracts.page_review import PageReconciliation
    record = PageReconciliation(reconciliation_id="dual-main", page_artifact_id="page",
        clause_pack_sha256="a" * 64, page_review_ids=["a", "b"])
    assert record.contract_version == "page-reconciliation/v4"
    dumped = record.model_dump(mode="json")
    for field in ("handwriting_reader_triggered", "missing_optional_lanes", "optional_lane_failures"):
        assert field not in dumped
    text, digest = encode_value(dumped)
    assert encode_contract(decode_contract(PageReconciliation, text, digest)) == (text, digest)
