# Phase 5.8d 访视覆盖范围与精确节点门禁已接受

日期：2026-08-28  
分支：`codex/phase5-clinical-facts-profile`  
工作树：`.worktrees/phase5-clinical-facts-profile`

## 本轮目标

修复 V10 父级拒绝所暴露的两个通用合同缺口：流程目标的来源范围不得超出访视身份，后续时间锚点不得绑定同阶段但错误的访视节点。

## 已完成

- 发布门禁从 owned 原文提取明确访视身份，并与 `required_procedure` 链接目录项的 `visit_instance` 并集比较。
- 明确属于对侧期别的带期别访视短语先排除，不会把 II 期审核中的 III 期 W16/W52 作为缺口。
- 原文仍含选定期 W12、提前退出等未链接访视时，流程必做处置不能再声称整个单元已被筛选/基线/D1 目标完整覆盖。
- 时间锚点若存在专门冻结节点，最终判定必须使用该节点；首次给药前复核不能退化为普通基线访视。没有专门节点的旧合同保持兼容。
- Agent 首轮和定向修订提示同步说明访视覆盖边界与精确节点选择，不包含 D001 特异规则。
- 保存的 V10 水合终稿在新门禁下确定性重放，被 `PROCEDURE_VISIT_SCOPE_UNCOVERED` 拒绝，缺口为“提前退出访视、第12周访视”。

## 验证

- 聚焦合同、发布、传输、规划和复合缺陷回归：`169 passed in 1.52s`。
- 完整方案层回归：`874 passed, 58 warnings in 125.93s`。
- V10 原终稿确定性重放：`accepted=false`，首个问题为 `PROCEDURE_VISIT_SCOPE_UNCOVERED`。
- V10 父级评估保持不变：`artifacts/phase5-slice60d-d001-pregnancy-fsh-parent-assessment-20260828/assessment-summary.json`。

## 边界

- 只接受通用门禁修复，不接受 V10 妊娠/FSH 临床解构，也未生成 V11。
- D001 II 仍为 `1848/1245/131`，剩余 `128` 包，`claims_complete=false`。
- 未运行受试者、OCR、病例审核、浏览器、视觉或独立测试者。

## 下一安全动作

选择一个不涉及妊娠/FSH、且能暴露不同结构风险的极小真实控制组，先核对冻结来源和既有目录边界，再决定是否进行一次真实语义验证。妊娠/FSH 如需重放，必须新建 V11 且先让确定性门禁接受人工构造的正确处置；不得直接复用 V10。
