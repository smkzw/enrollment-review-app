I'll start by reading the assigned context files, then trace the actual source code.

Bash unavailable as scope predicted. Using read-only tools.

Key evidence found. Now tracing the source.

Now examining the frozen receipts to quantify cross-batch context growth.

# Conference Output: acceptance-protocol-cost-20260916 - evidence_single_object

## Output

- Role: `codebuddy` / `codebuddy-cli` / `deepseek-v4.1-flash` / effort `max` — bounded advisory pass, read-only.
- Actual tools used: `Read` / `Glob` / `Grep` only. **`Bash` is unavailable in this session** (permission denied, non-interactive). Consequences: no test execution, no `jq`, no line-length-independent extraction of the ~2 MB single-line frozen request/response JSON. Where that limit bound a conclusion I say so explicitly instead of guessing.
- Not done (out of scope / not my authority): no clinical judgment, no runtime/model call, no writes, no browser/DB, no network. I did **not** write `runs/conference/.../evidence_single_object.md`.

---

### 0. Sources actually read

| Source | Read |
|---|---|
| `context/acceptance-protocol-cost-20260916_conference_context.md`, `plans/codex_main_venue_acceptance-protocol-cost-20260916.md` | full |
| `app/agents/protocol_deconstructor.py` | targeted: 180–200, 226–247, 520–570, 926–974, 1102–1290, 1379–1743, 1745–1845, 3506–3635, 4048–4145, 4449–4866, 4938–4957, 5150–5254 |
| `app/agents/protocol_semantic_transport.py` | targeted: 1–300, 330–490, 494–725 |
| `app/domain/contracts/agent_io.py` | 80–190 |
| `app/agents/protocol_semantic_model_router.py` | 330–450 |
| `tests/v2/agents/test_protocol_source_policy_generation.py` | full (73 lines) |
| `artifacts/acceptance-20260916/source-policy-generation.xml` | header + case names |
| `artifacts/acceptance-20260916/fresh-sar-protocol/execute/execute_record.json` | full |
| `.../execute/receipts/` `request-0000/0001/0012`, `receipt-0000…0012`, `response-0011`, `history-000-protocol-chat-1048031259.json` | bounded excerpts + counts |
| `artifacts/acceptance-20260916/data/blobs/protocol-semantic-route-audits/{da944f6e…,09b593a7…}/route-audit.json` | full |
| `artifacts/phase55-model-comparison/20260907/product-input-v1/product-code/domain/contracts/agent_io.py` | 112–136 (historical counterexample) |

I did **not** read any clinical document beyond the frozen prompt/response excerpts already inside the listed artifacts.

---

### 1. Findings by severity

#### S1 — BLOCKER (cost + completion risk): the bounded-context capability is a **backend whitelist**, so GLM resends the whole growing history on every batch

**Observation (code).**
- `app/agents/protocol_semantic_transport.py:387-389`
  ```python
  @property
  def supports_bounded_batch_context(self) -> bool:
      return self._backend in _LOCAL_STRUCTURED_BACKENDS
  ```
  `_LOCAL_STRUCTURED_BACKENDS = {"omlx", *{"mtplx","mtplx-api"}, "mlx-serve"}` (`:54-60`). `zhipu-coding-plan`/`glm` and `deepseek` are **not** members. The acceptance route's backend is `zhipu-coding-plan` (`execute_record.json` → `transport.backend`).
- `app/agents/protocol_deconstructor.py:4076-4087`
  ```python
  def _compact_transport_history(transport, session_id, *, context):
      if not getattr(transport, "supports_bounded_batch_context", _uses_compact_wire_contract(transport)):
          return                       # ← GLM exits here
      compactor = getattr(transport, "compact_session_history", None)
      ...
  ```
