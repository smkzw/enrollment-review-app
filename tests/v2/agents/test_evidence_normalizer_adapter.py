"""Evidence Normalizer 适配器与解码器聚焦测试。

覆盖中文原生系统提示、紧凑严格 JSON Schema、运行时解码器与有界传输适配器。
不依赖真实模型、不访问数据库、不生成 Profile。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest
from jsonschema import Draft202012Validator

from app.agents.evidence_normalizer import (
    EvidenceNormalizerRunner,
    build_evidence_normalizer_prompt,
    evidence_normalizer_compact_schema,
    evidence_normalizer_json_schema,
    evidence_normalizer_prompt_template_sha256,
    parse_evidence_normalizer_output,
    validate_evidence_normalizer_output,
    _SCHEMA_REPAIR_CONTRACT,
    _SYSTEM_CONTRACT,
    _enforce_exposure_source_fields,
)
from app.domain.contracts.evidence_normalizer import (
    EvidenceNormalizerContextInput,
    EvidenceNormalizerInput,
    EvidenceNormalizerLocatorInput,
    EvidenceNormalizerPageInput,
    EvidenceNormalizerPageReviewInput,
    evidence_normalizer_input_scope_hash,
    page_review_input_scope_hash,
)
from app.domain.contracts.enums import LocatorPrecision, LocatorSourceLayer, ReviewStage
from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.page_review import (
    ClauseEvidenceSignal,
    EvidenceSignal,
    PageCoverageEntry,
    PageDisposition,
    PageReconciliation,
    PageRegion,
    PageReviewLane,
    PageReviewRecord,
)
from app.domain.contracts.rules import EvidenceRequirement

UTC = timezone.utc
NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
SHA = "a" * 64


def _authority():
    return FactAuthority(
        project_id="p1", subject_id="s1", review_episode_id="e1", episode_revision=1,
        protocol_version_id="pv1", rule_set_id="rs1", rule_set_revision=1,
        evidence_snapshot_v2_id="snap1", complete_processing_revision_id="rev1",
    )


def _page(num: int, text: str, locs: list[str]) -> EvidenceNormalizerPageInput:
    return EvidenceNormalizerPageInput(
        source_document_version_id="docv-A",
        page_artifact_id=f"page-{num}",
        ocr_page_id=f"ocr-{num}",
        page_number=num,
        effective_text=text,
        effective_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        locator_ids=sorted(locs),
    )


def _input(
    related_requirements=(),
    *,
    document_type="筛选病历",
    source_party="研究者",
):
    auth = _authority()
    p1 = _page(1, "患者无糖尿病病史。", ["loc-1"])
    p2 = _page(2, "收缩压 120 mmHg。", ["loc-2"])
    context = EvidenceNormalizerContextInput(
        source_document_version_id="docv-A",
        metadata_revision_id="meta-A-1",
        document_type=document_type,
        source_party=source_party,
        current_review_stage=ReviewStage.SCREENING,
        workflow_stage_id="rs1:screening",
    )
    locators = [
        EvidenceNormalizerLocatorInput(
            locator_id="loc-1", page_number=1,
            source_layer=LocatorSourceLayer.EFFECTIVE_TEXT,
            precision=LocatorPrecision.TEXT_RANGE,
            source_text_sha256=p1.effective_text_sha256,
            localized_text=p1.effective_text,
        ),
        EvidenceNormalizerLocatorInput(
            locator_id="loc-2", page_number=2,
            source_layer=LocatorSourceLayer.EFFECTIVE_TEXT,
            precision=LocatorPrecision.TEXT_RANGE,
            source_text_sha256=p2.effective_text_sha256,
            localized_text=p2.effective_text,
        ),
    ]
    hs = evidence_normalizer_input_scope_hash(
        authority=auth, logical_document_id="doc-A", manifest_sha256=SHA,
        context=context, related_requirements=list(related_requirements),
        completion_manifest_sha256="b" * 64, page_numbers=[1, 2], pages=[p1, p2],
        available_locator_ids=["loc-1", "loc-2"], available_locators=locators,
    )
    return EvidenceNormalizerInput(
        run_id="run-1", call_id="call-1", authority=auth, logical_document_id="doc-A",
        context=context, related_requirements=list(related_requirements),
        manifest_sha256=SHA, completion_manifest_sha256="b" * 64,
        page_numbers=[1, 2], pages=[p1, p2], available_locator_ids=["loc-1", "loc-2"],
        available_locators=locators,
        input_scope_sha256=hs, created_at=NOW,
    )


def _valid_output_dict():
    # 最小合法输出：空候选 + 一条未解决
    return {
        "schema_version": "phase5/v1",
        "run_id": "run-1",
        "call_id": "call-1",
        "logical_document_id": "doc-A",
        "page_numbers": [1, 2],
        "fact_candidates": [],
        "event_candidates": [],
        "exposure_candidates": [],
        "unresolved_items": [
            {"code": "page_unreadable", "message": "两页均需核对", "affected_pages": [1, 2], "affected_locator_ids": [], "reason": "页1和页2均存在需要人工核对的字符"}
        ],
    }


# ------------------------------------------------------------- 系统提示与 Schema

def test_system_contract_is_chinese_native_and_covers_required_terms():
    assert "候选" in _SYSTEM_CONTRACT
    assert "未解决" in _SYSTEM_CONTRACT
    assert "沉默" in _SYSTEM_CONTRACT
    assert "否定" in _SYSTEM_CONTRACT
    assert "未知" in _SYSTEM_CONTRACT
    assert "洗脱期" in _SYSTEM_CONTRACT
    assert "溯源提醒" in _SYSTEM_CONTRACT
    assert "不能替代清晰事实候选" in _SYSTEM_CONTRACT
    assert "已经校对的当前有效文本" in _SYSTEM_CONTRACT
    assert "文本或布尔规范值的 unit 必须是 JSON null" in _SYSTEM_CONTRACT
    assert "单页或单份资料未出现某项要求，不代表整个证据包缺失" in _SYSTEM_CONTRACT
    assert "全部页组处理完成后统一核对" in _SYSTEM_CONTRACT
    for source_semantics in [
        "同期客观结果",
        "既往原始资料",
        "当前研究病历直接记录",
        "筛选病历转述",
        "无法确认来源",
    ]:
        assert source_semantics in _SYSTEM_CONTRACT
    assert "不得" in _SYSTEM_CONTRACT
    # 覆盖类别抽样
    for term in ["人口学", "药物暴露", "检验", "过敏"]:
        assert term in _SYSTEM_CONTRACT
    assert "不得补全残缺药名" in _SYSTEM_CONTRACT
    assert "仅因版面自动换行而分布在同页相邻定位" in _SYSTEM_CONTRACT
    assert "模型推测写入候选字段" in _SYSTEM_CONTRACT
    assert "邮件讨论、审核意见、治疗建议" in _SYSTEM_CONTRACT
    assert "发放、领取、携回" in _SYSTEM_CONTRACT
    assert "本身也不能证明已实际使用" in _SYSTEM_CONTRACT
    assert "不得生成 exposure_candidate" in _SYSTEM_CONTRACT
    assert "raw_value、canonical_value、unit 和 assertion_basis 填为 JSON null" in _SYSTEM_CONTRACT
    assert "连同虚词截取原句中的连续片段" in _SYSTEM_CONTRACT


def test_schema_repair_contract_requires_verbatim_asserted_object_repair():
    assert "直接截取最短连续临床名词" in _SCHEMA_REPAIR_CONTRACT
    assert "两处必须填同一个字符串" in _SCHEMA_REPAIR_CONTRACT
    assert "连同虚词原样截取原句中的连续片段" in _SCHEMA_REPAIR_CONTRACT
    assert "不得删除该候选来规避修复" in _SCHEMA_REPAIR_CONTRACT
    assert "原句明确给出定量结果" in _SCHEMA_REPAIR_CONTRACT
    assert "affirmed 的 raw_value" in _SCHEMA_REPAIR_CONTRACT
    assert "同一检验检查时点被拆成多条事件" in _SCHEMA_REPAIR_CONTRACT


def test_decoder_rejects_per_analyte_events_for_one_precise_test_occurrence():
    inp = _input()
    payload = {
        "schema_version": "phase5/normalizer-draft/v3",
        "actual_exposure_fact_refs": [],
        "non_exposure_medication_fact_refs": [],
        "fact_candidates": [
            {
                "candidate_ref": ref,
                "fact_type": "检验",
                "profile_lane": "test_exam_score",
                "polarity": "affirmed",
                "asserted_object": obj,
                "raw_value": value,
                "canonical_value": value,
                "unit": unit,
                "date_range": None,
                "record_time": None,
                "locator_ids": [locator],
                "candidate_source_semantics": "同期客观结果",
                "assertion_basis": {
                    "asserted_object": obj,
                    "assertion_text": text,
                    "locator_id": locator,
                },
                "model_uncertainty": 0.05,
            }
            for ref, obj, value, unit, locator, text in [
                ("f1", "淋巴细胞", 1.88, "10^9/L", "loc-1", "淋巴细胞 1.88 10^9/L"),
                ("f2", "收缩压", 120, "mmHg", "loc-2", "收缩压 120 mmHg"),
            ]
        ],
        "event_candidates": [
            {
                "candidate_ref": event_ref,
                "event_type": "检验采样",
                "profile_lane": "test_exam_score",
                "start_range": {
                    "source_text": "采样时间：2025-08-15 09:46",
                    "precision": "day",
                    "lower_bound": "2025-08-15",
                    "upper_bound": "2025-08-15",
                },
                "end_range": None,
                "duration_status": "single",
                "record_time": None,
                "fact_candidate_refs": [fact_ref],
                "locator_ids": [locator],
                "candidate_source_semantics": "同期客观结果",
                "model_uncertainty": 0.05,
            }
            for event_ref, fact_ref, locator in [
                ("e1", "f1", "loc-1"),
                ("e2", "f2", "loc-2"),
            ]
        ],
        "exposure_candidates": [],
        "unresolved_items": [],
    }

    with pytest.raises(ValueError, match="同一检验检查在同一明确时刻被拆成多条事件"):
        parse_evidence_normalizer_output(
            json.dumps(payload, ensure_ascii=False),
            expected_run_id=inp.run_id,
            expected_call_id=inp.call_id,
            expected_logical_document_id=inp.logical_document_id,
            expected_page_numbers=inp.page_numbers,
            available_locator_ids=set(inp.available_locator_ids),
            locator_source_hashes={
                item.locator_id: item.source_text_sha256
                for item in inp.available_locators
            },
            created_at=inp.created_at,
        )


def test_prompt_template_sha_is_stable():
    t = "请按输入页组抽取候选。"
    assert evidence_normalizer_prompt_template_sha256(t) == evidence_normalizer_prompt_template_sha256(t)
    assert evidence_normalizer_prompt_template_sha256(t) != evidence_normalizer_prompt_template_sha256(t + "x")


def test_visual_observation_boundary_changes_prompt_identity(monkeypatch):
    from app.agents import evidence_normalizer

    template = "请按输入页组抽取候选。"
    original = evidence_normalizer_prompt_template_sha256(template)
    monkeypatch.setattr(
        evidence_normalizer,
        "_VISUAL_OBSERVATION_PROMPT_BOUNDARY",
        evidence_normalizer._VISUAL_OBSERVATION_PROMPT_BOUNDARY + "核对新范围。",
    )
    assert evidence_normalizer_prompt_template_sha256(template) != original


def test_build_prompt_contains_input_and_schema_and_contract():
    inp = _input()
    prompt = build_evidence_normalizer_prompt(inp, prompt_template="请按输入页组抽取候选。")
    assert "患者无糖尿病病史" in prompt
    assert "筛选病历" in prompt
    assert "研究者" in prompt
    data, _ = json.JSONDecoder().raw_decode(prompt.split("本次输入：", 1)[1])
    assert data["context"]["current_review_stage"] == "screening"
    assert "候选" in prompt
    assert "fact_candidates" in prompt
    assert "必须同时生成引用该事实的 event_candidate" in prompt
    assert "肯定用药或治疗事实必须同时生成" in prompt
    assert "逐条对账肯定用药事实、用药事件与药物暴露" in prompt
    assert "不得因药名相同而合并或漏掉" in prompt
    assert "不得按分析物、分项结果或单个指标" in prompt
    assert "未明示时区时，不得自行换算为 UTC" in prompt
    assert prompt.count("输出结构：") == 1
    assert any(page["effective_text"] == "患者无糖尿病病史。" for page in data["pages"])
    assert any(item["locator_id"] == "loc-1" for item in data["locators"])
    assert any(item["precision"] == "text_range" for item in data["locators"])
    assert any(item["localized_text"] == "患者无糖尿病病史。" for item in data["locators"])
    assert "input_scope_sha256" not in prompt
    assert "source_text_sha256" not in json.dumps(data)
    assert "page_artifact_id" not in prompt
    # 模板与系统合同均参与哈希
    assert evidence_normalizer_prompt_template_sha256("请按输入页组抽取候选。") != hashlib.sha256("请按输入页组抽取候选。".encode()).hexdigest()


def _r3_input():
    inp = _input()
    reviews = [
        PageReviewRecord(
            page_review_id=f"review-{lane.value}",
            page_artifact_id="page-1",
            source_document_version_id="docv-A",
            page_number=1,
            page_image_sha256=SHA,
            clause_pack_id="clause-pack:" + "b" * 32,
            clause_pack_sha256="c" * 64,
            lane=lane,
            provider="zhipu-coding-plan" if lane == PageReviewLane.MAIN_A else "cms-smk",
            model="GLM-5.3-Flash" if lane == PageReviewLane.MAIN_A else "MiniMax-M3",
            reasoning_effort="high",
            endpoint_base_url="https://independent.example/v1",
            fallback_used=False,
            prompt_version="page-review-r3/v1",
            response_sha256=("d" if lane == PageReviewLane.MAIN_A else "e") * 64,
            has_eligibility_value=True,
            facts=[],
            clause_signals=[
                ClauseEvidenceSignal(
                    clause_id="clause-1",
                    signal=EvidenceSignal.MENTIONS,
                    region=PageRegion(excerpt="患者无糖尿病病史。"),
                ),
                ClauseEvidenceSignal(clause_id="clause-no-evidence", signal=EvidenceSignal.NONE),
            ],
            handwriting=[],
        )
        for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)
    ]
    reconciliation = PageReconciliation(
        reconciliation_id="reconciliation-1",
        page_artifact_id="page-1",
        clause_pack_sha256="c" * 64,
        page_review_ids=[item.page_review_id for item in reviews],
        accepted_clause_signals=reviews[0].clause_signals,
    )
    entries = [
        PageCoverageEntry(
            page_artifact_id="page-1",
            source_document_version_id="docv-A",
            page_number=1,
            disposition=PageDisposition.ACCEPTED,
            reconciliation_id="reconciliation-1",
        ),
        PageCoverageEntry(
            page_artifact_id="page-2",
            source_document_version_id="docv-A",
            page_number=2,
            disposition=PageDisposition.DISCARDED_NO_ELIGIBILITY_VALUE,
            discard_reason="两个主读道均未发现与当前入排条款有关的内容。",
        ),
    ]
    page_review = EvidenceNormalizerPageReviewInput(
        coverage_id="coverage-1",
        clause_pack_sha256="c" * 64,
        entries=entries,
        reviews=reviews,
        reconciliations=[reconciliation],
        scope_sha256=page_review_input_scope_hash(
            coverage_id="coverage-1",
            clause_pack_sha256="c" * 64,
            entries=entries,
            reviews=reviews,
            reconciliations=[reconciliation],
        ),
    )
    input_scope = evidence_normalizer_input_scope_hash(
        authority=inp.authority,
        logical_document_id=inp.logical_document_id,
        context=inp.context,
        related_requirements=inp.related_requirements,
        manifest_sha256=inp.manifest_sha256,
        completion_manifest_sha256=inp.completion_manifest_sha256,
        page_numbers=inp.page_numbers,
        pages=inp.pages,
        page_review=page_review,
        available_locator_ids=inp.available_locator_ids,
        available_locators=inp.available_locators,
    )
    inp = inp.model_copy(
        update={"page_review": page_review, "input_scope_sha256": input_scope}
    )
    return inp


def test_r3_prompt_uses_accepted_page_review_and_ocr_as_sidecar():
    inp = _r3_input()

    prompt = build_evidence_normalizer_prompt(
        inp, prompt_template="请按输入页组抽取候选。"
    )

    assert '"ocr_sidecar_pages"' in prompt
    assert '"sidecar_transcription"' in prompt
    assert '"accepted_pages"' in prompt
    assert '"clause-no-evidence"' not in prompt
    assert '"clause-1"' in prompt
    data, _ = json.JSONDecoder().raw_decode(prompt.split("本次输入：", 1)[1])
    assert any(item["disposition"] == "discarded_no_eligibility_value"
               for item in data["page_review"]["page_dispositions"])
    assert "不得从已舍弃页面的侧车文字另造候选" in prompt


def test_compact_schema_strips_titles_but_keeps_descriptions():
    schema = json.loads(evidence_normalizer_compact_schema())

    def walk(node):
        if isinstance(node, dict):
            assert "title" not in node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    # description 承载未解决项字段语义（如 code 示例），保留给非受限路由
    assert "description" in schema["$defs"]["EvidenceNormalizerUnresolvedItem"]["properties"]["code"]


def test_prompt_can_omit_embedded_schema_for_schema_enforcing_transports():
    inp = _input()
    prompt = build_evidence_normalizer_prompt(
        inp, prompt_template="请按输入页组抽取候选。", include_output_schema=False
    )
    assert "输出结构" not in prompt
    # Schema 专属结构键（additionalProperties）只随输出结构出现；省略后提示中不应再有
    assert "additionalProperties" not in prompt
    # 输入正文与合同不受影响
    assert "患者无糖尿病病史" in prompt
    assert "不得自创 locator" in prompt


def test_prompt_layout_version_is_v24():
    from app.agents.evidence_normalizer import _PROMPT_LAYOUT_VERSION

    assert _PROMPT_LAYOUT_VERSION == "phase5/evidence-normalizer-prompt/v24"


def test_prompt_does_not_promote_page_context_to_exposure_dates():
    prompt = build_evidence_normalizer_prompt(_input(), prompt_template="抽取候选")
    assert "context.time_text 仅是页读关联" in prompt
    assert "起止范围使用未知" in prompt
    assert "不得因两个主读都填写同一关联日期" in prompt


def test_prompt_rejects_oversized_model_input_before_transport():
    inp = _input().model_copy(
        update={
            "pages": [
                _page(1, "明确临床事实" * 20_000, ["loc-1"]),
                _page(2, "收缩压 120 mmHg。", ["loc-2"]),
            ]
        }
    )
    with pytest.raises(ValueError, match="超过单次处理上限"):
        build_evidence_normalizer_prompt(inp, prompt_template="请按输入页组抽取候选。")


def test_compact_schema_is_strict_and_phase5():
    schema_str = evidence_normalizer_compact_schema()
    schema = json.loads(schema_str)
    assert "run_id" not in schema["properties"]
    assert "candidate_ref" in schema["$defs"]["EvidenceFactDraft"]["properties"]
    # Pydantic extra=forbid -> additionalProperties false at top
    assert schema.get("additionalProperties") is False or any(v.get("additionalProperties") is False for v in schema.get("$defs", {}).values())
    # 模型只输出语义草稿，系统身份在解码后补全
    assert "phase5/normalizer-draft/v3" in schema_str
    # 紧凑：无换行与多余空格
    assert "\n" not in schema_str
    assert schema_str == json.dumps(json.loads(schema_str), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_generation_schema_requires_every_declared_field_to_be_explicit():
    schema = evidence_normalizer_json_schema()
    assert set(schema["required"]) == set(schema["properties"])
    assert "actual_exposure_fact_refs" in schema["required"]
    assert "non_exposure_medication_fact_refs" in schema["required"]
    for definition in schema.get("$defs", {}).values():
        properties = definition.get("properties")
        if properties:
            assert set(definition["required"]) == set(properties)


def test_decoder_rejects_actual_exposure_fact_without_exposure_candidate():
    inp = _input()
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0].update(
        profile_lane="medication",
        polarity="affirmed",
    )
    payload["actual_exposure_fact_refs"] = ["f1"]
    payload["non_exposure_medication_fact_refs"] = []

    with pytest.raises(ValueError, match="缺少暴露=.*f1"):
        parse_evidence_normalizer_output(
            json.dumps(payload, ensure_ascii=False),
            expected_run_id=inp.run_id,
            expected_call_id=inp.call_id,
            expected_logical_document_id=inp.logical_document_id,
            expected_page_numbers=inp.page_numbers,
            locator_source_hashes={
                item.locator_id: item.source_text_sha256
                for item in inp.available_locators
            },
            created_at=inp.created_at,
        )


def test_decoder_rejects_unclassified_affirmed_medication_fact():
    inp = _input()
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0].update(
        profile_lane="medication",
        polarity="affirmed",
    )

    with pytest.raises(ValueError, match="未归类=.*f1"):
        parse_evidence_normalizer_output(
            json.dumps(payload, ensure_ascii=False),
            expected_run_id=inp.run_id,
            expected_call_id=inp.call_id,
            expected_logical_document_id=inp.logical_document_id,
            expected_page_numbers=inp.page_numbers,
            locator_source_hashes={
                item.locator_id: item.source_text_sha256
                for item in inp.available_locators
            },
            created_at=inp.created_at,
        )

def test_generation_schema_rejects_unpaired_requirement_gap_fields():
    schema = evidence_normalizer_json_schema()
    payload = {
        "schema_version": "phase5/normalizer-draft/v3",
        "actual_exposure_fact_refs": [],
        "non_exposure_medication_fact_refs": [],
        "fact_candidates": [],
        "event_candidates": [],
        "exposure_candidates": [],
        "unresolved_items": [
            {
                "code": "ambiguous_date",
                "message": "日期需要核对",
                "affected_pages": [1],
                "affected_locator_ids": ["loc-1"],
                "affected_requirement_ids": ["req-1"],
                "gap_type": None,
                "referenced_file_id": None,
                "reason": "原文未提供完整日期",
            }
        ],
    }

    errors = list(Draft202012Validator(schema).iter_errors(payload))

    assert any(error.validator == "oneOf" for error in errors)


@pytest.mark.parametrize(
    ("requirement_ids", "gap_type", "referenced_file_id"),
    [
        ([], None, None),
        (["req-1"], "record_incomplete", None),
        (["req-1"], "referenced_file_missing", "file-1"),
    ],
)
def test_generation_schema_accepts_valid_requirement_gap_combinations(
    requirement_ids, gap_type, referenced_file_id
):
    schema = evidence_normalizer_json_schema()
    payload = {
        "schema_version": "phase5/normalizer-draft/v3",
        "actual_exposure_fact_refs": [],
        "non_exposure_medication_fact_refs": [],
        "fact_candidates": [],
        "event_candidates": [],
        "exposure_candidates": [],
        "unresolved_items": [
            {
                "code": "ambiguous_date",
                "message": "日期需要核对",
                "affected_pages": [1],
                "affected_locator_ids": ["loc-1"],
                "affected_requirement_ids": requirement_ids,
                "gap_type": gap_type,
                "referenced_file_id": referenced_file_id,
                "reason": "原文未提供完整日期",
            }
        ],
    }

    Draft202012Validator(schema).validate(payload)


def test_decoder_canonicalizes_set_like_draft_arrays_before_validation():
    inp = _input([_requirement("req-history", "既往史")])
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0]["locator_ids"] = ["loc-2", "loc-1", "loc-2"]
    payload["unresolved_items"][0].update(
        {
            "affected_pages": [2, 1, 2],
            "affected_locator_ids": ["loc-2", "loc-1", "loc-2"],
            "affected_requirement_ids": [],
            "gap_type": None,
            "referenced_file_id": None,
        }
    )

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    assert output.fact_candidates[0].locator_ids == ["loc-1", "loc-2"]
    assert output.unresolved_items[0].affected_pages == [1, 2]
    assert output.unresolved_items[0].affected_locator_ids == ["loc-1", "loc-2"]


def test_decoder_restores_only_the_omitted_system_locator_prefix():
    inp = _input([_requirement("req-history", "既往史")])
    locator_id = "locator-" + "8" * 40
    source_hash = "b" * 64
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0]["locator_ids"] = [locator_id.removeprefix("locator-")]
    payload["fact_candidates"][0]["assertion_basis"]["locator_id"] = locator_id.removeprefix("locator-")

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids={locator_id},
        locator_source_hashes={locator_id: source_hash},
        created_at=inp.created_at,
    )

    fact = output.fact_candidates[0]
    assert fact.locator_ids == [locator_id]
    assert fact.assertion_basis is not None
    assert fact.assertion_basis.locator_id == locator_id
    assert fact.assertion_basis.source_text_sha256 == source_hash


def test_decoder_does_not_guess_an_unknown_locator():
    inp = _input([_requirement("req-history", "既往史")])
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0]["locator_ids"] = ["unknown"]
    payload["fact_candidates"][0]["assertion_basis"]["locator_id"] = "unknown"

    with pytest.raises(ValueError, match="断言依据定位不在系统冻结的定位摘要中"):
        parse_evidence_normalizer_output(
            json.dumps(payload, ensure_ascii=False),
            expected_run_id=inp.run_id,
            expected_call_id=inp.call_id,
            expected_logical_document_id=inp.logical_document_id,
            expected_page_numbers=inp.page_numbers,
            available_locator_ids={"locator-known"},
            locator_source_hashes={"locator-known": "b" * 64},
            created_at=inp.created_at,
        )


def test_decoder_hydrates_model_draft_with_system_identity_and_locator_hash():
    inp = _input()
    payload = {
        "schema_version": "phase5/normalizer-draft/v3",
        "actual_exposure_fact_refs": [],
        "non_exposure_medication_fact_refs": [],
        "fact_candidates": [
            {
                "candidate_ref": "f1",
                "fact_type": "既往史",
                "profile_lane": "medical_history",
                "polarity": "negated",
                "asserted_object": "糖尿病病史",
                "raw_value": False,
                "canonical_value": False,
                "unit": None,
                "date_range": None,
                "record_time": None,
                "locator_ids": ["loc-1"],
                "candidate_source_semantics": "当前研究病历直接记录",
                "assertion_basis": {
                    "asserted_object": "糖尿病病史",
                    "assertion_text": "患者无糖尿病病史",
                    "locator_id": "loc-1",
                },
                "model_uncertainty": 0.05,
            }
        ],
        "event_candidates": [],
        "exposure_candidates": [],
        "unresolved_items": [],
    }
    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )
    fact = output.fact_candidates[0]
    assert fact.run_id == inp.run_id
    assert fact.call_id == inp.call_id
    assert fact.created_at == inp.created_at
    assert fact.assertion_basis is not None
    assert fact.assertion_basis.source_text_sha256 == inp.available_locators[0].source_text_sha256
    assert fact.supported_requirement_ids == []


def test_decoder_keeps_unknown_direction_and_discards_contradictory_assertion_details():
    inp = _input()
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0].update(
        {
            "polarity": "unknown",
            "raw_value": False,
            "canonical_value": False,
            "unit": "unitless",
        }
    )

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    normalized = output.fact_candidates[0]
    assert normalized.polarity.value == "unknown"
    assert normalized.raw_value is None
    assert normalized.canonical_value is None
    assert normalized.unit is None
    assert normalized.assertion_basis is None


def test_decoder_reports_all_non_verbatim_asserted_objects_at_once():
    inp = _input()
    payload = {
        "schema_version": "phase5/normalizer-draft/v3",
        "actual_exposure_fact_refs": [],
        "non_exposure_medication_fact_refs": [],
        "fact_candidates": [],
        "event_candidates": [],
        "exposure_candidates": [],
        "unresolved_items": [],
    }
    for index, asserted_object in enumerate(("家族遗传病病史", "医疗器械临床试验参加史"), start=1):
        payload["fact_candidates"].append(
            {
                "candidate_ref": f"f{index}",
                "fact_type": "既往史",
                "profile_lane": "medical_history",
                "polarity": "negated",
                "asserted_object": asserted_object,
                "raw_value": False,
                "canonical_value": False,
                "unit": None,
                "date_range": None,
                "record_time": None,
                "locator_ids": ["loc-1"],
                "candidate_source_semantics": "当前研究病历直接记录",
                "assertion_basis": {
                    "asserted_object": asserted_object,
                    "assertion_text": "患者否认相关既往史。",
                    "locator_id": "loc-1",
                },
                "model_uncertainty": 0.05,
            }
        )

    with pytest.raises(ValueError) as exc_info:
        parse_evidence_normalizer_output(
            json.dumps(payload, ensure_ascii=False),
            expected_run_id=inp.run_id,
            expected_call_id=inp.call_id,
            expected_logical_document_id=inp.logical_document_id,
            expected_page_numbers=inp.page_numbers,
            available_locator_ids=set(inp.available_locator_ids),
            locator_source_hashes={
                item.locator_id: item.source_text_sha256
                for item in inp.available_locators
            },
            created_at=inp.created_at,
        )

    message = str(exc_info.value)
    assert "家族遗传病病史" in message
    assert "医疗器械临床试验参加史" in message


# ------------------------------------------------- 断言对象机械逐字还原（Phase 5）

def test_mechanical_verbatim_repair_trims_added_suffix_only_when_unique():
    from app.agents.evidence_normalizer import _mechanical_verbatim_repair

    # 模型给对象添加了原句该处没有的 2 字类别后缀 → 去后缀还原
    assert (
        _mechanical_verbatim_repair("糠酸莫米松鼻喷剂使用", "既往规律使用糠酸莫米松鼻喷剂。")
        == "糠酸莫米松鼻喷剂"
    )
    # 逐字对象不做任何修改
    assert _mechanical_verbatim_repair("糖尿病病史", "患者无糖尿病病史") is None
    # 短于最短修复长度的对象不做机械修复
    assert _mechanical_verbatim_repair("肝大", "肝肿大，脾未及") is None
    # 原句不存在任何逐字片段且无唯一补虚词窗口 → 保持 None
    assert _mechanical_verbatim_repair("甲状腺功能异常", "患者无不适主诉。") is None


def test_mechanical_verbatim_repair_completes_dropped_particle():
    from app.agents.evidence_normalizer import _mechanical_verbatim_repair

    # 漏抄“等”→ 唯一最短连续窗口补齐
    assert _mechanical_verbatim_repair("眼部疾病", "既往无眼部等疾病。") == "眼部等疾病"
    # 漏抄“有”→ 唯一最短连续窗口补齐
    assert (
        _mechanical_verbatim_repair("3个月内大量饮酒", "3个月内有大量饮酒。")
        == "3个月内有大量饮酒"
    )


def test_mechanical_verbatim_repair_fails_closed_on_ambiguity():
    from app.agents.evidence_normalizer import _mechanical_verbatim_repair

    # 两个等长去尾/去头截取并存（甲状腺结节 / 结节病史）→ 歧义返回 None
    assert (
        _mechanical_verbatim_repair("甲状腺结节病史", "甲状腺结节，乳腺结节病史待核。")
        is None
    )
    # 两个等长补虚词窗口并存（有饮酒史 / 无饮酒史）→ 歧义返回 None
    assert _mechanical_verbatim_repair("饮酒史", "有饮酒史，无饮酒史记录。") is None


def test_decoder_repairs_negation_separated_asserted_object_from_page4_failure_shape():
    """回归（31001 第4页）：对象被否定虚词隔开时逐字门禁不再整页失败。

    模型把“家族无遗传病病史”顺口化为“家族遗传病病史”，解码器必须机械还原为
    逐字片段“遗传病病史”，并保持顶层与断言依据两处对象一致。
    """
    inp = _input()
    payload = {
        "schema_version": "phase5/normalizer-draft/v3",
        "actual_exposure_fact_refs": [],
        "non_exposure_medication_fact_refs": [],
        "fact_candidates": [
            {
                "candidate_ref": "f1",
                "fact_type": "家族遗传病病史",
                "profile_lane": "medical_history",
                "polarity": "negated",
                "asserted_object": "家族遗传病病史",
                "raw_value": False,
                "canonical_value": False,
                "unit": None,
                "date_range": None,
                "record_time": None,
                "locator_ids": ["loc-1"],
                "candidate_source_semantics": "当前研究病历直接记录",
                "assertion_basis": {
                    "asserted_object": "家族遗传病病史",
                    "assertion_text": "家族史：父母体健，家族无遗传病病史。",
                    "locator_id": "loc-1",
                },
                "model_uncertainty": 0.05,
            }
        ],
        "event_candidates": [],
        "exposure_candidates": [],
        "unresolved_items": [
            {
                "code": "page_closed",
                "message": "第 2 页无其他候选",
                "affected_pages": [2],
                "affected_locator_ids": [],
                "reason": "已逐页核对",
            }
        ],
    }

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    fact = output.fact_candidates[0]
    assert fact.asserted_object == "遗传病病史"
    assert fact.assertion_basis is not None
    assert fact.assertion_basis.asserted_object == "遗传病病史"


def test_decoder_repairs_suffix_added_asserted_object_end_to_end():
    inp = _input()
    payload = {
        "schema_version": "phase5/normalizer-draft/v3",
        "actual_exposure_fact_refs": ["f1"],
        "non_exposure_medication_fact_refs": [],
        "fact_candidates": [
            {
                "candidate_ref": "f1",
                "fact_type": "既往用药",
                "profile_lane": "medication",
                "polarity": "affirmed",
                "asserted_object": "糠酸莫米松鼻喷剂使用",
                "raw_value": True,
                "canonical_value": True,
                "unit": None,
                "date_range": None,
                "record_time": None,
                "locator_ids": ["loc-1"],
                "candidate_source_semantics": "筛选病历转述",
                "assertion_basis": {
                    "asserted_object": "糠酸莫米松鼻喷剂使用",
                    "assertion_text": "既往规律使用糠酸莫米松鼻喷剂。",
                    "locator_id": "loc-1",
                },
                "model_uncertainty": 0.05,
            }
        ],
        "event_candidates": [],
        "exposure_candidates": [
            {
                "candidate_ref": "x1",
                "medication_name": "糠酸莫米松鼻喷剂",
                "category": None,
                "indication": None,
                "dose": None,
                "unit": None,
                "frequency": None,
                "route": None,
                "start_range": None,
                "end_range": None,
                "duration_status": "unknown",
                "record_time": None,
                "fact_candidate_refs": ["f1"],
                "locator_ids": ["loc-1"],
                "candidate_source_semantics": "筛选病历转述",
                "model_uncertainty": 0.05,
            }
        ],
        "unresolved_items": [
            {
                "code": "page_closed",
                "message": "第 2 页无其他候选",
                "affected_pages": [2],
                "affected_locator_ids": [],
                "reason": "已逐页核对",
            }
        ],
    }

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    fact = output.fact_candidates[0]
    assert fact.asserted_object == "糠酸莫米松鼻喷剂"
    assert fact.assertion_basis is not None
    assert fact.assertion_basis.asserted_object == "糠酸莫米松鼻喷剂"


def test_decoder_still_rejects_ambiguous_asserted_objects_without_repair():
    """歧义对象不做机械修复，逐字门禁保持 fail-closed。"""
    inp = _input()
    payload = {
        "schema_version": "phase5/normalizer-draft/v3",
        "actual_exposure_fact_refs": [],
        "non_exposure_medication_fact_refs": [],
        "fact_candidates": [
            {
                "candidate_ref": "f1",
                "fact_type": "既往史",
                "profile_lane": "medical_history",
                "polarity": "negated",
                "asserted_object": "甲状腺结节病史",
                "raw_value": False,
                "canonical_value": False,
                "unit": None,
                "date_range": None,
                "record_time": None,
                "locator_ids": ["loc-1"],
                "candidate_source_semantics": "当前研究病历直接记录",
                "assertion_basis": {
                    "asserted_object": "甲状腺结节病史",
                    "assertion_text": "甲状腺结节，乳腺结节病史待核。",
                    "locator_id": "loc-1",
                },
                "model_uncertainty": 0.05,
            }
        ],
        "event_candidates": [],
        "exposure_candidates": [],
        "unresolved_items": [],
    }

    with pytest.raises(ValueError, match="甲状腺结节病史"):
        parse_evidence_normalizer_output(
            json.dumps(payload, ensure_ascii=False),
            expected_run_id=inp.run_id,
            expected_call_id=inp.call_id,
            expected_logical_document_id=inp.logical_document_id,
            expected_page_numbers=inp.page_numbers,
            available_locator_ids=set(inp.available_locator_ids),
            locator_source_hashes={
                item.locator_id: item.source_text_sha256
                for item in inp.available_locators
            },
            created_at=inp.created_at,
        )


def _requirement(requirement_id: str, fact_type: str) -> EvidenceRequirement:
    return EvidenceRequirement(
        requirement_id=requirement_id,
        procedure_catalog_item_id=f"procedure-{requirement_id}",
        fact_type=fact_type,
        due_stage=ReviewStage.SCREENING,
        description=f"核对 {fact_type}",
    )


def _bound_draft_payload(requirement_id: str) -> dict:
    return {
        "schema_version": "phase5/normalizer-draft/v3",
        "actual_exposure_fact_refs": [],
        "non_exposure_medication_fact_refs": [],
        "fact_candidates": [
            {
                "candidate_ref": "f1",
                "fact_type": "既往史",
                "profile_lane": "medical_history",
                "supported_requirement_ids": [requirement_id],
                "polarity": "negated",
                "asserted_object": "糖尿病病史",
                "raw_value": False,
                "canonical_value": False,
                "unit": None,
                "date_range": None,
                "record_time": None,
                "locator_ids": ["loc-1"],
                "candidate_source_semantics": "当前研究病历直接记录",
                "assertion_basis": {
                    "asserted_object": "糖尿病病史",
                    "assertion_text": "患者无糖尿病病史",
                    "locator_id": "loc-1",
                },
                "model_uncertainty": 0.05,
            }
        ],
        "event_candidates": [],
        "exposure_candidates": [],
        "unresolved_items": [
            {
                "code": "page_closed",
                "message": "第 2 页无其他候选",
                "affected_pages": [2],
                "affected_locator_ids": [],
                "reason": "已逐页核对",
            }
        ],
    }


def test_requirement_binding_hydrates_and_validates_against_frozen_input():
    requirement = _requirement("req-history", "既往史")
    inp = _input([requirement])
    output = parse_evidence_normalizer_output(
        json.dumps(_bound_draft_payload(requirement.requirement_id), ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )
    validated = validate_evidence_normalizer_output(output, inp)
    assert validated.fact_candidates[0].supported_requirement_ids == ["req-history"]


def test_decoder_rejects_model_draft_without_explicit_profile_lane():
    inp = _input()
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0].pop("profile_lane")

    with pytest.raises(ValueError, match="profile_lane"):
        parse_evidence_normalizer_output(
            json.dumps(payload, ensure_ascii=False),
            expected_run_id=inp.run_id,
            expected_call_id=inp.call_id,
            expected_logical_document_id=inp.logical_document_id,
            expected_page_numbers=inp.page_numbers,
            available_locator_ids=set(inp.available_locator_ids),
            locator_source_hashes={
                item.locator_id: item.source_text_sha256
                for item in inp.available_locators
            },
            created_at=inp.created_at,
        )


def test_requirement_binding_rejects_unknown_id():
    requirement = _requirement("req-history", "既往史")
    inp = _input([requirement])
    output = parse_evidence_normalizer_output(
        json.dumps(_bound_draft_payload("req-unknown"), ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )
    with pytest.raises(ValueError, match="不存在的资料要求"):
        validate_evidence_normalizer_output(output, inp)


def test_requirement_binding_is_independent_from_display_fact_type():
    requirement = _requirement("req-lab", "检验")
    inp = _input([requirement])
    output = parse_evidence_normalizer_output(
        json.dumps(_bound_draft_payload(requirement.requirement_id), ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    validated = validate_evidence_normalizer_output(output, inp)

    assert len(validated.fact_candidates) == 1
    assert validated.fact_candidates[0].supported_requirement_ids == ["req-lab"]
    assert output.fact_candidates[0].supported_requirement_ids == ["req-lab"]


def test_decoder_losslessly_uses_raw_scalar_when_repair_omits_canonical_value():
    inp = _input()
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0]["supported_requirement_ids"] = []
    payload["fact_candidates"][0]["raw_value"] = "否认糖尿病病史"
    payload["fact_candidates"][0]["canonical_value"] = None

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    assert output.fact_candidates[0].canonical_value == "否认糖尿病病史"


@pytest.mark.parametrize(
    ("model_value", "expected"),
    [
        ("84", 84),
        ("30.5", 30.5),
        ("－1.2e2", -120.0),
        ("1.58↓", 1.58),
        ("39.0↑", 39.0),
    ],
)
def test_decoder_restores_plain_numeric_string_with_unit(model_value, expected):
    inp = _input()
    payload = _bound_draft_payload("req-lab")
    fact = payload["fact_candidates"][0]
    fact.update(
        supported_requirement_ids=[],
        polarity="affirmed",
        asserted_object="血红蛋白",
        raw_value=model_value,
        canonical_value=model_value,
        unit="g/L",
        locator_ids=["loc-2"],
        candidate_source_semantics="同期客观结果",
        assertion_basis={
            "asserted_object": "血红蛋白",
            "assertion_text": "血红蛋白 120 g/L",
            "locator_id": "loc-2",
        },
    )

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    assert output.fact_candidates[0].canonical_value == expected
    assert output.fact_candidates[0].raw_value == model_value


@pytest.mark.parametrize(
    ("asserted_object", "model_value", "unit", "expected"),
    [
        ("QT/QTc", "QT/QTc : 346/413ms", "ms", "346/413"),
        ("RV5/SV1", "RV5/SV1 : 0.736/0.561mV", "mV", "0.736/0.561"),
        ("P/QRS/T", "P/QRS/T : 46/-4/34deg", "deg", "46/-4/34"),
    ],
)
def test_decoder_normalizes_compact_measurement_label_and_repeated_unit(
    asserted_object, model_value, unit, expected
):
    inp = _input()
    payload = _bound_draft_payload("req-lab")
    fact = payload["fact_candidates"][0]
    fact.update(
        supported_requirement_ids=[],
        polarity="affirmed",
        asserted_object=asserted_object,
        raw_value=model_value,
        canonical_value=model_value,
        unit=unit,
        locator_ids=["loc-2"],
        candidate_source_semantics="同期客观结果",
        assertion_basis={
            "asserted_object": asserted_object,
            "assertion_text": model_value,
            "locator_id": "loc-2",
        },
    )

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    candidate = output.fact_candidates[0]
    assert candidate.canonical_value == expected
    assert candidate.raw_value == model_value
    assert candidate.unit == unit


@pytest.mark.parametrize("identifier", ["00004721", "004", "84721", "A-0003"])
def test_decoder_preserves_explicit_identifier(identifier):
    inp = _input()
    payload = _bound_draft_payload("req-lab")
    payload["fact_candidates"][0].update(
        value_kind="identifier", supported_requirement_ids=[], polarity="affirmed",
        asserted_object="标识", raw_value=identifier, canonical_value=identifier,
        unit=None, locator_ids=["loc-2"],
        assertion_basis={"asserted_object": "标识", "assertion_text": "标识 " + identifier,
                         "locator_id": "loc-2"},
    )
    result = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False), expected_run_id=inp.run_id,
        expected_call_id=inp.call_id, expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers, available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={x.locator_id: x.source_text_sha256 for x in inp.available_locators},
        created_at=inp.created_at,
    )
    assert result.fact_candidates[0].canonical_value == identifier
    assert result.fact_candidates[0].unit is None
    from app.domain.contracts.facts import ClinicalFactCandidateV2
    candidate = result.fact_candidates[0]
    assert ClinicalFactCandidateV2.model_validate_json(candidate.model_dump_json()).value_kind == "identifier"


@pytest.mark.parametrize("updates", [
    {"canonical_value": "47"}, {"raw_value": 47, "canonical_value": 47},
    {"unit": "unitless"}, {"assertion_basis": None},
])
def test_identifier_does_not_allow_value_rewriting_or_missing_source(updates):
    from app.agents.evidence_normalizer import EvidenceFactDraft
    payload = _bound_draft_payload("req-lab")["fact_candidates"][0]
    payload.update(value_kind="identifier", raw_value="0047", canonical_value="0047", unit=None,
                   assertion_basis={"asserted_object": "标识", "assertion_text": "标识 0047", "locator_id": "loc-2"})
    payload.update(updates)
    with pytest.raises(ValueError, match="标识编号"):
        EvidenceFactDraft.model_validate(payload)


def test_decoder_does_not_let_numeric_string_without_unit_bypass_numeric_gate():
    inp = _input()
    payload = _bound_draft_payload("req-lab")
    fact = payload["fact_candidates"][0]
    fact.update(
        supported_requirement_ids=[],
        polarity="affirmed",
        asserted_object="心率",
        raw_value="85",
        canonical_value="85",
        unit=None,
        locator_ids=["loc-2"],
        candidate_source_semantics="同期客观结果",
        assertion_basis={
            "asserted_object": "心率",
            "assertion_text": "心率 85",
            "locator_id": "loc-2",
        },
    )

    with pytest.raises(ValueError, match="数值候选必须声明单位") as exc_info:
        parse_evidence_normalizer_output(
            json.dumps(payload, ensure_ascii=False),
            expected_run_id=inp.run_id,
            expected_call_id=inp.call_id,
            expected_logical_document_id=inp.logical_document_id,
            expected_page_numbers=inp.page_numbers,
            available_locator_ids=set(inp.available_locator_ids),
            locator_source_hashes={
                item.locator_id: item.source_text_sha256
                for item in inp.available_locators
            },
            created_at=inp.created_at,
        )
    assert fact["candidate_ref"] in str(exc_info.value)
    assert fact["asserted_object"] in str(exc_info.value)


def test_decoder_restores_percent_unit_from_explicit_percentage_object():
    inp = _input()
    payload = _bound_draft_payload("req-lab")
    fact = payload["fact_candidates"][0]
    fact.update(
        supported_requirement_ids=[],
        polarity="affirmed",
        asserted_object="有核红细胞百分比",
        raw_value="0.00",
        canonical_value=0.0,
        unit=None,
        locator_ids=["loc-2"],
        candidate_source_semantics="同期客观结果",
        assertion_basis={
            "asserted_object": "有核红细胞百分比",
            "assertion_text": "NRBC有核红细胞百分比 0.00",
            "locator_id": "loc-2",
        },
    )

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    candidate = output.fact_candidates[0]
    assert candidate.raw_value == "0.00"
    assert candidate.canonical_value == 0.0
    assert candidate.unit == "%"


def test_decoder_preserves_raw_lab_annotation_and_normalizes_numeric_value():
    inp = _input()
    payload = _bound_draft_payload("req-lab")
    fact = payload["fact_candidates"][0]
    fact.update(
        supported_requirement_ids=[],
        polarity="affirmed",
        asserted_object="直接胆红素",
        raw_value="8.7 (高于参考范围1.7--6.8 μmol/L)",
        canonical_value="8.7 (高于参考范围1.7--6.8 μmol/L)",
        unit="μmol/L",
        locator_ids=["loc-2"],
        candidate_source_semantics="同期客观结果",
        assertion_basis={
            "asserted_object": "直接胆红素",
            "assertion_text": "直接胆红素 8.7 (高于参考范围1.7--6.8 μmol/L)",
            "locator_id": "loc-2",
        },
    )

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    candidate = output.fact_candidates[0]
    assert candidate.raw_value == "8.7 (高于参考范围1.7--6.8 μmol/L)"
    assert candidate.canonical_value == 8.7
    assert candidate.unit == "μmol/L"


def test_decoder_restores_explicit_suffix_unit_from_compact_measurement():
    inp = _input()
    payload = _bound_draft_payload("req-lab")
    fact = payload["fact_candidates"][0]
    fact.update(
        supported_requirement_ids=[],
        polarity="affirmed",
        asserted_object="P/QRS/T",
        raw_value="46/-4/34deg",
        canonical_value="46/-4/34deg",
        unit="unitless",
        locator_ids=["loc-2"],
        candidate_source_semantics="同期客观结果",
        assertion_basis={
            "asserted_object": "P/QRS/T",
            "assertion_text": "P/QRS/T 46/-4/34deg",
            "locator_id": "loc-2",
        },
    )

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    candidate = output.fact_candidates[0]
    assert candidate.raw_value == "46/-4/34deg"
    assert candidate.canonical_value == "46/-4/34"
    assert candidate.unit == "deg"


@pytest.mark.parametrize(
    ("dose", "unit", "expected"),
    [("300mg", "mg", "300"), ("0.86g", "g", "0.86"), ("适量", None, "适量")],
)
def test_decoder_removes_only_exact_repeated_unit_from_exposure_dose(
    dose, unit, expected
):
    inp = _input()
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0].update(
        supported_requirement_ids=[],
        profile_lane="medication",
        polarity="affirmed",
        asserted_object="阿司匹林",
        raw_value=True,
        canonical_value=True,
        unit=None,
        assertion_basis={
            "asserted_object": "阿司匹林",
            "assertion_text": "患者已使用阿司匹林 300 mg 口服。",
            "locator_id": "loc-1",
        },
    )
    payload["actual_exposure_fact_refs"] = ["f1"]
    payload["non_exposure_medication_fact_refs"] = []
    payload["exposure_candidates"] = [
        {
            "candidate_ref": "x1",
            "medication_name": "阿司匹林",
            "category": None,
            "indication": None,
            "dose": dose,
            "unit": unit,
            "frequency": None,
            "route": "口服",
            "start_range": None,
            "end_range": None,
            "duration_status": "unknown",
            "record_time": None,
            "fact_candidate_refs": ["f1"],
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "当前研究病历直接记录",
            "model_uncertainty": 0.05,
        }
    ]
    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    assert output.exposure_candidates[0].dose == expected


@pytest.mark.parametrize(
    ("duration_status", "end_range"),
    [
        (
            "ongoing",
            {
                "source_text": "2025-08-08",
                "precision": "day",
                "lower_bound": "2025-08-08",
                "upper_bound": "2025-08-08",
            },
        ),
        ("ended", None),
    ],
)
def test_decoder_demotes_conflicting_exposure_duration_and_preserves_trace(
    duration_status, end_range
):
    inp = _input()
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0].update(
        supported_requirement_ids=[],
        profile_lane="medication",
        polarity="affirmed",
        asserted_object="阿司匹林",
        raw_value=True,
        canonical_value=True,
        unit=None,
        assertion_basis={
            "asserted_object": "阿司匹林",
            "assertion_text": "患者已使用阿司匹林。",
            "locator_id": "loc-1",
        },
    )
    payload["actual_exposure_fact_refs"] = ["f1"]
    payload["non_exposure_medication_fact_refs"] = []
    payload["exposure_candidates"] = [
        {
            "candidate_ref": "x1",
            "medication_name": "阿司匹林",
            "duration_status": duration_status,
            "end_range": end_range,
            "fact_candidate_refs": ["f1"],
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "当前研究病历直接记录",
            "model_uncertainty": 0.05,
        }
    ]

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    assert output.exposure_candidates[0].duration_status.value == "unknown"
    if end_range is None:
        assert output.exposure_candidates[0].end_range is None
    else:
        assert output.exposure_candidates[0].end_range.source_text == "2025-08-08"
    issue = output.unresolved_items[-1]
    assert issue.code == "duration_status_unclear"
    assert issue.affected_pages == [1, 2]
    assert issue.affected_locator_ids == ["loc-1"]


def test_decoder_demotes_inconsistent_day_range_without_choosing_a_boundary():
    inp = _input()
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0]["date_range"] = {
        "source_text": "2025年8月",
        "precision": "day",
        "lower_bound": "2025-08-01",
        "upper_bound": "2025-08-31",
    }

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    date_range = output.fact_candidates[0].date_range
    assert date_range is not None
    assert date_range.precision.value == "unknown"
    assert date_range.lower_bound is date_range.upper_bound is None
    assert date_range.source_text == "2025年8月"
    assert output.unresolved_items[-1].code == "date_range_unclear"


def test_decoder_does_not_coerce_compound_or_comparison_value_with_unit():
    inp = _input()
    payload = _bound_draft_payload("req-lab")
    fact = payload["fact_candidates"][0]
    fact.update(
        supported_requirement_ids=[],
        polarity="affirmed",
        raw_value="QT 346 ms；QTc 413 ms",
        canonical_value="QT 346 ms；QTc 413 ms",
        unit="ms",
    )

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    assert output.fact_candidates[0].canonical_value == "QT 346 ms；QTc 413 ms"


@pytest.mark.parametrize(
    ("profile_lane", "value"),
    [
        ("test_exam_score", "未检测到靶基因"),
        ("medication", "某药 300mg 皮下注射一次"),
    ],
)
def test_decoder_clears_unit_from_textual_fact_values(profile_lane, value):
    inp = _input()
    payload = _bound_draft_payload("req-lab")
    fact = payload["fact_candidates"][0]
    fact.update(
        supported_requirement_ids=[],
        profile_lane=profile_lane,
        polarity="affirmed",
        raw_value=value,
        canonical_value=value,
        unit="mg",
    )
    if profile_lane == "medication":
        payload["actual_exposure_fact_refs"] = []
        payload["non_exposure_medication_fact_refs"] = ["f1"]

    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    assert output.fact_candidates[0].unit is None


def test_chart_source_alignment_only_downgrades_impossible_elevated_label():
    inp = _input()
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0]["supported_requirement_ids"] = []
    payload["fact_candidates"][0]["candidate_source_semantics"] = "既往原始资料"
    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    validated = validate_evidence_normalizer_output(output, inp)

    assert validated.fact_candidates[0].candidate_source_semantics == "筛选病历转述"


@pytest.mark.parametrize(
    ("document_type", "source_party", "declared", "expected"),
    [
        ("实验室检验结果", "研究中心", "当前研究病历直接记录", "同期客观结果"),
        ("入组审核邮件", "研究中心", "同期客观结果", "无法确认来源"),
        ("既往病历", "外部医院", "筛选病历转述", "既往原始资料"),
    ],
)
def test_non_chart_source_alignment_uses_frozen_document_metadata(
    document_type, source_party, declared, expected
):
    inp = _input(document_type=document_type, source_party=source_party)
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0]["supported_requirement_ids"] = []
    payload["fact_candidates"][0]["candidate_source_semantics"] = declared
    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )

    validated = validate_evidence_normalizer_output(output, inp)

    assert validated.fact_candidates[0].candidate_source_semantics == expected


def test_draft_rejects_event_locator_not_covered_by_linked_facts():
    inp = _input()
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0]["supported_requirement_ids"] = []
    payload["event_candidates"] = [
        {
            "candidate_ref": "e1",
            "event_type": "病史事件",
            "profile_lane": "medical_history",
            "start_range": None,
            "end_range": None,
            "duration_status": "unknown",
            "record_time": None,
            "fact_candidate_refs": ["f1"],
            "locator_ids": ["loc-2"],
            "candidate_source_semantics": "当前研究病历直接记录",
            "model_uncertainty": 0.05,
        }
    ]

    with pytest.raises(ValueError, match="定位未被关联事实覆盖"):
        parse_evidence_normalizer_output(
            json.dumps(payload, ensure_ascii=False),
            expected_run_id=inp.run_id,
            expected_call_id=inp.call_id,
            expected_logical_document_id=inp.logical_document_id,
            expected_page_numbers=inp.page_numbers,
            available_locator_ids=set(inp.available_locator_ids),
            locator_source_hashes={
                item.locator_id: item.source_text_sha256
                for item in inp.available_locators
            },
            created_at=inp.created_at,
        )


def test_unresolved_gap_binding_requires_a_frozen_requirement():
    requirement = _requirement("req-history", "既往史")
    inp = _input([requirement])
    payload = _bound_draft_payload(requirement.requirement_id)
    payload["unresolved_items"][0].update(
        affected_requirement_ids=[requirement.requirement_id],
        gap_type="record_incomplete",
    )
    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id=inp.run_id,
        expected_call_id=inp.call_id,
        expected_logical_document_id=inp.logical_document_id,
        expected_page_numbers=inp.page_numbers,
        available_locator_ids=set(inp.available_locator_ids),
        locator_source_hashes={
            item.locator_id: item.source_text_sha256
            for item in inp.available_locators
        },
        created_at=inp.created_at,
    )
    validated = validate_evidence_normalizer_output(output, inp)
    assert validated.unresolved_items[0].affected_requirement_ids == ["req-history"]

    invalid = output.model_copy(deep=True)
    invalid.unresolved_items[0].affected_requirement_ids = ["req-other"]
    with pytest.raises(ValueError, match="不存在的资料要求"):
        validate_evidence_normalizer_output(invalid, inp)


# ------------------------------------------------------------- 解码器

def test_decoder_accepts_valid_minimal_output():
    out_json = json.dumps(_valid_output_dict(), ensure_ascii=False)
    out = parse_evidence_normalizer_output(
        out_json, expected_run_id="run-1", expected_call_id="call-1",
        expected_logical_document_id="doc-A", expected_page_numbers=[1, 2],
        available_locator_ids={"loc-1", "loc-2"},
    )
    assert out.run_id == "run-1"
    assert len(out.unresolved_items) == 1


def test_decoder_rejects_empty_string():
    with pytest.raises(ValueError, match="空输出"):
        parse_evidence_normalizer_output("   ", expected_run_id="run-1")


def test_decoder_rejects_markdown_wrapper():
    out_json = json.dumps(_valid_output_dict(), ensure_ascii=False)
    with pytest.raises(ValueError, match="Markdown"):
        parse_evidence_normalizer_output(f"```json\n{out_json}\n```", expected_run_id="run-1")


def test_decoder_rejects_invalid_json():
    with pytest.raises(ValueError, match="合法 JSON"):
        parse_evidence_normalizer_output("{not json}", expected_run_id="run-1")


def test_decoder_rejects_top_level_not_object():
    with pytest.raises(ValueError, match="JSON 对象"):
        parse_evidence_normalizer_output("[]", expected_run_id="run-1")


def test_decoder_rejects_forbidden_top_level_fields():
    payload = {**_valid_output_dict(), "accepted_facts": []}
    with pytest.raises(ValueError, match="禁止字段"):
        parse_evidence_normalizer_output(json.dumps(payload, ensure_ascii=False), expected_run_id="run-1")
    payload2 = {**_valid_output_dict(), "profile": {}}
    with pytest.raises(ValueError, match="禁止字段"):
        parse_evidence_normalizer_output(json.dumps(payload2, ensure_ascii=False), expected_run_id="run-1")
    payload3 = {**_valid_output_dict(), "gate_results": []}
    with pytest.raises(ValueError, match="禁止字段"):
        parse_evidence_normalizer_output(json.dumps(payload3, ensure_ascii=False), expected_run_id="run-1")


def test_decoder_rejects_mismatched_run_call():
    out_json = json.dumps(_valid_output_dict(), ensure_ascii=False)
    with pytest.raises(ValueError, match="run_id"):
        parse_evidence_normalizer_output(out_json, expected_run_id="run-9")
    with pytest.raises(ValueError, match="call_id"):
        parse_evidence_normalizer_output(out_json, expected_run_id="run-1", expected_call_id="call-9")
    with pytest.raises(ValueError, match="logical_document_id"):
        parse_evidence_normalizer_output(out_json, expected_run_id="run-1", expected_call_id="call-1", expected_logical_document_id="doc-9")
    with pytest.raises(ValueError, match="页清单与输入不一致"):
        parse_evidence_normalizer_output(out_json, expected_run_id="run-1", expected_call_id="call-1", expected_page_numbers=[1])


def test_decoder_rejects_unknown_locator():
    payload = _valid_output_dict()
    payload["fact_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-f1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "fact",
            "fact_type": "既往史",
            "polarity": "negated",
            "asserted_object": "糖尿病病史",
            "raw_value": False,
            "canonical_value": False,
            "unit": "unitless",
            "locator_ids": ["loc-99"],
            "candidate_source_semantics": "当前研究病历直接记录",
            "assertion_basis": {"asserted_object": "糖尿病病史", "assertion_text": "无糖尿病病史", "locator_id": "loc-99", "source_text_sha256": SHA},
            "model_uncertainty": 0.1,
            "created_at": NOW.isoformat(),
        }
    ]
    with pytest.raises(ValueError, match="输入未提供的 locator"):
        parse_evidence_normalizer_output(json.dumps(payload, ensure_ascii=False), expected_run_id="run-1", expected_call_id="call-1", available_locator_ids={"loc-1", "loc-2"})


def test_decoder_rejects_unresolved_without_available_locator():
    payload = _valid_output_dict()
    payload["unresolved_items"] = [
        {"code": "ambiguous", "message": "模糊", "affected_pages": [], "affected_locator_ids": ["loc-99"], "reason": "原因"},
    ]
    # unresolved 的 affected_locator_ids 也需在可用集合内
    with pytest.raises(ValueError, match="输入未提供的 locator"):
        parse_evidence_normalizer_output(json.dumps(payload, ensure_ascii=False), expected_run_id="run-1", available_locator_ids={"loc-1"})


def test_decoder_rejects_candidate_source_semantics_not_in_allowlist():
    payload = _valid_output_dict()
    payload["fact_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-f1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "fact",
            "fact_type": "既往史",
            "polarity": "affirmed",
            "asserted_object": "高血压病史",
            "raw_value": "有",
            "canonical_value": "有",
            "unit": "unitless",
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "unknown_source",
            "assertion_basis": {"asserted_object": "高血压病史", "assertion_text": "有高血压病史", "locator_id": "loc-1", "source_text_sha256": SHA},
            "model_uncertainty": 0.1,
            "created_at": NOW.isoformat(),
        }
    ]
    with pytest.raises(ValueError, match="来源语义不在白名单"):
        parse_evidence_normalizer_output(json.dumps(payload, ensure_ascii=False), expected_run_id="run-1", available_locator_ids={"loc-1", "loc-2"})


def test_decoder_allows_valid_fact_candidate_with_allowed_semantics():
    payload = _valid_output_dict()
    payload["fact_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-f1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "fact",
            "fact_type": "既往史",
            "polarity": "negated",
            "asserted_object": "糖尿病病史",
            "raw_value": False,
            "canonical_value": False,
            "unit": "unitless",
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "筛选病历转述",
            "assertion_basis": {"asserted_object": "糖尿病病史", "assertion_text": "无糖尿病病史", "locator_id": "loc-1", "source_text_sha256": SHA},
            "model_uncertainty": 0.95,
            "created_at": NOW.isoformat(),
        }
    ]
    out = parse_evidence_normalizer_output(json.dumps(payload, ensure_ascii=False), expected_run_id="run-1", available_locator_ids={"loc-1", "loc-2"})
    assert len(out.fact_candidates) == 1
    # model_uncertainty 作为审计字段保留，但不参与发布身份
    assert out.fact_candidates[0].model_uncertainty == 0.95


def test_decoder_rejects_candidate_extra_field():
    payload = _valid_output_dict()
    payload["fact_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-f1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "fact",
            "fact_type": "既往史",
            "polarity": "negated",
            "asserted_object": "糖尿病病史",
            "raw_value": False,
            "canonical_value": False,
            "unit": "unitless",
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "当前研究病历直接记录",
            "assertion_basis": {"asserted_object": "糖尿病病史", "assertion_text": "无糖尿病病史", "locator_id": "loc-1", "source_text_sha256": SHA},
            "model_uncertainty": 0.1,
            "created_at": NOW.isoformat(),
            "extra_forbidden": "oops",
        }
    ]
    with pytest.raises(ValueError):
        parse_evidence_normalizer_output(json.dumps(payload, ensure_ascii=False), expected_run_id="run-1", available_locator_ids={"loc-1"})


def test_decoder_allows_empty_candidates_when_pages_closed():
    # 无候选但页闭合（由 unresolved 或门禁判定），此处仅校验形状
    payload = {
        "schema_version": "phase5/v1",
        "run_id": "run-1",
        "call_id": "call-1",
        "logical_document_id": "doc-A",
        "page_numbers": [1],
        "fact_candidates": [],
        "event_candidates": [],
        "exposure_candidates": [],
        "unresolved_items": [],
    }
    out = parse_evidence_normalizer_output(json.dumps(payload, ensure_ascii=False), expected_run_id="run-1", expected_call_id="call-1", expected_page_numbers=[1])
    assert out.fact_candidates == []


# ------------------------------------------------------------- 有界传输适配器

class _FakeTransport:
    def __init__(self, responses):
        # responses: list of (text, session_id) or Exception
        self.responses = list(responses)
        self.start_prompts = []
        self.repair_prompts = []
        self._session = "session-1"
        self._histories = {}

    def start(self, *, prompt):
        self.start_prompts.append(prompt)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        text, sid = item
        self._session = sid
        return type("R", (), {"session_id": sid, "text": text})()

    def continue_session(self, *, session_id, prompt):
        self.repair_prompts.append((session_id, prompt))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        text, sid = item
        return type("R", (), {"session_id": sid, "text": text})()


@pytest.mark.parametrize("refs", [[], ["pending-observation"], ["fabricated-ref"]])
def test_real_runner_rejects_unaccepted_observation_sources(refs):
    inp = _r3_input()
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0]["supported_requirement_ids"] = []
    payload["fact_candidates"][0]["source_observation_refs"] = refs
    raw = json.dumps(payload, ensure_ascii=False)
    transport = _FakeTransport([(raw, "r3-source"), (raw, "r3-source")])
    result = EvidenceNormalizerRunner(max_schema_repairs=1).run(
        inp, transport, prompt_template="请按输入页组抽取候选。"
    )
    assert result.status == "需要核对"
    assert result.final_output is None
    assert len(transport.repair_prompts) == 1
    assert transport.repair_prompts[0][0] == "r3-source"
    assert all(attempt.outcome == "schema_invalid" for attempt in result.attempts)
    assert all("已采信观察" in " ".join(attempt.issues) for attempt in result.attempts)


def test_real_runner_accepts_explicit_source_after_bounded_repair():
    from app.projections.page_review_sources import accepted_observations
    inp = _r3_input()
    payload = _bound_draft_payload("req-history")
    payload["fact_candidates"][0]["supported_requirement_ids"] = []
    invalid = json.dumps(payload, ensure_ascii=False)
    source = accepted_observations(inp.page_review.reviews, inp.page_review.reconciliations[0])[0]
    payload["fact_candidates"][0]["source_observation_refs"] = [source["source_observation_ref"]]
    transport = _FakeTransport([(invalid, "r3-source"), (json.dumps(payload, ensure_ascii=False), "r3-source")])
    result = EvidenceNormalizerRunner(max_schema_repairs=1).run(
        inp, transport, prompt_template="请按输入页组抽取候选。"
    )
    assert result.status == "已解析"
    assert result.final_output.fact_candidates[0].source_observation_refs == [source["source_observation_ref"]]
    assert [attempt.outcome for attempt in result.attempts] == ["schema_invalid", "parsed"]


@pytest.mark.parametrize("invalid_reference", [False, True])
def test_call_local_aliases_restore_real_sources_before_validation(invalid_reference):
    from app.agents.evidence_normalizer import _model_input_payload
    from app.projections.normalizer_reference_aliases import NormalizerReferenceAliases
    from app.projections.page_review_sources import accepted_observations

    inp = _r3_input()
    payload = _bound_draft_payload("req-history")
    fact = payload["fact_candidates"][0]
    fact["supported_requirement_ids"] = []
    source = accepted_observations(inp.page_review.reviews, inp.page_review.reconciliations[0])[0]
    fact["source_observation_refs"] = [source["source_observation_ref"]]
    aliases = NormalizerReferenceAliases.from_payload(_model_input_payload(inp))
    compact = aliases.transform(payload)
    if invalid_reference:
        compact["fact_candidates"][0]["source_observation_refs"] = ["@O99999"]
    result = EvidenceNormalizerRunner(max_schema_repairs=0).run(
        inp, _FakeTransport([(json.dumps(compact, ensure_ascii=False), "short-refs")]),
        prompt_template="请按输入页组抽取候选。", compact_references=True)
    if invalid_reference:
        assert result.final_output is None
        assert "已采信观察" in " ".join(result.attempts[0].issues)
    else:
        original = EvidenceNormalizerRunner(max_schema_repairs=0).run(
            inp, _FakeTransport([(json.dumps(payload, ensure_ascii=False), "full-refs")]),
            prompt_template="请按输入页组抽取候选。")
        assert result.final_output is not None
        assert result.final_output == original.final_output


def test_verified_scope_prompt_requires_retained_pending_and_page_review():
    for inp, retained in ((_input(), True), (_r3_input(), False)):
        with pytest.raises(ValueError, match="待核对原文保全"):
            build_evidence_normalizer_prompt(inp, prompt_template="整理本次资料",
                pending_details_retained=retained, verified_scope_prompt=True)
    prompt = build_evidence_normalizer_prompt(_r3_input(), prompt_template="整理本次资料",
        pending_details_retained=True, verified_scope_prompt=True)
    assert "唯一事实来源是" in prompt
    assert "不能代替临床意义判断" in prompt
    assert "signal_conflicts" in prompt
    assert "当次研究操作" in prompt
    assert _SYSTEM_CONTRACT not in prompt
    assert "有效文本中的每条明确临床陈述均须进入对应候选" not in prompt


def test_verified_scope_repair_does_not_restore_ocr_only_facts():
    inp = _r3_input()
    transport = _FakeTransport([("{}", "verified-repair"), ("{}", "verified-repair")])
    result = EvidenceNormalizerRunner(max_schema_repairs=1).run(inp, transport,
        prompt_template="整理本次资料", pending_details_retained=True, verified_scope_prompt=True)
    assert result.final_output is None
    assert len(transport.repair_prompts) == 1
    repair = transport.repair_prompts[0][1]
    assert "只从本次accepted_observations修复候选" in repair
    assert "重新阅读原始页文本并恢复对应候选" not in repair


class _FailingStartTransport:
    def start(self, *, prompt):
        raise RuntimeError("上游连续返回空正文")

    def continue_session(self, *, session_id, prompt):
        raise RuntimeError("不应进入修复")


class _SchemaEnforcingTransport(_FakeTransport):
    """模拟 omlx 类传输：response_format 已用 JSON Schema 受限解码。"""

    enforces_output_json_schema = True


def test_runner_keeps_embedded_schema_for_json_object_transports():
    inp = _input()
    out_json = json.dumps(_valid_output_dict(), ensure_ascii=False)
    transport = _FakeTransport([(out_json, "session-1")])
    result = EvidenceNormalizerRunner().run(
        inp, transport, prompt_template="请按输入页组抽取候选。"
    )
    assert result.status == "已解析"
    # 无能力声明的传输（DeepSeek/MTPLX/GLM json_object）保持 Schema 内嵌
    assert "输出结构：" in transport.start_prompts[0]
    assert "additionalProperties" in transport.start_prompts[0]
    assert "同一定位内其他完整药名仍须独立抽取" in transport.start_prompts[0]
    assert "但不得生成 exposure_candidate" in transport.start_prompts[0]


def test_runner_omits_embedded_schema_when_transport_enforces_json_schema():
    inp = _input()
    out_json = json.dumps(_valid_output_dict(), ensure_ascii=False)
    transport = _SchemaEnforcingTransport([(out_json, "session-1")])
    result = EvidenceNormalizerRunner().run(
        inp, transport, prompt_template="请按输入页组抽取候选。"
    )
    assert result.status == "已解析"
    assert result.final_output is not None
    # 受限解码传输：提示不再重复内嵌同一份 Schema
    assert "输出结构" not in transport.start_prompts[0]
    assert "additionalProperties" not in transport.start_prompts[0]
    assert "患者无糖尿病病史" in transport.start_prompts[0]


def test_runner_schema_repair_also_omits_schema_when_enforced():
    inp = _input()
    invalid = json.dumps({**_valid_output_dict(), "page_numbers": [99]}, ensure_ascii=False)
    valid = json.dumps(_valid_output_dict(), ensure_ascii=False)
    transport = _SchemaEnforcingTransport([(invalid, "session-1"), (valid, "session-1")])
    result = EvidenceNormalizerRunner().run(
        inp, transport, prompt_template="请按输入页组抽取候选。"
    )
    assert result.status == "已解析"
    assert len(result.attempts) == 2
    # 修复 prompt 同样不重复内嵌 Schema（response_format 每次请求都会强制）
    assert "输出结构" not in transport.repair_prompts[0][1]
    assert "additionalProperties" not in transport.repair_prompts[0][1]
    assert "同一会话内仅修正" in transport.repair_prompts[0][1]


def test_runner_succeeds_on_valid_output_without_repair():
    inp = _input()
    out_json = json.dumps(_valid_output_dict(), ensure_ascii=False)
    transport = _FakeTransport([(out_json, "session-1")])
    runner = EvidenceNormalizerRunner(max_transport_retries=2, max_schema_repairs=2)
    result = runner.run(inp, transport, prompt_template="请按输入页组抽取候选。")
    assert result.status == "已解析"
    assert result.final_output is not None
    assert len(result.attempts) == 1
    assert result.attempts[0].outcome == "parsed"
    assert "患者无糖尿病病史" in transport.start_prompts[0]


def test_runner_repairs_schema_invalid_in_same_session():
    inp = _input()
    invalid = json.dumps({**_valid_output_dict(), "page_numbers": [99]}, ensure_ascii=False)
    valid = json.dumps(_valid_output_dict(), ensure_ascii=False)
    transport = _FakeTransport([(invalid, "session-1"), (valid, "session-1")])
    runner = EvidenceNormalizerRunner(max_transport_retries=2, max_schema_repairs=2)
    result = runner.run(inp, transport, prompt_template="请按输入页组抽取候选。")
    assert result.status == "已解析"
    assert len(result.attempts) == 2
    assert result.attempts[0].outcome == "schema_invalid"
    assert result.attempts[1].outcome == "parsed"
    # 修复 prompt 必须包含中文错误说明且在同一会话
    assert transport.repair_prompts[0][0] == "session-1"
    assert "同一会话内仅修正" in transport.repair_prompts[0][1] or "严格 JSON Schema" in transport.repair_prompts[0][1]


def test_runner_repairs_missing_numeric_unit_with_exact_candidate_context():
    inp = _input()
    invalid = _bound_draft_payload("req-lab")
    fact = invalid["fact_candidates"][0]
    fact.update(
        candidate_ref="fact-heart-rate",
        supported_requirement_ids=[],
        polarity="affirmed",
        asserted_object="心率",
        raw_value="85",
        canonical_value="85",
        unit=None,
        locator_ids=["loc-2"],
        candidate_source_semantics="同期客观结果",
        assertion_basis={
            "asserted_object": "心率",
            "assertion_text": "心率 85",
            "locator_id": "loc-2",
        },
    )
    invalid["unresolved_items"][0].update(
        message="第 1 页无其他候选",
        affected_pages=[1],
    )
    valid = json.loads(json.dumps(invalid, ensure_ascii=False))
    valid["fact_candidates"][0]["unit"] = "次/分"
    transport = _FakeTransport(
        [
            (json.dumps(invalid, ensure_ascii=False), "session-unit"),
            (json.dumps(valid, ensure_ascii=False), "session-unit"),
        ]
    )

    result = EvidenceNormalizerRunner(max_schema_repairs=1).run(
        inp, transport, prompt_template="请按输入页组抽取候选。"
    )

    assert result.status == "已解析"
    assert [attempt.outcome for attempt in result.attempts] == [
        "schema_invalid",
        "parsed",
    ]
    assert transport.repair_prompts[0][0] == "session-unit"
    assert "fact-heart-rate" in transport.repair_prompts[0][1]
    assert "心率" in transport.repair_prompts[0][1]


def test_runner_respects_schema_repair_budget():
    inp = _input()
    invalid = json.dumps({**_valid_output_dict(), "page_numbers": [99]}, ensure_ascii=False)
    # 三次均无效，超过 max_schema_repairs=1 应停在需要核对
    transport = _FakeTransport([(invalid, "session-1"), (invalid, "session-1"), (invalid, "session-1")])
    runner = EvidenceNormalizerRunner(max_transport_retries=2, max_schema_repairs=1)
    result = runner.run(inp, transport, prompt_template="请按输入页组抽取候选。")
    assert result.status == "需要核对"
    assert result.final_output is None
    assert len([a for a in result.attempts if a.outcome == "schema_invalid"]) == 2


def test_runner_classifies_semantically_empty_json_as_empty_output():
    inp = _input()
    empty = json.dumps(
        {
            "schema_version": "phase5/v1",
            "run_id": "run-1",
            "call_id": "call-1",
            "logical_document_id": "doc-A",
            "page_numbers": [1, 2],
            "fact_candidates": [],
            "event_candidates": [],
            "exposure_candidates": [],
            "unresolved_items": [],
        },
        ensure_ascii=False,
    )
    transport = _FakeTransport([(empty, "session-empty")])
    result = EvidenceNormalizerRunner(max_schema_repairs=0).run(
        inp, transport, prompt_template="请按输入页组抽取候选。"
    )
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.attempts[-1].error_code == "EMPTY_OUTPUT"


def test_runner_transport_failure_is_bounded_and_auditable():
    inp = _input()
    transport = _FailingStartTransport()
    runner = EvidenceNormalizerRunner(max_transport_retries=2, max_schema_repairs=2)
    result = runner.run(inp, transport, prompt_template="请按输入页组抽取候选。")
    assert result.status == "需要核对"
    assert result.final_output is None
    assert all(a.outcome == "transport_failed" for a in result.attempts)
    assert len(result.attempts) == 3  # 1 initial + 2 retries
    assert "上游连续返回空正文" in result.attempts[0].issues[0]


def test_runner_repair_transport_failure_stops_cleanly():
    inp = _input()
    invalid = json.dumps({**_valid_output_dict(), "page_numbers": [99]}, ensure_ascii=False)
    transport = _FakeTransport([(invalid, "session-1"), RuntimeError("修订请求未完成")])
    runner = EvidenceNormalizerRunner(max_transport_retries=2, max_schema_repairs=2)
    result = runner.run(inp, transport, prompt_template="请按输入页组抽取候选。")
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.attempts[-1].outcome == "transport_failed"


def test_output_with_medication_exposure_and_event_is_valid():
    payload = _valid_output_dict()
    payload["fact_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-f1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "fact",
            "fact_type": "检验",
            "polarity": "affirmed",
            "asserted_object": "血红蛋白",
            "raw_value": 120,
            "canonical_value": 120,
            "unit": "g/L",
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "同期客观结果",
            "assertion_basis": {"asserted_object": "血红蛋白", "assertion_text": "血红蛋白 120 g/L", "locator_id": "loc-1", "source_text_sha256": SHA},
            "model_uncertainty": 0.05,
            "created_at": NOW.isoformat(),
        }
    ]
    payload["event_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-e1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "event",
            "event_type": "检验事件",
            "duration_status": "unknown",
            "fact_candidate_ids": ["cand-f1"],
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "同期客观结果",
            "model_uncertainty": 0.05,
            "created_at": NOW.isoformat(),
        }
    ]
    payload["exposure_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-m1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "exposure",
            "medication_name": "阿司匹林",
            "duration_status": "unknown",
            "fact_candidate_ids": ["cand-f1"],
            "locator_ids": ["loc-2"],
            "candidate_source_semantics": "既往原始资料",
            "model_uncertainty": 0.1,
            "created_at": NOW.isoformat(),
        }
    ]
    out = parse_evidence_normalizer_output(json.dumps(payload, ensure_ascii=False), expected_run_id="run-1", available_locator_ids={"loc-1", "loc-2"})
    assert len(out.event_candidates) == 1
    assert len(out.exposure_candidates) == 1
    assert out.event_candidates[0].candidate_source_semantics == "同期客观结果"


def _medication_fact(locator_id: str):
    return {
        "schema_version": "phase5/v1",
        "candidate_id": "cand-f1",
        "run_id": "run-1",
        "call_id": "call-1",
        "candidate_kind": "fact",
        "fact_type": "用药",
        "profile_lane": "medication",
        "polarity": "affirmed",
        "asserted_object": "阿司匹林",
        "raw_value": True,
        "canonical_value": True,
        "locator_ids": [locator_id],
        "candidate_source_semantics": "当前研究病历直接记录",
        "assertion_basis": {
            "asserted_object": "阿司匹林",
            "assertion_text": "患者已使用阿司匹林 100 mg 口服。",
            "locator_id": locator_id,
            "source_text_sha256": SHA,
        },
        "model_uncertainty": 0.1,
        "created_at": NOW.isoformat(),
    }


def test_exposure_source_gate_clears_only_unsupported_optional_fields():
    inp = _input()
    medication_text = "患者已使用阿司匹林 100 mg 口服。"
    locators = [
        locator.model_copy(update={"localized_text": medication_text})
        if locator.locator_id == "loc-1"
        else locator
        for locator in inp.available_locators
    ]
    inp = inp.model_copy(update={"available_locators": locators})
    payload = _valid_output_dict()
    payload["fact_candidates"] = [_medication_fact("loc-1")]
    payload["exposure_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-m1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "exposure",
            "medication_name": "阿司匹林",
            "category": "抗血小板药",
            "indication": "心血管预防",
            "dose": "100",
            "unit": "mg",
            "frequency": "每日一次",
            "route": "口服",
            "duration_status": "unknown",
            "fact_candidate_ids": ["cand-f1"],
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "当前研究病历直接记录",
            "model_uncertainty": 0.1,
            "created_at": NOW.isoformat(),
        }
    ]
    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id="run-1",
        available_locator_ids={"loc-1", "loc-2"},
    )

    exposure = _enforce_exposure_source_fields(output, inp).exposure_candidates[0]

    assert exposure.medication_name == "阿司匹林"
    assert exposure.dose == "100"
    assert exposure.unit == "mg"
    assert exposure.route == "口服"
    assert exposure.category is None
    assert exposure.indication is None
    assert exposure.frequency is None


def test_exposure_source_gate_rejects_unsupported_medication_name():
    payload = _valid_output_dict()
    payload["fact_candidates"] = [_medication_fact("loc-2")]
    payload["exposure_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-m1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "exposure",
            "medication_name": "阿司匹林",
            "duration_status": "unknown",
            "fact_candidate_ids": ["cand-f1"],
            "locator_ids": ["loc-2"],
            "candidate_source_semantics": "当前研究病历直接记录",
            "model_uncertainty": 0.1,
            "created_at": NOW.isoformat(),
        }
    ]
    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id="run-1",
        available_locator_ids={"loc-1", "loc-2"},
    )

    with pytest.raises(ValueError, match="药名未逐字出现在所引原文中"):
        _enforce_exposure_source_fields(output, _input())


def test_exposure_source_gate_repairs_name_from_unique_linked_affirmed_fact():
    inp = _input()
    medication_text = "患者已使用阿司匹林 100 mg 口服。"
    inp = inp.model_copy(
        update={
            "available_locators": [
                locator.model_copy(update={"localized_text": medication_text})
                if locator.locator_id == "loc-1"
                else locator
                for locator in inp.available_locators
            ]
        }
    )
    payload = _valid_output_dict()
    payload["fact_candidates"] = [_medication_fact("loc-1")]
    payload["exposure_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-m1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "exposure",
            "medication_name": "阿司匹林片",
            "duration_status": "unknown",
            "fact_candidate_ids": ["cand-f1"],
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "当前研究病历直接记录",
            "model_uncertainty": 0.1,
            "created_at": NOW.isoformat(),
        }
    ]
    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id="run-1",
        available_locator_ids={"loc-1", "loc-2"},
    )

    exposure = _enforce_exposure_source_fields(output, inp).exposure_candidates[0]

    assert exposure.medication_name == "阿司匹林"


def test_exposure_source_gate_uses_page_order_for_cross_line_medication_name():
    """ID 字典序与阅读顺序相反时，仍按页内原文复原药名。"""
    inp = _input()
    page_text = "给予孟鲁司\n特钠片 10 mg，一日一次治疗。"
    page = inp.pages[0].model_copy(
        update={
            "effective_text": page_text,
            "effective_text_sha256": hashlib.sha256(page_text.encode()).hexdigest(),
            "locator_ids": ["loc-1", "loc-2"],
        }
    )
    locators = [
        inp.available_locators[0].model_copy(
            update={
                "locator_id": "loc-1",
                "source_text_sha256": SHA,
                "localized_text": "特钠片 10 mg，一日一次治疗。",
            }
        ),
        inp.available_locators[1].model_copy(
            update={
                "locator_id": "loc-2",
                "page_number": 1,
                "source_text_sha256": SHA,
                "localized_text": "给予孟鲁司",
            }
        ),
    ]
    inp = inp.model_copy(
        update={
            "page_numbers": [1],
            "pages": [page],
            "available_locator_ids": ["loc-1", "loc-2"],
            "available_locators": locators,
        }
    )
    fact = _medication_fact("loc-1")
    fact.update(
        asserted_object="孟鲁司特钠片",
        raw_value=True,
        canonical_value=True,
        locator_ids=["loc-1", "loc-2"],
        assertion_basis={
            "asserted_object": "孟鲁司特钠片",
            "assertion_text": "给予孟鲁司特钠片 10 mg，一日一次治疗。",
            "locator_id": "loc-1",
            "source_text_sha256": SHA,
        },
    )
    payload = _valid_output_dict()
    payload["page_numbers"] = [1]
    payload["fact_candidates"] = [fact]
    payload["exposure_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-m1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "exposure",
            "medication_name": "孟鲁司特钠片",
            "dose": "10",
            "unit": "mg",
            "frequency": "一日一次",
            "duration_status": "unknown",
            "fact_candidate_ids": ["cand-f1"],
            "locator_ids": ["loc-1", "loc-2"],
            "candidate_source_semantics": "筛选病历转述",
            "model_uncertainty": 0.1,
            "created_at": NOW.isoformat(),
        }
    ]
    payload["unresolved_items"] = [
        {
            "code": "medication_name_incomplete",
            "message": "孟鲁司特钠片因换行分布在两个定位",
            "affected_pages": [1],
            "affected_locator_ids": ["loc-1", "loc-2"],
            "affected_requirement_ids": [],
            "gap_type": None,
            "referenced_file_id": None,
            "reason": "模型误以为必须由单个定位承载完整药名",
        }
    ]
    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id="run-1",
        available_locator_ids={"loc-1", "loc-2"},
    )

    enforced = _enforce_exposure_source_fields(output, inp)

    assert [item.medication_name for item in enforced.exposure_candidates] == [
        "孟鲁司特钠片"
    ]
    assert [item.asserted_object for item in enforced.fact_candidates] == [
        "孟鲁司特钠片"
    ]
    assert enforced.unresolved_items == []


def test_exposure_source_gate_drops_exposure_on_locator_with_incomplete_medication_name():
    """药名残缺定位上的药物事实、事件和暴露均不进入发布链。"""
    inp = _input()
    medication_text = "鲁司特钠片 10 mg 每日1次。"
    inp = inp.model_copy(
        update={
            "available_locators": [
                locator.model_copy(update={"localized_text": medication_text})
                if locator.locator_id == "loc-1"
                else locator
                for locator in inp.available_locators
            ]
        }
    )
    payload = _valid_output_dict()
    medication_fact = _medication_fact("loc-1")
    medication_fact.update(
        asserted_object="鲁司特钠片",
        raw_value="鲁司特钠片",
        canonical_value="鲁司特钠片",
        assertion_basis={
            "asserted_object": "鲁司特钠片",
            "assertion_text": "鲁司特钠片 10 mg 每日1次。",
            "locator_id": "loc-1",
            "source_text_sha256": SHA,
        },
    )
    payload["fact_candidates"] = [medication_fact]
    payload["event_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-e1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "event",
            "event_type": "鲁司特钠片开始治疗",
            "profile_lane": "medication",
            "duration_status": "unknown",
            "fact_candidate_ids": ["cand-f1"],
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "筛选病历转述",
            "model_uncertainty": 0.3,
            "created_at": NOW.isoformat(),
        }
    ]
    payload["exposure_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-m1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "exposure",
            "medication_name": "鲁司特钠片",
            "duration_status": "unknown",
            "fact_candidate_ids": ["cand-f1"],
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "筛选病历转述",
            "model_uncertainty": 0.3,
            "created_at": NOW.isoformat(),
        }
    ]
    payload["unresolved_items"] = [
        {
            "code": "medication_name_incomplete",
            "message": "页首仅见鲁司特钠片，药名残缺",
            "affected_pages": [1],
            "affected_locator_ids": ["loc-1"],
            "affected_requirement_ids": [],
            "gap_type": None,
            "referenced_file_id": None,
            "reason": "药名起始部分不在当前页可见范围内",
        }
    ]
    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id="run-1",
        available_locator_ids={"loc-1", "loc-2"},
    )

    enforced = _enforce_exposure_source_fields(output, inp)
    assert enforced.exposure_candidates == []
    assert enforced.fact_candidates == []
    assert enforced.event_candidates == []
    assert [item.code for item in enforced.unresolved_items] == [
        "medication_name_incomplete"
    ]


def test_incomplete_medication_does_not_remove_complete_medication_on_same_locator():
    inp = _input()
    medication_text = "特钠片 10 mg，注射用奥马珠单抗 300 mg 皮下注射。"
    inp = inp.model_copy(
        update={
            "available_locators": [
                locator.model_copy(update={"localized_text": medication_text})
                if locator.locator_id == "loc-1"
                else locator
                for locator in inp.available_locators
            ]
        }
    )
    partial = _medication_fact("loc-1")
    partial.update(
        candidate_id="cand-partial",
        asserted_object="特钠片",
        raw_value="特钠片",
        canonical_value="特钠片",
        assertion_basis={
            "asserted_object": "特钠片",
            "assertion_text": medication_text,
            "locator_id": "loc-1",
            "source_text_sha256": SHA,
        },
    )
    complete = _medication_fact("loc-1")
    complete.update(
        candidate_id="cand-complete",
        asserted_object="注射用奥马珠单抗",
        raw_value="注射用奥马珠单抗",
        canonical_value="注射用奥马珠单抗",
        assertion_basis={
            "asserted_object": "注射用奥马珠单抗",
            "assertion_text": medication_text,
            "locator_id": "loc-1",
            "source_text_sha256": SHA,
        },
    )
    payload = _valid_output_dict()
    payload["fact_candidates"] = [partial, complete]
    payload["exposure_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": candidate_id,
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "exposure",
            "medication_name": medication_name,
            "duration_status": "unknown",
            "fact_candidate_ids": [fact_id],
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "筛选病历转述",
            "model_uncertainty": 0.2,
            "created_at": NOW.isoformat(),
        }
        for candidate_id, medication_name, fact_id in (
            ("exp-partial", "特钠片", "cand-partial"),
            ("exp-complete", "注射用奥马珠单抗", "cand-complete"),
        )
    ]
    payload["unresolved_items"] = [
        {
            "code": "medication_name_incomplete",
            "message": "断行后仅见特钠片",
            "affected_pages": [1],
            "affected_locator_ids": ["loc-1"],
            "affected_requirement_ids": [],
            "gap_type": None,
            "referenced_file_id": None,
            "reason": "完整药名无法由本页证明",
        }
    ]
    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id="run-1",
        available_locator_ids={"loc-1", "loc-2"},
    )

    enforced = _enforce_exposure_source_fields(output, inp)

    assert [fact.candidate_id for fact in enforced.fact_candidates] == ["cand-complete"]
    assert [item.candidate_id for item in enforced.exposure_candidates] == ["exp-complete"]


def test_unverifiable_source_cannot_publish_actual_medication_exposure():
    inp = _input()
    medication_text = "请核实既往是否使用阿司匹林。"
    inp = inp.model_copy(
        update={
            "available_locators": [
                locator.model_copy(update={"localized_text": medication_text})
                if locator.locator_id == "loc-1"
                else locator
                for locator in inp.available_locators
            ]
        }
    )
    fact = _medication_fact("loc-1")
    fact.update(candidate_source_semantics="无法确认来源")
    payload = _valid_output_dict()
    payload["fact_candidates"] = [fact]
    payload["exposure_candidates"] = [
        {
            "schema_version": "phase5/v1",
            "candidate_id": "cand-m1",
            "run_id": "run-1",
            "call_id": "call-1",
            "candidate_kind": "exposure",
            "medication_name": "阿司匹林",
            "duration_status": "unknown",
            "fact_candidate_ids": ["cand-f1"],
            "locator_ids": ["loc-1"],
            "candidate_source_semantics": "无法确认来源",
            "model_uncertainty": 0.6,
            "created_at": NOW.isoformat(),
        }
    ]
    output = parse_evidence_normalizer_output(
        json.dumps(payload, ensure_ascii=False),
        expected_run_id="run-1",
        available_locator_ids={"loc-1", "loc-2"},
    )

    enforced = _enforce_exposure_source_fields(output, inp)

    assert enforced.exposure_candidates == []
    assert [item.candidate_id for item in enforced.fact_candidates] == ["cand-f1"]
