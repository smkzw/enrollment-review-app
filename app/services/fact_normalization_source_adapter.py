"""事实规范化证据源适配器（数据库绑定，确定性，无模型）。

把活动 CompleteEvidenceProcessingRevision 与项目有效文本确定性适配为
逻辑文档调用所需的 PageInput 与逻辑文档映射，供纯确定性规划器消费。

职责边界：
- 从不可变有效文本层（raw OCR + 完整修订所选校对投影）读取；显式视觉来源
  路径允许无 OCR 的原件页，正文保持为空，事实仍由绑定的双读与视觉定位提供。
  绝不借用筛选日/上传日/操作日填补 PartialDateRange；
- 显式闭合：每个 manifest 页必须有对应页产物；文字路径核对 OCR 和有效文本，
  视觉路径核对原件图像及双读来源，缺页一律报错；
- 无跨审核节点借用：仅处理传入修订所在审核节点的资料版本与页产物，
  映射不一致一律拒绝；
- 稳定哈希：effective_text_sha256 来自 EffectiveTextProjection 的确定性 sha256。

本模块可被 Job 编排层复用，但不创建 Job/不发布事实/不写 Profile。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision
from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.evidence_normalizer import (
    EvidenceNormalizerContextInput,
    EvidenceNormalizerInput,
    EvidenceNormalizerLocatorInput,
    EvidenceNormalizerPageInput,
    EvidenceNormalizerPageReviewInput,
    evidence_normalizer_input_scope_hash,
    page_review_input_scope_hash,
)
from app.domain.contracts.enums import LocatorPrecision, LocatorSourceLayer
from app.domain.contracts.page_review import PageDisposition
from app.domain.contracts.rules import EvidenceRequirement
from app.domain.contracts.selective_vision_observation import (
    SelectiveVisionObservationAttachment,
    SelectiveVisionObservationStatus,
    visual_observation_scope_sha256,
)
from app.domain.policies import STAGE_RANK
from app.domain.planning.fact_normalization_planning import (
    FactNormalizationPlan,
    PageInput,
    plan_fact_normalization_calls,
)
from app.evidence.effective_text import EffectiveTextProjection, project_effective_text
from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
from app.storage.selective_vision_observation_repository import (
    SelectiveVisionObservationRepository,
)
from app.storage.page_review_repository import PageReviewRepository

__all__ = [
    "FactPlanningSourceError",
    "FactSourceAdapterResult",
    "build_effective_text_map",
    "build_doc_version_to_logical_map",
    "build_fact_normalization_plan",
    "build_evidence_normalizer_input",
    "build_page_review_normalizer_input",
    "collect_visual_observation_attachments",
    "select_call_visual_observation_attachments",
]


class FactPlanningSourceError(RuntimeError):
    """源适配器领域错误（缺页、跨节点、映射漂移、校对不可投影等）。"""


def _compact_locator_inputs(
    locators: list[EvidenceNormalizerLocatorInput],
) -> list[EvidenceNormalizerLocatorInput]:
    """R13修复：不做文本包含推断去重，保留全部定位输入。

    同页同源的相同文本可能出现在不同位置（如两列表各含"阴性"）。
    旧逻辑按文本包含关系去重会丢失不同出现位置。在引入几何信息
    （bbox/偏移量）之前，不做任何基于文本的去重。
    """
    return list(locators)


@dataclass(frozen=True)
class FactSourceAdapterResult:
    """一次源适配的中间结果（供规划器或调用方检查）。"""

    revision: CompleteEvidenceProcessingRevision
    page_inputs: dict[tuple[str, int], PageInput]
    doc_version_to_logical: dict[str, str]
    logical_to_metadata_revision: dict[str, str]
    context_by_logical_document: dict[str, EvidenceNormalizerContextInput]
    related_requirements: tuple[EvidenceRequirement, ...]


def _load_normalizer_context(
    session: Session,
    *,
    authority: FactAuthority,
    revision: CompleteEvidenceProcessingRevision,
    doc_version_to_logical: dict[str, str],
    logical_to_metadata_revision: dict[str, str],
) -> tuple[dict[str, EvidenceNormalizerContextInput], tuple[EvidenceRequirement, ...]]:
    """读取当前审核节点、资料元数据与本节点已到期的资料要求。"""
    from app.storage.evidence_repositories import (
        SourceDocumentMetadataRevisionRepository,
    )
    from app.storage.models import EvidenceRequirementRecord
    from app.storage.repositories import EpisodeRepository, get_evidence_requirement

    episode = EpisodeRepository(session).get(authority.review_episode_id)
    if (
        episode.revision != authority.episode_revision
        or episode.project_id != authority.project_id
        or episode.subject_id != authority.subject_id
        or episode.protocol_version_id != authority.protocol_version_id
        or episode.rule_set_id != authority.rule_set_id
        or episode.rule_set_revision != authority.rule_set_revision
        or episode.active_evidence_snapshot_id != authority.evidence_snapshot_v2_id
        or episode.active_evidence_processing_revision_id
        != authority.complete_processing_revision_id
    ):
        raise FactPlanningSourceError("审核节点与规范化权威元组不一致，拒绝构建模型输入")

    contexts: dict[str, EvidenceNormalizerContextInput] = {}
    metadata_repo = SourceDocumentMetadataRevisionRepository(session)
    version_by_logical = {logical: version for version, logical in doc_version_to_logical.items()}
    if len(version_by_logical) != len(doc_version_to_logical):
        raise FactPlanningSourceError("同一逻辑资料在活动修订中出现多个资料版本，无法冻结上下文")
    for logical_document_id, source_document_version_id in sorted(version_by_logical.items()):
        metadata_revision_id = logical_to_metadata_revision.get(logical_document_id)
        if metadata_revision_id is None:
            raise FactPlanningSourceError(
                f"逻辑文档 {logical_document_id} 缺少已确认的资料类型和来源方元数据"
            )
        metadata = metadata_repo.get(metadata_revision_id)
        if metadata.source_document_version_id != source_document_version_id:
            raise FactPlanningSourceError(
                f"逻辑文档 {logical_document_id} 的元数据修订与活动资料版本不一致"
            )
        # R14修复：有据的自动建议可直接采用，不构成隐藏人工门禁。
        # 仅当document_type为完全未知的占位值时才阻断——
        # "其他资料（待确认）"表示系统无法识别文件类型。
        if metadata.is_auto_suggestion and "待确认" in (metadata.document_type or ""):
            raise FactPlanningSourceError(
                f"逻辑文档 {logical_document_id} 的资料类型无法自动识别（仍为待确认），"
                "需人工确认后才能进入证据规范化"
            )
        contexts[logical_document_id] = EvidenceNormalizerContextInput(
            source_document_version_id=source_document_version_id,
            metadata_revision_id=metadata.metadata_revision_id,
            document_type=metadata.document_type,
            source_party=metadata.source_party,
            document_record_time=None,
            current_review_stage=episode.stage,
            workflow_stage_id=episode.workflow_stage_id,
        )

    rows = session.execute(
        select(EvidenceRequirementRecord).where(
            EvidenceRequirementRecord.rule_set_id == authority.rule_set_id,
            EvidenceRequirementRecord.rule_set_revision == authority.rule_set_revision,
        )
    ).scalars().all()
    requirements = [
        get_evidence_requirement(
            session,
            authority.rule_set_id,
            authority.rule_set_revision,
            row.requirement_id,
        )
        for row in rows
    ]
    related = tuple(
        sorted(
            (
                item
                for item in requirements
                if STAGE_RANK[item.due_stage] <= STAGE_RANK[episode.stage]
            ),
            key=lambda item: item.requirement_id,
        )
    )
    return contexts, related


def build_doc_version_to_logical_map(
    session: Session,
    revision: CompleteEvidenceProcessingRevision,
) -> tuple[dict[str, str], dict[str, str]]:
    """从 DB 读取 manifest 关联的 source_document_version -> logical_document_id。

    返回 (doc_version_to_logical, logical_to_metadata_revision) 二元组。
    任一资料版本缺失或无逻辑文档归属一律报错（拒绝隐式归属）。
    """
    from app.storage.evidence_models import SourceDocumentVersionV2Record

    doc_version_to_logical: dict[str, str] = {}
    logical_to_metadata: dict[str, str] = {}

    # 收集 manifest 涉及的资料版本
    version_ids = {entry.source_document_version_id for entry in revision.manifest}
    for vid in version_ids:
        record = session.get(SourceDocumentVersionV2Record, vid)
        if record is None:
            raise FactPlanningSourceError(f"资料版本 {vid} 不存在，无法确定性规划")
        if not record.logical_document_id:
            raise FactPlanningSourceError(f"资料版本 {vid} 缺少 logical_document_id")
        # 作用域校验：与修订一致，无跨 episode 借用
        if (
            record.project_id != revision.project_id
            or record.subject_id != revision.subject_id
            or record.review_episode_id != revision.review_episode_id
        ):
            raise FactPlanningSourceError(
                f"资料版本 {vid} 与完整修订 {revision.evidence_processing_revision_id} "
                f"作用域不一致（project/subject/episode 漂移），拒绝跨节点规划"
            )
        doc_version_to_logical[vid] = record.logical_document_id

    # 逻辑文档 -> 元数据修订（从 revision.metadata_revision_ids 解析）
    if revision.metadata_revision_ids:
        from app.storage.evidence_models import SourceDocumentMetadataRevisionRecord

        for mid in revision.metadata_revision_ids:
            meta = session.get(SourceDocumentMetadataRevisionRecord, mid)
            if meta is None:
                raise FactPlanningSourceError(f"元数据修订 {mid} 不存在")
            logical = doc_version_to_logical.get(meta.source_document_version_id)
            if logical is None:
                # 元数据修订所属资料版本不在 manifest 中，视为不一致
                raise FactPlanningSourceError(
                    f"元数据修订 {mid} 所属资料 {meta.source_document_version_id} "
                    "不在完整修订页清单中，拒绝"
                )
            previous = logical_to_metadata.get(logical)
            if previous is not None and previous != mid:
                raise FactPlanningSourceError(
                    f"逻辑文档 {logical} 同时关联元数据修订 {previous} 与 {mid}，无法确定来源强度"
                )
            logical_to_metadata[logical] = mid

    return doc_version_to_logical, logical_to_metadata


def build_effective_text_map(
    session: Session,
    revision: CompleteEvidenceProcessingRevision,
    *,
    doc_version_to_logical: dict[str, str] | None = None,
    allow_image_only: bool = False,
) -> dict[tuple[str, int], PageInput]:
    """为修订每页确定性投影有效文本并构建 PageInput 映射。

    - 对每页读取不可变 OCRPage.raw_text 与修订所选校正，调用 project_effective_text；
    - 使用 EffectiveTextProjection.effective_text_sha256 作为稳定输入哈希；
    - 绝不借用筛选/上传/操作日期补全缺失日期（本层不处理日期）；
    - 缺页/校对重叠/哈希不一致一律抛错。

    返回 key=(source_document_version_id, page_number) -> PageInput
    """
    from app.storage.evidence_locator_repositories import CorrectionRepository
    from app.storage.ocr_repositories import OcrPageRepository, PageArtifactRepository

    if doc_version_to_logical is None:
        doc_version_to_logical, _ = build_doc_version_to_logical_map(session, revision)

    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository

    locators_by_page: dict[tuple[str, int], list] = {}
    manifest_by_page = {
        (entry.source_document_version_id, entry.page_number): entry
        for entry in revision.manifest
    }
    locator_repo = EvidenceLocatorRepository(session)
    for locator_id in revision.locator_ids:
        try:
            locator = locator_repo.get(locator_id)
        except Exception as exc:
            raise FactPlanningSourceError(
                f"定位 {locator_id} 不存在或不可还原：{exc}"
            ) from exc
        key = (locator.source_document_version_id, locator.page_number)
        entry = manifest_by_page.get(key)
        if entry is None or locator.page_artifact_id != entry.page_artifact_id:
            raise FactPlanningSourceError(
                f"定位 {locator_id} 不属于完整处理修订的对应资料页，拒绝跨页或跨修订引用"
            )
        locators_by_page.setdefault(key, []).append(locator)

    # 收集修订所选校正
    correction_by_ocr: dict[str, list] = {}
    if revision.correction_ids:
        repo = CorrectionRepository(session)
        for cid in revision.correction_ids:
            try:
                corr = repo.get(cid)
            except Exception as exc:
                raise FactPlanningSourceError(f"校正 {cid} 不存在或不可还原：{exc}") from exc
            correction_by_ocr.setdefault(corr.ocr_page_id, []).append(corr)

    result: dict[tuple[str, int], PageInput] = {}
    for entry in revision.manifest:
        logical = doc_version_to_logical.get(entry.source_document_version_id)
        if logical is None:
            raise FactPlanningSourceError(
                f"资料版本 {entry.source_document_version_id} 缺少逻辑文档映射"
            )
        if entry.ocr_page_id is None:
            if not allow_image_only:
                raise FactPlanningSourceError("本页没有文字识别结果，请通过原件双读整理资料")
            artifact = PageArtifactRepository(session).get(entry.page_artifact_id)
            if (not artifact.page_image_sha256 or artifact.page_number != entry.page_number):
                raise FactPlanningSourceError("原件页图像缺失或页码不一致，不能整理资料")
            raw_text = ""
        else:
            ocr = OcrPageRepository(session).get(entry.ocr_page_id)
            if ocr.page_artifact_id != entry.page_artifact_id or ocr.page_number != entry.page_number:
                raise FactPlanningSourceError(
                    f"OCR 页 {entry.ocr_page_id} 与清单条目 {entry.entry_id} 归属不一致"
                )
            raw_text = ocr.raw_text
        corrections = correction_by_ocr.get(entry.ocr_page_id, [])
        try:
            projection: EffectiveTextProjection = project_effective_text(
                raw_text, corrections
            )
        except Exception as exc:
            raise FactPlanningSourceError(
                f"页 {entry.source_document_version_id}:{entry.page_number} "
                f"有效文本投影失败：{exc}"
            ) from exc

        key = (entry.source_document_version_id, entry.page_number)
        locator_inputs: list[EvidenceNormalizerLocatorInput] = []
        for locator in sorted(
            locators_by_page.get(key, []), key=lambda item: item.locator_id
        ):
            localized_text = locator.excerpt
            if localized_text is None and locator.precision != LocatorPrecision.PAGE_ONLY:
                if locator.source_layer == LocatorSourceLayer.EFFECTIVE_TEXT:
                    source_text = projection.effective_text
                elif locator.source_layer == LocatorSourceLayer.RAW_OCR:
                    source_text = raw_text
                else:
                    source_text = ""
                if locator.text_start is not None and locator.text_end is not None:
                    localized_text = source_text[locator.text_start : locator.text_end]
            try:
                locator_inputs.append(
                    EvidenceNormalizerLocatorInput(
                        locator_id=locator.locator_id,
                        page_number=locator.page_number,
                        source_layer=locator.source_layer,
                        precision=locator.precision,
                        source_text_sha256=locator.source_text_sha256,
                        localized_text=localized_text,
                    )
                )
            except ValueError as exc:
                raise FactPlanningSourceError(
                    f"定位 {locator.locator_id} 没有可供模型选择的真实原文范围：{exc}"
                ) from exc
        locator_inputs = _compact_locator_inputs(locator_inputs)
        result[key] = PageInput(
            source_document_version_id=entry.source_document_version_id,
            page_number=entry.page_number,
            page_artifact_id=entry.page_artifact_id,
            ocr_page_id=entry.ocr_page_id,
            effective_text_sha256=projection.effective_text_sha256,
            logical_document_id=logical,
            effective_text=projection.effective_text,
            locator_ids=tuple(item.locator_id for item in locator_inputs),
            locator_inputs=tuple(locator_inputs),
        )

    # 确定性：按 (logical, page_number) 排序后返回的字典插入顺序稳定（Python 3.7+）
    return dict(sorted(result.items(), key=lambda kv: (kv[1].logical_document_id, kv[1].page_number)))


def build_fact_normalization_plan(
    session: Session,
    *,
    authority: FactAuthority,
    revision: CompleteEvidenceProcessingRevision | None = None,
    revision_id: str | None = None,
    max_pages_per_call: int = 20,
    contract_version: str = "phase5/facts/v1",
    allow_image_only: bool = False,
) -> tuple[FactNormalizationPlan, FactSourceAdapterResult]:
    """一站式适配 + 确定性规划（DB 读取 + 纯规划）。

    调用方需提供已冻结的 FactAuthority 与活动 CompleteEvidenceProcessingRevision
    （或仅提供 revision_id 时从 DB 加载并校验）。返回 (plan, adapter_result)。

    本函数不创建 Job/Call 持久化记录，仅产生确定性规划与哈希，供编排层落库。
    """
    if revision is None:
        if revision_id is None:
            raise ValueError("build_fact_normalization_plan 需提供 revision 或 revision_id")
        revision = CompleteEvidenceProcessingRevisionRepository(session).get(revision_id)

    # 权威元组与修订一致性（无跨 episode）
    if authority.complete_processing_revision_id != revision.evidence_processing_revision_id:
        raise FactPlanningSourceError(
            "FactAuthority 的 complete_processing_revision_id 与传入修订不一致"
        )
    if (
        authority.project_id != revision.project_id
        or authority.subject_id != revision.subject_id
        or authority.review_episode_id != revision.review_episode_id
        or authority.evidence_snapshot_v2_id != revision.evidence_snapshot_id
    ):
        raise FactPlanningSourceError("FactAuthority 与完整修订作用域不一致，拒绝跨节点规划")

    doc_version_to_logical, logical_to_meta = build_doc_version_to_logical_map(
        session, revision
    )
    contexts, related_requirements = _load_normalizer_context(
        session,
        authority=authority,
        revision=revision,
        doc_version_to_logical=doc_version_to_logical,
        logical_to_metadata_revision=logical_to_meta,
    )
    page_inputs = build_effective_text_map(
        session, revision, doc_version_to_logical=doc_version_to_logical,
        allow_image_only=allow_image_only,
    )
    adapter_result = FactSourceAdapterResult(
        revision=revision,
        page_inputs=page_inputs,
        doc_version_to_logical=doc_version_to_logical,
        logical_to_metadata_revision=logical_to_meta,
        context_by_logical_document=contexts,
        related_requirements=related_requirements,
    )
    plan = plan_fact_normalization_calls(
        authority=authority,
        revision=revision,
        page_effective_text_map=page_inputs,
        doc_version_to_logical=doc_version_to_logical,
        context_by_logical_document=contexts,
        related_requirements=list(related_requirements),
        max_pages_per_call=max_pages_per_call,
        contract_version=contract_version,
    )
    return plan, adapter_result


def build_evidence_normalizer_input(
    session: Session,
    *,
    authority: FactAuthority,
    run_id: str,
    call_id: str,
    logical_document_id: str,
    page_numbers: list[int],
    expected_input_sha256: str | None,
    page_review_coverage_id: str | None = None,
    max_pages_per_call: int = 20,
    created_at: datetime | None = None,
    include_visual_sources: bool = False,
) -> EvidenceNormalizerInput:
    """从当前完整处理修订重建并核对一次模型调用的完整输入。"""
    plan, source = build_fact_normalization_plan(
        session,
        authority=authority,
        revision_id=authority.complete_processing_revision_id,
        max_pages_per_call=max_pages_per_call,
        allow_image_only=include_visual_sources and page_review_coverage_id is not None,
    )
    matches = [
        call
        for call in plan.calls
        if call.logical_document_id == logical_document_id
        and list(call.page_numbers) == page_numbers
    ]
    if len(matches) != 1:
        raise FactPlanningSourceError(
            f"逻辑文档 {logical_document_id} 页 {page_numbers} 不属于冻结的规范化计划"
        )
    planned = matches[0]
    if (
        expected_input_sha256 is not None
        and page_review_coverage_id is None
        and planned.input_sha256 != expected_input_sha256
    ):
        raise FactPlanningSourceError(
            f"逻辑文档 {logical_document_id} 页 {page_numbers} 的重建输入与任务冻结哈希不一致"
        )
    pages = [
        EvidenceNormalizerPageInput(
            source_document_version_id=page.source_document_version_id,
            page_artifact_id=page.page_artifact_id,
            ocr_page_id=page.ocr_page_id,
            page_number=page.page_number,
            effective_text=page.effective_text or "",
            effective_text_sha256=page.effective_text_sha256,
            locator_ids=list(page.locator_ids),
        )
        for page in planned.page_inputs
    ]
    available_locator_ids = sorted(
        {locator_id for page in planned.page_inputs for locator_id in page.locator_ids}
    )
    available_locators = sorted(
        (
            locator
            for page in planned.page_inputs
            for locator in page.locator_inputs
        ),
        key=lambda item: item.locator_id,
    )
    page_review = None
    if page_review_coverage_id is not None:
        page_review = build_page_review_normalizer_input(
            session,
            coverage_id=page_review_coverage_id,
            logical_document_id=logical_document_id,
            page_numbers=page_numbers,
            doc_version_to_logical=source.doc_version_to_logical,
            include_visual_sources=include_visual_sources,
        )
    if include_visual_sources:
        if page_review is None:
            raise FactPlanningSourceError("视觉来源输入必须绑定已完成的双模型判读")
        from app.services.page_review_visual_sources import rebuild_visual_sources
        from app.projections.page_review_visual_locators import project_visual_locators
        wanted = {page.page_artifact_id for page in pages}
        visual = [locator for group in rebuild_visual_sources(session, authority, page_review_coverage_id, page_ids=wanted)
                  if group.page_artifact_id in wanted for locator in project_visual_locators(group)]
        available_locators.extend(EvidenceNormalizerLocatorInput(
            locator_id=item.locator_id, page_number=item.page_number,
            source_layer=item.source_layer, precision=item.precision,
            source_text_sha256=item.source_text_sha256, localized_text=item.excerpt,
            page_review_visual=item.page_review_visual,
        ) for item in visual)
        available_locators.sort(key=lambda item: item.locator_id)
        available_locator_ids = sorted(item.locator_id for item in available_locators)
        for page in pages:
            page.locator_ids = sorted(set(page.locator_ids) | {
                item.locator_id for item in visual if item.page_artifact_id == page.page_artifact_id})
    input_scope_sha256 = planned.input_sha256
    if page_review is not None:
        input_scope_sha256 = evidence_normalizer_input_scope_hash(
            authority=authority,
            logical_document_id=logical_document_id,
            context=planned.context,
            related_requirements=list(planned.related_requirements),
            manifest_sha256=source.revision.manifest_sha256,
            completion_manifest_sha256=source.revision.completion_manifest_sha256,
            page_numbers=page_numbers,
            pages=pages,
            page_review=page_review,
            available_locator_ids=available_locator_ids,
            available_locators=available_locators,
        )
        if (
            expected_input_sha256 is not None
            and input_scope_sha256 != expected_input_sha256
        ):
            raise FactPlanningSourceError(
                f"逻辑文档 {logical_document_id} 页 {page_numbers} 的页级判读输入与任务冻结哈希不一致"
            )
    return EvidenceNormalizerInput(
        run_id=run_id,
        call_id=call_id,
        authority=authority,
        logical_document_id=logical_document_id,
        context=planned.context,
        related_requirements=list(planned.related_requirements),
        manifest_sha256=source.revision.manifest_sha256,
        completion_manifest_sha256=source.revision.completion_manifest_sha256,
        page_numbers=page_numbers,
        pages=pages,
        page_review=page_review,
        available_locator_ids=available_locator_ids,
        available_locators=available_locators,
        input_scope_sha256=input_scope_sha256,
        created_at=created_at or datetime.now(UTC),
    )


def build_page_review_normalizer_input(
    session: Session,
    *,
    coverage_id: str,
    logical_document_id: str,
    page_numbers: list[int],
    doc_version_to_logical: dict[str, str],
    include_visual_sources: bool = False,
) -> EvidenceNormalizerPageReviewInput:
    """重建一次规范化调用内的采信页级记录；失败页直接阻断。"""
    repository = PageReviewRepository(session)
    coverage = repository.get_coverage(coverage_id)
    wanted_pages = set(page_numbers)
    entries = [
        entry
        for entry in coverage.entries
        if doc_version_to_logical.get(entry.source_document_version_id)
        == logical_document_id
        and entry.page_number in wanted_pages
    ]
    if [entry.page_number for entry in entries] != page_numbers:
        raise FactPlanningSourceError("页级判读覆盖与规范化调用页清单不一致")
    if any(
        entry.disposition == PageDisposition.FAILED_PENDING_REREAD
        for entry in entries
    ):
        raise FactPlanningSourceError("页级判读仍有失败待复读页面，不能开始事实规范化")

    reconciliations = []
    reviews = []
    for entry in entries:
        if entry.reconciliation_id is None:
            continue
        reconciliation = repository.get_reconciliation(entry.reconciliation_id)
        reconciliations.append(reconciliation)
        reviews.extend(
            repository.get_review(page_review_id)
            for page_review_id in reconciliation.page_review_ids
        )
    scope_sha256 = page_review_input_scope_hash(
        coverage_id=coverage.coverage_id,
        clause_pack_sha256=coverage.clause_pack_sha256,
        entries=entries,
        reviews=reviews,
        reconciliations=reconciliations,
        visual_source_policy="page-review-visual-sources/v1" if include_visual_sources else None,
    )
    return EvidenceNormalizerPageReviewInput(
        coverage_id=coverage.coverage_id,
        clause_pack_sha256=coverage.clause_pack_sha256,
        entries=entries,
        reviews=reviews,
        reconciliations=reconciliations,
        scope_sha256=scope_sha256,
        visual_source_policy="page-review-visual-sources/v1" if include_visual_sources else None,
    )


# --------------------------------------------------------------- 视觉观察接线


def collect_visual_observation_attachments(
    session: Session,
    *,
    revision: CompleteEvidenceProcessingRevision,
    doc_version_to_logical: dict[str, str],
) -> tuple[SelectiveVisionObservationAttachment, ...]:
    """按最小来源保真合同收集可进入冻结候选输入的成功视觉观察。

    纳入规则（全部满足才纳入；不满足即静默排除，不报错、不污染原文）：

    1. 仅 ``status=succeeded`` 的观察（closed 行只是审计，永不进入输入）；
    2. 页身份闭合：观察经仓储回读校验后，还必须锚定冻结 manifest 中的
       ``page_artifact_id``，且资料版本与页码与清单条目一致（旧修订/其他
       页产物的观察不在冻结页集合内，天然排除）；
    3. OCR 身份闭合：观察携带 ``ocr_page_id`` 时必须等于清单条目的
       ``ocr_page_id``（OCR 漂移/旧 OCR 绑定的观察不纳入；其 OCR 风险提示
       一并作废）；未携带 OCR 绑定的观察仅作为补充材料纳入；
    4. 文档归属：资料版本必须映射到本修订的逻辑文档（无跨文档借用）。

    返回按 ``(资料版本, 页码, 观察身份哈希)`` 确定性排序的附件元组；
    仓储回读自带 payload/身份/来源闭包复核，篡改行在此处即失败。
    """
    from app.storage.evidence_models import SourceDocumentVersionV2Record

    if not revision.manifest:
        raise FactPlanningSourceError("完整处理修订的页清单不能为空，无法收集视觉观察")
    repository = SelectiveVisionObservationRepository(session)
    attachments: list[SelectiveVisionObservationAttachment] = []
    seen_identity: dict[str, str] = {}
    for entry in sorted(revision.manifest, key=lambda e: (e.source_document_version_id, e.page_number)):
        logical = doc_version_to_logical.get(entry.source_document_version_id)
        if logical is None:
            raise FactPlanningSourceError(
                f"资料版本 {entry.source_document_version_id} 缺少逻辑文档映射，"
                "无法收集视觉观察（拒绝隐式归属）"
            )
        record = session.get(SourceDocumentVersionV2Record, entry.source_document_version_id)
        if record is None or record.logical_document_id != logical:
            raise FactPlanningSourceError(
                f"资料版本 {entry.source_document_version_id} 的逻辑文档映射与当前记录不一致"
            )
        for observation in repository.list_by_page_artifact(entry.page_artifact_id):
            if observation.status is not SelectiveVisionObservationStatus.SUCCEEDED:
                continue
            if (
                observation.source_document_version_id != entry.source_document_version_id
                or observation.page_ordinal != entry.page_number
            ):
                continue
            if (
                observation.ocr_page_id is not None
                and observation.ocr_page_id != entry.ocr_page_id
            ):
                # OCR 漂移/旧修订绑定：观察与其 OCR 风险提示一并排除
                continue
            identity = observation.observation_identity_sha256
            previous = seen_identity.get(identity)
            if previous is not None and previous != observation.observation_id:
                raise FactPlanningSourceError(
                    f"同一成功观察身份 {identity} 对应多个观察行，拒绝冻结"
                )
            seen_identity[identity] = observation.observation_id
            attachments.append(
                SelectiveVisionObservationAttachment(
                    observation_id=observation.observation_id,
                    observation_identity_sha256=identity,
                    page_artifact_id=observation.page_artifact_id,
                    source_document_version_id=observation.source_document_version_id,
                    page_ordinal=observation.page_ordinal,
                    page_image_sha256=observation.page_image_sha256,
                    ocr_page_id=observation.ocr_page_id,
                    ocr_raw_text_sha256=observation.ocr_raw_text_sha256,
                    plan_version=observation.plan_version,
                    model_id=observation.model_id,
                    prompt_sha256=observation.prompt_sha256,
                    source_ref=observation.source_ref,
                    observation_text=observation.observation_text or "",
                    risk_reasons=list(observation.risk_reasons),
                    risk_reasons_sha256=observation.risk_reasons_sha256,
                )
            )
    attachments.sort(
        key=lambda a: (
            a.source_document_version_id,
            a.page_ordinal,
            a.observation_identity_sha256,
        )
    )
    return tuple(attachments)


def select_call_visual_observation_attachments(
    attachments: tuple[SelectiveVisionObservationAttachment, ...],
    *,
    doc_version_to_logical: dict[str, str],
    logical_document_id: str,
    page_numbers: list[int] | tuple[int, ...],
) -> tuple[SelectiveVisionObservationAttachment, ...]:
    """从全修订附件中确定性选取属于单次调用的附件（保持身份升序）。"""
    pages = set(page_numbers)
    selected = tuple(
        attachment
        for attachment in attachments
        if doc_version_to_logical.get(attachment.source_document_version_id)
        == logical_document_id
        and attachment.page_ordinal in pages
    )
    return tuple(sorted(selected, key=lambda a: a.observation_identity_sha256))


def visual_observation_run_scope(
    attachments: tuple[SelectiveVisionObservationAttachment, ...],
) -> str | None:
    """全修订视觉观察范围哈希；空集合为 ``None``（与无观察运行的旧键兼容）。"""
    return visual_observation_scope_sha256(
        [a.observation_identity_sha256 for a in attachments]
    )
