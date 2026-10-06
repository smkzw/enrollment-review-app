"""Structural recovery must preserve valid siblings without approving meaning."""
import copy
import json

import jsonschema
import pytest

from app.agents.protocol_deconstructor import (
    ProtocolAgentResponse, _collect_initial_semantic_response, _compact_schema,
)
from app.agents.protocol_schema_repair import (
    assemble_invalid_component_proposal, decode_fenced_repair_proposal,
    recover_invalid_component, recover_structural_batch, verify_repair_preserves_valid_parts,
    plan_source_field_repair, apply_source_field_repair, SOURCE_FIELD_REPAIR_VERSION,
    recover_source_fields, source_field_repair_prompt,
    assemble_declared_input_references, assemble_unresolved_observation_sources,
    plan_period_source_repair, PERIOD_SOURCE_REPAIR_VERSION,
)
from app.domain.contracts.agent_io import ProtocolSemanticDeconstructionCandidate
from app.domain.contracts.agent_io import ProtocolSemanticRuleRepair
from app.domain.contracts.occurrence_scope import OccurrenceScope
from app.llm.logical_call_budget import LogicalCallBudget
from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture, _catalog
from tests.v2.protocols.test_protocol_deconstructor_adapter_slice3 import FakeTransport, _semantic_candidate


def candidate():
    source, draft, _ = _fixture()
    return source, _semantic_candidate(source, draft)


def period_source_proposal():
    from app.domain.contracts.rules import AtomicExpression, AtomicPredicate

    source, good = candidate()
    prefix = "在准备期及治疗后六个月内，"
    branch = "甲类受试者同意采取措施甲"
    full = prefix + branch + "，乙类受试者同意采取措施乙。"
    source.source_materials[0].text = full
    component = good.proposed_rules[0].components[0]
    component.source_excerpts = [prefix, branch]
    component.expression = AtomicExpression(predicate=AtomicPredicate(
        predicate_id="period-plan", subject="受试者", attribute="计划采取措施甲",
        comparator="exists", source_clauses=[prefix, branch], semantic_proposition=prefix + branch,
        prospective_period={"kind": "source_defined", "source_excerpts": [prefix, branch]},
    ))
    before = good.model_dump(mode="json")
    before["proposed_rules"][0]["components"][0]["expression"]["predicate"]["prospective_period"]["source_excerpts"] = [full]
    text = json.dumps(before, ensure_ascii=False)
    codes = [rule.official_code for rule in good.proposed_rules]
    plan = plan_period_source_repair(text, source_input=source, rule_codes=codes)
    proposal = {"version": PERIOD_SOURCE_REPAIR_VERSION, "precondition_sha256": plan["precondition_sha256"],
        "fields": [{"path": target["path"], "source_excerpts": target["source_clauses"]}
                   for target in plan["targets"]]}
    return source, good, text, plan, proposal


def test_period_repair_requires_author_fields_and_freezes_every_other_field(tmp_path):
    from app.agents.protocol_deconstructor import _parse_semantic_candidate, protocol_output_response_format
    from app.domain.expression import evaluate_expression
    from app.domain.contracts.enums import TruthValue
    from tests.v2.test_contract_logic import evaluation_context
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    from app.evidence.artifacts import ArtifactStore
    from app.storage.config import resolve_data_paths

    _, good, before, plan, proposal = period_source_proposal()
    with pytest.raises(ValueError, match="全部逐字来源"):
        _parse_semantic_candidate(before)
    assembled, proof = apply_source_field_repair(before, json.dumps(proposal), plan=plan)
    assert json.loads(assembled) == good.model_dump(mode="json")
    assert not proof["adoption_checked"] and proof["added_paths"] == []
    assert proof["repaired_paths"] == [plan["targets"][0]["path"]]
    schema = protocol_output_response_format("semantic_period_sources")["json_schema"]["schema"]
    jsonschema.validate(proposal, schema)
    assert "semantic_proposition" in source_field_repair_prompt(plan)
    parsed = _parse_semantic_candidate(assembled)
    assert evaluate_expression(parsed.proposed_rules[0].components[0].expression,
                               evaluation_context()).truth == TruthValue.UNKNOWN
    paths = resolve_data_paths(tmp_path / "data")
    cache = _ProtocolSemanticBatchFileCache(paths, "synthetic-period-repair")
    refs = cache.store_source_field_input(raw_text=before, previous_text=before, plan=plan)
    saved = cache.store_source_field_result(previous_text=before, proposal_text=json.dumps(proposal),
        raw_text=json.dumps(proposal), assembled_text=assembled, plan=plan, input_refs=refs)
    store = ArtifactStore(paths)
    assert store.read(saved["previous_proposal_ref"]).decode() == before
    assert store.read(saved["assembled_proposal_ref"]).decode() == assembled
    assert json.loads(store.read(saved["field_repair_proof_ref"]))["repaired_paths"] == proof["repaired_paths"]


@pytest.mark.parametrize("fault", ["short", "foreign", "missing", "another_failure", "unsupported", "already_valid"])
def test_period_repair_does_not_complete_missing_scope_or_other_schema_errors(fault):
    source, good, before, _, _ = period_source_proposal()
    raw = json.loads(before)
    atom = raw["proposed_rules"][0]["components"][0]["expression"]["predicate"]
    if fault == "short":
        atom["prospective_period"]["source_excerpts"] = [atom["source_clauses"][0]]
    elif fault == "foreign":
        atom["prospective_period"]["source_excerpts"] = ["另一个要求的期间"]
    elif fault == "missing":
        atom["source_clauses"] = []
    elif fault == "another_failure":
        raw["proposed_rules"][1]["components"][0]["title"] = None
    elif fault == "unsupported":
        atom["prospective_period"]["period"] = "study_period"
    else:
        raw = good.model_dump(mode="json")
    assert plan_period_source_repair(json.dumps(raw), source_input=source,
        rule_codes=[rule.official_code for rule in good.proposed_rules]) is None


@pytest.mark.parametrize("fault", ["stale", "short", "foreign", "duplicate", "missing", "scope", "extra"])
def test_period_field_reply_cannot_change_scope_or_meaning(fault):
    _, _, before, plan, proposal = period_source_proposal()
    if fault == "stale":
        proposal["precondition_sha256"] = "f" * 64
    elif fault in {"short", "foreign"}:
        proposal["fields"][0]["source_excerpts"] = ["另一个期间"] if fault == "foreign" else proposal["fields"][0]["source_excerpts"][:1]
    elif fault == "duplicate":
        proposal["fields"].append(copy.deepcopy(proposal["fields"][0]))
    elif fault == "missing":
        proposal["fields"] = []
    elif fault == "scope":
        proposal["fields"][0]["path"][-1] = "semantic_proposition"
    else:
        proposal["proposed_rules"] = []
    with pytest.raises(ValueError):
        apply_source_field_repair(before, json.dumps(proposal), plan=plan)


def test_period_field_repair_runs_through_existing_batch_cache_and_preservation(monkeypatch, tmp_path):
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    from app.storage.config import resolve_data_paths

    source, good, before, _, _ = period_source_proposal()
    raw = json.loads(before)
    raw["proposed_rules"] = raw["proposed_rules"][:1]
    before = json.dumps(raw)
    codes = [rule.official_code for rule in good.proposed_rules]
    plan = plan_period_source_repair(before, source_input=source, rule_codes=codes[:1])
    proposal = {"version": PERIOD_SOURCE_REPAIR_VERSION, "precondition_sha256": plan["precondition_sha256"],
        "fields": [{"path": target["path"], "source_excerpts": target["source_clauses"]} for target in plan["targets"]]}
    second = good.model_copy(update={"proposed_rules": good.proposed_rules[1:]})
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="same", text=before),
        ProtocolAgentResponse(session_id="same", text=json.dumps(proposal)),
        ProtocolAgentResponse(session_id="same", text=second.model_dump_json()),
    ])
    transport.semantic_cache_identity = lambda **kwargs: {"model": "synthetic-frozen-model"}
    cache = _ProtocolSemanticBatchFileCache(resolve_data_paths(tmp_path / "data"), "synthetic-period-batches")
    transport._call_budget_store = cache
    monkeypatch.setattr("app.agents.protocol_deconstructor._plan_semantic_rule_batches",
                        lambda *args, **kwargs: [[code] for code in codes])
    response, error = _collect_initial_semantic_response(source, prompt_template="冻结原文",
        transport=transport, batch_size=1, batch_cache=cache)
    assert error is None
    assert transport.repair_output_kinds == ["semantic_period_sources", "semantic_candidate"]
    assert response.call_metadata["batches"][1]["source_field_repair"]["field_repair_proof_ref"]
    assert ProtocolSemanticDeconstructionCandidate.model_validate_json(response.text) == good


