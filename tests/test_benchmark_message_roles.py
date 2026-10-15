import asyncio
import json

import httpx
import pytest

from scripts import benchmark_direct_transports as transport


@pytest.mark.parametrize('provider', ['google-antigravity', 'openai-codex', 'opencode-go'])
def test_history_roles_and_text_preserved(monkeypatch, provider):
    captured = []

    def handle(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, text='data: [DONE]\n\n')

    client = httpx.AsyncClient
    monkeypatch.setattr(transport.httpx, 'AsyncClient',
                        lambda **kw: client(transport=httpx.MockTransport(handle), **kw))
    monkeypatch.setattr(transport, 'oauth_credential',
                        lambda _: {'access': 'test', 'projectId': 'test', 'accountId': 'test'})
    monkeypatch.setenv('OPENCODE_GO_API_KEY', 'test')
    messages = [{'role': 'system', 'content': 'system'},
                {'role': 'user', 'content': 'original'},
                {'role': 'assistant', 'content': 'prior response'},
                {'role': 'user', 'content': 'correction request'}]
    asyncio.run(transport.subscription_completion(provider, 'test', 'high', messages, 65536))
    body = captured[0]
    if provider == 'google-antigravity':
        turns = body['request']['contents']
        assert [x['role'] for x in turns] == ['user', 'model', 'user']
        assert [x['parts'][0]['text'] for x in turns] == [m['content'] for m in messages[1:]]
    else:
        assert [x['role'] for x in body['input']] == ['user', 'assistant', 'user']
        assert [x['content'][0]['text'] for x in body['input']] == [m['content'] for m in messages[1:]]


def test_unknown_role_rejected_before_credentials(monkeypatch):
    def forbidden(_):
        raise AssertionError('Must not read credentials')
    monkeypatch.setattr(transport, 'oauth_credential', forbidden)
    with pytest.raises(ValueError, match='message role'):
        asyncio.run(transport.subscription_completion('openai-codex', 'test', 'high',
                    [{'role': 'tool', 'content': 'not a user message'}], 65536))
