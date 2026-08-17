"""切片 6：八类结构化差异详情回归（新增/删除/原文/逻辑/时间窗/例外/证据要求/
应完成阶段）。

``compute_draft_diff`` 的粗粒度字段（rule codes / stage ids / component ids）保留
兼容前序调用方；新增的 ``rule_diffs`` 按官方父规则编号对齐，逐条输出八类结构化
详情。本文件验证：八类各自独立检出、相互不串扰；子组件按展示编号等稳定键对齐
（不依赖随机 ID）；新增/删除在规则与子组件两个粒度；差异输出确定可重建（门禁
diff_integrity 可复算声明）。
"""
from __future__ import annotations

import copy
import json

from app.domain.contracts.enums import (
    AnchorType,
    LogicalOperator,
    ReviewStage,
    TimeDirection,
)
from app.domain.contracts.protocol_drafts import ProtocolDraftRevisionDiff
from app.domain.contracts.rules import (
    AtomicExpression,
    EvidenceRequirement,
    RuleComponent,
    TimeConstraint,
)
from app.protocols.deconstruction_gate import (
    ProtocolDeconstructionGate,
    ProtocolDraftDiffDeclaration,
)
from app.services.protocol_draft_service import compute_draft_diff

from tests.v2.protocols.slice4_helpers import confirmed_fixture
from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture, _predicate

CATEGORY_FIELDS = (
    "original_text_changes",
    "logic_changes",
    "time_window_changes",
    "exception_changes",
    "evidence_changes",
    "due_stage_changes",
)


def _rule_diff(diff: ProtocolDraftRevisionDiff, official_code: str):
    return next(
        item for item in diff.rule_diffs if item.official_code == official_code
    )


def _assert_only_category(rule_diff, category_field: str) -> None:
    """断言只有指定类别有变化，其余五类为空（类别隔离）。"""

    for field in CATEGORY_FIELDS:
        changes = getattr(rule_diff, field)
        if field == category_field:
            assert changes, f"{category_field} 应检出变化"
        else:
            assert not changes, f"{field} 不应因 {category_field} 变化而触发: {changes}"


def _component(draft, code: str, display_code: str) -> RuleComponent:
    rule = _rule_of(draft, code)
    return next(
        component
        for component in rule.components
        if component.display_code == display_code
    )


def _rule_of(draft, code: str):
    return next(rule for rule in draft.proposed_rules if rule.official_code == code)


def test_original_text_change_rule_source_text() -> None:
    """父规则原文变化：输出 kind=rule 的原文类别条目，其他七类为空。"""

    _source_input, previous, _spans = confirmed_fixture()
    current = copy.deepcopy(previous)
    rule = _rule_of(current, "IN-01")
    current.proposed_rules = [
        rule.model_copy(update={"source_text": "年龄≥18周岁（修订版）"})
        if rule.official_code == "IN-01"
        else rule
        for rule in current.proposed_rules
    ]
    diff = compute_draft_diff(previous, current)
    rule_diff = _rule_diff(diff, "IN-01")
    assert rule_diff.added is False and rule_diff.removed is False
    assert len(rule_diff.original_text_changes) == 1
    change = rule_diff.original_text_changes[0]
    assert change.kind == "rule"
    assert change.stable_ref == "IN-01"
    assert change.previous["source_text"] == "年龄≥18岁"
    assert change.current["source_text"] == "年龄≥18周岁（修订版）"
    _assert_only_category(rule_diff, "original_text_changes")


def test_original_text_change_component_excerpt() -> None:
    """子组件方案摘录变化：原文类别检出组件级条目。"""

    _source_input, previous, _spans = confirmed_fixture()
    current = copy.deepcopy(previous)
    target_id = "draft-component-in"
    target = next(
        item for item in current.component_drafts if item.draft_component_id == target_id
    )
    current.component_drafts = [
        target.model_copy(update={"source_excerpts": [*target.source_excerpts, "补充摘录"]})
        if item.draft_component_id == target_id
        else item
        for item in current.component_drafts
    ]
    diff = compute_draft_diff(previous, current)
    rule_diff = _rule_diff(diff, "IN-01")
    change = next(
        change
        for change in rule_diff.original_text_changes
        if change.kind == "component"
    )
    assert change.stable_ref == "IN-01a"
    assert change.previous["source_binding"]["source_excerpts"] == ["年龄≥18岁"]
    assert change.current["source_binding"]["source_excerpts"] == [
        "年龄≥18岁",
        "补充摘录",
    ]
    _assert_only_category(rule_diff, "original_text_changes")


