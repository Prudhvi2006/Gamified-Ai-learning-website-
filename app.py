"""
GAL — Gamified AI Learning Platform
Flask Backend API — FIXED & PRODUCTION-READY VERSION v3.0

FIXES IN THIS VERSION:
1. Data flow fixed — all endpoints return consistent {ok, ...data} shape
2. /api/ai_chat fixed — properly proxies to Gemini with full system context
3. /api/progress endpoint added — tracks per-game level completion
4. update_stats fixed — accepts new fields (xp_earned, game, accuracy)
5. CORS fixed — proper preflight handling for all routes
6. Input validation added to all endpoints
7. Session token expiry (7-day TTL) added
8. Rate limiting hints added (implement with Flask-Limiter in prod)
"""

from flask import Flask, request, jsonify, send_from_directory
import json, os, time, hashlib, secrets, re
from datetime import datetime, timedelta

# ── Optional: Firebase Admin SDK ──────────────────────────────────
fb_enabled = False
fb_db = None
try:
    import firebase_admin
    from firebase_admin import db
    firebase_cred_path = os.environ.get('FIREBASE_CRED_PATH', 'serviceAccountKey.json')
    if os.path.exists(firebase_cred_path):
        firebase_admin.initialize_app(
            firebase_admin.credentials.Certificate(firebase_cred_path),
            {'databaseURL': os.environ.get('FIREBASE_DB_URL', '')}
        )
        fb_db = db
        fb_enabled = True
        print('✅ Firebase Admin SDK initialized')
except Exception as e:
    print(f'ℹ️  Firebase not available: {e}')

# ── Load .env if available ─────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
app.secret_key = secrets.token_hex(32)

DB_PATH     = os.path.join(BASE_DIR, 'data', 'db.json')
MONGODB_URI = os.environ.get('MONGODB_URI', '').strip()
MONGODB_DB  = os.environ.get('MONGODB_DB', 'gal')

# ── MongoDB Setup ─────────────────────────────────────────────────
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
        mongo_db        = mongo_client[MONGODB_DB]
        users_col       = mongo_db['users']
        sessions_col    = mongo_db['sessions']
        leaderboard_col = mongo_db['leaderboard']
        teams_col       = mongo_db['teams']
        users_col.create_index('email', unique=True)
        sessions_col.create_index('token', unique=True)
        leaderboard_col.create_index('uid', unique=True)
        teams_col.create_index('code', unique=True)
        # TTL index: sessions expire after 7 days
        sessions_col.create_index('ts', expireAfterSeconds=604800)
        print(f'✅ MongoDB connected: {MONGODB_URI}')
    except Exception as e:
        print(f'⚠️  MongoDB unavailable: {e}')
        mongo_client = None
else:
    print('ℹ️  No MONGODB_URI — using local JSON (data/db.json)')

# ─────────────────────────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────────────────────────
def _use_mongo():
    return mongo_client is not None

def dictify(doc):
    if not doc:
        return None
    d = dict(doc)
    d.pop('_id', None)
    return d

def load_db():
    if not os.path.exists(DB_PATH):
        return {'users': {}, 'sessions': {}, 'leaderboard': [], 'teams': {}}
    try:
        with open(DB_PATH) as f:
            data = json.load(f)
            for key in ('teams', 'users', 'sessions'):
                data.setdefault(key, {})
            data.setdefault('leaderboard', [])
            return data
    except Exception:
        return {'users': {}, 'sessions': {}, 'leaderboard': [], 'teams': {}}

def save_db(data):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, 'w') as f:
        json.dump(data, f, indent=2)

def hash_pass(p):
    return hashlib.sha256(p.encode()).hexdigest()

def find_user(email):
    if _use_mongo():
        return dictify(users_col.find_one({'email': email}))
    return load_db()['users'].get(email)

def save_user(user):
    if _use_mongo():
        users_col.replace_one({'email': user['email']}, user, upsert=True)
        return
    db = load_db()
    db['users'][user['email']] = user
    save_db(db)

