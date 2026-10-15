"""Posthoc explicit-label numeric slice; not full clinical acceptance or recall."""

import argparse
import json
import hashlib
import re
import unicodedata
from decimal import Decimal
from pathlib import Path


def label(value):
    return unicodedata.normalize('NFKC', value).strip().lstrip('*★').casefold()


def score(record, gold, composite_labels=False):
    if record['page_image_sha256'] != gold['source_sha256']:
        raise ValueError('Source mismatch')
    rows = []
    for name, expected, aliases in gold['values']:
        names = {label(x) for x in [name, *aliases]}
        if composite_labels:
            # Require both complete known labels; never match an arbitrary code prefix.
            names |= {a + ' ' + b for a in tuple(names) for b in tuple(names) if a != b}
        observations = [x for x in record['facts'] if label(x['field_name']) in names]
        state = 'missing_or_unmapped'
        if len(observations) > 1:
            state = 'ambiguous'
        elif observations:
            raw = unicodedata.normalize('NFKC', observations[0]['raw_value']).strip()
            # Only a leading scalar is scored; no searching a reference range for the answer.
            match = re.match(r'^([+-]?(?:\d+(?:\.\d*)?|\.\d+))(?![\d.])', raw)
            if match and re.match(r'^\s*(?:[-~/]\s*\d|[+*=<>])', raw[match.end():]):
                match = None
            state = 'unreadable_or_unparsed' if match is None else (
                'numeric_match' if Decimal(match[1]) == Decimal(expected) else 'numeric_mismatch'
            )
        rows.append({'item': name, 'expected': expected, 'state': state,
                     'observations': [{k: x[k] for k in ('field_name', 'raw_value', 'observation_id')}
                                      for x in observations]})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--gold', type=Path)
    parser.add_argument('--page-index', type=int, default=9)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--composite-labels', action='store_true',
                        help='Also match two complete gold labels separated by one space; retain baseline separately')
    parser.add_argument('--raw-candidates', action='store_true',
                        help='Posthoc text-only diagnostic; never a product-accepted result')
    args = parser.parse_args()
    gold = json.loads((args.gold or args.root / 'gold-sar-lab-page9.json').read_text())
    results = []
    unscored_runs = []
    records = [(str(path.parent.relative_to(args.root)), json.loads(path.read_text()))
               for path in sorted(args.root.glob(f'product-runs*/*page-{args.page_index}/record.json'))]
    for path in sorted(args.root.glob('product-runs*/*/batch.json')):
        batch = json.loads(path.read_text())
        records.extend((str(path.parent.relative_to(args.root)) + '/' + record['page_artifact_id'], record)
                       for record in batch['records'])
    if args.raw_candidates:
        from app.llm.page_review_harness import extract_json_object
        records = []
        for contract_path in sorted(args.root.glob(f'product-runs*/*page-{args.page_index}/run-contract.json')):
            contract = json.loads(contract_path.read_text())
            frozen = Path(contract['frozen'])
            if hashlib.sha256((frozen / 'manifest.json').read_bytes()).hexdigest() != contract['manifest_sha256']:
                raise ValueError('Raw diagnostic source manifest changed')
            manifest = json.loads((frozen / 'manifest.json').read_text())
            if hashlib.sha256((frozen / 'input.json').read_bytes()).hexdigest() != manifest['files']['input.json']:
                raise ValueError('Raw diagnostic input changed')
            payload = json.loads((frozen / 'input.json').read_text())
            source_hash = payload['pages'][args.page_index]['page_image_sha256']
            if source_hash != gold['source_sha256']:
                continue
            responses = sorted(contract_path.parent.glob('response-*.json'),
                               key=lambda p: int(p.stem.split('-')[-1]))
            if not responses:
                unscored_runs.append({'run': str(contract_path.parent.relative_to(args.root)), 'reason': 'no_response'})
                continue
            wire = json.loads(responses[-1].read_text())
            try:
                raw = extract_json_object(wire['text'])
            except Exception:
                unscored_runs.append({'run': str(contract_path.parent.relative_to(args.root)), 'reason': 'unparseable_response'})
                continue  # Unparseable output is not silently repaired into facts.
            facts = raw.get('facts', [])
            if not isinstance(facts, list) or any(not isinstance(f, dict) or
                    any(not isinstance(f.get(k), str) for k in ('field_name', 'raw_value', 'observation_id'))
                    for f in facts):
                unscored_runs.append({'run': str(contract_path.parent.relative_to(args.root)), 'reason': 'invalid_fact_fields'})
                continue
            records.append((str(contract_path.parent.relative_to(args.root)),
                            {'page_image_sha256': source_hash, 'facts': facts}))
    for run, record in records:
        if record['page_image_sha256'] != gold['source_sha256']:
            continue
        rows = score(record, gold, args.composite_labels)
        counts = {state: sum(x['state'] == state for x in rows)
                  for state in ('numeric_match', 'numeric_mismatch', 'missing_or_unmapped',
                                'ambiguous', 'unreadable_or_unparsed')}
        results.append({'run': run, 'counts': counts, 'rows': rows})
    output = {'scope': gold['scope'], 'clinical_acceptance': False,
              'label_matching': 'exact-or-known-composite/v1' if args.composite_labels else 'exact/v1',
              'raw_candidate_diagnostic_only': args.raw_candidates,
              'unscored_runs': unscored_runs,
              'failed_records_not_scored': not args.raw_candidates, 'results': results}
    default_name = 'raw-candidate-numeric-slice.json' if args.raw_candidates else 'sar-lab-numeric-slice.json'
    (args.output or args.root / default_name).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps([{k: r[k] for k in ('run', 'counts')} for r in results]))


if __name__ == '__main__':
    main()
