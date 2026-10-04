"""Replayable source/proposal checks; a relationship label is not a proof."""
from __future__ import annotations

import json
import hashlib
from collections.abc import Callable, Sequence

from app.domain.contracts.protocol_scope_review import OfficialScopeReading
from app.domain.publication import canonical_hash
from app.domain.contracts.rules import iter_atomic_predicates
from app.domain.contracts.enums import ReviewStage
from app.protocols.source_time_fragments import frozen_review_stage_aliases

SCOPE_REVIEW_VERSION = "official-source-scope-review/v3"


class OfficialScopeReviewError(ValueError):
    def __init__(self, code: str):
        self.code = code
        self.error_code = code
        super().__init__(code)


class OfficialScopeUnresolvedError(OfficialScopeReviewError):
    def __init__(self, dimensions: Sequence[str]):
        self.dimensions = tuple(dimensions)
        super().__init__("SOURCE_SCOPE_REVIEW_UNRESOLVED")


class OfficialScopeRejectedError(OfficialScopeReviewError):
    """One source assignment failed, without invalidating verified siblings."""

    def __init__(self, rejection_code: str):
        self.rejection_code = rejection_code
        super().__init__("SOURCE_SCOPE_REVIEW_REJECTED")


def scope_review_basis(source, draft, rule, headings: Sequence, *, heading_stages: Sequence[str]) -> dict:
    parents = [item for item in source.parent_rule_catalog.items
               if item.official_code == rule.official_code]
    if len(parents) != 1:
        raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_SOURCE_INVALID")
    parent = parents[0]
    materials = {item.source_span_id: item for item in source.source_materials}
    if len(materials) != len(source.source_materials):
        raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_SOURCE_INVALID")
    try:
        frozen = [materials[ref] for ref in parent.source_span_ids]
    except KeyError as exc:
        raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_SOURCE_INVALID") from exc
    frozen.sort(key=lambda item: item.block_order)
    bindings = {item.proposed_component.rule_component_id: item
                for item in draft.component_drafts}
    if len(bindings) != len(draft.component_drafts):
        raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_SOURCE_INVALID")
    children = []
    for component in rule.components:
        binding = bindings.get(component.rule_component_id)
        if (binding is None or binding.parent_official_code != rule.official_code
                or binding.proposed_component != component
                or not set(binding.source_refs) <= set(parent.source_span_ids)):
            raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_SOURCE_INVALID")
        children.append({
            "component_id": component.rule_component_id,
            "source_refs": list(binding.source_refs),
            "source_excerpts": list(binding.source_excerpts),
            "predicates": [{"predicate_id": predicate.predicate_id, "source_clauses": predicate.exact_source_clauses}
                           for root in [component.expression, *([component.exception_expression] if component.exception_expression is not None else []),
                                        *[trigger.expression for trigger in component.repeat_trigger_conditions]]
                           for predicate in iter_atomic_predicates(root)],
            "component": component.model_dump(mode="json", exclude={"source_scope_review_ref"}),
        })
    return {
        "version": SCOPE_REVIEW_VERSION,
        "project_id": source.project_id,
        "protocol_version_id": source.protocol_version_id,
        "source_sha256": source.protocol_file_sha256,
        "snapshot_id": source.extraction_snapshot_id,
        "catalog_sha256": source.parent_rule_catalog.catalog_sha256,
        "phase": source.selected_phase.value,
        "official_code": rule.official_code,
        "materials": [item.model_dump(mode="json") for item in frozen],
        "headings": [{"source_span_id": item.source_span_id, "excerpt": item.excerpt}
                     for item in headings],
        "heading_stages": sorted(set(heading_stages)),
        "procedure_catalog_sha256": source.required_procedure_catalog.catalog_sha256,
        "review_visit_nodes": sorted({(item.visit_instance, item.review_stage.value)
                                     for item in source.required_procedure_catalog.items
                                     if item.visit_instance and item.review_stage}),
        "review_visit_tables": [item.model_dump(mode="json") for item in source.required_procedure_catalog.visit_tables],
        "review_stage_aliases": {key.value: value.value for key, value
                                 in frozen_review_stage_aliases(source).items()},
        "procedure_source_sha256": canonical_hash({
            ref: materials[ref].text for ref in {
                *(ref for item in source.required_procedure_catalog.items for ref in item.source_span_ids),
                *(ref for table in source.required_procedure_catalog.visit_tables
                  for ref in (table.table_source_span_id, *(ref for column in table.columns for ref in column.source_span_ids))),
            } if ref in materials}),
        "children": children,
        "restricted_siblings": [item.model_dump(mode="json") for item in rule.restricted_components],
    }


