# Execution Output: phase5-generic-semantic-contract-repair-20260902 - worker_03

## Boundary And Context Check

- 只在 runner 绑定的当前工作目录（worktree `phase5-clinical-facts-profile`）内活动；初始读集为 `context/phase5-generic-semantic-contract-repair-20260902_execution_context.md` 与 `plans/codex_execution_phase5-generic-semantic-contract-repair-20260902.md`。
- 我的指派是工作项 3：新增反过拟合故障注入与回归测试（合成中文条款），证明新合同消除假阳性但仍拒绝真实遗漏、虚构任选关系、跨来源、未绑定时间窗。工作项 1（提示合同）与 2（确定性门禁）属于 worker_01/02，我未修改任何生产或应用源文件。
- 唯一新建工件：`tests/v2/protocols/test_generic_semantic_contract_fault_injection.py`（git 状态 `??`，纯新增）。报告按规程不自行写入 `runs/.../worker_03.md`，随本响应返回。
- 重要环境事实：worker_01/02 的修订在本会话进行期间**逐步合入同一工作树**（`app/agents/protocol_deconstructor.py`、`app/protocols/deconstruction_gate.py` 的 diff 在会话中途从无到 +3148/+645 行）。我的测试因此同时充当了新合同的“验收靶”：多次重跑中，防假阳性断言随其修订落地由红转绿，最终状态见下文。

## Work Performed

新增合成条款故障注入与回归测试套件（31 条测试），全部条款为本文件发明的 `SYN-001` 合成方案文字（合成药物“试验药甲/乙”、“镇静类药物成瘾史”、“活动性结核病史”等），零项目特异规则、零硬编码临床结论。

套件结构（四层）：

1. **全合成基线回归**：`_baseline()` 构造一个通过全部十二项门禁检查的合成草稿，父规则刻意覆盖五个目标语义维度——结构引导语+“并且”并列义务（IN-02）、“满足下列条件之一：…或…”替代（EX-01）、“和/或”共享期间逐字绑定到每个分支（EX-02）、“无…病史”否定绑定被断言对象+随机锚点时间窗（EX-03）、数值阈值（IN-01）。
2. **防假阳性回归**（ objective 的五个维度）：
   - 非限制性人群：`性别不限/男女不限/年龄不限/种族不限/民族不限/可以入组本研究/可以参加本研究` 均不得成为实义义务（单元级），且“年龄≥18周岁\n男女不限”集成场景不得触发 `PARENT_RULE_OBLIGATION_NOT_COVERED`；
   - 结构引导语：常见形态不得成为义务；
   - 明确“之一”替代：含“或”与纯顿号列举两种“之一”句式 × 两个合成条款族（妊娠/用药）参数化，ANY 均不得被判为虚构任选；
   - 共享期间：`筛选前3个月内…和/或…` 每分支以 `source_clauses` 绑定共享片段时零时序误报（基线覆盖+专项断言）；
   - 否定对象：`无活动性结核病史` 的 NOT 谓词由“无”前缀直接支撑，零否定误报。
3. **故障注入**（四类拒绝，全部从通过基线出发、单点变异、断言确定性 issue code）：
   - 真实遗漏：源文本多出一条实义子句而草稿未承接 → `PARENT_RULE_OBLIGATION_NOT_COVERED`（含“未承接：…”精确断言）；新增实质 span 未被任何子组件覆盖 → `PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING`；
   - 虚构任选：同一对分支在**无任何替代连接语**的顿号术语清单上建 ANY → `DISJUNCTION_NOT_BOUND_TO_SOURCE`（与“之一”合法场景构成最小对比对）；“并且”并列被拆成 ANY → `CONJUNCTION_CHANGED_TO_DISJUNCTION`；
   - 跨来源：子组件借用其他父规则 span → `COMPONENT_SOURCE_OUTSIDE_PARENT`；谓词 `source_clauses` 混入其他父规则子句 → `PREDICATE_CLAUSE_NOT_IN_SOURCE`；资料要求借用其他组件来源 → `REQUIREMENT_SOURCE_OUTSIDE_ORIGIN`；
   - 未绑定时间窗：谓词丢弃时间限定与窗口 → `TIME_QUALIFIER_DROPPED`；共享限定语未逐字绑定到分支 → `SHARED_TIME_QUALIFIER_NOT_BOUND`×2；凭空发明“随机前6个月”窗 → `TIME_CONSTRAINT_NOT_IN_SOURCE`。
