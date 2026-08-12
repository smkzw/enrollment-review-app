#!/usr/bin/env python3
"""Rerun MG-K10-SAR-III center-31 enrollment review through the HTTP API.

This script intentionally uses the public local FastAPI endpoints for upload
and processing so it exercises the same path as the browser UI:

1. parse/check protocol workflow metadata;
2. optionally back up and recreate the phase-scoped project from the protocol;
3. create center-31 subjects;
4. upload source files in progressive batches;
5. process screening and baseline review phases with study_stage=Ⅲ期;
6. persist a run log and an append-only audit ledger.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import shutil
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PROJECT_CODE = "MG-K10-SAR-III"
STUDY_STAGE = "Ⅲ期"
CENTER_CODE = "31"
CENTER_NAME = "河北省中医院"
DEFAULT_BASE_URL = "http://127.0.0.1:8900"
SOURCE_ROOT = Path(
    "/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/13. CFDI核查/自查/入排/各中心原始入排资料"
)
PROTOCOL_DOCX = Path(
    "/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/"
    "MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx"
)
PROJECT_DIR = ROOT / "projects" / PROJECT_CODE
SUBJECTS_DIR = PROJECT_DIR / "subjects"
RUN_LOG_DIR = PROJECT_DIR / "rerun_logs"
BACKUP_DIR = PROJECT_DIR / "rerun_backups"
AUDIT_LEDGER = PROJECT_DIR / "audit_ledger.jsonl"
DELETED_PROJECT_BACKUP_DIR = ROOT / "output" / "deleted_project_backups"

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
PHASES = ("screening_run_in", "baseline_randomization")
CENTER31_SUBJECTS = [
    "31001",
    "31006",
    "31008",
    "31010",
    "31013",
    "31014",
    "31015",
    "31016",
    "31017",
    "31018",
]


@dataclass
class SourceFile:
    path: Path
    subject_id: str
    category: str
    upload_batch: str

    def to_json(self) -> dict:
        d = asdict(self)
        d["path"] = str(self.path)
        return d


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def compact_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def append_audit(event: str, **details: object) -> None:
    AUDIT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": now(),
        "project_code": PROJECT_CODE,
        "study_stage": STUDY_STAGE,
        "event": event,
        **details,
    }
    with AUDIT_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def subject_source_dir(subject_id: str) -> Path:
    matches = [p for p in SOURCE_ROOT.rglob(subject_id) if p.is_dir() and p.name == subject_id]
    if not matches:
        raise FileNotFoundError(f"未找到受试者源目录: {subject_id}")
    if len(matches) > 1:
        # The source tree should not duplicate subject ids across centers, but
        # keep this explicit because duplicate ids would invalidate audit scope.
        raise RuntimeError(f"受试者 {subject_id} 在源目录中出现多次: {[str(p) for p in matches]}")
    return matches[0]


def category_for(path: Path, subject_dir: Path) -> str:
    rel = str(path.relative_to(subject_dir))
    name = path.name
    if "5.入组审核" in rel or any(kw in name for kw in ("邮件", "沟通", "Q&A", "QA", "随机前")):
        return "enrollment_comm"
    if "3.既往检验" in rel:
        return "prior_lab"
    if "1.既往" in rel or "既往病历" in name:
        return "prior_record"
    if "4.筛选-基线检验" in rel:
        return "screening_lab"
    if "2.筛选" in rel or "病历" in name:
        return "screening_record"
    if any(kw in name for kw in ("检验", "检查", "化验", "血", "尿", "心电", "超声", "过敏")):
        return "screening_lab"
    return "unknown"


def upload_batch_for(path: Path) -> str:
    name = path.name.upper()
    original = path.name
    if "筛选" in original:
        return "screening"
    if "基线" in original or "随机前" in original or "D1" in name:
        return "baseline"
    return "screening"


def collect_subject_files(subject_id: str) -> list[SourceFile]:
    sdir = subject_source_dir(subject_id)
    files: list[SourceFile] = []
    for path in sorted(sdir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        files.append(
            SourceFile(
                path=path,
                subject_id=subject_id,
                category=category_for(path, sdir),
                upload_batch=upload_batch_for(path),
            )
        )
    if not files:
        raise FileNotFoundError(f"未找到可上传文件: {subject_id}")
    return files


def inventory_source_tree() -> dict:
    centers = []
    subject_dirs = []
    file_count = 0
    for center in SOURCE_ROOT.iterdir():
        if center.is_dir() and not center.name.startswith("."):
            centers.append(center.name)
    for path in SOURCE_ROOT.rglob("*"):
        if path.is_dir() and re.fullmatch(r"\d{5}", path.name):
            subject_dirs.append(str(path))
        elif path.is_file() and not path.name.startswith(".") and path.suffix.lower() in SUPPORTED_SUFFIXES:
            file_count += 1
    return {
        "source_root": str(SOURCE_ROOT),
        "center_count": len(centers),
        "centers_sample": sorted(centers)[:10],
        "subject_count": len(subject_dirs),
        "subject_sample": sorted(subject_dirs)[:10],
        "supported_file_count": file_count,
    }


def parse_protocol_workflow() -> dict:
    from app.deconstructor import extract_docx_protocol_workflow

    workflow = extract_docx_protocol_workflow(str(PROTOCOL_DOCX))
    stages = workflow.get("study_stages", [])
    phases = [p.get("phase_id") for p in workflow.get("review_phases", [])]
    if STUDY_STAGE not in stages:
        raise RuntimeError(f"协议流程未识别到 {STUDY_STAGE}: {stages}")
    for phase in PHASES:
        if phase not in phases:
            raise RuntimeError(f"协议流程未识别到审核分期 {phase}: {phases}")
    return workflow


def authenticate(session: requests.Session, base_url: str, username: str, password: str) -> dict:
    resp = session.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password},
        timeout=120,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"login failed for {username}: HTTP {resp.status_code}: {resp.text}")
    data = resp.json()
    session.headers.update({
        "X-Enrollment-User": data["username"],
        "X-Enrollment-Token": data["token"],
    })
    return data


def request_json(session: requests.Session, method: str, url: str, **kwargs) -> dict:
    resp = session.request(method, url, timeout=120, **kwargs)
    if resp.status_code >= 400:
        raise RuntimeError(f"{method} {url} failed: HTTP {resp.status_code}: {resp.text}")
    if not resp.text:
        return {}
    return resp.json()


def project_exists(session: requests.Session, base_url: str) -> bool:
    resp = session.get(f"{base_url}/api/projects/{PROJECT_CODE}", timeout=120)
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    if resp.status_code == 403:
        raise RuntimeError(f"当前账号无权访问既有项目 {PROJECT_CODE}，请使用项目创建者或admin账号。")
    raise RuntimeError(f"GET project failed: HTTP {resp.status_code}: {resp.text}")


def backup_and_delete_project(session: requests.Session, base_url: str, run_id: str) -> str | None:
    if not project_exists(session, base_url):
        return None

    backup_path = None
    if PROJECT_DIR.exists():
        DELETED_PROJECT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = DELETED_PROJECT_BACKUP_DIR / f"{PROJECT_CODE}_{run_id}"
        suffix = 1
        while backup_path.exists():
            backup_path = DELETED_PROJECT_BACKUP_DIR / f"{PROJECT_CODE}_{run_id}_{suffix}"
            suffix += 1
        shutil.move(str(PROJECT_DIR), str(backup_path))

    resp = session.delete(f"{base_url}/api/projects/{PROJECT_CODE}", timeout=120)
    if resp.status_code not in {200, 404}:
        raise RuntimeError(f"delete project failed: HTTP {resp.status_code}: {resp.text}")
    return str(backup_path) if backup_path else None


def create_project_from_protocol(session: requests.Session, base_url: str, feedback: str = "") -> dict:
    with PROTOCOL_DOCX.open("rb") as handle:
        files = {
            "file": (
                PROTOCOL_DOCX.name,
                handle,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        data = {"study_stage": STUDY_STAGE}
        if feedback:
            data["feedback"] = feedback
        resp = session.post(f"{base_url}/api/projects/from-protocol", files=files, data=data, timeout=900)
    if resp.status_code >= 400:
        raise RuntimeError(f"create project from protocol failed: HTTP {resp.status_code}: {resp.text}")
    payload = resp.json()
    if payload.get("project_code") != PROJECT_CODE:
        raise RuntimeError(f"方案识别出的项目编号不是 {PROJECT_CODE}: {payload.get('project_code')}")
    project = payload.get("project") or {}
    if project.get("study_stage") != STUDY_STAGE:
        raise RuntimeError(f"方案项目未固定为 {STUDY_STAGE}: {project.get('study_stage')}")
    if payload.get("deconstruct_error"):
        raise RuntimeError(f"方案项目已创建但解构失败: {payload['deconstruct_error']}")
    return payload


def backup_existing_subject(subject_id: str, run_id: str) -> str | None:
    sd = SUBJECTS_DIR / subject_id
    if not sd.exists():
        return None
    target_root = BACKUP_DIR / run_id
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / subject_id
    if target.exists():
        suffix = 1
        while (target_root / f"{subject_id}_{suffix}").exists():
            suffix += 1
        target = target_root / f"{subject_id}_{suffix}"
    shutil.move(str(sd), str(target))
    append_audit("backup_subject", subject_id=subject_id, backup_path=str(target))
    return str(target)


def upload_files(session: requests.Session, base_url: str, subject_id: str, files: Iterable[SourceFile], label: str) -> dict:
    selected = list(files)
    if not selected:
        return {"status": "skipped", "batch": label, "files": []}

    multipart = []
    handles = []
    try:
        for item in selected:
            mime = mimetypes.guess_type(item.path.name)[0] or "application/octet-stream"
            handle = item.path.open("rb")
            handles.append(handle)
            multipart.append(("files", (item.path.name, handle, mime)))
            multipart.append(("categories", (None, item.category)))
        url = f"{base_url}/api/projects/{PROJECT_CODE}/subjects/{subject_id}/upload"
        resp = session.post(url, files=multipart, timeout=600)
        if resp.status_code >= 400:
            raise RuntimeError(f"upload {subject_id}/{label} failed: HTTP {resp.status_code}: {resp.text}")
        result = resp.json()
        result["batch"] = label
    finally:
        for handle in handles:
            handle.close()

    append_audit(
        "upload_batch",
        subject_id=subject_id,
        batch=label,
        file_count=len(selected),
        files=[{"path": str(f.path), "category": f.category} for f in selected],
        response=result,
    )
    return result


def process_phase(session: requests.Session, base_url: str, subject_id: str, phase: str) -> dict:
    url = f"{base_url}/api/projects/{PROJECT_CODE}/subjects/{subject_id}/process"
    params = {"phase": phase, "study_stage": STUDY_STAGE}
    events = []
    start = time.time()
    with session.get(url, params=params, stream=True, timeout=None) as resp:
        if resp.status_code >= 400:
            raise RuntimeError(f"process {subject_id}/{phase} failed: HTTP {resp.status_code}: {resp.text}")
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            events.append(event)
            msg = event.get("message", "")
            stage = event.get("stage", "")
            print(f"[{subject_id} {phase}] {stage}: {msg}", flush=True)
            if stage == "error":
                append_audit("process_phase_error", subject_id=subject_id, phase=phase, event=event)
                raise RuntimeError(f"process {subject_id}/{phase} error: {msg}")

    elapsed = round(time.time() - start, 1)
    append_audit("process_phase", subject_id=subject_id, phase=phase, elapsed_seconds=elapsed, events=events)
    return {"phase": phase, "elapsed_seconds": elapsed, "events": events}


def collect_artifacts(subject_id: str) -> dict:
    sd = SUBJECTS_DIR / subject_id
    cache_pages = list((sd / "cache").rglob("*.md")) if (sd / "cache").exists() else []
    raw_files = [p for p in (sd / "raw").iterdir() if p.is_file() and not p.name.startswith(".")]
    file_categories = {}
    cat_path = sd / "file_categories.json"
    if cat_path.exists():
        file_categories = json.loads(cat_path.read_text(encoding="utf-8"))

    phase_outputs = {}
    for phase in PHASES:
        bundle = sd / f"evidence_bundle_{phase}.md"
        report = sd / "llm" / phase / "review_report.md"
        raw = sd / "llm" / phase / "review_raw.md"
        phase_outputs[phase] = {
            "bundle_path": str(bundle),
            "bundle_exists": bundle.exists(),
            "bundle_chars": len(bundle.read_text(encoding="utf-8")) if bundle.exists() else 0,
            "chunk_count": bundle.read_text(encoding="utf-8").count("片段ck_") if bundle.exists() else 0,
            "report_path": str(report),
            "report_exists": report.exists(),
            "raw_response_path": str(raw),
            "raw_response_exists": raw.exists(),
        }

    info_path = sd / "info.json"
    info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
    return {
        "subject_id": subject_id,
        "raw_file_count": len(raw_files),
        "raw_files": [p.name for p in raw_files],
        "file_categories": file_categories,
        "cache_page_count": len(cache_pages),
        "info": info,
        "phase_outputs": phase_outputs,
    }


def run(args: argparse.Namespace) -> int:
    run_id = compact_ts()
    run_log_root = RUN_LOG_DIR if PROJECT_DIR.exists() else (ROOT / "output" / "mgk10sar_phase3_rerun_logs")
    run_log_root.mkdir(parents=True, exist_ok=True)
    run_log_path = run_log_root / f"mgk10sar_phase3_rerun_{run_id}.json"

    run_log = {
        "run_id": run_id,
        "started_at": now(),
        "base_url": args.base_url,
        "project_code": PROJECT_CODE,
        "study_stage": STUDY_STAGE,
        "subjects": args.subjects,
        "source_inventory": inventory_source_tree(),
        "protocol_workflow": {},
        "auth_user": args.username,
        "clean_project": args.clean_project,
        "create_from_protocol": args.create_from_protocol,
        "deleted_project_backup": None,
        "project_create_response": None,
        "subject_runs": {},
        "errors": [],
    }

    session = requests.Session()
    login = authenticate(session, args.base_url, args.username, args.password)
    run_log["login"] = {"username": login.get("username"), "role": login.get("role")}

    workflow = parse_protocol_workflow()
    run_log["protocol_workflow"] = workflow
    workflow_snapshot = run_log_root / f"protocol_workflow_snapshot_{run_id}.json"
    workflow_snapshot.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")

    health = request_json(session, "GET", f"{args.base_url}/api/health")
    run_log["health"] = health
    if not health.get("omlx") or not health.get("deepseek"):
        raise RuntimeError(f"后端健康检查失败: {health}")

    if args.clean_project:
        run_log["deleted_project_backup"] = backup_and_delete_project(session, args.base_url, run_id)

    if args.create_from_protocol:
        run_log["project_create_response"] = create_project_from_protocol(
            session,
            args.base_url,
            feedback=args.deconstruct_feedback,
        )
        run_log_root = RUN_LOG_DIR
        RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
        run_log_path = RUN_LOG_DIR / f"mgk10sar_phase3_rerun_{run_id}.json"
        workflow_snapshot = RUN_LOG_DIR / f"protocol_workflow_snapshot_{run_id}.json"
        workflow_snapshot.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")

    append_audit("run_start", run_id=run_id, subjects=args.subjects, auth_user=args.username)
    append_audit(
        "protocol_workflow_parsed",
        run_id=run_id,
        workflow_snapshot=str(workflow_snapshot),
        study_stages=workflow.get("study_stages", []),
        review_phases=[p.get("phase_id") for p in workflow.get("review_phases", [])],
    )

    api_workflow = request_json(session, "GET", f"{args.base_url}/api/projects/{PROJECT_CODE}/phases")
    run_log["api_workflow"] = api_workflow
    if api_workflow.get("requires_study_stage_selection"):
        raise RuntimeError("API workflow 仍要求选择研究阶段；III期解构后应为单一期别项目")
    if api_workflow.get("study_stage") != STUDY_STAGE:
        raise RuntimeError(f"API workflow 未固定为 {STUDY_STAGE}: {api_workflow.get('study_stage')}")
    stages = api_workflow.get("study_stages") or []
    if stages and stages != [STUDY_STAGE]:
        raise RuntimeError(f"API workflow 仍包含多个研究阶段: {stages}")
    wrong_phase_stages = [
        phase for phase in api_workflow.get("review_phases", [])
        if phase.get("study_stage") and phase.get("study_stage") != STUDY_STAGE
    ]
    if wrong_phase_stages:
        raise RuntimeError(f"API workflow 中仍有非III期审核阶段: {wrong_phase_stages}")

    for subject_id in args.subjects:
        subject_log = {"source_files": [], "backup_path": None, "uploads": [], "process": [], "artifacts": {}}
        run_log["subject_runs"][subject_id] = subject_log
        try:
            source_files = collect_subject_files(subject_id)
            subject_log["source_files"] = [f.to_json() for f in source_files]
            subject_log["backup_path"] = backup_existing_subject(subject_id, run_id)

            request_json(
                session,
                "POST",
                f"{args.base_url}/api/projects/{PROJECT_CODE}/subjects",
                json={
                    "subject_id": subject_id,
                    "center_code": CENTER_CODE,
                    "center_name": CENTER_NAME,
                },
            )
            append_audit("create_subject", subject_id=subject_id)

            screening_files = [f for f in source_files if f.upload_batch == "screening"]
            baseline_files = [f for f in source_files if f.upload_batch == "baseline"]

            subject_log["uploads"].append(upload_files(session, args.base_url, subject_id, screening_files, "screening"))
            subject_log["process"].append(process_phase(session, args.base_url, subject_id, "screening_run_in"))

            if baseline_files:
                subject_log["uploads"].append(upload_files(session, args.base_url, subject_id, baseline_files, "baseline"))
            else:
                subject_log["uploads"].append({"status": "skipped", "batch": "baseline", "files": []})
                append_audit("upload_batch_skipped", subject_id=subject_id, batch="baseline", reason="no baseline-named files")
            subject_log["process"].append(process_phase(session, args.base_url, subject_id, "baseline_randomization"))

            subject_log["artifacts"] = collect_artifacts(subject_id)
            append_audit("subject_complete", subject_id=subject_id, artifacts=subject_log["artifacts"])
        except Exception as exc:
            error = {"subject_id": subject_id, "error": str(exc)}
            run_log["errors"].append(error)
            append_audit("subject_error", **error)
            print(f"[{subject_id}] ERROR: {exc}", file=sys.stderr, flush=True)
            if not args.continue_on_error:
                break
        finally:
            run_log["updated_at"] = now()
            run_log_path.write_text(json.dumps(run_log, ensure_ascii=False, indent=2), encoding="utf-8")

    run_log["finished_at"] = now()
    run_log_path.write_text(json.dumps(run_log, ensure_ascii=False, indent=2), encoding="utf-8")
    append_audit("run_finish", run_id=run_id, run_log=str(run_log_path), errors=run_log["errors"])
    print(f"Run log: {run_log_path}")
    if run_log["errors"]:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--username", default="smkzw")
    parser.add_argument("--password", default="")
    parser.add_argument("--clean-project", action="store_true")
    parser.add_argument("--create-from-protocol", action="store_true")
    parser.add_argument(
        "--deconstruct-feedback",
        default="请按MG-K10-SAR III期入排审核需要，除固定入选/排除标准外，继续拆解筛选期、基线/随机前及基线以前必须完成的检查、检验、评分、知情同意、时间窗和入排审核分期。",
    )
    parser.add_argument("--subjects", nargs="+", default=CENTER31_SUBJECTS)
    parser.add_argument("--continue-on-error", action="store_true", default=True)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
