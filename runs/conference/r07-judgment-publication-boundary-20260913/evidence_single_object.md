I'll start with the assigned conference context and plan, then audit the judgment/publication-boundary evidence without writing files.I'll audit the listed source files and related judgment contracts next, focusing on unverified vs confirmed-missing boundaries.The first pass shows a split between `missing` and `unverified` reasons. I’ll read the evaluator, contracts, and judgment-search producers next.The evaluator already maps unmatched judgment to `unverified`. I’ll read producers, UAT coverage, and the design-doc recovery path next.Frozen fixtures still encode `professional_judgment_missing`. I’ll compare that with the live generator and the four remaining artifact tests.Coverage promotion looks too strong relative to the search contract. I’ll inspect the failing artifact tests and the publication path next.The four artifact failures look like live-evaluator drift, not simple stale JSON. I’ll pull the exact failure text and the coverage-signal contract.I'll confirm the unpublishable confirmed-missing signal and whether the two consumers use the same applicability rule.# Conference Output: r07-judgment-publication-boundary-20260913 - evidence_single_object

## Output

只读审阅。未改源码、未写报告文件、未读生产库/原件/凭据。不宣称临床、监管、视觉或当前 Web 终局。

### 最高影响缺陷

`fact_expectation_gaps.py` 把「双读完整、供给页零候选」写成 `CoverageGapSignal(kind=PROFESSIONAL_JUDGMENT, fallback_only=True)`。该对象**当前无法构造**，因此已确认缺失进不了正式期望合同。

本会话直接实例化：

| 构造 | 结果 |
|---|---|
| `CoverageGapSignal(fallback_only=True, kind=PROFESSIONAL_JUDGMENT)` | 拒绝：「仅未核实或记录不全的默认提示可在完整证据到位后撤去」 |
| `CoverageGapSignal(fallback_only=False, kind=PROFESSIONAL_JUDGMENT)` | 接受 |
| v1 `EvidenceExpectation(ABSENT, PROFESSIONAL_JUDGMENT)` | 拒绝：「未观察到的到期证据必须使用具体当前缺口」 |

前一设计会商已要求发射 `fallback_only=False`。现码用了 `True`。这不是测试夹具过期，而是正式生产者与合同互相否决。在此修复前刷新 `subject-*.json` / UAT JSON，只会把「无事实=缺失」改写成「无事实=未核实」，并弄丢 UAT 对 `professional_judgment` 的覆盖，**不会**补上已确认缺失路径。

### Evidence（观察）

1. **用户边界（会议上下文）**：缺失判断只能在完整有效来源审阅后报告；仅无事实=未核实；两读未见所需判断不要求用户再确认；不得为绿测试放宽采信。

2. **设计 §17.2 四态**：未完成核对 / 已找到待核实 / 本次资料未见所需记录→`professional_judgment`+研究者补充、继续、不暂停 / 已核实对应判断进入评估。`source_scope_verified` 与 `professional_judgment_absence_proven` 在检索合同上恒为 `False`，守卫的是「研究者从未在任何地方写过」而非「本次供给域未见」。

3. **求值器已改（`app/domain/expression.py:460-466`）**：`requires_professional_judgment` 且无匹配事实 → `professional_judgment_unverified`，不再 `professional_judgment_missing`。

4. **门控映射仍双轨（`assessment.py:195-198, 286-293`）**：
   - `professional_judgment_unverified` → `OBSERVATION_UNVERIFIED` → `INDETERMINATE`
   - `professional_judgment_missing` → `PROFESSIONAL_JUDGMENT` → `ComponentDecision.PROFESSIONAL_JUDGMENT`
   现场求值器已不发出 `missing`；该 reason 只存在于冻结 JSON 与历史映射。

5. **v1 期望不能携带 `PROFESSIONAL_JUDGMENT`**（`evidence.py:123-130`）。v2 `_ABSENT_GAP_TYPES` 可以（`evidence_expectations_v2.py:43-52`）。实时投影用 `EvidenceExpectation.model_construct` 把 v2 `gap_type` 送进 `derive_gate_gap_types`，绕过 v1 校验。这是运行时桥，不是批准放宽 v1 schema。

