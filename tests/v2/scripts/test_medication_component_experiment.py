"""Focused tests for the isolated medication-component experiment contract (v5)."""

import json

import pytest
from pydantic import ValidationError

from scripts.medication_component_experiment import (
    EXPERIMENT_VERSION,
    INSTANCE_SHAPE,
    BoundComponentExtraction,
    MedicationComponentExtraction,
    MedicationExtractionBatch,
    MedicationObservation,
    build_component_prompt,
    compare_component_outputs,
    validate_extraction,
    validate_extraction_batch,
)

_PAGE = {
    "page_artifact_id": "page-1",
    "source_document_version_id": "doc-v1",
    "page_number": 3,
    "page_image_sha256": "a" * 64,
    "clause_pack_sha256": "b" * 64,
}
NULL = {"value": None, "source_quote": None}
DRUG = {"value": "阿司匹林肠溶片", "source_quote": "阿司匹林肠溶片", "completeness": "complete"}
START = {"value": "2025-03-02", "source_quote": "2025-03-02", "role": "use_start", "precision": "day"}
END = {"value": "2025-03-15", "source_quote": "2025-03-15", "role": "use_end", "precision": "day"}
USE = {"value": "use", "source_quote": "阿司匹林肠溶片 100mg qd"}
USE_B = {"value": "use", "source_quote": "阿司匹林肠溶片 100 mg qd"}


def use_of(raw, value="use"):
    return {"value": value, "source_quote": raw}


def make_observation(**overrides):
    payload = {
        "observation_id": "obs-a",
        "page_review_id": "pr-a",
        "lane": "main-A",
        "raw_value": "阿司匹林肠溶片 100mg qd",
        "excerpt": "0. 阿司匹林肠溶片 100mg qd 口服（2025-03-02起）",
        "context": "既往用药史：阿司匹林",
        "page": dict(_PAGE),
    }
    payload.update(overrides)
    return MedicationObservation.model_validate(payload)


def make_paired_observation(**overrides):
    payload = {
        "observation_id": "obs-b",
        "page_review_id": "pr-b",
        "lane": "main-B",
        "raw_value": "阿司匹林肠溶片 100 mg qd",
        "excerpt": "1. 阿司匹林肠溶片 100 mg qd 口服（2025-03-02起）",
        "context": "既往用药史：阿司匹林",
        "page": dict(_PAGE),
    }
    payload.update(overrides)
    return MedicationObservation.model_validate(payload)


def make_extraction(observation_id="obs-a", **overrides):
    payload = {
        "observation_id": observation_id,
        "observation_use": dict(USE),
        "drug_name": dict(DRUG),
        "dose": {"value": "100mg", "source_quote": "100mg"},
        "frequency": {"value": "qd", "source_quote": "qd"},
        "route": {"value": "口服", "source_quote": "口服"},
        "times": [{"value": "2025-03-02", "source_quote": "2025-03-02起",
                   "role": "use_start", "precision": "day"}],
        "ongoing": dict(NULL),
        "administration_count": dict(NULL),
    }
    payload.update(overrides)
    return MedicationComponentExtraction.model_validate(payload)


def matching_pair():
    a = validate_extraction(make_extraction(), make_observation())
    b = validate_extraction(
        make_extraction(
            "obs-b",
            observation_use=dict(USE_B),
            dose={"value": "100 mg", "source_quote": "100 mg"},
        ),
        make_paired_observation(),
    )
    return a, b


def test_matching_medication_fields_agree_per_component():
    a, b = matching_pair()
    result = compare_component_outputs(a, b)
    components = result["components"]
    assert components["drug_name"]["status"] == "agree"
    assert components["drug_name"]["a_completeness"] == "complete"
    assert components["dose"]["status"] == "agree"
    assert components["frequency"]["status"] == "agree"
    assert components["route"]["status"] == "agree"
    assert components["ongoing"]["status"] == "missing"
    assert [(row["role"], row["status"]) for row in result["times"]] == [("use_start", "agree")]
    assert a.lane == "main-A" and a.page_review_id == "pr-a"
    assert b.lane == "main-B" and b.page_review_id == "pr-b"


def test_missing_batch_observation_is_not_silently_dropped():
    batch = MedicationExtractionBatch(experiment_version=EXPERIMENT_VERSION, items=[])
    with pytest.raises(ValueError, match="未返回"):
        validate_extraction_batch(batch, [make_observation()])


def test_adjacent_drug_substring_is_only_bound_not_clinically_accepted():
    observation = make_observation(raw_value="药甲100mg", excerpt="药甲100mg；药乙200mg")
    extraction = make_extraction(
        observation_use=use_of("药甲100mg"),
        drug_name={"value": "药甲", "source_quote": "药甲", "completeness": "fragment"},
        dose={"value": "200mg", "source_quote": "药乙200mg"},
        frequency=dict(NULL), route=dict(NULL), times=[],
        ongoing=dict(NULL), administration_count=dict(NULL),
    )
    result = validate_extraction(extraction, observation)
    assert result.dose.value == "200mg"  # binding succeeds; ownership is NOT proven
    assert result.source_qc_required is True
    assert result.product_acceptance is False


def test_one_sided_missing_time_is_never_borrowed():
    a = validate_extraction(make_extraction(), make_observation())
    b = validate_extraction(
        make_extraction("obs-b", observation_use=use_of("阿司匹林肠溶片 100mg"),
                        times=[], frequency=dict(NULL)),
        make_paired_observation(raw_value="阿司匹林肠溶片 100mg",
                                excerpt="1. 阿司匹林肠溶片 100mg 口服"),
    )
    rows = compare_component_outputs(a, b)["times"]
    assert rows == [{"role": "use_start", "status": "missing",
                     "a_values": [{"value": "2025-03-02", "precision": "day"}],
                     "b_values": []}]


