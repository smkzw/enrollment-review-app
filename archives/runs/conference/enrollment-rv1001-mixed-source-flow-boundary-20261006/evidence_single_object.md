收到。作为 `evidence_single_object` 角色执行一次有界只读工程审查。先读会议上下文包与 Codex 计划文件。

上下文包与计划已读（2 次 orientation read）。现在进入有界材料读取。先获取三个核心模块的函数轮廓。

材料检索已用 3 次。现在读取固定流程入口与编译器判定/组装函数。

关键耦合已定位在 `supports_front_stage_flow`（全批布尔门）与 `prepare_front_stage_flow` 的整批 raise。继续读取来源解释侧的既有逐点契约。

继续读取逐点校验契约与去构造器运行分支。

读取去构造器运行分支与消费者位置。

核心耦合已确认（deconstructor:7020-7023 的门 + fixed_flow:246/257/282 的整批 raise）。继续读取覆盖账、插入合并与执行层保存消费者。

执行层消费者门禁是最终耦合点。读取该验证块并列出来源测试文件。

最后两个有界动作：确认保存草稿验证器的调用点，以及固定流程现有测试场景。

# Conference Output: enrollment-rv1001-mixed-source-flow-boundary-20261006 - evidence_single_object

## Output

### 0. 结论摘要（先给裁定）

**建议：采用候选 A 的最小化版本，但必须同时改 3 处，缺一处则进展不可持久化。** 候选 B 依现有证据应裁定为"现有契约不支持"；候选 C 仅在没有 A 的落点时保留。核心裁定如下（详述见 §3/§4）：

1. **最早决定性耦合**：`app/agents/protocol_control_deconstructor.py:7020-7023` 的实时入口用**全批布尔** `supports_front_stage_flow(batch, interpretation)` 决定是否进入固定流程；混合批次（25 条中仅 7/8 可简单装配）在此返回 False，**根本不调用任何逐项流程**，直接落到 `7077` 之后的整 wire 基线 author 提示。这就是"退回整wire"的机制本体。
2. 只补 `protocol_control_fixed_flow.py` 不够：`app/services/protocol_control_execution.py:2552-2651` 的 `_validate_saved_source_review` 会在保存/恢复/校验四处（`:2416`、`:2788`、`:3184`、`:3655`）**拒绝**含保留决定的固定流程结果，使"推进"在第一次落盘后被销毁。
3. `covered_front_wire` 的**全 items 前置条件**（`fixed_flow.py:172-176`）+ `:219-222` 的 `FLOW_TARGET_COVERAGE_UNASSEMBLED` 会因一个非 additional 的保留点（`unresolved`/`not_current_control`/`cited_external_rationale`/`potential_same_requirement`）中止整批装配，这是第二个"整批退回"点。

---

### 1. 最早决定性耦合（函数级证据）

**实时路径（关键）**：`protocol_control_deconstructor.py:7020-7023`

```python
if (workflow_variant == FIXED_FLOW and raw_text is None
        and source_interpretation is not None and output_validator is not None
        and supports_front_stage_flow(batch, source_interpretation)):   # ← 全批门
    workflow_path_executed = "front_stage_flow"
    prepared = prepare_front_stage_flow(...)
```

- `supports_front_stage_flow`（`protocol_control_fixed_flow.py:98-129`）在 `:108-120` 要求**每一条**陈述要么是纯背景（`decision_functions == ["background"]`、force ∈ {descriptive, unclear}、无 unresolved），要么是单访视动作且 `can_compile_stage_bound_source(...)` 为真（`:117`）。25 条混合批次在第一条定义/多期/资格判定后动作处即失败。
- 因此混合批次**跳过整个 `prepare_front_stage_flow`**（`:7025-7076`），也跳过其"混合单元保留逐点证明"分支（`:276-331`），并把整批交给整 wire 模型路径（`:7083` 起）。注意：`prepare_front_stage_flow` 失败时会 `return build_result(status="需要核对", ...)`（`:7056-7065`），**不是**退整 wire；退整 wire 只发生在 `:7020-7023` 的门为 False 时。二者必须区分。

