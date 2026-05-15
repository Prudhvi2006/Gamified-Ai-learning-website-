"""
test_real_leaderboard.py
========================
Test that the leaderboard filters real active users correctly.
"""

import requests
import json

API_BASE = 'http://localhost:5050'

def test_real_leaderboard():
    """Test that leaderboard shows only 'real' active users."""
    print("Testing GET /api/leaderboard (real users filter)...\n")
    resp = requests.get(f'{API_BASE}/api/leaderboard')
    print(f"Status: {resp.status_code}")
    
    data = resp.json()
    if not data.get('ok'):
        print(f"Error: {data.get('msg')}")
        return
    
    entries = data.get('entries', [])
    print(f"Real users (filtered): {len(entries)}\n")
    
    # Count by engagement criteria
    engaged = 0
    for entry in entries:
        xp = entry.get('xp', 0)
        rooms = entry.get('rooms_cleared', 0)
        streak = entry.get('streak', 0)
        acc = entry.get('accuracy', 0)
        
        if xp > 250 or rooms > 0 or streak > 1 or acc > 0:
            engaged += 1
        
        print(f"{entry.get('name'):20} | XP:{xp:6} | Rooms:{rooms} | Streak:{streak} | Acc:{acc}%")
    
    print(f"\nEngaged users: {engaged}/{len(entries)}")

if __name__ == '__main__':
    test_real_leaderboard()
