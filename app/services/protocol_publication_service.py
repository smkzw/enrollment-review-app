"""方案解构发布服务（Phase 3 切片 4）：单事务原子幂等发布。

发布在**一个写事务**内完成：

1. 解析幂等记录：同键同请求返回原发布，同键异请求冲突，任何失败回滚全部；
2. 锁定草稿 revision（必须是当前链头且已保存），复跑确定性
   :class:`ProtocolDeconstructionGate`，未达可发布状态即拒绝；
3. 谱系与期别校验：重新解构必须同方案编号谱系、同期别；首次解构不得创建
   平行正式项目（同编号同期别已有项目时拒绝）；
4. 写入全部正式对象：方案来源记录、权威记录、操作事件、确认、完整性清单、
   GateResult、方案版本、RuleSet revision、规则树、流程节点、Project 状态、
   无受试者 EvidenceExpectation 模板投影，并把草稿 revision 标记为已发布；
5. 任一步失败或 revision 过期，整个事务回滚，旧正式版本保持不变。

每次发布都产生新的内部方案版本（``protocol_version_id``）；已存在的版本
记录不可复用——重新发布必须携带新的内部版本 id（封面版本号可不变），
保证两条发布证据链可追溯。

本服务不做最终临床/产品验收；验收由 Codex 持有。
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.agent_io import (
    ProtocolDeconstructionDraft,
    ProtocolDeconstructionInput,
)
from app.domain.contracts.agents import GateResult
from app.domain.contracts.enums import GateOutcome
from app.domain.contracts.evidence import EvidenceExpectationTemplate
from app.domain.contracts.protocol_drafts import (
    DraftRevisionStatus,
    ProtocolDraftRevision,
)
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.domain.contracts.protocol_metadata import InterpretationConflict
from app.domain.contracts.review import Project, ProtocolDocumentVersion
from app.domain.contracts.rules import (
    EvidenceRequirement,
    ProtocolAuthorityConfirmation,
    ProtocolAuthorityRecord,
    ProtocolIntegrityManifest,
    ProtocolSourceRecord,
    RuleSet,
    ServiceCommandEvent,
    WorkflowStage,
)
from app.domain.gates.integrity import (
    build_protocol_source_record,
    build_service_command_event,
)
from app.domain.publication import canonical_hash
from app.projections.evidence_expectation_templates import (
    project_evidence_expectation_templates,
)
from app.protocols.deconstruction_gate import (
    ProtocolDeconstructionGate,
    ProtocolDeconstructionGateResult,
)
from app.services.protocol_draft_service import ProtocolDraftService
from app.storage.codecs import utc_now
from app.storage.concurrency import StaleRevisionError
from app.storage.idempotency import IdempotencyRepository, request_hash
from app.storage.models import IdempotencyRecordRow, RuleSetRecord
from app.storage.repositories import (
    AppendRepository,
    AUTHORITY_CONFIRMATION_CONFIG,
    AUTHORITY_RECORD_CONFIG,
    COMMAND_EVENT_CONFIG,
    GATE_RESULT_CONFIG,
    INTEGRITY_MANIFEST_CONFIG,
    NotFoundError,
    PROTOCOL_DOC_CONFIG,
    ProjectRepository,
    ProtocolDraftRevisionRepository,
    SOURCE_RECORD_CONFIG,
    WORKFLOW_STAGE_CONFIG,
    find_project_by_protocol_and_phase,
    save_expectation_templates,
    save_rule_set,
)

PUBLICATION_IDEMPOTENCY_SCOPE = "protocol_publication"


class ProtocolPublicationError(RuntimeError):
    """发布前置条件或事务失败；携带稳定错误码。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class PublicationGateError(ProtocolPublicationError):
    """确定性门禁未通过：草稿不能发布。"""

    def __init__(self, result: ProtocolDeconstructionGateResult) -> None:
        issues = [
            (issue.check_name, issue.issue_code, issue.level)
            for check in result.checks
            for issue in check.issues
        ]
        self.result = result
        super().__init__(
            "publication_gate_rejected",
            f"方案解构门禁未通过，共 {len(issues)} 项问题：{issues}",
        )


class PublicationLineageError(ProtocolPublicationError):
    """重新解构的谱系或期别与目标项目不一致。"""


