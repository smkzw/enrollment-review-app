继续 C03 第二审（末版差异核查）。先定位末版函数与 25 项族位置的当前行号。

末版两处已读：helper 的行成员对账（source_interpretation.py:2435-2457）与 validator 的逐字豁免/数字分支（candidate_alignment.py:546-553、610-626）。最后读取 `_source_fragment`/`_COMPARISON_WORDS`/`_NUMBER` 定义，用于校验比较词表与接地的实际判据。

## C03 末版差异核查（同会话第二审）

**核读结论。** 三处均已读：helper 新增与冻结行成员对账（source_interpretation.py:2435-2457）、validator 逐字豁免与数字分支（candidate_alignment.py:546-553、594-626）、25 项族（tests/v2/protocols/test_slice58c_control_deconstructor.py:6605-6867）。整行身份（unit_kind/行号 2381-2385）、成员数组长度防御（2404-2406、2436-2439）、缺成员→覆盖抛错（6745-6749）与「不拼接来源」（span/逐字对集合相等，2454-2455）与末版描述一致。

**四问。**
1. **跳过有源义务：不能。** 豁免仅在 native 证明成立且同一义务原子 `statement` 逐字等于整行时免除「单格摘录含整行」（546-548）；证明本身已要求非空成员 (span, 逐字文本) 集合等于该原子 (span, excerpts) 集合（2453-2455），缺 X/缺成员/混他列/改句/改数字均集合不等而拒绝（20 变体含 partial_row、hidden_duration、changed_action）。义务原子在场、每组覆盖、禁止/例外检查未豁免（540-562）。
2. **阈值方向/单位：有一条可复核必修。** 检测到比较词或 threshold 时仍走原 predicate 门（595-625，含 comparator/value/unit）；且 native 路径本身排除 threshold 功能（2372-2374）。但 `_COMPARISON_WORDS`（82-87）缺「多于/最多/最少」及全角 ＞/＜；此类行若被判为 action，在 native 证明下会命中豁免（612-613）绕过 predicate 门（如“完成XX（最多2次）”）。修法：补词表（最小改动）或把豁免数字收紧为行号类；不必新框架。
3. **脚注：** 列标记脚注仍拒绝（2392）；标签脚注编号（^7）不阻塞且数字可不作比较——测试如此断言（6802-6822）。脚注含义无任何机械消费点，属声明过的残余，不得把 fully_expressed 当脚注已核。
4. **资料限制：** 未被跳过——`_validate_evidence_policy_checks` 无条件执行（486），新增 required_source_types 断言拒绝（6784）；`evidence_policy_alignment_pairs` 已含 candidate_linked 状态（59-71），有明确政策的候选必须带证明。

**残余（不阻塞）。** ①源侧限制/脚注语义仍靠模型；②词表补齐后仍需抽验全角/中文比较式；③同行 ≥2 候选接线按裁定保留；④前审「校正回环判据域差」未在本次读取范围内复核，待确认；⑤自洽而错误的冻结行数据可整链通过；⑥数字豁免依赖 decision_functions 分类正确。

**边界。** 严格只读（6 次有界读取），未运行任何测试；25 项为合成家族，connected 1244 在末版物理行修改前通过（owner 自述），不覆盖末版，两者均不作临床验收；工程独审不代替医学批准。

**处理建议。** 只修第 2 条词表缺口，其余保持；回交注明 ②③④⑥ 为已知残余。
