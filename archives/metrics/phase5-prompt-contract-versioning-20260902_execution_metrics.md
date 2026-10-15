# Execution Metrics: phase5-prompt-contract-versioning-20260902

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `zcode` | `GLM-5.3-Flash` | completed | 603.0s | 未单列 | 只读界定旧历史与最小兼容边界 |
| `worker_02` | `zcode` | `GLM-5.3-Flash` | completed after same-route recovery | 764.3s | 未单列 | v1.6/v3 版本化实现复核，1447 项回归通过 |
| `worker_03` | `zcode` | `GLM-5.3-Flash` | completed | 1273.0s | 未单列 | 独立确认历史不可变、双构建确定性及完整回归 |

## Codex Verification

- 聚焦重放与反过拟合回归：`57 passed`。
- 完整协议与 Agent 回归：两次独立运行均为 `1447 passed, 0 failed`。
- 双目录重建：逐字节一致，v3 包指纹 `c32bc9ddeceda41a5a4684a65a586254b2fc2c3af2e596c47468840081e3b66d`，校验退出码 0。
- 本执行包只完成工程版本化，不构成临床接受。
