"""Freeze original PDFs through product paging/rendering for component comparison.

This is an isolated reader input, not a persisted or completed production job.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from app.evidence.paging import page_source_document
from app.evidence.render import render_page_image, RENDERER_VERSION
from app.domain.contracts.page_review_context import PageReviewContext
from app.projections.clause_pack import project_clause_pack
from scripts.export_clause_pack import _load_rule_set
from scripts.run_frozen_product_reader import save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--rule-set-id', required=True)
    parser.add_argument('--revision', type=int, required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--subject', required=True)
    parser.add_argument('--stage', choices=['screening', 'baseline'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rules, rules_sha = _load_rule_set(args.database.resolve(), args.rule_set_id, args.revision)
    pack = project_clause_pack(rules)
    entries = [e for e in json.loads(args.manifest.read_text())
               if e['project'] == args.project and e['subject'] == args.subject]
    if not entries:
        parser.error('No source entries for selected subject')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'pages').mkdir()
    (args.output / 'originals').mkdir()
    pages, source_index = [], []
    # The old manifest only locates documents. No old questions, answers or rendered images are used.
    for source in dict.fromkeys(e['source_path'] for e in entries):
        path = Path(source)
        if path.suffix.lower() != '.pdf':
            raise ValueError('This source preparation supports PDF only')
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        (args.output / 'originals' / (digest + '.pdf')).write_bytes(content)
        plan = page_source_document(content=content, media_kind='pdf')
        for page in plan.pages:
            rendered = render_page_image(page)
            image_sha = hashlib.sha256(rendered.image_bytes).hexdigest()
            (args.output / 'pages' / image_sha).write_bytes(rendered.image_bytes)
            pages.append({'page_artifact_id': f'benchmark-page:{digest}:{page.page_number}:{image_sha}',
                          'source_document_version_id': digest, 'page_number': page.page_number,
                          'page_image_sha256': image_sha})
        source_index.append({'path': source, 'sha256': digest, 'page_count': len(plan.pages)})
    context = PageReviewContext(review_episode_id=f'isolated-reader:{args.project}:{args.subject}:{args.stage}',
                                episode_revision=1, stage=args.stage)
    save(args.output / 'input.json', {'pages': pages, 'review_context': context.model_dump(mode='json'),
                                    'clause_pack': pack.model_dump(mode='json')})
    save(args.output / 'provenance.json', {'sources': source_index, 'rule_database': str(args.database.resolve()),
         'published_rule_sha256': rules_sha, 'renderer_version': RENDERER_VERSION,
         'component_only': True, 'production_job': False, 'anchor_dates': 'not supplied; do not infer'})
    shutil.copytree('app', args.output / 'product-code', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(__file__, args.output / 'prepare.py')
    shutil.copy2('scripts/run_frozen_product_reader.py', args.output / 'runner.py')
    files = {str(p.relative_to(args.output)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in args.output.rglob('*') if p.is_file()}
    save(args.output / 'manifest.json', {'files': files, 'source_job': None, 'component_only': True,
                                       'gold_in_model_input': False, 'clinical_acceptance': False})
    print(json.dumps({'pages': len(pages), 'sources': len(source_index), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
