# Execution Output: phase5-nextflash-resume-20260903b - worker_03

## Boundary And Context Check

- 本 pass 为**只读**工作项（work item 3）：梳理 SAR 31001 事实发布、事件、用药暴露、Patient Profile、原始证据临床 QC 的剩余验收路径和确定性检查；不得以流程成功替代临床验收。
- 全程未写入任何文件、未修改运行数据库、未启动长任务或模型调用、未调用 retry/cancel。数据库仅经 `file:…?mode=ro` URI 只读查询；作业/事实/Profile 状态以 SQL 观察为准。
- 初始读集两份文件已读；按需补充读取了任务检查点、prd、代码与运行数据，理由：本工作项的交付物就是“剩余验收路径 + 确定性检查”映射，必须以代码与真实运行状态为证据源。同伴报告 worker_01/02.md 均为 3 行占位（PENDING），本报告独立完成，无重叠依赖。
- 运行数据目录定位依据：`artifacts/phase5-acceptance/20260903/normalizer-single-page-diag/DIAGNOSIS.md`（前一轮执行遗留的只读诊断，其中记录了 fresh 数据根）与 `runtime-identity.json`。

## Work Performed

### A. 当前已核实状态（确定性观察，全部只读）

数据根：`artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/enrollment-review-v2.sqlite3`

1. **数据库完整性**：`PRAGMA quick_check=ok`；主库 SHA-256 `2d19774519ec67c8f9ad75eda4e25c7dc886eaf9677b2d617a51a52aff7c876c`，与暂停检查点 `CHECKPOINT_20260903_NEXT_FLASH_NORMALIZATION_PAUSED.md` 记录完全一致；WAL 0 字节 → 暂停后零写入。
2. **旧作业已处合法取消终态**：job `67478824bad845c6bd91494fa91f09bf`（fact_normalization）`state=cancelled`、`cancel_requested=1`、`progress 1/15`、无租约。作业事件序列（库内本地时间）：21:37:46 创建/步骤1启动 → 21:58:37 步骤1第1次尝试失败（作业 failed）→ 22:00:45 自动退避重试 → 22:17:25 步骤1第2次尝试完成、检查点 `8082e16d…` 落盘、步骤2启动 → 22:23:55 cancel_requested → 00:26:52 转 cancelled（标准 runner 路径，事件类型 `cancelled`）。即暂停检查点中“旧 cancel_requested 作业合法终态对账”**在检查点固化前已由 runner 完成**；检查点中“保留为 cancel_requested”的表述与当下库状态相比已过时（`cancel_requested=1` 标志仍在，`state` 已是 `cancelled`）。
3. **步骤结构**：15 步 = 14 个页组规范化步骤 + 1 个“聚合校验与事实发布”步骤；仅步骤 1（逻辑文档 `3de28631…` 页 1，基线血常规 PDF）completed（attempt 2/3），其余 13 个页组步骤与汇总步骤均为 cancelled。
4. **候选与未解决项**：run `72787b3e…` 持久化 29 fact + 1 event = 30 条候选、5 条未解决项，与检查点 `8082e16d…` 载荷逐项对账一致（input_sha256 `7474a7bc…`，raw_output_sha256 `c4b4753d…`）。5 条未解决项均为结构化缺口（3 条 `ambiguous_unit`→`record_incomplete`、1 条 `date_timezone_ambiguous`→`date_or_anchor_missing`、1 条 `ocr_format_risk` 双列排版风险），未见极性/数值虚构。另有前一轮单页诊断 run `28b2f434…` 的 31 fact + 2 unresolved 同表共存（按 run_id 隔离，不进入受控发布输入，但盘点时应避免混淆）。
5. **权威与证据侧就绪**：筛选 episode `59b98368…` 活动完整修订 `complete-529c2876…`（episode rev 4，24 页）；**基线** episode `746385ab…` 活动完整修订 `complete-5f514e57…`（episode rev 4，24 页，09-02 19:23:05 构建）——即基线期证据处理修订已存在，缺的只是基线事实规范化；run_in episode 无活动修订（治疗期，Phase 5 范围外）。规则目录：`ruleset:draft-version-09b593a721e7:phase_iii` rev 1，23 条父规则（与 `SAR_R15_PREPUBLICATION_QC_20260902.md` 的发布前结构核对一致）。
6. **发布侧全空（符合预期）**：`clinical_facts_v2` / `clinical_events_v2` / `medication_exposures_v2` / `fact_rule_links_v2` / `evidence_expectations_v2` / `patient_profile_revisions_v2` / `fact_gate_results` 全部 0 行。`claims_complete=false` 成立。

