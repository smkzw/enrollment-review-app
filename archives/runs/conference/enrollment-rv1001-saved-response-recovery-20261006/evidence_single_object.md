Trellis SessionStart ✓

我先读取上下文集与主计划，然后按读取集读取六个冻结包文件。

Glob 未找到 artifacts 目录，扩大范围定位冻结包文件。

目录中存在 manifest.json。读取清单以获取六个冻结文件的确切名称。

清单列出五个冻结文件。并行读取全部五个。

已读取全部六个冻结文件（manifest.json + recovery.py.txt + call-contract.txt + executor-definitions.txt + transport-definitions.txt + tests.py.txt），无执行、无网络、无源码外读、无文件写入。以下为独立审阅报告全文，供 runner 采集。

# Conference Output: enrollment-rv1001-saved-response-recovery-20261006 - evidence_single_object

## Output

### 0. 总体裁定（先行结论）

**未在冻结定义中发现阻断性真实缺陷。** 对任务点名挑战的七条链路逐一核验后，恢复路径在写侧、检查点重放侧和汇总侧均**失败关闭**（fail-closed）；"不得回落到新的付费读取"由非可重试 StepFailure 与测试中的 forbidden transport 双重保证。我判定可放行为"证据充分的有限恢复能力"，但带 **1 项验收前置条件（F1，证据缺口）** 与 **2 项必须补的反例测试（F2、F3）**；另有 1 项可选加固（F4）与 1 项消费者待确认（Q3）。

关键区分：
- F1 是**包内可验证性缺口**，不是已证实的代码错误；若 Codex 接受 manifest 的 preflight 断言，则不构成阻断。
- F2/F3 是**反例覆盖缺口**：被挑战的核心规则（首答唯一、检查点丢失路径的证明强制）在代码中已实现，但没有直接对抗性测试。
- F4 是**可选精度加固**，非演示出的故障（payload 全等 + run_id/call_id 绑定使其当前不构成语义空洞）。

我**不批准临床事实**、**不放宽来源门禁**、**不宣称最终验收**；最终裁定权归 Codex。

---

### 1. 审阅范围与方法

- 只读：`context/..._conference_context.md`、`plans/codex_main_venue_...md`、`artifacts/normalizer-saved-recovery-review-20261006/` 下全部六个冻结文件，各读一次。
- 未读取任何实时源码、临床原件、数据库、日志；未运行测试或任何命令；未写文件。
- 未纳入评估：`evidence_candidate_partition`、`evidence_normalizer`（parse/validate）、`model_runner`、`build_evidence_normalizer_prompt`、`jobstore`、`artifact_store` 内部定义均不在包内。按任务规则，**包内缺失依赖记为局限，不记为缺陷证据**。
- manifest 为冻结包内证据：`base_commit=f2603a9f`，5 个源文件 sha256 + 5 个包文件 sha256，`evidence.model_calls=0 / database_writes=0 / current_revalidation_passed=true / protected_unchanged=true / claims_complete=false`。

---

### 2. 逐项裁定（对应任务点名的七项挑战）

**(1) 同调用/同作业/同请求绑定 — 通过（有一处精度说明，见 F4）**
- 失败清单与回执均做四元绑定校验：`recovery.py.txt L39-41`（job_id/step_id/run_id/call_id）；请求工件同样校验 `recovery.py.txt L57-62`。
- 写侧绑定取自真实执行上下文 `executor-definitions.txt L594-595`，非操作者自报。
- 重放侧：证明先查 policy 与 `raw_output_sha256 == call.raw_output_sha256`（`L138-139`），重建 `rebuilt.proof` 与存档 `proof` **逐字节相等**（`L163-164`），且 `_get_call_for_step(payload, proof["step_id"]) == frozen_call`（`L163`）；作业绑定采用"同 payload 全等"（`L160-162`）。
- 结论：恢复只在显式选择、且四元身份与当前冻结作业一致的失败原件上成立；错误 call_id 选取会被失败清单的 call_id 绑定拒绝。

