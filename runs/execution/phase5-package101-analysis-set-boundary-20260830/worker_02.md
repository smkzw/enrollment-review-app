# Execution Output: phase5-package101-analysis-set-boundary-20260830 - worker_02

## Boundary And Context Check

- 已读取初始执行上下文与计划。
- 本轮严格限定为 `body.p1186-p1196`，仅核验：
  - 分析集定义；
  - 盲态数据审核及分析集划分时点；
  - 统计软件；
  - 一般描述性统计及 MedDRA/WHO Drug 编码。
- 未处理 `body.p1179` 样本量内容；该段由其他工作项负责。
- 未吸收 `body.p1197`、`body.p1200-p1205` 等第102包内容。
- 未修改冻结候选、源方案、既有临床报告或生产文件。
- 未调用临床语义模型、未运行语义包、未发布控制点。

冻结身份：

- `plan_id`: `papl-e17d498106b6f71f440ff2be`
- 第101包：`pap-b0e90038f781b39606b42df9`
- `protocol_version_id`: `D001-02-002:v1.0:phase-ii`
- `snapshot_id`: `d001-ii-phase-closure-20260830-slice61cm-phase-context-boundary-rebaseline-snapshot`
- `claims_full_coverage`: `false`

## Work Performed

### 1. 核验第101包目标来源

冻结计划显示第101包拥有：

```text
body.p1179
body.p1186
body.p1187
body.p1188
body.p1189
body.p1190
body.p1191
body.p1192
body.p1193
body.p1194
body.p1195
body.p1196
```

本轮目标的11个来源全部且仅由第101包拥有，顺序连续，未发现重复所有权。

覆盖清单中：

- `body.p1188` 关键词索引含 `基线`、`随机`；
- `body.p1189-p1191` 关键词索引含 `随机`；
- `body.p1192` 的 `phase_scopes` 为 `["mixed"]`，因为正文同时提及Ⅱ期和Ⅲ期基础研究阶段；
- 关键词命中和混合期别标签均属于索引/来源属性，不构成筛选或基线控制点。

### 2. 分析集语义闭合

| 来源 | 原文语义 | 临床语义处置 | 越界风险 |
|---|---|---|---|
| `body.p1186` | “统计分析集的定义” | 章节标题，建议 `structural_only` | 不得独立发射候选 |
| `body.p1187` | “统计分析数据集：” | 统计集定义引导语；无独立受试者规则，建议按结构/引导语处理 | 不得生成筛选或基线任务 |
| `body.p1188` | ITT包括所有随机化参与者，按随机分配治疗组分析；用于人口学、基线和有效性 | 随机化后的统计分析人群定义 | “基线”仅指分析领域，不是基线访视必做或基线缺失入排条件 |
| `body.p1189` | SS = 随机化 + 至少一次试验用药 + 至少一次用药后安全性评价；按实际治疗分析 | 随机化后、给药后安全性分析集定义 | 不得改成必须给药、必须完成安全性检查或未给药不得入组 |
| `body.p1190` | PKCS = 随机化 + 至少一次 CMS-D001 给药 + 至少一个有效给药后血浆浓度 | 随机化后、给药后 PK 数据分析集定义 | 不得生成筛选期 PK 必做、随机前采样或无 PK 样本不得入组 |
| `body.p1191` | PDS = 随机化后至少一次给药 + 至少一个有效给药后 PD 数据 | 随机化后、给药后 PD 数据分析集定义 | 不得生成基线 PD 必做或无 PD 数据不得入组 |
| `body.p1192` | Ⅱ期及Ⅲ期基础研究阶段的分析集划分和各集剔除名单，在盲态数据审核后、数据库锁库和揭盲前确定 | 统计/数据管理时点 | “剔除分析集名单”不是“排除受试者名单”；不得改成筛选、随机或给药前资格复核 |
| `body.p1193` | “统计分析” | 章节标题 | 不得独立发射候选 |
| `body.p1194` | “一般方法” | 章节标题 | 不得独立发射候选 |
| `body.p1195` | 疗效及安全性分析使用 SAS 9.4+；PK 参数使用 WinNonlin 8.1+ | 统计软件背景 | 不形成任何受试者级执行义务 |
| `body.p1196` | 连续/分类变量描述统计；疾病史和 AE 用最新版 MedDRA 按 SOC/PT 汇总；合并药物用最新版 WHO Drug 编码 | 统计汇总及编码方法 | 不得改成病史筛查、药物禁用、编码缺失不得入组或基线必查 |

