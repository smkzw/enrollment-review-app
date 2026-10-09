# 逐项核对与有界原子恢复：所有者取舍

## 事实与范围

基线43928e2779dc52b1560c3378298df9dc4f66d785；本包只改candidate_alignment、deconstructor及两个原模块测试，不扩临床要求、不改历史证明。最新真实cbf562作业43完成/第44失败/46未执行，1物理调用149.215157秒。保护库、来源库、旧Job/原件未变；无共同发布、激活、签发。真实原答与数据库仅本机受控可读，外部审阅不可读。

首因：核对回答中一个合法操作项被另一个缺数值比较的项连带丢弃。只读实际回放将第二项保留，第一项定位到唯一原子，0模型/0写库；不是临床采信。新绑定仍保存完整原始JSON，绝不把过滤后的JSON伪装原答。

## 独立审阅及处置

批准C03 Grok/grok-build/grok-4.7/high，session318e06ad-e6b0-4d87-8b4d-8e38660ff615，781.912秒、exit0、1轮、无fallback，7200秒完成等待。报告runs/conference/rv1006-alignment-item-recovery-20261009/evidence_single_object.md。只读源码/合成测试，不读临床、不执行测试；末修代码由所有者直接验证，未冒称复审。

| 意见 | 所有者处置与反证 |
|---|---|
| 空分支范围不能推定全部 | 采纳，要求显式索引等于全部触发分支；新增empty与partial反例 |
| 阶段前缀可能把期外算期内 | 采纳，阶段后必须独立标点边界或条件引导词；期外/前/后/数值窗反例保持拒绝 |
| 数值修订可改命题、记录选择及时间，失败草稿未回滚 | 采纳，仅四求值字段可改，时间/命题/观察政策冻结；错阈值完整重验后回到原稿，同时保留真实提案和失败；原通用时间修订能力不受此窄路径覆盖 |
| 负面核对在后续失败时丢失 | 采纳，只恢复当前完整候选hash未变的合法negative记录；positive才可退出待核集合，新合法回答替代同配对旧答，改候选旧证据仍失效 |
| 实际失败是否真是唯一数值缺口 | 所有者只读实际回放确认numeric_predicate_missing与唯一路径；没有把顾问未读材料写成其结论 |

替代解释：模型核对正面结论本身不代表整个规则可用；后续定义、时间或依赖仍可能失败。局部修订未验证时不进入正式采用，即使Schema通过。

## 集中验证

三个模块：tests/v2/agents/test_protocol_control_candidate_alignment.py、tests/v2/protocols/test_slice58c_control_deconstructor.py、tests/v2/protocols/test_protocol_control_agent_transport.py。

命令：`.venv/bin/python -m pytest`上述三文件`-q --junitxml=artifacts/rv1006-alignment-item-recovery-connected-20261009-v8.xml`；1029passed/13.48秒/exit0，5既有SWIG警告。v6为1027pass/2fail：新增阶段夹具标点触发旧时间诊断、冻结对象赋值错误；v7为1028pass/1fail：新多阈值夹具整句忠实表达绕过了所要测试的alignment入口，调整为真正不完整候选。v8全部相连通过，不删除反例、不放宽门、不累加窗口。

正例合法逐项保存与唯一数值局部修订；反例坏身份、同句多阈值、错阈值、改命题/政策、条件分支遗漏、期外、断线、预算耗尽、后续重验失败、兄弟不变和negative不晋级。合成材料不是患者事实。git diff --check退出0。

## 交付层与接续

生产Runner/私人保存/当前源证明恢复已经软件接通；新包实际调用、完整共同发布、病例工作稿、更正后新旧报告及Q3尚未完成。下一在当前源码冻结后，以cbf562为声明来源执行只读复用预检并从现有API合法新建；实际90步计划须一致，不改旧终态或重读合格43组。
