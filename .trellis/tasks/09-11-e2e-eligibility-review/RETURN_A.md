# RETURN_A.md — Agent A 回交记录（V3 分工A：方案生产、同源预览、核对与共同发布）

# RETURN_A.md — Agent A 回交记录（V3 分工A）

> **2026-09-18 上午最终增量（覆盖一切更早的状态描述）**
> - **本地 MTPLX 全链打通并出成果**：属主启动（运行清单修复 27B 路径失效）+ 语法约束回退（xgrammar 编译 wire 合同失败：number 前瞻正则/嵌套 items unsatisfiable → 合同入提示词）+ 瘦合同后缀绕行 Flash-Next qsa_prefill Metal kernel JIT 500。**IN-02 由本地 Flash-Next 修订成功（revision 15）**，23 条兄弟规则零变化（参与者独立复核）。
> - **会商 v3-abc-retro-20260918 已完成**（complex_delivery_conference；参与者 codex-subagent/gpt-5.6-sol，主路由 zcode 会话失败已记录）。关键采纳：EX-04 两项时间问题=同一门禁识别缺陷（非临床未决）。
> - **门禁缺陷已修复并验证**：occurrence_window 存在时用完整逐字来源重识别频次（仍走严格 preserves 核对；绑定词前导周期/尾部"的"剥离）；门禁版本 2026-09-18.1；反例测试×2；真实重算 **blocking 5→3**。回归甄别：4 个失败全部预存（dirty 基线复现），零新增。
> - **剩余 3 项**：EX-07x 回溯锚点（真临床未决→等用户权威澄清材料走 register_interpretation_sources）；观察选择（EX-04+EX-15 聚合语义→医学责任方）；IN-06 来源绑定（确定性工程缺口→下次会话目标化修订 P1+P2，不等 GLM）。另：`_GRAMMAR_INCOMPATIBLE_BACKENDS` 需补 `mtplx-api`（工程清单）。
> - 详细综合评审：`reviews/codex_conference_v3-abc-retro-20260918_review.md`；启动能力：`scripts/start_local_model_services.sh`。


> **2026-09-18 凌晨最终增量（覆盖此前各节中已过时的阻塞描述）**
> - **门禁 28→6**：经 13 次被接受的模型反馈修订（revision 2→14，逐次通过范围守卫=兄弟规则零变化），已清 22 项（EX-03/IN-04/IN-06部分/EX-02/EX-07大部分/EX-09/EX-12/EX-04部分）。修订剧本固化在 `/tmp/submit_feedback.py`（NOTES 字典含全部处方文本，可复用；注意 /tmp 重启丢失，正文要点已写入本文件）。
> - **剩余 6 项**（均两轮无进展，保留未决）：IN-02 析取（模型3轮失败：JSON不可解析×2、谓词引用不唯一×1、分支绑定不满足×1）；EX-04×3（频次形式未核实/回溯锚点未决/观察选择未核实——修订被接受但问题未消）；EX-07x 回溯锚点未决（unresolved_items 转换后门禁仍计为阻止）；IN-06-C2-P1 来源子句绑定。
> - **新识别工程缺口（下一迭代最优先）**：门禁对 TIME_ANCHOR_UNRESOLVED 的处方是"保留为待确认解释问题"，但草稿以 unresolved_items 表达后**该问题仍计为阻止发布**——"按处方保留未决"与"阻止发布清零"在门禁中不可同时达成。需读 `deconstruction_gate.py` 的 temporal_semantics 检查，确认它接受哪种未决表达（或确认这类问题天然阻塞、需走解释材料通道 `register_interpretation_sources`）。
> - 发布（P0.P3）仍被 6 项阻塞；发布链本身已核实无缺口。GLM 配额 2026-09-19 21:36 恢复后可用默认路由重试 IN-02/EX-04（GLM 对 wire 合同的合规率历史更好）。
> - B 依赖确认：subject/episode 创建硬依赖已发布项目 → A 的发布仍是全局关键路径。
> - 下方"2026-09-18 凌晨增量"节记录的中间状态（EX-03 首胜、往返稳定证伪等）仍然有效，作为过程证据。