- Called before every subsequent batch: `app/agents/protocol_deconstructor.py:4816-4825`. So on GLM it is a **no-op on every one of the 22 subsequent batches**.
- The capability it refuses to use is **already implemented on the very same class**, generically, for all backends: `protocol_semantic_transport.py:702-714` `compact_session_history()` replaces the accumulated history with a 2-message audit anchor. `:725` `OpenAICompatibleProtocolAgentTransport = DeepSeekProtocolAgentTransport` — one class, aliased.
- Full-history resend is explicit: `start()` `:635-656` seeds `[user]`; `continue_session()` `:658-681` sends `[*self._histories[session_id], {"role":"user",...}]` and `_complete()` `:494-500` copies all messages. The class docstring (`:136-142`) states this as intended: *"every repair sends the complete prior user/assistant exchange."*

**Observation (frozen evidence).** One 23-batch plan; a session that reached batch 6 re-sent a monotonically growing prompt (`receipts/receipt-000N.json`):

| attempt | retained turns | messages in request | `prompt_tokens` | `completion_tokens` | `reasoning_tokens` | `elapsed_seconds` |
|---|---|---|---|---|---|---|
| 0 | 1 | 1 (`request-0000`) | 9,745 | 11,436 | 10,633 | 286.44 |
| 1 | 2 | 3 | 15,764 | 1,234 | 637 | 33.64 |
| 2 | 3 | 5 | 26,235 | 8,397 | 7,040 | 190.36 |
| 3 | 4 | 7 | 33,234 | 2,133 | 732 | 39.91 |
| 4 | 5 | 9 | 44,448 | 3,286 | 2,235 | 96.11 |
| 5 | 6 | 11 | 51,008 | 1,799 | 848 | 54.17 |
| 6,7,9 | fresh | 1 | 9,999 / 9,983 / 10,063 | 21,933 / 14,988 / 20,154 | 18,907 / 12,642 / 18,631 | 528.70 / 343.26 / 484.54 |
| 8,10,11 | partial | 3 | 17,312 / 17,785 / 16,889 | 2,366 / 3,564 / 1,637 | 520 / 1,284 / 384 | 49.80 / 75.20 / 41.58 |
| 12 | 7 | **13** | *(none — timeout)* | — | — | **600.0372** |

`request-00NN` message counts: `1,3,5,7,9,11` for 0000–0005 → one session, batches 1…6. Measured increments (batch→batch): **+6,019 / +10,471 / +6,999 / +11,214 / +6,560** → mean **+8,253**; batch-6 prompt is **5.23×** batch-1. A fresh single-message batch prompt is consistently **9.7k–10.1k** (attempts 0/6/7/9 — four different batches), so the growth is not the batch's own source; it is **retained prior turns**.

**Also disabled by the same flag:** `_configure_transport_output_scope` (`protocol_deconstructor.py:4090-4093`) is gated on line **4100** with the same `getattr(..., supports_bounded_batch_context, ...)` and returns early for GLM. So on the GLM route `transport.configure_output_scope()` is **never called**; `self._output_scope` stays `{}` (`protocol_semantic_transport.py:336`) and the DNF/source/requirement limits (`component_limit`, `group_limit`, `atom_limit`, `requirement_limit`, `source_limit`) are inert. The "1–3 父规则 / bounded output" guarantee is then carried **only by prompt text**, not by any schema. This is the same defect at a second call site, not a separate one.

**Inference (labelled).** Linear extrapolation of the measured increments to a 23-batch session (the frozen run never got past batch 4 *in the timed-out session*, so this is extrapolation, not measurement):

| mean increment/batch | est. batch-23 prompt | est. cumulative prompt tokens for 23 batches |
|---|---|---|
| +6.0k (low) | ≈142k | ≈1.67M |
| **+8.25k (mid, measured mean)** | **≈191k** | **≈2.31M** |
| +11.2k (high) | ≈256k | ≈2.93M |
| with compaction (23 × ~10k) | ≈10k | ≈0.23M |

⇒ **≈7×–13× 可省的累计 prompt token**（同一 23 批、同一冻结输入）。另有未经验证的风险：估算的末批 prompt 142k–256k 可能超过所配置模型的上下文窗口；冻结证据里**没有**记录 GLM-5.3-Flash 的上下文上限，因此"整轮必然溢出"是推断而非事实——但"末批远端请求远超单批 10k"是事实。

