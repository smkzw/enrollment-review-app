"""Durable, resumable execution of frozen phase-applicability batches.

This service deliberately uses the existing phase contracts, planner, Agent
Runner, and deterministic gate.  It adds only a small atomic JSON checkpoint
store because this acceptance path must be usable before a dedicated database
repository exists.  The persisted state contains the complete coverage
manifest and frozen plan, not just the ambiguous target IDs.

The service never turns a missing or rejected result into ``SHARED``.  A batch
is publishable only when the existing Runner has returned a gated
``PhaseApplicabilityResolutionSet``; failed and unresolved batches remain
recoverable ``needs_review`` records.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from app.agents.phase_applicability import (
    DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE,
    PhaseApplicabilityAgentAttempt,
    PhaseApplicabilityAgentInput,
    PhaseApplicabilityAgentRunResult,
    PhaseApplicabilityAgentRunner,
    PhaseApplicabilityAgentTransport,
    phase_applicability_agent_prompt_template_sha256,
)
from app.domain.contracts.common import ContractModel
from app.domain.contracts.phase_applicability import (
    PhaseApplicabilityResolutionSet,
)
from app.domain.contracts.protocol_controls import (
    ProtocolSectionCoverageManifest,
)
from app.protocols.phase_applicability_planning import (
    PHASE_APPLICABILITY_PLAN_V1_VERSION,
    PhaseApplicabilityFrozenPlan,
    plan_phase_applicability_batches,
)
from app.protocols.phase_applicability import PHASE_APPLICABILITY_GATE_VERSION


PHASE_APPLICABILITY_EXECUTION_VERSION = (
    "phase5/phase-applicability-execution/v1"
)
_LEGACY_PHASE_APPLICABILITY_GATE_VERSION = "phase5/phase-applicability-gate/v1"

__all__ = [
    "PHASE_APPLICABILITY_EXECUTION_VERSION",
    "PhaseApplicabilityBatchExecutionRecord",
    "PhaseApplicabilityExecutionError",
    "PhaseApplicabilityExecutionService",
    "PhaseApplicabilityExecutionState",
    "PhaseApplicabilityExecutionStore",
    "PhaseApplicabilityBatchExecutor",
    "create_phase_applicability_execution",
    "run_phase_applicability_execution",
]


_SHA256 = r"^[0-9a-f]{64}$"
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_BATCH_STATUSES = Literal["pending", "running", "accepted", "needs_review"]
_EXECUTION_STATUSES = Literal["planned", "running", "completed", "needs_review"]


class PhaseApplicabilityExecutionError(ValueError):
    """A durable execution or checkpoint identity error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _execution_plan_payload(plan: PhaseApplicabilityFrozenPlan) -> dict[str, object]:
    payload = plan.model_dump(mode="json")
    if plan.schema_version == PHASE_APPLICABILITY_PLAN_V1_VERSION:
        # Historical execution scopes were hashed before v2 added the
        # explicit packing policy field.  Preserve that immutable identity.
        payload.pop("batch_packing_policy", None)
    return payload


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _transport_identity(transport: PhaseApplicabilityAgentTransport) -> dict[str, str]:
    """Persist non-secret provider/model identity for deterministic resume."""

    def value(name: str) -> str | None:
        public = getattr(transport, name, None)
        if public is not None:
            return str(public)
        private = getattr(transport, f"_{name}", None)
        return str(private) if private is not None else None

    transport_type = type(transport)
    identity = {
        "transport_type": (
            f"{transport_type.__module__}.{transport_type.__qualname__}"
        ),
    }
    for field_name in (
        "provider",
        "backend",
        "model",
        "reasoning_effort",
        "max_tokens",
        "base_url",
        "temperature",
        "timeout",
        "max_retries",
        "response_format_sha256",
    ):
        field_value = value(field_name)
        if field_value:
            identity[field_name] = field_value
    return identity


