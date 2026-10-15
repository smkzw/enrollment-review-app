"""Chinese source-linked explanation of a saved frequency calculation."""


def _resolution_notes(resolution, unit):
    notes = []
    if "period_results" in resolution:
        label = "每个期间均须满足" if resolution["quantifier"] == "every" else "至少一个期间满足"
        notes.append(f"按方案分别核对各计数期间：{label}。")
        excluded = resolution["domain"].get("excluded_partial_periods", ())
        if excluded:
            notes.append(f"按方案仅纳入完整周期，另有{len(excluded)}个首尾不足周期的期间未纳入，不将其当作满足或不满足。")
        for row in resolution["period_results"]:
            period, calculation = row["period"], row["calculation"]
            result = calculation["result"]
            status = {"true": "达到该频次条件", "false": "未达到该频次条件", "unknown": "尚不能判断"}[result["truth"]]
            notes.append(f"{period['start']}至{period['end']}：{status}。")
            notes.extend(_resolution_notes(calculation, result.get("observed_unit") or ""))
        if not resolution["domain"]["domain_complete"]:
            notes.append("尚未完成全部适用期间的核算，未将已核算期间当作完整范围。")
        return notes
    bounds = resolution.get("bounds")
    if bounds is not None:
        lower, upper = bounds["lower"], bounds["upper"]
        if lower == upper:
            notes.append(f"按本次资料可确认：{lower}{unit}。")
        elif upper is None:
            notes.append(f"按本次资料至少可确认{lower}{unit}，尚不能确定最多发生多少。")
        else:
            notes.append(f"按本次资料可确认的范围为{lower}至{upper}{unit}，不能确定精确数量。")
    else:
        notes.append("目前尚不能确定要求期间内的次数或天数，未将记录条数当作发生次数。")
    for source in resolution.get("statement_sources", ()):
        excerpt = source.get("count_excerpt")
        period = source.get("period_excerpt")
        if excerpt:
            label = {"individual_occurrence": "原文逐次记载", "individual_day": "原文发生日记载"}.get(source.get("kind"), "原文计数记载")
            notes.append(f"{label}：{excerpt}")
        if period:
            notes.append(f"原文统计期间：{period}")
    policies = {item.get("anchor_provenance", {}).get("source")
                for item in (*resolution.get("period_calculations", {}).values(), resolution.get("individual_calculation", {}), resolution.get("day_calculation", {}))}
    if "application_policy" in policies:
        notes.append("方案未指定回溯日期，本项按当前审核节点的日期计算；筛选与基线分别判断。")
    return notes


def frequency_review_presentation(evaluation, facts):
    notes = _resolution_notes(evaluation.resolution, evaluation.result.observed_unit or "")
    related = [{
        "fact_id": key, "locator_ids": list(facts[key].locator_ids),
        "reason": "频次核对所用原文，保留逐次与汇总记载，不重复相加或补造事件。",
    } for key in sorted(evaluation.evidence_fact_ids - set(evaluation.result.used_fact_ids))]
    return list(dict.fromkeys(notes)), related
