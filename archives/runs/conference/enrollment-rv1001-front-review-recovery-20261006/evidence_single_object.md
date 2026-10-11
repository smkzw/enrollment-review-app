Trellis SessionStart 上下文已加载。开始按 `evidence_single_object` 角色做只读审查——先定位并读取初始读集。

Bash 不可用（非交互拒绝），改用只读工具继续。读取主会场计划文件。

现在读取 `protocol_control_source_interpretation.py` 的核心定义段。

Trellis SessionStart ✓

以下为本次 `evidence_single_object` 只读证据审阅的完整报告（未写入 runner 管理的报告路径，按角色约定内联返回；会议计划文件仍是 TODO 骨架，会议 context 是本次唯一可用的来源包）。

---

# Conference Output: enrollment-rv1001-front-review-recovery-20261006 - evidence_single_object

## Output

### 0. 审查边界与工具状态

- 【事实】工具：Bash 在非交互模式下被权限拒绝（`Permission to use Bash has been denied`），因此全部核查改用 Read/Grep/Glob 静态阅读完成；未运行测试（符合 read set「Do not run tests」）；未写任何文件；未读 /tmp、artifact、临床、env、DB、log 路径。
- 【事实】阅读量：2 个方向文件 + 约 17 个源码目标段落 + 4 个测试段落（略超 18 段的建议上限，但每段都是承重证据：失败链、消费者、原答证明、既有单项复核范式各至少两处交叉）。行号取自当前工作树；会议声明的 frozen HEAD174c3efd 因 git 不可用未独立复核，请 Codex 在最终验收时确认行号等价。
- 【事实】`plans/codex_main_venue_enrollment-rv1001-front-review-recovery-20261006.md` 全文为 TODO（任务分解、来源包、验证清单均未填），本次审阅以 `context/enrollment-rv1001-front-review-recovery-20261006_conference_context.md` 的 Source Of Truth 为准；这是一个流程证据缺口（见 H4）。

### 1. 总体判断

【事实】context 描述的损失真实存在且位置精确：FLOW 前置 25 条来源核对在 `TARGET_VISIT_SCOPE_UNPROVEN`（index 2）被拒后，**已解析的审核对象、逐项有效的兄弟条目、结构化拒绝字段**全部未进入失败结果与失败检查点；只有原始模型原答以 attempt 文本形式留在检查点里。重跑时消费者判定 `absent`，只能对 25 条整体重新问模型。

【建议（最高层）】最小局部恢复可以做，且不需要新框架：把基线路径早已存在的三件既有机制接到 FLOW 前置路径上——(a) `validated_source_review_seed` 的逐项保留、(b) 基线 7780–7966 的「结构化拒绝反馈 + 单条复核」范式、(c) 检查点里已有的原答回执。但必须先修一处**硬前提**：一旦引入任何"宿主组合"的前置审核并保存，现有恢复证明消费者会**抛异常**而不是降级（H2）。H2 是本轮我找到的最高影响实施风险。

### 2. 事实核验

#### 2.1 真实失败链（逐跳）