def test_both_sides_missing_time_stays_missing():
    a = validate_extraction(make_extraction(times=[]), make_observation())
    b = validate_extraction(
        make_extraction("obs-b", observation_use=use_of("阿司匹林肠溶片 100mg"),
                        times=[], frequency=dict(NULL)),
        make_paired_observation(raw_value="阿司匹林肠溶片 100mg",
                                excerpt="1. 阿司匹林肠溶片 100mg 口服"),
    )
    assert compare_component_outputs(a, b)["times"] == []


def dose_only_bound(value, observation_id="obs-a", page_review_id="pr-a", lane="main-A"):
    extraction = make_extraction(
        observation_id,
        observation_use=use_of(f"药X {value}"),
        drug_name={"value": None, "source_quote": None, "completeness": "absent"},
        dose={"value": value, "source_quote": value},
        frequency=dict(NULL), route=dict(NULL), times=[],
        ongoing=dict(NULL), administration_count=dict(NULL),
    )
    observation = make_observation(
        observation_id=observation_id, page_review_id=page_review_id, lane=lane,
        raw_value=f"药X {value}", excerpt=f"0. 药X {value} qd",
    )
    return validate_extraction(extraction, observation)


@pytest.mark.parametrize(("a_dose", "b_dose", "expected"), [
    ("100mg", "100 mg", "agree"),
    ("1g", "1000mg", "conflict"),
    ("100mg", "100", "conflict"),
    ("2片", "2", "conflict"),
])
def test_dose_units_are_never_dropped_or_converted(a_dose, b_dose, expected):
    a = dose_only_bound(a_dose)
    b = dose_only_bound(b_dose, observation_id="obs-b", page_review_id="pr-b",
                        lane="main-B")
    assert compare_component_outputs(a, b)["components"]["dose"]["status"] == expected


def test_unknown_and_duplicate_ids_are_rejected():
    with pytest.raises(ValueError, match="未知观察ID"):
        validate_extraction(make_extraction("obs-other"), make_observation())
    observations = [make_observation(), make_paired_observation()]
    doubled = MedicationExtractionBatch.model_validate({
        "experiment_version": EXPERIMENT_VERSION,
        "items": [make_extraction().model_dump(), make_extraction().model_dump()],
    })
    with pytest.raises(ValueError, match="重复输出"):
        validate_extraction_batch(doubled, observations)
    unknown = MedicationExtractionBatch.model_validate({
        "experiment_version": EXPERIMENT_VERSION,
        "items": [make_extraction("obs-z").model_dump()],
    })
    with pytest.raises(ValueError, match="未知观察ID"):
        validate_extraction_batch(unknown, observations)
    with pytest.raises(ValueError, match="观察ID重复"):
        validate_extraction_batch(
            MedicationExtractionBatch.model_validate(
                {"experiment_version": EXPERIMENT_VERSION, "items": []}
            ),
            [make_observation(), make_observation()],
        )


def test_foreign_quote_from_other_observation_is_rejected():
    other = make_paired_observation(raw_value="苯磺酸氨氯地平片 5mg",
                                    excerpt="3. 苯磺酸氨氯地平片 5mg qd 口服")
    borrowed = make_extraction(
        drug_name={"value": "苯磺酸氨氯地平片", "source_quote": "苯磺酸氨氯地平片",
                   "completeness": "complete"}
    )
    with pytest.raises(ValueError, match="精确子串"):
        validate_extraction(borrowed, make_observation())
    assert other.raw_value  # the foreign text itself stays untouched and unused


def test_context_only_quote_is_rejected():
    with pytest.raises(ValueError, match="精确子串"):
        validate_extraction(
            make_extraction(drug_name={"value": "阿司匹林", "source_quote": "既往用药史",
                                       "completeness": "fragment"}),
            make_observation(),
        )


def test_paraphrased_value_is_rejected():
    with pytest.raises(ValueError, match="原文文本"):
        validate_extraction(
            make_extraction(drug_name={"value": "拜阿司匹灵", "source_quote": "阿司匹林肠溶片",
                                       "completeness": "fragment"}),
            make_observation(),
        )


def test_component_keys_are_required_even_when_absent():
    payload = make_extraction().model_dump()
    del payload["route"]
    with pytest.raises(ValidationError):
        MedicationComponentExtraction.model_validate(payload)
    payload = make_extraction().model_dump()
    del payload["dose"]["source_quote"]
    with pytest.raises(ValidationError):
        MedicationComponentExtraction.model_validate(payload)
    payload = make_extraction().model_dump()
    del payload["times"]
    with pytest.raises(ValidationError):
        MedicationComponentExtraction.model_validate(payload)
    payload = make_extraction().model_dump()
    del payload["times"][0]["precision"]
    with pytest.raises(ValidationError):
        MedicationComponentExtraction.model_validate(payload)
    payload = make_extraction().model_dump()
    del payload["administration_count"]
    with pytest.raises(ValidationError):
        MedicationComponentExtraction.model_validate(payload)


def test_extra_fields_are_refused():
    payload = make_extraction().model_dump()
    payload["notes"] = "似乎可以采信"
    with pytest.raises(ValidationError):
        MedicationComponentExtraction.model_validate(payload)
    payload = make_extraction().model_dump()
    payload["dose"]["confidence"] = 0.9
    with pytest.raises(ValidationError):
        MedicationComponentExtraction.model_validate(payload)
    payload = make_extraction().model_dump()
    payload["times"][0]["certainty"] = "high"
    with pytest.raises(ValidationError):
        MedicationComponentExtraction.model_validate(payload)
    with pytest.raises(ValidationError):
        MedicationObservation.model_validate(
            {**make_observation().model_dump(), "reader": "main-B"}
        )


