"""
create_teacher.py
=================
Create a teacher account in the database.
"""

import json
import os
import secrets
import hashlib
import time

DB_FILE = 'data/db.json'

def hash_pass(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_teacher(name, email, password):
    """Create a teacher account."""
    if not os.path.exists(DB_FILE):
        print(f"Database file not found: {DB_FILE}")
        return False
    
    with open(DB_FILE, 'r') as f:
        db = json.load(f)
    
    users = db.get('users', {})
    
    if email in users:
        print(f"Email {email} already exists!")
        return False
    
    uid = 'u_' + secrets.token_hex(8)
    token = secrets.token_hex(32)
    today = time.strftime('%Y-%m-%d')
    
    user = {
        'uid': uid,
        'name': name,
        'email': email,
        'hash': hash_pass(password),
        'role': 'teacher',
        'class_name': '',
        'grade': '',
        'joined': int(time.time()),
        'xp': 0,
        'level': 1,
        'streak': 0,
        'last_active': int(time.time()),
        'rooms_cleared': 0,
        'missions_done': 0,
        'score': 0,
        'accuracy': 0,
        'hints_used': 0,
        'best_combo': 1,
        'achievements': [],
        'activity': [{
            'msg': 'Teacher account created',
            'xp': 0,
            'ts': int(time.time()),
            'diff': 'system',
        }],
        'streak_days': [today],
        'study_modules_done': [],
        'team_id': None,
        'game_progress': {
            'haunted_mansion': {'levels_done': [], 'unlocked': True},
            'code_red': {'levels_done': [], 'unlocked': False},
            'ai_labyrinth': {'levels_done': [], 'unlocked': False},
        },
    }
    
    users[email] = user
    db['users'] = users
    
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=2)
    
    print(f"✓ Teacher created successfully!")
    print(f"  Email: {email}")
    print(f"  Name: {name}")
    print(f"  UID: {uid}")
    return True

if __name__ == '__main__':
    create_teacher('Mr. Anderson', 'teacher@example.com', 'teacher123')
