"""Phase 5 Slice 5.2 门禁领域合同（纯确定性，无存储）。

本模块冻结 Slice 5.2 确定性门禁的输入/输出合同，供纯校验器与批量编排共享：

- ``FactCandidateBatch``：一次调用内的结构化候选批次（fact/event/exposure），不含文件路径或模型输出；
- ``GateVerdict``：单个门禁步骤对单个候选的确定性裁决（ACCEPTED/REJECTED/BLOCKED + 原因 + 受影响范围）；
- ``DedupGroup``：稳定内容身份相同的精确重复候选分组（不含定位与置信度）；
- ``SemanticConflictGroup``：同一语义对象但稳定身份不兼容的未解决冲突组（不择优）；
- ``BatchGateResult``：批次级门禁汇总（逐候选裁决、去重键与冲突占位，不含发布或 Profile）。

所有合同均为纯校验结构，不触发数据库、文件或模型调用；受影响范围仅使用候选自带的
``locator_ids``/``fact_candidate_ids``/缺页标识，不依赖外部定位真相。"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel
from .enums import FactGate, GateOutcome

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class GateVerdict(ContractModel):
    """单个门禁步骤对单个候选的确定性裁决。

    ``affected_scope`` 为该候选受影响的确定性范围（候选自带的 locator_ids 或
    引用缺口的 fact_candidate_ids），已排序去重，用于上游聚合受影响范围与
    阻断范围，不含页码或外部定位。
    """

    candidate_id: str = Field(min_length=1)
    gate: FactGate
    outcome: GateOutcome
    reasons: list[str] = Field(default_factory=list)
    affected_scope: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_verdict(self) -> GateVerdict:
        if self.outcome != GateOutcome.ACCEPTED and not self.reasons:
            raise ValueError("被拒或阻断的裁决必须给出原因")
        if self.affected_scope != sorted(set(self.affected_scope)):
            raise ValueError("受影响范围必须有序且去重")
        return self


class FactCandidateBatch(ContractModel):
    """一次确定性门禁批次输入：同一次 run/call 内的候选集合。

    本合同只校验批次内引用闭包与排序要求，不校验定位真实性、页覆盖或 OCR 风险
   （后两者由证据闭包适配器负责）。``run_id``/``call_id`` 必须与
    批次内每个候选一致，否则视为跨调用混批。
    """

    run_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    fact_candidate_ids: list[str] = Field(default_factory=list)
    event_candidate_ids: list[str] = Field(default_factory=list)
    exposure_candidate_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_batch(self) -> FactCandidateBatch:
        for label, ids in (
            ("事实候选", self.fact_candidate_ids),
            ("事件候选", self.event_candidate_ids),
            ("暴露候选", self.exposure_candidate_ids),
        ):
            if ids != sorted(set(ids)):
                raise ValueError(f"{label} 必须按 ID 排序且不得重复")
        # 跨种类 ID 不得重复（同一 candidate_id 不能既是 fact 又是 event）
        all_ids = self.fact_candidate_ids + self.event_candidate_ids + self.exposure_candidate_ids
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("批次内候选 ID 跨种类不得重复")
        return self


class DedupGroup(ContractModel):
    """精确重复候选分组：同一稳定身份的候选集合。

    ``stable_identity`` 为 ``clinical_*_stable_identity`` 的 64 位十六进制；
    ``candidate_ids`` 有序去重且至少 2 个；``merged_locator_ids`` 为组内全部
    定位的有序去重并集，用于审计追踪（不参与稳定身份）。
    """

    stable_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_ids: list[str] = Field(min_length=2)
    merged_locator_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dedup(self) -> DedupGroup:
        if self.candidate_ids != sorted(set(self.candidate_ids)):
            raise ValueError("去重组候选 ID 必须有序且去重")
        if self.merged_locator_ids != sorted(set(self.merged_locator_ids)):
            raise ValueError("去重组合并定位必须有序且去重")
        if not _SHA256.match(self.stable_identity):
            raise ValueError("稳定身份必须是 64 位十六进制")
        return self


class SemanticConflictGroup(ContractModel):
    """同一语义对象但稳定身份不兼容的未解决冲突组（不择优）。

    ``semantic_key`` 为语义对象键（如 fact 的 fact_type:asserted_object、
    event 的 event_type、exposure 的 medication_name）；``semantic_type``
    区分事实/事件/暴露；``candidate_ids`` 与 ``distinct_stable_identities``
    均至少 2 个且有序去重；``reasons`` 说明冲突维度（值/极性/日期/持续状态）。
    """

    semantic_key: str = Field(min_length=1)
    semantic_type: Literal["fact", "event", "exposure"]
    candidate_ids: list[str] = Field(min_length=2)
    distinct_stable_identities: list[str] = Field(min_length=2)
    reasons: list[str] = Field(default_factory=list)
    affected_scope: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_conflict(self) -> SemanticConflictGroup:
        if self.candidate_ids != sorted(set(self.candidate_ids)):
            raise ValueError("冲突组候选 ID 必须有序且去重")
        if self.distinct_stable_identities != sorted(set(self.distinct_stable_identities)):
            raise ValueError("冲突组稳定身份必须有序且去重")
        if len(self.distinct_stable_identities) < 2:
            raise ValueError("冲突组必须包含至少 2 个不同的稳定身份")
        if self.affected_scope != sorted(set(self.affected_scope)):
            raise ValueError("冲突组受影响范围必须有序且去重")
        for sid in self.distinct_stable_identities:
            if not _SHA256.match(sid):
                raise ValueError("稳定身份必须是 64 位十六进制")
        return self


class BatchGateResult(ContractModel):
    """批次级门禁汇总（确定性编排输出，不含发布或 Profile）。

    ``overall_outcome`` 为批次整体裁决（任一关键门禁 REJECTED/BLOCKED 时为
    REJECTED/BLOCKED，否则 ACCEPTED）；``failure_reasons`` 为批次级失败原因
    （如空输出、页覆盖不完整）；``dedup_groups`` 与 ``conflict_groups`` 为
    去重与冲突占位（不择优）；``gate_results`` 扁平为 ``GateVerdict``
    列表，确定性排序为 (candidate_id, gate.value)。
    """

    run_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    overall_outcome: GateOutcome
    failure_reasons: list[str] = Field(default_factory=list)
    dedup_groups: list[DedupGroup] = Field(default_factory=list)
    conflict_groups: list[SemanticConflictGroup] = Field(default_factory=list)
    gate_results: list[GateVerdict] = Field(default_factory=list)
    affected_scope: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_batch_result(self) -> BatchGateResult:
        if self.overall_outcome != GateOutcome.ACCEPTED and not self.failure_reasons:
            has_rejected = any(v.outcome != GateOutcome.ACCEPTED for v in self.gate_results)
            if not has_rejected:
                raise ValueError("非通过的批次必须给出失败原因或至少一个被拒/阻断的裁决")
        if self.affected_scope != sorted(set(self.affected_scope)):
            raise ValueError("批次受影响范围必须有序且去重")
        sorted_results = sorted(self.gate_results, key=lambda v: (v.candidate_id, v.gate.value))
        if self.gate_results != sorted_results:
            raise ValueError("批次门禁结果必须按 (candidate_id, gate) 确定性排序")
        if self.dedup_groups != sorted(self.dedup_groups, key=lambda g: g.stable_identity):
            raise ValueError("去重组必须按 stable_identity 确定性排序")
        if self.conflict_groups != sorted(self.conflict_groups, key=lambda g: g.semantic_key):
            raise ValueError("冲突组必须按 semantic_key 确定性排序")
        return self


class RunGateResult(ContractModel):
    """一个规范化 run 的唯一门禁汇总。

    多个文档 call 的裁决在这里按 ``(candidate_id, gate)`` 合并；
    ``candidate_call_ids`` 保留每个候选的真实调用归属，持久化时不得用一个
    代表性 call_id 冒充整个 run。
    """

    run_id: str = Field(min_length=1)
    call_ids: list[str] = Field(min_length=1)
    candidate_call_ids: dict[str, str] = Field(default_factory=dict)
    overall_outcome: GateOutcome
    failure_reasons: list[str] = Field(default_factory=list)
    dedup_groups: list[DedupGroup] = Field(default_factory=list)
    conflict_groups: list[SemanticConflictGroup] = Field(default_factory=list)
    gate_results: list[GateVerdict] = Field(default_factory=list)
    affected_scope: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_run_result(self) -> RunGateResult:
        if self.call_ids != sorted(set(self.call_ids)):
            raise ValueError("run 的 call_ids 必须有序且去重")
        if set(self.candidate_call_ids.values()) - set(self.call_ids):
            raise ValueError("候选调用归属必须属于本 run 的 call_ids")
        keys = [(item.candidate_id, item.gate.value) for item in self.gate_results]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ValueError("run 门禁结果必须按 candidate+gate 唯一且确定性排序")
        if set(self.candidate_call_ids) != {item.candidate_id for item in self.gate_results}:
            raise ValueError("run 门禁结果必须覆盖且只覆盖已声明调用归属的候选")
        if self.affected_scope != sorted(set(self.affected_scope)):
            raise ValueError("run 受影响范围必须有序且去重")
        if self.overall_outcome != GateOutcome.ACCEPTED and not self.failure_reasons:
            raise ValueError("非通过 run 必须给出失败原因")
        return self
