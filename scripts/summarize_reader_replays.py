"""Summarize saved reconciliations without accepting or repairing observations."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from app.domain.page_normalization import normalize_field_name


def summarize(path):
    payload = json.loads(path.read_text())
    if 'reconciliation' not in payload:
        return None
    records = []
    for source in payload['source_records']:
        data = Path(source['path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != source['sha256']:
            raise ValueError('Saved reader changed: ' + source['path'])
        records.append(json.loads(data))
    if len(records) != 2:
        raise ValueError('Expected two bound reader records')
    indexed = []
    for record in records:
        fields = defaultdict(list)
        for fact in record['facts']:
            fields[normalize_field_name(fact['field_name'])].append(fact)
        indexed.append(fields)
    left, right = indexed
    contrasts = []
    for field in sorted(left.keys() & right.keys()):
        if len(left[field]) != 1 or len(right[field]) != 1:
            contrasts.append({'field': field, 'ambiguous_members': True})
            continue
        a, b = left[field][0], right[field][0]
        contrasts.append({
            'field': field, 'observation_ids': [a['observation_id'], b['observation_id']],
            'different_fields': [key for key in ('raw_value', 'normalized_value',
                'normalized_unit', 'context', 'normalization_key') if a.get(key) != b.get(key)],
            'same_key': a['normalization_key'] == b['normalization_key'],
        })
    result = payload['reconciliation']
    return {
        'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_records': payload['source_records'],
        'counts': {key: len(result[key]) for key in ('accepted_fact_keys', 'fact_conflicts',
            'accepted_handwriting', 'handwriting_conflicts', 'signal_conflicts')},
        'eligible_targeted_review_fields': payload.get('eligible_targeted_review_fields'),
        'exact_field_contrasts': contrasts,
        'left_only_field_names': sorted(left.keys() - right.keys()),
        'right_only_field_names': sorted(right.keys() - left.keys()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directories', nargs='+', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = [row for directory in args.directories for path in sorted(directory.glob('*.json'))
            if (row := summarize(path)) is not None]
    report = {'clinical_acceptance': False, 'recomputed_reconciliation': False,
              'scope': 'saved_replay_counts_and_exact_field_contrasts_not_semantic_pairing',
              'runs': rows, 'run_count': len(rows),
              'zero_accepted_runs': sum(row['counts']['accepted_fact_keys'] == 0 for row in rows),
              'totals': {key: sum(row['counts'][key] for row in rows)
                         for key in rows[0]['counts']} if rows else {}}
    with args.output.open('x') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: value for key, value in report.items() if key != 'runs'}))


if __name__ == '__main__':
    main()