def test_component_pairing_time_items_and_completeness_rules():
    with pytest.raises(ValidationError):
        make_extraction(dose={"value": "100mg", "source_quote": None})
    with pytest.raises(ValidationError):
        make_extraction(times=[{"value": None, "source_quote": None,
                                "role": "use_start", "precision": "day"}])
    with pytest.raises(ValidationError):
        make_extraction(times=[{"value": "2025-03-02", "source_quote": "2025-03-02起",
                                "role": "use_start"}])
    with pytest.raises(ValidationError):
        make_extraction(times=[{"value": "2025-03-02", "source_quote": "2025-03-02起",
                                "role": "encounter_date", "precision": "day"}])
    with pytest.raises(ValidationError):
        make_extraction(times=[{"value": "2025-03-02", "source_quote": "2025-03-02起",
                                "role": "use_start", "precision": "unknown"}])
    with pytest.raises(ValidationError):
        make_extraction(drug_name={"value": None, "source_quote": None,
                                   "completeness": "complete"})
    with pytest.raises(ValidationError):
        make_extraction(drug_name={"value": "阿司匹林肠溶片", "source_quote": "阿司匹林肠溶片",
                                   "completeness": "absent"})


def time_bound(item, raw, excerpt, observation_id="obs-a", **observation_overrides):
    observation = make_observation(raw_value=raw, excerpt=excerpt,
                                   observation_id=observation_id,
                                   **observation_overrides)
    extraction = make_extraction(
        observation_id,
        observation_use=use_of(raw),
        drug_name={"value": None, "source_quote": None, "completeness": "absent"},
        dose=dict(NULL), frequency=dict(NULL), route=dict(NULL),
        times=[item], ongoing=dict(NULL), administration_count=dict(NULL),
    )
    return validate_extraction(extraction, observation)


def test_fragment_drug_name_match_is_unresolved_never_agree():
    fragment = {"value": "阿司匹林", "source_quote": "阿司匹林", "completeness": "fragment"}
    a = validate_extraction(make_extraction(drug_name=dict(fragment)), make_observation())
    b = validate_extraction(
        make_extraction("obs-b", observation_use=dict(USE_B), drug_name=dict(fragment),
                        dose={"value": "100 mg", "source_quote": "100 mg"}),
        make_paired_observation(),
    )
    row = compare_component_outputs(a, b)["components"]["drug_name"]
    assert row == {"status": "unresolved", "a_value": "阿司匹林", "b_value": "阿司匹林",
                   "a_completeness": "fragment", "b_completeness": "fragment"}


def test_complete_vs_fragment_disagreement_is_unresolved():
    fragment = {"value": "阿司匹林肠溶片", "source_quote": "阿司匹林肠溶片",
                "completeness": "fragment"}
    a = validate_extraction(make_extraction(), make_observation())
    b = validate_extraction(
        make_extraction("obs-b", observation_use=dict(USE_B), drug_name=dict(fragment),
                        dose={"value": "100 mg", "source_quote": "100 mg"}),
        make_paired_observation(),
    )
    row = compare_component_outputs(a, b)["components"]["drug_name"]
    assert row["status"] == "unresolved"


def test_different_time_roles_stay_separate_and_explicit():
    a = validate_extraction(make_extraction(), make_observation())
    b = validate_extraction(
        make_extraction(
            "obs-b",
            observation_use=use_of("处方：阿司匹林肠溶片 100mg qd（2025-03-02起）",
                                   value="prescription"),
            route=dict(NULL),
            times=[{"value": "2025-03-02", "source_quote": "2025-03-02起",
                    "role": "prescription_date", "precision": "day"}],
        ),
        make_paired_observation(raw_value="处方：阿司匹林肠溶片 100mg qd（2025-03-02起）",
                                excerpt="2. 处方：阿司匹林肠溶片 100mg qd（2025-03-02起）"),
    )
    rows = compare_component_outputs(a, b)["times"]
    assert {row["role"]: row["status"] for row in rows} == {
        "use_start": "missing",
        "prescription_date": "missing",
    }
    assert all(row["status"] != "agree" for row in rows)


def interval_bound(times, observation_id="obs-a", **observation_overrides):
    payload = {
        "raw_value": "药X 2025-03-02至2025-03-15 用药",
        "excerpt": "0. 药X 2025-03-02至2025-03-15 用药",
        "observation_id": observation_id,
    }
    payload.update(observation_overrides)
    observation = make_observation(**payload)
    extraction = make_extraction(
        observation_id,
        observation_use=use_of(observation.raw_value),
        drug_name={"value": None, "source_quote": None, "completeness": "absent"},
        dose=dict(NULL), frequency=dict(NULL), route=dict(NULL),
        times=times, ongoing=dict(NULL), administration_count=dict(NULL),
    )
    return validate_extraction(extraction, observation)


def test_matching_start_and_end_agree_per_role():
    a = interval_bound([dict(START), dict(END)])
    b = interval_bound(
        [dict(START), dict(END)],
        observation_id="obs-b", page_review_id="pr-b", lane="main-B",
        excerpt="1. 药X 2025-03-02至2025-03-15 用药",
    )
    rows = compare_component_outputs(a, b)["times"]
    assert [(row["role"], row["status"]) for row in rows] == [
        ("use_end", "agree"), ("use_start", "agree"),
    ]


