// C is loaded by constants.js (see index.html)

const ESCALATION_LABELS = {
  representative_requested: "Representative Requested",
  unsupported_question: "Unsupported Question",
  verification_failed: "Verification Failed",
  emergency: "Emergency",
};
function escalationLabel(reason) {
  return ESCALATION_LABELS[reason] || reason.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1);
}
const API_BASE =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
    ? `${window.location.protocol}//${window.location.hostname}:${C.DEV_PORT}`
    : ""; // same origin on Render

let _lastData = [];
let _activeView = "customer";
let _selectedCallerPhone = null;
const UNKNOWN_CALLER_PHONE = "+19995550000";

function normalizePhone(phone) {
  const digits = String(phone || "").replace(/\D/g, "");
  if (!digits) return "";
  if (digits.length === 10) return `+1${digits}`;
  return `+${digits}`;
}

function formatPhone(phone) {
  const normalized = normalizePhone(phone);
  const digits = normalized.replace(/\D/g, "");
  if (digits.length === 11 && digits.startsWith("1")) {
    return `+1 ${digits.slice(1, 4)}-${digits.slice(4, 7)}-${digits.slice(7)}`;
  }
  return normalized || "Not available";
}

const CALLER_PROFILES = {
  "+14085550192": {
    phone: "+14085550192",
    first_name: "Maya",
    last_name: "Patel",
    dob: "1987-09-14",
    claim_id: "CLM-2847",
    claim_status: "approved",
    docs_required: "—",
    policy_number: "POL-100192",
    zip_code: "95110",
  },
  "+13125550371": {
    phone: "+13125550371",
    first_name: "Carlos",
    last_name: "Rivera",
    dob: "1992-04-03",
    claim_id: "CLM-3105",
    claim_status: "requires_documentation",
    docs_required: "radiology report, treating physician statement",
    policy_number: "POL-100371",
    zip_code: "60601",
  },
  "+17145550884": {
    phone: "+17145550884",
    first_name: "Amara",
    last_name: "Okonkwo",
    dob: "1979-11-28",
    claim_id: "CLM-4422",
    claim_status: "pending",
    docs_required: "—",
    policy_number: "POL-100884",
    zip_code: "92801",
  },
};

// ── Dashboard auth (disabled) ─────────────────────────────────────────────────
// const _SESSION_KEY = "observe_dashboard_token"
// let _authCancelled = false
// function getStoredSecret() { return sessionStorage.getItem(_SESSION_KEY) || "" }
// function promptForSecret() { ... }
// function authHeaders() { const secret = getStoredSecret(); return secret ? { "X-Dashboard-Secret": secret } : {} }
// function clearStoredSecret() { sessionStorage.removeItem(_SESSION_KEY) }

// ── Audio player state ────────────────────────────────────────────────────────
let _audio = null;
let _rafId = null;

function stopAudio() {
  if (_audio) {
    _audio.pause();
    _audio = null;
  }
  if (_rafId) {
    cancelAnimationFrame(_rafId);
    _rafId = null;
  }
}

function initAudioPlayer(url) {
  stopAudio();
  // Clear any previous error message before loading new audio.
  const prevErr = document.querySelector("#audio-player .ap-error");
  if (prevErr) prevErr.textContent = "";
  _audio = new Audio(url);
  _audio.crossOrigin = "anonymous";

  const player = document.getElementById("audio-player");
  const playBtn = document.getElementById("ap-play");
  const progress = document.getElementById("ap-progress");
  const fill = document.getElementById("ap-fill");
  const thumb = document.getElementById("ap-thumb");
  const current = document.getElementById("ap-current");
  const duration = document.getElementById("ap-duration");
  const volSlider = document.getElementById("ap-vol");

  player.style.display = "";

  function fmt(s) {
    if (!isFinite(s)) return "0:00";
    const m = Math.floor(s / 60),
      sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  }

  function tick() {
    if (!_audio) return;
    const pct = _audio.duration
      ? (_audio.currentTime / _audio.duration) * 100
      : 0;
    fill.style.width = pct + "%";
    thumb.style.left = pct + "%";
    current.textContent = fmt(_audio.currentTime);
    _rafId = requestAnimationFrame(tick);
  }

  _audio.addEventListener("loadedmetadata", () => {
    duration.textContent = fmt(_audio.duration);
  });

  _audio.addEventListener("play", () => {
    playBtn.innerHTML = pauseIcon();
    _rafId = requestAnimationFrame(tick);
  });

  _audio.addEventListener("pause", () => {
    playBtn.innerHTML = playIcon();
    if (_rafId) {
      cancelAnimationFrame(_rafId);
      _rafId = null;
    }
  });

  _audio.addEventListener("ended", () => {
    playBtn.innerHTML = playIcon();
    fill.style.width = "0%";
    thumb.style.left = "0%";
    current.textContent = "0:00";
    if (_rafId) {
      cancelAnimationFrame(_rafId);
      _rafId = null;
    }
  });

  playBtn.onclick = () => {
    if (_audio.paused)
      _audio.play().catch((err) => {
        console.warn("audio play failed:", err);
        showAudioError(
          "Playback failed — recording may be unavailable or blocked by browser security.",
        );
      });
    else _audio.pause();
  };

  progress.onclick = (e) => {
    if (!_audio.duration) return;
    const rect = progress.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    _audio.currentTime = ratio * _audio.duration;
  };

  _audio.addEventListener("error", () => {
    showAudioError(
      "Could not load recording — it may have expired or be unavailable.",
    );
  });

  volSlider.oninput = () => {
    if (_audio) _audio.volume = volSlider.value;
  };

  _audio.play().catch((err) => {
    showAudioError(
      "Playback failed — recording may be unavailable or blocked by browser security.",
    );
    console.warn("audio autoplay failed:", err);
  });
}

