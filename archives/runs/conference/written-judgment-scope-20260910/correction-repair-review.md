# Conference Output: written-judgment-scope-20260910 - evidence_single_object

## Output

同会话第二轮只读审计完成（未改代码、未联网、未调用模型；独立复跑新测试 7 passed + 信号别名保真测试 3 passed，与 owner 的 73 passed 相容）。结论先行：**D1 修复的主体是成立的——共享推导逐行等价、终结行为保真、无循环导入、回滚与追加写语义正确、两个原始缺陷（静默升级/整笔回滚）已被真实任务链回归覆盖。但 owner 的三个疑虑经源码推演全部成立为真实缺陷或真实降级路径：concern 1 与 3 是确定性的特异性丢失，concern 2 的启发式存在可构造的“保守状态蒸发”漏洞。concern 4 的答复：仅靠窄作用域修补不够，concern 2 的精确性确实需要持久化输入信号溯源；但 1 和 3 可先用不引入溯源的确定性小修。**

---

### 一、修复主体核验（证据，全部通过）

- **共享逻辑保真**：`fact_expectation_gaps.expectation_gap_signals`（`app/services/fact_expectation_gaps.py:86-217`）与我第一轮读到的原 `_expectation_gap_signals` 逐行等价（未解决项映射、被拒候选 OCR 信号及其 accepted_requirements 抑制、JSON 去重、concrete 集合、兜底循环的 stage/workflow 判定与判断类分支）。终结调用点不变（`fact_normalization_executor.py:1277-1283`）；兼容别名注入模块全局（:137-158），既有 monkeypatch 单测语义保留（我复跑 2 个别名测试通过）。
- **无循环导入**：新模块只依赖 domain/storage/projections/workflow.errors（:24-68）；其全部依赖经 grep 确认不 import 任何 service。
- **回滚/追加写**：`ReprojectionLineageError`/`StepFailure` 在 `_reproject_expectations` 内包装为 `FactCorrectionError`（`fact_correction_service.py:1317-1331`），落入既有 ：1190-1204 整体回滚；期望仍经仓储追加 revision（测试断言 rev 2/3），旧行保留；`exclude_fact_ids=superseded_entity_ids` 仍在（:1338）。
- **node/local**：node 重投影全部模板、local 限受影响模板（:1300-1313）；由于兜底循环保证每个到期模板至少有 fallback 信号，`ProjectionInputError` 回滚路径在正常流中已不可达（防御性捕获保留，正确）。
- **不收集全部历史运行**：孤立运行排除测试真实且有效（`test_reprojection_ignores_unrelated_orphan_run`，且其注释诚实说明了跨权威不可构造的原因）。

### 二、逐条疑虑裁决（源码推演，含可复现链）

**Concern 1 —— 成立（特异性降级，非虚假升级）。**
决定性事实链：修订产生合成运行 `fcorr-run-*` 且新实体改挂该运行（`fact_correction_service.py:562`、:610、经 `_ensure_correction_run`/`_publish_primary_entity` 持久化 :1611-1675，合成运行**没有任何未解决项**）；原运行因此在其全部实体被修订后失去一切活动实体引用。而 `select_reprojection_source_runs` 只回溯**本次修订目标**的谱系（`fact_expectation_gaps.py:288-303`）。可复现链：run_R（事实 X 覆盖模板 T + 未解决项记录 T 的 OCR 风险）、run_Q（无关事实 Y）——修订 X（谱系含 run_R，风险正确重建）→ 再修订 Y（选择集 = {fcorr-run-C1, run_Q}，**run_R 掉出**）→ T 的具体 OCR 风险不可重建 → `_prior_state_needs_unreconfirmed_pad` 对 observed_weak/OCR 判真（:333-351）→ pad 为通用非默认 `observation_unverified`（:394-405）。即：**已知具体风险被替换为泛化不确定性**。所幸对 `_SIGNAL_ONLY_WEAK_GAPS` 先前状态，pad 保证不会升到 observed；故是“降级为泛化”而非“清除”。现有双修订测试只覆盖同链目标（`test_correction_lineage_reaches_original_run_across_two_corrections`），跨链场景无测试——这正是漏洞所在。
**最小修**（无需新溯源）：选择集追加“当前权威下每条修订记录的目标实体所引用的运行”（`source_run` 在 prepare 时已读取，`fact_correction_service.py:566`，只需在选择器中按 correction.target_id 取实体并校验权威后并入）。这保持“孤立运行不入选”的边界（T-E 回归必须保留），也不等于收集全部历史运行。

