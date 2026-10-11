# Execution Context: phase5-slice58-acceptance-harness-latest

Created: 2026-08-23 23:06:53
Objective: 为 Phase 5.8 建立可审计的真实项目隔离输入清单、病例级 P5-AC01 至 P5-AC13 验收账本与真实浏览器端到端验收工具；不得修改原始临床资料，不提前给出入排结论，不以 fixture 冒充真实运行。
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `cursor` / `cursor-cli` / `auto`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/prd.md`（P5-AC01 至 P5-AC13）
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/design.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/implement.md`（5.8 边界）
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- 现有 `app/api/v2`、`app/services`、`app/storage`、`frontend/e2e` 和测试帮助器，仅按各工作项需要渐进读取。
- 外部 D001/SAR 临床源目录不在执行者读取范围；Codex 在工具验收后以只读方式生成隔离清单和副本。

## Authorized Write Sets

- worker_01: `tools/phase5_acceptance/input_manifest.py`、`tests/tools/test_phase5_acceptance_input_manifest.py`、`.trellis/tasks/08-22-phase5-clinical-facts-profile/research/slice58-input-manifest-contract.md`。
- worker_02: `tools/phase5_acceptance/ledger.py`、`tools/phase5_acceptance/ledger.schema.json`、`tests/tools/test_phase5_acceptance_ledger.py`。
- worker_03: `frontend/e2e/phase5-real-acceptance.spec.ts`、`frontend/e2e/phase5-real-acceptance-support.ts`、必要时仅修改 `frontend/playwright.config.ts` 以登记显式环境开关。
- 上述路径互斥；不得修改同一文件，不得编辑 Phase 5 产品逻辑。若发现产品缺陷，只在报告中给出复现和最小修复建议。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 实现只读源目录盘点与内容哈希清单、排除照片/压缩包规则、隔离复制计划和源文件不变性校验；工具只生成工作区内清单/副本，不写外部原始目录。
2. 实现 P5-AC01 至 P5-AC13 机器可读验收账本与病例级数据库/文件/定位核对器，能区分观察、自动检查、人工临床核对和测试者证据，不把测试通过冒充临床正确。
3. 实现新架构 D001 II 与 MG-K10-SAR III 新项目的浏览器验收编排骨架，覆盖项目创建、方案期别选择、受试者资料上传、真实 Normalizer、Patient Profile、原文定位和历史回放；保持执行者与独立测试者角色分离。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
