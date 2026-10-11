# Codex Execution Plan: phase5-resume-next-flash-20260903

Objective: 在不改写历史证据且不引入项目特异硬编码的前提下，将现行 MTPLX 产品路由统一为 Qwen3.8-Next-Flash，恢复并验证 SAR 31001 Phase 5 事实规范化，形成可审计的 Phase 5 收口依据。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审计当前产品配置、运行辅助代码和现行测试中的旧 Qwen3.8-27B 身份，限定最小修改范围并补充防回退验证。 | `runs/execution/phase5-resume-next-flash-20260903/worker_01.md` |
| `worker_02` | 复现并持久化 SAR 31001 筛选期单页 Evidence Normalizer 诊断，区分来源闭包、Schema 和模型质量或性能问题。 | `runs/execution/phase5-resume-next-flash-20260903/worker_02.md` |
| `worker_03` | 在单页门禁通过后从合法新作业入口恢复筛选期与基线期规范化，核验事实、事件、用药暴露与 Profile 的来源闭包和临床质量。 | `runs/execution/phase5-resume-next-flash-20260903/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