### B. 剩余验收路径（阶段 × 确定性检查 × 代码依据）

**阶段 1 — 筛选期规范化收尾（剩余 13 个页组 + 汇总发布）**

发现（阻断级，需 Codex 裁决）：当前产品代码**不存在能复用已完成第 1 步的合法续跑入口**：
- 合法创建入口仅 `POST /subjects/{id}/review-episodes/{id}/fact-normalization-jobs`（`app/api/v2/fact_normalization.py:41`）→ `create_or_reuse`（`fact_normalization_command_service.py:513`）→ 幂等键由活动权威+登记配置+输入范围派生（`app/domain/contracts/facts.py:699`）。幂等表已有记录 `677c455e…` → job 67478824（已核实），同范围重发只会返回该 cancelled 作业（`fact_normalization_job_service.py:434-447`，created=False，无新建）。
- `POST /jobs/{id}/retry` → `retry_failed`（`app/workflow/jobstore.py:1220`）**明确拒绝 cancelled**（“只有失败的任务可以重试”）。
- 执行器复用只认步骤检查点（`fact_normalization_executor.py:712-738`），无跨 run 的调用级复用；若通过改权威（重建修订/换登记配置）造新键新建作业，第 1 步模型调用将重跑（本轮该页组约 16 分 40 秒；DIAGNOSIS 记录同页历史成功调用端到端 45 分 52 秒）。
- 用户面恢复文案（`app/api/v2/vocabulary.py:51`）承诺“已完成内容和恢复位置仍会保留”，但无对应可执行入口。

推荐（最小改动，供 Codex 决策）：为无租约、终态对账后的 cancelled 规范化作业开放受控重入（如允许 `retry_failed` 接受 cancelled 的 fact_normalization 作业并保留完成步骤/检查点），同时把 run 行状态 `failed` 重开为 running（见下）；配套恢复+幂等回归与 worker_01 的检查点缺失复用修复同批验收。

附带状态不一致（恢复前必须处理）：run `72787b3e…` 行 `status=failed`。根因（推断，有事件链佐证）：21:58 作业级失败时 `project_failed_job`（`app/api/v2/app.py:197-202`）把运行投影为 failed；22:00 的自动退避重试走 `requeue_due_retries` 不重开运行；00:26 取消投影只改 `running` 运行（`fact_normalization_job_service.py:590`）。人工重试路径的 `reopen_for_retry`（`app/storage/fact_repositories.py:341`，仅 failed→running）因 retry 拒绝 cancelled 而不可达。

性能前置确定性检查（启动任何新页组前）：核对冻结模型配置的 max_tokens/超时合同与实际单页组耗时（16m40s–45m52s）——产品传输默认 600 秒客户端超时低于单次生成耗时，按现状每次调用都会 `TRANSPORT_FAILED`（与 DIAGNOSIS 一致）；先做检查点要求的 Schema/提示词缩减验证，再验证第 1 步幂等复用零模型调用。

**阶段 2 — 基线期规范化（合法新入口已存在）**
- 入口：同一 POST 端点作用于基线 episode `746385ab…`；权威从其活动指针 `complete-5f514e57…` 派生（`fact_normalization_command_service.py:440`）。该修订 19:23:05 才激活，晚于全部旧幂等键，预期 `created=true`（执行时以响应核实）。
- 确定性检查：计划闭包（`build_fact_normalization_plan`，DIAGNOSIS 已对筛选期同路径验证 24 页/5 文档全过）；步骤检查点逐页生成；调用数 = 计划数（汇总步骤 `fact_normalization_executor.py:932` 硬校验）。
- 顺序约束（检查点要求）：筛选期完成并完成候选/未解决项质量审计后才串行启动基线。

**阶段 3 — 聚合校验与事实发布（确定性，无模型）**
汇总步骤链条（`fact_normalization_executor.py:919-1048`）：权威复核 → 全部调用落库校验 → `validate_page_coverage`（24 页全闭合）→ 持久页闭包校验 → `orchestrate_run_gates`（`app/domain/gates/fact_batch_orchestration.py:834`：页覆盖/定位闭包/原文哈希/极性/单位/日期/来源强度/去重/文档内外冲突）→ 门禁结果落库 → `FactPublicationService.publish`（`fact_publication_service.py:171`，事务发布事实/事件/用药暴露/冲突组/定位链接）→ 权威复核 → 规则索引重建（`fact_rule_links_v2`）→ 资料期望五类投影（`evidence_expectations_v2`）→ `PatientProfileService.generate` 必须 succeeded（`fact_normalization_executor.py:987-998`）。
- 确定性检查清单（发布后）：`fact_gate_results` 行数 vs 候选数；检查点计数（published_fact/event/exposure、rule_link、expectation、conflict_group、rejected_candidate）与 SQL 计数逐一相等；run 终态 SUCCEEDED/PARTIAL 语义（存在被拒事务性门禁 → PARTIAL）；发布行全部绑定不可变权威元组（`FactAuthorityValidator`）。
- 筛选/基线各自在自己权威下发布与投影，结构上保证后期不静默改写早期（AC08）。

