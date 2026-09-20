# Conference Metrics: r3-visual-cache-repair-review-20260909

Date: 2026-09-09

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `evidence_single_object` | `zcode` | `GLM-5.3:max` | completed | 673.618s | 11 | aggregate unknown | limited acceptance |
| `evidence_single_object round2` | `zcode` | `GLM-5.3:max` | completed | 220.063s | 4 | aggregate unknown | limited acceptance |

## Timeout And Retry Evidence

两轮同会话自然终态，无降级、超时或主动终止。不能把最后一次请求用量当整个审阅总用量。

## Quality Decision

采纳限定批量来源校验与失效修复，保留原始SQL保存点和外部identity-map已有风险。产品完整链和临床验收未通过；真实分段加速不等于整例同倍率加速。
