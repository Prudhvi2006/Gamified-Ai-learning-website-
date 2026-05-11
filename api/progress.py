"""
api/progress.py
===============
Blueprint: /api/progress   /api/progress/complete_level

Game unlock chain:
  haunted_mansion (always unlocked)
      --> code_red (after 10 haunted_mansion levels)
              --> ai_labyrinth (after 10 code_red levels)
"""

import time
from datetime import datetime

from flask import Blueprint, request, jsonify

from core.db import get_user_from_token, save_user

bp = Blueprint('progress', __name__)

# ── Game constants ──────────────────────────────────────────────────
GAME_IDS = ['haunted_mansion', 'code_red', 'ai_labyrinth']

GAME_UNLOCK_PREV = {
    'haunted_mansion': None,
    'code_red':        'haunted_mansion',
    'ai_labyrinth':    'code_red',
}

LEVELS_TO_UNLOCK_NEXT = 10  # complete this many levels to unlock the next game


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/progress
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/progress', methods=['GET'])
def get_progress():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({'ok': False, 'msg': 'Unauthorized'}), 401

    gp     = user.get('game_progress', {})
    result = {}

    for gid in GAME_IDS:
        default  = {'levels_done': [], 'unlocked': (gid == 'haunted_mansion')}
        gdata    = gp.get(gid, default)
        unlocked = gdata.get('unlocked', gid == 'haunted_mansion')

        # Re-verify unlock from previous game (source of truth)
        prev = GAME_UNLOCK_PREV.get(gid)
        if prev:
            prev_done = len(gp.get(prev, {}).get('levels_done', []))
            if prev_done >= LEVELS_TO_UNLOCK_NEXT and not unlocked:
                unlocked = True
                gdata['unlocked'] = True

        levels_done = gdata.get('levels_done', [])
        result[gid] = {
            'unlocked':        unlocked,
            'levels_done':     levels_done,
            'total_levels':    10,
            'can_unlock_next': len(levels_done) >= LEVELS_TO_UNLOCK_NEXT,
        }

    return jsonify({'ok': True, 'progress': result})


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/progress/complete_level
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/progress/complete_level', methods=['POST'])
def complete_level():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({'ok': False, 'msg': 'Unauthorized'}), 401

    data    = request.get_json(silent=True) or {}
    game_id = str(data.get('game_id', '')).strip()
    level   = data.get('level')

    if game_id not in GAME_IDS:
        return jsonify({'ok': False, 'msg': 'Invalid game_id'}), 400
    if not isinstance(level, int) or not (1 <= level <= 10):
        return jsonify({'ok': False, 'msg': 'Level must be an integer 1-10'}), 400

    gp          = user.setdefault('game_progress', {})
    gdata       = gp.setdefault(game_id, {'levels_done': [], 'unlocked': (game_id == 'haunted_mansion')})
    levels_done = gdata.setdefault('levels_done', [])

    newly_completed = False
    if level not in levels_done:
        levels_done.append(level)
        newly_completed = True

        # XP scales with level difficulty
        xp_bonus = 200 + (level * 50)
        user['xp']    = user.get('xp', 0) + xp_bonus
        user['level'] = max(1, user['xp'] // 5000 + 1)

        act = user.setdefault('activity', [])
        act.insert(0, {
            'msg':  f'{game_id.replace("_", " ").title()} Level {level} complete! +{xp_bonus} XP 🎯',
            'xp':   xp_bonus,
            'ts':   int(time.time()),
            'diff': game_id,
        })
        user['activity'] = act[:20]

    # ── Unlock next game if threshold reached ─────────────────────
    next_unlocked = False
    if len(levels_done) >= LEVELS_TO_UNLOCK_NEXT:
        next_idx = GAME_IDS.index(game_id) + 1
        if next_idx < len(GAME_IDS):
            next_game  = GAME_IDS[next_idx]
            next_gdata = gp.setdefault(next_game, {'levels_done': [], 'unlocked': False})
            if not next_gdata.get('unlocked'):
                next_gdata['unlocked'] = True
                next_unlocked = True
                act = user.setdefault('activity', [])
                act.insert(0, {
                    'msg':  f'🔓 {next_game.replace("_", " ").title()} UNLOCKED!',
                    'xp':   0,
                    'ts':   int(time.time()),
                    'diff': 'unlock',
                })
                user['activity'] = act[:20]

    save_user(user)

    return jsonify({
        'ok':              True,
        'newly_completed': newly_completed,
        'levels_done':     levels_done,
        'next_unlocked':   next_unlocked,
        'xp':              user.get('xp', 0),
        'level':           user.get('level', 1),
    })
