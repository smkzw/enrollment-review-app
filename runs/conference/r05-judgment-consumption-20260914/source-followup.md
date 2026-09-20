I'll re-read the current source of the bounded correction, including `predicate_ids` attribution and the new gap-selection path, and check mixed-requirement and stale-expectation cases.I'll read the changed definitions in full, including `predicate_ids` validation and the new gap-selection helpers.Next I’ll inspect expression-reason substitution, ClausePack rehydration of `predicate_ids`, live projection, and remaining action/wording paths.# Conference Output: r05-judgment-consumption-20260914 - evidence_single_object

## Output

只读复审当前源码，不沿用上一轮「无归属合同」前提。未跑测试/导入/库/网络。仅业主所述 `py_compile`。无语义采用、无临床或运行时接受声明。

### 1. 对上一轮前提的纠正

**证据：** `EvidenceRequirement.predicate_ids` 已在 `app/domain/contracts/rules.py:294-325`（空则省略序列化；非空须显式来源字段、去重、且不得用于流程/控制来源）。`RuleComponent.validate_evidence_predicate_links`（`:350-372`）要求引用落在本组件原子上。`ClausePackClause.evidence_requirements` 类型就是该合同（`clause_pack.py:34`）；`clause_to_rule_component`（`eligibility_review_projection.py:792-804`）原样重水合，不丢字段。

上一轮「没有归属合同、只能整组件压 `professional_judgment_unverified`」不成立。本轮也不再建议整组件抑制 OU。

---

### 2. Evidence（当前接线）

**E1. 发布 v3 在新保存前重放检索**

`frozen_review_publication.py:31, 67-75`：已完成幂等回执先返回（`:67-69`），不重放。新发布对 `context.judgment_search_results` 逐条 `verify_frozen_judgment_search_result`，再计算。方法版本钉 `PUBLICATION_VERSION` 与 `EVALUATOR_VERSION`（`:84-86`）。计算钉 `component-review/v7`（`frozen_review_calculation.py:27, 157`）。

**E2. 检索缺口按要求保留**

`_summary_gap_requirements`（`eligibility_review_projection.py:395-460`）输出 `dict[requirement_id, GapType]`。未来阶段、同阶段其他节点、同要求缺文件仍 skip。`CANDIDATES_PRESENT` / 无摘要 / 不完整 → OU；供给页双读未见 → PJ，**除非**该要求期望 `status==OBSERVED` 则改 OU（`:454-458`）。`_summary_gaps`（`:463-465`）只是 `set(values())`，供旧调用方。

**E3. 缺失原因替换只用显式链接**

`judgment_gap_selection.missing_judgment_predicates`（`:8-33`）：

- 候选要求 = `id in gaps` **或** 要求自身 `required_source_types` 含 `investigator_assessment`
- 其中任一 `predicate_ids` 为空 → 返回空集（整段不做替换）
- 每个 `requires_professional_judgment` 原子：取其在上述集合中的链接；须有链接、选择键存在且为空、且 **所有链接** `gaps.get(id)==PROFESSIONAL_JUDGMENT`
- 不写事实、不改真值

**E4. 组件计算**

`frozen_review_calculation.py:225-239` 把 per-requirement 缺口与 `missing_judgment_predicates(...)` 传入。`component_review.py:36-54`：只清 **该要求** 上过期 PJ/OU 期望缺口；缺文件等其它期望保留；`source_gaps` 并入该 map 的缺口值。其它谓词仍走独立 `unverified_predicate_ids`。

**E5. 求值器**

`expression.py:609-625`：`missing_judgment_predicate_ids` 须 ⊆ 专业判断原子且选择为空，否则抛错。命中则 `UNKNOWN` + `professional_judgment_missing`。未命中而在 unverified 中的专业判断原子仍是 `professional_judgment_unverified`（`:620-621`），不再误标成泛化 `observation_unverified`。`REASON_GAPS` 仍是 missing→PJ、unverified→OU（`assessment.py:211-212`）。

**E6. 未做的**

