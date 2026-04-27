const state = {
  username: localStorage.getItem("chat_username") || "guest",
  channel: "general",
  peers: [],
  selectedPeer: null,
  lastSeq: {
    general: 0,
    team1: 0
  },
  unseenCount: 0
};

const currentUserEl = document.getElementById("currentUser");
const statusTextEl = document.getElementById("statusText");
const peerListEl = document.getElementById("peerList");
const messagesEl = document.getElementById("messages");
const toastEl = document.getElementById("toast");
const inputEl = document.getElementById("messageInput");

currentUserEl.textContent = state.username;

function setStatus(text) {
  statusTextEl.textContent = text;
}

function showToast(text) {
  toastEl.textContent = text;
  toastEl.classList.remove("hidden");
  setTimeout(() => toastEl.classList.add("hidden"), 1800);
}

async function api(path, method = "GET", payload = null) {
  const opts = {
    method,
    credentials: "include",
    headers: {}
  };

  if (payload !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(payload);
  }

  const resp = await fetch(path, opts);
  const text = await resp.text();

  try {
    return JSON.parse(text);
  } catch (err) {
    return { ok: resp.ok, raw: text };
  }
}

function isNearBottom() {
  return messagesEl.scrollTop + messagesEl.clientHeight >= messagesEl.scrollHeight - 40;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderPeers() {
  peerListEl.innerHTML = "";

  if (!state.peers.length) {
    peerListEl.innerHTML = `<div class="peer empty">No peers</div>`;
    return;
  }

  state.peers.forEach((peer) => {
    const btn = document.createElement("button");
    btn.className = "peer" + (
      state.selectedPeer && state.selectedPeer.username === peer.username ? " active" : ""
    );
    btn.textContent = `${peer.username} (${peer.ip}:${peer.port})`;

    btn.addEventListener("click", () => {
      state.selectedPeer = peer;
      renderPeers();
      setStatus(`Selected peer: ${peer.username}`);
    });

    peerListEl.appendChild(btn);
  });
}

function renderMessages(newMessages) {
  const shouldStick = isNearBottom();

  newMessages.forEach((msg) => {
    const div = document.createElement("div");
    div.className = "msg " + (msg.direction === "out" ? "outgoing" : "incoming");
    div.innerHTML = `
      <div class="meta">
        <strong>${msg.from}</strong>
        <span>${msg.channel}</span>
      </div>
      <div class="text"></div>
    `;
    div.querySelector(".text").textContent = msg.text;
    messagesEl.appendChild(div);
  });

  if (shouldStick) {
    scrollToBottom();
  } else if (newMessages.length > 0) {
    state.unseenCount += newMessages.length;
    document.title = `(${state.unseenCount}) P2P Chat`;
    showToast(`${newMessages.length} new message(s)`);
  }
}

async function refreshPeers() {
  setStatus("Refreshing peers...");
  const data = await api("/get-list", "GET");

  if (data.ok && Array.isArray(data.peers)) {
    state.peers = data.peers.filter((p) => p.username !== state.username);
    renderPeers();
    setStatus("Peers updated");
  } else {
    setStatus("Failed to load peers");
  }
}

async function pollMessages() {
  const afterSeq = state.lastSeq[state.channel] || 0;
  const data = await api("/messages", "POST", {
    channel: state.channel,
    after_seq: afterSeq
  });

  if (data.ok) {
    const msgs = Array.isArray(data.messages) ? data.messages : [];
    renderMessages(msgs);
    state.lastSeq[state.channel] = data.last_seq || afterSeq;
  }
}

async function sendDirect() {
  if (!state.selectedPeer) {
    showToast("Select a peer first");
    return;
  }

  const message = inputEl.value.trim();
  if (!message) return;

  const res = await api("/send-peer", "POST", {
    sender: state.username,
    channel: state.channel,
    message,
    ip: state.selectedPeer.ip,
    port: state.selectedPeer.port
  });

  if (res.ok) {
    inputEl.value = "";
    setStatus("Direct message sent");
    await pollMessages();
  } else {
    showToast(res.error || "Send failed");
  }
}

async function broadcastMessage() {
  const message = inputEl.value.trim();
  if (!message) return;

  const res = await api("/broadcast-peer", "POST", {
    sender: state.username,
    channel: state.channel,
    message,
    peers: state.peers
  });

  if (res.ok) {
    inputEl.value = "";
    setStatus("Broadcast sent");
    await pollMessages();
  } else {
    showToast(res.error || "Broadcast failed");
  }
}

function bindChannels() {
  document.querySelectorAll(".channel").forEach((btn) => {
    btn.addEventListener("click", async () => {
      document.querySelectorAll(".channel").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      state.channel = btn.dataset.channel;
      messagesEl.innerHTML = "";
      state.unseenCount = 0;
      document.title = "P2P Chat";
      await pollMessages();
      scrollToBottom();
    });
  });
}

document.getElementById("sendBtn").addEventListener("click", sendDirect);
document.getElementById("broadcastBtn").addEventListener("click", broadcastMessage);
document.getElementById("refreshPeersBtn").addEventListener("click", refreshPeers);

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    sendDirect();
  }
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    state.unseenCount = 0;
    document.title = "P2P Chat";
  }
});

bindChannels();
refreshPeers();
pollMessages();
setInterval(refreshPeers, 5000);
setInterval(pollMessages, 1000);