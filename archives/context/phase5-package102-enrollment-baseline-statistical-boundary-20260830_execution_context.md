# Execution Context: phase5-package102-enrollment-baseline-statistical-boundary-20260830

Created: 2026-08-30 CST
Objective: 完成D001 II第102包参与者入组、基线特征与合并治疗统计内容的模型外来源闭包，阻断统计域向单例入排控制点的反向推理。
Task type: `long_horizon_code`
Risk: `medium`
Execution module trigger: Codex identified 4 independent work items, which is greater than two.
Route schedule: `unscheduled`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `openai-codex/gpt-5.6-luna:max -> codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex owns source authority, project boundaries, final verification, clinical acceptance and user delivery. Four first-line workers execute only their assigned bounded work; no separate execution manager is dispatched.

## Assigned Roles

- First-line executor: `long_horizon_code_executor` -> `pi` / `openai-codex` / `gpt-5.6-luna`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Package 102 参与者入组、基线特征与合并治疗统计边界

## 任务边界

- 活动 Trellis 任务：`.trellis/tasks/08-22-phase5-clinical-facts-profile`
- 不可变计划：`artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/frozen_phase_plan.json`
- 计划ID：`papl-e17d498106b6f71f440ff2be`
- Package 102 ID：`pap-ad0c757625a628fce5c7ed7c`
- 研究期别：Ⅱ期
- 本轮仅做模型外来源闭包、临床语义边界和确定性合同设计；不得调用临床语义模型、发布控制点或运行受试者/OCR/Patient Profile/浏览器流程。
- 原始方案、结构块、不可变计划、既有临床报告均只读。

## 拥有来源

1. `body.p1197`：参与者入组分析
2. `body.p1200`：人口统计学和基线特征分析
3. `body.p1201`：将基于ITT集，采用描述性统计方法来总结按组别及总体的参与者人口统计学特征和基线特性。
4. `body.p1202`：药物治疗与非药物治疗分析
5. `body.p1203`：根据WHO Drug分类统计合并用药的参与者例数和百分比；
6. `body.p1204`：根据MedDRA编码的系统器官分类（SOC）和首选术语（PT）分类统计合并治疗的参与者例数与百分比。
7. `body.p1205`：疗效分析

## 建议只读语境

- `body.p1198`：Ⅱ期临床阶段，列出总体入选及完成参与者例数，对各分析集的纳入和剔除情况进行总结。提供提前结束试验的参与者清单，对各分析集的参与者分布进行详细列表。
- `body.p1199`：Ⅲ期临床阶段，列出总体入选、完成16周基础期治疗、扩展期治疗以及完成试验的参与者例数，对各分析集的纳入和剔除情况进行总结。提供提前结束试验的参与者清单，对各分析集的参与者分布进行详细列表。
- `body.p1206`：Ⅱ期临床研究阶段
- `body.p1207`：主要疗效指标分析
- `body.p1208`：主要疗效指标为第12周PASI-75应答率，采用CMH检验比较各剂量组与安慰剂组并以多重填补处理缺失。
- `body.p1209`：主要疗效指标缺失采用LOCF、NRI等进行敏感性分析。

## 必须验证的临床语义

- “参与者入组分析”是对总体入选、完成、提前结束和分析集分布的事后统计总结，不是新的入组标准、筛选动作或入组决策入口。
- “人口统计学和基线特征分析”中的“基线”是ITT人群的统计描述域，不是基线访视项目、基线资料要求或缺口判定依据。
- WHO Drug与MedDRA SOC/PT用于合并用药/治疗的编码及人数、百分比汇总，不是合并用药禁限规则，也不能把编码缺失转成受试者不可入组或证据不足。
- “疗效分析”及Ⅱ期疗效统计语境属于随机后分析方法，不产生筛选、基线、随机或D1给药前义务。
- `p1198`和`p1199`必须保持Ⅱ/Ⅲ期分离；Ⅲ期基础期、扩展期和完成试验信息不得进入Ⅱ期控制。
- 分析集“纳入/剔除”、参与者“总体入选/完成/提前结束”和单例入排审核必须保持三个不同语义层级。

## 预期模型外合同

- 7 owned + 6 attached = 13 total，来源顺序为 `body.p1197-p1209`。
- `p1197/p1200/p1202/p1205/p1206/p1207` 仅作结构或统计分支引导。
- 拥有语义来源 `p1201/p1203/p1204` 预期 disposition 为 `administrative_statistical_background`。
- required candidates、workflow bindings、official rules和required procedures均为空；所有13个来源均禁止成为候选来源。
- `claims_complete=false`；不允许声明临床、D001全量或下游受试者验收完成。

## 相邻包边界

- Package 101拥有 `body.p1179`、`body.p1186-p1196`；不得回吸其样本量、分析集定义、软件和一般统计方法。
- `body.p1210-p1213` 是Ⅱ期后续疗效统计语境，`body.p1214-p1223` 是Ⅲ期疗效统计语境；在当前冻结计划中均不属于任何包的拥有来源，本包不得吸收。
- Package 103实际从 `body.p1224` 的安全性分析开始拥有来源；不得提前吸收其安全性、PK及暴露-效应统计正文。
- 宽泛上下文不得把统计章节的“入组”“基线”“用药”“治疗”词面提升为入排控制点。

## 验收锚点

- 逐字来源和所有权来自不可变计划与 coverage manifest，不以模型摘要代替。
- 需要一个最小配置、父级清单和专项测试，覆盖来源顺序、所有权、零候选、零工作流、Ⅱ/Ⅲ期隔离、统计域反向推理及相邻包排除。
- 执行者输出只能是建议或有界实现；Codex父级负责实际文件检查、测试、审计和临床接受。
