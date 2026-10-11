证据收集完毕（含四个核心文件全文、两个解构器的政策段、以及三处相邻依赖的定向核读）。以下为完整会议输出。

# Conference Output: r05-no-repeat-source-20260916 - evidence_single_object

## Output

### 0. 身份与回退声明

原定主路由 `codebuddy/codebuddy-cli/deepseek-v4.1-flash` 在可续会话存在前即不可用；本次由声明的回退 `zcode` / `GLM-5.3-Flash`（effort max）承担同一有界角色 `evidence_single_object`（重要证据审阅，serial）。能力限制：仅执行只读源码审阅（按任务约束未运行测试、未调用产品、未访问 DB/浏览器），因此**全部结论均为仅源码级结论，缺运行时验证**；未读取指定五文件之外的大范围代码，三处相邻读取仅用于裁定具体依赖（`qualified_observation_relation.py`、`protocol_controls.py::validate_control_repeat_conditions`、reason code 消费点检索）。

### 1. 审阅范围与方法

通读 `repeat_scheme.py`（198 行全文）、`repeat_result_selection.py`（107 行全文）、`repeat_result_resolution.py`（175 行全文）、`repeat_atom_calculation.py`（217 行全文）；`protocol_deconstructor.py` 的政策合同文本（398–459）、wire schema（679–702、712–799、930–975）、转换与校验（1980–2031、2170–2179）；`protocol_control_deconstructor.py` 的 wire 校验（462–484、536–556）、候选校验（715–744）、政策合同文本（1280–1330）。对照任务契约逐条核验：错误初查回退、被绕过的来源守卫、确定性错误路径、历史哈希变化。

### 2. 契约符合性核验（仅源码结论）

以下各条**核验通过**，均给出证据：

- **字段定义与序列化**：`no_repeat_result_use` 为 `Literal["retain_initial","no_result","unresolved"] | None`（repeat_scheme.py:114）。None 时序列化器删除该键（:121–122），v1/v2 载入该字段直接报错（:137–138）。因此**历史记录哈希不变**：`canonical_hash(scheme.model_dump(mode="json"))`（selection:42、resolution:89）对旧 scheme 输出与加字段前逐字节一致，已封存的 `constraints["scheme_sha256"]` 比对（resolution:93）不受影响。
- **新解构强制非空**：`require_current_extraction`（repeat_scheme.py:187–188）在 v3 且 None 时报“须说明没有复查记录时原文允许采用什么结果”；predicate 侧转换时调用（deconstructor:2176–2177），control 侧 wire 校验对条件原子与义务原子均要求 `repeat_scheme` 显式出现在 `model_fields_set` 并调用同函数（control:474–477、552–555）。wire schema 将全部属性设为 required（deconstructor:699），迫使模型显式给值或显式 null 后被拒——符合“无沉默缺省”。
- **禁止无根据推断**：两处解构合同均明确“不能仅因复查为 optional 或未见记录就推断 retain_initial；这一字段不证明复查未发生或资料齐全”（deconstructor:445–447、control:1308–1310）。无 absence 推断、无 optional-许可推断。
- **无复查时的选择顺序**：selection 先查 supplied scope（:56–57，scope 不完整→`repeat_result_scope_incomplete`，此时不得断言无复查），再查政策（:58–60）：`no_result`→`repeat_result_missing`，`unresolved` 及历史 None→`repeat_absence_policy_unverified`（None 走三元的 else 分支，正确失败关闭）。**旧代码在此处会直落 :89–90 静默选中初查；新代码封堵了该静默初查回退**——这是本次政策的核心改进，已验证。
- **既有复查不被隐藏**：政策分支仅在 `repeat_group_ids` 为空时触发（:55）；resolution 对每条 repeat 保留 trigger/permission/count/time 四项 checks（:110–136），atom 计算的 audit 保留全部组的 `acquisition_results`（:205–208）。无效复查作为证据保留，不因采用政策被丢弃。
- **retain_initial 保持既有守卫**：初查路径仍受 role=="initial"、`structural_reasons`、祖先闭包、scope 检查约束（selection:61–69、84–88；resolution:149–151 注释与实现一致）。
- **附加条件不嵌套复查**：control 侧代码强制“复查条件不能再次嵌套复查要求”（protocol_controls.py:1296–1298），非仅 prompt 约束。
- **条件性缺席（trigger FALSE）未实现**：selection 与 resolution 全链对 trigger 不感知缺席合规性——与“待定能力、不声明完成”一致，代码无任何声称已完成之处。

### 3. 缺陷与风险（按影响排序；均为源码级，含最小修正）

