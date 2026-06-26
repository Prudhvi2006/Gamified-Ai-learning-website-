"""
api/study.py
============
Blueprint: /api/study/modules   /api/study/complete
"""

import time
from flask import Blueprint, request, jsonify
from core.db import get_user_from_token, save_user

bp = Blueprint('study', __name__)

# ── Study module catalogue ──────────────────────────────────────────
STUDY_MODULES = [
    {'id': 'sm_python_basics',   'title': 'Python Basics',        'subject': 'Programming',    'level': 1, 'xp': 500,  'lessons': 10, 'icon': '🐍'},
    {'id': 'sm_ml_intro',        'title': 'ML Introduction',      'subject': 'AI/ML',          'level': 2, 'xp': 800,  'lessons': 12, 'icon': '🤖'},
    {'id': 'sm_data_structures', 'title': 'Data Structures',      'subject': 'CS Fundamentals','level': 2, 'xp': 700,  'lessons': 14, 'icon': '🌲'},
    {'id': 'sm_neural_nets',     'title': 'Neural Networks',      'subject': 'Deep Learning',  'level': 3, 'xp': 1200, 'lessons': 15, 'icon': '🧠'},
    {'id': 'sm_algorithms',      'title': 'Algorithms & Big-O',   'subject': 'CS Fundamentals','level': 2, 'xp': 900,  'lessons': 12, 'icon': '⚡'},
    {'id': 'sm_prompt_eng',      'title': 'Prompt Engineering',   'subject': 'AI/ML',          'level': 1, 'xp': 600,  'lessons': 8,  'icon': '✍️'},
    {'id': 'sm_web_dev',         'title': 'Web Development',      'subject': 'Programming',    'level': 1, 'xp': 700,  'lessons': 16, 'icon': '🌐'},
    {'id': 'sm_databases',       'title': 'Databases & SQL',      'subject': 'CS Fundamentals','level': 2, 'xp': 750,  'lessons': 11, 'icon': '🗄️'},
    {'id': 'sm_cybersecurity',   'title': 'Cybersecurity Basics', 'subject': 'Security',       'level': 3, 'xp': 1000, 'lessons': 13, 'icon': '🔐'},
    {'id': 'sm_math_ml',         'title': 'Math for ML',          'subject': 'Mathematics',    'level': 3, 'xp': 1100, 'lessons': 14, 'icon': '📐'},
]


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/study/modules
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/study/modules', methods=['GET'])
def get_study_modules():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    done  = user.get('study_modules_done', []) if user else []
    modules = [dict(m, completed=(m['id'] in done)) for m in STUDY_MODULES]
    return jsonify({'ok': True, 'modules': modules})


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/study/complete
# ──────────────────────────────────────────────────────────────────────────────

@bp.route('/api/study/complete', methods=['POST'])
def complete_module():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return jsonify({'ok': False, 'msg': 'Unauthorized'}), 401

    data      = request.get_json(silent=True) or {}
    module_id = str(data.get('module_id', '')).strip()
    module    = next((m for m in STUDY_MODULES if m['id'] == module_id), None)
    if not module:
        return jsonify({'ok': False, 'msg': 'Module not found'}), 404

    done = user.setdefault('study_modules_done', [])
    if module_id in done:
        return jsonify({'ok': True, 'xp_earned': 0, 'msg': 'Already completed'})

    done.append(module_id)
    xp = module['xp']
    user['xp']    = user.get('xp', 0) + xp
    user['level'] = max(1, user['xp'] // 5000 + 1)

    act = user.setdefault('activity', [])
    act.insert(0, {
        'msg':  f'Study Module Complete: {module["title"]} 📚 +{xp} XP',
        'xp':   xp,
        'ts':   int(time.time()),
        'diff': 'study',
    })
    user['activity'] = act[:20]
    save_user(user)

    return jsonify({'ok': True, 'xp_earned': xp, 'total_xp': user['xp'], 'level': user['level']})
