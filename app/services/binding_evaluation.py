"""Binding semantic-correspondence evaluation evidence (design §17.1.1 step 4).

Builds the typed ``BindingEvaluationManifest`` from a completed qualification
job plus a **human-authored** gold split. This module scores and records; it
never approves: ``ReviewMethodApproval`` and the ``review-method-adoption``
gate remain explicit user actions (see ``scripts/record_review_method_adoption``).

Gold split contract (``binding-gold-split/v1``): entries carry, per predicate
identity, the fact ids a clinically correct binding must select (``expected_fact_ids``)
and optional ``forbidden_fact_ids``. Gold is authored against source documents,
never derived from model output; this module only checks structural consistency
(identity hashes exist in the frozen input, fact ids resolve) before scoring.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.contracts.review_method_adoption import (
    BindingEvaluationManifest,
    EvaluatedBindingMethod,
    EvaluatedRoute,
    EvaluationMetric,
)
from app.domain.publication import canonical_hash
from app.services.binding_qualification_support import (
    verify_completed_binding_qualification,
)
from app.services.frozen_review_calculation import EVALUATOR_VERSION
from app.services.frozen_review_publication import PUBLICATION_VERSION
from app.domain.contracts.qualified_binding_selection import (
    QUALIFIED_BINDING_CONSUMER_ALGORITHM,
)

GOLD_SPLIT_VERSION = "binding-gold-split/v1"
SCORING_REPORT_VERSION = "binding-evaluation-scoring-report/v1"

_REQUIRED_ROUTE_FIELDS = (
    "provider", "base_url", "model", "reasoning_effort",
    "max_tokens", "max_concurrency", "fallback_base_url",
)


class BindingEvaluationError(RuntimeError):
    """Gold split or evaluation input invalid; never score an ambiguous set."""


def _validated_gold_split(gold_split: dict[str, Any], verified: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(gold_split, dict):
        raise BindingEvaluationError("金标拆分必须是JSON对象")
    if gold_split.get("version") != GOLD_SPLIT_VERSION:
        raise BindingEvaluationError(f"金标拆分版本必须是{GOLD_SPLIT_VERSION}")
    if gold_split.get("qualification_job_id") != verified["qualification_job_id"]:
        raise BindingEvaluationError("金标拆分不属于本次来源资格核对任务")
    annotator = (gold_split.get("annotated_by") or "").strip()
    if not annotator:
        raise BindingEvaluationError("金标拆分必须注明独立标注人")
    entries = gold_split.get("entries")
    if not isinstance(entries, list) or not entries:
        raise BindingEvaluationError("金标拆分必须至少包含一条金标条目")

    identity_to_predicate: dict[str, str] = {}
    for component in verified["frozen"].components:
        for pred in component.binding_predicates:
            identity_to_predicate[pred.predicate_identity_sha256] = pred.predicate_id
    frozen_facts = {fact.fact_id for fact in verified["frozen"].facts}

    seen_identities: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise BindingEvaluationError("金标条目必须是JSON对象")
        identity = entry.get("predicate_identity_sha256")
        predicate_id = entry.get("predicate_id")
        if identity_to_predicate.get(identity) != predicate_id:
            raise BindingEvaluationError(
                f"金标条目谓词身份与冻结输入不一致: {predicate_id!r}")
        if identity in seen_identities:
            raise BindingEvaluationError(f"金标条目谓词身份重复: {predicate_id!r}")
        seen_identities.add(identity)
        expected = entry.get("expected_fact_ids")
        forbidden = entry.get("forbidden_fact_ids") or []
        if not isinstance(expected, list) or not all(isinstance(f, str) and f for f in expected):
            raise BindingEvaluationError(
                f"金标条目 {predicate_id!r} 的expected_fact_ids必须是非空字符串列表")
        if not isinstance(forbidden, list) or not all(isinstance(f, str) for f in forbidden):
            raise BindingEvaluationError(
                f"金标条目 {predicate_id!r} 的forbidden_fact_ids必须是字符串列表")
        overlap = set(expected) & set(forbidden)
        if overlap:
            raise BindingEvaluationError(
                f"金标条目 {predicate_id!r} 的期望与禁止事实重叠")
        unknown = (set(expected) | set(forbidden)) - frozen_facts
        if unknown:
            raise BindingEvaluationError(
                f"金标条目 {predicate_id!r} 引用了冻结输入之外的事实: {sorted(unknown)[:3]}")
    return gold_split


def _selected_fact_ids_by_identity(verified: dict[str, Any]) -> dict[str, set[str]]:
    selections: dict[str, set[str]] = {}
    for record in verified["summary"].pair_records:
        if not (record.structurally_valid and record.dual_agreement):
            continue
        selections.setdefault(record.identity_sha256, set()).add(record.fact_id)
    return selections


def _score_entries(gold_split: dict[str, Any], selections: dict[str, set[str]]):
    entries = gold_split["entries"]
    per_entry = []
    gold_total = selected_good = selected_total = 0
    silent_missing = 0
    forbidden_hits = 0
    for entry in entries:
        identity = entry["predicate_identity_sha256"]
        expected = set(entry["expected_fact_ids"])
        forbidden = set(entry.get("forbidden_fact_ids") or [])
        selected = selections.get(identity, set())
        good = selected & expected
        bad = selected - expected - forbidden
        gold_total += len(expected)
        selected_good += len(good)
        selected_total += len(selected)
        forbidden_hits += len(selected & forbidden)
        entry_missing = bool(expected) and not good
        silent_missing += 1 if entry_missing else 0
        per_entry.append({
            "predicate_id": entry["predicate_id"],
            "expected_count": len(expected),
            "selected_count": len(selected),
            "correct_count": len(good),
            "wrong_selected_count": len(bad),
            "forbidden_selected_count": len(selected & forbidden),
            "silent_missing": entry_missing,
        })
    recall = Decimal(selected_good) / Decimal(gold_total) if gold_total else None
    precision = (
        Decimal(selected_good) / Decimal(selected_total) if selected_total else None
    )
    return per_entry, recall, precision, silent_missing, forbidden_hits


def _metric(name: str, definition: str, value: Decimal | None, unit: str,
            unavailable_reason: str | None = None) -> EvaluationMetric:
    return EvaluationMetric(
        name=name, definition=definition, value=value, unit=unit,
        unavailable_reason=unavailable_reason,
    )


def _evaluated_route(route: dict[str, Any]) -> EvaluatedRoute:
    missing = [field for field in _REQUIRED_ROUTE_FIELDS if field not in route]
    if missing:
        raise BindingEvaluationError(f"路线记录缺少字段: {missing}")
    return EvaluatedRoute(**{field: route[field] for field in _REQUIRED_ROUTE_FIELDS})


def build_binding_evaluation_manifest(
    session, artifact_store, *, qualification_job_id: str,
    gold_split: dict[str, Any], scoring_version: str,
) -> dict[str, Any]:
    """Verify, score against human gold, and persist evaluation evidence.

    Returns manifest with its artifact sha plus the scoring report artifact;
    approval remains a separate, user-owned step.
    """
    verified = verify_completed_binding_qualification(
        session, artifact_store, qualification_job_id,
        require_candidate_route_receipts=True,
    )
    gold_split = _validated_gold_split(gold_split, verified)
    selections = _selected_fact_ids_by_identity(verified)
    per_entry, recall, precision, silent_missing, forbidden_hits = _score_entries(
        gold_split, selections,
    )

    gold_split_sha = canonical_hash(gold_split)
    scoring_report = {
        "version": SCORING_REPORT_VERSION,
        "qualification_job_id": qualification_job_id,
        "gold_split_sha256": gold_split_sha,
        "scoring_version": scoring_version,
        "per_entry": per_entry,
        "aggregate": {
            "gold_fact_total": sum(item["expected_count"] for item in per_entry),
            "selected_total": sum(item["selected_count"] for item in per_entry),
            "correct_selected_total": sum(item["correct_count"] for item in per_entry),
            "silent_missing_entries": silent_missing,
            "forbidden_selected_total": forbidden_hits,
        },
        "created_at": datetime.now(UTC).isoformat(),
    }
    report_bytes = json.dumps(scoring_report, ensure_ascii=False,
                              sort_keys=True).encode("utf-8")
    report_artifact = artifact_store.put("raw_response", report_bytes)

    candidate_method = verified["candidate_method"]
    method = EvaluatedBindingMethod(
        candidate_family=verified["candidate_family"],
        candidate_job_type=candidate_method["candidate_job_type"],
        candidate_contract=candidate_method["candidate_contract"],
        candidate_prompt_version=candidate_method["candidate_prompt_version"],
        candidate_batch_prompt_version=candidate_method.get("candidate_batch_prompt_version"),
        qualification_contract=verified["contract"],
        qualification_prompt_version=verified["prompt_version"],
        qualification_summary_version=verified["summary"].version,
        consumer_algorithm_version=QUALIFIED_BINDING_CONSUMER_ALGORITHM,
        evaluator_version=EVALUATOR_VERSION,
        publication_version=PUBLICATION_VERSION,
        candidate_routes={
            lane: _evaluated_route(route)
            for lane, route in candidate_method["candidate_routes"].items()
        },
        qualification_routes={
            lane: _evaluated_route(route)
            for lane, route in verified["routes"].items()
        },
    )
    metrics = [
        _metric(
            "selection_recall",
            "金标期望事实中被正确选中的比例（Σ正确选中/Σ期望）",
            recall, "ratio",
            None if recall is not None else "金标条目均无期望事实",
        ),
        _metric(
            "selection_precision",
            "全部选中事实中命中金标的比例（Σ正确选中/Σ选中）",
            precision, "ratio",
            None if precision is not None else "本次评估无任何选中事实",
        ),
        _metric(
            "silent_missing_entries",
            "金标期望非空但选中结果完全未命中期望的条目数",
            Decimal(silent_missing), "count",
        ),
        _metric(
            "forbidden_selected_total",
            "选中了金标明令禁止事实的次数",
            Decimal(forbidden_hits), "count",
        ),
    ]
    manifest = BindingEvaluationManifest(
        source_corpus_sha256=verified["frozen_input_sha256"],
        gold_split_sha256=gold_split_sha,
        scoring_version=scoring_version,
        scoring_report_sha256=report_artifact.sha256,
        methods=[method],
        observed_metrics=metrics,
        created_at=datetime.now(UTC),
    )
    manifest_artifact = artifact_store.put(
        "evaluation_manifest", manifest.model_dump_json().encode("utf-8"),
    )
    return {
        "manifest": manifest,
        "manifest_sha256": manifest_artifact.sha256,
        "scoring_report_sha256": report_artifact.sha256,
        "gold_split_sha256": gold_split_sha,
        "aggregate": scoring_report["aggregate"],
    }