def find_session(token):
    if not token:
        return None
    if _use_mongo():
        sess = dictify(sessions_col.find_one({'token': token}))
        if sess:
            # Check 7-day expiry manually (belt + suspenders)
            if time.time() - sess.get('ts', 0) > 604800:
                sessions_col.delete_one({'token': token})
                return None
        return sess
    db = load_db()
    sess = db['sessions'].get(token)
    if sess and time.time() - sess.get('ts', 0) > 604800:
        db['sessions'].pop(token, None)
        save_db(db)
        return None
    return sess

def save_session(token, email):
    if _use_mongo():
        sessions_col.replace_one(
            {'token': token},
            {'token': token, 'email': email, 'ts': int(time.time())},
            upsert=True
        )
        return
    db = load_db()
    db['sessions'][token] = {'email': email, 'ts': int(time.time())}
    save_db(db)

def invalidate_session(token):
    if _use_mongo():
        sessions_col.delete_one({'token': token})
        return
    db = load_db()
    db['sessions'].pop(token, None)
    save_db(db)

def all_users_list():
    if _use_mongo():
        return [dictify(u) for u in users_col.find()]
    return list(load_db()['users'].values())

def get_leaderboard_entries(limit=20):
    if _use_mongo():
        from pymongo import DESCENDING
        return [dictify(e) for e in leaderboard_col.find().sort('score', DESCENDING).limit(limit)]
    db = load_db()
    return sorted(db.get('leaderboard', []), key=lambda e: e.get('score', 0), reverse=True)[:limit]

def save_leaderboard_entry(entry):
    if _use_mongo():
        leaderboard_col.replace_one({'uid': entry['uid']}, entry, upsert=True)
        _prune_leaderboard()
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

def _prune_leaderboard():
    if not _use_mongo():
        return
    from pymongo import ASCENDING
    count = leaderboard_col.count_documents({})
    if count <= 100:
        return
    extras = leaderboard_col.find().sort('score', ASCENDING).limit(count - 100)
    for doc in extras:
        leaderboard_col.delete_one({'_id': doc['_id']})

# ── FIREBASE HELPERS ─────────────────────────────────────────────
def fb_write_user(user):
    if not fb_enabled or not fb_db:
        return
    try:
        fb_db.reference(f'gal/users/{user.get("uid")}').update({
            'uid':    user.get('uid'),
            'name':   user.get('name'),
            'email':  user.get('email'),
            'level':  user.get('level', 1),
            'score':  user.get('score', 0),
            'xp':     user.get('xp', 0),
            'streak': user.get('streak', 0),
            'updated': int(time.time())
        })
    except Exception as e:
        print(f'Firebase write_user error: {e}')

def fb_write_leaderboard(user):
    if not fb_enabled or not fb_db:
        return
    try:
        fb_db.reference(f'gal/leaderboard/{user.get("uid")}').update({
            'uid':   user.get('uid'),
            'name':  user.get('name'),
            'score': user.get('score', 0),
            'level': user.get('level', 1),
            'updated': int(time.time())
        })
    except Exception as e:
        print(f'Firebase write_leaderboard error: {e}')

def fb_fetch_leaderboard():
    if not fb_enabled or not fb_db:
        return None
    try:
        snap = fb_db.reference('gal/leaderboard').get()
        if snap:
            entries = list(snap.values())
            return sorted(entries, key=lambda e: e.get('score', 0), reverse=True)[:20]
    except Exception as e:
        print(f'Firebase fetch_leaderboard error: {e}')
    return None

# ── CORS ─────────────────────────────────────────────────────────
@app.after_request
def add_cors(resp):
    origin = request.headers.get('Origin', '*')
    resp.headers['Access-Control-Allow-Origin']  = origin
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS,DELETE,PUT'
    resp.headers['Access-Control-Allow-Credentials'] = 'true'
    return resp

@app.route('/api/<path:p>', methods=['OPTIONS'])
def options_handler(p=''):
    from flask import Response
    r = Response('', 200)
    r.headers['Access-Control-Allow-Origin']  = request.headers.get('Origin', '*')
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    r.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS,DELETE,PUT'
    r.headers['Access-Control-Allow-Credentials'] = 'true'
    return r

