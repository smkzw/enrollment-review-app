"""Keep unsupported nonblank regex out of oMLX decoding, not validation."""

from copy import deepcopy


def decoding_response_format(response_format: dict) -> dict:
    result = deepcopy(response_format)

    def visit(value):
        if isinstance(value, dict):
            if value.get("type") == "string" and value.get("pattern") in {
                r"\S", r"^[\s\S]*\S[\s\S]*$",
            }:
                # xgrammar pattern compilation can bypass JSON string escaping.
                # Product parsing retains the authoritative nonblank check.
                del value["pattern"]
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(result.get("json_schema", {}).get("schema"))
    return result
