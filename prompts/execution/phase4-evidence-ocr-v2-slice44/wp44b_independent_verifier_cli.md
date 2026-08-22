# WP-44B 独立验收（CLI 兼容路线）

你是 fresh-context 独立检查者，只读审查，不得修改任何文件。当前目录就是工作树根目录。

## 背景与边界

- 这是 Phase 4 / Slice 4.4 / WP-44B 的最终独立验收；WP-44C 尚未开始。
- 方案与原始临床资料不在本轮范围；不要读取工作树外临床资料。
- 重点是系统级正确性，不是确认“流程能跑”。
- 工作者输出和本提示只作为线索，实际代码、测试、数据库约束和运行结果才是证据。
- 不要因为已有测试通过就降低审查强度；主动构造反例，尤其检查旁路和竞态。

Hard boundaries:

- Read-only review. Do not edit, create, delete, move, or format application, test, task, or source files.
- Do not read raw clinical material or any path outside the current workspace.
- You may run read-only commands and tests. Test-generated temporary data must remain under the test runner's temporary directory.
- Runner-managed report path: `runs/execution/phase4-evidence-ocr-v2-slice44/wp44b_independent_verifier_cli.md`. Return the complete report in the final response; the runner writes it.
- Do not write any other output file.

Read these files only:

- `AGENTS.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/prd.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/design.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/implement.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/research/slice44-detailed-contract-review.md`
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
- `tests/v2/evidence/test_slice44_effective_text_engine.py`
- `tests/v2/evidence/test_slice44_locator_engine.py`
- `tests/v2/services/test_slice44_activation_service.py`
- `tests/v2/services/test_slice44_correction_service.py`
- `tests/v2/services/test_slice44_locator_service.py`
- `tests/v2/services/test_slice44_referenced_document_service.py`
- `tests/v2/services/test_slice44_revision_workflow.py`
- `tests/v2/services/test_slice44_risk_service.py`
- `tests/v2/services/test_slice44_upload_pointer_authority.py`
- `tests/v2/storage/test_slice44_repositories.py`
- `tests/v2/storage/test_migration_0010.py`

## 已修复但需独立重验的历史 P1

1. 完整修订必须永久绑定唯一生产候选和冻结输入；不能由其他候选启用。
2. 激活幂等身份必须包含候选，重放必须返回事件冻结结果，不能随当前指针漂移。
3. 未知构建异常必须退出 `processing`，可重试/取消/陈旧恢复均可审计。
4. SQLite 竞态测试必须是真正多连接并发，而不是顺序模拟。
5. 激活与回滚事件在仓储层也必须拒绝 base 修订目标；不得仅依赖服务层。

## 验收重点

- occurrence-aware 定位：同源字符/词坐标闭包、重复文本消歧、四级诚实降级、无伪 bbox。
- 风险扫描：只读原 OCR，否定/肯定、数值、小数点、单位、日期旁路提示；不得写临床事实、规则、判断，也不得弱化且/或。
- 校对：原 OCR 不变，关键语义二次确认，重叠/链分支/作用域旁路均拒绝，历史完整修订可精确回放。
- 完整修订：冻结页、OCR、定位、风险核对、校对、元数据、被提及资料及满足关系的完整闭包；半成品不留可激活根。
- 候选状态：失败、未知异常、取消、重试、陈旧恢复均无永久处理中，幂等与冻结输入不漂移。
- 激活/回滚：只接受 READY 完整版本；ActivationEvent、快照首次启用、候选状态和审核节点成对指针同事务；失败/竞态不部分提交；旧事件重放稳定。
- current 读取和增量上传基线只认审核节点成对指针，不按时间、状态、列表顺序或 legacy 字段猜测。
- 数据库约束、仓储 API 和服务 API 必须共同封死旁路。

## 已有确定性锚点（请核实而非照抄）

- WP-44B 相关持久化/迁移/激活聚焦：`130 passed`。
- 全量 V2：`1443 passed, 130 warnings, 2 subtests passed`。
- 变更范围 Ruff：通过。
- 变更生产模块 Pyright：`0 errors, 0 warnings, 0 informations`。
- `git diff --check`：通过。

你可运行只读测试、查询和临时目录内的探针；不要改文件。输出必须包含：

1. `ACCEPT` 或 `REJECT`。
2. 按 P0/P1/P2 排序的发现，给出文件与行号、可复现证据、系统级原因和建议修复方向。
3. 若无阻断问题，明确说明你重验了哪些旁路/竞态/历史回放不变量。
4. 仍存但不阻断进入 WP-44C 的残余风险。
