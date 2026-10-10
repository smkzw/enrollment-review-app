Trellis SessionStart 上下文已加载。开始同一恢复边界的括号边界只读审阅（基线 78194eae；上限 12 次源码读取；只读、不执行测试、不写文件、不申请新 Phase）。先定位四处目标。

目标已定位（gate 226/4881/5017/5061、deconstructor 11796-11798、gate 测试 436、执行组成 2123）。并行读取四个实现区与测试索引。

实现区已读出（存在性集合新增 `（X）`/`(X)` 两个包裹形式 249-252；范围对账 258-273 未变；scoped 提示 11795-11798）。补两处：`_normalize_prohibition_quote` 的规范化粒度与门测试族（361/391/436/509）。

Trellis SessionStart 上下文已加载。只读审阅完成（11/12 次读取，留 1 次未用；未运行测试、未写文件、未创建 Trellis 任务、未申请新 Phase；不把任务说明当结论）。以下为报告。

## 实际已读范围（11/12）

- `app/protocols/protocol_control_gate.py`：161-162（`_normalize_prohibition_quote`：仅压缩空白+去尾部 `。；;`，括号原样保留）；173-175（`_split_prohibition_atom_covers_clause` 头）与 195-223（其体尾，未改动的既有路径）；226-273（**`_parenthetical_prohibitions_are_quoted` 全文**：括号提取/剩余括号守卫 231-234、禁止词必须在括号内 235-236、逐片段存在性 237-255、**新增成员集 249-252**、上下文范围对账 256-273）；4881-4990（`_uncovered_enrollment_prohibitions` 主体：条款挑选 4906-4915、同一候选全覆盖注释 4916-4918、quoted_clauses 与调用点 4933-4958）；5010-5034（`locate_source_quote_offsets`）、5061-5082（`source_statement_ranges_cover_unit`）、5085-5120（`candidate_cites_unit_quote` 头）。**未读**：`_uncovered_enrollment_prohibitions` 4990-5010 尾（官方/流程目标回退）、`_split_prohibition_atom_covers_clause` 头 173-194、`_PROHIBITION_WORD_RE`/`_ENROLLMENT_PROHIBITION_RE` 定义体。
- `app/agents/protocol_control_deconstructor.py`：11755-11804（scoped 分支：owned 裁剪与 context 只读 11755-11786；**提示 11795-11798**：禁止原子 statement 保留实际禁止事项、source_excerpts 同时保留逐字片段与完整上位原句、条件/允许/数量/后续/免除不得只留 notes、保留引用≠把允许改成必做）。
- `tests/v2/protocols/test_slice58c_protocol_control_gate.py`：355-530（`test_one_quoted_candidate_does_not_cover_second_prohibition_in_same_unit` 361-388、`test_full_paragraph_quote_covers_only_the_prohibition_expressed_by_atom` 391-425、**`test_parenthetical_prohibition_presence_does_not_require_other_actions_in_atom` 428-506**：17 个变体含 `fullwidth_source/ascii_source` 预期 0，`wrapped_missing_context/wrapped_wrong_source/nested/mismatched/borrowed_context/changed_context/missing_qualifier/second_missing/outside_prohibition` 预期 1）。
- `app/services/protocol_control_execution.py`：2123（新组成 `scoped-source-governing-citation/v1`，grep；组成列表机制为早前轮次已读）。
- 未做 diff（禁 shell）：“仅此一处改动”依代码形态与任务陈述。

## 机制事实与逐挑战结论

**存在性集（唯一改动点）**：249-252 由"引用须等于片段"扩展为 `{片段, （片段）, (片段)}`。片段为 `_normalize_prohibition_quote` 后的逐字文本（161-162 仅压空白、去尾标点，**不删任何限定词/否定/数量字符**）；statement 侧要求仍严格等于片段（248）。因此条件、数量、否定不会因该改动丢失——`missing_qualifier`（丢"复核前"）与 `changed_action` 仍拒（测试预期 1）。边界：若生产者把括号写进 **statement** 而非引用，仍会拒（本窗口未放宽，提示要求 statement 只留实际禁止事项），属有意范围；引用侧接受"片段/一对全角/一对 ASCII 包裹"三种精确形态。

