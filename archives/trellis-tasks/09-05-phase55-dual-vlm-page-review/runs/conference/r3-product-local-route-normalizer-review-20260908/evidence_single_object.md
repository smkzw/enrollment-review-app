I'll start a read-only evidence pass on the listed source and tests, focusing on local-route wiring, job identity, and verified/pending input boundaries.I’ve got the route and admission layer; next I’ll inspect job identity, executors, and how pending vs verified input is built.Job identity and pending policy are in view; next I’ll read executor input construction, the normalizer contract, and the isolated script.The listed `app/llm/evidence_normalizer.py` is missing; I’ll trace the actual adapter, API enqueue, admission wiring, and mixed pending/verified input next.# Conference Output: r3-product-local-route-normalizer-review-20260908 - evidence_single_object

## Output

本角色只读审阅新本地主读正式接线与规范化输入保全。未改源码、未跑测试、未调产品模型、未读病例或 `.env`。`app/llm/evidence_normalizer.py` 不存在；输入/提示实际在 `app/agents/evidence_normalizer.py` 与 `app/domain/contracts/evidence_normalizer.py`。

### 最高影响缺陷

路由切换后新建的页级任务会留下第二份同版本 coverage，`select_normalizer_coverage` 因「不唯一」拒绝规范化。这会同时打断产品「换本地主读后再整理」和 `scripts/run_isolated_page_revision.py --normalize`。

### 1. Evidence

**新任务路由（当前代码默认）**
- `app/config.py:189-211`：`PAGE_REVIEW_MAIN_A_MODEL` 默认 `glm-5.3-flash`；`PAGE_REVIEW_MAIN_B_PROVIDER` 默认 `mlx-serve`；`PAGE_REVIEW_MAIN_B_MODEL` 默认 `hub/ddalcu_Qwen3.8-Flash-Next-MLX-Serve-mixed-4-8bit`。
- `app/llm/page_review_harness.py:183-188,193-221`：main-A 必须 `zhipu-coding-plan` + `glm-5.3-flash`，`reasoning_effort` **写死** `"low"`；mlx-serve 时 main-B 必须精确匹配上述 Qwen 模型，`max_concurrency=1`。
- `app/llm/page_review_harness.py:267-272`：mlx-serve 预检要求 `loaded is True`、`state == "ready"`、capabilities 含 `vision`；失败文案为「不自动加载或替换模型」。
- `app/llm/page_review_harness.py:77-78`：enqueue 要求两个主读同时存在；`preflight_page_reader_routes` 主读失败即抛，手写道可省略。

**密钥与 fallback**
- mlx-serve 且未设 `PAGE_REVIEW_MAIN_B_API_KEY` 时用 `"local-product"`（`page_review_harness.py:162-164`）。`CMS_SMK_API_KEY` 仅非 local 时回退（`:166`）。`route_identity` 不含 `api_key`（`page_review_job_service.py:59-64`）。
- 若进程仍带旧的 `PAGE_REVIEW_MAIN_B_API_KEY`，mlx-serve 会原样使用（`harness.py:162`；`test_page_review_local_route.py:51-58` 明确测了「显式密钥被采用」）。
- `read_page` 在 `content_filter`/`endpoint` 时若 `fallback_base_url` 非空会改 `base_url` 再打一次（`harness.py:559-566,580-585`）。默认空串（`config.py:198-214`），但环境变量仍可打开自动换端点。`fallback_used` 进入 `page_review_id` 哈希（`harness.py:672-673`）。

**历史任务身份**
- 页级幂等键 = `r3_page_review:` + `canonical_hash(payload)`，payload 含 `routes`（`page_review_job_service.py:104-129`）。换 provider/model/effort 会得到新 job，旧 job 不被覆盖。
- 执行期：`payload` 版本 ≠ 当前 `page_review_execution_versions()` → `R3_EXECUTION_VERSION_CHANGED`（`page_review_job_executor.py:46-51`）；`payload["routes"]` ≠ 当前 `route_identity` → `R3_ROUTE_CHANGED`（`:54-55`）。旧任务不能用新运行时续跑。
- `execution_versions` 只有 contract/prompt/reconciliation/page_review 合同版本，**不含路由**（`page_review_job_service.py:32-37`）。`predecessor_coverage_id` 只在 recovery 重读时写入（`page_review_job_executor.py:83-85`；`page_review_recovery.py` 被 enqueue 引用）。
- `select_normalizer_coverage`（`page_review_coverage_selection.py:25-60`）：按权威+条款包筛 coverage，再要求 `execution_versions == 当前`，再用 predecessor 去重，丢掉有 `lane_failures` 的；`len(candidates) != 1` 则 `PAGE_COVERAGE_NOT_READY`「没有唯一可用的判读结果」。测试已固定「两份成功 coverage 即 409」（`test_page_review_job_executor.py:233-238`）。空 `execution_versions` 的旧 coverage 会被滤掉（`test_page_review.py:126-132`），**同版本、不同路由的成功 coverage 不会**。