function showAudioError(msg) {
  const player = document.getElementById("audio-player");
  let errEl = player.querySelector(".ap-error");
  if (!errEl) {
    errEl = document.createElement("div");
    errEl.className = "ap-error";
    player.appendChild(errEl);
  }
  errEl.textContent = msg;
}

function playIcon() {
  return `<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M8 5v14l11-7z"/></svg>`;
}
function pauseIcon() {
  return `<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;
}
function phoneIcon() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.91.33 1.8.62 2.65a2 2 0 0 1-.45 2.11L8.09 9.67a16 16 0 0 0 6.24 6.24l1.19-1.19a2 2 0 0 1 2.11-.45c.85.29 1.74.5 2.65.62A2 2 0 0 1 22 16.92z"/></svg>`;
}
function stopIcon() {
  return `<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="2"/></svg>`;
}

// ── Detail drawer ─────────────────────────────────────────────────────────────
function openDrawer(row, autoPlay = false) {
  document.getElementById("drawer-caller-name").textContent =
    row.caller_name || "Unknown";
  document.getElementById("drawer-caller-phone").textContent =
    row.caller_phone || "Not available";
  document.getElementById("drawer-time").textContent = formatTime(
    row.timestamp,
  );

  const sentimentEl = document.getElementById("drawer-sentiment");
  sentimentEl.textContent = capitalize(row.sentiment || "");
  sentimentEl.className = `badge badge-${esc(row.sentiment)}`;

  const outcomeEl = document.getElementById("drawer-outcome");
  outcomeEl.textContent = capitalize((row.outcome || "").replace(/_/g, " "));
  outcomeEl.className = `badge badge-${esc(row.outcome)}`;

  const escalationEl = document.getElementById("drawer-escalation");
  const escalationWrap = document.getElementById("drawer-escalation-wrap");
  if (row.escalation_reason && escalationEl && escalationWrap) {
    escalationEl.textContent = escalationLabel(row.escalation_reason);
    escalationWrap.style.display = "";
  } else if (escalationWrap) {
    escalationWrap.style.display = "none";
  }

  document.getElementById("drawer-summary").textContent =
    row.summary || "No summary available.";

  const transcriptEl = document.getElementById("drawer-transcript");
  if (row.transcript) {
    transcriptEl.textContent = row.transcript;
    transcriptEl.parentElement.style.display = "";
  } else {
    transcriptEl.parentElement.style.display = "none";
  }

  // Audio player
  const player = document.getElementById("audio-player");
  if (row.recording_url) {
    document.getElementById("ap-play").innerHTML = playIcon();
    document.getElementById("ap-fill").style.width = "0%";
    document.getElementById("ap-thumb").style.left = "0%";
    document.getElementById("ap-current").textContent = "0:00";
    document.getElementById("ap-duration").textContent = "0:00";
    player.style.display = "";
    if (autoPlay) initAudioPlayer(row.recording_url);
    else {
      stopAudio();
      document.getElementById("ap-play").onclick = () =>
        initAudioPlayer(row.recording_url);
    }
  } else {
    player.style.display = "none";
    stopAudio();
  }

  // Transcript link only — use DOM API to prevent href injection
  const linksEl = document.getElementById("drawer-links");
  const linksSection = document.getElementById("drawer-links-section");
  linksEl.textContent = "";
  const transcriptUrl = row.transcript_url || "";
  if (transcriptUrl && transcriptUrl.startsWith("https://")) {
    const a = document.createElement("a");
    a.href = transcriptUrl;
    a.textContent = "📄 Transcript";
    a.className = "drawer-link-btn";
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    linksEl.appendChild(a);
    linksSection.style.display = "";
  } else {
    linksSection.style.display = "none";
  }

  document.getElementById("drawer-overlay").classList.add("open");
  document.getElementById("detail-drawer").classList.add("open");
  document.body.style.overflow = "hidden";
}

