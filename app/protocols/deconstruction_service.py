"""Deterministic assembly of the protocol-deconstruction Agent input package.

This module is deliberately an application-facing composition boundary.  It
does not inspect a model, call an Agent, or write a source document.  The
upstream extraction, rendering/alignment, phase projection, and catalog
builders remain the owners of their respective facts; this service only
checks that their immutable outputs belong to one snapshot and assembles the
smallest source-material set that covers both frozen catalogs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from app.domain.contracts.agent_io import (
    ProtocolDeconstructionInput,
    ProtocolSourceMaterial,
)
from app.domain.contracts.enums import (
    ExtractionStatus,
    MetadataResolutionStatus,
    SourceLocatorPrecision,
    StudyPhase,
)
from app.domain.contracts.protocol_ingestion import (
    CatalogKind,
    FrozenProtocolCatalog,
    ProtocolExtractionSnapshot,
    ProtocolSourceArtifact,
    ProtocolSourceSpan,
)
from app.domain.contracts.protocol_metadata import (
    InterpretationSource,
    PhaseApplicabilityGraph,
    PhaseProjection,
    ProtocolIdentityDecision,
    StudyPhaseSelection,
)
from app.protocols.catalogs import freeze_official_parent_rules
from app.protocols.docx_structure import StructureBlock, StructureExtraction
from app.protocols.phase_detection import (
    PhaseDetectionResult,
    project_single_phase,
)
from app.protocols.procedure_catalog import build_required_procedure_catalog
from app.protocols.section_index import (
    build_section_index,
    formal_source_span_ids,
)
from app.protocols.source_alignment import AlignmentResult


_DEFAULT_FROZEN_BY = "protocol_deconstruction_input_assembler/v1"


class ProtocolDeconstructionInputAssemblyError(ValueError):
    """A deterministic precondition for Agent input assembly was not met."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


# Short aliases keep the failure type discoverable for callers that use
# "input package" rather than the full service name.
ProtocolInputAssemblyError = ProtocolDeconstructionInputAssemblyError
DeconstructionInputAssemblyError = ProtocolDeconstructionInputAssemblyError


@dataclass(frozen=True)
class ProtocolDeconstructionInputPackage:
    """Runner-ready immutable view of one confirmed protocol/phase snapshot.

    ``source_spans`` intentionally contains the complete alignment map, not
    just the selected material subset.  The runner's source gate needs the
    complete map to detect a duplicated physical range/page that collides
    with an otherwise relevant span.  ``source_input.source_materials`` is
    the minimal subset: exactly the union of all source spans referenced by
    both frozen catalogs, ordered by structural position.
    """

    source_input: ProtocolDeconstructionInput
    source_spans: Mapping[str, ProtocolSourceSpan]
    projection: PhaseProjection
    parent_rule_catalog: FrozenProtocolCatalog
    required_procedure_catalog: FrozenProtocolCatalog

    @property
    def input(self) -> ProtocolDeconstructionInput:
        """Convenient alias for callers passing the package to a runner."""

        return self.source_input

    @property
    def deconstruction_input(self) -> ProtocolDeconstructionInput:
        return self.source_input

    @property
    def protocol_input(self) -> ProtocolDeconstructionInput:
        return self.source_input

    @property
    def required_catalog(self) -> FrozenProtocolCatalog:
        return self.required_procedure_catalog

    @property
    def official_parent_catalog(self) -> FrozenProtocolCatalog:
        return self.parent_rule_catalog


def _fail(code: str, message: str) -> None:
    raise ProtocolDeconstructionInputAssemblyError(code, message)


