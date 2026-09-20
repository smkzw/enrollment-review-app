I'll start by reading the assigned read set and acknowledging Trellis SessionStart context, then conduct the bounded review.

Trellis SessionStart ✓

Let me read the initial read set.

Bash is denied in this session; I'll continue with read-only source tools.

# Conference Output: enrollment-reading-recovery-prefix-20260916 - evidence_single_object

## Output

**Role**: `evidence_single_object` · 只读审阅 · 未编辑任何产品文件 · 未写 runner 报告路径 · 未调用模型 · 未读原始临床资料 · 未跑测试
**Verdict**: **REVISE**（默认路由下阅读方向变更后继**不可用** = F-1；方向修正的产品入口与请求语义仍未闭环 = F-3/F-4）
**Source scope**: initial read set 全部 12 个文件 + 直接相邻消费者：`app/evidence/reading_view.py`、`app/evidence/artifacts.py`、`app/projections/page_review_prompt_pack.py`、`app/llm/page_review_format_repair.py`、`app/llm/page_review_transport_options.py`、`app/llm/page_reader_capabilities.py`、`app/llm/gemini_transport.py`、`app/llm/page_review_batch_experiment.py`、`app/llm/page_review_context_layout.py`、`app/services/page_review_coverage_selection.py`、`app/services/page_review_status.py`、`app/services/page_review_runtime.py`、`app/api/v2/page_review.py`、`app/services/evidence_app_errors.py`、`app/config.py`（页面判读路由默认值）、`scripts/r3_page_diagnostic.py`、`frontend/src/api/page-review/pageReviewHttp.ts`、以及 `tests/` 与 `artifacts/` 中 v12 版 `page_review_harness.py` 归档快照（用于核对"重排前"的真实形状，避免凭记忆断言）。
**标签**：`FACT` = 我在该行读到 · `INFER` = 我的推导 · `REC` = 建议 · `UNCERT` = 本次不可证实。

### 工具与证据失败（不隐藏）

- **Bash 在本会话被拒**（non-interactive，权限不可用）→ 本次**没有运行 pytest / ruff / mypy / git diff**。所有"已验证"均为**源码路径贯通核验**，不是运行证据；涉及测试的结论我明确标注为"按表达式可判定 KeyError/断言不符"，未实跑。
- 我读了同题历史会议产物（`runs/conference/enrollment-reading-view-integration-20260916/`、`enrollment-reading-view-review-20260916/`）**仅作上下文**，每条引用都已重新对当前源码核验；下文凡与旧结论重合者都标为"延续"并说明新增部分。
- 本次作为"重排前基线"的证据是**仓内归档快照** `artifacts/phase55-takeover/20260909/glm-gemini-product-runtime-05-verified-64k/product-code/llm/page_review_harness.py`（`PAGE_REVIEW_PROMPT_VERSION = "page-review-r3/v12"`，`:55`）与 `artifacts/phase55-model-comparison/20260907/product-runtime-v8-20260908/...`（v11）。它们是**归档副本、非权威**，但足以证明"内容部件顺序"与"prompt 键顺序"在 v12 时的真实值。

---

## A. 实质缺陷（新的，按影响排序）

### F-1（BLOCKING for the direction-change path on the default config · VERIFIED-BY-SOURCE）方向变更后继在默认 mtplx 读道下**必然 409**，且失败原因被误报为"记录与资料不一致"

`plan_page_reread` 复用未变页回执时，把记录的 `prompt_version` 与**不带传输后缀**的 `payload["main_prompt_version"]` 做等值比较：

- `FACT` `app/services/page_review_recovery.py:84-86`：
  `"prompt_version": payload["main_prompt_version"]` → `if record.lane.value != lane or any(getattr(record, key) != val ...): raise PageRereadNotReady("已完成的主读记录与当前资料不一致，不能复用")`。
