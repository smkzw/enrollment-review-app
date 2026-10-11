Trellis SessionStart ✓ — Independent conference review for Phase 5.8 runtime bootstrap. Reading the assigned context packet first, then auditing only the delta evidence needed for pseudo-pass risks.Context packet is sparse (many TODOs). Auditing source-of-truth files for config registration, contracts, recovery, and acceptance harness next.Worker_01 predates the registration fix — verifying current recovery path, provider allowlist, and whether acceptance can green without live model.## Conference Report — `general_grok46` (Cursor CLI / auto)

**Role:** participant 2, parallel, read-only  
**Verdict:** Runtime registration/selection largely closes the worker_01 fresh-DB / wrong-agent gaps; the highest remaining **伪通过** risks are in **acceptance observability mapping + live-model gating**, not in lifespan registration itself.

---

### ISSUES_ONLY
（按严重度；仅当前可验证缺陷/验收缺口）

1. **S1 — 真实验收可在未跑真实模型时 Playwright 绿灯**  
   `PHASE5_REAL_ACCEPTANCE_ALLOW_LIVE_MODEL≠1` 时，项目创建/OCR/规范化/Profile/定位全部写 `disposition: "not_run"`，但 `phase5-real-acceptance.spec.ts` 仍断言观察非空、角色正确、无溢出即通过。结构性门禁（空库、拒 fixture）可 `pass`，**不能**证明 P5-AC10/11/12。

2. **S1 — `criterion_ids` 映射把结构性门禁标成真实运行证据**  
   `gate.fixture_routes` → `["P5-AC10","P5-AC13"]` 且 `disposition: "pass"`。拒 fixture **不是** Evidence Normalizer 真实运行。若后续按 `criterion_ids`+`pass` 灌 ledger，会伪满足 `browser_tester`（ledger 仅认 `pass`）。

3. **S1 — 原件定位验收只验几何相交，不验摘录/页/断言一致性**  
   `stepPatientProfileAndLocator` 只需任一条目：解码图 + 红框与图 AABB 相交即 `verifiedLocator=true`。不核对摘录 vs OCR、页码、文件身份或病例期望事实。错误/随机框只要压在图上即可过，**不足以防 P5-AC02 伪通过**。

4. **S2 — 规范化运行恢复与 Job 恢复不对齐**  
   OCR 用 `recovered_jobs/cancelled/failed_final`；`recover_fact_normalization_runs` 只把仍为 `running` 且 Job 已是 `cancelled|failed_final` 的 run 投影终态。租约过期后 Job 重入队时，FactNormalizationRun 可长期停在 `running`，且 lifespan **未**传入 `recovery_report`。测试 `test_startup_recovery_closes_missed_failed_run_projection` 已证明失败后 run 可残留 `running`。对 P5-AC11「无永久处理中」存在投影层缺口（Job 层有恢复，run/UI 语义可能漂移）。

5. **S2 — 创建/执行路径未再次强制校验模型 `agent_node`/provider**  
   生产命令经 lifespan 冻结身份选择，较好。但 `FactNormalizationJobService._validate_registered_agent_config` 与 executor `_load_frozen_agent_config` 对 ModelConfig **不**校验 `parameters.agent_node` / 支持的 provider；只严查 Prompt。防御纵深不足，历史/手注错误 `model_config_id` 可延迟到 transport 失败。

6. **S2 — 「真实模型可用性」仅合同登记，无启动探针**  
   `register_evidence_normalizer_runtime_config` 成功 ≠ oMLX/目标模型可加载。默认 `omlx` + `Qwen3.8-27B-...` 可登记，执行期才失败。与 S1 叠加时，易把「配置已注册」误当成「真实验收已过」。

7. **S3 — 自动方案信息保留仅在 live 分支断言**  
   live 时校验方案编号/版本/日期/名称且禁止脚本覆盖名称，合理。非 live 时这些断言整段跳过；且 live 成功步骤多为 `observed_only`，ledger 也不会自动记 `pass`——需 Codex 人工升级，映射错误时风险在 S1。

8. **S3 — 前后端合同：`run_id` 被前端丢弃**  
   后端 `FactNormalizationSubmitDTO` 含 `run_id`；`decodeFactNormalizationCommand` 不读。轮询靠 `job_id` 可工作，但排障/恢复诊断弱于后端能力（低）。

---

### EVIDENCE_LOCATORS

