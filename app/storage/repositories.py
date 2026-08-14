"""领域仓储：Pydantic 合同 <-> ORM 适配、scope 校验与组合写入。

约定：

- 写操作全部在调用方持有的短事务内完成（``with session.begin()`` 由服务层
  持有边界）；本模块在 flush 处给出类型化错误（唯一冲突、引用缺失、跨 scope
  违规），并在失败时回滚会话；
- 不可变记录追加写；读取时校验 payload 哈希并交叉核对规范化列与 payload
  （漂移即 :class:`PersistedContractInvalid`），绝不返回空对象；
- 列表查询单条 SELECT，禁止按实体 N+1；
- 关键跨项目/跨方案版本/跨审核节点关系除真实外键外，再经服务层 scope 校验
  拒绝，杜绝只靠 JSON 内 ID 的“软引用”。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.contracts import (
    ActionRequest,
    AgentCallContract,
    AssessmentCandidate,
    ClinicalFact,
    EpisodeRollup,
    EvidenceExpectation,
    EvidenceNormalizationCandidate,
    EvidenceSnapshot,
    EvidenceSpan,
    EvidenceRequirement,
    FinalAssessment,
    FixtureV1,
    JobEvent,
    ModelConfigContract,
    PatientProfile,
    Project,
    PromptVersion,
    ProtocolAuthorityRecord,
    ProtocolIntegrityManifest,
    ReviewEpisode,
    ReviewRun,
    ReviewRunDiff,
    Rule,
    RuleComponent,
    RuleSet,
    Subject,
    WorkflowStage,
)
from app.domain.contracts.agents import CriticRun, GateResult
from app.domain.contracts.context import ReviewContextSnapshot
from app.domain.contracts.evidence import ConflictGroup, SourceDocumentVersion
from app.domain.contracts.review import ActionTransition, ProtocolDocumentVersion
from app.domain.contracts.rules import (
    ProtocolAuthorityConfirmation,
    ProtocolSourceRecord,
    ServiceCommandEvent,
)
from app.storage.codecs import (
    PersistedContractInvalid,
    check_column_mirrors,
    decode_contract,
    encode_contract,
    encode_value,
    parse_datetime_column,
    payload_get,
    utc_now,
)
from app.storage.concurrency import apply_revisioned_update
from app.storage.models import (
    ActionRequestRecord,
    ActionTransitionRecord,
    AgentCallRecord,
    AssessmentCandidateRecord,
    ClinicalFactRecord,
    ConflictGroupRecord,
    CriticRunRecord,
    EpisodeRollupRecord,
    EvidenceExpectationRecord,
    EvidenceNormalizationCandidateRecord,
    EvidenceRequirementRecord,
    EvidenceSnapshotRecord,
    EvidenceSpanRecord,
    FinalAssessmentRecord,
    GateResultRecord,
    JobCheckpointRecord,
    JobEventRecord,
    JobRecord,
    JobStepRecord,
    ModelConfigRecord,
    PatientProfileRecord,
    ProjectRecord,
    PromptVersionRecord,
    ProtocolAuthorityConfirmationRecord,
    ProtocolAuthorityRecordRow,
    ProtocolDocumentVersionRecord,
    ProtocolIntegrityManifestRecord,
    ProtocolSourceRecordRow,
    ReviewContextSnapshotRecord,
    ReviewEpisodeRecord,
    ReviewRunDiffRecord,
    ReviewRunRecord,
    RuleComponentRecord,
    RuleRecord,
    RuleSetRecord,
    ServiceCommandEventRecord,
    SourceDocumentVersionRecord,
    SubjectRecord,
    WorkflowStageRecord,
    action_transition_spans,
    agent_call_gate_results,
    agent_call_sources,
    clinical_fact_spans,
    evidence_expectation_spans,
    evidence_snapshot_documents,
    final_assessment_facts,
    final_assessment_spans,
    job_step_dependencies,
    workflow_stage_requirements,
)

# ---------------------------------------------------------------------------
# 错误类型
# ---------------------------------------------------------------------------


class RepositoryError(RuntimeError):
    """存储层基础错误。"""


class NotFoundError(RepositoryError):
    """主键不存在。"""


class DuplicateRecordError(RepositoryError):
    """唯一键冲突：同 ID/同键记录已存在。"""


class InvalidReferenceError(RepositoryError):
    """外键引用不存在：关系被数据库拒绝。"""


class ScopeViolationError(RepositoryError):
    """跨项目/跨方案版本/跨审核节点 scope 不一致，被服务校验拒绝。"""


def _flush_guarded(session: Session) -> None:
    """flush 并把唯一/外键冲突转换为类型化错误（失败时回滚会话）。"""
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        message = str(exc.orig) if exc.orig is not None else str(exc)
        upper = message.upper()
        if "UNIQUE" in upper:
            raise DuplicateRecordError(f"唯一约束冲突：{message}") from exc
        if "FOREIGN KEY" in upper:
            raise InvalidReferenceError(f"引用缺失被数据库拒绝：{message}") from exc
        raise RepositoryError(f"写入失败：{message}") from exc


def _get_required(session: Session, record_cls: type, ident: Any, what: str) -> Any:
    record = session.get(record_cls, ident)
    if record is None:
        raise InvalidReferenceError(f"{what} {ident!r} 不存在，无法建立该关系")
    return record


def _insert_revisioned(
    session: Session,
    record_cls: type,
    payload_json: str,
    payload_sha256: str,
    columns: dict[str, Any],
) -> Any:
    now = utc_now()
    row = record_cls(
        payload_json=payload_json,
        payload_sha256=payload_sha256,
        revision=1,
        created_at=now,
        updated_at=now,
        **columns,
    )
    session.add(row)
    _flush_guarded(session)
    return row


# ---------------------------------------------------------------------------
# 追加写仓储骨架
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssocSpec:
    """有序多值引用 ``(owner, ref, position)`` 关联表写入说明。"""

    table: Any
    owner_column: str
    owner_value_key: str  # payload key（点路径）提供 owner id
    refs_payload_key: str  # payload key 提供有序 ref 列表


@dataclass(frozen=True)
class AppendConfig:
    record_cls: type
    contract_type: type[BaseModel]
    entity_name: str
    specs: dict[str, str]  # 列名 -> payload key（点路径）
    datetime_cols: frozenset[str] = frozenset()
    mirrors: dict[str, str] = field(default_factory=dict)  # 列名 -> payload key
    assoc: tuple[AssocSpec, ...] = ()
    created_at_key: str | None = None  # payload 内提供记录创建时间的字段
    scope_check: Any = None  # callable(session, contract, payload) -> None


class AppendRepository:
    """追加写：payload JSON/hash + 规范化列；读取哈希校验 + 列/payload 交叉核对。"""

    def __init__(self, session: Session, config: AppendConfig) -> None:
        self.session = session
        self.config = config

    # -- 写 ---------------------------------------------------------------

    def _build_columns(
        self, payload: dict[str, Any], scope: dict[str, Any] | None
    ) -> dict[str, Any]:
        columns: dict[str, Any] = {}
        for column, key in self.config.specs.items():
            value = payload_get(payload, key)
            if column in self.config.datetime_cols:
                value = parse_datetime_column(value) if value is not None else None
            columns[column] = value
        if scope:
            known = set(self.config.record_cls.__table__.c.keys())
            columns.update({name: value for name, value in scope.items() if name in known})
        return columns

    def save(self, contract: BaseModel, *, scope: dict[str, Any] | None = None) -> BaseModel:
        payload_json, payload_sha256 = encode_contract(contract)
        payload = json.loads(payload_json)
        if self.config.scope_check is not None:
            self.config.scope_check(self.session, contract, payload)
        columns = self._build_columns(payload, scope)
        created_at_key = self.config.created_at_key
        if created_at_key is not None and payload.get(created_at_key) is not None:
            created_at = parse_datetime_column(payload[created_at_key])
        else:
            created_at = utc_now()
        record = self.config.record_cls(
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            created_at=created_at,
            **columns,
        )
        self.session.add(record)
        _flush_guarded(self.session)
        for assoc in self.config.assoc:
            self._write_assoc(assoc, payload)
            _flush_guarded(self.session)
        return contract

    def _write_assoc(self, assoc: AssocSpec, payload: dict[str, Any]) -> None:
        owner_value = payload_get(payload, assoc.owner_value_key)
        refs = payload_get(payload, assoc.refs_payload_key) or []
        if not refs:
            return
        table = assoc.table
        ref_column = next(
            name for name in table.c.keys() if name not in {assoc.owner_column, "position"}
        )
        self.session.execute(
            insert(table),
            [
                {
                    assoc.owner_column: owner_value,
                    ref_column: ref,
                    "position": position,
                }
                for position, ref in enumerate(refs)
            ],
        )

    # -- 读 ---------------------------------------------------------------

    def get(self, *ident: str | int) -> BaseModel:
        key = ident if len(ident) > 1 else ident[0]
        record = self.session.get(self.config.record_cls, key)
        if record is None:
            raise NotFoundError(f"{self.config.entity_name} {ident!r} 不存在")
        return self._decode(record)

    def get_or_none(self, *ident: str | int) -> BaseModel | None:
        key = ident if len(ident) > 1 else ident[0]
        record = self.session.get(self.config.record_cls, key)
        return self._decode(record) if record is not None else None

    def _decode(self, record: Any) -> BaseModel:
        contract = decode_contract(
            self.config.contract_type, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(self.config.entity_name, record, payload, self.config.mirrors)
        return contract


# ---------------------------------------------------------------------------
# scope 校验（外键之外的跨实体一致性）
# ---------------------------------------------------------------------------


def _check_snapshot_scope(session: Session, snapshot: EvidenceSnapshot) -> None:
    episode = _get_required(
        session, ReviewEpisodeRecord, snapshot.review_episode_id, "ReviewEpisode"
    )
    if episode.subject_id != snapshot.subject_id:
        raise ScopeViolationError(
            f"EvidenceSnapshot {snapshot.evidence_snapshot_id} 的 subject 超出其 episode"
        )


def _check_fact_scope(session: Session, fact: ClinicalFact) -> None:
    episode = _get_required(
        session, ReviewEpisodeRecord, fact.review_episode_id, "ReviewEpisode"
    )
    if episode.subject_id != fact.subject_id:
        raise ScopeViolationError(f"ClinicalFact {fact.fact_id} 的 subject 超出其 episode")
    if episode.project_id != fact.project_id:
        raise ScopeViolationError(f"ClinicalFact {fact.fact_id} 的 project 超出其 episode")
    snapshot = _get_required(
        session, EvidenceSnapshotRecord, fact.evidence_snapshot_id, "EvidenceSnapshot"
    )
    if snapshot.review_episode_id != fact.review_episode_id:
        raise ScopeViolationError(f"ClinicalFact {fact.fact_id} 的 snapshot 超出其 episode")
    if snapshot.subject_id != fact.subject_id:
        raise ScopeViolationError(f"ClinicalFact {fact.fact_id} 的 snapshot 超出其 subject")


def _check_run_scope(session: Session, run: ReviewRun) -> None:
    episode = _get_required(
        session, ReviewEpisodeRecord, run.review_episode_id, "ReviewEpisode"
    )
    if episode.protocol_version_id != run.protocol_version_id:
        raise ScopeViolationError(
            f"ReviewRun {run.review_run_id} 的 protocol_version 与 episode 不一致"
        )
    if episode.rule_set_revision != run.rule_set_revision:
        raise ScopeViolationError(
            f"ReviewRun {run.review_run_id} 的 rule_set_revision 与 episode 不一致"
        )
    if episode.evidence_snapshot_id != run.evidence_snapshot_id:
        raise ScopeViolationError(
            f"ReviewRun {run.review_run_id} 的 evidence_snapshot 与 episode 不一致"
        )


def _check_component_exists(session: Session, rule_set_id: str, revision: int, component_id: str) -> None:
    record = session.get(RuleComponentRecord, (rule_set_id, revision, component_id))
    if record is None:
        raise ScopeViolationError(
            f"RuleComponent {component_id} 不属于 RuleSet {rule_set_id} revision {revision}"
        )


def _check_assessment_scope(session: Session, assessment: FinalAssessment) -> None:
    episode = _get_required(
        session, ReviewEpisodeRecord, assessment.review_episode_id, "ReviewEpisode"
    )
    if episode.project_id != assessment.project_id:
        raise ScopeViolationError(
            f"FinalAssessment {assessment.assessment_id} 的 project 超出其 episode"
        )
    if episode.subject_id != assessment.subject_id:
        raise ScopeViolationError(
            f"FinalAssessment {assessment.assessment_id} 的 subject 超出其 episode"
        )
    if episode.rule_set_id != assessment.rule_set_id:
        raise ScopeViolationError(
            f"FinalAssessment {assessment.assessment_id} 的 rule_set 与 episode 不一致"
        )
    if episode.rule_set_revision != assessment.rule_set_revision:
        raise ScopeViolationError(
            f"FinalAssessment {assessment.assessment_id} 的 rule_set_revision 与 episode 不一致"
        )
    run = _get_required(session, ReviewRunRecord, assessment.review_run_id, "ReviewRun")
    if run.review_episode_id != assessment.review_episode_id:
        raise ScopeViolationError(
            f"FinalAssessment {assessment.assessment_id} 的 run 超出其 episode"
        )
    if run.evidence_snapshot_id != assessment.evidence_snapshot_id:
        raise ScopeViolationError(
            f"FinalAssessment {assessment.assessment_id} 的 snapshot 超出其 run"
        )
    _check_component_exists(
        session, assessment.rule_set_id, assessment.rule_set_revision, assessment.rule_component_id
    )


def _check_action_scope(session: Session, action: ActionRequest) -> None:
    episode = _get_required(
        session, ReviewEpisodeRecord, action.review_episode_id, "ReviewEpisode"
    )
    if episode.project_id != action.project_id or episode.subject_id != action.subject_id:
        raise ScopeViolationError(
            f"ActionRequest {action.action_id} 的 subject/project 超出其 episode"
        )
    if episode.rule_set_id != action.rule_set_id:
        raise ScopeViolationError(f"ActionRequest {action.action_id} 的 rule_set 与 episode 不一致")
    if episode.rule_set_revision != action.rule_set_revision:
        raise ScopeViolationError(
            f"ActionRequest {action.action_id} 的 rule_set_revision 与 episode 不一致"
        )
    run = _get_required(session, ReviewRunRecord, action.review_run_id, "ReviewRun")
    if run.review_episode_id != action.review_episode_id:
        raise ScopeViolationError(f"ActionRequest {action.action_id} 的 run 超出其 episode")
    if run.evidence_snapshot_id != action.evidence_snapshot_id:
        raise ScopeViolationError(f"ActionRequest {action.action_id} 的 snapshot 超出其 run")
    _check_component_exists(
        session, action.rule_set_id, action.rule_set_revision, action.rule_component_id
    )
    assessment = _get_required(
        session, FinalAssessmentRecord, action.assessment_id, "FinalAssessment"
    )
    if assessment.review_episode_id != action.review_episode_id:
        raise ScopeViolationError(
            f"ActionRequest {action.action_id} 的 assessment 超出其 episode"
        )


def _check_agent_call_scope(session: Session, call: AgentCallContract) -> None:
    if call.review_episode_id is None:
        return
    episode = _get_required(
        session, ReviewEpisodeRecord, call.review_episode_id, "ReviewEpisode"
    )
    if call.subject_id is not None and episode.subject_id != call.subject_id:
        raise ScopeViolationError(f"AgentCall {call.agent_call_id} 的 subject 超出其 episode")
    if call.rule_set_id is not None and episode.rule_set_id != call.rule_set_id:
        raise ScopeViolationError(f"AgentCall {call.agent_call_id} 的 rule_set 与 episode 不一致")
    if call.review_run_id is not None:
        run = _get_required(session, ReviewRunRecord, call.review_run_id, "ReviewRun")
        if run.review_episode_id != call.review_episode_id:
            raise ScopeViolationError(f"AgentCall {call.agent_call_id} 的 run 超出其 episode")
        if (
            call.evidence_snapshot_id is not None
            and run.evidence_snapshot_id != call.evidence_snapshot_id
        ):
            raise ScopeViolationError(f"AgentCall {call.agent_call_id} 的 snapshot 超出其 run")


def _check_expectation_scope(
    session: Session, expectation: EvidenceExpectation, payload: dict[str, Any]
) -> None:
    episode = _get_required(
        session, ReviewEpisodeRecord, expectation.review_episode_id, "ReviewEpisode"
    )
    requirement = session.get(
        EvidenceRequirementRecord,
        (episode.rule_set_id, episode.rule_set_revision, expectation.requirement_id),
    )
    if requirement is None:
        raise ScopeViolationError(
            f"EvidenceExpectation {expectation.expectation_id} 的 requirement "
            f"{expectation.requirement_id} 不属于 episode 的 RuleSet "
            f"{episode.rule_set_id} revision {episode.rule_set_revision}"
        )


def _check_episode_scope(session: Session, episode: ReviewEpisode) -> None:
    subject = _get_required(session, SubjectRecord, episode.subject_id, "Subject")
    if subject.project_id != episode.project_id:
        raise ScopeViolationError(
            f"ReviewEpisode {episode.review_episode_id} 的 project 与 subject 不一致"
        )
    rule_set = session.get(RuleSetRecord, (episode.rule_set_id, episode.rule_set_revision))
    if rule_set is None:
        raise ScopeViolationError(
            f"ReviewEpisode {episode.review_episode_id} 引用的 RuleSet "
            f"{episode.rule_set_id} revision {episode.rule_set_revision} 不存在"
        )
    if rule_set.protocol_version_id != episode.protocol_version_id:
        raise ScopeViolationError(
            f"ReviewEpisode {episode.review_episode_id} 的 rule_set 与 protocol_version 不一致"
        )


def _check_project_scope(
    session: Session, project: Project, payload: dict[str, Any], rule_set_revision: int
) -> None:
    _get_required(
        session,
        ProtocolDocumentVersionRecord,
        project.protocol_version.protocol_version_id,
        "ProtocolDocumentVersion",
    )
    rule_set = session.get(RuleSetRecord, (project.rule_set_id, rule_set_revision))
    if rule_set is None:
        raise ScopeViolationError(
            f"Project {project.project_id} 引用的 RuleSet {project.rule_set_id} "
            f"revision {rule_set_revision} 不存在"
        )
    if rule_set.protocol_version_id != project.protocol_version.protocol_version_id:
        raise ScopeViolationError(
            f"Project {project.project_id} 的 rule_set 与 protocol_version 不一致"
        )


# ---------------------------------------------------------------------------
# 追加写配置注册表
# ---------------------------------------------------------------------------


def _config(
    record_cls: type,
    contract_type: type[BaseModel],
    specs: dict[str, str],
    **kwargs: Any,
) -> AppendConfig:
    return AppendConfig(
        record_cls=record_cls,
        contract_type=contract_type,
        entity_name=contract_type.__name__,
        specs=specs,
        **kwargs,
    )


PROTOCOL_DOC_CONFIG = _config(
    ProtocolDocumentVersionRecord,
    ProtocolDocumentVersion,
    {
        "protocol_version_id": "protocol_version_id",
        "protocol_code": "protocol_code",
        "official_version": "official_version",
        "official_date_value": "official_date.value",
        "official_date_precision": "official_date.precision",
        "sha256": "sha256",
        "integrity_manifest_sha256": "integrity_manifest_sha256",
        "authority_record_sha256": "authority_record_sha256",
        "authority_confirmation_id": "authority_confirmation_id",
        "authority_gate_result_id": "authority_gate_result_id",
        "integrity_gate_result_id": "integrity_gate_result_id",
    },
    datetime_cols=frozenset({"official_date_value"}),
    mirrors={
        "protocol_code": "protocol_code",
        "official_version": "official_version",
        "official_date_precision": "official_date.precision",
        "sha256": "sha256",
        "authority_confirmation_id": "authority_confirmation_id",
        "authority_gate_result_id": "authority_gate_result_id",
        "integrity_gate_result_id": "integrity_gate_result_id",
    },
)

AUTHORITY_RECORD_CONFIG = _config(
    ProtocolAuthorityRecordRow,
    ProtocolAuthorityRecord,
    {
        "authority_record_id": "authority_record_id",
        "protocol_version_id": "protocol_version_id",
        "study_phase": "study_phase",
        "verified_at": "verified_at",
    },
    datetime_cols=frozenset({"verified_at"}),
    mirrors={"protocol_version_id": "protocol_version_id", "study_phase": "study_phase"},
)

SOURCE_RECORD_CONFIG = _config(
    ProtocolSourceRecordRow,
    ProtocolSourceRecord,
    {
        "source_ref": "source_ref",
        "protocol_version_id": "protocol_version_id",
        "protocol_document_sha256": "protocol_document_sha256",
    },
    mirrors={
        "protocol_version_id": "protocol_version_id",
        "protocol_document_sha256": "protocol_document_sha256",
    },
)

COMMAND_EVENT_CONFIG = _config(
    ServiceCommandEventRecord,
    ServiceCommandEvent,
    {
        "command_id": "command_id",
        "protocol_version_id": "protocol_version_id",
        "authority_record_id": "authority_record_id",
        "occurred_at": "occurred_at",
    },
    datetime_cols=frozenset({"occurred_at"}),
    mirrors={"protocol_version_id": "protocol_version_id", "authority_record_id": "authority_record_id"},
)

AUTHORITY_CONFIRMATION_CONFIG = _config(
    ProtocolAuthorityConfirmationRecord,
    ProtocolAuthorityConfirmation,
    {
        "confirmation_id": "confirmation_id",
        "command_id": "command_id",
        "protocol_version_id": "protocol_version_id",
        "authority_record_id": "authority_record_id",
        "confirmed_at": "confirmed_at",
    },
    datetime_cols=frozenset({"confirmed_at"}),
    mirrors={
        "command_id": "command_id",
        "protocol_version_id": "protocol_version_id",
        "authority_record_id": "authority_record_id",
    },
)

INTEGRITY_MANIFEST_CONFIG = _config(
    ProtocolIntegrityManifestRecord,
    ProtocolIntegrityManifest,
    {
        "manifest_id": "manifest_id",
        "protocol_version_id": "protocol_version_id",
        "authority_record_id": "authority_record_id",
    },
    mirrors={
        "protocol_version_id": "protocol_version_id",
        "authority_record_id": "authority_record_id",
    },
)

SOURCE_DOCUMENT_CONFIG = _config(
    SourceDocumentVersionRecord,
    SourceDocumentVersion,
    {
        "source_document_version_id": "source_document_version_id",
        "sha256": "sha256",
        "document_type": "document_type",
        "source_party": "source_party",
        "upload_mode": "upload_mode",
        "review_stage": "review_stage",
    },
    mirrors={
        "sha256": "sha256",
        "document_type": "document_type",
        "source_party": "source_party",
        "upload_mode": "upload_mode",
        "review_stage": "review_stage",
    },
)

EVIDENCE_SPAN_CONFIG = _config(
    EvidenceSpanRecord,
    EvidenceSpan,
    {
        "evidence_span_id": "evidence_span_id",
        "source_document_version_id": "source_document_version_id",
        "page_number": "page_number",
        "precision": "precision",
    },
    mirrors={
        "source_document_version_id": "source_document_version_id",
        "page_number": "page_number",
        "precision": "precision",
    },
)

SNAPSHOT_CONFIG = _config(
    EvidenceSnapshotRecord,
    EvidenceSnapshot,
    {
        "evidence_snapshot_id": "evidence_snapshot_id",
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "upload_mode": "upload_mode",
        "prior_snapshot_id": "prior_snapshot_id",
    },
    created_at_key="created_at",
    assoc=(
        AssocSpec(
            evidence_snapshot_documents,
            "evidence_snapshot_id",
            "evidence_snapshot_id",
            "source_document_version_ids",
        ),
    ),
    scope_check=lambda session, contract, payload: _check_snapshot_scope(session, contract),
    mirrors={
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "upload_mode": "upload_mode",
        "prior_snapshot_id": "prior_snapshot_id",
    },
)

CLINICAL_FACT_CONFIG = _config(
    ClinicalFactRecord,
    ClinicalFact,
    {
        "fact_id": "fact_id",
        "project_id": "project_id",
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "evidence_snapshot_id": "evidence_snapshot_id",
        "fact_type": "fact_type",
        "polarity": "polarity",
        "certainty": "certainty",
        "value_json": "value",
        "unit": "unit",
        "effective_date_json": "effective_date",
        "conflict_group_id": "conflict_group_id",
    },
    assoc=(AssocSpec(clinical_fact_spans, "fact_id", "fact_id", "evidence_span_ids"),),
    scope_check=lambda session, contract, payload: _check_fact_scope(session, contract),
    mirrors={
        "project_id": "project_id",
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "evidence_snapshot_id": "evidence_snapshot_id",
        "fact_type": "fact_type",
        "polarity": "polarity",
        "certainty": "certainty",
        "value_json": "value",
        "unit": "unit",
        "conflict_group_id": "conflict_group_id",
    },
)

EXPECTATION_CONFIG = _config(
    EvidenceExpectationRecord,
    EvidenceExpectation,
    {
        "expectation_id": "expectation_id",
        "requirement_id": "requirement_id",
        "review_episode_id": "review_episode_id",
        "status": "status",
        "gap_type": "gap_type",
    },
    assoc=(
        AssocSpec(
            evidence_expectation_spans,
            "expectation_id",
            "expectation_id",
            "evidence_span_ids",
        ),
    ),
    scope_check=lambda session, contract, payload: _check_expectation_scope(
        session, contract, payload
    ),
    mirrors={
        "requirement_id": "requirement_id",
        "review_episode_id": "review_episode_id",
        "status": "status",
        "gap_type": "gap_type",
    },
)

CONFLICT_GROUP_CONFIG = _config(
    ConflictGroupRecord,
    ConflictGroup,
    {"conflict_group_id": "conflict_group_id"},
)

NORMALIZATION_CANDIDATE_CONFIG = _config(
    EvidenceNormalizationCandidateRecord,
    EvidenceNormalizationCandidate,
    {
        "candidate_id": "candidate_id",
        "project_id": "project_id",
        "protocol_version_id": "protocol_version_id",
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "evidence_snapshot_id": "evidence_snapshot_id",
        "created_by_agent_call_id": "created_by_agent_call_id",
    },
    mirrors={
        "project_id": "project_id",
        "protocol_version_id": "protocol_version_id",
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "evidence_snapshot_id": "evidence_snapshot_id",
        "created_by_agent_call_id": "created_by_agent_call_id",
    },
)

PATIENT_PROFILE_CONFIG = _config(
    PatientProfileRecord,
    PatientProfile,
    {
        "patient_profile_id": "patient_profile_id",
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "stale": "stale",
    },
    mirrors={
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "stale": "stale",
    },
)

REVIEW_RUN_CONFIG = _config(
    ReviewRunRecord,
    ReviewRun,
    {
        "review_run_id": "review_run_id",
        "review_episode_id": "review_episode_id",
        "protocol_version_id": "protocol_version_id",
        "rule_set_revision": "rule_set_revision",
        "evidence_snapshot_id": "evidence_snapshot_id",
        "started_at": "started_at",
        "completed_at": "completed_at",
        "supersedes_review_run_id": "supersedes_review_run_id",
    },
    datetime_cols=frozenset({"started_at", "completed_at"}),
    scope_check=lambda session, contract, payload: _check_run_scope(session, contract),
    mirrors={
        "review_episode_id": "review_episode_id",
        "protocol_version_id": "protocol_version_id",
        "rule_set_revision": "rule_set_revision",
        "evidence_snapshot_id": "evidence_snapshot_id",
        "supersedes_review_run_id": "supersedes_review_run_id",
    },
)

ASSESSMENT_CANDIDATE_CONFIG = _config(
    AssessmentCandidateRecord,
    AssessmentCandidate,
    {
        "assessment_candidate_id": "assessment_candidate_id",
        "agent_call_id": "agent_call_id",
        "project_id": "project_id",
        "protocol_version_id": "protocol_version_id",
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "review_run_id": "review_run_id",
        "evidence_snapshot_id": "evidence_snapshot_id",
        "rule_set_id": "rule_set_id",
        "rule_set_revision": "rule_set_revision",
        "rule_component_id": "rule_component_id",
    },
    mirrors={
        "project_id": "project_id",
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "review_run_id": "review_run_id",
        "evidence_snapshot_id": "evidence_snapshot_id",
        "rule_set_id": "rule_set_id",
        "rule_set_revision": "rule_set_revision",
        "rule_component_id": "rule_component_id",
    },
)

FINAL_ASSESSMENT_CONFIG = _config(
    FinalAssessmentRecord,
    FinalAssessment,
    {
        "assessment_id": "assessment_id",
        "project_id": "project_id",
        "protocol_version_id": "protocol_version_id",
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "review_run_id": "review_run_id",
        "evidence_snapshot_id": "evidence_snapshot_id",
        "rule_set_id": "rule_set_id",
        "rule_set_revision": "rule_set_revision",
        "rule_component_id": "rule_component_id",
        "decision": "decision",
        "blocking_level": "blocking_level",
        "gate_result_id": "gate_result_id",
        "publication_fingerprint": "publication_fingerprint",
    },
    assoc=(
        AssocSpec(final_assessment_facts, "assessment_id", "assessment_id", "used_fact_ids"),
        AssocSpec(final_assessment_spans, "assessment_id", "assessment_id", "evidence_span_ids"),
    ),
    scope_check=lambda session, contract, payload: _check_assessment_scope(session, contract),
    mirrors={
        "project_id": "project_id",
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "review_run_id": "review_run_id",
        "evidence_snapshot_id": "evidence_snapshot_id",
        "rule_set_id": "rule_set_id",
        "rule_set_revision": "rule_set_revision",
        "rule_component_id": "rule_component_id",
        "decision": "decision",
        "blocking_level": "blocking_level",
        "gate_result_id": "gate_result_id",
        "publication_fingerprint": "publication_fingerprint",
    },
)

REVIEW_RUN_DIFF_CONFIG = _config(
    ReviewRunDiffRecord,
    ReviewRunDiff,
    {
        "review_run_diff_id": "review_run_diff_id",
        "prior_review_run_id": "prior_review_run_id",
        "current_review_run_id": "current_review_run_id",
    },
    mirrors={
        "prior_review_run_id": "prior_review_run_id",
        "current_review_run_id": "current_review_run_id",
    },
)

PROMPT_VERSION_CONFIG = _config(
    PromptVersionRecord,
    PromptVersion,
    {
        "prompt_version_id": "prompt_version_id",
        "node": "node",
        "template_sha256": "template_sha256",
        "schema_version_id": "schema_version_id",
    },
    mirrors={
        "node": "node",
        "template_sha256": "template_sha256",
        "schema_version_id": "schema_version_id",
    },
)

MODEL_CONFIG_CONFIG = _config(
    ModelConfigRecord,
    ModelConfigContract,
    {
        "model_config_id": "model_config_id",
        "provider": "provider",
        "model": "model",
        "reasoning_effort": "reasoning_effort",
    },
    mirrors={
        "provider": "provider",
        "model": "model",
        "reasoning_effort": "reasoning_effort",
    },
)

AGENT_CALL_CONFIG = _config(
    AgentCallRecord,
    AgentCallContract,
    {
        "agent_call_id": "agent_call_id",
        "node": "node",
        "output_kind": "output_kind",
        "write_scope": "write_scope",
        "prompt_version_id": "prompt_version_id",
        "model_config_id": "model_config_id",
        "idempotency_key": "idempotency_key",
        "attempt": "attempt",
        "outcome": "outcome",
        "started_at": "started_at",
        "finished_at": "finished_at",
        "project_id": "project_id",
        "protocol_version_id": "protocol_version_id",
        "rule_set_id": "rule_set_id",
        "rule_set_revision": "rule_set_revision",
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "review_run_id": "review_run_id",
        "evidence_snapshot_id": "evidence_snapshot_id",
        "input_tokens": "input_tokens",
        "output_tokens": "output_tokens",
        "estimated_cost": "estimated_cost",
    },
    datetime_cols=frozenset({"started_at", "finished_at"}),
    assoc=(
        AssocSpec(agent_call_sources, "agent_call_id", "agent_call_id", "source_ids"),
        AssocSpec(agent_call_gate_results, "agent_call_id", "agent_call_id", "gate_result_ids"),
    ),
    scope_check=lambda session, contract, payload: _check_agent_call_scope(session, contract),
    mirrors={
        "node": "node",
        "prompt_version_id": "prompt_version_id",
        "model_config_id": "model_config_id",
        "idempotency_key": "idempotency_key",
        "attempt": "attempt",
        "outcome": "outcome",
        "project_id": "project_id",
        "protocol_version_id": "protocol_version_id",
        "rule_set_id": "rule_set_id",
        "rule_set_revision": "rule_set_revision",
        "subject_id": "subject_id",
        "review_episode_id": "review_episode_id",
        "review_run_id": "review_run_id",
        "evidence_snapshot_id": "evidence_snapshot_id",
    },
)

GATE_RESULT_CONFIG = _config(
    GateResultRecord,
    GateResult,
    {
        "gate_result_id": "gate_result_id",
        "gate_name": "gate_name",
        "code_version": "code_version",
        "result": "result",
        "input_scope_hash": "input_scope_hash",
        "idempotency_key": "idempotency_key",
        "output_hash": "output_hash",
    },
    created_at_key="created_at",
    mirrors={
        "gate_name": "gate_name",
        "code_version": "code_version",
        "result": "result",
        "input_scope_hash": "input_scope_hash",
        "idempotency_key": "idempotency_key",
        "output_hash": "output_hash",
    },
)

CRITIC_RUN_CONFIG = _config(
    CriticRunRecord,
    CriticRun,
    {
        "critic_run_id": "critic_run_id",
        "assessment_candidate_id": "assessment_candidate_id",
        "created_by_agent_call_id": "created_by_agent_call_id",
        "critic_revision": "critic_revision",
    },
    mirrors={
        "assessment_candidate_id": "assessment_candidate_id",
        "created_by_agent_call_id": "created_by_agent_call_id",
        "critic_revision": "critic_revision",
    },
)

WORKFLOW_STAGE_CONFIG = _config(
    WorkflowStageRecord,
    WorkflowStage,
    {
        "workflow_stage_id": "workflow_stage_id",
        "stage": "stage",
    },
    assoc=(
        AssocSpec(
            workflow_stage_requirements,
            "workflow_stage_id",
            "workflow_stage_id",
            "due_requirement_ids",
        ),
    ),
    mirrors={"stage": "stage"},
)

CONTEXT_SNAPSHOT_CONFIG = _config(
    ReviewContextSnapshotRecord,
    ReviewContextSnapshot,
    {
        "context_id": "context_id",
        "review_episode_id": "review_episode_id",
    },
    mirrors={"review_episode_id": "review_episode_id"},
)


# ---------------------------------------------------------------------------
# 规则集树：rule_sets/rules/rule_components/evidence_requirements 组合写入
# ---------------------------------------------------------------------------


def save_rule_set(session: Session, rule_set: RuleSet) -> RuleSet:
    """追加写入 RuleSet 及其规则树；新 revision 追加新行，不覆盖历史。"""
    payload_json, payload_sha256 = encode_contract(rule_set)
    created_at = utc_now()
    session.add(
        RuleSetRecord(
            rule_set_id=rule_set.rule_set_id,
            revision=rule_set.revision,
            protocol_version_id=rule_set.protocol_version_id,
            study_phase=rule_set.study_phase.value,
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            created_at=created_at,
        )
    )
    _flush_guarded(session)
    for rule in rule_set.rules:
        rule_payload_json, rule_payload_sha256 = encode_contract(rule)
        session.add(
            RuleRecord(
                rule_id=rule.rule_id,
                rule_set_id=rule_set.rule_set_id,
                rule_set_revision=rule_set.revision,
                official_code=rule.official_code,
                kind=rule.kind.value,
                study_phase=rule.study_phase.value,
                payload_json=rule_payload_json,
                payload_sha256=rule_payload_sha256,
                created_at=created_at,
            )
        )
        _flush_guarded(session)
        for component in rule.components:
            expression_text, expression_sha256 = encode_value(
                component.expression.model_dump(mode="json")
            )
            exception_sha256 = None
            if component.exception_expression is not None:
                _exception_text, exception_sha256 = encode_value(
                    component.exception_expression.model_dump(mode="json")
                )
            component_payload_json, component_payload_sha256 = encode_contract(component)
            session.add(
                RuleComponentRecord(
                    rule_component_id=component.rule_component_id,
                    rule_set_id=rule_set.rule_set_id,
                    rule_set_revision=rule_set.revision,
                    parent_rule_id=component.parent_rule_id,
                    display_code=component.display_code,
                    title=component.title,
                    expression_json=component.expression.model_dump(mode="json"),
                    expression_sha256=expression_sha256,
                    exception_expression_json=(
                        component.exception_expression.model_dump(mode="json")
                        if component.exception_expression is not None
                        else None
                    ),
                    exception_expression_sha256=exception_sha256,
                    payload_json=component_payload_json,
                    payload_sha256=component_payload_sha256,
                    created_at=created_at,
                )
            )
            _flush_guarded(session)
            for requirement in component.evidence_requirements:
                requirement_payload_json, requirement_payload_sha256 = encode_contract(requirement)
                session.add(
                    EvidenceRequirementRecord(
                        requirement_id=requirement.requirement_id,
                        rule_set_id=rule_set.rule_set_id,
                        rule_set_revision=rule_set.revision,
                        rule_component_id=component.rule_component_id,
                        fact_type=requirement.fact_type,
                        due_stage=requirement.due_stage.value,
                        payload_json=requirement_payload_json,
                        payload_sha256=requirement_payload_sha256,
                        created_at=created_at,
                    )
                )
                _flush_guarded(session)
    return rule_set


def get_rule_set(session: Session, rule_set_id: str, revision: int) -> RuleSet:
    record = session.get(RuleSetRecord, (rule_set_id, revision))
    if record is None:
        raise NotFoundError(f"RuleSet {rule_set_id} revision {revision} 不存在")
    contract = decode_contract(RuleSet, record.payload_json, record.payload_sha256)
    payload = json.loads(record.payload_json)
    check_column_mirrors(
        "RuleSet", record, payload, {"protocol_version_id": "protocol_version_id", "study_phase": "study_phase"}
    )
    return contract


def get_rule(
    session: Session, rule_set_id: str, revision: int, rule_id: str
) -> Rule:
    record = session.get(RuleRecord, (rule_set_id, revision, rule_id))
    if record is None:
        raise NotFoundError(f"Rule {rule_id} 不在 RuleSet {rule_set_id} revision {revision}")
    contract = decode_contract(Rule, record.payload_json, record.payload_sha256)
    payload = json.loads(record.payload_json)
    check_column_mirrors(
        "Rule", record, payload, {"official_code": "official_code", "kind": "kind", "study_phase": "study_phase"}
    )
    return contract


def get_rule_component(
    session: Session, rule_set_id: str, revision: int, component_id: str
) -> RuleComponent:
    record = session.get(RuleComponentRecord, (rule_set_id, revision, component_id))
    if record is None:
        raise NotFoundError(
            f"RuleComponent {component_id} 不在 RuleSet {rule_set_id} revision {revision}"
        )
    contract = decode_contract(RuleComponent, record.payload_json, record.payload_sha256)
    # 表达式单独校验：canonical JSON 哈希必须与拆分列一致
    expression_text, expression_sha256 = encode_value(
        contract.expression.model_dump(mode="json")
    )
    if expression_sha256 != record.expression_sha256:
        raise PersistedContractInvalid(
            f"RuleComponent {component_id} 的 expression 哈希与存储列不一致"
        )
    return contract


def get_evidence_requirement(
    session: Session, rule_set_id: str, revision: int, requirement_id: str
) -> EvidenceRequirement:
    record = session.get(EvidenceRequirementRecord, (rule_set_id, revision, requirement_id))
    if record is None:
        raise NotFoundError(
            f"EvidenceRequirement {requirement_id} 不在 RuleSet {rule_set_id} revision {revision}"
        )
    contract = decode_contract(EvidenceRequirement, record.payload_json, record.payload_sha256)
    payload = json.loads(record.payload_json)
    check_column_mirrors(
        "EvidenceRequirement",
        record,
        payload,
        {"rule_component_id": "rule_component_id", "fact_type": "fact_type", "due_stage": "due_stage"},
    )
    return contract


# ---------------------------------------------------------------------------
# 可变根仓储
# ---------------------------------------------------------------------------


def _project_columns(payload: dict[str, Any], scope: dict[str, Any] | None) -> dict[str, Any]:
    columns = {
        "project_id": payload["project_id"],
        "project_code": payload["project_code"],
        "project_name": payload["project_name"],
        "study_phase": payload["study_phase"],
        "protocol_version_id": payload["protocol_version"]["protocol_version_id"],
        "rule_set_id": payload["rule_set_id"],
    }
    if scope and "rule_set_revision" in scope:
        columns["rule_set_revision"] = scope["rule_set_revision"]
    return columns


class ProjectRepository:
    MUTABLE_FIELDS = frozenset(
        {"project_code", "project_name", "study_phase", "protocol_version", "rule_set_id"}
    )

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, project: Project, *, rule_set_revision: int) -> Project:
        payload_json, payload_sha256 = encode_contract(project)
        payload = json.loads(payload_json)
        _check_project_scope(self.session, project, payload, rule_set_revision)
        _insert_revisioned(
            self.session,
            ProjectRecord,
            payload_json,
            payload_sha256,
            _project_columns(payload, {"rule_set_revision": rule_set_revision}),
        )
        return project

    def get(self, project_id: str) -> Project:
        record = _get_required(self.session, ProjectRecord, project_id, "Project")
        contract = decode_contract(Project, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "Project",
            record,
            payload,
            {
                "project_code": "project_code",
                "project_name": "project_name",
                "study_phase": "study_phase",
                "protocol_version_id": "protocol_version.protocol_version_id",
                "rule_set_id": "rule_set_id",
            },
        )
        return contract

    def update(
        self,
        project_id: str,
        expected_revision: int,
        changes: dict[str, Any],
        *,
        rule_set_revision: int | None = None,
    ) -> Project:
        scope = (
            {"rule_set_revision": rule_set_revision} if rule_set_revision is not None else None
        )
        new_contract, record = apply_revisioned_update(
            self.session,
            ProjectRecord,
            Project,
            project_id,
            expected_revision,
            changes,
            column_builder=_project_columns,
            mutable_fields=set(self.MUTABLE_FIELDS),
            entity_type="Project",
            scope=scope,
        )
        rule_set = self.session.get(
            RuleSetRecord, (record.rule_set_id, record.rule_set_revision)
        )
        if rule_set is None or rule_set.protocol_version_id != record.protocol_version_id:
            raise ScopeViolationError(
                f"Project {project_id} 更新后的 rule_set 与 protocol_version 不一致"
            )
        return new_contract

    def list(self) -> list[Project]:
        rows = self.session.execute(
            select(ProjectRecord).order_by(ProjectRecord.project_id)
        ).scalars().all()
        contracts = [
            decode_contract(Project, row.payload_json, row.payload_sha256) for row in rows
        ]
        for row, payload in (
            (row, json.loads(row.payload_json)) for row in rows
        ):
            check_column_mirrors("Project", row, payload, {"rule_set_id": "rule_set_id"})
        return contracts


def _subject_columns(payload: dict[str, Any], scope: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "subject_id": payload["subject_id"],
        "subject_code": payload["subject_code"],
        "project_id": payload["project_id"],
        "center_code": payload.get("center_code"),
        "center_name": payload.get("center_name"),
        "sex": payload.get("sex"),
        "age_years": payload.get("age_years"),
    }


class SubjectRepository:
    MUTABLE_FIELDS = frozenset(
        {"subject_code", "center_code", "center_name", "sex", "age_years"}
    )

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, subject: Subject) -> Subject:
        _get_required(self.session, ProjectRecord, subject.project_id, "Project")
        payload_json, payload_sha256 = encode_contract(subject)
        _insert_revisioned(
            self.session,
            SubjectRecord,
            payload_json,
            payload_sha256,
            _subject_columns(json.loads(payload_json), None),
        )
        return subject

    def get(self, subject_id: str) -> Subject:
        record = _get_required(self.session, SubjectRecord, subject_id, "Subject")
        contract = decode_contract(Subject, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "Subject",
            record,
            payload,
            {
                "subject_code": "subject_code",
                "project_id": "project_id",
                "center_code": "center_code",
                "center_name": "center_name",
                "sex": "sex",
                "age_years": "age_years",
            },
        )
        return contract

    def update(
        self, subject_id: str, expected_revision: int, changes: dict[str, Any]
    ) -> Subject:
        new_contract, _record = apply_revisioned_update(
            self.session,
            SubjectRecord,
            Subject,
            subject_id,
            expected_revision,
            changes,
            column_builder=_subject_columns,
            mutable_fields=set(self.MUTABLE_FIELDS),
            entity_type="Subject",
        )
        return new_contract

    def list_by_project(self, project_id: str) -> list[Subject]:
        rows = self.session.execute(
            select(SubjectRecord)
            .where(SubjectRecord.project_id == project_id)
            .order_by(SubjectRecord.subject_id)
        ).scalars().all()
        return [decode_contract(Subject, row.payload_json, row.payload_sha256) for row in rows]


def _episode_columns(payload: dict[str, Any], scope: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "review_episode_id": payload["review_episode_id"],
        "subject_id": payload["subject_id"],
        "project_id": payload["project_id"],
        "rule_set_id": payload["rule_set_id"],
        "rule_set_revision": payload["rule_set_revision"],
        "study_phase": payload["study_phase"],
        "stage": payload["stage"],
        "protocol_version_id": payload["protocol_version_id"],
        "evidence_snapshot_id": payload["evidence_snapshot_id"],
        "anchor_dates_json": payload["anchor_dates"],
        "due_at": (
            parse_datetime_column(payload["due_at"]) if payload.get("due_at") else None
        ),
    }


class EpisodeRepository:
    MUTABLE_FIELDS = frozenset({"stage", "due_at", "evidence_snapshot_id", "anchor_dates"})

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, episode: ReviewEpisode) -> ReviewEpisode:
        _check_episode_scope(self.session, episode)
        payload_json, payload_sha256 = encode_contract(episode)
        _insert_revisioned(
            self.session,
            ReviewEpisodeRecord,
            payload_json,
            payload_sha256,
            _episode_columns(json.loads(payload_json), None),
        )
        return episode

    def get(self, review_episode_id: str) -> ReviewEpisode:
        record = _get_required(
            self.session, ReviewEpisodeRecord, review_episode_id, "ReviewEpisode"
        )
        contract = decode_contract(ReviewEpisode, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "ReviewEpisode",
            record,
            payload,
            {
                "subject_id": "subject_id",
                "project_id": "project_id",
                "rule_set_id": "rule_set_id",
                "rule_set_revision": "rule_set_revision",
                "study_phase": "study_phase",
                "stage": "stage",
                "protocol_version_id": "protocol_version_id",
                "evidence_snapshot_id": "evidence_snapshot_id",
                "anchor_dates_json": "anchor_dates",
            },
        )
        return contract

    def update(
        self, review_episode_id: str, expected_revision: int, changes: dict[str, Any]
    ) -> ReviewEpisode:
        new_contract, _record = apply_revisioned_update(
            self.session,
            ReviewEpisodeRecord,
            ReviewEpisode,
            review_episode_id,
            expected_revision,
            changes,
            column_builder=_episode_columns,
            mutable_fields=set(self.MUTABLE_FIELDS),
            entity_type="ReviewEpisode",
        )
        return new_contract

    def list_by_subject(self, subject_id: str) -> list[ReviewEpisode]:
        rows = self.session.execute(
            select(ReviewEpisodeRecord)
            .where(ReviewEpisodeRecord.subject_id == subject_id)
            .order_by(ReviewEpisodeRecord.review_episode_id)
        ).scalars().all()
        return [
            decode_contract(ReviewEpisode, row.payload_json, row.payload_sha256) for row in rows
        ]

    def list_by_project(self, project_id: str) -> list[ReviewEpisode]:
        rows = self.session.execute(
            select(ReviewEpisodeRecord)
            .where(ReviewEpisodeRecord.project_id == project_id)
            .order_by(ReviewEpisodeRecord.review_episode_id)
        ).scalars().all()
        return [
            decode_contract(ReviewEpisode, row.payload_json, row.payload_sha256) for row in rows
        ]


def _expectation_columns(
    payload: dict[str, Any], scope: dict[str, Any] | None
) -> dict[str, Any]:
    columns = {
        "expectation_id": payload["expectation_id"],
        "requirement_id": payload["requirement_id"],
        "review_episode_id": payload["review_episode_id"],
        "status": payload["status"],
        "gap_type": payload.get("gap_type"),
    }
    if scope:
        columns["rule_set_id"] = scope["rule_set_id"]
        columns["rule_set_revision"] = scope["rule_set_revision"]
    return columns


def _replace_assoc(
    session: Session, table: Any, owner_column: str, owner_value: str, ordered_refs: list[str]
) -> None:
    session.execute(delete(table).where(table.c[owner_column] == owner_value))
    if not ordered_refs:
        return
    ref_column = next(
        name for name in table.c.keys() if name not in {owner_column, "position"}
    )
    session.execute(
        insert(table),
        [
            {owner_column: owner_value, ref_column: ref, "position": position}
            for position, ref in enumerate(ordered_refs)
        ],
    )


class EvidenceExpectationRepository:
    MUTABLE_FIELDS = frozenset({"status", "gap_type", "evidence_span_ids"})

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, expectation: EvidenceExpectation) -> EvidenceExpectation:
        episode = _get_required(
            self.session, ReviewEpisodeRecord, expectation.review_episode_id, "ReviewEpisode"
        )
        scope = {
            "rule_set_id": episode.rule_set_id,
            "rule_set_revision": episode.rule_set_revision,
        }
        payload_json, payload_sha256 = encode_contract(expectation)
        payload = json.loads(payload_json)
        _check_expectation_scope(self.session, expectation, payload)
        _insert_revisioned(
            self.session,
            EvidenceExpectationRecord,
            payload_json,
            payload_sha256,
            _expectation_columns(payload, scope),
        )
        _replace_assoc(
            self.session,
            evidence_expectation_spans,
            "expectation_id",
            expectation.expectation_id,
            list(expectation.evidence_span_ids),
        )
        _flush_guarded(self.session)
        return expectation

    def get(self, expectation_id: str) -> EvidenceExpectation:
        record = _get_required(
            self.session, EvidenceExpectationRecord, expectation_id, "EvidenceExpectation"
        )
        contract = decode_contract(EvidenceExpectation, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "EvidenceExpectation",
            record,
            payload,
            {
                "requirement_id": "requirement_id",
                "review_episode_id": "review_episode_id",
                "status": "status",
                "gap_type": "gap_type",
            },
        )
        return contract

    def update(
        self, expectation_id: str, expected_revision: int, changes: dict[str, Any]
    ) -> EvidenceExpectation:
        new_contract, record = apply_revisioned_update(
            self.session,
            EvidenceExpectationRecord,
            EvidenceExpectation,
            expectation_id,
            expected_revision,
            changes,
            column_builder=_expectation_columns,
            mutable_fields=set(self.MUTABLE_FIELDS),
            entity_type="EvidenceExpectation",
        )
        _replace_assoc(
            self.session,
            evidence_expectation_spans,
            "expectation_id",
            expectation_id,
            list(new_contract.evidence_span_ids),
        )
        _flush_guarded(self.session)
        return new_contract

    def list_by_episode(self, review_episode_id: str) -> list[EvidenceExpectation]:
        rows = self.session.execute(
            select(EvidenceExpectationRecord)
            .where(EvidenceExpectationRecord.review_episode_id == review_episode_id)
            .order_by(EvidenceExpectationRecord.expectation_id)
        ).scalars().all()
        return [
            decode_contract(EvidenceExpectation, row.payload_json, row.payload_sha256)
            for row in rows
        ]


def _action_columns(payload: dict[str, Any], scope: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "action_id": payload["action_id"],
        "project_id": payload["project_id"],
        "protocol_version_id": payload["protocol_version_id"],
        "subject_id": payload["subject_id"],
        "rule_set_id": payload["rule_set_id"],
        "rule_set_revision": payload["rule_set_revision"],
        "rule_component_id": payload["rule_component_id"],
        "review_episode_id": payload["review_episode_id"],
        "evidence_snapshot_id": payload["evidence_snapshot_id"],
        "review_run_id": payload["review_run_id"],
        "assessment_id": payload["assessment_id"],
        "gap_type": payload["gap_type"],
        "target_party": payload["target_party"],
        "requested_action": payload["requested_action"],
        "acceptable_evidence": payload["acceptable_evidence"],
        "due_stage": payload["due_stage"],
        "blocking_level": payload["blocking_level"],
        "trigger_evidence_span_id": payload.get("trigger_evidence_span_id"),
        "state": payload["state"],
        "recompute_scope_json": payload["recompute_scope"],
        "gate_result_id": payload["gate_result_id"],
        "publication_fingerprint": payload["publication_fingerprint"],
    }


def _insert_transitions(
    session: Session, action_id: str, transitions: list[ActionTransition]
) -> None:
    encoded = []
    for transition in transitions:
        payload_json, payload_sha256 = encode_contract(transition)
        payload = json.loads(payload_json)
        session.add(
            ActionTransitionRecord(
                transition_id=payload["transition_id"],
                action_id=action_id,
                from_state=payload["from_state"],
                to_state=payload["to_state"],
                occurred_at=parse_datetime_column(payload["occurred_at"]),
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=utc_now(),
            )
        )
        encoded.append((payload, payload_json))
    _flush_guarded(session)
    for payload, _payload_json in encoded:
        spans = payload.get("evidence_span_ids") or []
        session.execute(
            insert(action_transition_spans),
            [
                {
                    "transition_id": payload["transition_id"],
                    "evidence_span_id": span_id,
                    "position": position,
                }
                for position, span_id in enumerate(spans)
            ],
        )
    _flush_guarded(session)


class ActionRequestRepository:
    MUTABLE_FIELDS = frozenset(
        {
            "state",
            "recompute_scope",
            "requested_action",
            "acceptable_evidence",
            "due_stage",
            "blocking_level",
            "trigger_evidence_span_id",
        }
    )

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, action: ActionRequest) -> ActionRequest:
        _check_action_scope(self.session, action)
        payload_json, payload_sha256 = encode_contract(action)
        payload = json.loads(payload_json)
        _insert_revisioned(
            self.session,
            ActionRequestRecord,
            payload_json,
            payload_sha256,
            _action_columns(payload, None),
        )
        _insert_transitions(self.session, action.action_id, list(action.transitions))
        _flush_guarded(self.session)
        return action

    def get(self, action_id: str) -> ActionRequest:
        record = _get_required(self.session, ActionRequestRecord, action_id, "ActionRequest")
        contract = decode_contract(ActionRequest, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "ActionRequest",
            record,
            payload,
            {
                "project_id": "project_id",
                "subject_id": "subject_id",
                "rule_set_id": "rule_set_id",
                "rule_set_revision": "rule_set_revision",
                "rule_component_id": "rule_component_id",
                "review_episode_id": "review_episode_id",
                "evidence_snapshot_id": "evidence_snapshot_id",
                "review_run_id": "review_run_id",
                "assessment_id": "assessment_id",
                "gap_type": "gap_type",
                "due_stage": "due_stage",
                "blocking_level": "blocking_level",
                "trigger_evidence_span_id": "trigger_evidence_span_id",
                "state": "state",
                "recompute_scope_json": "recompute_scope",
                "gate_result_id": "gate_result_id",
                "publication_fingerprint": "publication_fingerprint",
            },
        )
        # 转换历史不得丢失：表内转换与 payload 转换必须一致
        stored_ids = set(
            self.session.execute(
                select(ActionTransitionRecord.transition_id).where(
                    ActionTransitionRecord.action_id == action_id
                )
            ).scalars()
        )
        payload_ids = {transition.transition_id for transition in contract.transitions}
        if stored_ids != payload_ids:
            raise PersistedContractInvalid(
                f"ActionRequest {action_id} 的转换历史与 payload 不一致，拒绝还原合同"
            )
        return contract

    def replace(self, action: ActionRequest, expected_revision: int) -> ActionRequest:
        """整合同替换（携带 expected revision）；新增转换追加写入，历史保留。"""
        _check_action_scope(self.session, action)
        existing_ids = set(
            self.session.execute(
                select(ActionTransitionRecord.transition_id).where(
                    ActionTransitionRecord.action_id == action.action_id
                )
            ).scalars()
        )
        new_contract, _record = apply_revisioned_update(
            self.session,
            ActionRequestRecord,
            ActionRequest,
            action.action_id,
            expected_revision,
            action.model_dump(mode="json"),
            column_builder=_action_columns,
            mutable_fields=set(self.MUTABLE_FIELDS),
            entity_type="ActionRequest",
        )
        new_transitions = [
            transition
            for transition in new_contract.transitions
            if transition.transition_id not in existing_ids
        ]
        _insert_transitions(self.session, action.action_id, new_transitions)
        _flush_guarded(self.session)
        return new_contract


# ---------------------------------------------------------------------------
# 投影
# ---------------------------------------------------------------------------


def save_episode_rollup(session: Session, rollup: EpisodeRollup) -> None:
    """追加写投影；同一 (episode, fingerprint) 的重建幂等跳过。"""
    existing = session.execute(
        select(EpisodeRollupRecord.id).where(
            EpisodeRollupRecord.review_episode_id == rollup.review_episode_id,
            EpisodeRollupRecord.publication_fingerprint == rollup.publication_fingerprint,
        )
    ).scalars().first()
    if existing is not None:
        return
    payload_json, payload_sha256 = encode_contract(rollup)
    payload = json.loads(payload_json)
    session.add(
        EpisodeRollupRecord(
            review_episode_id=payload["review_episode_id"],
            main_status=payload["main_status"],
            gate_result_id=payload["gate_result_id"],
            publication_fingerprint=payload["publication_fingerprint"],
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            created_at=utc_now(),
        )
    )
    _flush_guarded(session)


def get_latest_rollup(session: Session, review_episode_id: str) -> EpisodeRollup | None:
    record = session.execute(
        select(EpisodeRollupRecord)
        .where(EpisodeRollupRecord.review_episode_id == review_episode_id)
        .order_by(EpisodeRollupRecord.id.desc())
        .limit(1)
    ).scalars().first()
    if record is None:
        return None
    contract = decode_contract(EpisodeRollup, record.payload_json, record.payload_sha256)
    payload = json.loads(record.payload_json)
    check_column_mirrors(
        "EpisodeRollup",
        record,
        payload,
        {
            "review_episode_id": "review_episode_id",
            "main_status": "main_status",
            "gate_result_id": "gate_result_id",
            "publication_fingerprint": "publication_fingerprint",
        },
    )
    return contract


# ---------------------------------------------------------------------------
# Job 存储原语（状态机/租约/恢复由 workflow 层实现）
# ---------------------------------------------------------------------------


def _job_payload(payload: dict[str, Any] | None) -> tuple[str, str]:
    text, sha256 = encode_value(payload or {})
    return text, sha256


class JobRepository:
    """Job/Step/Checkpoint/Event 的存储原语；单调事件序号在写入事务内分配。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_job(
        self,
        *,
        job_id: str,
        job_type: str,
        state: str = "queued",
        payload: dict[str, Any] | None = None,
        progress_total: int = 0,
    ) -> JobRecord:
        payload_json, payload_sha256 = _job_payload(payload)
        row = JobRecord(
            job_id=job_id,
            job_type=job_type,
            state=state,
            lease_generation=0,
            cancel_requested=False,
            progress_completed=0,
            progress_total=progress_total,
            last_event_seq=0,
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            revision=1,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.session.add(row)
        _flush_guarded(self.session)
        return row

    def get_job(self, job_id: str) -> JobRecord:
        return _get_required(self.session, JobRecord, job_id, "Job")

    def create_step(
        self,
        *,
        step_id: str,
        job_id: str,
        name: str,
        state: str = "queued",
        attempt: int = 0,
        max_attempts: int = 1,
        retryable: bool = False,
        depends_on: list[str] | tuple[str, ...] = (),
    ) -> JobStepRecord:
        _get_required(self.session, JobRecord, job_id, "Job")
        payload_json, payload_sha256 = _job_payload(None)
        row = JobStepRecord(
            step_id=step_id,
            job_id=job_id,
            name=name,
            state=state,
            attempt=attempt,
            max_attempts=max_attempts,
            retryable=retryable,
            progress_completed=0,
            progress_total=0,
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            revision=1,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.session.add(row)
        _flush_guarded(self.session)
        self.add_step_dependencies(
            job_id=job_id,
            step_id=step_id,
            depends_on=depends_on,
        )
        return row

    def add_step_dependencies(
        self,
        *,
        job_id: str,
        step_id: str,
        depends_on: list[str] | tuple[str, ...],
    ) -> None:
        """在同一任务范围内添加有序依赖；可在所有步骤落库后调用。"""
        for position, depends_on_step in enumerate(depends_on):
            self.session.execute(
                insert(job_step_dependencies),
                [
                    {
                        "job_id": job_id,
                        "step_id": step_id,
                        "depends_on_step_id": depends_on_step,
                        "position": position,
                    }
                ],
            )
        _flush_guarded(self.session)

    def get_step(self, job_id: str, step_id: str) -> JobStepRecord:
        return _get_required(
            self.session,
            JobStepRecord,
            {"job_id": job_id, "step_id": step_id},
            "JobStep",
        )

    def create_checkpoint(
        self,
        *,
        checkpoint_id: str,
        job_id: str,
        step_id: str,
        payload: dict[str, Any],
    ) -> JobCheckpointRecord:
        _get_required(self.session, JobRecord, job_id, "Job")
        _get_required(
            self.session,
            JobStepRecord,
            {"job_id": job_id, "step_id": step_id},
            "JobStep",
        )
        payload_json, payload_sha256 = encode_value(payload)
        row = JobCheckpointRecord(
            checkpoint_id=checkpoint_id,
            job_id=job_id,
            step_id=step_id,
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            created_at=utc_now(),
        )
        self.session.add(row)
        _flush_guarded(self.session)
        return row

    def append_event(self, event: JobEvent) -> int:
        """写入 JobEvent 并返回分配的 ``(job_id, seq)`` 序号；同事务更新 job 序号水位。"""
        _get_required(self.session, JobRecord, event.job_id, "Job")
        payload_json, payload_sha256 = encode_contract(event)
        payload = json.loads(payload_json)
        # SQLite 同一时刻只有一个写者。用 jobs 水位的单条 UPDATE 分配序号，
        # 让并发会话在数据库写锁处排队；“查 max + 1”会让两个会话读到
        # 相同旧值，导致唯一约束冲突或快照升级失败。
        seq = self.session.execute(
            update(JobRecord)
            .where(JobRecord.job_id == event.job_id)
            .values(last_event_seq=JobRecord.last_event_seq + 1)
            .returning(JobRecord.last_event_seq)
            .execution_options(synchronize_session=False)
        ).scalar_one()
        self.session.add(
            JobEventRecord(
                job_id=payload["job_id"],
                event_seq=seq,
                event_type=payload["event_type"],
                step_id=payload.get("step_id"),
                occurred_at=parse_datetime_column(payload["occurred_at"]),
                attempt=payload["attempt"],
                checkpoint_id=payload.get("checkpoint_id"),
                retryable=payload["retryable"],
                progress_completed=payload["progress_completed"],
                progress_total=payload["progress_total"],
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=utc_now(),
            )
        )
        _flush_guarded(self.session)
        return int(seq)

    def list_events(self, job_id: str, after_seq: int = 0) -> list[JobEvent]:
        rows = self.session.execute(
            select(JobEventRecord)
            .where(JobEventRecord.job_id == job_id, JobEventRecord.event_seq > after_seq)
            .order_by(JobEventRecord.event_seq)
        ).scalars().all()
        return [
            decode_contract(JobEvent, row.payload_json, row.payload_sha256) for row in rows
        ]

    def list_event_rows(self, job_id: str, after_seq: int = 0) -> list[tuple[int, JobEvent]]:
        """返回 ``(event_seq, JobEvent)`` 有序行；seq 供 SSE ``after_seq`` 续订。"""
        rows = self.session.execute(
            select(JobEventRecord)
            .where(JobEventRecord.job_id == job_id, JobEventRecord.event_seq > after_seq)
            .order_by(JobEventRecord.event_seq)
        ).scalars().all()
        return [
            (row.event_seq, decode_contract(JobEvent, row.payload_json, row.payload_sha256))
            for row in rows
        ]

    def seed_fixture_events(self, events: list[JobEvent]) -> None:
        """为 UAT fixture 的 JobEvent 建立最小 Job/Step/Checkpoint 行后写入事件。"""
        if not events:
            return
        for job_id in dict.fromkeys(event.job_id for event in events):
            self.create_job(
                job_id=job_id,
                job_type="fixture_uat",
                state="completed",
                payload={"job_id": job_id},
            )
        for step_id, job_id in dict.fromkeys(
            (event.step_id, event.job_id)
            for event in events
            if event.step_id is not None
        ):
            self.create_step(
                step_id=step_id,
                job_id=job_id,
                name=step_id,
                state="completed",
                attempt=1,
                max_attempts=1,
            )
        for checkpoint_id, job_id, step_id in dict.fromkeys(
            (event.checkpoint_id, event.job_id, event.step_id)
            for event in events
            if event.checkpoint_id is not None
        ):
            self.create_checkpoint(
                checkpoint_id=checkpoint_id,
                job_id=job_id,
                step_id=step_id,
                payload={"checkpoint_id": checkpoint_id, "step_id": step_id},
            )
        for event in events:
            self.append_event(event)


# ---------------------------------------------------------------------------
# Fixture 组合播种
# ---------------------------------------------------------------------------


def save_protocol_authority_chain(session: Session, fixture: FixtureV1) -> None:
    """写入协议权威链：authority record -> command -> confirmation -> manifest ->
    source records -> workflow stages。"""
    authority = fixture.protocol_authority_record
    AppendRepository(session, AUTHORITY_RECORD_CONFIG).save(authority)
    AppendRepository(session, COMMAND_EVENT_CONFIG).save(fixture.protocol_authority_command)
    AppendRepository(session, AUTHORITY_CONFIRMATION_CONFIG).save(
        fixture.protocol_authority_confirmation
    )
    AppendRepository(session, INTEGRITY_MANIFEST_CONFIG).save(
        fixture.protocol_integrity_manifest
    )
    for record in fixture.protocol_source_records:
        AppendRepository(session, SOURCE_RECORD_CONFIG).save(record)
    for stage in fixture.workflow_stages:
        AppendRepository(session, WORKFLOW_STAGE_CONFIG).save(
            stage, scope={"protocol_version_id": authority.protocol_version_id}
        )


def persist_fixture(session: Session, fixture: FixtureV1) -> None:
    """按外键依赖顺序播种一个完整 FixtureV1（合同内容已经过 Gate 校验）。"""
    AppendRepository(session, PROTOCOL_DOC_CONFIG).save(fixture.project.protocol_version)
    save_protocol_authority_chain(session, fixture)
    save_rule_set(session, fixture.rule_set)
    ProjectRepository(session).save(fixture.project, rule_set_revision=fixture.rule_set.revision)
    SubjectRepository(session).save(fixture.subject)
    EpisodeRepository(session).save(fixture.review_episode)
    source_document_repo = AppendRepository(session, SOURCE_DOCUMENT_CONFIG)
    for document in fixture.source_documents:
        source_document_repo.save(document)
    AppendRepository(session, SNAPSHOT_CONFIG).save(fixture.evidence_snapshot)
    span_repo = AppendRepository(session, EVIDENCE_SPAN_CONFIG)
    for span in fixture.evidence_spans:
        span_repo.save(span)
    group_repo = AppendRepository(session, CONFLICT_GROUP_CONFIG)
    for group in fixture.conflict_groups:
        group_repo.save(group)
    fact_repo = AppendRepository(session, CLINICAL_FACT_CONFIG)
    for fact in fixture.facts:
        fact_repo.save(fact)
    expectation_repo = EvidenceExpectationRepository(session)
    for expectation in fixture.evidence_expectations:
        expectation_repo.save(expectation)
    prompt_repo = AppendRepository(session, PROMPT_VERSION_CONFIG)
    for prompt_version in fixture.prompt_versions:
        prompt_repo.save(prompt_version)
    model_repo = AppendRepository(session, MODEL_CONFIG_CONFIG)
    for model_config in fixture.model_configs:
        model_repo.save(model_config)
    gate_repo = AppendRepository(session, GATE_RESULT_CONFIG)
    for gate in fixture.gate_results:
        gate_repo.save(gate)
    run_repo = AppendRepository(session, REVIEW_RUN_CONFIG)
    for run in fixture.review_runs:
        run_repo.save(run)
    call_repo = AppendRepository(session, AGENT_CALL_CONFIG)
    for call in fixture.agent_calls:
        call_repo.save(call)
    candidate_repo = AppendRepository(session, NORMALIZATION_CANDIDATE_CONFIG)
    for candidate in fixture.evidence_normalization_candidates:
        candidate_repo.save(candidate)
    AppendRepository(session, PATIENT_PROFILE_CONFIG).save(fixture.patient_profile)
    assessment_candidate_repo = AppendRepository(session, ASSESSMENT_CANDIDATE_CONFIG)
    for candidate in fixture.assessment_candidates:
        assessment_candidate_repo.save(candidate)
    assessment_repo = AppendRepository(session, FINAL_ASSESSMENT_CONFIG)
    for assessment in fixture.final_assessments:
        assessment_repo.save(assessment)
    action_repo = ActionRequestRepository(session)
    for action in fixture.actions:
        action_repo.save(action)
    diff_repo = AppendRepository(session, REVIEW_RUN_DIFF_CONFIG)
    for diff in fixture.review_run_diffs:
        diff_repo.save(diff)
    save_episode_rollup(session, fixture.episode_rollup)
    JobRepository(session).seed_fixture_events(list(fixture.job_events))
