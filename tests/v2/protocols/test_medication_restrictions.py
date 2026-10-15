"""Source and time contracts use fictional drugs, not SAR or D001 medical fixtures."""
from copy import deepcopy
from datetime import datetime, UTC

import pytest

from app.domain.contracts.protocol_drafts import ReviewScopeSelection
from app.domain.publication import canonical_hash
from app.protocols.medication_restrictions import (MedicationRestrictionProposal, build_scope_supplement,
    scope_selection_hash, selected_scope_material, validate_scope_supplement)


def frozen_medications():
    key = "a" * 64
    selection = ReviewScopeSelection(scope_content_hash="b" * 64, included_candidate_keys=[key],
        snapshot_id="snapshot-fictional", saved_by="构建者验证", saved_at=datetime.now(UTC))
    text = "筛选前4周内禁止使用药物甲；补救治疗除外。"
    view = {"scope_content_hash": "b" * 64, "structure_sha256": "c" * 64,
        "candidates": [{"candidate_key": key, "scope_kind": "medication_section",
            "source_span_ids": ["title", "clause"], "official_codes": []}],
        "source_records": [{"source_span_id": "title", "identity_status": "ok", "raw_text": "合并用药"},
            {"source_span_id": "clause", "identity_status": "ok", "raw_text": text}], "additional_source_records": []}
    proposal = {"medications": [{"drug_text": "药物甲", "drug_class_id": None,
        "window": {"anchor_type": "screening_date", "direction": "before", "upper_bound": {"value": 4, "unit": "week"}},
        "period": None, "applicable_stages": ["screening"], "exception_excerpt": "补救治疗除外",
        "unresolved_reason": None, "source_quotes": [{"source_span_id": "clause", "excerpt": text}], "applies_to_rule": None}],
        "source_dispositions": [{"source_span_id": "title", "disposition": "heading", "reason": "本节标题"}]}
    return selection, view, proposal


def build(proposal, selection, view):
    return build_scope_supplement(proposal=MedicationRestrictionProposal.model_validate(proposal),
        selection=selection, view=view, phase="phase_iii", official_codes={"EX-01"})


def test_source_union_preserves_calendar_units_exception_and_stable_item_identity():
    selection, view, proposal = frozen_medications()
    result = build(proposal, selection, view)
    assert result.medications[0].item_id.startswith("med:")
    assert len(result.medications[0].item_id) == 28
    assert result.medications[0].window.upper_bound.unit == "week"
    assert result.medications[0].exception_excerpt == "补救治疗除外"
    assert result.selection_sha256 == scope_selection_hash(selection)
    duplicate = deepcopy(view["candidates"][0])
    duplicate["candidate_key"] = "d" * 64
    view["candidates"].append(duplicate)
    selection.included_candidate_keys.append("d" * 64)
    _, _, readable = selected_scope_material(view, selection)
    assert len(readable) == 2
    assert build(proposal, selection, view).medications[0].item_id == result.medications[0].item_id


def test_closed_zero_lower_distance_is_equivalent_not_an_invented_source_duration():
    selection, view, proposal = frozen_medications()
    expected = build(proposal, selection, view).medications[0]
    proposal["medications"][0]["window"]["lower_bound_days"] = 0
    assert build(proposal, selection, view).medications[0] == expected


@pytest.mark.parametrize("fault", ["omitted", "unknown_source", "altered_quote", "wrong_quantity", "wrong_unit", "wrong_anchor",
    "wrong_direction", "invented_exception", "omitted_exception", "expanded_period", "invented_class", "invented_code", "duplicate_disposition", "double_disposition"])
def test_invalid_proposals_cannot_be_saved_as_complete_scope(fault):
    selection, view, proposal = frozen_medications()
    item = proposal["medications"][0]
    if fault == "omitted": proposal["source_dispositions"] = []
    elif fault == "unknown_source": item["source_quotes"][0]["source_span_id"] = "another-snapshot"
    elif fault == "altered_quote": item["source_quotes"][0]["excerpt"] = "筛选前4周内允许使用药物甲。"
    elif fault == "wrong_quantity": item["window"]["upper_bound"]["value"] = 3
    elif fault == "wrong_unit": item["window"]["upper_bound"]["unit"] = "month"
    elif fault == "wrong_anchor": item["window"]["anchor_type"] = "randomization_date"
    elif fault == "wrong_direction": item["window"]["direction"] = "after"
    elif fault == "invented_exception": item["exception_excerpt"] = "所有情况均例外"
    elif fault == "omitted_exception": item["exception_excerpt"] = None
    elif fault == "expanded_period": item.update(window=None, period="study_period")
    elif fault == "invented_class": item["drug_class_id"] = "not_in_dictionary"
    elif fault == "invented_code": item["applies_to_rule"] = "EX-99"
    elif fault == "duplicate_disposition": proposal["source_dispositions"] *= 2
    elif fault == "double_disposition": proposal["source_dispositions"].append({"source_span_id": "clause", "disposition": "background", "reason": "不能同时将限制当背景"})
    with pytest.raises(ValueError): build(proposal, selection, view)


def test_true_unknown_remains_unknown_and_not_a_default_screening_window():
    selection, view, proposal = frozen_medications()
    proposal["medications"][0].update(window=None, applicable_stages=[], unresolved_reason="原文未定义时间起点")
    result = build(proposal, selection, view)
    assert result.medications[0].window is None and result.medications[0].period is None
    assert result.medications[0].unresolved_reason == "原文未定义时间起点"
    validate_scope_supplement(result, selection=selection, view=view, phase="phase_iii", official_codes={"EX-01"})
    tampered = result.model_copy(deep=True)
    tampered.medications[0].item_id = "med:" + "0" * 24
    with pytest.raises(ValueError):
        validate_scope_supplement(tampered, selection=selection, view=view, phase="phase_iii", official_codes={"EX-01"})


def test_new_optional_fields_do_not_change_existing_draft_or_ruleset_hashes():
    from tests.v2.protocols.slice4_helpers import confirmed_fixture
    from app.domain.contracts.agent_io import ProtocolDeconstructionDraft
    from app.domain.contracts.rules import RuleSet
    _, draft, _ = confirmed_fixture()
    payload = draft.model_dump(mode="json")
    assert "scope_supplement" not in payload
    assert canonical_hash(ProtocolDeconstructionDraft.model_validate(payload).model_dump(mode="json")) == canonical_hash(payload)
    rules = RuleSet(rule_set_id="fixture", protocol_version_id=draft.protocol_version_id,
        study_phase=draft.selected_phase, rules=draft.proposed_rules, revision=1)
    assert "scope_supplement" not in rules.model_dump(mode="json")
