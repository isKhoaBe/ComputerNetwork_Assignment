import json
import os
import uuid

from daemon import AsynapRous
from apps.p2p_logic import P2PNode

app = AsynapRous()

# -------------------------
# tracker data
# -------------------------
active_peers = {}
active_channels = ["general", "team1"]
# -------------------------
# auth/session
# -------------------------
sessions = {}

USERS = {
    "alice": "123",
    "bob": "123",
    "charlie": "123",
    "dave": "123",
}

# -------------------------
# app mode
# -------------------------
APP_MODE = os.environ.get("APP_MODE", "peer")   # "tracker" or "peer"
APP_IP = os.environ.get("APP_IP", "127.0.0.1")
P2P_PORT = int(os.environ.get("P2P_PORT", "9101"))
INSTANCE_ID = os.environ.get("INSTANCE_ID", "unknown")

# -------------------------
# local p2p node
# -------------------------
node = None
if APP_MODE != "tracker":
    node = P2PNode(listen_host="0.0.0.0", listen_port=P2P_PORT)
    node.start_background()


def build_http_response(json_data, status="200 OK", extra_headers=None):
    body_bytes = json.dumps(json_data).encode("utf-8")

    headers = [
        f"HTTP/1.1 {status}",
        "Content-Type: application/json",
        "Access-Control-Allow-Origin: *",
        "Access-Control-Allow-Headers: Content-Type, Cookie",
        "Access-Control-Allow-Methods: GET, POST, OPTIONS",
        f"Content-Length: {len(body_bytes)}",
    ]

    if extra_headers:
        for k, v in extra_headers.items():
            headers.append(f"{k}: {v}")

    response = ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8") + body_bytes
    return response


def _json_body(body, default=None):
    if default is None:
        default = {}

    if body is None:
        return default

    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", errors="replace")

    if isinstance(body, str):
        body = body.strip()
        if not body:
            return default
        return json.loads(body)

    if isinstance(body, dict):
        return body

    return default


def _header_get(headers, key, default=""):
    try:
        return headers.get(key, default) or default
    except Exception:
        return default


def _get_cookie(headers, name):
    cookie_header = _header_get(headers, "Cookie", "")
    for part in cookie_header.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip() == name:
                return v.strip()
    return None


@app.route('/self-info', methods=['GET'])
def self_info(headers="guest", body="anonymous"):
    return build_http_response({
        "ok": True,
        "ip": APP_IP,
        "p2p_port": P2P_PORT,
        "mode": APP_MODE
    })


@app.route('/instance', methods=['GET'])
def instance(headers="guest", body="anonymous"):
    return build_http_response({
        "ok": True,
        "instance": INSTANCE_ID,
        "ip": APP_IP,
        "p2p_port": P2P_PORT,
        "mode": APP_MODE
    })


# -------------------------
# tracker logic
# -------------------------
@app.route('/submit-info', methods=['POST'])
def submit_info(headers="guest", body="anonymous"):
    try:
        peer_info = _json_body(body, {})
        username = peer_info.get("username")
        ip = peer_info.get("ip")
        port = peer_info.get("port")

        if username and ip and port:
            active_peers[username] = {
                "ip": ip,
                "port": port
            }
            data = {"ok": True, "message": f"peer {username} registered"}
        else:
            data = {"ok": False, "error": "missing username/ip/port"}
    except Exception:
        data = {"ok": False, "error": "invalid JSON"}

    return build_http_response(data)

@app.route('/add-list', methods=['POST'])
def add_list(headers="guest", body="anonymous"):
    try:
        msg_data = _json_body(body, {})
        new_channel = msg_data.get("channel")
        if new_channel:
            if new_channel not in active_channels:
                active_channels.append(new_channel)
            data = {"ok": True, "message": f"Channel '{new_channel}' added"}
        else:
            data = {"ok": False, "error": "Missing channel name"}
    except Exception:
        data = {"ok": False, "error": "invalid request"}
    return build_http_response(data)

@app.route('/get-list', methods=['GET'])
def get_list(headers="guest", body="anonymous"):
    peer_list = [
        {"username": k, "ip": v["ip"], "port": v["port"]}
        for k, v in active_peers.items()
    ]
    data = {
        "ok": True,
        "peers": peer_list,
        "channels": active_channels 
    }
    return build_http_response(data)


@app.route("/connect-peer", methods=["POST"])
def connect_peer(headers="guest", body="anonymous"):
    try:
        req = _json_body(body, {})
        # Đổi "from" thành "target_username"
        target = req.get("target_username") 
        if target:
            data = {"ok": True, "status": "connected", "message": f"hello {target}, I'm ready!"}
        else:
            data = {"ok": False, "error": "missing target_username"}
    except Exception:
        data = {"ok": False, "error": "invalid JSON format"}
    return build_http_response(data)


