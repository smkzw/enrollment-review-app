"""跨章控制目录发布的追加写仓储：正文规范序列化 + 镜像校验 + 存储完整性核对。

职责边界（与 ``review_context_repository`` 相同的分层）：

- 本仓储只证明「已落库的发布行与它引用的 RuleSet 修订、正式审核节点、发布门禁凭据
  彼此一致」，即不可变存储完整性；
- 任务/检查点内容、目录来源与临床结论由发布服务在签发门禁前自行证明，本仓储不
  验证它们，也不得据此替代发布门禁；
- 调用方持有事务，本模块只 ``flush``，不 ``commit``。
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.control_catalog_publication import (
    CONTROL_CATALOG_PUBLICATION_GATE_NAME,
    ControlCatalogPublication,
)
from app.domain.contracts.enums import GateOutcome, ReviewStage
from app.domain.contracts.rules import WorkflowStage
from app.domain.publication import canonical_hash
from app.storage.codecs import check_column_mirrors, decode_contract
from app.storage.control_catalog_models import ProtocolControlCatalogRecord
from app.storage.models import WorkflowStageRecord
from app.storage.repositories import (
    GATE_RESULT_CONFIG,
    WORKFLOW_STAGE_CONFIG,
    AppendRepository,
    DuplicateRecordError,
    InvalidReferenceError,
    ScopeViolationError,
    _config,
    get_rule_set,
)

__all__ = ["ControlCatalogPublicationRepository"]

_CONTROL_CATALOG_PUBLICATION_CONFIG = _config(
    ProtocolControlCatalogRecord,
    ControlCatalogPublication,
    {
        "publication_id": "publication_id",
        "project_id": "project_id",
        "protocol_version_id": "protocol_version_id",
        "rule_set_id": "rule_set_id",
        "rule_set_revision": "rule_set_revision",
        "catalog_id": "catalog.catalog_id",
        "source_job_id": "source_job_id",
        "source_checkpoint_id": "source_checkpoint_id",
        "gate_result_id": "gate_result_id",
    },
    created_at_key="created_at",
    mirrors={
        "project_id": "project_id",
        "protocol_version_id": "protocol_version_id",
        "rule_set_id": "rule_set_id",
        "rule_set_revision": "rule_set_revision",
        "catalog_id": "catalog.catalog_id",
        "source_job_id": "source_job_id",
        "source_checkpoint_id": "source_checkpoint_id",
        "gate_result_id": "gate_result_id",
    },
)


class ControlCatalogPublicationRepository:
    """同一 RuleSet 修订至多一个已发布控制目录；同内容重复保存返回原记录。"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = AppendRepository(
            session, _CONTROL_CATALOG_PUBLICATION_CONFIG
        )

    def get(self, publication_id: str) -> ControlCatalogPublication:
        publication = self._repository.get(publication_id)
        self._verify_persisted_basis(publication)
        return publication

    def get_for_rule_set(
        self, rule_set_id: str, rule_set_revision: int
    ) -> ControlCatalogPublication | None:
        """按正式规则修订读取已发布目录；列过滤后仍执行完整正文/镜像校验。"""
        publication_id = self._session.scalar(
            select(ProtocolControlCatalogRecord.publication_id).where(
                ProtocolControlCatalogRecord.rule_set_id == rule_set_id,
                ProtocolControlCatalogRecord.rule_set_revision == rule_set_revision,
            )
        )
        if publication_id is None:
            return None
        return self.get(publication_id)

    def save(
        self, publication: ControlCatalogPublication
    ) -> ControlCatalogPublication:
        """追加写入一次发布；同内容幂等，同规则修订的第二份目录一律拒绝。"""
        validated = ControlCatalogPublication.model_validate(
            publication.model_dump(mode="json")
        )
        existing = self._repository.get_or_none(validated.publication_id)
        if existing is not None:
            if canonical_hash(existing.model_dump(mode="json")) != canonical_hash(
                validated.model_dump(mode="json")
            ):
                raise DuplicateRecordError(
                    "同一控制目录发布身份不能替换为不同内容"
                )
            self._verify_persisted_basis(existing)
            return existing
        self._verify_persisted_basis(validated)
        bound = self.get_for_rule_set(
            validated.rule_set_id, validated.rule_set_revision
        )
        if bound is not None:
            raise DuplicateRecordError(
                f"RuleSet {validated.rule_set_id} revision "
                f"{validated.rule_set_revision} 已有控制目录发布，"
                "目录变化必须发布新的正式规则修订"
            )
        self._repository.save(validated)
        return validated

    # -- 存储完整性 ---------------------------------------------------------

    def _verify_persisted_basis(self, publication: ControlCatalogPublication) -> None:
        """核对发布行引用的规则修订、正式审核节点与发布门禁凭据。"""
        rule_set = get_rule_set(
            self._session, publication.rule_set_id, publication.rule_set_revision
        )
        if canonical_hash(rule_set.model_dump(mode="json")) != publication.rule_set_sha256:
            raise ScopeViolationError(
                "控制目录发布绑定的正式规则修订内容与冻结哈希不一致"
            )
        catalog = publication.catalog
        if rule_set.protocol_version_id != publication.protocol_version_id:
            raise ScopeViolationError("控制目录发布的方案版本与正式规则修订不一致")
        if rule_set.study_phase != catalog.study_phase:
            raise ScopeViolationError("控制目录发布的期别与正式规则修订不一致")
        self._verify_workflow_stages(publication)
        self._verify_gate(publication)

    def _verify_workflow_stages(self, publication: ControlCatalogPublication) -> None:
        """映射目标必须是同一命名空间下的既有正式节点，且阶段与目录绑定一致。"""
        catalog = publication.catalog
        mapping = publication.workflow_stage_map
        expected_stage: dict[str, ReviewStage] = {}
        for control in catalog.controls:
            for binding in control.review_node_bindings:
                known = expected_stage.setdefault(
                    binding.workflow_stage_id, binding.review_stage
                )
                if known != binding.review_stage:
                    raise ScopeViolationError(
                        "同一审核节点在控制目录内绑定了互相冲突的阶段"
                    )
        target_ids = sorted(set(mapping.values()))
        rows = (
            self._session.execute(
                select(WorkflowStageRecord).where(
                    WorkflowStageRecord.workflow_stage_id.in_(target_ids)
                )
            ).scalars().all()
            if target_ids
            else []
        )
        by_id = {row.workflow_stage_id: row for row in rows}
        missing = sorted(set(mapping.values()) - set(by_id))
        if missing:
            raise InvalidReferenceError(
                "控制目录发布引用的正式审核节点不存在：" + ",".join(missing)
            )
        for source_id, target_id in sorted(mapping.items()):
            row = by_id[target_id]
            payload = json.loads(row.payload_json)
            stage = decode_contract(WorkflowStage, row.payload_json, row.payload_sha256)
            check_column_mirrors(
                WORKFLOW_STAGE_CONFIG.entity_name,
                row,
                payload,
                WORKFLOW_STAGE_CONFIG.mirrors,
            )
            if stage.workflow_stage_id != target_id:
                raise ScopeViolationError("正式审核节点的正文身份与映射目标不一致")
            if row.protocol_version_id != publication.protocol_version_id:
                raise ScopeViolationError(
                    f"正式审核节点 {target_id} 不属于本次发布的方案版本"
                )
            if row.study_phase is not None and row.study_phase != catalog.study_phase.value:
                raise ScopeViolationError(
                    f"正式审核节点 {target_id} 不属于本次发布的期别"
                )
            bound_stage = expected_stage.get(source_id)
            if bound_stage is not None and stage.stage != bound_stage:
                raise ScopeViolationError(
                    f"正式审核节点 {target_id} 的阶段与控制目录绑定不一致"
                )

    def _verify_gate(self, publication: ControlCatalogPublication) -> None:
        """发布门禁必须已接受本次发布身份，且输出哈希等于发布正文哈希。"""
        gate = AppendRepository(self._session, GATE_RESULT_CONFIG).get(
            publication.gate_result_id
        )
        if (
            gate.gate_name != CONTROL_CATALOG_PUBLICATION_GATE_NAME
            or gate.result != GateOutcome.ACCEPTED
            or publication.publication_id not in gate.accepted_entity_refs
            or gate.output_hash != canonical_hash(publication.model_dump(mode="json"))
            or publication.source_job_id not in gate.input_entity_refs
            or publication.source_checkpoint_id not in gate.input_entity_refs
        ):
            raise ScopeViolationError("控制目录发布缺少完整的发布门禁凭据")