def test_swapped_start_end_order_stays_conflict_per_role():
    a = interval_bound([dict(START), dict(END)])
    b = interval_bound(
        [
            {"value": "2025-03-15", "source_quote": "2025-03-15",
             "role": "use_start", "precision": "day"},
            {"value": "2025-03-02", "source_quote": "2025-03-02",
             "role": "use_end", "precision": "day"},
        ],
        observation_id="obs-b", page_review_id="pr-b", lane="main-B",
        excerpt="1. 药X 2025-03-02至2025-03-15 用药",
    )
    rows = compare_component_outputs(a, b)["times"]
    assert {row["role"] for row in rows} == {"use_start", "use_end"}
    assert all(row["status"] == "conflict" for row in rows)


def test_explicit_interval_quote_must_be_split_into_two_items():
    whole = {"value": "2025-03-02至2025-03-15", "source_quote": "2025-03-02至2025-03-15",
             "role": "use_start", "precision": "day"}
    with pytest.raises(ValueError, match="拆分"):
        interval_bound([whole])


@pytest.mark.parametrize("value", ["2025.7.18-2025.7.23", "2025-03-02–2025-03-15", "7.18-7.23",
                                   "自2025.7.18至2025.7.23使用", "用药7.18-7.23结束"])
def test_hyphen_ranges_cannot_be_single_start_dates(value):
    item = {"value": value, "source_quote": value, "role": "use_start", "precision": "day"}
    with pytest.raises(ValueError, match="拆分"):
        interval_bound([item], raw_value=value, excerpt=value)


def test_single_iso_date_with_wider_interval_quote_is_valid():
    item = {**START, "source_quote": "2025-03-02至2025-03-15"}
    assert interval_bound([item]).times[0].value == "2025-03-02"


@pytest.mark.parametrize("value", ["2025.4.31", "2025.02.30", "2023.13.01", "2023.13.uk"])
def test_matching_impossible_dates_are_unresolved(value):
    item = {"value": value, "source_quote": value, "role": "use_start", "precision": "day"}
    a = interval_bound([item], raw_value=value, excerpt=value)
    b = interval_bound([item], observation_id="obs-b", page_review_id="pr-b", lane="main-B",
                       raw_value=value, excerpt=value)
    row = compare_component_outputs(a, b)["times"][0]
    assert row["status"] == "unresolved"
    assert row["qc_flags"] == ["invalid_date"]


def test_date_omission_hint_does_not_fill_date_or_prove_ownership():
    result = interval_bound([], raw_value="药甲；药乙2023.UK.UK", excerpt="药甲；药乙2023.UK.UK")
    assert result.times == []
    assert result.qc_flags == ["possible_unextracted_time"]
    assert result.product_acceptance is False
    assert interval_bound([], raw_value="药甲", excerpt="药甲").qc_flags == []


def time_pair(item_a, item_b):
    a = time_bound(item_a, "药X 2025-03 开始", "0. 药X 2025-03 开始")
    b = time_bound(item_b, "药X 2025-03 开始", "1. 药X 2025-03 开始",
                   observation_id="obs-b", page_review_id="pr-b", lane="main-B")
    return compare_component_outputs(a, b)["times"]


def test_precision_difference_is_unresolved_not_a_source_value_conflict():
    month = {"value": "2025-03", "source_quote": "2025-03", "role": "use_start",
             "precision": "month"}
    unclear = {**month, "precision": "unclear"}
    rows = time_pair(month, unclear)
    assert rows == [{"role": "use_start", "status": "unresolved",
                     "reason": "precision_interpretation_disagreement",
                     "a_values": [{"value": "2025-03", "precision": "month"}],
                     "b_values": [{"value": "2025-03", "precision": "unclear"}]}]


def test_partial_dates_are_kept_verbatim():
    bound = time_bound(
        {"value": "3月2日", "source_quote": "3月2日", "role": "unclear",
         "precision": "partial"},
        "药X 3月2日", "0. 药X 3月2日 用药",
    )
    assert bound.times[0].value == "3月2日"
    assert bound.times[0].precision == "partial"
    assert bound.source_qc_required is True


def test_matching_unclear_time_is_unresolved_not_agree():
    item = {"value": "3月2日", "source_quote": "3月2日", "role": "unclear",
            "precision": "unclear"}
    a = time_bound(item, "药X 3月2日", "0. 药X 3月2日 用药")
    b = time_bound(item, "药X 3月2日", "1. 药X 3月2日 用药",
                   observation_id="obs-b", page_review_id="pr-b", lane="main-B")
    rows = compare_component_outputs(a, b)["times"]
    assert rows == [{"role": "unclear", "status": "unresolved",
                     "a_values": [{"value": "3月2日", "precision": "unclear"}],
                     "b_values": [{"value": "3月2日", "precision": "unclear"}]}]


def test_administration_count_is_separate_from_frequency():
    a = validate_extraction(
        make_extraction(observation_use=use_of("阿司匹林肠溶片 100mg 1次"),
                        frequency=dict(NULL), times=[],
                        administration_count={"value": "1次", "source_quote": "1次"}),
        make_observation(raw_value="阿司匹林肠溶片 100mg 1次",
                         excerpt="0. 阿司匹林肠溶片 100mg 1次 口服"),
    )
    b = validate_extraction(
        make_extraction("obs-b", observation_use=use_of("阿司匹林肠溶片 100mg 1次"),
                        frequency=dict(NULL), times=[],
                        administration_count={"value": "1次", "source_quote": "1次"}),
        make_paired_observation(raw_value="阿司匹林肠溶片 100mg 1次",
                                excerpt="1. 阿司匹林肠溶片 100mg 1次 口服"),
    )
    components = compare_component_outputs(a, b)["components"]
    assert components["frequency"]["status"] == "missing"
    assert components["administration_count"]["status"] == "agree"


