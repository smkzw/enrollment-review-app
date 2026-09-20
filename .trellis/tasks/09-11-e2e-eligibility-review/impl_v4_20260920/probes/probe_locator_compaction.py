#!/usr/bin/env python3
"""Offline locator compaction probe. No app imports, network, or clinical data.

Default: executes a behavior-preserving function excerpt (not full-module test).
--repo: extracts the named function from the current source AST, strips annotations
       and executes only that function. If its dependencies changed, reports error;
       never modifies the repository to make the probe run.
"""
from __future__ import annotations
import argparse, ast, hashlib, json
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Locator:
    locator_id: str
    localized_text: str
    source_layer: str = "raw_ocr"
    source_text_sha256: str = "a" * 64

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    path = (args.repo / "app/services/fact_normalization_source_adapter.py" if args.repo
            else Path(__file__).with_name("compact_locator_extract.py"))
    source = path.read_text(encoding="utf8")
    root = ast.parse(source)
    node = next((n for n in root.body if isinstance(n, ast.FunctionDef)
                 and n.name == "_compact_locator_inputs"), None)
    if node is None:
        raise SystemExit("Named function not found; inspect the current implementation.")
    node.returns = None
    for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
        arg.annotation = None
    for n in ast.walk(node):
        if isinstance(n, ast.AnnAssign):
            n.annotation = ast.Name(id="object", ctx=ast.Load())
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    scope: dict = {}
    exec(compile(module, str(path), "exec"), scope)
    function = scope["_compact_locator_inputs"]
    cases = [
        ("same_text_different_occurrences", [Locator("a-row", "阴性"), Locator("b-row", "阴性")], ["a-row", "b-row"]),
        ("text_containment_is_not_geometry", [Locator("a-cell", "阴性"), Locator("b-unrelated-row", "另一项目：阴性")], ["a-cell", "b-unrelated-row"]),
        ("different_source_hashes", [Locator("a-row", "阴性"), Locator("b-row", "阴性", source_text_sha256="b"*64)], ["a-row", "b-row"]),
    ]
    result = {"baseline_commit": "60f5bb8fe67ac14d44af9ceab0801a9b2a42120b",
              "mode": "current_function_ast" if args.repo else "behavioral_excerpt",
              "source_path": str(path), "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
              "scope": "helper only; does not establish final clinical misclassification", "cases": []}
    for name, inputs, expected in cases:
        observed = [x.locator_id for x in function(inputs)]
        result["cases"].append({"name": name, "input_locator_ids": [x.locator_id for x in inputs],
                                 "observed_output_ids": observed, "expected_occurrence_preserving_ids": expected,
                                 "preserves_distinct_occurrences": observed == expected})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
if __name__ == "__main__":
    main()