def test_period_author_decline_preserves_unaccounted_common_qualifier(monkeypatch, tmp_path):
    from app.agents.protocol_deconstructor import ProtocolAgentCallError
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    from app.storage.config import resolve_data_paths

    source, good, before, _, _ = period_source_proposal()
    raw = json.loads(before)
    raw["proposed_rules"] = raw["proposed_rules"][:1]
    atom = raw["proposed_rules"][0]["components"][0]["expression"]["predicate"]
    atom["source_clauses"] = atom["source_clauses"][1:]
    atom["semantic_proposition"] = atom["source_clauses"][0]
    before = json.dumps(raw)
    codes = [rule.official_code for rule in good.proposed_rules]
    plan = plan_period_source_repair(before, source_input=source, rule_codes=codes[:1])
    assert plan is not None  # Containment is admission for author review, not meaning approval.
    prompt = source_field_repair_prompt(plan)
    assert "共同期间、例外或适用人群" in prompt and "必须返回fields=[]" in prompt
    decline = {"version": plan["version"], "precondition_sha256": plan["precondition_sha256"], "fields": []}
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="same", text=before),
        ProtocolAgentResponse(session_id="same", text=json.dumps(decline)),
    ])
    cache = _ProtocolSemanticBatchFileCache(resolve_data_paths(tmp_path / "data"), "period-decline")
    transport._call_budget_store = cache
    monkeypatch.setattr("app.agents.protocol_deconstructor._plan_semantic_rule_batches",
                        lambda *args, **kwargs: [[code] for code in codes])
    with pytest.raises(ProtocolAgentCallError) as error:
        _collect_initial_semantic_response(source, prompt_template="冻结原文", transport=transport,
            batch_size=1, batch_cache=cache)
    assert error.value.error_code == "SOURCE_FIELD_REPAIR_DECLINED"
    assert transport.repair_output_kinds == ["semantic_period_sources"]
    assert not list(cache._root.glob("*.json"))


def missing_input_source_proposal():
    source, draft, _ = _fixture()
    text = "取全部指标甲记录的均值，指标甲≥18分"
    source.source_materials[0].text = text
    source.parent_rule_catalog = _catalog(source.parent_rule_catalog.catalog_kind, [
        item.model_copy(update={"label": text}) if index == 0 else item
        for index, item in enumerate(source.parent_rule_catalog.items)])
    good = _semantic_candidate(source, draft)
    target = good.proposed_rules[0].model_dump(mode="json")
    component = target["components"][0]
    component["source_excerpts"] = [text]
    atom = component["expression"]["predicate"]
    atom.update(attribute="指标甲", unit="分", source_clause=text, source_clauses=[])
    atom["observation_policy"]["source_excerpts"] = [text]
    atom["source_computation"] = {
        "operator": "mean", "operator_ref": {"statement_index": 0, "quote": "均值"},
        "missing_policy": "not_specified", "input_selection": {
            "mode": "all", "source": {"statement_index": 0, "quote": "全部指标甲记录"}},
    }
    before = {"candidate_id": good.candidate_id, "replacement_rules": [target],
              "replacement_unresolved_items": [], "replacement_structural_warnings": []}
    from app.agents.protocol_deconstructor import semantic_candidate_from_draft
    before["candidate_id"] = semantic_candidate_from_draft(draft).candidate_id
    previous_text = json.dumps(before, ensure_ascii=False)
    plan = plan_source_field_repair(previous_text, candidate_id=before["candidate_id"],
                                   official_code="IN-01")
    proposal = {"version": SOURCE_FIELD_REPAIR_VERSION,
        "precondition_sha256": plan["precondition_sha256"], "fields": [{
            "path": plan["targets"][0]["path"],
            "input_refs": [{"statement_index": 0, "quote": "全部指标甲记录"}]}]}
    return source, draft, previous_text, plan, proposal


def test_source_field_repair_preserves_raw_siblings_and_unresolved_state():
    _, _, before, plan, proposal = missing_input_source_proposal()
    original = json.loads(before)
    assembled, proof = apply_source_field_repair(before, json.dumps(proposal), plan=plan)
    raw = json.loads(assembled)
    atom = raw["replacement_rules"][0]["components"][0]["expression"]["predicate"]
    assert atom["source_computation"].pop("input_refs") == proposal["fields"][0]["input_refs"]
    assert raw == original
    parsed = ProtocolSemanticRuleRepair.model_validate_json(assembled)
    calculation = parsed.replacement_rules[0].components[0].expression.predicate.source_computation
    assert calculation.input_selection.mode == "all"
    assert proof["adoption_checked"] is False
    assert proof["previous_output_sha256"] == plan["precondition_sha256"]


@pytest.mark.parametrize("case", ["stale", "foreign", "index", "duplicate", "missing", "scope", "extra", "changed_body"])
def test_source_field_repair_rejects_changed_scope_or_source(case):
    _, _, before, plan, proposal = missing_input_source_proposal()
    if case == "stale":
        proposal["precondition_sha256"] = "f" * 64
    elif case == "foreign":
        proposal["fields"][0]["input_refs"][0]["quote"] = "另一条款"
    elif case == "index":
        proposal["fields"][0]["input_refs"][0]["statement_index"] = 2
    elif case == "duplicate":
        proposal["fields"].append(copy.deepcopy(proposal["fields"][0]))
    elif case == "missing":
        proposal["fields"] = []
    elif case == "scope":
        proposal["fields"][0]["path"][-1] = "operator"
    elif case == "extra":
        proposal["replacement_rules"] = []
    else:
        before += " "
    with pytest.raises(ValueError):
        apply_source_field_repair(before, json.dumps(proposal), plan=plan)


@pytest.mark.parametrize("existing", [[], None, [{"statement_index": 0, "quote": "错误"}]])
def test_source_field_repair_does_not_replace_explicit_fields(existing):
    _, _, before, plan, _ = missing_input_source_proposal()
    raw = json.loads(before)
    raw["replacement_rules"][0]["components"][0]["expression"]["predicate"]["source_computation"]["input_refs"] = existing
    assert plan_source_field_repair(json.dumps(raw), candidate_id=raw["candidate_id"],
                                   official_code="IN-01") is None


def disconnected_input_source_proposal():
    source, draft, text, _, _ = missing_input_source_proposal()
    raw = json.loads(text)
    calculation = raw["replacement_rules"][0]["components"][0]["expression"]["predicate"]["source_computation"]
    calculation["input_refs"] = [{"statement_index": 0, "quote": "指标甲记录"}]
    text = json.dumps(raw, ensure_ascii=False)
    plan = plan_source_field_repair(text, candidate_id=raw["candidate_id"], official_code="IN-01", include_disconnected=True)
    proposal = {"version": SOURCE_FIELD_REPAIR_VERSION,
        "precondition_sha256": plan["precondition_sha256"], "fields": [{
            "path": plan["targets"][0]["path"],
            "input_refs": [{"statement_index": 0, "quote": "全部指标甲记录"}]}]}
    return source, draft, text, plan, proposal