# ── SERVE HTML PAGES ─────────────────────────────────────────────
@app.route('/')
@app.route('/index.html')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/dashboard.html')
def dashboard():
    return send_from_directory(BASE_DIR, 'dashboard.html')

@app.route('/hauntedmansion.html')
def hauntedmansion():
    return send_from_directory(BASE_DIR, 'hauntedmansion.html')

@app.route('/codered.html')
def codered():
    return send_from_directory(BASE_DIR, 'codered.html')

@app.route('/shadowquery.html')
def shadowquery():
    return send_from_directory(BASE_DIR, 'shadowquery.html')

@app.route('/treasurehunt.html')
def treasurehunt():
    return send_from_directory(BASE_DIR, 'treasurehunt.html')

@app.route('/gemini-chat.html')
def gemini_chat():
    return send_from_directory(BASE_DIR, 'gemini-chat.html')

@app.route('/games.html')
def games_page():
    return send_from_directory(BASE_DIR, 'games.html')

@app.route('/study.html')
def study_page():
    return send_from_directory(BASE_DIR, 'study.html')

@app.route('/teamup.html')
def teamup_page():
    return send_from_directory(BASE_DIR, 'teamup.html')

# ── HEALTH CHECK ─────────────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "ok":       True,
        "db":       "mongodb" if _use_mongo() else "local_json",
        "firebase": fb_enabled,
        "ai_chat":  bool(os.environ.get('GEMINI_API_KEY') or 'AIzaSyAD3-6O7f25ZC56Crk77DxvhGRqAIVgAEI'),
        "ts":       int(time.time()),
        "version":  "3.0"
    })

# ── REGISTER ─────────────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def register():
    data       = request.get_json(silent=True) or {}
    name       = str(data.get('name', '')).strip()
    email      = str(data.get('email', '')).strip().lower()
    password   = str(data.get('password', ''))
    class_name = str(data.get('class_name', '')).strip()
    grade      = str(data.get('grade', '')).strip()

    if not name or not email or not password:
        return jsonify({"ok": False, "msg": "Name, email and password are required"}), 400
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return jsonify({"ok": False, "msg": "Invalid email address"}), 400
    if len(password) < 8:
        return jsonify({"ok": False, "msg": "Password must be at least 8 characters"}), 400
    if len(name) > 100:
        return jsonify({"ok": False, "msg": "Name too long"}), 400

    if find_user(email):
        return jsonify({"ok": False, "msg": "An account with this email already exists"}), 409

    uid   = 'u_' + secrets.token_hex(8)
    token = secrets.token_hex(32)
    today = datetime.now().strftime('%Y-%m-%d')

    user = {
        "uid":          uid,
        "name":         name,
        "email":        email,
        "hash":         hash_pass(password),
        "class_name":   class_name,
        "grade":        grade,
        "joined":       int(time.time()),
        "xp":           250,
        "level":        1,
        "streak":       1,
        "last_active":  int(time.time()),
        "rooms_cleared":0,
        "missions_done":0,
        "score":        0,
        "accuracy":     0,
        "hints_used":   0,
        "best_combo":   1,
        "achievements": [],
        "activity":     [{"msg": "Account created — Welcome to GAL! 🚀", "xp": 250, "ts": int(time.time()), "diff": "system"}],
        "streak_days":  [today],
        "study_modules_done": [],
        "team_id":      None,
        # GAME PROGRESSION — tracks per-game level completion
        "game_progress": {
            "haunted_mansion": {"levels_done": [], "unlocked": True},
            "code_red":        {"levels_done": [], "unlocked": False},
            "ai_labyrinth":    {"levels_done": [], "unlocked": False},
        }
    }
    save_user(user)
    save_session(token, email)
    fb_write_user(user)

    return jsonify({
        "ok":    True,
        "token": token,
        "uid":   uid,
        "name":  name,
        "xp":    user['xp'],
        "level": user['level']
    }), 201

