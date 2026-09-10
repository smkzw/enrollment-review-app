import hashlib

import pytest

from app.domain.contracts.page_review import PageReviewRecord
from app.domain.page_normalization import fact_normalization_key
from app.domain.page_source_association import PageAssociationSource, source_aligned_fact_keys
from tests.v2.domain.test_page_review_contracts import _review_payload


def _case():
    a = PageReviewRecord(**_review_payload())
    a.facts[0].context.polarity = "asserted"
    a.facts[0].normalization_key, a.facts[0].normalized_value, a.facts[0].normalized_unit = fact_normalization_key(
        a.facts[0].field_name, a.facts[0].raw_value, context=a.facts[0].context.model_dump())
    fact = a.facts[0].model_copy(deep=True)
    fact.context.location_text = "另一位置描述"
    fact.normalization_key, fact.normalized_value, fact.normalized_unit = fact_normalization_key(
        fact.field_name, fact.raw_value, context=fact.context.model_dump())
    b = PageReviewRecord(**{**_review_payload(), "page_review_id": "b", "lane": "main-B", "facts": [fact]})
    text = a.facts[0].region.excerpt
    source = PageAssociationSource(source_document_version_id=a.source_document_version_id,
        page_number=a.page_number, text=text, text_sha256=hashlib.sha256(text.encode()).hexdigest())
    return a, b, source


def test_unique_source_replaces_only_location_identity():
    a, b, source = _case()
    before = [record.model_dump(mode="json") for record in (a, b)]
    assert source_aligned_fact_keys([a, b], source) == {a.facts[0].normalization_key, b.facts[0].normalization_key}
    assert before == [record.model_dump(mode="json") for record in (a, b)]


def test_blank_target_does_not_establish_agreement_or_source_alignment():
    from app.domain.page_reconciliation import reconcile_page_reviews
    from app.domain.targeted_page_review import compare_targeted_reads
    a, b, source = _case()
    for record in (a, b):
        fact = record.facts[0]
        fact.context.target_text = " \u3000"
        fact.context.location_text = "same"
        fact.normalization_key, fact.normalized_value, fact.normalized_unit = fact_normalization_key(
            fact.field_name, fact.raw_value, context=fact.context.model_dump())
    assert not source_aligned_fact_keys([a, b], source)
    result = reconcile_page_reviews([a, b], determination_modes={}, association_source=source)
    assert not result.accepted_fact_keys
    assert result.fact_conflicts
    outcome = compare_targeted_reads([a, b], [a.facts[0].field_name])
    assert not outcome["agreed_candidate_targets"]


def test_source_alignment_cannot_erase_opposite_arrows():
    a, b, source = _case()
    for record, mark in ((a, "↑"), (b, "↓")):
        fact = record.facts[0]
        fact.raw_value = f"4.2{mark} x10^9/L"
        fact.normalization_key, fact.normalized_value, fact.normalized_unit = fact_normalization_key(
            fact.field_name, fact.raw_value, context=fact.context.model_dump())
    assert not source_aligned_fact_keys([a, b], source)
    from app.domain.page_reconciliation import reconcile_page_reviews
    result = reconcile_page_reviews([a, b], determination_modes={}, association_source=source)
    assert not result.accepted_fact_keys
    assert result.fact_conflicts


