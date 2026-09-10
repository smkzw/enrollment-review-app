"""Measure the native protocol transport without changing its messages or schema."""

import argparse
import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace

from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport
from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_harness import PageReaderRoute
from scripts.qwen_platform_measurement import MeasuredCompletion, save
from scripts.run_frozen_protocol_comparison import execute


class StreamingClient:
    def __init__(self, meter, route, request_lock):
        self.meter, self.route = meter, route
        self.request_lock = request_lock
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        messages = kwargs.pop("messages")
        budget = kwargs.pop("max_tokens")
        kwargs.pop("model")
        kwargs.pop("reasoning_effort", None)
        kwargs.update(kwargs.pop("extra_body", {}))
        # Product segmentation uses threads; all clients share one local slot.
        with self.request_lock:
            result = asyncio.run(self.meter(self.route, messages, budget, kwargs))
        return SimpleNamespace(
            id=result.response_id, model=result.response_model,
            usage=SimpleNamespace(**result.usage),
            choices=[SimpleNamespace(finish_reason=result.finish_reason,
                message=SimpleNamespace(content=result.text, reasoning_content=""))],
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", choices=["xhigh", "medium", "low"], default="xhigh")
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--formal-wire", action="store_true",
                        help="Isolated comparison using the existing formal product contract; defaults unchanged")
    args = parser.parse_args()
    output = args.run_dir / "measurements"
    output.mkdir(exist_ok=False)
    save(output / "wire-contract.json", {
        "compact_wire_override": False if args.formal_wire else None,
        "decode_time_scope": True,
        "bounded_batch_context": True,
        "omlx_pattern_projection": args.provider == "omlx",
        "diagnostic_only": args.formal_wire,
        "clinical_acceptance": False,
    })
    route = PageReaderRoute(PageReviewLane.MAIN_A, args.provider, args.url,
                            "local-benchmark", args.model, args.effort, 131072, 1)
    meter = MeasuredCompletion(output, args.tokenizer)
    request_lock = threading.Lock()

    def factory():
        return DeepSeekProtocolAgentTransport(
            client=StreamingClient(meter, route, request_lock), backend=args.provider,
            base_url=args.url, model=args.model, reasoning_effort=args.effort,
            max_tokens=131072, provider_defaults=True,
            compact_wire=False if args.formal_wire else None,
        )

    execute(run_dir=args.run_dir, backend=args.provider, model=args.model,
            reasoning_effort=args.effort, max_tokens=131072, provider_defaults=True,
            transport=factory(), transport_factory=factory)


if __name__ == "__main__":
    main()
