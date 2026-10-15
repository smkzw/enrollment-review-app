我先只读三份指定代码和对应差异，核对同源疑问的身份绑定、兄弟不变和恢复路径。绑定条件和恢复门禁还要对上数据模型和目标复核复用点，我接着只查这几处。# Conference Output: rv1006-same-source-question-review-20261009 - evidence_single_object

## Output

同源完整原文不能按「单元 span 是目标 span 的子集，且任一配对摘录等于整段单元原文」来放行。这个条件会在多 span 单元上把别的位置收进疑问上下文。恢复时若当前绑定消失，旧答复仍会被当成可跳过的当前证明。这两处都还没到可合并的程度。下面不构成临床、监管或发布验收。

### 证据

读过的当前定义，对照三文件 diff（相对 `db2dec4887437747fcbdb33eddac88c9396ca5f1`）：

- `source_question_official_context`、`can_recheck_source_scope_question`、`build_source_scope_question_prompt`、`apply_source_scope_question_recheck`：`app/agents/protocol_control_source_interpretation.py` 478–618。
- 疑问历史恢复与调用：`app/agents/protocol_control_deconstructor.py` 7207–7248、7703–7758。
- 目标复核复用身份：同文件 6913–6934、7045–7070、8244–8305、9079–9100。
- 合成测试与单 span 夹具：`tests/v2/protocols/test_slice58c_control_deconstructor.py` 178–190、13801–14008。
- 官方目标契约：`app/domain/contracts/protocol_controls.py` 271–275、292–296、2417–2443。`source_span_ids` 必须按 ID 排序且唯一；摘录非空时必须与 span 等长。`Phase5ControlModel` 只有 `extra="forbid"`，没有 `validate_assignment`。
- 相邻消费者（不在三文件 diff 内）：`app/services/protocol_control_execution.py` 2532–2583。疑问回放核 `precondition_sha256`、来源 span 和 `apply_source_scope_question_recheck`，不读 `source_context_sha256` 或 `prompt_sha256`。

Diff 实际新增的是：上下文函数、`can_recheck` 的官方上下文分支、提示词里的 `same_source_original_context`、历史兼容判断，以及调用时写入 `source_context_sha256`。普通原句的可改字段仍只有 `unresolved`；原生表分支的 `allowed` 集合没有改。

绑定实现在 493–497 行：

```493:497:app/agents/protocol_control_source_interpretation.py
        if not target.source_excerpts or not set(unit.source_span_ids).issubset(target.source_span_ids):
            continue
        if any(ref in unit.source_span_ids
               and normalize_source_excerpt(excerpt) == normalize_source_excerpt(unit.excerpt)
               for ref, excerpt in zip(target.source_span_ids, target.source_excerpts, strict=True)):
```

唯一性只看 `len(matches) != 1`（499–500）。返回包只有 `version`、`source_span_ids`、`source_excerpts`（502–506），没有 `source_order`、`official_code`。

单 span 且摘录错位时，现有写法会拒绝。单元只有 `S1`，目标在 `S2` 放了相同文字时，`S2` 不在单元 span 内，`any` 不成立。`wrong_source`、`wrong_excerpt`、`duplicate_target`、`missing_excerpt` 覆盖的是这一类，夹具单元只有一个 span（183 行 `source_span_ids=[span_id]`）。

恢复条件在 7239–7246 行：当前 `source_question_official_context` 为 `None` 时直接视为兼容；只有当前上下文仍存在才比较 hash。调用侧仅在上下文非空时写入 hash（7721–7726）。`prompt_sha256` 有记录（7718），恢复时不比较。`source_repairs = len(question_history)`（7248）没有被这处改写清零。

失败路径在 `question_response = source_reader(...)` 之后才改陈述；异常时原 `source_interpretation` 原样返回，状态是「需要核对」（7742–7758）。`can_recheck` 和 `build_source_scope_question_prompt` 在 7705–7709，位于 7727 的 `try` 之外。历史扫描 7239 行也在该 `try` 之外。

陈述身份含 `unresolved`（6920–6934）。疑问改写后，只有该 index 与 `resumed_review_identity` 不一致，从而退出复用（8244–8274）。成功复核后会按当前陈述重写身份（9097–9100）。`decision == "unresolved"` 的旧复核项本来就不进入 `previous_covered`（8252–8258），这不是本 diff 新加的。

### 推断

最高影响的缺陷有两处，都是本 diff 引入的。

1. 多 span 绑定过宽。单元 span 是 `{S1, S2}`，整段 `excerpt` 只等于 `S1` 的配对摘录，`S2` 的配对摘录不同，但 `S1` 已满足 `any`。函数仍返回整个目标的全部摘录。相同文字出现在单元并不拥有的 span 上不会单独放行；相同文字出现在单元多出来的另一个 span 上会放行。测试没有构造多 span 单元。

2. 绑定消失仍复用旧答复。历史收据里已有 `source_context_sha256`，恢复时目标被改到不再唯一、摘录不再相等或 span 不再覆盖，`official_context is None` 仍把该条放进 `seen_questions`。若恢复进来的陈述已经按旧上下文清空 `unresolved`，`can_recheck` 也因没有疑问而为假，旧清空结果会留下来。随后目标复核身份按清空后的陈述计算，清空之后做出的复核可以继续复用。这与「上下文变了不得把旧答复当当前证明」相反。上下文内容仍可绑定但 hash 不同时，7239–7242 行会重问，测试 14004–14007 只覆盖了这一种。

