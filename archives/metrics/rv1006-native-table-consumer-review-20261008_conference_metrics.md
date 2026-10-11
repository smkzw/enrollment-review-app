# Conference Metrics: rv1006-native-table-consumer-review-20261008

Date: 2026-10-08 UTC / 2026-10-09 CST

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `evidence_single_object` 首审 | `codebuddy-cli` | `deepseek-v4.1-flash:max` | completed / returncode0 | 194.256秒 | unknown | unknown | sorted缺陷；复用风险 |
| 同会话差异复核 | `codebuddy-cli` | `deepseek-v4.1-flash:max` | completed / returncode0 | 86.082秒 | unknown | unknown | 未找到必修反例；静态范围 |
| 同会话来源时间恢复 | `codebuddy-cli` | `deepseek-v4.1-flash:max` | completed / returncode0 | 79.969秒 | unknown | unknown | 子串风险采纳；未测试/临床 |

## Timeout And Retry Evidence

会话01a11c53-1d24-71c2-8a28-568da7aaea2e；每轮timeout7200、工具128内部turn上限，不是128临床调用。完成等待期间所有者静默，不因安静重派。没有fallback。首审约13次读取超10约束如实记录；两轮不是模型独立。

## Quality Decision

源码审阅不是产品实际读取/软件测试/医学批准；所有者修sorted、用真实保存wire做零调用重放，进一步验证相连模块。公开仅净化工程报告，不提交原件、DB、环境、临床原答或私有日志。
