"""Generic regression for typographic quote restoration (slice61au worker_02).

Covers:
- 弯/直单双引号唯一匹配可还原（‘ ’ “ ” ↔ ' "）
- 多重匹配仍失败
- 非引号差异仍失败（词字、标点、空白）
- 数字/单位/比较符差异仍失败
- 跨来源差异仍失败
- 原始模型文本哈希与审计提示保留
- D001 心电图真实重放（body.p790 Fridericia's → Fridericia’s）
"""
from __future__ import annotations

import hashlib
import json

import pytest

from tests.v2.protocols.test_slice58c_control_deconstructor import _evaluation, _evidence_policy

from app.agents.protocol_control_deconstructor import (
    CONTROL_AGENT_WIRE_VERSION,
    ProtocolControlAgentResponse,
    ProtocolControlAgentRunner,
    ProtocolControlAgentWire,
    ProtocolControlAgentWireCandidate,
    ProtocolControlAgentWireDisposition,
    ProtocolControlAgentWireEvidence,
    ProtocolControlAgentWireObligationAtom,
    ProtocolControlAgentWireObligationDnf,
    ProtocolControlAgentWireObligationGroup,
    ProtocolControlAgentWireValidationError,
    _control_quote_normalize,
    _recover_control_excerpt,
    build_protocol_control_repair_prompt,
    hydrate_protocol_control_agent_output,
)
from app.agents.protocol_deconstructor import (
    _quote_normalize,
    _recover_exact_excerpt,
)
from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.protocol_controls import (
    ControlObligationKind,
    KnownWorkflowStageTarget,
    ProtocolStructureUnit,
    ReviewNodeRole,
    ReviewStage,
    StructureUnitDispositionKind,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit(unit_id: str, order: int, span_id: str, excerpt: str) -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=f"generic.body.p{order}",
        member_source_refs=[f"generic.body.p{order}"],
        source_span_ids=[span_id],
        unit_kind="paragraph",
        heading_path=["其他方案控制"],
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.SHARED],
        excerpt=excerpt,
    )


def _control_batch(
    owned_units: list[ProtocolStructureUnit],
    *,
    context_units: list[ProtocolStructureUnit] | None = None,
) -> "ProtocolControlDispositionBatch":
    from app.domain.contracts.protocol_controls import ProtocolControlDispositionBatch

    owned_ids = [u.structure_unit_id for u in owned_units]
    owned_spans = sorted({s for u in owned_units for s in u.source_span_ids})
    ctx = context_units or []
    return ProtocolControlDispositionBatch(
        batch_id="pcb-61au-01",
        coverage_manifest_id="manifest:61au-01",
        protocol_version_id="protocol:61au-01",
        study_phase=StudyPhase.PHASE_II,
        batch_number=1,
        batch_total=1,
        owned_units=owned_units,
        context_units=ctx,
        owned_structure_unit_ids=sorted(owned_ids),
        context_structure_unit_ids=sorted([u.structure_unit_id for u in ctx]),
        owned_source_span_ids=owned_spans,
        context_source_span_ids=sorted({s for u in ctx for s in u.source_span_ids}),
        known_workflow_stage_targets=[
            KnownWorkflowStageTarget(
                workflow_stage_id="flow-screening",
                display_name="筛选期",
                review_stage=ReviewStage.SCREENING,
            )
        ],
    )


def _wire_candidate_with_excerpt(
    excerpt: str,
    span_id: str = "span:ecg-01",
    unit_id: str = "su-ecg-01",
) -> ProtocolControlAgentWireCandidate:
    return ProtocolControlAgentWireCandidate(
        title="控制候选",
        repeat_trigger_conditions=[],
        applicable_population="拟入组受试者",
        applicability_expression=None,
        trigger_expression=None,
        obligation_expression=ProtocolControlAgentWireObligationDnf(
            groups=[
                ProtocolControlAgentWireObligationGroup(
                    atoms=[
                        ProtocolControlAgentWireObligationAtom(
                            kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                            statement="占位陈述",
                            evaluation=_evaluation("占位陈述", span_id, excerpt),
                            time_constraint=None,
                            prospective_period=None,
                            source_span_ids=[span_id],
                            source_excerpts=[excerpt],
                            requires_professional_judgment=False,
                        )
                    ]
                )
            ]
        ),
        exception_expression=None,
        review_node_bindings=[
            {
                "workflow_stage_id": "flow-screening",
                "review_stage": ReviewStage.SCREENING,
                "role": ReviewNodeRole.DECIDE_AT_NODE,
                "guidance": None,
            }
        ],
        minimum_evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="ecg",
                description="核对",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["原始资料"],
                workflow_stage_ids=["flow-screening"],
                source_policy=_evidence_policy(span_id, excerpt),
                atom_refs=[{"layer": "obligation", "group_index": 0, "atom_index": 0}],
            )
        ],
        source_structure_unit_ids=[unit_id],
        source_span_ids=[span_id],
        cross_source_relations=[],
    )


