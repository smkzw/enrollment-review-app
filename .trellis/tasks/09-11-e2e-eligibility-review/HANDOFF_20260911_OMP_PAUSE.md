# 无损暂停记录：2026-09-11 OMP 接管会话（用户指令：无损暂停，做好任务记录）

更新时间：2026-09-11 17:25 CST。状态：用户明确要求无损暂停。本文是本会话的首要恢复入口。恢复实施需用户明确指令。

## 0. 接任者先读：本会话改变了什么、没改变什么

1. **本会话是 09-10 ZCode 接管线程（TASK_PLAN_0004）之后的第二个接管会话（OMP）**。ZCode 线程已留下 6 个提交（383fd08→0b6ea2c：判断检索五层接线、术语统一、入排工作台、报告打印页、占位路由清除）与子任务 `09-11-e2e-eligibility-review`（含用户裁决与双审阅冻结方案 v2）。本会话核实并接受了该基线（用户选择"逐项复核后再定"时本会话已完成核验：裁决内容与用户历次要求一致、提交实测通过）。
2. **本会话新增 3 个提交**（在 0b6ea2c 之上）：`24a8c77` 冲突组链头解析、`eaa428d` 判断检索 P0 修复。**发现并修复了产品级 P0 bug**（详见 §2）。
3. **发现 ZCode 线程遗留的 P0 bug 并已修复**：判断检索执行器 completion 包装签名错误导致所有真实模型调用必然失败。此前从未有真实判断检索成功运行——包括 09-10 交接文档记录的所有"小样"（那些走的是 scripts 探针路径，绕过了执行器包装）。
4. 没有改动：未提交的 19k+ 未跟踪文件原样保留；runtime05 历史运行只读；用药隔离试验未动；Phase5/5.5 claims_complete 仍为 false。

## 1. 现场快照（恢复核对用）

- 分支：`codex/phase5-clinical-facts-profile`，HEAD = `eaa428d`（fix(judgment-search): completion wrapper must honor 3-arg protocol）
- 提交链（本会话视角）：383fd08 → d7f52dc → 444e121 → af45ac3 → 56bc5b8 → 0b6ea2c → 24a8c77（本会话）→ eaa428d（本会话）
- 测试基线（本会话实测）：后端全量 tests/v2 = **4627 通过 / 0 失败 / 3 跳过**（22:52min）；前端 vitest = **564/564**；判断检索聚焦 = 64/64（含新增接线契约测试）。
- `.env` 未改动（变量名清单已核对：GLM Coding Plan、Gemini OAuth、CMS_SMK 等，值未输出）。
- 双读道路由实测：main-A = zhipu-coding-plan / glm-5.3-flash / low / 65536；main-B = google-antigravity / gemini-3.7-flash / high / 65536。

## 2. P0 根因与修复（本会话核心工程产出）

**现象**：runtime06（`artifacts/phase55-takeover/20260911/glm-gemini-runtime-06-judgment-search/`）首次真实入队判断检索作业 `e7327bec`：49 步全部 completed 但 48/48 读步 checkpoint 为 `page_failure{transport}`、`response_attempts=[]`、零回执工件；7 条要求摘要全部 `coverage_incomplete`、`missing_lanes=[main-A, main-B]`。

**根因**（直接调用执行器复现拿到原始 traceback）：`app/services/judgment_search_job_executor.py` 的 `recorded_completion(messages, max_tokens)` 是 2 参签名；读器 `read_judgment_search_page_batch` 按 `Completion` 协议（`app/llm/page_review_harness.py:121-123`）以 `completion(route, messages, max_tokens)` 3 参调用。TypeError 在进入函数体前抛出 → 被读器 456-466/657-667 行包装为 `failure_kind="transport"` → 执行器按可重试失败重试 2 次后落页级失败检查点（`PreparedStepResult` 成功语义）→ 步骤“完成”但零回执。单元测试全绿是因为测试假件同样用 3 参签名直接测读器，从未覆盖执行器包装层（全仓 grep 证实 `JudgmentSearchJobExecutor` 零测试引用）。

**修复**：`eaa428d`——包装改 3 参 `(route, messages, max_tokens)`；新增 `tests/v2/services/test_judgment_search_job_executor_wiring.py` 按真实调用形状锁定协议。