**Counterexample I looked for and did not find.** A legitimate reason to exclude cloud backends would be "the provider does not accept a session whose history was rewritten." Nothing in the frozen evidence supports that: the same class stores history client-side (`self._histories`) and the OpenAI-compatible endpoint is stateless (docstring `:136-142`); `compact_session_history` would only change the local list. Also, the run **already restarts sessions mid-flight** (`request-0006/0007/0009`, 1 message each) with a full fresh batch prompt — the "send a full batch prompt without prior history" pattern is already exercised and accepted.

**Minimum remedy (no behavior change to prompts, schema, or route):**
1. Treat the *operation* and the *backend class* as separate things. Split the conflated boolean into e.g. `supports_session_compaction` (property = "`compact_session_history` is callable") and keep the *policy* of whether to call it as an explicit, per-backend decision in one place. Do not drive it from `_LOCAL_STRUCTURED_BACKENDS`.
2. Fix all **three** call sites together — see S3 for the third one, which currently defaults to `False` instead of `_uses_compact_wire_contract(transport)`.
3. Fix the dead-but-misleading error string `"oMLX 批次 transport 缺少有界会话压缩能力"` (`protocol_deconstructor.py:4086`) — it would fire with a wrong vendor name the moment the flag is widened.

---

#### S2 — HIGH (evidence integrity): a transport timeout is recorded as `SCHEMA_INVALID`

**Observation (frozen evidence).** `execute_record.json`:
```json
"detail": "模型返回的结构化草稿无法读取：第 4/23 批调用未完成：Request timed out.",
"error_class": "SCHEMA_INVALID",
"final_identity": "zhipu-coding-plan:glm-5.3-flash:high",
"route_mode": "pinned"
```
"Request timed out" is a transport timeout, not a schema failure. The last receipt `receipt-0012.json` has **no `usage` block** and `elapsed_seconds: 600.0372` — exactly the client ceiling `timeout=600.0` set at `protocol_semantic_transport.py:331` (`max_retries=0`).

**Observation (code path).**
1. `protocol_deconstructor.py:4831-4834` returns the problem string `f"第 {batch_index+1}/{len(batches)} 批调用未完成：{exc}"` from the `except` around the batch call.
2. `:4942-4956` turns that string into `issue = _format_issue(collection_error)` and hard-codes `outcome="输出格式无效"`.
3. `:4048-4058` `_format_issue` always sets `issue_code="AGENT_OUTPUT_SCHEMA_INVALID"`, `check_name="tree_integrity"`, `repair_scope=["protocol_draft_json"]`.
4. `protocol_semantic_model_router.py:390-395` maps `outcome == "输出格式无效"` → `error_class = "SCHEMA_INVALID"`.

So **any** batch-call exception — timeout, HTTP 500, socket error — is reported as a schema problem, and `next_action` tells the operator/agent to "仅修正输出结构". This is exactly the misattribution the conference objective is at risk of inheriting: it would steer remediation toward the *source-policy schema* while the frozen evidence shows a 600 s timeout on a 13-message request.

Corroborating independent instances in the same artifact set: `da944f6e…/route-audit.json` attempt 1 is a **HTTP 500 `{'code':'500','message':'操作失败'}`** recorded as `error_class: "SESSION_ANOMALY"`; `09b593a7…/route-audit.json` attempt 2 is a **HTTP 401 authentication error** also recorded as `SESSION_ANOMALY`. Both are transport/provider-health failures wearing a schema/session label.

**Minimum remedy.** Classify by exception type at the boundary where the exception is still typed (`ProtocolAgentCallError.error_code == "TRANSPORT_TIMEOUT"` already exists, `protocol_semantic_transport.py:646-651`), and carry a distinct `error_class` (e.g. `TRANSPORT_TIMEOUT` / `TRANSPORT_ERROR`) into the attempt record before `_format_issue` collapses it. Do **not** change the clinical text of `problem`; only add the classification. This is a small, additive change and it makes the acceptance record truthful.

