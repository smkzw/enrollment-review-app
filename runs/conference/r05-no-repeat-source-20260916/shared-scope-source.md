全部版本标记证实（v5/v8/v28/v32/v14，约束保持 v2 与 resolution 同步）。证据链闭合，以下为完整会议输出。

# Conference Output: r05-no-repeat-source-20260916 - evidence_single_object（第五轮：多次共用原文范围）

## Output

### 0. 角色与限制声明

继续同一有界只读角色（回退 `zcode`/`GLM-5.3-Flash`，effort max）：仅源码读取，未写文件、未运行测试/导入/构造/服务/DB/浏览器。**静态审阅非运行或临床验收**；两端引文齐备不等于临床准确，本报告仅核实产品实现的守卫逻辑。收到上轮报告勘误（明确 other_episode 不令覆盖不完整）——已按现版代码核实：constraints:73-74 的覆盖条件是 `all(value != "unresolved")`，明确 other_episode 不阻断覆盖，仅未知阻断，勘误正确，代码无需改动。

### 1. 版本链核验

全部与声明一致：合同/提示 `observation-relation/v5`（observation_relation.py:12、llm:117）、输入 `observation-relation-input/v5`（input:123）、任务 `observation-relation-job/v5` 与摘要 `observation-relation-summary/v5`（receipts:13、:101）、消费 `qualified-observation-relation/v8`（v7文件:12）、资格 consumer/v28（合同:24）、计算 `component-review/v32`（frozen_review_calculation.py:27，:169 旧档门）、发布 `frozen-review-publication/v14`（:31）。序列约束保持 v2（:135）且 resolution:93 单点校验同步，无断链。

### 2. 六项重点逐一核验（file:line 证据）

**(1) 任一模型未支持范围仍被共用 — 无通路。** 消费层要求**双路都提供**非空 shared_scope_excerpt 才置 verified（v8:161-162 `all(...)`），任一路缺失即 False；多组 pair 只要有一项关联未验证即整对按归属歧义移出（:179-188）；下游条件取证再按事实复核 shared 标志，任一多组关联缺证明即 `repeat_condition_correspondence_unverified` 整体阻断（repeat_condition_selection:75-78）。LLM 层旧版本回答携带该字段直接拒收（llm:152-153）。

**(2) 拼接不同 pair 事实越范围 — 无通路。** 范围原文必须逐字来自该辅助 pair 自身的 (fact_id, locator_id) 摘录：LLM 层校验子串（llm:158-159），消费层经 `quote_reasons(auxiliary_pair=member)` 完整复核记录身份/定位/属性/摘录包含及来源资格（v8:81-86、:164-167）。辅助 pair 本身被合同绑定到同一 candidate_job/frozen_input/episode/comparison 哈希（contract:57-63），证据层再绑定到已核实来源（v8:38-41）。异源文本无法通过。

**(3) 普通一次许可被自动沿用 — 无通路。** 扩展必须由原文自身声明覆盖多次（逐字范围原文+双路一致+逐次两端依据，llm:99-103），且提示明示“仅有同一签字、一般同意、一次许可或含糊后续安排不能扩展”“共用范围不替代各次许可内容核实”（llm:101-103）；单组关联永不延伸（目标组不在 assignments 内 → source_not_found → 原子 unresolved，repeat_condition_selection:79-83）；每次 target 的书面许可仍独立走 `written_permission_scoped_to_target`（该行 scope 必须 role=target_observation 且 reference 恰为本次组、verified）与决定性分支 witness（repeat_permission_calculation:6-12、:36-52）。共用范围只扩展证据的采集归属，不扩展许可语义。

**(4) 范围原文未校验/异冻结资料串用 — 无通路。** 双层校验（llm:158-159 + v8:164-167 含 pair_direct_selection 拒绝理由）；观测证据与本次 source payload 的 context/frozen/comparison 哈希全量比对（v8:32-37）；`agreed` 关联的 key 来自双路交集（receipts:63-65、:80），单路虚构关联进不了 agreed。

**(5) 旧版本 hash 改写 — 未发生。** `shared_scope_excerpt` 为 None 时序列化省略（contract:151-156），历史记录逐字节不变；辅助成员/episode_memberships 的旧版省略规则原样保留（:35、:54、:206-208）；旧回答不得补入该字段（llm:152-153）；旧上下文不得升级为 v5 重发（llm:53-54 保留旧记录）；resolution 新增 `count_scope` 块（:176-182）仅存在于新产物，presentation 以 `.get` 读取、旧档无字段即跳过（presentation:11），不补写不重算。

**(6) 代码报错/新调用未接 — 未发现。** resolution 的 count_scope 块引用的四个约束键均为 v2 输出必有（constraints:139-143）；presentation 的 kind 比较、memberships `.get` 对旧档安全（:11-14、:50-52）；消费层 `lane[key].get` 对无该键的旧 lane 答案安全，`_evidence_scope` 对旧封存观测 `.get(...) is True` → False → 多组阻断（fail-closed）；`written_permission_scoped_to_target`/`written_permission_result` 调用方签名未变；agreed key 在双路均存在，`lane[key]` 无 KeyError。方法评测批准前不得正式采用的边界由 `require_observation_method` 的 consumer/prompt/summary/路由四重绑定维持（v8:15-26）。

### 3. 缺陷结论

**未发现确证缺陷**（不凑数量）。一条 P3 级语义观察，供 Codex 裁定，不影响采用正确性：

- P3：`written_permission_result` 在底层许可**表达式为 FALSE**（如书面记录为拒绝）时，只要决定性分支含已核实书面 witness，仍输出 truth=TRUE、理由 `repeat_written_permission_verified`（repeat_permission_calculation.py:52-55）。采用安全：许可条件自身 FALSE 在 resolution:119-120/:134-136 支配 check 状态为 does_not_meet，不可能放行；但审计操作数“已确认”的标签在拒绝场景可读作“许可成立”。最小修正（可选）：`usable` 增加 `truth != TruthValue.FALSE` 门，使拒绝场景显示未核实——是否更准确取决于“核实”指内容存在还是许可成立，属产品语义决策，交 Codex。

### 4. 未验证项声明

全部为静态阅读：共用范围在真实多组方案上的端到端行为、歧义移出后 `auxiliary_pairs_without_agreed_association` 与重复归属的交互呈现、v28/v32/v14 门对旧档的实际拦截，均未经运行证实。多初查、聚合排序、多次许可的独立完整性仍未声称完成——本轮代码无越界声称；`shared_scope_excerpts` 未验证时的原始文本仅存于双路 lanes 存档（v8:174 置空、lanes 全文保留），审计链完整。
