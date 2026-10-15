"""Gold-assisted numeric complementarity, separate from product acceptance."""

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path

from scripts.score_reader_lab_values import score


def compare(first, second, gold):
    for key in ('page_image_sha256', 'clause_pack_sha256', 'page_artifact_id'):
        if first[key] != second[key]:
            raise ValueError('Pair source or clause pack differs')
    if {first['lane'], second['lane']} != {'main-A', 'main-B'}:
        raise ValueError('Require genuine distinct main lanes')
    a, b = (score(record, gold, composite_labels=True) for record in (first, second))
    rows = [{'item': x['item'], 'first': x['state'], 'second': y['state'],
             'both_correct': x['state'] == y['state'] == 'numeric_match',
             'either_correct': 'numeric_match' in (x['state'], y['state']),
             'same_wrong_raw_observation': (
                 x['state'] == y['state'] == 'numeric_mismatch'
                 and unicodedata.normalize('NFKC', x['observations'][0]['raw_value']).strip()
                 == unicodedata.normalize('NFKC', y['observations'][0]['raw_value']).strip()
             )}
            for x, y in zip(a, b, strict=True)]
    return {'scope': 'gold_assisted_numeric_slice_not_clinical_recall',
            'clinical_acceptance': False, 'automatic_acceptance': False,
            'label_matching': 'exact-or-known-composite/v1',
            'gold_count': len(rows),
            'both_correct': sum(x['both_correct'] for x in rows),
            'either_correct': sum(x['either_correct'] for x in rows),
            'neither_correct': sum(not x['either_correct'] for x in rows),
            'same_wrong_raw_observation': sum(x['same_wrong_raw_observation'] for x in rows),
            'shared_error_scope': 'exact_nfkc_raw_value_only_not_unit_or_semantic_equivalence',
            'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records', nargs=2, type=Path, required=True)
    parser.add_argument('--gold', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(*(json.loads(p.read_text()) for p in args.records),
                     json.loads(args.gold.read_text()))
    result['sources'] = [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                         for p in [*args.records, args.gold]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'sources')}))


if __name__ == '__main__':
    main()