def _resolve_extraction(
    extraction: StructureExtraction | ProtocolExtractionSnapshot | None,
    *,
    blocks: Sequence[StructureBlock] | None,
    snapshot: ProtocolExtractionSnapshot | None,
) -> tuple[tuple[StructureBlock, ...], ProtocolExtractionSnapshot]:
    if isinstance(extraction, StructureExtraction):
        if blocks is not None or snapshot is not None:
            _fail(
                "extraction_arguments_ambiguous",
                "StructureExtraction 已包含 blocks 和 snapshot，不能重复提供拆分参数。",
            )
        return tuple(extraction.blocks), extraction.snapshot

    if isinstance(extraction, ProtocolExtractionSnapshot):
        if snapshot is not None and snapshot != extraction:
            _fail("snapshot_ambiguous", "提供了两个不一致的提取快照。")
        snapshot = extraction
    elif extraction is not None:
        _fail(
            "extraction_type_invalid",
            "extraction 必须是 StructureExtraction 或 ProtocolExtractionSnapshot。",
        )

    if blocks is None or snapshot is None:
        _fail(
            "extraction_missing",
            "必须同时提供不可变结构块和提取快照，才能组装方案解构输入。",
        )
    return tuple(blocks), snapshot


def _resolve_source_spans(
    source_spans: AlignmentResult
    | Iterable[ProtocolSourceSpan]
    | Mapping[str, ProtocolSourceSpan]
    | None,
    *,
    alignment: AlignmentResult | None,
) -> tuple[ProtocolSourceSpan, ...]:
    if source_spans is not None and alignment is not None:
        _fail(
            "source_spans_ambiguous",
            "source_spans 和 alignment 只能提供一个来源对齐结果。",
        )
    value: Any = alignment if alignment is not None else source_spans
    if isinstance(value, AlignmentResult):
        spans = tuple(value.spans)
    elif isinstance(value, Mapping):
        spans = tuple(value.values())
    elif value is not None:
        try:
            spans = tuple(value)
        except TypeError as exc:
            raise ProtocolDeconstructionInputAssemblyError(
                "source_spans_type_invalid",
                "source_spans 必须是 AlignmentResult、映射或 ProtocolSourceSpan 序列。",
            ) from exc
    else:
        _fail(
            "source_spans_missing",
            "必须提供渲染对齐产出的完整 ProtocolSourceSpan 集合。",
        )

    if not spans:
        _fail("source_spans_empty", "没有来源片段，不能建立可追溯的 Agent 输入。")
    if any(not isinstance(span, ProtocolSourceSpan) for span in spans):
        _fail("source_spans_type_invalid", "来源集合中含有非 ProtocolSourceSpan 对象。")
    return spans


def _resolve_phase_graph(
    phase_detection: PhaseDetectionResult | PhaseApplicabilityGraph | None,
    *,
    phase_graph: PhaseApplicabilityGraph | None,
) -> PhaseApplicabilityGraph:
    if phase_detection is not None and phase_graph is not None:
        _fail(
            "phase_graph_ambiguous",
            "phase_detection 和 phase_graph 只能提供一个期别适用图。",
        )
    value = phase_graph if phase_graph is not None else phase_detection
    if isinstance(value, PhaseDetectionResult):
        return value.graph
    if isinstance(value, PhaseApplicabilityGraph):
        return value
    _fail(
        "phase_graph_missing",
        "必须提供已完成的整份方案期别适用图，不能在服务内猜测期别。",
    )


def _validate_source_map(
    blocks: Sequence[StructureBlock],
    spans: Sequence[ProtocolSourceSpan],
    *,
    snapshot: ProtocolExtractionSnapshot,
) -> dict[str, ProtocolSourceSpan]:
    blocks_by_ref: dict[str, StructureBlock] = {}
    for block in blocks:
        if block.source_ref in blocks_by_ref:
            _fail("source_ref_duplicate", f"结构块 source_ref 重复：{block.source_ref}")
        blocks_by_ref[block.source_ref] = block

    by_id: dict[str, ProtocolSourceSpan] = {}
    refs: dict[str, ProtocolSourceSpan] = {}
    for span in spans:
        if span.source_span_id in by_id:
            _fail("source_span_duplicate", f"来源片段 ID 重复：{span.source_span_id}")
        if span.source_ref in refs:
            _fail("source_ref_duplicate", f"来源片段 source_ref 重复：{span.source_ref}")
        if span.snapshot_id != snapshot.snapshot_id:
            _fail(
                "source_snapshot_mismatch",
                f"来源片段 {span.source_span_id} 不属于当前提取快照。",
            )
        block = blocks_by_ref.get(span.source_ref)
        if block is None:
            _fail(
                "source_block_missing",
                f"来源片段 {span.source_span_id} 找不到对应结构原文：{span.source_ref}。",
            )
        if (
            span.block_order != block.block_order
            or span.document_part != block.document_part
            or span.section_index != block.section_index
            or span.table_path != block.table_path
            or span.table_row != (block.table_path[-2] if block.table_path else None)
            or span.table_col != (block.table_path[-1] if block.table_path else None)
        ):
            _fail(
                "source_structure_mismatch",
                f"来源片段 {span.source_span_id} 的结构定位与原始结构块不一致。",
            )
        by_id[span.source_span_id] = span
        refs[span.source_ref] = span
    return by_id


