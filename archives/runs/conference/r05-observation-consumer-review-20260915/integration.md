全部证据收集完毕。以下是第 2 轮完整输出。

---

# Conference Output: r05-observation-consumer-review-20260915 - evidence_single_object

## Output

第 2 轮只读复核完成（未运行测试/导入/产品/模型/数据库/浏览器，未修改源码）。**结论先行：Codex 陈述的六项变更全部与实际源码相符（F1/F2 修复属实且正确落地）；但新放行的 `source_validity` 排序在语义上不充分——它在没有来源支撑选择器的情况下硬编码“取有效期内的最新记录”，与单记录路径的失败语义不一致（R2-F1，需 Codex 裁定）；另有消费算法版本未随输出形状变更而升级（R2-F2）和审计契约缺空值序列化保护（R2-F3）两项方法完整性风险。**

### 一、Codex 陈述与实际源码的核对（证据）

| 陈述 | 核对结果 | 证据 |
|---|---|---|
| F1 已修：context 要求移到非排序分支之后 | ✅ 属实 | `qualified_binding_selection.py:300-310`：`policy.selection is None`（any/all）分支先行返回，`review_context is None` 门槛仅剩排序路径 |
| F2 已修：文案区分“方案要求”与“是否已选取” | ✅ 属实 | `review_history.py:412-419`（谓词侧，按 `observation.fact_ids` 分叉“已按该要求选取记录…”/“目前尚未确定可采用的记录。”）、`:551-553`（控制侧，按 `audit.selected_fact_ids`） |
| AssessmentCandidate 拒绝排序审计 | ✅ 属实 | `review.py:258-259`：“结果选择依据只能由已核实的正式资料核对流程保存，不能由模型候选提供” |
| 审计含 selected_fact_ids 且选中/未选不重叠不重复 | ✅ 属实 | `observation_selection.py:18, 26-29` |
| 官方观察与资格结果的选中集须与审计一致 | ✅ 属实 | 三层强制：`qualified_binding_selection.py:130-131`（资格结果）、`review.py:216-217`(PredicateObservation)、`review_control_repository.py:102-103`（控制义务行） |
| control-review-outcome/v3 按原子身份存四层审计，旧 v1/v2 序列化剔除 | ✅ 属实 | `control_review_outcome.py:59, 67, 69-74`（序列化剔除）、`:76-82`（旧版回填拒绝）；投影侧 `control_review_outcome.py:30-32, 97-98` 过滤到本控制自己的原子 |
| 仓储校验 sources/policy/selected/nonselected | ✅ 属实 | `review_control_repository.py:76-85`（policy_sha256 复算、selected/not_selected ⊆ 冻结事实）、`:98-103`（未选不得同时作为依据、used==selected）、`:117-120`（locator ⊆ 所引事实） |
| 历史/API 暴露 control_selection_records 与排除 locator | ✅ 属实 | `review_history_service.py:586-603`（谓词+控制排除事实 locator 聚合并经 FactAuthorityValidator）；`review_history.py:540-560`（按原子身份+layer 归属构造，与义务行分离，无适用/例外误挂到义务） |
| 前端四层分开渲染、locator 精确等价含排除记录 | ✅ 属实 | `reviewHistoryHttp.ts:911-936`（严格键解码、排除 locator 计入 referencedIds 且双向精确等价、identity 唯一性）；`FrozenReviewReport.tsx:170-175`（独立“记录采用依据”区块）；`frozenReviewExport.ts:60-65` |
| interval_condition 保持未核实而非过滤阈值结果 | ✅ 属实 | `ordered_observation_selection.py:76-77` 仅放行 {event_membership, source_validity}；`control_calculation_experiment.py:151-154` 过期源→UNKNOWN 不代入阈值 |

补充核实（无分歧）：评估器与排序助手日期语义一致——`_phase3_date_value`（`eligibility_review_projection.py:176-190`，保留下界+精度）与排序助手重建（`ordered_observation_selection.py:80`）完全相同，不存在窗口判定双真相源；未完成结果携带审计时 DTO 文案如实（“目前尚未确定…”）；幂等重发布路径（`frozen_review_publication.py:107-111`）早退不重写旧行。

### 二、新发现（按严重度排序）

**R2-F1（高，语义裁定——source_validity 排序硬编码“latest-valid”，缺来源支撑选择器）**
- 证据：`ordered_observation_selection.py:75-88` 对 `time_purpose == "source_validity"` 与 `event_membership` 共用同一逻辑：窗口 FALSE 的事实先被剔除（记为 `observation_out_of_window`），再在剩余者中做日期支配排序。`ObservationOrdering`（`observation_selection.py:33-36`）只有 `criterion`（latest/earliest）与 `ordering_attribute`，**无法表达“先取最新、再验证有效期”（latest-overall）与“取有效期内的最新”（latest-valid）的区别**；deconstruction gate 对政策摘录的校验（`rules.py:216-220`、`control_evaluation_spec.py:94-101`）也不要求摘录言明采用哪种读法。
- 矛盾点（推理）：同一临床问题在两条路径下语义不同——单记录 source_validity（`_select_facts_for_identity` 要求恰 1 条事实）会把 FALSE 时效结果交给计算层失败：`control_calculation_experiment.py:146-154` 明确“过期来源不证明阈值不满足”→ UNKNOWN `source_outside_validity_window`（fail-loud）；而多记录 + 最新一条过期时，排序阶段先过滤再排序，**静默回退到较旧的有效记录**（仅以 not_selected 披露）。记录条数决定语义，这不是方案原文能支撑的区分。
- 建议之二（按彻底程度）：
  1. 最小保守修：source_validity 排序改为“全候选排序→选中者要求 membership TRUE；FALSE → 新理由（如 `source_outside_validity_window` 类）→ unresolved”，即与单记录路径一致的 fail-loud 语义；待方案解构能区分读法后再放开。
  2. 彻底修：`ObservationOrdering` 增加来源校验字段（如 `validity_scope: Literal["order_within_window","order_then_verify"]`），并由解构门核验摘录确实言明所选读法。
