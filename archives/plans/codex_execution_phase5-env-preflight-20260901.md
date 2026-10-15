# Codex Execution Plan: phase5-env-preflight-20260901

Objective: 在 Phase 5 收口中以最小改动建立 worktree 显式环境文件契约，补齐方案解构 GLM 凭据映射，在后台任务启动前验证声明模型的凭据与端点，并用故障注入测试证明失败路径不会泄露密钥。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审查当前配置加载、启动脚本、语义路由与测试构造方式，给出最小根因修复边界和兼容风险。 | `runs/execution/phase5-env-preflight-20260901/worker_01.md` |
| `worker_02` | 实现显式 ENROLLMENT_ENV_FILE 契约、启动前语义路由预检与中文失败信息，补充缺失凭据及端点故障注入测试；仅改阻塞项直接相关文件。 | `runs/execution/phase5-env-preflight-20260901/worker_02.md` |
| `worker_03` | 独立审查实现与测试，重点验证 worktree 进程确实获得 DECONSTRUCT_GLM_API_KEY、声明路由等于可执行路由、故障不泄密且不误触测试网络。 | `runs/execution/phase5-env-preflight-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
