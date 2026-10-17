"""A bounded product request for selected medication sections, not a whole protocol."""
import json
import time

from app.config import DECONSTRUCT_BACKEND, DECONSTRUCT_MODEL, DECONSTRUCT_REASONING_EFFORT, DECONSTRUCT_MAX_TOKENS
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.rules import MedicationRestriction
from app.domain.publication import canonical_hash
from app.domain.variables.dictionary import load_drug_classes
from app.evidence.artifacts import ArtifactStore
from app.llm.json_container_recovery import strict_json_loads
from app.llm.predicate_binding_candidates import _strip_json_fences
from app.llm.page_review_harness import PageReaderRoute, direct_completion
from app.llm.provider_profiles import resolve_openai_connection
from app.protocols.medication_restrictions import (MedicationProposalError, MedicationRestrictionProposal,
    build_scope_supplement, medication_input_hash, selected_scope_material)

PROMPT = """你为方案审定人整理已选章节中的禁用药物、合并用药和伴随治疗限制，不审核受试者。
只按本次指定研究期别提取；不同期别的不同规定不能混用，共同适用必须有原文依据。
每项保留原文药物/治疗名称drug_text、逐字来源source_quotes、审核阶段、相对时间窗或明确研究期间。
TimeConstraint使用原文命名锚点、数量、日/周/月/年及方向；不补默认筛选起点，不把日历月折算固定天数。
window_interpretation须区分prohibited_interval（窗口内禁止使用，时长放上限）与minimum_washout（至少停药的间隔，时长放下限）；不明时保留null并说明未决，不靠数字相同认作含义相同。
仅明确整个研究/治疗期间才用period；window与period不同时填，时段不清用unresolved_reason说明，不猜。
有例外必须逐字保留exception_excerpt，并把限定它的上位原文一并引用，不能删例外以便自动计算。
本系统只审核预筛、筛选、导入和基线的资格要求。仅研究药物治疗期间适用的补救治疗许可，不构成入排要求，也不豁免入组前洗脱；单独来源列other_phase并说明。若它同时解释所引限制的例外，保留原文并以exception_period=treatment_period标明仅后续治疗期；不能默认例外覆盖本条所有阶段。确实整个研究期间适用时才用study_period，未核清则null。
drug_class_id只能来自给定类别表，药物归属不确定用null，不把外用、鼻用、吸入用混成全身用药。
不要把允许用药、背景介绍、后期治疗要求改成筛选排除，不给每个标题造患者义务。
每个非空来源位置必须被某条限制引用，或在source_dispositions中明确标为标题、允许、其他期别、背景或真实未决。
同一位置可含多项独立限制；有用药限制的位置不得同时列为背景等处置；摘录不能跨位置拼接。
applies_to_rule仅在原文或给定明确关系支持时关联当前IN/EX，无依据为null，不造官方编号。
仅输出符合output_schema的JSON。来源齐备不代表医学含义已批准，所有条目还需审定。"""


def medication_author_route():
    base, key = resolve_openai_connection(DECONSTRUCT_BACKEND,
        role_base_url_env="DECONSTRUCT_BASE_URL", role_api_key_env="DECONSTRUCT_API_KEY")
    return PageReaderRoute(PageReviewLane.MAIN_A, DECONSTRUCT_BACKEND, base, key,
        DECONSTRUCT_MODEL, DECONSTRUCT_REASONING_EFFORT, DECONSTRUCT_MAX_TOKENS, 1)


def medication_reader_identity():
    route = medication_author_route()
    return canonical_hash({"provider": route.provider, "base_url": route.base_url, "model": route.model,
        "effort": route.reasoning_effort, "max_tokens": route.max_tokens, "prompt": PROMPT,
        "schema": MedicationRestrictionProposal.model_json_schema()})


