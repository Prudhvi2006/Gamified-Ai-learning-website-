"""
api/ai_chat.py
==============
Blueprint: /api/ai_chat

Proxies requests to Groq API with:
  - Conversation history support (last 10 turns)
  - Clean error messages per HTTP status code
  - Works for both authenticated and guest users
"""

import urllib.request as _req
import json as _json

from flask import Blueprint, request, jsonify

from core.config import GROK_API_KEY, GROK_API_KEY_FALLBACK

bp = Blueprint('ai_chat', __name__)

_GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions'

_DEFAULT_SYSTEM = (
    "You are GAL's AI study assistant — a helpful, enthusiastic tutor for "
    "students learning programming, AI/ML, and computer science. Keep answers "
    "clear, educational, and encouraging. Use examples and emojis occasionally."
)

# ── Build list of available keys (primary first, fallback second) ────
def _get_keys() -> list[str]:
    keys = []
    if GROK_API_KEY:
        keys.append(GROK_API_KEY)
    if GROK_API_KEY_FALLBACK and GROK_API_KEY_FALLBACK != GROK_API_KEY:
        keys.append(GROK_API_KEY_FALLBACK)
    return keys


def _call_groq(api_key: str, payload: bytes) -> str:
    """
    Make one Groq API call with the given key.
    Returns the reply text on success.
    Raises urllib.error.HTTPError on API errors.
    Raises ValueError if the response has no usable choices.
    """
    req = _req.Request(
        _GROQ_URL,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        },
    )
    with _req.urlopen(req, timeout=30) as resp:
        result = _json.loads(resp.read().decode('utf-8'))

    choices = result.get('choices', [])
    if choices and choices[0].get('message'):
        reply = choices[0]['message'].get('content', '').strip()
        if reply:
            return reply
    raise ValueError('No usable response from Groq')


@bp.route('/api/ai_chat', methods=['POST'])
def ai_chat():
    keys = _get_keys()
    if not keys:
        return jsonify({
            'ok':  False,
            'msg': 'AI not configured. Add GROK_API_KEY to your .env file.',
        }), 503

    data    = request.get_json(silent=True) or {}
    message = str(data.get('message', '')).strip()

    if not message:
        return jsonify({'ok': False, 'msg': 'Message is required'}), 400
    if len(message) > 2000:
        return jsonify({'ok': False, 'msg': 'Message too long (max 2000 chars)'}), 400

    # ── System prompt ─────────────────────────────────────────────
    custom_ctx = str(data.get('context', ''))[:500]
    system_msg = data.get('system') or f'{_DEFAULT_SYSTEM} Context: {custom_ctx}'

    # ── Sanitise history ──────────────────────────────────────────
    clean_history = []
    for msg in (data.get('history') or [])[-10:]:
        if (
            isinstance(msg, dict)
            and msg.get('role') in ('user', 'assistant')
            and isinstance(msg.get('content'), str)
        ):
            clean_history.append({'role': msg['role'], 'content': msg['content'][:2000]})

    messages = clean_history + [{'role': 'user', 'content': message}]

    # ── Build Groq messages ─────────────────────────────────────
    groq_messages = [{'role': 'system', 'content': system_msg}] + messages

    payload = _json.dumps({
        'model': 'mixtral-8x7b-32768',
        'messages': groq_messages,
        'max_tokens': 800,
        'temperature': 0.7,
    }).encode('utf-8')

    # ── Try each key in order (primary first, fallback second) ────
    last_error = ''
    for idx, key in enumerate(keys):
        key_label = 'PRIMARY' if idx == 0 else 'FALLBACK'
        try:
            reply = _call_groq(key, payload)
            if idx > 0:
                print(f'[ai_chat] Used {key_label} key successfully after primary failed')
            return jsonify({'ok': True, 'reply': reply})

        except Exception as exc:
            err = str(exc)
            last_error = err
            is_quota   = any(x in err for x in ('429', 'RESOURCE_EXHAUSTED', 'quota'))
            is_invalid = any(x in err for x in ('400', 'INVALID_ARGUMENT', 'API_KEY', '401'))

            if is_quota:
                print(f'[ai_chat] {key_label} key quota exhausted — trying next key...')
                continue  # Try fallback key

            if is_invalid:
                print(f'[ai_chat] {key_label} key invalid: {err[:80]}')
                continue  # Try fallback key

            # Unexpected error — don't retry
            print(f'[ai_chat] Unexpected error with {key_label} key: {err[:120]}')
            return jsonify({'ok': False, 'msg': f'AI error: {err[:120]}'}), 500

    # ── All keys exhausted ────────────────────────────────────────
    if any(x in last_error for x in ('429', 'RESOURCE_EXHAUSTED', 'quota')):
        return jsonify({
            'ok':  False,
            'msg': (
                'Both API keys have hit their quota limit. '
                'Please get a new key at https://console.groq.com/keys '
                'and add it as GROK_API_KEY_FALLBACK in your .env file, then restart.'
            ),
        }), 429

    return jsonify({
        'ok':  False,
        'msg': 'AI service unavailable. Check your GROK_API_KEY in .env.',
    }), 503
