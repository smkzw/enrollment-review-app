同角色增量审阅（完成回执可追踪性分离）。先定位新增函数与三处消费者的实际名称与行位。

函数已定位：新函数 3488，未来路径 3508，三处消费者在 1247 / 3338 / 3769。继续读取完整定义与消费现场。

关键发现线索已出现（`_replay_checkpoint` 处 1244-1245 用的是**精确** component_identity 比较，而非 `_same_deep_components_with_current_gate` 的 validator 容忍比较）。继续读三处消费者与两个新测试。

三处消费者已核。继续读两个新测试、旧负例与 `_replay_checkpoint` 的调用条件，并补 `_validate_saved_source_review` 覆盖范围。

三处消费者与两个新测试已核。最后一组核对：定义消费门与保存结果形态校验落在哪个函数。

最后一读：`_validate_saved_source_review` 余段，确认 coverage/alignment/definition 门与 3716 分支。

# Conference Output: rv1006-pending-author-review-20261010 - evidence_single_object

## Output

### A. 已读证（当前文件，非旧提交）

**新函数与旧函数（读全）**
- `_completed_repair_receipt_traceable`（3488-3505）：形态门 + 64hex。条件：`run_result` 为 Mapping、`repair_used` 为 bool、status ∈ {已解析,待跨章核验,需要核对}、`final_output` 为 Mapping **或** `restricted_batch` 为 Mapping；`repair_used=False → True`；否则仅要求 `repair_contract_sha256` 是 64hex。无版本白名单、不比对当前合同、不核 attempts/error_classes。docstring 3489-3494 明示"历史措辞是证据、不是当前结果校验器；失败提案续读仍须匹配补答材料"。
- `_repair_material_matches`（3508-3547）：未变。当前合同精确匹配 → True；三个旧合同 hash 且 attempts 的 error_classes 与各自"受影响集合"相容 → True；未知 receipt → False。旧负例测试（6635-6719）逐条覆盖这一行为，并断言合同措辞变化后旧 receipt 由 True 变 False（6653-6654）——未来/失败路径未被新函数接管，读证成立。

