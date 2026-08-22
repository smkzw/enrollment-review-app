"""Slice 4.4 定位、风险、校对、完整处理修订、处理候选与活动版本领域契约（WP-44A）。

本模块只冻结纯校验与确定性身份计算，不含存储、文件路径或外部模型调用。覆盖
设计书 §3.4 的定位/引用/校对旁路工件、§3.2 的处理候选状态机与活动版本追加事件，
以及完整处理修订的 base/complete 辨别与闭包清单哈希：

- ``EvidenceLocatorArtifact``        occurrence-aware 定位旁路工件：绑定页产物、
                                     来源层、来源文本哈希、目标范围/摘录、
                                     坐标系与坐标 sidecar、消歧证据与真实性门禁；
- ``OCRRiskScan`` / ``OcrRiskFlag``   对某一原始 OCR 哈希与规则版本运行的完整风险
                                     集合（追加旁路，不改原 OCR、不写临床事实）；
- ``OCRRiskReview``                   用户对单个风险的追加写核对决议；
- ``CorrectionRecord``                对原始 OCR 固定范围的追加写校对记录（覆盖层）；
- ``ReferencedDocumentRevision`` / ``ReferencedDocumentResolutionRevision``
                                     “资料中提及但未提供”的两层不可变修订/满足关系；
- ``EvidenceActivationEvent``         审核节点从哪个快照/处理修订切到哪个版本、
                                     原因、预期修订号与时间；回滚也是新激活事件；
- ``EvidenceProcessingCandidate`` / ``EvidenceProcessingCandidateEvent``
                                     处理候选状态机：追加事件投影，终态不可跳转；
- ``CompleteEvidenceProcessingRevision`` 在 base 页清单上冻结全部 4.4 关联的完整
                                     修订；``completion_manifest_sha256`` 对有序
                                     闭包内容寻址。

Slice 4.4 硬不变量：原始层（PageArtifact/OCRPage.raw_text/4.3 基础修订 payload/hash）
永不 UPDATE；风险扫描只输出结构化提示不输出修正文；校对是覆盖层不替换 raw OCR；
bbox 必须由同源坐标 sidecar 证明；base 修订永不可激活；活动版本只由
``ReviewEpisode.active_evidence_snapshot_id + active_evidence_processing_revision_id``
成对指针决定，不得从时间/ID/状态推断。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from .common import VersionedModel
from .enums import (
    ActivationEventKind,
    CorrectionChangeKind,
    DisambiguationOutcome,
    EvidenceProcessingCandidateStatus,
    LocatorAuthenticity,
    LocatorPrecision,
    LocatorSourceLayer,
    OcrRiskReviewDecision,
    ProcessingCandidateEventKind,
    ProcessingRevisionStatus,
    ReferencedDocumentOrigin,
    ReferencedDocumentResolutionStatus,
    ReferencedDocumentStatus,
)
from .evidence import BoundingBox
from .evidence_processing import EvidenceProcessingRevisionPage
from .ocr import CoordinateFrame, OcrRiskFlag

__all__ = [
    "BLOCKING_CORRECTION_KINDS",
    "CANDIDATE_TRANSITIONS",
    "CompleteEvidenceProcessingRevision",
    "CorrectionRecord",
    "EvidenceActivationEvent",
    "EvidenceLocatorArtifact",
    "EvidenceProcessingCandidate",
    "EvidenceProcessingCandidateEvent",
    "OCRRiskPageReview",
    "OCRRiskReview",
    "OCRRiskScan",
    "ProcessingCandidateAttemptManifest",
    "ReferencedDocumentResolutionRevision",
    "ReferencedDocumentRevision",
    "activation_command_hash",
    "completion_manifest_hash",
    "processing_candidate_input_hash",
    "validate_correction_source_anchor",
]

_SHA256 = r"^[0-9a-f]{64}$"


def _require_utc(value: datetime, field_name: str) -> None:
    """Reject naive or non-UTC timestamps at the Slice 4.4 contract boundary."""
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")


def validate_correction_source_anchor(
    raw_text: str,
    *,
    text_start: int,
    text_end: int,
    original_text: str,
) -> None:
    """校验校对是否精确锚定不可变原始识别文本。

    ``start == end`` 表示在该原始字符位置补入漏识别文字，因此原文必须
    为空；非零范围仍必须逐字匹配原 OCR 对应的半开区间。
    """
    if not (0 <= text_start <= text_end <= len(raw_text)):
        raise ValueError(
            f"校对范围越出原始识别文本：[{text_start},{text_end})"
        )
    if text_start == text_end:
        if original_text != "":
            raise ValueError("零长度插入锚点的原文必须为空")
        return
    if raw_text[text_start:text_end] != original_text:
        raise ValueError("校对原文本与原始识别文本对应范围不一致")


#: 必须二次确认的校对变化类别（PRD blocking 规则：极性/关键数值/小数点/单位/日期，
#: 以及用户把且/或/任一/全部等连接词改成另一逻辑含义的语义连接词）。
BLOCKING_CORRECTION_KINDS = frozenset(
    {
        CorrectionChangeKind.POLARITY,
        CorrectionChangeKind.NUMERIC,
        CorrectionChangeKind.DECIMAL,
        CorrectionChangeKind.UNIT,
        CorrectionChangeKind.DATE,
        CorrectionChangeKind.SEMANTIC_CONNECTOR,
    }
)

#: 设计书 §6 状态表（未列出的转换一律拒绝）。value = (事件类型, 目标状态)。
CANDIDATE_TRANSITIONS: dict[EvidenceProcessingCandidateStatus, dict[
    ProcessingCandidateEventKind, EvidenceProcessingCandidateStatus
]] = {
    EvidenceProcessingCandidateStatus.STAGED: {
        ProcessingCandidateEventKind.WORKER_START: EvidenceProcessingCandidateStatus.PROCESSING,
        ProcessingCandidateEventKind.CANCEL: EvidenceProcessingCandidateStatus.CANCELLED,
    },
    EvidenceProcessingCandidateStatus.PROCESSING: {
        ProcessingCandidateEventKind.CHECKPOINT_SUCCESS: EvidenceProcessingCandidateStatus.PROCESSING,
        ProcessingCandidateEventKind.BLOCKING_RISK_FOUND: EvidenceProcessingCandidateStatus.NEEDS_ATTENTION,
        ProcessingCandidateEventKind.RETRYABLE_ERROR: EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE,
        ProcessingCandidateEventKind.TERMINAL_ERROR: EvidenceProcessingCandidateStatus.TERMINAL_FAILURE,
        ProcessingCandidateEventKind.CANCEL_AT_SAFE_BOUNDARY: EvidenceProcessingCandidateStatus.CANCELLED,
        ProcessingCandidateEventKind.ALL_GATES_PASSED: EvidenceProcessingCandidateStatus.READY,
    },
    EvidenceProcessingCandidateStatus.RETRYABLE_FAILURE: {
        ProcessingCandidateEventKind.RETRY: EvidenceProcessingCandidateStatus.PROCESSING,
        ProcessingCandidateEventKind.CANCEL: EvidenceProcessingCandidateStatus.CANCELLED,
    },
    EvidenceProcessingCandidateStatus.NEEDS_ATTENTION: {
        ProcessingCandidateEventKind.CORRECTION_OR_RESOLUTION: EvidenceProcessingCandidateStatus.STAGED,
        ProcessingCandidateEventKind.CANCEL: EvidenceProcessingCandidateStatus.CANCELLED,
    },
    EvidenceProcessingCandidateStatus.READY: {
        ProcessingCandidateEventKind.ACTIVATE: EvidenceProcessingCandidateStatus.ACTIVE,
        ProcessingCandidateEventKind.REVISION_MISMATCH: EvidenceProcessingCandidateStatus.REVISION_CONFLICT,
    },
}

#: 候选终态：不再允许任何候选状态跳转。
_CANDIDATE_TERMINAL = frozenset(
    {
        EvidenceProcessingCandidateStatus.ACTIVE,
        EvidenceProcessingCandidateStatus.REVISION_CONFLICT,
        EvidenceProcessingCandidateStatus.CANCELLED,
        EvidenceProcessingCandidateStatus.TERMINAL_FAILURE,
    }
)


# --------------------------------------------------------------------------- 定位


def locator_anchor_hash(
    *,
    page_artifact_id: str,
    source_layer: LocatorSourceLayer,
    source_text_sha256: str,
    precision: LocatorPrecision,
    target_id: str,
    excerpt: str | None,
    disambiguation: DisambiguationOutcome,
    degradation_reason: str | None,
) -> str:
    """计算降级定位的可回放锚点，拒绝调用方自报任意哈希。"""
    from app.domain.publication import canonical_hash

    if precision == LocatorPrecision.PAGE_EXCERPT:
        material = {
            "anchor": "page_excerpt/v1",
            "page_artifact_id": page_artifact_id,
            "source_layer": source_layer.value,
            "source_text_sha256": source_text_sha256,
            "target_id": target_id,
            "excerpt": excerpt,
            "disambiguation": disambiguation.value,
        }
    elif precision == LocatorPrecision.PAGE_ONLY:
        material = {
            "anchor": "page_only/v1",
            "page_artifact_id": page_artifact_id,
            "source_layer": source_layer.value,
            "source_text_sha256": source_text_sha256,
            "target_id": target_id,
            "disambiguation": disambiguation.value,
            "degradation_reason": degradation_reason,
        }
    else:
        raise ValueError("只有 page_excerpt/page_only 定位使用降级锚点")
    return canonical_hash(material)


class EvidenceLocatorArtifact(VersionedModel):
    """occurrence-aware 定位旁路工件（追加写，不可变）。

    定位身份至少包含页工件、来源层、来源文本哈希、目标范围/上下文锚点与算法版本，
    不能再仅按“页 + 目标字符串”生成会碰撞的 ID。bbox 必须由与来源文本同源的
    字符/词坐标 sidecar 逐字符映射证明，页尺寸或模型自报坐标本身不构成真实性；
    text-only 路线一律不得输出 bbox。
    """

    locator_id: str = Field(min_length=1)
    page_artifact_id: str = Field(min_length=1)
    ocr_page_id: str | None = None
    source_document_version_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    source_layer: LocatorSourceLayer
    source_text_sha256: str = Field(pattern=_SHA256)
    target_id: str = Field(min_length=1)
    precision: LocatorPrecision
    bbox: BoundingBox | None = None
    coordinate_frame: CoordinateFrame | None = None
    sidecar_sha256: str | None = Field(default=None, pattern=_SHA256)
    text_start: int | None = Field(default=None, ge=0)
    text_end: int | None = Field(default=None, ge=0)
    excerpt: str | None = None
    anchor_hash: str | None = Field(default=None, pattern=_SHA256)
    disambiguation: DisambiguationOutcome = DisambiguationOutcome.UNIQUE_MATCH
    locator_algorithm_version: str = Field(min_length=1)
    coordinate_transform_version: str | None = None
    authenticity: LocatorAuthenticity
    effective_text_sha256: str | None = Field(default=None, pattern=_SHA256)
    processing_revision_id: str | None = None
    match_confidence: float | None = Field(default=None, ge=0, le=1)
    degradation_reason: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_locator(self) -> EvidenceLocatorArtifact:
        _require_utc(self.created_at, "EvidenceLocatorArtifact.created_at")

        if self.authenticity == LocatorAuthenticity.AUTHENTICATED:
            if self.precision != LocatorPrecision.BBOX:
                raise ValueError("真实性通过的区域定位必须为 bbox")
        else:
            if self.precision == LocatorPrecision.BBOX:
                raise ValueError("未通过真实性门禁的定位不得声明 bbox 精度")

        if self.precision == LocatorPrecision.BBOX:
            if self.bbox is None or self.coordinate_frame is None:
                raise ValueError("bbox 定位必须提供坐标与坐标系/页尺寸")
            if self.sidecar_sha256 is None:
                raise ValueError("bbox 定位必须提供同源坐标 sidecar 哈希")
            if self.disambiguation != DisambiguationOutcome.UNIQUE_MATCH:
                raise ValueError("区域定位只能在唯一消歧后产生")
            if (
                self.bbox.x0 < 0
                or self.bbox.y0 < 0
                or self.bbox.x1 > self.coordinate_frame.page_width
                or self.bbox.y1 > self.coordinate_frame.page_height
            ):
                raise ValueError("bbox 定位不能越出绑定页工件的页面边界")
            # bbox 必须绑定具体原始字符范围（occurrence 身份），不能只靠自报页尺寸。
            if self.text_start is None or self.text_end is None:
                raise ValueError("bbox 定位必须绑定具体原始字符范围")
            if self.text_end <= self.text_start:
                raise ValueError("bbox 定位的字符范围必须有效")
        else:
            if self.bbox is not None or self.coordinate_frame is not None:
                raise ValueError("非 bbox 定位不能携带坐标或坐标系")

        if self.precision == LocatorPrecision.TEXT_RANGE:
            if self.text_start is None or self.text_end is None or self.text_end <= self.text_start:
                raise ValueError("text_range 必须提供有效字符范围")
            if self.disambiguation != DisambiguationOutcome.UNIQUE_MATCH:
                raise ValueError("text_range 只能在唯一消歧后产生")
        elif self.precision not in (
            LocatorPrecision.BBOX,
            LocatorPrecision.TEXT_RANGE,
        ) and (self.text_start is not None or self.text_end is not None):
            raise ValueError("非 bbox/text_range 定位不能携带字符范围")

        if self.precision == LocatorPrecision.PAGE_EXCERPT:
            if not self.excerpt:
                raise ValueError("page_excerpt 必须提供页面摘录")
            if self.disambiguation == DisambiguationOutcome.NOT_FOUND:
                raise ValueError("目标未找到时不能产生 page_excerpt")
            if self.anchor_hash is None:
                raise ValueError("page_excerpt 必须携带可回放的摘录/上下文锚点哈希")
            if self.anchor_hash != locator_anchor_hash(
                page_artifact_id=self.page_artifact_id,
                source_layer=self.source_layer,
                source_text_sha256=self.source_text_sha256,
                precision=self.precision,
                target_id=self.target_id,
                excerpt=self.excerpt,
                disambiguation=self.disambiguation,
                degradation_reason=self.degradation_reason,
            ):
                raise ValueError("page_excerpt 锚点哈希必须由目标、摘录和消歧结果确定性计算")
        if self.precision == LocatorPrecision.PAGE_ONLY:
            if self.excerpt is not None:
                raise ValueError("page_only 不能携带伪精确页面摘录")
            if not self.degradation_reason:
                raise ValueError("page_only 必须说明定位降级原因")
            if self.disambiguation != DisambiguationOutcome.NOT_FOUND:
                raise ValueError("page_only 只允许在目标未找到/仅知道页时使用")
            if self.anchor_hash is None:
                raise ValueError("page_only 必须携带稳定目标身份锚点哈希")
            if self.anchor_hash != locator_anchor_hash(
                page_artifact_id=self.page_artifact_id,
                source_layer=self.source_layer,
                source_text_sha256=self.source_text_sha256,
                precision=self.precision,
                target_id=self.target_id,
                excerpt=self.excerpt,
                disambiguation=self.disambiguation,
                degradation_reason=self.degradation_reason,
            ):
                raise ValueError("page_only 锚点哈希必须由目标和降级证明确定性计算")

        if self.authenticity == LocatorAuthenticity.DEGRADED and not self.degradation_reason:
            raise ValueError("降级定位必须说明降级原因")

        if self.source_layer == LocatorSourceLayer.EFFECTIVE_TEXT:
            if self.processing_revision_id is None or self.effective_text_sha256 is None:
                raise ValueError("effective_text 定位必须绑定处理修订与有效文本投影哈希")
        elif self.processing_revision_id is not None or self.effective_text_sha256 is not None:
            raise ValueError("非 effective_text 定位不能携带处理修订/投影哈希")
        return self


# --------------------------------------------------------------------------- 风险


class OCRRiskScan(VersionedModel):
    """对某一原始 OCR 哈希 + 规则版本运行后的完整风险集合（追加旁路）。

    同一 (ocr_page_id, raw_text_sha256, scanner_rule_version) 三元组幂等复用；
    规则版本变化新建扫描，不覆盖旧扫描。扫描只输出结构化提示，不输出修正文、
    不写 OCRPage/临床事实/规则表达式，也不因识别到数值/单位而重排合并改写
    “且/或/以及/任一/全部”等并列条件。``flags_sha256`` 对完整 flag 集合内容寻址，
    缺行/多行/换绑都会在回放时被拒绝。
    """

    scan_id: str = Field(min_length=1)
    ocr_page_id: str = Field(min_length=1)
    raw_text_sha256: str = Field(pattern=_SHA256)
    scanner_rule_version: str = Field(min_length=1)
    flags: list[OcrRiskFlag] = Field(default_factory=list)
    flags_sha256: str = Field(pattern=_SHA256)
    coverage_status: str = Field(default="complete", min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_scan(self) -> OCRRiskScan:
        _require_utc(self.created_at, "OCRRiskScan.created_at")
        from app.domain.publication import canonical_hash

        seen: set[str] = set()
        for flag in self.flags:
            if flag.risk_id in seen:
                raise ValueError("同一风险扫描内不允许重复 risk_id")
            seen.add(flag.risk_id)
        expected = canonical_hash(
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
                for flag in sorted(self.flags, key=lambda f: f.risk_id)
            ]
        )
        if self.flags_sha256 != expected:
            raise ValueError("风险扫描 flags 集合哈希与 flag 集合不一致")
        return self


class OCRRiskReview(VersionedModel):
    """用户对单个 OCR 风险的追加写核对决议。

    blocking 风险只有在完整处理修订明确选中有效 review 后才视为已核对；仅打开
    页面或保存草稿不算核对。本记录不写临床事实、规则判断或行动。
    """

    review_id: str = Field(min_length=1)
    risk_flag_id: str = Field(min_length=1)
    decision: OcrRiskReviewDecision
    reason: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    base_processing_revision_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    created_at: datetime

    @model_validator(mode="after")
    def validate_review(self) -> OCRRiskReview:
        _require_utc(self.created_at, "OCRRiskReview.created_at")
        return self


class OCRRiskPageReview(VersionedModel):
    """用户对某一 OCR 页全部待核对风险的一次性原子核对决议（追加写审计记录）。

    逐条核对在页级场景不可操作：本记录把「对照原件后本页待核对项一次确认」收敛为
    单事务原子动作——同一事务内为页上每个当前待核对（既无既有核对、又未被该 base
    修订覆盖校对解除）的风险条目各追加一条不可变 ``OCRRiskReview``
    （``created_review_ids`` 一一对应 ``covered_flag_ids``），全部成功或全部回滚。

    激活门禁仍逐条读取 ``OCRRiskReview.risk_flag_id``；本记录不替代门禁、不写临床
    事实或规则判断，只把逐条动作收敛为一次原子提交并保留来源快照
    （页原文哈希 + 所选扫描 + 规则版本）供审计回放。``covered_flag_sha256`` 对
    覆盖集合内容寻址，缺 flag/多 flag/换绑都在回放时被拒绝。
    """

    page_review_id: str = Field(min_length=1)
    ocr_page_id: str = Field(min_length=1)
    scan_id: str = Field(min_length=1)
    raw_text_sha256: str = Field(pattern=_SHA256)
    scanner_rule_version: str = Field(min_length=1)
    decision: OcrRiskReviewDecision
    reason: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    base_processing_revision_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    covered_flag_ids: list[str] = Field(min_length=1)
    created_review_ids: list[str] = Field(min_length=1)
    covered_flag_sha256: str = Field(pattern=_SHA256)
    created_at: datetime

    @model_validator(mode="after")
    def validate_page_review(self) -> OCRRiskPageReview:
        _require_utc(self.created_at, "OCRRiskPageReview.created_at")
        if len(set(self.covered_flag_ids)) != len(self.covered_flag_ids):
            raise ValueError("覆盖 flag 集合不允许重复 flag_id")
        if len(set(self.created_review_ids)) != len(self.created_review_ids):
            raise ValueError("原子核对产生的逐条 review_id 不允许重复")
        from app.domain.publication import canonical_hash

        expected = canonical_hash(sorted(self.covered_flag_ids))
        if self.covered_flag_sha256 != expected:
            raise ValueError("页级核对的 covered_flag_sha256 与覆盖 flag 集合不一致")
        return self


# --------------------------------------------------------------------------- 校对


class CorrectionRecord(VersionedModel):
    """对原始 OCR 来源锚点的追加写校对记录（覆盖层，不替换 raw text）。

    所有校对都锚定同一不可变 raw OCR（``raw_text_sha256`` + 原始字符位置/范围）。
    ``text_start == text_end`` 表示在该精确位置插入漏识别文字，此时
    ``original_text`` 必须为空；非零范围仍表示替换。校对不是
    锚定前一版 effective text，避免字符偏移逐版漂移。``supersedes_correction_id``
    显式替代前项；一个完整修订对同一原始范围最多选择一个有效 correction。极性/
    数值/小数点/单位/日期/语义连接词变化必须二次确认（``requires_confirmation``），
    确认前不得进入完整修订的有效校对集合。
    """

    correction_id: str = Field(min_length=1)
    ocr_page_id: str = Field(min_length=1)
    raw_text_sha256: str = Field(pattern=_SHA256)
    text_start: int = Field(ge=0)
    text_end: int = Field(ge=0)
    original_text: str
    corrected_text: str
    change_kind: CorrectionChangeKind
    requires_confirmation: bool = False
    confirmation_actor: str | None = None
    confirmation_at: datetime | None = None
    reason: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    base_processing_revision_id: str = Field(min_length=1)
    supersedes_correction_id: str | None = None
    affected_scope: list[str] = Field(default_factory=list)
    created_at: datetime

    @model_validator(mode="after")
    def validate_correction(self) -> CorrectionRecord:
        _require_utc(self.created_at, "CorrectionRecord.created_at")
        if self.confirmation_at is not None:
            _require_utc(self.confirmation_at, "CorrectionRecord.confirmation_at")
        if self.text_end < self.text_start:
            raise ValueError("校对范围必须有效")
        if self.text_start == self.text_end:
            if self.original_text != "":
                raise ValueError("零长度插入锚点的原文必须为空")
        elif self.text_end - self.text_start != len(self.original_text):
            raise ValueError("校对原文本长度必须与范围一致")
        if self.corrected_text == self.original_text:
            raise ValueError("校对必须改变文本，不能提交无变化记录")
        if self.change_kind in BLOCKING_CORRECTION_KINDS and not self.requires_confirmation:
            raise ValueError("关键语义变化必须要求二次确认")
        if (self.confirmation_actor is None) != (self.confirmation_at is None):
            raise ValueError("确认人与确认时间必须同时存在或同时为空")
        return self


# --------------------------------------------------------------------------- 被提及资料


class ReferencedDocumentRevision(VersionedModel):
    """“资料中提及但未提供”的不可变登记修订。

    ``referenced_document_id`` 是稳定逻辑身份，``revision`` 是其修订链位置。
    确定性模式只能生成 ``proposed``，绝不自动 confirmed/provided；每条
    ``confirmed`` 记录必须有可回放触发定位，无法提供 trigger 时不能伪装成“原文
    提及”。dismissed 只表示用户解除候选，不删除候选/触发原文/历史。本功能不创建
    ClinicalFact、规则判断、入排结论或 ActionRequest。
    """

    revision_id: str = Field(min_length=1)
    referenced_document_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    document_type: str | None = None
    source_party: str | None = None
    trigger_locator_id: str | None = None
    origin: ReferencedDocumentOrigin
    pattern_version: str | None = None
    status: ReferencedDocumentStatus
    user_reviewed: bool = False
    reason: str | None = None
    revision: int = Field(ge=1)
    supersedes_revision_id: str | None = None
    created_at: datetime
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_revision(self) -> ReferencedDocumentRevision:
        _require_utc(self.created_at, "ReferencedDocumentRevision.created_at")
        if self.revision == 1 and self.supersedes_revision_id is not None:
            raise ValueError("初始被提及资料修订不能引用前序修订")
        if self.revision > 1 and self.supersedes_revision_id is None:
            raise ValueError("非初始被提及资料修订必须引用其前序修订")
        if self.revision > 1 and (self.reason is None or not self.reason.strip()):
            raise ValueError("非初始被提及资料修订必须保留非空操作原因")
        if self.status == ReferencedDocumentStatus.CONFIRMED and self.trigger_locator_id is None:
            raise ValueError("被确认的被提及资料必须保留可回放触发定位")
        if (
            self.origin == ReferencedDocumentOrigin.DETERMINISTIC_CANDIDATE
            and self.status != ReferencedDocumentStatus.PROPOSED
            and (not self.user_reviewed or self.revision == 1)
        ):
            raise ValueError("确定性候选只有经过用户复核后的后续修订才能确认或解除")
        return self


class ReferencedDocumentResolutionRevision(VersionedModel):
    """被提及资料的不可变满足修订：unresolved 或 provided。

    provided 时必须引用同一 scope 且属于该完整处理修订快照成员的
    ``source_document_version_id``；解除关联产生新的 unresolved 修订，不删除旧的
    满足关系。旧处理修订仍回放 unresolved。
    """

    resolution_revision_id: str = Field(min_length=1)
    referenced_document_id: str = Field(min_length=1)
    status: ReferencedDocumentResolutionStatus
    source_document_version_id: str | None = None
    revision: int = Field(ge=1)
    supersedes_resolution_revision_id: str | None = None
    created_at: datetime
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_resolution(self) -> ReferencedDocumentResolutionRevision:
        _require_utc(self.created_at, "ReferencedDocumentResolutionRevision.created_at")
        if self.revision == 1 and self.supersedes_resolution_revision_id is not None:
            raise ValueError("初始满足修订不能引用前序修订")
        if self.revision > 1 and self.supersedes_resolution_revision_id is None:
            raise ValueError("非初始满足修订必须引用其前序修订")
        if self.status == ReferencedDocumentResolutionStatus.PROVIDED:
            if self.source_document_version_id is None:
                raise ValueError("provided 满足关系必须绑定快照成员资料版本")
        elif self.source_document_version_id is not None:
            raise ValueError("unresolved 满足关系不能绑定资料版本")
        return self


# --------------------------------------------------------------------------- 激活


class EvidenceActivationEvent(VersionedModel):
    """审核节点版本切换的追加写激活事件（激活与回滚都用本记录）。

    事件记录 from/to 两对 (snapshot, complete revision) 指针、事件类别、原因、
    触发 job、预期修订号与时间。成功激活后指针与事件在同一事务内更新；回滚也是
    新事件，不静默改写旧事件/旧指针/创建时间。
    """

    event_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    activation_seq: int = Field(ge=1)
    event_kind: ActivationEventKind
    from_snapshot_id: str | None = None
    from_revision_id: str | None = None
    to_snapshot_id: str = Field(min_length=1)
    to_revision_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    job_id: str | None = None
    candidate_id: str | None = None
    expected_revision: int = Field(ge=0)
    resulting_episode_revision: int = Field(ge=1)
    snapshot_status_transitioned: bool = False
    command_sha256: str = Field(pattern=_SHA256)
    created_at: datetime

    @model_validator(mode="after")
    def validate_event(self) -> EvidenceActivationEvent:
        _require_utc(self.created_at, "EvidenceActivationEvent.created_at")
        if (self.from_snapshot_id is None) != (self.from_revision_id is None):
            raise ValueError("激活事件的旧指针必须同时存在或同时为空")
        if (self.from_snapshot_id, self.from_revision_id) == (
            self.to_snapshot_id,
            self.to_revision_id,
        ):
            raise ValueError("激活事件必须切换到不同的活动版本对")
        if self.resulting_episode_revision != self.expected_revision + 1:
            raise ValueError("激活事件完成后的审核节点修订号必须等于预期修订号加一")
        if self.event_kind == ActivationEventKind.ACTIVATE:
            if self.candidate_id is None:
                raise ValueError("启用完整处理修订必须绑定生产候选")
        elif self.candidate_id is not None:
            raise ValueError("回滚事件不能绑定处理候选")
        expected_command = activation_command_hash(
            event_kind=self.event_kind,
            candidate_id=self.candidate_id,
            target_snapshot_id=self.to_snapshot_id,
            target_revision_id=self.to_revision_id,
            expected_revision=self.expected_revision,
            actor=self.actor,
            reason=self.reason,
            job_id=self.job_id,
        )
        if self.command_sha256 != expected_command:
            raise ValueError("激活事件命令哈希与冻结的完整命令不一致")
        return self


def activation_command_hash(
    *,
    event_kind: ActivationEventKind,
    candidate_id: str | None,
    target_snapshot_id: str,
    target_revision_id: str,
    expected_revision: int,
    actor: str,
    reason: str,
    job_id: str | None,
) -> str:
    """启用/回滚命令的完整、可重建幂等身份。"""
    from app.domain.publication import canonical_hash

    return canonical_hash(
        {
            "kind": event_kind.value,
            "candidate": candidate_id,
            "target_snapshot": target_snapshot_id,
            "target_revision": target_revision_id,
            "expected_revision": expected_revision,
            "actor": actor,
            "reason": reason,
            "job": job_id,
        }
    )


# --------------------------------------------------------------------------- 处理候选


class ProcessingCandidateAttemptManifest(VersionedModel):
    """一次候选构建尝试冻结的旁路工件清单。

    后台任务只能消费本清单，不能在取得租约后重新选择链头，避免排队期间新增的
    校对、核对或资料关系被较早命令静默吸收。
    """

    metadata_revision_ids: list[str] = Field(default_factory=list)
    risk_scan_ids: list[str] = Field(default_factory=list)
    risk_review_ids: list[str] = Field(default_factory=list)
    correction_ids: list[str] = Field(default_factory=list)
    locator_ids: list[str] = Field(default_factory=list)
    referenced_document_revision_ids: list[str] = Field(default_factory=list)
    resolution_revision_ids: list[str] = Field(default_factory=list)
    trigger_sidecar_id: str | None = None

    @model_validator(mode="after")
    def validate_manifest(self) -> ProcessingCandidateAttemptManifest:
        for field_name in (
            "metadata_revision_ids",
            "risk_scan_ids",
            "risk_review_ids",
            "correction_ids",
            "locator_ids",
            "referenced_document_revision_ids",
            "resolution_revision_ids",
        ):
            values = getattr(self, field_name)
            if values != sorted(set(values)):
                raise ValueError(f"候选尝试清单 {field_name} 必须排序且不得重复")
        return self


class EvidenceProcessingCandidate(VersionedModel):
    """证据处理候选：绑定快照、base 修订、预期修订号、Job 与幂等键。

    候选把“不可变完整修订”与“等待核对的可变过程”分开：locator/risk scan 等不可变
    工件可在失败后复用；候选状态由追加事件投影（``status`` 是最近一次事件目标）。
    候选冲突/失败后重试不得复用为另一个输入；同键同请求回放，同键异请求冲突。
    """

    candidate_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    base_processing_revision_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    job_id: str | None = None
    idempotency_key: str = Field(min_length=1)
    scanner_rule_version: str = Field(default="slice4.6/v2", min_length=1)
    selected_locator_ids: list[str] = Field(default_factory=list)
    attempt_manifest: ProcessingCandidateAttemptManifest = Field(
        default_factory=ProcessingCandidateAttemptManifest
    )
    candidate_input_sha256: str = Field(pattern=_SHA256)
    complete_revision_id: str | None = None
    status: EvidenceProcessingCandidateStatus
    created_by: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_candidate(self) -> EvidenceProcessingCandidate:
        _require_utc(self.created_at, "EvidenceProcessingCandidate.created_at")
        if self.selected_locator_ids != sorted(set(self.selected_locator_ids)):
            raise ValueError("候选选中的定位必须按 ID 排序且不得重复")
        expected = processing_candidate_input_hash(
            evidence_snapshot_id=self.evidence_snapshot_id,
            base_processing_revision_id=self.base_processing_revision_id,
            expected_revision=self.expected_revision,
            scanner_rule_version=self.scanner_rule_version,
            selected_locator_ids=self.selected_locator_ids,
            attempt_manifest=self.attempt_manifest,
        )
        if self.candidate_input_sha256 != expected:
            raise ValueError("候选输入哈希与冻结的快照、基础修订、扫描版本和定位集合不一致")
        return self


class EvidenceProcessingCandidateEvent(VersionedModel):
    """证据处理候选的一条追加状态事件；最新事件即当前状态。"""

    candidate_id: str = Field(min_length=1)
    seq: int = Field(ge=1)
    from_status: EvidenceProcessingCandidateStatus
    to_status: EvidenceProcessingCandidateStatus
    event_kind: ProcessingCandidateEventKind
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    complete_revision_id: str | None = None
    attempt_manifest: ProcessingCandidateAttemptManifest | None = None
    attempt_input_sha256: str | None = Field(default=None, pattern=_SHA256)
    created_at: datetime

    @model_validator(mode="after")
    def validate_event(self) -> EvidenceProcessingCandidateEvent:
        _require_utc(self.created_at, "EvidenceProcessingCandidateEvent.created_at")
        expected = CANDIDATE_TRANSITIONS.get(self.from_status, {}).get(self.event_kind)
        if expected is None:
            raise ValueError(
                f"候选状态转换 {self.from_status.value} --{self.event_kind.value}--> "
                f"{self.to_status.value} 不在状态表中，拒绝"
            )
        if expected != self.to_status:
            raise ValueError(
                f"候选状态 {self.from_status.value} 经 {self.event_kind.value} "
                f"只能进入 {expected.value}，得到 {self.to_status.value}"
            )
        requires_complete = self.event_kind in {
            ProcessingCandidateEventKind.ALL_GATES_PASSED,
            ProcessingCandidateEventKind.ACTIVATE,
        }
        if requires_complete != (self.complete_revision_id is not None):
            raise ValueError("候选构建完成或启用事件必须且只能绑定其生成的完整处理修订")
        return self


def processing_candidate_input_hash(
    *,
    evidence_snapshot_id: str,
    base_processing_revision_id: str,
    expected_revision: int,
    scanner_rule_version: str,
    selected_locator_ids: list[str],
    attempt_manifest: ProcessingCandidateAttemptManifest | None = None,
) -> str:
    """候选构建命令的完整、可重建输入身份。"""
    from app.domain.publication import canonical_hash

    return canonical_hash(
        {
            "snapshot": evidence_snapshot_id,
            "base": base_processing_revision_id,
            "expected_revision": expected_revision,
            "scanner_rule_version": scanner_rule_version,
            "locators": sorted(selected_locator_ids),
            "attempt_manifest": (
                attempt_manifest or ProcessingCandidateAttemptManifest()
            ).model_dump(mode="json"),
        }
    )


# --------------------------------------------------------------------------- 完整处理修订


def _validate_page_manifest(
    manifest: list[EvidenceProcessingRevisionPage], manifest_sha256: str
) -> None:
    """完整修订沿用 base 的用户资料顺序，且每份资料内页码递增。"""
    positions: set[int] = set()
    seen_pages: set[tuple[str, int]] = set()
    current_document_id: str | None = None
    closed_document_ids: set[str] = set()
    previous_page_number = 0
    for entry in manifest:
        if entry.position in positions:
            raise ValueError("页清单位置不能重复")
        positions.add(entry.position)
        page = (entry.source_document_version_id, entry.page_number)
        if page in seen_pages:
            raise ValueError("页清单不允许重复同一页")
        seen_pages.add(page)
        if entry.source_document_version_id != current_document_id:
            if entry.source_document_version_id in closed_document_ids:
                raise ValueError("同一资料的页面必须连续排列，不能被其他资料分隔")
            if current_document_id is not None:
                closed_document_ids.add(current_document_id)
            current_document_id = entry.source_document_version_id
            previous_page_number = 0
        if entry.page_number <= previous_page_number:
            raise ValueError("同一资料的页码必须升序")
        previous_page_number = entry.page_number
    positions_sorted = sorted(positions)
    if positions_sorted != list(range(1, len(manifest) + 1)):
        raise ValueError("页清单位置必须从 1 连续递增")
    from app.domain.publication import evidence_processing_manifest_hash

    expected = evidence_processing_manifest_hash(
        entries=[
            (
                entry.source_document_version_id,
                entry.page_number,
                entry.original_frame,
                entry.page_artifact_id,
                entry.ocr_page_id,
                entry.status.value,
            )
            for entry in manifest
        ]
    )
    if manifest_sha256 != expected:
        raise ValueError("完整处理修订页清单哈希与页清单集合不一致")


def completion_manifest_hash(
    *,
    base_processing_revision_id: str,
    base_processing_revision_sha256: str,
    page_entries: list[tuple[str, str]],
    locators: list[tuple[str, str]],
    risk_scans: list[tuple[str, str]],
    risk_reviews: list[tuple[str, str]],
    corrections: list[tuple[str, str]],
    metadata_revisions: list[tuple[str, str]],
    referenced_documents: list[tuple[str, str]],
    resolutions: list[tuple[str, str]],
) -> str:
    """完整处理修订的闭包内容身份（顺序保持，含子工件 canonical payload hash）。

    对 base 修订 ID + canonical payload hash、每页条目 ID + payload hash，以及每个
    有序子引用 (ID, payload hash) 内容寻址；任一子表缺行、多行、换绑、顺序漂移或
    子 payload 漂移都会改变哈希并在回放/激活时被拒绝。文件名与时间戳排除在外。

    本函数是纯确定性计算：调用方（仓储）负责从数据库读取子记录的 canonical
    payload hash，避免循环哈希完整修订根 payload 本身。
    """
    from app.domain.publication import canonical_hash

    return canonical_hash(
        {
            "manifest": "complete_processing_revision/v2",
            "base": {
                "id": base_processing_revision_id,
                "payload_sha256": base_processing_revision_sha256,
            },
            "pages": [
                {"id": entry_id, "payload_sha256": entry_sha}
                for entry_id, entry_sha in page_entries
            ],
            "locators": [
                {"id": ref_id, "payload_sha256": ref_sha}
                for ref_id, ref_sha in locators
            ],
            "risk_scans": [
                {"id": ref_id, "payload_sha256": ref_sha}
                for ref_id, ref_sha in risk_scans
            ],
            "risk_reviews": [
                {"id": ref_id, "payload_sha256": ref_sha}
                for ref_id, ref_sha in risk_reviews
            ],
            "corrections": [
                {"id": ref_id, "payload_sha256": ref_sha}
                for ref_id, ref_sha in corrections
            ],
            "metadata_revisions": [
                {"id": ref_id, "payload_sha256": ref_sha}
                for ref_id, ref_sha in metadata_revisions
            ],
            "referenced_documents": [
                {"id": ref_id, "payload_sha256": ref_sha}
                for ref_id, ref_sha in referenced_documents
            ],
            "resolutions": [
                {"id": ref_id, "payload_sha256": ref_sha}
                for ref_id, ref_sha in resolutions
            ],
        }
    )


class CompleteEvidenceProcessingRevision(VersionedModel):
    """不可变完整处理修订：在 base 页清单上冻结全部 4.4 关联。

    ``base_processing_revision_id`` 必须属于同一 snapshot/scope 且其页清单逐项等于
    本修订页清单；完整修订不能借机换页、换 OCR 或隐藏失败页。``is_activatable``
    默认 True（通过闭包门禁后才冻结），与 base 修订的 ``Literal[False]`` 明确区分。
    """

    evidence_processing_revision_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    revision_kind: Literal["complete"] = "complete"
    base_processing_revision_id: str = Field(min_length=1)
    producer_candidate_id: str = Field(min_length=1)
    candidate_input_sha256: str = Field(pattern=_SHA256)
    manifest: list[EvidenceProcessingRevisionPage] = Field(default_factory=list)
    manifest_sha256: str = Field(pattern=_SHA256)
    locator_ids: list[str] = Field(default_factory=list)
    risk_scan_ids: list[str] = Field(default_factory=list)
    risk_review_ids: list[str] = Field(default_factory=list)
    correction_ids: list[str] = Field(default_factory=list)
    metadata_revision_ids: list[str] = Field(default_factory=list)
    referenced_document_revision_ids: list[str] = Field(default_factory=list)
    resolution_revision_ids: list[str] = Field(default_factory=list)
    completion_manifest_sha256: str = Field(pattern=_SHA256)
    status: ProcessingRevisionStatus = ProcessingRevisionStatus.READY
    is_activatable: bool = True
    created_at: datetime
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_complete_revision(self) -> CompleteEvidenceProcessingRevision:
        _require_utc(self.created_at, "CompleteEvidenceProcessingRevision.created_at")
        if self.revision_kind != "complete":
            raise ValueError("完整处理修订必须标记 revision_kind=complete")
        if self.status != ProcessingRevisionStatus.READY:
            raise ValueError("完整处理修订只能处于 READY 状态")
        if not self.is_activatable:
            raise ValueError("冻结的完整处理修订必须为可激活候选")

        _validate_page_manifest(self.manifest, self.manifest_sha256)

        for label, values in (
            ("locator", self.locator_ids),
            ("risk scan", self.risk_scan_ids),
            ("risk review", self.risk_review_ids),
            ("correction", self.correction_ids),
            ("metadata revision", self.metadata_revision_ids),
            ("referenced document", self.referenced_document_revision_ids),
            ("resolution", self.resolution_revision_ids),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"完整处理修订内 {label} 引用不允许重复")
        return self
