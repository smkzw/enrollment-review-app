"""One published revision supplies both official and cross-chapter reading input."""
from sqlalchemy.orm import Session

from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.rules import RuleSet
from app.projections.clause_pack import project_clause_pack
from app.storage.control_catalog_repository import ControlCatalogPublicationRepository


def project_published_clause_pack(session: Session, rule_set: RuleSet) -> ClausePack:
    publication = ControlCatalogPublicationRepository(session).get_for_rule_set(
        rule_set.rule_set_id, rule_set.revision,
    )
    return project_clause_pack(rule_set, control_publication=publication)