def _wire_for_batch(batch, candidate: ProtocolControlAgentWireCandidate) -> ProtocolControlAgentWire:
    return ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[
            ProtocolControlAgentWireDisposition(
                structure_unit_id=sid,
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes="增量",
            )
            for sid in batch.owned_structure_unit_ids
        ],
        candidate_drafts=[candidate],
    )


# ---------------------------------------------------------------------------
# 1. Quote normalization is minimal (only 4 glyphs)
# ---------------------------------------------------------------------------

def test_quote_normalize_only_maps_four_glyphs() -> None:
    assert _quote_normalize("‘") == "'"
    assert _quote_normalize("’") == "'"
    assert _quote_normalize("“") == '"'
    assert _quote_normalize("”") == '"'
    assert _control_quote_normalize("‘") == "'"
    assert _control_quote_normalize("’") == "'"
    assert _control_quote_normalize("“") == '"'
    assert _control_quote_normalize("”") == '"'
    unchanged = "10 min 10分钟 ≥ ≤ > < =  ，。；： （） a  b 10.5"
    assert _quote_normalize(unchanged) == unchanged
    assert _control_quote_normalize(unchanged) == unchanged
    assert _quote_normalize(_quote_normalize("Fridericia’s “你好”")) == "Fridericia's \"你好\""


# ---------------------------------------------------------------------------
# 2. Unique match restores for all 4 quote variants (both directions)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("source", "excerpt"),
    [
        ("并应用Fridericia’s公式", "并应用Fridericia's公式"),
        ("他说‘你好’", "他说'你好'"),
        ("他说“你好”", '他说"你好"'),
        ("他说“你好”且‘再见’", '他说"你好"且\'再见\''),
        ("并应用Fridericia's公式", "并应用Fridericia’s公式"),
        ("他说'你好'", "他说‘你好’"),
        ('他说"你好"', "他说“你好”"),
    ],
)
def test_recover_exact_excerpt_unique_quote_restores(source: str, excerpt: str) -> None:
    assert _recover_exact_excerpt(excerpt, [source]) == source
    assert _recover_control_excerpt(excerpt, [source]) == source


def test_recover_exact_excerpt_double_quote_unique() -> None:
    source = "他说“你好”"
    excerpt = '他说"你好"'
    assert _recover_exact_excerpt(excerpt, [source]) == source
    assert _recover_control_excerpt(excerpt, [source]) == source
    assert _recover_exact_excerpt(source, [excerpt]) == excerpt