function closeDrawer() {
  stopAudio();
  document.getElementById("drawer-overlay").classList.remove("open");
  document.getElementById("detail-drawer").classList.remove("open");
  document.body.style.overflow = "";
}

window.closeDrawer = closeDrawer;

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDrawer();
});

// ── VAPI browser call ─────────────────────────────────────────────────────────
let _vapi = null;
let _calling = false;
let _micPermission = "unknown";
let _micPermStatusHandle = null;

// Active-call UI state
let _callTimerInterval = null;
let _callStartTime = null;
let _muted = false;
let _speakerOn = true;
let _vapiAudioEls = [];  // audio elements created by VAPI/Daily during a call
let _audioObserver = null;

function startCallTimer() {
  _callStartTime = Date.now();
  const timerEl = document.getElementById("pac-timer");
  if (!timerEl) return;
  _callTimerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - _callStartTime) / 1000);
    const m = Math.floor(elapsed / 60);
    const s = elapsed % 60;
    timerEl.textContent = `${m}:${s.toString().padStart(2, "0")}`;
  }, 1000);
}

function stopCallTimer() {
  if (_callTimerInterval) {
    clearInterval(_callTimerInterval);
    _callTimerInterval = null;
  }
  _callStartTime = null;
  const timerEl = document.getElementById("pac-timer");
  if (timerEl) timerEl.textContent = "0:00";
}

window.toggleMute = function toggleMute() {
  if (!_vapi) return;
  _muted = !_muted;
  _vapi.setMuted(_muted);
  const btn = document.getElementById("pac-mute-btn");
  const label = btn?.querySelector(".pac-ctrl-label");
  if (btn) {
    btn.classList.toggle("active", _muted);
    btn.setAttribute("aria-pressed", String(_muted));
  }
  if (label) label.textContent = _muted ? "Unmute" : "Mute";
};

function applyVolumeToCallAudio(volume) {
  // Apply to any audio elements we tracked during the call
  _vapiAudioEls.forEach((el) => { try { el.volume = volume; } catch {} });
  // Also sweep all audio elements in case we missed any
  document.querySelectorAll("audio").forEach((el) => { try { el.volume = volume; } catch {} });
}

function startAudioObserver() {
  _vapiAudioEls = [];
  // Snapshot any audio elements already in DOM (shouldn't be any, but safe)
  document.querySelectorAll("audio").forEach((el) => _vapiAudioEls.push(el));

  _audioObserver = new MutationObserver((mutations) => {
    mutations.forEach((m) => {
      m.addedNodes.forEach((node) => {
        if (node.nodeName === "AUDIO") {
          _vapiAudioEls.push(node);
          // Apply current speaker state to newly injected audio element
          node.volume = _speakerOn ? 1.0 : 1.0; // start at full volume; speaker toggle changes it
        }
        // Daily.co sometimes nests audio inside divs
        if (node.querySelectorAll) {
          node.querySelectorAll("audio").forEach((el) => {
            if (!_vapiAudioEls.includes(el)) {
              _vapiAudioEls.push(el);
            }
          });
        }
      });
    });
  });
  _audioObserver.observe(document.body, { childList: true, subtree: true });
}

function stopAudioObserver() {
  if (_audioObserver) {
    _audioObserver.disconnect();
    _audioObserver = null;
  }
  _vapiAudioEls = [];
}

window.toggleSpeaker = function toggleSpeaker() {
  _speakerOn = !_speakerOn;
  const btn = document.getElementById("pac-speaker-btn");
  const label = btn?.querySelector(".pac-ctrl-label");
  if (btn) {
    btn.classList.toggle("active", _speakerOn);
    btn.setAttribute("aria-pressed", String(_speakerOn));
  }
  if (label) label.textContent = _speakerOn ? "Speaker On" : "Speaker";

  // Speaker ON = loudspeaker (full volume), Speaker OFF = earpiece mode (lower volume)
  const targetVolume = _speakerOn ? 1.0 : 0.3;
  applyVolumeToCallAudio(targetVolume);
};

let _configLoaded = false;
let _vapiConfig = {};

async function loadConfig() {
  if (_configLoaded) return _vapiConfig;
  const res = await fetch(`${API_BASE}/api/config`);
  if (!res.ok) throw new Error("Failed to load config");
  _vapiConfig = await res.json();
  _configLoaded = true;
  return _vapiConfig;
}

