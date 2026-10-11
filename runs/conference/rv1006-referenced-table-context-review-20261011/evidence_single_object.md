我先读会议指定的两份材料，只核对冻结原文里的表号上下文闭合，不改代码、不跑产品。材料只给出冻结基线 `a201d040` 和五处补丁范围。我接着只看这些 diff 和被点名的只读相邻定义，核对表号是否真能落到唯一物理表。补丁把表号助手抽到新模块，并放宽了 `non_control` 只读准入。我接着核对闭合条件、计划重建和提示消费是否真的绑到同一张物理表。# Conference Output: rv1006-referenced-table-context-review-20261011 - evidence_single_object

## Output

本轮是只读证据审阅，不构成 Codex 终审，也不是临床、监管或现网验收。我没有改文件，没有运行产品或测试，没有打开 clinical、tmp、data、env 或其他角色的报告。主会场计划 `plans/codex_main_venue_rv1006-referenced-table-context-review-20261011.md` 仍是 TODO；以下以会议上下文里的冻结基线 `a201d040` 和指定补丁为准。

为判断“物理表”在真实结构里长什么样，在指定五份补丁和两个相邻文件之外，我还读了 `app/protocols/full_protocol_coverage.py` 的表题、表根和 `heading_path` 构造。工作区里还有未列入本包的脏文件 `app/agents/protocol_control_candidate_alignment.py` 及其测试，本轮没有把它们当证据。

### 证据

冻结基线就是当前 `HEAD`：`a201d040f9ad5c7c307458f36fb746fdd786e1d0`。相对它，指定跟踪补丁是 `protocol_controls.py`、`protocol_control_planning.py`、`phase_applicability_planning.py`、`test_protocol_control_generalization.py`；`app/domain/contracts/source_table_references.py` 是未跟踪新文件。

`table_number`、`table_key`、`normalize_reference_number` 和 `_TABLE_ROW_REF` 与从 `phase_applicability_planning.py` 删掉的实现一致。期别规划改为从新模块导入这两个助手。新的引用正则不是原样搬迁：`phase_applicability_planning.py` 第 351–355 行的 `_TABLE_REFERENCE_RE` 仍留在原地，且没有复合编号的负向断言。

生产者在 `plan_protocol_control_deep_batches_from_discovery` 里对完整 `coverage_manifest.units` 调用 `explicit_table_reference_context`，把结果接进原有 `related_context`，再写入批次 `context_units`。它不改发现处置。`_deep_batch_chunks` 会把这些 id 放进上下文，不受前 5 行日程截断的删除。

`explicit_table_reference_context` 只从引用单元的 `excerpt` 取号。物理表只承认 `table_key` 为 `("source", ...)` 且 `heading_path[-1]` 从“表/表格/table + 编号”起头的单元。同一 source key 的编号集合必须恰好是被引用的那一个号，且全清单里只有一个这样的 key，才整表入选。没有 `table_context`、但 `excerpt.strip()` 与入选标题完全相同的单元也会入选。

覆盖构建里，表行的 `heading_path` 来自 `_table_heading_paths`：章节路径末尾可以追加紧邻表根、且通过 `_TABLE_TITLE_RE` 的表题。该表题语法接受 `18-2`、`18.1` 和破折号 `18—2`。聚合行的 `source_ref` 是 `{table_root}.r{row}`，原子单元格是 `{table_root}.r{row}.c{col}.p{n}`；二者会被新的 source key 收成同一个表根。同一测试文件里已有表格夹具的 `heading_path` 是 `["访视安排"]`，`source_ref` 形如 `body.t0.r{index}.c0.p0`。新测试则把行的最后一级标题手工写成“表 18 给药安排”。

校验器 `ProtocolControlDiscoveryToDeepPlan.validate_bridge` 在 `protocol_controls.py` 第 2923–2938 行和 3022–3028 行用批次里已经嵌入的 `owned_units + context_units` 重新调用同一个选择器，用来放行 `non_control`。`stable_protocol_control_manifest_structure_unit_ids_sha256` 只哈希结构单元 ID 列表。

`_execute_closure` 会按当前清单重算深析计划。`_execute_deep` 和 closure/deep 的 `_replay_checkpoint` 只对已保存的 `deep_plan` 做 `model_validate`。`_preflight_deep_source` 会重算，并用 `_same_deep_batch_material` 比较除 `batch_total` 外的整批材料；材料不同时原因是 `planning_material_changed`，处置保持 `refresh_required`。

`batch_id` 由清单、批次号和 owned id 组成，不含 context。`_deep_component_identity` 含清单和发现计划摘要，不含深析 context。同一步诊断恢复在 `protocol_control_execution.py` 第 4562–4582 行按 `batch_id` 和 component identity 接回已保存的 `source_interpretation`。接回成功时，`ProtocolControlAgentRunner.run` 在 `protocol_control_deconstructor.py` 第 7859–7861 行直接使用旧解释；只有解释仍为空时，第 8094–8096 行才调用 `build_source_interpretation_prompt`。

该提示把 context 的 `structure_unit_id`、`source_ref`、`heading_path`、`excerpt`、`table_context` 放进“冻结来源”JSON。新测试只断言 context id 出现在提示字符串里。

新测试还证明：全角 18、英文 see Table 18 会闭合；同号第二张表、无引用、`18-2` 不会闭合；另一 source key 且标题改为表 20 的行不会并入表 18；owned 仍只有引用句；清单对象不被改写；只删 context、不删 `related_context` 会校验失败；把计划内引用句改成表 20 会校验失败。测试没有构造“相关 id 和 context 一起缩短”的自洽子集，也没有把第二张同号表留在清单里但不放进批次。

