"""入排审核只读投影的确定性与医学安全边界测试。"""
from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import (
    DatePrecision,
    FactGate,
    FactPolarity,
    GateOutcome,
    GapType,
    SourceStrength,
)
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalConflictGroupV2,
    ClinicalFactCandidateV2,
    ClinicalFactV2,
    FactAuthority,
    FactGateResult,
    PartialDateRange,
    clinical_fact_stable_identity,
)
from app.services.eligibility_review_projection import (
    EligibilityReviewProjectionService,
    EligibilityReviewProjectionError,
    _continuing_obligation_note,
    _fact_refs,
    _restricted_clause_projection,
    _selected_predicate_locators,
    _selected_control_locators,
    adapt_clinical_fact_v2,
    fold_fact_chain_heads,
)
from app.domain.contracts.protocol_controls import ControlContinuingObligation
from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
from app.storage.fact_repositories import (
    ClinicalConflictGroupV2Repository,
    ClinicalFactV2Repository,
    FactGateResultRepository,
    FactNormalizationCandidateRepository,
)
from app.storage.fact_rule_link_repository import FactRuleLinkV2Repository
from tests.v2.storage.test_fact_repositories import _seed_chain


NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)


def test_work_draft_source_navigation_uses_only_proven_pair_location(monkeypatch) -> None:
    from app.services import eligibility_review_projection as projection

    predicate = SimpleNamespace(
        predicate_id="predicate-1", predicate_identity_sha256="identity-1",
        predicate=SimpleNamespace(repeat_scheme=None, occurrence_window=None),
    )
    selection = SimpleNamespace(
        predicate_frozen_input=SimpleNamespace(components=[SimpleNamespace(
            rule_component_id="component-1", binding_predicates=[predicate],
        )]),
        identity_outcomes=[SimpleNamespace(
            identity_sha256="identity-1", status="usable", usable_pair_ids=["pair-1"],
        )],
        source_pair_locations=(("identity-1", "pair-1", "fact-1", "locator-1"),),
    )
    evaluation = SimpleNamespace(predicate_evaluations={
        "predicate-1": SimpleNamespace(used_fact_ids=["fact-1"]),
    })
    selected = _selected_predicate_locators(selection, "component-1", evaluation, {"fact-1"})
    assert selected == {"fact-1": {"locator-1"}}

    locators = [SimpleNamespace(
        locator_id=f"locator-{number}", page_number=number,
        source_document_version_id="document-1", page_artifact_id=f"page-{number}",
        excerpt=f"第{number}份扫描",
    ) for number in (1, 2)]
    monkeypatch.setattr(projection, "EvidenceLocatorRepository", lambda _session: SimpleNamespace(
        get_many=lambda _ids: locators,
    ))
    fact = SimpleNamespace(fact_id="fact-1", locator_ids=["locator-1", "locator-2"])
    refs = _fact_refs(object(), {"fact-1"}, {"fact-1": fact}, selected)
    assert [(item.fact_id, item.locator_id) for item in refs] == [("fact-1", "locator-1")]
    with pytest.raises(projection.EligibilityReviewProjectionError, match="原件范围不一致"):
        _fact_refs(object(), {"fact-1"}, {"fact-1": fact}, {"fact-1": {"another"}})


def test_control_work_draft_navigation_uses_its_own_verified_pairs(monkeypatch) -> None:
    from app.services import eligibility_review_projection as module

    selection = SimpleNamespace(
        identity_outcomes=[SimpleNamespace(
            identity_sha256="obligation", status="usable", usable_pair_ids=["pair"],
        )],
        source_pair_locations=[
            ("obligation", "pair", "fact", "chosen"),
            ("sibling", "sibling-pair", "fact", "other"),
        ],
    )
    chosen = _selected_control_locators(selection, "obligation", {"fact"})
    assert chosen == {"fact": {"chosen"}}
    fact = SimpleNamespace(fact_id="fact", locator_ids=["chosen", "other"])
    locators = [SimpleNamespace(
        locator_id=value, page_number=index + 1, source_document_version_id="document",
        page_artifact_id=f"page-{index}", excerpt=value,
    ) for index, value in enumerate(fact.locator_ids)]
    monkeypatch.setattr(module, "EvidenceLocatorRepository", lambda _session: SimpleNamespace(
        get_many=lambda _ids: locators,
    ))
    refs = _fact_refs(None, {"fact"}, {"fact": fact}, chosen)
    assert [(item.locator_id, item.page_number) for item in refs] == [("chosen", 1)]
    assert _selected_control_locators(selection, "obligation", set()) == {}


