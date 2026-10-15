# WP-44B 独立验收：第二次修复后最终复验

继续同一个只读独立验收会话，只复验上一轮报告中的 P1-1、P2-1、P2-2 及其传播边界。主动构造反例，但不要重复未变更范围的长篇审查。

## Hard boundaries

- Read-only review. Do not edit, create, delete, move, or format application, test, task, or source files.
- Do not read raw clinical material or any path outside the current workspace.
- You may run non-interactive read-only tests. Never use `pytest --trace`, `--pdb`, an interactive debugger, or any command that waits for user input.
- Test-generated temporary data must remain under the test runner's temporary directory.
- Runner-managed report path: `runs/execution/phase4-evidence-ocr-v2-slice44/wp44b_independent_verifier_followup_02.md`. Return the complete report in the final response; the runner writes it.
- Do not write any other output file.

Read these files only:

- `AGENTS.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/prd.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/design.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/implement.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/research/slice44-detailed-contract-review.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/research/slice4-goldset-coordinate-spike.md`
- `app/domain/contracts/evidence_locator.py`
- `app/services/evidence_activation_service.py`
- `app/services/evidence_referenced_document_service.py`
- `app/storage/evidence_locator_repositories.py`
- `app/storage/evidence_locator_models.py`
- `app/storage/models.py`
- `tests/v2/evidence/test_risk_scan.py`
- `tests/v2/domain/test_slice44_contracts.py`
- `tests/v2/services/test_slice44_activation_service.py`
- `tests/v2/services/test_slice44_referenced_document_service.py`
- `tests/v2/storage/test_slice44_repositories.py`
- `tests/v2/storage/test_migration_0010.py`
- `runs/execution/phase4-evidence-ocr-v2-slice44/wp44b_independent_verifier_followup_01.md`

## 修复声明（必须独立核实）

### 仓储级激活旁路

- `EvidenceActivationEventRepository.append_and_switch()` 现在自身开启嵌套保存点，并将以下动作作为一个仓储级原子单元：校验当前来源版本对、快照/审核节点/完整修订归属、生产候选 READY 状态、候选冻结 `expected_revision` 与事件一致、候选输入与完整修订一致、历史回滚目标、目标快照已启用；追加 ActivationEvent；乐观锁切换审核节点两条权威指针；追加候选 `READY→ACTIVE` 事件。
- 服务不再在仓储返回后另行转换候选；只消费仓储返回的 ACTIVE 候选。
- 新反例证明：
  1. 已启用快照上的合法 READY 新候选经仓储直调后，事件、指针和候选 ACTIVE 同时成立。
  2. `candidate.expected_revision != event.expected_revision` 时拒绝，原事件数、权威指针和候选 READY 状态均不变。
  3. 候选 ACTIVE 事件故障注入时，ActivationEvent、快照首次启用、成对指针和候选状态四面全部回滚。

### 风险分母冻结

- 种子集测试除阈值外，现明确断言：`total_gold_kinds == 26`、`clean_pages == 13`、`risk_pages == 10`、`processed_pages == eligible_pages == 23`、`unprocessed_page_ids == ()`。

### 操作原因审计

- `ReferencedDocumentRevision` 合同要求所有 `revision > 1` 的追加修订都有非空、去空白后的原因。
- `confirm()`、`revise()`、`dismiss()` 均在服务入口拒绝空白原因，原因进入不可变修订载荷；合同和服务均有反例。

## 父任务最新确定性锚点

- 修复相关聚焦回归：`209 passed, 32 warnings`。
- 全部 V2：`1455 passed, 130 warnings, 2 subtests passed`。
- 变更范围 Ruff：通过。
- 变更生产模块 Pyright：`0 errors, 0 warnings, 0 informations`。
- `git diff --check`：通过。

## 输出

返回 `ACCEPT` 或 `REJECT`。按 P0/P1/P2 给出文件行号、可复现证据、系统级原因。若接受，明确说明 WP-44B 可以进入 WP-44C，并列出不阻断的残余风险。父任务测试结果只能作为外部锚点，不能冒充你的独立执行证据。