逻辑骨架应保持为：

```text
ITT  = randomized
SS   = randomized AND >=1 dose AND post-dose safety evaluation
PKCS = randomized AND >=1 CMS-D001 dose AND >=1 valid post-dose concentration
PDS  = randomized AND >=1 dose AND >=1 valid post-dose PD datum
```

其中：

- ITT 按随机分配治疗组分析；
- SS 按实际接受治疗分析；
- 两者不可混写为同一治疗分配规则；
- `randomized`、`dose`、`post-dose data` 是分析集归属条件，不是研究者必须为入组者完成的筛选动作。

### 3. 盲态审核时点攻击

`body.p1192` 的时间关系仅为：

```text
盲态数据审核后
→ 确定分析集划分及各分析集剔除名单
→ 数据库锁库和揭盲之前
```

应保留以下边界：

- 该时点约束的是统计分析集确定及其剔除名单；
- “剔除某分析集”不等于退出试验、不符合入选标准或筛选失败；
- 正文未要求在随机前完成盲态审核；
- 正文未要求在入组前批准分析集；
- 正文未定义盲态审核的具体操作内容，不得自行补写研究者资格复核、D1 给药前复核或 SAP 入组前批准。

### 4. 一般统计方法与编码攻击

`body.p1195` 只指定软件最低版本：

- SAS `9.4` 或以上：疗效和安全性统计分析；
- WinNonlin `8.1` 或以上：PK 参数统计分析。

`body.p1196` 只指定：

- 连续变量：观测数、均数、中位数、标准差、最大值、最小值；
- 分类变量：参与者例数和百分比；
- 疾病史及 AE：最新版 MedDRA，按 SOC/PT 汇总；
- 合并药物治疗：最新版 WHO Drug 编码。

因此：

- MedDRA 编码方法不等于新增病史采集或疾病诊断资格判断；
- SOC/PT 是汇总维度，不是严重程度阈值、排除标准或筛选结论；
- WHO Drug 编码方法不等于合并用药禁用、洗脱期或随机前药物审核；
- “最新版”不能被擅自固化为其他段落出现的具体版本号；
- `body.p1196` 未规定缺失值处理，不能从其他统计段落补入本轮语义。

## Artifacts And Evidence

已读取并核对：

1. `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/frozen_phase_plan.json`
   - 第101包 ID 与拥有来源；
   - 目标11段均归第101包；
   - 第101包整体拥有12段，另含由其他工作项处理的 `body.p1179`。

2. `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/coverage_manifest.json`
   - 目标11段均有覆盖单元；
   - 目标顺序为 `body.p1186` 至 `body.p1196`；
   - `claims_full_coverage=false`；
   - 关键词索引中的“随机”“基线”未被误当成控制点。

3. `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json`
   - 找到目标11个结构块；
   - `body.p1186`、`p1193`、`p1194` 为标题结构；
   - `body.p1187` 为统计集引导语；
   - `body.p1188-p1196` 原文与覆盖清单摘要一致。

4. `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/source-input/blobs/protocol_sources/362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98.docx`
   - 冻结源方案输入。

5. `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/freeze_metadata.json`
   - 原始 DOCX SHA-256：
     `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
   - 冻结计划 SHA-256：
     `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
   - 结构块 SHA-256：
     `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`
   - `source_unchanged=true`。

6. `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-official-flow-controls.json`
   - 官方流程/入排矩阵共58行；
   - 目标 `body.p1186-p1196` 没有直接作为任何官方流程控制行的 source anchor；
   - 因此不能从目标段新增筛选、基线或 D1 给药前流程节点。

7. 相邻第100包契约与测试：
   - `representative_group_package100_statistical_hypothesis_phase_boundary.v1.json`
   - `test_slice61cm_package100_statistical_hypothesis_phase_boundary.py`
   - 已沿用其 `required_candidate_source_refs=[]`、`pre_enrollment_source_refs=[]`、零流程节点、零官方规则及“统计背景不得倒置为入排条件”的模式。

**建议的目标片段零候选契约：**

