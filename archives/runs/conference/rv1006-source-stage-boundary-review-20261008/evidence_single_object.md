我先读会议指定的上下文和主会场计划，只核对两个源范围阻断的最小修复位置，不改代码、不写报告文件。上下文把审查范围收在现有源解释、访视列和受限采用链上。我先在允许路径里定位阶段阻断、列证据传递和修正合同的定义。两个阻断都落在阶段字段和访视列传递上。我按完整函数读源解释、列范围和下游采用检查，不跑测试。# Conference Output: rv1006-source-stage-boundary-review-20261008 - evidence_single_object

## Output

两个阻断不能共用一个修复。异时 OR 已经能通过校验，却因「没有共同阶段」把疑问写进 `statement.unresolved`，现有校正既不会被调用，也不能清掉这条疑问。第 2 列访视证据已经在 `schedule_column_scope` 里，校验器只允许把它放进全体标记列都包含的 `scope_quote`；校正提示却禁止这条已经合法的载体。建议分开修，不改静态深析提示、不抬 `compiler_versions`，也不放宽已有覆盖门。本输出是顾问意见，不构成临床、监管、视觉或现行网页的最终接受。

### 证据

源语句合同只有一个 `affected_stage: str | None`、一个 `time_words` 列表，以及自由文本 `unresolved`。`validate_source_interpretation` 并不因为 `affected_stage is None` 且有多段已落地的 `time_words` 而拒绝语句。因此「五条语句有效、同时保留时间疑问」可以同时成立。

`validate_source_target_review` 在 `statement.unresolved` 非空时拒绝 `covered_by_official`、`covered_by_procedure`（`SOURCE_UNRESOLVED_STILL_COVERED`），并拒绝 `not_current_control`、`potential_same_requirement`、`cited_external_rationale`（`SOURCE_UNRESOLVED_STILL_EXCLUDED`）。`additional_requirement` 仍须带 `unresolved_aspects`，不能当成完整覆盖。

`apply_source_scope_correction` 在 `correction.unresolved` 非空时直接拒绝，且从不写回 `statement.unresolved`。解构器只在 `SOURCE_TIME_UNGROUNDED`、`SOURCE_SCOPE_UNGROUNDED`、`SOURCE_SCOPE_CONTEXT_INVALID`、`SOURCE_STAGE_UNGROUNDED`、`SOURCE_TIME_INCOMPLETE`、`SOURCE_STAGE_TIME_MISSING`、`STUDY_PHASE_NOT_VISIT_TIME`、`STUDY_PHASE_NOT_VISIT_STAGE` 时进入这次校正。已经校验通过、只是带着疑问的语句不会进入校正。

`_temporal_restriction_indexes` 要求错误类仅为 `TEMPORAL_SCOPE_UNRESOLVED`，且语句本身没有 `unresolved`。仅因没有共同阶段而留下的疑问，进不了现有的 `consumer_unavailable` 证明。

`schedule_column_scope` 按标记格返回 `column_index`、`cell_source_ref`、`header_text`、`header_source_refs`、`review_stage`、`boundary_side`、`visit_unresolved`。表头投影只把带阶段组标记、且不是访视/日期行的合并标题横向展开；访视、周、日保持列内，引用指向原格。

`affected_stage` 只允许出现在本条摘录、无标签引用时的 `scope_quote`，或标题路径。`scope_quote` 另有一条访视列表路径：所有标记列都有 `header_source_refs`，且范围文字是每个 `header_text` 的子串。单列 X 可以走通 `scope_quote`；多列标记且表头不一致时，`all(...)` 会拒绝把第 2 列访视写成整行范围。`SOURCE_STAGE_UNGROUNDED` 表示阶段文字不在摘录、`scope_quote` 或标题里，校验器当时没有查阅列范围。

来源提示的材料包只有 `table_context` 和 `possible_cell_scope_labels`，没有 `ScheduleColumnScope`。空的 `possible_cell_scope_labels` 只说明没有紧邻同格、冒号结尾的项目标签。校正提示写明：标签列表为空则 `scope_context_unit_id` 必须为 null；这种标签引用不能补 `time_words` 或 `affected_stage`；共享范围不在本条、标题或表格标题、且无可核标签时，`scope_quote` 填 null。这与校验器已经允许的「全体标记列表头」互相矛盾。

