"""Present saved repeat calculations; never recalculate clinical decisions."""
from app.domain.contracts.evaluation_result import RepeatAtomEvaluation, FrequencyAtomEvaluation
from app.projections.frequency_review_presentation import frequency_review_presentation


def repeat_review_presentation(evaluation: RepeatAtomEvaluation, facts):
    resolution = evaluation.resolution
    initial = set(resolution["initial_group_ids"])
    selected = set(evaluation.result.used_fact_ids)
    checks = {row["repeat_group_id"]: row for row in resolution["repeat_checks"]}
    notes = ["以下仅依据本次已提供并核对的资料；已知缺失另列，不代表未记录的情况未曾发生。"]
    count_scope = resolution.get("count_scope")
    chain_counts = (count_scope or {}).get("count_by_initial", {})
    chain_material = (count_scope or {}).get("acquisition_chains", {})
    chain_roots = {repeat: chain["initial_group_id"] for chain in chain_material.get("chains", ())
                   for repeat in chain["repeat_group_ids"]}
    initial_numbers = {row["group_id"]: number for number, row in enumerate(
        (row for row in resolution["acquisition_results"] if row["group_id"] in initial), start=1)}
    multi = resolution.get("multi_initial_selection")
    if multi is not None and multi["operation"] is not None:
        requirement = "每组均出现原文所述情况" if multi["operation"] == "all" else "至少一组出现原文所述情况"
        notes.append(f"按方案先在每组初查及其复查中采用结果，再核对是否{requirement}；不同组不混合计算数值。")
    chain_repeat_numbers = {}
    memberships = {}
    if count_scope is not None and count_scope["kind"] == "per_current_episode":
        memberships = count_scope["acquisition_episode_memberships"]
        count = len(count_scope["counted_repeat_group_ids"])
        notes.append(f"按本次审核节点计数，已核实属于本节点的复查共{count}次。" + (
            "本次已提供记录的节点归属均已核对。" if count_scope["complete"] else
            "仍有记录或归属未核清，该数量不能证明未超过方案上限。"))
    absence = resolution.get("absence_trigger")
    if absence is not None:
        state = {"false": "已核实未触发", "true": "已触发，但本次未见复查结果",
                 "unknown": "尚未核清是否触发"}[absence["truth"]]
        notes.append(f"方案规定的复查触发条件：{state}。")
    ordering = resolution.get("observation_ordering")
    if ordering is not None:
        name = "最近一次" if ordering["criterion"] == "latest" else "最早一次"
        agreement = ordering["agrees_with_repeat_selection"]
        notes.append(f"方案要求采用{name}检查；" + (
            "按日期与复查规则选出的检查一致。" if agreement is True else
            "按日期与复查规则选出的检查不同，尚未采用。" if agreement is False else
            "检查先后与复查规则的合并采用尚未核实。"))
    unselected = []
    repeat_number = 0
    for row in resolution["acquisition_results"]:
        group_id = row["group_id"]
        if group_id in initial:
            label = f"初查组 {initial_numbers[group_id]}" if len(initial) > 1 else "初查记录"
        else:
            repeat_number += 1
            root = chain_roots.get(group_id)
            if len(initial) > 1 and root in initial_numbers:
                chain_repeat_numbers[root] = chain_repeat_numbers.get(root, 0) + 1
                label = f"初查组 {initial_numbers[root]}的复查记录 {chain_repeat_numbers[root]}"
            else:
                label = (f"复查记录 {repeat_number}" if group_id in checks
                         else f"检查次序待核实的记录 {repeat_number}")
        adopted = bool(row["fact_ids"]) and set(row["fact_ids"]) <= selected
        adoption = "本次采用" if adopted else "本次未采用，原件保留"
        status = checks.get(group_id, {}).get("status")
        prerequisite = {
            "requirements_met": "已核实满足复查采用条件",
            "does_not_meet_requirements": "未满足复查采用条件",
            "unverified": "复查采用条件尚未核实",
        }.get(status, "")
        membership = {"current_episode": "原文已核实属于本次审核节点",
                      "other_episode": "原文已核实属于其他节点，不计入本节点复查次数",
                      "unresolved": "所属审核节点尚未核清"}.get(memberships.get(group_id), "")
        descriptions = []
        for fact_id in row["fact_ids"]:
            fact = facts[fact_id]
            value = ("未列明确结果" if fact.value is None else
                     "是" if fact.value is True else "否" if fact.value is False else str(fact.value))
            unit = f" {fact.unit}" if fact.unit else ""
            date = fact.date_range.source_text if fact.date_range is not None else None
            if not date and fact.date_range is not None:
                bounds = fact.date_range
                date = f"{bounds.lower_bound or '起始日期未明'} 至 {bounds.upper_bound or '结束日期未明'}"
            description = f"{date or '日期未列明'}：{value}{unit}"
            if fact.polarity.value != "affirmed":
                description += "（原文否认）" if fact.polarity.value == "negated" else "（原文表述尚未核清）"
            descriptions.append(description)
            if fact_id not in selected:
                unselected.append({"fact_id": fact_id, "locator_ids": list(fact.locator_ids),
                                   "reason": f"{label}；{description}；{prerequisite or adoption}。"
                                   + (f"{membership}。" if membership else "")})
        notes.append(f"{label}：{'；'.join(dict.fromkeys(descriptions))}。{adoption}。"
                     + (f"{prerequisite}。" if prerequisite else "")
                     + (f"{membership}。" if membership else ""))
        if group_id in chain_counts:
            counted = chain_counts[group_id]
            state = {"true": "未超过方案上限", "false": "已超过方案上限",
                     "unknown": "尚不能确认是否超过方案上限"}[counted["result"]["truth"]]
            notes.append(f"{label}已核实对应复查{len(counted['repeat_group_ids'])}次，{state}。"
                         + ("仍有本次资料未核清，不能将未见记录视为未复查。" if not counted["scope_complete"] else ""))
        for key, check in checks.get(group_id, {}).get("checks", {}).items():
            name = {"trigger": "是否满足复查触发条件", "permission": "是否满足复查许可条件",
                    "count": "复查次数是否符合要求", "time": "复查时间是否符合要求",
                    "written_permission": "研究者书面意见内容"}[key]
            state = {"true": "已确认", "false": "不满足", "unknown": "尚未核实"}[check["truth"]]
            if key == "written_permission":
                state = "原文内容已核实，是否同意见许可条件" if check["truth"] == "true" else "原文内容尚未核实"
            notes.append(f"{label} · {name}：{state}。")
        for frequency in resolution.get("condition_frequency_evaluations", ()):
            if frequency["repeat_group_id"] == group_id:
                notes.append(f"{label}涉及的次数或天数条件：")
                for value in frequency["evaluations"].values():
                    explanation, _ = frequency_review_presentation(FrequencyAtomEvaluation.model_validate(value), facts)
                    notes.extend(explanation)
    for fact_id in sorted(evaluation.evidence_fact_ids - set(evaluation.source_fact_ids)):
        fact = facts[fact_id]
        unselected.append({"fact_id": fact_id, "locator_ids": list(fact.locator_ids),
                           "reason": "复查条件的核对依据，不作为检查结果值采用。"})
    for chain in resolution.get("multi_initial_results", ()):
        label = f"初查组 {initial_numbers[chain['initial_group_id']]}"
        state = {"true": "原文所述条件成立", "false": "原文所述条件不成立", "unknown": "原文所述条件尚无法判定"}[chain["result"]["truth"]]
        notes.append(f"{label}：{state}。")
        numeric = chain["numeric_result"]
        if numeric is not None and numeric["exact_value"] is not None:
            exact = numeric["exact_value"]
            value = exact["numerator"] if exact["denominator"] == "1" else f"{exact['numerator']} ÷ {exact['denominator']}"
            notes.append(f"{label}按方案计算的结果：{value}{(' ' + numeric['unit']) if numeric['unit'] else ''}；原始记录保留，未生成新的检查记录。")
    for chain in (multi or {}).get("chains", ()):
        absence = chain["absence_trigger"]
        if absence is not None:
            state = {"false": "已核实未触发", "true": "已触发，但本次未见对应复查", "unknown": "尚未核清是否触发"}[absence["truth"]]
            notes.append(f"初查组 {initial_numbers[chain['initial_group_id']]}的复查条件：{state}。")
    numeric = evaluation.numeric_result
    if numeric is not None and numeric["exact_value"] is not None:
        exact = numeric["exact_value"]
        value = (exact["numerator"] if exact["denominator"] == "1" else
                 f"{exact['numerator']} ÷ {exact['denominator']}")
        operation = resolution["policy_selection"]["combination"]
        name = {"sum": "合计", "mean": "平均值", "minimum": "最小值", "maximum": "最大值"}[operation]
        notes.append(f"按方案计算的{name}：{value}{(' ' + numeric['unit']) if numeric['unit'] else ''}。"
                     "这是计算结果，不是新增的原始检查记录；比较阈值时未作四舍五入。")
    return notes, unselected
