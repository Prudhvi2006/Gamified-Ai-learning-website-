# GAL — Gamified AI Learning Platform

> An immersive, game-based learning system for AI, programming, and computer science.
> Built with **Flask + Vanilla JS**. No build step required.

---

## Project Structure

```
Gamified-Ai-learning-website-LEVELUP-AI/
│
├── app.py                      # Flask entry point (routes + startup)
├── gal_config.js               # Shared frontend config (API key, base URL)
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (gitignored)
│
├── core/                       # Backend core modules
│   ├── config.py               # Env vars, MongoDB, Firebase setup
│   ├── db.py                   # DB helpers (JSON + MongoDB dual-mode)
│   └── firebase.py             # Firebase Realtime Database helpers
│
├── api/                        # Flask Blueprints (one file per route group)
│   ├── auth.py                 # POST /api/register  /api/login  /api/logout
│   ├── profile.py              # GET  /api/profile   POST /api/update_stats
│   ├── progress.py             # GET  /api/progress  POST /api/progress/complete_level
│   ├── leaderboard.py          # GET  /api/leaderboard
│   ├── study.py                # GET  /api/study/modules  POST /api/study/complete
│   ├── team.py                 # POST /api/team/create    POST /api/team/join
│   │                           # GET  /api/team/info       GET  /api/team/leaderboard
│   └── ai_chat.py              # POST /api/ai_chat (Gemini proxy)
│
├── static/
│   └── js/
│       ├── gal-telemetry.js    # Async fire-and-forget event tracking
│       └── gal-charts.js       # Canvas chart library (Radar, Line, Bar, Ring)
│
├── data/
│   └── db.json                 # Local JSON database (auto-created)
│
└── pages/                      # HTML game pages (served directly by Flask)
    ├── index.html              # Landing / auth page
    ├── dashboard.html          # Player dashboard
    ├── hauntedmansion.html     # Game: Haunted Mansion
    ├── codered.html            # Game: Code Red
    ├── shadowquery.html        # Game: Shadow Query
    ├── treasurehunt.html       # Game: Treasure Hunt
    └── gemini-chat.html        # AI Chat page
```

---

## Quick Start

```bash
# 1. Install Python dependencies
pip install flask python-dotenv pymongo

# 2. Run the server
python app.py

# 3. Open http://localhost:5050
```

---

## Environment Variables (`.env`)

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `MONGODB_URI` | Optional | MongoDB Atlas connection string (falls back to local JSON) |
| `MONGODB_DB` | Optional | Database name (default: `gal`) |
| `FIREBASE_CRED_PATH` | Optional | Path to Firebase service account JSON |
| `FIREBASE_DB_URL` | Optional | Firebase Realtime Database URL |

---

## API Reference

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/register` | Create account |
| POST | `/api/login` | Login |
| POST | `/api/logout` | Logout |

### Player
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/profile` | Get full profile |
| POST | `/api/update_stats` | Submit game score / XP |
| GET | `/api/leaderboard` | Top 20 players |

### Game Progress
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/progress` | Get per-game level progress |
| POST | `/api/progress/complete_level` | Mark a level complete |

### Study
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/study/modules` | List all modules + completion status |
| POST | `/api/study/complete` | Mark a module complete |

### Team
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/team/create` | Create a team |
| POST | `/api/team/join` | Join by code |
| GET | `/api/team/info` | Get team details |
| GET | `/api/team/leaderboard` | Top 10 teams |

### AI
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ai_chat` | Chat with Gemini AI tutor |

### Misc
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Server health + feature flags |

---

## Frontend Modules

### `gal_config.js`
Loaded by every HTML page. Centralises API base URL and Gemini key.

### `static/js/gal-telemetry.js`
```js
import { Telemetry } from '/static/js/gal-telemetry.js';
Telemetry.startSession('haunted_mansion');
Telemetry.logEvent('answer_correct', { level: 3 });
Telemetry.endSession({ score: 1500, accuracy: 92 });
```

### `static/js/gal-charts.js`
```js
// Radar chart
GALCharts.radar('myCanvas', ['Python', 'ML', 'SQL'], [0.8, 0.6, 0.9]);

// Line chart (XP trend)
GALCharts.line('xpCanvas', ['Mon','Tue','Wed'], [250, 800, 500]);

// Accuracy ring
GALCharts.ring('ringCanvas', 87, 100, 'ACCURACY');
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + Flask 3.x |
| Database | Local JSON (dev) / MongoDB Atlas (prod) |
| Realtime | Firebase Realtime Database (optional) |
| AI | Google Gemini 2.0 Flash |
| Frontend | Vanilla HTML/CSS/JS (no build step) |
| Charts | Custom Canvas API library |
