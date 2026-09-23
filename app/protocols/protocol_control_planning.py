"""Deterministic planning for Phase 5.8 cross-section control batches.

This module is intentionally model-free.  It turns the frozen full-protocol
coverage manifest into bounded, source-closed work packets.  Every manifest
unit has one and only one owner; neighboring units may be repeated only in the
read-only context portion of a packet.  Frozen official/procedure catalogs are
copied into every packet as known relation targets, so a future Agent cannot
invent an identity or an official IN/EX/REQ number.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.domain.contracts.enums import CatalogKind
from app.domain.contracts.protocol_controls import (
    KnownOfficialRuleTarget,
    KnownRequiredProcedureTarget,
    ProtocolControlDiscoveryBatch,
    ProtocolControlDiscoveryDecision,
    ProtocolControlDiscoveryDisposition,
    ProtocolControlDiscoveryPlan,
    ProtocolControlDiscoveryToDeepPlan,
    KnownWorkflowStageTarget,
    ProtocolControlBatchPlan,
    ProtocolControlDispositionBatch,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    stable_protocol_control_discovery_batch_id,
    stable_protocol_control_manifest_structure_unit_ids_sha256,
    stable_protocol_control_batch_id,
)
from app.domain.contracts.protocol_ingestion import FrozenProtocolCatalog
from app.domain.contracts.rules import WorkflowStage
from app.protocols.adaptive_batch_budget import (
    AdaptiveBatchBudget,
    AdaptiveBatchPlanningError,
    pack_structure_units_by_budget,
)

__all__ = [
    "DEFAULT_PROTOCOL_CONTROL_DISCOVERY_BATCH_UNITS",
    "ProtocolControlPlanningError",
    "AdaptiveBatchBudget",
    "build_protocol_control_deep_plan",
    "build_protocol_control_discovery_plan",
    "build_protocol_control_batch_plan",
    "build_protocol_control_batches",
    "detect_required_action_kinds",
    "plan_protocol_control_batches",
    "plan_protocol_control_deep_batches_from_discovery",
    "plan_protocol_control_discovery",
    "validate_protocol_control_deep_selection",
    "validate_protocol_control_discovery_results",
]


DEFAULT_PROTOCOL_CONTROL_DISCOVERY_BATCH_UNITS = 48


_REQUIRED_ACTION_PATTERNS = (
    (
        "preserve_exemption_condition",
        re.compile(
            r"(?:无需|不需要|不要求|可免(?:除)?|"
            r"\b(?:not\s+required|need\s+not)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "collect_biospecimen",
        re.compile(
            r"(?:采集|收集|留取)"
            r"(?:用于[^，。；]{0,16}的)?(?:参与者的|受试者的)?"
            r"(?:样品|样本|标本|血样|尿样)"
        ),
    ),
    (
        "follow_specified_procedure",
        re.compile(
            r"(?:应|须|需|必须).{0,12}(?:根据|按照|遵循).{0,24}"
            r"(?:标准|规定|要求).{0,16}(?:程序|流程|方法|操作)"
        ),
    ),
    (
        "explain_information",
        re.compile(
            r"(?:解释|告知|说明).{0,24}(?:研究|试验).{0,24}"
            r"(?:程序|信息|要求|限制)|"
            r"解释.{0,24}(?:ICF|知情同意书).{0,24}(?:内容|信息)"
        ),
    ),
    (
        "communicate_with_participant",
        re.compile(
            r"(?:告知|说明|提醒).{0,24}(?:参与者|受试者)|"
            r"(?:参与者|受试者).{0,24}(?:告知|说明|提醒)"
        ),
    ),
    (
        "obtain_signature",
        re.compile(
            r"(?:(?:获得|获取|取得).{0,16})?"
            r"(?:参与者|受试者).{0,32}(?:自愿)?(?:签署|签名)"
        ),
    ),
    (
        "witness_consent",
        re.compile(
            r"(?:公正)?见证人.{0,32}(?:见证知情同意|见证.{0,12}签署)|"
            r"(?:见证知情同意|见证.{0,12}签署).{0,32}(?:公正)?见证人"
        ),
    ),
    (
        "allow_informed_decision_time",
        re.compile(
            r"签署.{0,12}(?:之前|前).{0,48}(?:充分的?)?(?:时间|机会)"
        ),
    ),
    (
        "record_signature_date",
        re.compile(r"(?:签名|签署).{0,16}(?:并)?注明日期"),
    ),
    (
        "record_signer_relationship",
        re.compile(
            r"(?:非|不是).{0,16}(?:参与者|受试者)本人签署.{0,20}注明关系|"
            r"(?:代签|监护人签署).{0,20}注明关系"
        ),
    ),
    (
        "collect_data",
        re.compile(
            r"(?:采集|获取|收集).{0,20}"
            r"(?:人口学|病史|用药史|治疗史|数据|资料|信息)"
        ),
    ),
    (
        "perform_height_measurement",
        re.compile(
            r"(?:进行|执行|完成|测量).{0,10}身高(?:测量)?|"
            r"身高(?:和|及|、)?体重.{0,8}测量"
        ),
    ),
    (
        "perform_weight_measurement",
        re.compile(
            r"(?:进行|执行|完成|测量).{0,10}体重(?:测量)?|"
            r"身高(?:和|及|、)?体重.{0,8}测量"
        ),
    ),
    (
        "prepare_participant",
        re.compile(
            r"(?:参与者|受试者).{0,28}"
            r"(?:静息|安静休息|休息|脱掉|脱去|摘掉|取下|排空膀胱)"
        ),
    ),
    (
        "verify_vital_sign_components",
        re.compile(
            r"(?=[^。；\n]{0,180}(?:血压|收缩压|舒张压))"
            r"(?=[^。；\n]{0,180}脉[搏博])"
            r"(?=[^。；\n]{0,180}体温)"
            r"(?=[^。；\n]{0,180}呼吸频率)"
            r"[^。；\n]{0,48}生命体征(?:检查|记录)?[^。；\n]{0,180}"
        ),
    ),
    (
        "sequence_before_related_procedure",
        re.compile(
            r"(?:应|须|需|必须|建议|推荐|尽可能|尽量|尽力)"
            r".{0,40}(?:在|于).{0,48}(?:之前|前).{0,16}"
            r"(?:完成|进行|执行|采集|测量|检查)|"
            r"\b(?:should|must|recommended|best\s+effort)\b"
            r".{0,64}\bbefore\b.{0,32}"
            r"(?:complete|perform|collect|measure|test)",
            re.IGNORECASE,
        ),
    ),
    (
        "position_participant",
        re.compile(
            r"(?:参与者|受试者).{0,32}"
            r"(?:站在|站立|站直|平视|仰头|双脚|膝盖|脚后跟)"
        ),
    ),
    (
        "use_calibrated_device",
        re.compile(
            r"(?:校准过的|经校准的|已校准的).{0,16}"
            r"(?:测量板|测量器|秤|称|设备|仪器)"
        ),
    ),
    (
        "operate_measurement_device",
        re.compile(
            r"(?:移动|调节|操作).{0,20}"
            r"(?:测量臂|仪器|测量器|设备)|"
            r"(?:测量臂|仪器|测量器|设备).{0,20}"
            r"(?:移动|调节|操作)"
        ),
    ),
    (
        "record_with_precision",
        re.compile(
            r"(?:记录.{0,40})?(?:单位为.{0,16})?"
            r"保留(?:整数|小数点后\s*\d+\s*位)"
        ),
    ),
    (
        "perform_ecg",
        re.compile(
            r"(?:进行|执行|完成|测量).{0,16}(?:12\s*[-‑]?导联)?心电图|"
            r"(?:12\s*[-‑]?导联)?心电图.{0,8}(?:检查|检测|测量)"
        ),
    ),
    (
        "record_ecg_measurements",
        re.compile(
            r"记录.{0,64}(?:心电图诊断|心率|PR间期|RR间期|QRS|QT间期)",
            re.IGNORECASE,
        ),
    ),
    (
        # Compatibility action key retained for existing gate metadata; the
        # detector is intentionally formula-agnostic and never names a metric.
        "calculate_qtcf",
        re.compile(
            r"(?:应用|根据|采用|按).{0,20}(?:公式|方法).{0,24}(?:计算|校正)|"
            r"(?:公式|方法).{0,24}(?:计算|校正)|"
            r"(?:计算|校正).{0,24}(?:公式|方法)",
            re.IGNORECASE,
        ),
    ),
)


class ProtocolControlPlanningError(ValueError):
    """Stable deterministic planning failure raised before any Agent call."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def detect_required_action_kinds(text: str) -> tuple[str, ...]:
    """Freeze source-backed action predicates before semantic disposition.

    These stable, project-neutral action names are gate-only metadata. They
    are intentionally absent from the Agent prompt so the validator can catch
    a model that discards an action merely because it is recommended,
    best-effort, or surrounded by a procedure category that already exists in
    a catalog. ``required`` in the compatibility name means the action must be
    preserved, not that its completion modality is mandatory.
    """

    return tuple(
        sorted(
            action_kind
            for action_kind, pattern in _REQUIRED_ACTION_PATTERNS
            if pattern.search(text)
        )
    )


