# Execution Output: phase5-sar31001-nextflash-closeout-20260902 - worker_01

## Boundary And Context Check

- 只执行 work item 1（只读审查模型标识切换完整性、历史证据未被误改、提出最小修正）；未写任何文件，未运行会产生缓存/临时文件的测试，未触碰 worker_02/03 的实现与审计职责。
- 读取了初始上下文两份文件；补充读取的证据（原因：任务要求核对运行时真实标识与历史证据状态）：`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`（R3 设计）、`docs/PROJECT_CONTEXT.md`（3455–3490 行）、`CHECKPOINT_20260902_SAR31001_NORMALIZATION_MTPLX_PAUSED.md`、`.env.example`、`app/config.py`、`app/agents/protocol_semantic_model_router.py`、`app/agents/protocol_semantic_route_preflight.py`、`app/llm/client.py`、`app/domain/publication.py`、`app/domain/contracts/ocr.py`、`app/evidence/{fingerprint,ocr_adapter,page_processor}.py`、`app/storage/{ocr_repositories,codecs}.py`、`scripts/probe_mtplx_semantic_route.py`、相关测试与 git diff/status。
- 全部操作限于 worktree 内；未读取主仓生产路径。

## Work Performed

**结论先行：Qwen3.8-Next-Flash 切换在 config/代码/测试夹具/运行时四层均已生效且相互一致；历史证据未被误改。发现 1 处过期默认标识（探针脚本，1 行修正）与 1 项尚未实现的目标（OCR 内容级复用与归属并存，属 worker_02 未完成项）。**

1. **R3 裁决来源确认**：`PROJECT_CONTEXT.md:3475` 记载“设计书 R3 与实施计划已按横评修订”；R3 设计 §83（设计书 83 行）规定本地降级/仲裁与手写第三读统一为 Qwen3.8-Next-Flash，并明确“当前运行标识为 `mtplx-flash-next-optimized-speed`"。`CHECKPOINT_20260902_SAR31001_NORMALIZATION_MTPLX_PAUSED.md` 记录了切换动机：暂停时应用冻结配置仍指 `mtplx-qwen38-27b-optimized-quality` 而 8002 已服务 Next-Flash，构成模型绑定不一致。

2. **四层标识核对（全部一致）**：
   - **运行时（实测）**：`GET 127.0.0.1:8002/v1/models` 返回唯一模型 `mtplx-flash-next-optimized-speed`（owned_by mtplx，context 262144）。
   - **运行时（新 8910 会话）**：`.../sar31001-fresh/runtime/protocol-semantic-route-preflight.json`（23:44:28 生成）记录复杂链 `zhipu-coding-plan:glm-5.3-flash:high → mtplx:mtplx-flash-next-optimized-speed:medium → deepseek:deepseek-v4-flash:high`、短链 `mtplx:mtplx-flash-next-optimized-speed:medium → deepseek:deepseek-v4-flash:high`，全部 executable、零 blocking_errors、`env_file_configured=true`——与 R3 §83 完全一致。
   - **config**（未提交 diff）：`app/config.py:135-138` `MTPLX_MODEL` 默认即为 Next-Flash 运行标识；`REVIEW/DECONSTRUCT/EVIDENCE_NORMALIZER/PROTOCOL_CONTROL` 四节点 backend 均默认 `mtplx`、model 均派生自 `MTPLX_MODEL`、effort 派生自 `MTPLX_REASONING_EFFORT=medium`。`.env.example` 各行一致。
   - **代码/测试**：路由器与预检全部从 config 导入（app/ 内唯一硬编码就是 config 默认值本身）；测试中出现的 `mtplx-qwen38-27b-optimized-quality` 均为合法夹具——monkeypatch 注入的自有候选链，或 fresh-runtime 的 `forbidden_model_identities`（旧作业必须被拒，语义正确，不应改）。

3. **发现 1 处缺陷（最小修正）**：`scripts/probe_mtplx_semantic_route.py:26` `DEFAULT_MODEL = "mtplx-qwen38-27b-optimized-quality"`。该脚本 docstring 自述"Keep the probe aligned with the application launcher"且 fail-closed 要求精确匹配服务端模型——现启动器已切 Next-Flash，探针不带 `--model` 跑必然失败。**建议修正（1 行）**：DEFAULT_MODEL 改为 `"mtplx-flash-next-optimized-speed"`（或读 `MTPLX_MODEL` 环境变量兜底）。未改，因本任务不得写文件。

4. **历史证据不可改写核对（通过，含一处已解释的哈希差异）**：
   - git 层：无任何跟踪的证据/数据文件被改；非代码变更仅 `pyproject.toml/uv.lock`（`openai`、`pymupdf` 从 dev 移入运行时依赖——与原生 PDF 路径和 OpenAI 兼容传输相称，合理）。
   - 文件系统层：`data_v2/` 最新写入停在 09-01，`projects/` 今日零改动。
   - **哈希锚差异诊断**：暂停检查点记录 SAR 库 SHA-256 `79d93f38…`（WAL 空），实测主库为 `903f5802…` 且 WAL 非空（41KB）。根因已查明：**本执行包的 worker_03 已合法重启专用 8910（PID 79405）并在 22:05–23:44 开展新入口作业**——`command-identities/` 最新记录 `actor=worker03-closeout-r3`，内容为“重建的基线期完整资料版本……替换先于元数据确认构建的旧版本”，目标是**新**修订 `complete-16b51a26…`/新快照 `350c8279…`，即构建新版本而非改写历史版本。此为授权范围内行为，非静默篡改。
   - DB 只读查询（mode=ro）：四个旧作业终态全部保留——事实规范化 `2e28e867…`=`cancelled`（由 `cancel_requested` 于 21:01 CST 正式终态化，属检查点要求的“核对租约与终态”合规动作，非复活）、两个基线 `failed_final`（SNAPSHOT_STATE_INVALID / EXECUTOR_ERROR）、一个 `cancelled`；无新建作业复用旧身份。检查点声明的 `claims_complete=false` 现状未变。

