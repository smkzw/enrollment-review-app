"""Repair-only projections and preservation checks, not clinical interpretation."""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json

from pydantic import ValidationError

from app.domain.contracts.agent_io import (
    ProtocolSemanticDeconstructionCandidate, SemanticRestrictedComponent, SemanticRuleComponent,
)
from app.domain.contracts.normalization import UnresolvedItem
from app.domain.contracts.source_computation import (
    SourceComputation, SourceQuote, input_selection_references, validate_computation_quotes,
)

SCHEMA_REPAIR_CONTRACT_VERSION = "protocol-schema-repair/v1"
SOURCE_FIELD_REPAIR_VERSION = "protocol-source-fields/v3"
PERIOD_SOURCE_REPAIR_VERSION = "protocol-period-source-fields/v1"


class SourceFieldRepairDeclined(ValueError):
    """The author explicitly could not supply the requested source references."""


def source_field_repair_schema(*, version: str = SOURCE_FIELD_REPAIR_VERSION) -> dict:
    if version not in {"protocol-source-fields/v2", SOURCE_FIELD_REPAIR_VERSION, PERIOD_SOURCE_REPAIR_VERSION}:
        raise ValueError("未知来源字段修复版本")
    field = "source_excerpts" if version == PERIOD_SOURCE_REPAIR_VERSION else "input_refs"
    item_schema = ({"type": "string", "minLength": 1}
                   if version == PERIOD_SOURCE_REPAIR_VERSION else SourceQuote.model_json_schema())
    return {
        "type": "object", "additionalProperties": False,
        "required": ["version", "precondition_sha256", "fields"],
        "properties": {
            "version": {"const": version},
            "precondition_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "fields": {"type": "array", "maxItems": 8,
                "items": {"type": "object", "additionalProperties": False,
                    "required": ["path", field], "properties": {
                        "path": {"type": "array", "minItems": 1, "items": {
                            "anyOf": [{"type": "string"}, {"type": "integer", "minimum": 0}]}},
                        field: {"type": "array", "minItems": 1, "items": item_schema},
                    }}},
        },
    }


def plan_period_source_repair(previous_text: str, *, source_input, rule_codes: list[str]) -> dict | None:
    """Admit only duplicate provenance fields; never select a new period or clause."""
    from app.agents.protocol_deconstructor import _batch_source_span_ids, _normalize_model_json

    try:
        previous = _unique_json(previous_text)
        rules = previous.get("proposed_rules")
        if not isinstance(rules, list) or [row["official_code"] for row in rules] != rule_codes:
            return None
        checked = copy.deepcopy(previous)
        targets = []

        def visit(value, path, materials):
            if isinstance(value, list):
                for index, item in enumerate(value):
                    visit(item, [*path, index], materials)
            elif isinstance(value, dict):
                period = value.get("prospective_period")
                if isinstance(period, dict) and period.get("kind") == "source_defined":
                    if set(period) != {"kind", "source_excerpts"}:
                        raise ValueError("期间来源字段不完整")
                    clauses = value.get("source_clauses") or [value.get("source_clause")]
                    quotes = period["source_excerpts"]
                    if quotes != clauses:
                        if (not isinstance(quotes, list) or not quotes or not clauses
                                or not all(isinstance(q, str) and q for q in [*clauses, *quotes])
                                or not all(any(clause in quote for quote in quotes) for clause in clauses)
                                or not all(any(quote in text for text in materials) for quote in quotes)):
                            raise ValueError("期间引用不是本父规则中完整有源的较宽引用")
                        targets.append({"path": [*path, "prospective_period", "source_excerpts"],
                                        "source_clauses": list(clauses), "previous_excerpts": list(quotes),
                                        "predicate": copy.deepcopy(value), "parent_sources": list(materials)})
                        # Validation probe only. No returned proposal or saved answer is changed here.
                        period["source_excerpts"] = list(clauses)
                for key, item in value.items():
                    if key != "prospective_period":
                        visit(item, [*path, key], materials)

        for index, rule in enumerate(checked["proposed_rules"]):
            ids = set(_batch_source_span_ids(source_input, [rule["official_code"]]))
            materials = [item.text for item in source_input.source_materials if item.source_span_id in ids]
            visit(rule, ["proposed_rules", index], materials)
        if not 1 <= len(targets) <= 8:
            return None
        ProtocolSemanticDeconstructionCandidate.model_validate(_normalize_model_json(checked))
        return {"version": PERIOD_SOURCE_REPAIR_VERSION,
                "precondition_sha256": hashlib.sha256(previous_text.encode()).hexdigest(), "targets": targets}
    except (ValueError, TypeError, KeyError):
        return None


