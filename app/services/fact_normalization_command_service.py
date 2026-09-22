"""事实规范化命令服务：从审核节点活动证据派生权威元组并幂等创建持久任务。

客户端只提供受试者/审核节点与可选幂等意图；PromptVersion、ModelConfig、
FactAuthority 与页组输入范围一律由服务端从当前登记状态派生，禁止客户端注入。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import isfinite
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import config as runtime_config
from app.agents.evidence_normalizer import (
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
    SUPPORTED_EVIDENCE_NORMALIZER_PROVIDERS,
    SUPPORTED_EVIDENCE_NORMALIZER_REASONING_EFFORTS,
    evidence_normalizer_prompt_template_sha256,
    validate_evidence_normalizer_model_config,
)
from app.domain.contracts.agents import ModelConfigContract, PromptVersion
from app.domain.contracts.enums import AgentNode
from app.domain.contracts.facts import FactAuthority
from app.services.evidence_app_errors import (
    AppNotFoundError,
    AppStaleAuthorityError,
    EvidenceAppError,
    app_error_boundary,
)
from app.services.fact_normalization_job_service import (
    CreateNormalizationJobResult,
    FactNormalizationJobService,
)
from app.services.fact_normalization_source_adapter import FactPlanningSourceError
from app.storage.fact_authority import FactAuthorityError, FactAuthorityValidator
from app.storage.models import ModelConfigRecord, PromptVersionRecord
from app.storage.repositories import (
    MODEL_CONFIG_CONFIG,
    PROMPT_VERSION_CONFIG,
    AppendRepository,
    EpisodeRepository,
    NotFoundError,
)
from app.workflow.errors import InvalidJobDefinitionError

_FACT_NORMALIZATION_CONTRACT_VERSION = "phase5/facts/v1"
_NORMALIZATION_POLICY_VERSION = "phase5/normalization-policy/v9"
_DEFAULT_CREATED_BY = "local-reviewer"
class AppFactNormalizationRejectedError(EvidenceAppError):
    """当前审核节点无法发起个例档案整理。"""

    status_code = 422
    code = "FACT_NORMALIZATION_REJECTED"
    title = "无法开始个例档案整理"
    recovery = "请确认当前审核节点已启用完整资料版本，并完成必要的识别核对后重试。"


class AppFactNormalizationConfigError(EvidenceAppError):
    """本机尚未登记或登记了多份冲突的证据规范化配置。"""

    status_code = 422
    code = "FACT_NORMALIZATION_CONFIG_UNAVAILABLE"
    title = "个例档案整理配置不可用"
    recovery = "请关闭后重新打开系统；若仍无法开始，请检查本机模型服务是否已启动。"


@dataclass(frozen=True)
class RegisteredNormalizerConfig:
    prompt_version_id: str
    model_config_id: str


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _prompt_identity(prompt: PromptVersion) -> str:
    """Return the content-derived identity suffix for a prompt contract."""
    return _canonical_hash(
        {
            "node": prompt.node.value,
            "template_sha256": prompt.template_sha256,
            "schema_version_id": prompt.schema_version_id,
        }
    )


def _model_identity(model_config: ModelConfigContract) -> str:
    """Return the content-derived identity suffix for a model contract."""
    return _canonical_hash(
        {
            "provider": model_config.provider,
            "model": model_config.model,
            "reasoning_effort": model_config.reasoning_effort,
            "parameters": model_config.parameters,
        }
    )


def _is_usable_model_config(
    model_config: ModelConfigContract,
    *,
    require_normalizer_role: bool = False,
    require_supported_provider: bool = False,
) -> bool:
    try:
        validate_evidence_normalizer_model_config(
            model_config,
            require_normalizer_role=require_normalizer_role,
        )
    except ValueError:
        return False
    return bool(model_config.model.strip())


def _model_marked_for_normalizer(model_config: ModelConfigContract) -> bool:
    return (
        str(model_config.parameters.get("agent_node") or "")
        == AgentNode.EVIDENCE_NORMALIZER.value
    )


def _is_usable_prompt(
    prompt: PromptVersion, *, prompt_template: str
) -> bool:
    if prompt.node is not AgentNode.EVIDENCE_NORMALIZER:
        return False
    if prompt.schema_version_id != _FACT_NORMALIZATION_CONTRACT_VERSION:
        return False
    expected = evidence_normalizer_prompt_template_sha256(prompt_template)
    return prompt.template_sha256 == expected


def _runtime_prompt(prompt_template: str) -> PromptVersion:
    if not prompt_template.strip():
        raise AppFactNormalizationConfigError(
            "个例档案整理所需的语义模板为空，系统已停止启动。"
        )
    template_hash = evidence_normalizer_prompt_template_sha256(prompt_template)
    prompt = PromptVersion(
        # PromptVersion enforces a non-empty id; this provisional value is
        # excluded from the content identity and replaced before persistence.
        prompt_version_id="pending",
        node=AgentNode.EVIDENCE_NORMALIZER,
        template_sha256=template_hash,
        schema_version_id=_FACT_NORMALIZATION_CONTRACT_VERSION,
    )
    return prompt.model_copy(
        update={
            "prompt_version_id": (
                "evidence-normalizer/prompt/"
                f"{_prompt_identity(prompt)}"
            )
        }
    )


def _runtime_model(
    *,
    provider: str,
    model: str,
    reasoning_effort: str,
    max_tokens: int,
    temperature: float | None,
) -> ModelConfigContract:
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip()
    normalized_effort = reasoning_effort.strip().lower()
    if normalized_provider not in SUPPORTED_EVIDENCE_NORMALIZER_PROVIDERS:
        raise AppFactNormalizationConfigError(
            f"个例档案整理的模型连接方式（供应商）{provider!r} 不受支持，系统已停止启动。"
        )
    if not normalized_model:
        raise AppFactNormalizationConfigError(
            "个例档案整理未配置模型名称，系统已停止启动。"
        )
    if normalized_effort not in SUPPORTED_EVIDENCE_NORMALIZER_REASONING_EFFORTS:
        raise AppFactNormalizationConfigError(
            f"个例档案整理的模型推理强度 {reasoning_effort!r} 不受支持，系统已停止启动。"
        )
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
        raise AppFactNormalizationConfigError(
            "个例档案整理的最大输出长度必须大于零，系统已停止启动。"
        )
    parameters: dict[str, str | int | float | bool] = {
        "agent_node": AgentNode.EVIDENCE_NORMALIZER.value,
        "max_tokens": max_tokens,
        "normalization_policy_version": _NORMALIZATION_POLICY_VERSION,
    }
    if temperature is not None:
        if isinstance(temperature, bool) or not isinstance(
            temperature, (int, float)
        ):
            raise AppFactNormalizationConfigError(
                "个例档案整理的采样温度必须是数值，系统已停止启动。"
            )
        if not isfinite(float(temperature)) or not 0 <= temperature <= 2:
            raise AppFactNormalizationConfigError(
                "个例档案整理的采样温度必须在 0 到 2 之间，系统已停止启动。"
            )
        parameters["temperature"] = temperature
    model_without_id = {
        "provider": normalized_provider,
        "model": normalized_model,
        "reasoning_effort": normalized_effort,
        "parameters": parameters,
    }
    if normalized_provider in {"mtplx", "mtplx-api"}:
        from app.config import MTPLX_BASE_URL
        from app.llm.mtplx_model_lifecycle import mtplx_deployment_fingerprint

        base_url = MTPLX_BASE_URL.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        deployment = mtplx_deployment_fingerprint(
            normalized_provider, base_url, normalized_model, normalized_effort,
        )
        if deployment is not None:
            parameters["mtplx_deployment_sha256"] = deployment
    return ModelConfigContract(
        model_config_id=(
            "evidence-normalizer/model/"
            f"{_canonical_hash(model_without_id)}"
        ),
        **model_without_id,
    )


def _configured_runtime_pair(
    *,
    prompt_template: str,
    provider: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> tuple[PromptVersion, ModelConfigContract]:
    prompt = _runtime_prompt(prompt_template)
    runtime_model = _runtime_model(
        provider=(
            runtime_config.EVIDENCE_NORMALIZER_PROVIDER
            if provider is None
            else provider
        ),
        model=(
            runtime_config.EVIDENCE_NORMALIZER_MODEL if model is None else model
        ),
        reasoning_effort=(
            runtime_config.EVIDENCE_NORMALIZER_REASONING_EFFORT
            if reasoning_effort is None
            else reasoning_effort
        ),
        max_tokens=(
            runtime_config.EVIDENCE_NORMALIZER_MAX_TOKENS
            if max_tokens is None
            else max_tokens
        ),
        temperature=(
            runtime_config.EVIDENCE_NORMALIZER_TEMPERATURE
            if temperature is None
            else temperature
        ),
    )
    return prompt, runtime_model


def _same_contract(left: Any, right: Any) -> bool:
    return left.model_dump(mode="json") == right.model_dump(mode="json")


def _ensure_immutable_registration(
    session: Session,
    *,
    expected: Any,
    repository: AppendRepository,
    identity: str,
    label: str,
) -> None:
    """Append a new identity or fail on payload drift; never update a row."""
    try:
        current = repository.get_or_none(identity)
    except Exception as exc:  # noqa: BLE001 - persisted-contract corruption is a hard stop
        raise AppFactNormalizationConfigError(
            f"已登记的 Evidence Normalizer {label} 配置无法还原，已拒绝启动。"
        ) from exc
    if current is None:
        repository.save(expected)
        return
    if not _same_contract(current, expected):
        raise AppFactNormalizationConfigError(
            f"已登记的 Evidence Normalizer {label} 配置发生合同漂移，"
            "系统不会覆盖旧身份，已拒绝启动。"
        )


def register_evidence_normalizer_runtime_config(
    session_factory: sessionmaker[Session],
    *,
    prompt_template: str = DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
    provider: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> RegisteredNormalizerConfig:
    """Idempotently append the current Evidence Normalizer runtime identity.

    Prompt/model identities are content-addressed.  A changed runtime setting
    therefore creates a new append-only row; a row whose content no longer
    matches its identity fails closed instead of being repaired in place.
    """
    prompt, model_config = _configured_runtime_pair(
        prompt_template=prompt_template,
        provider=provider,
        model=model,
        reasoning_effort=reasoning_effort,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    with session_factory() as session, session.begin():
        _ensure_immutable_registration(
            session,
            expected=prompt,
            repository=AppendRepository(session, PROMPT_VERSION_CONFIG),
            identity=prompt.prompt_version_id,
            label="PromptVersion",
        )
        _ensure_immutable_registration(
            session,
            expected=model_config,
            repository=AppendRepository(session, MODEL_CONFIG_CONFIG),
            identity=model_config.model_config_id,
            label="ModelConfig",
        )
    return RegisteredNormalizerConfig(
        prompt_version_id=prompt.prompt_version_id,
        model_config_id=model_config.model_config_id,
    )


def _load_exact_registered_config(
    session: Session,
    *,
    registered_config: RegisteredNormalizerConfig,
    prompt_template: str,
) -> RegisteredNormalizerConfig:
    prompt_repo = AppendRepository(session, PROMPT_VERSION_CONFIG)
    model_repo = AppendRepository(session, MODEL_CONFIG_CONFIG)
    try:
        prompt = prompt_repo.get(registered_config.prompt_version_id)
        model_config = model_repo.get(registered_config.model_config_id)
    except Exception as exc:  # noqa: BLE001 - selection must fail closed
        raise AppFactNormalizationConfigError(
            "个例档案整理的已登记设置不存在或已损坏，无法开始整理。"
        ) from exc
    if not isinstance(prompt, PromptVersion) or not isinstance(
        model_config, ModelConfigContract
    ):
        raise AppFactNormalizationConfigError(
            "个例档案整理的已登记设置无法识别，无法开始整理。"
        )
    if (
        prompt.prompt_version_id != registered_config.prompt_version_id
        or model_config.model_config_id != registered_config.model_config_id
        or _prompt_identity(prompt) != prompt.prompt_version_id.split("/", 2)[-1]
        or _model_identity(model_config) != model_config.model_config_id.rsplit("/", 1)[-1]
        or not _is_usable_prompt(prompt, prompt_template=prompt_template)
        or not _is_usable_model_config(
            model_config,
            require_normalizer_role=True,
            require_supported_provider=True,
        )
    ):
        raise AppFactNormalizationConfigError(
            "个例档案整理的已登记配置与当前系统不一致，无法开始整理。"
        )
    return registered_config


def select_registered_evidence_normalizer_config(
    session: Session,
    *,
    prompt_template: str = DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
    registered_config: RegisteredNormalizerConfig | None = None,
) -> RegisteredNormalizerConfig:
    """从不可变登记表选择唯一可用的 PromptVersion 与 ModelConfig。"""
    if registered_config is not None:
        return _load_exact_registered_config(
            session,
            registered_config=registered_config,
            prompt_template=prompt_template,
        )
    prompt_repo = AppendRepository(session, PROMPT_VERSION_CONFIG)
    model_repo = AppendRepository(session, MODEL_CONFIG_CONFIG)

    prompt_rows = session.execute(
        select(PromptVersionRecord).where(
            PromptVersionRecord.node == AgentNode.EVIDENCE_NORMALIZER.value
        )
    ).scalars().all()
    usable_prompts: list[PromptVersion] = []
    for row in prompt_rows:
        prompt = prompt_repo.get(row.prompt_version_id)
        if isinstance(prompt, PromptVersion) and _is_usable_prompt(
            prompt, prompt_template=prompt_template
        ):
            usable_prompts.append(prompt)

    if not usable_prompts:
        raise AppFactNormalizationConfigError(
            "本机尚未登记可用于证据规范化的提示词配置，无法开始个例档案整理。"
        )
    if len(usable_prompts) > 1:
        raise AppFactNormalizationConfigError(
            "本机登记了多份可用的证据规范化提示词配置，系统无法自动选择。请保留唯一有效配置后重试。"
        )

    model_rows = session.execute(select(ModelConfigRecord)).scalars().all()
    marked: list[ModelConfigContract] = []
    has_other_or_unmarked_config = False
    for row in model_rows:
        model_config = model_repo.get(row.model_config_id)
        if not isinstance(model_config, ModelConfigContract):
            continue
        if not _is_usable_model_config(
            model_config,
            require_supported_provider=True,
        ):
            continue
        if _model_marked_for_normalizer(model_config):
            marked.append(model_config)
        else:
            has_other_or_unmarked_config = True

    if not marked and has_other_or_unmarked_config:
        raise AppFactNormalizationConfigError(
            "本机没有登记证据规范化专属模型配置；无归属或属于其他任务的模型不能用于个例档案整理。"
        )
    if not marked:
        raise AppFactNormalizationConfigError(
            "本机尚未登记可用于证据规范化的模型配置，无法开始个例档案整理。"
        )
    if len(marked) > 1:
        raise AppFactNormalizationConfigError(
            "本机登记了多份可用的证据规范化模型配置，系统无法自动选择。请保留唯一有效配置后重试。"
        )

    return RegisteredNormalizerConfig(
        prompt_version_id=usable_prompts[0].prompt_version_id,
        model_config_id=marked[0].model_config_id,
    )


def authority_from_active_episode(
    session: Session, review_episode_id: str
) -> FactAuthority:
    """只从审核节点当前成对活动指针派生 FactAuthority。"""
    try:
        episode = EpisodeRepository(session).get(review_episode_id)
    except NotFoundError as exc:
        raise AppNotFoundError("找不到对应的审核节点。") from exc

    if (
        episode.active_evidence_snapshot_id is None
        or episode.active_evidence_processing_revision_id is None
    ):
        raise AppFactNormalizationRejectedError(
            "该审核节点还没有启用完整资料版本，无法开始个例档案整理。请先完成资料识别核对并启用当前资料版本。"
        )

    authority = FactAuthority(
        project_id=episode.project_id,
        subject_id=episode.subject_id,
        review_episode_id=episode.review_episode_id,
        episode_revision=episode.revision,
        protocol_version_id=episode.protocol_version_id,
        rule_set_id=episode.rule_set_id,
        rule_set_revision=episode.rule_set_revision,
        evidence_snapshot_v2_id=episode.active_evidence_snapshot_id,
        complete_processing_revision_id=episode.active_evidence_processing_revision_id,
    )
    try:
        FactAuthorityValidator(session).validate(authority)
    except FactAuthorityError as exc:
        raise AppStaleAuthorityError(
            "当前审核节点的活动资料不完整或已变化，无法按现有状态开始个例档案整理。"
            "请刷新页面，确认已启用完整资料版本后重新发起。"
        ) from exc
    return authority


class FactNormalizationCommandService:
    """HTTP/命令边界：派生权威、选择登记配置、幂等创建持久规范化任务。"""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        job_service: FactNormalizationJobService | None = None,
        prompt_template: str = DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        registered_config: RegisteredNormalizerConfig | None = None,
        max_pages_per_call: int | None = None,
        require_page_review: bool = False,
        require_source_readiness: bool = False,
        page_reader_identity=None,
        verified_scope_prompt: bool = False,
    ) -> None:
        self.session_factory = session_factory
        self.require_page_review = require_page_review
        self.require_source_readiness = require_source_readiness
        self.page_reader_identity = page_reader_identity
        self.verified_scope_prompt = verified_scope_prompt
        self.prompt_template = prompt_template
        self.registered_config = registered_config
        self.max_pages_per_call = (
            runtime_config.EVIDENCE_NORMALIZER_MAX_PAGES_PER_CALL
            if max_pages_per_call is None
            else max_pages_per_call
        )
        if self.max_pages_per_call < 1:
            raise ValueError("单次个例档案整理页数必须大于零")
        self.job_service = job_service or FactNormalizationJobService(
            session_factory, prompt_template=prompt_template
        )

    @app_error_boundary
    def create_or_reuse(
        self,
        *,
        subject_id: str,
        review_episode_id: str,
        idempotency_intent: str | None = None,
        created_by: str | None = None,
    ) -> CreateNormalizationJobResult:
        """从当前活动证据派生权威并创建/复用持久任务。

        ``idempotency_intent`` 仅作客户端稳定意图标记，不得携带权威或配置身份；
        真正幂等键由活动权威元组、登记配置与输入范围在 Job 服务内派生。
        """
        del idempotency_intent  # 显式丢弃：禁止影响权威/配置选择或服务端幂等键
        operator = (created_by or "").strip() or _DEFAULT_CREATED_BY

        with self.session_factory() as session:
            authority = authority_from_active_episode(session, review_episode_id)
            if authority.subject_id != subject_id:
                raise AppNotFoundError("找不到该受试者下的审核节点。")
            coverage_id = None
            if self.require_page_review:
                from app.services.page_review_coverage_selection import select_normalizer_coverage
                coverage_id = select_normalizer_coverage(
                    session, authority,
                    main_reader_identity_sha256=(self.page_reader_identity() if self.page_reader_identity else None),
                )
            elif self.require_source_readiness:
                from app.services.selective_vision_postprocess_job_service import (
                    SelectiveVisionPostprocessJobService,
                )

                view = SelectiveVisionPostprocessJobService(
                    self.session_factory
                ).get_revision_task(authority.complete_processing_revision_id)
                if not view.found:
                    # Historical image preparations predate the selective-read
                    # job.  They may continue only through their source-bound,
                    # fully reconciled legacy coverage; no new upload is sent
                    # back to the dual full-page path.
                    try:
                        from app.services.page_review_coverage_selection import (
                            select_normalizer_coverage,
                        )

                        coverage_id = select_normalizer_coverage(
                            session,
                            authority,
                            main_reader_identity_sha256=(
                                self.page_reader_identity()
                                if self.page_reader_identity
                                else None
                            ),
                        )
                    except EvidenceAppError as exc:
                        raise AppFactNormalizationRejectedError(
                            "当前资料的页面质量核对尚未建立，请等待资料处理完成后重试。"
                        ) from exc
                    view = None
                if view is not None:
                    if not view.plan_supported:
                        raise AppFactNormalizationRejectedError(
                            "当前资料使用了旧版页面质量核对方式，请重新发起核对后再整理。"
                        )
                    if view.state != "completed":
                        raise AppFactNormalizationRejectedError(
                            "页面质量核对尚未完成；正常文字页无需额外复读，系统只会继续核对存在识别风险的页面。"
                        )
                    eligible = view.eligible_page_count
                    observed = view.observation_page_count
                    closed = view.closed_page_count
                    if eligible is None or observed is None or closed is None:
                        raise AppFactNormalizationRejectedError(
                            "页面质量核对结果不完整，请重新运行当前资料的核对任务。"
                        )
                    if closed or observed != eligible:
                        raise AppFactNormalizationRejectedError(
                            "仍有存在识别风险的页面未核实完成；原件和疑问已保留，本次不会整理成正式病史。"
                        )
            selected = select_registered_evidence_normalizer_config(
                session,
                prompt_template=self.prompt_template,
                registered_config=self.registered_config,
            )

        try:
            return self.job_service.create_or_reuse_from_source(
                authority=authority,
                prompt_version_id=selected.prompt_version_id,
                model_config_id=selected.model_config_id,
                created_by=operator,
                max_pages_per_call=self.max_pages_per_call,
                page_review_coverage_id=coverage_id,
                include_visual_sources=coverage_id is not None,
                **({"verified_scope_prompt": True} if self.verified_scope_prompt else {}),
            )
        except FactPlanningSourceError as exc:
            raise AppFactNormalizationRejectedError(
                "当前启用的完整资料版本缺少可整理的有效页或原文，无法开始个例档案整理。"
                "请核对资料识别与校对结果后重试。"
            ) from exc
        except FactAuthorityError as exc:
            raise AppStaleAuthorityError(
                "审核节点的活动证据在创建任务前已变化，本次没有新建整理任务。"
                "请刷新后重新发起。"
            ) from exc
        except InvalidJobDefinitionError as exc:
            raise AppFactNormalizationConfigError(
                "当前证据规范化配置无法用于建立整理任务。请由维护人员核对登记配置后重试。"
            ) from exc
