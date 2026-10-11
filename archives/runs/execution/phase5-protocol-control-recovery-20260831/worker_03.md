# Execution Output: phase5-protocol-control-recovery-20260831 - worker_03

## Boundary And Context Check

- 已读取初始文件：
  - `context/phase5-protocol-control-recovery-20260831_execution_context.md`
  - `plans/codex_execution_phase5-protocol-control-recovery-20260831.md`
- 仅执行“恢复实现、提示词与合同边界独立审查”。
- 未读取其他 worker 报告，未修改源代码、测试、生产目录或临床资料。
- 未执行真实模型调用、真实方案解析、临床/监管验收；Codex 保留最终接受权。

## Work Performed

1. 审查恢复链路：
   - `scripts/run_protocol_control_smoke.py`
     - `_resume_existing_control_job`
     - `run_smoke`
     - `_read_persisted_source_chain`
     - `_control_metrics`
   - `app/workflow/jobstore.py`
     - 租约认领、检查点读取、`prepare_claimed`
     - `_reset_interrupted_steps`
     - `requeue_recovering`
   - `app/workflow/runner.py`
     - `run_job`
     - `prepare_claimed`
     - 已完成步骤跳过、执行器检查点回放、提交栅栏
   - `app/workflow/recovery.py`
     - 过期租约扫描与重新入队
   - `app/api/v2/app.py`
     - 启动恢复 wiring。

2. 审查提示词与合同：
   - `app/agents/protocol_control_deconstructor.py`
     - discovery/deep 输入合同
     - `_DISCOVERY_SYSTEM_CONTRACT`
     - `_CONTROL_AGENT_SYSTEM_CONTRACT`
     - 同会话定向修复合同
     - provider 输出身份、来源闭包和审核节点边界
   - `app/services/protocol_control_execution.py`
     - 持久 payload 冻结
     - discovery/deep 动态步骤生成
     - gate/hydrate 结果验证
   - `scripts/run_protocol_control_smoke.py`
     - 恢复参数互斥
     - `claims_complete`
     - formal catalog 边界记录。

3. 独立检查项目特异性：
   - 现有链级反过拟合测试覆盖两个 transport、control deconstructor、execution service、replay harness、两个脚本、运行时配置和 `.env.example`。
   - 未发现 D001、CMS-D001、SAR、疾病名称、药物名称、评分量表名称、项目特异时间点或数值阈值硬编码。
   - 提示词中的“药物”“评分”“首次给药”“基线”等是通用语义类别或结构化锚点，不是项目实例值。

4. 独立检查未完成结果边界：
   - 恢复记录始终写入 `claims_complete=False`。
   - gate 结果类型为 `hydrated_candidate_control_package`，正式目录状态为 `not_materialized`。
   - gate 使用空的 `PublishedProtocolControlCatalog` 作为闭包校验 scaffold，不返回、不持久化正式目录。
   - 未完成任务会因 `final_state != completed` 生成 `CONTROL_JOB_NOT_COMPLETED`，不会被标记为技术通过。

## Artifacts And Evidence

- 未创建或修改任何 artifact。
- 关键源码证据：
  - `scripts/run_protocol_control_smoke.py:678-911`：恢复只读取既有 SQLite、payload 和检查点，不重新打开方案文件。
  - `scripts/run_protocol_control_smoke.py:919-941`：`--resume-job-id` 与 fixture、期别和只读协议开关互斥。
  - `scripts/run_protocol_control_smoke.py:1100-1116`：控制任务未完成或水合结果缺失时生成失败码。
  - `scripts/run_protocol_control_smoke.py:1156-1167`：最终强制写入 `claims_complete=False`。
  - `app/workflow/jobstore.py:1315-1381`：有检查点的中断步骤恢复为 completed，无检查点步骤按尝试预算重新排队或终败。
  - `app/workflow/runner.py:229-247`：执行器收到持久 payload 和最后检查点。
  - `app/services/protocol_control_execution.py:791-910`：检查点回放只做合同校验，不重新调用模型或源文件。
  - `app/services/protocol_control_execution.py:1540-1615`：gate 明确输出候选控制点包，正式目录状态固定为 `not_materialized`。
  - `app/agents/protocol_control_deconstructor.py:1167-1430`：提示词合同要求受试者层面与组织治理义务分离，禁止凭项目名称、时点名称或相似文本建立候选。