def test_disconnected_literal_references_repair_without_rewriting_selection_or_siblings(tmp_path):
    source, draft, text, plan, proposal = disconnected_input_source_proposal()
    assembled, proof = apply_source_field_repair(text, json.dumps(proposal), plan=plan)
    raw = json.loads(assembled)
    calculation = raw["replacement_rules"][0]["components"][0]["expression"]["predicate"]["source_computation"]
    calculation["input_refs"] = [{"statement_index": 0, "quote": "指标甲记录"}]
    assert raw == json.loads(text)
    assert proof["added_paths"] == [] and len(proof["repaired_paths"]) == 1
    assert proof["adoption_checked"] is False
    from app.agents.protocol_deconstructor import revise_protocol_draft_from_feedback
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="author", text=text),
        ProtocolAgentResponse(session_id="author", text=json.dumps(proposal)),
    ])
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    from app.storage.config import resolve_data_paths
    transport._call_budget_store = _ProtocolSemanticBatchFileCache(resolve_data_paths(tmp_path / "data"), "synthetic-binding")
    revised = revise_protocol_draft_from_feedback(source, draft, target_rule_code="IN-01",
        feedback_note="仅修复已声明引用的连接。", transport=transport)
    assert transport.repair_output_kinds == []
    assert revised.proposed_rules[1] == draft.proposed_rules[1]
    assert revised.proposed_rules[0].components[0].expression.predicate.source_computation.input_selection.mode == "all"


def test_declared_reference_assembly_is_append_only_and_saved_with_original_response(tmp_path):
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    from app.evidence.artifacts import ArtifactStore
    from app.storage.config import resolve_data_paths
    _, _, before, _, _ = disconnected_input_source_proposal()
    raw = json.loads(before)
    assembled, proof = assemble_declared_input_references(before,
        candidate_id=raw["candidate_id"], official_code="IN-01")
    result = json.loads(assembled)
    refs = result["replacement_rules"][0]["components"][0]["expression"]["predicate"]["source_computation"]["input_refs"]
    assert refs == [{"statement_index": 0, "quote": "指标甲记录"},
                    {"statement_index": 0, "quote": "全部指标甲记录"}]
    refs.pop()
    assert result == raw
    assert proof["model_calls"] == 0 and not proof["adoption_checked"]
    paths = resolve_data_paths(tmp_path / "data")
    store = ArtifactStore(paths)
    cache = _ProtocolSemanticBatchFileCache(paths, "synthetic-job")
    saved = cache.store_source_reference_assembly(previous_text=before, raw_text=before,
        assembled_text=assembled, proof=proof)
    assert store.read(saved["previous_raw_response_ref"]).decode() == before
    assert store.read(saved["assembled_proposal_ref"]).decode() == assembled
    assert json.loads(store.read(saved["reference_assembly_proof_ref"]))["changes"] == proof["changes"]
    assert assemble_declared_input_references(assembled,
        candidate_id=raw["candidate_id"], official_code="IN-01") == (assembled, None)


def unresolved_source_pair_proposal():
    source, draft, before, _, _ = missing_input_source_proposal()
    raw = json.loads(before)
    quote = "核查本节点前一个月的指标甲，每期间用量不得超过18单位。"
    source.source_materials[0].text = quote
    source.parent_rule_catalog = _catalog(source.parent_rule_catalog.catalog_kind, [
        item.model_copy(update={"label": quote}) if index == 0 else item
        for index, item in enumerate(source.parent_rule_catalog.items)])
    component = raw["replacement_rules"][0]["components"][0]
    component["source_excerpts"] = [quote]
    atom = component["expression"]["predicate"]
    atom.update(source_clause=quote, source_clauses=[], source_computation=None,
                comparator="lte", value=18, unit="单位")
    atom["observation_policy"].update(mode="unresolved", selection=None,
        source_span_ids=component["source_span_ids"],
        source_excerpts=["本节点前一个月", "每期间用量不得超过18单位"])
    return source, draft, json.dumps(raw, ensure_ascii=False)


def test_unresolved_source_pair_only_packages_authored_quote_and_preserves_unknown(tmp_path):
    from app.domain.expression import evaluate_expression
    from app.domain.contracts.enums import TruthValue
    from tests.v2.test_contract_logic import evaluation_context
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    from app.evidence.artifacts import ArtifactStore
    from app.storage.config import resolve_data_paths

    _, _, before = unresolved_source_pair_proposal()
    original = json.loads(before)
    assembled, proof = assemble_unresolved_observation_sources(before,
        candidate_id=original["candidate_id"], official_code="IN-01")
    assert proof is not None and proof["model_calls"] == 0 and not proof["adoption_checked"]
    result = json.loads(assembled)
    atom = result["replacement_rules"][0]["components"][0]["expression"]["predicate"]
    atom["observation_policy"]["source_excerpts"] = proof["changes"][0]["original_refs"]
    assert result == original
    parsed = ProtocolSemanticRuleRepair.model_validate_json(assembled)
    expression = parsed.replacement_rules[0].components[0].expression
    assert expression.predicate.value == 18
    assert expression.predicate.observation_policy.mode == "unresolved"
    assert evaluate_expression(expression, evaluation_context()).truth == TruthValue.UNKNOWN
    paths = resolve_data_paths(tmp_path / "data")
    cache = _ProtocolSemanticBatchFileCache(paths, "synthetic-source-pair")
    saved = cache.store_source_reference_assembly(previous_text=before, raw_text=before,
        assembled_text=assembled, proof=proof)
    store = ArtifactStore(paths)
    assert store.read(saved["previous_raw_response_ref"]).decode() == before
    assert store.read(saved["assembled_proposal_ref"]).decode() == assembled
    assert assemble_unresolved_observation_sources(assembled,
        candidate_id=original["candidate_id"], official_code="IN-01") == (assembled, None)
    changed = dict(proof, model_calls=1)
    with pytest.raises(ValueError):
        cache.store_source_reference_assembly(previous_text=before, raw_text=before,
            assembled_text=assembled, proof=changed)


@pytest.mark.parametrize("fault", ["foreign_id", "foreign_quote", "known_policy", "selection",
    "duplicate", "non_string", "component", "rule", "two_sources", "outside_clause", "nan"])
def test_unresolved_source_pair_does_not_guess_or_fix_other_errors(fault):
    _, _, before = unresolved_source_pair_proposal()
    raw = json.loads(before)
    component = raw["replacement_rules"][0]["components"][0]
    atom = component["expression"]["predicate"]
    policy = atom["observation_policy"]
    if fault == "foreign_id":
        policy["source_span_ids"] = ["another-source"]
    elif fault == "foreign_quote":
        policy["source_excerpts"][0] = "另一条件"
    elif fault == "known_policy":
        policy["mode"] = "specified"
    elif fault == "selection":
        policy["selection"] = "latest"
    elif fault == "duplicate":
        policy["source_excerpts"] *= 2
    elif fault == "non_string":
        policy["source_excerpts"][0] = {}
    elif fault == "component":
        raw["replacement_rules"][0]["components"] = [None]
    elif fault == "rule":
        raw["replacement_rules"] = [None]
    elif fault == "two_sources":
        component["source_span_ids"].append("another-source")
    elif fault == "outside_clause":
        atom["source_clause"] = "仅有其他条件"
    else:
        atom["value"] = float("nan")
    text = json.dumps(raw, ensure_ascii=False)
    assert assemble_unresolved_observation_sources(text,
        candidate_id=raw["candidate_id"], official_code="IN-01") == (text, None)


def test_unresolved_pair_persistence_failure_is_not_another_author_call():
    from app.agents.protocol_deconstructor import revise_protocol_draft_from_feedback, ProtocolAgentCallError
    source, draft, before = unresolved_source_pair_proposal()

    class FailingStore:
        def store_source_reference_assembly(self, **kwargs):
            raise OSError("synthetic disk failure")

    transport = FakeTransport([ProtocolAgentResponse(session_id="author", text=before)])
    transport._call_budget_store = FailingStore()
    with pytest.raises(ProtocolAgentCallError) as caught:
        revise_protocol_draft_from_feedback(source, draft, target_rule_code="IN-01",
            feedback_note="仅核对当前要求。", transport=transport)
    assert caught.value.error_code == "SOURCE_REFERENCE_ASSEMBLY_PERSISTENCE_FAILED"
    assert len(transport.start_prompts) == 1 and not transport.repair_prompts


