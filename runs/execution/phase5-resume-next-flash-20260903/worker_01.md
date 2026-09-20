审计与防回退验证已完成。以下为完整执行报告。

# Execution Output: phase5-resume-next-flash-20260903 - worker_01

## Boundary And Context Check

- 仅在 runner 绑定的工作区内操作；初始读取了 `context/phase5-resume-next-flash-20260903_execution_context.md` 与 `plans/codex_execution_phase5-resume-next-flash-20260903.md`，按指派的 work item 1 执行。
- 会话期间仅写入 1 个授权范围内的文件（防回退测试）；未触碰任何产品源码、历史证据（artifacts/、metrics/、CHECKPOINT_*、PROJECT_CONTEXT）、`.trellis` 工作区文件或运行数据。
- 未读取 `/Users/smkzw/.codex/AGENTS.md` 与 `/Users/smkzw/.hermes/SOUL.md`；未启动会商；未安装任何包。

## Work Performed

**1. 产品配置审计（旧 Qwen3.8-27B 身份零残留，已统一为新身份）**

现行 MTPLX 路由身份 `mtplx-flash-next-optimized-speed`（即 Qwen3.8-Next-Flash 本地运行标识，依据 `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:83,375`“Qwen3.8-27B 暂不进入现行产品路由”）已覆盖全部路由定义面：

| 配置面 | 位置 | 现值 |
|---|---|---|
| 运行时默认 | `app/config.py:135-136` | `mtplx-flash-next-optimized-speed`，REVIEW/DECONSTRUCT/EVIDENCE_NORMALIZER/PROTOCOL_CONTROL 均派生自它 |
| 环境样例 | `.env.example:35,55,62,96,105` | 5 处均为新身份（仓库无 `.env` 本地覆盖文件） |
| 服务包装/启动/探测脚本 | `scripts/run_mtplx_service.sh:66`、`scripts/start_enrollment_review.command:115`、`scripts/probe_mtplx_semantic_route.py:26` | 默认新身份；`run_enrollment_review_service.sh` 仅透传 `MTPLX_MODEL` 不含字面量 |
| Phase 5 探测器 | `scripts/run_phase5_first_batch_probe.py` | 从 `app.config.MTPLX_MODEL` 取默认 |

对 `app/`、`scripts/`、`tools/` 三棵树做 `qwen / 27b / oQ8 / abliterated / pocketaihub` 全量扫描（排除 `__pycache__`）：**零命中**。

**2. 现行 MTPLX 服务实测身份（只读探测）**

`curl http://127.0.0.1:8002/v1/models` 与 `/health` 均上报 `mtplx-flash-next-optimized-speed`（模型路径 `Youssofal--Qwen3.8-Flash-Next-MTPLX-Optimized-Speed`）。现行产品路由与服务身份一致，无 `CHECKPOINT_20260902_SAR31001_NORMALIZATION_MTPLX_PAUSED.md:42` 所述“应用冻结配置指 27B、服务报 flash-next”的绑定不一致残留（当时疑因本地 `.env` 覆盖，现已不存在）。

**3. 现行测试审计（12 个文件含旧身份，全部为合法用法，无一钉死产品默认值）**

- MTPLX 27B 路由身份 `mtplx-qwen38-27b-optimized-quality`：11 个测试文件中出现，性质均为 (a) monkeypatch/显式参数注入后断言路由“跟随配置而非硬编码”（如 `test_protocol_semantic_model_routing.py`、`test_fresh_subject_runtime_routing_adversarial.py`、`test_protocol_control_agent_transport.py`）；(b) 作为**禁止身份**锚（`tests/tools/test_phase5_acceptance_fresh_runtime.py` 的 `forbidden_model_identities`，本质就是防回退用法）；(c) 大小写别名 fail-closed 词表中立夹具（`test_protocol_control_model_identity.py:32-36` 含 speed 变体 `pocketaihub-qwen3.8-27b-abliterated-mtplx-optimized-speed`）。这些**不应改写**：改掉会削弱“路由跟随配置”与“旧身份禁止”的证明力。
- `Qwen3.8-27B-oQ8e-fp16-mtp`：oMLX 后端（OCR/本地侧车）身份，非 MTPLX 产品路由，出现在 `test_deepseek_protocol_transport_slice3.py`、`test_deconstruction_transport_config.py` 等处作为显式参数，不属统一范围。
- `Qwen3.6-27B-oQ8-mtp`（`tests/test_phase_workflow.py:538`）：旧一代 oMLX 模型，显式参数化，不属本范围。
- 全量运行这 12 个文件：**258 passed，2 skipped**（跳过原因为 MG-K10-SAR 证据锚在本 worktree 不可用，与模型身份无关）。

