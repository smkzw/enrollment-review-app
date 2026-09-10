"""问题精化反例：来源覆盖缺失精化为未解析时间锚点的保存与发布边界。

局部方案语义修订合同：

- 仅当同一父规则、同一来源定位证明 ``PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING``
  精化为 ``TIME_ANCHOR_UNRESOLVED`` 时，局部修订可以保存；精化只把
  “来源内容缺失”收紧为“内容已在、时间锚点待确认”，因此草稿仍然不可发布；
- 外来来源、不同父规则、不同未解析问题和普通新问题继续按“新指纹回归”拒绝。

比较器级反例直接约束 ``regressing_rule_codes``；服务级反例通过
``apply_feedback`` 的原文理解纠错流程约束保存行为。合法精化的接受
用例在精化比较实现落地前按当前实现应失败（这正是被修复的误判）。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from app.agents.protocol_deconstructor import regressing_rule_codes
from app.domain.contracts.agent_io import (
    EvidenceRequirementDraft,
    ProtocolSourceMaterial,
    RuleComponentDraft,
)
from app.domain.contracts.enums import Comparator, ReviewStage
from app.domain.contracts.protocol_drafts import DraftFeedbackKind
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    EvidenceRequirement,
    RuleComponent,
)
from app.protocols.deconstruction_gate import (
    CHECK_NAMES,
    ProtocolDeconstructionGate,
    ProtocolDeconstructionGateResult,
    ProtocolGateCheckResult,
    ProtocolGateIssue,
)
from app.services.protocol_workbench_service import (
    ProtocolWorkbenchError,
    ProtocolWorkbenchService,
)
from tests.v2.protocols.slice4_helpers import confirmed_fixture
from tests.v2.protocols.test_deconstruction_gate_slice3 import _catalog, _fixture, _span

# JobStore 持久化列使用 UTC naive；测试服务时间必须与运行时一致。
NAIVE_NOW = datetime(2026, 8, 17, tzinfo=timezone.utc).replace(tzinfo=None)

# 通用夹具中的 EX-01 父规则新增一段实质性来源：既往回溯范围没有写明
# 锚点日期，只能保存为待确认的方案解释问题，不得静默当成无限期病史。
NOTE_SPAN = "span-ex-note"
NOTE_TEXT = "既往3个月内患有严重神经系统疾病"
DISEASE_TERM = "严重神经系统疾病"


# ---------------------------------------------------------------------------
# 场景构建
# ---------------------------------------------------------------------------


def _gap_scenario():
    """EX-01 目录新增一段未承接来源的基线：真实门禁只报来源覆盖缺失。"""

    source_input, draft, spans = confirmed_fixture()
    catalog = source_input.parent_rule_catalog
    items = [
        item.model_copy(update={"source_span_ids": ("span-ex", NOTE_SPAN)})
        if item.official_code == "EX-01"
        else item
        for item in catalog.items
    ]
    source_input = source_input.model_copy(
        update={
            "parent_rule_catalog": _catalog(catalog.catalog_kind, items),
            "allowed_source_span_ids": [
                *source_input.allowed_source_span_ids,
                NOTE_SPAN,
            ],
            "source_materials": [
                *source_input.source_materials,
                ProtocolSourceMaterial(
                    source_span_id=NOTE_SPAN,
                    source_ref="body.p5",
                    block_order=5,
                    text=NOTE_TEXT,
                ),
            ],
        }
    )
    spans = {**spans, NOTE_SPAN: _span(NOTE_SPAN, 5)}
    mappings = [
        mapping.model_copy(update={"source_span_ids": ["span-ex", NOTE_SPAN]})
        if mapping.catalog_item_id == "parent:ex01"
        else mapping
        for mapping in draft.parent_catalog_mappings
    ]
    draft = draft.model_copy(update={"parent_catalog_mappings": mappings})
    return source_input, draft, spans


def _note_predicate(
    predicate_id="predicate-ex-note",
    *,
    clause=NOTE_TEXT,
    comparator=Comparator.IN,
    value=None,
):
    return AtomicPredicate(
        predicate_id=predicate_id,
        subject="受试者",
        attribute=DISEASE_TERM,
        source_term=DISEASE_TERM,
        source_clause=clause,
        comparator=comparator,
        value=value if value is not None else [DISEASE_TERM],
    )


def _anchored_predicate(predicate_id="predicate-ex-note"):
    """同样承接来源片段、但不含回溯范围的原子条件。"""

    return _note_predicate(
        predicate_id=predicate_id, clause=f"患有{DISEASE_TERM}"
    )


def _draft_with_note_component(
    draft,
    *,
    refs,
    predicate=None,
    component_id="component-ex-note",
    display_code="EX-01b",
    requirement_id="req-ex-note",
):
    """在 EX-01 下新增一个承接指定来源片段的子规则（含来源与资料映射）。"""

    predicate = predicate or _note_predicate()
    requirement = EvidenceRequirement(
        requirement_id=requirement_id,
        rule_component_id=component_id,
        fact_type="方案要求事实",
        due_stage=ReviewStage.SCREENING,
        description="核对正式原始资料和研究者记录",
    )
    component = RuleComponent(
        rule_component_id=component_id,
        parent_rule_id="rule-ex",
        display_code=display_code,
        title="既往病史回溯",
        expression=AtomicExpression(predicate=predicate),
        evidence_requirements=[requirement],
    )
    rules = [
        rule.model_copy(update={"components": [*rule.components, component]})
        if rule.official_code == "EX-01"
        else rule
        for rule in draft.proposed_rules
    ]
    component_draft = RuleComponentDraft(
        draft_component_id=f"draft-{component_id}",
        parent_official_code="EX-01",
        proposed_component=component,
        source_refs=list(refs),
        source_excerpts=[NOTE_TEXT],
    )
    requirement_draft = EvidenceRequirementDraft(
        draft_requirement_id=f"draft-{requirement_id}",
        draft_component_id=f"draft-{component_id}",
        proposed_requirement=requirement,
        source_refs=list(refs),
    )
    stages = [
        stage.model_copy(
            update={
                "due_requirement_ids": [*stage.due_requirement_ids, requirement_id]
            }
        )
        if stage.stage == ReviewStage.SCREENING
        else stage
        for stage in draft.proposed_workflow_stages
    ]
    return draft.model_copy(
        update={
            "proposed_rules": rules,
            "component_drafts": [*draft.component_drafts, component_draft],
            "evidence_requirement_drafts": [
                *draft.evidence_requirement_drafts,
                requirement_draft,
            ],
            "proposed_workflow_stages": stages,
        }
    )


def _rewrite_alt_clause_with_lookback(draft):
    """把 EX-01 既有原子条件 ALT 改写成未解析回溯，模拟“另一个未解析问题”。"""

    rule = next(
        item for item in draft.proposed_rules if item.official_code == "EX-01"
    )
    component = rule.components[0]
    children = list(component.expression.children)
    rewritten = AtomicExpression(
        predicate=children[0].predicate.model_copy(
            update={"source_clause": "既往3个月内ALT或AST≥1.5×ULN"}
        ),
    )
    new_expression = component.expression.model_copy(
        update={"children": [rewritten, *children[1:]]}
    )
    new_component = component.model_copy(update={"expression": new_expression})
    rules = [
        rule.model_copy(update={"components": [new_component, *rule.components[1:]]})
        if item.official_code == "EX-01"
        else item
        for item in draft.proposed_rules
    ]
    bindings = [
        item.model_copy(update={"proposed_component": new_component})
        if item.proposed_component.rule_component_id == component.rule_component_id
        else item
        for item in draft.component_drafts
    ]
    return draft.model_copy(
        update={"proposed_rules": rules, "component_drafts": bindings}
    )


def _boundary_issue(code, check_name, problem, refs):
    return ProtocolGateIssue(
        issue_code=code,
        check_name=check_name,
        level="阻止发布",
        problem=problem,
        impact="当前草稿不能作为正式入排规则发布。",
        next_action="请回到方案原文逐项核对后重新检查。",
        affected_refs=list(refs),
        repair_scope=list(refs),
    )


def _atomic_expressions(expression):
    if expression.kind == "predicate":
        yield expression
        return
    for child in expression.children:
        yield from _atomic_expressions(child)


class RefinementBoundaryGate:
    """只表达来源覆盖缺失与未解析时间锚点两类问题的微型确定性门禁。

    服务级精化边界反例用它隔离真实门禁的其余检查，精确控制前后两稿
    的完整性问题指纹；问题定位语义与真实门禁一致（覆盖缺失携带
    父规则与缺失片段，未解析锚点携带谓词身份）。
    """

    def __init__(self, **gap_spans_by_code: tuple[str, ...]) -> None:
        self._gap_spans_by_code = gap_spans_by_code

    def evaluate(self, _source_input, draft, **_kwargs) -> ProtocolDeconstructionGateResult:
        covered: dict[str, set[str]] = {}
        for item in draft.component_drafts:
            covered.setdefault(item.parent_official_code, set()).update(
                item.source_refs
            )
        issues: dict[str, list[ProtocolGateIssue]] = {
            "source_coverage": [],
            "temporal_semantics": [],
        }
        for code, gap_spans in self._gap_spans_by_code.items():
            missing = sorted(set(gap_spans) - covered.get(code, set()))
            if missing:
                issues["source_coverage"].append(
                    _boundary_issue(
                        "PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING",
                        "source_coverage",
                        f"{code} 原文存在未承接的来源片段。",
                        [code, *missing],
                    )
                )
        for rule in draft.proposed_rules:
            for component in rule.components:
                for expression in _atomic_expressions(component.expression):
                    text = "".join(expression.predicate.exact_source_clauses)
                    if (
                        expression.time_constraint is None
                        and re.search(r"\d+\s*个?月内", text)
                    ):
                        issues["temporal_semantics"].append(
                            _boundary_issue(
                                "TIME_ANCHOR_UNRESOLVED",
                                "temporal_semantics",
                                f"{component.display_code} 的既往回溯范围缺少锚点日期。",
                                [expression.predicate.predicate_id],
                            )
                        )
        checks = [
            ProtocolGateCheckResult(
                check_name=name,
                passed=not issues.get(name),
                issues=issues.get(name, []),
            )
            for name in CHECK_NAMES
        ]
        return ProtocolDeconstructionGateResult(
            publishable=not any(item.issues for item in checks),
            checks=checks,
        )


# ---------------------------------------------------------------------------
# 服务级反例
# ---------------------------------------------------------------------------

def _make_service(session_factory, data_paths, *, gate=None, feedback_reviser=None):
    return ProtocolWorkbenchService(
        session_factory,
        data_paths=data_paths,
        now=lambda: NAIVE_NOW,
        gate=gate,
        feedback_reviser=feedback_reviser,
    )


def _write_minimal_docx(data_paths, name: str):
    directory = data_paths.root / "uploads"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(b"\x00" * 32)
    return path


def _seed_review(service, data_paths, source_input, draft, spans, *, key):
    started = service.start_first_deconstruction(
        upload_path=_write_minimal_docx(data_paths, f"{key}.docx"),
        original_name=f"{key}.docx",
        idempotency_key=key,
        actor="医学监查员",
    )
    service.seed_review_session(
        started.job_id,
        source_input=source_input,
        draft=draft,
        source_spans=spans,
        wait_at="await_review",
    )
    return started.job_id


def _apply_source_error(service, job_id):
    detail = service.get_draft_detail(job_id)
    return service.apply_feedback(
        job_id,
        expected_revision_id=detail.revision.revision_id,
        feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
        target_rule_code="EX-01",
        feedback_note="补齐该父规则缺失的来源内容。",
        actor="医学监查员",
    )


def test_refined_unresolved_anchor_saves_but_stays_unpublishable(
    slice4_env, data_paths
) -> None:
    """合法精化：同一父规则、同一来源片段的覆盖缺失收紧为未解析锚点。

    修订可以保存为新草稿修订，但新锚点仍是阻断问题，草稿依旧不可发布。
    """
    _factory, _now = slice4_env
    source_input, draft, spans = _gap_scenario()
    baseline = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    baseline_codes = {
        issue.issue_code
        for check in baseline.checks
        for issue in check.issues
    }
    assert "PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING" in baseline_codes
    assert baseline.publishable is False

    def revise(_source_input, current_draft, _target_rule_code, _feedback_note):
        return _draft_with_note_component(current_draft, refs=[NOTE_SPAN])

    service = _make_service(_factory, data_paths, feedback_reviser=revise)
    job_id = _seed_review(
        service,
        data_paths,
        source_input,
        draft,
        spans,
        key="refine-unresolved-anchor-legal",
    )
    before = service.get_draft_detail(job_id)

    after = _apply_source_error(service, job_id)

    assert after.revision.revision_number == before.revision.revision_number + 1
    revised_rule = next(
        rule
        for rule in after.revision.content.proposed_rules
        if rule.official_code == "EX-01"
    )
    assert any(
        component.rule_component_id == "component-ex-note"
        for component in revised_rule.components
    )

    integrity = service.get_integrity(job_id)
    codes = {issue["issue_code"] for issue in integrity.issues}
    assert "PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING" not in codes
    assert "TIME_ANCHOR_UNRESOLVED" in codes
    assert integrity.publishable is False
    assert integrity.blocking_count >= 1


def test_refinement_carrying_extra_new_problem_still_rejected(
    slice4_env, data_paths
) -> None:
    """精化候选若同时夹带其他新问题，整体仍按回归拒绝。"""
    _factory, _now = slice4_env
    source_input, draft, spans = _gap_scenario()

    def revise(_source_input, current_draft, _target_rule_code, _feedback_note):
        # 承接同一片段，但原子条件使用原文不支持的否定比较，构成普通新问题。
        predicate = _note_predicate(
            comparator=Comparator.NE, value=DISEASE_TERM
        )
        return _draft_with_note_component(
            current_draft, refs=[NOTE_SPAN], predicate=predicate
        )

    service = _make_service(_factory, data_paths, feedback_reviser=revise)
    job_id = _seed_review(
        service,
        data_paths,
        source_input,
        draft,
        spans,
        key="refine-unresolved-anchor-extra",
    )
    before = service.get_draft_detail(job_id)

    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        _apply_source_error(service, job_id)

    assert exc_info.value.code == "FEEDBACK_REVISION_FAILED"
    assert (
        service.get_draft_detail(job_id).revision.revision_id
        == before.revision.revision_id
    )


@pytest.mark.parametrize(
    ("mode", "extra_refs"),
    [
        ("同规则其他来源", ["span-ex"]),
        ("其他父规则来源", ["span-in"]),
    ],
)
def test_service_rejects_refinement_proven_by_foreign_source(
    slice4_env, data_paths, mode, extra_refs
) -> None:
    """覆盖缺失被干净承接后，别处新增的未解析锚点不得借用该精化证明。"""
    _factory, _now = slice4_env
    _source_input, draft, spans = confirmed_fixture()

    def revise(_source_input, current_draft, _target_rule_code, _feedback_note):
        closed = _draft_with_note_component(
            current_draft,
            refs=[NOTE_SPAN],
            predicate=_anchored_predicate(),
        )
        return _draft_with_note_component(
            closed,
            refs=extra_refs,
            predicate=_note_predicate(predicate_id="predicate-ex-extra"),
            component_id="component-ex-extra",
            display_code="EX-01c",
            requirement_id="req-ex-extra",
        )

    service = _make_service(
        _factory,
        data_paths,
        gate=RefinementBoundaryGate(**{"EX-01": (NOTE_SPAN,)}),
        feedback_reviser=revise,
    )
    job_id = _seed_review(
        service,
        data_paths,
        _source_input,
        draft,
        spans,
        key=f"refine-foreign-source-{mode}",
    )
    before = service.get_draft_detail(job_id)

    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        _apply_source_error(service, job_id)

    assert exc_info.value.code == "FEEDBACK_REVISION_FAILED"
    assert (
        service.get_draft_detail(job_id).revision.revision_id
        == before.revision.revision_id
    )


def test_service_rejects_unresolved_anchor_without_same_rule_gap(
    slice4_env, data_paths
) -> None:
    """覆盖缺失在 IN-01 时，EX-01 新增的未解析锚点没有精化前科可循。"""
    _factory, _now = slice4_env
    _source_input, draft, spans = confirmed_fixture()

    def revise(_source_input, current_draft, _target_rule_code, _feedback_note):
        return _draft_with_note_component(current_draft, refs=[NOTE_SPAN])

    service = _make_service(
        _factory,
        data_paths,
        gate=RefinementBoundaryGate(**{"IN-01": ("span-in-note",)}),
        feedback_reviser=revise,
    )
    job_id = _seed_review(
        service,
        data_paths,
        _source_input,
        draft,
        spans,
        key="refine-other-rule-gap",
    )
    before = service.get_draft_detail(job_id)

    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        _apply_source_error(service, job_id)

    assert exc_info.value.code == "FEEDBACK_REVISION_FAILED"
    assert (
        service.get_draft_detail(job_id).revision.revision_id
        == before.revision.revision_id
    )


def test_service_rejects_unresolved_anchor_on_unrelated_existing_predicate(
    slice4_env, data_paths
) -> None:
    """覆盖缺口被干净承接后，既有谓词上新出现的未解析锚点是另一个问题。"""
    _factory, _now = slice4_env
    _source_input, draft, spans = confirmed_fixture()

    def revise(_source_input, current_draft, _target_rule_code, _feedback_note):
        closed = _draft_with_note_component(
            current_draft,
            refs=[NOTE_SPAN],
            predicate=_anchored_predicate(),
        )
        return _rewrite_alt_clause_with_lookback(closed)

    service = _make_service(
        _factory,
        data_paths,
        gate=RefinementBoundaryGate(**{"EX-01": (NOTE_SPAN,)}),
        feedback_reviser=revise,
    )
    job_id = _seed_review(
        service,
        data_paths,
        _source_input,
        draft,
        spans,
        key="refine-existing-predicate",
    )
    before = service.get_draft_detail(job_id)

    with pytest.raises(ProtocolWorkbenchError) as exc_info:
        _apply_source_error(service, job_id)

    assert exc_info.value.code == "FEEDBACK_REVISION_FAILED"
    assert (
        service.get_draft_detail(job_id).revision.revision_id
        == before.revision.revision_id
    )


# ---------------------------------------------------------------------------
# 比较器级反例
# ---------------------------------------------------------------------------


def _gate_issue(code, refs, *, check_name="temporal_semantics"):
    return _boundary_issue(code, check_name, "需要核对的完整性问题。", refs)


COVERAGE_MISSING = "PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING"
TIME_ANCHOR_UNRESOLVED = "TIME_ANCHOR_UNRESOLVED"


def _previous_state():
    _source_input, draft, _spans = _fixture()
    return draft


def test_comparator_accepts_same_source_coverage_to_unresolved_refinement():
    """合法精化：同父规则、同来源片段的覆盖缺失收紧为未解析锚点，不算回归。"""
    previous = _previous_state()
    revised = _draft_with_note_component(previous, refs=[NOTE_SPAN])
    previous_issues = [_gate_issue(COVERAGE_MISSING, ["EX-01", NOTE_SPAN], check_name="source_coverage")]
    revised_issues = [_gate_issue(TIME_ANCHOR_UNRESOLVED, ["predicate-ex-note"])]

    assert (
        regressing_rule_codes(
            previous,
            previous_issues,
            revised,
            revised_issues,
            ["EX-01"],
        )
        == set()
    )


def test_comparator_keeps_accepting_plain_gap_closing():
    """覆盖缺失被干净承接且无新增问题时，维持“改进不算回归”。"""
    previous = _previous_state()
    revised = _draft_with_note_component(
        previous, refs=[NOTE_SPAN], predicate=_anchored_predicate()
    )
    previous_issues = [_gate_issue(COVERAGE_MISSING, ["EX-01", NOTE_SPAN], check_name="source_coverage")]

    assert (
        regressing_rule_codes(
            previous,
            previous_issues,
            revised,
            [],
            ["EX-01"],
        )
        == set()
    )


@pytest.mark.parametrize(
    ("mode", "refs"),
    [
        ("同规则其他来源", ["span-ex"]),
        ("其他父规则来源", ["span-in"]),
    ],
)
def test_comparator_rejects_unresolved_anchor_from_foreign_source(mode, refs):
    """新未解析锚点所属子规则没有引用缺失片段时，精化证明不成立。"""
    previous = _previous_state()
    revised = _draft_with_note_component(previous, refs=refs)
    previous_issues = [_gate_issue(COVERAGE_MISSING, ["EX-01", NOTE_SPAN], check_name="source_coverage")]
    revised_issues = [_gate_issue(TIME_ANCHOR_UNRESOLVED, ["predicate-ex-note"])]

    assert regressing_rule_codes(
        previous,
        previous_issues,
        revised,
        revised_issues,
        ["EX-01"],
    ) == {"EX-01"}


def test_comparator_rejects_mixed_missing_and_foreign_source_refs():
    """精化组件同时引用缺失片段和其他片段时，来源归属不唯一。"""
    previous = _previous_state()
    revised = _draft_with_note_component(
        previous, refs=[NOTE_SPAN, "span-ex"]
    )
    previous_issues = [
        _gate_issue(
            COVERAGE_MISSING,
            ["EX-01", NOTE_SPAN],
            check_name="source_coverage",
        )
    ]
    revised_issues = [
        _gate_issue(TIME_ANCHOR_UNRESOLVED, ["predicate-ex-note"])
    ]

    assert regressing_rule_codes(
        previous,
        previous_issues,
        revised,
        revised_issues,
        ["EX-01"],
    ) == {"EX-01"}


def test_comparator_rejects_unresolved_anchor_on_rule_without_gap():
    """覆盖缺失在 IN-01 时，EX-01 的新未解析锚点不得跨规则借用证明。"""
    previous = _previous_state()
    revised = _draft_with_note_component(previous, refs=[NOTE_SPAN])
    previous_issues = [_gate_issue(COVERAGE_MISSING, ["IN-01", "span-in-note"], check_name="source_coverage")]
    revised_issues = [_gate_issue(TIME_ANCHOR_UNRESOLVED, ["predicate-ex-note"])]

    assert regressing_rule_codes(
        previous,
        previous_issues,
        revised,
        revised_issues,
        ["IN-01", "EX-01"],
    ) == {"EX-01"}


def test_comparator_rejects_unresolved_anchor_on_unrelated_existing_predicate():
    """缺口干净承接后，既有谓词上的新未解析锚点不能冒充同一精化。"""
    previous = _previous_state()
    closed = _draft_with_note_component(
        previous, refs=[NOTE_SPAN], predicate=_anchored_predicate()
    )
    revised = _rewrite_alt_clause_with_lookback(closed)
    previous_issues = [_gate_issue(COVERAGE_MISSING, ["EX-01", NOTE_SPAN], check_name="source_coverage")]
    revised_issues = [_gate_issue(TIME_ANCHOR_UNRESOLVED, ["predicate-alt"])]

    assert regressing_rule_codes(
        previous,
        previous_issues,
        revised,
        revised_issues,
        ["EX-01"],
    ) == {"EX-01"}


@pytest.mark.parametrize(
    "code",
    ["TIME_ANCHOR_MISSING", "NEGATION_NOT_BOUND_TO_SOURCE"],
)
def test_comparator_rejects_new_fingerprints_outside_refinement_pair(code):
    """同位置出现的新问题若不是允许的精化目标编码，继续按新指纹拒绝。"""
    previous = _previous_state()
    revised = _draft_with_note_component(previous, refs=[NOTE_SPAN])
    previous_issues = [_gate_issue(COVERAGE_MISSING, ["EX-01", NOTE_SPAN], check_name="source_coverage")]
    revised_issues = [_gate_issue(code, ["predicate-ex-note"])]

    assert regressing_rule_codes(
        previous,
        previous_issues,
        revised,
        revised_issues,
        ["EX-01"],
    ) == {"EX-01"}


def test_comparator_rejects_refinement_alongside_extra_new_problem():
    """精化目标之外还夹带其他新问题时，目标规则整体仍算回归。"""
    previous = _previous_state()
    revised = _draft_with_note_component(previous, refs=[NOTE_SPAN])
    previous_issues = [_gate_issue(COVERAGE_MISSING, ["EX-01", NOTE_SPAN], check_name="source_coverage")]
    revised_issues = [
        _gate_issue(TIME_ANCHOR_UNRESOLVED, ["predicate-ex-note"]),
        _gate_issue("NEGATION_NOT_BOUND_TO_SOURCE", ["predicate-alt"]),
    ]

    assert regressing_rule_codes(
        previous,
        previous_issues,
        revised,
        revised_issues,
        ["EX-01"],
    ) == {"EX-01"}


def test_comparator_keeps_rejecting_unresolved_anchor_without_any_gap():
    """没有任何覆盖缺失前科时，新未解析锚点就是普通新问题。"""
    previous = _previous_state()
    revised = _draft_with_note_component(previous, refs=[NOTE_SPAN])
    revised_issues = [_gate_issue(TIME_ANCHOR_UNRESOLVED, ["predicate-ex-note"])]

    assert regressing_rule_codes(
        previous,
        [],
        revised,
        revised_issues,
        ["EX-01"],
    ) == {"EX-01"}
