原库哈希与复制时一致（`fb132e87…`），未做任何写入；所有工件已持久化。诊断完成，输出最终报告。

# 执行输出：phase5-resume-next-flash-20260903 - worker_02

## 边界与上下文检查

- 绑定运行器工作目录（worktree `phase5-clinical-facts-profile`，分支 `codex/phase5-clinical-facts-profile`）。Delegated 模式生效；未派发会议、未评审同伴、未写 runner 报告文件。
- 已读初始集合：`context/phase5-resume-next-flash-20260903_execution_context.md`、`plans/codex_execution_phase5-resume-next-flash-20260903.md`。我的任务是工作项 2：复现并持久化 SAR 31001 筛选期单页 Evidence Normalizer 诊断，区分来源闭包、Schema 和模型质量/性能问题。
- 额外读取（工具取证）：暂停检查点 `CHECKPOINT_20260902_SAR31001_NORMALIZATION_MTPLX_PAUSED.md`、既往执行报告（`phase5-sar31001-facts-profile-20260902/worker_02、worker_03`、`closeout-r3/worker_02`、`nextflash-closeout/worker_02`）、`app/agents/evidence_normalizer.py`、`app/domain/contracts/evidence_normalizer.py`、`app/agents/deepseek_evidence_normalizer_transport.py`、`app/services/fact_normalization_source_adapter.py`、`app/services/fact_normalization_executor.py`、`app/storage/db.py`、`app/storage/evidence_locator_repositories.py`（闭包门禁实现）、`app/config.py`、`scripts/run_phase5_first_batch_probe.py`。
- 边界遵守：验收数据库**只读**（副本 `db-snapshot/` 上运行全部产品代码路径；原库 SHA-256 会话前后均为 `fb132e87…`，未写入）；未启动/停止任何服务；未复用取消作业、未激活快照；仅写了授权的诊断工件目录 `artifacts/phase5-acceptance/20260903/normalizer-single-page-diag/`；未改动 `app/`、`tests/`（`git status` 中的 WIP 均为本会话之前已存在的未提交内容）。

## 已执行工作

**1. 现场核查（只读）。** 暂停检查点之后库已变化：DB 从 `79d93f38…` 漂移到 `fb132e87…`；16:02–19:23 期间发生了 9 个新规范化作业（全部 `cancelled`）和一次筛选完整修订重建并激活（19:22:57，`complete-529c2876…`，episode revision 3→4）。原始作业 `2e28e867…` 终态已是 `cancelled`。这些是合法 API 会话产物，已记录供 Codex 知悉；本诊断未复用任何旧作业。

**2. 来源闭包层（确定性重建，产品代码路径）。** 当前活动权威 `complete-529c2876…` 通过全部闭包门禁：24 页、5 个逻辑文档、单页调用可精确重建（逻辑文档 `3de28631…` = 基线血常规 PDF 第 1 页；1207 字符有效文本、240 个定位、58 条相关要求；输入哈希 `7474a7bc…`）。历史权威 `complete-45b1c163…` 在现行代码下重建失败：`RevisionClosureError`——量化差异为存储 1562 定位 vs 现行门禁期望 2146（差 584 个 `source-line:` 自动定位；存储集是期望集的纯子集，无伪造定位）。结论：**历史修订仅败于演进的定位合同（代码演进产物），当前链源闭包完好**。

**3. Schema 层（历史输出重放 + 全库核查）。** 全库 `fact_normalization_calls` 仅 1 行且 `succeeded`：2026-09-02 16:02 的单页调用（flash-next，冻结配置 42ac01d6：medium/60000/0.2）持久化了 **31 条 fact 候选 + 2 条未解决项**（EX-09:01:01 `ocr_or_parse_risk`、EX-09:05:01 `result_fields_missing`）。合同级重放：31+2 全部通过 pydantic 严格合同；引用的 88 个 locator 全部落在修订存储定位集内。严格 JSON Schema（MTPLX `json_schema` 受限解码 + `generation_mode: ar`）处于激活状态。**无任何 schema 失败证据**。

