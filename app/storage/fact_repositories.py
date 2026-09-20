"""Phase 5 v2 临床事实仓储。

在 ``facts_models`` ORM 之上提供追加写/读取的确定性仓储，并在持久化边界强制权威
元组与定位闭包门禁（调用 :class:`~app.storage.fact_authority.FactAuthorityValidator`）：

- ``FactNormalizationRunRepository`` / ``FactNormalizationCallRepository`` /
  ``FactGateResultRepository``   运行/调用/门禁记录（运行幂等键复用）；
- ``ClinicalFactV2Repository``   发布临床事实 + 定位闭包（含断言依据定位）；
- ``ClinicalEventV2Repository``  发布事件：事实/定位引用必须同一权威元组且事件定位
  属于其引用事实的定位闭包（P5-R06；事件借用同节点其他事实证据时拒绝）；
- ``MedicationExposureV2Repository``  发布用药/治疗暴露（同事件约束）；
- ``ClinicalConflictGroupV2Repository`` 未解决冲突组（同类型成员不少于两个、共享
  权威元组、定位属于成员实体闭包，不自动择优）。

所有写入先 ``validate`` 权威元组、再 ``validate_locators`` 定位闭包，然后追加写
canonical JSON + SHA-256 与规范化镜像列；读取时用 :func:`decode_contract` 还原并经
镜像交叉核对，任何不一致抛 :class:`PersistedContractInvalid`，绝不返回空对象。
旧 ``clinical_facts / evidence_expectations / patient_profiles`` 占位表保持只读，
本模块不读取、不写入 legacy 表。

``(stable_identity, revision)`` 唯一且只追加：同身份多来源合并为一条事实；人工修订/
增量重算追加更高 revision（必须为链头 +1），绝不覆盖旧行。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.facts import (
    ClinicalConflictGroupV2,
    ClinicalEventCandidateV2,
    ClinicalEventV2,
    ClinicalFactCandidateV2,
    ClinicalFactV2,
    FactAuthority,
    FactGateResult,
    FactNormalizationCall,
    FactNormalizationRun,
    MedicationExposureCandidateV2,
    MedicationExposureV2,
    PartialDateRange,
)
from app.domain.contracts.evidence_normalizer import (
    PersistedEvidenceNormalizerUnresolvedItem,
)
from app.domain.contracts.enums import (
    FactGate,
    FactNormalizationRunStatus,
    GateOutcome,
    SourceStrength,
)
from app.storage.codecs import (
    PersistedContractInvalid,
    check_column_mirrors,
    decode_contract,
    encode_contract,
    mirror_values_equal,
    parse_datetime_column,
    to_utc_naive,
)
from app.storage.fact_authority import (
    FactAuthorityValidator,
    FactLocatorReferenceError,
)
from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
from app.storage.facts_models import (
    ClinicalConflictEventMemberV2Record,
    ClinicalConflictExposureMemberV2Record,
    ClinicalConflictGroupV2Record,
    ClinicalConflictMemberV2Record,
    ClinicalEventV2Record,
    ClinicalFactV2Record,
    EventFactLinkRecord,
    ExposureFactLinkRecord,
    FactEvidenceLocatorLinkRecord,
    FactGateResultRecord,
    FactNormalizationCandidateRecord,
    FactNormalizationCallRecord,
    FactNormalizationRunRecord,
    FactNormalizationUnresolvedItemRecord,
    MedicationExposureV2Record,
)
from app.storage.repositories import (
    RepositoryError,
    _flush_guarded,
    _get_required,
)

__all__ = [
    "ClinicalConflictGroupV2Repository",
    "ClinicalEventV2Repository",
    "ClinicalFactV2Repository",
    "FactCrossEntityError",
    "FactGateResultRepository",
    "FactNormalizationCandidateRepository",
    "FactNormalizationCallRepository",
    "FactNormalizationRunRepository",
    "FactNormalizationUnresolvedItemRepository",
    "FactRevisionChainError",
    "MedicationExposureV2Repository",
    "Phase5RepositoryError",
    "authority_column_filters",
    "prefetch_locator_link_ids",
]


class Phase5RepositoryError(RepositoryError):
    """Phase 5 仓储领域错误基类。"""


class FactCrossEntityError(Phase5RepositoryError):
    """事件/暴露/冲突引用的事实或定位不属于同一审核节点与处理修订。"""


class FactRevisionChainError(Phase5RepositoryError):
    """稳定身份 revision 链只允许追加链头 +1，回退/跳号一律拒绝。"""


def _authority_columns(authority: FactAuthority) -> dict[str, Any]:
    """权威元组 -> 规范化列（发布实体/运行表共用）。"""
    return {
        "project_id": authority.project_id,
        "subject_id": authority.subject_id,
        "review_episode_id": authority.review_episode_id,
        "episode_revision": authority.episode_revision,
        "protocol_version_id": authority.protocol_version_id,
        "rule_set_id": authority.rule_set_id,
        "rule_set_revision": authority.rule_set_revision,
        "evidence_snapshot_v2_id": authority.evidence_snapshot_v2_id,
        "complete_processing_revision_id": authority.complete_processing_revision_id,
    }


def authority_column_filters(model: Any, authority: FactAuthority) -> tuple[Any, ...]:
    """用规范化权威列在 SQL 中限定冻结权威，避免解码库内无关行。"""
    return (
        model.project_id == authority.project_id,
        model.subject_id == authority.subject_id,
        model.review_episode_id == authority.review_episode_id,
        model.episode_revision == authority.episode_revision,
        model.protocol_version_id == authority.protocol_version_id,
        model.rule_set_id == authority.rule_set_id,
        model.rule_set_revision == authority.rule_set_revision,
        model.evidence_snapshot_v2_id == authority.evidence_snapshot_v2_id,
        model.complete_processing_revision_id == authority.complete_processing_revision_id,
    )


def prefetch_locator_link_ids(
    session: Session, entity_kind: str, entity_ids: Sequence[str]
) -> dict[str, list[str]]:
    """一次装载选定实体的定位链接，按 position 分组。缺行视为空列表。"""
    unique_ids = list(dict.fromkeys(entity_ids))
    grouped = {entity_id: [] for entity_id in unique_ids}
    if not unique_ids:
        return grouped
    rows = session.execute(
        select(FactEvidenceLocatorLinkRecord)
        .where(
            FactEvidenceLocatorLinkRecord.entity_kind == entity_kind,
            FactEvidenceLocatorLinkRecord.entity_id.in_(unique_ids),
        )
        .order_by(
            FactEvidenceLocatorLinkRecord.entity_id,
            FactEvidenceLocatorLinkRecord.position,
        )
    ).scalars().all()
    for row in rows:
        grouped[row.entity_id].append(row.locator_id)
    return grouped


def _prefetch_event_fact_ids(
    session: Session, event_ids: Sequence[str]
) -> dict[str, list[str]]:
    grouped = {event_id: [] for event_id in event_ids}
    if not event_ids:
        return grouped
    rows = session.execute(
        select(EventFactLinkRecord)
        .where(EventFactLinkRecord.event_id.in_(list(event_ids)))
        .order_by(EventFactLinkRecord.event_id, EventFactLinkRecord.position)
    ).scalars().all()
    for row in rows:
        grouped[row.event_id].append(row.fact_id)
    return grouped


def _prefetch_exposure_fact_ids(
    session: Session, exposure_ids: Sequence[str]
) -> dict[str, list[str]]:
    grouped = {exposure_id: [] for exposure_id in exposure_ids}
    if not exposure_ids:
        return grouped
    rows = session.execute(
        select(ExposureFactLinkRecord)
        .where(ExposureFactLinkRecord.exposure_id.in_(list(exposure_ids)))
        .order_by(ExposureFactLinkRecord.exposure_id, ExposureFactLinkRecord.position)
    ).scalars().all()
    for row in rows:
        grouped[row.exposure_id].append(row.fact_id)
    return grouped


def _prefetch_conflict_member_ids(
    session: Session,
    record_cls: Any,
    child_attr: str,
    group_ids: Sequence[str],
) -> dict[str, list[str]]:
    grouped = {group_id: [] for group_id in group_ids}
    if not group_ids:
        return grouped
    rows = session.execute(
        select(record_cls)
        .where(record_cls.conflict_group_id.in_(list(group_ids)))
        .order_by(record_cls.conflict_group_id, record_cls.position)
    ).scalars().all()
    for row in rows:
        grouped[row.conflict_group_id].append(getattr(row, child_attr))
    return grouped


def _date_range_columns(dr: PartialDateRange | None) -> dict[str, Any]:
    if dr is None:
        return {
            "date_precision": None,
            "date_lower_bound": None,
            "date_upper_bound": None,
            "date_source_text": None,
        }
    return {
        "date_precision": dr.precision.value,
        "date_lower_bound": dr.lower_bound,
        "date_upper_bound": dr.upper_bound,
        "date_source_text": dr.source_text,
    }


def _date_range_semantics(dr: PartialDateRange | None) -> tuple[Any, ...] | None:
    if dr is None:
        return None
    return (dr.precision, dr.lower_bound, dr.upper_bound)


def _payload_path_opt(payload: dict, path: str) -> Any:
    """容错取 payload 点路径；父节点缺失/为 None 时返回 None（用于可空嵌套镜像）。"""
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or current.get(part) is None:
            return None
        current = current[part]
    return current


def _check_tolerant_mirrors(
    entity_name: str, record: Any, payload: dict, mirrors: dict[str, str]
) -> None:
    """镜像交叉核对（容忍可空嵌套：payload 路径缺失/为 None 时要求列也为 None）。"""
    for column_attr, payload_path in mirrors.items():
        column_value = getattr(record, column_attr)
        payload_value = _payload_path_opt(payload, payload_path)
        if isinstance(column_value, datetime) and isinstance(payload_value, str):
            try:
                parsed_payload = parse_datetime_column(payload_value)
            except ValueError:
                parsed_payload = payload_value
            equal = to_utc_naive(column_value) == parsed_payload
        else:
            equal = mirror_values_equal(column_value, payload_value)
        if not equal:
            raise PersistedContractInvalid(
                f"{entity_name} 列 {column_attr} 与已验证 payload 不一致，拒绝还原合同"
            )


# ---------------------------------------------------------------------------
# 运行 / 调用 / 门禁
# ---------------------------------------------------------------------------


class FactNormalizationRunRepository:
    """规范化运行：权威元组校验 + 幂等键复用。

    同一 idempotency_key 重复提交返回原运行（不伪造 Phase 6 ReviewRun）；写入前冻结
    权威元组并校验其对应审核节点当前活动证据链。
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self._authority = FactAuthorityValidator(session)

    def create_or_reuse(self, run: FactNormalizationRun) -> FactNormalizationRun:
        self._authority.validate(run.authority)
        existing = self._by_idempotency_key(run.idempotency_key)
        if existing is not None:
            return self._decode_record(existing)
        payload_json, payload_sha256 = encode_contract(run)
        row = FactNormalizationRunRecord(
            run_id=run.run_id,
            idempotency_key=run.idempotency_key,
            prompt_version_id=run.prompt_version_id,
            model_config_id=run.model_config_id,
            input_scope_sha256=run.input_scope_sha256,
            status=run.status.value,
            job_id=None,
            created_by=run.created_by,
            created_at=to_utc_naive(run.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            **_authority_columns(run.authority),
        )
        self.session.add(row)
        _flush_guarded(self.session)
        return run

    def get(self, run_id: str) -> FactNormalizationRun:
        row = _get_required(
            self.session, FactNormalizationRunRecord, run_id, "FactNormalizationRun"
        )
        return self._decode_record(row)

    def set_status(
        self, run_id: str, status: FactNormalizationRunStatus
    ) -> FactNormalizationRun:
        """在受任务租约保护的事务中同步更新运行状态及其不可变镜像。"""
        row = _get_required(
            self.session, FactNormalizationRunRecord, run_id, "FactNormalizationRun"
        )
        current = self._decode_record(row)
        if current.status == status:
            return current
        if current.status != FactNormalizationRunStatus.RUNNING:
            raise Phase5RepositoryError(
                f"规范化运行 {run_id} 当前状态 {current.status.value}，不能转为 {status.value}"
            )
        updated = current.model_copy(update={"status": status})
        row.status = status.value
        row.payload_json, row.payload_sha256 = encode_contract(updated)
        _flush_guarded(self.session)
        return updated

    def reopen_for_retry(self, run_id: str) -> FactNormalizationRun:
        """人工重试或受控续跑同一任务时，把对应终态恢复为运行中。"""
        row = _get_required(
            self.session, FactNormalizationRunRecord, run_id, "FactNormalizationRun"
        )
        current = self._decode_record(row)
        if current.status not in {
            FactNormalizationRunStatus.FAILED,
            FactNormalizationRunStatus.CANCELLED,
        }:
            raise Phase5RepositoryError(
                f"规范化运行 {run_id} 当前状态 {current.status.value}，不能人工重试"
            )
        updated = current.model_copy(update={"status": FactNormalizationRunStatus.RUNNING})
        row.status = FactNormalizationRunStatus.RUNNING.value
        row.payload_json, row.payload_sha256 = encode_contract(updated)
        _flush_guarded(self.session)
        return updated

    def _by_idempotency_key(self, key: str) -> FactNormalizationRunRecord | None:
        rows = self.session.execute(select(FactNormalizationRunRecord)).scalars().all()
        matches = [row for row in rows if self._decode_record(row).idempotency_key == key]
        if len(matches) > 1:
            raise PersistedContractInvalid(
                f"运行幂等键 {key} 在已验证 payload 中重复，拒绝复用"
            )
        return matches[0] if matches else None

    def list_by_episode(self, review_episode_id: str) -> list[FactNormalizationRun]:
        rows = self.session.execute(select(FactNormalizationRunRecord)).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        return sorted(
            (
                run
                for run in contracts
                if run.authority.review_episode_id == review_episode_id
            ),
            key=lambda run: (run.created_at, run.run_id),
        )

    def _decode_record(self, row: FactNormalizationRunRecord) -> FactNormalizationRun:
        contract = decode_contract(
            FactNormalizationRun, row.payload_json, row.payload_sha256
        )
        payload = json.loads(row.payload_json)
        check_column_mirrors(
            "FactNormalizationRun",
            row,
            payload,
            {
                "run_id": "run_id",
                "idempotency_key": "idempotency_key",
                "prompt_version_id": "prompt_version_id",
                "model_config_id": "model_config_id",
                "input_scope_sha256": "input_scope_sha256",
                "status": "status",
                "created_by": "created_by",
                "created_at": "created_at",
                "project_id": "authority.project_id",
                "subject_id": "authority.subject_id",
                "review_episode_id": "authority.review_episode_id",
                "episode_revision": "authority.episode_revision",
                "protocol_version_id": "authority.protocol_version_id",
                "rule_set_id": "authority.rule_set_id",
                "rule_set_revision": "authority.rule_set_revision",
                "evidence_snapshot_v2_id": "authority.evidence_snapshot_v2_id",
                "complete_processing_revision_id": "authority.complete_processing_revision_id",
            },
        )
        return contract


class FactNormalizationCallRepository:
    """一次规范化调用：绑定已存在的运行，追加写。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, call: FactNormalizationCall) -> FactNormalizationCall:
        FactNormalizationRunRepository(self.session).get(call.run_id)
        payload_json, payload_sha256 = encode_contract(call)
        row = FactNormalizationCallRecord(
            call_id=call.call_id,
            run_id=call.run_id,
            logical_document_id=call.logical_document_id,
            page_numbers_json=call.page_numbers,
            status=call.status.value,
            input_sha256=call.input_sha256,
            raw_output_sha256=call.raw_output_sha256,
            created_at=to_utc_naive(call.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
        self.session.add(row)
        _flush_guarded(self.session)
        return call

    def get(self, call_id: str) -> FactNormalizationCall:
        row = _get_required(
            self.session, FactNormalizationCallRecord, call_id, "FactNormalizationCall"
        )
        return self._decode_record(row)

    @staticmethod
    def _decode_record(row: FactNormalizationCallRecord) -> FactNormalizationCall:
        contract = decode_contract(
            FactNormalizationCall, row.payload_json, row.payload_sha256
        )
        payload = json.loads(row.payload_json)
        check_column_mirrors(
            "FactNormalizationCall",
            row,
            payload,
            {
                "call_id": "call_id",
                "run_id": "run_id",
                "logical_document_id": "logical_document_id",
                "page_numbers_json": "page_numbers",
                "status": "status",
                "input_sha256": "input_sha256",
                "raw_output_sha256": "raw_output_sha256",
                "created_at": "created_at",
            },
        )
        return contract

    def list_by_run(self, run_id: str) -> list[FactNormalizationCall]:
        rows = self.session.execute(select(FactNormalizationCallRecord)).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        return sorted(
            (call for call in contracts if call.run_id == run_id),
            key=lambda call: (call.created_at, call.call_id),
        )


CandidateContract = (
    ClinicalFactCandidateV2
    | ClinicalEventCandidateV2
    | MedicationExposureCandidateV2
)


class FactNormalizationCandidateRepository:
    """不可变候选存储：与运行/调用绑定，与发布表物理分离。"""

    _KIND_BY_TYPE = {
        ClinicalFactCandidateV2: "fact",
        ClinicalEventCandidateV2: "event",
        MedicationExposureCandidateV2: "exposure",
    }
    _TYPE_BY_KIND = {value: key for key, value in _KIND_BY_TYPE.items()}

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self, call_id: str, candidate: CandidateContract
    ) -> CandidateContract:
        if call_id != candidate.call_id:
            raise Phase5RepositoryError(
                f"候选 {candidate.candidate_id} 的 call_id 与写入调用不一致"
            )
        call = FactNormalizationCallRepository(self.session).get(call_id)
        if call.run_id != candidate.run_id:
            raise Phase5RepositoryError(
                f"候选 {candidate.candidate_id} 不属于调用 {call_id} 的运行"
            )
        kind = self._KIND_BY_TYPE[type(candidate)]
        payload_json, payload_sha256 = encode_contract(candidate)
        self.session.add(
            FactNormalizationCandidateRecord(
                candidate_id=candidate.candidate_id,
                run_id=candidate.run_id,
                call_id=candidate.call_id,
                candidate_kind=kind,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(candidate.created_at),
            )
        )
        _flush_guarded(self.session)
        return candidate

    def get(self, candidate_id: str) -> CandidateContract:
        row = _get_required(
            self.session,
            FactNormalizationCandidateRecord,
            candidate_id,
            "FactNormalizationCandidate",
        )
        contract_type = self._TYPE_BY_KIND.get(row.candidate_kind)
        if contract_type is None:
            raise PersistedContractInvalid(
                f"候选 {candidate_id} 类型无法识别，拒绝还原"
            )
        contract = decode_contract(contract_type, row.payload_json, row.payload_sha256)
        payload = json.loads(row.payload_json)
        check_column_mirrors(
            "FactNormalizationCandidate",
            row,
            payload,
            {
                "candidate_id": "candidate_id",
                "run_id": "run_id",
                "call_id": "call_id",
                "candidate_kind": "candidate_kind",
                "created_at": "created_at",
            },
        )
        return contract

    def list_by_run(self, run_id: str) -> list[CandidateContract]:
        rows = self.session.execute(select(FactNormalizationCandidateRecord)).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        return sorted(
            (candidate for candidate in contracts if candidate.run_id == run_id),
            key=lambda candidate: (candidate.created_at, candidate.candidate_id),
        )

    def _decode_record(self, row: FactNormalizationCandidateRecord) -> CandidateContract:
        contract_type = self._TYPE_BY_KIND.get(row.candidate_kind)
        if contract_type is None:
            raise PersistedContractInvalid(
                f"候选 {row.candidate_id} 类型无法识别，拒绝还原"
            )
        contract = decode_contract(contract_type, row.payload_json, row.payload_sha256)
        payload = json.loads(row.payload_json)
        check_column_mirrors(
            "FactNormalizationCandidate",
            row,
            payload,
            {
                "candidate_id": "candidate_id",
                "run_id": "run_id",
                "call_id": "call_id",
                "candidate_kind": "candidate_kind",
                "created_at": "created_at",
            },
        )
        return contract


class FactNormalizationUnresolvedItemRepository:
    """逐页未解决项追加写仓储；与调用、运行和逻辑资料身份严格绑定。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self, unresolved: PersistedEvidenceNormalizerUnresolvedItem
    ) -> PersistedEvidenceNormalizerUnresolvedItem:
        call = FactNormalizationCallRepository(self.session).get(unresolved.call_id)
        if call.run_id != unresolved.run_id:
            raise Phase5RepositoryError("未解决项与调用不属于同一规范化运行")
        if call.logical_document_id != unresolved.logical_document_id:
            raise Phase5RepositoryError("未解决项与调用不属于同一逻辑资料")
        if not set(unresolved.item.affected_pages).issubset(set(call.page_numbers)):
            raise Phase5RepositoryError("未解决项引用了调用页清单之外的页面")
        payload_json, payload_sha256 = encode_contract(unresolved)
        self.session.add(
            FactNormalizationUnresolvedItemRecord(
                unresolved_item_id=unresolved.unresolved_item_id,
                run_id=unresolved.run_id,
                call_id=unresolved.call_id,
                logical_document_id=unresolved.logical_document_id,
                position=unresolved.position,
                code=unresolved.item.code,
                affected_pages_json=unresolved.item.affected_pages,
                affected_locator_ids_json=unresolved.item.affected_locator_ids,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(unresolved.created_at),
            )
        )
        _flush_guarded(self.session)
        return unresolved

    def get(self, unresolved_item_id: str) -> PersistedEvidenceNormalizerUnresolvedItem:
        row = _get_required(
            self.session,
            FactNormalizationUnresolvedItemRecord,
            unresolved_item_id,
            "FactNormalizationUnresolvedItem",
        )
        return self._decode_record(row)

    def list_by_run(self, run_id: str) -> list[PersistedEvidenceNormalizerUnresolvedItem]:
        rows = self.session.execute(
            select(FactNormalizationUnresolvedItemRecord).where(
                FactNormalizationUnresolvedItemRecord.run_id == run_id
            )
        ).scalars().all()
        return sorted(
            (self._decode_record(row) for row in rows),
            key=lambda item: (item.call_id, item.position, item.unresolved_item_id),
        )

    @staticmethod
    def _decode_record(
        row: FactNormalizationUnresolvedItemRecord,
    ) -> PersistedEvidenceNormalizerUnresolvedItem:
        contract = decode_contract(
            PersistedEvidenceNormalizerUnresolvedItem,
            row.payload_json,
            row.payload_sha256,
        )
        payload = json.loads(row.payload_json)
        check_column_mirrors(
            "FactNormalizationUnresolvedItem",
            row,
            payload,
            {
                "unresolved_item_id": "unresolved_item_id",
                "run_id": "run_id",
                "call_id": "call_id",
                "logical_document_id": "logical_document_id",
                "position": "position",
                "code": "item.code",
                "affected_pages_json": "item.affected_pages",
                "affected_locator_ids_json": "item.affected_locator_ids",
                "created_at": "created_at",
            },
        )
        return contract