找到摘录仍只是 OU。资格选择仍拒绝把 PJ 谓词做成确定性事实。无新的用户采用授权。实时投影仍只传 `_summary_gaps` 集合，不传 `judgment_gap_by_requirement` / missing 集合（`eligibility_review_projection.py:721-738`）。

---

### 3. 场景核对（源码路径，非运行）

| 场景 | 推断 |
|---|---|
| 单一到期 IA、显式链接、空选择、双读未见、期望非 OBSERVED | 该谓词进 missing → `professional_judgment_missing`；source_gaps 仅 PJ；unverified 被 missing 抢先。组件可只剩 PJ。相对 v6 并集，这是有界修正。 |
| 两套到期 IA：A 未见（PJ）链 P1，B 有候选/无摘要（OU）链 P2 | P1 missing，P2 保持 unverified。source_gaps `{PJ,OU}`。两缺口并存是按要求的，不是整组件抹 OU。 |
| 同一谓词链 A=未见且 B=未决 | `all(gaps==PJ)` 失败，不替换。P 保持 unverified。正确。 |
| 无摘要 / 覆盖不完整 | map 为 OU，不能 missing。过期期望 PJ 若该 id 在 map 内会被清掉。未检索不会晋升缺失。 |
| 同要求缺文件 | `_summary_gap_requirements` skip，不进 map；期望 RFM 不被清。`gaps.get` 非 PJ，不替换。未见不能盖掉缺文件。 |
| 期望 OBSERVED + 供给页未见 | map 强制 OU（`:454-458`）；discard 清过期 PJ；不进 missing。已有 OBSERVED 不会当成缺失。 |
| 遗留 IA `predicate_ids==[]` | `:20-21` 整组件不做替换。source_gaps 仍可含检索 PJ，谓词仍 unverified→OU。双缺口退回旧行为。这是有意 fail-closed，不是采用。 |
| 找到摘录 | 仍 OU，无 accepted fact。不是语义采用。 |

---

### 4. 具体错误（当前修正内部）

**D1（高，未来/他节点泄漏进「全部链接已缺失」）**

`missing_judgment_predicates` 外层集合含 **全部** IA 要求，包括 `_summary_gap_requirements` 因未来阶段或同阶段其他节点而 skip、因而不在 `gaps` 里的要求（`judgment_gap_selection.py:17-19` vs `eligibility_review_projection.py:418-429`）。

反例：P 显式链到到期 A（双读未见→`gaps[A]=PJ`）和基线 B（IA、未到期、有 `predicate_ids`）。`linked` 含 B，`gaps.get(B) is None`，`:30-31` 失败。P 不进 missing，保持 `professional_judgment_unverified`→OU；A 的 PJ 仍进入 `source_gaps`（`component_review.py:50`）。当前节点再次出现 PJ+OU 和互斥行动。未来要求通过「链接未全是 PJ」混入当前缺口，与 §17.2「未到期不混入当前缺口」及本任务点名的 future nodes 检查不一致。

同阶段 `template.workflow_stage_id != workflow_stage_id` 的 IA 同样不在 `gaps` 却在 `linked` 里，结果相同。

缺文件当前要求不在 `gaps`、但在 IA 集合中：`all(...)` 失败、不报缺失——这条应保留。

**D2（高，未到期/他节点的无归属 IA 误伤到期已归属缺失）**

`:20-21` 对上述外层集合做 `any(not predicate_ids)`。一条 **未来或他节点** 的遗留 IA（空 `predicate_ids`）会禁止 **当前** 已完整归属、已双读未见的谓词做 missing 替换。

反例：到期 A 归属 P、未见；未来 B 为遗留 IA。整段返回空。P 走 unverified，A 的 PJ 仍在 source_gaps → 又是双缺口。业主要的 fail-closed 是「无归属判断要求无法说明它解释哪条谓词」；把未到期无归属兄弟算进当前替换，过宽。到期且在 `gaps` 中的无归属 IA、以及当前缺文件 IA，仍应阻止替换。

**D3（中，相邻文案/行动仍按组件一套词）**

