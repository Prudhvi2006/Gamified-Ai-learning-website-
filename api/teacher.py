"""
api/teacher.py
==============
Blueprint: Teacher endpoints
  GET /api/teacher/students         — list students
  GET /api/teacher/student/<uid>    — get student details
  GET /api/teacher/class-stats      — aggregate class statistics
"""

import time
from flask import Blueprint, request, jsonify
from datetime import datetime
from core.db import get_all_users, find_user_by_uid, get_user_from_token

bp = Blueprint('teacher', __name__)


def _is_teacher(token_str):
    """Check if the user associated with token is a teacher."""
    user = get_user_from_token(token_str)
    if not user:
        return False
    return user.get('role') == 'teacher'


def _get_token_from_header():
    """Extract JWT token from Authorization header."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None


@bp.route('/api/teacher/students', methods=['GET'])
def get_students():
    """List all students with summary stats."""
    token = _get_token_from_header()
    if not token or not _is_teacher(token):
        return jsonify({'ok': False, 'msg': 'Unauthorized'}), 401
    
    all_users = get_all_users()
    students = []
    for user in all_users:
        if user.get('role') != 'teacher':
            students.append({
                'uid': user.get('uid'),
                'name': user.get('name'),
                'email': user.get('email'),
                'xp': user.get('xp', 0),
                'level': user.get('level', 1),
                'accuracy': user.get('accuracy', 0),
                'streak': user.get('streak', 0),
                'last_active': user.get('last_active'),
            })
    
    return jsonify({'ok': True, 'students': students})


@bp.route('/api/teacher/student/<uid>', methods=['GET'])
def get_student_detail(uid):
    """Get detailed progress for a specific student."""
    token = _get_token_from_header()
    if not token or not _is_teacher(token):
        return jsonify({'ok': False, 'msg': 'Unauthorized'}), 401
    
    user = find_user_by_uid(uid)
    if not user:
        return jsonify({'ok': False, 'msg': 'Student not found'}), 404
    
    return jsonify({
        'ok': True,
        'student': {
            'uid': user.get('uid'),
            'name': user.get('name'),
            'email': user.get('email'),
            'xp': user.get('xp', 0),
            'level': user.get('level', 1),
            'accuracy': user.get('accuracy', 0),
            'streak': user.get('streak', 0),
            'rooms_cleared': user.get('rooms_cleared', 0),
            'total_questions': user.get('total_questions', 0),
            'correct_answers': user.get('correct_answers', 0),
            'last_active': user.get('last_active'),
            'join_date': user.get('join_date'),
            'games': user.get('games', {}),
        }
    })


@bp.route('/api/teacher/class-stats', methods=['GET'])
def get_class_stats():
    """Get aggregated class statistics."""
    token = _get_token_from_header()
    if not token or not _is_teacher(token):
        return jsonify({'ok': False, 'msg': 'Unauthorized'}), 401
    
    all_users = get_all_users()
    students = [u for u in all_users if u.get('role') != 'teacher']
    
    if not students:
        return jsonify({
            'ok': True,
            'stats': {
                'total_students': 0,
                'avg_xp': 0,
                'avg_accuracy': 0,
                'avg_level': 0,
                'active_today': 0,
                'top_performers': [],
            }
        })
    
    total_xp = sum(u.get('xp', 0) for u in students)
    total_accuracy = sum(u.get('accuracy', 0) for u in students)
    total_level = sum(u.get('level', 1) for u in students)
    
    # Count active users (last_active is a timestamp)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_ts = int(today_start.timestamp())
    
    active_today = 0
    for u in students:
        last_active_ts = u.get('last_active', 0)
        if isinstance(last_active_ts, int) and last_active_ts > today_start_ts:
            active_today += 1
    
    top_performers = sorted(students, key=lambda x: x.get('xp', 0), reverse=True)[:5]
    
    return jsonify({
        'ok': True,
        'stats': {
            'total_students': len(students),
            'avg_xp': round(total_xp / len(students), 2),
            'avg_accuracy': round(total_accuracy / len(students), 2),
            'avg_level': round(total_level / len(students), 2),
            'active_today': active_today,
            'top_performers': [
                {
                    'name': p.get('name'),
                    'email': p.get('email'),
                    'xp': p.get('xp', 0),
                    'accuracy': p.get('accuracy', 0),
                }
                for p in top_performers
            ],
        }
    })
