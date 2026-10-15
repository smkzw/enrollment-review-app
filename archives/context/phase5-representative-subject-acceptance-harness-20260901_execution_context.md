# Execution Context: phase5-representative-subject-acceptance-harness-20260901

Created: 2026-09-01 03:32:56 CST
Objective: 为 Phase 5 建立最小、通用、可恢复的代表受试者验收路径：从只读原始受试者文件建立清洁隔离输入清单，复用现有 V2 证据处理、来源绑定视觉观察、真实 Evidence Normalizer、确定性门禁与 Patient Profile 投影，生成逐事件来源核对数据包。智谱独立视觉通道必须复用当前 OMP zhipu-coding-plan/glm-5.3-flash Coding Plan 接入合同；不得读取或写入凭据值，不得修改旧项目、旧缓存、旧 LLM 结果或暂停中的 D001 控制任务，不得写入 D001/SAR 项目特异临床规则。完成标准是最小实现、聚焦测试和父级可据此启动单一代表病例真实探针；本任务不宣称医学验收完成。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `night`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `zcode/glm-5.3:max -> openai-codex/gpt-5.6-luna:max -> codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor` -> `zcode` / `zcode` / `GLM-5.3`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读检查员：核对现有 V2 上传、证据修订、事实规范化、Patient Profile 与独立视觉通道的真实入口；以文件形态选择 D001 II SA01025 和 MG-K10-SAR III 31001 作为异质锚点，给出最短清洁隔离运行路线、现有能力和最小缺口。禁止修改代码或临床源文件，禁止引用旧 OCR/LLM 结果作为新输入。
2. 单一实现者：在不新增编排框架的前提下，补齐可复用的代表受试者验收清单/运行数据包能力及必要测试。输入必须是原始文件路径与内容哈希，输出必须显式记录隔离数据根、源只读指纹、运行权威、候选/发布/个例档案统计和逐事件来源核对项；不得硬编码疾病、药物、评分、日期或项目编号语义。优先复用现有服务/API；若现有能力已足够，仅补最薄的验收导出层。不要启动昂贵真实模型调用。
3. 独立对抗审阅者：只读检查实现及相关合同，攻击旧缓存复用、源文件变更、跨受试者/跨节点污染、无事实却假成功、无来源定位却发布、视觉观察替代 OCR、项目特异硬编码和人为宣称医学通过等失败模式；提出可执行的阻断测试和接受边界。禁止修改文件。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
