"""Slice 4.4 OCR 风险旁路扫描/核对服务（WP-44B）。

- ``EvidenceRiskScanService.scan_page``     对不可变 ``OCRPage.raw_text`` 运行冻结
  扫描器，只创建 ``OCRRiskScan`` 旁路工件（同一 (页, 原文哈希, 规则版本) 三元组
  幂等复用）；扫描前后重读 OCR 页验证 raw text/hash 逐字不变；
- ``EvidenceRiskScanService.create_review`` 追加用户风险核对决议（blocking 是否被
  完整修订选中由闭包门禁负责，本服务只持久化决议）。

模块边界（§4.3 与 §8.2 反例）：本服务不修改 ``OCRPage.raw_text`` / canonical
payload / hash，不写 ``ClinicalFact``、``RuleComponent/RuleExpression``、
``Assessment``、``ReviewRun`` 或任何行动/入排结论；扫描器输出只能是
``list[OcrRiskFlag]``，绝不返回修正文、规范化临床值或布尔表达式，也绝不因识别到
数值/单位而重排、合并或改写“且/或/以及/任一/全部”等并列条件。
"""
from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import OcrRiskReviewDecision
from app.domain.contracts.evidence_locator import (
    OCRRiskPageReview,
    OCRRiskReview,
    OCRRiskScan,
)
from app.domain.contracts.ocr import OcrRiskFlag
from app.domain.publication import canonical_hash
from app.evidence.risk import (
    OCR_RISK_RULE_VERSION,
    allows_risk_review,
    correction_covers_risk,
    scan_ocr_risks,
)
from app.storage.evidence_locator_repositories import (
    CorrectionRepository,
    OCRRiskPageReviewRepository,
    OCRRiskReviewRepository,
    OCRRiskScanRepository,
)
from app.storage.ocr_repositories import OcrPageRepository

__all__ = [
    "EvidenceRiskScanService",
    "RiskReviewDecisionError",
    "RiskReviewRequiresReprocessingError",
    "RiskPageReviewNoPendingError",
    "RiskPageReviewScanMismatchError",
    "RiskScanSideEffectError",
    "build_flags_sha256",
]




def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(UTC)

class EvidenceRiskScanServiceError(RuntimeError):
    """风险扫描/核对服务领域错误基类。"""


class RiskScanSideEffectError(EvidenceRiskScanServiceError):
    """扫描前后原 OCR 文本/哈希漂移：模块边界被破坏，拒绝返回扫描结果。"""


class RiskPageReviewNoPendingError(EvidenceRiskScanServiceError):
    """页上所有风险项均已核对或被覆盖校对解除，没有可原子确认的待核对项。"""


class RiskPageReviewScanMismatchError(EvidenceRiskScanServiceError):
    """页级核对引用的扫描不属于目标 OCR 页。"""


class RiskReviewDecisionError(EvidenceRiskScanServiceError):
    """核对动作与风险类型或页级确认合同不一致。"""


class RiskReviewRequiresReprocessingError(EvidenceRiskScanServiceError):
    """整页识别质量不可信，必须重新识别或校对整页，不能人工确认解除。"""


def _find_flag(
    session: Session, risk_flag_id: str
) -> tuple[OCRRiskScan, OcrRiskFlag]:
    """从稳定 ``scan_id:risk_id`` 标识定位冻结风险。"""
    scan_id, separator, risk_id = risk_flag_id.rpartition(":")
    if not separator or not scan_id or not risk_id:
        raise RiskReviewDecisionError("识别风险标识无效，请刷新页面后重试")
    scan = OCRRiskScanRepository(session).get(scan_id)
    flag = next((item for item in scan.flags if item.risk_id == risk_id), None)
    if flag is None:
        raise RiskReviewDecisionError("识别风险已变化，请刷新页面后重新核对")
    return scan, flag


def build_flags_sha256(flags: list[OcrRiskFlag]) -> str:
    """按合同校验器同一顺序敏感算法计算完整 flag 集合的内容哈希。"""
    return canonical_hash(
        [
            {
                "risk_id": flag.risk_id,
                "kind": flag.kind.value,
                "level": flag.level.value,
                "text": flag.text,
                "text_start": flag.text_start,
                "text_end": flag.text_end,
                "detail": flag.detail,
                "rule_version": flag.rule_version,
            }
            for flag in sorted(flags, key=lambda f: f.risk_id)
        ]
    )