**第二层（防御性重复门）**：`fixed_flow.py:246-247` 在 `prepare_front_stage_flow` 内重复同一全批门；`:257-260` 只要**任何一条** review 决定不在 {additional_requirement, covered_by_official, covered_by_procedure, background_context} 就整批 `FLOW_SOURCE_SCOPE_UNRESOLVED`；`:282-287` 只要**任何一条** additional 项不满足 `can_compile_stage_bound_requirement` 就整批放弃装配。三处都是"单点阻塞全批"。

**批量级装配前置**：`covered_front_wire`（`fixed_flow.py:167-233`）
- `:172-176`：`len(review.items) != len(interpretation.statements)` 即拒绝（全 items 义务）；
- `:214-218`：混合 additional 单元 → 保留 `pending_front_wire` 的 `OTHER_CONTROL_CANDIDATE`；
- `:219-222`：`kinds` 里出现 `unresolved`/`not_current_control` 等 → `FLOW_TARGET_COVERAGE_UNASSEMBLED` 整批 raise。

**现有逐点能力已经齐备（这是"最小方案"成立的前提）**：
- 逐点决定集本身已完整：`SourceTargetReviewItem.decision`（`source_interpretation.py:623-640`）包含全部 8 种决定；`validate_source_target_review`（`:1327-1658`）逐决定校验到原文/时间/例外/对象/归因级别；
- 逐点恢复已有原语：`validated_source_review_seed`（`:1661-1695`）"retain individually current decisions for recovery, never final adoption"，且 `SourceTargetReviewValidationError.retry_class = "single_statement"`（`:1290`）；
- 逐点能力判定已有：`can_compile_stage_bound_source/requirement`（`stage_compiler.py:224-277`）、`can_compile_shared_prohibition_requirement`（`:150-171`）；能力缺口有类型化载体 `StageBoundCompilationGap`（`:112-114`）与 `SourceTemporalScopeUnresolved`（`source_interpretation.py:1294-1325`，其 docstring 明确"not evidence of missing clinical data"）；
- 逐点编译+检查式推进已有：`compile_source_requirement_response`（`stage_compiler.py:808-829`）、`assemble_source_requirement_inserts`（`:832-857`，含逐项 `expressed` 校验）；
- 混合单元装配已有：`allow_additional_units=True` + pending disposition + `_merge_source_candidate_insert` 的授权单元限定（`deconstructor.py:5790-5871`，`:5832-5836` 超授权单元拒绝、`:5850-5856` 只改授权单元处置）。

**结论（证据+推断）**：现有代码其实已经实现了"混合批次逐点推进"所需的 90% 机制，唯独入口门、review 后闭合门、装配前置三处按"全批"编写，导致机制不可达。这是纯软件耦合，不是来源或标准问题。

---

### 2. 必须连通的现有 producer / save / consumer 链

| 环节 | 现有位置 | 必须做什么 |
|---|---|---|
| producer | `fixed_flow.prepare_front_stage_flow`（:236-331） | 接收混合批次；对可装配子集走既有 typed builders；对保留点产出**类型化保留清单**（不写入 review 本体） |
| 装配 | `fixed_flow.covered_front_wire`（:167-233） | 新增 `retained_indexes` 形参；保留点所在单元一律 pending，不得整段链接 |
| 保存 | `deconstructor.build_result`（:6664-6740）→ 字段 `partial_wire` / `source_front_target_review` / `source_statement_coverage`（序列化于 `protocol_control_execution.py:3271-3299`） | 增加一个可选字段保存保留清单（或复用 coverage 的 free-form `disposition` + `attempts[].error_detail`，见 §8-Q1） |
| 消费/校验 | `protocol_control_execution._validate_saved_source_review`（:2552-2651） | 逐点期望状态映射（`:2594-2601`）与两处重推导（`:2590`、`:2619`）必须用同一 `retained_indexes`；**最终采用路径保持零保留点** |
| 恢复 | `deconstructor.py:6628-6653`（seed）+ `execution.py:3117-3169`（resume 传入） | 见 O3：固定流程分支目前**不消费** `resumed_review_items` |

