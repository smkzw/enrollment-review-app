"""Bounded top-level completion: never rewrite existing model observations."""

import copy
import json

from jsonschema import Draft202012Validator


def missing_fields_schema(value: dict, schema: dict) -> dict:
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(value))
    if not errors or any(e.validator != "required" or e.absolute_path for e in errors):
        raise ValueError("Only missing top-level required fields can be completed")
    missing = [k for k in schema.get("required", []) if k not in value]
    properties = schema.get("properties", {})
    if not missing or any(k not in properties for k in missing):
        raise ValueError("Missing fields must have an explicit contract")
    result = {"type": "object", "properties": {k: copy.deepcopy(properties[k]) for k in missing},
              "required": missing, "additionalProperties": False}
    if "$defs" in schema:
        result["$defs"] = copy.deepcopy(schema["$defs"])
    return result


def completion_messages(messages: list, value: dict, schema: dict) -> list:
    patch_schema = missing_fields_schema(value, schema)
    return [*copy.deepcopy(messages), {"role": "assistant", "content": json.dumps(value, ensure_ascii=False)},
            {"role": "user", "content":
             "仅补答下列缺失字段，返回一个JSON对象。已给出的字段禁止重复或修改。"
             "仍须依据原始输入判断未解决问题，不能因为字段缺失就默认无问题；"
             "运行标识沿用原输入。不要重写规则或扩展本次范围。补答结构：\n"
             + json.dumps(patch_schema, ensure_ascii=False)}]


def merge_completion(value: dict, patch: dict, schema: dict) -> dict:
    patch_schema = missing_fields_schema(value, schema)
    Draft202012Validator(patch_schema).validate(patch)
    result = {**copy.deepcopy(value), **copy.deepcopy(patch)}
    Draft202012Validator(schema).validate(result)
    return result
