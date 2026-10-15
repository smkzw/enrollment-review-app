from app.domain.contracts.page_review import ObservationContext, PageFactObservation, PageReviewRecord
from app.domain.page_normalization import fact_normalization_key, handwriting_normalization_key
from app.domain.page_reconciliation import reconcile_page_reviews
from tests.v2.domain.test_page_review_contracts import _review_payload


def _fact(day):
    context = ObservationContext(target_text="检验项目", time_text=day, location_text="表格第一行")
    key, value, unit = fact_normalization_key("检查值", "4.2", context=context.model_dump())
    return PageFactObservation(observation_id=day, field_name="检查值", raw_value="4.2", raw_text="4.2",
                               normalized_value=value, normalized_unit=unit, normalization_key=key,
                               region={"excerpt": "检查值 4.2"}, context=context)


def test_distinct_dates_do_not_merge_equal_values_and_both_can_be_accepted():
    facts = [_fact("2026-09-01"), _fact("2026-09-02")]
    a = PageReviewRecord(**{**_review_payload(), "facts": facts})
    b = PageReviewRecord(**{**_review_payload(), "page_review_id": "b", "lane": "main-B", "facts": facts})
    result = reconcile_page_reviews([a, b], determination_modes={})
    assert len(result.accepted_fact_keys) == 2
    assert not result.fact_conflicts


def test_different_dates_do_not_count_as_corresponding_observations():
    a = PageReviewRecord(**{**_review_payload(), "facts": [_fact("2026-09-01")]})
    b = PageReviewRecord(**{**_review_payload(), "page_review_id": "b", "lane": "main-B", "facts": [_fact("2026-09-02")]})
    result = reconcile_page_reviews([a, b], determination_modes={})
    assert not result.accepted_fact_keys
    assert result.fact_conflicts


def test_handwriting_targets_and_polarity_are_part_of_association():
    a = ObservationContext(target_text="项目甲")
    b = ObservationContext(target_text="项目乙")
    assert handwriting_normalization_key("cs_ncs_judgment", "NCS", context=a.model_dump())[0] != handwriting_normalization_key("cs_ncs_judgment", "NCS", context=b.model_dump())[0]
    assert fact_normalization_key("病史", "记录", context=a.model_dump())[0] != fact_normalization_key("病史", "记录", context=a.model_copy(update={"polarity": "negated"}).model_dump())[0]


def test_equivalent_dates_have_same_context_key():
    assert _fact("2026-09-01").normalization_key == _fact("2026年9月1日").normalization_key


def test_missing_context_is_retained_as_unresolved_not_accepted():
    payload = _review_payload()
    for fact in payload["facts"]:
        key, value, unit = fact_normalization_key(fact.field_name, fact.raw_value)
        fact.context = None
        fact.normalization_key = key
        fact.normalized_value = value
        fact.normalized_unit = unit
    for item in payload["handwriting"]:
        item.context = None
        item.normalization_key, item.normalized_text = handwriting_normalization_key(item.kind.value, item.raw_text)
    a = PageReviewRecord(**payload)
    b = PageReviewRecord(**{**payload, "page_review_id": "b", "lane": "main-B"})
    result = reconcile_page_reviews([a, b], determination_modes={})
    assert result.accepted_fact_keys == []
    assert result.accepted_handwriting == []
    assert result.fact_conflicts and result.handwriting_conflicts


def test_blank_handwriting_target_cannot_be_accepted_by_two_readers():
    payload = _review_payload()
    for item in payload["handwriting"]:
        item.context = ObservationContext(target_text=" \u3000")
        item.normalization_key, item.normalized_text = handwriting_normalization_key(
            item.kind.value, item.raw_text, context=item.context.model_dump())
    a = PageReviewRecord(**payload)
    b = PageReviewRecord(**{**payload, "page_review_id": "b", "lane": "main-B"})
    result = reconcile_page_reviews([a, b], determination_modes={})
    assert not result.accepted_handwriting
    assert result.handwriting_conflicts
