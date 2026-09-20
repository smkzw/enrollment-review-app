# Codex Execution Plan: phase5-slice61bm-package75-semantic-boundary

Objective: 为 D001 II 活动131包计划第75包建立临床语义边界：区分D1给药前PK/IL-17A采样记录、治疗期计划外采样、全程不良事件监测与ICF后合并治疗收集，防止资料收集或治疗期义务被误升格为入排不通过条件；只建立来源闭包、项目无关门禁建议和最小测试，不修改源方案、不并入正式矩阵、不运行受试者审核。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读核对 body.p828、p831-p837 与 p829-p830、p749-p755、Ⅱ期流程表、D1给药前访视、合并治疗和不良事件章节的来源关系，形成临床语义分类：入排控制、阶段资料收集、治疗期监测、条件性可选动作；不得修改文件。 | `runs/execution/phase5-slice61bm-package75-semantic-boundary/worker_01.md` |
| `worker_02` | 基于第75包冻结计划创建最小来源闭包配置、父级临床核对清单和确定性测试，重点阻断把ICF后合并治疗收集、全程AE监测、计划外PK采样或中心实验室操作说明改写为入排不通过条件；只编辑本切片新增工件及必要共享测试，不调用模型、不改正式矩阵。 | `runs/execution/phase5-slice61bm-package75-semantic-boundary/worker_02.md` |
| `worker_03` | 独立审查第75包及现有控制矩阵，寻找结构包异质内容被错误合并、D1给药前与治疗期混并、可选计划外采样被强化、记录字段漏项、资料收集义务被当成资格判定、规则依据被当成受试者证据等反例；给出可执行验收条件，不修改实现。 | `runs/execution/phase5-slice61bm-package75-semantic-boundary/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

- [x] 三个执行工作项均完成。主路由 `glm-5.3-flash:max` 的三次真实调用均在约 2 秒返回配额类 429；保留原始记录后，按声明回退链使用 `deepseek-v4-flash:max` 完成同一任务，未静默替换。
- [x] 独立来源核对与反例审查均确认第 75 包是异质结构包：标题、治疗期采样执行、条件性可选采样、非受试者级中心操作说明、治疗期 AE 监测及 ICF 后资料收集不得合并为同一种候选。
- [x] Codex 未直接接受 worker_02 的初版配置：纠正其把 p831/p832/p835 误列为候选、把 p833 误列为结构标题、把无关冻结流程节点硬注入本批已知目标的问题。
- [x] 新增通用 `candidate_required_markers_by_source_ref` 门禁和 `CONTROL_DELTA_COMPONENT_DROPPED` 修复提示，只在配置中声明来源字段，未把 D001 项目特异规则写入共享代码。
- [x] 模型外准备通过：owned=9、attached=17、unit_count=26、prompt_char_count=40787、`claims_complete=false`。
- [x] 聚焦回归 `109 passed, 5 warnings`；方案与 Agent 全量回归 `1198 passed, 58 warnings`；`git diff --check` 通过。
- [x] 本轮不运行临床语义模型、不并入正式目录、不触及受试者、OCR、审核或前端视觉。