**验证**：修复后 runtime06b（`artifacts/phase55-takeover/20260911/glm-gemini-runtime-06b-judgment-search-fixed/`）真实作业 `dcf6786e`：49/49 步 completed、**47/48 读步带回执**、7 条要求中 6 条 `candidates_present`（含 p8 手写"CS 肝功能不全"、p3 手写"与研究病相关"等真实候选）、1 条诚实保留 `coverage_incomplete`（EX-16:01，对应那 1 页级失败读道）。**这是项目首个端到端成功的真实判断检索运行。**

**遗留观察（恢复后处理）**：
- 47/48 的那 1 步页级失败原因待查（06b 库 `job_checkpoints` 中 `page_failure` 条目）；
- 06 首跑（bug 版）与 06b（修复版）两个目录都保留为失败/成功证据，不删除；
- 本会话重复跑了一次真实作业（bg_9 实际已完成但收尾报告崩溃被误判为未跑、清库重启 bg_1）——多消耗一轮真实额度，已在 runner 修复 `jobs_models`→`models` import，恢复者勿重蹈：**先查作业终态再决定是否重跑**。

## 3. 本会话完成的接管审查结论（已验证的事实）

1. 09-10 交接文档的"P1-A 判断检索未接线"已被 ZCode 线程解决（五层证据：API 四端点/持久任务/执行器/0022 迁移/前端卡片）；但**接线从未真实跑通过**（上述 P0），本会话补上了这一环。
2. ZCode 审查的 P1-B（启动入口）已解决：`scripts/start_enrollment_review.command` 含 worktree 显式 env 合同。
3. 后端/前端全量零失败（本会话实测，见 §1）。
4. 新登记工程问题（未处理，恢复后按用户裁决"Slice 5 验收后专项"）：legacy v1 栈未退役（app/main.py+pipeline+router）；`app/authz.py:19` 硬编码口令回退（legacy）；`gemini_oauth.py` 绕过 config 直接读 os.environ；巨型文件（protocol_deconstructor 4766 行等）；`judgment_search_artifacts.py:46-48` 跨模块导入私有符号；`config.py:120` import 时副作用。

## 4. 恢复步骤（按序执行）

1. 只读核对：HEAD=eaa428d、§1 测试基线、`.env` 变量名、runtime06/06b 两个目录与 §2 数字一致。
2. Slice 5 剩余工作：
   a. 查 06b 那 1 步页级失败的原因（重试是否可解决）；
   b. **三档视口（1080P/2K/4K）真实浏览器验收**：对 06b 数据起正式服务（`app/api/v2/app:create_app`，数据根指向 06b 目录），走 方案工作台→受试者与资料→档案（书面判断检索卡+待办汇总卡）→入排工作台→报告打印 全流程；验收标准见 `09-11` 任务 PRD §验收标准；
   c. 判断检索卡在真实数据上的中文呈现核对（候选摘录→原件页跳转）。
3. 然后按 `09-11` PRD：独立会商审阅冻结结果 → Phase 5 收口建议（不自行改 claims_complete）。
4. 更新 `docs/PROJECT_CONTEXT.md`（本会话未及写入，恢复时补：P0 修复、runtime06/06b、测试基线）。

## 5. 边界（不变，接任者勿越）

- 产品仅 GLM-5.3-Flash low + Gemini-3.7-Flash high 直连；用药分项自动采信保持隔离；不迁移 harness；广泛横评后置。
- runtime05/06/06b 均为隔离受控实例，clinical_acceptance=false；06b 的 candidates_present 只是检索候选，不是临床判断。
- 不 reset、不 clean、不删失败证据（06 目录是 P0 的失败证据，必须保留）。
- 后续真实模型调用前先查库中作业终态，避免重复消费额度。

## 6. 本会话工件索引

- P0 失败证据：`artifacts/phase55-takeover/20260911/glm-gemini-runtime-06-judgment-search/`（job e7327bec，48/48 假 transport 失败）
- 修复后成功证据：`artifacts/phase55-takeover/20260911/glm-gemini-runtime-06b-judgment-search-fixed/`（job dcf6786e，6/7 candidates_present + 1 诚实 coverage_incomplete）
- 受控 runner（两目录内 `runner.py`，06b 版含 models import 修复）
- 新测试：`tests/v2/services/test_judgment_search_job_executor_wiring.py`
- ZCode 线程审查（背景）：`.trellis/tasks/09-05-phase55-dual-vlm-page-review/ENGINEERING_REVIEW_20260910_ZCODE_TAKEOVER.md`
- 当前任务：`.trellis/tasks/09-11-e2e-eligibility-review/`（PRD + plans/SLICE_4_6_BUILD_PLAN.md v2 冻结版）
