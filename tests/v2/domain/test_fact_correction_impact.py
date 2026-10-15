"""Phase 5 Slice 5.7 修订影响范围规划确定性测试（纯函数，无存储）。

覆盖：定位/文档/事实/事件/暴露起点的局部闭包；无关实体不进入范围；任一反向
链缺失、越过冻结权威或无法闭合时回退整个审核节点，并给出含
「将重新整理本审核节点全部事实」的中文原因。
"""

from __future__ import annotations

import pytest

from app.domain.contracts.facts import FactAuthority
from app.domain.planning.fact_correction_impact import (
    NODE_RECOMPUTE_MESSAGE,
    FactCorrectionImpactEntity,
    FactCorrectionImpactGraph,
    FactCorrectionImpactIndexFlags,
    FactCorrectionImpactSeed,
    FactReplacementSignature,
    LocatorDocumentBinding,
    LocatorEntityLink,
    ProfileRevisionIndex,
    plan_fact_correction_impact,
)

OTHER = FactAuthority(
    project_id="proj-1",
    subject_id="subj-1",
    review_episode_id="ep-1",
    episode_revision=2,
    protocol_version_id="pv-1",
    rule_set_id="rs-1",
    rule_set_revision=1,
    evidence_snapshot_v2_id="snap-2",
    complete_processing_revision_id="proc-2",
)


def _authority() -> FactAuthority:
    return FactAuthority(
        project_id="proj-1",
        subject_id="subj-1",
        review_episode_id="ep-1",
        episode_revision=1,
        protocol_version_id="pv-1",
        rule_set_id="rs-1",
        rule_set_revision=1,
        evidence_snapshot_v2_id="snap-1",
        complete_processing_revision_id="proc-1",
    )


def _entity(
    kind,
    entity_id,
    *,
    locators=(),
    facts=(),
    events=(),
    exposures=(),
    authority=None,
    fact_type=None,
    supported_requirement_ids=(),
    requirement_id=None,
):
    if kind == "fact" and fact_type is None:
        fact_type = "vital_sign"
    if kind == "expectation":
        if fact_type is None:
            fact_type = "vital_sign"
        if requirement_id is None:
            requirement_id = "req-vs"
    return FactCorrectionImpactEntity(
        entity_kind=kind,
        entity_id=entity_id,
        authority=authority or _authority(),
        locator_ids=tuple(locators),
        fact_ids=tuple(facts),
        event_ids=tuple(events),
        exposure_ids=tuple(exposures),
        fact_type=fact_type,
        supported_requirement_ids=tuple(supported_requirement_ids),
        requirement_id=requirement_id,
    )


def _graph(**overrides) -> FactCorrectionImpactGraph:
    authority = overrides.pop("authority", _authority())
    base = dict(
        authority=authority,
        frozen_locator_ids=("loc-1", "loc-2"),
        locator_documents=(
            LocatorDocumentBinding(locator_id="loc-1", document_id="doc-1"),
            LocatorDocumentBinding(locator_id="loc-2", document_id="doc-2"),
        ),
        locator_entities=(
            LocatorEntityLink(locator_id="loc-1", entity_kind="fact", entity_id="fact-1"),
            LocatorEntityLink(locator_id="loc-1", entity_kind="event", entity_id="event-1"),
            LocatorEntityLink(locator_id="loc-1", entity_kind="exposure", entity_id="exp-1"),
            LocatorEntityLink(locator_id="loc-1", entity_kind="expectation", entity_id="expct-1"),
            LocatorEntityLink(locator_id="loc-2", entity_kind="fact", entity_id="fact-2"),
        ),
        entities=(
            _entity("fact", "fact-1", locators=("loc-1",)),
            _entity("fact", "fact-2", locators=("loc-2",)),
            _entity("event", "event-1", locators=("loc-1",), facts=("fact-1",)),
            _entity("exposure", "exp-1", locators=("loc-1",), facts=("fact-1",)),
            _entity("expectation", "expct-1", locators=("loc-1",), facts=("fact-1",)),
        ),
        event_fact_links=(("event-1", "fact-1"),),
        exposure_fact_links=(("exp-1", "fact-1"),),
        rule_link_ids_by_fact=(("fact-1", ("link-1",)), ("fact-2", ("link-2",))),
        profile_revisions=(
            ProfileRevisionIndex(
                revision_id="profile-1",
                authority=authority,
                status="succeeded",
                item_refs=(("event", "event-1"), ("exposure", "exp-1"), ("fact", "fact-1")),
            ),
            ProfileRevisionIndex(
                revision_id="profile-2",
                authority=authority,
                status="succeeded",
                item_refs=(("fact", "fact-2"),),
            ),
        ),
        indexes=FactCorrectionImpactIndexFlags(),
    )
    base.update(overrides)
    return FactCorrectionImpactGraph(**base)


