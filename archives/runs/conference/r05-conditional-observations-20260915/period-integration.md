# Conference Output: r05-conditional-observations-20260915 - evidence_single_object

## Output

同会话第三轮只读源码审阅（未写/运行测试、未import应用、未访问DB、未调用模型/服务、未修改源码、未读workspace外资料；源码审阅通过≠产品/临床验收）。已完整核查本切片（未来期间声明核实的producer→consumer链）受影响定义及相邻消费者。

### 一、总裁决

切片的核心保护**成立**：期间守卫在三层独立实现且互相不依赖对方善意——载荷校验（`app/llm/proposition_evidence.py:135-139`）、合格消费者逐路重推导（`app/services/qualified_proposition_evidence.py:74-81`）、组合器双路重推导含缺路/缺块兜底（`app/projections/control_calculation_experiment.py:92-105`）。未发现可绕过期间守卫达到确定关系的路径。但发现 **1个中高严重度生产端缺陷（D1）**、**1个高严重度报告呈现缺陷（D2）** 及2个低severity加固点。

### 二、逐项核查结果（证据）

**期间守卫不可绕过（观察，正面）**
- 模型侧：非 prospective 配对必须返回 null、prospective 配对必须携带块（`proposition_evidence.py:128-129`）；确定关系仅当 `statement_of_intent` + `period_correspondence=supported`（:135-139）；`requirement_quote` 须逐字属于本条件方案摘录（:131），`period_quote` 须逐字属于该配对 locator（:133）。
- 消费者侧：`select_qualified_relations` 对 prospective 配对逐路附加 `unresolved_codes()`（`qualified_proposition_evidence.py:75-81`）——`ongoing_conduct→future_conduct_not_established`、期间非supported→`prospective_statement_period_unverified`、缺块兜底同名（合同 `app/domain/contracts/proposition_evidence.py:32-40`）。带原因的配对落入 per-pair 未定清单。
- 组合器侧：`_proposition_observation` 在任何时间处理**之前**重读全部 record 的两路 lane（`control_calculation_experiment.py:92-105`）：lane 集不合 → UNKNOWN；future 为 None → 未定；否则按结构化维度重推导。手工构造的 relation 字典（无合规 lane）同样被 ：96-97 拦截。
- 单观政策收缩防护：prospect 未定配对被丢弃后，`scope_candidates_complete = source_content_pairs == set(pair_ids)`（`app/services/qualified_binding_selection.py:552-556`）会变 False，`_universal_statement` 因此不成立（`control_calculation_experiment.py:143-153`），all 政策不能凭收缩后的集合宣称全覆盖——落入 `observation_scope_completeness_unverified`。

**声明≠持续履行（正面+缺陷D2）**
- 语义时间操作数与期间证明分离成立：`control_operand_calculation.py:78-87` 修订后，非确定性 v2 规格不因原子级 `prospective_period` 拒算时间（时间结果供 `_proposition_observation:108-127` 的 time_purpose 核对），而期间证明只读 lane `prospective_evidence`，两数据源无交叉；确定性未来履行仍被拒（:82-87）。
- 确定结果附注 `prospective_statement_verified`（`control_calculation_experiment.py:128-130`），经 `control_review_outcome.py:86-87` → API `review_history.py:588`（`reason_codes + observation_reason_codes` 无条件合并）→ 前端映射 `frontend/src/domain/reviewConditionNotes.ts:11`（“……不代表未来行为已经履行”）。
- **D2（高，屏幕端呈现缺失）**：API 已携带该注记，导出路径无条件渲染（`frozenReviewExport.ts:51`），但屏幕端控制要求单元格把 notes 限定在 `status === "unverified"` 时才显示（`FrozenReviewReport.tsx:152-155`）——**确定（fulfilled/unfulfilled）的声明核实义务在屏幕上只显示状态标签，不显示“声明≠未来履行”限定语**，与导出不一致，正是“声明被误报为持续遵守”的呈现面。最小修正：控制单元格改为无条件渲染 `reviewConditionNotes(item.reasonCodes)`，把 unverified 专属兜底文案留在状态判断内；条件级同款门控（:116 仅 unknown 渲染 vs 导出 ：38 无条件）今日无实际影响（官方谓词确定结果不携带注记），建议同批对齐。

**历史哈希/读取行为（观察，正面）**
- `proposition_sha256` 现纳入 `prospective_period`（`proposition_evidence.py:29-33`），v4 旧结果对新身份必失败；回执重建按 v5 消息哈希重放（`proposition_evidence_receipts.py:47-52,113-123`）。
- 回执门槛拒绝旧任务：contract `proposition-evidence-job/v2` + prompt v5 + summary v2 之外一律“只能读取当前版本”（`proposition_evidence_receipts.py:24-27,87-91`）——旧 v1/v4 作业不可再被现行消费者读取（fail-closed；注意：仍有效的旧采信授权若引用旧作业将硬失败而非降级处理，符合“不混入新方法”）。
- `ControlCalculationExperiment` 字面量联合保留 v3–v10（`control_calculation_experiment.py:27`），旧存储载荷仍可解析；selection_payload 版本串升 v10（:356）。冻结评估器保持 v15（`frozen_review_calculation.py:27`），本切片未动官方求值语义。

