"""Read-only control proof input from the existing authoritative fact snapshot."""
from sqlalchemy.orm import Session

from app.domain.contracts.control_atom_binding import (
    ControlBindingFrozenInput,
    control_binding_input_hash,
)
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.services.predicate_binding_input import build_predicate_binding_frozen_input
from app.storage.control_catalog_repository import ControlCatalogPublicationRepository


def build_control_binding_frozen_input(
    session: Session, review_episode_id: str,
) -> ControlBindingFrozenInput:
    evidence = build_predicate_binding_frozen_input(session, review_episode_id)
    publication = ControlCatalogPublicationRepository(session).get_for_rule_set(
        evidence.rule_set_id, evidence.rule_set_revision,
    )
    if publication is None:
        raise ValueError("当前方案修订尚未发布补充控制，不能创建对应证明输入")
    project_control_atom_identities(publication)
    return ControlBindingFrozenInput(
        publication=publication,
        evidence_input=evidence,
        frozen_input_sha256=control_binding_input_hash(publication, evidence),
    )
