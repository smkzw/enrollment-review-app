from types import SimpleNamespace

import pytest

from app.services.qualified_proposition_evidence import select_qualified_relations
from app.services.predicate_proposition_calculation import calculate_predicate_proposition_fact
from app.domain.contracts.enums import TruthValue


@pytest.mark.parametrize("obligation", ["required", "not_required_by_source", "unresolved"])
@pytest.mark.parametrize("direction", ["event_present", "event_absent", "unresolved"])
def test_source_record_purpose_survives_author_artifact_and_proposition_context(tmp_path, obligation, direction):
    import json
    from app.agents.protocol_deconstructor import (
        _wire_dnf_expression, _wire_atom_schema, protocol_output_response_format,
    )
    from app.domain.contracts.rules import AtomicExpression
    from app.domain.publication import canonical_hash
    from app.evidence.artifacts import ArtifactStore
    from app.storage.config import resolve_data_paths
    from app.llm.proposition_context import proposition_context
    from jsonschema import validate

    quote = "核对既往事件情况并保留指定记录"
    purpose = {"target_kind": "event_history", "record_obligation": obligation,
               "proposition_direction": direction, "source_excerpts": [quote]}
    atom = {"subject": "受试者", "attribute": "既往事件", "negated": False,
            "source_locator": {"source_clause": quote}, "requires_professional_judgment": False,
            "semantic_proposition": quote, "repeat_scheme": None, "observation_policy": None,
            "record_semantics": purpose}
    schema = _wire_atom_schema(shape="existence", unit_schema={"type": ["string", "null"]})
    schema["$defs"] = protocol_output_response_format("semantic_candidate", compact=True)["json_schema"]["schema"]["$defs"]
    validate(atom, schema)
    expression, _ = _wire_dnf_expression([{"existence_atoms": [atom], "scalar_atoms": [], "set_atoms": []}],
                                        identity_prefix="test-purpose", label="trigger", source_text=quote)
    typed = AtomicExpression.model_validate(expression)
    payload = typed.model_dump(mode="json")
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "purpose-artifacts")))
    artifact = store.put("raw_response", json.dumps(payload, ensure_ascii=False).encode())
    loaded = AtomicExpression.model_validate_json(store.read(artifact.storage_ref))
    pair = SimpleNamespace(candidate_family="predicate", condition={
        "predicate": loaded.predicate.model_dump(mode="json"), "source_status": "verbatim"})
    spec, _ = proposition_context(pair)
    assert spec["record_semantics"] == purpose
    assert loaded.predicate.record_semantics.record_obligation == obligation
    legacy = loaded.predicate.model_copy(update={"record_semantics": None})
    assert "record_semantics" not in legacy.model_dump(mode="json")
    assert canonical_hash(legacy.model_dump(mode="json")) != canonical_hash(loaded.predicate.model_dump(mode="json"))
    # These are saved author declarations, not patient observations or adopted truth.
    assert "verified" not in purpose and "accepted" not in purpose
    from app.domain.contracts.binding_qualification import (
        BindingQualificationPairContext, binding_qualification_pair_id,
    )
    from app.llm.binding_qualification import plan_qualification_batches
    from app.llm.proposition_evidence import build_proposition_evidence_messages
    identity = dict(candidate_job_id="synthetic-purpose", frozen_input_sha256="b" * 64,
                    identity_field="predicate_identity_sha256", identity_sha256="c" * 64,
                    fact_id="fact", fact_attribute="assertion_basis", locator_id="locator",
                    candidate_batch_sha256=None)
    source = BindingQualificationPairContext(
        **identity, pair_id=binding_qualification_pair_id(**identity),
        candidate_family="predicate", candidate_job_type="predicate_binding_candidates",
        candidate_contract="synthetic", comparison_sha256="d" * 64, condition=pair.condition,
        fact={"fact_id": "fact", "assertion_basis": {"locator_id": "locator", "assertion_text": "既往情况已记录"}},
        locator={"locator_id": "locator", "excerpt": "既往情况已记录"}, episode={"stage": "screening"},
        parent_source_context={}, source_policy_status="missing",
        lane_declarations={"main-A": {}, "main-B": {}},
        candidate_receipt_sha256s={"main-A": ["a" * 64], "main-B": ["e" * 64]},
    )
    batch = plan_qualification_batches([source])[0]
    messages = build_proposition_evidence_messages([source], batch)
    request = json.loads(messages[1]["content"][0]["text"])
    assert request["conditions"][source.identity_sha256]["condition"]["record_semantics"] == purpose
    assert request["prompt_version"] == "proposition-evidence/v8"
    assert "不证明患者资料已读全或未发生" in messages[0]["content"]


