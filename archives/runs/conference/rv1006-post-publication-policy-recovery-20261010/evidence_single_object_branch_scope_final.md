Trellis SessionStart 上下文已加载。开始有界差异只读复核（上限 9 次定向读取；不跑测试/模型/服务、不修改、不新建任务）。先定位新函数、激活算法与集中核验测试。

定位完成（新函数 371、conditioned 186、identity 513、validate 815-824/915；激活算法 80-204；测试 230/272/437 与 gate 4528）。并行读取五区。

最后一读：确认新测试正例真正走豁免路径（夹具）。

Trellis SessionStart 上下文已加载。有界差异只读复核完成（9/9 次读取用尽；未运行测试/模型/服务、未修改、未新建任务；git diff 仍不可用——Bash 上轮已被非交互权限拒绝，本轮未重试，差异结论以实际定义+测试为据）。以下为完整报告。

## 一、复核范围（9/9）

- `app/agents/protocol_control_candidate_alignment.py`：186-210（**更新后的 `_conditioned_obligations_cover_source`**）、352-368（`_statement_grounded_atoms`）、**371-414（`_independent_source_obligation_groups` 全）**、513-551（**`_alignment_input_identity`**）、554-571（`bind_candidate_alignment`）、780-937（validate：**relevant_groups 812-837**、numeric/时间/语气/例外 838-937、**numeric 循环 910-937**）。
- `app/domain/control_layer_evaluation.py`：75-210（**`compose_control_layers`：triggers/remaining/例外路由 112-171、逐组激活 172-175**）。
- 测试：`tests/v2/agents/test_protocol_control_candidate_alignment.py` 150-178（`_conditioned_action_material` 尾部）、**194-225（`_scoped_sibling_material` 夹具）**、228-292（`scoped_source_sibling` 八变体、`distributed_source_condition` 七变体）；`tests/v2/protocols/test_slice58c_protocol_control_gate.py` 4527-4550（**真实消费者逐组激活**）。
- 未读/未验：git diff；`SOURCE_CONDITIONAL_GROUP_ALIGNMENT_VERSION` 常量值；`ControlObligationGroup` 合同本轮未重读（上轮已读 1139-1175）；测试未运行（124pass/1738deselected/2.44s 为用户报告）；未读临床/私库/环境。

## 二、新差异的语义与逐挑战结论

**`_independent_source_obligation_groups`（371-414）判定链（已证明）：** ①候选须有 trigger 且无 exception 层（378-379）；②本条原子至少落入一个组，且**所有组都必须显式绑定已存在的 trigger 索引**，任一默认/无绑定→整体返回 `[]`（382-385）；③他源=同单元、非本条、非 `unresolved` 的陈述（386-388）；④被豁免组的**每个原子**必须被他源接地且不属于本条（401）；⑤被豁免组绑定集不得与任一选中组相同（402-403）；⑥对**被豁免组的每一条路径**，须存在选中组的某条路径，其原子集合被"该路径原子 ∪ 本条逐字逗号前缀生成的 source_conditions"完全包含（408-412）——source_conditions 仅取自**本条已选、本条第接地、且 statement 恰等于前缀 `source_parts[0]` 的触发原子**（392-396）。
- **无条件替代（已证明拒绝）**：任一组无绑定即 `[]`，回退原全组守卫（validate 818-822）；测试 `unscoped_group`、`empty_branch_mapping` 均期望 ValueError。
- **伪造前提（已证明拒绝）**：前缀只认第一个逗号前的逐字片段，且必须是已存在、已选、本条接地的触发原子；包含关系只是既有原子对象集合运算，不引入新词。`wrong_trigger`（改本条前提原子）、`wrong_prefix`、`unknown_atom`（组内加未接地原子）全部拒绝。
- **共享整段引句（代码推导，未直接以测试钉住）**：原子引句包含整条原文时被 `_statement_grounded_atoms` 归入 `current_atoms`（366-367），④的 `atom not in current_atoms` 不满足→不豁免→走严格守卫。建议补一条直接负例。
- **坏兄弟（已证明拒绝＋一处残余）**：`missing_sibling_source`、`unresolved_sibling`→他源为空；`unknown_atom`→接地不全。**残余 R1（未验）**：豁免只要求他源陈述"存在且无未决"，不要求它在**本轮 alignment pair 集**内被逐项核对；若某同单元无未决陈述不在本轮 pairs（如未被 candidate_linked），本条豁免可借其接地而该兄弟要求的本轮核对缺失。最小探针：令兄弟存在但不在 `expected_pairs`，看本条是否仍通过；若通过，建议在豁免条件加"他源须在本轮被核对/已绑定"（或由现有 pair 生成机制保证——须读 `evidence_policy_alignment_pairs` 与 runner 的 pairs 来源后再定级，本轮未读）。
- **损坏保存 proof（机制已证明，旧证明失效为推导）**：`_alignment_input_identity` 对"有 trigger 且义务组>1"的候选把**同单元全部陈述**与 `SOURCE_CONDITIONAL_GROUP_ALIGNMENT_VERSION` 折入 source 摘要（527-532），候选摘要为全候选（550）；`bind_candidate_alignment` 先校验模型返回一致且无 proofs 再签（556-560）；复用端逐项重验输入身份、response sha、响应重解析与唯一配对（上轮已读 581-622）。测试 253-259 绑定后修改兄弟陈述→`reusable_proven_alignment_items` 返回 `[]`。旧证明的 source_sha256 未含新键→不可能等于新摘要（推导，未读旧哈希样本）。
- **来源相同替代路仍按原合取检查（已证明）**：绑定集相同→不豁免（402-403）；同源但由本条接地的组天然属于 `selected_groups`，不走豁免；`_split_obligations_cover_source` 与按组合取检查对 relevant_groups 原样保留（824-837）。`distributed_source_condition` 的 `missing_condition/wrong_prefix/wrong_position/weaker_obligation/partial_branch_mapping/empty_branch_mapping` 全部拒绝。

