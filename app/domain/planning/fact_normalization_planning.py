"""确定性事实规范化规划（纯确定性，无存储/模型）。

职责单一：把活动 CompleteEvidenceProcessingRevision + 项目有效文本
确定性规划为逻辑文档调用与连续页组，满足 PRD P5-R02/P5-R09：

- 默认按逻辑文档一切片，超长文档按连续页组切片（每组页码连续、递增、无跨文档）；
- 稳定输入哈希（canonical_hash，排除时间戳/文件名/随机ID/模型置信度）；
- 显式完整页闭合（所有调用的 (logical_document_id, page_number) 并集精确等于
  完整修订期望页集合，无缺页/多余页/重复页/跨修订借用）；
- 无跨审核节点/隐式日期借用：绝不借用筛选日/上传日/操作日填补 PartialDateRange
  缺失上下界，事件时间与记录时间分开；跨 episode 复用一律拒绝。

本模块是纯函数，不访问数据库/文件/模型。调用方（source adapter）负责从
DB 读取不可变有效文本与逻辑文档映射后，传入本模块进行确定性切片与哈希。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision
from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.evidence_normalizer import (
    EvidenceNormalizerContextInput,
    EvidenceNormalizerLocatorInput,
    EvidenceNormalizerPageInput,
    evidence_normalizer_input_scope_hash,
)
from app.domain.contracts.rules import EvidenceRequirement
from app.domain.publication import canonical_hash

_CONTRACT_VERSION = "phase5/facts/v1"
_DEFAULT_MAX_PAGES_PER_CALL = 20


@dataclass(frozen=True)
class PageInput:
    """一页的确定性输入（用于输入哈希，不含隐式日期借用）。"""

    source_document_version_id: str
    page_number: int
    page_artifact_id: str
    ocr_page_id: str | None
    effective_text_sha256: str
    # 仅用于追溯/调试的逻辑文档身份，不参与借用
    logical_document_id: str
    locator_ids: tuple[str, ...] = ()
    locator_inputs: tuple[EvidenceNormalizerLocatorInput, ...] = ()
    # 可选：仅保存哈希对应的原文长度校验，不借用
    effective_text: str | None = None

    def __post_init__(self) -> None:
        if not self.source_document_version_id:
            raise ValueError("PageInput.source_document_version_id 不能为空")
        if self.page_number < 1:
            raise ValueError("PageInput.page_number 必须 >= 1")
        if not self.page_artifact_id:
            raise ValueError("PageInput.page_artifact_id 不能为空")
        if not self.effective_text_sha256 or len(self.effective_text_sha256) != 64:
            raise ValueError("PageInput.effective_text_sha256 必须是 64 位十六进制")
        if list(self.locator_ids) != sorted(set(self.locator_ids)):
            raise ValueError("PageInput.locator_ids 必须按 ID 排序且不得重复")
        if [item.locator_id for item in self.locator_inputs] != list(self.locator_ids):
            raise ValueError("PageInput.locator_inputs 必须按 ID 逐项闭合 locator_ids")
        if any(item.page_number != self.page_number for item in self.locator_inputs):
            raise ValueError("PageInput.locator_inputs 必须属于当前页")


@dataclass(frozen=True)
class PlannedCall:
    """一次确定性规划调用（逻辑文档 + 连续页组）。"""

    logical_document_id: str
    page_numbers: tuple[int, ...]
    page_inputs: tuple[PageInput, ...]
    context: EvidenceNormalizerContextInput
    related_requirements: tuple[EvidenceRequirement, ...]
    input_sha256: str

    def __post_init__(self) -> None:
        if not self.logical_document_id:
            raise ValueError("PlannedCall.logical_document_id 不能为空")
        if not self.page_numbers:
            raise ValueError("PlannedCall.page_numbers 不能为空")
        if list(self.page_numbers) != sorted(set(self.page_numbers)):
            raise ValueError("PlannedCall.page_numbers 必须升序、无重复且从 1 起")
        if any(p < 1 for p in self.page_numbers):
            raise ValueError("PlannedCall.page_numbers 页码必须 >= 1")
        # 连续性：同一调用内页码必须连续（不允许 [1,3]）
        if list(self.page_numbers) != list(range(self.page_numbers[0], self.page_numbers[-1] + 1)):
            raise ValueError(
                f"PlannedCall {self.logical_document_id} 的页组 {self.page_numbers} 必须连续"
            )
        if len(self.page_inputs) != len(self.page_numbers):
            raise ValueError("PlannedCall.page_inputs 数量必须与 page_numbers 一致")
        # page_inputs 必须与 page_numbers 一一对应且按页码排序
        input_numbers = [p.page_number for p in self.page_inputs]
        if input_numbers != list(self.page_numbers):
            raise ValueError("PlannedCall.page_inputs 必须按页码与 page_numbers 一一对应且有序")


@dataclass(frozen=True)
class FactNormalizationPlan:
    """一次运行的完整确定性规划（所有调用 + 范围哈希）。"""

    authority: FactAuthority
    complete_processing_revision_id: str
    calls: tuple[PlannedCall, ...]
    input_scope_sha256: str
    max_pages_per_call: int = _DEFAULT_MAX_PAGES_PER_CALL
    contract_version: str = _CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.complete_processing_revision_id != self.authority.complete_processing_revision_id:
            raise ValueError("FactNormalizationPlan 的完整修订必须与权威元组一致")
        if not self.calls:
            raise ValueError("FactNormalizationPlan 必须至少包含一个调用")
        if len(self.input_scope_sha256) != 64:
            raise ValueError("FactNormalizationPlan.input_scope_sha256 必须是 64 位哈希")
        if self.max_pages_per_call < 1:
            raise ValueError("FactNormalizationPlan.max_pages_per_call 必须大于零")


# --------------------------------------------------------------------------- 哈希

def compute_call_input_hash(
    *,
    authority: FactAuthority,
    revision: CompleteEvidenceProcessingRevision,
    logical_document_id: str,
    context: EvidenceNormalizerContextInput,
    related_requirements: list[EvidenceRequirement] | tuple[EvidenceRequirement, ...],
    page_numbers: list[int],
    page_inputs: list[PageInput],
    contract_version: str = _CONTRACT_VERSION,
) -> str:
    """使用规范化器输入合同计算唯一的调用输入哈希。"""
    sorted_inputs = sorted(page_inputs, key=lambda p: p.page_number)
    pages: list[EvidenceNormalizerPageInput] = []
    for page in sorted_inputs:
        if page.effective_text is None:
            raise ValueError(
                f"逻辑文档 {logical_document_id} 页 {page.page_number} 缺少有效文本，无法冻结调用"
            )
        pages.append(
            EvidenceNormalizerPageInput(
                source_document_version_id=page.source_document_version_id,
                page_artifact_id=page.page_artifact_id,
                ocr_page_id=page.ocr_page_id,
                page_number=page.page_number,
                effective_text=page.effective_text,
                effective_text_sha256=page.effective_text_sha256,
                locator_ids=list(page.locator_ids),
            )
        )
    available_locator_ids = sorted(
        {locator_id for page in sorted_inputs for locator_id in page.locator_ids}
    )
    available_locators = sorted(
        (locator for page in sorted_inputs for locator in page.locator_inputs),
        key=lambda item: item.locator_id,
    )
    return evidence_normalizer_input_scope_hash(
        authority=authority,
        logical_document_id=logical_document_id,
        context=context,
        related_requirements=list(related_requirements),
        manifest_sha256=revision.manifest_sha256,
        completion_manifest_sha256=revision.completion_manifest_sha256,
        page_numbers=sorted(set(page_numbers)),
        pages=pages,
        available_locator_ids=available_locator_ids,
        available_locators=available_locators,
    )


def compute_input_scope_hash(
    *,
    authority: FactAuthority,
    revision: CompleteEvidenceProcessingRevision,
    calls: list[PlannedCall],
    max_pages_per_call: int = _DEFAULT_MAX_PAGES_PER_CALL,
    contract_version: str = _CONTRACT_VERSION,
) -> str:
    """计算整个运行的输入范围哈希（对所有调用的输入哈希有序求和）。"""
    sorted_calls = sorted(calls, key=lambda c: (c.logical_document_id, c.page_numbers))
    material = {
        "input_scope/v2": True,
        "contract_version": contract_version,
        "authority": authority.model_dump(mode="json"),
        "max_pages_per_call": max_pages_per_call,
        "calls": [
            {
                "logical_document_id": c.logical_document_id,
                "page_numbers": list(c.page_numbers),
                "input_sha256": c.input_sha256,
            }
            for c in sorted_calls
        ],
    }
    return canonical_hash(material)


# --------------------------------------------------------------------------- 校验

def validate_authority_matches_revision(
    authority: FactAuthority,
    revision: CompleteEvidenceProcessingRevision,
) -> None:
    """权威元组必须与完整修订的作用域精确一致，无跨 episode 借用。"""
    if (
        authority.project_id != revision.project_id
        or authority.subject_id != revision.subject_id
        or authority.review_episode_id != revision.review_episode_id
        or authority.evidence_snapshot_v2_id != revision.evidence_snapshot_id
        or authority.complete_processing_revision_id != revision.evidence_processing_revision_id
    ):
        raise ValueError(
            "FactAuthority 与 CompleteEvidenceProcessingRevision 作用域不一致，"
            "拒绝跨 episode/跨快照/跨修订规划（无隐式借用）"
        )


def validate_full_page_closure(
    calls: list[PlannedCall] | tuple[PlannedCall, ...],
    revision: CompleteEvidenceProcessingRevision,
    *,
    doc_version_to_logical: dict[str, str] | None = None,
) -> None:
    """校验所有调用的 (logical_document_id, page_number) 并集精确等于修订期望页集合。

    显式拒绝：缺页、多余页、重复页、跨文档/跨修订页。
    """
    if not revision.manifest:
        raise ValueError("完整处理修订的页清单不能为空（无法证明完整页闭合）")
    # 期望集合：来自修订 manifest + 逻辑文档映射
    expected: set[tuple[str, int]] = set()
    for entry in revision.manifest:
        logical = None
        if doc_version_to_logical is not None:
            logical = doc_version_to_logical.get(entry.source_document_version_id)
        if logical is None:
            # 若无映射，以 source_document_version_id 作为逻辑文档占位（测试友好）
            # 但仍需保证每个 entry 都有归属
            logical = entry.source_document_version_id
        expected.add((logical, entry.page_number))

    actual: set[tuple[str, int]] = set()
    seen_counts: dict[tuple[str, int], int] = {}
    for call in calls:
        for page in call.page_numbers:
            key = (call.logical_document_id, page)
            actual.add(key)
            seen_counts[key] = seen_counts.get(key, 0) + 1

    # 重复页
    duplicates = [k for k, c in seen_counts.items() if c > 1]
    if duplicates:
        raise ValueError(f"调用集合存在重复页 {sorted(duplicates)}，拒绝")

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append(f"缺页 {missing}")
        if extra:
            parts.append(f"多余页 {extra}")
        raise ValueError("页闭合失败：" + "；".join(parts))


def validate_calls_contiguous(
    calls: list[PlannedCall] | tuple[PlannedCall, ...],
) -> None:
    """校验每个调用内的页组连续且跨调用无重叠/间隙（按逻辑文档内排序后连续）。

    注意：不同逻辑文档之间的页码独立，不要求全局连续。
    """
    # 按逻辑文档分组检查
    by_logical: dict[str, list[PlannedCall]] = {}
    for call in calls:
        by_logical.setdefault(call.logical_document_id, []).append(call)

    for logical, group in by_logical.items():
        # 组内按起始页排序
        sorted_group = sorted(group, key=lambda c: c.page_numbers[0])
        all_pages: list[int] = []
        for call in sorted_group:
            # PlannedCall 已保证内部连续，此处再保证跨调用连续无间隙/重叠
            all_pages.extend(call.page_numbers)
        if all_pages != sorted(set(all_pages)):
            raise ValueError(f"逻辑文档 {logical} 的调用页存在重复或乱序 {all_pages}")
        if all_pages:
            expected = list(range(all_pages[0], all_pages[-1] + 1))
            if all_pages != expected:
                raise ValueError(
                    f"逻辑文档 {logical} 的调用页必须连续无间隙，"
                    f"实际 {all_pages} 期望 {expected}"
                )


# --------------------------------------------------------------------------- 主规划

def plan_fact_normalization_calls(
    *,
    authority: FactAuthority,
    revision: CompleteEvidenceProcessingRevision,
    page_effective_text_map: dict[tuple[str, int], PageInput],
    doc_version_to_logical: dict[str, str],
    context_by_logical_document: dict[str, EvidenceNormalizerContextInput],
    related_requirements: list[EvidenceRequirement],
    max_pages_per_call: int = _DEFAULT_MAX_PAGES_PER_CALL,
    contract_version: str = _CONTRACT_VERSION,
) -> FactNormalizationPlan:
    """确定性规划：完整修订 + 有效文本 -> 逻辑文档调用与连续页组。

    - 默认按逻辑文档一切片，超长文档按连续页组切片；
    - 稳定哈希（不含时间/文件名/置信度）；
    - 显式完整页闭合与连续性校验；
    - 无跨 episode/隐式日期借用（仅传递有效文本哈希，不合成日期）。

    :param page_effective_text_map: key=(source_document_version_id, page_number)
        的有效文本输入（由 source adapter 从 DB 读取并投影）。
    :param doc_version_to_logical: source_document_version_id -> logical_document_id
    :param max_pages_per_call: 单次调用最大页数（>0），超长文档据此切分连续组。
    """
    if max_pages_per_call < 1:
        raise ValueError("max_pages_per_call 必须 >= 1")
    if not revision.manifest:
        raise ValueError("完整处理修订的页清单不能为空")
    if revision.status.value != "ready":
        raise ValueError("完整处理修订必须处于 READY 状态方可规划")
    if not revision.is_activatable:
        raise ValueError("完整处理修订必须为可激活方可规划")
    validate_authority_matches_revision(authority, revision)

    # 按逻辑文档分组收集页信息
    logical_to_entries: dict[str, list[EvidenceProcessingRevisionPage]] = {}
    for entry in revision.manifest:
        logical = doc_version_to_logical.get(entry.source_document_version_id)
        if not logical:
            raise ValueError(
                f"资料版本 {entry.source_document_version_id} 缺少逻辑文档映射，"
                "无法确定性规划（拒绝隐式归属）"
            )
        logical_to_entries.setdefault(logical, []).append(entry)

    # 校验：每个逻辑文档的页必须升序且连续（manifest 已保证，此处确定性再验）
    for logical, entries in logical_to_entries.items():
        pages = [e.page_number for e in sorted(entries, key=lambda x: x.page_number)]
        if pages != sorted(set(pages)):
            raise ValueError(f"逻辑文档 {logical} 的页清单存在重复 {pages}")
        # 连续性由 manifest 保证，但若调用方篡改映射，仍在此处暴露

    calls: list[PlannedCall] = []
    for logical_document_id in sorted(logical_to_entries):
        context = context_by_logical_document.get(logical_document_id)
        if context is None:
            raise ValueError(
                f"逻辑文档 {logical_document_id} 缺少资料类型、来源方和审核节点上下文"
            )
        entries = sorted(
            logical_to_entries[logical_document_id], key=lambda e: e.page_number
        )
        # 按页码收集对应的 PageInput
        page_inputs_in_order: list[PageInput] = []
        for entry in entries:
            key = (entry.source_document_version_id, entry.page_number)
            page_input = page_effective_text_map.get(key)
            if page_input is None:
                raise ValueError(
                    f"逻辑文档 {logical_document_id} 页 {entry.page_number} "
                    f"缺少有效文本输入（(source_version, page)={key}），拒绝隐式补页"
                )
            # 校验 PageInput 与 manifest 一致（无跨修订借用）
            if (
                page_input.source_document_version_id != entry.source_document_version_id
                or page_input.page_number != entry.page_number
                or page_input.page_artifact_id != entry.page_artifact_id
            ):
                raise ValueError(
                    f"PageInput {key} 与 manifest 条目不一致（page_artifact_id/page_number 漂移），拒绝"
                )
            if page_input.logical_document_id != logical_document_id:
                raise ValueError(
                    f"PageInput {key} 的 logical_document_id "
                    f"{page_input.logical_document_id} 与映射 {logical_document_id} 不一致"
                )
            page_inputs_in_order.append(page_input)

        # 超长文档按连续页组切片
        for chunk_start in range(0, len(page_inputs_in_order), max_pages_per_call):
            chunk_inputs = page_inputs_in_order[chunk_start : chunk_start + max_pages_per_call]
            chunk_page_numbers = [p.page_number for p in chunk_inputs]
            # chunk 必须连续（若原页有缺页，此处会暴露；但 manifest 保证连续，切片不会制造间隙）
            if chunk_page_numbers != list(
                range(chunk_page_numbers[0], chunk_page_numbers[-1] + 1)
            ):
                raise ValueError(
                    f"逻辑文档 {logical_document_id} 切片产生非连续页组 {chunk_page_numbers}，拒绝"
                )
            input_sha = compute_call_input_hash(
                authority=authority,
                revision=revision,
                logical_document_id=logical_document_id,
                context=context,
                related_requirements=related_requirements,
                page_numbers=chunk_page_numbers,
                page_inputs=chunk_inputs,
                contract_version=contract_version,
            )
            call = PlannedCall(
                logical_document_id=logical_document_id,
                page_numbers=tuple(chunk_page_numbers),
                page_inputs=tuple(chunk_inputs),
                context=context,
                related_requirements=tuple(related_requirements),
                input_sha256=input_sha,
            )
            calls.append(call)

    # 全局确定性排序：逻辑文档字典序 + 起始页
    calls.sort(key=lambda c: (c.logical_document_id, c.page_numbers[0]))

    # 显式完整页闭合与连续性校验（失败即拒绝，不生成空 Profile）
    validate_full_page_closure(calls, revision, doc_version_to_logical=doc_version_to_logical)
    validate_calls_contiguous(calls)

    input_scope = compute_input_scope_hash(
        authority=authority,
        revision=revision,
        calls=calls,
        max_pages_per_call=max_pages_per_call,
        contract_version=contract_version,
    )

    return FactNormalizationPlan(
        authority=authority,
        complete_processing_revision_id=revision.evidence_processing_revision_id,
        calls=tuple(calls),
        input_scope_sha256=input_scope,
        max_pages_per_call=max_pages_per_call,
        contract_version=contract_version,
    )
