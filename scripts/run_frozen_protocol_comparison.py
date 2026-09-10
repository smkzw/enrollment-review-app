#!/usr/bin/env python3
"""原始方案 DOCX 的冻结快照解构横评入口（隔离运行目录，复用现有产品服务）。

用法（准备与执行是两条独立命令，属于同一次横评的两个阶段）：

    python scripts/run_frozen_protocol_comparison.py prepare \
        --protocol /path/to/protocol.docx --run-dir runs/.../<run_id> \
        --study-phase phase_ii

    python scripts/run_frozen_protocol_comparison.py execute \
        --run-dir runs/.../<run_id> [--backend deepseek] [--model ...] \
        [--reasoning-effort high] [--max-tokens 65536] [--provider-defaults]

行为与边界：

- ``prepare`` 用真实产品链登记原始 DOCX 并走到冻结快照：工作台上传 ->
  结构提取 -> 渲染对齐 -> 方案信息与研究期别识别 -> 显式期别确认 ->
  冻结规则与流程目录；随后在 ``generate_draft`` 处以显式非重试边界停止，
  不做任何语义模型调用。
- ``execute`` 校验来源哈希与冻结检查点后，重新排队 ``generate_draft``，
  用生产 ``create_protocol_deconstruction_executor`` 与真实 ``JobRunner``
  继续官方 IN/EX 语义解构；不注入草稿构造器或页面文本构造器。
- 传输只允许产品原生 ``DeepSeekProtocolAgentTransport`` 的可配置后端；
  不支持的后端显式失败，绝不伪装成其他供应商。发送前强制输出预算
  >= 65536 tokens；保留产品原生采样参数并留存，不声称厂商默认。
  ``--provider-defaults`` 为显式可选开关：仅去掉产品侧采样覆盖
  （temperature），改用所选平台自身默认采样，保留 MTPLX 严格 JSON 的 AR 兼容措施，
  提示词与严格输出 Schema 保持不变；缺省关闭，行为与历史一致。
  开关与传输身份一起写入执行记录。
- 全部数据与 SQLite 位于 ``<run-dir>/data_v2`` 新建目录；拒绝已存在的
  运行目录，拒绝来源与输出目录互相重叠，绝不触碰默认产品数据库。
- 真实请求回执使用现有产品钩子：路由审计
  （``blobs/protocol-semantic-route-audits/<job>/route-audit.json``）、
  已验证语义批次缓存（``blobs/protocol-semantic-batches/<job>/``）与
  传输会话历史（``transport.history``）。不修改 app 增加钩子。
- 离线测试可通过函数参数注入测试执行器覆盖与传输；CLI 路径从不注入，
  运行记录会如实标注是否使用了测试覆盖。

退出码：0 完成；3 运行失败；4 使用/边界错误。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.agents.protocol_deconstructor import (  # noqa: E402
    protocol_prompt_template_sha256,
)
from app.agents.protocol_semantic_transport import (  # noqa: E402
    MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS,
    SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS,
    DeepSeekProtocolAgentTransport,
)
from app.config import (  # noqa: E402
    DECONSTRUCT_BACKEND,
    DECONSTRUCT_MAX_TOKENS,
    MTPLX_PROTOCOL_BATCH_MAX_TOKENS,
    OMLX_PROTOCOL_BATCH_MAX_TOKENS,
)
from app.domain.contracts.enums import StudyPhase  # noqa: E402
from app.services.protocol_deconstruction_executor import (  # noqa: E402
    _DEFAULT_PROMPT,
    ProtocolDeconstructionExecutorConfig,
    create_protocol_deconstruction_executor,
    load_persisted_route_audit,
)
from app.services.protocol_workbench_service import (  # noqa: E402
    PROTOCOL_DECONSTRUCTION_JOB_TYPE,
    ProtocolWorkbenchError,
    ProtocolWorkbenchService,
    STEP_EXTRACT,
    STEP_FREEZE,
    STEP_GENERATE,
)
from app.storage.codecs import utc_now, verify_payload_sha256  # noqa: E402
from app.storage.config import resolve_data_paths  # noqa: E402
from app.storage.db import build_engine, build_session_factory  # noqa: E402
from app.storage.migrate import MigrationManager  # noqa: E402
from app.workflow.errors import StepFailure  # noqa: E402
from app.workflow.jobstore import JobStore  # noqa: E402
from app.workflow.runner import JobRunner  # noqa: E402

RUNNER_LABEL = "frozen-protocol-comparison"
STOP_ERROR_CODE = "FROZEN_COMPARISON_STOP_AFTER_FREEZE"
CONTRACT = "frozen-protocol-comparison/v1"
MIN_BENCHMARK_MAX_TOKENS = 65536

EXIT_OK = 0
EXIT_RUN_FAILED = 3
EXIT_USAGE_OR_GUARD = 4

Now = Callable[[], datetime]
ExecutorOverrides = dict[str, Any]

# 与 app.agents.protocol_semantic_transport 的本地结构化批次上限保持一致
# （该模块未导出分组常量；此处只读复刻，用于发送前预算校验）。
_MTPLX_BACKENDS = frozenset({"mtplx", "mtplx-api"})


class ComparisonGuardError(RuntimeError):
    """使用方式或边界守卫不满足（退出码 4）。"""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_new_directory(path: Path) -> None:
    if path.exists():
        raise ComparisonGuardError(
            f"运行目录已存在，横评入口拒绝复用或覆盖：{path}"
        )


def _require_no_overlap(source: Path, output: Path) -> None:
    source_resolved = source.resolve()
    output_resolved = output.resolve()
    if (
        source_resolved == output_resolved
        or output_resolved in source_resolved.parents
        or source_resolved in output_resolved.parents
    ):
        raise ComparisonGuardError(
            "来源文件与输出目录互相重叠；请在互不嵌套的目录之间运行横评："
            f"来源={source_resolved}，输出={output_resolved}"
        )


def effective_output_budget(backend: str, requested: int) -> int:
    """按产品传输的同一规则计算实际生效的输出预算（只读复刻，不改 app）。"""
    if backend in _MTPLX_BACKENDS:
        return min(requested, MTPLX_PROTOCOL_BATCH_MAX_TOKENS)
    if backend == "omlx":
        return min(requested, OMLX_PROTOCOL_BATCH_MAX_TOKENS)
    if backend == "mlx-serve":
        return min(requested, MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS)
    return requested


def resolve_output_budget(backend: str, requested: int | None) -> int:
    """发送前强制输出预算 >= 65536；不满足时显式拒绝，不静默降级。"""
    requested_value = (
        requested if requested is not None else max(DECONSTRUCT_MAX_TOKENS, MIN_BENCHMARK_MAX_TOKENS)
    )
    if requested_value < MIN_BENCHMARK_MAX_TOKENS:
        raise ComparisonGuardError(
            "正式横评要求输出预算 >= "
            f"{MIN_BENCHMARK_MAX_TOKENS} tokens；当前请求 {requested_value}，未发送任何请求。"
        )
    effective = effective_output_budget(backend, requested_value)
    if effective < MIN_BENCHMARK_MAX_TOKENS:
        cap_env = (
            "MTPLX_PROTOCOL_BATCH_MAX_TOKENS"
            if backend in _MTPLX_BACKENDS
            else "OMLX_PROTOCOL_BATCH_MAX_TOKENS"
            if backend == "omlx"
            else "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS"
        )
        raise ComparisonGuardError(
            f"后端 {backend} 的本地批次上限（{cap_env}）把输出预算压到 "
            f"{effective} tokens，低于正式横评要求的 {MIN_BENCHMARK_MAX_TOKENS}；"
            f"请先调高 {cap_env} 后重试。未发送任何请求。"
        )
    return effective


def build_transport(
    backend: str,
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
    max_tokens: int,
    provider_defaults: bool = False,
) -> DeepSeekProtocolAgentTransport:
    if backend not in SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS:
        raise ComparisonGuardError(
            f"后端 {backend or '空值'} 不受产品方案解构支持；"
            f"受支持的后端：{sorted(SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS)}。"
            "横评不会把请求伪装成其他供应商。"
        )
    try:
        return DeepSeekProtocolAgentTransport(
            backend=backend,
            model=model,
            reasoning_effort=reasoning_effort,
            max_tokens=max_tokens,
            provider_defaults=provider_defaults,
        )
    except ValueError as exc:
        raise ComparisonGuardError(
            f"原生方案解构传输配置失败（未发送任何请求）：{exc}"
        ) from exc


def _transport_identity(transport: Any) -> dict[str, Any]:
    return {
        "transport_class": f"{type(transport).__module__}.{type(transport).__qualname__}",
        "backend": getattr(transport, "_backend", "unknown"),
        "model": getattr(transport, "_model", "unknown"),
        "reasoning_effort": getattr(transport, "_reasoning_effort", "unknown"),
        "max_tokens": getattr(transport, "_max_tokens", None),
        "provider_defaults": getattr(transport, "_provider_defaults", None),
    }


def _record_calls(transport: Any, receipts_dir: Path, sequence: list[int]) -> Any:
    """Observe the native SDK call without changing product messages or parameters."""
    completions = transport._client.chat.completions
    original = completions.create

    def create(**kwargs: Any) -> Any:
        if int(kwargs.get("max_tokens", 0)) < MIN_BENCHMARK_MAX_TOKENS:
            raise ComparisonGuardError("实际请求低于65536，未发送")
        index = sequence[0]
        sequence[0] += 1
        receipts_dir.mkdir(parents=True, exist_ok=True)
        _write_json(receipts_dir / f"request-{index:04d}.json", kwargs)
        started = time.monotonic()
        receipt = {**_transport_identity(transport), "attempt": index}
        try:
            response = original(**kwargs)
            payload = response.model_dump(mode="json")
            _write_json(receipts_dir / f"response-{index:04d}.json", payload)
            receipt.update(
                response_model=payload.get("model"),
                usage=payload.get("usage"),
                finish_reasons=[c.get("finish_reason") for c in payload.get("choices", [])],
            )
            return response
        except Exception as exc:
            receipt["failure_type"] = type(exc).__name__
            receipt["status_code"] = getattr(exc, "status_code", None)
            raise
        finally:
            receipt["elapsed_seconds"] = time.monotonic() - started
            _write_json(receipts_dir / f"receipt-{index:04d}.json", receipt)

    completions.create = create
    return transport


def _stop_after_freeze_executor(production_executor: Callable[[Any], dict[str, Any]]):
    """准备阶段包装生产执行器：冻结快照后在 generate_draft 显式停止。"""

    def execute(context: Any) -> dict[str, Any]:
        if context.step_id == STEP_GENERATE:
            raise StepFailure(
                retryable=False,
                error_code=STOP_ERROR_CODE,
                detail=(
                    "横评准备阶段已在冻结快照后停止来源任务；"
                    "语义解构由 execute 命令单独驱动。"
                ),
            )
        return production_executor(context)

    return execute


def _confirm_inputs(
    review: Any,
    *,
    study_phase: StudyPhase,
    overrides: dict[str, str | None],
) -> dict[str, Any]:
    """从产品识别结果推导确认输入；缺失项只接受显式覆盖，不做合成回退。"""
    pending = review.identity_decision
    resolved: dict[str, str] = {}
    for field in ("protocol_code", "project_name", "official_version"):
        value = overrides.get(field) or getattr(pending, field)
        if not value:
            raise ComparisonGuardError(
                f"产品未识别出{field}，横评不会填入合成值；"
                "请通过对应 CLI 参数显式确认后重试。"
            )
        resolved[field] = str(value)
    official_date = pending.official_date
    date_value = overrides.get("official_date_value")
    date_precision = overrides.get("official_date_precision")
    if official_date is not None and official_date.value is not None and not date_value:
        date_value = official_date.value.isoformat()
        date_precision = date_precision or official_date.precision.value
    if not date_value or not date_precision:
        raise ComparisonGuardError(
            "产品未识别出版本日期，横评不会填入合成日期；"
            "请通过 --official-date-value / --official-date-precision 显式确认后重试。"
        )
    candidate_phases = {
        str(item.get("phase")) for item in review.phase_candidates if item.get("phase")
    }
    if study_phase.value not in candidate_phases:
        raise ComparisonGuardError(
            "指定研究期别不在方案识别候选中，横评拒绝替用户选择；"
            f"指定：{study_phase.value}，实际候选：{sorted(candidate_phases) or '无'}。"
        )
    return {
        **resolved,
        "official_date_value": str(date_value),
        "official_date_precision": str(date_precision),
        "study_phase": study_phase,
    }


def _open_run_data(
    run_dir: Path, *, now: Now
) -> tuple[Any, Any, Any]:
    """解析隔离数据根并迁移到 head；返回 (data_paths, engine, session_factory)。"""
    data_paths = resolve_data_paths(env_override=str(run_dir / "data_v2"))
    data_paths.ensure_directories()
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    session_factory = build_session_factory(engine)
    return data_paths, engine, session_factory


def _checkpoint(store: JobStore, job_id: str, step_id: str) -> dict[str, Any]:
    checkpoint = store.get_last_checkpoint(job_id, step_id)
    if checkpoint is None:
        raise ComparisonGuardError(
            f"任务 {job_id} 缺少 {step_id} 检查点，横评拒绝继续。"
        )
    return checkpoint[1]


def prepare(
    *,
    run_dir: Path,
    protocol_path: Path,
    study_phase: StudyPhase,
    identity_overrides: dict[str, str | None] | None = None,
    actor: str = RUNNER_LABEL,
    now: Now = utc_now,
    executor_overrides: ExecutorOverrides | None = None,
) -> dict[str, Any]:
    """真实产品来源链：登记 -> 提取 -> 渲染对齐 -> 识别 -> 确认 -> 冻结。"""
    run_dir = Path(run_dir).resolve()
    protocol_path = Path(protocol_path).resolve()
    started = now()
    run_id = f"prepare-{started.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    record: dict[str, Any] = {
        "contract": CONTRACT,
        "phase": "prepare",
        "run_id": run_id,
        "runner": "scripts/run_frozen_protocol_comparison.py",
        "started_at": started.isoformat(),
        "claims_complete": False,
        "clinical_acceptance": False,
        "notes": [],
    }
    if not protocol_path.is_file():
        raise ComparisonGuardError(f"方案文件不存在：{protocol_path}")
    if protocol_path.suffix.lower() != ".docx":
        raise ComparisonGuardError(
            "横评入口只接受 DOCX 正式方案（产品 PDF 上传入口已下线）；"
            f"收到：{protocol_path.name}"
        )
    # 重叠守卫先于目录存在守卫：来源文件位于输出目录内时，输出目录必然
    # 已因来源文件而存在，此时重叠才是更精确的违规。
    _require_no_overlap(protocol_path, run_dir)
    _require_new_directory(run_dir)
    run_dir.mkdir(parents=True)
    source_sha256_before = _sha256_of(protocol_path)
    record["source"] = {
        "path": str(protocol_path),
        "sha256": source_sha256_before,
        "size_bytes": protocol_path.stat().st_size,
    }
    record["executor_overrides_used"] = bool(executor_overrides)

    data_paths, engine, session_factory = _open_run_data(run_dir, now=now)
    try:
        workbench = ProtocolWorkbenchService(
            session_factory, data_paths=data_paths, now=now
        )
        production_executor = create_protocol_deconstruction_executor(
            ProtocolDeconstructionExecutorConfig(
                data_paths=data_paths,
                session_factory=session_factory,
                now=now,
                **(executor_overrides or {}),
            )
        )
        runner = JobRunner(
            session_factory,
            {
                PROTOCOL_DECONSTRUCTION_JOB_TYPE: _stop_after_freeze_executor(
                    production_executor
                )
            },
            worker_id=f"{RUNNER_LABEL}-prepare",
            now=now,
        )
        start_result = workbench.start_first_deconstruction(
            upload_path=protocol_path,
            original_name=protocol_path.name,
            idempotency_key=f"{run_id}-source",
            actor=actor,
        )
        job_id = start_result.job_id
        record["protocol_job_id"] = job_id
        runner.run_job(job_id)
        review = workbench.get_identity_review(job_id)
        confirm_inputs = _confirm_inputs(
            review,
            study_phase=study_phase,
            overrides=identity_overrides or {},
        )
        workbench.confirm_identity(job_id, **confirm_inputs, actor=actor)
        runner.run_job(job_id)

        with session_factory() as session:
            store = JobStore(session, now=now)
            job = store.get_job(job_id)
            record["job_state_after_prepare"] = job.state
            steps = {step.step_id: step for step in store.list_steps(job_id)}
            generate_step = steps.get(STEP_GENERATE)
            stop_code = generate_step.error_code if generate_step else None
            if job.state not in {"failed", "failed_final"} or stop_code != STOP_ERROR_CODE:
                raise ComparisonGuardError(
                    "准备阶段未在 generate_draft 处按预期停止；"
                    f"任务状态={job.state}，generate 错误码={stop_code}。"
                )
            freeze_payload = _checkpoint(store, job_id, STEP_FREEZE)
            extract_payload = _checkpoint(store, job_id, STEP_EXTRACT)

        # 来源不可变副本哈希必须与登记一致。
        with session_factory() as session:
            store = JobStore(session, now=now)
            job = store.get_job(job_id)
            payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        registered_sha256 = str(payload["sha256"])
        storage_ref = str(payload["storage_ref"])
        blob_path = data_paths.blobs_dir / storage_ref
        if _sha256_of(blob_path) != registered_sha256:
            raise ComparisonGuardError(
                "已登记方案副本哈希与登记值不一致，横评拒绝继续。"
            )
        source_unchanged = _sha256_of(protocol_path) == source_sha256_before
        record["verification"] = {
            "source_blob_sha256_matches_registration": True,
            "source_file_unchanged": source_unchanged,
        }
        record["stopped_after"] = STEP_GENERATE
        record["stop_error_code"] = STOP_ERROR_CODE
        record["snapshot_id"] = extract_payload.get("snapshot_id")
        record["content_sha256"] = extract_payload.get("content_sha256")
        record["block_count"] = extract_payload.get("block_count")
        record["confirmed"] = {
            key: (
                value.value if isinstance(value, StudyPhase) else value
            )
            for key, value in confirm_inputs.items()
        }
        record["prompt_template_sha256"] = protocol_prompt_template_sha256(
            _DEFAULT_PROMPT
        )
        record["finished_at"] = now().isoformat()
        manifest = {
            "contract": CONTRACT,
            "runner": record["runner"],
            "created_at": record["finished_at"],
            "source": record["source"],
            "protocol_job_id": job_id,
            "snapshot_id": record["snapshot_id"],
            "content_sha256": record["content_sha256"],
            "block_count": record["block_count"],
            "confirmed": record["confirmed"],
            "prompt_template_sha256": record["prompt_template_sha256"],
            "stopped_after": STEP_GENERATE,
            "stop_error_code": STOP_ERROR_CODE,
            "claims_complete": False,
            "clinical_acceptance": False,
        }
        _write_json(run_dir / "manifest.json", manifest)
        _write_json(run_dir / "prepare_record.json", record)
        return record
    except Exception as exc:
        record["state"] = "failed"
        record["failure"] = f"{type(exc).__name__}: {exc}"
        _write_json(run_dir / "prepare_record.json", record)
        raise
    finally:
        engine.dispose()


def _collect_session_ids(payloads: list[Any]) -> list[str]:
    session_ids: list[str] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        audit = payload.get("semantic_route_audit") or payload
        for attempt in audit.get("attempts") or []:
            session_id = attempt.get("session_id")
            if session_id:
                session_ids.append(str(session_id))
    return session_ids


def _dump_transport_histories(
    transports: list[Any],
    session_ids: list[str],
    receipts_dir: Path,
) -> list[str]:
    """用产品传输自带的 history 钩子导出会话回执（含完整请求/响应正文）。"""
    receipts_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    sequence = 0
    for transport in transports:
        for session_id in session_ids:
            try:
                messages = transport.history(session_id)
            except ValueError:
                continue
            receipt = {
                "session_id": session_id,
                **_transport_identity(transport),
                "messages": [dict(message) for message in messages],
                "output_budget_enforced": True,
            }
            path = receipts_dir / f"history-{sequence:03d}-{session_id[:24]}.json"
            _write_json(path, receipt)
            written.append(str(path.relative_to(receipts_dir.parents[1])))
            sequence += 1
    return written


def execute(
    *,
    run_dir: Path,
    backend: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    max_tokens: int | None = None,
    provider_defaults: bool = False,
    actor: str = RUNNER_LABEL,
    now: Now = utc_now,
    executor_overrides: ExecutorOverrides | None = None,
    transport: Any | None = None,
    transport_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """校验冻结输入后用真实产品执行器与传输继续语义解构至审阅边界。"""
    run_dir = Path(run_dir).resolve()
    started = now()
    run_id = f"execute-{started.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    record: dict[str, Any] = {
        "contract": CONTRACT,
        "phase": "execute",
        "run_id": run_id,
        "runner": "scripts/run_frozen_protocol_comparison.py",
        "started_at": started.isoformat(),
        "claims_complete": False,
        "clinical_acceptance": False,
        "limitations": ["保留产品原生采样与重试，不把固定temperature称厂商默认；临床验收另行进行。"],
    }
    if not run_dir.is_dir():
        raise ComparisonGuardError(f"运行目录不存在，请先执行 prepare：{run_dir}")
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ComparisonGuardError(
            f"运行目录缺少 manifest.json，请先执行 prepare：{run_dir}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record["manifest_sha256"] = _sha256_of(manifest_path)
    record["executor_overrides_used"] = bool(executor_overrides)
    record["code_sha256"] = {
        str(path.relative_to(REPO_ROOT)): _sha256_of(path)
        for path in sorted([*REPO_ROOT.joinpath("app").rglob("*.py"), Path(__file__).resolve()])
    }

    selected_backend = (backend or DECONSTRUCT_BACKEND).strip().lower()
    budget = resolve_output_budget(selected_backend, max_tokens)
    record["provider_defaults"] = bool(provider_defaults)
    record["budget"] = {
        "requested": max_tokens if max_tokens is not None else max(
            DECONSTRUCT_MAX_TOKENS, MIN_BENCHMARK_MAX_TOKENS
        ),
        "effective": budget,
        "required": MIN_BENCHMARK_MAX_TOKENS,
        "enforced_before_send": True,
    }
    transports: list[Any] = []
    receipts_dir = run_dir / "execute" / "receipts"
    call_sequence = [0]
    if transport is None and transport_factory is None:
        def native_factory() -> Any:
            instance = build_transport(
                selected_backend, model=model,
                reasoning_effort=reasoning_effort, max_tokens=budget,
                provider_defaults=provider_defaults,
            )
            _record_calls(instance, receipts_dir, call_sequence)
            transports.append(instance)
            return instance

        base_transport = native_factory()
        record["transport"] = _transport_identity(base_transport)
        transport = base_transport
        transport_factory = native_factory
    elif transport is not None:
        transports.append(transport)
        record["transport"] = _transport_identity(transport)
    else:
        record["transport"] = {"transport_class": "injected-transport-factory"}

    # 预算与传输就绪后才创建执行输出目录，守卫失败不留下半成品目录。
    execute_dir = run_dir / "execute"
    _require_new_directory(execute_dir)
    execute_dir.mkdir(parents=True)
    receipts_dir = execute_dir / "receipts"

    data_paths, engine, session_factory = _open_run_data(run_dir, now=now)
    try:
        job_id = str(manifest["protocol_job_id"])
        with session_factory() as session:
            store = JobStore(session, now=now)
            job = store.get_job(job_id)
            payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
            job_state_before = job.state
            steps = {step.step_id: step for step in store.list_steps(job_id)}
            generate_step = steps.get(STEP_GENERATE)
            freeze_step = steps.get(STEP_FREEZE)
            if freeze_step is None or freeze_step.state != "completed":
                raise ComparisonGuardError("冻结步骤未完成，execute 拒绝继续。")
            if (
                generate_step is None
                or generate_step.error_code != STOP_ERROR_CODE
                or job_state_before not in {"failed", "failed_final"}
            ):
                raise ComparisonGuardError(
                    "来源任务不处于“冻结后显式停止”状态，execute 拒绝继续；"
                    f"任务状态={job_state_before}，generate 错误码="
                    f"{generate_step.error_code if generate_step else None}。"
                )
            freeze_payload = _checkpoint(store, job_id, STEP_FREEZE)
            extract_payload = _checkpoint(store, job_id, STEP_EXTRACT)

        verification: dict[str, Any] = {}
        verification["job_payload_sha256"] = True
        registered_sha256 = str(payload.get("sha256") or "")
        blob_path = data_paths.blobs_dir / str(payload.get("storage_ref"))
        verification["source_blob_sha256"] = (
            blob_path.is_file() and _sha256_of(blob_path) == registered_sha256
        )
        content_ref = str(extract_payload.get("content_storage_ref") or "")
        content_blob = data_paths.blobs_dir / content_ref
        verification["content_blob_sha256"] = (
            content_blob.is_file()
            and _sha256_of(content_blob)
            == str(extract_payload.get("content_sha256"))
        )
        verification["frozen_manifest_binding"] = (
            manifest.get("contract") == CONTRACT
            and manifest["source"]["sha256"] == registered_sha256
            and manifest.get("snapshot_id") == extract_payload.get("snapshot_id")
            and manifest.get("content_sha256") == extract_payload.get("content_sha256")
        )
        manifest_prompt = manifest.get("prompt_template_sha256")
        verification["prompt_template_unchanged"] = (
            manifest_prompt
            == protocol_prompt_template_sha256(_DEFAULT_PROMPT)
        )
        source_path = Path(str(manifest["source"]["path"]))
        verification["source_file_unchanged"] = (
            source_path.is_file()
            and _sha256_of(source_path)
            == str(manifest["source"]["sha256"])
        )
        if not all(
            value is True
            for key, value in verification.items()
            if key != "source_file_unchanged"
        ):
            raise ComparisonGuardError(
                f"冻结输入哈希校验未全部通过，execute 拒绝发送任何请求：{verification}"
            )
        record["verification"] = verification

        with session_factory() as session, session.begin():
            outcome = JobStore(session, now=now).retry_failed(job_id)
        record["resume"] = {
            "job_state_before": job_state_before,
            "requeued_state": outcome.state,
            "actor": actor,
        }

        executor = create_protocol_deconstruction_executor(
            ProtocolDeconstructionExecutorConfig(
                data_paths=data_paths,
                session_factory=session_factory,
                now=now,
                transport=transport,
                transport_factory=transport_factory,
                **(executor_overrides or {}),
            )
        )
        runner = JobRunner(
            session_factory,
            {PROTOCOL_DECONSTRUCTION_JOB_TYPE: executor},
            worker_id=f"{RUNNER_LABEL}-execute",
            now=now,
        )
        runner.run_job(job_id)

        with session_factory() as session:
            store = JobStore(session, now=now)
            job = store.get_job(job_id)
            steps = {step.step_id: step for step in store.list_steps(job_id)}
            generate_checkpoint = store.get_last_checkpoint(job_id, STEP_GENERATE)
            integrity_checkpoint = store.get_last_checkpoint(job_id, "integrity_check")
            route_audit = load_persisted_route_audit(
                ProtocolDeconstructionExecutorConfig(
                    data_paths=data_paths, session_factory=session_factory
                ),
                job_id,
            )
        generate_payload = generate_checkpoint[1] if generate_checkpoint else {}
        integrity_payload = integrity_checkpoint[1] if integrity_checkpoint else {}
        record["outcome"] = {
            "job_state": job.state,
            "awaiting_user": (
                "review"
                if steps.get("await_review") is not None
                and steps["await_review"].state == "waiting_user"
                else None
            ),
            "draft_id": generate_payload.get("draft_id"),
            "draft_revision_id": generate_payload.get("draft_revision_id"),
            "semantic_status": generate_payload.get("semantic_status"),
            "publishable": integrity_payload.get("publishable"),
        }
        record["route_audit"] = route_audit
        session_ids = _collect_session_ids([generate_payload, route_audit])
        record["receipts"] = {
            "transport_histories": _dump_transport_histories(
                transports, session_ids, receipts_dir
            ),
            "route_audit": (
                str(
                    data_paths.blobs_dir
                    / "protocol-semantic-route-audits"
                    / job_id
                    / "route-audit.json"
                )
                if route_audit
                else None
            ),
            "semantic_batch_cache_dir": str(
                data_paths.blobs_dir / "protocol-semantic-batches" / job_id
            ),
        }
        record["finished_at"] = now().isoformat()
        if record["outcome"]["awaiting_user"] != "review":
            record["state"] = "failed"
        _write_json(execute_dir / "execute_record.json", record)
        return record
    except Exception as exc:
        record["state"] = "failed"
        record["failure"] = f"{type(exc).__name__}: {exc}"
        _write_json(execute_dir / "execute_record.json", record)
        raise
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare", help="真实产品来源链：登记并冻结原始 DOCX（无模型调用）。"
    )
    prepare_parser.add_argument("--protocol", type=Path, required=True)
    prepare_parser.add_argument("--run-dir", type=Path, required=True)
    prepare_parser.add_argument(
        "--study-phase",
        choices=[item.value for item in StudyPhase],
        required=True,
        help="显式研究期别；必须出现在方案识别候选中。",
    )
    prepare_parser.add_argument("--protocol-code")
    prepare_parser.add_argument("--project-name")
    prepare_parser.add_argument("--official-version")
    prepare_parser.add_argument("--official-date-value")
    prepare_parser.add_argument(
        "--official-date-precision", choices=("year", "month", "day")
    )
    prepare_parser.add_argument("--actor", default=RUNNER_LABEL)

    execute_parser = subparsers.add_parser(
        "execute", help="校验冻结输入后用真实产品执行器与原生传输继续解构。"
    )
    execute_parser.add_argument("--run-dir", type=Path, required=True)
    execute_parser.add_argument(
        "--backend",
        help=f"原生传输后端；默认取 DECONSTRUCT_BACKEND（{DECONSTRUCT_BACKEND}）。",
    )
    execute_parser.add_argument("--model", help="缺省保持产品当前后端默认模型。")
    execute_parser.add_argument(
        "--reasoning-effort", help="缺省保持产品当前后端默认推理强度。"
    )
    execute_parser.add_argument(
        "--max-tokens",
        type=int,
        help=f"输出预算；必须 >= {MIN_BENCHMARK_MAX_TOKENS}，缺省取 max(DECONSTRUCT_MAX_TOKENS, {MIN_BENCHMARK_MAX_TOKENS})。",
    )
    execute_parser.add_argument(
        "--provider-defaults",
        action="store_true",
        help=(
            "改用所选平台自身默认采样：去掉产品侧 temperature，"
            "保留 MTPLX 严格 JSON 的 AR 兼容措施；提示词与输出 Schema 不变。"
            "缺省关闭，保留产品原生采样行为。"
        ),
    )
    execute_parser.add_argument("--actor", default=RUNNER_LABEL)

    args = parser.parse_args(argv)
    overrides = {
        "protocol_code": args.protocol_code if args.command == "prepare" else None,
        "project_name": args.project_name if args.command == "prepare" else None,
        "official_version": args.official_version if args.command == "prepare" else None,
        "official_date_value": (
            args.official_date_value if args.command == "prepare" else None
        ),
        "official_date_precision": (
            args.official_date_precision if args.command == "prepare" else None
        ),
    }
    try:
        if args.command == "prepare":
            record = prepare(
                run_dir=args.run_dir,
                protocol_path=args.protocol,
                study_phase=StudyPhase(args.study_phase),
                identity_overrides=overrides,
                actor=args.actor,
            )
            print(f"准备完成：{args.run_dir / 'prepare_record.json'}")
            print(f"来源任务：{record['protocol_job_id']}（冻结快照 {record['snapshot_id']}）")
        else:
            record = execute(
                run_dir=args.run_dir,
                backend=args.backend,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                max_tokens=args.max_tokens,
                provider_defaults=args.provider_defaults,
                actor=args.actor,
            )
            outcome = record["outcome"]
            print(f"执行记录：{args.run_dir / 'execute' / 'execute_record.json'}")
            print(
                "任务终态：{0}；等待审阅：{1}；可发布：{2}".format(
                    outcome["job_state"],
                    outcome["awaiting_user"],
                    outcome["publishable"],
                )
            )
            if record.get("state") == "failed":
                return EXIT_RUN_FAILED
    except ComparisonGuardError as exc:
        print(f"边界守卫：{exc}", file=sys.stderr)
        return EXIT_USAGE_OR_GUARD
    except ProtocolWorkbenchError as exc:
        print(f"工作台错误：{exc.code}: {exc.detail}", file=sys.stderr)
        return EXIT_RUN_FAILED
    except Exception as exc:  # noqa: BLE001 - CLI 边界
        print(f"横评运行失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_RUN_FAILED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
