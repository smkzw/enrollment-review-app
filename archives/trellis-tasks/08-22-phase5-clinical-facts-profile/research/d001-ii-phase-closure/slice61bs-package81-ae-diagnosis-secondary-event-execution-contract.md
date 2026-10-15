# 第 81 包执行合同：AE 诊断与继发事件边界

## 目标

对冻结计划第 81 包 `pap-d284831618aa0dcf855c35d7` 的 `body.p1027-p1032` 建立最小模型外来源闭包、父级临床检查清单和确定性回归。所有结论必须来自当前 D001 II 冻结计划、覆盖清单、结构块和原始 DOCX；不运行临床语义模型，不发布控制点。

## 权威来源

- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/coverage_manifest.json`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/structure/blobs/protocol_blocks/`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/source-input/blobs/protocol_sources/`
- 第 75-80 包现有配置、测试、父级清单和准备证据仅作模式参照，不能替代当前原文核对。

## 工作项

1. **来源与所有权独立核对（只读）**：逐字核对 `p1027-p1032`、第 80 包前置边界、第 82 包表 7及第 83-84 包后续记录规则，确认标题、正文、表题和上下游职责，不修改文件。
2. **最小实现**：复用现有代表组模式，新增第 81 包配置、父级清单、模型外准备证据和专项测试；不得新增共享抽象，除非发现项目无关且已有路径无法表达的真实合同缺口。
3. **独立反例挑战（只读）**：重点攻击诊断优先是否被误写为“必须立即确诊”、无法诊断时症状/体征/实验室值的并列关系、后续诊断替换是否丢失首次症状日期、主要原因判断是否被弱化，以及是否提前吞并表 7 或第 83-84 包细则。

## 接受边界

- `body.p1027-p1032` 六个拥有来源逐项有处置；上下游真实只读来源进入闭包。
- 诊断优先、暂无法诊断的记录路径、后续诊断更新与首次症状日期均保持原文逻辑。
- `p1031` 只保留“根据主要原因判断是否独立记录”及表 7 引用；不凭引导语补写表 7 的四类具体规则。
- 不把治疗期 AE 记录规则升格为预筛、筛选或基线入排门槛。
- 专项、相邻、Phase、方案与 Agent、治理测试及执行审计通过后，Codex 才能接受。
