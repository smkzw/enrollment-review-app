"""Deterministic contract tests for the full-protocol control matrix."""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import AnchorType, PhaseScope, ReviewStage, StudyPhase
from app.domain.contracts.protocol_control_matrix import (
    CONTROL_MATRIX_CONTRACT_VERSION,
    MatrixConditionAtom,
    MatrixCrossSourceRelation,
    MatrixDnf,
    MatrixDnfGroup,
    MatrixEvidence,
    MatrixObligation,
    MatrixPhaseDisposition,
    MatrixReviewNode,
    MatrixSourceAnchor,
    MatrixTimeAnchor,
    ProtocolControlMatrix,
    ProtocolControlMatrixRow,
    ProtocolControlMatrixSourceKind,
    build_protocol_control_matrix_json,
    render_protocol_control_matrix_markdown,
    stable_protocol_control_matrix_anchor_id,
    stable_protocol_control_matrix_row_id,
    stable_protocol_control_matrix_trigger_branch_id,
    validate_protocol_control_matrix_serializations,
)
from app.domain.contracts.protocol_controls import (
    ControlObligationAtom,
    ControlObligationKind,
    ControlObligationModality,
    ControlTemporalScopeKind,
    CrossSourceRelationKind,
    ControlMinimumEvidence,
    ProtocolReviewControl,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    ReviewNodeBinding,
    ReviewNodeRole,
    StructureUnitDisposition,
    StructureUnitDispositionKind,
)
from app.domain.contracts.rules import TimeConstraint, TimeDirection
from app.protocols.protocol_control_matrix import (
    CONTROL_MATRIX_VALIDATOR_VERSION,
    check_protocol_control_matrix,
    validate_protocol_control_matrix,
)


_SHA = "a" * 64


def _unit(unit_id: str, span_id: str, text: str, order: int) -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=f"body.p{order}",
        member_source_refs=[f"body.p{order}"],
        source_span_ids=[span_id],
        unit_kind="paragraph",
        heading_path=["筛选期", "研究控制"],
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.PHASE_II],
        excerpt=text,
    )


def _manifest(
    *,
    mixed: bool = False,
    procedure_candidate_id: str | None = None,
) -> ProtocolSectionCoverageManifest:
    units = [
        _unit("su-official", "span-official", "必须符合入选条件", 0),
        _unit("su-procedure", "span-procedure", "筛选期完成检查", 1),
        _unit("su-other", "span-other", "首次给药前核对禁用治疗", 2),
    ]
    if mixed:
        units[0] = units[0].model_copy(update={"phase_scopes": [PhaseScope.MIXED]})
    procedure_disposition = StructureUnitDisposition(
        structure_unit_id="su-procedure",
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_procedure_catalog_item_id=(
            None if procedure_candidate_id is not None else "proc-01"
        ),
        linked_procedure_candidate_id=procedure_candidate_id,
    )
    return ProtocolSectionCoverageManifest(
        manifest_id="manifest:matrix",
        protocol_version_id="protocol:matrix",
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:matrix",
        units=units,
        dispositions=[
            StructureUnitDisposition(
                structure_unit_id="su-official",
                disposition=StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY,
                linked_official_code="IN-01",
            ),
            procedure_disposition,
            StructureUnitDisposition(
                structure_unit_id="su-other",
                disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
                linked_control_candidate_id="candidate-other",
            ),
        ],
        claims_full_coverage=True,
    )


def _anchor(
    row_id: str,
    unit_id: str,
    span_id: str,
    text: str,
    *,
    source_ordinal: int = 0,
) -> MatrixSourceAnchor:
    return MatrixSourceAnchor(
        source_anchor_id=stable_protocol_control_matrix_anchor_id(
            row_id, source_ordinal
        ),
        source_ordinal=source_ordinal,
        structure_unit_id=unit_id,
        source_ref={
            "su-official": "body.p0",
            "su-procedure": "body.p1",
            "su-other": "body.p2",
        }[unit_id],
        source_title_zh="研究控制",
        heading_path_zh=["筛选期", "研究控制"],
        source_span_ids=[span_id],
        verbatim_excerpt=text,
    )


def _row(
    row_id: str,
    source_kind: ProtocolControlMatrixSourceKind,
    *,
    unit_id: str,
    span_id: str,
    excerpt: str,
    ordinal: int,
    target_row_id: str | None = None,
    candidate_id: str | None = None,
    title: str = "控制短标题",
    official_code: str = "IN-01",
) -> ProtocolControlMatrixRow:
    if source_kind == ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY:
        source_identity = official_code
        official_parent_code = official_code
        official_child_code = None
        procedure_id = None
        protocol_control_id = None
    elif source_kind == ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE:
        source_identity = candidate_id or "proc-01"
        official_parent_code = None
        official_child_code = None
        procedure_id = None if candidate_id else "proc-01"
        protocol_control_id = None
    else:
        source_identity = candidate_id or "pctrl-other"
        official_parent_code = None
        official_child_code = None
        procedure_id = None
        protocol_control_id = None if candidate_id else "pctrl-other"
    actual_row_id = stable_protocol_control_matrix_row_id(
        source_kind, source_identity, official_child_code
    )
    anchor = _anchor(actual_row_id, unit_id, span_id, excerpt)
    obligation_id = f"{actual_row_id}:obligation"
    relation = []
    if target_row_id is not None:
        relation = [
            # This source-backed relation is intentionally represented in the
            # matrix layer, not used to mutate the formal control catalog.
            MatrixCrossSourceRelation(
                relation_id=f"{row_id}:relation",
                kind=CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT,
                target_row_id=target_row_id,
                source_anchor_ids=[anchor.source_anchor_id],
            )
        ]
    kwargs: dict[str, object] = {
        "matrix_row_id": actual_row_id,
        "display_ordinal": ordinal,
        "source_kind": source_kind,
        "title_zh": title,
        "applicable_population_zh": "拟入组受试者",
        "required_action_zh": "完成并核对方案要求",
        "attainment_criteria_zh": "达到方案规定状态",
        "prohibition_zh": "不得发生未允许事件",
        "phase_disposition": MatrixPhaseDisposition.SELECTED_PHASE_APPLICABLE,
        "source_anchors": [anchor],
        "obligations": [
            MatrixObligation(
                obligation_id=obligation_id,
                kind=ControlObligationKind.MUST_RECORD,
                statement_zh="记录核对结果",
                source_anchor_ids=[anchor.source_anchor_id],
            )
        ],
        "obligation_expression": MatrixDnf(
            groups=[MatrixDnfGroup(atom_ids=[obligation_id])]
        ),
        "review_nodes": [
            MatrixReviewNode(
                workflow_stage_id=f"stage:{row_id}",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.DECIDE_AT_NODE,
                stage_ordinal=1,
                node_label_zh="筛选期",
                source_anchor_ids=[anchor.source_anchor_id],
            )
        ],
        "minimum_evidence": [
            MatrixEvidence(
                evidence_id=f"{row_id}:evidence",
                fact_type_zh="核对记录",
                description_zh="原始资料或筛选记录",
                due_workflow_stage_id=f"stage:{row_id}",
                required_source_types=["原始资料"],
                source_anchor_ids=[anchor.source_anchor_id],
            )
        ],
        "cross_source_relations": relation,
    }
    if source_kind == ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY:
        kwargs["official_parent_code"] = official_parent_code
    elif source_kind == ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE:
        if procedure_id is not None:
            kwargs["required_procedure_catalog_item_id"] = procedure_id
    else:
        if protocol_control_id is not None:
            kwargs["protocol_control_id"] = protocol_control_id
    if candidate_id is not None:
        kwargs["source_candidate_id"] = candidate_id
    return ProtocolControlMatrixRow(**kwargs)


