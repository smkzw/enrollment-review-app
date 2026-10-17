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


@pytest.mark.parametrize("change", ["same", "new_binding", "new_description", "removed", "changed_definition"])
def test_saved_extraction_scope_does_not_claim_changed_or_new_targets(change):
    from app.domain.variables.extraction import ExtractionTargets, unread_extraction_targets
    definition = load_dictionary()["age"]
    from app.domain.contracts.rules import EvidenceRequirement
    requirement = EvidenceRequirement(requirement_id="age-record", rule_component_id="age-component",
        fact_type="年龄", variable_id="age", due_stage=ReviewStage.SCREENING, description="年龄记录")
    before = ExtractionTargets((requirement,), (definition,))
    variables, requirements = before.variables, before.requirements
    if change == "new_binding":
        variables = (*variables, definition.model_copy(update={"variable_id": "different_measurement"}))
        requirements = (requirement.model_copy(update={"variable_id": "different_measurement"}),)
    elif change == "new_description":
        requirements = (requirement.model_copy(update={"description": "另一个有源要求"}),)
    elif change == "removed":
        variables, requirements = (), ()
    elif change == "changed_definition":
        variables = (definition.model_copy(update={"label_zh": "不同含义的数据项目"}),)
    result = unread_extraction_targets(before, ExtractionTargets(requirements, variables))
    expected_variables = ["different_measurement"] if change == "new_binding" else ["age"] if change == "changed_definition" else []
    expected_requirements = [requirement.requirement_id] if change in {"new_binding", "new_description"} else []
    assert result == (expected_variables, expected_requirements)
    assert before.requirements == (requirement,) and before.variables == (definition,)


def test_source_page_target_coverage_preserves_old_hash_and_cannot_imply_absence():
    from hashlib import sha256
    from app.domain.contracts.work_draft import WorkDraftSourcePage
    data = dict(source_document_version_id="doc", page_artifact_id="page", page_number=1,
        effective_text="有源记录", effective_text_sha256=sha256("有源记录".encode()).hexdigest(), extraction_complete=True)
    original = WorkDraftSourcePage(**data)
    assert original.model_dump(mode="json") == {**data, "document_category": None}
    updated = WorkDraftSourcePage(**data, unread_variable_ids=["new_value"], unread_requirement_ids=["new_requirement"])
    assert not updated.extraction_covers()
    assert not updated.extraction_covers(variable_ids=["new_value"])
    assert not updated.extraction_covers(requirement_ids=["new_requirement"])
    assert updated.extraction_covers(variable_ids=["unchanged_value"], requirement_ids=["unchanged_requirement"])
    assert not updated.model_copy(update={"extraction_complete": False}).extraction_covers(variable_ids=["unchanged_value"])
    for invalid in (["new_value", "new_value"], ["z", "a"], [" "]):
        with pytest.raises(ValueError):
            WorkDraftSourcePage(**data, unread_variable_ids=invalid)


def test_reference_ratio_expands_only_its_declared_raw_input():
    requirement = SimpleNamespace(requirement_id="ratio", due_stage=ReviewStage.SCREENING,
        variable_id="ast_uln_ratio", procedure_catalog_item_id=None)
    original = load_dictionary()["ast_uln_ratio"].model_dump(exclude={"reference_ratio_of"})
    from app.domain.variables.dictionary import VariableDef
    saved = VariableDef.model_validate(original)
    targets = build_extraction_targets(SimpleNamespace(variable_definitions=[saved], review_records=[]),
        ReviewStage.SCREENING, [requirement])
    assert [x.variable_id for x in targets.variables] == ["ast", "ast_uln_ratio"]
    assert targets.variables[1].reference_ratio_of == "ast"
    assert saved.model_dump() == original
    with pytest.raises(ValueError, match="不同定义"):
        load_dictionary([saved.model_copy(update={"canonical_unit": "different"})])


@pytest.mark.parametrize("row,range_text,value,accepted", [
    ("ALT 180 10-100 U/L", "10-100", 180, True),
    ("ALT 180 U/L ≤100", "≤100", 180, True),
    ("ALT 180 10--100 U/L", "10--100 U/L", 180, True),
    ("ALT 180 ↑≤100 U/L", "≤100 U/L", 180, True),
    ("ALT 180 10--100 mg/dL", "10--100 mg/dL", 180, False),
    ("ALT 180 10--100 U/L AST 25", "10--100 U/L", 180, False),
    ("ALT 1.8 10-100 U/L", "10-100", 100, False),
    ("ALT 180\nAST 10-100 U/L", "10-100", 180, False),
    ("ALT 180 10-100 AST 35 U/L", "10-100", 180, False),
    ("ALT 180 100-10 U/L", "100-10", 180, False),
    ("ALT 180 <0 U/L", "<0", 180, False),
    ("ALT 180 10-100", "10-100", 180, False),
    ("ALT 180 2025-08-08 U/L", "2025-08-08", 180, False),
])
def test_reference_upper_requires_same_field_not_same_page(row, range_text, value, accepted):
    from app.domain.risk_flags import reference_upper_bound
    from app.domain.contracts.fact_context import FactContextQualifier
    basis = SimpleNamespace(asserted_object="ALT", assertion_text=row,
        contextual_qualifiers=[FactContextQualifier(kind="reference_range", label=range_text)])
    fact = SimpleNamespace(assertion_basis=basis, value=value, unit="U/L")
    if accepted:
        assert reference_upper_bound(fact) == 100
    else:
        with pytest.raises(ValueError):
            reference_upper_bound(fact)


@pytest.mark.parametrize("row,range_text,value,expected", [
    ("ALT 180 10-100 U/L", "10-100", 180, "high"),
    ("ALT 5 10-100 U/L", "10-100", 5, "low"),
    ("ALT 50 10-100 U/L", "10-100", 50, None),
    ("ALT 10 10-100 U/L", "10-100", 10, None),
    ("ALT 100 10-100 U/L", "10-100", 100, None),
    ("ALT 100 <100 U/L", "<100", 100, "high"),
    ("ALT 100 ≤100 U/L", "≤100", 100, None),
    ("ALT 5 U/L １０～１００", "１０～１００", 5, "low"),
    ("ALT 180 10-100 mg/dL", "10-100", 180, None),
    ("ALT 180\nAST 10-100 U/L", "10-100", 180, None),
    ("ALT 1.8 10-100 U/L", "10-100", 100, None),
    ("ALT 180 10-100 U/L AST 25", "10-100", 180, None),
])
def test_reference_abnormality_is_display_only_and_requires_same_row(row, range_text, value, expected):
    from app.domain.risk_flags import reference_abnormality
    from app.domain.contracts.fact_context import FactContextQualifier
    basis = SimpleNamespace(asserted_object="ALT", assertion_text=row,
        contextual_qualifiers=[FactContextQualifier(kind="reference_range", label=range_text)])
    fact = SimpleNamespace(assertion_basis=basis, value=value, unit="U/L")
    assert reference_abnormality(fact) == expected
    assert fact.value == value
    assert basis.assertion_text == row
    fact.assertion_basis = None
    assert reference_abnormality(fact) is None


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
