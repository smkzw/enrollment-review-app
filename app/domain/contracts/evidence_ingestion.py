"""Phase 4 证据快照与资料版本领域契约（Slice 4.1 冻结）。

本模块冻结受试者/审核节点作用域下的不可变证据底座合同，只包含纯校验与确定性
身份计算，不含存储、文件路径或外部调用。覆盖设计书 §3.1 与 §3.2 的资料版本、
元数据修订、证据快照与成员关系：

- ``Subject``                   受试者（沿用 Phase 3 冻结合同，身份语义不变）；
- ``ReviewEpisode``             审核节点（Phase 4）：唯一运行合同来自
                                ``app.domain.contracts.review``（本模块只做兼容
                                再导出，不再维护第二套同名定义）；成对活动指针
                                只能同时存在或同时为空，且仅在候选通过全部发布
                                门禁后原子更新；
- ``SourceBlob``                不可变原始文件身份/存储引用，内容寻址：
                                ``source_blob_id`` 必须等于其 SHA-256；本 Slice 不负责上传
                                或二进制落盘；
- ``SourceDocumentVersion``     逻辑资料的一个不可变版本，绑定来源二进制与
                                项目/受试者/审核节点作用域，显式替代记录
                                ``supersedes_version_id``；
- ``SourceDocumentMetadataRevision``  资料类型/来源方的不可变元数据修订链，
                                用户可改语义不原地改写；自动分类只能是建议
                                （``is_auto_suggestion``）；
- ``EvidenceSnapshotMember``    快照中的一个活动资料成员：某逻辑资料在该快照下
                                生效的版本及其来源（继承/新增/显式替代）；
- ``EvidenceSnapshotStatusEvent`` 候选状态机的不可变状态事件；
- ``EvidenceSnapshot``          不可变证据快照：审核节点当时完整活动文档集合，
                                ``collection_sha256`` 对活动成员集合内容寻址，
                                重复集合确认据此判定 no-op。

Slice 4.1 停止点约束：补充资料快照必须有且只有一个前序快照，完整资料快照不得
继承前序成员；同一快照内每个逻辑资料只能有一个活动版本；集合哈希与成员集合
必须一致；活动快照/处理修订指针必须成对出现。候选状态转换、前序链无环、作用域
门禁与显式替代链由仓储层（worker_02）实施，本模块不提前冻结无表仓储接口；
EvidenceProcessingRevision 与 ActivationEvent 接口由仓储切片冻结。

Phase 3 的 ``app.domain.contracts.evidence`` 投影合同（FixtureV1 等）保持原样，
本模块是 Phase 4 摄入与快照的源合同，消费方按模块导入，不在包根覆盖同名导出。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from .common import RevisionedModel, VersionedModel
from .enums import (
    SnapshotMemberOrigin,
    SnapshotStatus,
    UploadMode,
)
from .review import ReviewEpisode, Subject

__all__ = [
    "EvidenceSnapshot",
    "EvidenceSnapshotMember",
    "EvidenceSnapshotStatusEvent",
    "ReviewEpisode",
    "SourceBlob",
    "SourceDocumentMetadataRevision",
    "SourceDocumentVersion",
    "Subject",
]

_SHA256 = r"^[0-9a-f]{64}$"


class SourceBlob(VersionedModel):
    """不可变原始文件身份/存储引用（内容寻址）：SHA-256 既是内容身份也是主键。

    同一内容在存储层只登记一份身份，但可在不同受试者、审核节点或快照中形成各自
    可审计的资料关联；去重不得合并临床作用域。``storage_ref`` 必须是可移植内容
    寻址引用，不暴露本机绝对路径。
    """

    source_blob_id: str = Field(min_length=1)
    sha256: str = Field(pattern=_SHA256)
    byte_size: int = Field(ge=0)
    media_type: str = Field(min_length=1)
    storage_ref: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_blob_identity(self) -> SourceBlob:
        _require_utc(self.created_at, "SourceBlob.created_at")
        if self.source_blob_id != self.sha256:
            raise ValueError("SourceBlob 内容身份必须等于其 SHA-256")
        if self.storage_ref.startswith("/") or ".." in self.storage_ref:
            raise ValueError("SourceBlob 存储引用必须是可移植内容寻址引用，不能是本机绝对路径")
        return self


class SourceDocumentVersion(VersionedModel):
    """逻辑资料的一个不可变版本，绑定来源二进制与项目/受试者/审核节点作用域。

    同名异内容文件经用户选择后建立明确关系：作为原资料的新版本时
    ``logical_document_id`` 保持不变并记录 ``supersedes_version_id``；并列保留时
    使用新的 ``logical_document_id``。被替代版本只留在历史快照与版本链中，可完整
    回放，不进入新快照活动成员。``version_number`` 是该逻辑资料面向用户的修订号，
    显式替代必然产生大于 1 的版本号。
    """

    source_document_version_id: str = Field(min_length=1)
    logical_document_id: str = Field(min_length=1)
    source_blob_sha256: str = Field(pattern=_SHA256)
    file_name: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    page_count: int | None = Field(default=None, ge=0)
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    version_number: int = Field(ge=1)
    supersedes_version_id: str | None = None
    created_at: datetime
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_version(self) -> SourceDocumentVersion:
        _require_utc(self.created_at, "SourceDocumentVersion.created_at")
        if self.version_number > 1 and self.supersedes_version_id is None:
            raise ValueError("非首版本必须显式替代前序版本")
        if self.supersedes_version_id is not None and self.version_number < 2:
            raise ValueError("显式替代的版本号必须大于等于 2")
        return self


class SourceDocumentMetadataRevision(RevisionedModel):
    """资料类型与来源方的不可变元数据修订；用户可改语义不原地改写。

    每次修改追加一条新修订并引用前序修订；自动分类生成的修订必须标记
    ``is_auto_suggestion=True``，作为建议而非既定事实展示。任一旧修订永远可回放。
    """

    metadata_revision_id: str = Field(min_length=1)
    source_document_version_id: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    source_party: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    is_auto_suggestion: bool = False
    supersedes_metadata_revision_id: str | None = None
    created_at: datetime
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_revision_chain(self) -> SourceDocumentMetadataRevision:
        _require_utc(self.created_at, "SourceDocumentMetadataRevision.created_at")
        if self.revision == 1 and self.supersedes_metadata_revision_id is not None:
            raise ValueError("初始元数据修订不能引用前序修订")
        if self.revision > 1 and self.supersedes_metadata_revision_id is None:
            raise ValueError("非初始元数据修订必须引用其前序修订")
        return self


class EvidenceSnapshotMember(VersionedModel):
    """证据快照中的一个活动资料成员。

    成员把逻辑资料固定到该快照下生效的版本；被替代版本通过版本链回放，不进入
    活动成员。``origin`` 记录该成员相对前序快照的来源（继承/新增/显式替代），
    完整资料快照的成员只能是 ``added``。
    """

    member_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    logical_document_id: str = Field(min_length=1)
    source_document_version_id: str = Field(min_length=1)
    origin: SnapshotMemberOrigin


class EvidenceSnapshotStatusEvent(VersionedModel):
    """证据快照候选状态机的一条不可变追加事件。"""

    snapshot_id: str = Field(min_length=1)
    seq: int = Field(ge=1)
    from_status: SnapshotStatus
    to_status: SnapshotStatus
    event: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_event(self) -> EvidenceSnapshotStatusEvent:
        _require_utc(self.created_at, "EvidenceSnapshotStatusEvent.created_at")
        return self


class EvidenceSnapshot(VersionedModel):
    """不可变证据快照：审核节点当时完整活动文档集合。

    补充资料快照必须有且只有一个前序快照并继承其仍有效成员；完整资料快照不继承
    前序成员，但保存与上一有效快照的比较基线。``collection_sha256`` 对活动成员
    集合内容寻址，同一作用域、上传方式与活动成员集合的重复确认返回既有候选或
    活动快照（no-op），不生成内容完全相同的新快照。候选状态转换与发布门禁由
    仓储/门禁层实施，本合同只冻结结构不变量。
    """

    evidence_snapshot_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    upload_mode: UploadMode
    prior_snapshot_id: str | None = None
    comparison_snapshot_id: str | None = None
    members: list[EvidenceSnapshotMember] = Field(default_factory=list)
    collection_sha256: str = Field(pattern=_SHA256)
    status: SnapshotStatus
    created_at: datetime
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_snapshot(self) -> EvidenceSnapshot:
        from app.domain.publication import evidence_snapshot_collection_hash

        _require_utc(self.created_at, "EvidenceSnapshot.created_at")

        if self.upload_mode == UploadMode.INCREMENTAL and self.prior_snapshot_id is None:
            raise ValueError("补充资料快照必须引用唯一的有效前序快照")
        if self.upload_mode == UploadMode.FULL and self.prior_snapshot_id is not None:
            raise ValueError("完整资料快照不能静默继承前序快照")
        if self.upload_mode == UploadMode.INCREMENTAL and (
            self.comparison_snapshot_id != self.prior_snapshot_id
        ):
            raise ValueError("补充资料快照的差异基线必须等于其前序快照")

        seen_logical: set[str] = set()
        for member in self.members:
            if member.snapshot_id != self.evidence_snapshot_id:
                raise ValueError("快照成员必须属于当前快照")
            if member.logical_document_id in seen_logical:
                raise ValueError("同一快照中每个逻辑资料只能有一个活动版本")
            seen_logical.add(member.logical_document_id)
            if self.upload_mode == UploadMode.FULL and member.origin != SnapshotMemberOrigin.ADDED:
                raise ValueError("完整资料快照的成员只能来自本次选择，不得继承前序")

        expected = evidence_snapshot_collection_hash(
            members=[
                (member.logical_document_id, member.source_document_version_id)
                for member in self.members
            ]
        )
        if self.collection_sha256 != expected:
            raise ValueError("证据快照集合哈希与活动成员集合不一致")

        if self.status in {SnapshotStatus.READY, SnapshotStatus.ACTIVE} and not self.members:
            raise ValueError("就绪或活动的证据快照不能为空集合")
        return self


def _require_utc(value: datetime, field_name: str) -> None:
    """Reject naive or non-UTC timestamps at the Phase 4 contract boundary."""
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")
