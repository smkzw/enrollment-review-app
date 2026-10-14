"""范围候选发现（``app/protocols/review_scope.py``）的合成工程测试。

只使用合成的工程输入：真实的 ``ProtocolDeconstructionInput`` /
``StructureBlock`` / ``ProtocolSourceSpan`` 契约，不依赖数据库、临床资料、
模型调用或已退役的完整解构链。
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.domain.contracts.agent_io import (
    ProtocolDeconstructionInput,
    ProtocolSourceMaterial,
)
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import (
    AlignmentStatus,
    CatalogItemKind,
    CatalogKind,
    DatePrecision,
    DocumentPart,
    MetadataResolutionStatus,
    ReviewStage,
    SourceLocatorPrecision,
    StudyPhase,
)
from app.domain.contracts.protocol_ingestion import (
    FrozenCatalogItem,
    FrozenProtocolCatalog,
    ProtocolSourceSpan,
)
from app.domain.contracts.protocol_metadata import (
    ProtocolIdentityDecision,
    StudyPhaseSelection,
)
from app.domain.publication import canonical_hash
from app.protocols.docx_structure import BlockKind, NumberingRef, StructureBlock
from app.protocols.review_scope import (
    ReviewScopeKind,
    ScopeDiagnosticKind,
    discover_review_scope,
)

NOW = datetime(2026, 10, 15, tzinfo=timezone.utc)
SHA = "c" * 64
SNAPSHOT = "snapshot-synthetic-scope"
OTHER_SNAPSHOT = "snapshot-other-protocol"


# ---------------------------------------------------------------------------
# 合成夹具
# ---------------------------------------------------------------------------


def _catalog(kind: CatalogKind, items: list[FrozenCatalogItem]) -> FrozenProtocolCatalog:
    payload = {
        "catalog_id": f"catalog:{kind.value}",
        "snapshot_id": SNAPSHOT,
        "catalog_kind": kind,
        "study_phase": StudyPhase.PHASE_II,
        "items": tuple(items),
        "frozen_at": NOW,
        "frozen_by": "synthetic_review_scope_fixture/v1",
    }
    unhashed = FrozenProtocolCatalog.model_construct(**payload, catalog_sha256="0" * 64)
    payload["catalog_sha256"] = canonical_hash(
        unhashed.model_dump(mode="json", exclude={"catalog_sha256"})
    )
    return FrozenProtocolCatalog(**payload)


def _parent_item(
    item_id: str, code: str, label: str, position: int, span_ids: tuple[str, ...]
) -> FrozenCatalogItem:
    return FrozenCatalogItem(
        item_id=item_id,
        kind=CatalogItemKind.PARENT_RULE,
        official_code=code,
        label=label,
        position=position,
        source_span_ids=span_ids,
    )


def _procedure_item(
    item_id: str,
    label: str,
    position: int,
    span_ids: tuple[str, ...],
    *,
    visit: str = "筛选期 D-28~D-1",
    stage: ReviewStage = ReviewStage.SCREENING,
) -> FrozenCatalogItem:
    return FrozenCatalogItem(
        item_id=item_id,
        kind=CatalogItemKind.REQUIRED_PROCEDURE,
        label=label,
        visit_instance=visit,
        review_stage=stage,
        position=position,
        source_span_ids=span_ids,
    )


def _material(span_id: str, source_ref: str, order: int, text: str) -> ProtocolSourceMaterial:
    return ProtocolSourceMaterial(
        source_span_id=span_id,
        source_ref=source_ref,
        block_order=order,
        text=text,
    )


def _source_input(
    *,
    parent_items: list[FrozenCatalogItem],
    materials: list[ProtocolSourceMaterial],
    procedure_items: list[FrozenCatalogItem] | None = None,
) -> ProtocolDeconstructionInput:
    if procedure_items is None:
        procedure_items = [
            _procedure_item("procedure:scope:default", "常规检查", 0, ("span-proc",))
        ]
    known = {item.source_span_id for item in materials}
    materials = list(materials)
    for item in procedure_items:
        for span_id in item.source_span_ids:
            if span_id not in known:
                materials.append(
                    _material(span_id, f"body.auto.{span_id}", 900, "筛选期常规检查项目")
                )
                known.add(span_id)
    identity = ProtocolIdentityDecision(
        identity_decision_id="identity-scope",
        snapshot_id=SNAPSHOT,
        project_name="合成范围核验",
        project_code="SYNTH",
        protocol_code="SYNTH-001",
        official_version="V1.0",
        official_date=DateValue(value=date(2026, 10, 15), precision=DatePrecision.DAY),
        study_phase=StudyPhase.PHASE_II,
        selected_candidate_ids=["candidate-scope"],
        status=MetadataResolutionStatus.CONFIRMED,
        confirmation_required=False,
        confirmed_by="synthetic",
        confirmed_at=NOW,
    )
    selection = StudyPhaseSelection(
        selection_id="phase-selection-scope",
        snapshot_id=SNAPSHOT,
        selected_phase=StudyPhase.PHASE_II,
        candidate_ids=["phase-candidate-scope"],
        status=MetadataResolutionStatus.CONFIRMED,
        confirmed_by="synthetic",
        confirmed_at=NOW,
    )
    material_ids = [item.source_span_id for item in materials]
    return ProtocolDeconstructionInput(
        project_id="project-scope",
        protocol_version_id="protocol-version-scope",
        protocol_file_sha256=SHA,
        extraction_snapshot_id=SNAPSHOT,
        phase_projection_id="projection-scope",
        selected_phase=StudyPhase.PHASE_II,
        identity_decision=identity,
        phase_selection=selection,
        allowed_source_span_ids=material_ids,
        source_materials=materials,
        parent_rule_catalog=_catalog(CatalogKind.OFFICIAL_PARENT_RULES, parent_items),
        required_procedure_catalog=_catalog(
            CatalogKind.REQUIRED_PROCEDURES, procedure_items
        ),
    )


def _para(
    order: int,
    ref: str,
    text: str,
    *,
    level: int | None = None,
    style: str | None = None,
    table_path: tuple[int, ...] | None = None,
) -> StructureBlock:
    return StructureBlock(
        source_ref=ref,
        document_part=DocumentPart.BODY,
        block_order=order,
        kind=BlockKind.PARAGRAPH,
        text=text,
        style_name=style,
        outline_level=level,
        table_path=table_path,
    )


def _table(order: int, ref: str, *, table_path: tuple[int, ...] | None = None) -> StructureBlock:
    return StructureBlock(
        source_ref=ref,
        document_part=DocumentPart.BODY,
        block_order=order,
        kind=BlockKind.TABLE,
        text="",
        table_path=table_path,
    )


def _span(
    span_id: str,
    ref: str,
    order: int,
    *,
    snapshot: str = SNAPSHOT,
    excerpt: str | None = None,
) -> ProtocolSourceSpan:
    if excerpt is None:
        return ProtocolSourceSpan(
            source_span_id=span_id,
            snapshot_id=snapshot,
            source_ref=ref,
            document_part=DocumentPart.BODY,
            block_order=order,
            precision=SourceLocatorPrecision.BLOCK,
            alignment_status=AlignmentStatus.ALIGNED,
        )
    return ProtocolSourceSpan(
        source_span_id=span_id,
        snapshot_id=snapshot,
        source_ref=ref,
        document_part=DocumentPart.BODY,
        block_order=order,
        precision=SourceLocatorPrecision.PAGE_EXCERPT,
        excerpt=excerpt,
        alignment_status=AlignmentStatus.ALIGNED,
    )


def _of_kind(result, kind: ReviewScopeKind):
    return [item for item in result.candidates if item.scope_kind is kind]


def _diagnostics_of(result, kind: ScopeDiagnosticKind):
    return [item for item in result.diagnostics if item.kind is kind]


# ---------------------------------------------------------------------------
# S1 官方条款原文
# ---------------------------------------------------------------------------


def test_s1_candidates_come_from_frozen_official_catalog_only():
    source_input = _source_input(
        parent_items=[
            _parent_item("parent:in01", "IN-01", "年龄要求", 0, ("span-in01",)),
            _parent_item("parent:ex01", "EX-01", "肝功能阈值", 1, ("span-ex01",)),
        ],
        materials=[
            _material("span-in01", "body.p1", 0, "年龄≥18岁。"),
            _material("span-ex01", "body.p2", 1, "ALT或AST≥1.5×ULN。"),
        ],
    )
    # 正文块含规则样文字，但不是目录成员，不得成为 S1 来源。
    blocks = [
        _para(0, "body.p1", "年龄≥18岁。"),
        _para(1, "body.p2", "ALT或AST≥1.5×ULN。"),
        _para(2, "body.p3", "模型式草稿：IN-99 年龄不限。"),
    ]
    spans = [_span("span-in01", "body.p1", 0), _span("span-ex01", "body.p2", 1)]

    result = discover_review_scope(
        source_input=source_input, blocks=blocks, source_spans=spans
    )

    official = _of_kind(result, ReviewScopeKind.OFFICIAL_RULE_TEXT)
    assert [item.official_codes for item in official] == [("IN-01",), ("EX-01",)]
    assert [item.label for item in official] == ["年龄要求", "肝功能阈值"]
    assert [item.source_span_ids for item in official] == [("span-in01",), ("span-ex01",)]
    assert [item.block_source_refs for item in official] == [(), ()]
    records = {item.source_span_id: item for item in result.source_records}
    assert records["span-in01"].raw_text == "年龄≥18岁。"
    assert records["span-in01"].roles == (ReviewScopeKind.OFFICIAL_RULE_TEXT,)
    assert records["span-in01"].identity_status == "ok"
    assert result.clinical_adoption_applied is False
    assert all(item.clinically_confirmed is False for item in result.candidates)
    assert "body.p3" not in {
        ref for item in result.candidates for ref in item.block_source_refs
    }


# ---------------------------------------------------------------------------
# S3 冻结必做项目录
# ---------------------------------------------------------------------------


def test_s3_candidates_come_from_frozen_procedure_catalog_not_visit_table():
    source_input = _source_input(
        parent_items=[_parent_item("parent:in01", "IN-01", "年龄要求", 0, ("span-in01",))],
        materials=[_material("span-in01", "body.p1", 0, "年龄≥18岁。")],
        procedure_items=[
            _procedure_item("procedure:scr:blood", "血常规", 0, ("span-proc-1",)),
            _procedure_item(
                "procedure:base:ecg",
                "心电图",
                1,
                ("span-proc-2",),
                visit="基线",
                stage=ReviewStage.BASELINE,
            ),
        ],
    )
    # 流程表结构块存在，但目录只冻结了筛查期血常规与基线心电图。
    blocks = [
        _para(0, "body.soa", "研究流程表", level=1),
        _table(1, "body.t0"),
        _para(2, "body.t0.r0.c0.p0", "访视", table_path=(0, 0)),
        _para(3, "body.t0.r0.c1.p0", "筛选期", table_path=(0, 1)),
        _para(4, "body.t0.r0.c2.p0", "W12 随访", table_path=(0, 2)),
    ]

    result = discover_review_scope(source_input=source_input, blocks=blocks, source_spans=[])

    procedures = _of_kind(result, ReviewScopeKind.REQUIRED_PROCEDURE)
    assert [item.label for item in procedures] == ["血常规", "心电图"]
    assert [item.visit_instance for item in procedures] == ["筛选期 D-28~D-1", "基线"]
    assert [item.review_stage for item in procedures] == [
        ReviewStage.SCREENING,
        ReviewStage.BASELINE,
    ]
    assert [item.source_span_ids for item in procedures] == [("span-proc-1",), ("span-proc-2",)]
    assert all(item.block_source_refs == () for item in procedures)
    assert not _of_kind(result, ReviewScopeKind.MEDICATION_SECTION)


# ---------------------------------------------------------------------------
# S2 引用解析
# ---------------------------------------------------------------------------


def test_s2_arabic_section_reference_resolves_to_bounded_subtree():
    source_input = _source_input(
        parent_items=[_parent_item("parent:in01", "IN-01", "用药限制", 0, ("span-in01",))],
        materials=[_material("span-in01", "body.p1", 0, "筛选期用药：见第 9.2 节所列药物。")],
    )
    blocks = [
        _para(0, "body.h8", "8 研究设计", level=0),
        _para(1, "body.s92", "9.2 合并用药与治疗", level=1),
        _para(2, "body.s92.p1", "受试者不得使用下列药物。"),
        _para(3, "body.s92.p2", "具体清单由研究者确认。"),
        _para(4, "body.h10", "10 安全性评估", level=1),
        _para(5, "body.h10.p1", "安全性评估描述。"),
    ]
    spans = [_span("span-s92", "body.s92", 1), _span("span-s92-p1", "body.s92.p1", 2)]

    result = discover_review_scope(
        source_input=source_input, blocks=blocks, source_spans=spans
    )

    referenced = _of_kind(result, ReviewScopeKind.REFERENCED_SOURCE)
    assert len(referenced) == 1
    candidate = referenced[0]
    assert candidate.identifiers == ("第 9.2 节",)
    assert candidate.official_codes == ("IN-01",)
    assert candidate.block_source_refs == ("body.s92", "body.s92.p1", "body.s92.p2")
    assert "body.h10" not in candidate.block_source_refs
    assert candidate.source_span_ids == ("span-s92", "span-s92-p1")
    assert candidate.citing_source_span_ids == ("span-in01",)
    assert candidate.discovery_reason.startswith("IN-01")
    assert candidate.clinically_confirmed is False
    assert candidate.review_stage is None


def test_s2_chinese_appendix_and_table_references_resolve():
    source_input = _source_input(
        parent_items=[_parent_item("parent:ex01", "EX-01", "避孕与检查", 0, ("span-ex01",))],
        materials=[
            _material("span-ex01", "body.p1", 0, "避孕要求详见附录三，检查范围见表二。")
        ],
    )
    blocks = [
        _para(0, "body.app3", "附录三 避孕方法", level=1),
        _para(1, "body.app3.p1", "可接受的避孕方法如下。"),
        _para(2, "body.h4", "4 检查", level=1),
        _para(3, "body.cap2", "表二 实验室检查正常值范围"),
        _table(4, "body.t0"),
        _para(5, "body.t0.r0.c0.p0", "白细胞计数 3.5-9.5", table_path=(0, 0)),
    ]
    spans = [_span("span-t0", "body.t0", 4), _span("span-app3", "body.app3", 0)]

    result = discover_review_scope(
        source_input=source_input, blocks=blocks, source_spans=spans
    )

    referenced = {
        item.identifiers[0]: item
        for item in _of_kind(result, ReviewScopeKind.REFERENCED_SOURCE)
    }
    assert set(referenced) == {"附录三", "表二"}
    assert referenced["附录三"].block_source_refs == ("body.app3", "body.app3.p1")
    assert referenced["附录三"].source_span_ids == ("span-app3",)
    assert referenced["表二"].block_source_refs == (
        "body.cap2",
        "body.t0",
        "body.t0.r0.c0.p0",
    )
    assert referenced["表二"].source_span_ids == ("span-t0",)
    assert referenced["表二"].discovery_reason.endswith("匹配表题「表二 实验室检查正常值范围」")
    assert not _diagnostics_of(result, ScopeDiagnosticKind.REFERENCE_UNRESOLVED)
    assert not _diagnostics_of(result, ScopeDiagnosticKind.REFERENCE_AMBIGUOUS)


def test_s2_external_guideline_references_are_not_bound():
    source_input = _source_input(
        parent_items=[
            _parent_item("parent:in01", "IN-01", "不良事件分级", 0, ("span-in01",)),
            _parent_item("parent:ex01", "EX-01", "药典方法", 1, ("span-ex01",)),
        ],
        materials=[
            _material("span-in01", "body.p1", 0, "不良事件严重程度按 NCI-CTCAE 5.0 第 9.2 节分级。"),
            _material("span-ex01", "body.p2", 1, "相关方法参见《中国药典》附录 3。"),
        ],
    )
    blocks = [
        _para(0, "body.s92", "9.2 分级标准", level=1),
        _para(1, "body.s92.p1", "分级标准描述。"),
        _para(2, "body.app3", "附录 3 避孕方法", level=1),
    ]

    result = discover_review_scope(source_input=source_input, blocks=blocks, source_spans=[])

    assert not _of_kind(result, ReviewScopeKind.REFERENCED_SOURCE)
    external = _diagnostics_of(result, ScopeDiagnosticKind.REFERENCE_EXTERNAL_ATTRIBUTION)
    assert {item.identifiers for item in external} == {("第 9.2 节",), ("附录 3",)}
    assert all(item.related_official_codes in {("IN-01",), ("EX-01",)} for item in external)
    assert not _diagnostics_of(result, ScopeDiagnosticKind.REFERENCE_UNRESOLVED)


def test_s2_unresolved_and_ambiguous_references_stay_explicit():
    source_input = _source_input(
        parent_items=[_parent_item("parent:in01", "IN-01", "引用检查", 0, ("span-in01",))],
        materials=[_material("span-in01", "body.p1", 0, "详见第 12.4 节与附录 5。")],
    )
    blocks = [
        _para(0, "body.app5a", "附录 5 禁用药物", level=1),
        _para(1, "body.app5a.p1", "清单如下。"),
        _para(2, "body.app5b", "附录 5 合并用药", level=1),
        _para(3, "body.app5b.p1", "清单如下。"),
    ]

    result = discover_review_scope(source_input=source_input, blocks=blocks, source_spans=[])

    assert not _of_kind(result, ReviewScopeKind.REFERENCED_SOURCE)
    unresolved = _diagnostics_of(result, ScopeDiagnosticKind.REFERENCE_UNRESOLVED)
    ambiguous = _diagnostics_of(result, ScopeDiagnosticKind.REFERENCE_AMBIGUOUS)
    assert [item.identifiers for item in unresolved] == [("第 12.4 节",)]
    assert [item.identifiers for item in ambiguous] == [("附录 5",)]
    assert ambiguous[0].source_refs == ("body.app5a", "body.app5b")
    assert ambiguous[0].related_official_codes == ("IN-01",)


# ---------------------------------------------------------------------------
# S4 用药／治疗章节
# ---------------------------------------------------------------------------


def test_body_medication_mention_does_not_create_s4_or_swallow_sections():
    source_input = _source_input(
        parent_items=[_parent_item("parent:in01", "IN-01", "年龄要求", 0, ("span-in01",))],
        materials=[_material("span-in01", "body.p1", 0, "年龄≥18岁。")],
    )
    mention_only = [
        _para(0, "body.h5", "5 其他要求", level=1),
        _para(1, "body.h5.p1", "研究期间不得使用合并用药；禁用药物清单由研究者判断。"),
        _para(2, "body.h6", "6 统计分析", level=1),
    ]
    result = discover_review_scope(
        source_input=source_input, blocks=mention_only, source_spans=[]
    )
    assert not _of_kind(result, ReviewScopeKind.MEDICATION_SECTION)

    bounded = [
        _para(0, "body.h4", "4 用药限制", level=1),
        _para(1, "body.h4.s", "4.1 合并用药", level=2),
        _para(2, "body.h4.s.p1", "合并用药需记录。"),
        _para(3, "body.h5", "5 其他要求", level=1),
        _para(4, "body.h5.p1", "此处再次提及禁用药物，但不构成章节。"),
    ]
    result = discover_review_scope(source_input=source_input, blocks=bounded, source_spans=[])
    sections = _of_kind(result, ReviewScopeKind.MEDICATION_SECTION)
    assert len(sections) == 1
    assert sections[0].block_source_refs == ("body.h4.s", "body.h4.s.p1")
    assert sections[0].discovery_reason == "标题匹配：4.1 合并用药"
    assert sections[0].clinically_confirmed is False


def test_s4_subtree_includes_nested_tables_with_consistent_geometry():
    source_input = _source_input(
        parent_items=[_parent_item("parent:in01", "IN-01", "年龄要求", 0, ("span-in01",))],
        materials=[_material("span-in01", "body.p1", 0, "年龄≥18岁。")],
    )
    blocks = [
        _para(0, "body.h6", "6.3 禁用药物与合并用药", level=1),
        _para(1, "body.h6.p1", "下列药物不得使用。"),
        _table(2, "body.t0"),
        _para(3, "body.t0.r0.c0.p0", "示例药物甲", table_path=(0, 0)),
        _table(4, "body.t0.r0.c0.t0", table_path=(0, 0)),
        _para(5, "body.t0.r0.c0.t0.r0.c0.p0", "嵌套内容", table_path=(0, 0, 0, 0)),
        _para(6, "body.h7", "7 统计分析", level=1),
        _para(7, "body.h7.p1", "统计方法。"),
    ]

    result = discover_review_scope(source_input=source_input, blocks=blocks, source_spans=[])

    sections = _of_kind(result, ReviewScopeKind.MEDICATION_SECTION)
    assert len(sections) == 1
    assert sections[0].block_source_refs == (
        "body.h6",
        "body.h6.p1",
        "body.t0",
        "body.t0.r0.c0.p0",
        "body.t0.r0.c0.t0",
        "body.t0.r0.c0.t0.r0.c0.p0",
    )
    assert "body.h7" not in sections[0].block_source_refs
    assert not _diagnostics_of(result, ScopeDiagnosticKind.TABLE_GEOMETRY_INCONSISTENT)


def test_duplicate_titles_and_texts_are_distinct_identities_and_sources_keep_roles():
    source_input = _source_input(
        parent_items=[
            _parent_item("parent:in01", "IN-01", "避孕引用", 0, ("span-in01",)),
            _parent_item("parent:ex01", "EX-01", "年龄要求", 1, ("span-ex01",)),
        ],
        materials=[
            _material("span-in01", "body.p1", 0, "避孕方法见附录 3。"),
            _material("span-ex01", "body.p2", 1, "年龄≥18岁。"),
        ],
    )
    blocks = [
        _para(0, "body.h5", "5.1 合并用药", level=1),
        _para(1, "body.h5.p1", "记录合并用药。"),
        _para(2, "body.h6", "5.2 合并用药", level=1),
        _para(3, "body.h6.p1", "同样记录合并用药。"),
        _para(4, "body.app3", "附录 3 禁用药物", level=1),
        _para(5, "body.app3.p1", "清单乙。"),
    ]
    spans = [_span("span-app3", "body.app3", 4), _span("span-in01", "body.p1", 0)]

    result = discover_review_scope(
        source_input=source_input, blocks=blocks, source_spans=spans
    )

    sections = _of_kind(result, ReviewScopeKind.MEDICATION_SECTION)
    assert [item.label for item in sections] == ["5.1 合并用药", "5.2 合并用药", "附录 3 禁用药物"]
    assert [item.block_source_refs[0] for item in sections] == [
        "body.h5",
        "body.h6",
        "body.app3",
    ]
    assert len({item.block_source_refs for item in sections}) == 3

    referenced = _of_kind(result, ReviewScopeKind.REFERENCED_SOURCE)
    assert len(referenced) == 1
    assert referenced[0].identifiers == ("附录 3",)

    records = {item.source_span_id: item for item in result.source_records}
    assert records["span-app3"].roles == (
        ReviewScopeKind.REFERENCED_SOURCE,
        ReviewScopeKind.MEDICATION_SECTION,
    )
    assert records["span-in01"].roles == (
        ReviewScopeKind.OFFICIAL_RULE_TEXT,
        ReviewScopeKind.REFERENCED_SOURCE,
    )


def test_phase_words_do_not_filter_candidates_and_nothing_is_clinically_confirmed():
    source_input = _source_input(
        parent_items=[_parent_item("parent:in01", "IN-01", "年龄要求", 0, ("span-in01",))],
        materials=[_material("span-in01", "body.p1", 0, "年龄≥18岁。")],
    )
    blocks = [
        _para(0, "body.h1", "5.1 Ⅱ期禁用药物", level=1),
        _para(1, "body.h1.p1", "Ⅱ期清单。"),
        _para(2, "body.h2", "5.2 Ⅲ期合并用药", level=1),
        _para(3, "body.h2.p1", "Ⅲ期清单。"),
    ]

    result = discover_review_scope(source_input=source_input, blocks=blocks, source_spans=[])

    sections = _of_kind(result, ReviewScopeKind.MEDICATION_SECTION)
    assert [item.label for item in sections] == ["5.1 Ⅱ期禁用药物", "5.2 Ⅲ期合并用药"]
    assert all(item.review_stage is None for item in sections)
    assert all(item.clinically_confirmed is False for item in result.candidates)
    assert result.clinical_adoption_applied is False


def test_heading_style_and_concrete_native_numbering_are_used_when_justified():
    source_input = _source_input(
        parent_items=[_parent_item("parent:in01", "IN-01", "用药限制", 0, ("span-in01",))],
        materials=[_material("span-in01", "body.p1", 0, "见第 9.2 节。")],
    )
    blocks = [
        StructureBlock(
            source_ref="body.s92",
            document_part=DocumentPart.BODY,
            block_order=0,
            kind=BlockKind.PARAGRAPH,
            text="合并用药与治疗",
            style_name="Heading 2",
            numbering=NumberingRef(num_id=7, level=1, lvl_text="9.2", num_fmt="decimal"),
        ),
        _para(1, "body.s92.p1", "正文内容。"),
        _para(2, "body.h10", "10 安全性评估", style="Heading 1"),
    ]

    result = discover_review_scope(source_input=source_input, blocks=blocks, source_spans=[])

    referenced = _of_kind(result, ReviewScopeKind.REFERENCED_SOURCE)
    assert len(referenced) == 1
    assert referenced[0].identifiers == ("第 9.2 节",)
    assert referenced[0].block_source_refs == ("body.s92", "body.s92.p1")


# ---------------------------------------------------------------------------
# 来源身份与摘录
# ---------------------------------------------------------------------------


def test_unknown_and_cross_snapshot_source_ids_are_reported_not_dropped():
    source_input = _source_input(
        parent_items=[
            _parent_item(
                "parent:in01",
                "IN-01",
                "年龄要求",
                0,
                ("span-in01", "span-ghost", "span-other"),
            )
        ],
        materials=[
            _material("span-in01", "body.p1", 0, "年龄≥18岁。"),
            _material("span-ghost", "body.p2", 1, "年龄≥18岁。"),
            _material("span-other", "body.p3", 2, "年龄≥18岁。"),
        ],
    )
    spans = [
        _span("span-in01", "body.p1", 0),
        _span("span-other", "body.p3", 2, snapshot=OTHER_SNAPSHOT),
    ]

    result = discover_review_scope(
        source_input=source_input, blocks=[], source_spans=spans
    )

    official = _of_kind(result, ReviewScopeKind.OFFICIAL_RULE_TEXT)
    assert official[0].source_span_ids == ("span-in01", "span-ghost", "span-other")
    records = {item.source_span_id: item for item in result.source_records}
    assert records["span-in01"].identity_status == "ok"
    assert records["span-ghost"].identity_status == "unknown_span"
    assert records["span-ghost"].raw_text == "年龄≥18岁。"
    assert records["span-other"].identity_status == "cross_snapshot"
    flags = {(item.kind, item.source_span_ids) for item in result.diagnostics}
    assert (ScopeDiagnosticKind.SOURCE_SPAN_UNKNOWN, ("span-ghost",)) in flags
    assert (ScopeDiagnosticKind.SOURCE_SPAN_CROSS_SNAPSHOT, ("span-other",)) in flags
    assert {"span-in01", "span-ghost", "span-other"} <= set(records)


def test_partial_excerpt_is_accepted_and_non_substring_excerpt_is_reported():
    source_input = _source_input(
        parent_items=[
            _parent_item("parent:in01", "IN-01", "摘录检查", 0, ("span-a", "span-b"))
        ],
        materials=[
            _material("span-a", "body.p1", 0, "筛选期常规检查记录。"),
            _material("span-b", "body.p2", 1, "筛选期常规检查记录。"),
        ],
    )
    spans = [
        _span("span-a", "body.p1", 0, excerpt="筛选期"),
        _span("span-b", "body.p2", 1, excerpt="不在原文中的摘录"),
    ]

    result = discover_review_scope(
        source_input=source_input, blocks=[], source_spans=spans
    )

    records = {item.source_span_id: item for item in result.source_records}
    assert records["span-a"].excerpt == "筛选期"
    assert records["span-a"].raw_text == "筛选期常规检查记录。"
    excerpt_diagnostics = _diagnostics_of(
        result, ScopeDiagnosticKind.EXCERPT_NOT_IN_SOURCE_TEXT
    )
    assert [item.source_span_ids for item in excerpt_diagnostics] == [("span-b",)]


def test_unsupported_identifier_is_reported_not_invented():
    source_input = _source_input(
        parent_items=[_parent_item("parent:in01", "IN-01", "时间窗引用", 0, ("span-in01",))],
        materials=[_material("span-in01", "body.p1", 0, "时间窗见第百二节。")],
    )
    blocks = [
        _para(0, "body.s102", "102 研究设计", level=1),
        _para(1, "body.s102.p1", "设计描述。"),
    ]

    result = discover_review_scope(source_input=source_input, blocks=blocks, source_spans=[])

    assert not _of_kind(result, ReviewScopeKind.REFERENCED_SOURCE)
    unsupported = _diagnostics_of(result, ScopeDiagnosticKind.REFERENCE_IDENTIFIER_UNSUPPORTED)
    assert [item.identifiers for item in unsupported] == [("第百二节",)]
    assert not _diagnostics_of(result, ScopeDiagnosticKind.REFERENCE_UNRESOLVED)


def test_new_native_section_keeps_full_text_outside_the_old_short_model_input():
    source = _source_input(parent_items=[_parent_item("parent:in01", "IN-01", "标准", 0, ("in",))],
        materials=[_material("in", "body.p0", 0, "入选要求。")])
    blocks = [_para(0, "body.p0", "入选要求。"), _para(1, "body.p1", "合并用药", level=0),
              _para(2, "body.p2", "限制条件及其例外保留在同一段。")]
    spans = [_span("in", "body.p0", 0), _span("heading", "body.p1", 1),
             _span("native", "body.p2", 2, excerpt="其例外")]
    result = discover_review_scope(source_input=source, blocks=blocks, source_spans=spans)
    record = next(row for row in result.source_records if row.source_span_id == "native")
    assert record.raw_text == blocks[2].text
    assert record.identity_status == "ok"
    assert not [row for row in result.diagnostics if row.kind == ScopeDiagnosticKind.SOURCE_TEXT_UNAVAILABLE
                and "native" in row.source_span_ids]


def test_whitespace_cannot_join_distinct_numbers_into_a_verified_excerpt():
    source = _source_input(parent_items=[_parent_item("parent:in01", "IN-01", "标准", 0, ("in",))],
        materials=[_material("in", "body.p0", 0, "原文读数：1 0 mg/L。")])
    result = discover_review_scope(source_input=source, blocks=[],
        source_spans=[_span("in", "body.p0", 0, excerpt="原文读数：10mg/L。")])
    record = next(row for row in result.source_records if row.source_span_id == "in")
    assert record.identity_status == "excerpt_mismatch"
    assert record.raw_text == "原文读数：1 0 mg/L。"
    assert any(row.kind == ScopeDiagnosticKind.EXCERPT_NOT_IN_SOURCE_TEXT for row in result.diagnostics)


def test_second_root_table_nested_reference_never_borrows_first_table():
    source = _source_input(parent_items=[_parent_item("parent:in01", "IN-01", "标准", 0, ("in",))],
        materials=[_material("in", "body.p0", 0, "要求见表2。")])
    blocks = [_para(0, "body.p0", "要求见表2。"), _table(1, "body.t0"),
        _para(2, "body.t0.r0.c0.p0", "无关表格", table_path=(0, 0)),
        _para(3, "body.p1", "其他内容"), _table(4, "body.t1"),
        _para(5, "body.t1.r0.c0.p0", "表2 对应要求", table_path=(0, 0)),
        _table(6, "body.t1.r0.c0.t0", table_path=(0, 0)),
        _para(7, "body.t1.r0.c0.t0.r0.c0.p0", "对应表格原文", table_path=(0, 0, 0, 0))]
    result = discover_review_scope(source_input=source, blocks=blocks, source_spans=[])
    target, = _of_kind(result, ReviewScopeKind.REFERENCED_SOURCE)
    assert target.block_source_refs == tuple(block.source_ref for block in blocks[5:])
    assert "body.t0" not in target.block_source_refs
    assert "body.t1" not in target.block_source_refs


def test_caption_after_table_cells_resolves_the_same_complete_table():
    source = _source_input(parent_items=[_parent_item("parent:in01", "IN-01", "标准", 0, ("in",))],
        materials=[_material("in", "body.p0", 0, "要求见表2。")])
    blocks = [_para(0, "body.p0", "要求见表2。"), _table(1, "body.t0"),
        _para(2, "body.t0.r0.c0.p0", "表格原文", table_path=(0, 0)),
        _para(3, "body.p1", "表2 对应要求"), _para(4, "body.p2", "下一段")]
    result = discover_review_scope(source_input=source, blocks=blocks, source_spans=[])
    target, = _of_kind(result, ReviewScopeKind.REFERENCED_SOURCE)
    assert target.block_source_refs == tuple(block.source_ref for block in blocks[1:4])


def test_wrong_native_position_is_not_marked_identity_ok():
    source = _source_input(parent_items=[_parent_item("parent:in01", "IN-01", "标准", 0, ("in",))],
        materials=[_material("in", "body.p0", 0, "标准原文。")])
    result = discover_review_scope(source_input=source, blocks=[_para(1, "body.p0", "标准原文。")],
        source_spans=[_span("in", "body.p0", 0)])
    assert next(row for row in result.source_records if row.source_span_id == "in").identity_status == "source_mismatch"
    assert any(row.kind == ScopeDiagnosticKind.SOURCE_GEOMETRY_INCONSISTENT for row in result.diagnostics)


def test_duplicate_source_identity_is_not_silently_kept_once():
    source = _source_input(parent_items=[_parent_item("parent:in01", "IN-01", "标准", 0, ("in",))],
        materials=[_material("in", "body.p0", 0, "标准原文。")])
    span = _span("in", "body.p0", 0)
    with pytest.raises(ValueError, match="来源身份或结构位置重复"):
        discover_review_scope(source_input=source, blocks=[], source_spans=[span, span])


def test_changed_frozen_text_cannot_replace_the_native_source_even_with_a_shared_excerpt():
    source = _source_input(parent_items=[_parent_item("parent:in01", "IN-01", "标准", 0, ("in",))],
        materials=[_material("in", "body.p0", 0, "标准：读数小于10。")])
    result = discover_review_scope(source_input=source, blocks=[_para(0, "body.p0", "标准：读数大于10。")],
        source_spans=[_span("in", "body.p0", 0, excerpt="标准：")])
    row = next(row for row in result.source_records if row.source_span_id == "in")
    assert row.raw_text == "标准：读数大于10。"
    assert row.identity_status == "source_mismatch"


def test_structural_table_anchor_reuses_the_same_ordered_native_text_as_deconstruction():
    source = _source_input(parent_items=[_parent_item("parent:in01", "IN-01", "标准", 0, ("in",))],
        materials=[_material("in", "body.t0", 0, "第一格\n第二格")])
    blocks = [_table(0, "body.t0"), _para(1, "body.t0.r0.c0.p0", "第一格", table_path=(0, 0)),
        _para(2, "body.t0.r0.c1.p0", "第二格", table_path=(0, 1)),
        _table(3, "body.t1"), _para(4, "body.t1.r0.c0.p0", "不属于此表", table_path=(0, 0))]
    result = discover_review_scope(source_input=source, blocks=blocks, source_spans=[_span("in", "body.t0", 0)])
    row = next(row for row in result.source_records if row.source_span_id == "in")
    assert row.raw_text == "第一格\n第二格"
    assert row.identity_status == "ok"


@pytest.mark.parametrize("cue", ["参照", "参见", "详见", "见"])
def test_reference_cue_dotted_section_without_di_or_jie_is_not_silently_ignored(cue):
    source = _source_input(parent_items=[_parent_item("parent:in01", "IN-01", "标准", 0, ("in",))],
        materials=[_material("in", "body.p0", 0, f"要求（{cue} 8.12相关说明）。")])
    blocks = [_para(0, "body.p0", source.source_materials[0].text),
        _para(1, "body.p1", "8.12 相关说明", level=1), _para(2, "body.p2", "说明原文")]
    resolved = discover_review_scope(source_input=source, blocks=blocks, source_spans=[])
    assert _of_kind(resolved, ReviewScopeKind.REFERENCED_SOURCE)[0].block_source_refs == ("body.p1", "body.p2")
    unresolved = discover_review_scope(source_input=source, blocks=blocks[:1], source_spans=[])
    assert any(d.kind == ScopeDiagnosticKind.REFERENCE_UNRESOLVED and d.identifiers == (f"{cue} 8.12",)
               for d in unresolved.diagnostics)


def test_source_options_paginate_native_structure_without_truncating_the_denominator():
    from app.protocols.review_scope import review_scope_source_options
    blocks = [_para(index, f"body.p{index}", f"共同说明{index}") for index in range(25)]
    spans = [_span(f"span{index}", f"body.p{index}", index) for index in range(25)]
    first = review_scope_source_options(blocks=blocks, source_spans=spans, query="共同说明")
    second = review_scope_source_options(blocks=blocks, source_spans=spans, query="共同说明", offset=first["next_offset"])
    assert first["total"] == second["total"] == 25
    assert len(first["items"]) == 20 and len(second["items"]) == 5
    assert second["next_offset"] is None
    assert len({row["source_span_ids"][0] for row in first["items"] + second["items"]}) == 25


def test_source_options_select_complete_heading_subtree_not_toc_or_next_section():
    from app.protocols.review_scope import review_scope_source_options
    blocks = [_para(0, "body.p0", "合并用药", level=0, style="TOC 1"),
        _para(1, "body.p1", "合并用药", level=0), _para(2, "body.p2", "本节说明"),
        _para(3, "body.p3", "下一章节", level=0)]
    spans = [_span(f"span{index}", f"body.p{index}", index) for index in range(4)]
    result = review_scope_source_options(blocks=blocks, source_spans=spans, query="合并用药")
    assert result["total"] == 1
    assert result["items"][0]["source_span_ids"] == ["span1", "span2"]