def test_legacy_normalization_call_does_not_acquire_a_reading_claim():
    from datetime import UTC, datetime
    from app.domain.contracts.facts import FactNormalizationCall
    original = dict(schema_version="phase5/v1", call_id="call", run_id="run", logical_document_id="doc",
                    page_numbers=[1], status="succeeded", input_sha256="a" * 64,
                    raw_output_sha256="b" * 64, created_at="2026-10-06T00:00:00Z")
    call = FactNormalizationCall.model_validate(original)
    assert call.reading_method is None
    assert call.model_dump(mode="json") == original
    with pytest.raises(ValueError, match="读取方式"):
        FactNormalizationCall(**{**original, "status": "running", "reading_method": "model_response"})


@pytest.mark.parametrize("change", [
    {"source_excerpts": ["另一条要求"]}, {"source_excerpts": [" "]},
    {"source_excerpts": ["既往事件", "既往事件"]}, {"verified": True},
    {"target_kind": "other", "proposition_direction": "event_absent"},
])
def test_record_purpose_rejects_borrowed_sources_and_adoption_flags(change):
    from app.domain.contracts.rules import AtomicPredicate
    purpose = {"target_kind": "event_history", "record_obligation": "not_required_by_source",
               "proposition_direction": "event_present", "source_excerpts": ["既往事件"], **change}
    with pytest.raises(ValueError):
        AtomicPredicate(predicate_id="history", subject="受试者", attribute="事件", comparator="exists",
                        source_clause="核对既往事件", record_semantics=purpose)


def test_required_judgment_cannot_be_reclassified_as_no_record_obligation():
    from app.domain.contracts.rules import AtomicPredicate
    from app.domain.contracts.control_evaluation_spec import ControlAtomEvaluationSpec
    purpose = {"target_kind": "other", "record_obligation": "not_required_by_source",
               "proposition_direction": "unresolved", "source_excerpts": ["研究者书面判断"]}
    with pytest.raises(ValueError, match="研究者判断"):
        AtomicPredicate(predicate_id="judge", subject="研究者", attribute="判断", comparator="exists",
                        source_clause="研究者书面判断", requires_professional_judgment=True,
                        record_semantics=purpose)
    with pytest.raises(ValueError, match="研究者判断"):
        ControlAtomEvaluationSpec(determination_mode="investigator_judgment", proposition="研究者书面判断",
                                 time_purpose="not_applicable", source_span_ids=["span"],
                                 source_excerpts=["研究者书面判断"], record_semantics=purpose)


def test_cross_chapter_history_and_required_record_are_independent_source_axes():
    from app.domain.contracts.control_evaluation_spec import ControlAtomEvaluationSpec
    purpose = {"target_kind": "event_history", "record_obligation": "required",
               "proposition_direction": "event_present", "source_excerpts": ["既往事件须以规定记录核对"]}
    spec = ControlAtomEvaluationSpec(determination_mode="semantic", proposition=purpose["source_excerpts"][0],
                                    time_purpose="not_applicable", source_span_ids=["span"],
                                    source_excerpts=purpose["source_excerpts"], record_semantics=purpose)
    pair = SimpleNamespace(candidate_family="control", condition={"atom": {"evaluation": spec.model_dump(mode="json")}})
    from app.llm.proposition_context import proposition_context
    restored, _ = proposition_context(pair)
    assert restored["record_semantics"] == purpose


@pytest.mark.parametrize("serialized_property", [False, True])
def test_official_proposition_rebuilds_source_from_actual_serialized_predicate(serialized_property):
    from app.domain.contracts.rules import AtomicPredicate
    from app.llm.proposition_context import proposition_context

    quote = "曾有示例药物用药史"
    predicate = AtomicPredicate(predicate_id="history", subject="medication_history", attribute="history",
                                comparator="exists", source_clause=quote, semantic_proposition=quote)
    wire = predicate.model_dump(mode="json")
    assert "exact_source_clauses" not in wire
    if serialized_property:
        wire["exact_source_clauses"] = [quote]
    pair = SimpleNamespace(candidate_family="predicate", condition={"predicate": wire, "source_status": "verbatim"})
    spec, _ = proposition_context(pair)
    assert spec["source_excerpts"] == [quote]
    assert spec["proposition"] == quote
    wire["exact_source_clauses"] = ["连续实际用药30天"]
    with pytest.raises(ValueError, match="逐字原文不一致"):
        proposition_context(pair)


