"""Slice 4.4 证据处理/校对/激活/被提及资料 API 契约（WP-44C）。

只做协议转换：请求体携带机器值（枚举/哈希/编号），响应把机器值投影为自然中文
标签。页接口**分别**暴露原始识别、校对后文本、所选校对、风险扫描/核对与定位
精度/降级，字段命名不得把校对层伪装成“原始识别”。current 只来自审核节点成对
活动指针，不使用创建时间、列表顺序或状态推断。被提及资料所有写操作都创建新的
不可变修订，不执行原地 UPDATE/DELETE。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.api.v2.schemas import _StrictModel
from app.domain.contracts.enums import (
    CorrectionChangeKind,
    OcrRiskReviewDecision,
    ReferencedDocumentOrigin,
    ReferencedDocumentResolutionStatus,
)

# --------------------------------------------------------------------------- 页读取


class OcrRiskFlagDTO(_StrictModel):
    """单个结构化识别风险：类别/阻断等级/原文位置/规则版本。"""

    risk_id: str
    kind: str
    kind_label: str
    level: str
    level_label: str
    text: str
    text_start: int
    text_end: int
    detail: str | None = None
    rule_version: str


class OcrRiskScanDTO(_StrictModel):
    """对某一原始识别文本 + 规则版本的完整风险扫描（追加旁路，不改原文）。"""

    scan_id: str
    ocr_page_id: str
    raw_text_sha256: str
    scanner_rule_version: str
    flags_sha256: str
    coverage_status: str
    created_at: datetime
    flags: list[OcrRiskFlagDTO] = Field(default_factory=list)


class OcrRiskReviewDTO(_StrictModel):
    """用户对单个风险的追加写核对决议。"""

    review_id: str
    risk_flag_id: str
    decision: str
    decision_label: str
    reason: str
    actor: str
    base_processing_revision_id: str
    expected_revision: int
    created_at: datetime


class CorrectionDTO(_StrictModel):
    """对原始识别文本固定范围的替换，或在精确字符位置的插入。"""

    correction_id: str
    ocr_page_id: str
    raw_text_sha256: str
    text_start: int
    text_end: int
    original_text: str
    corrected_text: str
    change_kind: str
    change_kind_label: str
    requires_confirmation: bool
    confirmation_actor: str | None = None
    confirmation_at: datetime | None = None
    reason: str
    actor: str
    base_processing_revision_id: str
    supersedes_correction_id: str | None = None
    affected_scope: list[str] = Field(default_factory=list)
    created_at: datetime


class LocatorDTO(_StrictModel):
    """证据定位工件：诚实精度 + 降级原因（降级不是错误）。"""

    locator_id: str
    page_artifact_id: str
    ocr_page_id: str | None = None
    source_document_version_id: str
    page_number: int
    source_layer: str
    source_layer_label: str
    source_text_sha256: str
    target_id: str
    precision: str
    precision_label: str
    degradation_reason: str | None = None
    text_start: int | None = None
    text_end: int | None = None
    excerpt: str | None = None
    disambiguation: str
    locator_algorithm_version: str
    authenticity: str
    match_confidence: float | None = None
    bbox: BoundingBoxDTO | None = None
    coordinate_frame: CoordinateFrameDTO | None = None
    coordinate_transform_version: str | None = None


class BoundingBoxDTO(_StrictModel):
    """经真实性门禁验证的页内矩形。"""

    x0: float
    y0: float
    x1: float
    y1: float


class CoordinateFrameDTO(_StrictModel):
    """区域定位所使用的稳定原始页坐标系。"""

    space: str
    page_width: float
    page_height: float
    rotation: int
    transform_version: str


class OcrPageDTO(_StrictModel):
    """页分层读取：原文 / 校对后文本 / 所选校对 / 风险核对 / 定位精度 并列。"""

    ocr_page_id: str
    page_artifact_id: str
    source_document_version_id: str
    page_number: int
    source_sha256: str
    raw_text: str
    raw_text_sha256: str
    status: str
    status_label: str
    # 有效文本投影所用的完整处理修订；未指定且当前活动版本存在时取活动版本。
    processing_revision_id: str | None = None
    is_current_revision: bool
    effective_text: str | None = None
    effective_text_sha256: str | None = None
    selected_corrections: list[CorrectionDTO] = Field(default_factory=list)
    risk_scans: list[OcrRiskScanDTO] = Field(default_factory=list)
    risk_reviews: list[OcrRiskReviewDTO] = Field(default_factory=list)
    locators: list[LocatorDTO] = Field(default_factory=list)


# --------------------------------------------------------------------------- 校对


class CorrectionConfirmationPayload(_StrictModel):
    """关键语义变化的显式二次确认（极性/数值/小数点/单位/日期/语义连接词）。"""

    actor: str = Field(min_length=1, max_length=128)
    at: datetime


class CorrectionCreateRequest(_StrictModel):
    """校对写命令：必须携带原识别哈希、原始范围、base 处理修订、预期审核节点
    修订号与幂等键；关键变化必须带显式确认载荷。"""

    raw_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text_start: int = Field(ge=0)
    text_end: int = Field(ge=0)
    original_text: str = Field(max_length=4000)
    corrected_text: str = Field(max_length=4000)
    change_kind: CorrectionChangeKind
    reason: str = Field(min_length=1, max_length=2000)
    base_processing_revision_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=256)
    actor: str | None = Field(default=None, max_length=128)
    supersedes_correction_id: str | None = None
    confirmation: CorrectionConfirmationPayload | None = None
    affected_scope: list[str] = Field(default_factory=list)
    target_candidate_id: str | None = None
    expected_candidate_event_seq: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_source_anchor(self) -> "CorrectionCreateRequest":
        if self.text_end < self.text_start:
            raise ValueError("校对结束位置不得早于开始位置")
        if self.text_start == self.text_end:
            if self.original_text != "":
                raise ValueError("补入漏识别文字时，插入位置的原文必须为空")
        elif not self.original_text:
            raise ValueError("替换校对必须携带选中的原文")
        return self


class CorrectionCreateResponse(_StrictModel):
    """校对结果：``created`` True=新建(201)，False=同幂等键回放(200)。"""

    correction: CorrectionDTO
    created: bool
    candidate_id: str
    job_id: str
    candidate_status: str
    candidate_status_label: str
    candidate_event_seq: int = Field(ge=0)
    complete_revision_id: str | None = None


# --------------------------------------------------------------------------- 风险核对


class RiskReviewCreateRequest(_StrictModel):
    """对单个风险条目的追加写核对（``risk_flag_id`` 形如 ``<scan_id>:<risk_id>``）。"""

    risk_flag_id: str = Field(min_length=1)
    decision: OcrRiskReviewDecision
    reason: str = Field(min_length=1, max_length=2000)
    base_processing_revision_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=256)
    actor: str | None = Field(default=None, max_length=128)
    target_candidate_id: str | None = None
    expected_candidate_event_seq: int | None = Field(default=None, ge=0)


class RiskReviewCreateResponse(_StrictModel):
    """风险核对结果：``created`` True=新建(201)，False=幂等回放(200)。"""

    review: OcrRiskReviewDTO
    created: bool
    candidate_id: str
    job_id: str
    candidate_status: str
    candidate_status_label: str
    candidate_event_seq: int = Field(ge=0)
    complete_revision_id: str | None = None


class OCRRiskPageReviewDTO(_StrictModel):
    """页级原子风险核对审计记录：来源快照 + 覆盖集合 + 逐条物化映射。"""

    page_review_id: str
    ocr_page_id: str
    scan_id: str
    raw_text_sha256: str
    scanner_rule_version: str
    decision: str
    decision_label: str
    reason: str
    actor: str
    base_processing_revision_id: str
    expected_revision: int
    covered_flag_ids: list[str]
    created_review_ids: list[str]
    covered_flag_sha256: str
    created_at: datetime


class PageRiskReviewCreateRequest(_StrictModel):
    """对页上全部待核对风险的一次原子核对（``scan_id`` 指用户所核对扫描版本）。"""

    scan_id: str = Field(min_length=1)
    decision: OcrRiskReviewDecision
    reason: str = Field(min_length=1, max_length=2000)
    base_processing_revision_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=256)
    actor: str | None = Field(default=None, max_length=128)
    target_candidate_id: str | None = None
    expected_candidate_event_seq: int | None = Field(default=None, ge=0)


class PageRiskReviewCreateResponse(_StrictModel):
    """页级原子核对结果：``created`` True=新建(201)，False=幂等回放(200)。"""

    page_review: OCRRiskPageReviewDTO
    reviews: list[OcrRiskReviewDTO] = Field(default_factory=list)
    created: bool
    candidate_id: str
    job_id: str
    candidate_status: str
    candidate_status_label: str
    candidate_event_seq: int = Field(ge=0)
    complete_revision_id: str | None = None


# --------------------------------------------------------------------------- 完整处理修订


class GateResultDTO(_StrictModel):
    """完整处理修订激活门禁的逐项结果投影（读路径已强校验，此处如实报告）。"""

    gate: str
    gate_label: str
    status: str
    status_label: str
    detail: str


class ProcessingRevisionPageDTO(_StrictModel):
    """处理修订冻结的有序页索引，供工作台发现并打开真实识别页。

    这里只投影不可变页清单身份和诚实处理状态；失败页没有 ``ocr_page_id``，
    前端不得为其构造识别页链接或伪造可查看文本。
    """

    entry_id: str
    position: int
    source_document_version_id: str
    page_number: int
    original_frame: str | None = None
    page_artifact_id: str
    ocr_page_id: str | None = None
    status: str
    status_label: str
    failure_reason: str | None = None
    image_available: bool
    page_width: float | None = None
    page_height: float | None = None


class ProcessingRevisionDTO(_StrictModel):
    """证据处理修订读取：kind / base ID / 快照 ID / 清单 hashes / 可激活 / 逐门禁。"""

    evidence_processing_revision_id: str
    revision_kind: str
    revision_kind_label: str
    evidence_snapshot_id: str
    base_processing_revision_id: str | None = None
    project_id: str
    subject_id: str
    review_episode_id: str
    status: str
    status_label: str
    is_activatable: bool
    is_current: bool
    manifest_sha256: str
    completion_manifest_sha256: str | None = None
    pages: list[ProcessingRevisionPageDTO] = Field(default_factory=list)
    risk_flag_count: int = Field(default=0, ge=0)
    pending_risk_flag_count: int = Field(default=0, ge=0)
    locator_ids: list[str] = Field(default_factory=list)
    risk_scan_ids: list[str] = Field(default_factory=list)
    risk_review_ids: list[str] = Field(default_factory=list)
    correction_ids: list[str] = Field(default_factory=list)
    metadata_revision_ids: list[str] = Field(default_factory=list)
    referenced_document_revision_ids: list[str] = Field(default_factory=list)
    resolution_revision_ids: list[str] = Field(default_factory=list)
    gates: list[GateResultDTO] = Field(default_factory=list)
    created_at: datetime
    created_by: str


class BuildRevisionRequest(_StrictModel):
    """构建完整处理修订：绑定快照 / base 修订 / 预期修订号 / 幂等键。"""

    evidence_snapshot_id: str = Field(min_length=1)
    base_processing_revision_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=256)
    actor: str | None = Field(default=None, max_length=128)
    scanner_rule_version: str | None = None
    selected_locator_ids: list[str] = Field(default_factory=list)


class BuildRevisionResponse(_StrictModel):
    """构建结果：候选状态；``revision`` 仅在 READY 时给出冻结的完整处理修订。"""

    candidate_id: str
    job_id: str
    candidate_status: str
    candidate_status_label: str
    candidate_event_seq: int = Field(ge=0)
    complete_revision_id: str | None = None
    created: bool
    revision: ProcessingRevisionDTO | None = None


class ProcessingCandidateDTO(_StrictModel):
    """持久资料版本候选状态；供工作台恢复、轮询和继续核对。"""

    candidate_id: str
    job_id: str
    candidate_status: str
    candidate_status_label: str
    candidate_event_seq: int = Field(ge=0)
    complete_revision_id: str | None = None


class ActivateRequest(_StrictModel):
    """启用/回滚命令：必须携带预期审核节点修订号与稳定幂等键；候选默认取
    完整修订的生产候选。"""

    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=256)
    actor: str | None = Field(default=None, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)
    candidate_id: str | None = None
    job_id: str | None = None


class ActivationEventDTO(_StrictModel):
    """激活/回滚事件：返回事件 ID、旧/新活动指针对与新审核节点修订号。"""

    event_id: str
    review_episode_id: str
    activation_seq: int
    event_kind: str
    event_kind_label: str
    from_snapshot_id: str | None = None
    from_revision_id: str | None = None
    to_snapshot_id: str
    to_revision_id: str
    reason: str
    actor: str
    candidate_id: str | None = None
    expected_revision: int
    resulting_episode_revision: int
    snapshot_status_transitioned: bool
    created_at: datetime


# --------------------------------------------------------------------------- 被提及资料


class ReferencedDocumentResolutionDTO(_StrictModel):
    """被提及资料的当前满足修订（unresolved/provided）。"""

    resolution_revision_id: str | None = None
    status: str | None = None
    status_label: str | None = None
    source_document_version_id: str | None = None
    revision: int | None = None
    created_by: str | None = None
    created_at: datetime | None = None


class ReferencedDocumentDTO(_StrictModel):
    """被提及资料的当前登记修订 + 当前满足修订。"""

    revision_id: str
    referenced_document_id: str
    project_id: str
    subject_id: str
    review_episode_id: str
    description: str
    document_type: str | None = None
    source_party: str | None = None
    origin: str
    origin_label: str
    pattern_version: str | None = None
    status: str
    status_label: str
    user_reviewed: bool
    reason: str | None = None
    revision: int
    supersedes_revision_id: str | None = None
    trigger_locator_id: str | None = None
    resolution: ReferencedDocumentResolutionDTO | None = None
    created_at: datetime
    created_by: str


class ReferencedDocumentListDTO(_StrictModel):
    """某审核节点下被提及资料的当前链头列表。"""

    subject_id: str
    review_episode_id: str
    items: list[ReferencedDocumentDTO] = Field(default_factory=list)


class ReferencedDocumentCreateRequest(_StrictModel):
    """登记被提及资料：作用域由服务端从路径受试者与 ``review_episode_id`` 重验；
    携带审核节点预期修订号与稳定幂等键。"""

    review_episode_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=2000)
    document_type: str | None = Field(default=None, max_length=128)
    source_party: str | None = Field(default=None, max_length=128)
    origin: ReferencedDocumentOrigin = ReferencedDocumentOrigin.MANUAL
    pattern_version: str | None = Field(default=None, max_length=128)
    trigger_locator_id: str | None = None
    actor: str | None = Field(default=None, max_length=128)


class ReferencedDocumentReviseRequest(_StrictModel):
    """修改候选描述/类型/来源方：追加新修订，保留触发定位与状态历史。

    ``expected_revision`` 是当前登记修订链头修订号（乐观并发）。"""

    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=2000)
    document_type: str | None = Field(default=None, max_length=128)
    source_party: str | None = Field(default=None, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)
    actor: str | None = Field(default=None, max_length=128)


class ReferencedDocumentConfirmRequest(_StrictModel):
    """确认候选：必须携带可回放触发定位，绝不自动 confirmed。

    ``expected_revision`` 是当前登记修订链头修订号（乐观并发）。"""

    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=256)
    trigger_locator_id: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=2000)
    actor: str | None = Field(default=None, max_length=128)


class ReferencedDocumentDismissRequest(_StrictModel):
    """解除候选：只追加 dismissed 修订，不删除候选/触发原文/历史。

    ``expected_revision`` 是当前登记修订链头修订号（乐观并发）。"""

    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1, max_length=2000)
    actor: str | None = Field(default=None, max_length=128)


class ReferencedDocumentResolveRequest(_StrictModel):
    """追加满足修订：provided 必须绑定该快照成员资料版本。

    ``expected_revision`` 是当前满足修订链头修订号（乐观并发；无满足链时为 0）。"""

    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=256)
    status: ReferencedDocumentResolutionStatus = ReferencedDocumentResolutionStatus.PROVIDED
    source_document_version_id: str | None = None
    actor: str | None = Field(default=None, max_length=128)
