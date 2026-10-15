Trellis SessionStart 上下文已加载。开始同一局部恢复边界的只读审阅（基线 1ef15ff1；上限 18 次读取；只读、不跑测试、不写文件、不派工；本轮为审阅、不申请 Phase）。先定位三处改动的符号。

符号已定位（gate 2667/2677/2719/3153/4975；transport 1595 为改动门、1518/1582/1855/1887；execution 2124；deconstructor 5683/7552/11243/11621）。并行读取 gate 新逻辑、推荐强度共用点、来源遗漏门与 transport 候选门。

gate 新证明（2664-2708）与 transport 新门（1595，自含单候选不写历史 1609-1613）已读出。继续读 transport 邻居（continue_candidates/restore）、resume 绑定、候选合并冻结、候选分支与当前测试。

补三处必要定义：候选合并载荷（来源冻结层）、gate 语气负例族、transport snapshot 测试。

Trellis SessionStart 上下文已加载。只读审阅完成（18/18 次读取用尽；未跑测试、未写文件、不派工；不把任务说明当结论）。以下为报告。

## 实际已读范围（18/18）

- `app/protocols/protocol_control_gate.py`：2620-2749（**`_literal_parenthetical_prohibition_source` 2664-2674**、**`_modality_source_for_atom` 2677-2708**、`_check_obligation_modality_fidelity` 2711-2749）；3120-3177（第二处 `_modality_source_for_atom` 使用点 3153，用于持期/锚期望；其所在函数体只读到 3177）；4901-5005（`_uncovered_enrollment_prohibitions`：4916-4938 部分覆盖注释、4953-4977 调用 `_parenthetical_prohibitions_are_quoted` 的同候选证明）。`_parenthetical_prohibitions_are_quoted` 本体沿用上一轮已读（基线 78194eae），本轮未重读。
- `app/agents/protocol_control_agent_transport.py`：1510-1621（`continue_session` 1518-1550 仍只认 `_histories`；**`continue_candidate` 1582-1614：新门 1595、单条 user 自含请求 1600、仅真实历史才写历史 1609-1613**）；1848-1909（**`continue_candidates` 1855-1885 仍只认 `_histories`**；`restore_scoped_session` 1887-1900 仅存 64-hex 标记、拒绝不同上下文覆盖）。
- `app/agents/protocol_control_deconstructor.py`：5550-5682（**`_merge_candidate_repair_payload` 5577-5680**：仅收 `candidate_draft` 5590-5593、禁键 5598-5604、字段修订授权 5606-5650、候选重校验 5657-5659、**来源冻结检查仅对非 wire 基线生效 5667-5673**、按位替换 5674）；5683-5702（`_merge_candidate_repair` 全量线校验）；7540-7591（pending-author 绑定：restore 必需 7560-7562、hash=batch+source+pending_author_wire 7563-7567、"不恢复任何批准" 7575-7582）；grep `candidate_only=True`（11243 focused 循环；主分支 11621）。
- 测试：`test_slice58c_control_deconstructor.py` 11660-11759（该测试新增 `followup/followup_sibling` 故障；missing_authority 走 candidate-only）；`test_slice58c_protocol_control_gate.py` 2030-2129（可选→必做不可改 2038-2052；括号禁止自带语气正例 2055-2070；focus 负例 2073-2086；可选语气不误配无关可能性 2089-2110）；`test_protocol_control_agent_transport.py` 1530-1644（scoped 仅开自含方法 1548-1574；**snapshot 候选续作 1577-1599**；scoped 单元修订 1602-1624）。
- `app/services/protocol_control_execution.py`：2124（新组成 `scoped-prohibition-modality-and-candidate-continuation/v1`，grep）。

## 三处改动结论与挑战核对

