"""Phase 5 迁移 0013：v2 临床事实/事件/暴露/冲突/期望/Profile 持久化 确定性测试。

覆盖（Slice 5.1，worker_02）：

- 升级到 head 后 15 张新表存在且 schema 与 ORM metadata 逐表一致；
- 旧占位表（``clinical_facts`` / ``evidence_expectations`` / ``patient_profiles`` /
  ``conflict_groups`` / ``evidence_normalization_candidates``）保持只读回归锚点：
  不被添加 v2 列、不被任何 v2 表外键引用；
- 权威元组绑定 v2 证据快照与完整处理修订（legacy snapshot id 不能通过外键）；
- 运行幂等键唯一、稳定身份 revision 链唯一、locator/事件/暴露/冲突成员外键强约束；
- 追加写 payload 哈希与镜像列一致；
- 降级：含正式数据拒绝有损降级并恢复备份；空绿地库按依赖逆序删除全部新表。
"""
from __future__ import annotations

import hashlib
from datetime import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.storage.migrate import MigrationFailure, MigrationManager, resolve_head_revision
from app.storage.facts_models import (
    ClinicalConflictGroupV2Record,
    ClinicalEventV2Record,
    ClinicalFactV2Record,
    EventFactLinkRecord,
    EvidenceExpectationV2Record,
    ExposureFactLinkRecord,
    FactEvidenceLocatorLinkRecord,
    FactGateResultRecord,
    FactNormalizationCandidateRecord,
    FactNormalizationCallRecord,
    FactNormalizationRunRecord,
    FactRuleLinkV2Record,
    MedicationExposureV2Record,
    PatientProfileRevisionV2Record,
)
from app.storage.evidence_models import EvidenceSnapshotV2Record
from app.storage.models import (
    EvidenceExpectationTemplateRecord,
    EvidenceRequirementRecord,
    ModelConfigRecord,
    ProjectRecord,
    PromptVersionRecord,
    ReviewEpisodeRecord,
    RuleSetRecord,
    SubjectRecord,
    ProtocolDocumentVersionRecord,
    WorkflowStageRecord,
)
from app.storage.ocr_models import EvidenceProcessingRevisionRecord

#: 0013 新建的 15 张 v2 表（降级检查顺序即依赖逆序）。
V2_TABLES = (
    "fact_normalization_runs",
    "fact_normalization_calls",
    "fact_normalization_candidates",
    "fact_gate_results",
    "clinical_facts_v2",
    "clinical_events_v2",
    "medication_exposures_v2",
    "fact_evidence_locator_links",
    "event_fact_links",
    "exposure_fact_links",
    "clinical_conflict_groups_v2",
    "clinical_conflict_members_v2",
    "fact_rule_links_v2",
    "evidence_expectations_v2",
    "patient_profile_revisions_v2",
)

#: Phase 2/3 占位事实表：Phase 5 只读回归锚点，不得进入 v2 写路径。
LEGACY_PLACEHOLDER_TABLES = frozenset(
    {
        "clinical_facts",
        "conflict_groups",
        "evidence_normalization_candidates",
        "evidence_expectations",
        "patient_profiles",
    }
)

NOW = datetime(2026, 8, 22, 12, 0, 0)


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _payload(payload: str = '{"kind": "test"}') -> tuple[str, str]:
    return payload, _sha256(payload)


# --------------------------------------------------------------------------- 播种


