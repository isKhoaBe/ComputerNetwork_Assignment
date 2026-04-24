import socket
import threading

HOSTS = {
    "app.local": {
        "backends": ["backend1:9001", "backend2:9001"],
        "policy": "round-robin",
        "index": 0
    },
}

def select_backend(host):
    cfg = HOSTS.get(host)
    if not cfg:
        return None
    backends = cfg["backends"]
    if cfg["policy"] == "round-robin":
        idx = cfg["index"]
        backend = backends[idx % len(backends)]
        cfg["index"] += 1
        return backend
    else:
        return backends[0]

def handle_client(client_socket):
    raw = client_socket.recv(4096)
    if not raw:
        client_socket.close()
        return

    lines = raw.split("\r\n")
    if len(lines[0].split()) < 3:
        client_socket.close()
        return

    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()

    host = headers.get("Host")
    backend_addr = select_backend(host)
    if not backend_addr:
        client_socket.send(b"HTTP/1.1 502 Bad Gateway\r\n\r\nHost not found")
        client_socket.close()
        return

    hostname, port = backend_addr.split(":")
    remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    remote.connect((hostname, int(port)))
    remote.send(raw)

    while True:
        data = remote.recv(4096)
        if not data:
            break
        client_socket.send(data)

    remote.close()
    client_socket.close()

def start_proxy(listen_ip="0.0.0.0", listen_port=8080):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((listen_ip, listen_port))
    server.listen(5)
    print("[Proxy] Listening on {}:{}".format(listen_ip, listen_port))

    while True:
        client_socket, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(client_socket,))
        t.start()

if __name__ == "__main__":
    start_proxy()