class EvidenceRiskScanService:
    """OCR 风险旁路扫描与核对服务（只产生风险侧车，永不改写原 OCR/临床事实）。"""

    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def scan_page(
        self, ocr_page_id: str, *, rule_version: str = OCR_RISK_RULE_VERSION
    ) -> OCRRiskScan:
        with self.session_factory() as session, session.begin():
            return self.scan_page_in_session(
                session, ocr_page_id, rule_version=rule_version
            )

    def scan_page_in_session(
        self, session: Session, ocr_page_id: str, *, rule_version: str = OCR_RISK_RULE_VERSION
    ) -> OCRRiskScan:
        """扫描一页原 OCR 并幂等持久化风险扫描（供工作流在外部事务内复用）。"""
        ocr_repo = OcrPageRepository(session)
        ocr = ocr_repo.get(ocr_page_id)
        raw_before = ocr.raw_text
        flags = scan_ocr_risks(raw_before, rule_version=rule_version)
        # 模块边界：扫描后必须能重读同一不可变 OCR 页，文本/哈希逐字不变。
        raw_after = ocr_repo.get(ocr_page_id).raw_text
        if raw_after != raw_before:
            raise RiskScanSideEffectError(
                f"风险扫描 {ocr_page_id} 后重读 OCRPage 原文发生变化，拒绝返回扫描结果"
            )
        if ocr_repo.get(ocr_page_id).raw_text_sha256 != ocr.raw_text_sha256:
            raise RiskScanSideEffectError(
                f"风险扫描 {ocr_page_id} 后重读 OCRPage raw_text_sha256 发生变化，"
                "模块边界被破坏"
            )
        scan = OCRRiskScan(
            scan_id=f"scan-{uuid4().hex}",
            ocr_page_id=ocr_page_id,
            raw_text_sha256=ocr.raw_text_sha256,
            scanner_rule_version=rule_version,
            flags=flags,
            flags_sha256=build_flags_sha256(flags),
            coverage_status="complete",
            created_at=_utcnow(),
        )
        persisted, _created = OCRRiskScanRepository(session).get_or_create(scan)
        return persisted

    def create_review(
        self,
        *,
        review_id: str | None,
        risk_flag_id: str,
        decision: OcrRiskReviewDecision,
        reason: str,
        actor: str,
        base_processing_revision_id: str,
        expected_revision: int,
    ) -> OCRRiskReview:
        with self.session_factory() as session, session.begin():
            return self.create_review_in_session(
                session,
                review_id=review_id,
                risk_flag_id=risk_flag_id,
                decision=decision,
                reason=reason,
                actor=actor,
                base_processing_revision_id=base_processing_revision_id,
                expected_revision=expected_revision,
            )

    def create_review_in_session(
        self,
        session: Session,
        *,
        review_id: str | None,
        risk_flag_id: str,
        decision: OcrRiskReviewDecision,
        reason: str,
        actor: str,
        base_processing_revision_id: str,
        expected_revision: int,
    ) -> OCRRiskReview:
        """在调用方事务内追加风险核对（供 API 命令服务与幂等键同事务提交）。"""
        _scan, flag = _find_flag(session, risk_flag_id)
        if not allows_risk_review(flag):
            raise RiskReviewRequiresReprocessingError(
                "本页识别内容异常重复，不能直接确认。请重新识别，或对照原件校对整页。"
            )
        if decision == OcrRiskReviewDecision.CORRECTED:
            raise RiskReviewDecisionError(
                "文字校对应在原文校对区完成，不能以风险核对代替文字校对"
            )
        review = OCRRiskReview(
            review_id=review_id or f"rv-{uuid4().hex}",
            risk_flag_id=risk_flag_id,
            decision=decision,
            reason=reason,
            actor=actor,
            base_processing_revision_id=base_processing_revision_id,
            expected_revision=expected_revision,
            created_at=_utcnow(),
        )
        return OCRRiskReviewRepository(session).create(review)

    def create_page_review(
        self,
        *,
        page_review_id: str,
        ocr_page_id: str,
        scan_id: str,
        decision: OcrRiskReviewDecision,
        reason: str,
        actor: str,
        base_processing_revision_id: str,
        expected_revision: int,
    ) -> OCRRiskPageReview:
        with self.session_factory() as session, session.begin():
            return self.create_page_review_in_session(
                session,
                page_review_id=page_review_id,
                ocr_page_id=ocr_page_id,
                scan_id=scan_id,
                decision=decision,
                reason=reason,
                actor=actor,
                base_processing_revision_id=base_processing_revision_id,
                expected_revision=expected_revision,
            )

    def create_page_review_in_session(
        self,
        session: Session,
        *,
        page_review_id: str,
        ocr_page_id: str,
        scan_id: str,
        decision: OcrRiskReviewDecision,
        reason: str,
        actor: str,
        base_processing_revision_id: str,
        expected_revision: int,
    ) -> OCRRiskPageReview:
        """在调用方事务内对页上全部待核对风险做一次原子核对。

        原子性：同一事务内为页上每个「既无既有核对、又未被该 base 修订覆盖校对解除」
        的风险条目各追加一条不可变 ``OCRRiskReview``，再追加一条页级审计记录
        ``OCRRiskPageReview``；任一步失败整体回滚。逐条 review_id 由页级身份与
        flag_id 确定性派生，同页级幂等键重放得到相同逐条记录。
        """
        scan = OCRRiskScanRepository(session).get(scan_id)
        if scan.ocr_page_id != ocr_page_id:
            raise RiskPageReviewScanMismatchError(
                f"页级核对引用的扫描 {scan_id} 不属于 OCR 页 {ocr_page_id}"
            )
        if decision != OcrRiskReviewDecision.CONFIRMED_AS_READ:
            raise RiskReviewDecisionError(
                "整页核对只用于确认已逐项对照原件；文字校对或不适用判断请逐项处理"
            )
        if any(not allows_risk_review(flag) for flag in scan.flags):
            raise RiskReviewRequiresReprocessingError(
                "本页识别内容异常重复，不能整页确认。请重新识别，或对照原件校对整页。"
            )
        page_text_length = len(OcrPageRepository(session).get(ocr_page_id).raw_text)
        review_repo = OCRRiskReviewRepository(session)
        corrections = [
            c
            for c in CorrectionRepository(session).list_by_page(ocr_page_id)
            if c.base_processing_revision_id == base_processing_revision_id
        ]
        flag_ids = [f"{scan.scan_id}:{flag.risk_id}" for flag in scan.flags]
        reviewed = review_repo.reviewed_flag_ids(flag_ids)
        pending: list[str] = []
        for flag in scan.flags:
            flag_id = f"{scan.scan_id}:{flag.risk_id}"
            if flag_id in reviewed:
                continue
            if any(
                correction_covers_risk(
                    flag,
                    correction_text_start=c.text_start,
                    correction_text_end=c.text_end,
                    page_text_length=page_text_length,
                )
                for c in corrections
            ):
                continue
            pending.append(flag_id)
        if not pending:
            raise RiskPageReviewNoPendingError(
                f"OCR 页 {ocr_page_id} 的扫描 {scan_id} 已无待核对风险项"
            )
        pending = sorted(pending)
        created_review_ids: list[str] = []
        for flag_id in pending:
            review_id = (
                "rv-" + sha256(f"{page_review_id}:{flag_id}".encode()).hexdigest()[:32]
            )
            review_repo.create(
                OCRRiskReview(
                    review_id=review_id,
                    risk_flag_id=flag_id,
                    decision=decision,
                    reason=reason,
                    actor=actor,
                    base_processing_revision_id=base_processing_revision_id,
                    expected_revision=expected_revision,
                    created_at=_utcnow(),
                )
            )
            created_review_ids.append(review_id)
        page_review = OCRRiskPageReview(
            page_review_id=page_review_id,
            ocr_page_id=ocr_page_id,
            scan_id=scan_id,
            raw_text_sha256=scan.raw_text_sha256,
            scanner_rule_version=scan.scanner_rule_version,
            decision=decision,
            reason=reason,
            actor=actor,
            base_processing_revision_id=base_processing_revision_id,
            expected_revision=expected_revision,
            covered_flag_ids=pending,
            created_review_ids=created_review_ids,
            covered_flag_sha256=canonical_hash(sorted(pending)),
            created_at=_utcnow(),
        )
        return OCRRiskPageReviewRepository(session).create(page_review)
