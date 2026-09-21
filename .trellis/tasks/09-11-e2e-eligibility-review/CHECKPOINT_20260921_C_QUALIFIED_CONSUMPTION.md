# CHECKPOINT 2026-09-21：C链资格消费接入完成（WP05核心）+ WP03/A01 + 评测证据harness

## 追加（同日晚些）

### 4. WP03/A01 位图正文门控（提交 9e5621ec）
- `decide_route_detailed`新增A01混合页降级：正文是整页位图（image coverage≥0.5）
  且文字层只挂页边（行带覆盖≤0.2）→ VISION_OCR。纯版面几何合取，无字符数启发；
  只降级不升级——真文本页/可检索扫描PDF不受影响。
- `NativePage`新增`large_image_coverage`（钳制位图面积占比）。
- 真实blob扫描验证：现有纯扫描页（93-98%位图、零文字）本就走VISION_OCR，
  文本页维持native——零既有路线变化，纯前瞻保护。
- 新增6个场景测试（tests/v2/evidence/test_page_processor_a01.py）全过。

### 5. 方法采用评测证据harness（用户接手路径已打通）
- `app/services/binding_evaluation.py`：gold拆分校验+打分+类型化
  `BindingEvaluationManifest`落盘（evaluation_manifest工件）。
  方法字段直接取自verify_completed_binding_qualification重建结果，
  与`require_evaluated_binding_method`按构造一致。
- `scripts/build_binding_gold_split_template.py`：从真实资格任务生成137条
  标注模板（expected/forbidden留空，参考清单仅作对照，不从模型输出派生金标）。
- `scripts/record_review_method_adoption.py`：**用户亲自行使**采用决定的工具
  （写入ReviewMethodApproval + review-method-adoption gate）。AI不得代跑。
- 13个纯逻辑测试全过（tests/v2/services/test_binding_evaluation.py）。

### 用户接手路径（C链最后一步）
1. `python scripts/build_binding_gold_split_template.py --qualification-job-id d37600378dea4952935bb098c4f007d7 --out gold.json`
2. 依据原件/方案独立标注 gold.json（expected/forbidden + annotated_by）
3. `build_binding_evaluation_manifest(...)` 产出评测清单（manifest sha）
4. 审阅指标后：`record_review_method_adoption.py --manifest-sha <sha> --approving-principal ... --approval-source-file ...`
5. 配置`ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID=<gate_result_id>`后
   `POST .../prepared-review-workflows/47c4ef67bf0a45ee.../publish`

## 本次完成

### 1. get_coverage持久化比对修复（阻塞投影的硬bug）
- `PageCoverageEntry`新增`source_policy_kind/verification`为payload-only字段（无ORM镜像列），
  `get_coverage`的entries表比对把所有历史覆盖记录误判为不一致
  （`PersistedContractInvalid: 页覆盖处置关联表与合同正文不一致`）。
- 修复：`app/storage/page_review_repository.py`比对时剔除`source_policy_*`两个无镜像键。
  payload完整性仍由`payload_sha256`保证，不弱化校验。
- 同时修复`test_reread_predecessor_is_source_bound...`的措辞不匹配（改为当前报错文案）。

### 2. 投影消费资格核对结果（WP05完整资格消费）
- `_load_binding_predicate_fact_ids`不再使用未核实的双路候选交集，
  改为：定位authority匹配的predicate candidates任务→定位其对应的已完成
  `binding_qualification`任务→`verify_completed_binding_qualification`完整重建→
  仅取`structurally_valid && dual_agreement`配对的fact选择。
- 映射对全部官方谓词完整（未核实=空表→evaluator按observation未核实UNKNOWN）。
- 投影侧expectations/source_gaps无条件传递（ER-03修复已在位）；
  `component_review`仅在trigger为definite时移除观察/记录类gap（合理范围）。

### 3. 验证结果
- IN-01 = inclusion_met（直接投影+API双重验证，6个fact refs，无gap）。
- 68条indeterminate是正确安全行为，原因有二：
  a) 候选任务对137个谓词全部求值，但只有8-9个谓词在55条已发布事实中找到候选
     （B链事实覆盖是确定性上限，不是C链管线缺陷）；
  b) 跨章control的采用与消费仍在前方。
- 测试：storage/domain/llm套件与基线对比修复4个、无新增失败
  （其余为MTPLX/云环境依赖的预存失败）。
- 提交：0db7b1b3 已推送GitHub。

## C链当前全貌（决策所需）

已完成管线（全部completed）：
- prepared_review_workflow 47c4ef67（含predicate+control qualification子任务）
- predicate_binding_candidates 4c87dff9 → binding_qualification d3760037（21对/9身份，5身份双路一致）
- control_binding_candidates bf61e93e → binding_qualification 2bee93ec
- protocol_control_execution 09084347（23:43完成，175检查点）

官方ReviewRun发布的剩余前置（不可由AI自授权，设计边界）：
1. 方法采用评测证据：`binding_semantic_correspondence`评测清单
   （`BindingEvaluationManifest`：source_corpus+gold_split+scoring_report+methods+observed_metrics）。
   gold_split须独立人工标注（评测文档：gold不入生产Agent；legacy K10项目协议不同，
   不能作当前链gold）。
2. 用户方法采用：`ReviewMethodApproval`（approving_principal+approval_source）+
   `review-method-adoption` gate（gate_results中尚无）。
   `authorized_clinical_adoption`为`Literal[False]`硬编码——资格阶段永不自授权。
3. 二者齐备后：`POST .../prepared-review-workflows/{id}/publish`
   （`ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID`当前为空，需配置）。

## 下一步（按V4顺序）

1. WP03：页manifest全覆盖检查（A01：只有页码文字层、正文扫描场景）。
2. WP05余项：control资格消费接入投影（跨章处置已有PENDING_CONTROL_APPLICABILITY基础）。
3. 评测harness脚手架（corpus/gold split/scoring程序），gold标注与采用决定留给用户。
4. WP06前端工作台（B1-B4）。
- B链事实覆盖（55条）是当前条款确定性上限；更多证据文件上传→更多事实→更多definite。