4. **反过拟合维度**：“之一”合法性与顿号虚构性用两个独立合成条款族（FAMILY_PREGNANCY / FAMILY_MEDICATION）参数化——同一对分支、不同术语，行为一致，证明门禁按连接语而非按词条判定；提示合同层新增 1 条断言：`_SYSTEM_CONTRACT` 必须把“之一”列为明示替代连接语。

**最终运行结果（当前树）：29 passed / 2 failed**。通过侧证明已落地的新合同消除了全部五个维度的假阳性并保持四类拒绝；2 个失败是精确定位的剩余合同缺口（见 Rerun Requests），非测试缺陷。

## Artifacts And Evidence

- 新建：`tests/v2/protocols/test_generic_semantic_contract_fault_injection.py`（31 条测试；唯一被授权写入的工件）。
- 只读证据源：`app/protocols/deconstruction_gate.py`（`_substantive_obligation_segments`、`_has_unambiguous_disjunction`、`_branches_have_source_disjunction`、`_ALTERNATIVE_LEAD_IN`、`_temporal_semantics`、`_source_coverage`）、`app/agents/protocol_deconstructor.py`（`_SYSTEM_CONTRACT`）、`tests/v2/protocols/test_deconstruction_gate_slice3.py`（既有 fixture 模式参照）、`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_*.md`（“先用通用、非项目特异失败类型收敛”的边界依据）。
- 会话中途观察到的并行落地证据：新门禁出现 `_ALTERNATIVE_LEAD_IN` 正则（含“之一/任一/任选其一/一项或多项”绑定结构名词）、扩展的 `structural`/`nonrestrictive` 正则；`_SYSTEM_CONTRACT` 会话末已含“之一”。我的对应防假阳性测试随这些落地由红转绿（四轮结果：12F/19P → 5F/26P → 3F/28P → 2F/29P）。

## Commands And Observations

- `uv run pytest tests/v2/protocols/test_generic_semantic_contract_fault_injection.py -q` → 最终 `2 failed, 29 passed`（约 0.1s，纯确定性、无模型/网络/存储）。
- `uv run pytest tests/v2/protocols/test_deconstruction_gate_slice3.py -q` → `114 passed`（与既有门禁回归无冲突）。
- `uv run pytest tests/v2/protocols/ -q` → `1350 passed, 5 failed`；其中 2 个失败为本套件的两个既知缺口参数，另两个为与本工件无关的既存/瞬态问题（见下）。`test_protocol_transport_transient_retry.py` 单独重跑 `14 passed`，此前整跑失败判为并行改树瞬态。
- `uv run python -m compileall <新文件>` → OK。仓库无 Ruff 可执行文件（与 20260901 检查点一致），未虚构 lint 结论。
- 开发期内部修正 3 处测试自身缺陷（`AtomicExpression.predicate.predicate_id` 访问、tuple/list 拼接、IN-01 原子表达式无 `children` 包装），均已修复并复跑确认。

## Blockers Or Missing Environment

无环境阻塞。两个非本工件范围的观察（供 Codex 处置，均未由我修改）：

1. **剩余合同缺口（本套件 2 个红灯，即其设计功能）**：`_substantive_obligation_segments` 的 `structural` 正则（`app/protocols/deconstruction_gate.py` 约 640–657 行）未覆盖两个常见引导语形态——`符合下列入选条件`（“入选条件”复合名词不在名词表）与`包括以下情况`（`包括` 仅在裸词形态被过滤）。后果：当此类引导语作为独立 span/分段出现时，义务级检查会误报 `PARENT_RULE_OBLIGATION_NOT_COVERED`（label-skip 只豁免 source_coverage 的 refs[0]，不豁免义务检查）。精确实词形态全匹配过滤不会吞掉实义条款（fail-closed 可保持）。
2. `test_protocol_replay_harness.py::test_d001_p803_p805_read_only_checkpoint_rebuilds` 因提示合同修订导致冻结 prompt SHA 漂移而失败——与 CHECKPOINT_20260831 记录的既存模式一致（旧检查点不得改哈希，需单独做提示合同版本化/重放迁移），属预期的并行修订后果。

## Rerun Requests Or Next Step

- 请 Codex 决定剩余缺口处置：若认可把 `符合下列入选条件`、`包括以下情况` 纳入结构引导语过滤属工作项 2 范围，转交 worker_02 按上述正则位置做最小修订；修订落地后本套件应 31/31 全绿。
- 建议在验收时把本套件与 `test_deconstruction_gate_slice3.py` 一并作为新合同的确定性验收靶（两者合计 145 条，当前 143 通过）。
- worker_01/02 报告落定后，建议在归档前再跑一次本套件，确认并行合入后无回归（本会话期间树持续变化，最终状态以本报告运行结果为准）。
