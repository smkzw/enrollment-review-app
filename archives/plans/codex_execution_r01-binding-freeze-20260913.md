# Codex Execution Plan: r01-binding-freeze-20260913

Objective: 落实R01绑定链的冻结输入和确定性来源校验，供后续双模型候选任务消费；不切换正式采信。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 先读 .trellis/tasks/09-11-e2e-eligibility-review/R01_REVIEW_INPUT_20260913.md、runs/conference/r01-semantic-binding-review-20260913-retry/evidence_single_object.md、设计§17.1.1及相关Trellis后端规范。仅允许新增 app/domain/contracts/predicate_binding.py、app/services/predicate_binding_input.py、tests/v2/services/test_predicate_binding_input.py。复用当前authority、已发布RuleSet/ClausePack、current_fact_heads和EvidenceLocator的现有真实读取及来源验证，不复制哈希/日期算法、不造新调度器。实现供后续任务使用的冻结输入构建函数：当前规则组件与触发/例外谓词完整身份、原文定位、当前已校正事实对象/值/单位/日期/极性与定位，内容寻址身份；拒绝跨authority、缺失或伪造来源、旧修订及重复身份冲突。不把fact_type索引当语义证明，不输出已验证绑定或最终临床判断。源字段不足须明确抛错/未核实，不能猜值。测试用隔离临时库和合成资料，覆盖合法冻结、乱序同hash、校正导致hash变化、不同对象同值不合并、缺定位及跨节点拒绝。先搜索现有复用件，完整读取受影响定义。不得写原临床库、全局配置或其他线程文件，不修改消费链，使用apply_patch。报告实际改动、测试与未完成限制。 | `runs/execution/r01-binding-freeze-20260913/worker_01.md` |

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
