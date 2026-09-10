"""受试者资料期望的确定性投影服务。"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.domain.contracts.evidence_expectations_v2 import (
    CoverageGapSignal,
    CoverageObservation,
    EvidenceExpectationV2,
)
from app.domain.contracts.facts import FactAuthority
from app.projections.evidence_expectations import project_expectation
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    EvidenceLocatorRepository,
)
from app.storage.evidence_repositories import SourceDocumentMetadataRevisionRepository
from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
from app.storage.fact_repositories import ClinicalFactV2Repository
from app.storage.repositories import EpisodeRepository, list_expectation_templates


class EvidenceExpectationProjectionError(RuntimeError):
    """投影所需的冻结资料类型或定位不完整。"""


class EvidenceExpectationProjectionService:
    """从当前权威事实、冻结资料类型和结构化缺口生成投影。"""

    def project(
        self,
        session: Session,
        *,
        authority: FactAuthority,
        gap_signals: list[CoverageGapSignal],
        created_at: datetime | None = None,
        template_ids: set[str] | None = None,
        exclude_fact_ids: set[str] | None = None,
        run_id: str | None = None,
    ) -> list[EvidenceExpectationV2]:
        created_at = created_at or datetime.now(UTC)
        episode = EpisodeRepository(session).get(authority.review_episode_id)
        if (
            episode.project_id != authority.project_id
            or episode.subject_id != authority.subject_id
            or episode.revision != authority.episode_revision
            or episode.rule_set_id != authority.rule_set_id
            or episode.rule_set_revision != authority.rule_set_revision
        ):
            raise EvidenceExpectationProjectionError(
                "资料期望所用审核节点与不可变权威元组不一致"
            )
        excluded = exclude_fact_ids or set()
        facts = [
            fact
            for fact in ClinicalFactV2Repository(session).list_by_episode(
                authority.review_episode_id
            )
            if fact.authority == authority
            and fact.fact_id not in excluded
            and (run_id is None or fact.run_id == run_id)
        ]
        observations = self._observations(session, authority, facts)
        templates = list_expectation_templates(
            session, authority.rule_set_id, authority.rule_set_revision
        )
        if template_ids is not None:
            templates = [
                template for template in templates if template.template_id in template_ids
            ]
        repository = EvidenceExpectationV2Repository(session)
        result = []
        for template in templates:
            if template.due_stage == episode.stage:
                if episode.workflow_stage_id is None:
                    raise EvidenceExpectationProjectionError(
                        "当前审核节点未绑定具体流程节点，无法判定同一阶段"
                        f"的资料要求 {template.requirement_id} 是否已到期"
                    )
                if template.workflow_stage_id != episode.workflow_stage_id:
                    raise EvidenceExpectationProjectionError(
                        f"资料要求 {template.requirement_id} 属于同一阶段的另一流程节点"
                        f" {template.workflow_stage_id}，当前节点为 {episode.workflow_stage_id}，"
                        "缺少节点先后关系时拒绝猜测到期状态"
                    )
            latest = repository.latest_by_template(
                authority.review_episode_id, template.template_id
            )
            revision = 1 if latest is None else latest.revision + 1
            expectation = project_expectation(
                template=template,
                authority=authority,
                current_stage=episode.stage,
                observations=observations,
                gap_signals=gap_signals,
                revision=revision,
                created_at=created_at,
            )
            result.append(repository.project(expectation))
        return result

    @staticmethod
    def _observations(session: Session, authority: FactAuthority, facts):
        revision = CompleteEvidenceProcessingRevisionRepository(session).get(
            authority.complete_processing_revision_id
        )
        metadata_repository = SourceDocumentMetadataRevisionRepository(session)
        metadata_by_document = {
            item.source_document_version_id: item
            for item in (
                metadata_repository.get(metadata_id)
                for metadata_id in revision.metadata_revision_ids
            )
        }
        locator_repository = EvidenceLocatorRepository(session)
        observations = []
        visual_sources = {}
        for fact in facts:
            source_types = set()
            for locator_id in fact.locator_ids:
                locator = locator_repository.get(locator_id)
                metadata = metadata_by_document.get(
                    locator.source_document_version_id
                )
                if metadata is None:
                    raise EvidenceExpectationProjectionError(
                        f"事实 {fact.fact_id} 的定位 {locator_id} 所属资料未在"
                        "当前完整处理修订中冻结资料类型"
                    )
                document_type = metadata.document_type.strip().casefold()
                # A file category cannot certify that a source contains written judgment.
                if document_type != "investigator_assessment":
                    source_types.add(document_type)
                provenance = getattr(locator, "page_review_visual", None)
                if (provenance is not None and fact.supported_requirement_ids
                    and fact.fact_type == "investigator_assessment"):
                    from app.services.page_review_visual_sources import rebuild_visual_sources
                    from app.services.fact_normalization_source_adapter import FactPlanningSourceError
                    from app.projections.page_review_visual_locators import project_visual_locators
                    from app.projections.written_judgment_evidence import written_judgment_locator_ids

                    if provenance.coverage_id not in visual_sources:
                        try:
                            visual_sources[provenance.coverage_id] = {
                                group.source_set_id: group
                                for group in rebuild_visual_sources(session, authority, provenance.coverage_id)
                            }
                        except FactPlanningSourceError as exc:
                            raise EvidenceExpectationProjectionError("无法按本次原件记录核实判断摘录来源") from exc
                    group = visual_sources[provenance.coverage_id].get(provenance.source_set_id)
                    if group is None or locator not in project_visual_locators(group):
                        raise EvidenceExpectationProjectionError("判断摘录与已保存的原件核对记录不一致")
                    if locator_id in written_judgment_locator_ids(group, asserted_object=fact.asserted_object):
                        source_types.add("investigator_assessment")
            observations.append(
                CoverageObservation(fact=fact, source_types=sorted(source_types))
            )
        return observations