def _catalog_targets(
    catalog: FrozenProtocolCatalog | None,
    *,
    expected_kind: CatalogKind,
    coverage: ProtocolSectionCoverageManifest,
) -> tuple[KnownOfficialRuleTarget, ...] | tuple[KnownRequiredProcedureTarget, ...]:
    if catalog is None:
        return ()
    if catalog.catalog_kind != expected_kind:
        raise ProtocolControlPlanningError(
            "catalog_kind_mismatch",
            f"冻结目录类型不是 {expected_kind.value}。",
        )
    if catalog.snapshot_id != coverage.snapshot_id:
        raise ProtocolControlPlanningError(
            "catalog_snapshot_mismatch",
            "冻结目录与全文覆盖清单不属于同一提取快照。",
        )
    if catalog.study_phase != coverage.study_phase:
        raise ProtocolControlPlanningError(
            "catalog_phase_mismatch",
            "冻结目录与全文覆盖清单期别不一致。",
        )

    items = sorted(catalog.items, key=lambda item: (item.position, item.item_id))
    if expected_kind == CatalogKind.OFFICIAL_PARENT_RULES:
        targets: list[KnownOfficialRuleTarget] = []
        for item in items:
            if not item.official_code:
                raise ProtocolControlPlanningError(
                    "official_target_identity_missing",
                    f"官方冻结目录项缺少 official_code：{item.item_id}。",
                )
            source_pairs = (
                sorted(zip(item.source_span_ids, item.source_excerpts, strict=True))
                if item.source_excerpts
                else []
            )
            if source_pairs:
                span_ids = [span_id for span_id, _ in source_pairs]
                excerpts = [excerpt for _, excerpt in source_pairs]
            else:
                span_ids = list(item.source_span_ids)
                excerpts = list(item.source_excerpts)
            targets.append(
                KnownOfficialRuleTarget(
                    catalog_item_id=item.item_id,
                    official_code=item.official_code,
                    label=item.label,
                    position=item.position,
                    source_span_ids=span_ids,
                    source_excerpts=excerpts,
                )
            )
        return tuple(targets)

    if expected_kind == CatalogKind.REQUIRED_PROCEDURES:
        procedure_targets: list[KnownRequiredProcedureTarget] = []
        for item in items:
            if item.visit_instance is None or item.review_stage is None:
                raise ProtocolControlPlanningError(
                    "procedure_target_identity_missing",
                    f"必做项目冻结目录项缺少访视或审核阶段：{item.item_id}。",
                )
            source_pairs = (
                sorted(zip(item.source_span_ids, item.source_excerpts, strict=True))
                if item.source_excerpts
                else []
            )
            if source_pairs:
                span_ids = [span_id for span_id, _ in source_pairs]
                excerpts = [excerpt for _, excerpt in source_pairs]
            else:
                span_ids = list(item.source_span_ids)
                excerpts = list(item.source_excerpts)
            procedure_targets.append(
                KnownRequiredProcedureTarget(
                    catalog_item_id=item.item_id,
                    label=item.label,
                    visit_instance=item.visit_instance,
                    review_stage=item.review_stage,
                    position=item.position,
                    source_span_ids=span_ids,
                    source_excerpts=excerpts,
                )
            )
        return tuple(procedure_targets)

    raise ProtocolControlPlanningError(
        "catalog_kind_unsupported",
        f"不支持的冻结目录类型：{expected_kind.value}。",
    )