@pytest.mark.parametrize("failure", ["unusable", "missing", "wrong_pair", "sibling_only"])
def test_control_work_draft_does_not_guess_missing_source_pair(failure) -> None:
    selection = SimpleNamespace(
        identity_outcomes=[SimpleNamespace(
            identity_sha256="obligation", status="usable", usable_pair_ids=["pair"],
        )],
        source_pair_locations=[("obligation", "pair", "fact", "chosen")],
    )
    if failure == "unusable":
        selection.identity_outcomes[0].status = "unresolved"
    elif failure == "missing":
        selection.source_pair_locations = []
    elif failure == "wrong_pair":
        selection.identity_outcomes[0].usable_pair_ids = ["another-pair"]
    else:
        selection.source_pair_locations = [("sibling", "pair", "fact", "other")]
    with pytest.raises(EligibilityReviewProjectionError):
        _selected_control_locators(selection, "obligation", {"fact"})


def test_repeat_or_unproven_source_does_not_guess_selected_location() -> None:
    predicate = SimpleNamespace(
        predicate_id="predicate-1", predicate_identity_sha256="identity-1",
        predicate=SimpleNamespace(repeat_scheme=object(), occurrence_window=None),
    )
    selection = SimpleNamespace(
        predicate_frozen_input=SimpleNamespace(components=[SimpleNamespace(
            rule_component_id="component-1", binding_predicates=[predicate],
        )]),
        identity_outcomes=[SimpleNamespace(
            identity_sha256="identity-1", status="usable", usable_pair_ids=["pair-1"],
        )],
        source_pair_locations=(("identity-1", "pair-1", "fact-1", "locator-1"),),
    )
    evaluation = SimpleNamespace(predicate_evaluations={
        "predicate-1": SimpleNamespace(used_fact_ids=["fact-1"]),
    })
    assert _selected_predicate_locators(selection, "component-1", evaluation, {"fact-1"}) == {}


@pytest.mark.parametrize("gap,confirmed", [
    (GapType.PROFESSIONAL_JUDGMENT, True),
    (GapType.OBSERVATION_UNVERIFIED, False),
])
def test_frozen_work_draft_displays_the_calculated_judgment_gap(
    session, monkeypatch, gap, confirmed,
) -> None:
    from app.domain.contracts.enums import BlockingLevel, ComponentDecision, TruthValue
    from app.projections.clause_pack import project_clause_pack
    from app.services.component_review import ComponentReviewResult
    from app.services import frozen_review_calculation as calculation_module
    from app.storage.repositories import get_rule_set

    chain = _seed_chain(session, f"frozen-judgment-{gap.value}")
    authority = chain["authority"]
    rule_set = get_rule_set(session, authority.rule_set_id, authority.rule_set_revision)
    pack = project_clause_pack(rule_set)
    clause = next(item for item in pack.clauses if item.official_code == "EX-02")
    evaluation = SimpleNamespace(
        trigger=SimpleNamespace(truth=TruthValue.UNKNOWN, used_fact_ids=[]),
        exception=None, predicate_evaluations={},
    )
    result = ComponentReviewResult(
        evaluation=evaluation, gaps=frozenset({gap}),
        decision=ComponentDecision.PROFESSIONAL_JUDGMENT if confirmed else ComponentDecision.INDETERMINATE,
        blocking_level=BlockingLevel.BLOCKING,
        judgment_gaps=((clause.evidence_requirements[0].requirement_id, gap),),
    )
    # This isolates projection consumption, not workflow receipt validation.
    monkeypatch.setattr(calculation_module, "calculate_frozen_review", lambda *_args, **_kw: SimpleNamespace(
        components=[SimpleNamespace(rule_component_id=clause.rule_component_id, result=result)],
        control_outcomes=[], computation_atom_evaluations={},
    ))
    frozen = SimpleNamespace(
        authority=authority, clause_pack=pack, facts=[], judgment_search_results=[],
        conflict_groups=(),
    )
    projected = EligibilityReviewProjectionService()._project_frozen_work_draft(
        session, frozen=frozen, rule_set=rule_set, selections=(),
    )
    rendered = projected.clauses[0]
    assert rendered.gap_type == gap.value
    if confirmed:
        assert "未见本条所需的研究者书面判断" in rendered.reason
        assert "尚未完成" not in rendered.reason
    else:
        assert "尚未完成" in rendered.reason
        assert "未见本条所需的研究者书面判断" not in rendered.reason
    assert not rendered.fact_refs
    assert projected.work_draft_state == "current"