def test_hydrate_control_unique_quote_restores_and_preserves_raw_hash() -> None:
    curved = "12导联心电图检查前参与者至少静息10 min。记录12导联心电图诊断结果、心率、PR间期、RR间期、QRS、QT间期，并应用Fridericia’s公式计算心率校正计算QTcF。"
    unit = _unit("su-ecg-01", 10, "span:ecg-01", curved)
    batch = _control_batch([unit])
    straight_excerpt = "并应用Fridericia's公式计算心率校正计算QTcF。"
    candidate = _wire_candidate_with_excerpt(straight_excerpt, span_id="span:ecg-01", unit_id="su-ecg-01")
    wire = _wire_for_batch(batch, candidate)
    raw_text = wire.model_dump_json()
    raw_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    # Raw JSON must contain straight quote before hydration
    assert "Fridericia's" in raw_text
    assert "Fridericia’s" not in raw_text
    hydrated = hydrate_protocol_control_agent_output(wire, batch)
    restored = hydrated.candidates[0].semantics.obligation_expression.groups[0].atoms[0].source_excerpts[0]
    assert restored == "并应用Fridericia’s公式计算心率校正计算QTcF。"
    assert "’" in restored
    assert "'" not in restored
    # Validation restores only its private copy; caller-owned wire remains raw.
    preserved_json = wire.model_dump_json()
    assert "Fridericia's" in preserved_json
    assert "Fridericia’s" not in preserved_json
    assert hashlib.sha256(raw_text.encode("utf-8")).hexdigest() == raw_hash
    # double quote
    curved2 = "他说“你好”。"
    unit2 = _unit("su-ecg-01", 10, "span:ecg-01", curved2)
    batch2 = _control_batch([unit2])
    straight2 = '他说"你好"。'
    cand2 = _wire_candidate_with_excerpt(straight2, span_id="span:ecg-01", unit_id="su-ecg-01")
    wire2 = _wire_for_batch(batch2, cand2)
    hydrated2 = hydrate_protocol_control_agent_output(wire2, batch2)
    assert hydrated2.candidates[0].semantics.obligation_expression.groups[0].atoms[0].source_excerpts[0] == curved2
    repair_prompt = build_protocol_control_repair_prompt(
        batch,
        problem="FABRICATED_EXCERPT: obligation 原子 0 的摘录不是来源 span:ecg-01 的连续原文",
        structure_unit_ids=["su-ecg-01"],
    )
    assert "Fridericia’s" in repair_prompt
    assert "标点、引号和空格均保持原样" in repair_prompt
    assert "授权结构单元原文与来源定位" in repair_prompt


# ---------------------------------------------------------------------------
# 3. Multi-match (duplicate normalized occurrences) must still fail
# ---------------------------------------------------------------------------

def test_recover_exact_excerpt_multi_match_fails() -> None:
    source = "试验’s 数据 试验’s 数据"
    excerpt = "试验's"
    assert _recover_exact_excerpt(excerpt, [source]) == excerpt
    assert _recover_control_excerpt(excerpt, [source]) == excerpt
    s1 = "他说“你好”。"
    s2 = "他说“你好”。"
    assert _recover_exact_excerpt('他说"你好"。', [s1, s2]) == '他说"你好"。'
    # intra-source duplicate still fails
    dup_source = "“你好” “你好”"
    dup_unit = _unit("su-ecg-01", 1, "span:ecg-01", dup_source)
    dup_batch = _control_batch([dup_unit])
    dup_candidate = _wire_candidate_with_excerpt('"你好"', span_id="span:ecg-01", unit_id="su-ecg-01")
    dup_wire = _wire_for_batch(dup_batch, dup_candidate)
    with pytest.raises(ProtocolControlAgentWireValidationError, match="FABRICATED_EXCERPT"):
        hydrate_protocol_control_agent_output(dup_wire, dup_batch)


def test_recover_exact_excerpt_multi_match_intra_source_duplicate_still_fails() -> None:
    source = "“a” and “a”"
    excerpt = '"a"'
    assert _recover_exact_excerpt(excerpt, [source]) == excerpt
    assert excerpt not in source


# ---------------------------------------------------------------------------
# 4. Non-quote differences still fail
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("source", "excerpt"),
    [
        ("并应用Fridericia’s公式", "并应用FridericiaX公式"),
        ("10 min。", "10 min."),
        ("（X）", "(X)"),
        ("10，20", "10,20"),
        ("10；20", "10;20"),
        ("a b", "a  b"),
        ("a\tb", "a b"),
        ("a\nb", "a b"),
    ],
)
def test_recover_exact_excerpt_non_quote_diff_still_fails(source: str, excerpt: str) -> None:
    assert _recover_exact_excerpt(excerpt, [source]) == excerpt
    assert _recover_control_excerpt(excerpt, [source]) == excerpt
    unit = _unit("su-ecg-01", 1, "span:ecg-01", source)
    batch = _control_batch([unit])
    cand = _wire_candidate_with_excerpt(excerpt, span_id="span:ecg-01", unit_id="su-ecg-01")
    wire = _wire_for_batch(batch, cand)
    with pytest.raises(ProtocolControlAgentWireValidationError, match="FABRICATED_EXCERPT"):
        hydrate_protocol_control_agent_output(wire, batch)