**Verification gap.** I could not decode the Pydantic/`_validation_error_summary` payloads actually stored in the 2 MB single-line `request-*`/`response-*` files (line-truncated at 2000 chars; no `jq`). So I verified the *classification chain* from source + the recorded `detail` string, not by re-parsing the stored exception object.

---

#### S3 — HIGH (self-contradiction): one capability, three call sites, two different fallback defaults, two opposite meanings

| line | expression | fallback when attribute absent |
|---|---|---|
| `protocol_deconstructor.py:4082` | `_compact_transport_history` gate | `_uses_compact_wire_contract(transport)` |
| `protocol_deconstructor.py:4100` | `_configure_transport_output_scope` gate | `_uses_compact_wire_contract(transport)` |
| `protocol_deconstructor.py:5181-5183` | `include_frozen_context=bool(getattr(transport, "supports_bounded_batch_context", False))` | **`False`** |

The third site also **inverts the polarity**. It asks "does this transport bound context?" to decide whether the **repair prompt must carry the frozen context itself**. For GLM the answer is `False`, so:
- `_repair_prompt` omits `_SYSTEM_CONTRACT` (`:1734`), and
- `candidate_context` is dropped because its condition is `if (compact or include_frozen_context) and candidate is not None and source_input is not None` (`:1710`) — and `compact=False` for GLM (see S4).

Net effect on the GLM route: a **targeted semantic repair prompt contains neither the frozen contract nor the target batch's source**, while the instruction text says *"请使用原会话中的冻结目录和方案原文"* (`:1683`) — i.e. it is explicitly designed to rely on the remote history. So the two "features" fight each other: S1 guarantees the history is unbounded (which is what makes this repair work), and any naive fix to S1 would silently break the repair path.

**Minimum remedy.** (a) Make the repair prompt **always** carry frozen context (the safe direction; it removes the dependency on session memory, and the payload is already built correctly at `:1711-1732`). (b) Then align the three gates on one named capability. Order matters: (a) before (b).

---

#### S4 — MEDIUM (prompt/schema mismatch, and this is the one that touches the source-policy fix): GLM never receives the provider-side strict schema, and the source-policy requirement is only nominally enforced there

**Observation.** `protocol_semantic_transport.py:406-417`:
```python
kwargs = {..., "response_format": {"type": "json_object"}}
if self._backend in _LOCAL_STRUCTURED_BACKENDS:
    kwargs["response_format"] = protocol_output_response_format(
        output_kind, compact=self.uses_compact_wire_contract, **self._output_scope)
```
GLM is not local ⇒ `response_format = {"type": "json_object"}`. Confirmed by the frozen request: `request-0000.json` contains `"response_format": {"type": "json_object"}` and **no** `json_schema`. Also `uses_compact_wire_contract` is `False` for GLM (`:382-385`, `_compact_wire` is never passed by app code — grep shows the parameter only exists inside the transport module), so `protocol_deconstructor.py:1543`
```python
schema_suffix = "" if compact else f"输出结构：{_compact_schema()}"
```
appends the **full Pydantic JSON Schema** at the *end of every batch prompt* — which, because of S1, is then retained and re-sent in all later batches. Confirmed present in the frozen prompt: `request-0000.json` contains `SemanticEvidenceRequirement`, `allows_screening_record_transcription`, and the marker `输出结构`.

**Why this matters to the assigned objective.** `tests/v2/agents/test_protocol_source_policy_generation.py:22`
```python
provider_schema = protocol_output_response_format(kind)["json_schema"]["schema"]
```
uses `compact` **defaulting to `False`**, so it asserts the *non-compact/local* provider payload. The real acceptance route (`zhipu-coding-plan`) receives no provider schema at all. Therefore the test's "prompt **and** provider require explicit source policy" claim does not describe the GLM route's actual enforcement; on GLM the requirement is prompt-only, and a prompt-only requirement is exactly what a real model can and did ignore (next item).

---

#### S5 — HIGH (verified by frozen provider output): the source-policy guard's error message is ambiguous and **demonstrably steers GLM into a non-fixing repair**