**辅助复核身份**
- 幂等键 = `r3_targeted_page_review:{reconciliation_id}`（`targeted_page_review_jobs.py:84-87`），注释写明配置变化也不换键。
- payload 含 `targeted_routes`（两主读 `reasoning_effort="high"`，`:30-31,74`）。同键异哈希 → `IdempotencyConflict`（`idempotency.py:111-124`）。
- 执行期 payload.routes ≠ 当前 targeted routes → `TARGETED_REVIEW_CONTRACT_CHANGED`（`targeted_page_review_executor.py:30-34`）。
- `compare_targeted_reads` 固定 `candidate_auto_accept: False`（`targeted_page_review.py:64-65`）。

**跨本地串行**
- `_admission_key` 把 `mlx-serve`/`mtplx-gui`/`mtplx`/`omlx` 合成 `("local","shared")`，limit=1（`page_review_admission.py:9-22`）。测试证明 MAIN_B 与 HANDWRITING_C 峰值并发为 1（`test_page_review_admission.py:13-31`）。
- `PageReviewRuntime._prepare` 把 admission 接到页级/辅助执行器（`page_review_runtime.py:40-46`）。
- `preflight_page_reader_routes` 对三道 `asyncio.gather` 并行 `/models`（`harness.py:287-290`），此时 admission 尚未建立。
- OCR 走 `OmlxGateClient`（`app.py:265-287`），`OCR_MAX_CONCURRENT` 默认 8（`config.py:145`），不经过 `PageReviewAdmission`。方案解构默认 mtplx，同样不经过该闸。

**规范化输入 / 无核实观察**
- 产品 `create_app` 设 `require_page_review=True`（`app.py:248-252`）。HTTP `POST .../fact-normalization-jobs` 经 `FactNormalizationCommandService.create_or_reuse` → `select_normalizer_coverage`（`fact_normalization.py:41-60`；`command_service.py:538-554`）。
- 有 coverage 时跳过视觉观察缝合（`fact_normalization_job_service.py:312-320`）。
- `pending_only_output`：该调用内**任一条** reconciliation 有已采信观察则返回 `None`（走模型）；否则无模型，按 `page_numbers` 逐页写 `no_verified_observations`，reason 写明「不代表符合入排要求」（`page_review_pending_normalization.py:14-37`）。
- executor：未知 policy 硬失败；有 policy 才调用 `pending_only_output`；legacy 无 policy 即使无采信观察仍打模型（`fact_normalization_executor.py:1117-1125`；`test_r3_page_review_normalizer_wiring.py:157-212`）。
- 模型输入：R3 把 OCR 改名为 `ocr_sidecar_pages`，并附 `accepted_observations` + `pending_observations` + 冲突（`evidence_normalizer.py:755-837`）。提示禁止用 pending 造已采信事实、禁止从已舍弃页侧车另造候选（`:555-564`）。`compact_page_review_input` 去掉 pending 的几何/派生值，保留原文与 excerpt（`page_review_model_input.py:6-37`）。R3 取消 `_MAX_PROMPT_CHARS` 上限（`evidence_normalizer.py:876-881`）。
- `DISCARDED_NO_ELIGIBILITY_VALUE` 无 reconciliation（`page_review_execution.py:125-138`）。`build_page_review_normalizer_input` 跳过无 `reconciliation_id` 的页，失败待复读直接阻断（`fact_normalization_source_adapter.py:599-615`）。
- 研究者书面判断：读页提示「不补写研究者判断」「无手写必须 `handwriting=[]`」（`harness.py:387-388,531`）。缺失判断在 finalize 以 `GapType.PROFESSIONAL_JUDGMENT` 报告，不改成入排通过（`fact_normalization_executor.py:236-250`；`evidence_expectations.py:258-275`）。

