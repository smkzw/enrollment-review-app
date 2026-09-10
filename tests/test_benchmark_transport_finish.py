from scripts.benchmark_direct_transports import normalized_finish
from scripts.benchmark_direct_transports import stream_events
import asyncio
import httpx


def test_truncation_and_filter_are_not_schema_failures():
    assert normalized_finish({'finish_reason': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}}) == 'length'
    assert normalized_finish({'finish_reason': 'incomplete'}) == 'incomplete'
    assert normalized_finish({'finish_reason': 'SAFETY'}) == 'content_filter'
    assert normalized_finish({'finish_reason': 'MAX_TOKENS'}) == 'length'
    assert normalized_finish({'finish_reason': 'completed'}) == 'stop'


def test_broken_stream_retains_prior_events():
    class Response:
        async def aiter_lines(self):
            yield 'data: {"type":"response.output_text.delta","delta":"partial"}'
            raise httpx.RemoteProtocolError('interrupted')

    async def collect():
        return [event async for event in stream_events(Response())]

    events = asyncio.run(collect())
    assert events[0]['delta'] == 'partial'
    assert events[1] == {'type': 'error', 'message': 'RemoteProtocolError'}
