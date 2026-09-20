# Conference Output: written-judgment-scope-20260910 - evidence_single_object

## Output

第三轮只读复审完成（未改代码/未联网/未调用模型；独立复跑合成测试 96 passed：correction-gap + expectations 投影 57、correction job + correction repository 39，与执行者宣称的 123 相容）。结论：**三项修复均在真实代码中核实成立，测试有实质断言而非摆设；行为目标（具体不确定性不蒸发、兜底可被完整证据解除）已被钉死。但按嘱挑战后确认一个残余角落：`_prior_unreconfirmed_signals` 的 `covered` 跳过是模板级的，一条无关的新具体信号可以在窄条件下掩盖旧的不可重建具体风险（下述 F1，低-中严重度）；另有一个 accepted_requirements 的低severity角落（F2）。均为窄修，不动架构。这不是临床验收；D2（判断类 PROFESSIONAL_JUDGMENT 生产者）与 R1（批注时间绑定）仍独立挂起。**

### 一、三项修复核实（证据）

**R1 全活动实体谱系（concern 1 修复，成立）。** `select_reprojection_source_runs` 现对当前权威下每条活动实体 ∪ 本次修订目标各自回溯全部祖先（`fact_expectation_gaps.py:306-320`），修订链森林良构：prepare 拒绝已修订目标（`fact_correction_service.py:525`、:1408「该记录已被修订，不能再从同一原记录分叉」），汇聚/成环仍整体拒绝。关键推论（源码推演）：同一权威内选择集是单调不减的——实体的祖先关系只增不减，运行一旦入选永不掉出，因此"重放失败"被压缩到 legacy/修复前损伤行，恰由 pad+溯源处理。孤立运行边界保持（无实体引用即排除，`test_reprojection_ignores_unrelated_orphan_run` 通过且我复核了其合法构造性说明）。跨链场景测试 `test_correction_of_unrelated_fact_keeps_other_chain_source_risk` 的断言方向正确（OCR 保留而非退化为 observation_unverified，rev 3）。

**R2 当前绑定压制（concern 3 修复，成立）。** 共享函数新增 `accepted_requirements` 覆盖参数（`fact_expectation_gaps.py:96,142-149,158`），None（原始终结）行为逐行不变；重投影传"当前未被取代的已发布事实的 supported_requirement_ids"（:449-456）。`test_rejected_candidate_risk_survives_accepted_binding_removal` 先断言终结语义下接受记录压制（observed），解除绑定后断言 ABSENT + 具体 OCR + 原门禁理由文字——正是我上轮的 T-C，断言完整。

**R3 输入信号溯源（concern 2 修复，成立）。** 合同三态 `None`（历史未知）/`[]`（明确无信号）/清单（精确输入）+ canonical 冻结 + 跨模板信号拒绝（`evidence_expectations_v2.py:145-214`）；投影器 6 个构造点全部携带同一 `input_provenance`（`evidence_expectations.py:227` 及 :235/:282/:294/:326/:349/:367），grep 证实生产代码无其他构造点绕过；仓储幂等内容含 provenance 且 `None ≠ []`（`evidence_expectation_repository.py:104-128`：可见状态相同、来源变化必须追加 revision）；legacy 行按 None 解码且读取不改写 payload/哈希（测试模拟了升级前旧行并断言哈希未变）。行为测试成对钉死：`test_concrete_absent_becoming_complete_stays_unverified`（具体缺席→覆盖补齐仍 observed_weak/未核实）与 `test_fallback_only_absence_clears_when_complete_evidence_arrives`（纯兜底缺席→完整证据到达升 observed）——两者恰好构成上轮 T-B/T-D。pad 现为不动点：pad 信号本身以非 fallback 身份冻结进 `input_gap_signals`（测试 ：644-652 显式断言），下一次修订按"不可复核的具体输入"继续保留。

### 二、挑战结果（按嘱以反例检验）

- **多个独立不确定性能否共存**：能——同模板多条具体信号全部冻结进 provenance（可见 gap_type 按合同单值呈现，属合同设计）；跨模板各自独立 pad。无缺陷。
- **无关具体信号掩盖旧风险（F1，确认存在，低-中）**：`covered` 按模板存在性跳过（`fact_expectation_gaps.py:380-384`、:392-393）。反例：先前期望携带**不可重建**的具体信号（pad 信号或 legacy None 只存在于 provenance，永不来自源运行记录）→ 之后一次新的规范化运行为同模板带来**无关的、非阻断类**具体信号（如 DESCRIPTION_INSUFFICIENT）且覆盖事实完整 → covered={T} → 不 pad → **OBSERVED**，旧"未确认风险"标记被无关信号蒸发。前置条件窄（pad/legacy 起源 + 新信号 + 完整覆盖），但方向是升级方向。最小修（无需改合同，溯源已在）：`covered` 改为按 (模板， kind) 比较——仅当先前的具体 kind 集合 ⊆ 当前重放的具体 kind 集合时才跳过；None+未决状态照旧保守。配套测试：pad 起源 + 新增无关非阻断信号 + 完整覆盖 → 断言保持 observed_weak。
- **observed_weak/PROVENANCE_FOLLOWUP 跳过（:403-407，判定无害）**：该形态不可能与阻断类（OCR/UNVERIFIED/HISTORICAL）共存——阻断类激活时 gap_type 即为阻断类；随行的只可能是非阻断具体 kind，而原始终结对"完整覆盖+非阻断信号"同样判 observed，跳过与终结语义一致。若采纳 F1 的 kind-aware 修法，此跳过被统一覆盖。
- **accepted_requirements 残余角落（F2，低）**：压制只看要求绑定、不看覆盖判定——活动事实若为 UNVERIFIABLE 强度且支持 R，会压制被拒候选信号而模板实际无覆盖（verdict none）→ 特异性退化为通用兜底（不升级）。可选小修：过滤仅计入非 UNVERIFIABLE 的活动事实。

### 三、兼容性与导出

`app/api` 无任何 expectations 暴露面（rg 无命中）；前端 `EvidenceExpectationWire` 是显式字段的瘦身 DTO（`frontend/src/api/wire.ts:196-204`，fixtures 供数），新增合同字段不会泄漏进 wire；profile 服务只消费 `coverage_fact_ids`/`expectation_id`；`contracts/` 仅存 v1 旧导出。**结论：无必需的导出更新**；将来若要向用户呈现"为何弱化"的审计视图，再在 wire 显式加 provenance 字段即可（建议但不属本轮）。

### 四、测试与边界

- 我复跑：`test_fact_correction_gap_reprojection.py`（11 测试，含 4 条新增行为测试，断言体逐条读过）+ `test_evidence_expectations.py`（含 4 条 provenance 合同/仓储测试，legacy 模拟真实）+ correction job/repository 39 通过。执行者宣称 123，owner 复跑中——与我局部结果一致。
- 建议补充（若采纳 F1/F2）：F1 的 kind-aware 回归（上述反例）、F2 的 unverifiable 事实压制反例；另建议补一条"pad 起源期望跨权威换新后不 pad（prior.authority != authority 跳过）"的守门测试——现有代码 ：399 已跳过，但无测试钉住。
- 声明：本轮全部结论为源码直读 + 合成测试复跑；F1/F2 为确定性推演反例、未新建用例实证（无写权限）。同厂商复审独立性受限；非临床/用户验收；D2/R1 未并入本轮结论。
