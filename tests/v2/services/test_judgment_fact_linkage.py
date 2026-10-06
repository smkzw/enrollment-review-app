"""Exact assertion subspans are source links, never judgment adoption."""
from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import LocatorPrecision
from app.domain.contracts.facts import AssertionBasis
from app.domain.contracts.judgment_search import JudgmentSearchCoverageSummary
from app.domain.contracts.predicate_binding import predicate_component_identity_sha256
from app.domain.contracts.rules import EvidenceRequirement
from app.services import judgment_content_input, judgment_content_receipts, qualified_judgment_content
from app.domain.publication import canonical_hash
from app.workflow.errors import InvalidJobDefinitionError
from app.services.judgment_fact_linkage import (
    judgment_content_input_version, judgment_source_index, link_judgment_excerpts,
)
from app.storage.repositories import ScopeViolationError
from tests.v2.services.test_predicate_binding_input import (
    _component_contract, _fact_record, _frozen_input, _locator_record, _sha,
)

QUOTE = "检验甲：异常（NCS）。"


def _source(*, quote=QUOTE, excerpt=None, object_name="检验甲", copies=1,
            precision=LocatorPrecision.TEXT_RANGE, basis_hash=None, linked=True):
    excerpt = excerpt if excerpt is not None else f"本次分析：{quote}其余检查见原件。"
    component = _component_contract(["p-1"], "component-a")
    requirements = [EvidenceRequirement(
        requirement_id="req-1", rule_component_id="component-a", fact_type="judgment",
        due_stage="screening", description="研究者书面判断", predicate_ids=["p-1"],
        allows_screening_record_transcription=True, requires_contemporaneous_objective_source=False,
    )]
    fields = {name: getattr(component, name) for name in (
        "rule_component_id", "parent_rule_id", "official_code", "kind", "display_code",
        "title", "rule_source_text", "expression", "exception_expression", "trigger_predicates",
        "exception_predicates", "repeat_trigger_conditions",
    )}
    component = component.model_copy(update={
        "evidence_requirements": requirements,
        "component_identity_sha256": predicate_component_identity_sha256(
            **fields, evidence_requirements=requirements),
    })
    locators, facts = [], []
    for number in range(copies):
        locator_id = f"loc-{number}"
        locator = _locator_record(locator_id).model_copy(update={
            "source_document_version_id": "document-1", "page_artifact_id": "page-1",
            "excerpt": excerpt, "text_end": len(excerpt), "precision": precision,
            **({"text_start": None, "text_end": None} if precision == LocatorPrecision.PAGE_ONLY else {}),
        })
        basis = AssertionBasis(asserted_object=object_name, assertion_text=quote,
            locator_id=locator_id if linked else "unattached-locator",
            source_text_sha256=basis_hash or locator.source_text_sha256)
        fact = _fact_record(f"fact-{number}", _sha(f"identity-{number}"),
            [locator_id]).model_copy(update={
                "asserted_object": object_name, "assertion_basis": basis,
            })
        locators.append(locator)
        facts.append(fact)
    return _frozen_input([component], facts, locators)


def _summary(*, quote=QUOTE, document="document-1", artifact="page-1", page=1, requirement="req-1"):
    return JudgmentSearchCoverageSummary.model_validate({
        "scope_sha256": _sha("scope"), "requirement_id": requirement,
        "status": "candidates_present", "found_candidates": [{
            "lane": "main-A", "provider": "synthetic", "model": "synthetic",
            "source_document_version_id": document, "page_artifact_id": artifact,
            "page_number": page, "page_image_sha256": _sha("image"),
            "channel": "printed_analysis", "candidates": [{"text": quote}],
        }],
    })


def test_unique_short_quote_links_without_changing_old_receipt_algorithm():
    source, summary = _source(), _summary()
    before = source.model_dump(mode="json")
    current = link_judgment_excerpts(summary, source)[0]
    historical = link_judgment_excerpts(summary, source, linkage_version=1)[0]
    assert current.status == "unique_source_match"
    assert current.matches == (("fact-0", "loc-0"),)
    assert historical.status == "no_source_match"
    assert current.linkage_id != historical.linkage_id
    assert source.model_dump(mode="json") == before
    assert not summary.product_acceptance and not summary.professional_judgment_absence_proven


def test_full_excerpt_remains_linkable_in_both_versions():
    source, summary = _source(excerpt=QUOTE), _summary()
    for version in (1, 2):
        assert link_judgment_excerpts(summary, source, linkage_version=version)[0].status == "unique_source_match"


def test_same_quote_at_two_locators_is_ambiguous_not_merged():
    result = link_judgment_excerpts(_summary(), _source(copies=2))[0]
    assert result.status == "ambiguous_source_match"
    assert len(result.matches) == 2


@pytest.mark.parametrize("changes", [
    {"excerpt": QUOTE + QUOTE},
    {"quote": "aba", "excerpt": "ababa", "object_name": "a"},
    {"object_name": "检验乙"},
    {"basis_hash": _sha("different-layer")},
    {"precision": LocatorPrecision.PAGE_ONLY},
    {"linked": False},
    {"excerpt": "原件中没有该句"},
])
def test_unlocated_or_nonunique_assertion_cannot_enter_source_index(changes):
    assert judgment_source_index(_source(**changes)) == {}


