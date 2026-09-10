"""Reversible, call-local reference compression; clinical text is never rewritten."""

from dataclasses import dataclass


_REFERENCE_FIELDS = {
    "locator_id": "locator", "locator_ids": "locator",
    "affected_locator_ids": "locator",
    "source_observation_ref": "observation", "source_observation_refs": "observation",
    "requirement_id": "requirement", "supported_requirement_ids": "requirement",
    "affected_requirement_ids": "requirement",
}


@dataclass(frozen=True)
class NormalizerReferenceAliases:
    aliases: dict[str, dict[str, str]]

    @classmethod
    def from_payload(cls, payload):
        identities = {kind: set() for kind in set(_REFERENCE_FIELDS.values())}

        def collect(value):
            if isinstance(value, list):
                for item in value:
                    collect(item)
            elif isinstance(value, dict):
                for field, item in value.items():
                    if field in _REFERENCE_FIELDS:
                        values = item if isinstance(item, list) else [item]
                        identities[_REFERENCE_FIELDS[field]].update(
                            identity for identity in values if isinstance(identity, str))
                    else:
                        collect(item)

        collect(payload)
        all_ids = set().union(*identities.values())
        prefix = "@"
        while any(identity.startswith(prefix) for identity in all_ids):
            prefix += "@"
        return cls({kind: {identity: f"{prefix}{kind[0].upper()}{index}"
                           for index, identity in enumerate(sorted(values), 1)}
                    for kind, values in identities.items()})

    def transform(self, payload, *, expand=False):
        mappings = ({kind: {alias: identity for identity, alias in values.items()}
                     for kind, values in self.aliases.items()} if expand else self.aliases)

        def visit(value):
            if isinstance(value, list):
                return [visit(item) for item in value]
            if not isinstance(value, dict):
                return value
            result = {}
            for field, item in value.items():
                if field not in _REFERENCE_FIELDS:
                    result[field] = visit(item)
                    continue
                mapping = mappings[_REFERENCE_FIELDS[field]]
                def replace(identity):
                    return mapping.get(identity, identity) if isinstance(identity, str) else identity
                result[field] = ([replace(identity) for identity in item]
                                 if isinstance(item, list) else replace(item))
            return result

        return visit(payload)
