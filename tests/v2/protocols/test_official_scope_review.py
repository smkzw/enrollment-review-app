"""Synthetic source/proposal readers through stored gate and publication consumers."""
from __future__ import annotations

import hashlib
import json

import pytest

from app.agents.protocol_deconstructor import ProtocolAgentResponse, protocol_output_response_format
from app.domain.contracts.agent_io import ProtocolDeconstructionDraft
from app.domain.contracts.enums import ReviewStage
from app.domain.contracts.protocol_scope_review import OfficialScopeReading
from app.evidence.artifacts import ArtifactStore
from app.llm.logical_call_budget import LogicalCallBudget
from app.protocols.deconstruction_gate import ProtocolDeconstructionGate
from app.protocols.official_scope_review import OfficialScopeReviewError
from app.services.protocol_scope_review_service import review_official_source_scope
from app.storage.config import resolve_data_paths
from tests.v2.protocols.slice4_helpers import confirmed_fixture


def scope_fixture(heading="筛选时和基线时需满足以下标准：", *, two_nodes=True):
    source, draft, spans = confirmed_fixture()
    child = "筛选时，年龄≥18岁"
    source.source_materials[0].text = heading + child
    rule = draft.proposed_rules[0]
    rule.source_text = heading + child
    component = rule.components[0]
    component.expression.predicate.source_clause = child
    component.expression.predicate.observation_policy = component.expression.predicate.observation_policy.model_copy(update={"source_excerpts": [child]})
    draft.component_drafts[0].source_excerpts = [child]
    draft.component_drafts[0].proposed_component = component.model_copy(deep=True)
    requirement = component.evidence_requirements[0]
    requirement.predicate_ids = [component.expression.predicate.predicate_id]
    if two_nodes:
        second_text = "基线时，年龄≥21岁"
        source.source_materials[0].text += "；" + second_text
        rule.source_text = source.source_materials[0].text
        second = component.model_copy(deep=True)
        second.rule_component_id = "component-in-baseline"
        second.display_code = "IN-01b"
        second.expression.predicate.predicate_id = "predicate-age-baseline"
        second.expression.predicate.value = 21
        second.expression.predicate.source_clause = second_text
        second.expression.predicate.observation_policy = second.expression.predicate.observation_policy.model_copy(update={"source_excerpts": [second_text]})
        second.evidence_requirements[0].requirement_id = "req-in-baseline"
        second.evidence_requirements[0].rule_component_id = second.rule_component_id
        second.evidence_requirements[0].due_stage = ReviewStage.BASELINE
        second.evidence_requirements[0].predicate_ids = [second.expression.predicate.predicate_id]
        rule.components.append(second)
        binding = draft.component_drafts[0].model_copy(deep=True)
        binding.draft_component_id = "draft-component-in-baseline"
        binding.proposed_component = second.model_copy(deep=True)
        binding.source_excerpts = [second_text]
        draft.component_drafts.append(binding)
        requirement_draft = draft.evidence_requirement_drafts[0].model_copy(deep=True)
        requirement_draft.draft_requirement_id = "draft-req-in-baseline"
        requirement_draft.draft_component_id = binding.draft_component_id
        requirement_draft.proposed_requirement = second.evidence_requirements[0].model_copy(deep=True)
        draft.evidence_requirement_drafts.append(requirement_draft)
        draft.proposed_workflow_stages[1].due_requirement_ids.append("req-in-baseline")
    draft.component_drafts[0].proposed_component = component.model_copy(deep=True)
    draft.evidence_requirement_drafts[0].proposed_requirement = requirement.model_copy(deep=True)
    return source, draft, spans


class ScopeReader:
    """Deterministic synthetic completion, not a medical model or gold standard."""
    def __init__(self, *, relation="separate_nodes", stages=None, agree=True, fail_second=False):
        self.relation, self.stages = relation, stages
        self.agree, self.fail_second = agree, fail_second
        self.prompts = []
        self.logical_call_budget = LogicalCallBudget("synthetic-scope", max_requests=2, max_output_tokens=131072)

    def _wire_contract_prompt(self, prompt, output_kind):
        assert output_kind == "official_source_scope_review"
        return prompt

    def _completion_kwargs(self, messages, *, output_kind):
        return {"model": "synthetic-reader", "messages": messages, "max_tokens": 65536,
                "response_format": protocol_output_response_format(output_kind)}

    def start(self, *, prompt, output_kind):
        self.prompts.append(prompt)
        if self.fail_second and len(self.prompts) == 2:
            raise TimeoutError("synthetic transport failed")
        basis = json.loads(prompt.split("\n冻结输入：\n", 1)[1])
        is_proposal = len(self.prompts) == 2
        from app.protocols.deconstruction_gate import _source_review_stages
        items = []
        for child in basis["children"]:
            stages = self.stages or sorted(stage.value for stage in _source_review_stages(child["source_excerpts"]))
            citations = [*basis["headings"], *[
                {"source_span_id": child["source_refs"][0], "excerpt": excerpt}
                for excerpt in child["source_excerpts"]]]
            items.append({
            "component_id": child["component_id"], "relation": self.relation,
            "required_stages": stages,
            "citations": citations,
            "predicate_assignments": [{"predicate_id": value["predicate_id"], "required_stages": stages,
                "citations": [{"source_span_id": child["source_refs"][0], "excerpt": clause} for clause in value["source_clauses"]]}
                for value in child["predicates"]],
            "heading_dispositions": [{**heading, "disposition": {"separate_nodes": "node_overview", "governing": "shared_constraint", "context_only": "context_only"}[self.relation],
                "finding": "根据该总标题及子项的逐字节点说明核对，不以关系标签代替原文。", "supporting_citations": citations}
                for heading in basis["headings"]],
            "unresolved_dimensions": [], "proposal_agreement": self.agree if is_proposal else None,
            })
        messages = [{"role": "user", "content": prompt}]
        sha = hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return ProtocolAgentResponse(
            session_id=f"synthetic-session-{len(self.prompts)}", text=OfficialScopeReading(items=items).model_dump_json(),
            call_metadata={"attempts": [{"request_sha256": sha, "requested_model": "synthetic-reader",
                                         "reported_model": "synthetic-reader", "finish_reason": "stop"}]},
        )