@pytest.mark.parametrize("has_selection", [True, False])
def test_frozen_work_draft_control_consumer_keeps_verified_location(
    session, monkeypatch, has_selection,
) -> None:
    from app.domain.contracts.control_evaluation_spec import ControlAtomEvaluationSpec
    from app.services import eligibility_review_projection as projection
    from app.services import frozen_review_calculation as calculation_module

    chain = _seed_chain(session, f"frozen-control-{has_selection}")
    atom = SimpleNamespace(
        obligation_id="obligation", continuing_obligation=None,
        source_excerpts=["记录过敏史。"],
        evaluation=ControlAtomEvaluationSpec(
            determination_mode="semantic", proposition="记录过敏史。",
            time_purpose="not_applicable", source_span_ids=["span"],
            source_excerpts=["记录过敏史。"],
        ),
    )
    source = SimpleNamespace(
        protocol_control_id="control", display_label="方案补充要求", title="记录过敏史",
        source_span_ids=["span"], obligation_expression=SimpleNamespace(
            groups=[SimpleNamespace(atoms=[atom])],
        ),
    )
    publication = SimpleNamespace(catalog=SimpleNamespace(
        controls=[source], restricted_statements=[],
    ))
    frozen = SimpleNamespace(
        authority=chain["authority"], judgment_search_results=[],
        conflict_groups=[
            SimpleNamespace(conflict_group_id="event-conflict", member_kind="event", event_ids=["event-1", "event-2"], exposure_ids=[]),
            SimpleNamespace(conflict_group_id="exposure-conflict", member_kind="exposure", event_ids=[], exposure_ids=["exposure-1", "exposure-2"]),
            SimpleNamespace(conflict_group_id="fact-conflict", member_kind="fact"),
        ],
        clause_pack=SimpleNamespace(clauses=[], restricted_clauses=[], control_publication=publication),
        facts=[SimpleNamespace(fact_id="fact", locator_ids=["chosen", "other"])],
    )
    selection = SimpleNamespace(
        candidate_family="control",
        identity_outcomes=[SimpleNamespace(
            identity_sha256="identity", status="usable", usable_pair_ids=["pair"],
        )],
        source_pair_locations=[("identity", "pair", "fact", "chosen")],
    )
    outcome = SimpleNamespace(
        protocol_control_id="control", obligations=[SimpleNamespace(
            obligation_id="obligation", obligation_group_id="group", identity_sha256="identity",
            statement="记录过敏史。", status="fulfilled", observation_reason_codes=[],
            used_fact_ids=["fact"],
        )],
    )
    # Calculator output is frozen here to test the real projection consumer.
    monkeypatch.setattr(calculation_module, "calculate_frozen_review", lambda *_args, **_kw: SimpleNamespace(
        components=[], control_outcomes=[outcome], computation_atom_evaluations={},
    ))
    locators = [SimpleNamespace(
        locator_id=value, page_number=index + 1, source_document_version_id="document",
        page_artifact_id=f"page-{index}", excerpt=value,
    ) for index, value in enumerate(["chosen", "other"])]
    monkeypatch.setattr(projection, "EvidenceLocatorRepository", lambda _session: SimpleNamespace(
        get_many=lambda _ids: locators,
    ))
    service = EligibilityReviewProjectionService()
    if not has_selection:
        with pytest.raises(EligibilityReviewProjectionError, match="缺少本次核对依据"):
            service._project_frozen_work_draft(session, frozen=frozen, rule_set=object(), selections=())
        return
    projected = service._project_frozen_work_draft(
        session, frozen=frozen, rule_set=object(), selections=(selection,),
    )
    rendered = projected.controls[0].obligations[0]
    assert rendered.status == "fulfilled"
    assert [(item.locator_id, item.page_number) for item in rendered.fact_refs] == [("chosen", 1)]
    assert [(item.conflict_group_id, item.member_kind, item.member_ids) for item in projected.unassigned_conflicts] == [
        ("event-conflict", "event", ("event-1", "event-2")),
        ("exposure-conflict", "exposure", ("exposure-1", "exposure-2")),
    ]


@pytest.mark.parametrize("limitation,owner", [
    ("interpretation_unresolved", "sponsor_medical_or_project"),
    ("consumer_unavailable", None),
])
def test_source_bound_unresolved_rule_is_visible_without_patient_gap_or_positive_result(
    limitation: str, owner: str | None,
) -> None:
    from app.domain.contracts.clause_pack import ClausePackRestrictedClause
    from app.domain.contracts.enums import ComponentDecision, RuleKind

    clause = ClausePackRestrictedClause(
        clause_id="component:IN-01:02", rule_id="rule:IN-01",
        official_code="IN-01", display_code="IN-01b", kind=RuleKind.INCLUSION,
        title="独立来源要求", source_text="完整规则原文",
        source_span_ids=["span:1"], source_excerpts=["独立来源要求"],
        limitation_kind=limitation,
        unresolved_dimensions=["适用对象尚未核清"],
    )
    projected = _restricted_clause_projection(clause)
    assert projected.decision == ComponentDecision.INDETERMINATE.value
    assert "适用对象尚未核清" in projected.reason
    assert projected.fact_refs == ()
    assert projected.limitation_kind == limitation
    assert projected.action_owner == owner
    assert projected.action_detail
    assert projected.gap_type is None


def test_future_control_is_explained_without_claiming_current_compliance() -> None:
    continuation = ControlContinuingObligation(
        statement="不得调整既定治疗",
        prospective_period={"period": "treatment_period"},
        source_span_ids=["span:control"],
        source_excerpts=["筛选期及治疗期间不得调整既定治疗"],
    )
    note = _continuing_obligation_note(continuation)
    assert note is not None
    assert "治疗期间" in note
    assert "本次入排审核不判定" in note
    assert _continuing_obligation_note(None) is None


