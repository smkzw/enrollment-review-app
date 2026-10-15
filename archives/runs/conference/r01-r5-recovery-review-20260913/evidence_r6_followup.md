按只读顾问跟进：先核对 r6 诊断与当前冻结代码，再验证谓词遗漏分类与最小下一步核验。r6 失败已确认为内容遗漏而非超时。接下来核验 B0 回答身份集合、v2 元数据合同与定向测试。# Conference Output: r01-r5-recovery-review-20260913 - evidence_single_object

## Output

同会话只读跟进：当前证据是 **r6 内容遗漏**，不是 r5 超时。Codex 保留集成与验收。未改文件、未调模型、未重跑 12 次调用。

---

### Evidence

**遗漏分类（r6 `read:0:main-B`）**

- 作业 `ae256ad6231d4cfab8450b84b37686e0`：`failed_final` / `PREDICATE_READ_INCOMPLETE`。12 次调用均为 `stop`；仅 B0 为 `incomplete`。失败文案：「候选回答须完整覆盖冻结条件且不得重复或引入其他条件」。
- 回执 `544d2a9883…`：`error_type=null`，`response_sha256` 存在。不是 `APITimeoutError`。
- 回答 `46f74fa300…`（SHA 与文件名一致）：`finish_reason=stop`，有 usage。`results` 长度 2，身份为  
  `433ba8e2…`（`IN-01-age-gte-18`）与 `9112da66…`（`IN-02-history-duration`）。  
  **未出现** `49a5bd27edd119bc855a9ecb33eca0f48ca9d0358e76c47f681c0a5d650e6260`（`IN-01-age-lte-75`）。返回身份不是该哈希的前缀/后缀变体。
- 同批冻结组件清单含上述三个 **trigger**，例外数为 0。A0 候选包 `19a35beb…` 含全部 3 个身份且 `accepted=false`；当前 `validate_predicate_candidates` 对 A0 仍通过引用校验。
- r6 请求为 `predicate-binding-candidates-batch/v3`：**没有** `required_predicate_identities`，schema **没有** `minItems`/`maxItems`/`enum`。冻结输入 `predicate-binding-frozen-input/v2`，`frozen_input_sha256=4bee1d39…`，prompt 含 5 份 `documents`（列：`source_document_version_id,file_name,media_type`；不含 `source_blob_sha256`）。

**当前冻结代码（live v6 未跑）**

- `PROMPT_VERSION=predicate-binding-candidates/v6`，`BATCH_PROMPT_VERSION=…-batch/v4`；作业合同名仍为 `predicate-binding-candidate-job/v6`。
- `build_predicate_binding_messages` 把 trigger+exception 身份列入 `required_predicate_identities`，并设 `results.minItems=maxItems=len(identities)`、身份 `enum`（`predicate_binding_candidates.py` 121–125、148–159 行）。
- `validate_predicate_candidates` 仍用 **集合相等** 拒绝遗漏/重复/外来身份（188–190 行）。同事实多条件仍允许（测试 `test_one_fact_can_be_a_candidate_for_multiple_predicates`）。
- 对本份 B0 原文，当前产品校验仍抛出同一覆盖错误。用 **当前 v4 消息** 的 schema 校验该 omit 载荷：`jsonschema` 报 `too short`。
- 反例（确定性、无模型）：三槽填 `[gte-18, gte-18, history-duration]`（计数=3，缺上界）。**jsonschema 通过**；产品校验仍报完整覆盖错误。`uniqueItems` 未设。`mtplx_schema_compat.decoding_response_format` 保留 min/max/enum，只剥 `if/then/else`。
- 系统提示要求例外与多原子条件分条、禁止按病种/模型名分支；消息中无 glm/qwen/mtplx。分批仍按事实+完整 locator，不按临床相关性裁剪。

**v1 / v2 来源元数据**

- v1：`documents is None`，哈希材料 identity 为 `predicate_binding_frozen_input/v1`（下划线）。字段字面量是 `predicate-binding-frozen-input/v1`（连字符）。`test_legacy_input_preserves_its_content_identity_without_document_inference` 覆盖读回。
- v2：构建器从 `SourceDocumentRepository.get` 抄 `file_name`/`media_type`/`source_blob_sha256`；清单必须与 locator 的 `source_document_version_id` 恰好一致（`predicate_binding.py` 473–486 行；`predicate_binding_input.py` 301–312 行）。prompt 去掉 blob sha。提示写明文件名/媒体类型不是作者、资料性质或医学事实证明。

**超时恢复命令（不得削弱）**

- `prepare_recovery` 要求：当前合同+**当前** prompt/batch 版本、路由一致、步骤 `incomplete`、冻结哈希未变、**最后回执 `error_type==APITimeoutError` 且无 `response_sha256`**、重建请求字节级等于原请求（`recover_predicate_binding_read.py` 41–95、87 行）。
- r6 B0 同时触发：prompt `v5/v3` ≠ 当前 `v6/v4`；回执有回答。现有恢复测试覆盖超时步、资料漂移、路由、请求漂移、损坏回执；**没有**内容失败回执用例，也没有「合同同名、提示已变」用例。

本轮只读核验：上述 blob/作业 payload、所列源文件与定向测试。未跑宣称的 81 项套件，未启动服务。

---