class UncertainScopeReader(ScopeReader):
    def __init__(self, *, component_ids=None):
        super().__init__()
        self.component_ids = component_ids

    def start(self, **kwargs):
        response = super().start(**kwargs)
        reading = json.loads(response.text)
        for item in reading["items"]:
            if self.component_ids is not None and item["component_id"] not in self.component_ids:
                continue
            item.update(relation="unresolved", required_stages=[],
                        unresolved_dimensions=["原文尚不能确认该条件的审核节点"])
            for assignment in item["predicate_assignments"]:
                assignment["required_stages"] = []
            for heading in item["heading_dispositions"]:
                heading["disposition"] = "unresolved"
            if item["proposal_agreement"] is not None:
                item["proposal_agreement"] = False
        return response.model_copy(update={"text": OfficialScopeReading.model_validate(reading).model_dump_json()})


def test_two_reads_store_relationship_without_changing_clinical_fields(tmp_path):
    source, draft, spans = scope_fixture()
    original = draft.model_dump_json()
    store, reader = ArtifactStore(resolve_data_paths(str(tmp_path / "data"))), ScopeReader()
    reviewed = review_official_source_scope(source, draft, official_code="IN-01", transport=reader, store=store)
    assert draft.model_dump_json() == original
    before = json.loads(reader.prompts[0].split("\n冻结输入：\n", 1)[1])
    assert all("component" not in item for item in before["children"])
    assert "component" in json.loads(reader.prompts[1].split("\n冻结输入：\n", 1)[1])["children"][0]
    component = reviewed.proposed_rules[0].components[0]
    assert component.source_scope_review_ref
    assert [item.due_stage for item in component.evidence_requirements] == [ReviewStage.SCREENING]
    restored = ProtocolDeconstructionDraft.model_validate_json(reviewed.model_dump_json())
    result = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, restored, source_spans=spans)
    assert result.publishable
    with pytest.raises(OfficialScopeReviewError):
        review_official_source_scope(source, draft, official_code="EX-01", transport=reader, store=store)


class NonduplicatedHeadingReader(ScopeReader):
    def start(self, **kwargs):
        response = super().start(**kwargs)
        reading = OfficialScopeReading.model_validate_json(response.text)
        for item in reading.items:
            for disposition in item.heading_dispositions:
                disposition.supporting_citations = [cite for cite in item.citations
                    if not (cite.source_span_id == disposition.source_span_id
                            and disposition.excerpt in cite.excerpt)]
        return response.model_copy(update={"text": reading.model_dump_json()})


def test_heading_witness_is_shared_within_the_verified_item_not_duplicated(tmp_path):
    from app.protocols.official_scope_review import SCOPE_VALIDATION_POLICY
    source, draft, spans = scope_fixture()
    before = draft.model_dump_json()
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    reviewed = review_official_source_scope(source, draft, official_code="IN-01",
                                            transport=NonduplicatedHeadingReader(), store=store)
    proof = json.loads(store.read(reviewed.proposed_rules[0].components[0].source_scope_review_ref))
    assert proof["validation_policy"] == SCOPE_VALIDATION_POLICY
    raw_refs = [receipt["response_ref"] for receipt in proof["receipts"]]
    raw_bytes = {ref: store.read(ref) for ref in raw_refs}
    for ref in raw_refs:
        reading = OfficialScopeReading.model_validate_json(json.loads(raw_bytes[ref])["text"])
        for item in reading.items:
            for disposition in item.heading_dispositions:
                assert not any(cite.source_span_id == disposition.source_span_id
                               and disposition.excerpt in cite.excerpt
                               for cite in disposition.supporting_citations)
    assert ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, reviewed, source_spans=spans).publishable
    assert draft.model_dump_json() == before
    # Historical policy still rejects the same raw answers. It is not rewritten.
    legacy = {**proof, "validation_policy": "component-local/v1"}
    legacy_ref = store.put("evaluation_manifest", json.dumps(legacy).encode()).storage_ref
    historical = reviewed.model_copy(deep=True)
    for component in historical.proposed_rules[0].components:
        component.source_scope_review_ref = legacy_ref
        next(binding for binding in historical.component_drafts
             if binding.proposed_component.rule_component_id == component.rule_component_id
             ).proposed_component.source_scope_review_ref = legacy_ref
    result = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, historical, source_spans=spans)
    assert not result.publishable
    assert any(issue.issue_code == "SOURCE_SCOPE_REVIEW_REJECTED" for check in result.checks for issue in check.issues)
    assert all(store.read(ref) == content for ref, content in raw_bytes.items())


def test_heading_explanation_still_requires_its_own_nonempty_support(tmp_path):
    from pydantic import ValidationError
    source, draft, _ = scope_fixture()
    class EmptySupportReader(NonduplicatedHeadingReader):
        def start(self, **kwargs):
            response = super().start(**kwargs)
            reading = json.loads(response.text)
            reading["items"][0]["heading_dispositions"][0]["supporting_citations"] = []
            return response.model_copy(update={"text": json.dumps(reading, ensure_ascii=False)})
    store, reader = ArtifactStore(resolve_data_paths(str(tmp_path / "data"))), EmptySupportReader()
    before = draft.model_dump_json()
    with pytest.raises(ValidationError, match="supporting_citations"):
        review_official_source_scope(source, draft, official_code="IN-01", transport=reader, store=store)
    assert len(reader.prompts) == 1 and draft.model_dump_json() == before
    responses = [json.loads(path.read_bytes()) for path in
                 (store.data_paths.root / "artifacts/raw_response").iterdir()]
    assert len(responses) == 1
    assert json.loads(responses[0]["text"])["items"][0]["heading_dispositions"][0]["supporting_citations"] == []