def _unique_json(text: str) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("来源字段修复不能选择重复JSON字段")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("来源字段修复不能接受非JSON数值")

    value = json.loads(text, object_pairs_hook=unique, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("来源字段修复只接受一个完整对象")
    return value


def _input_reference_repairable(calculation: dict, clauses: list[str]) -> bool:
    """Diagnose reference containment only; never supply the author's new field."""
    refs = calculation.get("input_refs")
    if not isinstance(refs, list) or not refs:
        return False
    try:
        computation = SourceComputation.model_validate(calculation)
        try:
            validate_computation_quotes(computation, clauses)
        except ValueError:
            pass
        else:
            return False
        # Retain every original reference. Invented indices/quotes, count or
        # policy errors still fail; only explicitly authored dependencies help.
        dependencies = input_selection_references(computation)
        if computation.declared_input_count is not None:
            dependencies.append(computation.declared_input_count.source)
        checked = computation.model_copy(update={"input_refs": [*computation.input_refs, *dependencies]})
        validate_computation_quotes(checked, clauses)
    except (ValueError, TypeError):
        return False
    return True


def plan_source_field_repair(previous_text: str, *, candidate_id: str,
                             official_code: str, include_disconnected: bool = False) -> dict | None:
    """Recover absent references or disconnected, literal authored dependencies.

    Existing semantic parsing and source/scope gates still validate the assembled
    proposal. This plan neither supplies references nor declares meaning correct.
    """
    try:
        previous = _unique_json(previous_text)
    except ValueError:
        return None
    rules = previous.get("replacement_rules")
    if (previous.get("candidate_id") != candidate_id or not isinstance(rules, list)
            or len(rules) != 1 or not isinstance(rules[0], dict)
            or rules[0].get("official_code") != official_code):
        return None
    targets = []

    def visit(value, path):
        if isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, [*path, index])
        elif isinstance(value, dict):
            calculation = value.get("source_computation")
            if isinstance(calculation, dict):
                single = value.get("source_clause")
                clauses = value.get("source_clauses", [])
                if isinstance(single, str) and single.strip() and clauses == []:
                    clauses = [single]
                elif single is not None or not isinstance(clauses, list) or not clauses:
                    return
                if not all(isinstance(item, str) and item.strip() for item in clauses):
                    return
                if "input_refs" not in calculation or (include_disconnected and _input_reference_repairable(calculation, clauses)):
                    targets.append({"path": [*path, "source_computation", "input_refs"],
                                    "source_clauses": clauses, "calculation": calculation})
            for key, item in value.items():
                if key != "source_computation":
                    visit(item, [*path, key])

    visit(rules, ["replacement_rules"])
    if not 1 <= len(targets) <= 8:
        return None
    plan = {"version": SOURCE_FIELD_REPAIR_VERSION,
            "precondition_sha256": hashlib.sha256(previous_text.encode()).hexdigest(),
            "targets": targets}
    # Existing bounded-history admission must not truncate a source quote.
    return plan if len(json.dumps(plan, ensure_ascii=False)) <= 8000 else None