- 测试证据：
  - `.venv/bin/python -m pytest -q tests/v2/services/test_protocol_control_execution.py tests/v2/services/test_protocol_control_smoke_runner.py`
    - `14 passed`
  - `.venv/bin/python -m pytest -q tests/v2/protocols/test_protocol_control_anti_overfit_chain_wide.py`
    - `17 passed`
  - `.venv/bin/python -m pytest -q tests/v2/protocols/test_protocol_control_generalization.py tests/v2/protocols/test_protocol_control_anti_overfit.py tests/v2/protocols/test_protocol_control_anti_overfit_chain_wide.py`
    - `48 passed`
  - `.venv/bin/python -m pytest -q tests/v2/workflow/test_recovery.py tests/v2/workflow/test_jobstore.py`
    - `29 passed`
  - `.venv/bin/python scripts/run_protocol_control_smoke.py --help`
    - 成功显示 `--resume-job-id` 入口及互斥参数说明。

## Commands And Observations

- `python -m pytest ...`
  - 失败：系统没有 `python` 命令。
- `python3 -m pytest ...`
  - 失败：系统 Python 缺少 `sqlalchemy`。
- `.venv/bin/python ...`
  - 成功；项目虚拟环境包含所需依赖。
- 反过拟合测试直接覆盖：
  - 项目/疾病/药物/评分量表/时间点词汇扫描；
  - discovery、deep、两类 repair prompt；
  - 合成 DOCX；
  - replay harness 工件；
  - `formal_catalog_materialized=False`；
  - `claims_complete=False`。
- 当前恢复回归证明已完成 discovery 批次不会再次调用 discovery transport，删除结构快照后仍可从持久 payload/checkpoint 继续 deep 步骤。

## Blockers Or Missing Environment

1. 系统 Python 环境不可直接运行测试：
   - `python` 不存在；
   - `python3` 缺少 `sqlalchemy`。
   - 已使用已有 `.venv` 完成全部聚焦检查；未安装任何依赖。

2. 现有回归未覆盖 `_resume_existing_control_job` 的完整运行记录路径：
   - 已覆盖底层 JobRunner/JobStore 恢复；
   - 尚未看到针对 CLI 恢复入口本身的“进程中断 + 删除源文件 + 恢复记录”专门测试。

3. 发现一个防御性合同缺口（代码推断，当前正常生成路径未触发）：
   - `scripts/run_protocol_control_smoke.py:876-885` 的恢复语义只判断 `result_kind is not None`，没有要求精确等于 `hydrated_candidate_control_package`；
   - 没有要求 `formal_catalog_status == not_materialized`；
   - 没有重新验证 `accepted is True` 或 gate payload 的完整候选闭包。
   - 对当前执行器生成的 gate 检查点，`app/services/protocol_control_execution.py:846-905` 已有严格回放校验；但恢复一个已完成 gate 的既有任务时，Runner 不会重新执行 gate，因此恢复入口自身可能接受旧版或异常但哈希有效的检查点。
   - 这可能造成 `semantic_acceptance.passed=True` 与正式目录状态字段不一致。未在当前测试中复现，属于需补强的边界。

4. 另一个溯源字段风险（代码推断）：
   - `_resume_existing_control_job` 将 `real_protocol_content_used` 固定为 `True`，但既有 control payload 未保存原始 fixture 是合成还是外部真实方案。
   - 对由合成协议创建的任务，恢复记录可能无法准确表达原始来源性质。
   - 不影响 `real_clinical_content_used=False` 或正式目录边界，但 provenance 语义不够精确。

## Rerun Requests Or Next Step

建议 Codex 在最终整合前补充以下确定性回归或收紧实现：

1. 恢复入口行为测试：
   - 创建多 discovery 批次任务；
   - 让一个 deep 动态步骤进程中断；
   - 删除冻结结构 blob；
   - 调用 `_resume_existing_control_job`；
   - 断言已完成 discovery 批次调用次数不增加、`source_file_read=False`、任务从持久检查点继续完成。

2. 恢复 gate 边界测试：
   - 构造已完成任务的异常/旧版 gate payload；
   - 断言恢复入口拒绝非候选 `result_kind`、正式目录状态或缺失 `accepted` 的检查点；
   - 恢复入口的技术通过条件建议改为精确匹配：
     - `result_kind == CANDIDATE_CONTROL_PACKAGE_RESULT_KIND`
     - `formal_catalog_status == FORMAL_CATALOG_STATUS_NOT_MATERIALIZED`
     - gate 接受状态和候选闭包均有效。

3. provenance 测试或合同调整：
   - 将原始 fixture 来源性质冻结到 control job payload；
   - 或将恢复路径无法确定的 `real_protocol_content_used` 改为明确的 unknown/null，而不是固定为 `True`。

4. 当前结论：
   - **反过拟合边界：通过现有静态与行为回归。**
   - **租约恢复与已完成批次不重复：底层回归通过。**
   - **正式目录/临床验收不被正常路径误报：当前生成路径明确阻断。**
   - **既有异常/旧版检查点的恢复防御：仍需 Codex 决定是否补强；不能据当前测试宣称已完成最终接受。**
