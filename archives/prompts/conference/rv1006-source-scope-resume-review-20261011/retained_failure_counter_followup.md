# 1006V1 旧失败保留与新读取计数：实际修改审阅

继续同一批准C03，只读当前源码和合成测试，不读真实方案/病例、数据库、env或私有运行目录，不改文件，不调用产品模型。不得将工程审阅称医学批准。

上轮建议现已实现，但需要核实际代码而非重复建议。app/workflow/errors.py StepFailure新增retained_failure，必须非重试且带诊断；app/services/protocol_control_execution.py::_execute_deep只有preserve_unresolved的实际旧证明重核通过、不可合法转换的负答才设置该标记。候选仍失败/adopted=false/0新调用，旧回执不改。

app/workflow/runner.py::_commit_step_failure由当前异常覆盖保留诊断中的保留标记，不信复制过来的标记；_continue_independent_after_failure仅显式原policy、原白名单/前缀、原max_failed_steps=2生效。以前的失败计数排除经当前执行器重核保留的旧失败；缺标记按新失败计；新的第二次失败仍止后续，采用gate仍拒。策略、总步数、每单元预算和发布要求不变。不是扩大临床通过，也不是无限试到好回答。

检查完整上述定义、tests/v2/workflow/test_runner.py新retained族，以及tests/v2/services/test_protocol_control_execution.py::test_preserved_failure_revalidates_restricted_source_through_actual_job_checkpoint。该实际服务例覆盖旧证明损坏/来源改变/不可转换，以及保留失败后一个和两个新失败。合并相连窗JUnit artifacts/rv1006-table-sequence-and-retained-failure-connected-20261011-v2.xml实有76测试/0失败/0错误/28.511秒；测试并非真实新方案作业。当前跨段表格来源位置功能只证明物理关系，既有49恢复还不会自行生成其新witness，不宣称修好了真实49。

最多8次必要只读工具，核以下：1) 新旧失败能否被误分类而绕过止损或被旧损坏记录伪装保留；2) 重启/持久化/失败后gate、没有白名单的错误是否保持；3) 有没有遗漏的相邻消费者直接风险。给明确必修/建议/证据不足及位置，不为可能性能收益要求新框架或全库测试。一次未使用的可选来源字段不应让47已核来源全部重读；实际复用仍由产品预检证明。
