"""Phase 5 Slice 5.2 证据闭包适配器（含仓储校验）。

覆盖 PRD P5-R03 / 设计书 §4.2 中依赖 Phase 4 持久化闭包的确定性校验：

- Gate PAGE_COVERAGE_AND_REFERENCE_CLOSURE 中的页覆盖部分：run/call 页清单必须
  完整覆盖当前完整处理修订的页清单（无整页遗漏、额外页或重复页），缺失/多余/重复
  均视为确定性 REJECTED，不生成空 Profile；
- Gate LOCATOR_AND_TEXT_HASH：候选的 locator_ids 必须全部属于当前完整处理修订的
  locator_ids，通过仓储还原并校验定位真实性（authenticated current-revision），
  页产物/OCR 页闭包与有效文本投影哈希必须一致，虚构定位、跨修订/跨页定位、
  原文哈希不一致均 REJECTED；
- 候选级阻断 OCR 风险：若候选任一定位所在页的 BLOCKING 级风险未被当前完整
  修订的 risk_review_ids 或 correction_ids 解除，且与定位范围重叠，则该候选
  BLOCKED（仅阻断相关候选，其余仍可发布），并记录受影响定位。

所有函数均为确定性：给定相同的 revision / calls / candidate 与数据库状态，
输出的 outcome / reasons / affected_scope 完全一致，不调用模型，不发布事实，
不产生随机性。持久化仅通过 ``FactGateResultRepository`` 写入逐候选门禁结果，
不触碰 ``ClinicalFactV2`` 等发布表。

与 ``fact_candidate_gates`` 的协作：
- 纯校验（极性/值/日期/来源/引用闭包）由候选门禁负责；
- 本模块仅负责需要仓库认证的证据闭包部分，二者可在批次编排中合并。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.contracts.enums import (
    FactGate,
    FactPolarity,
    GateOutcome,
    LocatorPrecision,
    LocatorSourceLayer,
    OcrRiskLevel,
    SourceStrength,
)
from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision
from app.domain.contracts.fact_gates import GateVerdict
from app.domain.contracts.facts import (
    ClinicalEventCandidateV2,
    ClinicalFactCandidateV2,
    FactGateResult,
    FactNormalizationCall,
    MedicationExposureCandidateV2,
)
from app.storage.repositories import RepositoryError

_CANDIDATE_UNION = (ClinicalFactCandidateV2, ClinicalEventCandidateV2, MedicationExposureCandidateV2)

# --------------------------------------------------------------------------- 工具
def _affected_locators(candidate) -> list[str]:
    locs = getattr(candidate, "locator_ids", []) or []
    return sorted(set(locs))


def _utc_now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- 页覆盖
def validate_page_coverage(
    revision: CompleteEvidenceProcessingRevision,
    calls: list[FactNormalizationCall],
    session: Session | None = None,
) -> tuple[GateOutcome, list[str], list[str]]:
    """校验 run/call 页清单对完整处理修订页清单的完整覆盖。

    确定性规则（设计书 §4.1/§4.2）：
    - 完整修订的 ``manifest`` 必须非空；
    - 每个 ``call.page_numbers`` 已由合同保证升序无重复，此处再校验跨 call
      不允许同一 ``(logical_document_id, page_number)`` 重复出现；
    - 所有 call 的 ``(logical_document_id, page_number)`` 并集必须精确等于
      完整修订期望的页集合，无缺页/多余页/重复页；
    - 期望页集合优先通过快照成员表将 ``source_document_version_id`` 映射为
      ``logical_document_id``（若 session 可查询且映射完整），否则回退为
      直接以 ``source_document_version_id`` 作为逻辑文档标识（测试简化路径）。

    返回 ``(outcome, reasons, affected_scope)``，其中 ``affected_scope`` 为
    缺失/多余/重复的页标识 ``"{doc}:{page}"`` 升序去重，满足 ``GateVerdict``
    的排序约束。无错误时 ``affected_scope`` 为空（或可由上层填充为候选定位，
    本函数保持纯页标识以便批次聚合）。
    """
    reasons: list[str] = []
    affected: list[str] = []

    if not revision.manifest:
        return GateOutcome.REJECTED, ["完整处理修订页清单为空，无法校验页覆盖"], []

    # 构建期望集合：尝试通过快照映射 source_version -> logical
    logical_by_source: dict[str, str] = {}
    if session is not None:
        try:
            from app.storage.evidence_models import EvidenceSnapshotMemberRecord

            rows = session.execute(
                select(EvidenceSnapshotMemberRecord).where(
                    EvidenceSnapshotMemberRecord.snapshot_id == revision.evidence_snapshot_id
                )
            ).scalars().all()
            for r in rows:
                logical_by_source[r.source_document_version_id] = r.logical_document_id
        except SQLAlchemyError:
            logical_by_source = {}

    expected: set[tuple[str, int]] = set()
    for entry in revision.manifest:
        logical = logical_by_source.get(entry.source_document_version_id, entry.source_document_version_id)
        expected.add((logical, entry.page_number))

    # 实际集合：跨 call 合并，检测重复
    actual: set[tuple[str, int]] = set()
    seen_counts: dict[tuple[str, int], int] = {}
    for call in calls:
        for page in call.page_numbers:
            key = (call.logical_document_id, page)
            seen_counts[key] = seen_counts.get(key, 0) + 1
            actual.add(key)

    duplicates = sorted([f"{doc}:{page}" for (doc, page), cnt in seen_counts.items() if cnt > 1])
    if duplicates:
        reasons.append(f"页覆盖存在重复页：{', '.join(duplicates)}")
        affected.extend(duplicates)

    missing = sorted([f"{doc}:{page}" for doc, page in (expected - actual)])
    if missing:
        reasons.append(f"页覆盖缺失 {len(missing)} 页：{', '.join(missing)}")
        affected.extend(missing)

    extra = sorted([f"{doc}:{page}" for doc, page in (actual - expected)])
    if extra:
        reasons.append(f"页覆盖多余 {len(extra)} 页：{', '.join(extra)}")
        affected.extend(extra)

    affected_sorted = sorted(set(affected))
    if reasons:
        return GateOutcome.REJECTED, reasons, affected_sorted
    return GateOutcome.ACCEPTED, [], []


def validate_page_coverage_per_candidate(
    revision: CompleteEvidenceProcessingRevision,
    calls: list[FactNormalizationCall],
    candidate,
    session: Session | None = None,
) -> GateVerdict:
    """为单个候选生成页覆盖门禁的 ``GateVerdict``。

    页覆盖是批次级属性，但需持久化为逐候选结果以满足
    “逐候选 accepted/rejected + 受影响范围” 的审计要求。
    若批次页覆盖失败，则该候选的此门禁为 REJECTED，
    affected_scope 为缺失/多余/重复页标识；否则 ACCEPTED。
    """
    outcome, reasons, affected = validate_page_coverage(revision, calls, session=session)
    # 若通过，affected_scope 按合同应为候选定位的有序集合或空；
    # 此处保持空以区分页标识与定位标识，批次聚合时可按需合并。
    if outcome == GateOutcome.ACCEPTED:
        return GateVerdict(
            candidate_id=candidate.candidate_id,
            gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            affected_scope=[],
        )
    return GateVerdict(
        candidate_id=candidate.candidate_id,
        gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
        outcome=outcome,
        reasons=reasons,
        affected_scope=affected,
    )


# --------------------------------------------------------------------------- 定位与哈希
def _fetch_locator(session: Session, locator_id: str):
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository

    repo = EvidenceLocatorRepository(session)
    return repo.get(locator_id)


def _manifest_page_set(revision: CompleteEvidenceProcessingRevision) -> set[tuple[str, int]]:
    return {(e.page_artifact_id, e.page_number) for e in revision.manifest}


def _localized_locator_text(session: Session, locator, revision) -> str | None:
    """还原当前定位实际覆盖的原文；page_only 不足以证明断言。"""
    if locator.precision == LocatorPrecision.PAGE_ONLY:
        return None
    if locator.precision == LocatorPrecision.PAGE_EXCERPT:
        return locator.excerpt
    if locator.ocr_page_id is None:
        return None
    from app.storage.ocr_models import OCRPageRecord

    ocr = session.get(OCRPageRecord, locator.ocr_page_id)
    if ocr is None:
        return None
    text = ocr.raw_text
    if locator.source_layer == LocatorSourceLayer.EFFECTIVE_TEXT:
        from app.evidence.effective_text import project_effective_text
        from app.storage.evidence_locator_repositories import CorrectionRepository

        corrections = [
            CorrectionRepository(session).get(correction_id)
            for correction_id in revision.correction_ids
        ]
        text = project_effective_text(
            text, [item for item in corrections if item.ocr_page_id == locator.ocr_page_id]
        ).effective_text
    if locator.text_start is None or locator.text_end is None:
        return None
    return text[locator.text_start : locator.text_end]


def _has_explicit_negation_relation(assertion: str, asserted_object: str) -> bool:
    """保守确认否定表达直接支配对象，拒绝“对象存在但未治疗”等伪否定。"""
    text = " ".join(assertion.lower().split())
    target = re.escape(" ".join(asserted_object.lower().split()))
    chinese_target_end = rf"{target}(?:病史)?(?=\s*(?:$|[，,。；;]))"
    english_target_end = rf"{target}(?:\s+history)?(?=\s*(?:$|[,.;]))"
    prefix_patterns = (
        rf"无\s*{chinese_target_end}",
        rf"(?:未见|没有|不伴|排除)\s*{chinese_target_end}",
        rf"未(?:发现|提示|检出|诊断为|诊断)\s*{chinese_target_end}",
        rf"否认[^，,。；;]{{0,32}}{chinese_target_end}",
        rf"(?:^|[\s,;:])(?:no|denies?|without)\s+(?:history\s+of\s+)?{english_target_end}",
    )
    suffix_patterns = (
        rf"{target}(?:病史)?\s*[：:]\s*(?:否认|无|未见|阴性|\(?-\)?)(?=\s*(?:$|[，,。；;]))",
        rf"{target}病史\s*(?:为)?\s*否认(?=\s*(?:$|[，,。；;]))",
        rf"{target}(?:病史)?\s*[（(]-[）)]",
        rf"{target}\s+(?:is\s+)?(?:not\s+present|negative|denied)(?:\b|$)",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in (*prefix_patterns, *suffix_patterns))


def _validate_assertion_text_closure(session: Session, candidate, revision) -> list[str]:
    if not isinstance(candidate, ClinicalFactCandidateV2) or candidate.assertion_basis is None:
        return []
    basis = candidate.assertion_basis
    locator = _fetch_locator(session, basis.locator_id)
    localized = _localized_locator_text(session, locator, revision)
    if localized is None:
        return ["断言依据必须定位到当前有效原文的具体文本范围或摘录"]
    assertion = " ".join(basis.assertion_text.split())
    source = " ".join(localized.split())
    if basis.asserted_object not in assertion:
        return ["断言文本未包含被断言对象，不能借用邻近句"]
    if candidate.polarity == FactPolarity.NEGATED:
        if assertion not in source:
            return ["否定断言文本不在当前定位有效原文内"]
        clauses = [item.strip() for item in re.split(r"[。！？；;.!?]", assertion) if item.strip()]
        object_clauses = [item for item in clauses if basis.asserted_object in item]
        if not object_clauses or not any(
            _has_explicit_negation_relation(clause, basis.asserted_object)
            for clause in object_clauses
        ):
            return ["否定表达未直接约束被断言对象，拒绝邻近句、其他状态否定或沉默"]
    elif basis.asserted_object not in source:
        return ["被断言对象不在当前定位有效原文内"]
    return []


def validate_locator_and_text_hash(
    session: Session,
    candidate,
    revision: CompleteEvidenceProcessingRevision,
) -> tuple[GateOutcome, list[str], list[str]]:
    """校验候选定位闭包、真实性与原文哈希一致性（Gate LOCATOR_AND_TEXT_HASH）。

    规则：
    - candidate.locator_ids 必须非空且已由合同保证排序去重；
    - 每个 locator_id 必须属于 revision.locator_ids，否则视为虚构定位；
    - 每个 locator 必须可通过仓储还原，否则 REJECTED；
    - locator 的 page_artifact_id / page_number 必须出现在 revision.manifest；
    - 对于 effective_text 定位，其 processing_revision_id 必须等于当前完整修订；
    - 对于 ClinicalFactCandidate，若存在 assertion_basis，则
      basis.locator_id 必须属于候选定位集合且 basis.source_text_sha256
      必须等于对应 locator.source_text_sha256，且 basis.assertion_text 非空
     （后者已在纯校验中覆盖，此处仅校验哈希一致性）；
    - 抑制跨修订/跨页/虚构定位：任一失败即 REJECTED。

    返回 (outcome, reasons, affected_scope)，其中 affected_scope 为失败的
    locator_ids 排序去重，无失败时返回候选的全部定位（用于审计追踪）。
    """
    candidate_id = getattr(candidate, "candidate_id", "unknown")
    locator_ids: list[str] = list(getattr(candidate, "locator_ids", []) or [])
    revision_locator_set = set(revision.locator_ids)
    manifest_pages = _manifest_page_set(revision)
    manifest_page_artifact_ids = {e.page_artifact_id for e in revision.manifest}

    errors: list[str] = []
    failed_locators: set[str] = set()

    if not locator_ids:
        return GateOutcome.REJECTED, ["候选未提供任何定位引用"], []

    # 检查是否属于当前修订
    for lid in locator_ids:
        if lid not in revision_locator_set:
            errors.append(f"定位 {lid} 不在当前完整处理修订的定位清单中（虚构或跨修订定位）")
            failed_locators.add(lid)

    # 对属于修订的定位进一步验证真实性与页闭包
    for lid in locator_ids:
        if lid in failed_locators:
            # 已判定为虚构，仍尝试获取以给出更精确原因，但不掩盖虚构错误
            try:
                locator = _fetch_locator(session, lid)
            except RepositoryError as exc:
                errors.append(f"定位 {lid} 无法还原：{exc}")
                continue
            else:
                # 即便能还原，虚构错误已记录，不再追加页闭包错误
                continue
        try:
            locator = _fetch_locator(session, lid)
        except RepositoryError as exc:
            errors.append(f"定位 {lid} 不存在或无法验证：{exc}")
            failed_locators.add(lid)
            continue

        # 页闭包：locator 必须绑定 manifest 中的页
        if locator.page_artifact_id not in manifest_page_artifact_ids:
            errors.append(f"定位 {lid} 的页产物 {locator.page_artifact_id} 不在完整修订页清单中（跨页/虚构页）")
            failed_locators.add(lid)
            continue
        # 更细：page_number 亦需匹配（同一页产物可能对应不同页码？）
        # 通过 manifest_pages 校验 (page_artifact_id, page_number)
        if (locator.page_artifact_id, locator.page_number) not in manifest_pages:
            errors.append(f"定位 {lid} 的页码 {locator.page_number} 与完整修订页清单不一致")
            failed_locators.add(lid)

        # 真实性：若 authenticity 为 REJECTED，直接拒绝；DEGRADED 允许但需有原因
        # （EvidenceLocatorRepository 在写入时已校验，此处仅做读取侧复核）
        from app.domain.contracts.enums import LocatorAuthenticity

        if locator.authenticity == LocatorAuthenticity.REJECTED:
            errors.append(f"定位 {lid} 未通过真实性门禁（authenticity=rejected）")
            failed_locators.add(lid)

        # effective_text 绑定当前修订
        if (
            locator.source_layer == LocatorSourceLayer.EFFECTIVE_TEXT
            and locator.processing_revision_id != revision.evidence_processing_revision_id
        ):
            errors.append(f"有效文本定位 {lid} 未绑定当前完整修订（{locator.processing_revision_id} != {revision.evidence_processing_revision_id}）")
            failed_locators.add(lid)
            # effective_text_sha256 已在仓储保存时校验与投影一致，此处不重算
            # 但需保证 source_text_sha256 存在且为 64 位十六进制（合同已保证）

    # 原文哈希一致性：仅对 ClinicalFactCandidate 校验 assertion_basis
    if isinstance(candidate, ClinicalFactCandidateV2):
        basis = getattr(candidate, "assertion_basis", None)
        if basis is not None:
            basis_lid = basis.locator_id
            if basis_lid not in locator_ids:
                errors.append(f"断言依据定位 {basis_lid} 必须属于候选定位集合")
                failed_locators.add(basis_lid)
            else:
                # 仅当该定位未被判定为虚构且能还原时校验哈希
                if basis_lid not in failed_locators:
                    try:
                        locator = _fetch_locator(session, basis_lid)
                        if basis.source_text_sha256 != locator.source_text_sha256:
                            errors.append(f"候选 {candidate_id} 的原文哈希与定位 {basis_lid} 的源文本哈希不一致")
                            failed_locators.add(basis_lid)
                        closure_errors = _validate_assertion_text_closure(
                            session, candidate, revision
                        )
                        if closure_errors:
                            errors.extend(closure_errors)
                            failed_locators.add(basis_lid)
                    except RepositoryError as exc:
                        errors.append(f"断言依据定位 {basis_lid} 无法还原：{exc}")
                        failed_locators.add(basis_lid)

    if errors:
        return GateOutcome.REJECTED, errors, sorted(failed_locators)
    return GateOutcome.ACCEPTED, [], sorted(set(locator_ids))


def _gate_verdict_for_locator(
    candidate,
    outcome: GateOutcome,
    reasons: list[str],
    affected: list[str],
) -> GateVerdict:
    return GateVerdict(
        candidate_id=getattr(candidate, "candidate_id", "unknown"),
        gate=FactGate.LOCATOR_AND_TEXT_HASH,
        outcome=outcome,
        reasons=reasons,
        affected_scope=sorted(set(affected)),
    )


# --------------------------------------------------------------------------- 阻断级 OCR 风险（候选级）
def validate_blocking_ocr_for_candidate(
    session: Session,
    candidate,
    revision: CompleteEvidenceProcessingRevision,
) -> tuple[GateOutcome, list[str], list[str]]:
    """候选级阻断 OCR 风险检查。

    若候选任一定位所在页存在未解除的 BLOCKING 级风险且与定位范围重叠，
    则该候选被 BLOCKED，affected_scope 为被阻断的定位 ids。

    解除条件（与完整修订闭包一致）：
    - 该风险 flag 的全局 id ``"{scan_id}:{risk_id}"`` 出现在
      ``revision.risk_review_ids`` 对应的 ``OCRRiskReview.risk_flag_id`` 中；或
    - 存在 ``revision.correction_ids`` 中某条 ``CorrectionRecord`` 覆盖该 flag
      的字符范围（同一 ocr_page_id 且 correction.text_start <= flag.text_start
      且 correction.text_end >= flag.text_end）。

    范围重叠判定：
    - 若定位为 BBOX / TEXT_RANGE 且携带 text_start/end，则与 flag 范围
      区间重叠即视为影响；
    - 若定位为 PAGE_EXCERPT / PAGE_ONLY 等页级定位，则该页任一未解除的
      BLOCKING 风险即视为阻断（保守策略，符合“整页 OCR 风险未完成校对时
      相关候选不得发布”的要求）。

    非 BLOCKING 风险不阻断。
    """
    locator_ids: list[str] = list(getattr(candidate, "locator_ids", []) or [])
    if not locator_ids:
        return GateOutcome.ACCEPTED, [], []

    # 收集该修订的扫描与 flag
    from app.storage.evidence_locator_repositories import (
        CorrectionRepository,
        OCRRiskReviewRepository,
        OCRRiskScanRepository,
    )

    scan_repo = OCRRiskScanRepository(session)
    review_repo = OCRRiskReviewRepository(session)
    correction_repo = CorrectionRepository(session)

    # 构建 ocr_page_id -> list[(scan_id, flag)]
    blocking_by_page: dict[str, list[tuple[str, object]]] = {}
    closure_errors: list[str] = []
    selected_flag_ids: set[str] = set()
    manifest_ocr_page_ids = {entry.ocr_page_id for entry in revision.manifest if entry.ocr_page_id}
    scan_counts: dict[str, int] = {}
    for scan_id in revision.risk_scan_ids:
        try:
            scan = scan_repo.get(scan_id)
        except RepositoryError as exc:
            closure_errors.append(f"完整修订选中的风险扫描 {scan_id} 无效：{exc}")
            continue
        ocr_pid = getattr(scan, "ocr_page_id", None)
        if ocr_pid is None:
            closure_errors.append(f"风险扫描 {scan_id} 缺少 OCR 页引用")
            continue
        if ocr_pid not in manifest_ocr_page_ids:
            closure_errors.append(f"风险扫描 {scan_id} 的 OCR 页不在完整修订页清单")
            continue
        scan_counts[ocr_pid] = scan_counts.get(ocr_pid, 0) + 1
        for flag in getattr(scan, "flags", []) or []:
            selected_flag_ids.add(f"{scan_id}:{getattr(flag, 'risk_id', '')}")
            if getattr(flag, "level", None) == OcrRiskLevel.BLOCKING:
                blocking_by_page.setdefault(ocr_pid, []).append((scan_id, flag))

    for ocr_page_id in sorted(manifest_ocr_page_ids):
        if scan_counts.get(ocr_page_id, 0) != 1:
            closure_errors.append(
                f"OCR 页 {ocr_page_id} 必须恰好绑定一个完整修订选中的风险扫描"
            )

    # 已解除的 flag ids
    resolved_via_review: set[str] = set()
    for rid in revision.risk_review_ids:
        try:
            review = review_repo.get(rid)
            flag_id = getattr(review, "risk_flag_id", rid)
            if flag_id not in selected_flag_ids:
                closure_errors.append(f"风险核对 {rid} 不属于本完整修订选中的风险扫描")
            if flag_id in resolved_via_review:
                closure_errors.append(f"同一风险 flag {flag_id} 只能选择一个有效核对")
            resolved_via_review.add(flag_id)
            if review.base_processing_revision_id != revision.base_processing_revision_id:
                closure_errors.append(f"风险核对 {rid} 未绑定当前完整修订的 base")
        except RepositoryError as exc:
            closure_errors.append(f"完整修订选中的风险核对 {rid} 无效：{exc}")
            continue

    corrections = []
    for cid in revision.correction_ids:
        try:
            corrections.append(correction_repo.get(cid))
            if corrections[-1].base_processing_revision_id != revision.base_processing_revision_id:
                closure_errors.append(f"校对 {cid} 未绑定当前完整修订的 base")
            if corrections[-1].requires_confirmation and corrections[-1].confirmation_actor is None:
                closure_errors.append(f"完整修订选中的关键校对 {cid} 未完成二次确认")
            if corrections[-1].ocr_page_id not in manifest_ocr_page_ids:
                closure_errors.append(f"校对 {cid} 的 OCR 页不在完整修订页清单")
        except RepositoryError as exc:
            closure_errors.append(f"完整修订选中的校对 {cid} 无效：{exc}")
            continue

    from app.evidence.effective_text import correction_anchors_conflict

    for index, left in enumerate(corrections):
        for right in corrections[index + 1 :]:
            if correction_anchors_conflict(left, right):
                closure_errors.append(
                    f"完整修订选中的校对 {left.correction_id} 与 {right.correction_id} 范围重叠"
                )

    if closure_errors:
        return GateOutcome.BLOCKED, closure_errors, sorted(set(locator_ids))
    if not blocking_by_page:
        return GateOutcome.ACCEPTED, [], sorted(set(locator_ids))

    blocked_locators: set[str] = set()
    reasons: list[str] = []

    for lid in locator_ids:
        try:
            locator = _fetch_locator(session, lid)
        except RepositoryError:
            # 定位本身无效由 locator 门禁负责，此处不重复阻断
            continue
        ocr_pid = getattr(locator, "ocr_page_id", None)
        if ocr_pid is None:
            # 无 OCR 页关联的定位（如 native_text 无 ocr_page）暂不参与风险阻断
            continue
        flags = blocking_by_page.get(ocr_pid, [])
        for scan_id, flag in flags:
            flag_id = f"{scan_id}:{getattr(flag, 'risk_id', '')}"
            if flag_id in resolved_via_review:
                continue
            # 检查是否被校对覆盖
            covered = False
            for corr in corrections:
                if getattr(corr, "ocr_page_id", None) != ocr_pid:
                    continue
                # 校对范围必须完全覆盖 flag 范围
                c_start = getattr(corr, "text_start", None)
                c_end = getattr(corr, "text_end", None)
                f_start = getattr(flag, "text_start", None)
                f_end = getattr(flag, "text_end", None)
                if (
                    c_start is not None
                    and c_end is not None
                    and f_start is not None
                    and f_end is not None
                    and c_start <= f_start
                    and c_end >= f_end
                ):
                    covered = True
                    break
            if covered:
                continue

            # 未解除，判断是否与定位重叠
            loc_start = getattr(locator, "text_start", None)
            loc_end = getattr(locator, "text_end", None)
            flag_start = getattr(flag, "text_start", None)
            flag_end = getattr(flag, "text_end", None)
            overlapping = False
            if locator.precision in (LocatorPrecision.BBOX, LocatorPrecision.TEXT_RANGE) and loc_start is not None and loc_end is not None and flag_start is not None and flag_end is not None:
                # 区间重叠： flag_end > loc_start and flag_start < loc_end
                if not (flag_end <= loc_start or flag_start >= loc_end):
                    overlapping = True
            else:
                # 页级定位：保守视为重叠
                overlapping = True

            if overlapping:
                detail = getattr(flag, "kind", "")
                kind_val = detail.value if hasattr(detail, "value") else str(detail)
                reasons.append(
                    f"定位 {lid} 所在页存在未解除的阻断级 OCR 风险 {kind_val}（{flag_start}-{flag_end}）"
                )
                blocked_locators.add(lid)
                # 同一定位若已阻断，无需对同一定位的多个 flag 重复追加多个原因？此处保留每个 flag 的原因
        # end for flag

    if reasons:
        return GateOutcome.BLOCKED, reasons, sorted(blocked_locators)
    return GateOutcome.ACCEPTED, [], sorted(set(locator_ids))


_SOURCE_LABEL_TO_STRENGTH = {
    "同期客观结果": SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
    "objective_result": SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
    "contemporaneous_objective": SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
    "既往原始资料": SourceStrength.HISTORICAL_PRIMARY,
    "historical_primary": SourceStrength.HISTORICAL_PRIMARY,
    "当前研究病历直接记录": SourceStrength.CURRENT_STUDY_CHART,
    "current_chart": SourceStrength.CURRENT_STUDY_CHART,
    "筛选病历转述": SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
    "screening_transcript": SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
    "无法确认来源": SourceStrength.UNVERIFIABLE,
    "unverifiable_source": SourceStrength.UNVERIFIABLE,
}


def derive_source_strength_for_candidate(
    session: Session, candidate, revision: CompleteEvidenceProcessingRevision
) -> SourceStrength:
    """仅从完整修订冻结的 Phase 4 文档元数据确定性派生来源强度。"""
    from app.storage.evidence_repositories import (
        SourceDocumentMetadataRevisionRepository,
    )

    metadata = [
        SourceDocumentMetadataRevisionRepository(session).get(item)
        for item in revision.metadata_revision_ids
    ]
    by_document = {item.source_document_version_id: item for item in metadata}
    strengths: list[SourceStrength] = []
    for locator_id in candidate.locator_ids:
        locator = _fetch_locator(session, locator_id)
        item = by_document.get(locator.source_document_version_id)
        if item is None:
            raise ValueError(
                f"定位 {locator_id} 的资料未在完整修订中冻结唯一 Phase 4 元数据"
            )
        document_type = item.document_type.strip().lower()
        source_party = item.source_party.strip().lower()
        if document_type in {"lab", "lab_report", "report", "imaging", "exam_report"}:
            strength = SourceStrength.CONTEMPORANEOUS_OBJECTIVE
        elif document_type == "screening_record":
            strength = SourceStrength.SCREENING_RECORD_TRANSCRIPTION
        elif document_type in {"baseline_record", "study_chart", "current_study_chart"}:
            strength = SourceStrength.CURRENT_STUDY_CHART
        elif document_type in {"medical_record", "discharge_summary", "historical_record"} or source_party in {
            "外院", "hospital", "external_hospital"
        }:
            strength = SourceStrength.HISTORICAL_PRIMARY
        else:
            strength = SourceStrength.UNVERIFIABLE
        strengths.append(strength)
    rank = {
        SourceStrength.UNVERIFIABLE: 0,
        SourceStrength.SCREENING_RECORD_TRANSCRIPTION: 1,
        SourceStrength.CURRENT_STUDY_CHART: 2,
        SourceStrength.HISTORICAL_PRIMARY: 3,
        SourceStrength.CONTEMPORANEOUS_OBJECTIVE: 4,
    }
    if not strengths:
        raise ValueError("候选没有可派生来源强度的定位")
    return max(strengths, key=rank.__getitem__)


def validate_source_strength_for_candidate(session: Session, candidate, revision) -> GateVerdict:
    reasons: list[str] = []
    try:
        derived = derive_source_strength_for_candidate(session, candidate, revision)
    except (RepositoryError, ValueError) as exc:
        reasons.append(str(exc))
    else:
        declared = _SOURCE_LABEL_TO_STRENGTH.get(candidate.candidate_source_semantics)
        if declared != derived:
            reasons.append(
                f"候选自由文本来源与 Phase 4 元数据派生结果不一致：派生为 {derived.value}"
            )
    return GateVerdict(
        candidate_id=candidate.candidate_id,
        gate=FactGate.VALUE_UNIT_DATE_SOURCE,
        outcome=GateOutcome.REJECTED if reasons else GateOutcome.ACCEPTED,
        reasons=reasons,
        affected_scope=_affected_locators(candidate) if reasons else [],
    )


# --------------------------------------------------------------------------- 组合门禁（证据闭包）
def gate_evidence_closure_for_candidate(
    session: Session,
    candidate,
    revision: CompleteEvidenceProcessingRevision,
    calls: list[FactNormalizationCall],
) -> dict[FactGate, GateVerdict]:
    """对单个候选执行证据闭包门禁，返回逐门的裁决字典。

    覆盖的两门（均落于 FactGate）：
    - PAGE_COVERAGE_AND_REFERENCE_CLOSURE：必须根据真实 calls 校验页覆盖；
      调用清单不可省略，避免缺少覆盖证据时隐式通过；
    - LOCATOR_AND_TEXT_HASH：合并定位真实性/哈希与阻断 OCR 风险，
      优先级 BLOCKED > REJECTED > ACCEPTED，且 affected_scope 为二者并集。

    该函数不触发网络或模型调用，仅读取数据库当前修订与定位状态。
    """
    verdicts: dict[FactGate, GateVerdict] = {}
    candidate_id = getattr(candidate, "candidate_id", "unknown")

    # 页覆盖
    outcome, reasons, affected = validate_page_coverage(revision, calls, session=session)
    if outcome == GateOutcome.ACCEPTED:
        verdicts[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE] = GateVerdict(
            candidate_id=candidate_id,
            gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            affected_scope=[],
        )
    else:
        verdicts[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE] = GateVerdict(
            candidate_id=candidate_id,
            gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
            outcome=outcome,
            reasons=reasons,
            affected_scope=affected,
        )

    # 定位与哈希
    loc_outcome, loc_reasons, loc_affected = validate_locator_and_text_hash(session, candidate, revision)
    # 阻断 OCR
    ocr_outcome, ocr_reasons, ocr_affected = validate_blocking_ocr_for_candidate(session, candidate, revision)

    # 合并：BLOCKED 优先
    if ocr_outcome == GateOutcome.BLOCKED:
        # 若定位本身已 REJECTED，仍以 BLOCKED 呈现但合并原因？
        # 策略：BLOCKED 覆盖 REJECTED，原因合并，受影响范围为二者并集中的被阻断定位
        combined_reasons = list(ocr_reasons)
        if loc_outcome == GateOutcome.REJECTED:
            combined_reasons = loc_reasons + ocr_reasons
            combined_affected = sorted(set(loc_affected) | set(ocr_affected))
        else:
            combined_affected = ocr_affected
        verdicts[FactGate.LOCATOR_AND_TEXT_HASH] = GateVerdict(
            candidate_id=candidate_id,
            gate=FactGate.LOCATOR_AND_TEXT_HASH,
            outcome=GateOutcome.BLOCKED,
            reasons=combined_reasons,
            affected_scope=combined_affected,
        )
    elif loc_outcome == GateOutcome.REJECTED:
        verdicts[FactGate.LOCATOR_AND_TEXT_HASH] = GateVerdict(
            candidate_id=candidate_id,
            gate=FactGate.LOCATOR_AND_TEXT_HASH,
            outcome=GateOutcome.REJECTED,
            reasons=loc_reasons,
            affected_scope=loc_affected,
        )
    else:
        # 定位通过且无阻断
        verdicts[FactGate.LOCATOR_AND_TEXT_HASH] = GateVerdict(
            candidate_id=candidate_id,
            gate=FactGate.LOCATOR_AND_TEXT_HASH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            affected_scope=_affected_locators(candidate),
        )

    return verdicts


def batch_gate_evidence_closure(
    session: Session,
    revision: CompleteEvidenceProcessingRevision,
    calls: list[FactNormalizationCall],
    fact_candidates: list[ClinicalFactCandidateV2] | None = None,
    event_candidates: list[ClinicalEventCandidateV2] | None = None,
    exposure_candidates: list[MedicationExposureCandidateV2] | None = None,
) -> dict[str, dict[FactGate, GateVerdict]]:
    """批次级证据闭包门禁：页覆盖一致 + 逐候选定位/哈希/阻断。

    返回 ``{candidate_id: {FactGate: GateVerdict}}``，键按 candidate_id 排序
    确保确定性。对页覆盖失败，所有候选的 PAGE_COVERAGE 门均 REJECTED；
    定位/阻断门逐候选独立。
    """
    fact_candidates = fact_candidates or []
    event_candidates = event_candidates or []
    exposure_candidates = exposure_candidates or []

    # 页覆盖批次校验（一次计算，供所有候选复用）
    page_outcome, page_reasons, page_affected = validate_page_coverage(revision, calls, session=session)

    result: dict[str, dict[FactGate, GateVerdict]] = {}
    all_candidates = [*fact_candidates, *event_candidates, *exposure_candidates]

    for cand in all_candidates:
        cid = getattr(cand, "candidate_id", "unknown")
        verdicts: dict[FactGate, GateVerdict] = {}

        # 页覆盖门
        if page_outcome == GateOutcome.ACCEPTED:
            verdicts[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE] = GateVerdict(
                candidate_id=cid,
                gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
                outcome=GateOutcome.ACCEPTED,
                reasons=[],
                affected_scope=[],
            )
        else:
            verdicts[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE] = GateVerdict(
                candidate_id=cid,
                gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
                outcome=page_outcome,
                reasons=list(page_reasons),
                affected_scope=list(page_affected),
            )

        # 定位/哈希/阻断
        loc_outcome, loc_reasons, loc_affected = validate_locator_and_text_hash(session, cand, revision)
        ocr_outcome, ocr_reasons, ocr_affected = validate_blocking_ocr_for_candidate(session, cand, revision)

        if ocr_outcome == GateOutcome.BLOCKED:
            combined_reasons = list(ocr_reasons)
            if loc_outcome == GateOutcome.REJECTED:
                combined_reasons = loc_reasons + ocr_reasons
                combined_affected = sorted(set(loc_affected) | set(ocr_affected))
            else:
                combined_affected = ocr_affected
            verdicts[FactGate.LOCATOR_AND_TEXT_HASH] = GateVerdict(
                candidate_id=cid,
                gate=FactGate.LOCATOR_AND_TEXT_HASH,
                outcome=GateOutcome.BLOCKED,
                reasons=combined_reasons,
                affected_scope=combined_affected,
            )
        elif loc_outcome == GateOutcome.REJECTED:
            verdicts[FactGate.LOCATOR_AND_TEXT_HASH] = GateVerdict(
                candidate_id=cid,
                gate=FactGate.LOCATOR_AND_TEXT_HASH,
                outcome=GateOutcome.REJECTED,
                reasons=loc_reasons,
                affected_scope=loc_affected,
            )
        else:
            verdicts[FactGate.LOCATOR_AND_TEXT_HASH] = GateVerdict(
                candidate_id=cid,
                gate=FactGate.LOCATOR_AND_TEXT_HASH,
                outcome=GateOutcome.ACCEPTED,
                reasons=[],
                affected_scope=_affected_locators(cand),
            )

        result[cid] = verdicts

        verdicts[FactGate.VALUE_UNIT_DATE_SOURCE] = validate_source_strength_for_candidate(
            session, cand, revision
        )

    return result


# --------------------------------------------------------------------------- 持久化衔接
def verdict_to_gate_result(
    verdict: GateVerdict,
    *,
    run_id: str,
    call_id: str,
    gate_result_id: str,
    created_at: datetime,
) -> FactGateResult:
    """将证据闭包裁决转为可持久化的 ``FactGateResult`` 合同。

    与 ``fact_candidate_gates.verdict_to_gate_result`` 保持相同字段搬运语义，
    仅做合同转换，不触发数据库。
    """
    return FactGateResult(
        gate_result_id=gate_result_id,
        run_id=run_id,
        call_id=call_id,
        candidate_id=verdict.candidate_id,
        gate=verdict.gate,
        outcome=verdict.outcome,
        reasons=list(verdict.reasons),
        created_at=created_at,
    )


def verdicts_to_gate_results(
    batch_verdicts: dict[str, dict[FactGate, GateVerdict]],
    *,
    run_id: str,
    call_id: str,
    created_at: datetime,
    id_prefix: str = "gate",
) -> list[FactGateResult]:
    """将证据闭包批次裁决扁平化为 ``FactGateResult`` 列表（确定性排序）。"""
    results: list[FactGateResult] = []
    for candidate_id in sorted(batch_verdicts.keys()):
        gate_map = batch_verdicts[candidate_id]
        for gate in sorted(gate_map.keys(), key=lambda g: g.value):
            verdict = gate_map[gate]
            gate_result_id = f"{id_prefix}-{candidate_id}-{gate.value}"
            results.append(
                FactGateResult(
                    gate_result_id=gate_result_id,
                    run_id=run_id,
                    call_id=call_id,
                    candidate_id=candidate_id,
                    gate=gate,
                    outcome=verdict.outcome,
                    reasons=list(verdict.reasons),
                    created_at=created_at,
                )
            )
    return results


def persist_gate_results(
    session: Session,
    results: list[FactGateResult],
) -> list[FactGateResult]:
    """通过 ``FactGateResultRepository`` 批量持久化门禁结果。

    调用方需保证 run/call/candidate 已持久化且归属一致；本函数仅循环
    ``create`` 并在失败时透传仓储异常，不静默吞错。
    """
    from app.storage.fact_repositories import FactGateResultRepository

    repo = FactGateResultRepository(session)
    persisted: list[FactGateResult] = []
    for r in results:
        persisted.append(repo.create(r))
    return persisted
