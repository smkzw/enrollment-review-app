# Execution Metrics: phase5-slice60zu-laboratory-action-preservation-rerun-20260828

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `cursor-cli` | `auto` | completed | 145.059s | read-only | 门控与提示隔离审查通过，提出候选动作表达残余风险 |
| `worker_02` | `cursor-cli` | `auto` | completed | 348.176s | read/write | 重建第 70–71 包并冻结动作映射，无提示泄露 |
| `worker_03` | `cursor-cli` | `auto` | completed after same-session follow-up | 51.422s + 32.467s | read-only | 工件完成后复核通过，允许一次有界调用 |

## Product Model Call

| Provider | Model | Effort | Calls | Duration | Result |
|---|---|---|---:|---:|---|
| `mtplx` | `mtplx-qwen38-27b-optimized-quality` | `medium` | 1 | 112.78853s | 3 条处置、0 候选；动作覆盖门控拒绝，未发布 |

## Verification

- 执行路线：三路均为 `cursor-cli/auto`，无 fallback。
- 模型路线：本地 MTPLX medium，严格结构输出，`max_retries=0`。
- 聚焦回归：`181 passed, 5 warnings in 36.42s`。
- 完整方案模块：`944 passed, 58 warnings in 135.29s`。
- Python 编译、JSON 解析和限定范围差异检查通过。
- Hermes 执行审计和评审门通过；执行过程已归档。
- 发布边界：`claims_complete=false`，`control_points_published=false`。
