"""MTPLX decoding subset; authoritative conditional checks stay in product validation."""
from copy import deepcopy


def decoding_response_format(response_format: dict) -> dict:
    result = deepcopy(response_format)

    def visit(schema):
        if not isinstance(schema, dict):
            return
        for keyword in ("if", "then", "else"):
            schema.pop(keyword, None)
        for keyword in ("properties", "$defs", "definitions", "patternProperties", "dependentSchemas"):
            children = schema.get(keyword)
            if isinstance(children, dict):
                for child in children.values():
                    visit(child)
        for keyword in ("items", "additionalProperties", "contains", "propertyNames", "not", "unevaluatedProperties"):
            visit(schema.get(keyword))
        for keyword in ("allOf", "anyOf", "oneOf", "prefixItems"):
            children = schema.get(keyword)
            if isinstance(children, list):
                for child in children:
                    visit(child)

    visit(result.get("json_schema", {}).get("schema"))
    return result
