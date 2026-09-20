# Conference Participant Output: r3-output-failure-review-20260906 - general_single_object

## Boundary Check

- 只读审阅完成：仅读取指定读集内的 8 个文件，及其直接依赖（`app/projections/clause_pack.py`、`app/projections/page_review_prompt_pack.py`、`app/domain/contracts/{common,evidence,clause_pack}.py`、`app/domain/page_normalization.py`、`app/services/page_review_execution.py`、`app/services/page_review_recovery.py`、`app/llm/page_review_admission.py`、`scripts/r3_page_diagnostic.py`、`scripts/audit_page_schema_failures.py`、`app/agents/protocol_deconstructor.py` 中 component_id 生成处的窄片段）。未打开 .env、数据库、病例原件、其他与会者输出或宿主配置；未发起新模型调用、网络或子进程委托；未写任何文件（含 runner 报告路径）。
- 模型与思考档保持 `GLM-5.3-Flash` / `max`，未切换。不声明任何临床、监管或最终验收权威；Codex 保留最终权威。
- 未验证项明示：我没有读取持久化的 usage、raw_response 或 replay JSON（数据边界）；以下对失败机理的判断来自代码事实 + Codex 冻结观察的交叉印证。

## Independent Work Product

### 结论先行

8 个 schema 失败可精确归入四个机理类别，且类别构成与冻结观察完全对账（A：4 个未知 clause_id + 1 个 target_text null + 1 个 bbox 缺 y1 + 1 个布尔矛盾页 = 7；B：1 个布尔矛盾页 = 1）。其中布尔矛盾页（has_eligibility_value=false 却输出 6/9 条 facts）是**A、B 两异源模型在同一页上的相关联系统性失败**，不是随机滑失，这是全部发现中影响最大的一条。最小可辩护路线是：**零代码的局部重读（R0）立即可用；若写代码，只做“失败触发的纠错重试”（R1），并把任何 prompt/预算/约束输出改动推迟到下一次有正当理由的整批运行**，否则会触发全量 24 页重跑。

### 排序发现（含代码位置）

