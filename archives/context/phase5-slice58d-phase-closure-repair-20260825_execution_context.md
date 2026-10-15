# Execution Context: phase5-slice58d-phase-closure-repair-20260825

Created: 2026-08-25 14:25:57
Objective: 修复全方案覆盖清单未持久化、期别语义 Agent 缺少真实 transport、跨章节控制使用临时结构身份的共享根因；以 D001 II 只读源完成可恢复的 1689 单元/1433 模糊单元闭包并用真实结构身份重建严格矩阵。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `codex-subagent` / `codex` / `gpt-5.6-luna`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md,task.json}`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260825_D001_V5_OFFICIAL_FLOW_ACCEPTED.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/slice58-d001-phase-applicability-gap.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/slice58-cross-section-protocol-controls.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-official-flow-controls.json`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-cross-section-controls.json` (Worker 03 首轮仅为被拒绝的候选发现输入)
- `app/agents/phase_applicability.py`
- `app/protocols/{full_protocol_coverage.py,phase_applicability.py,phase_applicability_planning.py,protocol_control_gate.py}`
- `app/domain/contracts/{phase_applicability.py,protocol_controls.py,protocol_control_matrix.py}`
- `tests/v2/protocols/`
- D001 原始方案 `/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx`，仅允许只读。权威 SHA-256 为 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`。

## Authorized Writes

- Worker 01 only: `app/agents/phase_applicability_transport.py`, `app/services/phase_applicability_execution.py`, `app/agents/phase_applicability.py`, `app/agents/__init__.py` / `app/services/__init__.py` 中必要的最小导出、`scripts/run_phase_applicability_acceptance.py`, `tests/v2/protocols/test_phase_applicability_live_execution.py`, `tests/v2/protocols/test_slice58c2_phase_applicability_agent.py`。若复用现有模块可以更少文件完成，优先更少文件；不得改 D001 临床逻辑或写入项目特异分支。Codex 父级真实首批验收已证明原提示投影要求模型返回全局 `source_span_indexes`，却未在逐单元投影中提供该映射；同一修复还必须让 Runner 每次获得模型响应并完成一次解析/门禁尝试后立即回调 execution checkpoint，避免后续修复调用中断时丢失首轮哈希和校验问题。
- Worker 02 only: `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/` 下的可恢复运行工件。不得改应用代码、测试、已接受 v5 矩阵或原始 DOCX。
- Worker 03 only: `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-cross-section-controls.json`, `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-control-matrix.json`, `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-control-matrix-review.md`。不得改已接受的 `d001-ii-official-flow-controls.json/.md`。
- Runner 管理的 `runs/` 报告只由 runner 写入。

## Execution Order And Acceptance

1. Worker 01 必须先终态完成并由 Codex 实际运行聚焦回归验收；Worker 02 不得自建替代 transport。
   Codex 的首批真实验收发现并拒绝了两个共享缺陷：逐单元缺少全局 span 数字索引，以及 Runner 完整结束前不保存单次尝试。Worker 01 必须在同一执行会话中定向修复并由 Codex 用首个冻结批次重新验收。
2. Worker 02 使用系统配置的 oMLX 方案解构模型与现有严格 Schema/Gate。本系统内置本地 LLM/VLM 不受执行/会商路由 32K 上下文限制；不得因此截断已冻结来源包。
3. Worker 02 必须持久化原始 1,689 单元清单、235 批冻结计划、逐批原始响应哈希/解析结果/错误与恢复状态、非变异聚合视图。任一未决单元必须保留 `unresolved`，不得默认共用。
4. Worker 03 仅在 Worker 02 已产生可读的权威清单后运行；42 个临时 ID 必须依据 `source_ref + 逐字摘录`唯一对齐到真实 `structure_unit_id`，不得只换前缀。
5. 跨章节文件的 25 行边界必须明确表达为“1 行已接受的流程审核基准 + 24 行新的其他章节候选”；合并矩阵仍为 58 + 24 = 82 行，不重复计数基准行。
6. 不以非空 JSON、模型自报或 `claims_complete=false` 代替严格验收。验收至少包括：源文件不变、Schema、冻结身份、每批所有权、逐字来源、期别闭包、矩阵严格来源/期别/时间/逻辑/例外/节点闭包。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- 不得读取或修改生产数据库、旧项目、受试者原始资料。本次只读外部路径只有上述 D001 方案。
- 不得静默安装依赖、替换模型/provider、缩短冻结来源包或放松 Gate。

## Work Items

1. 建立通用、provider-neutral 的期别语义真实模型 transport 与可恢复批次执行/持久化机制，复用现有 Schema、prompt、plan 和 gate，不硬编码 D001。
2. 从 D001 II 只读方案确定性重建并持久化 1689 单元全文清单与 235 批冻结期别计划，实际运行系统配置的独立 Agent，保留逐批结果、失败与未决项，不把未知默认共享。
3. 将 D001 II 24 条跨章节候选的 42 个临时结构身份全部替换为真实稳定结构单元，复核 25 行含1行流程基准的计数边界，并在权威清单上完成 v5 严格来源/期别/逻辑闭包与中文验收报告。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