def scope_review_prompt(basis: dict, *, source_reading: OfficialScopeReading | None = None) -> str:
    inputs = dict(basis)
    if source_reading is None:
        inputs["children"] = [{key: value for key, value in child.items() if key != "component"}
                              for child in basis["children"]]
        instruction = "只从冻结原文判断关系，不看现有程序条件；proposal_agreement 必须为 null。"
    else:
        inputs["source_reading"] = source_reading.model_dump(mode="json")
        instruction = (
            "先从原文逐项核对，再核对现有条件、资料节点和前次提案；"
            "仅当关系及每个实际必需节点均吻合时 proposal_agreement=true，否则 false。"
        )
    return (
        "你核对同一官方标准中总标题与各独立子项的作用关系，不作患者入排结论，不改规则。"
        "节点提示不等于所有子项在所有节点满足。共同约束为 governing；明确分别叙述不同节点为"
        " separate_nodes；只有背景作用为 context_only；原文不足或冲突为 unresolved。"
        "required_stages 只写本子项的实际审核节点，不能把测量时间机械当审核节点，也不能删除"
        "真正共同约束。review_visit_nodes提供冻结流程表的访视名称及节点；review_stage_aliases"
        "仅表示有源且唯一的合并访视名称，不改变时间锚点、日期或要求重复核对的次数。不得根据"
        "待核提案自己创建别名。"
        "不得用常见临床做法补原文。每项分别引用冻结标题和该子项支持文字，"
        "跨段限制必须保留；不选取兄弟片段替代本项。覆盖全部给定子项，不新增或合并。"
        "每个原子条件须单独给出适用节点及逐字依据。逐个总标题记录公开、可核查的作用范围说明与依据，"
        "不是只填关系标签或投票。node_overview只用于原文明确分别描述两个或更多节点的情况，"
        "总标题的全部节点须在完整子项来源中找到对应；真正共同约束须标shared_constraint，"
        "每个条件在每个共同节点都要有对应资料要求。context_only不能用来自动删去标题中的节点。"
        "真正无法确认节点时标unresolved，required_stages可为空，但仍逐项引用原文、"
        "保留条件身份并说明具体未知，不猜节点。"
        + instruction + "\n只输出以下Schema的JSON，不输出思考过程：\n"
        + json.dumps(OfficialScopeReading.model_json_schema(), ensure_ascii=False)
        + "\n冻结输入：\n" + json.dumps(inputs, ensure_ascii=False)
    )


