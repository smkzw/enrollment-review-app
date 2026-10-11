收到同会话续跑指令与主机构事实更新（末次为有绑定负回执的 `publication_invalid`，非传输失败）。按新边界：只读审阅工作区 diff（`protocol_control_execution.py` 与其测试），不委派、不浏览、不改文件、不做临床裁定。先取工作区变更范围。

Bash 被拒绝（非交互模式无审批）。按指示不绕过：改用只读 Grep/Read 定位工作区 diff 的新增符号（主机描述的新保留路径），逐段核对。

定位到新增区域（执行服务 255-270 策略、3150-3300 保留证明、4500-4730 深析接线；测试 4450-4820）。继续精确读取。

新增符号已定位（`_INDEPENDENT_DEEP_READ_POLICY`、`_preserved_negative_alignment_proof`、执行接线与 4 组新测试）。开始读取生产侧关键区段。

生产侧保留路径与绕过点已看清。继续读取：新失败路径的终局分支、`_saved_failed_deep_run_result` 绑定、以及两组关键新测试。

核心安全属性已成型。继续：测试断言主体、独立核查策略的真实消费点（JobRunner）、以及负对齐证明本身的参数化测试。

核查完成。Bash 被拒（无法取 git diff），改用符号锚定逐区只读核对；证据范围已覆盖生产策略、三份保留证明、计划/执行/消费接线、JobRunner 消费点与命名测试。以下为完整报告。

# Conference Output: rv1006-source-scope-resume-review-20261011 - evidence_single_object

## Output

**结论摘要**：补丁在合同层面是**安全的“FAILED 保留”**：证明与当前来源/线稿/实际答复/类型化错误域/已耗尽单元绑定；通过后**零新调用**、`adopted=false`、历史不可变、永不进入完整采用闸门、第二次同类失败停止独立读。未发现高危缺陷。发现 1 个**可操作测试缺口**（fresh-path 绕过的判别性测试）、若干标签精度与设计边界限制（不构成采用/隐瞒风险）、以及几处建议补测。以下严格区分 **[代码事实]/[推断]/[建议]/[不确定]**。

**工具限制（不隐瞒）**：`git diff` 因非交互无审批被拒；无法取得精确工作区 diff。本报告以符号与行号锚定读取重建对补丁区段的审阅：`_INDEPENDENT_DEEP_READ_POLICY`（257-264）、`_preserved_negative_alignment_proof`（3208-3262）及其两个兄弟证明（3112-3197）、计划判定（3550-3589）、执行保留与绕过（4428-4484、4626-4636、4644-4721）、JobRunner 消费（runner.py:244-271、475-486；jobstore.py:296-310、1551-1588）与命名测试（6048-6179、6182-6358、7414-7491、7494-7736）。**未核对**：`_resumable_saved_candidate_alignment` 等 diff 可能触碰但不在上述区段的定义（其行为仅由测试断言间接证明）——列为续跑点。

---

### 1. 证明是否真正绑定当前来源/线稿/实际答复/精确类型化错误域/已耗尽修复单元；畸形/被改/正向/未绑定记录能否误过

**[代码事实] 绑定链完整（逐项）**：
- 终态形状：末次尝试 `outcome=="publication_invalid"` 且 `error_classes == ["SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED"]`（恰一枚举，3216-3217）；`error_detail` 与 `partial_wire` 必须是 Mapping（3218-3219）。
- 类型化错误域：`detail.code==SCR`、`retry_class=="source_semantic_review"`、`ids` 非空、全为 `type is int`（bool 被拒）、`ids == sorted(set(ids))`（3222-3228）。
- 当前来源：`validate_source_interpretation(batch, source)`（3233）；当前线稿：`_validate_deep_batch_output(batch, hydrate(wire))`（3234，完整采用闸门复用，非降级校验）。
- 当前覆盖 vs 实际证明：`_coverage_matches_current_proofs(batch, result)`（3235-3236）——它从**当前**线稿/解释重算覆盖并要求与其逐项相等（`restricted_source.py:61-82`：`len(proven) == Σ(decision=="fully_expressed")` 且覆盖映射逐项相等）。
- 实际答复：`reusable_proven_alignment_items(..., require_positive=False)`（3237-3240；`candidate_alignment.py:790-831`：无双证/多证跳过、`validate_candidate_alignment` 单证重验、`_alignment_input_identity` 源+候选哈希一致、`response_text` 哈希重验、回执重解析后 `matches[0]==item`）。`negatives` 只取 `decision=="incomplete"`（3241），且 `detail.statement_ids` 必须**恰等于**其 statement 集（3242-3243）。
- 已耗尽修复单元：受影响 ids 无 `unresolved`，且 `units <= set(result.reviewed_semantic_repair_unit_ids)`（3244-3247）。
- 域交叉核对：`detail.source_refs == refs`（单元全部 span）、`detail.candidate_indexes == sorted(负条目候选)`、`affected_dependents == candidate_indexes`（3248-3253）。
- 证明载荷：`diagnostic_sha256` 覆盖整份保存诊断、`adopted is False`（3254-3262）。