调用点证据（`_validate_saved_source_review`）：`execution.py:2416`、`:2788`、`:3184`（resume）、`:3655`（批量校验）。四处都要求"决定集 ⊂ 4 类"（`:2576-2578`）且"无 unresolved"（`:2650-2651`）——即当前**保存态只接受完全成功**。

另注：`deconstructor.py:6745-6746` 明确禁止 `FIXED_FLOW` 从 `partial_wire` 直接恢复（`FLOW_RESUME_PROOF_REQUIRED`）。因此持久化推进必须走 **review seed** 通道，而不是 wire 通道——这与既有设计意图一致，方案不得要求放开该禁令（也不得授予任意父级修订权限）。

---

### 3. 最小可行方案（函数级，不新增框架、不降标准）

**P0（纯重构，无行为变化）**：把 `fixed_flow.py:108-120` 的逐条谓词原样抽成 `front_stage_supported_indexes(batch, interpretation) -> set[int]`；`supports_front_stage_flow` 改为 `len(supported) == len(statements)` + 原 `:121-129` 的覆盖范围条件。语义零变化，供混合路径复用；`can_compile_stage_bound_source` 的既有判定一行不改。

**P1（入口与装配）**：`prepare_front_stage_flow` 增加 `retain_unassemblable: bool = False`（或等价的新兄弟函数，二选一由 Codex 定，偏好加形参以最小化 diff）。准入条件改为：
- 保持 `validate_source_interpretation`；
- **保持** `set(target_review_indexes(...)) == set(range(len(statements)))` 与 `:124-126` 的 exact-match 排除（这条不放松：已逐字命中的点仍走既有比对路径，改它才是降标准）；
- 新增：`front_stage_supported_indexes` 非空即可进入（不必全批可编译）。
review 调用、`validate_source_target_review` 校验**完全不变**（单次 review 仍覆盖全 scope）。之后按既有判定把 items 分区：
- `assemblable_additional` = decision == additional_requirement 且 `can_compile_stage_bound_requirement` 或 `can_compile_shared_prohibition_requirement` 为真；
- `retained` = 其余非 {covered_by_official, covered_by_procedure, background_context} 的项（含 `unresolved`、`not_current_control`、`potential_same_requirement`、`cited_external_rationale`、以及不可编译的 additional）。
`retained` 为空 → 走今日既有路径（回归零风险）。非空 → `covered_front_wire(..., allow_additional_units=True, retained_indexes=...)` 取 pending；仅对 `assemblable_additional` 逐项 author（既有 prompt）→ `compile_source_requirement_response` 逐项检查 → `assemble_source_requirement_inserts`（仅该子集，`:855` 的逐项 expressed 校验自动只作用子集）→ candidate alignment 仅对子集 pairs（`:306-310`）。若 `assemblable_additional` 为空，跳过 author/assembly，直接 `output_validator(hydrate(pending))`（镜像 `:264-272`）。`FrontStageFlowResult` 新增 `retained: list[...]`（含 statement_index、原 review decision、`capability_code` 或 `review_reason`、source_refs）。**review 对象逐字保留，不写 `unresolved`、不写 `unresolved_aspects`**。

**P2（装配前置）**：`covered_front_wire(..., retained_indexes: frozenset[int] = frozenset())`。单元循环中，若该单元含保留点 → 直接 append `pending_dispositions[unit_id]` 并 `continue`（置于 `:214` 之前）。默认空集时行为逐字节不变。必要性证据：保留点为非 additional 时，现有 `:219-222` 的 `kinds` 会把 `unresolved` 计入并整批 raise；保留点与 covered 共存时同样 raise——不放行就无法产生任何部分装配。

**P3（保存/消费连接）**：`execution._validate_saved_source_review`
- `:2590` 与 `:2619` 重推导时传入同一 `retained_indexes`（来源：新保存字段或 coverage 载体）；
- `:2594-2601` 期望状态：保留 index 不期望 `"expressed"`；按单元处置映射为 `candidate_linked`（pending 单元）/`linked_only`/`not_located`；并保留 `:2604-2616` 的"pending 单元不得携带任何链接"的既有保证（该保证正是"不借整段链接"的消费者）；
- **最终采用（final_output 存在）仍要求保留集为空**，即"完整闭环"标准不变；只有草稿保存/恢复接受部分推进。

