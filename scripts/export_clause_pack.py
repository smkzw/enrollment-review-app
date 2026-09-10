#!/usr/bin/env python3
"""Export one published RuleSet as a Phase 5.5 ClausePack baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from app.domain.contracts.rules import RuleSet
from app.projections.clause_pack import project_clause_pack, verify_clause_pack


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--rule-set-id")
    parser.add_argument("--revision", type=int)
    return parser.parse_args()


def _load_rule_set(
    database: Path, rule_set_id: str | None, revision: int | None
) -> tuple[RuleSet, str]:
    query = "SELECT payload_json, payload_sha256 FROM rule_sets"
    where: list[str] = []
    parameters: list[object] = []
    if rule_set_id:
        where.append("rule_set_id = ?")
        parameters.append(rule_set_id)
    if revision is not None:
        where.append("revision = ?")
        parameters.append(revision)
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY revision DESC"
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute(query, parameters).fetchall()
    if len(rows) != 1:
        raise SystemExit(f"需要唯一已发布规则集，实际找到 {len(rows)} 条")
    payload_json, stored_sha256 = rows[0]
    actual_sha256 = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    if actual_sha256 != stored_sha256:
        raise SystemExit("已发布规则集载荷哈希不一致")
    return RuleSet.model_validate_json(payload_json), stored_sha256


def main() -> None:
    args = _args()
    rule_set, source_sha256 = _load_rule_set(
        args.database, args.rule_set_id, args.revision
    )
    clause_pack = project_clause_pack(rule_set)
    verify_clause_pack(clause_pack)

    args.output.mkdir(parents=True, exist_ok=True)
    pack_path = args.output / f"{args.label}.clause-pack.json"
    pack_path.write_text(
        json.dumps(clause_pack.model_dump(mode="json"), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )

    codes = sorted({clause.official_code for clause in clause_pack.clauses})
    comparison: dict[str, object] = {
        "label": args.label,
        "authority": "published_rule_set",
        "rule_set_id": rule_set.rule_set_id,
        "rule_set_revision": rule_set.revision,
        "source_payload_sha256": source_sha256,
        "clause_pack_sha256": clause_pack.clause_pack_sha256,
        "published_rule_count": len(rule_set.rules),
        "published_component_count": len(clause_pack.clauses),
        "published_official_codes": codes,
    }
    if args.benchmark:
        benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
        benchmark_codes = sorted({str(item["id"]) for item in benchmark["clauses"]})
        comparison.update(
            benchmark_role="reference_not_authority",
            benchmark_clause_count=len(benchmark["clauses"]),
            benchmark_official_codes=benchmark_codes,
            missing_from_published=sorted(set(benchmark_codes) - set(codes)),
            additional_in_published=sorted(set(codes) - set(benchmark_codes)),
        )
    comparison_path = args.output / f"{args.label}.comparison.json"
    comparison_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(pack_path)
    print(comparison_path)


if __name__ == "__main__":
    main()
