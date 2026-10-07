"""Scalar and list conditions require the same source-binding evidence."""

import pytest

from app.domain.contracts.rules import AtomicPredicate, ProspectivePeriod
from app.domain.contracts.enums import ProtocolPeriod
from app.protocols.deconstruction_gate import _predicate_binds_obligation


def predicate(value, comparator, clauses):
    return AtomicPredicate(
        predicate_id='status', subject='participant', attribute='status',
        comparator=comparator, value=value, source_clauses=clauses,
    )


def test_list_value_binds_with_verbatim_source():
    assert _predicate_binds_obligation(
        predicate(['稳定期'], 'in', ['且处于稳定期']), '且处于稳定期')


def test_scalar_value_binds_with_verbatim_source():
    assert _predicate_binds_obligation(
        predicate('稳定期', 'eq', ['且处于稳定期']), '且处于稳定期')


@pytest.mark.parametrize('value,comparator', [('稳定期', 'eq'), (['稳定期'], 'in')])
def test_value_cannot_replace_missing_source(value, comparator):
    assert not _predicate_binds_obligation(
        predicate(value, comparator, []), '且处于稳定期')


@pytest.mark.parametrize('value,comparator', [('其他状态', 'eq'), (['其他状态'], 'in')])
def test_source_alone_cannot_replace_condition(value, comparator):
    assert not _predicate_binds_obligation(
        predicate(value, comparator, ['且处于稳定期']), '且处于稳定期')


@pytest.mark.parametrize('wide_quote', [False, True])
def test_shared_words_do_not_bind_a_different_object(wide_quote):
    clause = '存在或疑似情况甲'
    if wide_quote:
        clause += '；存在或疑似情况乙'
    item = AtomicPredicate(
        predicate_id='condition-a', subject='参与者', attribute='情况甲',
        comparator='exists', source_clauses=[clause],
        semantic_proposition='存在或疑似情况甲',
    )
    assert _predicate_binds_obligation(item, '存在或疑似情况甲')
    assert not _predicate_binds_obligation(item, '存在或疑似情况乙')


@pytest.mark.parametrize('clause,segment', [
    ('参与者存在情况甲；存在情况乙', '存在情况甲'),
    ('存在情况甲', '参与者存在情况甲'),
    (' condition A ', 'CONDITION A'),
])
def test_complete_locator_and_identity_accept_containment_and_layout(clause, segment):
    item = AtomicPredicate(
        predicate_id='condition-a', subject='参与者', attribute='情况甲' if '情况甲' in clause else 'condition A',
        comparator='exists', source_clauses=[clause],
    )
    assert _predicate_binds_obligation(item, segment)


def test_generic_identity_does_not_replace_a_missing_exact_locator():
    item = AtomicPredicate(
        predicate_id='generic', subject='参与者', attribute='存在',
        comparator='exists', source_clauses=['存在或疑似情况甲'],
    )
    assert not _predicate_binds_obligation(item, '存在或疑似情况乙')


@pytest.mark.parametrize('mutation', ['normal', 'other_action', 'wrong_period', 'two_periods', 'no_period'])
def test_exact_action_can_bind_across_only_its_single_retained_period(mutation):
    text = '计划在研究期间接受专项评估'
    if mutation == 'other_action':
        text = '计划在研究期间拒绝专项评估'
    elif mutation == 'two_periods':
        text = '计划在研究期间及治疗期间接受专项评估'
    item = AtomicPredicate(
        predicate_id='plan', subject='参与者', attribute='计划接受专项评估',
        comparator='exists', source_clauses=[text],
        prospective_period=ProspectivePeriod(period=(ProtocolPeriod.TREATMENT_PERIOD
            if mutation == 'wrong_period' else ProtocolPeriod.STUDY_PERIOD)),
    )
    if mutation == 'no_period':
        item.prospective_period = None
    assert _predicate_binds_obligation(item, text) is (mutation == 'normal')