**嵌套/混搭**：231-234 先以 `（[^（）()]+）|\([^（）()]+\)` 抽取并检查剩余文本不得再含任一括号字符；249-252 为精确等值集合（无正则模糊）。`nested`、`mismatched` 预期 1 与实现一致；只允许同一片段外**恰好一对**同型括号。

**错误来源/借兄弟引用**：241-244 的 `grounded_atoms` 要求原子 span ⊆ 本单元 span；264 的 `locate_source_quote_offsets(clause, …)` 要求引用逐字出现在**本单元本条款**内；4955-4957 按候选逐个调用（每个候选自证），兄弟候选的词不能替另一候选通过。测试 `wrong_source/borrowed_context/wrong_source` 与 `wrapped_wrong_source`（预期 1）钉住；`fullwidth_source/ascii_source`（预期 0）钉住新允许项。同一候选内跨原子（如 trigger 上下文原子 + obligation 禁止原子）合并覆盖是既有设计（测试 446-450 即此形态），不是"借兄弟"。

**范围对账未被放宽**：258-259 只豁免每个片段的首尾两个括号字符（逐字符区间），260-266 追加本单元可定位引用，273 仍走 `source_statement_ranges_cover_unit(..., allow_joining_punctuation=True)`——除空白与连接标点外，条款其余每个字符都必须被候选引用字面覆盖。`wrapped_missing_context`、`changed_context`、`missing_context`（预期 1）证明新括号允许**不能**换掉上下文覆盖；`model 把上位情形留 notes` 的真实拒因（覆盖缺失）依然成立，不会被本增量洗白。

**"完整原文被当完整含义"**：不成立。229 自述 "Check literal presence only; conditional meaning still needs source review"；测试 503 注明 "proves presence, not clinical equivalence or authorization to publish"；提示 11798 明确"保留上位情形的引用不等于把允许/免除行为改成必须完成"。宿主不填患者/规则含义，不把引用更长当采用；采用门与语义核对未动。因此本窗口只把"误拦"改成"按真实缺陷拦"，模型没做上下文引用就停在需要核对（与任务描述一致）。

**另一个建议语气门/兄弟**：未读（不在本窗口范围）；scoped 提示仍为 owned 单元、context 只读（11755-11786），无"随第一闭包擅改兄弟"的新通道。

## 可达问题、反证与最小建议

- 在已读范围内**未发现该窄改动引入的可达缺陷或越权**：新允许项是闭合三形态等值，且被 `wrapped_missing_context/wrapped_wrong_source` 反证排除"只靠括号引用过关"。
- 边界 B1（可选确认）：statement 侧带括号、或引用带省略号/异型括号（「」等）仍拒。若真实生产者可能写出 statement 带括号的形态，这是下一处误拦候选；按现在提示（statement 留实际禁止事项）可不改，建议仅补一条负例测试钉住边界，不要放宽到模糊匹配。
- 反证：未 diff 基线，无法排除同窗口内还有其他未读改动；`_PROHIBITION_WORD_RE`/`_ENROLLMENT_PROHIBITION_RE` 定义体未读，`outside_prohibition`、`second_missing` 的判定细节以测试为准；二期"建议语气门"未读，不能对它下任何结论。
- 最小建议：保持 256-273 范围对账、249-252 精确集合与 11795-11798 提示不动；如要补强，只加"statement 带括号/异型括号/多余包裹"负例与"完整上位原句+片段双引用"正例各一；不建议改范围对账、不放宽来源标准、不让宿主填含义。

## 局限

工程审阅≠临床批准，未代跑产品；该 Job 的剩余拒因（上位情形文字未进引用、另一建议语气门）仍需真实模型核对。测试未由我执行；组成串仅 grep（2123）；未读清单见上。本轮只读、未创建任何任务；请确认 B1（statement 侧括号与异型括号）是否有意保持拒止，以便决定是否需要那条边界负例。
