import json
from types import SimpleNamespace

import pytest

import app.llm.proposition_evidence as module


PAIR_ID = "a" * 64
PROPOSITION_ID = "b" * 64


def _answer(status, relation, quote):
    return {"results": [{
        "pair_id": PAIR_ID,
        "proposition_sha256": PROPOSITION_ID,
        "scope": "pair_local",
        "scope_correspondence": "supported",
        "scope_quote": "筛选期",
        "assertion_extent": "individual",
        "scope_population": "unresolved",
        "population_quote": None,
        "prospective_evidence": None,
        "action_witness": {"status": status, "action_quote": quote},
        "target_correspondence": "supported",
        "node_correspondence": "supported",
        "investigator_attribution": "not_applicable",
        "relation": relation,
        "basis": "insufficient" if relation == "undetermined" else "explicit_statement",
        "quoted_evidence": "筛选期已完成检查",
        "explanation": "只核对检查操作",
        "unresolved_reasons": ["操作完成未证实"] if relation == "undetermined" else [],
    }]}


@pytest.fixture
def action_pair(monkeypatch):
    monkeypatch.setattr(module, "_spec", lambda pair: {
        "determination_mode": "semantic",
        "observation_policy": {"mode": "action_completion"},
    })
    monkeypatch.setattr(module, "_proposition_identity", lambda pair: PROPOSITION_ID)
    monkeypatch.setattr(module, "prospective_requirement", lambda pair: None)
    return SimpleNamespace(pair_id=PAIR_ID, locator={"excerpt": "筛选期已完成检查"})


def test_action_completion_requires_matching_source_witness(action_pair):
    result = module.validate_proposition_evidence_payload(
        [action_pair], json.dumps(_answer("completed", "entails", "已完成检查")),
    )
    assert result.results[0].action_witness.status == "completed"
    negative = _answer("explicit_not_completed", "contradicts", "未做检查")
    negative["results"][0]["quoted_evidence"] = "筛选期未做检查"
    action_pair.locator["excerpt"] = "筛选期未做检查"
    assert module.validate_proposition_evidence_payload(
        [action_pair], json.dumps(negative),
    ).results[0].relation == "contradicts"


@pytest.mark.parametrize("status,relation,quote", [
    ("completed", "contradicts", "已完成检查"),
    ("completed", "entails", "其他页面已完成检查"),
    ("not_established", "entails", None),
])
def test_action_completion_rejects_direction_or_unowned_quote(action_pair, status, relation, quote):
    with pytest.raises(ValueError):
        module.validate_proposition_evidence_payload(
            [action_pair], json.dumps(_answer(status, relation, quote)),
        )