`schedule_column_links` 只在整行都是字面 X、每列边界已定、入组列恰好对上一个流程目标时返回链接。空列表表示这条整行短路不成立，不表示没有列表头。`normalize_mixed_schedule_scopes` 会拆掉不能覆盖每个标记列的共享范围。

`_deep_component_identity` 哈希的是静态深析模板，不是 `build_source_interpretation_prompt` 的逐批文本。`_same_deep_components_with_current_gate` 允许只有 `validator_version` 不同；`compiler_versions` 或 `prompt_template_sha256` 不同则整批 `component_material_changed` / `prompt_material_changed`，完成批次变为 `refresh_required`。失败批次的 `_revalidated_source_seed_proof` 会重放原始回答和已见证的校正，比较规范化后的语句与保存快照；校正失败或快照不一致则证明为 `None`。它不把新的校验放宽伪装成旧提示的结果，但若只改内存中的动态提示、不改被哈希的身份，完成批次的复用键看不出来。

`RestrictedProtocolControlStatement` 投影为额外的「方案补充要求」，状态为受限，不改写官方条款的符合/不符合。官方通道的 `interpretation_unresolved` 才会把该条款投影为 `INDETERMINATE`。`DUPLICATE_STATEMENT` 在发布门要求 `shared_assessment_identity`；矩阵渲染只把它显示成「共享同一评估口径」。本次读到的投影路径没有因此停用官方消费者。

`source_requires_temporal_resolution` 把「期、/和/及/与…期」、时长、频次和持续义务标成需要时间解析。它不表示两段显式时间必须合成一个 `affected_stage`。`source_has_single_visit_anchor` 在 `time_words` 不是恰好一段时已经为假。

本次没有改文件，没有跑测试，没有读临床原件，也没有重放 source 12 / source 17。包内诊断只当作观察：source 12 五条语句有效且带着同一时间疑问；source 17 以 `SOURCE_STAGE_UNGROUNDED` 被拒。二者都未写入数据库，也不证明原文含义已经完整。

读数超过包内「八次实质阅读」。超出的部分是种子证明重放、预检身份、校正触发、受限投影和重复关系合同；这些都在允许源清单里，前八次没有覆盖完整定义。

### 推断

阻断 A 不是校验器缺了一个共同阶段，而是提示把「没有共同阶段」说成了阶段歧义，模型把这句话写进 `unresolved`，随后没有任何合法步骤能清掉它。硬填一个共同 `affected_stage` 会把异时 OR 说成同时约束。拆成两条必做语句、又不保留析取，会把 OR 做成 AND。用中文疑问文本做正则来决定能否恢复，会被包明确禁止，也无法区分「只是没有共同阶段」和同一列表里的真实歧义。

现有范围校正解决不了 A。它不处理已经有效的语句，而且即使校正对象声称已核清，语句上的 `unresolved` 仍原样留下。

阻断 B 的合法证据已经算完。失败点是模型按提示去对列，却把访视写进 `affected_stage`；校正提示又不许把同一表头写入校验器实际接受的 `scope_quote`。空的同格标签列表被容易误当成「没有列头」。列号对齐本身不是时间：`boundary_side == "unresolved"`、`visit_unresolved` 或空的 `header_source_refs` 都不能升级成阶段。

若只把非法 `affected_stage` 清空、却不让后续覆盖读到完整 `header_text`，带阶段的 X 会被洗成无时间语句。这是 B 的最大短路风险。`affected_stage` 也不该承载整段「阶段 / 访视 / 周 / 日」，否则周、日会丢掉。

只加一条受限补充、让官方条款继续单独判符合，不符合「忠实重复限制必须约束官方消费者」。官方摘录若缺一条 OR 分支或缺这列表头，现有 `TARGET_TIME_INCOMPLETE` / `TIME_SCOPE_MISMATCH` 应继续失败关闭；不应用警告代替这个失败。

