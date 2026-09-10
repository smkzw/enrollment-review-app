"""Phase 5 Slice 5.2 确定性批量门禁编排（纯确定性，无模型/发布）。

职责（设计书 §4.2 顺序，仅覆盖 Slice 5.2 的批量层）：

- 空输出失败：批次内 fact+event+exposure 均为空时，批次整体 REJECTED，不生成空 Profile；
- 页覆盖失败：若提供 revision+calls，校验页清单完整闭合，未闭合时逐候选
  ``PAGE_COVERAGE_AND_REFERENCE_CLOSURE`` 为 REJECTED，批次整体 REJECTED；
- 精确重复分组：基于 ``clinical_*_stable_identity`` 的稳定内容身份分组
  （权威元组 + 临床对象/类型/极性/规范值/单位/日期/持续状态，不含定位与置信度），
  确定性排序，不择优；
- 语义冲突检测：同一语义对象（fact 的 fact_type:asserted_object、
  event 的 event_type + 引用事实对象、exposure 的 medication_name）在同一批次内出现
  2 个及以上不同稳定身份时，建立未解决冲突组，不自动选择赢家；
- 逐候选裁决与受影响范围：为每个候选生成
  ``IN_DOCUMENT_DEDUP_CONFLICT`` 与 ``CROSS_DOCUMENT_MERGE_CONFLICT``
  的 ``GateVerdict``，受影响范围为同一去重/冲突组内其他候选 ID（有序去重）；
- 持久化衔接：将 ``GateVerdict`` 扁平为 ``FactGateResult``，确定性排序，
  通过 ``FactGateResultRepository`` 可持久化，但本模块不直接发布事实或 Profile。

所有函数均为纯确定性：无随机、无 wall clock（created_at 由调用方传入）、
无 DB（除页覆盖校验的可选 session 与 revision 传入）、无模型调用。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.domain.contracts.enums import DurationStatus, FactCallStatus, FactGate, GateOutcome
from app.domain.contracts.fact_gates import (
    BatchGateResult,
    DedupGroup,
    GateVerdict,
    RunGateResult,
    SemanticConflictGroup,
)
from app.domain.contracts.facts import (
    ClinicalEventCandidateV2,
    ClinicalFactCandidateV2,
    FactAuthority,
    FactGateResult,
    FactNormalizationCall,
    MedicationExposureCandidateV2,
    clinical_event_stable_identity,
    clinical_fact_stable_identity,
    medication_exposure_stable_identity,
)
# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _affected_scope_sorted(values: list[str]) -> list[str]:
    return sorted(set(values))


def _sha_like(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _authority_revision_errors(
    authority: FactAuthority,
    revision,
    session: Session | None,
) -> list[str]:
    """核对运行冻结权威与完整处理修订；有 session 时再复核活动指针。"""
    expected = (
        authority.complete_processing_revision_id,
        authority.evidence_snapshot_v2_id,
        authority.project_id,
        authority.subject_id,
        authority.review_episode_id,
    )
    actual = (
        revision.evidence_processing_revision_id,
        revision.evidence_snapshot_id,
        revision.project_id,
        revision.subject_id,
        revision.review_episode_id,
    )
    errors: list[str] = []
    if actual != expected:
        errors.append("完整处理修订与运行冻结的不可变权威元组不一致")
    if session is not None:
        from app.storage.fact_authority import FactAuthorityError, FactAuthorityValidator

        try:
            FactAuthorityValidator(session).validate(authority)
        except FactAuthorityError as exc:
            errors.append(str(exc))
    return sorted(set(errors))


# ---------------------------------------------------------------------------
# 稳定身份计算（纯确定性，复用已冻结的 stable_identity 函数）
# ---------------------------------------------------------------------------


def _fact_stable_identity(candidate: ClinicalFactCandidateV2, authority: FactAuthority) -> str:
    return clinical_fact_stable_identity(
        authority=authority,
        fact_type=candidate.fact_type,
        asserted_object=candidate.asserted_object,
        polarity=candidate.polarity,
        value=candidate.canonical_value,
        unit=candidate.unit,
        date_range=candidate.date_range,
    )


def _event_stable_identity(
    candidate: ClinicalEventCandidateV2,
    authority: FactAuthority,
    facts_by_id: dict[str, ClinicalFactCandidateV2],
) -> str:
    referenced_objects = sorted({
        f"{facts_by_id[fact_id].fact_type}:{facts_by_id[fact_id].asserted_object}"
        if fact_id in facts_by_id
        else f"missing:{fact_id}"
        for fact_id in candidate.fact_candidate_ids
    })
    return clinical_event_stable_identity(
        authority=authority,
        event_type=candidate.event_type,
        referenced_fact_objects=referenced_objects,
        start_range=candidate.start_range,
        end_range=candidate.end_range,
        duration_status=candidate.duration_status,
    )


def _exposure_stable_identity(candidate: MedicationExposureCandidateV2, authority: FactAuthority) -> str:
    return medication_exposure_stable_identity(
        authority=authority,
        medication_name=candidate.medication_name,
        category=candidate.category,
        indication=candidate.indication,
        dose=candidate.dose,
        unit=candidate.unit,
        frequency=candidate.frequency,
        route=candidate.route,
        start_range=candidate.start_range,
        end_range=candidate.end_range,
        duration_status=candidate.duration_status,
    )


def compute_stable_identity_map(
    *,
    authority: FactAuthority,
    fact_candidates: list[ClinicalFactCandidateV2],
    event_candidates: list[ClinicalEventCandidateV2],
    exposure_candidates: list[MedicationExposureCandidateV2],
) -> dict[str, str]:
    """计算批次内每个候选的稳定身份（确定性排序，不含候选顺序依赖）。

    返回 ``{candidate_id: stable_identity}``，其中 stable_identity 为
    64 位十六进制，去重键已排序。
    """
    result: dict[str, str] = {}
    facts_by_id = {candidate.candidate_id: candidate for candidate in fact_candidates}
    for fact_candidate in sorted(fact_candidates, key=lambda c: c.candidate_id):
        result[fact_candidate.candidate_id] = _fact_stable_identity(fact_candidate, authority)
    for event_candidate in sorted(event_candidates, key=lambda c: c.candidate_id):
        result[event_candidate.candidate_id] = _event_stable_identity(
            event_candidate, authority, facts_by_id
        )
    for exposure_candidate in sorted(exposure_candidates, key=lambda c: c.candidate_id):
        result[exposure_candidate.candidate_id] = _exposure_stable_identity(exposure_candidate, authority)
    return result


# ---------------------------------------------------------------------------
# 精确重复分组（稳定、确定性）
# ---------------------------------------------------------------------------


def group_exact_duplicates(
    *,
    authority: FactAuthority,
    fact_candidates: list[ClinicalFactCandidateV2],
    event_candidates: list[ClinicalEventCandidateV2],
    exposure_candidates: list[MedicationExposureCandidateV2],
) -> list[DedupGroup]:
    """按稳定身份对批次候选进行精确去重分组。

    - 同一稳定身份且 ``candidate_ids`` >=2 时形成一个 ``DedupGroup``；
    - ``merged_locator_ids`` 为组内全部定位的有序并集（不参与身份）；
    - 返回按 ``stable_identity`` 排序的确定性列表。
    """
    stable_map = compute_stable_identity_map(
        authority=authority,
        fact_candidates=fact_candidates,
        event_candidates=event_candidates,
        exposure_candidates=exposure_candidates,
    )
    # 反向索引：stable_identity -> candidate_ids
    rev: dict[str, list[str]] = {}
    # 收集定位：candidate_id -> locator_ids
    locator_map: dict[str, list[str]] = {}
    for fact_candidate in fact_candidates:
        locator_map[fact_candidate.candidate_id] = list(fact_candidate.locator_ids)
    for event_candidate in event_candidates:
        locator_map[event_candidate.candidate_id] = list(event_candidate.locator_ids)
    for exposure_candidate in exposure_candidates:
        locator_map[exposure_candidate.candidate_id] = list(exposure_candidate.locator_ids)

    for cid, sid in stable_map.items():
        rev.setdefault(sid, []).append(cid)

    groups: list[DedupGroup] = []
    for sid, cids in rev.items():
        if len(cids) < 2:
            continue
        cids_sorted = sorted(set(cids))
        merged: set[str] = set()
        for cid in cids_sorted:
            merged.update(locator_map.get(cid, []))
        groups.append(
            DedupGroup(
                stable_identity=sid,
                candidate_ids=cids_sorted,
                merged_locator_ids=sorted(merged),
            )
        )
    groups.sort(key=lambda g: g.stable_identity)
    return groups


# ---------------------------------------------------------------------------
# 语义键与冲突检测（不择优）
# ---------------------------------------------------------------------------


def _fact_semantic_key(candidate: ClinicalFactCandidateV2) -> str:
    # 同一被断言对象在不同极性/值/单位/日期下冲突；按 fact_type:asserted_object
    return f"fact:{candidate.fact_type}:{candidate.asserted_object}"


def _event_semantic_key(
    candidate: ClinicalEventCandidateV2,
    facts_by_id: dict[str, ClinicalFactCandidateV2],
) -> str:
    objects = sorted(
        {
            f"{facts_by_id[fid].fact_type}:{facts_by_id[fid].asserted_object}"
            for fid in candidate.fact_candidate_ids
            if fid in facts_by_id
        }
    )
    return f"event:{candidate.event_type}:{'|'.join(objects)}"


def _exposure_semantic_key(candidate: MedicationExposureCandidateV2) -> str:
    # 按药名聚合；是否冲突还需结合临床内容与暴露时间范围。
    return f"exposure:{candidate.medication_name}"


def _clinical_payload_signature(candidate) -> tuple:
    """排除时间字段后的临床内容；纯时间变化不构成冲突。"""
    if isinstance(candidate, ClinicalFactCandidateV2):
        return (candidate.polarity, candidate.canonical_value, candidate.unit)
    if isinstance(candidate, ClinicalEventCandidateV2):
        return (candidate.duration_status,)
    return (
        candidate.category,
        candidate.indication,
        candidate.dose,
        candidate.unit,
        candidate.frequency,
        candidate.route,
        candidate.duration_status,
    )


def _known_fact_bounds(candidate: ClinicalFactCandidateV2):
    date_range = candidate.date_range
    if (
        date_range is None
        or date_range.lower_bound is None
        or date_range.upper_bound is None
    ):
        return None
    return date_range.lower_bound, date_range.upper_bound


def _known_span_bounds(candidate):
    start = candidate.start_range
    if (
        start is None
        or start.lower_bound is None
        or start.upper_bound is None
    ):
        return None
    if candidate.duration_status == DurationStatus.SINGLE:
        return start.lower_bound, start.upper_bound
    if candidate.end_range is None or candidate.end_range.upper_bound is None:
        return start.lower_bound, None
    return start.lower_bound, candidate.end_range.upper_bound


def _exposures_have_known_conflict(left, right) -> bool:
    """Missing details and unknown duration are uncertainty, not contradiction."""
    for field in ("dose", "unit", "frequency", "route"):
        left_value = getattr(left, field)
        right_value = getattr(right, field)
        if left_value is not None and right_value is not None and left_value != right_value:
            return True
    return (
        left.duration_status != DurationStatus.UNKNOWN
        and right.duration_status != DurationStatus.UNKNOWN
        and left.duration_status != right.duration_status
    )


def _definitely_disjoint_in_time(left, right) -> bool:
    """仅在两个候选可证明前后分离时返回 True；未知边界保持保守。"""
    if isinstance(left, ClinicalFactCandidateV2):
        left_bounds = _known_fact_bounds(left)
        right_bounds = _known_fact_bounds(right)
    else:
        left_bounds = _known_span_bounds(left)
        right_bounds = _known_span_bounds(right)
    if left_bounds is None or right_bounds is None:
        return False
    left_start, left_end = left_bounds
    right_start, right_end = right_bounds
    return bool(
        (left_end is not None and left_end < right_start)
        or (right_end is not None and right_end < left_start)
    )


def _temporal_components(candidate_ids: list[str], candidates_by_id: dict) -> list[list[str]]:
    """按“时间不能证明互斥”关系生成稳定连通分量。"""
    remaining = set(candidate_ids)
    components: list[list[str]] = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        component = {seed}
        frontier = [seed]
        while frontier:
            current = frontier.pop()
            connected = sorted(
                candidate_id
                for candidate_id in remaining
                if not _definitely_disjoint_in_time(
                    candidates_by_id[current], candidates_by_id[candidate_id]
                )
            )
            for candidate_id in connected:
                remaining.remove(candidate_id)
                component.add(candidate_id)
                frontier.append(candidate_id)
        components.append(sorted(component))
    return components


def detect_semantic_conflicts(
    *,
    authority: FactAuthority,
    fact_candidates: list[ClinicalFactCandidateV2],
    event_candidates: list[ClinicalEventCandidateV2],
    exposure_candidates: list[MedicationExposureCandidateV2],
) -> list[SemanticConflictGroup]:
    """同一语义对象在时间可重叠且临床内容不兼容时建立冲突组。

    可证明时间前后分离的数值、事件或用药变化属于纵向历程，不是冲突。日期未知、
    部分日期重叠或边界相接时保守保留冲突，绝不自动选择赢家。
    """
    stable_map = compute_stable_identity_map(
        authority=authority,
        fact_candidates=fact_candidates,
        event_candidates=event_candidates,
        exposure_candidates=exposure_candidates,
    )
    # 语义键 -> candidate_ids
    sem_to_cids: dict[str, list[str]] = {}
    sem_to_type: dict[str, Literal["fact", "event", "exposure"]] = {}
    for fact_candidate in fact_candidates:
        k = _fact_semantic_key(fact_candidate)
        sem_to_cids.setdefault(k, []).append(fact_candidate.candidate_id)
        sem_to_type[k] = "fact"
    facts_by_id = {candidate.candidate_id: candidate for candidate in fact_candidates}
    for event_candidate in event_candidates:
        k = _event_semantic_key(event_candidate, facts_by_id)
        sem_to_cids.setdefault(k, []).append(event_candidate.candidate_id)
        sem_to_type[k] = "event"
    for exposure_candidate in exposure_candidates:
        k = _exposure_semantic_key(exposure_candidate)
        sem_to_cids.setdefault(k, []).append(exposure_candidate.candidate_id)
        sem_to_type[k] = "exposure"

    candidates_by_id = {
        candidate.candidate_id: candidate
        for candidate in [*fact_candidates, *event_candidates, *exposure_candidates]
    }

    # 收集定位用于 affected_scope（候选级受影响范围另算）
    locator_map: dict[str, list[str]] = {}
    for fact_candidate in fact_candidates:
        locator_map[fact_candidate.candidate_id] = list(fact_candidate.locator_ids)
    for event_candidate in event_candidates:
        locator_map[event_candidate.candidate_id] = list(event_candidate.locator_ids)
    for exposure_candidate in exposure_candidates:
        locator_map[exposure_candidate.candidate_id] = list(exposure_candidate.locator_ids)

    groups: list[SemanticConflictGroup] = []
    for sem_key in sorted(sem_to_cids.keys()):
        stype = sem_to_type[sem_key]
        for cids in _temporal_components(
            sorted(set(sem_to_cids[sem_key])), candidates_by_id
        ):
            if len(cids) < 2:
                continue
            if stype == "exposure":
                if not any(
                    _exposures_have_known_conflict(
                        candidates_by_id[left_id], candidates_by_id[right_id]
                    )
                    for index, left_id in enumerate(cids)
                    for right_id in cids[index + 1 :]
                ):
                    continue
            else:
                signatures = {
                    _clinical_payload_signature(candidates_by_id[cid]) for cid in cids
                }
                if len(signatures) < 2:
                    continue
            distinct_sids = sorted({stable_map[cid] for cid in cids})
            if stype == "fact":
                reasons = ["同一时间范围内或时间重叠无法排除时，事实值、极性或单位不兼容"]
            elif stype == "event":
                reasons = ["同一事件在时间重叠无法排除时，持续状态不兼容"]
            else:
                reasons = ["同一用药或治疗在时间重叠无法排除时，剂量、频次、途径或状态不兼容"]
            merged_locators = {
                locator_id for cid in cids for locator_id in locator_map.get(cid, [])
            }
            groups.append(
                SemanticConflictGroup(
                    semantic_key=sem_key,
                    semantic_type=stype,
                    candidate_ids=cids,
                    distinct_stable_identities=distinct_sids,
                    reasons=reasons,
                    affected_scope=sorted(merged_locators | set(cids)),
                )
            )
    groups.sort(key=lambda g: g.semantic_key)
    return groups


# ---------------------------------------------------------------------------
# 逐候选去重/冲突门禁
# ---------------------------------------------------------------------------


def gate_in_document_dedup_conflict(
    *,
    authority: FactAuthority,
    fact_candidates: list[ClinicalFactCandidateV2],
    event_candidates: list[ClinicalEventCandidateV2],
    exposure_candidates: list[MedicationExposureCandidateV2],
) -> dict[str, GateVerdict]:
    """处理 ``IN_DOCUMENT_DEDUP_CONFLICT`` 门禁。

    精确重复不视为失败：同一稳定身份的多个候选在该门禁中均为 ACCEPTED，
    但 ``affected_scope`` 为同一去重组内其他候选 ID（有序去重），便于审计
    “合并引用但保留全部定位” 的语义。唯一候选的 affected_scope 为空。
    """
    dedup_groups = group_exact_duplicates(
        authority=authority,
        fact_candidates=fact_candidates,
        event_candidates=event_candidates,
        exposure_candidates=exposure_candidates,
    )
    # 建立 candidate_id -> 其他重复成员
    other_map: dict[str, list[str]] = {}
    for g in dedup_groups:
        for cid in g.candidate_ids:
            others = [o for o in g.candidate_ids if o != cid]
            other_map[cid] = sorted(set(others))

    result: dict[str, GateVerdict] = {}
    all_cands = (
        [(c.candidate_id) for c in fact_candidates]
        + [(c.candidate_id) for c in event_candidates]
        + [(c.candidate_id) for c in exposure_candidates]
    )
    for cid in sorted(set(all_cands)):
        affected = other_map.get(cid, [])
        # 去重组内候选的 GateVerdict 仍为 ACCEPTED，但 affected_scope 指向其他重复者
        # 以满足“可追踪去重”的审计需求；非重复者 affected_scope 为空。
        if affected:
            result[cid] = GateVerdict(
                candidate_id=cid,
                gate=FactGate.IN_DOCUMENT_DEDUP_CONFLICT,
                outcome=GateOutcome.ACCEPTED,
                reasons=[],
                affected_scope=affected,
            )
        else:
            result[cid] = GateVerdict(
                candidate_id=cid,
                gate=FactGate.IN_DOCUMENT_DEDUP_CONFLICT,
                outcome=GateOutcome.ACCEPTED,
                reasons=[],
                affected_scope=[],
            )
    return result


def gate_cross_document_merge_conflict(
    *,
    authority: FactAuthority,
    fact_candidates: list[ClinicalFactCandidateV2],
    event_candidates: list[ClinicalEventCandidateV2],
    exposure_candidates: list[MedicationExposureCandidateV2],
) -> dict[str, GateVerdict]:
    """处理 ``CROSS_DOCUMENT_MERGE_CONFLICT`` 门禁（不择优）。

    对每个参与语义冲突的候选仍产生 ACCEPTED 裁决并保留受影响成员；冲突本身
    由 ``SemanticConflictGroup`` 并列发布，不能因为存在冲突而丢弃全部成员。
    affected_scope 为同一冲突组内其他候选 ID（有序去重）；未参与冲突的
    候选为 ACCEPTED。
    """
    conflict_groups = detect_semantic_conflicts(
        authority=authority,
        fact_candidates=fact_candidates,
        event_candidates=event_candidates,
        exposure_candidates=exposure_candidates,
    )
    # candidate_id -> (reasons, 其他冲突成员)
    conflict_map: dict[str, tuple[list[str], list[str]]] = {}
    for g in conflict_groups:
        for cid in g.candidate_ids:
            others = [o for o in g.candidate_ids if o != cid]
            # 合并同一候选可能参与多个语义键？理论上单一类型仅一个键，但防御性合并
            existing_reasons, existing_others = conflict_map.get(cid, ([], []))
            merged_reasons = sorted(set(existing_reasons) | set(g.reasons))
            merged_others = sorted(set(existing_others) | set(others))
            conflict_map[cid] = (merged_reasons, merged_others)

    result: dict[str, GateVerdict] = {}
    all_cids = (
        [c.candidate_id for c in fact_candidates]
        + [c.candidate_id for c in event_candidates]
        + [c.candidate_id for c in exposure_candidates]
    )
    for cid in sorted(set(all_cids)):
        if cid in conflict_map:
            _reasons, others = conflict_map[cid]
            result[cid] = GateVerdict(
                candidate_id=cid,
                gate=FactGate.CROSS_DOCUMENT_MERGE_CONFLICT,
                outcome=GateOutcome.ACCEPTED,
                reasons=[],
                affected_scope=others,
            )
        else:
            result[cid] = GateVerdict(
                candidate_id=cid,
                gate=FactGate.CROSS_DOCUMENT_MERGE_CONFLICT,
                outcome=GateOutcome.ACCEPTED,
                reasons=[],
                affected_scope=[],
            )
    return result


# ---------------------------------------------------------------------------
# 批次级失败行为：空输出 / 页覆盖不完整
# ---------------------------------------------------------------------------


def _validate_batch_not_empty(
    fact_candidates: list[ClinicalFactCandidateV2],
    event_candidates: list[ClinicalEventCandidateV2],
    exposure_candidates: list[MedicationExposureCandidateV2],
) -> tuple[GateOutcome, list[str], list[str]]:
    total = len(fact_candidates) + len(event_candidates) + len(exposure_candidates)
    if total == 0:
        return (
            GateOutcome.REJECTED,
            ["批次候选为空，无法生成临床事实（空输出不生成空 Profile）"],
            [],
        )
    return GateOutcome.ACCEPTED, [], []


def _gate_verdicts_for_page_coverage_failure(
    *,
    run_id: str,
    call_id: str,
    candidate_ids: list[str],
    reasons: list[str],
    affected: list[str],
) -> list[GateVerdict]:
    """为页覆盖失败生成逐候选的 PAGE_COVERAGE 门禁 REJECTED 裁决。"""
    verdicts: list[GateVerdict] = []
    for cid in sorted(set(candidate_ids)):
        verdicts.append(
            GateVerdict(
                candidate_id=cid,
                gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
                outcome=GateOutcome.REJECTED,
                reasons=list(reasons),
                affected_scope=list(affected),
            )
        )
    verdicts.sort(key=lambda v: (v.candidate_id, v.gate.value))
    return verdicts


# ---------------------------------------------------------------------------
# 确定性批量编排主入口
# ---------------------------------------------------------------------------


def orchestrate_batch_gates(
    *,
    authority: FactAuthority,
    run_id: str,
    call_id: str,
    fact_candidates: list[ClinicalFactCandidateV2],
    event_candidates: list[ClinicalEventCandidateV2],
    exposure_candidates: list[MedicationExposureCandidateV2],
    revision=None,
    calls: list[FactNormalizationCall] | None = None,
    session: Session | None = None,
) -> BatchGateResult:
    """确定性批量门禁编排主函数。

    顺序（与设计书 §4.2 一致，纯确定性子集）：
    1. 空输出检查（批次级失败）；
    2. 页覆盖检查（若提供 revision+calls）；
    3. 精确重复分组（IN_DOCUMENT）与语义冲突检测（CROSS_DOCUMENT）；
    4. 生成逐候选 GateVerdict 并聚合为 BatchGateResult。

    返回的 ``BatchGateResult`` 包含去重组、冲突组、逐候选裁决与批次整体
    受影响范围，确定性排序，不发布事实或 Profile。
    """
    # 0. 基础校验：批次内 ID 排序（合同已保证，但此处防御性）
    all_cids = (
        [c.candidate_id for c in fact_candidates]
        + [c.candidate_id for c in event_candidates]
        + [c.candidate_id for c in exposure_candidates]
    )
    # 1. 空输出失败
    empty_outcome, empty_reasons, empty_affected = _validate_batch_not_empty(
        fact_candidates, event_candidates, exposure_candidates
    )
    if empty_outcome != GateOutcome.ACCEPTED:
        return BatchGateResult(
            run_id=run_id,
            call_id=call_id,
            overall_outcome=GateOutcome.REJECTED,
            failure_reasons=list(empty_reasons),
            dedup_groups=[],
            conflict_groups=[],
            gate_results=[],
            affected_scope=list(empty_affected),
        )

    # 2. 页覆盖检查（可选）
    failure_reasons: list[str] = []
    page_verdicts: list[GateVerdict] = []
    page_affected: list[str] = []
    overall = GateOutcome.ACCEPTED
    if revision is not None and calls is not None:
        from app.domain.gates.fact_evidence_closure import validate_page_coverage

        outcome, reasons, affected = validate_page_coverage(revision, calls, session=session)
        if outcome != GateOutcome.ACCEPTED:
            failure_reasons.extend(reasons)
            page_affected = list(affected)
            overall = GateOutcome.REJECTED
            # 为每个候选生成 PAGE_COVERAGE 的 REJECTED 裁决
            page_verdicts = _gate_verdicts_for_page_coverage_failure(
                run_id=run_id,
                call_id=call_id,
                candidate_ids=all_cids,
                reasons=reasons,
                affected=affected,
            )
        else:
            # 页覆盖通过时，逐候选也生成 ACCEPTED 的页覆盖裁决以满足持久化审计
            for cid in sorted(set(all_cids)):
                page_verdicts.append(
                    GateVerdict(
                        candidate_id=cid,
                        gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
                        outcome=GateOutcome.ACCEPTED,
                        reasons=[],
                        affected_scope=[],
                    )
                )
            page_verdicts.sort(key=lambda v: (v.candidate_id, v.gate.value))

    # 3. 去重与冲突分组（纯确定性）
    dedup_groups = group_exact_duplicates(
        authority=authority,
        fact_candidates=fact_candidates,
        event_candidates=event_candidates,
        exposure_candidates=exposure_candidates,
    )
    conflict_groups = detect_semantic_conflicts(
        authority=authority,
        fact_candidates=fact_candidates,
        event_candidates=event_candidates,
        exposure_candidates=exposure_candidates,
    )

    # 4. 逐候选去重/冲突门禁
    dedup_verdicts_map = gate_in_document_dedup_conflict(
        authority=authority,
        fact_candidates=fact_candidates,
        event_candidates=event_candidates,
        exposure_candidates=exposure_candidates,
    )
    conflict_verdicts_map = gate_cross_document_merge_conflict(
        authority=authority,
        fact_candidates=fact_candidates,
        event_candidates=event_candidates,
        exposure_candidates=exposure_candidates,
    )

    # 5. 聚合逐候选 gate_results（确定性排序）
    gate_results: list[GateVerdict] = []
    gate_results.extend(page_verdicts)
    for cid in sorted(set(all_cids)):
        if cid in dedup_verdicts_map:
            gate_results.append(dedup_verdicts_map[cid])
        if cid in conflict_verdicts_map:
            gate_results.append(conflict_verdicts_map[cid])
    # 若未提供 revision，则不生成 PAGE_COVERAGE 的 gate_results（由上层保证）
    gate_results.sort(key=lambda v: (v.candidate_id, v.gate.value))

    # 6. 计算整体 outcome 与受影响范围
    # 整体 REJECTED 若任一关键门禁为 REJECTED/BLOCKED，或冲突存在时也视为 REJECTED？
    # 按任务要求：精确重复不导致批次失败；语义冲突导致相关候选 REJECTED，但批次整体标记为 REJECTED 以触发未解决冲突展示。
    has_page_rejected = any(
        v.gate == FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE and v.outcome != GateOutcome.ACCEPTED
        for v in gate_results
    )
    if has_page_rejected or failure_reasons:
        overall = GateOutcome.REJECTED
    else:
        overall = GateOutcome.ACCEPTED

    # 聚合 affected_scope：全部去重组+冲突组+页覆盖的 affected 并集
    affected_set: set[str] = set(page_affected)
    for dedup_group in dedup_groups:
        affected_set.update(dedup_group.candidate_ids)
        affected_set.update(dedup_group.merged_locator_ids)
    for conflict_group in conflict_groups:
        affected_set.update(conflict_group.candidate_ids)
        affected_set.update(conflict_group.affected_scope)
    for v in gate_results:
        if v.outcome != GateOutcome.ACCEPTED:
            affected_set.update(v.affected_scope)
    # 空输出与页覆盖的 affected 已在 page_affected 中；去重/冲突的 candidate_ids 已加入
    affected_scope = sorted(affected_set)

    # 若 overall 为 REJECTED 但 failure_reasons 为空，补充来自 gate_results 的 reasons
    if overall != GateOutcome.ACCEPTED and not failure_reasons:
        merged_reasons: set[str] = set()
        for v in gate_results:
            if v.outcome != GateOutcome.ACCEPTED:
                merged_reasons.update(v.reasons)
        if merged_reasons:
            failure_reasons = sorted(merged_reasons)

    # 保证 dedup/conflict 已排序（合同要求）
    dedup_groups_sorted = sorted(dedup_groups, key=lambda g: g.stable_identity)
    conflict_groups_sorted = sorted(conflict_groups, key=lambda g: g.semantic_key)

    return BatchGateResult(
        run_id=run_id,
        call_id=call_id,
        overall_outcome=overall,
        failure_reasons=sorted(set(failure_reasons)) if failure_reasons else [],
        dedup_groups=dedup_groups_sorted,
        conflict_groups=conflict_groups_sorted,
        gate_results=sorted(gate_results, key=lambda v: (v.candidate_id, v.gate.value)),
        affected_scope=affected_scope,
    )


# ---------------------------------------------------------------------------
# 持久化衔接（deterministic GateResult）
# ---------------------------------------------------------------------------


def batch_gate_results_to_fact_gate_results(
    batch_result: BatchGateResult,
    *,
    created_at: datetime | None = None,
    id_prefix: str = "gate",
) -> list[FactGateResult]:
    """将 ``BatchGateResult`` 的逐候选裁决扁平为可持久化的 ``FactGateResult`` 列表。

    ``created_at`` 必须为 UTC；未提供时使用当前 UTC。
    ``gate_result_id`` 格式为 ``{id_prefix}-{candidate_id}-{gate.value}``，
    确定性且与 ``fact_candidate_gates.verdicts_to_gate_results`` 一致。
    """
    if created_at is None:
        created_at = _utc_now()
    if created_at.tzinfo is None or created_at.utcoffset() is None or created_at.utcoffset().total_seconds() != 0:  # type: ignore[union-attr]
        raise ValueError("created_at 必须为 UTC 时区")

    results: list[FactGateResult] = []
    for verdict in sorted(batch_result.gate_results, key=lambda v: (v.candidate_id, v.gate.value)):
        gate_result_id = f"{id_prefix}-{verdict.candidate_id}-{verdict.gate.value}"
        results.append(
            FactGateResult(
                gate_result_id=gate_result_id,
                run_id=batch_result.run_id,
                call_id=batch_result.call_id,
                candidate_id=verdict.candidate_id,
                gate=verdict.gate,
                outcome=verdict.outcome,
                reasons=list(verdict.reasons),
                created_at=created_at,
            )
        )
    # 批次级失败若无逐候选记录但有 failure_reasons，则生成一条批次级合成 GateResult
    # 以满足“持久化 per-candidate outcomes” 的审计要求——空输出时无候选，不生成。
    return sorted(results, key=lambda r: (r.candidate_id, r.gate.value))


def persist_batch_gate_results(
    batch_result: BatchGateResult,
    session: Session,
    *,
    created_at: datetime | None = None,
) -> list[FactGateResult]:
    """通过 ``FactGateResultRepository`` 批量持久化批次门禁结果。

    仅写入 ``FactGateResult``，不触碰 ``ClinicalFactV2`` 等发布表。
    空输出批次返回空列表。
    """
    from app.storage.fact_repositories import FactGateResultRepository

    if not batch_result.gate_results:
        return []
    gate_results = batch_gate_results_to_fact_gate_results(batch_result, created_at=created_at)
    repo = FactGateResultRepository(session)
    return repo.create_many(gate_results)


def orchestrate_run_gates(
    *,
    authority: FactAuthority,
    run_id: str,
    calls: list[FactNormalizationCall],
    fact_candidates: list[ClinicalFactCandidateV2],
    event_candidates: list[ClinicalEventCandidateV2],
    exposure_candidates: list[MedicationExposureCandidateV2],
    revision=None,
    session: Session | None = None,
) -> RunGateResult:
    """跨 call 执行一次 run 的完整 Slice 5.2 确定性门禁。"""
    from app.domain.gates.fact_candidate_gates import (
        batch_gate_candidates,
        merge_gate_verdict_maps,
        validate_linked_candidate_locator_closure,
    )
    from app.domain.gates.fact_evidence_closure import batch_gate_evidence_closure

    if not calls:
        raise ValueError("run 至少需要一个真实调用")
    if revision is None:
        raise ValueError("run 必须提供当前完整处理修订以校验真实页覆盖")
    call_by_id = {call.call_id: call for call in calls}
    if len(call_by_id) != len(calls) or any(call.run_id != run_id for call in calls):
        raise ValueError("run 的调用必须唯一且全部属于当前 run")
    unsuccessful_calls = sorted(
        call.call_id for call in calls if call.status != FactCallStatus.SUCCEEDED
    )
    if unsuccessful_calls:
        raise ValueError(
            "run 的页覆盖只能使用已成功调用：" + ", ".join(unsuccessful_calls)
        )
    all_candidates: list[
        ClinicalFactCandidateV2 | ClinicalEventCandidateV2 | MedicationExposureCandidateV2
    ] = [*fact_candidates, *event_candidates, *exposure_candidates]
    candidate_call_ids: dict[str, str] = {}
    for candidate in all_candidates:
        if candidate.run_id != run_id or candidate.call_id not in call_by_id:
            raise ValueError(f"候选 {candidate.candidate_id} 不属于当前 run/call 闭包")
        if candidate.candidate_id in candidate_call_ids:
            raise ValueError(f"候选 ID {candidate.candidate_id} 在 run 内重复")
        candidate_call_ids[candidate.candidate_id] = candidate.call_id

    authority_errors = _authority_revision_errors(authority, revision, session)
    contract_authority_map = {
        candidate.candidate_id: {
            FactGate.CONTRACT_AND_ENUM: GateVerdict(
                candidate_id=candidate.candidate_id,
                gate=FactGate.CONTRACT_AND_ENUM,
                outcome=GateOutcome.ACCEPTED,
                reasons=[],
                affected_scope=[],
            ),
            FactGate.AUTHORITY_AND_ACTIVE_REVISION: GateVerdict(
                candidate_id=candidate.candidate_id,
                gate=FactGate.AUTHORITY_AND_ACTIVE_REVISION,
                outcome=(
                    GateOutcome.REJECTED if authority_errors else GateOutcome.ACCEPTED
                ),
                reasons=authority_errors,
                affected_scope=(
                    [authority.complete_processing_revision_id]
                    if authority_errors
                    else []
                ),
            ),
        }
        for candidate in all_candidates
    }

    pure_maps: list[dict[str, dict[FactGate, GateVerdict]]] = [
        contract_authority_map
    ]
    for call in calls:
        pure_maps.append(
            batch_gate_candidates(
                fact_candidates=[c for c in fact_candidates if c.call_id == call.call_id],
                event_candidates=[c for c in event_candidates if c.call_id == call.call_id],
                exposure_candidates=[c for c in exposure_candidates if c.call_id == call.call_id],
                run_id=run_id,
                call_id=call.call_id,
            )
        )

    # 事件/暴露允许引用本 run 其他文档 call 的事实；单 call 校验产生的悬空错误
    # 在 run 闭包中重新裁决。
    fact_candidates_by_id = {
        candidate.candidate_id: candidate for candidate in fact_candidates
    }
    linked_candidates: list[ClinicalEventCandidateV2 | MedicationExposureCandidateV2] = [
        *event_candidates,
        *exposure_candidates,
    ]
    for candidate in linked_candidates:
        errors = validate_linked_candidate_locator_closure(
            candidate, fact_candidates_by_id
        )
        affected = sorted(
            set(candidate.fact_candidate_ids) - set(fact_candidates_by_id)
            | {
                locator_id
                for locator_id in candidate.locator_ids
                if locator_id
                not in {
                    referenced_locator_id
                    for fact_id in candidate.fact_candidate_ids
                    if fact_id in fact_candidates_by_id
                    for referenced_locator_id in fact_candidates_by_id[fact_id].locator_ids
                }
            }
        )
        verdict = GateVerdict(
            candidate_id=candidate.candidate_id,
            gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
            outcome=GateOutcome.REJECTED if errors else GateOutcome.ACCEPTED,
            reasons=errors,
            affected_scope=affected,
        )
        for mapping in pure_maps:
            if candidate.candidate_id in mapping:
                mapping[candidate.candidate_id][FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE] = verdict

    batch = orchestrate_batch_gates(
        authority=authority,
        run_id=run_id,
        call_id=calls[0].call_id,
        fact_candidates=fact_candidates,
        event_candidates=event_candidates,
        exposure_candidates=exposure_candidates,
        revision=revision,
        calls=calls,
        session=session,
    )
    batch_map: dict[str, dict[FactGate, GateVerdict]] = {}
    for verdict in batch.gate_results:
        batch_map.setdefault(verdict.candidate_id, {})[verdict.gate] = verdict

    maps = [*pure_maps, batch_map]
    if session is not None and revision is not None:
        maps.append(
            batch_gate_evidence_closure(
                session,
                revision,
                calls,
                fact_candidates,
                event_candidates,
                exposure_candidates,
            )
        )
    merged = merge_gate_verdict_maps(*maps)
    gate_results = [
        verdict
        for candidate_id in sorted(merged)
        for _, verdict in sorted(merged[candidate_id].items(), key=lambda item: item[0].value)
    ]

    failure_reasons = list(batch.failure_reasons)
    empty_calls = sorted(set(call_by_id) - set(candidate_call_ids.values()))
    if empty_calls:
        failure_reasons.append(f"调用无候选输出：{', '.join(empty_calls)}")
    for verdict in gate_results:
        if verdict.outcome != GateOutcome.ACCEPTED:
            failure_reasons.extend(verdict.reasons)
    overall = GateOutcome.ACCEPTED
    if any(v.outcome == GateOutcome.BLOCKED for v in gate_results):
        overall = GateOutcome.BLOCKED
    elif failure_reasons or any(v.outcome == GateOutcome.REJECTED for v in gate_results):
        overall = GateOutcome.REJECTED
    affected = sorted(
        set(batch.affected_scope)
        | {item for verdict in gate_results for item in verdict.affected_scope}
        | set(empty_calls)
    )
    return RunGateResult(
        run_id=run_id,
        call_ids=sorted(call_by_id),
        candidate_call_ids=dict(sorted(candidate_call_ids.items())),
        overall_outcome=overall,
        failure_reasons=sorted(set(failure_reasons)),
        dedup_groups=batch.dedup_groups,
        conflict_groups=batch.conflict_groups,
        gate_results=gate_results,
        affected_scope=affected,
    )


def run_gate_results_to_fact_gate_results(
    run_result: RunGateResult,
    *,
    created_at: datetime,
    id_prefix: str = "gate",
) -> list[FactGateResult]:
    """按真实 call 归属生成唯一可持久化结果。"""
    return [
        FactGateResult(
            gate_result_id=f"{id_prefix}-{run_result.run_id}-{v.candidate_id}-{v.gate.value}",
            run_id=run_result.run_id,
            call_id=run_result.candidate_call_ids[v.candidate_id],
            candidate_id=v.candidate_id,
            gate=v.gate,
            outcome=v.outcome,
            reasons=v.reasons,
            created_at=created_at,
        )
        for v in run_result.gate_results
    ]