@pytest.mark.parametrize("pair", [False, True])
def test_host_reference_packaging_without_persistent_store_does_not_accept_an_answer(pair):
    from app.agents.protocol_deconstructor import revise_protocol_draft_from_feedback, ProtocolAgentCallError
    if pair:
        source, draft, before = unresolved_source_pair_proposal()
    else:
        source, draft, before, _, _ = disconnected_input_source_proposal()
    # The missing immutable proof prevents host packaging. A subsequent author
    # response may be tried within the existing budget, but is not fabricated.
    transport = FakeTransport([ProtocolAgentResponse(session_id="author", text=before)] * 2)
    with pytest.raises(ProtocolAgentCallError):
        revise_protocol_draft_from_feedback(source, draft, target_rule_code="IN-01",
            feedback_note="核查引用连接。", transport=transport)
    assert len(transport.start_prompts) == len(transport.repair_prompts) == 1


@pytest.mark.parametrize("case", ["already_valid", "invented", "count", "policy", "selection"])
def test_disconnected_references_do_not_admit_other_calculation_failures(case):
    _, _, text, _, _ = disconnected_input_source_proposal()
    raw = json.loads(text)
    calculation = raw["replacement_rules"][0]["components"][0]["expression"]["predicate"]["source_computation"]
    if case == "already_valid":
        calculation["input_refs"][0]["quote"] = "全部指标甲记录"
    elif case == "invented":
        calculation["input_refs"][0]["quote"] = "未出现的项目"
    elif case == "count":
        calculation["declared_input_count"] = {"value": 4, "number_text": "三",
            "source": {"statement_index": 0, "quote": "指标甲记录"}}
    elif case == "policy":
        calculation["missing_policy"] = "exclude"
    else:
        calculation["input_selection"]["source"]["quote"] = "全部指标乙记录"
    assert plan_source_field_repair(json.dumps(raw), candidate_id=raw["candidate_id"],
                                   official_code="IN-01", include_disconnected=True) is None


@pytest.mark.parametrize("case", ["drop_original", "changed_plan", "legacy_replace"])
def test_disconnected_reference_patch_preserves_existing_scope_and_version(case):
    _, _, text, plan, proposal = disconnected_input_source_proposal()
    if case == "drop_original":
        proposal["fields"][0]["input_refs"][0]["quote"] = "全部"
    elif case == "changed_plan":
        plan["targets"][0]["source_clauses"] = ["全部指标甲记录及另一个指标"]
    else:
        plan["version"] = proposal["version"] = "protocol-source-fields/v2"
    with pytest.raises(ValueError):
        apply_source_field_repair(text, json.dumps(proposal), plan=plan)


def test_legacy_missing_reference_repair_keeps_its_proof_shape():
    _, _, text, plan, proposal = missing_input_source_proposal()
    plan["version"] = proposal["version"] = "protocol-source-fields/v2"
    _, proof = apply_source_field_repair(text, json.dumps(proposal), plan=plan)
    assert proof["version"] == "protocol-source-fields/v2" and "repaired_paths" not in proof


def test_author_decline_is_not_reported_as_invalid_structure_or_patient_missing_evidence():
    from app.agents.protocol_deconstructor import revise_protocol_draft_from_feedback, ProtocolAgentCallError
    source, draft, before, plan, proposal = missing_input_source_proposal()
    proposal["fields"] = []
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="author", text=before),
        ProtocolAgentResponse(session_id="author", text=json.dumps(proposal)),
    ])
    with pytest.raises(ProtocolAgentCallError) as caught:
        revise_protocol_draft_from_feedback(source, draft, target_rule_code="IN-01",
            feedback_note="只补来源引用。", transport=transport)
    assert caught.value.error_code == "SOURCE_FIELD_REPAIR_DECLINED"
    assert len(transport.start_prompts) == len(transport.repair_prompts) == 1


def test_empty_recovery_history_fails_as_identity_error_before_another_call():
    from app.agents.protocol_deconstructor import ProtocolAgentCallError
    _, _, before, plan, _ = missing_input_source_proposal()
    transport = FakeTransport([])
    transport.history = lambda session: []
    with pytest.raises(ProtocolAgentCallError) as caught:
        recover_source_fields(previous_response=ProtocolAgentResponse(session_id="author", text=before),
            plan=plan, transport=transport)
    assert caught.value.error_code == "MODEL_IDENTITY_MISMATCH"
    assert not transport.repair_prompts


def test_preimage_save_failure_does_not_invent_a_repair_response():
    from app.agents.protocol_deconstructor import ProtocolAgentCallError
    _, _, before, plan, _ = missing_input_source_proposal()

    class FailingStore:
        def store_source_field_input(self, **kwargs):
            raise OSError("synthetic persistence failure")

        def store_source_field_result(self, **kwargs):
            raise AssertionError("No response exists")

    transport = FakeTransport([])
    transport._call_budget_store = FailingStore()
    with pytest.raises(ProtocolAgentCallError) as caught:
        recover_source_fields(previous_response=ProtocolAgentResponse(session_id="author", text=before),
            plan=plan, transport=transport)
    assert caught.value.error_code == "SOURCE_FIELD_REPAIR_PERSISTENCE_FAILED"
    assert "field_repair_response_sha256" not in caught.value.error_metadata
    assert not transport.repair_prompts


@pytest.mark.parametrize("index", [0, 1])
def test_reference_assembly_preserves_windows_counts_and_unknown_selection(index):
    from app.domain.contracts.source_computation import SourceComputation, validate_computation_quotes
    _, _, before, _, _ = disconnected_input_source_proposal()
    raw = json.loads(before)
    atom = raw["replacement_rules"][0]["components"][0]["expression"]["predicate"]
    source = "先期最后两次和当日一次（共三次）记录的均值，审核值至少18。"
    atom["source_clause"], atom["source_clauses"] = None, (["独立的背景句。"] if index else []) + [source]
    calculation = atom["source_computation"] = {
        "operator": "mean", "operator_ref": {"statement_index": index, "quote": "均值"},
        "input_refs": [{"statement_index": index, "quote": "先期最后两次"},
                       {"statement_index": index, "quote": "当日一次"}],
        "missing_policy": "not_specified",
        "declared_input_count": {"value": 3, "number_text": "三",
            "source": {"statement_index": index, "quote": "共三次"}},
        "input_selection": {"mode": "unresolved",
            "source": {"statement_index": index, "quote": "先期最后两次和当日一次（共三次）"},
            "window_refs": [{"statement_index": index, "quote": "先期最后两次"}]}}
    text = json.dumps(raw)
    assembled, proof = assemble_declared_input_references(text,
        candidate_id=raw["candidate_id"], official_code="IN-01")
    repaired = json.loads(assembled)["replacement_rules"][0]["components"][0]["expression"]["predicate"]["source_computation"]
    validate_computation_quotes(SourceComputation.model_validate(repaired), atom["source_clauses"])
    assert repaired["input_refs"][:2] == calculation["input_refs"]
    assert repaired["input_selection"] == calculation["input_selection"]
    assert repaired["declared_input_count"] == calculation["declared_input_count"]
    assert proof["model_calls"] == 0 and not proof["adoption_checked"]


