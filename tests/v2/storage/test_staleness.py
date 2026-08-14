"""实体 stale 状态：打开、影响范围查询与 ReviewRun 精确关闭。"""
from __future__ import annotations

from app.storage.staleness import StalenessRecord, StalenessRepository


def test_open_and_list_stale_records(session) -> None:
    repo = StalenessRepository(session)
    first = repo.open(
        target_type="rule_component",
        target_id="component-in-01",
        reason="规则逻辑变更",
        source_entity_type="rule_set",
        source_entity_id="ruleset-1",
        source_revision=2,
    )
    second = repo.open(
        target_type="subject",
        target_id="subject-1",
        reason="上游事实变更",
        source_entity_type="clinical_fact",
        source_entity_id="fact-1",
        source_revision=1,
    )
    session.commit()
    assert isinstance(first, StalenessRecord)
    assert first.open is True
    opened = repo.list_open()
    assert {record.id for record in opened} == {first.id, second.id}
    assert {record.target_type for record in opened} == {"rule_component", "subject"}


def test_reopen_same_source_revision_is_idempotent(session) -> None:
    repo = StalenessRepository(session)
    kwargs = dict(
        target_type="rule_component",
        target_id="component-in-01",
        reason="规则逻辑变更",
        source_entity_type="rule_set",
        source_entity_id="ruleset-1",
        source_revision=2,
    )
    first = repo.open(**kwargs)
    second = repo.open(**kwargs)
    assert first.id == second.id
    session.commit()
    assert len(repo.list_open()) == 1


def test_close_covered_only_clears_covered_targets(session) -> None:
    from app.storage.repositories import persist_fixture
    from tests.v2.storage.test_repositories_roundtrip import FIXTURES

    fixture = FIXTURES[0]
    persist_fixture(session, fixture)
    repo = StalenessRepository(session)
    repo.open(
        target_type="rule_component", target_id="c1", reason="r1",
        source_entity_type="rule_set", source_entity_id="rs", source_revision=2,
    )
    repo.open(
        target_type="rule_component", target_id="c2", reason="r1",
        source_entity_type="rule_set", source_entity_id="rs", source_revision=2,
    )
    repo.open(
        target_type="rule_component", target_id="c3", reason="r1",
        source_entity_type="rule_set", source_entity_id="rs", source_revision=2,
    )
    session.commit()
    closed = repo.close_covered(
        review_run_id=fixture.review_runs[0].review_run_id,
        covered=[("rule_component", "c1"), ("rule_component", "c3")],
    )
    assert closed == 2
    session.commit()
    remaining = repo.list_open(target_type="rule_component")
    assert [record.target_id for record in remaining] == ["c2"]
    all_records = [
        record
        for record in session.query(
            __import__("app.storage.models", fromlist=["EntityStalenessRow"]).EntityStalenessRow
        ).all()
    ]
    cleared = [r for r in all_records if r.cleared_at is not None]
    assert sorted(r.target_id for r in cleared) == ["c1", "c3"]
    assert all(r.cleared_by_review_run_id == fixture.review_runs[0].review_run_id for r in cleared)


def test_close_with_empty_coverage_closes_nothing(session) -> None:
    repo = StalenessRepository(session)
    repo.open(
        target_type="subject", target_id="s1", reason="r",
        source_entity_type="evidence_snapshot", source_entity_id="snap", source_revision=1,
    )
    session.commit()
    assert repo.close_covered(review_run_id="run-x", covered=[]) == 0
    assert len(repo.list_open()) == 1


def test_list_open_filters_by_target_and_source(session) -> None:
    repo = StalenessRepository(session)
    repo.open(
        target_type="subject", target_id="s1", reason="r",
        source_entity_type="rule_set", source_entity_id="rs", source_revision=2,
    )
    repo.open(
        target_type="subject", target_id="s2", reason="r",
        source_entity_type="rule_set", source_entity_id="rs", source_revision=2,
    )
    repo.open(
        target_type="action", target_id="a1", reason="r",
        source_entity_type="rule_set", source_entity_id="rs", source_revision=2,
    )
    session.commit()
    assert [r.target_id for r in repo.list_open(target_type="subject")] == ["s1", "s2"]
    assert [r.target_id for r in repo.list_open(target_id="s2")] == ["s2"]
    assert [r.target_id for r in repo.list_open(source_entity_type="rule_set", source_entity_id="rs")] == [
        "s1",
        "s2",
        "a1",
    ]