def test_prompt_carries_only_its_own_observation_verbatim():
    a = make_observation()
    b = make_observation(observation_id="obs-b", page_review_id="pr-b", lane="main-B",
                         raw_value="苯磺酸氨氯地平片 5mg qd",
                         excerpt="3. 苯磺酸氨氯地平片 5mg qd 口服",
                         context="血压用药史：氨氯地平")
    prompt_a = build_component_prompt(a)
    system_a = prompt_a[0]["content"]
    user_a = prompt_a[1]["content"]
    assert a.raw_value in user_a and a.excerpt in user_a and a.context in user_a
    assert b.raw_value not in user_a and b.excerpt not in user_a
    assert b.observation_id not in user_a and b.context not in user_a
    payload = json.loads(user_a)
    assert payload["experiment_version"] == EXPERIMENT_VERSION
    assert payload["observation"]["page_review_id"] == "pr-a"
    assert payload["observation"]["lane"] == "main-A"
    assert "实例形状" in system_a and INSTANCE_SHAPE in system_a
    assert "不得输出 $defs" in system_a
    assert '"$defs":' not in system_a and '"type"' not in system_a
    assert '"required"' not in system_a and '"properties"' not in system_a
    assert "剂型" in system_a
    assert "阿司匹林" not in system_a  # no real-data example or gold answer in the prompt
    # v5: the prompt must first classify purpose, never presuppose a medication record.
    assert "不要预设它一定是用药记录" in system_a
    assert "observation_use" in system_a
    for kind in ("use", "prescription", "purchase", "explicitly_no_medication",
                 "non_medication", "unclear"):
        assert kind in system_a
    assert "整条拒收" in system_a
    assert "不得删除/次" in system_a
    assert "仅缺剂型不算 fragment" in system_a
    assert "不得展开或猜测缩写" in system_a
    assert "只有原文明确各端点含义时才拆分" in system_a
    assert "借用其他观察的日期" in system_a
    assert "未知月份或日期不等于起止用途未知" in system_a
    assert "字段标题及冒号即使含『每次』也不属于分项值" in system_a
    assert INSTANCE_SHAPE.index("observation_use") < INSTANCE_SHAPE.index("drug_name")


def test_quote_binding_tolerates_whitespace_but_keeps_unit_string():
    observation = make_observation(
        raw_value="阿司匹林肠溶片 100 mg", excerpt="0. 阿司匹林肠溶片 100 mg qd"
    )
    bound = validate_extraction(
        make_extraction(
            observation_use=use_of("阿司匹林肠溶片 100 mg"),
            dose={"value": "100mg", "source_quote": "100 mg"},
            route=dict(NULL), times=[], ongoing=dict(NULL),
            administration_count=dict(NULL),
        ),
        observation,
    )
    assert bound.dose.value == "100mg"
    assert bound.dose.source_quote == "100 mg"


def test_comparison_requires_same_source_page():
    a = validate_extraction(make_extraction(), make_observation())
    b = validate_extraction(
        make_extraction("obs-b", observation_use=dict(USE_B),
                        dose={"value": "100 mg", "source_quote": "100 mg"}),
        make_paired_observation(page={**_PAGE, "page_number": 4}),
    )
    with pytest.raises(ValueError, match="同一来源页"):
        compare_component_outputs(a, b)


def test_comparison_rejects_same_lane():
    a = validate_extraction(make_extraction(), make_observation())
    b = validate_extraction(
        make_extraction("obs-b", observation_use=use_of("阿司匹林肠溶片 100mg"),
                        times=[], frequency=dict(NULL)),
        make_paired_observation(lane="main-A", raw_value="阿司匹林肠溶片 100mg",
                                excerpt="1. 阿司匹林肠溶片 100mg 口服"),
    )
    with pytest.raises(ValueError, match="不同读道"):
        compare_component_outputs(a, b)


def test_comparison_rejects_same_page_review_record():
    a = validate_extraction(make_extraction(), make_observation())
    b = validate_extraction(
        make_extraction("obs-b", observation_use=dict(USE_B),
                        dose={"value": "100 mg", "source_quote": "100 mg"}),
        make_paired_observation(page_review_id="pr-a"),
    )
    with pytest.raises(ValueError, match="页审核记录"):
        compare_component_outputs(a, b)


def test_batch_requires_matching_experiment_version():
    with pytest.raises(ValidationError):
        MedicationExtractionBatch.model_validate(
            {"experiment_version": "medication-component/v1", "items": []}
        )
    with pytest.raises(ValidationError):
        MedicationExtractionBatch.model_validate(
            {"experiment_version": "medication-component/v4", "items": []}
        )


def test_outputs_are_never_accepted_clinical_facts():
    a, b = matching_pair()
    result = compare_component_outputs(a, b)
    assert a.product_acceptance is False and a.source_qc_required is True
    assert result["product_acceptance"] is False and result["source_qc_required"] is True
    assert result["pairing_verified"] is False
    with pytest.raises(ValidationError):
        BoundComponentExtraction.model_validate(
            {**a.model_dump(), "product_acceptance": True}
        )
    with pytest.raises(ValidationError):
        BoundComponentExtraction.model_validate(
            {**a.model_dump(), "source_qc_required": False}
        )


# --- v5: purpose classification, purpose-conditional validation, reconciliation ---


