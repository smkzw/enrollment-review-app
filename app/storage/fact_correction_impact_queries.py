"""Slice 5.7 修订影响范围的只读反向索引装载。

把定位、资料版本、实体引用、FactRuleLink、资料期望和历史 Profile 条目装入
领域规划图；不做发布、不写修订、不进入入排结论。权威复核失败沿用现有仓储错误。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.contracts.facts import FactAuthority
from app.domain.planning.fact_correction_impact import (
    FactCorrectionImpactEntity,
    FactCorrectionImpactGraph,
    FactCorrectionImpactIndexFlags,
    LocatorDocumentBinding,
    LocatorEntityLink,
    ProfileRevisionIndex,
)
from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    EvidenceLocatorRepository,
)
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.fact_repositories import (
    ClinicalConflictGroupV2Repository,
    ClinicalEventV2Repository,
    ClinicalFactV2Repository,
    MedicationExposureV2Repository,
)
from app.storage.fact_rule_link_repository import FactRuleLinkV2Repository
from app.storage.patient_profile_repository import PatientProfileRevisionRepository
from app.storage.repositories import list_expectation_templates

__all__ = ["load_fact_correction_impact_graph"]


def load_fact_correction_impact_graph(
    session: Session, authority: FactAuthority
) -> FactCorrectionImpactGraph:
    """装载当前冻结权威下证明局部闭包所需的全部显式反向索引。"""
    FactAuthorityValidator(session).validate(authority)
    revision = CompleteEvidenceProcessingRevisionRepository(session).get(
        authority.complete_processing_revision_id
    )
    frozen_locator_ids = tuple(sorted(set(revision.locator_ids)))
    locator_repo = EvidenceLocatorRepository(session)
    locators = locator_repo.get_many(list(frozen_locator_ids)) if frozen_locator_ids else []
    locator_documents = tuple(
        LocatorDocumentBinding(
            locator_id=item.locator_id,
            document_id=item.source_document_version_id,
            processing_revision_id=item.processing_revision_id,
        )
        for item in locators
    )

    fact_repo = ClinicalFactV2Repository(session)
    event_repo = ClinicalEventV2Repository(session)
    exposure_repo = MedicationExposureV2Repository(session)
    conflict_repo = ClinicalConflictGroupV2Repository(session)
    expectation_repo = EvidenceExpectationV2Repository(session)
    rule_repo = FactRuleLinkV2Repository(session)
    profile_repo = PatientProfileRevisionRepository(session)

    facts = fact_repo.list_for_authority(authority)
    events = event_repo.list_for_authority(authority)
    exposures = exposure_repo.list_for_authority(authority)
    conflicts = conflict_repo.list_for_authority(authority)
    expectations = expectation_repo.list_for_authority(authority)
    templates = list_expectation_templates(
        session, authority.rule_set_id, authority.rule_set_revision
    )
    template_by_id = {item.template_id: item for item in templates}
    published_template_ids = [item.template_id for item in templates]
    latest_by_template: dict[str, object] = {}
    for item in expectations:
        current = latest_by_template.get(item.template_id)
        if current is None or item.revision > current.revision:
            latest_by_template[item.template_id] = item
    templates_complete = (
        len(published_template_ids) == len(set(published_template_ids))
        and set(published_template_ids) == set(latest_by_template)
        and all(
            item.authority == authority for item in latest_by_template.values()
        )
        and all(item.template_id in template_by_id for item in latest_by_template.values())
    )

    entities = tuple(
        [
            *(
                FactCorrectionImpactEntity(
                    entity_kind="fact",
                    entity_id=item.fact_id,
                    authority=item.authority,
                    locator_ids=tuple(item.locator_ids),
                    fact_type=item.fact_type,
                    supported_requirement_ids=tuple(item.supported_requirement_ids),
                )
                for item in facts
            ),
            *(
                FactCorrectionImpactEntity(
                    entity_kind="event",
                    entity_id=item.event_id,
                    authority=item.authority,
                    locator_ids=tuple(item.locator_ids),
                    fact_ids=tuple(item.fact_ids),
                )
                for item in events
            ),
            *(
                FactCorrectionImpactEntity(
                    entity_kind="exposure",
                    entity_id=item.exposure_id,
                    authority=item.authority,
                    locator_ids=tuple(item.locator_ids),
                    fact_ids=tuple(item.fact_ids),
                )
                for item in exposures
            ),
            *(
                FactCorrectionImpactEntity(
                    entity_kind="conflict",
                    entity_id=item.conflict_group_id,
                    authority=item.authority,
                    locator_ids=tuple(item.locator_ids),
                    fact_ids=tuple(item.fact_ids),
                    event_ids=tuple(item.event_ids),
                    exposure_ids=tuple(item.exposure_ids),
                )
                for item in conflicts
            ),
            *(
                FactCorrectionImpactEntity(
                    entity_kind="expectation",
                    entity_id=item.expectation_id,
                    authority=item.authority,
                    locator_ids=tuple(item.locator_ids),
                    fact_ids=tuple(item.coverage_fact_ids),
                    fact_type=(
                        template_by_id[item.template_id].fact_type
                        if item.template_id in template_by_id
                        else None
                    ),
                    requirement_id=(
                        template_by_id[item.template_id].requirement_id
                        if item.template_id in template_by_id
                        else None
                    ),
                )
                for item in expectations
            ),
        ]
    )

    entity_locator_ids = sorted(
        {locator_id for entity in entities for locator_id in entity.locator_ids}
    )
    locator_query_ids = sorted(set(frozen_locator_ids) | set(entity_locator_ids))
    locator_entities = tuple(
        LocatorEntityLink(locator_id=locator_id, entity_kind=kind, entity_id=entity_id)
        for locator_id, kind, entity_id in fact_repo.list_entity_links_for_locators(
            locator_query_ids
        )
        if kind in {"fact", "event", "exposure", "conflict", "expectation"}
    )

    fact_ids = [item.fact_id for item in facts]
    event_fact_links = tuple(event_repo.list_event_fact_links(fact_ids))
    exposure_fact_links = tuple(exposure_repo.list_exposure_fact_links(fact_ids))
    rule_links_by_fact = rule_repo.list_for_facts(fact_ids, facts=facts)
    rule_link_ids_by_fact = tuple(
        (
            fact_id,
            tuple(sorted(link.link_id for link in rule_links_by_fact.get(fact_id, []))),
        )
        for fact_id in sorted(fact_ids)
    )

    requirement_expectation_ids: dict[str, list[str]] = {
        item.requirement_id: [] for item in templates
    }
    fact_type_expectation_ids: dict[str, list[str]] = {}
    for item in templates:
        fact_type_expectation_ids.setdefault(item.fact_type, [])
    for item in latest_by_template.values():
        template = template_by_id.get(item.template_id)
        if template is None:
            continue
        requirement_expectation_ids.setdefault(template.requirement_id, []).append(
            item.expectation_id
        )
        fact_type_expectation_ids.setdefault(template.fact_type, []).append(
            item.expectation_id
        )

    profile_revisions = tuple(
        ProfileRevisionIndex(
            revision_id=revision.patient_profile_revision_id,
            authority=revision.authority,
            status=revision.status.value,
            item_refs=tuple(
                sorted(
                    {
                        (item.kind.value, item.source_id)
                        for section in revision.lanes
                        for item in section.items
                    }
                )
            ),
        )
        for revision in profile_repo.list_for_authority(authority)
    )

    return FactCorrectionImpactGraph(
        authority=authority,
        frozen_locator_ids=frozen_locator_ids,
        locator_documents=locator_documents,
        locator_entities=locator_entities,
        entities=entities,
        event_fact_links=event_fact_links,
        exposure_fact_links=exposure_fact_links,
        rule_link_ids_by_fact=rule_link_ids_by_fact,
        requirement_expectation_ids=tuple(
            (key, tuple(sorted(set(values))))
            for key, values in sorted(requirement_expectation_ids.items())
        ),
        fact_type_expectation_ids=tuple(
            (key, tuple(sorted(set(values))))
            for key, values in sorted(fact_type_expectation_ids.items())
        ),
        profile_revisions=profile_revisions,
        indexes=FactCorrectionImpactIndexFlags(requirement_templates=templates_complete),
    )