def _workflow_stage_targets(
    workflow_stages: Sequence[WorkflowStage] | None,
) -> tuple[KnownWorkflowStageTarget, ...]:
    if not workflow_stages:
        return ()
    targets: list[KnownWorkflowStageTarget] = []
    seen: set[str] = set()
    for stage in workflow_stages:
        if stage.workflow_stage_id in seen:
            raise ProtocolControlPlanningError(
                "workflow_stage_duplicate",
                f"workflow_stage_id 重复：{stage.workflow_stage_id}。",
            )
        seen.add(stage.workflow_stage_id)
        targets.append(
            KnownWorkflowStageTarget(
                workflow_stage_id=stage.workflow_stage_id,
                review_stage=stage.stage,
                display_name=stage.display_name,
                visit_instance=stage.visit_instance,
                visit_window=stage.visit_window,
            )
        )
    return tuple(targets)


def _validate_procedure_stage_reconciliation(
    procedure_targets: Sequence[KnownRequiredProcedureTarget],
    workflow_stage_targets: Sequence[KnownWorkflowStageTarget],
) -> None:
    if not workflow_stage_targets:
        return
    stage_keys = {
        (target.review_stage, target.visit_instance)
        for target in workflow_stage_targets
    }
    for procedure in procedure_targets:
        key = (procedure.review_stage, procedure.visit_instance)
        if key not in stage_keys:
            raise ProtocolControlPlanningError(
                "procedure_workflow_stage_unresolved",
                "流程必做目标无法与本批次已知流程节点的审核阶段和访视实例对应。",
            )


def _ordered_units(
    coverage_manifest: ProtocolSectionCoverageManifest,
) -> tuple[ProtocolStructureUnit, ...]:
    return tuple(
        sorted(
            coverage_manifest.units,
            key=lambda unit: (unit.source_order, unit.structure_unit_id),
        )
    )


