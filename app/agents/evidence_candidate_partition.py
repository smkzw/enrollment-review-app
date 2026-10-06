"""Quarantine source-local draft failures without rewriting valid siblings."""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from types import SimpleNamespace
from jsonschema import Draft202012Validator, FormatChecker

from app.agents.evidence_normalizer_repair import (
    EvidenceContextError, EvidenceProspectiveError, EvidenceSourceObjectError,
    EvidenceDerivedSourceError, EvidenceNumericUnitError, EvidenceNormalizedValueError,
    _unique_object,
)
from app.domain.contracts.evidence_normalizer import EvidenceNormalizerUnresolvedItem
from app.domain.publication import canonical_hash


CANDIDATE_PARTITION_POLICY = "evidence-candidate-partition/v3"


@dataclass(frozen=True)
class CandidatePartition:
    output: object
    receipt: dict


def recover_source_local_candidates(text, evidence_input, *, reference_aliases=None):
    from app.agents.evidence_normalizer import (
        parse_evidence_normalizer_output, _validate_normalizer_semantics,
    )

    def validate(remainder):
        decoded = parse_evidence_normalizer_output(remainder,
            expected_run_id=evidence_input.run_id, expected_call_id=evidence_input.call_id,
            expected_logical_document_id=evidence_input.logical_document_id,
            expected_page_numbers=evidence_input.page_numbers,
            available_locator_ids=set(evidence_input.available_locator_ids),
            locator_source_hashes={item.locator_id: item.source_text_sha256
                                   for item in evidence_input.available_locators},
            locator_source_texts={item.locator_id: item.localized_text
                                 for item in evidence_input.available_locators},
            created_at=evidence_input.created_at, require_current_draft=True)
        return _validate_normalizer_semantics(decoded, evidence_input)

    expanded = (reference_aliases.transform(_unique_object(text), expand=True)
                if reference_aliases is not None else None)
    source = json.dumps(expanded, ensure_ascii=False, sort_keys=True) if expanded is not None else text
    partition = partition_source_local_candidates(source, evidence_input, validate=validate)
    partition.receipt["raw_output_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    partition.receipt["original_response"] = text
    if reference_aliases is not None:
        partition.receipt["reference_aliases"] = reference_aliases.aliases
    return partition


def partition_source_local_candidates(text, evidence_input, *, validate):
    """Revalidate the unchanged remainder; global faults still fail closed.

    ``validate`` is the normal production decoder and semantic validator. It may
    identify only a bounded source/context/scope failure or an unexpressed value/unit.
    No model, word list, alternative value or invented source is used here.
    """
    from app.agents.evidence_normalizer import (
        EvidenceNormalizerDraftOutput, EvidenceFactDraft, EvidenceEventDraft,
        EvidenceExposureDraft, _demote_invalid_date_ranges, _demote_conflicting_duration_status,
        _normalize_evidence_json, _ALLOWED_CANDIDATE_SOURCE_SEMANTICS,
    )

    original = _unique_object(text)
    if (original.get("schema_version") != "phase5/normalizer-draft/v5"
            or set(original) - set(EvidenceNormalizerDraftOutput.model_fields)):
        raise ValueError("局部保留仅适用于身份完整的当前语义草稿")
    # Check even items that will be quarantined: deletion cannot hide a malformed answer.
    structural_errors = list(Draft202012Validator(
        EvidenceNormalizerDraftOutput.model_json_schema(), format_checker=FormatChecker(),
    ).iter_errors(original))
    if structural_errors:
        raise ValueError("原答结构不完整，不能通过局部隔离绕过输出合同")
    for question in original.get("unresolved_items", []):
        refs = question.get("affected_observation_refs", [])
        if len(refs) != len(set(refs)):
            raise ValueError("未解决项观察身份重复，不能以局部隔离绕过合同")
    metadata_checked = _demote_conflicting_duration_status(
        _demote_invalid_date_ranges(_normalize_evidence_json(deepcopy(original), preserve_boolean_objects=True),
            page_numbers=evidence_input.page_numbers),
        page_numbers=evidence_input.page_numbers)
    fields = {"fact_candidates": EvidenceFactDraft, "event_candidates": EvidenceEventDraft,
              "exposure_candidates": EvidenceExposureDraft}
    collections = {}
    all_refs = []
    available = set(evidence_input.available_locator_ids)
    for key, model in fields.items():
        items = original.get(key, [])
        if not isinstance(items, list):
            raise ValueError("局部保留缺少可核实的候选清单")
        for index, item in enumerate(items):
            if not isinstance(item, dict) or set(item) - set(model.model_fields):
                raise ValueError("候选含未知字段，不能以局部保留绕过输出合同")
            ref = item.get("candidate_ref")
            locators = item.get("locator_ids")
            if (not isinstance(ref, str) or not ref.strip() or not isinstance(locators, list)
                    or not locators or any(not isinstance(lid, str) for lid in locators)
                    or not set(locators) <= available):
                raise ValueError("候选身份或来源越界，不能作局部保留")
            all_refs.append(ref)
            if metadata_checked[key][index]["candidate_source_semantics"] not in _ALLOWED_CANDIDATE_SOURCE_SEMANTICS:
                raise ValueError("原答来源语义无效，不能以局部隔离隐藏")
            from app.domain.contracts.facts import PartialDateRange
            for date_field in ("date_range", "start_range", "end_range"):
                if metadata_checked[key][index].get(date_field) is not None:
                    PartialDateRange.model_validate(metadata_checked[key][index][date_field])
            if key != "fact_candidates":
                model.model_validate(metadata_checked[key][index])
        collections[key] = items
    if len(all_refs) != len(set(all_refs)):
        raise ValueError("候选身份重复，不能选择其中一份作局部保留")
    fact_refs = {item["candidate_ref"] for item in collections["fact_candidates"]}
    requirements = {item.requirement_id for item in evidence_input.related_requirements}
    source_proxies = []
    for item in collections["fact_candidates"]:
        basis = item.get("assertion_basis")
        if item.get("assertion_scope") is None:
            raise ValueError("原答缺少发生状态，不能以隔离绕过当前合同")
        if item["polarity"] == "negated" and (item.get("raw_value") is False or item.get("canonical_value") is False):
            raise ValueError("原答重复否定命题，不能以隔离绕过当前合同")
        if not set(item.get("supported_requirement_ids", [])) <= requirements:
            raise ValueError("原答绑定了冻结输入之外的资料要求，不能局部隔离")
        refs = item.get("source_observation_refs", [])
        if len(refs) != len(set(refs)) or any(not ref.strip() for ref in refs):
            raise ValueError("原答观察身份重复或为空，不能局部隔离")
        if item.get("value_kind") == "identifier":
            from app.domain.contracts.identifier_value import validate_identifier_value
            validate_identifier_value(item.get("raw_value"), item.get("canonical_value"),
                item.get("unit"), basis.get("assertion_text") if basis else None)
        if isinstance(basis, dict):
            if basis.get("locator_id") not in item["locator_ids"]:
                raise ValueError("断言来源与候选不一致，不能作局部保留")
            for qualifier in basis.get("contextual_qualifiers", []) or []:
                if isinstance(qualifier, dict) and isinstance(qualifier.get("source"), dict):
                    if qualifier["source"].get("locator_id") not in item["locator_ids"]:
                        raise ValueError("另处来源越界，不能作局部保留")
        # Source binding is checked before hydration can stop at a local value fault.
        source_basis = None if basis is None else SimpleNamespace(contextual_qualifiers=[
            SimpleNamespace(source=SimpleNamespace(**qualifier["source"]) if qualifier.get("source") else None)
            for qualifier in basis.get("contextual_qualifiers", [])])
        source_proxies.append(SimpleNamespace(candidate_id=item["candidate_ref"],
            source_observation_refs=refs, locator_ids=item["locator_ids"], assertion_basis=source_basis))
    from app.projections.page_review_sources import validate_accepted_candidate_sources
    validate_accepted_candidate_sources(SimpleNamespace(fact_candidates=source_proxies), evidence_input.page_review,
        locator_inputs=evidence_input.available_locators)
    for question in original.get("unresolved_items", []):
        if not set(question.get("affected_requirement_ids", [])) <= requirements:
            raise ValueError("原答疑问引用了冻结输入之外的资料要求")
    for key in ("event_candidates", "exposure_candidates"):
        for item in collections[key]:
            refs = item.get("fact_candidate_refs")
            if (not isinstance(refs, list) or not refs
                    or any(not isinstance(ref, str) for ref in refs) or not set(refs) <= fact_refs):
                raise ValueError("派生关系不完整，不能决定局部保留范围")
    for key in ("actual_exposure_fact_refs", "non_exposure_medication_fact_refs"):
        refs = original.get(key)
        if (not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs)
                or refs != sorted(set(refs)) or not set(refs) <= fact_refs):
            raise ValueError("用药分类身份不完整，不能作局部保留")
    if set(original["actual_exposure_fact_refs"]) & set(original["non_exposure_medication_fact_refs"]):
        raise ValueError("同一候选的用药分类冲突，不能作局部保留")
    actual = set(original["actual_exposure_fact_refs"])
    non_exposure = set(original["non_exposure_medication_fact_refs"])
    medication = {item["candidate_ref"] for item in collections["fact_candidates"]
                  if item["profile_lane"] == "medication" and item["polarity"] == "affirmed"}
    exposure_refs = {ref for item in collections["exposure_candidates"]
                     for ref in item["fact_candidate_refs"]}
    if actual | non_exposure != medication or exposure_refs != actual:
        raise ValueError("原答的药物分类或暴露依赖不完整，不能以隔离修补关系")

    locators = {item.locator_id: item for item in evidence_input.available_locators}

    def retained_questions(quarantined):
        questions = []
        for key in fields:
            for item in collections[key]:
                if item["candidate_ref"] not in quarantined:
                    continue
                lids = sorted(set(item["locator_ids"]))
                missing_unit = any(failure["code"] == "EvidenceNumericUnitError"
                    and item["candidate_ref"] in failure["candidate_refs"] for failure in failures)
                missing_value = any(failure["code"] == "EvidenceNormalizedValueError"
                    and item["candidate_ref"] in failure["candidate_refs"] for failure in failures)
                questions.append(EvidenceNormalizerUnresolvedItem(
                    code=("numeric_unit_missing" if missing_unit else "normalized_value_missing" if missing_value
                          else "candidate_source_validation_failed"),
                    message=("这项数值的单位尚未核清，未作为正式数值采用。" if missing_unit
                        else "这项记录的明确取值尚未核清，保留原文待核，未作为病史采用。" if missing_value
                        else "这项记录尚未通过原文及含义核对，未作为病史采用。"),
                    affected_pages=sorted({locators[lid].page_number for lid in lids}),
                    affected_locator_ids=lids,
                    affected_observation_refs=sorted(item.get("source_observation_refs", [])),
                    reason="这项记录及依靠它整理出的内容保留待核；"
                           "这是资料整理问题，不表示患者未做检查或不符合入排要求。",
                ).model_dump(mode="json"))
        return questions

    rejected, failures = set(), []
    while True:
        projection = deepcopy(original)
        # Isolate the full closure, never shorten an exposure or reclassify its facts.
        while True:
            removed_exposures = [item for item in collections["exposure_candidates"]
                                 if item["candidate_ref"] in rejected
                                 or set(item["fact_candidate_refs"]) & rejected]
            remaining_exposure_refs = {ref for item in collections["exposure_candidates"]
                                      if item not in removed_exposures
                                      for ref in item["fact_candidate_refs"]}
            orphaned = actual - rejected - remaining_exposure_refs
            if not orphaned:
                break
            rejected.update(orphaned)
            failures.append({"code": "exposure_dependency_quarantined",
                "candidate_refs": sorted(orphaned), "detail": "依赖的完整用药暴露被隔离，不能改变其分类"})
        dependent = {item["candidate_ref"] for key in ("event_candidates", "exposure_candidates")
                     for item in collections[key] if set(item["fact_candidate_refs"]) & rejected}
        quarantined = rejected | dependent
        for key in fields:
            projection[key] = [item for item in projection.get(key, [])
                               if item["candidate_ref"] not in quarantined]
        for key in ("actual_exposure_fact_refs", "non_exposure_medication_fact_refs"):
            projection[key] = [ref for ref in projection[key] if ref not in rejected]
        projection["unresolved_items"] = [*deepcopy(original.get("unresolved_items", [])),
                                          *retained_questions(quarantined)]
        # Order does not carry meaning for this explicit source-reference set.
        for question in projection["unresolved_items"]:
            if "affected_observation_refs" in question:
                question["affected_observation_refs"] = sorted(question["affected_observation_refs"])
        try:
            output = validate(json.dumps(projection, ensure_ascii=False, sort_keys=True))
            break
        except EvidenceNumericUnitError as exc:
            if type(exc) is not EvidenceNumericUnitError or exc.candidate_ref not in fact_refs - rejected:
                raise
            rejected.add(exc.candidate_ref)
            failures.append({"code": type(exc).__name__, "candidate_refs": [exc.candidate_ref],
                "detail": str(exc)})
        except EvidenceNormalizedValueError as exc:
            if type(exc) is not EvidenceNormalizedValueError or exc.candidate_ref not in fact_refs - rejected:
                raise
            rejected.add(exc.candidate_ref)
            failures.append({"code": type(exc).__name__, "candidate_refs": [exc.candidate_ref],
                "detail": str(exc)})
        except EvidenceDerivedSourceError as exc:
            valid_refs = {item["candidate_ref"] for item in collections.get(exc.collection, [])}
            if exc.collection not in {"event_candidates", "exposure_candidates"} or exc.candidate_ref not in valid_refs - rejected:
                raise
            rejected.add(exc.candidate_ref)
            failures.append({"code": type(exc).__name__, "candidate_refs": [exc.candidate_ref],
                             "collection": exc.collection, "detail": str(exc)})
        except EvidenceSourceObjectError as exc:
            if (type(exc) not in {EvidenceSourceObjectError, EvidenceContextError, EvidenceProspectiveError}
                    or not exc.bounded_repair or not exc.candidate_refs
                    or not set(exc.candidate_refs) <= fact_refs - rejected):
                raise
            rejected.update(exc.candidate_refs)
            failures.append({"code": type(exc).__name__, "candidate_refs": sorted(exc.candidate_refs),
                             "detail": str(exc)})
    if not rejected or not output.fact_candidates:
        raise ValueError("没有可独立保留的合法事实；原作业仍需核对")
    receipt = {
        "policy": CANDIDATE_PARTITION_POLICY,
        "input_sha256": canonical_hash(evidence_input.model_dump(mode="json")),
        "raw_output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "original_response": text,
        "original_draft": original,
        "retained_draft": projection,
        "quarantined_candidate_refs": sorted(quarantined),
        "failures": failures,
        "output": output.model_dump(mode="json"),
    }
    return CandidatePartition(output, receipt)