def _trigger_exception_row(
    *,
    exception_scopes: list[list[str]],
    source_text: str = "首次给药前核对禁用治疗",
    use_not: bool = False,
) -> ProtocolControlMatrixRow:
    row = _row(
        "row-trigger-exception",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt=source_text,
        ordinal=1,
    )
    anchor_id = row.source_anchors[0].source_anchor_id
    branch_a = stable_protocol_control_matrix_trigger_branch_id(row.matrix_row_id, 0)
    branch_b = stable_protocol_control_matrix_trigger_branch_id(row.matrix_row_id, 1)
    atoms = [
        MatrixConditionAtom(
            atom_id="trigger-a",
            statement_zh="存在触发分支甲",
            source_anchor_ids=[anchor_id],
        ),
        MatrixConditionAtom(
            atom_id="trigger-b",
            statement_zh="存在触发分支乙",
            source_anchor_ids=[anchor_id],
        ),
    ]
    if use_not:
        atoms.insert(
            2,
            MatrixConditionAtom(
                atom_id="trigger-c",
                statement_zh="存在触发排除条件丙",
                source_anchor_ids=[anchor_id],
            ),
        )
    exception_names = [
        f"exception-{chr(ord('a') + index)}"
        for index in range(max(2 if use_not else 1, len(exception_scopes)))
    ]
    atoms.extend(
        MatrixConditionAtom(
            atom_id=atom_id,
            statement_zh=f"完成例外路径{chr(ord('甲') + index)}",
            source_anchor_ids=[anchor_id],
        )
        for index, atom_id in enumerate(exception_names)
    )
    trigger_groups = [
        MatrixDnfGroup(
            atom_ids=["trigger-a"],
            negated_atom_ids=["trigger-c"] if use_not else [],
            trigger_branch_id=branch_a,
            logic_basis_zh=(
                "来源明确要求甲且不满足丙，或与另一触发分支并列"
                if use_not
                else "来源明确为甲或另一触发分支并列"
            ),
            source_anchor_ids=[anchor_id],
        ),
        MatrixDnfGroup(
            atom_ids=["trigger-b"],
            trigger_branch_id=branch_b,
            logic_basis_zh="来源明确为甲或乙",
            source_anchor_ids=[anchor_id],
        ),
    ]
    exception_groups = [
        MatrixDnfGroup(
            atom_ids=[exception_names[index]],
            negated_atom_ids=["exception-b"] if use_not else [],
            waives_trigger_branch_ids=scope,
            logic_basis_zh=(
                "来源明确要求例外甲且不满足例外乙"
                if use_not
                else ("来源明确为例外甲或例外乙" if len(exception_scopes) > 1 else None)
            ),
            source_anchor_ids=[anchor_id],
        )
        for index, scope in enumerate(exception_scopes)
    ]
    payload = row.model_dump(mode="python")
    payload["condition_atoms"] = atoms
    payload["trigger_expression"] = MatrixDnf(groups=trigger_groups)
    payload["exception_expression"] = MatrixDnf(groups=exception_groups)
    return ProtocolControlMatrixRow.model_validate(payload)


def _other_control() -> ProtocolReviewControl:
    return ProtocolReviewControl(
        protocol_control_id="pctrl-other",
        display_ordinal=1,
        protocol_version_id="protocol:matrix",
        study_phase=StudyPhase.PHASE_II,
        title="已有其他章节控制",
        applicable_population="拟入组受试者",
        obligations=[
            ControlObligationAtom(
                obligation_id="legacy-obligation",
                kind=ControlObligationKind.MUST_RECORD,
                statement="记录核对结果",
            )
        ],
        review_node_bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:other",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.DECIDE_AT_NODE,
            )
        ],
        minimum_evidence=[
            ControlMinimumEvidence(
                evidence_key="evidence-other",
                fact_type="核对记录",
                description="原始资料",
                due_stage=ReviewStage.SCREENING,
            )
        ],
        source_span_ids=["span-other"],
        source_structure_unit_ids=["su-other"],
    )


def _matrix() -> ProtocolControlMatrix:
    rows = [
        _row(
            "row-official",
            ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY,
            unit_id="su-official",
            span_id="span-official",
            excerpt="必须符合入选条件",
            ordinal=1,
        ),
        _row(
            "row-procedure",
            ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE,
            unit_id="su-procedure",
            span_id="span-procedure",
            excerpt="筛选期完成检查",
            ordinal=2,
        ),
        _row(
            "row-other",
            ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
            unit_id="su-other",
            span_id="span-other",
            excerpt="首次给药前核对禁用治疗",
            ordinal=3,
            target_row_id=stable_protocol_control_matrix_row_id(
                ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY,
                "IN-01",
                None,
            ),
        ),
    ]
    return ProtocolControlMatrix(
        matrix_id="matrix:phase-ii",
        protocol_version_id="protocol:matrix",
        protocol_document_sha256=_SHA,
        selected_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:matrix",
        coverage_manifest_id="manifest:matrix",
        title_zh="全方案控制对照矩阵",
        rows=rows,
    )


def test_matrix_validates_three_source_families_and_existing_control_identity() -> None:
    matrix = _matrix()
    accepted = validate_protocol_control_matrix(
        matrix,
        _manifest(),
        official_parent_codes=["IN-01"],
        required_procedure_ids=["proc-01"],
        protocol_controls=[_other_control()],
        require_all_source_kinds=True,
    )
    assert accepted is matrix
    report = check_protocol_control_matrix(matrix, _manifest())
    assert report.accepted is True
    assert [row.source_identity for row in matrix.rows] == [
        "IN-01",
        "proc-01",
        "pctrl-other",
    ]


def test_matrix_json_and_markdown_keep_the_same_ordered_identities() -> None:
    matrix = _matrix()
    json_payload = build_protocol_control_matrix_json(matrix)
    markdown = render_protocol_control_matrix_markdown(matrix)
    assert '"schema_version":"phase5/control-matrix/v5"' in json_payload
    assert matrix.rows[0].review_nodes[0].source_anchor_ids[0] in json_payload
    assert validate_protocol_control_matrix_serializations(
        matrix, json_payload, markdown
    ) is matrix
    other_row_id = matrix.rows[2].matrix_row_id
    broken = markdown.replace(
        f'"row_id":"{other_row_id}"', '"row_id":"row-unknown"'
    )
    with pytest.raises(ValueError, match="MARKDOWN_ROW_IDENTITY_MISMATCH"):
        validate_protocol_control_matrix_serializations(matrix, json_payload, broken)


def test_matrix_v4_payload_is_not_accepted_as_v5() -> None:
    payload = _matrix().model_dump(mode="python")
    payload["schema_version"] = "phase5/control-matrix/v4"
    with pytest.raises(ValidationError, match="schema_version"):
        ProtocolControlMatrix.model_validate(payload)
    assert CONTROL_MATRIX_VALIDATOR_VERSION == "phase5/control-matrix-validator/v5"


def test_matrix_rejects_mixed_phase_and_unrecoverable_source_excerpt() -> None:
    matrix = _matrix()
    with pytest.raises(ValueError, match="PHASE_MIXED_REJECTED"):
        validate_protocol_control_matrix(matrix, _manifest(mixed=True))

    bad_payload = matrix.model_copy(deep=True)
    bad_payload.rows[0].source_anchors[0].verbatim_excerpt = "不存在于冻结单元"
    with pytest.raises(ValueError, match="VERBATIM_EXCERPT_NOT_FOUND"):
        validate_protocol_control_matrix(bad_payload, _manifest())


def test_matrix_rejects_missing_dnf_coverage_and_screening_anchor_guess() -> None:
    row = _row(
        "row-dnf",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前核对禁用治疗",
        ordinal=1,
    )
    with pytest.raises(ValidationError, match="义务原子必须在义务 DNF"):
        ProtocolControlMatrixRow.model_validate(
            {
                **row.model_dump(mode="python"),
                "obligation_expression": MatrixDnf(
                    groups=[MatrixDnfGroup(atom_ids=["unknown-obligation"])]
                ),
            }
        )

    with pytest.raises(ValidationError, match="首次给药时间窗不得用筛选日期替代"):
        ProtocolControlMatrixRow.model_validate(
            {
                **row.model_dump(mode="python"),
                "time_anchors": [
                    MatrixTimeAnchor(
                        time_constraint_id="time-1",
                        anchor_label_zh="首次给药前 4 周",
                        time_constraint=TimeConstraint(
                            anchor_type=AnchorType.SCREENING_DATE,
                            direction=TimeDirection.BEFORE,
                            lower_bound_days=28,
                        ),
                        source_anchor_ids=[row.source_anchors[0].source_anchor_id],
                    )
                ],
            }
        )