def _heading_runs(
    units: Sequence[ProtocolStructureUnit],
) -> tuple[tuple[ProtocolStructureUnit, ...], ...]:
    runs: list[list[ProtocolStructureUnit]] = []
    for unit in units:
        heading = tuple(unit.heading_path)
        if not runs or tuple(runs[-1][0].heading_path) != heading:
            runs.append([])
        runs[-1].append(unit)
    return tuple(tuple(run) for run in runs)


def plan_protocol_control_batches(
    coverage_manifest: ProtocolSectionCoverageManifest,
    official_parent_catalog: FrozenProtocolCatalog | None = None,
    required_procedure_catalog: FrozenProtocolCatalog | None = None,
    *,
    max_owned_units_per_batch: int = 12,
    max_batch_size: int | None = None,
    context_radius: int = 1,
    prioritize_keyword_rank: bool = False,
    workflow_stages: Sequence[WorkflowStage] | None = None,
) -> ProtocolControlBatchPlan:
    """Build deterministic bounded work packets for all manifest units.

    ``max_owned_units_per_batch`` counts only units that the Agent may dispose.
    ``context_radius`` adds nearest same-heading units as read-only context and
    never changes ownership.  ``prioritize_keyword_rank`` is retained as a
    compatibility parameter; priority is exposed on each batch as a scheduling
    hint, while canonical source order always controls batch identity.
    """

    del prioritize_keyword_rank  # compatibility only; source order owns identity
    if max_batch_size is not None:
        if (
            max_owned_units_per_batch != 12
            and max_owned_units_per_batch != max_batch_size
        ):
            raise ProtocolControlPlanningError(
                "batch_size_ambiguous",
                "max_owned_units_per_batch 与 max_batch_size 不一致。",
            )
        max_owned_units_per_batch = max_batch_size
    if max_owned_units_per_batch < 1:
        raise ProtocolControlPlanningError(
            "batch_size_invalid",
            "max_owned_units_per_batch 必须为正整数。",
        )
    if context_radius < 0:
        raise ProtocolControlPlanningError(
            "context_radius_invalid",
            "context_radius 不能为负数。",
        )

    units = _ordered_units(coverage_manifest)
    official_targets = _catalog_targets(
        official_parent_catalog,
        expected_kind=CatalogKind.OFFICIAL_PARENT_RULES,
        coverage=coverage_manifest,
    )
    procedure_targets = _catalog_targets(
        required_procedure_catalog,
        expected_kind=CatalogKind.REQUIRED_PROCEDURES,
        coverage=coverage_manifest,
    )
    workflow_stage_targets = _workflow_stage_targets(workflow_stages)
    _validate_procedure_stage_reconciliation(
        procedure_targets,
        workflow_stage_targets,
    )

    chunks: list[
        tuple[tuple[ProtocolStructureUnit, ...], tuple[ProtocolStructureUnit, ...]]
    ] = []
    for run in _heading_runs(units):
        for start in range(0, len(run), max_owned_units_per_batch):
            owned = tuple(run[start : start + max_owned_units_per_batch])
            end = start + len(owned)
            context: list[ProtocolStructureUnit] = []
            if context_radius:
                context.extend(run[max(0, start - context_radius) : start])
                context.extend(run[end : min(len(run), end + context_radius)])
            chunks.append((owned, tuple(context)))

    total = len(chunks)
    batches: list[ProtocolControlDispositionBatch] = []
    for number, (owned, context) in enumerate(chunks, start=1):
        owned_ids = [unit.structure_unit_id for unit in owned]
        owned_spans = sorted({span for unit in owned for span in unit.source_span_ids})
        context_spans = sorted(
            {span for unit in context for span in unit.source_span_ids}
        )
        batches.append(
            ProtocolControlDispositionBatch(
                batch_id=stable_protocol_control_batch_id(
                    coverage_manifest.manifest_id,
                    number,
                    owned_ids,
                ),
                coverage_manifest_id=coverage_manifest.manifest_id,
                protocol_version_id=coverage_manifest.protocol_version_id,
                study_phase=coverage_manifest.study_phase,
                batch_number=number,
                batch_total=total,
                priority_rank=max(unit.priority_rank for unit in owned),
                owned_units=list(owned),
                context_units=list(context),
                owned_structure_unit_ids=owned_ids,
                context_structure_unit_ids=[unit.structure_unit_id for unit in context],
                owned_source_span_ids=owned_spans,
                context_source_span_ids=context_spans,
                owned_required_action_kinds_by_structure_unit_id={
                    unit.structure_unit_id: list(action_kinds)
                    for unit in owned
                    if (action_kinds := detect_required_action_kinds(unit.excerpt))
                },
                known_official_targets=list(official_targets),
                known_procedure_targets=list(procedure_targets),
                known_workflow_stage_targets=list(workflow_stage_targets),
            )
        )

    expected_ids = [unit.structure_unit_id for unit in units]
    plan_id = "pcp-" + stable_protocol_control_batch_id(
        coverage_manifest.manifest_id,
        len(batches),
        [batch.batch_id for batch in batches],
    ).removeprefix("pcb-")
    return ProtocolControlBatchPlan(
        plan_id=plan_id,
        coverage_manifest_id=coverage_manifest.manifest_id,
        protocol_version_id=coverage_manifest.protocol_version_id,
        study_phase=coverage_manifest.study_phase,
        max_owned_units_per_batch=max_owned_units_per_batch,
        context_radius=context_radius,
        expected_structure_unit_ids=expected_ids,
        batches=batches,
    )


