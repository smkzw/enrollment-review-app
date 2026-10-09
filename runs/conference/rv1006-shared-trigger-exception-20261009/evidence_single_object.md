我先只读这三份指定源码和它们相对 `e1cbe65a` 的差异，核对共同原文例外的接受边界，不改文件、不跑测试、不碰临床材料。# Conference Output: rv1006-shared-trigger-exception-20261009 - evidence_single_object

## Output

本轮不接受当前补丁作为可合并的范围证明。共同原文例外的新放行只证明“例外摘录这串字出现在每个触发分支的某条摘录里”，不能证明该例外管辖每个分支。在收紧见证之前，更安全的临时路径是继续用既有的 `EXCEPTION_SCOPE_ALL_UNSUPPORTED` 拒绝全部分支豁免。本角色不做临床批准，也不宣布产品完成。

### 实际阅读

只读，未改文件，未跑测试，未联网，未读真实方案、回答或数据库。

- 相对 `e1cbe65a` 的只读 diff：上述三文件，`+100/-1`。HEAD 就是 `e1cbe65a`，三文件均为未提交修改。
- `app/protocols/protocol_control_gate.py`：210–249、300–379、1985–2234、3050–3469、4150–4469、4480–4759。另用检索看到第 65 行 `CONTROL_PUBLICATION_GATE_VERSION = "phase5/control-publication-gate/v47"`，以及 5563、5578 行把该常量写入 `gate_version`。
- `tests/v2/protocols/test_slice58c_protocol_control_gate.py`：3087–3166、4200–4479。
- `app/services/protocol_control_execution.py`：1980–2199、2260–2439、2520–2639、2680–2799、3120–3239、4080–4259。检索确认 `current_gate_requires_refresh` 与 `failed_final` 的分流位置。

### 证据

补丁做了三件事。

1. 新增 `_exception_already_in_every_trigger`（`protocol_control_gate.py` 3213–3240）。无原子，或 `activates_obligation_group_ids` 为真，则返回假。否则每个例外原子的 span 集合非空，且**至少一条**归一化摘录同时满足：含 `_EXCEPTION_CUE_RE`（除非、除外、例外、unless、except）或整段匹配 `除.+(?:之外|以外)`；并且**每个**触发分支里至少有一个原子的 span 集合与该例外原子的整个 span 集合相等，且该摘录是该原子某条摘录的子串。
2. 该函数只在既有全分支检查里作为附加通道（3347–3353）：触发分支多于一个、`waives_trigger_branch_ids` 等于全部已知分支、组文本不含 `_EXCEPTION_BROAD_SCOPE_CUES` 时，旧逻辑失败；新函数为真则不再报 `EXCEPTION_SCOPE_ALL_UNSUPPORTED`。关键词通道保持原样。
3. `_deep_component_identity` 的 `validator_version` 连接串末尾增加 `shared-trigger-exception-source/v1`。`schema_version` 仍是 `phase5/deep-component-identity/v3`，`compiler_versions` 未改，`CONTROL_PUBLICATION_GATE_VERSION` 仍是 v47。

两个发布入口都先调用 `_check_dnf` → `_check_atom_sources`，再调用 `_check_branch_scope_and_paired_consequences`：候选在 4227–4259 与 4415，正式控制在 4550–4581 与 4712。`_check_atom_sources` 要求 span 与摘录等长、span 落在控制闭包内、摘录在对应结构单元中逐字出现。它不核对 `statement`。

新函数不读 `statement`。子串方向是 `quote in trigger_excerpt`。多条摘录用 `any`。span 按原子整集合比较，不按摘录下标配对。`_normalize_clause_fragment` 只去空白和句末 `。！？!?；;`，不去逗号，也不做 NFKC。

缩短检查在范围检查之后仍会执行。`_CONDITIONAL_SHORTEN_CUE_RE` 只覆盖洗脱缩短和 `washout may be shortened`。缩短夹具默认只豁免 `pct-target` 一个分支，进不了“豁免全部分支”这条分支。diff 没有改这六个缩短测试的夹具。

成功批次复用：`_same_deep_components_with_current_gate` 在仅 `validator_version` 不同时仍返回真。随后 `_validate_deep_batch_output` 通过才标 `reusable` / `same_material_and_current_gate`，并写上 `revalidated_from_gate_version`；校验失败则理由为 `current_gate_requires_refresh`，决策保持进入该分支前的 `refresh_required`。`failed_final` 走另一支，进入 `_validated_deep_partial_source`，不走上述成功复用。来源种子证明里的 `validator_version` 仍只写 `CONTROL_PUBLICATION_GATE_VERSION`。

测试里，平行夹具“除条件丙之外，条件甲/乙”和无该摘录的分支会走完整 `_gate_control_with_manifest`。`different_source`、`no_exception_cue`、`empty_atoms`、`replacement`、`extra_atom` 以及空白变体只直接断言辅助函数。

### 推断

这是本次新打开的接受路径，不是旧关键词通道的固有行为。旧通道在没有“全部/所有/任一/任意/无论/均适用/all triggers/any trigger”时拒绝全部分支豁免。新通道让下面的结构第一次可以通过。

最小反例：同一 span 的原文是“若条件甲（除条件丙之外）或条件乙成立，则必须记录用药日期。”两个触发分支都逐字引用这整句；例外原子摘录“除条件丙之外”、陈述“条件丙”、`waives` 两个分支、没有替代义务。来源校验通过，因为摘录都在单元里。新函数返回真：span 集合相同，摘录是子串，且匹配 `除.+之外`。门会放行。效果是条件丙成立时连条件乙一并豁免。括号里的例外只修饰条件甲。

