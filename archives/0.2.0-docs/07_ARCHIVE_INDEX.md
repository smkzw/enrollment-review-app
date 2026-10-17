# 0.2.0 ARCHIVE INDEX：0.1.x 历史材料索引

0.1.x（2026-06 至 2026-10-11）的全部过程材料已归档。**它们不是 0.2.0 的执行依据。** 其中仍有效的约束已提炼进 `01_PRD.md` §12.2，正常工作不需要打开归档。

只在以下情况查阅：要复用某个旧函数，需要了解它当初为什么这样写；要找某次真实运行的原始数据位置；用户明确要求追溯某个旧决定。查阅时只读具体条目，不要整体加载；归档中的"现行入口""当前 Goal""授权""预算账本""会商触发"等表述一律视为历史。

## 1. 位置

| 位置 | 内容 | 归档时间 |
|---|---|---|
| `archives/root/AGENTS.legacy.md` | 0.1.x 的 AGENTS.md（含 1006V1／0927V1-R1 文头） | 0.2.0 首次提交 |
| `archives/root/SYSTEM_REVIEW_REPORT.md` | 2026-06-25 v1 系统评审 | 同上 |
| `archives/root/DOCUMENTS_MAP.md` | 2026-09-20 文档地图（0.1.x 的阅读顺序） | 同上 |
| `archives/root/WP00_BASELINE_20260920.txt` | 0922 包基线 | 同上 |
| `archives/docs/` | `PROJECT_CONTEXT.md`（0.1.x 运行状态日志，4215 行）、`REARCHITECTURE_DISCOVERY_20260812.md`、`REARCHITECTURE_FINAL_DESIGN_20260812.md`、`REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md`、`v2/phase0*`（依赖与许可决策） | 同上 |
| `archives/context/ plans/ reviews/ metrics/` | 每个执行切片的上下文、计划、评审、度量四件套 | context／reviews／metrics 在首次提交归档；plans 在 0.2.0-WP0 |
| `archives/prompts/ conference/` | 会商与评审的 Prompt、回答 | 同上 |
| `archives/runs/ artifacts/` | 真实运行记录、会商记录、轻量日志 | 0.2.0-WP0 |
| `archives/trellis-tasks/` | 0.1.x 全部 Trellis 任务（PRD、design、implement、HANDOFF、CHECKPOINT、delivery 包） | 0.2.0-WP0（在此之前位于 `.trellis/tasks/`） |
| `archives/trellis-workspace/` | 开发者会话日志 | 0.2.0-WP0 |
| `archives/execution/` | 0.1.x 本机执行工件（被 `.gitignore` 忽略，只在原开发机上存在） | — |

## 2. 按问题查

| 想知道 | 去看 |
|---|---|
| v1 原型怎么跑通整批审核（2026-06），问题在哪 | `archives/root/SYSTEM_REVIEW_REPORT.md`；`archives/docs/PROJECT_CONTEXT.md` 中 D001／MG-K10 批次记录 |
| v2 重构为什么要建事实层、规则组件 | `archives/docs/REARCHITECTURE_DISCOVERY_20260812.md` |
| 规则谓词与事实类型交集为 0 的发现 | `…/09-11-e2e-eligibility-review/FINDING_20260911_FACT_TYPE_DISCONNECT.md` |
| 0.1.x 自己的复盘（目标置换、局部修复驱动） | `…/09-11-e2e-eligibility-review/RETROSPECTIVE_20261001.md`、`RETROSPECTIVE_20261004_1001V1.md`、`ENGINEERING_REVIEW_20260912_CODEX.md` |
| SAR 草稿 rev21、跨章 Job、31001 证据运行的 ID 与终态 | `…/09-11-e2e-eligibility-review/implement.md` 文件头（第 1–20 行）与 `HANDOFF_20261006_1001V1_PAUSE.md` |
| 2026-10-06 用户关于处方、"本次资料未见记录"、上传归属、档案展示的决定 | `…/09-11-e2e-eligibility-review/prd.md` 文件头（已提炼进 0.2.0 PRD §12.2、R-C6、R-C7） |
| 共享"医学经理工作台"对接现状 | `…/09-11-e2e-eligibility-review/WORKBENCH_ADAPTATION_20261007.md` |
| 研究流程表解析、双 VLM、局部视觉复核的设计缘由 | `…/09-05-phase55-dual-vlm-page-review/`、`…/08-22-phase5-clinical-facts-profile/` |
| 依赖许可决定 | `archives/docs/v2/phase0/DEPENDENCY_DECISIONS.md` |

`…` 在 0.2.0-WP0 之前为 `.trellis/tasks`，之后为 `archives/trellis-tasks`。

## 3. 0.1.x 版本名对照

| 0.1.x 名称 | 时间 | 含义 |
|---|---|---|
| Phase 0–5、5.5 | 08-12 至 09-19 | v2 重构分期；5.8 起扩展到全方案跨章控制 |
| V3（A/B/C 三链） | 09-17 | 方案链／资料链／审核链分工 |
| 0922 | 09-22 | 外部专家工作包 W0–W7 |
| 0927V1-R1 | 09-27 | 完整覆盖、混合执行、例外驱动 |
| 0929V1 | 09-29 | 原生结构优先＋局部视觉 |
| 1001V1 | 10-01 | 固定 workflow＋单一语义主责 |
| 1006V1 | 10-06 | 交付冻结窗口（一例工作稿＋一次更正），未达成 |
| **0.2.0** | **10-11 起** | **本版：细闭环，见 `docs/0.2.0/`** |
