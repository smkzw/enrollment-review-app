"""Focused checks for a non-publishing, source-bound semantic reading."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.agents.protocol_control_agent_transport import OpenAICompatibleProtocolControlAgentTransport
from app.agents.protocol_control_semantic_point import (
    SEMANTIC_BINDER_VERSION,
    SEMANTIC_POINT_VERSION,
    SourceSemanticPacket,
    bind_semantic_packet,
    bind_semantic_packet_partially,
    build_semantic_point_prompt,
)
from app.agents.protocol_control_semantic_repair import (
    apply_semantic_point_replacement, build_semantic_point_repair_prompt,
    semantic_point_precondition,
)
from app.agents.protocol_control_semantic_inquiry import (
    INQUIRY_PLAN_VERSION, INQUIRY_RESULT_VERSION,
    SourceInquiryPlan, SourceInquiryResult, build_inquiry_plan_prompt,
    materialize_inquiry_sources, verify_inquiry_result,
)
from app.agents.protocol_control_source_interpretation import (
    SOURCE_INTERPRETATION_VERSION,
    SOURCE_TARGET_REVIEW_VERSION,
    SourceInterpretation,
    SourceStatement,
    SourceStatementCoverage,
)
from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.protocol_controls import (
    KnownOfficialRuleTarget,
    ProtocolControlDispositionBatch, ProtocolControlDiscoveryDecision,
    ProtocolControlDiscoveryDisposition, ProtocolControlDiscoveryToDeepPlan,
    ProtocolStructureUnit, StructureUnitKind,
    TableCellContext,
    stable_protocol_control_manifest_structure_unit_ids_sha256,
)
from app.services.protocol_control_catalog_publication import (
    _require_frozen_draft_revision, _require_source_calculations_consumable, source_calculation_gaps,
)
from app.services.protocol_control_execution import STEP_CLOSURE
from app.storage.repositories import ScopeViolationError
from scripts.run_frozen_semantic_points import (
    parse_reused_packet, reuse_raw_response, select_repair_issue,
)
from scripts.run_frozen_semantic_inquiry import _result_status


def _source():
    excerpts = [
        "选择最近三次记录，取其均值作为本次审核值。",
        "缺失记录不填补，只按已有记录计算。",
        "本节介绍记录表的填写背景。",
    ]
    units = [
        ProtocolStructureUnit(
            structure_unit_id=f"u{i}", source_ref=f"body.p{i}",
            member_source_refs=[f"body.p{i}"], source_span_ids=[f"span-{i}"],
            unit_kind=StructureUnitKind.PARAGRAPH, heading_path=["核对方法"],
            source_order=i, study_phase=StudyPhase.PHASE_II,
            phase_scopes=[PhaseScope.SHARED], excerpt=excerpt,
        ) for i, excerpt in enumerate(excerpts)
    ]
    batch = ProtocolControlDispositionBatch(
        batch_id="batch-generic", coverage_manifest_id="manifest-generic",
        protocol_version_id="protocol-generic", study_phase=StudyPhase.PHASE_II,
        batch_number=1, batch_total=1, owned_units=units,
        owned_structure_unit_ids=[unit.structure_unit_id for unit in units],
        owned_source_span_ids=[f"span-{i}" for i in range(len(units))],
    )
    interpretation = SourceInterpretation(
        version=SOURCE_INTERPRETATION_VERSION,
        statements=[
            SourceStatement(
                structure_unit_id=unit.structure_unit_id, quoted_text=unit.excerpt,
                force="descriptive", decision_functions=functions, time_words=[],
            ) for unit, functions in zip(
                units, [["definition", "calculation_input"], ["calculation_input"], ["background"]]
            )
        ],
        units_without_statement=[],
    )
    return batch, interpretation


def _packet():
    return SourceSemanticPacket.model_validate({
        "version": SEMANTIC_POINT_VERSION,
        "items": [
            {
                "statement_index": 0, "proposition": "最近三次记录的算术均值是本次审核值",
                "role": "definition", "review_scope": "supporting_definition",
                "dependencies": [{"statement_index": 1, "point_key": "main"}],
                "computation": {
                    "operator": "mean", "operator_ref": {"statement_index": 0, "quote": "取其均值"},
                    "input_refs": [{"statement_index": 0, "quote": "最近三次记录"}],
                    "missing_policy": "exclude",
                    "missing_ref": {"statement_index": 1, "quote": "缺失记录不填补"},
                },
            },
            {"statement_index": 1, "proposition": "缺失值不填补", "role": "constraint",
             "review_scope": "supporting_definition"},
            {"statement_index": 2, "proposition": "仅说明表格背景", "role": "context",
             "review_scope": "study_level_background"},
        ],
    })


def _publication_source_store(batch, interpretation):
    unit_ids = batch.owned_structure_unit_ids
    plan = ProtocolControlDiscoveryToDeepPlan(
        plan_id="plan-generic", discovery_plan_id="discovery-generic",
        coverage_manifest_id=batch.coverage_manifest_id,
        protocol_version_id=batch.protocol_version_id,
        protocol_document_sha256="a" * 64, snapshot_id="snapshot-generic",
        study_phase=batch.study_phase, manifest_structure_unit_count=len(unit_ids),
        manifest_structure_unit_ids_sha256=stable_protocol_control_manifest_structure_unit_ids_sha256(unit_ids),
        expected_structure_unit_ids=unit_ids,
        discovery_decisions=[ProtocolControlDiscoveryDecision(
            structure_unit_id=unit_id,
            disposition=ProtocolControlDiscoveryDisposition.CANDIDATE,
            rationale="来源需核对",
        ) for unit_id in unit_ids],
        max_owned_units_per_batch=len(unit_ids), batches=[batch],
    )
    checkpoints = {
        STEP_CLOSURE: {"deep_plan": plan.model_dump(mode="json"),
                       "deep_step_ids": [{"batch_id": batch.batch_id, "step_id": "deep-1"}]},
        "deep-1": {"run_result": {
            "status": "已解析", "batch_id": batch.batch_id,
            "session_id": "session-generic", "attempts": [{
                "attempt": 1, "session_id": "session-generic",
                "raw_output_sha256": "b" * 64, "outcome": "parsed",
            }],
            "source_interpretation": interpretation.model_dump(mode="json"),
        }},
    }
    return SimpleNamespace(get_last_checkpoint=lambda _job, step: (step, checkpoints[step]))


def test_publication_requires_exact_frozen_draft_revision(monkeypatch) -> None:
    from app.services import protocol_control_catalog_publication as publication
    draft = SimpleNamespace(draft_id="draft-a", draft_revision=2)
    revision = SimpleNamespace(content=draft, content_sha256="a" * 64)
    monkeypatch.setattr(publication.ProtocolDraftRevisionRepository, "get",
                        lambda self, revision_id: revision)
    frozen = {"draft_revision_id": "revision-a", "draft_content_sha256": "a" * 64}
    _require_frozen_draft_revision(None, frozen, draft)
    with pytest.raises(ScopeViolationError, match="尚未绑定"):
        _require_frozen_draft_revision(None, {}, draft)
    with pytest.raises(ScopeViolationError, match="旧版"):
        _require_frozen_draft_revision(None, {**frozen, "draft_content_sha256": "b" * 64}, draft)
    with pytest.raises(ScopeViolationError, match="旧版"):
        _require_frozen_draft_revision(None, frozen, SimpleNamespace(draft_id="draft-a", draft_revision=3))


def test_publication_refuses_textual_coverage_without_calculation_consumer() -> None:
    batch, interpretation = _source()
    store = _publication_source_store(batch, interpretation)
    with pytest.raises(ScopeViolationError, match="计算定义尚无可核验的正式求值方式"):
        _require_source_calculations_consumable(store, "job-generic")
    gaps = source_calculation_gaps(store, "job-generic")
    assert [(item.batch_number, item.statement_index, item.source_span_ids, item.source_quote)
            for item in gaps] == [
        (1, 0, ("span-0",), batch.owned_units[0].excerpt),
        (1, 1, ("span-1",), batch.owned_units[1].excerpt),
    ]
    assert all(item.linked_official_code is None for item in gaps)
    assert all(item.review_decision is None and not item.unresolved_aspects for item in gaps)


def test_calculation_preview_only_links_a_frozen_official_target() -> None:
    batch, interpretation = _source()
    batch.known_official_targets = [KnownOfficialRuleTarget(
        catalog_item_id="target-1", official_code="IN-01", label="有源要求",
        position=0, source_span_ids=["span-0"],
        source_excerpts=[batch.owned_units[0].excerpt],
    )]
    store = _publication_source_store(batch, interpretation)
    checkpoint = store.get_last_checkpoint("job-generic", "deep-1")[1]
    checkpoint["run_result"]["source_target_review"] = {
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{
            "statement_index": 0, "decision": "covered_by_official",
            "target_id": "IN-01", "source_action_excerpt": batch.owned_units[0].excerpt,
            "target_action_excerpt": "取其均值",
        }],
    }
    gaps = source_calculation_gaps(store, "job-generic")
    assert gaps[0].linked_official_code == "IN-01"
    assert gaps[0].review_decision == "covered_by_official"
    assert gaps[0].unresolved_aspects == ()
    assert gaps[1].linked_official_code is None
    assert gaps[1].review_decision is None
    interpretation.statements[1].unresolved = ["输入次数的适用范围"]
    checkpoint["run_result"]["source_interpretation"] = interpretation.model_dump(mode="json")
    assert source_calculation_gaps(store, "job-generic")[1].unresolved_aspects == ("输入次数的适用范围",)
    interpretation.statements[1].unresolved = []
    interpretation.statements[0].quoted_text = batch.owned_units[0].excerpt.replace("三次", "三 次")
    checkpoint["run_result"]["source_interpretation"] = interpretation.model_dump(mode="json")
    assert source_calculation_gaps(store, "job-generic")[0].source_quote == batch.owned_units[0].excerpt
    interpretation.statements[0].quoted_text = "原文没有的计算定义"
    checkpoint["run_result"]["source_interpretation"] = interpretation.model_dump(mode="json")
    with pytest.raises(ScopeViolationError, match="原文摘录与冻结来源单元不一致"):
        source_calculation_gaps(store, "job-generic")


def test_publication_allows_noncalculated_source_through_this_guard() -> None:
    batch, interpretation = _source()
    for statement in interpretation.statements:
        statement.decision_functions = ["action"]
    _require_source_calculations_consumable(_publication_source_store(batch, interpretation), "job-generic")


def test_post_eligibility_calculation_does_not_block_current_review() -> None:
    batch, interpretation = _source()
    unit = batch.owned_units[0]
    unit.excerpt = "确认符合入排标准后，选择最近三次记录，取其均值作为研究结果。"
    statement = interpretation.statements[0]
    statement.quoted_text = "选择最近三次记录，取其均值作为研究结果。"
    statement.decision_functions = ["action", "calculation_input"]
    statement.eligibility_sequence = "after_eligibility_decision"
    statement.eligibility_sequence_quote = "确认符合入排标准后"
    coverage = SourceStatementCoverage(
        statement_index=0, structure_unit_id=unit.structure_unit_id,
        disposition="supporting_or_supplement", status="not_located",
    )
    store = _publication_source_store(batch, interpretation)
    saved = store.get_last_checkpoint("job-generic", "deep-1")[1]["run_result"]
    saved["source_statement_coverage"] = [coverage.model_dump(mode="json")]
    saved["source_target_review"] = {
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{
            "statement_index": 0, "decision": "not_current_control",
            "source_action_excerpt": statement.quoted_text,
            "non_control_basis_excerpt": statement.eligibility_sequence_quote,
        }],
    }
    assert [gap.statement_index for gap in source_calculation_gaps(store, "job-generic")] == [1]

    # An unverified source review cannot exclude a calculation from publication.
    saved["source_target_review"]["items"][0]["non_control_basis_excerpt"] = "没有这段先后说明"
    with pytest.raises(ScopeViolationError, match="来源核对记录无效"):
        source_calculation_gaps(store, "job-generic")
    saved["source_target_review"]["items"][0]["non_control_basis_excerpt"] = statement.eligibility_sequence_quote
    statement.decision_functions = ["definition", "calculation_input"]
    saved["source_interpretation"] = interpretation.model_dump(mode="json")
    assert [gap.statement_index for gap in source_calculation_gaps(store, "job-generic")] == [0, 1]
    statement.decision_functions = ["action", "calculation_input"]
    interpretation.statements[1].decision_functions = ["action"]
    saved["source_interpretation"] = interpretation.model_dump(mode="json")
    _require_source_calculations_consumable(store, "job-generic")


def test_mean_remains_source_bound_but_not_executable() -> None:
    batch, interpretation = _source()
    bound = bind_semantic_packet(batch, interpretation, [0, 1, 2], _packet())
    assert [point.capability for point in bound] == ["capability_gap", "not_applicable", "not_applicable"]
    assert bound[0].dependency_statement_indexes == [1]
    assert bound[0].source_ref == "body.p0"
    assert bound[0].source_span_ids == ["span-0"]
    assert "最近三次记录" in build_semantic_point_prompt(batch, interpretation, [0, 1])


def test_shared_action_can_keep_separate_source_bound_visit_scopes() -> None:
    batch, interpretation = _source()
    source = "筛选期和研究结束访视均须核查同一记录。"
    batch.owned_units[0].excerpt = source
    interpretation.statements[0].quoted_text = source
    interpretation.statements[0].decision_functions = ["action"]
    packet = SourceSemanticPacket.model_validate({
        "version": SEMANTIC_POINT_VERSION,
        "items": [
            {"statement_index": 0, "point_key": "screen", "exact_source_quote": "筛选期",
             "proposition": "筛选期须核查记录", "role": "action", "review_scope": "patient_eligibility"},
            {"statement_index": 0, "point_key": "end", "exact_source_quote": "研究结束访视",
             "proposition": "研究结束访视须核查记录", "role": "action", "review_scope": "patient_study_procedure"},
        ],
    })
    bound = bind_semantic_packet(batch, interpretation, [0], packet)
    assert [point.exact_point_quote for point in bound] == ["筛选期", "研究结束访视"]
    assert len({point.semantic_id for point in bound}) == 2
    prompt = build_semantic_point_prompt(batch, interpretation, [0])
    assert "各自时期" in prompt


def test_semantic_citations_keep_the_original_characters() -> None:
    batch, interpretation = _source()
    source = "筛选期（访视）须完成检查。"
    batch.owned_units[0].excerpt = source
    interpretation.statements[0].quoted_text = source
    interpretation.statements[0].decision_functions = ["action"]
    raw = SourceSemanticPacket.model_validate({
        "version": SEMANTIC_POINT_VERSION,
        "items": [{"statement_index": 0, "exact_source_quote": "筛选期（访视）",
                   "proposition": "筛选访视须完成检查", "role": "action",
                   "review_scope": "patient_eligibility"}],
    })
    assert bind_semantic_packet(batch, interpretation, [0], raw)[0].exact_point_quote == "筛选期（访视）"
    changed = raw.model_copy(deep=True)
    changed.items[0].exact_source_quote = "筛选期(访视)"
    with pytest.raises(ValueError, match="连续原串"):
        bind_semantic_packet(batch, interpretation, [0], changed)

    batch, interpretation = _source()
    batch.owned_units[0].excerpt = "选择最近三次记录，取其均值（算术）。"
    interpretation.statements[0].quoted_text = batch.owned_units[0].excerpt
    packet = _packet()
    packet.items[0].computation.operator_ref.quote = "取其均值(算术)"
    with pytest.raises(ValueError, match="连续原串"):
        bind_semantic_packet(batch, interpretation, [0, 1, 2], packet)


def test_single_point_revision_preserves_sibling_and_invalidates_dependents() -> None:
    batch, interpretation = _source()
    packet = _packet()
    before = bind_semantic_packet(batch, interpretation, [0, 1, 2], packet)
    old = packet.items[1]
    prompt = build_semantic_point_repair_prompt(
        batch, interpretation, packet, statement_index=1,
        point_key=old.point_key, issue="缺失政策须复核", visible_indexes=[0, 1, 2],
    )
    assert semantic_point_precondition(old) in prompt
    replacement_item = old.model_copy(update={"proposition": "原文规定缺失记录不填补"})
    replacement = SourceSemanticPacket(version=SEMANTIC_POINT_VERSION, items=[replacement_item])
    revised = apply_semantic_point_replacement(
        packet, replacement, statement_index=1, point_key=old.point_key,
        precondition_sha256=semantic_point_precondition(old),
    )
    after = bind_semantic_packet(batch, interpretation, [0, 1, 2], revised)
    assert packet.items[1].proposition == old.proposition
    assert after[0].semantic_id != before[0].semantic_id
    assert after[1].semantic_id != before[1].semantic_id
    assert after[2].semantic_id == before[2].semantic_id
    with pytest.raises(ValueError, match="原版本已变化"):
        apply_semantic_point_replacement(
            revised, replacement, statement_index=1, point_key=old.point_key,
            precondition_sha256=semantic_point_precondition(old),
        )
    with pytest.raises(ValueError, match="只能替换"):
        apply_semantic_point_replacement(
            packet, SourceSemanticPacket(version=SEMANTIC_POINT_VERSION, items=[packet.items[2]]),
            statement_index=1, point_key=old.point_key,
            precondition_sha256=semantic_point_precondition(old),
        )


def test_action_without_a_compiled_consumer_is_not_marked_ready() -> None:
    batch, interpretation = _source()
    batch.owned_units[0].excerpt = "筛选期须完成现场核查。"
    interpretation.statements[0].quoted_text = batch.owned_units[0].excerpt
    interpretation.statements[0].decision_functions = ["action"]
    packet = _packet().model_dump(mode="json")
    packet["items"] = [{
        "statement_index": 0, "proposition": "应按来源完成一次动作", "role": "action",
    }]
    bound = bind_semantic_packet(batch, interpretation, [0], SourceSemanticPacket.model_validate(packet))
    assert bound[0].capability == "unresolved"
    packet["items"][0]["review_scope"] = "patient_eligibility"
    bound = bind_semantic_packet(batch, interpretation, [0], SourceSemanticPacket.model_validate(packet))
    assert bound[0].capability == "capability_gap"
    assert SEMANTIC_BINDER_VERSION.endswith("/v33")


def test_structured_cross_statement_dependency_names_one_point_not_its_siblings() -> None:
    batch, interpretation = _source()
    batch.owned_units[1].excerpt = "缺失记录不填补；其他背景尚未核清。"
    interpretation.statements[1].quoted_text = batch.owned_units[1].excerpt
    interpretation.statements[0].decision_functions = ["action"]
    interpretation.statements[1].decision_functions = ["definition"]
    packet = SourceSemanticPacket.model_validate({
        "version": SEMANTIC_POINT_VERSION,
        "items": [
            {"statement_index": 0, "point_key": "decision", "proposition": "核对一次记录",
             "role": "condition", "review_scope": "patient_eligibility",
             "dependencies": [{"statement_index": 1, "point_key": "policy"}]},
            {"statement_index": 1, "point_key": "policy",
             "exact_source_quote": "缺失记录不填补", "proposition": "不填补缺失记录",
             "role": "constraint", "review_scope": "supporting_definition"},
            {"statement_index": 1, "point_key": "other",
             "exact_source_quote": "其他背景尚未核清", "proposition": "其他背景仍不清楚",
             "role": "unresolved", "review_scope": "unresolved",
             "unresolved_dimensions": ["原文未定义背景含义"]},
        ],
    })
    bound = bind_semantic_packet(batch, interpretation, [0, 1], packet)
    assert {point.point_key: point.capability for point in bound} == {
        "decision": "capability_gap", "policy": "capability_gap", "other": "unresolved",
    }
    changed = packet.model_copy(deep=True)
    changed.items[1].proposition = "缺失数据不作填补"
    after = bind_semantic_packet(batch, interpretation, [0, 1], changed)
    assert after[0].semantic_id != bound[0].semantic_id
    assert after[2].semantic_id == bound[2].semantic_id
    changed.items[0].dependencies[0].point_key = "not_returned"
    with pytest.raises(ValueError, match="有身份语义点"):
        bind_semantic_packet(batch, interpretation, [0, 1], changed)


def test_computation_with_unresolved_scope_keeps_dependent_condition_unresolved() -> None:
    batch, interpretation = _source()
    packet = _packet().model_copy(deep=True)
    packet.items[0].unresolved_dimensions = ["缺失规则的作用范围尚未核清"]
    with pytest.raises(ValueError, match="未核清的语义点"):
        bind_semantic_packet(batch, interpretation, [0, 1, 2], packet)
    packet.items[0].computation.missing_policy = "unresolved"
    packet.items[0].computation.missing_ref = None
    bound = bind_semantic_packet(batch, interpretation, [0, 1, 2], packet)
    assert bound[0].computation.operator == "mean"
    assert bound[0].computation.missing_policy == "unresolved"
    assert bound[0].capability == "unresolved"
    packet.items[0].unresolved_dimensions = []
    packet.items[1].role = "unresolved"
    packet.items[1].unresolved_dimensions = ["共用缺失规则未核清"]
    bound = bind_semantic_packet(batch, interpretation, [0, 1, 2], packet)
    assert [point.capability for point in bound] == [
        "unresolved", "unresolved", "not_applicable",
    ]


def test_explicit_missing_policy_keeps_its_source_but_not_rule_authority() -> None:
    batch, interpretation = _source()
    bound = bind_semantic_packet(batch, interpretation, [0, 1, 2], _packet())
    assert bound[0].computation.missing_ref.quote == "缺失记录不填补"
    assert bound[0].capability == "capability_gap"
    paraphrased = _packet().model_copy(deep=True)
    paraphrased.items[0].proposition = "本次审核值由最近三次记录取平均"
    after = bind_semantic_packet(batch, interpretation, [0, 1, 2], paraphrased)
    assert after[0].computation.missing_policy == "exclude"
    assert after[0].capability == "capability_gap"


def test_unresolved_missing_policy_cannot_carry_applied_fields() -> None:
    packet = _packet().model_dump(mode="json")
    calculation = packet["items"][0]["computation"]
    calculation["missing_policy"] = "unresolved"
    with pytest.raises(ValueError, match="适用范围未核清"):
        SourceSemanticPacket.model_validate(packet)
    calculation["missing_ref"] = None
    calculation["max_missing_count"] = {
        "value": 1, "number_text": "1",
        "source": {"statement_index": 1, "quote": "最多缺失1次"},
    }
    with pytest.raises(ValueError, match="适用范围未核清"):
        SourceSemanticPacket.model_validate(packet)


def test_unresolved_shared_policy_cannot_authorize_a_dependent_calculation() -> None:
    batch, interpretation = _source()
    packet = _packet().model_copy(deep=True)
    packet.items[1].role = "unresolved"
    packet.items[1].unresolved_dimensions = ["共用处理方式适用于哪些计算尚不清楚"]
    with pytest.raises(ValueError, match="共用来源尚未核清"):
        bind_semantic_packet(batch, interpretation, [0, 1, 2], packet)
    packet.items[0].computation.missing_policy = "unresolved"
    packet.items[0].computation.missing_ref = None
    bound = bind_semantic_packet(batch, interpretation, [0, 1, 2], packet)
    assert bound[0].capability == "unresolved"
    assert bound[0].computation.max_missing_count is None


def test_one_missing_count_shared_by_distinct_series_stays_unresolved() -> None:
    batch, interpretation = _source()
    batch.owned_units[0].excerpt = "甲的最近三次记录取均值，乙的最近四次记录取均值。"
    interpretation.statements[0].quoted_text = batch.owned_units[0].excerpt
    batch.owned_units[1].excerpt = "最多允许缺失1次，缺失记录不填补。"
    interpretation.statements[1].quoted_text = batch.owned_units[1].excerpt
    base = _packet().model_dump(mode="json")
    first = base["items"][0]
    first["point_key"] = "first"
    first["exact_source_quote"] = "甲的最近三次记录取均值"
    first["computation"]["operator_ref"]["quote"] = "取均值"
    first["computation"]["input_refs"] = [{
        "statement_index": 0, "quote": "甲的最近三次记录",
    }]
    first["computation"]["missing_ref"]["quote"] = "缺失记录不填补"
    first["computation"]["max_missing_count"] = {
        "value": 1, "number_text": "1",
        "source": {"statement_index": 1, "quote": "最多允许缺失1次"},
    }
    second = json.loads(json.dumps(first))
    second["point_key"] = "second"
    second["exact_source_quote"] = "乙的最近四次记录取均值"
    second["computation"]["input_refs"] = [{
        "statement_index": 0, "quote": "乙的最近四次记录",
    }]
    base["items"].insert(1, second)
    both = bind_semantic_packet(
        batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(base),
    )
    assert [point.capability for point in both[:2]] == ["unresolved", "unresolved"]
    assert all("计数适用范围" in point.unresolved_dimensions[-1] for point in both[:2])
    base["items"].pop(1)
    one = bind_semantic_packet(
        batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(base),
    )
    assert one[0].capability == "capability_gap"


def test_shared_missing_count_in_same_statement_stays_unresolved() -> None:
    batch, interpretation = _source()
    source = "甲的最近三次记录取均值，乙的最近四次记录取均值；最多允许缺失1次，缺失记录不填补。"
    batch.owned_units[0].excerpt = source
    interpretation.statements[0].quoted_text = source
    packet = _packet().model_dump(mode="json")
    first = packet["items"][0]
    first["point_key"] = "first"
    first["exact_source_quote"] = "甲的最近三次记录取均值"
    first["dependencies"] = [{"statement_index": 0, "point_key": "policy"}]
    first["computation"]["operator_ref"]["quote"] = "取均值"
    first["computation"]["input_refs"] = [{"statement_index": 0, "quote": "甲的最近三次记录"}]
    first["computation"]["missing_ref"] = {"statement_index": 0, "quote": "缺失记录不填补"}
    first["computation"]["max_missing_count"] = {
        "value": 1, "number_text": "1",
        "source": {"statement_index": 0, "quote": "最多允许缺失1次"},
    }
    second = json.loads(json.dumps(first))
    second["point_key"] = "second"
    second["exact_source_quote"] = "乙的最近四次记录取均值"
    second["computation"]["input_refs"][0]["quote"] = "乙的最近四次记录"
    policy = packet["items"][1]
    policy.update({"statement_index": 0, "point_key": "policy",
                   "exact_source_quote": "最多允许缺失1次，缺失记录不填补"})
    packet["items"] = [first, second, policy, packet["items"][2]]
    bound = bind_semantic_packet(batch, interpretation, [0, 2], SourceSemanticPacket.model_validate(packet))
    assert [point.capability for point in bound[:2]] == ["unresolved", "unresolved"]
    assert all("计数适用范围" in point.unresolved_dimensions[-1] for point in bound[:2])
    packet["items"].pop(1)
    single = bind_semantic_packet(batch, interpretation, [0, 2], SourceSemanticPacket.model_validate(packet))
    assert single[0].capability == "capability_gap"


def test_inquiry_summary_does_not_hide_unresolved_sibling() -> None:
    def result(*statuses: str) -> SourceInquiryResult:
        return SourceInquiryResult.model_validate({
            "version": INQUIRY_RESULT_VERSION,
            "point_results": [{
                "semantic_id": f"{index + 1:064x}", "status": status,
                "proposed_clarification": "仍需核对来源" if status == "remains_unknown" else "有源提案",
                "citations": [] if status == "remains_unknown" else [
                    {"structure_unit_id": "unit", "quote": "原文"},
                ],
            } for index, status in enumerate(statuses)],
        })

    assert _result_status(result("source_cited_proposal")) == "source_cited_proposal"
    assert _result_status(result("remains_unknown")) == "still_unresolved"
    assert _result_status(result("source_cited_proposal", "remains_unknown")) == "mixed_unresolved"


def test_source_quote_can_recover_a_misclassified_calculation_without_approving_it() -> None:
    batch, interpretation = _source()
    interpretation.statements[0].decision_functions = ["action"]
    bound = bind_semantic_packet(
        batch, interpretation, [0, 1, 2], _packet(),
    )
    assert bound[0].source_function_disagreement
    assert bound[0].capability == "capability_gap"
    assert bound[0].computation.operator_ref.quote == "取其均值"
    assert not bound[1].source_function_disagreement
    wrong_quote = _packet().model_dump(mode="json")
    wrong_quote["items"][0]["computation"]["operator_ref"]["quote"] = "取其最大值"
    with pytest.raises(ValueError, match="连续原串"):
        bind_semantic_packet(
            batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(wrong_quote),
        )


def test_partial_binding_keeps_independent_success_but_not_failed_dependencies() -> None:
    batch, interpretation = _source()
    packet = _packet().model_dump(mode="json")
    packet["items"][0]["dependencies"] = []
    packet["items"][0]["computation"]["missing_policy"] = "not_specified"
    packet["items"][0]["computation"]["missing_ref"] = None
    packet["items"][1]["proposition"] = "缺失方式没有原文"
    packet["items"][1]["role"] = "context"
    packet["items"][1]["review_scope"] = "study_level_background"
    bound, issues = bind_semantic_packet_partially(batch, interpretation, [0, 1, 2],
                                                   SourceSemanticPacket.model_validate(packet))
    assert [(point.statement_index, point.capability) for point in bound] == [
        (0, "capability_gap"), (2, "not_applicable")]
    assert [issue.statement_index for issue in issues] == [1]

    packet["items"][0]["dependencies"] = [{"statement_index": 1, "point_key": "main"}]
    bound, issues = bind_semantic_packet_partially(batch, interpretation, [0, 1, 2],
                                                   SourceSemanticPacket.model_validate(packet))
    assert [point.statement_index for point in bound] == [2]
    assert {issue.statement_index for issue in issues} == {0, 1}
    issue_by_statement = {issue.statement_index: issue for issue in issues}
    assert issue_by_statement[1].code == "point_invalid"
    assert "计算依赖" in issue_by_statement[1].reason
    assert issue_by_statement[0].code == "dependency_blocked"
    assert issue_by_statement[0].blocked_by.model_dump() == {
        "statement_index": 1, "point_key": "main",
    }
    assert "计算依赖" not in issue_by_statement[0].reason
    receipt = {"binding_issues": [issue.model_dump(mode="json") for issue in issues]}
    assert select_repair_issue(receipt, 1, "main")["reason"] == issue_by_statement[1].reason
    with pytest.raises(ValueError, match="真正出错"):
        select_repair_issue(receipt, 0, "main")


def test_partial_binding_keeps_valid_shared_calculation_policy() -> None:
    batch, interpretation = _source()
    bound, issues = bind_semantic_packet_partially(batch, interpretation, [0, 1, 2], _packet())
    assert not issues
    assert [point.statement_index for point in bound] == [0, 1, 2]
    assert [point.capability for point in bound] == [
        "capability_gap", "not_applicable", "not_applicable"]


def test_partial_binding_does_not_block_a_calculation_for_an_unrelated_sibling() -> None:
    batch, interpretation = _source()
    source = "缺失记录不填补，另列随访说明。"
    batch.owned_units[1].excerpt = source
    interpretation.statements[1].quoted_text = source
    packet = _packet().model_dump(mode="json")
    packet["items"][1]["exact_source_quote"] = "缺失记录不填补"
    packet["items"].insert(2, {
        "statement_index": 1, "point_key": "unrelated",
        "exact_source_quote": "未出现在原文的内容", "proposition": "另列随访说明",
        "role": "context", "review_scope": "study_level_background",
    })
    bound, issues = bind_semantic_packet_partially(
        batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(packet),
    )
    assert {(point.statement_index, point.point_key) for point in bound} == {
        (0, "main"), (1, "main"), (2, "main"),
    }
    assert [(issue.statement_index, issue.point_key) for issue in issues] == [(1, "unrelated")]

    wrong = _packet().model_dump(mode="json")
    wrong["items"][1]["point_key"] = "unrelated"
    wrong["items"][1]["exact_source_quote"] = "另列随访说明"
    wrong["items"][0]["dependencies"] = [
        {"statement_index": 1, "point_key": "unrelated"},
    ]
    bound, issues = bind_semantic_packet_partially(
        batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(wrong),
    )
    assert (0, "main") not in {(point.statement_index, point.point_key) for point in bound}
    assert any("包含该原文摘录" in issue.reason for issue in issues)


def test_partial_binding_rejects_computation_if_referenced_meaning_is_missing() -> None:
    batch, interpretation = _source()
    packet = _packet().model_dump(mode="json")
    packet["items"] = [packet["items"][0], packet["items"][2]]
    bound, issues = bind_semantic_packet_partially(
        batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(packet),
    )
    assert [point.statement_index for point in bound] == [2]
    assert {issue.statement_index for issue in issues} == {0, 1}
    assert any("有身份语义点" in issue.reason or "依赖陈述的语义" in issue.reason
               for issue in issues)


def test_source_point_identifier_does_not_reject_a_clinical_exception_name() -> None:
    packet = _packet().model_dump(mode="json")
    packet["items"][0]["point_key"] = "no_current_pet_contact_exception"
    assert SourceSemanticPacket.model_validate(packet).items[0].point_key == packet["items"][0]["point_key"]
    packet["items"][0]["point_key"] = "sigE_condition"
    assert SourceSemanticPacket.model_validate(packet).items[0].point_key == "sigE_condition"
    packet["items"][0]["point_key"] = "a" * 65
    with pytest.raises(ValueError):
        SourceSemanticPacket.model_validate(packet)


def test_old_raw_answer_can_be_inspected_without_becoming_current_dependency_proof() -> None:
    raw = _packet().model_dump(mode="json")
    raw["version"] = "phase5/control-semantic-point/v7"
    raw["items"][0]["point_key"] = "sigE_condition"
    parsed, previous = parse_reused_packet(json.dumps(raw, ensure_ascii=False))
    assert previous == "phase5/control-semantic-point/v7"
    assert parsed.items[0].point_key == "sigE_condition"
    assert parsed.items[0].dependency_point_keys == []
    raw["version"] = "phase5/control-semantic-point/v8"
    assert parse_reused_packet(json.dumps(raw, ensure_ascii=False))[1] == raw["version"]
    raw["version"] = "phase5/control-semantic-point/v10"
    raw["items"][0]["dependency_point_keys"] = ["main"]
    parsed, previous = parse_reused_packet(json.dumps(raw, ensure_ascii=False))
    assert previous == raw["version"]
    assert parsed.items[0].dependency_point_keys == []
    assert "旧版依赖" in parsed.items[0].unresolved_dimensions[-1]
    assert parsed.items[0].computation.missing_policy == "unresolved"
    assert parsed.items[0].computation.missing_ref is None
    raw["version"] = "phase5/control-semantic-point/v6"
    with pytest.raises(ValueError):
        parse_reused_packet(json.dumps(raw, ensure_ascii=False))


def test_current_packet_rejects_legacy_dependency_even_when_same_point_name_exists() -> None:
    raw = _packet().model_dump(mode="json")
    raw["items"][0]["dependency_point_keys"] = ["main"]
    with pytest.raises(ValueError, match="同时标明来源陈述序位和语义点标识"):
        SourceSemanticPacket.model_validate(raw)
    raw["items"][0]["dependency_point_keys"] = []
    raw["items"][0]["dependency_statement_indexes"] = [1]
    with pytest.raises(ValueError, match="同时标明来源陈述序位和语义点标识"):
        SourceSemanticPacket.model_validate(raw)


def test_old_ambiguous_dependency_remains_unresolved_after_read_only_migration() -> None:
    raw = _packet().model_dump(mode="json")
    raw["version"] = "phase5/control-semantic-point/v11"
    raw["items"][0]["dependency_point_keys"] = ["main"]
    packet, previous = parse_reused_packet(json.dumps(raw, ensure_ascii=False))
    assert previous == raw["version"]
    assert packet.items[0].dependency_point_keys == []
    assert "旧版依赖" in packet.items[0].unresolved_dimensions[-1]
    batch, interpretation = _source()
    bound = bind_semantic_packet(batch, interpretation, [0, 1, 2], packet)
    assert bound[0].capability == "unresolved"


def test_same_statement_dependency_keeps_only_independent_sibling() -> None:
    batch, interpretation = _source()
    excerpt = "参照原文诊断标准；符合该诊断；既往病史满两年。"
    batch.owned_units[0].excerpt = excerpt
    interpretation.statements[0].quoted_text = excerpt
    interpretation.statements[0].decision_functions = ["definition"]
    packet = {
        "version": SEMANTIC_POINT_VERSION,
        "items": [
            {"statement_index": 0, "point_key": "reference",
             "exact_source_quote": "参照原文诊断标准", "proposition": "诊断依据",
             "role": "definition", "review_scope": "supporting_definition"},
            {"statement_index": 0, "point_key": "diagnosis",
             "exact_source_quote": "符合该诊断", "proposition": "诊断条件",
             "role": "condition", "review_scope": "patient_eligibility",
             "dependencies": [{"statement_index": 0, "point_key": "reference"}]},
            {"statement_index": 0, "point_key": "history",
             "exact_source_quote": "既往病史满两年", "proposition": "病史条件",
             "role": "condition", "review_scope": "patient_eligibility"},
        ],
    }
    valid = SourceSemanticPacket.model_validate(packet)
    bound, issues = bind_semantic_packet_partially(batch, interpretation, [0], valid)
    assert not issues
    assert {point.point_key for point in bound} == {"reference", "diagnosis", "history"}
    assert next(point for point in bound if point.point_key == "diagnosis").dependencies[0].point_key == "reference"

    packet["items"][0]["exact_source_quote"] = "不存在的诊断标准"
    bound, issues = bind_semantic_packet_partially(
        batch, interpretation, [0], SourceSemanticPacket.model_validate(packet),
    )
    assert [point.point_key for point in bound] == ["history"]
    assert {issue.point_key for issue in issues} == {"reference", "diagnosis"}

    packet["items"] = packet["items"][1:]
    bound, issues = bind_semantic_packet_partially(
        batch, interpretation, [0], SourceSemanticPacket.model_validate(packet),
    )
    assert [point.point_key for point in bound] == ["history"]
    assert [issue.point_key for issue in issues] == ["diagnosis"]


def test_same_statement_unresolved_premise_propagates_without_hiding_independent_point() -> None:
    batch, interpretation = _source()
    excerpt = "参照原文诊断标准；符合该诊断；既往病史满两年。"
    batch.owned_units[0].excerpt = excerpt
    interpretation.statements[0].quoted_text = excerpt
    interpretation.statements[0].decision_functions = ["definition"]
    packet = SourceSemanticPacket.model_validate({
        "version": SEMANTIC_POINT_VERSION,
        "items": [
            {"statement_index": 0, "point_key": "reference",
             "exact_source_quote": "参照原文诊断标准", "proposition": "诊断依据尚不清楚",
             "role": "unresolved", "review_scope": "unresolved",
             "unresolved_dimensions": ["诊断标准正文尚未取得"]},
            {"statement_index": 0, "point_key": "diagnosis",
             "exact_source_quote": "符合该诊断", "proposition": "诊断条件",
             "role": "condition", "review_scope": "patient_eligibility",
             "dependencies": [{"statement_index": 0, "point_key": "reference"}]},
            {"statement_index": 0, "point_key": "history",
             "exact_source_quote": "既往病史满两年", "proposition": "病史条件",
             "role": "condition", "review_scope": "patient_eligibility"},
        ],
    })
    bound, issues = bind_semantic_packet_partially(batch, interpretation, [0], packet)
    assert not issues
    assert {point.point_key: point.capability for point in bound} == {
        "reference": "unresolved", "diagnosis": "unresolved", "history": "capability_gap",
    }


def test_same_statement_dependencies_cannot_prove_each_other_in_a_cycle() -> None:
    batch, interpretation = _source()
    excerpt = "须满足第一项和第二项。"
    batch.owned_units[0].excerpt = excerpt
    interpretation.statements[0].quoted_text = excerpt
    interpretation.statements[0].decision_functions = ["definition"]
    packet = SourceSemanticPacket.model_validate({
        "version": SEMANTIC_POINT_VERSION,
        "items": [
            {"statement_index": 0, "point_key": "first",
             "exact_source_quote": "第一项", "proposition": "第一项",
             "role": "condition", "review_scope": "patient_eligibility",
             "dependencies": [{"statement_index": 0, "point_key": "second"}]},
            {"statement_index": 0, "point_key": "second",
             "exact_source_quote": "第二项", "proposition": "第二项",
             "role": "condition", "review_scope": "patient_eligibility",
             "dependencies": [{"statement_index": 0, "point_key": "first"}]},
        ],
    })
    with pytest.raises(ValueError, match="形成循环"):
        bind_semantic_packet(batch, interpretation, [0], packet)


def test_cross_statement_dependencies_cannot_prove_each_other_in_a_cycle() -> None:
    batch, interpretation = _source()
    packet = _packet().model_dump(mode="json")
    packet["items"][0]["dependencies"] = [{"statement_index": 1, "point_key": "main"}]
    packet["items"][1]["dependencies"] = [{"statement_index": 0, "point_key": "main"}]
    with pytest.raises(ValueError, match="形成循环"):
        bind_semantic_packet(
            batch, interpretation, [0, 1, 2],
            SourceSemanticPacket.model_validate(packet),
        )


def test_same_statement_preserves_independent_aggregation_scope() -> None:
    batch, interpretation = _source()
    excerpt = "取最后三次读数的均值（总分和分项均计算）。"
    batch.owned_units[0].excerpt = excerpt
    interpretation.statements[0].quoted_text = excerpt
    packet = SourceSemanticPacket.model_validate({
        "version": SEMANTIC_POINT_VERSION,
        "items": [
                {"statement_index": 0, "point_key": "mean",
                 "exact_source_quote": "取最后三次读数的均值", "proposition": "最近三次求均值",
                 "role": "definition", "review_scope": "supporting_definition", "computation": {
                 "operator": "mean", "operator_ref": {"statement_index": 0, "quote": "均值"},
                 "input_refs": [{"statement_index": 0, "quote": "最后三次读数"}],
                 "missing_policy": "not_specified",
             }},
            {"statement_index": 0, "point_key": "scope",
             "exact_source_quote": "总分和分项均计算", "proposition": "总分和分项分别适用",
             "role": "constraint", "review_scope": "supporting_definition"},
        ],
    })
    bound, issues = bind_semantic_packet_partially(batch, interpretation, [0], packet)
    assert not issues
    assert [point.capability for point in bound] == ["capability_gap", "capability_gap"]
    assert bound[1].exact_point_quote == "总分和分项均计算"


def test_partial_binding_rejects_duplicate_identity_without_losing_sibling() -> None:
    batch, interpretation = _source()
    packet = _packet().model_dump(mode="json")
    packet["items"][1]["point_key"] = "duplicate"
    packet["items"].insert(2, {**packet["items"][1], "proposition": "重复身份"})
    bound, issues = bind_semantic_packet_partially(batch, interpretation, [0, 1, 2],
                                                   SourceSemanticPacket.model_validate(packet))
    assert [point.statement_index for point in bound] == [2]
    assert {issue.statement_index for issue in issues} == {0, 1}


def test_background_cannot_be_used_as_calculation_input() -> None:
    batch, interpretation = _source()
    packet = _packet().model_dump(mode="json")
    packet["items"][0]["computation"]["input_refs"] = [{
        "statement_index": 2, "quote": "记录表的填写背景",
    }]
    with pytest.raises(ValueError, match="计算依赖"):
        bind_semantic_packet(batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(packet))


def test_background_cannot_supply_only_the_missing_count_quote() -> None:
    batch, interpretation = _source()
    batch.owned_units[1].excerpt = "缺失记录不填补，最多缺失1次。"
    interpretation.statements[1].quoted_text = batch.owned_units[1].excerpt
    packet = _packet().model_dump(mode="json")
    packet["items"][0]["computation"]["max_missing_count"] = {
        "value": 1, "number_text": "1",
        "source": {"statement_index": 1, "quote": "最多缺失1次"},
    }
    packet["items"][1].update({
        "exact_source_quote": "最多缺失1次", "role": "context",
        "review_scope": "study_level_background",
    })
    with pytest.raises(ValueError, match="计算依赖"):
        bind_semantic_packet(batch, interpretation, [0, 1, 2],
                             SourceSemanticPacket.model_validate(packet))


def test_semantic_identity_changes_with_source_scope_not_only_quote() -> None:
    batch, interpretation = _source()
    first = bind_semantic_packet(batch, interpretation, [0, 1, 2], _packet())[0]
    changed = interpretation.model_copy(deep=True)
    changed.statements[0].time_words = ["最近三次记录"]
    second = bind_semantic_packet(batch, changed, [0, 1, 2], _packet())[0]
    assert first.exact_quote == second.exact_quote
    assert first.semantic_id != second.semantic_id
    assert second.source_statement.time_words == ["最近三次记录"]


def test_read_only_context_is_available_without_becoming_an_output_point() -> None:
    batch, interpretation = _source()
    prompt = build_semantic_point_prompt(batch, interpretation, [0], context_indexes=[1])
    assert '"purpose": "output"' in prompt
    assert '"purpose": "read_only_context"' in prompt
    packet = _packet().model_dump(mode="json")
    packet["items"] = packet["items"][:1]
    packet["items"][0]["dependencies"] = []
    bound = bind_semantic_packet(
        batch, interpretation, [0], SourceSemanticPacket.model_validate(packet),
        context_indexes=[1],
    )
    assert bound[0].dependency_statement_indexes == [1]
    assert bound[0].capability == "unresolved"
    assert "相邻原文" in bound[0].unresolved_dimensions[-1]
    changed = interpretation.model_copy(deep=True)
    changed.statements[1].force = "required"
    changed_bound = bind_semantic_packet(
        batch, changed, [0], SourceSemanticPacket.model_validate(packet),
        context_indexes=[1],
    )
    assert changed_bound[0].semantic_id != bound[0].semantic_id
    with pytest.raises(ValueError, match="未提供的来源陈述"):
        bind_semantic_packet(batch, interpretation, [0], SourceSemanticPacket.model_validate(packet))
    packet["items"][0]["dependencies"] = []
    with pytest.raises(ValueError, match="未提供"):
        bind_semantic_packet(batch, interpretation, [0], SourceSemanticPacket.model_validate(packet))
    packet["items"][0]["dependencies"] = [{"statement_index": 2, "point_key": "main"}]
    with pytest.raises(ValueError, match="另一条有身份语义点"):
        bind_semantic_packet(batch, interpretation, [0],
                             SourceSemanticPacket.model_validate(packet), context_indexes=[1])
    with pytest.raises(ValueError, match="重复"):
        build_semantic_point_prompt(batch, interpretation, [0], context_indexes=[0])


def test_shared_missing_policy_may_be_a_constraint_referenced_by_calculations() -> None:
    batch, interpretation = _source()
    packet = _packet().model_dump(mode="json")
    packet["items"][1]["computation"] = None
    packet["items"][1]["role"] = "constraint"
    packet["items"][0]["computation"]["missing_ref"] = {
        "statement_index": 1, "quote": "缺失记录不填补",
    }
    bound = bind_semantic_packet(
        batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(packet)
    )
    assert bound[1].capability == "not_applicable"
    packet["items"][0]["computation"]["missing_policy"] = "not_specified"
    packet["items"][0]["computation"]["missing_ref"] = None
    with pytest.raises(ValueError, match="计算相关陈述"):
        bind_semantic_packet(
            batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(packet)
        )


def test_decision_source_cannot_be_downgraded_to_background_or_unused_constraint() -> None:
    batch, interpretation = _source()
    packet = _packet().model_dump(mode="json")
    packet["items"] = [{
        "statement_index": 0, "proposition": "仅说明背景", "role": "context",
    }]
    with pytest.raises(ValueError, match="纯背景必须说明不是个例入排要求"):
        bind_semantic_packet(batch, interpretation, [0], SourceSemanticPacket.model_validate(packet))
    packet["items"] = [{
        "statement_index": 1, "proposition": "缺失记录不填补", "role": "constraint",
        "review_scope": "supporting_definition",
    }]
    with pytest.raises(ValueError, match="计算相关陈述"):
        bind_semantic_packet(batch, interpretation, [1], SourceSemanticPacket.model_validate(packet))
    interpretation.statements[1].decision_functions = ["threshold"]
    bound = bind_semantic_packet(batch, interpretation, [1], SourceSemanticPacket.model_validate(packet))
    assert bound[0].capability == "capability_gap"


@pytest.mark.parametrize("changes", [
    {"operator_ref": {"statement_index": 1, "quote": "按已有记录"}},
    {"operator_ref": {"statement_index": 0, "quote": "取其最大值"}},
    {"input_refs": [{"statement_index": 1, "quote": "最近三次记录"}]},
    {"input_refs": []},
    {"missing_ref": {"statement_index": 0, "quote": "缺失记录不填补"}},
])
def test_wrong_or_unlocated_calculation_evidence_is_rejected(changes) -> None:
    batch, interpretation = _source()
    packet = _packet().model_dump(mode="json")
    packet["items"][0]["computation"].update(changes)
    with pytest.raises(ValueError):
        bind_semantic_packet(
            batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(packet)
        )


def test_missing_or_duplicate_source_point_is_rejected() -> None:
    batch, interpretation = _source()
    packet = _packet().model_copy(deep=True)
    packet.items.pop()
    with pytest.raises(ValueError, match="至少对应"):
        bind_semantic_packet(batch, interpretation, [0, 1, 2], packet)
    packet.items.append(packet.items[0])
    with pytest.raises(ValueError, match="至少对应"):
        bind_semantic_packet(batch, interpretation, [0, 1, 2], packet)


def test_same_statement_can_split_study_background_from_subject_definition() -> None:
    batch, interpretation = _source()
    excerpt = "计划纳入164例中重度患者。"
    batch.owned_units[0].excerpt = excerpt
    interpretation.statements[0].quoted_text = excerpt
    interpretation.statements[0].decision_functions = ["definition"]
    packet = SourceSemanticPacket.model_validate({
        "version": SEMANTIC_POINT_VERSION,
        "items": [
            {"statement_index": 0, "point_key": "sample-size",
             "exact_source_quote": "计划纳入164例", "role": "context",
             "review_scope": "study_level_background", "proposition": "研究计划例数，不是个例条件"},
            {"statement_index": 0, "point_key": "population",
             "exact_source_quote": "中重度患者", "role": "definition",
             "review_scope": "supporting_definition", "proposition": "适用人群的严重程度仍须对照正式标准"},
        ],
    })
    bound = bind_semantic_packet(batch, interpretation, [0], packet)
    assert len({point.semantic_id for point in bound}) == 2
    assert [point.exact_point_quote for point in bound] == ["计划纳入164例", "中重度患者"]
    assert [point.capability for point in bound] == ["unresolved", "capability_gap"]
    assert bound[0].source_function_disagreement
    assert not bound[1].source_function_disagreement
    as_study_action = packet.model_dump(mode="json")
    as_study_action["items"][0]["role"] = "action"
    assert bind_semantic_packet(
        batch, interpretation, [0], SourceSemanticPacket.model_validate(as_study_action)
    )[0].capability == "unresolved"
    duplicate = packet.model_dump(mode="json")
    duplicate["items"][1]["point_key"] = "sample-size"
    with pytest.raises(ValueError, match="身份不得重复"):
        bind_semantic_packet(batch, interpretation, [0], SourceSemanticPacket.model_validate(duplicate))
    duplicate["items"][1]["point_key"] = "population"
    duplicate["items"][1]["exact_source_quote"] = "未出现的严重程度"
    with pytest.raises(ValueError, match="连续原串"):
        bind_semantic_packet(batch, interpretation, [0], SourceSemanticPacket.model_validate(duplicate))


def test_calculation_and_disjoint_study_background_in_one_statement() -> None:
    batch, interpretation = _source()
    extra = "本研究计划纳入164例。"
    batch.owned_units[0].excerpt += extra
    interpretation.statements[0].quoted_text += extra
    packet = _packet().model_dump(mode="json")
    packet["items"] = [
        {**packet["items"][0], "point_key": "mean", "dependencies": [],
         "exact_source_quote": "选择最近三次记录，取其均值"},
        {"statement_index": 0, "point_key": "sample-size", "exact_source_quote": "计划纳入164例",
         "role": "context", "review_scope": "study_level_background",
         "proposition": "研究规模不是测量输入"},
    ]
    bound = bind_semantic_packet(
        batch, interpretation, [0], SourceSemanticPacket.model_validate(packet), context_indexes=[1],
    )
    assert [point.capability for point in bound] == ["unresolved", "unresolved"]
    packet["items"][1]["exact_source_quote"] = "最近三次记录"
    with pytest.raises(ValueError, match="计算依赖"):
        bind_semantic_packet(
            batch, interpretation, [0], SourceSemanticPacket.model_validate(packet), context_indexes=[1],
        )


def test_required_source_cannot_be_automatically_dismissed_as_background() -> None:
    batch, interpretation = _source()
    interpretation.statements[2].force = "required"
    bound = bind_semantic_packet(batch, interpretation, [2], SourceSemanticPacket.model_validate({
        "version": SEMANTIC_POINT_VERSION,
        "items": [{"statement_index": 2, "point_key": "study-context",
                   "exact_source_quote": "记录表的填写背景", "role": "context",
                   "review_scope": "study_level_background", "proposition": "据称只是背景"}],
    }))
    assert bound[0].capability == "unresolved"
    assert bound[0].source_function_disagreement


def test_unresolved_schedule_columns_cannot_be_dismissed_as_background() -> None:
    batch, interpretation = _source()
    unit = batch.owned_units[2]
    unit.excerpt = "某项检查 | X"
    unit.unit_kind = StructureUnitKind.TABLE_ROW
    unit.table_context = TableCellContext(
        table_path=(0, 0), row_index=0, column_index=0,
        member_cell_paths=[(0, 0), (0, 1)], column_headers=["筛选期"],
    )
    interpretation.statements[2].quoted_text = unit.excerpt
    packet = SourceSemanticPacket.model_validate({
        "version": SEMANTIC_POINT_VERSION,
        "items": [{"statement_index": 2, "proposition": "据称只是研究背景",
                   "role": "context", "review_scope": "study_level_background"}],
    })
    bound = bind_semantic_packet(batch, interpretation, [2], packet)
    assert bound[0].capability == "unresolved"
    prompt = build_semantic_point_prompt(batch, interpretation, [2])
    assert '"table_context"' in prompt
    assert '"column_headers": ["筛选期"]' in prompt


def test_schedule_mark_alone_cannot_prove_eligibility_requirement() -> None:
    batch, interpretation = _source()
    unit = batch.owned_units[2]
    unit.excerpt = "某项探索性检查 | X"
    unit.unit_kind = StructureUnitKind.TABLE_ROW
    unit.table_context = TableCellContext(
        table_path=(0, 0), row_index=0, column_index=0,
        member_cell_paths=[(0, 0), (0, 1)], column_headers=["筛选期"],
    )
    interpretation.statements[2].quoted_text = unit.excerpt
    for scope in ("patient_eligibility", "patient_study_procedure"):
        packet = SourceSemanticPacket.model_validate({
            "version": SEMANTIC_POINT_VERSION,
            "items": [{"statement_index": 2, "proposition": "检查安排需核对其入排作用",
                       "role": "action", "review_scope": scope}],
        })
        bound = bind_semantic_packet(batch, interpretation, [2], packet)
        assert bound[0].capability == "unresolved"


def test_bounded_inquiry_reads_only_frozen_units_and_does_not_edit_points() -> None:
    batch, interpretation = _source()
    point = bind_semantic_packet(batch, interpretation, [0, 1, 2], _packet())[0]
    point = point.model_copy(update={"capability": "unresolved"})
    assert point.semantic_id in build_inquiry_plan_prompt([point])
    plan = SourceInquiryPlan(version=INQUIRY_PLAN_VERSION, queries=["缺失记录"], reason="核对缺失数据规则")
    sources = materialize_inquiry_sources(plan, batch.owned_units)
    assert [source.structure_unit_id for source in sources] == ["u1"]
    assert sources[0].source_ref == "body.p1"
    assert point.capability == "unresolved"
    with pytest.raises(ValueError, match="冻结方案"):
        materialize_inquiry_sources(SourceInquiryPlan(
            version=INQUIRY_PLAN_VERSION, read_structure_unit_ids=["outside"], reason="核对引用来源"
        ), batch.owned_units)
    with pytest.raises(ValueError, match="搜索或明确"):
        SourceInquiryPlan(version=INQUIRY_PLAN_VERSION, reason="未给任何查阅动作")


def test_inquiry_search_finds_separated_terms_in_another_section() -> None:
    batch, _ = _source()
    original = batch.owned_units[0]
    units = [
        original.model_copy(update={
            "structure_unit_id": "threshold", "excerpt": "筛选时量表X评分至少5分。",
            "heading_path": ["入选标准"], "source_order": 1,
        }),
        original.model_copy(update={
            "structure_unit_id": "repeated-threshold", "excerpt": "基线时量表X评分至少5分。",
            "heading_path": ["入选标准"], "source_order": 2,
        }),
        original.model_copy(update={
            "structure_unit_id": "method", "excerpt": "量表X的评分方法按四项症状分别记录。",
            "heading_path": ["评估方法"], "source_order": 3,
        }),
    ]
    plan = SourceInquiryPlan(
        version=INQUIRY_PLAN_VERSION, queries=["量表X 评分 方法"],
        read_structure_unit_ids=["threshold"], reason="查找另一章节的计算定义",
    )
    sources = materialize_inquiry_sources(plan, units, max_sources=2)
    assert [item.structure_unit_id for item in sources] == ["threshold", "method"]
    assert sources[1].excerpt == units[2].excerpt
    with pytest.raises(ValueError, match="不能静默省略"):
        materialize_inquiry_sources(plan.model_copy(update={
            "read_structure_unit_ids": ["threshold", "method"],
        }), units, max_sources=1)
    missing = SourceInquiryPlan(
        version=INQUIRY_PLAN_VERSION, queries=["另一种完全不存在的记录"],
        read_structure_unit_ids=["threshold"], reason="查找未见过的要求",
    )
    assert [item.structure_unit_id for item in materialize_inquiry_sources(missing, units)] == ["threshold"]


def test_inquiry_resolution_requires_visible_source_and_never_promotes_truncated_text() -> None:
    batch, interpretation = _source()
    point = bind_semantic_packet(batch, interpretation, [0, 1, 2], _packet())[0]
    source = materialize_inquiry_sources(
        SourceInquiryPlan(version=INQUIRY_PLAN_VERSION, read_structure_unit_ids=["u1"], reason="核对缺失记录"),
        batch.owned_units,
    )[0]
    result = SourceInquiryResult.model_validate({
        "version": INQUIRY_RESULT_VERSION,
        "point_results": [{
            "semantic_id": point.semantic_id, "status": "source_cited_proposal",
            "proposed_clarification": "缺失记录不填补",
            "citations": [{"structure_unit_id": "u1", "quote": "缺失记录不填补"}],
        }],
    })
    assert verify_inquiry_result(result, [point], [source]) is result
    with pytest.raises(ValueError, match="查得原文"):
        verify_inquiry_result(result, [point], [source.model_copy(update={"excerpt": "无关内容"})])
    changed_punctuation = result.model_copy(deep=True)
    changed_punctuation.point_results[0].citations[0].quote = "缺失记录（不填补）"
    with pytest.raises(ValueError, match="查得原文"):
        verify_inquiry_result(
            changed_punctuation, [point],
            [source.model_copy(update={"excerpt": "缺失记录(不填补)"})],
        )
    with pytest.raises(ValueError, match="未完整呈现"):
        verify_inquiry_result(result, [point], [source.model_copy(update={"truncated": True})])
    with pytest.raises(ValueError):
        SourceInquiryResult.model_validate({
            "version": INQUIRY_RESULT_VERSION,
            "point_results": [{
                "semantic_id": point.semantic_id,
                "status": "clarified",
                "proposed_clarification": "不能以模型意见宣称已核清",
                "citations": [{"structure_unit_id": "u1", "quote": "缺失记录不填补"}],
            }],
        })


def test_text_transport_includes_schema_once_and_keeps_product_model_route(monkeypatch) -> None:
    adapter = object.__new__(OpenAICompatibleProtocolControlAgentTransport)
    adapter._response_format_mode = "text"
    captured = {}

    def complete(messages, *, response_format, with_receipt=False):
        captured["messages"] = messages
        captured["response_format"] = response_format
        assert with_receipt is True
        return json.dumps(_packet().model_dump(mode="json"), ensure_ascii=False), {
            "attempts": [{"finish_reason": "stop", "usage": None}],
        }

    monkeypatch.setattr(adapter, "_complete", complete)
    response = adapter.read_semantic_points(prompt="冻结来源：例子")
    assert SourceSemanticPacket.model_validate_json(response.text).version == SEMANTIC_POINT_VERSION
    assert "冻结来源：例子" in captured["messages"][0]["content"]
    assert "protocol_control_semantic_point_v14" == captured["response_format"]["json_schema"]["name"]
    assert captured["messages"][0]["content"].count('"$defs"') == 1
    assert response.transport_receipt == {
        "attempts": [{"finish_reason": "stop", "usage": None}],
    }


def test_stream_receipt_keeps_usage_chunk_without_choices() -> None:
    final = SimpleNamespace(
        id="request-7", model="model-7", usage=None,
        choices=[SimpleNamespace(finish_reason="stop", delta=SimpleNamespace(content="{}"))],
    )
    usage = SimpleNamespace(
        id="request-7", model="model-7", choices=[],
        usage={"prompt_tokens": 41, "completion_tokens": 9},
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: iter([final, usage]),
    )))
    response = OpenAICompatibleProtocolControlAgentTransport._stream_completion(
        client, {"model": "model-7", "messages": []},
    )
    assert response.id == "request-7"
    assert response.model == "model-7"
    assert response.usage == {"prompt_tokens": 41, "completion_tokens": 9}
    assert response.choices[0].message.content == "{}"


def test_saved_model_answer_cannot_cross_source_or_prompt_identity() -> None:
    identity = {
        "source_job_id": "job-a", "batch_id": "batch-a",
        "source_probe_sha256": "a" * 64, "prompt_sha256": "b" * 64,
        "indexes": [0, 1], "context_indexes": [],
    }
    receipt = {**identity, "raw_response": _packet().model_dump_json(),
               "model_identity": {"requested": "test-model", "reported": "test-model"}}
    encoded = json.dumps(receipt).encode()
    assert reuse_raw_response(encoded, identity)["model_identity"] == {
        "requested": "test-model", "reported": "test-model",
    }
    with pytest.raises(ValueError, match="身份不一致"):
        reuse_raw_response(encoded, {**identity, "prompt_sha256": "c" * 64})
    with pytest.raises(ValueError, match="身份不一致"):
        reuse_raw_response(encoded, {**identity, "indexes": [0]})
    with pytest.raises(ValueError, match="身份不一致"):
        reuse_raw_response(encoded, {**identity, "context_indexes": [2]})


def test_declared_counts_need_matching_numeral_and_source() -> None:
    batch, interpretation = _source()
    packet = _packet().model_dump(mode="json")
    calculation = packet["items"][0]["computation"]
    calculation["declared_input_count"] = {
        "value": 3, "number_text": "三",
        "source": {"statement_index": 0, "quote": "最近三次记录"},
    }
    bind_semantic_packet(batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(packet))
    calculation["declared_input_count"]["value"] = 4
    with pytest.raises(ValueError, match="次数与原文数词"):
        bind_semantic_packet(batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(packet))
    calculation["declared_input_count"]["value"] = 3
    calculation["declared_input_count"]["source"]["statement_index"] = 1
    with pytest.raises(ValueError, match="输入次数须引用"):
        bind_semantic_packet(batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(packet))


def test_shared_missing_allowance_has_own_source_and_cannot_exceed_total() -> None:
    batch, interpretation = _source()
    interpretation.statements[1].quoted_text = "最多缺失一次记录；缺失记录不填补，只按已有记录计算。"
    batch.owned_units[1].excerpt = interpretation.statements[1].quoted_text
    packet = _packet().model_dump(mode="json")
    calculation = packet["items"][0]["computation"]
    calculation["declared_input_count"] = {
        "value": 3, "number_text": "三",
        "source": {"statement_index": 0, "quote": "最近三次记录"},
    }
    calculation["max_missing_count"] = {
        "value": 1, "number_text": "一",
        "source": {"statement_index": 1, "quote": "最多缺失一次记录"},
    }
    bind_semantic_packet(batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(packet))
    calculation["max_missing_count"]["value"] = 2
    with pytest.raises(ValueError, match="次数与原文数词"):
        bind_semantic_packet(batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(packet))


def test_count_cannot_be_extracted_from_a_larger_number() -> None:
    batch, interpretation = _source()
    interpretation.statements[0].quoted_text = "选择最近十三次记录，取其均值作为本次审核值。"
    batch.owned_units[0].excerpt = interpretation.statements[0].quoted_text
    packet = _packet().model_dump(mode="json")
    packet["items"][0]["computation"]["declared_input_count"] = {
        "value": 3, "number_text": "三",
        "source": {"statement_index": 0, "quote": "最近十三次记录"},
    }
    with pytest.raises(ValueError, match="次数必须逐字"):
        bind_semantic_packet(batch, interpretation, [0, 1, 2], SourceSemanticPacket.model_validate(packet))
