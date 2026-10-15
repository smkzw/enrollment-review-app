# Phase 5.8d MTPLX 结构化输出 500 根因诊断与恢复检查点

日期：2026-08-29

> 历史诊断记录：本文件保留当时的服务端故障分析，不再作为当前恢复入口。当前结论与下一安全动作以 `CHECKPOINT_20260829_VITAL_SIGN_MODALITY_AR_ACCEPTED.md` 为准；已接受的产品修复是严格 JSON Schema 请求使用请求级自回归解码，不要求修改服务环境变量。

## 当前结论

1. **根因完全定位与证据闭环**：
   - MTPLX 服务端在 `response_format` 启用 JSON Schema 且模型处于思考阶段时，通过 `mtplx/constrained.py` 生成带前导思考的 Lark 语法：
     `PRELUDE_TEXT: /(.|\n){0,4000}/`。
   - 服务端默认常量 `_THINK_PRELUDE_DEFAULT_MAX_CHARS = 4000` 限制了思考前导字符串最大长度为 4000 字符。
   - 在复杂方案控制任务（~31k 字符提示词、17.2KB Schema）下，Qwen3.8-27B 生成深入中文推理（约 1333–2000 个中文字词 Token）时，思考字符在跨过第 4000 字符瞬间（Step 2150，Token `109064`，字符数从 3999 跳至 4001），`llguidance` 解析器触发 `Stop: ParserTooComplex` 并报错 `Parser Error: token doesn't satisfy the grammar`。
   - `GrammarConstraint.advance()` 抛出 `RuntimeError: constrained decoding desync on token ...`，该异常脱离非流式生成循环，进入全局未捕获异常处理，记录 `orphaned` 飞行状态并向客户端返回 HTTP 500 `internal_error`（附带临时 12 位 `request_id`）。

2. **已排查并排除的假设**：
   - **提示词长度假说（排除）**：在非临床测试中，200 到 31,000 字符的提示词均在 7.21s 至 40.79s 内正常返回 HTTP 200 OK。
   - **Schema 复杂度假说（排除）**：在 31,000 字符提示词下，无约束、`json_object`、小型 Schema、中型 Schema 以及完整 17.2KB 的 `protocol_control_agent_wire_v1` 均在 28.5s 至 28.9s 内正常返回 HTTP 200 OK。
   - **KV Cache / 内存泄漏假说（排除）**：v13 请求发生时服务缓存仅 24.1 GB、9 个条目、0 个活动请求，依然精确在推理达到 4000 字符时复现 500。

3. **已验证的修复方案（外部基础设施）**：
   - MTPLX 服务端原生支持通过环境变量 `MTPLX_THINK_PRELUDE_MAX_CHARS` 配置思考前导长度：
     - 当 `MTPLX_THINK_PRELUDE_MAX_CHARS=0` 时，服务端生成 `PRELUDE_TEXT: /(.|\n)*/`（无字符上限），已验证平稳通过 5000+ 步（9,306+ 字符）深度推理无任何解析器报错。
     - 当 `MTPLX_THINK_PRELUDE_MAX_CHARS=16000` 时，已验证平稳通过 3000+ 步（5,584+ 字符）深度推理。
     - 思考结束输出 `</think>` 后，约束解码平稳转入严格 JSON Schema 验证。

## 冻结来源与状态

- 原始方案 SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Owned：`body.p784-p786`
- Read-only：`body.t5.r10`、`body.p321`、`body.p684`、`body.p885`
- 当前重放检查点 prompt SHA-256：`65b3021d1dcd8f03857d4ffc308679c6011fe003e0b26b53f504b9eff32bc9fc`
- 当前整包指纹：`21be5887366ce76efef352ad67f30e71c6b8b7afb73ea3033467b4adc40d98cb`
- 结构单元、批次身份、来源范围与正式统计均未变化：D001 II 仍为 `1848` 个结构单元、`1245` 个语义目标、`131` 个包，剩余 `128` 包，`claims_complete=false`。

## 持久化诊断证据

1. 矩阵测试数据：`.trellis/tasks/08-22-phase5-clinical-facts-profile/research/phase5-slice61bi-mtplx-structured-output-matrix-results.json`
2. 执行报告：
   - `archives/execution/phase5-slice61bi-mtplx-structured-output-diagnosis/phase5-slice61bi-mtplx-structured-output-diagnosis/worker_01.md`（代码与服务端异常链分析）
   - `archives/execution/phase5-slice61bi-mtplx-structured-output-diagnosis/phase5-slice61bi-mtplx-structured-output-diagnosis/worker_02.md`（4维非临床诊断矩阵与精确Token步进复现）
   - `archives/execution/phase5-slice61bi-mtplx-structured-output-diagnosis/phase5-slice61bi-mtplx-structured-output-diagnosis/worker_03.md`（根因收敛、回归测试与恢复检查点）
   - 归档清单：`archives/execution/phase5-slice61bi-mtplx-structured-output-diagnosis/cleanup_manifest.json`
3. 历史崩溃请求对照：
   - `284e3d052bce` (v11 修复轮, 512s)
   - `06172f5bb8d0`, `6d7fb4f3fe1d` (v12 两次请求, 104s, 96s)
   - `e0c906e5d034`, `c283bba62027` (v13 两次请求, 110s, 95s)
   - 每次崩溃在 MTP depth 2 下精确停止在 ~1321–1333 个生成周期（~3964–3999 tokens），对应 4000 字符限制。

## 下一步安全恢复操作

以下步骤是故障诊断当时的历史建议，已由当前检查点取代，不应继续执行。

1. **外部基础设施修复**：
   在启动/运行 MTPLX 服务的守护进程环境中配置环境变量：
   `export MTPLX_THINK_PRELUDE_MAX_CHARS=0`（或 `16000`），使长思考内容能够完整展开并不受限地过渡到 JSON 正文。
2. **非临床探针验证**：
   在正式临床重放前，先使用非临床测试用例验证 HTTP 200 OK 与完整 JSON 结构输出。
3. **恢复真实方案控制重放**：
   在基础设施环境更新后，基于 v13 配置只执行一次新的同源重放，不扩大来源范围，不更换临床问题，不泄露期望答案。
