"""
api/leaderboard.py
==================
Blueprint: /api/leaderboard

Shows ALL registered users sorted by XP (descending).
Every user who registers automatically appears here — no need to play first.
Supports up to 1000 entries.
"""

from flask import Blueprint, request, jsonify
from core.db import all_users_list, get_user_from_token
from core import config

bp = Blueprint('leaderboard', __name__)


@bp.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    # Optional: parse ?limit=N (max 1000, default 1000)
    try:
        limit = min(int(request.args.get('limit', 1000)), 1000)
    except (ValueError, TypeError):
        limit = 1000

    # ── Fetch from MongoDB ────────────────────────────────────────
    if config.users_col is not None:
        from pymongo import DESCENDING
        cursor = config.users_col.find(
            {},
            # Only return the fields we need (faster)
            {'uid': 1, 'name': 1, 'email': 1, 'xp': 1,
             'level': 1, 'score': 1, 'streak': 1,
             'rooms_cleared': 1, 'accuracy': 1, 'joined': 1}
        ).sort('xp', DESCENDING).limit(limit)

        lb = []
        for i, doc in enumerate(cursor):
            doc.pop('_id', None)
            lb.append(_format_entry(doc, i + 1))
        return jsonify({'ok': True, 'leaderboard': lb, 'total': len(lb)})

    # ── Fetch from local JSON ─────────────────────────────────────
    all_users = all_users_list()
    sorted_users = sorted(all_users, key=lambda u: u.get('xp', 0), reverse=True)[:limit]
    lb = [_format_entry(u, i + 1) for i, u in enumerate(sorted_users)]
    return jsonify({'ok': True, 'leaderboard': lb, 'total': len(lb)})


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/leaderboard/stats — platform-wide aggregate stats
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/leaderboard/stats', methods=['GET'])
def leaderboard_stats():
    import time
    one_day = int(time.time()) - 86400

    if config.users_col is not None:
        total_users   = config.users_col.count_documents({})
        active_today  = config.users_col.count_documents({'last_active': {'$gte': one_day}})
        total_xp_doc  = list(config.users_col.aggregate([
            {'$group': {'_id': None, 'total': {'$sum': '$xp'}}}
        ]))
        total_xp = total_xp_doc[0]['total'] if total_xp_doc else 0
    else:
        all_u        = all_users_list()
        total_users  = len(all_u)
        active_today = sum(1 for u in all_u if u.get('last_active', 0) >= one_day)
        total_xp     = sum(u.get('xp', 0) for u in all_u)

    return jsonify({
        'ok':          True,
        'total_users': total_users,
        'active_today':active_today,
        'total_xp':    total_xp,
    })


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _format_entry(user: dict, rank: int) -> dict:
    """Convert a raw user dict to a leaderboard row."""
    return {
        'rank':          rank,
        'uid':           user.get('uid', ''),
        'name':          user.get('name', 'Unknown'),
        'xp':            user.get('xp', 0),
        'level':         user.get('level', 1),
        'score':         user.get('score', 0),
        'streak':        user.get('streak', 0),
        'rooms_cleared': user.get('rooms_cleared', 0),
        'accuracy':      user.get('accuracy', 0),
        'joined':        user.get('joined', 0),
    }
