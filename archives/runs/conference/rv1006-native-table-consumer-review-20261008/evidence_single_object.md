Trellis SessionStart 上下文已加载。开始按受限读取集做只读证据审阅。

Context 已读。现在定位 gate、execution 与测试的精确位置。

定位新增测试与函数边界，然后开始定点读取。

开始定点读取受影响定义。第一批：source_interpretation 的原生表格包/提示构建/校验入口，与 deconstructor 的原子来源校验和 wire 校验。

核心装配点已确认（deconstructor.py:3690-3702 在原子校验后按已声明表格单元补全 span）。继续读 gate 来源闭包、candidate→domain 转换、deep source 复用与两组新测试。

继续：读取组件身份与 gate 负例测试，并用带上下文检索确认复用路径与排序不变量。

最后一批：复用预检路径 + gate 调用点 + 候选排序不变量 + 规范化层。

最后确认：domain 草稿/水合层是否强制 sorted-unique（决定补全后顺序不变量的严重度）。

决定性问题确认：domain 草稿是否对 `source_span_ids` 也强制 sorted。

# Conference Output: rv1006-native-table-consumer-review-20261008 - evidence_single_object

## Output

**定位与方法（标注）**：本输出是一次只读工程审阅，不是临床采用、不是最终验收、不是发布结论。仅使用受限读取集内的 7 个文件，约 13 次定点读取/带上下文检索；未编辑、未运行测试、未访问网络/环境/DB/私有目录。以下"证据"= 我在当前 dirty 树实际读到的代码/测试文本；"推断"= 由调用链得出的结论；"未验证"= 未能在本窗口证明。

---

### A. 结论先行

**建议：revise（方向可采纳，但补全装配有一处决定性缺陷必须先修，另有 1 个历史复用过渡疑点需 Codex 裁定）。**

- 补丁方向（表格行宿主侧闭包补全 + target reviewer 收到冻结原生位置包）本身没有越过原子出处/语义边界；原子、逻辑、时间、临床字段在宿主补全路径中保持不变。
- 但宿主补全写回 `source_span_ids` 时**未保持全管道要求的 sorted-unique 不变量**，会在"候选只引用行内非首单元格"这一 Step21 同型场景中，把本该修好的 wire 变成 `DOMAIN_DRAFT_INVALID` 硬失败。属决定性 must-fix，修复成本一行。
- 组件身份确实记录了本次两处变更（compiler_versions 两条），历史成功不会"假复用"，但旧身份检查点会 fail-closed，而非按宿主补全前向兼容重验——需要 Codex 对冻结运行 e628d4f0 的恢复语义做一次裁定（residual）。

---

### B. 六问裁定（证据 → 推断）

**Q1. 外部/上下文 span、错误原子摘录、未知单元、兄弟语义、缺失时间能否被补全"合法化"？**

不能（缺失时间见末尾未验证项）。各条阻断点与证据：

1. 外部/上下文 span：补全只从 `candidate.source_structure_unit_ids`（必须先 ⊆ owned，`protocol_control_deconstructor.py:3664-3670`）取单元，且只取 `unit_kind ∈ {table_header, table_row, table_note}` 单元的 `source_span_ids`（`:3692-3697`）。`batch.context_units` 不参与。候选自带 span 须先通过 `:3671`（⊆ owned spans）与 `:3683`（⊆ 声明单元闭包）。新负例 `tests/.../test_slice58c_control_deconstructor.py:12681-12691`（`context_span`/`unknown_unit`）。
2. 错误原子摘录：补全发生在 `_validate_exact_atom_sources`（`:3256-3321`，FABRICATED_EXCERPT / SOURCE_SCOPE_ESCAPE）**之后**，且只 `model_copy(update=...)` 顶层 span。正例断言原子 JSON 逐字不变、raw wire 冻结、二次校验幂等（`:12664-12677`）；负例 `atom_quote`。
3. 兄弟语义：补全不触碰 `applicability/trigger/obligation/exception`、`time_constraint`、`evaluation`、`minimum_evidence`；`_candidate_to_domain`（`:3844-3898`）逐字段搬运，语义层无宿主写入。
4. 作用域：gate 保持严格——`_source_scope`（`protocol_control_gate.py:1920-1955`）仍执行 allowed-span、声明单元闭合与 `TABLE_ROW_SOURCE_CLOSURE_PARTIAL`；gate 负例 `test_slice58c_protocol_control_gate.py:4756-4793` 仍要求 partial closure 被拒。补丁没有改 gate。

**Q2. 补进来的 provenance 会不会被当成"原子临床支持"？**

不会，但要说清它的确切效力（推断，证据链完整）：

- 原子支持仍由原子自带 `source_span_ids/source_excerpts` 承担；补全只加宽"控制级来源闭包"。gate `_check_atom_sources`（`protocol_control_gate.py:1985-2024`）是**上界关系**（原子 span ⊆ 控制闭包；摘录须在声明单元 `excerpt` 中逐字存在），闭包变宽只会让"原子引用行成员 span"不再被闭包卡住；不会产生无原文的引用。
- 语义草稿层要求"source_span_ids 必须覆盖所有原子直接来源"（`protocol_controls.py:1457`），补全是加宽，方向正确。
- 边界提示（未验证、临床侧）：行单元 `excerpt` 是成员文本展平（含 "X" 这类标记格），逐字校验允许极短标记摘录通过；这是既有语义，不是本补丁引入，但会随"整行闭合 + 原生列位置"更常见，Codex 若在意应另立最小摘录质量约束，不建议在本窗口扩框架。

