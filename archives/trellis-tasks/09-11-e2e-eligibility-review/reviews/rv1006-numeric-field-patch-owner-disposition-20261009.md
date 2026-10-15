# 数值字段补丁：当前来源、修复与边界

## 实际结果
- 真实产品源码b6fb9016；合法Jobd6e869ea2e1d46448ec7b4b848a13c6f，failed_final/PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID。7物理调用，277.53463079209905秒，exec92046/exit3。85发现及43成功零新调用，44失败，46未执行。检查点1fea68334eeb43589c9d8d46015b797b；旧Job/保护库/来源库保持，未共同发布/启用/签发。
- 私有请求/初答/回执：`/Users/smkzw/tmp/enrollment-rv1001-official-continuation-20261003/rv1006-citation-recovery-api-20261009-v1/`，本机可读、外部不可读。不提交临床原答。本次所有7回执均stop，非传输/截断失败。请求与响应模型均deepseek-v4.1-flash/high，65536额度。
- 第一处新因果错误：numeric_predicate_missing恢复时，比较条件摘录用完整父句，冻结evaluation只持局部数值原句；比较摘录包含校验拒绝正确。不能把此错误改名忠实来源歧义。先前上下文变化负结论现在实际核对，不再重复三次越界来源补入。

## 最小修改
生产：`protocol_control_agent_transport.continue_numeric_predicate`沿原单请求/同会话/同预算通道；`protocol_control_atom_repair_response_format(numeric_predicate_only=True)`只包含evaluation_patch四字段及现有AtomicPredicate定义。text/json_object/json_schema均带正确合同。

保存：`_merge_obligation_atom_repair`只允许四字段、确定性value_comparison/非空predicate/value；深拷贝原子，只更改授权求值字段。该补丁路径不运行可能重写冻结时间/观察字段的格式归一化；原完整原子修复保留。重复source_clause/source_clauses仅在逐字同一单条时折叠，不改来源/单位/值。

消费：原完整wire/原子包含校验及SourceCandidateAlignment仍执行；候选hash变化使旧正证明无效，错误阈值不能靠结构通过采用。原草稿和兄弟不改、失败后原稿保持，不机械修正实际坏答。

身份：numeric-evaluation-field-patch/v1仅进入validator身份，实际请求Schema/prompt/输出hash沿既有回执保存。作者/基础编译材料未变化；不反算改写历史，不给旧结果升级批准。

## 独审及取舍
批准C03，CodeBuddy/codebuddy-cli/deepseek-v4.1-flash/max，同session01a12117-a4b2-746e-8492-36b3f0d4fcc9增量，exit0/no fallback，207.470617041秒完成等待（120min上限，期间主线程静默）。报告`runs/conference/rv1006-source-dependent-restriction-20261009/evidence_numeric_patch_followup.md`。无测试/临床/网络/源码修改；不能核HEAD及6文件hash。仅程序/上下文分离，不是独立模型临床金标。

- M1“validator变化可能丢partial”：未采纳放宽精确身份建议。实际`_validated_deep_partial_source`首先使用validator-only容忍比较，changed_components=false；不是顾问推测的compiler-change分支。当前实际预检44为resume_partial/verified_unpublished_draft_source_review_reused，有原检查点及hash。旧同Job或错误作用域精确检查仍保留。其他结构变化不得借此复用。
- M2防降级：采纳。补丁Schema和合并均强制已定位的确定性数值比较；缺predicate/改semantic在调用后立即拒绝，而不等待另一模型再发现。原文不支持时仍拒，不伪造临床阈值。
- L1冻结字段归一化：采纳仅补丁路径跳过原格式归一化，防其改变授权外字段；legacy普通完整原子路径不变。
- L2遗漏反例：补缺字段、降级、补丁重复逐字来源反例。末加强由所有者测试验证，未另开第四轮独审。
- L3不可用方法：保持显式失败不静默走其他模型或重发整包。

## 实际验证
初受影响：18pass/1424deselected/1.97秒/exit0（首版本，不计末验证总数）。

末功能包：
```
.venv/bin/python -m pytest tests/v2/protocols/test_slice58c_control_deconstructor.py tests/v2/protocols/test_protocol_control_agent_transport.py tests/v2/agents/test_protocol_control_candidate_alignment.py tests/v2/services/test_protocol_control_execution.py tests/v2/domain/test_control_catalog_restricted_contract.py -q --tb=short --junitxml=artifacts/rv1006-numeric-field-patch-connected-20261009-v2.xml
```
1586passed/105.83秒/exit0，5既有SWIG警告。相连功能验证，不是全库或临床验收；窗口不累加。

实际只读前置：`preflight_rv1006_numeric_patch_20261009.py`/exit0，输出`rv1006-numeric-patch-preflight-20261009-v1.json`（上述私有根）；43reusable/1resume_partial/46refresh_required，0模型/0写，DBhash保持、无活动租约。源d6e869终态不改。SQLite普通只读打开失败后改immutable只读成功，禁止由此启动共享服务或改库。

## 未完成与下一动作
新数值补丁尚未真实执行。下一经现有合法API创建唯一新作业，核实际90步reuse决定与前置一致后接续，不重读43成功、不覆盖旧目录。共同引用未决闭包仍须真实消费验证；当前只是修复授权字段的提交合同，不能据此证明临床语义或受限采用成立。完整官方+跨章共同包、同包5份24页当前工作稿、UI更正/重算/新旧结果均未完成，claims_complete=false。

替代解释：格式范围修复后仍可能存在来源关系、真实歧义或算法能力缺口；不能因为本次7调用均stop把所有困难归因模型或认为下一次一定成功。不会继续为同一错误扩大整包或输出额度。
