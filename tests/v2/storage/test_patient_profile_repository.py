"""Phase 5 不可变 Patient Profile revision 仓储测试（Slice 5.5，worker_02）。

覆盖：权威元组复核（陈旧节点修订拒绝）；``(review_episode_id, revision)`` 追加写
（首条必须 1、链头 +1、回退/跳号拒绝、同内容幂等复用）；succeeded/generating/failed
状态记录往返与完整投影保留；镜像交叉核对（payload 哈希、status、highlights_json、
created_at、权威列漂移即拒绝）；列表与链头读取先解码全部不可变 payload 再过滤——
镜像列漂移的坏行不能被静默隐藏；历史按 revision 升序且按解码出的审核节点隔离。

旧 ``patient_profiles`` 占位表不进入本读取路径。
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.domain.contracts.enums import (
    FactPolarity,
    ProfileLane,
    ReviewStage,
    SourceStrength,
)
from app.domain.contracts.patient_profile_v2 import (
    PROFILE_LANE_ORDER,
    PatientProfileRevisionV2,
    ProfileHighlight,
    ProfileHighlightReason,
    ProfileItem,
    ProfileItemKind,
    ProfileLaneSection,
    ProfileStatus,
    profile_item_identity,
    profile_revision_identity,
)
from app.storage.codecs import PersistedContractInvalid
from app.storage.fact_authority import FactAuthorityError
from app.storage.fact_repositories import FactRevisionChainError, Phase5RepositoryError
from app.storage.facts_models import PatientProfileRevisionV2Record
from app.storage.models import ReviewEpisodeRecord
from app.storage.patient_profile_repository import PatientProfileRevisionRepository
from tests.v2.storage.test_fact_repositories import (
    _authority,
    _seed_chain,
    _update_episode,
)

NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)


def _empty_lanes() -> list[ProfileLaneSection]:
    return [ProfileLaneSection(lane=lane) for lane in PROFILE_LANE_ORDER]


def _revision(
    ids,
    *,
    revision: int = 1,
    status: ProfileStatus = ProfileStatus.SUCCEEDED,
    review_stage: ReviewStage = ReviewStage.SCREENING,
    authority=None,
    lanes=None,
    highlights=None,
    generated_at: datetime = NOW,
    created_at: datetime = NOW,
) -> PatientProfileRevisionV2:
    authority = authority if authority is not None else _authority(ids)
    complete = status in (ProfileStatus.SUCCEEDED, ProfileStatus.STALE)
    if complete:
        lanes = lanes if lanes is not None else _empty_lanes()
        highlights = highlights if highlights is not None else []
    else:
        lanes = []
        highlights = []
    return PatientProfileRevisionV2(
        patient_profile_revision_id=profile_revision_identity(
            ids["review_episode_id"], revision
        ),
        authority=authority,
        status=status,
        revision=revision,
        review_stage=review_stage,
        generated_at=generated_at if complete else None,
        created_at=created_at,
        pending_review_count=len(highlights),
        lanes=lanes,
        highlights=highlights,
    )


def _fact_item(source_id: str = "fact-1", lane: ProfileLane = ProfileLane.DEMOGRAPHICS) -> ProfileItem:
    return ProfileItem(
        item_id=profile_item_identity(ProfileItemKind.FACT, source_id),
        lane=lane,
        kind=ProfileItemKind.FACT,
        source_id=source_id,
        source_revision=1,
        title="性别",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="性别",
        value="女",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        locator_ids=["loc-1"],
    )


def _revision_with_highlight(
    ids, *, revision: int = 1, source_id: str = "fact-1"
) -> PatientProfileRevisionV2:
    item = _fact_item(source_id=source_id)
    highlight = ProfileHighlight(
        item_id=item.item_id,
        reasons=[ProfileHighlightReason.UNRESOLVED_CONFLICT],
    )
    lanes = [
        ProfileLaneSection(
            lane=lane, items=[item] if lane == item.lane else []
        )
        for lane in PROFILE_LANE_ORDER
    ]
    return _revision(ids, revision=revision, lanes=lanes, highlights=[highlight])


@pytest.fixture
def chain(session):
    return _seed_chain(session, "ppr")


@pytest.fixture
def chain_other(session):
    return _seed_chain(session, "ppr2", fixture_index=1)


def _rows(session) -> list[PatientProfileRevisionV2Record]:
    return session.execute(select(PatientProfileRevisionV2Record)).scalars().all()


# ------------------------------------------------------------- 往返与状态


def test_succeeded_roundtrip_preserves_complete_projection(chain, session):
    repo = PatientProfileRevisionRepository(session)
    created = repo.create(_revision_with_highlight(chain, revision=1))
    got = repo.get(created.patient_profile_revision_id)
    assert got == created
    assert got.status == ProfileStatus.SUCCEEDED
    assert [section.lane for section in got.lanes] == list(PROFILE_LANE_ORDER)
    assert got.pending_review_count == 1
    assert len(got.highlights) == 1
    assert got.highlights[0].item_id == _fact_item().item_id
    assert got.authority == _authority(chain)
    assert got.review_stage == ReviewStage.SCREENING
    assert got.generated_at is not None
    assert got.created_at is not None


def test_status_records_roundtrip(chain, session):
    repo = PatientProfileRevisionRepository(session)
    generating = repo.create(
        _revision(chain, revision=1, status=ProfileStatus.GENERATING)
    )
    got = repo.get(generating.patient_profile_revision_id)
    assert got.status == ProfileStatus.GENERATING
    assert got.lanes == []
    assert got.highlights == []
    assert got.pending_review_count == 0
    assert got.generated_at is None

    failed = repo.create(_revision(chain, revision=2, status=ProfileStatus.FAILED))
    got_failed = repo.get(failed.patient_profile_revision_id)
    assert got_failed.status == ProfileStatus.FAILED
    assert got_failed.generated_at is None
    assert got_failed.lanes == []


# ------------------------------------------------------------- 链头追加


def test_first_revision_must_be_one(chain, session):
    repo = PatientProfileRevisionRepository(session)
    with pytest.raises(FactRevisionChainError, match="首个"):
        repo.create(_revision(chain, revision=2))


def test_chain_append_head_plus_one_and_reject_rollback_skip(chain, session):
    repo = PatientProfileRevisionRepository(session)
    repo.create(_revision(chain, revision=1))
    created = repo.create(
        _revision(chain, revision=2, review_stage=ReviewStage.BASELINE)
    )
    assert created.revision == 2
    # 回退到已存在的 revision（内容不同于链头）→ 拒绝。
    with pytest.raises(FactRevisionChainError, match="链头"):
        repo.create(
            _revision(chain, revision=1, review_stage=ReviewStage.PRE_SCREENING)
        )
    # 跳号 → 拒绝。
    with pytest.raises(FactRevisionChainError, match="链头"):
        repo.create(
            _revision(chain, revision=4, review_stage=ReviewStage.RUN_IN)
        )


def test_create_rejects_stale_status_without_writing(chain, session):
    """stale 是读取派生状态，仓储写入边界必须拒绝，且不落任何行。"""
    repo = PatientProfileRevisionRepository(session)
    with pytest.raises(Phase5RepositoryError, match="stale"):
        repo.create(_revision(chain, revision=1, status=ProfileStatus.STALE))
    assert _rows(session) == []


def test_authority_stale_episode_revision_rejected(chain, session):
    repo = PatientProfileRevisionRepository(session)
    repo.create(_revision(chain, revision=1))
    episode = session.get(ReviewEpisodeRecord, chain["review_episode_id"])
    _update_episode(session, episode, revision=2)
    session.flush()
    with pytest.raises(FactAuthorityError, match="陈旧审核节点修订"):
        repo.create(
            _revision(chain, revision=2, review_stage=ReviewStage.BASELINE)
        )


# ------------------------------------------------------------- 镜像交叉核对


def test_mirror_drift_rejected_on_read(chain, session):
    repo = PatientProfileRevisionRepository(session)
    created = repo.create(_revision_with_highlight(chain, revision=1))
    row = session.get(
        PatientProfileRevisionV2Record, created.patient_profile_revision_id
    )

    row.status = "failed"
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="status"):
        repo.get(created.patient_profile_revision_id)

    row.status = "succeeded"
    row.highlights_json = []
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="highlights_json"):
        repo.get(created.patient_profile_revision_id)

    row.highlights_json = [
        h.model_dump(mode="json") for h in created.highlights
    ]
    row.created_at = datetime(2026, 8, 19, 12, 0, 0)
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="created_at"):
        repo.get(created.patient_profile_revision_id)


def test_authority_column_drift_rejected_on_read(chain, session):
    repo = PatientProfileRevisionRepository(session)
    created = repo.create(_revision(chain, revision=1))
    row = session.get(
        PatientProfileRevisionV2Record, created.patient_profile_revision_id
    )
    row.episode_revision = 2
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="episode_revision"):
        repo.get(created.patient_profile_revision_id)


def test_payload_hash_drift_rejected(chain, session):
    repo = PatientProfileRevisionRepository(session)
    created = repo.create(_revision(chain, revision=1))
    row = session.get(
        PatientProfileRevisionV2Record, created.patient_profile_revision_id
    )
    row.payload_sha256 = "0" * 64
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="哈希"):
        repo.get(created.patient_profile_revision_id)


# ------------------------------------------------------------- 列表/链头读取


def test_list_and_latest_decode_all_rows_before_filtering(chain, chain_other, session):
    """先解码全部不可变 payload 再过滤：漂移镜像列的坏行不能被静默隐藏。"""
    repo = PatientProfileRevisionRepository(session)
    repo.create(_revision(chain, revision=1))
    repo.create(_revision(chain_other, revision=1))
    other_id = _revision(chain_other, revision=1).patient_profile_revision_id
    drifted = session.get(PatientProfileRevisionV2Record, other_id)
    # 把另一审核节点行的镜像列漂移：若实现按镜像列先过滤，该坏行会被
    # 静默隐藏或混入；解码先行让它在任何读取路径大声失败。
    drifted.episode_revision = 2
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="episode_revision"):
        repo.list_by_episode(chain["review_episode_id"])
    with pytest.raises(PersistedContractInvalid, match="episode_revision"):
        repo.latest_by_episode(chain["review_episode_id"])
    # 恢复镜像列后正常读取。
    drifted.episode_revision = 1
    session.flush()
    got = repo.list_by_episode(chain["review_episode_id"])
    assert [item.revision for item in got] == [1]


def test_list_order_and_episode_isolation(chain, chain_other, session):
    repo = PatientProfileRevisionRepository(session)
    repo.create(_revision(chain, revision=1))
    repo.create(_revision(chain, revision=2, review_stage=ReviewStage.BASELINE))
    repo.create(_revision(chain_other, revision=1))
    got = repo.list_by_episode(chain["review_episode_id"])
    assert [item.revision for item in got] == [1, 2]
    assert all(
        item.authority.review_episode_id == chain["review_episode_id"] for item in got
    )


def test_latest_by_episode_returns_chain_head(chain, chain_other, session):
    repo = PatientProfileRevisionRepository(session)
    repo.create(_revision(chain, revision=1))
    repo.create(_revision(chain, revision=2, review_stage=ReviewStage.BASELINE))
    repo.create(_revision(chain_other, revision=1))
    head = repo.latest_by_episode(chain["review_episode_id"])
    assert head is not None and head.revision == 2
    assert repo.latest_by_episode("no-such-episode") is None
