# Phase 5.8d D001 单位级期别证据父级复核无损暂停

时间：2026-08-26 06:18 CST  
分支：`codex/phase5-clinical-facts-profile`  
工作树：`.worktrees/phase5-clinical-facts-profile`  
活动执行任务：`phase5-slice58k-d001-unit-phase-evidence-20260826`

## 本轮目标

在已验收的单位级期别证据设计基础上，为 D001 II 合并矩阵实际引用的 152 个冻结结构单元建立确定性证据视图、行级阻断汇总和异质代表包清单；同时收紧共同章节的语义提示，但不运行全部 137 个语义包、不启动病例审核或视觉测试，也不把矩阵主张误写成来源权威结论。

## 已完成但尚未最终验收

1. 三个受治理执行者均已返回，未使用替代路线：
   - Worker 01：生成单位级期别证据视图、报告、构建脚本与测试。
   - Worker 02：修改期别适用性提示合同与门禁测试。
   - Worker 03：只读独立复算数量、代表包、确定性和源文件哈希。
2. Worker 01 / Worker 03 一致报告：82 行、155 个来源锚点、152 个唯一单元；未运行任何语义包；`claims_complete=false`；D001 源 SHA-256 保持 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`。
3. 已生成 6 个代表包，覆盖 7 类异质分层；该清单只用于后续定向语义验证，不构成抽样临床结论。
4. 执行者聚焦测试曾通过，但父级尚未签署 review、metrics、review gate 或 `audit-execution`，因此本执行任务仍是未验收状态。

## 父级发现的阻断问题

### 1. Worker 02 采用了错误的词法门禁路线

`app/agents/phase_applicability.py` 新增了对理由文本中“同一义务家族”“全局广播”“部分闭合”“期别特异兄弟内容”等词语的命中/否定判断，并以此接受或拒绝模型结果。该做法把语义正确性退化为固定口令，违反本项目“不用正则或理由文本关键词修补语义错误”的质量边界。

恢复后必须：

- 删除新增词表、词法 helper、`_validate_shared_positive_evidence_boundary` 及其调用；
- 删除依赖这些固定词语的拒绝测试；
- 保留 Worker 02 对 v5 系统提示、修复提示和理由合同的语义强化；
- 增加反例测试，证明不念出固定术语、但结构化来源与两期共同义务证据闭合的合理中文理由仍可通过；
- 继续依赖既有结构化来源闭包、批次身份、目标所有权、处置一致性和同质分组门禁，不新增第二语义引擎。

### 2. `candidate_closed` 状态可能过度承诺

单位级研究视图把“结构明确为选定期别且与矩阵主张相容”的单元标为 `candidate_closed`。这仍可能被误读为临床语义已经闭合，而本切片只证明结构与来源相容。

恢复后先检查 `_anchor_assessment`、`_unit_status`、行级汇总及输出样本；若状态仅代表结构支持，应统一改为类似 `structurally_supported_candidate` 的非权威名称，并重建 JSON、测试和报告。不得仅因结构为 `phase_ii` 就宣称完整临床闭合。

## 当前文件与证据

- 生成器与测试：`.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/`
- 执行者报告：`runs/execution/phase5-slice58k-d001-unit-phase-evidence-20260826/worker_01.md` 至 `worker_03.md`
- 执行日志：`logs/execution/phase5-slice58k-d001-unit-phase-evidence-20260826/`
- 执行上下文：`context/phase5-slice58k-d001-unit-phase-evidence-20260826_execution_context.md`
- 执行计划：`plans/codex_execution_phase5-slice58k-d001-unit-phase-evidence-20260826.md`
- review 与 metrics 文件尚未由父级完成，不能作为验收证据。

## 恢复后的唯一安全顺序

1. 先移除 Worker 02 的理由文本词法门禁，保留提示合同强化并补无固定口令反例。
2. 复核并必要时重命名 `candidate_closed`，重建单位视图与报告两次并比较字节一致性。
3. 运行研究视图、期别适用性、跨章节合批、理由、矩阵和控制合同聚焦测试；再按影响范围运行协议回归、内存编译、Trellis validate 与 `git diff --check`。
4. Codex 复核实际 JSON 样本、状态统计、来源哈希与未运行语义包声明。
5. 仅在上述通过后填写 execution review/metrics，运行 review gate 与 `audit-execution`，再写验收检查点并清理本执行任务过程件。

## 明确禁止

- 不得把三个 Worker 报告视为最终验收。
- 不得在当前状态下运行 137 个语义包、病例审核、浏览器或独立视觉测试者。
- 不得把 `claims_complete` 改为 `true`。
- 不得修改 D001 原始方案或任何原始临床资料。
- 不得清理本执行任务的 prompts/runs/logs，直到父级验收和审计完成。