6. **冻结夹具 vs 内存生成（本会话复跑）**
   - 冻结 `contracts/v1/fixtures/*.json` 仍写 `professional_judgment_missing`；`subject-gap_conflict.json` 仍有 `proposed_decision=professional_judgment`、`gap_types=["professional_judgment"]`。
   - 内存 `build_fixture("clear"|"barrier"|"gap_conflict")` 均成功；观察 reason 已是 `professional_judgment_unverified`。
   - `gap_conflict` 的专业判断候选现为 `INDETERMINATE` + `DESCRIPTION_INSUFFICIENT` + `OBSERVATION_UNVERIFIED`；动作是 `observation_unverified`，无 `professional_judgment`。
   - `build_uat_workspace()` 失败：`UAT 工作区未覆盖全部核心缺口类型`（`uat.py:246-259` 仍强制 `GapType.PROFESSIONAL_JUDGMENT`）。
   - 冻结文件未被覆盖。符合「三场景内存可建、UAT 覆盖失败、JSON 未刷新」。

7. **四项合同工件失败不是单纯哈希过期**（`full-suite-20260913-binding-v6.xml`）：
   - `test_fixture_references_are_internally_consistent`
   - `test_fixture_rollups_match_scenario_semantics`
   - `test_uat_workspace_has_executable_multistage_coverage`
   - `test_fixture_scope_rejects_profile_event_span_outside_linked_facts`
   共同原因：`validate_assessment_candidate` 要求每条谓词观察的 `reason_codes` 与**当前**求值器逐字相等。冻结观察仍是 `professional_judgment_missing`，现场是 `professional_judgment_unverified`。失败出现在 `candidate-clear-ex` / `candidate-barrier-ex` / UAT screening-clear，不只 `gap_conflict`。即：未参与触发短接的判断谓词（如 `exception_confirmed`）也会让「明确符合/排除」夹具在重发布时失败。

8. **两套消费者、三套适用性**
   - 检索作业选择：`determine_component_mode == INVESTIGATOR_JUDGMENT`（任一 `requires_professional_judgment`）。
   - 期望缺口生产者：只认 `required_source_types` 含 `investigator_assessment`。
   - 实时投影 `_summary_gaps`：mode **或** source type。
   §17.2 要求单一适用性；09-13 附注又警告 `requires_professional_judgment` 目前混有「模型需懂语义 / 诊断评分已是专业评估 / 方案明确要求研究者书面判断」。消费者拉齐 ≠ 上游标注正确。

9. **已确认缺失生产者无整链测试**。`ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE` 的测试停在 coverage 摘要和 `_summary_gaps` 单测；没有测试真正构造 `fact_expectation_gaps` 的 `PROFESSIONAL_JUDGMENT` 信号。该路径若被调用，会在 `CoverageGapSignal` 校验处炸掉，而不是发出正式缺口。

10. **动作文案互斥**：`OBSERVATION_UNVERIFIED` 要求 CRA「核实前不要求补写研究者判断」；`PROFESSIONAL_JUDGMENT` 要求研究者「作出并记录明确临床判断」。若求值器的未核实与检索的已确认缺失被并入同一组件，会同时发出两条相反行动。

11. **文案错配**：`_reason()` 在 `gap==PROFESSIONAL_JUDGMENT` 且 summaries 缺 requirement 时，输出「不能据此认定缺少研究者判断」。那是未核实措辞，挂在已确认缺失缺口上。

12. **PROJECT_CONTEXT**：正式 `ReviewRun/FinalAssessment/ActionRequest` 均为 0。冻结 JSON 是合同样例史，不是受试者临床史。仍不得为绿测试改写这些样例所编码的采信规则。

### Inference（推论）

现场求值器「无事实→未核实」是对的，且必须保留。错误在于把这一改动当成已确认缺失的替代：生成器把 `gap_conflict` 改成未核实，UAT 因此失去 `professional_judgment`，压力会转向放宽 v1 `ABSENT` 或从 UAT 必选缺口里删掉它。这两条都是被否决的捷径。

已确认缺失的合法入口已经存在，只是没接上：

