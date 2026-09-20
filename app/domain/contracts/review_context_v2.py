"""Frozen V2 review inputs; storage identity is not clinical acceptance."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, model_serializer, model_validator

from .common import ContractModel
from .clause_pack import ClausePack
from .control_evidence_origin import ControlEvidenceOrigin
from .evidence import EvidenceExpectationTemplate
from .evidence_expectations_v2 import EvidenceExpectationV2
from .facts import (
    ClinicalConflictGroupV2, ClinicalEventV2, ClinicalFactV2,
    FactAuthority, MedicationExposureV2,
)
from .fact_rule_index import FactRuleLink
from .judgment_search import JudgmentSearchCoverageSummary, JudgmentSearchScope
from .review import ReviewEpisode, Subject, ProtocolDocumentVersion
from .rules import WorkflowStage

_SHA256 = r"^[0-9a-f]{64}$"


class FrozenSearchCheckpoint(ContractModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    checkpoint_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    payload_sha256: str = Field(pattern=_SHA256)


class FrozenJudgmentSearchResult(ContractModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    summary_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    job_payload_sha256: str = Field(pattern=_SHA256)
    checkpoints: tuple[FrozenSearchCheckpoint, ...]
    payload_sha256: str = Field(pattern=_SHA256)
    summary: JudgmentSearchCoverageSummary
    scope: JudgmentSearchScope
    target_text: str = Field(min_length=1)
    receipt_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_result(self) -> "FrozenJudgmentSearchResult":
        from app.domain.publication import canonical_hash

        if (
            self.summary.requirement_id != self.scope.requirement_id
            or self.summary.scope_sha256 != self.scope.scope_sha256
            or canonical_hash(self.summary.model_dump(mode="json")) != self.payload_sha256
        ):
            raise ValueError("冻结检索结果与原范围、要求或内容指纹不一致")
        if not self.target_text.strip():
            raise ValueError("检索目标不得为空白")
        if (
            len({item.step_id for item in self.checkpoints}) != len(self.checkpoints)
            or len({item.checkpoint_id for item in self.checkpoints}) != len(self.checkpoints)
        ):
            raise ValueError("检索步骤或原始记录引用重复")
        if len(set(self.receipt_refs)) != len(self.receipt_refs) or any(
            not value.startswith("artifacts/raw_response/") for value in self.receipt_refs
        ):
            raise ValueError("检索回执引用无效或重复")
        return self


class ReviewContextSnapshotV2(ContractModel):
    schema_version: Literal["review/v2"] = "review/v2"
    model_config = ConfigDict(frozen=True, extra="forbid")

    context_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    authority: FactAuthority
    review_episode: ReviewEpisode
    subject: Subject
    project_name: str = Field(min_length=1)
    project_revision: int = Field(ge=1)
    protocol_document: ProtocolDocumentVersion
    rule_set_sha256: str = Field(pattern=_SHA256)
    clause_pack_sha256: str = Field(pattern=_SHA256)
    clause_pack: ClausePack
    protocol_integrity_gate_result_id: str = Field(min_length=1)
    evaluator_version: str = Field(min_length=1)
    requirements_scope_version: Literal["review-requirements-scope/v1"] | None = None
    workflow_stages: tuple[WorkflowStage, ...]
    facts: tuple[ClinicalFactV2, ...] = ()
    fact_rule_links: tuple[FactRuleLink, ...] = ()
    events: tuple[ClinicalEventV2, ...] = ()
    medication_exposures: tuple[MedicationExposureV2, ...] = ()
    expectation_templates: tuple[EvidenceExpectationTemplate, ...] = ()
    expectations: tuple[EvidenceExpectationV2, ...] = ()
    conflict_groups: tuple[ClinicalConflictGroupV2, ...] = ()
    judgment_search_results: tuple[FrozenJudgmentSearchResult, ...] = ()
    created_at: datetime
    context_sha256: str = Field(pattern=_SHA256)

    @model_serializer(mode="wrap")
    def serialize_scope_version(self, handler):
        payload = handler(self)
        if self.requirements_scope_version is None:
            payload.pop("requirements_scope_version", None)
        return payload

    @model_validator(mode="after")
    def validate_context(self) -> "ReviewContextSnapshotV2":
        from app.domain.publication import canonical_hash

        episode = self.review_episode
        expected_authority = FactAuthority(
            project_id=episode.project_id,
            subject_id=episode.subject_id,
            review_episode_id=episode.review_episode_id,
            episode_revision=episode.revision,
            protocol_version_id=episode.protocol_version_id,
            rule_set_id=episode.rule_set_id,
            rule_set_revision=episode.rule_set_revision,
            evidence_snapshot_v2_id=episode.active_evidence_snapshot_id,
            complete_processing_revision_id=episode.active_evidence_processing_revision_id,
        )
        if self.authority != expected_authority:
            raise ValueError("审核上下文与冻结节点资料不一致")
        if (
            self.subject.subject_id != self.authority.subject_id
            or self.subject.project_id != self.authority.project_id
            or self.protocol_document.protocol_version_id != self.authority.protocol_version_id
            or self.protocol_document.integrity_gate_result_id != self.protocol_integrity_gate_result_id
        ):
            raise ValueError("报告对象或方案版本与本次审核不一致")
        pack = self.clause_pack
        pack_material = pack.model_dump(
            mode="json", exclude={"schema_version", "clause_pack_id", "clause_pack_sha256"},
        )
        digest = canonical_hash(pack_material)
        if (
            digest != self.clause_pack_sha256
            or digest != pack.clause_pack_sha256
            or pack.clause_pack_id != f"clause-pack:{digest[:32]}"
            or (pack.rule_set_id, pack.rule_set_revision, pack.protocol_version_id)
            != (self.authority.rule_set_id, self.authority.rule_set_revision, self.authority.protocol_version_id)
            or len({item.rule_component_id for item in pack.clauses}) != len(pack.clauses)
        ):
            raise ValueError("本次审核保存的条款内容或所属方案不一致")
        if self.created_at.utcoffset() is None or self.created_at.utcoffset().total_seconds() != 0:
            raise ValueError("审核上下文时间必须使用UTC")
        for values, key in (
            (self.facts, "fact_id"),
            (self.fact_rule_links, "link_id"),
            (self.events, "event_id"),
            (self.medication_exposures, "exposure_id"),
            (self.expectation_templates, "template_id"),
            (self.expectations, "template_id"),
            (self.conflict_groups, "conflict_group_id"),
            (self.judgment_search_results, "summary_id"),
        ):
            identities = [getattr(item, key) for item in values]
            if identities != sorted(set(identities)):
                raise ValueError("冻结审核集合必须按身份排序且不得重复")
        for item in (
            *self.facts, *self.events, *self.medication_exposures,
            *self.expectations, *self.conflict_groups,
        ):
            if item.authority != self.authority:
                raise ValueError("审核上下文混入其他资料版本的记录")
        templates = {item.template_id: item for item in self.expectation_templates}
        requirements = {
            item.requirement_id: item
            for clause in pack.clauses for item in clause.evidence_requirements
        }
        if len(requirements) != sum(len(clause.evidence_requirements) for clause in pack.clauses):
            raise ValueError("本次审核的资料要求身份重复")
        stages = {item.workflow_stage_id: item for item in self.workflow_stages}
        control_publication = pack.control_publication
        if control_publication is not None and (
            control_publication.project_id != self.authority.project_id
            or control_publication.rule_set_sha256 != self.rule_set_sha256
            or not set(control_publication.workflow_stage_map.values()).issubset(stages)
        ):
            raise ValueError("冻结补充要求与本次项目、规则内容或审核节点不同")
        if len(stages) != len(self.workflow_stages) or episode.workflow_stage_id not in stages:
            raise ValueError("冻结流程节点重复或缺少当前审核节点")
        if stages[episode.workflow_stage_id].stage != episode.stage:
            raise ValueError("冻结流程与当前审核阶段不一致")
        for template in templates.values():
            requirement = requirements.get(template.requirement_id)
            if requirement is not None and (any(
                getattr(template, key) != getattr(requirement, key)
                for key in (
                    "due_stage", "fact_type", "description",
                    "requires_contemporaneous_objective_source",
                    "allows_screening_record_transcription", "source_validity_window",
                )
            ) or set(template.required_source_types) != set(requirement.required_source_types)):
                raise ValueError("办理及核对所用资料要求与冻结方案条款不一致")
            if (template.rule_set_id, template.rule_set_revision) != (
                self.authority.rule_set_id, self.authority.rule_set_revision,
            ):
                raise ValueError("审核资料要求来自其他方案修订")
            stage = stages.get(template.workflow_stage_id)
            if (
                stage is None or stage.stage != template.due_stage
            ):
                raise ValueError("冻结资料要求与流程到期节点不一致")
            if template.control_origin is None:
                if template.requirement_id not in stage.due_requirement_ids:
                    raise ValueError("冻结资料要求与流程到期节点不一致")
            else:
                origin = template.control_origin
                source = origin.resolve(control_publication)
                policy = source.source_policy
                if (
                    template.requirement_id != origin.requirement_identity()
                    or template.requirement_id in requirements
                    or any(getattr(template, key) != getattr(source, key)
                           for key in ("due_stage", "fact_type", "description"))
                    or set(template.required_source_types) != set(source.required_source_types)
                    or any(getattr(template, key) != getattr(policy, key) for key in (
                        "requires_contemporaneous_objective_source", "allows_screening_record_transcription",
                    ))
                    or template.control_validity_status != policy.result_validity_status
                    or template.control_validity_constraint != policy.result_validity_constraint
                ):
                    raise ValueError("冻结补充资料要求与其发布原文或来源政策不一致")
        if self.requirements_scope_version is not None:
            expected_requirements = {}
            for stage in self.workflow_stages:
                for requirement_id in stage.due_requirement_ids:
                    if requirement_id in expected_requirements:
                        raise ValueError("冻结资料要求存在重复的到期安排")
                    expected_requirements[requirement_id] = stage.workflow_stage_id
            if control_publication is not None:
                for control in control_publication.catalog.controls:
                    for evidence in control.minimum_evidence:
                        if not evidence.workflow_stage_ids:
                            raise ValueError("冻结补充资料要求尚未明确适用访视")
                        for source_id in evidence.workflow_stage_ids:
                            target_id = control_publication.workflow_stage_map.get(source_id)
                            if target_id is None:
                                raise ValueError("冻结补充资料要求缺少正式访视对应")
                            origin = ControlEvidenceOrigin(
                                publication_id=control_publication.publication_id,
                                protocol_control_id=control.protocol_control_id,
                                evidence_key=evidence.evidence_key, workflow_stage_id=target_id,
                            )
                            origin.resolve(control_publication)
                            requirement_id = origin.requirement_identity()
                            if requirement_id in expected_requirements:
                                raise ValueError("冻结补充资料要求的来源身份重复")
                            expected_requirements[requirement_id] = target_id
            supplied = {item.requirement_id: item.workflow_stage_id for item in templates.values()}
            if len(supplied) != len(templates) or supplied != expected_requirements:
                raise ValueError("冻结资料要求未完整对应已发布方案及具体访视")
        fact_ids = {item.fact_id for item in self.facts}
        for link in self.fact_rule_links:
            if link.fact_id not in fact_ids or (link.rule_set_id, link.rule_set_revision) != (
                self.authority.rule_set_id, self.authority.rule_set_revision,
            ):
                raise ValueError("冻结事实索引未绑定本次事实与规则修订")
        for item in (*self.events, *self.medication_exposures):
            if not set(item.fact_ids) <= fact_ids:
                raise ValueError("冻结的事件或用药引用了本次审核以外的事实")
        member_pools = {
            "fact": fact_ids,
            "event": {item.event_id for item in self.events},
            "exposure": {item.exposure_id for item in self.medication_exposures},
        }
        for group in self.conflict_groups:
            members = getattr(group, f"{group.member_kind}_ids")
            if not set(members) <= member_pools[group.member_kind]:
                raise ValueError("冻结争议记录未完整绑定本次审核事实、事件或用药")
        for expectation in self.expectations:
            if expectation.template_id not in templates or not set(expectation.coverage_fact_ids) <= fact_ids:
                raise ValueError("审核资料期望未绑定冻结要求或事实")
        requirement_ids = {item.requirement_id for item in templates.values()}
        searched: set[str] = set()
        for item in self.judgment_search_results:
            requirement_id = item.scope.requirement_id
            if (
                item.scope.authority != self.authority
                or requirement_id not in requirement_ids
                or requirement_id in searched
            ):
                raise ValueError("检索结果不属于本次审核要求或重复绑定")
            searched.add(requirement_id)
        if self.context_sha256 != canonical_hash(self.model_dump(mode="json", exclude={"context_sha256"})):
            raise ValueError("审核上下文内容指纹无效")
        return self
