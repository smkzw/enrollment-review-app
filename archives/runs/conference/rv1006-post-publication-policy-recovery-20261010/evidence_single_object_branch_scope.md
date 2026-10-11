Trellis SessionStart 上下文已加载。开始定向只读复核（基线 effc9643；上限 14 次读取；不实施、不派工、不运行测试/模型；git diff 上轮已被非交互权限拒绝，本轮不再重试 Bash，将以实际定义+同族测试为据并如实标注）。

先定位拆句核对、义务分支、合同与受限生成边界。

核心符号已定位（item 模型 284/299、grounded atoms 345、prompt 364-445、validate 677 与"另一义务分支"757-758；同族测试 399；合同 modality 194/928/1139；受限生成边界 228/447/863）。并行读取 validate/grounded/prompt、合同与同族反例测试。

拆句核对的核心已读出（`_statement_grounded_atoms` 345-361、item 模型 281-303、validate 全组守卫 753-773、prompt 414-450、反例测试 368-420）。补四处：语气枚举头、建议/豁免消费者检查、条件覆盖助手、受限生成边界。

Trellis SessionStart 上下文已加载。定向只读复核完成（13/14 次读取；git diff 因非交互权限策略上轮已被拒、本轮未再尝试；未运行测试/模型/服务；不派工）。以下为完整报告。

## 一、读取范围（13/14）

- `app/agents/protocol_control_candidate_alignment.py`：275-450（item 模型 281-303；`_statement_grounded_atoms` 345-361；`build_candidate_alignment_prompt` 414-450）、149-235（`_split_obligations_cover_source` 149-182、`_conditioned_obligations_cover_source` 185-203、`_common_trigger_preserves_visit_time` 206-235）、670-775（**`validate_candidate_alignment` 全组守卫 753-773**）。
- `tests/v2/agents/test_protocol_control_candidate_alignment.py` 350-431（同源拆分/多分支/等价/无关反例族 368-420）。
- `app/domain/contracts/protocol_controls.py`：148-194（`ControlObligationKind` 177-191、`ControlObligationModality` 194-199、`_validate_obligation_semantics` 211-233）、920-1180（`ControlObligationAtom` 928-973、`ControlObligationGroup(Draft)` 1117-1175 与 `applies_to_trigger_branch_indexes` 语义）。
- `app/protocols/protocol_control_gate.py`：2288-2306（可选语气 `OPTIONAL_ACTION_MODALITY_DROPPED`、豁免 `EXEMPTION_MODALITY_OVERSTATED`）、2318-2333（`_check_conditional_exemption_binding` 头）。
- `app/services/protocol_control_restricted_source.py`：228-345（`_restricted_capability_batch` 全、受限记录字段 307-318）。
- **手段限制（如实）**：`git diff` 不可用——Bash 在非交互模式被权限策略拒绝（上轮实测；本轮不再重试），因此无法列出 effc9643 上的精确变更行；本报告以"实际定义+同族测试"为据。**未执行**：测试、模型、服务、写库。

## 二、根因（问题 1 前半）

**存在误拒，根因已定位在 `validate_candidate_alignment` 753-758：**
```python
if item.decision == "fully_expressed":
    if not any(atom in obligation_atoms for atom in selected_atoms): raise ...（未引用承担本条的义务原子）
    if any(not any(atom in selected_atoms for atom in group.atoms)
           for group in candidate.obligation_expression.groups):
        raise ValueError("候选存在未覆盖本条要求的另一义务分支")
```
- `selected_atoms`（735-748）= 仅由**本条 statement** 经 `_statement_grounded_atoms` 接地、且被模型引句命中的原子；守卫再把"该 statement 必须出现在**候选的每一个**义务组"作为 `fully_expressed` 前提。
- 它把两种合法结构混为一谈：(a) **同一要求的多个替代分支**（每个都必须成立——测试 395-400 `unrelated` 正是要防"无关 OR 替代绕过本条要求"，须保留）；(b) **同一来源单元中另一条独立原文**所在的义务组（冻结现象：第一/第三项各自只接地到组 0/组 1，互不覆盖却都被判"另一义务分支未覆盖"）。DNF 语义（`ControlObligationGroupDraft.applies_to_trigger_branch_indexes`，1120-1127）允许 (b)：组可由不同触发分支与不同原文承担。提示词本身也承认来源闭包中的其他原文不是"新增"（414-422：不得把无关邻句借给本条，但"本条之外的条件或义务若来自该闭包中的其他原文，不能仅因本句没有重述就判为新增"）——校验与提示在此相互矛盾，误拒成立。
- 同族测试的二分证明了矛盾所在：`equivalent`（两组携带同一条引句）通过；`unrelated`（替代组只含不被本 statement 接地的原子）拒绝。缺的正是"替代组由**其他 statement** 接地"这一合法类。

## 三、最小修复（问题 1 后半 + 问题 2）