class PhaseApplicabilityBatchExecutionRecord(ContractModel):
    """One package checkpoint; attempts are append-only across retries."""

    schema_version: Literal[PHASE_APPLICABILITY_EXECUTION_VERSION] = (
        PHASE_APPLICABILITY_EXECUTION_VERSION
    )
    package_id: str = Field(min_length=1)
    package_ordinal: int = Field(ge=1)
    owned_structure_unit_ids: list[str] = Field(min_length=1)
    status: _BATCH_STATUSES = "pending"
    run_results: list[PhaseApplicabilityAgentRunResult] = Field(default_factory=list)
    final_output: PhaseApplicabilityResolutionSet | None = None
    raw_output_sha256: list[str] = Field(default_factory=list)
    last_session_id: str | None = Field(default=None, min_length=1)
    last_error: str | None = Field(default=None, min_length=1)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    recovery_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_record(self) -> "PhaseApplicabilityBatchExecutionRecord":
        if len(self.owned_structure_unit_ids) != len(
            set(self.owned_structure_unit_ids)
        ):
            raise ValueError("批次 owned 结构单元不得重复")
        if any(
            len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in self.raw_output_sha256
        ):
            raise ValueError("批次 raw output 哈希必须是小写 SHA-256")
        if self.status == "accepted":
            if self.final_output is None:
                raise ValueError("已接受批次必须保留 gated final_output")
            if self.final_output.package_id != self.package_id:
                raise ValueError("批次 final_output 与 package_id 不一致")
            if self.last_error is not None:
                raise ValueError("已接受批次不得保留未清除的错误")
        elif self.final_output is not None:
            raise ValueError("未接受批次不得保留 final_output")
        if self.final_output is not None and self.final_output.package_id != self.package_id:
            raise ValueError("批次 final_output 与 package_id 不一致")
        for run_result in self.run_results:
            if run_result.package_id != self.package_id:
                raise ValueError("批次 run_result 与 package_id 不一致")
        if self.finished_at is not None and self.started_at is not None:
            if self.finished_at < self.started_at:
                raise ValueError("批次 finished_at 不能早于 started_at")
        return self

    @property
    def attempt_count(self) -> int:
        return sum(len(result.attempts) for result in self.run_results)

    @property
    def issue_count(self) -> int:
        return sum(
            len(attempt.issues)
            for result in self.run_results
            for attempt in result.attempts
        )


