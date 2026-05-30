// C is loaded by constants.js (see index.html)
const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? `${window.location.protocol}//${window.location.hostname}:${C.DEV_PORT}`
  : ""  // same origin on Railway

let _lastData = []

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
