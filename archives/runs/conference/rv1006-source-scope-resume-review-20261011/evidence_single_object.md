Trellis SessionStart 上下文已加载。

开始只读核查。先定位全部指定符号。

定位完成。现在读取核心定义与调用链。

核心定义已读取。现在读取调用点、候选对齐、受限来源与执行恢复的接线。

已读取调用点与恢复接线。现在核查 `continue_scoped_unit_repair` 的异常处理路径、受限来源消费端与测试引用。

继续读取错误消费路径、保存路径、受限来源消费端与既有测试契约。

继续核查错误消费分支、scoped 调用失败后的返回，以及受限来源消费端定义位置。

aborted

网络中断已恢复。继续读取受限来源消费端（两个入口函数）。

补一个关键判定：scoped 修复传输失败的失败码映射（决定任务级 retryable 与否）。

# Conference Output: rv1006-source-scope-resume-review-20261011 - evidence_single_object

## Output

本轮为只读工程核查（未改源码、未运行产品模型/测试、未读临床原件与私有运行）。工具用量：定位类 grep 9 次 + 目标读取 14 次（文件读取 ≤16）。以下标注 **[代码事实]**（我实际读到的行）、**[推断]**（由代码路径推导，未直接读到运行产物）、**[建议]**、**[不确定]**。

---

### 1. 生产是否区分“上下文标题 / 判定阶段绑定 / 患者人群”？是否存在决定性缺失证据/输入

**结论：在“输入与授权”层面区分充分；在“裁定”层面不做机械区分，没有决定性代码输入缺失，缺的是本次运行的具体证据。**

**[代码事实] 三个概念的载体是分开的：**
- 上下文标题：只读上下文走 `read_only_context_sources`，单元自身文本走 `source_unit`；`build_candidate_alignment_prompt` 明确禁止借标题新增条件——`app/agents/protocol_control_candidate_alignment.py:627-628`：“仅当本句的‘任一项’等回指在同一冻结来源单元中有唯一明确的先行要求时，可引用该要求解释所指对象；**不得借标题、其他来源单元或不明确的邻句新增条件**。”多单元闭包另给告诫：`candidate_alignment.py:607-609`（其他闭包原文不能仅因本句未重述就判为新增，也不得把无关邻句限制借给本条）。
- 判定阶段绑定：`bound_visit_sources` 只列候选绑定的冻结访视及其**原始表头来源**（`candidate_alignment.py:568-571`），与全量 `workflow_stage_sources` 并列；指令 `candidate_alignment.py:632-635` 明确“bound_visit_sources 仅说明绑定访视及其表头来源……**不证明动作、脚注、例外、结果条件或资料限制已完整表达**”“不得把另一列或缺出处的访视标签借给当前动作”。表格单元的 `native_review_scope`（`candidate_alignment.py:589-601`）同时给出逐列标记与只读表头，并声明它不是采信结论。
- 患者人群：`candidate_alignment.py:598-600`：“候选的通用记录主体并非自动新增人群筛选条件；核对的是实际适用对象、范围与条件……**特定亚组、对象改变或新的限制仍必须有原文依据**”。反向也被禁止：`candidate_alignment.py:611-612`（不得用操作完成替代结果条件，也不得新增原文没有的结果正常要求）。

**[代码事实] 这些输入被冻结进证明身份**：`_alignment_input_identity`（`candidate_alignment.py:650-701`）把 statement、source_unit（含标题在内的整段单元文本）、表格单元的 `native_review_scope`/`bound_visit_sources`/`context_units` 等一并哈希；`reusable_proven_alignment_items`（`candidate_alignment.py:790-831`）要求单证唯一、`validate_candidate_alignment` 通过、身份哈希与回执逐字节一致，才允许复用该判定。任何标题/阶段来源变化都会使旧负判定失效而必须重核。

