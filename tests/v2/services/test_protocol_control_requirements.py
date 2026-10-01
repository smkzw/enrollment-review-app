"""Read-only contract for the completed control package's source gaps."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.domain.contracts.protocol_controls import (
    ProtocolControlDefinitionAtomConsumption,
    ProtocolControlDefinitionConsumerRecord,
)
from app.services import protocol_control_status as module
from app.services.protocol_control_catalog_publication import SourceCalculationGap


@pytest.mark.parametrize("scope_complete,source_unit", [
    (False, "source-unit"), (True, "source-unit"), (True, "other-unit"),
])
def test_requirements_read_only_unresolved_source_gaps(
    monkeypatch, scope_complete: bool, source_unit: str,
) -> None:
    control_id = "control-job"
    source_id = "source-job"
    payload = {"source_deconstruction_job_id": source_id, "workflow_stages": [],
               "draft_revision_id": "draft-revision", "draft_content_sha256": "draft-hash"}
    job = SimpleNamespace(state="completed", cancel_requested=False,
                          payload_json=payload, payload_sha256="job-hash")
    record = ProtocolControlDefinitionConsumerRecord(
        batch_id="batch-a", source_structure_unit_id=source_unit,
        source_statement_index=0, source_quote="定义原文",
        source_span_ids=["source-span"],
        consumers=[ProtocolControlDefinitionAtomConsumption(
            consumer_kind="official_predicate", rule_component_id="component-a",
            predicate_id="predicate-a", consumer_excerpt="对应条款",
        )],
        scope_complete=scope_complete,
        unresolved_reasons=[] if scope_complete else ["对应范围仍待核对"],
    )
    checkpoint = SimpleNamespace(payload_json={
        "source_definition_consumers": [record.model_dump(mode="json")],
    }, payload_sha256="checkpoint-hash")
    session = SimpleNamespace(get=lambda _model, _id: checkpoint)

    @contextmanager
    def session_factory():
        yield session

    monkeypatch.setattr(module, "protocol_control_execution_status", lambda *_args, **_kwargs:
                        SimpleNamespace(publishable_checkpoint_id="checkpoint", source_job_id=source_id))
    monkeypatch.setattr(module, "JobStore", lambda _session:
                        SimpleNamespace(get_job=lambda job_id: job if job_id == control_id else None))
    monkeypatch.setattr(module, "verify_payload_sha256", lambda value, _digest: value)
    monkeypatch.setattr(module, "_verified_candidate_package", lambda *_args, **_kwargs:
                        ("checkpoint", {}))
    monkeypatch.setattr(module, "_validated_batch_results", lambda _checkpoint:
                        (SimpleNamespace(batches=[SimpleNamespace(
                            batch_id="batch-a", batch_number=1,
                            known_procedure_targets=[],
                        )]), []))
    monkeypatch.setattr(module, "ProtocolSectionCoverageManifest", SimpleNamespace(
        model_validate=lambda _value: SimpleNamespace(
            units=[], protocol_version_id="protocol-a", study_phase="phase_ii",
        ),
    ))
    monkeypatch.setattr(module, "ProtocolDraftRevisionRepository", lambda _session:
                        SimpleNamespace(get=lambda _id: SimpleNamespace(
                            content_sha256="draft-hash", protocol_version_id="protocol-a",
                            study_phase="phase_ii", content=SimpleNamespace(proposed_rules=[]),
                        )))
    monkeypatch.setattr(module, "RuleSet", lambda **_kwargs: SimpleNamespace())
    called = []
    gap = SourceCalculationGap(
        batch_number=1, statement_index=0, structure_unit_id="source-unit",
        source_span_ids=("source-span",), source_quote="定义原文",
        linked_official_code=None, review_decision=None, unresolved_aspects=(),
    )

    def gaps(_store, job_id):
        called.append(job_id)
        return (gap,)

    monkeypatch.setattr(module, "source_calculation_gaps", gaps)
    def release(_checkpoint, _plan, _batches, _manifest, _rule_set, _gaps):
        if scope_complete and source_unit != gap.structure_unit_id:
            raise module.ScopeViolationError("来源不同")
        return frozenset({(1, 0)}) if scope_complete else frozenset()

    monkeypatch.setattr(module, "_verified_calculation_release", release)
    if scope_complete and source_unit != gap.structure_unit_id:
        with pytest.raises(module.ProtocolControlCheckpointInvalidError):
            module.protocol_control_requirements(session_factory, job_id=control_id)
        assert called == [control_id]
        return
    view = module.protocol_control_requirements(session_factory, job_id=control_id)
    assert view.job_id == control_id
    assert view.source_job_id == source_id
    assert called == [control_id]
    assert view.calculation_gaps == (() if scope_complete else (gap,))
