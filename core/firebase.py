"""
core/firebase.py
================
Firebase Realtime Database helpers.

All functions are no-ops when Firebase is not configured — callers
do not need to guard against fb_enabled being False.
"""

import time
from core import config


# ──────────────────────────────────────────────────────────────────────────────
# Write helpers
# ──────────────────────────────────────────────────────────────────────────────

def write_user(user: dict) -> None:
    """Mirror a user's core stats to Firebase Realtime Database."""
    if not config.fb_enabled or not config.fb_db:
        return
    try:
        config.fb_db.reference(f'gal/users/{user.get("uid")}').update({
            'uid':    user.get('uid'),
            'name':   user.get('name'),
            'email':  user.get('email'),
            'level':  user.get('level', 1),
            'score':  user.get('score', 0),
            'xp':     user.get('xp', 0),
            'streak': user.get('streak', 0),
            'updated': int(time.time()),
        })
    except Exception as exc:
        print(f'[Firebase] write_user error: {exc}')


def write_leaderboard(user: dict) -> None:
    """Mirror a user's leaderboard entry to Firebase."""
    if not config.fb_enabled or not config.fb_db:
        return
    try:
        config.fb_db.reference(f'gal/leaderboard/{user.get("uid")}').update({
            'uid':     user.get('uid'),
            'name':    user.get('name'),
            'score':   user.get('score', 0),
            'level':   user.get('level', 1),
            'updated': int(time.time()),
        })
    except Exception as exc:
        print(f'[Firebase] write_leaderboard error: {exc}')


# ──────────────────────────────────────────────────────────────────────────────
# Read helpers
# ──────────────────────────────────────────────────────────────────────────────

def fetch_leaderboard() -> list | None:
    """
    Fetch leaderboard from Firebase.
    Returns a sorted list of up to 20 entries, or None if unavailable.
    """
    if not config.fb_enabled or not config.fb_db:
        return None
    try:
        snap = config.fb_db.reference('gal/leaderboard').get()
        if snap:
            entries = list(snap.values())
            return sorted(entries, key=lambda e: e.get('score', 0), reverse=True)[:20]
    except Exception as exc:
        print(f'[Firebase] fetch_leaderboard error: {exc}')
    return None