# -------------------------
# local peer routes
# -------------------------
@app.route('/messages', methods=['POST'])
def messages(headers="guest", body="{}"):
    if node is None:
        return build_http_response({"ok": False, "error": "messages not available on tracker mode"})

    try:
        data = _json_body(body, {})
        channel = data.get("channel", "general")
        after_seq = int(data.get("after_seq", 0))
        return build_http_response(node.get_messages(channel=channel, after_seq=after_seq))
    except Exception as exc:
        return build_http_response({"ok": False, "error": str(exc)})


@app.route('/send-peer', methods=['POST'])
def send_peer(headers="guest", body="anonymous"):
    if node is None:
        return build_http_response({"ok": False, "error": "send-peer not available on tracker mode"})

    try:
        msg_data = _json_body(body, {})
        sender = msg_data.get("sender")
        channel = msg_data.get("channel", "general")
        message = str(msg_data.get("message", "")).strip()
        ip = msg_data.get("ip")
        port = int(msg_data.get("port", 0))

        if not message:
            return build_http_response({"ok": False, "error": "empty message"})
        if not ip or not port:
            return build_http_response({"ok": False, "error": "missing peer ip/port"})

        result = node.send_direct_sync(
            sender=sender,
            ip=ip,
            port=port,
            channel=channel,
            text=message,
        )
        return build_http_response(result)
    except Exception as exc:
        return build_http_response({"ok": False, "error": str(exc)})


@app.route('/broadcast-peer', methods=['POST'])
def broadcast_peer(headers="guest", body="anonymous"):
    if node is None:
        return build_http_response({"ok": False, "error": "broadcast-peer not available on tracker mode"})

    try:
        msg_data = _json_body(body, {})
        sender = msg_data.get("sender")
        channel = msg_data.get("channel", "general")
        message = str(msg_data.get("message", "")).strip()
        peers = msg_data.get("peers", [])

        if not message:
            return build_http_response({"ok": False, "error": "empty message"})

        result = node.broadcast_sync(
            sender=sender,
            peers=peers,
            channel=channel,
            text=message,
        )
        return build_http_response(result)
    except Exception as exc:
        return build_http_response({"ok": False, "error": str(exc)})


# -------------------------
# auth + session
# -------------------------
@app.route('/login', methods=['POST'])
def login(headers="guest", body="anonymous"):
    try:
        msg_data = _json_body(body, {})
        username = str(msg_data.get("username", "")).strip()
        password = str(msg_data.get("password", "")).strip()

        expected_password = USERS.get(username)

        if not username or not password:
            return build_http_response(
                {"ok": False, "error": "missing username or password"},
                status="400 Bad Request"
            )

        if expected_password is None or expected_password != password:
            return build_http_response(
                {"ok": False, "error": "invalid username or password"},
                status="401 Unauthorized"
            )

        session_id = str(uuid.uuid4())
        sessions[session_id] = username

        return build_http_response(
            {
                "ok": True,
                "message": "login success",
                "username": username
            },
            extra_headers={
                "Set-Cookie": f"session_id={session_id}; Path=/; HttpOnly"
            }
        )

    except Exception as exc:
        print(f"[login] parse error: {exc}")
        return build_http_response(
            {"ok": False, "error": "invalid request"},
            status="400 Bad Request"
        )


@app.route('/me', methods=['GET'])
def me(headers="guest", body="anonymous"):
    session_id = _get_cookie(headers, "session_id")
    username = sessions.get(session_id)

    if not username:
        return build_http_response(
            {"ok": False, "error": "unauthorized"},
            status="401 Unauthorized"
        )

    return build_http_response({
        "ok": True,
        "username": username
    })


@app.route('/logout', methods=['POST'])
def logout(headers="guest", body="anonymous"):
    session_id = _get_cookie(headers, "session_id")
    if session_id in sessions:
        del sessions[session_id]

    return build_http_response(
        {"ok": True, "message": "logout success"},
        extra_headers={
            "Set-Cookie": "session_id=deleted; Path=/; Max-Age=0"
        }
    )

@app.route('/greeting', methods=['PUT'])
def greeting(headers="guest", body="anonymous"):
    return build_http_response({"ok": True, "message": "Framework ho tro PUT thanh cong!"})

@app.route('/remove-peer', methods=['DELETE'])
def delete_peer(headers="guest", body="anonymous"):
    return build_http_response({"ok": True, "message": "Framework ho tro DELETE thanh cong!"})

def create_sampleapp(ip, port, mode="peer"):
    print("=" * 40)
    if mode == 'tracker':
        print("[*] STARTING TRACKER SERVER")
        print(f"[*] Managing P2P directory at: {ip}:{port}")
    else:
        print("[*] STARTING PEER NODE")
        print(f"[*] Listening for HTTP at: {ip}:{port}")
        print(f"[*] Listening for P2P at: {APP_IP}:{P2P_PORT}")
    print("=" * 40)

    app.prepare_address(ip, port)
    app.run()