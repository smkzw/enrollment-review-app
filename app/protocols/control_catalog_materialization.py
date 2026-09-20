"""Preserve hydrated control semantics while constructing a validated catalog.

No persistence, clinical approval or RuleSet mutation occurs here. Workflow IDs
remain in their frozen source namespace; the publication owner binds that namespace
to the exact published revision separately.
"""
from __future__ import annotations

from collections.abc import Sequence

from app.domain.contracts.protocol_controls import (
    ControlCrossSourceRelation, ControlRelationTargetKind,
    KnownRequiredProcedureTarget,
    ProtocolControlBatchDispositionHydrated, ProtocolControlBatchPlan,
    ProtocolReviewControl, ProtocolSectionCoverageManifest,
    PublishedProtocolControlCatalog,
)
from app.domain.contracts.agent_io import ProcedureCatalogMapping
from app.domain.publication import canonical_hash
from app.domain.contracts.rules import RuleSet, WorkflowStage
from app.protocols.full_protocol_coverage import FullProtocolCoverageResolutionView
from app.protocols.protocol_control_gate import validate_protocol_control_publication


def materialize_control_catalog(
    *, coverage_manifest: ProtocolSectionCoverageManifest,
    plan: ProtocolControlBatchPlan,
    batch_dispositions: Sequence[ProtocolControlBatchDispositionHydrated],
    rule_component_ids: Sequence[str],
    phase_applicability_view: FullProtocolCoverageResolutionView | None = None,
) -> PublishedProtocolControlCatalog:
    """Copy every hydrated candidate, then validate the complete nonempty content.

    A rejected candidate fails the whole construction; it is never silently
    omitted to obtain a publishable catalog. Empty input is valid only when the
    complete plan and its source dispositions establish no additional controls.
    """
    manifest = ProtocolSectionCoverageManifest.model_validate(
        coverage_manifest.model_dump(mode="json"),
    )
    plan = ProtocolControlBatchPlan.model_validate(plan.model_dump(mode="json"))
    batches = tuple(ProtocolControlBatchDispositionHydrated.model_validate(
        item.model_dump(mode="json"),
    ) for item in batch_dispositions)
    candidates = [candidate for batch in batches for candidate in batch.candidates]
    if len({item.control_candidate_id for item in candidates}) != len(candidates):
        raise ValueError("补充审核要求中存在重复候选，未生成正式目录")
    units = {item.structure_unit_id: item for item in manifest.units}
    for candidate in candidates:
        if candidate.semantics is None:
            raise ValueError("补充审核要求尚未完成结构化理解，未生成正式目录")
        if not set(candidate.frozen_structure_unit_ids).issubset(units):
            raise ValueError("补充审核要求引用了范围之外的方案内容")
    candidates.sort(key=lambda item: (
        min(units[key].source_order for key in item.frozen_structure_unit_ids),
        item.control_candidate_id,
    ))
    digest = canonical_hash({
        "version": "control-catalog-materialization/v1",
        "manifest": manifest.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "batches": [item.model_dump(mode="json") for item in sorted(batches, key=lambda item: item.batch_id)],
    })
    identities = {item.control_candidate_id: "protocol-control:" + canonical_hash(
        [digest, item.control_candidate_id],
    )[:32] for item in candidates}
    controls = []
    for ordinal, candidate in enumerate(candidates, 1):
        semantics = candidate.semantics
        # The validation above narrows the optional legacy compatibility field.
        assert semantics is not None
        relations = []
        for relation in semantics.cross_source_relations:
            data = relation.model_dump(mode="json")
            for side in ("left", "right"):
                if data[f"{side}_target_kind"] == ControlRelationTargetKind.CONTROL_CANDIDATE.value:
                    source_id = data[f"{side}_target_id"]
                    if source_id not in identities:
                        raise ValueError("补充审核要求的关联对象不在本次完整目录中")
                    data[f"{side}_target_kind"] = ControlRelationTargetKind.PROTOCOL_CONTROL.value
                    data[f"{side}_target_id"] = identities[source_id]
            relations.append(ControlCrossSourceRelation.model_validate(data))
        data = semantics.model_dump(mode="json", exclude={"control_candidate_id", "cross_source_relations"})
        controls.append(ProtocolReviewControl.model_validate({
            **data,
            "protocol_control_id": identities[candidate.control_candidate_id],
            "display_ordinal": ordinal,
            "protocol_version_id": candidate.protocol_version_id,
            "study_phase": candidate.study_phase,
            "originating_candidate_id": candidate.control_candidate_id,
            "cross_source_relations": [item.model_dump(mode="json") for item in relations],
        }))
    catalog = PublishedProtocolControlCatalog(
        catalog_id=f"control-catalog:{digest}",
        protocol_version_id=manifest.protocol_version_id,
        protocol_document_sha256=manifest.protocol_document_sha256,
        study_phase=manifest.study_phase,
        coverage_manifest_id=manifest.manifest_id,
        allowed_source_span_ids=sorted({span for unit in manifest.units for span in unit.source_span_ids}),
        controls=controls,
    )
    return validate_protocol_control_publication(
        manifest, catalog, plan=plan, batch_dispositions=batches,
        rule_component_ids=rule_component_ids,
        phase_applicability_view=phase_applicability_view,
    )


