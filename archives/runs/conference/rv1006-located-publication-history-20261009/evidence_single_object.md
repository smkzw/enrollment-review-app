我先按冻结审阅合同读会议上下文和这六份补丁的 diff，只核对定位失败反馈、无效重试停止，以及成功来源的原答恢复。六文件相对 `d57cb647` 的未提交 diff 已对齐。接下来只读三个模块里改过的定义和调用点，核对指纹、修复范围和历史原答恢复。# Conference Output: rv1006-located-publication-history-20261009 - evidence_single_object

## Output

相对 `d57cb647` 的未提交六文件补丁（`+128/−6`）里，有两处必须修。单条已定位的条件映射失败，在候选身份改写后可以被停住；但门禁新写入的 `structure_unit_ids` 被当成了修订授权，会把同一候选的其余冻结单元挤出修订范围。只要同一次错误里还有一条没有路径的发现，定位指纹就整单退回原文哈希，候选身份一变，同一处已定位缺陷又会继续空转。

本轮只读，未改文件，未跑测试，未打开临床原件或私人运行目录。提示里的「受影响窗 29 通过」和「三模块全窗仍在跑」都不是本轮观察。

### 证据

工作区 `HEAD` 就是 `d57cb647eefb172b08ed0cf85c45d3a9cff38a52`。约定的六个文件都是未暂存修改，行数与冻结合同一致。同工作区还有大量与本包无关的既有改动，未纳入本轮。

条件失败新增的是定位字段，不是新的通过条件。`_check_conditional_branch_mapping` 仍在「触发组摘录没有任何一条落在该条件句里」时失败。新代码把该句所在结构单元和固定路径 `/trigger_expression/groups` 写进 `ProtocolControlGateError`，并把整句放进消息（`app/protocols/protocol_control_gate.py`，约 2156–2166 行）。调用点传入的 `units` 是该候选自己的来源范围（同文件约 4176–4234 行）。因此这些单元是 `frozen_structure_unit_ids` 的子集，`publication_repair_error` 不会因此把范围标成未知。

修订授权用的是同一组单元，不会在单元为空时再扩回整段冻结闭包：

- `publication_repair_error` 只有在 `issue_structure_unit_ids` 为空时，才补上 `candidate.frozen_structure_unit_ids`（`app/protocols/protocol_control_repair_errors.py`，约 161–171 行）。门禁一旦写入子集，这一步被跳过，错误上的 `structure_unit_ids` 只剩条件句所在单元（约 188–190 行）。
- 运行器把这组单元写成 `mutable_structure_unit_ids`（`app/agents/protocol_control_deconstructor.py`，约 10294 行）。
- 有线恢复时，不在这组单元里的处置被悄悄换回上一轮失败稿（约 5088–5093 行）。
- 水合结果若改了这些单元以外的处置，`_validate_bounded_output_repair` 抛 `REPAIR_SCOPE_ESCAPE`（约 4937–4994 行）。运行器见到该码即停止自动修订（约 10682–10707 行）。
- 修订提示的「结构单元范围」和授权原文只渲染这组单元（约 3092–3106 行）。`json_path` 会进入 `validation_findings` 和提示，但本错误码不会走进未来禁止、原子、时间操作数那类路径锁。`/trigger_expression/groups` 也不符合 `_future_prohibition_finding_paths` 要求的 `obligation_expression.groups.{i}.atoms.{j}...`。

定位指纹在 `_located_publication_failure_identity`（约 6974–6988 行）。它在 `repair_scope_unknown`、没有发现、或任一发现缺 `structure_unit_ids` / `json_path` 时返回 `None`。返回值只含 `code`、`json_path`、排序后的结构单元和 `obligation_source_span_ids`。条件句原文、`entity_id`、候选身份都不在里面。门禁这条失败也不写 `obligation_source_span_ids`，所以跨度恒为空；路径对所有未对应条件句都是 `/trigger_expression/groups`。