- **角色/时间**：Agent A（ZCode 会话 zcode-20260917-agent-abc），2026-09-17 23:2x 接手，2026-09-18 0x:xx 冻结本记录。
- **接手来源**：AGENT_ASSIGNMENTS_V3_20260917.md；接手时无任何 RETURN_*.md（A 为首个接手者）。
- **工作树/branch/HEAD**：`.worktrees/phase5-clinical-facts-profile`，`codex/phase5-clinical-facts-profile`，开始 HEAD=4caf392c（与分工文件一致），结束 HEAD 同（未提交任何 commit）。无其他写者（B 尚未接手）。
- **接手 dirty 基线**：2369 项（202 modified + 大量 untracked），git status 快照见 git；本包未把全树 dirty 当自己成果。

## 本次实际修改文件（全部为本包范围）
| 文件 | 原因 | 证据 |
|---|---|---|
| `app/agents/protocol_deconstructor.py` | ①runner/run 增加 `batch_progress` 回调并贯穿 `_collect_initial_semantic_response` 多批循环（上报失败仅告警不中断生成）；②新增 `hydrate_semantic_preview`（缩减父规则目录复用完整水合，返回部分草稿+待生成清单）；③新增 `_anchor_wire_source_excerpts`/`_merge_wire_observation_fragments`（wire 层观察/复查摘录确定性恢复：引号规范化、唯一超集锚定、单来源多片段按原文序并回；其余差异仍交严格门禁）；④`_call_issue` 保留底层服务错误原文（≤800字） | before/after：git diff；测试 4/4 |
| `app/services/protocol_deconstruction_executor.py` | ①`_persist_semantic_batch_progress`：逐批合并候选原子写 `blobs/protocol-semantic-preview/<job>/partial-candidate.json` + 追加 `SEMANTIC_BATCH_PROGRESS` 事件（B2 计量锚点）；②回调贯穿 fake/routing/pinned/graded 全部 runner.run 调用点 | 同上；真实运行事件流 |
| `app/services/protocol_workbench_service.py` | 新增 `get_generation_preview`：冻结输入存在且无正式草稿时读 partial 文件→部分水合→只读投影；正式草稿出现即 `final_draft_ready` 让位；任何解析失败返回不可用而非残缺内容 | 测试+实况 |
| `app/api/v2/protocols.py`、`app/api/v2/protocol_schemas.py` | `GET /{job_id}/draft/generation-preview` + `GenerationPreviewResponse`（preview_only 恒真，防误发布） | OpenAPI |
| `app/domain/contracts/enums.py` | `JobEventType.SEMANTIC_BATCH_PROGRESS`（追加值，兼容旧事件） | — |
| 前端 `protocolWorkbenchTypes/Normalize/Http/Repository/Stub.ts`、`ProtocolJobFlow.tsx`、`ProtocolJobProgress.tsx`、`styles/protocols.css` | 生成中 4s 轮询预览；只读"有源候选预览"面板（规则卡+来源摘录+待生成清单+不可发布声明） | tsc 通过；http 15/15 |
| `tests/v2/api/test_generation_preview_incremental.py`（新增） | 4 个聚焦测试：部分水合保留待生成、端点部分→让位、锚定/合并助手行为 | 4/4 通过 |
| `scripts/debug_batch4_raw_output.py`（新增，诊断工具） | 重放任务批收集并转储模型原始响应（不落草稿、复用批缓存） | /tmp/sar-batch4-responses.jsonl |
| design.md / implement.md / 本文件 | P0 短图+断点、六项状态、回交 | — |

## P 子项状态（§9 逐项）
- **P0**：已实现并已验收（短图+断点 B1–B4 已入 design.md「P0 短图」节；无已发布 RuleSet 的结论以 data_v2 空 rule_sets/projects 为证）。
- **P0.P1**：已实现并经真实运行验收（生产→保存→预览链全通；详见下）。
- **P0.P2**：实施中（真实草稿已生成；28 项门禁问题待修订清零；两项修订入口各遇到一个具体阻塞，见"未决"）。
- **P0.P3**：未开始实跑（被 P0.P2 阻止发布挡住；发布链本身已核实：前端 `useProtocolControls` 自动起控制任务并 `publicationBlocked` 强制等待，publish 请求带 control_job_id/checkpoint_id，`ProtocolPublicationService.publish` 仅在 control_job_id 非空时 prepare/save 控制目录——protocol_publication_service.py:383/464）。

