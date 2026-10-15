Trellis SessionStart context loaded. Continuing bounded read-only review; no writes, no agents, no tests.

# 供审报告：adoption-boundary delta（只读，未运行测试）

先声明：上一份报告未覆盖本次新代码；本报告只审此次冻结的三个面。Bash 仍被拒（无法计算 git diff），本轮 4 次聚焦读取完成，未写文件。

## 结论：支持 no-findings（无 must-fix）

**边界一：建议不会被静默强制化 —— 证据充分。**
- 保留端只在整单元路径生效，且源头必须同时满足（`app/services/protocol_control_restricted_source.py:175-189`）：`force=="recommended"`、`partial_wire` 存在、该单元在 wire 中 disposition 为 `REQUIRED_PROCEDURE`（`:176-179`）、且同单元存在**另一条** review 决策为 `additional_requirement` 的 required/prohibited ACTION（`:180-184`，`other != index` 保证 distinct）。任一不满足 → `source_action` False → 整批拒绝（`:190-194`）。
- 输出端不存在强制化通道：disposition 一律重建为 `RESTRICTED_SOURCE` 并丢弃 linked procedure id（`:569-572`），`source_force` 原样保留（`:563`），最终 gate 复核（`:577`）；投影 `recommended` 分支输出 `display_label="方案建议"`、reason 前置"本项为方案建议，不作为独立强制入排条件"、`status="restricted"`、`fact_refs=()`（`eligibility_review_projection.py:1432-1454`）。字面量合法且贯穿四个生产点（`protocol_controls.py:2155/2250` 允许 `recommended`；`restricted_source.py:287/406/563/789` 一致保留）。
- 正例（测试现存）：`test_protocol_control_execution.py:589-654`，`force=recommended` + 两条 `additional_requirement` + REQUIRED_PROCEDURE → 两条 restricted records、force 保留（`:640-641`）、投影 `方案建议` 且含非强制文案（`:650-652`）；`force=required` 走旧门同样保留，投影仍 `方案补充要求`（`:654`）——建议标签不会污染必做条目。
- 负例：`all_recommended`（无 distinct 必做兄弟）→ None（`:623-625`）；`definition_sibling`、`unread_prefix`、`transport`、`wrong_detail` → None（`:615-633`）。单 temporal 拒绝保持：逐条路径 `gate.py:4930-4933` 要求 `decision_functions==["action"]` 且 force∈{required,prohibited}，recommended 无法走 `_restricted_statement_batch_from_review`。

**边界二：整单元不会丢 required 兄弟 —— 证据充分。**
- 受控单元按 `by_unit[unit_id]` 全量产生记录，逐条保留 quote/force/时间/范围（`restricted_source.py:523-564`）；兄弟为必做时投影走非建议分支。
- 删除候选有双向约束：仅限完全落在 restricted_units 内的候选（`:513-522`），共享候选或残留候选触碰受控 span 即整批拒绝；兄弟只会以 restricted record 形式保留，不存在静默丢失通道（`:577` 末端 gate 兜底）。
- 危险反例（反证当前防护方向）：若 `:180-184` 只扫"同单元任意陈述"而不要求 `additional`+required/prohibited，仅建议单元即可被整单元保留；若允许 recommended 走逐条独立路径，`["action","time_validity"]` 型时间项会被误判 standalone。当前两处都收紧，故反例不成立。

## 可选观察（非 must-fix，冻结外，供 owner 决定）
1. 覆盖缺口：新前置"单元 disposition 必须 REQUIRED_PROCEDURE"的**否定支**（recommended + 必做兄弟但单元为 OTHER_CONTROL_CANDIDATE → 拒绝）没有直接参数化用例；现有 defect 只覆盖 force/兄弟性质/源覆盖/传输。代码上该支会经 `:176-179` 拒绝并可回落 `_restricted_statement_batch_from_review` 再拒，但无合成证据。另本测试只断言 index 1 的 force 与投影，兄弟 index 0 的 `方案补充要求` 标签未直接断言。
2. 一致性说明（低风险）：新条件读 `result.partial_wire.dispositions` 原始 wire，其"valid"性由调用序保证（`_whole_unit_restriction:437-441` 先 hydrate+gate 再于 `:447` 调用）；`execution.py:2894-2895` 的 preserved-proof 路径先不校验，但随后必须经 `restricted_batch_from_review` 校验通过才成立，无采用通道。

## 未读依赖与独立性
`hydrate_protocol_control_agent_output`（原始 wire 与 hydrated disposition 是否可能改写/清空，未验证其内部）、`check_protocol_control_batch_candidates` 内部、`display_label/status_label` 在投影之外的消费方（UI/评估侧）、owner 集中测试窗口结果、相对 `674dfffa` 的 diff（Bash 拒绝）。本报告为工程审查，合成测试证据非验收，无生产运行、无临床/强制化采用结论；模型独立性受限（可能与产品路线同属 DeepSeek 家族），未执行任何产品临床工作。
