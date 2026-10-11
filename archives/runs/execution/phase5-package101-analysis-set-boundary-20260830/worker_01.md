# Execution Output: phase5-package101-analysis-set-boundary-20260830 - worker_01

## Boundary And Context Check

- 按授权范围只读核验第101包相关冻结材料；未修改生产源文件、冻结候选、临床报告或生成文件。
- 冻结基线：`artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/`
- 协议版本：`D001-02-002:v1.0:phase-ii`
- 冻结选择期别：`phase_ii`
- 第101包：
  - owned：`body.p1179`、`body.p1186-p1196`
  - 本工作项只处理 owned 的 `body.p1179`，以及只读上下文 `body.p1180-p1185`
- 局部期别必须使用 `phase_scopes`：
  - `body.p1179`：`unknown`，结构标题
  - `body.p1180-p1181`：`phase_ii`
  - `body.p1182-p1185`：`phase_iii`
- 各单元的 `study_phase=phase_ii` 是冻结协议的整体选择期别，不能覆盖局部 `phase_scopes`，否则会把 III 期样本量设计误纳入 II 期。
- 官方个例入排/基线控制矩阵的真实锚点位于 `body.p630-p697` 等来源；`body.p1179-p1185` 不在官方控制矩阵的 source anchors 中。

## Work Performed

### 1. `body.p1179`：样本量章节结构边界

- 原文：`样本量计算`
- 结构路径：`统计学考虑 → 样本量计算`
- 所有权：第101包
- 语义：
  - 关闭上一节统计假设分支；
  - 开启后续 II/III 期样本量设计分支；
  - 本身不是样本量数值、入排标准、筛选动作或基线审核要求。
- 处置建议：
  - 保留为 `structural_only`；
  - 不生成控制候选；
  - 不绑定 `flow-screening`、`flow-baseline` 或 `flow-d1-pre-dose`。

### 2. `body.p1180-p1181`：II期样本量设计

`body.p1180` 是 `Ⅱ期临床阶段` 分支标签。`body.p1181` 明确包含：

- 第12周 PASI 75 应答比例为主要终点；
- II期主要目的为剂量探索；
- 样本量估算不做正式假设检验；
- 2个剂量组加安慰剂组；
- 随机比例 1:1:1；
- 每组预计40例，合计约120例。

这些语义不能被完全删除，但均属于：

- II期研究设计/样本量规划事实；
- 聚合层面的组别、比例和数量；
- 研究目的及终点背景。

它们不构成：

- 个体入选或排除条件；
- 预筛、筛选或基线审核动作；
- D1给药前资格判定；
- “证据不足不得入组”规则。

特别防止以下误读：

- “每组纳入40例”不是个体达到某条件后才可入组；
- “随机比例1:1:1”不是在完成资格核验前随机；
- “PASI 75应答”是第12周疗效终点，不是基线 `PASI≥12` 入选阈值；
- “不做正式假设检验”必须保留，不能从邻近 III期段落引入 Alpha、H0/H1 或优效检验。

### 3. `body.p1182-p1185`：III期样本量设计，只读对侧期别上下文

`body.p1182` 标示 `Ⅲ期临床阶段`。`body.p1183-p1185` 属于 III期，只读上下文，不能成为 II期候选来源。

#### `body.p1183`

保留的设计语义包括：

- 随机、双盲、安慰剂对照、优效设计；
- 第16周 PASI 75 应答比例；
- Deucravacitinib 两项 III期试验的 meta 分析数据；
- 试验组/安慰剂组应答率、差值及区间；
- 假定的安慰剂应答率和组间差异；
- 单侧 `α=0.025`；
- 2:1 随机比例；
- 两组共201例完成第16周评估；
- 99%把握度/效能设计语义。

这些是 III期统计设计、效能及外部参照假设，不是：

- II期控制；
- D001个体临床事实；
- 预筛或筛选标准；
- 基线 PASI/PGA/BSA 入选阈值。

“中度至重度斑块状银屑病”在此处是试验总体人群描述，不能替代官方入选标准中的研究者判断和具体阈值。

#### `body.p1184`

保留：

- III期 PGA-TS 第16周应答率及区间；
- 假定安慰剂应答率、差异；
- 201例和99%把握度；
- 单侧 `alpha=0.025`。

这些仍是 III期样本量/效能背景，不是基线 `PGA≥3` 控制，也不生成筛选或基线节点。

#### `body.p1185`

保留：