- 不确定：实际方案文本是否一律采用“有效期内最新”读法——这是临床裁定，归 Codex/用户；在裁定前，代码不应代替方案做此选择。

**R2-F2（中-高，方法完整性——consumer 版本未随输出形状变更升级）**
- 证据：`QUALIFIED_BINDING_CONSUMER_ALGORITHM` 仍为 `qualified-binding-selection-consumer/v10`（`qualified_binding_selection.py:24`），而审计新增 `selected_fact_ids`、outcome 校验新增 used==selected；对照 EVALUATOR 升至 v14（`frozen_review_calculation.py:27`）、PUBLICATION v5。方法采用按版本字符串绑定（`require_evaluated_binding_method`）；旧 v10 语义下批准的评测/授权若被重放，将无声覆盖新行为。
- 建议：升 consumer 至 v11（同步扩 `QualificationAdoptionAuthorization`/material 的 Literal），或由 Codex 记录肯定性证据：不存在将以 v10 绑定重放的已批准评测与授权（会议语境称“未发放新的采用许可”，倾向后者可行，但需明示记录）。

**R2-F3（中，旧载荷不可变性脆弱——OrderedObservationAudit 缺空值序列化保护）**
- 证据：`observation_selection.py:14-30` 无 wrap serializer，`selected_fact_ids` 即使为空也始终序列化输出。对照既有惯例：`ControlReviewOutcome.serialize_ordering`（v1/v2 剔除）、`ControlObligationOutcome.preserve_legacy_payload`（空 `unverified_evidence` 剔除）、`PredicateObservation.preserve_legacy_payload`。当前不可变性**成立**（核实：`_stored_assessments` 不重算 assessment gate output_hash；幂等重发布早退；控制快照有版本门控序列化），但任何未来对旧 PredicateObservation 行的重哈希（例如为与 actions 对称补 output_hash 复算）都会因旧审计字典重载后多出 `"selected_fact_ids": []` 而失配。
- 建议：给 `OrderedObservationAudit` 加 wrap serializer，空列表时剔除 `selected_fact_ids`（沿用项目既有模式），一行级修改。
- 附属 bounded question：是否存在早于近期默认字段新增的 v1/v2 `ReviewControlSnapshot` 存量行？`_verify`（`review_control_repository.py:141`）逐字重算 output_hash，若 `ControlObligationOutcome` 在 v2 行写入后新增过其他默认字段，旧历史读取会大声失败（fail-closed，符合“宁可大声失败”，但会阻断历史展示）。数据库在边界外，无法自查。

**R2-F4（低，防御对称性）**：`_stored_assessments` 的审计重校验（`review_history_service.py:390-392`）检查了 not_selected ⊆ 上下文事实，但未检查 `selected_fact_ids ⊆ context_fact_ids`（控制仓储在 `review_control_repository.py:83` 有）。写入期契约等式（fact_ids==selected）使其当前安全；建议在同一条件补一项，一行修改。

**R2-F5（信息，可选）**：`review_history.py:543-544` 的 `identities[identity_hash]` 与 `.observation_policy.selection.criterion` 解引用依赖仓储 `_verify` 先行拒绝未知身份/缺政策（读取路径确实先过 `get_or_none→_verify`，当前安全）；如需解耦 DTO 层与仓储校验顺序，可改为显式取值+明确报错。非必需。

### 三、给 Codex 的决策点与有界问题

1. **R2-F1 裁定**（最重要）：source_validity 排序在补上来源支撑选择器前，是否接受“全候选排序→选中者验窗→失败即 unresolved”的保守默认？还是维持 latest-valid 并接受“记录条数决定语义”的现状？我建议前者（或直接实现选择器）。
2. **R2-F2**：升级 consumer v11，还是书面记录“无 v10 存量绑定可重放”？
3. **R2-F3 附属**：请确认是否存在早于字段演进的 v1/v2 控制快照存量行（我无法在只读边界内核库）。
4. R2-F4 的一行对称补丁是否随下次修订顺手加入。

### 四、边界声明

只读审阅；“核对通过”均为静态证据链结论，不构成临床、监管、视觉或用户验收；未发现绕过正式发布路径的旁路（in-progress 评审 API 无排序暴露，属正确设计而非缺口）。条件复检（conditional retest）仍为已声明开放范围，本报告未将其记作已实现。无阻碍项，无需回退链。
