收到 C03 续审（源关系边界）。只读、不委派、不落盘。先定位：资格边界见证、冻结字段、R1 能力路径与相关测试。

定位到关键机制：`SourceStatement.eligibility_sequence` / `eligibility_sequence_quote`（同单元先决）与 `_restricted_capability_batch`（能力缺口路径）。读取核心定义。

核心证据已现：`POST_ELIGIBILITY_SEQUENCE_UNGROUNDED`（3282-3289，同单元前置）。继续读取 target review 校验、能力受限路径、表格单元契约与既有测试。

# Conference Output: rv1006-source-scope-resume-review-20261011 - evidence_single_object

## Output

**C03 续审：源关系边界（只读；未改文件、未运行产品/模型、未读临床或私有运行；未委派）。结论：① 没有可用的现成旁路——现有"跨单元前置"机制只有表格紧邻冒号标签一条且被明确收窄，不适用于前置段落；② 最小充分改动＝**只扩展现有 `eligibility_sequence` 见证的定位能力**，语义判断仍归新核；③ 当前 R1 无法合法承载该关系缺口（能力路径按类型只认 `TIME_PRECISION_UNSUPPORTED`），因此本窗口内要么用 ②，要么保持失败不产出，**不得伪装未决/不得伪造能力码**；④ 需要一个表格归属 + 时序语义转正的对照测试族。**

---

### 1. 是否已有可用来源/消费者路径被遗漏

**[代码事实] 现有"跨单元前置"只有一条，且不适用**：`scope_context_unit_id` → `immediate_cell_scope_label`（`control_scope_sources.py:15-58`）允许引用**只读上下文单元**，但要求：与属主单元**同一表格 `table_path`**、源引用**页码/块号紧邻**（`int(left[2]) + 1 == int(right[2])`，`:33-38`）、同 `heading_path`、期别相容、且引用文本必须是**冒号结尾的单段标签**（`:53-57`：不得含 `.。!?；\n`、不得含 必须/应当/完成/执行/进行 等动作词）。前置段落（含"确认符合资格后……接受试验制剂"等）**按构造不合格** → 这不是被遗漏的路线。
**[代码事实] 可复用的既有机制**：表格成员/列头来源证明已存在——`native_schedule_visit_scope_is_preserved`（`source_interpretation.py:2841-2899`，逐列要求 `header_source_refs` 非空、每个 ref 唯一定位到 header 单元的 span、`set(header_sources)==expected_header_refs`）、`native_schedule_action_cell_is_preserved`（`:2810-2838`）、`_native_table_source_packet`（`:1699-1709`，把 `member_source_refs/member_texts/table_context` 交给核对）；`TableCellContext` 已强校验 `member_cell_paths`/`table_path`/行列头（`protocol_controls.py:380-422`）。**可复用其身份/邻接/成员引用模式，但没有现成的时序见证。**
**[代码事实] 消费端齐全**：`is_post_eligibility_calculation`（`:1184-1196`）→ 执行 `protocol_control_execution.py:5088` 与 `protocol_control_catalog_publication.py:115`。因此缺的只是**见证位置**，不是消费者。
**反例**：`target_review_indexes`（`:1663-1672`）对"列绑定 `at_or_before_baseline` 且有 `procedure_target_id`"的日程项免核——本行**无冻结给药前映射目标**，不适用；标题路径/同访视日期均不是见证（`scope_quote` 只能来自标题/表头/紧邻子句，`:3214-3242`；`immediate_cell_scope_label` 明示"只证明字面标签，不证明适用性"）。

---

### 2. 最小充分关系契约（若需要）

**[建议] 只扩展既有两个字段的定位，不新增关系对象**：为 `SourceStatement.eligibility_sequence_quote` 增加**冻结上下文单元身份**（如 `eligibility_sequence_context_unit_id`），`SourceTargetReviewItem.non_control_basis_excerpt` 复用同一见证。**确定性检查（只证位置）**：① 上下文单元在 `batch.context_units` 中唯一、不在 owned、字节/摘要冻结；② 边界摘录逐字属于该单元 excerpt；③ 源顺序：上下文单元 `source_order` < 属主单元，且（表行场景）为该表之前**紧邻**的正文块；④ 属主必须是表格成员单元格且 `member_cell_paths==[table_path]`（沿用 `:42-43` 模式）；⑤ 对象/表归属：见证须绑定**对象列头的逐字原文与 header/member 引用**（沿用 `:2875-2896` 的 refs/spans 闭合），并拒绝"边界对象 ≠ 属主列对象"、拒绝引用另一 `table_path`、拒绝缺失 header 引用。
**必须仍由源语义核对判定（不可机械化）**：引用边界是否真的管辖**这一个**对象/动作；先后方向（"资格确认后给药" vs "给药后确认资格"）；合并单元格中属主是研究用药还是背景用药（除非列头对象已确定，否则仍需核对）；措辞本身时序不明时**不得形成见证**（保持 `current_or_unknown`、fail-closed）。
**[反例] 不得单独作为依据**：共享标题、精确药名、同访视日期、字面一致、仅 `scope_context_unit_id` 标签——均不构成见证；本契约只有**完整元组**才有资格，任何"部分命中"路径都应拒绝。
**[代码事实] 语义侧仍保留既有锁**：`validate_source_target_review:2305-2323` 现要求 `not_current_control` 的 basis 与陈述见证一致、不得仍有候选、不得有未决面；`validate_source_interpretation:3282-3289` 现要求同单元前序——扩展只改这一处定位，其余不动。**边界评估**：该改动限于 1 个模块 2 个校验函数 + 1-2 个字段 + 测试，不算框架；若推广成"普通前置段落可支持任意关系"则过宽，应拒绝。

---

### 3. 本窗口是否需要表格专属关系支持；现有 R1 能否承载

