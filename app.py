"""
app.py — GAL: Gamified AI Learning Platform
============================================
Entry point.  All business logic lives in api/ and core/.

Structure
---------
  core/config.py    — environment, MongoDB, Firebase setup
  core/db.py        — database helpers (JSON + MongoDB dual-mode)
  core/firebase.py  — Firebase Realtime Database helpers

  api/auth.py       — POST /api/register  /api/login  /api/logout
  api/profile.py    — GET  /api/profile   POST /api/update_stats
  api/progress.py   — GET  /api/progress  POST /api/progress/complete_level
  api/leaderboard.py— GET  /api/leaderboard
  api/study.py      — GET  /api/study/modules  POST /api/study/complete
  api/team.py       — POST /api/team/create    POST /api/team/join
                      GET  /api/team/info       GET  /api/team/leaderboard
  api/ai_chat.py    — POST /api/ai_chat
"""

import secrets
import os

from flask import Flask, request, jsonify, send_from_directory

from core import config as cfg

# ── Flask app ───────────────────────────────────────────────────────
app = Flask(__name__, static_folder=cfg.BASE_DIR, static_url_path='')
app.secret_key = secrets.token_hex(32)


# ──────────────────────────────────────────────────────────────────────────────
# CORS — allow all origins for API routes (preflight + actual)
# ──────────────────────────────────────────────────────────────────────────────

@app.after_request
def add_cors(response):
    origin = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Origin']      = origin
    response.headers['Access-Control-Allow-Headers']     = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods']     = 'GET,POST,OPTIONS,DELETE,PUT'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


@app.route('/api/<path:p>', methods=['OPTIONS'])
def options_handler(p=''):
    from flask import Response
    r = Response('', 200)
    r.headers['Access-Control-Allow-Origin']      = request.headers.get('Origin', '*')
    r.headers['Access-Control-Allow-Headers']     = 'Content-Type,Authorization'
    r.headers['Access-Control-Allow-Methods']     = 'GET,POST,OPTIONS,DELETE,PUT'
    r.headers['Access-Control-Allow-Credentials'] = 'true'
    return r


# ──────────────────────────────────────────────────────────────────────────────
# Static page routes — serve HTML from project root
# ──────────────────────────────────────────────────────────────────────────────

_PAGES = [
    ('/',                      'index.html'),
    ('/index.html',            'index.html'),
    ('/dashboard.html',        'dashboard.html'),
    ('/login.html',            'login.html'),
    ('/teacher-dashboard.html','teacher-dashboard.html'),
    ('/hauntedmansion.html',   'hauntedmansion.html'),
    ('/codered.html',          'codered.html'),
    ('/shadowquery.html',      'shadowquery.html'),
    ('/treasurehunt.html',     'treasurehunt.html'),
    ('/gemini-chat.html',      'gemini-chat.html'),
]

for _idx, (_route, _file) in enumerate(_PAGES):
    def _make_view(filename):
        def _view():
            return send_from_directory(cfg.BASE_DIR, filename)
        return _view
    # Each endpoint name must be unique
    _fn = _make_view(_file)
    _fn.__name__ = f'page_{_idx}'
    app.add_url_rule(_route, view_func=_fn)



# ──────────────────────────────────────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
def health():
    import time
    return jsonify({
        'ok':       True,
        'db':       'mongodb' if cfg.mongo_client else 'local_json',
        'firebase': cfg.fb_enabled,
        'ai_chat':  bool(cfg.GROK_API_KEY),
        'ts':       int(time.time()),
        'version':  '3.1',
    })


# ──────────────────────────────────────────────────────────────────────────────
# Register blueprints
# ──────────────────────────────────────────────────────────────────────────────

from api.auth        import bp as auth_bp
from api.profile     import bp as profile_bp
from api.progress    import bp as progress_bp
from api.leaderboard import bp as leaderboard_bp
from api.study       import bp as study_bp
from api.team        import bp as team_bp
from api.ai_chat     import bp as ai_chat_bp
from api.teacher     import bp as teacher_bp

for bp in (auth_bp, profile_bp, progress_bp, leaderboard_bp, study_bp, team_bp, ai_chat_bp, teacher_bp):
    app.register_blueprint(bp)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('  GAL -- Gamified AI Learning Platform  v3.1')
    print('  >> http://localhost:5050')
    print('=' * 60)
    print(f"  DB Mode  : {'MongoDB' if cfg.mongo_client else 'Local JSON (data/db.json)'}")
    print(f"  Firebase : {'Enabled' if cfg.fb_enabled else 'Disabled'}")
    print(f"  AI Chat  : {'[ON]' if cfg.GROK_API_KEY else '[OFF] set GROK_API_KEY'}")
    print('=' * 60 + '\n')

    app.run(debug=True, port=5050, host='0.0.0.0')