**P4（运行分支）**：`deconstructor.py:7020-7023` 的门改为 P0 的准入谓词；`supports_front_stage_flow` 为 False 但准入为真时，以 `retain_unassemblable=True` 调 `prepare_front_stage_flow`，并把 `retained` 存入 result。仅当准入为假（review scope 不完整或全 exact-match）才保留整 wire 基线回落——那是合法的旧路径，不是本次要消除的耦合。

---

### 4. 候选 A / B / C 裁定

- **A（先短 target review，再 typed builders，不支持的显式保留）**：**推荐**。证据充分（§1 逐点机制已存在），最小改动为 P0-P4，仍是一次 review、按需 author，无新框架。
- **B（按独立 owned 单元拆分，保留依赖与聚合闭环）**：**依现有证据建议裁定"现有契约不支持"**。理由：`source_statement_coverage` 与 `target_review_indexes` 都是**批级全局索引**（`deconstructor.py:4333`、`source_interpretation.py:1054-1088`），`validate_source_target_review:1333-1338` 要求 review scope 与全局 `target_review_indexes` **完全相等**；拆单元会产生"无全局重组合消费者"的空洞。数据包提到的"existing plan"分割器我在声明的读取范围内**未能验证存在**（见 §8-Q2），若 Codex 能指出具体函数，B 才重新进入比较。
- **C（维持基线）**：仅在 A 的保存/消费无法在本轮接通时保留。注意 C 对既定目标**严格更差**：门为 False 时连 review 都不会发起（`:7020-7023`），不产生任何逐点进展或 seed。若只能做一件事，优先级应是"保存已验证 review 供 resume 复用"而非维持整 wire 全量重读。

---

### 5. 测试要求（normal / counterfactual / unknown–failure recovery）

**重要：声明的测试路径不存在。** `tests/v2/agents/test_protocol_control_fixed_flow.py` 在冻结 HEAD 上 `ENOENT`（第 22 个动作失败），且 `tests/v2/agents/*.py` 目录清单中也没有 `test_protocol_control_fixed_flow*`、`test_protocol_control_stage_compiler*`、`test_protocol_control_source_interpretation*` 等同名文件。按数据包"Stop if a path is absent; no raw artifact search"，我**停止搜索**并如实上报：现有合成夹具的写法与场景覆盖**不可得**，下文的测试应在 Codex 定位到的真实测试归属处落地（可能在其他目录或不同命名，超出我的读取范围）。

- **normal（混合批次推进）**：3 条合成陈述 = {1 条 covered_by_official, 1 条可编译 additional_requirement, 1 条定义/多期（不可编译）}。断言：review 只调 1 次；author 只调 1 次（可编译项）；wire 中混合单元为 `OTHER_CONTROL_CANDIDATE` 且无任何链接；保留清单含定义项且其 `capability_code` 来自 `can_compile_*` 失败而非 review 改写；保存态可通过 `_validate_saved_source_review`（草稿路径）；**不产生 final_output**。
- **counterfactual A（全可编译）**：与今日 `supports_front_stage_flow` 路径产物**逐字节一致**（证明 P0-P2 默认参数无行为漂移）。
- **counterfactual B（零可装配）**：全部为保留点。断言：不伪造 author、不产生链接、不把任何点改写为 `unresolved`；决策点 Q3（是否仍回落整 wire 基线）按 Codex 裁定断言。
- **counterfactual C（unit 内 covered + retained 共存）**：断言该单元停在 pending、无链接（回归 `:219-222` 与 `execution:2604-2616` 的既有保证）。
- **unknown/failure recovery**：第 2 个 author 传输失败 → 第 1 项编译结果与 review 均可保存；以 `resume_source_target_review` 恢复时**不再重问 reviewer**（覆盖 O3 修复前后行为）；`FIXED_FLOW + partial_wire` 仍拒绝直接恢复（`:6745-6746` 不变）；错误码仍经 `_failure_code`/`attempts` 记录，不吞错。
- **守卫断言**：`retained` 里的 statement_index 必须仍在 `target_review_indexes(interpretation, pending_coverage)` 内（防止用"保留"掩盖已达 expressed 的点）。