| 跳 | 位置 | 事实 |
|---|---|---|
| 1 | `protocol_control_fixed_flow.py:250-273` | `prepare_front_stage_flow` 调 `transport.start_source_target_review`，`result.responses.append((phase, response))`（:269）**先于** `validate_source_target_review(...)`（:273）；即原答一定先被保留 |
| 2 | `protocol_control_source_interpretation.py:1593-1628` | `TARGET_VISIT_SCOPE_UNPROVEN` 由 `reject(...)` 抛出，携带 `statement_index=2`、`json_path=/items/2/target_id`、`source_refs`；`retry_class` 在 :1290 依 statement_index 自动成为 `single_statement` |
| 3 | `protocol_control_fixed_flow.py:376-383` | 被 except 捕获；`result.error=exc`、`result.error_code=_failure_code(exc)`（= `TARGET_VISIT_SCOPE_UNPROVEN`）；`result.review_validated` 保持 False；`result.error_detail` 在此分支为 None（只有 mixed/retained 分支在 :306-323 才填） |
| 4 | `protocol_control_deconstructor.py:7031-7032` | `front_target_review` 仅在 `prepared.review_validated` 时赋值 → 保持 None；已解析的 `prepared.review`（25 条）被丢弃 |
| 5 | `protocol_control_deconstructor.py:7045-7069` | 失败返回：`source_front_target_review=None`、`partial_wire=None`、`source_statement_coverage=[]`；attempt 的 `error_detail` 来自 `prepared.error_detail`（None），结构化字段丢失 |
| 6 | `protocol_control_deconstructor.py:7034-7044` | 原答 attempt 已记录：`session_id`、`raw_output_sha256`、`raw_output_text`、`error_detail={"workflow_phase": "source_review"}` |
| 7 | `protocol_control_execution.py:3229-3272` | 步骤层 `source_review_failure` 通过 `result.attempts[-1].error_classes`（或 `workflow_path_executed=="front_stage_flow"`）取到 `TARGET_VISIT_SCOPE_UNPROVEN` → `PROTOCOL_CONTROL_TARGET_VISIT_SCOPE_UNPROVEN`，`retryable=False` |
| 8 | `protocol_control_execution.py:3290-3348` | 失败检查点 v3 已含 `source_front_target_review` 键（:3324-3327，本场景为 None）、`workflow_path_executed`（:3328）、attempts 全量含 `raw_output_text`（:3334-3347） |
| 9 | `protocol_control_execution.py:2275` + `:2049-2052` | 重跑时 `_resumable_saved_source_review` 因 `source_front_target_review is None` 返回 `absent/no_saved_source_review` |
| 10 | `protocol_control_deconstructor.py:7027-7029` + `:266-273` | `resumed_review_items={}` → `review_seed=None` → 对 25 条整体重新发起 review 调用 |

【事实】未被丢失的：(1) 原答文本+哈希+会话；(2) 失败码与中文消息；(3) `workflow_path_executed`。被丢失的：(a) 已解析审核对象本身；(b) `validated_source_review_seed` 本可免费得到的有效兄弟集合；(c) 结构化拒绝（statement_index/json_path/source_refs/retry_class/affected_dependents）；(d) 重跑时任何种子复用可能。

【事实·对照】测试把当前行为钉死：`tests/v2/protocols/test_protocol_control_fixed_flow.py:1605-1624`（同构的 label-only 拒绝）断言 `source_front_target_review is None`、`attempts[-1].error_classes==[code]`、`transport.calls==["review"]`（即"尚无作者请求"成立）；`:899-915` 断言预算阻断时路径保持 `front_stage_flow` 且无前置证明；`:928-939` 断言无恢复证明的局部装配在**任何调用前**以 `FLOW_RESUME_PROOF_REQUIRED` 拒绝。**因此"丢弃无效前置审核"有一半是设计意图**：`source_front_target_review` 语义就是"已核过的前置证明"（:1621 注释 "Invalid evidence is not a validated front proof"）。任何修复都不得把无效条目塞进该字段——这是对 objective 字面读法的第一个纠正（见 §4）。

#### 2.2 三个点名对象的核验

**A. `validated_source_review_seed`（`protocol_control_source_interpretation.py:1661-1695`）**
- 【事实】逐条独立校验：对每条 item 用**单条 coverage**（`[coverage_by_index[item.statement_index]]`）调 `validate_source_target_review`，异常则 `continue`；返回保留集合或 None；重复/域外索引直接 `REVIEW_SCOPE_INVALID`；文档串明示 "Retain individually current decisions for recovery, never final adoption"。
- 【事实】同一校验器对单条与全量的判定等价性：`target_review_indexes` 是逐 entry 谓词（:1054-1088），`validate_source_target_review` 的全部判定都以 `coverage_by_index[item.statement_index]`、batch 冻结目标、`owned` 单元为输入；单条运行与全量运行对同一 item 不产生语义差异（除 json_path 位置）。
- 【推断】因此"24 条有效兄弟 + 1 条被拒"的划分在当前代码上是确定性可得的，不需要新校验。

