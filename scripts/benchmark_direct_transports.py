"""Isolated benchmark transports; no agent loop, tools, or clinical publication."""

import json
import os
import sqlite3
from pathlib import Path
import uuid

import httpx

OPENCODE_SESSION_ID = str(uuid.uuid4())


def oauth_credential(provider):
    """Read-only, one-off credential use explicitly authorized for this experiment."""
    path = Path.home() / '.omp/agent/agent.db'
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
        row = db.execute(
            'SELECT data FROM auth_credentials WHERE provider=? '
            'AND disabled_cause IS NULL ORDER BY updated_at DESC LIMIT 1', (provider,)
        ).fetchone()
    if row is None:
        raise ValueError('Missing authorized credential')
    return json.loads(row[0])


def normalized_finish(wire):
    finish = wire.get('finish_reason')
    if finish == 'incomplete' and (wire.get('incomplete_details') or {}).get('reason') == 'max_output_tokens':
        return 'length'
    return {'STOP': 'stop', 'completed': 'stop', 'MAX_TOKENS': 'length',
            'SAFETY': 'content_filter', 'RECITATION': 'content_filter'}.get(finish, finish)


async def stream_events(response):
    """Preserve accumulated output when a stream breaks after successful headers."""
    try:
        async for line in response.aiter_lines():
            if line.startswith('data:') and line[5:].strip() != '[DONE]':
                yield json.loads(line[5:])
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        yield {'type': 'error', 'message': type(exc).__name__}


async def subscription_completion(provider, model, effort, messages, budget, *, timeout=900):
    allowed = {'google-antigravity': {'low', 'high'}, 'openai-codex': {'low', 'high', 'max'},
               'opencode-go': {'high'}}
    if provider not in allowed or effort not in allowed[provider]:
        raise ValueError('Unsupported benchmark provider/effort')
    if any(message.get('role') not in {'system', 'user', 'assistant'} for message in messages):
        raise ValueError('Unsupported benchmark message role; refusing to relabel it')
    credential = ({'access': os.environ['OPENCODE_GO_API_KEY']} if provider == 'opencode-go'
                  else oauth_credential(provider))
    headers = {'Authorization': 'Bearer ' + credential['access']}
    if provider == 'opencode-go':
        headers.update({'User-Agent': 'enrollment-review-benchmark/1.0',
                        'x-opencode-session': OPENCODE_SESSION_ID})
    system = '\n'.join(m['content'] for m in messages if m['role'] == 'system')
    if provider == 'google-antigravity':
        contents = []
        for message in messages:
            if message['role'] == 'system':
                continue
            parts = []
            for item in message['content'] if isinstance(message['content'], list) else [{'type': 'text', 'text': message['content']}]:
                if item['type'] == 'text':
                    parts.append({'text': item['text']})
                else:
                    data_uri = item['image_url']['url']
                    head, data = data_uri.split(',', 1)
                    parts.append({'inlineData': {'mimeType': head[5:].split(';')[0], 'data': data}})
            contents.append({'role': 'model' if message['role'] == 'assistant' else 'user',
                             'parts': parts})
        headers['User-Agent'] = 'antigravity/hub/2.8.0 (aidev_client; os_type=darwin; arch=arm64; cl=963137146)'
        url = 'https://daily-cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
        body = {'project': credential['projectId'], 'model': model,
                'userAgent': 'antigravity', 'requestType': 'agent', 'requestId': str(uuid.uuid4()),
                'request': {'contents': contents, 'systemInstruction': {'role': 'user', 'parts': [{'text': system}]},
                            'generationConfig': {'maxOutputTokens': budget, 'thinkingConfig': {'thinkingLevel': effort.upper(), 'includeThoughts': True}}}}
    else:
        url = ('https://opencode.ai/zen/go/v1/responses' if provider == 'opencode-go'
               else 'https://chatgpt.com/backend-api/codex/responses')
        if provider == 'openai-codex':
            headers.update({'ChatGPT-Account-Id': credential['accountId'],
                        'OpenAI-Beta': 'responses=experimental', 'originator': 'codex_cli_rs',
                        'accept': 'text/event-stream'})
        inputs = []
        for message in messages:
            if message['role'] == 'system':
                continue
            parts = []
            for item in message['content'] if isinstance(message['content'], list) else [{'type': 'text', 'text': message['content']}]:
                parts.append({'type': 'input_text', 'text': item['text']} if item['type'] == 'text'
                             else {'type': 'input_image', 'image_url': item['image_url']['url']})
            inputs.append({'role': message['role'], 'content': parts})
        # Codex subscription transport does not accept max_output_tokens.
        body = {'model': model, 'instructions': system, 'input': inputs, 'stream': True,
                'store': False, 'reasoning': {'effort': effort}, 'tools': []}
        if provider == 'opencode-go':
            body['max_output_tokens'] = budget
    text, thought, usage, finish, actual, response_id = '', '', {}, None, None, None
    incomplete = None
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=15), trust_env=False) as client:
        async with client.stream('POST', url, headers=headers, json=body) as response:
            if response.status_code != 200:
                raw = await response.aread()
                return {'http_status': response.status_code, 'error': raw.decode(errors='replace')[:1200], 'text': ''}
            async for event in stream_events(response):
                if event.get('type') == 'error':
                    return {'http_status': 200, 'error': event.get('message', 'stream_error'), 'text': text,
                            'usage': usage, 'finish_reason': finish,
                            'response_model': actual, 'response_id': response_id,
                            'output_budget_enforced': provider != 'openai-codex'}
                if provider == 'google-antigravity':
                    value = event.get('response', event)
                    usage = value.get('usageMetadata', usage)
                    actual = value.get('modelVersion', actual)
                    response_id = value.get('responseId', response_id)
                    for candidate in value.get('candidates', []):
                        finish = candidate.get('finishReason', finish)
                        for part in candidate.get('content', {}).get('parts', []):
                            if part.get('thought'):
                                thought += part.get('text', '')
                            else:
                                text += part.get('text', '')
                elif event.get('type') == 'response.output_text.delta':
                    text += event.get('delta', '')
                elif event.get('type') in ('response.completed', 'response.incomplete', 'response.failed'):
                    value = event['response']
                    usage = value.get('usage', {})
                    actual, response_id = value.get('model'), value.get('id')
                    finish = value.get('status')
                    incomplete = value.get('incomplete_details')
    return {'text': text, 'thought_characters': len(thought) if provider == 'google-antigravity' else None, 'usage': usage,
            'incomplete_details': incomplete,
            'response_model': actual, 'response_id': response_id, 'finish_reason': finish,
            'output_budget_enforced': provider != 'openai-codex', 'http_status': 200}