def test_observation_use_is_required_enum_with_own_source_quote():
    payload = make_extraction().model_dump()
    del payload["observation_use"]
    with pytest.raises(ValidationError):
        MedicationComponentExtraction.model_validate(payload)
    with pytest.raises(ValidationError):
        make_extraction(observation_use={"value": "taken", "source_quote": "阿司匹林肠溶片 100mg qd"})
    with pytest.raises(ValidationError):
        make_extraction(observation_use={"value": "use", "source_quote": "   "})
    with pytest.raises(ValueError, match="精确子串"):
        validate_extraction(
            make_extraction(observation_use={"value": "use", "source_quote": "苯磺酸氨氯地平片"}),
            make_observation(),
        )
    bound = validate_extraction(make_extraction(), make_observation())
    assert bound.observation_use.value == "use"
    assert bound.observation_use.source_quote == "阿司匹林肠溶片 100mg qd"


def no_use_extraction(kind, quote):
    return make_extraction(
        observation_use={"value": kind, "source_quote": quote},
        drug_name={"value": None, "source_quote": None, "completeness": "absent"},
        dose=dict(NULL), frequency=dict(NULL), route=dict(NULL), times=[],
        ongoing=dict(NULL), administration_count=dict(NULL),
    )


NO_USE_RAW = "未服阿司匹林。高血压病史（2023年确诊）"


def no_use_observation(**overrides):
    payload = {"raw_value": NO_USE_RAW, "excerpt": f"0. {NO_USE_RAW}", "context": None}
    payload.update(overrides)
    return make_observation(**payload)


def test_negative_history_with_dates_keeps_components_empty_and_skips_date_hint():
    quote = "未服阿司匹林"
    a = validate_extraction(no_use_extraction("explicitly_no_medication", quote),
                            no_use_observation())
    assert a.drug_name.value is None and a.drug_name.completeness == "absent"
    assert a.times == []
    for name in ("dose", "frequency", "route", "ongoing", "administration_count"):
        assert getattr(a, name).value is None
    # The date hint (2023年) must not fire for a disease-only non-use record.
    assert a.qc_flags == []
    b = validate_extraction(no_use_extraction("explicitly_no_medication", quote),
                            no_use_observation(page_review_id="pr-b", lane="main-B",
                                               excerpt="1. " + NO_USE_RAW))
    result = compare_component_outputs(a, b)
    assert result["observation_use"] == {"a_value": "explicitly_no_medication",
                                         "b_value": "explicitly_no_medication",
                                         "status": "agree"}
    assert all(row["status"] == "missing" for row in result["components"].values())
    assert result["times"] == []
    assert result["product_acceptance"] is False


def test_inconsistent_no_use_output_is_rejected_not_silently_erased():
    observation = no_use_observation()
    with pytest.raises(ValueError, match="拒收"):
        validate_extraction(make_extraction(
            observation_use={"value": "explicitly_no_medication", "source_quote": "未服阿司匹林"},
        ), observation)
    with pytest.raises(ValueError, match="拒收"):
        validate_extraction(make_extraction(
            observation_use={"value": "non_medication", "source_quote": "未服阿司匹林"},
            drug_name={"value": None, "source_quote": None, "completeness": "absent"},
            dose=dict(NULL), frequency=dict(NULL), route=dict(NULL),
            times=[dict(START)], ongoing=dict(NULL), administration_count=dict(NULL),
        ), observation)
    with pytest.raises(ValueError, match="拒收"):
        validate_extraction(make_extraction(
            observation_use={"value": "non_medication", "source_quote": "未服阿司匹林"},
            drug_name={"value": None, "source_quote": None, "completeness": "absent"},
            dose=dict(NULL), frequency=dict(NULL), route=dict(NULL), times=[],
            ongoing={"value": "长期", "source_quote": "长期"},
            administration_count=dict(NULL),
        ), observation)


PURCHASE_RAW = "自购：布洛芬缓释胶囊 1盒（2025-03-02购买）"


def purchase_observation(**overrides):
    payload = {"raw_value": PURCHASE_RAW, "excerpt": f"0. {PURCHASE_RAW}", "context": None}
    payload.update(overrides)
    return make_observation(**payload)


def purchase_extraction(observation_id="obs-a", **overrides):
    payload = {
        "observation_id": observation_id,
        "observation_use": {"value": "purchase", "source_quote": "自购"},
        "drug_name": {"value": "布洛芬缓释胶囊", "source_quote": "布洛芬缓释胶囊",
                      "completeness": "complete"},
        "dose": dict(NULL), "frequency": dict(NULL), "route": dict(NULL), "times": [],
        "ongoing": dict(NULL), "administration_count": dict(NULL),
    }
    payload.update(overrides)
    return make_extraction(**payload)


def test_purchase_preserves_item_identity_but_not_exposure_details():
    bound = validate_extraction(purchase_extraction(), purchase_observation())
    assert bound.drug_name.value == "布洛芬缓释胶囊"
    assert bound.observation_use.value == "purchase"
    for component_overrides in (
        {"dose": {"value": "1盒", "source_quote": "1盒"}},
        {"frequency": {"value": "每日", "source_quote": "每日"}},
        {"route": {"value": "口服", "source_quote": "口服"}},
        {"ongoing": {"value": "长期", "source_quote": "长期"}},
        {"administration_count": {"value": "1次", "source_quote": "1次"}},
        {"times": [dict(START)]},
        {"times": [{"value": "2025-03-02", "source_quote": "2025-03-02购买",
                    "role": "use_end", "precision": "day"}]},
    ):
        with pytest.raises(ValueError, match="purchase"):
            validate_extraction(purchase_extraction(**component_overrides),
                                purchase_observation())
    for role in ("unclear", "prescription_date"):
        with pytest.raises(ValueError, match="purchase"):
            validate_extraction(purchase_extraction(times=[
                {"value": "2025-03-02", "source_quote": "2025-03-02购买",
                 "role": role, "precision": "day"},
            ]), purchase_observation())