async function initVapi() {
  if (_vapi) return _vapi;
  const cfg = await loadConfig();
  const { vapiPublicKey, vapiAssistantId } = cfg;
  if (!vapiPublicKey)
    throw new Error("VAPI_PUBLIC_KEY not configured on server");

  const vapiMod = await import("https://esm.sh/@vapi-ai/web@2.5.2");
  const VapiClass = vapiMod.default;
  if (typeof VapiClass !== "function")
    throw new Error("Vapi SDK failed to load — check network/CSP");
  _vapi = new VapiClass(vapiPublicKey);
  _vapi._assistantId = vapiAssistantId;

  _vapi.on("call-end", () => {
    _calling = false;
    setCallBtn(false);
    _selectedCallerPhone = null;
    try {
      renderCustomerView(_lastData);
    } catch {}
    setTimeout(load, 3000);
  });
  _vapi.on("error", (e) => {
    console.error("VAPI error", e);
    _calling = false;
    setCallBtn(false);
  });
  return _vapi;
}

function openMicModal() {
  const overlay = document.getElementById("mic-modal-overlay");
  if (!overlay) return;
  overlay.classList.add("open");
  overlay.setAttribute("aria-hidden", "false");
}

window.closeMicModal = function () {
  const overlay = document.getElementById("mic-modal-overlay");
  if (!overlay) return;
  overlay.classList.remove("open");
  overlay.setAttribute("aria-hidden", "true");
};

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") window.closeMicModal();
});

function updateMicPermissionUI() {
  const micPermissionBtn = document.getElementById("mic-permission-btn");
  if (!micPermissionBtn) return;
  // Only show "Enable Microphone" button after a denied check — never block Start Call
  micPermissionBtn.style.display = _micPermission === "denied" ? "inline-flex" : "none";
}

async function refreshMicPermission(requestPrompt = false) {
  if (!navigator.mediaDevices?.getUserMedia) {
    _micPermission = "unavailable";
    updateMicPermissionUI();
    return _micPermission;
  }

  if (navigator.permissions?.query) {
    try {
      const status = await navigator.permissions.query({ name: "microphone" });
      _micPermStatusHandle = status;
      _micPermission = status.state;
      status.onchange = () => {
        _micPermission = status.state;
        updateMicPermissionUI();
      };
    } catch {
      _micPermission = "prompt";
    }
  } else {
    _micPermission = "prompt";
  }

  if (requestPrompt && _micPermission !== "granted") {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      _micPermission = "granted";
    } catch {
      _micPermission = "denied";
    }
  }

  updateMicPermissionUI();
  return _micPermission;
}

function setCallBtn(active) {
  const btn = document.getElementById("call-btn");
  const label = document.getElementById("call-label");
  const icon = document.getElementById("call-icon");
  btn.classList.toggle("active", active);
  label.textContent = active ? "End Call" : "Start Call";
  icon.innerHTML = active ? stopIcon() : phoneIcon();
  btn.disabled = false;

  if (active) {
    startCallTimer();
    startAudioObserver();
    // Ensure speaker button reflects default-on state
    const spkBtnStart = document.getElementById("pac-speaker-btn");
    if (spkBtnStart) {
      spkBtnStart.classList.add("active");
      spkBtnStart.setAttribute("aria-pressed", "true");
      const sl = spkBtnStart.querySelector(".pac-ctrl-label");
      if (sl) sl.textContent = "Speaker On";
    }
  } else {
    stopCallTimer();
    stopAudioObserver();
    // Reset mute state
    _muted = false;
    const muteBtn = document.getElementById("pac-mute-btn");
    if (muteBtn) {
      muteBtn.classList.remove("active");
      muteBtn.setAttribute("aria-pressed", "false");
      const ml = muteBtn.querySelector(".pac-ctrl-label");
      if (ml) ml.textContent = "Mute";
    }
    // Reset speaker state (default: on)
    _speakerOn = true;
    const spkBtn = document.getElementById("pac-speaker-btn");
    if (spkBtn) {
      spkBtn.classList.add("active");
      spkBtn.setAttribute("aria-pressed", "true");
      const sl = spkBtn.querySelector(".pac-ctrl-label");
      if (sl) sl.textContent = "Speaker On";
    }
    applyVolumeToCallAudio(1.0);
  }

  syncCallStateUI(active);
}

async function toggleCall() {
  const btn = document.getElementById("call-btn");
  if (!_calling) {
    const permission = await refreshMicPermission(true);
    if (permission !== "granted") {
      openMicModal();
      setCallBtn(false);
      return;
    }
  }
  btn.disabled = true;
  try {
    const vapi = await initVapi();
    if (_calling) {
      vapi.stop();
      _calling = false;
      setCallBtn(false);
    } else {
      await vapi.start(vapi._assistantId);
      _calling = true;
      setCallBtn(true);
    }
  } catch (e) {
    const callError = document.getElementById("call-error-text");
    if (callError) callError.textContent = e.message || "Could not start call.";
    setCallBtn(false);
  }
}

