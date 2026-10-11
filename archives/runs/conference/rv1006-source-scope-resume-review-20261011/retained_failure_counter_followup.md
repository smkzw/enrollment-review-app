收到：审阅 retained_failure 实际实现。只读、不改文件、不委派（Trellis 任务与计划文件与本次只读边界不符，不创建）。先定位全部实际使用点。

定位完成：`errors.py:77-87`、`runner.py:275/766`、`execution.py:4482`。读取完整定义与新增测试。

# Conference Output: rv1006-source-scope-resume-review-20261011 - evidence_single_object

## Output

只读审阅 retained_failure 实际实现（8 次工具已用满：2 定位＋6 读取）。未改文件、未运行产品模型、未读真实方案/病例/DB/env/私有运行、未委派（Trellis 任务与计划文件与本次只读边界不符，未创建）。合成 JUnit 76/0/0/28.5s 为宿主提供，**不是真实新方案作业**；本审阅**不构成医学批准**，也不称 47/49 复用已修好（既有 49 不会自行生成表格 witness，同意该表述）。

---

### 结论速览

**[代码事实] 上轮建议的实现与描述一致，未发现可实测的止损绕过或"旧损坏记录伪装保留"路径；3 项建议级加固、2 项证据不足。** 关键链条已逐条读完并有测试支撑：

- `StepFailure` 新增 `retained_failure` 且**构造即强制**非重试＋带诊断（`app/workflow/errors.py:77-87`：`:79-81` 校验，:215-219 测试两向拒绝）。
- 唯一生产者为 `_execute_deep` 的 `preserve_unresolved` 终局分支（`app/services/protocol_control_execution.py:4479-4487`，`:4482` `retained_failure=True`）；到达该行前必须依次通过：策略逐值相等（`:4431-4433`）→ 部分草稿重载 → `_preserved_source_review_proof` 重核非 None（`:4442-4443`）→ 与入队前冻结证明**逐字节相等**（`:4449-4451`）→ 负证明强制 `restricted=None` 的合法不可转换判定（`:4455-4457`）→ 未走受限转换（`:4463-4478`）。损坏/来源改变→`DEEP_SOURCE_INVALID`/`RESTRICTED_SOURCE_INVALID`（`:4444-4451、4458-4462`）**不带**该标记。
- `_commit_step_failure` 用**当前异常**的值覆盖复制来的标记（`app/workflow/runner.py:762-766`），`_continue_independent_after_failure` 只信显式原 policy/白名单/前缀/`max_failed_steps=2`（`:248-264`），计数逐步骤读最近 checkpoint 的 `_runner_failure_origin`，**保留失败不计、缺标记按新失败计**（`:265-274`），并 `prior_failed + int(not failure.retained_failure) < max_failed`（`:275`）。

---

### 1) 新旧失败误分类 / 旧损坏记录伪装保留

**[代码事实] 不能（当前代码）：**
- 复制标记无效：服务例 `test_preserved_failure_revalidates_restricted_source_through_actual_job_checkpoint` 的 runner 测试显式构造"新失败携带复制来的 `_runner_failure_origin=revalidated-retained-failure/v1`"（`tests/v2/workflow/test_runner.py:175-177`），并断言实际落盘为 `new-failure/v1`（`:186-188`）——覆盖逻辑在 `runner.py:765-766`。
- 旧记录伪装：无标记（旧版本或未带诊断的失败）一律计入新失败（`runner.py:272-274`，`saved is None` 亦然）→ **更保守**（更早止损），不是豁免。
- 误豁免的唯一通道是"执行器自行声明 `retained_failure=True`"：当前应用内仅 `execution.py:4482` 一处（全库 grep 仅 3 个应用点：`errors.py:77/79/87`、`runner.py:275/766`、`execution.py:4482`）。
**[建议/S1] 防御纵深**：`runner.py:272-274` 接受 `revalidated-retained-failure/v1` 时，可加一条廉价结构校验（保留诊断须含 `preserved_unresolved_from` 且 `new_model_calls == 0`、`adopted is False`），或在 `execution.py` 保留分支断言 `proof["error_code"]` ∈ policy 白名单。**权衡**：通用 runner 层引入协议字段会耦合；现状单生产者可接受，故列为建议非必修。
**[建议/S2]** 保留分支的 `error_code` 取自 proof：STU/SCR 在白名单（`source_interpretation.py:3158`、`candidate_alignment.py` 系 3260 同义），temporal proof 为 `PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID`（`:3196`）**不在**白名单——当前经由 `_preserved_temporal_restriction_proof` 自身的受限批前置（`:3178-3183`）实际不可达该 raise；建议仍加一条断言或注释，防止未来 proof 类型静默失去"保留不计数"。

