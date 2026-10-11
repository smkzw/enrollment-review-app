源审完成。核对了两个服务的控制接线全文、`project_expectation` 完整函数、v2 期望合同与枚举、投影服务、组合器与共享政策合同。以下为聚焦答复。

---

# Conference Output: r05-control-expectation-scope-20260914 - evidence_single_object（聚焦续审：覆盖≠适用性）

## Output

### 一、两服务回归检查：未发现具体回归（仅源审）
- **judgment_search_source.py**：流程来源拒绝原样保留（:296-304）；官方目标路径与序列化不变（:381-433，`judgment_search_target/v1`）。控制分支（:343-379）以 `control-v1` 独立身份重新核对发布↔权威↔节点一致（:350-355）、唯一控制选取（:356-359），目标保留完整已发布控制+模板+要求（:369-371），并明示检索结果不证明条件成立（:372-375）。模板↔要求语义比对已含 control_origin/status/完整约束与可空政策，精确等值、`None==None` 通过、无默认值顶替（:259-295）。控制来源正确跳过 `due_requirement_ids` 成员检查、节点闭包改由 `origin.workflow_stage_id == template.workflow_stage_id` 证明（:334-341、:353）。
- **review_protocol_source.py**：冻结重建以 `shared_control_requirements(publication)` 重投影并要求与已存模板 (template_id, projection_sha256) 全等（:92-108）——控制模板自此成为冻结上下文模板集的正式成员。注意两点伴生行为（非缺陷）：① 受 `project_expectation` 对控制模板抛错影响（evidence_expectations.py:219-222），投影服务不滤控模板（evidence_expectation_projection_service.py:70-98），控制绑定节点上的 episode **整次期望投影都会中止**——当前守卫实际是全局阻断，撤销时必须先改循环行为；② 冻结上下文“有模板无期望行”将成为常态，消费者不得由缺行推断缺失。

### 二、载体划分（最小方案，复用既有模型）
- **覆盖（文档/事实层）**：留在 `EvidenceExpectationV2`（按 template×episode 追加）。OBSERVED/OBSERVED_WEAK/REFERENCED_MISSING 本就是与适用性无关的文档真相，直接复用。
- **适用性（控制层）**：由**持久化的 `ControlLayerEvaluation`** 承载（control_layer_evaluation.py:16-26 已含 applicability TruthValue 与激活态），按键 (authority, protocol_control_id) 追加、内容寻址（control_sha256）。不改期望合同、不落模板（模板是方案级，受试者适用性永不回写模板）。期望投影把它当作与 gap_signals 同级的**输入**。
- 消费规则（替换 :219-222 的整体 raise）：
  - applicability **TRUE** → 走完整既有状态机，含 ABSENT；此时“双读完整仍无书面判断”升 PROFESSIONAL_JUDGMENT，是**可报告未决项**而非用户确认停点（与现有 fact_expectation_gaps.py:254-271 升级逻辑一致，语义终于合法）。
  - **UNKNOWN/无记录** → 仅允许覆盖为正的路径（observed/observed_weak/referenced_missing 照常，保住已确认证据与候选事实）；**绝不产生 ABSENT**，也不滥用 NOT_DUE/FUTURE_STAGE_NOT_DUE；“适用性未确认”由适用性投影本身可见。
  - **FALSE** → 本 episode 不建期望行（沿用姐妹访视 skip 先例，evidence_expectation_projection_service.py:77-80），可审计性由适用性行保证。
- **来源政策 unknown（None）**：不得转为假。`_coverage_verdict` 需显式分支：None 不得使判定**更严**（未断言的禁止不得把转述判 none，evidence_expectations.py:161-167 现状会）也不得**更宽**（未断言同期要求不得据此判 complete）；`result_validity_status="unknown"` 不做新鲜度过滤但发可撤回的“有效期未断言”提示，"specified" 用 `control_validity_constraint` 接真实日期区间消费者（复用 `source_validity`/`evaluate_time_constraint` 思路，不造点日期）。

### 三、既有状态/缺口类型是否足够
**足够，不需新增 ExpectationStatus/GapType**：五状态覆盖文档真相与到期语义；“适用性未知”不是期望状态而是控制层状态，由新载体表达。缺的是上述两条门控规则与 None 政策分支，不是新枚举。

### 四、须同步修改的消费者（撤销守卫的前置集）
控制覆盖守卫（evidence_expectations.py:219-222）撤销前须一起改：① 适用性投影的持久化与读取；② 投影服务按 `template.control_origin.protocol_control_id` 联查适用性并处理 TRUE/UNKNOWN/FALSE 三分支（并消除全局中止）；③ `project_expectation` 控制分支 + `_coverage_verdict` None 分支 + 有效期约束消费者；④ **fact_expectation_gaps.expectation_gap_signals 的适用性门控**——现 fallback 与 PROFESSIONAL_JUDGMENT 升级对控制模板无条件生效（fact_expectation_gaps.py:232-302），会对适用性未证明的控制断言“未见书面判断”，这是目前“覆盖≠适用”在信号层的真实泄漏点，最小修复是控制来源模板的判断缺口升级以 applicability=TRUE 为前提（fallback_only 提示可保留但措辞条件化）；⑤ 报告/审核上下文把“适用性未确认”与“资料缺失”分开渲染，并按原子 modality 呈现建议项（不折叠为排除）。完整审核守卫（frozen_review_calculation.py:37-38）在前述之外还须：控制原子**已验证绑定**（现仅候选通道，control_binding_candidates.py 候选不含接受真值）、组合器由已接受原子真值驱动、逐原子 modality 处置与控制结果/来源进入报告，并过最终集中验证后方可撤销。

### 未验证部分
本轮纯源审：未运行测试/投影；未验证控制目标判断检索作业的真实执行；适用性投影持久化为建议而非现有代码；None 政策在 `_coverage_verdict` 的最终分支形态未实现未验证；prompt 行为未测。不构成临床或最终验收结论。