实际停机键是三元组（约 9991–9996 行）：定位身份，否则原文 `sha256`；然后是 `error.code`；然后是 `str(validation_error)[:2000]`。`publication_repair_error` 的消息是 `issue.code: issue.message`，不拼 `entity_id`。本条门禁消息含条件句、不含候选身份。因此「只有这一条完整定位发现、消息不变、仅标题或候选身份变化」时，原文哈希被换掉，第二次应写入「连续返回相同无效结果…停止自动修订」。测试 `test_located_publication_defect_does_not_reset_when_candidate_identity_changes` 构造的就是这一条路径。本轮没有执行它。

`check_protocol_control_batch_candidates` 按候选各收第一条门禁错误（`protocol_control_gate.py`，约 5249–5268 行）。同函数里「分支被复用」和 `CONDITIONAL_BRANCH_CONSEQUENCE_MISSING` 仍不写单元和路径。

成功检查点把非空的 `result.source_scope_question_history` 写在顶层，不写进 `run_result`（`app/services/protocol_control_execution.py`，约 4389–4394 行）。`ProtocolControlAgentAttempt.raw_output_text` 与 `ProtocolControlAgentRunResult.source_scope_question_history` 都是 `exclude=True`（`protocol_control_deconstructor.py`，约 4299、4320–4322 行），所以 `run_result` 的 `model_dump` 不含原答，也不含这份历史。`build_result` 在序列化后再把 `raw_output_text` 放回历史字典（约 7101–7107 行）。`_deep_attempt_raw_outputs` 对主尝试不写 `role`，只给两类定义登记尝试写角色（`protocol_control_execution.py`，约 4399–4428 行）。

旧账没有顶层历史键时，加载器在「有 `run_result` 且顶层没有 `attempts`」时走嵌套恢复：`role is None`、`attempt`、`session_id` 必须恰好一行，再核对 UTF-8 `sha256` 与 `raw_output_chars`。缺失、重复、唯一行被标成外来角色、长度或哈希不符都会抛错。测试证明该函数不改写入参。顶层历史键只要存在，加载器直接返回，不再做这组核对。恢复进运行器时，只在原答非空时核对哈希，不核对长度（约 7243–7254 行）；原答为空的已解析记录不会进入 `seen_questions`。

`validator_version` 末尾新增 `located-publication-recovery/v1`。`_same_deep_components_with_current_gate` 比较时忽略整个 `validator_version`。加载器不回写旧检查点。

### 推断

必须修 1：有类型的单元反馈把候选修订收窄错了。

反例：候选冻结单元是 `(su-A, su-B)`，未对应条件句只在 `su-A`。门禁现在给出 `structure_unit_ids=(su-A,)`。这是冻结单元的子集，修订范围仍算已知，但授权从原来的整段 `(su-A, su-B)` 变成只有 `su-A`。后果有三：

1. 默认全量修订提示不再给出 `su-B` 的授权原文。传输层没有 `continue_candidate` 时，也不会附上候选原稿。
2. 模型若在补触发分支时改了 `su-B` 的处置，水合校验抛 `REPAIR_SCOPE_ESCAPE`，本批直接停止，不再给下一次修订。
3. 有线恢复会把 `su-B` 的处置悄悄换回上一轮失败稿，模型对 `su-B` 的处置修改留不下。

候选来源键仍可能让整份候选草稿被替换，所以触发组本身不一定被路径锁死。锁住的是同候选其余单元的处置和提示里的原文。`json_path` 没有单独造成这道机械锁。修复应把单元和路径留在定位发现里，修订授权继续用该候选的完整冻结单元。

必须修 2：候选身份变化仍会掩盖同一条已定位缺陷，只要指纹被整单作废。

反例：候选 1 是带单元和路径的 `CONDITIONAL_BRANCH_MAPPING_INVALID`；候选 2 是同批收集到的另一条没有 `json_path` 的门禁错误。`_located_publication_failure_identity` 看到任一发现不完整就返回 `None`，三元组退回整段原文 `sha256`。两份回答只改标题或生成的候选身份时，哈希不同，`no_progress` 不触发，剩余修订预算会继续消耗。同函数里未写单元和路径的「分支复用」与「后果未绑定」也仍走这条退路。

