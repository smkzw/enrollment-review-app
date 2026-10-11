我先读会议上下文和主会场计划，只核对冻结目录共用说明与现有参数覆盖路径。上下文已定位到共用说明访视见证和受限消费者两处阻断。接下来只读指定函数与相邻合成测试。# Conference Output: rv1006-common-parameter-scope-20261007 - evidence_single_object

## Output

结论先行：现有 `schedule_column_links` 不能当作共用参数的访视见证。它是整行无条件 `X` 的流程关闭捷径，而且入组列一带 `^n` 就整段放弃。扁平化后的 `KnownRequiredProcedureTarget.source_excerpts` 也只保留共用脚注的表来源，不能证明该句属于哪一次访视。能复用的现成生产者只有 `schedule_column_scope`，而且只能补 `TARGET_VISIT_SCOPE_UNPROVEN` 里“来源自己没有访视词”这一支。剂量、频次、日内时间仍受时间门和受限消费者拦住。最小修复是审查分支内的一个合取，不改保存结构，不放宽 `schedule_column_links`，不拿掉 `calculation_input` 拒绝。

### Evidence

只读了任务点名的定义和相邻命中，共 16 次读/搜。未读真实临床资料、库、env、tmp、旧模型输出，未跑测试，未改文件。

冻结目标没有行列。`KnownRequiredProcedureTarget`（`app/domain/contracts/protocol_controls.py` 2420–2450）只有目录身份、标签、`visit_instance`、`review_stage`、`source_span_ids`、`source_excerpts`。`_catalog_targets`（`app/protocols/protocol_control_planning.py` 360–390）按 span 排序后原样拷贝摘录，不写 `covered_action_kinds`，也不写脚注号或列号。`ProtocolStructureUnit`（同文件 425–446）另有 `member_texts`、`member_source_refs`、`member_source_span_ids`、`table_context`。

原生网格还在结构单元上。`_schedule_cells_from_units`（`app/protocols/procedure_catalog.py` 680–742）只用这些成员重建单元格；`member_texts` 缺失或与路径对不齐时抛 `ProcedureCatalogError`，不返回空。`schedule_column_scope`（768–822）对当前行的 `X` 给出列、表头、`header_source_refs`、`review_stage`、`boundary_side`、`visit_unresolved`、`marker_footnotes`（`\^\d+`）。它不把列绑定到目录项。

`schedule_column_links`（`app/agents/protocol_control_source_interpretation.py` 516–623）更窄，且失败即整表 `[]`：

- 引用必须等于整行 `excerpt`（525–526）。脚注句进不来。
- 任一列 `boundary_side == unresolved` 则放弃（531–532）。
- 入组列出现括号内标记则放弃（555–563）。
- 行形必须是“标签 + 纯 `X`/`×`，可带 `^n`”（564–567）。
- 入组列只要有 `marker_footnotes` 就 `return []`（597–598）。
- 成功时才写 `procedure_target_id`：`visit_instance == header_text`、阶段相同、标签 span 的原文被该目标摘录包含，且只能命中一个目标（599–613）。

共用原文的拒绝已经写在审查里。`validate_source_target_review`（1673–1708）：`covered_by_procedure` 且来源时间落在某个 span 上，该 span 又出现在另一个 `visit_instance` 不同的流程目标上，就记入 `shared_time_spans`。没有“含同一时间、且 span 不在共用集合里”的 `specific_quote` 时，若来源含“其余/其他/剩余/后续访视”或“除…外”，或 `_visit_scope_keys(source_time)` 为空，或不被目标访视包含，则 `TARGET_VISIT_SCOPE_UNPROVEN`，文案是“多个访视共用原文，所选流程目标缺少本条时期的独立访视依据”。其前还有 `FREQUENCY_ONLY_COVERAGE`（1661–1670）：时间词全部是“每（日|天|周|月）N次”且 `scope_quote` 不在目标摘录或 `visit_instance` 中即拒绝。

目录组装只定位到，未读函数体。`procedure_catalog.py` 12、1055、1317、1329、1379–1443、1523、1652、1746：正式来源把重复 `X` 当可选锚；表头和操作标签会去掉展示脚注；实例摘录来自 `blocks_by_ref` 与 `optional_source_excerpts_for_spans`。这与“正式材料省略重复标记格、结构单元成员保留它们”的方向一致，但不能代替函数体。