---

### 6. 三类原因必须分离（且各自可持久化）

| 类别 | 载体（复用现有） | 禁止 |
|---|---|---|
| 软件能力缺口 | `can_compile_stage_bound_source/requirement`、`can_compile_shared_prohibition_requirement` 为 False；`StageBoundCompilationGap`；`SourceTemporalScopeUnresolved`（code=`TEMPORAL_SCOPE_UNRESOLVED`） | 不得改写为 review 的 `unresolved`；不得写成"研究者缺资料" |
| 真实来源未决 | review 的 `unresolved` + `unresolved_aspects`（由 reviewer 声明，`validate_source_target_review` 校验） | 不得由编译器失败伪造；不得由软件缺失反推 |
| 读取未完成/传输 | `_failure_code`、`attempts[].outcome`（transport_failed / schema_invalid / publication_invalid） | 不得并入来源未决 |

同时：保留点不得从批次移除（无删除、无 `units_without_statement` 变更）；定义语句及其 `SourceDefinitionConsumers` 声明原样保留（`validate_source_definition_consumers`、`require_frozen_official_predicate_identities` 是独立消费者，前端流程从未触碰，也不得由部分 wire 采用）；合并仍走 `authorized_unit_ids=owned` 的受限插入（`:5832-5836`），不得放开父级修订。

---

### 7. 我主动发现的高影响缺陷、反例与反对意见

- **O1（最高影响，必须同轮修复）**：只改 `fixed_flow` + `deconstructor` 门是**表面修复**。`_validate_saved_source_review` 在 `:2576-2578`/`:2650-2651` 拒绝保留决定，且有 4 个调用点（含 resume `:3184`）。不改它，"推进"第一次落盘即被销毁。**反例**：混合批推进出 2 条候选 → 保存 → 重新载入 → 校验抛"前置新增要求核对不能借已有覆盖或未决通过采用" → 进度归零且已花掉的模型调用不可追回。
- **O2（装配契约缺口）**：`covered_front_wire:172-176` 的全 items 前置与保留点排除相冲突。若不新增 `retained_indexes` 形参而改用"过滤 review 子集"，必然触发 `validate_source_target_review:1333-1338` 的 `REVIEW_SCOPE_INVALID`（scope 必须等于全局 required 集）。**结论**：P2 是必要条件，不是可选优化。
- **O3（恢复链断点）**：`deconstructor:7020-7076` 的固定流程分支只使用 `prepared.responses/review`，**完全不消费** `resumed_review_items`（`:6646-6649` 构建的已验证 seed）。后果：每一轮"推进 2/25"都要重新支付一次 25 点 review。**最小修复**：给 `prepare_front_stage_flow` 增加可选 `resume_review` 形参，入参先经 `validated_source_review_seed(batch, interpretation, coverage, saved)` 过滤，仅对 `review_scope − kept` 调用 transport；若 `kept` 已覆盖全部 scope 则零 review 调用。这复用现有恢复原语，不新增机制。
- **O4（整批退回的第二种形态）**：即便修好入口门，`:257-260` 的 review 后闭合门与 `:282-287` 的 compile-all 门仍会把"一点未决"放大为"整批失败"。这两处是 P1 必须触碰的核心，不能只改 `:7020-7023`。
- **O5（对"不降标准"的挑战）**：有一种更省事的写法是"对不可编译 additional 直接判 `unresolved` 交给研究者"——这**同时违反**两条红线（伪造来源未决、把能力缺口转成研究者缺资料），必须在评审中明确排除；另有"允许部分 wire 直接进入最终采用"的写法，会让未闭环批次获得发布资格，同样排除。P3 的"最终采用要求保留集为空"是这条红线的执行点。

