# T5 办理链实现续审

沿批准 C03 同会话做只读实现复核。不得修改任何代码、读数据库或密钥、运行测试、安装依赖、调用产品模型；报告由 runner 保存。这不是新鲜上下文的独立临床签收。只读当前 worktree，不扫其他项目。

请核对完整定义：app/services/review_action_command.py、app/api/v2/review_actions.py、app/storage/review_reference_validation.py、app/storage/fact_authority.py 新 validate_frozen_source、app/storage/repositories.py 的 _check_action_scope 和 ActionRequestRepository、app/domain/contracts/review.py 的 ActionTransition/ActionRequest；前端 frontend/src/components/review/ReviewActionResponseDialog.tsx 及 frontend/src/api/review-history/reviewActionHttp.ts。必要时查相邻服务和合同，不广扫历史。

补充看 app/domain/review_action_directives.py 与 app/domain/contracts/review_context_v2.py：新版待办从冻结条款与现有 ACTION_CONTENT 推导，不判断缺口，不自动采信。模板允许独立流程要求，不要求全部出现在 ClausePack；条款中已存在的同身份要求则必须内容一致。新推导器尚未接发布器，请不要误报已全链可用。

验收问题：人工办结必须理由及回应原件；只说明已办理、不改临床结论。回应同受试者同节点但可新快照，新建时显式当前修订，历史读取只验其冻结来源。转换原样追加且一次一个，身份和触发依据不可变。幂等重试必须返回第一次转换，修订冲突不能覆盖。单事务保存 gate/action/receipt，无新表/队列。仅 close_manual/reopen，不开放系统自动关闭。指出真实错误及最小修订，证据到文件/行；区分实现缺陷与待最终测试项。不要建议制造旧 AgentCall、把候选事实当已证明，或为产出正式报告放行所有未知。控制输出，先 findings，再无问题范围与未验证项。