@pytest.mark.parametrize(
    "statement",
    [
        "A 且 B",
        "A 并且 B",
        "A 同时 B",
        "A 和 B",
        "A + B",
        "A 或 B",
        "A 或者 B",
        "A\nB",
        "A；B；C",
        "符合以下任一项：",
        "注：需要复核",
    ],
)
def test_matrix_atoms_reject_top_level_logic_lists_and_labels(statement: str) -> None:
    anchor_id = "pcm-src-test"
    with pytest.raises(ValidationError):
        MatrixConditionAtom(
            atom_id="condition-boundary",
            statement_zh=statement,
            source_anchor_ids=[anchor_id],
        )
    with pytest.raises(ValidationError):
        MatrixObligation(
            obligation_id="obligation-boundary",
            kind=ControlObligationKind.MUST_RECORD,
            statement_zh=statement,
            source_anchor_ids=[anchor_id],
        )


def test_matrix_atoms_ignore_logic_inside_paired_examples() -> None:
    anchor_id = "pcm-src-test"
    condition = MatrixConditionAtom(
        atom_id="condition-example",
        statement_zh="既往治疗（如 A 或 B）已完成",
        source_anchor_ids=[anchor_id],
    )
    obligation = MatrixObligation(
        obligation_id="obligation-example",
        kind=ControlObligationKind.MUST_RECORD,
        statement_zh="记录检查结果（A 且 B 可作为示例）",
        source_anchor_ids=[anchor_id],
    )
    assert condition.atom_id == "condition-example"
    assert obligation.obligation_id == "obligation-example"


def test_matrix_obligation_preserves_collection_modality_and_temporal_scope() -> None:
    obligation = MatrixObligation(
        obligation_id="obligation-history",
        kind=ControlObligationKind.MUST_RECORD,
        statement_zh="尽可能收集完整病程",
        source_anchor_ids=["pcm-src-test"],
        modality=ControlObligationModality.BEST_EFFORT,
        temporal_scope=ControlTemporalScopeKind.FULL_HISTORY,
    )
    assert obligation.modality == ControlObligationModality.BEST_EFFORT
    assert obligation.temporal_scope == ControlTemporalScopeKind.FULL_HISTORY


def test_matrix_obligation_rejects_collection_scope_strengthening() -> None:
    with pytest.raises(ValidationError, match="不得用于禁止"):
        MatrixObligation(
            obligation_id="obligation-invalid-modality",
            kind=ControlObligationKind.PROHIBIT_EVENT,
            statement_zh="不得发生事件",
            source_anchor_ids=["pcm-src-test"],
            modality=ControlObligationModality.BEST_EFFORT,
        )
    with pytest.raises(ValidationError, match="日历回顾范围必须关联"):
        MatrixObligation(
            obligation_id="obligation-invalid-window",
            kind=ControlObligationKind.MUST_RECORD,
            statement_zh="收集近两年病史",
            source_anchor_ids=["pcm-src-test"],
            temporal_scope=ControlTemporalScopeKind.CALENDAR_LOOKBACK,
        )


def test_matrix_markdown_uses_native_chinese_collection_labels() -> None:
    matrix = _matrix()
    row = matrix.rows[2]
    obligation = row.obligations[0].model_copy(
        update={
            "modality": ControlObligationModality.BEST_EFFORT,
            "temporal_scope": ControlTemporalScopeKind.FULL_HISTORY,
        }
    )
    rows = [*matrix.rows[:2], row.model_copy(update={"obligations": [obligation]})]
    markdown = render_protocol_control_matrix_markdown(
        matrix.model_copy(update={"rows": rows})
    )
    assert "完成强度=尽力完成" in markdown
    assert "资料范围=完整历程" in markdown


def test_matrix_rejects_source_logic_without_structured_dnf() -> None:
    row = _row(
        "row-source-logic",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前核对禁用治疗",
        ordinal=1,
    )
    payload = row.model_dump(mode="python")
    payload["source_anchors"][0]["verbatim_excerpt"] = "符合以下任一项：存在既往病史或当前症状"
    with pytest.raises(ValidationError, match="来源存在顶层或/列表分支关系"):
        ProtocolControlMatrixRow.model_validate(payload)


def test_matrix_requires_dnf_basis_for_compound_and_alternative_groups() -> None:
    with pytest.raises(ValidationError, match="多原子 DNF 合取组"):
        MatrixDnfGroup(atom_ids=["a", "b"])
    with pytest.raises(ValidationError, match="多替代组 DNF"):
        MatrixDnf(
            groups=[
                MatrixDnfGroup(atom_ids=["a"]),
                MatrixDnfGroup(atom_ids=["b"]),
            ]
        )


@pytest.mark.parametrize(
    ("label", "anchor_type", "direction"),
    [
        ("筛选日期", AnchorType.EVENT_DATE, TimeDirection.ON),
        ("基线日期", AnchorType.EVENT_DATE, TimeDirection.ON),
        ("首次给药前 3 个月", AnchorType.EVENT_DATE, TimeDirection.ON),
        ("首次给药后 3 个月", AnchorType.FIRST_DOSE_DATE, TimeDirection.ON),
        ("随机日期", AnchorType.SCREENING_DATE, TimeDirection.ON),
    ],
)
def test_matrix_rejects_generic_or_wrong_named_time_anchors(
    label: str, anchor_type: AnchorType, direction: TimeDirection
) -> None:
    row = _row(
        "row-time-boundary",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前核对禁用治疗",
        ordinal=1,
    )
    payload = row.model_dump(mode="python")
    payload["time_anchors"] = [
        MatrixTimeAnchor(
            time_constraint_id="time-boundary",
            anchor_label_zh=label,
            time_constraint=TimeConstraint(
                anchor_type=anchor_type,
                direction=direction,
            ),
            source_anchor_ids=[row.source_anchors[0].source_anchor_id],
        )
    ]
    with pytest.raises(ValidationError):
        ProtocolControlMatrixRow.model_validate(payload)


def test_matrix_preserves_screening_and_baseline_as_two_named_anchors() -> None:
    row = _row(
        "row-two-milestones",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前核对禁用治疗",
        ordinal=1,
    )
    anchor_id = row.source_anchors[0].source_anchor_id
    payload = row.model_dump(mode="python")
    payload["source_anchors"][0]["verbatim_excerpt"] = "筛选和基线均需评估"
    payload["time_anchors"] = [
        MatrixTimeAnchor(
            time_constraint_id="time-screening",
            anchor_label_zh="筛选日期",
            time_constraint=TimeConstraint(
                anchor_type=AnchorType.SCREENING_DATE,
                direction=TimeDirection.ON,
            ),
            source_anchor_ids=[anchor_id],
        ),
        MatrixTimeAnchor(
            time_constraint_id="time-baseline",
            anchor_label_zh="基线日期",
            time_constraint=TimeConstraint(
                anchor_type=AnchorType.BASELINE_DATE,
                direction=TimeDirection.ON,
            ),
            source_anchor_ids=[anchor_id],
        ),
    ]
    valid = ProtocolControlMatrixRow.model_validate(payload)
    assert [item.anchor_label_zh for item in valid.time_anchors] == ["筛选日期", "基线日期"]


def test_matrix_rejects_incomplete_half_life_or_window_expression() -> None:
    row = _row(
        "row-half-life",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前洗脱期",
        ordinal=1,
    )
    payload = row.model_dump(mode="python")
    payload["source_anchors"][0]["verbatim_excerpt"] = "首次给药前 3 个月，另按 5 个半衰期择长"
    payload["time_anchors"] = [
        MatrixTimeAnchor(
            time_constraint_id="time-half-life",
            anchor_label_zh="首次给药前 3 个月或 5 个半衰期",
            time_constraint=TimeConstraint(
                anchor_type=AnchorType.FIRST_DOSE_DATE,
                direction=TimeDirection.BEFORE,
                lower_bound_days=90,
            ),
            source_anchor_ids=[row.source_anchors[0].source_anchor_id],
        )
    ]
    with pytest.raises(ValidationError, match="半衰期与固定窗口择长规则"):
        ProtocolControlMatrixRow.model_validate(payload)