**Q3. 复用是否"诚实记录、就地重验"，而非重放历史或一刀切重跑？**

大部分是（证据 → 推断）：

- 身份记录：`_deep_component_identity`（`protocol_control_execution.py:1989-2064`）`schema_version: .../v3`，`compiler_versions` 含 `"native-row-candidate-provenance-closure/v1"`（`:2037`）与 `"source-target-native-table-packet/v1"`（`:2038`），`validator_version` 组合四版本（`:2057-2060`）。两处变更确实被记录。
- 接受路径 `_validated_deep_source`（`:3408-3485`）先比对 payload/计划/提示/组件/transport 身份（`:3443-3455`），不一致即 `StepFailure(retryable=False, PROTOCOL_CONTROL_DEEP_SOURCE_INVALID)`；一致时**仍重验**保存结果（`_validate_saved_source_review`、`_validate_deep_batch_output`，`:3473-3478`），并按 `_source_interpretation_requires_refresh` 只刷新受影响批次（`:3466,3471`）。
- `_same_deep_components_with_current_gate`（`:2067-2079`）只容忍 `validator_version` 漂移；compiler_versions 变化不容忍。因此旧 success 不会被"假复用"，也不会无条件重跑模型——但会 fail-closed（见 D 残留项）。

**Q4. 新测试 + 既有 gate 负例是否构成有界代码证据？**

基本够用，但有一个盲区（证据）：

- 正例/幂等/域传播：`:12664-12677`（补全发生、原子不变、`span:03` 不得进入、raw wire 不变、二次校验幂等、`wire_to_...` 传播）。
- 负例：`:12680-12691`（context_span / unknown_unit / atom_quote 均拒绝）。
- 提示与冻结：`:12694-12725`（member_texts、member_cell_paths、context 单元位置保留、`unresolved` 保留、"位置关系本身不证明已有目标覆盖"存在、输入 JSON 冻结）。
- gate 负例：`test_table_row_partial_source_closure_is_rejected`、`test_mixed_table_row_cannot_be_flattened_without_member_contract` 仍在且未放宽。
- **盲区（推断）**：正例的 span 排序恰好有利（`span:01` < `span:row-mark`），没有覆盖"补全后顺序"这条不变量轴，所以测试全绿也不能证明字段路径安全（见 C）。同时没有针对"reviewer 用列位置做出覆盖判断"的回复级测试。
- 我未能执行测试（边界禁止），以上为静态证据。

**Q5–Q6. 决定性 must-fix 与一个 residual：见 C、D。**

---

### C. Must-fix（决定性）

**宿主补全破坏 `source_span_ids` 的 sorted-unique 不变量，产生确定性 `DOMAIN_DRAFT_INVALID` 误杀。**

完整证据链（全部为实际读取）：

1. wire 候选在解析时被自动规范化排序：`ProtocolControlAgentWireCandidate.canonicalize_source_id_sets`（`protocol_control_deconstructor.py:877-887`，`sources = sorted(set(ids))`）；`_validate_exact_atom_sources` 在 `:3274-3276` 再 `model_validate(model_dump())`，仍有序。
2. 补全在之后执行，且用保序去重：`:3692-3702`
   ```python
   row_spans = [span for unit_id in candidate.source_structure_unit_ids
                if units_by_id[unit_id].unit_kind in {"table_header","table_row","table_note"}
                for span in units_by_id[unit_id].source_span_ids]
   if row_spans:
       candidate = candidate.model_copy(update={"source_span_ids": list(dict.fromkeys([*candidate.source_span_ids, *row_spans]))})
   ```
   `model_copy(update=...)` 在 pydantic v2 不触发校验/规范化（推断，标准语义；且该规范化是 `mode="before"`，只在 dict 解析时运行）。
3. 复现形状：行单元 spans = `[s01, s02, s03]`（成员序=排序序），候选只引用 `s02`（**正是 Step21"两个候选各引用同一行不同单元格"之一**）→ 补全得 `[s02, s01, s03]`，非排序。
4. `wire_to_protocol_control_batch_disposition`（`:3901-3957`）立即 `_candidate_to_domain`（`:3886` `source_span_ids=list(candidate.source_span_ids)`）。
5. 语义草稿模型强制排序：`protocol_controls.py:1413-1420`（`_require_sorted_unique(self.source_span_ids, "语义草稿 source_span_ids")`，`:1420`）→ 抛 `ValueError`。
6. 被 `:3953-3957` 捕获并转为 `ProtocolControlAgentWireValidationError("DOMAIN_DRAFT_INVALID")` → 提供方"输出非法"→ 修复轮，甚至可能耗尽预算。