---

### 8. 决策点与给 Codex 的有界问题

- **Q1（决定补丁形态）**：本轮是否允许给运行结果/保存草稿增加**一个可选字段**（保留清单 + 类型化原因码）？若不允许 schema 增量，安全暂定路径是：把逐点保留原因写入已持久化的 `SourceStatementCoverage.disposition`（free-form string，`source_interpretation.py:500`）与 `attempts[].error_detail`，不新增字段——但需确认 `source_statement_coverage`（`deconstructor.py:4333` 起）的 `disposition` 组装允许该取值（我只读了该函数前段 140 行，未读完，属已知不确定性）。
- **Q2（决定 B 是否重开）**：数据包提到的"existing plan"是否有可复用的**独立单元分割器**函数（具体模块/函数名）？没有则建议按 §4 裁定 B 不成立。
- **Q3（临床/产品政策，非技术）**：当混合批次**零可装配点**时，是保留今日"回落整 wire 基线"（多付一次全批模型调用，但走既有发布路径），还是返回 `需要核对` + 已验证 review seed（省一次调用，但本轮无法签发）？我倾向后者 + 显式 `error_code`，但这属于 Codex 保留的临床/产品裁定范围。
- **Q4（消费者归属）**：`_validate_saved_source_review` 的 4 个调用点中，哪些属于"最终采用"、哪些属于"草稿持久化/恢复"？P3 的放宽只能作用于后者；我只核对了函数体与调用行号，未逐一读取各调用点上下文（预算上限）。

---

### 9. 证据轨迹、读取范围与不确定性

**已执行动作：材料读/搜 22/22（用满，无超支；第 22 个动作因路径不存在报错，计入额度）；orientation 2/2。** 实际读取（节选关键）：

- `context/enrollment-rv1001-mixed-source-flow-boundary-20261006_conference_context.md`（全文）
- `plans/codex_main_venue_enrollment-rv1001-mixed-source-flow-boundary-20261006.md`（全文，内容为 TODO 骨架，无额外设计约束）
- `app/agents/protocol_control_fixed_flow.py:51-350`（三个完整定义所在区段）
- `app/agents/protocol_control_stage_compiler.py:112-331, 800-929`
- `app/agents/protocol_control_source_interpretation.py:155-204, 497-566, 623-702, 1054-1113, 1280-1659, 1661-1930`
- `app/agents/protocol_control_deconstructor.py:6618-7082, 4333-4472, 5790-5929` + 函数定义索引
- `app/services/protocol_control_execution.py:2480-2709` + 匹配定位（未整读）
- `app/domain/contracts/protocol_controls.py`（枚举/类名定位）
- `tests/v2/agents/*.py` 目录清单

**未读/不可得（如实上报）**：
- `tests/v2/agents/test_protocol_control_fixed_flow.py` **不存在**（ENOENT）；同目录无同名族测试。既有夹具与测试场景覆盖未验证，测试落地位置需 Codex 指定。
- `source_statement_coverage`（`deconstructor.py:4333` 起）完整函数体未读完（预算上限），`disposition` 字段的完整取值语义未验证。
- `protocol_control_execution.py` 保存/恢复路径（`:3011`、`:3117-3169`、`:3271-3299`）仅经 grep 定位，未整读；`_validate_saved_source_review` 四个调用点的上下文未逐一读取。
- "existing plan"（独立单元分割器）未在读取范围内找到，未做范围外搜索。
- 未读：临床原件、数据库、.env、日志、`/Users/smkzw/tmp`、web；未运行测试、未修改任何源码，未写入 runner 管理的报告路径。

**确定性分级**：§1 的函数级耦合为**直接观察**（代码行号可复核）；§3 的 P0-P2 为**基于现有契约的工程建议**；P3 的具体放宽点、O3 的修复形参、Q1 的字段方案为**推断，需 Codex 复核调用点上下文**；Q3 为政策问题。全部结论为顾问意见，**不构成 Codex 或临床的最终验收**；`response_format`、传输失败分类与 UI/浏览器验收均不在本 pass 范围内。