**修在校验侧（`validate_candidate_alignment`），不改作者编码。** 理由：让作者把第一条的引句复制进组 1 会制造虚假字面覆盖（并被后续受限/语义闭包与证据政策机制看见），且与 414-422 的"兄弟要求各自处置"直接冲突；让作者按原文拆成多个候选则会撞上单元级候选身份/受限机制（如 restricted_source 228-274 对"失败候选必须单单元"的假设），爆炸半径更大。作者在**同源同候选**内按触发条件分组建义务组本身是合同的合法表达。

**决定性规则（全部由宿主从冻结数据推导，不用模型自报分支索引，不加词表/病种特例）：**
对 `fully_expressed` 的守卫，把"每一组都必须含本条引句"改为"**每个未被宿主证明为他源要求的组**都必须含本条引句"。对不含 `selected_atoms` 的组 g：
1. **他源接地**：若 g 含有被**同单元其他 statement** 接地的原子（用同一 `_statement_grounded_atoms(unit, other_statement, candidate)` 计算，并建议要求 g 的每个原子都被他源覆盖，而非"恰好一个"，以收紧 laundering），记 `other_grounded(g)=True`；
2. **本条作用域不达**：若 `statement.scope_quote` 非空，且 g 的触发分支原子引句（规范化包含）未引用该 scope，记 `out_of_scope(g)=True`；`scope_quote` 为空（无条件要求）→ `out_of_scope=False`（保护不松）。
3. 仅当 `other_grounded(g) and out_of_scope(g)` → 豁免；其余仍抛"另一义务分支"。随后 760-773 的按组合取检查对豁免组 `continue`。
- **保护不丢**：无条件要求（`scope_quote` 空）仍要求全组覆盖 → `unrelated`（395-400）与"同一要求的每个替代分支"照旧拒绝；条件相同但分列两个触发分支、同由本条接地的组不满足 `other_grounded` → 仍要求覆盖（412-418 `weaker/full_quote_weaker` 的"完整合取内容"检查也保留）。
- **防坏分支被兄弟正核对掩盖**：豁免需要**同时**满足"他源完整接地"与"本条 scope 不达"；无关兄弟的正核对（另一 statement 的 `fully_expressed`）只证明它自己的要求，不改变本条组的豁免判定。残余风险如实报告：若坏分支故意不引 scope 且挂上他源引句，文本层仍可能蒙混（宿主不做语义推断，`validate_candidate_alignment` 自述 678 "model remains responsible for semantics"）；这属于已知文本边界，应依托后续来源复核/发布门，而不是删除守卫或引入模型分支索引自报。
- 建议用现有正反例扩展测试：新正例（他源组豁免）、等义例（同要求双分支仍要求双向覆盖）、危险例（他源引句+scope 引用仍须覆盖）、恢复例（豁免规则若放宽过度，`unrelated` 必须仍拒，且上述既有测试保持绿）。

## 四、消费者能否忠实表达"允许一次 / 无须"（问题 3）

- **合同现状**：`ControlObligationModality` 只有 `MANDATORY/RECOMMENDED/BEST_EFFORT`（194-199）——**没有** allowed/permitted/not_required 值；kind 里也没有"允许"类（177-191）。"允许"目前只能靠**陈述措辞 + 语气检查**：gate 2288-2295 要求原文可选 cue（如"可…"）出现在原子 `source_excerpts` 时，`atom.statement` 必须保留可选语气，否则 `OPTIONAL_ACTION_MODALITY_DROPPED`；**豁免**则被 2301-2306 明确拒止（`prohibit_event` 的引句含"无需/不要求"→ `EXEMPTION_MODALITY_OVERSTATED`），另有 `_check_conditional_exemption_binding`（2318-2333）要求豁免的条件与其被豁免操作绑定。
- **结论**："允许一次操作乙"仅在"措辞保真 + （如建模）次数经 evaluation 的 `repeat_scheme` 承载"的范围内可表达；"一次"没有义务侧的计数/比较符专用位（`value_comparison` 属于 `ControlAtomEvaluationSpec`，非许可计数）。"无须重新编号"不能作为义务语气表达——把它编码为 prohibition 被正确拒绝；豁免只能落在外层例外/条件绑定或受限记录。**判定：部分可表达；缺口是"许可/无须"没有结构位**。
- **如何精确记录缺口而不放行（沿既有记录）**：使用现有 `RestrictedProtocolControlStatement`（restricted_source.py 307-318：`limitation_kind`、`unresolved_dimensions`、`source_quote/source_span_ids`、`source_force`、`decision_functions`；版本族见 52-58；登记校验入口 `_validate_restricted_definition_registration` 622-644），即把"当前消费者无法忠实表达该许可/豁免语义"登记为受限陈述并保留逐字原文；**不**把 `incomplete` 改标 `fully_expressed`，**不**新增通用框架。必须如实指出：自动隔离路径 `_restricted_capability_batch` 目前只接纳 `TIME_PRECISION_UNSUPPORTED`（243-244 与 238-248 条件），**许可/豁免类缺口目前没有同等的自动落点**——这是需要确认/补齐的缺口（本轮未读其它登记路径全貌，标注"未检查"）。

