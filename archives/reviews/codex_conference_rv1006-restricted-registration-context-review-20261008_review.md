# RV1006 来源登记与局部恢复审阅

日期2026-10-08，基础源码8b1cb65e。本功能包未作临床批准，提交身份由implement记录。

## 事实与审阅边界

批准C03实际CodeBuddy/codebuddy-cli/deepseek-v4.1-flash/max，session 01a11922-655e-75df-af04-fc5dae439ab8；初审和两次同会话有界复核均exit0/no fallback。结果在runs/conference/rv1006-restricted-registration-context-review-20261008/，120分钟完成等待期间主线程静默。后两轮不叫新模型独立意见，未读临床原答/未跑测试。

实际Job 1f79e0e7b20442f3b66edde7a2ed6fa1 failed_final：90组9completed、2failed、79未读。未改旧终态，合成验证不等于真实恢复。

## 建议与所有者处置

- 采纳：登记失败明确为deep_failure_diagnostic/v3，保存实际来源、核对、登记尝试；失败标记及派生登记失败不能按deep成功重放。
- 采纳：同格连续上下文保存原生ID、范围、停止原因及complete_list_asserted=false；只改变受影响批次身份，不把24单元前缀称完整列表。
- 采纳B1：显式重读缺记录失败范围时，旧和当前owned_structure_unit_ids必须相同，不能仅凭步骤编号对应来源。
- 关闭B2（实际反证）：JobStore.get_last_checkpoint只有无行才None；有行调用verify_payload_sha256，损坏/哈希错抛错。已有坏诊断仍拒，不另建存在性查询。
- 保留复杂混合单元全单元受限；不放宽计算/时点/来源资格，不新增全局歧义自动解除。来源/作者各自的窄提示保留，去重建议由顾问撤回。

## 证据与未完成

第11组6份实际请求/回答零网络精确重放：修前登记后受限内容消失，修后前后相等。原答/DB保持；不是新Job成功或临床QC。私有材料仅本机可读，外部审阅不可读，不提交临床全文。

六相连模块573passed/114.22s/exit0/5既有SWIG，JUnit artifacts/rv1006-registration-context-missing-record-connected-20261008-final.xml；此快照早于末版B1两行硬化。随后相邻6反例/正例6passed/5.24s/exit0。前549/488等窗口不累加。

只读预检6reusable/84refresh_required，0调用/DB不变：3旧完成组上下文改变，第9组新核，第11组缺诊断明确新读，79未读。完整新API Job、共同要求包、病例新报告与更正闭环仍未完成。

顾问读窗有限，未看全部消费者/API测试/JobStore；B1最终补丁由所有者验证，不声称末版全部独审。替代解释：第9组补上下文后仍可能是真实源歧义；登记路径修复不意味着所有定义关系可执行。会商一致不证明医学含义正确。
