"""Product endpoints with fictional sources and an injected completion, never real API fees."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_harness import PageReaderRoute
from tests.v2.api.test_protocol_review_scope import preserved_scope, scope_proposal


def save_scope(client):
    path = "/api/v2/protocol/deconstructions/scope-current/draft"
    view = client.get(path + "/review-scope").json()
    response = client.put(path + "/review-scope", json={"expected_revision_id": view["draft_revision_id"], "proposal": scope_proposal(view)})
    assert response.status_code == 200
    return path, response.json()


def install_completion(monkeypatch, *, fail_first=False):
    from app.agents import protocol_medication_author as author
    route = PageReaderRoute(PageReviewLane.MAIN_A, "fixture", "http://fixture.invalid/v1", "fixture-not-secret", "fixture-model", "high", 65536, 1)
    monkeypatch.setattr(author, "medication_author_route", lambda: route)
    real_author = author.author_medications
    calls = []

    async def completion(route, messages, max_tokens):
        payload = json.loads(messages[1]["content"])
        calls.append(payload)
        assert max_tokens == 65536
        is_local = payload["output_schema"]["title"] == "MedicationRestriction"
        assert len(payload["sources"]) == (1 if is_local else 2)
        assert len({row["source_span_id"] for row in payload["sources"]}) == len(payload["sources"])
        if not is_local:
            heading = next(row for row in payload["sources"] if row["excerpt"] == "合并用药")
        clause = next(row for row in payload["sources"] if row["excerpt"] != "合并用药")
        proposal = {"medications": [{"drug_text": "药物甲", "drug_class_id": None,
            "window": {"anchor_type": "screening_date", "direction": "before", "upper_bound": {"value": 3 if fail_first and len(calls) == 1 else 4, "unit": "week"}},
            "period": None, "applicable_stages": ["screening"], "exception_excerpt": None,
            "unresolved_reason": None, "source_quotes": [clause], "applies_to_rule": None}],
            "source_dispositions": [] if is_local else [{"source_span_id": heading["source_span_id"], "disposition": "heading", "reason": "章节标题"}]}
        return SimpleNamespace(text=json.dumps(proposal["medications"][0] if is_local else proposal), finish_reason="stop", usage={"total_tokens": 123},
            response_model="fixture-model", response_id="fixture-response", output_lengths={})

    async def injected(**kwargs):
        return await real_author(**kwargs, completion=completion)
    monkeypatch.setattr(author, "author_medications", injected)
    return calls


def test_product_proposal_bounded_retry_save_readback_and_existing_review_entry_consumer(build_app, data_paths, monkeypatch):
    calls = install_completion(monkeypatch, fail_first=True)
    app = build_app()
    with TestClient(app) as client:
        preserved_scope(app, data_paths, medication_text="筛选前4周内禁止使用药物甲。")
        path, scope = save_scope(client)
        before = client.get(path).json()
        response = client.post(path + "/medications/suggest", json={"expected_revision_id": scope["draft_revision_id"]})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["supplement"] is not None and len(calls) == 2
        assert calls[1]["item_index"] == 0 and "current_item" in calls[1]
        assert "medications" not in calls[1] and "source_dispositions" not in calls[1]
        assert len(result["receipts"]) == 2
        assert client.post(path + "/medications/suggest", json={"expected_revision_id": scope["draft_revision_id"]}).json()["reused"] is True
        assert len(calls) == 2
        supplement = result["supplement"]
        proposal = {"medications": [{key: value for key, value in row.items() if key != "item_id"} for row in supplement["medications"]],
            "source_dispositions": supplement["source_dispositions"]}
        saved = client.put(path + "/medications", json={"expected_revision_id": scope["draft_revision_id"],
            "proposal": proposal, "proposal_ref": result["proposal_ref"]})
        assert saved.status_code == 200, saved.text
        after = client.get(path).json()
        assert after["revision_id"] != before["revision_id"]
        assert after["content"]["proposed_rules"] == before["content"]["proposed_rules"]
        assert after["content"].get("variable_definitions") == before["content"].get("variable_definitions")
        assert after["content"]["scope_supplement"]["request_refs"]
        entries = client.get(path + "/reviews").json()["entries"]
        medications = [row for row in entries if row["kind"] == "medication"]
        assert len(medications) == 1 and medications[0]["label"] == "药物甲" and medications[0]["review"] is None
        assert len([row for row in entries if row["kind"] == "scope"]) == 1
        assert client.post(path + "/medications/suggest", json={"expected_revision_id": after["revision_id"]}).json()["reused"] is True
        assert len(calls) == 2


def test_bad_quote_or_stale_revision_cannot_write_medications(build_app, data_paths, monkeypatch):
    calls = install_completion(monkeypatch)
    app = build_app()
    with TestClient(app) as client:
        preserved_scope(app, data_paths, medication_text="筛选前4周内禁止使用药物甲。")
        path, scope = save_scope(client)
        result = client.post(path + "/medications/suggest", json={"expected_revision_id": scope["draft_revision_id"]}).json()
        proposal = {"medications": [{key: value for key, value in result["supplement"]["medications"][0].items() if key != "item_id"}],
            "source_dispositions": result["supplement"]["source_dispositions"]}
        proposal["medications"][0]["source_quotes"][0]["excerpt"] = "伪造的原文"
        rejected = client.put(path + "/medications", json={"expected_revision_id": scope["draft_revision_id"], "proposal": proposal})
        assert rejected.status_code == 409
        assert client.get(path).json()["revision_id"] == scope["draft_revision_id"]
        stale = client.post(path + "/medications/suggest", json={"expected_revision_id": "old"})
        assert stale.status_code == 409 and len(calls) == 1


def test_saved_initial_answer_revalidated_without_refreshing_failed_call_budget(build_app, data_paths, monkeypatch):
    from app.agents import protocol_medication_author as author
    calls = install_completion(monkeypatch)
    real_build = author.build_scope_supplement
    def old_guard(**kwargs):
        raise ValueError("模拟旧检查器误拒整个回答")
    monkeypatch.setattr(author, "build_scope_supplement", old_guard)
    app = build_app()
    with TestClient(app) as client:
        preserved_scope(app, data_paths, medication_text="筛选前4周内禁止使用药物甲。")
        path, scope = save_scope(client)
        request = {"expected_revision_id": scope["draft_revision_id"]}
        failed = client.post(path + "/medications/suggest", json=request).json()
        assert failed["supplement"] is None and len(calls) == 2
        assert not failed["manual_supplement"]["medications"]
        assert all(row["disposition"] == "unresolved" for row in failed["manual_supplement"]["source_dispositions"])
        again = client.post(path + "/medications/suggest", json=request).json()
        assert again["supplement"] is None and again["new_model_calls"] == 0 and len(calls) == 2
        monkeypatch.setattr(author, "build_scope_supplement", real_build)
        recovered = client.post(path + "/medications/suggest", json=request).json()
        assert recovered["supplement"] is not None and recovered["new_model_calls"] == 0 and len(calls) == 2
        assert recovered["revalidation"]["basis"] == "original_initial_response"
        assert recovered["revalidated_from"] == failed["proposal_ref"]
        assert len(recovered["receipts"]) == 2
        assert recovered["supplement"]["request_refs"] == [failed["receipts"][0]["request_ref"]]
        from app.evidence.artifacts import ArtifactStore
        assert json.loads(ArtifactStore(data_paths).read(failed["proposal_ref"]))["supplement"] is None
        supplement = recovered["supplement"]
        proposal = {"medications": [{key: value for key, value in row.items() if key != "item_id"} for row in supplement["medications"]],
            "source_dispositions": supplement["source_dispositions"]}
        saved = client.put(path + "/medications", json={**request, "proposal": proposal, "proposal_ref": recovered["proposal_ref"]})
        assert saved.status_code == 200, saved.text
        assert saved.json()["content"]["scope_supplement"]["request_refs"] == supplement["request_refs"]


def test_changed_context_after_failure_does_not_reset_model_budget(build_app, data_paths, monkeypatch):
    from app.agents import protocol_medication_author as author
    calls = install_completion(monkeypatch)
    def old_guard(**kwargs):
        raise ValueError("旧检查器误拒")
    monkeypatch.setattr(author, "build_scope_supplement", old_guard)
    app = build_app()
    with TestClient(app) as client:
        preserved_scope(app, data_paths, medication_text="筛选前4周内禁止使用药物甲。")
        path, scope = save_scope(client)
        request = {"expected_revision_id": scope["draft_revision_id"]}
        first = client.post(path + "/medications/suggest", json=request).json()
        assert first["supplement"] is None and len(calls) == 2
        monkeypatch.setattr(author, "PROMPT", author.PROMPT + "\n不同提示不能借旧回执冒充。")
        second = client.post(path + "/medications/suggest", json=request).json()
        assert second["supplement"] is None and second["new_model_calls"] == 0 and len(calls) == 2


def test_manual_time_meaning_save_review_and_shared_publication_are_one_source_chain(build_app, data_paths, monkeypatch):
    from app.domain.contracts.rules import ProtocolScopeSupplement
    from app.storage.repositories import get_rule_set
    calls = install_completion(monkeypatch)
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        preserved_scope(app, data_paths, medication_text="筛选前4周内禁止使用药物甲。")
        path, scope = save_scope(client)
        result = client.post(path + "/medications/suggest", json={"expected_revision_id": scope["draft_revision_id"]}).json()
        proposal = {"medications": [{key: value for key, value in result["supplement"]["medications"][0].items() if key != "item_id"}],
            "source_dispositions": result["supplement"]["source_dispositions"]}
        proposal["medications"][0]["window_interpretation"] = "minimum_washout"
        assert client.put(path + "/medications", json={"expected_revision_id": scope["draft_revision_id"], "proposal": proposal}).status_code == 422
        proposal["medications"][0]["window_interpretation"] = "prohibited_interval"
        saved = client.put(path + "/medications", json={"expected_revision_id": scope["draft_revision_id"], "proposal": proposal})
        assert saved.status_code == 200, saved.text
        after = saved.json()
        assert after["content"]["scope_supplement"]["medications"][0]["window_interpretation"] == "prohibited_interval"
        assert after["review_scope_pending"] is False
        # Saving has not approved either medication or official requirements.
        blocked = client.post(path.removesuffix("/draft") + "/publish", json={"idempotency_key": "not-reviewed"})
        assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "PUBLICATION_FAILED"
        assert "尚未审定或已修改" in blocked.json()["error"]["detail"]
        assert after["content"]["scope_supplement"]["medications"][0]["item_id"] in blocked.json()["error"]["detail"]
        reviews = client.get(path + "/reviews").json()
        entries = [{"official_code": row["official_code"], "rule_content_hash": row["rule_content_hash"],
            "note": "excluded" if row["kind"] == "procedure" else None,
            "result_variables": ["eos"] if row["kind"] == "procedure" else []} for row in reviews["entries"]]
        approved = client.post(path + "/reviews", json={"expected_revision_id": after["revision_id"],
            "reviewer_kind": "builder_verification", "entries": entries})
        assert approved.status_code == 200, approved.text
        published = client.post(path.removesuffix("/draft") + "/publish", json={"idempotency_key": "reviewed-medication"})
        assert published.status_code == 200, published.text
        assert published.json()["verification_only"] is True
        with app.state.session_factory() as session:
            rules = get_rule_set(session, published.json()["rule_set_id"], published.json()["rule_set_revision"])
            assert rules.scope_supplement == ProtocolScopeSupplement.model_validate(after["content"]["scope_supplement"])
        assert len(calls) == 1


def test_selected_scope_source_damage_blocks_publication_instead_of_hiding_missing_sources(build_app, data_paths, monkeypatch):
    install_completion(monkeypatch)
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        _, _, structure = preserved_scope(app, data_paths, medication_text="筛选前4周内禁止使用药物甲。")
        path, scope = save_scope(client)
        result = client.post(path + "/medications/suggest", json={"expected_revision_id": scope["draft_revision_id"]}).json()
        proposal = {"medications": [{key: value for key, value in result["supplement"]["medications"][0].items() if key != "item_id"}],
            "source_dispositions": result["supplement"]["source_dispositions"]}
        saved = client.put(path + "/medications", json={"expected_revision_id": scope["draft_revision_id"], "proposal": proposal})
        assert saved.status_code == 200
        original = structure.read_bytes()
        structure.write_bytes(b"[]")
        try:
            response = client.post(path.removesuffix("/draft") + "/publish", json={"idempotency_key": "damaged-source"})
            assert response.status_code == 409
            assert response.json()["error"]["code"] == "PUBLICATION_FAILED"
            assert response.json()["error"]["detail"] == "补充范围与已保存原文未能核对一致，原规则保留。"
        finally:
            structure.write_bytes(original)
        assert client.get(path).json()["revision_id"] == saved.json()["revision_id"]


@pytest.mark.parametrize("change", ["members", "new_class"])
def test_manual_class_members_save_review_hash_and_publication_retain_frozen_meaning(build_app, data_paths, monkeypatch, change):
    from app.domain.variables import dictionary
    from app.storage.repositories import get_rule_set
    calls = install_completion(monkeypatch)
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        preserved_scope(app, data_paths, medication_text="筛选前4周内禁止使用药物甲。")
        path, scope = save_scope(client)
        result = client.post(path + "/medications/suggest", json={"expected_revision_id": scope["draft_revision_id"]}).json()
        supplement = result["supplement"]
        classes = supplement["drug_classes"]
        class_id = next(iter(classes))
        one = {key: value for key, value in supplement["medications"][0].items() if key != "item_id"}
        one["window_interpretation"] = "prohibited_interval"
        sibling = deepcopy(one)
        one["drug_class_id"] = class_id
        proposal = {"medications": [one, sibling], "source_dispositions": supplement["source_dispositions"]}
        initial = client.put(path + "/medications", json={"expected_revision_id": scope["draft_revision_id"],
            "proposal": proposal, "proposal_ref": result["proposal_ref"]})
        assert initial.status_code == 200, initial.text
        revision = initial.json()
        reviews = client.get(path + "/reviews").json()
        entries = [{"official_code": row["official_code"], "rule_content_hash": row["rule_content_hash"],
            "note": "excluded" if row["kind"] == "procedure" else None,
            "result_variables": ["eos"] if row["kind"] == "procedure" else []} for row in reviews["entries"]]
        assert client.post(path + "/reviews", json={"expected_revision_id": revision["revision_id"],
            "reviewer_kind": "builder_verification", "entries": entries}).status_code == 200
        monkeypatch.setattr(dictionary, "load_drug_classes", lambda: {"new_global": ["不应替换原类别"]})
        unchanged = client.put(path + "/medications", json={"expected_revision_id": revision["revision_id"], "proposal": proposal})
        assert unchanged.status_code == 200, unchanged.text
        current = unchanged.json()
        assert current["content"]["scope_supplement"]["drug_classes"] == classes
        assert current["content"]["scope_supplement"]["request_refs"] == supplement["request_refs"]
        changed = deepcopy(classes)
        if change == "members":
            changed[class_id].append("合成品种乙")
        else:
            changed["custom_1"] = ["药物甲", "合成品种乙"]
            proposal["medications"][0]["drug_class_id"] = "custom_1"
            proposal["medications"][0]["class_scope"] = "all_members"
        saved = client.put(path + "/medications", json={"expected_revision_id": current["revision_id"],
            "proposal": proposal, "drug_classes": changed})
        assert saved.status_code == 200, saved.text
        after = saved.json()
        assert after["content"]["scope_supplement"]["drug_classes"] == changed
        assert after["content"]["scope_supplement"]["input_sha256"] != supplement["input_sha256"]
        assert after["content"]["scope_supplement"]["request_refs"] == []
        reused = client.post(path + "/medications/suggest", json={"expected_revision_id": after["revision_id"]})
        assert reused.status_code == 200, reused.text
        assert reused.json()["reused"] and reused.json()["new_model_calls"] == 0
        assert reused.json()["supplement"] == after["content"]["scope_supplement"]
        assert initial.json()["content"]["scope_supplement"]["drug_classes"] == classes
        reviewed = client.get(path + "/reviews").json()
        medication_rows = [row for row in reviewed["entries"] if row["kind"] == "medication"]
        assert medication_rows[0]["review"] is None
        assert medication_rows[1]["review"] is not None
        assert all(row["review"] is not None for row in reviewed["entries"] if row["kind"] in {"rule", "procedure"})
        rejected = client.post(path.removesuffix("/draft") + "/publish", json={"idempotency_key": "changed-class-unreviewed"})
        assert rejected.status_code == 409
        pending = [{"official_code": row["official_code"], "rule_content_hash": row["rule_content_hash"]}
            for row in reviewed["entries"] if row["review"] is None]
        assert client.post(path + "/reviews", json={"expected_revision_id": after["revision_id"],
            "reviewer_kind": "builder_verification", "entries": pending}).status_code == 200
        published = client.post(path.removesuffix("/draft") + "/publish", json={"idempotency_key": "class-reviewed"})
        assert published.status_code == 200, published.text
        assert published.json()["verification_only"] is True
        with app.state.session_factory() as session:
            rules = get_rule_set(session, published.json()["rule_set_id"], published.json()["rule_set_revision"])
            assert rules.scope_supplement.drug_classes == changed
            if change == "new_class":
                from app.services.work_draft_medications import calculate_medications
                from app.domain.contracts.enums import ComponentDecision
                from tests.v2.services.test_work_draft_medications import medication_context
                frame, _, refs = medication_context()
                computed = calculate_medications(frame, rules, evidence_refs=refs)
                assert computed[0].decision == ComponentDecision.EXCLUSION_TRIGGERED
                assert computed[0].confidence == "low"
                assert computed[0].evidence_refs == refs["med-fact"]
                # A verified dictionary does not establish a missing exposure.
                frame.medication_exposures = []
                assert calculate_medications(frame, rules, evidence_refs=refs)[0].decision == ComponentDecision.INDETERMINATE
        assert len(calls) == 1


@pytest.mark.parametrize("fault", ["key", "empty", "blank", "duplicate", "false_receipt", "unlinked_class", "blank_class_id", "blank_reference", "false_new_class_receipt"])
def test_bad_class_member_changes_never_write_or_borrow_old_reading(build_app, data_paths, monkeypatch, fault):
    calls = install_completion(monkeypatch)
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        preserved_scope(app, data_paths, medication_text="筛选前4周内禁止使用药物甲。")
        path, scope = save_scope(client)
        result = client.post(path + "/medications/suggest", json={"expected_revision_id": scope["draft_revision_id"]}).json()
        supplement = result["supplement"]
        proposal = {"medications": [{key: value for key, value in row.items() if key != "item_id"}
            for row in supplement["medications"]], "source_dispositions": supplement["source_dispositions"]}
        classes = deepcopy(supplement["drug_classes"])
        class_id = next(iter(classes))
        if fault == "key": classes = {"wrong": ["药物甲"]}
        elif fault == "empty": classes[class_id] = []
        elif fault == "blank": classes[class_id] = [" "]
        elif fault == "duplicate": classes[class_id] = ["药物甲", "药物甲"]
        elif fault == "unlinked_class": classes["custom_1"] = ["药物乙"]
        elif fault == "blank_class_id":
            classes[" "] = ["药物甲"]
        elif fault == "blank_reference":
            proposal["medications"][0]["drug_class_id"] = " "
        elif fault == "false_new_class_receipt":
            classes["custom_1"] = ["药物甲"]
            proposal["medications"][0]["drug_class_id"] = "custom_1"
        else: classes[class_id].append("合成品种乙")
        response = client.put(path + "/medications", json={"expected_revision_id": scope["draft_revision_id"],
            "proposal": proposal, "drug_classes": classes,
            **({"proposal_ref": result["proposal_ref"]} if fault in {"false_receipt", "false_new_class_receipt"} else {})})
        assert response.status_code == (422 if fault == "blank_reference" else 409), response.text
        assert client.get(path).json()["revision_id"] == scope["draft_revision_id"]


def test_class_scope_requires_new_review_and_survives_verification_publication(build_app, data_paths, monkeypatch):
    from app.storage.repositories import get_rule_set
    calls = install_completion(monkeypatch)
    app = build_app(run_runner=False)
    with TestClient(app) as client:
        preserved_scope(app, data_paths, medication_text="筛选前4周内禁止使用药物甲。")
        path, scope = save_scope(client)
        suggested = client.post(path + "/medications/suggest", json={"expected_revision_id": scope["draft_revision_id"]}).json()
        supplement = suggested["supplement"]
        one = {key: value for key, value in supplement["medications"][0].items() if key != "item_id"}
        one["drug_class_id"] = next(iter(supplement["drug_classes"]))
        proposal = {"medications": [one, deepcopy(one)], "source_dispositions": supplement["source_dispositions"]}
        proposal["medications"][1]["drug_class_id"] = None
        saved = client.put(path + "/medications", json={"expected_revision_id": scope["draft_revision_id"], "proposal": proposal})
        assert saved.status_code == 200, saved.text
        current = saved.json()
        reviews = client.get(path + "/reviews").json()
        entries = [{"official_code": row["official_code"], "rule_content_hash": row["rule_content_hash"],
            "note": "excluded" if row["kind"] == "procedure" else None,
            "result_variables": ["eos"] if row["kind"] == "procedure" else []} for row in reviews["entries"]]
        assert client.post(path + "/reviews", json={"expected_revision_id": current["revision_id"],
            "reviewer_kind": "builder_verification", "entries": entries}).status_code == 200
        proposal["medications"][0]["class_scope"] = "all_members"
        changed = client.put(path + "/medications", json={"expected_revision_id": current["revision_id"], "proposal": proposal})
        assert changed.status_code == 200, changed.text
        after = client.get(path + "/reviews").json()
        medication_rows = [row for row in after["entries"] if row["kind"] == "medication"]
        assert medication_rows[0]["review"] is None and medication_rows[1]["review"] is not None
        assert all(row["review"] is not None for row in after["entries"] if row["kind"] in {"rule", "procedure"})
        publication = path.removesuffix("/draft") + "/publish"
        assert client.post(publication, json={"idempotency_key": "unreviewed-scope"}).status_code == 409
        pending = [{"official_code": row["official_code"], "rule_content_hash": row["rule_content_hash"]}
                   for row in after["entries"] if row["review"] is None]
        assert client.post(path + "/reviews", json={"expected_revision_id": changed.json()["revision_id"],
            "reviewer_kind": "builder_verification", "entries": pending}).status_code == 200
        published = client.post(publication, json={"idempotency_key": "reviewed-scope"})
        assert published.status_code == 200, published.text
        assert published.json()["verification_only"] is True
        with app.state.session_factory() as session:
            rules = get_rule_set(session, published.json()["rule_set_id"], published.json()["rule_set_revision"])
            assert rules.scope_supplement.medications[0].class_scope == "all_members"
            assert rules.scope_supplement.medications[1].class_scope is None
        assert len(calls) == 1
        assert len(calls) == 1
