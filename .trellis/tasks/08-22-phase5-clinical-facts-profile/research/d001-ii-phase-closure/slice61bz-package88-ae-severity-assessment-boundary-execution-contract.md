# D001 II 第 88 包不良事件严重程度评估边界执行合同

## 目标

为当前 131 包冻结计划第 88 包 `body.p1084-p1086` 建立最小模型外来源闭包、确定性反例门禁和可恢复准备产物。只处理不良事件严重程度评估方法与表 8 入口，不发布控制点，不进入受试者、OCR、Patient Profile 或前端。

## 当前权威来源

- 冻结计划：`artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`
- 计划标识：`papl-40b1237a22e538a278b4fd5e`
- 计划 SHA-256：`f0aa7e4bccad782ad5472c1f446f079e26343f694ad3ddca401bfbef89f38250`
- 当前包：ordinal `88`，package id `pap-c83571533332e92881f82dd1`
- 前包：ordinal `87`，package id `pap-2479acb2cc6c17a411ff2a3e`
- 后包：ordinal `89`，package id `pap-2a23364a794edb74a0db5e2b`

## 拥有来源

- `body.p1084`：不良事件的严重程度评估（结构标题）。
- `body.p1085`：研究者可参考 CTCAE 6.0；CTCAE 对已收录 AE 给出 1–5 级特定描述；未收录 AE 若方案有具体定义则按方案定义，否则使用下列通用准则。
- `body.p1086`：表 8 不良事件严重程度分级（结构标题/表格入口）。

## 只读附加来源

- `body.p1083`：上一层“不良事件的评估”章节标题，仅用于层级闭合。
- `body.t13.r0-r5`：第 89 包拥有的表 8 表头和 1–5 级定义，完整只读进入以闭合“下列准则”，不得转移所有权或由第 88 包发布等级规则。
- `body.p997`、`body.p999`、`body.p1000`、`body.p1014`：第 78–79 包 SAE 严重性 OR 总纲、实际危及生命定义、永久或严重残疾或功能丧失标准及其他重要医学事件判断，仅用于防止严重程度等级与 SAE 严重性混同，不得进入本包候选或重新拥有 SAE 规则。

## 必须保留的语义

1. `p1084/p1086` 仅提供结构归属，不独立形成控制点；`p1085` 保持 `post_treatment_execution`。
2. CTCAE 版本必须保持 `6.0`，不得替换为其他版本或省略版本。
3. CTCAE 已收录 AE 的特定 1–5 级描述、未收录 AE 的方案定义优先、无方案定义时才使用表 8 通用准则，必须保持条件层级和回退顺序。
4. “可参考”不得无依据改成“必须一律采用”，也不得弱化为任选任意标准。
5. 表 8 具体等级由第 89 包拥有；第 88 包只能携带只读闭包并指向表格入口，不能自行生成等级规则。
6. 严重程度是强度/分级，不等同 SAE 严重性；3 级的“严重”或住院字样、4 级危及生命、5 级死亡均不能机械等同或替代第 78–79 包 SAE 判定。
7. `required_candidate_source_refs=[]`，拥有来源和只读附加来源均不得发射候选；任何预筛、筛选、基线候选或入排结论均为越界。

## 允许写入

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package88_ae_severity_assessment_boundary.v1.json`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61bz_package88_ae_severity_assessment_boundary.py`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61bz-package88-ae-severity-assessment-boundary-parent-checklist.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n-prepare/d001-ii-package88-ae-severity-assessment-boundary/`

## 禁止事项

- 不修改共享运行器、正式入排矩阵、冻结计划、协议解析、受试者、OCR、Patient Profile 或前端。
- 不调用临床语义模型，不发布控制点，不把相邻包只读来源变成拥有来源。
- 不读取或采用历史 137/217 包序号作为当前权威，不按 ordinal 以外的历史映射重接来源。
- 不把 CTCAE、表 8、SAE 严重性、因果关系、预期性或报告流程相互替代。

## 完成证据

- 当前计划、包标识、来源指纹与 3 个拥有来源逐项一致。
- 只读附加来源完整进入模型外提示，且所有权不转移。
- 专项反例覆盖版本漂移、回退顺序反转、表 8 提前拥有、严重程度/严重性混同和候选升级。
- dry-run prepare、专项测试、相邻/Phase 回归、方案与 Agent 回归、治理测试、JSON、差异检查和执行审计通过。
- `claims_complete=false`，明确下一包和未完成边界。
