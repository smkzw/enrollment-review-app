"""Phase 5 Patient Profile 投影服务测试（Slice 5.5，worker_02）。

覆盖：从当前权威元组已发布 v2 实体生成 ``succeeded`` 完整投影（13 条泳道、条目
定位/来源修订保真、首屏突出、待核对数、审核阶段）；泳道归属只来自已发布
``profile_lane``（事实/事件按解码字段归类，绝不再分类或默认归属）；只读同一权威
元组（其他节点/旧权威实体排除）；同稳定身份取链头（合并事实只出现一次）；同内容
重生成幂等复用、新内容追加链头 +1；generating/failed 显式状态记录；对照当前审核
节点权威派生 ``stale``（不改写历史行）；链头折叠后引用闭包校验（事件/暴露引用旧
事实 revision、冲突引用旧成员、期望覆盖旧事实一律拒绝）；缺失审核节点上下文时
读取派生大声失败而非返回成功；Profile 不读取 fixture/旧事实。

旧 ``patient_profiles`` 占位表不进入本读取路径。
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.domain.contracts.enums import (
    DurationStatus,
    ExpectationStatus,
    FactGate,
    FactPolarity,
    GapType,
    GateOutcome,
    ProfileLane,
    ReviewStage,
)
from app.domain.contracts.evidence_expectations_v2 import EvidenceExpectationV2
from app.domain.contracts.facts import (
    ClinicalConflictGroupV2,
    ClinicalEventCandidateV2,
    ClinicalFactCandidateV2,
    FactGateResult,
    MedicationExposureCandidateV2,
)
from app.domain.contracts.patient_profile_v2 import (
    PROFILE_LANE_ORDER,
    ProfileHighlightReason,
    ProfileItemKind,
    ProfileStatus,
    profile_items,
)
from app.services.patient_profile_service import (
    PatientProfileProjectionError,
    PatientProfileService,
)
from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
from app.storage.fact_repositories import (
    ClinicalConflictGroupV2Repository,
    ClinicalEventV2Repository,
    ClinicalFactV2Repository,
    FactGateResultRepository,
    FactNormalizationCandidateRepository,
    MedicationExposureV2Repository,
)
from app.storage.facts_models import PatientProfileRevisionV2Record
from app.storage.models import ReviewEpisodeRecord
from app.storage.repositories import EpisodeRepository, NotFoundError
from tests.v2.projections.test_evidence_expectations import _template
from tests.v2.storage.test_fact_repositories import (
    _authority,
    _basis,
    _create_and_assert_fact_conflict_group,
    _date_range,
    _event,
    _exposure,
    _fact,
    _seed_chain,
    _update_episode,
)

NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def chain(session):
    return _seed_chain(session, "svc")


@pytest.fixture
def chain_other(session):
    return _seed_chain(session, "svc2", fixture_index=1)


def _rows(session) -> list[PatientProfileRevisionV2Record]:
    return session.execute(select(PatientProfileRevisionV2Record)).scalars().all()


# ------------------------------------------------------- 悬挂引用测试发布助手
# 通过正式仓储发布自建候选/门禁的实体，制造“引用旧事实 revision”的确定性悬挂场景。


def _publish_with_candidate(session, chain, candidate, gate_id) -> None:
    FactNormalizationCandidateRepository(session).create(chain["call_id"], candidate)
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=gate_id,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            candidate_id=candidate.candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )


def _fact_via_candidate(
    session, chain, fact_id, *, value="120/80", supported_requirement_ids=(), revision=1
):
    candidate = ClinicalFactCandidateV2(
        candidate_id=f"cc-{fact_id}-cand",
        run_id=chain["run_id"],
        call_id=chain["call_id"],
        fact_type="vital_sign",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="血压",
        raw_value=value,
        canonical_value=value,
        unit="unitless",
        date_range=_date_range(),
        record_time=NOW,
        locator_ids=[chain["locator_id"]],
        candidate_source_semantics="objective_result",
        assertion_basis=_basis(chain["locator_id"]),
        supported_requirement_ids=list(supported_requirement_ids),
        model_uncertainty=0.01,
        created_at=NOW,
    )
    _publish_with_candidate(session, chain, candidate, f"cc-{fact_id}-gate")
    return ClinicalFactV2Repository(session).create(
        _fact(
            chain,
            fact_id=fact_id,
            gate_id=f"cc-{fact_id}-gate",
            value=value,
            revision=revision,
            source_candidate_ids=[candidate.candidate_id],
            gate_ids=[f"cc-{fact_id}-gate"],
            supported_requirement_ids=list(supported_requirement_ids),
        )
    )
def _event_via_candidate(session, chain, event_id, *, fact_candidate_ids, fact_ids):
    candidate = ClinicalEventCandidateV2(
        candidate_id=f"cc-{event_id}-cand",
        run_id=chain["run_id"],
        call_id=chain["call_id"],
        event_type="diagnosis",
        start_range=_date_range(),
        end_range=None,
        duration_status=DurationStatus.ONGOING,
        record_time=NOW,
        fact_candidate_ids=sorted(set(fact_candidate_ids)),
        locator_ids=[chain["locator_id"]],
        candidate_source_semantics="historical_primary",
        model_uncertainty=0.02,
        created_at=NOW,
    )
    _publish_with_candidate(session, chain, candidate, f"cc-{event_id}-gate")
    return ClinicalEventV2Repository(session).create(
        _event(
            chain,
            event_id=event_id,
            gate_id=f"cc-{event_id}-gate",
            fact_ids=sorted(set(fact_ids)),
            referenced_fact_objects=["vital_sign:血压"],
            source_candidate_ids=[candidate.candidate_id],
            gate_ids=[f"cc-{event_id}-gate"],
        )
    )


def _exposure_via_candidate(session, chain, exposure_id, *, fact_candidate_ids, fact_ids):
    candidate = MedicationExposureCandidateV2(
        candidate_id=f"cc-{exposure_id}-cand",
        run_id=chain["run_id"],
        call_id=chain["call_id"],
        medication_name="二甲双胍",
        category="降糖药",
        indication="2 型糖尿病",
        dose="500",
        unit="mg",
        frequency="bid",
        route="口服",
        start_range=_date_range(),
        end_range=None,
        duration_status=DurationStatus.ONGOING,
        record_time=NOW,
        fact_candidate_ids=sorted(set(fact_candidate_ids)),
        locator_ids=[chain["locator_id"]],
        candidate_source_semantics="current_chart",
        model_uncertainty=0.03,
        created_at=NOW,
    )
    _publish_with_candidate(session, chain, candidate, f"cc-{exposure_id}-gate")
    return MedicationExposureV2Repository(session).create(
        _exposure(
            chain,
            exposure_id=exposure_id,
            gate_id=f"cc-{exposure_id}-gate",
            fact_ids=sorted(set(fact_ids)),
            source_candidate_ids=[candidate.candidate_id],
            gate_ids=[f"cc-{exposure_id}-gate"],
        )
    )


# ------------------------------------------------------------------ 生成


def test_generate_builds_complete_profile_from_published_entities(chain, session):
    ClinicalFactV2Repository(session).create(
        _fact(chain, profile_lane=ProfileLane.TARGET_DISEASE)
    )
    ClinicalEventV2Repository(session).create(
        _event(chain, profile_lane=ProfileLane.SPECIAL_HISTORY)
    )
    MedicationExposureV2Repository(session).create(_exposure(chain))

    revision = PatientProfileService().generate(session, authority=_authority(chain))
    assert revision.status == ProfileStatus.SUCCEEDED
    assert revision.revision == 1
    episode = EpisodeRepository(session).get(chain["review_episode_id"])
    assert revision.review_stage == episode.stage
    assert [section.lane for section in revision.lanes] == list(PROFILE_LANE_ORDER)

    items = profile_items(revision)
    by_id = {item.source_id: item for item in items}
    fact_id = f"{chain['run_id']}-fact"
    assert by_id[fact_id].lane == ProfileLane.TARGET_DISEASE
    assert by_id[fact_id].source_revision == 1
    assert by_id[fact_id].locator_ids == [chain["locator_id"]]
    event_id = f"{chain['run_id']}-event"
    assert by_id[event_id].lane == ProfileLane.SPECIAL_HISTORY
    assert by_id[event_id].fact_ids == [fact_id]
    exposure_id = f"{chain['run_id']}-exposure"
    assert by_id[exposure_id].lane == ProfileLane.MEDICATION
    assert revision.pending_review_count == 0
    assert revision.highlights == []


def test_lane_assignments_come_only_from_published_profile_lane(chain, session):
    repo = ClinicalFactV2Repository(session)
    repo.create(
        _fact(chain, fact_id="lane-fact-a", profile_lane=ProfileLane.TEST_EXAM_SCORE)
    )
    repo.create(
        _fact(chain, fact_id="lane-fact-b", profile_lane=ProfileLane.DEMOGRAPHICS)
    )
    revision = PatientProfileService().generate(session, authority=_authority(chain))
    items = profile_items(revision)
    by_id = {item.source_id: item for item in items}
    assert by_id["lane-fact-a"].lane == ProfileLane.TEST_EXAM_SCORE
    assert by_id["lane-fact-b"].lane == ProfileLane.DEMOGRAPHICS
    # 服务绝不把已发布泳道重新分类或落到默认泳道。
    assert by_id["lane-fact-a"].lane != ProfileLane.EVIDENCE_QUALITY


def test_generate_reads_only_same_authority_entities(chain, chain_other, session):
    ClinicalFactV2Repository(session).create(
        _fact(chain, fact_id="auth-fact-a", profile_lane=ProfileLane.TARGET_DISEASE)
    )
    ClinicalFactV2Repository(session).create(
        _fact(chain_other, fact_id="auth-fact-b", profile_lane=ProfileLane.DEMOGRAPHICS)
    )
    revision = PatientProfileService().generate(session, authority=_authority(chain))
    source_ids = {item.source_id for item in profile_items(revision)}
    assert "auth-fact-a" in source_ids
    assert "auth-fact-b" not in source_ids


def test_merged_fact_chain_head_appears_once(chain, session):
    repo = ClinicalFactV2Repository(session)
    first = repo.create(_fact(chain, fact_id="merged-fact-v1"))
    second = repo.create(_fact(chain, fact_id="merged-fact-v2", revision=2))
    assert first.stable_identity == second.stable_identity

    revision = PatientProfileService().generate(session, authority=_authority(chain))
    fact_items = [
        item for item in profile_items(revision) if item.kind == ProfileItemKind.FACT
    ]
    assert len(fact_items) == 1
    assert fact_items[0].source_id == "merged-fact-v2"
    assert fact_items[0].source_revision == 2


def test_run_filter_cannot_hide_unresolved_historical_references(
    chain, session, monkeypatch
):
    """换run不能掩盖旧事件悬挂引用，须先修复引用而不是省略事件。"""
    old_fact = _fact(chain, fact_id="rerun-fact-v1")
    old_event = _event(
        chain,
        event_id="rerun-event-v1",
        fact_ids=[old_fact.fact_id],
    )
    current_run_id = f"{chain['run_id']}-current"
    current_fact = _fact(
        {**chain, "run_id": current_run_id},
        fact_id="rerun-fact-v2",
        revision=2,
    )

    monkeypatch.setattr(
        ClinicalFactV2Repository,
        "list_by_episode",
        lambda self, _episode_id: [old_fact, current_fact],
    )
    monkeypatch.setattr(
        ClinicalEventV2Repository,
        "list_by_episode",
        lambda self, _episode_id: [old_event],
    )
    monkeypatch.setattr(
        MedicationExposureV2Repository,
        "list_by_episode",
        lambda self, _episode_id: [],
    )
    monkeypatch.setattr(
        ClinicalConflictGroupV2Repository,
        "list_by_episode",
        lambda self, _episode_id: [],
    )

    service = PatientProfileService()
    with pytest.raises(PatientProfileProjectionError, match="引用已折叠链头之外"):
        service.generate(session, authority=_authority(chain))

    with pytest.raises(PatientProfileProjectionError, match="引用已折叠链头之外"):
        service.generate(
            session,
            authority=_authority(chain),
            run_id=current_run_id,
        )


def test_incremental_profile_keeps_previous_facts_events_and_exposures(
    chain, session, monkeypatch
):
    old = _fact(chain, fact_id="earlier-fact")
    added = _fact(
        {**chain, "run_id": "supplemental-run"},
        fact_id="additional-fact", value="130/85",
    )
    event = _event(chain, event_id="earlier-event", fact_ids=[old.fact_id])
    exposure = _exposure(chain, exposure_id="earlier-exposure", fact_ids=[old.fact_id])
    monkeypatch.setattr(ClinicalFactV2Repository, "list_by_episode", lambda *_: [old, added])
    monkeypatch.setattr(ClinicalEventV2Repository, "list_by_episode", lambda *_: [event])
    monkeypatch.setattr(MedicationExposureV2Repository, "list_by_episode", lambda *_: [exposure])
    monkeypatch.setattr(ClinicalConflictGroupV2Repository, "list_by_episode", lambda *_: [])
    revision = PatientProfileService().generate(
        session, authority=old.authority, run_id=added.run_id,
    )
    assert {item.source_id for item in profile_items(revision)} == {
        old.fact_id, added.fact_id, event.event_id, exposure.exposure_id,
    }


@pytest.mark.parametrize("kind", ["event", "exposure"])
def test_corrected_event_or_exposure_does_not_revive_old_revision(
    chain, session, monkeypatch, kind
):
    import app.services.patient_profile_service as module

    factory = _event if kind == "event" else _exposure
    identifier = f"{kind}_id"
    old = factory(chain, **{identifier: "old", "revision": 1})
    head = factory(chain, **{identifier: "head", "revision": 2})
    repository = ClinicalEventV2Repository if kind == "event" else MedicationExposureV2Repository
    monkeypatch.setattr(repository, "list_by_episode", lambda *_: [old, head])
    monkeypatch.setattr(module, "_superseded_ids", lambda *_: {"head"})
    service = PatientProfileService()
    read = service._published_events if kind == "event" else service._published_exposures
    assert read(session, old.authority) == []


def test_regenerate_identical_content_is_idempotent(chain, session):
    ClinicalFactV2Repository(session).create(
        _fact(chain, profile_lane=ProfileLane.TARGET_DISEASE)
    )
    service = PatientProfileService()
    first = service.generate(session, authority=_authority(chain))
    second = service.generate(session, authority=_authority(chain))
    assert second.patient_profile_revision_id == first.patient_profile_revision_id
    assert second.revision == 1
    assert len(_rows(session)) == 1


def test_new_content_appends_chain_head(chain, session):
    repo = ClinicalFactV2Repository(session)
    repo.create(_fact(chain, fact_id="grow-a", profile_lane=ProfileLane.TARGET_DISEASE))
    service = PatientProfileService()
    first = service.generate(session, authority=_authority(chain))
    assert first.revision == 1

    repo.create(
        _fact(chain, fact_id="grow-b", profile_lane=ProfileLane.MEDICAL_HISTORY)
    )
    second = service.generate(session, authority=_authority(chain))
    assert second.revision == 2
    assert {item.source_id for item in profile_items(second)} >= {"grow-a", "grow-b"}
    history = service.history(session, chain["review_episode_id"])
    assert [item.revision for item in history] == [1, 2]


# ------------------------------------------------------------------ 状态记录


def test_status_records_and_generation_flow(chain, session):
    service = PatientProfileService()
    authority = _authority(chain)
    generating = service.record_status(
        session, authority=authority, status=ProfileStatus.GENERATING
    )
    assert generating.status == ProfileStatus.GENERATING
    assert generating.lanes == []
    assert generating.generated_at is None

    failed = service.record_status(
        session, authority=authority, status=ProfileStatus.FAILED
    )
    assert failed.status == ProfileStatus.FAILED

    ClinicalFactV2Repository(session).create(
        _fact(chain, profile_lane=ProfileLane.DEMOGRAPHICS)
    )
    succeeded = service.generate(session, authority=authority)
    assert succeeded.status == ProfileStatus.SUCCEEDED
    assert succeeded.revision == 3
    assert [item.revision for item in service.history(session, chain["review_episode_id"])] == [1, 2, 3]


def test_record_status_rejects_success_status(chain, session):
    with pytest.raises(PatientProfileProjectionError, match="显式状态记录"):
        PatientProfileService().record_status(
            session,
            authority=_authority(chain),
            status=ProfileStatus.SUCCEEDED,
        )


# ------------------------------------------------------------------ stale 派生


def test_stale_derived_after_authority_change_without_mutation(chain, session):
    ClinicalFactV2Repository(session).create(
        _fact(chain, profile_lane=ProfileLane.TARGET_DISEASE)
    )
    service = PatientProfileService()
    revision = service.generate(session, authority=_authority(chain))
    assert (
        service.latest(session, chain["review_episode_id"]).status
        == ProfileStatus.SUCCEEDED
    )

    episode = session.get(ReviewEpisodeRecord, chain["review_episode_id"])
    _update_episode(session, episode, revision=2)
    session.flush()

    stale = service.latest(session, chain["review_episode_id"])
    assert stale.status == ProfileStatus.STALE
    assert [item.status for item in service.history(session, chain["review_episode_id"])] == [
        ProfileStatus.STALE
    ]
    # 历史行未被改写：仓储读取仍是 succeeded。
    persisted = service.get(session, revision.patient_profile_revision_id)
    assert persisted.status == ProfileStatus.SUCCEEDED


# ------------------------------------------------------------------ 突出


def test_highlights_include_conflict_and_expectation_gap(chain, session):
    _create_and_assert_fact_conflict_group(chain, session)
    template = _template(
        session,
        chain,
        requirement_id="req",
        fact_type="vital_sign",
        due_stage=ReviewStage.SCREENING,
    )
    expectation = EvidenceExpectationV2(
        expectation_id=f"{chain['run_id']}-exp-absent",
        authority=_authority(chain),
        template_id=template.template_id,
        status=ExpectationStatus.ABSENT,
        gap_type=GapType.RECORD_INCOMPLETE,
        gap_detail="病历记录不完整",
        revision=1,
        locator_ids=[],
        coverage_fact_ids=[],
        source_coverage="none",
        created_at=NOW,
    )
    EvidenceExpectationV2Repository(session).project(expectation)

    revision = PatientProfileService().generate(session, authority=_authority(chain))
    assert revision.status == ProfileStatus.SUCCEEDED
    kinds = {item.kind for item in profile_items(revision)}
    assert ProfileItemKind.CONFLICT in kinds
    assert ProfileItemKind.EXPECTATION in kinds
    reasons = {reason for highlight in revision.highlights for reason in highlight.reasons}
    assert ProfileHighlightReason.UNRESOLVED_CONFLICT in reasons
    assert ProfileHighlightReason.CURRENT_DUE_EXPECTATION_GAP in reasons
    assert revision.pending_review_count == len(revision.highlights) == 2


# ------------------------------------------------------------------ 错误与空


def test_generate_rejects_episode_scope_mismatch(chain, session):
    ClinicalFactV2Repository(session).create(
        _fact(chain, profile_lane=ProfileLane.DEMOGRAPHICS)
    )
    authority = _authority(chain, project_id="foreign-project")
    with pytest.raises(PatientProfileProjectionError, match="不一致"):
        PatientProfileService().generate(session, authority=authority)


# ------------------------------------------------------------------ 引用闭包


@pytest.mark.parametrize("kind", ["event", "exposure", "conflict", "expectation"])
def test_generate_rejects_dangling_typed_references(session, kind):
    """链头折叠后事件/暴露/冲突/期望引用旧事实 revision 一律拒绝，绝不静默并入。"""
    chain = _seed_chain(session, f"dangle-{kind}")
    if kind == "expectation":
        template = _template(
            session,
            chain,
            requirement_id="req",
            fact_type="vital_sign",
            due_stage=ReviewStage.SCREENING,
        )
        v1 = _fact_via_candidate(
            session, chain, "dangle-fact-v1",
            supported_requirement_ids=[template.requirement_id],
        )
        v2 = _fact_via_candidate(
            session, chain, "dangle-fact-v2", revision=2
        )
    else:
        v1 = _fact_via_candidate(session, chain, "dangle-fact-v1")
        v2 = _fact_via_candidate(session, chain, "dangle-fact-v2", revision=2)
    assert v1.stable_identity == v2.stable_identity

    if kind == "event":
        _event_via_candidate(
            session, chain, "dangle-event",
            fact_candidate_ids=["cc-dangle-fact-v1-cand"],
            fact_ids=["dangle-fact-v1"],
        )
    elif kind == "exposure":
        _exposure_via_candidate(
            session, chain, "dangle-exposure",
            fact_candidate_ids=["cc-dangle-fact-v1-cand"],
            fact_ids=["dangle-fact-v1"],
        )
    elif kind == "conflict":
        _fact_via_candidate(session, chain, "dangle-other", value="90/60")
        ClinicalConflictGroupV2Repository(session).create(
            ClinicalConflictGroupV2(
                conflict_group_id="dangle-conflict",
                run_id=chain["run_id"],
                gate_id="cc-dangle-fact-v1-gate",
                authority=_authority(chain),
                fact_ids=["dangle-fact-v1", "dangle-other"],
                locator_ids=[chain["locator_id"]],
                created_at=NOW,
            )
        )
    else:  # expectation
        EvidenceExpectationV2Repository(session).project(
            EvidenceExpectationV2(
                expectation_id="dangle-exp",
                authority=_authority(chain),
                template_id=template.template_id,
                status=ExpectationStatus.OBSERVED,
                revision=1,
                locator_ids=[chain["locator_id"]],
                coverage_fact_ids=["dangle-fact-v1"],
                source_coverage="complete",
                created_at=NOW,
            )
        )

    label = {"event": "事件", "exposure": "暴露", "conflict": "冲突",
             "expectation": "期望"}[kind]
    with pytest.raises(PatientProfileProjectionError, match=label):
        PatientProfileService().generate(session, authority=_authority(chain))


# ------------------------------------------------------------------ stale 派生失败


def test_stale_derivation_requires_current_episode(chain, session, monkeypatch):
    """缺失审核节点上下文不是当前成功的证明：读取派生必须大声失败。"""
    ClinicalFactV2Repository(session).create(
        _fact(chain, profile_lane=ProfileLane.TARGET_DISEASE)
    )
    service = PatientProfileService()
    service.generate(session, authority=_authority(chain))

    class MissingEpisodeRepository:
        def __init__(self, session):
            pass

        def get(self, review_episode_id):
            raise NotFoundError(f"审核节点 {review_episode_id} 不存在")

    monkeypatch.setattr(
        "app.services.patient_profile_service.EpisodeRepository",
        MissingEpisodeRepository,
    )
    with pytest.raises(PatientProfileProjectionError, match="无法读取审核节点"):
        service.latest(session, chain["review_episode_id"])
    with pytest.raises(PatientProfileProjectionError, match="无法读取审核节点"):
        service.history(session, chain["review_episode_id"])

def test_latest_and_history_for_missing_episode(chain, session):
    service = PatientProfileService()
    assert service.latest(session, "no-such-episode") is None
    assert service.history(session, "no-such-episode") == []
