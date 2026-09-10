"""Inventory retained reader attempts without inferring clinical acceptance or prices."""

import argparse
import csv
import json
from pathlib import Path


def usage_value(usage, *keys):
    for key in keys:
        if usage.get(key) is not None:
            return usage[key]
    return None


def collect(root, pattern="product-runs*/*/receipts.json"):
    rows = []
    for receipt_path in sorted(root.glob(pattern)):
        directory = receipt_path.parent
        status_path = directory / "status.json"
        state = json.loads(status_path.read_text()) if status_path.exists() else {}
        result_path = directory / "result.json"
        if result_path.exists():
            state = json.loads(result_path.read_text())
        contract_path = directory / "transport-contract.json"
        contract = json.loads(contract_path.read_text()) if contract_path.exists() else {}
        for index, receipt in enumerate(json.loads(receipt_path.read_text())):
            usage = receipt.get("usage") or {}
            details = usage.get("output_tokens_details") or usage.get("completion_tokens_details") or {}
            prompt_details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
            transport_path = directory / f"transport-{index}.json"
            transport = json.loads(transport_path.read_text()) if transport_path.exists() else {}
            request_path = directory / f"request-{index}.json"
            request = json.loads(request_path.read_text()) if request_path.exists() else {}
            disagreement = (
                usage.get("completion_tokens") is not None
                and usage.get("output_tokens") is not None
                and usage["completion_tokens"] != usage["output_tokens"]
            )
            rows.append({
                "run": str(directory.relative_to(root)),
                "attempt": index,
                "requested_model": receipt.get("model") or receipt.get("requested_model"),
                "response_model": receipt.get("response_model"),
                "requested_effort": receipt.get("effort") or receipt.get("reasoning_effort"),
                "requested_budget": request.get("budget", request.get("max_tokens")),
                "transport_contract": contract.get("kind"),
                "formal_transport_comparison": contract.get("formal_transport_comparison"),
                "output_budget_enforced": transport.get("output_budget_enforced", receipt.get("output_budget_enforced")),
                "reader_state": state.get("state", state.get("status", "pending")),
                "failure_kind": state.get("failure_kind"),
                "finish_reason": receipt.get("finish_reason"),
                "elapsed_seconds": receipt.get("elapsed_seconds"),
                "input_tokens": usage_value(usage, "prompt_tokens", "input_tokens", "promptTokenCount"),
                "output_tokens_reported": usage_value(usage, "completion_tokens", "output_tokens", "candidatesTokenCount"),
                "reasoning_tokens_reported": usage_value(details, "reasoning_tokens") if details else usage.get("thoughtsTokenCount"),
                "cached_tokens": usage_value(prompt_details, "cached_tokens") if prompt_details else usage.get("cachedContentTokenCount"),
                "output_usage_disagreement": disagreement,
                "clinical_acceptance": False,
                "api_cost": None,
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--normalizers", action="store_true")
    args = parser.parse_args()
    rows = collect(args.root, "normalizer*-runs/*/receipts.json" if args.normalizers else "product-runs*/*/receipts.json")
    output = args.root / ("normalizer-attempts.csv" if args.normalizers else "reader-attempts.csv")
    if rows:
        with output.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps({"attempts": len(rows), "output": str(output), "clinical_acceptance": False}))


if __name__ == "__main__":
    main()