- `FACT` `app/services/page_review_job_service.py:45`：`"main_prompt_version": PAGE_REVIEW_PROMPT_VERSION`（`"page-review-r3/v20"`，无后缀）。
- `FACT` 落库值**带后缀**：`app/llm/page_review_harness.py:786-788` `prompt_version = PAGE_REVIEW_PROMPT_VERSION; if result.transport_contract: prompt_version += ":" + result.transport_contract`；`app/llm/page_review_transport_options.py:11-16,19-52`：`mtplx`/`omlx` 会带 `response_format` → `transport_contract` 非空 → 实存 `"page-review-r3/v20:mtplx-schema-mtp-conditional-validation-v3"`。
- `FACT` **产品默认 main-B 就是 mtplx**：`app/config.py:218-219` `PAGE_REVIEW_MAIN_B_PROVIDER` 默认 `"mtplx"`，base_url 默认 `http://127.0.0.1:8002/v1`（`:221-224`）。
- `FACT` 同一仓里另一处消费者**明确期待带后缀的形状**：`app/services/page_review_coverage_selection.py:79-82` `expected_prompt = PAGE_REVIEW_PROMPT_VERSION + (":" + transport if transport else "")`，并把它当作"处理方式未变"的接受条件。两处约定互相矛盾。

**反例（具体、可判定）**：三页任务，main-B=mtplx（默认），三页双读全部成功；操作者把第 2 页方向 90°→180°。第 1、3 页方向未变 → 进入复用分支 → 第 1 页 main-B 记录 `page_review_version` 带 `:mtplx-...` 后缀 → 与 `"page-review-r3/v20"` 不等 → `PageRereadNotReady`（409，`PAGE_REREAD_NOT_READY`），提示"已完成的主读记录与当前资料不一致，不能复用"。**没有任何记录真的不一致**，方向修正被完全挡在门外；单页任务不受影响（changed_pages 覆盖全页 → 不走复用）。已存在的覆盖测试只覆盖"云端/无后缀"读道（`tests/v2/api/test_page_review.py:236-274` 用的是自造 provider），所以这条路径至今无声。

**最小修复（1 处）**：在 `page_review_recovery.py` 里改为按**基础版本**比较，或复用规范化器同一表达式，例如
`expected = payload["main_prompt_version"]; ... if record.prompt_version.split(":", 1)[0] != expected: raise ...`
（`split` 版本最稳，因为 `generation_mode` 由 `page_transport_contract(provider, generation_mode=...)` 决定，恢复侧不应猜；另一可选写法是按 `record.provider` 求 `page_transport_contract(record.provider)` 后拼接，与 `coverage_selection` 完全一致。）

### F-2（MEDIUM-HIGH · VERIFIED-BY-SOURCE）内容部件顺序由 `[image, text]` 翻转为 `[text, image]`，产品消费者安全，但**测试侧的位置断言未迁移**（本区域当前没有可信回归网）

- `FACT` 重排前基线（归档 v12 快照 `:423-426`）：`"content": [{"type":"image_url"...},{"type":"text"...}]`；v11 快照 `:430-432` 同形。
- `FACT` 当前：`app/llm/page_review_harness.py:519-522` 改为 `[{"type":"text"...},{"type":"image_url"...}]`。
- `FACT` **产品代码没有位置假设**（我对全仓 `content"]["<n>"]` 做了穷举式搜索，命中全在 `tests/`）：`read_page` 用 `part["type"]=="text"` 过滤（`:676-683`）、`store_page_request` 遍历全部部件（`page_request_receipt.py:11-32`）、`page_completion_options` 扫描找 `output_schema`（`:27-43`）、`gemini_transport.build_gemini_request` 按顺序映射部件（`:82-94`，text→inlineData 合法）、`page_review_batch_experiment` 按类型拆分（`:117-124`）。→ **对产品运行路径无破坏**。
- `FACT` 测试侧仍有 ≥6 处按**旧位置**取值（按表达式即可判定 KeyError）：`tests/v2/llm/test_page_review_harness.py:111`、`:246`、`:468`（`build_page_review_messages(...)[1]["content"][1]["text"]`）；`tests/v2/llm/test_targeted_page_review.py:73-74`、`:101`（`seen[0][1]["content"][1]["text"]`，`seen` 来自 `read_page` 回调）；`tests/v2/llm/test_page_review_format_repair.py:116-117`（`calls[0][1]["content"][0]["image_url"]`）；`tests/test_page_review_batch_experiment.py:195`；`tests/v2/services/test_conflict_reread_experiment.py:12`；`tests/v2/llm/test_gemini_transport.py:248`。
- `FACT`（削弱/加重并存）：同两个文件里还有**与当前代码不符的版本字面量**——`test_page_review_harness.py:481` 断言 `"page-review-r3/v13"`（现为 v20）、`test_targeted_page_review.py:72` 断言 `"page-targeted-review/v4:"`（现为 v5）。这说明这批测试**在本次重排之前就已不是绿的**，因此"重排导致 CI 变红"我不能断言（`UNCERT`）；但由此也可确认：**v20 重排是在没有任何可用回归信号的情况下落地的**。
- **REC**：把上述表达式改为按 `part["type"]` 选点（与产品代码一致），并同步修版本字面量；若 Codex 想把本区域纳入验收门禁，应先跑一次 `tests/v2/llm/test_page_review_harness.py`、`test_page_review_format_repair.py`、`test_targeted_page_review.py`、`test_page_request_receipt.py`、`tests/test_page_review_batch_experiment.py` 并公开结果。

