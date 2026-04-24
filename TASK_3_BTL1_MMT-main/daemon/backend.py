import socket
from httpadapter import handle_http
from response import Response

def run_backend(ip, port, router):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((ip, port))
    s.listen(5)
    print("[Backend] Running at %s:%d" % (ip, port))

    while True:
        conn, addr = s.accept()
        print("[Backend] Connection from", addr)
        def handler(req):
            h = router.get(req.path, lambda r: Response("404 Not Found", 404))
            return h(req)
        handle_http(conn, handler)


def create_backend(ip, port, router):
    run_backend(ip, port, router)
