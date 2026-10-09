# 同源原文局部疑问核对：所有者取舍

范围：1006V1完整要求快照的直接阻断；不改变事实自动采用或签发权限。基线db2dec4887437747fcbdb33eddac88c9396ca5f1，当前功能包源码/测试另行明确提交。真实原件、DB与模型原答不入Git。

## 第一因果错误与修复

实际8e50终态保存40组，37/42失败，48未读。37来源读道没有后续列表，却冻结官方原文已有；42同段选择关系可能真正不清。新增的是来源上下文的局部核查，不是EX编号或药物词表，不自动清空疑问。仅一个来源位置与整段文字相符且唯一官方目标时允许完整原文；多位置不拼接。来源数组不是阅读顺序，已知单来源单元给物理顺序，未知明确空。

普通陈述只允许修改unresolved；实际上下文版本/hash记录并由Runner与来源证明回放对账。上下文改变/消失不能复用旧清空；保留疑问可在旧预算内继续，兄弟不变。来源平行数组/重复位置损坏显式拒绝，不静默缓存未中。新目标核查与原采用门保留，无正式发布。

## 执行与独审

所有者直接集成＋批准C03一个新上下文工程审阅，因来源恢复影响采用证明。Grok/grok-build/grok-4.7/high，session0c5f3c06-8159-4e8f-af64-9702295537d8，首384.181秒/续约183秒完成等待，exit0/no fallback。首审发现多来源任一相同过宽及当前上下文消失仍复用，采纳并加入Runner/实际来源证明正反例。续审无必修；末建议的仅单来源单元提供顺序已采纳，由所有者验证。两个报告在runs/conference/rv1006-same-source-question-review-20261009/。

限制：顾问没有运行测试/临床，未读全部调用者；不是专业批准。记录prompt hash但历史不同提示不能凭当前内容反算旧提示；本次上下文recipe版本及hash冻结，后续改变recipe需新身份。损坏目标为硬本地失败，不增加模型重试。成功组实际复用按前置计划，不声称所有临床已验证。

## 实际检查

命令：`.venv/bin/python -m pytest tests/v2/protocols/test_slice58c_control_deconstructor.py tests/v2/services/test_protocol_control_execution.py -q -k 'same_source_official_question or same_source_question_runner or completed_local_context_question or actual_runner_uses_one_context_request or owned_context_target_recheck or saved_source_review or gate_only_change_revalidates or revalidated_source_seed or revalidated_source_question' --junitxml=artifacts/rv1006-same-source-question-affected-20261009-v5.xml`

最终66passed/1198deselected/7.26秒/exit0/5既有SWIG；不是全库/医学验收。首19/7为新夹具source-ID及必填数组；25/1为测试误假设未决目标复用；均修夹具而非放松产品门。33/65为先前补丁窗口，不累加。危险反例：错位置、不同整段、多位置、来源损坏、重复来源、改摘录/阶段、仍真未决、传输失败、上下文变化后旧答复与来源证明拒绝。新调用后该条目标必须新核查，兄弟原样保留。

只读实际计划40reusable/2resume_partial/48refresh，0模型/0写/DBhash保持；37索引1/6及42索引1绑定原文。最终v2预检私有目录仅本机可读，不能当临床恢复。真实新Job/共同发布/病例新工作稿及UI更正尚未在本报告完成。
