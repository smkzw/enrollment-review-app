# Conference Output: enrollment-rv1001-numeric-unit-partition-20261006 - evidence_single_object

## Output

### 角色、范围与结论

- 实际角色：`evidence_single_object`，声明的 `pi` fallback，`openai-codex / gpt-6.1-sol`。未调用 Grok Build，不声称提供独立 Grok 模型视角。
- 完成一次有界只读审阅及内存中合成数据实验。未编辑源码、报告文件或数据库；未调用产品模型、读取临床原件、访问网络或开展视觉验收。
- **建议 Codex 暂不认定 v3 满足全部软件验收条件。已复现缺单位隔离遮蔽同候选其他合同错误，包括外来资料要求和外来原件观察引用。**
- 这是软件恢复边界审阅，不是医学、监管或最终产品批准；最终裁决归 Codex。

### 一、证据与来源身份

**实测证据**

`git rev-parse HEAD` 返回：

```text
896258cb39970dce0c283edd998e2705ff55dad6
```

上下文提供的七个哈希全部与对应**文件内容 SHA-256**一致：

- `app/agents/evidence_candidate_partition.py`
- `app/agents/evidence_normalizer.py`
- `app/agents/evidence_normalizer_repair.py`
- `app/domain/contracts/facts.py`
- `app/services/fact_normalization_executor.py`
- `tests/v2/agents/test_evidence_candidate_partition.py`
- `tests/v2/services/test_fact_normalization_persistence.py`

上下文称其为“Patch hashes”，但实际匹配的是文件内容哈希。初次计算 partition 的 `git diff HEAD` 哈希不匹配，随后文件内容哈希全部匹配；**没有因此推断源码漂移**。

`fact_normalization_job_service.py` 和历史 adapter 测试属于授权来源，但上下文未提供其文件哈希；对此只报告当前所读源码证据，不声称获得同等级冻结校验。

### 二、主要缺陷与异议

#### F1 — P1：缺单位异常可以遮蔽同候选的其他合同错误【已复现】

**源码证据**

1. `ClinicalFactCandidateV2.validate_candidate`：
   - `app/domain/contracts/facts.py:304-309` 先抛出 `numeric_unit_missing`。
   - `:310-316` 的断言依据及对象一致性检查位于其后。
2. `_hydrate_draft_output`：
   - `app/agents/evidence_normalizer.py:1552-1559` 将“本次返回一个 numeric-unit 错误”转换为 `EvidenceNumericUnitError`。
   - **一个返回错误不等于候选只有一个缺陷**；同一个 after-validator 已经提前退出。
3. `partition_source_local_candidates`：
   - `app/agents/evidence_candidate_partition.py:209-214` 收到该类型即删除候选。
   - `:90-130` 没有对所有事实执行完整、独立于单位的合同检查。
4. 部分全局边界检查更晚：
   - 来源语义白名单：`evidence_normalizer.py:1782-1783`。
   - 资料要求身份：`_filter_supported_requirement_bindings`，`:1848-1854`。
   - 已采信观察来源：`_validate_normalizer_semantics`，`:1823-1825`。
   - 候选先被删除后，这些检查只能看到余项。

**具体危险反例与实测结果**

合成草稿含缺单位数值候选 `f1` 和合法独立候选 `good`。下列附加错误分别放在 `f1` 上：

| `f1` 的附加错误 | 单位缺失 | 单位明确的对照 |
|---|---|---|
| `supported_requirement_ids=["foreign-requirement"]` | 成功 partition，仅保留 `good`；failure 仅为 `EvidenceNumericUnitError` | 拒绝：绑定了冻结输入不存在的资料要求 |
| 非白名单 `candidate_source_semantics` | 同上 | 拒绝：来源语义不在白名单 |
| 候选 `asserted_object` 与 basis 对象不一致 | 同上 | 拒绝：对象必须一致 |
| R3 候选 `source_observation_refs=["other-patient-observation"]` | 成功 partition；failure 仅为 `EvidenceNumericUnitError` | 拒绝：必须引用本次已采信观察 |