def test_purchase_exposure_pair_never_reads_as_verified_agreement():
    same_raw = "自购：阿司匹林肠溶片 1盒（2025-03-02购买）"
    a = validate_extraction(make_extraction(), make_observation())
    b = validate_extraction(purchase_extraction(
        "obs-b",
        drug_name={"value": "阿司匹林肠溶片", "source_quote": "阿司匹林肠溶片",
                   "completeness": "complete"},
    ), make_observation(observation_id="obs-b", page_review_id="pr-b", lane="main-B",
                        raw_value=same_raw, excerpt=f"1. {same_raw}"))
    result = compare_component_outputs(a, b)
    assert result["observation_use"] == {"a_value": "use", "b_value": "purchase",
                                         "status": "conflict"}
    # Identical complete drug text is demoted: a purchase is not exposure evidence.
    drug = result["components"]["drug_name"]
    assert drug["status"] == "unresolved"
    assert drug["a_value"] == drug["b_value"] == "阿司匹林肠溶片"  # values retained
    assert result["components"]["dose"]["status"] == "missing"
    assert result["pairing_verified"] is False and result["product_acceptance"] is False
    assert result["source_qc_required"] is True


def test_unknown_drug_name_does_not_erase_real_use_regimen_or_time():
    a = validate_extraction(make_extraction(
        observation_use={"value": "use", "source_quote": "药名不详"},
        drug_name={"value": None, "source_quote": None, "completeness": "absent"},
        dose={"value": "100mg", "source_quote": "100mg"},
        frequency={"value": "qd", "source_quote": "qd"},
        route=dict(NULL),
        times=[{"value": "2025-03-02", "source_quote": "2025-03-02起",
                "role": "use_start", "precision": "day"}],
        ongoing=dict(NULL), administration_count=dict(NULL),
    ), make_observation(raw_value="药名不详 100mg qd（2025-03-02起）",
                        excerpt="0. 药名不详 100mg qd（2025-03-02起）"))
    b = validate_extraction(make_extraction(
        "obs-b",
        observation_use={"value": "use", "source_quote": "药名不详"},
        drug_name={"value": None, "source_quote": None, "completeness": "absent"},
        dose={"value": "100 mg", "source_quote": "100 mg"},
        frequency={"value": "qd", "source_quote": "qd"},
        route=dict(NULL),
        times=[{"value": "2025-03-02", "source_quote": "2025-03-02起",
                "role": "use_start", "precision": "day"}],
        ongoing=dict(NULL), administration_count=dict(NULL),
    ), make_paired_observation(raw_value="药名不详 100 mg qd（2025-03-02起）",
                               excerpt="1. 药名不详 100 mg qd（2025-03-02起）"))
    result = compare_component_outputs(a, b)
    assert result["observation_use"]["status"] == "agree"
    assert result["components"]["drug_name"]["status"] == "missing"
    assert result["components"]["dose"]["status"] == "agree"
    assert result["components"]["frequency"]["status"] == "agree"
    assert result["times"][0]["status"] == "agree"
    # A verbatim uncertain designation is preserved without expanding abbreviations.
    designated = validate_extraction(make_extraction(
        observation_use={"value": "use", "source_quote": "药名不详"},
        drug_name={"value": "药名不详", "source_quote": "药名不详", "completeness": "uncertain"},
        dose=dict(NULL), frequency=dict(NULL), route=dict(NULL), times=[],
        ongoing=dict(NULL), administration_count=dict(NULL),
    ), make_observation(raw_value="药名不详 100mg qd（2025-03-02起）",
                        excerpt="0. 药名不详 100mg qd（2025-03-02起）"))
    assert designated.drug_name.value == "药名不详"
    assert designated.drug_name.completeness == "uncertain"


def test_unclear_purpose_on_both_sides_gates_agreement_to_unresolved():
    a = validate_extraction(
        make_extraction(observation_use={"value": "unclear", "source_quote": "阿司匹林肠溶片 100mg qd"}),
        make_observation(),
    )
    b = validate_extraction(
        make_extraction("obs-b", observation_use={"value": "unclear",
                                                  "source_quote": "阿司匹林肠溶片 100 mg qd"},
                        dose={"value": "100 mg", "source_quote": "100 mg"}),
        make_paired_observation(),
    )
    result = compare_component_outputs(a, b)
    assert result["observation_use"] == {"a_value": "unclear", "b_value": "unclear",
                                         "status": "unresolved"}
    assert result["components"]["drug_name"]["status"] == "unresolved"
    assert result["components"]["dose"]["status"] == "unresolved"
    assert result["components"]["dose"]["a_value"] == "100mg"  # extracted values retained
    assert all(row["status"] == "unresolved" for row in result["times"])
    assert result["product_acceptance"] is False and result["source_qc_required"] is True


@pytest.mark.parametrize("value", ["2023.uk.uk-2024.1.2", "2025.uk-2025.03",
                                   "2023.UK.UK至2024.01.02"])
def test_uk_endpoint_ranges_cannot_be_labeled_single_concrete_dates(value):
    item = {"value": value, "source_quote": value, "role": "use_start",
            "precision": "partial"}
    with pytest.raises(ValueError, match="拆分"):
        interval_bound([item], raw_value=value, excerpt=value)