class DuplicateFirstProjectError(ProtocolPublicationError):
    """首次解构不得为同一方案编号与期别创建第二套正式项目。"""


@dataclass(frozen=True)
class ProtocolPublicationRequest:
    """一次发布请求；同 idempotency_key 的同内容请求可安全重放。"""

    idempotency_key: str
    draft_revision_id: str
    source_input: ProtocolDeconstructionInput
    source_spans: Mapping[str, ProtocolSourceSpan] = field(
        default_factory=dict
    )
    interpretation_conflicts: tuple[InterpretationConflict, ...] = ()
    actor: str = "system"
    published_at: datetime | None = None
    # 重新解构：目标正式项目与新的内部方案版本 id；None 表示首次发布。
    project_id: str | None = None
    protocol_version_id: str | None = None


@dataclass(frozen=True)
class ProtocolPublicationResult:
    project_id: str
    project_revision: int
    protocol_version_id: str
    rule_set_id: str
    rule_set_revision: int
    authority_record_id: str
    manifest_id: str
    confirmation_id: str
    authority_gate_result_id: str
    integrity_gate_result_id: str
    published_revision_id: str
    template_count: int
    replay: bool = False

    def to_stored_id(self) -> str:
        return json.dumps(
            {
                "project_id": self.project_id,
                "project_revision": self.project_revision,
                "protocol_version_id": self.protocol_version_id,
                "rule_set_id": self.rule_set_id,
                "rule_set_revision": self.rule_set_revision,
                "authority_record_id": self.authority_record_id,
                "manifest_id": self.manifest_id,
                "confirmation_id": self.confirmation_id,
                "authority_gate_result_id": self.authority_gate_result_id,
                "integrity_gate_result_id": self.integrity_gate_result_id,
                "published_revision_id": self.published_revision_id,
                "template_count": self.template_count,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_stored_id(cls, value: str) -> "ProtocolPublicationResult":
        return cls(**json.loads(value))


class ProtocolPublicationService:
    """原子幂等发布服务；每个用例在一个短写事务内完成。"""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        gate: ProtocolDeconstructionGate | None = None,
        now=None,
    ) -> None:
        self.session_factory = session_factory
        self.gate = gate or ProtocolDeconstructionGate()
        self.now = now or utc_now

    # ------------------------------------------------------------------ 用例

    def publish(
        self, request: ProtocolPublicationRequest
    ) -> ProtocolPublicationResult:
        with self.session_factory() as session:
            with session.begin():
                return self._publish_in_transaction(session, request)

    def _publish_in_transaction(
        self, session: Session, request: ProtocolPublicationRequest
    ) -> ProtocolPublicationResult:
        submitted = self._request_hash(request)
        idempotency = IdempotencyRepository(session)
        record, created = idempotency.resolve(
            scope=PUBLICATION_IDEMPOTENCY_SCOPE,
            idempotency_key=request.idempotency_key,
            submitted_hash=submitted,
            result_type="protocol_publication",
            result_id="",  # 占位；成功后在事务内回填真实结果
        )
        if not created:
            return replace(
                ProtocolPublicationResult.from_stored_id(record.result_id),
                replay=True,
            )

        revisions = ProtocolDraftRevisionRepository(session)
        revision = revisions.get(request.draft_revision_id)
        head = revisions.get_head(revision.draft_id)
        if head is None or head.revision_id != revision.revision_id:
            raise StaleRevisionError(
                entity_type="ProtocolDraftRevision",
                entity_id=revision.draft_id,
                expected_revision=head.revision_number if head else 0,
                current_revision=head.revision_number if head else 0,
                field_diff={},
                current_record=head,
            )
        if revision.status not in {
            DraftRevisionStatus.SAVED,
            DraftRevisionStatus.DRAFT,
        }:
            raise ProtocolPublicationError(
                "revision_not_editable",
                f"草稿 revision {revision.revision_id} 状态为 "
                f"{revision.status.value}，不能发布",
            )
        draft = revision.content

        # 1) 确定性门禁复跑：发布权威只在门禁通过后成立。
        gate_result = self.gate.evaluate(
            request.source_input,
            draft,
            source_spans=request.source_spans,
            interpretation_conflicts=request.interpretation_conflicts,
        )
        if not gate_result.publishable:
            raise PublicationGateError(gate_result)

        # 2) 谱系与期别校验。
        identity = request.source_input.identity_decision
        protocol_code = identity.protocol_code
        selected_phase = draft.selected_phase
        target_project: Project | None = None
        if request.project_id is not None:
            target_project = ProjectRepository(session).get(request.project_id)
            if target_project.protocol_version.protocol_code != protocol_code:
                raise PublicationLineageError(
                    "cross_protocol",
                    f"重新解构文件属于方案 {protocol_code}，"
                    f"与项目 {request.project_id} 的方案谱系不一致，拒绝发布",
                )
            if target_project.study_phase != selected_phase:
                raise PublicationLineageError(
                    "cross_phase",
                    f"重新解构期别 {selected_phase.value} 与项目 "
                    f"{request.project_id} 的期别不一致，拒绝发布",
                )
        else:
            existing = find_project_by_protocol_and_phase(
                session, protocol_code, selected_phase.value
            )
            if existing is not None:
                raise DuplicateFirstProjectError(
                    "duplicate_first_project",
                    f"方案 {protocol_code} {selected_phase.value} 已有正式项目 "
                    f"{existing.project_id}；首次解构不得创建平行项目，"
                    "请进入重新解构流程",
                )

        # 3) 组装正式权威链对象（方案版本记录在最后一步按真实引用创建）。
        version_id = request.protocol_version_id or draft.protocol_version_id
        document_sha256 = request.source_input.protocol_file_sha256
        rule_set = self._build_rule_set(
            session, draft, version_id=version_id, target_project=target_project
        )
        # 发布工件中的审核节点 ID 按 (rule_set, revision) 命名空间化，
        # 同一草稿在重新发布时不会与旧 revision 的节点行冲突。
        published_stages = self._published_workflow_stages(draft, rule_set)
        authority, source_records = self._build_authority_chain(
            session,
            draft,
            request,
            version_id=version_id,
            document_sha256=document_sha256,
            official_workflow_stages=published_stages,
        )
        command = build_service_command_event(
            command_id=f"command:{uuid.uuid4().hex}",
            record=authority,
            actor_id=request.actor,
            occurred_at=self._published_at(request),
        )
        confirmation = self._build_confirmation(command, authority)
        authority_gate = self._build_authority_gate(
            authority, confirmation, version_id=version_id, sha256=document_sha256
        )
        manifest = self._build_manifest(
            authority,
            source_records,
            study_phase=selected_phase,
        )
        procedure_requirements = self._procedure_requirements(draft)
        integrity_gate = self._build_integrity_gate(
            rule_set,
            workflow_stages=published_stages,
            manifest=manifest,
            authority_record=authority,
            authority_confirmation=confirmation,
            authority_gate_result=authority_gate,
        )
        protocol_version = self._build_protocol_version(
            session,
            request,
            draft,
            identity,
            version_id=version_id,
            manifest=manifest,
            authority=authority,
            confirmation=confirmation,
            authority_gate=authority_gate,
            integrity_gate=integrity_gate,
        )

        # 4) 单事务写入（外键依赖顺序）。
        self._persist(
            session,
            request=request,
            revision=revision,
            draft=draft,
            protocol_version=protocol_version,
            rule_set=rule_set,
            procedure_requirements=procedure_requirements,
            authority=authority,
            source_records=source_records,
            command=command,
            confirmation=confirmation,
            manifest=manifest,
            authority_gate=authority_gate,
            integrity_gate=integrity_gate,
            target_project=target_project,
            workflow_stages=published_stages,
        )

        result = ProtocolPublicationResult(
            project_id=target_project.project_id
            if target_project is not None
            else draft.project_id,
            project_revision=(
                target_project.revision if target_project is not None else 1
            ),
            protocol_version_id=protocol_version.protocol_version_id,
            rule_set_id=rule_set.rule_set_id,
            rule_set_revision=rule_set.revision,
            authority_record_id=authority.authority_record_id,
            manifest_id=manifest.manifest_id,
            confirmation_id=confirmation.confirmation_id,
            authority_gate_result_id=authority_gate.gate_result_id,
            integrity_gate_result_id=integrity_gate.gate_result_id,
            published_revision_id=revision.revision_id,
            template_count=len(
                self._templates(
                    rule_set, published_stages, procedure_requirements
                )
            ),
        )
        # 幂等记录回填真实结果（同一事务）。
        row = session.execute(
            select(IdempotencyRecordRow)
            .where(
                IdempotencyRecordRow.scope == PUBLICATION_IDEMPOTENCY_SCOPE,
                IdempotencyRecordRow.idempotency_key == request.idempotency_key,
            )
            .limit(1)
        ).scalars().first()
        if row is not None:
            row.result_id = result.to_stored_id()
        return result

    # ------------------------------------------------------------------ 组装

    def _request_hash(self, request: ProtocolPublicationRequest) -> str:
        return request_hash(
            {
                "draft_revision_id": request.draft_revision_id,
                "project_id": request.project_id,
                "protocol_version_id": request.protocol_version_id,
                "actor": request.actor,
                "identity": request.source_input.identity_decision.model_dump(
                    mode="json"
                ),
                "selected_phase": request.source_input.selected_phase.value,
            }
        )

    def _published_at(self, request: ProtocolPublicationRequest) -> datetime:
        return request.published_at or self.now()

    def _build_protocol_version(
        self,
        session: Session,
        request: ProtocolPublicationRequest,
        draft: ProtocolDeconstructionDraft,
        identity,
        *,
        version_id: str,
        manifest: ProtocolIntegrityManifest,
        authority: ProtocolAuthorityRecord,
        confirmation: ProtocolAuthorityConfirmation,
        authority_gate: GateResult,
        integrity_gate: GateResult,
    ) -> ProtocolDocumentVersion:
        """创建内部方案版本记录；已存在的版本 id 不可复用（防双权威链）。"""
        try:
            AppendRepository(session, PROTOCOL_DOC_CONFIG).get(version_id)
        except NotFoundError:
            pass
        else:
            raise PublicationLineageError(
                "protocol_version_already_published",
                f"内部方案版本 {version_id} 已存在发布记录；重新发布必须携带"
                "新的内部版本 id（封面版本号可不变），保证两条证据链可追溯",
            )
        return ProtocolDocumentVersion(
            protocol_version_id=version_id,
            protocol_code=identity.protocol_code,
            official_version=draft.protocol_metadata.version_candidate,
            official_date=identity.official_date,
            sha256=request.source_input.protocol_file_sha256,
            integrity_manifest_sha256=manifest.manifest_sha256,
            authority_record_sha256=authority.authority_record_sha256,
            authority_confirmation_id=confirmation.confirmation_id,
            authority_gate_result_id=authority_gate.gate_result_id,
            integrity_gate_result_id=integrity_gate.gate_result_id,
        )

    def _build_rule_set(
        self,
        session: Session,
        draft: ProtocolDeconstructionDraft,
        *,
        version_id: str,
        target_project: Project | None,
    ) -> RuleSet:
        if target_project is not None:
            rule_set_id = target_project.rule_set_id
            latest = session.execute(
                select(func.max(RuleSetRecord.revision)).where(
                    RuleSetRecord.rule_set_id == rule_set_id
                )
            ).scalar_one()
            revision = (latest or 0) + 1
        else:
            rule_set_id = f"ruleset:{version_id}:{draft.selected_phase.value}"
            revision = 1
        return RuleSet(
            rule_set_id=rule_set_id,
            protocol_version_id=version_id,
            study_phase=draft.selected_phase,
            rules=draft.proposed_rules,
            revision=revision,
        )

    def _published_workflow_stages(
        self,
        draft: ProtocolDeconstructionDraft,
        rule_set: RuleSet,
    ) -> list[WorkflowStage]:
        """发布工件内的审核节点 ID 按 (rule_set, revision) 命名空间化。"""
        return [
            stage.model_copy(
                update={
                    "workflow_stage_id": (
                        f"{rule_set.rule_set_id}:{rule_set.revision}:"
                        f"{stage.workflow_stage_id}"
                    )
                }
            )
            for stage in draft.proposed_workflow_stages
        ]

    def _procedure_requirements(
        self, draft: ProtocolDeconstructionDraft
    ) -> list[EvidenceRequirement]:
        requirements = [
            item.proposed_requirement
            for item in draft.evidence_requirement_drafts
            if item.procedure_catalog_item_id is not None
        ]
        return sorted(requirements, key=lambda item: item.requirement_id)

    def _source_refs(
        self, span_ids: Sequence[str], source_spans: Mapping[str, ProtocolSourceSpan]
    ) -> list[str]:
        refs: list[str] = []
        for span_id in span_ids:
            span = source_spans.get(span_id)
            if span is None:
                raise ProtocolPublicationError(
                    "source_span_missing",
                    f"来源片段 {span_id} 不在本次解构的来源图中",
                )
            refs.append(span.source_ref)
        return sorted(set(refs))

    def _build_authority_chain(
        self,
        session: Session,
        draft: ProtocolDeconstructionDraft,
        request: ProtocolPublicationRequest,
        *,
        version_id: str,
        document_sha256: str,
        official_workflow_stages: list[WorkflowStage],
    ) -> tuple[ProtocolAuthorityRecord, list[ProtocolSourceRecord]]:
        catalog_items = {
            item.item_id: item
            for item in request.source_input.parent_rule_catalog.items
        }
        rule_anchor_refs: dict[str, list[str]] = {}
        for mapping in draft.parent_catalog_mappings:
            item = catalog_items.get(mapping.catalog_item_id)
            if item is None or item.official_code is None:
                raise ProtocolPublicationError(
                    "parent_mapping_missing",
                    f"父规则映射 {mapping.catalog_item_id} 找不到冻结目录项",
                )
            refs = self._source_refs(
                mapping.source_span_ids, request.source_spans
            )
            rule_anchor_refs[item.official_code] = [
                f"{version_id}:{ref}" for ref in refs
            ]
        procedure_drafts = {
            item.proposed_requirement.requirement_id: item
            for item in draft.evidence_requirement_drafts
            if item.procedure_catalog_item_id is not None
        }
        procedure_anchor_refs: dict[str, list[str]] = {}
        for requirement_id, item in procedure_drafts.items():
            refs = self._source_refs(item.source_refs, request.source_spans)
            procedure_anchor_refs[requirement_id] = [
                f"{version_id}:{ref}" for ref in refs
            ]
        authority_data = {
            "authority_record_id": f"authority:{uuid.uuid4().hex}",
            "protocol_version_id": version_id,
            "protocol_document_sha256": document_sha256,
            "study_phase": draft.selected_phase,
            "official_rules": draft.proposed_rules,
            "official_workflow_stages": official_workflow_stages,
            "rule_source_anchor_refs": rule_anchor_refs,
            "procedure_evidence_requirements": self._procedure_requirements(draft),
            "procedure_requirement_source_anchor_refs": procedure_anchor_refs,
            "verified_by": request.actor,
            "verified_at": self._published_at(request),
            "verification_method": "human_verified_official_protocol",
        }
        authority_draft = ProtocolAuthorityRecord.model_construct(
            **authority_data,
            authority_record_sha256="0" * 64,
        )
        authority = ProtocolAuthorityRecord(
            **authority_data,
            authority_record_sha256=canonical_hash(
                authority_draft.model_dump(
                    mode="json", exclude={"authority_record_sha256"}
                )
            ),
        )
        all_refs = sorted(
            {
                ref
                for refs in (
                    *rule_anchor_refs.values(),
                    *procedure_anchor_refs.values(),
                )
                for ref in refs
            }
        )
        source_records = [
            build_protocol_source_record(
                source_ref=ref,
                protocol_version_id=version_id,
                protocol_document_sha256=document_sha256,
                locator=ref,
            )
            for ref in all_refs
        ]
        return authority, source_records

    def _build_confirmation(
        self,
        command: ServiceCommandEvent,
        authority: ProtocolAuthorityRecord,
    ) -> ProtocolAuthorityConfirmation:
        data = {
            "confirmation_id": f"confirmation:{uuid.uuid4().hex}",
            "command_id": command.command_id,
            "protocol_version_id": authority.protocol_version_id,
            "protocol_document_sha256": authority.protocol_document_sha256,
            "authority_record_id": authority.authority_record_id,
            "authority_record_sha256": authority.authority_record_sha256,
            "confirmed_by": command.actor_id,
            "confirmed_at": command.occurred_at,
            "action": "accept_protocol_authority",
            "recorded_by_service": "enrollment-review-app",
        }
        draft = ProtocolAuthorityConfirmation.model_construct(
            **data, confirmation_sha256="0" * 64
        )
        return ProtocolAuthorityConfirmation(
            **data,
            confirmation_sha256=canonical_hash(
                draft.model_dump(mode="json", exclude={"confirmation_sha256"})
            ),
        )

    def _build_authority_gate(
        self,
        authority: ProtocolAuthorityRecord,
        confirmation: ProtocolAuthorityConfirmation,
        *,
        version_id: str,
        sha256: str,
    ) -> GateResult:
        payload = {
            "authority_record": authority.model_dump(mode="json"),
            "confirmation": confirmation.model_dump(mode="json"),
        }
        return GateResult(
            gate_result_id=f"gate:authority:{uuid.uuid4().hex}",
            gate_name="protocol-authority-human-acceptance-gate",
            result=GateOutcome.ACCEPTED,
            input_scope_hash=canonical_hash(payload),
            input_revision_map={version_id: 1},
            input_entity_refs=[
                version_id,
                sha256,
                authority.authority_record_id,
                confirmation.confirmation_id,
                confirmation.command_id,
            ],
            accepted_entity_refs=[authority.authority_record_id],
            affected_scope=[version_id],
            recompute_scope=[version_id],
            idempotency_key=(
                f"protocol-authority:{version_id}:{authority.authority_record_id}"
            ),
            created_at=confirmation.confirmed_at,
            output_hash=canonical_hash(payload),
        )

    def _build_manifest(
        self,
        authority: ProtocolAuthorityRecord,
        source_records: list[ProtocolSourceRecord],
        *,
        study_phase,
    ) -> ProtocolIntegrityManifest:
        data = {
            "manifest_id": f"manifest:{uuid.uuid4().hex}",
            "protocol_version_id": authority.protocol_version_id,
            "protocol_document_sha256": authority.protocol_document_sha256,
            "study_phase": study_phase,
            "source_refs": [record.source_ref for record in source_records],
            "authority_record_id": authority.authority_record_id,
            "authority_record_sha256": authority.authority_record_sha256,
            "authoritative_rule_set_sha256": canonical_hash(
                [item.model_dump(mode="json") for item in authority.official_rules]
            ),
            "authoritative_workflow_sha256": canonical_hash(
                [
                    item.model_dump(mode="json")
                    for item in authority.official_workflow_stages
                ]
            ),
        }
        draft = ProtocolIntegrityManifest.model_construct(
            **data, manifest_sha256="0" * 64
        )
        return ProtocolIntegrityManifest(
            **data,
            manifest_sha256=canonical_hash(
                draft.model_dump(mode="json", exclude={"manifest_sha256"})
            ),
        )

    def _build_integrity_gate(
        self,
        rule_set: RuleSet,
        *,
        workflow_stages: list[WorkflowStage],
        manifest: ProtocolIntegrityManifest,
        authority_record: ProtocolAuthorityRecord,
        authority_confirmation: ProtocolAuthorityConfirmation,
        authority_gate_result: GateResult,
    ) -> GateResult:
        payload = {
            "rule_set": rule_set.model_dump(mode="json"),
            "workflow_stages": [item.model_dump(mode="json") for item in workflow_stages],
            "protocol_version": {
                "protocol_version_id": rule_set.protocol_version_id,
                "rule_set_revision": rule_set.revision,
            },
            "manifest": manifest.model_dump(mode="json"),
            "authority_record": authority_record.model_dump(mode="json"),
            "authority_confirmation": authority_confirmation.model_dump(mode="json"),
            "authority_gate_result": authority_gate_result.model_dump(mode="json"),
        }
        return GateResult(
            gate_result_id=f"gate:integrity:{uuid.uuid4().hex}",
            gate_name="protocol-integrity-gate",
            result=GateOutcome.ACCEPTED,
            input_scope_hash=canonical_hash(payload),
            input_revision_map={
                rule_set.protocol_version_id: rule_set.revision
            },
            input_entity_refs=[
                rule_set.protocol_version_id,
                authority_record.authority_record_id,
                authority_confirmation.confirmation_id,
                authority_gate_result.gate_result_id,
                manifest.manifest_id,
                rule_set.rule_set_id,
            ],
            accepted_entity_refs=[manifest.manifest_id, rule_set.rule_set_id],
            affected_scope=[rule_set.protocol_version_id],
            recompute_scope=[rule_set.protocol_version_id],
            idempotency_key=(
                f"protocol-integrity:{rule_set.protocol_version_id}:"
                f"{rule_set.revision}"
            ),
            created_at=authority_gate_result.created_at,
            output_hash=canonical_hash(payload),
        )

    def _templates(
        self,
        rule_set: RuleSet,
        workflow_stages: list[WorkflowStage],
        procedure_requirements: list[EvidenceRequirement],
    ) -> list[EvidenceExpectationTemplate]:
        return project_evidence_expectation_templates(
            rule_set=rule_set,
            workflow_stages=workflow_stages,
            procedure_requirements=procedure_requirements,
            created_at=self.now(),
        )

    # ------------------------------------------------------------------ 持久化

    def _persist(
        self,
        session: Session,
        *,
        request: ProtocolPublicationRequest,
        revision: ProtocolDraftRevision,
        draft: ProtocolDeconstructionDraft,
        protocol_version: ProtocolDocumentVersion,
        rule_set: RuleSet,
        procedure_requirements: list[EvidenceRequirement],
        authority: ProtocolAuthorityRecord,
        source_records: list[ProtocolSourceRecord],
        command: ServiceCommandEvent,
        confirmation: ProtocolAuthorityConfirmation,
        manifest: ProtocolIntegrityManifest,
        authority_gate: GateResult,
        integrity_gate: GateResult,
        target_project: Project | None,
        workflow_stages: list[WorkflowStage],
    ) -> None:
        # 方案版本记录（先于 RuleSet/Project 外键依赖）。
        AppendRepository(session, PROTOCOL_DOC_CONFIG).save(protocol_version)
        source_repo = AppendRepository(session, SOURCE_RECORD_CONFIG)
        for record in source_records:
            source_repo.save(record)
        AppendRepository(session, AUTHORITY_RECORD_CONFIG).save(authority)
        AppendRepository(session, COMMAND_EVENT_CONFIG).save(command)
        AppendRepository(session, AUTHORITY_CONFIRMATION_CONFIG).save(confirmation)
        AppendRepository(session, INTEGRITY_MANIFEST_CONFIG).save(manifest)
        gate_repo = AppendRepository(session, GATE_RESULT_CONFIG)
        gate_repo.save(authority_gate)
        gate_repo.save(integrity_gate)

        save_rule_set(
            session,
            rule_set,
            procedure_requirements=procedure_requirements,
        )
        stage_repo = AppendRepository(session, WORKFLOW_STAGE_CONFIG)
        for stage in workflow_stages:
            stage_repo.save(
                stage,
                scope={
                    "protocol_version_id": protocol_version.protocol_version_id,
                    "study_phase": draft.selected_phase.value,
                },
            )

        if target_project is not None:
            project_repo = ProjectRepository(session)
            project_repo.update(
                project_id=target_project.project_id,
                expected_revision=target_project.revision,
                changes={
                    "protocol_version": protocol_version.model_dump(mode="json"),
                    "rule_set_id": rule_set.rule_set_id,
                    "study_phase": draft.selected_phase,
                },
                rule_set_revision=rule_set.revision,
            )
        else:
            ProjectRepository(session).save(
                Project(
                    project_id=draft.project_id,
                    project_code=protocol_version.protocol_code,
                    project_name=request.source_input.identity_decision.project_name,
                    study_phase=draft.selected_phase,
                    protocol_version=protocol_version,
                    rule_set_id=rule_set.rule_set_id,
                ),
                rule_set_revision=rule_set.revision,
            )

        # 无受试者模板投影（可重建，同一事务落库）。
        templates = self._templates(
            rule_set, workflow_stages, procedure_requirements
        )
        save_expectation_templates(session, templates)

        # 发布成功：草稿链头标记为已发布。
        draft_service = ProtocolDraftService(
            session,
            revision_repository=ProtocolDraftRevisionRepository(session),
        )
        draft_service.mark_published(
            draft_id=revision.draft_id,
            expected_revision_id=revision.revision_id,
        )
