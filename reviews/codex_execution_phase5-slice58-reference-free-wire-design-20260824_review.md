# Codex Execution Review: phase5-slice58-reference-free-wire-design-20260824

## Verdict

accept_design_only

## Worker Outputs

- `worker_01` 从强 Kleene 三值逻辑、原子否定、重复项和确定性水合角度证明无引用 DNF 可表达当前领域逻辑，并指明不得用 comparator 取反替代 `NOT(AtomicExpression)`。
- `worker_02` 比较固定深度树、布尔 DSL、位置引用及 DNF/CNF，结论是首版应只提供固定语义的 DNF，不应让模型选择表达形式。
- `worker_03` 将 v6-v9 的真实失败映射到迁移边界、系统所有身份、新旧合同隔离及 D001/MG-K10-SAR 真实验收门槛。
- 三份报告均独立得出 `dnf-v1` 无引用“或分支中的且条件组”结构，不保留 `node_id`/`children`/`root_node_id`。

## Manager Assessment

本路由 Codex 直接复核，未设置执行经理。三份报告的共识与连续真实探针一致：v6 、v8 和 v9 均出现悬空引用，v9 的同会话修订仍失败；v8 还出现原文合取逻辑被改成 `ANY/NOT` 及伪造单位/时间窗。因此继续增加图引用提示词不具备工程合理性。

接受的迁移边界：

- 仅替换 oMLX compact wire Schema、提示合同和确定性水合；不改正式 `RuleExpression` 、三值评估器、历史已水合领域草案或项目特异临床规则。
- 触发表达式与例外表达式均使用同一 DNF 形状，但分开水合、分开生成正式身份。
- provider 不生成正式 predicate id；正式身份由系统基于规则/组件/作用域/规范化语义及来源确定性生成。
- 同组重复原子、重复分支、空分支、旧图字段、复杂度超限均显式拒绝，不截断、不静默去重、不退回旧 wire。
- 初始复杂度限制只作待真实项目校准的操作保护，不视为已完成的临床适用性结论。

## Boundary

- 本次只接受 wire 迁移设计，不声称 `dnf-v1` 已实现、已通过真实项目或已通过用户界面验收。
- 不改原始研究方案、旧项目、已发布 RuleSet、事实/Profile 或三值评估器；不引入 D001/MG 项目特异死规则。

## Hermes Workflow

- 通过 `hermes_workflow_guard.py` 初始化并审计执行任务；实际参与者均为指定的 `codex/gpt-5.6-luna:max`。
- 原生子会话准入不可用后，使用同模型、同推理强度的标记 CLI 兼容路径；未使用其他模型或未申报 fallback。

## Codex Independent Verification

- 已重新打开 v6-v9 摘要和报告所指的原始回包，确认失败顺序为：悬空 `p2` 、数值单位缺失、悬空 `p3` 且语义漂移、同会话修订后仍悬空 `p4`。
- 已核对当前领域评估器为强 Kleene `TRUE/FALSE/UNKNOWN` 逻辑；原子否定必须包裹完整原子表达式，不允许经典二值简化。
- worker_02/03 运行时聚焦回归共 `34 passed, 5 warnings`，这仅是旧 wire 的基线，不是 `dnf-v1` 实现证据。
- 未执行新 DNF 真实 oMLX 调用、D001/MG-K10-SAR 全批次或浏览器验收；这些是实现后必须通过的独立验收门。

## Cleanup Decision

接受设计后由 runner 归档会话输入、运行日志和 worker 报告；v5-v9 真实失败工件作为根因回归证据保留。