- III期设置2个剂量组和1个安慰剂组；
- 或基于II期结果确定推荐剂量组；
- 按20%脱落进行规划；
- 最多入组420例；
- 2:2:1分配；
- 每个试验组最多168例、安慰剂组最多84例，且不计转组治疗例数；
- 同时满足疗效与安全性分析需求。

这些属于总体试验规模、脱落假设和治疗分配规划，不是个体入排控制。特别不能将以下内容改写为个体规则：

- “最多入组420例”不能变成个体不符合即排除；
- “20%的脱落”不能变成筛选失败或证据缺口；
- “推荐剂量组”是未来基于II期结果的设计分支，不是当前个体资格条件；
- “满足安全性分析需求”不是安全性分析集定义，不能吸收或替代后续 `body.p1186-p1196`。

## Artifacts And Evidence

1. 冻结协议源文件  
   `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/source-input/blobs/protocol_sources/362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98.docx`

2. 冻结结构块  
   `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json`

3. 冻结覆盖清单  
   `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/coverage_manifest.json`
   - `body.p1179`：`phase_scopes=["unknown"]`
   - `body.p1180-p1181`：`phase_scopes=["phase_ii"]`
   - `body.p1182-p1185`：`phase_scopes=["phase_iii"]`
   - 目标原文和结构字段位于覆盖清单约第54564至54747行。

4. 冻结计划  
   `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/frozen_phase_plan.json`
   - 第101包拥有 `body.p1179` 和 `body.p1186-p1196`；
   - `body.p1180-p1185` 是第101包只读上下文；
   - 第102包从 `body.p1197`、`body.p1200-p1205` 开始，不能提前吸收。

5. 冻结元数据  
   `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/freeze_metadata.json`
   - `source_unchanged=true`
   - 源协议 SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`

6. 官方流程控制对照  
   `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-official-flow-controls.json`
   - 共58条控制记录，其中36条为官方入排记录；
   - 个例入排和筛选/基线控制真实锚点为 `body.p630-p697`；
   - `body.p1179-p1185` 与官方控制 source anchors 无交集。

## Commands And Observations

- 读取执行上下文和执行计划：确认本工作项为只读核验，不允许生产写入。
- 解析冻结结构块和覆盖清单：恢复 `body.p1179-p1185` 原文、结构路径、局部期别和 source order。
- 解析冻结计划：确认第101包 ownership 与只读上下文边界。
- 解析官方流程控制矩阵：
  - 58条记录；
  - 36条官方入排；
  - 目标页无官方控制锚点交集。
- 执行源文件哈希核对：

```text
shasum -a 256 artifacts/.../362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98.docx

362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98
```

- 执行只读边界断言，结果：

```text
PASS package101 target boundary: owned p1179; context p1180-p1185; II p1180-p1181; III p1182-p1185; zero official-control overlap
```

- 未运行项目测试、格式化或模型调用；本工作项没有代码或契约文件变更。

## Blockers Or Missing Environment

- 无环境阻塞。
- 未发现冻结源文件哈希漂移。
- 未发现目标页缺失或包所有权冲突。
- `body.p1183` 的完整原文可从冻结覆盖清单及源协议恢复；未进行任何文本补写或语义修复。

## Rerun Requests Or Next Step

建议 Codex 将以下内容作为第101包样本量子切片的零候选契约：

```text
owned_source_refs:
  - body.p1179

attached_context_source_refs:
  - body.p1180
  - body.p1181
  - body.p1182
  - body.p1183
  - body.p1184
  - body.p1185

required_candidate_source_refs: []
pre_enrollment_source_refs: []
workflow_stage_ids_by_source_ref: {}
known_official_targets: []
known_procedure_targets: []
forbidden_candidate_source_refs:
  - body.p1179
  - body.p1180
  - body.p1181
  - body.p1182
  - body.p1183
  - body.p1184
  - body.p1185
```

必须同时锁定：

1. `body.p1179` 仅为结构边界，保留 `su-16e9bca649de0099da16794e`，不得发射候选。
2. `body.p1180-p1181` 的 II期终点、剂量探索、1:1:1及约120例等设计事实不得删除，但不得转成个例入排控制。
3. `body.p1182-p1185` 只能作为 III期只读上下文，`α=0.025`、99%把握度、201例完成评估、20%脱落、420例及2:2:1分配不得倒灌到II期。
4. `PASI 75`/`PGA-TS`疗效终点不得与官方基线 `PASI/PGA/BSA` 入选阈值混同。
5. `body.p1185` 的“安全性分析需求”不得吸收后续 `body.p1186-p1196` 分析集正文。
6. 后续集成后由Codex运行第101包确定性门禁；本报告仅提供模型外语义证据，不代表临床或最终验收。
