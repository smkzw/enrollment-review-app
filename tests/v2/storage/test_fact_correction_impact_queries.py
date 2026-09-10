"""Phase 5 Slice 5.7 影响范围只读反向查询与图装载测试。"""

from __future__ import annotations

from app.domain.planning.fact_correction_impact import (
    NODE_RECOMPUTE_MESSAGE,
    FactCorrectionImpactSeed,
    FactReplacementSignature,
    plan_fact_correction_impact,
)
from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
from app.storage.fact_correction_impact_queries import load_fact_correction_impact_graph
from app.storage.codecs import PersistedContractInvalid
from app.storage.facts_models import FactEvidenceLocatorLinkRecord
from app.storage.fact_repositories import (
    ClinicalConflictGroupV2Repository,
    ClinicalEventV2Repository,
    ClinicalFactV2Repository,
    MedicationExposureV2Repository,
)
from app.storage.patient_profile_repository import PatientProfileRevisionRepository
import pytest
from sqlalchemy import select

from tests.v2.storage.test_fact_repositories import (
    _authority,
    _create_and_assert_fact_conflict_group,
    _event,
    _exposure,
    _fact,
    _seed_chain,
)
from tests.v2.storage.test_patient_profile_repository import _revision_with_highlight


@pytest.fixture
def chain(session):
    return _seed_chain(session, "impact-idx")


def test_locator_and_fact_reverse_indexes_are_explicit(chain, session):
    ClinicalFactV2Repository(session).create(_fact(chain))
    ClinicalEventV2Repository(session).create(_event(chain))
    MedicationExposureV2Repository(session).create(_exposure(chain))

    fact_id = f"{chain['run_id']}-fact"
    event_id = f"{chain['run_id']}-event"
    exposure_id = f"{chain['run_id']}-exposure"
    locator_id = chain["locator_id"]

    links = ClinicalFactV2Repository(session).list_entity_links_for_locators([locator_id])
    assert (locator_id, "fact", fact_id) in links
    assert (locator_id, "event", event_id) in links
    assert (locator_id, "exposure", exposure_id) in links

    assert ClinicalEventV2Repository(session).list_event_ids_for_facts([fact_id]) == [
        event_id
    ]
    assert MedicationExposureV2Repository(session).list_exposure_ids_for_facts(
        [fact_id]
    ) == [exposure_id]
    assert ClinicalEventV2Repository(session).list_event_ids_for_facts([]) == []
    assert ClinicalFactV2Repository(session).list_entity_links_for_locators([]) == []


def test_conflict_member_reverse_index(chain, session):
    _create_and_assert_fact_conflict_group(chain, session)
    groups = ClinicalConflictGroupV2Repository(session).list_group_ids_for_members(
        "fact", ["fact-a"]
    )
    assert groups == ["conflict-1"]
    assert ClinicalConflictGroupV2Repository(session).list_group_ids_for_members(
        "fact", ["missing"]
    ) == []


def test_profile_source_index_lists_typed_items(chain, session):
    fact = ClinicalFactV2Repository(session).create(_fact(chain))
    repo = PatientProfileRevisionRepository(session)
    created = repo.create(_revision_with_highlight(chain, source_id=fact.fact_id))
    refs = repo.list_item_source_refs(chain["review_episode_id"])
    assert (created.patient_profile_revision_id, "fact", fact.fact_id) in refs


def test_loaded_graph_proves_local_scope_for_one_locator(chain, session):
    ClinicalFactV2Repository(session).create(_fact(chain))
    ClinicalEventV2Repository(session).create(_event(chain))
    MedicationExposureV2Repository(session).create(_exposure(chain))
    fact = ClinicalFactV2Repository(session).get(f"{chain['run_id']}-fact")
    PatientProfileRevisionRepository(session).create(
        _revision_with_highlight(chain, source_id=fact.fact_id)
    )

    authority = _authority(chain)
    graph = load_fact_correction_impact_graph(session, authority)
    locator = EvidenceLocatorRepository(session).get(chain["locator_id"])
    assert any(
        item.locator_id == chain["locator_id"]
        and item.document_id == locator.source_document_version_id
        for item in graph.locator_documents
    )

    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(kind="locator", ids=(chain["locator_id"],)),
        graph,
    )
    assert scope.scope_kind == "local"
    assert scope.affected_locator_ids == [chain["locator_id"]]
    assert scope.affected_document_ids == [locator.source_document_version_id]
    assert scope.affected_fact_ids == [fact.fact_id]
    assert scope.affected_event_ids == [f"{chain['run_id']}-event"]
    assert scope.affected_exposure_ids == [f"{chain['run_id']}-exposure"]
    assert chain["locator_id_2"] not in scope.affected_locator_ids


def test_loaded_graph_retains_conflict_group_identity(chain, session):
    _create_and_assert_fact_conflict_group(chain, session)
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(
            kind="fact",
            ids=("fact-a",),
            replacement=FactReplacementSignature(fact_type="vital_sign"),
        ),
        load_fact_correction_impact_graph(session, _authority(chain)),
    )
    assert scope.scope_kind == "local"
    assert scope.affected_conflict_group_ids == ["conflict-1"]
    assert set(scope.affected_fact_ids) >= {"fact-a", "fact-b"}


