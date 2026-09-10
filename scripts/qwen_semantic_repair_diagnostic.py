"""Isolated replay of product frequency checks and targeted repair prompt."""

import argparse
import asyncio
import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from types import SimpleNamespace

import jsonschema

from app.agents.protocol_deconstructor import (
    _SYSTEM_CONTRACT, _omlx_wire_schema, _parse_semantic_candidate, _parse_semantic_repair, _repair_prompt,
    protocol_output_response_format,
    _configure_transport_output_scope,
    _merge_semantic_batches, _apply_semantic_repair, _hydrate_semantic_candidate,
    _parent_segmentation_thresholds,
    _next_batch_prompt,
)
from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport
from app.domain.contracts.agent_io import ProtocolDeconstructionInput
from app.storage.codecs import verify_payload_sha256
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.protocols.parent_rule_semantic_segmentation import plan_parent_rule_segments, merge_parent_rule_segments, validate_segment_source_closure
from app.protocols.deconstruction_gate import ProtocolDeconstructionGate
from scripts.qwen_protocol_measurement import StreamingClient
from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_harness import PageReaderRoute
from app.protocols.deconstruction_gate import (
    _issue, _predicate_preserves_frequency, _source_frequency_specs, _walk_expression_tree,
    _frequency_repair_action,
)
from scripts.qwen_platform_measurement import MeasuredCompletion, save
from app.protocols.definition_scope_check import crosses_example_scope
from app.llm.omlx_schema_compat import decoding_response_format


def frequency_issues(candidate):
    issues = []
    for rule in candidate.proposed_rules:
        for component in rule.components:
            specs = _source_frequency_specs(" ".join(component.source_excerpts))
            roots = [component.expression]
            if component.exception_expression is not None:
                roots.append(component.exception_expression)
            atoms = [node.predicate for root in roots for node in _walk_expression_tree(root)
                     if node.kind == "predicate"]
            if any(not any(_predicate_preserves_frequency(atom, spec) for atom in atoms)
                   for spec in specs):
                issues.append(_issue("temporal_semantics", "FREQUENCY_WINDOW_NOT_STRUCTURED",
                    "原文频次定义未完整保留为可计算条件。", [rule.official_code],
                    action=_frequency_repair_action()))
    return issues


def scope_issues(candidate):
    issues = []
    for rule in candidate.proposed_rules:
        for component in rule.components:
            for group in _walk_expression_tree(component.expression):
                if group.kind != "logical" or group.operator != "all":
                    continue
                atoms = [child.predicate for child in group.children if child.kind == "predicate"]
                for atom in atoms:
                    if atom.occurrence_window is None or not atom.source_clause:
                        continue
                    if any(crosses_example_scope(source, atom.source_clause, other.source_clause or "")
                           for source in component.source_excerpts for other in atoms if other is not atom):
                        issues.append(_issue("temporal_semantics", "FREQUENCY_WINDOW_SCOPE",
                            "示例中的频次与上位条件处于同一个必须同时满足的组，可能收窄原文范围。",
                            [rule.official_code], level="需要核对",
                            action="依据原文核对定义与触发条件的区别，不得把示例限制设为上位条件的必要条件；保持上位条件原有范围。"))
    return issues


