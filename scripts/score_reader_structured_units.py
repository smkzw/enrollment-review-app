"""Posthoc unit availability in product fields; not OCR or clinical acceptance."""

import argparse
import hashlib
import json
from pathlib import Path
import unicodedata

from scripts.score_reader_lab_values import score


def canonical_unit(value):
    if not value:
        return None
    unit = ''.join(unicodedata.normalize('NFKC', value).casefold().split())
    return unit.removeprefix('×') if unit.startswith('×10^') else unit


def evaluate(record, numeric_gold, unit_gold):
    if record['page_image_sha256'] != unit_gold['source_sha256']:
        raise ValueError('Unit source differs')
    facts = {fact['observation_id']: fact for fact in record['facts']}
    result = []
    for row in score(record, numeric_gold, composite_labels=True):
        if row['item'] not in unit_gold['units']:
            continue
        expected = unit_gold['units'][row['item']]
        observations = row['observations']
        actual = None
        if len(observations) != 1:
            state = 'observation_missing_or_ambiguous'
        else:
            actual = facts[observations[0]['observation_id']].get('normalized_unit')
            state = ('structured_unit_missing' if not actual else
                     'unit_match' if canonical_unit(actual) == canonical_unit(expected) else 'unit_mismatch')
        result.append({'item': row['item'], 'numeric_state': row['state'],
                       'unit_state': state, 'expected_unit': expected, 'actual_unit': actual,
                       'number_and_unit_match': row['state'] == 'numeric_match' and state == 'unit_match'})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--unit-gold', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    gold_paths = [args.root / 'gold-sar-lab-page9.json', args.unit_gold]
    gold, units = (json.loads(path.read_text()) for path in gold_paths)
    results = []
    for path in sorted(args.root.glob('product-runs*/*/record.json')):
        record = json.loads(path.read_text())
        if record['page_image_sha256'] != gold['source_sha256']:
            continue
        rows = evaluate(record, gold, units)
        results.append({'run': str(path.parent.relative_to(args.root)),
                        'record_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'counts': {state: sum(row['unit_state'] == state for row in rows) for state in
                                   ('unit_match', 'unit_mismatch', 'structured_unit_missing', 'observation_missing_or_ambiguous')},
                        'number_and_unit_match': sum(row['number_and_unit_match'] for row in rows),
                        'rows': rows})
    payload = {'scope': 'structured_units_only_not_whole_page_recall', 'clinical_acceptance': False,
               'missing_unit_does_not_mean_unit_absent_from_excerpt': True,
               'gold_sources': [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                                for path in gold_paths], 'results': results}
    with args.output.open('x') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'runs': len(results), 'unit_items': len(units['units']), 'clinical_acceptance': False}))


if __name__ == '__main__':
    main()