**正式试验入口**
- `scripts/run_isolated_page_revision.py:84-110`：`create_app(...)` + `TestClient.post` 产品 `page-review-jobs` / `fact-normalization-jobs`，`JobRunner.run_job(新 job_id)`。要求 HTTP 201，200 复用旧任务则中止。`run_runner=False`，不认领历史队列。
- 脚本复制整库（含旧 coverage），新 POST **不**带 `predecessor_job_id`（`:89`）。未断言 GLM low / mlx-serve ddalcu，路由完全跟进程环境。
- 接线单测 `_persist_page_review` 仍写入 `cms-smk` / `MiniMax-M3` / `reasoning_effort="high"`（`test_r3_page_review_normalizer_wiring.py:45-55`），走 `FactNormalizationJobService` 而非 HTTP。

### 2. Inference

1. **已确认（产品+孤立试验）**：换 mlx-serve 后，因 payload 含 routes，会新建页级 job（符合「保留旧身份」）。但新 coverage 与仍匹配当前 `execution_versions` 的旧成功 coverage 并列，且没有 predecessor 链。规范化选择器会 409。孤立脚本在「源任务已是旧云端路由、合同版本未变」时，页级 201 能跑完，`--normalize` 会在产品 API 上失败。这不是试验脚本私有逻辑，是产品选择器行为。

2. **已确认（辅助复核）**：路由变化后，同一 `reconciliation_id` 会 `IdempotencyConflict`（409），不能建新辅助任务，也不能跑旧 payload（执行期合同变更）。辅助复核在换本地主读后被锁死。

3. **已确认（残留密钥）**：mlx-serve 不继承 `CMS_SMK_API_KEY`，但会把仍存在的 `PAGE_REVIEW_MAIN_B_API_KEY` 打到 `127.0.0.1:11234`。这是跨 provider 密钥残留，不是模块常量泄漏（测试已挡住后者）。

4. **已确认（自动 fallback 仍存活）**：默认关闭，但 `read_page` 仍按 `fallback_base_url` 自动换端点。与「无自动模型 fallback」不一致；换的是 URL 不是 model 字段，身份哈希会记 `fallback_used`。

5. **已确认（混合输入偏大）**：pending 短路是**整个 call** 全有或全无。`max_pages_per_call` 默认 2（`config.py:340-342`）。同一逻辑文档一组里只要一页有已采信观察，整组进模型，并带上未核实页的全文 sidecar、pending 观察和舍弃页 disposition。证据没有丢，但未核实页的 OCR 对「只能从 accepted_observations 造候选」是冗余的。

6. **已确认（正式入口用了产品 API）**：孤立脚本的创建与执行走 `create_app` 注册的 runtime/command/executor，不是私有 harness。它没有覆盖 coverage 唯一性、也没有钉死新路由。页级本地路由单测只打 `require_page_reader_routes(dict)`。

7. **未升级为缺陷**：admission 对页级 mlx-serve 与 mtplx-gui 串行是有效的；OCR/解构不在闸内。需求写「其他应用不归本产品管」。预检并行 `/models` 通常很轻。缺失研究者判断走 gap，不走「请确认缺失」或自动合格。`candidate_auto_accept` 仍为 false。

### 3. Recommendation（最小修订，不改代码）

**P0 — coverage 选择（换路由后仍可整理，且不改写旧 coverage）**
在 `select_normalizer_coverage` 增加与路由绑定、但不修改历史行的过滤，三选一，优先前两个：
1. 把 `route_identity`（不含密钥）纳入 coverage 的比较键：或写入 `execution_versions` 的显式字段，或在选择时要求 coverage 所引用的 main-A/B `provider+model+effort` 等于当前 `require_page_reader_routes()`。旧 MiniMax coverage 自然退出当前选择，行仍保留。
2. 若 Codex 不愿把路由放进 `execution_versions`：当多份成功 coverage 版本相同且无 predecessor 时，拒绝静默挑最新，改为 409 并要求带 `predecessor_job_id` 的受控重读，或提供显式 coverage_id。不要按 `created_at` 默默选一份。
3. 孤立脚本：`--normalize` 前若存在同权威、当前版本的旧 coverage，应失败并写明原因；或 POST 页级任务时带上源 job 为 predecessor。不要为了让试验通过而绕过 `select_normalizer_coverage`。

**P0 — 辅助复核身份**
幂等键改为 `targeted + reconciliation_id + route_identity`（或 targeted payload 哈希）。同一 reconciliation、旧路由的任务保持不可变；新路由允许新任务。不要把 `candidate_auto_accept` 改成 true。