def test_logic_change_threshold() -> None:
    """逻辑变化：阈值改变只落入逻辑类别（时间窗/例外/证据/阶段不串扰）。"""

    _source_input, previous, _spans = confirmed_fixture()
    current = copy.deepcopy(previous)
    component = _component(current, "IN-01", "IN-01a")
    new_component = component.model_copy(
        update={
            "expression": component.expression.model_copy(
                update={
                    "predicate": component.expression.predicate.model_copy(
                        update={"value": 20}
                    )
                }
            )
        }
    )
    current.proposed_rules = [
        rule.model_copy(
            update={
                "components": [
                    new_component
                    if comp.rule_component_id == component.rule_component_id
                    else comp
                    for comp in rule.components
                ]
            }
        )
        if rule.official_code == "IN-01"
        else rule
        for rule in current.proposed_rules
    ]
    diff = compute_draft_diff(previous, current)
    rule_diff = _rule_diff(diff, "IN-01")
    change = next(
        change for change in rule_diff.logic_changes if change.stable_ref == "IN-01a"
    )
    assert change.kind == "component"
    predicate_before = change.previous["predicate"]
    predicate_after = change.current["predicate"]
    assert predicate_before["value"] == 18
    assert predicate_after["value"] == 20
    # 原文片段与时间约束不属于逻辑快照
    assert "source_clause" not in predicate_before
    assert "time_constraint" not in change.previous
    _assert_only_category(rule_diff, "logic_changes")


def test_time_window_change_only() -> None:
    """时间窗变化：新增相对锚点时间窗只落入时间窗类别。"""

    _source_input, previous, _spans = confirmed_fixture()
    current = copy.deepcopy(previous)
    component = _component(current, "IN-01", "IN-01a")
    windowed_expression = AtomicExpression(
        predicate=component.expression.predicate,
        time_constraint=TimeConstraint(
            anchor_type=AnchorType.SCREENING_DATE,
            direction=TimeDirection.BEFORE,
            upper_bound_days=28,
        ),
    )
    new_component = component.model_copy(update={"expression": windowed_expression})
    current.proposed_rules = [
        rule.model_copy(
            update={
                "components": [
                    new_component
                    if comp.rule_component_id == component.rule_component_id
                    else comp
                    for comp in rule.components
                ]
            }
        )
        if rule.official_code == "IN-01"
        else rule
        for rule in current.proposed_rules
    ]
    diff = compute_draft_diff(previous, current)
    rule_diff = _rule_diff(diff, "IN-01")
    change = next(
        change
        for change in rule_diff.time_window_changes
        if change.stable_ref == "IN-01a"
    )
    assert change.previous[0]["time_constraint"] is None
    assert change.current[0]["time_constraint"]["anchor_type"] == "screening_date"
    _assert_only_category(rule_diff, "time_window_changes")


def test_exception_change_only() -> None:
    """例外变化：新增例外表达式只落入例外类别。"""

    _source_input, previous, _spans = confirmed_fixture()
    current = copy.deepcopy(previous)
    component = _component(current, "IN-01", "IN-01a")
    new_component = component.model_copy(
        update={
            "exception_expression": _predicate(
                "predicate-exception",
                "研究者判断",
                "可接受",
                "unitless",
            )
        }
    )
    current.proposed_rules = [
        rule.model_copy(
            update={
                "components": [
                    new_component
                    if comp.rule_component_id == component.rule_component_id
                    else comp
                    for comp in rule.components
                ]
            }
        )
        if rule.official_code == "IN-01"
        else rule
        for rule in current.proposed_rules
    ]
    diff = compute_draft_diff(previous, current)
    rule_diff = _rule_diff(diff, "IN-01")
    change = next(
        change
        for change in rule_diff.exception_changes
        if change.stable_ref == "IN-01a"
    )
    assert change.previous is None
    assert change.current["kind"] == "predicate"
    _assert_only_category(rule_diff, "exception_changes")