**[代码事实] 不能。** `_restricted_capability_batch`（`restricted_source.py:228-318`）要求末次错误类含 `TIME_PRECISION_UNSUPPORTED`（`:243-244、253`）并以 `limitation_kind="consumer_unavailable"` + 明确"小时/分钟精度"文案记录（`:311-312`）；`capability_wire` 仅在 `TIME_PRECISION_UNSUPPORTED` 且无其它类时生成（`deconstructor.py:11316-11334`）。语句级受限（`:653-800`）只接受 `unresolved`/`additional_requirement` 复核决定（`:697-700`）；整单元受限只接受 `{SOURCE_TARGET_REVIEW_UNRESOLVED}`/`{TEMPORAL_SCOPE_UNRESOLVED}`（`:461-463`）。**关系能力缺口没有类型化承载**：填 `unresolved`＝把已知关系伪装成来源歧义（禁止）；填 `TIME_PRECISION_UNSUPPORTED`＝伪造能力码（禁止）。
**[推断] 因此按窗口目标二选一**：若目标是"**不错误采用**"——现况已满足（该行保持 `current_or_unknown`，不产生受限语句，批次失败/待核，无共同发布）；若目标是"**正确把该行排除出当前控制并可产出**"——需要 §2 见证或一个**新的有界能力码**（同族小扩展，非框架）。不建议本轮同时新增能力码与见证（双轨）；优先 §2，因为它的消费者已存在且无需改动。
**[建议] 顺序**：先修关系见证；行内"数值守卫"问题（C03 上一轮）是**后续独立能力**，不要与关系见证捆绑发布；关系未见证前，数值守卫即便修好也不能安全放行该行。

---

### 4. 测试（生产/保存/消费命名；仅 helper 通过不算）

**[代码事实] 既有锚点**：`test_post_eligibility_action_requires_source_order_and_no_current_candidate`（`test_slice58c_control_deconstructor.py:3825-3898`，含次序错、未确认、仍有候选三类拒绝）、`test_runner_rejects_candidate_for_action_after_eligibility_decision`（`:3901+`）、`test_shared_scope_must_precede_the_action_and_survive_target_review`（`:1955-1990`）、`test_source_inventory_corrects_embedded_eligibility_basis_locally`（`:2587-2598`）、`test_schedule_row_with_enrollment_columns_cannot_be_discarded_as_post_treatment`（`:6865-6897`）、`test_marker_only_randomization_row_is_not_new_eligibility_control`（`:6819`）。
**[建议] 新增四类**
1. **正向**：前置段落置于 `context_units`、表行为 `owned_units`（合并列头 + 独立背景列）；断言只有**完整见证**才通过 `validate_source_interpretation`，`validate_source_target_review` 需 basis 一致且无当前候选，`is_post_eligibility_calculation` 转真；消费端 = 执行 `:5088` 与 `catalog_publication:115`（保存后重读仍成立）。
2. **同义布局**：边界在（a）同属主单元（既有正例）、（b）紧邻前置上下文单元（新增）、（c）表题/首块变体——**等价布局同判**；段落位于表后、或同措辞但跨章节 → 由顺序/身份拒绝。
3. **对象/时序反事实**：属主引句落在**背景列**而边界只述研究用药 → 列头对象不符即拒；边界为"给药后确认资格" → 定位可过但**新核不得选 `not_current_control`**（断言未选时 `is_post_eligibility_calculation` 为假）；引用另一张表 / 缺 header 引用 / 时序措辞不明 → 各自拒绝或保持 `current_or_unknown`（fail-closed，且不得生成受限语句）。
4. **恢复证明失效**：改动上下文单元字节、`source_order`/`table_path`、列头 refs、复核 basis 后，`validate_source_interpretation`/`validate_source_target_review`/`_coverage_matches_current_proofs`（`restricted_source.py:61-82`）与既有对齐复用（`reusable_proven_alignment_items`）必须拒绝旧证明；见证须带摘要以便保存重放失败。
**生产/保存/消费命名**：生产＝两个校验器 + `target_review_indexes`；保存＝既有冻结模型字段（上下文单元身份在 batch 内，不建新存储）；消费＝`is_post_eligibility_calculation` → 执行与目录发布；**仅改 helper 而不改两个校验器与消费断言＝不算通过**。

---

**决定性的源观察 / 不确定 / 可选**：决定性——同单元定位规则在两处独立实现（`:3282-3289`、`:2305-2313`），扩展必须同步，否则复核会拒；`immediate_cell_scope_label` 的邻接/成员约束是最接近的先例，复用其检查模式而非其语义。不确定——源引用格式是否总支持"段落块紧邻表格块"的邻接证明（`(.+)\.p(\d+)` 模式在 `:33-34`）；若不能，退化为严格 `source_order` + 同 `heading_path` + 表前无其它表格插入。可选——若窗口只求不误采用，保持现状失败即可，无需本轮改动。
**独立性折减**：同族模型（仅适配器/上下文不同）；以上为源码合同级分析，不构成医学批准，也未对真实材料作任何诊断或建议。

**证据清单**：`protocol_control_source_interpretation.py:245-275、1128-1196、1643-1677、2111-2326、2805-2899、3166-3310、3419-3421`；`protocol_controls.py:380-486`；`control_scope_sources.py:15-117`；`protocol_control_restricted_source.py:228-335、461-463、653-700`；`protocol_control_deconstructor.py:11316-11334`；`protocol_control_execution.py:5088`；`protocol_control_catalog_publication.py:115`；测试 `test_slice58c_control_deconstructor.py:1955-1990、2587-2598、3825-3898、6819、6865-6897`。限制：未取 git diff；`procedure_catalog.py` 行/成员/表头 helper 仅按引用面取证，未逐行通读。