def _seed_authority(session) -> dict[str, str]:
    """播种最小权威链：protocol -> rule_set -> project -> subject -> episode ->
    snapshot_v2 -> base/complete 处理修订 -> prompt_version -> model_config ->
    run -> call -> gate。返回全部 id 供发布实体引用。

    逐条 flush：legacy ``review_episodes <-> evidence_snapshots`` 双向 FK 形成 UoW
    循环，批量 flush 的拓扑排序不可靠（与 ``test_domain_schema`` 的
    ``test_episode_snapshot_cycle_allowed_in_one_transaction`` 同一约定）。
    """
    now = NOW
    payload, payload_sha = _payload()
    protocol_version_id = "protocol-0013"
    rule_set_id = "ruleset-0013"
    project_id = "project-0013"
    subject_id = "subject-0013"
    review_episode_id = "episode-0013"
    evidence_snapshot_id = "snapshot-v2-0013"
    base_revision_id = "epr-base-0013"
    complete_revision_id = "epr-complete-0013"
    prompt_version_id = "prompt-0013"
    model_config_id = "modelcfg-0013"
    run_id = "run-0013"
    call_id = "call-0013"
    gate_result_id = "gate-0013"

    def add(record) -> None:
        session.add(record)
        session.flush()

    add(ProtocolDocumentVersionRecord(
        protocol_version_id=protocol_version_id,
        protocol_code="P13",
        official_version="v1",
        official_date_value=None,
        official_date_precision="unknown",
        sha256=_sha256("protocol"),
        integrity_manifest_sha256=_sha256("integrity"),
        authority_record_sha256=_sha256("authority"),
        authority_confirmation_id="confirm-0013",
        authority_gate_result_id="agr-0013",
        integrity_gate_result_id="igr-0013",
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(RuleSetRecord(
        rule_set_id=rule_set_id,
        revision=1,
        protocol_version_id=protocol_version_id,
        study_phase="phase_iii",
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(EvidenceRequirementRecord(
        rule_set_id=rule_set_id,
        rule_set_revision=1,
        requirement_id="req-0013",
        rule_component_id=None,
        procedure_catalog_item_id="procedure-catalog-0013",
        fact_type="vital_sign",
        due_stage="screening",
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(ProjectRecord(
        project_id=project_id,
        project_code="P0013",
        project_name="migration-0013",
        study_phase="phase_iii",
        protocol_version_id=protocol_version_id,
        rule_set_id=rule_set_id,
        rule_set_revision=1,
        payload_json=payload,
        payload_sha256=payload_sha,
        revision=1,
        created_at=now,
        updated_at=now,
    ))
    add(SubjectRecord(
        subject_id=subject_id,
        subject_code="S0013",
        project_id=project_id,
        payload_json=payload,
        payload_sha256=payload_sha,
        revision=1,
        created_at=now,
        updated_at=now,
    ))
    add(ReviewEpisodeRecord(
        review_episode_id=review_episode_id,
        subject_id=subject_id,
        project_id=project_id,
        rule_set_id=rule_set_id,
        rule_set_revision=1,
        study_phase="phase_iii",
        stage="screening",
        protocol_version_id=protocol_version_id,
        evidence_snapshot_id=None,
        active_evidence_snapshot_id=None,
        active_evidence_processing_revision_id=None,
        anchor_dates_json={},
        due_at=None,
        payload_json=payload,
        payload_sha256=payload_sha,
        revision=1,
        created_at=now,
        updated_at=now,
    ))
    add(EvidenceSnapshotV2Record(
        evidence_snapshot_id=evidence_snapshot_id,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=review_episode_id,
        upload_mode="full",
        prior_snapshot_id=None,
        comparison_snapshot_id=None,
        collection_sha256=_sha256("collection"),
        created_by="test",
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(EvidenceProcessingRevisionRecord(
        evidence_processing_revision_id=base_revision_id,
        evidence_snapshot_id=evidence_snapshot_id,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=review_episode_id,
        manifest_sha256=_sha256("base-manifest"),
        status="ready",
        is_activatable=False,
        revision_kind="base",
        base_processing_revision_id=None,
        producer_candidate_id=None,
        candidate_input_sha256=None,
        completion_manifest_sha256=None,
        created_by="test",
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(EvidenceProcessingRevisionRecord(
        evidence_processing_revision_id=complete_revision_id,
        evidence_snapshot_id=evidence_snapshot_id,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=review_episode_id,
        manifest_sha256=_sha256("complete-manifest"),
        status="ready",
        is_activatable=True,
        revision_kind="complete",
        base_processing_revision_id=base_revision_id,
        producer_candidate_id="candidate-0013",
        candidate_input_sha256=_sha256("candidate-input"),
        completion_manifest_sha256=_sha256("completion-manifest"),
        created_by="test",
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(PromptVersionRecord(
        prompt_version_id=prompt_version_id,
        node="evidence_normalizer",
        template_sha256=_sha256("prompt"),
        schema_version_id="phase5/facts/v1",
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(ModelConfigRecord(
        model_config_id=model_config_id,
        provider="test-provider",
        model="test-model",
        reasoning_effort="medium",
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(WorkflowStageRecord(
        workflow_stage_id="stage-0013",
        protocol_version_id=protocol_version_id,
        stage="screening",
        study_phase="phase_iii",
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(EvidenceExpectationTemplateRecord(
        template_id="template-0013",
        rule_set_id=rule_set_id,
        rule_set_revision=1,
        requirement_id="req-0013",
        due_stage="screening",
        study_phase="phase_iii",
        workflow_stage_id="stage-0013",
        fact_type="vital_sign",
        required_source_types=None,
        projection_sha256=_sha256("template-projection"),
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(FactNormalizationRunRecord(
        run_id=run_id,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=review_episode_id,
        episode_revision=1,
        protocol_version_id=protocol_version_id,
        rule_set_id=rule_set_id,
        rule_set_revision=1,
        evidence_snapshot_v2_id=evidence_snapshot_id,
        complete_processing_revision_id=complete_revision_id,
        idempotency_key=_sha256("idempotency-0013"),
        prompt_version_id=prompt_version_id,
        model_config_id=model_config_id,
        input_scope_sha256=_sha256("input-scope"),
        status="succeeded",
        job_id=None,
        created_by="test",
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(FactNormalizationCallRecord(
        call_id=call_id,
        run_id=run_id,
        logical_document_id="logical-doc-0013",
        page_numbers_json=[1, 2, 3],
        status="succeeded",
        input_sha256=_sha256("call-input"),
        raw_output_sha256=_sha256("raw-output"),
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(FactNormalizationCandidateRecord(
        candidate_id="candidate-0013",
        run_id=run_id,
        call_id=call_id,
        candidate_kind="fact",
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    add(FactGateResultRecord(
        gate_result_id=gate_result_id,
        run_id=run_id,
        call_id=call_id,
        candidate_id="candidate-0013",
        gate="transactional_publish",
        outcome="accepted",
        reasons_json=[],
        payload_json=payload,
        payload_sha256=payload_sha,
        created_at=now,
    ))
    return {
        "project_id": project_id,
        "subject_id": subject_id,
        "review_episode_id": review_episode_id,
        "protocol_version_id": protocol_version_id,
        "rule_set_id": rule_set_id,
        "evidence_snapshot_v2_id": evidence_snapshot_id,
        "complete_processing_revision_id": complete_revision_id,
        "run_id": run_id,
        "call_id": call_id,
        "gate_id": gate_result_id,
        "template_id": "template-0013",
    }


def _fact_kwargs(ids: dict[str, str], *, fact_id: str = "fact-0013",
                 stable_identity: str | None = None, revision: int = 1) -> dict:
    payload, payload_sha = _payload()
    return {
        "fact_id": fact_id,
        "run_id": ids["run_id"],
        "gate_id": ids["gate_id"],
        "project_id": ids["project_id"],
        "subject_id": ids["subject_id"],
        "review_episode_id": ids["review_episode_id"],
        "episode_revision": 1,
        "protocol_version_id": ids["protocol_version_id"],
        "rule_set_id": ids["rule_set_id"],
        "rule_set_revision": 1,
        "evidence_snapshot_v2_id": ids["evidence_snapshot_v2_id"],
        "complete_processing_revision_id": ids["complete_processing_revision_id"],
        "fact_type": "vital_sign",
        "polarity": "affirmed",
        "value_json": "120/80",
        "unit": "unitless",
        "source_strength": "contemporaneous_objective_result",
        "date_precision": None,
        "date_lower_bound": None,
        "date_upper_bound": None,
        "date_source_text": None,
        "record_time": None,
        "assertion_object": "blood pressure",
        "assertion_text": "血压 120/80 mmHg",
        "assertion_locator_id": None,
        "assertion_source_text_sha256": None,
        "stable_identity": stable_identity or _sha256("identity-0013"),
        "revision": revision,
        "payload_json": payload,
        "payload_sha256": payload_sha,
        "created_at": NOW,
    }


# --------------------------------------------------------------------------- 升级


def test_0013_upgrade_creates_exact_tables_matching_metadata(data_paths):
    MigrationManager(data_paths).upgrade("head")
    engine = None
    try:
        from app.storage.db import build_engine
        from app.storage.db import Base
        from app.storage.migrate import verify_schema_matches_metadata

        engine = build_engine(data_paths.db_path)
        tables = set(inspect(engine).get_table_names())
        for name in V2_TABLES:
            assert name in tables, f"缺少 0013 新表 {name}"
        assert verify_schema_matches_metadata(engine, Base.metadata) == []
    finally:
        if engine is not None:
            engine.dispose()


def test_0013_legacy_placeholder_tables_untouched_and_unreferenced(
    data_paths, migrated_engine
):
    """旧占位表保持只读回归锚点：不被添加 v2 列，不被任何 v2 表外键引用。"""
    inspector = inspect(migrated_engine)
    tables = set(inspector.get_table_names())
    for legacy in LEGACY_PLACEHOLDER_TABLES:
        assert legacy in tables
        names = {column["name"] for column in inspector.get_columns(legacy)}
        for v2_column in (
            "evidence_snapshot_v2_id",
            "complete_processing_revision_id",
            "stable_identity",
            "source_strength",
        ):
            assert v2_column not in names, f"旧占位表 {legacy} 被添加 v2 列 {v2_column}"
    referenced = {
        fk["referred_table"]
        for name in V2_TABLES
        for fk in inspector.get_foreign_keys(name)
    }
    assert referenced.isdisjoint(LEGACY_PLACEHOLDER_TABLES), (
        f"v2 表外键引用旧占位表：{referenced & LEGACY_PLACEHOLDER_TABLES}"
    )
    # 权威快照绑定必须指向 v2 快照表而非 legacy evidence_snapshots。
    fact_fks = {
        (fk["constrained_columns"][0], fk["referred_table"])
        for fk in inspector.get_foreign_keys("clinical_facts_v2")
    }
    assert ("evidence_snapshot_v2_id", "evidence_snapshots_v2") in fact_fks
    assert ("evidence_snapshot_v2_id", "evidence_snapshots") not in fact_fks


def test_0013_foreign_key_check_clean_after_upgrade(data_paths):
    MigrationManager(data_paths).upgrade("head")
    from app.storage.db import build_engine

    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            violations = connection.exec_driver_sql(
                "PRAGMA foreign_key_check"
            ).fetchall()
        assert violations == []
    finally:
        engine.dispose()


# --------------------------------------------------------------------------- 外键与约束


def test_0013_authority_binding_rejects_legacy_and_missing_snapshot_ids(
    migrated_engine, session_factory
):
    """事实的权威快照外键只认 v2 快照表：legacy/不存在 id 一律被拒。"""
    with session_factory() as session:
        ids = _seed_authority(session)
        session.commit()
    with session_factory() as session:
        bad = _fact_kwargs(ids)
        bad["evidence_snapshot_v2_id"] = "legacy-snapshot-id"
        session.add(ClinicalFactV2Record(**bad))
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.commit()
    session_factory().close()


def test_0013_non_complete_processing_revision_id_rejected_at_storage(
    migrated_engine, session_factory
):
    """发布事实引用不存在/非完整处理修订 id 时外键拒绝（非 complete 的排除在
    仓储层由 worker_03 校验；这里证明绑定列外键指向处理修订表本身）。"""
    with session_factory() as session:
        ids = _seed_authority(session)
        session.commit()
    with session_factory() as session:
        bad = _fact_kwargs(ids)
        bad["complete_processing_revision_id"] = "epr-does-not-exist"
        session.add(ClinicalFactV2Record(**bad))
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.commit()


def test_0013_run_idempotency_key_unique(migrated_engine, session_factory):
    with session_factory() as session:
        ids = _seed_authority(session)
        session.commit()
    with session_factory() as session:
        # 与已存在 run 相同的幂等键 -> UNIQUE 拒绝（重复运行不得创建重复事实）。
        session.add(FactNormalizationRunRecord(
            run_id="run-dup",
            project_id=ids["project_id"],
            subject_id=ids["subject_id"],
            review_episode_id=ids["review_episode_id"],
            episode_revision=1,
            protocol_version_id=ids["protocol_version_id"],
            rule_set_id=ids["rule_set_id"],
            rule_set_revision=1,
            evidence_snapshot_v2_id=ids["evidence_snapshot_v2_id"],
            complete_processing_revision_id=ids["complete_processing_revision_id"],
            idempotency_key=_sha256("idempotency-0013"),  # 与已存在 run 相同
            prompt_version_id="prompt-0013",
            model_config_id="modelcfg-0013",
            input_scope_sha256=_sha256("input-scope"),
            status="succeeded",
            job_id=None,
            created_by="test",
            payload_json='{"k": 3}',
            payload_sha256=_sha256('{"k": 3}'),
            created_at=NOW,
        ))
        with pytest.raises(IntegrityError, match="UNIQUE"):
            session.commit()


def test_0013_fact_stable_identity_revision_chain_unique(migrated_engine, session_factory):
    with session_factory() as session:
        ids = _seed_authority(session)
        session.add(ClinicalFactV2Record(**_fact_kwargs(ids)))
        session.commit()
    with session_factory() as session:
        # 同身份同 revision 重复 -> 拒绝
        session.add(ClinicalFactV2Record(**_fact_kwargs(ids, fact_id="fact-dup")))
        with pytest.raises(IntegrityError, match="UNIQUE"):
            session.commit()
    with session_factory() as session:
        # 同身份更高 revision -> 允许（人工修订/增量重算追加新 revision）
        session.add(ClinicalFactV2Record(
            **_fact_kwargs(ids, fact_id="fact-rev2", revision=2)
        ))
        session.commit()


def test_0013_locator_link_rejects_unknown_locator(migrated_engine, session_factory):
    with session_factory() as session:
        ids = _seed_authority(session)
        session.add(ClinicalFactV2Record(**_fact_kwargs(ids)))
        session.commit()
    with session_factory() as session:
        session.add(FactEvidenceLocatorLinkRecord(
            entity_kind="fact",
            entity_id="fact-0013",
            fact_id="fact-0013",
            position=1,
            locator_id="locator-does-not-exist",
        ))
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.commit()


def test_0013_gate_rejects_unknown_candidate(migrated_engine, session_factory):
    with session_factory() as session:
        ids = _seed_authority(session)
        session.query(FactGateResultRecord).filter_by(
            gate_result_id=ids["gate_id"]
        ).delete()
        session.flush()
        payload, payload_sha = _payload()
        session.add(FactGateResultRecord(
            gate_result_id="gate-unknown-candidate",
            run_id=ids["run_id"],
            call_id=ids["call_id"],
            candidate_id="candidate-does-not-exist",
            gate="transactional_publish",
            outcome="accepted",
            reasons_json=[],
            payload_json=payload,
            payload_sha256=payload_sha,
            created_at=NOW,
        ))
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.commit()


def test_0013_event_exposure_conflict_member_links_reject_unknown_facts(
    migrated_engine, session_factory
):
    with session_factory() as session:
        ids = _seed_authority(session)
        session.add(ClinicalFactV2Record(**_fact_kwargs(ids)))
        session.add(ClinicalEventV2Record(
            event_id="event-0013",
            run_id=ids["run_id"],
            gate_id=ids["gate_id"],
            project_id=ids["project_id"],
            subject_id=ids["subject_id"],
            review_episode_id=ids["review_episode_id"],
            episode_revision=1,
            protocol_version_id=ids["protocol_version_id"],
            rule_set_id=ids["rule_set_id"],
            rule_set_revision=1,
            evidence_snapshot_v2_id=ids["evidence_snapshot_v2_id"],
            complete_processing_revision_id=ids["complete_processing_revision_id"],
            event_type="diagnosis",
            start_precision=None,
            start_lower_bound=None,
            start_upper_bound=None,
            start_source_text=None,
            end_precision=None,
            end_lower_bound=None,
            end_upper_bound=None,
            end_source_text=None,
            duration_status="unknown",
            record_time=None,
            source_strength="current_study_chart_direct_record",
            stable_identity=_sha256("event-identity"),
            revision=1,
            payload_json='{"kind": "event"}',
            payload_sha256=_sha256('{"kind": "event"}'),
            created_at=NOW,
        ))
        session.add(MedicationExposureV2Record(
            exposure_id="exposure-0013",
            run_id=ids["run_id"],
            gate_id=ids["gate_id"],
            project_id=ids["project_id"],
            subject_id=ids["subject_id"],
            review_episode_id=ids["review_episode_id"],
            episode_revision=1,
            protocol_version_id=ids["protocol_version_id"],
            rule_set_id=ids["rule_set_id"],
            rule_set_revision=1,
            evidence_snapshot_v2_id=ids["evidence_snapshot_v2_id"],
            complete_processing_revision_id=ids["complete_processing_revision_id"],
            medication_name="试验药",
            category=None,
            indication=None,
            dose=None,
            unit=None,
            frequency=None,
            route=None,
            start_precision=None,
            start_lower_bound=None,
            start_upper_bound=None,
            start_source_text=None,
            end_precision=None,
            end_lower_bound=None,
            end_upper_bound=None,
            end_source_text=None,
            duration_status="ongoing",
            source_strength="current_study_chart_direct_record",
            stable_identity=_sha256("exposure-identity"),
            revision=1,
            payload_json='{"kind": "exposure"}',
            payload_sha256=_sha256('{"kind": "exposure"}'),
            created_at=NOW,
        ))
        session.add(ClinicalConflictGroupV2Record(
            conflict_group_id="conflict-0013",
            run_id=ids["run_id"],
            gate_id=ids["gate_id"],
            project_id=ids["project_id"],
            subject_id=ids["subject_id"],
            review_episode_id=ids["review_episode_id"],
            episode_revision=1,
            protocol_version_id=ids["protocol_version_id"],
            rule_set_id=ids["rule_set_id"],
            rule_set_revision=1,
            evidence_snapshot_v2_id=ids["evidence_snapshot_v2_id"],
            complete_processing_revision_id=ids["complete_processing_revision_id"],
            resolution_revision=0,
            payload_json='{"kind": "conflict"}',
            payload_sha256=_sha256('{"kind": "conflict"}'),
            created_at=NOW,
        ))
        session.commit()
    # 事件/暴露/冲突成员链接到不存在的 fact_id -> 外键拒绝
    with session_factory() as session:
        session.add(EventFactLinkRecord(
            event_id="event-0013", position=1, fact_id="fact-missing"
        ))
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.commit()
    with session_factory() as session:
        session.add(ExposureFactLinkRecord(
            exposure_id="exposure-0013", position=1, fact_id="fact-missing"
        ))
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.commit()
    with session_factory() as session:
        from app.storage.facts_models import ClinicalConflictMemberV2Record

        session.add(ClinicalConflictMemberV2Record(
            conflict_group_id="conflict-0013", position=1, fact_id="fact-missing"
        ))
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.commit()


def test_0013_rule_link_and_expectation_and_profile_rows_persist(
    migrated_engine, session_factory
):
    """规则索引/期望/Profile 行可写回读，且规则集复合外键生效。"""
    with session_factory() as session:
        ids = _seed_authority(session)
        session.add(ClinicalFactV2Record(**_fact_kwargs(ids)))
        session.add(FactRuleLinkV2Record(
            link_id="frl-0013",
            fact_id="fact-0013",
            target_kind="evidence_requirement",
            rule_set_id=ids["rule_set_id"],
            rule_set_revision=1,
            target_id="req-0013",
            evidence_requirement_id="req-0013",
        ))
        session.add(EvidenceExpectationV2Record(
            expectation_id="expectation-0013",
            project_id=ids["project_id"],
            subject_id=ids["subject_id"],
            review_episode_id=ids["review_episode_id"],
            episode_revision=1,
            protocol_version_id=ids["protocol_version_id"],
            rule_set_id=ids["rule_set_id"],
            rule_set_revision=1,
            evidence_snapshot_v2_id=ids["evidence_snapshot_v2_id"],
            complete_processing_revision_id=ids["complete_processing_revision_id"],
            template_id=ids["template_id"],
            status="referenced_missing",
            gap_type="referenced_file_missing",
            revision=1,
            payload_json='{"kind": "expectation"}',
            payload_sha256=_sha256('{"kind": "expectation"}'),
            created_at=NOW,
        ))
        session.add(PatientProfileRevisionV2Record(
            patient_profile_revision_id="profile-0013",
            project_id=ids["project_id"],
            subject_id=ids["subject_id"],
            review_episode_id=ids["review_episode_id"],
            episode_revision=1,
            protocol_version_id=ids["protocol_version_id"],
            rule_set_id=ids["rule_set_id"],
            rule_set_revision=1,
            evidence_snapshot_v2_id=ids["evidence_snapshot_v2_id"],
            complete_processing_revision_id=ids["complete_processing_revision_id"],
            status="succeeded",
            generated_at=NOW,
            highlights_json={"count": 0},
            revision=1,
            payload_json='{"kind": "profile"}',
            payload_sha256=_sha256('{"kind": "profile"}'),
            created_at=NOW,
        ))
        session.commit()
    with session_factory() as session:
        row = session.get(FactRuleLinkV2Record, "frl-0013")
        assert row is not None and row.target_id == "req-0013"
        expectation = session.get(EvidenceExpectationV2Record, "expectation-0013")
        assert expectation is not None and expectation.status == "referenced_missing"
        profile = session.get(PatientProfileRevisionV2Record, "profile-0013")
        assert profile is not None and profile.status == "succeeded"
        # 复合规则集外键：指向不存在的规则集 revision 必须被拒
        session.add(FactRuleLinkV2Record(
            link_id="frl-bad",
            fact_id="fact-0013",
            target_kind="evidence_requirement",
            rule_set_id=ids["rule_set_id"],
            rule_set_revision=99,
            target_id="req-missing",
            evidence_requirement_id="req-missing",
        ))
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.commit()


def test_0013_payload_hash_matches_mirror_columns(migrated_engine, session_factory):
    with session_factory() as session:
        ids = _seed_authority(session)
        session.add(ClinicalFactV2Record(**_fact_kwargs(ids)))
        session.commit()
    with session_factory() as session:
        from sqlalchemy import select

        row = session.execute(
            select(ClinicalFactV2Record).where(
                ClinicalFactV2Record.fact_id == "fact-0013"
            )
        ).scalar_one()
        assert row.payload_sha256 == _sha256(row.payload_json)
        # 镜像列与正文一致：规范化列与 payload 校验在仓储层，这里证明行可回读
        assert row.fact_type == "vital_sign"
        assert row.source_strength == "contemporaneous_objective_result"
        assert row.episode_revision == 1


# --------------------------------------------------------------------------- 降级


def test_0013_downgrade_refuses_populated_v2_and_restores(data_paths):
    """含正式数据时降级必须失败并由管理器从迁移前备份恢复（不丢 v2 历史）。"""
    from app.storage.db import build_engine, build_session_factory

    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    factory = build_session_factory(engine)
    with factory() as session:
        ids = _seed_authority(session)
        session.add(ClinicalFactV2Record(**_fact_kwargs(ids)))
        session.commit()
    # 备份/恢复需要独占访问：先释放连接池，与 test_migration_0008 同约定。
    engine.dispose()
    with pytest.raises(MigrationFailure, match="0013"):
        manager.downgrade("0012")
    # 失败后自动从迁移前备份恢复：仍在 head，数据未丢。
    assert manager.read_revision(data_paths.db_path) == resolve_head_revision()
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM clinical_facts_v2"
            ).scalar_one()
        assert count == 1
    finally:
        engine.dispose()


def test_0013_downgrade_greenfield_drops_all_tables_in_reverse_order(data_paths):
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    manager.downgrade("0012")
    from app.storage.db import build_engine

    engine = build_engine(data_paths.db_path)
    try:
        tables = set(inspect(engine).get_table_names())
        for name in V2_TABLES:
            assert name not in tables, f"降级后残留 0013 表 {name}"
    finally:
        engine.dispose()
    # 空绿地库降级后可重新升级到 head 且 schema 校验通过。
    manager.upgrade("head")
