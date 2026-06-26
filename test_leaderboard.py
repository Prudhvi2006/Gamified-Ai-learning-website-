"""
test_leaderboard.py
===================
Quick test of the leaderboard endpoint.
"""

import requests
import json

API_BASE = 'http://localhost:5050'

def test_leaderboard():
    """Test basic leaderboard fetch."""
    print("Testing GET /api/leaderboard...")
    resp = requests.get(f'{API_BASE}/api/leaderboard')
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    if data.get('ok'):
        entries = data.get('entries', [])
        print(f"\nTotal entries: {len(entries)}")
        for i, entry in enumerate(entries[:5], 1):
            print(f"  {i}. {entry.get('name')} - XP: {entry.get('xp')}, Level: {entry.get('level')}")

if __name__ == '__main__':
    test_leaderboard()
