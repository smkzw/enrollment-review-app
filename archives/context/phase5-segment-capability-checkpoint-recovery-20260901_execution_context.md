# Execution Context: phase5-segment-capability-checkpoint-recovery-20260901

Created: 2026-09-01 12:26:18 CST
Objective: 修复真实 GLM 父规则分段探针暴露的通用机制缺陷：将分段能力与 compact wire 解耦，按确定性分段身份持久复用成功结果，区分远端超时与 Schema 错误并仅对同模型同分段有限恢复；不得加入项目、疾病、药物、量表、条款号或时间点硬编码，不得恢复 D001 或改写冻结临床源与旧探针。
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

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读追踪 GLM 传输能力声明、父规则分段进入条件、并发执行、错误映射、缓存/检查点接口及调用方；提出最小通用修复边界和兼容性风险，不修改生产文件。
2. 单写者实施通用修复：独立的父规则分段能力声明；来源哈希、提示版本、模型身份、分段身份组成的成功段检查点；同模型同分段有限超时恢复；超时与 Schema 错误分离；保持部分结果不可发布和跨 provider 不拼接。
3. 独立编写并运行对抗测试：GLM 可进入分段、非分段传输不误入、成功段复用、只恢复失败段、缓存身份漂移失效、超时分类、并发上限、合并完整性、失败关闭及项目特异硬编码扫描；不得改生产实现。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
