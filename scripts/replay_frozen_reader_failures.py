"""Diagnose retained benchmark contract failures without any inference requests."""

import argparse
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re

from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.page_review_context import PageReviewContext
from app.llm.independent_vlm import PageVisionInput
from app.llm.page_review_harness import PageCompletion, PageReviewInput, read_page, require_page_reader_routes
from scripts.run_frozen_product_reader import save


async def audit(root):
    routes = require_page_reader_routes()
    reports = []
    for status_path in sorted(root.glob('product-runs*/*/status.json')):
        status = json.loads(status_path.read_text())
        match = re.search(r'page-(\d+)$', status_path.parent.name)
        responses = sorted(status_path.parent.glob('response-*.json'),
                           key=lambda path: int(path.stem.split('-')[-1]))
        if status.get('failure_kind') not in {'schema', 'invalid_json'} or not match or not responses:
            continue
        response_path = responses[-1]
        contract_path = status_path.parent / 'run-contract.json'
        contract = json.loads(contract_path.read_text()) if contract_path.exists() else {}
        frozen = Path(contract['frozen']) if contract else root / ('product-source-d001-sa07007-v1' if status_path.parent.name.startswith('d001-') else 'product-input-v2')
        if contract and hashlib.sha256((frozen / 'manifest.json').read_bytes()).hexdigest() != contract['manifest_sha256']:
            raise ValueError('Replay manifest differs from original runtime contract')
        manifest = json.loads((frozen / 'manifest.json').read_text())
        code_hashes = {name: digest for name, digest in manifest['files'].items()
                       if name.startswith('product-code/')}
        for name, digest in code_hashes.items():
            current = Path('app') / Path(name).relative_to('product-code')
            if hashlib.sha256(current.read_bytes()).hexdigest() != digest:
                raise ValueError('Replay product version differs from frozen input: ' + name)
        payload = json.loads((frozen / 'input.json').read_text())
        raw = json.loads(response_path.read_text())
        request = json.loads(response_path.with_name(response_path.name.replace('response-', 'request-')).read_text())
        page = payload['pages'][int(match[1])]
        image = (frozen / 'pages' / page['page_image_sha256']).read_bytes()
        assert hashlib.sha256(image).hexdigest() == page['page_image_sha256']
        source = PageReviewInput(**page, review_context=PageReviewContext.model_validate(payload['review_context']),
                                page=PageVisionInput(source_ref=page['page_artifact_id'], page_ordinal=page['page_number'], image_bytes=image))
        lane = PageReviewLane(contract['lane']) if contract else (PageReviewLane.MAIN_B if request['model'] == 'cms-model' else PageReviewLane.MAIN_A)
        route = replace(routes[lane], model=request['model'], reasoning_effort=request['effort'], fallback_base_url='')

        async def replay(*_args):
            return PageCompletion(**raw)

        try:
            await read_page(route, source, ClausePack.model_validate(payload['clause_pack']), completion=replay, retry_length=False)
            detail = 'replay_passed_requires_investigation'
        except Exception as exc:
            detail = str(exc)
            if exc.__cause__ is not None:
                detail += '\nCause: ' + str(exc.__cause__)
        reports.append({'run': str(status_path.parent.relative_to(root)),
                        'response_file': response_path.name,
                        'replay_manifest_sha256': hashlib.sha256((frozen / 'manifest.json').read_bytes()).hexdigest(),
                        'replay_code_verified': True,
                        'lane_reconstructed_from_model_not_runtime_receipt': not bool(contract),
                        'scope': 'response_contract_validation_not_request_reexecution',
                        'response_file_sha256': hashlib.sha256(response_path.read_bytes()).hexdigest(),
                        'detail': detail, 'model_called': False})
    save(root / 'contract-failure-replay.json', reports)
    print(json.dumps({'diagnosed': len(reports), 'model_called': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    asyncio.run(audit(parser.parse_args().root))