// Expose to HTML onclick (module scripts don't pollute window automatically)
window.toggleCall = toggleCall;
window.requestMicPermission = async function requestMicPermission() {
  // First query current permission state without prompting
  await refreshMicPermission(false);

  if (_micPermission === "denied") {
    // Already blocked — skip getUserMedia (it'll just fail), show instructions
    openMicModal();
    return;
  }

  // State is "prompt" or "unknown" — trigger native browser dialog
  const permission = await refreshMicPermission(true);
  if (permission !== "granted") {
    openMicModal();
  }
};

function syncCallStateUI(active) {
  const customerState = document.getElementById("customer-call-state");
  const phoneTopStatus = document.getElementById("phone-top-status");
  const headerState = document.getElementById("header-call-state");
  const tabCustomer = document.getElementById("tab-customer");
  const tabDashboard = document.getElementById("tab-dashboard");
  const phoneIdle = document.getElementById("phone-idle");
  const phoneActive = document.getElementById("phone-active");

  if (customerState) {
    customerState.textContent = active ? "Call in progress" : "Ready to call";
  }
  if (phoneTopStatus) {
    phoneTopStatus.textContent = active ? "Call in progress" : "Ready to call";
  }
  headerState.textContent = active ? "Call active" : "No active call";
  tabCustomer.classList.toggle("locked", active);
  tabDashboard.classList.toggle("locked", active);

  if (phoneIdle) phoneIdle.style.display = active ? "none" : "";
  if (phoneActive) phoneActive.style.display = active ? "" : "none";
}

function setActiveView(view) {
  if (_calling && view !== _activeView) {
    alert("You can switch tabs after the call ends.");
    return;
  }
  _activeView = view;

  const customerView = document.getElementById("customer-view");
  const dashboardView = document.getElementById("dashboard-view");
  const tabCustomer = document.getElementById("tab-customer");
  const tabDashboard = document.getElementById("tab-dashboard");
  const viewToggle = document.getElementById("view-toggle");

  const customerActive = view === "customer";
  customerView.classList.toggle("hidden", !customerActive);
  dashboardView.classList.toggle("hidden", customerActive);
  tabCustomer.classList.toggle("active", customerActive);
  tabDashboard.classList.toggle("active", !customerActive);
  tabCustomer.setAttribute("aria-selected", String(customerActive));
  tabDashboard.setAttribute("aria-selected", String(!customerActive));
  if (viewToggle) {
    viewToggle.classList.toggle("is-customer", customerActive);
    viewToggle.classList.toggle("is-dashboard", !customerActive);
  }

  // Always show fresh shimmer + latest error/success state when opening Dashboard.
  if (!customerActive) {
    load();
  }
}

function setupTabs() {
  document
    .getElementById("tab-customer")
    .addEventListener("click", () => setActiveView("customer"));
  document
    .getElementById("tab-dashboard")
    .addEventListener("click", () => setActiveView("dashboard"));
}

function setupTalkGuideAccordion() {
  const items = document.querySelectorAll(".talk-item");
  const getContent = (item) => item.querySelector(".talk-content");

  function animateOpen(item) {
    const content = getContent(item);
    if (!content) return;
    item.open = true;
    content.style.maxHeight = "0px";
    content.style.opacity = "0";
    requestAnimationFrame(() => {
      content.style.maxHeight = `${content.scrollHeight}px`;
      content.style.opacity = "1";
    });
  }

  function animateClose(item) {
    const content = getContent(item);
    if (!content || !item.open) return;
    content.style.maxHeight = `${content.scrollHeight}px`;
    content.style.opacity = "1";
    requestAnimationFrame(() => {
      content.style.maxHeight = "0px";
      content.style.opacity = "0";
    });
    const done = () => {
      item.open = false;
    };
    content.addEventListener("transitionend", done, { once: true });
  }

  items.forEach((item) => {
    const summary = item.querySelector("summary");
    const content = getContent(item);
    if (!summary || !content) return;
    item.open = false;
    content.style.maxHeight = "0px";
    content.style.opacity = "0";

    summary.addEventListener("click", (e) => {
      e.preventDefault();
      const isOpen = item.open;
      if (isOpen) {
        animateClose(item);
        return;
      }
      items.forEach((other) => {
        if (other !== item) animateClose(other);
      });
      animateOpen(item);
    });
  });
}

