# Conference Output: r05-proposition-consumer-20260915 - evidence_single_object

## Output

同会话窄域设计咨询（只读；已核 `control_evaluation_spec.py`、`proposition_evidence` 合同/读取器、`control_calculation_experiment.py`、工程设 计§17/§17.1.1 及 2026-09-14 观察选择扩展条目）。≤50 行，证据/建议分列。

### 证据（现状）
1. `ControlObservationPolicy` 已在发布侧声明 `mode + scope(原文范围描述) + source_span_ids/excerpts（逐字）`（`control_evaluation_spec.py:14-30`），且设计明言“来源包含校验不是范围完整性或语义证明”（R3 设计 ：330）。当前 proposition 提示只注入 **spec 级** `source_excerpts/span_ids`（`app/llm/proposition_evidence.py:46-47`），**未注入 policy 的 scope/excerpts** → 两读者目前无从判断“整条声明观察”，缺口属实。
2. 逐对 `entails` 已断言**完整命题**：提示要求核对对象、属性、否认范围、限定条件并给出配对摘录内逐字引用（`proposition_evidence.py:55-59`、合同 `:26-38`、`validate_...:81-89`）。它是**该摘录见证下的整命题成立**，不是范围主张——`scope_correspondence` 与 `relation` 正交，不冗余。
3. 显式否认 vs 缺失已分立（“原文未提及不等于否认”入提示；空关系集→UNKNOWN `semantic_evidence_unverified`，`control_calculation_experiment.py:69-72`）；single 侧结构性计数纪律已有先例（`_conditional_truth:47-48`、选择侧 `:256-257`）。

### 挑战结论
仅 `supported/partial/unresolved` 三值是**模型主张**，无结构锚即与既有“包含校验≠范围证明”纪律不符；但为此新建任务/全文重读不必要。区分“整条单次声明观察”与“部分观察”的最小充分集 = 三值字段 + 逐字范围引用 + 纯代码的计数/一致门。

### 最小可实施建议
1. `PropositionEvidenceCheck` 增 `scope_correspondence: Literal["supported","partial","unresolved"]` 与 `scope_quote: str`（仅 `supported` 时必填、须为**该配对 locator 摘录**的逐字子串，代码校验同 `quoted_evidence` 之道；spec 无 `observation_policy` 时强制 `unresolved`、禁 `scope_quote`）。partial=摘录仅含声明观察的一部分（他处尚有其余），unresolved=不能判定；**不从空匹配推任何结论**。
2. 提示注入该条件的 `observation_policy`（mode/scope/policy excerpts/span_ids），并明文：范围判断独立于 entails/contradicts，永不改变 relation，partial≠contradicts；避免与 relation 形成矛盾标签——scope 不是真值，仅作 single 准入门。
3. 消费端（代码，非模型）：`agreement_key()` 纳入 scope 字段（分歧→既有 disagreement 排除）；single 模式仅在**恰好一条**来源合格事实、双路 scope 均 supported、无时间约束、无争议组、policy.mode==single 时准入 TRUE/FALSE（复用现有门）；事实数≥1 但≠1 → UNKNOWN `observation_identity_multiple_facts`；唯一事实 scope partial/unresolved → UNKNOWN 对应原因；any/all 维持见证语义，reverse 方向 UNKNOWN 不变。`identity_coverage.observation_scope_verified` 仅在准入时置 True，其余保持 False。
4. 版本后果：schema+提示变更须 `proposition-evidence/v1→v2`（含 comparison/summary 重算；旧 v1 任务在版本门处 fail-closed，与 binding-qualification v3→v4 同纪律）。

不新建队列、不做全文重读、两模型一致仍非临床采信（旗标与审批门不动，主审保留临床评估）。无须用户裁决的临床政策点：partial/unresolved 的后续跟进人沿用现有 unresolved 呈报路径。
