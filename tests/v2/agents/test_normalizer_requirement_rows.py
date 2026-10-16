"""Lossless input layout; never a new source policy or model quality claim."""
from copy import deepcopy
import json

import pytest

from app.agents.evidence_normalizer import (
    _compact_requirement_rows, build_evidence_normalizer_prompt,
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, evidence_normalizer_prompt_template_sha256,
)
from app.domain.variables.dictionary import VariableDef
from tests.v2.agents.test_evidence_normalizer_adapter import _input, _requirement


@pytest.mark.parametrize("variables", [False, True])
def test_prompt_rows_round_trip_every_requirement_without_changing_sources(variables):
    requirements = [_requirement(f"synthetic-{index:02d}", "病史") for index in range(25)]
    evidence = _input(requirements)
    if variables:
        evidence = evidence.model_copy(update={"variable_definitions": [VariableDef(
            variable_id="synthetic_history", label_zh="病史", value_type="boolean", domain="history")]})
    before = evidence.model_dump_json()
    options = dict(prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, include_output_schema=False)
    old = build_evidence_normalizer_prompt(evidence, **options)
    assert old == build_evidence_normalizer_prompt(evidence, compact_requirement_rows=False, **options)
    compact = build_evidence_normalizer_prompt(evidence, compact_requirement_rows=True, **options)
    payload, _ = json.JSONDecoder().raw_decode(compact.split("本次输入：", 1)[1])
    for name in ("related_requirements", "requirement_contexts"):
        columns = payload.pop(name + "_columns", None)
        if columns:
            assert all(len(row) == len(columns) for row in payload[name])
            payload[name] = [dict(zip(columns, row, strict=True)) for row in payload[name]]
    old_payload, _ = json.JSONDecoder().raw_decode(old.split("本次输入：", 1)[1])
    assert payload == old_payload
    assert len(compact) < len(old)
    assert evidence.model_dump_json() == before


@pytest.mark.parametrize("rows", [[], [{"a": None}, {"b": None}], [{"a": None}, {"a": None, "b": []}],
    [None], [[], []], [{"short": 1}]])
def test_empty_or_heterogeneous_records_are_not_padded_or_reinterpreted(rows):
    payload = {"related_requirements": deepcopy(rows), "unrelated": [{"a": 1}]}
    before = deepcopy(payload)
    _compact_requirement_rows(payload)
    assert payload == before


def test_compaction_retains_nested_policies_nulls_order_and_extra_fields():
    rows = [{"requirement_id": "r1", "required_source_types": ["original"], "allows_transcription": False,
        "value": None, "extra": {"unknown": True}},
        {"requirement_id": "r2", "required_source_types": [], "allows_transcription": True,
        "value": "", "extra": {"unknown": False}}]
    payload = {"related_requirements": deepcopy(rows)}
    _compact_requirement_rows(payload)
    assert [dict(zip(payload["related_requirements_columns"], row, strict=True))
        for row in payload["related_requirements"]] == rows


@pytest.mark.parametrize("value", [None, 1, "true", [], {}])
def test_invalid_layout_is_rejected_not_coerced(value):
    with pytest.raises(ValueError, match="紧凑格式"):
        build_evidence_normalizer_prompt(_input(), prompt_template="按原文读取", compact_requirement_rows=value)
    with pytest.raises(ValueError, match="紧凑格式"):
        evidence_normalizer_prompt_template_sha256("按原文读取", compact_requirement_rows=value)


def test_opt_in_changes_identity_without_changing_schema_or_legacy_hash():
    legacy = evidence_normalizer_prompt_template_sha256(DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE)
    assert legacy == "dd2d86d2da5d1ee69ea98aa6f7bb8854c3fa915c077f4b78f2af5c2cc4d3dbe8"
    assert legacy != evidence_normalizer_prompt_template_sha256(
        DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, compact_requirement_rows=True)