**三处消费者（读全消费者段）**
1. `_replay_checkpoint` deep 分支（1218-1299，调用点 1247）：batch_id/prompt sha/**component_identity 精确等值**（1244-1245）/transport identity 精确 + traceable（1241-1247）→ `_saved_deep_run_result` + 定义登记一致性（1252-1261）→ restricted 分支 `expected==saved` + `_validate_deep_batch_output`（1269-1274）或全量分支 `_validate_saved_source_review` + `_validate_deep_batch_output`（1276-1279）+ 来源刷新（1280）+ 待核状态/关联一致性（1284-1293）。
2. `_preflight_deep_source` 完成分支（3268-3384，调用点 3338）：route（3276-3287）/prompt 形态（3288-3290）/结果形态（3291-3297）/组件键集与摘要形态、v2/v3 下 repair_hash 64hex（3298-3316）→ batch/prompt/permissive 组件比较（3317-3337，`_same_deep_components_with_current_gate` 3322-3336 对 validator 漂移容忍）→ traceable（3338-3345）→ 受限路径 `expected==saved`+刷新（3349-3366）/全量路径 status+final_output（3368-3369）、`_validate_saved_source_review`（3371）、`_validate_deep_batch_output`（3377）、来源刷新（3381）→ 仅全过才 `reusable`（3384）。
3. `_validated_deep_source`（3724-3801，调用点 3769）：permissive 组件（3765-3768）+ traceable（3769）+ transport 精确（3770）；结果形态 3773-3786；受限路径（3776-3784）；全量路径 refresh（3787）+ 两道当前门（3790、3794）。

**当前门覆盖**：`_validate_saved_source_review`（3550-3721）读证含 SourceInterpretation（3564）、前置/逐项来源核对（3565、3573-3641）、SourceTargetReview（3642-3651）、evidence-policy 与 alignment 证明（3652-3715）、**定义消费门（3716-3721：有定义陈述必须存在登记回执，否则 raise；存在则 `validate_source_definition_consumers`）**。即三处消费者的全量路径都实际执行 owner 声称的全部门。

**调用条件（决定可达性）**：执行器 1107-1135——非诊断、非 failure 阶段的 `last_checkpoint`（含 stage="deep"）且非 scope/hydrate/gate 步 → 直接 `return _replay_checkpoint(...)`，无回退 `_execute_deep`；失败即 `CHECKPOINT_INVALID`（retryable=False）。另外 1109-1114：job payload 的 execution_version 与当前不符则整包拒绝（"从方案整理建立新任务"）。

**测试（读全）**：test 1（4046-4157）覆盖：修复发生在原始会话、attempts=[parsed,publication_invalid,parsed]、`repair_used=True`、raw 回执与 attempts 分存（4114-4120）；改合同措辞后新 Job 预检全 `reusable`（4136）、消费零新读取（4138）、旧 checkpoint 逐字节不变（4140）；当前门变严 → 计划全 `current_gate_requires_refresh`（4156）且零调用（4157，未 run_job）。test 2（6722-6751）：`repair_contract_sha256="broken"` → 预检硬失败 `DEEP_SOURCE_INVALID`（触发点在 3313-3316 的形态校验，早于 traceable），零新读取。

**新 validator 身份**：2113 `completed-result-current-gate-revalidation/v1` 位于 `_deep_component_identity` 的 validator_version 连接串内（2115 收尾）。

---

### B. 核心问题的直接回答

**是否漏掉不可由当前来源/含义校验重验的补答来源或权限边界？** 在当前读证范围内：**未发现可用于"绕过采用"的缺口**。历史补答权限（当时的合同措辞）确实被有意降级为证据；替代它的"当前门重验"在三处消费者的全量路径真实执行（A 已逐条读证），且 restricted 路径不产生采用。**但存在一处门强度不一致（F1）和若干非采用面的差异（F3/F4），以及明确缺失的回放测试（F5）。**

### C. 缺陷按严重度

**F1 · 中（条件性；fail-closed，非绕过）· 消费者1的身份门与另两处不一致**
`_replay_checkpoint` 1244-1245 对 `component_identity` 用**精确等值**；消费者2/3 用 `_same_deep_components_with_current_gate`（3330、3765-3768，validator 漂移容忍，2122-2136 已读）。若 2113 的 `completed-result-current-gate-revalidation/v1` 为本增量新增（owner 描述如此），则更早写下的完成检查点 `validator_version` 必不同；一旦这类检查点走到 `_replay_checkpoint`（崩溃恢复窗口：步骤被重执行而 last_checkpoint 已是完成 deep 状态；调用路径 1115-1135 已读），会在 traceable 与当前门**之前**以 `CHECKPOINT_INVALID` 拒绝——完成结果在该路径依旧不可用，与"完成结果过当前门即可复用"的目标自相矛盾（且该函数自己随后就用当前门重验，1244 的精确比较与其自身语义冲突）。
- 必要具体条件：(a) 2113 字符串新于现存完成检查点；(b) 该检查点所在 job 仍能通过 1109-1114 的 execution_version 门（即改动未同步 bump execution_version）。
- 最小验证（一个聚焦测试即可定案）：取 test 1 的完成 checkpoint，将 `component_identity.validator_version` 替换为任一旧值，走 `_replay_checkpoint`/执行器回放分支——预期（方案语义）应通过当前门并回放成功；当前代码预期 `CHECKPOINT_INVALID`。
- 最小修复：1244-1245 改用 `_same_deep_components_with_current_gate(checkpoint.get("component_identity") or {}, _deep_component_identity(...))`（与 2/3 一致；后面 1276-1280 的当前门与刷新检查原样保留）。若刻意只允许同 epoch 回放，则须在 1109-1114 处把 validator 变更与 execution_version 绑定，并在文档中写明。
- 声明：这是"闭门过严"反例，**不是**采用绕过；未把未读代码当已证——(a)(b) 两条件未证，故定级中而非高。

**F2 · 低（设计边界确认，非缺陷）** traceable 接受任意 64hex（3504-3505），旧 attempts/error_classes 相容性检查（3524-3547）对完成结果不再执行；3309-3316 只保形态。这等价于"完成结果的补答年限不可由当前门重验，也不需要重验"——成立前提是"完成结果只能经这三个消费者 + 各自完整当前门"。今日读证成立；该不变量是约定（3489-3494 docstring）而非构造强制。建议最小加固：把"完成结果消费者必须先身份后门、不得只调 traceable"写入函数注释旁的显式约束，并加一条测试钉住"非真实合同 64hex 也仅是证据、仍须过门"的语义，防止后续改动悄悄重加白名单或漏门。不建议引入任何版本白名单（与 owner 立场一致）。

**F3 · 低（既有差异，非本增量引入）** restricted 分支：消费者1 对受限批跑 `_validate_deep_batch_output`（1274），消费者2/3 的 restricted 分支不跑（3349-3366、3776-3784），依赖 `restricted_batch_from_review` + `expected==saved` + 刷新检查。受限结果不进入采用，故非采用漏洞；若要求门强度一致可补齐输出门（低成本），但不属本窗口阻断项。

**F4 · 低（既有差异）** 定义登记一致性检查 `consumers is None and restricted...attempts` 只在消费者1（1254-1256）；2/3 依赖 `_validate_saved_source_review` 3716-3721 的"有定义陈述必须有回执"（fail-closed 主情形已覆盖）。"无定义陈述但 attempts 非空"的更窄状态在 2/3 未查，语料可达性未证；建议镜像该检查或注释说明。

**F5 · 中（测试缺口）** 缺失：(a) `_replay_checkpoint` 对完成检查点的接受度测试（正是 F1 的区间）；(b) test 1 第三阶段只验证计划 `current_gate_requires_refresh`，未 `run_job(rejected.job_id)`，刷新路径的"实际重读且旧 checkpoint 不变"未被断言；(c) 预检/采用层用**旧 validator_version**（非仅旧合同 hash）的完成检查点单独参数化（6843+ 只覆盖 restricted）。最小补充见 D2。

### D. 决定所需未证条件与最小验证

- U1（决定 F1 定级）：`completed-result-current-gate-revalidation/v1` 是否本增量新增；增量前完成检查点是否可能带旧 validator_version 走到 `_replay_checkpoint`（且通过 1109 门）。验证 D1：一个回放级聚焦测试。
- U2（决定 F2 是否需加固）：是否存在"完成 deep 检查点 + repair_used=True + 非 `protocol_control_agent_repair_contract_sha256` 产物的 64hex receipt"的真实/合成保存。owner 的 6657-6719 说明历史变体存在且 traceable 有意全收；建议一条显式测试钉住该语义。
- U3（决定 F5(b)）：刷新决策执行后旧检查点仍不变、且确以新读取完成。验证 D2：在 test 1 第三阶段加 `assert runner.run_job(rejected.job_id)` + 新读取计数 + 旧 checkpoint 断言。
- 最小验证清单：D1 回放旧 validator 测试；D2 刷新执行断言；D3（可选）traceable 非合同 64hex 语义测试。三者皆不触碰临床门，不需要重读成功组。

### E. 有界可接续建议

**可接续，无阻断。** 增量结构自洽：完成结果=形态+身份+当前门+来源刷新；未来路径=精确补答材料比较（旧负例未动、读证确认）；无版本白名单、无当前材料伪算历史 hash（3503-3505、3313-3316 均为形态校验）。建议以最小改动闭合：修 F1 单行（或文档化 epoch 语义）+ 补 D1/D2 两个测试；F3/F4 仅记录。真实产品未运行、无 DB/临床原件读取，本判断限于合成测试与当前源码；同家族模型仅程序/上下文隔离，不构成独立金标。

**剩余未读边界**：`_saved_deep_run_result` 全文（仅 grep 4672-4700 行）；`_validated_deep_partial_source` 本轮仅 grep（2822/2838/2899/2915 的精确补答身份比较仍在，结构与上轮读证一致，未重读全函数）；`restore_scoped_session` 实现不在读取集；未做 diff（无法归因 2113/1244 哪行是本次新增）。
