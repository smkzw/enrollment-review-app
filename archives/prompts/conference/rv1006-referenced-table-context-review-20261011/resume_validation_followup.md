# 同一C03审阅的恢复边界增量

角色仍为只读顾问，不编辑文件，不运行测试或产品，不读临床资料、env、tmp、模型原答；不得递归派发。本次只核一个恢复因果问题，勿扩展架构或医学判断。

冻结改动：app/services/protocol_control_execution.py::_preflight_deep_source 的失败草稿分支，只有 saved component_identity.validator_version 与当前相同，才调用 _preserved_source_review_proof 冻结旧失败。当前validator不同则仍沿既有 _validated_deep_partial_source、resume_partial、当前重新核对路径，不修改旧终态/旧原答/预算、不提升为成功、不把技术问题变医学歧义。

原因（仅诊断线索，不是请你相信所有者）：新的通用条件前缀证明能认可旧草稿的一个配对，旧 source_statement_coverage 因而不等于当前计算结果。原预检却先尝试冻结旧失败，抛“来源覆盖与实际对应证明不一致”。同版本损坏仍必须拒绝；不能 blanket catch ValueError。

请独立读取上述完整函数和相关消费者、tests/v2/services/test_protocol_control_execution.py::test_independent_reads_preserve_actual_unresolved_failure_without_model_retry（现在gate_changed两支），指出这项限制是否能避免旧失败被当当前事实、是否掩盖身份损坏/越过重核、是否不必要地作废成功兄弟。表号空白/分隔符、期别引用共用正则与正文提示反例已按上一报告修，必要时仅核其增量。不要因一般性建议要求新框架或再全方案调用。

输出问题优先；无问题就说明证据边界。未跑测试/未读90批/未核临床必须明确。初轮和续轮均只为工程审阅，不是临床批准。
