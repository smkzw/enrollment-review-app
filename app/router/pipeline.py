"""Pipeline endpoints — OCR only, Review only, and full SSE pipeline."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import time as _time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.shared import (
    ensure_project, ensure_subject, project_dir, subject_dir,
    load_subject_info, save_subject_info, sse_event,
)
from app.models import SubjectStatus
from app.pipeline.classifier import classify_directory
from app.pipeline.ocr import ocr_documents_parallel
from app.config import OCR_MAX_CONCURRENT
from app.pipeline.bundler import build_evidence_bundle
from app.pipeline.reviewer import run_review
from app.subject_dates import backfill_subject_icf_date, subject_anchor_dates
from app.phases import (
    load_review_workflow,
    phase_by_id,
    phase_bundle_path,
    phase_llm_dir,
)
from app.authz import current_user, require_project_access, require_subject_modify
from app.audit import log_audit
from app.processing_locks import acquire_subject_processing_lock, release_subject_processing_lock

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects/{code}/subjects/{sid}", tags=["pipeline"])


# ---------------------------------------------------------------------------
# OCR only
# ---------------------------------------------------------------------------

@router.post("/ocr")
async def run_ocr(code: str, sid: str, request: Request):
    """Run OCR on all uploaded files."""
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)

    info = load_subject_info(sd)
    require_subject_modify(user, cfg, info)
    if info.status == SubjectStatus.PROCESSING.value:
        raise HTTPException(status_code=409, detail=f"受试者 {sid} 正在处理中，请等待完成后再试")
    lock_key = await acquire_subject_processing_lock(code, sid)
    info.status = SubjectStatus.PROCESSING.value
    info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_subject_info(sd, info)

    try:
        log_audit(code, "ocr_start", user.get("username", ""), subject_id=sid)
        raw_dir = sd / "raw"
        cache_dir = sd / "cache"
        cache_dir.mkdir(exist_ok=True)

        classified = classify_directory(raw_dir)
        total = len(classified)
        results = []

        ocr_input = [{"path": str(cf.path), "stem": cf.path.stem, "category": cf.category} for cf in classified]
        parallel = await ocr_documents_parallel(ocr_input, cache_dir)
        for item in parallel["results"]:
            results.append({
                "file": item["file"],
                "pages": len(item.get("pages", [])),
                "error": item.get("error"),
            })

        backfill_subject_icf_date(sd)
        info = load_subject_info(sd)
        info.status = SubjectStatus.PENDING.value
        info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_subject_info(sd, info)
        log_audit(code, "ocr_done", user.get("username", ""), subject_id=sid, page_count=sum(item.get("pages", 0) for item in results if isinstance(item.get("pages", 0), int)))

        return {"status": "completed", "ocr_results": results}

    except Exception as exc:
        logger.exception("OCR failed for subject %s", sid)
        info.status = SubjectStatus.ERROR.value
        info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_subject_info(sd, info)
        log_audit(code, "ocr_error", user.get("username", ""), subject_id=sid, error=str(exc))
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}")
    finally:
        release_subject_processing_lock(lock_key)


# ---------------------------------------------------------------------------
# Review only
# ---------------------------------------------------------------------------

@router.post("/review")
async def run_review_only(
    code: str,
    sid: str,
    request: Request,
    phase: str = Query("full"),
    study_stage: str = Query(""),
):
    """Run LLM review only (assumes evidence bundle already exists)."""
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)
    info = load_subject_info(sd)
    require_subject_modify(user, cfg, info)
    if info.status == SubjectStatus.PROCESSING.value:
        raise HTTPException(status_code=409, detail=f"受试者 {sid} 正在处理中，请等待完成后再试")
    lock_key = await acquire_subject_processing_lock(code, sid)

    rules_path = project_dir(code) / "criteria_rules.md"
    rules_text = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""
    study_stage = study_stage or cfg.study_stage
    workflow = load_review_workflow(project_dir(code), rules_text)
    if workflow.get("requires_study_stage_selection") and not study_stage:
        raise HTTPException(status_code=400, detail="项目包含多个研究阶段，请先选择Ⅱ期或Ⅲ期。")

    phase_info = phase_by_id(workflow, phase)
    bundle_path = phase_bundle_path(sd, phase)
    if not bundle_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Evidence bundle not found. Run /process or build bundle first.",
        )

    backfill_subject_icf_date(sd)
    bundle_text = bundle_path.read_text(encoding="utf-8")
    anchor_dates = subject_anchor_dates(sd, phase)

    info.status = SubjectStatus.PROCESSING.value
    info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_subject_info(sd, info)

    try:
        log_audit(code, "review_start", user.get("username", ""), subject_id=sid, phase=phase)
        report = await run_review(
            subject_id=sid,
            project_code=code,
            anchor_dates=anchor_dates,
            criteria_rules=rules_text,
            evidence_bundle=bundle_text,
            output_dir=phase_llm_dir(sd, phase),
            review_phase=phase_info,
            study_stage=study_stage,
        )

        info.status = SubjectStatus.REVIEWED.value
        info.overall_verdict = report.overall_verdict
        info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_subject_info(sd, info)
        log_audit(code, "review_done", user.get("username", ""), subject_id=sid, phase=phase, verdict=report.overall_verdict)

        return {
            "status": "completed",
            "overall_verdict": report.overall_verdict,
            "summary": report.summary,
        }

    except Exception as exc:
        logger.exception("Review failed for subject %s", sid)
        info.status = SubjectStatus.ERROR.value
        info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_subject_info(sd, info)
        log_audit(code, "review_error", user.get("username", ""), subject_id=sid, phase=phase, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Review failed: {exc}")
    finally:
        release_subject_processing_lock(lock_key)


# ---------------------------------------------------------------------------
# Full pipeline with SSE
# ---------------------------------------------------------------------------

@router.get("/process")
async def process_subject(
    code: str,
    sid: str,
    request: Request,
    phase: str = Query("full"),
    study_stage: str = Query(""),
):
    """Run full pipeline (OCR → bundle → review) with SSE progress events."""
    user = current_user(request)
    cfg = ensure_project(code)
    require_project_access(user, cfg)
    sd = ensure_subject(code, sid)
    info = load_subject_info(sd)
    require_subject_modify(user, cfg, info)
    if info.status == SubjectStatus.PROCESSING.value:
        raise HTTPException(status_code=409, detail=f"受试者 {sid} 正在处理中，请等待完成后再试")

    raw_dir = sd / "raw"
    files_in_raw = [f for f in raw_dir.iterdir() if f.is_file()] if raw_dir.exists() else []
    if not files_in_raw:
        raise HTTPException(status_code=400, detail="No files uploaded for this subject")

    lock_key = await acquire_subject_processing_lock(code, sid)
    info.status = SubjectStatus.PROCESSING.value
    info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_subject_info(sd, info)
    log_audit(code, "process_start", user.get("username", ""), subject_id=sid, phase=phase)

    rules_path = project_dir(code) / "criteria_rules.md"
    rules_text = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""
    study_stage = study_stage or cfg.study_stage
    workflow = load_review_workflow(project_dir(code), rules_text)
    if workflow.get("requires_study_stage_selection") and not study_stage:
        raise HTTPException(status_code=400, detail="项目包含多个研究阶段，请先选择Ⅱ期或Ⅲ期。")
    phase_info = phase_by_id(workflow, phase)

    async def event_generator():
        try:
            # Stage 1: Classify
            yield sse_event({"stage": "classify", "progress": 0, "total": 5, "message": "分类文档..."})
            classified = classify_directory(raw_dir)
            total_files = len(classified)
            yield sse_event({
                "stage": "classify", "progress": 1, "total": 5,
                "message": f"共 {total_files} 个文件",
            })

            # Stage 1.5: VLM connectivity test
            yield sse_event({"stage": "ocr", "progress": 0, "total": total_files, "message": "测试VLM连通性..."})
            from app.llm.client import call_vision_ocr
            from PIL import Image
            test_img = Image.new('RGB', (50, 50), 'white')
            buf = io.BytesIO()
            test_img.save(buf, format='JPEG')
            test_b64 = base64.b64encode(buf.getvalue()).decode()

            vlm_ok = False
            vlm_backend = ""
            try:
                result = await call_vision_ocr(test_b64, "回复OK", total_pages=1)
                vlm_ok = True
                if "ok" in result.lower() or "好" in result or "白" in result:
                    vlm_backend = "auto(成功)"
                else:
                    vlm_backend = "auto(已连接)"
            except Exception as e:
                vlm_backend = f"失败: {str(e)[:50]}"

            if vlm_ok:
                yield sse_event({
                    "stage": "ocr", "progress": 0, "total": total_files,
                    "message": f"VLM连通性: ✅ {vlm_backend} | 开始OCR {total_files}个文件...",
                })
            else:
                yield sse_event({
                    "stage": "ocr", "progress": 0, "total": total_files,
                    "message": f"VLM连通性: ❌ {vlm_backend} | 尝试备用通道...",
                })

            # Stage 2: OCR — process files concurrently with one shared VLM limit
            cache_dir = sd / "cache"
            cache_dir.mkdir(exist_ok=True)

            ocr_start = _time.time()
            ocr_errors = []
            total_pages_all = 0
            native_all = 0
            vlm_all = 0
            cached_all = 0

            yield sse_event({
                "stage": "ocr",
                "progress": 0,
                "total": total_files,
                "message": f"OCR并发处理中: {total_files}个文件，最多{OCR_MAX_CONCURRENT}路VLM调用...",
            })
            ocr_input = [{"path": str(cf.path), "stem": cf.path.stem} for cf in classified]
            parallel = await ocr_documents_parallel(ocr_input, cache_dir)
            for item in parallel["results"]:
                pages_result = item.get("pages", [])
                total_pages_all += len(pages_result)
                if item.get("error"):
                    ocr_errors.append({"file": item.get("file", ""), "error": item["error"]})
                methods = item.get("methods", {})
                native_all += methods.get("native", 0)
                vlm_all += methods.get("vlm", 0)
                cached_all += methods.get("cache", 0)

            ocr_elapsed = _time.time() - ocr_start
            cached_files = list(cache_dir.rglob("*.md"))
            total_cached_pages = len(cached_files)
            error_msg = f" | {len(ocr_errors)}个文件失败" if ocr_errors else ""

            if total_cached_pages == 0 and total_pages_all == 0:
                error_detail = "; ".join(
                    [f"{e.get('file','?')}: {e.get('error','?')}" for e in ocr_errors]
                ) if ocr_errors else "未知原因"
                yield sse_event({
                    "stage": "error", "progress": 0, "total": 1,
                    "message": f"OCR失败: 未生成任何缓存文件。错误: {error_detail}",
                })
                info = load_subject_info(sd)
                info.status = "error"
                save_subject_info(sd, info)
                return

            yield sse_event({
                "stage": "ocr", "progress": total_files, "total": total_files,
                "message": f"OCR完成: {total_cached_pages}页缓存, {ocr_elapsed:.0f}秒{error_msg} (文本{native_all}+VLM{vlm_all}+缓存{cached_all})",
            })
            backfill_subject_icf_date(sd)

            # Stage 3: Build evidence bundle
            yield sse_event({"stage": "bundle", "progress": 1, "total": 1, "message": "构建证据包..."})
            bundle_text = build_evidence_bundle(
                subject_dir=sd,
                project_code=code,
                criteria_rules=rules_text,
                review_phase=phase,
                review_workflow=workflow,
                anchor_dates=subject_anchor_dates(sd, phase),
            )
            anchor_dates = subject_anchor_dates(sd, phase)

            if "共 0 个片段" in bundle_text:
                yield sse_event({
                    "stage": "error", "progress": 0, "total": 1,
                    "message": "证据包为空: OCR未产生有效内容。请检查上传的文件是否为有效PDF/图片。",
                })
                info = load_subject_info(sd)
                info.status = "error"
                save_subject_info(sd, info)
                return

            bundle_path = phase_bundle_path(sd, phase)
            bundle_path.write_text(bundle_text, encoding="utf-8")
            yield sse_event({"stage": "bundle", "progress": 1, "total": 1,
                             "message": f"证据包构建完成: {bundle_text.count('ck_')//2}个片段"})

            # Stage 4: model review
            yield sse_event({"stage": "review", "progress": 0, "total": 1, "message": "智能审核中..."})

            review_task = asyncio.create_task(run_review(
                subject_id=sid,
                project_code=code,
                anchor_dates=anchor_dates,
                criteria_rules=rules_text,
                evidence_bundle=bundle_text,
                output_dir=phase_llm_dir(sd, phase),
                review_phase=phase_info,
                study_stage=study_stage,
            ))

            heartbeat_count = 0
            while not review_task.done():
                await asyncio.sleep(5)
                heartbeat_count += 1
                if await request.is_disconnected():
                    review_task.cancel()
                    info = load_subject_info(sd)
                    info.status = SubjectStatus.PENDING.value
                    info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    save_subject_info(sd, info)
                    log_audit(code, "process_cancelled", user.get("username", ""), subject_id=sid, phase=phase)
                    return
                if heartbeat_count % 6 == 0:
                    yield sse_event({
                        "stage": "review", "progress": 0, "total": 1,
                        "message": f"智能审核中... (已等待{heartbeat_count * 5}秒)"
                    })

            report = await review_task
            yield sse_event({
                "stage": "review", "progress": 1, "total": 1,
                "message": f"审核完成: {report.overall_verdict}",
            })

            # Stage 5: Done
            info = load_subject_info(sd)
            info.status = SubjectStatus.REVIEWED.value
            info.overall_verdict = report.overall_verdict
            info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_subject_info(sd, info)
            log_audit(code, "process_done", user.get("username", ""), subject_id=sid, phase=phase, verdict=report.overall_verdict)

            yield sse_event({
                "stage": "done", "progress": 1, "total": 1,
                "message": "处理完成",
                "overall_verdict": report.overall_verdict,
                "summary": report.summary,
            })

        except Exception as exc:
            logger.exception("Pipeline failed for subject %s", sid)
            try:
                info = load_subject_info(sd)
                info.status = SubjectStatus.ERROR.value
                info.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_subject_info(sd, info)
            except Exception:
                pass
            log_audit(code, "process_error", user.get("username", ""), subject_id=sid, phase=phase, error=str(exc))
            yield sse_event({
                "stage": "error", "progress": 0, "total": 1,
                "message": f"处理失败: {exc}",
            })
        finally:
            release_subject_processing_lock(lock_key)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
