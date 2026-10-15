# Codex Execution Plan: phase5-slice58-normalizer-profile-integration-latest

Objective: 补齐真实证据启用后事实规范化任务创建、任务完成后 Patient Profile 生成及前端可见状态，使 Phase 5.8 能用真实隔离项目运行；不得生成入排结论，不得绕过权威元组、活动资料和定位门禁。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 实现后端事实规范化命令入口与应用注册：只从当前审核节点活动证据派生 FactAuthority，使用注册的 PromptVersion/ModelConfig 幂等创建持久任务，提供自然中文错误与恢复动作。 | `runs/execution/phase5-slice58-normalizer-profile-integration-latest/worker_01.md` |
| `worker_02` | 在事实规范化 finalize 事务中生成不可变 Patient Profile，明确记录生成中/失败/成功，保持幂等、陈旧权威拒绝和上一活动版本不受失败影响。 | `runs/execution/phase5-slice58-normalizer-profile-integration-latest/worker_02.md` |
| `worker_03` | 实现前端在资料版本启用后自动发起个例档案整理、展示持久任务状态并恢复；更新真实验收编排以等待实际 OCR、事实规范化、Profile、定位与历史，不使用 fixture。 | `runs/execution/phase5-slice58-normalizer-profile-integration-latest/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
