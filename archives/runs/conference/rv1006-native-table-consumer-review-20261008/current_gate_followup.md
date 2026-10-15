复核开始：先读当前受影响定义（补全处、身份与容忍比较器），再查两处设计取舍的代码落点。

补全已改为 sorted set（deconstructor:3700），两条 compiler 标记已撤（2007-2054），validator_version 已加 `native-row-source-normalization/v1`（2059）。现在验证身份哈希边界与新增测试、preserve_unresolved 分支的真实形态。

最后两处决定性确认：模板哈希的具体覆盖面，以及 preflight 的 prompt_template 实参与 preserve_unresolved 策略开关。

# 同会话复核输出（validator-only 取舍 vs 当前代码边界）

**结论**：与所读代码边界相符，未找到"必须让旧已完成含义失效"的具体反例。以下为静态复核；我未执行产品、测试、DB 或临床核实。

**必须修复（本轮差异内）**：无。前轮 sorted 缺陷已修：`protocol_control_deconstructor.py:3700` 改为 `sorted({...})`，满足 domain 草稿 sorted-unique（`protocol_controls.py:1420`）。新用例 `test_slice58c_control_deconstructor.py:12664-12680` 参数化 `cited_span=["span:01","span:row-mark"]`（含只列整行最后一个 span），验证原子/输入不变、幂等、domain 装配一致——上轮盲区闭合。

**残余（有证据）**：
1) 补全后指纹：`deconstructor.py:3703-3711` 的 `DUPLICATE_CANDIDATE` 用补全后内容，两个仅顶层 span 枚举不同的候选会判重（fail-closed、走修复路径）。旧保存记录不经过此路，不影响复用。
2) `_same_deep_components_with_current_gate`（`execution.py:2066-2080`）只比较非 validator 字段，容忍与具体版本串无关；其安全依赖 `_validated_deep_source` 的当前重验（`:3473-3478`）。既有反例测试在位：`test_protocol_control_execution.py:508`（compiler 变更仅特殊重验）、`:5655`（gate-only 无模型复用）、`:3625-3631`（`compiler_old` 拒复用）。本次放 validator_version 与该边界一致。

**无证据支持的疑虑**：
a) "新材料 hash 如实保存"未能证实到具体字段：所读路径（`execution.py:2004-2005、3642、3684`）只落模板级 hash；渲染材料 hash 落点未读到，不作否定断言。
b) `preserve_unresolved` 是 `execution_control.continue_after_final_failure` 的显式 opt-in（`execution.py:224-228、3112-3117`），代码不默认启用；我只验了分支条件，未验新作业配置默认值。
c) 原生列位置可能影响 reviewer 判断；提示已加"位置不证明覆盖"防线，无代码反例，属临床侧。
d) 提示指导行是否应计入 `SOURCE_TARGET_REVIEW_*` 版本，取决于这些行在旧记录时是否已存在；我未核对历史文本，故不作反例断言。

**对"必须失效"的挑战裁定**：无具体反例。整行闭包原本由 publication gate 强制（`protocol_control_gate.py:1942-1954`，本补丁未改）；补全只作用于新验证的 wire；旧 complete 结果已闭合并过原门，规范化对它们是 no-op（与 owner 18/18+1 证据一致，我未复现）。旧记录仅 validator_version 差异→容忍→当前门重验，自洽。若 e628d4f0 曾带旧标记运行，则身份不匹配将 fail-closed（`execution.py:3443-3455→3480-3485`），不会假复用，符合"真正 compiler/schema/source/route 变化拒绝复用"的保留反例。

**未执行声明**：无产品/模型/测试/DB/临床动作；未输出任何临床文本；不给正式采用结论。