def _count_graph_load_selects(session, chain) -> int:
    from sqlalchemy import event

    engine = session.get_bind()
    count = {"n": 0}

    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        sql = " ".join(str(statement).lower().split())
        if sql.startswith("select") or sql.startswith("select "):
            count["n"] += 1
        elif "select " in sql:
            count["n"] += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        load_fact_correction_impact_graph(session, _authority(chain))
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
    return count["n"]


def test_graph_load_select_count_remains_bounded_with_rule_links(chain, session):
    from tests.v2.storage.test_fact_rule_link_repository import (
        _publish_fact,
        _seed_procedure_requirement,
    )
    from app.storage.fact_rule_link_repository import FactRuleLinkV2Repository

    _seed_procedure_requirement(
        session, chain, requirement_id="req-bulk", fact_type="vital_sign"
    )
    small_n = 4
    large_extra = 12
    for index in range(small_n):
        _publish_fact(
            session,
            chain,
            fact_id=f"rl-s-{index}",
            fact_type="vital_sign",
            asserted_object=f"血压S{index}",
            value=f"{200 + index}",
            supported_requirement_ids=["req-bulk"],
        )
    FactRuleLinkV2Repository(session).rebuild_for_authority(_authority(chain))
    small = _count_graph_load_selects(session, chain)
    for index in range(large_extra):
        _publish_fact(
            session,
            chain,
            fact_id=f"rl-l-{index}",
            fact_type="vital_sign",
            asserted_object=f"血压L{index}",
            value=f"{300 + index}",
            supported_requirement_ids=["req-bulk"],
        )
    FactRuleLinkV2Repository(session).rebuild_for_authority(_authority(chain))
    large = _count_graph_load_selects(session, chain)
    print(f"graph-load SELECT small={small} large={large}")
    assert large == small


def test_missing_expectation_for_published_template_falls_back_on_signature_change(
    chain, session
):
    from tests.v2.projections.test_evidence_expectations import _template
    from app.domain.contracts.enums import ReviewStage

    ClinicalFactV2Repository(session).create(_fact(chain))
    _template(
        session,
        chain,
        requirement_id="req-missing-exp",
        fact_type="medical_history",
        due_stage=ReviewStage.SCREENING,
    )
    graph = load_fact_correction_impact_graph(session, _authority(chain))
    assert graph.indexes.requirement_templates is False
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(
            kind="fact",
            ids=(f"{chain['run_id']}-fact",),
            replacement=FactReplacementSignature(
                fact_type="medical_history",
                supported_requirement_ids=("slice54-req-missing-exp",),
            ),
        ),
        graph,
    )
    assert scope.scope_kind == "node"
    assert NODE_RECOMPUTE_MESSAGE in (scope.fallback_reason or "")


def test_bulk_list_for_authority_rejects_missing_locator_link(chain, session):
    repo = ClinicalFactV2Repository(session)
    fact = repo.create(_fact(chain))
    link = session.execute(
        select(FactEvidenceLocatorLinkRecord).where(
            FactEvidenceLocatorLinkRecord.entity_kind == "fact",
            FactEvidenceLocatorLinkRecord.entity_id == fact.fact_id,
        )
    ).scalars().one()
    session.delete(link)
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="定位链接与 payload"):
        repo.list_for_authority(_authority(chain))


def test_bulk_get_many_rejects_extra_and_mismatched_locator_links(chain, session):
    repo = ClinicalFactV2Repository(session)
    fact = repo.create(_fact(chain))
    extra = FactEvidenceLocatorLinkRecord(
        entity_kind="fact",
        entity_id=fact.fact_id,
        position=2,
        locator_id=chain["locator_id_2"],
        fact_id=fact.fact_id,
    )
    session.add(extra)
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="定位链接与 payload"):
        repo.get_many([fact.fact_id])
    session.delete(extra)
    session.flush()
    link = session.execute(
        select(FactEvidenceLocatorLinkRecord).where(
            FactEvidenceLocatorLinkRecord.entity_kind == "fact",
            FactEvidenceLocatorLinkRecord.entity_id == fact.fact_id,
        )
    ).scalars().one()
    link.locator_id = chain["locator_id_2"]
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="定位链接与 payload"):
        repo.list_for_authority(_authority(chain))
    with pytest.raises(PersistedContractInvalid, match="定位链接与 payload"):
        repo.get(fact.fact_id)


def test_unknown_locator_seed_falls_back_to_node(chain, session):
    graph = load_fact_correction_impact_graph(session, _authority(chain))
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(kind="locator", ids=("locator-does-not-exist",)),
        graph,
    )
    assert scope.scope_kind == "node"
    assert "将重新整理本审核节点全部事实" in (scope.fallback_reason or "")