def test_layout_normalization_preserves_source_positions_and_ambiguity():
    a, b, source = _case()
    a.facts[0].region.excerpt = "检查值：4.2"
    b.facts[0].region.excerpt = "检查值: 4.2"
    text = "检查\n值： ４.２"
    source = source.model_copy(update={"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
    assert len(source_aligned_fact_keys([a, b], source)) == 2
    text += " 检查值:4.2"
    source = source.model_copy(update={"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
    assert not source_aligned_fact_keys([a, b], source)


@pytest.mark.parametrize("excerpt", ["检查值>4.2", "检查值-4.2", "检查值未检出", "2026-09-07"])
def test_layout_normalization_does_not_erase_material_characters(excerpt):
    a, b, source = _case()
    a.facts[0].region.excerpt = excerpt
    b.facts[0].region.excerpt = excerpt
    text = "检查值<4.2 检查值4.2 检查值检出 2026-09-06"
    source = source.model_copy(update={"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
    assert not source_aligned_fact_keys([a, b], source)


@pytest.mark.parametrize("field,value", [("time_text", "2026-09-02"), ("target_text", "另一项目"), ("polarity", "negated")])
def test_material_context_difference_is_not_erased(field, value):
    a, b, source = _case()
    setattr(b.facts[0].context, field, value)
    b.facts[0].normalization_key, b.facts[0].normalized_value, b.facts[0].normalized_unit = fact_normalization_key(
        b.facts[0].field_name, b.facts[0].raw_value, context=b.facts[0].context.model_dump())
    assert source_aligned_fact_keys([a, b], source) == set()


def test_repeated_excerpt_and_wrong_source_never_match():
    a, b, source = _case()
    repeated = source.model_copy(update={"text": source.text * 2, "text_sha256": hashlib.sha256((source.text * 2).encode()).hexdigest()})
    assert not source_aligned_fact_keys([a, b], repeated)
    with pytest.raises(ValueError):
        source_aligned_fact_keys([a, b], source.model_copy(update={"page_number": source.page_number + 1}))
    with pytest.raises(ValueError):
        source_aligned_fact_keys([a, b], source.model_copy(update={"text": "changed"}))


def test_reconciliation_binds_source_hash_and_keeps_old_observations():
    from app.domain.page_reconciliation import reconcile_page_reviews
    a, b, source = _case()
    plain = reconcile_page_reviews([a, b], determination_modes={})
    linked = reconcile_page_reviews([a, b], determination_modes={}, association_source=source)
    assert not plain.accepted_fact_keys
    assert len(linked.accepted_fact_keys) == 2
    assert linked.association_text_sha256 == source.text_sha256
    assert linked.contract_version == "page-reconciliation/v4"
    assert linked.reconciliation_id != plain.reconciliation_id
    assert not linked.fact_conflicts
    from app.domain.contracts.page_review import PageReconciliation
    for version in ("page-reconciliation/v1", "page-reconciliation/v2"):
        with pytest.raises(ValueError, match="历史对账版本"):
            PageReconciliation.model_validate({**linked.model_dump(), "contract_version": version})


def test_duplicate_observation_or_forged_value_cannot_form_match():
    a, b, source = _case()
    duplicate = b.facts[0].model_copy(update={"observation_id": "duplicate"})
    b.facts.append(duplicate)
    assert not source_aligned_fact_keys([a, b], source)
    b.facts.pop()
    b.facts[0].normalized_value = "999"
    with pytest.raises(ValueError):
        source_aligned_fact_keys([a, b], source)


def test_conflicting_extra_value_cannot_hide_outside_matching_pair():
    a, b, source = _case()
    conflicting = b.facts[0].model_copy(deep=True)
    conflicting.observation_id = "conflicting"
    conflicting.raw_value = "999"
    conflicting.normalization_key, conflicting.normalized_value, conflicting.normalized_unit = fact_normalization_key(
        conflicting.field_name, conflicting.raw_value, context=conflicting.context.model_dump())
    b.facts.append(conflicting)
    assert not source_aligned_fact_keys([a, b], source)


@pytest.mark.parametrize("different_time", [False, True])
def test_exact_match_cannot_ignore_same_context_conflicting_value(different_time):
    from app.domain.page_reconciliation import reconcile_page_reviews
    a, b, source = _case()
    b.facts = [a.facts[0].model_copy(deep=True)]
    conflicting = b.facts[0].model_copy(deep=True)
    conflicting.observation_id = "another-value"
    conflicting.raw_value = "999"
    if different_time:
        conflicting.context.time_text = "2026-09-06"
    conflicting.normalization_key, conflicting.normalized_value, conflicting.normalized_unit = fact_normalization_key(
        conflicting.field_name, conflicting.raw_value, context=conflicting.context.model_dump())
    b.facts.append(conflicting)
    for association_source in (None, source):
        result = reconcile_page_reviews([a, b], determination_modes={}, association_source=association_source)
        assert result.accepted_fact_keys == ([a.facts[0].normalization_key] if different_time else [])
        assert result.fact_conflicts
