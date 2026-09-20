"""Constrain explicit source identities without interpreting clinical content."""

from collections.abc import Iterator, Mapping, Sequence


_SOURCE_ARRAYS = frozenset({"source_span_ids", "source_refs"})


def constrain_source_schema(schema: dict, allowed: Sequence[str]) -> dict:
    """Scope all declared source fields in a fresh generation schema."""
    if not allowed:
        return schema

    def visit(value):
        if isinstance(value, dict):
            for name, field in value.get("properties", {}).items():
                if name in _SOURCE_ARRAYS and field.get("type") == "array":
                    field["items"]["enum"] = list(allowed)
                elif name == "source_span_id" and field.get("type") == "string":
                    field["enum"] = list(allowed)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    return schema


def source_references(value: object) -> Iterator[str]:
    """Read named provenance fields, never excerpts or document position labels."""
    if isinstance(value, Mapping):
        for name, child in value.items():
            if name in _SOURCE_ARRAYS:
                if isinstance(child, (list, tuple)):
                    yield from (item for item in child if isinstance(item, str))
            elif name == "source_span_id" and isinstance(child, str):
                yield child
            else:
                yield from source_references(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from source_references(child)
