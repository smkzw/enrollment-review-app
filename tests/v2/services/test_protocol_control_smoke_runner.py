"""冒烟运行器的确定性检查：不调用真实模型，仅替换语义传输。

来源链、控制任务建立、生产执行器与 JobRunner 全部使用真实生产实现；
只有发现/深析两个语义传输被确定性假传输替换。运行记录、模型身份失效
关闭、真实项目边界守卫与合成协议词汇中立性在此验证。
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from docx import Document

from app.agents.protocol_control_agent_transport import (
    ProtocolControlModelIdentityError,
)
from app.agents.protocol_control_deconstructor import (
    CONTROL_AGENT_WIRE_VERSION,
    CONTROL_DISCOVERY_WIRE_VERSION,
)
from app.domain.contracts.protocol_controls import (
    ControlObligationKind,
    ProtocolControlDiscoveryDisposition,
    StructureUnitDispositionKind,
)
from app.workflow.errors import StepFailure


REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = REPO_ROOT / "scripts" / "run_protocol_control_smoke.py"


@pytest.fixture(scope="module")
def smoke():
    spec = importlib.util.spec_from_file_location(
        "run_protocol_control_smoke_under_test", _SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _prompt_payload(prompt: str, marker: str) -> dict[str, Any]:
    return json.loads(prompt.split(marker, 1)[1].split("\n\n", 1)[0])


class _FakeDiscoveryTransport:
    """确定性发现传输：有摘录的单元轮流进入候选/不确定，其余轮流上下文/非控制。"""

    def __init__(self, model: str = "fake-smoke-model") -> None:
        self.model = model
        self.start_calls = 0
        self.routing: dict[str, str] = {}
        self.candidate_count = 0

    def verify_model_identity(self, *, force: bool = False) -> str:
        return self.model

    def _response(self, prompt: str):
        payload = _prompt_payload(prompt, "本次发现输入：")
        units = payload["target_units"]
        for unit in units:
            unit_id = unit["structure_unit_id"]
            if unit_id in self.routing:
                continue
            if unit.get("excerpt", "").strip() and self.candidate_count < 4:
                disposition = (
                    ProtocolControlDiscoveryDisposition.CANDIDATE
                    if self.candidate_count % 2 == 0
                    else ProtocolControlDiscoveryDisposition.UNCERTAIN
                )
                self.candidate_count += 1
            else:
                disposition = (
                    ProtocolControlDiscoveryDisposition.CONTEXT_ONLY
                    if len(self.routing) % 2 == 0
                    else ProtocolControlDiscoveryDisposition.NON_CONTROL
                )
            self.routing[unit_id] = disposition.value
        decisions = [
            {
                "structure_unit_id": unit["structure_unit_id"],
                "disposition": self.routing[unit["structure_unit_id"]],
                "required_context_structure_unit_ids": [],
                "rationale": "deterministic smoke routing",
            }
            for unit in units
        ]
        from app.agents.protocol_control_deconstructor import (
            ProtocolControlDiscoveryAgentResponse,
        )

        return ProtocolControlDiscoveryAgentResponse(
            session_id="smoke-discovery-session",
            text=json.dumps(
                {
                    "wire_version": CONTROL_DISCOVERY_WIRE_VERSION,
                    "decisions": decisions,
                },
                ensure_ascii=False,
            ),
        )

    def start(self, *, prompt: str):
        self.start_calls += 1
        return self._response(prompt)

    def continue_session(self, *, session_id: str, prompt: str):
        raise AssertionError("确定性冒烟不应触发发现修复会话")


class _FakeDeepTransport:
    """确定性深析传输：每个 owned 单元一个增量候选，绑定空审核目标。"""

    def __init__(self, model: str = "fake-smoke-model") -> None:
        self.model = model
        self.start_calls = 0
        self.owned_batches: list[tuple[str, ...]] = []

    def verify_model_identity(self, *, force: bool = False) -> str:
        return self.model

    def _response(self, prompt: str):
        payload = _prompt_payload(prompt, "本次冻结输入：")
        units = payload["owned_units"]
        targets = payload["known_workflow_stage_targets"]
        assert targets, "冻结必做项目录必须为非空，否则无法派生可绑定审核节点"
        stage = targets[0]
        self.owned_batches.append(
            tuple(unit["structure_unit_id"] for unit in units)
        )
        dispositions = []
        candidates = []
        for unit in units:
            unit_id = unit["structure_unit_id"]
            span_ids = sorted(unit["source_span_ids"])
            excerpts = (
                [unit["excerpt"]] if unit.get("excerpt", "").strip() else []
            )
            dispositions.append(
                {
                    "structure_unit_id": unit_id,
                    "disposition": StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
                    "linked_official_code": None,
                    "linked_procedure_catalog_item_id": None,
                    "linked_procedure_catalog_item_ids": [],
                    "notes": "deterministic smoke candidate",
                }
            )
            candidates.append(
                {
                    "title": "smoke candidate",
                    "applicable_population": "synthetic scope",
                    "applicability_expression": None,
                    "trigger_expression": None,
                    "obligation_expression": {
                        "groups": [
                            {
                                "atoms": [
                                    {
                                        "kind": ControlObligationKind.REACH_CONDITION.value,
                                        "statement": unit["excerpt"] or "record state",
                                        "time_constraint": None,
                                        "prospective_period": None,
                                        "modality": "mandatory",
                                        "temporal_scope": None,
                                        "source_span_ids": span_ids,
                                        "source_excerpts": excerpts,
                                        "requires_professional_judgment": False,
                                    }
                                ],
                                "applies_to_trigger_branch_indexes": [],
                            }
                        ]
                    },
                    "exception_expression": None,
                    "review_node_bindings": [
                        {
                            "workflow_stage_id": stage["workflow_stage_id"],
                            "review_stage": stage["review_stage"],
                            "role": "decide_at_node",
                            "guidance": None,
                        }
                    ],
                    "minimum_evidence": [
                        {
                            "fact_type": "source",
                            "description": "source evidence",
                            "due_stage": stage["review_stage"],
                            "required_source_types": ["source"],
                        }
                    ],
                    "source_structure_unit_ids": [unit_id],
                    "source_span_ids": span_ids,
                    "cross_source_relations": [],
                }
            )
        from app.agents.protocol_control_deconstructor import (
            ProtocolControlAgentResponse,
        )

        return ProtocolControlAgentResponse(
            session_id="smoke-deep-session",
            text=json.dumps(
                {
                    "wire_version": CONTROL_AGENT_WIRE_VERSION,
                    "dispositions": dispositions,
                    "candidate_drafts": candidates,
                },
                ensure_ascii=False,
            ),
        )

    def start(self, *, prompt: str):
        self.start_calls += 1
        return self._response(prompt)

    def continue_session(self, *, session_id: str, prompt: str):
        raise AssertionError("确定性冒烟不应触发深析修复会话")


def _identity_record(smoke, discovery, deep) -> dict[str, Any]:
    return {
        "verified_before_run": True,
        "discovery": smoke._transport_identity(
            discovery, stage="discovery", verified_model=discovery.model
        ),
        "deep": smoke._transport_identity(
            deep, stage="deep", verified_model=deep.model
        ),
    }


@pytest.fixture
def patched_verify(smoke, monkeypatch):
    def install(discovery, deep):
        record = _identity_record(smoke, discovery, deep)
        monkeypatch.setattr(
            smoke,
            "verify_live_model_identity",
            lambda **kwargs: (discovery, deep, record),
        )
        return record

    return install


# ---------------------------------------------------------------------------
# 模型身份失效关闭
# ---------------------------------------------------------------------------


def test_identity_mismatch_fails_closed_before_any_run(
    smoke, tmp_path, monkeypatch
):
    def raise_mismatch(**kwargs):
        raise ProtocolControlModelIdentityError(
            "配置模型与服务实际加载模型不一致",
            configured_model="quality-target",
            served_model_ids=["speed-variant-loaded"],
            reason="mismatch",
        )

    monkeypatch.setattr(smoke, "verify_live_model_identity", raise_mismatch)
    record, exit_code = smoke.run_smoke(out_dir=tmp_path / "out")

    assert exit_code == smoke.EXIT_IDENTITY_FAIL_CLOSED
    identity = record["model_identity"]
    assert identity["verified_before_run"] is False
    assert identity["failure_class"] == "model_identity_mismatch"
    assert identity["reason"] == "mismatch"
    assert identity["configured_model"] == "quality-target"
    assert identity["served_model_ids"] == ["speed-variant-loaded"]
    # 失效关闭必须发生在任何任务建立之前：不创建数据目录与合成文件。
    assert not (tmp_path / "out" / "data_v2").exists()
    persisted = json.loads(
        (tmp_path / "out" / "run_record.json").read_text(encoding="utf-8")
    )
    assert persisted["claims_complete"] is False
    assert persisted["model_identity"]["failure_class"] == "model_identity_mismatch"


# ---------------------------------------------------------------------------
# 真实项目边界守卫
# ---------------------------------------------------------------------------


def test_guard_rejects_real_project_and_data_dir_fixtures(smoke, tmp_path, monkeypatch):
    fake_repo = tmp_path / "repo"
    projects_dir = fake_repo / "projects"
    projects_dir.mkdir(parents=True)
    project_protocol = projects_dir / "real.docx"
    project_protocol.write_bytes(b"docx")
    monkeypatch.setattr(smoke, "REPO_ROOT", fake_repo)
    monkeypatch.setattr(
        smoke,
        "resolve_data_paths",
        lambda **kwargs: type("P", (), {"root": tmp_path / "real_data"})(),
    )

    with pytest.raises(smoke.SmokeGuardError):
        smoke._assert_fixture_allowed(project_protocol)
    with pytest.raises(smoke.SmokeGuardError):
        smoke._assert_fixture_allowed(tmp_path / "real_data" / "uploaded.docx")
    # 受控临时目录中的合成文件不被拒绝。
    allowed = tmp_path / "scratch" / "synthetic.docx"
    allowed.parent.mkdir(parents=True)
    allowed.write_bytes(b"docx")
    smoke._assert_fixture_allowed(allowed)


def test_phase_selection_never_uses_a_fixed_priority(smoke) -> None:
    candidates = [{"phase": "phase_ii"}, {"phase": "phase_iii"}]

    with pytest.raises(smoke.SmokeGuardError, match="不得按固定优先级"):
        smoke._pick_study_phase(candidates)
    assert smoke._pick_study_phase(
        candidates,
        selected_phase=smoke.StudyPhase.PHASE_III,
    ) == smoke.StudyPhase.PHASE_III


def test_explicit_phase_must_exist_in_recognized_candidates(smoke) -> None:
    with pytest.raises(smoke.SmokeGuardError, match="不在方案识别候选中"):
        smoke._pick_study_phase(
            [{"phase": "phase_ii"}],
            selected_phase=smoke.StudyPhase.PHASE_III,
        )


# ---------------------------------------------------------------------------
# 合成协议词汇中立性
# ---------------------------------------------------------------------------


def test_synthetic_fixture_is_self_contained(smoke, tmp_path):
    docx_path = tmp_path / "synthetic.docx"
    sha256 = smoke.build_synthetic_protocol_docx(docx_path)

    declared_texts: set[str] = {smoke._SYNTHETIC_DOCX_TITLE}
    for heading, paragraphs, rules in smoke._SYNTHETIC_DOCX_SECTIONS:
        declared_texts.add(heading)
        declared_texts.update(paragraphs)
        declared_texts.update(rules)
    declared_texts.update(cell for row in smoke._SYNTHETIC_FLOW_TABLE for cell in row)

    document = Document(str(docx_path))
    produced: list[str] = []
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            produced.append(paragraph.text)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    produced.append(cell.text)
    # 文档中的每一段文本都必须逐字来自声明的常量集合：任何外部输入都
    # 无法进入合成文档，结构上保证词汇中立。
    assert set(produced) <= declared_texts
    assert sha256 == hashlib.sha256(docx_path.read_bytes()).hexdigest()
    assert any(
        "该受试者进入基线节点前" in text
        and "必须同时满足" in text
        and "任一项未满足" in text
        for text in produced
    )


# ---------------------------------------------------------------------------
# 端到端：真实生产链 + 确定性假传输
# ---------------------------------------------------------------------------


def test_full_smoke_run_with_verified_fake_transports(
    smoke, tmp_path, patched_verify
):
    discovery = _FakeDiscoveryTransport()
    deep = _FakeDeepTransport()
    patched_verify(discovery, deep)

    record, exit_code = smoke.run_smoke(out_dir=tmp_path / "out")
    run_record_path = Path(record["run_record_path"])
    persisted = json.loads(run_record_path.read_text(encoding="utf-8"))

    assert exit_code == smoke.EXIT_OK
    assert record["model_identity"]["discovery"]["verified_model"] == "fake-smoke-model"
    assert record["model_identity"]["deep"]["verified_model"] == "fake-smoke-model"

    source = record["source_chain"]
    assert source["stopped_after"] == "freeze_deconstruction_input"
    assert source["stop_error_code"] == "SMOKE_SOURCE_STOP_AFTER_FREEZE"
    assert source["snapshot_id"]
    assert source["content_sha256"]
    assert source["block_count"] and source["block_count"] > 0

    control = record["control_execution"]
    assert control["final_state"] == "completed"
    assert control["result_kind"] == "hydrated_candidate_control_package"
    assert control["formal_catalog_status"] == "not_materialized"
    assert control["gate_version"]
    assert control["candidate_ids_count"] > 0
    assert record["semantic_acceptance"] == {
        "mode": "bundled_positive_control",
        "incremental_candidate_required": True,
        "passed": True,
        "failure_codes": [],
    }
    distribution = control["discovery"]["distribution"]
    assert distribution
    assert sum(distribution.values()) == sum(
        batch["decision_count"] for batch in control["discovery"]["batches"]
    )
    assert distribution.get("candidate", 0) + distribution.get("uncertain", 0) > 0
    assert control["deep"]["batch_count"] == len(deep.owned_batches)
    assert control["deep"]["owned_structure_unit_count"] == sum(
        len(batch) for batch in deep.owned_batches
    )
    assert control["discovery"]["schema_repair_count"] == 0
    assert control["deep"]["schema_repair_count"] == 0
    assert control["latency_seconds"]["control_execution"] >= 0

    boundaries = record["boundaries"]
    assert boundaries["formal_catalog_materialized"] is False
    assert boundaries["source_snapshot_bypassed"] is False
    assert boundaries["fixture_is_synthetic_only"] is True
    assert record["claims_complete"] is False
    assert record["latency_seconds"]["total"] >= 0

    # 运行记录必须与返回值一致且可独立加载。
    assert persisted["run_id"] == record["run_id"]
    assert (
        persisted["control_execution"]["result_kind"]
        == "hydrated_candidate_control_package"
    )


def test_smoke_source_job_never_reaches_official_deconstruction(
    smoke, tmp_path, patched_verify
):
    """来源任务必须在冻结快照后停止，不得进入官方 IN/EX 语义解构。"""

    discovery = _FakeDiscoveryTransport()
    deep = _FakeDeepTransport()
    patched_verify(discovery, deep)

    record, exit_code = smoke.run_smoke(out_dir=tmp_path / "out")
    assert exit_code == smoke.EXIT_OK
    source = record["source_chain"]
    assert source["final_state"] == "failed_final"
    assert source["stop_error_code"] == "SMOKE_SOURCE_STOP_AFTER_FREEZE"
    # 冻结快照必须真实存在且被生产控制任务消费。
    assert record["control_execution"]["job_id"]
    assert record["control_execution"]["job_id"] != source["job_id"]


def test_completed_job_resume_reuses_sqlite_without_reopening_source(
    smoke, tmp_path, patched_verify
):
    discovery = _FakeDiscoveryTransport()
    deep = _FakeDeepTransport()
    patched_verify(discovery, deep)
    out_dir = tmp_path / "out"

    first, first_exit = smoke.run_smoke(out_dir=out_dir)
    assert first_exit == smoke.EXIT_OK
    discovery_calls = discovery.start_calls
    deep_calls = deep.start_calls
    (out_dir / "synthetic_protocol.docx").unlink()

    resumed, resumed_exit = smoke.run_smoke(
        out_dir=out_dir,
        resume_job_id=first["control_execution"]["job_id"],
    )

    assert resumed_exit == smoke.EXIT_OK
    assert resumed["resume"]["runner_claimed"] is False
    assert resumed["source_chain"]["source_file_read"] is False
    assert resumed["boundaries"]["real_protocol_content_used"] is None
    assert discovery.start_calls == discovery_calls
    assert deep.start_calls == deep_calls
    assert resumed["semantic_acceptance"]["passed"] is True
    assert Path(resumed["run_record_path"]).name.startswith("resume-")


@pytest.mark.parametrize(
    ("field", "value", "failure_code"),
    [
        ("result_kind", "legacy_result", "CANDIDATE_PACKAGE_RESULT_INVALID"),
        ("formal_catalog_status", "materialized", "FORMAL_CATALOG_BOUNDARY_INVALID"),
        ("gate_accepted", False, "CANDIDATE_GATE_NOT_ACCEPTED"),
    ],
)
def test_candidate_gate_acceptance_rejects_stale_terminal_payload(
    smoke, field, value, failure_code
):
    metrics = {
        "final_state": "completed",
        "result_kind": smoke.CANDIDATE_CONTROL_PACKAGE_RESULT_KIND,
        "formal_catalog_status": smoke.FORMAL_CATALOG_STATUS_NOT_MATERIALIZED,
        "gate_accepted": True,
    }
    metrics[field] = value

    assert failure_code in smoke._candidate_gate_failure_codes(metrics)
