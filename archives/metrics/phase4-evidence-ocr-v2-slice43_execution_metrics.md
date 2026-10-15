# Execution Metrics: phase4-evidence-ocr-v2-slice43

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `cms-smk` | `deepseek-v4-flash:max` | completed | 未单独保留 | 报告内详列 | 迁移、仓储与租约合同完成；两轮修订后接受 |
| `worker_02` | `cms-smk` | `deepseek-v4-flash:max` | completed | 未单独保留 | 报告内详列 | 分页、页工件与 OCR 适配完成；两轮修订后接受 |
| `worker_03` | `cms-smk` | `deepseek-v4-flash:max` | completed | 未单独保留 | 报告内详列 | 持久执行、门禁与恢复完成；一轮修订后接受 |
| `trellis-check` | `codex` | `gpt-5.6-luna:max` | completed | 约 118 分钟 | 文件、终端、测试 | 修复 5 类共同原因后终局接受 |

## Acceptance Anchors

- Codex 聚焦回归：`172 passed`。
- Codex V2 全量：`1233 passed, 58 warnings, 2 subtests passed`。
- 真实顺序探针：2/2 页原文一致、模型身份一致、无机器坐标。
- 真实并发探针：12/12 成功，峰值 8，完成后租约 0。
- Ruff、限定 Pyright、`zsh -n`、`git diff --check` 均通过。
- 原始执行 runner 未提供可独立核对的分角色耗时字段，因此保留“未单独保留”，不补写估算值。