**(2) 首答唯一（first-answer-only）— 通过（实现正确，缺直接反例，见 F2）**
- 三重约束：`attempts[0].error_code == "PARTIAL_OUTPUT"`（`recovery.py.txt L43-45`）；所选回执必须在失败清单的回执列表中（`L46`）；`sha256(raw_text) == attempts[0].raw_output_sha256`（`L51-53`）。
- attempts 的时序语义在包内有旁证：`executor-definitions.txt L677-681`（`attempts[-1]` 为最近一次；"最初未通过核对"/"随后仍未解决"），可判定 `attempts[0]` 为首答。
- 反例（有效）：`tests.py.txt L75-92, L137-154` 中 `foreign_job/input/length/request_missing/prompt/budget/repair/alias/foreign_locator/model` 十个变异全部 `failed_final`、无事实发布、无调用落库；其中 `foreign_locator`（L53-56）正是"虚构定位"答案被拒绝的正例。
- 说明：`repair` 变异改的是请求体（被请求等值拒绝），**并未**测试"选择第二个修复回答的回执"；这正是 F2 要求补的反例。

**(3) 当前解码器/分区等价 — 结构上通过；真实请求等价在包内不可验证（见 F1）**
- 恢复不使用任何缓存的解析结果，而是用**当前** `parse_evidence_normalizer_output` + `validate_evidence_normalizer_output` 重新解析原答，并传 `require_current_draft=True`、当前 `evidence_input` 的页/定位符/来源哈希/创建时间（`recovery.py.txt L79-88`）。
- 分区回退仅在当前冻结 payload 已启用 `CANDIDATE_PARTITION_POLICY` 时可用（`executor-definitions.txt L597-598`；策略合法性在 `L430-435` 被前置校验），**未新增门禁放松**。
- 请求等价采用"实存请求体 == 当前重建体"逐字段比较 + `canonical_hash` 双重校验（`recovery.py.txt L63-67`）；模型身份 requested_model 严格相等、response_model 折叠大小写相等、response_id 非空（`L68-73`）；来源简称集合严格相等（`L74-76`）。
- 保留项：真实首答所用的真实请求（`record_request` 产物，`executor-definitions.txt L549-556`）与 `_prepare_response_revalidation` 重建体的字节等价，包内只有 manifest 布尔断言支撑；且 `text_reference_strategy` 专用分支存在一个未决差异点（F1b）。

**(4) 证据门禁 — 通过，未发现放松**
- 恢复后仍走与实时路径相同的后处理：候选/未解决项水合与持久化（`executor-definitions.txt L732-765`）、`apply` 内身份冲突校验（`L767-806`）、汇总期 `validate_page_coverage`、`_validate_persisted_page_closure`、文本核对（`L879-893`）。
- 有分区的调用会把运行状态压到 PARTIAL（`L1015-1016`），恢复不会伪装成"干净全成功"。
- 无 `model_called` 的四种读法在合同层有区分：`reading_method` 仅记录"有原答身份的成功调用"，且 `response_recovery_sha256` 必须伴随 `model_response`（`call-contract.txt L41-49`）。

**(5) 证明持久化/汇总/检查点重放 — 通过**
- 写侧：证明先以内容寻址工件保存，其 sha 落入调用行 `response_recovery_sha256`（`executor-definitions.txt L599-600, L760-761, L775-777`）；分区处置另存独立工件（`L604-608`）。
- 重放侧：`_validate_response_recovery_replay` 完整重跑恢复重建并做字节相等（`L150-166`），随后 `_validate_saved_output_matches` 对比已存候选/未解决项（`L167, L299-321`）。
- 汇总侧：**检查点路径**（`L835-844`）与 **apply 路径**（`L868-878`）都逐调用校验恢复证明；检查点丢失时由 `_rebuild_call_checkpoint_from_persisted` 从持久成功调用重建，并写入 `response_recovery_sha256` 与 `model_called=false`（`L408-414`），再进入同一重放校验（`L495-504`）。

**(6) 缺失/被篡改证明 — 缺失：通过（失败关闭）；篡改：在威胁模型内失败关闭**
- 缺失：工件存储未配置或证明读不到 → 立即 `ValueError("保存原答恢复的证明缺失")` 并包装为非可重试 StepFailure（`executor-definitions.txt L135-136, L168-170`）；`tests.py.txt L157-171` 在汇总侧删证明文件后验证抛错"保存原答恢复不能复用"。
- 篡改：单点改动（policy/raw_output_sha256/绑定字段）会被 `L138-139` 的显式比对或 `rebuilt.proof != proof` 字节相等捕获；若伪造为另一调用的自洽证据链，则 `_get_call_for_step(payload, proof["step_id"]) != frozen_call` 拒绝。完全自洽的跨调用伪造还需同时改数据库中的 `response_recovery_sha256`，属受控边界之外，且与本功能"显式操作者选择 + 审计"定位一致。
- 被删证明在**两条消费路径**（步骤重放、汇总）由同一函数兜底，方向一致。