只改动态来源提示、不改 `compiler_versions`，十五个已完成组的复用键不变，新指令会被当成旧阅读。只抬 `compiler_versions`，则这十五组都会 `refresh_required`。只抬 `validator_version` 可以留住已通过当前校验的成功组，因为复用比较忽略该字段，而保存结果仍会再跑当前校验。这个差别只能用于「对已成功语句为无操作」的恢复，不能用来假装提示没变。

### 建议

最小完整路径分成两处，都不要放宽采用，也不要重读整份方案。

**A. 异时 OR，改预检过滤和仅针对命中批次的来源提示，不改校正器。**

对已保存且已有效的语句，只有同时满足下列结构条件才重新阅读该批：`affected_stage is None`；至少两段 `time_words`，每段都能在本条摘录中逐字落地；摘录里两段时间之间有显式析取（「或」或「或者」的位置，而不是去匹配 `unresolved` 的中文）；`unresolved` 非空。其余已完成批次保持 `reusable`。这需要在 `_same_deep_components_with_current_gate` 之外增加一条显式例外：身份差异仅这一项，且该批没有上述语句，则不刷新。不要把这项差异藏进未升版的动态提示。

重新阅读时只加一句合同：两段都写明的时间用「或/或者」连接、且没有同时约束两段的共同阶段原文时，`affected_stage` 填 null，两段分别进入 `time_words`；不得制造共同阶段，也不得仅因没有共同阶段写入 `unresolved`。任一段的时间、对象、例外或「或」的辖域无法从本句核清时，仍保留具体 `unresolved`。

不要自动清空旧的 `unresolved`。新阅读若仍留下疑问，覆盖继续被 `SOURCE_UNRESOLVED_STILL_COVERED` 挡住。新阅读若疑问为空，沿用现有规则：目标必须逐项覆盖每段 `time_words`，只对齐一段则 `TARGET_TIME_INCOMPLETE`。`source_has_single_visit_anchor` 保持为假。若两段时期触发 `requires_temporal_resolution`，走现有时间受限，不升为完整覆盖。

**B. 第 2 列原生表头，做成与 `normalize_mixed_schedule_scopes` 同类的确定性规范化，不改模型可填字段。**

在抛出 `SOURCE_STAGE_UNGROUNDED` 之前，仅当同时成立才把该阶段文字写入 `scope_quote`，并保留 `affected_stage`：该行恰好一个标记列；`header_source_refs` 非空；`boundary_side` 不是 `unresolved`；`visit_unresolved` 为假；`affected_stage` 等于该列 `header_text` 的一个完整分段或等于整段 `header_text`，不用新的子串放宽。随后仍走现有校验。`SOURCE_STAGE_TIME_MISSING` 的现有豁免（阶段在 `scope_quote` 内且摘录没有未列的时间碎片）因此可以适用，访视名不必再复制进 `time_words`。

多列标记且表头不一致时不要填写，也不要合成共同阶段；继续拒绝，或由校正把阶段和时间留空并写上真实 `unresolved`。不要把空的 `possible_cell_scope_labels` 当成缺表头。不要按列号推断时间。混合行继续由 `normalize_mixed_schedule_scopes` 拆共享范围。

这个规范化对已经合法的语句是无操作，因此不要升 `compiler_versions`。种子证明要使用新的证明版本，记录「系统按已见证表头引用写入 `scope_quote`」，不能复用 `revalidated-source-seed-proof/v3` 的名义。失败批只有在被拒阶段文字满足上面的相等条件时才重放；否则保持拒绝。

覆盖侧必须同时读这个 `scope_quote` 所依据的整段 `header_text`：`covered_by_*` 要用 `source_visit_scope_matches` 对齐目标访视与该表头，而不是对齐列号。官方摘录缺这段表头则失败关闭。不要另加一条不改变官方判定的补充警告。

校正提示若仍会在规范化之后被调用，应单独说明：可核列表头包与同格标签不是同一对象；只有全体标记列共享、且引用非空的表头才能进入 `scope_quote`；同格标签仍不能补阶段或时间。这项文字不要塞进静态深析模板。成功组不调用校正提示。

**不要做的事**

