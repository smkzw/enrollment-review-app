"""Target-scoped reading evidence; never an invented negative clinical fact."""
from typing import Literal

from pydantic import Field, model_validator

from app.domain.publication import canonical_hash
from .common import ContractModel
from .record_semantics import RecordSemantics
from .selective_vision_observation import SelectiveVisionObservationAttachment

VERSION = "history-source-search/v2"
PROMPT_VERSION = "history-source-search/prompt/v2"
SHA = r"^[0-9a-f]{64}$"


class HistorySearchTarget(ContractModel):
    identity_sha256: str = Field(pattern=SHA)
    family: Literal["predicate", "control"]
    proposition: str = Field(min_length=1)
    record_semantics: RecordSemantics
    condition: dict
    parent_source: dict

    @model_validator(mode="after")
    def require_history_purpose(self):
        purpose = self.record_semantics
        if (purpose.target_kind != "event_history"
                or purpose.record_obligation != "not_required_by_source"
                or purpose.proposition_direction == "unresolved"):
            raise ValueError("本次检索只适用于无需指定记录的常规既往事件")
        return self


class HistorySearchPage(ContractModel):
    page_key: str = Field(pattern=SHA)
    source_document_version_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    page_artifact_id: str = Field(min_length=1)
    page_image_sha256: str = Field(pattern=SHA)
    effective_text_sha256: str = Field(pattern=SHA)
    effective_text: str
    metadata: dict
    blockers: list[str]
    visual_sources: list[SelectiveVisionObservationAttachment] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_visual_page_identity(self):
        identities = set()
        for source in self.visual_sources:
            if (source.page_artifact_id != self.page_artifact_id
                    or source.source_document_version_id != self.source_document_version_id
                    or source.page_ordinal != self.page_number
                    or source.page_image_sha256 != self.page_image_sha256
                    or source.observation_identity_sha256 in identities):
                raise ValueError("图片核实内容与本页来源不一致或重复")
            identities.add(source.observation_identity_sha256)
        return self


class HistoryPageFinding(ContractModel):
    identity_sha256: str = Field(pattern=SHA)
    disposition: Literal["not_seen", "mentioned", "unresolved"]
    excerpts: list[str]
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_actual_mentions(self):
        if self.disposition == "mentioned" and not self.excerpts:
            raise ValueError("发现相关记录须保留实际原文")
        if self.disposition == "not_seen" and self.excerpts:
            raise ValueError("未见记录不得伪造阴性摘录")
        if any(not quote.strip() for quote in self.excerpts):
            raise ValueError("原文摘录不得为空白")
        return self


class HistoryPageRead(ContractModel):
    version: Literal["history-source-search/v2"] = VERSION
    scope_sha256: str = Field(pattern=SHA)
    page_key: str = Field(pattern=SHA)
    findings: list[HistoryPageFinding]


def validate_history_page_read(scope, page, value):
    read = HistoryPageRead.model_validate(value)
    if read.scope_sha256 != scope["scope_sha256"] or read.page_key != page.page_key:
        raise ValueError("检索结果不属于本次条款和资料页")
    identities = [item.identity_sha256 for item in read.findings]
    expected = [item["identity_sha256"] for item in scope["targets"]]
    if len(identities) != len(set(identities)) or set(identities) != set(expected):
        raise ValueError("本页检索没有完整对应所有目标，或引用了其他目标")
    for item in read.findings:
        if any(not excerpt_sources(page, quote) for quote in item.excerpts):
            raise ValueError("检索摘录不属于本页有效原文")
        if item.disposition == "not_seen" and (page.blockers or not page.effective_text.strip()):
            raise ValueError("未核清的资料页不能作为未见记录依据")
    return read


def excerpt_sources(page, excerpt):
    """Keep text and visual provenance separate, including ambiguous repeats."""
    result = []
    if excerpt in page.effective_text:
        result.append({"source_layer": "effective_text", "source_sha256": page.effective_text_sha256})
    for source in page.visual_sources:
        if excerpt in source.observation_text:
            result.append({"source_layer": "visual_observation",
                           "source_sha256": source.observation_identity_sha256,
                           "observation_id": source.observation_id})
    return result


def history_scope_hash(scope):
    return canonical_hash({key: value for key, value in scope.items() if key != "scope_sha256"})


def summarize_history_search(scope, reads):
    """Reconcile page identities, not counts; a mention never becomes absence."""
    if scope.get("version") != VERSION or history_scope_hash(scope) != scope.get("scope_sha256"):
        raise ValueError("检索资料范围身份无法核实")
    identities = [HistorySearchTarget.model_validate(row).identity_sha256 for row in scope["targets"]]
    if len(identities) != len(set(identities)):
        raise ValueError("检索目标身份重复")
    pages = {item["page_key"]: HistorySearchPage.model_validate(item) for item in scope["pages"]}
    if len(pages) != len(scope["pages"]):
        raise ValueError("检索清单的资料页身份重复")
    checked = {}
    for raw in reads:
        key = raw.get("page_key")
        if key not in pages or key in checked:
            raise ValueError("检索记录重复或来自清单以外的资料页")
        checked[key] = validate_history_page_read(scope, pages[key], raw)
    result = []
    for raw_target in scope["targets"]:
        target = HistorySearchTarget.model_validate(raw_target)
        findings = [next(row for row in read.findings if row.identity_sha256 == target.identity_sha256)
                    for read in checked.values()]
        incomplete = len(checked) != len(pages) or not pages or scope["blockers"]
        if any(row.disposition == "mentioned" for row in findings):
            status = "mentioned"
        elif incomplete or any(page.blockers for page in pages.values()):
            status = "incomplete"
        elif any(row.disposition == "unresolved" for row in findings):
            status = "unresolved"
        else:
            status = "not_seen"
        result.append({"identity_sha256": target.identity_sha256, "status": status,
                       "proposition_direction": target.record_semantics.proposition_direction,
                       "scope_sha256": scope["scope_sha256"],
                       "page_keys": sorted(checked),
                       "source_refs": [
                           {"page_key": key, "source_document_version_id": pages[key].source_document_version_id,
                            "page_artifact_id": pages[key].page_artifact_id, "page_number": pages[key].page_number,
                            "page_image_sha256": pages[key].page_image_sha256,
                            "disposition": finding.disposition,
                            "excerpts": [{"text": quote, "sources": excerpt_sources(pages[key], quote)}
                                         for quote in finding.excerpts]}
                           for key, read in sorted(checked.items())
                           for finding in read.findings if finding.identity_sha256 == target.identity_sha256],
                       "notice": "本次已提供且已核实的资料未见相关记录" if status == "not_seen" else
                                 "保留相关记录或尚未核清的资料，不按未发生处理"})
    return result