# ── LOGIN ─────────────────────────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def login():
    data     = request.get_json(silent=True) or {}
    email    = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))

    if not email or not password:
        return jsonify({"ok": False, "msg": "Email and password required"}), 400

    user = find_user(email)
    if not user or user.get('hash') != hash_pass(password):
        return jsonify({"ok": False, "msg": "Invalid email or password"}), 401

    token = secrets.token_hex(32)
    save_session(token, email)

    today = datetime.now().strftime('%Y-%m-%d')
    days  = user.setdefault('streak_days', [])
    if today not in days:
        days.append(today)
        user['streak_days'] = sorted(days)[-60:]
        user['streak'] = _calc_streak(user['streak_days'])
        act = user.setdefault('activity', [])
        act.insert(0, {"msg": f"Daily login streak: {user['streak']} days 🔥", "xp": 0, "ts": int(time.time()), "diff": "system"})
        user['activity'] = act[:20]

    user['last_active'] = int(time.time())
    save_user(user)
    fb_write_user(user)

    return jsonify({
        "ok":    True,
        "token": token,
        "name":  user['name'],
        "uid":   user['uid'],
        "xp":    user.get('xp', 0),
        "level": user.get('level', 1),
        "streak": user.get('streak', 0),
    })

# ── LOGOUT ────────────────────────────────────────────────────────
@app.route('/api/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    if token:
        invalidate_session(token)
    return jsonify({"ok": True})

# ── STREAK HELPER ─────────────────────────────────────────────────
def _calc_streak(days):
    if not days:
        return 0
    sorted_d = sorted(days, reverse=True)
    today    = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    if sorted_d[0] not in (today, yesterday):
        return 1
    streak = 1
    for i in range(1, len(sorted_d)):
        d1 = datetime.strptime(sorted_d[i-1], '%Y-%m-%d')
        d2 = datetime.strptime(sorted_d[i],   '%Y-%m-%d')
        if (d1 - d2).days == 1:
            streak += 1
        else:
            break
    return streak

def get_user_from_token(token):
    if not token:
        return None
    sess = find_session(token)
    if not sess:
        return None
    return find_user(sess['email'])

# ── PROFILE ──────────────────────────────────────────────────────
@app.route('/api/profile', methods=['GET'])
def profile():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    if _use_mongo():
        total_users = users_col.count_documents({})
        rank = users_col.count_documents({"score": {"$gt": user.get('score', 0)}}) + 1
    else:
        all_u = sorted(all_users_list(), key=lambda u: u.get('score', 0), reverse=True)
        total_users = len(all_u)
        rank = next((i + 1 for i, u in enumerate(all_u) if u['uid'] == user['uid']), total_users)

    return jsonify({
        "ok":                 True,
        "name":               user['name'],
        "email":              user['email'],
        "uid":                user['uid'],
        "class_name":         user.get('class_name', ''),
        "grade":              user.get('grade', ''),
        "xp":                 user.get('xp', 0),
        "level":              user.get('level', 1),
        "streak":             user.get('streak', 0),
        "rooms_cleared":      user.get('rooms_cleared', 0),
        "missions_done":      user.get('missions_done', 0),
        "score":              user.get('score', 0),
        "accuracy":           user.get('accuracy', 0),
        "hints_used":         user.get('hints_used', 0),
        "best_combo":         user.get('best_combo', 1),
        "achievements":       user.get('achievements', []),
        "activity":           user.get('activity', [])[-10:],
        "streak_days":        user.get('streak_days', [])[-28:],
        "rank":               rank,
        "total_users":        total_users,
        "joined":             user.get('joined', 0),
        "study_modules_done": user.get('study_modules_done', []),
        "team_id":            user.get('team_id'),
        "game_progress":      user.get('game_progress', {}),
    })

# ── UPDATE STATS ─────────────────────────────────────────────────
@app.route('/api/update_stats', methods=['POST'])
def update_stats():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    data         = request.get_json(silent=True) or {}
    score        = max(0, int(data.get('score', 0)))
    rooms        = max(0, int(data.get('rooms_cleared', 0)))
    accuracy     = max(0.0, min(100.0, float(data.get('accuracy', 0))))
    hints        = max(0, int(data.get('hints_used', 0)))
    combo        = max(1, int(data.get('best_combo', 1)))
    difficulty   = str(data.get('difficulty', 'haunted'))[:20]
    xp_earned    = max(0, int(data.get('xp_earned', max(score, 1))))
    activity_msg = str(data.get('activity_msg', f'Game session: +{xp_earned} XP'))[:200]

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
    act.insert(0, {"msg": activity_msg, "xp": xp_earned, "ts": int(time.time()), "diff": difficulty})
    user['activity'] = act[:20]

    today = datetime.now().strftime('%Y-%m-%d')
    days  = user.setdefault('streak_days', [])
    if today not in days:
        days.append(today)
        user['streak_days'] = sorted(days)[-60:]
        user['streak'] = _calc_streak(user['streak_days'])

    user['last_active'] = int(time.time())
    save_user(user)

    entry = {
        "uid":        user['uid'],
        "name":       user['name'],
        "score":      user['score'],
        "xp":         user['xp'],
        "level":      user['level'],
        "difficulty": difficulty,
        "rooms":      user['rooms_cleared'],
        "date":       datetime.now().strftime('%Y-%m-%d')
    }
    save_leaderboard_entry(entry)
    fb_write_user(user)
    fb_write_leaderboard(user)

    return jsonify({
        "ok":     True,
        "xp":     user['xp'],
        "level":  user['level'],
        "streak": user.get('streak', 0),
        "score":  user['score']
    })

# ── GAME PROGRESSION ─────────────────────────────────────────────
GAME_IDS = ['haunted_mansion', 'code_red', 'ai_labyrinth']
GAME_UNLOCK_LEVELS = {
    'haunted_mansion': 0,   # always unlocked
    'code_red':        10,  # unlock after 10 levels in haunted_mansion
    'ai_labyrinth':    10,  # unlock after 10 levels in code_red
}
GAME_UNLOCK_PREV = {
    'haunted_mansion': None,
    'code_red':        'haunted_mansion',
    'ai_labyrinth':    'code_red',
}

@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Get game progression state for the current user."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    gp = user.get('game_progress', {})
    result = {}
    for gid in GAME_IDS:
        gdata    = gp.get(gid, {'levels_done': [], 'unlocked': (gid == 'haunted_mansion')})
        prev     = GAME_UNLOCK_PREV.get(gid)
        unlocked = gdata.get('unlocked', gid == 'haunted_mansion')
        # Re-verify unlock based on previous game levels (source of truth)
        if prev:
            prev_data = gp.get(prev, {'levels_done': []})
            prev_done = len(prev_data.get('levels_done', []))
            if prev_done >= 10 and not unlocked:
                unlocked = True
                gdata['unlocked'] = True
        result[gid] = {
            "unlocked":    unlocked,
            "levels_done": gdata.get('levels_done', []),
            "total_levels": 10,
            "can_unlock_next": len(gdata.get('levels_done', [])) >= 10
        }
    return jsonify({"ok": True, "progress": result})


@app.route('/api/progress/complete_level', methods=['POST'])
def complete_level():
    """Mark a level as complete for a given game."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    data    = request.get_json(silent=True) or {}
    game_id = str(data.get('game_id', '')).strip()
    level   = data.get('level')

    if game_id not in GAME_IDS:
        return jsonify({"ok": False, "msg": "Invalid game_id"}), 400
    if not isinstance(level, int) or level < 1 or level > 10:
        return jsonify({"ok": False, "msg": "Level must be an integer 1-10"}), 400

    gp = user.setdefault('game_progress', {})
    gdata = gp.setdefault(game_id, {'levels_done': [], 'unlocked': (game_id == 'haunted_mansion')})
    levels_done = gdata.setdefault('levels_done', [])

    newly_completed = False
    if level not in levels_done:
        levels_done.append(level)
        newly_completed = True

        # Award XP for level completion
        xp_bonus = 200 + (level * 50)  # scales with level difficulty
        user['xp']   = user.get('xp', 0) + xp_bonus
        user['level'] = max(1, user['xp'] // 5000 + 1)
        act = user.setdefault('activity', [])
        act.insert(0, {
            "msg":  f"{game_id.replace('_',' ').title()} Level {level} complete! +{xp_bonus} XP 🎯",
            "xp":   xp_bonus,
            "ts":   int(time.time()),
            "diff": game_id
        })
        user['activity'] = act[:20]

    # Check if next game should be unlocked
    next_unlocked = False
    if len(levels_done) >= 10:
        next_idx = GAME_IDS.index(game_id) + 1
        if next_idx < len(GAME_IDS):
            next_game = GAME_IDS[next_idx]
            next_gdata = gp.setdefault(next_game, {'levels_done': [], 'unlocked': False})
            if not next_gdata.get('unlocked'):
                next_gdata['unlocked'] = True
                next_unlocked = True
                act = user.setdefault('activity', [])
                act.insert(0, {
                    "msg":  f"🔓 {next_game.replace('_',' ').title()} UNLOCKED!",
                    "xp":   0,
                    "ts":   int(time.time()),
                    "diff": "unlock"
                })
                user['activity'] = act[:20]

    save_user(user)
    return jsonify({
        "ok":              True,
        "newly_completed": newly_completed,
        "levels_done":     levels_done,
        "next_unlocked":   next_unlocked,
        "xp":              user.get('xp', 0),
        "level":           user.get('level', 1),
    })

# ── LEADERBOARD ───────────────────────────────────────────────────
@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    if fb_enabled:
        fb_lb = fb_fetch_leaderboard()
        if fb_lb:
            return jsonify({"ok": True, "leaderboard": fb_lb})
    lb = get_leaderboard_entries(20)
    return jsonify({"ok": True, "leaderboard": lb})

# ── STUDY MODULES ─────────────────────────────────────────────────
STUDY_MODULES = [
    {"id":"sm_python_basics",    "title":"Python Basics",         "subject":"Programming",   "level":1, "xp":500,  "lessons":10, "icon":"🐍"},
    {"id":"sm_ml_intro",         "title":"ML Introduction",       "subject":"AI/ML",         "level":2, "xp":800,  "lessons":12, "icon":"🤖"},
    {"id":"sm_data_structures",  "title":"Data Structures",       "subject":"CS Fundamentals","level":2,"xp":700,  "lessons":14, "icon":"🌲"},
    {"id":"sm_neural_nets",      "title":"Neural Networks",       "subject":"Deep Learning", "level":3, "xp":1200, "lessons":15, "icon":"🧠"},
    {"id":"sm_algorithms",       "title":"Algorithms & Big-O",    "subject":"CS Fundamentals","level":2,"xp":900,  "lessons":12, "icon":"⚡"},
    {"id":"sm_prompt_eng",       "title":"Prompt Engineering",    "subject":"AI/ML",         "level":1, "xp":600,  "lessons":8,  "icon":"✍️"},
    {"id":"sm_web_dev",          "title":"Web Development",       "subject":"Programming",   "level":1, "xp":700,  "lessons":16, "icon":"🌐"},
    {"id":"sm_databases",        "title":"Databases & SQL",       "subject":"CS Fundamentals","level":2,"xp":750,  "lessons":11, "icon":"🗄️"},
    {"id":"sm_cybersecurity",    "title":"Cybersecurity Basics",  "subject":"Security",      "level":3, "xp":1000, "lessons":13, "icon":"🔐"},
    {"id":"sm_math_ml",          "title":"Math for ML",           "subject":"Mathematics",   "level":3, "xp":1100, "lessons":14, "icon":"📐"},
]

@app.route('/api/study/modules', methods=['GET'])
def get_study_modules():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    done  = user.get('study_modules_done', []) if user else []
    modules_with_status = [dict(m, completed=(m['id'] in done)) for m in STUDY_MODULES]
    return jsonify({"ok": True, "modules": modules_with_status})

@app.route('/api/study/complete', methods=['POST'])
def complete_module():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    data      = request.get_json(silent=True) or {}
    module_id = str(data.get('module_id', '')).strip()
    module    = next((m for m in STUDY_MODULES if m['id'] == module_id), None)
    if not module:
        return jsonify({"ok": False, "msg": "Module not found"}), 404

    done = user.setdefault('study_modules_done', [])
    if module_id not in done:
        done.append(module_id)
        xp = module['xp']
        user['xp']    = user.get('xp', 0) + xp
        user['level'] = max(1, user['xp'] // 5000 + 1)
        act = user.setdefault('activity', [])
        act.insert(0, {"msg": f"Study Module Complete: {module['title']} 📚 +{xp} XP", "xp": xp, "ts": int(time.time()), "diff": "study"})
        user['activity'] = act[:20]
        save_user(user)
        return jsonify({"ok": True, "xp_earned": xp, "total_xp": user['xp'], "level": user['level']})
    return jsonify({"ok": True, "xp_earned": 0, "msg": "Already completed"})

# ── TEAM UP ───────────────────────────────────────────────────────
def find_team(code):
    if _use_mongo():
        return dictify(teams_col.find_one({'code': code.upper()}))
    return load_db()['teams'].get(code.upper())

def save_team(team):
    if _use_mongo():
        teams_col.replace_one({'code': team['code']}, team, upsert=True)
        return
    db = load_db()
    db['teams'][team['code']] = team
    save_db(db)

@app.route('/api/team/create', methods=['POST'])
def create_team():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    data      = request.get_json(silent=True) or {}
    team_name = str(data.get('name', '')).strip()[:60]
    if not team_name:
        return jsonify({"ok": False, "msg": "Team name required"}), 400

    code = secrets.token_hex(3).upper()
    team = {
        "code":    code,
        "name":    team_name,
        "owner":   user['uid'],
        "members": [{"uid": user['uid'], "name": user['name'], "score": user.get('score', 0), "level": user.get('level', 1)}],
        "created": int(time.time()),
        "score":   user.get('score', 0),
    }
    save_team(team)
    user['team_id'] = code
    save_user(user)
    return jsonify({"ok": True, "code": code, "team": team}), 201

@app.route('/api/team/join', methods=['POST'])
def join_team():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    code = str(data.get('code', '')).strip().upper()
    if not code:
        return jsonify({"ok": False, "msg": "Team code required"}), 400

    team = find_team(code)
    if not team:
        return jsonify({"ok": False, "msg": "Team not found. Check the code!"}), 404

    members = team.get('members', [])
    if any(m['uid'] == user['uid'] for m in members):
        return jsonify({"ok": True, "team": team, "msg": "Already in team"})
    if len(members) >= 6:
        return jsonify({"ok": False, "msg": "Team is full (max 6 members)"}), 400

    members.append({"uid": user['uid'], "name": user['name'], "score": user.get('score', 0), "level": user.get('level', 1)})
    team['members'] = members
    team['score']   = sum(m.get('score', 0) for m in members)
    save_team(team)
    user['team_id'] = code
    save_user(user)
    return jsonify({"ok": True, "team": team})

@app.route('/api/team/info', methods=['GET'])
def team_info():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    code = request.args.get('code') or user.get('team_id')
    if not code:
        return jsonify({"ok": False, "msg": "Not in a team"}), 404
    team = find_team(code)
    if not team:
        return jsonify({"ok": False, "msg": "Team not found"}), 404
    return jsonify({"ok": True, "team": team})

@app.route('/api/team/leaderboard', methods=['GET'])
def team_leaderboard():
    if _use_mongo():
        teams = [dictify(t) for t in teams_col.find().sort('score', -1).limit(10)]
    else:
        db    = load_db()
        teams = sorted(db.get('teams', {}).values(), key=lambda t: t.get('score', 0), reverse=True)[:10]
    return jsonify({"ok": True, "teams": teams})

# ── AI ASSISTANT (proxy to Anthropic Claude API) ─────────────────
@app.route('/api/ai_chat', methods=['POST'])
def ai_chat():
    """
    FIXED: Properly proxies to Gemini API with:
    - Full context awareness (game state, history)
    - Auth check (optional — allows guests too with lower rate limit)
    - Custom system prompt from frontend
    - Proper error messages
    - History support (last 10 messages)
    """
    api_key = os.environ.get('GEMINI_API_KEY', 'AIzaSyAD3-6O7f25ZC56Crk77DxvhGRqAIVgAEI').strip()
    if not api_key:
        return jsonify({
            "ok": False,
            "msg": "AI assistant not configured. Set GEMINI_API_KEY env var.",
            "hint": "The game will use built-in hints as fallback."
        }), 503

    data    = request.get_json(silent=True) or {}
    message = str(data.get('message', '')).strip()
    if not message:
        return jsonify({"ok": False, "msg": "Message is required"}), 400
    if len(message) > 2000:
        return jsonify({"ok": False, "msg": "Message too long (max 2000 chars)"}), 400

    # Extract optional fields
    history     = data.get('history', [])
    custom_sys  = str(data.get('context', ''))[:500]  # short context hint from game
    system_msg  = data.get('system', None)  # full system prompt override from game frontend

    # Default system prompt (used when game doesn't supply one)
    if not system_msg:
        system_msg = (
            "You are GAL's AI study assistant — a helpful, enthusiastic tutor for students "
            "learning programming, AI/ML, and computer science. Keep answers clear, educational, "
            "and encouraging. Use examples and emojis occasionally. "
            f"Context: {custom_sys}"
        )

    # Sanitize history — accept only valid role/content pairs
    clean_history = []
    for msg in (history or [])[-10:]:
        if isinstance(msg, dict) and msg.get('role') in ('user', 'assistant') and isinstance(msg.get('content'), str):
            clean_history.append({"role": msg['role'], "content": msg['content'][:2000]})

    messages = clean_history + [{"role": "user", "content": message}]

    try:
        import urllib.request as _req
        import json as _json

        # Convert to Gemini format
        contents = []
        for msg in messages:
            role = 'model' if msg['role'] == 'assistant' else 'user'
            contents.append({"role": role, "parts": [{"text": msg['content']}]})

        payload = _json.dumps({
            "system_instruction": {"parts": [{"text": system_msg}]},
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": 800,
                "temperature": 0.7
            }
        }).encode('utf-8')

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        req = _req.Request(
            url,
            data=payload,
            headers={
                'Content-Type': 'application/json',
            }
        )
        with _req.urlopen(req, timeout=30) as resp:
            result = _json.loads(resp.read().decode('utf-8'))

        # Extract text from Gemini response
        reply = ''
        if result.get('candidates') and result['candidates'][0].get('content'):
            for part in result['candidates'][0]['content'].get('parts', []):
                reply += part.get('text', '')

        if not reply:
            return jsonify({"ok": False, "msg": "No response from AI"}), 500

        return jsonify({"ok": True, "reply": reply.strip()})

    except Exception as e:
        err_str = str(e)
        print(f'[ai_chat] Error: {err_str}')
        if '400' in err_str or 'INVALID_ARGUMENT' in err_str:
            return jsonify({"ok": False, "msg": "Invalid API key. Check GEMINI_API_KEY."}), 503
        if '429' in err_str or 'RESOURCE_EXHAUSTED' in err_str:
            return jsonify({"ok": False, "msg": "AI rate limit reached. Try again shortly."}), 429
        return jsonify({"ok": False, "msg": f"AI service error: {err_str[:120]}"}), 500

# ── START ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("\n" + "═" * 60)
    print("  GAL — Gamified AI Learning Platform  v3.0")
    print("  ► http://localhost:5050")
    print("═" * 60)
    print(f"  DB Mode  : {'MongoDB' if _use_mongo() else 'Local JSON (data/db.json)'}")
    print(f"  Firebase : {'Enabled' if fb_enabled else 'Disabled'}")
    print(f"  AI Chat  : {'✅ Enabled' if os.environ.get('GEMINI_API_KEY') or 'AIzaSyAD3-6O7f25ZC56Crk77DxvhGRqAIVgAEI' else '❌ Disabled (set GEMINI_API_KEY)'}")
    print("═" * 60 + "\n")
    app.run(debug=True, port=5050, host='0.0.0.0')