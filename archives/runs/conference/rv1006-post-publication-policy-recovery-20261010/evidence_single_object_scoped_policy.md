Trellis SessionStart 上下文已加载。开始同一工作树的局部字段审阅（基线 b898aaba；只读、上限 16 次源码读取、不执行测试、不写文件、不新建 Trellis 任务）。先建立符号与新增点地图。

新增点已定位（`_invalid_scoped_observation_payload` 6622、抢救块 10721-10732、新组成串 2121、新测试 11741；跨 Job 只存合法 `pending_author_wire` 亦由 2798-2818/4639-4644 佐证）。并行读取六个关键区。

核心机制已读出（`_invalid_scoped_observation_payload` 6622-6654 的拼接与索引计算、抢救块 10721-10732、停止块 11329-11380 新增 `OBSERVATION_REPAIR_INVALID` 子句、测试 11739-11835 全貌）。补三处：scoped 解析器的错误码/时间检查、`scoped_unit_repair_ids` 全部装配点、`ContractModel` 额外字段策略。

核心判定点已成形。最后三次读取闭合三个关键问题：scoped 解析器错误码映射（决定抢救是否可达）、作用域恢复/消费者调用点现状、pending-author 绑定调用点现状（16/16 用尽）。

Trellis SessionStart 上下文已加载。只读审阅完成（16/16 源码读取用尽；未运行测试、未写文件、未创建 Trellis 任务）。以下为报告。

## 实际已读范围（16/16）

- `app/agents/protocol_control_deconstructor.py`：1147-1186（`parse_protocol_control_agent_wire` 错误码映射：ValidationError→`WIRE_SCHEMA_INVALID`，1177-1179 三项规范化）；5729-5749（`_parse_repartition_with_checked_time` 全长：5747-5748 复用已核时间属性 + 5749 规范解析）；6390-6830（`_invalid_candidate_payload` 6397-6439、`_single_invalid_candidate_payload` 6442-6444、`_invalid_observation_policy_paths` 6509-6553、`_merge_observation_policy_repair_payload` 6556-6601、**`_invalid_scoped_observation_payload` 6622-6654**、`_build_observation_policy_repair_prompt` 6657-6688）；8385-8530（循环顶：观察合并最高优先 8432-8439、解析链 8440-8511、状态清空 8518-8530）；8531-8575（`_restore_bounded_wire_repair` 调用 8531-8548、hydrate 8565、`output_validator` 8572+）；10490-10805（异常入口 10528-10551、失败捕获 10530-10532、**新抢救块 10721-10732**、范围推导 10773-10805）；11290-11500（停止块 11329-11365、预算自增 11381-11394、通道判定 11395-11460）。另以 grep 实证：dispatch 链首 `if scoped_unit_repair:` 11672-11718（含 11673 `scoped_unit_repair_ids=set(mutable_candidate_source_union)`、11716 调用）；pending-author 绑定 7508-7515、resume_wire 可选绑定 7539-7545。
- `app/agents/protocol_control_agent_transport.py`：1725-1800（`continue_observation_policies` 1738-1767：`_histories` 或 `_scoped_resume_contexts` 门 1745-1746、单条 user 消息 1758、响应格式 1747）。`restore_scoped_session` 本体与 `_scoped_resume_contexts` 门集合为上轮本会话已读实际定义。
- `app/domain/contracts/common.py`：11-12（`ContractModel`，`extra="forbid"`）。
- `app/services/protocol_control_execution.py`：2121（新组成串 `scoped-source-proposal-missing-policy-recovery/v1`）；2798/2807-2808/2818、4639-4644（跨 Job 保存/重载片段）。
- 测试：`tests/v2/protocols/test_slice58c_control_deconstructor.py` 11739-11835（`test_scoped_missing_policy_uses_field_reader_and_preserves_actual_proposal` 全貌）。
- **未读**：deconstructor 6830-7440、8576-10490、**11500-11672（关键：当前 scoped 选择条件 ~1153x 与 prompt 覆盖/dispatch 前置逻辑）**、10805-11290；`_restore_unchanged_time_operands` 本体；候选模型的时间属性校验器；`ObservationPolicy` 交叉校验细节；service 2398-2818/4400-4700 全文（仅 grep 片段）。

