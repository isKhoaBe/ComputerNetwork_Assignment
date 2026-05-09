const TRACKER_BASE = "http://10.127.23.95:9000";

const ALL_MESSAGES_CHANNEL = "__all__";

const state = {
  username: "",
  channel: "general",
  peers: [],  
  selectedPeer: null,
  lastSeq: 0,
  seenIds: new Set(),
  unseenCount: 0,
  polling: false,

  currentView: "channel:general",
  views: {
    "channel:general": []
  }
};

const currentUserEl = document.getElementById("currentUser");
const statusTextEl = document.getElementById("statusText");
const peerListEl = document.getElementById("peerList");
const messagesEl = document.getElementById("messages");
const toastEl = document.getElementById("toast");
const inputEl = document.getElementById("messageInput");
const actionBtn = document.getElementById("actionBtn");
const logoutBtn = document.getElementById("logoutBtn");

function setStatus(text) {
  statusTextEl.textContent = text;
}

function showToast(text) {
  toastEl.textContent = text;
  toastEl.classList.remove("hidden");
  setTimeout(() => toastEl.classList.add("hidden"), 1800);
}

function buildDmChannelKey(a, b) {
  const left = String(a || "").trim();
  const right = String(b || "").trim();
  return `dm:${[left, right].sort().join(":")}`;
}

async function requireLogin() {
  try {
    const resp = await fetch("/me", {
      method: "GET",
      credentials: "include"
    });

    const text = await resp.text();
    let data = {};
    try { data = JSON.parse(text); } catch (_) {}

    if (!resp.ok || !data.ok || !data.username) {
      window.location.href = "/login.html";
      return false;
    }

    state.username = data.username;
    currentUserEl.textContent = state.username;
    return true;
  } catch (err) {
    window.location.href = "/login.html";
    return false;
  }
}

async function logout() {
  try {
    await fetch("/logout", {
      method: "POST",
      credentials: "include"
    });
  } catch (_) {}

  window.location.href = "/login.html";
}

function getChannelViewKey(channel) {
  return `channel:${channel}`;
}

function getPeerViewKey(username) {
  return `peer:${username}`;
}

function ensureView(key) {
  if (!state.views[key]) {
    state.views[key] = [];
  }
}

function getCurrentViewMessages() {
  ensureView(state.currentView);
  return state.views[state.currentView];
}

function switchToChannel(channel) {
  state.channel = channel;
  state.selectedPeer = null;
  state.currentView = getChannelViewKey(channel);
  ensureView(state.currentView);
  renderPeers();
  renderCurrentView();
  updateModeUI();
}

function switchToPeer(peer) {
  state.selectedPeer = peer;
  state.currentView = getPeerViewKey(peer.username);
  ensureView(state.currentView);
  renderPeers();
  renderCurrentView();
  updateModeUI();
}

function normalizeTextResponse(resp, text) {
  try {
    return JSON.parse(text);
  } catch (_) {
    return { ok: resp.ok, raw: text };
  }
}

async function localApi(path, method = "GET", payload = null) {
  const opts = {
    method,
    headers: {}
  };

  if (payload !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(payload);
  }

  const resp = await fetch(path, opts);
  const text = await resp.text();
  return normalizeTextResponse(resp, text);
}

async function trackerApi(path, method = "GET", payload = null) {
  const opts = {
    method,
    headers: {}
  };

  if (payload !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(payload);
  }

  const resp = await fetch(TRACKER_BASE + path, opts);
  const text = await resp.text();
  return normalizeTextResponse(resp, text);
}