**[代码事实] 明确的拒绝/失败关闭矩阵（测试直接覆盖，7444-7491）**：`unbound`（proofs=[]）、`changed_candidate`（线稿文本改）、`changed_reply`（decision 翻正）、`boolean_range`、`wrong_range`、`wrong_refs`、`wrong_dependents`、`technical_failure`（换错误类）、`source_ambiguity`（statement.unresolved）、`repair_not_used`（标记为空）→ 全部 `None`；`coverage_changed`→`ValueError`（上抛，fail-closed）；且测试断言 `saved == original`（7491，**证明过程不写入**）。正向只对 `fault is None` 放行（7485-7488）。

**[推断] 误过情形**：正向条目不可能成为负条目（decision 过滤）；未绑定→无负条目→statement 集不等→`None`；来源/批次漂移→身份哈希或 `_alignment_input_identity` 失配→无条目→`None`。**残余差异（非缺陷）**：`units ⊆ 标记` 是包含而非相等（保守，多出的已耗单元不增加声明）；同批 `uncertain` 条目被忽略（不放大声明）；负证明**不要求** `json_path=="/items"`（兄弟未决证明要求，3150），`json_path` 为常量，无实质风险。

---

### 2. 绕过 `restricted_batch_from_review`：是保留真实失败，还是隐瞒 quote 完成/来源损坏；证明范围是否足够 FAILED-only

**[代码事实] 两个绕过点**：
- 保留路径（4453-4455）：`restricted = None if proof["schema_version"]=="phase5/preserved-negative-alignment-proof/v1" else restricted_batch_from_review(...)`；随后 4477-4484 抛 `StepFailure(error_code=proof["error_code"])`，诊断含 `model_call_receipts: []`、`new_model_calls: 0`、`adopted: False`、`preserved_unresolved_from`。
- 新失败路径（4630-4634）：`final_output is None` 时先算负证明；非 None 则**不再调用**受限生产者，直接走 4680-4696 StepFailure（`PROTOCOL_CONTROL_` + SCR）。

**[代码事实] 旧行为的“掩盖”机制已被正确移除**：`restricted_batch_from_review` 首步是 `validate_completed_quote_review(...)`（`restricted_source.py:885-887`），该保存记录中旧 quote-completion 条目缺当前逐项 target-review 项时会抛错，旧执行路径把 ValueError 映射为 `PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID`（4442-4446、4692），从而掩盖真实原因——“首个失败先前变成 RESTRICTED_SOURCE_INVALID”与代码一致。新证明**不依赖** target review（只依赖解释/线稿/覆盖/对齐/标记），因此该掩盖不再发生。

**[推断] 是否会隐瞒损坏**：不会。来源解释损坏→`validate_source_interpretation` 抛错；线稿损坏→`_validate_deep_batch_output` 抛错；覆盖不一致/证明缺失→`ValueError` 或 `None`。前者在保留/新鲜两路径都映射为 RESTRICTED_SOURCE_INVALID（停止类，不在策略码表内），后者退回 `resume_partial`。保存记录本身完整保留（含 `source_target_review`、覆盖、对齐、attempts 与 `diagnostic_sha256`），不存在字节级隐瞒。

**[推断] 范围是否足够 FAILED-only**：足够，但有一条明确限制——证明**不要求 quote 完成度**（不调 `validate_completed_quote_review`），故若真实根因恰是“读取/quote 未完成”，记录的原因标签会写成“候选语义未证”；这**不是采用、不是转化、不是抑制重读任何新证据**（零调用、`adopted=false`、全诊断可复核），只是标签精度问题。**关键加强项**：标记（3246）本身是“该单元曾被 runner 自身准入并消耗唯一修复授权”的见证（`deconstructor:10520-10528` 的准入要求恰一个完整单元、无 unresolved、候选闭包恰等），这使“未完成读取被误标为语义负”的概率与影响都受限于 FAILED-only。若 Codex 要求更强，可在证明里增记既有 `source_target_review` 的 quote 完成状态位（可选，不建议本轮改 schema）。