**Observation (code).** `app/domain/contracts/agent_io.py:132-142`
```python
@model_validator(mode="after")
def validate_predicate_ids(self) -> "SemanticEvidenceRequirement":
    if self.predicate_ids:
        if not {"allows_screening_record_transcription",
                "requires_contemporaneous_objective_source"}.issubset(self.model_fields_set):
            raise ValueError("明确关联条件时须同时说明资料来源要求，不能沿用默认值")
```
This is a **parse-path** guard keyed on `model_fields_set`, not a generation-path guard. It fires whenever a payload carries `predicate_ids` but omits the two booleans.

**Observation (frozen provider output).** `receipts/response-0011.json` is a real GLM-5.3-Flash SAR response. Its `choices[0].message.reasoning_content` says:

> *"The error says: \"明确关联条件时须同时说明资料来源要求，不能沿用默认值\" — when explicitly associating conditions (predicate_ids), must also specify source requirements (required_source_types), cannot use default values. … I need to add required_source_types to each evidence requirement that has predicate_ids."*

and the returned `evidence_requirements` in that same file carry `"predicate_ids":["IN04-SEG03-BLN-RTNSS-DEF-001"]` together with `required_source_types`, while the string `allows_screening_record_transcription` **does not appear anywhere in that file** (grep count = 0).

**Inference.** The model resolved "资料来源要求" to the field named `required_source_types` (资料来源**类型**) instead of the two source-policy booleans. The repair therefore does not satisfy the validator; that call cost **16,889 prompt tokens + 1,637 completion tokens and 41.58 s** and did not fix the stated problem. `request-0012.json` contains 3 such repair prompts, and the frozen history file `history-000-protocol-chat-1048031259.json` also contains exactly 3 — i.e. **every one of batches 1, 2, 3 in the session that later timed out needed a structural repair.** I verified the batch index of the timeout independently: `request-0012.json` contains `继续返回冻结目录的第 4/23 批语义结果。` exactly once, and its role sequence is `u,a,u,a,u,a,u,a,u,a,u,a,u` (13 messages) — consistent with 4 batch prompts + 3 repairs, and matching the recorded `第 4/23 批调用未完成`.

**Minimum remedy (highest value per character changed).** Reword the validator message so it names the fields and explicitly rules out the confusable neighbour — e.g. *"明确关联条件时，必须显式给出 allows_screening_record_transcription 与 requires_contemporaneous_objective_source；required_source_types 不能替代这两个字段。"* No schema change, no clinical semantics change, no route change. Optional reinforcement: state the same in the prompt's requirement block so the model never has to infer it from the error.

---

#### S6 — MEDIUM (backward compatibility): "retaining legacy read defaults" is only true for one of the two historical shapes

**Observation.** The stated intent is generation-strict / read-lenient: `protocol_deconstructor.py:535-546` `_semantic_generation_schema` adds both fields to `required` and pops `"default"` from their properties; `agent_io.py:118-119` keeps `True`/`False` defaults so old records still parse.

The read-leniency actually holds **only when `predicate_ids` is absent**, because the guard at `agent_io.py:134` is `if self.predicate_ids:`. And `predicate_ids` itself is new: the 2026-09-07 snapshot `artifacts/phase55-model-comparison/20260907/product-input-v1/product-code/domain/contracts/agent_io.py:112-120` has `SemanticEvidenceRequirement` **without** `predicate_ids` and **without** this validator (grep for `model_fields_set`/`明确关联条件` in that file: no matches).

**So the compatibility gap is the middle generation**: records written after `predicate_ids` was introduced but before both booleans became mandatory — where the model emitted `predicate_ids` and relied on the `True`/`False` defaults. Those now raise on read with the S5 message, and there is no migration/back-fill. That shape is not hypothetical: `response-0011.json` shows GLM producing exactly it on the real SAR protocol.

**Test coverage gap.** `tests/v2/agents/test_protocol_source_policy_generation.py:46-54` `test_unlinked_historical_requirements_remain_readable` validates only
```python
{"fact_type": ..., "due_stage": "screening", "description": "Historical record"}
```
i.e. the **no-`predicate_ids`** shape. There is no test for the `predicate_ids`-present-without-policy legacy shape. The test name therefore over-claims "historical requirements remain readable."

