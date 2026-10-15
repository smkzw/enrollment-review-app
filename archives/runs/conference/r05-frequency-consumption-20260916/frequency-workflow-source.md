# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本轮读取：`prepared_review_workflow.py`（429 行全读）、`review_runtime_ownership.py`、`prepared_review_intake/progress/publication.py`、`page_review_runtime.py` 注册段、`qualified_review_command.py`（245 行全读）、`frozen_review_publication.py`（238 行全读，v15）、`qualified_binding_selection.py` 频次段、`review.py` PredicateObservation、`control_review_outcome.py`、`review_history_service.py` 重建段、`review_control_repository.py`/`review_control_models.py`、`api/v2/review_history.py` 呈现段、`frequency_review_presentation.py`、前端三个频次相关文件。按指示不做算术面重复审阅；仅编译、无运行——本报告不构成方法批准或完成宣告。

---

### 1. 闭包核验（evidence，通过项）

- **父工作流 v7**：`READABLE_CONTRACTS` v1–v7 全保留（`prepared_review_workflow.py:27`）；期望子任务集按合同版本逐级累积（280-295），v7 新增双族 `*_frequency_evidence`；`verification` 步为两族候选各派频次任务（371-377）；`task_versions` 冻结全部七个执行器的 contract/prompt_version，advance/retry/发布三处重验（212, 418, 20）；子任务重复引用检查（299-300）；空频次组走零调用 summary 任务完成，依赖不会挂起。
- **所有权**：`OWNED_TYPES` 含 `frequency_evidence`；`prepared_review_job_scope` 仅把 owner 标记＋上下文绑定的任务纳入自动调度，旧隔离任务不受影响（`review_runtime_ownership.py:18-26`）；子任务归属核验（context/sha/routes 与父一致，126-145）；取消路径对无法确权记录“保留并停止其他已确认任务”（139-143）——不饿死兄弟任务。
- **发布入口**：`prepared_review_publication.py:68-73` 重放已完成的频次子任务回执，coverage 非空才映射；`qualified_review_command.py:93-96` 频次任务逐一归属 qualification 任务且不重复；`FrequencyEvidenceAdoption`（`qualified_binding_selection.py:42-44`）进入授权对象与 `auth_id`/gate 实体引用哈希（`qualified_review_command.py:207-208, 231`）；并发重复经内容比对幂等（28-42）。“有频次材料必须有频次授权”强制（`qualified_binding_selection.py:225`）。
- **报告与计算一致性**：`review.py:225-229` 在合同层强制保存的观察 truth/used_fact_ids 必须与冻结频次结果一致，且 **repeat×frequency 共存直接拒绝**；序列化 None 即 pop（250-256），`fixture/v1` 禁混频次（208-210）。呈现注释全部由存储的 `frequency_evaluation` 现场生成（`api/v2/review_history.py:450-452, 590-593`）——报告无法与计算矛盾。历史服务重建 atom 哈希、证据事实⊆冻结上下文、statement 定位闭合，重复条款结论拒绝展示（`review_history_service.py:383-421`）。
- **旧默认序列化**：`control_review_outcome.py` v5 版本门＋空 pop＋与 repeat 互斥（79-95）；`QualificationAdoptionAuthorization` v5＋pop（83-84）；`control_calculation_experiment.py` v12/four_layer 门＋空 pop（52, 63-64）。
- **辅助-复查条件频次排除属实**：输入采集含 repeat_trigger 身份（证据保留在 qualified material），但 `frequency_atom_calculation.py:58-60` 拒绝 repeat_scheme 所有者，四层组合仅覆盖 applicability/trigger/obligation/exception，且频次与 repeat 求值映射强制互斥（`control_calculation_experiment.py:221-222`）——辅助频次未被静默套用目标期解释，走旧 unknown 路径。与声明一致。
- **前端**：任务类型解码含 `frequency_evidence`（`preparedReviewHttp.ts:4`）、中文任务名（`PreparedReviewPanel.tsx:20`）、原因码中文映射覆盖后端全部 `frequency_*` 码（`reviewConditionNotes.ts:13-30`），含“未按零次处理”“不是受试者资料缺失”的准确表述。

---

### 2. 发现（按严重度；最小处置）

- **F1（本轮唯一实质缺陷）发布侧缺频次评测种类的再校验**：`frozen_review_publication.py:77-83` 汇入采用门复验的评测摘要集合含 base/judgment/proposition/observation 四类，**唯独漏了 `frequency_evidence.evaluation_sha256`**；91-96 的种类核验同样只覆盖三类。后果：经 `submit_qualified_review` 正常入口时无碍（`qualified_review_command.py:188-194` 已验 `frequency_statement_fidelity`），但绕过命令直接调 `publish_frozen_review` 传入手工授权对象时，频次评测摘要既不要求在采用门清单内、也不验种类——与三个兄弟族相比少了同一条纵深防御。**最小补救**：evaluations 集合并入 `item.frequency_evidence.evaluation_sha256`（77-83），并在 ~96 行后加 `auth.frequency_evidence is not None and manifests[...].evaluation_kind != "frequency_statement_fidelity"` 拒绝，与兄弟分支同款。
- **F2（呈现缺口）`occurrence_count_bounds_inconclusive` 无中文条目**：后端产出（`occurrence_count_bounds.py:70`）→ 保存观察 reason_codes → 前端映射缺失（`reviewConditionNotes.ts` 无此键），落到通用兜底文案“本条件尚有未核实内容…”。语义不失真（兜底仍准确）但丢失“已核实范围内无法判定”的特异解释。**最小补救**：补一行如“已核实的记载仍不能确定次数是否满足要求，需核对原件。”
- **F3（健壮性卫生）** `api/v2/review_history.py:450-452`：频次分支复用 `repeat_notes, repeat_unselected` 变量名直接覆盖。当前无实害（合同禁共存，`review.py:226`），但若未来合同放宽即变成静默吞掉复查说明。**最小补救**：改为独立变量或 `elif`，一行改动。
- **R1（观察，无需改动）** 被消费频次原子的 qualification gaps 清空（`frozen_review_publication.py:151`）语义正确——真值来自频次路径，语义配对疑问不再是该原子的依据；频次分辨率自身的 statement_sources/period_calculations 全程随 resolution 持久化，溯源不丢。
- **R2（观察）** `frequency_review_presentation.py:33` 的 related 集合在当前 resolve 语义下恒为空（used==source facts）；保留无害，留作未来逐次路径的呈现位。

---

### 3. 明确非声明

本轮所审为源码与编译级事实：频次生产→资格→计算→封存→出版的接线在两个族内闭合、无既有路径回归、未发现不健全正面判定；但**方法评测批准、父注册的实际运行验证、授权签发、辅助-复查条件频次、逐次-汇总对账、复杂窗口、完整报告呈现均未完成**（后四项与 runner 声明一致，F1 建议在授权签发前修复）。无运行、无浏览器、无临床验收；最终采信归 Codex/owner。会话保持可续。
