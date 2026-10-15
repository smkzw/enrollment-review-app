装配链闭合（qualified_binding_selection:476-537 → v7 消费 → 条件选择 v2 → resolution v2 约束）。所有证据已收集，以下为完整会议输出。

# Conference Output: r05-no-repeat-source-20260916 - evidence_single_object（第四轮：本次节点复查计数）

## Output

### 0. 角色与限制声明

继续同一有界只读角色（回退 `zcode`/`GLM-5.3-Flash`，effort max）：仅源码读取，未修改、未运行测试/导入/对象构造/服务/DB/浏览器。**静态审阅不是运行或临床验收**。收到 runner 说明：O-a 建议不采纳的理由成立（空集会通过子集检查反而放行，维持错误向上失败）、O-b 维持上游冻结校验——均无异议；前轮回执信息不作为本轮依据，本轮全部按现版代码独立核验。

### 1. 变更链逐项核验（对照九项审重点，file:line 证据）

**版本链全部对齐**：观察合同/任务/提示/摘要 v4（observation_relation.py:12 `observation-relation/v4`、receipts:13/101）、观察消费 v7（qualified_observation_relation.py:12）、资格消费 v27（qualified_binding_selection 合同 :24 默认）、计算 v31 / 发布 v13（frozen_review_calculation.py:27、frozen_review_publication.py:31）、序列约束 v2（repeat_series_constraints.py:135）且 resolution:93 已同步 `!= "repeat-series-constraints/v2"`——**无残留 v1 检查**（全库仅此一处消费该版本串）。

**(1) 辅助原文混成结果 — 未发现通路。** 合同层辅助成员独立排序、禁止与本项身份/任务/资料版本混合（observation_relation.py:53-63）；LLM 校验要求 reviewed_fact_ids 恰等于本项结果记录（llm:127），辅助归属单独核对（:143-155）；消费层 operand_pairs 仅来自 group.members（v7:247-258），辅助关联只产出 `acquisition_group_id` 作用域归属（:161-166），从不成为结果操作数；条件选择侧辅助身份仅取 ancillary 条件的 initial/preceding/target 角色（input:49-56、:70-78）。

**(2) 漏计/重复计数 — 未发现。** 计数对象是角色为 repeat 的采集组（constraints:31），每组一次（组 ID 唯一、图分组互斥）；`counted_repeats` 仅含全组成员一致归属 current_episode 的组（:58-67）；初查组不入计数。未知/其他节点组不计入且令覆盖不完整 → UNKNOWN（:73-74 + repeat_observation_count.py:40-41），而已计组数超上限仍可判 FALSE（count:38-39）——部分集可证超限、不可证合规，与声明一致。

**(3) 未知当其他节点 — 已防住。** 双路一致才进入 agreed_memberships 且排除 unresolved（receipts:70-73）；消费层仅 agreed 项经双路原文引用+来源资格复核后才入 qualified_memberships（v7:128-138）；constraints 只接受 current/other 两值，unresolved 混入直接报错（:55-57）；组内任一成员未覆盖或值不一 → 组级 unresolved（:58-62）。无任何“未知→其他节点”的推断路径。

**(4) 原文引用不匹配 — 三层设防。** LLM 校验逐条 quote 必须是本记录 (fact_id, locator_id) 摘录的子串（llm:138-142）；消费层对双路 quote 重新执行 `quote_reasons`（含记录/身份/属性/原文一致及直接选择拒绝理由，v7:72-101、:133-134）；合同要求非 unresolved 必带 quotes 且引用本条自身（contract:169-177）。

**(5) 节点说明已绑定。** workflow_stage 取自冻结 ReviewContext 的正式 episode 节点（input:84-85），v4 合同强制其与成员 episode 的节点身份一致（contract:43-47），pair_id 绑定全部内容哈希（input:111）；计数必须携带 `episode_sha256=canonical_hash(episode)` 否则 UNKNOWN（constraints:68-69）；消费方法绑定 consumer v27+提示 v4+摘要 v4+路由（v7:20-26）；准备重建全量比对（receipts:22-29）。

**(6) 同组冲突不被吞。** 组内归属冲突 → unresolved（:58-62）；组内日期不一致 → `group_date` 返回 None → `repeat_date_unverified`（:88-98、:126），注释明示按精度与日期比较而非字面；数值冲突沿用 atom calc 既有闸门；双路归属分歧 → 不入 agreed → 覆盖不完整。无静默吞并。

**(7) 旧哈希/版本许可偷渡 — 无通路。** 回执重建后全 payload 等值比对（receipts:27-28）；旧版观察上下文在消息构建即拒（llm:53-54）、旧结果不得补入 episode_memberships（llm:136-137）、旧上下文不得补 workflow_stage（contract:48-49）；约束版本 v2 单点强校验（resolution:93）；序列化器对 None/旧版本键的省略保持历史哈希不变（contract:30-39、:191-199）。

**(8) 新方法无批准不自动采用。** 计数仅在方案冻结 `count_scope=="per_current_episode"` 时激活（constraints:66；LLM 侧同一来源 llm:43、:131-132）；归属仅来自双路一致的原文声明，上传归属/日期窗口/文件排列被提示与实现双重排除（llm:101-107；代码无任何自动分组路径）；无归属证据时覆盖不完整，只有明确原文才可归属（contract:169-177）。

**(9) 相邻调用兼容。** resolution:93 已同步 v2；`evaluate_repeat_count` 新签名由 constraints 两处正确调用（:71-75、:82-86）；atom calc 消费的 `count_result`/`time_checks` 键未变；`counted_repeat_group_ids`/`acquisition_episode_memberships`/`count_scope_complete` 为审计保存字段（随 observation 哈希封存，resolution:172），无下游误用；v7 输出经 qualified_binding_selection:485-493 装配，键位与 resolution 读取一致。

**采用路径与初查口径未变**：per_initial_acquisition 仍要求 `one_initial_series`（constraints:51-52、:77-86），结果选择/期限/采用全部沿用原函数；per_current_episode 的多初查不阻断节点计数语义（计数按节点归属而非初查归属，合理），初查唯一性仍由采用路径独立把守。

### 2. 缺陷结论

**本轮未发现确证缺陷**（不凑数量）。一条设计耦合观察，非缺陷：节点计数 UNKNOWN 会经每条 repeat 的 count 操作数使全部 checks 置为 unverified，从而阻断 use_single/use_last/combine 的复查采用（resolution:125-137、:158-165）——这是“未知成员不能证明未超限”的正确传导（本节点可能还有未归知的复查时不应采用），且 retain_initial 采用路径不受影响（selection:67-71 早退），与既定设计一致。

### 3. 未验证项声明

全部为静态阅读结论：双路归属在真实方案上的端到端行为、`_evaluate_atomic` 时间窗对 other_episode 复查的适用性（期限检查按系列语义不按节点，code 按声明“所有原期限路径保持”实现，未运行验证）、v27 资格工厂与 v31/v13 门的具体拦截行为，均未经运行证实。多初查、聚合排序、多次许可仍未声称完成，本轮代码与该边界一致（聚合+排序仍被 reconcile 组合闸门挡为 UNKNOWN，未在本轮读取集重开）。
