"""修订提交栅栏仓储：Profile 精确回放与冲突谱系。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.fact_corrections import (
    FactCorrectionCommitV2,
)
from app.domain.contracts.facts import FactAuthority
from app.domain.publication import canonical_hash
from app.domain.contracts.patient_profile_v2 import profile_items
from app.storage.codecs import (
    PersistedContractInvalid,
    decode_contract,
    encode_contract,
    to_utc_naive,
)
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.fact_correction_repository import FactCorrectionRepository
from app.storage.fact_repositories import ClinicalConflictGroupV2Repository
from app.storage.facts_models import (
    FactCorrectionCommitRecord,
    FactCorrectionConflictOutcomeRecord,
)
from app.storage.patient_profile_repository import PatientProfileRevisionRepository
from app.storage.repositories import (
    InvalidReferenceError,
    NotFoundError,
    RepositoryError,
    _flush_guarded,
    _get_required,
)

__all__ = ["FactCorrectionCommitRepository", "FactCorrectionCommitError"]


class FactCorrectionCommitError(RepositoryError):
    """提交栅栏校验失败。"""


def _authority_columns(authority: FactAuthority) -> dict[str, Any]:
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


def _outcome_id(correction_id: str, superseded_id: str) -> str:
    return "fcorr-out-" + canonical_hash(
        {"correction_id": correction_id, "superseded": superseded_id}
    )[:24]


def _payload_outcome_pairs(
    contract: FactCorrectionCommitV2,
) -> list[tuple[str, str | None]]:
    return [
        (item.superseded_conflict_group_id, item.successor_conflict_group_id)
        for item in contract.conflict_outcomes
    ]


def _typed_outcome_pairs(
    session: Session, correction_id: str
) -> list[tuple[str, str | None]]:
    rows = session.execute(
        select(FactCorrectionConflictOutcomeRecord).where(
            FactCorrectionConflictOutcomeRecord.correction_id == correction_id
        )
    ).scalars().all()
    return sorted(
        (row.superseded_conflict_group_id, row.successor_conflict_group_id)
        for row in rows
    )


def _decode_record(
    session: Session, record: FactCorrectionCommitRecord
) -> FactCorrectionCommitV2:
    contract = decode_contract(
        FactCorrectionCommitV2, record.payload_json, record.payload_sha256
    )
    canonical_payload_json, canonical_payload_sha256 = encode_contract(contract)
    if (
        record.payload_json != canonical_payload_json
        or record.payload_sha256 != canonical_payload_sha256
    ):
        raise PersistedContractInvalid(
            f"修订提交 {contract.correction_id} payload 不是规范 JSON，拒绝还原合同"
        )
    mirrors = {
        "correction_id": contract.correction_id,
        "patient_profile_revision_id": contract.patient_profile_revision_id,
        "impact_scope_kind": contract.impact_scope.scope_kind,
        "impact_fallback_reason": contract.impact_scope.fallback_reason,
        "impact_scope_json": contract.impact_scope.model_dump(mode="json"),
        "superseded_conflict_group_ids_json": [
            item.superseded_conflict_group_id for item in contract.conflict_outcomes
        ],
        "successor_conflict_group_ids_json": sorted(
            {
                item.successor_conflict_group_id
                for item in contract.conflict_outcomes
                if item.successor_conflict_group_id is not None
            }
        ),
    }
    for col, value in _authority_columns(contract.authority).items():
        if getattr(record, col) != value:
            raise PersistedContractInvalid(
                f"修订提交 {contract.correction_id} 权威列 {col} 与 payload 不一致"
            )
    for col, expected in mirrors.items():
        actual = getattr(record, col)
        if actual != expected:
            raise PersistedContractInvalid(
                f"修订提交 {contract.correction_id} 列 {col} 与 payload 不一致"
            )
    if record.created_at != to_utc_naive(contract.created_at):
        raise PersistedContractInvalid(
            f"修订提交 {contract.correction_id} created_at 与 payload 不一致"
        )
    typed = _typed_outcome_pairs(session, contract.correction_id)
    payload = sorted(_payload_outcome_pairs(contract))
    if typed != payload:
        raise PersistedContractInvalid(
            f"修订提交 {contract.correction_id} 类型化冲突谱系行与 payload 不一致"
        )
    return contract


class FactCorrectionCommitRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self._authority = FactAuthorityValidator(session)

    def _require_same_authority(self, contract: FactCorrectionCommitV2) -> None:
        try:
            parent_contract = FactCorrectionRepository(self.session).get(
                contract.correction_id
            )
        except (NotFoundError, InvalidReferenceError) as exc:
            raise FactCorrectionCommitError(
                f"修订 {contract.correction_id} 不存在，不能写提交栅栏"
            ) from exc
        if parent_contract.authority != contract.authority:
            raise FactCorrectionCommitError(
                f"修订提交 {contract.correction_id} 与父修订不属于同一权威元组"
            )
        try:
            profile = PatientProfileRevisionRepository(self.session).get(
                contract.patient_profile_revision_id
            )
        except (NotFoundError, InvalidReferenceError) as exc:
            raise FactCorrectionCommitError(
                f"修订提交 {contract.correction_id} 引用的病历档案不存在"
            ) from exc
        if profile.authority != contract.authority:
            raise FactCorrectionCommitError(
                f"修订提交 {contract.correction_id} 引用的病历档案不属于同一权威元组"
            )
        if profile.authority.review_episode_id != contract.authority.review_episode_id:
            raise FactCorrectionCommitError(
                f"修订提交 {contract.correction_id} 引用的病历档案不属于同一审核节点"
            )
        # patient_profile_revision_id 必须是本次修订生成的档案（含新实体与提交定位）。
        from app.domain.contracts.patient_profile_v2 import ProfileItemKind

        kind_map = {
            "fact": ProfileItemKind.FACT,
            "event": ProfileItemKind.EVENT,
            "exposure": ProfileItemKind.EXPOSURE,
        }
        expected_kind = kind_map[parent_contract.target_kind]
        matches = [
            item
            for item in profile_items(profile)
            if item.kind == expected_kind and item.source_id == parent_contract.new_entity_id
        ]
        if not matches:
            raise FactCorrectionCommitError(
                f"修订提交 {contract.correction_id} 引用的病历档案未包含本次新实体，"
                "不能把修订前档案当作提交结果"
            )
        if sorted(set(parent_contract.locator_ids) - set(matches[0].locator_ids)):
            raise FactCorrectionCommitError(
                f"修订提交 {contract.correction_id} 引用的病历档案未绑定提交定位"
            )
        conflicts = ClinicalConflictGroupV2Repository(self.session)
        for item in contract.conflict_outcomes:
            try:
                superseded = conflicts.get(item.superseded_conflict_group_id)
            except (NotFoundError, InvalidReferenceError) as exc:
                raise FactCorrectionCommitError(
                    f"修订提交引用的被替代冲突组 {item.superseded_conflict_group_id} 不存在"
                ) from exc
            if superseded.authority != contract.authority:
                raise FactCorrectionCommitError(
                    f"被替代冲突组 {item.superseded_conflict_group_id} 不属于同一权威元组"
                )
            if item.successor_conflict_group_id is None:
                continue
            try:
                successor = conflicts.get(item.successor_conflict_group_id)
            except (NotFoundError, InvalidReferenceError) as exc:
                raise FactCorrectionCommitError(
                    f"修订提交引用的后继冲突组 {item.successor_conflict_group_id} 不存在"
                ) from exc
            if successor.authority != contract.authority:
                raise FactCorrectionCommitError(
                    f"后继冲突组 {item.successor_conflict_group_id} 不属于同一权威元组"
                )

    def _decode_and_validate(
        self, record: FactCorrectionCommitRecord
    ) -> FactCorrectionCommitV2:
        contract = _decode_record(self.session, record)
        self._require_same_authority(contract)
        return contract

    def create(self, contract: FactCorrectionCommitV2) -> FactCorrectionCommitV2:
        existing = self.session.get(FactCorrectionCommitRecord, contract.correction_id)
        if existing is not None:
            decoded = self._decode_and_validate(existing)
            if decoded != contract:
                raise FactCorrectionCommitError(
                    f"修订提交 {contract.correction_id} 已存在且内容不一致"
                )
            return decoded
        self._require_same_authority(contract)
        self._authority.validate(contract.authority)
        payload_json, payload_sha256 = encode_contract(contract)
        record = FactCorrectionCommitRecord(
            correction_id=contract.correction_id,
            patient_profile_revision_id=contract.patient_profile_revision_id,
            impact_scope_kind=contract.impact_scope.scope_kind,
            impact_fallback_reason=contract.impact_scope.fallback_reason,
            impact_scope_json=contract.impact_scope.model_dump(mode="json"),
            superseded_conflict_group_ids_json=[
                item.superseded_conflict_group_id for item in contract.conflict_outcomes
            ],
            successor_conflict_group_ids_json=sorted(
                {
                    item.successor_conflict_group_id
                    for item in contract.conflict_outcomes
                    if item.successor_conflict_group_id is not None
                }
            ),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            created_at=to_utc_naive(contract.created_at),
            **_authority_columns(contract.authority),
        )
        self.session.add(record)
        _flush_guarded(self.session)
        for item in contract.conflict_outcomes:
            self.session.add(
                FactCorrectionConflictOutcomeRecord(
                    outcome_id=_outcome_id(
                        contract.correction_id, item.superseded_conflict_group_id
                    ),
                    correction_id=contract.correction_id,
                    superseded_conflict_group_id=item.superseded_conflict_group_id,
                    successor_conflict_group_id=item.successor_conflict_group_id,
                )
            )
        _flush_guarded(self.session)
        return self._decode_and_validate(record)

    def get(self, correction_id: str) -> FactCorrectionCommitV2:
        record = _get_required(
            self.session,
            FactCorrectionCommitRecord,
            correction_id,
            "修订提交栅栏",
        )
        return self._decode_and_validate(record)

    def get_optional(self, correction_id: str) -> FactCorrectionCommitV2 | None:
        record = self.session.get(FactCorrectionCommitRecord, correction_id)
        if record is None:
            return None
        return self._decode_and_validate(record)

    def list_by_authority(self, authority: FactAuthority) -> list[FactCorrectionCommitV2]:
        rows = self.session.execute(select(FactCorrectionCommitRecord)).scalars().all()
        contracts = [self._decode_and_validate(row) for row in rows]
        return sorted(
            [item for item in contracts if item.authority == authority],
            key=lambda item: (item.created_at, item.correction_id),
        )

    def list_by_review_episode(
        self, review_episode_id: str
    ) -> list[FactCorrectionCommitV2]:
        """读取审核节点全部提交栅栏；逐条仍按自身冻结权威校验。"""
        rows = self.session.execute(select(FactCorrectionCommitRecord)).scalars().all()
        contracts = [self._decode_and_validate(row) for row in rows]
        filtered = [
            item
            for item in contracts
            if item.authority.review_episode_id == review_episode_id
        ]
        return sorted(filtered, key=lambda item: (item.created_at, item.correction_id))

    def superseded_conflict_ids(self, authority: FactAuthority) -> set[str]:
        ids: set[str] = set()
        for commit in self.list_by_authority(authority):
            ids.update(
                item.superseded_conflict_group_id for item in commit.conflict_outcomes
            )
        return ids