**[推断] 因此：**
- “负判定”足以授权一次**有界改写**（它只允许在同一来源闭包内重提案，且改写后必须过完整闸门与**新一轮**对齐核对，见 §2/§3），但**不足以断言候选有缺陷，更不构成采用**——这正是“不把未证候选转成已采用的来源歧义”的机制基础。
- “会不会把标题当许可加限制”不是靠确定性校验器判定的，而是靠**同族模型审阅者**按上述指令判定；生产没有（也不需要）一个“该限制来自标题”的确定性分类器。
- **决定性缺失证据不在代码里，而在本次运行产物里**：该负判定的 `response_text`（`unresolved_dimensions` 原文）、涉事候选的 `bound_visit_sources`/原子文本、三个 statement 与单元摘要（含标题）。没有它们无法判定“阶段限制是标题借入（审阅者误判）还是候选新增（审阅者正确）”。**[不确定]** 另有一处未读：`_statement_grounded_atoms` 生成 `allowed_candidate_atom_quotes` 时是否可能把单元内标题文字纳入允许引句；若可，需要加一条可核对的边界（但改写仍受新对齐与全闸门约束，风险有限）。

**直接回答“标题不是许可”**：代码层面标题**从未**被当作新增限制的依据；`candidate_alignment.py:627-628` 是明文禁止，且逐字引句（`source_excerpt` 必须逐字等于 `required_source_excerpt`，`candidate_alignment.py:631、749`）与原子引句白名单是确定性防线。

---

### 2. 单元级一次性标记是否有意为之？建议何种恢复

**结论：标记是**有意且已被测试**的**一次性授权账本**，此处应保留；不要清除标记、不要刷新 `source_repair_limit`。恢复必须按“被消耗的原因”分流；仅当原因被证明为“未送达”（无任何模型答复）时，才值得最小因果绑定提案（receipt 化，总次数 ≤2）。

**[代码事实] 关键路径：**
- 门控与消耗（`app/agents/protocol_control_deconstructor.py:10514-10528`）：只有“未在该单元标记中 + transport 具备 `continue_scoped_unit_repair` + `max(repairs, source_repairs) < max_schema_repairs`”三条件同时成立，才会 `reviewed_semantic_repair_units.update(...)`（10525）后 `raise semantic_repair`（10528）。**标记先于调用写入**，语义是“授权已消耗”，不是“修复已成功”。
- 同轮/续轮都不再重复（10520 的 `not ... & reviewed_semantic_repair_units`）；被挡住时走 10529-10556：追加 `publication_invalid` 的 `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED` 并返回“需要核对”，**不再发模型调用**。
- 恢复校验（7547-7552）：标记必须是唯一 str、⊆ 当前 `batch.owned_structure_unit_ids`，且必须随 `resume_wire` 恢复；`build_result` 默认写回（7558-7559），执行层从保存草稿读取（`protocol_control_execution.py:4549-4550`）并写入失败诊断（4663）。集合只增不减（grep 全库仅 10525 一处 `update`）。
- 测试契约：`tests/v2/protocols/test_slice58c_control_deconstructor.py:14749-14835` 明确断言：`unchanged/bad_json/escape` 后 `reviewed_semantic_repair_unit_ids == ["su-02"]`（14826），再次恢复 `scoped_calls == 0` 且 `final_output is None`（14834）；`14838-14845` 断言非法标记直接 `ValueError`。**你所观察到的“单元 ID 已在标记中→不能再修”就是这一被冻结的行为，不是故障。**

**[代码事实] 已存在的有界显式恢复（无需动账本）：**
- **预算型恢复**：门控含预算条件。测试 `reply="budget"`（`max_schema_repairs=0`）时 `scoped_calls == 0`，且标记未被消耗（14814 与 14824 分支）；即“因额度未发起”不会消耗授权，后续以预算恢复的运行仍可尝试一次。这是系统内已有的显式恢复通道。
- **诚实终点恢复**：标记被消耗后恢复运行会走到 10529 的 `publication_invalid` 落点，从而让 `restricted_batch_from_review`（`app/services/protocol_control_restricted_source.py:868-909`）判断能否对其余真正未决单元产出不可执行受限批——它要求末次尝试为 `publication_invalid` 且错误类 ⊆ {`SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`,`SOURCE_TARGET_REVIEW_UNRESOLVED`,`TEMPORAL_SCOPE_UNRESOLVED`}（872-884、670-678），且源逐项复核/覆盖必须与当前证明一致（`_coverage_matches_current_proofs`，61-82）。[推断] 这是“另一个真正未决时间锚”单元能拿到诚实受限结果的路径；若同一批内它与被负判定单元互不交叉（797-800），可以成立。
- **新谱系**：全新的、显式授权的深析来源作业（空标记重跑）。调用有真实成本，但符合“可测试调用、无任意总上限、但不抹账本”的边界。

