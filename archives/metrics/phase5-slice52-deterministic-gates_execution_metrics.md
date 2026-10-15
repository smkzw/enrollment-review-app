# Execution Metrics: phase5-slice52-deterministic-gates

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `opencode-go` | `muse-spark-1.2-contributor` (`xhigh`) | 完成 | 1444.490 s | 未单列 | 合同与纯确定性门禁；单轮、无 fallback |
| `worker_02` | `opencode-go` | `muse-spark-1.2-contributor` (`xhigh`) | 完成 | 1366.354 s | 未单列 | Phase 4 证据闭包与候选级 OCR 阻断；单轮、无 fallback |
| `worker_03` | `opencode-go` | `muse-spark-1.2-contributor` (`xhigh`) | 完成 | 1107.496 s | 未单列 | 去重、冲突与批量编排；单轮、无 fallback |

三名执行者均由 `role-specific-beijing-schedules-v2` 在北京时间夜间从声明主路线切换到有效路线；执行日志 `returncode=0`、`round_count=1`，未发生模型替换或恢复轮次。工具调用数未由 runner 输出，故不推测填写。
