同批准角色继续只读增量审阅（确定性阶段回填 + v6 恢复）。先定位五文件中的新符号与实际落点。

定位完成。读取核心定义：两个时间词辅助函数、缺失门触发处与 `normalize_source_stage_echo` 本体。

继续读取 v6 恢复主体、`_validated_deep_partial_source` 投影，以及新测试与 echo 版本常量。

v6 主体已读。核对四个关键点：组件身份中 echo 版本的位置（决定旧完成组是否被丢弃）、编译器对时间词/阶段的使用、seed 余额消费处、以及存量真实服务消费测试。

最后一读：编译器快速路径门 `can_compile_stage_bound_source` 本体，判定时间词回填能否改变编译资格。

# Conference Output: rv1006-pending-author-review-20261010 - evidence_single_object

## Output

### A. 已读范围（18 项聚焦读取，全程只读）

- `protocol_control_source_interpretation.py`：`_scope_carries_stage_fragment`/`_time_words_cover_stage_label`/`_unreported_time_fragments`（198-247）、缺失门与时间门（3186-3224）、`normalize_source_stage_echo` 全函数（3256-3283）、`SOURCE_STAGE_ECHO_VERSION`（47）。
- `protocol_control_deconstructor.py`：来源读取后的归一化/验证/实际 raw 回执记录（7761-7888，含 7767 echo、7770 完整 validate、7771-7787 receipt、7826+ 范围修订链）。
- `protocol_control_execution.py`：`_unrepaired_source_seed_proof`（2353-2407）、`_revalidated_source_seed_proof` 全 v6（2410-2674）、`_validated_deep_partial_source` 分支与投影（2961-3075）、`_deep_component_identity` 尾部与 `_same_deep_components_with_current_gate`（2088-2140）、`source_repair_limit` 投影点（2831-2836、2958、2651）。
- `protocol_control_stage_compiler.py`：`can_compile_stage_bound_requirement`/`can_compile_stage_bound_source`（245-298）；`_simple_stage_scope`/`source_has_single_visit_anchor` 仅由 grep 见到 143-145，未读全。
- 测试：slice58c `test_grounded_stage_echo_...`（5400-5418）、`test_runner_echoes_...`（5421-5445）、`test_stage_echo_never_repairs_...` 六例（5448-5467）、`test_runner_corrects_study_phase_...`（5470+ 开头）；execution `test_pending_stage_witness_with_two_corrections_reaches_real_recovery_consumer`（4774-4922，含 tamper 分支）。

### B. 已核事实（读证，非采信结论）

1. **echo 仅复制、不选阶段**：`normalize_source_stage_echo` 先 `validate_source_interpretation`，仅捕获精确 `SOURCE_STAGE_TIME_MISSING`（3264-3266）；已有时间词与 stage 存在包含/被包含关系即中止（3271-3273，测试 5451 证"筛选"部分成员不补）；未报时间片段中存在任何 `!= stage` 者即中止（3274，测试 5452/5453 证窗口/分钟不补）；只 `append(affected_stage)`（3279）；不改原对象（3277，测试 5413-5415 逐字段相等）。
2. **下一原门仍运行**：回填后立即 `validate_source_interpretation`（7770）；若非缺失门的其他门仍失败，按原范围修订链处理（7826-7875），窗口/时长/小时门（3202-3224）不被跳过。
3. **原答与 hash 保持**：`raw_output_text=source_text`、`raw_output_sha256=sha256(source_text)`（7774-7775）；echo 元数据作为 `error_detail` 记录在实际 attempt（7784-7786，测试 5442-5445）。
4. **v6 恢复**：仅未采用且无下游证明的 pending（2438-2446）；逐条重放成功修订（2520-2602：attempt 序号、parsed、无 error_classes、raw hash 全验证，scope 修订不得改已核 scope/context/affected_stage 2590-2597）；失败尾巴必须全 schema_invalid 且逐条 hash 验证、只丢弃不合并（2524-2541、2659-2660）；不得略过 parsed 成功（2560-2562、测试 4880-4881 篡改为 parsed→refresh）。
5. **余额**：`source_repair_limit = max − pending_repairs_used`（2651），已花数必须等于 `attempts[1:]` 有原答的条数（2477-2482）；测试 4911 断言 4−3=1，4878-4879 改 0 → refresh。
6. **投影与采用隔离**：消费点重算 echo 并比对 `stage_echo_indexes` 与 `source_sha256`（3008-3014）；旧 source hash（`original_source_sha256` 2655）与新 hash（`source_sha256` 2668）均记录；旧 checkpoint 指纹在恢复与消费后不变（测试 4922）；损坏回执硬失败不降级（2492-2494；测试 4886-4889）。
7. **组件身份**：`SOURCE_STAGE_ECHO_VERSION` 位于 `validator_version` 连接串（2118，join 收于 2120），**未进入 compiler_versions**；`_same_deep_components_with_current_gate`（2127-2140）对 validator 漂移容忍 → 预检/采用类完成组复用不会因本增量被丢弃。