**B. 来源核对消费者**
- 【事实】`_validate_saved_source_review`（`protocol_control_execution.py:2578-2740`）：对 **final_output 非空** 的结果做全量门禁——FLOW 请求必须带前置证明（:2593-2596）、`workflow_path_executed=="front_stage_flow"` 且 front 为 None 直接拒绝（:2597-2598）、`validate_front_review` 全量（:2599-2601）、decision 白名单（:2602-2604）、hydrate 一致（:2605-2608）、derived coverage 逐项表达（:2616-2629）、混合单元不得借用整段链接（:2630-2642）、全量 `validate_source_target_review`（:2643-2653）。**该消费者不要求原答身份**。
- 【事实】`_resumable_saved_source_review`（:2030-2124）才是"恢复原答证明"的持有者：front 分支要求 `source_front_target_review` 非空 + `workflow_path_executed=="front_stage_flow"` + `partial_wire is None`（:2049-2052），`validate_front_review` 全量（:2056），然后**逐 attempt 见证**（:2057-2070）：phase 标记为 `source_review` 的 attempt 必须 `sha256(raw)==raw_output_sha256` 且 `SourceTargetReview.model_validate_json(raw) == 保存的 review`，否则**抛 ValueError**（:2067）；无任何见证则 `refresh_required/front_review_receipt_unproven`（:2069-2070）。
- 【事实·不对称】基线分支（:2076-2124）依赖 `source_target_review` + 全量 `source_statement_coverage`，用 `validated_source_review_seed` 重新证明后可返回 `reused` 或 `partially_reused`（保留子集 + coverage 子集），**没有原答见证**。即：基线允许"组合/部分种子"复用，前置路径只允许"单一完整原答"复用。这个不对称是 H2 的根因。
- 【事实】deconstructor 前端合并（:7163-7196）：`covered_review` 收窄后再次 `validate_source_target_review`（:7172-7173），失败即带结构化 error_detail 失败（:7174-7194）；成功才把 `latest_source_target_review`/coverage 交给作者阶段。

**C. 恢复原答证明**
- 【事实】前端复用的统一路径是 `_resumable_saved_source_review` front 分支（仅 deep 重跑调用，:2275）。测试 `test_protocol_control_fixed_flow.py:276-330` 逐项钉死：`raw_hash`/`raw_text` 不一致 → **raises ValueError**；`no_receipt`（error_detail 缺失）→ 不采用；`partial_wire` 存在 → 不采用；完好时 → `state="reused"`，重跑 `transport.calls==["author","alignment"]`。
- 【事实】检查点在失败时保存 attempts 原文（execution :3334-3347），公开 `model_dump` 不含原文（测试注释 :296-297 与 `_deep_attempt_raw_outputs` :3367-3376 佐证），所以"保留完整来源"的层次是**检查点级**，不是公开结果级。

### 3. 关键缺陷

**H1｜结构化拒绝与有效兄弟双双丢失（已证实；被点名的"第一个工程限制"）**
- 证据：§2.1 第 3-5、8 跳；对照基线在完全相同的异常类型上做的保留（deconstructor :7548-7572 把 code/statement_id/json_path/source_refs/retry_class/affected_dependents/review_snapshot 写进 attempt；:7939-7951 失败时仍以组合 review + coverage + 结构化 detail 返回）。
- 后果：(1) 重跑必然重问 25 条（模型很可能重复同一过度声明）；(2) 下游只能看到代码+中文句子，无法定位字段级拒绝；(3) 已付费的 24 条判定被弃。
- 修复方向见 P0；这是"最小"的第一步，且不动任何门禁。

**H2｜组合式前置审核会让恢复证明硬抛异常（最高影响实施风险；P1 的硬前提）**
- 【事实】若实现"有界单项纠正"并把合并后的（宿主组合）review 作为 `source_front_target_review` 保存（通过 in-run 全程门禁 + `_validate_saved_source_review` 均可），那么一旦该 run 在**作者/对齐阶段**再失败（`partial_wire is None`），之后重跑命中 front 分支时：`validate_front_review` 通过（组合 review 是逐条真实有效的），但见证循环会拿**初始 25 条原答**与组合 review 比对 → 不等 → `ValueError("前置来源核对与实际保存原答不一致，不能复用")`（execution :2067）。这是一个**新的硬失败模式**，且被现有测试的期望（:312-315 期望 raises）间接固化。
- 【推断】该路径在真实形态下可达：修正 index2 后如果新决策是 `additional_requirement` 但不可编译（context 称该条 `force=required/functions=[background]`，`front_stage_supported_indexes` 要求含 `action`，:98-110），则 `retained` 非空、`reviews` 为空 → 以 `FLOW_COMPILER_CAPABILITY_GAP` 失败（fixed_flow :345-349），此时 `review_validated=True` → 失败结果**带组合 review**（deconstructor :7031-7032）→ 检查点写入（execution :3324-3327）→ 下次重跑抛 H2 异常。
- 【建议】P1 必须配对实现"真实原答组成证明"（per-item receipts）：见证循环改为——每条保存的 item 必须能在 phase 为 `source_review`/`source_review_correction` 的某个 attempt 的解析结果中，于**同一 statement_index 找到逐字段相等**的条目，且该 attempt 的 sha 自洽；全量门禁保持不变。保留"整条等于单一原答"的快速路径。此方案对已钉死测试**向后兼容**：`raw_hash` 仍抛（sha 失配）、`raw_text` 仍抛（该 attempt 中不存在能匹配保存条目的 receipts）、`no_receipt`/`partial_wire` 行为不变；同时把"组合不得冒充单一原答"从禁止改为"必须逐条举证"——正是 context 的 "actual raw composition proof if needed"。

