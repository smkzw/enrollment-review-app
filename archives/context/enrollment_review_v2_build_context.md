# Task Context: enrollment_review_v2_build

Created: 2026-08-12 19:09:33
Objective: 依据V2架构设计与分阶段计划构建本地单用户AI主导的临床试验入排审核工作台，先完成Phase 0/0.5/1并在Phase 1.5用户验收前停止后台核心实施
Task type: `long_horizon_code`
Risk: `high`
Selected agent route: `cms-smk` / `deepseek-v4-flash` / `max`

## Trigger Reason

This task was initialized through the Codex x Hermes complex-task entrypoint because it is expected to involve more than three execution steps, research/writing/report/code/report-visual work, or source-grounded verification.

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`：已获用户确认的产品与架构事实源。
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`：阶段顺序、退出门槛和统一验证矩阵。
- `.trellis/tasks/08-12-enrollment-review-v2/`：V2 总任务合同。
- `.trellis/tasks/08-12-phase0-foundation/`：当前 Phase 0 工作合同和上下文清单。
- `.trellis/spec/backend/`、`.trellis/spec/frontend/`：实施与检查规范。
- `AGENTS.md`、全局 `/Users/smkzw/.codex/AGENTS.md`：执行边界和路由政策。
- legacy 源码、`tests/test_phase_workflow.py`、`SYSTEM_REVIEW_REPORT.md`：旧系统行为和反面回归锚点。
- 当前文件系统、Git、真实命令输出和浏览器运行时优先于旧文档中的历史数字。

## Scope

- In scope: Phase 0/0.5/1 及 Phase 1.5 前的分阶段实现；本地单用户、无登录、中文医学监查工作台；Agent 候选与确定性 Gate 分离；Patient Profile、方案解构、阶段审核、证据与 Action 合同；真实浏览器和临床回归准备。
- Out of scope: Phase 1.5 用户验收通过前的 Phase 2 持久化业务实施；修改或删除 legacy 临床项目；重新运行全量临床审核；公开部署；安全测试；Qwen 3.8 会商或执行路线。

## Success Criteria

- 每个阶段有 Trellis 子任务、可复现产物、自动化证据、独立检查和 Codex 接受记录。
- legacy 代码和项目保持可运行且不可被 V2 写路径修改。
- Phase 0.5 冻结领域/API/Agent/Gate/Job/fixture 合同；Agent 不直接写最终状态。
- Phase 1 使用相同合同的 stub API 构建可演进 React 产品壳，不读取旧 Markdown 作为事实源。
- 真实浏览器验证自然中文、无页面级横向滚动、阶段直观、父子规则清晰、关键证据不超过 3 次操作可达。
- Phase 1.5 量化 UAT 未通过即停止后台实施并回到原型修订。

## Risk Boundaries

- Do not write to production paths until Codex review gate passes and writable paths are explicit.
- The delegated agent is not final authority; Codex owns verification and acceptance.
- 不得向 `projects/`、`output/` 中的 legacy 临床资产写入或删除内容。
- 不得将模型自由文本、Markdown、mtime 或单一总体结论作为 V2 临床事实源。
- 不得因供应商探测失败或响应慢静默更换模型；按路由政策完成真实尝试、同会话恢复和证据记录。
- 用户已明确取消 Qwen 3.8 会商；任何执行/检查包不得选择或回退到 Qwen 3.8。

## Timeout Policy

- Do not mark the delegated agent failed for slow response alone.
- For complex or artifact-heavy work, wait and poll generously; use conference mode when multiple independent model perspectives are needed.
- Failure requires terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no progress after hard wait plus one retry.
- A provider catalog/auth/transport preflight is diagnostic, not a live capability verdict: timeout, auth refresh failure, or malformed probe output must be recorded and followed by one real route attempt. Only a missing executable or explicit invalid/retired/unlisted model may stop before that attempt.

## Loop Log

- 2026-08-12 19:09:33: Task initialized by `tools/hermes_workflow_guard.py init-task`.
- 2026-08-12: Trellis 0.6.14 initialized; baseline commit `a02b833`, Phase 0 branch `codex/v2-phase0-foundation`.
- 2026-08-12: legacy actual runtime `/usr/bin/python3`; 131 tests passed, 1 skipped; health endpoint reports oMLX/DeepSeek ready.
- 2026-08-12: V2 runtime separated to CPython 3.12.13; dependency locks and initial write-boundary tests created.
