"""
api/ai_chat.py
==============
Blueprint: /api/ai_chat

Proxies requests to Google Gemini API with:
  - Automatic fallback to GEMINI_API_KEY_FALLBACK on quota/rate-limit errors
  - Conversation history support (last 10 turns)
  - Clean error messages per HTTP status code
  - Works for both authenticated and guest users
"""

import urllib.request as _req
import json as _json

from flask import Blueprint, request, jsonify

from core.config import GEMINI_API_KEY, GEMINI_API_KEY_FALLBACK

bp = Blueprint('ai_chat', __name__)

_GEMINI_URL = (
    'https://generativelanguage.googleapis.com/v1beta/'
    'models/gemini-2.0-flash:generateContent?key={key}'
)

_DEFAULT_SYSTEM = (
    "You are GAL's AI study assistant — a helpful, enthusiastic tutor for "
    "students learning programming, AI/ML, and computer science. Keep answers "
    "clear, educational, and encouraging. Use examples and emojis occasionally."
)

# ── Build list of available keys (primary first, fallback second) ────
def _get_keys() -> list[str]:
    keys = []
    if GEMINI_API_KEY:
        keys.append(GEMINI_API_KEY)
    if GEMINI_API_KEY_FALLBACK and GEMINI_API_KEY_FALLBACK != GEMINI_API_KEY:
        keys.append(GEMINI_API_KEY_FALLBACK)
    return keys


def _call_gemini(api_key: str, payload: bytes) -> str:
    """
    Make one Gemini API call with the given key.
    Returns the reply text on success.
    Raises urllib.error.HTTPError on API errors.
    Raises ValueError if the response has no usable candidate.
    """
    req = _req.Request(
        _GEMINI_URL.format(key=api_key),
        data=payload,
        headers={'Content-Type': 'application/json'},
    )
    with _req.urlopen(req, timeout=30) as resp:
        result = _json.loads(resp.read().decode('utf-8'))

    candidates = result.get('candidates', [])
    if candidates and candidates[0].get('content'):
        reply = ''.join(
            part.get('text', '')
            for part in candidates[0]['content'].get('parts', [])
        )
        if reply.strip():
            return reply.strip()
    raise ValueError('No usable response from Gemini')


@bp.route('/api/ai_chat', methods=['POST'])
def ai_chat():
    keys = _get_keys()
    if not keys:
        return jsonify({
            'ok':  False,
            'msg': 'AI not configured. Add GEMINI_API_KEY to your .env file.',
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

    # ── Build Gemini contents ─────────────────────────────────────
    contents = [
        {
            'role':  'model' if m['role'] == 'assistant' else 'user',
            'parts': [{'text': m['content']}],
        }
        for m in messages
    ]

    payload = _json.dumps({
        'system_instruction': {'parts': [{'text': system_msg}]},
        'contents':           contents,
        'generationConfig':   {'maxOutputTokens': 800, 'temperature': 0.7},
    }).encode('utf-8')

    # ── Try each key in order ─────────────────────────────────────
    last_error = ''
    for idx, key in enumerate(keys):
        key_label = 'PRIMARY' if idx == 0 else 'FALLBACK'
        try:
            reply = _call_gemini(key, payload)
            if idx > 0:
                print(f'[ai_chat] Used {key_label} key successfully after primary failed')
            return jsonify({'ok': True, 'reply': reply})

        except Exception as exc:
            err = str(exc)
            last_error = err
            is_quota   = any(x in err for x in ('429', 'RESOURCE_EXHAUSTED', 'quota'))
            is_invalid = any(x in err for x in ('400', 'INVALID_ARGUMENT', 'API_KEY'))

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
                'Both API keys have hit their free-tier quota. '
                'Please get a new key at https://aistudio.google.com/apikey '
                'and add it as GEMINI_API_KEY in your .env file, then restart.'
            ),
        }), 429

    return jsonify({
        'ok':  False,
        'msg': 'AI service unavailable. Check your GEMINI_API_KEY in .env.',
    }), 503
