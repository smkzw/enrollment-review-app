# Phase 5.8d MTPLX 默认语义路由验收

**时间**：2026-08-27 10:20 CST  
**分支**：`codex/phase5-clinical-facts-profile`  
**执行任务**：`phase5-mtplx-default-semantic-agent-20260827`

## 已接受结果

- 后续内置语义 Agent 默认统一为 `MTPLX/mtplx-qwen38-27b-optimized-quality:medium`：入排审核、方案解构、期别适用性判断和证据规范化均使用该身份。
- OCR 仍独立使用 oMLX，默认并发与 OCR 模型不变；误把 MTPLX 配成 OCR 后端时明确拒绝，不静默替换。
- MTPLX 默认地址统一为 `http://127.0.0.1:8002`，与当前 oMLX OCR 服务隔离；启动器要求 `/v1/models` 精确公布目标模型 ID。
- 本地方案解构与证据规范化均使用严格 JSON Schema；本地方案批次输出上限固定为 8192，避免继承旧 60,000 token 配置。
- 活动 Phase 5 单批探针 harness 已改用 MTPLX 默认值，并保留显式 backend/model/effort 覆盖能力。历史运行脚本、失败反例和既有临床产物未改写。

## 真实运行证据

- MTPLX 2.9.2 成功从本机缓存加载 `Youssofal/Qwen3.8-27B-MTPLX-Optimized-Quality`，服务 ID 精确为 `mtplx-qwen38-27b-optimized-quality`。
- 首次严格 Schema 请求返回 HTTP 400，根因不是模型，而是 MTPLX 基础安装缺少其官方 `server` 可选依赖 `llguidance>=1.7`；已在 `~/.mtplx/venv` 安装 `llguidance 1.8.0`。
- 补齐依赖后，真实探针在 `http://127.0.0.1:8002/v1` 通过：仅公布 1 个目标模型，`reasoning_effort=medium`，严格 JSON Schema 有效，返回模型身份完全一致，完成耗时约 1.99 秒。
- 应用配置实测：review/deconstruct/normalizer 均为 `mtplx` + 目标模型 + `medium`，`OCR_BACKEND=omlx`，`check_mtplx()` 返回 `true`。

## 验证

- 聚焦回归：`71 passed, 5 warnings`。
- `py_compile`、四个启动脚本 `zsh -n`、`git diff --check` 均通过。
- governed execution audit 通过，执行者未替代 Codex 宿主机真实验收。

## 明确边界

- 根目录旧系统 `.env` 仍显式选择 DeepSeek；本轮未修改，因为旧根目录代码尚未合并 MTPLX 适配器，提前改动会破坏当前旧入口。
- 桌面入口仍指向 V2 静态界面 UAT 启动器，不是本轮语义 Agent 服务入口；待 Phase 5 代码整合到主工作树后再同步桌面入口和运行 `.env`。
- 本轮只接受默认语义路由和真实严格结构化连通性，不接受 D001 全文语义闭包；`claims_complete=false`，剩余 134 包、受试者、浏览器和独立测试者均未启动。

## 下一安全动作

继续 Phase 5.8d 时，在新的不可变产物目录用当前 MTPLX 路由重跑已选的少量异质代表包，先比较结构接受率和临床理由质量；不得直接全跑 137 包，也不得覆盖旧 oMLX 诊断产物。