**[代码事实] 最高影响缺陷候选（本次核查重点）：传输失败会消耗一次性授权。**
- scoped 调用异常路径（12087-12114）：记录 `outcome="transport_failed"`，`error_classes=[protocol_control_call_failure_code(exc2)] if ... else []`，然后**立即返回 `build_result(status="需要核对", ...)`**；因 `build_result` 默认写回标记，**该单元的一次性授权被消耗**。
- 失败码映射（`app/agents/protocol_control_agent_transport.py:332-349`）：身份错→`MODEL_IDENTITY_INVALID`；额度→`LOGICAL_BUDGET_EXHAUSTED`；`uncertain_completion`→`FLOW_COMPLETION_UNCERTAIN`；**普通连接异常→`None`（error_classes 可为空）**。
- 执行层（`protocol_control_execution.py:4610-4629`）：retryable 白名单（4615-4624）不含上述任一种；末次 `transport_failed` 也**不满足**受限批的 `publication_invalid` 前置（670-677、892-895）→ 直接 `StepFailure(retryable=False)` → failed_final。即：**同一批里其他真正未决单元也拿不到受限批**，一个单元的瞬时连接故障把整批变成终局失败，且不可在本谱系内重试该单元。
- 需要强调的一致性：[推断] 由于单元级禁止重试，任务级若把 scoped 传输失败标为 retryable 只会制造“无法前进的重试”，所以当前“单元不可重试 + 任务不可重试”的组合是自洽的设计，而非两个独立漏洞。真正的问题只在“无信息失败”也消耗了带信息才应消耗的授权。

**[建议] 按原因分流（不改源码即可执行）：**
1. **先读收据定因**（不变量：旧状态与回执不可变）。若该单元末次 scoped 尝试 `outcome=="publication_invalid"` 或 `raw_output_text` 非空（有答复：坏 JSON、越界、未变、过闸失败），**保留现状**——这是有信息结果，停止正确；剩余语义疑点按“需要核对”交责任方，或按需走预算型/诚实终点/新谱系恢复。
2. 若 `outcome=="transport_failed"` 且无任何答复：优先**已有有界显式恢复**——(a) 若首因是额度未消耗（标记为空）直接用预算恢复一次；(b) 否则恢复一次以产出诚实终点（受限批或显式“需要核对”失败）；(c) 临床/产品确需再修时，走**新显式授权的深析来源作业**（新谱系，空标记，不触碰回执）。
3. **仅当 (2) 全部穷尽且 Codex 决定要第二次有界尝试**，才采纳下述**最小因果绑定提案契约**（receipt 化，不新增编排框架）：
   - 标记由 `list[str]`（4429）升级为并列保存的收据列表：`{unit_id, attempt_ordinal, cause_class, error_code, precondition_sha256, raw_output_present}`；读取点 7547-7552、门控 10520-10528、传输异常点 12087-12114 三处最小改动。
   - 可在**同一谱系**再尝试的充要条件：收据 `cause_class=="transport_no_answer"`（`transport_failed` 且无原始输出；`FLOW_COMPLETION_UNCERTAIN`/空错误码属此类）**且**负判定条目仍与当前 wire 身份绑定（`reusable_proven_alignment_items` 同一校验）**且**预算允许；总尝试数 ≤2；第二次无论何种失败均为终局。有答复的失败（含 `MODEL_IDENTITY_INVALID`、额度类、坏 JSON、越界、未变）**永不再试**。
   - 明确不做：不清标记、不重置 `source_repair_limit`（4518-4523 已把额度做成单调上限）、不放宽来源闸门、不做无条件循环、不新框架。

