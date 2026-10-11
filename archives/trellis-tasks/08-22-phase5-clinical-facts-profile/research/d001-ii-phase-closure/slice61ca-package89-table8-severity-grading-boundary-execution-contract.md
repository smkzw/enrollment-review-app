# D001 II 第 89 包表 8 不良事件严重程度分级边界执行合同

## 目标

为当前 131 包冻结计划第 89 包 `body.t13.r0-r5` 建立最小模型外来源闭包、确定性反例门禁和可恢复准备产物。只处理表 8 的列关系及 1–5 级严重程度定义，不发布预筛、筛选或基线控制点，不进入受试者、OCR、Patient Profile 或前端。

## 当前权威来源

- 冻结计划：`artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`
- 计划标识：`papl-40b1237a22e538a278b4fd5e`
- 计划 SHA-256：`f0aa7e4bccad782ad5472c1f446f079e26343f694ad3ddca401bfbef89f38250`
- 当前包：ordinal `89`，package id `pap-2a23364a794edb74a0db5e2b`
- 前包：ordinal `88`，package id `pap-c83571533332e92881f82dd1`
- 后包：ordinal `90`，package id `pap-969cb2554a2487b656fbbb20`

## 拥有来源

- `body.t13.r0`：表头“分级｜类型｜定义（满足列举的任一情况）”。
- `body.t13.r1-r5`：1–5 级定义。`r1-r3` 保持分级、类型、定义三个有值单元格的行内绑定；`r4/r5` 的类型单元格 `c1` 在源文档中为空，仅 `c0` 分级与 `c2` 定义有值，不得虚构类型或把空单元格解释为列合并。同一行定义中的分号分支由表头明确为任一情况，不得改成全部同时满足。

## 只读附加来源

- `body.p1084-p1086`：第 88 包拥有的严重程度评估标题、CTCAE 6.0 参考与回退方法、表 8 入口；仅用于闭合表格用途和适用路径，不转移所有权。
- `body.p997-p1001` 中的 `p997/p998/p999/p1000/p1001` 与 `body.p1014`：SAE OR 总纲及死亡、实际危及生命、残疾/功能丧失、住院/延长住院、其他重要医学事件标准；仅用于阻断表 8 等级和 SAE 严重性机械等同，不得进入本包候选或重新拥有 SAE 规则。

## 必须保留的语义

1. `r0` 是三列表头；`r1-r3` 的分级、类型、定义必须按行绑定；`r4/r5` 必须保留空 `c1` 类型单元格这一源结构事实，仅以 `c0` 与 `c2` 的有值文本形成摘录。不得串列、错位、把类型当定义、虚构类型或声称类型与定义发生列合并。
2. “定义（满足列举的任一情况）”使每个等级定义内的分号分支保持 OR；不得强化为全部同时满足。
3. 1 级无症状/轻微、仅为临床或诊断所见、无需治疗是并列备选；2 级治疗要求与工具性日常生活活动受限是并列备选。
4. 3 级的严重或重要医学意义、住院或延长住院、致残、自理性日常生活活动受限是并列备选；“但不会立即危及生命”仅修饰第一分支，“并未卧床不起”仅修饰自理性活动受限分支，两者均不得扩展到其他分支或整级。
5. 4 级包含危及生命或需要紧急治疗；5 级是与不良事件相关的死亡。不得删去“与不良事件相关”。
6. 等级是严重程度/强度分级，不等于 SAE 严重性；相同词语不能直接替代 `p997-p1001/p1014` 的 SAE 判断。
7. `required_candidate_source_refs=[]`，拥有和只读附加来源全部为零候选；任何预筛、筛选、基线候选或入排结论均为越界。

## 允许写入

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package89_table8_severity_grading_boundary.v1.json`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61ca_package89_table8_severity_grading_boundary.py`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61ca-package89-table8-severity-grading-boundary-parent-checklist.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n-prepare/d001-ii-package89-table8-severity-grading-boundary/`

## 禁止事项

- 不修改共享运行器、正式入排矩阵、冻结计划、协议解析、受试者、OCR、Patient Profile 或前端。
- 不调用临床语义模型，不发布控制点，不把第 88/78/79 包只读来源变成拥有来源。
- 不提前吞并第 90 包及以后因果关系、预期性或报告流程。
- 不把 CTCAE、表 8 严重程度分级、SAE 严重性、因果关系或报告路径相互替代；不得由本包反向改写第 88 包的 CTCAE 6.0 版本、“可参考”强度或“CTCAE 特定描述→方案定义→表 8 通用准则”的回退顺序。

## 完成证据

- 当前计划、包标识、来源指纹与六个表格来源逐项一致。
- 只读附加来源完整进入模型外提示且所有权不转移。
- 专项反例覆盖列错位、OR 反转为 AND、分支限定外溢、等级文本删改、严重程度与 SAE 混同及候选升级。
- dry-run prepare、专项测试、相邻/Phase 回归、方案与 Agent 回归、治理测试、JSON、差异检查和执行审计通过。
- `claims_complete=false`，明确下一包和未完成边界。