### 推断

诚实的新闭包会把“清单里已有、标题落在路径末级、编号唯一”的整张 source 表放进只读 context，且不把这些行提升为 owned。前 5 行规则不会再把这张被点名的表裁掉。提示函数本身会带上这些行的正文。新的预检重算也会让旧批次因材料变化而不能标成 reusable。

这条链没有证明已知那次遗漏已经被闭合。选择器认的编号窄于覆盖层已经承认的表题。ASCII 或全角连字符、半角或全角点号组成的“表 18-2 / 表 18.1”在引用侧和标题侧都被拒绝，生产者得到空 context，正文仍不进入批次。覆盖层却会把这种表题追加为 `heading_path[-1]`。破折号“表 18—2”相反：新拒绝类不含 `—`，标题和引用都会被收成裸号 18。清单里若只有这张复合表，裸号 18 和带破折号的引用都会把这张表当成表 18。

`意见表 18` 会被引用正则命中。`见` 没有字边界，`意见` 的“见”加后面的“表 18”满足 `(?:见)\s*(?:表格?|table)`。这是在完整清单上就会发生的错误准入，不需要伪造计划。

无 `table_context` 的单元只要整段 excerpt 与入选标题逐字相同就进入 `non_control` 只读集。表题段因此能进来，任何整段等于表题的其他单元也会进来。行的 `heading_path` 已经带表题，提示不依赖这段无坐标单元。

校验器的证据宇宙就是计划里已经放入的单元。会拆穿同号歧义的另一张 `non_control` 表若没有进入任何批次，就看不见。把 related ids 和 context 同步缩成该表的一部分行，选择器仍会在剩余行上看见唯一的表 18，精确闭合检查也能通过。ID 哈希不覆盖 `source_ref`、标题和正文。因此一份自洽的子集或改写过嵌入标题的计划可以通过 `model_validate`。深度执行和 closure 回放走的正是这条校验，不会回头读清单重算。

同作业诊断恢复也不看 context。闭包重算后即使 context 多了表行，`batch_id` 和 component identity 仍可不变；旧的来源解释会继续用，新正文不会进入新提示。预检那条重算路径覆盖的是新作业对照旧作业，不覆盖这条同一步恢复。

新测试把末级标题预设成表题，所以它演示的是选择器的目标形状，不是覆盖构建给普通表行的唯一形状。`heading_path == ["访视安排"]` 的表行不会被这个选择器认作表 18。

### 建议

最小连贯修复是四件事，仍沿用现有 `related_context`、source key 和整表只读，不新增框架：

1. 让引用token和标题token使用与 `_TABLE_TITLE_RE` 相同的完整编号，包括连字符、点号和破折号后的子号。身份是完整token，不能把 `18-2` 或 `18—2` 收成 `18`。两个 source key 的完整token相同，就整段引用失败关闭。
2. 引用动词使用明确边界，至少让“意见表 N”不能命中。保留测试里的“参见表 18”和 “see Table 18”。
3. 只读准入只保留 source key 下的单元。表题已经在这些行的 `heading_path[-1]` 上，去掉“excerpt 等于标题”这一支。
4. 在 `_execute_deep`、closure/deep replay 和同一步恢复处，用作业里的冻结清单重算 `explicit_table_reference_context`，要求 `non_control` 的 related ids 与重算结果一致；恢复身份加入 context id 及其 excerpt。模型校验器自身没有清单正文，不能单独充当这道证明。`_preflight_deep_source` 已有的重算比较可以继续作为新作业复用门。

测试应补：破折号复合号、`意见表 18`、同步缩短后的自洽子集、第二张同号表只留在清单里、提示中的 excerpt 正文，以及恢复路径在 context 变化后必须重新生成提示。

### 不确定性

我没有读产生“已知表引用、正文未进批次”的那份冻结方案，因此不能判断该表题是裸号、复合号，还是末级标题根本不是表题。在看到引用原句、被引行的 `heading_path[-1]` 和 source key 之前，这个补丁对那次遗漏是未证实的。

也没有运行新测试。上面的闭合和拒绝结论来自代码和测试源文，不是执行结果。

`_execute_deep` 会对进入 context 的表行调用 `_require_schedule_member_sources`。覆盖构建会写 `member_texts`；缺少逐格原文的旧行一旦被这张引用带入，深度步会直接失败。这是附带后果，我没有用真实清单核过这类行是否存在。

### 异议、决定点、待 Codex 回答的问题

最高影响的缺陷有两个。生产者会把破折号复合表题当成裸号，也会漏掉覆盖层已经承认的连字符或点号表题；“意见表 N”会在完整清单上被当成明确引用。校验器则用批次内单元自我证明物理表，自洽子集能够通过现有保存和回放路径。新测试没有覆盖这两处。

请 Codex 定三件事。第一，已知引用若是复合表号，本补丁应继续失败关闭，还是按完整token闭合。第二，无坐标表题段是否必须出现在 context；我的建议是不必，标题留在表行路径上即可。第三，在深度执行和回放改为对照冻结清单重算之前，不应把 `model_validate` 视为这张表已经闭合。

需要的唯一输入是：该冻结引用的原句、被引各行的 `heading_path` 和 `source_ref` 表根，以及清单里是否还有第二个相同展示号。我没有打开临床原文。安全的临时路径是：本补丁先不作为那次遗漏的修复；只做结构对照。只有末级标题和引用都是同一个裸号、source key 唯一、且深度步会重新生成含这些 excerpt 的提示时，才重跑闭包。