**更新后的 `_conditioned_obligations_cover_source`（186-210，已证明）**：由旧的"组必须绑定全部触发分支"改为——所有绑定分支必须携带本条已选前缀条件原子（202-203）；**所有携带该前缀的分支必须蕴含某个绑定分支**（205-209）；前缀只认逐字片段偏移前的文本（192-197），无连接词改写；随后 `_split_obligations_cover_source(source[offset:], …)` 原样（210）。与描述"所有绑定分支须带本条已选原文条件；每个带条件分支必须蕴含一个绑定分支；部分分支映射不能丢失条件"一致；`partial_branch_mapping` 测试即钉此保护。

**实际消费者（已证明）**：`compose_control_layers` 按**逐组激活**计算——组的路由由 `applies_to_trigger_branch_ids` 选定的（remaining）触发分支 OR 得到，替代义务经例外路由（142-175），不存在"义务组自由 OR"；gate 测试 4527-4550 以 `second_truth∈{F,T,U}` 证明两组激活与义务真值互相独立。豁免证明的"路径蕴含"与消费者"路径激活"语义同构，非按名字推定。

**未变化门（结构核对，未 diff/未运行）**：numeric 循环（910-937，含 `comparison_source_preserved`、方向/数值/单位复核）、数量范围（895-909）、时间/例外保留（870-894）、禁止强制（845-850）均保持；豁免只把被豁免组从守卫与 numeric-consequence 循环中移除，后者缺失只会使 `comparison_source_preserved` 更难满足（fail-closed），不会放行允许/无需或未支持次数。

## 三、确定必修与反例

**确定必修：无。** 在读取范围内，六个挑战方向均有代码路径+对应变体测试（无条件替代、伪造前提、坏兄弟、证明失效、逐组激活、原合取保护），未发现可通过的绕过。

**最小反例（残余，按严重度）：**
- R1（中，未验）：位置 `_independent_source_obligation_groups` 386-389 + pair 生成侧。反例：同单元两个非未决陈述，兄弟陈述本轮未被要求逐项核对（不在 pairs）；条 A 的豁免借其接地通过 → 该兄弟要求本轮无人核对。最小验证：兄弟不在 `expected_pairs` 时跑 `validate_candidate_alignment`。若确可通过，最小修法是把"本轮被核对的 statement 集合"作为豁免前提传入（或由 pairs 机制保证并加断言），不新增框架。
- R2（低，建议）：共享整段引句变体没有专测；补一条"兄弟组原子引用整句→不得豁免"的负例即可（代码推导应拒）。
- R3（低，建议）：把"前缀条件假设"（在逐字前缀成立时证明路径蕴含）写入 `_independent_source_obligation_groups` 文档串，避免后续维护者误把该假设当无条件蕴含。

## 四、反证与局限

- 可能推翻 R1 的未读证据：runner 的 pairs 生成（是否恒含全部同单元 candidate_linked 陈述）；本轮未读。
- 旧证明必然失效为**推导**（未取样旧 proof 的 sha 输入）；`SOURCE_CONDITIONAL_GROUP_ALIGNMENT_VERSION` 常量值未读。
- `ControlObligationGroup` 合同以合同字段+消费者算法双重核对（1139-1175 上轮 + 本轮 compose），未再重读合同。
- 未执行测试；124pass 为用户口径；本报告为工程边界意见，非医学或迁移批准；未创建任务、不请求新框架。

R1 是否按必修处理，建议先确认 pairs 生成是否恒覆盖全部同单元非未决陈述（可在下一窗口只读 `evidence_policy_alignment_pairs`/runner pairs 来源后定级）。
