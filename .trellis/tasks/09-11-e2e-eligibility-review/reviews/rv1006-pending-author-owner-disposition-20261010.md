# 未采用作者提案恢复｜1006V1所有者记录

## 实际产物与边界

本包基础源码972428f6258dd5eabfea580346177e1c049eaf09。只更改两源码、两原模块测试和当前任务记录；七份继承dirty不纳入提交。Goal active、claims_complete=false。

真实Job775a750ed7634c4bbfa7a5400485e54f在972428f6源码上终止：failed_final/PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID，2物理调用241.53028695797548秒，驱动exit3。85发现及44成功零新调用，deep_0045失败、余45未读。检查点ab7501a2ad2f442490e0f5aaeb9375cf；旧Job、来源库、保护库检查均不变。该运行尚未使用本包，不是完整采用或临床验收。

首因：所属原子仅摘动作短句，嵌套复查政策引用同来源完整条件；修订又缩短内层摘录而未删除触发原句。原两层来源包含门正确拒绝。不是端点不可用，也不是原件明确缺研究者判断。原文、完整请求和原答仅受控本机可读，外部审阅不可读，不提交临床片段。替代解释包括一次模型生成波动与作者/Schema复杂度；一次失败不能证明模型无能力。通用修订提示仅明确嵌套来源闭包和授权范围，不改变Schema或临床含义。

## 生产、保存、消费

- ProtocolControlAgentRunner仅捕获Schema合法提案，独立于partial_wire和已核证明；在全门失败时保留pending_author_wire、生成时source hash和累计作者修订数。能力失败分支不混存。
- ProtocolControlExecutionService保存和读取同一检查点工件，校验原完整工件proof、来源/分包/材料/route，以及提案hash；损坏硬拒，不当缓存未命中。BASELINE限定、无已核证明、不和来源核对/能力产物混用。
- 恢复先restore_scoped_session和完整门禁，再用既有受限修订。新Job不将作者次数归零；来源复核也扣除携带次数后的余额。来源改变保存PENDING_AUTHOR_SOURCE_CHANGED及实际回执，不继续旧提案。
- 合成JobRunner实际生产/保存/新Job合法读回/消费正例与损坏反例已运行，旧检查点fingerprint保持。没有新产品UI，也没有真实临床采用。
- 实际latest775a只有来源解释、无typed提案；只读预检44reusable/1source-only resume/45refresh，0模型/0写，库hash保持。不得把老失败原答补造为新字段。
- 限制：scoped restore不重建历史对话。continue_atom等自含上下文方法支持它，continue_candidate(s)仍需要真实history；当前仅证明受限原子路径，不声称所有恢复方式已真实可用。物理调用账仍既有Job作用域，本包仅保留作者修订数及既有来源问题账，不宣称重写全任务预算。

## 独审与取舍

批准C03/evidence_single_object，codebuddy/codebuddy-cli/deepseek-v4.1-flash/max，无fallback；session01a1226e-303b-7746-9434-5b2568b22ffe。初审188.067秒，增量约95秒，均exit0；120分钟完成等待。报告位于runs/conference/rv1006-pending-author-review-20261010/。同产品模型家族，只有程序/上下文分离，不是模型独立金标、医学批准或用户验收；不运行测试、不读临床/DB/env。

采纳：来源漂移裸异常改类型化回执；生成时来源hash绑定；作者修订数携带；能力/已核产物不与pending混存；运行时helper错误包装StepFailure。增量审指出来源问题调用失败时计数可归零、失败码映射未证，所有者检查后修正计数下限/余额与映射，并补changed/transport/exhausted三路径反例。最后小修未再派第三审，由实际反例关闭；不宣称最后源码被顾问全面读取。

## 命令与可复核结果

1. 三相连原模块：pytest tests/v2/protocols/test_slice58c_control_deconstructor.py tests/v2/protocols/test_slice58c_protocol_control_gate.py tests/v2/services/test_protocol_control_execution.py -q --tb=short --junitxml=artifacts/rv1006-pending-author-connected-20261010-v1.xml：1641passed，120.26秒，exit0。此前中间聚焦12/18不累计。
2. 最后计数/映射/通用修订提示后的受影响窗：pytest tests/v2/protocols/test_slice58c_control_deconstructor.py tests/v2/services/test_protocol_control_execution.py -q -k 'unaccepted_author or pending_author or same_source_question_runner or repair_prompt' --tb=short --junitxml=artifacts/rv1006-pending-author-affected-20261010-v3.xml：55passed/1388deselected，2.76秒，exit0。末全窗未重复，两窗不能相加。5既有SWIG警告。
3. git diff --check：exit0。只读预检产物本机/Users/smkzw/tmp/enrollment-rv1001-official-continuation-20261003/rv1006-pending-author-preflight-20261010-v1.json，0模型/0写，44/1/45；增加修订提示后须再核新身份，不把旧预检直接当新运行依据。

## 窗口仍未达

没有完整官方+跨章共同采用包，沒有新同包24页整例工作稿、正式UI有源更正后的新旧结果。旧UI描述更正0规则关联不冒充闭环。下一是冻结源码、最新材料复用预检、合法有界接续；不复活旧终态或继续无新假设的整组重读。