损坏的平行数组会把整批跑崩，而不是保留来源。`zip(..., strict=True)` 在长度不等时抛 `ValueError`。模型构造期会拒绝这种目标，但列表就地 `append` 不会再次验证；本测试就是这样改目标的。异常发生在疑问 `try` 之外，不会变成「需要核对」收据，历史扫描中的其他成功兄弟也不会被正常标记。

源顺序没有单独的阅读序。返回的是官方目标已排序的 span ID 序。提示词 558–560 行要求模型判断后续列表、上位条件和相邻分支，载荷里却没有 `source_order`。结构单元有 `source_order`（186 行），这个函数没有读。span ID 是否与阅读顺序单调，生产者不在本次阅读范围内，不能当成已证实的错序。

以下要求在已读代码里成立，不记为缺陷：

- 普通原句只允许改 `unresolved`；兄弟陈述只替换当前 index（615–617）。
- 原生表可改字段集合没有变。
- 疑问步骤本身不发布。失败保持原陈述并返回「需要核对」；清空疑问后仍要走原有 wire 和目标复核。`unresolved` 变化会使该条旧复核失效，兄弟身份不变则可复用。
- 相同 `unresolved` 的疑问收据不会再次调用源疑问。未决目标复核本来就不可复用，所以不能发布；下一次恢复仍会为该条再叫目标复核。这是原策略，不是本助手把成功兄弟拖去重读。
- 预算不重置。上下文变化后的新疑问继续消耗 `len(question_history)` 之后的剩余次数。

### 建议

绑定改成按单元自己的 span 取配对，损坏目标跳过，不要让 `ValueError` 逃出：

- `len(spans) != len(excerpts)` 的目标 `continue`。
- 只接受恰好一个单元 span；该 span 在目标里，且这一条配对摘录经现有 `normalize_source_excerpt` 后等于整个 `unit.excerpt`。
- 多 span 单元返回 `None`，直到另有已定义的整段拼接规则。不要用无分隔符拼接猜规则。
- 其他位置的相同文字不参与查找。

恢复比较两边的上下文身份，而不是把「当前没有上下文」当成兼容：

```python
current = _sha256(json.dumps(official_context, ensure_ascii=False, sort_keys=True)) if official_context else None
context_compatible = detail.get("source_context_sha256") == current
```

没有官方上下文的旧疑问两边都是空，仍可跳过，避免成功兄弟只因这个助手被重读。有记录 hash 而当前绑定消失，则重问，并继续计入已有预算。

上下文载荷不要把排序后的 span ID 序说成阅读顺序。能在本批 owned 或 context 单元找到的 span 附上 `source_order`；找不到的标成无顺序。这会改变 hash，旧上下文收据应失效。

`protocol_control_execution.py` 2532–2560 的回放在采用疑问答复前增加同一 hash 比较。不相等则整段见证返回 `None`，不要只靠事后丢弃 `source_target_review`。

### 不确定性

- 没有运行测试。分配里给出的 33 passed / 1223 deselected / 5.98s 不是我的证据。
- 没有读官方摘录的生产者，因此不能证明生产 span ID 与 `source_order` 不一致，也不能证明多 span 单元会在生产批次里走到这个助手。
- 没有读 execution 见证的调用方，所以不能证明 2532–2583 的返回值会直接发布。能证明的是它会把疑问改写后的来源陈述标成复用，且不核上下文 hash。
- 没有读 `validate_source_interpretation` 对研究期别的规则，也没有读 `build_result` 的默认参数。原生分支丢弃 `apply_source_scope_correction` 返回值是原代码，不在本 diff 的逻辑变更里。
- 归一化相等会抹掉空白和弯引号。这与现有来源比较一致；不是逐码点相等。
- 孤立真实产品运行不在本次证据内。合成夹具不是临床原文，不能代替医学批准。

未读：三个大文件的其余部分、`tmp/`、`.env`、模型原答、数据库、临床原件；除上述模型与 execution 见证外，没有为了扩范围再搜。

### 异议、修复、决定点与给 Codex 的问题

异议：现在的「唯一绑定」只保证恰好一个官方目标被子集命中，不保证单元的全部来源 ID 与整段原文独占同一组配对。恢复逻辑把绑定丢失写成兼容，旧的清空或保留疑问会变成当前证明。提示词把这份列表当完整原文的前后文，载荷却是 span ID 排序。

修复：单 span 精确配对，损坏目标跳过，上下文 hash 双边比较，回放见证使用同一比较，输出顺序与阅读顺序分开。

决定点：多 span 单元是直接拒绝，还是允许一种明确的整段拼接。在决定前应按拒绝处理。

请 Codex 在同会话确认两点：

1. 多 span 官方单元是否本轮就必须能问？若否，单 span 精确配对就是本轮契约。
2. `protocol_control_execution.py` 的疑问见证是否纳入本轮？若冻结批次在该见证下不能改摘录，这个洞是潜伏的；若目录摘录会刷新，它就是第二条复用路径。临时安全路径是 hash 不等则见证失败，不发布。