@pytest.mark.parametrize("kind", ["event", "exposure"])
@pytest.mark.parametrize("stale", [None, "member", "fact"])
def test_non_clause_conflicts_preserved_without_fact_link_fanout(session, monkeypatch, kind, stale):
    from app.domain.contracts.enums import DurationStatus
    from app.services.patient_profile_service import PatientProfileService
    from app.services.eligibility_review_projection import EligibilityReviewProjectionError
    from tests.v2.services.test_fact_correction_job import _publish_event, _publish_exposure, _day
    from tests.v2.storage.test_fact_correction_repository import _seed_valid_chain

    chain = _seed_valid_chain(session, f"unassigned-{kind}-{stale}")
    fact = _publish_age_fact(session, chain, value=20, suffix="age")
    FactRuleLinkV2Repository(session).rebuild_for_authority(chain["authority"])
    before = EligibilityReviewProjectionService().project(session, chain["episode_id"])
    publish = _publish_event if kind == "event" else _publish_exposure
    members = [publish(session, chain, fact, suffix=str(index), start=_day(day),
                       duration=DurationStatus.ONGOING)
               for index, day in enumerate(["2026-01-01", "2026-03-01"])]
    ids = sorted(getattr(item, f"{kind}_id") for item in members)
    group = ClinicalConflictGroupV2Repository(session).create(ClinicalConflictGroupV2(
        conflict_group_id=f"{chain['run_id']}-conflict", run_id=members[0].run_id,
        gate_id=members[0].gate_id, authority=chain["authority"], member_kind=kind,
        **{f"{kind}_ids": ids}, locator_ids=[chain["locator_id"]], created_at=NOW,
    ))
    if stale == "member":
        method = "_published_events" if kind == "event" else "_published_exposures"
        monkeypatch.setattr(PatientProfileService, method, lambda *_: members[:1])
    if stale == "fact":
        _publish_superseding_age_fact(session, chain, base=fact, suffix="new-source")
    if stale:
        with pytest.raises(EligibilityReviewProjectionError, match="尚未完整衔接"):
            EligibilityReviewProjectionService().project(session, chain["episode_id"])
    else:
        after = EligibilityReviewProjectionService().project(session, chain["episode_id"])
        assert after.clauses == before.clauses
        assert len(after.unassigned_conflicts) == 1
        assert after.unassigned_conflicts[0].member_ids == tuple(ids)
        assert after.unassigned_conflicts[0].conflict_group_id == group.conflict_group_id
        assert after.unassigned_conflicts[0].member_kind == kind
    assert ClinicalConflictGroupV2Repository(session).get(group.conflict_group_id) == group


def test_projection_preserves_published_source_separately_from_summary(session_factory):
    from app.storage.repositories import get_rule_set
    from app.projections.clause_pack import project_clause_pack

    with session_factory() as session:
        chain = _seed_chain(session, "source-text")
        authority = chain["authority"]
        expected = project_clause_pack(get_rule_set(session, authority.rule_set_id, authority.rule_set_revision))
        result = EligibilityReviewProjectionService().project(session, authority.review_episode_id)
        by_id = {item.rule_component_id: item for item in expected.clauses}
        for item in result.clauses:
            assert item.source_text == by_id[item.rule_component_id].source_text
            assert item.text_summary == by_id[item.rule_component_id].title


def test_latest_expectations_reads_current_authority_once(monkeypatch):
    from app.services import eligibility_review_projection as projection

    current_authority = object()
    current = [SimpleNamespace(template_id="req-1", revision=1, authority=current_authority),
               SimpleNamespace(template_id="req-1", revision=2, authority=current_authority),
               SimpleNamespace(template_id="req-2", revision=1, authority=current_authority)]

    class Repository:
        def __init__(self, _session):
            pass

        def list_for_authority(self, authority):
            assert authority is current_authority
            return current

        def list_by_episode(self, _episode_id):
            pytest.fail("读取当前权威时不应扫描全体历史记录")

        def latest_by_template(self, _episode_id, _template_id):
            pytest.fail("同批已校验记录不应逐模板重读全库")

    monkeypatch.setattr(projection, "EvidenceExpectationV2Repository", Repository)
    assert [(item.template_id, item.revision) for item in projection._latest_expectations(
        object(), current_authority,
    )] == [("req-2", 1), ("req-1", 2)]


