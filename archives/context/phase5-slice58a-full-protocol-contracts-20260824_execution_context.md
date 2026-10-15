# Execution Context: phase5-slice58a-full-protocol-contracts-20260824

Created: 2026-08-24 18:58:12
Objective: 实现全方案结构单元覆盖与其他方案审核控制点的第一阶段领域合同和确定性覆盖清单，不调用模型、不接触真实项目写路径，并以通用夹具验证完整性、来源和官方编号边界。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `cursor` / `cursor-cli` / `auto`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/slice58-cross-section-protocol-controls.md`
- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/quality-guidelines.md`
- `app/domain/contracts/{common,enums,protocol_ingestion,phase_applicability,rules}.py`
- `app/protocols/{structure_extractor,phase_applicability,section_index,deconstruction_service,procedure_catalog}.py`
- `tests/v2/protocols/`
- 不得读取工作树之外的真实方案、受试者资料或生产数据。

## Frozen Design Decisions

- 保留官方 IN/EX 编号边界；其他方案控制不得生成 `CTRL-xx`、`REQ-xx` 或新 IN/EX 官方编号。
- 全文覆盖清单、Agent 候选处置与正式发布控制必须是分离合同。
- 单个正式控制包含非空的多义务原子集，义务类型至少支持：完成/核对、达到条件、禁止事件、禁止药物/治疗暴露、必须记录、必须专业评估。
- 审核节点绑定必须显式标记：提前关注、本节点判定或后续节点复核。
- 跨来源关系为重复表述、补充要求、进一步解释或实质冲突；不实现文本相似度合并。
- 结构单元清单是选定期别全文覆盖，不是关键词候选列表。候选关键词只可影响优先级，不得过滤未命中单元。

## Authorized Write Boundaries And Order

Workers execute serially in this order; later workers may read earlier accepted edits.

1. `worker_01`: may create `app/domain/contracts/protocol_controls.py` and make the minimum export additions in `app/domain/contracts/__init__.py`; avoid changing existing Rule official-code patterns.
2. `worker_02`: may create `app/protocols/full_protocol_coverage.py` and make the minimum export additions in `app/protocols/__init__.py`; do not add Agent or storage integration.
3. `worker_03`: may create focused tests under `tests/v2/protocols/` only. It may report a product defect but must not edit product code.

No worker may modify migrations, API, frontend, prompts, real-project artifacts, task logs, design documents, or runner-owned report files.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- This slice defines contracts and a deterministic manifest skeleton only. It does not claim full-protocol semantic extraction, publication, D001/MG acceptance, browser acceptance, or independent tester acceptance.

## Work Items

1. 新增候选与发布分离的全方案结构单元覆盖、审核控制、多义务原子、节点作用和跨来源关系领域合同。
2. 实现从现有StructureBlock与单期投影生成保留标题路径、表格行列语境和来源定位的确定性全文结构单元清单骨架。
3. 补充合同、构建器和反例测试，证明未处置单元、伪官方编号、来源越界、空义务和不明确节点作用均被拒绝。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
