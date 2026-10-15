"""Regression tests for authoritative catalog excerpts and control-batch passing."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import (
    CatalogItemKind,
    CatalogKind,
    ReviewStage,
    StudyPhase,
)
from app.domain.contracts.protocol_controls import (
    KnownOfficialRuleTarget,
    KnownRequiredProcedureTarget,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
)
from app.domain.contracts.protocol_ingestion import (
    FrozenCatalogItem,
    FrozenProtocolCatalog,
    ProtocolSourceSpan,
    frozen_catalog_content_hash,
    optional_source_excerpts_for_spans,
)
from app.domain.contracts.enums import (
    AlignmentStatus,
    DocumentPart,
    PhaseScope,
    SourceLocatorPrecision,
)
from app.domain.publication import canonical_hash
from app.protocols.catalogs import freeze_official_parent_rules
from app.protocols.protocol_control_planning import plan_protocol_control_batches
from app.protocols.procedure_catalog import build_required_procedure_catalog
from tests.v2.protocols.test_catalogs_slice3 import FROZEN_AT, SNAPSHOT, _index
from tests.v2.protocols.test_procedure_catalog_slice3 import (
    _build,
    _matrix,
    _projection,
)


_SHA = "b" * 64
_SNAPSHOT = SNAPSHOT
_PROTOCOL = "protocol:slice60zn"


def _span(
    span_id: str, excerpt: str | None, source_ref: str = "body.p0"
) -> ProtocolSourceSpan:
    return ProtocolSourceSpan(
        source_span_id=span_id,
        snapshot_id=_SNAPSHOT,
        source_ref=source_ref,
        document_part=DocumentPart.BODY,
        block_order=0,
        excerpt=excerpt,
        precision=SourceLocatorPrecision.TEXT_RANGE,
        text_start=0,
        text_end=max(1, len(excerpt or "")),
        alignment_status=AlignmentStatus.ALIGNED,
        render_artifact_id="render-slice60zn",
        render_page=1,
    )


def _unit() -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id="su-01",
        source_ref="body.p1",
        member_source_refs=["body.p1"],
        source_span_ids=["span:01"],
        unit_kind="paragraph",
        heading_path=["章节 A"],
        source_order=1,
        study_phase=StudyPhase.PHASE_III,
        phase_scopes=[PhaseScope.SHARED],
        excerpt="章节原文",
    )


def _manifest() -> ProtocolSectionCoverageManifest:
    return ProtocolSectionCoverageManifest(
        manifest_id="manifest:slice60zn",
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_III,
        snapshot_id=_SNAPSHOT,
        units=[_unit()],
    )


def _catalog(
    kind: CatalogKind, items: list[FrozenCatalogItem]
) -> FrozenProtocolCatalog:
    base = dict(
        catalog_id=f"catalog:{kind.value}:slice60zn",
        snapshot_id=_SNAPSHOT,
        catalog_kind=kind,
        study_phase=StudyPhase.PHASE_III,
        items=tuple(items),
        frozen_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
        frozen_by="slice60zn-test",
    )
    shell = FrozenProtocolCatalog.model_construct(
        schema_version="fixture/v1",
        **base,
        catalog_sha256="",
    )
    return FrozenProtocolCatalog(
        **base,
        catalog_sha256=canonical_hash(
            shell.model_dump(mode="json", exclude={"catalog_sha256"})
        ),
    )


def test_optional_source_excerpts_align_multi_span_verbatim_text() -> None:
    spans = {
        "span-a": _span("span-a", "父级引导段", "body.p1"),
        "span-b": _span("span-b", "子项条件", "body.p2"),
    }
    excerpts = optional_source_excerpts_for_spans(
        ("span-a", "span-b"),
        by_id=spans,
    )
    assert excerpts == ("父级引导段", "子项条件")


def test_optional_source_excerpts_keep_complete_cross_page_source_block() -> None:
    spans = {
        "span-a": _span("span-a", "跨页段落前半段", "body.p1"),
    }
    block = SimpleNamespace(text="跨页段落前半段，末尾要求空腹采样。")

    assert optional_source_excerpts_for_spans(
        ("span-a",),
        by_id=spans,
        blocks_by_ref={"body.p1": block},
    ) == ("跨页段落前半段，末尾要求空腹采样。",)


def test_optional_source_excerpts_keeps_null_for_structural_span() -> None:
    spans = {
        "span-a": _span("span-a", "有摘录", "body.p1"),
        "span-b": _span("span-b", None, "body.p2"),
    }
    assert optional_source_excerpts_for_spans(("span-a", "span-b"), by_id=spans) == (
        "有摘录",
        None,
    )


def test_optional_source_excerpts_returns_empty_when_all_spans_lack_text() -> None:
    spans = {
        "span-a": _span("span-a", None, "body.t1"),
        "span-b": _span("span-b", None, "body.t2"),
    }
    assert optional_source_excerpts_for_spans(("span-a", "span-b"), by_id=spans) == ()


def test_official_parent_catalog_carries_multi_source_excerpts() -> None:
    index, _blocks, spans = _index()
    catalog = freeze_official_parent_rules(
        index,
        StudyPhase.PHASE_III,
        source_spans=spans,
        frozen_at=FROZEN_AT,
    )
    first = catalog.items[0]
    assert first.source_span_ids == ("span-body.p1", "span-body.p2")
    assert first.source_excerpts == ("criterion alpha", "subcondition alpha")
    assert len(first.source_excerpts) == len(first.source_span_ids)


def test_required_procedure_catalog_carries_multi_source_excerpts() -> None:
    blocks, spans = _matrix(
        [
            ["检查项目", "筛选期", "基线期"],
            ["访视", "V1", "V2"],
            ["实验室检查", "X", "X"],
        ],
        cols=3,
    )
    catalog = _build(blocks, spans, _projection(blocks))
    procedure = next(item for item in catalog.items if item.label == "实验室检查")
    assert len(procedure.source_span_ids) >= 1
    if len(procedure.source_span_ids) > 1:
        assert len(procedure.source_excerpts) == len(procedure.source_span_ids)
        assert any(excerpt and excerpt.strip() for excerpt in procedure.source_excerpts)
    else:
        assert procedure.source_excerpts == ("实验室检查",)


def test_frozen_catalog_item_rejects_mismatched_excerpt_length() -> None:
    with pytest.raises(ValidationError, match="一一对应"):
        FrozenCatalogItem(
            item_id="official-item-1",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="IN-01",
            label="入选标准",
            position=0,
            source_span_ids=("span:01", "span:02"),
            source_excerpts=("只有一条摘录",),
        )


def test_known_official_target_rejects_mismatched_excerpt_length() -> None:
    with pytest.raises(ValidationError, match="一一对应"):
        KnownOfficialRuleTarget(
            catalog_item_id="official-item-1",
            official_code="IN-01",
            label="入选标准",
            position=0,
            source_span_ids=["span:01", "span:02"],
            source_excerpts=["只有一条摘录"],
        )


def test_known_procedure_target_rejects_mismatched_excerpt_length() -> None:
    with pytest.raises(ValidationError, match="一一对应"):
        KnownRequiredProcedureTarget(
            catalog_item_id="procedure-item-1",
            label="筛选期检查",
            visit_instance="screening-1",
            review_stage=ReviewStage.SCREENING,
            position=0,
            source_span_ids=["span:01", "span:02"],
            source_excerpts=["只有一条摘录"],
        )


def test_legacy_catalog_item_without_excerpts_field_deserializes() -> None:
    item = FrozenCatalogItem.model_validate(
        {
            "item_id": "official-item-legacy",
            "kind": "parent_rule",
            "official_code": "IN-01",
            "label": "既有入选标准",
            "position": 0,
            "source_span_ids": ["span:01"],
        }
    )
    assert item.source_excerpts == ()
    catalog = _catalog(
        CatalogKind.OFFICIAL_PARENT_RULES,
        [
            item,
        ],
    )
    assert catalog.items[0].source_excerpts == ()


def test_legacy_catalog_hash_without_excerpt_field_still_validates() -> None:
    payload = {
        "schema_version": "fixture/v1",
        "catalog_id": "catalog:official_parent_rules:legacy-hash",
        "snapshot_id": _SNAPSHOT,
        "catalog_kind": "official_parent_rules",
        "study_phase": "phase_iii",
        "items": [
            {
                "item_id": "official-item-legacy-hash",
                "kind": "parent_rule",
                "official_code": "IN-01",
                "label": "既有入选标准",
                "visit_instance": None,
                "review_stage": None,
                "position": 0,
                "source_span_ids": ["span:01"],
            }
        ],
        "frozen_at": "2026-08-28T00:00:00Z",
        "frozen_by": "legacy-builder",
    }
    payload["catalog_sha256"] = canonical_hash(payload)

    catalog = FrozenProtocolCatalog.model_validate(payload)

    assert catalog.items[0].source_excerpts == ()
    assert frozen_catalog_content_hash(catalog) == payload["catalog_sha256"]


def test_planner_passes_catalog_excerpts_to_known_targets() -> None:
    official = _catalog(
        CatalogKind.OFFICIAL_PARENT_RULES,
        [
            FrozenCatalogItem(
                item_id="official-item-1",
                kind=CatalogItemKind.PARENT_RULE,
                official_code="EX-01",
                label="既有排除标准",
                position=0,
                source_span_ids=("span:01", "span:02"),
                source_excerpts=("排除引导", "排除子项"),
            ),
        ],
    )
    procedure = _catalog(
        CatalogKind.REQUIRED_PROCEDURES,
        [
            FrozenCatalogItem(
                item_id="procedure-item-1",
                kind=CatalogItemKind.REQUIRED_PROCEDURE,
                label="筛选期检查",
                visit_instance="screening-1",
                review_stage=ReviewStage.SCREENING,
                position=0,
                source_span_ids=("span:03", "span:04"),
                source_excerpts=("操作原文", "标记原文"),
            ),
        ],
    )
    plan = plan_protocol_control_batches(
        _manifest(),
        official,
        procedure,
    )
    batch = plan.batches[0]
    official_target = batch.known_official_targets[0]
    procedure_target = batch.known_procedure_targets[0]
    assert official_target.source_excerpts == ["排除引导", "排除子项"]
    assert procedure_target.source_excerpts == ["操作原文", "标记原文"]
    assert official_target.source_span_ids == ["span:01", "span:02"]
    assert procedure_target.source_span_ids == ["span:03", "span:04"]


def test_planner_sorts_source_ids_and_excerpts_as_pairs() -> None:
    official = _catalog(
        CatalogKind.OFFICIAL_PARENT_RULES,
        [
            FrozenCatalogItem(
                item_id="official-item-unsorted",
                kind=CatalogItemKind.PARENT_RULE,
                official_code="EX-01",
                label="既有排除标准",
                position=0,
                source_span_ids=("span:02", "span:01"),
                source_excerpts=("第二段原文", "第一段原文"),
            ),
        ],
    )

    target = (
        plan_protocol_control_batches(_manifest(), official)
        .batches[0]
        .known_official_targets[0]
    )

    assert target.source_span_ids == ["span:01", "span:02"]
    assert target.source_excerpts == ["第一段原文", "第二段原文"]


def test_empty_excerpts_catalog_preserves_planner_compatibility() -> None:
    official = _catalog(
        CatalogKind.OFFICIAL_PARENT_RULES,
        [
            FrozenCatalogItem(
                item_id="official-item-legacy",
                kind=CatalogItemKind.PARENT_RULE,
                official_code="IN-01",
                label="既有入选标准",
                position=0,
                source_span_ids=("span:01",),
            ),
        ],
    )
    plan = plan_protocol_control_batches(_manifest(), official)
    target = plan.batches[0].known_official_targets[0]
    assert target.source_excerpts == []
    assert target.catalog_item_id == "official-item-legacy"


def test_official_catalog_preserves_partial_text_with_structural_null() -> None:
    index, _blocks, spans = _index(locator_overrides={1: ("page", 1)})
    catalog = freeze_official_parent_rules(
        index,
        StudyPhase.PHASE_III,
        source_spans=spans,
        frozen_at=FROZEN_AT,
    )
    # The page-only parent remains a structural anchor while its text child stays visible.
    first = catalog.items[0]
    assert first.source_excerpts == (None, "subcondition alpha")
    assert len(first.source_span_ids) == 2


def test_procedure_catalog_builder_end_to_end_excerpts_match_span_ids() -> None:
    blocks, spans = _matrix(
        [
            ["检查项目", "筛选期", "基线期"],
            ["访视", "V1", "V2"],
            ["知情同意", "X", ""],
        ],
        cols=3,
    )
    catalog = build_required_procedure_catalog(
        blocks,
        phase_projection=_projection(blocks),
        source_spans=spans,
        frozen_at=FROZEN_AT,
    )
    for item in catalog.items:
        if item.source_excerpts:
            assert len(item.source_excerpts) == len(item.source_span_ids)
            assert all(text.strip() for text in item.source_excerpts)