**(7) 恢复是否可伪装成"新鲜读取" — 包内可区分；包外消费者待确认（Q3）**
- 持久化调用行同时携带 `reading_method="model_response"` 与 `response_recovery_sha256`；证明与检查点均显式 `model_called=false`（`executor-definitions.txt L760-762`、`recovery.py.txt L102`）；测试断言 `proof["model_called"] is False` 与重启 `result["model_called"] is False`（`tests.py.txt L122, L130`）。
- 局限：`reading_method` 本身仍写 `model_response`（合同语义为"有原答身份的成功调用，不证明资料核清"，`call-contract.txt L41-43`）。包内未出现任何按 `reading_method` 统计"新鲜模型调用"的消费者；包外不可验证。

---

### 3. Findings

#### F1（验收前置条件｜证据缺口，非已证实代码缺陷）真实请求等价的决定性证据不在包内
- 冻结引用：`recovery.py.txt L63-67`（请求等值门禁）;`executor-definitions.txt L117-129`（重建助手）vs `L654-665`（实时 `model_runner.run` 调用）；`tests.py.txt L50-51, L66-67`（fixture 用同一助手构造"真实请求"）；`manifest.json`（`current_revalidation_passed=true`、`claims_complete=false`）。
- 观察：(a) 合成测试的 `request` 由 `_prepare_response_revalidation` 生成后写入 `raw_request`，而恢复校验又用同一助手重建后比较——**等值测试在合成层是自证循环**，无法捕获重建体与真实实时首请求的偏差。(b) 定义实时首请求的 `model_runner.run` 与 `build_evidence_normalizer_prompt` 不在包内；其中实时路径在 `text_reference_strategy` 分支会传 `compact_references=True`（`L664`），而重建助手只传 `reference_aliases`（`L121-128`），若提示构建器存在独立于 `reference_aliases` 的 compact 行为，该分支重建体可能与真实首请求不一致。(c) 真实失败调用的请求等值只有 manifest 的布尔摘要，未附字节比对产物。
- 方向：**失败关闭**——重建体与真实实存请求不一致时恢复被拒绝（"当前来源、提示、输出合同或模型参数与保存请求不同"），不会造成假接受；因此这是可验证性/可用性缺口，不是门禁放松。
- 正/反例：正例 = manifest 断言真实 preflight 通过（若为真，真实调用分支的等值已被经验证实）；反例 = 上述 `text_reference_strategy` 专用分支的重建偏差假设无法在包内排除。
- 最小一致修正（不新增框架、不产生付费读取）：①将 preflight 的按调用字节比对摘要（保存请求 sha vs 重建 sha）补入验收记录或冻结包；或②补一条**非自证**测试：用真实实时构造链（`model_runner.run` + 同一 transport 工厂，记录 `record_request`）产生首个请求，再对恢复断言 `actual_body == expected_request`；③若 `build_evidence_normalizer_prompt` 确有独立 `compact_references` 参数，则在 `_prepare_response_revalidation` 的 text-only 分支补齐同参（需先由 Codex 提供该函数定义确认，包内不能判定）。

#### F2（中等｜必须补的反例测试）首答唯一规则无直接对抗测试
- 冻结引用：`recovery.py.txt L43-47, L51-53`；`tests.py.txt L75-92`（`repair` 只改请求体）。
- 观察：核心规则"只能恢复所选失败的**首个**逻辑回答"由 raw 哈希与 `attempts[0]` 绑定实现，但没有任何测试构造"两次尝试、选择第二份回执"的场景；`repair` 变异在第 65 行只追加了一条 user 消息，命中的是请求等值门禁，而非首答选择门禁。
- 最小反例测试：fixture 写入 `transport_receipt_sha256=[shaA, shaB]`、`attempts=[{PARTIAL_OUTPUT, rawA},{…, rawB}]`、`raw_text(A)≠raw_text(B)`，选择 `shaB` → 期望 StepFailure"保存原答不是失败记录中的首次回答"；选择 `shaA` → 恢复成功。无需模型调用。