function renderCustomerLoadingState() {
  const verifyEl = document.getElementById("customer-verify");
  const tbody = document.getElementById("customer-caller-body");
  if (!verifyEl || !tbody) return;

  verifyEl.textContent = "Loading caller details...";
  const row = () => `
    <tr>
      <td><div class="skeleton" style="width:118px;height:13px"></div></td>
      <td><div class="skeleton" style="width:72px;height:13px"></div></td>
      <td><div class="skeleton" style="width:76px;height:13px"></div></td>
      <td><div class="skeleton" style="width:84px;height:13px"></div></td>
      <td><div class="skeleton" style="width:84px;height:13px"></div></td>
      <td><div class="skeleton" style="width:56px;height:13px"></div></td>
      <td><div class="skeleton" style="width:124px;height:13px"></div></td>
      <td><div class="skeleton" style="width:92px;height:13px"></div></td>
      <td><div class="skeleton" style="width:94px;height:13px"></div></td>
    </tr>
  `;
  tbody.innerHTML = Array.from({ length: 5 }).map(row).join("");
}

// ── Loading skeletons ─────────────────────────────────────────────────────────
function renderLoadingState() {
  // Stats skeleton
  const statsEl = document.getElementById("stats");
  if (statsEl) {
    const card = () => `
      <div class="card">
        <div class="skeleton" style="width:90px;height:10px"></div>
        <div class="skeleton" style="width:120px;height:26px;margin-top:8px"></div>
        <div class="skeleton" style="width:70px;height:10px;margin-top:8px"></div>
      </div>`;
    statsEl.innerHTML = [card(), card(), card(), card()].join("");
  }

  // Interactions table skeleton
  const tbody = document.getElementById("table-body");
  if (tbody) {
    const row = () => `
      <tr>
        <td class="time-cell"><div class="skeleton" style="width:60px;height:12px"></div></td>
        <td>
          <div class="skeleton" style="width:120px;height:13px"></div>
          <div class="skeleton" style="width:90px;height:11px;margin-top:4px"></div>
        </td>
        <td><div class="skeleton" style="width:260px;height:12px"></div></td>
        <td><div class="skeleton" style="width:60px;height:12px"></div></td>
        <td><div class="skeleton" style="width:80px;height:12px"></div></td>
        <td><div class="skeleton" style="width:100px;height:12px"></div></td>
        <td><div class="skeleton" style="width:20px;height:20px;border-radius:999px;margin-left:2px"></div></td>
      </tr>`;
    tbody.innerHTML = Array.from({ length: 10 }).map(row).join("");
  }

  renderCustomerLoadingState();

  const last = document.getElementById("last-updated");
  if (last) last.textContent = "Loading…";
}

const INTERACTIONS_TIMEOUT_MS = 10000;

async function fetchJsonWithTimeout(url, timeoutMs) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

function renderDashboardErrorState(message) {
  const msg = esc(message || "Could not load dashboard data.");
  const statsEl = document.getElementById("stats");
  if (statsEl) {
    const card = (title) => `
      <div class="card">
        <div class="card-title">${title}</div>
        <div class="card-value" style="font-size:20px">N/A</div>
        <div class="card-sub">${msg}</div>
      </div>`;
    statsEl.innerHTML = [
      card("Total Calls"),
      card("Containment Rate"),
      card("Escalated"),
      card("Auth Failures"),
    ].join("");
  }
}