def assemble_declared_input_references(previous_text: str, *, candidate_id: str,
                                       official_code: str) -> tuple[str, dict | None]:
    """Append exact references already authored in this same computation.

    No text is selected from the protocol, no source index is inferred, and no
    missing field is filled. Original references, including order, stay intact.
    """
    plan = plan_source_field_repair(previous_text, candidate_id=candidate_id,
        official_code=official_code, include_disconnected=True)
    if plan is None:
        return previous_text, None
    assembled = _unique_json(previous_text)
    changes = []
    for target in plan["targets"]:
        calculation = target["calculation"]
        if "input_refs" not in calculation:
            continue
        computation = SourceComputation.model_validate(calculation)
        dependencies = input_selection_references(computation)
        if computation.declared_input_count is not None:
            dependencies.append(computation.declared_input_count.source)
        references = copy.deepcopy(calculation["input_refs"])
        for ref in dependencies:
            item = ref.model_dump(mode="json")
            if item not in references:
                references.append(item)
        checked = computation.model_copy(update={"input_refs": [SourceQuote.model_validate(ref) for ref in references]})
        validate_computation_quotes(checked, target["source_clauses"])
        owner = assembled
        for step in target["path"][:-1]:
            owner = owner[step]
        owner["input_refs"] = references
        changes.append({"path": target["path"], "original_refs": calculation["input_refs"],
                        "appended_refs": references[len(calculation["input_refs"]):]})
    if not changes:
        return previous_text, None
    text = json.dumps(assembled, ensure_ascii=False, sort_keys=True)
    return text, {"version": "protocol-source-reference-assembly/v1",
        "candidate_id": candidate_id, "official_code": official_code,
        "previous_output_sha256": plan["precondition_sha256"],
        "assembled_output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "changes": changes, "model_calls": 0, "adoption_checked": False}


def assemble_unresolved_observation_sources(previous_text: str, *, candidate_id: str,
                                            official_code: str) -> tuple[str, dict | None]:
    """Bind unfinished-policy fragments to one already-authored component quote.

    No protocol text is selected or concatenated, no known policy is changed,
    and no qualification follows from this source-list packaging operation.
    """
    try:
        previous = _unique_json(previous_text)
    except ValueError:
        return previous_text, None
    rules = previous.get("replacement_rules")
    if (previous.get("candidate_id") != candidate_id or not isinstance(rules, list)
            or len(rules) != 1 or not isinstance(rules[0], dict)
            or rules[0].get("official_code") != official_code):
        return previous_text, None
    components = rules[0].get("components")
    if not isinstance(components, list) or len(components) != 1:
        return previous_text, None
    component = components[0]
    if not isinstance(component, dict):
        return previous_text, None
    ids, quotes = component.get("source_span_ids"), component.get("source_excerpts")
    if (not isinstance(ids, list) or len(ids) != 1 or not isinstance(quotes, list)
            or not isinstance(ids[0], str) or not ids[0].strip()
            or len(quotes) != 1 or not isinstance(quotes[0], str) or not quotes[0].strip()):
        return previous_text, None
    assembled = copy.deepcopy(previous)
    changes = []

    def visit(value, path):
        if isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, [*path, index])
        elif isinstance(value, dict):
            policy = value.get("observation_policy")
            if isinstance(policy, dict) and policy.get("mode") == "unresolved" and policy.get("selection") is None:
                fragments = policy.get("source_excerpts")
                clauses = value.get("source_clauses", [])
                if isinstance(value.get("source_clause"), str) and not clauses:
                    clauses = [value["source_clause"]]
                if (policy.get("source_span_ids") == ids and isinstance(fragments, list)
                        and 2 <= len(fragments) <= 8
                        and all(isinstance(q, str) and q.strip() and q in quotes[0] for q in fragments)
                        and len(set(fragments)) == len(fragments)
                        and isinstance(clauses, list) and any(isinstance(q, str) and quotes[0] in q for q in clauses)):
                    policy["source_excerpts"] = list(quotes)
                    changes.append({"path": [*path, "observation_policy", "source_excerpts"],
                                    "original_refs": fragments, "authored_component_refs": quotes})
            for key, item in value.items():
                if key != "observation_policy":
                    visit(item, [*path, key])

    visit(assembled["replacement_rules"][0]["components"][0], ["replacement_rules", 0, "components", 0])
    if len(changes) != 1:
        return previous_text, None
    text = json.dumps(assembled, ensure_ascii=False, sort_keys=True)
    return text, {"version": "protocol-unresolved-source-pair-assembly/v1",
        "candidate_id": candidate_id, "official_code": official_code,
        "previous_output_sha256": hashlib.sha256(previous_text.encode()).hexdigest(),
        "assembled_output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "changes": changes, "model_calls": 0, "adoption_checked": False}


def source_field_repair_prompt(plan: dict) -> str:
    if plan["version"] == PERIOD_SOURCE_REPAIR_VERSION:
        return (
            "本次只核对并修正列出的prospective_period.source_excerpts。原答使用了较宽的父条引用，"
            "而本条件已有独立source_clauses。请核对后逐项返回完整source_clauses，文字及顺序不变。"
            "不得改主体、期间含义、命题、条件来源、数值、例外、兄弟项或其他字段；若这些也需要改变，"
            "尤其是较宽引文中未被本条件来源保留的文字仍限定共同期间、例外或适用人群时，"
            "必须返回fields=[]；不能因为文字包含关系或其他兄弟引用过就认定本条件已保留这些限定。"
            "返回fields=[]，不要用修来源字段来改含义。这里只修重复来源包装，不批准规则或入组。"
            "仅返回字段提案JSON，不重答整个规则。\n"
            + json.dumps({"frozen_plan": plan, "output_schema": source_field_repair_schema(version=plan["version"])},
                         ensure_ascii=False, sort_keys=True)
        )
    return (
        "上一提案的计算输入引用遗漏或未完整连接已声明依据。本次仅修复targets中列出的input_refs字段，"
        "不重写任何规则、算子、数值、日期、选择方式、窗口、例外或未决事项。"
        "每个path逐项原样返回；statement_index只指该目标source_clauses从零开始的位置，"
        "quote须为对应片段的逐字子串，并完整覆盖已声明输入范围及其次数来源。"
        "既有calculation.input_selection的source、window_refs及非空ordering_ref须分别被同一局部"
        "statement_index的某个input_refs.quote完整包含；declared_input_count.source也须如此。"
        "仅摘时间窗中的部分词、拆成若干不能完整包含原引用的短词均不够；"
        "其他既有引用不改；已有input_refs的每个引用须保留或被同位置的完整引用包含。"
        "不由宿主把这些字段自动当作input_refs。"
        "若不能有据填写，返回fields=[]表示修复失败，不猜来源；这不是研究者缺资料。"
        "仅输出下列合同JSON，不返回全规则。提案仍由原门禁检查，不表示可计算或采用。\n"
        + json.dumps({"frozen_plan": plan, "output_schema": source_field_repair_schema(version=plan["version"])},
                     ensure_ascii=False, sort_keys=True)
    )


def apply_source_field_repair(previous_text: str, proposal_text: str, *, plan: dict) -> tuple[str, dict]:
    """Repair exactly the admitted reference fields; all other bytes' meaning is frozen."""
    from jsonschema import validate, ValidationError

    if hashlib.sha256(previous_text.encode()).hexdigest() != plan["precondition_sha256"]:
        raise ValueError("来源字段修复的原答已变化")
    proposal = _unique_json(proposal_text)
    try:
        validate(proposal, source_field_repair_schema(version=plan["version"]))
    except ValidationError as exc:
        raise ValueError("来源字段修复未遵守只补字段合同") from exc
    if proposal["precondition_sha256"] != plan["precondition_sha256"]:
        raise ValueError("来源字段修复不能替换原答身份")
    if not proposal["fields"]:
        raise SourceFieldRepairDeclined("未能有据修复期间引用；未判断受试者资料是否缺失"
            if plan["version"] == PERIOD_SOURCE_REPAIR_VERSION else
            "未能有据补齐计算输入引用；未判断受试者资料是否缺失")
    expected = {tuple(target["path"]): target for target in plan["targets"]}
    period_repair = plan["version"] == PERIOD_SOURCE_REPAIR_VERSION
    field_name = "source_excerpts" if period_repair else "input_refs"
    fields = {tuple(field["path"]): field[field_name] for field in proposal["fields"]}
    if len(fields) != len(proposal["fields"]) or fields.keys() != expected.keys():
        raise ValueError("来源字段修复缺项、重复或超出原缺失范围")
    assembled = _unique_json(previous_text)
    for path, references in fields.items():
        target = expected[path]
        if period_repair:
            owner = assembled
            for step in path[:-2]:
                owner = owner[step]
            clauses = owner.get("source_clauses") or [owner.get("source_clause")]
            period = owner.get("prospective_period")
            if (path[-2:] != ("prospective_period", "source_excerpts")
                    or clauses != target["source_clauses"] or references != clauses
                    or not isinstance(period, dict)
                    or period != {"kind": "source_defined", "source_excerpts": target["previous_excerpts"]}):
                raise ValueError("期间来源修复超出原条件或改变原文范围")
            period["source_excerpts"] = copy.deepcopy(references)
            continue
        for reference in references:
            ref = SourceQuote.model_validate(reference)
            if ref.statement_index >= len(target["source_clauses"]) or ref.quote not in target["source_clauses"][ref.statement_index]:
                raise ValueError("来源字段修复引用了其他条件或改写原文")
        owner = assembled
        predicate_owner = assembled
        for step in path[:-2]:
            predicate_owner = predicate_owner[step]
        clauses = predicate_owner.get("source_clauses", [])
        if predicate_owner.get("source_clause") is not None and clauses == []:
            clauses = [predicate_owner["source_clause"]]
        if clauses != target["source_clauses"]:
            raise ValueError("来源字段修复的原文范围已变化")
        for step in path[:-1]:
            owner = owner[step]
        if not isinstance(owner, dict) or path[-1] != "input_refs":
            raise ValueError("来源字段修复不得替换其他字段")
        if owner != target["calculation"]:
            raise ValueError("来源字段修复的计算声明已变化")
        if path[-1] in owner:
            if (plan["version"] != SOURCE_FIELD_REPAIR_VERSION
                    or not _input_reference_repairable(owner, target["source_clauses"])):
                raise ValueError("来源字段修复不得替换已有效或不合法的字段")
            if any(not any(old["statement_index"] == new["statement_index"]
                           and old["quote"] in new["quote"] for new in references)
                   for old in owner[path[-1]]):
                raise ValueError("来源字段修复不得撤下已有输入依据")
        owner[path[-1]] = copy.deepcopy(references)
    text = json.dumps(assembled, ensure_ascii=False, sort_keys=True)
    proof = {"version": plan["version"],
        "previous_output_sha256": plan["precondition_sha256"],
        "field_output_sha256": hashlib.sha256(proposal_text.encode()).hexdigest(),
        "assembled_output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "added_paths": [] if period_repair else [target["path"] for target in plan["targets"] if "input_refs" not in target["calculation"]],
        "adoption_checked": False}
    if period_repair:
        proof["repaired_paths"] = [target["path"] for target in plan["targets"]]
    if plan["version"] == SOURCE_FIELD_REPAIR_VERSION:
        proof["repaired_paths"] = [target["path"] for target in plan["targets"] if "input_refs" in target["calculation"]]
    return text, proof


def recover_source_fields(*, previous_response, plan: dict, transport):
    """One same-model/session recovery; the caller owns the existing persisted budget."""
    from app.agents.protocol_deconstructor import (
        ProtocolAgentCallError, _compact_transport_history,
    )

    history = getattr(transport, "history", None)
    if callable(history):
        messages = history(previous_response.session_id)
        if not messages or messages[-1] != {
            "role": "assistant", "content": previous_response.original_text
        }:
            raise ProtocolAgentCallError(previous_response.session_id,
                "来源字段修复的原答与会话不一致", error_code="MODEL_IDENTITY_MISMATCH")
    prompt = source_field_repair_prompt(plan)
    store = getattr(transport, "_call_budget_store", None)
    save_input = getattr(store, "store_source_field_input", None)
    save_result = getattr(store, "store_source_field_result", None)
    save_response = getattr(store, "store_source_field_response", None)
    input_refs = {}
    response_refs = {}
    response = previous_response
    try:
        if callable(save_input) and callable(save_result):
            input_refs = save_input(raw_text=previous_response.original_text,
                                    previous_text=previous_response.text, plan=plan)
            _compact_transport_history(transport, previous_response.session_id,
                context=json.dumps(plan, ensure_ascii=False, sort_keys=True))
        response = transport.continue_session(session_id=previous_response.session_id,
            prompt=prompt, output_kind=("semantic_period_sources"
                if plan["version"] == PERIOD_SOURCE_REPAIR_VERSION else "semantic_source_fields"))
        if input_refs and callable(save_response):
            response_refs = save_response(response=response, requested_session_id=previous_response.session_id,
                                          plan=plan, input_refs=input_refs)
        if response.session_id != previous_response.session_id:
            raise ValueError("来源字段修复不得更换原会话")
        assembled, proof = apply_source_field_repair(previous_response.text, response.text, plan=plan)
        if input_refs:
            proof.update(save_result(previous_text=previous_response.text,
                proposal_text=response.text, raw_text=response.original_text,
                assembled_text=assembled, plan=plan, input_refs=input_refs))
        proof.update(response_refs)
        proof["previous_raw_output_sha256"] = hashlib.sha256(previous_response.original_text.encode()).hexdigest()
        return response.model_copy(update={"text": assembled, "raw_text": response.original_text,
            "call_metadata": {**response.call_metadata, "source_field_repair": proof}})
    except ProtocolAgentCallError as exc:
        raise ProtocolAgentCallError(exc.session_id, str(exc), error_code=exc.error_code,
            error_metadata={**exc.error_metadata, "source_field_input": input_refs,
                            "source_field_response": response_refs}) from exc
    except (ValueError, OSError, KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ProtocolAgentCallError(response.session_id, str(exc),
            error_code=("SOURCE_FIELD_REPAIR_PERSISTENCE_FAILED" if isinstance(exc, OSError)
                        else "SOURCE_FIELD_REPAIR_DECLINED" if isinstance(exc, SourceFieldRepairDeclined)
                        else "SOURCE_FIELD_REPAIR_INVALID"), error_metadata={
                **(response.call_metadata if response is not previous_response else {}),
                "source_field_input": input_refs,
                "source_field_response": response_refs,
                **({"field_repair_response_sha256": hashlib.sha256(response.original_text.encode()).hexdigest()}
                   if response is not previous_response else {}),
            }) from exc

_RESTRICTED_REPAIR_BOUNDARY = (
    "consumer_unavailable只允许当前来源核验可证明的三类结构：列举项括号内专属频次、"
    "开放列举的局部括号例外、括号内条件性适用人群。已明确且可独立表达的兄弟条件不得撤下。"
    "其他程序能力缺口不得借该标签通过；保持失败范围，不删除原文中的数量、期间、方向或例外。"
    "真实原文含义歧义才用interpretation_unresolved，结构错误不是研究者缺少记录。"
)


def project_repair_constraints(schema: dict) -> dict:
    """Expose existing cross-field restrictions only in the repair specification."""
    scope = schema["$defs"]["OccurrenceScope"]
    scope["allOf"] = [
        {"if": {"properties": {"kind": {"not": {"enum": kinds}}}, "required": ["kind"]},
         "then": {"properties": {field: {"type": "null"}}}}
        for field, kinds in (
            ("duration_basis", ["any_consecutive", "anchored_period"]),
            ("calendar_week_start", ["calendar_period"]),
            ("anchor_type", ["anchored_lookback", "anchored_period"]),
        )
    ] + [
        {"if": {"properties": {"quantifier": {"not": {"enum": ["any", "every"]}}},
                "required": ["quantifier"]},
         "then": {"properties": {"boundary_periods": {"type": "null"}}}},
    ]
    predicate = schema["$defs"]["AtomicPredicate"]["properties"]
    predicate["occurrence_window"]["description"] = (
        "仅表达带次或发生天数单位的数值计数，或minimum_count明示的最小次数。"
        "量、浓度、剂量、评分及其每期间平均或总量不能借用事件次数结构。"
        + _RESTRICTED_REPAIR_BOUNDARY
    )
    schema["$defs"]["SemanticRestrictedComponent"]["description"] = _RESTRICTED_REPAIR_BOUNDARY
    return schema


def _canonical(value) -> str:
    return json.dumps(value.model_dump(mode="json"), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"))


def verify_repair_preserves_valid_parts(
    previous_text: str, repaired: ProtocolSemanticDeconstructionCandidate,
    *, component_conversion: tuple[str, int] | None = None,
) -> dict:
    """Preserve all independently valid components/issues in a readable failed answer.

    Invalid parts still need source and semantic gates; this check cannot approve
    a replacement's clinical meaning or recover malformed/unidentifiable JSON.
    """
    previous = json.loads(previous_text)
    if not isinstance(previous, dict) or not isinstance(previous.get("proposed_rules"), list):
        raise ValueError("结构修复前的规则范围无法核实")
    for key in ("candidate_id", "created_by_agent_call_id"):
        if key in previous and previous[key] != getattr(repaired, key):
            raise ValueError("结构修复不得更换草稿身份")
    before_rules = previous["proposed_rules"]
    if not all(isinstance(row, dict) for row in before_rules):
        raise ValueError("结构修复前的父规则无法核实")
    if [row.get("official_code") for row in before_rules] != [
        row.official_code for row in repaired.proposed_rules
    ]:
        raise ValueError("结构修复不得更换父规则范围或顺序")
    preserved = 0
    for before, after in zip(before_rules, repaired.proposed_rules, strict=True):
        if "components" not in before:
            raise ValueError("结构修复前的要求清单无法核实")
        converted = None
        if component_conversion is not None and before["official_code"] == component_conversion[0]:
            converted = component_conversion[1]
            rows = before["components"]
            if (type(converted) is not int or not isinstance(rows, list)
                    or not 0 <= converted < len(rows)
                    or len(after.components) != len(rows) - 1
                    or len(after.restricted_components) != len(before.get("restricted_components", [])) + 1):
                raise ValueError("子项转为受限记录的范围无法核实")
            try:
                SemanticRuleComponent.model_validate(rows[converted])
            except ValidationError:
                pass
            else:
                raise ValueError("结构恢复不能撤下原本合法的子项")
        invalid_sources = Counter()
        replacements = Counter()
        original_count = 0
        for key, model in (("components", SemanticRuleComponent),
                           ("restricted_components", SemanticRestrictedComponent)):
            rows = before.get(key, [])
            if not isinstance(rows, list):
                raise ValueError("结构修复前的要求清单无法核实")
            original_count += len(rows)
            actual_rows = getattr(after, key)
            valid_positions = set()
            for index, row in enumerate(rows):
                try:
                    valid = model.model_validate(row)
                except ValidationError:
                    invalid_sources[_source_identity(row)] += 1
                    continue
                actual_index = index - 1 if key == "components" and converted is not None and index > converted else index
                if actual_index >= len(actual_rows) or _canonical(valid) != _canonical(actual_rows[actual_index]):
                    raise ValueError("结构修复改变、重排或删除了原本合法的兄弟要求")
                valid_positions.add(actual_index)
                preserved += 1
            for index, row in enumerate(actual_rows):
                if index not in valid_positions:
                    replacements[_source_identity(row.model_dump(mode="json"))] += 1
        if original_count != len(after.components) + len(after.restricted_components):
            raise ValueError("结构修复不得新增或删除要求；拆分须另行有源修订")
        if invalid_sources != replacements:
            raise ValueError("结构修复不得删去或更换待修要求的原文引用")
    for key in ("unresolved_items", "structural_warnings"):
        rows = previous.get(key, [])
        if not isinstance(rows, list):
            raise ValueError("结构修复前的未决清单无法核实")
        required = Counter()
        for row in rows:
            try:
                required[_canonical(UnresolvedItem.model_validate(row))] += 1
            except ValidationError:
                continue
        if required - Counter(_canonical(row) for row in getattr(repaired, key)):
            raise ValueError("结构修复删除或改写了原本合法的未决记录")
    return {"version": SCHEMA_REPAIR_CONTRACT_VERSION, "preserved_components": preserved,
            "previous_output_sha256": hashlib.sha256(previous_text.encode()).hexdigest(),
            "repaired_output_sha256": hashlib.sha256(repaired.model_dump_json().encode()).hexdigest()}


def _source_identity(row) -> str:
    if not isinstance(row, dict):
        raise ValueError("待修要求的原文引用无法核实")
    for key in ("source_span_ids", "source_excerpts"):
        if not isinstance(row.get(key), list) or not row[key] or not all(
            isinstance(item, str) and item.strip() for item in row[key]
        ):
            raise ValueError("待修要求的原文引用无法核实")
    return json.dumps([row["source_span_ids"], row["source_excerpts"]], ensure_ascii=False)


def recover_structural_batch(*, source_input, previous_response, transport, batch_id: str,
                             rule_codes: list[str]):
    """One explicit same-session recovery under the existing persistent budget.

    The owner supplies frozen source/history and decides whether to store the
    validated candidate. This does not retry a Job or approve a clinical rule.
    """
    from app.agents.protocol_deconstructor import (
        _batch_schema_repair_prompt, _batch_source_span_ids,
        _configure_transport_output_scope, _parse_semantic_candidate,
        _validate_semantic_batch, _uses_compact_wire_contract,
    )

    if _uses_compact_wire_contract(transport):
        raise ValueError("当前局部结构恢复只支持完整语义合同")
    if transport.logical_run_budget is None:
        raise ValueError("局部结构恢复缺少原运行预算")
    history = transport.history(previous_response.session_id)
    if history[-1] != {"role": "assistant", "content": previous_response.text}:
        raise ValueError("局部结构恢复的原答与会话不一致")
    before = json.loads(previous_response.text)
    if (not isinstance(before, dict) or not isinstance(before.get("proposed_rules"), list)
            or not all(isinstance(row, dict) for row in before["proposed_rules"])
            or [row.get("official_code") for row in before["proposed_rules"]] != rule_codes
            or not isinstance(before.get("candidate_id"), str)
            or not before["candidate_id"]
            or not isinstance(before.get("created_by_agent_call_id"), str)
            or not before["created_by_agent_call_id"]):
        raise ValueError("局部结构恢复的身份或父规则范围无法核实")
    try:
        _parse_semantic_candidate(previous_response.text)
    except ValueError as exc:
        if not isinstance(exc.__cause__, ValidationError):
            raise ValueError("当前失败不是可恢复的类型化结构错误") from exc
        problem = str(exc)
    else:
        raise ValueError("原答不存在类型化结构错误，不重复调用模型")
    _configure_transport_output_scope(transport, source_input, rule_codes)
    budget_before = transport.logical_call_budget.snapshot()
    if budget_before["requests_used"] < 1:
        raise ValueError("局部结构恢复不能新建空预算冒充历史")
    response = transport.continue_session(
        session_id=previous_response.session_id, output_kind="semantic_candidate",
        prompt=_batch_schema_repair_prompt(rule_codes, candidate_id=before["candidate_id"],
            agent_call_id=before["created_by_agent_call_id"], batch_id=batch_id,
            problem=problem, allowed_source_span_ids=_batch_source_span_ids(source_input, rule_codes)),
    )
    if response.session_id != previous_response.session_id:
        raise ValueError("局部结构恢复不得更换会话")
    candidate = _parse_semantic_candidate(response.text)
    _validate_semantic_batch(candidate, expected_codes=rule_codes,
        expected_candidate_id=before["candidate_id"],
        expected_agent_call_id=before["created_by_agent_call_id"], source_input=source_input)
    proof = verify_repair_preserves_valid_parts(previous_response.text, candidate)
    response.call_metadata["structural_preservation"] = proof
    response.call_metadata["scope_budget_before"] = budget_before
    response.call_metadata["scope_budget_after"] = transport.logical_call_budget.snapshot()
    return response, candidate


def _invalid_component_context(source_input, previous_text, official_code, component_index):
    from app.agents.protocol_deconstructor import _batch_source_span_ids

    before = json.loads(previous_text)
    rules = before.get("proposed_rules") if isinstance(before, dict) else None
    if (not isinstance(rules, list) or len(rules) != 1 or not isinstance(rules[0], dict)
            or rules[0].get("official_code") != official_code
            or not isinstance(rules[0].get("components"), list)
            or type(component_index) is not int
            or not 0 <= component_index < len(rules[0]["components"])
            or not all(isinstance(before.get(key), str) and before[key].strip()
                       for key in ("candidate_id", "created_by_agent_call_id"))):
        raise ValueError("子项核对的父规则范围无法核实")
    target = rules[0]["components"][component_index]
    for index, sibling in enumerate(rules[0]["components"]):
        if index != component_index:
            SemanticRuleComponent.model_validate(sibling)
    for sibling in rules[0].get("restricted_components", []):
        SemanticRestrictedComponent.model_validate(sibling)
    target_source = _source_identity(target)
    try:
        SemanticRuleComponent.model_validate(target)
    except ValidationError as exc:
        problems = exc.errors(include_url=False, include_input=False, include_context=False)
    else:
        raise ValueError("当前子项已可读取，不能借结构恢复改写含义")
    source_ids = _batch_source_span_ids(source_input, [official_code])
    materials = {item.source_span_id: item.text for item in source_input.source_materials}
    if (set(target["source_span_ids"]) - set(source_ids)
            or any(not any(quote in materials.get(ref, "") for ref in target["source_span_ids"])
                   for quote in target["source_excerpts"])):
        raise ValueError("待修子项的原文不属于冻结来源")
    return before, target, target_source, problems, source_ids


def decode_fenced_repair_proposal(text: str) -> tuple[str, dict]:
    """Explicit offline recovery only; never accept prose as clinical evidence."""
    lines = text.splitlines(keepends=True)
    markers = [index for index, line in enumerate(lines) if line.strip().startswith("```")]
    if (len(markers) != 2 or lines[markers[0]].strip().lower() != "```json"
            or lines[markers[1]].strip() != "```" or markers[1] <= markers[0] + 1):
        raise ValueError("不能唯一定位完整的JSON提案")
    outside = "".join(lines[:markers[0]] + lines[markers[1] + 1:])
    if any(token in outside for token in ("{", "}", "[", "]", "```")):
        raise ValueError("提案之外存在其他结构内容，不能自动选择")
    body = "".join(lines[markers[0] + 1:markers[1]]).strip()

    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("JSON提案包含重复字段")
            value[key] = item
        return value

    parsed = json.loads(body, object_pairs_hook=unique_object)
    if not isinstance(parsed, dict):
        raise ValueError("JSON提案顶层必须为对象")
    return body, {"version": "single-fenced-proposal/v1", "candidate_only": True,
        "raw_output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "extracted_output_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "discarded_commentary_sha256": hashlib.sha256(outside.encode()).hexdigest()}


def recover_invalid_component(*, source_input, previous_text: str, transport,
                              official_code: str, component_index: int):
    """Opt-in one-call proposal after exhausted recovery, never automatic adoption.

    Keep the exhausted ledger, the original run envelope and all valid siblings.
    A new identity binds the actual failed answer, prompt, source and route; using
    another output directory cannot grant another call.
    """
    from app.agents.protocol_deconstructor import (
        _batch_prompt_payload, _compact_repair_schema,
        _uses_compact_wire_contract,
        DNF_WIRE_MAX_ATOMS_PER_GROUP, DNF_WIRE_MAX_GROUPS,
        DNF_WIRE_MAX_REQUIREMENTS_PER_COMPONENT,
    )

    if _uses_compact_wire_contract(transport) or transport.logical_run_budget is None:
        raise ValueError("子项核对需完整语义合同及原运行预算")
    store = getattr(transport, "_call_budget_store", None)
    if not all(callable(getattr(store, name, None)) for name in ("load_call_budget", "store_call_budget")):
        raise ValueError("子项核对需绑定原持久预算存储")
    if transport.logical_call_budget is None:
        raise ValueError("子项核对缺少原读取预算")
    prior_budget = transport.logical_call_budget.snapshot()
    if (prior_budget["max_requests"] <= 1
            or prior_budget["requests_used"] != prior_budget["max_requests"]):
        raise ValueError("应先使用既有恢复预算，不另建子项核对")
    before, target, _, problems, source_ids = _invalid_component_context(
        source_input, previous_text, official_code, component_index)
    context = _batch_prompt_payload(source_input, [official_code], batch_number=1,
        batch_total=1, candidate_id=before["candidate_id"], related_procedures_only=True,
        compact_unrelated_procedures=True)
    schema = project_repair_constraints(json.loads(_compact_repair_schema(source_ids)))
    prompt = (
        "仅核对一个无法读取的方案子项。原文是权威，旧表达是待纠正提案。"
        "从原文区分事件计数、每期间数量、平均/总量、检查结果选择与定义；"
        "不能只删期间、阈值、单位、量词或例外，也不能将确定性计算包装成语义命题。"
        + _RESTRICTED_REPAIR_BOUNDARY
        + "在unresolved_dimensions逐项写明实际待核维度，不把已明确条件说成原文含义不明。"
        "返回既有ProtocolSemanticRuleRepair，只含目标父规则下一个正常或受限子项，"
        "不得同时返回两类，不得拆分或附带兄弟。candidate_id保持原值；"
        "source_span_ids和source_excerpts逐项原样保留。两个replacement_*事项数组为空，"
        "原有事项由宿主保留。其他子项不交你重写。提案仍需全包门禁，不代表采用。\n"
        + json.dumps({"target": target, "problems": problems, "frozen_context": context,
                      "output_schema": schema}, ensure_ascii=False, sort_keys=True)
    )
    identity = hashlib.sha256(json.dumps({
        "version": "invalid-component-recovery/v1", "source": source_input.model_dump(mode="json"),
        "previous": hashlib.sha256(previous_text.encode()).hexdigest(),
        "parent": official_code, "index": component_index, "prior_scope": prior_budget["logical_task_id"],
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "route": transport.semantic_cache_identity(output_kind="semantic_rule_repair"),
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    transport.configure_output_scope(official_codes=[official_code], allowed_source_span_ids=source_ids,
        component_limit=1, group_limit=DNF_WIRE_MAX_GROUPS, atom_limit=DNF_WIRE_MAX_ATOMS_PER_GROUP,
        requirement_limit=DNF_WIRE_MAX_REQUIREMENTS_PER_COMPONENT)
    transport.configure_logical_task(logical_task_id=identity, max_requests=1)
    response = transport.start(prompt=prompt, output_kind="semantic_rule_repair")
    candidate = assemble_invalid_component_proposal(source_input=source_input,
        previous_text=previous_text, response=response, official_code=official_code,
        component_index=component_index)
    response.call_metadata["prior_exhausted_budget"] = prior_budget
    response.call_metadata["scope_budget_after"] = transport.logical_call_budget.snapshot()
    response.call_metadata["component_recovery"]["identity"] = identity
    return response, candidate


def assemble_invalid_component_proposal(*, source_input, previous_text: str, response,
                                        official_code: str, component_index: int):
    """Validate and assemble an existing proposal without generation or adoption."""
    from app.agents.protocol_deconstructor import _parse_semantic_repair, _validate_semantic_batch

    before, target, target_source, problems, _ = _invalid_component_context(
        source_input, previous_text, official_code, component_index)
    repair = _parse_semantic_repair(response.text)
    if (repair.candidate_id != before["candidate_id"] or len(repair.replacement_rules) != 1
            or repair.replacement_rules[0].official_code != official_code
            or repair.replacement_unresolved_items or repair.replacement_structural_warnings):
        raise ValueError("子项核对越过冻结身份或事项范围")
    replacement = repair.replacement_rules[0]
    items = [*replacement.components, *replacement.restricted_components]
    if len(items) != 1 or _source_identity(items[0].model_dump(mode="json")) != target_source:
        raise ValueError("子项核对不能增删要求或更换原文引用")
    payload = copy.deepcopy(before)
    parent = payload["proposed_rules"][0]
    if replacement.components:
        parent["components"][component_index] = items[0].model_dump(mode="json")
    else:
        parent["components"].pop(component_index)
        parent.setdefault("restricted_components", []).append(items[0].model_dump(mode="json"))
    candidate = ProtocolSemanticDeconstructionCandidate.model_validate(payload)
    _validate_semantic_batch(candidate, expected_codes=[official_code],
        expected_candidate_id=before["candidate_id"],
        expected_agent_call_id=before["created_by_agent_call_id"], source_input=source_input)
    response.call_metadata["structural_preservation"] = verify_repair_preserves_valid_parts(
        previous_text, candidate,
        component_conversion=(official_code, component_index) if replacement.restricted_components else None)
    response.call_metadata["candidate_only"] = True
    if replacement.restricted_components:
        from app.agents.protocol_deconstructor import hydrate_semantic_preview
        from app.protocols.deconstruction_gate import _restricted_component_capability_proof

        preview, _ = hydrate_semantic_preview(source_input, candidate)
        rule = preview.proposed_rules[0]
        item = next(item for item in source_input.parent_rule_catalog.items
                    if item.official_code == official_code)
        materials = {item.source_span_id: item.text for item in source_input.source_materials}
        restricted = rule.restricted_components[-1]
        proof = (_restricted_component_capability_proof(restricted, rule, item, materials)
                 if restricted.limitation_kind == "consumer_unavailable" else None)
        response.call_metadata["restricted_capability"] = {
            "limitation_kind": restricted.limitation_kind, "source_proof_family": proof,
            "adoption_checked": False,
        }
    response.call_metadata["component_recovery"] = {
        "version": "invalid-component-recovery/v1",
        "official_code": official_code, "component_index": component_index,
        "previous_target_sha256": hashlib.sha256(json.dumps(target, ensure_ascii=False,
            sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "problems": problems,
    }
    return candidate