## 逐挑战结论

1）索引随保留兄弟重排——正确。拼接后 `merged["candidate_drafts"] = [*siblings, *drafts]`，`index = len(siblings) + 无效项在 raw 中的序位`（6645-6648），paths 计算（6650-6652）与字段合并（8435-8437）都作用于同一 `merged` 与同一 index；其后的 `_restore_bounded_wire_repair` 可能重排，但 hydrate/门禁按身份而非序位，字段写入已按正确候选完成。
2）局部无效提案未被误当已核——`repair_baseline_raw` 仅作未采用暂存（10729），采用必须经 8439 全线解析→8531-8548 作用域恢复→8565 hydrate→8572+ 完整输出校验；实际回答进入 attempts 回执；测试 11807（原件不突变）与 11820-11824（采用内容=实际提案+字段补写）双重钉住。
3）scope/span 与错误分类——处置集合严格 == 授权单元（6635）；每个 raw 候选来源单元 ⊆ 授权、来源 span ⊆ 授权单元实际 span 并集（6632-6637）；跨闭包旧候选一律拒绝（6638-6640）；唯一无效候选 + 全部错误均为缺观察说明（6627-6628、6533-6553，任一其他错误即 `()`）。两个边界注记：span 检查是"授权单元并集"级而非逐单元配对（与既有 `_merge_scoped_unit_repair` 同粒度，逐单元一致性仍由后置全门禁承担）；候选级校验看不见的线级缺陷不会在此分类，会在字段轮后暴露并由停止/预算兜底（fail-closed，无采用）。
4）兄弟保留与真实消费者——兄弟取自 previous 中与授权不相交者（6645-6647），恢复期按闭包参数再冻结（8531-8548）， hydrated 消费者在测试中调用**真实** `validate_protocol_control_batch_candidates`（11791）；11825-11828 断言兄弟候选与处置原样。
5）错误/传输/额度不退整包——坏 JSON/越域/混合：抢救返回 None，`failed_scoped_unit_repair` 保留→停止 11331、回执文案 11362-11365；字段返回非法（position/quote/extra_field）：11332-11333 的 `OBSERVATION_REPAIR_INVALID` 子句直接停止；传输故障：dispatch 边界异常→需要核对；额度：11355 以既有 `repairs` 计数（无新预算），`max=1` 时字段轮被拒（测试 11809-11810）。closure 授权仍 True 时 candidate/整批通道本身被 `not allow_source_closure_rewrite` 排除；`continue_session` 对空 `_histories` 也会拒绝——三层都不会到达模型。
6）真实测试是否抵达字段调用——设计上抵达：只覆写 `_complete`（11775-11785），运行级断言 `requests==2`、第二条为单 user 消息且 schema 属性 `== {"items"}`（11810-11816）、`_histories=={}`（11808）、字段提示文案（11814）。我未运行测试，不背书其绿色。

## 可达问题

