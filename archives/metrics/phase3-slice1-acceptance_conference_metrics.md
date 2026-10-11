# Conference Metrics: phase3-slice1-acceptance

Date: 2026-08-14

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `general_pi_qwen38` | `cms-smk` | `deepseek-v4-flash:max` | complete, focused passes | runner logs | recorded | recorded | 初审、返修复核、最终碰撞复核通过 |
| `general_grok46` | `grok-build` | `grok-4.6` | one complete audit; later output incomplete | runner logs | recorded | recorded | 有效问题纳入，最终放行不依赖该角色 |

## Timeout And Retry Evidence

Pi 健康探针超时，但按规则进行一次真实调用并建立可恢复会话；未因探针超时 fallback。
Grok 首轮 `stopReason=cancelled` 后复用同一 session 完成报告；后续不完整输出经同会话
恢复仍不满足验收，因此明确不计最终通过。所有长任务按 runner 硬等待，无定时重派。

## Quality Decision

Pi 最终独立复测：MG/D001 剩余精确范围碰撞 `0/0`，页级核验失败 `0/0`，协议测试
`47 passed`，全仓 `514 passed + 18 subtests`。结论：无新 P0/P1，切片 1 可进入切片 2。