def test_two_heading_witnesses_are_pinned_to_this_item_and_each_disposition(tmp_path):
    from app.protocols.official_scope_review import SCOPE_VALIDATION_POLICY, validate_scope_reading
    source, draft, _ = scope_fixture()
    store, reader = ArtifactStore(resolve_data_paths(str(tmp_path / "data"))), NonduplicatedHeadingReader()
    reviewed = review_official_source_scope(source, draft, official_code="IN-01", transport=reader, store=store)
    proof = json.loads(store.read(reviewed.proposed_rules[0].components[0].source_scope_review_ref))
    first = proof["receipts"][0]
    reading = OfficialScopeReading.model_validate_json(json.loads(store.read(first["response_ref"]))["text"])
    basis = json.loads(reader.prompts[0].split("\n冻结输入：\n", 1)[1])
    second_heading = {**basis["headings"][0], "source_span_id": "synthetic-second-heading"}
    basis["headings"].append(second_heading)
    basis["materials"].append({"source_span_id": second_heading["source_span_id"],
                               "text": second_heading["excerpt"]})
    for item in reading.items:
        item.citations.append(item.citations[0].model_copy(update=second_heading))
        second = item.heading_dispositions[0].model_copy(deep=True)
        second.source_span_id = second_heading["source_span_id"]
        item.heading_dispositions.append(second)
    validate_scope_reading(reading, basis, proposal=False, validation_policy=SCOPE_VALIDATION_POLICY)
    bad = reading.model_copy(deep=True)
    bad.items[0].heading_dispositions[1].source_span_id = "neighbor-source"
    with pytest.raises(OfficialScopeReviewError, match="SOURCE_SCOPE_REVIEW_HEADING_MISSING"):
        validate_scope_reading(bad, basis, proposal=False, validation_policy=SCOPE_VALIDATION_POLICY)


@pytest.mark.parametrize("fault", ["missing", "foreign_ref", "wrong_excerpt", "neighbor_only", "wrong_disposition", "changed_source"])
def test_shared_heading_witness_does_not_remove_source_or_scope_boundaries(tmp_path, fault):
    source, draft, spans = scope_fixture()
    class InvalidReader(NonduplicatedHeadingReader):
        def start(self, **kwargs):
            response = super().start(**kwargs)
            reading = OfficialScopeReading.model_validate_json(response.text)
            selected = reading.items[0]
            heading = selected.heading_dispositions[0]
            index = next(i for i, cite in enumerate(selected.citations)
                         if cite.source_span_id == heading.source_span_id and heading.excerpt in cite.excerpt)
            if fault in {"missing", "neighbor_only"}:
                selected.citations.pop(index)
            elif fault == "foreign_ref":
                selected.citations[index].source_span_id = "foreign-source"
            elif fault == "wrong_excerpt":
                selected.citations[index].excerpt = "这个标题并不在冻结原文中"
            elif fault == "wrong_disposition":
                heading.disposition = "context_only"
            return response.model_copy(update={"text": reading.model_dump_json()})
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    reviewed = review_official_source_scope(source, draft, official_code="IN-01", transport=InvalidReader(), store=store)
    if fault == "changed_source":
        source.source_materials[0].text += "来源修订"
    result = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, reviewed, source_spans=spans)
    assert not result.publishable
    assert any(issue.issue_code in {"SOURCE_SCOPE_REVIEW_REJECTED", "SOURCE_SCOPE_REVIEW_INVALID"}
               for check in result.checks for issue in check.issues)


@pytest.mark.parametrize("change", ["source", "threshold", "stage", "citation", "missing_store", "raw_corruption"])
def test_old_relationship_cannot_release_changed_or_unverifiable_scope(tmp_path, change):
    source, draft, spans = scope_fixture()
    paths = resolve_data_paths(str(tmp_path / "data"))
    store = ArtifactStore(paths)
    reviewed = review_official_source_scope(source, draft, official_code="IN-01", transport=ScopeReader(), store=store)
    if change == "source":
        source.source_materials[0].text = source.source_materials[0].text.replace("需满足", "均须满足全部")
    elif change == "threshold":
        reviewed.proposed_rules[0].components[0].expression.predicate.value = 21
    elif change == "stage":
        reviewed.proposed_rules[0].components[0].evidence_requirements[0].due_stage = ReviewStage.BASELINE
    elif change == "citation":
        reviewed.component_drafts[0].source_refs = ["span-ex"]
    elif change == "raw_corruption":
        ref = reviewed.proposed_rules[0].components[0].source_scope_review_ref
        manifest = json.loads(store.read(ref))
        target = paths.root / manifest["receipts"][0]["response_ref"]
        target.write_bytes(b'{"status":"not a response"}')
    reader = None if change == "missing_store" else store.read
    result = ProtocolDeconstructionGate(artifact_reader=reader).evaluate(source, reviewed, source_spans=spans)
    assert not result.publishable
    assert any(item.issue_code == "SOURCE_SCOPE_REVIEW_INVALID" for check in result.checks for item in check.issues)