**F1（P0，系统性）：布尔矛盾是双模型相关失败，纯文本提示补丁大概率无效**
- 合同：`app/domain/contracts/page_review.py:218-228`（`validate_empty_page`：has_eligibility_value ⇔ 任一观察非空）；对账层 `app/services/page_review_execution.py:125-139`（双 false 才 discard）。
- 提示词已**逐字写明**该规则：`app/llm/page_review_harness.py:391-393`（“任一非空时必须为 true；仅三者均为空时为 false”）。两个异源模型仍同页违反 → 失败根源是提示内部张力（“只报告相关内容/忠实摘录”的强指令 vs 布尔只表示“是否返回了观察”），两个模型一致地按语义判断填了 false。
- 推论一：给提示再补一句话（text patch）对该类别缺乏有效性证据——模型已经违反了明确指令；把校验器矛盾作为显式反馈的重试，条件化强度远高于重述规则。
- 推论二（设计层）：在该合同下 has_eligibility_value 是其余三字段的**100% 冗余函数**，它不携带任何信息，却贡献了一个失败类别。废止或代码规范化它不构成临床推断（合同已把它定义为恰为此函数），但 2026-09-05 设计明确“矛盾时拒绝，不自动翻转”（`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §7），这是用户已定决策，只能由用户重开。
- 推论三：A/B 系统提示逐字相同（测试锁定：`tests/v2/llm/test_page_review_harness.py:56-69`），双读的独立性是感知独立而非提示解释独立——同类 schema 错误在两道相关出现是设计内期望行为，“双异源”不能被当作该类别互为校验的证据。

**F2（P0）：未知 clause_id ×4——提示从未要求逐字复制，且条款包每条含 5 个形近 ID 字段**
- 门禁：`app/llm/page_review_harness.py:632-633`（未知 clause_id → schema 失败）。
- 生产身份格式：clause_id = rule_component_id = `component:{official_code}:{NN}`（`app/agents/protocol_deconstructor.py:2525`），display_code = official_code 或加 a/b 后缀（同文件 ：2390-2394）。模型输出 `component:IN-01`（缺尾段）、`component:EX-07:28:01`（多段）等“近似身份”。
- 代码侧确定性映射**不可行**：投影只保证 rule_component_id 唯一（`app/projections/clause_pack.py:103-107`），display_code 不保证唯一；`component:EX-07:28:01` 无唯一指涉。部分可映射、部分不可映射会造成两套修复语义——按边界不做任何静默改写。
- 提示侧缺口：输出 schema 对 clause_id 仅 min_length=1，系统提示没有“clause_id 必须逐字复制条款包对应字段”的指令；每条条款还同时下发 clause_id、rule_id、rule_component_id、official_code、display_code（且 clause_id 与 rule_component_id 恒等重复），低思考档的 A 更易综合近似值（A 4 例 / B 0 例与 effort 差异一致）。

**F3（P1）：bbox 缺 y1 与 target_text null——严格合同遇到提示歧义**
- `BoundingBox` 要求 x0/y0/x1/y1 四字段齐全（`app/domain/contracts/evidence.py:21-31`），`ObservationContext.target_text` min_length=1 永不可 null（`app/domain/contracts/page_review.py:57`）。
- 提示歧义实据：`page_review_harness.py:366-367`“看不清所指对象时 context 为 null”与 ：387-388“只有对象确实无法辨认时才为 null”——后句的 null 指涉对象在语法上可绑定到上一句的 target_text，模型按后者理解即产生 `target_text: null` → `:586-590` 处 string_type 失败。bbox 无任何“要么四值齐全、要么整体省略”的提示。
- 这两类是纯输出形状问题，原生约束输出（required/enum）可结构性消除（见 R2）。

**F4（P1）：B 道残余 2 例 length——“思考预算挤占输出预算”假说优先于任何加预算动作**
- 现行为：length 翻倍一次后仍截断即终态失败（`page_review_harness.py:547-554`；设计 §6 冻结“翻倍一次”）。
- 调用量对账：B 32 调用 = 24 道 + 8 次 length 重试；10 次 length 终结 = 8 次首试 + 2 次加倍后仍截断，加倍挽回率 6/8。B 在 24 页中 8 页（33%）触顶，而 A（low）24/24 全 stop——与“MiniMax high 的思考 token 计入 completion 预算”假说高度一致。**判定性验证零成本**：executor 已把每次尝试的 usage 记入 checkpoint（`app/services/page_review_job_executor.py:126-135`），离线比对 10 次 length 调用的 reasoning vs completion token 占比即可定案，无需任何新调用。
- 身份代价（Codex 要求澄清的预算含义）：`route_identity` 冻结 max_tokens（`app/services/page_review_job_service.py:58-63`），任何基础预算/端点/effort 变更都会改变 payload → `plan_page_reread` 比对失败（`app/services/page_review_recovery.py:26-31`）→ 22 个已成功 B 收据全部不可复用，强制 24 页全量重跑。run 内只读改道 `read_page` 内部第二次翻倍不破坏 payload 身份，但违反“翻倍一次”的冻结设计 → 用户决策。

**F5（P2，加固项）：handwriting 归一化调用未包 try（`page_review_harness.py:599-603`，对照 fact 路径 :591-598）**
- 当前 `handwriting_normalization_key` 全路径不抛出（`app/domain/page_normalization.py:154-159`），不可达缺陷；但若未来加校验会以 unexpected 而非 schema 类别炸步骤，绕过 `audit_page_schema_failures.py` 的 lane_failure 复放通道。低优先加固。

**F6（P2，治理约束）：任何“算法版本”变更的全量代价需要显式入账**
- 执行版本门禁（`page_review_job_executor.py:45-50`）+ payload 冻结（`page_review_job_service.py:101-115`）+ reread 可比性（`page_review_recovery.py:30-31`）三层叠加：改 `PAGE_REVIEW_PROMPT_VERSION` / `PAGE_REVIEW_JOB_CONTRACT` / 任何 route 字段 ⇒ 16 个已采信页收据不可复用 ⇒ 全量重跑。这正是“避免仅为算法版本全量重跑”约束的机制根源。

### 恢复路线（按最小性排序）

- **R0（今日可用，零代码）**：对已完成 job 走 `plan_page_reread` 后继任务——自动复用 ~40 个成功读道收据，仅重跑 8 个失败道（约 7×A≈37s + 3×B≈137s，受并发 2–3 约束）。失败重采样是全新抽样；布尔矛盾页有复发风险（相关失败），length 页按 B 历史 stop 率约 69–75% 概率通过。这是唯一不需要任何决策即可执行的路线。
- **R1（推荐的最小代码改进）：失败触发的 lawful 重试，基础身份完全不动**。在 `read_page` 内，schema 失败后追加**一个**用户轮次：附校验器的字段级错误 +（clause_id 类）有效 id 清单，要求重出完整 JSON；上限 1 次；两个响应与两次请求均已由 `recorded_completion`/`store_page_request` 无损留痕；失败则维持 lane_failure。关键优点：`page_review_execution_versions()` 与 payload 不变 → 已完成 16 页收据仍可复用，修复能力只作用于失败道。
  - R1 内部形态需 Codex 定夺：(a) 全文重出（简单，最终记录=模型新观察，两次响应都保留）vs (b) 受限结构修复（代码强制 diff：未被错误指涉的字段必须逐字节不变——保内容最强，但 diff 检查器本身是新风险面，且布尔类修复本质是让模型改判断而非改形状）。我倾向 (a) 起步：代码最小、无新检查器风险，且“修复输出形状”与“纠正临床内容”的边界由“两次响应都保留 + 记录身份含修复标记”保证可审计。
  - **R1 必须同步修一个隐藏坑**：若记录 prompt_version 带修复标记（如 `page-review-r3/v11+repair1`），`plan_page_reread` 的复用绑定按 `record.prompt_version == payload["main_prompt_version"]` 严格相等校验（`page_review_recovery.py:60-67`）会把修复恢复出的记录判为不可复用，未来二次恢复时这些道将被无谓重跑——绑定需显式接受基础版本的已声明修复变体。
- **R2（能力门控，不与本批绑定）**：原生约束输出（`direct_openai_completion` 现完全不传 response_format，`page_review_harness.py:436-446`）。若两个端点经合成探针验证支持 JSON schema 严格模式，可结构性消除 F2（enum clause_id）与 F3（required 字段）；**不能**修 F1（跨字段不变式）与 F4。能力未验证前不启用（约束原文要求 verified adapter capability）；探针需网络授权，本会话不可执行。
- **R3（推迟）**：B 专项基础预算/第二次翻倍/prompt 单行修订（clause_id 逐字复制、消除 ：387-388 null 指涉歧义、bbox 四值全有或全无）——全部是正确的改进，但全部触发版本/身份破坏。**时序硬约束：这些改动若在 8 页恢复之前落地，R0/R1 的局部恢复路径即被切断**。应先以冻结身份完成恢复，再把批量 prompt/合同改进搭下一次本来就有正当理由的整批运行（新修订/新条款包/新节点）。

### 输出形状修复 vs 临床内容修复的边界（Codex 要求显式区分）

- 形状类（F2/F3）：clause_id 逐字复制、bbox 补齐、target_text 改为可见对象原文或 context 整体置 null——重试反馈只提供“何为合法形状”，改写动作完全由模型执行，代码不做任何值级补写。
- 判定类（F1）：让模型在知道矛盾的前提下重新决定布尔，是模型自有的判定修正，不是代码翻转；代码侧唯一被禁止的是自动翻转（设计冻结）。丢弃 facts、改写摘录、映射 id 均不做。
- 全程无新增临床推断；无第三方读者；无两阶段新架构。

### 建议测试（R1 若采纳）

1. 四类失败各一个 fixture（按复放观测构造）：首试失败 → 修复轮含确切校验错误与有效 id 清单 → 成功后记录带修复标记；二次失败仍出 lane_failure。
2. 修复重试不被 endpoint/length/rate_limit 触发；targeted focus 路径默认不启用（其自有两轮边界）。
3. 身份黄金样：无修复的 v11 记录逐字段不变；带修复标记的同响应记录 page_review_id 必然不同。
4. payload 可比性回归：代码变更前后构建的 job，`plan_page_reread` 仍接受前者为前驱（execution_versions 不变）。
5. `page_review_recovery.py` 复用绑定接受修复变体（R1 隐藏坑的锁定测试）。
6. F1 回归锁：双 false + 非空观察 → failed_pending_reread，不得 discard、不得翻转（现合同已锁，防止未来松动）。

## Evidence And Assumptions

- 代码事实（已读源文件，行号见上文）：身份格式（`protocol_deconstructor.py:2525`）、合同严格性（`page_review.py:57,218-228`、`evidence.py:21-31`）、门禁与重试结构（`page_review_harness.py:547-633`）、恢复可比性与收据复用（`page_review_recovery.py`、`page_review_job_service.py:58-63`）、复放通道仅覆盖 lane_failure=schema 且只取末次尝试（`scripts/audit_page_schema_failures.py:30-35`）。
- Codex 冻结观察视为给定证据：8 schema + 2 残余 length；我做的算术对账（A 7 = 4+1+1+1；B 1；B 32 调 = 24 道 + 8 次 length 重试，10 次 length 终结 = 8 首试 + 2 加倍后）与全部观察自洽，构成佐证而非直接读取数据的证明。
- 假设（明示不确定性）：① MiniMax 思考 token 计入 completion 预算——未经数据验证，是 F4 所有建议的前提，须先做 V1；② 两端点不支持/未验证 response_format json_schema——未验证，故 R2 门控；③ “emit 6/9 facts” 理解为 A 6 条、B 9 条。

## Risks, Gaps, And Verification Needs

- **V1（决定 F4，只读、零成本）**：对 10 个 B length 尝试的持久化 usage 做 reasoning/completion token 占比分析（数据在 job_checkpoints + raw_response，Codex/所有者可执行）。若假说成立，加基础预算的边际收益低而身份代价高，结论完全不同。
- **V2（决定 R2，需网络授权）**：对两端点各发一次合成 response_format 探针（无病例数据），验证 JSON schema 严格模式与 enum/required 支持度；我无权执行。
- **V3**：用 `schema-failure-replay.json` 与本报告四分类做 1:1 对账确认（我按边界未读该产物）。
- 风险：R1 的修复轮在 B 上可能推高时延与 token（B 已在预算边缘）；修复轮引入的新提示语义若不标记身份，会造成“同 prompt_version 不同请求形状”的隐式漂移——必须用变体标记 + V3 式审计兜底。R0 的布尔矛盾页可能复发，届时该页应升级为人工核对路径而非无限重试（现有 plan_page_reread 无重试次数上限，值得后续加链长限制）。
- 缺口：本审阅未覆盖 targeted review executor 与 v2 API 层的失败呈现面（不在失败链上）；未审计 `repair_json_quotes` 对合法中文引号内容的极端误伤面（现有测试仅一个用例）。

## Recommended Next Step

1. **立即（无决策成本）**：执行 R0——对当前 job 发起 `plan_page_reread` 后继任务，恢复 8 个失败页；同时执行 V1（length usage 离线分析）与 V3（复放报告对账）。
2. **一个会话内可定夺的设计问题（请 Codex 裁定）**：R1 采纳与否及其形态——(a) 全文重出 vs (b) diff 约束的结构修复；以及修复变体 prompt_version 的身份语义与 `plan_page_reread` 绑定放行规则。我的建议是 R1(a)。
3. **需用户重开的冻结决策（不替用户定）**：D1 has_eligibility_value 是否改为代码规范化（其冗余性已由本次双模型相关失败实证）；D2 是否允许第二次 length 翻倍或 B 专项预算（含全量重跑代价的显式接受）。
4. **明确不做**：恢复完成前落地任何 prompt/合同/预算版本变更（会切断局部恢复）；任何代码侧静默改写 id、补 bbox、翻转布尔；任何新架构。
