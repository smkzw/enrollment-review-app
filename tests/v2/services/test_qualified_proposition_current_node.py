from types import SimpleNamespace

import pytest

from app.services.qualified_proposition_evidence import select_qualified_relations


@pytest.mark.parametrize(
    ("current_node", "role", "expected_reason"),
    [
        ("rules:2:screening", "decide_at_node", None),
        ("rules:2:baseline", "decide_at_node", "proposition_current_node_mismatch"),
        ("rules:2:screening", "early_attention", "proposition_current_node_unverified"),
        (None, "decide_at_node", "proposition_current_node_unverified"),
    ],
)
def test_control_relation_requires_frozen_current_decision_node(
    monkeypatch, current_node, role, expected_reason,
):
    import app.services.qualified_binding_selection as binding_selection

    monkeypatch.setattr(binding_selection, "pair_direct_selection_rejection_reasons",
                        lambda *args, **kwargs: [])
    monkeypatch.setattr(binding_selection, "source_validity_operand_calculable",
                        lambda *args, **kwargs: False)
    pair = SimpleNamespace(
        pair_id="pair", candidate_family="control", fact_id="fact", locator_id="locator",
        episode={"workflow_stage_id": current_node},
        parent_source_context={
            "workflow_stage_map": {"screening": "rules:2:screening"},
            "review_node_bindings": [{"workflow_stage_id": "screening", "role": role}],
        },
        condition={"atom": {"evaluation": {
            "determination_mode": "semantic", "proposition": "应完成本次检查",
            "observation_policy": {"mode": "unresolved"},
        }}},
    )
    source = SimpleNamespace(pair_id="pair", identity_sha256="identity", fact_id="fact")
    evidence = {
        "pairs": [pair],
        "summary": {"comparisons": [{"records": [{
            "pair_id": "pair", "identity_sha256": "identity", "status": "entails_agreed",
            "lanes": {"main-A": {"assertion_extent": "individual"},
                      "main-B": {"assertion_extent": "individual"}},
        }]}]},
    }
    selected, unresolved = select_qualified_relations(evidence, [source])
    if expected_reason is None:
        assert len(selected) == 1
        assert unresolved == []
    else:
        assert selected == []
        assert len(unresolved) == 1
        assert expected_reason in unresolved[0]["reasons"]


def test_action_completion_needs_both_readers_explicit_source_witness(monkeypatch):
    import app.services.qualified_binding_selection as binding_selection

    monkeypatch.setattr(binding_selection, "pair_direct_selection_rejection_reasons",
                        lambda *args, **kwargs: [])
    monkeypatch.setattr(binding_selection, "source_validity_operand_calculable",
                        lambda *args, **kwargs: False)
    pair = SimpleNamespace(
        pair_id="pair", candidate_family="control", fact_id="fact", locator_id="locator",
        episode={"workflow_stage_id": "rules:2:screening"},
        parent_source_context={
            "workflow_stage_map": {"screening": "rules:2:screening"},
            "review_node_bindings": [{"workflow_stage_id": "screening", "role": "decide_at_node"}],
        },
        condition={"atom": {"evaluation": {
            "determination_mode": "semantic", "proposition": "应完成本次检查",
            "observation_policy": {"mode": "action_completion"},
        }}},
    )
    source = SimpleNamespace(pair_id="pair", identity_sha256="identity", fact_id="fact")
    lanes = {
        "main-A": {"assertion_extent": "individual"},
        "main-B": {"assertion_extent": "individual"},
    }
    record = {"pair_id": "pair", "identity_sha256": "identity", "status": "entails_agreed",
              "lanes": lanes}
    evidence = {"pairs": [pair], "summary": {"comparisons": [{"records": [record]}]}}
    selected, unresolved = select_qualified_relations(evidence, [source])
    assert selected == []
    assert "action_completion_source_unverified" in unresolved[0]["reasons"]

    for lane in lanes.values():
        lane["action_witness"] = {"status": "completed", "action_quote": "已完成本次检查"}
        lane["scope_correspondence"] = "supported"
        lane["scope_quote"] = "筛选期"
    selected, unresolved = select_qualified_relations(evidence, [source])
    assert len(selected) == 1 and unresolved == []