class PhaseApplicabilityExecutionState(ContractModel):
    """Complete immutable-input plus mutable-checkpoint execution snapshot."""

    schema_version: Literal[PHASE_APPLICABILITY_EXECUTION_VERSION] = (
        PHASE_APPLICABILITY_EXECUTION_VERSION
    )
    run_id: str = Field(min_length=1, max_length=128)
    input_scope_sha256: str = Field(pattern=_SHA256)
    prompt_template_sha256: str = Field(pattern=_SHA256)
    gate_version: str = Field(default=_LEGACY_PHASE_APPLICABILITY_GATE_VERSION, min_length=1)
    transport_identity: dict[str, str] = Field(default_factory=dict)
    coverage_manifest: ProtocolSectionCoverageManifest
    plan: PhaseApplicabilityFrozenPlan
    status: _EXECUTION_STATUSES = "planned"
    batches: list[PhaseApplicabilityBatchExecutionRecord] = Field(
        default_factory=list
    )
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_state(self) -> "PhaseApplicabilityExecutionState":
        if not _RUN_ID_RE.fullmatch(self.run_id):
            raise ValueError("run_id 含有不安全或不支持的字符")
        if any(
            not key.strip() or not value.strip()
            for key, value in self.transport_identity.items()
        ):
            raise ValueError("持久 transport identity 不得包含空键或空值")
        manifest = self.coverage_manifest
        plan = self.plan
        if plan.coverage_manifest_id != manifest.manifest_id:
            raise ValueError("持久计划与全文清单 manifest_id 不一致")
        if plan.protocol_version_id != manifest.protocol_version_id:
            raise ValueError("持久计划与全文清单 protocol_version_id 不一致")
        if plan.study_phase != manifest.study_phase:
            raise ValueError("持久计划与全文清单 study_phase 不一致")
        if any(
            package.protocol_document_sha256 != manifest.protocol_document_sha256
            or package.snapshot_id != manifest.snapshot_id
            for package in plan.packages
        ):
            raise ValueError("冻结批次来源哈希或 snapshot 与全文清单不一致")
        scope_payload = {
            "execution_version": PHASE_APPLICABILITY_EXECUTION_VERSION,
            "coverage_manifest": manifest.model_dump(mode="json"),
            "plan": _execution_plan_payload(plan),
        }
        if self.gate_version != _LEGACY_PHASE_APPLICABILITY_GATE_VERSION:
            scope_payload["gate_version"] = self.gate_version
        expected_scope_hash = _sha256_json(scope_payload)
        if self.input_scope_sha256 != expected_scope_hash:
            raise ValueError("持久 execution input_scope_sha256 与冻结输入不一致")

        manifest_units = {
            unit.structure_unit_id: unit for unit in manifest.units
        }
        expected_agent_ids = set(plan.expected_structure_unit_ids)
        if not expected_agent_ids <= set(manifest_units):
            raise ValueError("冻结计划 expected_structure_unit_ids 超出全文清单")
        for package in plan.packages:
            for package_unit in package.all_units:
                manifest_unit = manifest_units.get(package_unit.structure_unit_id)
                if manifest_unit is None:
                    raise ValueError("冻结批次引用了全文清单外结构单元")
                if manifest_unit != package_unit:
                    raise ValueError("冻结批次结构单元内容与全文清单不一致")

        expected_packages = list(plan.packages)
        if len(self.batches) != len(expected_packages):
            raise ValueError("持久批次记录必须与冻结计划逐批对应")
        for record, package in zip(self.batches, expected_packages):
            if record.package_id != package.package_id:
                raise ValueError("持久批次 package_id 与冻结计划不一致")
            if record.package_ordinal != package.package_ordinal:
                raise ValueError("持久批次序号与冻结计划不一致")
            if record.owned_structure_unit_ids != list(package.owned_structure_unit_ids):
                raise ValueError("持久批次 owned 身份与冻结计划不一致")
        if self.status == "completed" and any(
            record.status != "accepted" for record in self.batches
        ):
            raise ValueError("未逐批接受时不得标记 execution completed")
        return self

    @property
    def accepted_package_ids(self) -> tuple[str, ...]:
        return tuple(
            record.package_id
            for record in self.batches
            if record.status == "accepted"
        )

    @property
    def accepted_structure_unit_ids(self) -> tuple[str, ...]:
        return tuple(
            unit_id
            for record in self.batches
            if record.status == "accepted"
            for unit_id in record.owned_structure_unit_ids
        )

    @property
    def unresolved_structure_unit_ids(self) -> tuple[str, ...]:
        accepted = set(self.accepted_structure_unit_ids)
        return tuple(
            unit.structure_unit_id
            for unit in self.coverage_manifest.units
            if unit.structure_unit_id in set(self.plan.expected_structure_unit_ids)
            and unit.structure_unit_id not in accepted
        )

    @property
    def final_outputs(self) -> tuple[PhaseApplicabilityResolutionSet, ...]:
        return tuple(
            record.final_output
            for record in self.batches
            if record.final_output is not None
        )


