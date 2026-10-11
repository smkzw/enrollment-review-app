# 1006V1｜缺失原文单元的有界补读

## 实际首错与范围

基线7effacd；真实Job d371ca37793e49bcaa6dcecd48ce9e32，failed_final / SOURCE_TARGET_REVIEW_UNRESOLVED，14物理调用474.0040339579573秒，43成功/44失败/46未执行。只读消费者核查确认当前覆盖证明与原草稿结构有效，但一个94字符原文单元仅覆盖[0,53]及[53,76]，其余[76,94]为有决策作用的上位条件连接。原文不入公共包；受限采用拒绝正确，不能靠把未决改标签解决来源遗漏。

本功能只允许模型逐字扩展该单元原陈述的连续摘录。陈述数量、顺序、作用、时间、范围、例外、疑问及其他单元不改。新独立陈述或重分不能在此接口偷加。补齐只证明捕获范围，不证明含义；受影响批次旧候选、核对、覆盖、alignment和会话全部丢弃作为复用种子，实际原答/账本不删除。随后重新作者/核对/既有门禁；43个已成功批次仍须当前合同重验，不自动升级旧批准。

## 审阅与所有者取舍

- 旧长上下文C03续审实际exit3，Max turns24 exceeded，202.829秒；没有可用意见。失败记录保留，不称审阅通过。
- 新批准单C03实际CodeBuddy / codebuddy-cli / deepseek-v4.1-flash / max，session01a121c4-3f34-7a5a-bbac-628950c6456c，301.969秒、returncode0、no fallback。120min静默完成等待。报告在runs/conference/rv1006-unit-quote-completion-review-20261010/evidence_single_object.md。
- 顾问实际31工具，超12聚焦读取建议；均在声明代码/测试范围，不读病例/方案原件，不跑测试、不验证hash，不做临床批准。同模型家族仅程序/新上下文分离，不称模型独立金标。
- 顾问确认捕获种子与采用证明确实分离，不能借补读采用规则；发现失败往返可能丢账本并重读上游。所有者读完整恢复消费者后采纳：失败保存source与pending；实际连接失败保留同源种子及历史续读；坏答复在预检/同Job恢复明确停止，不回退整批作者。既有resolve在已执行失败步骤停在当前Job，不回源寻找有利答案。
- 两个新错误保留具体code，连接故障可恢复、内容不合规不可自动重读；身份、预算、断流不确定的既有硬错误不改成普通连接故障。失败记录和原已用次数一起恢复，原额度上限与当前上限取较小者；未发送的阻止记录不再计新付费调用，旧记录保守计入。
- 采纳新增摘录的含义风险：实际成功补读登记expanded_statement_indexes，后续核对须完整引用扩展后的摘录或明确未决；正常采用与受限采用消费者共同检查，不由文字完整推断医学正确。新prompt只对本次扩大摘录的索引说明该要求。
- 防御性拒绝旧alignment/coverage进入补读；原完整来源、数值、身份、权限和历史门不放宽。

## 同版本证据与限制

集中相连三模块reviewed-connected-v1：1471passed/2failed，110.81秒，exit1；两失败都是新持久化夹具未计入JobRunner附加attempt。随后据实际SQLite记录核明：max_attempts=1的夹具在手动恢复后即使故障本身可恢复也终态failed_final且retryable=false；修正确切断言，不改产品门。

最终受影响reviewed-affected-v3：58passed/465deselected，4.25秒，exit0，5第三方SWIG警告。包含实际JobRunner/JobStore失败保存→读回→原范围恢复、连接两次后额度阻止、坏答复拒重复、来源连续扩展/缩短/重叠/错ID/越权/清疑问反例、完整新摘录与缩短核对的采用边界及具体错误分类。最终未全库或末版全相连重跑，各窗不累计；不是临床验收。

命令：

```sh
.venv/bin/python -m pytest tests/v2/services/test_protocol_control_execution.py tests/v2/protocols/test_slice58c_control_deconstructor.py tests/v2/agents/test_protocol_control_candidate_alignment.py -q --junitxml=artifacts/rv1006-source-unit-completion-reviewed-connected-20261010-v1.xml
.venv/bin/python -m pytest tests/v2/services/test_protocol_control_execution.py -q -k 'unit_completion_failure or completed_source_quote or source_unit_quote_completion or saved_source_gap_preflight or deep_service_preserves_recheck_failure or gate_only_change' --junitxml=artifacts/rv1006-source-unit-completion-reviewed-affected-20261010-v3.xml
```

只读预检v1误用R1全未决采用证明，拒绝执行；v2改为实际原文捕获见证；最终v3为43reusable/1resume_partial/46refresh，0模型/0库写/hash保持，44仅一缺口单元，旧wire/review/coverage/alignment/session不复用。首次v3入口漏PYTHONPATH，导入前exit1/无模型无写；显式环境后exit0。记录位于受控本机rv1006-unit-quote-completion-preflight-20261010-v3.json，外部审阅不可读；哈希证明身份不证明医学含义。

顾问审阅冻结初版；所有者后续恢复与扩大引用保护由上述实际服务/反例核查验证，不能写成顾问已复审末版。真正独立语义含义仍由产品新作者/核对及来源消费确认。

## 接续而非暂停

从同一合法入口新建受控Job，逐项核90分包与预检一致，保留旧终态和原答。一个单元补读后，重新核当前受影响批次；成功范围进入既有后续闭环，失败按层定位不自动扩大输入。本包尚未实际模型试跑，完整共同发布、同包病例工作稿、实际UI更正及新旧报告仍未完成，claims_complete=false，Goal active。不新建平台、Phase、规则真相或特定方案词表。