@pytest.mark.parametrize("split", [False, True])
def test_source_field_repair_quote_presence_does_not_bypass_full_input_scope(split):
    _, _, before, plan, proposal = missing_input_source_proposal()
    prompt = source_field_repair_prompt(plan)
    assert "source、window_refs及非空ordering_ref" in prompt
    assert "declared_input_count.source" in prompt
    proposal["fields"][0]["input_refs"] = ([
        {"statement_index": 0, "quote": "全部"},
        {"statement_index": 0, "quote": "指标甲记录"},
    ] if split else [{"statement_index": 0, "quote": "指标甲记录"}])
    assembled, _ = apply_source_field_repair(before, json.dumps(proposal), plan=plan)
    # A field proposal can be a faithful quote yet still fail the unchanged
    # semantic constructor. The repair proof is never adoption authority.
    with pytest.raises(ValueError, match="选取方式、日期角色和窗口"):
        ProtocolSemanticRuleRepair.model_validate_json(assembled)

    from app.agents.protocol_deconstructor import revise_protocol_draft_from_feedback, ProtocolAgentCallError
    source, draft, _, _, _ = missing_input_source_proposal()
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="same-author", text=before),
        ProtocolAgentResponse(session_id="same-author", text=json.dumps(proposal)),
    ])
    with pytest.raises(ProtocolAgentCallError) as caught:
        revise_protocol_draft_from_feedback(source, draft, target_rule_code="IN-01",
            feedback_note="合成输入范围合同", transport=transport)
    metadata = caught.value.error_metadata
    assert metadata["source_field_repair"]["adoption_checked"] is False
    assert metadata["local_repair_trigger"]["assembled_response_sha256"] == metadata["source_field_repair"]["assembled_output_sha256"]
    assert metadata["source_field_repair"]["previous_output_sha256"] == plan["precondition_sha256"]
    assert len(transport.start_prompts) == len(transport.repair_prompts) == 1


def test_feedback_source_field_repair_uses_one_existing_recovery_and_consumes_result():
    from app.agents.protocol_deconstructor import revise_protocol_draft_from_feedback
    from app.domain.expression import EvaluationContext, evaluate_expression
    from app.domain.contracts.enums import TruthValue

    source, draft, before, plan, proposal = missing_input_source_proposal()
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="original-author", text=before),
        ProtocolAgentResponse(session_id="original-author", text=json.dumps(proposal)),
    ])
    revised = revise_protocol_draft_from_feedback(source, draft, target_rule_code="IN-01",
        feedback_note="合成合同：核对计算输入来源，不采用任何患者结果。", transport=transport)
    assert transport.repair_output_kinds == ["semantic_source_fields"]
    assert len(transport.start_prompts) == len(transport.repair_prompts) == 1
    prompt_payload = json.loads(transport.repair_prompts[0][1].split("\n", 1)[1])
    assert set(prompt_payload) == {"frozen_plan", "output_schema"}
    assert set(prompt_payload["output_schema"]["properties"]) == {"version", "precondition_sha256", "fields"}
    assert "identity_decision" not in transport.repair_prompts[0][1]
    original_other = draft.proposed_rules[1].model_dump(mode="json")
    assert revised.proposed_rules[1].model_dump(mode="json") == original_other
    expression = revised.proposed_rules[0].components[0].expression
    assert expression.predicate.source_computation.input_refs[0].quote == "全部指标甲记录"
    assert evaluate_expression(expression, EvaluationContext(project_id="project-1",
        subject_id="synthetic-subject", review_episode_id="synthetic-episode",
        evidence_snapshot_id="synthetic-snapshot")).truth == TruthValue.UNKNOWN


def test_feedback_source_field_repair_invalid_answer_does_not_expand_to_third_call():
    from app.agents.protocol_deconstructor import revise_protocol_draft_from_feedback, ProtocolAgentCallError

    source, draft, before, plan, proposal = missing_input_source_proposal()
    proposal["fields"][0]["path"][-1] = "operator"
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="same-author", text=before),
        ProtocolAgentResponse(session_id="same-author", text=json.dumps(proposal)),
    ])
    with pytest.raises(ProtocolAgentCallError) as caught:
        revise_protocol_draft_from_feedback(source, draft, target_rule_code="IN-01",
            feedback_note="仅补有源输入引用", transport=transport)
    assert caught.value.error_code == "SOURCE_FIELD_REPAIR_INVALID"
    assert caught.value.error_metadata["local_repair_trigger"]["phase"] == "parse"
    assert len(transport.start_prompts) == len(transport.repair_prompts) == 1


def test_source_field_recovery_freezes_preimage_before_compacting_and_saves_result(tmp_path):
    from app.agents.protocol_deconstructor import revise_protocol_draft_from_feedback
    from app.evidence.artifacts import ArtifactStore
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    from app.storage.config import resolve_data_paths

    source, draft, before, plan, proposal = missing_input_source_proposal()
    paths = resolve_data_paths(str(tmp_path / "data"))
    cache = _ProtocolSemanticBatchFileCache(paths, "synthetic-feedback")
    artifacts = ArtifactStore(paths)

    class Bounded(FakeTransport):
        supports_bounded_batch_context = True
        _call_budget_store = cache
        def compact_session_history(self, *, session_id, context):
            assert session_id == "same-budget"
            refs = cache.store_source_field_input(raw_text=before, previous_text=before, plan=plan)
            assert artifacts.read(refs["previous_proposal_ref"]).decode() == before
            assert json.loads(artifacts.read(refs["field_plan_ref"])) == plan
            assert json.loads(context) == plan
            self.compacted = context

    transport = Bounded([ProtocolAgentResponse(session_id="same-budget", text=before),
        ProtocolAgentResponse(session_id="same-budget", text=json.dumps(proposal))])
    revised = revise_protocol_draft_from_feedback(source, draft, target_rule_code="IN-01",
        feedback_note="合成来源补字段", transport=transport)
    assert transport.compacted and revised.proposed_rules[0].components
    refs = cache.store_source_field_input(raw_text=before, previous_text=before, plan=plan)
    assembled, _ = apply_source_field_repair(before, json.dumps(proposal), plan=plan)
    saved = cache.store_source_field_result(previous_text=before, proposal_text=json.dumps(proposal),
        raw_text=json.dumps(proposal), assembled_text=assembled, plan=plan, input_refs=refs)
    proof = json.loads(artifacts.read(saved["field_repair_proof_ref"]))
    assert proof["adoption_checked"] is False
    assert artifacts.read(proof["assembled_proposal_ref"]).decode() == assembled
    assert artifacts.read(proof["previous_raw_response_ref"]).decode() == before
    with pytest.raises(ValueError, match="原答身份"):
        cache.store_source_field_input(raw_text=before, previous_text=before + " ", plan=plan)
    with pytest.raises(ValueError, match="保存内容"):
        cache.store_source_field_result(previous_text=before, proposal_text=json.dumps(proposal),
            raw_text=json.dumps(proposal), assembled_text=assembled + " ", plan=plan, input_refs=refs)


@pytest.mark.parametrize("used", [0, 1])
def test_source_field_recovery_does_not_create_or_reset_budget(used):
    from app.agents.protocol_deconstructor import ProtocolAgentCallError

    _, _, before, plan, proposal = missing_input_source_proposal()
    budget = LogicalCallBudget("existing-source-field-stage", max_requests=1, max_output_tokens=100)
    if used:
        budget.reserve(request_sha256="previous-call", max_tokens=100)

    class Budgeted(FakeTransport):
        def continue_session(self, **kwargs):
            try:
                budget.reserve(request_sha256="actual-field-call", max_tokens=100)
            except RuntimeError as exc:
                raise ProtocolAgentCallError(kwargs["session_id"], str(exc),
                    error_code="LOGICAL_BUDGET_EXHAUSTED") from exc
            return super().continue_session(**kwargs)

    transport = Budgeted([ProtocolAgentResponse(session_id="original", text=json.dumps(proposal))])
    previous = ProtocolAgentResponse(session_id="original", text=before)
    if used:
        with pytest.raises(ProtocolAgentCallError) as caught:
            recover_source_fields(previous_response=previous, plan=plan, transport=transport)
        assert caught.value.error_code == "LOGICAL_BUDGET_EXHAUSTED"
        assert transport.repair_prompts == []
    else:
        response = recover_source_fields(previous_response=previous, plan=plan, transport=transport)
        assert response.call_metadata["source_field_repair"]["adoption_checked"] is False
        assert response.original_text == json.dumps(proposal)
        assert len(transport.repair_prompts) == 1
    assert budget.snapshot()["requests_used"] == 1


