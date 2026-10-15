<!-- RV1006-AGENT:BEGIN -->
现行执行入口：.trellis/tasks/09-11-e2e-eligibility-review/delivery_1006V1/00_START_HERE.md；用户2026-10-06明确恢复实施。仅维护implement文头一张当前用户流程表。窗口终点为完整同源范围下的一例隔离当前节点工作稿、原件回源、一次有源更正/补证、新旧结果；仅直接阻断或错误采用保护修复准入，不默认继续扩展恢复/通用能力。R1、1001V1及历史边界继续有效，旧暂停交接不代表当前Goal；正式事实自动采用、规则激活与临床签发不因窗口认可获授权。共享事务单一所有者；必要会商按全局触发，routine修复不增加多轮会商。达到本窗口先回交，不自动扩大优化。
<!-- RV1006-AGENT:END -->

<!-- ENROLLMENT-0927V1-R1:BEGIN -->
> **现行产品规范已更新：0927V1-R1（2026-09-27，用户已确认）。**
> 入排子系统采用“完整覆盖、混合执行、例外驱动、先闭环再扩展”。完整有源包可保留严格的真实未决/能力缺口；独立已核工作稿继续，受影响项不假判通过。已知错义、来源缺失、越界和损坏仍硬拒绝；官方与相关跨章同源共同纳入。
> R1历史决策入口：`.trellis/tasks/09-11-e2e-eligibility-review/delivery_0927V1_R1/00_START_HERE.md`；现行窗口以上方1006V1为准，需求/设计/排序/验收为同任务 `prd.md`、`design.md`、`plan.md`、`acceptance.md`。旧“等待该宏观确认”、全机器化前置、旧模型默认和旧串行排序不再作为现行指令。
> 下方内容保留为历史或不冲突技术参考，不代表当前完成。规范批准不等于代码迁移、临床验证、规则激活或签发；不自动恢复暂停Goal。更高层安全/工具权限和原件保护不变。
<!-- ENROLLMENT-0927V1-R1:END -->

<!-- ENROLLMENT-0927V1-R1-AGENT:BEGIN -->
## 当前Agent接续裁定

不再重复征询混合执行宏观边界。按 `.trellis/tasks/09-11-e2e-eligibility-review/plan.md` 的P1–P3实施，最多两线并行；历史回归资产按受影响范围复用，不每轮叠新框架/长作业。技术能力缺口归开发，真实医学未决归相应责任方。用户要求安装本包时，只更改规范；后续真实调用/写入/发布按实际授权。以下Trellis、来源、安全、会商和工具路由约束完整保留；本段不改变工具使用权限。
<!-- ENROLLMENT-0927V1-R1-AGENT:END -->

# Enrollment Review Project Instructions

Current execution supplement: `.trellis/tasks/09-11-e2e-eligibility-review/delivery_1006V1/00_START_HERE.md`. The approved 0927V1-R1 and 1001V1 boundaries remain in force; prior native-structure-first and selective-visual results remain scoped evidence, not proof of clinical acceptance. Current status is recorded in the task's `implement.md`.

## Current Phase

- The approved rearchitecture is under implementation in `.trellis/tasks/09-11-e2e-eligibility-review/`; use its current PRD, design, implementation record, and the live user request for scope and status.
- Keep `docs/REARCHITECTURE_DISCOVERY_20260812.md`, `docs/PROJECT_CONTEXT.md`, and the active task/conference context as durable historical decision sources. Historical review notes do not by themselves authorize a new clinical job or publication.

## Clinical And Evidence Boundaries

- Never modify source protocols, raw subject documents, manual IE trackers, or existing clinical reports.
- Legacy projects are read-only counterexample and regression anchors. New architecture work must create fresh projects from source inputs.
- Protocol and current amendment are authoritative. Q&A, letters, email, and medical interpretation may clarify ambiguity but cannot change or override the protocol/current amendment.
- Preserve official IN/EX numbering and parent/child logic. Do not hardcode project-specific clinical fixes into shared rules.
- Separate rule judgment from gap reason. Do not collapse record incompleteness, missing source file, unperformed procedure, professional judgment, conflict, OCR risk, or future-stage requirement into one status.
- Preserve source file, document version, page, exact excerpt, and image/text location for every material fact and rule assessment.
- The application is AI-led but is not the final enrollment decision authority. Every unresolved item needs a specific responsible party, action, acceptable evidence, due stage, and rule/source locator.

## Product Boundaries

- Target: local single-Mac, single-user, direct launch without login or multi-account ownership behavior.
- Support immutable full evidence snapshots and deduplicated incremental uploads.
- Later-stage evidence must not silently rewrite an earlier-stage result.
- Use source-preserving OCR/fact correction with affected-scope reruns and history.
- Design Patient Profile as the source-linked longitudinal view from earliest evidence through the current prescreen/screen/baseline cutoff.

## Engineering And Verification

- Prefer structured domain models and deterministic validators for logic, dates, units, state, and audit behavior. Use bounded Agents only for semantic tasks.
- Use `apply_patch` for manual text/code edits. Preserve unrelated user changes.
- Verify user-facing UI in a real browser at representative 1080P, 2K, and 4K desktop viewports.
- The product targets maximized wide-screen desktop use only. Do not add mobile or narrow-screen interaction variants; keep layouts fluid across desktop DPI and browser zoom, and avoid fixed pixel dimensions as the primary layout strategy.
- Update task context and `docs/PROJECT_CONTEXT.md` at material milestones.

## Conference Boundary

- Conference participants are read-only advisers. They must not modify source or application files and must not read raw clinical material outside this workspace.
- Codex owns final synthesis, clinical/product acceptance, and user delivery.

## Codex Dispatch Boundary

- Trellis Codex implementation, checking, and research are inline in this project. Do not dispatch a native child directly from a Trellis workflow prompt.
- A native Codex child is permitted only from a workflow packet created by `/Users/smkzw/.codex/tools/hermes_workflow_guard.py`; the packet must provide an explicit model and reasoning effort that match the live route.
- Never call `multi_agent_v1__spawn_agent` with an omitted model or effort, and never let a child inherit the parent session's model or effort. `agent_type` alone is not a route.
- If the live route has no Codex subAgent node, keep the work inline or use the packet's declared CLI fallback after a verified native transport failure.

<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->