**来源/身份绑定（正面）**
- `requirement_quote ⊆ spec.source_excerpts`（:131），而 spec 摘录已被校验 ⊆ 原子摘录（`control_evaluation_spec.py:88-93`）——引用链闭合；比较一致性键含 prospective 结构化维度、引用文本不参与一致性（`proposition_evidence.py:29-30,103-107`），引用逐路逐字校验（llm:120-134）。

**方法授权隔离（正面）**
- `require_proposition_method` 要求 manifest 方法行的 `content_prompt_version == v5`、`content_summary_version == v2`、`content_consumer_version == v4`（`qualified_proposition_evidence.py:17-23`）——现存任何旧方法评测（v4/v1/v3）都不匹配，在新的已评测方法+采信授权签发前，任何正式消费都会被拒，与“无新采信批准”一致。

**未决证明到达报告（正面）**
- 链路完整：per-pair 原因 → `unresolved_proposition_pairs`（`qualified_binding_selection.py:622-627`）→ 冻结 pair gaps → 组合器 UNKNOWN 时合并进 `unresolved_atoms`（`control_calculation_experiment.py:338-350`）→ `control_review_outcome.py:44-48,66-67,86-87` → API :585-588 → 前端 `unverifiedEvidence` 无条件渲染（`FrozenReviewReport.tsx:156-157`）。前端四个 prospective 注记文案齐全且准确（`reviewConditionNotes.ts:8-11`）。

### 三、缺陷与最小修正

**D1（中高；生产端输入死巷）**：`requirement_quote` 只对 **evaluation spec** 的摘录校验（`proposition_evidence.py:131`），且提示输入中条件块被整体替换为仅含 spec 摘录的字典（:44-52，模型看不到原子级摘录）；而 `prospective_period` 声明在**原子**上，门只保证期间句在**原子自己的**摘录里（`protocol_control_gate.py:2864-2882`；解构指引 `protocol_control_deconstructor.py:1364`），`validate_control_atom_evaluation` 从不要求 spec 摘录覆盖期间句。若解构把期间句只放原子摘录，任何合法 `requirement_quote` 都不存在 → 每次双路读取校验失败 → 作业无法完成（fail-closed 但系统性死巷+重试烧钱）。最小修正（推荐前者）：门+解构提示要求“带 prospective_period 的非确定性原子，其求值规格 `source_excerpts` 必须包含期间要求句”；或在 ：44-52 条件块中同时提供原子摘录并让 ：131 接受两集合之一（改动更大，二选一即可）。

**D2（高；屏幕端声明误报面）**：如上，`FrozenReviewReport.tsx:152-155` 的 `status === "unverified"` 门控吞掉确定结果上的 `prospective_statement_verified` 注记。最小修正：无条件渲染 notes，兜底文案留在状态判断内。

**D3（低；合同级防线补齐）**：`PropositionEvidenceCheck.validate_basis`（合同 :70-101）本身不强制“确定关系须 statement_of_intent+supported 期间”——现由载荷校验+两处重推导兜住，树内无裸读者；但未来直接读 summary lane 记录的新消费者可能绕过。最小修正：在合同 validator 增加同款条件判断（约3行）。

**D4（低；观察）**：`review_history.py:565-567` 对 not_selected 原因用两段硬编码中文且含 else 兜底（“按方案规定的检查先后顺序……”）。对现行两种原因（`observation_selection.py:11`）准确；复查切片新增原因种类时 else 分支不得静默吸收——届时改为穷举匹配或走 notes 映射。

### 四、范围诚实声明

确认以下**未实现**且本轮未被描述为完成：官方谓词 prospective 消费（`expression.py:478-481` 守卫原样、`_spec` 仍拒谓词族 `proposition_evidence.py:18-21`、采纳授权仍限控制族 `qualified_binding_selection.py` 合同 ：79-82）；发生次数事件计数（无计数分支，occurrence 守卫无条件）；复查关系（无任何 relation/retest 合同或作业文件；`QUALIFIED_BINDING_CONSUMER_ALGORITHM` 仍为 v11 未动）。同意所有者判断：复查需显式来源关系；事件计数不能仅凭 `stable_identity` 断定临床去重（两次诊断可为同一病程 episode）——计数单位与 Episode 语义须在实现切片中显式解决，不得默认 stable_identity 已回答该问题。

### 五、边界

静态审阅；未运行任何验证。双路模型能否在 spec 摘录含期间句时稳定产出正确的 requirement_kind/期间对应，须经隔离评测；D1 修正后建议先以真实解构样本核对摘录覆盖再谈方法评测。本轮未涉 UI 实机浏览器验证（D2 修后按项目惯例需 1080P/2K/4K 核对）；未涉 DB 迁移（本切片无迁移面）。
