"""原子幂等发布服务：正式权威链、回滚、幂等、谱系与完整性哈希。"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import CatalogKind, DatePrecision
from app.domain.contracts.rules import RestrictedRuleComponent
from app.domain.publication import canonical_hash
from app.projections.clause_pack import project_clause_pack, verify_clause_pack
from app.services.protocol_draft_service import ProtocolDraftService
from app.services.eligibility_review_projection import _restricted_clause_projection
from app.services.protocol_publication_service import (
    DuplicateFirstProjectError,
    ProtocolPublicationRequest,
    ProtocolPublicationService,
    PublicationGateError,
    PublicationLineageError,
)
from app.storage.concurrency import StaleRevisionError
from app.storage.idempotency import IdempotencyConflict
from app.storage.models import (
    EvidenceExpectationTemplateRecord,
    EvidenceRequirementRecord,
    IdempotencyRecordRow,
    ProjectRecord,
    ProtocolAuthorityConfirmationRecord,
    ProtocolAuthorityRecordRow,
    ProtocolIntegrityManifestRecord,
    ProtocolSourceRecordRow,
    RuleSetRecord,
    ServiceCommandEventRecord,
    WorkflowStageRecord,
)
from app.storage.repositories import (
    AppendRepository,
    AUTHORITY_RECORD_CONFIG,
    ProtocolDraftRevisionRepository,
    get_rule_set,
    list_expectation_templates,
)

from tests.v2.protocols.slice4_helpers import NOW, confirmed_fixture
from tests.v2.protocols.test_deconstruction_gate_slice3 import _catalog


def _count(session, model) -> int:
    return int(
        session.execute(select(func.count()).select_from(model)).scalar_one()
    )


def _publish(
    factory,
    source_input,
    draft,
    spans,
    revision_id,
    key,
    *,
    now=NOW,
    actor="医学监查员",
    **kwargs,
):
    service = ProtocolPublicationService(factory, now=lambda: now)
    return service.publish(
        ProtocolPublicationRequest(
            idempotency_key=key,
            draft_revision_id=revision_id,
            source_input=source_input,
            source_spans=spans,
            actor=actor,
            published_at=now,
            **kwargs,
        )
    )


def _save_revision(
    factory, draft, actor="医学监查员", now=NOW, *, baseline=None
):
    with factory() as session:
        with session.begin():
            return ProtocolDraftService(session).save_initial_draft(
                draft, actor=actor, created_at=now, baseline=baseline
            )


def _edit_draft(factory, draft, expected_revision_id, edits, actor="医学监查员", now=NOW):
    edited = draft.model_copy(deep=True)
    for mutate in edits:
        mutate(edited)
    with factory() as session:
        with session.begin():
            return ProtocolDraftService(session).apply_manual_edit(
                edited,
                expected_revision_id=expected_revision_id,
                actor=actor,
                created_at=now,
            )


def test_first_publication_writes_full_formal_chain_in_one_transaction(
    slice4_env,
) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    result = _publish(factory, source_input, draft, spans, r1.revision_id, "pub-1")
    assert result.replay is False
    with factory() as session:
        assert _count(session, ProjectRecord) == 1
        assert _count(session, RuleSetRecord) == 1
        assert _count(session, ProtocolAuthorityRecordRow) == 1
        assert _count(session, ProtocolIntegrityManifestRecord) == 1
        assert _count(session, ServiceCommandEventRecord) == 1
        assert _count(session, ProtocolAuthorityConfirmationRecord) == 1
        assert _count(session, ProtocolSourceRecordRow) >= 1
        assert _count(session, WorkflowStageRecord) == 2
        assert _count(session, EvidenceRequirementRecord) == 4
        assert _count(session, EvidenceExpectationTemplateRecord) == 4
        # 流程资料要求不再伪造组件来源
        origins = session.execute(
            select(EvidenceRequirementRecord.rule_component_id,
                   EvidenceRequirementRecord.procedure_catalog_item_id)
        ).all()
        assert all(
            (left is None) != (right is None) for left, right in origins
        )
        # 审核节点带期别
        assert all(
            row.study_phase == "phase_ii"
            for row in session.execute(select(WorkflowStageRecord)).scalars()
        )
        # 草稿链头标记为已发布
        head = ProtocolDraftRevisionRepository(session).get_head(draft.draft_id)
        assert head.status.value == "published"
        # 模板投影落库
        templates = list_expectation_templates(
            session, result.rule_set_id, result.rule_set_revision
        )
        assert len(templates) == 4
        assert all(
            item.template_id.startswith("expectation-template:") for item in templates
        )


def test_source_scope_review_persists_through_real_publication_and_rule_readback(slice4_env, data_paths):
    from app.evidence.artifacts import ArtifactStore
    from app.services.protocol_scope_review_service import review_official_source_scope
    from tests.v2.protocols.test_official_scope_review import ScopeReader, scope_fixture
    factory, _ = slice4_env
    source, draft, spans = scope_fixture()
    reviewed = review_official_source_scope(source, draft, official_code="IN-01",
                                           transport=ScopeReader(), store=ArtifactStore(data_paths))
    revision = _save_revision(factory, reviewed)
    result = _publish(factory, source, reviewed, spans, revision.revision_id, "pub-source-scope")
    with factory() as session:
        formal = get_rule_set(session, result.rule_set_id, result.rule_set_revision)
        component = formal.rules[0].components[0]
        assert component.source_scope_review_ref == reviewed.proposed_rules[0].components[0].source_scope_review_ref
        assert [item.due_stage.value for item in component.evidence_requirements] == ["screening"]
        assert ProtocolDraftRevisionRepository(session).get_head(draft.draft_id).status.value == "published"


def test_client_scope_reference_without_original_reads_cannot_publish(slice4_env, data_paths):
    from app.evidence.artifacts import ArtifactStore
    from tests.v2.protocols.test_official_scope_review import scope_fixture
    factory, _ = slice4_env
    source, draft, spans = scope_fixture()
    fake = ArtifactStore(data_paths).put("evaluation_manifest", b'{"accepted":true}').storage_ref
    draft.proposed_rules[0].components[0].source_scope_review_ref = fake
    draft.component_drafts[0].proposed_component = draft.proposed_rules[0].components[0].model_copy(deep=True)
    revision = _save_revision(factory, draft)
    with pytest.raises(PublicationGateError) as error:
        _publish(factory, source, draft, spans, revision.revision_id, "pub-fake-source-scope")
    assert any(item.issue_code == "SOURCE_SCOPE_REVIEW_INVALID"
               for check in error.value.result.checks for item in check.issues)
    with factory() as session:
        assert _count(session, RuleSetRecord) == 0
        assert _count(session, ProtocolAuthorityRecordRow) == 0


def test_new_unresolved_scope_blocks_publication_instead_of_reusing_old_clearance(slice4_env, data_paths):
    from app.evidence.artifacts import ArtifactStore
    from app.services.protocol_scope_review_service import review_official_source_scope
    from tests.v2.protocols.test_official_scope_review import ScopeReader, UncertainScopeReader, scope_fixture
    factory, _ = slice4_env
    source, draft, spans = scope_fixture()
    store = ArtifactStore(data_paths)
    cleared = review_official_source_scope(source, draft, official_code="IN-01", transport=ScopeReader(), store=store)
    current = review_official_source_scope(source, cleared, official_code="IN-01", transport=UncertainScopeReader(), store=store)
    revision = _save_revision(factory, current)
    with pytest.raises(PublicationGateError) as error:
        _publish(factory, source, current, spans, revision.revision_id, "pub-new-scope-unknown")
    assert any(item.issue_code == "SOURCE_SCOPE_REVIEW_UNRESOLVED" for check in error.value.result.checks for item in check.issues)
    with factory() as session:
        assert _count(session, RuleSetRecord) == 0
        assert _count(session, ProtocolAuthorityRecordRow) == 0


def test_source_bound_unresolved_requirement_survives_formal_rule_storage(slice4_env) -> None:
    factory, _ = slice4_env
    source, draft, spans = confirmed_fixture()
    items = list(source.parent_rule_catalog.items)
    items[0] = items[0].model_copy(update={"label": "年龄≥18岁；另须完成专项评估"})
    source.parent_rule_catalog = _catalog(CatalogKind.OFFICIAL_PARENT_RULES, items)
    source.source_materials[0].text = "年龄≥18岁；另须完成专项评估"
    draft.proposed_rules[0].source_text = "年龄≥18岁；另须完成专项评估"
    draft.proposed_rules[0].restricted_components = [RestrictedRuleComponent(
        rule_component_id="component-extra", display_code="IN-01b",
        title="另项独立要求", source_span_ids=["span-in"],
        source_excerpts=["另须完成专项评估"],
        limitation_kind="interpretation_unresolved",
        unresolved_dimensions=["适用对象尚未核清"],
    )]
    revision = _save_revision(factory, draft)
    result = _publish(factory, source, draft, spans, revision.revision_id, "pub-limited-source")
    with factory() as session:
        rule_set = get_rule_set(session, result.rule_set_id, result.rule_set_revision)
        restricted = rule_set.rules[0].restricted_components
        assert len(restricted) == 1
        assert restricted[0].source_excerpts == ["另须完成专项评估"]
        pack = project_clause_pack(rule_set)
        assert pack.projection_version == "clause-pack/v4"
        assert pack.restricted_clauses[0].clause_id == restricted[0].rule_component_id
        verify_clause_pack(pack)


def test_saved_predicate_quote_cannot_publish_omitted_parent_scope(slice4_env) -> None:
    factory, _ = slice4_env
    source, draft, spans = confirmed_fixture()
    heading, child = "筛选时和基线时需满足以下标准：", "年龄≥18岁"
    source.source_materials[0].text = heading + child
    predicate = draft.proposed_rules[0].components[0].expression.predicate
    predicate.source_clause = None
    predicate.source_clauses = [heading, child]
    draft.component_drafts[0].source_excerpts = [child]
    before = draft.model_dump_json()
    revision = _save_revision(factory, draft)

    with pytest.raises(PublicationGateError) as rejected:
        _publish(factory, source, draft, spans, revision.revision_id, "pub-omitted-scope")

    assert any(
        issue.issue_code == "REVIEW_STAGE_SCOPE_UNVERIFIED"
        and "component-in" in issue.affected_refs
        for check in rejected.value.result.checks
        for issue in check.issues
    )
    assert draft.model_dump_json() == before
    with factory() as session:
        for model in (ProjectRecord, RuleSetRecord, ProtocolAuthorityRecordRow,
                      EvidenceRequirementRecord, EvidenceExpectationTemplateRecord):
            assert _count(session, model) == 0
        head = ProtocolDraftRevisionRepository(session).get_head(draft.draft_id)
        assert head.status.value != "published"


@pytest.mark.parametrize("mixed", [False, True])
def test_merged_segment_restrictions_reach_gate_storage_and_clause_consumer(slice4_env, mixed):
    from app.agents.protocol_deconstructor import _hydrate_semantic_candidate
    from app.domain.contracts.agent_io import (
        ProtocolSemanticDeconstructionCandidate, SemanticRestrictedComponent, SemanticRule,
    )
    from app.protocols.deconstruction_gate import ProtocolDeconstructionGate
    from app.protocols.parent_rule_semantic_segmentation import (
        merge_parent_rule_segments, plan_parent_rule_segments,
    )
    from tests.v2.protocols.test_parent_rule_semantic_segmentation import _thresholds
    from tests.v2.protocols.test_protocol_deconstructor_adapter_slice3 import _semantic_candidate

    factory, _ = slice4_env
    source, original, spans = confirmed_fixture()
    original_candidate = _semantic_candidate(source, original)
    texts = [
        "年龄≥18岁。" if mixed else "须完成专项评估。",
        "须完成独立资格核查。", "须取得专科意见。", "须核对适用人群。",
    ]
    span_ids = ["span-in", "span-second", "span-third", "span-fourth"]
    template = source.source_materials[0]
    source.source_materials = [
        x for x in source.source_materials if x.source_span_id != "span-in"
    ] + [template.model_copy(update={
        "source_span_id": span_id, "text": text,
        "block_order": 10 + index, "source_ref": f"body.p{10 + index}",
    }) for index, (span_id, text) in enumerate(zip(span_ids, texts, strict=True))]
    for index, span_id in enumerate(span_ids):
        spans[span_id] = spans["span-in"].model_copy(update={
            "source_span_id": span_id, "source_ref": f"body.p{10 + index}",
            "block_order": 10 + index, "render_page": 10 + index,
            "text_start": 0, "text_end": len(texts[index]), "excerpt": texts[index],
        })
    source.allowed_source_span_ids = list(spans)
    items = list(source.parent_rule_catalog.items)
    parent = items[0].model_copy(update={
        "label": "\n".join(texts), "source_span_ids": tuple(span_ids),
        "source_excerpts": tuple(texts),
    })
    items[0] = parent
    source.parent_rule_catalog = _catalog(CatalogKind.OFFICIAL_PARENT_RULES, items)
    plan = plan_parent_rule_segments(
        parent, source_materials=source.source_materials,
        token_estimate=100, thresholds=_thresholds(),
    )
    assert plan is not None and len(plan.segments) == 4
    candidates = []
    for index, (span_id, text) in enumerate(zip(span_ids, texts, strict=True)):
        executable = mixed and index == 0
        component = original_candidate.proposed_rules[0].components[0].model_copy(deep=True)
        component.source_excerpts = [text]
        rule = SemanticRule(
            official_code="IN-01", components=[component] if executable else [],
            restricted_components=[] if executable else [SemanticRestrictedComponent(
                title=f"独立要求{index}", source_span_ids=[span_id], source_excerpts=[text],
                limitation_kind="interpretation_unresolved",
                unresolved_dimensions=["具体执行条件尚待核清"],
            )],
        )
        candidates.append(ProtocolSemanticDeconstructionCandidate(
            candidate_id=f"segment-{index}", proposed_rules=[rule],
            created_by_agent_call_id=f"segment-call-{index}",
        ))
    merged = merge_parent_rule_segments(
        candidates, plan=plan, candidate_id="merged-parent", agent_call_id="merged-call",
    )
    complete = merged.model_copy(update={
        "proposed_rules": [merged.proposed_rules[0], original_candidate.proposed_rules[1]],
    })
    draft = _hydrate_semantic_candidate(source, complete)
    report = ProtocolDeconstructionGate().evaluate(source, draft, source_spans=spans)
    assert report.publishable, "\n".join(
        f"{check.check_name}: {issue.issue_code}: {issue.affected_refs}"
        for check in report.checks for issue in check.issues
    )
    invalid = draft.model_copy(deep=True)
    invalid.proposed_rules[0].restricted_components[-1].source_span_ids = ["span-ex"]
    rejected = ProtocolDeconstructionGate().evaluate(source, invalid, source_spans=spans)
    assert not rejected.publishable
    assert any(
        issue.issue_code == "RESTRICTED_COMPONENT_SOURCE_INVALID"
        for check in rejected.checks for issue in check.issues
    )
    revision = _save_revision(factory, draft)
    result = _publish(
        factory, source, draft, spans, revision.revision_id, f"merged-restriction-{mixed}",
    )
    with factory() as session:
        rule_set = get_rule_set(session, result.rule_set_id, result.rule_set_revision)
        pack = project_clause_pack(rule_set)
        verify_clause_pack(pack)
        assert len(pack.restricted_clauses) == (3 if mixed else 4)
        assert [x.source_excerpts for x in rule_set.rules[0].restricted_components] == [
            [text] for text in texts[(1 if mixed else 0):]
        ]
        assert len(rule_set.rules[0].components) == int(mixed)


def test_population_gap_survives_publication_pack_and_actual_component_consumer(slice4_env):
    from app.domain.contracts.enums import ComponentDecision, GapType, ReviewStage, TruthValue
    from app.services.component_review import calculate_component_review
    from app.services.eligibility_review_projection import _reason
    from app.domain.policies import ACTION_CONTENT
    from tests.v2.test_contract_logic import evaluation_context

    factory, _ = slice4_env
    source, draft, spans = confirmed_fixture()
    text = "年龄≥18岁（仅女性受试者）"
    items = list(source.parent_rule_catalog.items)
    items[0] = items[0].model_copy(update={"label": text})
    source.parent_rule_catalog = _catalog(CatalogKind.OFFICIAL_PARENT_RULES, items)
    source.source_materials[0].text = text
    draft.proposed_rules[0].source_text = text
    predicate = draft.proposed_rules[0].components[0].expression.predicate
    predicate.source_clause = None
    predicate.source_clauses = ["年龄≥18岁", "（仅女性受试者）"]
    draft.component_drafts[0].source_excerpts = [text]
    predicate.applicable_population = "仅女性受试者"
    revision = _save_revision(factory, draft)
    result = _publish(factory, source, draft, spans, revision.revision_id, "pub-population-gap")
    with factory() as session:
        rule_set = get_rule_set(session, result.rule_set_id, result.rule_set_revision)
        pack = project_clause_pack(rule_set)
        verify_clause_pack(pack)
        rule = next(item for item in rule_set.rules if item.official_code == "IN-01")
        component = rule.components[0]
        assert component.expression.predicate.applicable_population == "仅女性受试者"
        clause = next(item for item in pack.clauses if item.official_code == "IN-01")
        assert clause.expression == component.expression
        review = calculate_component_review(
            component=component, rule_kind=rule.kind, context=evaluation_context(),
            episode_stage=ReviewStage.SCREENING, expectations=[], conflicts=[],
            predicate_fact_ids={predicate.predicate_id: []},
        )
        assert review.evaluation.trigger.truth == TruthValue.UNKNOWN
        assert review.decision == ComponentDecision.INDETERMINATE
        assert GapType.APPLICABLE_POPULATION_UNVERIFIED in review.gaps
        reason = _reason(clause, decision=review.decision,
                        gap=GapType.APPLICABLE_POPULATION_UNVERIFIED, summaries={})
        assert "适用人群" in reason and "无法取得" not in reason
        assert ACTION_CONTENT[GapType.APPLICABLE_POPULATION_UNVERIFIED][0].value == "sponsor_medical_or_project"


def test_verified_member_frequency_gap_keeps_sibling_executable_on_publication(slice4_env) -> None:
    factory, _ = slice4_env
    source, draft, spans = confirmed_fixture()
    nested = "有严重感染既往史（包括反复细菌感染（2年内发生2次或以上））"
    text = f"ALT或AST≥1.5×ULN；{nested}"
    items = list(source.parent_rule_catalog.items)
    items[1] = items[1].model_copy(update={"label": text})
    source.parent_rule_catalog = _catalog(CatalogKind.OFFICIAL_PARENT_RULES, items)
    next(item for item in source.source_materials if item.source_span_id == "span-ex").text = text
    rule = draft.proposed_rules[1]
    rule.source_text = text
    rule.restricted_components = [RestrictedRuleComponent(
        rule_component_id="component-ex-limited", display_code="EX-01b",
        title="严重感染史", source_span_ids=["span-ex"],
        source_excerpts=[nested], limitation_kind="consumer_unavailable",
        unresolved_dimensions=["开放列举中的复发项有专属频次定义，当前表达结构无法同时保留上位范围"],
    )]

    revision = _save_revision(factory, draft)
    published = _publish(factory, source, draft, spans, revision.revision_id, "pub-frequency-gap")
    with factory() as session:
        rule_set = get_rule_set(session, published.rule_set_id, published.rule_set_revision)
        pack = project_clause_pack(rule_set)
        verify_clause_pack(pack)
        assert len(pack.clauses) == 2
        assert len(pack.restricted_clauses) == 1
        assert pack.restricted_clauses[0].limitation_kind == "consumer_unavailable"
        projection = _restricted_clause_projection(pack.restricted_clauses[0])
        assert "当前审核方式尚不能可靠判定" in projection.reason
        assert not projection.fact_refs


def test_authority_record_closure_hashes_are_self_consistent(slice4_env) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    result = _publish(factory, source_input, draft, spans, r1.revision_id, "pub-hash")
    with factory() as session:
        authority = AppendRepository(session, AUTHORITY_RECORD_CONFIG).get(
            result.authority_record_id
        )
        # 合同自校验哈希：含流程资料要求与来源定位
        assert authority.authority_record_sha256 == canonical_hash(
            authority.model_dump(mode="json", exclude={"authority_record_sha256"})
        )
        assert len(authority.procedure_evidence_requirements) == 2
        assert set(authority.procedure_requirement_source_anchor_refs) == {
            item.requirement_id
            for item in authority.procedure_evidence_requirements
        }
        # 每条官方规则与流程要求都有绑定当前版本的前缀来源定位
        prefix = f"{result.protocol_version_id}:"
        for refs in authority.rule_source_anchor_refs.values():
            assert all(ref.startswith(prefix) for ref in refs)
        for refs in authority.procedure_requirement_source_anchor_refs.values():
            assert all(ref.startswith(prefix) for ref in refs)
        # 每条资料要求必须且仅到期一次（合同校验已保证，此处再断言闭包）
        due_ids = [
            requirement_id
            for stage in authority.official_workflow_stages
            for requirement_id in stage.due_requirement_ids
        ]
        assert len(due_ids) == len(set(due_ids))
        # 发布结果与存储的清单/权威记录一致
        assert result.manifest_id is not None
        assert result.authority_record_id == authority.authority_record_id


def test_authority_allows_distinct_visit_instances_in_same_review_stage(
    slice4_env,
) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    result = _publish(factory, source_input, draft, spans, r1.revision_id, "pub-visits")

    with factory() as session:
        authority = AppendRepository(session, AUTHORITY_RECORD_CONFIG).get(
            result.authority_record_id
        )
    first_stage = authority.official_workflow_stages[0]
    moved_requirement = first_stage.due_requirement_ids[0]
    stages = [
        first_stage.model_copy(
            update={
                "due_requirement_ids": first_stage.due_requirement_ids[1:]
            }
        ),
        first_stage.model_copy(
            update={
                "workflow_stage_id": first_stage.workflow_stage_id + ":visit-2",
                "display_name": first_stage.display_name + "第二次访视",
                "visit_instance": (
                    first_stage.visit_instance or "筛选期 D1"
                ) + " 第二次",
                "due_requirement_ids": [moved_requirement],
            }
        ),
        *authority.official_workflow_stages[1:],
    ]
    payload = authority.model_dump(
        mode="json", exclude={"authority_record_sha256"}
    )
    payload["official_workflow_stages"] = [
        stage.model_dump(mode="json") for stage in stages
    ]

    rebuilt = authority.__class__(
        **payload,
        authority_record_sha256=canonical_hash(payload),
    )
    assert [stage.stage for stage in rebuilt.official_workflow_stages[:2]] == [
        first_stage.stage,
        first_stage.stage,
    ]
    assert rebuilt.official_workflow_stages[0].workflow_stage_id != (
        rebuilt.official_workflow_stages[1].workflow_stage_id
    )


def test_same_key_same_request_returns_original_publication(slice4_env) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    first = _publish(factory, source_input, draft, spans, r1.revision_id, "pub-idem")
    second = _publish(factory, source_input, draft, spans, r1.revision_id, "pub-idem")
    assert second.replay is True
    assert second == first.__class__(
        **{**first.__dict__, "replay": False}
    ) or second.authority_record_id == first.authority_record_id
    with factory() as session:
        # 重放不产生第二套正式行
        assert _count(session, ProjectRecord) == 1
        assert _count(session, ProtocolAuthorityRecordRow) == 1


def test_same_key_different_request_conflicts(slice4_env) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    _publish(factory, source_input, draft, spans, r1.revision_id, "pub-conflict")
    with pytest.raises(IdempotencyConflict):
        _publish(
            factory,
            source_input,
            draft,
            spans,
            r1.revision_id,
            "pub-conflict",
            actor="另一个操作者",
        )


def test_same_key_with_changed_source_document_conflicts(slice4_env) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    _publish(factory, source_input, draft, spans, r1.revision_id, "pub-source-conflict")

    changed_source = source_input.model_copy(
        update={"protocol_file_sha256": "f" * 64}
    )
    with pytest.raises(IdempotencyConflict):
        _publish(
            factory,
            changed_source,
            draft,
            spans,
            r1.revision_id,
            "pub-source-conflict",
        )


def test_failed_gate_rolls_back_all_formal_rows(slice4_env) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    # 篡改身份日期 -> 门禁 identity 拒绝（编辑边界允许，门禁阻止发布）
    broken = _edit_draft(
        factory,
        draft,
        r1.revision_id,
        [
            lambda d: d.protocol_metadata.__setattr__(
                "date_candidate", "2020-01-01"
            )
        ],
    )
    with pytest.raises(PublicationGateError):
        _publish(factory, source_input, draft, spans, broken.revision_id, "pub-fail")
    with factory() as session:
        assert _count(session, ProjectRecord) == 0
        assert _count(session, RuleSetRecord) == 0
        assert _count(session, ProtocolAuthorityRecordRow) == 0
        assert _count(session, ProtocolIntegrityManifestRecord) == 0
        assert _count(session, WorkflowStageRecord) == 0
        assert _count(session, EvidenceExpectationTemplateRecord) == 0
        # 草稿链头仍是可编辑的已保存状态
        head = ProtocolDraftRevisionRepository(session).get_head(draft.draft_id)
        assert head.status.value == "saved"


def test_failure_after_formal_writes_rolls_back_entire_publication(
    slice4_env, monkeypatch
) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    service = ProtocolPublicationService(factory, now=lambda: now)

    def fail_template_projection(*args, **kwargs):
        raise RuntimeError("模拟正式记录写入后的模板投影失败")

    monkeypatch.setattr(service, "_templates", fail_template_projection)
    with pytest.raises(RuntimeError, match="模板投影失败"):
        service.publish(
            ProtocolPublicationRequest(
                idempotency_key="pub-write-fail",
                draft_revision_id=r1.revision_id,
                source_input=source_input,
                source_spans=spans,
                actor="医学监查员",
                published_at=now,
            )
        )

    with factory() as session:
        for model in (
            ProjectRecord,
            RuleSetRecord,
            ProtocolAuthorityRecordRow,
            ProtocolIntegrityManifestRecord,
            WorkflowStageRecord,
            EvidenceExpectationTemplateRecord,
            IdempotencyRecordRow,
        ):
            assert _count(session, model) == 0
        head = ProtocolDraftRevisionRepository(session).get_head(draft.draft_id)
        assert head.status.value == "saved"


def test_stale_revision_publication_rolls_back_and_keeps_previous_published(
    slice4_env,
) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    # 另一标签页在 r1 仍为已保存时追加 r2；随后用过期 r1 发布 -> 过期。
    # （已发布的 revision 不能再编辑/覆盖，因此过期场景必须在发布前构造。）
    r2 = _edit_draft(
        factory,
        draft,
        r1.revision_id,
        [
            lambda d: d.proposed_workflow_stages[0].__setattr__(
                "display_name", "另一标签页的修改"
            )
        ],
    )
    assert r2.revision_number == 2
    with pytest.raises(StaleRevisionError) as exc_info:
        _publish(factory, source_input, draft, spans, r1.revision_id, "pub-stale-2")
    error = exc_info.value
    # 过期错误必须报告提交方真实 expected revision、当前 revision 与结构化差异，
    # 不能写成 expected == current == 当前值且差异为空。
    assert error.entity_type == "ProtocolDraftRevision"
    assert error.expected_revision == 1
    assert error.current_revision == 2
    assert error.field_diff, "过期发布必须携带结构化差异信封"
    stage_change = error.field_diff["workflow_stage:stage-screening"]
    assert stage_change.submitted["display_name"] == "筛选期审核"
    assert stage_change.current["display_name"] == "另一标签页的修改"
    with factory() as session:
        # 过期发布不产生任何正式行
        assert _count(session, ProjectRecord) == 0
        assert _count(session, RuleSetRecord) == 0
        assert _count(session, ProtocolAuthorityRecordRow) == 0
        repo = ProtocolDraftRevisionRepository(session)
        # r1 从未被标记为已发布；r2 仍是链头且保持已保存
        assert repo.get(r1.revision_id).status.value == "saved"
        assert repo.get(r2.revision_id).status.value == "saved"
        assert repo.get_head(draft.draft_id).revision_id == r2.revision_id


def test_duplicate_first_project_is_prevented(slice4_env) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    _publish(factory, source_input, draft, spans, r1.revision_id, "pub-first")
    # 同一方案编号 + 同期别的第二个草稿：首次发布必须拒绝
    second_draft = draft.model_copy(deep=True)
    second_draft.draft_id = "draft-2"
    r2 = _save_revision(factory, second_draft)
    with pytest.raises(DuplicateFirstProjectError):
        _publish(factory, source_input, second_draft, spans, r2.revision_id, "pub-dup")


def test_republish_same_protocol_lineage_appends_rule_set_revision(slice4_env) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    first = _publish(factory, source_input, draft, spans, r1.revision_id, "pub-r1")

    # 新修订案：同方案编号，新版本/日期/内部版本 id
    new_version_id = "protocol-version-2"
    revised = draft.model_copy(deep=True)
    revised.draft_id = "draft-v2"
    revised.protocol_version_id = new_version_id
    revised.protocol_metadata = revised.protocol_metadata.model_copy(
        update={"version_candidate": "V2.0", "date_candidate": "2026-09-01"}
    )
    revised_input = source_input.model_copy(deep=True)
    revised_input.protocol_version_id = new_version_id
    revised_input.identity_decision = source_input.identity_decision.model_copy(
        update={
            "official_version": "V2.0",
            "official_date": DateValue(
                value=date(2026, 9, 1), precision=DatePrecision.DAY
            ),
        }
    )
    rv2 = _save_revision(factory, revised, baseline=draft)
    result2 = _publish(
        factory,
        revised_input,
        revised,
        spans,
        rv2.revision_id,
        "pub-r2",
        project_id="project-1",
        protocol_version_id=new_version_id,
    )
    assert result2.project_id == "project-1"
    assert result2.rule_set_id == first.rule_set_id
    assert result2.rule_set_revision == first.rule_set_revision + 1
    assert result2.project_revision == first.project_revision + 1
    assert result2.protocol_version_id == new_version_id
    with factory() as session:
        project = session.get(ProjectRecord, "project-1")
        assert project.rule_set_revision == result2.rule_set_revision
        # 旧 revision 的正式行全部保留
        old = get_rule_set(session, first.rule_set_id, first.rule_set_revision)
        assert len(old.rules) == 2
        # 旧权威记录仍可读
        AppendRepository(session, AUTHORITY_RECORD_CONFIG).get(
            first.authority_record_id
        )
        # 新版本行带真实清单/权威引用
        from app.storage.repositories import PROTOCOL_DOC_CONFIG

        version = AppendRepository(session, PROTOCOL_DOC_CONFIG).get(new_version_id)
        assert version.integrity_manifest_sha256 != "0" * 64
        assert version.authority_record_sha256 != "0" * 64


def test_republish_cross_protocol_or_cross_phase_is_rejected(slice4_env) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    _publish(factory, source_input, draft, spans, r1.revision_id, "pub-x-1")

    # 另一方案
    other_input = source_input.model_copy(deep=True)
    other_input.identity_decision = source_input.identity_decision.model_copy(
        update={"protocol_code": "OTHER-001"}
    )
    other_input.protocol_version_id = "protocol-other-v1"
    other_draft = draft.model_copy(deep=True)
    other_draft.draft_id = "draft-other"
    other_draft.protocol_version_id = "protocol-other-v1"
    other_draft.protocol_metadata = other_draft.protocol_metadata.model_copy(
        update={"protocol_code_candidate": "OTHER-001"}
    )
    ro = _save_revision(factory, other_draft)
    with pytest.raises(PublicationLineageError) as exc_info:
        _publish(
            factory,
            other_input,
            other_draft,
            spans,
            ro.revision_id,
            "pub-x-other",
            project_id="project-1",
        )
    assert exc_info.value.code == "cross_protocol"

    # 另一期别（III 期）：用恒可通过的门禁隔离谱系检查本身
    from app.domain.contracts.enums import StudyPhase
    from app.protocols.deconstruction_gate import (
        CHECK_NAMES,
        ProtocolDeconstructionGateResult,
        ProtocolGateCheckResult,
    )

    class AlwaysPublishableGate:
        def evaluate(self, *args, **kwargs):
            return ProtocolDeconstructionGateResult(
                publishable=True,
                checks=[
                    ProtocolGateCheckResult(check_name=name, passed=True)
                    for name in CHECK_NAMES
                ],
            )

    phase_input = source_input.model_copy(deep=True)
    phase_input.protocol_version_id = "protocol-phase3-v1"
    phase_draft = draft.model_copy(deep=True)
    phase_draft.draft_id = "draft-phase3"
    phase_draft.selected_phase = StudyPhase.PHASE_III
    phase_draft.protocol_version_id = "protocol-phase3-v1"
    phase_draft.proposed_rules = [
        rule.model_copy(update={"study_phase": StudyPhase.PHASE_III})
        for rule in phase_draft.proposed_rules
    ]
    rp = _save_revision(factory, phase_draft)
    service = ProtocolPublicationService(
        factory, gate=AlwaysPublishableGate(), now=lambda: now
    )
    with pytest.raises(PublicationLineageError) as exc_info:
        service.publish(
            ProtocolPublicationRequest(
                idempotency_key="pub-x-phase",
                draft_revision_id=rp.revision_id,
                source_input=phase_input,
                source_spans=spans,
                actor="医学监查员",
                published_at=now,
                project_id="project-1",
                protocol_version_id="protocol-phase3-v1",
            )
        )
    assert exc_info.value.code == "cross_phase"


def test_published_revision_cannot_be_published_again(slice4_env) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    _publish(factory, source_input, draft, spans, r1.revision_id, "pub-twice-1")
    from app.services.protocol_publication_service import ProtocolPublicationError

    with pytest.raises(ProtocolPublicationError) as exc_info:
        _publish(factory, source_input, draft, spans, r1.revision_id, "pub-twice-2")
    assert exc_info.value.code == "revision_not_editable"


def test_same_protocol_version_id_cannot_host_two_authority_chains(slice4_env) -> None:
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    _publish(factory, source_input, draft, spans, r1.revision_id, "pub-v1")
    # 第二个草稿尝试以重新解构方式复用同一内部版本 id -> 拒绝
    second = draft.model_copy(deep=True)
    second.draft_id = "draft-v1b"
    r2 = _save_revision(factory, second)
    with pytest.raises(PublicationLineageError) as exc_info:
        _publish(
            factory,
            source_input,
            second,
            spans,
            r2.revision_id,
            "pub-v1b",
            project_id="project-1",
            protocol_version_id="protocol-version-1",
        )
    assert exc_info.value.code == "protocol_version_already_published"


def test_first_publish_cannot_override_protocol_version_id(slice4_env) -> None:
    """首次发布不接受重新解构专用的外部版本 id 覆盖。"""
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    with pytest.raises(PublicationLineageError) as exc_info:
        _publish(
            factory,
            source_input,
            draft,
            spans,
            r1.revision_id,
            "pub-first-override",
            protocol_version_id="protocol-version-external",
        )
    assert exc_info.value.code == "first_publish_cannot_override_version"


def test_republish_version_id_must_match_draft_and_input(slice4_env) -> None:
    """重新发布的内部版本 id 必须与新草稿/输入一致，不能脱离。"""
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    _publish(factory, source_input, draft, spans, r1.revision_id, "pub-mismatch-1")

    revised = draft.model_copy(deep=True)
    revised.draft_id = "draft-v2-mismatch"
    revised.protocol_version_id = "protocol-version-2"
    revised_input = source_input.model_copy(deep=True)
    revised_input.protocol_version_id = "protocol-version-2"
    rv2 = _save_revision(factory, revised)
    # 请求携带与草稿不一致的版本 id -> 拒绝
    with pytest.raises(PublicationLineageError) as exc_info:
        _publish(
            factory,
            revised_input,
            revised,
            spans,
            rv2.revision_id,
            "pub-mismatch-2",
            project_id="project-1",
            protocol_version_id="protocol-version-3",
        )
    assert exc_info.value.code == "republish_version_mismatch"
    # 草稿与输入版本不一致 -> 拒绝（输入被替换成另一版本）
    with pytest.raises(PublicationLineageError) as exc_info:
        _publish(
            factory,
            source_input,
            revised,
            spans,
            rv2.revision_id,
            "pub-mismatch-3",
            project_id="project-1",
            protocol_version_id="protocol-version-2",
        )
    assert exc_info.value.code == "draft_input_version_mismatch"


def test_authority_record_keeps_per_requirement_source_anchors(slice4_env) -> None:
    """权威记录必须逐条保存所有规则 EvidenceRequirement 的来源锚点，
    不能只覆盖父规则与流程要求。"""
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    result = _publish(factory, source_input, draft, spans, r1.revision_id, "pub-req-anchors")
    with factory() as session:
        authority = AppendRepository(session, AUTHORITY_RECORD_CONFIG).get(
            result.authority_record_id
        )
    all_requirement_ids = {
        requirement.requirement_id
        for rule in authority.official_rules
        for component in rule.components
        for requirement in component.evidence_requirements
    } | {
        requirement.requirement_id
        for requirement in authority.procedure_evidence_requirements
    }
    # 闭包：每条资料要求都有非空、绑定当前版本前缀的来源锚点
    assert set(authority.requirement_source_anchor_refs) == all_requirement_ids
    assert len(authority.requirement_source_anchor_refs) == 4
    prefix = f"{result.protocol_version_id}:"
    for refs in authority.requirement_source_anchor_refs.values():
        assert refs and all(ref.startswith(prefix) for ref in refs)


def test_publication_rejects_requirement_source_outside_component(slice4_env) -> None:
    """即使畸形首稿绕过编辑边界，发布门禁仍拒绝越界来源并回滚。"""
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    malformed = draft.model_copy(deep=True)
    malformed.evidence_requirement_drafts[0] = (
        malformed.evidence_requirement_drafts[0].model_copy(
            update={"source_refs": ["span-ex"]}
        )
    )
    r1 = _save_revision(factory, malformed)
    with pytest.raises(PublicationGateError) as exc_info:
        _publish(factory, source_input, malformed, spans, r1.revision_id, "pub-req-outside")
    assert any(
        issue.issue_code == "REQUIREMENT_SOURCE_OUTSIDE_COMPONENT"
        for check in exc_info.value.result.checks
        if check.check_name == "source_coverage"
        for issue in check.issues
    )
    with factory() as session:
        assert _count(session, ProjectRecord) == 0
        assert _count(session, RuleSetRecord) == 0


def test_successor_publication_reruns_diff_integrity_with_previous(slice4_env) -> None:
    """发布后继 revision 时必须携带前序草稿与声明差异复跑 diff_integrity；
    声明差异与实际结构差异不一致 -> 拒绝发布。"""
    factory, now = slice4_env
    source_input, draft, spans = confirmed_fixture()
    r1 = _save_revision(factory, draft)
    r2 = _edit_draft(
        factory,
        draft,
        r1.revision_id,
        [
            lambda d: d.proposed_rules[0].components[0].__setattr__(
                "title", "年龄要求（修改）"
            )
        ],
    )
    assert r2.revision_number == 2
    assert r2.content.draft_revision == 2
    assert r2.content.previous_draft_id == draft.draft_id

    from app.storage.repositories import ProtocolDraftRevisionRepository

    # 篡改声明差异（改动 revision.diff）-> diff_integrity 拒绝
    with factory() as session:
        repo = ProtocolDraftRevisionRepository(session)
        record = repo.get(r2.revision_id)
        tampered = record.model_copy(deep=True)
        tampered.diff = tampered.diff.model_copy(
            update={"modified_rule_codes": ["EX-01"]}
        )
        repo.replace(tampered)
        session.commit()
    with pytest.raises(PublicationGateError) as exc_info:
        _publish(
            factory,
            source_input,
            draft,
            spans,
            r2.revision_id,
            "pub-successor-tampered",
        )
    assert any(
        issue.issue_code == "DECLARED_DIFF_NOT_REPRODUCIBLE"
        for check in exc_info.value.result.checks
        if check.check_name == "diff_integrity"
        for issue in check.issues
    )
    with factory() as session:
        assert _count(session, ProjectRecord) == 0

    # 恢复正确差异后，后继草稿携带正确 previous_draft + declared_diff -> 通过
    with factory() as session:
        repo = ProtocolDraftRevisionRepository(session)
        record = repo.get(r2.revision_id)
        correct = record.model_copy(deep=True)
        correct.diff = correct.diff.model_copy(
            update={"modified_rule_codes": ["IN-01"]}
        )
        repo.replace(correct)
        session.commit()
    result = _publish(
        factory,
        source_input,
        draft,
        spans,
        r2.revision_id,
        "pub-successor",
    )
    assert result.rule_set_revision == 1
    with factory() as session:
        head = ProtocolDraftRevisionRepository(session).get_head(draft.draft_id)
        assert head.status.value == "published"
