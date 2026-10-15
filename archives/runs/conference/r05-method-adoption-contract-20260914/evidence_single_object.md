I'll start with the assigned context and source files, then independently audit the adoption-contract design against those sources.Context files are mostly placeholders, so I’ll audit the assigned source modules and the engineering-design sections next.The qualification consumer is already authorization-gated; next I’ll inspect persistence, GateResult, and the design sections that define adoption.I’ll pull design §17.1.1/§17.6 and the persistence/gate contracts next, focusing on how evaluation hashes are treated as proofs.I have enough source evidence: the highest-impact gap is that evaluation proof is an untyped `raw_response` hash, so I’ll write the bounded contract review next.

# Conference Output: r05-method-adoption-contract-20260914 - evidence_single_object

## Output

角色：只读证据审阅，不是 Codex 终审，也不是临床/监管/视觉验收。未改代码、未跑测试、未调模型、未读生产库、未签发批准。会商上下文与主场计划仍为 TODO 占位；以下以当前源码与设计 §17.1.1 / §17.6 为准。

---

### Evidence（观察）

1. **资格材料本身禁止采信。** `BindingQualificationSummary`、`QualifiedBindingSelectionMaterial`、`FrozenReviewCalculation` 都将 `accepted` / `authorized_clinical_adoption` / `clinically_qualified` 钉死为 `False`（`app/domain/contracts/qualified_binding_selection.py:123-131`；`app/services/binding_qualification_support.py:819-821, 1000-1006`；`app/services/frozen_review_calculation.py:34,47`）。`accepted=false` 是中间未采用记录，不是缺陷。

2. **正式写入已有两道门，但都没有类型化评测体。**
   - 方法门：`review-method-adoption`，`output_hash` 必须等于当前请求现场拼出的 `{version: frozen-review-publication/v1, evaluator_version: component-review/v6, consumer_versions, evaluation_evidence}`（`frozen_review_publication.py:71-82`）。该 dict **从未作为 ContractModel 落盘**。
   - 任务门：`binding-adoption-authorization`，`output_hash` 必须等于调用方传入的 `QualificationAdoptionAuthorization.model_dump()`（`qualified_binding_selection.py:106-138`）。授权对象也 **不从仓储重建**，只做哈希比对。
   - `app/` 内这两类 `gate_name` 只有校验、没有签发。`publish_frozen_review` 无 HTTP 注册。

3. **所谓评测证据只是 `raw_response` 存在性检查。** 方法门与任务门都执行 `artifact_store.read_by_sha("raw_response", digest)` 后丢弃字节（`frozen_review_publication.py:81-82`；`qualified_binding_selection.py:268-269`）。`ARTIFACT_KINDS` 现仅有 `page_image/native_text/native_coordinates/raw_request/raw_response`（`app/evidence/artifacts.py:20-22`）。资格汇总、LLM 回执、候选比较都已写在 `raw_response` 下。不存在 `EvaluationManifest` / `scoring_version` / `gold_split` 合同（`app/**/*.py` 无匹配）。

4. **任务授权钉的是「这一份 job」，不是「已评测方法」。** `QualificationAdoptionAuthorization` 含 `qualification_job_id`、本案 `frozen_input_sha256/comparison_sha256/summary_*`、资格 prompt/contract/summary 的 Literal 版本、以及 `route_identities`（`qualified_binding_selection.py:26-68`）。它不钉候选阶段 `candidate_contract/prompt/batch_prompt`，也不钉 `EVALUATOR_VERSION`。方法门也不钉 prompt/schema/A/B 路由。

5. **回执重建与授权比范围不对称。** `verify_completed_binding_qualification` 会重建候选比较 + 资格双路，资格步 `require_route_receipts=True`（`binding_qualification_support.py:1007-1016`）。候选重建只核 `model` 与 `reasoning_effort`，不核完整 `route_identity`（同文件 409-418）。产品 `route_identity()` 实际冻结 7 字段：`provider, base_url, model, reasoning_effort, max_tokens, max_concurrency, fallback_base_url`（`page_review_job_service.py:68-73`）；授权校验只要求前 5 个是子集（`qualified_binding_selection.py:63-65`），随后又与 job payload **整 dict 相等**。

