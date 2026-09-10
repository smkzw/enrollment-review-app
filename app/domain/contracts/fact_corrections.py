"""Phase 5 Slice 5.7 人工临床事实修订领域合同（纯校验，无存储）。

- ``FactAuthority`` 与定位同权威、理由必填、UTC 时间可回放为北京时间；
- 修订记录保存目标原实体/新实体两侧稳定身份与 revision、旧/新语义快照与哈希、理由、来源 locator、操作者、时间与影响范围；
- 语义快照仅含用户可审阅字段（不含 ID/run/gate/revision/时间戳），经 ``app.domain.publication`` 规范 JSON 序列化；
- 旧/新语义快照必须是 ``snapshot_for_kind`` 的完整字段集，禁止仅含展示片段；
- ``FactCorrectionCommitV2.patient_profile_revision_id`` 指向本次修订生成的不可变档案；
- 影响范围只沿显式 locator / 文档版本 / 实体引用 / FactRuleLink / Profile revision 反向索引传播，
  无法证明时 ``scope_kind='node'`` 并给出回退原因；
- 新稳定身份与旧相同时沿同一 ``(stable_identity, revision)`` 链追加，新链头为 ``target_revision+1``；
  新旧稳定不同时新身份可从 1 新起；分支由仓储唯一约束阻止（单出边/单入边）。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import ConfigDict, Field, model_validator

from app.domain.contracts.facts import ClinicalEventV2, ClinicalFactV2, FactAuthority, MedicationExposureV2
from app.domain.publication import canonical_hash
from .common import ContractModel

__all__ = [
    "ConflictCorrectionOutcome",
    "FactCorrectionCommitV2",
    "FactCorrectionImpactScope",
    "FactCorrectionV2",
    "canonical_json",
    "fact_correction_idempotency_key",
    "fact_semantic_snapshot",
    "event_semantic_snapshot",
    "exposure_semantic_snapshot",
    "snapshot_for_kind",
    "to_beijing_aware",
    "to_beijing_naive",
]

_SHA256 = r"^[0-9a-f]{64}$"
_BEIJING_TZ = ZoneInfo("Asia/Shanghai")

# 语义快照必须是 snapshot_for_kind 产出的完整字段集，禁止仅含展示片段（如只有 value）。
_FACT_SNAPSHOT_KEYS = frozenset(
    {
        "kind",
        "fact_type",
        "profile_lane",
        "polarity",
        "asserted_object",
        "value",
        "unit",
        "date_range",
        "source_strength",
        "assertion_object",
        "assertion_text",
        "supported_requirement_ids",
    }
)
_EVENT_SNAPSHOT_KEYS = frozenset(
    {
        "kind",
        "event_type",
        "profile_lane",
        "referenced_fact_objects",
        "start_range",
        "end_range",
        "duration_status",
        "source_strength",
    }
)
_EXPOSURE_SNAPSHOT_KEYS = frozenset(
    {
        "kind",
        "medication_name",
        "category",
        "indication",
        "dose",
        "unit",
        "frequency",
        "route",
        "start_range",
        "end_range",
        "duration_status",
        "source_strength",
    }
)
_SNAPSHOT_KEYS_BY_KIND = {
    "fact": _FACT_SNAPSHOT_KEYS,
    "event": _EVENT_SNAPSHOT_KEYS,
    "exposure": _EXPOSURE_SNAPSHOT_KEYS,
}


def _require_utc(value: datetime, field_name: str) -> None:
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")


def _require_sorted_unique(values: list[str], label: str) -> None:
    if any(value.strip() == "" for value in values):
        raise ValueError(f"{label} 不得包含空 ID")
    if values != sorted(set(values)):
        raise ValueError(f"{label} 必须按 ID 排序且不得重复")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _snapshot_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_canonical_snapshot(text: str, *, target_kind: str, label: str) -> dict:
    """Parse one user-facing snapshot and enforce its stored representation.

    The correction record keeps the exact JSON text so a reviewer can replay the
    old/new values byte-for-byte.  Accepting semantically equivalent but
    differently formatted JSON would make the stored hash and audit display
    depend on the caller, so the domain contract owns this canonicalization
    check instead of leaving it to the repository.
    """

    def reject_nonfinite(token: str) -> None:
        raise ValueError(token)

    try:
        value = json.loads(text, parse_constant=reject_nonfinite)
    except Exception as exc:
        raise ValueError(f"{label}快照 JSON 必须为有效 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label}快照 JSON 必须是对象")
    if value.get("kind") != target_kind:
        raise ValueError(f"{label}快照类型必须为 {target_kind}")
    expected_keys = _SNAPSHOT_KEYS_BY_KIND.get(target_kind)
    if expected_keys is None:
        raise ValueError(f"不支持的修订目标类型 {target_kind}")
    actual_keys = frozenset(value)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        detail_parts: list[str] = []
        if missing:
            detail_parts.append(f"缺少字段 {', '.join(missing)}")
        if extra:
            detail_parts.append(f"含有多余字段 {', '.join(extra)}")
        raise ValueError(f"{label}快照必须是完整语义快照：{'；'.join(detail_parts)}")
    if canonical_json(value) != text:
        raise ValueError(f"{label}快照 JSON 必须为规范 JSON")
    return value


def fact_semantic_snapshot(fact: ClinicalFactV2) -> dict:
    return {
        "kind": "fact",
        "fact_type": fact.fact_type,
        "profile_lane": fact.profile_lane.value if hasattr(fact.profile_lane, "value") else str(fact.profile_lane),
        "polarity": fact.polarity.value if hasattr(fact.polarity, "value") else str(fact.polarity),
        "asserted_object": fact.asserted_object,
        "value": fact.value,
        "unit": fact.unit,
        "date_range": fact.date_range.model_dump(mode="json") if fact.date_range is not None else None,
        "source_strength": fact.source_strength.value if hasattr(fact.source_strength, "value") else str(fact.source_strength),
        "assertion_object": fact.assertion_basis.asserted_object if fact.assertion_basis else None,
        "assertion_text": fact.assertion_basis.assertion_text if fact.assertion_basis else None,
        "supported_requirement_ids": list(fact.supported_requirement_ids),
    }


def event_semantic_snapshot(event: ClinicalEventV2) -> dict:
    return {
        "kind": "event",
        "event_type": event.event_type,
        "profile_lane": event.profile_lane.value if hasattr(event.profile_lane, "value") else str(event.profile_lane),
        "referenced_fact_objects": event.referenced_fact_objects,
        "start_range": event.start_range.model_dump(mode="json") if event.start_range is not None else None,
        "end_range": event.end_range.model_dump(mode="json") if event.end_range is not None else None,
        "duration_status": event.duration_status.value if hasattr(event.duration_status, "value") else str(event.duration_status),
        "source_strength": event.source_strength.value if hasattr(event.source_strength, "value") else str(event.source_strength),
    }


def exposure_semantic_snapshot(exp: MedicationExposureV2) -> dict:
    return {
        "kind": "exposure",
        "medication_name": exp.medication_name,
        "category": exp.category,
        "indication": exp.indication,
        "dose": exp.dose,
        "unit": exp.unit,
        "frequency": exp.frequency,
        "route": exp.route,
        "start_range": exp.start_range.model_dump(mode="json") if exp.start_range is not None else None,
        "end_range": exp.end_range.model_dump(mode="json") if exp.end_range is not None else None,
        "duration_status": exp.duration_status.value if hasattr(exp.duration_status, "value") else str(exp.duration_status),
        "source_strength": exp.source_strength.value if hasattr(exp.source_strength, "value") else str(exp.source_strength),
    }


def snapshot_for_kind(kind: str, entity: ClinicalFactV2 | ClinicalEventV2 | MedicationExposureV2) -> dict:
    if kind == "fact":
        assert isinstance(entity, ClinicalFactV2)
        return fact_semantic_snapshot(entity)
    if kind == "event":
        assert isinstance(entity, ClinicalEventV2)
        return event_semantic_snapshot(entity)
    if kind == "exposure":
        assert isinstance(entity, MedicationExposureV2)
        return exposure_semantic_snapshot(entity)
    raise ValueError(f"不支持的修订目标类型 {kind}")


def fact_correction_idempotency_key(
    *,
    authority: FactAuthority,
    target_kind: str,
    target_id: str,
    target_stable_identity: str,
    target_revision: int,
    new_entity_id: str,
    new_stable_identity: str,
    new_revision: int,
    old_snapshot_sha256: str,
    new_snapshot_sha256: str,
    reason: str,
    locator_ids: list[str],
    operator_id: str,
) -> str:
    return canonical_hash(
        {
            "idempotency": "fact_correction/v1",
            "authority": authority.model_dump(mode="json"),
            "target_kind": target_kind,
            "target_id": target_id,
            "target_stable_identity": target_stable_identity,
            "target_revision": target_revision,
            "new_entity_id": new_entity_id,
            "new_stable_identity": new_stable_identity,
            "new_revision": new_revision,
            "old_snapshot_sha256": old_snapshot_sha256,
            "new_snapshot_sha256": new_snapshot_sha256,
            "reason": reason.strip(),
            "locator_ids": sorted(locator_ids),
            "operator_id": operator_id,
        }
    )


def to_beijing_aware(value: datetime) -> datetime:
    _require_utc(value, "value")
    return value.astimezone(_BEIJING_TZ)


def to_beijing_naive(value: datetime) -> datetime:
    aware = to_beijing_aware(value)
    return aware.replace(tzinfo=None)


class FactCorrectionImpactScope(ContractModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scope_kind: Literal["local", "node"]
    fallback_reason: str | None = None
    affected_locator_ids: list[str] = Field(default_factory=list)
    affected_document_ids: list[str] = Field(default_factory=list)
    affected_fact_ids: list[str] = Field(default_factory=list)
    affected_event_ids: list[str] = Field(default_factory=list)
    affected_exposure_ids: list[str] = Field(default_factory=list)
    affected_conflict_group_ids: list[str] = Field(default_factory=list)
    affected_rule_link_ids: list[str] = Field(default_factory=list)
    affected_expectation_ids: list[str] = Field(default_factory=list)
    affected_profile_revision_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scope(self) -> "FactCorrectionImpactScope":
        for label, values in [
            ("受影响定位", self.affected_locator_ids),
            ("受影响文档", self.affected_document_ids),
            ("受影响事实", self.affected_fact_ids),
            ("受影响事件", self.affected_event_ids),
            ("受影响暴露", self.affected_exposure_ids),
            ("受影响冲突组", self.affected_conflict_group_ids),
            ("受影响规则索引", self.affected_rule_link_ids),
            ("受影响期望", self.affected_expectation_ids),
            ("受影响 Profile", self.affected_profile_revision_ids),
        ]:
            _require_sorted_unique(values, label)
        if self.scope_kind == "local":
            if self.fallback_reason is not None and self.fallback_reason.strip() != "":
                raise ValueError("局部影响范围不得携带回退原因")
            has_any = any(
                [
                    self.affected_locator_ids,
                    self.affected_document_ids,
                    self.affected_fact_ids,
                    self.affected_event_ids,
                    self.affected_exposure_ids,
                    self.affected_conflict_group_ids,
                    self.affected_rule_link_ids,
                    self.affected_expectation_ids,
                    self.affected_profile_revision_ids,
                ]
            )
            if not has_any:
                raise ValueError("局部影响范围必须包含至少一类受影响集合，无法证明时应使用节点级回退")
        else:
            if self.fallback_reason is None or self.fallback_reason.strip() == "":
                raise ValueError("节点级回退必须给出明确的回退原因")
        return self


class FactCorrectionV2(ContractModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    correction_id: str = Field(min_length=1)
    authority: FactAuthority
    target_kind: Literal["fact", "event", "exposure"]
    target_id: str = Field(min_length=1)
    target_stable_identity: str = Field(pattern=_SHA256)
    new_stable_identity: str = Field(pattern=_SHA256)
    target_revision: int = Field(ge=1)
    new_entity_id: str = Field(min_length=1)
    new_revision: int = Field(ge=1)
    old_snapshot_json: str = Field(min_length=1)
    old_snapshot_sha256: str = Field(pattern=_SHA256)
    new_snapshot_json: str = Field(min_length=1)
    new_snapshot_sha256: str = Field(pattern=_SHA256)
    reason: str = Field(min_length=1)
    locator_ids: list[str] = Field(min_length=1)
    operator_id: str = Field(min_length=1)
    corrected_at: datetime
    created_at: datetime
    impact_scope: FactCorrectionImpactScope
    idempotency_key: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_correction(self) -> "FactCorrectionV2":
        _require_utc(self.corrected_at, "corrected_at")
        _require_utc(self.created_at, "created_at")
        _require_sorted_unique(self.locator_ids, "修订来源定位")
        if self.reason.strip() == "":
            raise ValueError("修订理由不得为空")
        if self.operator_id.strip() == "":
            raise ValueError("修订操作者不得为空")
        if self.old_snapshot_json == self.new_snapshot_json:
            raise ValueError("旧/新语义快照必须不同")
        if self.old_snapshot_sha256 != _snapshot_sha(self.old_snapshot_json):
            raise ValueError("旧快照哈希与快照 JSON 不一致")
        if self.new_snapshot_sha256 != _snapshot_sha(self.new_snapshot_json):
            raise ValueError("新快照哈希与快照 JSON 不一致")
        if self.old_snapshot_sha256 == self.new_snapshot_sha256:
            raise ValueError("旧/新快照哈希必须不同")
        _parse_canonical_snapshot(
            self.old_snapshot_json,
            target_kind=self.target_kind,
            label="旧",
        )
        _parse_canonical_snapshot(
            self.new_snapshot_json,
            target_kind=self.target_kind,
            label="新",
        )
        if self.impact_scope.scope_kind == "local" and not set(self.locator_ids).issubset(
            self.impact_scope.affected_locator_ids
        ):
            raise ValueError("局部影响范围必须包含修订提交引用的全部定位")
        if self.new_entity_id == self.target_id:
            raise ValueError("新实体 ID 不得与目标 ID 相同")
        # 同稳定身份时新 revision 必须为 target+1；不同稳定时允许新起（1 或链头+1 由仓储校验）
        if self.target_stable_identity == self.new_stable_identity:
            if self.new_revision != self.target_revision + 1:
                raise ValueError("同稳定身份时新 revision 必须为目标 revision + 1")
        else:
            if self.new_revision < 1:
                raise ValueError("新 revision 必须 >=1")
            # 不强制 target+1，允许从 1 新起；分支由仓储唯一约束阻止
        expected = fact_correction_idempotency_key(
            authority=self.authority,
            target_kind=self.target_kind,
            target_id=self.target_id,
            target_stable_identity=self.target_stable_identity,
            target_revision=self.target_revision,
            new_entity_id=self.new_entity_id,
            new_stable_identity=self.new_stable_identity,
            new_revision=self.new_revision,
            old_snapshot_sha256=self.old_snapshot_sha256,
            new_snapshot_sha256=self.new_snapshot_sha256,
            reason=self.reason,
            locator_ids=self.locator_ids,
            operator_id=self.operator_id,
        )
        if self.idempotency_key != expected:
            raise ValueError("修订幂等键与权威元组/旧/新快照哈希/理由/定位/操作者不一致")
        return self


class ConflictCorrectionOutcome(ContractModel):
    """一条冲突组在本次修订中的显式谱系：旧组被替代或被解决，绝不改写旧行。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    superseded_conflict_group_id: str = Field(min_length=1)
    successor_conflict_group_id: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "ConflictCorrectionOutcome":
        if (
            self.successor_conflict_group_id is not None
            and self.successor_conflict_group_id == self.superseded_conflict_group_id
        ):
            raise ValueError("冲突组后继不得与被替代组相同")
        return self


