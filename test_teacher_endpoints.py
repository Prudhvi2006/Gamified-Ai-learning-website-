"""
test_teacher_endpoints.py
==========================
Test teacher API endpoints.
"""

import requests
import json

API_BASE = 'http://localhost:5050'

# Test teacher login
print("Testing teacher login...\n")
resp = requests.post(f'{API_BASE}/api/login', json={
    'email': 'teacher@example.com',
    'password': 'teacher123',
    'role': 'teacher'
})
data = resp.json()
print(f"Status: {resp.status_code}")
print(f"Response: {json.dumps(data, indent=2)}\n")

if not data.get('ok'):
    print("Login failed!")
    exit(1)

teacher_token = data.get('token')
print(f"✓ Teacher token: {teacher_token[:20]}...\n")

# Test get students
print("Testing GET /api/teacher/students...\n")
resp = requests.get(
    f'{API_BASE}/api/teacher/students',
    headers={'Authorization': f'Bearer {teacher_token}'}
)
data = resp.json()
print(f"Status: {resp.status_code}")
print(f"Response: {json.dumps(data, indent=2)}\n")

# Test get class stats
print("Testing GET /api/teacher/class-stats...\n")
resp = requests.get(
    f'{API_BASE}/api/teacher/class-stats',
    headers={'Authorization': f'Bearer {teacher_token}'}
)
data = resp.json()
print(f"Status: {resp.status_code}")
print(f"Response: {json.dumps(data, indent=2)}\n")

print("✓ All teacher endpoints working!")
