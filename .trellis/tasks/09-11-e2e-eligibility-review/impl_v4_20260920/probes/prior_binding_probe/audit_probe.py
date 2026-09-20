#!/usr/bin/env python3
"""Read-only, network-free audit of candidate transport control flow.

Default: execute the bundled verbatim source extract with synthetic completions.
--repo /path/to/worktree: AST-extract the same definitions from local source,
without importing app, loading .env, opening a database, or invoking a model.
This is a narrow control-flow probe, NOT the repository test suite and NOT
clinical or end-to-end validation. It does not modify the worktree.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

BASELINE = "60f5bb8fe67ac14d44af9ceab0801a9b2a42120b"
SOURCE_PATH = Path("app/llm/predicate_binding_candidates.py")


async def never_send(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("This audit must not invoke a model endpoint")


def load_probe(repo: Path | None):
    if repo:
        source_path = repo.resolve() / SOURCE_PATH
        capability_path = repo.resolve() / "app/llm/page_reader_capabilities.py"
        source = source_path.read_text(encoding="utf-8")
        cap_tree = ast.parse(capability_path.read_text(encoding="utf-8"))
        maximum = None
        for node in cap_tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "MAX_SEMANTIC_OUTPUT_TOKENS"
                for t in node.targets
            ):
                maximum = ast.literal_eval(node.value)
        if not isinstance(maximum, int):
            raise ValueError("Cannot statically read MAX_SEMANTIC_OUTPUT_TOKENS")
        mode = "worktree_ast_extract"
    else:
        source_path = Path(__file__).parent / "source_extracts/predicate_binding_candidates_extract.py"
        source = source_path.read_text(encoding="utf-8")
        maximum = 262144
        mode = "bundled_baseline_source_extract"
    names = {"PredicateCandidateReadError", "read_candidate_payload"}
    selected = [n for n in ast.parse(source).body if isinstance(
        n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    if {n.name for n in selected} != names:
        raise ValueError("Expected source definitions have changed; inspect before adapting the probe")
    module = ast.Module(body=[ast.ImportFrom(module="__future__",
        names=[ast.alias(name="annotations")], level=0), *selected], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "asyncio": asyncio,
        "direct_completion": never_send,
        "MAX_SEMANTIC_OUTPUT_TOKENS": maximum,
        "_status_code": lambda exc: getattr(exc, "status_code", None),
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace, {
        "mode": mode,
        "review_baseline": BASELINE,
        "source_path": str(source_path),
        "read_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "global_maximum": maximum,
        "limitations": [
            "No application imports, database, clinical data, or live model calls",
            "No repository pytest suite, frontend, or end-to-end execution",
            "Acceptance here means payload-helper acceptance, not clinical publication",
        ],
    }


async def probe(namespace: dict[str, Any]) -> list[dict[str, Any]]:
    read = namespace["read_candidate_payload"]
    error_type = namespace["PredicateCandidateReadError"]
    reports = []
    for initial in (65536, 131072, 262144):
        sent = []
        async def always_length(route, messages, budget):
            sent.append(budget)
            return SimpleNamespace(finish_reason="length", response_model="synthetic-reader", text="{}", usage={})
        try:
            await read(SimpleNamespace(max_tokens=initial, model="requested-reader"), [],
                       validate=json.loads, completion=always_length)
            error = None
        except error_type as exc:
            error = str(exc)
        reports.append({"case": "length_budget_path", "initial_budget": initial,
            "sent_budgets": sent, "error": error,
            "reached_global_maximum": namespace["MAX_SEMANTIC_OUTPUT_TOKENS"] in sent})
    async def mismatched_model(route, messages, budget):
        return SimpleNamespace(finish_reason="stop", response_model="different-returned-reader", text="{}", usage={})
    try:
        result = await read(SimpleNamespace(max_tokens=65536, model="requested-reader"), [],
                            validate=json.loads, completion=mismatched_model)
        accepted = True
        actual = result[1][-1].response_model
        error = None
    except error_type as exc:
        accepted, actual, error = False, "different-returned-reader", str(exc)
    reports.append({"case": "response_model_mismatch", "requested_model": "requested-reader",
        "response_model": actual, "helper_accepted_payload": accepted, "error": error,
        "not_a_clinical_publication_test": True})
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        namespace, result = load_probe(args.repo)
        result["observations"] = asyncio.run(probe(namespace))
    except (OSError, ValueError, SyntaxError, NameError) as exc:
        parser.exit(2, f"Audit could not complete: {type(exc).__name__}: {exc}\n")
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        output = args.out.resolve()
        if args.repo and (output == args.repo.resolve() or args.repo.resolve() in output.parents):
            parser.exit(2, "Write the audit output outside the source worktree.\n")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
