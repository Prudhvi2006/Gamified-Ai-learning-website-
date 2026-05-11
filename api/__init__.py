"""
api package — Flask Blueprints for every route group.

Registration order (imported and registered in app.py):
  auth        /api/register  /api/login  /api/logout
  profile     /api/profile   /api/update_stats
  progress    /api/progress  /api/progress/complete_level
  leaderboard /api/leaderboard
  study       /api/study/*
  team        /api/team/*
  ai_chat     /api/ai_chat
"""