```json
{
  "owned_source_refs": [
    "body.p1186", "body.p1187", "body.p1188", "body.p1189",
    "body.p1190", "body.p1191", "body.p1192", "body.p1193",
    "body.p1194", "body.p1195", "body.p1196"
  ],
  "required_candidate_source_refs": [],
  "forbidden_candidate_source_refs": [
    "body.p1186", "body.p1187", "body.p1188", "body.p1189",
    "body.p1190", "body.p1191", "body.p1192", "body.p1193",
    "body.p1194", "body.p1195", "body.p1196"
  ],
  "pre_enrollment_source_refs": [],
  "structural_only_source_refs": [
    "body.p1186", "body.p1187", "body.p1193", "body.p1194"
  ],
  "expected_workflow_stage_ids_by_source_ref": {},
  "known_targets": {
    "official_rules": [],
    "required_procedures": []
  }
}
```

建议将 `body.p1188-p1192`、`body.p1195-p1196` 作为统计/行政背景事实保留，而不是删除来源含义；零候选表示“不发射受试者控制候选”，不表示“零来源事实”。

## Commands And Observations

- `functions.read`
  - 读取执行上下文、执行计划、冻结计划、覆盖清单、冻结元数据、源 DOCX、官方流程矩阵、相邻包契约和测试。
  - 观察：目标11段均可稳定回源，未发现源文本缺失。

- `functions.grep`
  - 搜索 `body.p1186`、`body.p1196`、第101包身份及相邻边界。
  - 观察：第101包拥有目标段；第100包和第102包边界可区分。

- `functions.eval`
  - 解析冻结计划、覆盖清单、结构块、官方流程矩阵及执行状态。
  - 观察：
    - 目标11段均由第101包单一拥有；
    - 目标段在官方流程矩阵中直接锚定行数为 `0`；
    - 第101包当前执行记录为 `pending`，`raw_output_sha256=[]`，`run_results=[]`，未发现既有语义模型输出。

- `functions.eval` 指纹和映射断言：
  - 原始 DOCX、冻结计划、结构块哈希均与 `freeze_metadata.json` 一致；
  - 目标段所有权与顺序断言通过；
  - 输出：`fingerprints_and_target_mapping: PASS`、`target_ownership: PASS`。

- `bash wc -l artifacts/.../frozen_phase_plan.json`
  - 观察：冻结计划为大体量 JSON，使用定点解析而非全量终端展开。

未运行项目级测试、格式化、模型调用或生产命令。

## Blockers Or Missing Environment

无环境阻塞。

限制说明：

- 本轮只读核验，不创建配置文件或测试文件；
- 未对第101包完整契约作最终合并；
- `body.p1179` 样本量段及第102包后续统计分析段未纳入本轮结论；
- 本报告是 Codex 的证据输入，不是最终临床、监管或用户验收。

## Rerun Requests Or Next Step

建议 Codex 在父级契约中锁定以下最小不变量和反例：

1. `required_candidate_source_refs == []`。
2. `pre_enrollment_source_refs == []`。
3. `expected_workflow_stage_ids_by_source_ref == {}`。
4. `known_targets.official_rules == []` 且 `required_procedures == []`。
5. 目标11段全部进入 `forbidden_candidate_source_refs`。
6. 保留四类分析集的随机化/给药后/有效数据 AND 关系。
7. 保留 ITT“按随机分配治疗组”与 SS“按实际治疗”之间的差异。
8. 保留 `body.p1192` 的盲态审核后、数据库锁库和揭盲之前时点，不改写为随机前或入组前。
9. 保留 `body.p1195` 的 SAS 9.4+ 与 WinNonlin 8.1+，不引入其他软件职责。
10. 保留 `body.p1196` 的 MedDRA `SOC/PT` 和 WHO Drug 编码方法，不生成病史筛查、合并用药禁用或基线必查。
11. 测试应拒绝以下反例：
    - “基线缺失不得入组”；
    - “未随机不得进入筛选”；
    - “未给药不得入组”；
    - “无安全性评价不得随机”；
    - “无 PK/PD 数据不得入组”；
    - “盲态审核必须在随机前完成”；
    - “SAP/分析集未定稿不得入组”；
    - “MedDRA/WHO Drug 编码缺失不得入组”。

父级合并时应保留其他工作项对 `body.p1179` 的处理，并继续将 `body.p1197`、`body.p1200-p1205` 留给第102包；不得因第101包统计章节连续性而吸收相邻包来源。
