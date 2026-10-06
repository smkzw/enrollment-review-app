"""Separate citations are preserved candidates, not approved source relationships."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from app.agents.evidence_normalizer import (
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, EvidenceNormalizerRunner, parse_evidence_normalizer_output,
    validate_evidence_normalizer_output,
)
from app.domain.contracts.evidence_normalizer import EvidenceNormalizerInput, EvidenceNormalizerOutput, evidence_normalizer_input_scope_hash
from app.domain.contracts.facts import AssertionBasis, ClinicalFactCandidateV2, ClinicalFactV2
from app.domain.contracts.enums import GateOutcome, FactGate, LocatorAuthenticity, LocatorPrecision, LocatorSourceLayer
from app.domain.gates.fact_candidate_gates import gate_fact_candidate
from app.domain.gates import fact_evidence_closure as closure
from app.evidence.artifacts import ArtifactStore
from app.projections.normalizer_reference_aliases import NormalizerReferenceAliases
from app.storage.codecs import encode_contract, decode_contract
from tests.v2.agents.test_evidence_normalizer_adapter import _input, _page, _bound_draft_payload, _FakeTransport
from tests.v2.domain.test_fact_evidence_closure import _make_revision
from tests.v2.services.test_fact_context_consumers import _context_fact


def _source_input():
    old = _input()
    pages = [_page(1, "量表甲", ["loc-1"]), _page(2, "项目乙2", ["loc-2"])]
    locators = [item.model_copy(update={"localized_text": page.effective_text,
        "source_text_sha256": page.effective_text_sha256})
        for item, page in zip(old.available_locators, pages, strict=True)]
    digest = evidence_normalizer_input_scope_hash(authority=old.authority,
        logical_document_id=old.logical_document_id, context=old.context,
        related_requirements=old.related_requirements, manifest_sha256=old.manifest_sha256,
        completion_manifest_sha256=old.completion_manifest_sha256, page_numbers=old.page_numbers,
        pages=pages, available_locator_ids=old.available_locator_ids, available_locators=locators)
    return EvidenceNormalizerInput.model_validate({**old.model_dump(mode="json"),
        "pages": [p.model_dump(mode="json") for p in pages],
        "available_locators": [loc.model_dump(mode="json") for loc in locators],
        "input_scope_sha256": digest})


def _payload():
    payload = _bound_draft_payload("unused")
    payload["schema_version"] = "phase5/normalizer-draft/v5"
    payload["unresolved_items"] = []
    fact = payload["fact_candidates"][0]
    fact.update(assertion_scope="observed_state", asserted_object="项目乙", fact_type="measurement",
        supported_requirement_ids=[], polarity="affirmed", raw_value=2, canonical_value=2,
        unit="unitless", locator_ids=["loc-1", "loc-2"])
    fact["assertion_basis"].update(asserted_object="项目乙", assertion_text="项目乙2", locator_id="loc-2",
        contextual_qualifiers=[{"kind": "assessment", "label": "量表甲",
            "source": {"locator_id": "loc-1", "excerpt": "量表甲"}}])
    return payload


def _parse(payload, *, texts=None, aliases=None):
    inp = _source_input()
    return parse_evidence_normalizer_output(json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id, expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id, expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids), created_at=inp.created_at,
        locator_source_hashes={loc.locator_id: loc.source_text_sha256 for loc in inp.available_locators},
        locator_source_texts=texts if texts is not None else {loc.locator_id: loc.localized_text for loc in inp.available_locators},
        reference_aliases=aliases, require_current_draft=True)


@pytest.mark.parametrize("change", [None, "hash", "excerpt", "nonmember"])
def test_structured_revalidation_uses_frozen_context_sources(change):
    inp, output = _source_input(), _parse(_payload())
    if change is not None:
        payload = output.model_dump(mode="json")
        fact = payload["fact_candidates"][0]
        source = fact["assertion_basis"]["contextual_qualifiers"][0]["source"]
        if change == "hash":
            source["source_text_sha256"] = "0" * 64
        elif change == "excerpt":
            source["excerpt"] = "量表甲外"
        else:
            fact["locator_ids"] = ["loc-2"]
        with pytest.raises(ValueError):
            output = EvidenceNormalizerOutput.model_validate(payload)
            validate_evidence_normalizer_output(output, inp)
        return
    revalidated = validate_evidence_normalizer_output(output, inp)
    assert revalidated == output
    assert gate_fact_candidate(revalidated.fact_candidates[0])[FactGate.POLARITY_AND_ASSERTED_OBJECT].outcome == GateOutcome.BLOCKED


@pytest.mark.parametrize("compact", [False, True])
def test_separate_citation_roundtrip_and_actual_runner_storage_consumer(data_paths, compact):
    inp, payload = _source_input(), _payload()
    aliases = NormalizerReferenceAliases.from_payload(inp.model_dump(mode="json"))
    output = _parse(aliases.transform(payload) if compact else payload, aliases=aliases if compact else None)
    fact = output.fact_candidates[0]
    assert fact.assertion_basis.assertion_text == "项目乙2"
    assert fact.asserted_object == "项目乙"
    source = fact.assertion_basis.contextual_qualifiers[0].source
    assert source.locator_id == "loc-1" and source.excerpt == "量表甲"
    assert source.source_text_sha256 == hashlib.sha256("量表甲".encode()).hexdigest()
    assert output.unresolved_items[0].code == "context_relation_unverified"
    assert output.unresolved_items[0].gap_type is None
    assert not output.unresolved_items[0].affected_requirement_ids
    transport = _FakeTransport([(json.dumps(payload, ensure_ascii=False), "ctx-session")])
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=0).run(
        inp, transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, require_current_draft=True)
    assert result.final_output == output
    artifacts = ArtifactStore(data_paths)
    stored = artifacts.put("evaluation_manifest", result.final_output.model_dump_json().encode())
    restored = EvidenceNormalizerOutput.model_validate_json(artifacts.read(stored.storage_ref))
    assert restored == output
    encoded, sha = encode_contract(fact)
    assert decode_contract(ClinicalFactCandidateV2, encoded, sha) == fact
    verdict = gate_fact_candidate(restored.fact_candidates[0])[FactGate.POLARITY_AND_ASSERTED_OBJECT]
    assert verdict.outcome == GateOutcome.BLOCKED
    assert verdict.affected_scope == ["loc-1", "loc-2"]
    # Even bypassing the candidate gate cannot turn a cited pending relationship
    # into a published fact through the existing publication contract.
    published = _context_fact().model_dump(mode="json")
    published.update(asserted_object=fact.asserted_object,
        assertion_basis=fact.assertion_basis.model_dump(mode="json"), locator_ids=fact.locator_ids)
    with pytest.raises(ValueError, match="仅可保留候选与疑问"):
        ClinicalFactV2.model_validate(published)


@pytest.mark.parametrize("change,pattern", [
    ("unknown_locator", "冻结"), ("nonmember", "冻结"), ("wrong_label", "自己的独立摘录"),
    ("joined_excerpt", "连续且唯一"), ("duplicate_quote", "连续且唯一"),
    ("missing_text", "连续且唯一"), ("model_hash", "source_text_sha256"),
    ("model_verified", "verified"),
])
def test_no_frozen_source_or_relationship_authority_can_be_invented(change, pattern):
    payload = _payload()
    fact = payload["fact_candidates"][0]
    qualifier = fact["assertion_basis"]["contextual_qualifiers"][0]
    texts = None
    if change == "unknown_locator":
        qualifier["source"]["locator_id"] = "other-patient"
        fact["locator_ids"].append("other-patient")
    elif change == "nonmember":
        fact["locator_ids"] = ["loc-2"]
    elif change == "wrong_label":
        qualifier["label"] = "量表乙"
    elif change == "joined_excerpt":
        qualifier["source"]["excerpt"] = "量表甲项目乙2"
    elif change == "duplicate_quote":
        texts = {"loc-1": "量表甲量表甲", "loc-2": "项目乙2"}
    elif change == "missing_text":
        texts = {}
    elif change == "model_hash":
        qualifier["source"]["source_text_sha256"] = "a" * 64
    else:
        qualifier["verified"] = True
    from app.agents.evidence_normalizer_repair import EvidenceContextError
    with pytest.raises(EvidenceContextError, match=pattern) as exc:
        _parse(payload, texts=texts)
    assert exc.value.bounded_repair and exc.value.candidate_refs == ("f1",)


@pytest.mark.parametrize("failure", [None, "hash", "other_document", "page_only", "fabricated_quote"])
def test_current_source_gate_rechecks_both_citations(monkeypatch, failure):
    fact = _parse(_payload()).fact_candidates[0]
    locators = {loc.locator_id: SimpleNamespace(locator_id=loc.locator_id, page_artifact_id=f"pa-{loc.page_number}",
        page_number=loc.page_number, source_document_version_id="doc-1", source_layer=LocatorSourceLayer.RAW_OCR,
        authenticity=LocatorAuthenticity.DEGRADED, target_id="test", source_text_sha256=loc.source_text_sha256,
        precision=LocatorPrecision.PAGE_EXCERPT, excerpt=loc.localized_text)
        for loc in _source_input().available_locators}
    if failure == "hash":
        locators["loc-1"].source_text_sha256 = "0" * 64
    elif failure == "other_document":
        locators["loc-1"].source_document_version_id = "other-doc"
    elif failure == "page_only":
        locators["loc-1"].precision = LocatorPrecision.PAGE_ONLY
    elif failure == "fabricated_quote":
        locators["loc-1"].excerpt = "量表乙"
    monkeypatch.setattr(closure, "_fetch_cached", lambda session, lid, cache, batch: locators[lid])
    result, reasons, _ = closure.validate_locator_and_text_hash(None, fact,
        _make_revision(locator_ids=["loc-1", "loc-2"]))
    assert result == (GateOutcome.ACCEPTED if failure is None else GateOutcome.REJECTED)
    assert bool(reasons) == (failure is not None)
    # Source authenticity and relationship truth remain separate checks.
    assert gate_fact_candidate(fact)[FactGate.POLARITY_AND_ASSERTED_OBJECT].outcome == GateOutcome.BLOCKED


def test_old_inline_context_bytes_and_new_draft_schema_do_not_request_hashes():
    from app.agents.evidence_normalizer import evidence_normalizer_json_schema
    old = _context_fact().assertion_basis
    assert old.contextual_qualifiers[0].model_dump(mode="json") == {"kind": "assessment", "label": "量表甲"}
    assert AssertionBasis.model_validate_json(old.model_dump_json()) == old
    schema = evidence_normalizer_json_schema()["$defs"]["FactContextSourceDraft"]
    assert set(schema["properties"]) == {"locator_id", "excerpt"}
    assert "source_text_sha256" not in json.dumps(schema)


def test_r3_sidecar_header_cannot_become_an_accepted_context_source():
    from tests.v2.agents.test_evidence_normalizer_adapter import _r3_input_with_accepted_fact
    from app.projections.page_review_sources import validate_accepted_candidate_sources
    inp, refs = _r3_input_with_accepted_fact()
    output = _parse(_payload())
    fact = output.fact_candidates[0].model_copy(update={"source_observation_refs": refs})
    output = output.model_copy(update={"fact_candidates": [fact]})
    with pytest.raises(ValueError, match="不能借OCR侧车"):
        validate_accepted_candidate_sources(output, inp.page_review, locator_inputs=inp.available_locators)


@pytest.mark.parametrize("repair", ["empty", "inline", "replace", "deduplicate"])
def test_actual_runner_cannot_clear_original_cross_location_uncertainty(repair):
    from copy import deepcopy
    payload = _payload()
    original_context = payload["fact_candidates"][0]["assertion_basis"]["contextual_qualifiers"][0]
    payload["fact_candidates"][0]["assertion_basis"]["contextual_qualifiers"].append(deepcopy(original_context))
    proposal = deepcopy(payload)
    qualifiers = proposal["fact_candidates"][0]["assertion_basis"]["contextual_qualifiers"]
    if repair == "empty":
        qualifiers.clear()
    elif repair == "inline":
        qualifiers[:] = [{"kind": "assessment", "label": "项目乙", "source": None}]
    elif repair == "replace":
        qualifiers[:] = [{"kind": "assessment", "label": "项目乙",
                           "source": {"locator_id": "loc-2", "excerpt": "项目乙2"}}]
    else:
        qualifiers.pop()
    transport = _FakeTransport([(json.dumps(item, ensure_ascii=False), "ctx-session") for item in (payload, proposal)])
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=1).run(
        _source_input(), transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        require_current_draft=True)
    assert len(transport.start_prompts) == len(transport.repair_prompts) == 1
    if repair == "deduplicate":
        assert result.final_output is not None
        fact = result.final_output.fact_candidates[0]
        assert gate_fact_candidate(fact)[FactGate.POLARITY_AND_ASSERTED_OBJECT].outcome == GateOutcome.BLOCKED
        assert result.final_output.unresolved_items[0].code == "context_relation_unverified"
    else:
        assert result.final_output is None
        assert "解除归属待核状态" in "；".join(result.attempts[-1].issues)


@pytest.mark.parametrize("repair", ["preserve", "empty", "inline", "replace", "delete_fact"])
def test_generic_format_recovery_retains_pending_context(repair):
    from copy import deepcopy
    payload = _payload()
    del payload["fact_candidates"][0]["unit"]
    proposal = deepcopy(payload)
    fact = proposal["fact_candidates"][0]
    fact["unit"] = "unitless"
    qualifiers = fact["assertion_basis"]["contextual_qualifiers"]
    if repair == "empty":
        qualifiers.clear()
    elif repair == "inline":
        qualifiers[:] = [{"kind": "assessment", "label": "项目乙"}]
    elif repair == "replace":
        qualifiers[0]["source"] = {"locator_id": "loc-2", "excerpt": "项目乙2"}
    elif repair == "delete_fact":
        proposal["fact_candidates"] = []
        proposal["unresolved_items"] = [{"code": "no_result", "message": "本页无结果",
            "affected_page_numbers": [1, 2], "affected_locator_ids": [], "reason": "无记录"}]
    transport = _FakeTransport([(json.dumps(item, ensure_ascii=False), "ctx-session") for item in (payload, proposal)])
    result = EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=1).run(
        _source_input(), transport, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        require_current_draft=True)
    assert len(transport.start_prompts) == len(transport.repair_prompts) == 1
    if repair == "preserve":
        assert result.final_output is not None
        assert gate_fact_candidate(result.final_output.fact_candidates[0])[FactGate.POLARITY_AND_ASSERTED_OBJECT].outcome == GateOutcome.BLOCKED
    else:
        assert result.final_output is None
        assert "解除归属待核状态" in "；".join(result.attempts[-1].issues)
