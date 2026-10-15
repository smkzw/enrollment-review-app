# Codex Execution Plan: phase5-slice58-runtime-bootstrap-20260824

Objective: 为 Phase 5.8 建立 Evidence Normalizer 的生产可用、不可变且可验证的运行配置注册，确保全新数据库能够实际启动规范化任务，同时不误选其他 Agent 的配置。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审计现有 PromptVersion、ModelConfig、应用 lifespan 与 FactNormalizationCommandService 的真实运行路径，确认全新数据库配置缺口及共享模式。 | `runs/execution/phase5-slice58-runtime-bootstrap-20260824/worker_01.md` |
| `worker_02` | 实现 Evidence Normalizer 专属运行配置的确定性注册和精确选择，配置变化追加新身份、合同漂移失败关闭，不修改临床规则。 | `runs/execution/phase5-slice58-runtime-bootstrap-20260824/worker_02.md` |
| `worker_03` | 补充全新应用启动、不可变身份、配置变化追加、错误配置拒绝及命令路径的聚焦回归测试，并执行相关测试。 | `runs/execution/phase5-slice58-runtime-bootstrap-20260824/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
