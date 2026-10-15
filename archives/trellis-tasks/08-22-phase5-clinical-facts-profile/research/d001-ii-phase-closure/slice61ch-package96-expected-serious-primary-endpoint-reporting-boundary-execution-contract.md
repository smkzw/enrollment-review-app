# Slice 61ch / Package 96 执行合同：预期严重不良反应与主要疗效终点报告边界

## 目标

为 D001 II 当前 131 包冻结计划第 96 包建立最小模型外来源闭包。只恢复 `body.p1136-p1137` 在申办者快速报告章节中的原文职责、条件强度和跨包列表关系；不调用临床语义模型，不发布控制点，不进入受试者资料、OCR、Patient Profile、浏览器或视觉工作。

## 权威来源

- 当前冻结计划：`artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`
- `plan_id`：`papl-40b1237a22e538a278b4fd5e`
- 第 96 包：`pap-8dd6a669bdee4e77cc1f0b63`
- 自有来源：
  - `body.p1136`：`严重但属预期的不良反应；`
  - `body.p1137`：`当以严重不良事件为主要疗效终点时，不建议申请人以个例安全性报告形式向国家药品审评机构报告。`
- 前接第 95 包只读来源：`body.p1133-p1135`，用于保留“以下情况一般不作为快速报告内容”引导及列表前两项。
- 定义只读来源：`body.p1018-p1019`，用于区分 SUSAR 三维定义及《研究者手册》的预期性参考地位，不转移第 80 包所有权。
- 第 97 包 `body.p1138-p1149` 仅保留所有权边界，不进入本包提示、配置或测试正向语义。

## 临床语义边界

1. `p1136` 是“严重 AND 属预期”的不良反应，不得弱化为“严重 OR 属预期”，不得把“预期”解释为“不严重”，也不得与 `p1134` 非严重不良事件合并。
2. `p1136` 继承 `p1133` 的“以下情况一般不作为快速报告内容”。“一般”是非绝对强度，不得改写成永不、禁止、无需或不允许报告。
3. `p1137` 的触发条件是“以严重不良事件为主要疗效终点”。不得把条件删除、扩大为任何 SAE，或缩成只有确认相关/非预期 SAE。
4. `p1137` 的结论是“不建议申请人以个例安全性报告形式向国家药品审评机构报告”，不是禁止报告，也不是“不向任何机构报告”。申请人、报告形式和接收机构均须保留。
5. `p1137` 不授权反向推理：当 SAE 不是主要疗效终点时，不能据此推导必须、应当或必然采用个例安全性报告快速报告；其他快速报告条件仍由第 95 包原文决定。
6. `p1133-p1137` 必须作为一个连续列表理解，但本包只拥有 `p1136-p1137`。只读回接不能反向改写或重复发布第 95 包来源。
7. 两个自有来源均为 `post_treatment_execution`，没有预筛、筛选或基线候选权；`required_candidate_source_refs` 必须显式为空，所有自有和附加来源均进入零候选门禁。

## 工作项

1. 创建 Package 96 配置与父级检查清单，严格保持 2 个自有来源、5 个只读附加来源和所有权映射。
2. 创建确定性变异测试与 dry-run prepare 证据，覆盖 AND/OR、非绝对强度、条件作用域、主体/形式/机构、省略与反向推理。
3. 独立只读攻击审阅，优先寻找“正确禁止字段遮蔽错误正向字段”、条件逆命题、绝对化和跨包吞并等可静默通过的最小反例。

## 允许写入

- 配置：`configs/representative_group_package96_expected_serious_primary_endpoint_reporting_boundary.v1.json`
- 父级检查清单：`slice61ch-package96-expected-serious-primary-endpoint-reporting-boundary-parent-checklist.md`
- 确定性测试：`test_slice61ch_package96_expected_serious_primary_endpoint_reporting_boundary.py`
- 模型外准备产物：`slice59n-prepare/d001-ii-package96-expected-serious-primary-endpoint-reporting-boundary/`

上述相对路径均以本合同所在的 `d001-ii-phase-closure` 目录为基准。除这些路径外不得写入其他业务、临床或运行产物；执行报告仍由 runner 管理。

## 验收条件

- 配置、测试、检查清单和准备产物均来自上述权威来源，`claims_complete=false`。
- 模型外准备精确为 `2 owned / 5 attached / 7 total`；无候选、无语义模型调用。
- 结构化变异测试必须在只修改权威正向字段时仍能捕获 AND→OR、一般→绝对、删除主要疗效终点条件、删除申请人/个例安全性报告/国家药品审评机构，以及错误逆命题。
- 专项、相邻包、Phase 闭包、JSON、作用域差异检查、review-gate 与执行审计通过。
- 父级复核后才能写入 accepted 检查点；worker 不得自行宣告验收。

## 停止条件

- 冻结计划来源、包身份或所有权不一致；
- `p1133-p1135` 未真实进入只读闭包，或第 97 包内容进入本包；
- 任一正向语义错误可被关键词、禁止反转或备注中的正确文本遮蔽；
- 出现候选、发布、模型调用或 `claims_complete=true`；
- 任何预期外结果未定位原因即准备继续。