同一机制还有三个相邻逃逸，都落在 3226–3236 的 `any` 加子串上。

- 短提示词：例外摘录只有“除非”或“除外”。它是提示词，也是两个分支长摘录的子串。陈述可以写成与摘录无关的肯定句或改写后的后果。
- 同原子额外摘录：一条是“除条件丙之外”，另一条是来源中另有的“改为永久停药”。`any` 只要求前者出现在每个分支。替代后果没有放进 `activates_obligation_group_ids`，缩短正则也认不出“改为/无需/豁免”。
- `除.+` 贪婪：整段以“之外/以外”收尾即可，中间可以夹着另一句义务。陈述不被比对。

第一因边界在 `quote in _normalize_clause_fragment(item)`，加上“任一摘录即可”。span 集合相等只说明两边标了同一组 span，不能把摘录钉到配对的那一个 span，也不能区分一个 span 里的多个分句。

平行夹具本身仍然站得住：两个分支的摘录分别是“除条件丙之外，条件甲”和“除条件丙之外，条件乙”，例外摘录等于共同前缀，陈述“条件丙”就是“除…之外”的内部名词。这个形状应当继续放行。

既有宽口径关键词路径另有缺口，补丁前已经如此。`_group_text` 把模型陈述和摘录拼在一起，“任一剂量”“全部受试者”这类词出现在陈述里就会满足全部分支豁免。它不证明例外覆盖每个触发分支。本补丁按合同保留该路径。缩短消费者只豁免单支，不经过新函数。本次 diff 没有改它们的判定式。

身份方面，深批成功结果会因校验串变化而被当前门重放：仍通过则不新增模型调用，不再通过则标为刷新而不是复用。这与“43 个成功批不重呼、失败记录不静默当成功”一致，前提是失败批留在 `failed_final`，不进入成功复用支。作者、编译和 schema 字段不在 diff 里。

### 建议

在当前合同内收紧这一个函数，不另起框架，也不改关键词通道和缩短判定。

每个例外原子、它的每一条摘录都要满足，而不能只满足其中一条：

- 归一化后的摘录能解析出唯一内部陈述：`除(.+)(?:之外|以外)` 的捕获组，或去掉句首“除非/除外/例外/unless/except”后的剩余部分。
- 该内部文本与该原子归一化后的非空 `statement` 完全相等。
- 每个触发分支都有一个原子，在与该摘录下标配对的同一个 `source_span_id` 上，把这条摘录当作分界前缀：摘录等于分支摘录，或分支摘录在该摘录之后紧跟 `，,；;、的`。
- 去掉这个共享前缀后，各分支剩余文本非空，且彼此不完全相同。

这样，现有平行夹具和“之 外”空白变体仍通过。单支缺失、外来 span、无提示词、空原子、额外原子、带 `activates_obligation_group_ids` 的替代组仍失败。括号中缀、短提示词、同原子夹带的替换句、陈述与内部名词不一致，都会回到 `EXCEPTION_SCOPE_ALL_UNSUPPORTED`。

测试应改到完整 `_gate_control_with_manifest`，至少覆盖：平行夹具放行、中缀整句复制拒绝、同原子第二条非共享摘录拒绝、陈述与内部名词不一致拒绝。现在的五参数辅助函数测试锁不住发布入口。

不要在本补丁里改 `_EXCEPTION_BROAD_SCOPE_CUES`。那会改变已经靠关键词放行的旧控制。v47 常量是否要动，见下面的决定点；在 Codex 确认前，不要顺便升出版本号。

### 不确定性

- 没有执行测试，所以上面的放行与拒绝是按代码路径推的。
- 没有读批次 44 的真实摘录。若当时每个分支已是“共享前缀 + 不同子条件”，收紧后的规则可以放行；若每个分支复制的是同一整句，不同剩余文本这一条会继续拒绝。后者需要 Codex 用私有形状确认，本角色不能读那些材料。
- 例外 `statement` 下游怎么被执行，不在这三份文件里。当前门确实不核对陈述，所以陈述偏离至少能通过发布门。
- `failed_final` 的局部草稿之后会不会在另一次恢复里重跑新门并采纳先前失败的完整 wire，本次只追到分流，没有追到最终调用点。成功复用支本身不会把门失败标成 `reusable`。
- 5563 与 5578 行之外，是否还有只按 v47 复用已发布目录的消费者，未读。

### 异议、决定点、给 Codex 的问题

最重要的异议：源摘录相配不是范围证明。当前补丁会把“一句里只修饰一个孩子的例外”放开成全部分支豁免，也会让肯定句、改写后果和额外摘录乘上同一豁免。

次要异议：拒绝用例大多没有打到两个发布入口；关键词通道本身不能证明全分支范围，但这是旧限制，不应混进这次修复。

决定点：

1. 是否要求先落地上述见证收紧，再允许产品重跑。本角色建议要求收紧。
2. 是否只保留深批 `validator_version` 后缀、出版门常量维持 v47。若还有目录只认 v47，身份边界就不够；若深批重校验已是唯一复用门，维持 v47 符合“只改校验身份”。
3. 不同剩余文本是否纳入本次最小修复。它能挡住“整句复制到每个分支”，也可能挡住真实的共享父句。这取决于未读取的批次 44 形状。

需要 Codex 回答的两点：批次 44 的共享摘录是各分支不同的前缀残段，还是同一句被复制进每个分支？出版结果的复用键是否只有深批 `validator_version`，还是同时包括仍为 v47 的 `gate_version`？在这两点明确前，临时路径是保持全分支豁免失败，不把当前补丁当作已通过的安全修复。