def test_common_heading_does_not_clear_an_actual_missing_node(tmp_path):
    source, draft, spans = scope_fixture("筛选和基线时均应满足以下全部标准：")
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    reviewed = review_official_source_scope(source, draft, official_code="IN-01",
        transport=ScopeReader(relation="governing", stages=["screening", "baseline"]), store=store)
    gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, reviewed, source_spans=spans)
    assert not gate.publishable
    assert any(issue.issue_code == "SOURCE_SCOPE_REVIEW_REJECTED" for check in gate.checks for issue in check.issues)
    assert draft.proposed_rules[0].components[0].source_scope_review_ref is None
    assert not ProtocolDeconstructionGate().evaluate(source, draft, source_spans=spans).publishable


def test_all_rejected_completed_review_supersedes_old_clearance(tmp_path):
    source, draft, spans = scope_fixture()
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    previous = review_official_source_scope(source, draft, official_code="IN-01", transport=ScopeReader(), store=store)
    previous_bytes = previous.model_dump_json()
    previous_ref = previous.proposed_rules[0].components[0].source_scope_review_ref
    assert ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, previous, source_spans=spans).publishable
    reader = ScopeReader(relation="governing", stages=["screening", "baseline"])
    current = review_official_source_scope(source, previous, official_code="IN-01", transport=reader, store=store)
    assert current.proposed_rules[0].components[0].source_scope_review_ref != previous_ref
    assert previous.model_dump_json() == previous_bytes
    assert len(reader.prompts) == 2
    gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, current, source_spans=spans)
    assert not gate.publishable
    rejected = {ref for check in gate.checks for issue in check.issues
                if issue.issue_code == "SOURCE_SCOPE_REVIEW_REJECTED" for ref in issue.affected_refs}
    assert rejected == {component.rule_component_id for component in current.proposed_rules[0].components}


@pytest.mark.parametrize("failure", ["transport", "budget"])
def test_unfinished_review_keeps_original_and_completed_answers(tmp_path, failure):
    source, draft, _ = scope_fixture()
    paths = resolve_data_paths(str(tmp_path / "data"))
    reader = ScopeReader(fail_second=failure == "transport")
    if failure == "budget":
        reader.logical_call_budget = LogicalCallBudget("too-small", max_requests=1, max_output_tokens=65536)
    original = draft.model_dump_json()
    with pytest.raises((OfficialScopeReviewError, TimeoutError)):
        review_official_source_scope(source, draft, official_code="IN-01", transport=reader, store=ArtifactStore(paths))
    assert draft.model_dump_json() == original
    raw = list((paths.root / "artifacts/raw_response").glob("*"))
    assert len(raw) == (0 if failure == "budget" else 2)


def test_serialization_without_review_preserves_historical_shape():
    _, draft, _ = confirmed_fixture()
    assert "source_scope_review_ref" not in draft.model_dump_json()


def test_scope_reading_rejects_unknown_keys_and_predicate_judgments():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        OfficialScopeReading(items=[{"component_id": "x", "relation": "separate_nodes",
            "required_stages": ["screening"], "citations": [{"source_span_id": "s", "excerpt": "q"}],
            "unresolved_dimensions": [], "proposal_agreement": True, "verified": True}])


@pytest.mark.parametrize("separator", ["", "\n"])
def test_heading_layout_does_not_invent_an_extra_clinical_predicate(tmp_path, separator):
    source, draft, spans = scope_fixture("筛选时和基线时需满足以下标准：" + separator)
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    unreviewed = ProtocolDeconstructionGate().evaluate(source, draft, source_spans=spans)
    assert not unreviewed.publishable
    reviewed = review_official_source_scope(source, draft, official_code="IN-01", transport=ScopeReader(), store=store)
    assert ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, reviewed, source_spans=spans).publishable


def test_unresolved_sibling_does_not_rewrite_or_discard_a_verified_item(tmp_path):
    source, draft, spans = scope_fixture()
    rule = draft.proposed_rules[0]
    sibling = rule.components[1].model_copy(deep=True)
    class PartialReader(ScopeReader):
        def start(self, **kwargs):
            response = super().start(**kwargs)
            reading = OfficialScopeReading.model_validate_json(response.text)
            item = reading.items[-1]
            item.relation = "unresolved"
            item.unresolved_dimensions = ["原文未说明该子项是否在两个节点分别适用"]
            for heading in item.heading_dispositions:
                heading.disposition = "unresolved"
            if item.proposal_agreement is not None:
                item.proposal_agreement = False
            return response.model_copy(update={"text": reading.model_dump_json()})
    result = review_official_source_scope(source, draft, official_code="IN-01", transport=PartialReader(),
                                         store=ArtifactStore(resolve_data_paths(str(tmp_path / "data"))))
    assert result.proposed_rules[0].components[0].source_scope_review_ref
    updated = result.proposed_rules[0].components[-1]
    assert updated.model_copy(update={"source_scope_review_ref": None}) == sibling
    assert updated.source_scope_review_ref
    gate = ProtocolDeconstructionGate(artifact_reader=ArtifactStore(resolve_data_paths(str(tmp_path / "data"))).read)
    assert not gate.evaluate(source, result, source_spans=spans).publishable
    assert draft.proposed_rules[0].components[0].source_scope_review_ref is None


@pytest.mark.parametrize("all_unknown", [False, True])
def test_completed_unknown_supersedes_previous_clearance_without_rewriting_history(tmp_path, all_unknown):
    source, draft, spans = scope_fixture()
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    cleared = review_official_source_scope(source, draft, official_code="IN-01", transport=ScopeReader(), store=store)
    old_bytes = cleared.model_dump_json()
    old_ref = cleared.proposed_rules[0].components[-1].source_scope_review_ref
    old_receipt = store.read(old_ref)
    unknown_ids = None if all_unknown else {cleared.proposed_rules[0].components[-1].rule_component_id}
    updated = review_official_source_scope(source, cleared, official_code="IN-01",
        transport=UncertainScopeReader(component_ids=unknown_ids), store=store)
    assert cleared.model_dump_json() == old_bytes and store.read(old_ref) == old_receipt
    assert updated.proposed_rules[0].components[-1].source_scope_review_ref != old_ref
    assert updated.component_drafts[-1].proposed_component == updated.proposed_rules[0].components[-1]
    before_gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, cleared, source_spans=spans)
    after_gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, updated, source_spans=spans)
    assert before_gate.publishable and not after_gate.publishable
    unresolved = [issue for check in after_gate.checks for issue in check.issues if issue.issue_code == "SOURCE_SCOPE_REVIEW_UNRESOLVED"]
    assert len(unresolved) == (2 if all_unknown else 1)
    assert all("原文尚不能确认" in issue.problem for issue in unresolved)
    assert not any(issue.issue_code == "SOURCE_SCOPE_REVIEW_INVALID" for check in after_gate.checks for issue in check.issues)


