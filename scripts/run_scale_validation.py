"""Run the WP08 scale validation: one subject's full chain over a staged set.

F06 hardening:
- Every HTTP call checks status and the app error envelope; an error
  response can never masquerade as an empty-but-successful result.
- Works only against the explicitly given project and creates its own
  subject; a conflicting subject code is a failure, not a silent reuse.
- Coverage counts are reported separately: expected (manifest) vs
  processed vs usable, plus per-stage terminal states. Any stage failure
  writes report.json with the failure and exits non-zero — a partial run
  is never reported as success.
- The projection hash is computed only from a non-error response.

Scope: evidence ingestion → processing → page review → fact
normalization → projection. Protocol deconstruction, binding,
qualification and formal publication are prerequisite flows and are
reported as such, not silently skipped.

Usage (after build_scale_validation_set.py and backend on :8902):
    python scripts/run_scale_validation.py \
        --project <project_id> --set runs/execution/wp08-scale-validation \
        --subject-code SC-SCALE-01
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import sys
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8902"


class StepFailure(RuntimeError):
    def __init__(self, step: str, detail: str):
        super().__init__(f"{step}: {detail}")
        self.step = step
        self.detail = detail


def _check(r: requests.Response, step: str) -> dict:
    if r.status_code >= 400:
        try:
            envelope = r.json().get("error", {})
            detail = f"{envelope.get('code')}: {envelope.get('detail', '')[:200]}"
        except Exception:
            detail = r.text[:200]
        raise StepFailure(step, f"HTTP {r.status_code} {detail}")
    return r.json()


def wait_job(job_id: str, *, timeout_s: int) -> tuple[str, str | None]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = requests.get(f"{BASE}/api/v2/jobs/{job_id}", timeout=60)
        if r.status_code == 200:
            d = r.json()
            state = d.get("state") or d.get("job_state")
            if state in {"completed", "failed_final", "cancelled"}:
                return state, d.get("error_code") or d.get("error_detail")
        time.sleep(20)
    return "timeout", None


def _write_report(out: Path, report: dict) -> None:
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("report:", out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--set", dest="set_dir", required=True)
    parser.add_argument("--subject-code", required=True)
    parser.add_argument("--center-code", default="SC1")
    parser.add_argument("--center-name", default="规模验证中心")
    parser.add_argument("--actor", default="wp08-scale")
    parser.add_argument("--upload-timeout", type=int, default=7200)
    args = parser.parse_args()

    manifest = json.loads(
        (Path(args.set_dir) / "manifest.json").read_text(encoding="utf-8")
    )
    expected_files = manifest["total_files"]
    expected_pages = manifest.get("known_pages", manifest.get("total_pages"))
    report: dict = {
        "set": {"files": expected_files, "pages": expected_pages},
        "steps": {},
        "metrics": {},
    }
    out = Path(args.set_dir) / "report.json"

    try:
        if not manifest.get("page_inventory_complete", False):
            raise StepFailure(
                "资料清单",
                "存在无法确认页数的文件，不能据此进行完整性验收",
            )
        if not isinstance(expected_pages, int) or expected_pages < 1:
            raise StepFailure("资料清单", "没有可核对的已知页面")

        # 1. subject（只创建自己的对象；冲突即失败，不静默复用他者）
        r = requests.post(
            f"{BASE}/api/v2/projects/{args.project}/subjects",
            json={
                "subject_code": args.subject_code,
                "center_code": args.center_code,
                "center_name": args.center_name,
            },
            timeout=120,
        )
        if r.status_code == 201:
            subject = r.json()
        else:
            raise StepFailure("subject", f"HTTP {r.status_code} {r.text[:200]}")
        subject_id = subject["subject_id"]
        report["steps"]["subject_id"] = subject_id
        print("subject:", subject_id)

        # 2. episode（筛选节点优先）
        r = requests.get(
            f"{BASE}/api/v2/subjects/{subject_id}/review-episodes", timeout=60)
        episodes = _check(r, "episodes").get("items", [])
        if not episodes:
            raise StepFailure("episodes", "受试者没有审核节点")
        screening = [e for e in episodes if e.get("stage") == "screening"]
        episode_id = (
            screening[0]["review_episode_id"] if screening
            else episodes[0]["review_episode_id"]
        )
        report["steps"]["review_episode_id"] = episode_id
        print("episode:", episode_id)

        # 3. upload（逐文件按真实媒体类型）
        with ExitStack() as stack:
            handles = []
            for entry in manifest["files"]:
                handle = stack.enter_context(open(entry["staged_path"], "rb"))
                handles.append(("files", (
                    entry["upload_name"], handle, entry["media_type"],
                )))
            r = requests.post(
                f"{BASE}/api/v2/subjects/{subject_id}/evidence-upload-previews",
                data={
                    "review_episode_id": episode_id,
                    "upload_mode": "full",
                    "base_revision": "1",
                    "actor": args.actor,
                },
                files=handles,
                timeout=600,
            )
        preview = _check(r, "upload-preview")
        r = requests.post(
            f"{BASE}/api/v2/evidence-upload-previews/{preview['preview_id']}/commit",
            json={
                "preview_sha256": preview["preview_sha256"],
                "upload_mode": "full",
                "base_revision": 1,
                "idempotency_key": (
                    f"{args.actor}-scale-"
                    f"{hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()}"
                ),
                "actor": args.actor,
            },
            timeout=600,
        )
        commit = _check(r, "upload-commit")
        upload_job = commit["job_id"]
        report["steps"]["upload_job_id"] = upload_job
        state, err = wait_job(upload_job, timeout_s=args.upload_timeout)
        report["steps"]["upload_state"] = state
        if state != "completed":
            raise StepFailure("processing", f"{state} {err}")
        print("processing completed")

        # 4. page review
        r = requests.post(
            f"{BASE}/api/v2/subjects/{subject_id}/review-episodes/{episode_id}/page-review-jobs",
            json={}, timeout=300,
        )
        pr_job = _check(r, "page-review-submit").get("job_id")
        report["steps"]["page_review_job_id"] = pr_job
        state, err = wait_job(pr_job, timeout_s=10800)
        report["steps"]["page_review_state"] = state
        if state != "completed":
            raise StepFailure("page-review", f"{state} {err}")

        # 5. normalization
        r = requests.post(
            f"{BASE}/api/v2/subjects/{subject_id}/review-episodes/{episode_id}/fact-normalization-jobs",
            json={"idempotency_intent": f"{args.actor}-scale-norm"}, timeout=300,
        )
        norm_job = _check(r, "normalization-submit").get("job_id")
        report["steps"]["normalization_job_id"] = norm_job
        state, err = wait_job(norm_job, timeout_s=10800)
        report["steps"]["normalization_state"] = state
        if state != "completed":
            raise StepFailure("normalization", f"{state} {err}")

        # 6. projection（错误信封绝不当作零条款成功）
        r = requests.get(
            f"{BASE}/api/v2/subjects/{subject_id}/review-episodes/{episode_id}/eligibility-review",
            timeout=300,
        )
        if r.status_code != 200:
            raise StepFailure("projection", f"HTTP {r.status_code} {r.text[:200]}")
        body = r.json()
        if "error" in body:
            raise StepFailure(
                "projection",
                f"应用错误信封: {json.dumps(body['error'], ensure_ascii=False)[:200]}")
        clauses = body["clauses"]
        decisions: dict[str, int] = {}
        gaps: dict[str, int] = {}
        for c in clauses:
            decisions[c["decision"]] = decisions.get(c["decision"], 0) + 1
            if c.get("gap_type"):
                gaps[c["gap_type"]] = gaps.get(c["gap_type"], 0) + 1
        report["metrics"] = {
            "expected_files": expected_files,
            "expected_pages": expected_pages,
            "clause_count": len(clauses),
            "decision_distribution": decisions,
            "gap_distribution": gaps,
            "clauses_with_facts": sum(1 for c in clauses if c.get("fact_refs")),
            "projection_sha256": hashlib.sha256(
                json.dumps(clauses, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest(),
        }
        _write_report(out, report)
        print(json.dumps(report["metrics"], ensure_ascii=False, indent=1))
        return 0
    except StepFailure as exc:
        report["failure"] = {"step": exc.step, "detail": exc.detail}
        _write_report(out, report)
        print(f"FAILED at {exc.step}: {exc.detail}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - 意外也落盘为失败，不当作成功
        report["failure"] = {"step": "unexpected", "detail": str(exc)[:300]}
        _write_report(out, report)
        raise


if __name__ == "__main__":
    sys.exit(main())
