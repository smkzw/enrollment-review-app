"""乐观并发：expected revision 更新、字段差异信封与两会话冲突。"""
from __future__ import annotations

import pytest

from app.storage.concurrency import StaleRevisionError
from app.storage.repositories import (
    EvidenceExpectationRepository,
    ProjectRepository,
    SubjectRepository,
    persist_fixture,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES


@pytest.fixture
def seeded(session):
    fixture = FIXTURES[0]
    persist_fixture(session, fixture)
    session.commit()
    return fixture


def test_update_with_correct_revision_bumps_and_persists(session, seeded) -> None:
    subject_id = seeded.subject.subject_id
    repo = SubjectRepository(session)
    updated = repo.update(
        subject_id,
        expected_revision=1,
        changes={"center_code": "CENTER-02", "center_name": "中心二号"},
    )
    assert updated.revision == 2
    assert updated.center_code == "CENTER-02"
    session.commit()
    reread = repo.get(subject_id)
    assert reread == updated
    assert reread.revision == 2
    assert reread.center_name == "中心二号"


def test_stale_revision_conflict_returns_current_and_diff(session_factory, seeded) -> None:
    """两个会话以相同 revision 编辑，后提交者收到当前值与字段差异。"""
    subject_id = seeded.subject.subject_id
    with session_factory() as first_session:
        winner = SubjectRepository(first_session).update(
            subject_id,
            expected_revision=1,
            changes={"center_code": "CENTER-WINNER"},
        )
        first_session.commit()

    with session_factory() as second_session:
        repo = SubjectRepository(second_session)
        with pytest.raises(StaleRevisionError) as caught:
            repo.update(
                subject_id,
                expected_revision=1,  # 过期 revision
                changes={"center_code": "CENTER-LOSER"},
            )
        error = caught.value
        assert error.code == "STALE_REVISION"
        assert error.expected_revision == 1
        assert error.current_revision == 2
        assert "center_code" in error.field_diff
        change = error.field_diff["center_code"]
        assert change.current == "CENTER-WINNER"
        assert change.submitted == "CENTER-LOSER"
        envelope = error.as_dict()
        assert envelope["current_revision"] == 2
        assert envelope["field_diff"]["center_code"]["current"] == "CENTER-WINNER"
        assert envelope["current_record"]["revision"] == 2

    # 数据库内容未被静默覆盖
    with session_factory() as third_session:
        current = SubjectRepository(third_session).get(subject_id)
        assert current.center_code == "CENTER-WINNER"
        assert current.revision == 2


def test_true_flush_race_returns_fresh_revision_and_diff(session_factory, seeded) -> None:
    """两个会话都先读取 revision 1；输家 flush 时必须重新读取赢家结果。"""
    subject_id = seeded.subject.subject_id
    with session_factory() as winner_session, session_factory() as loser_session:
        winner_repo = SubjectRepository(winner_session)
        loser_repo = SubjectRepository(loser_session)

        # 两边都先把 revision 1 的 ORM 行放入 identity map。
        assert winner_repo.get(subject_id).revision == 1
        assert loser_repo.get(subject_id).revision == 1

        winner_repo.update(
            subject_id,
            expected_revision=1,
            changes={"center_code": "CENTER-RACE-WINNER"},
        )
        winner_session.commit()

        with pytest.raises(StaleRevisionError) as caught:
            loser_repo.update(
                subject_id,
                expected_revision=1,
                changes={"center_code": "CENTER-RACE-LOSER"},
            )

        error = caught.value
        assert error.current_revision == 2
        assert error.current_record is not None
        assert error.current_record.center_code == "CENTER-RACE-WINNER"
        assert error.field_diff["center_code"].current == "CENTER-RACE-WINNER"
        assert error.field_diff["center_code"].submitted == "CENTER-RACE-LOSER"


def test_update_with_unknown_field_is_rejected_by_contract(session, seeded) -> None:
    subject_id = seeded.subject.subject_id
    repo = SubjectRepository(session)
    with pytest.raises(Exception, match="extra|Extra"):
        repo.update(
            subject_id,
            expected_revision=1,
            changes={"project_id": "project-other", "not_a_field": 1},
        )


def test_project_update_with_rule_set_change_moves_scope(session, seeded) -> None:
    """rule_set_id 变化必须携带新 revision；scope 重新校验并落列。"""
    repo = ProjectRepository(session)
    # 新 rule set revision 与既有规则内容相同但 revision 不同（追加写）
    from app.storage.repositories import save_rule_set

    rule_set_v2 = seeded.rule_set.model_copy(update={"revision": 2})
    save_rule_set(session, rule_set_v2)
    project = repo.update(
        seeded.project.project_id,
        expected_revision=1,
        changes={"rule_set_id": seeded.rule_set.rule_set_id},
        rule_set_revision=2,
    )
    assert project.revision == 2
    row = session.get(
        __import__("app.storage.models", fromlist=["ProjectRecord"]).ProjectRecord,
        seeded.project.project_id,
    )
    assert row.rule_set_revision == 2
    session.commit()
    assert repo.get(seeded.project.project_id).rule_set_id == seeded.rule_set.rule_set_id


def test_expectation_update_replaces_span_assoc(session, seeded) -> None:
    from app.storage.models import evidence_expectation_spans
    from sqlalchemy import select

    expectation = seeded.evidence_expectations[0]
    repo = EvidenceExpectationRepository(session)
    new_spans = [seeded.evidence_spans[0].evidence_span_id]
    updated = repo.update(
        expectation.expectation_id,
        expected_revision=1,
        changes={"evidence_span_ids": new_spans},
    )
    assert updated.evidence_span_ids == new_spans
    from app.storage.models import EvidenceExpectationRecord

    assert session.get(EvidenceExpectationRecord, expectation.expectation_id).revision == 2
    rows = session.execute(
        select(evidence_expectation_spans)
        .where(evidence_expectation_spans.c.expectation_id == expectation.expectation_id)
        .order_by(evidence_expectation_spans.c.position)
    ).all()
    assert [row.evidence_span_id for row in rows] == new_spans
    session.commit()
    assert repo.get(expectation.expectation_id) == updated