def test_disagreement_is_a_completed_unresolved_outcome_not_a_transport_failure(tmp_path):
    source, draft, spans = scope_fixture()
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    updated = review_official_source_scope(source, draft, official_code="IN-01",
        transport=ScopeReader(agree=False), store=store)
    gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, updated, source_spans=spans)
    assert not gate.publishable
    assert any(issue.issue_code == "SOURCE_SCOPE_REVIEW_UNRESOLVED" for check in gate.checks for issue in check.issues)


@pytest.mark.parametrize("fault", ["model", "length", "request", "session"])
def test_receipt_identity_and_terminal_evidence_are_required(tmp_path, fault):
    source, draft, spans = scope_fixture()
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    reviewed = review_official_source_scope(source, draft, official_code="IN-01", transport=ScopeReader(), store=store)
    component = reviewed.proposed_rules[0].components[0]
    record = json.loads(store.read(component.source_scope_review_ref))
    receipt = record["receipts"][1]
    response = json.loads(store.read(receipt["response_ref"]))
    if fault == "model":
        response["call_metadata"]["attempts"][0]["reported_model"] = "unapproved-model"
    elif fault == "length":
        response["call_metadata"]["attempts"][0]["finish_reason"] = "length"
    elif fault == "request":
        response["call_metadata"]["attempts"][0]["request_sha256"] = "0" * 64
    else:
        response["session_id"] = "synthetic-session-1"
    receipt["response_ref"] = store.put("raw_response", json.dumps(response).encode()).storage_ref
    component.source_scope_review_ref = store.put("evaluation_manifest", json.dumps(record).encode()).storage_ref
    reviewed.component_drafts[0].proposed_component = component.model_copy(deep=True)
    gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, reviewed, source_spans=spans)
    assert not gate.publishable
    assert any(issue.issue_code == "SOURCE_SCOPE_REVIEW_INVALID" for check in gate.checks for issue in check.issues)


def test_real_transport_consumes_persistent_budget_without_restarting_it(tmp_path):
    from types import SimpleNamespace
    from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport
    source, draft, _ = scope_fixture()
    synthetic = ScopeReader()
    calls, saved = [], []
    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            response = synthetic.start(prompt=kwargs["messages"][0]["content"], output_kind="official_source_scope_review")
            return iter([SimpleNamespace(id=f"request-{len(calls)}", model="glm-5.3-flash", usage=None,
                choices=[SimpleNamespace(finish_reason="stop", delta=SimpleNamespace(content=response.text, reasoning_content=None))])])
    transport = DeepSeekProtocolAgentTransport(client=SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
        backend="cms-router", model="glm-5.3-flash", reasoning_effort="high", max_tokens=65536)
    budget = LogicalCallBudget("frozen-scope", max_requests=2, max_output_tokens=131072, persist=saved.append)
    transport.share_call_budget(budget)
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    result = review_official_source_scope(source, draft, official_code="IN-01", transport=transport, store=store)
    assert result.proposed_rules[0].components[0].source_scope_review_ref
    assert len(calls) == 2 and saved[-1]["requests_used"] == 2
    assert saved[-1]["reserved_output_tokens"] == 131072
    assert all(len(call["messages"]) == 1 and "temperature" not in call for call in calls)
    transport.share_call_budget(LogicalCallBudget("frozen-scope", max_requests=2, max_output_tokens=131072, saved=saved[-1]))
    with pytest.raises(OfficialScopeReviewError, match="LOGICAL_BUDGET_EXHAUSTED"):
        review_official_source_scope(source, draft, official_code="IN-01", transport=transport, store=store)
    assert len(calls) == 2


def test_run_or_output_budget_preflight_prevents_a_half_review(tmp_path):
    source, draft, _ = scope_fixture()
    reader = ScopeReader()
    reader.logical_run_budget = LogicalCallBudget("whole-run", max_requests=1, max_output_tokens=131072)
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    with pytest.raises(OfficialScopeReviewError, match="LOGICAL_BUDGET_EXHAUSTED"):
        review_official_source_scope(source, draft, official_code="IN-01", transport=reader, store=store)
    assert reader.prompts == []
    reader.logical_run_budget = None
    reader.logical_call_budget = LogicalCallBudget("frozen-scope", max_requests=2, max_output_tokens=65536)
    with pytest.raises(OfficialScopeReviewError, match="LOGICAL_BUDGET_EXHAUSTED"):
        review_official_source_scope(source, draft, official_code="IN-01", transport=reader, store=store)
    assert reader.prompts == []


def test_scope_only_feedback_cannot_change_a_clinical_condition():
    from app.services.protocol_workbench_service import ProtocolWorkbenchService
    _, draft, _ = scope_fixture()
    revised = draft.model_copy(deep=True)
    revised.proposed_rules[0].components[0].expression.predicate.value = 21
    with pytest.raises(ValueError, match="不得修改条件"):
        ProtocolWorkbenchService._validate_scope_review_only(draft, revised, "IN-01")


