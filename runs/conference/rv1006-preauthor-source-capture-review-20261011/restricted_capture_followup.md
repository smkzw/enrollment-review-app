初审的三条入口和兄弟漏文要按新哈希复核。我只读现行补丁，核对受限批次是否与正常保存共用同一先决捕获门。定向复核只核对现行补丁是否封住三条入口和兄弟范围。先按给定哈希核对源码行，不改文件、不跑测试。三条采用入口和已见证的兄弟漏文，按现行源码已封住。没有更小的可采用反例。这是工程路径复核，不是医学金标，也不代表产品或临床完成。

审阅路线是 Grok / grok-build / grok-4.7 / high，与产品跨章 DeepSeek 不是同一模型。首报告里的同系列表述撤回。主路线 CLI 返回 0 只说明进程退出，报告当时不可接受，ZCode 失败后的回退由 runner 执行，不能把这次或上次的 CLI 0 当成审阅已成。基线仍是 `f25f7eeb667cae0570223b739dc349e278341876`。六份声明哈希与工作区字节一致。本轮只读源码，未写文件、未跑测试、未读临床材料。

## 事实与代码行

统一门在 `restricted_batch_from_review`。合法受限回执越过 903–913 的早退之后，只要 `source_interpretation` 存在且 `missing_sequence_source_units` 非空，就抛 `SOURCE_SEQUENCE_CAPTURE_INCOMPLETE`，随后才做摘录复核。

```914:927:app/services/protocol_control_restricted_source.py
    if result.source_interpretation is not None:
        gaps = missing_sequence_source_units(batch, result.source_interpretation)
        if gaps:
            unit_id = gaps[0]
            ...
            raise SourceInterpretationValidationError(
                "SOURCE_SEQUENCE_CAPTURE_INCOMPLETE",
                "保存的先决与动作来源未完整覆盖，须重新核对受影响来源",
```

谓词与正常保存相同：`after_eligibility_decision` 且 `eligibility_sequence_context is None`，再要求该单元全部陈述的字面覆盖。版本字面量是 `source-sequence-preauthor-capture/v2`，只拼进 `validator_version`（`protocol_control_source_interpretation.py` 363–375；`protocol_control_execution.py` 2166–2169）。`_same_deep_components_with_current_gate` 忽略仅验证器版本差异（2177–2190），所以旧回执仍会进入受限分支，再由新策略处理。`SourceInterpretationValidationError` 是 `ValueError` 子类（3398–3404）。

三条入口的现行结果：

- 新任务预检 `3663–3681`：版本不同且错误码属于未决排除、未决新增或 `SOURCE_SEQUENCE_CAPTURE_INCOMPLETE` 时，该批保持 3559 行的默认 `refresh_required`，原因写为 `current_source_review_requires_refresh`。同版本再抛。抛出发生在 `session.begin()` 内、`create_job_in_session`（622）之前，外层包成 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`「未建立新任务」（576–587）。
- `_validated_deep_source` `4113–4138`：同一异常进入外层 `ValueError`，成为新任务上的 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`。函数只读来源检查点。它只在执行期决策已是 `reusable` 时被调用（4772–4778）。
- `_replay_checkpoint` `1296–1325`：异常变成 `PROTOCOL_CONTROL_CHECKPOINT_INVALID`，不返回旧成功检查点。深审重入走 1156 行的回放，不走重新执行。

兄弟范围在失败恢复的既有见证条件内合并。`3112–3120` 把整批 `missing_sequence_source_units` 并入原逐项缺口；`3121–3142` 仅在 `witnessed.state == "reused"` 且 `completion_witnessed` 时返回补读种子，并清空 `partial_wire`、`source_target_review`、覆盖和装配。种子状态是 `absent`，`review` 默认为空（2260–2262）。执行器把 `source_unit_completion_ids` 交给 runner（4904–4905）。作者前补读先处理这批编号（deconstructor 8031–8034）；证明未恢复时，8495–8504 仍会按全批缺口再算一次。

其余复用点也先经过该函数：保留未决执行 4738–4746、当场采用 4916–4924、定义登记重核 4507–4518、时间范围证明 3327、深审结果装配 5554–5567。`app/` 里读取 `restricted_batch` 后用于采用的路径都调用了它。