**Minimum remedy.** Choose one and record it: (a) add a test asserting the *intended* behavior for the middle generation (either it parses with defaults, or it fails closed with an explicit, documented reason and a named remediation), or (b) if failing closed is intended, say so in the PRD/design and change the test name so the guarantee is scoped. Do **not** silently loosen the generation requirement.

**Verification gap.** I cannot tell from the read set whether any *persisted* middle-generation record exists (that needs the DB, which is out of scope). I can only prove the shape is producible and that the guard rejects it.

---

### 2. Direct answers to the four questions in the assigned scope

**Q1 "challenge new generation-only explicit source-policy requirements."**
- They are *not* purely generation-only: `agent_io.py:132-142` is a parse-path guard (S5/S6).
- The generation half does not reach the acceptance route with any force: GLM gets no provider schema (S4), so the requirement is prompt-text only, and the one frozen sample shows it being violated and the confusable error being misread (S5).
- The prompt carrier is applied at the worst possible position and cost: `_compact_schema()` (full Pydantic schema, ~large) is appended to *every* non-compact batch prompt (`:1543`), so under S1 it is retained and re-sent in every later batch.

**Q2 "verify old persisted read compatibility."**
- Holds for the pre-`predicate_ids` generation (proven against the 2026-09-07 snapshot).
- **Does not** hold for `predicate_ids`-present records lacking the booleans; untested; no migration. → S6.

**Q3 "why is `supports_bounded_batch_context` local-only?"**
- It is not derived from any capability of the *operation*; it is the backend-class predicate `_backend in _LOCAL_STRUCTURED_BACKENDS`, i.e. the same predicate as `uses_compact_wire_contract` (`:382-385`). It is a naming collision between "local structured backend" and "can bound the conversation", and the operation itself (`compact_session_history`, `:702-714`) is backend-agnostic and lives on the one shared class. No evidence in the frozen artifacts supports excluding cloud backends; the run already safely uses the "fresh session + full batch prompt" pattern mid-flight. → S1.

**Q4 "would enabling bounded contexts lose source context?"**
- **No loss of frozen source context.** For every batch ≥2 the next prompt is built with `scoped_source=True` (`:4763`) → `_batch_prompt_payload` re-attaches that batch's `parent_rule_catalog` items with their `source_span_ids`/`source_excerpts`, the batch's `source_materials` verbatim text, `allowed_source_span_ids`, `batch_rule_codes`, `candidate_id`, `agent_call_id`, plus the schema suffix. The compaction anchor passed at `:4819-4824` already carries `candidate_id` and the completed batch id, and cross-batch consistency is enforced by `_validate_semantic_batch` (`:3529-3561`) and `_merge_semantic_batches` (`:3636+`), not by model memory.
- **What does change**: the model's own prior-batch reasoning and prior assistant outputs are dropped — which is the whole point. **And two real risks must be handled before enabling it:** (i) S3's repair path currently *depends* on the retained history (`:5181-5183` + `:1710` + `:1734`), so compaction must not land before the repair prompt is made self-carrying; (ii) compaction is destructive and changes failure/resume semantics — after a compaction the persisted/anchor history ends with an assistant placeholder, and `restore_history` (`:683-700`, requires the last turn to be `assistant`, and refuses to overwrite an existing session) plus `_collect_initial_semantic_response`'s cache path (`:4789-4805`) are the only recovery routes. The frozen evidence shows recovery in this run actually happened by starting *fresh sessions* (attempts 6/7/9 are 1-message requests), not by restoring history — so I recommend confirming that intended resume behavior explicitly rather than assuming it.

---

### 3. Recommended bounded verification/comparison **before** any route-wide change

Order matters; every step below is deterministic and needs no clinical judgment.

