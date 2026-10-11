# Phase 4 Slice 4.4 WP-44C 独立终局验收

你是全新上下文中的只读验收者。请站在资深后端架构审查者和临床证据系统质量负责人视角，独立判断 WP-44C 是否可以放行。不要修改任何文件，不要接受实现者的结论作为事实，不要读取工作区之外的原始临床资料。

从当前工作区根目录开始工作。

Hard boundaries:

- 只读验收，不修改应用、测试、Trellis、上下文或任何源文件。
- 不读取工作区外的原始临床资料。
- 不安装依赖，不执行生产写入，不启动外部临床数据处理。
- 仅返回验收报告；运行器负责保存输出，验收者不得用文件工具写报告。

Write exactly one output file: `runs/conference/phase4-wp44c-final-acceptance/codex_native_wp44c_acceptance.md`

上面的输出文件由运行器接收最终回答后保存，验收者不要自行写入。

## 权威约束

Read these files only:

按顺序阅读以下权威约束、重点实现和对应测试；可以读取这些文件在同一模块内直接导入的代码，但不得扩展到原始临床资料：

1. `AGENTS.md`
2. `.trellis/tasks/08-19-phase4-evidence-ocr-v2/prd.md`
3. `.trellis/tasks/08-19-phase4-evidence-ocr-v2/design.md`
4. `.trellis/tasks/08-19-phase4-evidence-ocr-v2/implement.md`
5. `.trellis/tasks/08-19-phase4-evidence-ocr-v2/research/slice44-detailed-contract-review.md`
6. `context/phase4-evidence-ocr-v2-slice44_execution_context.md`
7. `app/services/evidence_activation_service.py`
8. `app/services/evidence_api_command_service.py`
9. `app/services/evidence_command_identity_store.py`
10. `app/services/evidence_app_errors.py`
11. `app/api/v2/errors.py`
12. `app/services/job_service.py`
13. `app/services/evidence_upload_service.py`
14. `tests/v2/api/test_slice44_activation_fault_injection.py`
15. `tests/v2/api/test_slice44_build_matrix.py`
16. `tests/v2/api/test_slice44_409_contexts.py`
17. `tests/v2/api/test_slice44_refdoc_matrix.py`
18. `tests/v2/test_architecture_boundaries.py`

## 本轮必须独立核验的系统级问题

1. 激活和回滚事务在陈旧修订、快照发布后故障等任意失败点都不会留下半激活快照、孤立事件、错误 current 指针或错误候选状态。应用冲突记录本身可以保留，但临床权威状态必须回滚。
2. 构建完整处理修订在候选与幂等记录已经提交、进程随后中断时，同一幂等键重试能恢复同一候选并完成，而不是永久失败或创建第二个候选。
3. 同一幂等键提交不同命令时，409 必须基于持久化的首次规范化命令给出真实字段差异；不得出现伪造占位文本，也不得因进程重启丢失首次命令。
4. 校对、完整修订、激活、回滚、被提及资料确认/修改/解除等所有写入口的 409 都具有用户可理解且可恢复的结构：提交值、当前记录、字段差异、下一步动作；历史事件计数和 current 指针不得被失败请求污染。
5. API 错误映射层不得识别或翻译存储层异常；存储异常必须在服务公开边界翻译为应用错误。任意层级嵌套的内部异常、SQL、路径、堆栈或技术字符串不得进入用户响应。
6. 被提及资料的确认、修改、解除必须覆盖同键同命令、同键不同命令、陈旧修订、新键重试、历史计数和 current 链头不漂移等矩阵。
7. 所有 current 读取只依赖 episode 成对活动指针，不得按时间、ID、列表顺序、状态或 legacy 字段猜测。

## 已报告但必须自行复核的锚点

- WP-44C 聚焦回归：72 passed。
- 新增缺陷矩阵与架构检查：91 passed，2 subtests。
- 相关 API/服务聚焦回归：82 passed。
- V2 全量：1534 passed，130 warnings，2 subtests。
- 改动范围 Ruff 通过；生产代码 Pyright 0 errors；`git diff --check` 通过。

请至少运行足以独立证实关键语义的聚焦测试；若认为必要，可补充全量或静态检查。不要因为测试名存在就假定覆盖充分，要查看断言和实现控制流。

## 输出格式

第一行只写 `ACCEPT` 或 `REJECT`。随后按严重度列出发现，必须给出文件和行号、可复现路径、系统级原因。没有问题时明确写“无 P0/P1/P2 未闭合问题”，并列出实际运行的检查和仍存在但不阻塞 WP-44D 的残余风险。验收者只做判断，不改代码。