# ---------------------------------------------------------------------------
# 5. Digit / unit / comparator differences still fail
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("source", "excerpt", "reason"),
    [
        ("10 min", "11 min", "digit"),
        ("10 min", "10分钟", "unit"),
        ("≥18岁", ">18岁", "comparator ≥ vs >"),
        ("≤10 min", "<10 min", "comparator ≤ vs <"),
        ("=10", "≠10", "comparator = vs ≠"),
        ("20 mg", "20mg", "unit spacing is not quote – should fail if exact missing"),
        ("10 min。", "10  min。", "whitespace inside number-unit is not quote"),
    ],
)
def test_digit_unit_comparator_still_fail(source: str, excerpt: str, reason: str) -> None:
    assert _recover_exact_excerpt(excerpt, [source]) == excerpt, reason
    assert _recover_control_excerpt(excerpt, [source]) == excerpt, reason
    unit = _unit("su-ecg-01", 1, "span:ecg-01", source)
    batch = _control_batch([unit])
    cand = _wire_candidate_with_excerpt(excerpt, span_id="span:ecg-01", unit_id="su-ecg-01")
    wire = _wire_for_batch(batch, cand)
    with pytest.raises(ProtocolControlAgentWireValidationError, match="FABRICATED_EXCERPT"):
        hydrate_protocol_control_agent_output(wire, batch)


# ---------------------------------------------------------------------------
# 6. Cross-source (span mismatch) still fails even with quote normalization
# ---------------------------------------------------------------------------

def test_cross_source_quote_diff_still_fails_when_span_mismatch() -> None:
    u1 = _unit("su-01", 1, "span:01", "他说“你好”。")
    u2 = _unit("su-02", 2, "span:02", "他说‘再见’。")
    from app.domain.contracts.protocol_controls import ProtocolControlDispositionBatch

    batch = ProtocolControlDispositionBatch(
        batch_id="pcb-61au-01",
        coverage_manifest_id="manifest:61au-01",
        protocol_version_id="protocol:61au-01",
        study_phase=StudyPhase.PHASE_II,
        batch_number=1,
        batch_total=1,
        owned_units=[u1, u2],
        context_units=[],
        owned_structure_unit_ids=["su-01", "su-02"],
        context_structure_unit_ids=[],
        owned_source_span_ids=["span:01", "span:02"],
        context_source_span_ids=[],
        known_workflow_stage_targets=[
            KnownWorkflowStageTarget(
                workflow_stage_id="flow-screening",
                display_name="筛选期",
                review_stage=ReviewStage.SCREENING,
            )
        ],
    )
    candidate = ProtocolControlAgentWireCandidate(
        title="跨来源",
        repeat_trigger_conditions=[],
        applicable_population="拟入组受试者",
        applicability_expression=None,
        trigger_expression=None,
        obligation_expression=ProtocolControlAgentWireObligationDnf(
            groups=[
                ProtocolControlAgentWireObligationGroup(
                    atoms=[
                        ProtocolControlAgentWireObligationAtom(
                            kind=ControlObligationKind.COMPLETE_OR_VERIFY,
                            statement="占位",
                            evaluation=_evaluation("占位", "span:01", "他说'再见'。"),
                            time_constraint=None,
                            prospective_period=None,
                            source_span_ids=["span:01"],
                            source_excerpts=["他说'再见'。"],
                            requires_professional_judgment=False,
                        )
                    ]
                )
            ]
        ),
        exception_expression=None,
        review_node_bindings=[
            {
                "workflow_stage_id": "flow-screening",
                "review_stage": ReviewStage.SCREENING,
                "role": ReviewNodeRole.DECIDE_AT_NODE,
                "guidance": None,
            }
        ],
        minimum_evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="ecg",
                description="核对",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["原始资料"],
                workflow_stage_ids=["flow-screening"],
                source_policy=_evidence_policy("span:01", "他说'再见'。"),
                atom_refs=[{"layer": "obligation", "group_index": 0, "atom_index": 0}],
            )
        ],
        source_structure_unit_ids=["su-01"],
        source_span_ids=["span:01"],
        cross_source_relations=[],
    )
    wire = _wire_for_batch(batch, candidate)
    with pytest.raises(ProtocolControlAgentWireValidationError, match="FABRICATED_EXCERPT"):
        hydrate_protocol_control_agent_output(wire, batch)
    assert _recover_exact_excerpt("他说'再见'。", ["他说“你好”。"]) == "他说'再见'。"
    assert _recover_control_excerpt("他说'再见'。", ["他说“你好”。"]) == "他说'再见'。"