6. **一旦任务门放过，配对层不再看评测内容。** `_AUTHORIZATION_WAIVED_REASONS` 去掉 `evaluation_activation_absent` 与 `clinical_adoption_not_authorized`（`qualified_binding_selection.py:40-45,100-102`）。授权通过后，双路一致且结构可用的配对可进入计算选择。

7. **方法门 `output_hash` 由本次发布请求反推。** 评测 SHA 集合来自本次 `authorizations`；集合不同则哈希不同。方法批准因此绑的是「这次请求里出现的 SHA 集合」，而不是一份独立的方法身份。`GateResult.gate_name` 是自由字符串（`agents.py:160-176`）；`AppendRepository.save` 无签发策略（`repositories.py:303-325`）。谁能写 GateResult + 放入任意 `raw_response` 字节，就能凑齐两道门。

8. **设计边界。** §17.1.1：结构检查不能证明语义；自动采用须隔离双源评测 + 用户接入确认；本节不是已实现/已验收。§17.6：整批发布须有独立真实采用批准；`accepted=false` 不自行授权；允许带未决项完成本次审核，但不等于符合入组。T4 已给出**系统级**事实：并集事实召回 ≥0.95、金标负判定静默漏判 =0；其余采信/性能阈值须用户在实测数字上批准（`REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md:100`；`REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md:229`）。T5：正式推广须 T4 前置通过；当前不签发批准。

9. **现有持久化足够，不必新队列。** `GateResult` 追加写、`ArtifactStore` 内容寻址、`IdempotencyRepository` 的 `(scope, key) + request_sha256` 语义已存在。本任务无任何已签发的 method-adoption 行可迁。

---

### Inference（推论）

**最高影响缺陷：未类型化的 `raw_response` SHA + 由消费者现场拼出的方法 dict，使「任意相同哈希的字节」可以冒充已评测批准。**

攻击面（源码即可构造，无需阈值或临床复测）：

- 把资格汇总、LLM `raw_response`、甚至任意 JSON 的 SHA 填进 `approved_evaluation_evidence_sha256`。
- 写入 `GateResult(gate_name="binding-adoption-authorization", result=ACCEPTED, output_hash=hash(authorization), input_entity_refs=[该SHA], accepted_entity_refs=[job_id])`。
- 再写 `review-method-adoption`，`output_hash` 对齐发布函数现场拼出的 method dict。
- 两处 `read_by_sha` 只证明字节存在且内容哈希一致，不证明这是评测清单、不证明金标/评分版本、不证明 A/B 身份。

这不是假设性风格问题。注释已写 “A digest in a gate is not the evaluation artifact itself.”（`qualified_binding_selection.py:268`），但下一步仍只做存在性读取。

**对所有者提案的裁定：** 三分层（不可变评测清单 → 显式用户批准回执 → 服务在回执重建后签发任务授权）方向正确，且与 §17.1.1 第 3–5 步、§17.6「独立真实采用批准」一致。当前代码把第 1、2 层压成不透明 SHA，把第 3 层做成**调用方必须预先持有的 per-job ACCEPTED 门**。若人来签发第 3 层，就是逐例批准负担；若服务签发，则现有 API 仍要求调用方提交授权对象，服务并未比较「重建出的方法身份 ⊆ 已批准评测范围」。

**不要把 T4 事实召回报告拿来当绑定方法批准。** 0.95 / 静默漏判 0 是全系统事实抽取退出门槛，不是 §17.1.1 语义对应金标。未类型化 SHA 会使一份页读评测报告冒充绑定方法评测。