build_protocol_control_batch_plan = plan_protocol_control_batches
build_protocol_control_batches = plan_protocol_control_batches


def plan_protocol_control_discovery(
    coverage_manifest: ProtocolSectionCoverageManifest,
    *,
    max_units_per_batch: int = DEFAULT_PROTOCOL_CONTROL_DISCOVERY_BATCH_UNITS,
    context_radius: int = 1,
    batch_budget: AdaptiveBatchBudget | None = None,
) -> ProtocolControlDiscoveryPlan:
    """Plan bounded, exactly-once coarse discovery over the full manifest.

    When ``batch_budget`` is provided, packs are sized by estimated input tokens
    and per-unit output budget instead of a fixed unit count. Fixed packing
    remains available for compatibility and tests.
    """

    if max_units_per_batch < 1:
        raise ProtocolControlPlanningError(
            "discovery_batch_size_invalid",
            "max_units_per_batch 必须为正整数。",
        )
    if context_radius < 0:
        raise ProtocolControlPlanningError(
            "discovery_context_radius_invalid",
            "context_radius 不能为负数。",
        )

    units = _ordered_units(coverage_manifest)
    chunks: list[
        tuple[tuple[ProtocolStructureUnit, ...], tuple[ProtocolStructureUnit, ...]]
    ] = []
    if batch_budget is not None:
        try:
            effective = AdaptiveBatchBudget(
                max_input_tokens=batch_budget.max_input_tokens,
                max_output_tokens=batch_budget.max_output_tokens,
                output_tokens_per_unit=batch_budget.output_tokens_per_unit,
                template_overhead_tokens=batch_budget.template_overhead_tokens,
                chars_per_token=batch_budget.chars_per_token,
                max_units_hard_cap=min(
                    batch_budget.max_units_hard_cap, max_units_per_batch
                ),
                min_units=batch_budget.min_units,
                per_unit_json_overhead_chars=batch_budget.per_unit_json_overhead_chars,
            )
            packs = pack_structure_units_by_budget(
                units,
                budget=effective,
                context_radius=context_radius,
                group_by_heading=False,
            )
        except AdaptiveBatchPlanningError as exc:
            raise ProtocolControlPlanningError(exc.code, str(exc)) from exc
        chunks = [(pack.owned_units, pack.context_units) for pack in packs]
        max_units_per_batch = max(
            max((len(owned) for owned, _ in chunks), default=1),
            effective.max_units_hard_cap,
        )
    else:
        context_by_unit_id: dict[str, tuple[ProtocolStructureUnit, ...]] = {}
        for run in _heading_runs(units):
            for position, unit in enumerate(run):
                context_by_unit_id[unit.structure_unit_id] = tuple(
                    run[max(0, position - context_radius) : position]
                ) + tuple(run[position + 1 : position + context_radius + 1])

        for start in range(0, len(units), max_units_per_batch):
            target = tuple(units[start : start + max_units_per_batch])
            target_ids = {unit.structure_unit_id for unit in target}
            context_by_id = {
                context.structure_unit_id: context
                for unit in target
                for context in context_by_unit_id[unit.structure_unit_id]
                if context.structure_unit_id not in target_ids
            }
            context = tuple(
                sorted(
                    context_by_id.values(),
                    key=lambda unit: (unit.source_order, unit.structure_unit_id),
                )
            )
            chunks.append((target, context))

    batch_total = len(chunks)
    batches: list[ProtocolControlDiscoveryBatch] = []
    for number, (target, context) in enumerate(chunks, start=1):
        target_ids_list = [unit.structure_unit_id for unit in target]
        context_ids = [unit.structure_unit_id for unit in context]
        batches.append(
            ProtocolControlDiscoveryBatch(
                discovery_batch_id=stable_protocol_control_discovery_batch_id(
                    coverage_manifest.manifest_id,
                    number,
                    target_ids_list,
                ),
                coverage_manifest_id=coverage_manifest.manifest_id,
                protocol_version_id=coverage_manifest.protocol_version_id,
                study_phase=coverage_manifest.study_phase,
                batch_number=number,
                batch_total=batch_total,
                target_units=list(target),
                context_units=list(context),
                target_structure_unit_ids=target_ids_list,
                context_structure_unit_ids=context_ids,
                target_source_span_ids=sorted(
                    {
                        span_id
                        for unit in target
                        for span_id in unit.source_span_ids
                    }
                ),
                context_source_span_ids=sorted(
                    {
                        span_id
                        for unit in context
                        for span_id in unit.source_span_ids
                    }
                ),
            )
        )

    expected_ids = [unit.structure_unit_id for unit in units]
    plan_id = "pcd-" + stable_protocol_control_discovery_batch_id(
        coverage_manifest.manifest_id,
        len(batches),
        [batch.discovery_batch_id for batch in batches],
    ).removeprefix("pcd-")
    return ProtocolControlDiscoveryPlan(
        plan_id=plan_id,
        coverage_manifest_id=coverage_manifest.manifest_id,
        protocol_version_id=coverage_manifest.protocol_version_id,
        protocol_document_sha256=coverage_manifest.protocol_document_sha256,
        snapshot_id=coverage_manifest.snapshot_id,
        study_phase=coverage_manifest.study_phase,
        manifest_structure_unit_count=len(expected_ids),
        manifest_structure_unit_ids_sha256=(
            stable_protocol_control_manifest_structure_unit_ids_sha256(expected_ids)
        ),
        expected_structure_unit_ids=expected_ids,
        max_units_per_batch=max_units_per_batch,
        context_radius=context_radius,
        batches=batches,
    )