def _fact_seed(*ids: str, replacement=None) -> FactCorrectionImpactSeed:
    if replacement is None:
        replacement = FactReplacementSignature(fact_type="vital_sign")
    return FactCorrectionImpactSeed(kind="fact", ids=ids, replacement=replacement)


def test_locator_seed_proves_local_closure_and_excludes_unrelated_fact():
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(kind="locator", ids=("loc-1",)),
        _graph(),
    )
    assert scope.scope_kind == "local"
    assert scope.fallback_reason is None
    assert scope.affected_locator_ids == ["loc-1"]
    assert scope.affected_document_ids == ["doc-1"]
    assert scope.affected_fact_ids == ["fact-1"]
    assert scope.affected_event_ids == ["event-1"]
    assert scope.affected_exposure_ids == ["exp-1"]
    assert scope.affected_rule_link_ids == ["link-1"]
    assert scope.affected_expectation_ids == ["expct-1"]
    assert scope.affected_profile_revision_ids == ["profile-1"]
    assert "fact-2" not in scope.affected_fact_ids
    assert "profile-2" not in scope.affected_profile_revision_ids
    assert "link-2" not in scope.affected_rule_link_ids


def test_document_seed_includes_all_locators_on_that_document_only():
    graph = _graph(
        locator_documents=(
            LocatorDocumentBinding(locator_id="loc-1", document_id="doc-1"),
            LocatorDocumentBinding(locator_id="loc-2", document_id="doc-1"),
        ),
        locator_entities=(
            LocatorEntityLink(locator_id="loc-1", entity_kind="fact", entity_id="fact-1"),
            LocatorEntityLink(locator_id="loc-1", entity_kind="event", entity_id="event-1"),
            LocatorEntityLink(locator_id="loc-1", entity_kind="exposure", entity_id="exp-1"),
            LocatorEntityLink(locator_id="loc-1", entity_kind="expectation", entity_id="expct-1"),
            LocatorEntityLink(locator_id="loc-2", entity_kind="fact", entity_id="fact-2"),
        ),
    )
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(kind="document", ids=("doc-1",)),
        graph,
    )
    assert scope.scope_kind == "local"
    assert scope.affected_locator_ids == ["loc-1", "loc-2"]
    assert scope.affected_fact_ids == ["fact-1", "fact-2"]
    assert sorted(scope.affected_profile_revision_ids) == ["profile-1", "profile-2"]


def test_fact_seed_pulls_conflict_siblings_and_expectation_coverage_facts():
    graph = _graph(
        locator_entities=(
            LocatorEntityLink(locator_id="loc-1", entity_kind="fact", entity_id="fact-1"),
            LocatorEntityLink(locator_id="loc-1", entity_kind="event", entity_id="event-1"),
            LocatorEntityLink(locator_id="loc-1", entity_kind="exposure", entity_id="exp-1"),
            LocatorEntityLink(locator_id="loc-1", entity_kind="expectation", entity_id="expct-1"),
            LocatorEntityLink(locator_id="loc-1", entity_kind="conflict", entity_id="conf-1"),
            LocatorEntityLink(locator_id="loc-2", entity_kind="conflict", entity_id="conf-1"),
            LocatorEntityLink(locator_id="loc-2", entity_kind="expectation", entity_id="expct-1"),
            LocatorEntityLink(locator_id="loc-2", entity_kind="fact", entity_id="fact-2"),
        ),
        entities=(
            _entity("fact", "fact-1", locators=("loc-1",)),
            _entity("fact", "fact-2", locators=("loc-2",)),
            _entity("event", "event-1", locators=("loc-1",), facts=("fact-1",)),
            _entity("exposure", "exp-1", locators=("loc-1",), facts=("fact-1",)),
            _entity(
                "conflict",
                "conf-1",
                locators=("loc-1", "loc-2"),
                facts=("fact-1", "fact-2"),
            ),
            _entity(
                "expectation",
                "expct-1",
                locators=("loc-1", "loc-2"),
                facts=("fact-1", "fact-2"),
            ),
        ),
    )
    scope = plan_fact_correction_impact(_fact_seed("fact-1"), graph)
    assert scope.scope_kind == "local"
    assert scope.affected_fact_ids == ["fact-1", "fact-2"]
    assert scope.affected_conflict_group_ids == ["conf-1"]
    assert scope.affected_locator_ids == ["loc-1", "loc-2"]
    assert scope.affected_document_ids == ["doc-1", "doc-2"]


