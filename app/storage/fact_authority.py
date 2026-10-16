"""Phase 5 权威元组与定位引用确定性校验（Slice 5.1，worker_03）。

设计书 §2.1/§2.3 与 PRD P5-R01/P5-AC01 的权威边界由本模块在持久化边界强制：

- 证据快照必须存在于 ``evidence_snapshots_v2`` 且作用域与权威元组一致；legacy
  ``evidence_snapshots`` 占位 id 一律拒绝（新写路径只有一个明确权威源）；
- 审核节点必须已激活且活动版本指针对成对存在（``active_evidence_snapshot_id`` 与
  ``active_evidence_processing_revision_id`` 同时非空），任一缺失即拒绝；
- 权威快照/完整处理修订必须等于审核节点当前活动指针，否则视为引用非活动版本；
- ``episode_revision`` 必须等于审核节点当前 ``revision``，否则视为陈旧修订；
- 权威元组其余成员（project/subject/rule_set/rule_set_revision/protocol_version）
  必须与审核节点作用域一致；
- 完整处理修订必须是可激活的 complete 修订（``revision_kind='complete'``、
  ``is_activatable=1``、``status='ready'``），base/未激活/未就绪修订一律拒绝；
- 定位引用只接受当前审核节点/当前活动快照成员资料的真实 locator：跨审核节点、
  跨快照、跨处理修订的 locator id 一律拒绝。

本模块只做确定性校验，不写任何持久状态；发布实体仓储（``fact_repositories``）在
写入前调用 ``validate`` 与 ``validate_locators``。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision
from app.storage.codecs import PersistedContractInvalid
from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
from app.storage.evidence_locator_models import ProcessingRevisionLocatorRecord
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    EvidenceLocatorRepository,
)
from app.storage.evidence_models import (
    EvidenceSnapshotMemberRecord,
    EvidenceSnapshotV2Record,
    SourceDocumentVersionV2Record,
)
from app.storage.evidence_repositories import (
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)
from app.storage.models import ReviewEpisodeRecord
from app.storage.ocr_models import EvidenceProcessingRevisionRecord
from app.storage.repositories import EpisodeRepository, RepositoryError

__all__ = [
    "FactAuthorityError",
    "FactAuthorityValidator",
    "FactLocatorReferenceError",
]


class FactAuthorityError(RepositoryError):
    """权威元组校验失败：legacy/缺失快照、未激活/未配对指针、陈旧修订、非 complete
    修订或作用域不一致，拒绝发布。"""


class FactLocatorReferenceError(RepositoryError):
    """定位引用不在当前审核节点/活动快照/处理修订闭包内（跨节点/跨快照/跨修订）。"""


def clinical_source_scope_is_compatible(previous, authority, old_rules, current_rules, old_protocol, current_protocol):
    """A rule-only revision can reuse source readings, not its former conclusions."""
    identity_fields = {"episode_revision", "protocol_version_id", "rule_set_revision"}
    old_variables = {item.variable_id: item.model_dump(mode="json") for item in old_rules.variable_definitions or ()}
    current_variables = {item.variable_id: item.model_dump(mode="json") for item in current_rules.variable_definitions or ()}
    return (previous.model_dump(exclude=identity_fields) == authority.model_dump(exclude=identity_fields)
        and old_protocol.sha256 == current_protocol.sha256
        and old_rules.study_phase == current_rules.study_phase
        and all(current_variables.get(key) == value for key, value in old_variables.items()))


class FactAuthorityValidator:
    """把不可变权威元组与数据库当前状态确定性核对。

    校验失败抛 :class:`FactAuthorityError` / :class:`FactLocatorReferenceError`，
    不写入任何记录；调用方负责在事务内先校验后发布。
    """

    def __init__(self, session: Session, artifact_store=None) -> None:
        self.session = session
        self.artifact_store = artifact_store
        self._retained_documents = {}
        self._retained_pages = {}

    def _require_artifact_store(self):
        """native_text 定位闭包核验需要内容寻址工件库；惰性构建避免循环导入。"""
        if self.artifact_store is None:
            from app.evidence.artifacts import ArtifactStore
            from app.services.evidence_app_bootstrap import resolve_data_paths

            self.artifact_store = ArtifactStore(resolve_data_paths())
        return self.artifact_store

    # ------------------------------------------------------------------ 权威元组

    def validate(self, authority: FactAuthority) -> None:
        """校验权威元组对应当前活动证据链；任一不满足即拒绝。"""
        self.validate_and_get_revision(authority)

    def validate_and_get_revision(
        self, authority: FactAuthority
    ) -> CompleteEvidenceProcessingRevision:
        """完整核验并返回本次读取的修订；不缓存，也不接受外部已验证标记。"""
        self._validate_snapshot(authority)
        self._validate_episode(authority)
        return self._validate_complete_revision(authority)

    def validate_frozen_source(self, authority: FactAuthority) -> CompleteEvidenceProcessingRevision:
        """Verify retained source scope without requiring today's active pointers.

        This proves document/processing membership, not current clinical facts or
        rule applicability; callers separately establish subject/episode ownership.
        """
        self._validate_snapshot(authority)
        return self._validate_complete_revision(authority)

    def rule_revision_source_is_reusable(self, previous: FactAuthority, current: FactAuthority) -> bool:
        """Verify retained material for 0.2.0; current writes still require validate()."""
        if previous == current:
            return True
        identity_fields = {"episode_revision", "protocol_version_id", "rule_set_revision"}
        if previous.model_dump(exclude=identity_fields) != current.model_dump(exclude=identity_fields):
            return False
        from app.storage.repositories import AppendRepository, PROTOCOL_DOC_CONFIG, get_rule_set
        old_rules = get_rule_set(self.session, previous.rule_set_id, previous.rule_set_revision)
        current_rules = get_rule_set(self.session, current.rule_set_id, current.rule_set_revision)
        if not old_rules.variable_definitions or not current_rules.variable_definitions:
            return False
        protocols = AppendRepository(self.session, PROTOCOL_DOC_CONFIG)
        if not clinical_source_scope_is_compatible(previous, current, old_rules, current_rules,
                protocols.get(previous.protocol_version_id), protocols.get(current.protocol_version_id)):
            return False
        self.validate_frozen_source(previous)
        self.validate_frozen_source(current)
        return True

    def retained_source_documents(self, previous: FactAuthority, current: FactAuthority) -> frozenset[str]:
        """Prove unchanged document inputs along the actual incremental snapshot chain.

        This is source reuse, not a new fact, model read or rule approval. Replaced
        files, changed text/locators/classification and unrelated snapshots do not
        qualify. Corrupt retained records remain errors, not cache misses.
        """
        cache_key = (previous.model_dump_json(), current.model_dump_json())
        if cache_key in self._retained_documents:
            return self._retained_documents[cache_key][0]
        if any(getattr(previous, key) != getattr(current, key) for key in (
                "project_id", "subject_id", "review_episode_id", "rule_set_id")):
            return frozenset()
        from app.storage.repositories import AppendRepository, PROTOCOL_DOC_CONFIG, get_rule_set
        old_rules = get_rule_set(self.session, previous.rule_set_id, previous.rule_set_revision)
        new_rules = get_rule_set(self.session, current.rule_set_id, current.rule_set_revision)
        protocols = AppendRepository(self.session, PROTOCOL_DOC_CONFIG)
        old_protocol, new_protocol = (protocols.get(key) for key in (previous.protocol_version_id, current.protocol_version_id))
        variables = {row.variable_id: row.model_dump(mode="json") for row in new_rules.variable_definitions or ()}
        if (not old_rules.variable_definitions or old_protocol.sha256 != new_protocol.sha256
                or old_rules.study_phase != new_rules.study_phase
                or any(variables.get(row.variable_id) != row.model_dump(mode="json") for row in old_rules.variable_definitions)):
            return frozenset()
        chain = set()
        key = current.evidence_snapshot_v2_id
        while key is not None:
            if key in chain:
                raise FactAuthorityError("资料版本链重复，不能复用旧读取")
            chain.add(key)
            snapshot = EvidenceSnapshotRepository(self.session).get(key)
            if (snapshot.project_id, snapshot.subject_id, snapshot.review_episode_id) != (
                    current.project_id, current.subject_id, current.review_episode_id):
                raise FactAuthorityError("资料版本链属于其他个例或节点")
            key = snapshot.prior_snapshot_id
        if previous.evidence_snapshot_v2_id not in chain:
            return frozenset()
        old_revision, new_revision = (self.validate_frozen_source(row) for row in (previous, current))
        if (old_revision.source_qualification_mode != new_revision.source_qualification_mode
                or old_revision.referenced_document_revision_ids != new_revision.referenced_document_revision_ids
                or old_revision.resolution_revision_ids != new_revision.resolution_revision_ids):
            return frozenset()
        from app.services.fact_normalization_source_adapter import build_doc_version_to_logical_map, build_effective_text_map
        from app.storage.evidence_repositories import SourceDocumentMetadataRevisionRepository
        old_docs, old_meta = build_doc_version_to_logical_map(self.session, old_revision)
        new_docs, new_meta = build_doc_version_to_logical_map(self.session, new_revision)
        old_pages = build_effective_text_map(self.session, old_revision, doc_version_to_logical=old_docs)
        new_pages = build_effective_text_map(self.session, new_revision, doc_version_to_logical=new_docs)
        from app.storage.evidence_locator_repositories import OCRRiskScanRepository, OCRRiskReviewRepository
        def risk_scopes(revision):
            scans = OCRRiskScanRepository(self.session).get_many(revision.risk_scan_ids)
            reviews = OCRRiskReviewRepository(self.session).get_many(revision.risk_review_ids)
            result = {}
            for page in revision.manifest:
                selected = [scan for scan in scans if scan.ocr_page_id == page.ocr_page_id]
                flags = {flag.risk_id for scan in selected for flag in scan.flags}
                result[(page.source_document_version_id, page.page_number)] = (sorted(scan.scan_id for scan in selected),
                    sorted(review.review_id for review in reviews if review.risk_flag_id in flags),
                    sorted(flags & set(revision.unresolved_blocking_risk_ids)))
            return result
        old_risks, new_risks = risk_scopes(old_revision), risk_scopes(new_revision)
        metadata = SourceDocumentMetadataRevisionRepository(self.session)
        selected, retained_pages = set(), set()
        for document in old_docs.keys() & new_docs.keys():
            logical = old_docs[document]
            if new_docs[document] != logical or logical not in old_meta or logical not in new_meta:
                continue
            old = metadata.get(old_meta[logical])
            new = metadata.get(new_meta[logical])
            if any(getattr(old, key) != getattr(new, key) for key in (
                    "document_type", "source_party", "document_category", "source_category")):
                continue
            prior = {key: value for key, value in old_pages.items() if key[0] == document}
            present = {key: value for key, value in new_pages.items() if key[0] == document}
            matching = {key for key in prior.keys() & present.keys()
                if prior[key] == present[key] and old_risks[key] == new_risks[key]}
            retained_pages.update(matching)
            if prior and prior.keys() == present.keys() == matching:
                selected.add(document)
        result = frozenset(selected)
        self._retained_documents[cache_key] = result, frozenset(new_revision.locator_ids)
        self._retained_pages[cache_key] = frozenset(retained_pages)
        return result

    def retained_source_pages(self, previous: FactAuthority, current: FactAuthority) -> frozenset[tuple[str, int]]:
        """Page reuse preserves the same ownership, metadata and risk checks as document reuse."""
        self.retained_source_documents(previous, current)
        return self._retained_pages.get((previous.model_dump_json(), current.model_dump_json()), frozenset())

    def retained_fact_source_is_reusable(self, fact, current: FactAuthority) -> bool:
        if self.rule_revision_source_is_reusable(fact.authority, current):
            return True
        pages = self.retained_source_pages(fact.authority, current)
        if not pages or not fact.locator_ids:
            return False
        from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
        locators = EvidenceLocatorRepository(self.session).get_many(fact.locator_ids)
        if any((locator.source_document_version_id, locator.page_number) not in pages for locator in locators):
            return False
        documents = self.retained_source_documents(fact.authority, current)
        _, current_locators = self._retained_documents[(fact.authority.model_dump_json(), current.model_dump_json())]
        if not set(fact.locator_ids) <= current_locators:
            return False
        if all(locator.source_document_version_id in documents for locator in locators):
            return True
        from app.domain.contracts.facts import ClinicalConflictGroupV2
        if isinstance(fact, ClinicalConflictGroupV2):
            from app.storage.fact_repositories import ClinicalFactV2Repository, ClinicalEventV2Repository, MedicationExposureV2Repository
            repository, members = {
                "fact": (ClinicalFactV2Repository, fact.fact_ids),
                "event": (ClinicalEventV2Repository, fact.event_ids),
                "exposure": (MedicationExposureV2Repository, fact.exposure_ids),
            }[fact.member_kind]
            repo = repository(self.session)
            return all(self.retained_fact_source_is_reusable(repo.get(identity), current) for identity in members)
        if not fact.source_candidate_ids:
            return False
        # A multi-page reading may depend on a changed sibling even when this
        # fact's displayed excerpt is on an unchanged page.
        from app.storage.fact_repositories import FactNormalizationCandidateRepository, FactNormalizationCallRepository
        candidates = FactNormalizationCandidateRepository(self.session)
        calls = FactNormalizationCallRepository(self.session)
        for candidate_id in fact.source_candidate_ids:
            candidate = candidates.get(candidate_id)
            call = calls.get(candidate.call_id)
            call_documents = {locator.source_document_version_id for locator in locators}
            if len(call_documents) != 1 or any((next(iter(call_documents)), page) not in pages for page in call.page_numbers):
                return False
        return True

    def _validate_snapshot(self, authority: FactAuthority) -> None:
        snapshot = self.session.get(
            EvidenceSnapshotV2Record, authority.evidence_snapshot_v2_id
        )
        if snapshot is None:
            raise FactAuthorityError(
                f"证据快照 {authority.evidence_snapshot_v2_id} 不存在于 "
                "evidence_snapshots_v2；legacy evidence_snapshots 占位 id 一律拒绝"
            )
        decoded = EvidenceSnapshotRepository._decode_record(snapshot)
        if (
            decoded.project_id,
            decoded.subject_id,
            decoded.review_episode_id,
        ) != (
            authority.project_id,
            authority.subject_id,
            authority.review_episode_id,
        ):
            raise FactAuthorityError(
                f"权威快照 {authority.evidence_snapshot_v2_id} 作用域与权威元组不一致"
            )

    def _validate_episode(self, authority: FactAuthority) -> None:
        episode = self.session.get(
            ReviewEpisodeRecord, authority.review_episode_id
        )
        if episode is None:
            raise FactAuthorityError(
                f"审核节点 {authority.review_episode_id} 不存在"
            )
        decoded = EpisodeRepository._decode_record(episode)
        # 活动指针对必须成对：任一为空即视为未激活/未配对。
        if (
            decoded.active_evidence_snapshot_id is None
            or decoded.active_evidence_processing_revision_id is None
        ):
            raise FactAuthorityError(
                f"审核节点 {authority.review_episode_id} 未激活或活动版本指针未配对，"
                "拒绝发布事实"
            )
        if decoded.active_evidence_snapshot_id != authority.evidence_snapshot_v2_id:
            raise FactAuthorityError(
                f"权威快照 {authority.evidence_snapshot_v2_id} 不是审核节点当前活动快照 "
                f"({decoded.active_evidence_snapshot_id})，拒绝发布"
            )
        if (
            decoded.active_evidence_processing_revision_id
            != authority.complete_processing_revision_id
        ):
            raise FactAuthorityError(
                f"完整处理修订 {authority.complete_processing_revision_id} 不是审核节点"
                f"当前活动处理修订 ({decoded.active_evidence_processing_revision_id})，"
                "拒绝发布"
            )
        if decoded.revision != authority.episode_revision:
            raise FactAuthorityError(
                f"陈旧审核节点修订：权威元组 episode_revision="
                f"{authority.episode_revision}，当前审核节点 revision="
                f"{decoded.revision}，拒绝发布"
            )
        if (
            decoded.project_id,
            decoded.subject_id,
            decoded.rule_set_id,
            decoded.rule_set_revision,
            decoded.protocol_version_id,
        ) != (
            authority.project_id,
            authority.subject_id,
            authority.rule_set_id,
            authority.rule_set_revision,
            authority.protocol_version_id,
        ):
            raise FactAuthorityError(
                f"权威元组与审核节点 {authority.review_episode_id} 作用域不一致，拒绝发布"
            )

    def _validate_complete_revision(
        self, authority: FactAuthority
    ) -> CompleteEvidenceProcessingRevision:
        revision_row = self.session.get(
            EvidenceProcessingRevisionRecord, authority.complete_processing_revision_id
        )
        if revision_row is None:
            raise FactAuthorityError(
                f"完整处理修订 {authority.complete_processing_revision_id} 不存在"
            )
        try:
            decoded = CompleteEvidenceProcessingRevisionRepository(
                self.session, self._require_artifact_store(),
            ).get(authority.complete_processing_revision_id)
        except (RepositoryError, PersistedContractInvalid) as exc:
            raise FactAuthorityError(
                f"完整处理修订 {authority.complete_processing_revision_id} "
                "的页、定位、风险或资料元数据闭包不完整"
            ) from exc
        if not decoded.is_activatable or decoded.status.value != "ready":
            raise FactAuthorityError(
                f"处理修订 {authority.complete_processing_revision_id} 不是可激活的"
                "complete 修订（base/未激活/未就绪一律拒绝）"
            )
        if decoded.evidence_snapshot_id != authority.evidence_snapshot_v2_id:
            raise FactAuthorityError(
                f"完整处理修订 {authority.complete_processing_revision_id} 与权威快照 "
                f"{authority.evidence_snapshot_v2_id} 不一致"
            )
        if decoded.review_episode_id != authority.review_episode_id:
            raise FactAuthorityError(
                f"完整处理修订 {authority.complete_processing_revision_id} 与审核节点 "
                f"{authority.review_episode_id} 不一致"
            )
        return decoded

    # ------------------------------------------------------------------ 定位引用

    def validate_locators(
        self, authority: FactAuthority, locator_ids: list[str]
    ) -> None:
        """逐个校验定位引用都在指定审核节点/冻结快照/处理修订闭包内。

        同一批定位共享一个视觉核验上下文：同一事务内重复的整修订核验只
        执行一次；上下文随本次调用结束而丢弃，不跨事务复用。
        """
        from app.storage.page_review_visual_locator_validation import (
            VisualLocatorBatchContext,
        )

        batch = VisualLocatorBatchContext(self.session)
        for locator_id in sorted(set(locator_ids)):
            self._validate_locator(authority, locator_id, batch)

    def _validate_locator(self, authority: FactAuthority, locator_id: str, batch=None) -> None:
        locator = self.session.get(EvidenceLocatorArtifactRecord, locator_id)
        if locator is None:
            raise FactLocatorReferenceError(f"定位 {locator_id} 不存在")
        decoded_locator = EvidenceLocatorRepository._decode(locator)
        if decoded_locator.page_review_visual is not None:
            from app.storage.page_review_visual_locator_validation import verify_visual_locator_authority
            verify_visual_locator_authority(self.session, decoded_locator, authority, batch=batch)
            return
        document = self.session.get(
            SourceDocumentVersionV2Record,
            decoded_locator.source_document_version_id,
        )
        if document is None:
            raise FactLocatorReferenceError(
                f"定位 {locator_id} 引用的资料版本 "
                f"{decoded_locator.source_document_version_id} 不存在"
            )
        decoded_document = SourceDocumentRepository._decode(document)
        if decoded_document.review_episode_id != authority.review_episode_id:
            raise FactLocatorReferenceError(
                f"定位 {locator_id} 属于其他审核节点 "
                f"({decoded_document.review_episode_id})，跨审核节点定位引用拒绝"
            )
        member_rows = self.session.execute(
            select(EvidenceSnapshotMemberRecord).where(
                EvidenceSnapshotMemberRecord.snapshot_id == authority.evidence_snapshot_v2_id
            )
        ).scalars().all()
        decoded_members = [
            EvidenceSnapshotRepository._decode_member_record(
                row,
                expected_snapshot_id=authority.evidence_snapshot_v2_id,
            )
            for row in member_rows
        ]
        matching_members = [
            member
            for member in decoded_members
            if member.snapshot_id == authority.evidence_snapshot_v2_id
            and member.source_document_version_id
            == decoded_document.source_document_version_id
        ]
        if not matching_members:
            raise FactLocatorReferenceError(
                f"定位 {locator_id} 的资料不属于指定快照成员（跨快照/跨处理修订"
                "定位引用拒绝）"
            )
        revision_member = self.session.execute(
            select(ProcessingRevisionLocatorRecord).where(
                ProcessingRevisionLocatorRecord.revision_id
                == authority.complete_processing_revision_id,
                ProcessingRevisionLocatorRecord.locator_id == locator_id,
            )
        ).scalar_one_or_none()
        if revision_member is None:
            raise FactLocatorReferenceError(
                f"定位 {locator_id} 未收录于指定完整处理修订 "
                f"{authority.complete_processing_revision_id} 的定位清单，拒绝引用"
            )
        if (
            decoded_locator.processing_revision_id is not None
            and decoded_locator.processing_revision_id
            != authority.complete_processing_revision_id
        ):
            raise FactLocatorReferenceError(
                f"定位 {locator_id} 绑定其他处理修订 "
                f"({decoded_locator.processing_revision_id})，拒绝引用"
            )
