# Execution Metrics: phase5-slice61bx-package86-dili-evaluation-boundary

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `codebuddy-cli` | `deepseek-v4-flash:max` | fallback complete | 172.740 s | 28 | 原始 DOCX 指纹、结构、列表层级及第 85-87 包所有权核对完成 |
| `worker_02` | `codebuddy-cli` | `deepseek-v4-flash:max` | fallback complete; parent revised | 786.982 s | 110 | 配置、清单、准备证据和专项回归完成，父级补强交叉引用非唯一门禁 |
| `worker_03` | `codebuddy-cli` | `deepseek-v4-flash:max` | fallback complete | 295.140 s | 37 | 六类临床语义反例、时间锚、调查层次与跨包吞并挑战完成 |

三个角色均在声明的 `glm-5.3-flash:max` 路线不可用后，按受控路线使用同平台回退 `deepseek-v4-flash:max` 完成；未替换为未声明模型。Codex 独立验收：模型外准备 `7/12/19`，提示 `36744`；专项 `42 passed`，Phase 闭包 `491 passed`，方案与 Agent `1198 passed`，治理工具 `30 passed`，未调用临床语义模型。
