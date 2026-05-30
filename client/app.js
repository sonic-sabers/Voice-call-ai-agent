// C is loaded by constants.js (see index.html)
const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? `${window.location.protocol}//${window.location.hostname}:${C.DEV_PORT}`
  : ""  // same origin on Render

let _lastData = []

// ── VAPI browser call ─────────────────────────────────────────────────────────
let _vapi = null
let _calling = false

async function initVapi() {
  if (_vapi) return _vapi
  const res = await fetch(`${API_BASE}/api/config`)
  if (!res.ok) throw new Error("Failed to load config")
  const { vapiPublicKey, vapiAssistantId } = await res.json()
  if (!vapiPublicKey) throw new Error("VAPI_PUBLIC_KEY not configured on server")

  const vapiMod = await import("https://esm.sh/@vapi-ai/web@2.5.2")
  const VapiClass = vapiMod.default
  if (typeof VapiClass !== "function") throw new Error("Vapi SDK failed to load — check network/CSP")
  _vapi = new VapiClass(vapiPublicKey)
  _vapi._assistantId = vapiAssistantId

  _vapi.on("call-end", () => {
    _calling = false
    setCallBtn(false)
    setTimeout(load, 3000)
  })
  _vapi.on("error", (e) => {
    console.error("VAPI error", e)
    _calling = false
    setCallBtn(false)
  })
  return _vapi
}

function setCallBtn(active) {
  const btn = document.getElementById("call-btn")
  const label = document.getElementById("call-label")
  const icon = document.getElementById("call-icon")
  btn.classList.toggle("active", active)
  label.textContent = active ? "End Call" : "Start Call"
  icon.textContent = active ? "⏹" : "📞"
  btn.disabled = false
}

async function toggleCall() {
  const btn = document.getElementById("call-btn")
  btn.disabled = true
  try {
    const vapi = await initVapi()
    if (_calling) {
      vapi.stop()
      _calling = false
      setCallBtn(false)
    } else {
      await vapi.start(vapi._assistantId)
      _calling = true
      setCallBtn(true)
    }
  } catch (e) {
    alert("Could not start call: " + e.message)
    btn.disabled = false
  }
}

// Expose to HTML onclick (module scripts don't pollute window automatically)
window.toggleCall = toggleCall

// ── Dashboard data ────────────────────────────────────────────────────────────
async function load() {
  const dot = document.getElementById("status-dot")
  try {
    const res = await fetch(`${API_BASE}/api/interactions`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    _lastData = data
    render(data)
    dot.className = "status-dot ok"
    document.getElementById("last-updated").textContent =
      `Updated ${new Date().toLocaleTimeString()} · ${C.REFRESH_LABEL}`
  } catch (e) {
    dot.className = "status-dot error"
    document.getElementById("last-updated").textContent = `Error: ${e.message}`
    if (_lastData.length === 0) {
      document.getElementById("table-body").innerHTML =
        `<tr><td colspan="6" class="empty">Failed to load — is the backend running?</td></tr>`
    }
  }
}

window.load = load

function render(rows) {
  rows.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))

  const total      = rows.length
  const resolved   = rows.filter(r => r.outcome === "resolved").length
  const escalated  = rows.filter(r => r.outcome === "escalated").length
  const authFailed = rows.filter(r => r.outcome === "auth_failed").length
  const containment = total > 0 ? Math.round((resolved / total) * 100) : 0

  const stats = [
    { title: "Total Calls",      value: total,              sub: "all time",            bar: null },
    { title: "Containment Rate", value: `${containment}%`,  sub: `${resolved} resolved`, bar: containment },
    { title: "Escalated",        value: escalated,          sub: `${pct(escalated, total)}% of calls`, bar: null },
    { title: "Auth Failures",    value: authFailed,         sub: `${rows.filter(r => r.sentiment === "positive").length} positive sentiment`, bar: null },
  ]

  document.getElementById("stats").innerHTML = stats.map(c => `
    <div class="card">
      <div class="card-title">${c.title}</div>
      <div class="card-value">${c.value}</div>
      <div class="card-sub">${c.sub}</div>
      ${c.bar !== null ? `<div class="card-bar"><div class="card-bar-fill" style="width:${c.bar}%"></div></div>` : ""}
    </div>
  `).join("")

  if (rows.length === 0) {
    document.getElementById("table-body").innerHTML =
      `<tr><td colspan="6" class="empty">No calls yet. Make a test call to see data here.</td></tr>`
    return
  }

  document.getElementById("table-body").innerHTML = rows.map(r => {
    const ts = formatTime(r.timestamp)
    const links = [
      r.recording_url  ? `<a class="link" href="${r.recording_url}"  target="_blank" rel="noopener">▶ Recording</a>`  : "",
      r.transcript_url ? `<a class="link" href="${r.transcript_url}" target="_blank" rel="noopener">📄 Transcript</a>` : "",
    ].join("")
    return `
      <tr>
        <td class="time-cell">${ts}</td>
        <td>
          <div class="caller-name">${esc(r.caller_name)}</div>
          <div class="caller-phone">${esc(r.caller_phone)}</div>
        </td>
        <td><div class="summary" title="${esc(r.summary)}">${esc(r.summary)}</div></td>
        <td><span class="badge badge-${esc(r.sentiment)}">${esc(r.sentiment)}</span></td>
        <td><span class="badge badge-${esc(r.outcome)}">${esc(r.outcome).replace("_", " ")}</span></td>
        <td>${links || "<span class='muted'>—</span>"}</td>
      </tr>
    `
  }).join("")
}

function pct(n, total) {
  return total > 0 ? Math.round((n / total) * 100) : 0
}

function formatTime(iso) {
  try {
    const d = new Date(iso)
    const today = new Date()
    const isToday = d.toDateString() === today.toDateString()
    if (isToday) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    return d.toLocaleDateString([], { month: "short", day: "numeric" }) + " " +
           d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  } catch {
    return iso
  }
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

load()
setInterval(load, C.POLL_INTERVAL_MS)