**H3｜重跑成本与重试语义**
- 【事实】`retryable=False`（execution :3259-3267，语义拒绝不属于传输失败集合）；`retry_class="single_statement"` 目前**没有任何步骤层消费者**（只存在于异常对象与（修复后）error_detail 中）。人工重跑=整段 25 条重问。
- 【建议】P0 后 retry_class 至少进入 error_detail（诊断可用）；是否让步骤层读取它是决策点 D5。

**H4｜流程证据缺口（过程性，非临床）**
- 【事实】主会场计划文件全 TODO；会议 context 的 Success Criteria 要求 runner 记录 session/usage/fallback，而计划里的 Timeout/Verification 清单为空。不影响本次只读结论，但 Codex 的最终合议产物应补齐，否则"来源包"与"分工"只存在于 context 单点。

### 4. 对目标的独立审计（挑战与红线具体化）

1. **挑战字面读法**："The failure result drops the invalid front review" 不能读成"应当把无效 review 存进 `source_front_target_review`"。该字段的既有语义 = 已核前置证明（测试 :1621 明确钉死）；把无效条目塞进去会让 `validate_front_review` 在恢复消费者里直接抛异常（execution :2056 无 try 包裹），或更糟——若有人顺手弱化校验，就会把被正确拒绝的过度声明洗成可复用的"证明"。**任何保留都必须是独立类型的 seed/拒绝对，绝不复用 validated 字段。**
2. **"不能改作用范围"的具体红线**：单条复核提示必须由**未修改**的 `build_source_target_review_prompt` 基于同一 batch/interpretation 生成（它对该条仍列出全部已知官方/程序目标，:1142-1162），单条运行只收窄**调用**的索引集合，不收窄**校验**的索引集合；合并后必须过全量门禁（对照 fixed_flow :273、:287-291 与 deconstructor :7966-7978）。单条提示里禁止出现"本次只比较列出的目标"式的目标裁剪（基线的 `compare_one` 分支才是这种场景，且它只在原有失败已限定目标时使用，:7819、:7828-7831）。
3. **"不能把技术错误变临床未决"的具体红线**：宿主不得自行把被拒条目改写成 `unresolved`/`additional_requirement`；只有模型在单条复核里可以。基线既有底线话术可直接复用：:7801 "上一项未经采信…不能原样重复被拒的声明"、:7805 "不强制把失败改为增量要求"、:7807 "不能因格式或程序错误要求研究者作医学判断"。
4. **"不新建证明平台"的具体判据**：新机制若引入新的持久化证明结构（新库表/新 attestation 类型/新哈希链）即越界；复用「attempt 原答回执 + `validated_source_review_seed` + `validate_source_target_review`」三件套即可满足。按此判据，per-item receipts 是对既有尝试回执的**读取方式**扩展，不是新平台。
5. **"有据选择暂不加恢复"是合法终点的场景**：若 Codex 判定（i）真实缺陷是模型过度声明、正确处置是"每轮重问/人工重排"而不是跨轮复用；且（ii）跨轮复用所需的消费者改动会改变已钉死的篡改语义——则只做 P0（保留证据）+ 明确记录"前置部分恢复本阶段不支持"，并保留 `FLOW_RESUME_PROOF_REQUIRED`（deconstructor :6744-6746；execution :3148-3151）作为诚实边界，是可辩护的。

### 5. 建议方案（有界、全部复用既有机制）

