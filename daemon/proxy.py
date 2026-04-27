import socket
import threading
from collections import defaultdict


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


def _extract_hostname(request_text: str) -> str | None:
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

        if hostname not in routes:
            conn.sendall(_http_error(404, "Not Found", f"Unknown host: {hostname}"))
            return

        try:
            target_host, target_port = _pick_backend(routes[hostname])
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