@pytest.mark.parametrize("relation", ["context_only", "separate_nodes"])
def test_two_agreeing_labels_cannot_remove_an_unresolved_common_duty(tmp_path, relation):
    source, draft, spans = scope_fixture("筛选和基线时均须满足以下全部标准：", two_nodes=False)
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    reviewed = review_official_source_scope(source, draft, official_code="IN-01",
        transport=ScopeReader(relation=relation), store=store)
    gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, reviewed, source_spans=spans)
    assert not gate.publishable
    assert any(issue.issue_code == "SOURCE_SCOPE_REVIEW_REJECTED" for check in gate.checks for issue in check.issues)
    assert draft.proposed_rules[0].components[0].source_scope_review_ref is None


@pytest.mark.parametrize("heading", [
    "筛选和基线时均须满足以下全部标准：",
    "筛选和基线时均应符合以下各项要求：",
])
def test_distinct_children_do_not_erase_a_substantive_common_prefix(tmp_path, heading):
    source, draft, spans = scope_fixture(heading)
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    reviewed = review_official_source_scope(source, draft, official_code="IN-01", transport=ScopeReader(), store=store)
    gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, reviewed, source_spans=spans)
    assert not gate.publishable
    assert any(issue.issue_code == "SOURCE_SCOPE_REVIEW_REJECTED" for check in gate.checks for issue in check.issues)
    assert all(component.source_scope_review_ref is None for component in draft.proposed_rules[0].components)


def test_aggregate_stage_set_cannot_hide_missing_predicate_attribution():
    from app.protocols.official_source_scope import frozen_parent_scope_fragments
    from app.protocols.deconstruction_gate import _source_review_stages, _substantive_obligation_segments
    from app.protocols.official_scope_review import scope_review_basis, scope_review_prompt, validate_scope_reading
    source, draft, _ = scope_fixture(two_nodes=False)
    component = draft.proposed_rules[0].components[0]
    extra = component.evidence_requirements[0].model_copy(deep=True)
    extra.requirement_id += ":baseline"
    extra.due_stage = ReviewStage.BASELINE
    extra.predicate_ids = []
    component.evidence_requirements.append(extra)
    draft.component_drafts[0].proposed_component = component.model_copy(deep=True)
    headings = frozen_parent_scope_fragments(source, "IN-01", scope_has_stages=lambda text: bool(_source_review_stages([text])),
        is_substantive=lambda text: bool(_substantive_obligation_segments(text)))
    basis = scope_review_basis(source, draft, draft.proposed_rules[0], headings, heading_stages=["screening", "baseline"])
    reader = ScopeReader(relation="governing", stages=["screening", "baseline"])
    first = OfficialScopeReading.model_validate_json(reader.start(prompt=scope_review_prompt(basis), output_kind="official_source_scope_review").text)
    second = OfficialScopeReading.model_validate_json(reader.start(prompt=scope_review_prompt(basis, source_reading=first), output_kind="official_source_scope_review").text)
    with pytest.raises(OfficialScopeReviewError, match="PREDICATE_REQUIREMENT_MISMATCH"):
        validate_scope_reading(second, basis, proposal=True)


def test_descriptive_prompt_and_actual_messages_must_be_the_same_request(tmp_path):
    source, draft, spans = scope_fixture()
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    result = review_official_source_scope(source, draft, official_code="IN-01", transport=ScopeReader(), store=store)
    component = result.proposed_rules[0].components[0]
    record = json.loads(store.read(component.source_scope_review_ref))
    receipt = record["receipts"][0]
    request, response = json.loads(store.read(receipt["request_ref"])), json.loads(store.read(receipt["response_ref"]))
    request["request_options"]["messages"] = [{"role": "user", "content": "another source"}]
    response["call_metadata"]["attempts"][0]["request_sha256"] = hashlib.sha256(json.dumps(
        request["request_options"]["messages"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt["request_ref"] = store.put("raw_request", json.dumps(request).encode()).storage_ref
    receipt["response_ref"] = store.put("raw_response", json.dumps(response).encode()).storage_ref
    component.source_scope_review_ref = store.put("evaluation_manifest", json.dumps(record).encode()).storage_ref
    result.component_drafts[0].proposed_component = component.model_copy(deep=True)
    assert not ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, result, source_spans=spans).publishable


def test_changed_frozen_visit_source_invalidates_scope_review_without_a_model_call(tmp_path):
    source, draft, spans = scope_fixture()
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    reader = ScopeReader()
    result = review_official_source_scope(source, draft, official_code="IN-01", transport=reader, store=store)
    old_ref = result.proposed_rules[0].components[0].source_scope_review_ref
    old_bytes = store.read(old_ref)
    ref = source.required_procedure_catalog.items[0].source_span_ids[0]
    next(item for item in source.source_materials if item.source_span_id == ref).text += "（访视范围已变更）"
    gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, result, source_spans=spans)
    assert any(issue.issue_code == "SOURCE_SCOPE_REVIEW_INVALID" for check in gate.checks for issue in check.issues)
    assert len(reader.prompts) == 2
    assert store.read(old_ref) == old_bytes


def test_restricted_sibling_changes_invalidate_the_parent_review(tmp_path):
    from app.domain.contracts.rules import RestrictedRuleComponent
    source, draft, spans = scope_fixture()
    draft.proposed_rules[0].restricted_components = [RestrictedRuleComponent(
        rule_component_id="limited-sibling", display_code="IN-01c", title="另项待核",
        source_span_ids=["span-in"], source_excerpts=["基线时，年龄≥21岁"],
        limitation_kind="interpretation_unresolved", unresolved_dimensions=["作用范围待核"],
    )]
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    result = review_official_source_scope(source, draft, official_code="IN-01", transport=ScopeReader(), store=store)
    result.proposed_rules[0].restricted_components[0].unresolved_dimensions = ["改变后的作用范围"]
    gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, result, source_spans=spans)
    assert any(issue.issue_code == "SOURCE_SCOPE_REVIEW_INVALID" for check in gate.checks for issue in check.issues)


