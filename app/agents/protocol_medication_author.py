"""A bounded product request for selected medication sections, not a whole protocol."""
import json
import time

from app.config import DECONSTRUCT_BACKEND, DECONSTRUCT_MODEL, DECONSTRUCT_REASONING_EFFORT, DECONSTRUCT_MAX_TOKENS
from app.domain.contracts.page_review import PageReviewLane
from app.domain.publication import canonical_hash
from app.domain.variables.dictionary import load_drug_classes
from app.evidence.artifacts import ArtifactStore
from app.llm.json_container_recovery import strict_json_loads
from app.llm.predicate_binding_candidates import _strip_json_fences
from app.llm.page_review_harness import PageReaderRoute, direct_completion
from app.llm.provider_profiles import resolve_openai_connection
from app.protocols.medication_restrictions import (MedicationRestrictionProposal,
    build_scope_supplement, medication_input_hash, selected_scope_material)

PROMPT = """你为方案审定人整理已选章节中的禁用药物、合并用药和伴随治疗限制，不审核受试者。
只按本次指定研究期别提取；不同期别的不同规定不能混用，共同适用必须有原文依据。
每项保留原文药物/治疗名称drug_text、逐字来源source_quotes、审核阶段、相对时间窗或明确研究期间。
TimeConstraint使用原文命名锚点、数量、日/周/月/年及方向；不补默认筛选起点，不把日历月折算固定天数。
仅明确整个研究/治疗期间才用period；window与period不同时填，时段不清用unresolved_reason说明，不猜。
有例外必须逐字保留exception_excerpt，并把限定它的上位原文一并引用，不能删例外以便自动计算。
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


async def author_medications(*, view, selection, phase, official_codes, data_paths, completion=direct_completion):
    _, _, readable = selected_scope_material(view, selection)
    if not readable:
        supplement = build_scope_supplement(proposal=MedicationRestrictionProposal(), view=view,
            selection=selection, phase=phase, official_codes=official_codes)
        return {"supplement": supplement.model_dump(mode="json"), "receipts": [], "system_issue": None}
    route = medication_author_route()
    payload = {"phase": phase, "official_codes": sorted(official_codes), "drug_classes": load_drug_classes(),
        "sources": [row.model_dump(mode="json") for row in readable],
        "output_schema": MedicationRestrictionProposal.model_json_schema()}
    messages = [{"role": "system", "content": PROMPT}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    store, receipts = ArtifactStore(data_paths), []
    for attempt in range(2):
        request = {"messages": messages, "model": route.model, "provider": route.provider,
            "effort": route.reasoning_effort, "max_tokens": route.max_tokens,
            "input_sha256": medication_input_hash(phase, readable)}
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
            proposal = MedicationRestrictionProposal.model_validate(strict_json_loads(_strip_json_fences(response.text)))
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
            messages = [*messages, {"role": "user", "content": "上次JSON未通过核对：" + str(exc)[:1200]
                + "。只修正此提案，保留来源和真实未决，不扩大读取。"}]