@pytest.mark.parametrize("source_status,source_clause", [("unverified", "已完成检查"), ("verbatim", None)])
def test_official_proposition_rejects_unverified_or_missing_frozen_source(source_status, source_clause):
    from app.domain.contracts.rules import AtomicPredicate
    from app.llm.proposition_context import proposition_context

    predicate = AtomicPredicate(predicate_id="check", subject="procedure", attribute="completion",
                                comparator="exists", source_clause=source_clause, semantic_proposition="已完成检查")
    pair = SimpleNamespace(candidate_family="predicate",
                           condition={"predicate": predicate.model_dump(mode="json"), "source_status": source_status})
    with pytest.raises(ValueError, match="缺少明确原文"):
        proposition_context(pair)


@pytest.mark.parametrize("kind,correspondence,expected", [
    ("statement_of_intent", "supported", TruthValue.TRUE),
    ("statement_of_intent", "partial", TruthValue.UNKNOWN),
    ("ongoing_conduct", "supported", TruthValue.UNKNOWN),
    ("unresolved", "unresolved", TruthValue.UNKNOWN),
])
def test_source_defined_period_reaches_real_proposition_context_and_consumer(kind, correspondence, expected):
    from app.domain.contracts.rules import AtomicPredicate
    from app.llm.proposition_context import prospective_requirement, prospective_sources

    text = "计划在准备阶段及干预阶段（第六次访视之前）接受专项评估"
    predicate = AtomicPredicate(predicate_id="planned", subject="受试者", attribute="计划接受专项评估",
        comparator="exists", source_clause=text, semantic_proposition=text,
        prospective_period={"kind": "source_defined", "source_excerpts": [text]})
    wire = {**predicate.model_dump(mode="json"), "exact_source_clauses": predicate.exact_source_clauses}
    pair = SimpleNamespace(candidate_family="predicate", condition={"predicate": wire, "source_status": "verbatim"})
    assert prospective_requirement(pair) == {"prospective_period": {"kind": "source_defined", "source_excerpts": [text]}}
    assert prospective_sources(pair) == [{"excerpt": text}]
    entry = SimpleNamespace(predicate=predicate, time_constraint=None)
    future = {"requirement_kind": kind, "requirement_quote": text,
              "period_correspondence": correspondence,
              "period_quote": None if correspondence == "unresolved" else "声明涉及上述期间"}
    records = [{"status": "entails_agreed", "lanes": {
        "main-A": {"prospective_evidence": future}, "main-B": {"prospective_evidence": future}}}]
    fact = SimpleNamespace(fact_id="fact", conflict_group_id=None)
    result = calculate_predicate_proposition_fact(entry, fact, records, SimpleNamespace())
    assert result.truth == expected
    records[0]["lanes"]["main-B"]["prospective_evidence"] = None
    assert calculate_predicate_proposition_fact(entry, fact, records, SimpleNamespace()).truth == TruthValue.UNKNOWN


@pytest.mark.parametrize(("kind", "correspondence", "truth", "reason"), [
    ("statement_of_intent", "supported", TruthValue.TRUE, "prospective_statement_verified"),
    ("ongoing_conduct", "supported", TruthValue.UNKNOWN, "future_conduct_not_established"),
    ("statement_of_intent", "partial", TruthValue.UNKNOWN, "prospective_statement_period_unverified"),
    ("unresolved", "supported", TruthValue.UNKNOWN, "prospective_requirement_unverified"),
])
def test_prospective_consumer_does_not_promote_a_statement_to_future_fulfillment(kind, correspondence, truth, reason):
    entry = SimpleNamespace(predicate=SimpleNamespace(prospective_period={"period": "study_period"},
        prospective_window={"anchor_type": "last_dose_date", "upper_bound": {"value": 4, "unit": "week"}}),
        time_constraint=None)
    fact = SimpleNamespace(fact_id="source-fact", conflict_group_id=None)
    future = {"requirement_kind": kind, "requirement_quote": "同意在研究期间及末次给药后四周避免某操作",
        "period_correspondence": correspondence, "period_quote": "同意遵守上述完整期间要求"}
    records = [{"status": "entails_agreed", "lanes": {
        "main-A": {"prospective_evidence": future}, "main-B": {"prospective_evidence": future},
    }}]
    result = calculate_predicate_proposition_fact(entry, fact, records, SimpleNamespace())
    assert result.truth == truth
    assert reason in result.reason_codes
    if truth == TruthValue.UNKNOWN:
        assert "prospective_statement_verified" not in result.reason_codes


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
