"""Deterministic, model-free protocol replay harness.

从原始 DOCX 产品结构化链构建一次可提交的不可变重放包（replay pack）：

    登记原始方案 -> 结构提取 -> 期别适用图 -> 单期投影
    -> 全文覆盖清单 -> 指定 source_ref 范围的重放批次 -> 确定性 Agent 提示词

产品边界：

- 默认路径不调用任何模型，绝不实例化传输层（transport）。``live`` 重放是
  独立的显式动作，不属于本模块。
- 全部确定性计算复用产品链（``register_source_artifact``、
  ``extract_docx_structure``、``build_phase_applicability_graph``、
  ``project_single_phase``、``build_full_protocol_coverage_manifest``、
  ``build_protocol_control_agent_prompt`` 与 ``stable_protocol_control_batch_id``），
  不引入第二套实现。
- 不依赖人工控制矩阵、冻结计划或任何硬编码源路径/哈希/计数；输入身份全部
  来自配置与运行时计算。
- 原始方案与全部中间产物以内容寻址方式原子落盘，写后校验 SHA-256；
  ``verify_replay_pack`` 可重放校验整包指纹与提示词确定性。
- 结构提取仅接受原始 DOCX 方案；方案 PDF 上传与结构分派入口已下线。
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pydantic
from pydantic import Field, model_validator

from app.agents.protocol_control_deconstructor import (
    CONTROL_AGENT_PROMPT_VERSION,
    DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE,
    ProtocolControlAgentInput,
    build_protocol_control_agent_prompt,
    protocol_control_agent_prompt_template_sha256,
)
from app.domain.contracts.common import ContractModel
from app.domain.contracts.enums import StudyPhase
from app.domain.contracts.protocol_controls import (
    KnownOfficialRuleTarget,
    KnownRequiredProcedureTarget,
    KnownWorkflowStageTarget,
    ProtocolControlDispositionBatch,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    stable_protocol_control_batch_id,
)
from app.domain.contracts.protocol_ingestion import ProtocolExtractionSnapshot
from app.protocols.full_protocol_coverage import (
    build_full_protocol_coverage_manifest,
)
from app.protocols.docx_structure import extract_docx_structure
from app.protocols.ingestion import (
    ProtocolFileKind,
    compute_sha256,
    detect_format,
    register_source_artifact,
)
from app.protocols.phase_detection import (
    build_phase_applicability_graph,
    project_single_phase,
)
from app.protocols.protocol_control_planning import detect_required_action_kinds

__all__ = [
    "REPLAY_HARNESS_CONFIG_SCHEMA",
    "REPLAY_HARNESS_INPUT_SCHEMA",
    "REPLAY_HARNESS_SUMMARY_SCHEMA",
    "ReplayArtifact",
    "ReplayHarnessConfig",
    "ReplayHarnessError",
    "ReplayHarnessResult",
    "build_protocol_replay_pack",
    "load_replay_harness_config",
    "replay_pack_fingerprint",
    "verify_replay_pack",
]

REPLAY_HARNESS_CONFIG_SCHEMA = "phase5/protocol-replay-harness-config/v1"
REPLAY_HARNESS_INPUT_SCHEMA = "phase5/protocol-replay-harness-input/v1"
REPLAY_HARNESS_SUMMARY_SCHEMA = "phase5/protocol-replay-harness-summary/v1"

#: 重放包的模式标记；默认且唯一路径。``live`` 由独立显式动作产生，绝不在此出现。
REPLAY_PACK_MODE = "model_free"


class ReplayHarnessError(RuntimeError):
    """重放包构建或校验失败；错误信息保持可操作且确定性。"""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _stable_suffix(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:24]


def _canonical_sha(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_text(payload)


def _write_bytes(path: Path, data: bytes, *, expected_sha256: str | None = None) -> None:
    """原子写入并写后校验 SHA-256；成功文件绝不留下半写状态。"""

    if expected_sha256 is not None and _sha256_bytes(data) != expected_sha256:
        raise ReplayHarnessError(f"内容哈希校验失败，未写入 {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        actual = _sha256_bytes(path.read_bytes())
        if expected_sha256 is not None and actual != expected_sha256:
            raise ReplayHarnessError(f"写后哈希校验失败：{path}")
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def _write_json(path: Path, value: object, *, sort_keys: bool = True) -> str:
    """原子写入 JSON；``sort_keys=False`` 用于键序即合同语义的模型产物。"""

    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=sort_keys) + "\n"
    ).encode("utf-8")
    _write_bytes(path, payload)
    return _sha256_bytes(payload)


def _resolve_path(raw: str, base_dir: Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else base_dir / path


class ReplayHarnessConfig(ContractModel):
    """一次模型无关重放包的完整输入；不含任何硬编码源身份。

    ``owned_source_refs`` 是本次重放必须逐项处置的稳定 ``source_ref`` 范围；
    ``attached_source_refs`` 只能作为只读上下文携带。两者都必须能在从原始
    DOCX 重建的全文覆盖清单中解析，否则构建显式失败。
    """

    schema_version: Literal[REPLAY_HARNESS_CONFIG_SCHEMA]
    protocol_path: str = Field(min_length=1)
    expected_protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    study_phase: StudyPhase
    protocol_version_id: str = Field(min_length=1)
    source_artifact_id: str = Field(min_length=1)
    owned_source_refs: list[str] = Field(min_length=1)
    attached_source_refs: list[str] = Field(default_factory=list)
    out_dir: str = Field(min_length=1)
    # 相对路径解析根；缺省为进程工作目录。
    base_dir: str | None = None
    # 确定性身份覆盖；缺省时由文档哈希与期别推导。
    manifest_id: str | None = None
    snapshot_id: str | None = None
    # 可复现运行钉住的 UTC 时间戳（ISO-8601，必须带时区）；缺省为运行时刻。
    pinned_created_at: str = Field(min_length=1)
    # 冻结的只读目标目录；结构与产品合同一致，全部可选。
    workflow_stages: list[KnownWorkflowStageTarget] = Field(default_factory=list)
    official_targets: list[KnownOfficialRuleTarget] = Field(default_factory=list)
    procedure_targets: list[KnownRequiredProcedureTarget] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ref_range(self) -> "ReplayHarnessConfig":
        owned = self.owned_source_refs
        if any(not ref.strip() for ref in owned):
            raise ValueError("owned_source_refs 不得包含空引用")
        if len(owned) != len(set(owned)):
            raise ValueError("owned_source_refs 不得重复")
        if any(not ref.strip() for ref in self.attached_source_refs):
            raise ValueError("attached_source_refs 不得包含空引用")
        if len(self.attached_source_refs) != len(set(self.attached_source_refs)):
            raise ValueError("attached_source_refs 不得重复")
        if set(owned) & set(self.attached_source_refs):
            raise ValueError(
                "owned_source_refs 与 attached_source_refs 不得重叠："
                + ",".join(sorted(set(owned) & set(self.attached_source_refs)))
            )
        parsed = datetime.fromisoformat(self.pinned_created_at)
        if parsed.tzinfo is None:
            raise ValueError("pinned_created_at 必须带时区（ISO-8601）")
        return self


@dataclass(frozen=True)
class ReplayArtifact:
    """重放包内一个不可变文件的指纹条目。"""

    rel_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class ReplayHarnessResult:
    """一次成功重放包构建的结果摘要。"""

    out_dir: Path
    protocol_document_sha256: str
    snapshot_id: str
    manifest_id: str
    batch_id: str
    prompt_sha256: str
    created_at: str
    owned_source_refs: tuple[str, ...]
    attached_source_refs: tuple[str, ...]
    owned_structure_unit_ids: tuple[str, ...]
    attached_structure_unit_ids: tuple[str, ...]
    unit_counts: dict[str, int]
    artifacts: tuple[ReplayArtifact, ...]


def load_replay_harness_config(path: str | Path) -> ReplayHarnessConfig:
    """加载并校验重放配置 JSON；相对路径字段保持原样由构建时解析。"""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return ReplayHarnessConfig.model_validate(raw)


def _created_at_from_config(config: ReplayHarnessConfig) -> datetime:
    parsed = datetime.fromisoformat(config.pinned_created_at)
    return parsed.astimezone(timezone.utc)


def _unit_by_source_ref(
    manifest: ProtocolSectionCoverageManifest,
) -> dict[str, ProtocolStructureUnit]:
    by_ref: dict[str, ProtocolStructureUnit] = {}
    duplicates: list[str] = []
    for unit in manifest.units:
        if unit.source_ref in by_ref:
            duplicates.append(unit.source_ref)
        by_ref[unit.source_ref] = unit
    if duplicates:
        raise ReplayHarnessError(
            "覆盖清单包含重复 source_ref，无法确定重放所有权："
            + ",".join(sorted(set(duplicates)))
        )
    return by_ref


def _resolve_units(
    manifest: ProtocolSectionCoverageManifest,
    *,
    owned_refs: list[str],
    attached_refs: list[str],
) -> tuple[list[ProtocolStructureUnit], list[ProtocolStructureUnit]]:
    """把稳定 source_ref 范围解析到重建覆盖清单的结构单元上。

    缺失的引用必须显式失败并给出清单内可用引用数量；批次单元保持原文顺序。
    """

    by_ref = _unit_by_source_ref(manifest)
    missing = [ref for ref in [*owned_refs, *attached_refs] if ref not in by_ref]
    if missing:
        raise ReplayHarnessError(
            "source_ref 无法在从原始 DOCX 重建的覆盖清单中解析："
            + ",".join(missing)
            + f"（清单共 {len(by_ref)} 个结构单元）"
        )

    def ordered(refs: list[str]) -> list[ProtocolStructureUnit]:
        units = [by_ref[ref] for ref in refs]
        return sorted(units, key=lambda unit: (unit.source_order, unit.source_ref))

    return ordered(owned_refs), ordered(attached_refs)


def _replay_batch(
    manifest: ProtocolSectionCoverageManifest,
    owned_units: list[ProtocolStructureUnit],
    context_units: list[ProtocolStructureUnit],
    config: ReplayHarnessConfig,
) -> ProtocolControlDispositionBatch:
    """构建拥有指定 source_ref 范围的单一重放批次。

    批次身份仅由冻结系统输入推导（``stable_protocol_control_batch_id``），
    与模型文本无关；上下文单元只读，绝不进入所有权闭包。
    """

    owned_ids = [unit.structure_unit_id for unit in owned_units]
    context_ids = [unit.structure_unit_id for unit in context_units]
    return ProtocolControlDispositionBatch(
        batch_id=stable_protocol_control_batch_id(manifest.manifest_id, 1, owned_ids),
        coverage_manifest_id=manifest.manifest_id,
        protocol_version_id=manifest.protocol_version_id,
        study_phase=manifest.study_phase,
        batch_number=1,
        batch_total=1,
        priority_rank=max((unit.priority_rank for unit in owned_units), default=0),
        owned_units=owned_units,
        context_units=context_units,
        owned_structure_unit_ids=owned_ids,
        context_structure_unit_ids=context_ids,
        owned_source_span_ids=sorted(
            {span for unit in owned_units for span in unit.source_span_ids}
        ),
        context_source_span_ids=sorted(
            {span for unit in context_units for span in unit.source_span_ids}
        ),
        owned_required_action_kinds_by_structure_unit_id={
            unit.structure_unit_id: list(action_kinds)
            for unit in owned_units
            if (action_kinds := detect_required_action_kinds(unit.excerpt))
        },
        known_official_targets=list(config.official_targets),
        known_procedure_targets=list(config.procedure_targets),
        known_workflow_stage_targets=list(config.workflow_stages),
    )


def _walk_artifacts(out_dir: Path) -> list[ReplayArtifact]:
    artifacts: list[ReplayArtifact] = []
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        artifacts.append(
            ReplayArtifact(
                rel_path=path.relative_to(out_dir).as_posix(),
                sha256=_sha256_bytes(data),
                size_bytes=len(data),
            )
        )
    return artifacts


def _remove_pack_dir(out_dir: Path) -> None:
    """整体移除半成品重放包目录；构建开始前的空/不存在状态由此恢复。"""

    shutil.rmtree(out_dir, ignore_errors=True)


def build_protocol_replay_pack(
    config: ReplayHarnessConfig, *, base_dir: str | Path | None = None
) -> ReplayHarnessResult:
    """从原始 DOCX 产品结构化链构建一次不可变重放包（模型无关）。

    包内容是（范围配置, 输入字节）的纯函数：位置字段（out_dir/base_dir）
    不参与包身份，同一配置两次构建产生逐字节相同的文件集。全部计算先在
    输出目录内暂存；只有整条链成功后，重放包才原子发布。``out_dir`` 已
    存在且非空时显式失败——一个目录只承载一次重放包，绝不覆盖既有不可变
    产物。任何一步失败都抛出 :class:`ReplayHarnessError`，``out_dir`` 恢复
    为空或不存在。
    """

    base = Path(base_dir or config.base_dir or Path.cwd()).resolve()
    protocol_path = _resolve_path(config.protocol_path, base)
    out_dir = _resolve_path(config.out_dir, base)
    if not protocol_path.is_file():
        raise ReplayHarnessError(f"原始方案不存在或不可读：{protocol_path}")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ReplayHarnessError(
            f"输出目录非空，拒绝覆盖既有重放包：{out_dir}（一个目录只承载一次重放包）"
        )

    _mime, kind = detect_format(protocol_path)
    if kind != ProtocolFileKind.DOCX:
        raise ReplayHarnessError(
            f"仅支持 DOCX 结构提取，检测到 {kind.value}：{protocol_path}；"
            "方案 PDF 上传与结构分派入口已下线。"
        )

    protocol_document_sha256 = compute_sha256(protocol_path)
    if protocol_document_sha256 != config.expected_protocol_sha256:
        raise ReplayHarnessError(
            "原始方案 SHA-256 与重放配置不一致："
            f"期望 {config.expected_protocol_sha256}，实际 {protocol_document_sha256}"
        )
    created_at = _created_at_from_config(config)
    created_at_iso = created_at.astimezone(timezone.utc).isoformat()
    snapshot_id = config.snapshot_id or "snp-" + _stable_suffix(protocol_document_sha256)

    # 输出目录先前已确认为空或不存在；本次运行完全拥有该目录，
    # 任何失败都整体移除，恢复「要么整包、要么无包」语义。
    out_dir.mkdir(parents=True, exist_ok=True)
    staged = tempfile.mkdtemp(prefix=".staging-", dir=out_dir)
    staged_source_dir = Path(staged) / "source-input"
    try:
        # 1. 登记原始方案：内容寻址不可变副本（暂存）。
        artifact = register_source_artifact(
            protocol_path,
            source_artifact_id=config.source_artifact_id,
            storage_root=staged_source_dir,
            uploaded_at=created_at,
        )
        if artifact.sha256 != protocol_document_sha256:
            raise ReplayHarnessError("登记的源哈希与运行时计算不一致")

        # 2. 结构提取：规范块集 blob 与不可变快照（暂存）。
        extraction = extract_docx_structure(
            protocol_path,
            snapshot_id=snapshot_id,
            source_artifact=artifact,
            output_dir=staged_source_dir,
            created_at=created_at,
        )
        blocks = extraction.blocks
        if not blocks:
            raise ReplayHarnessError("结构提取未产生任何结构块")

        # 3. 期别适用图 -> 单期投影 -> 全文覆盖清单（全部产品确定性函数）。
        detection = build_phase_applicability_graph(blocks, snapshot_id=snapshot_id)
        projection = project_single_phase(detection.graph, config.study_phase)
        manifest = build_full_protocol_coverage_manifest(
            blocks,
            projection,
            detection.graph,
            protocol_version_id=config.protocol_version_id,
            protocol_document_sha256=protocol_document_sha256,
            snapshot_id=snapshot_id,
            manifest_id=config.manifest_id,
        )

        # 4. 解析指定 source_ref 范围。
        owned_units, context_units = _resolve_units(
            manifest,
            owned_refs=list(config.owned_source_refs),
            attached_refs=list(config.attached_source_refs),
        )

        # 5. 重放批次与确定性 Agent 提示词（模型输入；此处绝不调用模型）。
        batch = _replay_batch(manifest, owned_units, context_units, config)
        agent_input = ProtocolControlAgentInput.from_batch(batch)
        prompt = build_protocol_control_agent_prompt(batch)
        prompt_bytes = prompt.encode("utf-8")
        prompt_sha256 = _sha256_bytes(prompt_bytes)
        prompt_template_sha256 = protocol_control_agent_prompt_template_sha256(
            DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE
        )
    except BaseException:
        _remove_pack_dir(out_dir)
        raise

    # 6. 原子发布：先移入不可变源输入（同文件系统 rename），再写链产物、
    # 提示词与指纹摘要。
    try:
        os.replace(staged_source_dir, out_dir / "source-input")
        Path(staged).rmdir()
        config_echo = config.model_dump(mode="json")
        # 位置字段（out_dir/base_dir）不属于包身份：包内容是
        # （范围配置, 输入字节）的纯函数，目的地不落盘。
        for location_field in ("protocol_path", "out_dir", "base_dir"):
            config_echo.pop(location_field, None)
        input_payload = {
            "schema_version": REPLAY_HARNESS_INPUT_SCHEMA,
            "config": config_echo,
            "protocol_document_sha256": protocol_document_sha256,
            "source_artifact": artifact.model_dump(mode="json"),
            "created_at": created_at_iso,
            "toolchain": {
                "python_version": platform.python_version(),
                "pydantic_version": pydantic.__version__,
                "parser_name": extraction.snapshot.parser_name,
                "parser_version": extraction.snapshot.parser_version,
            },
        }
        _write_json(out_dir / "replay-input.json", input_payload)
        chain_dir = out_dir / "chain"
        # 模型产物保持声明/插入键序：批次的归属字典键序即合同语义，
        # 重新排序会在回读校验时破坏合同。
        _write_json(
            chain_dir / "extraction-snapshot.json",
            extraction.snapshot.model_dump(mode="json"),
            sort_keys=False,
        )
        _write_json(
            chain_dir / "phase-applicability-graph.json",
            detection.graph.model_dump(mode="json"),
            sort_keys=False,
        )
        _write_json(
            chain_dir / "phase-projection.json",
            projection.model_dump(mode="json"),
            sort_keys=False,
        )
        _write_json(
            out_dir / "coverage-manifest.json",
            manifest.model_dump(mode="json"),
            sort_keys=False,
        )
        _write_json(
            out_dir / "replay-batch.json", batch.model_dump(mode="json"), sort_keys=False
        )
        _write_json(
            out_dir / "agent-input.json",
            agent_input.model_dump(mode="json"),
            sort_keys=False,
        )
        _write_bytes(out_dir / "prompt.txt", prompt_bytes)

        # 摘要不含自身指纹（循环），其余文件全部逐一举证。
        artifacts = [
            item
            for item in _walk_artifacts(out_dir)
            if item.rel_path != "replay-summary.json"
        ]
        summary = {
            "schema_version": REPLAY_HARNESS_SUMMARY_SCHEMA,
            "mode": REPLAY_PACK_MODE,
            "transport_instantiated": False,
            "created_at": created_at_iso,
            "protocol_document_sha256": protocol_document_sha256,
            "source_artifact_id": config.source_artifact_id,
            "protocol_version_id": config.protocol_version_id,
            "study_phase": config.study_phase.value,
            "snapshot_id": snapshot_id,
            "manifest_id": manifest.manifest_id,
            "batch_id": batch.batch_id,
            "prompt_sha256": prompt_sha256,
            # 版本记录：提示词正文不携带版本串，包身份与版本轴解耦；
            # 摘要显式登记版本 id 与模板合同哈希，供外部检查点钉扎版本漂移。
            "prompt_version": CONTROL_AGENT_PROMPT_VERSION,
            "prompt_template_sha256": prompt_template_sha256,
            "toolchain": input_payload["toolchain"],
            "owned_source_refs": list(config.owned_source_refs),
            "attached_source_refs": list(config.attached_source_refs),
            "owned_structure_unit_ids": list(batch.owned_structure_unit_ids),
            "attached_structure_unit_ids": list(batch.context_structure_unit_ids),
            "unit_counts": {
                "blocks": len(blocks),
                "manifest_units": len(manifest.units),
                "owned_units": len(owned_units),
                "context_units": len(context_units),
            },
            "artifacts": {
                item.rel_path: {"sha256": item.sha256, "size_bytes": item.size_bytes}
                for item in artifacts
            },
        }
        _write_json(out_dir / "replay-summary.json", summary)
    except BaseException:
        # 发布中断：整体移除半成品目录，恢复“要么整包、要么无包”语义。
        _remove_pack_dir(out_dir)
        raise

    final_artifacts = tuple(
        sorted(_walk_artifacts(out_dir), key=lambda item: item.rel_path)
    )

    return ReplayHarnessResult(
        out_dir=out_dir,
        protocol_document_sha256=protocol_document_sha256,
        snapshot_id=snapshot_id,
        manifest_id=manifest.manifest_id,
        batch_id=batch.batch_id,
        prompt_sha256=prompt_sha256,
        created_at=created_at_iso,
        owned_source_refs=tuple(config.owned_source_refs),
        attached_source_refs=tuple(config.attached_source_refs),
        owned_structure_unit_ids=tuple(batch.owned_structure_unit_ids),
        attached_structure_unit_ids=tuple(batch.context_structure_unit_ids),
        unit_counts=dict(summary["unit_counts"]),
        artifacts=final_artifacts,
    )


def replay_pack_fingerprint(out_dir: str | Path) -> str:
    """整包规范指纹：实际文件相对路径与 SHA-256 的规范哈希。

    指纹直接读取整包（包括摘要），不信任摘要内自报的哈希。
    因此外部检查点记录该值后，可发现摘要本身被替换。
    """

    directory = Path(out_dir)
    summary_path = directory / "replay-summary.json"
    if not summary_path.is_file():
        raise ReplayHarnessError(f"重放包缺失 replay-summary.json：{directory}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    artifacts = _walk_artifacts(directory)
    if not artifacts:
        raise ReplayHarnessError("重放包摘要缺少 artifacts 指纹表")
    return _canonical_sha(
        {
            "artifacts": {item.rel_path: item.sha256 for item in artifacts},
        }
    )


def verify_replay_pack(
    out_dir: str | Path, *, expected_fingerprint: str | None = None
) -> list[str]:
    """确定性重放校验：整包指纹、提示词不变性与合同重校验。

    返回不一致列表；空列表表示校验通过。校验只读，绝不修改包内容。
    """

    directory = Path(out_dir)
    mismatches: list[str] = []
    if expected_fingerprint is not None:
        actual_fingerprint = replay_pack_fingerprint(directory)
        if actual_fingerprint != expected_fingerprint:
            mismatches.append(
                f"pack_fingerprint:{actual_fingerprint}!={expected_fingerprint}"
            )
    summary_path = directory / "replay-summary.json"
    if not summary_path.is_file():
        return [f"missing:replay-summary.json"]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("schema_version") != REPLAY_HARNESS_SUMMARY_SCHEMA:
        mismatches.append(
            f"schema_version:{summary.get('schema_version')}!={REPLAY_HARNESS_SUMMARY_SCHEMA}"
        )
    if summary.get("mode") != REPLAY_PACK_MODE:
        mismatches.append(f"mode:{summary.get('mode')}!={REPLAY_PACK_MODE}")
    if summary.get("transport_instantiated") is not False:
        mismatches.append("transport_instantiated:expected false")

    replay_input: dict[str, object] | None = None
    replay_input_path = directory / "replay-input.json"
    if replay_input_path.is_file():
        try:
            loaded = json.loads(replay_input_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("顶层必须为对象")
            replay_input = loaded
        except Exception as exc:
            mismatches.append(f"contract:replay-input.json:{exc}")
        else:
            if replay_input.get("schema_version") != REPLAY_HARNESS_INPUT_SCHEMA:
                mismatches.append("replay_input.schema_version:mismatch")
            config = replay_input.get("config")
            source_artifact = replay_input.get("source_artifact")
            if not isinstance(config, dict):
                mismatches.append("replay_input.config:missing")
            else:
                if config.get("expected_protocol_sha256") != summary.get(
                    "protocol_document_sha256"
                ):
                    mismatches.append("replay_input.expected_protocol_sha256:mismatch")
                for key in (
                    "source_artifact_id",
                    "protocol_version_id",
                    "study_phase",
                    "owned_source_refs",
                    "attached_source_refs",
                ):
                    if config.get(key) != summary.get(key):
                        mismatches.append(f"replay_input.config.{key}:mismatch")
            if not isinstance(source_artifact, dict):
                mismatches.append("replay_input.source_artifact:missing")
            else:
                if source_artifact.get("source_artifact_id") != summary.get(
                    "source_artifact_id"
                ):
                    mismatches.append("replay_input.source_artifact_id:mismatch")
                if source_artifact.get("sha256") != summary.get(
                    "protocol_document_sha256"
                ):
                    mismatches.append("replay_input.source_artifact_sha256:mismatch")
            if replay_input.get("protocol_document_sha256") != summary.get(
                "protocol_document_sha256"
            ):
                mismatches.append("replay_input.protocol_document_sha256:mismatch")
            if replay_input.get("created_at") != summary.get("created_at"):
                mismatches.append("replay_input.created_at:mismatch")
            if replay_input.get("toolchain") != summary.get("toolchain"):
                mismatches.append("replay_input.toolchain:mismatch")

    recorded = summary.get("artifacts")
    if not isinstance(recorded, dict):
        return mismatches + ["artifacts:missing"]
    recorded_without_self = {
        rel: entry for rel, entry in recorded.items() if rel != "replay-summary.json"
    }

    on_disk = {
        item.rel_path: item for item in _walk_artifacts(directory)
        if item.rel_path != "replay-summary.json"
    }
    for rel in sorted(set(recorded_without_self) - set(on_disk)):
        mismatches.append(f"missing:{rel}")
    for rel in sorted(set(on_disk) - set(recorded_without_self)):
        mismatches.append(f"unexpected:{rel}")
    for rel in sorted(set(recorded_without_self) & set(on_disk)):
        entry = recorded_without_self[rel]
        item = on_disk[rel]
        if not isinstance(entry, dict) or entry.get("sha256") != item.sha256:
            mismatches.append(f"sha256:{rel}")
        elif isinstance(entry, dict) and entry.get("size_bytes") != item.size_bytes:
            mismatches.append(f"size:{rel}")

    # 提示词确定性：从保存的批次重建产品合同并重放提示词。
    batch_path = directory / "replay-batch.json"
    prompt_path = directory / "prompt.txt"
    batch: ProtocolControlDispositionBatch | None = None
    if batch_path.is_file() and prompt_path.is_file() and not any(
        key.startswith(("sha256:replay-batch.json", "missing:replay-batch.json", "sha256:prompt.txt", "missing:prompt.txt"))
        for key in mismatches
    ):
        try:
            batch = ProtocolControlDispositionBatch.model_validate(
                json.loads(batch_path.read_text(encoding="utf-8"))
            )
        except Exception as exc:
            mismatches.append(f"contract:replay-batch.json:{exc}")
        else:
            rebuilt_prompt = build_protocol_control_agent_prompt(batch)
            if _sha256_bytes(rebuilt_prompt.encode("utf-8")) != summary.get("prompt_sha256"):
                mismatches.append("prompt_sha256:mismatch")
            if prompt_path.read_bytes() != rebuilt_prompt.encode("utf-8"):
                mismatches.append("prompt.txt:rebuilt-content-mismatch")

    # 合同重校验：清单、批次、Agent 输入。
    manifest: ProtocolSectionCoverageManifest | None = None
    manifest_path = directory / "coverage-manifest.json"
    if manifest_path.is_file():
        try:
            manifest = ProtocolSectionCoverageManifest.model_validate(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
        except Exception as exc:
            mismatches.append(f"contract:coverage-manifest.json:{exc}")
        else:
            if (
                manifest.protocol_document_sha256
                != summary.get("protocol_document_sha256")
            ):
                mismatches.append("manifest.protocol_document_sha256:mismatch")
            for field in ("manifest_id", "snapshot_id", "protocol_version_id"):
                if getattr(manifest, field) != summary.get(field):
                    mismatches.append(f"manifest.{field}:mismatch")
            if manifest.study_phase.value != summary.get("study_phase"):
                mismatches.append("manifest.study_phase:mismatch")
    input_path = directory / "agent-input.json"
    agent_input: ProtocolControlAgentInput | None = None
    if input_path.is_file():
        try:
            agent_input = ProtocolControlAgentInput.model_validate(
                json.loads(input_path.read_text(encoding="utf-8"))
            )
        except Exception as exc:
            mismatches.append(f"contract:agent-input.json:{exc}")

    snapshot_path = directory / "chain" / "extraction-snapshot.json"
    if snapshot_path.is_file():
        try:
            snapshot = ProtocolExtractionSnapshot.model_validate(
                json.loads(snapshot_path.read_text(encoding="utf-8"))
            )
        except Exception as exc:
            mismatches.append(f"contract:chain/extraction-snapshot.json:{exc}")
        else:
            if snapshot.snapshot_id != summary.get("snapshot_id"):
                mismatches.append("snapshot.snapshot_id:mismatch")
            if snapshot.source_sha256 != summary.get("protocol_document_sha256"):
                mismatches.append("snapshot.source_sha256:mismatch")
            expected_toolchain = summary.get("toolchain")
            if not isinstance(expected_toolchain, dict):
                mismatches.append("summary.toolchain:missing")
            elif (
                snapshot.parser_name != expected_toolchain.get("parser_name")
                or snapshot.parser_version != expected_toolchain.get("parser_version")
            ):
                mismatches.append("snapshot.parser_toolchain:mismatch")

    # 所有权闭包：批次 owned 单元身份必须与摘要记录逐一对应。
    if batch is not None:
        if list(batch.owned_structure_unit_ids) != summary.get(
            "owned_structure_unit_ids"
        ):
            mismatches.append("owned_structure_unit_ids:mismatch")
        owned_refs = {unit.source_ref for unit in batch.owned_units}
        if owned_refs != set(summary.get("owned_source_refs") or []):
            mismatches.append("owned_source_refs:closure-mismatch")
        attached_refs = {unit.source_ref for unit in batch.context_units}
        if attached_refs != set(summary.get("attached_source_refs") or []):
            mismatches.append("attached_source_refs:closure-mismatch")
        if list(batch.context_structure_unit_ids) != summary.get(
            "attached_structure_unit_ids"
        ):
            mismatches.append("attached_structure_unit_ids:mismatch")
        if batch.batch_id != summary.get("batch_id"):
            mismatches.append("batch.batch_id:mismatch")
        if batch.coverage_manifest_id != summary.get("manifest_id"):
            mismatches.append("batch.coverage_manifest_id:mismatch")
        if batch.protocol_version_id != summary.get("protocol_version_id"):
            mismatches.append("batch.protocol_version_id:mismatch")
        if batch.study_phase.value != summary.get("study_phase"):
            mismatches.append("batch.study_phase:mismatch")
        if manifest is not None:
            manifest_units = {
                unit.structure_unit_id: unit.model_dump(mode="json")
                for unit in manifest.units
            }
            for unit in [*batch.owned_units, *batch.context_units]:
                if manifest_units.get(unit.structure_unit_id) != unit.model_dump(
                    mode="json"
                ):
                    mismatches.append(
                        f"batch.unit_not_in_manifest:{unit.structure_unit_id}"
                    )
        if agent_input is not None and agent_input != ProtocolControlAgentInput.from_batch(
            batch
        ):
            mismatches.append("agent_input:batch_projection_mismatch")

    return mismatches
