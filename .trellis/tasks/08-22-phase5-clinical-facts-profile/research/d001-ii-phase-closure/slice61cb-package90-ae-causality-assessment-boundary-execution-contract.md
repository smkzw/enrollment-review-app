# D001 II 第 90 包不良事件因果关系判断边界执行合同

## 目标

为当前 131 包冻结计划第 90 包 `body.p1087-p1097` 建立最小模型外来源闭包、确定性反例门禁和可恢复准备产物。只处理治疗后不良事件与试验用药品的因果关系综合判断，不发布预筛、筛选或基线控制点，不进入受试者、OCR、Patient Profile 或前端。

## 当前权威来源

- 冻结计划：`artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`
- 计划标识：`papl-40b1237a22e538a278b4fd5e`
- 计划 SHA-256：`f0aa7e4bccad782ad5472c1f446f079e26343f694ad3ddca401bfbef89f38250`
- 当前包：ordinal `90`，package id `pap-969cb2554a2487b656fbbb20`
- 前包：ordinal `89`，package id `pap-2a23364a794edb74a0db5e2b`
- 后包：ordinal `91`，package id `pap-87e89271165354d285b2faa1`

## 拥有来源

- `body.p1087`：因果关系判断标题，仅作结构。
- `body.p1088-p1089`：五级相关性结论与研究者基于五个评价要点综合判断并提供依据的总纲。
- `body.p1090-p1094`：时间关系、已知性、去激发、再激发、其他合理解释五个评价要点。
- `body.p1095`：分类参照句及统计分析时前三类归为相关。
- `body.p1096`：SAE 由研究者和申办者共同判断；意见不一致时任意一方判断相关即属报告范围。
- `body.p1097`：表 9 入口标题，仅作结构。

## 必须核对并保留的语义

1. 五个评价要点是综合评价输入，不得被改为全部满足、固定计分、单项充分条件或机械决策树；去激发/再激发可能未进行或不适用的含义由第 91 包表 9 核对。
2. `p1095` 原文写“可参照表7”，紧接 `p1097` 及下表标题均为“表9”。必须保留该方案内部不一致并标为需要核对，不得静默改成表9，也不得把真正的第 82 包表7继发事件规则吸入本包。
3. 统计分析相关分组只包含“肯定有关、很可能有关、可能有关”；不得扩大到“可能无关”或“无关”，也不得反推个例报告规则。
4. `p1096` 的共同判断不等于双方一致。意见不一致时，研究者或申办者任一方判断相关即进入报告范围；不得把 OR 改为 AND，也不得把“报告范围”改成“最终确认相关”。
5. 因果关系、严重程度、SAE 严重性、预期性和报告时限是不同维度，不得相互替代。
6. `required_candidate_source_refs=[]`；拥有和只读附加来源均不得发射入排候选。

## 来源闭包建议

- 第 91 包 `body.t14.r0-r7` 应只读进入，以闭合 `p1095/p1097` 指向的实际因果关系评价表及 `+/-/±/++/-?` 注释；所有权和候选发射权不转移。
- 第 89 包表 8、第 78–79 包 SAE 严重性、第 92 包预期性及更后报告流程仅在确有防混同必要时以最小只读锚点进入，不得整包反向注入。

## 允许写入

- `configs/representative_group_package90_ae_causality_assessment_boundary.v1.json`
- `test_slice61cb_package90_ae_causality_assessment_boundary.py`
- `slice61cb-package90-ae-causality-assessment-boundary-parent-checklist.md`
- `slice59n-prepare/d001-ii-package90-ae-causality-assessment-boundary/`

以上路径均位于 `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/`。

## 禁止事项

- 不修改共享运行器、正式入排矩阵、冻结计划、方案解析、受试者、OCR、Patient Profile 或前端。
- 不调用临床语义模型，不发布控制点，不改变第 89/91 包所有权。
- 不把“表7”静默校正为“表9”，不把真正的表7继发事件规则作为因果评价表。
- 不提前吞并第 91 包表格所有权、第 92 包预期性或第 93 包以后报告流程。

## 完成证据

- 当前计划、包标识、11 个拥有来源及必要只读来源逐项一致。
- 专项反例覆盖五要点 AND 化/计分化、表号静默纠正、统计分组扩大、双方判断 AND 化、报告范围升级为最终相关、跨维度混同及候选升级。
- dry-run prepare、专项/相邻/Phase、方案与 Agent、治理、JSON、差异与执行审计通过。
- `claims_complete=false`，明确下一包和未完成边界。
