"""候选检索回执的工件保存/装载（candidate-only，纯工程存储，无编排/临床语义）。

最小可复用助手，完全复用既有 ``ArtifactStore`` 的 ``raw_response`` 工件类别
（不发明持久化框架、数据表或新工件类别）：

- ``save_judgment_search_receipt``：把**当前**仓储准备的 scope/target 下通过
  ``assemble_judgment_search_coverage`` 绑定核验的一条完整已验证回执存为
  规范化 JSON 字节（``sort_keys`` 确定性序列化；完整保留内嵌原始
  ``PageCompletion``、逐字摘录、``uncertainty_note``、未核实坐标约定与元数据），
  返回既有 ``StoredArtifact``。同内容幂等去重 → 同字节同身份。
- ``load_judgment_search_receipt``：按既有 ``storage_ref`` 读取（ArtifactStore
  内容哈希完整性复核），以现行读器解析器严格解析**一个完整 JSON 对象**
  （重复键拒绝），按当前合同验证回执，然后再次经
  ``assemble_judgment_search_coverage`` 与**当前** scope/target 绑定核验后返回。
  单条回执覆盖不完整是合法存储状态，不构成覆盖完成。

诚实边界（术语与实现一致）：

- 调用方负责用 ``prepare_judgment_search_target`` 从当前数据库准备 scope 与
  target；本模块绝不从保存的 scope 静默重建信任——装载核验一律使用调用方
  准备的当前来源。
- 不重标、不迁移旧回执：过时提示版本/语义的回执在绑定核验处显式报错，
  绝不静默消失、绝不折叠成 not_found、绝不自动接纳。
- 损坏、外来类别或语义漂移的工件都产生明确有界的
  ``JudgmentSearchArtifactError``（ValueError，保留 cause 链）；绑定核验失败
  原样传播既有 ``JudgmentSearchResultsError``（同为 ValueError 域错误）。
- 这是工程存储：不是持久编排、不是重试/作业接线、不产生任何接受结论或缺口；
  ``product_acceptance`` 在保存与装载后均恒为 False。
"""
from __future__ import annotations

import json

from pydantic import ValidationError

from app.domain.contracts.judgment_search import JudgmentSearchScope
from app.evidence.artifacts import (
    ArtifactStore,
    ArtifactStoreError,
    StoredArtifact,
)
from app.llm.judgment_search_reader import (
    JudgmentSearchReaderError,
    JudgmentSearchReaderReceipt,
)
from app.llm.judgment_search_reader import (
    _extract_single_json_object as _parse_single_json_object,
)
from app.services.judgment_search_results import assemble_judgment_search_coverage

_RAW_RESPONSE_REF_PREFIX = "artifacts/raw_response/"

__all__ = [
    "JudgmentSearchArtifactError",
    "load_judgment_search_receipt",
    "save_judgment_search_receipt",
]


class JudgmentSearchArtifactError(ValueError):
    """回执工件的存储/解析/合同错误（ValueError，保留 cause 链）。

    存储读取、字节解码、JSON 解析与合同验证失败都包装为本异常并保留底层
    异常；与当前 scope/target 的绑定核验失败原样传播既有
    ``JudgmentSearchResultsError``。损坏/外来/过时回执绝不静默消失，
    也绝不折叠成 not_found。
    """


def _canonical_receipt_bytes(receipt: JudgmentSearchReaderReceipt) -> bytes:
    """回执的规范化 JSON 字节：确定性序列化，完整保留全部字段与原始完成。"""
    return json.dumps(
        receipt.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def save_judgment_search_receipt(
    store: ArtifactStore,
    scope: JudgmentSearchScope,
    target_text: str,
    receipt: JudgmentSearchReaderReceipt,
) -> StoredArtifact:
    """把一条与当前 scope/target 绑定核验通过的回执存为 raw_response 工件。"""
    try:
        validated = JudgmentSearchReaderReceipt.model_validate(receipt.model_dump())
    except ValidationError as exc:
        raise JudgmentSearchArtifactError(
            f"回执未通过当前合同验证，拒绝保存：{exc.error_count()} 项错误"
        ) from exc
    # 绑定核验复用装配函数：原始回答、页/目标/模型/提示身份必须与当前
    # scope/target 一致；单条回执覆盖不完整是合法存储状态，不检查覆盖状态。
    assemble_judgment_search_coverage(scope, target_text, [validated])
    return store.put("raw_response", _canonical_receipt_bytes(validated))


def load_judgment_search_receipt(
    store: ArtifactStore,
    scope: JudgmentSearchScope,
    target_text: str,
    storage_ref: str,
) -> JudgmentSearchReaderReceipt:
    """按存储引用装载回执并用当前 scope/target 重新绑定核验。"""
    if not storage_ref.startswith(_RAW_RESPONSE_REF_PREFIX):
        raise JudgmentSearchArtifactError(
            f"拒绝非 raw_response 工件引用 {storage_ref!r}：候选回执只保存于 "
            f"{_RAW_RESPONSE_REF_PREFIX}<sha256>"
        )
    try:
        payload = store.read(storage_ref)
    except ArtifactStoreError as exc:
        raise JudgmentSearchArtifactError(
            f"回执工件读取失败（缺失或完整性复核不通过）：{exc}"
        ) from exc
    try:
        text = payload.decode("utf-8")
        if not text.lstrip().startswith("{"):
            raise JudgmentSearchArtifactError("系统保存的回执必须为纯 JSON 对象，不接受代码围栏")
        raw = _parse_single_json_object(text)
    except (UnicodeDecodeError, JudgmentSearchReaderError) as exc:
        raise JudgmentSearchArtifactError(
            f"回执工件不是可解析的完整单对象 JSON（重复键/截断/包装均拒绝）：{exc}"
        ) from exc
    try:
        receipt = JudgmentSearchReaderReceipt.model_validate(raw)
    except ValidationError as exc:
        raise JudgmentSearchArtifactError(
            f"回执工件未通过当前合同验证：{exc.error_count()} 项错误"
        ) from exc
    # 与当前 scope/target 的绑定核验：过时/漂移回执在此显式失败
    # （既有 JudgmentSearchResultsError，ValueError 域），绝不静默接纳。
    assemble_judgment_search_coverage(scope, target_text, [receipt])
    return receipt