**4. 模型质量/性能层（活体复现）。** 质量已由上述历史成功调用证明合格。性能为唯一阻断项，三重证据：(a) 历史成功调用端到端 **45 分 52 秒**（16:02:09→16:48:01，job 事件持久化），第二步 66+ 分钟未完成被取消；(b) 今日复现：60k 请求在客户端终止后服务端仍生成约 **48 分钟**才完成（与历史一致），空闲引擎上两次 300 秒超时尝试（16384 max_tokens、63,348 字符 prompt）均未返回；(c) 引擎占用期间 8 token 极小请求也 60 秒超时——单槽队头阻塞，即历史 baseline 作业被饿死的同因。原始 06:21 作业的 3 次 `TRANSPORT_FAILED / Error code: 502`（持久化事件确认）所用冻结身份 `mtplx-qwen38-27b-optimized-quality` **已不在 8002 `/v1/models` 列表**——路由身份错配已由 15:44 起的 flash-next 配置解决（`app/config.py` 默认与 DB 冻结配置均已是 flash-next，与 8002 实际服务模型一致）。

**5. 持久化。** 全部工件与可复算脚本写入诊断目录（见下），`DIAGNOSIS.md` 为完整诊断书。

## 工件与证据

目录 `artifacts/phase5-acceptance/20260903/normalizer-single-page-diag/`：
- `DIAGNOSIS.md` — 完整诊断书（分类结论、证据、残留验证需求）
- `run_single_page_diag.py` — 可复算诊断脚本（离线重放 + `--live` 有界活体调用）
- `diag-summary.json`、`locator-closure-delta.json`、`historical-authority.json`、`current-authority.json`、`historical-input.json`、`current-input.json`、`live-model-config.json`、`live-transport-calls.json`、`routing-observations.json`
- `db-snapshot/enrollment-review-v2.sqlite3` — 只读副本（`fb132e87…`）
- `live-clean/` — 空闲引擎复跑输出；`wait_and_live.sh` — 引擎排空守候 + 干净复跑脚本（路径已修复，可直接复跑）

## 命令与观察

- `sqlite3 -readonly`（后改副本）核查：10 个规范化运行（1 failed + 9 cancelled）、1 行 succeeded 调用、31 候选 + 2 未解决项、4 个冻结模型配置（06:21=27B-quality，15:44 起=flash-next）、原始作业 3 次 502 事件。
- `build_engine`+`build_fact_normalization_plan`/`build_evidence_normalizer_input`（副本上）：当前修订闭包通过；历史修订抛 `RevisionClosureError`。
- 定位闭包差异 SQL/ORM 复算：1562 vs 2146（stored-only=0）。
- MTPLX 观察：`/v1/models` 仅 flash-next（context 262144）；`/health` turbo MTP；占用期间极小请求 60s 超时；排空后实测仍 2×300s 超时。
- 无测试运行（未改任何源码/测试）；`.venv` 内 openai 2.37.0/sqlalchemy 2.0.52 可用。

## 阻碍或缺失环境

- **模型性能为唯一阻断**：flash-next 单页生成 ≈46–48 分钟/次，与产品同步传输的 600 秒客户端超时完全不兼容；14 次调用/筛选期意味着 11–15 小时纯生成。根因定位（怀疑 strict json_schema 受限解码 × MTP 推测解码相互作用或长推理循环）需 MTPLX/模型侧权限，超出本 worker 边界。
- 8002 为共享服务，按检查点边界未发送任何控制命令；被弃请求无法由我取消，只能等待自然排空。
- 不确定项（标注）：502 的服务端根因不可从客户端观测；历史 46 分钟步骤内可能含 schema 修复重试（runner 不持久化中间尝试），但今日空闲引擎实测单次生成 >300 秒与 ~48 分钟完成数据点独立成立。

## 重跑请求或下一步

1. Codex 决策性能修复路线（更换语义路由模型/参数，或异步长任务传输），随后由 worker_03 从合法新入口恢复筛选期规范化（使用当前活动修订 `complete-529c2876…`）。
2. 引擎空闲窗口可运行 `zsh artifacts/phase5-acceptance/20260903/normalizer-single-page-diag/wait_and_live.sh` 捕获完整活体输出与精确时延，并与历史 31+2 候选逐条对比。
3. `claims_complete=false` 保持成立；本诊断不构成任何临床/监管验收。
