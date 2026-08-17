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
    EvidenceExpectationTemplateRecord,
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


def _seed_template_context(session):
    """建立一份可发布 RuleSet、其审核节点和确定性模板。"""
    from app.projections.evidence_expectation_templates import (
        project_evidence_expectation_templates,
    )
    from app.storage.repositories import WORKFLOW_STAGE_CONFIG

    _seed_document_version(session)
    rule_set = _rule_set()
    procedure = _procedure_requirements()
    save_rule_set(session, rule_set, procedure_requirements=procedure)
    stages = [
        WorkflowStage(
            workflow_stage_id="ruleset:slice4:1:stage-screening",
            stage=ReviewStage.SCREENING,
            display_name="筛选期审核",
            visit_instance="筛选期 D-28~D-1",
            due_requirement_ids=["req-in", "req-ex", "requirement:procedure:screen"],
        ),
        WorkflowStage(
            workflow_stage_id="ruleset:slice4:1:stage-baseline",
            stage=ReviewStage.BASELINE,
            display_name="基线审核",
            visit_instance="基线 D1",
            due_requirement_ids=["requirement:procedure:baseline"],
        ),
    ]
    for stage in stages:
        AppendRepository(session, WORKFLOW_STAGE_CONFIG).save(
            stage,
            scope={
                "protocol_version_id": "protocol-version-1",
                "study_phase": rule_set.study_phase.value,
            },
        )
    return rule_set, stages, project_evidence_expectation_templates(
        rule_set=rule_set,
        workflow_stages=stages,
        procedure_requirements=procedure,
        created_at=NOW,
    )


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
            visit_instance="筛选期 D-28~D-1",
            due_requirement_ids=["req-in", "requirement:procedure:screen"],
        ),
        WorkflowStage(
            workflow_stage_id="ruleset:slice4:1:stage-baseline",
            stage=ReviewStage.BASELINE,
            display_name="基线审核",
            visit_instance="基线 D1",
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
    # 模板引用完整性：先落库 RuleSet revision 与审核节点，模板才能引用。
    from app.storage.repositories import WORKFLOW_STAGE_CONFIG

    for stage in (
        WorkflowStage(
            workflow_stage_id="ruleset:slice4:1:stage-screening",
            stage=ReviewStage.SCREENING,
            display_name="筛选期审核",
            visit_instance="筛选期 D-28~D-1",
            due_requirement_ids=["req-in", "requirement:procedure:screen"],
        ),
        WorkflowStage(
            workflow_stage_id="ruleset:slice4:1:stage-baseline",
            stage=ReviewStage.BASELINE,
            display_name="基线审核",
            visit_instance="基线 D1",
            due_requirement_ids=["requirement:procedure:baseline"],
        ),
    ):
        AppendRepository(session, WORKFLOW_STAGE_CONFIG).save(
            stage,
            scope={
                "protocol_version_id": "protocol-version-1",
                "study_phase": rule_set.study_phase.value,
            },
        )
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

    from app.projections.evidence_expectation_templates import (
        project_evidence_expectation_templates,
    )

    stages = [
        WorkflowStage(
            workflow_stage_id="ruleset:slice4:1:stage-screening",
            stage=ReviewStage.SCREENING,
            display_name="筛选期审核",
            visit_instance="筛选期 D-28~D-1",
            due_requirement_ids=["req-in", "req-ex", "requirement:procedure:screen"],
        ),
        WorkflowStage(
            workflow_stage_id="ruleset:slice4:1:stage-baseline",
            stage=ReviewStage.BASELINE,
            display_name="基线审核",
            visit_instance="基线 D1",
            due_requirement_ids=["requirement:procedure:baseline"],
        ),
    ]
    valid = next(
        item
        for item in project_evidence_expectation_templates(
            rule_set=rule_set,
            workflow_stages=stages,
            procedure_requirements=_procedure_requirements(),
            created_at=NOW,
        )
        if item.requirement_id == "req-in"
    )
    save_expectation_templates(session, [valid])
    session.flush()
    loaded = list_expectation_templates(session, rule_set.rule_set_id, 1)
    assert [item.requirement_id for item in loaded] == ["req-in"]
    # 同一 (rule_set, revision, requirement) 幂等跳过
    save_expectation_templates(session, [valid])
    session.flush()
    assert len(list_expectation_templates(session, rule_set.rule_set_id, 1)) == 1


def _valid_template(rule_set, requirement_id="req-in", stage_id="ruleset:slice4:1:stage-screening"):
    from app.projections.evidence_expectation_templates import (
        template_identity,
        template_projection_sha256,
    )

    return EvidenceExpectationTemplate(
        template_id=template_identity(rule_set.rule_set_id, 1, requirement_id),
        rule_set_id=rule_set.rule_set_id,
        rule_set_revision=1,
        requirement_id=requirement_id,
        due_stage=ReviewStage.SCREENING,
        study_phase=rule_set.study_phase,
        workflow_stage_id=stage_id,
        fact_type="方案要求事实",
        description="核对正式原始资料",
        projection_sha256=template_projection_sha256(
            rule_set_id=rule_set.rule_set_id,
            revision=1,
            requirement_id=requirement_id,
            due_stage=ReviewStage.SCREENING,
            study_phase=rule_set.study_phase,
            workflow_stage_id=stage_id,
            fact_type="方案要求事实",
            required_source_types=[],
            requires_contemporaneous_objective_source=False,
            allows_screening_record_transcription=True,
            description="核对正式原始资料",
        ),
        created_at=NOW,
    )


def test_ghost_rule_set_revision_template_is_rejected(session) -> None:
    """模板引用不存在的 RuleSet revision -> 拒绝（杜绝孤儿模板）。"""
    _seed_document_version(session)
    rule_set = _rule_set()
    ghost = _valid_template(rule_set)
    ghost = ghost.model_copy(update={"rule_set_revision": 99})
    # 重新计算 revision=99 的稳定投影哈希，让合同校验通过后由仓储拒绝幽灵引用。
    from app.projections.evidence_expectation_templates import (
        template_identity,
        template_projection_sha256,
    )

    ghost = ghost.model_copy(
        update={
            "template_id": template_identity(rule_set.rule_set_id, 99, "req-in"),
            "projection_sha256": template_projection_sha256(
                rule_set_id=rule_set.rule_set_id,
                revision=99,
                requirement_id="req-in",
                due_stage=ReviewStage.SCREENING,
                study_phase=rule_set.study_phase,
                workflow_stage_id="ruleset:slice4:1:stage-screening",
                fact_type="方案要求事实",
                required_source_types=[],
                requires_contemporaneous_objective_source=False,
                allows_screening_record_transcription=True,
                description="核对正式原始资料",
            ),
        }
    )
    from app.storage.repositories import InvalidReferenceError

    with pytest.raises(InvalidReferenceError, match="RuleSet"):
        save_expectation_templates(session, [ghost])


def test_ghost_requirement_template_is_rejected(session) -> None:
    """模板引用该 RuleSet revision 中不存在的资料要求 -> 拒绝。"""
    _seed_document_version(session)
    rule_set = _rule_set()
    save_rule_set(session, rule_set, procedure_requirements=_procedure_requirements())
    from app.storage.repositories import WORKFLOW_STAGE_CONFIG

    AppendRepository(session, WORKFLOW_STAGE_CONFIG).save(
        WorkflowStage(
            workflow_stage_id="ruleset:slice4:1:stage-screening",
            stage=ReviewStage.SCREENING,
            display_name="筛选期审核",
            visit_instance="筛选期 D-28~D-1",
            due_requirement_ids=["req-in", "requirement:procedure:screen"],
        ),
        scope={
            "protocol_version_id": "protocol-version-1",
            "study_phase": rule_set.study_phase.value,
        },
    )
    ghost = _valid_template(rule_set, requirement_id="requirement:ghost")
    from app.storage.repositories import InvalidReferenceError

    with pytest.raises(InvalidReferenceError, match="资料要求"):
        save_expectation_templates(session, [ghost])


def test_cross_revision_draft_chain_is_rejected(session) -> None:
    """草稿 revision 的前序必须属于同一草稿且紧邻；跨草稿/跨号拼接被拒。"""
    _source_input, draft, _spans = confirmed_fixture()
    other_draft = draft.model_copy(deep=True)
    other_draft.draft_id = "draft-other"
    repo = ProtocolDraftRevisionRepository(session)
    r1 = ProtocolDraftRevision(
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
    repo.save(r1)
    session.flush()
    # 另一草稿的首稿先落库，随后跨草稿引用它 -> 拒绝
    other_r1 = ProtocolDraftRevision(
        revision_id="draft-revision:other:1",
        draft_id="draft-other",
        revision_number=1,
        project_id=other_draft.project_id,
        protocol_version_id=other_draft.protocol_version_id,
        study_phase=other_draft.selected_phase,
        status=DraftRevisionStatus.SAVED,
        reason=DraftRevisionReason.INITIAL_SAVE,
        actor="医学监查员",
        content=other_draft,
        content_sha256=canonical_hash(other_draft.model_dump(mode="json")),
        created_at=NOW,
    )
    repo.save(other_r1)
    session.flush()
    cross = ProtocolDraftRevision(
        revision_id="draft-revision:draft-1:2",
        draft_id="draft-1",
        revision_number=2,
        previous_revision_id="draft-revision:other:1",
        project_id=draft.project_id,
        protocol_version_id=draft.protocol_version_id,
        study_phase=draft.selected_phase,
        status=DraftRevisionStatus.SAVED,
        reason=DraftRevisionReason.MANUAL_EDIT,
        actor="医学监查员",
        content=draft.model_copy(
            update={"draft_revision": 2, "previous_draft_id": "draft-1"}
        ),
        content_sha256=canonical_hash(
            draft.model_copy(
                update={"draft_revision": 2, "previous_draft_id": "draft-1"}
            ).model_dump(mode="json")
        ),
        created_at=NOW,
    )
    from app.storage.repositories import ScopeViolationError

    with pytest.raises(ScopeViolationError, match="前序"):
        repo.save(cross)
    # 非紧邻前序：previous 是 r1 但声明 revision_number=3 -> 拒绝
    non_adjacent = ProtocolDraftRevision(
        revision_id="draft-revision:draft-1:3",
        draft_id="draft-1",
        revision_number=3,
        previous_revision_id=r1.revision_id,
        project_id=draft.project_id,
        protocol_version_id=draft.protocol_version_id,
        study_phase=draft.selected_phase,
        status=DraftRevisionStatus.SAVED,
        reason=DraftRevisionReason.MANUAL_EDIT,
        actor="医学监查员",
        content=draft.model_copy(
            update={"draft_revision": 3, "previous_draft_id": "draft-1"}
        ),
        content_sha256=canonical_hash(
            draft.model_copy(
                update={"draft_revision": 3, "previous_draft_id": "draft-1"}
            ).model_dump(mode="json")
        ),
        created_at=NOW,
    )
    with pytest.raises(ScopeViolationError, match="紧邻"):
        repo.save(non_adjacent)


def _rehash_template(template, **changes):
    """模拟一个自洽哈希但语义被改写的模板。"""
    from app.projections.evidence_expectation_templates import (
        template_projection_sha256,
    )

    changed = template.model_copy(update=changes)
    return changed.model_copy(
        update={
            "projection_sha256": template_projection_sha256(
                rule_set_id=changed.rule_set_id,
                revision=changed.rule_set_revision,
                requirement_id=changed.requirement_id,
                due_stage=changed.due_stage,
                study_phase=changed.study_phase,
                workflow_stage_id=changed.workflow_stage_id,
                fact_type=changed.fact_type,
                required_source_types=changed.required_source_types,
                requires_contemporaneous_objective_source=(
                    changed.requires_contemporaneous_objective_source
                ),
                allows_screening_record_transcription=(
                    changed.allows_screening_record_transcription
                ),
                description=changed.description,
            )
        }
    )


def test_template_self_hash_cannot_override_requirement_semantics(session) -> None:
    from app.storage.repositories import ScopeViolationError

    _rule_set_value, _stages, templates = _seed_template_context(session)
    valid = next(item for item in templates if item.requirement_id == "req-in")
    forged = _rehash_template(valid, required_source_types=["伪造的资料类型"])
    with pytest.raises(ScopeViolationError, match="资料语义"):
        save_expectation_templates(session, [forged])


def test_template_cannot_borrow_stage_from_another_ruleset(session) -> None:
    from app.storage.repositories import ScopeViolationError, WORKFLOW_STAGE_CONFIG

    _rule_set_value, _stages, templates = _seed_template_context(session)
    valid = next(item for item in templates if item.requirement_id == "req-in")
    foreign_stage = WorkflowStage(
        workflow_stage_id="ruleset:other:1:stage-screening",
        stage=ReviewStage.SCREENING,
        display_name="其他规则集筛选节点",
        visit_instance="筛选期 D-28~D-1",
        due_requirement_ids=[valid.requirement_id],
    )
    AppendRepository(session, WORKFLOW_STAGE_CONFIG).save(
        foreign_stage,
        scope={
            "protocol_version_id": "protocol-version-1",
            "study_phase": StudyPhase.PHASE_II.value,
        },
    )
    forged = _rehash_template(
        valid, workflow_stage_id=foreign_stage.workflow_stage_id
    )
    with pytest.raises(ScopeViolationError, match="RuleSet revision"):
        save_expectation_templates(session, [forged])


def test_existing_wrong_template_is_not_silently_skipped(session) -> None:
    from app.storage.repositories import (
        EVIDENCE_EXPECTATION_TEMPLATE_CONFIG,
        ScopeViolationError,
    )

    _rule_set_value, _stages, templates = _seed_template_context(session)
    valid = next(item for item in templates if item.requirement_id == "req-in")
    forged = _rehash_template(valid, description="被改写的模板描述")
    # 模拟历史错误投影已写入；重复构建必须识别冲突，不能见到唯一键就跳过。
    AppendRepository(session, EVIDENCE_EXPECTATION_TEMPLATE_CONFIG).save(forged)
    with pytest.raises(ScopeViolationError, match="拒绝静默跳过"):
        save_expectation_templates(session, [valid])


def test_template_requires_workflow_stage_and_ruleset_phase(session) -> None:
    from app.storage.repositories import ScopeViolationError

    _rule_set_value, _stages, templates = _seed_template_context(session)
    valid = next(item for item in templates if item.requirement_id == "req-in")
    without_stage = _rehash_template(valid, workflow_stage_id=None)
    with pytest.raises(Exception, match="workflow_stage_id"):
        save_expectation_templates(session, [without_stage])

    wrong_phase = _rehash_template(valid, study_phase=StudyPhase.PHASE_III)
    with pytest.raises(ScopeViolationError, match="研究期别"):
        save_expectation_templates(session, [wrong_phase])


def test_revision_replace_and_status_update_reject_existing_mirror_drift(
    session,
) -> None:
    from app.storage.repositories import ScopeViolationError

    _source_input, draft, _spans = confirmed_fixture()
    repo = ProtocolDraftRevisionRepository(session)
    revision = ProtocolDraftRevision(
        revision_id="draft-revision:draft-1:1",
        draft_id=draft.draft_id,
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
    repo.save(revision)

    detached_content = draft.model_copy(update={"project_id": "project-other"})
    detached = revision.model_copy(
        update={
            "project_id": "project-other",
            "content": detached_content,
            "content_sha256": canonical_hash(
                detached_content.model_dump(mode="json")
            ),
        }
    )
    with pytest.raises(ScopeViolationError, match="project_id"):
        repo.replace(detached)
    with pytest.raises(ScopeViolationError, match="project_id"):
        repo.update_status(
            detached.model_copy(update={"status": DraftRevisionStatus.CANCELLED})
        )
    # 两次拒绝均发生在写前，原 revision 仍可读取且身份未变。
    loaded = repo.get(revision.revision_id)
    assert loaded.project_id == draft.project_id
    assert loaded.status == DraftRevisionStatus.SAVED


@pytest.mark.parametrize(
    ("field_name", "new_value"),
    [
        (
            "diff",
            ProtocolDraftRevision.model_fields["diff"].default_factory().model_copy(
                update={"source_scope_changed": True}
            ),
        ),
        ("feedback_note", "状态转换时偷改的反馈说明"),
        ("created_at", NOW.replace(day=18)),
    ],
)
def test_status_update_cannot_rewrite_audit_payload(
    session, field_name, new_value
) -> None:
    from app.storage.repositories import ScopeViolationError

    _source_input, draft, _spans = confirmed_fixture()
    repo = ProtocolDraftRevisionRepository(session)
    revision = ProtocolDraftRevision(
        revision_id="draft-revision:audit-only:1",
        draft_id=draft.draft_id,
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
    repo.save(revision)

    changed = revision.model_copy(
        update={
            "status": DraftRevisionStatus.CANCELLED,
            field_name: new_value,
        }
    )
    expected_message = "created_at" if field_name == "created_at" else "只能改变 status"
    with pytest.raises(ScopeViolationError, match=expected_message):
        repo.update_status(changed)

    assert repo.get(revision.revision_id) == revision


def test_revision_list_cannot_hide_normalized_column_drift(session) -> None:
    from app.storage.codecs import PersistedContractInvalid

    _source_input, draft, _spans = confirmed_fixture()
    repo = ProtocolDraftRevisionRepository(session)
    revision = ProtocolDraftRevision(
        revision_id="draft-revision:list-drift:1",
        draft_id=draft.draft_id,
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
    repo.save(revision)
    row = session.get(ProtocolDraftRevisionRecord, revision.revision_id)
    row.draft_id = "被篡改后不再命中查询的草稿"
    session.flush()

    with pytest.raises(PersistedContractInvalid, match="draft_id"):
        repo.list_by_draft(revision.draft_id)
    with pytest.raises(PersistedContractInvalid, match="draft_id"):
        repo.get_head(revision.draft_id)


def test_revision_created_at_is_immutable_and_mirrored_on_every_read(session) -> None:
    from app.storage.codecs import PersistedContractInvalid
    from app.storage.repositories import ScopeViolationError

    _source_input, draft, _spans = confirmed_fixture()
    repo = ProtocolDraftRevisionRepository(session)
    revision = ProtocolDraftRevision(
        revision_id="draft-revision:created-at:1",
        draft_id=draft.draft_id,
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
    repo.save(revision)

    with pytest.raises(ScopeViolationError, match="created_at"):
        repo.replace(revision.model_copy(update={"created_at": NOW.replace(day=18)}))

    row = session.get(ProtocolDraftRevisionRecord, revision.revision_id)
    row.created_at = NOW.replace(tzinfo=None, day=19)
    session.flush()
    with pytest.raises(PersistedContractInvalid, match="created_at"):
        repo.get(revision.revision_id)
    with pytest.raises(PersistedContractInvalid, match="created_at"):
        repo.list_by_draft(revision.draft_id)
    with pytest.raises(PersistedContractInvalid, match="created_at"):
        repo.get_head(revision.draft_id)


def test_template_list_cannot_hide_normalized_column_drift(session) -> None:
    from app.storage.codecs import PersistedContractInvalid

    rule_set, _stages, templates = _seed_template_context(session)
    valid = next(item for item in templates if item.requirement_id == "req-in")
    save_expectation_templates(session, [valid])
    row = session.get(EvidenceExpectationTemplateRecord, valid.template_id)
    row.fact_type = "被篡改后不再反映正文的资料类型"
    session.flush()

    with pytest.raises(PersistedContractInvalid, match="fact_type"):
        list_expectation_templates(session, rule_set.rule_set_id, 1)


def test_template_created_at_is_mirrored_on_direct_and_list_reads(session) -> None:
    from app.storage.codecs import PersistedContractInvalid
    from app.storage.repositories import EVIDENCE_EXPECTATION_TEMPLATE_CONFIG

    rule_set, _stages, templates = _seed_template_context(session)
    valid = next(item for item in templates if item.requirement_id == "req-in")
    save_expectation_templates(session, [valid])
    row = session.get(EvidenceExpectationTemplateRecord, valid.template_id)
    row.created_at = NOW.replace(tzinfo=None, day=19)
    session.flush()

    with pytest.raises(PersistedContractInvalid, match="created_at"):
        AppendRepository(session, EVIDENCE_EXPECTATION_TEMPLATE_CONFIG).get(
            valid.template_id
        )
    with pytest.raises(PersistedContractInvalid, match="created_at"):
        list_expectation_templates(session, rule_set.rule_set_id, 1)