| 议题 | 定位 |
|---|---|
| lifespan 注册+冻结选择 | `app/api/v2/app.py` ~129–203；`fact_normalization_command_service.py` `register_*` / `select_*` / `create_or_reuse` |
| 环境变量 | `app/config.py` ~78–92 |
| 无 unmarked 回退（相对 worker_01） | `select_registered_evidence_normalizer_config` ~449–460：无标记则拒绝，不回退其他 Agent |
| Job 校验缺 agent_node | `fact_normalization_job_service.py` `_validate_registered_agent_config` ~166–208 |
| Executor 冻结核验偏 Prompt | `fact_normalization_executor.py` `_load_frozen_agent_config` ~255–323 |
| 恢复不对齐 | `app.py` lifespan vs `recover_fact_normalization_runs` ~545–564；对比 `recover_evidence_ocr_runs(...)` |
| 验收伪通过 | `phase5-real-acceptance.spec.ts`；`phase5-real-acceptance-support.ts` `STEP_CRITERIA`、`allowLiveModel` 分支、`stepPatientProfileAndLocator` ~874–987 |
| Ledger 仅认 pass | `tools/phase5_acceptance/ledger.py` `PASSING_DISPOSITIONS_BY_CLASS` |
| AC 原文 | `prd.md` P5-AC02/10/11/12 |

---

### NO_ISSUE_SCOPE
（本轮**不**再当作未修缺陷）

- 全新库缺 Normalizer 登记、误选其他 Agent 唯一模型（worker_01 当时缺陷）：当前 lifespan 注册 + `agent_node` 标记选择 + 精确 `registered_config` 已覆盖；聚焦测试 `test_fact_normalization_registration.py` 覆盖追加身份、漂移失败关闭、忽略其他 Agent 模型。  
- 客户端注入 Prompt/Model/Authority：命令 DTO 仅 `idempotency_intent` 且被丢弃。  
- 未对本仓库做安全渗透；未读生产路径；未改任何文件。

---

### RECOMMENDED_REPAIR

1. **验收硬门：** `allowLiveModel≠true` 时：要么整套 `test.skip`/`fail`（不得当 pass），要么 summary 含 `blocking: true` 且 CI/ledger 导入拒绝把该次 run 当作 P5-AC10/12 证据。  
2. **改映射：** `gate.fixture_routes` 至多挂结构性准则；**禁止**挂 P5-AC10。`gate.fresh_identity` 勿挂 P5-AC12。  
3. **定位断言升级：** 至少一条关键事实：文件身份 + 页码 + 摘录 ⊆ 页文本（或 OCR 回读）+ bbox 覆盖摘录区域；禁止「任一相交即过」。  
4. **恢复对称：** `recover_fact_normalization_runs` 消费 `RecoveryReport`（与 OCR 同形）：`failed_final/cancelled` 投影终态；`requeued` 明确保留/重置 run 语义并测「杀进程→重启→无永久处理中、无重复事实」。  
5. **纵深校验：** job create + executor 对 model 强制 `agent_node==evidence_normalizer` 且 provider∈支持集。  
6. **可选：** 启动健康探针（oMLX 可达/模型名）写入 readiness，与「合同已登记」分离展示。

---

### QUESTIONS_FOR_CODEX

1. Phase 5.8 独立测试者跑 Playwright 时，**是否强制** `PHASE5_REAL_ACCEPTANCE_ALLOW_LIVE_MODEL=1`？若否，谁负责把 `not_run` 从「通过」叙事中剔除？  
2. Browser 观察进 ledger 是手工还是脚本？若脚本，是否已按 `disposition==pass`∧`criterion_ids` 自动归并？（决定 S1 映射是否立即 blocker）  
3. P5-AC11 的权威状态是 Job state、FactNormalizationRun status，还是 Profile 生成态？三者不一致时以谁为准？  
4. 定位验收是否必须绑定病例金标准摘录，还是「任意一条可定位」即可？（影响 S1 定位修复深度）

**暂定安全路径：** 在 1–2 澄清前，**不得**将当前 harness 绿灯或 `gate.*.pass` 记为 P5-AC10/12 完成；runtime bootstrap 代码可继续审，但 5.8 闭环验收保持 blocked。

---

### RESIDUAL_RISK

- 多份 Normalizer ModelConfig（env 变更追加）下，生产靠 lifespan 精确 ID，安全；无 `registered_config` 的旁路会失败关闭——运维需知。  
- `ModelConfig.agent_node` 仍在 free-form `parameters`，无列级约束。  
- Ledger 要求 P5-AC12=`clinical_manual`：浏览器几何通过也**不能**替代逐事件人工核对——当前 harness 注释正确，流程纪律仍依赖 Codex。  
- Conference context/plan 大量 TODO；本结论以源码为准，非以空 plan 为准。

---

### 主动挑战（最高影响）

**假设「runtime bootstrap 完成 ⇒ 5.8 命令闭环可防伪通过」不成立。**  
注册/选择修复的是**启动与选模正确性**；防伪通过的主闸在**真实验收是否强制 live + 证据映射是否诚实 + 定位是否语义正确**。后三者任一缺口即可在「配置正确」的前提下伪通过。

**异议：** worker_02「无角色旧配置迁移回退」与**当前**选择器不符（当前无标记则拒绝）——以源码为准，该回退若仍存在于叙述中应更正，以免审查者低估严格性或误测旁路。

**决策点：** Codex 须裁定：5.8 浏览器证据的「完成」定义是（A）live+语义定位+人工升级 ledger，还是（B）允许 structural-only Playwright green 作为中间证据。推荐 **A**。
