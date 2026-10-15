# Execution Context: phase5-slice59h-20260827

Created: 2026-08-27 14:16:02
Objective: 在当前冻结 D001 II 计划上，以系统内置 MTPLX 语义 Agent 对源包39、69、70进行真实小批量方案适用性处理，分别验收筛选/基线流程控制、合并用药总则、禁用治疗与洗脱期表格；不得扩大到其余包，不得写入临床源文件。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `pi` / `mtplx` / `mtplx-qwen38-27b-optimized-quality`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- 冻结全文覆盖清单：`artifacts/phase5-slice58r6-d001-phase-handoff-atomization-20260827/coverage_manifest.json`
- 冻结期别计划：`artifacts/phase5-slice58r6-d001-phase-handoff-atomization-20260827/frozen_phase_plan.json`
- 真实验收脚本：`scripts/run_phase_applicability_acceptance.py`
- 现行门禁：`app/agents/phase_applicability.py` 及其相关域模型/测试。
- 内置语义模型端点：`http://127.0.0.1:8002/v1`；模型 `mtplx-qwen38-27b-optimized-quality`；推理强度 `medium`；输出上限 `16384`。
- 每个执行者只能运行自己的一个源包，不得扩大到其他序号，不得修改冻结清单/计划。
- 工件目录分别为：
  - 包 39：`artifacts/phase5-slice59h-d001-package39-mtplx-20260827/`
  - 包 69：`artifacts/phase5-slice59h-d001-package69-mtplx-20260827/`
  - 包 70：`artifacts/phase5-slice59h-d001-package70-mtplx-20260827/`
- 运行参数：`--backend mtplx --base-url http://127.0.0.1:8002/v1 --model mtplx-qwen38-27b-optimized-quality --reasoning-effort medium --max-tokens 16384 --temperature 0 --max-schema-repairs 2`。
- 允许读取当前工作树内与所分配源包直接相关的代码、测试、检查点和过往不可变工件；不得读写临床源文件或生产路径。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 运行并审查源包39：验证筛选/基线节点、资料收集要求、基线时间锚点与检查项目是否形成完整且可回源的期别处置；持久化运行工件与紧凑交接。
2. 运行并审查源包69：验证合并用药记录范围、允许用药、基线前禁用总则及与后续表格的父子关系；持久化运行工件与紧凑交接。
3. 运行并审查源包70：验证禁用治疗表中首次给药前时间窗、较长者为准、洗脱例外及表格逐行原文逻辑；持久化运行工件与紧凑交接。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.

## Per-Worker Command Contract

- `worker_01` 使用 `--package-ordinals 39`、`--run-id d001-ii-phase-closure-20260827-slice59h-pkg39-mtplx`，状态目录为包 39 工件目录下的 `execution/`，摘要为 `semantic-summary.json`。
- `worker_02` 使用 `--package-ordinals 69`、`--run-id d001-ii-phase-closure-20260827-slice59h-pkg69-mtplx`，状态目录为包 69 工件目录下的 `execution/`，摘要为 `semantic-summary.json`。
- `worker_03` 使用 `--package-ordinals 70`、`--run-id d001-ii-phase-closure-20260827-slice59h-pkg70-mtplx`，状态目录为包 70 工件目录下的 `execution/`，摘要为 `semantic-summary.json`。
- 执行前先确认 `/v1/models` 返回上述模型。单次运行慢时应等待其终态，不得因延迟重复派发。
- 交接必须分开：原文观察、模型处置、门禁结果、临床逻辑风险和未验证项；不得自行宣告临床验收通过。