**替代解释与排除**：唯一能救回的口子是"补全后、草稿构造前还有一次重排序/重解析"。已排查：`validate_protocol_control_agent_wire` 在补全后不再重解析候选，`wire.candidate_drafts[i] = candidate` 赋值不会重跑 `mode="before"` 规范化（即便 `validate_assignment` 开启，传入对象也不会走 dict 分支），`_candidate_to_domain` 直接搬运。该替代解释不成立。

**建议修复（最小）**：把 `list(dict.fromkeys([...]))` 改为 `sorted({*candidate.source_span_ids, *row_spans})`（对现有正例结果不变，幂等，保持草稿/flush 契约）。或在补全后以 `canonicalize_source_id_sets` 同等语义规范化一次。修复后应在负例参数中加一个"`cited_cell_not_first`"用例锁定该轴。

---

### D. Residual（一个）：旧身份检查点的过渡语义

`_same_deep_components_with_current_gate` 只容忍 `validator_version` 漂移（`protocol_control_execution.py:2067-2079`）；两条新 marks 属 compiler_versions，**不容忍**。因此 pre-patch 已保存的 deep 结果（冻结运行 e628d4f0 的 19 deep complete）在新身份下要么被 `_preflight_deep_source`（`:2877+`，逐批 refresh 决策，我只验到 `:2967`）标为 refresh，要么在 `_validated_deep_source` fail-closed（`:3443-3455 → :3480-3485`）。这与补丁"记录新要求、不复用旧成功"的诚实性一致，但存在一个更省成本的替代路径：**补全是宿主侧变换，saved raw provider reply 本可用新 deconstructor 就地重验并前向补全**，从而避免对已读批次重跑模型（Step17/21 的 17 source-target-unresolved 最需要的是新 reviewer 提示，而不是全体重读）。

- 未验证：`_preflight_deep_source` 在 `:2967` 之后的逐批分支是否已有"仅验证器/宿主补全变化 → 就地重验"通路；若没有，身份 bump 的实际后果是旧批次全部 refresh 或 job fail-closed。
- 这是一个窗口级取舍（恢复成本 vs 诚实性），应由 Codex 裁定，不必新框架。

---

### E. 未验证关注（明确标注，非 must-fix）

1. **位置推断的语义边界（临床侧，Codex 保留）**：新提示明确允许"标记单元格与表头列位置"用于核查"本行动作适用的访视"（`protocol_control_source_interpretation.py:1461-1466`），而机器校验仍只有"两端摘录归一化相等"（`:1505-1510` 段及后续时间校验）。逐字相等不能证明列位置推出的访视关系在医学上成立。提示已加防线（"位置关系本身不证明已有目标覆盖""表头未写出的时长、锚点、例外继续保留具体未决"），但我没有找到针对"位置驱动误覆盖"的回复级负例。建议 Codex 用一次真实 failed reply 回放核对，或明确接受该风险。
2. **补全后的重复语义**：`fingerprints` 在补全之后计算（`:3702-3711`），两个仅顶层 span 枚举不同、其余全同的候选现在会撞 `DUPLICATE_CANDIDATE`。语义上大概率正确（同规则重复），但它是补丁引入的行为变化，会转化为修复轮；如需保守可对"补全前内容"取指纹。
3. **e628d4f0 冻结元数据与补丁状态的关系**：Step21 的 `TABLE_ROW_SOURCE_CLOSURE_PARTIAL` 若发生在**已含本补全**的运行中，则说明有一条到达 gate 的路径绕过了 `validate_protocol_control_agent_wire`（例如 insert/restricted/repair 构造）。我无法从元数据判定当时补丁状态——这是与 must-fix 并列的最高价值时间线问题（见下 Q1）。

---

### F. 对 Codex 的有界问题与决策点

1. e628d4f0 的 Step21 是在含 `native-row-candidate-provenance-closure/v1` 的树上产生的吗？若是，请给一条该候选进入 gate 的具体路径（哪个 step/哪类 insert），我将定位绕过点；若否，C 与 D 即为当前结论。
2. 恢复策略取哪一种：旧身份 deep 完成批次 (a) fail-closed / (b) 逐批 refresh 重读 / (c) 对 saved raw reply 就地重验并宿主补全？这决定 19 个已完成批次与 17 个 unresolved 的实际成本。
3. C 的修复是否授权为一行 bounded repair（`sorted({...})` + 补一个非首单元格负例）？在该修复前，任何"候选只引用行内非首单元格"的诚实输出都会以 `DOMAIN_DRAFT_INVALID` 失败。
4. 是否接受 E1/E2 为已知残余（不扩框架），还是要求一并收紧？

**安全临时路径（在回答前）**：不要把本补丁当"已解决 Step21"使用——C 未修前，与 Step21 同型的输出会以新错误码失败；D 未裁定前，不要基于旧身份检查点推断复用可行。工程方向（宿主行闭包 + 原生位置包）本身可以保留为待修正方案。

**证据边界声明**：以上均为对当前 dirty 树的静态代码追踪，未执行测试；身份/复用结论限于我所读范围（`_preflight_deep_source` 决策分支止于 `:2967`）。不作临床采用、发布或最终交付结论；最终判定与修复授权归 Codex。