def _validate_upstream_scope(
    *,
    source_artifact: ProtocolSourceArtifact,
    snapshot: ProtocolExtractionSnapshot,
    identity_decision: ProtocolIdentityDecision,
    phase_selection: StudyPhaseSelection,
    phase_graph: PhaseApplicabilityGraph,
    blocks: Sequence[StructureBlock],
    spans_by_id: Mapping[str, ProtocolSourceSpan],
) -> StudyPhase:
    if snapshot.status != ExtractionStatus.COMPLETED:
        _fail(
            "extraction_not_complete",
            f"提取快照状态为 {snapshot.status.value}，未达到可组装的完整状态。",
        )
    if snapshot.source_artifact_id != source_artifact.source_artifact_id:
        _fail("source_artifact_mismatch", "提取快照与源方案登记对象不一致。")
    if snapshot.source_sha256 != source_artifact.sha256:
        _fail("source_hash_mismatch", "提取快照与不可变源方案哈希不一致。")
    if identity_decision.status != MetadataResolutionStatus.CONFIRMED:
        _fail("identity_not_confirmed", "方案身份尚未确认，不能组装 Agent 输入。")
    if phase_selection.status != MetadataResolutionStatus.CONFIRMED:
        _fail("phase_not_confirmed", "研究期别尚未确认，不能组装 Agent 输入。")
    if identity_decision.snapshot_id != snapshot.snapshot_id:
        _fail("identity_snapshot_mismatch", "已确认方案身份不属于当前提取快照。")
    if phase_selection.snapshot_id != snapshot.snapshot_id:
        _fail("phase_snapshot_mismatch", "已确认研究期别不属于当前提取快照。")
    if identity_decision.study_phase != phase_selection.selected_phase:
        _fail("phase_identity_mismatch", "已确认身份与已确认期别不一致。")
    selected_phase = phase_selection.selected_phase
    if selected_phase == StudyPhase.OTHER:
        _fail("phase_unresolved", "本次解构必须使用已确认的 II 期、III 期或真正无缝期别。")
    if phase_graph.snapshot_id != snapshot.snapshot_id:
        _fail("phase_snapshot_mismatch", "期别适用图不属于当前提取快照。")
    if not blocks:
        _fail("structure_empty", "结构提取没有可供解构的原文块。")

    block_refs = {block.source_ref for block in blocks}
    for block in phase_graph.blocks:
        if block.snapshot_id != snapshot.snapshot_id:
            _fail("phase_block_snapshot_mismatch", f"期别图块不属于当前快照：{block.block_id}。")
        span_refs: set[str] = set()
        for span_id in block.source_span_ids:
            if span_id not in spans_by_id:
                _fail(
                    "phase_source_span_missing",
                    f"期别图块 {block.block_id} 引用了不存在的来源片段：{span_id}。",
                )
            span_refs.add(spans_by_id[span_id].source_ref)
        # Phase detection deliberately emits aggregate table nodes such as
        # ``body.t0.c0`` and ``body.t0.r1``.  Those are structural projections,
        # not extraction blocks; their child source spans are the authoritative
        # physical bridge back to the immutable structure extraction.
        if block.source_ref not in block_refs and not span_refs:
            _fail("phase_block_missing", f"期别图块找不到结构原文：{block.source_ref}。")
        if block.source_ref in block_refs and span_refs != {block.source_ref}:
            _fail(
                "phase_source_structure_mismatch",
                f"期别图块 {block.block_id} 的来源片段与结构块不一致。",
            )
    return selected_phase


