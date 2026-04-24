class Response:
    def __init__(self, body, code=200, content_type="text/plain"):
        self.body = body
        self.code = code
        self.content_type = content_type
        self.headers = {}

    def build(self):
        if isinstance(self.body, str):
            body_bytes = self.body
        else:
            body_bytes = self.body

        header = "HTTP/1.1 {} OK\r\nContent-Type: {}\r\nContent-Length: {}\r\n".format(
            self.code, self.content_type, len(body_bytes)
        )

        for k, v in self.headers.items():
            header += "{}: {}\r\n".format(k, v)

        header += "\r\n"

        return header.encode("utf-8") + body_bytes
