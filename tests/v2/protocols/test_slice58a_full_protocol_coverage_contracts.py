"""Slice 5.8a 全方案结构单元覆盖合同与确定性清单反例。

通用夹具（无真实方案/生产写路径）证明：

- 未处置单元不得宣称全文覆盖完整；
- 伪官方编号（CTRL/REQ/新 IN·EX）被拒绝；
- 发布控制来源越界被拒绝；
- 空义务集与不明确节点作用被拒绝；
- 输入闭包收紧后：投影外 UNKNOWN/MIXED 正文仍入清单、关键词未命中不消失、
  表格行保留全成员/全路径/全来源片段、正文缺期别图块失败、
  脚注/尾注/文本框可 UNKNOWN 但须显式来源片段、多级标题路径保留父子层级。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import (
    ApplicabilityGranularity,
    DocumentPart,
    PhaseScope,
    ReviewStage,
    StudyPhase,
)
from app.domain.contracts.protocol_controls import (
    ControlCandidateAction,
    ControlCrossSourceRelation,
    ControlMinimumEvidence,
    ControlObligationAtom,
    ControlObligationKind,
    ControlRelationTargetKind,
    CrossSourceRelationKind,
    ProtocolControlCandidate,
    ProtocolControlCandidateDisposition,
    ProtocolReviewControl,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    PublishedProtocolControlCatalog,
    ReviewNodeBinding,
    ReviewNodeRole,
    StructureUnitDisposition,
    StructureUnitDispositionKind,
    StructureUnitKind,
    TableCellContext,
    is_forbidden_protocol_control_code,
    protocol_control_display_label,
)
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityBlock,
    PhaseApplicabilityGraph,
    PhaseProjection,
)
from app.protocols.docx_structure import BlockKind, NumberingRef, StructureBlock
from app.protocols.full_protocol_coverage import (
    FullProtocolCoverageError,
    build_full_protocol_coverage_manifest,
)

_SHA = "a" * 64
_SNAPSHOT = "snap:slice58a"
_GRAPH = "graph:slice58a"
_PROTOCOL = "protocol:slice58a-v1"
_PROJECTION = "projection:phase_ii"


# ---------------------------------------------------------------------------
# 通用夹具
# ---------------------------------------------------------------------------


def _para(
    order: int,
    ref: str,
    text: str,
    *,
    part: DocumentPart = DocumentPart.BODY,
    style: str | None = None,
    style_name: str | None = None,
    outline_level: int | None = None,
    numbering: NumberingRef | None = None,
    table_path: tuple[int, ...] | None = None,
) -> StructureBlock:
    return StructureBlock(
        source_ref=ref,
        document_part=part,
        section_index=0,
        block_order=order,
        kind=BlockKind.PARAGRAPH,
        text=text,
        style=style,
        style_name=style_name,
        outline_level=outline_level,
        numbering=numbering,
        table_path=table_path,
    )


def _phase_block(
    block: StructureBlock,
    *,
    scopes: list[PhaseScope],
    span_ids: list[str] | None = None,
) -> PhaseApplicabilityBlock:
    return PhaseApplicabilityBlock(
        block_id=f"phase:{block.source_ref}",
        snapshot_id=_SNAPSHOT,
        source_ref=block.source_ref,
        source_span_ids=span_ids or [f"span:{block.source_ref}"],
        granularity=ApplicabilityGranularity.PARAGRAPH,
        source_order=block.block_order,
        text=block.text,
        phase_scopes=scopes,
        table_path=block.table_path,
    )


def _graph(blocks: list[PhaseApplicabilityBlock]) -> PhaseApplicabilityGraph:
    scopes = sorted(
        {scope for block in blocks for scope in block.phase_scopes},
        key=lambda item: item.value,
    )
    return PhaseApplicabilityGraph(
        graph_id=_GRAPH,
        snapshot_id=_SNAPSHOT,
        blocks=blocks,
        detected_phase_scopes=scopes or [PhaseScope.SHARED],
    )


def _projection(
    blocks: list[PhaseApplicabilityBlock],
    *,
    phase: StudyPhase = StudyPhase.PHASE_II,
) -> PhaseProjection:
    return PhaseProjection(
        projection_id=_PROJECTION,
        graph_id=_GRAPH,
        selected_phase=phase,
        blocks=blocks,
    )


def _unit(
    *,
    unit_id: str = "su-body-1",
    source_ref: str = "body.p1",
    source_order: int = 0,
    kind: StructureUnitKind = StructureUnitKind.PARAGRAPH,
    heading_path: list[str] | None = None,
    table_context: TableCellContext | None = None,
    is_footnote_or_note: bool = False,
    phase_scopes: list[PhaseScope] | None = None,
    excerpt: str = "基线前完成知情同意",
    member_source_refs: list[str] | None = None,
    source_span_ids: list[str] | None = None,
) -> ProtocolStructureUnit:
    members = member_source_refs or [source_ref]
    spans = source_span_ids or [f"span:{ref}" for ref in members]
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=source_ref,
        member_source_refs=sorted(members),
        source_span_ids=sorted(spans),
        unit_kind=kind,
        heading_path=heading_path or ["入选标准"],
        table_context=table_context,
        is_footnote_or_note=is_footnote_or_note,
        source_order=source_order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=phase_scopes or [PhaseScope.SHARED],
        excerpt=excerpt,
    )


def _obligation(obligation_id: str = "ob-1") -> ControlObligationAtom:
    return ControlObligationAtom(
        obligation_id=obligation_id,
        kind=ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
        statement="首次给药前 4 周内不得使用禁用药物",
    )


def _node_binding(
    *,
    stage_id: str = "stage:screening",
    role: ReviewNodeRole = ReviewNodeRole.EARLY_ATTENTION,
) -> ReviewNodeBinding:
    return ReviewNodeBinding(
        workflow_stage_id=stage_id,
        review_stage=ReviewStage.SCREENING,
        role=role,
        guidance="筛选时提前关注洗脱期不足风险",
    )


def _evidence(evidence_key: str = "ev:washout-med") -> ControlMinimumEvidence:
    return ControlMinimumEvidence(
        evidence_key=evidence_key,
        fact_type="medication_exposure",
        description="用药史或医嘱记录",
        due_stage=ReviewStage.BASELINE,
        required_source_types=["用药记录"],
    )


def _published_control(
    *,
    control_id: str = "pc-washout-01",
    ordinal: int = 1,
    source_span_ids: list[str] | None = None,
    obligations: list[ControlObligationAtom] | None = None,
    bindings: list[ReviewNodeBinding] | None = None,
    relations: list[ControlCrossSourceRelation] | None = None,
) -> ProtocolReviewControl:
    return ProtocolReviewControl(
        protocol_control_id=control_id,
        display_ordinal=ordinal,
        protocol_version_id=_PROTOCOL,
        study_phase=StudyPhase.PHASE_II,
        title="禁用合并用药洗脱",
        applicable_population="全部拟入组受试者",
        obligations=obligations if obligations is not None else [_obligation()],
        review_node_bindings=bindings if bindings is not None else [_node_binding()],
        minimum_evidence=[_evidence()],
        source_span_ids=source_span_ids or ["span:body.p1"],
        source_structure_unit_ids=["su-body-1"],
        cross_source_relations=relations or [],
    )


def _coverage_fixture_blocks() -> dict[str, StructureBlock]:
    """多级标题 + 共享正文 + UNKNOWN/MIXED 正文 + 表格行 + 脚注/文本框。"""

    return {
        # Numeric style IDs and Chinese names mirror the real DOCX shape; the
        # outline level, not the style text, is the heading contract.
        "h1": _para(
            0,
            "body.p0",
            "5 试验设计",
            style="114",
            style_name="中文自定义一级标题",
            outline_level=0,
        ),
        "h2": _para(
            1,
            "body.p1",
            "5.1 合并用药",
            style="116",
            style_name="中文自定义二级标题",
            outline_level=1,
        ),
        "shared": _para(2, "body.p2", "共享期别：基线前完成知情同意。"),
        "unknown": _para(3, "body.p3", "期别未明正文：复测规则待确认。"),
        "mixed": _para(4, "body.p4", "混合期别正文：II/III 对照表述并存。"),
        "nohit": _para(5, "body.p5", "行政说明：本段不含优先级关键词。"),
        "t00": _para(
            10,
            "body.t0.r0.c0.p0",
            "禁用药物",
            table_path=(0, 0),
        ),
        "t01": _para(
            11,
            "body.t0.r0.c1.p0",
            "时间窗",
            table_path=(0, 1),
        ),
        "t10": _para(
            12,
            "body.t0.r1.c0.p0",
            "甲氨蝶呤",
            table_path=(1, 0),
        ),
        "t11": _para(
            13,
            "body.t0.r1.c1.p0",
            "首次给药前 4 周",
            table_path=(1, 1),
        ),
        "fn": _para(
            20,
            "footnote.p0",
            "注：脚注补充洗脱例外。",
            part=DocumentPart.FOOTNOTE,
        ),
        "tb": _para(
            21,
            "textbox.p0",
            "文本框补充：需专业评估。",
            part=DocumentPart.TEXTBOX,
        ),
    }


def _build_coverage_inputs(
    *,
    include_unknown_mixed_in_graph: bool = True,
    omit_body_from_graph: StructureBlock | None = None,
    footnote_in_graph: bool = False,
):
    blocks_map = _coverage_fixture_blocks()
    structure_blocks = list(blocks_map.values())
    structure_blocks.insert(
        0,
        StructureBlock(
            source_ref="body.t0",
            document_part=DocumentPart.BODY,
            section_index=0,
            block_order=9,
            kind=BlockKind.TABLE,
            text="",
            table_rows=2,
            table_cols=2,
        ),
    )

    body_for_graph = [
        blocks_map["h1"],
        blocks_map["h2"],
        blocks_map["shared"],
        blocks_map["nohit"],
        blocks_map["t00"],
        blocks_map["t01"],
        blocks_map["t10"],
        blocks_map["t11"],
    ]
    phase_blocks: list[PhaseApplicabilityBlock] = [
        _phase_block(block, scopes=[PhaseScope.SHARED]) for block in body_for_graph
    ]
    if include_unknown_mixed_in_graph:
        phase_blocks.append(
            _phase_block(blocks_map["unknown"], scopes=[PhaseScope.UNKNOWN])
        )
        phase_blocks.append(
            _phase_block(blocks_map["mixed"], scopes=[PhaseScope.MIXED])
        )
    if omit_body_from_graph is not None:
        phase_blocks = [
            item
            for item in phase_blocks
            if item.source_ref != omit_body_from_graph.source_ref
        ]
    if footnote_in_graph:
        phase_blocks.append(
            _phase_block(blocks_map["fn"], scopes=[PhaseScope.UNKNOWN])
        )

    graph = _graph(phase_blocks)
    # 单期投影只能含非模糊块；UNKNOWN/MIXED 故意留在投影外。
    projected = [
        item
        for item in phase_blocks
        if set(item.phase_scopes).isdisjoint({PhaseScope.UNKNOWN, PhaseScope.MIXED})
    ]
    projection = _projection(projected)
    return structure_blocks, graph, projection, blocks_map


def _build_table_scope_inputs(
    rows: list[list[list[PhaseScope]]],
    *,
    cross_phase_cells: set[tuple[int, int]] | None = None,
) -> tuple[list[StructureBlock], PhaseApplicabilityGraph, PhaseProjection]:
    """Build a table whose member scopes exercise row aggregation boundaries."""

    cross_phase_cells = cross_phase_cells or set()
    table_root = StructureBlock(
        source_ref="body.t9",
        document_part=DocumentPart.BODY,
        section_index=0,
        block_order=1,
        kind=BlockKind.TABLE,
        text="",
        table_rows=len(rows),
        table_cols=max(len(row) for row in rows),
    )
    context_block = _para(0, "body.p0", "共享上下文")
    blocks = [context_block, table_root]
    phase_blocks = [_phase_block(context_block, scopes=[PhaseScope.SHARED])]
    order = 2
    for row_index, row in enumerate(rows):
        for column_index, scopes in enumerate(row):
            block = _para(
                order,
                f"body.t9.r{row_index}.c{column_index}.p0",
                f"r{row_index}c{column_index}",
                table_path=(row_index, column_index),
            )
            phase_block = _phase_block(block, scopes=scopes)
            if (row_index, column_index) in cross_phase_cells:
                phase_block = phase_block.model_copy(
                    update={"cross_phase_comparison": True}
                )
            blocks.append(block)
            phase_blocks.append(phase_block)
            order += 1

    graph = _graph(phase_blocks)
    projected = [
        item
        for item in phase_blocks
        if tuple(item.phase_scopes)
        in {(PhaseScope.PHASE_II,), (PhaseScope.SHARED,)}
    ]
    return blocks, graph, _projection(projected)


# ---------------------------------------------------------------------------
# 合同反例：未处置、伪官方编号、来源越界、空义务、节点作用
# ---------------------------------------------------------------------------


def test_claims_full_coverage_rejects_undisposed_units() -> None:
    unit = _unit()
    with pytest.raises(ValidationError, match="未处置结构单元"):
        ProtocolSectionCoverageManifest(
            manifest_id="man-1",
            protocol_version_id=_PROTOCOL,
            protocol_document_sha256=_SHA,
            study_phase=StudyPhase.PHASE_II,
            snapshot_id=_SNAPSHOT,
            units=[unit],
            dispositions=[],
            claims_full_coverage=True,
        )


def test_claims_full_coverage_accepts_when_every_unit_disposed() -> None:
    unit = _unit()
    manifest = ProtocolSectionCoverageManifest(
        manifest_id="man-1",
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id=_SNAPSHOT,
        units=[unit],
        dispositions=[
            StructureUnitDisposition(
                structure_unit_id=unit.structure_unit_id,
                disposition=StructureUnitDispositionKind.PENDING_CONFIRMATION,
            )
        ],
        claims_full_coverage=True,
    )
    assert manifest.undisposed_structure_unit_ids == []


@pytest.mark.parametrize(
    "code",
    ["CTRL-01", "CTRL_1", "REQ-12", "req 3", "IN-01", "EX-99", "in-02"],
)
def test_forbidden_pseudo_official_control_codes(code: str) -> None:
    assert is_forbidden_protocol_control_code(code)
    with pytest.raises(ValidationError, match="伪官方或官方编号"):
        _published_control(control_id=code)
    with pytest.raises(ValidationError, match="伪官方或官方编号"):
        ProtocolControlCandidate(
            control_candidate_id=code,
            protocol_version_id=_PROTOCOL,
            study_phase=StudyPhase.PHASE_II,
            frozen_structure_unit_ids=["su-body-1"],
            title="候选",
            source_span_ids=["span:body.p1"],
        )


def test_display_label_is_ordinal_not_official_code() -> None:
    assert protocol_control_display_label(1) == "方案控制 01"
    assert not is_forbidden_protocol_control_code(protocol_control_display_label(1))
    control = _published_control()
    assert control.display_label == "方案控制 01"


def test_disposition_rejects_non_official_linked_codes() -> None:
    with pytest.raises(ValidationError, match="既有官方 IN/EX"):
        StructureUnitDisposition(
            structure_unit_id="su-1",
            disposition=StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY,
            linked_official_code="REQ-01",
        )
    with pytest.raises(ValidationError, match="既有官方 IN/EX"):
        StructureUnitDisposition(
            structure_unit_id="su-1",
            disposition=StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY,
            linked_official_code="CTRL-01",
        )
    with pytest.raises(ValidationError, match="既有官方 IN/EX"):
        StructureUnitDisposition(
            structure_unit_id="su-1",
            disposition=StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY,
            linked_official_code="IN-1",
        )


def test_procedure_disposition_requires_one_formal_or_candidate_identity() -> None:
    formal = StructureUnitDisposition(
        structure_unit_id="su-procedure",
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_procedure_catalog_item_id="proc-01",
    )
    candidate = StructureUnitDisposition(
        structure_unit_id="su-procedure",
        disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        linked_procedure_candidate_id="candidate:procedure-01",
    )
    assert formal.linked_procedure_candidate_id is None
    assert candidate.linked_procedure_catalog_item_id is None

    with pytest.raises(ValidationError, match="必须且只能绑定正式流程目录身份或流程候选身份"):
        StructureUnitDisposition(
            structure_unit_id="su-procedure",
            disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
            linked_procedure_catalog_item_id="proc-01",
            linked_procedure_candidate_id="candidate:procedure-01",
        )
    with pytest.raises(ValidationError, match="仅流程必做处置可链接流程候选身份"):
        StructureUnitDisposition(
            structure_unit_id="su-other",
            disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
            linked_procedure_candidate_id="candidate:procedure-01",
        )
    with pytest.raises(ValidationError, match="仅流程必做处置可链接必做项目录项"):
        StructureUnitDisposition(
            structure_unit_id="su-other",
            disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
            linked_procedure_catalog_item_id="proc-01",
        )
    with pytest.raises(ValidationError, match="正式流程目录身份不得使用流程候选身份"):
        StructureUnitDisposition(
            structure_unit_id="su-procedure",
            disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
            linked_procedure_catalog_item_id="candidate:procedure-01",
        )
    with pytest.raises(ValidationError, match="必须且只能绑定正式流程目录身份或流程候选身份"):
        StructureUnitDisposition(
            structure_unit_id="su-procedure",
            disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
        )


@pytest.mark.parametrize("candidate_id", ["IN-01", "candidate:IN-01", "candidate:REQ-01"])
def test_procedure_candidate_identity_cannot_mimic_official_code(candidate_id: str) -> None:
    with pytest.raises(ValidationError, match="candidate"):
        StructureUnitDisposition(
            structure_unit_id="su-procedure",
            disposition=StructureUnitDispositionKind.REQUIRED_PROCEDURE,
            linked_procedure_candidate_id=candidate_id,
        )


def test_published_catalog_rejects_source_overreach() -> None:
    control = _published_control(source_span_ids=["span:body.p1", "span:outsider"])
    with pytest.raises(ValidationError, match="来源越界"):
        PublishedProtocolControlCatalog(
            catalog_id="cat-1",
            protocol_version_id=_PROTOCOL,
            protocol_document_sha256=_SHA,
            study_phase=StudyPhase.PHASE_II,
            coverage_manifest_id="man-1",
            allowed_source_span_ids=["span:body.p1"],
            controls=[control],
        )


def test_published_control_rejects_empty_obligations() -> None:
    with pytest.raises(ValidationError):
        _published_control(obligations=[])


def test_review_node_binding_rejects_missing_or_ambiguous_role() -> None:
    with pytest.raises(ValidationError):
        ReviewNodeBinding(
            workflow_stage_id="stage:screening",
            review_stage=ReviewStage.SCREENING,
            # role 省略：必须显式节点作用
        )
    with pytest.raises(ValidationError):
        ReviewNodeBinding(
            workflow_stage_id="stage:screening",
            review_stage=ReviewStage.SCREENING,
            role="maybe_later",  # type: ignore[arg-type]
        )


def test_candidate_exclude_requires_reason_and_blocks_candidate_id() -> None:
    with pytest.raises(ValidationError, match="排除理由"):
        ProtocolControlCandidateDisposition(
            disposition_id="disp-1",
            coverage_manifest_id="man-1",
            action=ControlCandidateAction.EXCLUDE,
            frozen_structure_unit_ids=["su-body-1"],
        )
    with pytest.raises(ValidationError, match="明确排除不得同时绑定"):
        ProtocolControlCandidateDisposition(
            disposition_id="disp-1",
            coverage_manifest_id="man-1",
            action=ControlCandidateAction.EXCLUDE,
            frozen_structure_unit_ids=["su-body-1"],
            control_candidate_id="pc-cand-1",
            exclude_reason="非入排控制",
        )


def test_cross_source_duplicate_requires_shared_identity() -> None:
    with pytest.raises(ValidationError, match="共享评估身份"):
        ControlCrossSourceRelation(
            relation_id="rel-1",
            kind=CrossSourceRelationKind.DUPLICATE_STATEMENT,
            left_target_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
            left_target_id="pc-washout-01",
            right_target_kind=ControlRelationTargetKind.OFFICIAL_RULE,
            right_target_id="EX-05",
        )


def test_unresolved_substantive_conflict_blocks_catalog() -> None:
    relation = ControlCrossSourceRelation(
        relation_id="rel-conflict",
        kind=CrossSourceRelationKind.SUBSTANTIVE_CONFLICT,
        left_target_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
        left_target_id="pc-washout-01",
        right_target_kind=ControlRelationTargetKind.OFFICIAL_RULE,
        right_target_id="EX-05",
        notes="时间窗冲突未裁决",
    )
    control = _published_control(relations=[relation])
    with pytest.raises(ValidationError, match="实质冲突阻断"):
        PublishedProtocolControlCatalog(
            catalog_id="cat-1",
            protocol_version_id=_PROTOCOL,
            protocol_document_sha256=_SHA,
            study_phase=StudyPhase.PHASE_II,
            coverage_manifest_id="man-1",
            allowed_source_span_ids=["span:body.p1"],
            controls=[control],
        )


# ---------------------------------------------------------------------------
# 构建器夹具：闭包收紧回归
# ---------------------------------------------------------------------------


def test_builder_keeps_unknown_mixed_and_keyword_misses_outside_projection() -> None:
    blocks, graph, projection, blocks_map = _build_coverage_inputs()
    assert all(
        item.source_ref
        not in {blocks_map["unknown"].source_ref, blocks_map["mixed"].source_ref}
        for item in projection.blocks
    )

    manifest = build_full_protocol_coverage_manifest(
        blocks,
        projection,
        graph,
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        snapshot_id=_SNAPSHOT,
        priority_keywords=["洗脱", "禁用", "知情同意"],
        source_span_ids={
            blocks_map["fn"].source_ref: "span:footnote.p0",
            blocks_map["tb"].source_ref: "span:textbox.p0",
        },
    )

    by_ref = {unit.source_ref: unit for unit in manifest.units}
    # 投影外 UNKNOWN/MIXED 正文仍须进入全文清单。
    assert blocks_map["unknown"].source_ref in by_ref
    assert blocks_map["mixed"].source_ref in by_ref
    assert PhaseScope.UNKNOWN in by_ref[blocks_map["unknown"].source_ref].phase_scopes
    assert PhaseScope.MIXED in by_ref[blocks_map["mixed"].source_ref].phase_scopes

    # 关键词未命中正文不得消失；优先级可为空。
    nohit = by_ref[blocks_map["nohit"].source_ref]
    assert nohit.priority_keyword_hits == []
    assert nohit.priority_rank == 0

    shared = by_ref[blocks_map["shared"].source_ref]
    assert "知情同意" in shared.priority_keyword_hits
    assert shared.priority_rank >= 1

    assert manifest.claims_full_coverage is False
    assert manifest.dispositions == []
    assert manifest.undisposed_structure_unit_ids == [
        unit.structure_unit_id for unit in manifest.units
    ]


def test_builder_table_row_keeps_all_members_paths_and_spans() -> None:
    blocks, graph, projection, blocks_map = _build_coverage_inputs()
    manifest = build_full_protocol_coverage_manifest(
        blocks,
        projection,
        graph,
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        snapshot_id=_SNAPSHOT,
        source_span_ids={
            blocks_map["fn"].source_ref: "span:footnote.p0",
            blocks_map["tb"].source_ref: "span:textbox.p0",
        },
    )

    row = next(
        unit
        for unit in manifest.units
        if unit.unit_kind == StructureUnitKind.TABLE_ROW
    )
    assert row.member_source_refs == sorted(
        [
            blocks_map["t10"].source_ref,
            blocks_map["t11"].source_ref,
        ]
    )
    assert row.table_context is not None
    assert set(row.table_context.member_cell_paths) == {(1, 0), (1, 1)}
    assert row.source_span_ids == sorted(
        [
            f"span:{blocks_map['t10'].source_ref}",
            f"span:{blocks_map['t11'].source_ref}",
        ]
    )
    assert "甲氨蝶呤" in row.excerpt
    assert "首次给药前 4 周" in row.excerpt
    # 不能只保留首格定位。
    assert row.source_ref == "body.t0.r1"
    assert row.table_context.member_cell_paths != [row.table_context.table_path]


def test_builder_atomizes_only_conflicting_or_composite_table_members() -> None:
    rows = [
        [[PhaseScope.UNKNOWN], [PhaseScope.UNKNOWN]],
        [[PhaseScope.PHASE_II], [PhaseScope.PHASE_II]],
        [[PhaseScope.UNKNOWN], [PhaseScope.PHASE_II]],
        [[PhaseScope.UNKNOWN], [PhaseScope.PHASE_III]],
        [[PhaseScope.UNKNOWN], [PhaseScope.SHARED]],
        [
            [PhaseScope.UNKNOWN, PhaseScope.PHASE_II],
            [PhaseScope.UNKNOWN, PhaseScope.PHASE_II],
        ],
        [[PhaseScope.SHARED], [PhaseScope.SHARED]],
        [[PhaseScope.MIXED], [PhaseScope.MIXED]],
    ]
    blocks, graph, projection = _build_table_scope_inputs(
        rows,
        cross_phase_cells={(6, 1)},
    )
    manifest = build_full_protocol_coverage_manifest(
        blocks,
        projection,
        graph,
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        snapshot_id=_SNAPSHOT,
    )

    rows_by_index: dict[int, list[ProtocolStructureUnit]] = {}
    for unit in manifest.units:
        if unit.table_context is not None:
            rows_by_index.setdefault(unit.table_context.row_index, []).append(unit)
    for row_units in rows_by_index.values():
        row_units.sort(key=lambda unit: unit.source_order)

    # Same single UNKNOWN and same explicit scope remain row aggregates.
    assert [unit.source_ref for unit in rows_by_index[0]] == ["body.t9.r0"]
    assert rows_by_index[0][0].phase_scopes == [PhaseScope.UNKNOWN]
    assert [unit.source_ref for unit in rows_by_index[1]] == ["body.t9.r1"]
    assert rows_by_index[1][0].phase_scopes == [PhaseScope.PHASE_II]

    # Different member signatures, composite member scopes, MIXED scopes, and
    # an explicit cross-phase comparison each require per-cell ownership.
    for row_index in range(2, 8):
        assert [unit.source_ref for unit in rows_by_index[row_index]] == [
            f"body.t9.r{row_index}.c0.p0",
            f"body.t9.r{row_index}.c1.p0",
        ]

    assert rows_by_index[2][0].phase_scopes == [PhaseScope.UNKNOWN]
    assert rows_by_index[2][1].phase_scopes == [PhaseScope.PHASE_II]
    assert rows_by_index[3][1].phase_scopes == [PhaseScope.PHASE_III]
    assert set(rows_by_index[4][0].phase_scopes) == {PhaseScope.UNKNOWN}
    assert set(rows_by_index[4][1].phase_scopes) == {PhaseScope.SHARED}
    assert set(rows_by_index[5][0].phase_scopes) == {
        PhaseScope.PHASE_II,
        PhaseScope.UNKNOWN,
    }
    assert rows_by_index[6][0].phase_scopes == [PhaseScope.SHARED]
    assert rows_by_index[7][0].phase_scopes == [PhaseScope.MIXED]

    expected_member_refs = {
        f"body.t9.r{row_index}.c{column_index}.p0"
        for row_index, row in enumerate(rows)
        for column_index, _scopes in enumerate(row)
    }
    owned_refs = [
        source_ref
        for row_units in rows_by_index.values()
        for unit in row_units
        for source_ref in unit.member_source_refs
    ]
    owned_spans = [
        span_id
        for row_units in rows_by_index.values()
        for unit in row_units
        for span_id in unit.source_span_ids
    ]
    assert set(owned_refs) == expected_member_refs
    assert len(owned_refs) == len(expected_member_refs)
    assert len(owned_refs) == len(set(owned_refs))
    assert len(owned_spans) == len(set(owned_spans))

    atom = rows_by_index[2][0]
    assert atom.table_context is not None
    assert atom.table_context.table_path == (2, 0)
    assert atom.table_context.row_headers == ["r2c0"]
    assert atom.table_context.column_headers == ["r0c0"]


def test_nested_table_rows_do_not_merge_with_outer_table_rows() -> None:
    blocks, graph, projection, blocks_map = _build_coverage_inputs()
    nested = StructureBlock(
        source_ref="body.t0.r1.c1.t0.r0.c0.p0",
        document_part=DocumentPart.BODY,
        block_order=95,
        kind=BlockKind.PARAGRAPH,
        text="内层表控制条件",
        table_path=(1, 1, 0, 0),
    )
    blocks = [*blocks, nested]
    nested_phase = _phase_block(nested, scopes=[PhaseScope.SHARED])
    graph = graph.model_copy(update={"blocks": [*graph.blocks, nested_phase]})
    projection = projection.model_copy(
        update={"blocks": [*projection.blocks, nested_phase]}
    )
    manifest = build_full_protocol_coverage_manifest(
        blocks,
        projection,
        graph,
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        snapshot_id=_SNAPSHOT,
        source_span_ids={
            blocks_map["fn"].source_ref: "span:footnote.p0",
            blocks_map["tb"].source_ref: "span:textbox.p0",
        },
    )
    rows = {unit.source_ref: unit for unit in manifest.units if unit.table_context}
    assert "body.t0.r1" in rows
    assert "body.t0.r1.c1.t0.r0" in rows
    assert rows["body.t0.r1"].member_source_refs == sorted(
        [blocks_map["t10"].source_ref, blocks_map["t11"].source_ref]
    )
    assert rows["body.t0.r1.c1.t0.r0"].member_source_refs == [nested.source_ref]


def test_builder_fails_when_body_missing_from_phase_graph() -> None:
    blocks, graph, projection, blocks_map = _build_coverage_inputs(
        omit_body_from_graph=_coverage_fixture_blocks()["nohit"]
    )
    with pytest.raises(FullProtocolCoverageError, match="期别适用图外结构单元"):
        build_full_protocol_coverage_manifest(
            blocks,
            projection,
            graph,
            protocol_version_id=_PROTOCOL,
            protocol_document_sha256=_SHA,
            snapshot_id=_SNAPSHOT,
            source_span_ids={
                blocks_map["fn"].source_ref: "span:footnote.p0",
                blocks_map["tb"].source_ref: "span:textbox.p0",
            },
        )


def test_builder_allows_footnote_textbox_unknown_with_explicit_spans() -> None:
    blocks, graph, projection, blocks_map = _build_coverage_inputs()
    # 脚注/文本框不在期别图内：必须显式来源片段，并标记 UNKNOWN。
    manifest = build_full_protocol_coverage_manifest(
        blocks,
        projection,
        graph,
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        snapshot_id=_SNAPSHOT,
        source_span_ids={
            blocks_map["fn"].source_ref: ["span:footnote.p0"],
            blocks_map["tb"].source_ref: ["span:textbox.p0"],
        },
    )
    by_ref = {unit.source_ref: unit for unit in manifest.units}
    footnote = by_ref[blocks_map["fn"].source_ref]
    textbox = by_ref[blocks_map["tb"].source_ref]
    assert footnote.unit_kind == StructureUnitKind.FOOTNOTE_OR_ANNOTATION
    assert footnote.is_footnote_or_note is True
    assert footnote.source_span_ids == ["span:footnote.p0"]
    assert PhaseScope.UNKNOWN in footnote.phase_scopes
    assert textbox.source_span_ids == ["span:textbox.p0"]
    assert PhaseScope.UNKNOWN in textbox.phase_scopes

    with pytest.raises(FullProtocolCoverageError, match="必须显式提供来源片段"):
        build_full_protocol_coverage_manifest(
            blocks,
            projection,
            graph,
            protocol_version_id=_PROTOCOL,
            protocol_document_sha256=_SHA,
            snapshot_id=_SNAPSHOT,
            source_span_ids={
                # 故意漏掉脚注来源片段
                blocks_map["tb"].source_ref: "span:textbox.p0",
            },
        )


def test_builder_preserves_nested_heading_path() -> None:
    blocks, graph, projection, blocks_map = _build_coverage_inputs()
    manifest = build_full_protocol_coverage_manifest(
        blocks,
        projection,
        graph,
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        snapshot_id=_SNAPSHOT,
        source_span_ids={
            blocks_map["fn"].source_ref: "span:footnote.p0",
            blocks_map["tb"].source_ref: "span:textbox.p0",
        },
    )
    shared = next(
        unit
        for unit in manifest.units
        if unit.source_ref == blocks_map["shared"].source_ref
    )
    assert shared.heading_path == ["5 试验设计", "5.1 合并用药"]

    h2 = next(
        unit
        for unit in manifest.units
        if unit.source_ref == blocks_map["h2"].source_ref
    )
    assert h2.heading_path == ["5 试验设计", "5.1 合并用药"]


def test_builder_uses_outline_for_custom_headings_and_table_title_context() -> None:
    blocks, graph, projection, blocks_map = _build_coverage_inputs()
    # A numbered paragraph can look like a chapter in extracted text.  It has
    # no structural outline level, so it must remain a list item and must not
    # replace the preceding custom-style heading path.
    numbered = _para(
        6,
        "body.p6",
        "1. 这是编号列表项，不是章节标题",
        style="Heading 3",
        numbering=NumberingRef(num_id=7, level=0),
    )
    table_title = _para(8, "body.p8", "表 7 研究流程与检查项目")
    blocks.extend([numbered, table_title])
    numbered_phase = _phase_block(numbered, scopes=[PhaseScope.SHARED])
    title_phase = _phase_block(table_title, scopes=[PhaseScope.SHARED])
    graph = graph.model_copy(update={"blocks": [*graph.blocks, numbered_phase, title_phase]})
    projection = projection.model_copy(
        update={"blocks": [*projection.blocks, numbered_phase, title_phase]}
    )

    manifest = build_full_protocol_coverage_manifest(
        blocks,
        projection,
        graph,
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        snapshot_id=_SNAPSHOT,
        source_span_ids={
            blocks_map["fn"].source_ref: "span:footnote.p0",
            blocks_map["tb"].source_ref: "span:textbox.p0",
        },
    )
    by_ref = {unit.source_ref: unit for unit in manifest.units}

    assert by_ref["body.p6"].unit_kind == StructureUnitKind.LIST_ITEM
    assert by_ref["body.p6"].heading_path == [
        "5 试验设计",
        "5.1 合并用药",
    ]
    assert by_ref["body.p8"].heading_path == [
        "5 试验设计",
        "5.1 合并用药",
    ]
    assert by_ref["body.t0.r1"].heading_path == [
        "5 试验设计",
        "5.1 合并用药",
        "表 7 研究流程与检查项目",
    ]


def test_builder_body_span_override_cannot_hide_phase_graph_omission() -> None:
    omitted = _coverage_fixture_blocks()["nohit"]
    blocks, graph, projection, blocks_map = _build_coverage_inputs(
        omit_body_from_graph=omitted
    )
    with pytest.raises(FullProtocolCoverageError, match="期别适用图外结构单元"):
        build_full_protocol_coverage_manifest(
            blocks,
            projection,
            graph,
            protocol_version_id=_PROTOCOL,
            protocol_document_sha256=_SHA,
            snapshot_id=_SNAPSHOT,
            source_span_ids={
                omitted.source_ref: "span:override-body-nohit",
                blocks_map["fn"].source_ref: "span:footnote.p0",
                blocks_map["tb"].source_ref: "span:textbox.p0",
            },
        )