def _catalog_source_ids(*catalogs: FrozenProtocolCatalog) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            span_id
            for catalog in catalogs
            for item in sorted(catalog.items, key=lambda item: item.position)
            for span_id in item.source_span_ids
        )
    )


def _validate_catalog_sources(
    catalogs: Sequence[FrozenProtocolCatalog],
    *,
    spans_by_id: Mapping[str, ProtocolSourceSpan],
    blocks_by_ref: Mapping[str, StructureBlock],
) -> frozenset[str]:
    formal_ids = formal_source_span_ids(spans_by_id.values())
    for catalog in catalogs:
        for item in catalog.items:
            if catalog.catalog_kind == CatalogKind.OFFICIAL_PARENT_RULES:
                if item.review_stage is not None:
                    _fail(
                        "catalog_review_stage_invalid",
                        f"父规则目录项 {item.item_id} 不应包含 review_stage。",
                    )
            elif catalog.catalog_kind == CatalogKind.REQUIRED_PROCEDURES:
                if item.review_stage is None:
                    _fail(
                        "catalog_review_stage_missing",
                        f"必做项目目录项 {item.item_id} 必须包含 review_stage。",
                    )
            missing = [span_id for span_id in item.source_span_ids if span_id not in spans_by_id]
            if missing:
                _fail(
                    "catalog_source_span_missing",
                    f"冻结目录项 {item.item_id} 引用了不存在的来源片段：{'、'.join(missing)}。",
                )
            non_formal = set(item.source_span_ids) - formal_ids
            if non_formal:
                _fail(
                    "catalog_item_without_formal_source",
                    f"冻结目录项 {item.item_id} 含有非正式或非唯一来源定位："
                    f"{'、'.join(sorted(non_formal))}；"
                    "降级页提示或结构块定位不能作为唯一依据。",
                )
            for span_id in item.source_span_ids:
                span = spans_by_id[span_id]
                if span.precision == SourceLocatorPrecision.TEXT_RANGE:
                    block = blocks_by_ref.get(span.source_ref)
                    if block is None or not span.excerpt or span.excerpt not in block.text:
                        _fail(
                            "catalog_source_locator_invalid",
                            f"冻结目录项 {item.item_id} 的正式摘录无法在结构原文中逐字核验。",
                        )
    return formal_ids


def _projection_text_by_span(
    projection: PhaseProjection,
) -> dict[str, str]:
    projected: dict[str, str] = {}
    for block in projection.blocks:
        if block.projection_text is None:
            continue
        for span_id in block.source_span_ids:
            prior = projected.get(span_id)
            if prior is not None and prior != block.projection_text:
                _fail(
                    "projection_source_ambiguous",
                    f"来源片段 {span_id} 对应多个不一致的单期期别投影文本。",
                )
            projected[span_id] = block.projection_text
    return projected


def _build_source_materials(
    source_ids: Sequence[str],
    *,
    spans_by_id: Mapping[str, ProtocolSourceSpan],
    blocks_by_ref: Mapping[str, StructureBlock],
    projection: PhaseProjection,
) -> list[ProtocolSourceMaterial]:
    projected_text = _projection_text_by_span(projection)
    materials: list[ProtocolSourceMaterial] = []
    for span_id in source_ids:
        span = spans_by_id.get(span_id)
        if span is None:
            _fail("catalog_source_span_missing", f"目录引用了不存在的来源片段：{span_id}。")
        block = blocks_by_ref.get(span.source_ref)
        if block is None:
            _fail("source_block_missing", f"来源片段没有对应的结构原文：{span.source_ref}。")
        source_text = block.text
        if not source_text.strip():
            # A table root is a legitimate formal structural anchor but its
            # own StructureBlock intentionally has no prose.  Preserve the
            # root's structural original by joining its immutable descendants
            # in source order; do not fall back to the whole protocol.
            prefix = f"{block.source_ref}."
            descendants = sorted(
                (
                    candidate
                    for candidate in blocks_by_ref.values()
                    if candidate.source_ref.startswith(prefix) and candidate.text.strip()
                ),
                key=lambda candidate: (candidate.block_order, candidate.source_ref),
            )
            source_text = "\n".join(candidate.text for candidate in descendants)
        if not source_text.strip():
            _fail(
                "source_material_empty",
                f"目录来源片段 {span_id} 对应的结构原文为空，不能发送给方案解构。",
            )
        materials.append(
            ProtocolSourceMaterial(
                source_span_id=span.source_span_id,
                source_ref=span.source_ref,
                block_order=block.block_order,
                text=source_text,
                projection_text=projected_text.get(span.source_span_id),
            )
        )
    materials.sort(key=lambda item: (item.block_order, item.source_ref, item.source_span_id))
    return materials


