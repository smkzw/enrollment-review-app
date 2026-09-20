# Conference Metrics: phase5-slice58j-d001-phase-evidence-design-20260826

Date: 2026-08-26

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `general_pi_qwen38` | `alibaba` | `qwen3.8-max:xhigh` | accepted after output recovery | 2751.968 s | 1 | 169520 | 完整审阅；建议经 Codex 选择性采纳 |
| `general_grok46` | `cursor-cli` | `auto` | accepted | 185.734 s | 1 | 101944 | 完整独立挑战；无 fallback |

## Timeout And Retry Evidence

- Cursor 单轮返回，runner 记录 185.734 秒、返回码 0、无 fallback。
- Qwen 初始可恢复会话连续输出工具调用而无规定报告；同会话补全耗尽。主控尝试声明的 Muse 后备时，runner 按北京夜间调度把有效路线重新水合为 Qwen3.8 Max；新会话 2751.968 秒后返回完整报告，返回码 0、无 runner fallback。原始不完整报告和日志保存在 `archives/conference/phase5-slice58j-d001-phase-evidence-design-20260826/primary-incomplete/`。
- Qwen 有效轮次的 169520 tokens 含缓存读取；Cursor 表中 tokens 为输入加输出，不含 573696 cache-read tokens。两者口径不同，不用于模型质量排名。

## Quality Decision

两份有效报告均达到独立挑战要求，但只作为顾问证据。Codex 已拒绝全局共享桥接、官方编号即 selected 和永久跳过全文剩余单元三项过度推断；其余建议须由下一轮确定性生成器、回归和真实方案语义包验证。