def validate_scope_reading(reading: OfficialScopeReading, basis: dict, *, proposal: bool,
                           component_id: str | None = None) -> None:
    expected = {child["component_id"]: child for child in basis["children"]}
    if {item.component_id for item in reading.items} != set(expected):
        raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_TARGET_MISMATCH")
    if component_id is not None and component_id not in expected:
        raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_TARGET_MISMATCH")
    texts = {item["source_span_id"]: item["text"] for item in basis["materials"]}
    def valid_citations(citations):
        return all(cite.source_span_id in texts and cite.excerpt in texts[cite.source_span_id] for cite in citations)
    for item in reading.items:
        if component_id is not None and item.component_id != component_id:
            continue
        child = expected[item.component_id]
        if (not isinstance(item.proposal_agreement, bool) if proposal else item.proposal_agreement is not None):
            raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_PHASE_MISMATCH")
        if (item.relation == "governing"
                and not set(basis["heading_stages"]) <= {stage.value for stage in item.required_stages}):
            raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_SHARED_NODE_MISSING")
        citations = item.citations
        if any(cite.source_span_id not in texts
               or cite.excerpt not in texts[cite.source_span_id] for cite in citations):
            raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_CITATION_INVALID")
        if any(not any(cite.source_span_id == heading["source_span_id"]
                       and heading["excerpt"] in cite.excerpt for cite in citations)
               for heading in basis["headings"]):
            raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_HEADING_MISSING")
        if not child["source_excerpts"] or any(
            not any(cite.source_span_id in child["source_refs"] and excerpt in cite.excerpt
                    for cite in citations) for excerpt in child["source_excerpts"]
        ):
            raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_CHILD_MISSING")
        if proposal and item.proposal_agreement is True:
            actual = {value["due_stage"] for value in child["component"]["evidence_requirements"]}
            if actual != {stage.value for stage in item.required_stages}:
                raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_PROPOSAL_MISMATCH")
        expected_predicates = {predicate["predicate_id"]: predicate for predicate in child["predicates"]}
        assignments = {assignment.predicate_id: assignment for assignment in item.predicate_assignments}
        if len(assignments) != len(item.predicate_assignments) or set(assignments) != set(expected_predicates):
            raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_PREDICATE_MISMATCH")
        assigned_stages = set()
        for predicate_id, assignment in assignments.items():
            assigned_stages.update(assignment.required_stages)
            if (len(assignment.required_stages) != len(set(assignment.required_stages))
                    or not valid_citations(assignment.citations)
                    or not expected_predicates[predicate_id]["source_clauses"]
                    or any(not any(cite.source_span_id in child["source_refs"] and clause in cite.excerpt
                                   for cite in assignment.citations)
                           for clause in expected_predicates[predicate_id]["source_clauses"])):
                raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_PREDICATE_SOURCE_INVALID")
            if item.relation == "governing" and not set(basis["heading_stages"]) <= {stage.value for stage in assignment.required_stages}:
                raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_SHARED_NODE_MISSING")
            if proposal and item.proposal_agreement is True:
                actual = {requirement["due_stage"] for requirement in child["component"]["evidence_requirements"]
                          if predicate_id in requirement.get("predicate_ids", [])}
                if actual != {stage.value for stage in assignment.required_stages}:
                    raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_PREDICATE_REQUIREMENT_MISMATCH")
        if assigned_stages != set(item.required_stages):
            raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_PREDICATE_MISMATCH")
        headings = {(heading["source_span_id"], heading["excerpt"]) for heading in basis["headings"]}
        dispositions = {(value.source_span_id, value.excerpt): value for value in item.heading_dispositions}
        if len(dispositions) != len(item.heading_dispositions) or set(dispositions) != headings:
            raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_HEADING_MISSING")
        expected_disposition = {"governing": "shared_constraint", "separate_nodes": "node_overview",
                                "context_only": "context_only", "unresolved": "unresolved"}[item.relation]
        for disposition in dispositions.values():
            if disposition.disposition != expected_disposition or not valid_citations(disposition.supporting_citations):
                raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_DISPOSITION_INVALID")
            if not any(cite.source_span_id == disposition.source_span_id and disposition.excerpt in cite.excerpt
                       for cite in disposition.supporting_citations):
                raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_HEADING_MISSING")
        if item.relation == "context_only" and not set(basis["heading_stages"]) <= {stage.value for stage in item.required_stages}:
            raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_NARROWING_UNVERIFIED")
        if item.relation in {"separate_nodes", "context_only"}:
            from app.protocols.deconstruction_gate import _substantive_obligation_segments
            # A colon also inventories substantive or ambiguous prefixes. They
            # must not become harmless headings merely because two labels agree.
            if any(_substantive_obligation_segments(
                heading["excerpt"].rstrip("：:\r\n").strip().replace("，", "").replace(",", "")
            ) for heading in basis["headings"]):
                raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_NARROWING_UNVERIFIED")
        if item.relation == "separate_nodes":
            from app.protocols.deconstruction_gate import _source_review_stages
            aliases = {ReviewStage(key): ReviewStage(value)
                       for key, value in basis.get("review_stage_aliases", {}).items()}
            supported = set().union(*(_source_review_stages(value["source_excerpts"], stage_aliases=aliases) for value in basis["children"]))
            if len(supported) < 2 or not set(basis["heading_stages"]) <= {stage.value for stage in supported}:
                raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_NARROWING_UNVERIFIED")
            if any(not set(assignment.required_stages) <= _source_review_stages(expected_predicates[predicate_id]["source_clauses"], stage_aliases=aliases)
                   for predicate_id, assignment in assignments.items()):
                raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_NARROWING_UNVERIFIED")


def accepted_scope_items(first: OfficialScopeReading, second: OfficialScopeReading) -> set[str]:
    by_id = {item.component_id: item for item in first.items}
    return {item.component_id for item in second.items
            if item.proposal_agreement is True and item.relation != "unresolved"
            and by_id[item.component_id].relation == item.relation
            and set(by_id[item.component_id].required_stages) == set(item.required_stages)
            and {value.predicate_id: set(value.required_stages) for value in by_id[item.component_id].predicate_assignments}
                == {value.predicate_id: set(value.required_stages) for value in item.predicate_assignments}}


