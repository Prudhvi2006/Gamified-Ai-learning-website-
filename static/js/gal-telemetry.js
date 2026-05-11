/**
 * static/js/gal-telemetry.js — GAL Async Telemetry Client
 * =========================================================
 * Fire-and-forget session + event tracking.
 * Gameplay is NEVER blocked by telemetry calls.
 *
 * Usage (add 3 lines to any game page):
 *   import { Telemetry } from '/static/js/gal-telemetry.js';
 *   Telemetry.startSession('haunted_mansion');
 *   // ...gameplay...
 *   Telemetry.endSession({ score: 500, accuracy: 87 });
 */

const _API  = () => (window.GAL_CONFIG?.API_BASE ?? window.location.origin);
const _tok  = () => localStorage.getItem('gal_token') ?? '';
const _dbg  = (...a) => window.GAL_CONFIG?.DEBUG && console.debug('[Telemetry]', ...a);

// ── Local buffer (survives temporary backend outages) ────────────
const _BUFFER_KEY = 'gal_telemetry_buffer';
const _buf = {
  get: () => { try { return JSON.parse(localStorage.getItem(_BUFFER_KEY) ?? '[]'); } catch { return []; } },
  add: (e) => { const b = _buf.get(); b.push(e); localStorage.setItem(_BUFFER_KEY, JSON.stringify(b.slice(-50))); },
  clear: ()  => localStorage.removeItem(_BUFFER_KEY),
};

// ── Retry fetch (exponential back-off, max 3 attempts) ──────────
async function _post(path, body, attempt = 0) {
  try {
    const res = await fetch(`${_API()}${path}`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${_tok()}` },
      body:    JSON.stringify(body),
    });
    return res.ok;
  } catch (err) {
    if (attempt < 2) {
      await new Promise(r => setTimeout(r, 300 * 2 ** attempt));
      return _post(path, body, attempt + 1);
    }
    _dbg('failed after 3 attempts:', path, err.message);
    return false;
  }
}

// ── Event batch queue (debounced 250 ms) ────────────────────────
let _sessionId = null;
let _gameId    = null;
let _queue     = [];
let _timer     = null;

function _flush() {
  if (!_queue.length || !_sessionId) return;
  const batch = _queue.splice(0);
  _dbg('flush', batch.length, 'events');
  _post('/api/game/session/event', { session_id: _sessionId, events: batch })
    .then(ok => { if (!ok) batch.forEach(e => _buf.add(e)); });
}

// ── Public API ───────────────────────────────────────────────────
export const Telemetry = {
  /**
   * Call once at game start.
   * @param {string} gameId  e.g. 'haunted_mansion'
   */
  startSession(gameId) {
    _gameId = gameId;
    _post('/api/game/session/start', { game_id: gameId })
      .then(ok => { if (!ok) _dbg('startSession failed — continuing offline'); });
    // Optimistic local ID so events can still be queued offline
    _sessionId = `local_${Date.now()}`;
    _dbg('session started', gameId);
  },

  /**
   * Log a gameplay event (batched, debounced).
   * @param {string} type    e.g. 'answer_correct', 'hint_used', 'room_cleared'
   * @param {object} payload Optional extra data
   */
  logEvent(type, payload = {}) {
    const event = { type, ts: Date.now(), ...payload };
    _queue.push(event);
    clearTimeout(_timer);
    _timer = setTimeout(_flush, 250);
    _dbg('event queued', type);
  },

  /**
   * Call at game end / page unload.
   * Uses sendBeacon so it survives page navigation.
   * @param {{ score, accuracy, rooms_cleared, hints_used }} stats
   */
  endSession(stats = {}) {
    clearTimeout(_timer);
    _flush(); // send remaining queued events first

    const body = JSON.stringify({
      session_id: _sessionId,
      game_id:    _gameId,
      ...stats,
    });

    // sendBeacon is fire-and-forget and works during page unload
    const sent = navigator.sendBeacon?.(
      `${_API()}/api/game/session/end`,
      new Blob([body], { type: 'application/json' })
    );
    if (!sent) {
      _post('/api/game/session/end', { session_id: _sessionId, game_id: _gameId, ...stats });
    }

    _dbg('session ended', stats);
    _sessionId = null;
    _gameId    = null;
  },
};

// ── Auto-end session on page unload ─────────────────────────────
window.addEventListener('pagehide', () => {
  if (_sessionId) Telemetry.endSession({});
});
