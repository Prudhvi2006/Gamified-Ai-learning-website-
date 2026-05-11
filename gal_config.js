/**
 * gal_config.js — GAL Shared Frontend Configuration
 * ===================================================
 * Loaded by every HTML page via: <script src="gal_config.js"></script>
 *
 * All pages read from window.GAL_CONFIG instead of hardcoding values,
 * so you only ever need to update this one file.
 */

window.GAL_CONFIG = {
  // ── Backend ──────────────────────────────────────────────────
  API_BASE: window.location.origin,

  // ── Gemini AI ────────────────────────────────────────────────
  GEMINI_API_KEY: 'AIzaSyBcqfDyc5l1XWjCRp8u7w8oYdjyZx0rVtE',
  GEMINI_MODEL:   'gemini-2.0-flash',

  // ── Feature flags ────────────────────────────────────────────
  TELEMETRY_ENABLED: true,   // set false to disable analytics tracking
  DEBUG:             false,  // set true for verbose console logs
};

// Convenience shorthand used in older game pages
window.GAL_API = window.GAL_CONFIG.API_BASE;
