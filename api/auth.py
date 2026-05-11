"""
api/auth.py
===========
Blueprint: /api/register  /api/login  /api/logout
"""

import re
import time
import secrets
from datetime import datetime

from flask import Blueprint, request, jsonify

from core.db import (
    find_user, save_user,
    save_session, invalidate_session,
    hash_pass, calc_streak,
)
from core.firebase import write_user

bp = Blueprint('auth', __name__)


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/register
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/register', methods=['POST'])
def register():
    data       = request.get_json(silent=True) or {}
    name       = str(data.get('name', '')).strip()
    email      = str(data.get('email', '')).strip().lower()
    password   = str(data.get('password', ''))
    class_name = str(data.get('class_name', '')).strip()
    grade      = str(data.get('grade', '')).strip()

    # ── Validation ────────────────────────────────────────────────
    if not name or not email or not password:
        return jsonify({'ok': False, 'msg': 'Name, email and password are required'}), 400
    if not re.match(r'^[^\@\s]+@[^\@\s]+\.[^\@\s]+$', email):
        return jsonify({'ok': False, 'msg': 'Invalid email address'}), 400
    if len(password) < 8:
        return jsonify({'ok': False, 'msg': 'Password must be at least 8 characters'}), 400
    if len(name) > 100:
        return jsonify({'ok': False, 'msg': 'Name too long'}), 400
    if find_user(email):
        return jsonify({'ok': False, 'msg': 'An account with this email already exists'}), 409

    # ── Create user ───────────────────────────────────────────────
    uid   = 'u_' + secrets.token_hex(8)
    token = secrets.token_hex(32)
    today = datetime.now().strftime('%Y-%m-%d')

    user = {
        'uid':        uid,
        'name':       name,
        'email':      email,
        'hash':       hash_pass(password),
        'class_name': class_name,
        'grade':      grade,
        'joined':     int(time.time()),
        'xp':         250,
        'level':      1,
        'streak':     1,
        'last_active': int(time.time()),
        'rooms_cleared':  0,
        'missions_done':  0,
        'score':          0,
        'accuracy':       0,
        'hints_used':     0,
        'best_combo':     1,
        'achievements':   [],
        'activity': [{
            'msg':  'Account created — Welcome to GAL! 🚀',
            'xp':   250,
            'ts':   int(time.time()),
            'diff': 'system',
        }],
        'streak_days':         [today],
        'study_modules_done':  [],
        'team_id':             None,
        'game_progress': {
            'haunted_mansion': {'levels_done': [], 'unlocked': True},
            'code_red':        {'levels_done': [], 'unlocked': False},
            'ai_labyrinth':    {'levels_done': [], 'unlocked': False},
        },
    }

    save_user(user)
    save_session(token, email)
    write_user(user)

    return jsonify({
        'ok':    True,
        'token': token,
        'uid':   uid,
        'name':  name,
        'xp':    user['xp'],
        'level': user['level'],
    }), 201


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/login
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/login', methods=['POST'])
def login():
    data     = request.get_json(silent=True) or {}
    email    = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))

    if not email or not password:
        return jsonify({'ok': False, 'msg': 'Email and password required'}), 400

    user = find_user(email)
    if not user or user.get('hash') != hash_pass(password):
        return jsonify({'ok': False, 'msg': 'Invalid email or password'}), 401

    token = secrets.token_hex(32)
    save_session(token, email)

    # ── Daily streak update ───────────────────────────────────────
    today = datetime.now().strftime('%Y-%m-%d')
    days  = user.setdefault('streak_days', [])
    if today not in days:
        days.append(today)
        user['streak_days'] = sorted(days)[-60:]
        user['streak']      = calc_streak(user['streak_days'])
        act = user.setdefault('activity', [])
        act.insert(0, {
            'msg':  f'Daily login streak: {user["streak"]} days 🔥',
            'xp':   0,
            'ts':   int(time.time()),
            'diff': 'system',
        })
        user['activity'] = act[:20]

    user['last_active'] = int(time.time())
    save_user(user)
    write_user(user)

    return jsonify({
        'ok':     True,
        'token':  token,
        'name':   user['name'],
        'uid':    user['uid'],
        'xp':     user.get('xp', 0),
        'level':  user.get('level', 1),
        'streak': user.get('streak', 0),
    })


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/logout
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    if token:
        invalidate_session(token)
    return jsonify({'ok': True})