5. **OCR 缓存归属审查（work item 2 现状）**：未提交代码已实现 v2 缓存键——`app/domain/publication.py` 新增 `ocr_page_cache/v2`（键绑定 `page_artifact_id`），适配器命中复核、租约 `validate_work_identity` 重算均含 `page_artifact_id`（纵深防御）；`app/domain/contracts/ocr.py:364-373` 验证器**同时接受 v1（历史行，不可改写仍可回放）与 v2（新写入）**双键，契约正确。`DECODER_VERSION_BY_KIND["pdf"]` 随 pdf_native 阅读序/字符映射变更升至 `slice61ar/pdfplumber/v2`，符合“解码行为变更必须提版”纪律。`codecs.mirror_values_equal` 修复 SQLite JSON 整数化（`5.0`↔`5`）导致的镜像误拒。**尚未完成的目标半程**：v2 绑定归属后，同内容跨资料版本的 OCR **内容级推理复用被一并切断**（设计目标要求两者并存），且原 EXECUTOR_ERROR 根因回归测试未见新增——这正是 worker_02 待实现项，现状确认无冲突实现。

## Artifacts And Evidence

- 本 worker 未创建/修改任何文件（遵守"不得写文件"）。运行报告由 runner 落盘。
- 关键证据文件（引用，未改动）：
  - 运行时模型：`http://127.0.0.1:8002/v1/models`（实测）；`artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/runtime/protocol-semantic-route-preflight.json`
  - 切换 diff：`app/config.py:133-138,151-152,210-215,289-294,304-312`；`.env.example:35,55,62,96,101`
  - 缓存 v2：`app/domain/publication.py:21-77`；`app/domain/contracts/ocr.py:351-373`；`app/evidence/fingerprint.py:44-65`
  - 过期标识：`scripts/probe_mtplx_semantic_route.py:26`
  - 旧作业终态：sqlite 只读查询（见下）

## Commands And Observations

- `git status --porcelain` / `git log --oneline` / `git diff <files>`：确认切换位于未提交工作区，无证据文件被改。
- `grep` 全仓：旧标识仅存于探针脚本（活代码）、测试夹具（合法）与历史 artifacts/metrics（不可改写，正确保留）。
- `curl 127.0.0.1:8002/v1/models`：服务 `mtplx-flash-next-optimized-speed`。
- `shasum -a 256 .../sar31001-fresh/enrollment-review-v2.sqlite3` → `903f5802…`（与检查点 `79d93f38…` 不符，已由 worker_03 合法活动解释）。
- `lsof`：8910=PID 79405（本包 worker_03 专用服务，运行中）、8900=8502、8002=78215。
- `sqlite3 "file:…?mode=ro" "SELECT … FROM jobs …"`：4 个旧作业终态保留，无复用。
- **未运行 pytest**（会产生 `.pytest_cache`/临时文件，与“不得写文件”冲突）；静态核验替代。

## Blockers Or Missing Environment

- 无阻断性缺失。两点不确定性如实记录：
  1. 我仅验证了 8002 端口/模型清单与预检可达性，**未做最小真实推理调用**——检查点提到的 HTTP 502 根因仍待 worker_03 的调用记录审计证实（超出本项边界）。
  2. WAL 当前非空且 8910 活跃：若 Codex 需要新的库哈希锚点，必须等 worker_03 连接静默后再取，否则锚点必然漂移。
- 观察（非缺陷）：设计书中 "Qwen3.8-Flash-Next"（手写第三读）与 "Qwen3.8-Next-Flash"（降级/仲裁）命名不一致（同一模型族）；手写专项读道（effort=low、只写手写字段）在 `app/config.py` 尚无节点级配置入口，属 Phase 5.5 待建项，不影响本次 MTPLX 语义路线切换的完整性。

## Rerun Requests Or Next Step

- **无需 rerun 本 worker**。建议 Codex 采纳的最小修正（均可派单执行）：
  1. `scripts/probe_mtplx_semantic_route.py:26` 默认模型改为 `mtplx-flash-next-optimized-speed`（1 行；或 `os.getenv("MTPLX_MODEL", …)`）。
  2. （可选，文档级）统一设计书中 Qwen3.8 模型命名写法。
  3. worker_02 继续：实现内容级推理复用与 v2 归属并存 + 补 EXECUTOR_ERROR 根因回归测试；建议其验证命令：`pytest tests/v2/evidence/test_ocr_adapter_cache.py tests/v2/agents/test_protocol_semantic_model_routing.py -q`（本轮因只读约束未运行）。
  4. worker_03 侧已有活动运行中，其 `claims_complete` 仍应为 false 直至逐源临床 QC 完成——现状检查点与此一致，无需干预。
