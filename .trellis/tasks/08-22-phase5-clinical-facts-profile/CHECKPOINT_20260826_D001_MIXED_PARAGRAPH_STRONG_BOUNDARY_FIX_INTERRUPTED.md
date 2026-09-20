# Phase 5.8d D001 混合段落强边界修复中断检查点

## 暂停结论

- 当前状态：`in_progress / interrupted`，不是实现验收、D001 临床验收或发布验收。
- 用户要求立即无损暂停后，活动续修执行已用中断信号停止；复核时未发现该任务的执行器、续修会话或子进程残留。
- 当前工作树的大量既有 Phase 5 改动全部按原状保留，没有清理、回滚或覆盖其他改动。
- `claims_complete=false`。本轮未运行全部语义包、受试者审核、浏览器、视觉或独立测试者工作。

## 三层状态边界

### 1. 上一已接受基线

- D001 II 冻结清单：`1840` 个全文单元、`1298` 个待处置目标、`137` 个计划包。
- 全局章节纳入当前固定 II 期项目的代表性真实运行已接受，但不外推为 II/III 期共用。
- 恢复期间仍不得把代表包结果当作全部 137 包的临床闭包。

### 2. 首轮 58p 失败诊断

- 工作项：`phase5-slice58p-mixed-paragraph-atomization-20260826`。
- 路线：`codex-subagent/codex/gpt-5.6-luna:max`；无模型替换。
- 初始三个执行会话：Worker 01 `01a03ced-833c-7553-9d50-331453863d77`；Worker 02 `01a03ced-831f-7462-b56c-c75cd8dd474b`；Worker 03 `01a03d01-9789-7952-9290-b966a48b8748`。
- 初次真实重建生成 `1857/1304/138`，相对已接受基线为 `+17/+6/+1`；4 个父段生成 21 个原子。
- `body.p729`、`body.p801`、`body.p815`、`body.p1237` 出现 17 个不完整临床片段。比例 `1:1:1`、`2:2:1`、剂量列表、括号内期别参照和访视清单被软标点/期别标记错误切断。
- `artifacts/phase5-slice58p-mixed-paragraph-atomization-20260826/diff-qc.json` 已将 `semantic_atom_boundary` 标为 `needs_revision`。该目录只保留为失败诊断证据，不得作为接受产物。
- 原始方案冻结副本 SHA-256 保持 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`；未修改源文件。

### 3. 中断时的强边界修复中间态

- 父级已向同一 Worker 01 会话发出续修：只允许在 `。！？!?；;` 或换行等强边界处分句，禁止在比例、剂量、括号参照和访视列表内部切分；相邻相同期别签名应合并。
- 续修提示：`prompts/execution/phase5-slice58p-mixed-paragraph-atomization-20260826/worker_01_followup_01.md`。
- 用户要求暂停时，同一会话续修正在运行；已中断，未生成续修报告、测试结果、真实重建或父级验收。
- 中断前部分代码已落盘到 `app/protocols/full_protocol_coverage.py`，可见 `_PARAGRAPH_STRONG_BOUNDARY_RE`、`_paragraph_clauses`、`_paragraph_clause_groups` 和更新后的 `_paragraph_atom_slices`。这只是未验证中间态，禁止直接接受。
- 当前实现文件 SHA-256：`9aa477b404e94b4786c8b178b6d4163fed3e83ce3875b4cabfaadfcae2504504`，mtime `2026-08-26 15:57:41 +0800`。
- 当前测试文件仍是首轮假设版本，SHA-256：`59818fd8ab8a547e5d931b5445a36bf0a342a890c5a8cc8a489b58d6027558e8`。其中要求在同一个强句内拆成 shared/II/III 三段的用例已被父级判为不安全，恢复时必须改写，而不是让实现迎合该断言。
- 初次失败 QC 文件 SHA-256：`db043451530f4d131a6fa87ede0c7df138c24fda9c7300100c7114c519b6b0cd`。

## 必须保留的证据

- `artifacts/phase5-slice58p-mixed-paragraph-atomization-20260826/`
- `runs/execution/phase5-slice58p-mixed-paragraph-atomization-20260826/`
- `logs/execution/phase5-slice58p-mixed-paragraph-atomization-20260826/`
- `context/phase5-slice58p-mixed-paragraph-atomization-20260826_execution_context.md`
- `plans/codex_execution_phase5-slice58p-mixed-paragraph-atomization-20260826.md`
- `prompts/execution/phase5-slice58p-mixed-paragraph-atomization-20260826/`
- `CHECKPOINT_20260826_D001_MIXED_PARAGRAPH_ATOMIZATION_REBUILD_NEEDS_REVISION.md`

## 下一安全动作

1. 先读取本检查点和当前 `full_protocol_coverage.py` 的未提交差异，确认强边界修复是否完整；不得假设中断前代码处于一致状态。
2. 优先恢复原 Worker 01 会话 `01a03ced-833c-7553-9d50-331453863d77`；若同会话技术上不可恢复，必须按现行受控路线重新建立任务并明确记录，不得静默替换模型。
3. 完成强边界实现，并改写错误的首轮测试假设。至少覆盖：同一强句中的比例、剂量、括号期别参照和访视列表保持完整；只有两个以上完整强句且期别签名不同才允许原子化；相邻同签名强句合并；来源片段按字符区间无重叠、可完整回放。
4. 先运行最小聚焦测试和相邻协议回归。测试通过后，用新的产物目录重建 D001，禁止覆盖首轮 58p 失败证据。
5. 人工核对 `body.p729`、`body.p801`、`body.p815`、`body.p1237` 的完整临床义务边界，再复核受影响的 package 79/80/111。
6. 上述步骤通过前，不运行全部 138 包，不进入受试者、浏览器、视觉或独立测试。

## 暂停时未做事项

- 未对中断后的代码运行任何测试、编译、D001 重建或语义 Provider。
- 未生成新的接受报告、review gate、execution audit 或临床结论。
- 未清理首轮失败产物、缓存或执行记录，以保证可追溯恢复。
