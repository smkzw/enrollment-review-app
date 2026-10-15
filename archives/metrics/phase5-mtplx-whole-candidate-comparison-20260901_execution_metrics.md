# Execution Metrics: phase5-mtplx-whole-candidate-comparison-20260901

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `cursor` | `default` | completed | 未单独记录 | 未单独记录 | 固定冻结输入与隔离边界；Codex 有选择采纳 |
| `worker_02` | `cursor` | `default` | recovered | 未单独记录 | 未单独记录 | 首轮截断自报撤销；同会话修复脚本 |
| `worker_03` | `cursor` | `default` | completed | 未单独记录 | 未单独记录 | 建立确定性核验；最终结果由 Codex 重放更新 |

## Product Run Metrics

| 候选 | 完整尝试 | 用时 | 调用 | 当前门禁问题 | 可发布 |
|---|---:|---:|---:|---:|---|
| GLM-5.3-Flash high 分段合并 | 1 | 分段检查点恢复与修订分开记录 | 3 次恢复/修订调用 | 6 | 否 |
| MTPLX medium 整候选 | 1 | 1082.56 秒 | 2 | 12 | 否 |
| DeepSeek V4 Flash high 整候选 02 | 1 | 374.19 秒 | 4 | 2 | 否 |
| DeepSeek V4 Flash high 整候选 03 | 1 | 309.54 秒 | 2 | 9 | 否 |