def test_evidence_change_only() -> None:
    """证据要求变化：资料要求描述变化只落入证据类别。"""

    _source_input, previous, _spans = confirmed_fixture()
    current = copy.deepcopy(previous)
    component = _component(current, "IN-01", "IN-01a")
    new_component = component.model_copy(
        update={
            "evidence_requirements": [
                requirement.model_copy(
                    update={"description": "核对正式原始资料与研究者评估记录"}
                )
                for requirement in component.evidence_requirements
            ]
        }
    )
    current.proposed_rules = [
        rule.model_copy(
            update={
                "components": [
                    new_component
                    if comp.rule_component_id == component.rule_component_id
                    else comp
                    for comp in rule.components
                ]
            }
        )
        if rule.official_code == "IN-01"
        else rule
        for rule in current.proposed_rules
    ]
    diff = compute_draft_diff(previous, current)
    rule_diff = _rule_diff(diff, "IN-01")
    change = next(
        change for change in rule_diff.evidence_changes if change.kind == "component"
    )
    assert change.stable_ref == "IN-01a"
    assert (
        change.previous[0]["description"] == "核对正式原始资料和研究者记录"
    )
    assert (
        change.current[0]["description"]
        == "核对正式原始资料与研究者评估记录"
    )
    _assert_only_category(rule_diff, "evidence_changes")


def test_due_stage_change_only() -> None:
    """应完成阶段变化：资料要求到期阶段变化只落入应完成阶段类别。"""

    _source_input, previous, _spans = confirmed_fixture()
    current = copy.deepcopy(previous)
    component = _component(current, "IN-01", "IN-01a")
    new_component = component.model_copy(
        update={
            "evidence_requirements": [
                requirement.model_copy(update={"due_stage": ReviewStage.BASELINE})
                for requirement in component.evidence_requirements
            ]
        }
    )
    current.proposed_rules = [
        rule.model_copy(
            update={
                "components": [
                    new_component
                    if comp.rule_component_id == component.rule_component_id
                    else comp
                    for comp in rule.components
                ]
            }
        )
        if rule.official_code == "IN-01"
        else rule
        for rule in current.proposed_rules
    ]
    diff = compute_draft_diff(previous, current)
    rule_diff = _rule_diff(diff, "IN-01")
    change = next(
        change
        for change in rule_diff.due_stage_changes
        if change.stable_ref == "IN-01a"
    )
    assert change.kind == "component"
    assert change.previous == ["screening"]
    assert change.current == ["baseline"]
    _assert_only_category(rule_diff, "due_stage_changes")


def test_requirement_added_and_removed_within_component() -> None:
    """子组件内证据要求新增/删除：以 requirement 粒度输出证据类别条目。"""

    source_input, previous, source_spans = _fixture()
    component = _component(previous, "IN-01", "IN-01a")
    added_req = EvidenceRequirement(
        requirement_id="req-extra",
        rule_component_id=component.rule_component_id,
        fact_type="方案要求事实",
        due_stage=ReviewStage.SCREENING,
        description="研究者复核记录",
    )
    current = copy.deepcopy(previous)
    current_component = _component(current, "IN-01", "IN-01a")
    current.proposed_rules = [
        rule.model_copy(
            update={
                "components": [
                    current_component.model_copy(
                        update={
                            "evidence_requirements": [
                                *current_component.evidence_requirements,
                                added_req,
                            ]
                        }
                    )
                    if comp.rule_component_id == current_component.rule_component_id
                    else comp
                    for comp in rule.components
                ]
            }
        )
        if rule.official_code == "IN-01"
        else rule
        for rule in current.proposed_rules
    ]
    diff = compute_draft_diff(previous, current)
    rule_diff = _rule_diff(diff, "IN-01")
    requirement_change = next(
        change
        for change in rule_diff.evidence_changes
        if change.kind == "requirement"
    )
    assert requirement_change.stable_ref == "IN-01a#req[1]"
    assert requirement_change.previous is None
    assert requirement_change.current == {"requirement_id": "req-extra"}

    # 删除方向：回到前一稿，新增条目从当前稿消失
    diff_removed = compute_draft_diff(current, previous)
    rule_diff_removed = _rule_diff(diff_removed, "IN-01")
    removed_change = next(
        change
        for change in rule_diff_removed.evidence_changes
        if change.kind == "requirement"
    )
    assert removed_change.previous == {"requirement_id": "req-extra"}
    assert removed_change.current is None


