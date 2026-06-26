/**
 * gal_config.js — GAL Shared Frontend Configuration
 * ===================================================
 * Loaded by every HTML page via: <script src="gal_config.js"></script>
 *
 * All pages read from window.GAL_CONFIG instead of hardcoding values,
 * so you only ever need to update this one file.
 */

// Cache-busting timestamp
const CONFIG_VERSION = Date.now();

window.GAL_CONFIG = {
  // ── Backend ──────────────────────────────────────────────────
  API_BASE: window.location.origin,
  AI_CHAT_ENDPOINT: window.location.origin + '/api/ai_chat',
  
  // ── Version control ──────────────────────────────────────────
  VERSION: CONFIG_VERSION,

  // ── Feature flags ────────────────────────────────────────────
  TELEMETRY_ENABLED: true,   // set false to disable analytics tracking
  DEBUG:             false,  // set true for verbose console logs
};

// Convenience shorthand used in older game pages
window.GAL_API = window.GAL_CONFIG.API_BASE;

/**
 * callAI() — Universal AI Chat Function with Automatic Fallback
 * ═══════════════════════════════════════════════════════════════
 * All games, chatbots, and AI features use this function.
 * Backend automatically handles API key fallback on quota/rate-limit errors.
 *
 * @param {string} message - User message
 * @param {array} history - Chat history (optional)
 * @param {string} systemPrompt - System prompt (optional)
 * @returns {Promise<{ok: boolean, reply?: string, msg?: string}>}
 */
async function callAI(message, history = [], systemPrompt = "You are a helpful AI assistant.") {
  try {
    const response = await fetch(window.GAL_CONFIG.AI_CHAT_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: message,
        history: history,
        system: systemPrompt
      })
    });

    const data = await response.json();
    return data;
  } catch (error) {
    return {
      ok: false,
      msg: `Network error: ${error.message}`
    };
  }
}
