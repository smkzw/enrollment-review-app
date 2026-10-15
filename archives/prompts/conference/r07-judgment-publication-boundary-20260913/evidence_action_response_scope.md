# T5 待办回应来源的最小续审

沿原C03同会话只读工程审阅，不能修改代码或原临床资料、读凭据/数据库、调用产品模型、运行测试或安装依赖。允许读取本worktree源码，输出建议由runner保存。不是新的专业医学签收。用户要求整体验证后置，不要求本轮测试。

本次实质问题：app/storage/repositories.py::_check_action_scope 把全部transition.locator_ids放在原审核authority下验证，补上传的新证据会被拒；同时拿当前episode.rule_set_revision核旧Action，使方案修订后无法办理旧事项。原触发依据应该固定，但后续回应需要自己的版本。ActionRequest已经保存完整转换、revision和fingerprint，不能另建待办状态机。

请读完整受影响定义：app/domain/contracts/review.py ActionTransition/ActionRequest，app/storage/repositories.py _check_action_scope/ActionRequestRepository，app/storage/review_reference_validation.py，app/storage/fact_authority.py，app/domain/gates/actions.py，app/domain/contracts/enums.py ActionState，app/services/review_history_service.py，设计§17.6及恢复PlanT5。必要时定位相邻模型/仓储，不扫全库。

拟议最小方案（挑战而非自动采纳）：
1. review/v2转换增加可空response_authority: FactAuthority；非空locator_ids必须带回应authority，按其实际冻结snapshot/complete验证，不要求等于原run。authority的project/subject/episode必须与Action相同；只校验来源闭合，不要求后来仍current。旧fixture/v1字段省略保持指纹。原trigger_locator始终按原context.authority验证，不能搬到新版本。
2. Action原范围与原FinalAssessment/ReviewContext一致，不再与当前episode规则修订比较。新写首次发布仍由正式发布入口验当前权威；关闭/重开不改原结论。转换新增字段进payload/hash，既有transitionlocator关联表可复用；不另建queue/table。
3. 人工办理只能明确记录有依据的关闭/重开及原因；关闭缺口须提供具体回应原件，不能只勾选即符合。自动关闭/被新审核替代必须另有新ReviewRun及对应结论/缺口证明，首版不开放自动关闭，不伪造此证明。缺研究者判断仍是报告内容，不要求用户再次确认缺失。
4. 仓储replace需确证旧转换列表是新列表的原样前缀，只能追加，不能同ID改历史正文。新输入显式预期revision与幂等键，由现有命令事务处理。

问题：该方案是否遗漏必须的回应时间/节点限制、历史完整性或闭环语义？FactAuthority是否过重或会错误要求回应已有病史整理（定位检查只需要snapshot/complete）？如何区分人工办结与“已解决缺口”的临床含义，而不增新状态枚举？请给最小可实施修订、真正阻塞项，标源码位置。不要建议所有新证据继续按旧authority验，也不要要求用户确认已核实缺失。此次只处理回应/历史保存，不将未批准谓词对应接入正式判断。