**软件方法采用 ≠ 本例正式保存 ≠ 入组结论。** 方法批准只应解锁「用该推理方法做正式计算输入」。`publish_frozen_review` 仍是用户对本例的保存命令（个案签字）。`assessment-publication-gate` 的 `ACCEPTED` 只表示该评估行已按本次 run 落盘，不表示方法已评测，也不表示受试者符合入组。三者必须继续分名。

---

### Recommendation（可实施合同）

#### 1. 最小字段（建议三个 ContractModel，全部 disabled）

**A. `EvaluationManifest`（`evaluation-manifest/v1`，不可变事实，不是批准）**

| 字段 | 约束 |
|---|---|
| `version` | Literal `evaluation-manifest/v1` |
| `evaluation_kind` | Literal，至少 `binding-qualification-semantic-correspondence`；禁止与页读/OCR 报告混用 |
| `source_corpus_sha256` | 64 hex；冻结评测输入包 |
| `gold_split_sha256` | 64 hex；金标/留出划分；T4「不把旧 0.969 直接转移」 |
| `scoring_version` | 非空字符串，如 `binding-qualification-scorer/v1` |
| `observed_metrics` | 显式映射，至少含 `union_recall`、`silent_negative_misses` 的**观测值**；可另报双源采信召回/未对应/错误关联，但**不在代码里判及格** |
| `method_identity` | 见下表 |
| `manifest_sha256` | 自排除内容哈希 |

`method_identity` 必须同时覆盖**候选与资格**两阶段、以及正式消费版本：

- families：`predicate` 和/或 `control`
- 候选：`job_type/contract/prompt_version/batch_prompt_version`（当前谓词 v7/v6/v4，控制 v5/v1/`None`）
- 资格：`binding-qualification-job/v2`、`binding-qualification/v2`、`binding-qualification-summary/v2`
- 消费：`qualified-binding-selection-consumer/v1`、`component-review/v6`、`frozen-review-publication/v1`、`unverified-predicate/v1`
- 路由：`main-A`/`main-B` 各一份，且**分阶段**列出候选路由与资格路由；字段与 `route_identity()` 七项对齐，不得只留 5 项子集
- 不含凭证；`base_url` 是部署身份，不是密钥

工件类别：新增 `evaluation_manifest` 到 `ARTIFACT_KINDS`。不要放进 `raw_response`。

**B. `MethodAdoptionApproval`（`method-adoption-approval/v1`，唯一人类回执）**

| 字段 | 约束 |
|---|---|
| `version` | Literal |
| `manifest_sha256` | 必须指向可 parse 的 A |
| `approving_principal` | 非空；禁止 `system`/`score-gate` |
| `approved_at` | UTC |
| `decision` | Literal `adopt_method_for_formal_calculation` |
| `cited_metrics` | 从 manifest **抄录**的观测值，表示人看过这些数 |
| `clinical_case_signoff` | Literal `false` |
| `approval_sha256` | 自排除哈希 |

代码路径：**禁止** `if recall >= 0.95: emit approval`。0.95 与静默漏判 0 是给人看的既定事实，不是签发触发器。额外阈值等完整系统评测数字出来后再由用户定。

落盘：`GateResult.gate_name="review-method-adoption"`，`output_hash=canonical_hash(approval)`，`input_entity_refs` 含 `evaluation_manifest/{sha}`，`accepted_entity_refs` 含 approval 身份。**禁止**再把现场拼的 method dict 当作 output 体。

**C. 任务授权（保留现有 `QualificationAdoptionAuthorization`，补钉）**

现有 per-job 字段（job id、本案冻结/比较/摘要哈希、资格版本、路由）仍应用作**重建证明**。补：

- `method_approval_id`
- `evaluation_manifest_sha256`（kind 必须是 `evaluation_manifest`）
- `candidate_contract` / `candidate_prompt_version` / `candidate_batch_prompt_version`
- 服务端比较：重建出的 method_identity **等于** manifest 中对应 family 的范围；不相等则拒绝，不做模糊兼容

