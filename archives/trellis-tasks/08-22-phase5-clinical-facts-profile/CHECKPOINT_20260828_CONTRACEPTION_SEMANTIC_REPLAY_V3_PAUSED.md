# Phase 5.8d 避孕附录语义回放 v3 无损暂停检查点

日期：2026-08-28  
分支：`codex/phase5-clinical-facts-profile`  
工作树：`.worktrees/phase5-clinical-facts-profile`

## 本轮已完成

1. 按最新执行路由创建并完整运行受治理执行包 `phase5-slice60k-contraception-semantics-20260828`；三名只读执行者均由 `cursor-cli/auto` 正常终止，未触发 fallback，输出位于 `runs/execution/phase5-slice60k-contraception-semantics-20260828/`。
2. 父级核对后确认两个共享根因：
   - 条件分句与候选摘录的句末中文标点不一致时，可能绕过条件映射门禁；
   - “告知参与者，如果……则……”是当前沟通义务所承载的条件指令，不应被误写为筛选/基线已经发生的触发事件。
3. 已修改共享门禁：统一去除句末强分句标点后再做条件来源包含判断；被告知/说明/提醒的条件内容不再被当作当前动作的触发。
4. 已修改控制点 Agent 合同并将提示版本升至 `phase5/control-agent-prompt/v1.1`：
   - `must_record` 仅用于原文明示的记录动作；
   - 沟通、确认、告知、讨论和记录不继承被沟通内容的持续期；
   - 计划访视作用域必须保留，但不得发明冻结目录外节点；
   - 条件指令与真正条件触发动作分层。
5. 新增 3 个共享回归：句末标点、条件告知不是当前触发、被告知研究期不得附到沟通动作。修改后聚焦文件回归 `85 passed in 0.48s`，`py_compile` 与 `git diff --check` 通过。
6. 新建不可变配置 `representative_group_contraception_documentation.v3.json`。干跑成功：2 个 owned、1 个 attached、提示 22804 字符；模型预检确认 `127.0.0.1:8002` 为 `mtplx-qwen38-27b-optimized-quality`，上下文 262144。
7. 完成一次真实 MTPLX medium v3 回放，工件位于 `artifacts/phase5-slice60k-d001-contraception-documentation-replay-semantic-guidance-20260828/`：5 次传输均成功，耗时 279.15151 秒，但最终 `hydrated=false`、`gate_accepted=false`、`claims_complete=false`，不得视为模型成功。

## v3 回放得到的新证据

- `body.p1326` 已稳定改进：保留计划访视告知、明示病历记录、参与者同意及停用方法/已知或怀疑怀孕时立即联系研究者的完整条件指令；没有虚构当前触发，也没有把研究期附到沟通/记录动作。
- 剩余失败集中于 `body.p1325` 的时间区间表达：模型把“从签署 ICF 起至末次给药后 3 个月”错误写成 `icf_date + 3个月`，或漏掉末次给药尾段锚点。
- 最后一轮拒绝为 `TIME_CALENDAR_BOUND_UNSUPPORTED`。技术门禁正确拒绝；不是应放宽门禁的理由。
- 模型仍重复了 IN-06 已覆盖的持续避孕同意义务；即使后续技术绿色，父级仍须做重复义务临床拒绝检查。

## 暂停前最后修改（尚未验证）

用户发出暂停前，已通过 `apply_patch` 追加一处通用提示合同修订：

- “从签署知情同意起至末次给药后 N 天/周/月”应表示为 `study_period` 加 `last_dose_date / after / upper_bound=N`，不得写成 `icf_date + N`；
- 修正 `complete_or_verify`、`TIME_ANCHOR_MISSING`、`TIME_CALENDAR_BOUND_UNSUPPORTED` 的定向修订指引；
- 已知目标完整覆盖的持续义务不得重复生成。

该最后补丁尚未运行任何测试、`py_compile` 或差异检查。恢复后必须先验证，不能直接进行 v4 模型调用。

## 活动边界

- 无运行中的 MTPLX 回放或执行者会话；本轮所有长任务已终止。
- 受治理执行包尚未运行 `audit-execution` / review-gate / cleanup；恢复后须先核对三份输出并完成审计，不得把执行者自述当作验收。
- D001 II 总体仍为 `1848/1245/131`，剩余 `128` 包，`claims_complete=false`。
- 未进入受试者、OCR、病例审核、浏览器、视觉或用户指定测试者流程。
- 不删除 v1/v2/v3 配置及 slice60i/60j/60k 真实响应，它们是不可变回归证据。

## 下一安全动作

1. 先运行新提示补丁相关的 Agent/门禁聚焦回归、`py_compile`、JSON 解析和 `git diff --check`。
2. 离线重放 v3 最后一轮响应，确认新提示只影响未来调用、现有门禁仍正确拒绝错误锚点。
3. 完成 `phase5-slice60k-contraception-semantics-20260828` 执行包审计与父级 review 记录。
4. 仅在上述全部通过后，新建不可变 v4 配置并最多运行一次 MTPLX medium；不得覆写 v3 工件。
5. 任何技术绿色结果仍需逐条父级临床核对 p1325/p1326、IN-06 去重、筛选/基线节点和原始 DOCX 来源闭包。

