# Execution Metrics: phase3-protocol-slice1

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `codebuddy-cli` | `deepseek-v4-pro:xhigh` | complete | runner log | enabled | 契约、ORM、迁移 |
| `worker_02` | `codebuddy-cli` | `deepseek-v4-pro:xhigh` | complete + follow-up | runner log | enabled | 结构、渲染、来源对齐 |
| `worker_03` | `codebuddy-cli` | `deepseek-v4-pro:xhigh` | usable code / incomplete report | runner log | enabled | 测试、真实方案、候选 spike |

自动 Pi/OpenCode Go 主路由两次真实调用均因 `429` 周额度限制终止，随后使用声明的
CodeBuddy 回退。验收不依赖 worker 自报，Codex 重跑全部测试与真实方案回归。
