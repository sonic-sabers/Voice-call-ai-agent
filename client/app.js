// C is loaded by constants.js (see index.html)
const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? `${window.location.protocol}//${window.location.hostname}:${C.DEV_PORT}`
  : ""  // same origin on Render

let _lastData = []

// ── Audio player state ────────────────────────────────────────────────────────
let _audio = null
let _rafId = null

function stopAudio() {
  if (_audio) {
    _audio.pause()
    _audio = null
  }
  if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null }
}

function initAudioPlayer(url) {
  stopAudio()
  _audio = new Audio(url)
  _audio.crossOrigin = "anonymous"

  const player   = document.getElementById("audio-player")
  const playBtn  = document.getElementById("ap-play")
  const progress = document.getElementById("ap-progress")
  const fill     = document.getElementById("ap-fill")
  const thumb    = document.getElementById("ap-thumb")
  const current  = document.getElementById("ap-current")
  const duration = document.getElementById("ap-duration")
  const volSlider = document.getElementById("ap-vol")

  player.style.display = ""

  function fmt(s) {
    if (!isFinite(s)) return "0:00"
    const m = Math.floor(s / 60), sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, "0")}`
  }

  function tick() {
    if (!_audio) return
    const pct = _audio.duration ? (_audio.currentTime / _audio.duration) * 100 : 0
    fill.style.width  = pct + "%"
    thumb.style.left  = pct + "%"
    current.textContent = fmt(_audio.currentTime)
    _rafId = requestAnimationFrame(tick)
  }

  _audio.addEventListener("loadedmetadata", () => {
    duration.textContent = fmt(_audio.duration)
  })

  _audio.addEventListener("play", () => {
    playBtn.innerHTML = pauseIcon()
    _rafId = requestAnimationFrame(tick)
  })

  _audio.addEventListener("pause", () => {
    playBtn.innerHTML = playIcon()
    if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null }
  })

  _audio.addEventListener("ended", () => {
    playBtn.innerHTML = playIcon()
    fill.style.width = "0%"
    thumb.style.left = "0%"
    current.textContent = "0:00"
    if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null }
  })

  playBtn.onclick = () => {
    if (_audio.paused) _audio.play().catch(() => {})
    else _audio.pause()
  }

  progress.onclick = (e) => {
    if (!_audio.duration) return
    const rect = progress.getBoundingClientRect()
    const ratio = (e.clientX - rect.left) / rect.width
    _audio.currentTime = ratio * _audio.duration
  }

  volSlider.oninput = () => { if (_audio) _audio.volume = volSlider.value }

  _audio.play().catch(() => {})
}

function playIcon() {
  return `<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M8 5v14l11-7z"/></svg>`
}
function pauseIcon() {
  return `<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`
}

// ── Detail drawer ─────────────────────────────────────────────────────────────
function openDrawer(row, autoPlay = false) {
  document.getElementById("drawer-caller-name").textContent = row.caller_name || "Unknown"
  document.getElementById("drawer-caller-phone").textContent = row.caller_phone || "—"
  document.getElementById("drawer-time").textContent = formatTime(row.timestamp)

  const sentimentEl = document.getElementById("drawer-sentiment")
  sentimentEl.textContent = row.sentiment || ""
  sentimentEl.className = `badge badge-${esc(row.sentiment)}`

  const outcomeEl = document.getElementById("drawer-outcome")
  outcomeEl.textContent = (row.outcome || "").replace("_", " ")
  outcomeEl.className = `badge badge-${esc(row.outcome)}`

  document.getElementById("drawer-summary").textContent = row.summary || "No summary available."

  const transcriptEl = document.getElementById("drawer-transcript")
  if (row.transcript) {
    transcriptEl.textContent = row.transcript
    transcriptEl.parentElement.style.display = ""
  } else {
    transcriptEl.parentElement.style.display = "none"
  }

  // Audio player
  const player = document.getElementById("audio-player")
  if (row.recording_url) {
    document.getElementById("ap-play").innerHTML = playIcon()
    document.getElementById("ap-fill").style.width = "0%"
    document.getElementById("ap-thumb").style.left = "0%"
    document.getElementById("ap-current").textContent = "0:00"
    document.getElementById("ap-duration").textContent = "0:00"
    player.style.display = ""
    if (autoPlay) initAudioPlayer(row.recording_url)
    else {
      stopAudio()
      document.getElementById("ap-play").onclick = () => initAudioPlayer(row.recording_url)
    }
  } else {
    player.style.display = "none"
    stopAudio()
  }

  // Transcript link only
  const linksEl = document.getElementById("drawer-links")
  const linksSection = document.getElementById("drawer-links-section")
  if (row.transcript_url) {
    linksEl.innerHTML = `<a class="drawer-link-btn" href="${row.transcript_url}" target="_blank" rel="noopener">📄 Transcript</a>`
    linksSection.style.display = ""
  } else {
    linksSection.style.display = "none"
  }

  document.getElementById("drawer-overlay").classList.add("open")
  document.getElementById("detail-drawer").classList.add("open")
  document.body.style.overflow = "hidden"
}

function closeDrawer() {
  stopAudio()
  document.getElementById("drawer-overlay").classList.remove("open")
  document.getElementById("detail-drawer").classList.remove("open")
  document.body.style.overflow = ""
}

window.closeDrawer = closeDrawer

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDrawer()
})

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

  const tbody = document.getElementById("table-body")
  tbody.innerHTML = rows.map((r, i) => {
    const ts = formatTime(r.timestamp)
    const playCell = r.recording_url
      ? `<button class="row-play-btn" data-idx="${i}" aria-label="Play recording" onclick="event.stopPropagation()">
           <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14"><path d="M8 5v14l11-7z"/></svg>
         </button>`
      : `<span class="muted">—</span>`
    return `
      <tr class="clickable-row" data-idx="${i}">
        <td class="time-cell">${ts}</td>
        <td>
          <div class="caller-name">${esc(r.caller_name)}</div>
          <div class="caller-phone">${esc(r.caller_phone)}</div>
        </td>
        <td><div class="summary-clickable" title="Click to view details">${esc(r.summary)}</div></td>
        <td><span class="badge badge-${esc(r.sentiment)}">${esc(r.sentiment)}</span></td>
        <td><span class="badge badge-${esc(r.outcome)}">${esc(r.outcome).replace("_", " ")}</span></td>
        <td>${playCell}</td>
      </tr>
    `
  }).join("")

  tbody.querySelectorAll("tr.clickable-row").forEach(tr => {
    tr.addEventListener("click", () => {
      const idx = parseInt(tr.dataset.idx, 10)
      openDrawer(rows[idx])
    })
  })

  tbody.querySelectorAll(".row-play-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation()
      const idx = parseInt(btn.dataset.idx, 10)
      openDrawer(rows[idx], true)
    })
  })
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