class ProtocolDeconstructionInputAssembler:
    """Build one deterministic, minimal and runner-ready input package."""

    def __init__(
        self,
        *,
        frozen_at: datetime | None = None,
        frozen_by: str = _DEFAULT_FROZEN_BY,
    ) -> None:
        self._frozen_at = frozen_at
        self._frozen_by = frozen_by

    def _validate_interpretation_sources(
        self,
        sources: Sequence[InterpretationSource],
        *,
        protocol_version_id: str,
    ) -> list[InterpretationSource]:
        """解释来源必须绑定本次方案版本，且由仓储校验后整体进入输入包。"""

        seen: set[str] = set()
        for source in sources:
            if not isinstance(source, InterpretationSource):
                _fail(
                    "interpretation_source_type_invalid",
                    "解释来源必须是经仓储校验的 InterpretationSource 对象。",
                )
            if source.protocol_version_id != protocol_version_id:
                _fail(
                    "interpretation_protocol_mismatch",
                    f"解释来源 {source.interpretation_source_id} 绑定的方案版本"
                    "与本次解构不一致，不能带入输入包。",
                )
            if source.interpretation_source_id in seen:
                _fail(
                    "interpretation_source_duplicate",
                    f"解释来源 {source.interpretation_source_id} 重复。",
                )
            seen.add(source.interpretation_source_id)
        return list(sources)

    def assemble(
        self,
        *,
        project_id: str,
        protocol_version_id: str,
        source_artifact: ProtocolSourceArtifact,
        extraction: StructureExtraction | ProtocolExtractionSnapshot | None = None,
        blocks: Sequence[StructureBlock] | None = None,
        snapshot: ProtocolExtractionSnapshot | None = None,
        source_spans: AlignmentResult
        | Iterable[ProtocolSourceSpan]
        | Mapping[str, ProtocolSourceSpan]
        | None = None,
        alignment: AlignmentResult | None = None,
        phase_detection: PhaseDetectionResult | PhaseApplicabilityGraph | None = None,
        phase_graph: PhaseApplicabilityGraph | None = None,
        identity_decision: ProtocolIdentityDecision,
        phase_selection: StudyPhaseSelection,
        interpretation_sources: Sequence[InterpretationSource] = (),
        frozen_at: datetime | None = None,
        frozen_by: str | None = None,
    ) -> ProtocolDeconstructionInputPackage:
        resolved_blocks, resolved_snapshot = _resolve_extraction(
            extraction,
            blocks=blocks,
            snapshot=snapshot,
        )
        resolved_spans = _resolve_source_spans(source_spans, alignment=alignment)
        resolved_graph = _resolve_phase_graph(phase_detection, phase_graph=phase_graph)
        spans_by_id = _validate_source_map(
            resolved_blocks,
            resolved_spans,
            snapshot=resolved_snapshot,
        )
        selected_phase = _validate_upstream_scope(
            source_artifact=source_artifact,
            snapshot=resolved_snapshot,
            identity_decision=identity_decision,
            phase_selection=phase_selection,
            phase_graph=resolved_graph,
            blocks=resolved_blocks,
            spans_by_id=spans_by_id,
        )
        validated_interpretation_sources = self._validate_interpretation_sources(
            interpretation_sources,
            protocol_version_id=protocol_version_id,
        )
        effective_frozen_at = self._frozen_at if frozen_at is None else frozen_at
        effective_frozen_by = self._frozen_by if frozen_by is None else frozen_by

        try:
            projection = project_single_phase(resolved_graph, selected_phase)
            section_index = build_section_index(
                resolved_blocks,
                resolved_graph,
                tuple(spans_by_id.values()),
            )
            parent_catalog = freeze_official_parent_rules(
                section_index,
                selected_phase,
                source_spans=tuple(spans_by_id.values()),
                frozen_at=effective_frozen_at,
                frozen_by=effective_frozen_by,
            )
            required_catalog = build_required_procedure_catalog(
                resolved_blocks,
                phase_projection=projection,
                source_spans=tuple(spans_by_id.values()),
                selected_phase=selected_phase,
                snapshot_id=resolved_snapshot.snapshot_id,
                frozen_at=effective_frozen_at,
                frozen_by=effective_frozen_by,
            )
        except ProtocolDeconstructionInputAssemblyError:
            raise
        except Exception as exc:
            # Keep upstream deterministic builder codes in the exception text,
            # but expose one stable service-level failure category to callers.
            if getattr(exc, "code", None) == "source_coverage_missing":
                _fail(
                    "catalog_item_without_formal_source",
                    f"冻结方案目录失败：{exc}；目录项缺少正式、唯一的物理来源定位。",
                )
            _fail("catalog_build_failed", f"冻结方案目录失败：{exc}")

        blocks_by_ref = {block.source_ref: block for block in resolved_blocks}
        _validate_catalog_sources(
            (parent_catalog, required_catalog),
            spans_by_id=spans_by_id,
            blocks_by_ref=blocks_by_ref,
        )
        catalog_source_ids = _catalog_source_ids(parent_catalog, required_catalog)
        materials = _build_source_materials(
            catalog_source_ids,
            spans_by_id=spans_by_id,
            blocks_by_ref=blocks_by_ref,
            projection=projection,
        )
        if not materials or {item.source_span_id for item in materials} != set(catalog_source_ids):
            _fail(
                "catalog_material_coverage",
                "发送给方案解构的原文材料没有完整覆盖两份冻结目录的来源片段。",
            )

        try:
            source_input = ProtocolDeconstructionInput(
                project_id=project_id,
                protocol_version_id=protocol_version_id,
                protocol_file_sha256=source_artifact.sha256,
                extraction_snapshot_id=resolved_snapshot.snapshot_id,
                phase_projection_id=projection.projection_id,
                selected_phase=selected_phase,
                identity_decision=identity_decision,
                phase_selection=phase_selection,
                allowed_source_span_ids=[item.source_span_id for item in materials],
                source_materials=materials,
                parent_rule_catalog=parent_catalog,
                required_procedure_catalog=required_catalog,
                interpretation_source_ids=[item.interpretation_source_id for item in validated_interpretation_sources],
                interpretation_sources=validated_interpretation_sources,
            )
        except Exception as exc:
            _fail("input_contract_invalid", f"方案解构输入合同校验失败：{exc}")

        # The mapping is complete for runner-side physical uniqueness checks;
        # the package and its map cannot be mutated by a downstream caller.
        frozen_source_spans = MappingProxyType(dict(spans_by_id))
        return ProtocolDeconstructionInputPackage(
            source_input=source_input,
            source_spans=frozen_source_spans,
            projection=projection,
            parent_rule_catalog=parent_catalog,
            required_procedure_catalog=required_catalog,
        )


def assemble_protocol_deconstruction_input(
    **kwargs: Any,
) -> ProtocolDeconstructionInputPackage:
    """Functional entry point for one-shot input package assembly."""

    return ProtocolDeconstructionInputAssembler().assemble(**kwargs)


assemble_deconstruction_input_package = assemble_protocol_deconstruction_input
build_protocol_deconstruction_input_package = assemble_protocol_deconstruction_input


__all__ = [
    "DeconstructionInputAssemblyError",
    "ProtocolDeconstructionInputAssembler",
    "ProtocolDeconstructionInputAssemblyError",
    "ProtocolDeconstructionInputPackage",
    "ProtocolInputAssemblyError",
    "assemble_deconstruction_input_package",
    "assemble_protocol_deconstruction_input",
    "build_protocol_deconstruction_input_package",
]
