我先读会议上下文和主会场计划，再按允许的源文件核对权限/豁免的生产端与消费端语义。上下文里的来源清单还是空的。我按合同只查允许的定义文件，核对权限与豁免从生产到消费是否会被当成必须完成。门禁会在没有「建议」措辞时拒绝 `recommended`。还差可选操作的合法编码，以及评估结果的最终消费方。# Conference Output: rv1006-permission-consumer-review-20261011 - evidence_single_object

## Output

权限和豁免已经有落点。当前失败是生产者把它们写成了 `modality=recommended`，门禁在保存前按原文没有「建议/推荐」而拒绝。这不是缺一种新语气，也不是把 `recommended` 改成 `mandatory` 就能对齐。最终是否把「没做可选动作」判成资格失败，这一层消费端正文还没读完，不能当成已经安全。

本轮只读，未改文件，未跑测试，未读临床原文、原始模型响应或环境。定义阅读 8/8 已用完。下文不构成临床或监管接受。

### 证据

生产者合同在 `app/agents/protocol_control_deconstructor.py`。

- 复查许可在 `repeat-scheme/v4`：`trigger_condition_id` 指向旁置触发条件；只有原文明确要求研究者许可时才填 `permission_condition_id`。`optional` 或没有复查记录，不能推出仍采用初查，也不能推出复查没做或资料齐全（约 2025–2055 行）。
- 「可进行/允许进行」是可选操作，陈述里要留下可选语气，次数上限照原文字保留。「无需/不要求执行」是豁免，不是禁止。豁免若受结果有效期限制，同一义务组并列两个原子：`verify_result_validity` 独占 `time_constraint`，不带时间约束的 `complete_or_verify` 只表示免予状态。最低证据只证明有效期成立，不要求证明被免操作没有发生（2125–2132 行）。
- `modality=mandatory` 的定义是明确必做。`recommended` 只用于原文「建议」或同义措辞，`best_effort` 只用于「尽可能/尽量/尽力」。建议项没有记录时，不得单独写成证据不足（2142–2154 行）。
- `_repair_problem_guidance` 对 `RECOMMENDED_MODALITY_` 的回复是：有「建议」才用 `recommended`，没有该措辞不得升格（2738–2741 行）。它没有把被拒候选指回 `RepeatScheme.permission=optional` 或豁免原子对。豁免路径写在另一支 `CONDITIONAL_EXEMPTION_BINDING_MISSING`（2770–2777 行），可选语气写在 `OPTIONAL_ACTION_MODALITY_DROPPED`（2724–2729 行）。这两支都不会在 `RECOMMENDED_MODALITY_UNSUPPORTED` 时触发。

合同在 `app/domain/contracts/repeat_scheme.py` 105–110 行：`permission` 已是 `required | optional | forbidden | investigator_discretion | unresolved`。`investigator_discretion` 才强制 `permission_condition_id`。义务模态默认是 `mandatory`（解构草稿约 666 行；`protocol_controls.py` 约 947、1042 行）。

门禁在 `app/protocols/protocol_control_gate.py`。

- `_RECOMMENDED_CUE_RE` 只认「建议|推荐|recommended|recommend」（425 行）。有该措辞却不是 `recommended`，报 `RECOMMENDED_MODALITY_DROPPED`。没有该措辞却是 `recommended`，报 `RECOMMENDED_MODALITY_UNSUPPORTED`（2704–2728 行）。缺失模态按 `mandatory` 处理。
- `_OPTIONAL_ACTION_CUE_RE` 只认「可(以)进行/重新筛选/复查/复测/检查/检测/评估/记录」「允许」加同样动词，以及英文 `may perform|repeat|test|assess|record`（409–420 行）。摘录里有这些词、陈述里没有，才报 `OPTIONAL_ACTION_MODALITY_DROPPED`（2288–2295 行）。这个检查不看 `modality` 枚举。
- 因此「允许复查」可以带着默认 `mandatory` 通过可选语气检查，只要陈述里仍有「允许复查」。英文 “permitted” / “may be waived” 打不中这条英文正则，也打不中建议正则。

已定位、但未读完的消费端：

- `compose_control_layers`（`app/domain/control_layer_evaluation.py` 80 行）按适用、触发、义务、例外四层组合原子真值，并把 `modality` 抄到结果上。结果模型有一处注释：该合取是描述，不是资格阻断（约 44 行）。函数在收集原子身份之后的正文没有读。
- 调用方只看到两处：`app/services/control_history_search_calculation.py` 40 行，`app/projections/control_calculation_experiment.py` 428 行。两处如何把层真值或模态变成资格结论，没有读。
- 对齐匹配里有一条旁证：`app/agents/protocol_control_candidate_alignment.py` 538 行，`permission == "optional"` 且 `statement.force` 为 `required` 或 `prohibited` 时该匹配返回假。函数全貌没读。当前失败发生在对齐之前，这条匹配还碰不到那 8 次被拒调用。

### 推论

两条合成句都不应占用 `recommended`。