**1）gate 语气来源（prohibit_event 专用 focus）。** `_literal_parenthetical_prohibition_source` 仅对 `kind=="prohibit_event"` 生效（2667），复用的证明要求：该原子引用的某摘录中禁止词全部在括号内、无嵌套/混搭括号、**statement 与括号片段逐字相等**（normalized）、且原子以独立片段（或一对包裹）引用之；覆盖一栏因 clause 就是其自身引用而恒真，因此实际证明=逐字片段+独立引用。命中则 `_modality_source_for_atom` 返回 statement（2689-2691），否则走原回落（2693-2708，普通原子不变）。真实作业的"上位句允许语气误拦"由此消除；另一候选"豁免写成 recommended"因非 prohibit_event（或证明不成立）仍走完整引用，`RECOMMENDED_MODALITY_UNSUPPORTED` 保持（测试 2038-2052 与 2711-2736 逻辑）。
- 已核反例（成立）：片段内自带豁免/可选语气仍被查（2073-2086 `exemption_prohibition` 期望 `EXEMPTION_MODALITY_OVERSTATED`；因 focus 源就是 statement）；缺失独立片段引用（仅引上位句）证明不成立→回落完整引用→上位句的可选语气照旧触发（2073-2086 `missing_fragment`）；原子改义（statement 不等片段）→回落（`changed_statement`）；双重括号禁止因单原子无法同时满足两个片段→回落完整引用；嵌套/混搭→不命中（上一轮实读机制）。
- **可达反例 C1（主发现）**：同一 helper 被 3153 的持期/锚检查共用——focus 命中的 prohibit_event 原子，其 period 期望改从 statement 推导；如 `治疗期（不得使用X）`、片段独立引用、但省略 `prospective_period`：旧行为从完整引用见"治疗期"→`PROSPECTIVE_PERIOD_MISSING`；新行为静默放过。该点无测试钉住（2055-2070 只测两检查通过的正例）。若为有意，请在文档/测试声明；若非有意，最小修法是把"语气 cue 检查"与"持期/锚检查"拆成两个取值口（前者用 focus，后者用完整引用），或补一条"治疗期（不得X）省略持续期间应拒"的负例。注意我只读到 3177，后续分支未读，结论需以完整函数复核。
- 残余观察（非越权）：focus 证明是原子级文本证明，span 局部性/上位全文保留由其他门与提示承担（"主张、条件、span、完整来源仍由原消费者核验"一致）；同一原子多处引用中的其他摘录不再被语气检查扫描（缺测试，可探针）。

**2）transport `continue_candidate` 接受 snapshot。** 1595 允许 `_scoped_resume_contexts`；无历史时请求=单条 user+Schema（1600），**不写 `_histories`**（1609-1613）；响应格式仍只 candidate_draft；`continue_session`（1526-1531）、`continue_candidates`（1866-1867）、`history` 未开放（transport 测试 1569-1573、1597-1598 逐条断言）。runner 侧：`missing_authority` 走**普通已定位单候选**——prompt 含"冻结批次、结构单元和候选范围"、schema 属性恰为 `{candidate_draft}` 无 dispositions（11716-11720）；未见历史伪造；`continue_candidate` 的物理调用前无会话时零调用（transport 1583-1585）。
- `followup`：二次合法单候选经同一 snapshot 再次发起（requests=2、单条 user、Schema 只 candidate_draft），合并后**再次经过完整消费者**（seen==3、已解析）——即真实作业的"后续因缺会話失败"已修；`followup_sibling`（改来源为 su-02）被拒：需要核对、`pending_author_wire` 保留首修、非 transport_failed；`budget`（max=0）0 请求；`bad_json/sibling_source` 首个请求非法即停并附"不得退回整组改写"；`second_gate` 门拒后保留首修。
- 越权面核对：目标由宿主定位错误决定、兄弟经后续恢复/输出层冻结（注意：`_merge_candidate_repair_payload` 对 wire 基线的来源字段**不在载荷层检查**（5667-5673 仅非 wire 基线），冻结落在 `_restore_bounded_wire_repair`/`_validate_bounded_output_repair` 与消费者；本轮未重读两者，测试 `followup_sibling` 以结果钉住）。binding 仍是宿主计算的 64-hex 标记，transport 不比对 prompt——与既有 scoped 字段通道同一信任面，未新增其它普通通道。

**3）组成身份。** 仅追加 `scoped-prohibition-modality-and-candidate-continuation/v1`（2124，grep）；作者/编译/模型/累计预算未动（预算：focus 与候选续作不重置 `repairs`；测试 budget 验证 0 额度 0 请求）。

## 最小建议

1. 处理 C1：给持期/锚检查保留完整引用取值口（或明确声明 focus 仅用于语气），并补一条上位句持期 + 省略持续期间的 gate 负例；不关闭任何门。
2. 可选补两枚探针测试：双重括号禁止（两片段）必须回落完整引用；同原子附加矛盾引用时语气检查是否应扫描其余摘录——用于钉住边界，不必改码。
3. 其余保持：整组回退与 history 通道不开放、不允许伪造历史、不追加整组读取、不引入词表。

## 反证与未读范围

- 可能推翻 C1 者：3153 所在完整函数（3120 之前定义、3177 之后分支）与 `_check_obligation_modality_and_event_anchor` 全体的持期条件；`_parenthetical_prohibitions_are_quoted` 本体本轮未重读（其调用约定与测试为准）。
- 未读：`build_protocol_control_repair_prompt` 的 candidate-only 文案来源（仅测试断言）；`_restore_bounded_wire_repair`/`_validate_bounded_output_repair` 本轮未重读（来源冻结的实际落点，依早前轮次+测试）；service 恢复集成除 2124 外的调用侧；未做 diff（禁 shell）；测试未运行（220.7s/失败的现场描述来自任务说明）。

## 局限

工程审阅≠临床或医学批准，不代跑产品；证据只证明控制流/授权/冻结边界，不证明模型下一答正确或覆盖完整；真实作业的剩余缺陷仍需真实模型与来源核对。本轮为只读、未创建任务；是否需要为 C1 拆出 Trellis 任务（或仅登记为文本清单）？
