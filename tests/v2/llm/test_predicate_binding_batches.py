import json

import pytest

from app.llm.predicate_binding_batches import plan_binding_batches, project_binding_batch, validate_binding_batch
from app.llm.predicate_binding_candidates import predicate_binding_prompt_input, validate_predicate_candidates
from tests.v2.llm.test_predicate_binding_candidates import _case
from tests.v2.services.test_predicate_binding_input import _fact_record, _frozen_input, _locator_record, _sha


def _input():
    base, _ = _case()
    return _frozen_input(base.components,
        [_fact_record(f"fact-{n}", _sha(str(n)), [f"loc-{n}"]) for n in range(3)],
        [_locator_record(f"loc-{n}") for n in range(3)])


def test_batches_cover_every_fact_and_full_source_without_pruning():
    frozen = _input()
    prompt = predicate_binding_prompt_input(frozen)
    batches = plan_binding_batches(frozen, prompt, max_characters=100000)
    full_size = len(json.dumps(project_binding_batch(prompt, frozen, batches[0]), ensure_ascii=False, separators=(",", ":")))
    batches = plan_binding_batches(frozen, prompt, max_characters=full_size - 1)
    assert len(batches) > 1
    assert sorted(key for b in batches for key in b.fact_ids) == sorted(f.fact_id for f in frozen.facts)
    for batch in batches:
        part = project_binding_batch(prompt, frozen, batch)
        assert part["components"] == prompt["components"]
        assert part["episode"] == prompt["episode"]
        assert all(row in prompt["sources"]["rows"] for row in part["sources"]["rows"])
        assert len(json.dumps(part, ensure_ascii=False, separators=(",", ":"))) <= full_size - 1
        assert set(batch.locator_ids) == {key for fact in frozen.facts if fact.fact_id in batch.fact_ids for key in fact.locator_ids}


def test_cannot_use_a_fact_not_shown_in_this_batch():
    frozen = _input()
    prompt = predicate_binding_prompt_input(frozen)
    full = plan_binding_batches(frozen, prompt, max_characters=100000)[0]
    size = len(json.dumps(project_binding_batch(prompt, frozen, full), ensure_ascii=False, separators=(",", ":")))
    batch = plan_binding_batches(frozen, prompt, max_characters=size - 1)[0]
    absent = next(f for f in frozen.facts if f.fact_id not in batch.fact_ids)
    _, payload = _case()
    for item in payload["results"]:
        item["candidates"][0].update(fact_id=absent.fact_id, locator_id=absent.locator_ids[0])
    with pytest.raises(ValueError, match="本批"):
        validate_predicate_candidates(frozen, json.dumps(payload), batch=batch)


def test_batch_cannot_drop_source_or_truncate_oversized_content():
    frozen = _input()
    prompt = predicate_binding_prompt_input(frozen)
    batch = plan_binding_batches(frozen, prompt, max_characters=100000)[0]
    with pytest.raises(ValueError):
        validate_binding_batch(frozen, batch.model_copy(update={"locator_ids": []}))
    with pytest.raises(ValueError, match="不能截断"):
        plan_binding_batches(frozen, prompt, max_characters=1)


def test_batch_identity_is_independent_of_input_order():
    frozen = _input()
    shuffled = _frozen_input(list(reversed(frozen.components)), list(reversed(frozen.facts)), list(reversed(frozen.locators)))
    assert plan_binding_batches(frozen, predicate_binding_prompt_input(frozen), max_characters=100000) == plan_binding_batches(shuffled, predicate_binding_prompt_input(shuffled), max_characters=100000)