- 检索覆盖态 `ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE`（描述供给域，不证明宇宙完备）
- v2 `CoverageGapSignal(PROFESSIONAL_JUDGMENT, fallback_only=False)`
- v2 期望 `ABSENT + professional_judgment`
- 经 `model_construct` 视图进入 `derive_gate_gap_types` / `derive_component_decision`

求值器不应再从缺事实推出 `professional_judgment_missing`。`REASON_GAPS` 里保留旧 reason 只服务于**已发布**历史回放，不能当现场生产者。

四项失败证明：门控重发布用的是当前求值器，不是冻结观察快照。在正式已确认缺失路径存在之前刷新 JSON，会：

- 把 clear/barrier 的旁路判断 reason 改成 unverified（语义上对，但会掩盖「缺搜索覆盖仍报缺失」这个旧错误）
- 把 gap_conflict 的专业判断样例改成未核实，UAT 必选 `PROFESSIONAL_JUDGMENT` 继续失败
- 诱使下一步删 UAT 要求或放宽 v1 schema

因此：**现在刷新夹具不合适。** 失败应保持为阻断，直到有一条带合成检索覆盖的正式路径能重新发出 `professional_judgment`。

实时工作台经 `_summary_gaps` 已能在无期望信号时画出 `PROFESSIONAL_JUDGMENT`。正式审核门控做不到。§17.2「唯一可复用服务」尚未成立。

### Recommendation（建议，非实施）

**不要做**：刷新冻结 JSON；放宽 v1 `ABSENT` 允许 `PROFESSIONAL_JUDGMENT`；从 UAT `required_gaps` 删除 `PROFESSIONAL_JUDGMENT` 来绿测试；把 `professional_judgment_unverified` 与 `professional_judgment_missing` 在观察比较里视为相等；把 `source_scope_verified` 改成 True；用「无事实」或「两读未见」在求值器里直接变缺失。

**最小正式路径（复用已有合同，按序）：**

1. **生产者合法化**：`ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE` 且 C4' 无 `referenced_file_missing` 时，发 `CoverageGapSignal(kind=PROFESSIONAL_JUDGMENT, fallback_only=False, applies_to_template_id=…)`。detail 必须带「本次提交的资料中」以及 `scope_sha256` / 双读身份。`fallback_only=True` 只留给未核实/记录不全默认项。候选/不完整覆盖继续只发 `OBSERVATION_UNVERIFIED`。
2. **同一组件互斥**：已确认缺失成立时，抑制同源判断谓词上的 `professional_judgment_unverified`，避免 CRA「先别让研究者写」与研究者「请补写判断」并出。缺文件优先于 P2（已有 v2 优先级）。
3. **适用性（本边界的安全默认）**：只对**实际执行过的判断检索目标**评 P2，不在缺口生产者里新推 `determine_component_mode` 或 source_type。检索选了但覆盖未闭合 → 未核实；没检索 → 未核实。把「诊断/评分是否真要书面判断」留给 §17.2 上游隔离审阅，不在本修复改已发布布尔。
4. **评估门控消费 v2 期望**，不改 v1 schema。`derive_gate_gap_types` 已会并入 `expectation.gap_type`；`PROFESSIONAL_JUDGMENT ∈ gaps` 时决策已是 `professional_judgment`。求值器缺事实分支保持 unverified。
5. **合成已确认缺失夹具**（新路径，不是改 clear/barrier 语义）：冻结检索范围 + 两读全页 `not_found` + 无缺文件信号 → v2 `ABSENT/PROFESSIONAL_JUDGMENT` → 评估 `professional_judgment` → 单条研究者行动。用它恢复 UAT/生成器覆盖。在此之前不要 `write_json` 覆盖现有 fixture。
6. **测试顺序**：先生产者校验拒绝 `fallback_only=True`+PJ、接受 `False`；再 C1–C6 合成矩阵（干净缺失 / unreadable / found / ambiguous / 缺文件 / 目标漂移 / 无检索）；再门控发布；最后才重生夹具。历史 JSON 的 schema/pydantic 校验可继续；活门控重发布在重生前应视为已知不匹配，而不是改观察字符串去凑绿。
7. **历史 reason**：保留 `REASON_GAPS["professional_judgment_missing"]` 供旧候选回放。现场不得再发出。PROJECT_CONTEXT 称正式评估为 0，无受试者评估史可改写；合同样例仍等第 5 步后再重生。
8. **未接线、本轮不要假装完成**：已核实书面判断解除无法判定（§17.2 第四态）；`_reason()` 在 PJ 缺口上误用未核实措辞；检索选择过宽与缺口生产者过窄的上游语义。