def test_single_partial_uk_date_is_preserved_verbatim_never_forced_to_start():
    bound = time_bound(
        {"value": "2023.uk.uk", "source_quote": "2023.uk.uk", "role": "unclear",
         "precision": "partial"},
        "药X 2023.uk.uk 开始", "0. 药X 2023.uk.uk 开始",
    )
    assert bound.times[0].value == "2023.uk.uk"
    assert bound.times[0].role == "unclear"
    assert bound.times[0].precision == "partial"
    item = {"value": "2023.uk.uk", "source_quote": "2023.uk.uk", "role": "unclear",
            "precision": "partial"}
    a = time_bound(item, "药X 2023.uk.uk 开始", "0. 药X 2023.uk.uk 开始")
    b = time_bound(item, "药X 2023.uk.uk 开始", "1. 药X 2023.uk.uk 开始",
                   observation_id="obs-b", page_review_id="pr-b", lane="main-B")
    rows = compare_component_outputs(a, b)["times"]
    assert rows[0]["status"] == "unresolved"


def test_intact_name_without_dosage_form_is_not_a_fragment():
    bound = validate_extraction(make_extraction(
        observation_use=use_of("阿司匹林 100mg"),
        drug_name={"value": "阿司匹林", "source_quote": "阿司匹林", "completeness": "complete"},
        dose={"value": "100mg", "source_quote": "100mg"},
        frequency=dict(NULL), route=dict(NULL), times=[],
        ongoing=dict(NULL), administration_count=dict(NULL),
    ), make_observation(raw_value="阿司匹林 100mg", excerpt="0. 阿司匹林 100mg 口服"))
    assert bound.drug_name.completeness == "complete"
    assert bound.drug_name.value == "阿司匹林"


def test_per_administration_denominator_stays_in_dose_value():
    raw = "每次 2片/次 口服"
    no_name = {"value": None, "source_quote": None, "completeness": "absent"}
    observation = make_observation(raw_value=raw, excerpt=f"0. {raw}")
    bound = validate_extraction(make_extraction(
        observation_use=use_of(raw),
        drug_name=dict(no_name),
        dose={"value": "2片/次", "source_quote": "2片/次"},
        frequency=dict(NULL), route={"value": "口服", "source_quote": "口服"}, times=[],
        ongoing=dict(NULL), administration_count=dict(NULL),
    ), observation)
    assert bound.dose.value == "2片/次"  # /次 and 每次 denominator never stripped
    a = bound
    b = validate_extraction(make_extraction(
        "obs-b",
        observation_use=use_of("每次 2片/次 口服"),
        drug_name=dict(no_name),
        dose={"value": "2片/次", "source_quote": "2片/次"},
        frequency=dict(NULL), route={"value": "口服", "source_quote": "口服"}, times=[],
        ongoing=dict(NULL), administration_count=dict(NULL),
    ), make_paired_observation(raw_value="每次 2片/次 口服",
                               excerpt="1. 每次 2片/次 口服"))
    stripped = validate_extraction(make_extraction(
        "obs-b",
        observation_use=use_of("每次 2片 口服"),
        drug_name=dict(no_name),
        dose={"value": "2片", "source_quote": "2片"},
        frequency=dict(NULL), route={"value": "口服", "source_quote": "口服"}, times=[],
        ongoing=dict(NULL), administration_count=dict(NULL),
    ), make_paired_observation(raw_value="每次 2片 口服", excerpt="1. 每次 2片 口服"))
    assert compare_component_outputs(a, b)["components"]["dose"]["status"] == "agree"
    assert compare_component_outputs(a, stripped)["components"]["dose"]["status"] == "conflict"


def test_date_hint_flags_only_use_prescription_or_unclear_purposes():
    purchase = validate_extraction(purchase_extraction(), purchase_observation())
    assert purchase.qc_flags == []  # purchase record: no unextracted-time hint
    use_extraction = make_extraction(
        observation_use={"value": "use", "source_quote": "布洛芬缓释胶囊"},
        drug_name={"value": "布洛芬缓释胶囊", "source_quote": "布洛芬缓释胶囊",
                   "completeness": "complete"},
        dose=dict(NULL), frequency=dict(NULL), route=dict(NULL), times=[],
        ongoing=dict(NULL), administration_count=dict(NULL),
    )
    flagged = validate_extraction(use_extraction, purchase_observation())
    assert flagged.qc_flags == ["possible_unextracted_time"]
    for kind in ("prescription", "unclear"):
        assert validate_extraction(make_extraction(
            observation_use={"value": kind, "source_quote": "布洛芬缓释胶囊"},
            drug_name={"value": "布洛芬缓释胶囊", "source_quote": "布洛芬缓释胶囊",
                       "completeness": "complete"},
            dose=dict(NULL), frequency=dict(NULL), route=dict(NULL), times=[],
            ongoing=dict(NULL), administration_count=dict(NULL),
        ), purchase_observation()).qc_flags == ["possible_unextracted_time"]


def test_prescription_purpose_keeps_regimen_without_asserting_use():
    raw = "处方：阿司匹林肠溶片 100mg qd（2025-03-02）"
    observation = make_observation(raw_value=raw, excerpt=f"2. {raw}")
    bound = validate_extraction(make_extraction(
        observation_use={"value": "prescription", "source_quote": "处方"},
        route=dict(NULL),
        times=[{"value": "2025-03-02", "source_quote": "（2025-03-02）",
                "role": "prescription_date", "precision": "day"}],
    ), observation)
    assert bound.observation_use.value == "prescription"
    assert bound.dose.value == "100mg"  # prescribed regimen preserved
    assert bound.times[0].role == "prescription_date"
    assert bound.source_qc_required is True