# ---------------------------------------------------------------------------
# 7. Raw model hash and audit prompt retention via runner
# ---------------------------------------------------------------------------

def test_quote_restoration_rejects_candidates_that_become_identical():
    batch = _control_batch([_unit("su-ecg-01", 1, "span:ecg-01", "记录‘甲’结果")])
    straight = _wire_candidate_with_excerpt("记录'甲'结果")
    curved = _wire_candidate_with_excerpt("记录‘甲’结果")
    wire = _wire_for_batch(batch, straight).model_copy(update={"candidate_drafts": [straight, curved]})
    with pytest.raises(ProtocolControlAgentWireValidationError, match="DUPLICATE_CANDIDATE"):
        hydrate_protocol_control_agent_output(wire, batch)


def test_atom_time_constraint_half_life_sources_are_restored_with_the_atom():
    from app.domain.contracts.control_evaluation_spec import ControlAtomEvaluationSpec
    from app.domain.contracts.rules import TimeConstraint

    raw = "'甲'的半衰期为2天"
    source = "‘甲’的半衰期为2天"
    batch = _control_batch([_unit("su-ecg-01", 1, "span:ecg-01", source)])
    candidate = _wire_candidate_with_excerpt(raw)
    atom = candidate.obligation_expression.groups[0].atoms[0]
    atom.kind = ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE
    atom.evaluation = ControlAtomEvaluationSpec.model_validate({
        **_evaluation("检查用药时间", "span:ecg-01", raw),
        "time_purpose": "event_membership", "time_operand_attribute": "date_range",
    })
    atom.time_constraint = TimeConstraint(
        anchor_type="first_dose_date", direction="before", half_life_multiplier=5,
        half_life_evidence={"value": 2, "unit": "day", "source_span_id": "span:ecg-01",
                            "source_excerpt": raw, "applies_to_quote": "'甲'", "duration_quote": "2天"},
    )
    output = hydrate_protocol_control_agent_output(_wire_for_batch(batch, candidate), batch)
    restored = output.candidates[0].semantics.obligation_expression.groups[0].atoms[0]
    assert restored.source_excerpts == [source]
    assert restored.time_constraint.half_life_evidence.source_excerpt == source
    assert restored.time_constraint.half_life_evidence.applies_to_quote == "‘甲’"
    assert restored.time_constraint.half_life_multiplier == 5
    assert atom.source_excerpts == [raw]


def test_runner_preserves_raw_hash_and_audit_prompt_on_quote_restoration() -> None:
    curved = "12导联心电图检查前参与者至少静息10 min。记录12导联心电图诊断结果、心率、PR间期、RR间期、QRS、QT间期，并应用Fridericia’s公式计算心率校正计算QTcF。"
    unit = _unit("su-ecg-01", 10, "span:ecg-01", curved)
    batch = _control_batch([unit])
    straight_excerpt = "并应用Fridericia's公式计算心率校正计算QTcF。"
    candidate_straight = _wire_candidate_with_excerpt(straight_excerpt, span_id="span:ecg-01", unit_id="su-ecg-01")
    wire_straight = _wire_for_batch(batch, candidate_straight)
    raw_text = wire_straight.model_dump_json()
    raw_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    hydrated = hydrate_protocol_control_agent_output(wire_straight, batch)
    assert hydrated.candidates[0].semantics.obligation_expression.groups[0].atoms[0].source_excerpts[0] == "并应用Fridericia’s公式计算心率校正计算QTcF。"

    class FakeTransport:
        def __init__(self, text: str):
            self.text = text
            self.prompts: list[str] = []

        def start(self, *, prompt: str):
            self.prompts.append(prompt)
            return ProtocolControlAgentResponse(session_id="sess-61au", text=self.text)

        def continue_session(self, *, session_id: str, prompt: str):
            self.prompts.append(prompt)
            return ProtocolControlAgentResponse(session_id=session_id, text=self.text)

    transport = FakeTransport(raw_text)
    runner = ProtocolControlAgentRunner()
    result = runner.run(batch, transport)
    assert result.status == "已解析"
    assert len(result.attempts) == 1
    assert result.attempts[0].raw_output_sha256 == raw_hash
    final_excerpt = result.final_output.candidates[0].semantics.obligation_expression.groups[0].atoms[0].source_excerpts[0]
    assert final_excerpt == "并应用Fridericia’s公式计算心率校正计算QTcF。"
    assert "’" in final_excerpt
    repair_prompt = build_protocol_control_repair_prompt(
        batch,
        problem="FABRICATED_EXCERPT: obligation 原子 0 的摘录不是来源 span:ecg-01 的连续原文",
        structure_unit_ids=["su-ecg-01"],
    )
    assert "Fridericia’s" in repair_prompt
    assert "授权结构单元原文与来源定位" in repair_prompt
    assert "标点、引号和空格均保持原样" in repair_prompt


