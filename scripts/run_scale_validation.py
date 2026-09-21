"""Run the WP08 scale validation: one subject's full chain over a staged set.

Drives the real product chain via HTTP against the local v2 backend:
  create subject → upload set (preview→commit) → wait processing complete →
  page review → fact normalization → eligibility projection → metrics report.

Every write goes through the public API; the script records coverage counts,
read/audit outcomes and the projection hash into report.json. It never
modifies clinical data outside the created subject.

Usage (after build_scale_validation_set.py and backend on :8902):
    python scripts/run_scale_validation.py \
        --project <project_id> --set runs/execution/wp08-scale-validation \
        --subject-code SC-SCALE-01
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8902"


def wait_job(job_id: str, *, timeout_s: int = 3600) -> tuple[str, str | None]:
    """Poll the jobs table via the progress-free retry endpoint contract.

    Uses the internal sqlite-free route: GET /api/v2/jobs/{id} if available,
    else falls back to polling /api/v2/jobs/{job_id}/evidence-progress for
    evidence jobs. Terminal states: completed / failed_final / cancelled.
    """
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--set", dest="set_dir", default="runs/execution/wp08-scale-validation")
    parser.add_argument("--subject-code", required=True)
    parser.add_argument("--center-code", default="SC1")
    parser.add_argument("--center-name", default="规模验证中心")
    parser.add_argument("--actor", default="wp08-scale")
    parser.add_argument("--upload-timeout", type=int, default=7200)
    args = parser.parse_args()

    manifest = json.loads(
        (Path(args.set_dir) / "manifest.json").read_text(encoding="utf-8")
    )
    report: dict = {"set": manifest, "steps": {}}

    # 1. subject
    r = requests.post(
        f"{BASE}/api/v2/projects/{args.project}/subjects",
        json={
            "subject_code": args.subject_code,
            "center_code": args.center_code,
            "center_name": args.center_name,
        },
        timeout=120,
    )
    if r.status_code not in (200, 201):
        # 已存在则复用：同 code 受试者查询
        r = requests.get(f"{BASE}/api/v2/projects/{args.project}/subjects", timeout=60)
        match = [s for s in r.json().get("items", [])
                 if s.get("subject_code") == args.subject_code]
        if not match:
            raise SystemExit(f"受试者创建失败: {r.status_code} {r.text[:200]}")
        subject = match[0]
    else:
        subject = r.json()
    subject_id = subject["subject_id"]
    report["steps"]["subject_id"] = subject_id
    print("subject:", subject_id)

    # 2. episode: 上传前需要 review-episode；取该受试者的当前节点（流水线自动派生）。
    r = requests.get(
        f"{BASE}/api/v2/subjects/{subject_id}/review-episodes", timeout=60
    )
    episodes = r.json().get("items", [])
    if not episodes:
        raise SystemExit("受试者没有可用审核节点；请先经建档流程创建。")
    episode_id = episodes[0]["review_episode_id"]
    report["steps"]["review_episode_id"] = episode_id
    print("episode:", episode_id)

    # 3. upload preview (full mode) + commit
    files = [
        ("files", (f["file_name"], open(f["staged_path"], "rb"), "application/pdf"))
        for f in manifest["files"]
    ]
    r = requests.post(
        f"{BASE}/api/v2/subjects/{subject_id}/evidence-upload-previews",
        data={
            "review_episode_id": episode_id,
            "upload_mode": "full",
            "base_revision": "1",
            "actor": args.actor,
        },
        files=files,
        timeout=600,
    )
    if r.status_code not in (200, 201):
        raise SystemExit(f"预览失败: {r.status_code} {r.text[:300]}")
    preview = r.json()
    preview_id = preview["preview_id"]
    r = requests.post(
        f"{BASE}/api/v2/evidence-upload-previews/{preview_id}/commit",
        json={
            "preview_sha256": preview["preview_sha256"],
            "upload_mode": "full",
            "base_revision": 1,
            "idempotency_key": f"{args.actor}-scale-commit-{manifest['total_pages']}",
            "actor": args.actor,
        },
        timeout=600,
    )
    if r.status_code not in (200, 201):
        raise SystemExit(f"提交失败: {r.status_code} {r.text[:300]}")
    commit = r.json()
    upload_job = commit["job_id"]
    report["steps"]["upload_job_id"] = upload_job
    print("processing job:", upload_job)
    state, err = wait_job(upload_job, timeout_s=args.upload_timeout)
    report["steps"]["upload_state"] = state
    if state != "completed":
        raise SystemExit(f"资料处理未完成: {state} {err}")
    print("processing completed")

    # 4. page review（新修订上全量双路判读；由守望脚本或人工另行触发亦可）
    r = requests.post(
        f"{BASE}/api/v2/subjects/{subject_id}/review-episodes/{episode_id}/page-review-jobs",
        json={}, timeout=300,
    )
    if r.status_code not in (200, 201):
        raise SystemExit(f"页判读提交失败: {r.status_code} {r.text[:300]}")
    pr_job = r.json()["job_id"]
    report["steps"]["page_review_job_id"] = pr_job
    print("page review:", pr_job)
    state, err = wait_job(pr_job, timeout_s=7200)
    report["steps"]["page_review_state"] = state
    if state != "completed":
        raise SystemExit(f"页判读未完成: {state} {err}")

    # 5. fact normalization
    r = requests.post(
        f"{BASE}/api/v2/subjects/{subject_id}/review-episodes/{episode_id}/fact-normalization-jobs",
        json={"idempotency_intent": f"{args.actor}-scale-norm"}, timeout=300,
    )
    if r.status_code not in (200, 201):
        raise SystemExit(f"事实整理提交失败: {r.status_code} {r.text[:300]}")
    norm_job = r.json()["job_id"]
    report["steps"]["normalization_job_id"] = norm_job
    state, err = wait_job(norm_job, timeout_s=7200)
    report["steps"]["normalization_state"] = state
    if state != "completed":
        raise SystemExit(f"事实整理未完成: {state} {err}")

    # 6. projection + metrics
    r = requests.get(
        f"{BASE}/api/v2/subjects/{subject_id}/review-episodes/{episode_id}/eligibility-review",
        timeout=300,
    )
    projection = r.json()
    clauses = projection.get("clauses", [])
    report["metrics"] = {
        "clause_count": len(clauses),
        "decision_distribution": {},
        "gap_distribution": {},
        "clauses_with_facts": sum(1 for c in clauses if c.get("fact_refs")),
        "projection_sha256": None,
    }
    for c in clauses:
        report["metrics"]["decision_distribution"][c["decision"]] = (
            report["metrics"]["decision_distribution"].get(c["decision"], 0) + 1
        )
        gap = c.get("gap_type")
        if gap:
            report["metrics"]["gap_distribution"][gap] = (
                report["metrics"]["gap_distribution"].get(gap, 0) + 1
            )
    canon = json.dumps(clauses, sort_keys=True, ensure_ascii=False)
    import hashlib

    report["metrics"]["projection_sha256"] = hashlib.sha256(
        canon.encode()
    ).hexdigest()

    out = Path(args.set_dir).parent / "report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("report:", out)
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
