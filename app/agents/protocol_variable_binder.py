"""One bounded semantic suggestion; reuse the product's direct endpoint transport."""
import json
import time

from app.config import DECONSTRUCT_BACKEND, DECONSTRUCT_MODEL, DECONSTRUCT_REASONING_EFFORT, DECONSTRUCT_MAX_TOKENS
from app.domain.contracts.page_review import PageReviewLane
from app.evidence.artifacts import ArtifactStore
from app.llm.json_container_recovery import strict_json_loads
from app.llm.predicate_binding_candidates import _strip_json_fences
from app.llm.page_review_harness import PageReaderRoute, direct_completion
from app.llm.provider_profiles import resolve_openai_connection
from app.services.protocol_variable_binding import VariableBindingProposal, binding_view, validated_variable_suggestions

PROMPT = """你只为已保存的方案条件建议对应的数据项目，不重写方案，不判断受试者。
逐项保留输入的 component_id、predicate_id，requirement_id 必须来自该子项的 requirements。
已有定义含义吻合时复用；不能仅因单位相同而合并不同检查、不同症状评分、不同判断。
不同量表、单项评分、测量对象必须各有独立稳定变量；不能全部绑定通用症状评分。
结合source_context.rules[official_code]的完整条款与source_context.components[component_id]的子项原文核对测量背景；同名同单位但量表、采集方式或回顾期间不同的项目不可混用。
子项原文与完整条款相同时不重复列出；仍按已给条件限定范围，不补造省略内容。
完整条款只帮助理解本项限定，不把其他子项、后续节点或例外擅自并入本条件。
缺少定义时在 variables 中提出完整的项目定义，中文名称保留原判断对象、项目和期间差别。
新 variable_id 为小写英文下划线；数值项目必须有标准单位、合理上下限（不是入排阈值）。
variables 只列新增定义，已有项目仅在 bindings 中引用，不重新声明或改写定义。
类别结果不得绑定数值项目；数值与相对参考上限倍数不同，不能无参考范围互换。
研究者判断按原条件保留，不凭 sIgE 数值替代研究者诊断；是否类用 boolean，药物暴露用 exposure。
不要补造单位换算，不添加阈值、疾病规则或病例答案。不能确定的条件不返回绑定，留给审定人。
仅输出符合 output_schema 的 JSON，不含解释文字；所有建议均要经程序检查与医学经理审定。"""


async def suggest_variables(draft, data_paths, *, completion=direct_completion):
    base, key = resolve_openai_connection(DECONSTRUCT_BACKEND,
        role_base_url_env="DECONSTRUCT_BASE_URL", role_api_key_env="DECONSTRUCT_API_KEY")
    route = PageReaderRoute(PageReviewLane.MAIN_A, DECONSTRUCT_BACKEND, base, key,
        DECONSTRUCT_MODEL, DECONSTRUCT_REASONING_EFFORT, DECONSTRUCT_MAX_TOKENS, 1)
    view = binding_view(draft)
    components, rule_sources, component_sources = {}, {}, {}
    for item in view["predicates"]:
        context = view["source_context"][item["component_id"]]
        rule_sources[item["official_code"]] = context["parent_source_text"]
        if context["component_source_text"] != context["parent_source_text"]:
            component_sources[item["component_id"]] = context["component_source_text"]
        component = components.setdefault(item["component_id"], {
            "component_id": item["component_id"], "official_code": item["official_code"],
            "requirements": [], "predicates": []})
        known = {requirement["requirement_id"] for requirement in component["requirements"]}
        component["requirements"].extend(requirement for requirement in item["requirements"]
                                         if requirement["requirement_id"] not in known)
        component["predicates"].append({"predicate_id": item["predicate_id"],
            "predicate": item["predicate"], "variable_id": item["variable_id"],
            "requirement_ids": [requirement["requirement_id"] for requirement in item["requirements"]]})
    # Shared source policies occur once per component, not once per atomic condition.
    payload = {"input": {"variables": view["variables"], "components": list(components.values()),
                         "source_context": {"rules": rule_sources, "components": component_sources}},
               "output_schema": VariableBindingProposal.model_json_schema()}
    messages = [{"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    artifacts = ArtifactStore(data_paths)
    receipts = []
    for attempt in range(2):
        request = {"messages": messages, "draft_id": draft.draft_id, "draft_revision": draft.draft_revision,
                   "protocol_version_id": draft.protocol_version_id,
                   "model": route.model, "provider": route.provider,
                   "effort": route.reasoning_effort, "max_tokens": route.max_tokens}
        request_ref = artifacts.put("raw_request", json.dumps(request, ensure_ascii=False).encode()).storage_ref
        started = time.monotonic()
        try:
            response = await completion(route, messages, route.max_tokens)
            raw = {"text": response.text, "finish_reason": response.finish_reason,
                   "usage": dict(response.usage), "response_model": response.response_model,
                   "response_id": response.response_id, "request_ref": request_ref,
                   "seconds": time.monotonic() - started, "output_lengths": response.output_lengths}
            response_ref = artifacts.put("raw_response", json.dumps(raw, ensure_ascii=False).encode()).storage_ref
            receipts.append({"request_ref": request_ref, "response_ref": response_ref,
                             "seconds": time.monotonic() - started, "model": response.response_model,
                             "usage": dict(response.usage), "finish_reason": response.finish_reason})
            if response.finish_reason != "stop":
                raise ValueError("模型输出尚未完整结束")
            proposal = VariableBindingProposal.model_validate(strict_json_loads(_strip_json_fences(response.text)))
            proposal, issues = validated_variable_suggestions(draft, proposal)
            return {"proposal": proposal.model_dump(mode="json"), "receipts": receipts,
                    "binding_issues": issues,
                    "system_issue": f"仍有 {len(issues)} 个条件的建议未通过核对，请在清单中选择。" if issues else None,
                    "unbound_count": len(view["predicates"]) - len({
                        (item.component_id, item.predicate_id) for item in proposal.bindings})}
        except Exception as exc:
            if not receipts or receipts[-1].get("request_ref") != request_ref:
                receipts.append({"request_ref": request_ref, "seconds": time.monotonic() - started,
                                 "error_type": type(exc).__name__})
            if attempt == 1:
                return {"proposal": None, "receipts": receipts,
                        "system_issue": "数据项目建议未通过核对，请直接在下拉清单中选择。"}
            # Same bounded role, no parent/protocol reread and no hidden retry layer.
            messages = [*messages, {"role": "user", "content": "上次建议未通过类型、单位或身份核对："
                                   + str(exc)[:1000] + "。请仅重交此建议 JSON；不改变原条件。"}]
