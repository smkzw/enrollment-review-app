# Phase 5.8d D001 混合期别复合段落原子化重建检查点

## 状态

- 当前状态：`needs_revision`，不是 Phase 5.8d 临床或发布验收。
- 工作项：`phase5-slice58p-mixed-paragraph-atomization-20260826` / `worker_03`。
- 只在工作区内执行；未读取或修改工作区外原始/生产路径。
- `claims_complete=false`；未调用语义 Provider，未启动受试者、浏览器或视觉测试。

## 已完成

- 使用工作区冻结 D001 DOCX 副本完成真实只读重建。副本 SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`；重建前后哈希、大小和 mtime 未变化。
- 重建结果：结构块 `3581`、期别图块 `3405`、全文单元 `1857`、待处置目标 `1304`、计划包 `138`。
- 相对已接受 5.8o 的 `1840/1298/137`，变化为 `+17/+6/+1`；4 个混合父段生成 21 个原子单元。
- 所有原子片段均能从父段原文按顺序、无重叠、完整回放；package 79 的目标/来源/上下文闭包和唯一性检查通过。
- 测试：58p 聚焦 `6 passed`；相邻协议回归 `109 passed, 5 warnings`；产物契约重载、内存编译和定向 `git diff --check` 通过。

## 阻断观察

4 个混合父段共有 17 个原子在强句界前截断。已记录的典型来源为 `body.p729`、`body.p801`、`body.p815` 和 `body.p1237`；`body.p729#atom-1` 的内容仅到“按照1”，比例和给药安排在后续片段中。此证据证明字节级回源，不证明语义义务边界正确。

固定 ordinal 79 已因新增前置原子单元发生成员漂移：旧 package 79 为 `body.p806` 至 `body.p816`，新 package 79 为 `body.p801#atom-0` 与 `body.p802` 至 `body.p805`；旧 `body.p815` 相关原子位于新 package 80。旧 package 79 语义输出不得重放到新包。

## 证据文件

- `artifacts/phase5-slice58p-mixed-paragraph-atomization-20260826/coverage_manifest.json`
- `artifacts/phase5-slice58p-mixed-paragraph-atomization-20260826/frozen_phase_plan.json`
- `artifacts/phase5-slice58p-mixed-paragraph-atomization-20260826/package-0079-agent-input.json`
- `artifacts/phase5-slice58p-mixed-paragraph-atomization-20260826/package-0079-review.json`
- `artifacts/phase5-slice58p-mixed-paragraph-atomization-20260826/diff-qc.json`
- `artifacts/phase5-slice58p-mixed-paragraph-atomization-20260826/verification-results.json`
- `artifacts/phase5-slice58p-mixed-paragraph-atomization-20260826/execution/d001-ii-phase-closure-20260826-slice58p.json`

## 安全恢复动作

先修正原子边界合同/实现，使期别专属片段按完整临床义务或安排切分，并增加 D001 真实反例回归；然后重跑 58p 聚焦测试、真实重建、差异/QC 和受影响 package 79/80/111 复核。修复和复核完成前，不运行全部 138 包，不进行受试者或视觉测试。