### F-3（MEDIUM · VERIFIED-BY-SOURCE）新能力在**产品入口上不可达**：`can_reread` 与前端解码器共同把"干净任务的方向修正"锁死

- `FACT` 服务端：`app/services/page_review_status.py:36-51` → `status = "needs_reread" if failed else "ready"`，`can_reread = status == "needs_reread" and not exhausted`。**无失败页 ⇒ `can_reread=false`**。
- `FACT` 前端：`frontend/src/api/page-review/pageReviewHttp.ts:78-81` 提交体只可能是 `{predecessor_job_id}` 或 `{}`，**从不发送 `reading_rotations`**；`:46-49` 解码器还强制 `canReread ⇒ status === "needs_reread"`，否则 `throw new PageReviewApiError()`。即"让服务端在 ready 上报 can_reread=true"这条捷径会直接触发前端异常。
- 与旧轮次的差别（**不是重复**）：旧轮次指出的是"前端零命中 `reading_rotations`"；本轮新增的是**服务端状态门 + 前端解码硬不变量**这两道独立关卡，即使后端已支持"无失败页的方向修正"（`page_review_recovery.py:62-63`、`app/storage/page_review_repository.py:297-299` 已放宽），产品也**无法表达**该动作。
- **REC（二选一，需 Codex 裁定）**：(a) 新增独立能力位（例如 `can_correct_direction`）与页面方向控件，提交时发送**完整** `reading_rotations`；或 (b) 明确宣布本阶段为"运维/API 专用"，并在 UI 与 409 文案里写明理由，同时按 `AGENTS.md` 把"方向未经确认"落成具名缺口（责任人/动作/可接受证据/到期阶段），不能默认 0°。

### F-4（MEDIUM · VERIFIED-BY-SOURCE，本轮新引入的语义）`reading_rotations` 的"缺项"被同时当作两种含义：**未变更（复用）** 与 **清除（改为不旋转）**

- `FACT` `app/services/page_review_recovery.py:37-40`：`old_rotations.get(page_id) != new_rotations.get(page_id)`，字典缺项即 `None`，因此"新映射没写这页"= 方向变更。
- `FACT` API 只接受 `90/180/270`（`app/api/v2/page_review.py:22`；`app/services/page_review_job_service.py:128-131`），**没有 0/None 哨兵**；于是"清除旋转"只能用缺项表达，与"不关心该页"不可区分。
- **反例**：旧覆盖率 `{p1:90, p2:90}`；调用方本意"把 p2 改成 180"，请求体只写 `{p2:180}` → p1 被判为方向变更 → 双读重跑 p1（此时 `view=None`，模型看到**未旋转原图**）→ 新覆盖率 `reading_rotations={p2:180}`，旧覆盖率被 supersede。结果：一个未被操作者意图覆盖的页面，其阅读依据被**静默改变**，而 `AGENTS.md` 要求"later-stage evidence must not silently rewrite an earlier-stage result"。
- 旧轮次无法出现此形态（当时任何方向差异都被整体拒绝），故属本轮**新增**风险。
- **最小修复**：在入队处拒绝歧义请求——要求 `set(reading_rotations)` ⊇ `{旧方向非空的页}`（即必须回显未变页），并为"清除"提供显式哨兵（如允许 `0` 表示取消旋转、或用独立字段 `clear_reading_rotation_pages`）。若不接受新哨兵，退而求其次：缺项一律视为"沿用前次"，本轮不支持清除（并在文档/前端说明）。

