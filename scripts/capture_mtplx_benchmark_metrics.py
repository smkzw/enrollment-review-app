"""Retain selected runtime timing fields and exact response-ID bindings."""

import argparse
import datetime
import json
from pathlib import Path
import urllib.request

FIELDS = (
    'request_id', 'request_reasoning_effort', 'prompt_tokens', 'completion_tokens',
    'cached_tokens', 'new_prefill_tokens', 'cache_source', 'prompt_eval_time_s',
    'cache_restore_time_s', 'prefill_tok_s', 'prefill_compute_tok_s', 'prefill_wall_tok_s',
    'ttft_s', 'decode_elapsed_s', 'request_elapsed_s', 'decode_tok_s',
    'active_memory_bytes', 'peak_memory_bytes', 'cache_memory_bytes', 'finish_reason',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def fetch(path):
        with opener.open('http://127.0.0.1:8002/' + path, timeout=10) as stream:
            return json.load(stream)
    health = fetch('health')
    if health['model'] != args.model:
        raise ValueError('Unexpected local model; refusing to mix metrics')
    metrics = fetch('metrics')['recent']
    prior = json.loads(args.output.read_text()) if args.output.exists() else {
        'model': args.model, 'records': {}, 'clinical_acceptance': False,
    }
    if prior['model'] != args.model:
        raise ValueError('Output belongs to another model')
    bindings = {}
    responses = list(args.root.glob('product-runs*/*/response-*.json'))
    responses.extend(args.root.glob('normalizer*-runs/*/response-*.json'))
    for path in responses:
        response = json.loads(path.read_text())
        if response.get('response_model') == args.model and response.get('response_id'):
            bindings.setdefault(response['response_id'], []).append(str(path.relative_to(args.root)))
    for item in metrics:
        request_id = item.get('request_id')
        if request_id:
            prior['records'][request_id] = {
                **{key: item.get(key) for key in FIELDS},
                'source_responses': bindings.get(request_id, []),
            }
    prior['captured_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(prior, ensure_ascii=False, indent=2))
    print(json.dumps({'records': len(prior['records']),
                      'bound': sum(bool(x['source_responses']) for x in prior['records'].values())}))


if __name__ == '__main__':
    main()
