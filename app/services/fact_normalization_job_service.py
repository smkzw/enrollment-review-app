"""事实规范化持久任务定义。

复用现有 ``Job/Step/Checkpoint/Lease/Idempotency`` 与 ``FactNormalizationRun/Call/Candidate`` 仓储，
在发布前冻结不可变权威元组并拒绝陈旧结果，禁止重复事实/Profile 写入。

设计要点（implement.md §5.3 / prd P5-R09）：
- 每个逻辑文档一个调用；超长文档按连续页组切片并保留文档级合并；每个调用
  显式声明页清单，覆盖门禁要求所有页已处理或有逐页未解决原因。
- 幂等键 = ``(authority, prompt_version, model_config, input_scope_sha)``，
  同键同内容复用原 Job/Run，同键异内容抛 ``IdempotencyConflict``。
- 权威元组在 Job 创建时与持久 ``FactNormalizationRun`` 同时冻结；Job 执行
  期间每次提交前再次核对 ``ReviewEpisode.active_evidence_snapshot_id /
  active_evidence_processing_revision_id / revision``，任一变化即拒绝
  陈旧结果并保留上一活动状态（不发布新事实/Profile）。
- 空输出、整页遗漏、虚构 Span、跨节点定位均在门禁中失败，不生成空 Profile；
  迟到回包由租约 generation/有效期丢弃，交由恢复器从最后成功 Checkpoint 重放。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.agents.evidence_normalizer import (
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
    evidence_normalizer_prompt_template_sha256,
    validate_evidence_normalizer_model_config,
)
from app.domain.contracts.agents import ModelConfigContract, PromptVersion
from app.domain.contracts.enums import AgentNode, FactNormalizationRunStatus
from app.domain.contracts.facts import FactAuthority, fact_run_idempotency_key
from app.domain.publication import canonical_hash
from app.services.evidence_app_errors import app_error_boundary
from app.storage.codecs import utc_now, verify_payload_sha256
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.fact_repositories import FactNormalizationRunRepository
from app.storage.facts_models import FactNormalizationRunRecord
from app.storage.models import JobRecord
from app.storage.idempotency import IdempotencyRepository, request_hash
from app.storage.repositories import (
    MODEL_CONFIG_CONFIG,
    PROMPT_VERSION_CONFIG,
    AppendRepository,
)
from app.workflow.errors import InvalidJobDefinitionError
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobStore
from app.workflow.states import backoff_delay


def _now_utc() -> datetime:
    return datetime.now(UTC)



FACT_NORMALIZATION_JOB_TYPE = "fact_normalization"
FACT_NORMALIZATION_IDEMPOTENCY_SCOPE = "fact_normalization"
FACT_NORMALIZATION_FINALIZE_STEP_ID = "finalize"

# 内部稳定失败码；界面通过中文错误投影展示，不直接暴露这些代码。
STALE_AUTHORITY_CODE = "STALE_AUTHORITY"
EMPTY_OUTPUT_CODE = "EMPTY_OUTPUT"
PARTIAL_OUTPUT_CODE = "PARTIAL_OUTPUT"
LATE_REPLY_CODE = "LATE_REPLY"
DUPLICATE_REQUEST_CODE = "DUPLICATE_REQUEST"
_FACT_NORMALIZATION_CONTRACT_VERSION = "phase5/facts/v1"


@dataclass(frozen=True)
class FactNormalizationCallSpec:
    """逻辑文档调用切片：连续页组，显式页清单。"""

    logical_document_id: str
    page_numbers: list[int]
    input_sha256: str  # 有效文本/输入范围的稳定哈希

    def as_dict(self) -> dict[str, Any]:
        return {
            "logical_document_id": self.logical_document_id,
            "page_numbers": sorted(self.page_numbers),
            "input_sha256": self.input_sha256,
        }

    @classmethod
    def from_planned_call(cls, call) -> "FactNormalizationCallSpec":
        return cls(
            logical_document_id=call.logical_document_id,
            page_numbers=list(call.page_numbers),
            input_sha256=call.input_sha256,
        )


@dataclass(frozen=True)
class CreateNormalizationJobResult:
    job_id: str
    run_id: str
    idempotency_key: str
    created: bool
    status: str


def _compute_input_scope_sha256(
    authority: FactAuthority,
    calls: list[FactNormalizationCallSpec],
    *,
    max_pages_per_call: int = 20,
    visual_observation_scope_sha256: str | None = None,
) -> str:
    """与确定性规划层一致的唯一输入范围哈希。

    ``visual_observation_scope_sha256`` 非空时把视觉观察范围缝合成运行输入
    身份的一部分（幂等键随观察集变化）；为 ``None`` 时与旧页级范围逐字节一致，
    既有无观察任务的重建与回归不受影响。
    """
    payload = {
        "input_scope/v2": True,
        "contract_version": "phase5/facts/v1",
        "authority": authority.model_dump(mode="json"),
        "max_pages_per_call": max_pages_per_call,
        "calls": [
            c.as_dict()
            for c in sorted(
                calls, key=lambda x: (x.logical_document_id, x.page_numbers)
            )
        ],
    }
    if visual_observation_scope_sha256 is not None:
        payload["visual_observation_scope_sha256"] = visual_observation_scope_sha256
    return canonical_hash(payload)


def _job_payload_hash(payload: dict[str, Any]) -> str:
    return request_hash(payload)


def _validate_call_specs(calls: list[FactNormalizationCallSpec]) -> None:
    if not calls:
        raise InvalidJobDefinitionError("规范化调用切片不能为空")
    seen_pages: set[tuple[str, int]] = set()
    by_document: dict[str, list[int]] = {}
    for spec in calls:
        if not spec.logical_document_id or not spec.logical_document_id.strip():
            raise InvalidJobDefinitionError("调用逻辑文档编号不能为空")
        if not spec.page_numbers:
            raise InvalidJobDefinitionError(f"调用 {spec.logical_document_id} 页清单不能为空")
        if spec.page_numbers != sorted(set(spec.page_numbers)):
            raise InvalidJobDefinitionError(f"调用 {spec.logical_document_id} 页清单必须升序且无重复")
        if any(p < 1 for p in spec.page_numbers):
            raise InvalidJobDefinitionError(f"调用 {spec.logical_document_id} 页码必须从 1 起")
        if len(spec.input_sha256) != 64 or any(c not in "0123456789abcdef" for c in spec.input_sha256):
            raise InvalidJobDefinitionError(f"调用 {spec.logical_document_id} 的 input_sha256 必须是 64 位十六进制")
        if spec.page_numbers != list(range(spec.page_numbers[0], spec.page_numbers[-1] + 1)):
            raise InvalidJobDefinitionError(f"调用 {spec.logical_document_id} 的页组必须连续")
        for page_number in spec.page_numbers:
            key = (spec.logical_document_id, page_number)
            if key in seen_pages:
                raise InvalidJobDefinitionError(
                    f"逻辑文档 {spec.logical_document_id} 页 {page_number} 被多个调用重复覆盖"
                )
            seen_pages.add(key)
            by_document.setdefault(spec.logical_document_id, []).append(page_number)
    for logical_document_id, pages in by_document.items():
        ordered = sorted(pages)
        if ordered != list(range(ordered[0], ordered[-1] + 1)):
            raise InvalidJobDefinitionError(
                f"逻辑文档 {logical_document_id} 的调用之间存在页码间隙"
            )


def _validate_registered_agent_config(
    session: Session,
    *,
    prompt_version_id: str,
    model_config_id: str,
    prompt_template: str,
) -> None:
    """创建或复用任务前核对实际提示词和完整模型行为配置。"""
    try:
        prompt = AppendRepository(session, PROMPT_VERSION_CONFIG).get(
            prompt_version_id
        )
        model_config = AppendRepository(session, MODEL_CONFIG_CONFIG).get(
            model_config_id
        )
    except Exception as exc:
        raise InvalidJobDefinitionError(f"无法读取证据规范化配置：{exc}") from exc
    if not isinstance(prompt, PromptVersion) or not isinstance(
        model_config, ModelConfigContract
    ):
        raise InvalidJobDefinitionError("证据规范化配置类型不正确")
    if prompt.node is not AgentNode.EVIDENCE_NORMALIZER:
        raise InvalidJobDefinitionError("所选提示词不属于证据规范化任务")
    if prompt.schema_version_id != _FACT_NORMALIZATION_CONTRACT_VERSION:
        raise InvalidJobDefinitionError("所选提示词与当前输出结构版本不一致")
    if prompt.template_sha256 != evidence_normalizer_prompt_template_sha256(
        prompt_template
    ):
        raise InvalidJobDefinitionError("所选提示词内容与当前证据规范化模板不一致")
    try:
        validate_evidence_normalizer_model_config(model_config)
    except ValueError as exc:
        raise InvalidJobDefinitionError(str(exc)) from exc


def _build_step_specs(calls: list[FactNormalizationCallSpec]) -> list[dict[str, Any]]:
    """为每个调用生成稳定步骤声明；最终步骤在同一事务中聚合门禁并发布。"""
    steps: list[dict[str, Any]] = []
    for idx, spec in enumerate(sorted(calls, key=lambda c: (c.logical_document_id, c.page_numbers))):
        safe_doc = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in spec.logical_document_id)[:48]
        step_id = f"normalize_{idx:03d}_{safe_doc}"
        if len(step_id) > 120:
            step_id = f"normalize_{idx:03d}_{hashlib.sha256(safe_doc.encode()).hexdigest()[:16]}"
        steps.append(
            {
                "step_id": step_id,
                "name": f"规范化 {spec.logical_document_id} 页 {spec.page_numbers[0]}-{spec.page_numbers[-1]}" if len(spec.page_numbers) > 1 else f"规范化 {spec.logical_document_id} 页 {spec.page_numbers[0]}",
                "max_attempts": 3,
                "retryable": True,
            }
        )
    depends = tuple(s["step_id"] for s in steps)
    steps.append(
        {
            "step_id": FACT_NORMALIZATION_FINALIZE_STEP_ID,
            "name": "聚合校验与事实发布",
            "max_attempts": 1,
            "retryable": False,
            "depends_on": depends,
        }
    )
    return steps


def _build_persisted_calls(calls: list[FactNormalizationCallSpec], run_id: str) -> list[dict[str, Any]]:
    """为每个调用生成确定性 call_id 并落入 job payload，实现幂等重放。"""
    persisted: list[dict[str, Any]] = []
    for spec in sorted(calls, key=lambda c: (c.logical_document_id, c.page_numbers)):
        # call_id 用 run_id + 逻辑文档 + 页清单的稳定哈希截断，保证同一 run 内唯一且可重建
        material = {
            "run_id": run_id,
            "logical_document_id": spec.logical_document_id,
            "page_numbers": sorted(spec.page_numbers),
        }
        call_id = "call_" + canonical_hash(material)[:24]
        persisted.append(
            {
                "call_id": call_id,
                "logical_document_id": spec.logical_document_id,
                "page_numbers": sorted(spec.page_numbers),
                "input_sha256": spec.input_sha256,
            }
        )
    return persisted


class FactNormalizationJobService:
    """持久规范化任务的应用服务：幂等创建、权威校验、步骤声明与恢复入口。"""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        now=utc_now,
        lease_ttl: timedelta = DEFAULT_LEASE_TTL,
        backoff=backoff_delay,
        prompt_template: str = DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
    ) -> None:
        self.session_factory = session_factory
        self.now = now
        self.lease_ttl = lease_ttl
        self.backoff = backoff
        self.prompt_template = prompt_template

    def _store(self, session: Session) -> JobStore:
        return JobStore(session, now=self.now, lease_ttl=self.lease_ttl, backoff=self.backoff)

    def create_or_reuse_from_source(
        self,
        *,
        authority: FactAuthority,
        prompt_version_id: str,
        model_config_id: str,
        created_by: str,
        max_pages_per_call: int = 20,
        page_review_coverage_id: str | None = None,
        include_visual_sources: bool = False,
        verified_scope_prompt: bool = False,
    ) -> CreateNormalizationJobResult:
        """从活动完整处理修订生成计划，避免调用方自行拼接页组或输入哈希。

        同时按最小来源保真合同收集成功视觉观察：无匹配观察时任务键与任务
        载荷和旧链路逐字节一致；有匹配观察时把观察范围哈希缝入运行输入身份
        并冻结进任务载荷，观察集不同的运行不会误判为重复请求。
        """
        from app.services.fact_normalization_source_adapter import (
            build_fact_normalization_plan,
            build_evidence_normalizer_input,
            collect_visual_observation_attachments,
            visual_observation_run_scope,
        )

        with self.session_factory() as session:
            plan, source = build_fact_normalization_plan(
                session,
                authority=authority,
                revision_id=authority.complete_processing_revision_id,
                max_pages_per_call=max_pages_per_call,
            )
            attachments = (
                ()
                if page_review_coverage_id is not None
                else collect_visual_observation_attachments(
                    session,
                    revision=source.revision,
                    doc_version_to_logical=source.doc_version_to_logical,
                )
            )
            if page_review_coverage_id is None:
                calls = [
                    FactNormalizationCallSpec.from_planned_call(call)
                    for call in plan.calls
                ]
            else:
                calls = [
                    FactNormalizationCallSpec(
                        logical_document_id=call.logical_document_id,
                        page_numbers=list(call.page_numbers),
                        input_sha256=build_evidence_normalizer_input(
                            session,
                            authority=authority,
                            run_id="scope-only",
                            call_id="scope-only",
                            logical_document_id=call.logical_document_id,
                            page_numbers=list(call.page_numbers),
                            expected_input_sha256=None,
                            max_pages_per_call=max_pages_per_call,
                            page_review_coverage_id=page_review_coverage_id,
                            include_visual_sources=include_visual_sources,
                        ).input_scope_sha256,
                    )
                    for call in plan.calls
                ]
        vision_scope = visual_observation_run_scope(attachments)
        if vision_scope is None:
            input_scope = (
                plan.input_scope_sha256
                if page_review_coverage_id is None
                else _compute_input_scope_sha256(
                    authority, calls, max_pages_per_call=max_pages_per_call
                )
            )
            return self.create_or_reuse_job(
                authority=authority,
                prompt_version_id=prompt_version_id,
                model_config_id=model_config_id,
                calls=calls,
                input_scope_sha256=input_scope,
                created_by=created_by,
                max_pages_per_call=max_pages_per_call,
                page_review_coverage_id=page_review_coverage_id,
                include_visual_sources=include_visual_sources,
                verified_scope_prompt=verified_scope_prompt,
            )
        stitched_scope = _compute_input_scope_sha256(
            authority,
            calls,
            max_pages_per_call=max_pages_per_call,
            visual_observation_scope_sha256=vision_scope,
        )
        return self.create_or_reuse_job(
            authority=authority,
            prompt_version_id=prompt_version_id,
            model_config_id=model_config_id,
            calls=calls,
            input_scope_sha256=stitched_scope,
            visual_observation_scope_sha256=vision_scope,
            created_by=created_by,
            max_pages_per_call=max_pages_per_call,
            page_review_coverage_id=page_review_coverage_id,
            verified_scope_prompt=verified_scope_prompt,
        )

    @app_error_boundary
    def create_or_reuse_job(
        self,
        *,
        authority: FactAuthority,
        prompt_version_id: str,
        model_config_id: str,
        input_scope_sha256: str | None = None,
        calls: list[FactNormalizationCallSpec],
        created_by: str,
        idempotency_key: str | None = None,
        max_pages_per_call: int = 20,
        visual_observation_scope_sha256: str | None = None,
        page_review_coverage_id: str | None = None,
        include_visual_sources: bool = False,
        verified_scope_prompt: bool = False,
    ) -> CreateNormalizationJobResult:
        """幂等创建规范化 Job 与冻结的 FactNormalizationRun。

        ``visual_observation_scope_sha256`` 为 64 位十六进制时缝入幂等键并写入
        任务载荷（执行期据此复核观察清单未被漂移）；为 ``None`` 时保持旧键与
        旧载荷形状不变。
        """
        _validate_call_specs(calls)
        if not prompt_version_id or not prompt_version_id.strip():
            raise InvalidJobDefinitionError("PromptVersion 不能为空")
        if not model_config_id or not model_config_id.strip():
            raise InvalidJobDefinitionError("ModelConfig 不能为空")
        if not created_by or not created_by.strip():
            raise InvalidJobDefinitionError("创建者不能为空")
        if max_pages_per_call < 1:
            raise InvalidJobDefinitionError("单次规范化页数必须大于零")
        if visual_observation_scope_sha256 is not None:
            scope_value = visual_observation_scope_sha256
            if len(scope_value) != 64 or any(c not in "0123456789abcdef" for c in scope_value):
                raise InvalidJobDefinitionError("视觉观察范围哈希必须是 64 位十六进制")
        if page_review_coverage_id is not None and not page_review_coverage_id.strip():
            raise InvalidJobDefinitionError("页级判读覆盖身份不能为空")

        computed_scope = _compute_input_scope_sha256(
            authority,
            calls,
            max_pages_per_call=max_pages_per_call,
            visual_observation_scope_sha256=visual_observation_scope_sha256,
        )
        if input_scope_sha256 is not None and input_scope_sha256 != computed_scope:
            raise InvalidJobDefinitionError("input_scope_sha256 与调用切片的冻结内容不一致")
        effective_scope = computed_scope
        if include_visual_sources and page_review_coverage_id is None:
            raise InvalidJobDefinitionError("视觉来源必须绑定双模型判读结果")
        if verified_scope_prompt and not include_visual_sources:
            raise InvalidJobDefinitionError("已核实观察整理必须绑定原件双读来源")
        strategy = None
        if page_review_coverage_id is not None:
            from app.projections.page_review_pending_normalization import PENDING_NORMALIZATION_POLICY
            effective_scope = canonical_hash({
                "input_scope_sha256": computed_scope,
                "pending_normalization_policy": PENDING_NORMALIZATION_POLICY,
            })
        if include_visual_sources:
            from app.services.page_review_visual_sources import VISUAL_SOURCE_POLICY
            effective_scope = canonical_hash({"input_scope_sha256": effective_scope,
                                              "visual_source_policy": VISUAL_SOURCE_POLICY})
        if verified_scope_prompt:
            from app.agents.verified_evidence_prompt import verified_evidence_strategy
            strategy = verified_evidence_strategy()
            effective_scope = canonical_hash({"input_scope_sha256": effective_scope,
                                              "verified_evidence_strategy": strategy})
        if len(effective_scope) != 64 or any(c not in "0123456789abcdef" for c in effective_scope):
            raise InvalidJobDefinitionError("input_scope_sha256 必须是 64 位十六进制")

        expected_key = fact_run_idempotency_key(
            authority=authority,
            prompt_version_id=prompt_version_id,
            model_config_id=model_config_id,
            input_scope_sha256=effective_scope,
        )
        effective_key = idempotency_key or expected_key
        if effective_key != expected_key:
            raise InvalidJobDefinitionError("幂等键与权威元组/PromptVersion/ModelConfig/输入范围不一致")

        sorted_calls_payload = [c.as_dict() for c in sorted(calls, key=lambda x: (x.logical_document_id, x.page_numbers))]
        job_request_payload = {
            "idempotency_key": effective_key,
            "authority": authority.model_dump(mode="json"),
            "prompt_version_id": prompt_version_id,
            "model_config_id": model_config_id,
            "input_scope_sha256": effective_scope,
            "calls": sorted_calls_payload,
            "max_pages_per_call": max_pages_per_call,
        }
        if visual_observation_scope_sha256 is not None:
            # 仅在确有视觉材料时新增载荷字段：无观察任务保持与旧链路逐字节一致，
            # 升级后同键重放不会因请求哈希漂移误报幂等冲突。
            job_request_payload["visual_observation_scope_sha256"] = (
                visual_observation_scope_sha256
            )
        if page_review_coverage_id is not None:
            job_request_payload["page_review_coverage_id"] = page_review_coverage_id
            job_request_payload["pending_normalization_policy"] = PENDING_NORMALIZATION_POLICY
        submitted_hash = _job_payload_hash(job_request_payload)
        if strategy is not None:
            job_request_payload["verified_evidence_strategy"] = strategy
            submitted_hash = _job_payload_hash(job_request_payload)
        if include_visual_sources:
            job_request_payload["visual_source_policy"] = VISUAL_SOURCE_POLICY
            submitted_hash = _job_payload_hash(job_request_payload)

        with self.session_factory() as session, session.begin():
            _validate_registered_agent_config(
                session,
                prompt_version_id=prompt_version_id,
                model_config_id=model_config_id,
                prompt_template=self.prompt_template,
            )
            idem = IdempotencyRepository(session)
            job_id = uuid4().hex
            record, created = idem.resolve(
                scope=FACT_NORMALIZATION_IDEMPOTENCY_SCOPE,
                idempotency_key=effective_key,
                submitted_hash=submitted_hash,
                result_type="fact_normalization_job",
                result_id=job_id,
            )
            if not created:
                store = self._store(session)
                job = store.get_job(record.result_id)
                payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
                existing_run_id = str(payload.get("run_id") or payload.get("runId") or "")
                if not existing_run_id:
                    existing_run_id = self._lookup_run_id_by_key(session, effective_key) or record.result_id
                return CreateNormalizationJobResult(
                    job_id=record.result_id,
                    run_id=existing_run_id,
                    idempotency_key=effective_key,
                    created=False,
                    status=job.state,
                )

            validator = FactAuthorityValidator(session)
            validator.validate(authority)
            if include_visual_sources:
                from app.services.page_review_visual_sources import persist_visual_locators
                persist_visual_locators(session, authority, page_review_coverage_id)

            from app.domain.contracts.enums import FactNormalizationRunStatus
            from app.domain.contracts.facts import FactNormalizationRun

            run_id = uuid4().hex
            run = FactNormalizationRun(
                run_id=run_id,
                authority=authority,
                idempotency_key=effective_key,
                prompt_version_id=prompt_version_id,
                model_config_id=model_config_id,
                input_scope_sha256=effective_scope,
                status=FactNormalizationRunStatus.RUNNING,
                created_at=_now_utc(),
                created_by=created_by,
            )
            repo = FactNormalizationRunRepository(session)
            persisted_run = repo.create_or_reuse(run)
            actual_run_id = persisted_run.run_id

            persisted_calls = _build_persisted_calls(calls, actual_run_id)

            job_payload = {
                "run_id": actual_run_id,
                "idempotency_key": effective_key,
                "authority": authority.model_dump(mode="json"),
                "prompt_version_id": prompt_version_id,
                "model_config_id": model_config_id,
                "input_scope_sha256": effective_scope,
                "calls": persisted_calls,
                "max_pages_per_call": max_pages_per_call,
            }
            if visual_observation_scope_sha256 is not None:
                job_payload["visual_observation_scope_sha256"] = (
                    visual_observation_scope_sha256
                )
            if page_review_coverage_id is not None:
                job_payload["page_review_coverage_id"] = page_review_coverage_id
                job_payload["pending_normalization_policy"] = PENDING_NORMALIZATION_POLICY
            step_defs = _build_step_specs(calls)
            if strategy is not None:
                job_payload["verified_evidence_strategy"] = strategy
            if include_visual_sources:
                job_payload["visual_source_policy"] = VISUAL_SOURCE_POLICY
            store = self._store(session)
            store.create_job(
                job_id=job_id,
                job_type=FACT_NORMALIZATION_JOB_TYPE,
                payload=job_payload,
                progress_total=len(step_defs),
            )
            for s in step_defs:
                store.create_step(
                    step_id=s["step_id"],
                    job_id=job_id,
                    name=s["name"],
                    max_attempts=s.get("max_attempts", 1),
                    retryable=s.get("retryable", False),
                )
            for s in step_defs:
                if s.get("depends_on"):
                    store.add_step_dependencies(
                        job_id=job_id,
                        step_id=s["step_id"],
                        depends_on=tuple(s["depends_on"]),
                    )
            from app.domain.contracts.enums import JobEventType

            store.append_event(
                store.make_event(
                    job_id=job_id,
                    event_type=JobEventType.CREATED,
                    progress_total=len(step_defs),
                    payload={"job_type": FACT_NORMALIZATION_JOB_TYPE, "run_id": actual_run_id},
                )
            )
            self._link_run_job_if_empty(session, actual_run_id, job_id)
            return CreateNormalizationJobResult(
                job_id=job_id,
                run_id=actual_run_id,
                idempotency_key=effective_key,
                created=True,
                status="queued",
            )

    def _lookup_run_id_by_key(self, session: Session, key: str) -> str | None:
        row = session.execute(select(FactNormalizationRunRecord).where(FactNormalizationRunRecord.idempotency_key == key)).scalars().first()
        return row.run_id if row is not None else None

    def _link_run_job_if_empty(self, session: Session, run_id: str, job_id: str) -> None:
        session.execute(update(FactNormalizationRunRecord).where(FactNormalizationRunRecord.run_id == run_id, FactNormalizationRunRecord.job_id.is_(None)).values(job_id=job_id))
        session.flush()

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self.session_factory() as session:
            store = self._store(session)
            job = store.get_job(job_id)
            payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
            return {
                "job_id": job.job_id,
                "job_type": job.job_type,
                "state": job.state,
                "payload": payload,
                "progress_total": job.progress_total,
                "progress_completed": job.progress_completed,
            }

    def cancel(self, job_id: str):
        with self.session_factory() as session, session.begin():
            outcome = self._store(session).request_cancel(job_id)
        if outcome.changed and outcome.state == "cancelled":
            project_fact_normalization_run_status(
                self.session_factory,
                job_id,
                FactNormalizationRunStatus.CANCELLED,
            )
        return outcome

    def retry(self, job_id: str):
        with self.session_factory() as session, session.begin():
            store = self._store(session)
            job = store.get_job(job_id)
            if job.job_type != FACT_NORMALIZATION_JOB_TYPE:
                raise InvalidJobDefinitionError("该任务不属于个例资料整理")
            row = session.execute(
                select(FactNormalizationRunRecord).where(
                    FactNormalizationRunRecord.job_id == job_id
                )
            ).scalars().one_or_none()
            if row is None:
                raise InvalidJobDefinitionError("个例资料整理任务缺少对应运行记录")
            previous_job_state = job.state
            outcome = (
                store.resume_cancelled(job_id)
                if job.state == "cancelled"
                else store.retry_failed(job_id)
            )
            repository = FactNormalizationRunRepository(session)
            run = repository.get(row.run_id)
            # Retryable step failure does not close the normalization run.
            # The job-store transition above still enforces state and lease checks.
            if not (
                previous_job_state == "failed_retryable"
                and run.status == FactNormalizationRunStatus.RUNNING
            ):
                repository.reopen_for_retry(row.run_id)
            return outcome


def project_fact_normalization_run_status(
    session_factory: sessionmaker[Session],
    job_id: str,
    status: FactNormalizationRunStatus,
) -> None:
    """将通用任务终态投影到对应事实规范化运行；非本类任务为空操作。"""
    with session_factory() as session, session.begin():
        row = session.execute(
            select(FactNormalizationRunRecord).where(
                FactNormalizationRunRecord.job_id == job_id
            )
        ).scalars().one_or_none()
        if row is None:
            return
        run = FactNormalizationRunRepository(session).get(row.run_id)
        if run.status is not FactNormalizationRunStatus.RUNNING:
            return
        FactNormalizationRunRepository(session).set_status(row.run_id, status)


def recover_fact_normalization_runs(
    session_factory: sessionmaker[Session],
) -> None:
    """启动时收敛已终止 Job 对应的事实规范化运行状态。"""
    with session_factory() as session, session.begin():
        rows = session.execute(
            select(FactNormalizationRunRecord, JobRecord)
            .join(JobRecord, JobRecord.job_id == FactNormalizationRunRecord.job_id)
            .where(FactNormalizationRunRecord.status == "running")
        ).all()
        repository = FactNormalizationRunRepository(session)
        for run_row, job_row in rows:
            if job_row.state == "cancelled":
                repository.set_status(
                    run_row.run_id, FactNormalizationRunStatus.CANCELLED
                )
            elif job_row.state == "failed_final":
                repository.set_status(
                    run_row.run_id, FactNormalizationRunStatus.FAILED
                )
