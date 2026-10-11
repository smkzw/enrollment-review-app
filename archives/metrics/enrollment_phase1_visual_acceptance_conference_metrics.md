# Conference Metrics: enrollment_phase1_visual_acceptance

Date: 2026-08-13

| Role | Provider | Model | Status | Duration | Passes | Result |
|---|---|---|---|---:|---:|---|
| `visual_pi_k3_256k` | `kimi-code` | `k3-256k` | completed | 39m 46s | 2，同一会话 | 接受进入 Phase 1.5 |

## Timeout And Retry Evidence

- 首次连接性目录探测 90 秒超时，仅作为诊断；按全局规则仍执行一次真实路由。
- 真实路由成功创建会话 `019ff816-9fb5-7000-990c-36ce6ad29bd4`，首轮 1228.658 秒，同会话复核 1157.176 秒。
- 未更换模型、未触发 fallback、未因慢响应重派；两轮均使用 7200 秒 runner 超时和 128 个内部步骤上限。
- 大体量逐步输出只用于恢复证据，验收后清理；正式报告保存在 `runs/conference/enrollment_phase1_visual_acceptance/`。

## Quality Decision

- 首轮发现 `undefined` 时间窗这一真实阻断，并追溯到前端 Wire 与冻结 fixture 字段错配。
- 同会话复核确认阻断关闭，提出两个非阻断残余：方案差异区 `REQ-` 漏映射、缩放测试假阳性。
- Codex 未把“接受”当作停止理由，继续关闭两个残余并重新完成 137 项单元/组件测试、构建、153 项浏览器测试和截图复核。
- 会议质量满足独立挑战、同会话恢复、非模型验证锚点和最终由 Codex 验收的要求。