def test_component_added_and_removed_aligned_by_display_code() -> None:
    """子组件新增/删除按展示编号列出，不依赖随机组件 ID。"""

    source_input, previous, source_spans = _fixture()
    rule = _rule_of(previous, "EX-01")
    extra_component = RuleComponent(
        rule_component_id="component-ex-b",
        parent_rule_id=rule.rule_id,
        display_code="EX-01b",
        title="另一项排除条件",
        expression=_predicate(
            "predicate-ex-b",
            "既往病史",
            "存在",
            "unitless",
        ),
    )
    current = copy.deepcopy(previous)
    current_rule = _rule_of(current, "EX-01")
    current.proposed_rules = [
        rule.model_copy(update={"components": [*rule.components, extra_component]})
        if rule.official_code == "EX-01"
        else rule
        for rule in current.proposed_rules
    ]
    diff = compute_draft_diff(previous, current)
    added = _rule_diff(diff, "EX-01")
    assert added.added_component_refs == ["EX-01b"]
    assert added.removed_component_refs == []
    # 组件显示名/标题变化不计为任何类别变化（快照剔除外观字段）
    assert not added.logic_changes

    diff_removed = compute_draft_diff(current, previous)
    removed = _rule_diff(diff_removed, "EX-01")
    assert removed.removed_component_refs == ["EX-01b"]


def test_rule_added_and_removed() -> None:
    """父规则新增/删除：rule_diffs 给出 added/removed 标记与子组件引用。"""

    source_input, previous, source_spans = _fixture()
    new_rule = _rule_of(previous, "IN-01").model_copy(
        update={
            "rule_id": "rule-in-02",
            "official_code": "IN-02",
            "components": [
                _component(previous, "IN-01", "IN-01a").model_copy(
                    update={
                        "rule_component_id": "component-in-02",
                        "parent_rule_id": "rule-in-02",
                        "display_code": "IN-02a",
                    }
                )
            ],
        }
    )
    current = copy.deepcopy(previous)
    current.proposed_rules = [*current.proposed_rules, new_rule]
    diff = compute_draft_diff(previous, current)
    added = _rule_diff(diff, "IN-02")
    assert added.added is True
    assert added.added_component_refs == ["IN-02a"]
    assert diff.added_rule_codes == ["IN-02"]

    diff_removed = compute_draft_diff(current, previous)
    removed = _rule_diff(diff_removed, "IN-02")
    assert removed.removed is True
    assert removed.removed_component_refs == ["IN-02a"]
    assert diff_removed.removed_rule_codes == ["IN-02"]
    # 删除时既非新增也非修改
    assert removed.added is False


def test_component_alignment_ignores_random_ids() -> None:
    """对齐不依赖随机 ID：仅改组件 ID 与谓词 ID 不产生任何差异。"""

    source_input, previous, source_spans = _fixture()
    current = copy.deepcopy(previous)
    rule = _rule_of(current, "IN-01")
    component = _component(current, "IN-01", "IN-01a")
    renamed = component.model_copy(
        update={
            "rule_component_id": "component-in-renamed",
            "expression": AtomicExpression(
                predicate=component.expression.predicate.model_copy(
                    update={"predicate_id": "predicate-age-renamed"}
                )
            ),
        }
    )
    current.proposed_rules = [
        rule.model_copy(update={"components": [renamed]})
        if rule.official_code == "IN-01"
        else rule
        for rule in current.proposed_rules
    ]
    # 同步组件草稿引用，保持来源绑定对齐（组件 ID 变化不产生差异）
    current.component_drafts = [
        item.model_copy(
            update={
                "proposed_component": item.proposed_component.model_copy(
                    update={"rule_component_id": "component-in-renamed"}
                )
            }
        )
        for item in current.component_drafts
    ]
    diff = compute_draft_diff(previous, current)
    rule_diff = _rule_diff(diff, "IN-01")
    assert rule_diff.added_component_refs == []
    assert rule_diff.removed_component_refs == []
    for field in CATEGORY_FIELDS:
        assert not getattr(rule_diff, field), f"{field} 不应因随机 ID 变化触发"


