# Phase 5 当前状态与会商裁决

## 当前实现证据

- Phase 4 的活动证据权威是 `ReviewEpisodeRecord.active_evidence_snapshot_id + active_evidence_processing_revision_id`，处理修订必须为可激活的完整修订。
- Phase 2 占位 `clinical_facts / evidence_expectations / patient_profiles` 仍绑定旧 `evidence_snapshots`；不能直接作为 Phase 5 写路径。
- 现有 `ClinicalFact` 与 `EvidenceNormalizationCandidate` 未绑定完整处理修订；Profile 前端仍走 fixture/stub，没有真实 HTTP Profile API。
- Phase 4 已有有效文本、校对、真实定位、页图、OCR 风险、持久 Job、租约、检查点和幂等能力，Phase 5 应复用而非另建编排框架。

## 独立会商一致意见

2026-08-22 使用两个相互独立的只读参与者审查：`DeepSeek V4 Flash max` 与 `Grok Build 4.6 high`。两者均确认以下阻断项：

1. 新事实必须绑定活动 `evidence_snapshots_v2 + complete processing revision`，发布前再次核对活动指针。
2. Agent 候选与发布实体必须分离，不能把模型输出对象直接晋升为事实。
3. 事实只引用 Phase 4 已认证定位；模型提出的坐标不能直接成为红框。
4. 沉默不能形成否定/正常事实；否定必须有明确原句与被断言对象。
5. 部分日期必须保存上下界，事件时间与记录时间分开，“既往”不能推断结束。
6. 冲突并列、无自动赢家；精确重复合并全部定位。
7. 使用独立 FactNormalizationRun，不借用 Phase 6 ReviewRun。
8. 首屏突出集合由后端投影，不能把所有有规则关联的事实都当成风险。

## Codex 采纳、延后与拒绝

### 采纳

- 新建 Phase 5 v2 写表并冻结旧占位表读路径。
- 默认按逻辑文档切片，超长文档可连续页组切片；页清单必须闭合。
- 先实现合同、真实性/极性/日期/冲突门禁和确定性夹具，再接真实模型。
- 事实到规则仅做确定性 `fact_type / requirement` 身份匹配，不做自由文本模糊链接。
- 关键 OCR 风险仅阻断受影响候选；失败运行保留上一可用 Profile。

### 延后

- 逐条入排判断、方案阈值与洗脱结论到 Phase 6。
- ActionRequest、自动关闭、批量与报告到 Phase 6/7。
- 大规模盲后医学准确性验证到 Phase 8；Phase 5 仍对两个隔离新架构代表病例逐事件核对。

### 拒绝

- 向量数据库、知识图谱数据库、通用多 Agent 编排框架。
- 模型置信度作为事实发布或首屏隐藏阈值。
- 模型自动解决冲突、“最新资料自动胜出”、空 Profile 冒充成功。
- 重定向旧表外键或混用旧占位事实的原地迁移。

## 已知工具问题

守卫初次生成的会商提示包含 worktree 绝对路径，触发了其自身“生产路径”预检；改为 runner 当前目录后预检通过。初次 Pi 命令还携带了与实时清单冲突的重复日夜调度参数，未发起模型调用；按实时角色清单使用当时的日间主路由后完成。规划和验收应以 runner 的实际 provider/model/session 元数据为准，不能依据角色文件名判断模型。
