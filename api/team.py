"""
api/team.py
===========
Blueprint: /api/team/create   /api/team/join
           /api/team/info      /api/team/leaderboard
"""

import time
import secrets

from flask import Blueprint, request, jsonify

from core.db import get_user_from_token, save_user, load_db, save_db
from core import config

bp = Blueprint('team', __name__)


# ──────────────────────────────────────────────────────────────────────────────
# Team DB helpers (teams use the same dual-mode pattern as users)
# ──────────────────────────────────────────────────────────────────────────────

def _find_team(code: str) -> dict | None:
    if config.teams_col is not None:
        doc = config.teams_col.find_one({'code': code.upper()})
        if not doc:
            return None
        d = dict(doc)
        d.pop('_id', None)
        return d
    return load_db()['teams'].get(code.upper())


def _save_team(team: dict) -> None:
    if config.teams_col is not None:
        config.teams_col.replace_one({'code': team['code']}, team, upsert=True)
        return
    db = load_db()
    db['teams'][team['code']] = team
    save_db(db)


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/team/create
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/team/create', methods=['POST'])
def create_team():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({'ok': False, 'msg': 'Unauthorized'}), 401

    data      = request.get_json(silent=True) or {}
    team_name = str(data.get('name', '')).strip()[:60]
    if not team_name:
        return jsonify({'ok': False, 'msg': 'Team name required'}), 400

    code = secrets.token_hex(3).upper()
    team = {
        'code':    code,
        'name':    team_name,
        'owner':   user['uid'],
        'members': [{
            'uid':   user['uid'],
            'name':  user['name'],
            'score': user.get('score', 0),
            'level': user.get('level', 1),
        }],
        'created': int(time.time()),
        'score':   user.get('score', 0),
    }
    _save_team(team)
    user['team_id'] = code
    save_user(user)

    return jsonify({'ok': True, 'code': code, 'team': team}), 201


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/team/join
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/team/join', methods=['POST'])
def join_team():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({'ok': False, 'msg': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    code = str(data.get('code', '')).strip().upper()
    if not code:
        return jsonify({'ok': False, 'msg': 'Team code required'}), 400

    team = _find_team(code)
    if not team:
        return jsonify({'ok': False, 'msg': 'Team not found. Check the code!'}), 404

    members = team.get('members', [])
    if any(m['uid'] == user['uid'] for m in members):
        return jsonify({'ok': True, 'team': team, 'msg': 'Already in team'})
    if len(members) >= 6:
        return jsonify({'ok': False, 'msg': 'Team is full (max 6 members)'}), 400

    members.append({
        'uid':   user['uid'],
        'name':  user['name'],
        'score': user.get('score', 0),
        'level': user.get('level', 1),
    })
    team['members'] = members
    team['score']   = sum(m.get('score', 0) for m in members)
    _save_team(team)
    user['team_id'] = code
    save_user(user)

    return jsonify({'ok': True, 'team': team})


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/team/info
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/team/info', methods=['GET'])
def team_info():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({'ok': False, 'msg': 'Unauthorized'}), 401

    code = request.args.get('code') or user.get('team_id')
    if not code:
        return jsonify({'ok': False, 'msg': 'Not in a team'}), 404

    team = _find_team(code)
    if not team:
        return jsonify({'ok': False, 'msg': 'Team not found'}), 404

    return jsonify({'ok': True, 'team': team})


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/team/leaderboard
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/team/leaderboard', methods=['GET'])
def team_leaderboard():
    if config.teams_col is not None:
        teams = []
        for t in config.teams_col.find().sort('score', -1).limit(10):
            d = dict(t)
            d.pop('_id', None)
            teams.append(d)
    else:
        db    = load_db()
        teams = sorted(
            db.get('teams', {}).values(),
            key=lambda t: t.get('score', 0),
            reverse=True
        )[:10]

    return jsonify({'ok': True, 'teams': teams})
