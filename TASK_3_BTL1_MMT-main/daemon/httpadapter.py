from response import Response
from request import Request

def handle_http(conn, handler):
    raw = conn.recv(1024)
    if not raw:
        return
    req = Request(raw)
    print "[HTTPAdapter] Received:", req.method, req.path
    res = handler(req)
    if type(res) is str:
        res = Response(res)
    conn.send(res.build())
    conn.close()