---

### 3. 最小真实生产/保存/消费路径 + 测试与独立性折减

**[代码事实] 最小路径（全链）**
- 生产：`protocol_control_deconstructor.py:5128-5166`（`_reviewed_semantic_closure_repair`；复用过滤器 `candidate_alignment.py:790-831` `require_positive=False`，身份 `:650-701`）。前置：恰好一个单元、该单元无 `unresolved` statement、所有触及该单元的候选闭包恰等于该单元、候选 ID 完备（5151-5158）。
- 门控/消耗：`deconstructor:10514-10528` →（异常消费）`11040-11223`（闭包扩展与 `closure_candidate_source_union <= error.structure_unit_ids` 授权逃逸检查 11078-11087）→ scoped 派发 `11816-11822、11966-12016` → 拼接（`5102-5125`，`REPAIR_SCOPE_ESCAPE` 全套）+ `_restore_bounded_wire_repair(allow_source_closure_rewrite=True)`（5169+/8784/8822）→ 完整重验 → 新对齐 → 终局或 `publication_invalid`。
- 保存：结果字段 `4429` ← `build_result` 默认 `7558-7559` ← 执行层草稿读取 `protocol_control_execution.py:4549-4550`、失败诊断 `4655-4667`。
- 恢复消费：`7547-7552` 校验；`10520` 阻断；`restricted_source.py:868-909 → 653-800（语句级受限）/447-624（整单元受限，要求末次错误类恰为 `{SOURCE_TARGET_REVIEW_UNRESOLVED}` 或 `{TEMPORAL_SCOPE_UNRESOLVED}`，461-463）`；执行层 `4561-4629`。

**[建议] 测试（复用 `test_slice58c_control_deconstructor.py` 的 `_FakeTransport` 与 `_two_independent_candidate_linked_alignment_material`）：**
- 正向（语义保持，已有）：`14749-14835[valid]`——scoped 改写被拼接、新对齐翻正、兄弟候选/处置原样（14819-14820）。
- 有界负向（已有）：`14715-14746` 参数化 `unbound/positive/ambiguity/shared_source/two_units` 全部返回 `None`——没有绑定负判定、或单元不完整、或候选跨源，就不得授权。
- 恢复契约（已有）：`14838-14845` 非法标记直接拒绝；`14826-14835` 标记持久且恢复不再调用。
- **危险负向（建议新增）**：`continue_scoped_unit_repair` 返回越界/坏 JSON/未变时，断言“标记已消耗 + 恢复 0 次调用 + `final_output is None` + 无采用”；再加一例：改写后新对齐仍判 `incomplete` → 终局“需要核对”，**不得**出现第二次 scoped 调用或 `continue_session` 兜底（沿用 14794 的 `pytest.fail` 守卫）。
- **因果绑定恢复（仅当采纳 §2.3）**：① 首轮 scoped 抛连接异常/`uncertain_completion=True` → 收据 `transport_no_answer`、无原始输出；恢复且身份不变、预算允许 → 恰好多一次（ordinal 2）；第二次仍失败 → 终局不再调度（大预算也不调第三次）。② 同一收据下负判定身份已变 → 不自动再试，落“需要核对”。③ 有答复失败（如 `escape`）→ 永不再试。④ 预算型反向对照：`max_schema_repairs=0` 首轮不消耗标记，恢复后允许一次（固化既有恢复语义）。
- **诚实终点（建议新增）**：传输失败被消耗后，恢复一次，断言要么产出 `_restricted_statement_batch_from_review` 的不可执行受限批（无假采用），要么显式 `需要核对` 失败——两者皆可，但**不得**把未证候选转成受限“来源歧义”语句（负判定候选若与未决单元相交，797-800 必须拒绝）。

**[代码事实+注明] 独立性折减**：本审阅者与产品模型同属 DeepSeek 家族，仅适配器与会话上下文不同；以上结论是**源码合同级**工程核查，不构成医学/临床批准，也未验证本次运行负判定的医学正确性。对“阶段限制/人群/标题”边界的医学裁定需要非同族审阅者或人工裁定。

