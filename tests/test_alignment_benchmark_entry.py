import asyncio
from argparse import Namespace
import json

import pytest

from scripts.evaluate_observation_alignment import run
from scripts import evaluate_observation_alignment as entry


def test_low_budget_rejected_before_output_or_model_call(tmp_path):
    target = tmp_path / 'run'
    with pytest.raises(ValueError, match='65536'):
        asyncio.run(run(Namespace(max_tokens=4000, output=str(target))))
    assert not target.exists()


def test_connection_failure_keeps_request_and_unknown_usage(tmp_path, monkeypatch):
    class Record:
        page_review_id = 'record'
        def model_dump(self, **kwargs):
            return {'test': True}

    route = Namespace(provider='test-provider', model='test-model', reasoning_effort='low')
    async def resolve(value):
        return value
    async def fail(*args):
        raise ConnectionError('Do not persist arbitrary exception text')
    monkeypatch.setattr(entry, 'load_database_samples', lambda args: [(0, Record(), Record())])
    monkeypatch.setattr(entry, 'observations', lambda record: [])
    monkeypatch.setattr(entry, 'require_page_reader_routes', lambda: {entry.PageReviewLane.MAIN_A: route})
    monkeypatch.setattr(entry, 'resolve_route_model', resolve)
    monkeypatch.setattr(entry, 'direct_openai_completion', fail)
    target = tmp_path / 'failure'
    args = Namespace(max_tokens=65536, records=None, database='unused',
                     coverage='test', indices=[0], output=str(target))
    with pytest.raises(ConnectionError):
        asyncio.run(run(args))
    request = json.loads((target / 'page-0-request.json').read_text())
    failure = json.loads((target / 'page-0-error.json').read_text())
    assert request['max_tokens'] == 65536
    assert request['model'] == 'test-model'
    assert failure['usage'] is None
    assert failure['error_type'] == 'ConnectionError'
    assert failure['elapsed_seconds'] >= 0
    assert 'Do not persist' not in (target / 'page-0-error.json').read_text()


def test_incomplete_source_binding_rejected_before_output(tmp_path):
    target = tmp_path / 'run'
    args = Namespace(max_tokens=65536, records=None, database=None,
                     coverage=None, indices=None, output=str(target))
    with pytest.raises(ValueError, match='Require records'):
        asyncio.run(run(args))
    assert not target.exists()


def test_source_field_proposal_preserves_input_and_keeps_default_policy():
    source = {'main_A': [{'id': 'a'}], 'main_B': [{'id': 'b'}]}
    old = entry.pairing_messages(source)
    new = entry.pairing_messages(source, 'source-field/v2')
    assert old[1] == new[1]
    assert '本实验不配对' in old[0]['content']
    assert '不表示读值正确' in new[0]['content']
    assert '不得用另一读道的时间或对象替它补齐' in new[0]['content']
    assert source == {'main_A': [{'id': 'a'}], 'main_B': [{'id': 'b'}]}
    with pytest.raises(ValueError, match='Unknown'):
        entry.pairing_messages(source, 'unapproved')


def test_source_field_v3_does_not_change_prior_prompts_or_source():
    source = {'main_A': [], 'main_B': []}
    v2 = entry.pairing_messages(source, 'source-field/v2')
    v3 = entry.pairing_messages(source, 'source-field/v3')
    assert v3[0]['content'].startswith(v2[0]['content'])
    assert v3[1] == v2[1]
    assert '每个a和每个b最多出现一次' in v3[0]['content']
    assert 'field与value共同限定' in v3[0]['content']
    assert 'field与value共同限定' not in v2[0]['content']