受限消费者的整批拒绝在 `restricted_batch_from_review`（`app/services/protocol_control_restricted_source.py` 303–350）。有 `partial_wire` 时，只要 `source_definition_consumers is not None`，或任一条陈述的 `decision_functions` 含 `calculation_input`，或决定类型超出“已覆盖 / unresolved / 时间类 additional_requirement”，函数在逐条证明之前 `return None`。同文件 105–106 有同一谓词，所在函数体未读。同文件 250–300 的共存证明只比较同一 `unit.excerpt` 内逐字区间是否相交。

`source_requires_temporal_resolution`（1927–1939）把日内片段、时长、全程/持续、以及“每日 N 次”算作时间范围，而不是访视名。`target_action_established`（1913–1924）在 `covered_action_kinds` 为空时，只接受引文被目标摘录包含。

`schedule_column_links` 的执行层调用点在 `app/services/protocol_control_execution.py` 2680，调用体未读。`_visit_scope_keys`、`_flow_footnote_refs`（367 起）、`_build_instances_for_table` 的脚注挂接（1379 起）均未读。

### Inference

这次阻断分两层，不能合成一次“放行”。

表来源不等于语义覆盖。两个流程目标共用同一脚注 span，只说明目录组装时把同一段正式摘录挂到了两个 `visit_instance`。审查器看不见 `X^n` 落在哪一列，所以在来源句自己没有访视词时拒绝。这个拒绝是对的。`visit_instance` 只是目标身份，不能倒推这句参数属于该次访视。

`schedule_column_scope` 有能力恢复列、表头、边界和 `^n`，因为成员原文还在。这只是附着来源，不是临床等价，也不是剂量/频次/日内时间已经可执行。

`schedule_column_links` 不是更小的现成通路。它的成功结果是“这一整行的入组列都由既有流程目标关闭”。共用参数脚注正好踩中它的失败条件。放宽 597–598 行会把“列上有脚注”变成“整行操作已被覆盖”。

脚注号到脚注句的连接在扁平化之后没有字段可放。标记格上有 `^n`，但代码注释写明编号不一定在抽出的注释正文里重复。审查时若注释单元本身没有这个编号，就不能从网格安全接回参数句。此时应继续拒绝，而不是按列表顺序猜。

`calculation_input` / `source_definition_consumers` 是另一条依赖边界，而且是有 `partial_wire`、审查已能通过时，受限消费者的首个整批 `return None`。共存证明只保证同一摘录里两段逐字范围不相交，不保证被留下的候选不再使用这条计算输入。定义消费者还允许定义在方法章、消费者在访视章。只要存在这种绑定，或任一条被标成计算输入，整批都不能局部放行。剂量、频次、日内参数正是这类输入。只补访视见证，不能让这条受限通路发布。

若参数时间词全是频次，`FREQUENCY_ONLY_COVERAGE` 会先于共用 span 分支拒绝。若含日内时间，访视合取通过后仍可能进入既有时间范围门。这些都不应在同一次修复里跳过。

### Recommendation

最小下一刀只改 `validate_source_target_review` 的共用 span 分支，生产者仍用已有的 `schedule_column_scope`，不新增模型，不写入 `KnownRequiredProcedureTarget`，不写入 `SourceStatementCoverage.schedule_columns`，不改 `schedule_column_links`，不改 `restricted_batch_from_review`。

仅当下面全部成立时，才把“来源没有访视词”这一支视为已有列附着，其他拒绝条件保持：

1. 决定是 `covered_by_procedure`，`specific_quote` 为假，失败原因只是来源访视键为空。相对访视、排除式措辞、来源访视键非空但不被目标包含，仍拒绝。
2. 共用 span 来自本批已有的脚注/注释单元，不是另一行操作正文。
3. 操作行已经在本批 `owned_units` 或 `context_units` 中，且 `member_texts` 能重建。缺行、缺成员、或重建抛错时，维持今天的 `TARGET_VISIT_SCOPE_UNPROVEN`，不扩大 `context_radius`，不重读方案。
4. 注释单元自身仍带有与标记格相同的 `^n`。编号不在冻结单元上则拒绝。
5. 该 `^n` 的每一个基线及以前、非括号标记列，都能一对一对应到共享该 span 的冻结流程目标：表头等于 `visit_instance`，阶段相等，边界不是 `unresolved`，操作标签被该目标自己的摘录包含，且只命中一个目标。当前被审目标必须在这个集合里。
6. 同一 `^n` 若还落在基线后列、未解析列、括号标记，或其他操作行，整条不证明。
7. 动作、例外、时间词一致、`FREQUENCY_ONLY_COVERAGE`、时间范围和定义消费者门保持原样。这里不把参数句升级成流程动作等价，也不把候选标成可执行。

