# Execution Context: phase5-stage-relative-lookback-20260902

Created: 2026-09-02 11:03:06 CST
Objective: 建立项目无关的节点相对回溯窗口机制：医学解释只澄清未命名锚点，正式条款阈值和逻辑不变；筛选与基线按各自节点日期形成独立评判实例，并为 SAR EX-07 的正式局部修订提供可审计入口。
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `zcode/glm-5.3-flash:max -> codebuddy-cli/deepseek-v4-flash:max -> mtplx/qwen3.8-flash-next-mtplx-optimized-speed:medium -> openai-codex/gpt-5.6-luna:xhigh`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `zcode` / `zcode` / `GLM-5.3-Flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md`、`.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}` 与 `CHECKPOINT_20260902_SAR_TARGETED_REPAIR_PAUSED.md`。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`、`plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`。
- `app/domain/interpretation.py`、`app/domain/contracts/{enums.py,protocol_metadata.py,rules.py,agent_io.py,protocol_drafts.py}`。
- `runs/execution/phase5-stage-relative-lookback-20260902/worker_01.md` 的只读合同审查结论。
- `app/agents/protocol_deconstructor.py`、`app/protocols/deconstruction_gate.py`、`app/services/{protocol_workbench_service.py,protocol_draft_service.py,protocol_publication_service.py}` 及其直接测试。
- 用户的项目级医学解释：未命名“6个月内”回溯条件在筛选审核节点以筛选日期为锚点，在基线审核节点以基线日期再次独立评判；不得改变原阈值、触发逻辑或官方编号。
- SAR 数据库、原始方案和受试者资料在本执行包中只读；不得直接写入或借项目内容驱动共享规则。

## Authorized Edits

- `app/domain/interpretation.py` 与上述直接领域合同中为表达项目无关节点相对锚点所必需的最小文件。
- `app/agents/protocol_deconstructor.py`、`app/protocols/deconstruction_gate.py`、`app/services/protocol_workbench_service.py` 及其直接依赖，仅限通用解释接入、提示框架、门禁与持久化入口。
- 对应 `tests/v2/protocols`、`tests/v2/services`、`tests/v2/storage` 下的词汇中立测试。
- 不授权修改 `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/**`、原始方案、原始受试者资料、既有临床报告或旧冻结检查点。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- 项目级医学解释只能澄清未命名时间锚点；不得冒充当前修订案，不得改写阈值、布尔逻辑、官方编号或目标审核节点集合。
- 没有解释来源时继续产生 `TIME_ANCHOR_UNRESOLVED`；解释越界或与方案冲突时失败关闭。
- 正式条件保持单一，逐审核节点生成可审计的评判实例/资料要求；筛选结果不得覆盖或替代基线结果。

## Codex Contract Decisions

- 新增项目无关锚点机器值 `review_node_date`，表示“当前 ReviewRun 所绑定审核节点的日期”；它不是筛选/基线默认值，也不能在缺少合法解释来源时出现。
- 在 `InterpretationSource` 的既有 `payload_json` 中增加可选结构化锚点解析列表；不新建表、不改现有镜像列。旧记录缺少该字段时按空列表读取，既有机器值与行数据不改写。
- 每条解析必须绑定父规则/原子引用、原歧义方案来源、目标审核阶段集合和唯一解析模式；不得携带或重写窗口量、方向、阈值、布尔逻辑、官方编号。
- 新增“审核节点实例化”这一受限解释变更类型，不纳入任意 `DUE_STAGE`/`WORKFLOW_NODE` 修改。只有方案确实未命名锚点、解释通过权威检查、目标阶段均为已有 WorkflowStage、且新增资料要求只复制同一条件的核对义务时允许。
- `ProtocolDeconstructionInput` 应携带经过仓储校验的完整解释来源，而不只传裸 ID；ID 集合必须与对象集合一致。解释摘录进入专用提示区，禁止进入方案 `source_text/source_excerpts/source_clauses`。
- Gate 必须验证：无解释仍报 `TIME_ANCHOR_UNRESOLVED`；`review_node_date` 仅在合法解析绑定下可发布；资料要求的 due_stage 集合覆盖解释声明的全部目标阶段；解释越权、来源/规则/谓词不匹配、目标节点不存在或解释冲突均失败关闭。
- 评判时由 ReviewRun/episode 注入 `anchor_dates[review_node_date]`；筛选和基线各自使用其权威元组与证据快照，不跨节点复用结果。若本执行包尚无 Phase 6 评判入口，仅完成合同与确定性验证，不伪造端到端完成。

## Work Items

1. 只读审查现有 InterpretationSource、草稿反馈、TimeConstraint、审核节点与发布门禁，提出最小通用合同和兼容边界，明确哪些临床语义不得写入共享代码。
2. 实现通用节点相对回溯窗口合同、项目级解释来源接入和确定性门禁；更新提示框架，使独立模型可依据显式解释生成一个正式条件及多节点资料要求，不直接修改 SAR 数据库。
3. 独立审查实现，使用词汇中立的合成协议验证筛选/基线独立锚定、节点历史不覆盖、无解释时失败关闭、解释越权被拒绝及反过拟合护栏；运行受影响与完整协议回归。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
