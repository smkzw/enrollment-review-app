# 会议输出：r05-frequency-consumption-20260916 - evidence_single_object

## 输出

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本轮读取：计划 T3–T7 现行段、`T3_CUMULATIVE_PROFILE_20260913.md`（71 行全读，含最新补验）、`patient_profile_service.py`（409 行全读）、`source_conflict_successors.py`（45 行全读）；`source_reference_successors.py` 与 `fact_publication_service.py` 闭合段沿用本会话早前全读（后者自 pass-1 后未见结构性变更——`_publish_facts` 链头/继承与 `_validate_referential_closure` 门在场）。仅源码事实；owner 决定。

---

### A. 剩余建设阻塞（有序，含证据）

1. **R06：24 项历史事件引用的原件核对与合法重建**（当前唯一有真实数据 blocker 性质的项）。证据：`T3_CUMULATIVE_PROFILE_20260913.md:7-9`（重放仍 516/46/22/9/130，24 项事件引用不在当前事实集；同稳定身份新事实**无** `inherited_from_fact_id` 且不含全部旧定位——“不能宣称真实 Profile 已恢复”）；`:53-57` 逐字段差异（23 项同页同摘录但 locator_id/target_id/created_at/text_start/end 不同；2 项出生日期跨文档版本/页/OCR/文本哈希——“不能把不同原件上的同值自动当作来源等价”）；根因已定位（:57，批次发布 vs 累计消费的衔接缺失）。**后继机制代码已存在且闭合**：`source_reference_successors.py:9-63`、`source_conflict_successors.py:9-45`、发布闭包门 `fact_publication_service.py:290-331`、`patient_profile_service.py:277-331`。剩余是**操作型建设**：24 项逐一原件 QC（含 2 项出生日期的视觉复核，:9），再从合法受控入口以显式继承/后继路径重建，使闭包门自然通过。禁止伪造旧继承或把历史坏行当“现代码损坏”的证据——现源码无缺失。
2. **已声明但未编码的频次解读**（真实方案声明时才成为建设项）：无界/部分统计地平线（`frequency_quantified_periods.py:46-49`）、日历多单位周期（73-80）、滑动部分窗（92-94）、外层 TimeConstraint 组合（`frequency_total_resolution.py:20-21`）、governing-initial 选链与跨链聚合排序（`repeat_result_resolution.py:187-188`＋`repeat_observation_ordering.py:19-21`）。现状全部 fail-closed 为显式原因码。**本轮无证据表明当前方案已声明这些形态**——标为"unverified need"，非当前节点 blocker；出现时按既有模式扩展，不需要新抽象层。
3. **T5 尾项**（按计划现行段：批量重新识别运行验证、耗时/费用估算展示、复杂观察选择收尾）——计划文本如此记载，本轮未逐一回查源码状态，标为**部分未核验**；建议 owner 以 PROJECT_CONTEXT 对照确认后收口。
4. **声明性收尾**：`claims_complete=false` 维持（计划 T3 段）；T6/T7 无独立建设项，属下列验证阶段。

### B. 最终验证工作（与建设分列，用户已禁令阶段测试至建设完成）

1. T4 Phase5/5.5 临床退出：新正式隔离任务（当前双模型）、有效金标冻结、逐项原件 QC、三档浏览器（ego）验证——计划 T4 段全列。
2. 整链集中运行：上传→页任务→覆盖→事实/Profile→组件审核/行动/报告，含 R06 重建节点的真实 Profile 生成与 24 项引用闭包复核。
3. 方法采用批准链实测（类型化评测清单→用户采用回执→逐任务授权签发）——现链路源码已通（`qualified_review_command`），未签发。
4. T7 交付/清理/备份回读。

### C. 抽象合同评估

**不建议新增抽象合同**。量化期间、链分解、逐初查政策、辅助频次的机制均已存在且 fail-closed；B2/B3 的扩展是同模式的具体解释分支，遇到真实声明再写；B1 是数据 QC＋受控重放，不是合同问题。当前边际收益最大的动作是关闭 B1 的操作链，然后转入 B 阶段集中验证。

**未核验声明**：T5 尾项的逐一源码现状、24 项之外的节点是否存在同类引用缺口（仅核对了文档记载的那一节点）——均如实标注，不虚构工作。本审阅独立建议，owner 决定；不构成验收。会话保持可续。
