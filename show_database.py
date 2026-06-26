"""
show_database.py
================
Display summary of all users in the database.
"""

import json
import os

DB_FILE = 'data/db.json'

def show_database():
    """Show all users in database."""
    if not os.path.exists(DB_FILE):
        print(f"Database file not found: {DB_FILE}")
        return
    
    with open(DB_FILE, 'r') as f:
        db = json.load(f)
    
    users = db.get('users', [])
    print(f"\n{'='*80}")
    print(f"Database Summary: {len(users)} users")
    print(f"{'='*80}\n")
    
    for i, user in enumerate(users, 1):
        print(f"{i:2}. {user.get('name', 'N/A'):25} | {user.get('email', 'N/A'):30}")
        print(f"    UID: {user.get('uid')}")
        print(f"    XP: {user.get('xp', 0):6} | Level: {user.get('level', 1)} | Streak: {user.get('streak', 0)}")
        print(f"    Accuracy: {user.get('accuracy', 0)}% | Rooms Cleared: {user.get('rooms_cleared', 0)}")
        print(f"    Last Active: {user.get('last_active', 'N/A')}")
        print()

if __name__ == '__main__':
    show_database()