### C. 按严重度发现

**C1 · 中（前次遗留，本轮未复核；本增量扩大暴露面）· replay 消费者与 validator 版本**
`_deep_component_identity` 新增 validator 串（2118）使所有旧检查点的 `validator_version` 与当前不等。预检/采用路径用 `_same_deep_components_with_current_gate` 容忍（已核）；但上一轮读证的 `_replay_checkpoint` 深审分支曾用**精确** `component_identity` 比较（当时 1244-1245）。若当前版本仍为精确比较且本增量未同步 bump `PROTOCOL_CONTROL_EXECUTION_VERSION`（1109-1114 的版本门会整包拒绝旧 job），则崩溃恢复窗口内旧 completed 检查点在该路径 `CHECKPOINT_INVALID`——即"旧 completed 被不必要丢弃"的一个残余入口。最小验证（1 行）：读当前 `_replay_checkpoint` 深审分支的 identity 条件 + 查 execution 版本常量是否随增量 bump。未复核前不作已证结论。

**C2 · 低（测试未隔离）· 编译器快速路径问题未定**
`can_compile_stage_bound_source`（257-298）静态门：单访视锚（266）、force=required（269）、`_simple_stage_scope`（270）、**`time_words` 非空**（271）、无例外/未决（272-273）、声明时间部件 ⊆ 简单范围（288-291）、与冻结访视匹配（292-297，只用 scope_text，不用 time_words）。echo 唯一可能翻转的是 271；仅凭重复标签不能制造冻结访视匹配。但 test 5400 夹具带 `exception_words="原有例外"`、`unresolved=["原有疑问"]`（5407），`assert not can_compile...` 由 272-273 即可满足，**未隔离标题来源标签能否启用快速路径**。最小用例：force=required、无例外/未决、仅标题来源 stage、echo 后断言结果并确认决定守卫；`_simple_stage_scope` 若以单时间词推导范围则需一并核（本轮未读，不当作已证缺陷）。

**C3 · 低（追踪对称性）** `_unrepaired_source_seed_proof` 施加 echo（2384）但 proof 不含 `normalization_version/stage_echo_indexes`（2390-2407，v1）；消费端无需投影（保存来源已含标签，3015 直接 validate 通过），无安全影响，仅取证完整性。

**C4 · 低（既有边界，非回归）** 已含 echo 的 pending（读时回填、后因他陈述失败）不会被 v6 pending 分支恢复（2483-2485 对 whole-member 覆盖直接拒绝；且 2443 要求末次错误码为缺失门）；该状态在旧 v4 下同样不可恢复，属既有边界。

### D. 可否有界使用

可以有界使用：echo 是确定性纯函数、只复制已被完整 validator 证明来源的字段、原答/回执/旧 hash 全保留、v6 逐条重算并以 hash 与序号封闭、损坏即硬失败、旧检查点不变。建议在放开前做两项最小动作：C1 的 1 行复核（决定 replay 路径是否需与另两消费者对齐为 `_same_deep_components_with_current_gate`，改动即 1 行）与 C2 的 1 个隔离用例。真实相连窗口（真实 reviewer 消费链）尚未跑通——测试 4774 以 `failed_final` 结束是刻意的"不伪造审核者"，不算回归。

### E. 未证边界与证据限制

- 无 diff，不能归因任何行为"本次新增"；`_replay_checkpoint` 当前版本未复读；`_execute_deep` 的 seed 余额消费行因 grep head_limit 截断未读（仅由上轮同函数读证与 2651 投影互证）；`_simple_stage_scope`/`source_has_single_visit_anchor` 未读；execution 版本常量是否 bump 未知；未运行测试（采信 owner 18 passed）；修复者声称的"先前 12+1 失败为 fixture TypeError"未独立复核。
- 本审阅为同家族模型的程序/上下文隔离审查，非独立金标、非医学批准；未输出临床内容，未读原件/库/env/原答。