def read_scope_receipt(basis, stage, receipt, read, *, source_reading=None):
    """Verify the saved actual request and response, not a reconstructed answer."""
    if not receipt["request_ref"].startswith("artifacts/raw_request/") or not receipt["response_ref"].startswith("artifacts/raw_response/"):
        raise ValueError("wrong artifact kind")
    request, response = json.loads(read(receipt["request_ref"])), json.loads(read(receipt["response_ref"]))
    expected_request = {"version": SCOPE_REVIEW_VERSION, "basis_sha256": canonical_hash(basis),
                        "stage": stage, "prompt": scope_review_prompt(basis, source_reading=source_reading)}
    if {key: request.get(key) for key in expected_request} != expected_request:
        raise ValueError("request changed")
    options = request["request_options"]
    if options["messages"] != [{"role": "user", "content": expected_request["prompt"]}]:
        raise ValueError("actual request is not the frozen prompt")
    attempts = response["call_metadata"]["attempts"]
    if (not attempts or attempts[-1]["finish_reason"] != "stop"
            or not attempts[-1]["requested_model"]
            or attempts[-1]["requested_model"].casefold() != attempts[-1]["reported_model"].casefold()
            or any(attempt["requested_model"] != options["model"] for attempt in attempts)
            or attempts[0]["request_sha256"] != hashlib.sha256(json.dumps(
                options["messages"], ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest()
            or attempts[-1]["request_sha256"] != attempts[0]["request_sha256"]
            or not response["session_id"]):
        raise ValueError("unverifiable model response")
    return OfficialScopeReading.model_validate_json(response["text"]), response["session_id"], options


def scope_item_rejections(reading, basis, *, proposal):
    # Missing/foreign targets and Schema errors remain whole-receipt failures.
    if {item.component_id for item in reading.items} != {item["component_id"] for item in basis["children"]}:
        raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_TARGET_MISMATCH")
    rejected = {}
    for item in reading.items:
        try:
            validate_scope_reading(reading, basis, proposal=proposal, component_id=item.component_id)
        except OfficialScopeReviewError as exc:
            rejected[item.component_id] = exc.code
    return rejected


def reviewed_scope_stages(source, draft, rule, component, headings, read: Callable[[str], bytes] | None, *, heading_stages):
    ref = component.source_scope_review_ref
    if ref is None:
        return None
    try:
        if read is None or not ref.startswith("artifacts/evaluation_manifest/"):
            raise ValueError("missing review store")
        record = json.loads(read(ref))
        basis = scope_review_basis(source, draft, rule, headings, heading_stages=heading_stages)
        if (record["version"] != SCOPE_REVIEW_VERSION
                or record["basis_sha256"] != canonical_hash(basis)
                or record.get("validation_policy") not in (None, "component-local/v1")):
            raise ValueError("stale scope review")
        readings, sessions = [], []
        rejection_code = None
        for stage, receipt in zip(("source", "proposal"), record["receipts"], strict=True):
            reading, session_id, _options = read_scope_receipt(
                basis, stage, receipt, read, source_reading=readings[0] if readings else None)
            sessions.append(session_id)
            if record.get("validation_policy") == "component-local/v1":
                rejected = scope_item_rejections(reading, basis, proposal=stage == "proposal")
                if component.rule_component_id in rejected:
                    rejection_code = rejection_code or rejected[component.rule_component_id]
            else:
                validate_scope_reading(reading, basis, proposal=stage == "proposal")
            readings.append(reading)
        if len({json.loads(read(receipt["request_ref"]))["request_options"]["model"] for receipt in record["receipts"]}) != 1:
            raise ValueError("scope review changed model")
        if len(set(sessions)) != 2 or not all(sessions):
            raise ValueError("review disagreement or reused session")
        if rejection_code is not None:
            raise OfficialScopeRejectedError(rejection_code)
        if component.rule_component_id not in accepted_scope_items(*readings):
            current = next(item for item in readings[1].items if item.component_id == component.rule_component_id)
            first = next(item for item in readings[0].items if item.component_id == component.rule_component_id)
            raise OfficialScopeUnresolvedError(current.unresolved_dimensions or first.unresolved_dimensions
                or ["两次核对对本子项的总标题作用范围或适用节点尚未一致"])
        return set(next(item for item in readings[1].items if item.component_id == component.rule_component_id).required_stages)
    except (OfficialScopeUnresolvedError, OfficialScopeRejectedError):
        raise
    except (ValueError, KeyError, TypeError, AttributeError, IndexError, OSError, RuntimeError) as exc:
        raise OfficialScopeReviewError("SOURCE_SCOPE_REVIEW_INVALID") from exc
