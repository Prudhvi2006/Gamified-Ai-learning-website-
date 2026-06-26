"""
core/config.py
==============
Single source of truth for:
  - Path constants (BASE_DIR, DB_PATH)
  - Environment variables (MONGODB_URI, GEMINI_API_KEY …)
  - MongoDB client + collection references
  - Firebase state flags

Import this module everywhere you need these values:
    from core import config
    config.users_col.find_one(...)
"""

import os
import sys

# ── Windows: force UTF-8 stdout so emoji print() calls don't crash ─
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

# ── Load .env (silently skip if python-dotenv not installed) ────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Path constants ──────────────────────────────────────────────────
# core/config.py lives one directory below project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, 'data', 'db.json')

# ── Environment variables ───────────────────────────────────────────
MONGODB_URI    = os.environ.get('MONGODB_URI', '').strip()
MONGODB_DB     = os.environ.get('MONGODB_DB', 'gal')
GROK_API_KEY = os.environ.get(
    'GROK_API_KEY',
    'YOUR_GROQ_API_KEY'
).strip()
# Fallback key — used automatically when primary key hits quota/rate-limit
GROK_API_KEY_FALLBACK = os.environ.get(
    'GROK_API_KEY_FALLBACK', 'YOUR_GROQ_API_KEY'
).strip()

# ── MongoDB client + collections ────────────────────────────────────
mongo_client    = None
users_col       = None
sessions_col    = None
leaderboard_col = None
teams_col       = None

if MONGODB_URI:
    try:
        from pymongo import MongoClient

        mongo_client    = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command('ping')

        _mongo_db        = mongo_client[MONGODB_DB]
        users_col        = _mongo_db['users']
        sessions_col     = _mongo_db['sessions']
        leaderboard_col  = _mongo_db['leaderboard']
        teams_col        = _mongo_db['teams']

        # Indexes (idempotent — safe to call on every startup)
        users_col.create_index('email', unique=True)
        sessions_col.create_index('token', unique=True)
        leaderboard_col.create_index('uid', unique=True)
        teams_col.create_index('code', unique=True)
        sessions_col.create_index('ts', expireAfterSeconds=604800)  # 7-day TTL

        print(f'[OK] MongoDB connected: {MONGODB_URI[:40]}...')
    except Exception as exc:
        print(f'[WARN] MongoDB unavailable: {exc}')
        mongo_client = None
else:
    print('[INFO] No MONGODB_URI -- using local JSON (data/db.json)')

# ── Firebase state flags ────────────────────────────────────────────
fb_enabled = False
fb_db      = None

try:
    import firebase_admin
    from firebase_admin import db as firebase_db

    _cred_path = os.environ.get('FIREBASE_CRED_PATH', 'serviceAccountKey.json')
    if os.path.exists(_cred_path):
        firebase_admin.initialize_app(
            firebase_admin.credentials.Certificate(_cred_path),
            {'databaseURL': os.environ.get('FIREBASE_DB_URL', '')}
        )
        fb_db      = firebase_db
        fb_enabled = True
        print('[OK] Firebase Admin SDK initialized')
except Exception as exc:
    print(f'[INFO] Firebase not available: {exc}')
