#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.response
~~~~~~~~~~~~~~~~~

This module provides a :class:`Response <Response>` object to manage and persist
response settings (cookies, auth, proxies), and to construct HTTP responses
based on incoming requests.

The current version supports MIME type detection, content loading and header formatting
"""

import datetime
import os
import mimetypes
import json
from .dictionary import CaseInsensitiveDict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep


class Response:
    __attrs__ = [
        "_content",
        "_header",
        "status_code",
        "method",
        "headers",
        "url",
        "history",
        "encoding",
        "reason",
        "cookies",
        "elapsed",
        "request",
        "body",
        "reason",
    ]

    def __init__(self, request=None):
        self._content = False
        self._content_consumed = False
        self._next = None

        self.status_code = 200
        self.headers = {}
        self.url = None
        self.encoding = None
        self.history = []
        self.reason = "OK"
        self.cookies = CaseInsensitiveDict()
        self.elapsed = datetime.timedelta(0)
        self.request = request

    def get_mime_type(self, path):
        if not path:
            return "text/html"

        lower = path.lower()
        if lower.endswith(".js"):
            return "application/javascript"
        if lower.endswith(".css"):
            return "text/css"
        if lower.endswith(".html"):
            return "text/html"
        if lower.endswith(".json"):
            return "application/json"
        if lower.endswith(".ico"):
            return "image/x-icon"

        try:
            mime_type, _ = mimetypes.guess_type(path)
        except Exception:
            return "application/octet-stream"

        return mime_type or "application/octet-stream"

    def prepare_content_type(self, path, mime_type="text/html"):
        if not hasattr(self, "headers") or self.headers is None:
            self.headers = {}

        safe_path = (path or "/").split("?", 1)[0]

        if safe_path == "/" or safe_path.endswith(".html"):
            self.headers["Content-Type"] = "text/html; charset=utf-8"
            return os.path.join(BASE_DIR, "www")

        if safe_path.startswith("/static/css/") or mime_type == "text/css":
            self.headers["Content-Type"] = "text/css; charset=utf-8"
            return os.path.join(BASE_DIR, "static", "css")

        if safe_path.startswith("/static/js/") or mime_type in ("application/javascript", "text/javascript"):
            self.headers["Content-Type"] = "application/javascript; charset=utf-8"
            return os.path.join(BASE_DIR, "static", "js")

        if safe_path.startswith("/static/images/") or mime_type.startswith("image/"):
            self.headers["Content-Type"] = mime_type
            return os.path.join(BASE_DIR, "static", "images")

        if mime_type == "application/json":
            self.headers["Content-Type"] = "application/json"
            return os.path.join(BASE_DIR, "www")

        self.headers["Content-Type"] = mime_type
        return os.path.join(BASE_DIR, "www")

    def build_content(self, path, base_dir):
        safe_path = (path or "/").split("?", 1)[0]

        if safe_path in ("", "/"):
            rel_path = "index.html"
        elif safe_path.startswith("/static/css/"):
            rel_path = safe_path[len("/static/css/"):]
        elif safe_path.startswith("/static/js/"):
            rel_path = safe_path[len("/static/js/"):]
        elif safe_path.startswith("/static/images/"):
            rel_path = safe_path[len("/static/images/"):]
        elif safe_path.startswith("/"):
            rel_path = safe_path[1:]
        else:
            rel_path = safe_path

        filepath = os.path.normpath(os.path.join(base_dir, rel_path))
        base_dir_norm = os.path.normpath(base_dir)

        print(f"[Response] Serving object path={safe_path} -> {filepath}")

        if not filepath.startswith(base_dir_norm):
            raise FileNotFoundError("invalid path traversal")

        with open(filepath, "rb") as f:
            content = f.read()

        return len(content), content

    def build_response_header(self, request):
        reqhdr = request.headers if getattr(request, "headers", None) else {}

        headers = {
            "Date": datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "Content-Type": self.headers.get("Content-Type", "text/html; charset=utf-8"),
            "Content-Length": str(len(self._content)),
            "Cache-Control": "no-cache",
            "Connection": "close",
            "Accept": reqhdr.get("Accept", "*/*"),
            "Accept-Language": reqhdr.get("Accept-Language", "en-US,en;q=0.9"),
            "User-Agent": reqhdr.get("User-Agent", "AsynapRous/1.0"),
        }

        if self.cookies:
            cookies_parts = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
            headers["Set-Cookie"] = cookies_parts

        status_line = f"HTTP/1.1 {self.status_code} {self.reason}\r\n"
        fmt_header = status_line + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n"
        return fmt_header.encode("utf-8")

    def build_notfound(self):
        body = b"404 Not Found"
        return (
            b"HTTP/1.1 404 Not Found\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"Connection: close\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
            + body
        )

    def build_internal_error(self, message=b"internal server error"):
        if isinstance(message, str):
            message = message.encode("utf-8")
        return (
            b"HTTP/1.1 500 Internal Server Error\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"Connection: close\r\n"
            + f"Content-Length: {len(message)}\r\n\r\n".encode("utf-8")
            + message
        )

    def build_response(self, request, envelop_content=None):
        print(f"[Response] Start build response with req {request}")

        if envelop_content is not None:
            # sampleapp already returns full HTTP response bytes
            if isinstance(envelop_content, (bytes, bytearray)) and envelop_content.startswith(b"HTTP/1.1 "):
                return envelop_content

            if isinstance(envelop_content, dict):
                self._content = json.dumps(envelop_content).encode("utf-8")
                self.headers["Content-Type"] = "application/json"
            elif isinstance(envelop_content, str):
                self._content = envelop_content.encode("utf-8")
            else:
                self._content = envelop_content

            self.status_code = 200
            self.reason = "OK"
            self._header = self.build_response_header(request)
            return self._header + self._content

        path = request.path
        mime_type = self.get_mime_type(path)
        print(f"[Response] {request.method} path {request.path} mime_type {mime_type}")

        try:
            base_dir = self.prepare_content_type(path, mime_type)
            content_length, self._content = self.build_content(path, base_dir)
            self.status_code = 200
            self.reason = "OK"
        except FileNotFoundError:
            return self.build_notfound()
        except Exception as e:
            print(f"[Response] static serve error: {e}")
            return self.build_internal_error("internal server error")

        self._header = self.build_response_header(request)
        return self._header + self._content

    def build_login_response(self, username, session_token):
        body = json.dumps({"message": "Login successful", "user": username}).encode("utf-8")

        header = (
            "HTTP/1.1 200 OK\r\n"
            f"Set-Cookie: session={session_token}; HttpOnly; Path=/\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("utf-8")

        return header + body

    def build_logout_response(self):
        body = b'{"message": "Logged out"}'
        header = (
            "HTTP/1.1 200 OK\r\n"
            "Set-Cookie: session=; HttpOnly; Path=/; Max-Age=0\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("utf-8")
        return header + body