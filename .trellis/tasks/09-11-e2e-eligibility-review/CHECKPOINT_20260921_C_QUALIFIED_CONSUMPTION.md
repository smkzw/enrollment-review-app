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

## 续（同日第二轮）：WP03收尾 + WP05审计 + WP06问题队列

### 6. WP03 A02–A09 审计结论（4f244670）
- 逐场景核对既有机制与测试：旋转canonical坐标（pdf_native+executor测试）、
  重复文本降级（locator+risk测试+R13不按文本去重）、分段OCR区域隔离
  （segmentation+分段请求合同）、手写对账主A优先（reconciliation+回归测试）、
  标量语法保真（test_page_scalar_grammar）、数值事实必须显式单位（合同校验+
  unitless测试）——均已实现且有测试。
- 补齐两个薄弱钉扎（tests/v2/evidence/test_wp03_scenarios.py，7个测试）：
  A08 低置信INFORMATIONAL不阻断+OCR提示禁补字；A09 未知/空内容→显式FAILED页
  （缺页不静默丢弃）+record_time与date_range字段级分离（记录日期≠事件日期）。

### 7. WP05控制消费审计
- 控制资格任务（2bee93ec）23个控制原子全部no_candidates_in_supplied_input、
  0对双路一致——上游候选为空（55条基线事实不含控制相关观察）。
- 无可消费数据；模板级PENDING_CONTROL_APPLICABILITY处置（R05）即当前正确状态。
  完整控制消费路径已在frozen_review_calculation（control_input/control_selections）
  就位，等待上游证据。

### 8. WP06 问题队列（c8568be6）
- EligibilityWorkbenchPage新增问题队列：风险/冲突/未决按根因（投影gapType）
  聚合+条款影响计数；组内全量渲染不截断；点击即复用条款详情/原件下钻。
- 前端GapType联合类型与labels卫生测试补齐control_applicability_pending。
- 验证：工作台12/12、全前端583/583、tsc清；ego-browser实测1080P/2K/4K
  真实数据（68条→1根因组）渲染与下钻正常。

### 下一步
- WP06余项：issue详情增强（对象/时间/冲突各方/具体动作聚合显示）。
- WP07：更正/补证增量复用与影响闭包。
- WP08：30–150页规模验证与全仓剩余验收。
- C链官方发布：等待用户gold标注与方法采用（人机边界，见上文第5节）。

### 9. WP06 issue详情动作指令（9c3c3479）
- 投影线新增action_owner/action_detail/action_evidence（来自domain.policies
  ACTION_CONTENT注册合同，仅有缺口时给出）；API DTO、前端视图模型、详情面板
  "建议动作·责任方+动作+可接受证据"贯通。
- 验证：API对68条缺口条款全部返回动作字段；前端584/584、tsc清；
  1080P实测渲染正常。对象/时间经fact_refs下钻呈现，冲突各方经
  病史不一致横幅+档案页呈现（既有能力）。

### WP06退出标准对照（当前数据前沿）
- 默认风险/冲突/未决队列+根因聚合+条款影响计数：✅（问题队列）
- 全量条款/事实/原件下钻：✅（队列→详情→原件三栏贯通）
- 具体动作+可接受证据：✅（本节）
- 不用top-N隐藏：✅（全量渲染+测试钉扎）
- 1080P/2K/4K真实浏览器：✅（截图验证）
- 保存系统审核报告无需逐条勾选：属正式ReviewRun发布路径（方法采用门后）。
