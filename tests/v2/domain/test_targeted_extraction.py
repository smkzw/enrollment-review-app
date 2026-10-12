from types import SimpleNamespace

import pytest

from app.domain.risk_flags import RiskFlag, fact_risk_flags, number_in_excerpt
from app.domain.variables.dictionary import load_dictionary
from app.domain.variables.extraction import build_extraction_targets
from app.domain.contracts.enums import ReviewStage
from app.agents.evidence_normalizer import evidence_normalizer_json_schema, _model_input_payload
from tests.v2.agents.test_evidence_normalizer_adapter import _input
from app.domain.contracts.evidence_normalizer import evidence_normalizer_input_scope_hash, EvidenceNormalizerInput


@pytest.mark.parametrize("value,text,expected", [
    (5.6, "ALT 5.6 U/L", True), (5.6, "ALT 55.6 U/L", False),
    (5.6, "ALT 5.60 U/L", True), (0.5, "EOS 0.50", True),
    (6, "第16页", False), (True, "已完成", True),
    (9.5, "ALT 3.5-9.5 U/L", True), (-9.5, "ALT 3.5-9.5 U/L", False),
    (-9.5, "结果 -9.5", True),
])
def test_numeric_excerpt_exact_value(value, text, expected):
    assert number_in_excerpt(value, text) is expected


@pytest.mark.parametrize("raw,value,expected", [("51", 51, True), ("51.0", 51, True),
    ("５１", 51, True), ("5.1e1", 51, True), ("51岁", 51, False), ("<51", 51, False),
    ("51", 52, False), ("510", 51, False), (True, 1, False), ("nan", float("nan"), False)])
def test_numeric_representation_never_changes_the_reading(raw, value, expected):
    from app.domain.risk_flags import same_numeric_reading
    assert same_numeric_reading(raw, value) is expected


def candidate(value=5.6, unit="U/L"):
    return SimpleNamespace(raw_value=value, canonical_value=value, unit=unit,
                           risk_flags=[], date_range=None, date_role=None)


def test_risks_are_explicit_and_do_not_remove_values():
    definition = load_dictionary()["alt"]
    item = candidate(5.6)
    assert fact_risk_flags(item, definition, text="ALT 5.6 U/L") == []
    assert RiskFlag.ATTRIBUTION_UNCERTAIN in fact_risk_flags(item, definition, text="ALT\nAST 5.6 U/L")
    assert RiskFlag.ATTRIBUTION_UNCERTAIN in fact_risk_flags(item, definition, text="ALT 5.6–9.5 U/L")
    assert RiskFlag.NEAR_THRESHOLD in fact_risk_flags(item, definition, text="ALT 5.6 U/L", thresholds=[5.5])
    assert RiskFlag.IMPLAUSIBLE_VALUE in fact_risk_flags(candidate(999999), definition, text="ALT 999999 U/L")
    assert RiskFlag.UNIT_INFERRED in fact_risk_flags(item, definition, text="ALT 5.6")
    assert fact_risk_flags(item, definition, text="ALT 5.6 U/L", low_ocr=True, handwritten=True) == [RiskFlag.HANDWRITTEN, RiskFlag.LOW_OCR_CONFIDENCE]
    assert item.canonical_value == 5.6


def test_targets_respect_due_stage_excluded_procedures_and_required_results():
    requirements = [SimpleNamespace(requirement_id="a", due_stage=ReviewStage.SCREENING, variable_id="age", procedure_catalog_item_id=None),
                    SimpleNamespace(requirement_id="b", due_stage=ReviewStage.BASELINE, variable_id="alt", procedure_catalog_item_id=None),
                    SimpleNamespace(requirement_id="c", due_stage=ReviewStage.SCREENING, variable_id=None, procedure_catalog_item_id="proc-1"),
                    SimpleNamespace(requirement_id="d", due_stage=ReviewStage.SCREENING, variable_id=None, procedure_catalog_item_id="proc-2")]
    rule_set = SimpleNamespace(variable_definitions=[], review_records=[
        SimpleNamespace(official_code="proc-1", note="excluded", result_variables=[]),
        SimpleNamespace(official_code="proc-2", note=None, result_variables=["alt"])])
    targets = build_extraction_targets(rule_set, ReviewStage.SCREENING, requirements)
    assert [item.requirement_id for item in targets.requirements] == ["a", "d"]
    assert [item.variable_id for item in targets.variables] == ["age", "alt"]


def test_frozen_input_identity_includes_target_dictionary():
    original = _input()
    material = {key: getattr(original, key) for key in (
        "authority", "logical_document_id", "context", "related_requirements", "manifest_sha256",
        "completion_manifest_sha256", "page_numbers", "pages", "page_review", "available_locator_ids", "available_locators")}
    variables = [load_dictionary()["age"]]
    updated = evidence_normalizer_input_scope_hash(**material, variable_definitions=variables)
    assert updated != original.input_scope_sha256
    shaped = EvidenceNormalizerInput.model_validate({**original.model_dump(), "variable_definitions": variables, "input_scope_sha256": updated})
    assert _model_input_payload(shaped)["variable_definitions"][0]["variable_id"] == "age"
    schema = evidence_normalizer_json_schema(["age", "alt"])
    assert schema["$defs"]["EvidenceFactDraft"]["properties"]["variable_id"]["anyOf"][0]["enum"] == ["age", "alt"]
    assert "risk_flags" not in schema["$defs"]["EvidenceFactDraft"]["properties"]


def test_compact_requirement_pool_and_locator_rows_preserve_every_identity_and_text():
    import json
    from app.agents.evidence_normalizer import evidence_normalizer_reference_aliases, build_evidence_normalizer_prompt
    original = _input()
    # Frozen source identity is computed from the full input, not the projection.
    material = {key: getattr(original, key) for key in (
        "authority", "logical_document_id", "context", "related_requirements", "manifest_sha256",
        "completion_manifest_sha256", "page_numbers", "pages", "page_review", "available_locator_ids", "available_locators")}
    definitions = [load_dictionary()["age"]]
    identity = evidence_normalizer_input_scope_hash(**material, variable_definitions=definitions)
    source = EvidenceNormalizerInput.model_validate({**original.model_dump(), "variable_definitions": definitions,
        "input_scope_sha256": identity})
    prompt = build_evidence_normalizer_prompt(source, prompt_template="冻结模板", include_output_schema=False)
    projection, _ = json.JSONDecoder().raw_decode(prompt.split("本次输入：", 1)[1].lstrip())
    contexts = projection["requirement_contexts"]
    assert len(projection["related_requirements"]) == len(source.related_requirements)
    for original_req, projected in zip(source.related_requirements, projection["related_requirements"]):
        assert projected["requirement_id"] == original_req.requirement_id
        assert contexts[projected["context_ref"]]["description"] == original_req.description
    assert projection["locator_columns"] == ["locator_id", "page_number", "precision", "localized_text"]
    decoded = [dict(zip(projection["locator_columns"], row)) for row in projection["locators"]]
    assert [(item["locator_id"], item["localized_text"]) for item in decoded] == [
        (item.locator_id, item.localized_text) for item in source.available_locators]
    aliases = evidence_normalizer_reference_aliases(source)
    assert aliases.transform(aliases.transform(projection), expand=True) == projection
    assert source.input_scope_sha256 == identity
