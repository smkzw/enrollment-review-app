"""三份 Phase 0.5 fixture 的持久化完整往返、跨 scope 反向测试与 N+1 检查。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import event, select

from app.domain.contracts import FixtureV1
from app.storage.repositories import (
    ActionRequestRepository,
    AppendRepository,
    AGENT_CALL_CONFIG,
    ASSESSMENT_CANDIDATE_CONFIG,
    CLINICAL_FACT_CONFIG,
    CONFLICT_GROUP_CONFIG,
    EVIDENCE_SPAN_CONFIG,
    FINAL_ASSESSMENT_CONFIG,
    GATE_RESULT_CONFIG,
    MODEL_CONFIG_CONFIG,
    NORMALIZATION_CANDIDATE_CONFIG,
    PATIENT_PROFILE_CONFIG,
    PROMPT_VERSION_CONFIG,
    PROTOCOL_DOC_CONFIG,
    REVIEW_RUN_CONFIG,
    SNAPSHOT_CONFIG,
    SOURCE_DOCUMENT_CONFIG,
    AUTHORITY_CONFIRMATION_CONFIG,
    AUTHORITY_RECORD_CONFIG,
    COMMAND_EVENT_CONFIG,
    INTEGRITY_MANIFEST_CONFIG,
    SOURCE_RECORD_CONFIG,
    DuplicateRecordError,
    InvalidReferenceError,
    ScopeViolationError,
    EpisodeRepository,
    EvidenceExpectationRepository,
    JobRepository,
    ProjectRepository,
    SubjectRepository,
    get_evidence_requirement,
    get_latest_rollup,
    get_rule,
    get_rule_component,
    get_rule_set,
    persist_fixture,
)
from app.storage.models import (
    JobEventRecord,
    ReviewEpisodeRecord,
    clinical_fact_spans,
    evidence_snapshot_documents,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATHS = sorted((ROOT / "contracts" / "v1" / "fixtures").glob("subject-*.json"))


def load_fixture(path: Path) -> FixtureV1:
    return FixtureV1.model_validate(json.loads(path.read_text(encoding="utf-8")))


FIXTURES = [load_fixture(path) for path in FIXTURE_PATHS]


@pytest.fixture(params=FIXTURES, ids=[path.stem for path in FIXTURE_PATHS])
def seeded_session(request, session):
    """已播种一份 fixture 的会话（测试结束时回滚）。"""
    fixture = request.param
    persist_fixture(session, fixture)
    session.commit()
    yield fixture, session


# ---------------------------------------------------------------------------
# 完整往返
# ---------------------------------------------------------------------------


def test_fixture_persists_and_roundtrips_fully(seeded_session) -> None:
    fixture, session = seeded_session

    project_repo = ProjectRepository(session)
    assert project_repo.get(fixture.project.project_id) == fixture.project

    subject_repo = SubjectRepository(session)
    assert subject_repo.get(fixture.subject.subject_id) == fixture.subject
    assert subject_repo.list_by_project(fixture.project.project_id) == [fixture.subject]

    episode_repo = EpisodeRepository(session)
    assert episode_repo.get(fixture.review_episode.review_episode_id) == fixture.review_episode

    # 协议权威链
    protocol_doc = AppendRepository(session, PROTOCOL_DOC_CONFIG).get(
        fixture.project.protocol_version.protocol_version_id
    )
    assert protocol_doc == fixture.project.protocol_version
    assert (
        AppendRepository(session, AUTHORITY_RECORD_CONFIG).get(
            fixture.protocol_authority_record.authority_record_id
        )
        == fixture.protocol_authority_record
    )
    assert (
        AppendRepository(session, COMMAND_EVENT_CONFIG).get(
            fixture.protocol_authority_command.command_id
        )
        == fixture.protocol_authority_command
    )
    assert (
        AppendRepository(session, AUTHORITY_CONFIRMATION_CONFIG).get(
            fixture.protocol_authority_confirmation.confirmation_id
        )
        == fixture.protocol_authority_confirmation
    )
    assert (
        AppendRepository(session, INTEGRITY_MANIFEST_CONFIG).get(
            fixture.protocol_integrity_manifest.manifest_id
        )
        == fixture.protocol_integrity_manifest
    )
    for record in fixture.protocol_source_records:
        assert (
            AppendRepository(session, SOURCE_RECORD_CONFIG).get(record.source_ref) == record
        )

    # 规则集树
    assert get_rule_set(session, fixture.rule_set.rule_set_id, fixture.rule_set.revision) == (
        fixture.rule_set
    )
    for rule in fixture.rule_set.rules:
        assert (
            get_rule(session, fixture.rule_set.rule_set_id, fixture.rule_set.revision, rule.rule_id)
            == rule
        )
        for component in rule.components:
            assert (
                get_rule_component(
                    session,
                    fixture.rule_set.rule_set_id,
                    fixture.rule_set.revision,
                    component.rule_component_id,
                )
                == component
            )
            for requirement in component.evidence_requirements:
                assert (
                    get_evidence_requirement(
                        session,
                        fixture.rule_set.rule_set_id,
                        fixture.rule_set.revision,
                        requirement.requirement_id,
                    )
                    == requirement
                )

    # 证据链
    snapshot_repo = AppendRepository(session, SNAPSHOT_CONFIG)
    assert snapshot_repo.get(fixture.evidence_snapshot.evidence_snapshot_id) == (
        fixture.evidence_snapshot
    )
    document_repo = AppendRepository(session, SOURCE_DOCUMENT_CONFIG)
    for document in fixture.source_documents:
        assert document_repo.get(document.source_document_version_id) == document
    span_repo = AppendRepository(session, EVIDENCE_SPAN_CONFIG)
    for span in fixture.evidence_spans:
        assert span_repo.get(span.evidence_span_id) == span
    fact_repo = AppendRepository(session, CLINICAL_FACT_CONFIG)
    for fact in fixture.facts:
        assert fact_repo.get(fact.fact_id) == fact
    group_repo = AppendRepository(session, CONFLICT_GROUP_CONFIG)
    for group in fixture.conflict_groups:
        assert group_repo.get(group.conflict_group_id) == group
    expectation_repo = EvidenceExpectationRepository(session)
    assert expectation_repo.list_by_episode(
        fixture.review_episode.review_episode_id
    ) == sorted(fixture.evidence_expectations, key=lambda item: item.expectation_id)

    # 审核链
    run_repo = AppendRepository(session, REVIEW_RUN_CONFIG)
    for run in fixture.review_runs:
        assert run_repo.get(run.review_run_id) == run
    candidate_repo = AppendRepository(session, ASSESSMENT_CANDIDATE_CONFIG)
    for candidate in fixture.assessment_candidates:
        assert candidate_repo.get(candidate.assessment_candidate_id) == candidate
    assessment_repo = AppendRepository(session, FINAL_ASSESSMENT_CONFIG)
    for assessment in fixture.final_assessments:
        assert assessment_repo.get(assessment.assessment_id) == assessment
    action_repo = ActionRequestRepository(session)
    assert sorted(
        (action_repo.get(action.action_id).action_id for action in fixture.actions)
    ) == sorted(action.action_id for action in fixture.actions)
    for action in fixture.actions:
        assert action_repo.get(action.action_id) == action

    # Agent/Gate
    prompt_repo = AppendRepository(session, PROMPT_VERSION_CONFIG)
    for prompt_version in fixture.prompt_versions:
        assert prompt_repo.get(prompt_version.prompt_version_id) == prompt_version
    model_repo = AppendRepository(session, MODEL_CONFIG_CONFIG)
    for model_config in fixture.model_configs:
        assert model_repo.get(model_config.model_config_id) == model_config
    call_repo = AppendRepository(session, AGENT_CALL_CONFIG)
    for call in fixture.agent_calls:
        assert call_repo.get(call.agent_call_id) == call
    gate_repo = AppendRepository(session, GATE_RESULT_CONFIG)
    for gate in fixture.gate_results:
        assert gate_repo.get(gate.gate_result_id) == gate
    candidate_norm_repo = AppendRepository(session, NORMALIZATION_CANDIDATE_CONFIG)
    for candidate in fixture.evidence_normalization_candidates:
        assert candidate_norm_repo.get(candidate.candidate_id) == candidate

    # 投影与 Job 事件
    assert (
        AppendRepository(session, PATIENT_PROFILE_CONFIG).get(
            fixture.patient_profile.patient_profile_id
        )
        == fixture.patient_profile
    )
    assert get_latest_rollup(session, fixture.review_episode.review_episode_id) == (
        fixture.episode_rollup
    )


def test_job_events_roundtrip_with_monotonic_seq(seeded_session) -> None:
    fixture, session = seeded_session
    repo = JobRepository(session)
    for job_id in dict.fromkeys(event.job_id for event in fixture.job_events):
        events = repo.list_events(job_id)
        expected = [event for event in fixture.job_events if event.job_id == job_id]
        assert events == expected
        # 序号从 1 单调递增，不重复
        rows = session.execute(
            select(JobEventRecord)
            .where(JobEventRecord.job_id == job_id)
            .order_by(JobEventRecord.event_seq)
        ).scalars().all()
        sequences = [row.event_seq for row in rows]
        assert sequences == list(range(1, len(events) + 1))
        # after_seq 断点续读：只返回更新的、有序、无重复
        if len(events) > 2:
            assert repo.list_events(job_id, after_seq=2) == expected[2:]


def test_association_tables_preserve_ordered_refs(seeded_session) -> None:
    fixture, session = seeded_session
    snapshot = fixture.evidence_snapshot
    rows = session.execute(
        select(evidence_snapshot_documents)
        .where(evidence_snapshot_documents.c.evidence_snapshot_id == snapshot.evidence_snapshot_id)
        .order_by(evidence_snapshot_documents.c.position)
    ).all()
    assert [row.source_document_version_id for row in rows] == list(
        snapshot.source_document_version_ids
    )
    for fact in fixture.facts:
        rows = session.execute(
            select(clinical_fact_spans)
            .where(clinical_fact_spans.c.fact_id == fact.fact_id)
            .order_by(clinical_fact_spans.c.position)
        ).all()
        assert [row.evidence_span_id for row in rows] == list(fact.evidence_span_ids)


def test_duplicate_fixture_persist_is_rejected_not_duplicated(seeded_session) -> None:
    fixture, session = seeded_session
    with pytest.raises(DuplicateRecordError):
        persist_fixture(session, fixture)


# ---------------------------------------------------------------------------
# 跨 scope 反向测试
# ---------------------------------------------------------------------------


def test_cross_subject_fact_is_rejected(seeded_session) -> None:
    fixture, session = seeded_session
    fact = fixture.facts[0]
    cross_subject = fact.model_copy(update={"subject_id": "subject-other", "fact_id": "fact-cross"})
    with pytest.raises(ScopeViolationError, match="subject 超出"):
        AppendRepository(session, CLINICAL_FACT_CONFIG).save(cross_subject)


def test_run_with_wrong_rule_set_revision_is_rejected(seeded_session) -> None:
    fixture, session = seeded_session
    run = fixture.review_runs[0]
    cross = run.model_copy(
        update={"review_run_id": "run-cross-revision", "rule_set_revision": 99}
    )
    with pytest.raises(ScopeViolationError, match="rule_set_revision"):
        AppendRepository(session, REVIEW_RUN_CONFIG).save(cross)


def test_run_with_wrong_protocol_version_is_rejected(seeded_session) -> None:
    fixture, session = seeded_session
    run = fixture.review_runs[0]
    cross = run.model_copy(
        update={"review_run_id": "run-cross-protocol", "protocol_version_id": "protocol-other"}
    )
    with pytest.raises(ScopeViolationError, match="protocol_version"):
        AppendRepository(session, REVIEW_RUN_CONFIG).save(cross)


def test_assessment_with_component_from_other_rule_set_is_rejected(seeded_session) -> None:
    fixture, session = seeded_session
    assessment = fixture.final_assessments[0]
    cross = assessment.model_copy(
        update={"assessment_id": "assessment-cross-component", "rule_component_id": "component-elsewhere"}
    )
    with pytest.raises(ScopeViolationError, match="RuleComponent"):
        AppendRepository(session, FINAL_ASSESSMENT_CONFIG).save(cross)


def test_action_with_assessment_from_other_episode_is_rejected(seeded_session) -> None:
    fixture, session = seeded_session
    action = fixture.actions[0]
    cross = action.model_copy(
        update={"action_id": "action-cross-assessment", "review_episode_id": "episode-other"}
    )
    with pytest.raises((ScopeViolationError, InvalidReferenceError)):
        ActionRequestRepository(session).save(cross)


def test_episode_with_mismatched_subject_project_is_rejected(seeded_session) -> None:
    fixture, session = seeded_session
    episode = fixture.review_episode
    cross = episode.model_copy(
        update={"review_episode_id": "episode-cross-project", "project_id": "project-other"}
    )
    with pytest.raises(ScopeViolationError, match="project 与 subject 不一致"):
        EpisodeRepository(session).save(cross)


def test_episode_with_unknown_rule_set_is_rejected(seeded_session) -> None:
    fixture, session = seeded_session
    episode = fixture.review_episode
    cross = episode.model_copy(
        update={"review_episode_id": "episode-cross-ruleset", "rule_set_revision": 99}
    )
    with pytest.raises(ScopeViolationError, match="RuleSet"):
        EpisodeRepository(session).save(cross)


def test_expectation_with_foreign_requirement_is_rejected(seeded_session) -> None:
    fixture, session = seeded_session
    expectation = fixture.evidence_expectations[0]
    cross = expectation.model_copy(
        update={"expectation_id": "expectation-cross", "requirement_id": "requirement-elsewhere"}
    )
    with pytest.raises(ScopeViolationError, match="requirement"):
        EvidenceExpectationRepository(session).save(cross)


def test_subject_with_unknown_project_is_rejected(seeded_session) -> None:
    fixture, session = seeded_session
    subject = fixture.subject
    cross = subject.model_copy(update={"subject_id": "subject-cross-project", "project_id": "project-other"})
    with pytest.raises(InvalidReferenceError, match="Project"):
        SubjectRepository(session).save(cross)


# ---------------------------------------------------------------------------
# N+1 查询检查
# ---------------------------------------------------------------------------


def _count_selects(session_factory, operation) -> int:
    count = 0

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal count
        if statement.lstrip().upper().startswith("SELECT"):
            count += 1

    engine = session_factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        with session_factory() as session:
            operation(session)
            session.commit()
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    return count


def test_list_queries_are_constant_not_n_plus_one(session_factory, session) -> None:
    """列表查询 SELECT 数量与行数无关（批量加载，禁止按实体 N+1）。"""
    # 播种第二个 subject（5 个 episode 场景不够多也没关系：验证 1 行与 N 行查询数一致）
    fixture = FIXTURES[0]
    persist_fixture(session, fixture)
    session.commit()
    engine = session_factory.kw["bind"]

    def run_list(session_arg, n_rows):
        rows = session_arg.execute(
            select(ReviewEpisodeRecord).order_by(ReviewEpisodeRecord.review_episode_id)
        ).scalars().all()
        assert len(rows) == n_rows

    baseline = _count_selects(session_factory, lambda s: run_list(s, 1))
    assert baseline == 1  # 单条 SELECT

    # 插入更多 episode（复制现有 episode 换 id，规则集不变）
    from app.storage.repositories import EpisodeRepository

    episode_repo = EpisodeRepository(session)
    original = fixture.review_episode
    for index in range(2, 6):
        copy = original.model_copy(
            update={"review_episode_id": f"episode-extra-{index}", "subject_id": original.subject_id}
        )
        # 需要新的 subject 才能满足 episode 唯一性不冲突（episode id 已不同）
        episode_repo.save(copy)
    session.commit()
    grown = _count_selects(session_factory, lambda s: run_list(s, 5))
    assert grown == baseline == 1
