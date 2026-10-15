补充审阅完成。我核对了新投影 `control_evidence_requirements.py`、更新后的 `ControlMinimumEvidence`（含 `workflow_stage_ids`）、门禁 v2 的节点闭合校验、姐妹访视投影改动的三个消费点、模板/存储合同现状（未接入）、`_coverage_verdict` 对两个来源政策布尔值的实际消费方式、`source_validity` 锚点语义，以及更新后的设计 §17.3。以下为本次续审报告。

---

# Conference Output: r05-control-expectation-scope-20260914 - evidence_single_object（续审：来源政策与存储边界）

## Output

**总体判断**：已实现的“显式节点 + 每节点独立身份 + 目录证明闭包 + 姐妹访视跳过”与 §17.3 新文本一致，方向正确；**当前最大缺口是来源政策（source policy）三态设计与共享管道的进入条件**——`ControlEvidenceRequirement` 完全没有政策字段，若原样流入共享模板通道，将静默继承宽松默认值，等于由默认值替方案作临床约束决定。

### 优先风险（均经当前源码核实）

**R1 来源政策缺位且默认值会“放行”（最高）。**
`ControlEvidenceRequirement` 仅承载 `required_source_types` 等字段，无两项政策与有效期（app/projections/control_evidence_requirements.py:17-30）。共享侧 `EvidenceRequirement` 的 `allows_screening_record_transcription=True`、`requires_contemporaneous_objective_source=False`、`source_validity_window=None` 是带默认值的非可选布尔（app/domain/contracts/rules.py:285-288），且直接决定覆盖判定：转述是否算 weak（app/projections/evidence_expectations.py:161-167）、是否必须同期客观来源（:151-153）、是否做新鲜度过滤（:252-254）。`None` 窗口意味着**完全不做时限核对**——这正是 §17.3 明令禁止的“从缺少期限推断任意期限”。未知（unknown）绝不能落成这两真一空的默认形态。

**R2 三态必须放在新控制线合同，不能改共享合同。**
模板投影哈希包含两个布尔（app/domain/contracts/evidence.py:178-197），v1/v2 哈希形态有专门兼容层（:166-172、215-222）；把共享字段改成三态会改历史字节。正确位置：`ControlMinimumEvidence/Draft` 增可选 `source_policy`（每项 `required|not_required|unknown`，缺省=历史未声明→按 unknown）与可选**显式** `result_validity_window`，序列化时缺省即剔除以保历史字节（沿用 `workflow_stage_ids` 的先例，app/domain/contracts/protocol_controls.py:1410-1415）。禁止从义务 `temporal_scope`/calendar_lookback 推导检查有效期（§17.3：病史回溯、结果有效期、同期记录分别表达），也禁止从药名/疾病/资料类型单独推政策。

**R3 unknown 的可见而不假通过/不阻断——最小语义**：
- **进入共享模板通道的条件 = 政策已断言**（`required`/`not_required`）：此时模板布尔是真断言而非默认；unknown 不建共享模板，留在“资料已请求”可见层（页审提示 v15 已带紧凑引用，app/projections/page_review_prompt_pack.py:22-27）。
- **unknown 政策在请求层的呈现**：“来源要求未确认（未核对是否需原件/同期记录）”，作溯源提醒而非 absent 阻断缺口——不假通过（无 complete 判定捷径，因为根本不进 `_coverage_verdict`），不假阻断（不产生 `record_incomplete` 兜底，app/services/fact_expectation_gaps.py:287-302 只作用于已存储模板）。
- **unknown 适用性同理**：控制 `applicability_expression` 无求值器前（frozen 审核拒绝仍在，app/services/frozen_review_calculation.py:37-38），控制来源要求只能以“适用性未确认”呈现；确认适用后才允许 absent 阻断。义务强度必须随行——当前投影丢失了父控制的 modality（control_evidence_requirements.py 无此字段），RECOMMENDED/BEST_EFFORT 证据进共享通道后会与 mandatory 同样阻断，违反 §17.3“推荐与必须分别保留”。建议 `ControlEvidenceRequirement` 增 `obligation_modality`（门禁已有保真检查可复用，app/protocols/protocol_control_gate.py:945-993），非必须 → 永久留在请求层。