def test_matrix_rejects_placeholder_or_repeated_minimum_evidence() -> None:
    row = _row(
        "row-evidence-boundary",
        ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY,
        unit_id="su-official",
        span_id="span-official",
        excerpt="必须符合入选条件",
        ordinal=1,
    )
    placeholder = row.minimum_evidence[0].model_dump(mode="python")
    placeholder["fact_type_zh"] = "方案官方条件"
    with pytest.raises(ValidationError, match="空泛方案条件"):
        MatrixEvidence.model_validate(placeholder)

    repeated = row.model_dump(mode="python")
    repeated["minimum_evidence"][0]["description_zh"] = row.source_anchors[0].verbatim_excerpt
    with pytest.raises(ValidationError, match="逐字复述"):
        ProtocolControlMatrixRow.model_validate(repeated)

    missing_source_types = row.model_dump(mode="python")
    missing_source_types["minimum_evidence"][0]["required_source_types"] = []
    with pytest.raises(ValidationError, match="具体来源类型"):
        ProtocolControlMatrixRow.model_validate(missing_source_types)


def test_matrix_requires_objective_and_researcher_evidence_when_semantics_need_them() -> None:
    objective = _row(
        "row-objective-evidence",
        ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY,
        unit_id="su-official",
        span_id="span-official",
        excerpt="必须符合入选条件",
        ordinal=1,
    )
    objective_payload = objective.model_dump(mode="python")
    objective_payload["source_anchors"][0]["verbatim_excerpt"] = "实验室检查结果满足方案要求"
    with pytest.raises(ValidationError, match="同期客观来源"):
        ProtocolControlMatrixRow.model_validate(objective_payload)
    objective_payload["minimum_evidence"][0]["requires_contemporaneous_objective_source"] = True
    objective_valid = ProtocolControlMatrixRow.model_validate(objective_payload)

    judgment_payload = objective_valid.model_dump(mode="python")
    judgment_payload["obligations"][0]["requires_professional_judgment"] = True
    with pytest.raises(ValidationError, match="研究者评估记录"):
        ProtocolControlMatrixRow.model_validate(judgment_payload)
    judgment_payload["minimum_evidence"][0]["requires_researcher_assessment_record"] = True
    assert ProtocolControlMatrixRow.model_validate(judgment_payload)


def test_matrix_review_nodes_require_source_and_supported_stage() -> None:
    row = _row(
        "row-node-boundary",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前核对禁用治疗",
        ordinal=1,
    )
    missing_source = row.model_dump(mode="python")
    missing_source["review_nodes"][0]["source_anchor_ids"] = []
    with pytest.raises(ValidationError):
        ProtocolControlMatrixRow.model_validate(missing_source)

    wrong_stage = row.model_dump(mode="python")
    wrong_stage["review_nodes"][0].update(
        review_stage=ReviewStage.BASELINE,
        node_label_zh="基线期",
    )
    with pytest.raises(ValidationError, match="阶段必须由直接来源"):
        ProtocolControlMatrixRow.model_validate(wrong_stage)

    bad_node = row.review_nodes[0].model_copy(update={"source_anchor_ids": ["unknown-anchor"]})
    bad_row = row.model_copy(update={"review_nodes": [bad_node]})
    bad_matrix = _matrix().model_copy(update={"rows": [bad_row]})
    with pytest.raises(ValueError, match="REVIEW_NODE_SOURCE_ESCAPE"):
        validate_protocol_control_matrix(bad_matrix, _manifest())


def test_matrix_allows_official_node_to_use_same_matrix_procedure_basis() -> None:
    matrix = _matrix()
    procedure_row = matrix.rows[1]
    official = matrix.rows[0]
    payload = official.model_dump(mode="python")
    payload["review_nodes"][0]["source_anchor_ids"] = []
    payload["review_nodes"][0]["workflow_basis_row_id"] = procedure_row.matrix_row_id
    official_with_basis = ProtocolControlMatrixRow.model_validate(payload)
    with_basis = matrix.model_copy(
        update={"rows": [official_with_basis, procedure_row, matrix.rows[2]]}
    )

    assert validate_protocol_control_matrix(
        with_basis,
        _manifest(),
        official_parent_codes=["IN-01"],
        required_procedure_ids=["proc-01"],
        protocol_controls=[_other_control()],
    ) is with_basis
    markdown = render_protocol_control_matrix_markdown(with_basis)
    visible = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
    assert "节点依据：研究流程中的流程必做 01（控制短标题）" in visible
    assert procedure_row.matrix_row_id not in visible
    assert validate_protocol_control_matrix_serializations(
        with_basis,
        build_protocol_control_matrix_json(with_basis),
        markdown,
    ) is with_basis
    both_payload = official.model_dump(mode="python")
    both_payload["review_nodes"][0]["source_anchor_ids"] = [
        official.source_anchors[0].source_anchor_id
    ]
    both_payload["review_nodes"][0]["workflow_basis_row_id"] = procedure_row.matrix_row_id
    both_official = ProtocolControlMatrixRow.model_validate(both_payload)
    both = matrix.model_copy(
        update={"rows": [both_official, procedure_row, matrix.rows[2]]}
    )
    assert validate_protocol_control_matrix(both, _manifest()) is both
    tampered_basis = markdown.replace(
        f'"workflow_basis_row_id":"{procedure_row.matrix_row_id}"',
        '"workflow_basis_row_id":"pcm-row-unknown"',
        1,
    )
    with pytest.raises(ValueError, match="MARKDOWN_ROW_IDENTITY_MISMATCH"):
        validate_protocol_control_matrix_serializations(
            with_basis,
            build_protocol_control_matrix_json(with_basis),
            tampered_basis,
        )


@pytest.mark.parametrize("basis_mutation", ["unknown", "self", "non_procedure", "stage_missing"])
def test_matrix_rejects_invalid_workflow_basis_rows(basis_mutation: str) -> None:
    matrix = _matrix()
    official = matrix.rows[0]
    procedure = matrix.rows[1]
    payload = official.model_dump(mode="python")
    payload["review_nodes"][0]["source_anchor_ids"] = []
    if basis_mutation == "unknown":
        payload["review_nodes"][0]["workflow_basis_row_id"] = "pcm-row-unknown"
        expected = "REVIEW_NODE_BASIS_UNKNOWN"
    elif basis_mutation == "self":
        payload["review_nodes"][0]["workflow_basis_row_id"] = official.matrix_row_id
        expected = "REVIEW_NODE_BASIS_SELF"
    elif basis_mutation == "non_procedure":
        payload["review_nodes"][0]["workflow_basis_row_id"] = matrix.rows[2].matrix_row_id
        expected = "REVIEW_NODE_BASIS_KIND_INVALID"
    else:
        payload["review_nodes"][0]["review_stage"] = ReviewStage.BASELINE
        payload["review_nodes"][0]["node_label_zh"] = "基线期"
        payload["review_nodes"][0]["workflow_basis_row_id"] = procedure.matrix_row_id
        with pytest.raises(ValueError, match="REVIEW_NODE_BASIS_STAGE_MISSING"):
            validate_protocol_control_matrix(
                matrix.model_copy(
                    update={
                        "rows": [
                            ProtocolControlMatrixRow.model_validate(payload),
                            procedure,
                            matrix.rows[2],
                        ]
                    }
                ),
                _manifest(),
            )
        return

    with pytest.raises(ValueError, match=expected):
        validate_protocol_control_matrix(
            matrix.model_copy(
                update={
                    "rows": [ProtocolControlMatrixRow.model_validate(payload), *matrix.rows[1:]]
                }
            ),
            _manifest(),
        )


