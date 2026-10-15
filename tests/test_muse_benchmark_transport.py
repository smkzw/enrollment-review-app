import asyncio
import json

import httpx

from scripts import benchmark_direct_transports as transport


def test_muse_preserves_budget_image_and_own_session(monkeypatch):
    requests = []
    def handle(request):
        requests.append(request)
        events = [
            {'type': 'response.output_text.delta', 'delta': '{}'},
            {'type': 'response.completed', 'response': {
                'status': 'completed', 'model': 'muse-spark-1.3-contributor',
                'id': 'test-response', 'usage': {'output_tokens': 2}}},
        ]
        return httpx.Response(200, text=''.join('data: ' + json.dumps(e) + '\n\n' for e in events))
    client = httpx.AsyncClient
    monkeypatch.setattr(transport.httpx, 'AsyncClient',
                        lambda **kwargs: client(transport=httpx.MockTransport(handle), **kwargs))
    monkeypatch.setenv('OPENCODE_GO_API_KEY', 'test-only')
    messages = [{'role': 'system', 'content': 'unchanged'}, {'role': 'user', 'content': [
        {'type': 'text', 'text': 'source'},
        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AA=='}}]}]
    async def run():
        return [await transport.subscription_completion(
            'opencode-go', 'muse-spark-1.3-contributor', 'high', messages, 65536) for _ in range(2)]
    results = asyncio.run(run())
    body = json.loads(requests[0].content)
    assert body['max_output_tokens'] == 65536
    assert body['instructions'] == 'unchanged'
    assert body['input'][0]['content'][1]['image_url'] == 'data:image/png;base64,AA=='
    assert str(requests[0].url) == 'https://opencode.ai/zen/go/v1/responses'
    assert requests[0].headers['x-opencode-session'] == requests[1].headers['x-opencode-session']
    assert requests[0].headers['user-agent'] == 'enrollment-review-benchmark/1.0'
    assert 'chatgpt-account-id' not in requests[0].headers
    assert results[0]['output_budget_enforced'] is True
    assert results[0]['response_model'] == 'muse-spark-1.3-contributor'
