"""Persist exact prompt text with content-addressed image references."""

import base64
import copy
import hashlib
import json


def store_page_request(artifact_store, route, messages, max_tokens):
    frozen = copy.deepcopy(messages)
    for message in frozen:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if part.get("type") != "image_url":
                continue
            image = part["image_url"]
            prefix, encoded = image["url"].split(",", 1)
            if not prefix.startswith("data:image/") or not prefix.endswith(";base64"):
                raise ValueError("页请求必须使用可复验的内嵌原图")
            image_bytes = base64.b64decode(encoded, validate=True)
            digest = hashlib.sha256(image_bytes).hexdigest()
            if artifact_store.read_by_sha("page_image", digest) != image_bytes:
                raise ValueError("页请求图像与已保存原图不一致")
            image["url"] = {"data_prefix": prefix, "page_image_sha256": digest}
    payload = {"receipt_version": "page-request/v1", "provider": route.provider,
               "model": route.model, "reasoning_effort": route.reasoning_effort,
               "max_tokens": max_tokens, "messages": frozen}
    return artifact_store.put("raw_request", json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).sha256
