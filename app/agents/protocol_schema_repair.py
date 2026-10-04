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

SCHEMA_REPAIR_CONTRACT_VERSION = "protocol-schema-repair/v1"

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