class FactGateResultRepository:
    """逐候选门禁结果：绑定运行与调用（调用必须属于该运行）。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, result: FactGateResult) -> FactGateResult:
        self.create_many([result])
        return result

    def create_many(self, results: Sequence[FactGateResult]) -> list[FactGateResult]:
        """批量校验归属并单次落库，避免逐门禁重复查询和刷新。"""
        items = list(results)
        if not items:
            return []
        run_ids = {item.run_id for item in items}
        existing_run_ids = set(
            self.session.execute(
                select(FactNormalizationRunRecord.run_id).where(
                    FactNormalizationRunRecord.run_id.in_(run_ids)
                )
            ).scalars()
        )
        missing_runs = sorted(run_ids - existing_run_ids)
        if missing_runs:
            raise Phase5RepositoryError(f"门禁结果引用了不存在的运行：{missing_runs}")
        call_ids = {item.call_id for item in items}
        calls = {
            row.call_id: row
            for row in self.session.execute(
                select(FactNormalizationCallRecord).where(
                    FactNormalizationCallRecord.call_id.in_(call_ids)
                )
            ).scalars()
        }
        candidate_ids = {item.candidate_id for item in items}
        candidates = {
            row.candidate_id: row
            for row in self.session.execute(
                select(FactNormalizationCandidateRecord).where(
                    FactNormalizationCandidateRecord.candidate_id.in_(candidate_ids)
                )
            ).scalars()
        }
        rows = []
        for result in items:
            call = calls.get(result.call_id)
            if call is None or call.run_id != result.run_id:
                raise Phase5RepositoryError(
                    f"门禁结果调用 {result.call_id} 不属于运行 {result.run_id}"
                )
            candidate = candidates.get(result.candidate_id)
            if (
                candidate is None
                or candidate.run_id != result.run_id
                or candidate.call_id != result.call_id
            ):
                raise Phase5RepositoryError(
                    f"门禁结果 {result.gate_result_id} 与候选 {result.candidate_id} "
                    "不属于同一运行/调用"
                )
            payload_json, payload_sha256 = encode_contract(result)
            rows.append(
                FactGateResultRecord(
                    gate_result_id=result.gate_result_id,
                    run_id=result.run_id,
                    call_id=result.call_id,
                    candidate_id=result.candidate_id,
                    gate=result.gate.value,
                    outcome=result.outcome.value,
                    reasons_json=result.reasons,
                    created_at=to_utc_naive(result.created_at),
                    payload_json=payload_json,
                    payload_sha256=payload_sha256,
                )
            )
        self.session.add_all(rows)
        _flush_guarded(self.session)
        return items

    def get(self, gate_result_id: str) -> FactGateResult:
        row = _get_required(
            self.session, FactGateResultRecord, gate_result_id, "FactGateResult"
        )
        return self._decode_record(row)

    @staticmethod
    def _decode_record(row: FactGateResultRecord) -> FactGateResult:
        contract = decode_contract(
            FactGateResult, row.payload_json, row.payload_sha256
        )
        payload = json.loads(row.payload_json)
        check_column_mirrors(
            "FactGateResult",
            row,
            payload,
            {
                "gate_result_id": "gate_result_id",
                "run_id": "run_id",
                "call_id": "call_id",
                "candidate_id": "candidate_id",
                "gate": "gate",
                "outcome": "outcome",
                "reasons_json": "reasons",
                "created_at": "created_at",
            },
        )
        return contract

    def list_by_run(self, run_id: str) -> list[FactGateResult]:
        rows = self.session.execute(select(FactGateResultRecord)).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        return sorted(
            (result for result in contracts if result.run_id == run_id),
            key=lambda result: (result.created_at, result.gate_result_id),
        )


# ---------------------------------------------------------------------------
# 发布实体公共工具
# ---------------------------------------------------------------------------


class _PublishMixin:
    """发布实体公共写入门禁：权威元组、定位闭包、运行/门禁、跨实体事实引用。"""

    session: Session
    _authority: FactAuthorityValidator
    _complete_revision: Any | None

    def list_entity_links_for_locators(
        self, locator_ids: Sequence[str]
    ) -> list[tuple[str, str, str]]:
        """定位 -> 实体的显式反向索引（``fact_evidence_locator_links``）。

        返回 ``(locator_id, entity_kind, entity_id)``，按三者稳定排序。空输入
        返回空列表，不扫描全表。
        """
        unique_ids = sorted(set(locator_ids))
        if not unique_ids:
            return []
        rows = self.session.execute(
            select(FactEvidenceLocatorLinkRecord)
            .where(FactEvidenceLocatorLinkRecord.locator_id.in_(unique_ids))
            .order_by(
                FactEvidenceLocatorLinkRecord.locator_id,
                FactEvidenceLocatorLinkRecord.entity_kind,
                FactEvidenceLocatorLinkRecord.entity_id,
            )
        ).scalars().all()
        return [(row.locator_id, row.entity_kind, row.entity_id) for row in rows]

    def _validate_common(
        self,
        authority: FactAuthority,
        run_id: str,
        gate_id: str,
        locator_ids: list[str],
        expected_candidate_kind: str | None,
    ) -> CandidateContract:
        self._authority.validate(authority)
        self._authority.validate_locators(authority, locator_ids)
        run = FactNormalizationRunRepository(self.session).get(run_id)
        if run.authority != authority:
            raise FactCrossEntityError(
                f"运行 {run_id} 与待发布实体不属于同一不可变权威元组"
            )
        gate = FactGateResultRepository(self.session).get(gate_id)
        if gate.run_id != run_id:
            raise Phase5RepositoryError(
                f"门禁结果 {gate_id} 不属于运行 {run_id}"
            )
        if (
            gate.gate != FactGate.TRANSACTIONAL_PUBLISH.value
            or gate.outcome != GateOutcome.ACCEPTED.value
        ):
            raise Phase5RepositoryError(
                f"门禁结果 {gate_id} 不是已接受的最终事务发布门禁，拒绝发布"
            )
        candidate = FactNormalizationCandidateRepository(self.session).get(
            gate.candidate_id
        )
        if (
            candidate.run_id != run_id
            or expected_candidate_kind is not None
            and candidate.candidate_kind != expected_candidate_kind
        ):
            raise FactCrossEntityError(
                f"门禁结果 {gate_id} 引用的候选与发布实体类型或运行不一致"
            )
        return candidate

    def _validate_publication_group(
        self,
        *,
        authority: FactAuthority,
        run_id: str,
        primary_gate_id: str,
        gate_ids: list[str],
        candidate_ids: list[str],
        locator_ids: list[str],
        expected_candidate_kind: str,
    ) -> list[CandidateContract]:
        """校验一个发布实体的全部来源候选。

        旧调用方没有显式溯源集时仍按主门禁对应的单候选校验；
        新发布路径必须提供候选与最终门禁的一一对应集。
        """
        primary_candidate = self._validate_common(
            authority, run_id, primary_gate_id, locator_ids, expected_candidate_kind
        )
        effective_candidate_ids = candidate_ids or [primary_candidate.candidate_id]
        effective_gate_ids = gate_ids or [primary_gate_id]
        if primary_candidate.candidate_id not in effective_candidate_ids:
            raise FactCrossEntityError("主门禁对应候选必须属于发布溯源集")
        if primary_gate_id not in effective_gate_ids:
            raise FactCrossEntityError("主门禁必须属于发布门禁集")

        candidates: list[CandidateContract] = []
        gate_candidate_ids: list[str] = []
        gate_repository = FactGateResultRepository(self.session)
        candidate_repository = FactNormalizationCandidateRepository(self.session)
        for gate_id in effective_gate_ids:
            gate = gate_repository.get(gate_id)
            if (
                gate.run_id != run_id
                or gate.gate != FactGate.TRANSACTIONAL_PUBLISH
                or gate.outcome != GateOutcome.ACCEPTED
            ):
                raise Phase5RepositoryError(
                    f"门禁结果 {gate_id} 不是当前运行已接受的最终发布门禁"
                )
            gate_candidate_ids.append(gate.candidate_id)
        if sorted(gate_candidate_ids) != effective_candidate_ids:
            raise FactCrossEntityError("发布门禁与来源候选必须一一对应")
        for candidate_id in effective_candidate_ids:
            candidate = candidate_repository.get(candidate_id)
            if candidate.run_id != run_id or candidate.candidate_kind != expected_candidate_kind:
                raise FactCrossEntityError(
                    f"来源候选 {candidate_id} 与发布实体类型或运行不一致"
                )
            candidates.append(candidate)
        locator_union = sorted(
            {locator_id for candidate in candidates for locator_id in candidate.locator_ids}
        )
        if locator_union != locator_ids:
            raise FactLocatorReferenceError("发布定位必须等于全部来源候选的定位并集")
        return candidates

    def _require_published_source_strength(
        self,
        authority: FactAuthority,
        candidates: list[CandidateContract],
        published_strength: SourceStrength,
    ) -> None:
        from app.domain.gates.fact_evidence_closure import (
            derive_source_strength_for_candidate,
            resolve_source_strength_for_candidate,
        )
        from app.storage.evidence_locator_repositories import (
            CompleteEvidenceProcessingRevisionRepository,
        )

        revision = self._complete_revision
        if revision is None:
            revision = CompleteEvidenceProcessingRevisionRepository(self.session).get(
                authority.complete_processing_revision_id
            )
        elif (
            revision.evidence_processing_revision_id
            != authority.complete_processing_revision_id
        ):
            raise FactCrossEntityError(
                "批量发布复用的完整处理修订与权威元组不一致"
            )
        rank = {
            SourceStrength.UNVERIFIABLE: 0,
            SourceStrength.SCREENING_RECORD_TRANSCRIPTION: 1,
            SourceStrength.CURRENT_STUDY_CHART: 2,
            SourceStrength.HISTORICAL_PRIMARY: 3,
            SourceStrength.CONTEMPORANEOUS_OBJECTIVE: 4,
        }
        expected_from_metadata = max(
            (
                derive_source_strength_for_candidate(
                    self.session, candidate, revision
                )
                for candidate in candidates
            ),
            key=rank.__getitem__,
        )
        if published_strength == expected_from_metadata:
            return
        try:
            expected_from_candidates = max(
                (
                    resolve_source_strength_for_candidate(
                        self.session, candidate, revision
                    )
                    for candidate in candidates
                ),
                key=rank.__getitem__,
            )
        except ValueError as exc:
            raise FactCrossEntityError(
                "发布来源强度超出完整处理修订允许范围"
            ) from exc
        if published_strength != expected_from_candidates:
            raise FactCrossEntityError(
                "发布来源强度超出完整处理修订允许范围"
            )

    def _require_facts_same_authority(
        self, authority: FactAuthority, fact_ids: list[str]
    ) -> None:
        """事件/暴露/冲突引用的事实必须属于同一审核节点与处理修订。"""
        unique = sorted(set(fact_ids))
        if len(unique) != len(fact_ids):
            raise FactCrossEntityError("事实引用不允许重复")
        repository = ClinicalFactV2Repository(self.session)
        for fact_id in unique:
            fact = repository.get(fact_id)
            if fact.authority != authority:
                raise FactCrossEntityError(
                    f"事实 {fact.fact_id} 与事件/暴露/冲突不属于同一不可变权威元组"
                )

    def _fact_candidate_ids(self, fact_ids: list[str]) -> list[str]:
        fact_repository = ClinicalFactV2Repository(self.session)
        gate_repository = FactGateResultRepository(self.session)
        facts = [fact_repository.get(fact_id) for fact_id in fact_ids]
        return sorted(
            {
                candidate_id
                for fact in facts
                for candidate_id in (
                    fact.source_candidate_ids
                    or [gate_repository.get(fact.gate_id).candidate_id]
                )
            }
        )

    def _require_fact_candidate_reference_closure(
        self,
        fact_ids: list[str],
        referenced_candidate_ids: list[str],
        *,
        entity_label: str,
    ) -> None:
        fact_repository = ClinicalFactV2Repository(self.session)
        gate_repository = FactGateResultRepository(self.session)
        referenced = set(referenced_candidate_ids)
        sources_by_fact = []
        for fact_id in fact_ids:
            fact = fact_repository.get(fact_id)
            sources_by_fact.append(
                set(
                    fact.source_candidate_ids
                    or [gate_repository.get(fact.gate_id).candidate_id]
                )
            )
        if (
            not referenced.issubset(set().union(*sources_by_fact))
            or any(not referenced.intersection(sources) for sources in sources_by_fact)
        ):
            raise FactCrossEntityError(
                f"发布{entity_label}的事实引用与候选事实引用不一致"
            )

    def _fact_semantic_objects(self, fact_ids: list[str]) -> list[str]:
        repository = ClinicalFactV2Repository(self.session)
        return sorted(
            {
                f"{fact.fact_type}:{fact.asserted_object}"
                for fact_id in fact_ids
                for fact in [repository.get(fact_id)]
            }
        )

    def _fact_locator_closure(self, fact_ids: list[str]) -> set[str]:
        """成员事实的定位闭包（来自定位链接表，唯一的定位真相源）。"""
        repository = ClinicalFactV2Repository(self.session)
        return {
            locator_id
            for fact_id in fact_ids
            for locator_id in repository.get(fact_id).locator_ids
        }

    def _require_locators_within_facts(
        self, locator_ids: list[str], fact_ids: list[str]
    ) -> None:
        """事件/暴露/冲突的定位必须属于其引用事实的定位闭包。"""
        closure = self._fact_locator_closure(fact_ids)
        outside = [loc for loc in locator_ids if loc not in closure]
        if outside:
            raise FactLocatorReferenceError(
                f"定位 {sorted(outside)} 不属于其引用事实的定位闭包（同一审核节点内"
                "其他事实的证据不构成事件证据）"
            )

    def _require_revision_chain_head(
        self,
        record_cls: Any,
        stable_identity: str,
        revision: int,
        decode_record: Any,
    ) -> None:
        """同稳定身份 revision 链只允许追加链头 +1。"""
        rows = self.session.execute(select(record_cls)).scalars().all()
        contracts = [decode_record(row) for row in rows]
        chain = [
            contract
            for contract in contracts
            if contract.stable_identity == stable_identity
        ]
        if not chain:
            if revision != 1:
                raise FactRevisionChainError(
                    f"稳定身份 {stable_identity} 的首个 revision 必须为 1"
                )
            return
        head = max(chain, key=lambda contract: contract.revision)
        if revision != head.revision + 1:
            raise FactRevisionChainError(
                f"稳定身份 {stable_identity} 的 revision 必须是当前链头 "
                f"{head.revision} + 1（得到 {revision}），回退/跳号一律拒绝"
            )

    def _write_locator_links(
        self, entity_kind: str, entity_id: str, locator_ids: list[str]
    ) -> None:
        parent_column = {
            "fact": "fact_id",
            "event": "event_id",
            "exposure": "exposure_id",
            "conflict": "conflict_group_id",
            "expectation": "expectation_id",
        }.get(entity_kind)
        if parent_column is None:
            raise Phase5RepositoryError(f"不支持的定位链接实体类型 {entity_kind}")
        for position, locator_id in enumerate(locator_ids, start=1):
            self.session.add(
                FactEvidenceLocatorLinkRecord(
                    entity_kind=entity_kind,
                    entity_id=entity_id,
                    position=position,
                    locator_id=locator_id,
                    **{parent_column: entity_id},
                )
            )
        _flush_guarded(self.session)

    def _locator_ids_for(self, entity_kind: str, entity_id: str) -> list[str]:
        rows = self.session.execute(
            select(FactEvidenceLocatorLinkRecord)
            .where(
                FactEvidenceLocatorLinkRecord.entity_kind == entity_kind,
                FactEvidenceLocatorLinkRecord.entity_id == entity_id,
            )
            .order_by(FactEvidenceLocatorLinkRecord.position)
        ).scalars().all()
        return [row.locator_id for row in rows]

    def _assert_link_mirror(
        self,
        entity_kind: str,
        entity_id: str,
        payload_ids: list[str],
        *,
        locator_ids: list[str] | None = None,
    ) -> None:
        links = (
            list(locator_ids)
            if locator_ids is not None
            else self._locator_ids_for(entity_kind, entity_id)
        )
        if links != payload_ids:
            raise PersistedContractInvalid(
                f"{entity_kind} {entity_id} 定位链接与 payload 定位不一致，拒绝还原合同"
            )


# ---------------------------------------------------------------------------
# 临床事实
# ---------------------------------------------------------------------------


class ClinicalFactV2Repository(_PublishMixin):
    """发布接受的事实：权威元组 + 定位闭包 + 断言依据定位约束 + revision 链追加。"""

    def __init__(
        self,
        session: Session,
        *,
        authority_validator: FactAuthorityValidator | None = None,
        complete_revision: Any | None = None,
    ) -> None:
        self.session = session
        self._authority = authority_validator or FactAuthorityValidator(session)
        self._complete_revision = complete_revision

    def _publication_candidates(self, fact: ClinicalFactV2) -> list[CandidateContract]:
        if fact.inherited_from_fact_id is None:
            return self._validate_publication_group(
                authority=fact.authority, run_id=fact.run_id,
                primary_gate_id=fact.gate_id, gate_ids=fact.gate_ids,
                candidate_ids=fact.source_candidate_ids, locator_ids=fact.locator_ids,
                expected_candidate_kind="fact",
            )
        from app.storage.fact_correction_repository import FactCorrectionRepository

        prior = self.get(fact.inherited_from_fact_id)
        if (
            prior.authority != fact.authority
            or prior.stable_identity != fact.stable_identity
            or prior.run_id == fact.run_id
            or prior.revision + 1 != fact.revision
            or prior.fact_id in FactCorrectionRepository(self.session).superseded_entity_ids(
                fact.authority
            )
        ):
            raise FactCrossEntityError("继承来源必须是同一事实未经更正的上一版本")
        inherited_ids = set(prior.source_candidate_ids)
        inherited_gates = set(prior.gate_ids)
        if (
            not inherited_ids or not inherited_gates
            or not inherited_ids <= set(fact.source_candidate_ids)
            or not inherited_gates <= set(fact.gate_ids)
        ):
            raise FactCrossEntityError("继承来源必须完整保留上一版本的候选与发布记录")
        repository = FactNormalizationCandidateRepository(self.session)
        current_ids = sorted(set(fact.source_candidate_ids) - inherited_ids)
        if not current_ids or not (set(fact.gate_ids) - inherited_gates):
            raise FactCrossEntityError("继承发布必须包含本次已核实的新来源")
        current_candidates = [repository.get(item) for item in current_ids]
        current_locators = sorted({
            locator for candidate in current_candidates for locator in candidate.locator_ids
        })
        current = self._validate_publication_group(
            authority=fact.authority, run_id=fact.run_id,
            primary_gate_id=fact.gate_id,
            gate_ids=sorted(set(fact.gate_ids) - inherited_gates),
            candidate_ids=current_ids, locator_ids=current_locators,
            expected_candidate_kind="fact",
        )
        inherited = [repository.get(item) for item in sorted(inherited_ids)]
        if sorted({loc for item in inherited for loc in item.locator_ids}) != prior.locator_ids:
            raise FactLocatorReferenceError("继承来源与上一版本定位不一致")
        candidates = sorted(current + inherited, key=lambda item: item.candidate_id)
        if sorted({loc for item in candidates for loc in item.locator_ids}) != fact.locator_ids:
            raise FactLocatorReferenceError("发布定位必须完整保留本次与继承来源")
        self._authority.validate_locators(fact.authority, fact.locator_ids)
        return candidates

    def create(self, fact: ClinicalFactV2) -> ClinicalFactV2:
        candidates = self._publication_candidates(fact)
        expected_semantics = (
            fact.fact_type,
            fact.polarity,
            fact.asserted_object,
            fact.value,
            fact.unit,
            _date_range_semantics(fact.date_range),
        )
        for candidate in candidates:
            if not isinstance(candidate, ClinicalFactCandidateV2) or (
                candidate.fact_type,
                candidate.polarity,
                candidate.asserted_object,
                candidate.canonical_value,
                candidate.unit,
                _date_range_semantics(candidate.date_range),
            ) != expected_semantics:
                raise FactCrossEntityError(
                    f"发布事实 {fact.fact_id} 与最终门禁审查的候选语义不一致"
                )
        record_times = {candidate.record_time for candidate in candidates}
        expected_record_time = next(iter(record_times)) if len(record_times) == 1 else None
        representative = min(candidates, key=lambda candidate: candidate.candidate_id)
        expected_requirement_ids = sorted(
            {
                requirement_id
                for candidate in candidates
                for requirement_id in candidate.supported_requirement_ids
            }
        )
        if fact.supported_requirement_ids != expected_requirement_ids:
            raise FactCrossEntityError(
                f"发布事实 {fact.fact_id} 支持的资料要求与来源候选确定性并集不一致"
            )
        if fact.record_time != expected_record_time or fact.assertion_basis != representative.assertion_basis:
            raise FactCrossEntityError(
                f"发布事实 {fact.fact_id} 的记录时间或断言依据与来源候选的确定性合并结果不一致"
            )
        self._require_published_source_strength(
            fact.authority, candidates, fact.source_strength
        )
        if fact.assertion_basis is not None:
            if fact.assertion_basis.locator_id not in fact.locator_ids:
                raise FactLocatorReferenceError(
                    "断言依据定位必须属于发布事实的定位集合"
                )
            locator = _get_required(
                self.session,
                EvidenceLocatorArtifactRecord,
                fact.assertion_basis.locator_id,
                "EvidenceLocatorArtifact",
            )
            if locator.source_text_sha256 != fact.assertion_basis.source_text_sha256:
                raise FactLocatorReferenceError(
                    "断言依据原文哈希与定位记录不一致，拒绝发布"
                )
        self._require_revision_chain_head(
            ClinicalFactV2Record,
            fact.stable_identity,
            fact.revision,
            self._decode_record,
        )
        payload_json, payload_sha256 = encode_contract(fact)
        row = ClinicalFactV2Record(
            fact_id=fact.fact_id,
            run_id=fact.run_id,
            gate_id=fact.gate_id,
            fact_type=fact.fact_type,
            polarity=fact.polarity.value,
            value_json=fact.value,
            unit=fact.unit,
            source_strength=fact.source_strength.value,
            record_time=to_utc_naive(fact.record_time),
            assertion_object=fact.asserted_object,
            assertion_text=(
                fact.assertion_basis.assertion_text
                if fact.assertion_basis is not None
                else None
            ),
            assertion_locator_id=(
                fact.assertion_basis.locator_id
                if fact.assertion_basis is not None
                else None
            ),
            assertion_source_text_sha256=(
                fact.assertion_basis.source_text_sha256
                if fact.assertion_basis is not None
                else None
            ),
            stable_identity=fact.stable_identity,
            revision=fact.revision,
            created_at=to_utc_naive(fact.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            **_date_range_columns(fact.date_range),
            **_authority_columns(fact.authority),
        )
        self.session.add(row)
        _flush_guarded(self.session)
        self._write_locator_links("fact", fact.fact_id, fact.locator_ids)
        return fact

    def get(self, fact_id: str) -> ClinicalFactV2:
        row = _get_required(
            self.session, ClinicalFactV2Record, fact_id, "ClinicalFactV2"
        )
        return self._decode_record(row)

    def get_many(self, fact_ids: Sequence[str]) -> dict[str, ClinicalFactV2]:
        """按 ID 批量还原已发布事实；缺失不得静默省略。定位镜像一次预取。"""
        ordered = list(dict.fromkeys(fact_ids))
        if not ordered:
            return {}
        rows = self.session.execute(
            select(ClinicalFactV2Record).where(
                ClinicalFactV2Record.fact_id.in_(ordered)
            )
        ).scalars().all()
        by_id = {row.fact_id: row for row in rows}
        missing = [fact_id for fact_id in ordered if fact_id not in by_id]
        if missing:
            raise Phase5RepositoryError(
                f"ClinicalFactV2 不存在: {missing}"
            )
        locators = prefetch_locator_link_ids(self.session, "fact", ordered)
        return {
            fact_id: self._decode_record(
                by_id[fact_id], locator_ids=locators[fact_id]
            )
            for fact_id in ordered
        }

    def list_for_authority(self, authority: FactAuthority) -> list[ClinicalFactV2]:
        """按冻结权威 SQL 过滤后批量解码；定位镜像一次预取。"""
        rows = self.session.execute(
            select(ClinicalFactV2Record).where(
                *authority_column_filters(ClinicalFactV2Record, authority)
            )
        ).scalars().all()
        locators = prefetch_locator_link_ids(
            self.session, "fact", [row.fact_id for row in rows]
        )
        contracts = [
            self._decode_record(row, locator_ids=locators[row.fact_id]) for row in rows
        ]
        return sorted(
            (fact for fact in contracts if fact.authority == authority),
            key=lambda fact: (fact.created_at, fact.fact_id),
        )

    def list_by_episode(self, review_episode_id: str) -> list[ClinicalFactV2]:
        rows = self.session.execute(select(ClinicalFactV2Record)).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        return sorted(
            (
                fact
                for fact in contracts
                if fact.authority.review_episode_id == review_episode_id
            ),
            key=lambda fact: (fact.created_at, fact.fact_id),
        )

    def _decode_record(
        self, row: ClinicalFactV2Record, *, locator_ids: list[str] | None = None
    ) -> ClinicalFactV2:
        contract = decode_contract(ClinicalFactV2, row.payload_json, row.payload_sha256)
        payload = json.loads(row.payload_json)
        _check_tolerant_mirrors(
            "ClinicalFactV2",
            row,
            payload,
            {
                "fact_id": "fact_id",
                "run_id": "run_id",
                "gate_id": "gate_id",
                "fact_type": "fact_type",
                "polarity": "polarity",
                "value_json": "value",
                "unit": "unit",
                "source_strength": "source_strength",
                "record_time": "record_time",
                "stable_identity": "stable_identity",
                "revision": "revision",
                "created_at": "created_at",
                "date_precision": "date_range.precision",
                "date_lower_bound": "date_range.lower_bound",
                "date_upper_bound": "date_range.upper_bound",
                "date_source_text": "date_range.source_text",
                "assertion_object": "asserted_object",
                "assertion_text": "assertion_basis.assertion_text",
                "assertion_locator_id": "assertion_basis.locator_id",
                "assertion_source_text_sha256": "assertion_basis.source_text_sha256",
                "project_id": "authority.project_id",
                "subject_id": "authority.subject_id",
                "review_episode_id": "authority.review_episode_id",
                "episode_revision": "authority.episode_revision",
                "protocol_version_id": "authority.protocol_version_id",
                "rule_set_id": "authority.rule_set_id",
                "rule_set_revision": "authority.rule_set_revision",
                "evidence_snapshot_v2_id": "authority.evidence_snapshot_v2_id",
                "complete_processing_revision_id": "authority.complete_processing_revision_id",
            },
        )
        self._assert_link_mirror(
            "fact", row.fact_id, payload["locator_ids"], locator_ids=locator_ids
        )
        return contract.model_copy(update={"locator_ids": payload["locator_ids"]})


# ---------------------------------------------------------------------------
# 事件 / 暴露 / 冲突组
# ---------------------------------------------------------------------------


class ClinicalEventV2Repository(_PublishMixin):
    """发布事件：事实与定位引用必须同一权威元组，事件定位属于成员事实定位闭包。"""

    def __init__(
        self,
        session: Session,
        *,
        authority_validator: FactAuthorityValidator | None = None,
        complete_revision: Any | None = None,
    ) -> None:
        self.session = session
        self._authority = authority_validator or FactAuthorityValidator(session)
        self._complete_revision = complete_revision

    def create(self, event: ClinicalEventV2) -> ClinicalEventV2:
        origin_run = event.run_id
        if event.source_revision_of is not None:
            from app.storage.source_reference_successors import source_successor_origin_run
            origin_run = source_successor_origin_run(
                self.session, event, self, id_field="event_id"
            )
        candidates = self._validate_publication_group(
            authority=event.authority,
            run_id=origin_run,
            primary_gate_id=event.gate_id,
            gate_ids=event.gate_ids,
            candidate_ids=event.source_candidate_ids,
            locator_ids=event.locator_ids,
            expected_candidate_kind="event",
        )
        expected_semantics = (
            event.event_type,
            _date_range_semantics(event.start_range),
            _date_range_semantics(event.end_range),
            event.duration_status,
        )
        for candidate in candidates:
            if not isinstance(candidate, ClinicalEventCandidateV2) or (
                candidate.event_type,
                _date_range_semantics(candidate.start_range),
                _date_range_semantics(candidate.end_range),
                candidate.duration_status,
            ) != expected_semantics:
                raise FactCrossEntityError(
                    f"发布事件 {event.event_id} 与最终门禁审查的候选语义不一致"
                )
        record_times = {candidate.record_time for candidate in candidates}
        expected_record_time = next(iter(record_times)) if len(record_times) == 1 else None
        if event.record_time != expected_record_time:
            raise FactCrossEntityError(
                f"发布事件 {event.event_id} 的记录时间与来源候选的确定性合并结果不一致"
            )
        self._require_published_source_strength(
            event.authority, candidates, event.source_strength
        )
        self._require_facts_same_authority(event.authority, event.fact_ids)
        expected_fact_candidates = sorted(
            {fact_id for candidate in candidates for fact_id in candidate.fact_candidate_ids}
        )
        self._require_fact_candidate_reference_closure(
            event.fact_ids,
            expected_fact_candidates,
            entity_label=f"事件 {event.event_id}",
        )
        if self._fact_semantic_objects(event.fact_ids) != event.referenced_fact_objects:
            raise FactCrossEntityError(
                f"发布事件 {event.event_id} 的引用事实对象与实际发布事实不一致"
            )
        self._require_locators_within_facts(event.locator_ids, event.fact_ids)
        self._require_revision_chain_head(
            ClinicalEventV2Record,
            event.stable_identity,
            event.revision,
            self._decode_record,
        )
        payload_json, payload_sha256 = encode_contract(event)
        row = ClinicalEventV2Record(
            event_id=event.event_id,
            run_id=event.run_id,
            gate_id=event.gate_id,
            event_type=event.event_type,
            record_time=to_utc_naive(event.record_time),
            source_strength=event.source_strength.value,
            stable_identity=event.stable_identity,
            revision=event.revision,
            created_at=to_utc_naive(event.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            start_precision=(
                event.start_range.precision.value
                if event.start_range is not None
                else None
            ),
            start_lower_bound=(
                event.start_range.lower_bound
                if event.start_range is not None
                else None
            ),
            start_upper_bound=(
                event.start_range.upper_bound
                if event.start_range is not None
                else None
            ),
            start_source_text=(
                event.start_range.source_text
                if event.start_range is not None
                else None
            ),
            end_precision=(
                event.end_range.precision.value if event.end_range is not None else None
            ),
            end_lower_bound=(
                event.end_range.lower_bound if event.end_range is not None else None
            ),
            end_upper_bound=(
                event.end_range.upper_bound if event.end_range is not None else None
            ),
            end_source_text=(
                event.end_range.source_text if event.end_range is not None else None
            ),
            duration_status=event.duration_status.value,
            **_authority_columns(event.authority),
        )
        self.session.add(row)
        _flush_guarded(self.session)
        for position, fact_id in enumerate(event.fact_ids, start=1):
            self.session.add(
                EventFactLinkRecord(
                    event_id=event.event_id, position=position, fact_id=fact_id
                )
            )
        self._write_locator_links("event", event.event_id, event.locator_ids)
        return event

    def get(self, event_id: str) -> ClinicalEventV2:
        row = _get_required(self.session, ClinicalEventV2Record, event_id, "ClinicalEventV2")
        return self._decode_record(row)

    def list_for_authority(self, authority: FactAuthority) -> list[ClinicalEventV2]:
        rows = self.session.execute(
            select(ClinicalEventV2Record).where(
                *authority_column_filters(ClinicalEventV2Record, authority)
            )
        ).scalars().all()
        event_ids = [row.event_id for row in rows]
        locators = prefetch_locator_link_ids(self.session, "event", event_ids)
        fact_ids_by_event = _prefetch_event_fact_ids(self.session, event_ids)
        referenced = sorted(
            {fact_id for ids in fact_ids_by_event.values() for fact_id in ids}
        )
        facts_by_id = ClinicalFactV2Repository(self.session).get_many(referenced)
        contracts = []
        for row in rows:
            fact_ids = fact_ids_by_event[row.event_id]
            objects = sorted(
                {
                    f"{facts_by_id[fact_id].fact_type}:{facts_by_id[fact_id].asserted_object}"
                    for fact_id in fact_ids
                }
            )
            contracts.append(
                self._decode_record(
                    row,
                    locator_ids=locators[row.event_id],
                    fact_ids=fact_ids,
                    referenced_fact_objects=objects,
                )
            )
        return sorted(
            (event for event in contracts if event.authority == authority),
            key=lambda event: (event.created_at, event.event_id),
        )

    def list_by_episode(self, review_episode_id: str) -> list[ClinicalEventV2]:
        rows = self.session.execute(select(ClinicalEventV2Record)).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        return sorted(
            (
                event
                for event in contracts
                if event.authority.review_episode_id == review_episode_id
            ),
            key=lambda event: (event.created_at, event.event_id),
        )

    def list_event_fact_links(self, fact_ids: Sequence[str]) -> list[tuple[str, str]]:
        """一次查出 ``(event_id, fact_id)``，禁止按事实 N+1。"""
        unique_ids = sorted(set(fact_ids))
        if not unique_ids:
            return []
        rows = self.session.execute(
            select(EventFactLinkRecord.event_id, EventFactLinkRecord.fact_id)
            .where(EventFactLinkRecord.fact_id.in_(unique_ids))
            .order_by(EventFactLinkRecord.event_id, EventFactLinkRecord.fact_id)
        ).all()
        return [(row[0], row[1]) for row in rows]

    def list_event_ids_for_facts(self, fact_ids: Sequence[str]) -> list[str]:
        """事实 -> 引用它的事件（``event_fact_links.fact_id`` 反向索引）。"""
        return sorted({event_id for event_id, _fact_id in self.list_event_fact_links(fact_ids)})

    def _decode_record(
        self,
        row: ClinicalEventV2Record,
        *,
        locator_ids: list[str] | None = None,
        fact_ids: list[str] | None = None,
        referenced_fact_objects: list[str] | None = None,
    ) -> ClinicalEventV2:
        contract = decode_contract(ClinicalEventV2, row.payload_json, row.payload_sha256)
        payload = json.loads(row.payload_json)
        _check_tolerant_mirrors(
            "ClinicalEventV2",
            row,
            payload,
            {
                "event_id": "event_id",
                "run_id": "run_id",
                "gate_id": "gate_id",
                "event_type": "event_type",
                "record_time": "record_time",
                "source_strength": "source_strength",
                "stable_identity": "stable_identity",
                "revision": "revision",
                "created_at": "created_at",
                "start_precision": "start_range.precision",
                "start_lower_bound": "start_range.lower_bound",
                "start_upper_bound": "start_range.upper_bound",
                "start_source_text": "start_range.source_text",
                "end_precision": "end_range.precision",
                "end_lower_bound": "end_range.lower_bound",
                "end_upper_bound": "end_range.upper_bound",
                "end_source_text": "end_range.source_text",
                "duration_status": "duration_status",
                "project_id": "authority.project_id",
                "subject_id": "authority.subject_id",
                "review_episode_id": "authority.review_episode_id",
                "episode_revision": "authority.episode_revision",
                "protocol_version_id": "authority.protocol_version_id",
                "rule_set_id": "authority.rule_set_id",
                "rule_set_revision": "authority.rule_set_revision",
                "evidence_snapshot_v2_id": "authority.evidence_snapshot_v2_id",
                "complete_processing_revision_id": "authority.complete_processing_revision_id",
            },
        )
        self._assert_link_mirror(
            "event", row.event_id, payload["locator_ids"], locator_ids=locator_ids
        )
        if fact_ids is None:
            fact_rows = self.session.execute(
                select(EventFactLinkRecord)
                .where(EventFactLinkRecord.event_id == row.event_id)
                .order_by(EventFactLinkRecord.position)
            ).scalars().all()
            fact_ids = [link.fact_id for link in fact_rows]
        if fact_ids != payload["fact_ids"]:
            raise PersistedContractInvalid(
                f"event {row.event_id} 事实链接与 payload 不一致，拒绝还原合同"
            )
        objects = (
            referenced_fact_objects
            if referenced_fact_objects is not None
            else self._fact_semantic_objects(fact_ids)
        )
        if objects != payload["referenced_fact_objects"]:
            raise PersistedContractInvalid(
                f"event {row.event_id} 引用事实对象与实际发布事实不一致，拒绝还原合同"
            )
        return contract.model_copy(
            update={"fact_ids": fact_ids, "locator_ids": payload["locator_ids"]}
        )


class MedicationExposureV2Repository(_PublishMixin):
    """发布暴露：同事件约束，保留原始药名/起止/持续状态。"""

    def __init__(
        self,
        session: Session,
        *,
        authority_validator: FactAuthorityValidator | None = None,
        complete_revision: Any | None = None,
    ) -> None:
        self.session = session
        self._authority = authority_validator or FactAuthorityValidator(session)
        self._complete_revision = complete_revision

    def create(self, exposure: MedicationExposureV2) -> MedicationExposureV2:
        origin_run = exposure.run_id
        if exposure.source_revision_of is not None:
            from app.storage.source_reference_successors import source_successor_origin_run
            origin_run = source_successor_origin_run(
                self.session, exposure, self, id_field="exposure_id"
            )
        candidates = self._validate_publication_group(
            authority=exposure.authority,
            run_id=origin_run,
            primary_gate_id=exposure.gate_id,
            gate_ids=exposure.gate_ids,
            candidate_ids=exposure.source_candidate_ids,
            locator_ids=exposure.locator_ids,
            expected_candidate_kind="exposure",
        )
        expected_semantics = (
            exposure.medication_name,
            exposure.category,
            exposure.indication,
            exposure.dose,
            exposure.unit,
            exposure.frequency,
            exposure.route,
            _date_range_semantics(exposure.start_range),
            _date_range_semantics(exposure.end_range),
            exposure.duration_status,
        )
        for candidate in candidates:
            if not isinstance(candidate, MedicationExposureCandidateV2) or (
                candidate.medication_name,
                candidate.category,
                candidate.indication,
                candidate.dose,
                candidate.unit,
                candidate.frequency,
                candidate.route,
                _date_range_semantics(candidate.start_range),
                _date_range_semantics(candidate.end_range),
                candidate.duration_status,
            ) != expected_semantics:
                raise FactCrossEntityError(
                    f"发布暴露 {exposure.exposure_id} 与最终门禁审查的候选语义不一致"
                )
        record_times = {candidate.record_time for candidate in candidates}
        expected_record_time = next(iter(record_times)) if len(record_times) == 1 else None
        if exposure.record_time != expected_record_time:
            raise FactCrossEntityError(
                f"发布暴露 {exposure.exposure_id} 的记录时间与来源候选的确定性合并结果不一致"
            )
        self._require_published_source_strength(
            exposure.authority, candidates, exposure.source_strength
        )
        self._require_facts_same_authority(exposure.authority, exposure.fact_ids)
        expected_fact_candidates = sorted(
            {fact_id for candidate in candidates for fact_id in candidate.fact_candidate_ids}
        )
        self._require_fact_candidate_reference_closure(
            exposure.fact_ids,
            expected_fact_candidates,
            entity_label=f"暴露 {exposure.exposure_id}",
        )
        self._require_locators_within_facts(exposure.locator_ids, exposure.fact_ids)
        self._require_revision_chain_head(
            MedicationExposureV2Record,
            exposure.stable_identity,
            exposure.revision,
            self._decode_record,
        )
        payload_json, payload_sha256 = encode_contract(exposure)
        row = MedicationExposureV2Record(
            exposure_id=exposure.exposure_id,
            run_id=exposure.run_id,
            gate_id=exposure.gate_id,
            medication_name=exposure.medication_name,
            category=exposure.category,
            indication=exposure.indication,
            dose=exposure.dose,
            unit=exposure.unit,
            frequency=exposure.frequency,
            route=exposure.route,
            duration_status=exposure.duration_status.value,
            record_time=to_utc_naive(exposure.record_time),
            source_strength=exposure.source_strength.value,
            stable_identity=exposure.stable_identity,
            revision=exposure.revision,
            created_at=to_utc_naive(exposure.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            start_precision=(
                exposure.start_range.precision.value
                if exposure.start_range is not None
                else None
            ),
            start_lower_bound=(
                exposure.start_range.lower_bound
                if exposure.start_range is not None
                else None
            ),
            start_upper_bound=(
                exposure.start_range.upper_bound
                if exposure.start_range is not None
                else None
            ),
            start_source_text=(
                exposure.start_range.source_text
                if exposure.start_range is not None
                else None
            ),
            end_precision=(
                exposure.end_range.precision.value
                if exposure.end_range is not None
                else None
            ),
            end_lower_bound=(
                exposure.end_range.lower_bound
                if exposure.end_range is not None
                else None
            ),
            end_upper_bound=(
                exposure.end_range.upper_bound
                if exposure.end_range is not None
                else None
            ),
            end_source_text=(
                exposure.end_range.source_text
                if exposure.end_range is not None
                else None
            ),
            **_authority_columns(exposure.authority),
        )
        self.session.add(row)
        _flush_guarded(self.session)
        for position, fact_id in enumerate(exposure.fact_ids, start=1):
            self.session.add(
                ExposureFactLinkRecord(
                    exposure_id=exposure.exposure_id,
                    position=position,
                    fact_id=fact_id,
                )
            )
        self._write_locator_links("exposure", exposure.exposure_id, exposure.locator_ids)
        return exposure

    def get(self, exposure_id: str) -> MedicationExposureV2:
        row = _get_required(
            self.session, MedicationExposureV2Record, exposure_id, "MedicationExposureV2"
        )
        return self._decode_record(row)

    def list_for_authority(self, authority: FactAuthority) -> list[MedicationExposureV2]:
        rows = self.session.execute(
            select(MedicationExposureV2Record).where(
                *authority_column_filters(MedicationExposureV2Record, authority)
            )
        ).scalars().all()
        exposure_ids = [row.exposure_id for row in rows]
        locators = prefetch_locator_link_ids(self.session, "exposure", exposure_ids)
        fact_ids_by_exposure = _prefetch_exposure_fact_ids(self.session, exposure_ids)
        contracts = [
            self._decode_record(
                row,
                locator_ids=locators[row.exposure_id],
                fact_ids=fact_ids_by_exposure[row.exposure_id],
            )
            for row in rows
        ]
        return sorted(
            (item for item in contracts if item.authority == authority),
            key=lambda item: (item.created_at, item.exposure_id),
        )

    def list_by_episode(self, review_episode_id: str) -> list[MedicationExposureV2]:
        rows = self.session.execute(select(MedicationExposureV2Record)).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        return sorted(
            (
                exposure
                for exposure in contracts
                if exposure.authority.review_episode_id == review_episode_id
            ),
            key=lambda exposure: (exposure.created_at, exposure.exposure_id),
        )

    def list_exposure_fact_links(self, fact_ids: Sequence[str]) -> list[tuple[str, str]]:
        """一次查出 ``(exposure_id, fact_id)``，禁止按事实 N+1。"""
        unique_ids = sorted(set(fact_ids))
        if not unique_ids:
            return []
        rows = self.session.execute(
            select(ExposureFactLinkRecord.exposure_id, ExposureFactLinkRecord.fact_id)
            .where(ExposureFactLinkRecord.fact_id.in_(unique_ids))
            .order_by(ExposureFactLinkRecord.exposure_id, ExposureFactLinkRecord.fact_id)
        ).all()
        return [(row[0], row[1]) for row in rows]

    def list_exposure_ids_for_facts(self, fact_ids: Sequence[str]) -> list[str]:
        """事实 -> 引用它的暴露（``exposure_fact_links.fact_id`` 反向索引）。"""
        return sorted(
            {exposure_id for exposure_id, _fact_id in self.list_exposure_fact_links(fact_ids)}
        )

    def _decode_record(
        self,
        row: MedicationExposureV2Record,
        *,
        locator_ids: list[str] | None = None,
        fact_ids: list[str] | None = None,
    ) -> MedicationExposureV2:
        contract = decode_contract(
            MedicationExposureV2, row.payload_json, row.payload_sha256
        )
        payload = json.loads(row.payload_json)
        _check_tolerant_mirrors(
            "MedicationExposureV2",
            row,
            payload,
            {
                "exposure_id": "exposure_id",
                "run_id": "run_id",
                "gate_id": "gate_id",
                "medication_name": "medication_name",
                "category": "category",
                "indication": "indication",
                "dose": "dose",
                "unit": "unit",
                "frequency": "frequency",
                "route": "route",
                "duration_status": "duration_status",
                "record_time": "record_time",
                "source_strength": "source_strength",
                "stable_identity": "stable_identity",
                "revision": "revision",
                "created_at": "created_at",
                "start_precision": "start_range.precision",
                "start_lower_bound": "start_range.lower_bound",
                "start_upper_bound": "start_range.upper_bound",
                "start_source_text": "start_range.source_text",
                "end_precision": "end_range.precision",
                "end_lower_bound": "end_range.lower_bound",
                "end_upper_bound": "end_range.upper_bound",
                "end_source_text": "end_range.source_text",
                "project_id": "authority.project_id",
                "subject_id": "authority.subject_id",
                "review_episode_id": "authority.review_episode_id",
                "episode_revision": "authority.episode_revision",
                "protocol_version_id": "authority.protocol_version_id",
                "rule_set_id": "authority.rule_set_id",
                "rule_set_revision": "authority.rule_set_revision",
                "evidence_snapshot_v2_id": "authority.evidence_snapshot_v2_id",
                "complete_processing_revision_id": "authority.complete_processing_revision_id",
            },
        )
        self._assert_link_mirror(
            "exposure",
            row.exposure_id,
            payload["locator_ids"],
            locator_ids=locator_ids,
        )
        if fact_ids is None:
            fact_rows = self.session.execute(
                select(ExposureFactLinkRecord)
                .where(ExposureFactLinkRecord.exposure_id == row.exposure_id)
                .order_by(ExposureFactLinkRecord.position)
            ).scalars().all()
            fact_ids = [link.fact_id for link in fact_rows]
        if fact_ids != payload["fact_ids"]:
            raise PersistedContractInvalid(
                f"exposure {row.exposure_id} 事实链接与 payload 不一致，拒绝还原合同"
            )
        return contract.model_copy(
            update={"fact_ids": fact_ids, "locator_ids": payload["locator_ids"]}
        )


class ClinicalConflictGroupV2Repository(_PublishMixin):
    """未解决冲突组：同类成员共享权威元组，定位属于成员闭包，不自动择优。"""

    def __init__(
        self,
        session: Session,
        *,
        authority_validator: FactAuthorityValidator | None = None,
        complete_revision: Any | None = None,
    ) -> None:
        self.session = session
        self._authority = authority_validator or FactAuthorityValidator(session)
        self._complete_revision = complete_revision

    def create(self, group: ClinicalConflictGroupV2) -> ClinicalConflictGroupV2:
        origin_run = group.run_id
        if group.source_revision_of is not None:
            from app.storage.source_conflict_successors import validate_conflict_successor
            origin_run = validate_conflict_successor(self.session, group, self)
        candidate = self._validate_common(
            group.authority, origin_run, group.gate_id, group.locator_ids, None
        )
        members = self._load_members(group)
        if any(member.authority != group.authority for member in members):
            raise FactCrossEntityError("冲突组成员不属于同一不可变权威元组")
        gate_repository = FactGateResultRepository(self.session)
        member_candidate_ids = sorted(
            {
                candidate_id
                for member in members
                for candidate_id in (
                    member.source_candidate_ids
                    or [gate_repository.get(member.gate_id).candidate_id]
                )
            }
        )
        if candidate.candidate_id not in member_candidate_ids:
            raise FactCrossEntityError(
                f"冲突组 {group.conflict_group_id} 的最终门禁候选不属于其成员"
            )
        locator_closure = {
            locator_id for member in members for locator_id in member.locator_ids
        }
        outside = sorted(set(group.locator_ids) - locator_closure)
        if outside:
            raise FactLocatorReferenceError(
                f"冲突组定位 {outside} 不属于其成员实体的定位闭包"
            )
        payload_json, payload_sha256 = encode_contract(group)
        row = ClinicalConflictGroupV2Record(
            conflict_group_id=group.conflict_group_id,
            run_id=group.run_id,
            gate_id=group.gate_id,
            member_kind=group.member_kind,
            resolution_revision=group.resolution_revision,
            created_at=to_utc_naive(group.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            **_authority_columns(group.authority),
        )
        self.session.add(row)
        _flush_guarded(self.session)
        for position, fact_id in enumerate(group.fact_ids, start=1):
            self.session.add(
                ClinicalConflictMemberV2Record(
                    conflict_group_id=group.conflict_group_id,
                    position=position,
                    fact_id=fact_id,
                )
            )
        for position, event_id in enumerate(group.event_ids, start=1):
            self.session.add(
                ClinicalConflictEventMemberV2Record(
                    conflict_group_id=group.conflict_group_id,
                    position=position,
                    event_id=event_id,
                )
            )
        for position, exposure_id in enumerate(group.exposure_ids, start=1):
            self.session.add(
                ClinicalConflictExposureMemberV2Record(
                    conflict_group_id=group.conflict_group_id,
                    position=position,
                    exposure_id=exposure_id,
                )
            )
        self._write_locator_links(
            "conflict", group.conflict_group_id, group.locator_ids
        )
        return group

    def _load_members(self, group: ClinicalConflictGroupV2) -> list[Any]:
        if group.member_kind == "fact":
            repository = ClinicalFactV2Repository(self.session)
            return [repository.get(member_id) for member_id in group.fact_ids]
        if group.member_kind == "event":
            repository = ClinicalEventV2Repository(self.session)
            return [repository.get(member_id) for member_id in group.event_ids]
        repository = MedicationExposureV2Repository(self.session)
        return [repository.get(member_id) for member_id in group.exposure_ids]

    def get(self, conflict_group_id: str) -> ClinicalConflictGroupV2:
        row = _get_required(
            self.session,
            ClinicalConflictGroupV2Record,
            conflict_group_id,
            "ClinicalConflictGroupV2",
        )
        return self._decode_record(row)

    def list_for_authority(self, authority: FactAuthority) -> list[ClinicalConflictGroupV2]:
        rows = self.session.execute(
            select(ClinicalConflictGroupV2Record).where(
                *authority_column_filters(ClinicalConflictGroupV2Record, authority)
            )
        ).scalars().all()
        group_ids = [row.conflict_group_id for row in rows]
        locators = prefetch_locator_link_ids(self.session, "conflict", group_ids)
        fact_ids = _prefetch_conflict_member_ids(
            self.session, ClinicalConflictMemberV2Record, "fact_id", group_ids
        )
        event_ids = _prefetch_conflict_member_ids(
            self.session, ClinicalConflictEventMemberV2Record, "event_id", group_ids
        )
        exposure_ids = _prefetch_conflict_member_ids(
            self.session,
            ClinicalConflictExposureMemberV2Record,
            "exposure_id",
            group_ids,
        )
        contracts = [
            self._decode_record(
                row,
                locator_ids=locators[row.conflict_group_id],
                fact_ids=fact_ids[row.conflict_group_id],
                event_ids=event_ids[row.conflict_group_id],
                exposure_ids=exposure_ids[row.conflict_group_id],
            )
            for row in rows
        ]
        return sorted(
            (item for item in contracts if item.authority == authority),
            key=lambda item: (item.created_at, item.conflict_group_id),
        )

    def list_by_episode(self, review_episode_id: str) -> list[ClinicalConflictGroupV2]:
        rows = self.session.execute(select(ClinicalConflictGroupV2Record)).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        return sorted(
            (
                group
                for group in contracts
                if group.authority.review_episode_id == review_episode_id
            ),
            key=lambda group: (group.created_at, group.conflict_group_id),
        )

    def list_group_ids_for_members(
        self, member_kind: str, member_ids: Sequence[str]
    ) -> list[str]:
        """冲突成员 -> 冲突组（类型化成员表反向索引）。"""
        unique_ids = sorted(set(member_ids))
        if not unique_ids:
            return []
        table_and_column = {
            "fact": (ClinicalConflictMemberV2Record, ClinicalConflictMemberV2Record.fact_id),
            "event": (
                ClinicalConflictEventMemberV2Record,
                ClinicalConflictEventMemberV2Record.event_id,
            ),
            "exposure": (
                ClinicalConflictExposureMemberV2Record,
                ClinicalConflictExposureMemberV2Record.exposure_id,
            ),
        }.get(member_kind)
        if table_and_column is None:
            raise Phase5RepositoryError(f"不支持的冲突成员类型 {member_kind}")
        table, column = table_and_column
        rows = self.session.execute(
            select(table.conflict_group_id)
            .where(column.in_(unique_ids))
            .distinct()
            .order_by(table.conflict_group_id)
        ).all()
        return [row[0] for row in rows]

    def _decode_record(
        self,
        row: ClinicalConflictGroupV2Record,
        *,
        locator_ids: list[str] | None = None,
        fact_ids: list[str] | None = None,
        event_ids: list[str] | None = None,
        exposure_ids: list[str] | None = None,
    ) -> ClinicalConflictGroupV2:
        contract = decode_contract(
            ClinicalConflictGroupV2, row.payload_json, row.payload_sha256
        )
        payload = json.loads(row.payload_json)
        _check_tolerant_mirrors(
            "ClinicalConflictGroupV2",
            row,
            payload,
            {
                "conflict_group_id": "conflict_group_id",
                "run_id": "run_id",
                "gate_id": "gate_id",
                "resolution_revision": "resolution_revision",
                "created_at": "created_at",
                "project_id": "authority.project_id",
                "subject_id": "authority.subject_id",
                "review_episode_id": "authority.review_episode_id",
                "episode_revision": "authority.episode_revision",
                "protocol_version_id": "authority.protocol_version_id",
                "rule_set_id": "authority.rule_set_id",
                "rule_set_revision": "authority.rule_set_revision",
                "evidence_snapshot_v2_id": "authority.evidence_snapshot_v2_id",
                "complete_processing_revision_id": "authority.complete_processing_revision_id",
            },
        )
        if row.member_kind != contract.member_kind:
            raise PersistedContractInvalid(
                f"ClinicalConflictGroupV2 列 member_kind 与已验证合同不一致，拒绝还原合同"
            )
        self._assert_link_mirror(
            "conflict",
            row.conflict_group_id,
            payload["locator_ids"],
            locator_ids=locator_ids,
        )
        if fact_ids is None:
            member_rows = self.session.execute(
                select(ClinicalConflictMemberV2Record)
                .where(
                    ClinicalConflictMemberV2Record.conflict_group_id
                    == row.conflict_group_id
                )
                .order_by(ClinicalConflictMemberV2Record.position)
            ).scalars().all()
            fact_ids = [m.fact_id for m in member_rows]
        if event_ids is None:
            event_rows = self.session.execute(
                select(ClinicalConflictEventMemberV2Record)
                .where(
                    ClinicalConflictEventMemberV2Record.conflict_group_id
                    == row.conflict_group_id
                )
                .order_by(ClinicalConflictEventMemberV2Record.position)
            ).scalars().all()
            event_ids = [m.event_id for m in event_rows]
        if exposure_ids is None:
            exposure_rows = self.session.execute(
                select(ClinicalConflictExposureMemberV2Record)
                .where(
                    ClinicalConflictExposureMemberV2Record.conflict_group_id
                    == row.conflict_group_id
                )
                .order_by(ClinicalConflictExposureMemberV2Record.position)
            ).scalars().all()
            exposure_ids = [m.exposure_id for m in exposure_rows]
        if (
            fact_ids != payload.get("fact_ids", [])
            or event_ids != payload.get("event_ids", [])
            or exposure_ids != payload.get("exposure_ids", [])
        ):
            raise PersistedContractInvalid(
                f"conflict {row.conflict_group_id} 成员链接与 payload 不一致，拒绝还原合同"
            )
        return contract.model_copy(
            update={
                "fact_ids": fact_ids,
                "event_ids": event_ids,
                "exposure_ids": exposure_ids,
                "locator_ids": payload["locator_ids"],
            }
        )
