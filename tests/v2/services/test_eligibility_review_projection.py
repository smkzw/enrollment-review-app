"""入排审核只读投影的确定性与医学安全边界测试。"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.domain.contracts.enums import (
    DatePrecision,
    FactGate,
    FactPolarity,
    GateOutcome,
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
    _continuing_obligation_note,
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
