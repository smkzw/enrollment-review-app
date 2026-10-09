同角色续审，限定增量核对。先定位两源码与两测试中该增量的落点。

增量已定位。核对四处关键实现：build_result 保留条件、恢复入口校验、F1 类型化失败与计数合并、服务端比对。

# Conference Output: rv1006-pending-author-review-20261010 - evidence_single_object

## Output

### A. 已读证确认（增量范围内）

1. **F1（deconstructor 8181-8192，已读）**：source 漂移不再抛裸异常；改为追加 receipt `outcome="publication_invalid", error_classes=["PENDING_AUTHOR_SOURCE_CHANGED"], error_detail={code, adopted:False}`，并 `return build_result(..., source_interpretation=更新后 source, pending_author_wire=None)`。显式 `None` 经 `setdefault`（7320）不会被覆写，旧回执不落本检查点——与声明一致；尝试序列含实际 source 复核 receipt（8104-8113 路径仍在，失败即返回、无作者调用）。
2. **F2（9319/7318-7319、7447、8480；service 2737-2739，已读）**：保留条件要求 `pending_author_source_sha256 == sha256(current source)`（7318-7319），哈希在恢复时对获重回执重算（7447）、在解析/合并捕获点写入（8480）；服务端在读入口用**保存的 source 本体**重算比对（2737-2739，fail-closed 报“与生成时的来源解释不一致”）。捕获于 parse/merge 时点、非返回时补造，成立。
3. **F3 主线（7309、7423-7426、8243、7323；service 2740-2742、4411、4537-4538，已读）**：`resume_pending_author_repairs_used` 类型/非负校验（7423-7424）、不得脱离提案单独恢复（7425-7426）；`repairs = source_repairs + resume_pending_author_repairs_used` 在任何修复前建立（8243）；结果字段 `pending_author_repairs_used: int ge=0`（4390）；服务端校验类型（2740-2742）、运行期透传（4411）、诊断落盘（4537-4538）。**但发现一处可达计数旁路，见 B1。**
4. **F5（7317、2729-2731，已读）**：build_result 层 `capability_wire is None` 才允许附 pending（7317）；服务消费层拒绝 `capability_wire`/`source_front_target_review`/`pending_source_definition_consumers` 与 pending 共存（2729-2730）。双层防护成立。（Q3“producer 移除 TIME_PRECISION_UNSUPPORTED 共储”未在本轮读取窗口复核，见 D。）
5. **旧语义不回退（已读）**：pending 恢复仍拒绝与已核草稿/复核证明混用（7427-7433 扩列后保持）、`restore_scoped_session` 必须存在（7435-7437）、无审批恢复 receipt（7452-7457）。

### B. 找到的候选可达旁路（计数）——需一行确认后即可定案

**B1 · 计数重置旁路：pending 恢复期若发生一次 source 疑问复核失败，累积作者次数被写成 0。**
- 机制（全部读证）：恢复时 `repairs` 初值仍为 0（7309 `repairs = source_repairs = 0`）；复核循环 guard 只看 `source_repairs`（8067-8068），调用前 `source_repairs += 1`（8088）；调用失败即 `return build_result(..., source_interpretation, partial_wire=None)`（8114-8118）——此时 pending 变量非空（7446 设置）、source 未变（异常路径不改 source）→ 7318-7319 哈希条件成立、pending 保留；但 `pending_author_repairs_used = max(0, repairs - source_repairs)`（7323）在 `repairs` 尚未被 8243 重设前计算 → 结果恒为 0。旧回执不可变，但**新诊断检查点把累计作者次数归零**（4537-4538 原样落盘），下一 Job 读回 0（2740、4411）→ 可再获一次“已付过”的作者修复额度，绕过 F3 宣称的“新 Job 不得静默授予调用”。
- 可达条件（严格）：pending 提案 + 存在合格且未问过的疑问（8067）且 `source_repairs < max`。后者在“同 max”下通常被历史合计挡住（原运行耗尽额度），因此现实入口是**新 Job 的 `deep_max_schema_repairs` 大于原 Job 源侧已用数**——恰是 F3 要防的跨 Job 预算场景；复核调用本身若失败即触发归零。
- 负向影响面：仅额度，不漂移、不误采用（作者修复仍需完整门禁）。
- 最小修复（一行）：把 8243 的重设上移到复核循环之前（获取历史合计之后），或 7323 改为 `max(0, repairs - source_repairs, resume_pending_author_repairs_used)`。
- **唯一未证前提**（请以一次 `grep -n "^\s*repairs = "` 于 7309-8243 之间闭合）：该区间内不存在其他 `repairs` 赋值；否则 B1 不成立。我不把这作为已证缺陷。
- 缺失测试建议：pending 恢复 + 1 个合格疑问 + 复核调用失败 → 断言 `result.pending_author_repairs_used == 携带值`、下一 Job 不再获新额度。owner 的“零调用”测试用空 statements 夹具（11937-11946 前例），覆盖不到该路径。

### C. 第二处候选缺口（映射/测试，需一行确认）

**C1 · runner 是否把 PENDING_AUTHOR_SOURCE_CHANGED 映为类型化 StepFailure。** 我上轮读到的失败码集合（execution 4436-4465）与 detail 映射（4493 起）中**没有**该码；若本轮未追加，则 deconstructor 的类型化 receipt 在 runner 边界退化为 `PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID` + 通用文案（4499-4507 兜底），检查点仍落盘、旧回执仍安全，但“结构化失败”在**StepFailure 错误码层不可见**。请确认 4436-4465/4493 是否已加入该码；并确认新 runner 测试断言的是映射后的 StepFailure 码而非仅 run 结果。此行我本轮未重读，按未证处理。

### D. 剩余边界（诚实声明）

- 未读：deconstructor 7470-8040（`repairs` 赋值点与 7524 区历史合计的重算；B1 的唯一前提）；execution 4405-4415 仅凭 grep、4315-4325（F6 包裹）与 4434-4507 未重读（C1 前提；F6 本轮不可确认，仅记录 owner 陈述）；capability 赋值点（Q3）；`_deep_source_checkpoint_proof` 全文（Q2）；transport `restore_scoped_session` 实现不在读取集（Q1，采信 owner 描述）。
- 未运行测试；不核对 owner 的 18/1422（无法在本边界内复核测试体）；新增测试名未被我的关键词命中，未定位其行号。
- 本报告为同家族程序/上下文隔离审查，非独立模型结论，不构成临床或最终验收。

（报告完。如需闭合 B1/C1，各需 1 次聚焦读取；本会话可直接续审。）
