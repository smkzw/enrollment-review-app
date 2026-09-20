"""跨章控制目录发布的不可变版本合同（纯校验：无存储、无模型、无临床判定）。

本模块把「已发布控制目录」（:class:`PublishedProtocolControlCatalog`）与它实际绑定
的正式 ``RuleSet`` 修订、发布 Job/检查点凭据和发布门禁结果冻结成一个内容寻址版本，
供后续资料期望、审核计划与报告共同消费：

- ``publication_id`` 由本合同的规范化 JSON 正文（不含自身）内容寻址派生，调用方
  不需要、也不允许手工拼接：传入身份必须等于派生结果，未传入则自动派生；
- ``workflow_stage_map`` 只做身份命名空间映射：冻结原节点 ID -> 正式
  已由必做项目映射证明的正式节点，绝不按名称、访视或阶段猜配节点；
- 同一 ``RuleSet`` 修订只能有一个已发布目录（目录变化必须发布新的正式规则修订）。

硬边界：

- 本合同不重写目录内容、不改写 ``RuleSet``、不产生任何临床结论，也不做临床评估；
- ``rule_set_sha256`` / ``source_job_payload_sha256`` / ``source_checkpoint_sha256``
  只是内容哈希字段，本模块不验证 Job 与检查点内容——发布服务必须在签发门禁前
  证明任务、检查点与目录来源；
- 存储完整性由 ``ControlCatalogPublicationRepository`` 负责，本模块不做任何 I/O。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain.publication import canonical_hash

from .common import ContractModel
from .protocol_controls import (
    ControlRelationTargetKind,
    PublishedProtocolControlCatalog,
)

__all__ = [
    "CONTROL_CATALOG_PUBLICATION_GATE_NAME",
    "CONTROL_CATALOG_PUBLICATION_ID_PREFIX",
    "ControlCatalogPublication",
    "control_catalog_publication_id",
]

_SHA256 = r"^[0-9a-f]{64}$"

#: 发布身份前缀：目录发布不是官方 IN/EX 编号，也不得伪装为方案控制编号。
CONTROL_CATALOG_PUBLICATION_ID_PREFIX = "control-publication:"

#: 发布门禁名称唯一；发布服务与仓储必须引用同一常量，不得各自拼写字符串。
CONTROL_CATALOG_PUBLICATION_GATE_NAME = "protocol-control-catalog-publication-gate"


def _require_utc(value: datetime, field_name: str) -> None:
    """拒绝 naive 或非 UTC 时间戳（与 Phase 4/5 合同边界一致）。"""
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")


def control_catalog_publication_id(payload: Mapping[str, Any]) -> str:
    """由发布正文的规范化 JSON 形态（忽略 ``publication_id``）派生内容寻址身份。"""
    body = {key: value for key, value in payload.items() if key != "publication_id"}
    return f"{CONTROL_CATALOG_PUBLICATION_ID_PREFIX}{canonical_hash(body)}"


class _ControlCatalogPublicationBody(ContractModel):
    """发布正文（不含身份）：身份派生与正文校验的唯一定义。

    ``ControlCatalogPublication`` 的字段与校验全部来自这里；单独成类只为了让
    「先规范化正文、再按正文派生身份」与「正文校验」使用同一份字段定义，
    避免调用方各自拼装身份。它不是可对外流转的合同，不要直接持久化本类。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["control-catalog/v1"] = "control-catalog/v1"
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    rule_set_sha256: str = Field(pattern=_SHA256)
    source_job_id: str = Field(min_length=1)
    source_job_payload_sha256: str = Field(pattern=_SHA256)
    source_checkpoint_id: str = Field(min_length=1)
    source_checkpoint_sha256: str = Field(pattern=_SHA256)
    catalog: PublishedProtocolControlCatalog
    #: 冻结原节点 ID -> 正式命名空间节点 ID；值必须逐字等于
    #: 当前规则修订前缀。两条来源链的原始节点 ID 不相同，由发布服务验证桥接。
    workflow_stage_map: dict[str, str]
    gate_result_id: str = Field(min_length=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        _require_utc(value, "created_at")
        return value

    @model_validator(mode="after")
    def validate_body(self) -> "_ControlCatalogPublicationBody":
        if self.protocol_version_id != self.catalog.protocol_version_id:
            raise ValueError("控制目录发布必须绑定目录自身的方案版本")
        self._validate_workflow_stage_map()
        return self

    def _validate_workflow_stage_map(self) -> None:
        """映射必须逐节点命名空间化、目标唯一，并覆盖目录引用的全部审核节点。"""
        mapping = self.workflow_stage_map
        for source_id, target_id in mapping.items():
            if not source_id.strip() or not target_id.strip():
                raise ValueError("审核节点映射不得包含空 ID")
            prefix = f"{self.rule_set_id}:{self.rule_set_revision}:"
            if not target_id.startswith(prefix) or not target_id[len(prefix):].strip():
                raise ValueError(
                    "审核节点映射目标必须属于当前正式规则修订"
                )
        if len(set(mapping.values())) != len(mapping):
            raise ValueError("审核节点映射目标不得重复")

        referenced: set[str] = set()
        for control in self.catalog.controls:
            for binding in control.review_node_bindings:
                referenced.add(binding.workflow_stage_id)
            for evidence in control.minimum_evidence:
                referenced.update(evidence.workflow_stage_ids)
            for relation in control.cross_source_relations:
                for target_kind, target_id in (
                    (relation.left_target_kind, relation.left_target_id),
                    (relation.right_target_kind, relation.right_target_id),
                ):
                    if target_kind == ControlRelationTargetKind.WORKFLOW_STAGE:
                        referenced.add(target_id)
                if relation.affected_workflow_stage_id is not None:
                    referenced.add(relation.affected_workflow_stage_id)
        unmapped = sorted(referenced - set(mapping))
        if unmapped:
            raise ValueError(
                "控制目录引用的审核节点未映射到正式节点：" + ",".join(unmapped)
            )


class ControlCatalogPublication(_ControlCatalogPublicationBody):
    """一次正式发布的跨章控制目录版本；目录内容本身不被本模块修改。

    ``publication_id`` 是内容寻址身份：由正文规范化 JSON（不含身份）派生。调用方
    可不传身份（自动派生），若传入则必须与派生结果一致，绝不接受手工指定的身份。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    publication_id: str = Field(pattern=r"^control-publication:[0-9a-f]{64}$")

    @model_validator(mode="before")
    @classmethod
    def _bind_publication_id(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)
        provided = payload.pop("publication_id", None)
        canonical = _ControlCatalogPublicationBody.model_validate(
            payload
        ).model_dump(mode="json")
        derived = control_catalog_publication_id(canonical)
        if provided is not None and provided != derived:
            raise ValueError(
                "控制目录发布身份必须由正文内容寻址派生，不能手工指定"
            )
        return {**canonical, "publication_id": derived}
