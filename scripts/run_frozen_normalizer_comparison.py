"""Compare the actual normalizer on a read-only product-built input."""

import argparse
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents.evidence_normalizer import (
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, EvidenceNormalizerAgentResponse,
    EvidenceNormalizerRunner, evidence_normalizer_json_schema,
)
from app.agents.deepseek_evidence_normalizer_transport import DeepSeekEvidenceNormalizerTransport
from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.evidence_normalizer import EvidenceNormalizerInput, EvidenceNormalizerOutput
from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_harness import direct_openai_completion, require_page_reader_routes
from app.services.fact_normalization_executor import _build_input
from app.storage.fact_repositories import FactNormalizationRunRepository
from app.projections.page_review_sources import validate_accepted_candidate_sources
from scripts.benchmark_direct_transports import subscription_completion, normalized_finish
from scripts.run_frozen_product_reader import save, require_idle_local_reader


def audit_saved_normalizer_output(output):
    output = Path(output)
    evidence = EvidenceNormalizerInput.model_validate_json((output / 'input.json').read_text())
    result = json.loads((output / 'result.json').read_text())
    audit = {'clinical_acceptance': False, 'scope': 'fact_candidate_source_references',
             'source_check_passed': False}
    if result.get('final_output') is not None:
        candidates = EvidenceNormalizerOutput.model_validate(result['final_output'])
        try:
            validate_accepted_candidate_sources(candidates, evidence.page_review,
                                                locator_inputs=evidence.available_locators)
            audit['source_check_passed'] = evidence.page_review is not None
        except ValueError as exc:
            audit['source_error'] = str(exc)
        audit.update(facts=len(candidates.fact_candidates), events=len(candidates.event_candidates),
                     exposures=len(candidates.exposure_candidates), unresolved=len(candidates.unresolved_items))
    save(output / 'source-audit.json', audit)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen', type=Path, required=True)
    parser.add_argument('--job', required=True)
    parser.add_argument('--call', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lane', choices=['main-A', 'main-B'], default='main-A')
    parser.add_argument('--effort', choices=['low', 'high', 'max'], required=True)
    parser.add_argument('--provider', choices=['google-antigravity', 'openai-codex', 'omlx', 'mtplx'])
    parser.add_argument('--model')
    args = parser.parse_args()
    require_idle_local_reader(args.provider)
    manifest = json.loads((args.frozen / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        if hashlib.sha256((args.frozen / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen input changed: ' + name)
        if name.startswith('product-code/'):
            current = Path('app') / Path(name).relative_to('product-code')
            if hashlib.sha256(current.read_bytes()).hexdigest() != expected:
                raise ValueError('Product version changed: ' + name)
    uri = (args.frozen / 'enrollment-review-v2.sqlite3').resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as db:
        payload = json.loads(db.execute('SELECT payload_json FROM jobs WHERE job_id=?', (args.job,)).fetchone()[0])
    call = next(item for item in payload['calls'] if item['call_id'] == args.call)
    engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(uri, uri=True))
    with Session(engine) as session:
        created = FactNormalizationRunRepository(session).get(payload['run_id']).created_at
        evidence = _build_input(session, FactAuthority.model_validate(payload['authority']),
            payload['run_id'], call, max_pages_per_call=payload['max_pages_per_call'],
            created_at=created, page_review_coverage_id=payload['page_review_coverage_id'])
    engine.dispose()
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / 'input.json', evidence.model_dump(mode='json'))
    shutil.copy2(__file__, args.output / 'runner.py')
    shutil.copy2('scripts/benchmark_direct_transports.py', args.output / 'transport.py')
    route = replace(require_page_reader_routes()[PageReviewLane(args.lane)],
                    reasoning_effort=args.effort, fallback_base_url='')
    if args.provider:
        if not args.model:
            raise ValueError('Explicit provider requires model')
        route = replace(route, provider=args.provider, model=args.model, api_key='')
        if args.provider in {'omlx', 'mtplx'}:
            route = replace(route, base_url='http://127.0.0.1:' +
                            ('8001' if args.provider == 'omlx' else '8002') + '/v1', api_key='local-benchmark')
    save(args.output / 'run-contract.json', {'job': args.job, 'call': args.call,
        'provider': route.provider, 'model': route.model, 'effort': route.reasoning_effort,
        'component_only': True, 'clinical_acceptance': False, 'budget': 65536,
        'manifest_sha256': hashlib.sha256((args.frozen / 'manifest.json').read_bytes()).hexdigest()})
    messages = []
    session_id = 'normalizer-benchmark-' + uuid.uuid4().hex
    receipts = []

    class Transport:
        def start(self, *, prompt):
            messages.clear()
            return self.continue_session(session_id=session_id, prompt=prompt)

        def continue_session(self, *, session_id, prompt):
            messages.append({'role': 'user', 'content': prompt})
            index = len(receipts)
            save(args.output / f'request-{index}.json', {'messages': messages, 'budget': 65536})
            started = time.monotonic()
            receipt = {'provider': route.provider, 'model': route.model,
                       'effort': route.reasoning_effort,
                       'output_budget_enforced': args.provider != 'openai-codex'}
            try:
                if args.provider in {'google-antigravity', 'openai-codex'}:
                    wire = asyncio.run(subscription_completion(route.provider, route.model,
                        route.reasoning_effort, messages, 65536, timeout=900))
                    save(args.output / f'response-{index}.json', wire)
                    if wire.get('http_status') != 200 or wire.get('error'):
                        raise RuntimeError('Transport failed; retained response contains details')
                    body = wire['text']
                    receipt.update(usage=wire.get('usage'), finish_reason=wire.get('finish_reason'),
                                   response_model=wire.get('response_model'))
                    if normalized_finish(wire) != 'stop':
                        raise RuntimeError('Incomplete candidate response; not accepted as normalizer output')
                else:
                    result = asyncio.run(direct_openai_completion(route, messages, 65536))
                    body = result.text
                    save(args.output / f'response-{index}.json', {
                        'text': body, 'usage': result.usage, 'finish_reason': result.finish_reason,
                        'response_model': result.response_model, 'response_id': result.response_id})
                    receipt.update(usage=result.usage, finish_reason=result.finish_reason)
                messages.append({'role': 'assistant', 'content': body})
                return EvidenceNormalizerAgentResponse(session_id=session_id, text=body)
            except Exception as exc:
                receipt['error_type'] = type(exc).__name__
                raise
            finally:
                receipt['elapsed_seconds'] = time.monotonic() - started
                receipts.append(receipt)
                save(args.output / 'receipts.json', receipts)

    transport = Transport()
    transport_kind = 'candidate_adapter_diagnostic'
    if route.provider in {'zhipu-coding-plan', 'omlx', 'mtplx'}:
        def retain_receipt(receipt):
            index = len(receipts)
            save(args.output / f'response-{index}.json', receipt)
            receipts.append(receipt)
            save(args.output / 'receipts.json', receipts)

        response_format = {'type': 'json_object'}
        if route.provider == 'omlx':
            response_format = {'type': 'json_schema', 'json_schema': {
                'name': 'evidence_normalizer_output', 'strict': True,
                'schema': evidence_normalizer_json_schema()}}
        transport = DeepSeekEvidenceNormalizerTransport(backend=route.provider,
            api_key=route.api_key, base_url=route.base_url, model=route.model,
            reasoning_effort=route.reasoning_effort, max_tokens=65536,
            response_format=response_format, receipt_callback=retain_receipt)
        original_request = transport._request

        def retained_request(kwargs):
            save(args.output / f'request-{len(receipts)}.json', kwargs)
            return original_request(kwargs)

        transport._request = retained_request
        transport_kind = 'product_native_transport'
    save(args.output / 'transport-contract.json', {'kind': transport_kind,
        'clinical_acceptance': False, 'formal_transport_comparison': transport_kind == 'product_native_transport'})
    result = EvidenceNormalizerRunner().run(evidence, transport,
        prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE)
    save(args.output / 'result.json', result.model_dump(mode='json'))
    audit_saved_normalizer_output(args.output)
    print(json.dumps({'status': result.status, 'attempts': len(result.attempts),
                      'clinical_acceptance': False}))


if __name__ == '__main__':
    main()