def test_source_field_recovery_rejects_changed_history_without_call():
    from app.agents.protocol_deconstructor import ProtocolAgentCallError

    _, _, before, plan, proposal = missing_input_source_proposal()
    transport = FakeTransport([])
    transport.history = lambda session_id: [{"role": "assistant", "content": "另一原答"}]
    with pytest.raises(ProtocolAgentCallError) as caught:
        recover_source_fields(previous_response=ProtocolAgentResponse(session_id="original", text=before),
                              plan=plan, transport=transport)
    assert caught.value.error_code == "MODEL_IDENTITY_MISMATCH"
    assert transport.repair_prompts == []


@pytest.mark.parametrize("failure", [None, "foreign_source", "bad_json", "wrong_session"])
def test_source_field_answer_is_frozen_before_validation_with_actual_budget(tmp_path, failure):
    from app.agents.protocol_deconstructor import ProtocolAgentCallError
    from app.evidence.artifacts import ArtifactStore
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    from app.storage.config import resolve_data_paths

    _, _, before, plan, proposal = missing_input_source_proposal()
    if failure == "foreign_source":
        proposal["fields"][0]["input_refs"][0]["quote"] = "另一要求的输入"
    body = "不是合法JSON" if failure == "bad_json" else json.dumps(proposal, ensure_ascii=False)
    raw = "```json\n" + body + "\n```"
    actual_budget = LogicalCallBudget("actual-canonical-source-scope", max_requests=3, max_output_tokens=300)
    actual_budget.reserve(request_sha256="actual-field-request", max_tokens=100)
    metadata = {"logical_call_budget": actual_budget.snapshot(), "reported_model": "fixture-author"}
    paths = resolve_data_paths(str(tmp_path / "data"))
    cache = _ProtocolSemanticBatchFileCache(paths, "synthetic-source-answer")
    store = ArtifactStore(paths)

    class Saved(FakeTransport):
        _call_budget_store = cache

    transport = Saved([ProtocolAgentResponse(
        session_id="different" if failure == "wrong_session" else "original",
        text=body, raw_text=raw, call_metadata=metadata,
    )])
    previous = ProtocolAgentResponse(session_id="original", text=before)
    if failure:
        with pytest.raises(ProtocolAgentCallError) as caught:
            recover_source_fields(previous_response=previous, plan=plan, transport=transport)
        assert caught.value.error_code == "SOURCE_FIELD_REPAIR_INVALID"
        result_meta = caught.value.error_metadata
        refs = result_meta["source_field_response"]
        assert result_meta["logical_call_budget"] == actual_budget.snapshot()
        assert result_meta["reported_model"] == "fixture-author"
        assert "assembled_proposal_ref" not in refs and "field_repair_proof_ref" not in refs
    else:
        response = recover_source_fields(previous_response=previous, plan=plan, transport=transport)
        refs = response.call_metadata["source_field_repair"]
        assert json.loads(store.read(refs["field_repair_proof_ref"]))["adoption_checked"] is False
    receipt = json.loads(store.read(refs["field_response_receipt_ref"]))
    assert receipt["call_metadata"]["logical_call_budget"] == actual_budget.snapshot()
    assert receipt["requested_session_id"] == "original"
    assert receipt["response_session_id"] == ("different" if failure == "wrong_session" else "original")
    assert receipt["validation_completed"] is False and receipt["adoption_checked"] is False
    assert store.read(refs["field_raw_response_ref"]).decode() == raw
    assert store.read(refs["field_proposal_ref"]).decode() == body
    assert store.read(receipt["previous_proposal_ref"]).decode() == before
    assert json.loads(store.read(receipt["field_plan_ref"])) == plan
    assert len(transport.repair_prompts) == 1 and actual_budget.snapshot()["requests_used"] == 1


def test_failed_source_field_response_storage_does_not_trigger_another_call(tmp_path, monkeypatch):
    from app.agents.protocol_deconstructor import ProtocolAgentCallError
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    from app.storage.config import resolve_data_paths

    _, _, before, plan, proposal = missing_input_source_proposal()
    cache = _ProtocolSemanticBatchFileCache(resolve_data_paths(str(tmp_path / "data")), "synthetic-storage-failure")
    def unavailable(**kwargs):
        raise OSError("synthetic storage failure")
    monkeypatch.setattr(cache, "store_source_field_response", unavailable)
    class Saved(FakeTransport):
        _call_budget_store = cache
    metadata = {"logical_call_budget": {"logical_task_id": "actual-scope", "requests_used": 3}}
    transport = Saved([ProtocolAgentResponse(session_id="original", text=json.dumps(proposal), call_metadata=metadata)])
    with pytest.raises(ProtocolAgentCallError) as caught:
        recover_source_fields(previous_response=ProtocolAgentResponse(session_id="original", text=before),
                              plan=plan, transport=transport)
    assert caught.value.error_code == "SOURCE_FIELD_REPAIR_PERSISTENCE_FAILED"
    assert caught.value.error_metadata["logical_call_budget"] == metadata["logical_call_budget"]
    assert caught.value.error_metadata["source_field_response"] == {}
    assert len(transport.repair_prompts) == 1


