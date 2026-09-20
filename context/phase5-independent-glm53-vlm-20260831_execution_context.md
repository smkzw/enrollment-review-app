# Execution Context: phase5-independent-glm53-vlm-20260831

Created: 2026-08-31 15:02:55 CST
Objective: 为入排审核系统建立统一的智谱GLM-5.3-Flash视觉模型配置与调用契约，覆盖直接DOCX/PDF来源处理所需的视觉核验能力，并修正旧串行方案控制回放的性能边界；不得改变确定性临床判定边界或写入项目特异规则。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `day`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `cursor/default -> google-antigravity/gemini-3.7-flash:high -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> opencode-go/muse-spark-1.2-contributor:xhigh -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `default`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- 用户当前指令：独立视觉模型使用智谱 BigModel `glm-5.3-flash`，推理强度 `high`；测试者模型与产品内置模型相互独立。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_D001_DISCOVERY_PERFORMANCE_PAUSED.md`
- `.env.example`、`app/config.py`、`app/llm/`、`app/agents/`、`app/protocols/`、`app/evidence/` 和相关 `tests/v2/` 是本执行包的授权代码边界。
- D001 冻结回放、原始临床资料和生产数据不在写入边界内；不得恢复旧任务或引入项目特异规则。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 盘点现有方案解构、方案控制、证据处理、事实规范化和受试者审核harness的模型入口，提出最小共享视觉适配层及兼容迁移清单。
2. 实现并测试BigModel GLM-5.3-Flash视觉传输配置、high到thinking enabled的映射、原始页面输入和来源定位保真契约；远程余额不足必须明确失效关闭。
3. 实现或收紧基于输入令牌和输出预算的自适应批次、有限并发与运行指标，避免继续D001逐固定包串行回放，并做通用性/过拟合审计。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