def _standalone_fact(*, fact_id: str, revision: int, authority: FactAuthority):
    date_range = PartialDateRange(
        source_text="2026-03-01",
        precision=DatePrecision.DAY,
        lower_bound=date(2026, 3, 1),
        upper_bound=date(2026, 3, 1),
    )
    stable_identity = clinical_fact_stable_identity(
        authority=authority,
        fact_type="demographics.age_years",
        asserted_object="年龄",
        polarity=FactPolarity.AFFIRMED,
        value=20,
        unit="岁",
        date_range=date_range,
    )
    return ClinicalFactV2(
        fact_id=fact_id,
        run_id="run",
        gate_id="gate",
        authority=authority,
        fact_type="demographics.age_years",
        supported_requirement_ids=["req-age"],
        polarity=FactPolarity.AFFIRMED,
        asserted_object="年龄",
        value=20,
        unit="岁",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        date_range=date_range,
        locator_ids=["locator"],
        assertion_basis=AssertionBasis(
            asserted_object="年龄",
            assertion_text="年龄 20 岁",
            locator_id="locator",
            source_text_sha256="0" * 64,
        ),
        stable_identity=stable_identity,
        revision=revision,
        created_at=NOW,
    )


def _publish_age_fact(session, chain, *, value: int, suffix: str) -> ClinicalFactV2:
    """用正式 V2 仓储发布一条可供 IN-01 求值的年龄事实。"""
    locator = session.get(EvidenceLocatorArtifactRecord, chain["locator_id"])
    assert locator is not None
    candidate_id = f"{chain['run_id']}-{suffix}-candidate"
    gate_id = f"{chain['run_id']}-{suffix}-gate"
    basis = AssertionBasis(
        asserted_object="年龄",
        assertion_text=f"年龄 {value} year",
        locator_id=chain["locator_id"],
        source_text_sha256=locator.source_text_sha256,
    )
    candidate = ClinicalFactCandidateV2(
        candidate_id=candidate_id,
        run_id=chain["run_id"],
        call_id=chain["call_id"],
        fact_type="demographics.age_years",
        supported_requirement_ids=["req-age"],
        polarity=FactPolarity.AFFIRMED,
        asserted_object="年龄",
        raw_value=value,
        canonical_value=value,
        unit="year",
        locator_ids=[chain["locator_id"]],
        record_time=NOW,
        candidate_source_semantics="objective_result",
        assertion_basis=basis,
        model_uncertainty=0.01,
        created_at=NOW,
    )
    FactNormalizationCandidateRepository(session).create(
        chain["call_id"], candidate
    )
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=gate_id,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            candidate_id=candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )
    authority = chain["authority"]
    fact = ClinicalFactV2(
        fact_id=f"{chain['run_id']}-{suffix}-fact",
        run_id=chain["run_id"],
        gate_id=gate_id,
        source_candidate_ids=[candidate_id],
        gate_ids=[gate_id],
        authority=authority,
        fact_type="demographics.age_years",
        supported_requirement_ids=["req-age"],
        polarity=FactPolarity.AFFIRMED,
        asserted_object="年龄",
        value=value,
        unit="year",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        record_time=NOW,
        locator_ids=[chain["locator_id"]],
        assertion_basis=basis,
        stable_identity=clinical_fact_stable_identity(
            authority=authority,
            fact_type="demographics.age_years",
            asserted_object="年龄",
            polarity=FactPolarity.AFFIRMED,
            value=value,
            unit="year",
            date_range=None,
        ),
        revision=1,
        created_at=NOW,
    )
    return ClinicalFactV2Repository(session).create(fact)


def _publish_superseding_age_fact(session, chain, *, base, suffix: str) -> ClinicalFactV2:
    """在同一稳定身份链上发布 revision+1 的取代事实（模拟人工修订）。"""
    candidate_id = f"{chain['run_id']}-{suffix}-candidate"
    FactNormalizationCandidateRepository(session).create(
        chain["call_id"],
        base.model_copy(update={
            "candidate_id": candidate_id,
            "raw_value": base.value,
            "canonical_value": base.value,
        }).model_copy(update={}) if False else ClinicalFactCandidateV2(
            candidate_id=candidate_id,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            fact_type="demographics.age_years",
            supported_requirement_ids=["req-age"],
            polarity=FactPolarity.AFFIRMED,
            asserted_object="年龄",
            raw_value=base.value,
            canonical_value=base.value,
            unit="year",
            locator_ids=[chain["locator_id"]],
            record_time=NOW,
            candidate_source_semantics="objective_result",
            assertion_basis=base.assertion_basis,
            model_uncertainty=0.01,
            created_at=NOW,
        ),
    )
    gate_id = f"{chain['run_id']}-{suffix}-gate"
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=gate_id,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            candidate_id=candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )
    return ClinicalFactV2Repository(session).create(
        base.model_copy(update={
            "fact_id": f"{chain['run_id']}-{suffix}-fact",
            "gate_id": gate_id,
            "source_candidate_ids": [candidate_id],
            "gate_ids": [gate_id],
            "revision": base.revision + 1,
        })
    )