**P0｜保留（必做，最小，不动门禁）**
1. `protocol_control_fixed_flow.py` except 分支（:376-383）：当 `isinstance(exc, SourceTargetReviewValidationError)` 时填 `result.error_detail`，字段与基线同构：`code / statement_id / json_path / source_refs / retry_class / affected_dependents / review_snapshot_kind:"rejected_front_review" / review_snapshot: {拒绝条目，可含其所属条目的 model_dump}`（范式：deconstructor :7891-7919、:7562-7571）。**不改** `review_validated`。
2. runner 无需大改：:7048-7059 已经读取 `prepared.error_detail`，P0 后其非空即落 attempt；检查点 :3334-3347 自动携带。
3. seed：仅当 `exc.retry_class=="single_statement"` 且在**不新建字段**的分支下，由检查点已有的原答回执在读取时派生（P2 的读取器），或按决策 D3 加显式键。P0 本身只要求"拒绝证据完整"，seed 属 P2。
4. 读回验证（必须随 P0 交付）：新增**生产者形状**测试——走真实 `_execute_deep` 失败路径生成检查点（不要用 `result.model_dump` 拼夹具，参考既有教训），断言 `attempts[-1].error_detail` 含上述结构化字段且 `raw_output_text` 自洽；并断言同一检查点重跑时 `_resumable_saved_source_review` 的行为与今天一致（absent/refresh，而非异常）。

**P1｜有界单项复核（推荐；P0 之后、P2 之前）**
1. 触发：仅 `retry_class=="single_statement"` 且 `statement_index` 可定位（scope 级 `REVIEW_SCOPE_INVALID` 不触发，避免"改作用范围"嫌疑）；每个失败索引至多 1 次复核（上限对齐基线 `focused_reads>=2` 的保守值，决策 D4）。
2. 调用：`reviewer(prompt=build_source_target_review_prompt(batch, interpretation, [entry]) + 结构化拒绝反馈 + 底线话术)`；新会话、原答+sha+session 全记录，phase 标记用 `source_review_correction`（供 H2 receipts 精确识别，且不污染既有"单一原答"通道）。
3. 校验与合并：单条 `validate_source_target_review(batch, interpretation, [entry], corrected)`（表内 :7834-7836）；合并 `corrected.items[0]` 回原位（:7846-7852）；**全量**重验（:7966-7978 对应物）后再进 `covered_front_wire` 与 :288 的二次全量校验。
4. 失败闭合：同型失败 → 保持今日 `TARGET_VISIT_SCOPE_UNPROVEN` 或复用基线 `SOURCE_TARGET_FOCUSED_INVALID/…` 码，附结构化 detail + 原答（:7884-7938 范式）；绝不静默降级。
5. 配对项（强制）：H2 的 per-item receipts 见证（否则 P1 会引入硬抛异常）。
6. 产品可见变化（需 Codex 确认，D6）：修正为可编译增量时，作者调用会出现（mixed 路径既有能力），失败码可能从 `TARGET_VISIT_SCOPE_UNPROVEN` 变为 `FLOW_COMPILER_CAPABILITY_GAP`/`FLOW_SOURCE_SCOPE_UNRESOLVED`——这是"模型过度声明→有据的能力缺口"的分类变化，语义更准，但改变对外错误码。

**P2｜跨轮恢复（建议有条件推迟）**
- 组成：读取时从检查点原答回执派生 seed（复用 `validated_source_review_seed`；无新字段）→ runner :7027-7029 的"仅全量种子"条件放宽为"部分种子 + 缺失索引补问" → `prepare_front_stage_flow` 接受 partial seed → 每次读取由全量门禁与 per-item receipts 重新举证。
- 判据：若 P1 落地后仍有反复重排场景（同批次多轮深审）、且团队接受消费者改动，再做；否则按 §4.5 记录"暂不加恢复"，成本更低、语义更稳。**初始建议：推迟。**

**明确拒绝的选项**
- R1 把被拒 review 存进 `source_front_target_review`（破坏语义、恢复消费者抛异常；测试 :1621 反证）。
- R2 为让流程通过而改 `target_review_indexes`/coverage/目标清单或弱化 `TARGET_VISIT_SCOPE_UNPROVEN`（无证据支持，context 明示"no evidence to weaken the gate"）。
- R3 宿主把失败条目改写成 `unresolved`/`additional_requirement`（技术错误→临床未决）。
- R4 新证明库/新 attestation 结构/新网络调用（例如去外部重新核源）。
- R5 绕过全量门禁的"直接采用有效兄弟"（任何采用仍须 :273/:288、`_validate_saved_source_review` 全量）。

### 6. 反例与边界清单