人类只批 B。C 由拥有服务在重建成功后签发。调用方不应手组授权对象。

幂等：`IdempotencyRepository`，scope 建议 `binding-adoption:{qualification_job_id}`，key = `method_approval_id`。方法批准：scope `method-adoption:{manifest_sha256}`。无新队列、无新生命周期状态机。

#### 2. 现有消费者缺口（按优先级）

| ID | 缺口 | 位置 |
|---|---|---|
| G1 | 评测 SHA 未 parse、未分 kind | `qualified_binding_selection.py:268-269`；`frozen_review_publication.py:81-82` |
| G2 | 方法门 output 是请求反推 dict，无独立批准体 | `frozen_review_publication.py:72-79` |
| G3 | 任务授权由调用方传入，不从仓储重建 | `publish_frozen_review` 签名；`_validate_authorization` |
| G4 | 方法身份不含候选 prompt/contract，也不含 evaluator | `QualificationAdoptionAuthorization` |
| G5 | 方法门不含 A/B 路由；不同部署可共用同一不透明 SHA | 同上 |
| G6 | 候选回执不核完整 `route_identity` | `binding_qualification_support.py:409-418` vs `1007-1016` |
| G7 | 发布 API 一旦启用，客户端可提交伪造授权对象，只要 DB 里有匹配 GateResult | 无签发器 + 自由 `gate_name` |
| G8 | `evaluation_activation_absent` 在配对层被豁免，评测安全性完全压在 G1/G2 | `qualified_binding_selection.py:40-45` |

#### 3. 迁移 / 版本含义

- 当前无已签发 method-adoption 行，**没有历史批准可迁**。不要把旧资格汇总 SHA 回填成 manifest。
- 新增 artifact kind 是文件系统约定，不改 GateResult DDL。
- 现有 Literal 版本（资格 v2、消费 v1、求值 v6）应 fail-closed：prompt/schema/路由任一变化 ⇒ 旧 manifest 不能授权新 job。禁止「兼容范围」。
- 消费者改为 parse 类型化清单后，任何用假 `raw_response` SHA 的测试夹具会失败——本任务不跑测试，实现轮再改夹具。
- `accepted=false` 材料保持原字节身份；不要为「看起来已采用」去翻标志。

#### 4. 源码对照的替代方案

| 方案 | 结论 |
|---|---|
| 所有者三分层 + 现有 Gate/Artifact/Idempotency | **采用**，作为最小完整设计 |
| 继续用 `raw_response` + 存在性检查 | **拒绝**；这就是冒充面 |
| 在 `raw_response` 内放 JSON 并 parse | 弱于独立 kind；同目录已混有 LLM 回执。仅当 Codex 禁止扩 kind 时的退路，且必须 parse-or-reject |
| 人签每份 `QualificationAdoptionAuthorization` | **拒绝**；这就是逐例负担 |
| 分数达标自动写 `review-method-adoption` | **拒绝**；违反「批准不得由及格分自动产生」 |
| 新队列/新状态机 | **拒绝**；§17.7 与现有追加写已够 |
| 把 T4 召回报告当绑定方法批准 | **拒绝**；评测对象不同 |
| 临床医生对每例重测模型 | **拒绝**；非本任务，也非最小合同 |

#### 5. 可现在就构建（保持禁用）vs 必须等完整系统评测

**现在可建、且必须保持禁用 / 不签发：**

1. `EvaluationManifest`、`MethodAdoptionApproval` 合同。
2. `ARTIFACT_KINDS` 增加 `evaluation_manifest`。
3. 消费者改为：按 kind 读取 → `model_validate` → 比对 method_identity；拒绝 `raw_response` 充当评测证据。
4. 方法门改为哈希 **B**，不再哈希现场拼 dict。
5. 纯函数「重建 job → 比较 manifest 范围 → **假如**已有 B 则构造 C」——不注册 HTTP、不写 ACCEPTED 批准、不调用产品模型。
6. 发布函数可先保留现签名，但内部必须能从 job + method_approval **重放**出与调用方授权相同的 C；不一致即拒绝。最终应改为只收 `method_approval_gate_id` + `qualification_job_ids`。