def test_v2_adapter_preserves_fact_scope_and_locator_ids():
    authority = FactAuthority(
        project_id="project",
        subject_id="subject",
        review_episode_id="episode",
        episode_revision=1,
        protocol_version_id="protocol",
        rule_set_id="rules",
        rule_set_revision=1,
        evidence_snapshot_v2_id="snapshot",
        complete_processing_revision_id="complete",
    )
    fact = _standalone_fact(fact_id="fact-1", revision=1, authority=authority)
    adapted = adapt_clinical_fact_v2(fact)
    assert adapted.fact_id == fact.fact_id
    assert adapted.evidence_snapshot_id == authority.evidence_snapshot_v2_id
    assert adapted.evidence_span_ids == fact.locator_ids
    assert adapted.effective_date is not None
    assert adapted.effective_date.value == date(2026, 3, 1)


@pytest.mark.parametrize("value,polarity,expected", [
    (False, FactPolarity.NEGATED, "unknown"),
    (True, FactPolarity.NEGATED, "false"),
    (True, FactPolarity.AFFIRMED, "true"),
])
def test_real_v2_adapter_keeps_negative_history_and_consumer_does_not_double_invert(value, polarity, expected):
    from app.domain.contracts.rules import AtomicExpression, AtomicPredicate
    from app.domain.expression import EvaluationContext, evaluate_expression
    authority = FactAuthority(project_id="project", subject_id="subject", review_episode_id="episode",
        episode_revision=1, protocol_version_id="protocol", rule_set_id="rules", rule_set_revision=1,
        evidence_snapshot_v2_id="snapshot", complete_processing_revision_id="complete")
    fact = _standalone_fact(fact_id="fact-1", revision=1, authority=authority).model_copy(update={
        "fact_type": "history.condition", "value": value, "unit": None, "polarity": polarity})
    frozen = fact.model_dump_json()
    adapted = adapt_clinical_fact_v2(fact)
    context = EvaluationContext(project_id="project", subject_id="subject", review_episode_id="episode",
        evidence_snapshot_id="snapshot", accepted_fact_ids=[adapted.fact_id], facts=[adapted])
    result = evaluate_expression(AtomicExpression(predicate=AtomicPredicate(
        predicate_id="condition", subject="history", attribute="condition", comparator="eq", value=True)), context)
    assert result.truth.value == expected
    assert adapted.value is value and adapted.polarity == polarity
    assert fact.model_dump_json() == frozen


def test_fact_chain_heads_keep_highest_revision_and_adapter_sets_are_equal():
    authority = FactAuthority(
        project_id="project",
        subject_id="subject",
        review_episode_id="episode",
        episode_revision=1,
        protocol_version_id="protocol",
        rule_set_id="rules",
        rule_set_revision=1,
        evidence_snapshot_v2_id="snapshot",
        complete_processing_revision_id="complete",
    )
    first = _standalone_fact(fact_id="fact-r1", revision=1, authority=authority)
    second = _standalone_fact(fact_id="fact-r2", revision=2, authority=authority)
    heads = fold_fact_chain_heads([first, second])
    assert [fact.fact_id for fact in heads] == ["fact-r2"]
    adapted = [adapt_clinical_fact_v2(fact) for fact in heads]
    assert {fact.fact_id for fact in adapted} == {fact.fact_id for fact in heads}


def test_projection_without_published_fact_is_unknown_not_negative(session):
    chain = _seed_chain(session, "eligibility-no-fact")
    projection = EligibilityReviewProjectionService().project(session, chain["episode_id"])
    by_code = {item.rule_code: item for item in projection.clauses}
    # The fixture's investigator-judgment clause must stop at a gap, never become an
    # exclusion-not-triggered conclusion merely because no fact was published.
    assert by_code["EX-02"].decision == "indeterminate"
    assert by_code["EX-02"].gap_type == "observation_unverified"
    assert "资料尚未完成核实" in by_code["EX-02"].reason
    assert "未见" not in by_code["EX-02"].reason


@pytest.mark.parametrize("state", ["source_changed", "method_changed"])
def test_changed_source_or_method_is_visible_without_reusing_old_work_draft(session, monkeypatch, state):
    from app.services.eligibility_review_projection import _STALE_WORK_DRAFT, _STALE_METHOD_WORK_DRAFT
    from app.api.v2.eligibility_review import EligibilityReviewResponse

    chain = _seed_chain(session, "eligibility-source-changed")
    service = EligibilityReviewProjectionService(artifact_store=object())
    monkeypatch.setattr(
        service, "_completed_work_draft",
        lambda _session, *, authority, rule_set: (
            _STALE_WORK_DRAFT if state == "source_changed" else _STALE_METHOD_WORK_DRAFT),
    )
    projection = service.project(session, chain["episode_id"])
    assert projection.work_draft_state == state
    assert EligibilityReviewResponse.model_validate(projection.to_dict()).work_draft_state == state
    assert all(not clause.fact_refs for clause in projection.clauses)