class PhaseApplicabilityExecutionStore:
    """Atomic JSON store scoped to an explicit directory or JSON file."""

    def __init__(self, path: str | Path) -> None:
        resolved = Path(path)
        if resolved.name in {"", ".", ".."}:
            raise ValueError("期别语义 execution store 路径不能为空")
        self._path = resolved

    @property
    def path(self) -> Path:
        return self._path

    def path_for(self, run_id: str) -> Path:
        if not _RUN_ID_RE.fullmatch(run_id):
            raise PhaseApplicabilityExecutionError(
                "RUN_ID_INVALID",
                "run_id 只能包含字母、数字、点、下划线、冒号和短横线",
            )
        if self._path.suffix.lower() == ".json":
            return self._path
        return self._path / f"{run_id}.json"

    def exists(self, run_id: str) -> bool:
        return self.path_for(run_id).is_file()

    def load(self, run_id: str) -> PhaseApplicabilityExecutionState:
        path = self.path_for(run_id)
        if not path.is_file():
            raise PhaseApplicabilityExecutionError(
                "CHECKPOINT_NOT_FOUND",
                f"未找到期别语义 execution checkpoint：{path}",
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return PhaseApplicabilityExecutionState.model_validate(payload)
        except PhaseApplicabilityExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - persisted boundary
            raise PhaseApplicabilityExecutionError(
                "CHECKPOINT_INVALID",
                f"期别语义 execution checkpoint 无法读取：{exc}",
            ) from exc

    def save(self, state: PhaseApplicabilityExecutionState) -> None:
        try:
            validated = PhaseApplicabilityExecutionState.model_validate(
                state.model_dump(mode="json")
            )
        except Exception as exc:  # noqa: BLE001 - checkpoint boundary
            raise PhaseApplicabilityExecutionError(
                "CHECKPOINT_INVALID",
                f"拒绝写入未通过 execution 合同的 checkpoint：{exc}",
            ) from exc
        path = self.path_for(state.run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = validated.model_dump(mode="json")
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = handle.name
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass


def _initial_state(
    *,
    run_id: str,
    coverage_manifest: ProtocolSectionCoverageManifest,
    plan: PhaseApplicabilityFrozenPlan,
    prompt_template: str,
    now: datetime,
) -> PhaseApplicabilityExecutionState:
    input_scope = {
        "execution_version": PHASE_APPLICABILITY_EXECUTION_VERSION,
        "gate_version": PHASE_APPLICABILITY_GATE_VERSION,
        "coverage_manifest": coverage_manifest.model_dump(mode="json"),
        "plan": _execution_plan_payload(plan),
    }
    return PhaseApplicabilityExecutionState(
        run_id=run_id,
        input_scope_sha256=_sha256_json(input_scope),
        prompt_template_sha256=phase_applicability_agent_prompt_template_sha256(
            prompt_template
        ),
        gate_version=PHASE_APPLICABILITY_GATE_VERSION,
        coverage_manifest=coverage_manifest,
        plan=plan,
        status="planned",
        batches=[
            PhaseApplicabilityBatchExecutionRecord(
                package_id=package.package_id,
                package_ordinal=package.package_ordinal,
                owned_structure_unit_ids=list(package.owned_structure_unit_ids),
            )
            for package in plan.packages
        ],
        created_at=now,
        updated_at=now,
    )


class PhaseApplicabilityExecutionService:
    """Prepare, execute and resume a frozen phase-applicability plan."""

    def __init__(
        self,
        store: PhaseApplicabilityExecutionStore,
        *,
        runner: PhaseApplicabilityAgentRunner | None = None,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.store = store
        self.runner = runner or PhaseApplicabilityAgentRunner()
        self.now = now

    def prepare(
        self,
        *,
        run_id: str,
        coverage_manifest: ProtocolSectionCoverageManifest,
        plan: PhaseApplicabilityFrozenPlan | None = None,
        prompt_template: str = DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE,
        max_owned_units_per_batch: int = 12,
        context_radius: int = 1,
    ) -> PhaseApplicabilityExecutionState:
        """Persist the complete input snapshot before any model call."""

        if not prompt_template.strip():
            raise PhaseApplicabilityExecutionError(
                "PROMPT_TEMPLATE_EMPTY",
                "期别语义 execution prompt 不能为空",
            )
        frozen_plan = plan or plan_phase_applicability_batches(
            coverage_manifest,
            max_owned_units_per_batch=max_owned_units_per_batch,
            context_radius=context_radius,
        )
        candidate = _initial_state(
            run_id=run_id,
            coverage_manifest=coverage_manifest,
            plan=frozen_plan,
            prompt_template=prompt_template,
            now=self.now(),
        )
        if self.store.exists(run_id):
            existing = self.store.load(run_id)
            if existing.run_id != run_id:
                raise PhaseApplicabilityExecutionError(
                    "EXECUTION_RUN_ID_CONFLICT",
                    "指定 checkpoint 文件已绑定其他 execution run_id",
                )
            if existing.input_scope_sha256 != candidate.input_scope_sha256:
                raise PhaseApplicabilityExecutionError(
                    "EXECUTION_INPUT_CONFLICT",
                    "已有 execution checkpoint 与本次全文清单或冻结计划不一致",
                )
            if existing.prompt_template_sha256 != candidate.prompt_template_sha256:
                raise PhaseApplicabilityExecutionError(
                    "EXECUTION_PROMPT_CONFLICT",
                    "已有 execution checkpoint 与本次期别语义 prompt 不一致",
                )
            return existing
        self.store.save(candidate)
        return candidate

    def execute(
        self,
        *,
        run_id: str,
        coverage_manifest: ProtocolSectionCoverageManifest,
        transport: PhaseApplicabilityAgentTransport,
        plan: PhaseApplicabilityFrozenPlan | None = None,
        prompt_template: str = DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE,
        max_owned_units_per_batch: int = 12,
        context_radius: int = 1,
    ) -> PhaseApplicabilityExecutionState:
        """Run pending/rejected batches and save a checkpoint after each one."""

        state = self.prepare(
            run_id=run_id,
            coverage_manifest=coverage_manifest,
            plan=plan,
            prompt_template=prompt_template,
            max_owned_units_per_batch=max_owned_units_per_batch,
            context_radius=context_radius,
        )
        if not state.batches:
            state = state.model_copy(update={"status": "completed", "updated_at": self.now()})
            self.store.save(state)
            return state

        transport_identity = _transport_identity(transport)
        if state.transport_identity and state.transport_identity != transport_identity:
            raise PhaseApplicabilityExecutionError(
                "EXECUTION_TRANSPORT_CONFLICT",
                "已有 execution checkpoint 与本次 provider/model transport 不一致",
            )
        if not state.transport_identity:
            state = state.model_copy(
                update={
                    "transport_identity": transport_identity,
                    "updated_at": self.now(),
                }
            )
            self.store.save(state)

        for index, record in enumerate(state.batches):
            if record.status == "accepted":
                continue
            package = state.plan.packages[index]
            started_at = self.now()
            running_record = record.model_copy(
                update={
                    "status": "running",
                    "started_at": started_at,
                    "finished_at": None,
                    "last_error": None,
                    "recovery_count": record.recovery_count + 1,
                }
            )
            state = state.model_copy(
                update={
                    "status": "running",
                    "updated_at": started_at,
                    "batches": [
                        running_record if item_index == index else item
                        for item_index, item in enumerate(state.batches)
                    ],
                },
                deep=True,
            )
            self.store.save(state)

            prior_results = list(running_record.run_results)
            attempt_history: list[PhaseApplicabilityAgentAttempt] = []

            def checkpoint_attempt(
                attempt: PhaseApplicabilityAgentAttempt,
            ) -> None:
                """Persist one completed parse/gate attempt before repair."""

                nonlocal state
                attempt_history.append(attempt)
                partial_result = PhaseApplicabilityAgentRunResult(
                    status="需要核对",
                    package_id=package.package_id,
                    session_id=attempt.session_id,
                    attempts=list(attempt_history),
                )
                attempt_hashes = [
                    item.raw_output_sha256
                    for item in attempt_history
                    if item.outcome != "transport_failed"
                ]
                attempt_issues = [
                    issue
                    for item in attempt_history
                    for issue in item.issues
                ]
                checkpoint_record = running_record.model_copy(
                    update={
                        "run_results": [*prior_results, partial_result],
                        "raw_output_sha256": [
                            *running_record.raw_output_sha256,
                            *attempt_hashes,
                        ],
                        "last_session_id": attempt.session_id,
                        "last_error": (
                            "；".join(attempt_issues)[:4000]
                            if attempt_issues
                            else None
                        ),
                    },
                    deep=True,
                )
                state = state.model_copy(
                    update={
                        "status": "running",
                        "updated_at": self.now(),
                        "batches": [
                            checkpoint_record
                            if item_index == index
                            else item
                            for item_index, item in enumerate(state.batches)
                        ],
                    },
                    deep=True,
                )
                self.store.save(state)

            try:
                agent_input = PhaseApplicabilityAgentInput.from_frozen_package(package)
                result = self.runner.run(
                    agent_input,
                    transport,
                    prompt_template=prompt_template,
                    accepted_package_ids=state.accepted_package_ids,
                    on_attempt=checkpoint_attempt,
                )
            except Exception as exc:  # noqa: BLE001 - recoverable batch boundary
                finished_at = self.now()
                failed_record = state.batches[index].model_copy(
                    update={
                        "status": "needs_review",
                        "finished_at": finished_at,
                        "last_error": f"{type(exc).__name__}: {exc}"[:4000],
                    }
                )
                state = state.model_copy(
                    update={
                        "status": "needs_review",
                        "updated_at": finished_at,
                        "batches": [
                            failed_record if item_index == index else item
                            for item_index, item in enumerate(state.batches)
                        ],
                    },
                    deep=True,
                )
                self.store.save(state)
                continue

            finished_at = self.now()
            raw_hashes = [
                attempt.raw_output_sha256
                for attempt in result.attempts
                if attempt.outcome != "transport_failed"
            ]
            issues = [
                issue
                for attempt in result.attempts
                for issue in attempt.issues
            ]
            accepted = result.final_output is not None and result.status == "已解析"
            completed_record = running_record.model_copy(
                update={
                    "status": "accepted" if accepted else "needs_review",
                    "run_results": [*prior_results, result],
                    "final_output": result.final_output if accepted else None,
                    "raw_output_sha256": [
                        *running_record.raw_output_sha256,
                        *raw_hashes,
                    ],
                    "last_session_id": result.session_id,
                    "last_error": None if accepted else ("；".join(issues)[:4000] or "批次未通过解析或门禁"),
                    "finished_at": finished_at,
                }
            )
            state = state.model_copy(
                update={
                    "status": "running",
                    "updated_at": finished_at,
                    "batches": [
                        completed_record if item_index == index else item
                        for item_index, item in enumerate(state.batches)
                    ],
                },
                deep=True,
            )
            self.store.save(state)

        final_status: _EXECUTION_STATUSES = (
            "completed"
            if all(record.status == "accepted" for record in state.batches)
            else "needs_review"
        )
        state = state.model_copy(update={"status": final_status, "updated_at": self.now()})
        self.store.save(state)
        return state

    # Explicit aliases make the recovery operation discoverable to callers
    # that model it as a run/resume command rather than a service method.
    run = execute
    resume = execute


PhaseApplicabilityBatchExecutor = PhaseApplicabilityExecutionService


def create_phase_applicability_execution(
    *,
    store: PhaseApplicabilityExecutionStore,
    run_id: str,
    coverage_manifest: ProtocolSectionCoverageManifest,
    plan: PhaseApplicabilityFrozenPlan | None = None,
    prompt_template: str = DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE,
    max_owned_units_per_batch: int = 12,
    context_radius: int = 1,
    now: Callable[[], datetime] = _utc_now,
) -> PhaseApplicabilityExecutionState:
    """Convenience function for the pre-model durable freeze step."""

    return PhaseApplicabilityExecutionService(store, now=now).prepare(
        run_id=run_id,
        coverage_manifest=coverage_manifest,
        plan=plan,
        prompt_template=prompt_template,
        max_owned_units_per_batch=max_owned_units_per_batch,
        context_radius=context_radius,
    )


def run_phase_applicability_execution(
    *,
    store: PhaseApplicabilityExecutionStore,
    run_id: str,
    coverage_manifest: ProtocolSectionCoverageManifest,
    transport: PhaseApplicabilityAgentTransport,
    plan: PhaseApplicabilityFrozenPlan | None = None,
    prompt_template: str = DEFAULT_PHASE_APPLICABILITY_AGENT_PROMPT_TEMPLATE,
    max_owned_units_per_batch: int = 12,
    context_radius: int = 1,
    runner: PhaseApplicabilityAgentRunner | None = None,
    now: Callable[[], datetime] = _utc_now,
) -> PhaseApplicabilityExecutionState:
    """Convenience function for one bounded or resumable execution pass."""

    return PhaseApplicabilityExecutionService(store, runner=runner, now=now).execute(
        run_id=run_id,
        coverage_manifest=coverage_manifest,
        transport=transport,
        plan=plan,
        prompt_template=prompt_template,
        max_owned_units_per_batch=max_owned_units_per_batch,
        context_radius=context_radius,
    )
