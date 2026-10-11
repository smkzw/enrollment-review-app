我按 `evidence_single_object` 做只读核验。先读会议上下文和主会场计划，核对先决来源捕获、局部补读和作者前执行是否降级。上下文把四个文件按哈希冻结。我先核对哈希，再只在这些文件和允许的相邻合同里查完整性门禁、作者前补读和保存/恢复路径。# Conference Output: rv1006-preauthor-source-capture-review-20261011 - evidence_single_object

## Output

回退说明：主角色 `codebuddy-cli` / `deepseek-v4.1-flash` 在可恢复会话出现前不可用。本轮是已声明的回退 `grok-build` / `grok-4.7`。本轮没有重跑测试、没有读临床材料、没有调用产品模型，也不把捕获完整说成医学语义已通过。审阅与产品跨章模型同系列，不能声称模型独立或医学金标。Codex 保留最终采用权。

### 证据

四个冻结文件的 SHA256 与上下文一致，工作区 `HEAD` 就是基础提交 `f25f7eeb667cae0570223b739dc349e278341876`。相邻测试 `tests/v2/services/test_protocol_control_execution.py` 的 SHA256 为 `b6469a12d0fc9cdcb8dffdf3a426f88d188920b2ca7ee6cb985cdf2c3da36a90`，上下文未冻结该值。上下文中的「140 passed / 1624 deselected」是会场记录，本轮没有复跑。

新鲜来源、且当前没有作者草稿、未核提案、逐项核对、候选对齐或覆盖账时，作者前会调用 `missing_sequence_source_units`，再进入 `complete_source_units`（`protocol_control_deconstructor.py` 8495–8504）。补读只允许扩展 `quoted_text`：`apply_source_unit_quote_completion` 用 `model_dump(exclude={"quoted_text"})` 冻结强度、时间、先决、疑问和兄弟字段，并限制在宿主窗口内（`protocol_control_source_interpretation.py` 442–467）。窗口把先决摘录留在动作之前，并挡住吞并兄弟摘录。保存侧对带 `final_output` 的结果调用同一个 `missing_sequence_source_units`；有缺口时抛出 `SOURCE_SEQUENCE_CAPTURE_INCOMPLETE`（`protocol_control_execution.py` 3884–3897）。非受限旧成功因此留在 `refresh_required`，原因 `current_source_review_requires_refresh`。

预算没有因新作业升高。恢复种子里的 `source_repair_limit` 来自来源作业的 `deep_max_schema_repairs`，执行时取 `min(当前上限, 种子上限)`（4866–4871）。已调用次数由 `source_scope_question_history` 里 `called` 不为假的记录重算；缺省按已调用计。传输失败可在剩余缺口上续读，被拒绝的补读在校验器已变且当前仍有缺口时直接停止，不退回整批重读（2841–2910）。

### 最高后果缺陷

受限完成回执没有走这条捕获门禁。`restricted_batch` 存在时，预检、复用和检查点重放都只重建 `restricted_batch_from_review`，再比较是否与保存件相等：

- `_preflight_deep_source` 3661–3678：相等且链接不需刷新时，决策写成 `reusable`，原因 `same_restricted_source_and_current_gate`。
- `_validated_deep_source` 4110–4118：同样比较后直接返回该检查点。
- `_replay_checkpoint` 1296–1301：同样接受。

这三处都不调用 `missing_sequence_source_units`。`_same_deep_components_with_current_gate`（2177–2191）又忽略单独的 `validator_version` 差异，而 `source-sequence-preauthor-capture/v1` 正写在这个版本串里（2169）。因此校验器升到本门禁后，旧受限成功仍可按「当前门禁已复验」复用。

`validate_source_interpretation`（3575–3588）只要求先决短语位于动作之前，不要求摘录盖住单元尾部。`restricted_batch_from_review`（`protocol_control_restricted_source.py` 895–938）也只做来源和逐项核对校验。合成反例：

- 单元正文：`完成前置审核后，登记后续访视安排，只有以下条件满足才能继续`
- `quoted_text`：`登记后续访视安排`
- `eligibility_sequence`：`after_eligibility_decision`
- `eligibility_sequence_quote`：`完成前置审核后`