// ── Dashboard data ────────────────────────────────────────────────────────────
async function load() {
  const dot = document.getElementById("status-dot");
  // Show loading state before fetching
  renderLoadingState();
  if (dot) dot.className = "status-dot";
  try {
    const res = await fetchJsonWithTimeout(
      `${API_BASE}/api/interactions`,
      INTERACTIONS_TIMEOUT_MS,
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _lastData = data;
    render(data);
    dot.className = "status-dot ok";
    document.getElementById("last-updated").textContent =
      `Updated ${new Date().toLocaleTimeString()}`;
  } catch (e) {
    dot.className = "status-dot error";
    const isTimeout = e?.name === "AbortError";
    const lastUpdatedEl = document.getElementById("last-updated");
    if (lastUpdatedEl) {
      lastUpdatedEl.textContent = isTimeout
        ? "No response yet (10 sec timeout)"
        : `Error: ${e.message}`;
    }

    // If we have old data, keep the UI useful and explain that it's stale.
    if (_lastData.length > 0) {
      render(_lastData);
      if (lastUpdatedEl) {
        lastUpdatedEl.textContent = isTimeout
          ? "Showing last synced data - click Refresh"
          : "Showing last synced data - click Refresh";
      }
      return;
    }

    const verifyEl = document.getElementById("customer-verify");
    if (verifyEl) {
      verifyEl.textContent = isTimeout
        ? "No response yet. It may take up to 10 sec to sync calls."
        : "Could not load caller details right now. Please refresh.";
    }

    const customerBody = document.getElementById("customer-caller-body");
    if (customerBody) {
      customerBody.innerHTML = `<tr><td colspan="9" class="empty">${isTimeout ? "No response yet. Try Refresh in a few seconds." : "Failed to load caller details. Please refresh."}</td></tr>`;
    }

    const tableBody = document.getElementById("table-body");
    if (tableBody) {
      tableBody.innerHTML = `<tr><td colspan="7" class="empty">${isTimeout ? "No response from server yet. Click Refresh after a few seconds." : "Failed to load interactions. Check backend and click Refresh."}</td></tr>`;
    }
    document.getElementById("pagination").innerHTML = "";
    renderDashboardErrorState(
      isTimeout
        ? "No response yet. Try Refresh in a few seconds."
        : "Failed to load. Click Refresh to retry.",
    );
  }
}

window.load = load;

// ── Pagination state ──────────────────────────────────────────────────────────
const PAGE_SIZE = 10;
let _allRows = [];
let _currentPage = 1;

function render(rows) {
  rows.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  _allRows = rows;
  _currentPage = 1;

  const total = rows.length;
  const resolved = rows.filter((r) => r.outcome === "resolved").length;
  const escalated = rows.filter((r) => r.outcome === "escalated").length;
  const authFailed = rows.filter((r) => r.outcome === "auth_failed").length;
  const containment = total > 0 ? Math.round((resolved / total) * 100) : 0;
  const repRequested = rows.filter((r) => r.escalation_reason === "representative_requested").length;
  const emergency = rows.filter((r) => r.escalation_reason === "emergency").length;
  const unsupported = rows.filter((r) => r.escalation_reason === "unsupported_question").length;
  const verificationFailed = rows.filter((r) => r.escalation_reason === "verification_failed").length;

  const escalationSub = escalated > 0
    ? [
        repRequested ? `${repRequested} rep requested` : "",
        verificationFailed ? `${verificationFailed} verify failed` : "",
        unsupported ? `${unsupported} unsupported` : "",
        emergency ? `${emergency} emergency` : "",
      ].filter(Boolean).join(" · ") || `${pct(escalated, total)}% of calls`
    : "none this period";

  const stats = [
    { title: "Total Calls", value: total, sub: "all time", bar: null },
    {
      title: "Containment Rate",
      value: `${containment}%`,
      sub: `${resolved} resolved without escalation`,
      bar: containment,
    },
    {
      title: "Escalated",
      value: escalated,
      sub: escalationSub,
      bar: null,
    },
    {
      title: "Auth Failures",
      value: authFailed,
      sub: `${rows.filter((r) => r.sentiment === "positive").length} positive sentiment`,
      bar: null,
    },
  ];

  document.getElementById("stats").innerHTML = stats
    .map(
      (c) => `
    <div class="card">
      <div class="card-title">${c.title}</div>
      <div class="card-value">${c.value}</div>
      <div class="card-sub">${c.sub}</div>
      ${c.bar !== null ? `<div class="card-bar"><div class="card-bar-fill" style="width:${c.bar}%"></div></div>` : ""}
    </div>
  `,
    )
    .join("");

  renderCustomerView(rows);
  renderPage();
}

function renderCustomerView(rows) {
  // Do not auto-select a caller; selection occurs during/after agent prompt
  const selected = _selectedCallerPhone
    ? CALLER_PROFILES[normalizePhone(_selectedCallerPhone)] || null
    : null;
  const verifyEl = document.getElementById("customer-verify");
  const chipEl = document.getElementById("selected-caller-chip");
  if (selected) {
    verifyEl.textContent = `Confirm ${selected.first_name} ${selected.last_name} — DOB ${selected.dob} — ZIP ${selected.zip_code}`;
    chipEl.textContent = `Selected: ${selected.first_name} ${selected.last_name} (${formatPhone(selected.phone)})`;
    chipEl.style.display = "";
  } else {
    verifyEl.textContent =
      "Agent confirms identity by name, ZIP, or DOB during the call.";
    chipEl.style.display = "none";
  }

  const statusBadge = (status) => {
    const cls = status === "approved" ? "resolved" : status === "pending" ? "neutral" : "escalated";
    return `<span class="badge badge-${cls}">${status.replace("_", " ")}</span>`;
  };

  const rowsHtml = Object.values(CALLER_PROFILES)
    .map((caller) => {
      const displayPhone = formatPhone(caller.phone);
      return `
      <tr>
        <td class="phone-cell"><span class="phone-number">${displayPhone}</span></td>
        <td>${caller.first_name}</td>
        <td>${caller.last_name}</td>
        <td>${caller.dob}</td>
        <td>${caller.claim_id}</td>
        <td>${statusBadge(caller.claim_status)}</td>
        <td>${caller.zip_code || "—"}</td>
        <td class="docs-cell">${caller.docs_required || "—"}</td>
        <td>${caller.policy_number || "—"}</td>
      </tr>
    `;
    })
    .join("");

  const unknownRow = `
    <tr class="row-unknown">
      <td class="phone-cell"><span class="phone-number">${formatPhone(UNKNOWN_CALLER_PHONE)}</span></td>
      <td colspan="8" class="muted">Not on file — triggers alternate verification flow</td>
    </tr>
  `;

  const tbody = document.getElementById("customer-caller-body");
  tbody.innerHTML = rowsHtml + unknownRow;
}

function renderPage() {
  const rows = _allRows;
  const tbody = document.getElementById("table-body");

  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty">No calls yet. Make a test call to see data here.</td></tr>`;
    document.getElementById("pagination").innerHTML = "";
    return;
  }

  const totalPages = Math.ceil(rows.length / PAGE_SIZE);
  const page = Math.max(1, Math.min(_currentPage, totalPages));
  _currentPage = page;

  const start = (page - 1) * PAGE_SIZE;
  const pageRows = rows.slice(start, start + PAGE_SIZE);

  tbody.innerHTML = pageRows
    .map((r, i) => {
      const globalIdx = start + i;
      const ts = formatTime(r.timestamp);
      const playCell = r.recording_url
        ? `<button class="row-play-btn" data-idx="${globalIdx}" aria-label="Play recording" onclick="event.stopPropagation()">
           <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14"><path d="M8 5v14l11-7z"/></svg>
         </button>`
        : `<span class="muted">Not available</span>`;
      const escalationCell = r.escalation_reason
        ? `<span class="badge badge-escalation-${esc(r.escalation_reason)}">${escalationLabel(r.escalation_reason)}</span>`
        : `<span class="muted">—</span>`;
      return `
      <tr class="clickable-row" data-idx="${globalIdx}">
        <td class="time-cell">${ts}</td>
        <td>
          <div class="caller-name">${esc(r.caller_name)}</div>
          <div class="caller-phone">${esc(r.caller_phone)}</div>
        </td>
        <td><div class="summary-clickable" title="Click to view details">${esc(r.summary)}</div></td>
        <td><span class="badge badge-${esc(r.sentiment)}">${capitalize(r.sentiment)}</span></td>
        <td><span class="badge badge-${esc(r.outcome)}">${capitalize(r.outcome.replace(/_/g, " "))}</span></td>
        <td>${escalationCell}</td>
        <td>${playCell}</td>
      </tr>
    `;
    })
    .join("");

  tbody.querySelectorAll("tr.clickable-row").forEach((tr) => {
    tr.addEventListener("click", () => {
      const idx = parseInt(tr.dataset.idx, 10);
      openDrawer(rows[idx]);
    });
  });

  tbody.querySelectorAll(".row-play-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const idx = parseInt(btn.dataset.idx, 10);
      openDrawer(rows[idx], true);
    });
  });

  renderPagination(page, totalPages);
}