@pytest.mark.parametrize("changes", [
    {"quote": "NCS"}, {"quote": QUOTE + "额外判断"},
    {"document": "other-document"}, {"artifact": "other-page"}, {"page": 2},
])
def test_search_excerpt_requires_exact_quote_and_same_source(changes):
    assert link_judgment_excerpts(_summary(**changes), _source())[0].status == "no_source_match"


def test_requirement_not_in_frozen_scope_is_not_linked():
    row = link_judgment_excerpts(_summary(requirement="foreign"), _source())[0]
    assert row.status == "requirement_outside_binding_scope" and not row.matches


@pytest.mark.parametrize("family,version", [("predicate", True), ("control", 3), ("unknown", 2)])
def test_unsupported_linkage_versions_are_rejected(family, version):
    with pytest.raises(ValueError):
        judgment_content_input_version(family, version)


@pytest.mark.parametrize("family", ["predicate", "control"])
@pytest.mark.parametrize("version", [1, 2])
def test_input_reconstruction_uses_explicit_historical_algorithm(monkeypatch, family, version):
    seen = []
    material = dict(family=family, review_context_id="context", review_context_sha256=_sha("context"),
        frozen_input=None, frozen_input_sha256=_sha("frozen"), comparison_sha256=_sha("comparison"),
        candidate_receipt_sha256s=[], pairs=[])
    monkeypatch.setattr(judgment_content_input, "load_completed_candidate_qualification_input",
        lambda *args, **kwargs: material)
    def loader(*args, **kwargs):
        seen.append(kwargs["linkage_version"])
        return ()
    monkeypatch.setattr(judgment_content_input, "load_prepared_judgment_links", loader)
    monkeypatch.setattr(judgment_content_input, "load_prepared_control_judgment_links", loader)
    name = judgment_content_input_version(family, version)
    result = judgment_content_input.load_judgment_content_input(None, None,
        candidate_job_id="candidate", context_id="context", input_version=name)
    assert result["version"] == name and seen == [version]
    assert result["pairs"] == [] and result["excerpt_coverage"] == []
    if version == 2:
        assert judgment_content_input.load_judgment_content_input(None, None,
            candidate_job_id="candidate", context_id="context")["input_sha256"] == result["input_sha256"]


def test_empty_input_version_cannot_silently_become_current(monkeypatch):
    monkeypatch.setattr(judgment_content_input, "load_completed_candidate_qualification_input",
        lambda *args, **kwargs: {"family": "predicate", "review_context_id": "context"})
    with pytest.raises(ValueError, match="版本"):
        judgment_content_input.load_judgment_content_input(None, None,
            candidate_job_id="candidate", context_id="context", input_version="")


@pytest.mark.parametrize("family", ["predicate", "control"])
def test_current_adoption_rejects_old_input_before_method_or_supported_pairs(monkeypatch, family):
    monkeypatch.setattr(qualified_judgment_content, "verify_completed_judgment_content",
        lambda *args: {"payload": {"input_version": judgment_content_input_version(family, 1)}})
    with pytest.raises(ScopeViolationError, match="不一致"):
        qualified_judgment_content.verify_qualified_content(None, None,
            source={"candidate_family": family}, binding_method=None, adoption=SimpleNamespace(job_id="old"))


@pytest.mark.parametrize("version", [1, 2])
def test_receipt_rebuild_preserves_input_version_and_rejects_changed_material(monkeypatch, version):
    material = dict(version=judgment_content_input_version("predicate", version),
        candidate_job_id="candidate", review_context_id="context", review_context_sha256=_sha("context"),
        frozen_input_sha256=_sha("frozen"), comparison_sha256=_sha("comparison"),
        candidate_receipt_sha256s=[], pairs=[], excerpt_coverage=[])
    material["input_sha256"] = canonical_hash(material)
    payload = {**material, "input_version": material["version"]}
    seen = []
    def loader(*args, **kwargs):
        seen.append(kwargs["input_version"])
        return material.copy()
    monkeypatch.setattr(judgment_content_receipts, "load_judgment_content_input", loader)
    before = payload.copy()
    assert judgment_content_receipts.rebuild_judgment_content_input(None, None, payload) == material
    assert seen == [material["version"]] and payload == before
    with pytest.raises(InvalidJobDefinitionError, match="不一致"):
        judgment_content_receipts.rebuild_judgment_content_input(None, None,
            {**payload, "comparison_sha256": _sha("changed")})


def test_old_consumer_evaluation_cannot_authorize_new_method():
    binding = SimpleNamespace(candidate_family="predicate")
    content = dict(contract="contract", prompt_version="prompt", summary={"version": "summary"}, routes={})
    method = SimpleNamespace(candidate_family="predicate", source_qualification_method=binding,
        content_contract="contract", content_prompt_version="prompt", content_summary_version="summary",
        content_routes={}, content_consumer_version="qualified-judgment-content/v2")
    manifest = SimpleNamespace(evaluation_kind="written_judgment_content_fidelity", methods=[method])
    with pytest.raises(ScopeViolationError, match="版本"):
        qualified_judgment_content.require_content_method(manifest, binding, content)
    method.content_consumer_version = qualified_judgment_content.CONTENT_CONSUMER_VERSION
    qualified_judgment_content.require_content_method(manifest, binding, content)
