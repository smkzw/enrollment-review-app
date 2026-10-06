"""Actual parser checks; simple pair scope is not a receipt-verification fixture."""

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.domain.contracts.binding_qualification import (
    BindingQualificationBatch, binding_qualification_batch_hash,
)
from app.domain.contracts.qualified_binding_selection import QualificationAdoptionAuthorization
from app.llm.binding_qualification import validate_binding_qualification_payload


def _judgment(**changes):
    return {
        "pair_id": "a" * 64,
        "source_admissibility": "admissible",
        "object_match": "supported",
        "attribute_match": "direct",
        "denial_scope": "compatible",
        "temporal_role": "not_applicable",
        "direct_operand_usable": "usable",
        "unresolved_reasons": [],
        "explanation": "The source and operand agree; no unresolved dimension.",
        **changes,
    }


def _parse(judgment, *, fact_attribute="value"):
    material = {
        "frozen_input_sha256": "b" * 64, "candidate_job_id": "synthetic",
        "pair_ids": ["a" * 64], "identity_sha256s": ["c" * 64],
        "fact_ids": ["synthetic-fact"], "locator_ids": ["synthetic-locator"],
    }
    batch = BindingQualificationBatch(
        **material, batch_sha256=binding_qualification_batch_hash(material),
    )
    pairs = [SimpleNamespace(
        pair_id="a" * 64, source_policy_status="present",
        fact_attribute=fact_attribute,
    )]
    return validate_binding_qualification_payload(
        pairs, json.dumps({"results": [judgment]}), batch=batch,
    ).results[0]


def test_positive_explanation_is_not_an_unresolved_reason():
    judgment = _judgment()
    assert _parse(judgment).model_dump(mode="json") == judgment


@pytest.mark.parametrize("field,value", [
    ("source_admissibility", "inadmissible"),
    ("source_admissibility", "unresolved"),
    ("object_match", "uncertain"),
    ("object_match", "rejected"),
    ("attribute_match", "rejected"),
    ("attribute_match", "context_only"),
    ("attribute_match", "derivation_operand"),
    ("denial_scope", "incompatible"),
    ("temporal_role", "mismatched"),
    ("direct_operand_usable", "not_usable"),
])
def test_negative_dimension_is_preserved_and_missing_reason_rejected(field, value):
    judgment = _judgment(**{field: value})
    with pytest.raises(ValidationError):
        _parse(judgment)
    judgment["unresolved_reasons"] = ["A specific unresolved dimension remains."]
    assert _parse(judgment).model_dump(mode="json") == judgment


def test_record_time_is_preserved_not_rewritten_to_uncertain():
    assert _parse(_judgment(temporal_role="record_time")).temporal_role == "record_time"
    with pytest.raises(ValueError, match="记录时间"):
        _parse(_judgment(temporal_role="event_date"), fact_attribute="record_time")


@pytest.mark.parametrize("changes", [
    {"object_match": "unsupported-enum"}, {"source_admissibility": "weak"},
    {"temporal_role": "record_date"}, {"denial_scope": "not_mentioned"},
])
def test_invalid_enum_is_rejected_not_converted_into_unknown(changes):
    with pytest.raises(ValidationError):
        _parse(_judgment(**changes))


@pytest.mark.parametrize("missing", ["denial_scope", "direct_operand_usable", "explanation"])
def test_missing_required_field_is_not_completed_from_explanation(missing):
    judgment = _judgment()
    judgment.pop(missing)
    with pytest.raises(ValidationError):
        _parse(judgment)


@pytest.mark.parametrize("version", ["binding-qualification/v5", "binding-qualification/v6"])
def test_authorization_contract_can_name_current_or_historical_version_without_issuing_it(version):
    route = {"provider": "synthetic", "base_url": "https://invalid.example",
             "model": "synthetic", "reasoning_effort": "high", "max_tokens": 65536}
    material = {
        "authorization_id": "synthetic", "authorizing_service": "synthetic",
        "qualification_job_id": "synthetic", "candidate_family": "predicate",
        "qualification_prompt_version": version,
        "frozen_input_sha256": "a" * 64, "comparison_sha256": "b" * 64,
        "summary_logical_sha256": "c" * 64, "summary_artifact_sha256": "d" * 64,
        "approved_evaluation_evidence_sha256": "e" * 64,
        "route_identities": {"main-A": route, "main-B": route},
    }
    authorization = QualificationAdoptionAuthorization(**material)
    assert authorization.qualification_prompt_version == version
    assert authorization.qualification_contract == "binding-qualification-job/v3"
    with pytest.raises(ValidationError):
        QualificationAdoptionAuthorization(**{**material, "authorization_id": ""})
