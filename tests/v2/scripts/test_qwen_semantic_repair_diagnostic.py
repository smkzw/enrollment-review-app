from types import SimpleNamespace
import sqlite3
import json

import pytest

from app.storage.codecs import encode_value, PersistedContractInvalid

from scripts import qwen_semantic_repair_diagnostic as diagnostic


def test_frozen_input_checks_hash_and_job_identity(tmp_path, monkeypatch):
    database = tmp_path / "snapshot.sqlite3"
    raw, digest = encode_value({"source_input": {"frozen": True}})
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE job_checkpoints(job_id, payload_json, payload_sha256, created_at)")
        connection.execute("INSERT INTO job_checkpoints VALUES(?,?,?,?)", ("target", raw, digest, 1))
    monkeypatch.setattr(diagnostic, "ProtocolDeconstructionInput", SimpleNamespace(model_validate=lambda x: x))
    assert diagnostic.frozen_input(database, "target") == {"frozen": True}
    with pytest.raises(ValueError, match="冻结方案输入"):
        diagnostic.frozen_input(database, "other")
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE job_checkpoints SET payload_sha256='invalid'")
    with pytest.raises(PersistedContractInvalid):
        diagnostic.frozen_input(database, "target")


def test_frozen_input_rejects_uncheckpointed_wal(tmp_path):
    database = tmp_path / "snapshot.sqlite3"
    database.with_name(database.name + "-wal").write_bytes(b"pending")
    with pytest.raises(ValueError, match="WAL"):
        diagnostic.frozen_input(database, "target")


def test_offline_gate_does_not_assemble_incomplete_baseline(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    raw, digest = encode_value({"proposed_rules": [{"official_code": "IN-01"}]})
    (cache / "batch.json").write_text(json.dumps({"cache_contract": "protocol-semantic-batch/v1",
        "response_text": raw, "response_sha256": digest}))
    source = SimpleNamespace(parent_rule_catalog=SimpleNamespace(items=[
        SimpleNamespace(official_code="IN-01"), SimpleNamespace(official_code="EX-01")]))
    monkeypatch.setattr(diagnostic, "frozen_payload", lambda *args: {"source_input": {}})
    monkeypatch.setattr(diagnostic, "ProtocolDeconstructionInput", SimpleNamespace(model_validate=lambda _: source))
    monkeypatch.setattr(diagnostic, "_parse_semantic_candidate", lambda *args, **kwargs:
        SimpleNamespace(proposed_rules=[SimpleNamespace(official_code="IN-01")]))
    args = SimpleNamespace(frozen_db=None, job_id="j", offline_gate_cache=cache, output=tmp_path / "output")
    diagnostic.offline_gate(args)
    status = json.loads((args.output / "status.json").read_text())
    assert status["state"] == "incomplete_baseline"
    assert status["missing_rule_codes"] == ["EX-01"]
    assert status["model_called"] is False
    assert not (args.output / "after-draft.json").exists()


def test_frequency_failure_uses_product_predicate_check(monkeypatch):
    atom = object()
    expression = object()
    component = SimpleNamespace(expression=expression, exception_expression=None,
                                source_excerpts=["原文定义"])
    candidate = SimpleNamespace(proposed_rules=[SimpleNamespace(
        official_code="IN-99", components=[component])])
    spec = (3, "month", 4, "次")
    monkeypatch.setattr(diagnostic, "_source_frequency_specs", lambda text: {spec})
    monkeypatch.setattr(diagnostic, "_walk_expression_tree", lambda root: [
        SimpleNamespace(kind="predicate", predicate=atom)])
    monkeypatch.setattr(diagnostic, "_predicate_preserves_frequency", lambda a, s: False)
    issues = diagnostic.frequency_issues(candidate)
    assert len(issues) == 1
    assert issues[0].issue_code == "FREQUENCY_WINDOW_NOT_STRUCTURED"
    assert issues[0].affected_refs == ["IN-99"]
    monkeypatch.setattr(diagnostic, "_predicate_preserves_frequency", lambda a, s: True)
    assert diagnostic.frequency_issues(candidate) == []


def test_scope_check_flags_conjunction_but_not_alternatives():
    def atom(clause, window=None):
        return SimpleNamespace(kind="predicate", predicate=SimpleNamespace(
            source_clause=clause, occurrence_window=window))

    group = SimpleNamespace(kind="logical", operator="all", children=[
        atom("上位条件"), atom("子类（某周期内多次）", object())])
    component = SimpleNamespace(expression=group,
        source_excerpts=["上位条件（包括但不限于子类（某周期内多次））"])
    candidate = SimpleNamespace(proposed_rules=[SimpleNamespace(
        official_code="EX-88", components=[component])])
    issues = diagnostic.scope_issues(candidate)
    assert [i.issue_code for i in issues] == ["FREQUENCY_WINDOW_SCOPE"]
    assert issues[0].level == "需要核对"
    group.operator = "any"
    assert diagnostic.scope_issues(candidate) == []