#### F3（中等｜必须补的反例测试）检查点丢失 + 恢复证明的重建路径未被覆盖
- 冻结引用：`executor-definitions.txt L482-506`（重建分支）、`L408-414`（重建写入 `model_called=false` 与 `response_recovery_sha256`）、`L255-257`（重建后的恢复重放）；`tests.py.txt L123-129`（重启测试始终传入 checkpoint，走的是 `L452-481` 分支）。
- 观察：`_rebuild_call_checkpoint_from_persisted` 是本轮新增/相关的消费路径，其与恢复证明的交互（含 `model_called=false` 进入检查点、以及证明缺失时失败关闭）没有测试；缺失证明的反例只在汇总侧覆盖（`tests.py.txt L157-171`）。
- 最小修正测试：恢复成功后（合成环境）删除步骤检查点、以 `last_checkpoint=None` 重入 `execute_call`，断言重建检查点含 `model_called=False` 且恢复校验通过；再删证明工件重跑，断言 StepFailure。

#### F4（低｜可选精度加固，非演示故障）重放侧作业绑定以"payload 全等"为代理
- 冻结引用：`executor-definitions.txt L157-162`（`JobStore.get_job(proof["job_id"])` + `verify_payload_sha256(...) != payload`），对比写侧用真实 `context.job_id/step_id` 绑定（`recovery.py.txt L39-41` 与 `executor-definitions.txt L594-595`）。
- 分析：冻结 payload 含 run_id、调用清单与策略，且 `_get_call_for_step(payload, proof["step_id"]) == frozen_call` 与调用行身份校验共同成立；`_rebuild_call_checkpoint_from_persisted` 的既定语义本就是"持久成功调用是唯一事实，可跨重启复用"。因此"同 payload 的不同作业记录"在语义上是同一份工作，当前**不构成可演示的空洞**。
- 若需收紧（一行级）：在 `_validate_response_recovery_replay` 增加可选的 `expected_job_id/expected_step_id` 参数，由 `execute_call`/`execute_finalize` 传入 `context.job_id/context.step_id` 并断言相等。另注：`_validate_partition_replay`（`L276-279`）只校验 call_id/run_id/raw_output_sha256，未校验分区工件内的 job_id/step_id；该行为对"非恢复分区"是既有实现，恢复路径已由证明覆盖，仅作一致性观察。

---

### 4. 未决与不确定性（包内无法判定，按失败方向影响分级）

1. **回执字段契约**：`raw_text/finish_reason/request_sha256/requested_model/response_model/response_id` 由恢复代码读取、由合成 fixture 写入，但生产回执封装（`_request_stream`/`_streaming_completion` 内构造）不在包内；`canonical_hash` 与 `_bind_request_receipt` 的序列化（`transport-definitions.txt L41-44`）是否完全同一编码也未在包内证明。方向：不一致则恢复整体失败关闭（假拒绝）。
2. **attempts 时序**：已由 `executor-definitions.txt L677-681` 旁证为时序排列，但 `model_runner` 定义缺失，无法 100% 确证 `attempts[0]` 恒为首答。
3. **"首答唯一"的作用域语义**：若同一调用存在**多个**失败清单（两次实时失败），代码接受任一与当前身份/输入/请求匹配的失败清单的**该失败内**首答；这是"按所选失败"而非"全历史唯一"。每个候选仍须通过当前全部门禁，且证明完整记录所选清单与回执 sha，属可审计的显式选择。建议 Codex 明确该定义（见 D3）。
4. **消费者口径**：包内未见按 `reading_method` 统计模型调用/成本或"新鲜读取"的消费者；包外待确认（Q3）。
5. **恢复时刻**：证明与调用行的 `created_at` 取 `run_created_at`（`executor-definitions.txt L732`）以保重放确定性；证明不含恢复时间戳，恢复发生时刻只能从作业/步骤审计轨迹获得。属可选审计增强，不影响正确性（见 D4）。
6. `verify_payload_sha256` 语义（校验并返回负载）按常规推断，未在包内定义；若其在校验失败时的行为不同，最坏结果仍是失败关闭。

---

### 5. 我最重要的反对意见、替代方案与决策点（给 Codex）

