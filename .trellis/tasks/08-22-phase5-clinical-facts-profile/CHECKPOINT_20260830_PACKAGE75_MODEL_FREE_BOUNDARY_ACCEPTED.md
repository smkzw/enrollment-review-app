# Phase 5.8d 第 75 包模型外语义边界验收

## 结论

第 75 包已完成来源闭包、临床语义分区、通用确定性门禁、模型外准备和治理审计。该结论只接受“可进入后续有界语义重放”的工程基础，不接受任何模型生成控制点，也不并入正式 131 包目录。

正式 D001 II 状态保持 `1848` 个结构单元、`1245` 个语义目标、`131` 个包、剩余 `128` 包，`claims_complete=false`。

## 已接受的语义分区

- `body.p828`、`p834`、`p836`、`p838`：结构标题，不形成候选。
- `body.p831`：治疗期 PK/IL-17A 采样及时间、给药时间、给药量记录说明，处置为 `post_treatment_execution`。
- `body.p832`：治疗期特殊情况及条件性可选计划外 PK 采样，处置为 `post_treatment_execution`，不得丢失“可以选择”的语气。
- `body.p833`：申办者对研究中心的中心实验室操作说明，处置为 `non_enrollment_execution`。
- `body.p835`：治疗期不良事件监测，处置为 `post_treatment_execution`。
- `body.p837`：本组唯一 `other_control_candidate`，覆盖筛选、基线、D1 给药前资料收集，必须保留开始、结束、剂量、频率、给药途径、治疗方法、适应症。

## 机制修复

1. 新增通用配置项 `candidate_required_markers_by_source_ref`，允许父级按来源声明必须由模型语义陈述保留的组成要素。
2. 新增确定性拒绝码 `CONTROL_DELTA_COMPONENT_DROPPED` 和对应有界修复提示。
3. 必填要素只检查模型形成的语义陈述，不允许完整原文摘录替模型漏写兜底。
4. 第 75 包只向本批注入与 p837 直接重叠的官方合并治疗矩阵行；IL-17A 和筛选合并治疗流程目录节点仍作为只读来源闭包和模型外防重证据，不硬塞进访视实例不一致的本批已知目标。

## 深挖结果

- 首次模型外准备因冻结 IL-17A 流程目标的访视实例为“治疗期 / W0 / D1”，而本批工作流实例为“D1给药前”而失败。这不是数据缺失，而是已知目标注入边界错误；未放宽验证器。
- p529 的概述性文本含 D1 PK 表述，而 p829、流程表和 D1 访视清单均显示 D1 只有 IL-17A、PK 自 W2 起。该方案内部不一致继续保留为“来源冲突，需要核对”，不得静默裁决，也不影响本组非入排分区。
- p839-p979 访视安排正文仍处于当前冻结计划未拥有范围，是 `claims_full_coverage=false` 的已知规划缺口；本轮仅以 attached 来源形成只读闭包，未冒充全方案覆盖。

## 验证证据

- 模型外准备：owned `9`、attached `17`、total `26`、prompt `40787` 字符，`claims_complete=false`。
- 聚焦回归：`109 passed, 5 warnings`。
- 方案与 Agent 全量回归：`1198 passed, 58 warnings`。
- `git diff --check`：通过。
- 执行治理审计：`ok=true`，`warnings=[]`，`errors=[]`。
- 主路由三次真实调用均以配额类 429 终止；按声明回退链使用 `deepseek-v4-flash:max` 完成三项执行。所有主路由失败和回退报告均保留。

## 关键工件

- 配置：`research/d001-ii-phase-closure/configs/representative_group_package75_semantic_boundary.v1.json`
- 父级清单：`research/d001-ii-phase-closure/slice61bm-package75-semantic-boundary-parent-checklist.md`
- 模型外测试：`research/d001-ii-phase-closure/test_slice61bm_package75_semantic_boundary.py`
- 模型外准备证据：`research/d001-ii-phase-closure/slice59n-prepare/d001-ii-package75-semantic-boundary/`
- 执行治理包：工作树根目录的 `context/`、`plans/`、`runs/`、`logs/`、`reviews/`、`metrics/` 中对应 `phase5-slice61bm-package75-semantic-boundary` 的文件。

## 下一安全动作

先把本检查点作为第 75 包唯一恢复入口。下一步可选择：

1. 对第 75 包执行一次新的、有界、不可变临床语义重放，并由 Codex 独立临床验收；或
2. 若当前优先级仍是模型外全方案覆盖，则按冻结计划进入第 76 包（安全性定义）并先做来源闭包。

两者均不得改变正式 131 包状态；不得直接扩到受试者、OCR、Patient Profile、浏览器或视觉阶段。