**R4 到期节点≠采集日期：锚点语义基本就绪，但控制窗口须显式。**
`source_validity_anchor` 按到期阶段取 SCREENING/BASELINE/REVIEW_NODE 日期（app/domain/source_validity.py:10-23），三值判定含 UNKNOWN（:26-45）——"较早来源支持较晚显式复核”由锚定判断节点的窗口自然容纳。风险仅在：控制证据若绑显式窗口，锚必须是**所绑访视的节点日期**（姐妹访视各自 episode 各自锚）；且 UNKNOWN 新鲜度应显示为“结果时限未核对”，而非现在的静默通过。

**R5 姐妹访视改动的范围正确性（受托检查项）——判定：正确，附两处边角。**
三处消费已对齐：投影跳过并注明“非本访视缺失、不证明先后”（app/services/evidence_expectation_projection_service.py:77-80）、缺口兜底跳过（app/services/fact_expectation_gaps.py:235-238）、审核缺口跳过（app/services/eligibility_review_projection.py:423-429）；episode 按节点建（app/domain/contracts/review.py:87-115），姐妹模板在其自身节点 episode 投影；旧代码是硬报错故不存在历史姐妹行。边角一：`_prior_unreconfirmed_signals` 只跳未来阶段不跳姐妹节点（fact_expectation_gaps.py:466），当前无害仅因姐妹行不可能存在，建议补同款跳过以防将来模板范围/节点指针变化。边角二：未来阶段模板得 NOT_DUE 行、同阶段姐妹模板无行——有意为之，但报告/上下文层必须读全量模板并区分“属同阶段另一访视”，否则姐妹访视要求看似缺失（§17.3 已写明，属呈现层义务）。

**R6 页审引用与 finalize 的现实碰撞点。**
提示 v15 给模型的紧凑 `requirement_id` 若被模型写进候选的 `supported_requirement_ids`/未解决项的 `affected_requirement_ids`，finalize 会因查无当前模板而 StepFailure（fact_expectation_gaps.py:154-161、192-198 "没有当前规则修订模板”）。在控制要求进入模板存储前，必须确保模型输出合同把这些 ID 限定为“关联留痕”而非支持绑定，或扩展该查表范围——这是共享存储未接入期间最可能先炸的接缝。

**R7 证据级来源锚过粗（次要）。**
`ControlEvidenceRequirement.source_span_ids` 取控制级并集（control_evidence_requirements.py:73），弱于流程先例的逐条要求锚（protocol_publication_service.py:691-696、711-743）。入共享存储前应收窄为支持该证据的片段或由门禁增证据级锚。

### 最小字段/消费/存储顺序
① 控制线加三态 `source_policy` + 显式 `result_validity_window` + `obligation_modality`（缺省剔除保字节；投影版本升 `control-evidence/v2`）；② 门禁 v3：新发布必须显式断言两项政策（协议确实沉默时显式写 `unknown`，这也是忠实断言），并校验政策不随义务强度软化/硬化；③ `ControlEvidenceRequirement` 承载上述字段；④ 共享侧 `EvidenceRequirement` 增第三 origin（`protocol_control_id` 三选一，rules.py:291-297 + 存储CHECK + `save_rule_set`/`save_expectation_templates` 扩展，同事务，不动已发布 `due_requirement_ids`）；⑤ 仅“政策已断言 + 适用性已确认（独立投影）”的要求可生成共享模板并参与 absent 判定；其余留在请求/提醒层；⑥ 判断检索增控制来源分支（原文走 protocol source spans）。

### 源码无法裁决、留 Codex 的取舍
1. unknown 转述政策：完全 fail-closed（不进共享通道，本报告推荐）还是允许 weak+溯源标记更早共享——前者更安全，后者覆盖更快。
2. 适用性状态的承载位置：期望行内标志 vs 独立适用性投影（推荐独立投影，避免改 `EvidenceExpectationV2` 不可变合同）。
3. 门禁是否允许 `unknown` 无限期存在，还是发布后限期要求人工补断言。

本次为只读续审：未运行测试、未导入应用、未做任何修改；不构成临床或最终验收结论。