## 生产→保存→消费→正式可操作入口（真实证据）
- **生产**：正式 DOCX `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`（418KB，未改动原件）经 UI 上传（Ego Lite，localhost:5173 → 8902）。job `769ae98f76b4450ca810fbbdd9f518d8`，身份确认 III 期（E2E 元数据与页眉逐字依据已在身份面板核对）。
- **保存**：23/23 批全部通过；draft revision `draft-revision:draft:all:1`（draft_id `draft:all`），状态"已保存"，23 条父规则、3 个流程节点。
- **消费/入口**：`GET /api/v2/protocol/deconstructions/{job}/draft|integrity|sources|draft/generation-preview`；UI 审阅页可打开。逐批预览实况从 1/23 推进到 23/23 并正确让位（final_draft_ready）。
- **证据位置**（绝对路径，工作树根= `.worktrees/phase5-clinical-facts-profile`）：`data_v2/enrollment-review-v2.sqlite3`（jobs/job_checkpoints/protocol_draft_revisions）；`data_v2/blobs/protocol-semantic-batches/769ae9…/`（23 个已验证批次缓存）；`data_v2/blobs/protocol-semantic-preview/769ae9…/partial-candidate.json`；`data_v2/blobs/protocol-semantic-route-audits/769ae9…/route-audit.json`。

## 实际模型调用（工程 review 与产品调用分开）
- 产品-方案生成：`deepseek` / `deepseek-v4-flash` / reasoning_effort=high / thinking enabled / max_tokens 65536 / 端点 api.deepseek.com（.env 既有 DEEPSEEK_API_KEY）。**原因**：默认 GLM（zhipu-coding-plan glm-5.3-flash）实测 429「每周/每月上限，2026-09-19 21:36:26 重置」；本地 MTPLX 属主模式要求独占端口/自装实例，共享 MTPLX.app 实例（8002）在驻留 107GB 权重、系统仅 38% 空闲，无法再装。启动方式：`DECONSTRUCT_BACKEND=deepseek DECONSTRUCT_MODEL=deepseek-v4-flash DECONSTRUCT_REASONING_EFFORT=high`（仅环境变量，未改代码/未改 .env）。批次重试共 6 次任务级 retry（每次批缓存回放、只调失败批）。
- 产品-反馈修订：同上路由（GRADE_SHORT→pinned→deepseek），1 次调用，模型有产出但被宿主范围守卫拒绝（守卫行为正确）。
- 工程 review：无（未调用会商；本轮为连续实施）。

## 运行中任务与归属
- 后端 uvicorn 8902（PID 见 `ps`；日志 /tmp/enroll-v2-8902.log；启动命令含上述 DECONSTRUCT_* 环境变量）。
- 前端 vite 5173（日志 /tmp/enroll-vite.log）。
- 共享服务未动：8002=MTPLX.app 共享 FlashNext（勿停）；8910=医学经理工作台；oMLX 8001 未启动。
- Ego Lite TaskSpace id=10（p1 打开着任务页）。等待/取消：两个 nohup 进程可直接 kill；Job 在 DB 中持久，重试随时可续（批缓存回放）。

## 验证记录
- 聚焦测试：`tests/v2/api/test_generation_preview_incremental.py` 4/4 passed（0.6–1.7s）。
- 前端：`tsc -b` 通过；`vitest run src/api/protocolWorkbenchHttp.test.ts` 15/15。
- 回归定性：`tests/v2/api/test_protocols_api.py` 10 failed/19 passed 与基线失败集对比——经"仅 stash 本包 6 个后端文件"的定向实验证实 publish 等失败在无本包改动时同样出现（预存）；`tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py` 等 21 项失败为预存 dirty 基线 wire 测试问题（该文件 HEAD 版本连 DNF_WIRE_VERSION 都无法导入，无法构成基线对照），失败模式均为 wire round-trip，与本包改动（回调/预览/摘录恢复）无交集。
- 真实运行：如上"生产→保存→消费"。

## 未决（分三类）
- **技术阻塞（P0.P2 发布闸门）**：
  1. 完整性门禁 28 项阻止发布：boolean_logic 3（IN-02/EX-03"至少一种/之一"需 any 节点承载、EX-06i 例外作用域）、temporal_semantics 22（REVIEW_STAGE_USED_AS_DATE_CONSTRAINT×5、PROSPECTIVE_*×8、TIME_ANCHOR_*×4 等）、source_coverage 3。逐项清单：`GET …/integrity`。
  2. `PUT /draft`（手工修订）对 GET content 原样回传报深路径 INVALID_REQUEST（FastAPI 校验"相关内容·第2项·第1项·…·第3项 内容不符合填写要求"）。correlation: daa7acfeea3e4598976ec4e128e26ae9。已排除空 `source_clauses:[]` 因素。**下一完整动作**：用 `python -c` 以 OpenAPI schema 对 GET content 做逐字段校验定位字段（预计 30 分钟内），或复现前端 patchComponentSemantics 路径对照差异。
  3. 反馈修订（模型）1 次被范围守卫拒（"候选稿改动了选定标准以外的内容"）——重试时反馈说明需更强限定"仅返回 IN-02 单条对象"；GLM 配额 2026-09-19 21:36 恢复后可回默认路由。