- **D1（承接 F1）**：不要把"真实请求等值"仅记为 manifest 布尔。请二选一：附 preflight 字节比对摘要；或补 F1② 的非自证测试。**在获得该证据前，建议恢复能力只对 preflight 已覆盖的分支授予使用；对未覆盖分支（尤其 `text_reference_strategy`-only）保持禁用**。这是我唯一的验收前置条件。
- **D2（承接 F2/F3）**：把两条反例测试作为本切片"完成"定义的一部分——它们分别直接证明"不得接受后来的修复回答"和"重启（含检查点丢失）不得绕过证明"，都是任务点名的高危规则；无模型调用、无新框架，成本极低。
- **D3（语义决策）**：确认"首答唯一"为"按所选失败清单内首答"；若产品意图是"全历史唯一首答"，则需在操作者契约中固定单一 manifest 或在代码中限制选择集，二者必择其一并写入文档，避免未来出现"择优选择失败清单"的解释空间。
- **D4（可选）**：是否在证明中加入恢复时刻（需同步更新 policy 版本串），以补审计时间线；不加入也可从作业审计还原，我倾向不加入以保持证明最小化。
- **D5（可选加固）**：F4 的 `expected_job_id/step_id` 显式断言，一行级改动；当前无演示故障，可按需延后。

### 6. 给 Codex 的精确有界问题

- **Q1（决定性）**：零调用 preflight 是否对真实失败调用做了"重建初始请求体 vs 实存 `raw_request` 请求体"的逐字节比较，且结果可通过？能否附上该比较摘要（两侧 sha + 结果）或授权一次同环境只读复核？——这是 F1 的唯一决定性证据；若不能，安全暂定路径 = 按 D1 限制恢复使用范围。
- **Q2**：`build_evidence_normalizer_prompt` 是否存在独立于 `reference_aliases` 的 `compact_references` 行为（对应实时调用 `executor-definitions.txt L664` 与重建助手 `L121-128` 的差异）？——决定 F1b 是"可用性缺陷（假拒绝）"还是"不存在差异"。
- **Q3**：仓库内是否有任何消费者（用量/成本/报告/UI）仅凭 `reading_method == "model_response"` 推断发生过新鲜模型调用，而不检查 `response_recovery_sha256` / `model_called`？——决定第 (7) 项的包外结论；若有，最小修正 = 在消费者处加一个派生判断，无需改数据模型。
- **Q4（次要）**：`_validate_partition_replay` 是否应一并校验分区工件的 `job_id/step_id`（当前仅恢复证明覆盖）？——一致性偏好问题，非阻断。

### 7. 正例/反例证据汇总（供快速复核）

| 挑战点 | 正例（实现/测试） | 反例（被拒绝） |
|---|---|---|
| 同调用/作业/请求绑定 | `recovery.py.txt L39-41,57-62`；`executor-definitions.txt L594-595` | `tests.py.txt` `foreign_job`、`input` 变异 |
| 首答唯一 | `recovery.py.txt L43-47,51-53` | 代码上由 raw 哈希拒绝非首答；**测试缺位（F2）** |
| 请求/模型/来源等价 | `recovery.py.txt L63-76` | `prompt`/`budget`/`alias`/`model` 变异 |
| 当前解码器+分区可选性 | `recovery.py.txt L79-93`；`executor-definitions.txt L430-435,597-598` | `foreign_locator` 变异（虚构定位在分区回退下同样被拒） |
| 证明持久化/重放/汇总 | `executor-definitions.txt L599-600,835-844,868-878,1015-1016` | 无证明 → 非可重试 StepFailure |
| 缺失/篡改证明 | `executor-definitions.txt L135-136,138-139,163-166`；`tests.py.txt L157-171` | 删除证明文件 → "保存原答恢复不能复用" |
| 不伪装新鲜读取 | `recovery.py.txt L102`；`executor-definitions.txt L760-762`；`tests.py.txt L122,130` | 包外消费者待确认（Q3） |

**最终声明**：本报告为受限会议角色的一次完整独立审阅，未修改任何文件、未运行任何执行、未读取原始临床材料；不构成临床事实批准、来源门禁放松或最终验收。是否接受该恢复能力、以及 F1 前置条件如何满足，由 Codex 裁定；如需同会话补充，我可以针对 Q1–Q4 或 F2/F3 的测试设计给出更细的方案。
