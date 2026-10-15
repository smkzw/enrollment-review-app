"""Generation-time projection of existing atomic predicate requirements."""


def predicate_generation_schema(schema, comparator_schema):
    properties = schema["properties"]
    value_types = properties["value"]["anyOf"]
    scalar_types = [item for item in value_types if item.get("type") not in {"array", "null"}]
    array_type = next(item for item in value_types if item.get("type") == "array")
    scalar_comparators = [item for item in comparator_schema["enum"] if item not in {"exists", "in", "not_in"}]
    branches = []
    for source_field, source_schema in (
        ("source_clause", {"type": "string", "minLength": 1}),
        ("source_clauses", {"type": "array", "minItems": 1,
                            "items": {"type": "string", "minLength": 1}}),
    ):
        other_field = "source_clauses" if source_field == "source_clause" else "source_clause"
        other_schema = ({"type": "array", "maxItems": 0} if other_field == "source_clauses"
                        else {"type": "null"})
        for comparators, value_schema, require_value in (
            (["exists"], {"type": "null"}, False),
            (["in", "not_in"], array_type, True),
            (scalar_comparators, {"anyOf": scalar_types}, True),
        ):
            # Keep complete object branches: native decoders may ignore anyOf siblings.
            branches.append({
                **schema,
                "required": [*schema["required"], source_field, *(["value"] if require_value else [])],
                "properties": {**properties, source_field: source_schema, other_field: other_schema,
                               "comparator": {"type": "string", "enum": comparators}, "value": value_schema},
            })
    return {"anyOf": branches}
