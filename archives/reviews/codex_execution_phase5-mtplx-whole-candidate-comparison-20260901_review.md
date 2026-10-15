# Codex Execution Review: phase5-mtplx-whole-candidate-comparison-20260901

## Verdict

`accept_evidence_reject_candidate`

接受本执行包作为 MTPLX 复杂任务 fallback 的负向性能与质量证据；拒绝 MTPLX 候选进入方案草稿。该结论不代表 Phase 5 完成。

## Worker Outputs

- `worker_01` 正确固定冻结 EX-06 输入、候选隔离和 D001 暂停边界；报告尾部 Trellis 询问不属于分配任务，不作为结论。
- `worker_02` 首轮曾把分页标记写入脚本并错误自报完成；同一会话恢复后修复脚本。Codex 未采信首轮自报，重新编译并完成真实 MTPLX 调用。
- `worker_03` 建立模型外核验器；其早期“GLM 当前门禁可发布”检查与本轮比较目标不一致，已从最终核验器移除。最终 MTPLX 核验正确保持来源闭包和语义验收失败。

## Manager Assessment

本路线没有执行管理者，由 Codex 直接验收。临时恢复提示未登记且属于冗余过程文件，恢复日志保留，临时提示已删除。

## Codex Independent Verification

- MTPLX 真实整候选：1082.56 秒，2 次调用，第二次 600.002 秒超时；当前生产门禁重放 12 个问题，`publishable=false`。
- DeepSeek V4 Flash high 两个独立整候选：374.19 秒/2 个问题与 309.54 秒/9 个问题，均 `publishable=false`，显示速度较好但质量有波动。
- GLM 分段合并候选：6 个问题；局部修订扩大为 26 个问题，已拒绝。
- `semantic-model-fallback-comparison-ex06-20260901/comparison-results.json`：四个候选模型身份、冻结哈希和门禁重放一致；`evidence_integrity_passed=true`、`semantic_acceptance_passed=false`。
- 路由根因修复：只有 `status=可以进入审阅`、存在终稿且最终门禁 `publishable=true` 才能停止回退；不可发布草稿必须整候选丢弃并继续下一供应商。
- 延迟边界：复杂任务 MTPLX 只运行完整首稿，不再追加最长 600 秒的语义修订；短任务 MTPLX 和 DeepSeek 各允许一次定向修订；GLM 复杂主路由保留完整公平修订预算。
- 聚焦回归：202 项通过。

## Cleanup Decision

保留正式提示、执行输出、运行日志和验收产物；删除未登记的临时恢复提示及 Python 缓存。待本轮治理审计通过后再按 guard 的正式清理命令归档，不手工删除证据。
