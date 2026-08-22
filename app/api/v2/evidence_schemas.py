"""V2 证据上传预览/确认/快照 API 契约（Slice 4.2）。

只做协议转换：请求体携带机器值（枚举/哈希/编号），响应把机器值投影为自然中文
标签。作用域（project/subject/review_episode）一律由服务端从审核节点与路径派生并
重验，客户端不得提交项目/受试者/节点归属声明；``preview_sha256`` 是确认幂等所需的
确定性摘要，服务端会重算核验，不信任前端摘要。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.api.v2.schemas import _StrictModel
from app.domain.contracts.enums import (
    UploadConflictResolution,
    UploadMode,
)


class EvidenceUploadItemDTO(_StrictModel):
    """逐文件预览条目：机器分类 + 中文类别/原因/下一步动作。"""

    item_id: str
    file_name: str
    byte_size: int
    media_type: str
    status: str
    status_label: str
    processing_hint: str
    processing_hint_label: str
    reason: str
    next_action: str
    logical_document_id: str | None = None
    existing_version_id: str | None = None
    error_detail: str | None = None


class EvidenceUploadPreviewDTO(_StrictModel):
    """上传预览：绑定作用域、上传方式、基准修订号与逐文件差异。"""

    preview_id: str
    project_id: str
    subject_id: str
    review_episode_id: str
    upload_mode: str
    upload_mode_label: str
    base_revision: int
    base_snapshot_id: str | None = None
    status: str
    status_label: str
    items: list[EvidenceUploadItemDTO] = Field(default_factory=list)
    matching_snapshot_id: str | None = None
    matching_snapshot_status: str | None = None
    matching_snapshot_status_label: str | None = None
    preview_sha256: str
    created_at: datetime
    created_by: str


class EvidenceMetadataRevisionDTO(_StrictModel):
    metadata_revision_id: str
    source_document_version_id: str
    revision: int
    document_type: str
    source_party: str
    reason: str
    is_auto_suggestion: bool
    supersedes_metadata_revision_id: str | None = None
    created_at: datetime
    created_by: str


class EvidenceMetadataRevisionRequest(_StrictModel):
    document_type: str = Field(min_length=1, max_length=128)
    source_party: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=500)
    expected_metadata_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=256)
    actor: str | None = Field(default=None, max_length=128)

    @field_validator("document_type", "source_party", "reason")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("请填写完整内容")
        return value


class EvidenceMetadataRevisionResponse(_StrictModel):
    created: bool
    metadata: EvidenceMetadataRevisionDTO


class EvidenceSnapshotMemberDTO(_StrictModel):
    """证据快照活动成员：固定到具体逻辑资料版本，中文来源标签。"""

    member_id: str
    snapshot_id: str
    logical_document_id: str
    source_document_version_id: str
    file_name: str
    media_type: str
    version_number: int
    origin: str
    origin_label: str
    metadata_head: EvidenceMetadataRevisionDTO


class EvidenceSnapshotCandidateDTO(_StrictModel):
    """最近一次资料版本生成状态，供刷新后继续核对。"""

    candidate_id: str
    job_id: str | None = None
    candidate_status: str
    candidate_status_label: str
    candidate_event_seq: int = Field(ge=0)
    complete_revision_id: str | None = None


class EvidenceSnapshotDTO(_StrictModel):
    """不可变证据快照：当时完整活动文档集合与候选状态。

    ``is_current`` 只来自审核节点成对活动指针的投影（``active_evidence_snapshot_id``
    是否等于本快照），绝不从创建时间、列表顺序或 ``status=active`` 推断。
    """

    evidence_snapshot_id: str
    project_id: str
    subject_id: str
    review_episode_id: str
    upload_mode: str
    upload_mode_label: str
    prior_snapshot_id: str | None = None
    comparison_snapshot_id: str | None = None
    status: str
    status_label: str
    is_current: bool
    base_processing_revision_id: str | None = None
    upload_job_id: str | None = None
    latest_processing_candidate: EvidenceSnapshotCandidateDTO | None = None
    members: list[EvidenceSnapshotMemberDTO] = Field(default_factory=list)
    collection_sha256: str
    created_at: datetime
    created_by: str


class EvidenceSnapshotListDTO(_StrictModel):
    """某受试者审核节点下的证据快照列表。

    同时暴露审核节点成对活动指针，供前端投影 ``is_current``，禁止用快照自身
    状态/时间/顺序猜测当前版本。
    """

    subject_id: str
    review_episode_id: str
    active_evidence_snapshot_id: str | None = None
    active_evidence_processing_revision_id: str | None = None
    items: list[EvidenceSnapshotDTO] = Field(default_factory=list)


class EvidenceCommitRequest(_StrictModel):
    """确认命令：预览摘要哈希、期望基准修订号、幂等键与同名异内容处置。

    ``preview_id`` 由路径 ``/evidence-upload-previews/{preview_id}/commit`` 唯一
    确定，不再在请求体重复提交；作用域（project/subject/review_episode）由服务端
    从预览记录派生并重验，客户端不得提交项目/受试者/节点归属声明。
    """

    preview_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    upload_mode: UploadMode
    base_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=256)
    actor: str | None = Field(default=None, max_length=128)
    resolutions: dict[str, UploadConflictResolution] = Field(default_factory=dict)


class EvidenceResolutionDecisionDTO(_StrictModel):
    """一个同名异内容文件在确认时实际应用的处置。"""

    item_id: str
    logical_document_id: str
    resolution: str
    resolution_label: str
    source_document_version_id: str
    supersedes_version_id: str | None = None


class EvidenceCommitResponse(_StrictModel):
    """确认结果：候选快照与持久任务；created/replayed/duplicate 三标志互斥可解释。

    - 新建候选：``created=True, replayed=False, duplicate=False``（HTTP 201）；
    - 同一幂等键回放：``created=False, replayed=True``，``duplicate`` 保留原确认
      是否命中重复集合的事实（HTTP 200）；
    - 新预览/新幂等键命中同集合候选：``created=False, replayed=False,
      duplicate=True``（HTTP 200）。
    """

    commit_id: str
    preview_id: str
    evidence_snapshot_id: str
    project_id: str
    subject_id: str
    review_episode_id: str
    upload_mode: str
    upload_mode_label: str
    idempotency_key: str
    job_id: str | None = None
    created: bool
    replayed: bool
    duplicate: bool
    resolutions: list[EvidenceResolutionDecisionDTO] = Field(default_factory=list)
    snapshot: EvidenceSnapshotDTO
    created_at: datetime
    created_by: str


class EvidenceFileProgressDTO(_StrictModel):
    """单文件处理进度投影（中文业务状态，不暴露内部列名/日志）。"""

    source_document_version_id: str
    file_name: str
    page_total: int
    page_succeeded: int
    page_failed: int
    status: str
    status_label: str


class EvidenceProgressDTO(_StrictModel):
    """一次证据处理任务的只读进度投影。

    总页数覆盖本次全部资料；``files`` 每个资料版本只投影最新一次
    图像识别运行（重试不重复累计）。``scope_note`` 用中文说明直接读取页
    和图像识别页的区别。
    """

    job_id: str
    job_state: str
    job_state_label: str
    total_pages: int
    completed_pages: int
    failed_pages: int
    pending_pages: int
    scope_note: str
    files: list[EvidenceFileProgressDTO] = Field(default_factory=list)
