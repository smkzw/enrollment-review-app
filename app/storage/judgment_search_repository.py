"""判断检索覆盖摘要的追加写仓储与按权威元组的最新摘要查询。

持久化合同与列镜像遵循 ``page_review_repository`` 的既有约定：正文以
``payload_json``（规范化 JSON + 哈希）为准，镜像列仅供直接查询。摘要身份
由权威元组 + 合同正文内容寻址派生（合同本身不含身份字段）：同权威同内容
幂等去重，重跑产生新内容即新行，旧行按不可变历史保留。
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.judgment_search import JudgmentSearchCoverageSummary
from app.domain.publication import canonical_hash
from app.storage.codecs import (
    check_column_mirrors,
    decode_contract,
    encode_contract,
    to_utc_naive,
)
from app.storage.judgment_search_models import JudgmentSearchSummaryORM
from app.storage.repositories import (
    DuplicateRecordError,
    InvalidReferenceError,
    ScopeViolationError,
    _flush_guarded,
    _get_required,
)
from app.storage.models import ReviewEpisodeRecord, SubjectRecord
from app.storage.evidence_models import EvidenceSnapshotV2Record
from app.storage.ocr_models import EvidenceProcessingRevisionRecord

__all__ = ["JudgmentSearchSummaryRepository"]


class JudgmentSearchSummaryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_summary(
        self, summary: JudgmentSearchCoverageSummary, *, authority: FactAuthority,
        job_id: str, created_at,
    ) -> JudgmentSearchCoverageSummary:
        self._verify_scope(authority=authority)
        payload_json, payload_sha256 = encode_contract(summary)
        summary_id = "judgment-search-summary:" + canonical_hash({
            "authority": authority.model_dump(mode="json"),
            "summary": json.loads(payload_json),
        })[:32]
        row = self.session.get(JudgmentSearchSummaryORM, summary_id)
        if row is not None:
            if row.payload_sha256 != payload_sha256:
                raise DuplicateRecordError("判断检索摘要身份已存在但合同内容不同")
            return self.get_summary(summary_id)
        self.session.add(JudgmentSearchSummaryORM(
            summary_id=summary_id,
            subject_id=authority.subject_id,
            review_episode_id=authority.review_episode_id,
            evidence_snapshot_id=authority.evidence_snapshot_v2_id,
            evidence_processing_revision_id=authority.complete_processing_revision_id,
            rule_set_id=authority.rule_set_id,
            rule_set_revision=authority.rule_set_revision,
            scope_sha256=summary.scope_sha256,
            requirement_id=summary.requirement_id,
            status=summary.status.value,
            found_candidate_count=len(summary.found_candidates),
            job_id=job_id,
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            created_at=to_utc_naive(created_at),
        ))
        _flush_guarded(self.session)
        return summary

    def get_summary(self, summary_id: str) -> JudgmentSearchCoverageSummary:
        row = _get_required(self.session, JudgmentSearchSummaryORM, summary_id, "判断检索摘要")
        return self._decode(row)

    def latest_for_authority(
        self, authority: FactAuthority,
    ) -> dict[str, JudgmentSearchCoverageSummary]:
        """当前权威元组下每条要求的最新检索摘要（供缺口推导与界面读取）。

        同一要求多次检索（如受控重跑）时按 ``created_at``、``summary_id``
        确定性取最新；不同权威（新资料版本/新规则修订）的摘要不混入。
        """
        rows = self.session.scalars(
            select(JudgmentSearchSummaryORM)
            .where(
                JudgmentSearchSummaryORM.review_episode_id == authority.review_episode_id,
                JudgmentSearchSummaryORM.evidence_processing_revision_id
                == authority.complete_processing_revision_id,
                JudgmentSearchSummaryORM.rule_set_id == authority.rule_set_id,
                JudgmentSearchSummaryORM.rule_set_revision == authority.rule_set_revision,
            )
            .order_by(
                JudgmentSearchSummaryORM.requirement_id,
                JudgmentSearchSummaryORM.created_at,
                JudgmentSearchSummaryORM.summary_id,
            )
        ).all()
        latest: dict[str, JudgmentSearchCoverageSummary] = {}
        for row in rows:  # 排序后同 requirement 的最后一行即最新
            latest[row.requirement_id] = self._decode(row)
        return latest

    def _decode(self, row: JudgmentSearchSummaryORM) -> JudgmentSearchCoverageSummary:
        summary = decode_contract(
            JudgmentSearchCoverageSummary, row.payload_json, row.payload_sha256
        )
        check_column_mirrors(
            "JudgmentSearchCoverageSummary", row, json.loads(row.payload_json),
            {"scope_sha256": "scope_sha256", "requirement_id": "requirement_id",
             "status": "status"},
        )
        if row.found_candidate_count != len(summary.found_candidates):
            raise InvalidReferenceError("判断检索摘要候选计数与合同正文不一致")
        return summary

    def _verify_scope(self, *, authority: FactAuthority) -> None:
        subject = _get_required(self.session, SubjectRecord, authority.subject_id, "受试者")
        episode = _get_required(
            self.session, ReviewEpisodeRecord, authority.review_episode_id, "审核节点"
        )
        snapshot = _get_required(
            self.session, EvidenceSnapshotV2Record,
            authority.evidence_snapshot_v2_id, "证据快照",
        )
        revision = _get_required(
            self.session, EvidenceProcessingRevisionRecord,
            authority.complete_processing_revision_id, "证据处理修订",
        )
        if (
            episode.subject_id != subject.subject_id
            or snapshot.subject_id != subject.subject_id
            or revision.subject_id != subject.subject_id
        ):
            raise ScopeViolationError("判断检索摘要的受试者作用域不一致")
        if (
            snapshot.review_episode_id != episode.review_episode_id
            or revision.review_episode_id != episode.review_episode_id
            or revision.evidence_snapshot_id != snapshot.evidence_snapshot_id
        ):
            raise ScopeViolationError("判断检索摘要的审核节点作用域不一致")