**Concern 2 —— 成立（启发式有真实漏洞，非仅理论）。**
`_prior_state_needs_unreconfirmed_pad`（:342-351）对 observed_weak+UNVERIFIED 仅当 `source_coverage == "complete"` 才 pad；ABSENT+UNVERIFIED 一律不 pad。但 **pad 自身产生的状态不是不动点**：pad + 仅弱覆盖事实 → 存储为 (observed_weak, UNVERIFIED, source_coverage="weak")（投影器 `evidence_expectations.py:327` 无 complete 事实即 "weak"）；pad + 无覆盖 → (ABSENT, UNVERIFIED)。下一次修订若把覆盖补成完整：先前期望按启发式判为 fallback 起源 → 不 pad → fallback_only 信号被 complete 事实抑制（`evidence_expectations.py:256-260`、:286-297）→ **OBSERVED，保守状态蒸发**。两步修订即可构造（第一步产生 weak/UNVERIFIED/weak，第二步补强覆盖）。信息论层面：fallback 起源与 pad/具体起源在这两种形态下**存储元组完全相同**，事后不可判别——启发式在此不是“保守与否”的选择，而是不可判定。唯一受保护的形态（/complete）恰是现有单样本测试所在的分支；同意 owner：不能因该样本保守就背书。D2 一旦落地真实非默认 unverified 生产者，漏洞会一步显化。
**结论（并入 concern 4）**：此处的精确 pad **确实需要持久化输入信号溯源**（最小形态：每条期望 revision 记录施加于它的具体（非 fallback）信号 kind 集合，或等价布尔+枚举；读侧据此判别“具体未核实”与“兜底未核实”）。过渡期可接受现状但必须以测试钉死当前行为（T-B/T-D），防无声扩散。

**Concern 3 —— 成立（跨运行合并抑制清除已知风险）。**
`reconstruct_reprojection_gap_signals` 合并所选运行的全部候选与 TRANSACTIONAL 门禁（:427-450），`expectation_gap_signals` 的抑制逻辑用合并后的 `accepted_requirements`（:133-150）：**任何**历史 accepted 候选（哪怕其事实已被取代、或修订后已解除该要求绑定）都会抑制同要求的被拒候选 OCR 信号。原始终结中“accepted ⇒ 会发布 ⇒ 会覆盖”使抑制安全；重投影上下文中该耦合已断裂。可复现链：run_R 内候选 A（要求 R）被拒 + 候选 B（要求 R）通过并发布 → 修订 B 解除 R 绑定（同缺陷 B 测试的 updates）→ 重投影时 B 原 run 的 accepted 候选仍判 R 已接受 → A 的“发现相关记录但未通过完整性核对”被抑制 → 只剩泛化 `record_incomplete`（“当前尚无已核实的相关记录”）。这不是升到 observed（仍 absent），但把系统自证记录里“有相关记录但完整性未过”这一类别抹成“没找到已核实记录”——与“区分记录不全/未执行/冲突”的分层规则相悖，且未经过任何显式解决。
**最小修**（无需新溯源）：给 `expectation_gap_signals` 加可选参数（默认 None 保持终结行为冻结），重投影路径传入“活跃且仍绑定该要求”的 accepted 候选过滤——候选→事实映射可由现有 `gate_id`/`source_candidate_ids` 关联推出，纯当前态计算。

**Concern 4 裁决**：窄作用域修补对 concern 1、3 **足够**（上文两处确定性小修，均不改合同、不动旧数据）；对 concern 2 **不够**——精确 pad 依赖持久化输入信号溯源，这是真实需要的新持久化信息，不是架构重写（一行级附加字段/链接表即可）。三项都符合 owner 约束：以精确源重放为主机制，溯源仅在重放不可重建时消歧；不从数值修订推断临床解决、不把旧缺口当现症事实、不收集全部历史运行。

### 三、遗留必测（我未执行，executor 落地）

- **T-A（concern 1）**：双运行跨链场景（修 X 后修 Y），先按现状断言 T 降级为 observed_weak/OBSERVATION_UNVERIFIED（钉死当前行为），修复后改为断言 OCR_OR_PARSE_RISK 保留。
- **T-B（concern 2）**：两步链得到 (observed_weak, UNVERIFIED, weak) 后第三步补完整覆盖；现状断言 OBSERVED（记录漏洞），溯源修复后断言保持 weak。
- **T-D（T-B 的守门伴测）**：fallback 起源的 ABSENT/UNVERIFIED 在完整覆盖到位后**仍须**升为 OBSERVED——确保修复不会过度冻结兜底语义。
- **T-C（concern 3）**：同要求 accepted+rejected 共存、修订解除绑定后，断言应得 OCR_OR_PARSE_RISK（修复后）而非泛化 RECORD_INCOMPLETE。
- **T-E**：concern 1 的选择集扩展后，孤立运行排除性质必须保持（复用现有 orphan 测试）。
- 小项：`_prior_unreconfirmed_signals` 未像兜底循环那样跳过“同阶段另一流程节点”模板（:386-387 只查 due_stage）——该情形下投影器本就硬拒，行为等价，仅冗余 pad，可顺手对齐，非缺陷。

### 四、边界与不确定性声明

- 证据等级：本节全部结论来自源码直接读取 + 已有测试复跑；concern 1/2/3 的可复现链是确定性推演（关键事实：合成运行改挂 ：562/:610、无未解决项持久化、抑制用合并集 ：133-150），**未实际执行新构造用例**（我无写权限），故标注为“源码推演成立、待 T-A/T-B/T-C 实证”。执行者为同厂商 Flash 变体、且自报已复现 D1——我的审计独立于其报告，不构成验收；D2/R1/打印分析按嘱仍独立挂起，未与本轮合并。
