# Execution Context: r05-official-proposition-source-20260915

Created: 2026-09-15 11:07:02 CST
Objective: 为所有者接通官方谓词的受限原文命题消费，实施来源合同/生产端小单元；并非临床采信或独立测试。遵守本树指令、apply_patch、保留全部无关脏工作。用户禁止阶段测试，不写或运行测试、样例探针、import应用、DB/服务/模型/浏览器，不递归派发。
Task type: `E03`
Risk: `high`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> pi/mtplx/mtplx-flash-next-optimized-speed:xhigh -> pi/openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `deepseek-v4.1-flash`
- Review owner: Codex directly reviews worker outputs and final artifacts.

## Source Of Truth

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. 仅允许修改 app/domain/contracts/rules.py、app/agents/protocol_deconstructor.py、app/protocols/deconstruction_gate.py、app/services/protocol_draft_service.py；其他文件只读。AtomicPredicate增可选semantic_proposition:str非空（旧None序列化省略，保留旧内容身份），显式表达需要来源含义核实的命题；只允许comparator=exists/value=None/unit=None、不与requires_professional_judgment混用（研究者仍走原专属链），不允许occurrence_window与该字段混用；允许prospective_period/prospective_window，未来命题不再伪造数值直接比较。不得从旧字段自动补命题。生产wire新增必填nullable字段，解析/草稿编辑白名单/持久化映射完整保存；系统提示说明语义原方向、与数字日期计算分离、按方案来源保留限定条件、不能把意愿当已履行；不硬编码项目疾病药物。研究者判断不改含义，复杂复查仍明确未核实，不借本字段跳过。更新当前wire版本与发布门版本使旧工件不能假冒新生产方法，历史读取保留；不要更改稳定系统ID种子。检查合法新产物从wire到RuleComponent来源校验及草稿编辑是否丢字段，门拒新生产缺字段/来源不闭合，但不要把机械substring当语义真实性。仅实现以上来源单元；消费者由所有者整合后统一审阅，不能宣布端到端完成。返回修改清单、明确静态未运行边界、相邻必改点。

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