**阶段 4 — Patient Profile**
- 按权威生成不可变 revision（`patient_profile_service.py:93-107`：只读本权威已发布实体、泳道只取已发布 `profile_lane`、同内容幂等、内容变化链头 +1）；13 泳道、首屏突出集合、定位深链（仅真实 bbox）、陈旧/生成中/失败状态均为 5.5–5.7 已验收机制。
- 确定性检查：Profile API（当前链头/历史/指定修订）返回 succeeded revision；每条事实/事件定位都能在冻结修订内解析（越界大声失败）；500 事实投影性能沿用 5.5 验收（26.63s），本阶段真实数据量远小。

**阶段 5 — 原始证据临床 QC（人工/父级，不可被流程成功替代）**
- 逐事件对照 5 份原始 PDF（24 页/期别）核对人口学、疾病历程、MH、CM/治疗、检验检查/评分、日期、冲突、弱来源与定位（P5-AC12 的 SAR 半边；D001 II 受试者不在本工作项内）。
- 首页组已知 QC 输入：5 条未解决项须人工对照原件裁决（RDW-SD/P-LCC/NRBC 单位歧义、采样时间时区、双列排版 OCR 风险）；血常规页手写 `NCS` 便签尚未进入 Phase 5.5 三源手写审读（检查点已挂起）。
- 定位回放：每个关键事实/事件 ≤3 次操作打开正确文件/页/定位，无坐标时诚实降级（AC02）。
- 独立审查与试用（AC13）：会商只做架构/临床逻辑挑战；三名固定测试者（Cursor CLI auto、Pi minimax-m3、Pi ox-alpha-free）真实浏览器端到端；两类证据不互替；Codex 复核真实文件/数据库/浏览器后裁决。此前所有确定性绿勾都不改变 `claims_complete=false`。

### C. P5-AC01–AC13 状态映射（针对 31001 路径）

| AC | 机制就绪（已验收切片） | 31001 剩余 |
|---|---|---|
| 01 权威链 | 5.1/5.4 合同+校验器 | 发布后 SQL 核对发布行权威绑定 |
| 02 来源回放 | 5.6 定位深链/真实 bbox | 真实数据逐条回放核对（人工） |
| 03 沉默与否定 | 5.2/5.3 极性门禁 | 首页组 5 条未解决项人工裁决；后续页组同 |
| 04 来源强度 | 5.2/5.4 弱来源双状态 | 筛选病历转述类事实逐条核对（人工） |
| 05 日期范围 | 5.2 边界测试 | 发布行抽查：部分日期/持续状态/记录时间（人工+SQL） |
| 06 重复与冲突 | 5.2/5.4 冲突并列 | 冲突组并列展示核对（人工） |
| 07 期望覆盖 | 5.4 五类投影 | 期望行 vs 原始资料逐类核对（人工） |
| 08 增量与历史 | 5.5/5.7 revision 链 | 筛选→基线两阶段 revision 链验证（SQL+界面） |
| 09 Profile 内容 | 5.5/5.6 | 真实数据 13 泳道/首屏/三档宽屏浏览器（测试者） |
| 10 真实运行 | 5.3 | 剩余 13+基线页组真实调用（受速度/超时约束） |
| 11 恢复与幂等 | 5.3/5.7+worker_01 修复中 | 本作业取消/重入即活体用例；需先补重入能力 |
| 12 代表病例核对 | — | SAR 31001 半边：逐事件 QC（本报告阶段 5）；D001 另行 |
| 13 独立审查与试用 | — | 会商+三测试者+Codex 终裁，全部未启动 |

### D. 流程成功 vs 临床验收边界（本工作项的显式要求）