**F1（最重要，P2）：初查范围守卫存在不对称绕过路径（fail-open）。**
`repeat_result_selection.py:61` 将 initial-scope 完整性守卫门控在 `scheme.result_use == "retain_initial"` 上，但选中初查组的返回点有**两个**：受守卫的 ：63–64 与**不受该守卫的 ：89–90**。两条暴露路径：
- (a) `result_use != "retain_initial"` + `no_repeat_result_use == "retain_initial"` + 零复查 + `initial_scope_complete=False` → 走 ：89 选中初查，:62 的阻断（本应返回 `repeat_initial_scope_unverified`）永不执行。这正是本次会议主题场景——无复查记录时依赖 no_repeat 政策采用初查——却恰好漏掉初查范围核实。
- (b) `initial_scope_complete=None`（resolution:146 以 `.get` 链读取，历史封存 observation 缺 `initial_scope` 键时为 None）→ 对 `result_use=="retain_initial"` 守卫整体跳过，:87–88 直接选中初查。标志**存在且为 False 时阻断、缺失时放行**，方向与 fail-closed 相反。
可达性核读：当前生产方 `qualified_observation_relation.py:219–231` 总是写入 `initial_scope.complete` 布尔并传入 `initial_scope_complete=not initial_reasons`，且 origin/角色失败大多同时污染整体 `scope_reasons`（:184–189），故 (a) 在新数据上窗口很窄、(b) 仅影响加字段前封存的 observation 在重算时的行为。但守卫应靠构造成立而非依赖生产方惯例。
**最小修正**：将 ：61 的条件扩为“凡将选中初查组即要求标志”——`scheme.result_use == "retain_initial" or (scheme.no_repeat_result_use == "retain_initial" and not repeat_group_ids)`；并将 `initial_scope_complete is None` 视为未核实（返回 `repeat_initial_scope_unverified`）而非跳过，或在 resolution 层校验 supplied_scope 载荷必含 `initial_scope`。

**F2（P3）：`repeat_result_missing` 一码三义。** 政策性缺席（selection:59）、组内零事实（atom calc:156）、无可用选中组兜底（:177）共用同一 reason code。按“缺失来源义务须单列”的项目边界，政策性缺席应可被下游区分以生成具体义务项（建议独立码如 `repeat_result_absent_per_policy`）。消费方在本次审阅集之外，见 Q1。

**F3（P3）：初查不唯一时政策评估被跳过。** resolution:140–148 中 `len(initial_ids) != 1` 时 selection 为 None，无复查政策（含 `no_result`）从未参与判定，输出仅含 `repeat_initial_scope_unverified/not_unique`。失败关闭方向正确，但理由流丢失政策层信息。可在该分支追加政策理由。

**F4（P2，迁移语义）：旧封存结果的沉默初查选中不会被动失效。** 政策改动前计算的已存 resolution（旧行为会走 ：89–90 选中初查）与现行输出同为 `repeat-result-resolution/v1`（resolution:161）、scheme 同为 v3——**版本串未区分**。重算会因 `policy_selection` 变化改变 `resolution_sha256` 从而可检出，但无机制主动强制重算。不构成“后段证据静默改写前段”（旧结果未被改写），但陈旧错误结果会以有效外观继续存在。见 Q2。

**F5（信息项）：** selection:61–64 将 role 不匹配与 scope 不完整合并为 `repeat_initial_scope_unverified`；且该早退使 `result_use=="retain_initial"` 时绕过 ：65 的 `structural_reasons`——与 resolution:149–151“复查执行问题不阻断初查真值”的设计一致，但若 `structural_reasons` 可能描述初查组自身则被掩盖（见 Q3）。

### 4. 给 Codex 的异议、建议、决策点与有界问题

**最高影响异议**：F1。任务契约明确“No-repeat selection first checks supplied scope and this policy, **then existing initial/source guards**”——而 ：89 路径恰恰在无复查场景下缺了 initial/source 守卫之一，与契约文字不符。建议按 F1 最小修正后，为 (a) 场景补一条确定性单测（零复查 + no_repeat=retain_initial + initial_scope_complete=False + result_use=use_last_repeat）。

**建议**：F2 的独立 reason code 应在义务项生成器落地前定稿，避免下游按码分派时二次迁移；F4 建议对政策改动前封存的、`selected_group_ids` 恰为初查且无复查记录的 resolution 做一次定向审计清单，而非全量重算。

**决策点（请 Codex 裁定）**：D1 = F1(b) 中历史 observation 缺 `initial_scope` 时，选“视为未核实（更严，可能翻旧为 unknown）”还是“按 supplied_scope 版本号放行旧载荷（保兼容）”——两者都消掉 fail-open，但对存量重算结果的影响面不同。D2 = F4 是否需要版本标记或审计清单。

**有界问题**：
- Q1：哪一个组件消费 selection 级 `repeat_result_missing`/`repeat_absence_policy_unverified` 来生成“落实复查记录是否存在”的具体义务项（责任方、动作、可接受证据、到期节点、来源定位）？若尚无，`no_result` 政策目前终止于原子 UNKNOWN 理由而无显式义务项——请确认这是否为既定归属。
- Q2：政策改动前已存结果是否有审计/重算/版本计划（见 F4）？
- Q3：`structural_reasons`（observation_relation_graph.py:98 产出）的取值空间是否可能描述初查组自身？若是，F5 的早退掩盖需要处理；若否，F5 降为信息项即可。
- Q4：确认“trigger FALSE 时条件性缺席合规”仍是待定能力、本期不声明完成——本次源码核验与此一致，仅求书面确认。

### 5. 未验证项声明

未运行任何测试或产品路径：上述所有行为推断来自静态阅读；`select_repeat_result_groups` 与 `repeat_result_resolution.py` 的联合行为（尤其 F1 的两条暴露路径）未有用例执行证实；`calculate_repeat_numeric_result`、`qualified_binding_selection.py`、义务项/缺口生成下游均在授权读取集之外，相关判断止步于接口证据。未发现需要捏造缺陷的情况；F1 是本次审阅实际发现的唯一构造性守卫缺口。
