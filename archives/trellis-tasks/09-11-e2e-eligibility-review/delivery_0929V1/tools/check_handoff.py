#!/usr/bin/env python3
"""Read-only, standard-library check of the review index, not clinical validation.

Does not read referenced files, run commands, contact GitHub, scan for PHI, or
certify the content of any evidence. Additional descriptive fields are allowed.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any

SHA40 = re.compile(r"[0-9a-f]{40}")
SHA64 = re.compile(r"[0-9a-f]{64}")
ACCESS = {"reviewer_accessible", "local_only", "missing", "not_provided"}


def one_of(value: Any, allowed: set[str]) -> bool:
    return isinstance(value, str) and value in allowed


def has_id(value: Any, index: dict) -> bool:
    return isinstance(value, str) and value in index


def validate(data: Any, *, allow_template: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ["Top level must be a JSON object."], warnings
    if data.get("schema_version") != "review-index/0929v1/v1":
        errors.append("Unsupported or missing schema_version.")
    kind = data.get("document_kind")
    if not one_of(kind, {"template", "handoff"}):
        errors.append("document_kind must be template or handoff.")
    if kind == "template":
        if not allow_template:
            errors.append("Unfilled template is not a handoff; fill it or use --allow-template for structure only.")
        warnings.append("TEMPLATE ONLY: no real execution or evidence is asserted.")
    for field in ("round_id", "task_path", "execution_variant"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            errors.append(f"{field} must be a nonempty string.")
    if not isinstance(data.get("base_review_commit"), str) or not SHA40.fullmatch(data["base_review_commit"]):
        errors.append("base_review_commit must be a 40-character lowercase SHA.")
    if type(data.get("product_claims_complete")) is not bool:
        errors.append("product_claims_complete must be explicitly true or false.")
    if data.get("product_claims_complete") is True:
        warnings.append("Product completion is NOT certified by this checker; independently review R1 acceptance and authorization.")
    if kind == "handoff":
        try:
            timestamp = datetime.fromisoformat(data["recorded_at"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("timezone missing")
        except (KeyError, TypeError, AttributeError, ValueError):
            errors.append("recorded_at must be an ISO8601 timestamp with timezone.")

    arrays: dict[str, list[dict[str, Any]]] = {}
    indexes: dict[str, dict[str, dict[str, Any]]] = {}
    names = ("code_snapshots", "changes", "claims", "tests", "artifacts", "hypotheses", "recommendations", "next_actions")
    for name in names:
        value = data.get(name)
        if not isinstance(value, list):
            errors.append(f"{name} must be an array.")
            value = []
        rows: list[dict[str, Any]] = []
        table: dict[str, dict[str, Any]] = {}
        for pos, row in enumerate(value):
            if not isinstance(row, dict):
                errors.append(f"{name}[{pos}] must be an object.")
                continue
            identifier = row.get("id")
            if not isinstance(identifier, str) or not identifier.strip():
                errors.append(f"{name}[{pos}] needs a nonempty id.")
                continue
            if identifier in table:
                errors.append(f"Duplicate id {identifier} in {name}.")
            table[identifier] = row
            rows.append(row)
        arrays[name], indexes[name] = rows, table

    def refs(row: dict[str, Any], key: str, target: str, label: str) -> list[str]:
        value = row.get(key, [])
        if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
            errors.append(f"{label}.{key} must be an array of ids.")
            return []
        if len(set(value)) != len(value):
            errors.append(f"{label}.{key} contains duplicate references.")
        for ref in value:
            if ref not in indexes[target]:
                errors.append(f"{label}.{key} references missing {target} id {ref}.")
        return value

    for row in arrays["artifacts"]:
        ident = row["id"]
        if not one_of(row.get("access"), ACCESS):
            errors.append(f"{ident}: invalid artifact access level.")
        if not one_of(row.get("sensitivity"), {"public_technical", "redacted", "restricted_source"}):
            errors.append(f"{ident}: invalid artifact sensitivity.")
        if row.get("access") == "reviewer_accessible" and row.get("sensitivity") == "restricted_source":
            errors.append(f"{ident}: restricted source must not be declared in the ordinary shareable review package.")
        digest = row.get("sha256")
        if digest is not None and (not isinstance(digest, str) or not SHA64.fullmatch(digest)):
            errors.append(f"{ident}: sha256 must be null or 64 lowercase hex characters.")
        if one_of(row.get("access"), {"reviewer_accessible", "local_only"}) and not row.get("path"):
            errors.append(f"{ident}: accessible/local evidence needs an actual path or controlled alias.")
        if row.get("access") != "reviewer_accessible":
            warnings.append(f"{ident}: evidence is {row.get('access')}; no external verification implied.")

    for row in arrays["code_snapshots"]:
        ident = row["id"]
        if not one_of(row.get("kind"), {"commit", "working_tree"}):
            errors.append(f"{ident}: snapshot kind must be commit or working_tree.")
        if not isinstance(row.get("base_commit"), str) or not SHA40.fullmatch(row["base_commit"]):
            errors.append(f"{ident}: base_commit must be a 40-character lowercase SHA.")
        if not one_of(row.get("access"), ACCESS):
            errors.append(f"{ident}: invalid code access level.")
        if row.get("kind") == "working_tree":
            artifact_id = row.get("manifest_artifact_id")
            if not isinstance(artifact_id, str) or artifact_id not in indexes["artifacts"]:
                errors.append(f"{ident}: working-tree snapshot needs an indexed code manifest artifact.")
    if kind == "handoff" and not has_id(data.get("delivered_snapshot_id"), indexes["code_snapshots"]):
        errors.append("delivered_snapshot_id must reference an actual code snapshot.")

    for row in arrays["changes"]:
        ident = row["id"]
        if not one_of(row.get("delivery_state"), {"committed", "patch_attached", "local_only", "planned"}):
            errors.append(f"{ident}: invalid delivery_state.")
        if not isinstance(row.get("paths"), list) or not row["paths"]:
            errors.append(f"{ident}: list the changed paths.")
        refs(row, "evidence_ids", "artifacts", ident)

    for row in arrays["tests"]:
        ident, status = row["id"], row.get("status")
        if not one_of(status, {"passed", "failed", "interrupted", "blocked", "not_run"}):
            errors.append(f"{ident}: invalid test status.")
        execution_kind = row.get("execution_kind", "command")
        if not one_of(execution_kind, {"command", "product_entry"}):
            errors.append(f"{ident}: execution_kind must be command or product_entry.")
        executed = one_of(status, {"passed", "failed", "interrupted"})
        if executed and not has_id(row.get("snapshot_id"), indexes["code_snapshots"]):
            errors.append(f"{ident}: executed test needs its actual code snapshot.")
        if executed and (not isinstance(row.get("command"), str) or not row["command"].strip()):
            errors.append(f"{ident}: executed test needs its command or exact product entry.")
        evidence = refs(row, "evidence_ids", "artifacts", ident)
        if executed and not evidence:
            errors.append(f"{ident}: executed test needs an indexed result artifact.")
        if status == "passed" and execution_kind == "command" and (type(row.get("exit_code")) is not int or row["exit_code"] != 0):
            errors.append(f"{ident}: passed command requires its actual exit_code 0.")
        if executed and execution_kind == "product_entry":
            if row.get("exit_code") is not None:
                errors.append(f"{ident}: product entry has no invented process exit code; use null.")
            if not row.get("expected_result") or not row.get("actual_result"):
                errors.append(f"{ident}: product entry needs its expected and observed result, not just HTTP200.")
        if one_of(status, {"blocked", "not_run"}) and row.get("exit_code") is not None:
            errors.append(f"{ident}: unexecuted test must not have an exit code.")
        counts = row.get("counts", {})
        if not isinstance(counts, dict):
            errors.append(f"{ident}: counts must be an object; unknown values are null.")
            counts = {}
        for count_name in ("passed", "failed", "skipped"):
            value = counts.get(count_name)
            if value is not None and (type(value) is not int or value < 0):
                errors.append(f"{ident}: {count_name} count must be a nonnegative integer or null.")
        if status == "passed" and isinstance(counts.get("failed"), int) and counts["failed"] > 0:
            errors.append(f"{ident}: cannot report passed with failing tests.")

    for row in arrays["claims"]:
        ident, status = row["id"], row.get("status")
        if not one_of(status, {"static_observation", "reproduced", "verified", "author_report", "unverified", "refuted"}):
            errors.append(f"{ident}: invalid claim status.")
        evidence = refs(row, "evidence_ids", "artifacts", ident)
        tests = refs(row, "test_ids", "tests", ident)
        if not row.get("statement") or not row.get("limitations"):
            errors.append(f"{ident}: state the claim and its limitations.")
        if one_of(status, {"static_observation", "reproduced", "verified", "refuted"}) and not evidence:
            errors.append(f"{ident}: supported claim requires explicit evidence ids.")
        if one_of(status, {"reproduced", "verified"}):
            if not tests:
                errors.append(f"{ident}: reproduced/verified requires executed test references, not only prose.")
            if not has_id(row.get("snapshot_id"), indexes["code_snapshots"]):
                errors.append(f"{ident}: reproduced/verified needs the code snapshot it actually concerns.")
            for test_id in tests:
                test = indexes["tests"].get(test_id, {})
                if one_of(test.get("status"), {"not_run", "blocked"}):
                    errors.append(f"{ident}: unexecuted test {test_id} cannot support reproduced/verified.")
                if test.get("snapshot_id") != row.get("snapshot_id"):
                    errors.append(f"{ident}: claim and test {test_id} refer to different code snapshots.")
                if status == "verified" and test.get("status") != "passed":
                    errors.append(f"{ident}: verified success cannot be based on non-passing test {test_id}.")
        if evidence and not any(indexes["artifacts"].get(e, {}).get("access") == "reviewer_accessible" for e in evidence):
            warnings.append(f"{ident}: supporting evidence is not currently accessible to the reviewer.")

    for row in arrays["hypotheses"]:
        ident = row["id"]
        refs(row, "support_evidence_ids", "artifacts", ident)
        refs(row, "counter_evidence_ids", "artifacts", ident)
        if not isinstance(row.get("alternatives"), list) or not row["alternatives"]:
            errors.append(f"{ident}: list a plausible alternative, or explicitly explain why unavailable.")
        if not row.get("disconfirming_test"):
            errors.append(f"{ident}: specify what evidence could change the judgment.")
    for row in arrays["recommendations"]:
        if not one_of(row.get("decision_status"), {"approved", "proposed", "rejected"}):
            errors.append(f"{row['id']}: distinguish approved decisions from proposals.")
        for key in ("proposal", "basis", "risk", "validation"):
            if not row.get(key):
                errors.append(f"{row['id']}: missing recommendation {key}.")
    if len(arrays["next_actions"]) > 3:
        warnings.append("More than three next_actions: reduce the handoff to the immediate choices, without deleting backlog evidence.")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--allow-template", action="store_true")
    args = parser.parse_args()
    try:
        data = json.loads(args.index.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid_input", "error": str(exc)}, ensure_ascii=False))
        return 2
    errors, warnings = validate(data, allow_template=args.allow_template)
    print(json.dumps({
        "status": "index_structure_ok" if not errors else "index_structure_invalid",
        "errors": errors, "warnings": warnings,
        "scope": "Index consistency only; not proof of source fidelity, code execution, access, redaction, or clinical correctness.",
    }, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