确定性层（机器可判）：DB 完整性/哈希、权威校验、页覆盖、九步门禁、事务发布原子性、规则索引重建等价、期望投影、Profile 投影幂等、调用数=计划数、检查点重放一致。
临床层（不可机器替代）：未解决项医学裁决、候选数值/单位/极性与原件逐条对照、弱来源提醒是否恰当、冲突并列是否保真、Profile 泳道临床含义、以及 AC12/AC13 的人工核对、独立试用与 Codex 终裁。**筛选/基线 15+15 步全部 completed、Profile succeeded 都只是“可进入临床 QC”的前提，不是验收通过。**

## Artifacts And Evidence

- 未创建/修改任何工作区文件；本报告由 runner 落盘。
- 只读证据源：
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/implement.md`（1451 行全读，含 P5-AC 与统一验证命令）、`CHECKPOINT_20260903_NEXT_FLASH_NORMALIZATION_PAUSED.md`、`prd.md`（AC 定义 102-114 行）
  - `artifacts/phase5-acceptance/20260903/normalizer-single-page-diag/DIAGNOSIS.md`（性能/路由/历史修订证据）
  - `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/enrollment-review-v2.sqlite3`（只读 URI 查询，见下节）
  - 代码：`app/services/fact_normalization_executor.py`、`fact_normalization_job_service.py`、`fact_normalization_command_service.py`、`fact_publication_service.py`、`patient_profile_service.py`、`app/workflow/jobstore.py`、`app/api/v2/{fact_normalization,jobs,vocabulary,app}.py`、`app/domain/gates/{fact_batch_orchestration,fact_candidate_gates,fact_evidence_closure}.py`、`app/domain/contracts/facts.py`、`app/storage/fact_repositories.py`

## Commands And Observations

- `shasum -a 256 <fresh db>` → `2d197745…`，与暂停检查点一致；`ls -la` 显示 WAL 0 字节、主库 mtime 09-03 06:24（暂停时刻）。
- `sqlite3 "file:…?mode=ro"` 执行：`PRAGMA quick_check` → ok；jobs/job_steps/job_events/fact_normalization_runs/calls/candidates/unresolved/gate_results/发布六表/episodes/rule_sets/idempotency_records 计数与状态查询（结果见 Work Performed A 节）。
- `grep`/`sed` 代码定位：retry 拒绝 cancelled（jobstore.py:1223-1225）、执行器检查点复用（executor.py:712-738）、汇总发布链（executor.py:919-1048）、幂等键（facts.py:699-723）、Profile 按权威生成（patient_profile_service.py:93-107）。
- 未运行 pytest/前端套件：映射工作不要求，且统一验证命令属 Codex 验收工具；未发现缺环境（`.venv`、sqlite3 3.51.0 可用）。

## Blockers Or Missing Environment

1. **重入入口缺口（需 Codex 产品决策）**：cancelled 规范化作业无合法重入路径（create 同键返回旧作业、retry 拒绝 cancelled、无跨 run 复用）；直接后果是要么改代码开受控重入，要么接受第 1 步起全部重跑的模型成本。
2. **run 状态不一致**：run `72787b3e…` `status=failed` 与作业 `cancelled` 并存（成因已定位，见 B 阶段 1）；任何重入实现必须一并处理 run 重开。
3. **模型性能/超时失配（阻断真实运行）**：单页组 16m40s–45m52s vs 产品传输默认 600s；未解决前新页组必然 TRANSPORT_FAILED。检查点规定的 Schema/提示词缩减尚未实施（属 worker_01/后续执行范围，本 pass 只登记）。
4. 无缺失工具/依赖；未安装任何包。

## Rerun Requests Or Next Step

供 Codex 裁决的精确问题：**是否按“最小重入”方案开放 cancelled 规范化作业的受控 retry（保留完成步骤/检查点 + `reopen_for_retry` 重开 run 行 + 回归测试），还是接受新幂等键全量重跑？** 建议前者：它与既有用户面恢复文案、幂等合同和 worker_01 的检查点复用修复天然对齐，且避免 14 次全量重调。

建议执行顺序（全部确定性检查可先于模型运行）：(1) 落实重入并回归；(2) 核对冻结模型配置/超时与 Schema 缩减，先验证第 1 步零模型调用复用；(3) 筛选期余下页组+汇总发布，跑 B 阶段 3 的 SQL 对账清单；(4) 候选/未解决项质量审计（临床输入）后经合法 API 新建基线作业（核实 created=true）；(5) 基线发布+Profile；(6) 进入阶段 5 临床 QC；AC12/AC13 人工路径与 `claims_complete=false` 维持不变。本 pass 无需重跑；若 Codex 采纳重入方案，worker_01 的实现与回归应在同一变更批验收。
