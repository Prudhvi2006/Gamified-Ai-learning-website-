"""
api/profile.py
==============
Blueprint: /api/profile   /api/update_stats
"""

import time
from datetime import datetime

from flask import Blueprint, request, jsonify

from core.db import (
    get_user_from_token, save_user, all_users_list,
    save_leaderboard_entry, calc_streak,
)
from core.firebase import write_user, write_leaderboard
from core import config

bp = Blueprint('profile', __name__)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/profile
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/profile', methods=['GET'])
def profile():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({'ok': False, 'msg': 'Unauthorized'}), 401

    # ── Rank calculation ──────────────────────────────────────────
    if config.users_col is not None:
        total_users = config.users_col.count_documents({})
        rank = config.users_col.count_documents({'score': {'$gt': user.get('score', 0)}}) + 1
    else:
        all_u = sorted(all_users_list(), key=lambda u: u.get('score', 0), reverse=True)
        total_users = len(all_u)
        rank = next((i + 1 for i, u in enumerate(all_u) if u['uid'] == user['uid']), total_users)

    return jsonify({
        'ok':                  True,
        'name':                user['name'],
        'email':               user['email'],
        'uid':                 user['uid'],
        'class_name':          user.get('class_name', ''),
        'grade':               user.get('grade', ''),
        'xp':                  user.get('xp', 0),
        'level':               user.get('level', 1),
        'streak':              user.get('streak', 0),
        'rooms_cleared':       user.get('rooms_cleared', 0),
        'missions_done':       user.get('missions_done', 0),
        'score':               user.get('score', 0),
        'accuracy':            user.get('accuracy', 0),
        'hints_used':          user.get('hints_used', 0),
        'best_combo':          user.get('best_combo', 1),
        'achievements':        user.get('achievements', []),
        'activity':            user.get('activity', [])[-10:],
        'streak_days':         user.get('streak_days', [])[-28:],
        'rank':                rank,
        'total_users':         total_users,
        'joined':              user.get('joined', 0),
        'study_modules_done':  user.get('study_modules_done', []),
        'team_id':             user.get('team_id'),
        'game_progress':       user.get('game_progress', {}),
    })


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/update_stats
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/update_stats', methods=['POST'])
def update_stats():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({'ok': False, 'msg': 'Unauthorized'}), 401

    data         = request.get_json(silent=True) or {}
    score        = max(0, int(data.get('score', 0)))
    rooms        = max(0, int(data.get('rooms_cleared', 0)))
    accuracy     = max(0.0, min(100.0, float(data.get('accuracy', 0))))
    hints        = max(0, int(data.get('hints_used', 0)))
    combo        = max(1, int(data.get('best_combo', 1)))
    difficulty   = str(data.get('difficulty', 'haunted'))[:20]
    xp_earned    = max(0, int(data.get('xp_earned', max(score, 1))))
    activity_msg = str(data.get('activity_msg', f'Game session: +{xp_earned} XP'))[:200]

    # ── Apply stats ───────────────────────────────────────────────
    user['xp']            = user.get('xp', 0) + xp_earned
    user['level']         = max(1, user['xp'] // 5000 + 1)
    user['score']         = max(user.get('score', 0), score)
    user['rooms_cleared'] = user.get('rooms_cleared', 0) + rooms
    user['missions_done'] = user.get('missions_done', 0) + (1 if rooms > 0 else 0)
    user['hints_used']    = user.get('hints_used', 0) + hints
    user['best_combo']    = max(user.get('best_combo', 1), combo)

    if accuracy > 0:
        old_acc  = user.get('accuracy', 0)
        sessions = max(1, user.get('missions_done', 1))
        user['accuracy'] = round((old_acc * (sessions - 1) + accuracy) / sessions, 1)

    act = user.setdefault('activity', [])
    act.insert(0, {
        'msg':  activity_msg,
        'xp':   xp_earned,
        'ts':   int(time.time()),
        'diff': difficulty,
    })
    user['activity'] = act[:20]

    # ── Streak ────────────────────────────────────────────────────
    today = datetime.now().strftime('%Y-%m-%d')
    days  = user.setdefault('streak_days', [])
    if today not in days:
        days.append(today)
        user['streak_days'] = sorted(days)[-60:]
        user['streak']      = calc_streak(user['streak_days'])

    user['last_active'] = int(time.time())
    save_user(user)

    # ── Leaderboard ───────────────────────────────────────────────
    lb_entry = {
        'uid':        user['uid'],
        'name':       user['name'],
        'score':      user['score'],
        'xp':         user['xp'],
        'level':      user['level'],
        'difficulty': difficulty,
        'rooms':      user['rooms_cleared'],
        'date':       datetime.now().strftime('%Y-%m-%d'),
    }
    save_leaderboard_entry(lb_entry)
    write_user(user)
    write_leaderboard(user)

    return jsonify({
        'ok':     True,
        'xp':     user['xp'],
        'level':  user['level'],
        'streak': user.get('streak', 0),
        'score':  user['score'],
    })