## 五、四类样例与消费者落点（问题 4）

- **必要正例（新规则下应过）**：单元含"如存在条件甲，允许一次操作乙；操作乙前禁止行为丙；如结果丁成立，可进入流程戊"；statement1（scope=条件甲）接地组 0、statement3（scope=丁）接地组 1；两条 `fully_expressed` 在"他源接地+scope 不达"豁免下通过，且各自按组合取检查通过。现状（未修）：两条均被 753-758 拒——**已证明**（守卫生效路径+夹具同型）。
- **等义例（保护）**：同一要求的两个触发分支各自携带本条引句（同由本条接地）→ 不满足 `other_grounded` → 仍要求每组覆盖，`unrelated/weaker/full_quote_weaker`（395-418）语义不变——**已证明**（现有测试断言）。
- **危险反例（残留风险）**：坏分支丢弃 statement1、触发原子不引 scope 且挂上 statement3 的引句 → 文本层可获得豁免，掩盖漏表达；修复中"他源**完整**接地 + scope 引用必须比对触发原子"可挡住常见形态，但不能证明语义——**已证明（风险可达路径为代码推导）+ 未检查（未用真实回答验证）**。
- **恢复反例（若修错）**：把守卫直接删掉或按"任一组覆盖即可"，`unrelated` 类替代组即通过，绑定负核对→语义闭包修复路径（上一增量 10280-10370）不再触发，遗漏静默——**已证明**（测试 395-400 即为该反例的现存闸门）。
- **消费者落点**：`validate_candidate_alignment`（753-773）← `_statement_grounded_atoms`/`_source_fragment`（139-146）← 绑定与证明复用（`reusable_proven_alignment_items` 581-622）；其判定进入 runner 的 `require_evidence_policy_alignment` 与 cited_unexpressed/`_reviewed_semantic_closure_repair` 分支（上轮已读 10249-10370）；语气消费者为 gate 2288-2306（可选项/豁免）与既有 modality 检查；受限落点为 `_restricted_capability_batch`（228-340）与受限登记（622-644）。**引用对应≠含义证明**：678 自述与 447-448 已限定字面/身份核对，修复只改"哪些组必须携带字面覆盖"，不升级语义结论——**已证明**。

## 六、必修项与建议（工程与批准分开）

- **必修（P1，误拒根因）**：`protocol_control_candidate_alignment.py` 753-758 + 760-773 的豁免规则（见第三节）。反例：冻结的三句同源多组样例（第一/第三项互不覆盖）；当前两条 `fully_expressed` 均被拒，导致 3 次请求后仍拒绝。最小改动=新增宿主推导的豁免判据并跳过豁免组，不删守卫、不加词表。
- **必修（P2，能力缺口登记）**：确认"许可/无须"缺口的登记落点（现有受限记录 vs `_restricted_capability_batch` 是否扩展到同类 `consumer_unavailable`）；未确认前不得把此类回答标为 `fully_expressed`，不得改标签放行。反例：`ControlObligationModality` 无 permitted/not_required（194-199），`EXEMPTION_MODALITY_OVERSTATED`（2301-2306）会拒绝把"无须"写成禁止。
- **不建议**：关闭任何 gate、伪造 history、追加整组读取、词表/病种特例、通用新框架。
- **批准边界**：以上为工程边界意见；是否修、以及任何临床/迁移结论需另行评审，本报告不构成医学批准或迁移批准。

## 七、反证与未读（如实）

- **已证明**：守卫生效与误拒机理；接地的文本/单元局部性；提示与守卫的矛盾；语气/豁免消费者代码；DNF 组语义与合同字段；受限记录字段族；`unrelated/weaker/equivalence` 测试二分。
- **推测**：冻结作业的两条 statement 的 `scope_quote` 已被解释器填充（修复可命中）；受限登记可直接承载许可/豁免缺口（未验）。
- **未检查/未读**：`git diff`（权限拒绝）；`_check_obligation_modality_and_event_anchor` 全体与 `_OPTIONAL_ACTION_STATEMENT_RE`/`_EXEMPTION_MODALITY_RE` 图案本体；`_conditioned_obligations_cover_source` 与豁免规则叠加后的联合行为（需以新测试固化）；受限登记其它路径（447-520、622-644 仅读头部）；解释器写入 `scope_quote` 的路径；真实回答/病例（按约束不读）。
- **未执行**：未运行任何测试或模型；修复效果未由运行验证。

本轮为只读复核、未创建任务；若要将 P1/P2 登记为 Trellis 任务或进入计划，请告知。