@pytest.mark.parametrize("field,kind,quantifier,value", [
    ("duration_basis", "calendar_period", "every", "calendar_span"),
    ("calendar_week_start", "any_consecutive", "any", "monday"),
    ("anchor_type", "calendar_period", "every", "screening_date"),
    ("boundary_periods", "unanchored_lookback", "single", "full_only"),
])
def test_repair_schema_exposes_existing_cross_field_rejections(field, kind, quantifier, value):
    schema = json.loads(_compact_schema(repair=True))
    scope = {"kind": kind, "quantifier": quantifier, "source_excerpts": ["冻结原文"], field: value}
    scope_schema = {"$defs": schema["$defs"], **schema["$defs"]["OccurrenceScope"]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(scope, scope_schema)
    with pytest.raises(ValueError):
        OccurrenceScope.model_validate(scope)
    scope[field] = None
    jsonschema.validate(scope, scope_schema)
    OccurrenceScope.model_validate(scope)


def test_repair_schema_does_not_change_initial_contract():
    initial = _compact_schema()
    repair = json.loads(_compact_schema(repair=True))
    assert _compact_schema() == initial
    assert "allOf" not in json.loads(initial)["$defs"]["OccurrenceScope"]
    assert repair["$defs"]["OccurrenceScope"]["allOf"]


def failed_with_valid_siblings(good):
    before = good.model_dump(mode="json")
    bad = copy.deepcopy(before["proposed_rules"][0]["components"][0])
    bad["title"] = ""
    before["proposed_rules"][0]["components"].append(bad)
    return before


def repaired_candidate(before):
    payload = copy.deepcopy(before)
    payload["proposed_rules"][0]["components"][-1]["title"] = "修复目标要求"
    return ProtocolSemanticDeconstructionCandidate.model_validate(payload)


def test_valid_siblings_preserved_with_default_normalization_and_issue_records():
    _, good = candidate()
    before = failed_with_valid_siblings(good)
    issue = {"code": "SOURCE_UNRESOLVED", "affected_scope": ["IN-01"], "source_refs": ["source-1"]}
    before["unresolved_items"] = [issue]
    repaired = repaired_candidate(before)
    proof = verify_repair_preserves_valid_parts(json.dumps(before), repaired)
    assert proof["preserved_components"] == sum(len(rule.components) for rule in good.proposed_rules)
    assert len(proof["previous_output_sha256"]) == 64
    no_issue = repaired.model_copy(update={"unresolved_items": []})
    with pytest.raises(ValueError, match="未决记录"):
        verify_repair_preserves_valid_parts(json.dumps(before), no_issue)


@pytest.mark.parametrize("change", ["title", "source", "delete", "duplicate", "identity", "reorder", "extra", "invalid_source", "missing_components"])
def test_repair_rejects_unrelated_changes(change):
    _, good = candidate()
    before = failed_with_valid_siblings(good)
    repaired = repaired_candidate(before)
    component = repaired.proposed_rules[0].components[0]
    if change == "title":
        component.title = "无关改写"
    elif change == "source":
        component.source_excerpts = ["另一个来源"]
    elif change == "delete":
        repaired.proposed_rules[0].components = []
    elif change == "duplicate":
        before["proposed_rules"][0]["components"].append(copy.deepcopy(before["proposed_rules"][0]["components"][0]))
    elif change == "reorder":
        repaired.proposed_rules[0].components.reverse()
    elif change == "extra":
        repaired.proposed_rules[0].components.append(component.model_copy(deep=True))
    elif change == "invalid_source":
        repaired.proposed_rules[0].components[-1].source_excerpts = ["不能更换待修来源"]
    elif change == "missing_components":
        before["proposed_rules"][0].pop("components")
    else:
        repaired.candidate_id = "another-candidate"
    with pytest.raises(ValueError):
        verify_repair_preserves_valid_parts(json.dumps(before), repaired)


@pytest.mark.parametrize("bad", [{"proposed_rules": [None]}, {"proposed_rules": [], "unresolved_items": None}])
def test_unverifiable_structure_fails_closed(bad):
    _, good = candidate()
    with pytest.raises(ValueError):
        verify_repair_preserves_valid_parts(json.dumps(bad), good)


@pytest.mark.parametrize("change_sibling", [False, True])
def test_real_batch_collection_checks_repair_before_saving(change_sibling, monkeypatch):
    source, good = candidate()
    codes = [rule.official_code for rule in good.proposed_rules]
    monkeypatch.setattr("app.agents.protocol_deconstructor._plan_semantic_rule_batches",
                        lambda *args, **kwargs: [[code] for code in codes])
    first = good.model_copy(update={"proposed_rules": [good.proposed_rules[0]]}, deep=True)
    second = good.model_copy(update={"proposed_rules": [good.proposed_rules[1]]}, deep=True)
    before = failed_with_valid_siblings(second)
    repaired = repaired_candidate(before)
    if change_sibling:
        repaired.proposed_rules[0].components[0].title = "不得改写的兄弟项"
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="same", text=first.model_dump_json()),
        ProtocolAgentResponse(session_id="same", text=json.dumps(before)),
        ProtocolAgentResponse(session_id="same", text=repaired.model_dump_json()),
    ])
    transport.semantic_cache_identity = lambda **kwargs: {"model": "synthetic-frozen-model"}
    class Cache:
        def __init__(self):
            self.saved = {}
        def load(self, key):
            return self.saved.get(key)
        def store(self, key, value):
            self.saved[key] = value
    cache = Cache()
    response, error = _collect_initial_semantic_response(source, prompt_template="冻结原文",
        transport=transport, batch_size=1, batch_cache=cache)
    assert len(transport.start_prompts) + len(transport.repair_prompts) == 3
    if change_sibling:
        assert "兄弟要求" in error
        assert len(cache.saved) == 1
    else:
        assert error is None
        assert len(cache.saved) == 2
        assert response.call_metadata["batches"][-1]["structural_preservation"]["preserved_components"] >= 1


@pytest.mark.parametrize("prior_calls", [0, 2, 3])
def test_explicit_structural_recovery_uses_remaining_budget_only(prior_calls):
    source, good = candidate()
    before = failed_with_valid_siblings(good)
    previous = ProtocolAgentResponse(session_id="saved-session", text=json.dumps(before))
    class Transport(FakeTransport):
        uses_compact_wire_contract = False
        logical_run_budget = LogicalCallBudget("saved-run", max_requests=10, max_output_tokens=100)
        logical_call_budget = LogicalCallBudget("saved-scope", max_requests=3, max_output_tokens=30)
        def history(self, session_id):
            return [{"role": "user", "content": "冻结上下文"},
                    {"role": "assistant", "content": previous.text}]
        def configure_output_scope(self, **kwargs):
            pass
        def configure_logical_task(self, **kwargs):
            assert kwargs["max_requests"] == 3
        def continue_session(self, **kwargs):
            self.logical_call_budget.reserve(request_sha256="synthetic", max_tokens=10)
            self.logical_run_budget.reserve(request_sha256="synthetic", max_tokens=10)
            return super().continue_session(**kwargs)
    transport = Transport([ProtocolAgentResponse(session_id="saved-session",
        text=repaired_candidate(before).model_dump_json())])
    for _ in range(prior_calls):
        transport.logical_call_budget.reserve(request_sha256="old-synthetic", max_tokens=10)
    if prior_calls == 2:
        response, repaired = recover_structural_batch(source_input=source, previous_response=previous,
            transport=transport, batch_id="1/1", rule_codes=[rule.official_code for rule in good.proposed_rules])
        assert response.call_metadata["scope_budget_after"]["requests_used"] == 3
        assert len(transport.repair_prompts) == 1
        assert repaired.proposed_rules
    else:
        with pytest.raises((ValueError, RuntimeError)):
            recover_structural_batch(source_input=source, previous_response=previous,
                transport=transport, batch_id="1/1", rule_codes=[rule.official_code for rule in good.proposed_rules])
        assert not transport.repair_prompts


def component_recovery_transport(previous, reply, prior_calls=3, saved=None):
    class Transport(FakeTransport):
        uses_compact_wire_contract = False
        def __init__(self):
            super().__init__([ProtocolAgentResponse(session_id="fresh-one", text=json.dumps(reply))])
            self.saved = {} if saved is None else saved
            self._call_budget_store = self
            self.logical_run_budget = LogicalCallBudget("original-run", max_requests=8, max_output_tokens=80)
            self.original_budget = LogicalCallBudget("original-scope", max_requests=3, max_output_tokens=30)
            for _ in range(prior_calls):
                self.original_budget.reserve(request_sha256="old", max_tokens=10)
            self.logical_call_budget = self.original_budget
        def semantic_cache_identity(self, **kwargs):
            return "frozen-synthetic-route"
        def configure_output_scope(self, **kwargs):
            self.scope = kwargs
        def load_call_budget(self, key):
            return self.saved.get(key)
        def store_call_budget(self, value):
            self.saved[value["logical_task_id"]] = value
        def configure_logical_task(self, *, logical_task_id, max_requests):
            self.logical_call_budget = LogicalCallBudget(logical_task_id, max_requests=max_requests,
                max_output_tokens=20, saved=self.saved.get(logical_task_id),
                persist=lambda value: self.saved.update({logical_task_id: value}))
        def start(self, **kwargs):
            self.logical_call_budget.reserve(request_sha256="new-one", max_tokens=10)
            self.logical_run_budget.reserve(request_sha256="new-one", max_tokens=10)
            return super().start(**kwargs)
    return Transport()