单一完整定位发现、消息稳定时，候选身份不进入指纹。这一条本身不会再被身份改写掩盖。现有测试只覆盖这一条，覆盖不到必须修 1 和必须修 2。

不同未对应条件句：同一单元、同一路径、空跨度时，定位身份相同。当前复合指纹仍把条件句放在消息前 2000 字里，单条失败会先报第一句，所以普通的两句不同条件不会被当成同一次失败。定位身份单独使用是不够的。前 2000 字相同、差异落在截断之后的后随条件，会被提前停掉。

成功原答：新检查点在历史非空时把含原答的私有历史放在顶层；公开 `run_result` 不含该字段和 `raw_output_text`。嵌套旧账的缺失、重复、外来角色、哈希和长度拒绝与代码一致。外来角色行只有在它是唯一匹配行时会被拒绝；旁边另有一行无角色的同尝试记录时，外来行被忽略。这与「主尝试无角色、登记尝试另有角色且可共用尝试号」的写法一致，不应当成缺陷。

旧检查点文件不会被加载器改写。新的深析检查点会多出历史键（仅非空时）和更长的 `validator_version`。已核到的恢复比较函数忽略该版本字段。

### 建议

1. 门禁可以继续把条件句、单元和 `/trigger_expression/groups` 放进发现与消息。`publication_repair_error` 在单元只是候选冻结闭包的真子集时，修订用的 `structure_unit_ids` 仍应扩展为完整 `frozen_structure_unit_ids`。不要让定位子集变成 `mutable_structure_unit_ids`。
2. 定位身份加入规范化条件句，或该句的稳定哈希，不要只靠消息前 2000 字。已定位的发现按自身身份计数；旁边有一条无路径发现时，不要把整单退回原文哈希。
3. 顶层历史键也做与嵌套恢复相同的尝试号、会话、角色、哈希和长度核对，避免两条加载路径标准不同。
4. 补测试：多单元候选不得因只定位到其中一个单元而 `REPAIR_SCOPE_ESCAPE`；一条已定位缺陷加一条无路径缺陷，候选身份变化后仍须第二次停止；同单元两句不同条件不得共用同一停机键。

不建议顺手改发现循环、源语义或其他门禁码。那不是这次六文件交付里已经发生的收窄。

### 不确定性

- 未运行 `pytest`，不能确认那 29 个用例或三模块全窗的结果。
- 未读候选身份生成函数。掩盖判断只依赖「身份退回时使用整段原文哈希，而标题在原文里」。
- 未打开历史检查点。不能证明线上是否已有「疑问尝试只在 `run_result.attempts`、且 `attempt_raw_outputs` 对不上」的旧账。代码上，这种旧成功检查点以前会得到空历史并继续，现在会抛「历史原答缺失或重复」或「与回执不一致」。
- 未逐一核对模块外是否有人按完整字符串比较 `component_identity`。已读的 `_same_deep_components_with_current_gate` 不比较 `validator_version`。

### 异议、决定点与给 Codex 的问题

最重要的异议是：把「这句话在哪个单元」写成门禁的 `structure_unit_ids`，在现有 `publication_repair_error` 里等于缩小修订授权。这和「只给模型更准的失败反馈」不是同一件事。第二异议是：定位指纹用「全部发现都必须可定位」做开关，一次混合失败就会回到「改个候选身份就看起来像有进展」。

决定点：定位单元是只进入发现，还是允许作为修订授权。建议只进入发现；修订授权保持该候选的完整冻结闭包。

安全的临时路径：在这点决定之前，不要把当前补丁当成已经同时完成「准确定位」和「不缩小修订」。单一发现上的停机可以保留；多单元授权和混合发现的停机还不能算成立。

有界问题：是否存在已保存的深析检查点，其来源疑问尝试只在 `run_result.attempts` 中，且没有能按尝试号、会话、空角色、哈希和长度对上的 `attempt_raw_outputs`？若有，当前加载器会把原先的空历史恢复变成硬失败。本轮按边界没有打开私人运行目录，无法替 Codex 回答。若这类旧账必须继续跑，缺账时应保持旧的空历史，只有账本存在但不一致时才拒绝。