### F-5（LOW-MEDIUM · VERIFIED）同一前次可派生**两个后继**，冲突直到"整理个例档案"才以误导文案爆出

- `FACT` 幂等键 `canonical_hash(payload)` 内含 `recovery`（`app/services/page_review_job_service.py:187`），方向不同 → 键不同 → 两个后继都可成功创建；两者 `predecessor_coverage_id` 都指向 P。
- `FACT` `app/services/page_review_coverage_selection.py:43-65`：`superseded` 只收"直接前驱"，P 被淘汰后剩 S1、S2 → `len(candidates) != 1` → 409 `PAGE_COVERAGE_NOT_READY`"当前资料没有唯一可用的判读结果，请核对资料处理记录。" 文案把原因指向"资料处理记录"，与真实原因（两条后继竞争）无关。
- **REC**：同一 `predecessor_coverage_id` 的第二个后继应在入队即以明确文案冲突（或把继承链改为"后继的后继"，让最新覆盖自然唯一）。

### F-6（LOW · VERIFIED）复用回执把**前次任务**的 `response_attempts` 原样带入后继任务的身份字段

- `FACT` `app/services/page_review_recovery.py:87` 直接复用 `value`（前次 read 检查点）；`app/services/page_review_job_executor.py:60-64` 原样作为后继检查点返回。
- `FACT` 失败尝试回执里含 `"job_id": context.job_id, "step_id": context.step_id`（`page_review_job_executor.py:130-145`）→ 若前次该道曾失败后重试成功，后继任务的 `read:{i}:{lane}` 检查点会携带**属于前次 job** 的 job_id/step_id；`scripts/audit_page_schema_failures.py:34` 正是读这组字段做审计。
- **REC**：复用时剔除或改写这两个字段（或补 `reused_from_job_id`），保持"检查点身份 = 所属任务"。

### F-7（LOW · VERIFIED，相邻实验消费者）存量"稳定前缀"实验在 v20 之后变成**与默认完全一致的对照**，继续跑比较会得到无效结论

- `FACT` `app/llm/page_review_context_layout.py:13-24` 的 `stable_prefix_messages` 做两件事：把 `clause_pack/output_schema` 提到最前、把 text 部件排到 image 之前。当前默认（`page_review_harness.py:488-500,519-522`）**已经就是这两个顺序**，且两处 `json.dumps(..., separators=(",",":"))` 参数一致 → 变换后字节相同，`LAYOUT_VERSION="stable-prefix/v1"` 变体与基线内容无差异（记录身份因 `prompt_version + "+" + layout_version` 仍不同）。
- 消费方：`artifacts/**/runner.py` 的变体运行器与 `tests/test_page_review_context_layout.py`。
- **REC**：若仍需该对照，实验必须显式构造**旧顺序基线**（image 先、clause_pack 后），否则任何"stable-prefix 优于默认"的结论不可采信。

---

## B. 已验证正确（回归锚点，避免 Codex 重复排查）

