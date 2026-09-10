"""Phase 5 规则索引仓储确定性测试（Slice 5.4，worker_02）。

覆盖：

- 只基于已发布 ``fact_type`` / ``RuleComponent`` / ``EvidenceRequirement`` 显式
  身份建立双向链接，绝不使用 title/description/asserted_object 自由文本模糊匹配；
- 仅当资料要求显式 ``rule_component_id`` 非空时才经该身份追加组件链接；流程必做
  项目录来源（无组件）不捏造组件；
- 不产生跨规则集修订链接；重建等价、幂等、确定性排序；
- 漂移拒绝：父列自洽（合同层）、``link_id`` 内容哈希（payload 漂移）、父实体/父
  要求不再可推导（link-parent 漂移）读取与重建均拒绝。

复用 ``test_fact_repositories`` 的活动证据链播种与发布事实帮助函数（同包内共享）。
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update

from app.domain.contracts.enums import (
    FactGate,
    FactPolarity,
    GateOutcome,
    ReviewStage,
    SourceStrength,
)
from app.domain.contracts.fact_rule_index import (
    FactRuleLink,
    PublishedRequirement,
    derive_fact_rule_links,
    fact_rule_link_id,
)
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalFactCandidateV2,
    ClinicalFactV2,
    FactGateResult,
)
from app.domain.contracts.rules import EvidenceRequirement
from app.storage.codecs import encode_contract
from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
from app.storage.fact_repositories import (
    ClinicalFactV2Repository,
    FactGateResultRepository,
    FactNormalizationCandidateRepository,
)
from app.storage.fact_rule_link_repository import (
    FactRuleIndexError,
    FactRuleLinkDriftError,
    FactRuleLinkV2Repository,
)
from app.storage.facts_models import FactRuleLinkV2Record
from app.storage.models import EvidenceRequirementRecord
from app.storage.repositories import get_rule_set, save_rule_set
from tests.v2.helpers.phase5_fact_chain import NOW, seed_valid_fact_chain
from tests.v2.storage.test_fact_repositories import _add, _date_range, _fact


COMPONENT_ID = "component-in-01"


@pytest.fixture
def chain(session):
    """head 库会话 + 已激活权威链；测试回滚。"""
    result = seed_valid_fact_chain(session, "rule-index", create_run=True)
    _seed_procedure_requirement(
        session,
        result,
        requirement_id="req",
        fact_type="vital_sign",
    )
    return result


def _published_requirement(requirement_id, rule_component_id, fact_type):
    return PublishedRequirement(
        requirement_id=requirement_id,
        rule_component_id=rule_component_id,
        fact_type=fact_type,
    )


def _publish_fact(
    session,
    chain,
    *,
    fact_id: str,
    fact_type: str,
    asserted_object: str,
    value: str,
    unit: str = "unitless",
    supported_requirement_ids: list[str] | None = None,
) -> ClinicalFactV2:
    """用真实发布路径发布一条事实（候选 + 事务门禁 + 事实），语义与门禁候选一致。"""
    candidate_id = f"{fact_id}-cand"
    gate_id = f"{fact_id}-gate"
    locator = session.get(EvidenceLocatorArtifactRecord, chain["locator_id"])
    assert locator is not None
    basis = AssertionBasis(
        asserted_object=asserted_object,
        assertion_text=locator.excerpt or asserted_object,
        locator_id=chain["locator_id"],
        source_text_sha256=locator.source_text_sha256,
    )
    if supported_requirement_ids is None:
        supported_requirement_ids = sorted(
            row.requirement_id
            for row in session.execute(select(EvidenceRequirementRecord)).scalars()
            if row.rule_set_id == chain["rule_set_id"]
            and row.rule_set_revision == 1
            and row.fact_type == fact_type
        )
    FactNormalizationCandidateRepository(session).create(
        chain["call_id"],
        ClinicalFactCandidateV2(
            candidate_id=candidate_id,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            fact_type=fact_type,
            supported_requirement_ids=supported_requirement_ids,
            polarity=FactPolarity.AFFIRMED,
            asserted_object=asserted_object,
            raw_value=value,
            canonical_value=value,
            unit=unit,
            date_range=_date_range(),
            record_time=NOW,
            locator_ids=[chain["locator_id"]],
            candidate_source_semantics="objective_result",
            assertion_basis=basis,
            model_uncertainty=0.01,
            created_at=NOW,
        ),
    )
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=gate_id,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            candidate_id=candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )
    return ClinicalFactV2Repository(session).create(
        _fact(
            {**chain, "gate_id": gate_id},
            fact_id=fact_id,
            gate_id=gate_id,
            fact_type=fact_type,
            supported_requirement_ids=supported_requirement_ids,
            asserted_object=asserted_object,
            value=value,
            unit=unit,
            source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
            assertion_basis=basis,
        )
    )


def _seed_component_requirement(
    session,
    chain,
    *,
    requirement_id: str,
    component_id: str,
    fact_type: str,
    title: str = "component",
) -> None:
    """向现有已发布组件追加一条经过正式合同编码的资料要求。"""
    assert component_id == COMPONENT_ID
    requirement = EvidenceRequirement(
        requirement_id=requirement_id,
        rule_component_id=component_id,
        procedure_catalog_item_id=None,
        fact_type=fact_type,
        due_stage=ReviewStage.SCREENING,
        description=title,
    )
    payload_json, payload_sha256 = encode_contract(requirement)
    _add(
        session,
        EvidenceRequirementRecord(
            rule_set_id=chain["rule_set_id"],
            rule_set_revision=1,
            requirement_id=requirement_id,
            rule_component_id=component_id,
            procedure_catalog_item_id=None,
            fact_type=fact_type,
            due_stage="screening",
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            created_at=NOW,
        ),
    )


def _seed_procedure_requirement(
    session, chain, *, requirement_id: str, fact_type: str
) -> None:
    """向链规则集写入一条流程必做项目录来源资料要求（不绑定组件）。"""
    requirement = EvidenceRequirement(
        requirement_id=requirement_id,
        rule_component_id=None,
        procedure_catalog_item_id=f"catalog-{requirement_id}",
        fact_type=fact_type,
        due_stage=ReviewStage.SCREENING,
        description=f"测试资料要求 {requirement_id}",
    )
    payload_json, payload_sha256 = encode_contract(requirement)
    _add(
        session,
        EvidenceRequirementRecord(
            rule_set_id=chain["rule_set_id"],
            rule_set_revision=1,
            requirement_id=requirement_id,
            rule_component_id=None,
            procedure_catalog_item_id=f"catalog-{requirement_id}",
            fact_type=fact_type,
            due_stage="screening",
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            created_at=NOW,
        ),
    )


def _seed_rule_set_revision2(session, chain) -> None:
    """追加同一规则集 revision 2 及一条同 ``fact_type`` 的要求（跨修订检验用）。"""
    revision_1 = get_rule_set(session, chain["rule_set_id"], 1)
    revision_2 = revision_1.model_copy(update={"revision": 2})
    save_rule_set(
        session,
        revision_2,
        procedure_requirements=[
            EvidenceRequirement(
                requirement_id="req-v2",
                rule_component_id=None,
                procedure_catalog_item_id="catalog-v2",
                fact_type="vital_sign",
                due_stage=ReviewStage.SCREENING,
                description="跨修订测试资料要求",
            )
        ],
    )


def _min_ids() -> dict[str, str]:
    """纯推导测试用的最小身份字典（不落库）。"""
    return {
        "run_id": "run",
        "gate_id": "gate",
        "project_id": "proj",
        "subject_id": "subj",
        "review_episode_id": "episode",
        "protocol_version_id": "proto",
        "rule_set_id": "rs-a",
        "rule_set_revision": 1,
        "evidence_snapshot_v2_id": "snap",
        "complete_processing_revision_id": "complete",
        "locator_id": "loc",
    }


# ------------------------------------------------------------- 合同层


def test_link_contract_rejects_inconsistent_parent_columns():
    """列漂移：父列判别不一致在合同层即拒绝（与数据库 CHECK 互为双保险）。"""
    base = dict(
        fact_id="f",
        rule_set_id="rs",
        rule_set_revision=1,
    )
    # rule_component 行携带 evidence_requirement_id -> 拒绝
    with pytest.raises(ValidationError, match="evidence_requirement_id"):
        FactRuleLink(
            link_id="l",
            target_kind="rule_component",
            target_id="comp-1",
            rule_component_id="comp-1",
            evidence_requirement_id="req-1",
            **base,
        )
    # rule_component 行 rule_component_id != target_id -> 拒绝
    with pytest.raises(ValidationError, match="rule_component_id"):
        FactRuleLink(
            link_id="l",
            target_kind="rule_component",
            target_id="comp-1",
            rule_component_id="comp-other",
            evidence_requirement_id=None,
            **base,
        )
    # evidence_requirement 行携带 rule_component_id -> 拒绝
    with pytest.raises(ValidationError, match="rule_component_id"):
        FactRuleLink(
            link_id="l",
            target_kind="evidence_requirement",
            target_id="req-1",
            evidence_requirement_id="req-1",
            rule_component_id="comp-1",
            **base,
        )
    # evidence_requirement 行 evidence_requirement_id != target_id -> 拒绝
    with pytest.raises(ValidationError, match="evidence_requirement_id"):
        FactRuleLink(
            link_id="l",
            target_kind="evidence_requirement",
            target_id="req-1",
            evidence_requirement_id="req-other",
            rule_component_id=None,
            **base,
        )


def test_link_id_is_deterministic_content_hash():
    a = fact_rule_link_id(
        fact_id="f",
        target_kind="evidence_requirement",
        rule_set_id="rs",
        rule_set_revision=1,
        target_id="req-1",
    )
    b = fact_rule_link_id(
        fact_id="f",
        target_kind="evidence_requirement",
        rule_set_id="rs",
        rule_set_revision=1,
        target_id="req-1",
    )
    c = fact_rule_link_id(
        fact_id="f",
        target_kind="evidence_requirement",
        rule_set_id="rs",
        rule_set_revision=1,
        target_id="req-2",
    )
    assert a == b
    assert a != c


def test_pure_derive_skips_facts_of_other_rule_set():
    facts = [_fact(_min_ids())]
    reqs = [_published_requirement("req-1", None, "vital_sign")]
    # 权威元组规则集（rs-a）与传入作用域（rs-b）不一致 -> 不参与推导
    derived = derive_fact_rule_links(
        facts, reqs, rule_set_id="rs-b", rule_set_revision=1
    )
    assert derived == []


def test_pure_derive_links_component_through_explicit_id_and_dedups():
    facts = [
        _fact(_min_ids()).model_copy(
            update={"supported_requirement_ids": ["r1", "r2", "r3"]}
        )
    ]
    reqs = [
        _published_requirement("r1", "comp-x", "vital_sign"),
        _published_requirement("r2", "comp-x", "vital_sign"),
        _published_requirement("r3", None, "blood_pressure"),
    ]
    derived = derive_fact_rule_links(
        facts, reqs, rule_set_id="rs-a", rule_set_revision=1
    )
    kinds = [(link.target_kind, link.target_id) for link in derived]
    # 两条同组件要求各建 er 链接，但共享组件只产生一条 rc 链接（去重）。
    assert ("evidence_requirement", "r1") in kinds
    assert ("evidence_requirement", "r2") in kinds
    assert kinds.count(("rule_component", "comp-x")) == 1
    # 流程来源（无组件）不捏造组件；fact_type 不同不建链接。
    assert ("rule_component", "r3") not in kinds
    assert ("evidence_requirement", "r3") not in kinds


def test_unbound_legacy_fact_links_nothing_even_when_fact_type_matches():
    fact = _fact(_min_ids())
    assert fact.supported_requirement_ids == []
    assert derive_fact_rule_links(
        [fact],
        [_published_requirement("req-1", "comp-x", "vital_sign")],
        rule_set_id="rs-a",
        rule_set_revision=1,
    ) == []


def test_exact_requirement_membership_excludes_same_type_sibling():
    fact = _fact(_min_ids()).model_copy(
        update={"supported_requirement_ids": ["req-a"]}
    )
    links = derive_fact_rule_links(
        [fact],
        [
            _published_requirement("req-a", "comp-a", "vital_sign"),
            _published_requirement("req-b", "comp-b", "vital_sign"),
        ],
        rule_set_id="rs-a",
        rule_set_revision=1,
    )
    assert {(link.target_kind, link.target_id) for link in links} == {
        ("evidence_requirement", "req-a"),
        ("rule_component", "comp-a"),
    }


# ------------------------------------------------------------- 模糊匹配禁令


def test_no_title_description_fuzzy_match(chain, session):
    """title/description 提到“血压”也不得把 blood_pressure 要求链到 vital_sign 事实。"""
    _seed_component_requirement(
        session,
        chain,
        requirement_id="req-bp",
        component_id=COMPONENT_ID,
        fact_type="blood_pressure",
        title="血压水平",
    )
    _publish_fact(
        session, chain, fact_id="f-vs", fact_type="vital_sign",
        asserted_object="血压", value="120/80",
    )
    _publish_fact(
        session, chain, fact_id="f-bp", fact_type="blood_pressure",
        asserted_object="血压", value="150/95",
    )
    repo = FactRuleLinkV2Repository(session)
    links = repo.rebuild_for_episode(chain["review_episode_id"])
    by_fact: dict[str, set[tuple[str, str]]] = {}
    for link in links:
        by_fact.setdefault(link.fact_id, set()).add(
            (link.target_kind, link.target_id)
        )
    # vital_sign 事实只链到流程要求 req（vital_sign），不因描述提到血压而链到 req-bp。
    assert by_fact["f-vs"] == {("evidence_requirement", "req")}
    # blood_pressure 事实只链到 req-bp 及其组件 comp-bp，不链到 req。
    assert by_fact["f-bp"] == {
        ("evidence_requirement", "req-bp"),
        ("rule_component", COMPONENT_ID),
    }


# ------------------------------------------------------------- 组件只经显式身份


def test_procedure_only_requirement_invents_no_component(chain, session):
    """流程必做项目录来源要求（无组件）不产生任何组件链接。"""
    _publish_fact(
        session, chain, fact_id="f-vs", fact_type="vital_sign",
        asserted_object="血压", value="120/80",
    )
    repo = FactRuleLinkV2Repository(session)
    links = repo.rebuild_for_episode(chain["review_episode_id"])
    assert [link.target_kind for link in links] == ["evidence_requirement"]
    assert all(link.rule_component_id is None for link in links)
    component_rows = session.execute(
        select(FactRuleLinkV2Record).where(
            FactRuleLinkV2Record.target_kind == "rule_component"
        )
    ).scalars().all()
    assert component_rows == []


def test_component_owned_requirement_links_component_through_explicit_id(
    chain, session,
):
    _seed_component_requirement(
        session, chain, requirement_id="req-vs", component_id=COMPONENT_ID,
        fact_type="vital_sign",
    )
    _publish_fact(
        session, chain, fact_id="f-vs", fact_type="vital_sign",
        asserted_object="血压", value="120/80",
    )
    repo = FactRuleLinkV2Repository(session)
    links = repo.rebuild_for_episode(chain["review_episode_id"])
    component_links = [l for l in links if l.target_kind == "rule_component"]
    assert len(component_links) == 1
    component = component_links[0]
    assert component.target_id == COMPONENT_ID
    assert component.rule_component_id == COMPONENT_ID
    assert component.evidence_requirement_id is None


# ------------------------------------------------------------- 跨修订


def test_no_cross_rule_revision_link(chain, session):
    """事实在 revision 1 权威下，绝不链到同规则集 revision 2 的要求。"""
    _seed_rule_set_revision2(session, chain)
    _publish_fact(
        session, chain, fact_id="f-vs", fact_type="vital_sign",
        asserted_object="血压", value="120/80",
    )
    repo = FactRuleLinkV2Repository(session)
    links = repo.rebuild_for_episode(chain["review_episode_id"])
    # 只链到 revision 1 的流程要求 req；revision 2 的 req-v2（同 fact_type）不参与。
    assert sorted(l.target_id for l in links) == ["req"]
    assert repo.list_for_rule_set(chain["rule_set_id"], 2) == []


def test_cross_rule_revision_link_row_is_drift(chain, session):
    """手工插入格式正确但指向 revision 2 的链接行 -> 读取/重建都拒绝。"""
    _seed_rule_set_revision2(session, chain)
    _publish_fact(
        session, chain, fact_id="f-vs", fact_type="vital_sign",
        asserted_object="血压", value="120/80",
    )
    repo = FactRuleLinkV2Repository(session)
    repo.rebuild_for_episode(chain["review_episode_id"])
    # 指向 revision 2 的 well-formed 链接（CHECK 与 FK 都满足，link_id 正确）
    drift_link_id = fact_rule_link_id(
        fact_id="f-vs",
        target_kind="evidence_requirement",
        rule_set_id=chain["rule_set_id"],
        rule_set_revision=2,
        target_id="req-v2",
    )
    _add(
        session,
        FactRuleLinkV2Record(
            link_id=drift_link_id,
            fact_id="f-vs",
            target_kind="evidence_requirement",
            rule_set_id=chain["rule_set_id"],
            rule_set_revision=2,
            target_id="req-v2",
            evidence_requirement_id="req-v2",
        ),
    )
    with pytest.raises(FactRuleLinkDriftError, match="跨修订"):
        repo.get(drift_link_id)
    with pytest.raises(FactRuleLinkDriftError, match="跨修订"):
        repo.rebuild_for_episode(chain["review_episode_id"])


# ------------------------------------------------------------- 重建等价


def test_rebuild_is_idempotent_and_equivalent(chain, session):
    """二次重建无差异；删除一行后重建可自愈；结果稳定排序、无重复。"""
    _seed_component_requirement(
        session, chain, requirement_id="req-vs", component_id=COMPONENT_ID,
        fact_type="vital_sign",
    )
    _publish_fact(
        session, chain, fact_id="f-vs", fact_type="vital_sign",
        asserted_object="血压", value="120/80",
    )
    repo = FactRuleLinkV2Repository(session)
    first = repo.rebuild_for_episode(chain["review_episode_id"])
    # 期望：er req（流程）+ er req-vs（组件）+ rc 组件 = 3 条
    assert len(first) == 3
    first_ids = [link.link_id for link in first]
    rows = session.execute(select(FactRuleLinkV2Record)).scalars().all()
    assert len(rows) == 3

    second = repo.rebuild_for_episode(chain["review_episode_id"])
    assert [link.link_id for link in second] == first_ids
    rows = session.execute(select(FactRuleLinkV2Record)).scalars().all()
    assert len(rows) == 3  # 幂等：无重复

    # 删除一行组件链接后重建 -> 自愈恢复，仍等价。
    row_to_delete = session.execute(
        select(FactRuleLinkV2Record).where(
            FactRuleLinkV2Record.target_kind == "rule_component"
        )
    ).scalar_one()
    session.delete(row_to_delete)
    session.flush()
    restored = repo.rebuild_for_episode(chain["review_episode_id"])
    assert [link.link_id for link in restored] == first_ids

    # 再次重建仍无变化。
    again = repo.rebuild_for_episode(chain["review_episode_id"])
    assert [link.link_id for link in again] == first_ids


def test_rebuild_for_authority_does_not_mutate_other_authority_links(chain, session):
    """按权威元组重建时，不得清扫另一受试者/审核节点的已验证索引。"""
    other = seed_valid_fact_chain(
        session, "rule-index-other", fixture_index=1, create_run=True
    )
    _seed_procedure_requirement(
        session, other, requirement_id="req-other", fact_type="vital_sign"
    )
    first_fact = _publish_fact(
        session, chain, fact_id="f-authority-a", fact_type="vital_sign",
        asserted_object="血压", value="120/80",
    )
    second_fact = _publish_fact(
        session, other, fact_id="f-authority-b", fact_type="vital_sign",
        asserted_object="血压", value="130/85",
    )
    repo = FactRuleLinkV2Repository(session)
    first_links = repo.rebuild_for_authority(first_fact.authority)
    second_links = repo.rebuild_for_authority(second_fact.authority)
    second_ids = {link.link_id for link in second_links}

    first_row = session.get(FactRuleLinkV2Record, first_links[0].link_id)
    assert first_row is not None
    session.delete(first_row)
    session.flush()
    rebuilt = repo.rebuild_for_authority(first_fact.authority)

    assert {link.link_id for link in rebuilt} == {link.link_id for link in first_links}
    assert second_ids <= {
        row.link_id
        for row in session.execute(select(FactRuleLinkV2Record)).scalars().all()
    }


def test_rebuild_requires_published_facts(chain, session):
    repo = FactRuleLinkV2Repository(session)
    with pytest.raises(FactRuleIndexError, match="没有已发布事实"):
        repo.rebuild_for_episode(chain["review_episode_id"])


# ------------------------------------------------------------- 双向查询


def test_bidirectional_queries(chain, session):
    _seed_component_requirement(
        session, chain, requirement_id="req-vs", component_id=COMPONENT_ID,
        fact_type="vital_sign",
    )
    _publish_fact(
        session, chain, fact_id="f-vs", fact_type="vital_sign",
        asserted_object="血压", value="120/80",
    )
    repo = FactRuleLinkV2Repository(session)
    repo.rebuild_for_episode(chain["review_episode_id"])

    by_fact = repo.list_for_fact("f-vs")
    assert sorted((l.target_kind, l.target_id) for l in by_fact) == [
        ("evidence_requirement", "req"),
        ("evidence_requirement", "req-vs"),
        ("rule_component", COMPONENT_ID),
    ]
    req_facts = repo.list_facts_for_requirement(
        chain["rule_set_id"], 1, "req"
    )
    assert [l.fact_id for l in req_facts] == ["f-vs"]
    comp_facts = repo.list_facts_for_component(
        chain["rule_set_id"], 1, COMPONENT_ID
    )
    assert [l.fact_id for l in comp_facts] == ["f-vs"]
    # 不存在的要求/组件 -> 空列表
    assert repo.list_facts_for_requirement(chain["rule_set_id"], 1, "nope") == []
    assert repo.list_facts_for_component(chain["rule_set_id"], 1, "nope") == []
    assert len(repo.list_for_rule_set(chain["rule_set_id"], 1)) == 3


# ------------------------------------------------------------- 漂移拒绝


def test_link_id_payload_drift_rejected_on_read_and_rebuild(chain, session):
    """列被改而不更新 link_id -> 内容哈希失配，读取与重建拒绝（payload 漂移）。"""
    _seed_procedure_requirement(
        session, chain, requirement_id="req-bp", fact_type="blood_pressure"
    )
    _publish_fact(
        session, chain, fact_id="f-vs", fact_type="vital_sign",
        asserted_object="血压", value="120/80",
    )
    repo = FactRuleLinkV2Repository(session)
    repo.rebuild_for_episode(chain["review_episode_id"])
    row = session.execute(select(FactRuleLinkV2Record)).scalar_one()
    original_id = row.link_id
    # 把 fact f-vs 的 er req 链接改指向 blood_pressure 要求（CHECK/FK 满足，
    # 但 link_id 未更新 -> 内容哈希失配）。
    session.execute(
        update(FactRuleLinkV2Record)
        .where(FactRuleLinkV2Record.link_id == original_id)
        .values(target_id="req-bp", evidence_requirement_id="req-bp")
    )
    session.expire_all()
    with pytest.raises(FactRuleLinkDriftError, match="link_id"):
        repo.get(original_id)
    with pytest.raises(FactRuleLinkDriftError, match="link_id"):
        repo.rebuild_for_episode(chain["review_episode_id"])


def test_link_parent_drift_rejected(chain, session):
    """well-formed 但父实体/父要求不再可推导（fact_type 不匹配）-> 拒绝。"""
    _seed_component_requirement(
        session, chain, requirement_id="req-bp", component_id=COMPONENT_ID,
        fact_type="blood_pressure",
    )
    _publish_fact(
        session, chain, fact_id="f-vs", fact_type="vital_sign",
        asserted_object="血压", value="120/80",
    )
    repo = FactRuleLinkV2Repository(session)
    repo.rebuild_for_episode(chain["review_episode_id"])

    # 手工插入 well-formed 组件链接：f-vs(vital_sign) -> 仅由
    # blood_pressure 资料要求支持的组件。
    # link_id 正确、CHECK/FK 满足，但父要求 fact_type 与事实不匹配，不可推导。
    drift_link_id = fact_rule_link_id(
        fact_id="f-vs",
        target_kind="rule_component",
        rule_set_id=chain["rule_set_id"],
        rule_set_revision=1,
        target_id=COMPONENT_ID,
    )
    _add(
        session,
        FactRuleLinkV2Record(
            link_id=drift_link_id,
            fact_id="f-vs",
            target_kind="rule_component",
            rule_set_id=chain["rule_set_id"],
            rule_set_revision=1,
            target_id=COMPONENT_ID,
            rule_component_id=COMPONENT_ID,
        ),
    )
    with pytest.raises(FactRuleLinkDriftError, match="推导"):
        repo.get(drift_link_id)
    with pytest.raises(FactRuleLinkDriftError, match="推导"):
        repo.rebuild_for_episode(chain["review_episode_id"])


def test_roundtrip_get_preserves_link_contract(chain, session):
    """正常链接读取还原完整合同，父列与 link_id 一致。"""
    _seed_component_requirement(
        session, chain, requirement_id="req-vs", component_id=COMPONENT_ID,
        fact_type="vital_sign",
    )
    _publish_fact(
        session, chain, fact_id="f-vs", fact_type="vital_sign",
        asserted_object="血压", value="120/80",
    )
    repo = FactRuleLinkV2Repository(session)
    links = repo.rebuild_for_episode(chain["review_episode_id"])
    for link in links:
        got = repo.get(link.link_id)
        assert got == link
        assert got.link_id == fact_rule_link_id(
            fact_id=got.fact_id,
            target_kind=got.target_kind,
            rule_set_id=got.rule_set_id,
            rule_set_revision=got.rule_set_revision,
            target_id=got.target_id,
        )
