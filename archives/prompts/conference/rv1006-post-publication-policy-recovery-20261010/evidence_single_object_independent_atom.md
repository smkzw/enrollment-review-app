# 单字段恢复与未决兄弟项：限定审阅

沿批准 C03 同会话只读审阅，最多14次定向读取。基线9fb3ade，当前差异仅下述源码与原模块测试。不得读取临床原件、私库、环境或其他线程，不运行测试/模型/服务，不修改文件，不递归会商。程序分离不是独立模型临床金标。

请核实际git diff及完整相关分支：
- app/agents/protocol_control_deconstructor.py 的 cited_unexpressed / numeric_failures / reviewed_atom_repairs / pending_alignment_atom_baseline / build_result。
- app/services/protocol_control_execution.py 的 validator组成身份及恢复历史。
- tests/v2/agents/test_protocol_control_candidate_alignment.py 的 test_source_repeat_count_runner_requests_only_missing_scheme_and_rechecks，及既有numeric字段和局部合并测试。
- tests/v2/services/test_protocol_control_execution.py 的门禁身份兼容测试。

真实运行结构性诊断（不是请你批准临床结论）：同一有源候选包含两个独立声明。声明0缺repeat_scheme，错误定位仅[0,0,0]；声明1时间关系未由原文逐项证明。旧条件要求数值错误的声明集合等于所有未完整表达的声明集合，因此另一未决阻止已定位字段发起一次受控修复。修改只允许一个错误、一个声明、一个原子，声明须仍属于cited_unexpressed；原预算、已尝试路径、会话身份、字段白名单、完整校验和重新核对均保留。

合成正反测试：本节点可复检三次，另项复检前不得干预但候选尚无完整时间表达；只补次数字段，不改其他属性。正确/错次数/改政策/传输失败各与单项及未决兄弟配对。新选窗68通过，未跑全库。尚有兄弟未核清时final_output仍为空，partial_wire恢复原基线；修复原答作为attempt保存，不冒充已采用。初版夹具用持续七天义务，提前触发TEMPORAL_SCOPE_UNRESOLVED，已经替换为实际失败家族的相对事件禁止；不是放松该提前保护。

问题：这处解耦是否会扩大修订授权、绕来源/预算/兄弟依赖或造成重复计费？基线回退意味着局部正确修复仍不会被采用，是否有必要在本冻结交付窗口进一步改变，还是先保留安全边界并查另一时间首错？只指出有源码证据的必须修复、建议和未证；不要另建中间真相/框架/无限修复机制，不要求整方案重跑。给准确函数、正反例和消费落点。无原件的审阅不得声称已核临床含义。