@pytest.mark.parametrize("restricted", [False, True])
@pytest.mark.parametrize("target_first", [False, True])
def test_one_component_proposal_assembles_frozen_siblings_and_cannot_reset_budget(restricted, target_first):
    source, good = candidate()
    good.proposed_rules = good.proposed_rules[:1]
    before = failed_with_valid_siblings(good)
    target = repaired_candidate(before).proposed_rules[0].components[-1]
    if target_first:
        before["proposed_rules"][0]["components"].insert(0, before["proposed_rules"][0]["components"].pop())
    replacement = target.model_dump(mode="json")
    if restricted:
        replacement = {key: replacement[key] for key in ("title", "source_span_ids", "source_excerpts")}
        replacement.update(limitation_kind="consumer_unavailable", unresolved_dimensions=["合成能力尚未接通"])
    reply = {"candidate_id": good.candidate_id, "replacement_rules": [{
        "official_code": good.proposed_rules[0].official_code,
        "components": [] if restricted else [replacement],
        "restricted_components": [replacement] if restricted else [],
    }], "replacement_unresolved_items": [], "replacement_structural_warnings": []}
    text = json.dumps(before)
    transport = component_recovery_transport(text, reply)
    frozen = transport.original_budget.snapshot()
    kwargs = dict(source_input=source, previous_text=text, transport=transport,
        official_code=good.proposed_rules[0].official_code,
        component_index=0 if target_first else len(before["proposed_rules"][0]["components"]) - 1)
    response, assembled = recover_invalid_component(**kwargs)
    assert response.call_metadata["candidate_only"] is True
    assert response.call_metadata["prior_exhausted_budget"] == frozen
    assert transport.original_budget.snapshot() == frozen
    sibling_index = 1 if target_first and not restricted else 0
    assert assembled.proposed_rules[0].components[sibling_index] == good.proposed_rules[0].components[0]
    assert len(transport.start_prompts) == 1
    assert transport.scope["component_limit"] == 1
    assert "其他程序能力缺口不得借该标签通过" in transport.start_prompts[0]
    if restricted:
        assert response.call_metadata["restricted_capability"] == {
            "limitation_kind": "consumer_unavailable", "source_proof_family": None,
            "adoption_checked": False,
        }
    with pytest.raises(ValueError, match="既有恢复预算"):
        recover_invalid_component(**kwargs)
    transport.logical_call_budget = transport.original_budget
    with pytest.raises(RuntimeError, match="预算已用尽"):
        recover_invalid_component(**kwargs)
    assert len(transport.start_prompts) == 1
    fresh = component_recovery_transport(text, reply, saved=transport.saved)
    with pytest.raises(RuntimeError, match="预算已用尽"):
        recover_invalid_component(**{**kwargs, "transport": fresh})
    assert not fresh.start_prompts


@pytest.mark.parametrize("fault", ["foreign_source", "two_invalid", "valid_target", "prior_remaining"])
def test_invalid_component_preflight_prevents_unnecessary_or_foreign_call(fault):
    source, good = candidate()
    good.proposed_rules = good.proposed_rules[:1]
    before = failed_with_valid_siblings(good)
    index = len(before["proposed_rules"][0]["components"]) - 1
    if fault == "foreign_source":
        before["proposed_rules"][0]["components"][index]["source_excerpts"] = ["不属于冻结原文"]
    elif fault == "two_invalid":
        before["proposed_rules"][0]["components"][0]["title"] = ""
    elif fault == "valid_target":
        before["proposed_rules"][0]["components"][index]["title"] = "已合法目标"
    transport = component_recovery_transport(json.dumps(before), {}, prior_calls=2 if fault == "prior_remaining" else 3)
    with pytest.raises(ValueError):
        recover_invalid_component(source_input=source, previous_text=json.dumps(before), transport=transport,
            official_code=good.proposed_rules[0].official_code, component_index=index)
    assert not transport.start_prompts


@pytest.mark.parametrize("fault", ["wrong_parent", "new_issue", "two_components", "changed_quote"])
def test_component_proposal_cannot_expand_target_or_write_sibling(fault):
    source, good = candidate()
    good.proposed_rules = good.proposed_rules[:1]
    before = failed_with_valid_siblings(good)
    target = repaired_candidate(before).proposed_rules[0].components[-1].model_dump(mode="json")
    reply = {"candidate_id": good.candidate_id, "replacement_rules": [{
        "official_code": good.proposed_rules[0].official_code, "components": [target],
    }], "replacement_unresolved_items": [], "replacement_structural_warnings": []}
    if fault == "wrong_parent":
        reply["replacement_rules"][0]["official_code"] = "EX-99"
    elif fault == "new_issue":
        reply["replacement_unresolved_items"] = [{"code": "NEW", "affected_scope": ["IN-01"], "source_refs": ["source-1"]}]
    elif fault == "two_components":
        reply["replacement_rules"][0]["components"].append(copy.deepcopy(target))
    else:
        target["source_excerpts"] = ["改变的原文"]
    transport = component_recovery_transport(json.dumps(before), reply)
    with pytest.raises(ValueError):
        recover_invalid_component(source_input=source, previous_text=json.dumps(before), transport=transport,
            official_code=good.proposed_rules[0].official_code,
            component_index=len(before["proposed_rules"][0]["components"]) - 1)
    assert len(transport.start_prompts) == 1


@pytest.mark.parametrize("payload,index", [([], 0), ({}, 0), ({"proposed_rules": None}, 0),
    ({"proposed_rules": [None]}, 0), ({"proposed_rules": [{"official_code": "IN-01", "components": []}]}, 0)])
def test_component_preflight_shape_errors_are_typed_and_do_not_call(payload, index):
    source, _ = candidate()
    transport = component_recovery_transport(json.dumps(payload), {})
    with pytest.raises(ValueError):
        recover_invalid_component(source_input=source, previous_text=json.dumps(payload),
            transport=transport, official_code="IN-01", component_index=index)
    assert not transport.start_prompts


def test_component_recovery_requires_persistent_budget_store():
    source, good = candidate()
    transport = component_recovery_transport("", {})
    transport._call_budget_store = None
    with pytest.raises(ValueError, match="持久预算"):
        recover_invalid_component(source_input=source, previous_text=good.model_dump_json(),
            transport=transport, official_code="IN-01", component_index=0)
    assert not transport.start_prompts


def test_offline_fenced_proposal_preserves_json_and_does_not_adopt_commentary():
    source, good = candidate()
    good.proposed_rules = good.proposed_rules[:1]
    before = failed_with_valid_siblings(good)
    target = repaired_candidate(before).proposed_rules[0].components[-1].model_dump(mode="json")
    proposal = {"candidate_id": good.candidate_id, "replacement_rules": [{
        "official_code": good.proposed_rules[0].official_code, "components": [target],
    }], "replacement_unresolved_items": [], "replacement_structural_warnings": []}
    body = json.dumps(proposal, ensure_ascii=False, indent=2)
    text, proof = decode_fenced_repair_proposal("核对说明，不是采用依据。\n```json\n" + body + "\n```\n仍需核实。")
    assert text == body
    assert proof["candidate_only"] is True
    assert proof["raw_output_sha256"] != proof["extracted_output_sha256"]
    response = ProtocolAgentResponse(session_id="offline-revalidation", text=text)
    assembled = assemble_invalid_component_proposal(source_input=source, previous_text=json.dumps(before),
        response=response, official_code=good.proposed_rules[0].official_code,
        component_index=len(before["proposed_rules"][0]["components"]) - 1)
    assert assembled.proposed_rules[0].components[0] == good.proposed_rules[0].components[0]
    assert response.call_metadata["candidate_only"] is True
    assert "scope_budget_after" not in response.call_metadata
    proposal["replacement_rules"][0]["components"][0]["source_excerpts"] = ["不是冻结原文"]
    response.text = json.dumps(proposal)
    with pytest.raises(ValueError, match="更换原文"):
        assemble_invalid_component_proposal(source_input=source, previous_text=json.dumps(before),
            response=response, official_code=good.proposed_rules[0].official_code,
            component_index=len(before["proposed_rules"][0]["components"]) - 1)


@pytest.mark.parametrize("text", [
    '说明 {"other":1}\n```json\n{}\n```',
    '```json\n{}\n```\n```json\n{}\n```',
    '```json\n{}', '```python\n{}\n```', '```json\n[]\n```',
    '```json\n{"a":1,"a":2}\n```', '```json\n{"nested":{"a":1,"a":2}}\n```',
    '```json\n{} {}\n```', '说明\n{}\n说明',
])
def test_offline_proposal_does_not_guess_between_structures(text):
    with pytest.raises(ValueError):
        decode_fenced_repair_proposal(text)
