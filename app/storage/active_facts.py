"""Current published facts for one immutable authority, independent of run."""

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.domain.contracts.facts import ClinicalFactV2, FactAuthority
from app.storage.fact_correction_repository import FactCorrectionRepository
from app.storage.fact_repositories import ClinicalFactV2Repository
from app.storage.repositories import InvalidReferenceError


def current_fact_heads(
    session: Session,
    authority: FactAuthority,
    *,
    facts: Sequence[ClinicalFactV2] | None = None,
    exclude_fact_ids: set[str] | None = None,
) -> list[ClinicalFactV2]:
    """Select validated repository records; never infer replacement from run age."""
    if facts is None:
        facts = ClinicalFactV2Repository(session).list_by_episode(
            authority.review_episode_id
        )
    excluded = FactCorrectionRepository(session).superseded_entity_ids(authority)
    excluded.update(exclude_fact_ids or ())
    heads: dict[str, ClinicalFactV2] = {}
    for fact in facts:
        if fact.authority != authority:
            continue
        current = heads.get(fact.stable_identity)
        if current is None or fact.revision > current.revision:
            heads[fact.stable_identity] = fact
        elif fact.revision == current.revision and fact.fact_id != current.fact_id:
            raise InvalidReferenceError("同一事实存在相同修订号的不同记录，须先核对来源。")
    # Select the head before excluding it: removal must not resurrect an older value.
    return sorted(
        (fact for fact in heads.values() if fact.fact_id not in excluded),
        key=lambda fact: (fact.revision, fact.fact_id),
    )
