Trellis SessionStart 上下文已加载。开始限定只读审阅（基线 9fb3ade；上限 14 次读取；不派工、不运行、不改文件；git diff 因非交互权限早前被拒、本轮不再重试——以实际定义与测试为据并如实标注）。先定位分流条件、基线回退与身份组成。

定位完成（分流条件 10388-10398 已现出"单错误/单声明/在 cited_unexpressed"的解耦；测试签名新增 `unresolved_sibling` 参数 417；基线回退 7510/7614-7616）。并行读取关键区与身份兼容测试点。

补两处决定性区域：数值块尾部的复查证明调用点与 runner 测试余部（兄弟未决断言）。

补两处：夹具（force 与 scheme 设定）与 validate 尾部（许可/事件计数拒绝点）。

最后一读：比较词表与许可相关模式（定位新负例 `event_count`/`mandatory_permission` 的拒绝点）。

修正：上一次该函数读取的行号与最新 grep 偏差（+5），必须直接复核函数体以确认许可/事件计数的拒绝点。

最后复核 `source_declares_uncompared_action_count` 当前真实函数体（消除行号偏移）。

Trellis SessionStart 上下文已加载。限定只读审阅完成（14/14 次读取用尽；未运行测试/模型/服务、未改文件、未派工、未新建任务；git diff 因非交互权限早前被拒、未重试——差异结论以当前实际定义与测试为据，行号曾出现一次显示偏移，关键函数均已用直读复核；报告不复述任何原文）。以下按要求分列。

## 一、结论（先回答两问）

- **解耦是否扩大修订授权/绕来源/绕预算/绕兄弟依赖/重复计费**：**未发现扩大**。放宽的只是"触发条件"——不再要求"数值错误的声明集合 == 全部未完整表达声明"，改为**单错误、单声明、且该声明在 `cited_unexpressed` 内**（deconstructor 10396-10398）；其余闸门（单错误 10384-10386、原子路径唯一、会话身份 10419-10420、字段白名单合并 7063-7144、合并后整线校验 7139、路径去重 10403-10404、预算 10400/10405-10406）全部保留。兄弟未决不会被修、也不会被采用；跨运行存在**有界重复计费**（见建议 S1）。
- **基线回退要不要在本窗口改**：**建议保留安全边界，不在冻结窗口改**；下一步查另一时间首错（兄弟声明的时间关系未逐项证明）。理由：回退点是"绝不把未过消费者的编辑当草稿"（7614-7618 与注释 7615）；兄弟未决不清，`final_output` 本应为空；代价仅是"下次运行可能再花一次单原子修复"。

## 二、已证（源码+测试直接支持）

**A. 分流与解耦**
1. `cited_unexpressed` 限定为"有候选字面引用"的未完整表达声明（10379-10382）；数值失败只取 `numeric_predicate_missing` / `repeat_scheme_missing` 且 `atom_paths` 恰一条（10384-10386）。
2. 修复执行条件：`len(numeric_failures)==1`、`len(statement_ids)==1`、`statement_ids[0] in cited_unexpressed`、reader 可调用、`max(repairs, source_repairs) < max_schema_repairs`（10396-10400）。
3. `repeat_scheme_only` 另外要求 reason 为 `repeat_scheme_missing` 且该声明满足 `source_declares_uncompared_action_count`（10388-10392）；该分支禁用 numeric-predicate reader（10393-10394）。
4. 授权面：单一原子路径；提示/合并白名单（原句/类型/强度/来源/后续义务/研究者判断冻结，7122-7131、7191-7198）；合并以 `ProtocolControlAgentWire.model_validate` 收口（7139）。
5. 来源：`cited_unexpressed` 依赖 `_literally_cited_*` 字面引用；不存在"未引用却被修"的声明。

