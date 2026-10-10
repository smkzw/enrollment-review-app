# 局部来源角色与复查合同恢复：冻结代码审阅

沿批准C03同会话只读审阅，最多14次定向读取。基线5749dd12，当前未提交修改仅下述相关文件；不得读临床原件、私库、环境或其他线程；不执行测试/模型/服务，不修改文件，不递归会商。模型家族与产品部分相同，只称程序分离，不称独立模型金标。

请审查实际源码而非采信所有者说明：
- app/agents/protocol_control_source_interpretation.py：SourceScopeCorrection、heading_scope_requires_recheck、apply_source_scope_correction。
- app/agents/protocol_control_deconstructor.py：heading recheck/history恢复；repeat_scheme_only局部合并/提示；cited_unexpressed失败分流。
- app/agents/protocol_control_candidate_alignment.py：source_declares_uncompared_action_count、缺失repeat_scheme定位、source count representation、proof输入身份。
- app/services/protocol_control_execution.py：实际history保存/恢复和source seed回放，validator身份。
- 新增原模块测试：heading_topic、source_repeat_count；必要时核现有repeat_scheme及count/trigger消费者。

问题：只从完整标题复制的阶段是否能经局部读取纠正为主题，而不改正文/真实访视/前后窗、不凭提出“主题”就临床采用？当前topic声明只留原冻结标题及原答，不写scope_quote，避免制造访视来源绑定。正文与显式时间保留、已知节点标题不可删除；之后旧来源核对证明应失效并重新核对。

另一个补丁只填原子缺失的repeat_scheme，其余原句、来源、数值、政策、时间和兄弟保持。次数/来源核验只证明有源表示，未知count_scope或结果采用规则不自动补，既有消费者保持UNKNOWN；动作次数不强填检验comparison predicate。请查有没有扩大修订范围、吞错误、漏预算/历史、把普通事件次数错误当repeat policy或把“可复查”变“必须复查”的实际危险路径。明确现有完整核对能覆盖什么、仍缺什么；不能拿Schema有效或同源引用当含义证明。

输出必须修复项、建议、已证、未验分别列，给准确函数/正例/反例/消费者。不要要求整方案反复重跑；不要自行批准采用或要求新增模型。所有临床调用及来源角色诊断仅保留本机，不在报告复述原文。