混合到期要求下保留 PJ+OU 是正确的。但 `publish_review_actions` 仍对每个 gap 用组件级 `ACTION_CONTENT`（`policies.py:68-72, 108-112`）：CRA「核实前不要求补写研究者判断」与研究者「作出并记录明确判断」并排，且不带 requirement_id。实时 `_reason`（`eligibility_review_projection.py:573-587`）仍用「任一 IA 不在 summaries」否定 PJ 文案。冻结主链不用 `_reason`，但正式行动词仍冲突。这不是再做整组件压 OU；是行动/文案粒度仍大于要求。

**D4（低，无期望行的已检索要求）**

`derive_gate_gap_types`（`assessment.py:268-270`）对到期且无期望行的要求加 `RECORD_INCOMPLETE`。discard 只改已有期望（`component_review.py:44-49`）。已检索 IA 若冻结上下文没有期望行：search PJ/OU 加上 RECORD_INCOMPLETE。是否出现取决于装配是否总有期望行；`requirements_scope_version` 管模板全集，不管期望行。不是检索采用错误，但是缺口并集多了一类。

**不是本修正的错误**

- 幂等旧回执不重放检索：业主已定为历史读取。
- 实时投影仍走 `_summary_gaps` 集合、无 missing 替换：旧消费者；v7 冻结路径未声称覆盖。
- 控制族 `investigator_judgment` 仍 unresolved：不在此次官方谓词替换范围。
- `source_scope_verified` 仍恒 False：正确。
- 非 IA 却带同一 `predicate_ids` 的实验室要求不进入 `linked`：实验室 OBSERVED + IA 未见正是应报 PJ 的形态；把非判断要求算进 `all==PJ` 会永远禁替换。

---

### 5. Recommendation

最小完整补丁只动 `missing_judgment_predicates` 的候选集，使其与 `_summary_gap_requirements` 的到期/当前节点窗口对齐：

1. **Poison（无归属）**：仅当「当前会参与判断检索消费」的要求无 `predicate_ids` 时返回空——即 `id in gaps` 的要求，加上当前节点被缺文件 skip 的 IA（仍须挡住缺失晋升）。不要把未来/他节点 IA 算进 `any(not predicate_ids)`。
2. **`linked` / `all==PJ`**：只对上述当前窗口要求取显式 `predicate_ids`。未来/他节点链接既不证明当前缺失，也不应阻止当前缺失原因。缺文件当前 IA 继续留在窗口内，使 `gaps.get!=PJ`。
3. **不要**整组件丢 `professional_judgment_unverified`；P2 未决必须仍是 OU。
4. 行动文案（D3）可另做有界改动：PJ/OU 并存时带要求描述，或 CRA 词不要写「不要求补写判断」。不是 gap 选择的闭合条件。
5. 不把本 diff 当成找到判断的资格/采用；`CANDIDATES_PRESENT` 保持 OU。方法批准须另签 v7/v3，本次没有。

---

### 6. Uncertainty

- 未跑测试；D1/D2 是源码闭合反例，不是 fixture 记录。
- 现场 ClausePack 有多少到期 IA 已填 `predicate_ids`、有多少未来 IA 仍为空：未知。空则当前节点仍走旧双缺口（D2 会放大）。
- 冻结上下文是否总有与检索要求对应的期望行（D4）：未读装配保证以外的存储。
- 实时投影仍可双缺口：不在 v7 发布路径；若工作台与正式报告必须同词，尚未对齐。

---

### 7. 给 Codex

**反对：** 不能把当前 v7 写成「缺失报告已按组件闭合」。单一当前节点、全链接、无未来 IA 兄弟时，原因替换是对的；未来/他节点 IA 仍能阻止 missing 并打回 PJ+OU。也不能把混合到期 PJ+OU 当成回归。

**决策点：** D1/D2 的候选集是否应收成与 `_summary_gap_requirements` 同一当前窗口（推荐是）。D3 是否纳入本 bounded correction。

**有界问题：** 显式链到未到期 IA 的专业判断原子，在当前节点是否允许 `professional_judgment_missing`（仅当前链接均未见），还是必须等全部链接节点到期？源码今日等于后者，并因此把未来混进当前 OU。暂态：按当前窗口收 `linked`/`poison`，缺文件当前 IA 仍阻止缺失。