**4. 最小修改 + 防回退守卫（本会话唯一写入）**

产品配置面已统一、无需改动；补齐的缺口是“旧 27B 身份回流到路由定义面”的显式守卫。向 `tests/v2/agents/test_mtplx_semantic_route_regressions.py`（该文件为本分支未跟踪新文件）追加约 50 行：

- `LEGACY_MTPLX_27B_IDENTITIES`：quality 与 speed 两个 27B 家族身份常量，附设计依据注释。
- `test_route_model_defaults_never_use_legacy_27b_identity`：干净环境子进程探测 `app.config`，断言 MTPLX/DECONSTRUCT/EVIDENCE_NORMALIZER/PHASE_APPLICABILITY/REVIEW 五个路由模型默认值均非 27B 身份（可捕获 `.env` 覆盖回流与 config 默认回退）。
- `test_route_defining_surfaces_carry_no_legacy_27b_identity`：扫描 `app/**/*.py` 全树 + `.env.example` + 5 个脚本面，断言零旧身份字面量；刻意不扫 `tests/`（夹具合法保留旧身份）。

## Artifacts And Evidence

- 修改：`tests/v2/agents/test_mtplx_semantic_route_regressions.py`（唯一写入文件；守卫块位于 298-334 行附近）。
- 关键证据引用：`app/config.py:135-136`；`.env.example:35,55,62,96,105`；`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:83,375`；`CHECKPOINT_20260902_SAR31001_NORMALIZATION_MTPLX_PAUSED.md:42`（不一致来源已消除的背景）；服务探测 JSON（`/v1/models`、`/health`）。
- 工具使用记录：Read（初始 2 份上下文）；Bash grep/curl/pytest/python（上述全部扫描、探测、测试）；Edit（1 次，守卫块）。无浏览器/网络外呼（仅 localhost 服务只读探测）。

## Commands And Observations

- `pytest tests/v2/agents/test_mtplx_semantic_route_regressions.py -q` → 改前 10 passed；改后 **12 passed**（含 2 项新守卫，`-k legacy_27b` 单独 2 passed）。
- 12 个含旧身份的测试文件全量：**258 passed, 2 skipped**（8.34s）。
- 守卫灵敏度负向验证：同一扫描逻辑指向 `tests/` 时检出全部 12 个含旧身份文件（含守卫自身常量），证明扫描逻辑具备检出能力而非恒真。
- `git status` 确认会话新增未跟踪文件仅为我编辑的那 1 个测试文件；其余 `??`/`M` 均为分支既有工作。

## Blockers Or Missing Environment

- 无阻塞。`tests/test_phase_workflow.py` 的 2 个 skip 依赖本 worktree 缺失的证据锚（MG-K10-SAR），属环境性既有状态，未处理也不在本范围。
- 推断（非证据）：若用户 shell profile 曾导出 `MTPLX_MODEL=<27B>`，仓库内守卫探测不到；但当前无 `.env`、服务实测报 flash-next，无行动必要。

## Rerun Requests Or Next Step

- 无需重跑。建议 Codex 验收时复核：新守卫两测试的扫描范围是否符合对“路由定义面”的定义；worker_02/03 的真实 MTPLX 端到端运行将实测新身份链路（本 pass 未做真实 LLM 调用，属其范围）。
- 遗留提示：`CHECKPOINT_20260902:42` 记录的“应用冻结配置指 27B”若指某个已冻结作业载荷中的 `declared_model`，那属历史证据，按边界不改写；新守卫已防其回到配置面。