1. 达到排除界值后，复查至多两次、复查前不得对症处理、正常复查才允许继续。这是条件复查的许可和结果采用：触发条件、`permission=optional`、次数上限、复查前限制、正常复查作为排除例外。没做复查时，排除仍然成立。这和「漏做一项必做操作」不是同一件事。
2. 再筛选时，有效期内已完成的检查可以免做。这是同一义务组里的有效期原子加免予原子。免予成立只取决于有效期，不取决于把免掉的检查再做一遍。

模型若把「可/允许/可免除/permitted/waived」当成「建议」的同义措辞，门禁会正确拒绝。修复提示只说「不要升格为建议」，没有指回已有字段，下一轮就容易落回默认 `mandatory`。按生产者自己的定义，`mandatory` 就是明确必做。可选语气只留在句子里、模态仍是必做，正好会把许可写成必须完成。

门禁拒绝本身是对的。错的是归档槽位和修复指引。

### 建议

只改生产者提示和 `RECOMMENDED_MODALITY_UNSUPPORTED` 这一支修复文案。门禁继续拒绝没有「建议/推荐」的 `recommended`。不要把许可改成 `mandatory`，不要放宽建议正则，不要新增模态、表或疾病专用提示。

提示里与 2125、2145 行相邻的位置写明：可、允许、无需、可免除、may be waived 不是建议强度。复查许可写入 `repeat_scheme.permission=optional`，次数照原文；有效期免做写入已有的 `verify_result_validity` + `complete_or_verify` 同组原子。两处都不得改成必须完成该可选动作。

修复函数把 `RECOMMENDED_MODALITY_UNSUPPORTED` 从笼统的 `RECOMMENDED_MODALITY_` 拆出来。原文是许可或豁免时，去掉 `recommended`，改走上面两个已有结构；禁止补写「建议」，也禁止改成无条件必做。

消费端和界面先不动。

尚未执行、授权后才能做的核对：

- 正例：原文「建议」，模态 `recommended`，无记录不单独成为证据缺口。
- 等价：原文「允许复查至多 2 次」，`permission=optional`、`maximum_repeats=2`、陈述保留「允许复查」、模态不是 `recommended`。不出现 `RECOMMENDED_MODALITY_UNSUPPORTED`，也不出现 `OPTIONAL_ACTION_MODALITY_DROPPED`。没做复查只保留原排除，不另判一项操作未完成。
- 反事实：同一许可句使用 `recommended`，仍是 `RECOMMENDED_MODALITY_UNSUPPORTED`。
- 失败：把「允许复查」写成陈述中没有可选语气的无条件必做，出现 `OPTIONAL_ACTION_MODALITY_DROPPED`。
- 豁免正例：有效窗与「无需再次检查」同组并列，模态不是 `recommended`。窗内旧结果成立且没有重做时，免予成立。
- 反事实：免予原子使用 `recommended` 且原文没有「建议」，仍然被拒。

### 不确定

- `compose_control_layers` 后半段，以及两个调用方怎样把义务为假变成资格结论，没读。因此不能证明：正确保存之后，没做可选复查一定不会变成资格失败。
- `_EXEMPTION_MODALITY_RE` 没读。「可免除 / may be waived」是否已经能打中豁免门禁，未知。可选动作正则不覆盖 “permitted” 和 “waived”。
- `statement.force` 的允许取值，以及它是不是最终展示力量，没读。
- 界面没有纳入本次阅读。未读消费端保持未决，不把未决写成缺陷，也不写成安全。

### 异议、决定点、有界问题

最高异议：把这次拒绝解释成「建议模态太严，改成必做或让可/允许也算建议」。建议正则和许可正则是分开的。许可不是advice。放宽建议正则，或在修复时改成 `mandatory`，都会把可选动作变成必须完成。

第二异议：可选动作门禁只查陈述措辞，不查模态。这是真实空洞，但现在就规定「一见可/允许就禁止 `mandatory`」会误伤别的原子。许可可以写在 `RepeatScheme` 上，同候选里另有真正必做原子。这条门禁要等消费端读完再定。

第三异议：8 次调用停在累计额度、没有采纳，说明失败是保存前拒绝。此时改消费端没有被拒样本可以对照。

决定点：本轮若授权修改，范围只限主提示加 `RECOMMENDED_MODALITY_UNSUPPORTED` 修复支。门禁接受条件和消费端都保持原样。

请 Codex 只回答这两点：

1. 那 8 次被拒候选，是否就是义务 `modality=recommended`，且摘录含可/允许/免除/permitted/waived，而不含建议/推荐？本次按错误码和正则推出这个形状，但按边界没有读原始响应。
2. 是否授权同会话再读 `control_layer_evaluation.py` 80 行至文件末，以及 `control_calculation_experiment.py` 428 行附近的层真值绑定？在此之前，安全路径是不改消费端、不把许可改成必做。

若额度在此截断，恢复点就是上述两个读段，加上 `protocol_control_candidate_alignment.py` 520–549 行所属函数名。