---

### 4. 证据是否不足；精确缺失项

**[代码事实] 合同层面证据充足**（上述行号均可定位、测试已固化）。**[不确定] 本次运行产物不足**，缺且只缺：
1. 被标记单元末次 scoped 尝试的收据：`outcome`、`error_classes`、`raw_output_text` 是否存在（决定“有信息 vs 无信息”，即 §2 分流）。
2. 该负判定的 `source_candidate_alignment` 证明回执（`response_text` 中的 `unresolved_dimensions` 原文）。
3. 涉事候选 payload（`bound_visit_sources`、`review_node_bindings`、被指“另加阶段限制”的原子/前置文本）与三句 statement 的 `quoted_text`、单元摘要（含标题）。
4. 当前运行实际走的恢复分支（加载了 `resume_alignment_saved` 还是重新派生对齐）。
这些缺失**不阻塞** §1-§3 的合同结论与分流建议；只阻塞“本单元该不该再修”的最终裁定。缺失期间可继续的其他独立工作：核对其他未决单元（如真实时间锚单元）的受限批资格（447-624、653-800）、以及 §3 测试。

---

### 5. 我的反对意见、建议、决策点与给 Codex 的有界问题（主动项）

**最重要反对意见**
1. **“无信息失败”消耗一次性授权**（12087-12114 + 7559）：瞬时连接故障把可修语义缺口变成谱系内不可恢复的终局，并连带阻断同批其他真正未决单元的诚实受限终点（670-677、892-895）。这是我在本审阅中发现的最大可操作缺陷候选。修复顺序：先读收据定因 → 已有恢复 → 仅“未送达”情形才做收据化二试（≤2 次/单元/谱系）。**反对**任何清标记/刷额度/放宽闸门的方案。
2. **反假设**：“用户允许测试调用”不等于“应把第二次调用花在同一单元”。若收据显示是**有答复的负判定**，正确动作是修正提示/来源范围或接受未决，而不是重复消耗模型预算——重复不会改变新对齐仍由同族模型给出的结论。
3. **提示可能的二次误判**：若 `allowed_candidate_atom_quotes` 可能纳入标题文字（未读 `_statement_grounded_atoms`），建议加一条确定性断言或测试；这是“标题不得成为限制依据”的最后一道机械防线（其余由提示与全闸门承担）。

**建议**：采纳 §2 的分流 +（仅必要时的）收据化二试契约；补齐 §3 的“危险负向/诚实终点”测试；把“末次尝试原因”写进既有人工复核提示文案（4651-4652 已具雏形），让责任方无需重读全案即可裁定。

**决策点（需 Codex 或用户裁定）**
- P1：本次单元采取“直接接受需要核对”还是“走一次恢复以取得诚实终点”？
- P2：是否授权收据化最小二试契约（仅“未送达”情形，≤2 次/单元/谱系）？还是以新谱系作业替代？
- P3：对“阶段限制/人群”负判定是否需要一次非同族人工裁定后再决定是否重跑？

**有界问题（Codex 可同会话答复）**
- Q1：该单元末次 scoped 尝试的 `outcome`/`error_classes`/是否有 `raw_output_text`？（决定 §2 分流）
- Q2：当前 failed_final 的最后一次 attempt 是 10529 的 `publication_invalid` 落点，还是 12088 的 `transport_failed`？两者恢复含义不同。
- Q3：若 Q1 为“无信息失败”，是否授权收据化二试（契约见 §2.3），还是指定新谱系作业？
- Q4：是否提供该负判定回执原文与候选/原文文本（§4 的 2、3 项），以便用一次确定性检查回答“标题借入还是候选新增”？
- Q5（边界确认）：“旧状态与回执不可变”对我意味着**不得编辑保存草稿中的标记**；请确认我按此执行（我不建议也不执行任何标记清除）。

**证据边界声明**：以上“代码事实”均来自本轮读取的公开源码与测试；“运行产物”类判断（哪些尝试实际发生、哪一分支被走）均为推断，需以 Q1/Q2 的回执核对。本报告不构成医学批准，也不改写任何临床结论。