@pytest.mark.parametrize(
    "age",
    [20, 17],
)
def test_projection_does_not_use_unqualified_age_fact(session, age: int):
    chain = _seed_chain(session, f"eligibility-age-{age}")
    fact = _publish_age_fact(session, chain, value=age, suffix="age")

    from tests.v2.storage.test_repositories_roundtrip import FIXTURES
    from app.projections.evidence_expectation_templates import project_evidence_expectation_templates
    from app.storage.repositories import save_expectation_templates
    from app.services.evidence_expectation_projection_service import EvidenceExpectationProjectionService

    fixture = FIXTURES[0]
    from app.storage.codecs import encode_contract
    from app.storage.models import WorkflowStageRecord, ReviewEpisodeRecord
    from tests.v2.services.test_fact_normalization_persistence import _update_episode

    stages = []
    for stage in fixture.workflow_stages:
        stage = stage.model_copy(update={
            "workflow_stage_id": f"{fixture.rule_set.rule_set_id}:{fixture.rule_set.revision}:{stage.workflow_stage_id}",
        })
        payload, digest = encode_contract(stage)
        session.add(WorkflowStageRecord(
            workflow_stage_id=stage.workflow_stage_id,
            protocol_version_id=chain["protocol_version_id"], stage=stage.stage.value,
            study_phase=fixture.rule_set.study_phase.value,
            payload_json=payload, payload_sha256=digest, created_at=NOW,
        ))
        stages.append(stage)
    session.flush()
    _update_episode(
        session, session.get(ReviewEpisodeRecord, chain["episode_id"]),
        workflow_stage_id=next(s.workflow_stage_id for s in stages if "req-age" in s.due_requirement_ids),
    )
    templates = project_evidence_expectation_templates(
        rule_set=fixture.rule_set, workflow_stages=stages, created_at=NOW,
    )
    save_expectation_templates(session, templates)
    age_templates = {t.template_id for t in templates if t.requirement_id == "req-age"}
    assert age_templates
    expectations = EvidenceExpectationProjectionService().project(
        session, authority=chain["authority"], gap_signals=[], created_at=NOW,
        template_ids=age_templates,
    )
    assert len(expectations) == 1

    projection = EligibilityReviewProjectionService().project(
        session, chain["episode_id"]
    )
    clause = next(item for item in projection.clauses if item.rule_code == "IN-01")

    assert clause.decision == "indeterminate"
    assert clause.determination_mode == "deterministic"
    assert clause.gap_type == "observation_unverified"
    assert clause.fact_refs == ()
    assert fact.fact_id not in {
        item.fact_id for item in clause.fact_refs
    }


def test_published_fact_without_requirement_coverage_is_not_professional_judgment(session):
    chain = _seed_chain(session, "age-without-coverage")
    _publish_age_fact(session, chain, value=20, suffix="age")
    projection = EligibilityReviewProjectionService().project(session, chain["episode_id"])
    clause = next(item for item in projection.clauses if item.rule_code == "IN-01")
    assert clause.decision == "indeterminate"
    assert clause.gap_type == "observation_unverified"


def test_withdrawn_latest_fact_does_not_restore_older_evidence(session, monkeypatch):
    from app.storage.fact_correction_repository import FactCorrectionRepository

    chain = _seed_chain(session, "withdrawn-latest")
    older = _publish_age_fact(session, chain, value=20, suffix="older")
    latest = _publish_superseding_age_fact(session, chain, base=older, suffix="latest")
    # Correction persistence is tested by its repository; exercise the real review
    # pipeline with its authoritative exclusion result, not a prefiltered fact list.
    monkeypatch.setattr(
        FactCorrectionRepository, "superseded_entity_ids",
        lambda self, authority: {latest.fact_id},
    )
    projection = EligibilityReviewProjectionService().project(session, chain["episode_id"])
    used = {ref.fact_id for clause in projection.clauses for ref in clause.fact_refs}
    assert older.fact_id not in used
    assert latest.fact_id not in used


def test_projection_marks_future_clause_not_due_and_missing_judgment_summary(
    session,
):
    chain = _seed_chain(session, "eligibility-gaps")
    projection = EligibilityReviewProjectionService().project(
        session, chain["episode_id"]
    )
    by_code = {item.rule_code: item for item in projection.clauses}

    assert by_code["EX-02"].decision == "indeterminate"
    assert by_code["EX-02"].gap_type == "observation_unverified"
    assert "尚未完成" in by_code["EX-02"].reason
    assert "未见" not in by_code["EX-02"].reason
    assert "需先核对本次提交的原件" in by_code["EX-02"].reason
    assert by_code["EX-03"].decision == "not_due"
    assert by_code["EX-03"].gap_type == "future_stage_not_due"
    assert "不在本次节点到期" in by_code["EX-03"].reason


