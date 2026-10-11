上一轮的结论要按主人的新决定重核。我只读更新后的差异和四份相关定义，核对校正见证、证明与消费者边界。没有发现新的阻断性产品缺陷。失败检查点在编译器、修复合同或门禁版本变化后，只复用重新校验过的来源；结构损坏的作者草稿仍会硬拒。原地重试的身份边界没有被放宽。

## Evidence

- `_validated_deep_partial_source` 用完整组件字典比较。`compiler_versions` 或 `validator_version` 任一变化都会进入来源证明分支，不再落到旧作者草稿。
- 该分支对 `partial_wire` 只做 `ProtocolControlAgentWire.model_validate`。结构损坏会抛出，并且不调用 `_validate_deep_batch_output`。证明成立后清空 wire、核对、覆盖账、候选对齐和 `session_id`。
- 执行端只有草稿仍带 `partial_wire` 时才恢复作者 wire。证明路径已把它置为 `None`，因此不会再过发布门禁。同一版本、身份未变的原地检查点仍会过发布门禁。
- 原地续跑仍要求 `component_identity` 与修复合同完全等于当前值。引擎变化后的失败任务继续硬拒；变化后的续跑走带预检的新任务。已完成批次仍是 `same_material_and_current_gate`，不在这次差异里。
- 生产者在成功的范围校正上写入 `workflow_phase`、`code`、`statement_id`、`source_refs`。重放要求校正序号为 `2`、`3` 这种精确整数，触发码、陈述编号和原文引用必须与现行错误一致；第一条校正缺少自身触发时可以回退到初答，第二条缺少触发不能复用。最终清单必须与保存的 `source_interpretation` 完全相同。
- 集成测试已经覆盖门禁版本变化，以及结构合法但现行发布门禁失败的 wire。两条校正的正例、缺触发、错触发和错序号只直接调用证明函数。

## Inference

生产者和重放使用同一次校验异常。第一条校正的陈述编号与初答触发一致，第二条使用下一次现行错误。辅助测试里的两条校正不经过检查点往返、预检或运行器。

`tests/v2/protocols/test_slice58c_control_deconstructor.py` 中 `test_source_scope_repair_targets_statement_not_shared_unit_label` 同时要求初答 `statement_id == 1`，以及校正触发顺序为 `[0, 1]`。按当前生产者，这两项不能同时成立。该文件不在这次三文件差异中，本次也没有执行它。它与重放逻辑没有对上，但不能据此证明恢复会被错误放行。

修复合同单独变化、组件未变且没有 wire 时，干净初答仍走旧的 `_unrepaired_source_seed_proof`。需要范围校正时才会落到新证明。两条路径都会清空作者结果。

## Recommendation

产品边界可以按主人的决定保留，不必放宽原地重试，也不必另做恢复框架。还缺一条真正连上的消费者测试：生产者生成的两次范围校正写入失败检查点，同时存在一份结构合法但发布门禁已过时的 wire，再由版本化新任务恢复，并断言运行器只收到来源、旧任务指纹不变。现有 `source_witness_old_gate` 没有校正尝试；两条校正测试也没有进入预检和运行器。

## Uncertainty

本次没有运行测试，也不把主人所述的 33 通过当作本角色的验收。证明字典经过计划工件往返后的相等性，只被单次初答集成测试覆盖到，两条校正的往返没有直接证据。
