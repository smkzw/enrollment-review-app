"""Deterministic reconciliation for the R3 page review lanes."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from app.domain.contracts.clause_pack import DeterminationMode
from app.domain.contracts.page_review import (
    ClauseEvidenceSignal,
    HandwritingObservation,
    PageReconciliation,
    PageReviewLane,
    PageReviewRecord,
    ReconciliationConflict,
    PAGE_REVIEW_CONTRACT_VERSION,
)
from app.domain.publication import canonical_hash
from app.domain.page_normalization import normalize_field_name, normalize_text, observation_context_key, source_arrow_marks
from app.domain.page_source_association import PageAssociationSource, source_aligned_fact_keys

RECONCILIATION_VERSION = "page-reconciliation/r3-v13"


class PageReconciliationError(ValueError):
    pass


def _conflict(
    *, field_name: str, keys: Sequence[str], record_ids: Sequence[str], reason: str
) -> ReconciliationConflict:
    return ReconciliationConflict(
        field_name=field_name,
        normalization_keys=sorted(set(keys)),
        page_review_ids=sorted(set(record_ids)),
        reason=reason,
    )


def reconcile_page_reviews(
    records: Sequence[PageReviewRecord],
    *,
    determination_modes: Mapping[str, DeterminationMode],
    association_source: PageAssociationSource | None = None,
) -> PageReconciliation:
    """Reconcile the two main reads; a third vote from any lane is rejected."""
    if any(record.contract_version != PAGE_REVIEW_CONTRACT_VERSION for record in records):
        raise PageReconciliationError("历史页记录版本仅供回看，请按当前版本重新判读后对账")
    by_lane = {record.lane: record for record in records}
    if PageReviewLane.HANDWRITING_C in by_lane:
        raise PageReconciliationError("页级对账只接受 main-A 与 main-B 两票，不接受第三读记录")
    if len(by_lane) != len(records):
        raise PageReconciliationError("同一页面的读道记录不得重复")
    if PageReviewLane.MAIN_A not in by_lane or PageReviewLane.MAIN_B not in by_lane:
        raise PageReconciliationError("每页必须同时具备 main-A 与 main-B 主读记录")

    page_ids = {record.page_artifact_id for record in records}
    pack_hashes = {record.clause_pack_sha256 for record in records}
    source_identities = {(record.source_document_version_id, record.page_number,
                          record.page_image_sha256, record.clause_pack_id) for record in records}
    if len(page_ids) != 1 or len(pack_hashes) != 1 or len(source_identities) != 1:
        raise PageReconciliationError(
            "同一次页级对账必须绑定同一页和同一条款包"
        )

    main_records = [by_lane[PageReviewLane.MAIN_A], by_lane[PageReviewLane.MAIN_B]]
    if main_records[0].reading_view != main_records[1].reading_view:
        raise PageReconciliationError("两次独立判读使用的阅读视图不一致，不能合并核对")
    facts_by_key: dict[str, list[PageReviewRecord]] = defaultdict(list)
    facts_by_field: dict[str, list[tuple[str, PageReviewRecord]]] = defaultdict(list)
    unassociated_fact_keys: set[str] = set()
    facts_by_identity = defaultdict(list)
    marks_by_key = defaultdict(set)
    for record in main_records:
        for fact in record.facts:
            if fact.context is None or not normalize_text(fact.context.target_text):
                unassociated_fact_keys.add(fact.normalization_key)
            else:
                identity = (normalize_field_name(fact.field_name), observation_context_key(fact.context.model_dump()))
                facts_by_identity[identity].append((record.lane, fact.normalization_key))
            facts_by_key[fact.normalization_key].append(record)
            marks_by_key[fact.normalization_key].add(source_arrow_marks(fact.raw_value))
            facts_by_field[fact.field_name].append((fact.normalization_key, record))

    accepted_fact_keys = sorted(
        key for key, sources in facts_by_key.items()
        if len(sources) == 2 and len({item.lane for item in sources}) == 2
        and key not in unassociated_fact_keys
    )
    if association_source is not None:
        accepted_fact_keys = sorted(set(accepted_fact_keys) | source_aligned_fact_keys(main_records, association_source))
    ambiguous_keys = {
        key for observations in facts_by_identity.values()
        if any(count > 1 for count in Counter(lane for lane, _ in observations).values())
        for _, key in observations
    }
    annotation_conflicts = {key for key, marks in marks_by_key.items() if len(marks) > 1}
    accepted_fact_keys = [key for key in accepted_fact_keys if key not in ambiguous_keys | annotation_conflicts]
    fact_conflicts: list[ReconciliationConflict] = []
    for field_name, observations in sorted(facts_by_field.items()):
        keys = [key for key, _record in observations]
        source_ids = [record.page_review_id for _key, record in observations]
        if not set(keys).issubset(accepted_fact_keys):
            fact_conflicts.append(
                _conflict(
                    field_name=field_name,
                    keys=keys,
                    record_ids=source_ids,
                    reason=("原件异常标记的判读不一致，需核对原件" if set(keys) & annotation_conflicts
                            else "观察所指对象尚待核对" if set(keys) & unassociated_fact_keys
                            else "主读结果未形成双源一致事实"),
                )
            )

    dropped_deterministic: set[str] = set()
    signals_by_clause: dict[
        str, list[tuple[ClauseEvidenceSignal, PageReviewRecord]]
    ] = defaultdict(list)
    for record in main_records:
        for signal in record.clause_signals:
            if determination_modes.get(signal.clause_id) == DeterminationMode.DETERMINISTIC:
                dropped_deterministic.add(signal.clause_id)
                continue
            signals_by_clause[signal.clause_id].append((signal, record))

    accepted_signals: list[ClauseEvidenceSignal] = []
    signal_conflicts: list[ReconciliationConflict] = []
    for clause_id, signals in sorted(signals_by_clause.items()):
        values = [item.signal.value for item, _record in signals]
        source_ids = [record.page_review_id for _item, record in signals]
        if (len(signals) == 2 and len(set(values)) == 1
                and {record.lane for _signal, record in signals}
                == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}):
            accepted_signals.append(signals[0][0])
        else:
            signal_conflicts.append(
                _conflict(
                    field_name=f"clause:{clause_id}",
                    keys=values,
                    record_ids=source_ids,
                    reason="语义条款证据信号未形成双主读一致",
                )
            )

    handwriting_by_key: dict[
        str, list[tuple[HandwritingObservation, PageReviewRecord]]
    ] = defaultdict(list)
    for record in records:
        for observation in record.handwriting:
            handwriting_by_key[observation.normalization_key].append((observation, record))

    accepted_handwriting: list[HandwritingObservation] = []
    handwriting_conflicts: list[ReconciliationConflict] = []
    for key, observations in sorted(handwriting_by_key.items()):
        counts = Counter(record.lane for _item, record in observations)
        lanes = {lane for lane, count in counts.items() if count == 1}
        lanes -= {record.lane for item, record in observations
                  if item.context is None or not normalize_text(item.context.target_text)}
        if len(lanes) >= 2:
            # 胜者必须与传入顺序无关：同一内容键两读道各有一票时按读道优先级
            # 取 main-A；否则从存储的排序 page_review_ids 重算会选到另一读道，
            # 破坏对账内容的可复现性。
            lane_priority = {PageReviewLane.MAIN_A: 0, PageReviewLane.MAIN_B: 1}
            accepted_item, _winner = min(
                ((item, record) for item, record in observations if record.lane in lanes),
                key=lambda pair: lane_priority.get(pair[1].lane, 9),
            )
            accepted_handwriting.append(accepted_item)
        else:
            handwriting_conflicts.append(
                _conflict(
                    field_name="handwriting",
                    keys=[key],
                    record_ids=[record.page_review_id for _item, record in observations],
                    reason="手写批注来源不足、所指对象或重复位置尚待核对",
                )
            )

    material = {
        "page_artifact_id": next(iter(page_ids)),
        "clause_pack_sha256": next(iter(pack_hashes)),
        "page_review_ids": sorted(record.page_review_id for record in records),
    }
    result_fields = dict(
        association_text_sha256=association_source.text_sha256 if association_source is not None else None,
        accepted_fact_keys=accepted_fact_keys,
        fact_conflicts=fact_conflicts,
        accepted_clause_signals=accepted_signals,
        signal_conflicts=signal_conflicts,
        accepted_handwriting=accepted_handwriting,
        handwriting_conflicts=handwriting_conflicts,
        dropped_deterministic_signal_clause_ids=sorted(dropped_deterministic),
    )
    identity = {
        **material,
        **result_fields,
        "algorithm": RECONCILIATION_VERSION,
        "determination_modes": dict(determination_modes),
    }
    return PageReconciliation(
        reconciliation_id="page-reconciliation:" + canonical_hash(identity)[:32],
        **material,
        **result_fields,
    )


__all__ = ["PageReconciliationError", "reconcile_page_reviews"]
