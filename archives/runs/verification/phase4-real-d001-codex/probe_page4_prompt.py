from __future__ import annotations

import base64
import json
import os
import urllib.request
from pathlib import Path


IMAGE = Path(
    os.environ.get(
        "OCR_PROBE_IMAGE",
        "/tmp/enrollment-review-phase4-real-d001-minimax-20260822/artifacts/page_image/"
        "06c4b5668a7bf1ebe42b6f5302469be59c94d1b639078dfa8a32dbfce44a5736",
    )
)
OUTPUT = Path(
    os.environ.get(
        "OCR_PROBE_OUTPUT",
        Path(__file__).with_name("page4-enhanced-prompt-response.json"),
    )
)
PROMPT = (
    "请严格逐字转写整张病历页面，自上而下按版面顺序输出全部文字。"
    "不得忽略横线附近、黄色高亮、小字号、页眉页脚，以及诊断字段前后的文字；"
    "特别保留否定词、日期、药品名、剂量和实际是否使用等原文。"
    "不要总结、改写或合并句子，只返回完整转写文字。"
)


def main() -> None:
    request_body = {
        "model": "GLM-OCR-bf16",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + base64.b64encode(IMAGE.read_bytes()).decode("ascii")
                        },
                    },
                ],
            }
        ],
        "temperature": 0,
    }
    request = urllib.request.Request(
        "http://127.0.0.1:8001/v1/chat/completions",
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=900) as response:
        OUTPUT.write_bytes(response.read())
    print(OUTPUT)


if __name__ == "__main__":
    main()
