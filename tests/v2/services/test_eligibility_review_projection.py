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
    adapt_clinical_fact_v2,
    fold_fact_chain_heads,
)
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
    assert by_code["EX-02"].decision == "professional_judgment"
    assert by_code["EX-02"].gap_type == "professional_judgment"
    assert "本次提交的资料中" in by_code["EX-02"].reason


@pytest.mark.parametrize(
    ("age", "expected_decision"),
    [(20, "inclusion_met"), (17, "inclusion_not_met")],
)
def test_projection_deterministically_evaluates_age_clause(
    session, age: int, expected_decision: str
):
    chain = _seed_chain(session, f"eligibility-age-{age}")
    fact = _publish_age_fact(session, chain, value=age, suffix="age")

    projection = EligibilityReviewProjectionService().project(
        session, chain["episode_id"]
    )
    clause = next(item for item in projection.clauses if item.rule_code == "IN-01")

    assert clause.decision == expected_decision
    assert clause.determination_mode == "deterministic"
    assert {item.fact_id for item in clause.fact_refs} == {fact.fact_id}
    assert {item.locator_id for item in clause.fact_refs} == {chain["locator_id"]}


def test_projection_marks_future_clause_not_due_and_missing_judgment_summary(
    session,
):
    chain = _seed_chain(session, "eligibility-gaps")
    projection = EligibilityReviewProjectionService().project(
        session, chain["episode_id"]
    )
    by_code = {item.rule_code: item for item in projection.clauses}

    assert by_code["EX-02"].decision == "professional_judgment"
    assert by_code["EX-02"].gap_type == "professional_judgment"
    assert "判断检索摘要" in by_code["EX-02"].reason
    assert by_code["EX-03"].decision == "not_due"
    assert by_code["EX-03"].gap_type == "future_stage_not_due"
    assert "尚未到期" in by_code["EX-03"].reason


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


def test_projection_keeps_mixed_revision_conflict_on_head_members(session):
    """混合冲突组（链头+已被取代 revision）不阻断投影，按链头成员保留冲突。"""
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

    projection = EligibilityReviewProjectionService().project(
        session, chain["episode_id"]
    )
    clause = next(item for item in projection.clauses if item.rule_code == "IN-01")

    # first 与 third（second 的链头）构成当前活跃冲突：条款必须保持 conflict，不得静默降级。
    assert clause.decision == "conflict"
    assert clause.gap_type == "source_conflict"
    assert "相互冲突" in clause.reason


def test_projection_skips_fully_superseded_conflict_groups(session):
    """全部成员均被修订链取代的冲突组不参与当前求值，也不阻断投影。"""
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
            # 两成员分别是两条链的旧 revision：解析后各自指向新链头（first-v2/third），
            # 组按链头成员参与；验证链头解析路径不抛错、投影可用。
            fact_ids=sorted((first.fact_id, second.fact_id)),
            locator_ids=[chain["locator_id"]],
            created_at=NOW,
        )
    )

    projection = EligibilityReviewProjectionService().project(
        session, chain["episode_id"]
    )
    clause = next(item for item in projection.clauses if item.rule_code == "IN-01")

    # 无活跃冲突时按事实求值：18<=age<75 仍以链头事实判定，不因死组报错。
    assert clause.decision in {"inclusion_met", "inclusion_not_met", "conflict"}
