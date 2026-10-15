from copy import deepcopy

from app.projections.page_review_model_input import group_pending_observations
from app.projections.page_review_model_input import retained_pending_summary


def test_grouping_is_lossless_and_preserves_interleaved_order():
    pending = [
        {"page_review_id": lane, "lane": lane, "kind": "facts",
         "review_status": "association_pending", "review_message": "待核对",
         "observation": {"observation_id": str(index), "raw_value": value,
                         "context": {"date": date}, "region": {"excerpt": value}},
         "same_source_passage": None}
        for index, (lane, value, date) in enumerate([
            ("main-A", "4.2 mg/L", "2026-01-01"),
            ("main-B", "4.2 mg/L", "2026-02-01"),
            ("main-A", "未见书面判断", None),
        ])
    ]
    original = deepcopy(pending)
    groups = group_pending_observations(pending)
    rebuilt = sorted(
        (item["position"], {**group["shared"], **item["detail"]})
        for group in groups for item in group["observations"]
    )
    assert [item for _, item in rebuilt] == original
    assert pending == original
    assert len(groups) == 2
    groups[0]["observations"][0]["detail"]["observation"]["raw_value"] = "changed"
    assert pending == original


def test_empty_pending_stays_empty():
    assert group_pending_observations([]) == []


def test_retained_summary_removes_only_pending_detail_not_accepted_or_clause_conflicts():
    source = {"accepted_pages": [{
        "page_number": 3, "accepted_observations": [{"raw_value": "keep"}],
        "pending_observation_groups": group_pending_observations([
            {"lane": "main-A", "kind": "facts", "review_status": "association_pending",
             "observation": {"raw_value": "pending-value"}},
            {"lane": "main-B", "kind": "facts", "review_status": "association_pending",
             "observation": {"raw_value": "other-pending-value"}},
        ]),
        "fact_conflicts": [{"unverified": "value"}],
        "handwriting_conflicts": [], "signal_conflicts": [{"clause": "keep"}],
    }], "page_dispositions": [{"page_number": 3}]}
    before = deepcopy(source)
    projected = retained_pending_summary(source)
    page = projected["accepted_pages"][0]
    assert page["accepted_observations"] == before["accepted_pages"][0]["accepted_observations"]
    assert page["signal_conflicts"] == [{"clause": "keep"}]
    assert page["pending_retention"]["observation_count"] == 2
    assert page["pending_retention"]["counts"] == [
        {"kind": "facts", "review_status": "association_pending", "count": 2}]
    assert "pending_observation_groups" not in page and "fact_conflicts" not in page
    assert projected["page_dispositions"] == source["page_dispositions"]
    assert source == before