function renderPagination(page, totalPages) {
  const el = document.getElementById("pagination");
  if (totalPages <= 1) {
    el.innerHTML = "";
    return;
  }

  const pages = paginationPages(page, totalPages);
  const chevL = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="13" height="13"><path d="M15 18l-6-6 6-6"/></svg>`;
  const chevR = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="13" height="13"><path d="M9 18l6-6-6-6"/></svg>`;

  el.innerHTML = [
    `<button class="pg-btn" data-pg="${page - 1}" ${page === 1 ? "disabled" : ""}>${chevL} Previous</button>`,
    ...pages.map((p) =>
      p === "…"
        ? `<span class="pg-dots">···</span>`
        : `<button class="pg-btn${p === page ? " active" : ""}" data-pg="${p}">${p}</button>`,
    ),
    `<button class="pg-btn" data-pg="${page + 1}" ${page === totalPages ? "disabled" : ""}>Next ${chevR}</button>`,
  ].join("");

  el.querySelectorAll(".pg-btn[data-pg]").forEach((btn) => {
    btn.addEventListener("click", () => {
      _currentPage = parseInt(btn.dataset.pg, 10);
      renderPage();
      document
        .getElementById("interactions-table")
        .scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function paginationPages(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (current <= 4) return [1, 2, 3, 4, 5, "…", total];
  if (current >= total - 3)
    return [1, "…", total - 4, total - 3, total - 2, total - 1, total];
  return [1, "…", current - 1, current, current + 1, "…", total];
}

function pct(n, total) {
  return total > 0 ? Math.round((n / total) * 100) : 0;
}

function formatTime(iso) {
  try {
    const d = new Date(iso);
    return (
      d.toLocaleDateString([], { month: "short", day: "numeric" }) +
      " " +
      d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    );
  } catch {
    return iso;
  }
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

load();
document.getElementById("call-icon").innerHTML = phoneIcon();
setupTabs();
setupTalkGuideAccordion();
setActiveView("customer");
syncCallStateUI(false);
