# Codex Conference Review: phase5-slice61ak-v8-bounded-repair-audit-20260828

Date: 2026-08-28

## Verdict

有条件采纳并完成一项相邻修订。不同来源候选的越界内容改写可由系统恢复上一轮内容；同源未授权兄弟、候选数量变化和来源分区变化仍严格拒绝。v8 保持未水合、未通过和未发布，不允许沿相同单候选合同重跑。

## Boundary Compliance

- 两名参与者均只读审查，没有修改应用文件、调用 MTPLX、发布控制点或触碰范围外临床资料。
- 实际路由分别为 `google-antigravity/gemini-3.7-flash:high` 与 `grok-build/grok-4.6:medium`，均一次完成且无 fallback。
- 审查边界限定于 v8 第 4→5 次响应、有界恢复实现、确定性测试和恢复后的发布门禁；未扩展到其他方案包、受试者、OCR、Patient Profile 或视觉验收。
- Codex 保留最终工程和临床边界裁决。

## Hermes Governance

会商由 guard 生成数据包并由 runner 执行；日志记录请求/实际路由、session、`returncode=0` 和耗时。参与者输出只作为独立挑战证据，不自动构成接受结论。

## Participant Outputs Reviewed

- `general_pi_antigravity`：独立复现 v8 第 4→5 次恢复，确认不同来源 p805 改写被丢弃、获授权 p804 候选修订保留，并确认恢复后 `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` 拒绝正确。
- `general_grok46`：独立复现相同结果，确认 28 项聚焦测试和当时 988 项方案层回归；指出单候选位置修订不可能修复 p804 的跨候选范围拆分，并提出多冻结候选共享无关来源键的相邻测试缺口。

## Conference Panel Review

两名参与者都确认当前隔离规则对真实 v8 形态有效，且 p804 的无条件筛选兄弟候选必须继续被拒绝。Grok 对“下一次不能仍只修订豁免候选”的异议成立：`CONDITIONAL_EXEMPTION_SCOPE_SPLIT` 的正确修复对象是同一 p804 来源闭包内的两个候选，p805 应保持冻结。

Grok 指出的无关来源存在多个冻结候选时会误拒绝的问题成立。主线程已把无关来源匹配改为按来源键逐个消费并始终恢复上一轮对象，同时保持获授权来源键内未授权兄弟必须唯一且完全相等。新增正向测试后聚焦测试增至 29 项，方案层回归增至 989 项。

## Main-Venue Codex Review

采纳隔离修复和相邻多冻结候选修订；不采纳额外向 `_validate_bounded_output_repair` 传递候选位置。runner 在水合前只要存在 `repair_baseline_wire` 就必经 `_restore_bounded_wire_repair`，后置水合校验接收的是已经恢复的 wire；再建一套位置恢复会重复状态源并增加分歧风险。

`CONDITIONAL_EXEMPTION_SCOPE_SPLIT` 继续保留候选重分区权限。它与前一轮 `CONDITIONAL_EXEMPTION_BINDING_MISSING` 不同：前者的错误确实跨越同源兄弟候选，需要在来源全集守恒且 p805 冻结的前提下合并或重写 p804 候选；后者只允许单候选内部表达式重组。v8 的修订预算已经耗尽，因此该权限未在 v8 中执行。

## Codex Independent Verification

- 真实运行：v8 使用 `mtplx-qwen38-27b-optimized-quality:medium`，5 次响应、336.866189 秒，`hydrated=false`、`gate_accepted=false`、`claims_complete=false`。
- 真实 A4→A5 离线恢复：获授权 p804 候选采用 A5；同源 p804 冻结兄弟保持 A4；不同来源 p805 的越界改写恢复为 A4。
- 完整离线发布门禁：恢复后唯一阻塞为 `CONDITIONAL_EXEMPTION_SCOPE_SPLIT`，实体为 p804 无条件筛选候选 `pcc-624367a4829552da203e1c79`；临床拒绝门禁无额外问题。
- 聚焦合同：`29 passed in 0.09s`。
- 当前方案层全量回归：`989 passed, 58 warnings in 133.77s`。
- `compileall` 与 `git diff --check` 通过。
- 本切片不涉及 UI，因此未进行浏览器或视觉验收。

## Final Decision

接受有界恢复隔离实现及多冻结无关来源修订；拒绝 v8 临床/发布接受。不得覆盖 v8 工件，不得发布控制点，不得增加修订预算后重跑同一 v8。下一安全步骤应把 `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` 作为独立的新切片设计：只开放 p804 来源闭包的合并/重写，p805 继续冻结，并在任何新模型调用前先完成确定性来源守恒和跨候选豁免测试。