### Inference

1. 分类成立：**原子身份遗漏**，不是打错哈希、不是超时、不是空用量。B0 对其余两条件给出了结构合法条目（一条 candidates、一条 unresolved）；缺的是上界条件这一 **结果槽**。不得把下界候选复制到上界。
2. r6 当时的 v3 schema **不会**在解码层挡住这次 omit；失败靠事后集合校验，所以整步 `incomplete`、作业 `failed_final`，回答仍保留。这与「未修理模型答案」一致。
3. v6/v4 结构补丁是通用身份清单，不引入项目/疾病分支，也不合并 trigger/exception。它能挡住 **短数组** 这类 schema 失败（本份 B0 omit 即是）。它 **不能** 单独挡住「用重复允许身份凑满 minItems」。那仍是语义/内容失败，必须靠现有精确集合校验。live schema 是否被 MTPLX 强制执行，本轮未测。
4. 文件名进 prompt 只提供上传元数据线索；不能当原始记录或入排证明。v1 无 documents 仍可校验；现构建器只产 v2，旧 v1 作业不能当「当前资料」做同输入补测。
5. 超时恢复命令若被拿来重放 r6 B0，**应当拒绝**。削弱该门闩会把内容失败与超时补测混成一次「同输入恢复」。

---

### Recommendation

**最小下一步核验（无新 harness、不改旧作业、不重放 12 次）**

1. **先无模型（本轮已用产品函数做过，应落成定向测试而非再问用户）：**  
   - 只读加载 r6 payload 的 frozen v2 + `batches[0]`；  
   - `validate_predicate_candidates(frozen, B0.text)` 必须失败；  
   - `build_predicate_binding_messages(..., batch=batch0)` 的 required 列表必须含 `49a5bd27…`；  
   - 当前 schema 拒绝该 omit；产品校验拒绝「重复身份凑满 3 槽」；三条 `unresolved` 精确覆盖必须通过且 `accepted` 不出现。  
   复用现有 `validate_predicate_candidates` / `build_predicate_binding_messages`，输入即 r6 冻结物。
2. **补缺测试后再考虑 1 次隔离实呼：** 新目录、sqlite `mode=ro`、调用已有 `read_predicate_candidates(frozen, main-B, batch=batch0)`。不要跑 `recover_predicate_binding_read.py`，不要 `retry_failed`，不要重写 r6 检查点。仍 `accepted=false`。一次内容失败即停，不扩成 12 次。
3. **保持超时恢复门闩原样。** 为 r6 这种 stop+缺身份补一条拒绝测试，而不是放宽 `APITimeoutError` 判定。

**不要做：** 把 A0 的上界候选并入 B0；把文件名当临床证明；把 schema 通过当成语义通过；用恢复命令「修」r6；声称 live v6 已跑。

---

### Uncertainty

- 未验证 MTPLX 是否执行 `minItems`/`enum`；adapter 只证明字段未被剥掉。
- 未重跑 81 项；DIAGNOSIS 写 75、本提示写 81，本顾问不采信任一数字为当前复验结果。
- r6 无例外条件，例外分条仅由代码路径与提示保证，缺实载荷。
- B2/B3 曾 >900s 仍 `stop`，与本次遗漏是不同问题，本轮不展开。
- 未打开影像原件；未把 A0/B0 候选当医学对应。

---

### 异议、反例、缺测、给 Codex 的决策点

**最高影响缺口：** 结构修复把「少一条」变成可预防的 schema 失败，但 **精确集合仍不是 schema 不变量**。  
反例：`results = [433ba8e2, 433ba8e2, 9112da66]`（相对 `49a5bd27` 上界）。jsonschema 通过；`validate_predicate_candidates` 拒绝。若解码器只保证长度，live v6 仍可能得到与 r6 同类的 `incomplete`，只是失败形态从「太短」变成「重复凑数」。

**缺测（应先于 live）**

| 缺口 | 现况 | 反例 |
|---|---|---|
| 恢复拒绝内容失败 | `test_predicate_read_recovery.py` 无 stop+response 的 incomplete | 把 r6 B0 回执形态交给 `prepare_recovery` → 必须 `未取得回答` |
| 恢复拒绝提示漂移 | 只测资料/路由/请求字节 | 合同仍 `job/v6`、prompt `v5`≠`v6` → 必须拒绝 |
| schema 重复凑数 vs 产品精确集 | schema 测 omit/非法 enum；产品测 omit/duplicate；未对照「满长度重复」 | 上表三槽重复 |
| 例外身份进清单 | `_case()` 的 `exception_predicates=[]` | 触发+例外两身份；合并成一条必须失败 |
| adapter 保留 min/enum | 只断言 `generation_mode=ar` 且有 `response_format` | compat 后 min/max/enum 仍在 |

**决策点（不削弱恢复的前提下）**  
live 单呼是否等上述测试合入；schema 是否加「身份唯一」约束（仍不能替代产品集合校验）。两者都不要求再向用户申请已授权的隔离评测。

**暂定路径：** r6 作业保持 `failed_final`；42 条候选保持未采信；超时恢复命令保持拒绝 r6；下一步只固化无模型精确集/恢复拒绝用例，必要时再对 **batch0 × main-B × 当前 v4 消息** 做一次新目录隔离读取。
