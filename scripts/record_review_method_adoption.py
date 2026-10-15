"""Record the user's review-method adoption decision (design §17.6).

This script is run BY THE USER after they have reviewed the evaluation
metrics. It persists the typed ``ReviewMethodApproval`` and the
``review-method-adoption`` gate that ``frozen_review_publication`` requires.
It must never be run by an agent on the user's behalf: the approval record
is the user's own written decision.

Usage:
    python scripts/record_review_method_adoption.py \
        --manifest-sha <sha256> [--manifest-sha <sha256> ...] \
        --approving-principal "姓名/角色" \
        --approval-source-file approval_note.txt \
        [--approved-at 2026-09-21T10:00:00+00:00]

After success, set ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID=<gate_result_id>
so the prepared-review publish endpoint can use it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-sha", action="append", required=True)
    parser.add_argument("--approving-principal", required=True)
    parser.add_argument("--approval-source-file", required=True)
    parser.add_argument("--approved-at", default=None)
    args = parser.parse_args()

    os.environ.setdefault("ENROLLMENT_ENV_FILE", str(Path(__file__).resolve().parents[1] / ".env"))
    from app.config import load_enrollment_env_file
    load_enrollment_env_file()
    from app.domain.contracts.agents import GateResult
    from app.domain.contracts.enums import GateOutcome
    from app.domain.contracts.review_method_adoption import (
        BindingEvaluationManifest,
        ReviewMethodApproval,
    )
    from app.domain.publication import canonical_hash
    from app.evidence.artifacts import ArtifactStore
    from app.services.evidence_app_bootstrap import resolve_data_paths, upgrade_or_fail
    from app.storage.repositories import AppendRepository, GATE_RESULT_CONFIG

    approved_at = (
        datetime.fromisoformat(args.approved_at)
        if args.approved_at else datetime.now(UTC)
    )
    if approved_at.utcoffset() is None:
        approved_at = approved_at.replace(tzinfo=UTC)

    _, _engine, session_factory = upgrade_or_fail(resolve_data_paths())
    artifact_store = ArtifactStore(resolve_data_paths())
    manifest_shas = []
    for digest in args.manifest_sha:
        manifest = BindingEvaluationManifest.model_validate_json(
            artifact_store.read_by_sha("evaluation_manifest", digest),
        )
        # 采用确认不得早于评测记录（与读取侧校验一致）。
        if manifest.created_at > approved_at:
            raise SystemExit(f"评测记录 {digest[:12]} 晚于采用时间，拒绝采用")
        manifest_shas.append(digest)
    if len(manifest_shas) != len(set(manifest_shas)):
        raise SystemExit("评测记录不得重复")

    source_bytes = Path(args.approval_source_file).read_bytes()
    if not source_bytes.strip():
        raise SystemExit("采用来源记录为空，拒绝采用")
    source_artifact = artifact_store.put("approval_source", source_bytes)
    approval = ReviewMethodApproval(
        evaluation_manifest_sha256s=manifest_shas,
        approving_principal=args.approving_principal,
        approval_source_sha256=source_artifact.sha256,
        approved_at=approved_at,
        decision="adopt_method_for_formal_calculation",
    )
    approval_artifact = artifact_store.put(
        "method_approval", approval.model_dump_json().encode("utf-8"),
    )
    gate_id = f"gate:review-method-adoption:{approval_artifact.sha256[:16]}"
    gate = GateResult(
        gate_result_id=gate_id,
        gate_name="review-method-adoption",
        result=GateOutcome.ACCEPTED,
        input_scope_hash=canonical_hash({
            "manifests": sorted(manifest_shas),
            "approval_source": source_artifact.sha256,
        }),
        input_entity_refs=(
            [f"method_approval:{approval_artifact.sha256}"]
            + [f"evaluation_manifest:{digest}" for digest in manifest_shas]
        ),
        accepted_entity_refs=[gate_id],
        affected_scope=["review_method"],
        recompute_scope=["review_method"],
        idempotency_key=canonical_hash({
            "identity": "review-method-adoption/v1",
            "approval": approval_artifact.sha256,
        }),
        created_at=datetime.now(UTC),
        output_hash=canonical_hash(approval.model_dump(mode="json")),
    )
    with session_factory() as session, session.begin():
        AppendRepository(session, GATE_RESULT_CONFIG).save(gate)
    print(json.dumps({
        "gate_result_id": gate_id,
        "approval_sha256": approval_artifact.sha256,
        "manifests": manifest_shas,
        "next": f"set ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID={gate_id}",
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