def validate_protocol_control_deep_selection(
    decisions: Sequence[ProtocolControlDiscoveryDecision],
    selected_structure_unit_ids: Sequence[str],
) -> tuple[str, ...]:
    """Ensure deep ownership is exactly the candidate/uncertain set."""

    decision_by_id = {
        decision.structure_unit_id: decision for decision in decisions
    }
    expected_deep_ids = [
        decision.structure_unit_id
        for decision in decisions
        if decision.disposition
        in {
            ProtocolControlDiscoveryDisposition.CANDIDATE,
            ProtocolControlDiscoveryDisposition.UNCERTAIN,
        }
    ]
    selected = list(selected_structure_unit_ids)
    if any(unit_id not in decision_by_id for unit_id in selected):
        raise ProtocolControlPlanningError(
            "deep_selection_unknown_unit",
            "深析选择包含完整发现处置之外的结构单元。",
        )
    if sorted(selected) != sorted(expected_deep_ids):
        missing_uncertain = [
            unit_id
            for unit_id in expected_deep_ids
            if decision_by_id[unit_id].disposition
            == ProtocolControlDiscoveryDisposition.UNCERTAIN
            and unit_id not in selected
        ]
        if missing_uncertain:
            raise ProtocolControlPlanningError(
                "uncertain_requires_deep_analysis",
                "uncertain 处置必须进入深析，不得被丢弃。",
            )
        extra = [unit_id for unit_id in selected if unit_id not in expected_deep_ids]
        if extra:
            raise ProtocolControlPlanningError(
                "non_deep_unit_owned",
                "非候选/不确定单元不得进入深析拥有集合。",
            )
        raise ProtocolControlPlanningError(
            "deep_selection_mismatch",
            "深析选择必须恰好等于候选与不确定单元集合。",
        )
    return tuple(expected_deep_ids)