对照单位只来自合成场景，用于揭示检查次序；没有补填真实数据单位。

**推论**

这不是外来候选被直接发布的证明：坏候选确实被删除。但它是**本应全局拒绝的来源/绑定损坏被缺单位隔离洗成部分成功**的证明，违反上下文要求的 foreign-reference fail-closed 边界。Receipt 保留原答，不会自动修复错误分类；重建同样的删除过程也不会发现被遮蔽的错误。

**最小修复建议**

- 将单位异常资格限定为：“全部其他必需合同及全局身份检查已完成后，唯一剩余问题是缺单位”。
- 在任何候选删除之前，对原始候选全量校验：
  - 冻结资料要求身份；
  - 来源语义白名单；
  - 观察引用的成员资格、重复及来源绑定；
  - 非单位领域合同，包括对象一致性。
- 领域 validator 中将缺单位判断放在其他检查之后，可修复对象一致性短路，**但单独移动这一判断不足以覆盖更晚的来源与资料要求检查**。
- 不使用临时 `unitless`、空单位替代值或猜测单位作为生产修复。

**Codex 决策点**

是否确认外来资料要求、外来观察引用和对象合同损坏仍属于不可被局部隔离遮蔽的错误？上下文已要求该边界；安全暂行路径是保持全局失败，修复后再执行 v3 窗口验证。

---

#### F2 — P2：新增隔离疑问没有继承原候选的观察身份【字段缺失已实测；独占组影响为推论】

**源码证据**

`retained_questions`，`app/agents/evidence_candidate_partition.py:155-172`：

- 保留页面和 locator；
- 没有将事实的 `source_observation_refs` 传入疑问的 `affected_observation_refs`。

R3 观察对账，`app/agents/evidence_normalizer.py:2205-2222`：

- 以保留候选引用和疑问观察引用共同计算观察组闭合；
- 仅有页面或 locator 不足以对账某个已采信观察组。

**实测证据**

使用合成 R3 输入，让缺单位候选和合法 sibling 引用同一已采信观察组：

```text
outcome: partitioned
retained: ["good"]
question_observation_refs: [[], []]
receipt_reconstruction_equal: true
```

该场景说明：即使原候选已有观察身份，隔离疑问也不继承它；原答身份仍可在 receipt 中保留，但疑问对象没有对应字段。

**推论与限制**

- `[INFERENCE]` 若隔离候选是某个独立已采信观察组的唯一消费者，该组可能因未转为观察级疑问而保持 uncovered，使本可局部保留的流程失败。
- 本轮**未完成两个独立已采信观察组的直接运行复现**。
- “sibling 不带观察引用”的尝试首先被合法来源门禁拒绝，不能拿它当作 uncovered 缺陷的实测证明。
- 不能把“receipt 保存了原始引用”解释为“疑问消费已完整携带引用”。

**最小修复建议**

在先验证原始观察引用合法、无重复、来源绑定正确之后，将被隔离事实的引用排序后写入新增疑问的 `affected_observation_refs`。不要直接搬运未经验证的引用，否则会重新引入 F1 的外来来源问题。

**Codex 有界问题**

请提供或构造“两组独立已采信观察；缺单位候选独占 A，合法 sibling 消费 B”的合成输入，验证 A 是否明确转为观察级待核。安全暂行路径：保持观察闭合门禁，不放宽为仅页面覆盖。

### 三、已成立的机制与验证边界

