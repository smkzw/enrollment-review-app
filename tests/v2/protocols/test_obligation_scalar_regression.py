"""Scalar and list conditions require the same source-binding evidence."""

import pytest

from app.domain.contracts.rules import AtomicPredicate
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