def test_cross_authority_profile_is_not_rewritten():
    graph = _graph(
        profile_revisions=(
            ProfileRevisionIndex(
                revision_id="profile-1",
                authority=_authority(),
                status="succeeded",
                item_refs=(("fact", "fact-1"),),
            ),
            ProfileRevisionIndex(
                revision_id="profile-old",
                authority=OTHER,
                status="succeeded",
                item_refs=(("fact", "fact-1"),),
            ),
        )
    )
    scope = plan_fact_correction_impact(_fact_seed("fact-1"), graph)
    assert scope.scope_kind == "local"
    assert scope.affected_profile_revision_ids == ["profile-1"]


@pytest.mark.parametrize(
    "flag, fragment",
    [
        ("locator_documents", "定位到资料版本"),
        ("locator_entities", "定位到实体"),
        ("event_facts", "事件反向索引"),
        ("exposure_facts", "暴露反向索引"),
        ("conflict_members", "冲突组成员"),
        ("rule_links", "规则索引"),
        ("expectations", "资料期望"),
        ("profile_items", "历史 Profile"),
        ("frozen_locators", "完整处理修订定位清单"),
    ],
)
def test_missing_index_flag_falls_back_to_node(flag, fragment):
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(kind="locator", ids=("loc-1",)),
        _graph(indexes=FactCorrectionImpactIndexFlags(**{flag: False})),
    )
    assert scope.scope_kind == "node"
    assert NODE_RECOMPUTE_MESSAGE in (scope.fallback_reason or "")
    assert fragment in (scope.fallback_reason or "")
    assert not scope.affected_fact_ids


def test_locator_without_document_binding_falls_back_to_node():
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(kind="locator", ids=("loc-missing",)),
        _graph(),
    )
    assert scope.scope_kind == "node"
    assert "修订起点不在当前冻结证据闭包中" in (scope.fallback_reason or "")


def test_locator_entity_mismatch_falls_back_to_node():
    graph = _graph(
        locator_entities=(
            LocatorEntityLink(locator_id="loc-1", entity_kind="event", entity_id="event-1"),
            LocatorEntityLink(locator_id="loc-1", entity_kind="exposure", entity_id="exp-1"),
            LocatorEntityLink(locator_id="loc-1", entity_kind="expectation", entity_id="expct-1"),
            LocatorEntityLink(locator_id="loc-2", entity_kind="fact", entity_id="fact-2"),
        )
    )
    scope = plan_fact_correction_impact(_fact_seed("fact-1"), graph)
    assert scope.scope_kind == "node"
    assert "定位链接与实体声明不一致" in (scope.fallback_reason or "")


def test_event_reverse_index_gap_falls_back_to_node():
    graph = _graph(event_fact_links=())
    scope = plan_fact_correction_impact(_fact_seed("fact-1"), graph)
    assert scope.scope_kind == "node"
    assert "事件反向索引" in (scope.fallback_reason or "")


def test_entity_outside_frozen_authority_falls_back_to_node():
    graph = _graph(
        entities=(
            _entity("fact", "fact-1", locators=("loc-1",), authority=OTHER),
            _entity("fact", "fact-2", locators=("loc-2",)),
            _entity("event", "event-1", locators=("loc-1",), facts=("fact-1",)),
            _entity("exposure", "exp-1", locators=("loc-1",), facts=("fact-1",)),
            _entity("expectation", "expct-1", locators=("loc-1",), facts=("fact-1",)),
        )
    )
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(kind="locator", ids=("loc-1",)),
        graph,
    )
    assert scope.scope_kind == "node"
    assert "权威不一致" in (scope.fallback_reason or "")


def test_succeeded_profile_with_unknown_source_falls_back_to_node():
    graph = _graph(
        profile_revisions=(
            ProfileRevisionIndex(
                revision_id="profile-1",
                authority=_authority(),
                status="succeeded",
                item_refs=(("fact", "fact-missing"),),
            ),
        )
    )
    scope = plan_fact_correction_impact(_fact_seed("fact-1"), graph)
    assert scope.scope_kind == "node"
    assert "历史 Profile" in (scope.fallback_reason or "")


def test_unsupported_seed_kind_is_rejected():
    with pytest.raises(ValueError, match="不支持的影响范围起点类型"):
        FactCorrectionImpactSeed(kind="conflict", ids=("conf-1",))
    seed = FactCorrectionImpactSeed(kind="fact", ids=("fact-1",))
    object.__setattr__(seed, "kind", "nope")
    with pytest.raises(ValueError, match="不支持的影响范围起点类型"):
        plan_fact_correction_impact(seed, _graph())


