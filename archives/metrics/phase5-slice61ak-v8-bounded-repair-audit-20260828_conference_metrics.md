# Conference Metrics: phase5-slice61ak-v8-bounded-repair-audit-20260828

Date: 2026-08-28

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `general_pi_antigravity` | `google-antigravity` | `gemini-3.7-flash` | 完成 | 452.900 秒 | 未暴露 | 未暴露 | 复现隔离恢复并确认恢复后门禁拒绝正确 |
| `general_grok46` | `grok-build` | `grok-4.6` | 完成 | 741.953 秒 | 未暴露 | 4,042,361（含缓存读取） | 复现恢复、指出下一修复范围及多冻结来源键缺口 |

## Timeout And Retry Evidence

两名参与者均一次完成，runner `returncode=0`；没有超时、续写、重试或 fallback。Gemini session `01a04897-b2f2-7000-afb5-5da3d1cc9630`，Grok session `19303f83-9391-425d-b1fa-6e66f179ab60`。

## Quality Decision

会商对真实 v8 工件给出一致结论：隔离修复成立，p804 范围拆分仍应拒绝。Codex 采纳多冻结无关来源键缺口并补充第 29 个聚焦测试；最终以 `989 passed`、真实 A4→A5 离线恢复和恢复后发布门禁拒绝作为非模型锚点。v8 不接受、不发布、不沿相同合同重跑。