def validate_protocol_control_discovery_results(
    discovery_plan: ProtocolControlDiscoveryPlan,
    batch_decisions: Sequence[Sequence[ProtocolControlDiscoveryDecision]],
) -> tuple[ProtocolControlDiscoveryDecision, ...]:
    """Deterministically close every discovery target and context reference."""

    if len(batch_decisions) != len(discovery_plan.batches):
        raise ProtocolControlPlanningError(
            "discovery_batch_result_incomplete",
            "发现结果必须逐批返回且不得缺批。",
        )
    expected_ids = discovery_plan.expected_structure_unit_ids
    expected_manifest_hash = stable_protocol_control_manifest_structure_unit_ids_sha256(
        expected_ids
    )
    if (
        discovery_plan.manifest_structure_unit_count != len(expected_ids)
        or discovery_plan.manifest_structure_unit_ids_sha256 != expected_manifest_hash
    ):
        raise ProtocolControlPlanningError(
            "discovery_plan_manifest_invalid",
            "发现计划完整清单计数或身份哈希无效。",
        )
    decisions: list[ProtocolControlDiscoveryDecision] = []
    decision_by_id: dict[str, ProtocolControlDiscoveryDecision] = {}
    expected_set = set(expected_ids)
    for batch, raw_decisions in zip(
        discovery_plan.batches, batch_decisions, strict=True
    ):
        target_ids = list(batch.target_structure_unit_ids)
        returned_ids = [item.structure_unit_id for item in raw_decisions]
        if len(returned_ids) != len(set(returned_ids)):
            raise ProtocolControlPlanningError(
                "discovery_batch_result_duplicate",
                "发现结果不得重复处置同一结构单元。",
            )
        if sorted(returned_ids) != sorted(target_ids):
            raise ProtocolControlPlanningError(
                "discovery_batch_result_incomplete",
                "发现结果必须闭合当前批次全部 target_units。",
            )
        ordered = sorted(
            raw_decisions,
            key=lambda item: target_ids.index(item.structure_unit_id),
        )
        for decision in ordered:
            unknown_context = set(decision.required_context_structure_unit_ids) - expected_set
            if unknown_context:
                raise ProtocolControlPlanningError(
                    "discovery_context_out_of_scope",
                    "发现阶段所需上下文结构单元越出完整清单。",
                )
            decisions.append(decision)
            decision_by_id[decision.structure_unit_id] = decision

    if [item.structure_unit_id for item in decisions] != expected_ids:
        raise ProtocolControlPlanningError(
            "discovery_result_order_invalid",
            "发现处置必须按原文顺序恰好覆盖完整清单。",
        )

    # Discovery batches classify their owned units independently.  A unit may
    # therefore be labelled non_control by its owner while a candidate in a
    # different batch names that same unit as indispensable context.  The
    # cross-batch relation is more specific: promote the referenced unit to
    # context_only without turning it into a control or changing source text.
    required_context_ids = {
        context_id
        for decision in decisions
        if decision.disposition
        in {
            ProtocolControlDiscoveryDisposition.CANDIDATE,
            ProtocolControlDiscoveryDisposition.UNCERTAIN,
        }
        for context_id in decision.required_context_structure_unit_ids
    }
    decisions = [
        decision.model_copy(
            update={
                "disposition": ProtocolControlDiscoveryDisposition.CONTEXT_ONLY,
                "rationale": (
                    f"{decision.rationale}；该段被其他候选或待核对段落"
                    "明确列为必要上下文，系统仅将其收录为上下文，"
                    "不单独生成审核要求。"
                ),
            }
        )
        if (
            decision.structure_unit_id in required_context_ids
            and decision.disposition
            == ProtocolControlDiscoveryDisposition.NON_CONTROL
        )
        else decision
        for decision in decisions
    ]

    deep_ids = [
        decision.structure_unit_id
        for decision in decisions
        if decision.disposition
        in {
            ProtocolControlDiscoveryDisposition.CANDIDATE,
            ProtocolControlDiscoveryDisposition.UNCERTAIN,
        }
    ]
    validate_protocol_control_deep_selection(decisions, deep_ids)
    return tuple(decisions)


def _deep_batch_chunks(
    units: Sequence[ProtocolStructureUnit],
    context_ids_by_unit_id: dict[str, tuple[str, ...]],
    *,
    max_owned_units_per_batch: int,
    all_units: Sequence[ProtocolStructureUnit] | None = None,
) -> list[
    tuple[tuple[ProtocolStructureUnit, ...], tuple[ProtocolStructureUnit, ...]]
]:
    unit_by_id = {
        unit.structure_unit_id: unit
        for unit in (all_units or units)
    }
    chunks: list[
        tuple[tuple[ProtocolStructureUnit, ...], tuple[ProtocolStructureUnit, ...]]
    ] = []
    for run in _heading_runs(units):
        for start in range(0, len(run), max_owned_units_per_batch):
            owned = tuple(run[start : start + max_owned_units_per_batch])
            owned_ids = [unit.structure_unit_id for unit in owned]
            required_context_ids = {
                context_id
                for owned_id in owned_ids
                for context_id in context_ids_by_unit_id.get(owned_id, ())
            } - set(owned_ids)
            context = tuple(
                sorted(
                    (unit_by_id[context_id] for context_id in required_context_ids),
                    key=lambda unit: (unit.source_order, unit.structure_unit_id),
                )
            )
            chunks.append((owned, context))
    return chunks