**[推断] 设计边界（需 Codex 确认）**：当负证明成立时，绕过是**整批**生效——同批另一“真正无决”单元的合法受限（不可执行）产出在该次运行中不会生成；作业以 SCR 失败保留、独立读继续、`gate` 级联失败。这与“不得把负提案转成忠实来源歧义”一致，但与“保留负单元同时照常产出兄弟受限单元”不是同一语义；若后者是需求，需要按单元而非按批绕过（本轮未做）。

---

### 3. 更宽的识别是否会继续未被证明背书的损坏路径；与 JobRunner 续跑策略的比对

**[代码事实] 识别面极窄，三层**：
1. 策略仅随显式 opt-in 注入（1048-1054），严格布尔（测试 6048-6053：`None/1/"true"/[]` 全拒），载荷精确到字典（测试 6149-6155）。
2. 消费点三处：计划判定（3571-3577，需 `partial[2].source_seed_proof is None`）、执行保留（4428-4449，需控制字典与策略**逐值相等**）、新鲜路径门（4630-4632）。
3. JobRunner（`runner.py:244-262`）：必须 `not failure.retryable` + `step_id` 前缀匹配 + `failure.error_code ∈ codes` + `max_failed_steps` 合法正整数；`prior_failed + 1 < 2`（265-271）——**第一次同类失败继续，第二次停止**。`continue_independent` 为假时 `settle_job=True`（477-479）→ 任务终败；为真时仅在任务仍 running 时 `continue`（484-485）。
- **身份/结构错误必停**：`MODEL_IDENTITY_INVALID`、`PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`、`RESTRICTED_SOURCE_INVALID`、`DEPENDENCY_FAILED_CODE`、可重试传输码都不在码表且各自被 `retryable` 或名单拒绝（250、255-262）；证明不等→DEEP_SOURCE_INVALID（4447-4449）；生产者异常→RESTRICTED_SOURCE_INVALID（4442-4446）。
- **采用闸门必失败**：依赖失败的步骤不可运行（`jobstore.py:296-310` 仅“依赖全部 completed”才可运行）；终败时 `_cascade_final_failure` 把传递依赖全部置 `failed_final`+`DEPENDENCY_FAILED_CODE`（1551-1588），`_finalize_job_failure` 置任务 `failed_final`（1600-1610）。测试 6307/6342 断言 gate 执行器未被调用且步骤 `failed_final`。
- **零调用**：保留分支在 4477-4484 直接返回失败，`model_call_receipts: []`；测试 6293 用 `pytest.fail` 守卫“保存的未决不得再调用作者或核对模型”。

**[推断] 潜在延续面**：唯一“更多识别”的是把 SCR 纳入 `error_codes`，它只影响**继续运行独立步骤**，不会把失败步转化为成功、受限或采用；也不改变 `resume_partial`/`reusable` 语义。未发现可被伪造证明继续的损坏链（畸形记录在最外层就被终止）。

---

### 4. 真实 Job/Artifact/checkpoint 测试是否证明六项主张；fixture 修正是否放宽生产校验