**B. 兄弟依赖与不采用语义**
1. 兄弟失败仍在 `alignment_failures` 中：`if not alignment_failures` 同时挡住来源目标复核要求（10453-10456）与语义闭包修复（10465-10469）——同轮不可能借该路径修掉兄弟。
2. 修复原答只作为 attempt（outcome="parsed"、含 raw 文本、`automatic_adoption=False`、workflow_phase=reviewed_atom_repair；10409-10411、10439-10444）。
3. 未完成时 `build_result` 把 `partial_wire/coverage/alignment/review` 还原为修复前基线（7614-7618）——即"局部正确修复不被采用、不冒充草稿"。
4. 测试钉住：`test_source_repeat_count_runner_requests_only_missing_scheme_and_rechecks`（415-522，reply×`unresolved_sibling` 双参数）：原子调用恰一次；无兄弟且成功→采用（与原始线仅差 repeat_scheme，512-514）；**有兄弟且成功→final 为空、partial_wire 与原线逐字相等（516）、重新对齐（alignment_calls==2）、存在 parsed 的 reviewed_atom_repair attempt（520-521）、兄弟候选未被改（522）**；`continue_numeric_predicate`/`continue_scoped_unit_repair` 被禁（500-503）。

**C. 预算**
- 单计数器：`repairs = max(repairs, source_repairs)+1; source_repairs = repairs`（10405-10406）；`build_result` 回写 `pending_author_repairs_used = max(resume_..., repairs - source_repairs)`（7520-7521），此处差值为 0，**无重复计费**（运行内）。

**D. 本次窗口同时收口的两条前轮建议（已证）**
1. 许可强度对齐源力：`_source_repeat_count_is_preserved` 461-464——`permission="required"` 仅在 `statement.force ∈ {required, conditional}` 成立；`optional` 不得配 required/prohibited；`forbidden` 必须配 prohibited；违反即返回 False → 落到严格数值门拒绝（测试 `mandatory_permission` 期望抛错，340-342）。
2. 纯事件次数排除：`source_declares_uncompared_action_count` 428-436 新增复查动词模式（复查/复测/复验/复检/重测/重复或再次+测量检查检验检测/retest/recheck/repeat...）；事件发生次数句式不含该动词 → False → 严格数值门拒绝（测试 `event_count` 期望抛错）。
3. 证明身份：候选含任一 scheme 时输入身份加入 `repeat_count_alignment`（563-586）；组合身份列表新增 `SOURCE_REPEAT_COUNT_ALIGNMENT_VERSION`、`SOURCE_HEADING_SCOPE_RECHECK_VERSION`、`"source-single-atom-sibling-recovery/v1"`（execution 2127-2132）；兼容语义测试（tests/services 704-710）：除 `validator_version` 外全同才可复用旧结果、旧门只允许"重新验证"路径。

## 三、必须修复

**无已证必须修复项。** 读取窗口内未发现越权、吞错、漏预算或兄弟被绕的源码证据。

## 四、建议（正例/危险反例/消费落点）

- **S1（跨运行有界重复计费）**：`reviewed_atom_repairs` 每次 run 新建（8614），无恢复参数；而基线回退丢弃已修线，恢复运行可在无新证据下再花一次单原子修复。正例：兄弟未决期暂停→下次恢复若已持久化"已尝试原子路径"，可直接复用或跳过；危险反例：按路径粗暴持久化会在原子前置变化后错误跳过——必须按"路径+前置哈希"键（与 8297 的标题重核、7500-7505 的语义单元持久化同法）。消费落点：runner 恢复路径、`reviewed_atom_repairs`。建议先**记录为已知余量**，等产品决定；不改本窗口。
- **S2（复查动词表残余）**：428-436 的动词模式覆盖常见中英表达；表外同义表达会使该分支不触发而落到严格数值门（fail-closed，不会误采用）。正例：现表内短语正常；危险反例：无（方向是"拒"，不是"放"）。仅当出现真实误拒样例再扩展，不引入病种表。
- **S3（文档化）**：把"基线回退=不采用；修复仅在 attempts"写入本分支注释/回执说明，避免后续维护者误加"把修复线直接当 partial_wire"。

## 五、未验

- git diff 不可用（权限拒绝，未重试）：无法给出精确 base 行级差异；本报告的"变更点"以当前定义+测试为准。
- 服务侧新身份字符串的保存/恢复全文未读；兼容测试仅读完选行（704-710）。
- 兄弟的"时间关系未逐项证明"首错路径本轮未查（消费落点：`validate_candidate_alignment` 时间/例外段 940-959；建议下一窗口专读）。
- 测试未运行；"新选窗68通过/未跑全库"为用户口径。无原件、未做临床判断——本报告不声称已核任何临床含义。

建议的下一步读取窗口：兄弟时间首错（时间/例外段与其触发的对齐/来源目标复核），以确认它能否在不新增机制的前提下被有据解决；本轮未建任务。是否按此优先级进入下一窗口？
