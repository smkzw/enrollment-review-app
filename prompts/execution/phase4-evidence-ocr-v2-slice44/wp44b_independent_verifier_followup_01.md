# WP-44B 独立验收：同会话修复后复验

继续你上一轮只读独立验收。不要修改任何文件，不要读取工作区外资料，不要重新评审未变更的范围。请集中复验上一轮三个 P1 和风险量化 P2；主动构造旁路反例，不能只照抄下列结果。

## Hard boundaries

- Read-only review. Do not edit, create, delete, move, or format application, test, task, or source files.
- Do not read raw clinical material or any path outside the current workspace.
- You may run read-only commands and tests. Test-generated temporary data must remain under the test runner's temporary directory.
- Runner-managed report path: `runs/execution/phase4-evidence-ocr-v2-slice44/wp44b_independent_verifier_followup_01.md`. Return the complete report in the final response; the runner writes it.
- Do not write any other output file.

Read these files only:

- `AGENTS.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/prd.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/design.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/implement.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/research/slice44-detailed-contract-review.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/research/slice4-goldset-coordinate-spike.md`
- `context/phase4-evidence-ocr-v2-slice44_execution_context.md`
- `runs/execution/phase4-evidence-ocr-v2-slice44/worker_02.md`
- `app/evidence/effective_text.py`
- `app/evidence/locator.py`
- `app/services/evidence_risk_service.py`
- `app/services/evidence_correction_service.py`
- `app/services/evidence_locator_service.py`
- `app/services/evidence_referenced_document_service.py`
- `app/services/evidence_revision_builder.py`
- `app/services/evidence_revision_workflow.py`
- `app/services/evidence_activation_service.py`
- `app/storage/evidence_locator_repositories.py`
- `app/storage/evidence_repositories.py`
- `app/storage/evidence_locator_models.py`
- `app/storage/ocr_models.py`
- `app/domain/contracts/evidence_locator.py`
- `app/services/evidence_upload_service.py`
- `tests/v2/evidence/test_locator.py`
- `tests/v2/evidence/test_risk_scan.py`
- `tests/v2/evidence/test_slice44_effective_text_engine.py`
- `tests/v2/evidence/test_slice44_locator_engine.py`
- `tests/v2/domain/test_slice44_contracts.py`
- `tests/v2/services/test_slice44_activation_service.py`
- `tests/v2/services/test_slice44_correction_service.py`
- `tests/v2/services/test_slice44_locator_service.py`
- `tests/v2/services/test_slice44_referenced_document_service.py`
- `tests/v2/services/test_slice44_revision_workflow.py`
- `tests/v2/services/test_slice44_risk_service.py`
- `tests/v2/services/test_slice44_upload_pointer_authority.py`
- `tests/v2/storage/test_slice44_repositories.py`
- `tests/v2/storage/test_migration_0010.py`

## 上一轮 P1 的修复声明（必须独立核实）

1. **重叠 occurrence**
   - 忽略空白匹配在命中后从下一原文字符继续搜索，`AAA` 中 `AA` 得到两个重叠 occurrence。
   - 纯文本和原生字符坐标两层均有反例；重复 occurrence 必须降级为页内摘录且 `bbox=None`。

2. **被提及资料追加链**
   - 登记修订和满足修订均以 `all_ids - superseded_ids` 选择唯一链头，多链头拒绝猜测。
   - 确定性识别来源与用户复核状态拆分：自动生成仍只能是 `proposed`；用户确认后保留 `deterministic_candidate` 来源，并以 `user_reviewed=true` 证明是后续人工复核修订。
   - 增加确认→修改→解除多步不可变链、provided 后解除关联、历史回放；确认/修改/解除原因进入修订载荷。

3. **激活幂等与仓储旁路**
   - 未提供 `event_id` 时按完整命令哈希生成稳定事件 ID，并可按命令哈希回放原事件冻结投影。
   - `EvidenceActivationEventRepository.append()` 永久拒绝孤立事件；唯一写入口 `append_and_switch()` 在同一事务校验来源指针对、episode/snapshot/revision 归属、完整修订、READY 生产候选、历史回滚目标与目标快照已启用，然后追加事件并乐观锁切换两条当前版本指针。
   - 服务的首次快照启用、事件、成对指针和候选状态仍处于同一外层事务；故障注入和真实多连接竞态验证无部分提交。
   - 新反例覆盖未就绪候选直接仓储启用、无历史回滚、陈旧来源版本对、base/不存在修订和孤立 append。

## 风险量化证据

- `tests/v2/evidence/test_risk_scan.py::test_risk_seed_metric_miss_zero_and_fp_within_ten_percent` 对全部 eligible 页建立分母。
- 冻结结果记录：关键风险漏检 `0/26`；干净页页面级误报 `0/13 = 0.0%`；覆盖 `23/23` 页。
- 这只证明确定性风险规则种子集，不冒充扫描/照片 OCR 模型的一般准确率。

## 父任务最新确定性锚点

- 修复相关聚焦回归：`170 passed, 32 warnings`。
- 合同/引用资料/仓储聚焦：`142 passed, 32 warnings`。
- 全部 V2：`1451 passed, 130 warnings, 2 subtests passed`。
- 变更范围 Ruff：通过。
- 变更生产模块 Pyright：`0 errors, 0 warnings, 0 informations`。
- `git diff --check`：通过。

## 输出

返回 `ACCEPT` 或 `REJECT`，并按 P0/P1/P2 给出文件行号、可复现证据、系统级原因。若接受，明确列出已复验的不变量与不阻断 WP-44C 的残余风险。不要把父任务测试结果当作你的独立执行证据；无法在只读沙箱运行的测试应清楚区分为父任务锚点。
