"""诊断：重放 SAR 方案解构批4，抓取模型原始输出（不落草稿、不改产品行为）。

用途：定位 IN-04 observation_policy 校验失败的真实模型输出形态。
批次1-3从既有文件缓存重放（不重复调用）；批4起每次响应原文写入 /tmp。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from app.config import ENROLLMENT_ENV_FILE_VAR  # noqa: E402

os.environ.setdefault(ENROLLMENT_ENV_FILE_VAR, str(ROOT / ".env"))

import sqlalchemy as sa  # noqa: E402

from app.agents.protocol_deconstructor import (  # noqa: E402
    ProtocolDeconstructorRunner,
    ProtocolSemanticBatchCache,
)
from app.domain.contracts.agent_io import (  # noqa: E402
    ProtocolDeconstructionInput,
    ProtocolDeconstructionDraft,
)
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan  # noqa: E402
from app.domain.contracts.protocol_metadata import PhaseProjection  # noqa: E402
from app.domain.contracts.agents import PromptVersion  # noqa: E402
from app.agents.protocol_deconstructor import (  # noqa: E402
    protocol_prompt_template_sha256,
    AgentNode,
)
from app.agents.protocol_semantic_transport import (  # noqa: E402
    OpenAICompatibleProtocolAgentTransport,
)
from app.services.protocol_deconstruction_executor import (  # noqa: E402
    _ProtocolSemanticBatchFileCache,
)
from app.storage.config import resolve_data_paths  # noqa: E402

JOB_ID = "769ae98f76b4450ca810fbbdd9f518d8"
DUMP = Path("/tmp/sar-batch4-responses.jsonl")


class DumpingTransport:
    def __init__(self, inner):
        self._inner = inner
        self.calls = 0

    def start(self, *, prompt, output_kind="semantic_candidate"):
        response = self._inner.start(prompt=prompt, output_kind=output_kind)
        self._record("start", prompt, response.text)
        return response

    def continue_session(self, *, session_id, prompt, output_kind="semantic_candidate"):
        response = self._inner.continue_session(
            session_id=session_id, prompt=prompt, output_kind=output_kind
        )
        self._record("continue", prompt, response.text)
        return response

    def _record(self, kind, prompt, text):
        self.calls += 1
        with DUMP.open("a") as stream:
            stream.write(
                json.dumps(
                    {
                        "call": self.calls,
                        "kind": kind,
                        "prompt_tail": prompt[-600:],
                        "response_len": len(text),
                        "response_full": text,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    def __getattr__(self, name):
        return getattr(self._inner, name)


def merged_payload(job_id: str) -> dict:
    engine = sa.create_engine("sqlite:///data_v2/enrollment-review-v2.sqlite3")
    with engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT payload_json FROM jobs WHERE job_id=:j"), {"j": job_id}
        ).fetchone()
        merged = json.loads(row[0])
        # 逐步骤检查点合并（与工作台 _merged_payload 一序）
        rows = conn.execute(
            sa.text(
                "SELECT step_id, payload_json FROM job_checkpoints "
                "WHERE job_id=:j ORDER BY created_at"
            ),
            {"j": job_id},
        ).fetchall()
    for _, payload_json in rows:
        payload = json.loads(payload_json)
        merged.update({k: v for k, v in payload.items() if k != "attempt"})
    return merged


def main() -> None:
    merged = merged_payload(JOB_ID)
    source_input = ProtocolDeconstructionInput.model_validate(merged["source_input"])
    spans = {
        span["source_span_id"]: ProtocolSourceSpan.model_validate(span)
        for span in merged["source_spans"].values()
    }
    projection = PhaseProjection.model_validate(merged["phase_projection"])
    del projection

    prompt_template = (
        "请以资深临床试验医学监查人员的专业语义解构本次已确认期别的正式研究方案。"
        "逐条保留官方父规则，准确表达每个必要条件、替代条件、例外、时间锚点、专业判断，"
        "并把基线及以前每个必做项目映射到其独立审核节点。"
    )
    prompt_version = PromptVersion(
        prompt_version_id="protocol-deconstructor/v1",
        node=AgentNode.PROTOCOL_DECONSTRUCTOR,
        template_sha256=protocol_prompt_template_sha256(prompt_template),
        schema_version_id="protocol-deconstruction-draft/v1",
    )
    data_paths = resolve_data_paths()
    cache: ProtocolSemanticBatchCache = _ProtocolSemanticBatchFileCache(data_paths, JOB_ID)
    inner = OpenAICompatibleProtocolAgentTransport(
        backend="deepseek",
        model="deepseek-v4-flash",
        reasoning_effort="high",
    )
    transport = DumpingTransport(inner)
    runner = ProtocolDeconstructorRunner()
    result = runner.run(
        source_input,
        prompt_version=prompt_version,
        prompt_template=prompt_template,
        transport=transport,
        source_spans=spans,
        batch_cache=cache,
    )
    print("status:", result.status)
    print("final_draft:", result.final_draft is not None)
    for attempt in result.attempts[-2:]:
        print("attempt", attempt.attempt, attempt.outcome)
        for issue in attempt.issues[:3]:
            print("  issue:", issue.problem[:500])
    print("transport calls:", transport.calls, "dump:", DUMP)


if __name__ == "__main__":
    main()