def test_matrix_rejects_workflow_basis_when_no_direct_or_cross_source_basis_exists() -> None:
    row = _row(
        "row-node-no-basis",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前核对禁用治疗",
        ordinal=1,
    )
    payload = row.model_dump(mode="python")
    payload["review_nodes"][0]["source_anchor_ids"] = []
    payload["review_nodes"][0]["workflow_basis_row_id"] = None
    with pytest.raises(ValidationError, match="至少需要直接来源锚点或同矩阵流程依据"):
        ProtocolControlMatrixRow.model_validate(payload)


def test_strict_matrix_rejects_tampered_compound_atom_and_placeholder_evidence() -> None:
    row = _row(
        "row-strict-semantic-boundary",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前核对禁用治疗",
        ordinal=1,
    )
    bad_obligation = row.obligations[0].model_copy(
        update={"statement_zh": "A 且 B"}
    )
    bad_row = row.model_copy(update={"obligations": [bad_obligation]})
    with pytest.raises(ValueError, match="ATOMIC_LOGIC_NOT_EXPRESSED"):
        validate_protocol_control_matrix(
            _matrix().model_copy(update={"rows": [bad_row]}),
            _manifest(),
        )

    bad_evidence = row.minimum_evidence[0].model_copy(
        update={"fact_type_zh": "方案官方条件"}
    )
    bad_row = row.model_copy(update={"minimum_evidence": [bad_evidence]})
    with pytest.raises(ValueError, match="EVIDENCE_FACT_TYPE_PLACEHOLDER"):
        validate_protocol_control_matrix(
            _matrix().model_copy(update={"rows": [bad_row]}),
            _manifest(),
        )


def test_official_child_must_keep_parent_identity() -> None:
    with pytest.raises(ValidationError, match="官方子编号必须以其父编号开头"):
        base = _row(
            "row-child",
            ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY,
            unit_id="su-official",
            span_id="span-official",
            excerpt="必须符合入选条件",
            ordinal=1,
        )
        ProtocolControlMatrixRow.model_validate(
            {**base.model_dump(mode="python"), "official_child_code": "EX-01.01"}
        )


def test_matrix_rejects_tampered_row_and_anchor_identity_in_contract_and_validator() -> None:
    base = _row(
        "row-tamper",
        ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY,
        unit_id="su-official",
        span_id="span-official",
        excerpt="必须符合入选条件",
        ordinal=1,
    )
    with pytest.raises(ValidationError, match="矩阵行身份必须等于系统派生身份"):
        ProtocolControlMatrixRow.model_validate(
            {**base.model_dump(mode="python"), "matrix_row_id": "pcm-row-tampered"}
        )
    with pytest.raises(ValidationError, match="矩阵来源锚点身份必须等于"):
        ProtocolControlMatrixRow.model_validate(
            {
                **base.model_dump(mode="python"),
                "source_anchors": [
                    base.source_anchors[0].model_copy(
                        update={"source_anchor_id": "pcm-src-tampered"}
                    )
                ],
            }
        )

    tampered_row = base.model_copy(update={"matrix_row_id": "pcm-row-tampered"})
    with pytest.raises(ValueError, match="MATRIX_ROW_ID_DERIVED_MISMATCH"):
        validate_protocol_control_matrix(
            _matrix().model_copy(update={"rows": [tampered_row]}), _manifest()
        )
    tampered_anchor = base.source_anchors[0].model_copy(
        update={"source_anchor_id": "pcm-src-tampered"}
    )
    tampered_row = base.model_copy(update={"source_anchors": [tampered_anchor]})
    with pytest.raises(ValueError, match="SOURCE_ANCHOR_ID_DERIVED_MISMATCH"):
        validate_protocol_control_matrix(
            _matrix().model_copy(update={"rows": [tampered_row]}), _manifest()
        )


def test_matrix_source_anchor_order_is_frozen_by_ordinal_and_manifest() -> None:
    row = _row(
        "row-order",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前核对禁用治疗",
        ordinal=1,
    )
    first = _anchor(
        row.matrix_row_id,
        "su-procedure",
        "span-procedure",
        "筛选期完成检查",
        source_ordinal=0,
    )
    second = _anchor(
        row.matrix_row_id,
        "su-other",
        "span-other",
        "首次给药前核对禁用治疗",
        source_ordinal=1,
    )
    payload = row.model_dump(mode="python")
    payload["source_anchors"] = [first, second]
    anchor_ids = [first.source_anchor_id, second.source_anchor_id]
    payload["obligations"][0]["source_anchor_ids"] = sorted(anchor_ids)
    payload["minimum_evidence"][0]["source_anchor_ids"] = sorted(anchor_ids)
    valid = ProtocolControlMatrixRow.model_validate(payload)
    swapped = valid.model_dump(mode="python")
    swapped["source_anchors"] = list(reversed(swapped["source_anchors"]))
    with pytest.raises(ValidationError, match="稳定序位连续排列"):
        ProtocolControlMatrixRow.model_validate(swapped)

    swapped["source_anchors"] = [
        valid.source_anchors[0].model_copy(
            update={
                "structure_unit_id": "su-other",
                "source_ref": "body.p2",
                "source_span_ids": ["span-other"],
                "verbatim_excerpt": "首次给药前核对禁用治疗",
            }
        ),
        valid.source_anchors[1].model_copy(
            update={
                "structure_unit_id": "su-procedure",
                "source_ref": "body.p1",
                "source_span_ids": ["span-procedure"],
                "verbatim_excerpt": "筛选期完成检查",
            }
        ),
    ]
    with pytest.raises(ValueError, match="SOURCE_ANCHOR_ORDER_MISMATCH"):
        validate_protocol_control_matrix(
            _matrix().model_copy(
                update={"rows": [ProtocolControlMatrixRow.model_construct(**swapped)]}
            ),
            _manifest(),
        )


def test_matrix_markdown_is_chinese_detailed_and_serialization_order_is_checked() -> None:
    matrix = _matrix()
    json_payload = build_protocol_control_matrix_json(matrix)
    markdown = render_protocol_control_matrix_markdown(matrix)
    visible = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
    assert "official_eligibility" not in visible
    assert "selected_phase_applicable" not in visible
    assert "本项目适用性" in visible
    assert "本项目适用" in visible
    assert "选定期别适用" not in visible
    assert "跨期共享" not in visible
    assert "行身份" not in visible
    assert "访视实例" not in visible
    assert "IN-01" in visible
    assert "流程必做 01" in visible
    assert "方案控制 01" in visible
    for row in matrix.rows:
        assert row.matrix_row_id not in visible
        if row.source_kind != ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY:
            assert row.source_identity not in visible
        for anchor in row.source_anchors:
            assert anchor.source_anchor_id not in visible
            assert anchor.structure_unit_id not in visible
            assert anchor.source_ref not in visible
            assert not any(span_id in visible for span_id in anchor.source_span_ids)
        for obligation in row.obligations:
            assert obligation.obligation_id not in visible
        for evidence in row.minimum_evidence:
            assert evidence.evidence_id not in visible
        for node in row.review_nodes:
            assert node.workflow_stage_id not in visible
        for relation in row.cross_source_relations:
            assert relation.relation_id not in visible
            assert relation.target_row_id not in visible
    for field_name in (
        "matrix_row_id",
        "source_anchor_id",
        "workflow_stage_id",
        "workflow_basis_row_id",
        "time_constraint_id",
        "obligation_id",
        "evidence_id",
        "relation_id",
        "source_ref",
        "source_span_ids",
    ):
        assert field_name not in visible
    for label in (
        "做什么",
        "达标条件",
        "禁止事项",
        "审核节点",
        "方案命名时间锚点/窗口",
        "六类义务及 DNF 逻辑",
        "最低证据",
        "专业判断",
        "跨章节关系",
        "来源标题路径",
        "逐字摘录",
    ):
        assert label in visible
    assert "（记录核对结果）" in visible
    assert "pcm-row-" not in visible
    assert "pcm-src-" not in visible
    assert validate_protocol_control_matrix_serializations(
        matrix, json_payload, markdown
    ) is matrix

    broken_heading = markdown.replace("## IN-01：", "## 流程必做 01：", 1)
    with pytest.raises(ValueError, match="MARKDOWN_DETAIL_ORDER_MISMATCH"):
        validate_protocol_control_matrix_serializations(matrix, json_payload, broken_heading)
    broken_identity = markdown.replace(
        "- 审阅标签：IN-01",
        "- 审阅标签：流程必做 01",
        1,
    )
    with pytest.raises(ValueError, match="MARKDOWN_DETAIL_IDENTITY_MISMATCH"):
        validate_protocol_control_matrix_serializations(matrix, json_payload, broken_identity)
    broken_index = markdown.replace(
        "| IN-01 | 官方入排条件 | 控制短标题 | 本项目适用 |",
        "| 未知标签 | 官方入排条件 | 控制短标题 | 本项目适用 |",
        1,
    )
    with pytest.raises(ValueError, match="MARKDOWN_INDEX_MISMATCH"):
        validate_protocol_control_matrix_serializations(matrix, json_payload, broken_index)
    broken_enum = markdown.replace("官方入排条件", "official_eligibility", 1)
    with pytest.raises(ValueError, match="MARKDOWN_ENUM_VISIBLE"):
        validate_protocol_control_matrix_serializations(matrix, json_payload, broken_enum)
    broken_machine = markdown.replace("方案控制 01", "方案控制 stage:fake", 1)
    with pytest.raises(ValueError, match="MARKDOWN_MACHINE_ID_VISIBLE"):
        validate_protocol_control_matrix_serializations(matrix, json_payload, broken_machine)
    broken_field = markdown.replace("控制短标题", "控制 matrix_row_id", 1)
    with pytest.raises(ValueError, match="MARKDOWN_INTERNAL_FIELD_VISIBLE"):
        validate_protocol_control_matrix_serializations(matrix, json_payload, broken_field)


