/**
 * Single source of truth for all client-side constants.
 * Import in app.js: import { ... } from './constants.js'
 * Or access as window.C after <script src="constants.js"> (non-module usage).
 */

const C = {
  // ── API ────────────────────────────────────────────────────────────────────
  /** Dev server port — must match server DEFAULT_PORT */
  DEV_PORT: 3000,

  // ── Dashboard copy ─────────────────────────────────────────────────────────
  BRAND_NAME: "Observe Insurance",
  DASHBOARD_TITLE: "VoiceAI Claims Dashboard",

  // ── Outcome / sentiment values (must match server derive_outcome output) ───
  OUTCOMES: Object.freeze(["resolved", "escalated", "auth_failed"]),
  SENTIMENTS: Object.freeze(["positive", "neutral", "negative"]),
}

// Allow non-module <script> usage: window.C
if (typeof window !== "undefined") window.C = C
