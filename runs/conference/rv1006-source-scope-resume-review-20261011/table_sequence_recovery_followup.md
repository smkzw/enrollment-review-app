收到 C03 接续审阅（来源顺序局部核对）。只读、不改文件、不委派（Trellis 任务与本次只读边界不符，不创建）。先定位新符号与测试。

核心已读：`source_question_context_identity`（`:641-648`，身份由上下文/表位置派生、与顺序字段无关）、`can_recheck` 新分支（`:673-677`）、`apply` 三字段冻结（`:768-801`）、`POST_ELIGIBILITY_ACTION_AS_CONTROL` 仅在有完整 witness 时授权（`:8890-8903`）、三支新测试。最后 1 次读取核服务恢复侧的历史身份检查。

# Conference Output: rv1006-source-scope-resume-review-20261011 - evidence_single_object

## Output

只读审阅（8 次工具已用满：4 定位＋4 读取）。未改文件、未运行产品模型、未读临床原件/私有目录/DB/env、未委派（Trellis 任务/计划文件与只读边界不符，未创建）。合成 JUnit 与前 98 窗、47/1/1/41 预检数字均为宿主提供，未复核；**不称临床采用/启用/签发，不称真实 49 已恢复**。独立性折减：审阅者与产品同属 DeepSeek 模型家族，仅适配器/上下文不同。

---

### 1) 新问题范围（can/build/apply）

**[代码事实] 与描述一致**：
- `can_recheck_source_scope_question` 新增顺序分支（`protocol_control_source_interpretation.py:673-677`）：仅当 `eligibility_sequence=="current_or_unknown"` ＋ `eligibility_sequence_context is None` ＋ `"action" in decision_functions` ＋ `_source_question_table_sequence_locations`（同文档同表物理位置，`:651-656` 调 `table_sequence_context_locations`）非 None 时放行；旧路径（local_context/official，`:678-693`）不变。
- 提示只在该分支给出字段权限（`:707-722`："只可修改eligibility_sequence、…quote、…context"，"证据不足则保留current_or_unknown及两个空字段"），其余字段逐项原样（`:712-713`）。
- `apply_source_scope_question_recheck`（`:768-801`）：先过 `can_recheck`（`:773`），`allowed` 按序严格三选一（序列三字段/原生范围四字段/仅 unresolved，`:782-784`），`exclude=allowed` 的逐字段相等保证逻辑、时间、例外、unresolved 冻结（`:785-787`）；`after` 必须带完整 witness（`:788-789`）；最后整体 `validate_source_interpretation`（`:800`）。
- 反例：`question_cannot_change_other_semantics` 六参数（force/quote/times/exception/unresolved/missing_witness，测试 `:3971-3992`）全部 `ValueError`。**结论：未知不猜、语义冻结成立。**

### 2) context 身份在 before/after 保持

**[代码事实] 成立**：`source_question_context_identity`（`:641-648`）= sha256(official_context ＋ table_sequence_locations)，两者均由**冻结 batch/单元**派生，不含顺序字段 → 问答前后同值。测试显式断言 history 身份 == 原陈述身份 == 提案陈述身份（`:3958-3959`）。账本记录与兼容检查分别在 deconstructor `:8404`（记录）与 `:7793`（复用兼容）引用同一函数（两处均只定位、未读上下文，见 §5 证据不足）。

### 3) 旧 question 兼容与重启

**[代码事实]**：runner 级恢复携带 `resume_source_scope_question_history=history` 时不再发问（测试 `:3963-3968`：`again.questions == 0`、`final_output` 非空）；"只问一次"由状态自然闭合（答后 witness 存在 → `can_recheck` 新分支条件不再满足），非新增计数器。累计预算仍复用（同一 `max_source_corrections` 账，`execution.py:2648`）。
**[不确定→必修核对] 服务侧种子证明的旧/新历史门**：`_revalidated_source_seed_proof` 对非标题问答要求 `error_detail.json_path == f"statements[{index}].unresolved"`（`protocol_control_execution.py:2656-2661`），并校验 `source_context_sha256`（`:2660`）与 `precondition_sha256`（`:2661`）。**若顺序问答按新字段记录 `json_path`（如 `…eligibility_sequence_context`），该门会直接 `return None`**——这正是你问的"第一因果缺口"：服务恢复无法复用这次问答，退回 refresh/重读（非错误采用，但有成本）。若生产者为兼容记成 `unresolved`，则门能过但记录路径名不符实。**必修项（见 §5）**：读实际记录点（deconstructor `:8404` 附近）确认 `json_path`/`code`，必要时把该分支扩为接受顺序路径（语义仍由共享的 `apply_*` 冻结把关，`:2668`），或改用独立 `code`。新增测试 `test_table_sequence_question_restores_only_source_relation_and_survives_resume` 只覆盖 runner 级 resume ＋ `_validate_saved_source_review`（`:3961`），**未覆盖** `_revalidated_source_seed_proof`，故该缺口不会被现有测试发现。