class FactCorrectionCommitV2(ContractModel):
    """修订提交栅栏：绑定本次产生的 Profile revision 与冲突谱系，供精确回放。

    ``patient_profile_revision_id`` 只在 ``PatientProfileService.generate`` 之后写入，
    因此指向**本次修订生成**的不可变档案，而不是修订前现行档案。历史回放必须用该
    ID 加载档案与其中的定位/页工件；同一 locator id 跨档案版本页码/摘录不可变。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    correction_id: str = Field(min_length=1)
    authority: FactAuthority
    patient_profile_revision_id: str = Field(min_length=1)
    impact_scope: FactCorrectionImpactScope
    conflict_outcomes: list[ConflictCorrectionOutcome] = Field(default_factory=list)
    created_at: datetime

    @model_validator(mode="after")
    def validate_commit(self) -> "FactCorrectionCommitV2":
        _require_utc(self.created_at, "created_at")
        superseded = [item.superseded_conflict_group_id for item in self.conflict_outcomes]
        if superseded != sorted(set(superseded)):
            raise ValueError("冲突谱系的被替代组必须排序且不得重复")
        successors = [
            item.successor_conflict_group_id
            for item in self.conflict_outcomes
            if item.successor_conflict_group_id is not None
        ]
        if successors != sorted(set(successors)):
            raise ValueError("冲突谱系的后继组必须排序且不得重复")
        expected_order = sorted(
            self.conflict_outcomes,
            key=lambda item: item.superseded_conflict_group_id,
        )
        if list(self.conflict_outcomes) != expected_order:
            raise ValueError("冲突谱系必须按被替代冲突组编号排序")
        return self
