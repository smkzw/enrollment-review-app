# Execution Context: r01-binding-freeze-20260913

Created: 2026-09-13 10:26:07 CST
Objective: 落实R01绑定链的冻结输入和确定性来源校验，供后续双模型候选任务消费；不切换正式采信。
Task type: `E03`
Risk: `high`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `zcode/zcode/glm-5.3-flash:max -> pi/mtplx/mtplx-flash-next-optimized-speed:xhigh -> pi/openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `zcode` / `zcode` / `GLM-5.3-Flash`
- Review owner: Codex directly reviews worker outputs and final artifacts.

## Source Of Truth

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. 先读 .trellis/tasks/09-11-e2e-eligibility-review/R01_REVIEW_INPUT_20260913.md、runs/conference/r01-semantic-binding-review-20260913-retry/evidence_single_object.md、设计§17.1.1及相关Trellis后端规范。仅允许新增 app/domain/contracts/predicate_binding.py、app/services/predicate_binding_input.py、tests/v2/services/test_predicate_binding_input.py。复用当前authority、已发布RuleSet/ClausePack、current_fact_heads和EvidenceLocator的现有真实读取及来源验证，不复制哈希/日期算法、不造新调度器。实现供后续任务使用的冻结输入构建函数：当前规则组件与触发/例外谓词完整身份、原文定位、当前已校正事实对象/值/单位/日期/极性与定位，内容寻址身份；拒绝跨authority、缺失或伪造来源、旧修订及重复身份冲突。不把fact_type索引当语义证明，不输出已验证绑定或最终临床判断。源字段不足须明确抛错/未核实，不能猜值。测试用隔离临时库和合成资料，覆盖合法冻结、乱序同hash、校正导致hash变化、不同对象同值不合并、缺定位及跨节点拒绝。先搜索现有复用件，完整读取受影响定义。不得写原临床库、全局配置或其他线程文件，不修改消费链，使用apply_patch。报告实际改动、测试与未完成限制。

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