- B1 scope 级错误（`statement_index=None`）不得生成种子或单条复核（避免把"整卷范围错误"降格为例外项）。
- B2 `validated_source_review_seed` 返回 None（全部无效）：必须按"无恢复证据"处理，不能把 None 当"通过"。
- B3 索引漂移：source 修复会改 interpretation（基线有 `_source_statement_reuse_identity` :6650、`reuse_inputs_unchanged` :7497-7513 的先例）；P2 的任何种子必须绑定 statement 身份并逐次重验。
- B4 见证的 phase 过滤：H2 receipts 必须显式枚举 `source_review`+`source_review_correction`，不得用宽松前缀匹配否则未来新阶段会污染身份。
- B5 单条复核的会话是新 session（transport :1310-1328 每次 `uuid4`），上下文靠提示文本承载；记录时必须用响应自身 session_id（对照 :7668、:7959）。
- B6 成本上限：P1 的 1 次/索引、每轮 ≤2 的上限必须显式，且不得递归进入二级修复。
- B7 公开结果不含原答（:296-297）：任何"保留"验收必须对准检查点，而不是 `result.model_dump`。
- B8 若 transport 缺 `start_source_target_review`：FLOW 路径在 :266 是**无 callable 保护**的直接调用（基线 :7522-7524 有保护）；这是既有不对称，非本任务缺陷，但 P1 新增调用点建议沿用基线保护风格。

### 7. 决策点（Codex）

- D1：P2（跨轮部分恢复）现在做还是按证据推迟？我建议推迟。
- D2：若做 P1，H2 采用 per-item receipts（我建议）还是"组合即降级为 refresh"（会改动已钉死的篡改语义测试期望，:312-315）。
- D3：seed 持久化形态：读取时从原答派生（默认，无新字段）vs 显式新键（更可检视，但需新增"生产者形状"读回测试）。
- D4：单条复核触发码范围与次数上限（我建议：仅 single_statement、1 次/索引）。
- D5：`error_detail` 采用基线同构 schema（我建议）还是另立；步骤层是否消费 `retry_class`。
- D6：接受 P1 带来的失败分类变化与"混合作者调用先行"的产品行为（对应 0927V1-R1 的混合执行边界）。

### 8. 给 Codex 的有界问题

- Q1：跨轮复用"部分修正后的前置审核"是否在本任务授权范围内？若否，P0+P1 即终态，H2 的 receipts 仍需随 P1 一起交付（否则引入新硬失败）。
- Q2：允许更新 `test_protocol_control_fixed_flow.py:312-315` 的期望吗？按我的分析，per-item receipts 方案下该测试**无需修改**即可通过（raw_hash→sha 抛；raw_text→无 receipts 抛），请复核确认。
- Q3：P0 的读回由哪个消费者权威裁定——仅 deep `_resumable_saved_source_review`，还是也要覆盖 catalog/restricted 消费者（它们同样读 run result）？
- Q4：步骤机对 `PROTOCOL_CONTROL_TARGET_VISIT_SCOPE_UNPROVEN` 这类"未登记语义码"是否有 UI/重排 allowlist 需要同步？（现有参数化测试清单 :838-856 不含它。）

### 9. 不确定性与未验证

- 【不确定】未运行任何测试、未执行 git（Bash 被拒）；frozen HEAD174c3efd 的行号等价性请 Codex 复核。
- 【推断】H2 可达性来自静态路径推演（组合 review 保存 → `partial_wire is None` 的作者阶段失败 → 见证据环 ;2067/:312-315）；我没有真实重放该 run。
- 【推断】"单条校验 ≡ 全量校验对同一条"由校验器结构推断（§2.2-A），未以测试验证。
- 【不确定】真实 25 条/index2 的临床与运行细节取自 context 的 Owner observation（按 read set 我未读任何运行产物或临床材料）；"尚无作者请求"以同构测试 :1624 与代码路径支撑，非该案例的直接回执。
- 【事实】本报告未写入 `runs/conference/.../evidence_single_object.md`；如 Codex 需要落盘，请按 runner 流程处理。

**最重要的三条**：H1（已证实的结构化损失，P0 即可闭合）；H2（P1 的硬前提：组合式审核会让原答见证抛异常，必须先用 per-item receipts 或显式降级处理）；§4.1（不得把无效审核塞进 `source_front_target_review`——这是最小恢复最容易踩的红线）。
