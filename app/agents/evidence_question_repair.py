"""Source-bound question classification proposals; never rewrite clinical candidates."""

from copy import deepcopy
import hashlib
import json
from pydantic import ValidationError

from app.agents.evidence_normalizer_repair import _unique_object
from app.domain.contracts.enums import GapType
from app.domain.contracts.evidence_normalizer import EvidenceNormalizerUnresolvedItem
from app.domain.publication import canonical_hash


QUESTION_REPAIR_POLICY = "evidence-question-classification-repair/v1"
# Recovery cannot introduce an assertion that a procedure/file/judgment is absent.
RECOVERABLE_GAP_TYPES = frozenset({
    GapType.DESCRIPTION_INSUFFICIENT.value,
    GapType.DATE_OR_ANCHOR_MISSING.value,
    GapType.PROVENANCE_FOLLOWUP.value,
    GapType.OCR_OR_PARSE_RISK.value,
})


class EvidenceQuestionClassificationError(ValueError):
    def __init__(self, message, indices):
        super().__init__(message)
        self.indices = tuple(indices)


def classification_error(exc):
    """Use structured validator errors, not translated message parsing."""
    errors = exc.errors(include_url=False)
    if not errors or any(error["type"] != "normalizer_gap_type_not_supported"
                         or len(error["loc"]) != 2
                         or error["loc"][0] != "unresolved_items"
                         or not isinstance(error["loc"][1], int) for error in errors):
        return None
    return EvidenceQuestionClassificationError("疑问分类不属于本次资料整理范围，不能据此判定患者资料缺失。",
        sorted({error["loc"][1] for error in errors}))


