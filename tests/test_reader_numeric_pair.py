import pytest

from scripts.score_reader_numeric_pair import compare


def sample(lane, value):
    return {'lane': lane, 'page_image_sha256': 'a' * 64,
            'clause_pack_sha256': 'b' * 64, 'page_artifact_id': 'page',
            'facts': [{'field_name': 'X', 'raw_value': value, 'observation_id': 'f1'}]}


def test_one_correct_is_not_agreement_or_acceptance():
    result = compare(sample('main-A', '5'), sample('main-B', '6'),
                     {'source_sha256': 'a' * 64, 'values': [['X', '5', []]]})
    assert result['either_correct'] == 1
    assert result['both_correct'] == 0
    assert result['automatic_acceptance'] is False


@pytest.mark.parametrize('first,second,shared', [('6', '6', 1), ('６', '6', 1),
                                               ('6 mg', '6 g', 0), ('6', '7', 0)])
def test_shared_wrong_reading_is_not_success(first, second, shared):
    result = compare(sample('main-A', first), sample('main-B', second),
                     {'source_sha256': 'a' * 64, 'values': [['X', '5', []]]})
    assert result['same_wrong_raw_observation'] == shared
    assert result['neither_correct'] == 1
    assert result['either_correct'] == 0


@pytest.mark.parametrize('key,value', [('lane', 'main-A'),
                                      ('page_artifact_id', 'other'),
                                      ('clause_pack_sha256', 'c' * 64)])
def test_binding_rejected(key, value):
    other = sample('main-B', '5')
    other[key] = value
    with pytest.raises(ValueError):
        compare(sample('main-A', '5'), other,
                {'source_sha256': 'a' * 64, 'values': [['X', '5', []]]})
