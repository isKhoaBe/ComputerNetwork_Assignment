import json
import re
import socket
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Tuple


_rr_counter = defaultdict(int)


def _http_error(status_code: int, reason: str, message: str) -> bytes:
    body = message.encode("utf-8")
    return (
        f"HTTP/1.1 {status_code} {reason}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("utf-8") + body


def _recv_http_request(conn: socket.socket) -> bytes:
    raw = b""
    conn.settimeout(5.0)

    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        raw += chunk

        if b"\r\n\r\n" in raw:
            header_part, body_part = raw.split(b"\r\n\r\n", 1)
            headers_text = header_part.decode("utf-8", errors="replace")

            content_length = 0
            for line in headers_text.splitlines():
                if line.lower().startswith("content-length:"):
                    try:
                        content_length = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        content_length = 0
                    break

            if len(body_part) >= content_length:
                break

    return raw


def _extract_hostname(request_text: str) -> Optional[str]:
    for line in request_text.split("\r\n"):
        if line.lower().startswith("host:"):
            return line.split(":", 1)[1].strip()
    return None


def _pick_backend(route_value):
    backend_spec, policy = route_value

    if isinstance(backend_spec, str):
        target = backend_spec
    else:
        normalized_policy = (policy or "").strip().lower()
        if normalized_policy in {"round", "round-robin", "roundrobin"}:
            idx = _rr_counter[id(backend_spec)] % len(backend_spec)
            _rr_counter[id(backend_spec)] += 1
            target = backend_spec[idx]
        else:
            target = backend_spec[0]

    if ":" not in target:
        raise ValueError(f"Invalid backend target: {target}")

    host, port = target.rsplit(":", 1)
    return host, int(port)


def _parse_http_response(raw: bytes) -> Tuple[int, Dict[str, str], bytes]:
    header_part, _, body = raw.partition(b"\r\n\r\n")
    header_text = header_part.decode("utf-8", errors="replace")
    lines = header_text.split("\r\n")

    status_code = 0
    if lines:
        parts = lines[0].split()
        if len(parts) >= 2:
            try:
                status_code = int(parts[1])
            except ValueError:
                status_code = 0

    headers: Dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    return status_code, headers, body


def forward_request(host: str, port: int, request: bytes) -> bytes:
    try:
        with socket.create_connection((host, port), timeout=5.0) as backend:
            backend.sendall(request)

            response = b""
            while True:
                chunk = backend.recv(4096)
                if not chunk:
                    break
                response += chunk

            if response:
                return response

            return _http_error(502, "Bad Gateway", "Empty response from upstream")
    except Exception as exc:
        print(f"[Proxy] forward_request error -> {host}:{port} : {exc}")
        return _http_error(502, "Bad Gateway", f"Cannot reach upstream {host}:{port}")


def _guess_tracker_backend(routes) -> Optional[Tuple[str, int]]:
    for host, route_value in routes.items():
        try:
            backend_spec, _policy = route_value
            candidates = [backend_spec] if isinstance(backend_spec, str) else list(backend_spec)
            for target in candidates:
                if ":" not in target:
                    continue
                upstream_host, upstream_port = target.rsplit(":", 1)
                if int(upstream_port) == 9000:
                    return upstream_host, int(upstream_port)
        except Exception:
            continue
    return None


def _fetch_tracker_peers(routes) -> Optional[List[dict]]:
    tracker_backend = _guess_tracker_backend(routes)
    if not tracker_backend:
        print("[Proxy] cannot find tracker backend in routes")
        return None

    tracker_host, tracker_port = tracker_backend
    tracker_request = (
        "GET /get-list HTTP/1.1\r\n"
        f"Host: {tracker_host}:{tracker_port}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("utf-8")

    raw_response = forward_request(tracker_host, tracker_port, tracker_request)
    status_code, _headers, body = _parse_http_response(raw_response)

    if status_code != 200:
        print(f"[Proxy] tracker /get-list returned status {status_code}")
        return None

    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
        peers = payload.get("peers", [])
        if isinstance(peers, list):
            return peers
    except Exception as exc:
        print(f"[Proxy] cannot parse tracker response: {exc}")

    return None


def _extract_dynamic_username(hostname: str) -> Optional[str]:
    host_no_port = hostname.split(":", 1)[0].strip().lower()

    # Supported examples:
    # alice.192.168.208.150.nip.io
    # bob.local
    # charlie.peer
    m = re.match(r"^([a-zA-Z0-9_-]+)\.", host_no_port)
    if not m:
        return None

    username = m.group(1).strip().lower()
    if username in {"www", "rr"}:
        return None
    return username


def _infer_http_port_from_peer(peer: dict) -> Optional[int]:
    try:
        p2p_port = int(peer.get("port", 0))
    except Exception:
        return None

    # Convention used in this project:
    # HTTP 9001 <-> P2P 9101, HTTP 9002 <-> P2P 9102, ...
    # If your project changes that convention, store http_port in tracker instead.
    if p2p_port >= 9100:
        return p2p_port - 100
    return None


def _resolve_dynamic_peer_backend(hostname: str, routes) -> Optional[Tuple[str, int]]:
    username = _extract_dynamic_username(hostname)
    if not username:
        return None

    peers = _fetch_tracker_peers(routes)
    if not peers:
        return None

    for peer in peers:
        if str(peer.get("username", "")).strip().lower() == username:
            ip = peer.get("ip")
            http_port = _infer_http_port_from_peer(peer)
            if ip and http_port:
                print(f"[Proxy] dynamic resolve {username} -> {ip}:{http_port}")
                return ip, http_port

    print(f"[Proxy] username {username} not found in tracker list")
    return None


def resolve_backend(hostname: str, routes) -> Tuple[str, int]:
    # 1) Static route from proxy.conf first
    if hostname in routes:
        return _pick_backend(routes[hostname])

    # 2) Dynamic peer resolve via tracker
    dynamic_target = _resolve_dynamic_peer_backend(hostname, routes)
    if dynamic_target:
        return dynamic_target

    raise KeyError(f"Unknown host: {hostname}")


def handle_client(ip, port, conn, addr, routes):
    try:
        raw_request = _recv_http_request(conn)
        if not raw_request:
            conn.sendall(_http_error(400, "Bad Request", "Empty request"))
            return

        request_text = raw_request.decode("utf-8", errors="replace")
        hostname = _extract_hostname(request_text)

        if not hostname:
            conn.sendall(_http_error(400, "Bad Request", "Missing Host header"))
            return

        print(f"[Proxy] {addr} at Host: {hostname}")

        try:
            target_host, target_port = resolve_backend(hostname, routes)
        except KeyError as exc:
            conn.sendall(_http_error(404, "Not Found", str(exc)))
            return
        except Exception as exc:
            conn.sendall(_http_error(500, "Internal Server Error", f"Route error: {exc}"))
            return

        print(f"[Proxy] Host name {hostname} is forwarded to {target_host}:{target_port}")

        response = forward_request(target_host, target_port, raw_request)
        conn.sendall(response)

    except Exception as exc:
        print(f"[Proxy] handle_client error: {exc}")
        try:
            conn.sendall(_http_error(500, "Internal Server Error", str(exc)))
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_proxy(ip, port, routes):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((ip, port))
    server.listen(50)

    print(f"[Proxy] Listening on IP {ip} port {port}")

    while True:
        conn, addr = server.accept()
        t = threading.Thread(
            target=handle_client,
            args=(ip, port, conn, addr, routes),
            daemon=True,
        )
        t.start()


def create_proxy(ip, port, routes):
    run_proxy(ip, port, routes)