**P1 — 密钥 / fallback**
- mlx-serve：忽略遗留的 `PAGE_REVIEW_MAIN_B_API_KEY`，固定 `local-product`，除非新增单独的本地密钥变量。
- 产品 `require_page_reader_routes` 对两主读强制 `fallback_base_url=""`，或配置了 fallback 则启动失败。不要只靠默认空串。

**P1 — 混合输入缩小（只提案）**
保持「无已采信观察 → 不打模型」。按页拆 call：仅含未采信/舍弃的页走 `preserve-pending/v1`；仅含已采信（可带**本页** pending 以解释缺口）的页再进模型。模型 call 中：
- 保留该页 `accepted_observations`、冲突、本页 pending（`use=unresolved_only`）、对应 locators、以及 pending 锚点所需 sidecar；
- 去掉其他未核实/已舍弃页的全文 `ocr_sidecar_pages`；
- 不要从 pending 或语义对应关系自动采信。

**P2 — 正式入口**
孤立脚本在 201 之后断言 payload.routes：main-A `glm-5.3-flash` + `low`，main-B `mlx-serve` + 精确 ddalcu 模型。接线单测若声称覆盖产品路径，应经 HTTP command 服务，而不是只插入 MiniMax fixture。

**不要做**
- 不要自动跑旧页级/辅助/规范化 job。
- 不要把缺失 NCS/研究者判断写成合格或「请确认缺失」。
- 不要把 OCR/其他应用强行并进本闸，除非 Codex 把范围内本地调用定义为包含 OCR。

### 4. Uncertainty

- 未观察真实 mlx-serve 对 `reasoning_effort=high` 的处理；`direct_openai_completion` 会发送该字段（`harness.py:452-456`）。若服务端拒未知参数，MAIN_B 会失败且无模型 fallback。这是环境问题，不是已证代码 bug。
- 未读 `.env`，不知道现场是否仍有 `PAGE_REVIEW_MAIN_B_PROVIDER=cms-smk`、`PAGE_REVIEW_MAIN_B_API_KEY` 或 `*_FALLBACK_BASE_URL`。
- 未读运行库，不知道源孤立 runtime 的 coverage 是否已是 `r3-page-review-job/v7`。若旧 coverage 版本更老，选择器会滤掉它们，P0 碰撞不会发生。
- 有 page_review 时丢掉 `collect_visual_observation_attachments` 可能是有意用页级读替代视觉 sidecar；pending-only 页因此没有视觉附件。是否可接受需 Codex 定。
- pending-only 的 unresolved 只有 `affected_pages`，没有 `page_artifact_id`/`coverage_id`。原始页级记录仍在库里。是否要在 unresolved 上加定位器，属保全完整性问题，不是已证丢失。

### 5. Objections / 决策点 / 给 Codex 的有界问题

**异议**
- 「新 job 幂等已含 routes，旧任务不会被跑」为真，但**不够**：规范化消费的是 coverage 行，不是 job_id。换本地主读后，用户完成新双主读仍可能无法整理。
- 「孤立脚本用了产品 API」为真，但复制整库 + 要求 201 + 无 predecessor，正好踩中上述产品缺口。不能把它当成已验证的规范化产品路径。
- 接线测试用 MiniMax fixture 不能证明新本地主读已接到规范化。

**决策点（需 Codex，本角色不拍板）**
1. 换路由后的当前 coverage：按当前路由过滤，还是强制 predecessor 重读？
2. 辅助复核：换路由是否允许新任务，还是整段冻结直到人工清幂等？
3. mlx-serve 是否允许任何非空 API key？
4. 混合页组：拆 call（推荐）还是仅压缩 sidecar、保持同一 call？

**有界问题**
1. 目标孤立源库里的已完成页级 coverage，`execution_versions.contract` 是否已是 `r3-page-review-job/v7`？若是，P0 会在 `--normalize` 实打实出现。
2. 现场 `.env` 是否仍设置 `PAGE_REVIEW_MAIN_B_FALLBACK_BASE_URL` 或云端 `PAGE_REVIEW_MAIN_B_API_KEY`？（不要把密钥值发进会议。）
3. 「跨本地串行」是否包含本产品 OCR/方案解构，还是仅页级三道？

**安全暂定路径**：在 Codex 回答前，不要把换路由后的 coverage 自动选为规范化输入；不要跑历史 job；无已采信观察时保持 `preserve-pending/v1`、不打模型。辅助复核在路由变化后应视为未就绪，而不是复用旧 MiniMax 任务。