| # | 结论 | 证据 |
|---|---|---|
| G-1 | **方向变更强制双读重跑**：changed 页 `continue`，既不复用两道回执也不复用 reconcile；engine 只保留"有失败道"的页 | `page_review_recovery.py:39-40,68-71,88-89`；`page_review_job_executor.py:167-199` |
| G-2 | **未变页仍受来源/版本约束**：`binding` 含 page_artifact_id / source_document_version_id / page_number / page_image_sha256 / clause_pack_id / clause_pack_sha256 / contract_version，且经仓储 `_verify_page` 与 PageArtifact 行二次核对 | `page_review_recovery.py:76-86`；`page_review_repository.py:58-73,134` |
| G-3 | **无关来源/配置变化不能 supersede**：`comparable != payload(-reading_rotations)` 逐键全等（含 authority/pages/clause_pack/review_context/association_sources/routes/execution_versions），覆盖率侧再比 8 个来源字段 | `page_review_recovery.py:33-42`；`page_review_repository.py:285-299`；已被 `tests/v2/api/test_page_review.py:218-235` 覆盖 |
| G-4 | **"无失败页 + 方向变更"两侧同时放宽**（本轮 V-2 的服务端修复确实到位） | `page_review_recovery.py:62-63`；`page_review_repository.py:297-299` |
| G-5 | **谱系使旧结果非当前**：直接前驱集合被淘汰，含环与断链检测；淘汰先于"失败终局不算候选"的过滤，失败后继不会复活父覆盖 | `page_review_coverage_selection.py:44-65`；`tests/v2/api/test_page_review.py:269-279`（规范化器最终取到新 coverage_id） |
| G-6 | **旧轮 V-1 修复确实落地**：派生工件类别 `reading_view_image` 已加入白名单；执行器落盘视图字节；回执 v2 按 `reading_view.image_sha256` 复核并记录 `(kind, sha)` | `app/evidence/artifacts.py:21`；`page_review_job_executor.py:100-106`；`page_request_receipt.py:24-35` |
| G-7 | **v20 重排按目标形状落地**：`clause_pack` → `output_schema` → `page_artifact_id/page_number/image_coordinates/(reading_view)/(review_context)`；对照 v12 归档快照（`:410-417`：page_artifact_id, page_number, review_context, clause_pack, output_schema）**没有任何既有键被删除**，反而新增了 `image_coordinates`/`reading_view` | `page_review_harness.py:488-500`；`artifacts/.../page_review_harness.py:410-417` |
| G-8 | **定向复核与格式纠正不受重排影响**：两者都按 `part["type"]` 定位、`pop("clause_pack")` 与 `maxItems` 语义与 v12 完全一致；纠正消息仍追加为最后一条（`messages[-1]` 即纠正说明） | `page_review_harness.py:676-690` vs 归档 v12 `:548-555`；`page_review_format_repair.py:205-220`；`page_review_harness.py:794-798` |
| G-9 | **源/视图框一致**：schema `maximum` 按**视图**尺寸钳制、`evaluate(...image_size=视图尺寸)` 越界即拒、`source_bbox` 反演回原页、记录级再按 `reading_view.source_*` 复检 | `page_review_harness.py:414-423,781-784`；`page_review_format_repair.py:137-148`；`app/domain/contracts/page_review.py:292-306` |

---

## C. 我最重要的反对意见（面向 Codex）

1. **反对把"方向修正后继"记为已交付**。默认 main-B 就是 mtplx（`app/config.py:218-219`），而 F-1 使"多页任务的任何方向变更"在入队即 409，且文案把矛头指向"记录不一致"。这是**本轮标题能力的阻塞项**，应先修 F-1 再谈验收；否则任何"已支持方向修正"的表述不成立。
2. **反对在 F-4 未裁定前开放"部分映射"**。`{p2:180}` 与 `{p1:90,p2:180}` 现在语义不同，且前者会**静默取消 p1 的旋转并重跑双读**。这是"后期结果静默改写早期依据"的具体形态，不是文档问题。
3. **反对以"产品代码无位置消费者"收尾 F-2**。结论对**产品**成立（我已穷举），但本区域的测试表达式与版本字面量都已过期（v13/v4），意味着 v20 重排**没有可用的回归信号**；若 Codex 以"测试未变红"支撑"无回归"，该论据不成立。
4. **提醒一个被"能力已实现"掩盖的入口问题（F-3）**：服务端放宽了 `_verify_coverage_scope` / `plan_page_reread`，但 `can_reread` 与前端解码器把路封住，等于能力只对直接调 API 的人可见。
5. **不重复但要点明**：`coordinate_space` 同时标注两组像素尺寸（`image_coordinates` 用视图尺寸、`reading_view` 用源尺寸，`page_review_harness.py:495-497` + `app/domain/contracts/reading_view.py:10-11`）仍是**上一轮遗留**（旧 V-4）；本轮我把 `image_coordinates` 与 `reading_view` 排到相邻位置，但**没有**改变该歧义，也未新增证据，故不作为本轮发现，仅列为未闭环项。