class QuestionClassificationRepair:
    def __init__(self, raw_text, evidence_input, indices, *, reference_aliases=None):
        self.original_response = raw_text
        self.precondition = hashlib.sha256(raw_text.encode()).hexdigest()
        self.input_scope = canonical_hash(evidence_input.model_dump(mode="json"))
        self.original = _unique_object(raw_text)
        if self.original.get("schema_version") != "phase5/normalizer-draft/v5":
            raise ValueError("疑问分类恢复仅适用于当前草稿")
        expanded = (reference_aliases.transform(self.original, expand=True)
                    if reference_aliases is not None else deepcopy(self.original))
        self.indices = tuple(indices)
        questions = expanded.get("unresolved_items")
        if (not isinstance(questions, list) or not self.indices
                or tuple(sorted(set(self.indices))) != self.indices
                or any(index < 0 or index >= len(questions) for index in self.indices)):
            raise ValueError("疑问分类恢复目标不属于冻结原答")
        available_locators = set(evidence_input.available_locator_ids)
        requirements = {item.requirement_id for item in evidence_input.related_requirements}
        pages = set(evidence_input.page_numbers)
        self.questions = {}
        for index in self.indices:
            question = questions[index]
            if (not isinstance(question, dict)
                    or question.get("gap_type") not in {item.value for item in GapType}
                    or not set(question.get("affected_locator_ids", [])) <= available_locators
                    or not set(question.get("affected_requirement_ids", [])) <= requirements
                    or not set(question.get("affected_pages", [])) <= pages):
                raise ValueError("疑问类型或来源身份无效，不能限定恢复")
            try:
                EvidenceNormalizerUnresolvedItem.model_validate(question)
            except ValidationError as exc:
                if any(error["type"] != "normalizer_gap_type_not_supported" for error in exc.errors()):
                    raise ValueError("原疑问还有非分类错误，不能限定恢复") from exc
            else:
                raise ValueError("原疑问分类已经有效，不能借恢复改变含义")
            # Only classification may be invalid; these substitutions are a
            # preflight shape check, never a proposed or persisted clinical result.
            shape = {**question, "gap_type": GapType.DESCRIPTION_INSUFFICIENT.value}
            EvidenceNormalizerUnresolvedItem.model_validate(shape)
            self.questions[index] = self.original["unresolved_items"][index]
        self.targets = {index: canonical_hash(question) for index, question in self.questions.items()}
        self.locator_context = [item.model_dump(mode="json") for item in evidence_input.available_locators
            if item.locator_id in {lid for index in self.indices
                for lid in questions[index].get("affected_locator_ids", [])}]
        if reference_aliases is not None:
            self.locator_context = reference_aliases.transform(self.locator_context)

    def prompt(self):
        return (
            "仅核对以下已保存疑问的分类，不重新读取或改写事实、事件、用药、日期、原句及来源。"
            "根据原有疑问和冻结来源，选择能忠实表示问题的分类。已写但字迹不清不等于未记录；"
            "记录含义不明不等于未执行。不得新增患者缺资料、缺研究者判断或未做检查的断言。"
            "没有忠实分类时gap_type返回null，保留失败；不能为了通过检查强行映射。"
            "只返回本次小提案对象，不返回整份草稿，不改变原来的疑问或资料要求关联。"
            + json.dumps({"policy": QUESTION_REPAIR_POLICY, "precondition_sha256": self.precondition,
                "input_scope_sha256": self.input_scope, "allowed_gap_types": sorted(RECOVERABLE_GAP_TYPES),
                "targets": [{"index": index, "question_sha256": self.targets[index],
                    "question": self.questions[index]} for index in self.indices],
                "frozen_locators": self.locator_context, "output_schema": self.schema()},
                ensure_ascii=False, sort_keys=True)
        )

    def schema(self):
        return {"type": "object", "additionalProperties": False,
            "required": ["policy", "precondition_sha256", "input_scope_sha256", "changes"],
            "properties": {"policy": {"const": QUESTION_REPAIR_POLICY},
                "precondition_sha256": {"const": self.precondition},
                "input_scope_sha256": {"const": self.input_scope},
                "changes": {"type": "array", "minItems": len(self.indices), "maxItems": len(self.indices),
                    "items": {"type": "object", "additionalProperties": False,
                        "required": ["index", "question_sha256", "gap_type"],
                        "properties": {"index": {"type": "integer", "enum": list(self.indices)},
                            "question_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                            "gap_type": {"enum": [*sorted(RECOVERABLE_GAP_TYPES), None]}}}}}}

    def apply(self, proposal_text):
        from jsonschema import Draft202012Validator

        proposal = _unique_object(proposal_text)
        Draft202012Validator(self.schema()).validate(proposal)
        changes = proposal["changes"]
        if len({item["index"] for item in changes}) != len(self.indices):
            raise ValueError("疑问分类提案不能遗漏或重复目标")
        composed = deepcopy(self.original)
        for item in changes:
            index = item["index"]
            if item["question_sha256"] != self.targets[index]:
                raise ValueError("疑问分类提案与原疑问身份不一致")
            if item["gap_type"] is None:
                raise ValueError("原疑问没有可忠实采用的分类，保留待核")
            composed["unresolved_items"][index]["gap_type"] = item["gap_type"]
        # The model never provides the replacement clinical draft.
        text = json.dumps(composed, ensure_ascii=False, sort_keys=True)
        receipt = {"policy": QUESTION_REPAIR_POLICY, "input_scope_sha256": self.input_scope,
            "original_response": self.original_response, "raw_output_sha256": self.precondition,
            "proposal_response": proposal_text, "proposal_sha256": hashlib.sha256(proposal_text.encode()).hexdigest(),
            "target_indices": list(self.indices), "composed_sha256": hashlib.sha256(text.encode()).hexdigest()}
        return text, receipt


def compose_question_repair(receipt, evidence_input, *, reference_aliases=None):
    """Rebuild only the frozen classification composition, without adopting it."""
    repair = QuestionClassificationRepair(receipt["original_response"], evidence_input,
        receipt["target_indices"], reference_aliases=reference_aliases)
    text, rebuilt = repair.apply(receipt["proposal_response"])
    if any(receipt.get(key) != value for key, value in rebuilt.items()):
        raise ValueError("疑问分类恢复证明的原答、输入、提案或范围不一致")
    return text


def replay_question_repair(receipt, evidence_input, *, reference_aliases=None, partition_receipt=None):
    """Reconstruct both transformations; a stored proof is not adoption permission."""
    from app.agents.evidence_normalizer import parse_evidence_normalizer_output, _validate_normalizer_semantics

    text = compose_question_repair(receipt, evidence_input, reference_aliases=reference_aliases)
    if partition_receipt is not None:
        from app.agents.evidence_candidate_partition import recover_source_local_candidates
        if (partition_receipt.get("original_response") != text
                or partition_receipt.get("raw_output_sha256") != receipt["composed_sha256"]):
            raise ValueError("局部保留必须来自已证明的分类组成答，不能借另份模型回答")
        partition = recover_source_local_candidates(text, evidence_input, reference_aliases=reference_aliases)
        if any(partition_receipt.get(key) != value for key, value in partition.receipt.items()):
            raise ValueError("分类组成后的局部保留证明不一致")
        return partition.output
    output = parse_evidence_normalizer_output(text, expected_run_id=evidence_input.run_id,
        expected_call_id=evidence_input.call_id, expected_logical_document_id=evidence_input.logical_document_id,
        expected_page_numbers=evidence_input.page_numbers, available_locator_ids=set(evidence_input.available_locator_ids),
        locator_source_hashes={item.locator_id: item.source_text_sha256 for item in evidence_input.available_locators},
        locator_source_texts={item.locator_id: item.localized_text for item in evidence_input.available_locators},
        created_at=evidence_input.created_at, reference_aliases=reference_aliases, require_current_draft=True)
    return _validate_normalizer_semantics(output, evidence_input)
