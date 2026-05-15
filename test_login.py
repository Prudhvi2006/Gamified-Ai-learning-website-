"""
test_login.py
=============
Test login endpoint with different roles.
"""

import requests
import json

API_BASE = 'http://localhost:5050'

def test_login_student():
    """Test student login."""
    print("Testing POST /api/login (student)...\n")
    
    resp = requests.post(f'{API_BASE}/api/login', json={
        'email': 'student1@example.com',
        'password': 'password123',
        'role': 'student'
    })
    
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    if data.get('ok'):
        token = data.get('token')
        print(f"\nToken received: {token[:20]}...")
        print(f"UID: {data.get('uid')}")
        print(f"Name: {data.get('name')}")
        print(f"Role: {data.get('role')}")
    
    return data

def test_login_teacher():
    """Test teacher login."""
    print("\n\nTesting POST /api/login (teacher)...\n")
    
    # First create a teacher account if needed
    resp = requests.post(f'{API_BASE}/api/register', json={
        'name': 'Teacher One',
        'email': 'teacher1@example.com',
        'password': 'password123',
        'class_name': 'Grade 9',
        'grade': '9'
    })
    print(f"Register status: {resp.status_code}")
    
    # Now try to login with teacher role
    resp = requests.post(f'{API_BASE}/api/login', json={
        'email': 'teacher1@example.com',
        'password': 'password123',
        'role': 'teacher'
    })
    
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    return data

if __name__ == '__main__':
    test_login_student()
    test_login_teacher()