class PartiallyRejectedScopeReader(ScopeReader):
    def start(self, **kwargs):
        response = super().start(**kwargs)
        reading = OfficialScopeReading.model_validate_json(response.text)
        wrong = reading.items[-1]
        wrong.required_stages = [ReviewStage.SCREENING]
        for assignment in wrong.predicate_assignments:
            assignment.required_stages = [ReviewStage.SCREENING]
        return response.model_copy(update={"text": reading.model_dump_json()})


class JointVisitScopeReader(ScopeReader):
    def start(self, **kwargs):
        response = super().start(**kwargs)
        reading = OfficialScopeReading.model_validate_json(response.text)
        for item in reading.items:
            item.required_stages = [ReviewStage.RUN_IN if stage == ReviewStage.SCREENING else stage
                                    for stage in item.required_stages]
            for assignment in item.predicate_assignments:
                assignment.required_stages = [ReviewStage.RUN_IN if stage == ReviewStage.SCREENING else stage
                                             for stage in assignment.required_stages]
        return response.model_copy(update={"text": reading.model_dump_json()})


def joint_scope_fixture():
    from tests.v2.protocols.test_deconstruction_gate_slice3 import _joint_visit_fixture
    source, draft, spans = scope_fixture()
    joint, _, _ = _joint_visit_fixture()
    source.required_procedure_catalog = joint.required_procedure_catalog
    headers = [item for item in joint.source_materials if item.source_span_id.startswith("span-joint")]
    source.source_materials.extend(headers)
    source.allowed_source_span_ids.extend(item.source_span_id for item in headers)
    return source, draft, spans


def test_source_node_equivalence_diagnoses_a_real_binding_error_without_clearing_it(tmp_path):
    source, draft, spans = joint_scope_fixture()
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    reader = JointVisitScopeReader()
    reviewed = review_official_source_scope(source, draft, official_code="IN-01", transport=reader, store=store)
    gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, reviewed, source_spans=spans)
    assert not gate.publishable
    assert any(issue.issue_code == "SOURCE_SCOPE_REVIEW_NODE_BINDING_MISMATCH"
               and issue.affected_refs == [draft.proposed_rules[0].components[0].rule_component_id]
               for check in gate.checks for issue in check.issues)
    assert reviewed.proposed_rules[0].components[0].evidence_requirements[0].due_stage == ReviewStage.SCREENING
    assert len(reader.prompts) == 2


def test_correcting_a_joint_node_cannot_relabel_old_proof_as_a_current_proposal(tmp_path):
    source, draft, spans = joint_scope_fixture()
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    reviewed = review_official_source_scope(source, draft, official_code="IN-01", transport=JointVisitScopeReader(), store=store)
    old_ref = reviewed.proposed_rules[0].components[0].source_scope_review_ref
    old_bytes = store.read(old_ref)
    component = reviewed.proposed_rules[0].components[0]
    component.evidence_requirements[0].due_stage = ReviewStage.RUN_IN
    reviewed.component_drafts[0].proposed_component = component.model_copy(deep=True)
    result = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, reviewed, source_spans=spans)
    assert any(issue.issue_code == "SOURCE_SCOPE_REVIEW_INVALID" for check in result.checks for issue in check.issues)
    assert store.read(old_ref) == old_bytes


def test_rejected_source_assignment_does_not_clear_itself_or_block_verified_sibling(tmp_path):
    from app.services.protocol_scope_review_service import validate_completed_scope_review
    from app.services.protocol_workbench_service import ProtocolWorkbenchService
    source, draft, spans = scope_fixture()
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    reader = PartiallyRejectedScopeReader()
    reviewed = review_official_source_scope(source, draft, official_code="IN-01", transport=reader, store=store)
    ProtocolWorkbenchService._validate_scope_review_only(draft, reviewed, "IN-01")
    validate_completed_scope_review(source, reviewed, official_code="IN-01", store=store)
    gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, reviewed, source_spans=spans)
    rejected = [issue for check in gate.checks for issue in check.issues
                if issue.issue_code == "SOURCE_SCOPE_REVIEW_REJECTED"]
    assert rejected and all(issue.affected_refs == ["component-in-baseline"] for issue in rejected)
    assert not gate.publishable
    assert not any(issue.issue_code.startswith("SOURCE_SCOPE_REVIEW")
                   and draft.proposed_rules[0].components[0].rule_component_id in issue.affected_refs
                   for check in gate.checks for issue in check.issues)
    assert len(reader.prompts) == 2
    assert draft.proposed_rules[0].components[0].source_scope_review_ref is None


def test_rejected_item_still_verifies_second_receipt_integrity(tmp_path):
    source, draft, spans = scope_fixture()
    paths = resolve_data_paths(str(tmp_path / "data"))
    store = ArtifactStore(paths)
    reviewed = review_official_source_scope(source, draft, official_code="IN-01",
        transport=PartiallyRejectedScopeReader(), store=store)
    manifest = json.loads(store.read(reviewed.proposed_rules[0].components[0].source_scope_review_ref))
    (paths.root / manifest["receipts"][1]["response_ref"]).write_bytes(b'{"bad":"receipt"}')
    gate = ProtocolDeconstructionGate(artifact_reader=store.read).evaluate(source, reviewed, source_spans=spans)
    invalid = [ref for check in gate.checks for issue in check.issues
               if issue.issue_code == "SOURCE_SCOPE_REVIEW_INVALID" for ref in issue.affected_refs]
    assert set(invalid) == {component.rule_component_id for component in draft.proposed_rules[0].components}