**必须等完整系统评测 / 用户决定之后才能有的证据：**

- 真实 `source_corpus_sha256` / `gold_split_sha256`（T4 冻结金标；§17.1.1 所列正反例是否覆盖）
- 观测指标数字，含是否达到既定 0.95 / 静默漏判 0
- 用户对**额外**阈值的批准
- 评测环境里真实的 main-A / main-B 部署身份
- 谓词与控制是一份金标还是两份（合同用 `families` 列表兼容两种，但数据尚未存在）
- 任何 `GateResult(result=ACCEPTED)` 的方法批准行
- 正式 HTTP、翻转 `accepted`、临床个案签字

---

### Uncertainty（不确定）

- 完整系统评测尚未发生；0.95 / 0 是否已被当前双模型满足，本角色无证据。
- 绑定链自己的金标包尚未冻结；§17.1.1 验收清单与 T4 事实召回是否共用同一 split，Codex 未裁决。
- 候选与资格若允许使用不同 A/B 部署，manifest 必须分阶段记录；若作业构造期就应强制同一部署，应在生产者拒绝，而不是只在采用合同里补。
- 谁有权写 `review-method-adoption`：现有 `AppendRepository` 无策略。未设签发器前，任何能拿到 session 的代码都能写 ACCEPTED 门。产品路径必须继续不注册。

---

### 对所有者提案的异议与替代

1. **异议（最高）：** 「一份 SHA + GateResult 成员关系」不足以绑定评测。必须是可 parse 的清单 + 独立用户回执 + 独立 artifact kind。
2. **异议：** 把 per-job 授权做成人类预签发门，会把方法批准退化成逐例批准。改为服务签发 C，人类只签 B。
3. **异议：** 方法门用请求反推 dict 当 `output_hash`，批准体随消费者代码漂移。批准体必须先落盘再被核对。
4. **异议：** 不要用 T4 页读召回 SHA 充当绑定方法评测。
5. **同意：** `accepted=false` 不是 bug；不要新队列；本任务不签发批准。

---

### 给 Codex 的决策点

1. 新增 `evaluation_manifest` kind，还是强制 parse `raw_response`？**建议新 kind。**
2. 发布入口最终是否改为只收 `method_approval_gate_id` + job ids？**建议是。**
3. 既定 0.95 / 静默漏判 0 是否写入签发代码当硬拒绝？**建议不写进签发器**；写进清单必填观测字段 + 给人看的说明。
4. 一份 method approval 是否必须同时覆盖 predicate 与 control？**建议 manifest.families 显式列出；缺的 family 不能签发对应 C。** 若方案含跨章控制，发布仍须两类齐全（现有 `frozen_review_calculation.py:102-106`）。

未裁决前的安全暂定路径：按新 kind + families 列表实现禁用合同；发布内部重放 C；不编码分数触发器；不启用 HTTP；不写 ACCEPTED 批准。

---

### 有界问题（请 Codex 同会话答复）

1. `evaluation_kind` 是否只允许 `binding-qualification-semantic-correspondence`，T4 全系统评测另用别的清单/门，互不为证？这决定方法门能否引用页读报告 SHA。
2. 候选路由与资格路由在作业构造时是否必须字节级相同？若必须，采用合同只核一份；若允许不同，清单必须分阶段。
3. 拥有服务的名字（`authorizing_service`）是否固定为一个内部模块名（例如 `frozen-review-publication`），禁止外部/脚本写入？这决定 G7 在有 session 时是否仍能手写门。

---

本角色不声称最终接受。实现顺序：合同与 kind → 消费者拒收未类型化 SHA → 禁用的重建比较器 → 等金标与用户批准后再谈签发。
