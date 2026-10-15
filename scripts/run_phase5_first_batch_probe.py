"""Run one bounded real-model protocol batch through all publication checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport
from app.agents.protocol_deconstructor import (
    ProtocolDeconstructorRunner,
    _hydrate_semantic_candidate,
    _parse_semantic_candidate,
    _validate_semantic_batch,
    build_protocol_deconstruction_prompt,
    protocol_prompt_template_sha256,
)
from app.domain.contracts.agents import PromptVersion
from app.config import (
    DECONSTRUCT_MAX_TOKENS,
    MTPLX_BASE_URL,
    MTPLX_MODEL,
    MTPLX_REASONING_EFFORT,
)
from app.domain.contracts.agent_io import ProtocolDeconstructionInput
from app.domain.contracts.enums import AgentNode
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.protocols.deconstruction_gate import ProtocolDeconstructionGate


PROMPT_TEMPLATE = (
    "请以资深临床试验医学监查人员的专业语义解构本次已确认期别的正式研究方案。"
    "逐条保留官方父规则，准确表达每个必要条件、替代条件、例外、时间锚点、专业判断，"
    "并把基线及以前每个必做项目映射到其独立审核节点。"
)


class _FirstBatchAcceptanceRunner(ProtocolDeconstructorRunner):
    """Exercise the product loop without allowing repeated semantic guessing."""

    MAX_SCHEMA_REPAIRS = 1
    MAX_LOCAL_SCHEMA_REPAIRS = 1
    MAX_SEMANTIC_REPAIRS = 1


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _failure_summary(
    *,
    args: argparse.Namespace,
    rule_codes: list[str],
    prompt: str,
    elapsed: float,
    status: str,
    failure_code: str,
    diagnostic: str,
    session_id: str | None = None,
    raw_response_preserved: bool = False,
) -> dict[str, object]:
    return {
        "status": status,
        "failure_code": failure_code,
        "model": args.model,
        "base_url": args.base_url,
        "local_product_model_context_limit_override": True,
        "batch_id": args.batch_id,
        "rule_codes": rule_codes,
        "prompt_chars": len(prompt),
        "session_id": session_id,
        "elapsed_seconds": elapsed,
        "source_file": str(args.source_file) if args.source_file else None,
        "source_sha256_before": _sha256(args.source_file) if args.source_file else None,
        "source_sha256_expected": None,
        "raw_response_preserved": raw_response_preserved,
        "diagnostic": diagnostic[:2000],
        "publishable": False,
        "manual_clinical_qc": {"status": "not_started"},
    }


def _scoped_input(
    source_input: ProtocolDeconstructionInput, rule_codes: list[str]
) -> ProtocolDeconstructionInput:
    selected_items = tuple(
        item
        for item in source_input.parent_rule_catalog.items
        if item.official_code in rule_codes
    )
    selected_refs = list(
        dict.fromkeys(
            span_id for item in selected_items for span_id in item.source_span_ids
        )
    )
    selected_materials = [
        material
        for material in source_input.source_materials
        if material.source_span_id in selected_refs
    ]
    return source_input.model_copy(
        update={
            "allowed_source_span_ids": selected_refs,
            "source_materials": selected_materials,
            "parent_rule_catalog": source_input.parent_rule_catalog.model_copy(
                update={"items": selected_items}
            ),
            "required_procedure_catalog": (
                source_input.required_procedure_catalog.model_copy(update={"items": ()})
            ),
            "interpretation_source_ids": [],
        },
        deep=True,
    )


def _run_bounded_product_loop(
    *,
    args: argparse.Namespace,
    source_input: ProtocolDeconstructionInput,
    source_spans: dict[str, ProtocolSourceSpan],
    rule_codes: list[str],
) -> int:
    scoped_input = _scoped_input(source_input, rule_codes)
    scoped_spans = {
        span_id: source_spans[span_id]
        for span_id in scoped_input.allowed_source_span_ids
    }
    transport = DeepSeekProtocolAgentTransport(
        backend=args.backend,
        base_url=args.base_url,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        max_tokens=args.max_tokens,
    )
    prompt_version = PromptVersion(
        prompt_version_id="phase5-first-batch-acceptance/v1",
        node=AgentNode.PROTOCOL_DECONSTRUCTOR,
        template_sha256=protocol_prompt_template_sha256(PROMPT_TEMPLATE),
        schema_version_id="protocol-deconstruction-draft/fixture-v1",
    )
    started = time.monotonic()
    result = _FirstBatchAcceptanceRunner().run(
        scoped_input,
        prompt_version=prompt_version,
        prompt_template=PROMPT_TEMPLATE,
        transport=transport,
        source_spans=scoped_spans,
    )
    elapsed = round(time.monotonic() - started, 2)
    _write_json(
        args.output_dir / "runner-result.json",
        result.model_dump(mode="json"),
    )
    _write_json(
        args.output_dir / "conversation-history.json",
        list(transport.history(result.same_session_id)),
    )
    if result.final_draft is not None:
        _write_json(
            args.output_dir / "hydrated-draft.json",
            result.final_draft.model_dump(mode="json"),
        )
    if result.final_gate_result is not None:
        _write_json(
            args.output_dir / "full-gate-result.json",
            result.final_gate_result.model_dump(mode="json"),
        )
    issues = [issue for attempt in result.attempts for issue in attempt.issues]
    publishable = bool(
        result.final_gate_result and result.final_gate_result.publishable
    )
    summary = {
        "status": "formal_gate_passed" if publishable else "rejected",
        "model": args.model,
        "base_url": args.base_url,
        "local_product_model_context_limit_override": True,
        "mode": "bounded_product_runner",
        "semantic_repair_limit": 1,
        "rule_codes": rule_codes,
        "session_id": result.same_session_id,
        "elapsed_seconds": elapsed,
        "attempt_count": len(result.attempts),
        "attempt_outcomes": [item.outcome for item in result.attempts],
        "issue_codes": [item.issue_code for item in issues],
        "source_file": str(args.source_file) if args.source_file else None,
        "source_sha256_before": _sha256(args.source_file) if args.source_file else None,
        "source_sha256_expected": scoped_input.protocol_file_sha256,
        "publishable": publishable,
        "manual_clinical_qc": {
            "status": "pending" if result.final_draft is not None else "not_started",
            "instruction": "必须逐条对照父条款原文、原子条件、资料要求和来源定位，不得以门控通过代替。",
        },
    }
    _write_json(args.output_dir / "summary.json", summary)
    return 0 if publishable else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-package", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-file", type=Path)
    parser.add_argument("--backend", default="mtplx")
    parser.add_argument("--base-url", default=MTPLX_BASE_URL)
    parser.add_argument("--model", default=MTPLX_MODEL)
    parser.add_argument("--reasoning-effort", default=MTPLX_REASONING_EFFORT)
    parser.add_argument("--max-tokens", type=int, default=DECONSTRUCT_MAX_TOKENS)
    parser.add_argument("--batch-id", default="1/12")
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--agent-call-id", required=True)
    parser.add_argument("--rule-code", action="append", required=True)
    parser.add_argument("--bounded-product-runner", action="store_true")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=False)
    package = json.loads(args.source_package.read_text(encoding="utf-8"))
    source_input = ProtocolDeconstructionInput.model_validate(package["source_input"])
    source_spans = {
        span_id: ProtocolSourceSpan.model_validate(payload)
        for span_id, payload in package["source_spans"].items()
    }
    rule_codes = list(args.rule_code)
    if args.bounded_product_runner:
        return _run_bounded_product_loop(
            args=args,
            source_input=source_input,
            source_spans=source_spans,
            rule_codes=rule_codes,
        )
    batch_number, batch_total = (int(value) for value in args.batch_id.split("/"))
    prompt = build_protocol_deconstruction_prompt(
        source_input,
        prompt_template=PROMPT_TEMPLATE,
        requested_rule_codes=rule_codes,
        batch_number=batch_number,
        batch_total=batch_total,
        candidate_id=args.candidate_id,
        batch_id=args.batch_id,
        agent_call_id=args.agent_call_id,
        compact=True,
    )
    (args.output_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    transport = DeepSeekProtocolAgentTransport(
        backend=args.backend,
        base_url=args.base_url,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        max_tokens=args.max_tokens,
    )
    started = time.monotonic()
    try:
        response = transport.start(prompt=prompt, output_kind="semantic_candidate")
    except Exception as exc:
        elapsed = round(time.monotonic() - started, 2)
        summary = _failure_summary(
            args=args,
            rule_codes=rule_codes,
            prompt=prompt,
            elapsed=elapsed,
            status="transport_failed",
            failure_code="MODEL_RESPONSE_UNAVAILABLE",
            diagnostic=f"{type(exc).__name__}: {exc}",
            session_id=getattr(exc, "session_id", None),
        )
        summary["source_sha256_expected"] = source_input.protocol_file_sha256
        _write_json(args.output_dir / "summary.json", summary)
        return 3
    elapsed = round(time.monotonic() - started, 2)
    (args.output_dir / "raw-response.txt").write_text(
        response.text, encoding="utf-8"
    )
    try:
        raw_payload = json.loads(response.text)
    except json.JSONDecodeError as exc:
        summary = _failure_summary(
            args=args,
            rule_codes=rule_codes,
            prompt=prompt,
            elapsed=elapsed,
            status="response_invalid",
            failure_code="JSON_BODY_INVALID",
            diagnostic=(
                f"JSONDecodeError: 第{exc.lineno}行第{exc.colno}列，{exc.msg}"
            ),
            session_id=response.session_id,
            raw_response_preserved=True,
        )
        summary["source_sha256_expected"] = source_input.protocol_file_sha256
        _write_json(args.output_dir / "summary.json", summary)
        return 3
    _write_json(args.output_dir / "raw-response.json", raw_payload)

    try:
        candidate = _parse_semantic_candidate(
            response.text, compact=True, expected_batch_id=args.batch_id
        )
        _validate_semantic_batch(
            candidate,
            expected_codes=rule_codes,
            expected_candidate_id=args.candidate_id,
            expected_agent_call_id=args.agent_call_id,
            source_input=source_input,
        )
    except (TypeError, ValueError) as exc:
        summary = _failure_summary(
            args=args,
            rule_codes=rule_codes,
            prompt=prompt,
            elapsed=elapsed,
            status="contract_rejected",
            failure_code="COMPACT_CONTRACT_INVALID",
            diagnostic=f"{type(exc).__name__}: {exc}",
            session_id=response.session_id,
            raw_response_preserved=True,
        )
        summary["source_sha256_expected"] = source_input.protocol_file_sha256
        _write_json(args.output_dir / "summary.json", summary)
        return 2
    scoped_input = _scoped_input(source_input, rule_codes)
    scoped_spans = {
        span_id: source_spans[span_id]
        for span_id in scoped_input.allowed_source_span_ids
    }
    draft = _hydrate_semantic_candidate(scoped_input, candidate)
    gate_result = ProtocolDeconstructionGate().evaluate(
        scoped_input, draft, source_spans=scoped_spans
    )
    _write_json(
        args.output_dir / "full-gate-result.json",
        gate_result.model_dump(mode="json"),
    )
    _write_json(
        args.output_dir / "hydrated-draft.json", draft.model_dump(mode="json")
    )
    issues = [issue for check in gate_result.checks for issue in check.issues]
    summary = {
        "status": "formal_gate_passed" if gate_result.publishable else "rejected",
        "model": args.model,
        "base_url": args.base_url,
        "local_product_model_context_limit_override": True,
        "batch_id": args.batch_id,
        "rule_codes": rule_codes,
        "prompt_chars": len(prompt),
        "session_id": response.session_id,
        "response_chars": len(response.text),
        "elapsed_seconds": elapsed,
        "source_file": str(args.source_file) if args.source_file else None,
        "source_sha256_before": (
            _sha256(args.source_file) if args.source_file else None
        ),
        "source_sha256_expected": source_input.protocol_file_sha256,
        "publishable": gate_result.publishable,
        "full_gate_issue_count": len(issues),
        "full_gate_issue_codes": [issue.issue_code for issue in issues],
        "manual_clinical_qc": {
            "status": "pending",
            "instruction": "必须逐条对照父条款原文、原子条件、资料要求和来源定位，不得以门控通过代替。",
        },
    }
    _write_json(args.output_dir / "summary.json", summary)
    return 0 if gate_result.publishable else 2


if __name__ == "__main__":
    raise SystemExit(main())