合成正例：一行“甲测量”，表头只有“筛选期”“基线”，两格都是不加括号的 `X^1`，两个冻结目标的访视名和阶段与这两列相同，标签在各自摘录中，脚注单元正文含 `^1` 和参数句，没有第三处 `^1`。来源时间等于该脚注句，且没有访视词。此时只允许通过访视合取。

放宽范围守卫时必须仍能打死的反例：同一 `^1` 同时标在“甲检查/筛选期”和“乙给药/第1天、第15天”。参数句是“每次2片，每日2次，用药后1小时”，不含访视词。若改成“只要 span 被共用且目标有 `visit_instance` 就通过”，甲检查会被这条给药参数覆盖。列集合不相等时必须继续 `TARGET_VISIT_SCOPE_UNPROVEN`。另一反例：把 `schedule_column_links` 的 `^n` 直接删掉后，整行“甲检查 | (X)^1 | X”会被现成关闭路径当成无条件入组流程。括号检查和脚注检查都要留下。

### Uncertainty

`_flow_footnote_refs` 与实例挂接函数体未读，不能断定编号丢失后能否只靠本批结构单元重算。在读完之前，编号不在注释单元上就拒绝。

`protocol_control_restricted_source.py` 105 行所在函数未读。若它先于 `restricted_batch_from_review` 执行，它才是入口处的第一道同一拒绝；343 行则是该函数内部、逐条证明之前的第一道。

执行层 2680 行如何消费 `schedule_columns` 未读。因此更不能把脚注列写进 `ScheduleColumnLink.procedure_target_id`。

`_visit_scope_keys` 未读。空访视键这一支是按调用点推断的，具体分词以该函数为准。

未跑合成测试。以上正反例是审查用例，不是已执行结果。

### Objections

最高影响的反对是：用原生日程见证去“支持参数覆盖”，会把列附着说成流程覆盖，并绕开计算输入边界。`schedule_column_links` 证明的是整行操作关闭；共用脚注证明不了剂量、频次或日内时间可执行。扁平摘录里的共用 span 也不能区分“故意挂到多次访视”和“span 被误复用”。

第二处反对是修复面。若顺手让受限消费者在出现 `calculation_input` 或 `source_definition_consumers` 时仍返回局部批次，文本不相交的证明盖不住跨章计算依赖。这条拒绝应保留。

第三处是失败方式。审查期直接调用 `schedule_column_scope` 时，成员原文缺失会抛错。必须落回现有拒绝码，不能把今天的可控拒绝变成目录异常，也不能为此扩大批次上下文。

### Decision points

1. 期望结局是“参数句对这两个流程目标只补上访视附着，其余门仍可拒绝”，还是“限制该脚注并发布同批其他独立陈述”？本角色只建议前者。后者会被 `calculation_input` 整批挡住，而且不应拆掉这道门。
2. 注释正文没有 `^n` 时，是在读完 `_flow_footnote_refs` 后确认它只吃本批结构单元再重算，还是继续拒绝？当前安全路径是继续拒绝。
3. 日内时间下一道若是 `TEMPORAL_SCOPE_UNRESOLVED`，不要并进这次访视修复。

### Bounded questions

请 Codex 确认：这次要消掉的是 `TARGET_VISIT_SCOPE_UNPROVEN` 的空访视键一支，还是要让受限消费者在剂量/频次句上发布同批其余陈述？两件事的首阻断不同。在确认前，不放宽 `schedule_column_links`，不删除 343 行的 `calculation_input` / `source_definition_consumers` 拒绝，不把缺编号的脚注当成已附着。

续读点，若需要同一会话补证：`procedure_catalog.py` 367–400 与 1310–1450，`protocol_control_restricted_source.py` 70–160，`protocol_control_execution.py` 2620–2760，以及 `_visit_scope_keys` 定义。本角色不声称最终验收。