不要为 OR 制造共同 `affected_stage`。不要把 OR 拆成两条没有析取载体的必做语句。不要用中文 `unresolved` 正则决定恢复。不要在 `unresolved` 仍非空时允许完整覆盖或排除。不要把一个列头抄到混合 X 行。不要把列绑定写进 `schedule_columns`，否则会误触发 `_source_interpretation_requires_refresh` 的整行短路比较。不要把新字段放进模型响应模式；本次没有核对 `protocol_control_agent_json_schema`，多一个模型字段有机会改变 `wire_schema_sha256`，从而刷新全部完成批。

**应有的正例与反例（本次按包未运行）**

正例：一句里两段逐字时间加「或」，没有共同阶段。结果是 `affected_stage is None`、两段 `time_words` 都在；只有新阅读才能让 `unresolved` 为空。目标只含一段则 `TARGET_TIME_INCOMPLETE`；两段都在目标原文中才可能覆盖。

正例：第 2 列只有一个 X，表头引用非空，基线侧已定，`visit_unresolved` 为假，被拒的阶段文字等于该列表头分段。规范化写入 `scope_quote` 后通过现有校验；覆盖必须匹配整段表头。空的同格标签仍为 null。

反例：同一行多个标记且表头不同。不得写成一个阶段或一个行级 `scope_quote`。边界未定、访视未定或引用为空时，不得升级为阶段。阶段文字来自另一列时，`SOURCE_STAGE_UNGROUNDED` 保持。语句同时有真实非阶段疑问时，不得清除 `unresolved`。方案期别仍由 `STUDY_PHASE_NOT_VISIT_STAGE` 拒绝。已成功语句在仅 `validator_version` 变化时仍为 `reusable`，规范化不改其字段。官方重复关系即使有共享评估身份，官方摘录缺分支或缺表头时也不能单独判通过。

### 不确定性

十五个已完成组是否都有 v3 `component_identity`，本次没有打开任务检查点。若有的批次没有这份身份，它们已经会以 `legacy_component_identity_unproven` 刷新，与这次修复无关。

source 17 的被拒语句是否同时带有非空 `unresolved`，包内未说明。规范化不清除 `unresolved`。若当时已经写了疑问，校正成功后覆盖仍会被挡住，这是故意的。

`shared_assessment_identity` 是否在投影以外的官方求值器里改变符合/不符合，本次只看到发布门和矩阵文案，没有看到它约束官方判定。

`header_text` 使用 `" / ".join`。现有 `scope_in_visit_headers` 用子串包含，本身偏宽。建议的自动填写用分段相等，不把这个子串测试放宽到 `affected_stage`。

表头纵向填充会把同列上一格非空文字继承到空白格，引用仍指向原格。合成类似物写的是第 2 列明确有阶段/访视/周/日，不是空白继承。自动填写仍应要求引用属于冻结成员路径。

### 异议、决策点与给 Codex 的问题

最高影响异议：若计划是「改全局来源提示，让异时分支不必有共同阶段，并允许把列表头写入 `affected_stage`」，这会把两件不同的事绑在一次会刷新十五组的提示变更上，并可能把列证据洗成无时间语句。现有校正器不能合法完成其中任何一件。

决策点 1。A 是否授权「只重读结构上命中的批次」。建议授权。不授权则这些语句继续被疑问挡住，直到人工点名重读；这是安全的暂定路径，但 source 12 不会在本次最小修复里变成可覆盖。

决策点 2。B 采用「恰好一个标记列时，把已等于表头分段的阶段写入 `scope_quote`」，还是采用旁路列绑定。建议前者，因为校验器已经认 `scope_quote` 这条访视列表路径，成功语句无操作，且不必新增模型字段。多标记列不要走前者。

决策点 3。是否允许失败批用新的种子证明版本重放 source 17。建议只在被拒阶段文字与该唯一标记列表头分段相等时重放。

给 Codex 的问题：十五个完成批是否全部带 v3 组成身份，并且都是深析复用计划里的 `completed` 检查点。这决定「只抬校验版本、不抬编译版本」是否足以留住它们。合成类似物里的 X 行除第 2 列外是否还有别的标记格。若有，单个 `affected_stage` 必须继续非法，不能采用单列填写。
