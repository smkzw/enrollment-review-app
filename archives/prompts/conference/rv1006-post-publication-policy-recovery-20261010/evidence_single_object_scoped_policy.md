# 同一恢复边界的局部字段审阅

沿原批准 C03/evidence_single_object 会话，基础 b898aaba；不改路线，不批准临床采用。只读源码，禁止 shell、网络、env、数据库、临床原答/原件、写文件、递归派发和运行测试。最多16次源码读取；明确已读与未读范围。

真实接续已经进入原来的 scoped reader，一次调用后得到合法 JSON，但一个局部候选的 trigger/obligation 中四个原子都缺 observation_policy。当前完整 Schema 拒绝并保存实际回答，未采用。新增恢复仅针对这个结构性缺失，不为模型补写临床选择规则。

请阅读当前 app/agents/protocol_control_deconstructor.py 的 _invalid_scoped_observation_payload、_invalid_candidate_payload、_invalid_observation_policy_paths、_merge_observation_policy_repair_payload，以及 Runner 的 failed_scoped_unit_repair 捕获/转字段修复/后续合并/作用域恢复/预算和停止条件；app/agents/protocol_control_agent_transport.py 的 continue_observation_policies 和 scoped binding；test_scoped_missing_policy_uses_field_reader_and_preserves_actual_proposal。

变化：只在 scoped 回复的唯一无效候选全部错误均为缺观察选择说明时，将实际局部提案与原来授权闭包外兄弟拼为未采用 raw 基线，随后走已有字段 reader。要求处置集合精确等于已授权单元；候选来源只在授权单元和实际来源 span 内；拒绝跨闭包旧候选。字段返回仅能修改指定 observation_policy，引用只能取该原子来源。完整 hydrate、来源/含义/发布门仍重新执行。未开新预算；坏 JSON、混合结构错误、错来源、错字段返回仍停止，不回退整候选/整批。只新增 validator 组成标识，不改作者/编译/模型身份。

重点挑战：索引随保留兄弟重排是否正确；局部无效提案是否被误当已核结果；scope/span 与错误分类是否有漏洞；字段读取后兄弟是否保留、整个要求是否仍走真实消费者；错误/传输/额度是否会偷偷退整包；真实测试是否实际抵达字段调用。不要依据本说明推定代码正确。

本增量还没有完成跨 Job 保存无效 raw 提案的恢复：当前服务只保留合法未采用 pending_author_wire，故新 Job 仍可能重作一次局部提案，不能声称已零调用恢复旧无效答。此限制不通过伪造会话/回执解决；请区分运行中字段恢复与跨 Job 重用。

输出可达问题、反证、最小建议和阅读局限；无问题也说明程序审阅不证明下一模型答正确、不是独立模型金标或临床批准。
