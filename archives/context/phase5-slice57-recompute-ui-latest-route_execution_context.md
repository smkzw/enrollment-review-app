# Execution Context: phase5-slice57-recompute-ui-latest-route

Created: 2026-08-23 16:49:32
Objective: 在已验收的事实修订合同与仓储上完成 Slice 5.7 剩余工作：确定性影响范围、持久增量重算服务/API及中文宽屏修订界面，并覆盖重启、取消、迟到回包、重复回调和局部失败；不进入入排结论。
Task type: `long_horizon_code`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `grok` / `grok-build` / `grok-4.6`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md`、`.trellis/workflow.md`、`.trellis/spec/backend/**`、`.trellis/spec/frontend/**`。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` §4.2、§4.3、§7.2、§7.3、§8；`plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` Phase 5。
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}`，尤其设计 §6 与 P5-AC08/P5-AC11。
- 已由 Codex 独立验收的 Slice 5.7 前置合同：`app/domain/contracts/fact_corrections.py`、`app/storage/fact_correction_repository.py`、`app/storage/facts_models.py`、迁移 `0017_fact_corrections.py` 及对应测试；组合回归为 `161 passed`。后续工作不得重新设计或削弱其不可变谱系、类型化外键、快照和幂等约束。
- 现有运行与投影基础：`app/workflow/{jobstore.py,runner.py}`、`app/services/{fact_normalization_job_service.py,fact_publication_service.py,patient_profile_service.py}`、`app/storage/{fact_rule_link_repository.py,patient_profile_repository.py}`、`app/api/v2/patient_profiles.py`、`frontend/src/api/patient-profile/**`、`frontend/src/pages/SubjectsPage.tsx`、`frontend/src/components/profile/**`。
- 不读取或修改工作树外真实项目、原始方案、受试者资料、旧临床报告或生产数据库。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- 不修改原 OCR、原文校对、Normalizer 候选、既有事实/事件/暴露、冲突、资料期望或历史 Profile；修订只能追加新实体、新修订记录与新 Profile revision。
- 影响范围只能沿显式 locator、逻辑文档/文档版本、实体引用、FactRuleLink、资料期望和 Profile revision 反向索引传播。任一必要反向链不存在、越过冻结权威或无法证明闭包时，必须返回 `node` 范围和中文回退原因；不得使用自由文本、相似度或模型猜测缩小范围。
- 后期资料不得改写早期审核节点链头。历史 Profile 必须按原 revision 和原权威元组完整读取。
- 复用现有持久 Job/Step/Checkpoint/Lease/PreparedStepResult；任务成功提交时，新实体、修订记录、新 Profile 与检查点同一写栅栏事务提交。取消只在安全边界生效；租约丢失、迟到结果、重复回调和局部失败不得产生重复实体或永久处理中。
- 本切片不生成入选/排除、通过/不通过、洗脱期裁决、ActionRequest、责任方任务或 ReviewRun 主结论。

## Ordered Dependencies And Write Sets

1. `worker_01` 先冻结影响范围规划器和必要的只读反向查询。可写：新增 `app/domain/planning/fact_correction_impact.py`、必要的最小共享仓储查询扩展及对应 `tests/v2/domain|storage/**`。不得写服务、API 或前端。
2. Codex 验收 worker_01 后再运行 `worker_02`。可写：新增/修改人工修订服务、持久任务服务、`app/api/v2/*` Schema/路由注册、必要的服务与工作流测试；除修复明确缺陷外不得改 worker_01 规划合同或 `0017`。
3. Codex 验收真实后端合同后再运行 `worker_03`。可写：`frontend/src/api/patient-profile/**`、`frontend/src/components/profile/**`、`frontend/src/pages/SubjectsPage.tsx`、`frontend/src/styles/profile.css` 及对应单元/E2E 测试；不得改后端。

### Worker 01 已验收前置合同（2026-08-23）

- 事实修订预览和提交必须用拟发布新事实的 `fact_type + supported_requirement_ids` 构造 `FactReplacementSignature`；事实起点缺少替换签名时只能回退整个审核节点，不能默认局部重算。
- 局部影响范围已显式保留 `affected_conflict_group_ids`。服务提交、检查点、API 与后续界面不得丢弃该集合。
- 规则签名变化时，只有旧/新两侧资料要求、模板及每模板当前期望的反向闭包都可证明，才允许局部范围；否则使用节点级重算。
- 图装载已通过批量定位镜像和规则链接读取，4 条与 16 条带真实规则链接事实的 SELECT 数均为 132；服务不得重新引入按事实逐条读取。

## Done Signals

- 一个定位修订只重算结构化反向索引可证明相关的事实、事件/暴露、规则链接、资料期望和 Profile；任一断链确定性扩大到整个审核节点。
- 旧 Profile revision 在新修订成功、失败、取消和恢复后均保持可读且内容不变；新的活动结果只在完整事务成功后可见。
- 服务重启、租约丢失、取消、迟到回包、重复请求/回调和局部失败均有故障注入回归，无重复发布、悬空修订或永久处理中。
- 中文界面提交前并列显示原值、来源原文、拟修改内容、理由和影响范围；提交后可回看新旧历史，不出现程序员枚举、英文日志或 Phase 6/7 结论。
- Codex 最终运行受影响层与全量回归，并在真实最大化 1080P、2K、4K 浏览器中验收；Phase 5.8 独立测试者仍不得提前启动。

## Work Items

1. 影响范围：沿定位、文档、事实引用、规则索引和历史Profile反向索引证明局部闭包，无法证明时明确回退整个审核节点。
2. 执行与接口：基于持久Job/Step/Checkpoint/Lease/PreparedStepResult原子生成新实体、修订记录和新Profile，覆盖恢复、取消、迟到结果、重复回调与局部失败。
3. 用户界面：在Patient Profile提供中文原生事实修订预览、理由、来源、影响范围和历史回看，并完成宽屏浏览器验证。

## Worker 02 已验收执行合同（2026-08-23）

- 人工修订使用持久 Job/Step/Checkpoint/Lease/PreparedStepResult；新实体、修订记录、冲突谱系、资料期望、新 Patient Profile 与本笔提交栅栏在同一租约写事务内原子提交。
- apply 在提交前重新校验冻结权威、活动修订链头、旧语义快照和最新影响图；计划检查点只可被保守放宽，不能缩窄实际影响范围。
- 活动规则索引排除已替代事实；事实修订会为引用它的事件/暴露追加当前 revision，并为受影响冲突追加后继或显式解决谱系。未变化冲突不制造冗余后继。
- 冲突是否仍存在按完整临床身份、值/极性、日期与持续状态确定性比较；后继冲突的门禁必须来自当前成员，禁止复用已替代成员门禁。
- 提交栅栏精确绑定本笔 Patient Profile revision；创建与读取均复核父修订、Profile、冲突组的同权威闭包及类型化谱系镜像。旧实体、旧冲突组和旧 Profile 保持不可变可回看。
- Codex 独立验收：聚焦及相邻后端套件 `124 passed, 5 warnings, 2 subtests passed`；changed-module compileall 与 `git diff --check` 通过。前端不得绕过这些 API/状态语义，也不得在浏览器端伪造修订成功。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