### 4) 局部删除范围与 fresh 核查

**[代码事实] 授权边界正确**：`POST_ELIGIBILITY_ACTION_AS_CONTROL` raise 现在附带 `allow_source_closure_rewrite=witnessed_sequence` 与 `allow_post_enrollment_reclassification=witnessed_sequence`（`deconstructor.py:8893-8903`），而 `witnessed_sequence` 要求**全部**冲突陈述都带完整 witness（`:8890-8892`）→ 无 witness 或部分 witness 时两个授权均为 False，"原无 witness 路径不扩权"成立。
**[代码事实] 端到端**：`test_table_sequence_resumed_candidate_is_locally_reclassified_then_freshly_reviewed`（`:3995-4047`）证明：恢复旧 candidate → 单条来源问答 → `continue_scoped_unit_repair` 恰一次且 `owned_structure_unit_ids == ["su-01"]`（`:4029`）→ `continue_session` 被禁止（`:4032-4033`，"不允许整批重读"）→ 终态候选清空、fresh 目标核对含 `non_control_sequence_context`（`:4045`）→ 保存读回通过（`:4046`）→ 原解释/线稿字节未变（`:4047`）。仅改来源闭包与处置，不凭 `after` 取消未核义务（unresolved 冻结于 `:785-787` 且六反例覆盖）。
**[证据不足]** splice/兄弟保护沿用既有 `_restore_bounded_wire_repair` 通道（前轮已核），本轮未重读；"只对应未改数值阈值"未在本次路径中读到任何数值原子变更（C03 数值守卫与本路径正交），列为推断。

### 5) 必修 / 建议 / 证据不足（含位置）

**必修（先核对，非要求新框架）**
- [P1 候选] `execution.py:2656-2657` 的 `json_path=="…unresolved"` 门与顺序问答记录字段是否一致；不一致则 `_revalidated_source_seed_proof` 对新真实历史返回 None（第一因果缺口）。最小修复：在非标题分支接受顺序问答路径/专用 code（应用侧冻结已由共享 `apply_source_scope_question_recheck` 保证，`:2668`），或统一记录字段。位置：`deconstructor.py:8404` 附近（记录点，未读）＋`execution.py:2656-2661`。

**建议**
- 补一条服务级用例：顺序问答历史经 `_revalidated_source_seed_proof`（而非仅 runner resume）可复用；并加一条旧格式历史（缺 `source_context_sha256`）行为断言（现 `:2660` 会 `None != identity` → 拒绝 → 回落 refresh），确认这是期望而非意外。
- 顺序问答的 `json_path`/`code` 语义在提示（`:712`）与账本（`:8404`）间保持单一事实，避免"路径说 unresolved、权限说 eligibility"的双重叙述。

**证据不足**
- `deconstructor.py:7770-7830`（`:7793` context_compatible 的完整逻辑）与 `:8380-8430`（`:8404` 记录点）未读；这是 P1 判定的关键两处，也是"旧 question 兼容"的完整证据。
- 前 98 窗 exit0、最新恢复例 1pass/3.42s、fixture `complete_action`→`complete_or_verify` 修正未复核（宿主提供；同意"生产合同未放宽"需以未读的 diff 为准）。
- 未读 splice/sibling 内部本轮；未读数值阈值路径。

**同模型家族折减**：以上为源码合同级审阅，不构成医学批准，也不替代完整 1006V1；真实 49 恢复仍不宣称。**给 Codex 的有界问题**：Q1 记录点的 `json_path`/`code` 实际值？Q2 是否授权按 §5 必修做最小对齐（若需改动，仅 `execution.py:2656-2661` 与记录点，不新框架）？
