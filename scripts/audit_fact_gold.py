"""Read-only fact-gold inventory; never interprets free-text adjudications."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import openpyxl


def audit(path, reviews_dir=None):
    review_index = {}
    if reviews_dir is not None:
        for source in sorted(Path(reviews_dir).glob("*.json")):
            raw = source.read_bytes()
            review = json.loads(raw)
            for fact in review.get("facts", []):
                key = (fact.get("page_id"), fact.get("field"), str(fact.get("value")))
                review_index.setdefault(key, []).append({
                    "review_file": source.name, "review_sha256": hashlib.sha256(raw).hexdigest(),
                    "subject": review.get("subject"), "verdict": fact.get("verdict"),
                    "has_excerpt": bool(fact.get("excerpt")),
                    "uncertain": bool(fact.get("uncertain")),
                })
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = workbook["关键事实金标"].iter_rows(values_only=True)
        headers = next(rows)
        if len(set(headers)) != len(headers):
            raise ValueError("Duplicate fact-sheet headers")
        counts = Counter()
        issues = []
        for number, cells in enumerate(rows, 2):
            if not any(value is not None for value in cells):
                continue
            row = dict(zip(headers, cells))
            decision = row.get("GT裁决(保留/修正/删除/新增)")
            counts[decision] += 1
            reasons = []
            if decision not in {"保留", "修正", "删除", "新增"}:
                reasons.append("unstructured_decision")
            if decision != "删除":
                for field in ("page_id", "subject", "field", "value", "excerpt"):
                    value = row.get(field)
                    if value is None or isinstance(value, str) and not value.strip():
                        reasons.append("missing_" + field)
            if reasons:
                issue = {"sheet_row": number, "reasons": reasons}
                if reviews_dir is not None:
                    key = (row.get("page_id"), row.get("field"), str(row.get("value")))
                    issue["review_candidates"] = review_index.get(key, [])
                issues.append(issue)
        return {"source_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                "total_rows": sum(counts.values()), "decision_counts": dict(counts),
                "explicit_retained_rows": sum(counts[key] for key in ("保留", "修正", "新增")),
                "historical_non_deleted_rows": sum(counts.values()) - counts["删除"],
                "issues": issues, "clinical_acceptance": False}
    finally:
        workbook.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--reviews-dir")
    args = parser.parse_args()
    result = audit(args.source, args.reviews_dir)
    with Path(args.output).open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: value for key, value in result.items() if key not in {"issues", "decision_counts"}}, ensure_ascii=False))