def test_rule_diffs_are_deterministic_and_sorted() -> None:
    """属性式：同一输入对输出完全相同；rule_diffs 按官方编号稳定排序。"""

    source_input, previous, source_spans = _fixture()
    current = copy.deepcopy(previous)
    component = _component(current, "EX-01", "EX-01a")
    current.proposed_rules = [
        rule.model_copy(
            update={
                "components": [
                    component.model_copy(
                        update={
                            "expression": AtomicExpression(
                                predicate=component.expression.children[0].predicate,
                                time_constraint=TimeConstraint(
                                    anchor_type=AnchorType.RANDOMIZATION_DATE,
                                    direction=TimeDirection.BEFORE,
                                    upper_bound_days=7,
                                ),
                            )
                        }
                    )
                    if comp.rule_component_id == component.rule_component_id
                    else comp
                    for comp in rule.components
                ]
            }
        )
        if rule.official_code == "EX-01"
        else rule
        for rule in current.proposed_rules
    ]
    first = compute_draft_diff(previous, current)
    second = compute_draft_diff(previous, current)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    codes = [item.official_code for item in first.rule_diffs]
    assert codes == sorted(codes)
    # JSON 往返无损
    round_trip = ProtocolDraftRevisionDiff.model_validate_json(
        json.dumps(first.model_dump(mode="json"), ensure_ascii=False)
    )
    assert round_trip == first


def test_gate_declared_diff_must_reproduce_rule_diffs() -> None:
    """门禁 diff_integrity：声明差异与结构重建一致才通过；篡改详情被拒绝。"""

    source_input, previous, source_spans = _fixture()
    current = copy.deepcopy(previous)
    current = current.model_copy(
        update={"draft_revision": 2, "previous_draft_id": previous.draft_id}
    )
    component = _component(current, "IN-01", "IN-01a")
    current.proposed_rules = [
        rule.model_copy(
            update={
                "components": [
                    component.model_copy(
                        update={
                            "expression": component.expression.model_copy(
                                update={
                                    "predicate": component.expression.predicate.model_copy(
                                        update={"value": 21}
                                    )
                                }
                            )
                        }
                    )
                    if comp.rule_component_id == component.rule_component_id
                    else comp
                    for comp in rule.components
                ]
            }
        )
        if rule.official_code == "IN-01"
        else rule
        for rule in current.proposed_rules
    ]
    actual = compute_draft_diff(previous, current)
    declared = ProtocolDraftDiffDeclaration(**actual.model_dump(mode="python"))
    gate = ProtocolDeconstructionGate()
    result = gate.evaluate(
        source_input,
        current,
        source_spans=source_spans,
        previous_draft=previous,
        declared_diff=declared,
    )
    diff_issues = [
        issue
        for check in result.checks
        if check.check_name == "diff_integrity"
        for issue in check.issues
    ]
    assert not any(
        issue.issue_code == "DECLARED_DIFF_NOT_REPRODUCIBLE"
        for issue in diff_issues
    )

    # 篡改声明详情（删除逻辑类别条目）必须被拒绝
    tampered_payload = dict(actual.model_dump(mode="python"))
    rule_diff = tampered_payload["rule_diffs"][1]
    rule_diff["logic_changes"] = []
    tampered = ProtocolDraftDiffDeclaration(**tampered_payload)
    result = gate.evaluate(
        source_input,
        current,
        source_spans=source_spans,
        previous_draft=previous,
        declared_diff=tampered,
    )
    assert any(
        issue.issue_code == "DECLARED_DIFF_NOT_REPRODUCIBLE"
        for check in result.checks
        if check.check_name == "diff_integrity"
        for issue in check.issues
    )