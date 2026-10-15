这次只核对失败草稿的预检：同版本才冻结旧失败，版本不同则走现有重核。我先读完整分支和对应测试，看旧失败会不会被当成当前事实。这次只核恢复因果：失败草稿是否仅在校验器版本相同时才冻结旧失败。我先读预检函数、下游消费者和 `gate_changed` 两支测试。这项限制成立。校验器版本不同时，旧失败不会被冻结成当前事实；同版本覆盖损坏仍会拒绝建任务；成功兄弟不会被这条分支改判或改写。

版本相同才进入冻结。`_preflight_deep_source` 对每个 `failed_final` 批次都先走 `_validated_deep_partial_source`。只有独立读取策略、没有 `source_seed_proof`、且保存的 `component_identity.validator_version` 与当前相同，才调用 `_preserved_source_review_proof`。证明成立才把该批次改成 `preserve_unresolved`。版本不同时决定保持 `resume_partial`，不附 `unresolved_review_proof`。

因此旧失败不会变成当前事实。`preserve_unresolved` 才会在执行时零调用、`adopted=False`，并把原错误码重新落到新步骤。版本不同进不了这条分支。执行端对 `resume_partial` 会重新装入草稿并调用当前 runner：未决条目被排除在可复用核对之外；跨次恢复还要求该条保存覆盖与当次 `source_statement_coverage` 全等，不等就进入待核对并重新询问。旧终态、旧原答和旧预算没有写回。

同版本损坏没有被挡住，也没有被收成医学未决。该调用没有 `try/except`。覆盖不一致仍由 `_preserved_negative_alignment_proof` 或 `_preserved_unresolved_review_proof` 抛出 `ValueError`。外层只把这个异常变成 409，整份新任务不建立，不会改成 `resume_partial`，也不会换成未决错误码。证明函数对范围、引用、线路等损坏仍返回 `None`，从而不冻结；这是原证明的拒绝方式，不是这次新增的吞掉异常。

成功兄弟不被这条限制作废。比较写在失败批次分支内。已完成批次仍走原来的完成路径；校验器只变时，组件相等判断本来就忽略 `validator_version`，再按当前门重核。版本不同而不再抛覆盖异常，反而不再因为一个失败批次阻止整份复用计划返回。同版本抛错仍会拒绝建立新任务，但不会改写已保存的兄弟检查点。

`gate_changed=True` 只证明计划层：读到的校验器被改成 `previous-validator` 时，冻结证明不被调用，决定是 `resume_partial`，旧作业指纹不变，然后返回。`gate_changed=False` 才跑续跑，并检查失败步骤零调用、兄弟步骤完成、旧指纹不变。

证据边界：测试未跑，90 批对照未读，临床资料未核。`gate_changed=True` 没有进入执行，所以“重新核对会发出当前读取”只来自上述代码路径，不是这次测试执行结果。表号空白、分隔符、期别共用正则和正文提示反例本次未再核。初轮和这次都是工程审阅，不是临床批准。