解构器哈希与上次已核字节相同，本修订没有改它。额度、来源身份和作者身份不在这次读取的门、预检和恢复差异里。

合同测试已写在源码中，本轮未执行。`test_restricted_source_sequence_capture_uses_the_same_gate_as_normal_results`（1032–1058）直接调用真实函数：有尾文且未捕获时期望 `SOURCE_SEQUENCE_CAPTURE_INCOMPLETE`，完整捕获时期望不抛。`test_pending_exclusion_invalidates_only_an_older_restricted_proof`（7586–7637）把旧门与同门分成两支：旧门且错误码不是 `SOURCE_SCOPE_INVALID` 时只把 `deep_0001` 标成 `refresh_required`；同门或范围损坏时整次建任务抛 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`，且不增加模型调用。

## 关闭

- 预检采用：有先决缺口的旧受限完成证明不再得到 `same_restricted_source_and_current_gate`。版本不同只刷新该批；同版本硬拒，且拒在新任务写入之前。
- `_validated_deep_source` 采用：缺口不再返回可复用检查点。
- 回放采用：缺口不再交回旧成功检查点。
- 保留未决、当场采用、定义重核、时间证明和深审结果装配：缺口不再形成可消费受限批。
- 已见证兄弟：原未决或时间范围恢复一旦满足既有见证并处于 `reused`，种子编号包含该兄弟，并撤掉会让作者前补读被跳过的核对证明。

903–913 的早退仍直接返回 `None`，不抛新门。调用方随后以「不一致」或硬拒结束，不采用。`source_interpretation is None` 时新门不运行；没有解释对象也就没有可证明的先后缺口。

## 未关闭

这三条入口和已见证兄弟范围没有未关闭的采用路径，因此没有可核反例，也没有要求再补一处。

同作业回放和 `_deep_results` 的失败形态是硬拒，不是新任务预检那种 `refresh_required`。这不构成静默采用。已完成步骤不在可启动状态内（`states.py` 71–74，`jobstore.py` 569–572），本修订也不要求重开全部已完成批次。

## 最高风险

最高残留不是漏文被再次采用。它是：崩溃恢复把「仍为 running、且已有非诊断检查点」的步骤直接标成 `completed`，不调用执行器（`jobstore.py` 1470–1498；`recovery.py` 1–7）。旧终态因此不会被自动改写，新门也不会在这次恢复时重算。后续新任务预检或深审结果装配仍会挡住采用。若当时已有一份被旧代码冻成 `reusable` 的计划，现行 `_validated_deep_source` 会在执行期硬拒该新任务步骤。

## 建议

按代码路径，这次最小修订可以收下：统一门、旧门只刷新、同版本硬拒、已见证兄弟进入同一补读种子。摘录扩窗、连接标点、补读额度历史计数这三项没有被这次修订改成新的绕过，继续延后。不要把摘录扩全当成语义批准。完整捕获测试旁的注释也是这个边界。

所有者另行跑集中测试和实际完整预检。本报告不宣布这些测试已通过，也不宣布产品或临床完成。

## 证据不足

- 两份新测试未在本会话执行。预检测试用猴补丁抛的是 `SourceTargetReviewValidationError`，不是生产路径上的 `SourceInterpretationValidationError`；除元组同时包含两者，这是读代码得出的接线，不是一次真实运行。
- 正向合同测试只断言完整捕获不抛，没有断言返回了受限批，也没有调用预检、回放或 `_validated_deep_source`。
- 预检异常会回滚 `_prepare_source_in_session`，这是根据 `session.begin()` 和异常位于 `create_job_in_session` 之前作出的推断，没有观察事务。
- 没有清点是否已经存在「旧代码写成 reusable、尚未执行」的在途计划。代码上该计划会失败关闭，不是被采用。
- `completion_witnessed` 不成立，或见证状态不是 `reused` 时，3112 的并集不发种子。采用仍会被统一门挡住。这不在上次已见证兄弟漏文的反例里，本轮没有把它提升为缺陷。
- 额度、来源身份和作者身份没有在本轮逐行重审；依据是解构器哈希未变，以及本次读取的门、版本和恢复差异没有改这些字段。
