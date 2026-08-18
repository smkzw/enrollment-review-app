#!/usr/bin/env python3
"""Run the Phase 3 real-protocol workflow against a clean V2 database.

The runner uses the production API, durable job executor, document renderer,
semantic model transport, publication service, and read projections.  It never
writes to the source protocol files and refuses to reuse a non-empty data root.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.v2.app import create_app
from app.domain.contracts.enums import StudyPhase
from app.services.protocol_deconstruction_executor import (
    ProtocolDeconstructionExecutorConfig,
    create_protocol_deconstruction_executor,
)
from app.services.protocol_workbench_service import PROTOCOL_DECONSTRUCTION_JOB_TYPE
from app.storage.config import resolve_data_paths
from app.workflow.runner import JobRunner
from app.workflow.recovery import recover_expired_jobs


@dataclass(frozen=True)
class ProtocolCase:
    name: str
    source: Path
    phase: StudyPhase
    protocol_code: str
    project_code: str
    project_name: str
    official_version: str
    official_date: str
    inclusion_count: int
    exclusion_count: int
    procedure_count: int
    expected_blocking_issue_codes: tuple[str, ...] = ()


CASES = {
    "mg-iii": ProtocolCase(
        name="mg-iii",
        source=Path(
            "/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/"
            "MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx"
        ),
        phase=StudyPhase.PHASE_III,
        protocol_code="MG-K10-SAR-001",
        project_code="MG-K10-SAR",
        project_name=(
            "一项评价MG-K10人源化单抗注射液治疗季节性过敏性鼻炎的有效性、"
            "安全性、药代动力学（PK）特征、药效动力学（PD）特征和免疫原性的"
            "多中心、随机、双盲、安慰剂对照的Ⅱ/Ⅲ期操作无缝临床研究"
        ),
        official_version="V2.1",
        official_date="2025-09-19",
        inclusion_count=7,
        exclusion_count=16,
        procedure_count=41,
        expected_blocking_issue_codes=("TIME_ANCHOR_UNRESOLVED",),
    ),
    "d001-ii": ProtocolCase(
        name="d001-ii",
        source=Path(
            "/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/"
            "CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx"
        ),
        phase=StudyPhase.PHASE_II,
        protocol_code="D001-02-002",
        project_code="D001-02",
        project_name=(
            "评价CMS-D001片治疗中度至重度斑块状银屑病成人患者的有效性和安全性的"
            "多中心、随机、双盲、安慰剂对照Ⅱ/Ⅲ期临床研究"
        ),
        official_version="1.0",
        official_date="2025-12-10",
        inclusion_count=6,
        exclusion_count=30,
        procedure_count=50,
    ),
}


def _source_state(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _request_json(response, *, expected: int = 200) -> dict[str, Any]:
    if response.status_code != expected:
        raise RuntimeError(
            f"HTTP {response.request.method} {response.request.url.path} "
            f"返回 {response.status_code}：{response.text[:1000]}"
        )
    return response.json()


def _advance_until(
    client: TestClient,
    runner: JobRunner,
    job_id: str,
    *,
    awaiting_user: str,
    limit: int = 40,
) -> dict[str, Any]:
    for _ in range(limit):
        current = _request_json(
            client.get(f"/api/v2/protocol/deconstructions/{job_id}")
        )
        if current.get("awaiting_user") == awaiting_user:
            return current
        if current.get("state") in {"failed", "failed_final", "cancelled"}:
            job = _request_json(client.get(f"/api/v2/jobs/{job_id}"))
            raise RuntimeError(
                f"方案任务在等待 {awaiting_user} 前终止："
                f"{json.dumps(job, ensure_ascii=False)[:4000]}"
            )
        runner.run_job(job_id)
    raise RuntimeError(f"任务未在 {limit} 次推进后到达 {awaiting_user}")


def _official_codes(prefix: str, count: int) -> list[str]:
    return [f"{prefix}-{index:02d}" for index in range(1, count + 1)]


def _validate_draft(case: ProtocolCase, body: dict[str, Any]) -> dict[str, Any]:
    draft = body["content"]
    rules = draft["proposed_rules"]
    codes = [rule["official_code"] for rule in rules]
    expected_codes = [
        *_official_codes("IN", case.inclusion_count),
        *_official_codes("EX", case.exclusion_count),
    ]
    if codes != expected_codes:
        raise RuntimeError(f"{case.name} 官方父规则编号/顺序偏离：{codes}")

    procedure_mappings = draft["procedure_catalog_mappings"]
    if len(procedure_mappings) != case.procedure_count:
        raise RuntimeError(
            f"{case.name} 必做项映射数为 {len(procedure_mappings)}，"
            f"预期 {case.procedure_count}"
        )
    for mapping in procedure_mappings:
        if not mapping["source_span_ids"] or not mapping["proposed_requirement_ids"]:
            raise RuntimeError(f"{case.name} 存在无来源或无资料要求的必做项")

    parent_mappings = draft["parent_catalog_mappings"]
    if len(parent_mappings) != len(expected_codes):
        raise RuntimeError(f"{case.name} 父规则目录未被逐项覆盖")

    component_ids = {
        component["rule_component_id"]
        for rule in rules
        for component in rule["components"]
    }
    component_drafts = draft["component_drafts"]
    bound_component_ids = {
        item["proposed_component"]["rule_component_id"] for item in component_drafts
    }
    if component_ids != bound_component_ids:
        raise RuntimeError(f"{case.name} 子组件与来源绑定不是一一闭包")
    if any(not item["source_refs"] for item in component_drafts):
        raise RuntimeError(f"{case.name} 存在无原文来源的子组件")

    visible_rule_text = json.dumps(rules, ensure_ascii=False)
    cross_phase_noise = (
        "仅III期",
        "仅Ⅲ期",
        "与II期对应条款一致",
        "与Ⅱ期对应条款一致",
        "本次按III期编号审核",
        "本次按Ⅲ期编号审核",
    )
    found_noise = [text for text in cross_phase_noise if text in visible_rule_text]
    if found_noise:
        raise RuntimeError(f"{case.name} 选定单一期别后仍有跨期噪声：{found_noise}")

    return {
        "rule_count": len(rules),
        "revision_number": body["revision_number"],
        "revision_id": body["revision_id"],
        "component_count": len(component_ids),
        "procedure_count": len(procedure_mappings),
        "requirement_count": len(draft["evidence_requirement_drafts"]),
        "workflow_stage_count": len(draft["proposed_workflow_stages"]),
        "official_codes": codes,
        "unresolved_items": draft["unresolved_items"],
    }


def _run_case(
    client: TestClient,
    runner: JobRunner,
    case: ProtocolCase,
    *,
    resume_job_id: str | None = None,
) -> dict[str, Any]:
    before = _source_state(case.source)
    started_at = time.monotonic()
    if resume_job_id is None:
        with case.source.open("rb") as handle:
            started = _request_json(
                client.post(
                    "/api/v2/protocol/deconstructions",
                    files={
                        "file": (
                            case.source.name,
                            handle,
                            "application/vnd.openxmlformats-officedocument."
                            "wordprocessingml.document",
                        )
                    },
                    data={
                        "idempotency_key": f"slice7-{case.name}-first",
                        "actor": "医学监查员验收",
                    },
                ),
                expected=201,
            )
        job_id = started["job_id"]
    else:
        job_id = resume_job_id

    current_session = _request_json(
        client.get(f"/api/v2/protocol/deconstructions/{job_id}")
    )
    if resume_job_id is not None and current_session.get("state") in {
        "failed_retryable",
        "failed_final",
    }:
        retry = _request_json(client.post(f"/api/v2/jobs/{job_id}/retry"))
        if retry.get("state") != "queued":
            raise RuntimeError(f"{case.name} 失败步骤未能进入重试队列：{retry}")
        current_session = _request_json(
            client.get(f"/api/v2/protocol/deconstructions/{job_id}")
        )
    if current_session.get("selected_phase"):
        # A durable resume continues from the latest checkpoint. It must not
        # search for or replay an already completed identity boundary.
        identity_session = current_session
    else:
        identity_session = _advance_until(
            client, runner, job_id, awaiting_user="identity"
        )
    identity = _request_json(
        client.get(f"/api/v2/protocol/deconstructions/{job_id}/identity")
    )
    detected = identity["identity"]
    identity_assertions = {
        "protocol_code": case.protocol_code,
        "project_code": case.project_code,
        "project_name": case.project_name,
        "official_version": case.official_version,
    }
    for field, expected in identity_assertions.items():
        if detected.get(field) != expected:
            raise RuntimeError(
                f"{case.name} {field} 识别为 {detected.get(field)!r}，"
                f"预期 {expected!r}"
            )

    if not any(
        item["phase"] == case.phase.value for item in identity["phase_candidates"]
    ):
        raise RuntimeError(f"{case.name} 未提供 {case.phase.value} 期别候选")
    if current_session.get("selected_phase"):
        confirm = {"selected_phase": current_session["selected_phase"]}
    else:
        confirm = _request_json(
            client.post(
                f"/api/v2/protocol/deconstructions/{job_id}/identity/confirm",
                json={
                    "protocol_code": case.protocol_code,
                    "project_code": case.project_code,
                    "project_name": case.project_name,
                    "official_version": case.official_version,
                    "official_date_value": case.official_date,
                    "official_date_precision": "day",
                    "study_phase": case.phase.value,
                    # Identity candidates and phase candidates are separate
                    # source sets.  The service deterministically binds every
                    # matching phase citation after this metadata confirmation.
                    "selected_candidate_ids": detected["selected_candidate_ids"],
                    "actor": "医学监查员验收",
                },
            )
        )
    if confirm["selected_phase"] != case.phase.value:
        raise RuntimeError(f"{case.name} 期别确认未持久化")

    current_session = _request_json(
        client.get(f"/api/v2/protocol/deconstructions/{job_id}")
    )
    if current_session.get("awaiting_user") in {"review", "publish"}:
        # A prior publish attempt may already have advanced the durable user
        # boundary to publish while leaving the immutable draft untouched.
        review_session = current_session
    else:
        review_session = _advance_until(
            client, runner, job_id, awaiting_user="review", limit=80
        )
    draft = _request_json(
        client.get(f"/api/v2/protocol/deconstructions/{job_id}/draft")
    )
    draft_summary = _validate_draft(case, draft)
    integrity = _request_json(
        client.get(f"/api/v2/protocol/deconstructions/{job_id}/integrity")
    )
    blocking_codes = sorted(
        item["issue_code"]
        for item in integrity["issues"]
        if item["level"] == "阻止发布"
    )
    expected_codes = sorted(case.expected_blocking_issue_codes)
    if blocking_codes != expected_codes:
        raise RuntimeError(
            f"{case.name} 阻止发布问题为 {blocking_codes}，预期 {expected_codes}"
        )
    if integrity["publishable"] != (not expected_codes):
        raise RuntimeError(f"{case.name} 发布状态与完整性问题不一致")

    sources = _request_json(
        client.get(f"/api/v2/protocol/deconstructions/{job_id}/sources")
    )
    if sources["selected_phase"] != case.phase.value or not sources["source_materials"]:
        raise RuntimeError(f"{case.name} 来源投影不完整")

    publication: dict[str, Any] | None = None
    replay: dict[str, Any] | None = None
    if integrity["publishable"]:
        publication = _request_json(
            client.post(
                f"/api/v2/protocol/deconstructions/{job_id}/publish",
                json={
                    "idempotency_key": f"slice7-{case.name}-publish",
                    "actor": "医学监查员验收",
                },
            )
        )
        replay = _request_json(
            client.post(
                f"/api/v2/protocol/deconstructions/{job_id}/publish",
                json={
                    "idempotency_key": f"slice7-{case.name}-publish",
                    "actor": "医学监查员验收",
                },
            )
        )
        if publication["replay"] or not replay["replay"]:
            raise RuntimeError(f"{case.name} 发布幂等语义错误")

    after = _source_state(case.source)
    if before != after:
        raise RuntimeError(f"{case.name} 原始方案在验收期间发生变化")

    return {
        "case": case.name,
        "job_id": job_id,
        "source_state": after,
        "identity": {
            "protocol_code": detected["protocol_code"],
            "project_code": detected["project_code"],
            "project_name": detected["project_name"],
            "official_version": detected["official_version"],
            "official_date": case.official_date,
            "selected_phase": confirm["selected_phase"],
        },
        "identity_recovery_checkpoint": identity_session["recovery_checkpoint_id"],
        "review_recovery_checkpoint": review_session["recovery_checkpoint_id"],
        "draft": draft_summary,
        "integrity": {
            "publishable": integrity["publishable"],
            "blocking_issue_codes": blocking_codes,
            "blocking_count": integrity["blocking_count"],
            "review_count": integrity["review_count"],
            "reminder_count": integrity["reminder_count"],
        },
        "publication": publication,
        "publication_replay": replay,
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--case", choices=[*CASES, "all"], default="all"
    )
    parser.add_argument("--resume-job-id")
    args = parser.parse_args()

    data_root = args.data_root.resolve()
    if data_root.exists() and any(data_root.iterdir()) and not args.resume_job_id:
        raise RuntimeError(f"真实验收数据根必须为空目录：{data_root}")
    if args.resume_job_id and args.case == "all":
        raise RuntimeError("恢复既有任务时必须指定一个方案用例")
    for case in CASES.values():
        if not case.source.is_file():
            raise FileNotFoundError(case.source)

    paths = resolve_data_paths(str(data_root))
    app = create_app(data_paths=paths, run_runner=False)
    selected = list(CASES) if args.case == "all" else [args.case]
    results: list[dict[str, Any]] = []
    with TestClient(app) as client:
        executor = create_protocol_deconstruction_executor(
            ProtocolDeconstructionExecutorConfig(
                data_paths=app.state.data_paths,
                session_factory=app.state.session_factory,
            )
        )
        runner = JobRunner(
            app.state.session_factory,
            {PROTOCOL_DECONSTRUCTION_JOB_TYPE: executor},
            worker_id="phase3-slice7-real-acceptance",
            poll_interval=0.01,
        )
        if args.resume_job_id is not None:
            recover_expired_jobs(app.state.session_factory)
        for name in selected:
            results.append(
                _run_case(
                    client,
                    runner,
                    CASES[name],
                    resume_job_id=args.resume_job_id,
                )
            )

        projects = _request_json(client.get("/api/v2/protocol/projects"))
        project_phases = {
            (item["protocol_code"], item["study_phase"])
            for item in projects["projects"]
        }
        expected_published = {
            (CASES[name].protocol_code, CASES[name].phase.value)
            for name in selected
            if not CASES[name].expected_blocking_issue_codes
        }
        if project_phases != expected_published:
            raise RuntimeError(
                f"正式项目边界不一致：{project_phases}，预期 {expected_published}"
            )
        expected_project_codes = {
            CASES[name].protocol_code: CASES[name].project_code
            for name in selected
            if not CASES[name].expected_blocking_issue_codes
        }
        for project in projects["projects"]:
            expected_project_code = expected_project_codes.get(project["protocol_code"])
            if (
                expected_project_code is not None
                and project["project_code"] != expected_project_code
            ):
                raise RuntimeError(
                    f"{project['protocol_code']} 正式项目代号为 "
                    f"{project['project_code']!r}，预期 {expected_project_code!r}"
                )

    payload = {
        "data_root": str(data_root),
        "results": results,
        "official_projects": projects["projects"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
