# Phase 5 方案语义 fallback 对照验收、候选质量拒绝

日期：2026-09-01  
状态：`claims_complete=false`  
任务状态：`in_progress`

## 本轮边界

- 继续使用同一只读冻结 SAR EX-06 输入；未恢复失败 SAR 作业，未创建正式 SAR V2 草稿。
- D001 控制任务继续停在第 19 个已完成发现包之后，未运行第 20 包。
- 模型间只比较完全隔离的整候选；未续接跨供应商会话、未拼接候选或缓存。
- 没有增加 SAR、D001、疾病、药物、量表、条款编号或时间点特异规则。

## 接受的路由设计

- 复杂方案语义任务：`GLM-5.3-Flash high -> MTPLX medium -> DeepSeek V4 Flash high`。
- 单规则、单批、短提示任务：`MTPLX medium -> DeepSeek V4 Flash high`。
- 路由只按父规则数、批次数和输入令牌估算分级；项目名称与临床内容不参与选路。
- 修复一个关键根因：有 `final_draft` 不代表成功。只有状态为“可以进入审阅”、终稿存在且最终完整门禁 `publishable=true` 时才停止回退；否则丢弃整个候选并进入下一供应商。
- 为限制真实等待时间，复杂任务的 MTPLX fallback 只评估一次完整首稿，不追加最长 600 秒的语义修订；短任务 MTPLX 与 DeepSeek 允许一次定向修订；GLM 复杂主路由保留完整公平修订预算。

## 同源真实结果

| 候选 | 墙钟时间 | 调用 | 当前完整门禁问题 | 处置 |
|---|---:|---:|---:|---|
| GLM-5.3-Flash high 分段合并 | 分段恢复与修订分开记录 | 3 次恢复/修订调用 | 6 | 拒绝 |
| MTPLX medium 整候选 | 1082.56 秒 | 2 | 12 | 拒绝 |
| DeepSeek V4 Flash high 整候选 02 | 374.19 秒 | 4 | 2 | 拒绝 |
| DeepSeek V4 Flash high 整候选 03 | 309.54 秒 | 2 | 9 | 拒绝 |

- MTPLX 第二次修订在 600.002 秒超时；该证据直接支持复杂 fallback 不再追加 MTPLX 语义修订。
- DeepSeek 较快，但两个独立整候选的问题数从 2 到 9 波动；不能把最好一次当作稳定质量证明。
- 通用中文列举提示消除了 DeepSeek 早期把顿号/逗号术语清单改成“或”分支的错误，但新输出暴露例外范围、指标来源和时间限定问题。提示修复不得绕过完整门禁。
- 四个候选均为 `publishable=false`，不发布、不写入正式草稿。

## 确定性证据

- 比较器：`artifacts/phase5-acceptance/20260901/semantic-model-fallback-comparison-ex06-20260901/verify_comparison.py`。
- 结果：`comparison-results.json` 中 `evidence_integrity_passed=true`、`semantic_acceptance_passed=false`。
- 比较器重新加载冻结方案输入和各候选水合草稿，以当前生产门禁离线重放；四个运行的模型身份、冻结哈希、问题列表及可发布状态均一致。
- 路由与确定性核验聚焦回归：`24 passed`。
- 协议与 Agent 扩展回归：`1373 passed, 1 failed`；唯一失败仍为既存 D001 只读检查点提示词 SHA 漂移，旧检查点未修改。
- 编译、`compileall`、`git diff --check` 通过；仓库未配置 Ruff 可执行文件，因此没有虚构 lint 通过结论。
- 治理执行审计 `phase5-mtplx-whole-candidate-comparison-20260901` 通过，`errors=[]`、`warnings=[]`；过程提示、输出和日志已正式归档到 `archives/execution/`。

## 清理

- 删除未登记的临时恢复提示，保留同会话恢复日志和正式执行报告。
- 删除本轮验收目录中的 Python `__pycache__`；未删除模型原始响应、调用台账、门禁结果、冻结合同或失败证据。

## 下一安全动作

不再对同一 EX-06 反复调用模型。下一步先用通用、非项目特异的失败类型收敛提示合同和确定性门禁，再选择新的异构冻结父规则做一次独立 GLM 主路由验收；只有得到可发布候选且时效可接受后，才允许新建 SAR V2 方案解构作业。D001 第 20 包继续禁止运行。