def test_matrix_allows_structured_empty_summary_and_renders_source_gap() -> None:
    row = _row(
        "row-empty-summary",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前核对禁用治疗",
        ordinal=1,
    )
    payload = row.model_dump(mode="python")
    payload.update(
        required_action_zh=None,
        attainment_criteria_zh=None,
        prohibition_zh=None,
    )
    empty_row = ProtocolControlMatrixRow.model_validate(payload)
    matrix = ProtocolControlMatrix(
        matrix_id="matrix:empty-summary",
        protocol_version_id="protocol:matrix",
        protocol_document_sha256=_SHA,
        selected_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:matrix",
        coverage_manifest_id="manifest:matrix",
        title_zh="结构化空值反例",
        rows=[empty_row],
    )
    visible = re.sub(
        r"<!--.*?-->", "", render_protocol_control_matrix_markdown(matrix), flags=re.DOTALL
    )
    assert visible.count("方案未规定该类要求") == 3
    assert "记录核对结果" in visible
    assert validate_protocol_control_matrix_serializations(
        matrix, build_protocol_control_matrix_json(matrix), render_protocol_control_matrix_markdown(matrix)
    ) is matrix


def test_matrix_dnf_markdown_uses_chinese_statements_without_atom_ids() -> None:
    row = _row(
        "row-dnf-visible",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前核对禁用治疗",
        ordinal=1,
    )
    anchor_id = row.source_anchors[0].source_anchor_id
    payload = row.model_dump(mode="python")
    condition_a = MatrixConditionAtom(
        atom_id="condition-a",
        statement_zh="有既往病史",
        source_anchor_ids=[anchor_id],
    )
    condition_b = MatrixConditionAtom(
        atom_id="condition-b",
        statement_zh="达到稳定状态",
        source_anchor_ids=[anchor_id],
    )
    payload["condition_atoms"] = [condition_a, condition_b]
    payload["applicability_expression"] = MatrixDnf(
        groups=[
            MatrixDnfGroup(
                atom_ids=["condition-a", "condition-b"],
                logic_basis_zh="来源明确要求两项同时满足（且）",
                source_anchor_ids=[anchor_id],
            )
        ]
    )
    dnf_row = ProtocolControlMatrixRow.model_validate(payload)
    matrix = ProtocolControlMatrix(
        matrix_id="matrix:dnf-visible",
        protocol_version_id="protocol:matrix",
        protocol_document_sha256=_SHA,
        selected_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:matrix",
        coverage_manifest_id="manifest:matrix",
        title_zh="中文 DNF 反例",
        rows=[dnf_row],
    )
    visible = re.sub(
        r"<!--.*?-->", "", render_protocol_control_matrix_markdown(matrix), flags=re.DOTALL
    )
    assert "（有既往病史 且 达到稳定状态）" in visible
    assert "condition-a" not in visible
    assert "condition-b" not in visible
    markdown = render_protocol_control_matrix_markdown(matrix)
    assert validate_protocol_control_matrix_serializations(
        matrix, build_protocol_control_matrix_json(matrix), markdown
    ) is matrix


def test_exception_paths_are_scoped_to_exact_trigger_branches() -> None:
    row = _trigger_exception_row(
        exception_scopes=[
            [stable_protocol_control_matrix_trigger_branch_id(
                stable_protocol_control_matrix_row_id(
                    ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
                    "pctrl-other",
                    None,
                ),
                0,
            )],
            [stable_protocol_control_matrix_trigger_branch_id(
                stable_protocol_control_matrix_row_id(
                    ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
                    "pctrl-other",
                    None,
                ),
                0,
            )],
            [stable_protocol_control_matrix_trigger_branch_id(
                stable_protocol_control_matrix_row_id(
                    ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
                    "pctrl-other",
                    None,
                ),
                1,
            )],
        ]
    )
    trigger_ids = [
        group.trigger_branch_id for group in row.trigger_expression.groups
    ]
    assert row.exception_expression is not None
    assert [
        group.waives_trigger_branch_ids for group in row.exception_expression.groups
    ] == [[trigger_ids[0]], [trigger_ids[0]], [trigger_ids[1]]]


def test_trigger_branch_identity_is_derived_and_tamper_rejected() -> None:
    row = _trigger_exception_row(
        exception_scopes=[
            [stable_protocol_control_matrix_trigger_branch_id(
                stable_protocol_control_matrix_row_id(
                    ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
                    "pctrl-other",
                    None,
                ),
                0,
            )]
        ]
    )
    bad_group = row.trigger_expression.groups[0].model_copy(
        update={"trigger_branch_id": "pcm-trg-tampered"}
    )
    bad_row = row.model_copy(
        update={"trigger_expression": MatrixDnf(groups=[bad_group, row.trigger_expression.groups[1]])}
    )
    matrix = ProtocolControlMatrix(
        matrix_id="matrix:trigger-identity",
        protocol_version_id="protocol:matrix",
        protocol_document_sha256=_SHA,
        selected_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:matrix",
        coverage_manifest_id="manifest:matrix",
        title_zh="触发分支身份",
        rows=[row],
    )
    with pytest.raises(ValueError, match="TRIGGER_BRANCH_ID_DERIVED_MISMATCH"):
        validate_protocol_control_matrix(
            matrix.model_copy(update={"rows": [bad_row]}),
            _manifest(),
        )


def test_exception_scope_all_triggers_requires_and_accepts_explicit_source_support() -> None:
    row_id = stable_protocol_control_matrix_row_id(
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        "pctrl-other",
        None,
    )
    scopes = [
        sorted(
            [
                stable_protocol_control_matrix_trigger_branch_id(row_id, 0),
                stable_protocol_control_matrix_trigger_branch_id(row_id, 1),
            ]
        )
    ]
    row = _trigger_exception_row(
        exception_scopes=scopes,
        source_text="任何触发分支均可适用例外处理",
    )
    assert row.exception_expression.groups[0].waives_trigger_branch_ids == scopes[0]


