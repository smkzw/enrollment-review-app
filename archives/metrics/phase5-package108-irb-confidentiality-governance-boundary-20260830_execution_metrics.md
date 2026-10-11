# Execution Metrics: phase5-package108-irb-confidentiality-governance-boundary-20260830

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `cursor` | `default` | COMPLETE | 168.2s | 41 | 来源闭包、语境所有权和逐项治理分类通过。 |
| `worker_02` | `cursor` | `default` | COMPLETE | 416.4s | 178 | 创建受限工件；专项30项通过，无共享代码修改。 |
| `worker_03` | `cursor` | `default` | COMPLETE | 215.9s | 74 | 独立攻击未发现遗漏的单例前置控制。 |
| `worker_04` | `cursor` | `default` | COMPLETE | 390.9s | 197 | 相邻/共享回归174项及39项独立不变量通过。 |

全部角色实际运行身份均为`cursor/default`，return code均为0，无fallback。