def medication_messages(*, phase, official_codes, readable):
    payload = {"phase": phase, "official_codes": sorted(official_codes), "drug_classes": load_drug_classes(),
        "sources": [row.model_dump(mode="json") for row in readable],
        "output_schema": MedicationRestrictionProposal.model_json_schema()}
    return [{"role": "system", "content": PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def revalidate_medication_result(saved, *, view, selection, phase, official_codes, data_paths):
    """Recheck the original unconditioned proposal, never shop among retry answers."""
    receipts = saved.get("receipts", [])
    issue = "已保存的读取尚不能用于当前草稿；未重新调用模型，可按原文手工核对。"
    result = {"supplement": None, "receipts": receipts, "system_issue": issue}
    if not receipts or not receipts[0].get("response_ref"):
        return result
    store = ArtifactStore(data_paths)
    first = receipts[0]
    # Integrity failures propagate. A corrupt receipt is not a cache miss.
    request = json.loads(store.read(first["request_ref"]))
    response = json.loads(store.read(first["response_ref"]))
    _, _, readable = selected_scope_material(view, selection)
    route = medication_author_route()
    expected = medication_messages(phase=phase, official_codes=official_codes, readable=readable)
    if (request.get("messages") != expected
            or request.get("scope_input_sha256", request.get("input_sha256")) != medication_input_hash(phase, readable)
            or any(request.get(key) != value for key, value in {"provider": route.provider,
                "model": route.model, "effort": route.reasoning_effort, "max_tokens": route.max_tokens}.items())
            or (request.get("reader_identity") is not None and request["reader_identity"] != medication_reader_identity())
            or response.get("request_ref") != first["request_ref"] or response.get("finish_reason") != "stop"):
        return result
    try:
        proposal = MedicationRestrictionProposal.model_validate(strict_json_loads(_strip_json_fences(response["text"])))
        supplement = build_scope_supplement(proposal=proposal, view=view, selection=selection,
            phase=phase, official_codes=official_codes, receipts=[first])
    except (ValueError, KeyError) as exc:
        return {**result, "validation_issue": {"code": "stored_proposal_invalid",
            "item_index": exc.item_index if isinstance(exc, MedicationProposalError) else None}}
    # Legacy requests did not freeze the endpoint. Do not assert its identity retroactively.
    supplement.reader_identity = request.get("reader_identity")
    return {"supplement": supplement.model_dump(mode="json"), "receipts": receipts, "system_issue": None,
        "revalidation": {"basis": "original_initial_response", "request_ref": first["request_ref"],
            "response_ref": first["response_ref"], "new_model_calls": 0,
            "endpoint_identity_recorded": request.get("reader_identity") is not None}}


async def author_medications(*, view, selection, phase, official_codes, data_paths, completion=direct_completion):
    _, _, readable = selected_scope_material(view, selection)
    if not readable:
        supplement = build_scope_supplement(proposal=MedicationRestrictionProposal(), view=view,
            selection=selection, phase=phase, official_codes=official_codes)
        return {"supplement": supplement.model_dump(mode="json"), "receipts": [], "system_issue": None}
    route = medication_author_route()
    messages = medication_messages(phase=phase, official_codes=official_codes, readable=readable)
    store, receipts = ArtifactStore(data_paths), []
    proposal, target_index = None, None
    for attempt in range(2):
        request = {"messages": messages, "model": route.model, "provider": route.provider,
            "effort": route.reasoning_effort, "max_tokens": route.max_tokens,
            "reader_identity": medication_reader_identity(),
            "scope_input_sha256": medication_input_hash(phase, readable), "target_index": target_index,
            "request_sources_sha256": canonical_hash(json.loads(messages[1]["content"])["sources"])}
        request_ref = store.put("raw_request", json.dumps(request, ensure_ascii=False).encode()).storage_ref
        started = time.monotonic()
        try:
            response = await completion(route, messages, route.max_tokens)
            raw = {"text": response.text, "finish_reason": response.finish_reason,
                "usage": dict(response.usage), "response_model": response.response_model,
                "response_id": response.response_id, "request_ref": request_ref,
                "seconds": time.monotonic() - started, "output_lengths": response.output_lengths}
            response_ref = store.put("raw_response", json.dumps(raw, ensure_ascii=False).encode()).storage_ref
            receipts.append({key: raw[key] for key in ("usage", "finish_reason", "response_model", "response_id", "seconds")}
                | {"request_ref": request_ref, "response_ref": response_ref})
            if response.finish_reason != "stop":
                raise ValueError("用药限制读取尚未完整结束")
            value = strict_json_loads(_strip_json_fences(response.text))
            if target_index is None:
                proposal = MedicationRestrictionProposal.model_validate(value)
            else:
                replacement = MedicationRestriction.model_validate(value)
                original = proposal.medications[target_index]
                source_ids = {quote.source_span_id for quote in original.source_quotes}
                if {quote.source_span_id for quote in replacement.source_quotes} != source_ids:
                    raise ValueError("局部核对不能删除背景来源或换到另一段原文")
                source_text = {row.source_span_id: row.excerpt for row in readable}
                if any(quote.excerpt in source_text[quote.source_span_id] and quote not in replacement.source_quotes
                       for quote in original.source_quotes):
                    raise ValueError("局部核对不能删去原本逐字成立的摘录来绕过例外")
                if (any(original.drug_text in quote.excerpt for quote in original.source_quotes)
                        and replacement.drug_text != original.drug_text):
                    raise ValueError("局部核对不能替换已有原文支持的药物对象")
                if replacement.applies_to_rule not in {None, original.applies_to_rule}:
                    raise ValueError("局部核对不能新增另一条官方标准关联")
                proposal = proposal.model_copy(deep=True)
                proposal.medications[target_index] = replacement
            supplement = build_scope_supplement(proposal=proposal, view=view, selection=selection,
                phase=phase, official_codes=official_codes, receipts=receipts)
            supplement.reader_identity = medication_reader_identity()
            return {"supplement": supplement.model_dump(mode="json"), "receipts": receipts, "system_issue": None}
        except Exception as exc:
            if not receipts or receipts[-1]["request_ref"] != request_ref:
                receipts.append({"request_ref": request_ref, "seconds": time.monotonic() - started,
                                 "error_type": type(exc).__name__})
            if attempt == 1 or type(exc).__name__ in {"AuthenticationError", "PermissionDeniedError", "RateLimitError"}:
                return {"supplement": None, "receipts": receipts,
                    "system_issue": "用药限制尚未完成核对，原范围和已发布规则保留；请核对模型连接或本次读取问题。"}
            if isinstance(exc, MedicationProposalError) and proposal is not None:
                target_index = exc.item_index
                target = proposal.medications[target_index]
                source_ids = {quote.source_span_id for quote in target.source_quotes}
                local_sources = [row.model_dump(mode="json") for row in readable if row.source_span_id in source_ids]
                if len(local_sources) != len(source_ids):
                    return {"supplement": None, "receipts": receipts,
                        "system_issue": "本条建议引用了未知原文位置，未猜测对应关系；其余原答和范围保留。"}
                messages = [{"role": "system", "content": PROMPT + "\n本次只返回指定条目本身的JSON，不返回medications清单或其他条目；程序保留所有兄弟条目。"},
                    {"role": "user", "content": json.dumps({"phase": phase, "item_index": target_index,
                        "current_item": target.model_dump(mode="json"), "validation_issue": str(exc),
                        "sources": local_sources, "drug_classes": load_drug_classes(),
                        "output_schema": MedicationRestriction.model_json_schema()}, ensure_ascii=False)}]
            else:
                messages = [*messages, {"role": "user", "content": "上次JSON未通过核对：" + str(exc)[:1200]
                    + "。只修正此提案，保留来源和真实未决，不扩大读取。"}]