def test_exception_scope_supports_not_and_chinese_rendering_without_branch_ids() -> None:
    row = _trigger_exception_row(
        exception_scopes=[
            [stable_protocol_control_matrix_trigger_branch_id(
                stable_protocol_control_matrix_row_id(
                    ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
                    "pctrl-other",
                    None,
                ),
                0,
            )]
        ],
        use_not=True,
    )
    matrix = ProtocolControlMatrix(
        matrix_id="matrix:trigger-exception",
        protocol_version_id="protocol:matrix",
        protocol_document_sha256=_SHA,
        selected_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:matrix",
        coverage_manifest_id="manifest:matrix",
        title_zh="触发例外作用域矩阵",
        rows=[row],
    )
    json_payload = build_protocol_control_matrix_json(matrix)
    markdown = render_protocol_control_matrix_markdown(matrix)
    visible = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
    assert '"trigger_branch_id":"pcm-trg-' in json_payload
    assert '"waives_trigger_branch_ids":["pcm-trg-' in json_payload
    assert "非（存在触发排除条件丙）" in visible
    assert "例外作用域（仅作用于明确触发分支）" in visible
    assert "仅适用于触发条件：存在触发分支甲" in visible
    assert "pcm-trg-" not in visible
    for field_name in (
        "trigger_branch_id",
        "waives_trigger_branch_ids",
        "negated_atom_ids",
    ):
        assert field_name not in visible
    assert validate_protocol_control_matrix_serializations(
        matrix, json_payload, markdown
    ) is matrix
    tampered = markdown.replace(
        '"waives_trigger_branch_ids":["pcm-trg-',
        '"waives_trigger_branch_ids":["pcm-trg-tampered-',
        1,
    )
    with pytest.raises(ValueError, match="MARKDOWN_ROW_IDENTITY_MISMATCH"):
        validate_protocol_control_matrix_serializations(matrix, json_payload, tampered)


@pytest.mark.parametrize(
    ("scopes", "expected"),
    [
        ([[]], "EXCEPTION_SCOPE_MISSING"),
        ([['pcm-trg-unknown']], "EXCEPTION_SCOPE_UNKNOWN_TRIGGER"),
        ([['obligation-branch']], "EXCEPTION_SCOPE_UNKNOWN_TRIGGER"),
        (
            [sorted([
                stable_protocol_control_matrix_trigger_branch_id(
                    stable_protocol_control_matrix_row_id(
                        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
                        "pctrl-other",
                        None,
                    ),
                    0,
                ),
                stable_protocol_control_matrix_trigger_branch_id(
                    stable_protocol_control_matrix_row_id(
                        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
                        "pctrl-other",
                        None,
                    ),
                    1,
                ),
            ])],
            "EXCEPTION_SCOPE_ALL_UNSUPPORTED",
        ),
    ],
)
def test_exception_scope_missing_unknown_or_broad_is_rejected(
    scopes: list[list[str]], expected: str
) -> None:
    row = _trigger_exception_row(
        exception_scopes=[
            [
                stable_protocol_control_matrix_trigger_branch_id(
                    stable_protocol_control_matrix_row_id(
                        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
                        "pctrl-other",
                        None,
                    ),
                    0,
                )
            ]
        ]
    )
    group = row.exception_expression.groups[0].model_copy(
        update={"waives_trigger_branch_ids": scopes[0]}
    )
    bad_row = row.model_copy(
        update={"exception_expression": MatrixDnf(groups=[group])}
    )
    matrix = ProtocolControlMatrix(
        matrix_id="matrix:exception-scope-boundary",
        protocol_version_id="protocol:matrix",
        protocol_document_sha256=_SHA,
        selected_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:matrix",
        coverage_manifest_id="manifest:matrix",
        title_zh="例外作用域边界",
        rows=[row],
    )
    with pytest.raises((ValidationError, ValueError), match=expected):
        validate_protocol_control_matrix(
            matrix.model_copy(update={"rows": [bad_row]}),
            _manifest(),
        )


def test_matrix_preserves_and_compound_obligations_and_rejects_fake_padding() -> None:
    row = _row(
        "row-and",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前核对禁用治疗",
        ordinal=1,
    )
    payload = row.model_dump(mode="python")
    first = dict(payload["obligations"][0])
    first_id = first["obligation_id"]
    second_id = f"{row.matrix_row_id}:obligation-b"
    first["conjunction_group_id"] = "and:1"
    second = {
        **first,
        "obligation_id": second_id,
        "statement_zh": "完成第二项核对",
    }
    payload["obligations"] = [first, second]
    payload["obligation_expression"] = MatrixDnf(
        groups=[
            MatrixDnfGroup(
                atom_ids=sorted([first_id, second_id]),
                logic_basis_zh="来源明确要求两项同时完成（且）",
                source_anchor_ids=[row.source_anchors[0].source_anchor_id],
            )
        ]
    )
    compound = ProtocolControlMatrixRow.model_validate(payload)
    assert len(compound.obligations) == 2
    assert {item.kind for item in compound.obligations} == {ControlObligationKind.MUST_RECORD}

    weakened = compound.model_dump(mode="python")
    weakened["obligation_expression"] = MatrixDnf(
        groups=[MatrixDnfGroup(atom_ids=[first_id])]
    )
    with pytest.raises(ValidationError, match="义务原子必须在义务 DNF"):
        ProtocolControlMatrixRow.model_validate(weakened)

    arbitrary_alternatives = compound.model_dump(mode="python")
    anchor_id = row.source_anchors[0].source_anchor_id
    arbitrary_alternatives["obligation_expression"] = MatrixDnf(
        groups=[
            MatrixDnfGroup(
                atom_ids=[first_id],
                logic_basis_zh="各组之间任选一项或另一项",
                source_anchor_ids=[anchor_id],
            ),
            MatrixDnfGroup(
                atom_ids=[second_id],
                logic_basis_zh="各组之间任选一项或另一项",
                source_anchor_ids=[anchor_id],
            ),
        ]
    )
    with pytest.raises(ValidationError, match="且复合义务不得被弱化"):
        ProtocolControlMatrixRow.model_validate(arbitrary_alternatives)

    padded = row.model_dump(mode="python")
    padded["obligations"][0]["statement_zh"] = "不适用"
    with pytest.raises(ValidationError, match="虚假占位表述"):
        ProtocolControlMatrixRow.model_validate(padded)

    assert len(row.obligations) == 1
    assert {item.kind for item in row.obligations} == {ControlObligationKind.MUST_RECORD}


def test_phase_disposition_is_internal_but_independent_project_markdown_is_natural_zh() -> None:
    assert CONTROL_MATRIX_CONTRACT_VERSION == "phase5/control-matrix/v5"
    row = _row(
        "row-shared",
        ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY,
        unit_id="su-official",
        span_id="span-official",
        excerpt="必须符合入选条件",
        ordinal=1,
    ).model_copy(update={"phase_disposition": MatrixPhaseDisposition.CROSS_PHASE_SHARED})
    matrix = _matrix().model_copy(update={"rows": [row, *_matrix().rows[1:]]})
    json_payload = build_protocol_control_matrix_json(matrix)
    markdown = render_protocol_control_matrix_markdown(matrix)
    visible = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)

    assert '"phase_disposition":"cross_phase_shared"' in json_payload
    assert "本项目适用性" in visible
    assert "本项目适用" in visible
    assert "跨期共享" not in visible
    assert "选定期别适用" not in visible
    assert validate_protocol_control_matrix_serializations(
        matrix, json_payload, markdown
    ) is matrix


@pytest.mark.parametrize(
    ("title", "official_code"),
    (
        ("官方入选 IN-01", "IN-01"),
        ("官方排除 EX-01", "EX-01"),
        ("IN-01", "IN-01"),
    ),
)
def test_official_title_must_describe_the_control_not_repeat_generic_code(
    title: str, official_code: str
) -> None:
    with pytest.raises(ValidationError, match="机械重复编号"):
        _row(
            "row-mechanical-title",
            ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY,
            unit_id="su-official",
            span_id="span-official",
            excerpt="必须符合入选条件",
            ordinal=1,
            title=title,
            official_code=official_code,
        )

    meaningful = _row(
        "row-meaningful-title",
        ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY,
        unit_id="su-official",
        span_id="span-official",
        excerpt="必须符合入选条件",
        ordinal=1,
        title="知情同意与沟通遵从能力",
        official_code=official_code,
    )
    assert meaningful.title_zh == "知情同意与沟通遵从能力"