1. **Pure unit assertions (no network, no provider call).** Using the existing public accessors: assert that for `backend="zhipu-coding-plan"` (and `"deepseek"`) `transport.supports_bounded_batch_context` reflects the *intended* policy, and assert that `_compact_transport_history(transport, sid, context="…")` collapses `transport.history(sid)` (accessor already exists at `protocol_semantic_transport.py:716-719`) from `2k+1` messages to exactly 2. Put this in the same module as the tested behaviour so it cannot drift from the acceptance route. This is the single cheapest guard against S1 regressing again.
2. **Frozen-evidence arithmetic check (no execution of the product).** Recompute the per-batch `prompt_tokens` increments from `receipts/receipt-0000…0005.json` and confirm they equal `(retained fixed block) + (new batch payload) + (previous assistant content)`; the assistant-content term is directly derivable as `completion_tokens − reasoning_tokens` (803 / 597 / 1,357 / 1,401 / 1,051). This proves the growth is *history resend* rather than a per-batch payload increase, using only frozen files. (I could not complete the fixed-block/payload decomposition myself: with 5 equations and ≥7 unknowns it is underdetermined, and `jq` was unavailable. That is deliberate scope honesty, not an omission to paper over.)
3. **Only then, one pinned single-route comparison.** Re-run exactly one `zhipu-coding-plan:glm-5.3-flash:high` attempt on the same frozen SAR input (`route_mode: "pinned"`, no fallback), and compare against the frozen baseline on: `route_audit.accepted_batches`, per-batch `prompt_tokens` (must fall toward ~10k/batch), total `elapsed_seconds`, and — separately and later — the semantic gate verdict. Do **not** change the route chain, the prompt template, or the clinical contract in the same step; otherwise the comparison cannot attribute the delta.
4. **Separately, and independently of 1–3: fix S2's misclassification and S5's message wording.** Both are additive/local, both improve the next acceptance record's truthfulness, and neither affects model behavior in a way that invalidates comparison 3 *if* they land first and are recorded as such. I recommend landing S5's wording **before** comparison 3 so the repair-loop cost is measured against the corrected message.

---

### 4. Most important objections

- **O1 — The record's `SCHEMA_INVALID` is not the failure.** If Codex inherits that label, the conference will optimize the source-policy schema while the frozen evidence shows a 600.0 s client timeout (`receipt-0012`, matching `timeout=600.0` at `protocol_semantic_transport.py:331`) on a 13-message request, plus two sibling audits where HTTP 500 / HTTP 401 were labelled `SESSION_ANOMALY`. Misclassification is the top systemic defect here, not any single missing field. (S2)
- **O2 — Do not flip the compaction flag first.** S3 means that flipping it before making the repair prompt self-carrying converts a slow-but-working repair path into a broken one. My proposal therefore deliberately sequences "make repair self-carrying" → "align the three gates" → "bounded comparison". If Codex prefers a faster experiment, the honest framing is "we accept a temporary repair-path regression for one comparison run", stated up front.
- **O3 — The timeout is a second, independent blocker.** Observed single-call latencies in this run reach 528.70 s and 484.54 s, against a 600.0 s client ceiling — a margin of ~1.13×. Even a perfectly compacted 23-batch session can still die on one slow high-effort call, and `_send_completion` deliberately re-raises timeouts without retry (`:476-477`). I am *not* recommending silently raising the timeout or adding retries (both change the frozen acceptance identity); I am recommending that Codex decide explicitly between (a) treating this run as a latency/health failure and re-running the pinned comparison, and (b) making a timed-out *batch* call a resumable checkpoint instead of terminal — and record which. My safe provisional path: keep the transport contract as-is, fix S2 so the failure is labelled correctly, and re-run the pinned comparison after S5 and S1's bounded check.
- **O4 — `source-policy-generation.xml` (21 passed, 0 failed) does not establish the claim in its own module docstring.** The file's assertions cover the non-compact provider payload, `_wire_evidence_requirement_schema()`, and the no-`predicate_ids` legacy shape. They do not exercise the acceptance route's actual configuration (non-compact + no provider schema) and they do not cover the `predicate_ids`-present legacy shape. I am explicitly **not** declaring the suite insufficient overall — only that these four cases cannot carry the "prompt and provider require explicit source policy" conclusion for GLM. (S4, S6)

### 5. Decision points for Codex