function isNearBottom() {
  return messagesEl.scrollTop + messagesEl.clientHeight >= messagesEl.scrollHeight - 40;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function updateModeUI() {
  if (state.selectedPeer) {
    actionBtn.textContent = "Send";
    inputEl.placeholder = `Send private message to ${state.selectedPeer.username}...`;
    setStatus(`Mode: Direct message to ${state.selectedPeer.username}`);
  } else {
    actionBtn.textContent = "Broadcast";
    inputEl.placeholder = `Broadcast to #${state.channel}...`;
    setStatus(`Mode: Broadcast to #${state.channel}`);
  }
}

function renderPeers() {
  peerListEl.innerHTML = "";

  if (!state.peers.length) {
    peerListEl.innerHTML = `<div class="peer empty">No peers</div>`;
    return;
  }

  state.peers.forEach((peer) => {
    const btn = document.createElement("button");
    const isActive = state.selectedPeer && state.selectedPeer.username === peer.username;
    btn.className = "peer" + (isActive ? " active" : "");
    btn.textContent = `${peer.username} (${peer.ip}:${peer.port})`;

    btn.addEventListener("click", () => {
      if (isActive) {
        switchToChannel(state.channel);
      } else {
        switchToPeer(peer);
      }
    });

    peerListEl.appendChild(btn);
  });
}

function buildMessageNode(msg) {
  const div = document.createElement("div");
  div.className = "msg " + (msg.direction === "out" ? "outgoing" : "incoming");

  const kind = msg.type === "broadcast" ? "broadcast" : "direct";

  div.innerHTML = `
    <div class="meta">
      <strong>${msg.from}</strong>
      <span>${kind}</span>
    </div>
    <div class="text"></div>
  `;

  div.querySelector(".text").textContent = msg.text;
  return div;
}

function renderCurrentView() {
  const msgs = getCurrentViewMessages();
  messagesEl.innerHTML = "";

  if (!msgs.length) {
    const empty = document.createElement("div");
    empty.className = "empty-chat";
    empty.textContent = state.selectedPeer
      ? `No messages with ${state.selectedPeer.username} yet`
      : `No messages in #${state.channel} yet`;
    messagesEl.appendChild(empty);
    return;
  }

  msgs.forEach((msg) => {
    messagesEl.appendChild(buildMessageNode(msg));
  });

  scrollToBottom();
}

function addMessageToView(viewKey, msg) {
  ensureView(viewKey);

  const alreadyExists = state.views[viewKey].some((item) => item.id === msg.id);
  if (alreadyExists) {
    return;
  }

  state.views[viewKey].push(msg);

  if (state.currentView === viewKey) {
    const empty = messagesEl.querySelector(".empty-chat");
    if (empty) empty.remove();
    messagesEl.appendChild(buildMessageNode(msg));
    scrollToBottom();
  }
}

function pushNewMessagesToCurrentView(newMessages, targetViewKey) {
  const shouldStick = isNearBottom();

  newMessages.forEach((msg) => {
    addMessageToView(targetViewKey, msg);
  });

  if (state.currentView === targetViewKey) {
    if (shouldStick) {
      scrollToBottom();
    }
  } else if (newMessages.length > 0) {
    state.unseenCount += newMessages.length;
    document.title = `(${state.unseenCount}) P2P Chat`;
    showToast(`${newMessages.length} new message(s)`);
  }
}

async function refreshPeers() {
  setStatus("Refreshing peers...");
  try {
    const data = await trackerApi("/get-list", "GET");

    if (data.ok && Array.isArray(data.peers)) {
      state.peers = data.peers.filter((p) => p.username !== state.username);

      state.peers.forEach((peer) => {
        ensureView(getPeerViewKey(peer.username));
      });

      renderPeers();
      updateModeUI();
    } else {
      setStatus("Failed to load peers");
    }
  } catch (err) {
    console.error("refreshPeers error:", err);
    setStatus("Tracker offline");
  }
}

function routeIncomingMessage(msg) {
  if (!msg || !msg.id) return null;
  if (state.seenIds.has(msg.id)) return null;

  state.seenIds.add(msg.id);

  if (msg.type === "broadcast") {
    const channel = msg.channel || "general";
    return {
      viewKey: getChannelViewKey(channel),
      msg
    };
  }

  if (msg.type === "direct") {
    const peerUser = msg.direction === "in"
      ? (msg.from || "unknown")
      : (msg.to || "unknown");

    return {
      viewKey: getPeerViewKey(peerUser),
      msg
    };
  }

  return null;
}

async function pollMessages() {
  if (state.polling) return;
  state.polling = true;

  try {
    const afterSeq = state.lastSeq || 0;
    const data = await localApi("/messages", "POST", {
      channel: ALL_MESSAGES_CHANNEL,
      after_seq: afterSeq
    });

    if (!data.ok) return;

    const msgs = Array.isArray(data.messages) ? data.messages : [];
    const grouped = {};

    msgs.forEach((rawMsg) => {
      const routed = routeIncomingMessage(rawMsg);
      if (!routed) return;

      const { viewKey, msg } = routed;
      if (!grouped[viewKey]) grouped[viewKey] = [];
      grouped[viewKey].push(msg);
    });

    Object.keys(grouped).forEach((viewKey) => {
      pushNewMessagesToCurrentView(grouped[viewKey], viewKey);
    });

    state.lastSeq = data.last_seq || afterSeq;
  } catch (err) {
    console.error("pollMessages error:", err);
  } finally {
    state.polling = false;
  }
}

async function sendDirect() {
  if (!state.selectedPeer) {
    showToast("Select a peer first");
    return;
  }

  const message = inputEl.value.trim();
  if (!message) return;

  const peer = state.selectedPeer;
  const dmChannel = buildDmChannelKey(state.username, peer.username);

  const res = await localApi("/send-peer", "POST", {
    sender: state.username,
    to: peer.username,
    type: "direct",
    channel: dmChannel,
    message,
    ip: peer.ip,
    port: peer.port
  });

  if (res.ok) {
    const localMsg = {
      id: res.id || `local-direct-${Date.now()}-${Math.random()}`,
      from: state.username,
      to: peer.username,
      text: message,
      channel: dmChannel,
      direction: "out",
      type: "direct"
    };

    state.seenIds.add(localMsg.id);
    addMessageToView(getPeerViewKey(peer.username), localMsg);
    inputEl.value = "";
    setStatus(`Sent to ${peer.username}`);
  } else {
    showToast(res.error || "Send failed");
  }
}

async function broadcastMessage() {
  const message = inputEl.value.trim();
  if (!message) return;

  const res = await localApi("/broadcast-peer", "POST", {
    sender: state.username,
    channel: state.channel,
    message,
    peers: state.peers
  });

  if (res.ok) {
    inputEl.value = "";
    setStatus(`Broadcast sent to #${state.channel}`);
    await pollMessages();
  } else {
    showToast(res.error || "Broadcast failed");
  }
}

async function handleMainAction() {
  if (state.selectedPeer) {
    await sendDirect();
  } else {
    await broadcastMessage();
  }
}

function bindChannels() {
  document.querySelectorAll(".channel").forEach((btn) => {
    btn.addEventListener("click", async () => {
      document.querySelectorAll(".channel").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      switchToChannel(btn.dataset.channel);
      await pollMessages();
    });
  });
}

document.getElementById("refreshPeersBtn").addEventListener("click", refreshPeers);
actionBtn.addEventListener("click", handleMainAction);
if (logoutBtn) {
  logoutBtn.addEventListener("click", logout);
}

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    handleMainAction();
  }
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    state.unseenCount = 0;
    document.title = "P2P Chat";
  }
});

(async function initApp() {
  const ok = await requireLogin();
  if (!ok) return;

  bindChannels();
  updateModeUI();
  refreshPeers();
  renderCurrentView();
  pollMessages();
  setInterval(refreshPeers, 5000);
  setInterval(pollMessages, 1000);
})();