def bind_control_workflow_stages(
    catalog: PublishedProtocolControlCatalog, *, rule_set: RuleSet,
    source_stages: Sequence[WorkflowStage], draft_stages: Sequence[WorkflowStage],
    published_stages: Sequence[WorkflowStage],
    procedure_targets: Sequence[KnownRequiredProcedureTarget],
    procedure_mappings: Sequence[ProcedureCatalogMapping],
) -> dict[str, str]:
    """Bridge control nodes via source-proven procedure mappings, not label guesses.

    Control planning and deconstruction use different node IDs. The frozen
    procedure item ID and its verified draft mapping bridge them. Then verify
    the publisher's exact namespace transformation for the entire draft tree.
    """
    if (catalog.protocol_version_id, catalog.study_phase) != (
        rule_set.protocol_version_id, rule_set.study_phase,
    ):
        raise ValueError("补充审核要求与正式方案版本或期别不同")
    source = {item.workflow_stage_id: item for item in source_stages}
    draft = {item.workflow_stage_id: item for item in draft_stages}
    published = {item.workflow_stage_id: item for item in published_stages}
    if (len(source) != len(source_stages) or len(draft) != len(draft_stages)
            or len(published) != len(published_stages)):
        raise ValueError("审核节点身份重复，不能对应正式方案")
    prefix = f"{rule_set.rule_set_id}:{rule_set.revision}:"
    for draft_id, stage in draft.items():
        target_id = prefix + draft_id
        expected = stage.model_dump(mode="json")
        expected["workflow_stage_id"] = target_id
        target = published.get(target_id)
        if target is None or target.model_dump(mode="json") != expected:
            raise ValueError("正式审核节点与原方案节点内容不同，不能沿用补充要求")
    if {prefix + key for key in draft} != set(published):
        raise ValueError("正式审核节点与已校验草稿的完整节点版本不同")
    source_by_visit = {(item.stage, item.visit_instance): item for item in source.values()}
    mappings_by_item = {item.catalog_item_id: item for item in procedure_mappings}
    if (len(source_by_visit) != len(source)
            or len(mappings_by_item) != len(procedure_mappings)
            or len({item.catalog_item_id for item in procedure_targets}) != len(procedure_targets)):
        raise ValueError("方案必做项目或来源访视的对应关系重复")
    if set(mappings_by_item) != {item.catalog_item_id for item in procedure_targets}:
        raise ValueError("补充要求与正式草稿未使用同一完整必做项目录")
    mapping = {}
    for item in procedure_targets:
        relation = mappings_by_item[item.catalog_item_id]
        source_stage = source_by_visit.get((item.review_stage, item.visit_instance))
        draft_stage = draft.get(relation.proposed_workflow_stage_id)
        if (source_stage is None or draft_stage is None
                or (draft_stage.stage, draft_stage.visit_instance) != (item.review_stage, item.visit_instance)
                or set(relation.source_span_ids) != set(item.source_span_ids)
                or not set(relation.proposed_requirement_ids).issubset(draft_stage.due_requirement_ids)):
            raise ValueError("必做项目的原文、资料要求或执行节点无法证明对应")
        target_id = prefix + draft_stage.workflow_stage_id
        previous = mapping.setdefault(source_stage.workflow_stage_id, target_id)
        if previous != target_id:
            raise ValueError("同一来源访视被对应到多个正式审核节点")
    if set(mapping) != set(source) or len(set(mapping.values())) != len(mapping):
        raise ValueError("来源审核节点的对应关系不完整或合并了不同访视")
    for control in catalog.controls:
        for binding in control.review_node_bindings:
            stage = source.get(binding.workflow_stage_id)
            if stage is None or stage.stage != binding.review_stage:
                raise ValueError("补充审核要求引用的审核节点或阶段不一致")
        for relation in control.cross_source_relations:
            node_ids = [target_id for target_kind, target_id in (
                (relation.left_target_kind, relation.left_target_id),
                (relation.right_target_kind, relation.right_target_id),
            ) if target_kind == ControlRelationTargetKind.WORKFLOW_STAGE]
            if relation.affected_workflow_stage_id is not None:
                node_ids.append(relation.affected_workflow_stage_id)
            if not set(node_ids).issubset(mapping):
                raise ValueError("补充审核要求的关联节点不属于本次正式方案")
    return dict(sorted(mapping.items()))