---

## D. 决策点与有界问题（可在同会话内回答）

| # | 决策 | 我的建议 |
|---|---|---|
| D1 | F-1 修法：`split(":",1)[0]` 比较 vs 按 `page_transport_contract(provider)` 复算后缀 | 用 `split` 比较 + 注释说明后缀来源；两者都应与 `coverage_selection.py:79-82` 收敛到同一个 helper，避免第三处分叉 |
| D2 | F-3 方向修正是否为**产品支持动作** | 若"是"：加 `can_correct_direction` + 方向控件 + 完整映射提交；若"否"：改 409/UI 文案并登记"方向未经确认"缺口 |
| D3 | F-4：方向映射的完整性强约束 vs 显式清除哨兵 | **要求回显全部旧方向非空页**，并允许显式 `0`/`clear_pages` 表达清除；缺项不再等价于清除 |
| D4 | F-5：同前驱双后继 | 入队冲突（推荐，文案明确）或线性化 supersede |
| D5 | F-7：`stable_prefix_messages` 是否保留 | 保留但显式构造旧顺序基线；否则删除该变体以免产出无效比较 |
| D6 | D-审查门禁 | 是否把 `tests/v2/llm/test_page_review_harness.py`、`test_page_review_format_repair.py`、`test_targeted_page_review.py` 的迁移纳入本轮收尾 |

**有界问题**
1. （F-1）修复可用 1 行 `split`，是否授权一次性最小补丁？我未改任何文件。
2. （F-4）"清除旋转"是否必须是受支持动作？若不是，是否接受"缺项=沿用"并在本轮禁用清除？
3. （F-2）本区域测试的过期是"已知待迁移"还是"未知漂移"？这决定我要不要在同会话内给出逐行迁移清单。
4. （F-5/F-6）覆盖率谱系与检查点身份是否属于本轮验收范围？若否，请明确写入 out-of-scope，以免我下次重复排查。

---

## E. 不确定性与边界

- **未做**：未运行任何测试/lint/type-check（Bash 被拒）、未 `git diff`（无法确认哪些改动属于本轮）、未调用模型、未读工作区外临床资料、未写 runner 报告路径、未编辑产品文件。
- **F-1 为源码路径贯通核验**：后缀链每一环都有行号，但**没有运行复现**（`UNCERT`：实际 env 是否覆盖 `PAGE_REVIEW_MAIN_B_PROVIDER`；若现场把 main-B 换成 gemini/cms-smk，则 F-1 只在 main-A 为 mtplx/omlx 时触发）。
- **F-2 的判断是"按表达式可判定"**：我把 `content[n]` 的类型与断言表达式逐条对上，但未执行 pytest；且该批测试另有两处版本字面量不匹配，故"之前是否绿"`UNCERT`。
- **明确不作为结论**：共享前缀带来的**速度/缓存收益**我未做任何验证，也不主张（按任务要求）；我只指出 `output_schema` 内嵌**逐页变化**的 bbox `maximum`（`page_review_harness.py:421-423`），因此当页尺寸/旋转不同时共享前缀会在 `output_schema` 内部断开——`INFER`，若 Codex 的目标是最大化共享前缀，需自行裁定是否把尺寸移出稳定区（这与约束解码强度存在取舍）。
- **会议材料缺口**：`context/...conference_context.md:29-35` 与 `plans/codex_main_venue_...md:3-8,26,33` 仍是 TODO，没有 Codex 声明的 scope/out-of-scope 与验收标准；我的范围完全由本次 prompt 推断（阅读视图集成、方向变更后继、v20 重排）。
- 本文任何内容都**不构成**临床、监管、视觉、浏览器或生产验收；最终综合、裁定与交付仍归 Codex。
