I'll start with a bounded read-only audit of the assigned source set and conference context, then trace the formal publication and ActionRequest control-origin chain before writing the evidence report.Conference context is in place. Next I’ll read the assigned source modules and trace the publication/action-origin chain.ActionRequest and storage look like the high-risk spots. I’ll read those serializers, column mapping, and consumers next.I've got the publication and history chain. Next I’ll inspect serializers, authorization, frontend handling, and a few likely hash/atomicity defects.# Conference Output: r05-formal-publication-actions-20260914 - evidence_single_object

## Output

只读全链审阅结论：**现有代码可以把「accepted=false 的控制计算结果」写成正式报告部件，并进入既有 ActionRequest 生命周期（OPEN，强制项 BLOCKING）**。旧条款待办的载荷哈希兼容大体成立；正式 HTTP 发布入口未接线；`review-method-adoption` / `binding-adoption-authorization` 在 `app/` 内只有校验、没有签发。这三件事都还不能当完成。

本角色不拥有最终临床/监管/视觉/现网接受权。未跑测试、未 import 应用、未读写 DB、未改文件。

---

### 1. Evidence（源码事实）

**额外读取（初始清单之外，为核对设计口径与接线）：**
- `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §17.1–17.6
- `app/services/frozen_review_calculation.py`
- `app/services/qualified_binding_selection.py`
- `app/services/review_action_publication.py`
- `app/projections/control_review_outcome.py`
- `app/projections/control_calculation_experiment.py`
- `app/domain/control_layer_evaluation.py`
- `app/domain/policies.py`（`ACTION_CONTENT` / `derive_action_blocking_level`）
- `app/storage/codecs.py`、`app/storage/idempotency.py`、`app/storage/concurrency.py`
- `app/storage/review_reference_validation.py`
- `app/api/v2/review_actions.py`、`app/api/v2/app.py`、`app/main.py`

**发布主链**
- `publish_frozen_review`（`app/services/frozen_review_publication.py` L32–160）：校验非空授权与幂等键 → 按 `formal-review:{context_id}` 查回执 → 校验 `review-method-adoption` 门禁 → 读评测工件 → 回执核实资格选择 → `calculate_frozen_review` → `session.begin_nested()` 内写 `ReviewRun`、逐条 `FinalAssessment`、条款待办、可选控制快照与控制待办 → 末尾 `get_run` → `receipts.resolve`。注释写明不签发方法批准、不发现凭证、不跑模型。
- `app/` 内没有任何 HTTP 路由调用 `publish_frozen_review`。`app/api/v2/app.py` L388–390 只挂了历史 GET 和办理 POST。`app/main.py` 不挂 V2 这些路由。
- `review-method-adoption`、`binding-adoption-authorization` 在 `app/` 内只出现在校验侧（`frozen_review_publication.py` L69–73；`qualified_binding_selection.py` L115–120），没有签发实现。

**原子性 / 幂等 / 历史不改写**
- 回执检查在嵌套事务之外（L52–60）；`run` 是否已存在的检查也在嵌套之外（L84–86）；计算同样在写事务外（L76–80）。
- 嵌套事务内最后才 `receipts.resolve`（L158–159）。`IdempotencyRepository.resolve`（`app/storage/idempotency.py` L102–164）对同键同哈希复用、异哈希冲突；用 SQLite `on_conflict_do_nothing`。
- `_flush_guarded`（`app/storage/repositories.py` L185–197）在 `IntegrityError` 时执行 `session.rollback()`，回滚的是整个 Session，不是 savepoint。
- 控制待办重入：先比 gate，再比除 `revision/state/transitions` 外的字段；有行无 gate 则拒绝（`control_action_publication.py` L66–79）。条款待办同一模式（`review_action_publication.py` L83–96）。
- 人工办理只追加一条 transition，禁止改写前缀与原要求（`review_action_command.py` L110–136；`ActionRequestRepository.replace` `repositories.py` L2440–2452）。`schema_version != review/v2` 直接拒绝（`review_action_command.py` L49–50）。

**旧载荷哈希兼容**
- `ActionRequest.serialize_action_evidence`（`review.py` L385–392）：`control_origin is None` 时 `pop("control_origin")`。符合设计 §17.6「新空字段仅在旧载荷中省略，不全局 exclude_none」。
- `assessment_id` / `rule_component_id` 改为可空后，旧行仍带原字符串，不会因为新字段缺省而改写旧 JSON。
- 迁移 `0027`（`app/storage/migrations/versions/0027_action_control_origin.py`）只改表结构，不改 `payload_json`。有控制行时拒绝降级（L65–66）。升级路径会 `raw.commit()` 并 `PRAGMA foreign_keys=OFF` 整表重建（L23–56）。文件头写明最终验收推迟到隔离整产品验证。

**控制来源 / 强度**
- 新来源合同只有 `review_run_id, protocol_control_id, obligation_id, modality`（`control_action_origin.py` L8–13）。校验器禁止与条款结论混用，且 `origin.review_run_id == action.review_run_id`（`review.py` L398–404）。
- 非 mandatory 一律 `BlockingLevel.ATTENTION`，mandatory 走 `derive_action_blocking_level`（`control_action_publication.py` L49–50；`review.py` L431–435）。`OBSERVATION_UNVERIFIED` / `SOURCE_CONFLICT` 对强制项都是 BLOCKING（`policies.py` L246–251）。
- `control_action_gaps`（`control_action_directives.py` L6–12）：仅 `status == "unverified"` 生成待办；`observation_reason_codes` 含 `source_conflict` 则只保留 `SOURCE_CONFLICT`，否则 `OBSERVATION_UNVERIFIED`。`unfulfilled` / `not_applicable` / `fulfilled` 不生成 ActionRequest。
- 控制计算在事实属于任何 `member_kind=="fact"` 争议组时，把该观察写成 `UNKNOWN + ["source_conflict"]`（`control_calculation_experiment.py` L152–162）。设计 §17.2：不得因结果不同直接声称来源冲突。设计 §17.6：基础事实被某条款使用，不证明派生争议影响该条款。
- `ControlReviewOutcome.accepted` 与 `ReviewControlSnapshot` 注释均为「保存报告不等于临床批准」（`control_review_outcome.py` L54, L59–64）。`publish_control_actions` 仍创建 `state=OPEN` 的 ActionRequest。
- 义务组 `activation == UNKNOWN` 时，组内每条义务 `status=unverified`（`control_review_outcome.py` L50–53；`control_layer_evaluation.py` L117–122 起触发未知会传到 activation）。

**资格授权 / method-adoption**
- 有控制目录时，正式计算要求 predicate+control 两份已核实选择，禁止重复或遗漏（`frozen_review_calculation.py` L101–106）。
- `assert_qualified_selections_match_review_context` 核对 authority、episode、事实集合、控制目录（L450–511），不把资格作业直接当成临床采信。
- 方法门禁只绑定 publisher/evaluator/consumer 版本和评测工件哈希（`frozen_review_publication.py` L65–73），不绑定受试者/节点。个案绑定靠资格授权门禁 + 上述上下文核对。
- 空选择在计算里保持 UNKNOWN；发布仍把整次审核写成 `completed_at=now` 的已完成 `ReviewRun`（L81–92, L157）。

**报告 / 办理联动**
- 发布末尾 `get_run`：已完成运行必须有全量条款结论、全量控制结果、以及 `expected_gaps == handled_gaps`（`review_history_service.py` L535–560, L460–468）。缺一件则整批 savepoint 回滚。
- 历史 API 把控制压成义务行，不含 `reason_codes` / `observation_reason_codes` / `activation`（`review_history.py` L487–494）。前端解码同样不要求「已完成 ⇒ 每条 unverified 都有待办」（`reviewHistoryHttp.ts` L827–837），只要求 action.control 能对上 control 键。
- 报告页控制表只显示状态；待办表用 `clause ?? control` 身份，并走同一办理对话框（`FrozenReviewReport.tsx` L99–160）。无待办且存在 unverified/unfulfilled 时提示「尚未保存对应办理事项」（L118–119）。
- 办理 HTTP 已启用（`review_actions.py` L32–46），不区分条款/控制来源；`validate_action_response` 只核回应资料权威（`review_reference_validation.py` L53–69）。

---

### 2. Inference（不是源码字面）

1. 当前实现把「计算未批准」和「办理事项已对用户生效」拆开了：快照 `accepted=false` 不能阻止 BLOCKING 待办进入正式报告和办理 POST。
2. `source_conflict` 从「事实在某个争议组里」提升为 INVESTIGATOR 冲突核实待办，强度超过设计允许的保守 UNKNOWN。
3. 触发/例外未知会把整组义务打成 unverified，再按义务逐条生成「核对现有原始资料归属」待办；真正缺的是适用性/触发/例外，不是每条义务的观察。
4. 同幂等键并发：先通过回执=空，再撞上已提交的 `ReviewRun`，会报「已有保存记录但缺少对应回执」，即使赢家已经写了同一回执。`_flush_guarded` 的整会话 rollback 还会打掉 savepoint 隔离。
5. 旧条款 ActionRequest 在 decode/response 时 `pop("control_origin")`，与历史门禁 `output_hash` 对齐；这是本扩展里真正做对的哈希兼容点。
6. 方法门禁未签发 ⇒ `publish_frozen_review` 在真实路径上进不了写事务。这是关闭，不是完成。

---

### 3. 缺陷与最小修复（按影响）

**D1 — 最高影响：争议组成员身份被写成 SOURCE_CONFLICT 办理事项**

- 位置：`app/projections/control_calculation_experiment.py` L152–162；`app/domain/control_action_directives.py` L6–12；`app/services/control_action_publication.py` L30–50。
- 问题：事实只要出现在任何 fact 争议组，观察原因就是 `source_conflict`；`control_action_gaps` 再把它变成 `GapType.SOURCE_CONFLICT`。强制项因此得到 BLOCKING、负责方 INVESTIGATOR、文案「核实相互冲突的资料」。这与 §17.2 / §17.6 直接冲突，也把隔离实验（`accepted=false`）写进既有行动状态机。
- 最小修复：发布用的 gap 函数不要消费「组成员 ⇒ source_conflict」。仅当该义务实际消费的属性已证明冲突时才发 `SOURCE_CONFLICT`；否则保持 `OBSERVATION_UNVERIFIED`。计算层即使暂留该 reason，也不得单独作为办理升级依据。在评测批准签发前，控制待办的 `blocking_level` 对这类 UNKNOWN 不得高于 ATTENTION——若这改变产品语义，先由 Codex 裁决，而不是靠 `accepted=false` 假装没发布。

**D2 — 触发/例外未知时，义务级待办扇出**

- 位置：`app/domain/control_action_directives.py` L6–12；`app/projections/control_review_outcome.py` L50–53, L75–76；`app/services/control_action_publication.py` L28–33。
- 问题：`reason_codes=["activation_unverified"]` 仍走义务级 `OBSERVATION_UNVERIFIED`。一组 N 条义务会得到 N 条几乎相同的 CRA 待办，文案还在说核对本条观察归属。
- 最小修复：`control_action_gaps` 若 `activation_unverified` 且本条 `observation_truth != UNKNOWN`，不要发义务级待办；改为按未核实的 trigger/exception 原子发一条（或按组一条）待办。历史 `expected_gaps` 与发布必须用同一个函数，避免已完成报告读不出来。

**D3 — 正式保存幂等 TOCTOU，且 unique 冲突会 rollback 外层事务**

- 位置：`app/services/frozen_review_publication.py` L52–60, L84–86, L100–159；`app/storage/repositories.py` L185–197。
- 问题：回执检查和 run 存在检查都在 `begin_nested` 之外。同键并发会把「已成功保存」误报成「有 run 无回执」。`_flush_guarded` 的 `session.rollback()` 会拆掉 savepoint。
- 最小修复（本包范围内）：在 L84–86 若 `runs.get_or_none(run_id)` 非空，立刻再读同一 `(scope, idempotency_key)`：同哈希则 `get_run` 后返回；异哈希则 `IdempotencyConflict`；无回执才维持现错。不要把 `_flush_guarded` 改成全局静默吞冲突。

**D4 — 控制结果/待办原因无法在报告首屏区分**

- 位置：`app/api/v2/review_history.py` L225–237, L487–494；`frontend/src/api/review-history/reviewHistoryHttp.ts` L810–837；`frontend/src/components/review/FrozenReviewReport.tsx` L99–119。
- 问题：§17.4 要求先回答「有什么问题、补什么」。控制行只有 status；前端完成态也不核「unverified ⇒ 必有待办」。后端 `get_run` 对完成态是核的，但 HTTP 合同把原因丢掉了。
- 最小修复：DTO 增加冻结的 `reason_codes` / `observation_reason_codes`（或只加已投影的 `gap_type`）。前端完成态复现 `expected_gaps`。在 D2 落地前不要先改文案充数。

**D5 — 迁移 0027 的连接级 commit + FK 关闭重建**

- 位置：`0027_action_control_origin.py` L23–56。
- 问题：`raw.commit()` 可能提交 Alembic 外层事务；FK 关闭后重建，失败提示靠备份恢复。文件自己把最终验收推迟了。
- 最小修复：只在隔离库跑：历史条款行 payload 哈希不变、CHECK 两支、有控制行拒降级、重建后 `PRAGMA foreign_key_check`。不要在临床库跑。不把 DDL 成功当成通过。

**不是缺陷、但不得标完成**
- 正式发布 HTTP 未启用：观察，且应保持。
- 方法批准 / 资格授权签发未实现：校验关闭是对的；没有签发就不存在可发布路径。
- 临床语义完整性仍开放：空选择 → UNKNOWN → 未核实待办，这是保守，不是「已证明资料缺失」。
- 旧 ActionRequest 省略 `control_origin`：当前 serializer 做对了。

---

### 4. Uncertainty（未在本角色内关闭）

- 未在运行时验证 datetime 往返（`Z` vs `+00:00`）是否会让控制待办重入时 `old_gate != gate`。
- 未验证 SQLite MATCH SIMPLE 下 `(rule_set_id, rule_set_revision, rule_component_id)` 复合外键对 `rule_component_id NULL` 的控制行是否接受。
- 未验证 `0027` 整表重建是否完整保留既有 CHECK/复合外键/关联表。
- `derive_action_blocking_level` 写在 `ActionRequest` 校验器里，decode 时会重跑；改政策会使旧行无法读取。条款待办也有这个耦合，控制来源多了一条 modality 分支。
- `unfulfilled` 强制项不生成 ActionRequest：可能是「已判定未满足，不是补资料」，也可能是漏了方案偏离办理。源码不能单独裁决。

---

### 5. 对当前方案的异议（不要把表面闭环当成完成）

1. **异议：** `ControlReviewOutcome.accepted is False` 不能保护产品。同一事务里写出来的 ActionRequest 是真待办，历史报告和办理 POST 都会用。
2. **异议：** 「带未决项完成审核」（§17.6）不等于可以把未证明的 `source_conflict` 写成 INVESTIGATOR BLOCKING 项。保守 UNKNOWN 应停在 unverified + 核实归属，而不是升级成冲突结论。
3. **异议：** 发布末尾 `get_run` 只能证明「按当前 gap 函数自洽」，不能证明 gap 函数临床正确。函数一改，旧完成报告会读失败（fail-closed），但错误待办一旦经隔离库写出去，办理历史已经落地。
4. **异议：** 不要为了打通演示去签发 `review-method-adoption` 或打开 HTTP。那会把 D1/D2 送进既有行动链。
5. **异议：** 前端「尚未保存对应办理事项」把 `unfulfilled` 和「漏写待办」混在一起；在 Codex 决定 unfulfilled 要不要行动之前，这句会误导。

**建议的安全暂行路径：** 保持发布 HTTP 关闭；不要签发方法/资格采用门禁；先改 D1/D2/D3；D5 只在隔离库做。在此之前不要把 `publish_frozen_review` 接到任何共享库。

---

### 6. 请 Codex 裁决的问题（会影响修复形态）

1. **强制项 `unfulfilled`：** 只在控制表显示「未满足」，还是要进既有 ActionRequest（例如方案偏离/需研究者说明）？在未裁决前，我按「不补造未设计的偏离工作流」处理，并保持 D4 的原因字段可见。
2. **争议组成员：** 正式控制待办是否允许在属性级证明之前使用 `SOURCE_CONFLICT`？我的暂行路径是不允许，只保留 `OBSERVATION_UNVERIFIED`。若产品暂时要冲突待办，也应降为 ATTENTION，且文案不得写成已证实冲突。
3. **`activation_unverified`：** 按未核实的 trigger/exception 原子生成一条待办，还是按义务组一条？不应对组内每条已观察义务各写一条。
4. **同键并发：** D3 的「run 已存在则重读回执」是否接受？另一种是继续 fail-closed，但那会把成功的并发重试打成「无回执」。

以上四问未答之前，不建议启用正式 HTTP，也不建议签发 `review-method-adoption`。
