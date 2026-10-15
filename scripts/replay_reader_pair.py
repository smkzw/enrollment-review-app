"""Replay genuine saved lanes through product reconciliation without relabeling."""

import argparse
import hashlib
import json
from pathlib import Path

from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.page_review import PageReviewRecord
from app.domain.page_reconciliation import reconcile_page_reviews
from app.domain.page_source_association import PageAssociationSource
from app.domain.targeted_page_review import explicit_conflict_fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--records', type=Path, nargs=2, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; preserved evidence will not be overwritten')
    source_input = json.loads(args.input.read_text())
    pack = ClausePack.model_validate(source_input['clause_pack'])
    records = [PageReviewRecord.model_validate_json(path.read_text()) for path in args.records]
    if any(record.clause_pack_sha256 != pack.clause_pack_sha256 for record in records):
        parser.error('Record and input clause packs differ')
    association = source_input.get('association_sources', {}).get(records[0].page_artifact_id)
    result = reconcile_page_reviews(records, determination_modes={
        clause.clause_id: clause.determination_mode for clause in pack.clauses
    }, association_source=PageAssociationSource.model_validate(association) if association else None)
    payload = {
        'component_only': True, 'clinical_acceptance': False,
        'association_source_present': association is not None,
        'eligible_targeted_review_fields': list(explicit_conflict_fields(records)),
        'source_records': [{
            'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()
        } for path in args.records],
        'reconciliation': result.model_dump(mode='json'),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(json.dumps({
        'accepted_fact_keys': len(result.accepted_fact_keys),
        'fact_conflicts': len(result.fact_conflicts),
        'accepted_handwriting': len(result.accepted_handwriting),
        'clinical_acceptance': False,
    }))


if __name__ == '__main__':
    main()
