# Phase 5 规划会商上下文

## 目标

审查并挑战 Phase 5“临床事实与 Patient Profile”规划，使其能把 Phase 4 已激活证据快照/完整处理修订转化为可回源、可重放、可增量重算的事实基座和中文 Patient Profile，同时严格停在 Phase 6 入排判断之前。

## 权威来源

1. `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` §4.3、§7.2、§8.4。
2. `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` Phase 5。
3. `.trellis/tasks/08-22-phase5-clinical-facts-profile/prd.md`。
4. Phase 4 归档检查点及当前代码合同、迁移、测试。

## 已观察的技术事实

- Phase 0.5 已有 `ClinicalFact`、候选 Event/MedicationExposure、ConflictGroup、EvidenceExpectation、PatientProfile 合同和合成前端。
- Phase 2 占位 `clinical_facts`/`evidence_expectations`/`patient_profiles` 绑定旧 `evidence_snapshots`；Phase 4 当前活动版本绑定 `evidence_snapshots_v2 + complete processing revision`。这是必须先解决的身份错链。
- Phase 4 已能回放有效 OCR 文本、校对、页图、真实定位和风险核对，但尚未运行 Evidence Normalizer。
- 当前前端 Profile 只读取 fixture/stub；没有真实 HTTP Profile API。

## 独立审查工作项

1. **领域与溯源审查：** 事实/事件/暴露/冲突/Expectation 的身份、来源强度、日期范围、旧表迁移、活动处理修订绑定和增量重算是否自洽。
2. **Agent 与运行图审查：** Evidence Normalizer 输入切片、结构化输出、Gate、Job/Checkpoint、幂等、失败恢复和空/漏页/虚构 Span 防线是否充分且不过度设计。
3. **临床与用户体验审查：** 13 泳道、首屏风险过滤、事件回源、筛选病历转述溯源提醒、冲突并列和中文交互能否支持懒惰但专业的资深医学监查员。
4. **主席综合：** 给出必须修订、可延后、拒绝采纳项和可执行 Slice/验收顺序；不得把 Phase 6 判断或 Phase 7 行动闭环提前塞入 Phase 5。

## 硬边界

- 只读会商，不修改文件。
- 不读取工作区外真实临床资料。
- 不以模型信心代替证据或 Gate。
- 不引入项目特异规则、向量数据库、图数据库或通用 Agent 编排框架，除非能证明现有 SQLite/Job 图无法满足硬需求。
- 会商角色不承担后续真实浏览器测试，二者证据链分离。

## 输出

每名参与者返回：关键发现（按严重性）、建议合同/数据流、必需测试、应拒绝的复杂度、残余风险。主席返回可直接修订 `prd.md/design.md/implement.md` 的统一裁决。
