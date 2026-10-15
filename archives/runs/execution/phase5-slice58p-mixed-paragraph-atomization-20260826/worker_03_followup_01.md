# Execution Output: phase5-slice58p-mixed-paragraph-atomization-20260826 - worker_03

## Boundary And Context Check

- 仅写入新目录：`artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/`
- 未修改 58p 诊断目录、应用代码、测试、任务记录、临床源文件、受试者、浏览器文件或 runner 报告。
- 未调用语义 Provider、未运行全部包、未启动受试者/浏览器/视觉/独立测试。
- `claims_complete=false`；不作最终验收。

## Work Performed

已完成真实 D001 II 期全文重建产物复核、源身份检查、全部衍生原子回放、四个指定混合段落检查，以及第 79、80、111 包身份/成员对照。

当前计数：

| 项目 | 当前 58q | 5.8o 基线 | 首个 58p | 相对 5.8o |
|---|---:|---:|---:|---:|
| 结构块 | 3581 | — | — | — |
| 期别图块 | 3405 | — | — | — |
| 覆盖单元 | 1846 | 1840 | 1857 | +6 |
| 未决目标 | 1303 | 1298 | 1304 | +5 |
| 冻结包 | 138 | 137 | 138 | +1 |

相对首个 58p：覆盖单元 `-11`、未决目标 `-1`、包数 `0`。该差异已保留并标记为需父任务复核，未因数量变小而判定正确。

全部 9 个衍生原子均精确、连续、无重叠地回放到父段：

- `body.p729`：`0–223`、`223–362`
- `body.p801`：原单元直接保留，`0–58`
- `body.p815`：`0–11`、`11–74`、`74–161`
- `body.p1237`：`0–15`、`15–100`、`100–160`、`160–208`

保护性词组检查 5/5 通过：比例/剂量、期别括号、访视列表均留在完整强句中。

## Artifacts And Evidence

目录：

`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/`

关键证据：

- [coverage_manifest.json](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/coverage_manifest.json)
- [frozen_phase_plan.json](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/frozen_phase_plan.json)
- [rebuild-summary.json](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/rebuild-summary.json)
- [diff-qc.json](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/diff-qc.json)
- [verification-results.json](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/verification-results.json)
- [mixed-paragraph-parent-reviews.json](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/mixed-paragraph-parent-reviews.json)
- [package-0079-review.json](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/package-0079-review.json)
- [package-0080-review.json](/Users/smkzw/Documents/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/package-0080-review.json)
- [package-0111-review.json](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/package-0111-review.json)
- [source-snapshot.json](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/source-snapshot.json)
- [source-identity-check.json](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/source-identity-check.json)
- [recovery-checkpoint.json](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/recovery-checkpoint.json)

包身份均相对两个历史计划发生变化：

- 79：当前 `pap-2e662c2807a2441886f59ff0`，成员 `body.p806–p813`
- 80：当前 `pap-15734206834cfab1e9acf554`，成员 `body.p814`、`body.p815` 三个原子、`body.p816–p818`
- 111：当前 `pap-b1e63af74b347b8a6f54b612`，成员 `body.p1236` 及 `body.p1237` 三个原子

所有包均记录 `historical_semantic_output_reused=false`。第 79 包发现的历史语义目录已明确排除。

## Commands And Observations

执行了：

- `PYTHONPATH=. .venv/bin/python` 内联真实重建流程：`register_source_artifact`、DOCX 结构提取、期别图构建、Ⅱ期投影、全文覆盖清单构建、冻结包计划。
- `PYTHONPATH=. .venv/bin/python` 内联确定性验证：读取当前/5.8o/首个 58p JSON，进行契约重载、源哈希、字符范围回放和包身份比较。
- `jq`/`find` 只读检查证据文件、包成员和 QC 字段。

源副本：

- SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- 大小：`405567` bytes
- mtime_ns 重建前后均为：`1779871799537588300`
- mtime UTC：`2026-05-27T08:49:59.537588+00:00`
- 结果：SHA、大小、mtime 均未变化；若任一变化，验证脚本 fail-closed。

独立确定性断言：通过。

## Blockers Or Missing Environment

无环境阻塞。

仍需父任务复核：

- `1846/1303/138` 相对两套基线的计数差异；
- `body.p1237` 原子在第 111 包及相邻包之间的归属；
- 四个父段的临床边界观察。

## Rerun Requests Or Next Step

当前无需重复确定性重建。请父任务读取 `diff-qc.json`、`mixed-paragraph-parent-reviews.json` 和三个包评审文件；确认计数及包归属后，再单独授权必要的有限语义复核。
