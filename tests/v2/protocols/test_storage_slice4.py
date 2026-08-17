"""切片 4 存储层：资料要求来源列、审核节点期别、草稿 revision 与模板投影。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.domain.contracts.enums import (
    DatePrecision,
    ReviewStage,
    StudyPhase,
)
from app.domain.contracts.evidence import EvidenceExpectationTemplate
from app.domain.contracts.protocol_drafts import (
    DraftRevisionReason,
    DraftRevisionStatus,
    ProtocolDraftRevision,
)
from app.domain.contracts.rules import EvidenceRequirement, RuleSet, WorkflowStage
from app.domain.publication import canonical_hash
from app.storage.models import (
    EvidenceRequirementRecord,
    ProtocolDraftRevisionRecord,
    WorkflowStageRecord,
)
from app.storage.repositories import (
    AppendRepository,
    ProtocolDraftRevisionRepository,
    get_evidence_requirement,
    list_expectation_templates,
    save_expectation_templates,
    save_rule_set,
)
from tests.v2.protocols.slice4_helpers import NOW, confirmed_fixture

from app.domain.contracts.common import DateValue
from app.domain.contracts.review import ProtocolDocumentVersion
from app.storage.repositories import PROTOCOL_DOC_CONFIG


def _seed_document_version(session, version_id: str = "protocol-version-1") -> None:
    AppendRepository(session, PROTOCOL_DOC_CONFIG).save(
        ProtocolDocumentVersion(
            protocol_version_id=version_id,
            protocol_code="TEST-001",
            official_version="V1.0",
            official_date=DateValue(value=None, precision=DatePrecision.UNKNOWN),
            sha256="b" * 64,
            integrity_manifest_sha256="0" * 64,
            authority_record_sha256="0" * 64,
            authority_confirmation_id="confirmation-seed",
            authority_gate_result_id="gate-seed",
            integrity_gate_result_id="gate-seed-2",
        )
    )


def _rule_set(study_phase=StudyPhase.PHASE_II) -> RuleSet:
    _source_input, draft, _spans = confirmed_fixture()
    return RuleSet(
        rule_set_id="ruleset:slice4",
        protocol_version_id="protocol-version-1",
        study_phase=study_phase,
        rules=draft.proposed_rules,
        revision=1,
    )


def _procedure_requirements() -> list[EvidenceRequirement]:
    return [
        EvidenceRequirement(
            requirement_id="requirement:procedure:screen",
            procedure_catalog_item_id="procedure:screening:lab",
            fact_type="方案要求事实",
            due_stage=ReviewStage.SCREENING,
            description="核对筛选期正式原始资料",
        ),
        EvidenceRequirement(
            requirement_id="requirement:procedure:baseline",
            procedure_catalog_item_id="procedure:baseline:lab",
            fact_type="方案要求事实",
            due_stage=ReviewStage.BASELINE,
            description="核对基线正式原始资料",
        ),
    ]


def test_rule_set_persists_procedure_origin_without_fabricated_component(session) -> None:
    """根缺陷回归：流程资料要求不再伪造规则组件来源。"""
    _seed_document_version(session)
    rule_set = _rule_set()
    procedure_requirements = _procedure_requirements()
    save_rule_set(session, rule_set, procedure_requirements=procedure_requirements)
    session.flush()

    component_origin = get_evidence_requirement(
        session, rule_set.rule_set_id, 1, "req-in"
    )
    assert component_origin.rule_component_id == "component-in"
    assert component_origin.procedure_catalog_item_id is None

    procedure_origin = get_evidence_requirement(
        session, rule_set.rule_set_id, 1, "requirement:procedure:screen"
    )
    assert procedure_origin.procedure_catalog_item_id == "procedure:screening:lab"
    assert procedure_origin.rule_component_id is None

    rows = session.execute(
        select(EvidenceRequirementRecord).where(
            EvidenceRequirementRecord.rule_set_id == rule_set.rule_set_id,
            EvidenceRequirementRecord.rule_set_revision == 1,
        )
    ).scalars().all()
    assert len(rows) == 4  # 2 组件 + 2 流程
    origins = {(row.rule_component_id, row.procedure_catalog_item_id) for row in rows}
    assert all(
        (left is None) != (right is None) for left, right in origins
    ), "每个资料要求必须且只能绑定一个来源"


def test_repository_rejects_both_or_no_origin(session) -> None:
    _seed_document_version(session)
    rule_set = _rule_set()
    with pytest.raises(Exception):
        save_rule_set(
            session,
            rule_set,
            procedure_requirements=[
                EvidenceRequirement(
                    requirement_id="requirement:bad",
                    rule_component_id="component-in",
                    procedure_catalog_item_id="procedure:screening:lab",
                    fact_type="方案要求事实",
                    due_stage=ReviewStage.SCREENING,
                    description="双重来源必须拒绝",
                )
            ],
        )
    with pytest.raises(Exception):
        save_rule_set(
            session,
            rule_set,
            procedure_requirements=[
                EvidenceRequirement(
                    requirement_id="requirement:none",
                    fact_type="方案要求事实",
                    due_stage=ReviewStage.SCREENING,
                    description="无来源必须拒绝",
                )
            ],
        )


def test_workflow_stage_persists_study_phase_and_visit_identity(session) -> None:
    """同名操作在筛选与基线保持两个独立节点，并按期别隔离。"""
    _seed_document_version(session)
    rule_set = _rule_set()
    save_rule_set(session, rule_set, procedure_requirements=_procedure_requirements())
    stages = [
        WorkflowStage(
            workflow_stage_id="ruleset:slice4:1:stage-screening",
            stage=ReviewStage.SCREENING,
            display_name="筛选期审核",
            due_requirement_ids=["req-in", "requirement:procedure:screen"],
        ),
        WorkflowStage(
            workflow_stage_id="ruleset:slice4:1:stage-baseline",
            stage=ReviewStage.BASELINE,
            display_name="基线审核",
            due_requirement_ids=["requirement:procedure:baseline"],
        ),
    ]
    from app.storage.repositories import WORKFLOW_STAGE_CONFIG

    for stage in stages:
        AppendRepository(session, WORKFLOW_STAGE_CONFIG).save(
            stage,
            scope={
                "protocol_version_id": "protocol-version-1",
                "study_phase": rule_set.study_phase.value,
            },
        )
    session.flush()
    rows = session.execute(
        select(WorkflowStageRecord).order_by(WorkflowStageRecord.stage)
    ).scalars().all()
    assert [row.stage for row in rows] == ["baseline", "screening"]
    assert all(row.study_phase == StudyPhase.PHASE_II.value for row in rows)
    assert rows[0].workflow_stage_id != rows[1].workflow_stage_id


def test_draft_revision_repository_roundtrip_and_head(session) -> None:
    _source_input, draft, _spans = confirmed_fixture()
    revision = ProtocolDraftRevision(
        revision_id="draft-revision:draft-1:1",
        draft_id="draft-1",
        revision_number=1,
        project_id=draft.project_id,
        protocol_version_id=draft.protocol_version_id,
        study_phase=draft.selected_phase,
        status=DraftRevisionStatus.SAVED,
        reason=DraftRevisionReason.INITIAL_SAVE,
        actor="医学监查员",
        content=draft,
        content_sha256=canonical_hash(draft.model_dump(mode="json")),
        created_at=NOW,
    )
    repo = ProtocolDraftRevisionRepository(session)
    repo.save(revision)
    session.flush()
    loaded = repo.get(revision.revision_id)
    assert loaded == revision
    assert repo.get_head("draft-1").revision_id == revision.revision_id
    assert repo.count("draft-1") == 1


def test_draft_revision_content_hash_is_verified_on_read(session) -> None:
    _source_input, draft, _spans = confirmed_fixture()
    row = ProtocolDraftRevisionRecord(
        revision_id="draft-revision:draft-x:1",
        draft_id="draft-x",
        revision_number=1,
        project_id=draft.project_id,
        protocol_version_id=draft.protocol_version_id,
        study_phase=draft.selected_phase.value,
        status=DraftRevisionStatus.SAVED.value,
        reason=DraftRevisionReason.INITIAL_SAVE.value,
        feedback_kind=None,
        actor="a",
        content_sha256="0" * 64,
        payload_json="{}",
        payload_sha256="0" * 64,
        created_at=NOW,
    )
    session.add(row)
    session.flush()
    from app.storage.codecs import PersistedContractInvalid

    with pytest.raises(PersistedContractInvalid):
        ProtocolDraftRevisionRepository(session).get(row.revision_id)


def test_expectation_template_repository_dedup_and_identity(session) -> None:
    _seed_document_version(session)
    rule_set = _rule_set()
    save_rule_set(session, rule_set, procedure_requirements=_procedure_requirements())
    from app.projections.evidence_expectation_templates import (
        template_identity,
        template_projection_sha256,
    )

    # 模板 ID/投影哈希必须与稳定身份一致，否则合同拒绝。
    forged = EvidenceExpectationTemplate.model_construct(
        template_id="expectation-template:" + "a" * 32,
        rule_set_id=rule_set.rule_set_id,
        rule_set_revision=1,
        requirement_id="req-in",
        due_stage=ReviewStage.SCREENING,
        study_phase=StudyPhase.PHASE_II,
        workflow_stage_id="ruleset:slice4:1:stage-screening",
        fact_type="方案要求事实",
        description="核对正式原始资料",
        projection_sha256="0" * 64,
        created_at=NOW,
    )
    with pytest.raises(Exception):
        save_expectation_templates(session, [forged])

    valid = forged.model_copy(
        update={
            "template_id": template_identity(
                rule_set.rule_set_id, 1, "req-in"
            ),
            "projection_sha256": template_projection_sha256(
                rule_set_id=rule_set.rule_set_id,
                revision=1,
                requirement_id="req-in",
                due_stage=ReviewStage.SCREENING,
                study_phase=StudyPhase.PHASE_II,
                workflow_stage_id="ruleset:slice4:1:stage-screening",
            ),
        }
    )
    save_expectation_templates(session, [valid])
    session.flush()
    loaded = list_expectation_templates(session, rule_set.rule_set_id, 1)
    assert [item.requirement_id for item in loaded] == ["req-in"]
    # 同一 (rule_set, revision, requirement) 幂等跳过
    save_expectation_templates(session, [valid])
    session.flush()
    assert len(list_expectation_templates(session, rule_set.rule_set_id, 1)) == 1