- **D1** — Accept S2's reclassification (add a transport-failure `error_class` alongside `SCHEMA_INVALID`) as a prerequisite for any further interpretation of the `fresh-sar-protocol` failure? (My recommendation: yes.)
- **D2** — Accept S5's message reword as a minimal, semantics-preserving repair, and land it before the next pinned comparison? (My recommendation: yes.)
- **D3** — For S6, is the middle generation `predicate_ids`-present-without-booleans (i) meant to fail closed, or (ii) meant to read with defaults? Either answer is fine; leaving it unstated + untested is what I object to.
- **D4** — For S1, approve only the ordered sequence *unit assertions → frozen arithmetic → one pinned comparison*, with no route-wide change until that comparison exists? (My recommendation: yes; this is also the smallest change that answers "would enabling bounded contexts lose source context".)
- **D5** — For O3, which branch: health-failure re-run, or resumable-batch checkpoint? These are not equivalent and the second is a Controlled change to failure semantics.

### 6. Bounded questions to Codex

- **Q1** — Is the middle generation of `SemanticEvidenceRequirement` (has `predicate_ids`, lacks the two booleans) known to be persisted anywhere in a live project DB? If yes, `agent_io.py:132-142` is a live read break and the S6 remedy becomes mandatory rather than a test-name fix. *(Why it matters: it converts a coverage gap into a production-compatibility defect. Safe provisional path: assume it may exist and treat the guard as a read break until disproved.)*
- **Q2** — Does the acceptance definition require the `fresh-sar-protocol` execute to be a single uninterrupted session, or is a fresh-session restart mid-run (as attempts 6/7/9 already do) acceptable? *(Why it matters: it decides whether compaction's change to resume semantics is even in scope. Safe provisional path: treat the frozen `execute_record` + receipts as a single acceptance attempt with restart allowed, since the run already did exactly that.)*
- **Q3** — Can you supply, or authorize me to read, the configured `DECONSTRUCT_GLM_*` request ceiling and GLM-5.3-Flash's context window from the product config? *(Why it matters: it converts my extrapolated "batch-23 prompt ≈142k–256k may exceed the context window" from inference into fact, and it bounds D5.)* I did not read private configuration because the scope excludes it.
- **Q4** — For the frozen-evidence decomposition in §3 step 2, is a one-off read-only extraction of the stored `problem` strings from `request-0001/0011/0012` acceptable (needs `jq`/Bash, which is unavailable to me here)? *(Why it matters: it would let me name the exact 3 repair causes instead of reporting "3 repairs occurred, cause not extractable". Safe provisional path: report the count and the one cause I could read from `response-0011.json`'s `reasoning_content`, and leave the other two open.)*

### 7. Explicit uncertainties

- The batch-23 cost figures are **linear extrapolation** from 5 measured increments in one 6-batch session; the frozen run only reached batch 4 in the timed-out session. Treat as an order-of-magnitude argument (≈7×–13×), not a measurement.
- The exact `problem` text behind 2 of the 3 observed structural repairs could not be extracted (single-line multi-MB JSON, no `jq`). I verified the *count* (3) by two independent carriers (`request-0012.json` and `history-000-protocol-chat-1048031259.json`) and the *one* cause I could read.
- I did not run any test. My statements about test *coverage* are from reading the test source; `source-policy-generation.xml` is cited only as the recorded pass/fail artifact supplied in the read set.
- Whether the workspace is currently mid-change (Trellis reported a clean detached-HEAD state and no active task) was not verified by me beyond what the frozen artifacts describe; I attributed nothing to uncommitted work.

### 8. No-material-defect statement (scoped)

In the parts of the read set I was asked to review for *this* purpose, I **did** find material defects (S1–S6), so this pass does not return "no material defect". Conversely, the specific claim "the generation-only explicit source-policy change is safe and correctly tested" is **not** established by the artifacts I was given, for the reasons in S4/S5/S6 — I am not asserting the change is wrong, only that its stated guarantee is unproven on the acceptance route. Codex retains final clinical, product, and user-facing acceptance; nothing above is a final acceptance statement.
