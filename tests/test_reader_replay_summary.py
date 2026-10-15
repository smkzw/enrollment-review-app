import hashlib
import json
from pathlib import Path

import pytest

from scripts.summarize_reader_replays import summarize


def test_summary_keeps_value_and_context_differences_separate(tmp_path):
    sources = []
    for name, value, context in [('a', '1', None), ('b', '2', {'target_text': 'lab'})]:
        path = tmp_path / (name + '.json')
        path.write_text(json.dumps({'facts': [{'field_name': 'WBC', 'observation_id': name,
            'raw_value': value, 'normalized_value': value, 'normalized_unit': None,
            'context': context, 'normalization_key': name}]}))
        sources.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    replay = tmp_path / 'replay.json'
    replay.write_text(json.dumps({'source_records': sources, 'reconciliation': {
        key: [] for key in ('accepted_fact_keys', 'fact_conflicts', 'accepted_handwriting',
                           'handwriting_conflicts', 'signal_conflicts')}}))
    result = summarize(replay)
    assert result['counts']['accepted_fact_keys'] == 0
    assert result['exact_field_contrasts'][0]['different_fields'] == [
        'raw_value', 'normalized_value', 'context', 'normalization_key']
    assert result['eligible_targeted_review_fields'] is None
    Path(sources[0]['path']).write_text('{}')
    with pytest.raises(ValueError, match='Saved reader changed'):
        summarize(replay)
