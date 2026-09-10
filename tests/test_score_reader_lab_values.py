import pytest

from scripts.score_reader_lab_values import score


def sample(field, value='4.04'):
    return {'page_image_sha256': 'source', 'facts': [
        {'field_name': field, 'raw_value': value, 'observation_id': 'one'}]}


GOLD = {'source_sha256': 'source', 'values': [['WBC', '4.04', ['white blood cells']]]}


def test_composite_is_opt_in_and_requires_complete_known_labels():
    record = sample('WBC white blood cells')
    assert score(record, GOLD)[0]['state'] == 'missing_or_unmapped'
    assert score(record, GOLD, True)[0]['state'] == 'numeric_match'
    assert score(sample('WBC other measure'), GOLD, True)[0]['state'] == 'missing_or_unmapped'
    assert score(sample('WBC% white blood cells'), GOLD, True)[0]['state'] == 'missing_or_unmapped'


def test_composite_preserves_mismatch_ambiguity_and_source_checks():
    assert score(sample('WBC white blood cells', '4.4'), GOLD, True)[0]['state'] == 'numeric_mismatch'
    record = sample('WBC white blood cells')
    record['facts'].extend(sample('WBC')['facts'])
    assert score(record, GOLD, True)[0]['state'] == 'ambiguous'
    record['page_image_sha256'] = 'other'
    with pytest.raises(ValueError, match='Source mismatch'):
        score(record, GOLD, True)