# ---------------------------------------------------------------------------
# 8. Protocol deconstructor whitespace and punctuation not restored
# ---------------------------------------------------------------------------

def test_protocol_deconstructor_whitespace_and_punctuation_not_restored() -> None:
    assert _recover_exact_excerpt("a  b", ["a b"]) == "a  b"
    assert _recover_exact_excerpt("a,b", ["a，b"]) == "a,b"
    assert _recover_exact_excerpt("10,000", ["10，000"]) == "10,000"
    assert _recover_exact_excerpt("（X）", ["(X)"]) == "（X）"


# ---------------------------------------------------------------------------
# 9. D001 真实重放：artifacts 中的 body.p790 弯引号在真实 batch 上可还原
# ---------------------------------------------------------------------------

def test_d001_historical_quotes_restore_but_old_wire_is_not_current_acceptance() -> None:
    import pathlib

    batch_path = pathlib.Path("artifacts/phase5-slice61as-d001-ecg-screening-20260829/execution/batch.json")
    raw_path = pathlib.Path("artifacts/phase5-slice61as-d001-ecg-screening-20260829/execution/raw-responses.json")
    if not batch_path.exists() or not raw_path.exists():
        pytest.skip("D001 artifacts not present in worktree")
    batch_data = json.loads(batch_path.read_text(encoding="utf-8"))
    raw_responses = json.loads(raw_path.read_text(encoding="utf-8"))
    p790 = None
    for u in batch_data["owned_units"]:
        if "body.p790" in u.get("source_span_ids", []):
            p790 = u
            break
    assert p790 is not None
    assert "Fridericia’s" in p790["excerpt"]
    assert "’" in p790["excerpt"]
    straight = None
    for r in raw_responses:
        if "Fridericia's" in r["text"]:
            straight = r
            break
    assert straight is not None
    straight_hash = straight["text_sha256"]
    assert hashlib.sha256(straight["text"].encode("utf-8")).hexdigest() == straight_hash
    source_text = p790["excerpt"]
    assert _recover_control_excerpt("并应用Fridericia's公式计算心率校正计算QTcF", [source_text]) == "并应用Fridericia’s公式计算心率校正计算QTcF"
    assert _recover_control_excerpt("并应用Fridericia's公式计算心率校正计算QTcF。", [source_text]) == "并应用Fridericia’s公式计算心率校正计算QTcF。"
    from app.domain.contracts.protocol_controls import ProtocolControlDispositionBatch

    real_batch = ProtocolControlDispositionBatch.model_validate(batch_data)
    assert json.loads(straight["text"])["wire_version"] != CONTROL_AGENT_WIRE_VERSION
    with pytest.raises(ProtocolControlAgentWireValidationError, match="WIRE_SCHEMA_INVALID"):
        hydrate_protocol_control_agent_output(straight["text"], real_batch)

    class FakeTransport:
        def __init__(self, text: str):
            self.text = text

        def start(self, *, prompt: str):
            return ProtocolControlAgentResponse(session_id=straight["session_id"], text=self.text)

        def continue_session(self, *, session_id: str, prompt: str):
            return ProtocolControlAgentResponse(session_id=session_id, text=self.text)

    transport = FakeTransport(straight["text"])
    runner = ProtocolControlAgentRunner()
    result = runner.run(real_batch, transport)
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.attempts[0].raw_output_sha256 == straight_hash