### 2) 重启/持久化/失败后 gate / 非白名单错误

**[代码事实] 保持：**
- 重启：标记随失败 checkpoint 持久，跨 worker 重读；`test_retained_failure_origin_is_preserved_across_worker_stop`（`:191-212`）证明停止后第二次运行仍按标记排除旧失败（`calls == ["deep_0001","deep_0002","deep_0003"]`，终态 `failed_final`）。
- 计数语义：`test_retained_failures_do_not_spend_new_read_limit_and_never_allow_publication`（`:158-188`，参数 0/1/2 个新失败）证明：两个保留失败不消耗名额；第 1 个新失败继续、第 2 个新失败停止（`calls == reads[:4]`）；`gate` 从未执行（`:183`）。
- 失败后 gate：依赖失败步→不可运行；服务例断言 `gate` 执行器被 `pytest.fail` 守卫且步骤终态 `failed_final`（`test_protocol_control_execution.py:6315-6316、6355`），并断言 `deep_0003` 在"一个保留后新失败"时**完成**、在"两个新失败"时 `failed_final` 且 `deep_0004==queued`（`:6349-6354`）——即 41 单元类场景的"止损边界"在真实 Job/checkpoint 上成立。
- 非白名单/身份/结构/传输：`eligible` 三关（前缀、码表、max 类型）不满足即 `return False`（`runner.py:255-264`），且 `failure.retryable` 先拒（`:250`）；`errors.py:79-81` 保证保留失败不可能可重试。终态、策略、总步数、每单元预算、发布要求均未被本补丁改动（服务例仍断言旧作业指纹不变、保留步 `new_model_calls==0`、`adopted is False`、`_runner_failure_origin` 正确，`:6328、6340-6343`）。

### 3) 相邻消费者直接风险

- **[代码事实]** `_runner_failure_origin` 仅 `runner.py:272-273` 读、`:765-766` 写，无第二消费者；诊断多一个键不会破坏既有读取（`_saved_failed_deep_run_result` 按模型字段过滤，`execution.py:4881-4882` 旧编号面；proof 的 `diagnostic_sha256` 在计划与执行两处均读同一 checkpoint，保持一致——服务例 `:6238` 与 `:4442` 同源）。
- **[证据不足/E1]** `tests/v2/agents/test_evidence_prospective_repair.py:95` 也命中 `retained_failure` 字样，未读；该子系统的错误码/前缀不在 `deep_` 白名单面，推测无直接计数影响，但未核实其是否新增第二个 `retained_failure=True` 生产者。
- **[证据不足/E2]** 版本串纳入 `validator_version`（`protocol_control_execution.py:2095-2100`）与"未使用的可选来源字段不应导致 47 已核来源全部重读"的关系：我未读产品预检的分粒度比较（`same-identity` 复用路径），无法证实新增版本串不会触发整批 refresh。**有界问题**：该 join 变化是否只影响新作业的组件身份，而旧材料复用仍由逐材料预检证明？这是本补丁唯一可能产生"扩大重读"的相邻点。

---

### 必修 / 建议 / 证据不足

**必修**：无（未发现可实测绕过；止损、标记覆盖、重启持久化、gate 拒绝均成立）。
**建议**：S1 保留标记的结构性复核（或声明其执行器信任边界并加注释）；S2 保留分支 `error_code ∈` 白名单断言；补一条"保留失败 + 非白名单码（如 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`）仍立即停止"的直接用例（现由服务例 `changed_proof` 间接覆盖，但未走 retained 属性路径）。
**证据不足**：E1 `tests/v2/agents/test_evidence_prospective_repair.py:95` 的实际用法；E2 版本串→整批重读的预检分粒度。两处均给位置，不影响上述结论。

**独立性折减**：审阅者与产品同族模型（仅适配器/上下文不同）；本报告为源码合同级审阅，不构成医学批准，也不替代完整 1006V1 流程；未对真实方案/49 恢复作任何结论。**给 Codex 的有界问题**：Q1 是否接受 S1 的通用层耦合（若否，是否只在 execution 侧加断言即可）；Q2 请提供 E2 预检分粒度的确认（决定是否需要限制版本串的作用域）。