def test_projection_passes_missing_source_state_to_summary_composition(session, monkeypatch):
    from app.domain.contracts.enums import ExpectationStatus, GapType
    from app.domain.contracts.judgment_search import (
        JudgmentSearchCoverageStatus, JudgmentSearchCoverageSummary,
    )
    from app.domain.gates.assessment import RequirementGapState
    from app.services import eligibility_review_projection as module
    from app.storage.judgment_search_repository import JudgmentSearchSummaryRepository

    chain = _seed_chain(session, "judgment-missing-source")
    # Repository/expectation validation is covered separately. Exercise the full
    # projection wiring with explicit, conflicting supplied-scope inputs.
    monkeypatch.setattr(module, "_expectation_views", lambda *_: [
        RequirementGapState("req-professional", ExpectationStatus.ABSENT,
                            GapType.REFERENCED_FILE_MISSING),
    ])
    monkeypatch.setattr(JudgmentSearchSummaryRepository, "latest_for_authority", lambda *_: {
        "req-professional": JudgmentSearchCoverageSummary(
            scope_sha256="a" * 64, requirement_id="req-professional",
            status=JudgmentSearchCoverageStatus.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE,
        ),
    })
    projection = EligibilityReviewProjectionService().project(session, chain["episode_id"])
    clause = next(item for item in projection.clauses if item.rule_code == "EX-02")
    assert clause.gap_type == "referenced_file_missing"
    assert clause.decision == "indeterminate"
    assert "该文件未在本次提交中提供" in clause.reason


def test_projection_reverses_conflict_members_to_component(session):
    chain = _seed_chain(session, "eligibility-conflict")
    first = _publish_age_fact(session, chain, value=20, suffix="first")
    second = _publish_age_fact(session, chain, value=17, suffix="second")
    member_ids = sorted((first.fact_id, second.fact_id))
    FactRuleLinkV2Repository(session).rebuild_for_authority(chain["authority"])
    ClinicalConflictGroupV2Repository(session).create(
        ClinicalConflictGroupV2(
            conflict_group_id=f"{chain['run_id']}-age-conflict",
            run_id=chain["run_id"],
            gate_id=first.gate_id,
            authority=chain["authority"],
            member_kind="fact",
            fact_ids=member_ids,
            locator_ids=[chain["locator_id"]],
            created_at=NOW,
        )
    )

    projection = EligibilityReviewProjectionService().project(
        session, chain["episode_id"]
    )
    clause = next(item for item in projection.clauses if item.rule_code == "IN-01")

    assert clause.decision == "conflict"
    assert clause.gap_type == "source_conflict"
    assert "相互冲突" in clause.reason


def test_projection_rejects_mixed_revision_conflict_without_successor(session):
    """同身份新事实不能替代明确的冲突来源修订。"""
    chain = _seed_chain(session, "eligibility-mixed-conflict")
    first = _publish_age_fact(session, chain, value=20, suffix="first")
    second = _publish_age_fact(session, chain, value=17, suffix="second")
    third = _publish_superseding_age_fact(session, chain, base=second, suffix="third")
    FactRuleLinkV2Repository(session).rebuild_for_authority(chain["authority"])
    ClinicalConflictGroupV2Repository(session).create(
        ClinicalConflictGroupV2(
            conflict_group_id=f"{chain['run_id']}-age-mixed",
            run_id=chain["run_id"],
            gate_id=first.gate_id,
            authority=chain["authority"],
            member_kind="fact",
            fact_ids=sorted((first.fact_id, second.fact_id)),
            locator_ids=[chain["locator_id"]],
            created_at=NOW,
        )
    )

    from app.services.eligibility_review_projection import EligibilityReviewProjectionError
    with pytest.raises(EligibilityReviewProjectionError, match="尚未完整衔接"):
        EligibilityReviewProjectionService().project(session, chain["episode_id"])


def test_projection_rejects_all_stale_conflict_members_without_successor(session):
    """全部成员已有新版本不等于原冲突已经解决。"""
    chain = _seed_chain(session, "eligibility-dead-conflict")
    first = _publish_age_fact(session, chain, value=20, suffix="first")
    second = _publish_age_fact(session, chain, value=17, suffix="second")
    third = _publish_superseding_age_fact(session, chain, base=second, suffix="third")
    _publish_superseding_age_fact(session, chain, base=first, suffix="first-v2")
    FactRuleLinkV2Repository(session).rebuild_for_authority(chain["authority"])
    ClinicalConflictGroupV2Repository(session).create(
        ClinicalConflictGroupV2(
            conflict_group_id=f"{chain['run_id']}-age-dead",
            run_id=chain["run_id"],
            gate_id=first.gate_id,
            authority=chain["authority"],
            member_kind="fact",
            # 没有冲突后继记录，不能隐式转到新事实。
            fact_ids=sorted((first.fact_id, second.fact_id)),
            locator_ids=[chain["locator_id"]],
            created_at=NOW,
        )
    )

    from app.services.eligibility_review_projection import EligibilityReviewProjectionError
    with pytest.raises(EligibilityReviewProjectionError, match="尚未完整衔接"):
        EligibilityReviewProjectionService().project(session, chain["episode_id"])
