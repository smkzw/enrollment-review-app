#!/usr/bin/env python3
"""Independent regressions for slice59n configurable replay + reject gates.

Covers:
- config-driven resolve/pack (table5 planner + viral/TB single-batch)
- cross-chapter source closure stop conditions
- logic/phase/scope rejects on synthetic Agent output
- product bounded repair restoration still enforced
- accepted slice59m real model artifact still publication-green
- accepted viral/TB live MTPLX artifacts retain their parent-reviewed clinical shape
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE_CLOSURE = Path(__file__).resolve().parent
CONFIG_DIR = PHASE_CLOSURE / "configs"
PREPARE_VIRAL = (
    PHASE_CLOSURE / "slice59n-prepare" / "d001-ii-viral-tb-cross-chapter"
)
PREPARE_TABLE5 = PHASE_CLOSURE / "slice59n-prepare" / "d001-ii-table5-reps"
SLICE59M_BOUNDED = (
    ROOT
    / "artifacts"
    / "phase5-slice59m-d001-table5-mtplx-control-replay-bounded-repair-20260827"
)
VIRAL_ACCEPTED = (
    ROOT / "artifacts" / "phase5-slice59n-d001-viral-control-replay-contract-v10-20260828"
)
TB_ACCEPTED = (
    ROOT / "artifacts" / "phase5-slice59n-d001-tb-control-replay-contract-v5-20260828"
)
ICF_DEMOGRAPHICS_ACCEPTED = (
    ROOT
    / "artifacts"
    / "phase5-slice60zb-d001-icf-demographics-replay-before-anchor-20260828"
)

from slice59n_representative_group_control_replay import (  # noqa: E402
    _build_pack,
    _clinical_repair_error,
    _combined_repair_error,
    _load_config,
    _phase_view,
    _published_control_id,
    _publication_repair_error,
    _replay_validation_error,
    _promote_candidate_relations,
    _resolve_units,
)
from slice59n_representative_group_reject_gates import (  # noqa: E402
    VIRAL_TB_REQUIRED_ATTACHED_REFS,
    VIRAL_TB_REQUIRED_OWNED_REFS,
    assert_no_rejects,
    evaluate_hydrated_agent_output,
    evaluate_prepare_source_closure,
)
from app.domain.contracts.protocol_controls import (  # noqa: E402
    ControlCrossSourceRelation,
    ControlRelationTargetKind,
    CrossSourceRelationKind,
)
from app.agents.protocol_control_deconstructor import (  # noqa: E402
    ProtocolControlAgentWireValidationError,
)


def _rows_as_dicts(resolved) -> list[dict]:
    return [
        {
            "source_ref": row.source_ref,
            "role": row.role,
            "lookup": row.lookup,
            "structure_unit_id": row.structure_unit_id,
            "source_span_ids": list(row.source_span_ids),
            "excerpt": row.excerpt,
            "study_phase": row.study_phase,
        }
        for row in resolved
    ]


def test_viral_tb_config_resolves_cross_chapter_closure() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_viral_tb.v1.json")
    rows = _resolve_units(config)
    dict_rows = _rows_as_dicts(rows)
    issues = evaluate_prepare_source_closure(
        group_id=config["group_id"],
        rows=dict_rows,
        owned_source_refs=config["owned_source_refs"],
        attached_source_refs=config.get("attached_source_refs") or [],
        study_phase=config["study_phase"],
    )
    assert_no_rejects(issues)
    owned = {row.source_ref for row in rows if row.role == "owned"}
    attached = {row.source_ref for row in rows if row.role == "attached"}
    assert owned == VIRAL_TB_REQUIRED_OWNED_REFS
    assert VIRAL_TB_REQUIRED_ATTACHED_REFS <= attached
    assert {row.package_id for row in rows if row.role == "owned"} == {
        "pap-3a57e1ae15a1a44c3ea68a1e"
    }


def test_split_configs_keep_each_clinical_family_complete() -> None:
    viral = _load_config(CONFIG_DIR / "representative_group_viral.v1.json")
    tb = _load_config(CONFIG_DIR / "representative_group_tb.v1.json")

    assert viral["owned_source_refs"] == [
        "body.p802",
        "body.p803",
        "body.p804",
        "body.p805",
    ]
    assert viral["required_candidate_source_refs"] == ["body.p804", "body.p805"]
    assert [item["official_code"] for item in viral["known_targets"]["official_rules"]] == ["EX-22"]
    assert tb["owned_source_refs"] == [
        "body.p806",
        "body.p807",
        "body.p808",
        "body.p809",
        "body.p810",
        "body.p811",
        "body.p812",
        "body.p813",
    ]
    assert tb["required_candidate_source_refs"] == [
        "body.p807",
        "body.p809",
        "body.p813",
    ]
    assert [item["official_code"] for item in tb["known_targets"]["official_rules"]] == ["EX-09"]


def test_viral_tb_single_batch_keeps_authority_sources_read_only() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_viral_tb.v1.json")
    rows = _resolve_units(config)
    manifest, plan, batch, *_rest = _build_pack(config, rows)
    assert len(plan.batches) == 1
    assert len(batch.owned_structure_unit_ids) == 12
    assert len(batch.context_structure_unit_ids) == 15
    assert set(batch.owned_structure_unit_ids) == {
        row.structure_unit_id for row in rows if row.role == "owned"
    }
    assert manifest.study_phase.value == "phase_ii"
    assert [item.official_code for item in batch.known_official_targets] == [
        "EX-09",
        "EX-22",
    ]
    assert [item.label for item in batch.known_procedure_targets] == [
        "病毒学检查",
        "结核检测",
    ]
    assert all(item.source_excerpts for item in batch.known_official_targets)
    assert all(item.source_excerpts for item in batch.known_procedure_targets)
    assert not set(batch.owned_structure_unit_ids) & {
        row.structure_unit_id for row in rows if row.role == "attached"
    }
    assert set(batch.context_structure_unit_ids) == {
        row.structure_unit_id for row in rows if row.role == "attached"
    }
    assert {
        (item.review_stage.value, item.visit_instance)
        for item in batch.known_procedure_targets
    } == {("screening", "筛选访视")}
    assert [item.workflow_stage_id for item in batch.known_workflow_stage_targets] == [
        "flow-screening",
        "flow-baseline",
    ]


def test_history_collection_attachments_reach_prompt_as_read_only_context() -> None:
    config = _load_config(
        CONFIG_DIR / "representative_group_history_collection.v2.json"
    )
    rows = _resolve_units(config)
    manifest, plan, batch, _workflow, prompt, *_rest = _build_pack(config, rows)

    assert len(manifest.units) == 4
    assert len(plan.expected_structure_unit_ids) == 4
    assert len(batch.owned_structure_unit_ids) == 4
    assert len(batch.context_structure_unit_ids) == 10
    assert "body.p857" in prompt
    assert "body.p870" in prompt
    assert "基线访视" in prompt
    assert "W0（D1）访视" in prompt
    assert not set(batch.owned_structure_unit_ids) & set(
        batch.context_structure_unit_ids
    )


def test_history_collection_exact_execution_visits_are_frozen_separately() -> None:
    config = _load_config(
        CONFIG_DIR / "representative_group_history_collection.v8.json"
    )
    rows = _resolve_units(config)
    _manifest, _plan, batch, _workflow, prompt, *_rest = _build_pack(config, rows)
    unit_id_by_ref = {
        row.source_ref: row.structure_unit_id for row in rows if row.role == "owned"
    }

    assert batch.owned_visit_instance_by_structure_unit_id == {
        unit_id_by_ref["body.p858"]: "基线访视",
        unit_id_by_ref["body.p871"]: "D1首次给药前",
    }
    assert "owned_visit_instance_by_structure_unit_id" in prompt
    assert "自筛选/上次访视以来" in prompt


def test_history_collection_family_expectations_do_not_leak_into_agent_prompt() -> None:
    config = _load_config(
        CONFIG_DIR / "representative_group_history_collection.v9.json"
    )
    rows = _resolve_units(config)
    _manifest, _plan, batch, _workflow, prompt, *_rest = _build_pack(config, rows)
    unit_id_by_ref = {
        row.source_ref: row.structure_unit_id for row in rows if row.role == "owned"
    }

    assert batch.owned_procedure_semantic_families_by_structure_unit_id == {
        unit_id_by_ref["body.p858"]: [
            "medical_history",
            "treatment_history",
        ],
        unit_id_by_ref["body.p871"]: [
            "medical_history",
            "treatment_history",
        ],
    }
    assert {
        item.semantic_family for item in batch.known_procedure_targets
    } == {"medical_history", "treatment_history"}
    assert "owned_procedure_semantic_families_by_structure_unit_id" not in prompt


def test_icf_demographics_group_uses_active_plan_and_keeps_authorities_read_only() -> None:
    config = _load_config(
        CONFIG_DIR / "representative_group_icf_demographics.v1.json"
    )
    rows = _resolve_units(config)
    row_dicts = _rows_as_dicts(rows)
    issues = evaluate_prepare_source_closure(
        group_id=config["group_id"],
        rows=row_dicts,
        owned_source_refs=config["owned_source_refs"],
        attached_source_refs=config["attached_source_refs"],
        study_phase=config["study_phase"],
    )
    assert_no_rejects(issues)

    manifest, plan, batch, _workflow, prompt, *_rest = _build_pack(config, rows)
    assert len(manifest.units) == 2
    assert len(plan.expected_structure_unit_ids) == 2
    assert {row.package_id for row in rows if row.role == "owned"} == {
        "pap-48c6db04c4eb5d5c0a72679f"
    }
    assert {row.source_ref for row in rows if row.role == "owned"} == {
        "body.p768",
        "body.p770",
    }
    assert {row.source_ref for row in rows if row.role == "attached"} == {
        "body.p767",
        "body.p769",
        "body.t5.r5",
        "body.t5.r6",
        "body.p315",
        "body.p317",
        "body.p630",
        "body.p631",
    }
    assert [item.official_code for item in batch.known_official_targets] == [
        "IN-01",
        "IN-02",
    ]
    assert [item.semantic_family for item in batch.known_procedure_targets] == [
        "informed_consent",
        "demographics",
    ]
    unit_id_by_ref = {
        row.source_ref: row.structure_unit_id
        for row in rows
        if row.role == "owned"
    }
    assert batch.pre_enrollment_structure_unit_ids == [
        unit_id_by_ref["body.p768"],
        unit_id_by_ref["body.p770"],
    ]
    assert batch.owned_visit_instance_by_structure_unit_id == {
        unit_id_by_ref["body.p770"]: "筛选访视"
    }
    assert batch.owned_procedure_semantic_families_by_structure_unit_id == {
        unit_id_by_ref["body.p770"]: ["demographics"]
    }
    assert {
        (item.review_stage.value, item.visit_instance)
        for item in batch.known_procedure_targets
    } == {("screening", "筛选访视")}
    assert [
        item.workflow_stage_id for item in batch.known_workflow_stage_targets
    ] == ["flow-screening"]
    assert "body.p315" in prompt
    assert "body.p317" in prompt
    assert "body.p630" in prompt
    assert "body.p631" in prompt
    assert "clinical_qc_checks_by_source_ref" not in prompt
    assert "owned_procedure_semantic_families_by_structure_unit_id" not in prompt


def test_icf_demographics_parent_delta_expectation_does_not_leak_to_agent() -> None:
    config = _load_config(
        CONFIG_DIR / "representative_group_icf_demographics.v3.json"
    )
    rows = _resolve_units(config)
    _manifest, _plan, batch, _workflow, prompt, *_rest = _build_pack(config, rows)
    unit_id_by_ref = {
        row.source_ref: row.structure_unit_id
        for row in rows
        if row.role == "owned"
    }

    assert config["required_candidate_source_refs"] == ["body.p768"]
    assert batch.owned_required_action_kinds_by_structure_unit_id == {
        unit_id_by_ref["body.p768"]: [
            "explain_information",
            "obtain_signature",
        ],
        unit_id_by_ref["body.p770"]: ["collect_data"],
    }
    assert [
        item.covered_action_kinds for item in batch.known_procedure_targets
    ] == [["obtain_signature"], ["collect_data"]]
    assert "required_candidate_source_refs" not in prompt
    assert "owned_required_action_kinds_by_structure_unit_id" not in prompt
    assert "p768增量候选期望" not in prompt


def test_height_weight_group_freezes_method_deltas_without_prompt_leakage() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_height_weight.v1.json")
    rows = _resolve_units(config)
    _manifest, _plan, batch, _workflow, prompt, *_rest = _build_pack(config, rows)
    unit_id_by_ref = {
        row.source_ref: row.structure_unit_id
        for row in rows
        if row.role == "owned"
    }

    assert {row.package_ordinal for row in rows if row.role == "owned"} == {68}
    assert config["required_candidate_source_refs"] == [
        "body.p777",
        "body.p778",
        "body.p779",
        "body.p780",
        "body.p782",
        "body.p783",
    ]
    assert {
        "perform_height_measurement",
        "record_with_precision",
    } <= set(
        batch.owned_required_action_kinds_by_structure_unit_id[
            unit_id_by_ref["body.p780"]
        ]
    )
    assert batch.owned_required_action_kinds_by_structure_unit_id[
        unit_id_by_ref["body.p783"]
    ] == ["record_with_precision"]
    assert {
        item.semantic_family for item in batch.known_procedure_targets
    } == {"anthropometry"}
    assert "clinical_qc_checks_by_source_ref" not in prompt
    assert "required_candidate_source_refs" not in prompt
    assert "owned_required_action_kinds_by_structure_unit_id" not in prompt
    assert "kg及小数点后1位完整保留" not in prompt


def test_height_weight_rebaseline_separates_timing_from_catalog_coverage() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_height_weight.v2.json")
    rows = _resolve_units(config)
    _manifest, _plan, batch, _workflow, prompt, *_rest = _build_pack(config, rows)
    unit_id_by_ref = {
        row.source_ref: row.structure_unit_id
        for row in rows
        if row.role == "owned"
    }

    assert batch.owned_visit_instance_by_structure_unit_id == {
        unit_id_by_ref["body.p775"]: "筛选访视"
    }
    assert set(batch.pre_enrollment_structure_unit_ids) == {
        unit_id_by_ref[source_ref]
        for source_ref in config["pre_enrollment_source_refs"]
    }
    assert {
        "position_participant",
        "use_calibrated_device",
    } <= set(
        batch.owned_required_action_kinds_by_structure_unit_id[
            unit_id_by_ref["body.p778"]
        ]
    )
    assert "owned_visit_instance_by_structure_unit_id" in prompt
    assert "owned_required_action_kinds_by_structure_unit_id" not in prompt


def test_height_weight_target_scope_is_frozen_without_prompt_leakage() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_height_weight.v8.json")
    rows = _resolve_units(config)
    _manifest, _plan, batch, _workflow, prompt, *_rest = _build_pack(config, rows)
    unit_id_by_ref = {
        row.source_ref: row.structure_unit_id
        for row in rows
        if row.role == "owned"
    }

    assert batch.owned_required_procedure_target_ids_by_structure_unit_id[
        unit_id_by_ref["body.p777"]
    ] == ["procedure:d001-height-weight-screening"]
    assert batch.owned_required_procedure_target_ids_by_structure_unit_id[
        unit_id_by_ref["body.p782"]
    ] == [
        "procedure:d001-height-weight-screening",
        "procedure:d001-weight-baseline",
    ]
    assert batch.owned_visit_instance_by_structure_unit_id == {}
    assert batch.structural_only_structure_unit_ids == [
        unit_id_by_ref["body.p774"],
        unit_id_by_ref["body.p776"],
        unit_id_by_ref["body.p781"],
    ]
    assert batch.owned_required_procedure_target_ids_by_structure_unit_id[
        unit_id_by_ref["body.p775"]
    ] == [
        "procedure:d001-height-weight-screening",
        "procedure:d001-weight-baseline",
    ]
    assert "owned_required_procedure_target_ids_by_structure_unit_id" not in prompt
    assert "structural_only_structure_unit_ids" not in prompt
    assert "身高动作不得绑定基线" not in prompt


def test_icf_demographics_live_acceptance_keeps_action_and_eligibility_layers_separate() -> None:
    summary = json.loads(
        (ICF_DEMOGRAPHICS_ACCEPTED / "replay-summary.json").read_text(
            encoding="utf-8"
        )
    )
    hydrated = json.loads(
        (ICF_DEMOGRAPHICS_ACCEPTED / "hydrated-batch.json").read_text(
            encoding="utf-8"
        )
    )
    gate = json.loads(
        (ICF_DEMOGRAPHICS_ACCEPTED / "gate-results.json").read_text(
            encoding="utf-8"
        )
    )

    assert summary["attempt_outcomes"] == ["schema_invalid", "parsed"]
    assert summary["candidate_count"] == 1
    assert gate["accepted"] is True
    candidate = hydrated["candidates"][0]
    assert candidate["source_span_ids"] == ["body.p768"]
    atoms = candidate["semantics"]["obligation_expression"]["groups"][0]["atoms"]
    assert len(atoms) == 1
    assert atoms[0]["kind"] == "complete_before_anchor"
    assert atoms[0]["time_constraint"]["anchor_type"] == "screening_date"
    assert atoms[0]["time_constraint"]["direction"] == "before"
    assert "签署" not in atoms[0]["statement"]
    assert "签署" not in "".join(atoms[0]["source_excerpts"])
    dispositions = {
        item["structure_unit_id"]: item for item in hydrated["dispositions"]
    }
    assert dispositions["su-dce8b05405461354d06760c5"]["disposition"] == (
        "other_control_candidate"
    )
    assert dispositions["su-a9a2b3350561d48442cf1cba"] == {
        "disposition": "required_procedure",
        "linked_control_candidate_ids": [],
        "linked_official_code": None,
        "linked_procedure_catalog_item_id": None,
        "linked_procedure_catalog_item_ids": [
            "procedure:d001-demographics-screening"
        ],
        "notes": dispositions["su-a9a2b3350561d48442cf1cba"]["notes"],
        "schema_version": "phase5/v1",
        "structure_unit_id": "su-a9a2b3350561d48442cf1cba",
    }


def test_table5_config_still_uses_planner_single_batch() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_table5.v1.json")
    rows = _resolve_units(config)
    _manifest, plan, batch, *_rest = _build_pack(config, rows)
    assert len(rows) == 4
    assert all(row.role == "owned" for row in rows)
    assert len(plan.batches) == 1
    assert len(batch.owned_structure_unit_ids) == 4


def test_explicit_phase_representative_group_builds_publishable_phase_view() -> None:
    config = _load_config(
        CONFIG_DIR / "representative_group_visit_merge_baseline_value.v1.json"
    )
    rows = _resolve_units(config)
    manifest, _plan, _batch, *_rest = _build_pack(config, rows)

    assert manifest.units[0].phase_scopes[0].value == "phase_ii"
    view = _phase_view(manifest, config)
    assert view.accepted is True
    assert view.disposition_for(manifest.units[0].structure_unit_id).value == (
        "selected_phase_applicable"
    )


def test_candidate_relation_promotion_preserves_external_target() -> None:
    candidate_id = "candidate:viral-validity"
    control_id = "pctrl-viral-validity"
    relation = ControlCrossSourceRelation(
        relation_id="relation-viral-ex22",
        kind=CrossSourceRelationKind.FURTHER_EXPLANATION,
        left_target_kind=ControlRelationTargetKind.CONTROL_CANDIDATE,
        left_target_id=candidate_id,
        right_target_kind=ControlRelationTargetKind.OFFICIAL_RULE,
        right_target_id="EX-22",
    )

    promoted = _promote_candidate_relations(
        [relation], candidate_id=candidate_id, control_id=control_id
    )

    assert promoted[0].left_target_kind == ControlRelationTargetKind.PROTOCOL_CONTROL
    assert promoted[0].left_target_id == control_id
    assert promoted[0].right_target_kind == ControlRelationTargetKind.OFFICIAL_RULE
    assert promoted[0].right_target_id == "EX-22"


def test_split_candidates_from_one_source_receive_unique_control_ids() -> None:
    first = _published_control_id("viral", "candidate:screening")
    second = _published_control_id("viral", "candidate:baseline")

    assert first != second
    assert first.endswith("candidate:screening")
    assert second.endswith("candidate:baseline")


def test_publication_repair_error_aggregates_all_affected_candidates() -> None:
    candidates = {
        "candidate:first": SimpleNamespace(
            control_candidate_id="candidate:first",
            frozen_structure_unit_ids=["su-first"],
        ),
        "candidate:second": SimpleNamespace(
            control_candidate_id="candidate:second",
            frozen_structure_unit_ids=["su-second"],
        ),
    }
    error = _publication_repair_error(
        issues=[
            SimpleNamespace(code="ISSUE_A", message="第一项", entity_id="candidate:first"),
            SimpleNamespace(code="ISSUE_B", message="第二项", entity_id="pctrl-second"),
        ],
        candidate_by_id=candidates,
        control_to_candidate={"pctrl-second": "candidate:second"},
        default_structure_unit_ids=["su-all"],
    )

    assert error.code == "PUBLICATION_GATE_REJECTED"
    assert error.candidate_ids == ("candidate:first", "candidate:second")
    assert error.structure_unit_ids == ("su-first", "su-second")
    assert "ISSUE_A: 第一项" in str(error)
    assert "ISSUE_B: 第二项" in str(error)


def test_clinical_repair_error_aggregates_all_affected_units() -> None:
    error = _clinical_repair_error(
        [
            SimpleNamespace(code="ISSUE_A", message="第一项", structure_unit_ids=("su-a",)),
            SimpleNamespace(code="ISSUE_B", message="第二项", structure_unit_ids=("su-b",)),
        ]
    )

    assert error.code == "CLINICAL_REJECT_GATE_REJECTED"
    assert error.structure_unit_ids == ("su-a", "su-b")
    assert "ISSUE_A: 第一项" in str(error)
    assert "ISSUE_B: 第二项" in str(error)


def test_combined_repair_error_exposes_publication_and_clinical_scope_together() -> None:
    publication = ProtocolControlAgentWireValidationError(
        "PUBLICATION_GATE_REJECTED",
        "阶段绑定错误",
        structure_unit_ids=["su-stage"],
        candidate_ids=["candidate:stage"],
    )
    clinical = ProtocolControlAgentWireValidationError(
        "CLINICAL_REJECT_GATE_REJECTED",
        "临床控制遗漏",
        structure_unit_ids=["su-delta"],
    )

    error = _combined_repair_error(publication, clinical)

    assert error.code == "OUTPUT_VALIDATION_REJECTED"
    assert error.structure_unit_ids == ("su-delta", "su-stage")
    assert error.candidate_ids == ("candidate:stage",)
    assert "阶段绑定错误" in str(error)
    assert "临床控制遗漏" in str(error)


def test_replay_validation_does_not_feed_expected_delta_back_to_agent() -> None:
    candidate = SimpleNamespace(
        control_candidate_id="candidate:stage",
        frozen_structure_unit_ids=["su-stage"],
    )
    error = _replay_validation_error(
        publication_report=SimpleNamespace(
            accepted=False,
            issues=[
                SimpleNamespace(
                    code="MIXED_TRIGGER_DECISION_STAGES",
                    message="筛选与首次给药前最终判定时点未拆分",
                    entity_id="candidate:stage",
                )
            ],
        ),
        clinical_issues=[
            SimpleNamespace(
                code="CONTROL_DELTA_DROPPED",
                message="初潮前女性豁免未形成增量候选",
                structure_unit_ids=("su-premenarchal",),
            )
        ],
        candidate_by_id={"candidate:stage": candidate},
        control_to_candidate={},
        default_structure_unit_ids=["su-all"],
    )

    assert error is not None
    assert error.code == "OUTPUT_VALIDATION_REJECTED"
    assert error.structure_unit_ids == ("su-stage",)
    assert error.candidate_ids == ("candidate:stage",)
    assert "MIXED_TRIGGER_DECISION_STAGES" in str(error)
    assert "CONTROL_DELTA_DROPPED" not in str(error)


def test_replay_validation_keeps_expected_delta_for_parent_acceptance_only() -> None:
    error = _replay_validation_error(
        publication_report=SimpleNamespace(accepted=True, issues=[]),
        clinical_issues=[
            SimpleNamespace(
                code="CONTROL_DELTA_DROPPED",
                message="人工预期存在增量控制，但 Agent 判定已被目录覆盖",
                structure_unit_ids=("su-expected",),
            )
        ],
        candidate_by_id={},
        control_to_candidate={},
        default_structure_unit_ids=["su-all"],
    )

    assert error is None


def test_replay_validation_accepts_only_when_both_issue_families_are_empty() -> None:
    assert (
        _replay_validation_error(
            publication_report=SimpleNamespace(accepted=True, issues=[]),
            clinical_issues=[],
            candidate_by_id={},
            control_to_candidate={},
            default_structure_unit_ids=["su-all"],
        )
        is None
    )


def test_planner_mode_rejects_cross_chapter_attachments() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_viral_tb.v1.json")
    config = copy.deepcopy(config)
    config["batching"] = {"mode": "planner"}
    rows = _resolve_units(config)
    with pytest.raises(SystemExit, match="single_batch_with_attachments"):
        _build_pack(config, rows)


def test_missing_attached_ref_is_source_missing() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_viral_tb.v1.json")
    rows = _resolve_units(config)
    dict_rows = [
        row
        for row in _rows_as_dicts(rows)
        if row["source_ref"] != "body.p649"
    ]
    issues = evaluate_prepare_source_closure(
        group_id=config["group_id"],
        rows=dict_rows,
        owned_source_refs=config["owned_source_refs"],
        attached_source_refs=config.get("attached_source_refs") or [],
        study_phase=config["study_phase"],
    )
    assert any(issue.code in {"SOURCE_MISSING", "CONTEXT_BLIND_CROSS_CHAPTER"} for issue in issues)
    assert any("body.p649" in issue.source_refs for issue in issues)


def test_prepare_artifact_matches_config_closure() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_viral_tb.v1.json")
    rows = json.loads((PREPARE_VIRAL / "source_rows.json").read_text(encoding="utf-8"))
    summary = json.loads((PREPARE_VIRAL / "replay-summary.json").read_text(encoding="utf-8"))
    issues = evaluate_prepare_source_closure(
        group_id=config["group_id"],
        rows=rows,
        owned_source_refs=config["owned_source_refs"],
        attached_source_refs=config.get("attached_source_refs") or [],
        study_phase=config["study_phase"],
    )
    assert_no_rejects(issues)
    assert summary["unit_count"] == 27
    assert summary["owned_count"] == 12
    assert summary["attached_count"] == 15
    assert summary["mode"] == "dry_run_prepare"
    assert (PREPARE_TABLE5 / "replay-summary.json").is_file()


def test_hydrated_output_rejects_phase_mismatch() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_viral_tb.v1.json")
    rows = _rows_as_dicts(_resolve_units(config))
    unit_id = next(
        row["structure_unit_id"] for row in rows if row["source_ref"] == "body.p808"
    )
    hydrated = {
        "candidates": [
            {
                "title": "活动性结核不得随机",
                "study_phase": "phase_iii",
                "frozen_structure_unit_ids": [unit_id],
                "semantics": {
                    "obligation_expression": {
                        "groups": [
                            {
                                "atoms": [
                                    {
                                        "statement": "有活动性结核证据的参与者不得被随机分组",
                                        "source_span_ids": ["body.p808"],
                                        "source_excerpts": [
                                            "有活动性结核证据的参与者不得被随机分组"
                                        ],
                                        "time_constraint": None,
                                    }
                                ]
                            }
                        ]
                    },
                    "exception_expression": {"groups": []},
                },
            }
        ],
        "dispositions": [
            {
                "structure_unit_id": unit_id,
                "disposition": "OTHER_CONTROL_CANDIDATE",
            }
        ],
    }
    issues = evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated=hydrated,
        allowed_structure_unit_ids=[row["structure_unit_id"] for row in rows],
    )
    assert any(issue.code == "PHASE_MISMATCH" for issue in issues)


def test_hydrated_output_rejects_dropped_cross_chapter_control_deltas() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_viral_tb.v1.json")
    rows = _rows_as_dicts(_resolve_units(config))
    issues = evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated={"candidates": [], "dispositions": []},
        allowed_structure_unit_ids=[row["structure_unit_id"] for row in rows],
        required_candidate_source_refs=config["required_candidate_source_refs"],
    )
    dropped = {
        issue.source_refs[0]
        for issue in issues
        if issue.code == "CONTROL_DELTA_DROPPED"
    }
    assert dropped == {
        "body.p804",
        "body.p805",
        "body.p807",
        "body.p809",
        "body.p813",
    }


def test_hydrated_output_can_require_an_explicit_non_enrollment_disposition() -> None:
    config = _load_config(
        CONFIG_DIR / "representative_group_vital_sign_modality.v1.json"
    )
    rows = _rows_as_dicts(_resolve_units(config))
    unit_id = next(
        row["structure_unit_id"]
        for row in rows
        if row["source_ref"] == "body.p786"
    )
    hydrated = {
        "candidates": [],
        "dispositions": [
            {
                "structure_unit_id": unit_id,
                "disposition": "post_treatment_execution",
            }
        ],
    }

    assert not evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated=hydrated,
        allowed_structure_unit_ids=[row["structure_unit_id"] for row in rows],
        expected_disposition_by_source_ref={
            "body.p786": "post_treatment_execution"
        },
    )

    issues = evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated={
            "candidates": [],
            "dispositions": [
                {
                    "structure_unit_id": unit_id,
                    "disposition": "other_control_candidate",
                }
            ],
        },
        allowed_structure_unit_ids=[row["structure_unit_id"] for row in rows],
        expected_disposition_by_source_ref={
            "body.p786": "post_treatment_execution"
        },
    )
    assert any(issue.code == "DISPOSITION_MISMATCH" for issue in issues)


def test_parent_qc_can_require_complete_review_stage_scope() -> None:
    config = _load_config(
        CONFIG_DIR / "representative_group_vital_sign_modality.v1.json"
    )
    rows = _rows_as_dicts(_resolve_units(config))
    unit_id = next(
        row["structure_unit_id"]
        for row in rows
        if row["source_ref"] == "body.p785"
    )
    candidate = {
        "frozen_structure_unit_ids": [unit_id],
        "semantics": {
            "review_node_bindings": [
                {"workflow_stage_id": "flow-screening"}
            ],
            "obligation_expression": {"groups": []},
        },
    }

    issues = evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated={"candidates": [candidate], "dispositions": []},
        allowed_structure_unit_ids=[row["structure_unit_id"] for row in rows],
        expected_workflow_stage_ids_by_source_ref={
            "body.p785": ["flow-screening", "flow-baseline"]
        },
    )
    assert any(issue.code == "REVIEW_STAGE_SCOPE_MISMATCH" for issue in issues)

    candidate["semantics"]["review_node_bindings"].append(
        {"workflow_stage_id": "flow-baseline"}
    )
    assert not evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated={"candidates": [candidate], "dispositions": []},
        allowed_structure_unit_ids=[row["structure_unit_id"] for row in rows],
        expected_workflow_stage_ids_by_source_ref={
            "body.p785": ["flow-screening", "flow-baseline"]
        },
    )


def test_parent_qc_rejects_dropped_required_source_components() -> None:
    config = _load_config(
        CONFIG_DIR / "representative_group_package75_semantic_boundary.v1.json"
    )
    rows = _rows_as_dicts(_resolve_units(config))
    unit_id = next(
        row["structure_unit_id"]
        for row in rows
        if row["source_ref"] == "body.p837"
    )
    candidate = {
        "frozen_structure_unit_ids": [unit_id],
        "semantics": {
            "review_node_bindings": [
                {"workflow_stage_id": "flow-screening"},
                {"workflow_stage_id": "flow-baseline"},
                {"workflow_stage_id": "flow-d1-pre-dose"},
            ],
            "obligation_expression": {
                "groups": [
                    {
                        "atoms": [
                            {
                                "statement": "记录开始日期、结束日期、剂量和频率。",
                                "source_span_ids": ["body.p837"],
                                "source_excerpts": [
                                    "开始/结束日期、剂量、治疗频率、给药途径或治疗方法和适应症"
                                ],
                            }
                        ]
                    }
                ]
            },
        },
    }
    kwargs = {
        "group_id": config["group_id"],
        "study_phase": config["study_phase"],
        "rows": rows,
        "hydrated": {"candidates": [candidate], "dispositions": []},
        "allowed_structure_unit_ids": [row["structure_unit_id"] for row in rows],
        "candidate_required_markers_by_source_ref": config[
            "candidate_required_markers_by_source_ref"
        ],
    }
    issues = evaluate_hydrated_agent_output(**kwargs)
    assert any(
        issue.code == "CONTROL_DELTA_COMPONENT_DROPPED" for issue in issues
    )

    candidate["semantics"]["obligation_expression"]["groups"][0]["atoms"][0][
        "statement"
    ] = (
        "记录开始日期、结束日期、剂量、频率、给药途径或治疗方法和适应症。"
    )
    assert not evaluate_hydrated_agent_output(**kwargs)


def test_package75_semantic_partition_is_enforced() -> None:
    config = _load_config(
        CONFIG_DIR / "representative_group_package75_semantic_boundary.v1.json"
    )
    rows = _rows_as_dicts(_resolve_units(config))
    unit_by_ref = {row["source_ref"]: row["structure_unit_id"] for row in rows}
    candidate = {
        "frozen_structure_unit_ids": [unit_by_ref["body.p837"]],
        "title": "合并治疗资料收集",
        "semantics": {
            "review_node_bindings": [
                {"workflow_stage_id": "flow-screening"},
                {"workflow_stage_id": "flow-baseline"},
                {"workflow_stage_id": "flow-d1-pre-dose"},
            ],
            "obligation_expression": {
                "groups": [
                    {
                        "atoms": [
                            {
                                "statement": (
                                    "记录开始日期、结束日期、剂量、频率、给药途径或"
                                    "治疗方法和适应症。"
                                ),
                                "source_span_ids": ["body.p837"],
                            }
                        ]
                    }
                ]
            },
        },
    }
    dispositions = [
        {
            "structure_unit_id": unit_by_ref[ref],
            "disposition": disposition,
        }
        for ref, disposition in config["expected_disposition_by_source_ref"].items()
    ]
    kwargs = {
        "group_id": config["group_id"],
        "study_phase": config["study_phase"],
        "rows": rows,
        "hydrated": {"candidates": [candidate], "dispositions": dispositions},
        "allowed_structure_unit_ids": [row["structure_unit_id"] for row in rows],
        "required_candidate_source_refs": config["required_candidate_source_refs"],
        "forbidden_candidate_source_refs": config["forbidden_candidate_source_refs"],
        "expected_disposition_by_source_ref": config[
            "expected_disposition_by_source_ref"
        ],
        "expected_workflow_stage_ids_by_source_ref": config[
            "expected_workflow_stage_ids_by_source_ref"
        ],
        "candidate_forbidden_markers_by_source_ref": config[
            "candidate_forbidden_markers_by_source_ref"
        ],
        "candidate_required_markers_by_source_ref": config[
            "candidate_required_markers_by_source_ref"
        ],
    }
    assert not evaluate_hydrated_agent_output(**kwargs)

    next(
        item
        for item in dispositions
        if item["structure_unit_id"] == unit_by_ref["body.p831"]
    )["disposition"] = "other_control_candidate"
    issues = evaluate_hydrated_agent_output(**kwargs)
    assert any(issue.code == "DISPOSITION_MISMATCH" for issue in issues)


def test_configured_parent_qc_rejects_duplicate_candidate_and_covered_branch() -> None:
    config = _load_config(
        CONFIG_DIR / "representative_group_pregnancy_fsh_contract_v5.v1.json"
    )
    rows = _rows_as_dicts(_resolve_units(config))
    unit_by_ref = {row["source_ref"]: row["structure_unit_id"] for row in rows}

    def candidate(source_ref: str, title: str) -> dict[str, object]:
        return {
            "title": title,
            "study_phase": "phase_ii",
            "frozen_structure_unit_ids": [unit_by_ref[source_ref]],
            "semantics": {
                "trigger_expression": {"groups": []},
                "obligation_expression": {
                    "groups": [
                        {
                            "atoms": [
                                {
                                    "statement": title,
                                    "source_span_ids": ["body.p815"],
                                    "source_excerpts": [title],
                                    "time_constraint": None,
                                }
                            ]
                        }
                    ]
                },
                "exception_expression": {"groups": []},
            },
        }

    hydrated = {
        "candidates": [
            candidate("body.p815#atom-11-74", "筛选与基线血清妊娠试验"),
            candidate("body.p816", "已绝经妇女无需妊娠试验"),
        ],
        "dispositions": [],
    }
    issues = evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated=hydrated,
        allowed_structure_unit_ids=[row["structure_unit_id"] for row in rows],
        required_candidate_source_refs=config["required_candidate_source_refs"],
        forbidden_candidate_source_refs=config["forbidden_candidate_source_refs"],
        candidate_forbidden_markers_by_source_ref=config[
            "candidate_forbidden_markers_by_source_ref"
        ],
    )

    assert {issue.code for issue in issues} >= {
        "CONTROL_DUPLICATE_RETAINED",
        "COVERED_BRANCH_DUPLICATED",
    }


def test_hydrated_output_rejects_missing_obligation_source() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_viral_tb.v1.json")
    rows = _rows_as_dicts(_resolve_units(config))
    unit_id = next(
        row["structure_unit_id"] for row in rows if row["source_ref"] == "body.p808"
    )
    hydrated = {
        "candidates": [
            {
                "title": "活动性结核不得随机",
                "study_phase": "phase_ii",
                "frozen_structure_unit_ids": [unit_id],
                "semantics": {
                    "obligation_expression": {
                        "groups": [
                            {
                                "atoms": [
                                    {
                                        "statement": "有活动性结核证据的参与者不得被随机分组",
                                        "source_span_ids": [],
                                        "source_excerpts": [],
                                        "time_constraint": None,
                                    }
                                ]
                            }
                        ]
                    },
                    "exception_expression": {"groups": []},
                },
            }
        ],
        "dispositions": [
            {"structure_unit_id": unit_id, "disposition": "OTHER_CONTROL_CANDIDATE"}
        ],
    }
    issues = evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated=hydrated,
        allowed_structure_unit_ids=[row["structure_unit_id"] for row in rows],
    )
    assert any(issue.code == "SOURCE_MISSING" for issue in issues)


def test_hydrated_output_rejects_logic_weakening_on_time_anchor() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_viral_tb.v1.json")
    rows = _rows_as_dicts(_resolve_units(config))
    unit_id = next(
        row["structure_unit_id"] for row in rows if row["source_ref"] == "body.p809"
    )
    hydrated = {
        "candidates": [
            {
                "title": "潜伏结核随机门控",
                "study_phase": "phase_ii",
                "frozen_structure_unit_ids": [unit_id],
                "semantics": {
                    "obligation_expression": {
                        "groups": [
                            {
                                "atoms": [
                                    {
                                        "statement": (
                                            "有潜伏性结核证据的参与者不得被随机分组，"
                                            "除非在随机分组前已完成至少4周的适当治疗疗程。"
                                        ),
                                        "source_span_ids": ["body.p809"],
                                        "source_excerpts": [
                                            "有潜伏性结核证据的参与者不得被随机分组，"
                                            "除非在随机分组前已完成至少4周的适当治疗疗程。"
                                        ],
                                        # Weakening: rewrite randomization gate to first_dose only.
                                        "time_constraint": {
                                            "anchor_type": "first_dose_date",
                                            "direction": "before",
                                            "lower_bound": {"unit": "week", "value": 4},
                                        },
                                    }
                                ]
                            }
                        ]
                    },
                    "exception_expression": {"groups": []},
                },
            }
        ],
        "dispositions": [
            {"structure_unit_id": unit_id, "disposition": "OTHER_CONTROL_CANDIDATE"}
        ],
    }
    issues = evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated=hydrated,
        allowed_structure_unit_ids=[row["structure_unit_id"] for row in rows],
    )
    assert any(issue.code == "LOGIC_WEAKENING" for issue in issues)


def test_hydrated_output_rejects_scope_creep_outside_group() -> None:
    config = _load_config(CONFIG_DIR / "representative_group_viral_tb.v1.json")
    rows = _rows_as_dicts(_resolve_units(config))
    unit_id = next(
        row["structure_unit_id"] for row in rows if row["source_ref"] == "body.p808"
    )
    hydrated = {
        "candidates": [
            {
                "title": "越界候选",
                "study_phase": "phase_ii",
                "frozen_structure_unit_ids": [unit_id, "su-unrelated-outside-group"],
                "semantics": {
                    "obligation_expression": {
                        "groups": [
                            {
                                "atoms": [
                                    {
                                        "statement": "有活动性结核证据的参与者不得被随机分组",
                                        "source_span_ids": ["body.p808"],
                                        "source_excerpts": [
                                            "有活动性结核证据的参与者不得被随机分组"
                                        ],
                                    }
                                ]
                            }
                        ]
                    },
                    "exception_expression": {"groups": []},
                },
            }
        ],
        "dispositions": [],
    }
    issues = evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated=hydrated,
        allowed_structure_unit_ids=[row["structure_unit_id"] for row in rows],
    )
    assert any(issue.code == "SCOPE_CREEP" for issue in issues)


def test_product_repair_scope_escape_is_restored_before_acceptance() -> None:
    # Keep product protection live; do not re-implement the runner check here.
    from tests.v2.protocols import test_slice58c_control_deconstructor as product

    product.test_post_hydration_repair_restores_changes_outside_original_scope()


def test_slice59m_real_model_output_remains_publication_green() -> None:
    summary = json.loads((SLICE59M_BOUNDED / "replay-summary.json").read_text())
    gate = json.loads((SLICE59M_BOUNDED / "gate-results.json").read_text())
    runner = json.loads(
        (SLICE59M_BOUNDED / "execution" / "runner-result.json").read_text()
    )
    assert summary["gate_accepted"] is True
    assert gate["accepted"] is True
    assert gate["issues"] == []
    assert [item["outcome"] for item in runner["attempts"]] == [
        "publication_invalid",
        "parsed",
    ]
    # Repair targeted leflunomide unit only on attempt 1.
    assert runner["attempts"][0]["rejected_structure_unit_ids"] == [
        "su-baee6d67a377ab4f63ee3255"
    ]
    assert len(runner["final_output"]["candidates"]) == 4


def _accepted_artifact(path: Path) -> tuple[dict, dict[str, str]]:
    runner = json.loads((path / "execution" / "runner-result.json").read_text())
    rows = json.loads((path / "source_rows.json").read_text())
    return runner, {row["structure_unit_id"]: row["source_ref"] for row in rows}


def test_viral_live_artifact_keeps_incremental_panel_and_validity_controls_separate() -> None:
    runner, source_ref_by_unit = _accepted_artifact(VIRAL_ACCEPTED)
    candidates = runner["final_output"]["candidates"]
    by_ref: dict[str, list[dict]] = {}
    for candidate in candidates:
        semantics = candidate["semantics"]
        source_ref = source_ref_by_unit[semantics["source_structure_unit_ids"][0]]
        by_ref.setdefault(source_ref, []).append(semantics)

    assert [item["outcome"] for item in runner["attempts"]] == [
        "publication_invalid",
        "parsed",
    ]
    assert {key: len(value) for key, value in by_ref.items()} == {
        "body.p804": 2,
        "body.p805": 1,
    }
    p804_screening = next(
        item
        for item in by_ref["body.p804"]
        if item["review_node_bindings"][0]["review_stage"] == "screening"
    )
    assert [
        atom["statement"]
        for atom in p804_screening["obligation_expression"]["groups"][0]["atoms"]
    ] == ["完成乙肝表面抗体检测", "完成乙肝e抗原检测", "完成乙肝e抗体检测"]
    p805 = by_ref["body.p805"][0]
    trigger_ids = [group["trigger_branch_id"] for group in p805["trigger_expression"]["groups"]]
    assert len(trigger_ids) == 3
    assert set(
        p805["obligation_expression"]["groups"][0]["applies_to_trigger_branch_ids"]
    ) == set(trigger_ids)
    assert p805["obligation_expression"]["groups"][0]["atoms"][0]["time_constraint"] == {
        "allow_partial_date": False,
        "anchor_type": "first_dose_date",
        "combined_window_selection": None,
        "direction": "before",
        "half_life_multiplier": None,
        "lower_bound": None,
        "lower_bound_days": None,
        "upper_bound": None,
        "upper_bound_days": 28,
    }


def test_tb_live_artifact_preserves_exception_optional_action_and_event_anchor() -> None:
    runner, source_ref_by_unit = _accepted_artifact(TB_ACCEPTED)
    output = runner["final_output"]
    candidate_by_ref = {
        source_ref_by_unit[item["semantics"]["source_structure_unit_ids"][0]]: item[
            "semantics"
        ]
        for item in output["candidates"]
    }
    disposition_by_ref = {
        source_ref_by_unit[item["structure_unit_id"]]: item for item in output["dispositions"]
    }

    assert set(candidate_by_ref) == {"body.p807", "body.p808", "body.p809", "body.p813"}
    assert disposition_by_ref["body.p811"]["disposition"] == "official_eligibility"
    assert disposition_by_ref["body.p812"]["disposition"] == "official_eligibility"
    for source_ref in ("body.p808", "body.p809"):
        obligation = candidate_by_ref[source_ref]["obligation_expression"]["groups"][0][
            "atoms"
        ][0]
        assert obligation["time_constraint"]["anchor_type"] == "randomization_date"
        assert obligation["time_constraint"]["direction"] == "on"
    p809 = candidate_by_ref["body.p809"]
    assert len(p809["trigger_expression"]["groups"]) == 1
    assert len(p809["exception_expression"]["groups"]) == 1
    assert p809["exception_expression"]["groups"][0]["atoms"][0]["time_constraint"][
        "lower_bound"
    ] == {"unit": "week", "value": 4}
    p813 = candidate_by_ref["body.p813"]
    assert p813["obligation_expression"]["groups"][0]["atoms"][0]["statement"] == "可进行1次复测"
    assert any("如已执行" in item["description"] for item in p813["minimum_evidence"])
