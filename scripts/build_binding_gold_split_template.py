"""Generate a gold-split annotation template from a completed qualification job.

The template pre-fills predicate identities and candidate facts **as inventory
only**; the human annotator decides ``expected_fact_ids`` / ``forbidden_fact_ids``
from the source documents and fills ``annotated_by``. Gold is never derived from
model selections — the ``expected``/``forbidden`` columns start empty on purpose.

Usage:
    python scripts/build_binding_gold_split_template.py \
        --qualification-job-id <id> --out gold_split_template.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

GOLD_SPLIT_VERSION = "binding-gold-split/v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-job-id", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    os.environ.setdefault("ENROLLMENT_ENV_FILE", str(Path(__file__).resolve().parents[1] / ".env"))
    from app.config import load_enrollment_env_file
    load_enrollment_env_file()
    from app.services.evidence_app_bootstrap import resolve_data_paths, upgrade_or_fail
    from app.services.binding_qualification_support import (
        verify_completed_binding_qualification,
    )
    from app.evidence.artifacts import ArtifactStore

    _, _engine, session_factory = upgrade_or_fail(resolve_data_paths())
    with session_factory() as session:
        verified = verify_completed_binding_qualification(
            session, ArtifactStore(resolve_data_paths()), args.qualification_job_id,
        )
        identity_to_predicate = {}
        for component in verified["frozen"].components:
            for pred in component.binding_predicates:
                identity_to_predicate[pred.predicate_identity_sha256] = pred.predicate_id
        candidate_facts = sorted(fact.fact_id for fact in verified["frozen"].facts)
        selected = {}
        for record in verified["summary"].pair_records:
            if record.structurally_valid and record.dual_agreement:
                selected.setdefault(record.identity_sha256, set()).add(record.fact_id)

        entries = []
        for identity, predicate_id in sorted(identity_to_predicate.items(),
                                             key=lambda item: item[1]):
            entries.append({
                "predicate_id": predicate_id,
                "predicate_identity_sha256": identity,
                # 标注区：由独立标注人依据原件与方案原文填写；模板留空。
                "expected_fact_ids": [],
                "forbidden_fact_ids": [],
                "notes": "",
                # 参考清单（非金标）：仅列出冻结输入事实与双路一致选择，供对照。
                "_reference_candidate_fact_ids": candidate_facts,
                "_reference_dual_agreement_selected": sorted(selected.get(identity, [])),
            })
        template = {
            "version": GOLD_SPLIT_VERSION,
            "qualification_job_id": args.qualification_job_id,
            "annotated_by": "",
            "entries": entries,
        }
        Path(args.out).write_text(
            json.dumps(template, ensure_ascii=False, indent=1), encoding="utf-8",
        )
    print(f"wrote {args.out} with {len(entries)} entries; "
          "fill expected/forbidden per source documents and set annotated_by.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