先决短语能定位，来源校验可以通过。尾句 `只有以下条件满足才能继续` 不是空白，也不属于连接标点 `；;。.:：，,`，所以 `source_unit_quotes_cover_source` 为假，`missing_sequence_source_units` 会返回该单元。若完成检查点的 `restricted_batch.source_quote` 仍只是短摘录，且重建结果与保存件相等，上述三条路径会把它标成可复用。同一解释若走非受限 `final_output`，3888–3897 会拒绝。保存消费者在两条完成路径上标准不一致，受限路径更宽。

同一缺口在失败恢复里也会漏到兄弟单元。`_validated_deep_partial_source` 3112–3118 只把「未决索引所属单元」算进补读名单。另一个已覆盖、但先决尾句未捕获的兄弟单元不会进入名单。函数随后可带着原草稿和核对返回（3254）。跑者看到 `resume_source_target_review` 后跳过 8495–8498 的作者前补读。校验器版本相同且独立续读政策开启时，`preserve_unresolved`（3718–3729）还能经 `restricted_batch_from_review` 把该结果完成（4744–4758），仍然不查序列捕获。

### 可延后问题

窗口内的连续扩展会被宿主接受，即使新增文字含有独立条件、否定或时间，冻结字段仍可保持旧值。提示语要求模型退回原陈述，宿主没有第二道判定。采用前 `validate_completed_quote_review`（1377–1385）要求扩展索引重核全文或保持未决。这只证明字段未改，不证明医学含义未变。

`source_unit_quotes_cover_source` 使用 `allow_joining_punctuation=True`（358–360）。`source_statement_ranges_cover_unit` 因此把逗号也当可跳过连接符（`protocol_control_gate.py` 5131–5152）。纯标点间隙可以不算遗漏；带实词的条件句仍会失败并触发补读。表格显示用 ` | ` 只有在正文恰好由冻结成员拼出时才豁免，字面竖线仍失败。作者前和带 `final_output` 的保存侧共用该函数。

额度按历史重算时，只要求历史最后一条等于最后一次尝试（2884–2886）。正常检查点写入完整历史。若 `source_scope_question_history` 被截成只剩最后一条，而更早的已调用补读仍在 `attempts`，已用次数会被少计。

带 `eligibility_sequence_context` 的单元不进入 `missing_sequence_source_units`。作者前和 `final_output` 保存侧使用同一排除。本轮没有逐行审 `validate_table_sequence_context`，不能证明表格上下文路径会捕获单元尾句。

### 异议、改法和决定点

异议：把 `same_restricted_source_and_current_gate` 当作本捕获标准已复验，依据不足。重建受限批次只证明旧受限投影仍能算出来，没有证明先决正文已被完整捕获。

改法：在受限复用、检查点重放、`preserve_unresolved` 完成，以及「已有作者证明就跳过作者前补读」之前，调用同一个 `missing_sequence_source_units`。名单非空时丢掉作者草稿和核对证明，走现有的 `source_unit_quote_completion_required` 种子；保留历史，额度继续用 `min(当前上限, 种子上限)`。被拒绝且当前仍有缺口的补读维持硬停止。3112–3118 的缺口应改为整批 `missing_sequence_source_units`，不要只取未决索引所属单元。不要因此退回整批重读。

决定点：已经完成并可能被下游见过的受限检查点，发现尾句缺口后，是局部补读后重新核对，还是把检查点判为当前门禁无效并停止自动恢复。本轮建议局部补读。若这些检查点已经对用户呈现为完成结果，Codex 需要先决定能否自动重开。

有界问题：校验器升到 `source-sequence-preauthor-capture/v1` 后，受限完成回执是否仍允许 `decision=reusable`？这决定上述缺口是缺陷还是有意排除。确认前的安全暂定是：不要把含序列缺口的受限回执标成 `reusable`，也不要整批重读或重置额度。

### 未完成边界

本轮没有运行测试、模型、数据库或浏览器，没有读 `.env`、原始产物或真实方案。临床链、视觉和正式采用均未验收。材料捕获通过不等于医学语义通过。