def test_replacement_signature_includes_absent_expectation_when_maps_complete():
    graph = _graph(
        entities=(
            _entity("fact", "fact-1", locators=("loc-1",), fact_type="vital_sign"),
            _entity("fact", "fact-2", locators=("loc-2",), fact_type="vital_sign"),
            _entity("event", "event-1", locators=("loc-1",), facts=("fact-1",)),
            _entity("exposure", "exp-1", locators=("loc-1",), facts=("fact-1",)),
            _entity(
                "expectation",
                "expct-1",
                locators=("loc-1",),
                facts=("fact-1",),
                fact_type="vital_sign",
                requirement_id="req-vs",
            ),
            _entity(
                "expectation",
                "expct-absent",
                locators=(),
                facts=(),
                fact_type="medical_history",
                requirement_id="req-mh",
            ),
        ),
        requirement_expectation_ids=(
            ("req-mh", ("expct-absent",)),
            ("req-vs", ("expct-1",)),
        ),
        fact_type_expectation_ids=(
            ("medical_history", ("expct-absent",)),
            ("vital_sign", ("expct-1",)),
        ),
    )
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(
            kind="fact",
            ids=("fact-1",),
            replacement=FactReplacementSignature(
                fact_type="medical_history",
                supported_requirement_ids=("req-mh",),
            ),
        ),
        graph,
    )
    assert scope.scope_kind == "local"
    assert "expct-absent" in scope.affected_expectation_ids


def test_replacement_signature_without_requirement_maps_falls_back_to_node():
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(
            kind="fact",
            ids=("fact-1",),
            replacement=FactReplacementSignature(
                fact_type="medical_history",
                supported_requirement_ids=("req-mh",),
            ),
        ),
        _graph(entities=(
            _entity("fact", "fact-1", locators=("loc-1",), fact_type="vital_sign"),
            _entity("fact", "fact-2", locators=("loc-2",)),
            _entity("event", "event-1", locators=("loc-1",), facts=("fact-1",)),
            _entity("exposure", "exp-1", locators=("loc-1",), facts=("fact-1",)),
            _entity("expectation", "expct-1", locators=("loc-1",), facts=("fact-1",)),
        )),
    )
    assert scope.scope_kind == "node"
    assert NODE_RECOMPUTE_MESSAGE in (scope.fallback_reason or "")
    assert "规则索引" in (scope.fallback_reason or "")


def test_generating_profile_without_items_is_ignored():
    graph = _graph(
        profile_revisions=(
            ProfileRevisionIndex(
                revision_id="profile-1",
                authority=_authority(),
                status="succeeded",
                item_refs=(("fact", "fact-1"),),
            ),
            ProfileRevisionIndex(
                revision_id="profile-generating",
                authority=_authority(),
                status="generating",
                item_refs=(),
            ),
        )
    )
    scope = plan_fact_correction_impact(_fact_seed("fact-1"), graph)
    assert scope.scope_kind == "local"
    assert scope.affected_profile_revision_ids == ["profile-1"]


def test_fact_seed_without_replacement_falls_back_to_node():
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(kind="fact", ids=("fact-1",)),
        _graph(),
    )
    assert scope.scope_kind == "node"
    assert NODE_RECOMPUTE_MESSAGE in (scope.fallback_reason or "")
    assert "替换签名" in (scope.fallback_reason or "")


def test_fact_without_fact_type_cannot_prove_local():
    graph = _graph(
        entities=(
            _entity("fact", "fact-1", locators=("loc-1",), fact_type=""),
            _entity("fact", "fact-2", locators=("loc-2",)),
            _entity("event", "event-1", locators=("loc-1",), facts=("fact-1",)),
            _entity("exposure", "exp-1", locators=("loc-1",), facts=("fact-1",)),
            _entity("expectation", "expct-1", locators=("loc-1",), facts=("fact-1",)),
        )
    )
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(kind="locator", ids=("loc-1",)),
        graph,
    )
    assert scope.scope_kind == "node"
    assert NODE_RECOMPUTE_MESSAGE in (scope.fallback_reason or "")
    assert "fact_type" in (scope.fallback_reason or "")


def test_expectation_without_requirement_id_cannot_prove_local():
    graph = _graph(
        entities=(
            _entity("fact", "fact-1", locators=("loc-1",)),
            _entity("fact", "fact-2", locators=("loc-2",)),
            _entity("event", "event-1", locators=("loc-1",), facts=("fact-1",)),
            _entity("exposure", "exp-1", locators=("loc-1",), facts=("fact-1",)),
            _entity(
                "expectation",
                "expct-1",
                locators=("loc-1",),
                facts=("fact-1",),
                fact_type="vital_sign",
                requirement_id="",
            ),
        )
    )
    scope = plan_fact_correction_impact(
        FactCorrectionImpactSeed(kind="locator", ids=("loc-1",)),
        graph,
    )
    assert scope.scope_kind == "node"
    assert NODE_RECOMPUTE_MESSAGE in (scope.fallback_reason or "")
    assert "requirement_id" in (scope.fallback_reason or "")
