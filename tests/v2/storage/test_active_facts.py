"""Current evidence selection must not depend on batch order or revive old values."""

from itertools import permutations

import pytest

from app.storage.active_facts import current_fact_heads
from app.storage.fact_correction_repository import FactCorrectionRepository
from app.storage.repositories import InvalidReferenceError
from tests.v2.storage.test_fact_repositories import _fact, _seed_chain


@pytest.fixture
def chain(session):
    return _seed_chain(session, "active-facts")


def test_batches_and_input_order_do_not_change_current_selection(chain, session):
    first = _fact(chain, fact_id="old-revision")
    head = _fact({**chain, "run_id": "later-run"}, fact_id="head", revision=2)
    other = _fact(chain, fact_id="another-observation", value="130/85")
    for ordered in permutations([first, head, other]):
        selected = current_fact_heads(session, first.authority, facts=ordered)
        assert {item.fact_id for item in selected} == {head.fact_id, other.fact_id}


def test_corrected_chain_head_does_not_revive_earlier_revision(chain, session, monkeypatch):
    first = _fact(chain, fact_id="historical")
    head = _fact(chain, fact_id="corrected-target", revision=2)
    correction = _fact(chain, fact_id="corrected-value", value="130/85")
    monkeypatch.setattr(
        FactCorrectionRepository, "superseded_entity_ids", lambda *_: {head.fact_id}
    )
    selected = current_fact_heads(
        session, first.authority, facts=[first, head, correction]
    )
    assert [item.fact_id for item in selected] == [correction.fact_id]


def test_explicit_exclusion_does_not_revive_earlier_revision(chain, session):
    first = _fact(chain, fact_id="historical")
    head = _fact(chain, fact_id="excluded-head", revision=2)
    assert current_fact_heads(
        session, first.authority, facts=[first, head], exclude_fact_ids={head.fact_id}
    ) == []


def test_other_authority_is_not_merged(chain, session):
    first = _fact(chain)
    other = first.model_copy(update={
        "fact_id": "other-episode",
        "authority": first.authority.model_copy(update={"review_episode_id": "other"}),
    })
    assert current_fact_heads(session, first.authority, facts=[other, first]) == [first]


def test_ambiguous_revision_is_rejected_not_chosen_by_order(chain, session):
    first = _fact(chain, fact_id="a")
    other = _fact(chain, fact_id="b")
    for ordered in permutations([first, other]):
        with pytest.raises(InvalidReferenceError, match="相同修订号"):
            current_fact_heads(session, first.authority, facts=ordered)
