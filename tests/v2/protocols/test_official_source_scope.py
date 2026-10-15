"""Synthetic inventory checks for frozen-parent leading-scope resolution."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.domain.contracts.agent_io import (
    ProtocolDeconstructionInput,
    ProtocolSourceMaterial,
)
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import (
    CatalogItemKind,
    CatalogKind,
    DatePrecision,
    MetadataResolutionStatus,
    ReviewStage,
    StudyPhase,
)
from app.domain.contracts.protocol_ingestion import (
    FrozenCatalogItem,
    FrozenProtocolCatalog,
)
from app.domain.contracts.protocol_metadata import (
    ProtocolIdentityDecision,
    StudyPhaseSelection,
)
from app.domain.publication import canonical_hash
from app.protocols.official_source_scope import (
    FrozenParentScopeError,
    FrozenParentScopeFragment,
    frozen_parent_scope_fragments,
)

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
SHA = "a" * 64


def _has_stages(text: str) -> bool:
    return ("筛选时" in text or "筛选和基线时" in text) and "基线时" in text


def _is_substantive(text: str) -> bool:
    body = text.rstrip("：:")
    return any(token in body for token in ("年龄≥", "ALT", "AST", "胸部CT"))


def _catalog(kind: CatalogKind, items: list[FrozenCatalogItem]) -> FrozenProtocolCatalog:
    payload = {
        "catalog_id": f"catalog:{kind.value}",
        "snapshot_id": "snapshot-scope",
        "catalog_kind": kind,
        "study_phase": StudyPhase.PHASE_II,
        "items": tuple(items),
        "frozen_at": NOW,
        "frozen_by": "synthetic_scope_fixture/v1",
    }
    unhashed = FrozenProtocolCatalog.model_construct(
        **payload, catalog_sha256="0" * 64
    )
    payload["catalog_sha256"] = canonical_hash(
        unhashed.model_dump(mode="json", exclude={"catalog_sha256"})
    )
    return FrozenProtocolCatalog(**payload)


def _source_input(
    *,
    parent_items: list[FrozenCatalogItem],
    materials: list[ProtocolSourceMaterial],
) -> ProtocolDeconstructionInput:
    procedure_items = [
        FrozenCatalogItem(
            item_id="procedure:scope:screening",
            kind=CatalogItemKind.REQUIRED_PROCEDURE,
            label="常规检查",
            visit_instance="筛选期 D-28~D-1",
            review_stage=ReviewStage.SCREENING,
            position=0,
            source_span_ids=["span-proc"],
        )
    ]
    identity = ProtocolIdentityDecision(
        identity_decision_id="identity-scope",
        snapshot_id="snapshot-scope",
        project_name="合成范围核验",
        project_code="SCOPE",
        protocol_code="SCOPE-001",
        official_version="V1.0",
        official_date=DateValue(value=date(2026, 10, 4), precision=DatePrecision.DAY),
        study_phase=StudyPhase.PHASE_II,
        selected_candidate_ids=["candidate-scope"],
        status=MetadataResolutionStatus.CONFIRMED,
        confirmation_required=False,
        confirmed_by="synthetic",
        confirmed_at=NOW,
    )
    selection = StudyPhaseSelection(
        selection_id="phase-selection-scope",
        snapshot_id="snapshot-scope",
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
        extraction_snapshot_id="snapshot-scope",
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


def _material(span_id: str, order: int, text: str) -> ProtocolSourceMaterial:
    return ProtocolSourceMaterial(
        source_span_id=span_id,
        source_ref=f"body.p{order}",
        block_order=order,
        text=text,
    )


def _two_parent_fixture(
    *,
    in_span_ids: list[str],
    ex_span_ids: list[str],
    texts: dict[str, str],
    orders: dict[str, int] | None = None,
) -> ProtocolDeconstructionInput:
    span_ids = list(dict.fromkeys([*in_span_ids, *ex_span_ids, "span-proc"]))
    order_map = orders or {
        span_id: index for index, span_id in enumerate(span_ids)
    }
    payload_texts = {"span-proc": "筛选期常规检查", **texts}
    parent_items = [
        FrozenCatalogItem(
            item_id="parent:in01",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="IN-01",
            label="年龄要求",
            position=0,
            source_span_ids=tuple(in_span_ids),
        ),
        FrozenCatalogItem(
            item_id="parent:ex01",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="EX-01",
            label="肝功能阈值",
            position=1,
            source_span_ids=tuple(ex_span_ids),
        ),
    ]
    materials = [
        _material(span_id, order_map[span_id], payload_texts[span_id])
        for span_id in span_ids
    ]
    return _source_input(parent_items=parent_items, materials=materials)


def _inventory(source_input: ProtocolDeconstructionInput, official_code: str):
    return frozen_parent_scope_fragments(
        source_input,
        official_code,
        scope_has_stages=_has_stages,
        is_substantive=_is_substantive,
    )


def test_same_span_colon_prefix_is_inventoried_without_child_body():
    heading = "筛选时和基线时需满足以下标准："
    child = "年龄≥18岁"
    source_input = _two_parent_fixture(
        in_span_ids=["span-in"],
        ex_span_ids=["span-ex"],
        texts={
            "span-in": heading + child,
            "span-ex": "ALT或AST≥1.5×ULN",
            "span-proc": "筛选期常规检查",
        },
    )

    assert _inventory(source_input, "IN-01") == (
        FrozenParentScopeFragment(source_span_id="span-in", excerpt=heading),
    )


def test_split_span_heading_before_substantive_child():
    heading = "筛选时和基线时需满足以下标准："
    child = "年龄≥18岁"
    source_input = _two_parent_fixture(
        in_span_ids=["span-in-heading", "span-in-child"],
        ex_span_ids=["span-ex"],
        texts={
            "span-in-heading": heading,
            "span-in-child": child,
            "span-ex": "ALT或AST≥1.5×ULN",
            "span-proc": "筛选期常规检查",
        },
        orders={
            "span-in-heading": 0,
            "span-in-child": 1,
            "span-ex": 2,
            "span-proc": 3,
        },
    )

    assert _inventory(source_input, "IN-01") == (
        FrozenParentScopeFragment(
            source_span_id="span-in-heading",
            excerpt=heading,
        ),
    )


def test_another_parent_heading_is_isolated():
    heading = "筛选时和基线时需满足以下标准："
    source_input = _two_parent_fixture(
        in_span_ids=["span-in"],
        ex_span_ids=["span-ex"],
        texts={
            "span-in": "年龄≥18岁",
            "span-ex": heading + "ALT或AST≥1.5×ULN",
            "span-proc": "筛选期常规检查",
        },
    )

    assert _inventory(source_input, "IN-01") == ()
    assert _inventory(source_input, "EX-01") == (
        FrozenParentScopeFragment(source_span_id="span-ex", excerpt=heading),
    )


def test_scope_after_substantive_body_is_excluded():
    source_input = _two_parent_fixture(
        in_span_ids=["span-in-body", "span-in-late-heading"],
        ex_span_ids=["span-ex"],
        texts={
            "span-in-body": "年龄≥18岁",
            "span-in-late-heading": "筛选时和基线时需满足以下标准：",
            "span-ex": "ALT或AST≥1.5×ULN",
            "span-proc": "筛选期常规检查",
        },
        orders={
            "span-in-body": 0,
            "span-in-late-heading": 1,
            "span-ex": 2,
            "span-proc": 3,
        },
    )

    assert _inventory(source_input, "IN-01") == ()


def test_non_stage_prefix_is_excluded():
    source_input = _two_parent_fixture(
        in_span_ids=["span-in"],
        ex_span_ids=["span-ex"],
        texts={
            "span-in": "需满足以下标准：年龄≥18岁",
            "span-ex": "ALT或AST≥1.5×ULN",
            "span-proc": "筛选期常规检查",
        },
    )

    assert _inventory(source_input, "IN-01") == ()


def test_missing_official_code_raises_structured_error():
    source_input = _two_parent_fixture(
        in_span_ids=["span-in"],
        ex_span_ids=["span-ex"],
        texts={
            "span-in": "年龄≥18岁",
            "span-ex": "ALT或AST≥1.5×ULN",
            "span-proc": "筛选期常规检查",
        },
    )

    with pytest.raises(ValueError, match="FROZEN_PARENT_SCOPE_IDENTITY_MISSING"):
        _inventory(source_input, "IN-99")


def test_duplicate_official_code_raises_structured_error():
    parent_items = [
        FrozenCatalogItem(
            item_id="parent:in01",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="IN-01",
            label="年龄要求",
            position=0,
            source_span_ids=("span-in-a",),
        ),
        FrozenCatalogItem(
            item_id="parent:in01-dup",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="IN-01",
            label="年龄要求重复项",
            position=1,
            source_span_ids=("span-in-b",),
        ),
    ]
    source_input = _source_input(
        parent_items=parent_items,
        materials=[
            _material("span-in-a", 0, "筛选时和基线时需满足以下标准：年龄≥18岁"),
            _material("span-in-b", 1, "年龄≥18岁"),
            _material("span-proc", 2, "筛选期常规检查"),
        ],
    )

    with pytest.raises(ValueError, match="FROZEN_PARENT_SCOPE_IDENTITY_DUPLICATE"):
        _inventory(source_input, "IN-01")


def test_missing_referenced_frozen_material_raises_structured_error():
    source_input = _two_parent_fixture(
        in_span_ids=["span-in"],
        ex_span_ids=["span-ex"],
        texts={
            "span-in": "筛选时和基线时需满足以下标准：年龄≥18岁",
            "span-ex": "ALT或AST≥1.5×ULN",
            "span-proc": "筛选期常规检查",
        },
    )
    source_input.source_materials = [
        item
        for item in source_input.source_materials
        if item.source_span_id != "span-in"
    ]

    with pytest.raises(ValueError, match="FROZEN_PARENT_SCOPE_MATERIAL_MISSING"):
        _inventory(source_input, "IN-01")


def test_duplicate_same_material_object_is_not_a_valid_source_identity():
    source = _two_parent_fixture(
        in_span_ids=["span-in"], ex_span_ids=["span-ex"],
        texts={"span-in": "年龄≥18岁", "span-ex": "ALT或AST≥1.5×ULN"},
    )
    source.source_materials.append(source.source_materials[0])
    with pytest.raises(FrozenParentScopeError) as caught:
        _inventory(source, "IN-01")
    assert caught.value.code == "FROZEN_PARENT_SCOPE_MATERIAL_DUPLICATE"
    assert caught.value.source_refs == ("span-in",)


def test_consecutive_leading_headings_are_preserved_before_the_body():
    source = _two_parent_fixture(
        in_span_ids=["span-h1", "span-h2", "span-child"], ex_span_ids=["span-ex"],
        texts={"span-h1": "筛选时和基线时需满足以下标准：",
               "span-h2": "筛选和基线时需满足下列标准：",
               "span-child": "年龄≥18岁", "span-ex": "ALT或AST≥1.5×ULN"},
    )
    assert [item.source_span_id for item in _inventory(source, "IN-01")] == ["span-h1", "span-h2"]


def test_equal_block_order_keeps_catalog_span_order_not_identifier_order():
    source = _two_parent_fixture(
        in_span_ids=["z-heading", "a-child"], ex_span_ids=["span-ex"],
        texts={"z-heading": "筛选时和基线时需满足以下标准：",
               "a-child": "年龄≥18岁", "span-ex": "ALT或AST≥1.5×ULN"},
        orders={"z-heading": 0, "a-child": 0, "span-ex": 1, "span-proc": 2},
    )
    assert [item.source_span_id for item in _inventory(source, "IN-01")] == ["z-heading"]


@pytest.mark.parametrize("text,expected", [
    ("入选标准：筛选时和基线时需满足以下标准：年龄≥18岁",
     ["筛选时和基线时需满足以下标准："]),
    ("筛选时和基线时，需满足以下标准：年龄≥18岁",
     ["筛选时和基线时，需满足以下标准："]),
    ("筛选时需满足以下标准：年龄≥18岁", ["筛选时需满足以下标准："]),
    ("筛选时和基线时需满足以下标准\n年龄≥18岁",
     ["筛选时和基线时需满足以下标准\n"]),
    ("筛选时和基线时（注：含复查）需满足以下标准：年龄≥18岁",
     ["筛选时和基线时（注：含复查）需满足以下标准："]),
    ("筛选时年龄≥18岁", []),
    ("年龄≥18岁\n筛选时和基线时需满足以下标准：", []),
])
def test_inventory_uses_real_product_classifiers(text, expected):
    from app.protocols.deconstruction_gate import _source_review_stages, _substantive_obligation_segments
    source = _two_parent_fixture(
        in_span_ids=["span-in"], ex_span_ids=["span-ex"],
        texts={"span-in": text, "span-ex": "ALT或AST≥1.5×ULN"},
    )
    fragments = frozen_parent_scope_fragments(
        source, "IN-01",
        scope_has_stages=lambda value: bool(_source_review_stages([value])),
        is_substantive=lambda value: bool(_substantive_obligation_segments(value)),
    )
    assert [item.excerpt for item in fragments] == expected
    assert all(item.excerpt in text for item in fragments)


def test_non_stage_colon_lead_in_does_not_hide_a_later_heading():
    from app.protocols.deconstruction_gate import _source_review_stages, _substantive_obligation_segments
    source = _two_parent_fixture(
        in_span_ids=["lead", "heading", "child"], ex_span_ids=["span-ex"],
        texts={"lead": "入选标准：", "heading": "筛选时和基线时需满足以下标准：",
               "child": "年龄≥18岁", "span-ex": "ALT或AST≥1.5×ULN"},
    )
    fragments = frozen_parent_scope_fragments(
        source, "IN-01",
        scope_has_stages=lambda value: bool(_source_review_stages([value])),
        is_substantive=lambda value: bool(_substantive_obligation_segments(value)),
    )
    assert [item.source_span_id for item in fragments] == ["heading"]
