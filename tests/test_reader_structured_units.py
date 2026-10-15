import pytest

from scripts.score_reader_structured_units import canonical_unit, evaluate


@pytest.mark.parametrize('unit,state,matched', [('g/L', 'unit_match', True),
                                              ('mg/L', 'unit_mismatch', False),
                                              (None, 'structured_unit_missing', False)])
def test_number_alone_is_not_complete_measurement(unit, state, matched):
    record = {'page_image_sha256': 'x', 'facts': [{'observation_id': 'a', 'field_name': 'X',
              'raw_value': '5', 'normalized_unit': unit}]}
    rows = evaluate(record, {'source_sha256': 'x', 'values': [['X', '5', []]]},
                    {'source_sha256': 'x', 'units': {'X': 'g/L'}})
    assert rows[0]['unit_state'] == state
    assert rows[0]['number_and_unit_match'] is matched


def test_no_scale_conversion_or_case_sensitive_litre_difference():
    assert canonical_unit('×10^9/L') == canonical_unit('10^9/l')
    assert canonical_unit('10^9/L') != canonical_unit('10^12/L')


def test_unit_source_must_match():
    with pytest.raises(ValueError, match='source'):
        evaluate({'page_image_sha256': 'x'}, {}, {'source_sha256': 'other'})
