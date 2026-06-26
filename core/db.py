"""
core/db.py
==========
All database read/write helpers — works with either:
  - MongoDB Atlas  (when core.config.mongo_client is set)
  - Local JSON     (data/db.json fallback)

Public API
----------
  _use_mongo()
  load_db() / save_db(data)
  hash_pass(p)
  find_user(email) / save_user(user)
  find_session(token) / save_session(token, email) / invalidate_session(token)
  all_users_list()
  get_leaderboard_entries(limit) / save_leaderboard_entry(entry)
  get_user_from_token(token)
  calc_streak(days)
"""

import json
import os
import time
import hashlib
import secrets
from datetime import datetime, timedelta

from core import config


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _use_mongo() -> bool:
    """Return True when a live MongoDB connection is available."""
    return config.mongo_client is not None


def _dictify(doc) -> dict | None:
    """Strip MongoDB ObjectId and return a plain dict."""
    if not doc:
        return None
    d = dict(doc)
    d.pop('_id', None)
    return d


# ──────────────────────────────────────────────────────────────────────────────
# JSON DB (local fallback)
# ──────────────────────────────────────────────────────────────────────────────

def load_db() -> dict:
    """Load the local JSON database; return empty scaffold if missing/corrupt."""
    if not os.path.exists(config.DB_PATH):
        return {'users': {}, 'sessions': {}, 'leaderboard': [], 'teams': {}}
    try:
        with open(config.DB_PATH) as f:
            data = json.load(f)
        for key in ('teams', 'users', 'sessions'):
            data.setdefault(key, {})
        data.setdefault('leaderboard', [])
        return data
    except Exception:
        return {'users': {}, 'sessions': {}, 'leaderboard': [], 'teams': {}}


def save_db(data: dict) -> None:
    """Persist the in-memory JSON database to disk."""
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    with open(config.DB_PATH, 'w') as f:
        json.dump(data, f, indent=2)


# ──────────────────────────────────────────────────────────────────────────────
# Password
# ──────────────────────────────────────────────────────────────────────────────

def hash_pass(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────────────────────────────────────

def find_user(email: str) -> dict | None:
    if _use_mongo():
        return _dictify(config.users_col.find_one({'email': email}))
    return load_db()['users'].get(email)


def save_user(user: dict) -> None:
    if _use_mongo():
        config.users_col.replace_one({'email': user['email']}, user, upsert=True)
        return
    db = load_db()
    db['users'][user['email']] = user
    save_db(db)


def all_users_list() -> list:
    if _use_mongo():
        return [_dictify(u) for u in config.users_col.find()]
    return list(load_db()['users'].values())


def get_all_users() -> list:
    """Alias for all_users_list() — returns all users."""
    return all_users_list()


def find_user_by_uid(uid: str) -> dict | None:
    """Find a user by their unique ID (uid)."""
    users = get_all_users()
    for user in users:
        if user.get('uid') == uid:
            return user
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Sessions
# ──────────────────────────────────────────────────────────────────────────────

_SESSION_TTL = 604800  # 7 days in seconds


def find_session(token: str) -> dict | None:
    if not token:
        return None

    if _use_mongo():
        sess = _dictify(config.sessions_col.find_one({'token': token}))
        if sess and time.time() - sess.get('ts', 0) > _SESSION_TTL:
            config.sessions_col.delete_one({'token': token})
            return None
        return sess

    db   = load_db()
    sess = db['sessions'].get(token)
    if sess and time.time() - sess.get('ts', 0) > _SESSION_TTL:
        db['sessions'].pop(token, None)
        save_db(db)
        return None
    return sess


def save_session(token: str, email: str) -> None:
    record = {'token': token, 'email': email, 'ts': int(time.time())}
    if _use_mongo():
        config.sessions_col.replace_one({'token': token}, record, upsert=True)
        return
    db = load_db()
    db['sessions'][token] = {'email': email, 'ts': record['ts']}
    save_db(db)


def invalidate_session(token: str) -> None:
    if _use_mongo():
        config.sessions_col.delete_one({'token': token})
        return
    db = load_db()
    db['sessions'].pop(token, None)
    save_db(db)


# ──────────────────────────────────────────────────────────────────────────────
# Leaderboard
# ──────────────────────────────────────────────────────────────────────────────

def get_leaderboard_entries(limit: int = 20) -> list:
    if _use_mongo():
        from pymongo import DESCENDING
        return [
            _dictify(e)
            for e in config.leaderboard_col.find().sort('score', DESCENDING).limit(limit)
        ]
    db = load_db()
    return sorted(db.get('leaderboard', []), key=lambda e: e.get('score', 0), reverse=True)[:limit]


def save_leaderboard_entry(entry: dict) -> None:
    if _use_mongo():
        config.leaderboard_col.replace_one({'uid': entry['uid']}, entry, upsert=True)
        _prune_leaderboard_mongo()
        return
    db = load_db()
    lb = db.setdefault('leaderboard', [])
    existing = next((e for e in lb if e.get('uid') == entry['uid']), None)
    if existing:
        existing.update(entry)
    else:
        lb.append(entry)
    lb.sort(key=lambda e: e.get('score', 0), reverse=True)
    db['leaderboard'] = lb[:100]
    save_db(db)


def _prune_leaderboard_mongo() -> None:
    if not _use_mongo():
        return
    from pymongo import ASCENDING
    count  = config.leaderboard_col.count_documents({})
    if count <= 100:
        return
    extras = config.leaderboard_col.find().sort('score', ASCENDING).limit(count - 100)
    for doc in extras:
        config.leaderboard_col.delete_one({'_id': doc['_id']})


# ──────────────────────────────────────────────────────────────────────────────
# Auth helpers (used by multiple API modules)
# ──────────────────────────────────────────────────────────────────────────────

def get_user_from_token(token: str) -> dict | None:
    """Resolve a Bearer token to a user dict, or None if invalid/expired."""
    if not token:
        return None
    sess = find_session(token)
    if not sess:
        return None
    return find_user(sess['email'])


def calc_streak(days: list) -> int:
    """Return the current daily login streak length from a sorted list of date strings."""
    if not days:
        return 0
    sorted_d  = sorted(days, reverse=True)
    today     = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    if sorted_d[0] not in (today, yesterday):
        return 1
    streak = 1
    for i in range(1, len(sorted_d)):
        d1 = datetime.strptime(sorted_d[i - 1], '%Y-%m-%d')
        d2 = datetime.strptime(sorted_d[i],     '%Y-%m-%d')
        if (d1 - d2).days == 1:
            streak += 1
        else:
            break
    return streak