### Uncertainty（不确定）

- 未跑全量套件；四失败与 4859/14/9 以 `full-suite-20260913-binding-v6.xml` 及本会话内存复现为据。另 10 项失败属 PAGE_COVERAGE / 预算 / 传输，不在本边界。
- 未验证 `fact_expectation_gaps` 判断分支是否已有运行时调用方；无整链测试，可能是死路径。无论死活，对象都不可发布。
- 未读真实检索回执。隔离库历史摘要「12 候选、2 未完成、无整页零候选」来自 PROJECT_CONTEXT，本角色未打开 DB。
- 分组目标下「无关通道不可读是否阻断本要求」仍是 2026-09-10 会商未决项。
- `requires_professional_judgment` 的三种上游含义未做方案原文对照；本修复不得按条款号或疾病名改布尔。

### 对现方案的异议

把生成器改成 `indeterminate + observation_unverified` 作为「最小调整」方向对，**作为 UAT/夹具的终态不对**。它把唯一会发出 `professional_judgment` 的合成故事拆掉了，却没有补上搜索覆盖故事。

实时 `_summary_gaps` 在摘要状态上直接画 `PROFESSIONAL_JUDGMENT`，不经 v2 信号。这会让工作台与正式审核分叉，也绕过 `fallback_only=False` 与缺文件互斥。投影应消费已发布期望，而不是第二套状态机。

`_expectation_views` 的 `model_construct` 是必要的 v2→v1 视图，但不能反过来当成「v1 也可以 ABSENT+PJ」的理由。

### Codex 决策点

1. **夹具重生时机**：建议等合成搜索覆盖路径能合法发出 PJ 之后。立即重生=否。
2. **P2 适用性**：建议=「实际检索目标 ∩ C1–C6」。备选 A=仅 `investigator_assessment` source type；备选 B=`determine_component_mode`。B 会扩大到诊断/评分，与 09-13 上游待审冲突。
3. **UAT 必选 `PROFESSIONAL_JUDGMENT`**：建议保留，用新合成已确认缺失剧情满足，不删枚举、不放宽 v1。
4. **活门控 vs 冻结观察**：建议拆开测试；在重生前不要为绿测试改冻结 reason。

### 向 Codex 的有界问题

若决策点 2 不选「实际检索目标」：缺口生产者是否允许对**从未建检索作业**的 `requires_professional_judgment` 组件发出 PJ？这决定会不会把「未检索」晋升为「已确认缺失」。

**Codex 未答时的安全暂定路径**：不编辑、不刷新夹具、不放宽 schema。现场继续：无事实/无摘要/覆盖不全=未核实。已确认缺失视为未接线。四项失败保持为阻断证据。不把工作台 `_summary_gaps` 当作正式审核合同。

### 本会话只读范围

`context/r07-judgment-publication-boundary-20260913_conference_context.md`；`plans/codex_main_venue_r07-judgment-publication-boundary-20260913.md`；`app/domain/expression.py`；`app/domain/gates/assessment.py`；`app/domain/policies.py`；`app/domain/contracts/{evidence,uat,evidence_expectations_v2,judgment_search,enums,context}.py`；`app/domain/judgment_search_coverage.py`；`app/services/{fact_expectation_gaps,eligibility_review_projection}.py`；`scripts/generate_v2_contracts.py`；`tests/v2/{test_contract_artifacts.py,services/test_judgment_summary_gap_states.py,projections/test_evidence_expectations.py}`；`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §16–17.2；`docs/PROJECT_CONTEXT.md` R07 段；`artifacts/review-20260912/full-suite-20260913-binding-v6.xml` 失败摘录；`runs/conference/written-judgment-scope-20260910/supplied-absence-semantics.md`（既有设计证据，非本角色结论）。

本会话命令：构造 `CoverageGapSignal` / v1 `EvidenceExpectation`；内存 `build_fixture` ×3 与 `build_uat_workspace()`。无网络、无库写、无浏览器。