def test_candidate_and_formal_source_identities_are_mutually_exclusive_and_stable() -> None:
    formal = _row(
        "row-formal-boundary",
        ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE,
        unit_id="su-procedure",
        span_id="span-procedure",
        excerpt="筛选期完成检查",
        ordinal=1,
    )
    formal_payload = formal.model_dump(mode="python")
    formal_payload["source_candidate_id"] = "candidate:procedure-01"
    with pytest.raises(ValidationError, match="必须且只能提供正式流程目录身份或来源候选身份"):
        ProtocolControlMatrixRow.model_validate(formal_payload)
    formal_candidate_payload = formal.model_dump(mode="python")
    formal_candidate_payload["required_procedure_catalog_item_id"] = "candidate:procedure-01"
    with pytest.raises(ValidationError, match="正式流程目录身份不得使用流程候选身份"):
        ProtocolControlMatrixRow.model_validate(formal_candidate_payload)

    candidate = _row(
        "row-candidate-boundary",
        ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE,
        unit_id="su-procedure",
        span_id="span-procedure",
        excerpt="筛选期完成检查",
        ordinal=1,
        candidate_id="candidate:procedure-01",
    )
    assert candidate.required_procedure_catalog_item_id is None
    assert candidate.source_candidate_id == "candidate:procedure-01"
    assert candidate.matrix_row_id == stable_protocol_control_matrix_row_id(
        ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE,
        "candidate:procedure-01",
        None,
    )
    invalid_candidate = candidate.model_dump(mode="python")
    invalid_candidate["source_candidate_id"] = "proc-01"
    with pytest.raises(ValidationError, match="candidate 前缀"):
        ProtocolControlMatrixRow.model_validate(invalid_candidate)
    candidate_payload = candidate.model_dump(mode="python")
    candidate_payload["required_procedure_catalog_item_id"] = "proc-01"
    with pytest.raises(ValidationError, match="必须且只能提供正式流程目录身份或来源候选身份"):
        ProtocolControlMatrixRow.model_validate(candidate_payload)

    validator_tampered = candidate.model_copy(
        update={"required_procedure_catalog_item_id": "proc-01"}
    )
    validator_base = ProtocolControlMatrix(
        matrix_id="matrix:validator-boundary",
        protocol_version_id="protocol:matrix",
        protocol_document_sha256=_SHA,
        selected_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:matrix",
        coverage_manifest_id="manifest:matrix",
        title_zh="严格校验身份边界",
        rows=[candidate],
    )
    validator_matrix = validator_base.model_copy(update={"rows": [validator_tampered]})
    with pytest.raises(ValueError, match="SOURCE_IDENTITY_MUTUAL_EXCLUSION"):
        validate_protocol_control_matrix(validator_matrix, _manifest())

    candidate_matrix = ProtocolControlMatrix(
        matrix_id="matrix:candidate-disposition",
        protocol_version_id="protocol:matrix",
        protocol_document_sha256=_SHA,
        selected_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:matrix",
        coverage_manifest_id="manifest:matrix",
        title_zh="候选处置边界",
        rows=[candidate],
    )
    with pytest.raises(ValueError, match="CANDIDATE_FORMAL_LINK_FORBIDDEN"):
        validate_protocol_control_matrix(candidate_matrix, _manifest())
    with pytest.raises(ValueError, match="CANDIDATE_DISPOSITION_MISMATCH"):
        validate_protocol_control_matrix(
            candidate_matrix,
            _manifest(procedure_candidate_id="candidate:procedure-other"),
        )
    assert validate_protocol_control_matrix(
        candidate_matrix,
        _manifest(procedure_candidate_id="candidate:procedure-01"),
    ) is candidate_matrix

    formal_matrix = _matrix()
    with pytest.raises(ValueError, match="PROCEDURE_DISPOSITION_CANDIDATE_MISMATCH"):
        validate_protocol_control_matrix(
            formal_matrix,
            _manifest(procedure_candidate_id="candidate:procedure-01"),
        )

    official_payload = _row(
        "row-official-boundary",
        ProtocolControlMatrixSourceKind.OFFICIAL_ELIGIBILITY,
        unit_id="su-official",
        span_id="span-official",
        excerpt="必须符合入选条件",
        ordinal=1,
    ).model_dump(mode="python")
    official_payload["source_candidate_id"] = "candidate:official-01"
    with pytest.raises(ValidationError, match="官方入排行不得携带"):
        ProtocolControlMatrixRow.model_validate(official_payload)


def test_candidate_rows_are_manual_baseline_only_and_formal_complete_rows_need_authorities() -> None:
    candidate = _row(
        "row-candidate-complete",
        ProtocolControlMatrixSourceKind.REQUIRED_PROCEDURE,
        unit_id="su-procedure",
        span_id="span-procedure",
        excerpt="筛选期完成检查",
        ordinal=1,
        candidate_id="candidate:procedure-01",
    )
    candidate_matrix = ProtocolControlMatrix(
        matrix_id="matrix:candidate",
        protocol_version_id="protocol:matrix",
        protocol_document_sha256=_SHA,
        selected_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:matrix",
        coverage_manifest_id="manifest:matrix",
        title_zh="候选身份盲前矩阵",
        rows=[candidate],
    )
    assert validate_protocol_control_matrix(
        candidate_matrix,
        _manifest(procedure_candidate_id="candidate:procedure-01"),
    ) is candidate_matrix
    complete_payload = candidate_matrix.model_dump(mode="python")
    complete_payload["claims_complete"] = True
    with pytest.raises(ValidationError, match="claims_complete=true"):
        ProtocolControlMatrix.model_validate(complete_payload)

    complete_candidate = candidate_matrix.model_copy(update={"claims_complete": True})
    with pytest.raises(ValueError, match="CANDIDATE_ID_NOT_COMPLETE"):
        validate_protocol_control_matrix(
            complete_candidate,
            _manifest(procedure_candidate_id="candidate:procedure-01"),
        )

    complete_formal = _matrix().model_copy(update={"claims_complete": True})
    with pytest.raises(ValueError, match="PROCEDURE_AUTHORITY_REQUIRED"):
        validate_protocol_control_matrix(complete_formal, _manifest())
    with pytest.raises(ValueError, match="PROTOCOL_CONTROL_AUTHORITY_REQUIRED"):
        validate_protocol_control_matrix(
            complete_formal,
            _manifest(),
            required_procedure_ids=["proc-01"],
        )
    assert validate_protocol_control_matrix(
        complete_formal,
        _manifest(),
        official_parent_codes=["IN-01"],
        required_procedure_ids=["proc-01"],
        protocol_controls=[_other_control()],
    ) is complete_formal


def test_candidate_identity_is_hidden_from_markdown_but_retained_in_json_and_order_check() -> None:
    candidate = _row(
        "row-candidate-visible",
        ProtocolControlMatrixSourceKind.OTHER_SECTION_CONTROL,
        unit_id="su-other",
        span_id="span-other",
        excerpt="首次给药前核对禁用治疗",
        ordinal=1,
        candidate_id="candidate-other",
    )
    matrix = ProtocolControlMatrix(
        matrix_id="matrix:candidate-visible",
        protocol_version_id="protocol:matrix",
        protocol_document_sha256=_SHA,
        selected_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:matrix",
        coverage_manifest_id="manifest:matrix",
        title_zh="候选身份可见层隔离",
        rows=[candidate],
    )
    assert validate_protocol_control_matrix(matrix, _manifest()) is matrix
    json_payload = build_protocol_control_matrix_json(matrix)
    markdown = render_protocol_control_matrix_markdown(matrix)
    visible = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
    assert '"source_candidate_id":"candidate-other"' in json_payload
    assert "candidate-other" not in visible
    for field_name in (
        "source_candidate_id",
        "candidate_identity",
        "candidate_id",
        "protocol_control_id",
    ):
        assert field_name not in visible
    assert validate_protocol_control_matrix_serializations(
        matrix, json_payload, markdown
    ) is matrix
    tampered_marker = markdown.replace(
        '"source_candidate_id":"candidate-other"',
        '"source_candidate_id":"candidate-other-tampered"',
        1,
    )
    with pytest.raises(ValueError, match="MARKDOWN_ROW_IDENTITY_MISMATCH"):
        validate_protocol_control_matrix_serializations(matrix, json_payload, tampered_marker)
