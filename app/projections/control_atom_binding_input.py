"""Project control identities; auxiliary checks are opt-in, never new layers."""
from app.domain.contracts.control_atom_binding import FrozenControlAtomIdentity
from app.domain.contracts.control_catalog_publication import ControlCatalogPublication
from app.domain.publication import canonical_hash


def project_control_atom_identities(
    publication: ControlCatalogPublication, *, include_repeat_triggers: bool = False,
) -> tuple[FrozenControlAtomIdentity, ...]:
    publication = ControlCatalogPublication.model_validate(publication.model_dump(mode="json"))
    catalog_hash = canonical_hash(publication.catalog.model_dump(mode="json"))
    result = []
    seen = set()
    for control in publication.catalog.controls:
        if control.obligation_expression is None:
            raise ValueError("补充控制尚未保留完整条件结构，不能生成原子证明身份")
        expressions = [(layer, None, getattr(control, f"{layer}_expression"))
                       for layer in ("applicability", "trigger", "obligation", "exception")]
        if include_repeat_triggers:
            expressions.extend(("repeat_trigger", item.condition_id, item.expression)
                               for item in control.repeat_trigger_conditions)
        for layer, condition_id, expression in expressions:
            if expression is None:
                continue
            for group_index, group in enumerate(expression.groups):
                for atom_index, atom in enumerate(group.atoms):
                    atom_id = atom.obligation_id if layer == "obligation" else atom.condition_atom_id
                    key = (control.protocol_control_id, atom_id)
                    if key in seen:
                        raise ValueError("同一补充控制的原子身份重复，不能合并来源")
                    seen.add(key)
                    material = {
                        "publication_id": publication.publication_id,
                        "catalog_sha256": catalog_hash,
                        "protocol_control_id": control.protocol_control_id,
                        "layer": layer,
                        "group_index": group_index,
                        "atom_index": atom_index,
                        "atom_id": atom_id,
                        "atom": atom.model_dump(mode="json"),
                    }
                    if condition_id is not None:
                        material["condition_id"] = condition_id
                    result.append(FrozenControlAtomIdentity(
                        **material,
                        identity_sha256=canonical_hash({
                            "identity": "control_atom_binding/v1", **material,
                        }),
                    ))
    return tuple(result)


def verify_control_atom_identity(
    publication: ControlCatalogPublication,
    identity: FrozenControlAtomIdentity,
) -> FrozenControlAtomIdentity:
    """A self-consistent hash is insufficient; resolve against the full publication."""
    identity = FrozenControlAtomIdentity.model_validate(identity.model_dump(mode="json"))
    expected = next((
        item for item in project_control_atom_identities(publication, include_repeat_triggers=True)
        if item.protocol_control_id == identity.protocol_control_id
        and item.atom_id == identity.atom_id
    ), None)
    if expected is None or expected != identity:
        raise ValueError("控制原子证明身份与已发布目录不一致")
    return expected