def frozen_payload(database, job_id):
    # This diagnostic accepts only an offline database, never a live WAL snapshot.
    wal = Path(str(database) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise ValueError("请先提供一致的离线数据库副本，不读取活动 WAL")
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        rows = connection.execute(
            "SELECT payload_json,payload_sha256 FROM job_checkpoints WHERE job_id=? ORDER BY created_at",
            (job_id,),
        ).fetchall()
    finally:
        connection.close()
    inputs = [value for raw, digest in rows
              if "source_input" in (value := verify_payload_sha256(raw, digest))]
    if len(inputs) != 1:
        raise ValueError("必须且只能找到一份冻结方案输入")
    return inputs[0]


def frozen_input(database, job_id):
    return ProtocolDeconstructionInput.model_validate(frozen_payload(database, job_id)["source_input"])


def offline_gate(args):
    payload = frozen_payload(args.frozen_db, args.job_id)
    source = ProtocolDeconstructionInput.model_validate(payload["source_input"])
    entries = []
    for path in sorted(args.offline_gate_cache.glob("*.json")):
        cached = json.loads(path.read_text())
        verify_payload_sha256(cached["response_text"], cached["response_sha256"])
        entries.append((cached["cache_contract"], _parse_semantic_candidate(cached["response_text"], compact=False)))
    normal = [c for kind, c in entries if kind == "protocol-semantic-batch/v1"]
    available = {r.official_code for _, c in entries for r in c.proposed_rules}
    missing = [item.official_code for item in source.parent_rule_catalog.items
               if item.official_code not in available]
    if missing:
        args.output.mkdir(parents=True, exist_ok=False)
        status = {"state": "incomplete_baseline", "clinical_acceptance": False,
                  "model_called": False, "missing_rule_codes": missing}
        save(args.output / "status.json", status)
        print(json.dumps(status), flush=True)
        return
    first = normal[0]
    batches = []
    for item in sorted(source.parent_rule_catalog.items, key=lambda item: item.position):
        matches = [(c, r) for c in normal for r in c.proposed_rules if r.official_code == item.official_code]
        if matches:
            if len(matches) != 1:
                raise ValueError("缓存父规则重复")
            c, rule = matches[0]
            batches.append(c.model_copy(update={"proposed_rules": [rule], "structural_warnings": [], "unresolved_items": []}))
            continue
        thresholds = _parent_segmentation_thresholds()
        # Cached segments prove that the trigger fired; boundaries still use the product planner.
        plan = plan_parent_rule_segments(item, source_materials=source.source_materials,
            token_estimate=thresholds.soft_input_tokens, thresholds=thresholds)
        if plan is None:
            raise ValueError("无法重建既有分段边界")
        parts = []
        for segment in plan.segments:
            matched = []
            for kind, c in entries:
                if kind != "protocol-semantic-parent-segment/v1":
                    continue
                try:
                    validate_segment_source_closure(c, segment)
                except ValueError:
                    continue
                matched.append(c)
            if len(matched) != 1:
                raise ValueError("分段缓存无法唯一匹配冻结来源")
            parts.append(matched[0])
        batches.append(merge_parent_rule_segments(parts, plan=plan,
            candidate_id=first.candidate_id, agent_call_id=first.created_by_agent_call_id))
    candidate = _merge_semantic_batches(batches, source_input=source,
        expected_codes=[item.official_code for item in sorted(source.parent_rule_catalog.items, key=lambda item: item.position)])
    # Retain warnings from every whole batch; splitting above must not duplicate them.
    candidate = candidate.model_copy(update={
        "structural_warnings": [w for _, c in entries for w in c.structural_warnings],
        "unresolved_items": [w for _, c in entries for w in c.unresolved_items]})
    text = args.candidate.read_text()
    raw = json.loads(text)
    repair = _parse_semantic_repair(raw.get("text", text), compact=False)
    revised = _apply_semantic_repair(candidate, repair,
        expected_codes=[rule.official_code for rule in repair.replacement_rules])
    spans = {key: ProtocolSourceSpan.model_validate(value) for key, value in payload["source_spans"].items()}
    args.output.mkdir(parents=True, exist_ok=False)
    for label, value in (("before", candidate), ("after", revised)):
        draft = _hydrate_semantic_candidate(source, value)
        result = ProtocolDeconstructionGate().evaluate(source, draft, source_spans=spans)
        save(args.output / (label + "-gate.json"), result.model_dump(mode="json"))
        save(args.output / (label + "-draft.json"), draft.model_dump(mode="json"))
    print(json.dumps({"state": "offline_gates_completed", "clinical_acceptance": False}), flush=True)


def formal_diagnostic(args, request, text):
    candidate = _parse_semantic_candidate(text, compact=False)
    source = frozen_input(args.frozen_db, args.job_id)
    issues = frequency_issues(candidate) + scope_issues(candidate)
    codes = list(dict.fromkeys(ref for issue in issues for ref in issue.affected_refs))
    if args.batch_codes:
        codes = args.batch_codes
        issues = []
        prompt = _next_batch_prompt(codes, batch_number=1, batch_total=1,
            candidate_id=candidate.candidate_id, source_input=source,
            compact=False, scoped_source=True)
        output_kind = "semantic_candidate"
    elif not codes:
        raise ValueError("没有可复现的频次问题，不发起模型调用")
    else:
        prompt = _repair_prompt(issues, attempt=1, parsed_draft_available=True,
            replacement_rule_codes=codes, compact=False, include_frozen_context=True,
            candidate=candidate, source_input=source)
        output_kind = "semantic_rule_repair"
    args.output.mkdir(parents=True, exist_ok=False)
    route = PageReaderRoute(PageReviewLane.MAIN_A, args.provider, args.url, "local-benchmark",
        request["model"], request["reasoning_effort"], args.max_tokens, 1)
    meter = MeasuredCompletion(args.output, args.tokenizer)
    transport = DeepSeekProtocolAgentTransport(
        client=StreamingClient(meter, route, threading.Lock()), backend=args.provider,
        base_url=args.url, model=request["model"], reasoning_effort=request["reasoning_effort"],
        max_tokens=args.max_tokens, provider_defaults=True, compact_wire=False)
    _configure_transport_output_scope(transport, source, codes)
    # Product repair restores frozen source explicitly, so no prior batch history is needed.
    prepared = transport._completion_kwargs(
        [{"role": "user", "content": prompt}], output_kind=output_kind)
    if prepared["max_tokens"] != args.max_tokens:
        raise ValueError("产品批次额度与诊断要求不一致，请显式设置对应平台的 PROTOCOL_BATCH_MAX_TOKENS")
    save(args.output / "prepared-request.json", prepared)
    save(args.output / "diagnostic.json", {
        "ranking_eligible": False, "clinical_acceptance": False, "codes": codes,
        "strategy": "formal_product_" + output_kind, "job_id": args.job_id,
        "candidate_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "issues": [issue.model_dump(mode="json") for issue in issues]})
    if args.prepare_only:
        print(json.dumps({"state": "prepared", "model_called": False, "codes": codes}), flush=True)
        return
    try:
        result = transport.start(prompt=prompt, output_kind=output_kind)
        repair = (_parse_semantic_candidate(result.text, compact=False) if args.batch_codes
                  else _parse_semantic_repair(result.text, compact=False))
        rules = repair.proposed_rules if args.batch_codes else repair.replacement_rules
        if repair.candidate_id != candidate.candidate_id or sorted(
            rule.official_code for rule in rules) != sorted(codes):
            raise ValueError("修订身份或条款范围与请求不一致")
        remaining = frequency_issues(SimpleNamespace(proposed_rules=rules))
        remaining += scope_issues(SimpleNamespace(proposed_rules=rules))
        status = {"state": "completed", "clinical_acceptance": False,
                  "remaining_issues": [issue.model_dump(mode="json") for issue in remaining]}
    except Exception as exc:
        status = {"state": "failed", "clinical_acceptance": False,
                  "error": type(exc).__name__, "detail": str(exc)[:1000]}
    save(args.output / "status.json", status)
    print(json.dumps(status, ensure_ascii=False), flush=True)


async def main(args):
    if args.offline_gate_cache:
        offline_gate(args)
        return
    request = json.loads(args.request.read_bytes())
    text = args.candidate.read_text()
    payload = json.loads(text)
    if "text" in payload:
        text = payload["text"]
        payload = json.loads(text)
    if args.frozen_db:
        if not args.job_id:
            raise ValueError("正式格式诊断必须指定冻结作业身份")
        await asyncio.to_thread(formal_diagnostic, args, request, text)
        return
    if args.prepare_only:
        raise ValueError("只准备模式必须指定冻结数据库")
    if "replacement_rules" in payload:
        repair = _parse_semantic_repair(text, compact=True)
        candidate = SimpleNamespace(proposed_rules=repair.replacement_rules)
    else:
        candidate = _parse_semantic_candidate(text, compact=True)
    issues = frequency_issues(candidate) + scope_issues(candidate)
    if not issues:
        raise ValueError("No product frequency check failure to repair")
    codes = list(dict.fromkeys(ref for issue in issues for ref in issue.affected_refs))
    sources = sorted({s for rule in candidate.proposed_rules if rule.official_code in codes
                      for component in rule.components for s in component.source_span_ids})
    schema = _omlx_wire_schema("semantic_rule_repair", official_codes=codes,
                                        allowed_source_span_ids=sources)
    prompt = _repair_prompt(issues, attempt=1, parsed_draft_available=True,
                            replacement_rule_codes=codes, compact=True)
    messages = [*request["messages"], {"role": "assistant", "content": text},
                {"role": "user", "content": prompt + "\n" + _SYSTEM_CONTRACT
                 + "\n本次修订输出格式：" + json.dumps(schema, ensure_ascii=False)}]
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / "diagnostic.json", {"ranking_eligible": False, "clinical_acceptance": False,
        "strategy": "product_frequency_check_and_repair", "codes": codes,
        "candidate_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "issues": [i.model_dump(mode="json") for i in issues]})
    route = PageReaderRoute(PageReviewLane.MAIN_A, args.provider, args.url, "local-benchmark",
                            request["model"], request["reasoning_effort"], request["max_tokens"], 1)
    meter = MeasuredCompletion(args.output, args.tokenizer)
    options = {"response_format": protocol_output_response_format(
        "semantic_rule_repair", compact=True, official_codes=codes,
        allowed_source_span_ids=sources)}
    if args.provider == "omlx":
        options["response_format"] = decoding_response_format(options["response_format"])
        if "thinking_budget" in request:
            options["thinking_budget"] = request["thinking_budget"]
    try:
        result = await meter(route, messages, request["max_tokens"],
                             options)
        parsed = json.loads(result.text)
        jsonschema.validate(parsed, schema)
        _parse_semantic_repair(result.text, compact=True)
        status = {"state": "completed" if result.finish_reason == "stop" else "incomplete",
                  "schema_valid": True, "product_wire_validated": True, "clinical_acceptance": False}
    except Exception as exc:
        status = {"state": "failed", "error": type(exc).__name__, "detail": str(exc)[:500],
                  "clinical_acceptance": False}
    save(args.output / "status.json", status)
    print(json.dumps(status), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("request", "candidate", "output", "tokenizer"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:11234/v1")
    parser.add_argument("--provider", choices=["mlx-serve", "omlx", "mtplx"], default="mlx-serve")
    parser.add_argument("--frozen-db", type=Path)
    parser.add_argument("--job-id")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=131072)
    parser.add_argument("--offline-gate-cache", type=Path)
    parser.add_argument("--batch-codes", nargs="+")
    asyncio.run(main(parser.parse_args()))
