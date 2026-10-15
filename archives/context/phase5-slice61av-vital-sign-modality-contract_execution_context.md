# Phase 5.8d Slice 61av：生命体征操作模态合同

Created: 2026-08-29 19:04:21 CST
Task type: `finite_code_task`
Risk: `high`
Route schedule: `day`; packet branch recorded at creation in `Asia/Shanghai`.
Effective worker chain: `cursor/auto -> google-antigravity/gemini-3.7-flash:high -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> opencode-go/muse-spark-1.2-contributor:xhigh -> openai-codex/gpt-5.6-luna:max`

## 执行角色

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `auto`
- Execution manager: none (Codex reviews the worker outputs directly)

以上路由元数据补录自初始化器已生成的
`context/phase5-slice61av-vital-sign-modality-contract_execution_route_manifest.json`；
临床任务合同、执行提示和执行结果均未改写。

## 活动任务

`.trellis/tasks/08-22-phase5-clinical-facts-profile`

## 目标

用 D001 II 期原始方案 `body.p784` 至 `body.p786` 建立最小异质代表组，验证系统可同时保留：

1. 生命体征检查和体温、坐位血压、坐位脉搏、呼吸频率记录的明确必做要求；
2. “测量前，建议参与者至少休息5分钟”的推荐性准备，不得强化为硬性入排门槛；
3. “与PK采样时间一致时，尽量在PK样本采集之前完成”的尽力遵循顺序，不得强化为绝对先后；
4. `EX-21` 仅在异常、具有临床意义、研究者判断参与研究构成不可接受风险同时成立时触发，不得把操作偏离或单纯异常直接写成不符合。

## 来源闭包

Owned：

- `body.p784`：章节标题，仅结构定位。
- `body.p785`：检查项目、记录项和推荐休息准备。
- `body.p786`：与 PK 采样同点时的尽力顺序。

Read-only context：

- `body.t5.r10`：II 期流程表生命体征访视安排。
- `body.p321`：方案摘要“生命体征：筛选期”。
- `body.p684`：EX-21 合取排除条件。
- `body.p885`：D1 给药前结果作为基线值及基线资格复核。

不得读取或修改原始方案以外的项目特异答案，不得把父级检查清单注入模型提示。

## 三个独立执行项

### Worker 01：语义合同与最小实现

- 检查 `ControlObligationModality`、wire、hydration、publication gate 和 prompt 的现有合同。
- 以项目无关方式表达 recommended 与 best-effort 操作模态；不得写 D001、生命体征或条款编号特例。
- 保持 mandatory 与资料收集 best-effort 的既有行为兼容。

### Worker 02：确定性门禁与回归

- 添加“建议”不得硬化为 mandatory、“尽量”不得硬化为 mandatory 的正负向测试。
- 验证直接来源不支持时不得擅自降级模态。
- 验证操作模态与 EX-21 合取排除逻辑相互独立。

### Worker 03：真实来源代表组与批判性检查

- 新建最小 config/dry-run 来源冻结，不进行全量包运行。
- 核对流程目录覆盖：四项记录不得重复发布；推荐休息与尽力顺序应作为增量控制保留。
- 检查中文提示和持久证据，不得包含工程化用户文案。

## 完成标准

- 项目无关的结构、wire、门禁和提示词合同一致。
- 聚焦测试、协议模块全量回归、JSON 和差异检查通过。
- 真实来源 dry-run 证明来源闭包与已知目录无遗漏；只有在确定性合同通过后，才允许一次有界真实语义重放。
- 独立审阅确认没有把推荐/尽力要求强化为入排否决，也没有因此丢弃方案控制点。
- 不进入受试者、OCR、Patient Profile、浏览器或视觉阶段；`claims_complete=false`。
