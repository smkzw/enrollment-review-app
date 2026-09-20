# Phase 5.8d D001 只读异构回放无损暂停

日期：2026-08-31  
分支：`codex/phase5-clinical-facts-profile`  
状态：**已暂停，可恢复，未完成，`claims_complete=false`**

## 本轮已完成

- 通用两阶段方案控制点链路继续保持项目中立：原始 DOCX/PDF 仅结构化读取一次，全清单进入一次高召回发现，仅候选与不确定项进入深度语义分析。
- 深度候选增加同会话语义发布门禁；候选批次身份、来源范围、阶段一致性和条件豁免范围可在原模型会话内修复。
- 相关聚焦回归曾完成 `67 passed`；加入只读回放入口与反过拟合测试修正后，相关范围完成 `30 passed`。当时 `py_compile` 与 `git diff --check` 通过。
- 词汇中立真实模型冒烟已完成，记录位于 `runs/protocol_control_smoke/quality-positive-control-packed48-v4-20260831/run_record.json`：发现批次 1 个，深度批次 5 个，结果为 `hydrated_candidate_control_package`，正式目录未物化，`claims_complete=false`。
- 冒烟中的深度结构修复发生在同一会话；发布语义修复能力由确定性服务集成测试证明，本次真实冒烟未触发发布语义修复，不得混称。

## D001 回放中断点

- 只读来源：`/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx`
- 暂停时 SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- 明确研究期别：`phase_ii`；没有使用固定优先级推断。
- 回放目录：`runs/protocol_control_replay/d001-phase-ii-20260831/`
- 权威数据库：`data_v2/enrollment-review-v2.sqlite3`。
- 来源冻结任务：`384a7b3b802d46009e039c81ea7f7cc0`。前 6 个来源处理步骤已完成；`generate_draft` 使用约定的 `SMOKE_SOURCE_STOP_AFTER_FREEZE` 停止，因此该任务的 `failed_final` 是只读回放入口的预期边界，不代表来源解析失败。
- 控制点任务：`3259ab5f070447c3938ff2de5f45c9cd`。共 39 个发现批次；`discovery_0001` 至 `discovery_0005` 已完成并各有 1 个检查点，`discovery_0006` 在用户暂停时被中断，`discovery_0007` 至 `discovery_0039` 及确定性闭包均未开始。
- 停止后未发现 `run_protocol_control_smoke.py` 或其审核子进程。数据库仍显示任务/第 6 批为 `running`，这是进程中断后的持久状态，恢复前必须先走恢复语义，不得据此重复启动一个新任务。
- 未生成 `run_record.json`，未形成 D001 正式控制点目录，未做 D001 临床验收；SAR 回放尚未开始。

## 边界与未完成项

- D001 和 MG-K10-SAR 仅为只读异构验收语料，不是共享规则、评分、药物、疾病或时间点硬编码来源。
- 候选到正式控制点目录的物化尚未完成。
- 受试者审核、Patient Profile、前端展示、浏览器验收及独立复核均未进入本切片。
- 本次暂停未清理回放数据库、检查点、冒烟记录或诊断资料。
- 本轮单独启动的 `127.0.0.1:8003` Quality 模型服务已正常停止；未对其他模型服务执行启停操作。

## 下一安全动作

1. 先读取本检查点和数据库，不重新解析原始方案。
2. 核对现有 runner 是否能以任务 `3259ab5f070447c3938ff2de5f45c9cd` 恢复：将中断的 `discovery_0006` 按租约/中断恢复规则重新排队，复用 `0001-0005` 检查点。
3. 若 CLI 尚不能恢复既有任务，先补一个复用现有 SQLite 任务的恢复入口并做确定性测试；不得直接新建全量回放造成重复模型调用。
4. D001 完整闭包并独立验收后，再以完全相同的提示、合同和门禁运行 SAR III 期只读回放；不得因任一语料加入项目特异修补。
