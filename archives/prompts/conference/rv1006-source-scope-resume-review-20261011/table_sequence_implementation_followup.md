# 1006V1 有界跨段来源证明：实际补丁独审

所有者仍连续实施，非暂停。只读当前worktree源码及合成测试，不读任何真实方案/病例、数据库、env、私有运行目录，不修改文件，不执行产品模型或临床作业。

本次补丁尚未提交，相对4ac85430。主要文件：app/protocols/control_scope_sources.py；app/agents/protocol_control_source_interpretation.py；app/agents/protocol_control_deconstructor.py（reuse_identity）；app/services/protocol_control_execution.py（validator version）；tests/v2/protocols/test_slice58c_control_deconstructor.py（_table_sequence_material及table_sequence相关新增测试）。请用只读工具核实际完整定义及消费者；能读取diff则读，否则用符号/正文，明确限制。检查实际实现，而非复述上次建议。

已实现：同表原生格/合并列定位→完整对象表头引用及来源hash→只读前文引用表号→SourceStatement可选版本化witness→现有target review强制fresh核查→原保存/读回门。位置不推临床先后。没有新框架、数据库、参数执行器或自动采用。原作者提示只有具备位置包才附加新说明，核对提示只有存在witness才附新说明；请求Schema的可选新字段/hash按实际请求保留。25个受影响合成例已通过，但非真实试跑。

主要问题：
1. 实际来源/表号/列/期别/文档/hash/完整性是否有未保护的误归属？counterfactual须明确方向由模型核，不把位置保护宣传成临床语义证明。
2. 重用身份、旧可选字段、保存/读回及采用消费者是否相容？是否存在跳过fresh核对或伪造not_current_control的漏洞？scope之外的背景/例外不能借研究治疗顺序排除。
3. 当前失败独立读取策略见runner::_continue_independent_after_failure和execution::_INDEPENDENT_DEEP_READ_POLICY：max_failed_steps=2是整个job累计，而非同一来源重复失败。当前两个独立failed单元导致41单元未读。1006V1明确“停止一个分支不等于停止独立工作”。请核风险和建议：是否应在显式版本化的新Job中允许计划范围内其他独立读取继续（仅既有语义失败白名单，不放行身份/结构/传输，失败仍失败，终态仍失败，publication依赖不变，每步原预算不刷新）？这不是已实施补丁。如何最小完成，避免无上限重试或两份policy真相？是否有反证支持保留总两次限制？给出源码位置。

最多12次必要只读工具，优先上述完整定义与新增测试，报告P1/P2缺陷和最小修复；区分必须、建议、证据不足。不称临床批准/发布/Q3完成。不要求重构所有恢复器。已有正常实例应能用，危险反例应拒；只说“更安全”不足以关闭。
