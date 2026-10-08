# 原生来源依赖先于目标字段修复：有界差异审阅

沿既有批准C03只读审阅本次五文件补丁，基础a7de55be。不得修改代码、跑测试、调用产品、读环境/tmp/库/真实方案/临床原答，或递归派发。原C03报告不当成本增量已审证据。

真实新证据（净化）：v2合法产品接续400f018e…两调用/178.479445秒失败，16完成、17失败、73未读。初答additional_requirement缺unresolved_aspects且source_time为空；一次格式纠正后才读到原生标题时间，被SOURCE_TIME_UNGROUNDED正确拒绝。该行完整原生结构只有一个标记列，来源解释scope/stage/time均缺。先前v2依赖reviewer填写时间才选择scope纠正，仍有顺序盲点；不再重复相同长作业。

当前修订只改变选择输入：native_schedule_scope_requires_recheck依据冻结原生列本身，而非核对者是否提了时间。已有scope/stage/time任一不空不触发；必须整行逐字来源、全部实际标记列有明确有源且共同完整标题、无访视/标记脚注未决。复用native_schedule_time_excerpt_is_grounded与原有schedule_column_scope，不补临床时期或采用结论。即使model填null/假时间，来源自身遗漏仍先交既有correct_source_scope；假目标时间照样须经后续完整门核验。

ScopeCorrection只能改授权单条scope/stage/time，不能改原句、用途、例外、兄弟；完整标题格/列等值和现有来源门必须通过，再以原来的一次目标修正核对。source_repairs共用旧预算、repaired_review_indexes不增加机会、不刷新旧调用，失败仍存草稿。validator标记升native-table-scope-recovery/v3；旧来源/编译/Schema/线路兼容及当前门复验保持。不是新语义框架、自动推断或临床批准。

允许读以下完整受影响定义及相邻合同，最多10次有界读取：
- app/agents/protocol_control_source_interpretation.py：两native_schedule助手、build_source_scope_correction_prompt、apply_source_scope_correction与来源/目标验证。
- app/agents/protocol_control_deconstructor.py：8150附近scope依赖修复与局部目标验证；不要全文件扫描。
- app/services/protocol_control_execution.py：当前validator组成及partial复用门。
- tests/v2/protocols/test_slice58c_control_deconstructor.py：6600附近合成原生结构、missing_aspects_no_time_first、假时点、已有scope、预算/重复/transport反例。
- tests/v2/services/test_protocol_control_execution.py：validator-only复验例。
- 如确需，app/protocols/procedure_catalog.py：schedule_column_scope。

重点挑战：是否借原生列选择错误语义对象、错列/跨时期/未知脚注，是否扩大已解释范围或超出原修复额度；模型未填时点时是否仍合法修源；旧成功产物是否可安全在现门复用。给具体反例、第一因果位置和必须修/建议/残余，约1200中文字符。静态审阅未运行测试/未核临床；同会话差异复核非新独立模型金标。