- **临床待澄清**：无新增（未发现需用户裁定的真实语义冲突；SAR 比较附件仍未找到，未影响本链）。
- **普通剩余**：批22（EX-15 饮酒频次+复查先后关系）曾连续两次不同错误、第 3 次任务级重试通过——该模式提示复杂频次规则对 flash 档模型偏难，后续方案首次生成可观察；API 套件预存失败清单与根因（16K 批预算 vs 单响应 fake transport）已记录，属预存测试债，建议 C 的 P5 集中核查时统一处理。

## 新接口/配置/迁移与消费者
- 新增只读端点 `/draft/generation-preview`（前端已接：JobFlow 轮询+Progress 面板；stub 已实现返回不可用）。
- 新增事件类型 `SEMANTIC_BATCH_PROGRESS`（无新表/迁移；追加枚举值）。
- 新增 blobs 目录两类（preview/route-audits 后者原有）。无数据库迁移。
- 直接消费者均已接线；无未接消费者。

## 对其他包的影响
- B：不受影响（未触碰资料链任何文件）。
- C：P3 最终必须消费本包真实发布规则——当前未发布，P3 前需先完成 P0.P2/P0.P3（或按 V3 允许 P1/P2 与 P0.P 交错，P3 仍被阻塞）。
- 未修改 PRD/Goal；design.md 仅追加「P0 短图」节与原文一致。

## 下一安全动作（完整可执行步骤）
0. **（新增，接手后先做）两个已定位的关键事实**：
   a. 手工 PUT /draft 的深路径错误已精确定位：我对 IN-02 的单分支 `any` 包装违反合同"ALL/ANY 至少包含两个子表达式"（`ProtocolDeconstructionDraft.model_validate` 直接复现：`proposed_rules·1·components·0·expression·logical·children·2·logical: ALL/ANY 至少包含两个子表达式`）。GET 原始 content 本身校验合法（`/tmp/draft_content.json` 通过）。因此 IN-02 的确定性修法不是 any 包装；需按合同用其他结构表达"至少一种"（或留给模型修订）。
   b. 反馈修订两次同因被拒（`候选稿改动了选定标准以外的内容，或没有形成有效修订`，workbench_service.py:1784）。修复格式本身只应替换目标规则，**疑似根因：修订路径 `semantic_candidate_from_draft → repair → _hydrate_semantic_candidate` 往返对兄弟规则的非确定性重表示（谓词ID去重重映射、摘录恢复差异）被范围守卫判为"其他规则变更"**。验证方法：在脚本中跑 `revise_protocol_draft_from_feedback` 的内部步骤，对 23 条规则做 before/after 指纹（`/tmp/sibling_fps_before.json` 已有 before 指纹脚本思路），定位非 IN-02 规则的 diff 来源函数；确认为宿主往返不稳定后修宿主（保序/稳定ID），不放宽守卫。
1. 依据 0a/0b 修宿主后重试反馈修订（反馈说明已备：见本文件"未决"节模板）→ 断言新 revision 号+1 且兄弟指纹不变。
2. 之后按 integrity 清单处理剩余 27 项（每项：回源→确定性手工修订或模型反馈修订，两轮无进展停止并保留未决）。
3. 全部清零后走 UI 发布（前端会自动等控制任务就绪）并记录 P0.P3 六个时间锚点。

## 回滚/恢复
- 本包代码改动全部可按文件 `git checkout -- <file>` 撤销（未 commit）；删除新增文件即可。不可自动回滚 DB 中的 job/草稿——它们是真实运行证据，按约束保留（发布前的 draft revision 可经 UI"取消本次草稿"作废）。
- 原件（SAR DOCX）、共享服务、其他包 dirty 均未触碰。不建议也不需要 git reset。
- 任务未完成，不 archive；task.py 当前指针属 session zcode-20260917-agent-abc。
