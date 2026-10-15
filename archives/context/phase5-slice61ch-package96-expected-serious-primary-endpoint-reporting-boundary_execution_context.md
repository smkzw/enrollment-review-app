# Execution Context: phase5-slice61ch-package96-expected-serious-primary-endpoint-reporting-boundary

Created: 2026-08-30 09:45:16 CST
Objective: 建立并独立攻击验证 D001 II 当前 131 包计划第 96 包 body.p1136-p1137 的模型外来源闭包，保持跨包列表、条件作用域和非绝对报告强度，不产生入排候选或调用临床模型。
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

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61ch-package96-expected-serious-primary-endpoint-reporting-boundary-execution-contract.md`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/coverage_manifest.json`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json`
- Do not add production paths without explicit Codex authorization.

## Authorized Artifact Paths

- Worker 01 may write the Package 96 config and parent checklist named in the execution contract.
- Worker 02 may write `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61ch_package96_expected_serious_primary_endpoint_reporting_boundary.py` and the dry-run directory `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n-prepare/d001-ii-package96-expected-serious-primary-endpoint-reporting-boundary/`.
- Worker 03 is read-only and may inspect those artifacts after Workers 01 and 02 complete.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 创建第 96 包结构化配置与父级检查清单，仅写合同授权路径，严格使用 2 个自有来源与 5 个只读附加来源。
2. 创建确定性变异测试并运行 dry-run prepare，覆盖 AND/OR、一般/不建议强度、主要疗效终点条件、报告主体/形式/机构及逆命题。
3. 独立只读攻击审阅配置、测试和准备产物，寻找正反字段互相遮蔽、条件逆推、绝对化、跨包吞并和候选越权的最小反例。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
