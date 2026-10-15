"""Reference validator delegates unchanged retained sources, never replacements."""
from types import SimpleNamespace

import pytest

from app.domain.contracts.facts import FactAuthority
from app.storage.fact_repositories import FactCrossEntityError
from app.storage.source_reference_successors import validate_source_fact_references


def _references(monkeypatch, *, retained=True, corrected=False, replace_retained=False):
    from app.storage import fact_repositories, source_reference_successors, fact_authority
    authority = FactAuthority(project_id="project", subject_id="subject", review_episode_id="episode",
        episode_revision=11, protocol_version_id="protocol", rule_set_id="rules", rule_set_revision=1,
        evidence_snapshot_v2_id="snapshot", complete_processing_revision_id="complete")
    previous_authority = authority.model_copy(update={"episode_revision": 4})
    def fact(key, *, revision=1, inherited=None, scope=authority):
        return SimpleNamespace(fact_id=key, authority=scope, stable_identity="stable",
            revision=revision, inherited_from_fact_id=inherited, locator_ids=["locator"],
            source_candidate_ids=["candidate"], gate_ids=["gate"])
    values = {"prior": fact("prior"), "next": fact("next", revision=2, inherited="prior"),
        "retained": fact("retained", scope=previous_authority),
        "retained-next": fact("retained-next", revision=2, inherited="retained")}
    monkeypatch.setattr(fact_repositories, "ClinicalFactV2Repository", lambda session: SimpleNamespace(get=values.__getitem__))
    monkeypatch.setattr(source_reference_successors, "FactCorrectionRepository", lambda session: SimpleNamespace(
        superseded_entity_ids=lambda scope: set(),
        list_by_review_episode=lambda episode: [SimpleNamespace(target_id="retained")] if corrected else []))
    checks = []
    def source_check(self, candidate, current):
        checks.append((candidate.fact_id, current))
        return retained
    monkeypatch.setattr(fact_authority.FactAuthorityValidator, "retained_fact_source_is_reusable", source_check)
    current_ids = ["next", "retained-next" if replace_retained else "retained"]
    return authority, current_ids, checks


def test_expectation_keeps_exact_already_qualified_old_reference(monkeypatch):
    authority, current, checks = _references(monkeypatch)
    validate_source_fact_references(None, authority, ["prior", "retained"], current,
        allow_retained_unchanged=True)
    assert checks == [("retained", authority)]


@pytest.mark.parametrize("fault", ["unqualified", "corrected", "replace_old_scope", "event_default"])
def test_retained_source_is_not_a_cross_scope_or_corrected_fact_shortcut(monkeypatch, fault):
    authority, current, _ = _references(monkeypatch, retained=fault != "unqualified",
        corrected=fault == "corrected", replace_retained=fault == "replace_old_scope")
    with pytest.raises(FactCrossEntityError):
        validate_source_fact_references(None, authority, ["prior", "retained"], current,
            allow_retained_unchanged=fault != "event_default")