def plan_protocol_control_deep_batches_from_discovery(
    coverage_manifest: ProtocolSectionCoverageManifest,
    discovery_plan: ProtocolControlDiscoveryPlan,
    batch_decisions: Sequence[Sequence[ProtocolControlDiscoveryDecision]],
    official_parent_catalog: FrozenProtocolCatalog | None = None,
    required_procedure_catalog: FrozenProtocolCatalog | None = None,
    *,
    max_owned_units_per_batch: int = 12,
    workflow_stages: Sequence[WorkflowStage] | None = None,
) -> ProtocolControlDiscoveryToDeepPlan:
    """Build deep batches only for candidate/uncertain discovery outcomes."""

    if max_owned_units_per_batch < 1:
        raise ProtocolControlPlanningError(
            "deep_batch_size_invalid",
            "max_owned_units_per_batch 必须为正整数。",
        )
    expected_ids = [unit.structure_unit_id for unit in coverage_manifest.units]
    if (
        discovery_plan.coverage_manifest_id != coverage_manifest.manifest_id
        or discovery_plan.protocol_version_id != coverage_manifest.protocol_version_id
        or discovery_plan.protocol_document_sha256
        != coverage_manifest.protocol_document_sha256
        or discovery_plan.snapshot_id != coverage_manifest.snapshot_id
        or discovery_plan.study_phase != coverage_manifest.study_phase
        or discovery_plan.expected_structure_unit_ids != expected_ids
    ):
        raise ProtocolControlPlanningError(
            "discovery_plan_manifest_mismatch",
            "发现计划必须绑定当前完整结构清单。",
        )
    decisions = validate_protocol_control_discovery_results(
        discovery_plan,
        batch_decisions,
    )
    decision_by_id = {decision.structure_unit_id: decision for decision in decisions}
    deep_ids = list(
        validate_protocol_control_deep_selection(
            decisions,
            [
                decision.structure_unit_id
                for decision in decisions
                if decision.disposition
                in {
                    ProtocolControlDiscoveryDisposition.CANDIDATE,
                    ProtocolControlDiscoveryDisposition.UNCERTAIN,
                }
            ],
        )
    )
    unit_by_id = {unit.structure_unit_id: unit for unit in coverage_manifest.units}
    deep_units = [unit_by_id[unit_id] for unit_id in deep_ids]
    context_ids_by_unit_id = {
        decision.structure_unit_id: tuple(
            decision.required_context_structure_unit_ids
        )
        for decision in decisions
    }
    chunks = _deep_batch_chunks(
        deep_units,
        context_ids_by_unit_id,
        max_owned_units_per_batch=max_owned_units_per_batch,
        all_units=coverage_manifest.units,
    )
    official_targets = _catalog_targets(
        official_parent_catalog,
        expected_kind=CatalogKind.OFFICIAL_PARENT_RULES,
        coverage=coverage_manifest,
    )
    procedure_targets = _catalog_targets(
        required_procedure_catalog,
        expected_kind=CatalogKind.REQUIRED_PROCEDURES,
        coverage=coverage_manifest,
    )
    workflow_stage_targets = _workflow_stage_targets(workflow_stages)
    _validate_procedure_stage_reconciliation(
        procedure_targets,
        workflow_stage_targets,
    )
    batches: list[ProtocolControlDispositionBatch] = []
    batch_total = len(chunks)
    for number, (owned, context) in enumerate(chunks, start=1):
        owned_ids = [unit.structure_unit_id for unit in owned]
        context_ids = [unit.structure_unit_id for unit in context]
        batches.append(
            ProtocolControlDispositionBatch(
                batch_id=stable_protocol_control_batch_id(
                    coverage_manifest.manifest_id,
                    number,
                    owned_ids,
                ),
                coverage_manifest_id=coverage_manifest.manifest_id,
                protocol_version_id=coverage_manifest.protocol_version_id,
                study_phase=coverage_manifest.study_phase,
                batch_number=number,
                batch_total=batch_total,
                priority_rank=max(unit.priority_rank for unit in owned),
                owned_units=list(owned),
                context_units=list(context),
                owned_structure_unit_ids=owned_ids,
                context_structure_unit_ids=context_ids,
                owned_source_span_ids=sorted(
                    {
                        span_id
                        for unit in owned
                        for span_id in unit.source_span_ids
                    }
                ),
                context_source_span_ids=sorted(
                    {
                        span_id
                        for unit in context
                        for span_id in unit.source_span_ids
                    }
                ),
                known_official_targets=list(official_targets),
                known_procedure_targets=list(procedure_targets),
                known_workflow_stage_targets=list(workflow_stage_targets),
            )
        )
    deep_plan_id = "pcdp-" + stable_protocol_control_batch_id(
        coverage_manifest.manifest_id,
        len(batches),
        [batch.batch_id for batch in batches],
    ).removeprefix("pcb-")
    return ProtocolControlDiscoveryToDeepPlan(
        plan_id=deep_plan_id,
        discovery_plan_id=discovery_plan.plan_id,
        coverage_manifest_id=coverage_manifest.manifest_id,
        protocol_version_id=coverage_manifest.protocol_version_id,
        protocol_document_sha256=coverage_manifest.protocol_document_sha256,
        snapshot_id=coverage_manifest.snapshot_id,
        study_phase=coverage_manifest.study_phase,
        manifest_structure_unit_count=len(expected_ids),
        manifest_structure_unit_ids_sha256=(
            stable_protocol_control_manifest_structure_unit_ids_sha256(
                expected_ids
            )
        ),
        expected_structure_unit_ids=expected_ids,
        discovery_decisions=list(decisions),
        max_owned_units_per_batch=max_owned_units_per_batch,
        batches=batches,
    )


build_protocol_control_discovery_plan = plan_protocol_control_discovery
build_protocol_control_deep_plan = plan_protocol_control_deep_batches_from_discovery
