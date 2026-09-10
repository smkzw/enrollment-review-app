import base64
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from app.services.page_request_receipt import store_page_request


class Store:
    def __init__(self):
        self.data = {("page_image", hashlib.sha256(b"page").hexdigest()): b"page"}

    def read_by_sha(self, kind, digest):
        return self.data[kind, digest]

    def put(self, kind, value):
        digest = hashlib.sha256(value).hexdigest()
        self.data[kind, digest] = value
        return SimpleNamespace(sha256=digest)


def test_prompt_receipt_preserves_exact_text_and_image_without_mutating_messages():
    store = Store()
    route = SimpleNamespace(provider="test", model="reader", reasoning_effort="high")
    url = "data:image/png;base64," + base64.b64encode(b"page").decode()
    messages = [{"role": "system", "content": "原始提示\n保留空格  "},
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": url, "detail": "high"}},
                                              {"type": "text", "text": '{"value":0}'}]}]
    before = copy.deepcopy(messages)
    digest = store_page_request(store, route, messages, 12000)
    saved = json.loads(store.read_by_sha("raw_request", digest))
    assert messages == before
    assert saved["messages"][0] == messages[0]
    image = saved["messages"][1]["content"][0]["image_url"]
    assert image["detail"] == "high"
    ref = image["url"]
    rebuilt = ref["data_prefix"] + "," + base64.b64encode(store.read_by_sha("page_image", ref["page_image_sha256"])).decode()
    assert rebuilt == url
    assert store_page_request(store, route, messages, 12000) == digest
    assert store_page_request(store, route, messages, 24000) != digest
    messages[0]["content"] += "修订"
    assert store_page_request(store, route, messages, 12000) != digest


def test_missing_source_image_rejects_receipt():
    route = SimpleNamespace(provider="test", model="reader", reasoning_effort="high")
    messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {
        "url": "data:image/png;base64," + base64.b64encode(b"missing").decode(),
    }}]}]
    with pytest.raises(KeyError):
        store_page_request(Store(), route, messages, 12000)