@pytest.mark.parametrize("alteration", [None, "source", "model", "receipt_budget", "wire_hash",
    "same_id_reset", "missing_store", "missing_run", "foreign_run", "dispatched_timeout"])
def test_saved_source_read_resumes_only_the_remaining_proposal_in_original_allowance(tmp_path, monkeypatch, alteration):
    from types import SimpleNamespace
    from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    import app.services.protocol_scope_review_service as service
    source, draft, _ = scope_fixture()
    store = ArtifactStore(resolve_data_paths(str(tmp_path / "data")))
    cache = _ProtocolSemanticBatchFileCache(store.data_paths, "offline-scope-recovery")
    scope_id = hashlib.sha256(b"offline-scope").hexdigest()
    run_id = hashlib.sha256(b"offline-run").hexdigest()
    calls, synthetic = [], ScopeReader()
    class Completions:
        fail = False
        def create(self, **kwargs):
            calls.append(kwargs)
            if self.fail:
                raise TimeoutError("after actual dispatch reservation")
            response = synthetic.start(prompt=kwargs["messages"][0]["content"], output_kind="official_source_scope_review")
            return iter([SimpleNamespace(id=f"offline-{len(calls)}", model="glm-5.3-flash", usage=None,
                choices=[SimpleNamespace(finish_reason="stop", delta=SimpleNamespace(content=response.text, reasoning_content=None))])])
    completions = Completions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    def transport():
        reader = DeepSeekProtocolAgentTransport(client=client, backend="cms-router",
            model="glm-5.3-flash", reasoning_effort="high", max_tokens=65536)
        reader.bind_call_budget_store(cache)
        reader.configure_logical_task(logical_task_id=scope_id, max_requests=2)
        reader.configure_logical_run(logical_task_id=run_id, max_requests=2, contract_sha256="frozen-contract")
        return reader
    first = transport()
    original = service.scope_item_rejections
    def host_interruption(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("host interrupted after source persistence, before proposal dispatch")
    monkeypatch.setattr(service, "scope_item_rejections", host_interruption)
    with pytest.raises(RuntimeError, match="host interrupted"):
        review_official_source_scope(source, draft, official_code="IN-01", transport=first, store=store)
    monkeypatch.setattr(service, "scope_item_rejections", original)
    assert len(calls) == 1 and first.logical_call_budget.snapshot()["requests_used"] == 1
    requests = [str(path.relative_to(store.data_paths.root))
                for path in (store.data_paths.root / "artifacts/raw_request").iterdir()]
    source_ref = next(ref for ref in requests if json.loads(store.read(ref))["stage"] == "source")
    responses = [str(path.relative_to(store.data_paths.root))
                 for path in (store.data_paths.root / "artifacts/raw_response").iterdir()]
    response_ref = next(ref for ref in responses if "session_id" in json.loads(store.read(ref)))
    receipt = {"request_ref": source_ref, "response_ref": response_ref}
    resumed = transport()
    if alteration == "source":
        source.source_materials[0].text += "来源变化"
    elif alteration == "model":
        resumed._model = "another-model"
    elif alteration in {"receipt_budget", "wire_hash"}:
        response = json.loads(store.read(response_ref))
        if alteration == "receipt_budget":
            response["call_metadata"]["logical_call_budget"]["logical_task_id"] = "foreign-allowance"
        else:
            response["call_metadata"]["attempts"][-1]["budget_request_sha256"] = "0" * 64
        receipt["response_ref"] = store.put("raw_response", json.dumps(response).encode()).storage_ref
    elif alteration == "same_id_reset":
        historical = resumed.logical_call_budget.snapshot()
        resumed._reserve_completion(calls[0])
        resumed.share_call_budget(LogicalCallBudget(historical["logical_task_id"], max_requests=historical["max_requests"],
            max_output_tokens=historical["max_output_tokens"], saved=historical))
    elif alteration == "missing_store":
        resumed.bind_call_budget_store(None)
    elif alteration == "missing_run":
        resumed.logical_run_budget = None
    elif alteration == "foreign_run":
        resumed.configure_logical_run(logical_task_id=hashlib.sha256(b"another-run").hexdigest(),
                                      max_requests=2, contract_sha256="frozen-contract")
    elif alteration == "dispatched_timeout":
        completions.fail = True
        with pytest.raises(Exception, match="after actual dispatch reservation"):
            review_official_source_scope(source, draft, official_code="IN-01", transport=resumed,
                                         store=store, resume_source_receipt=receipt)
        assert len(calls) == 2 and resumed.logical_call_budget.snapshot()["requests_used"] == 2
    before_calls = len(calls)
    if alteration:
        expected = "LOGICAL_BUDGET_EXHAUSTED" if alteration == "dispatched_timeout" else "SOURCE_SCOPE_REVIEW_INVALID"
        with pytest.raises(OfficialScopeReviewError, match=expected):
            review_official_source_scope(source, draft, official_code="IN-01", transport=resumed,
                                         store=store, resume_source_receipt=receipt)
        assert len(calls) == before_calls
        return
    reviewed = review_official_source_scope(source, draft, official_code="IN-01", transport=resumed,
                                           store=store, resume_source_receipt=receipt)
    assert len(calls) == 2 and resumed.logical_call_budget.snapshot()["requests_used"] == 2
    assert resumed.logical_run_budget.snapshot()["requests_used"] == 2
    assert cache.load_call_budget(scope_id) == resumed.logical_call_budget.snapshot()
    assert cache.load_call_budget(run_id) == resumed.logical_run_budget.snapshot()
    proof = json.loads(store.read(reviewed.proposed_rules[0].components[0].source_scope_review_ref))
    assert proof["receipts"][0] == receipt
    assert json.loads(store.read(proof["receipts"][1]["request_ref"]))["stage"] == "proposal"