- **R1（恢复可用性缺口，fail-closed）**：抢救路径绕过正常 scoped 路径的"复用已核时间属性"步骤。正常路径 `_parse_repartition_with_checked_time` 在规范解析前对来源匹配的草案执行 `_restore_unchanged_time_operands`（5742-5748）；新抢救只用 `_invalid_candidate_payload` 的三种规范化（6412-6414，与 canonical 1177-1179 同构，但**不含**时间属性恢复）。若实际局部回答对未变原子省略/改写已核时间属性（正常路径靠该步骤保真，模型被允许不重发），候选校验会产出时间类错误 → 与缺政策混合 → `_invalid_observation_policy_paths` 返回 `()`（6543）→ 抢救 None → 停止。即：该恢复只在"回答除缺政策外完全自包含"时生效。另一分支（若校验器容忍省略）：合并线将缺少该保真步骤，仅靠后置门禁兜底。两种分支都不产生越权采用，但都会使真实场景可能停在需要核对。最小建议：在 `_invalid_scoped_observation_payload` 内复用 5742-5748 的匹配与恢复（确定性复用已核属性，不新增授权面），或明确把"自包含原子"写为恢复前提并补一条省略时间属性的负例/正例测试。
- **J1（关键未读结合点）**：本文件 dispatch 链首是 `if scoped_unit_repair:`（11672-11718 实证），而抢救轮里因解析异常时 `output is None`，权限反赋值块（10733 之后的 10825-10834）被跳过，闭包授权/union 仍为 True。若当前 scoped 选择条件（~11535，位于我读窗 11290-11500 之后、未读）未排除 observation 状态（如缺 `observation_repair_candidate is None`），第二次物理调用会是 scoped reader（batch schema），测试 11816 的 `{"items"}` 断言会失败。该测试本身能暴露此点，但窗口仍在运行、我未运行它，故此结合点必须显式核对；最小修法即在选择条件补该排除（或抢救时清闭包授权），二选一以现状为准。
- **R2（跨 Job 限制，非缺陷但需区分）**：服务侧保存的是 `result.pending_author_wire`（4639-4644），重载要求 `ProtocolControlAgentWire.model_validate` + sha 一致（2807-2808）——**无效 raw 提案结构上无法成为跨 Job 恢复输入**；新 Job 会重发一次局部提案。本增量只实现"运行中字段恢复"，未实现"跨 Job 重用旧无效答"；且未通过伪造会话/回执绕过（transport 绑定仅 `restore_scoped_session` 写入、`_histories` 保持空，测试 11808 即证）。
- R3（小项）：`_invalid_candidate_payload` 对 payload 做原地规范化（6412-6414），与 canonical 解析一致，属刻意设计（注释 6410-6411）；其保真度依赖两处规范化函数长期同步，当前同构，仅记录。

## 反证（可能推翻上述）

- 未读窗口 11500-11672 若含额外守卫或不同选择文本，J1 结论需修正（当前只能证明"若不排除则路由错"）。
- `_restore_unchanged_time_operands` 采用方（`_merge_candidate_repair_payload`、`_parse_repartition_with_checked_time`）之外的第三种调用若存在于未读窗口，R1 不成立；我已读的抢救两函数（6622-6654、6397-6439）内确认无此调用。
- 候选模型对"有 time_constraint 而求值缺时间属性"的实际校验规则未读（决定 R1 落在停止分支还是保真分支）。
- 测试未运行；逐故障路径为代码推演。夹具（11753-11758）复制完整 evaluation、仅置空 policy，未覆盖 R1 的省略时间属性场景。

## 最小建议汇总

1. 核对 J1 的选择条件/dispatch 前置（一行排除即可）；这是本增量可达性的开关。
2. R1 处理二选一：复用 5742-5748 恢复（推荐，纯确定性）或显式声明前提；两种情况都补对应测试。
3. 其余保持现状：授权生产、预算、停止、门禁、身份均未动；组成身份仅新增 2121 一项（与既有 `_same_deep_components_with_current_gate` 机制一致——上轮已读，只允许 `validator_version` 差异）。

## 局限

证据全部为控制流/授权/冻结边界：**不证明模型下一条回答正确**；同模型家族仅为程序与上下文分离，不是独立金标；不构成临床或产品批准。未接触临床原件/原答/env/DB；未执行测试；16 次读取窗口导致上述未读区（尤其 J1、时间校验器）。跨 Job 结论基于服务层 grep 片段（2807-2808、4639-4644），非全函数通读。

请确认：集中窗口是否包含 J1 的路由断言（第二次请求 schema `{"items"}`）？另，本轮为只读审阅、未创建 Trellis 任务；如需把 J1/R1 登记为任务请告知。