| 审阅项 | 证据 | 结论边界 |
|---|---|---|
| 缺单位局部隔离 | 直接运行整数数值及数值字符串；均仅保留 `good`，不改原草稿 | 该窄路径已实测 |
| 新旧默认行为 | Runner 实测：关闭隔离为“需要核对”；开启为“部分已解析”；合法开启路径为“已解析”且无 receipt | 三条路径 repair 调用均为 0；未运行真实产品模型 |
| 首答不可被失败修复替换 | Runner `:2378,2390-2393` 固定 `initial_raw_text`；receipt 保存原答及哈希 | 首答选择源码成立；未运行失败补答替换场景 |
| 派生闭合 | partition `:178-199` 删除依赖事件/完整暴露；迭代隔离失去完整暴露支持的 actual facts，不缩短暴露或重新分类 | 源码及合成测试定义已读；本轮没有执行闭合测试 |
| 已有疑问引用顺序 | partition `:78-81` 拒绝重复；`:203-205` 排序；授权测试定义覆盖 reverse/duplicate/foreign | 未执行该测试参数矩阵 |
| 保存与重建 | `_validate_partition_replay`，executor `:811-865` 重建原答，比较 receipt、保存候选和保存疑问 | 内存 receipt 重建相等已实测；数据库 replay 未运行 |
| 部分状态 | finalize `:1430-1433` 先重验 partition；`:1450,1570-1571` 按 receipt 存在强制 `PARTIAL` | 不再依赖某个疑问 code；为源码证据 |
| v2/v3 身份隔离 | job service `:569-574` 将 policy 纳入 scope；executor `:408-417` 校验冻结身份；replay `:835-838` 比较重建 receipt，包括 policy | 仅改旧 payload policy 字符串不足以满足当前检查；负向运行矩阵仍未验证 |
| 保存后疑问消费 | persistence 测试 `:1209-1350` 定义缺单位、文字对账、真实 executor 与 API DTO 场景 | 测试定义不是运行结果；本轮未作 API/浏览器验收 |

**额外异议**

Replay 能证明保存结果与当前恢复算法一致，不能证明算法本身满足所有恢复边界。F1 的错误若确定性重现，receipt 重建仍可能通过。

### 四、建议 Codex 的下一步与待答问题

1. **优先修复 F1**：原始候选的非单位合同及全局引用身份必须在删除前完成校验。
2. 再处理 F2：仅将已核实观察引用转入待核项，证明两个独立观察组的闭合。
3. 运行连接回归及保存消费负向矩阵：
   - 缺单位同时携带非法 requirement、source semantics、对象不一致、foreign observation；
   - 两个独立观察组的隔离与待核转换；
   - 原答、候选、疑问或 receipt 篡改后的 replay 拒绝；
   - v2 Job/receipt 仅改 policy 字符串后的拒绝；
   - 无破损 v3、compact references 和文字对账路径保持正常。
4. 明确下游消费者是否可能把 call 的 `SUCCEEDED` 误读为整个 normalization run 已完整成功。源码将 partition call 存为 `SUCCEEDED`、run 汇总为 `PARTIAL`；本轮没有扫描授权列表以外的全部消费者，不作无遗漏保证。

### 五、实际工具与能力限制

- **22 次文件/目录 read、glob、grep 命令**，到达上下文规定的读取上限；未扫描历史报告。
- 额外 **1 次必需 harness memory read**；仅作流程背景，不作为本次源码结论依据。
- **3 次只读 shell 命令**：diff 哈希、七个文件内容哈希、HEAD 身份。
- **5 次 eval 调用**：以 `.venv/bin/python -B` 运行无落盘合成函数实验，设置 `PYTHONDONTWRITEBYTECODE=1`；全部进程 exit code 为 0。早期 R3 构造被来源页绑定或页面闭合门禁拒绝，调整合成绑定与第 2 页待核后才得到上述有效结果。
- 实验导入授权测试模块中的 synthetic helpers；其依赖包括 `tests/v2/agents/test_fact_context_sources.py` 的输入构造。没有运行测试函数或测试套件，没有连接生产数据库。
- 使用会话 todo 跟踪审阅；未创建 Trellis task，未写任何输出文件。
- 未验证真实新模型输出、数据库保存 replay、实际 API/UI 表面、临床准确性或最终验收。上下文中的历史测试结果仅属提供的背景，**本轮没有把 v3 pending 窗口报告为通过**。

**本轮建议：先解决 F1，再验证 F2 与保存重放负向边界；保持未知单位为有定位的待核问题，不猜单位、不新增数值自动采纳。**