**[代码事实] 逐项证据**（`tests/v2/services/test_protocol_control_execution.py`）：
- **历史不变**：6319（旧作业 checkpoint 指纹与运行前相等）、6179。
- **保留失败零新调用**：6331-6332（`new_model_calls==0`、`model_call_receipts==[]`）、6176-6177。
- **不进入完整采用**：6307（gate 执行器永不调用）、6342（gate `failed_final`）+ jobstore 级联（1551-1588）。
- **独立工作前进**：6313（真实 `JobRunner.run_job` 返回真）、6339（`deep_0002 completed`）、6169。
- **被改证明拒绝**：6248（`diagnostic_sha256="bad"`）→6322-6323 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`；7729-7734（组件/修复身份损坏，且 7734 断言无额外调用）。
- **两次失败上限未变**：6190（`second_failure`）→6339-6341（`deep_0002 failed_final`、`deep_0003` 未 completed）、runner 上限 265-271。
- 保留分支真实落盘：6237（从真实 checkpoint 重算证明）、6318-6335（`partial_wire`/`source_candidate_alignment` 与诊断逐字节相等、`adopted is False`）。
- 负证明自身的拒绝矩阵：7444-7491（12 个故障参数 + 不可变性断言）。
**fixture 修正**：7414-7441 通过改写来源文本/时间字段、清 `time_words`/`decision_functions`/`source_time_excerpt` 并**用生产 `bind_candidate_alignment` 重新绑定**实现“隔离非时间语义失败”；测试 7481 调用的就是生产证明函数，6223/6238 亦复算生产证明——**未放宽生产校验**，与主机描述一致。

**[建议] 补测（覆盖缺口）**：
1. **fresh-path 绕过判别测试**（最高优先）：现有能到达 4630 的测试（6192 保留路径、7640 轮转）要么走保留分支，要么把 `restricted_batch_from_review` monkeypatch 成 `None`（7689），无法区分“绕过”与“生产者恰好返回 None”。建议：构造 `final_output is None` 且 marker 已耗尽、对齐/覆盖有效的 runner 结果，将生产者替换为 `AssertionError` 探针，断言 `_execute_deep` 的失败码为 `PROTOCOL_CONTROL_SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED` 且探针未被触发。
2. 负证明故障矩阵补 `changed_source_text`（单元文本改→身份漂移）与 `changed_batch/protocol id`，以及同批存在 `uncertain` 条目的对照。
3. 计划阶段的证明异常映射（3575 无本地 try）补一条负例，明确用户看到的是拒绝而非继续。

**次要测试观察**：测试 7640 系列显示“标记未耗尽”时恢复仍会**发出一次**逐项对齐调用（7725-7727：只问 statement 1、不问 0），与 3246 的“耗尽”前置一致；两机制互补，非冲突。

---

### 缺陷（按严重度，均附精确证据）

- **S1｜测试覆盖缺口（low-medium）**：fresh-path 绕过无可判别测试（见上 §4.1）。证据：7689 把生产者置 `None`；6192 的负例走 4428/4477 保留分支（4453-4455 的绕过早于 4630）。**替代方案**：探针测试（不需要改生产代码）。**限制**：若未来有人把 4630 的负证明门删除，现测试不会红。
- **S2｜标签精度（low）**：保留证明不校验 quote 完成度（对比 `_preserved_unresolved_review_proof` 还排除“依赖路由可用”的非动作定义，3140-3141；负证明无对应排除）。若真实根因是读取未完成，记录标签可能是“语义未证”。**替代方案**：仅在证明中附记既有 target-review 状态位（可选）；**不建议**改判定（会削弱“不重复读取”的边界）。**限制**：全诊断与 sha 保留，可人工复核。
- **S3｜设计边界（low，需确认）**：负证明成立时**整批**不再产出受限批（4453-4455、4630-4634），同批真正无决单元的合法受限产出被推迟到后续计划。**替代方案（如需要）**：按单元绕过（仅跳过负单元，允许其余单元受限）；**限制**：会引入“受限批内含未证候选”的新组合，需重新证明候选与受限单元不相交（`restricted_source.py:797-800`），本轮不建议。
- **S4｜证据差异（note）**：`units ⊆ marker` 为包含（3246），`json_path` 未校验（对比 3150）。均保守，无利用路径。
- **无高危**：未发现可让畸形/变更/正向/未绑定记录通过、或让失败路径产生调用/采用/继续损坏链的缺陷。

### 反对意见、决策点与有界问题

- 反对意见 1：不要把“保留失败”理解成“已裁定的临床结论”；它只冻结一次**有界、已耗尽**的模型分歧，供后续人工/独立流程处置。
- 反对意见 2：若 Codex 期望同批兄弟单元仍产出受限结果，当前补丁不满足——需显式决策（S3）。
- 决策点 P1：是否要求 S1 的探针测试作为合入门槛（建议：是，零生产改动）。
- 决策点 P2：是否接受 S2 的标签精度（建议：接受，并留档）。
- 有界问题 Q1（可只读回答）：对真实保存诊断运行 `_preserved_negative_alignment_proof` 是否返回非 None（验证 `statement_ids`/`candidate_indexes`/`affected_dependents` 与真实 runner 落点完全相等）？若否，补丁的零调用收益在实际记录上不会兑现。
- 有界问题 Q2：真实记录的 `source_target_review` 是否存在“旧 quote-completion 条目缺当前 target-review 项”的状态（决定旧掩盖是否确实被本次修复消除）？
- 有界问题 Q3：S3 的按单元绕过是否属于本轮需求？（若不属于，请记录为已接受边界。）

**独立性折减**：审阅者与产品同属 DeepSeek 模型家族，仅适配器/上下文不同；本报告是**源码合同级**工程审阅，不构成医学批准，也未对负判定的临床正确性作任何断言。可安全声明：**本补丁在 FAILED-only 保留范围内是安全的**；超出该范围（采用、受限转化、临床结论）均未被证明，也未被补丁触碰。
