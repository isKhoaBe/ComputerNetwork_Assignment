#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

import asyncio
import inspect
import json

from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict


class HttpAdapter:
    """
    A mutable HTTP adapter for managing client connections and routing requests.
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        self.ip = ip
        self.port = port
        self.conn = conn
        self.connaddr = connaddr
        self.routes = routes or {}
        self.request = Request()
        self.response = Response()

    # -------------------------------------------------
    # Internal helpers
    # -------------------------------------------------
    def _normalize_handler_output(self, response_body):
        """
        Normalize handler output before passing to Response.build_response().

        Supported:
        - dict  -> JSON bytes
        - str   -> UTF-8 bytes
        - bytes -> keep as-is
        - bytearray -> convert to bytes

        If bytes already represent a full raw HTTP response that starts with
        b"HTTP/1.1 ", caller may send it directly.
        """
        if isinstance(response_body, dict):
            return json.dumps(response_body).encode("utf-8")

        if isinstance(response_body, str):
            return response_body.encode("utf-8")

        if isinstance(response_body, bytearray):
            return bytes(response_body)

        return response_body

    def _build_hook_response_sync(self, req, resp, handler):
        kwargs = {
            "headers": req.headers,
            "body": req.body,
        }

        try:
            if inspect.iscoroutinefunction(handler):
                response_body = asyncio.run(handler(**kwargs))
            else:
                response_body = handler(**kwargs)
        except Exception as e:
            print("[HttpAdapter] Hook error: {}".format(e))
            response_body = {"ok": False, "error": "internal server error"}

        response_body = self._normalize_handler_output(response_body)

        if isinstance(response_body, (bytes, bytearray)) and response_body.startswith(b"HTTP/1.1 "):
            return bytes(response_body)

        return resp.build_response(req, envelop_content=response_body)

    async def _build_hook_response_async(self, req, resp, handler):
        kwargs = {
            "headers": req.headers,
            "body": req.body,
        }

        try:
            if inspect.iscoroutinefunction(handler):
                response_body = await handler(**kwargs)
            else:
                response_body = handler(**kwargs)
        except Exception as e:
            print("[HttpAdapter] Hook error: {}".format(e))
            response_body = {"ok": False, "error": "internal server error"}

        response_body = self._normalize_handler_output(response_body)

        if isinstance(response_body, (bytes, bytearray)) and response_body.startswith(b"HTTP/1.1 "):
            return bytes(response_body)

        return resp.build_response(req, envelop_content=response_body)

    # -------------------------------------------------
    # Main handlers
    # -------------------------------------------------
    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection in synchronous mode.
        """
        self.conn = conn
        self.connaddr = addr

        req = self.request
        resp = self.response

        try:
            raw = conn.recv(4096)
            if not raw:
                conn.close()
                return

            msg = raw.decode("utf-8", errors="ignore")
            req.prepare(msg, routes)

            print("[HttpAdapter] Invoke handle_client connection {}".format(addr))

            if req.hook:
                response = self._build_hook_response_sync(req, resp, req.hook)
            else:
                response = resp.build_response(req)

            if response:
                conn.sendall(response)

        except Exception as e:
            print("[HttpAdapter] handle_client error: {}".format(e))
            try:
                conn.sendall(
                    b"HTTP/1.1 500 Internal Server Error\r\n"
                    b"Content-Type: text/plain\r\n"
                    b"Content-Length: 21\r\n"
                    b"\r\n"
                    b"internal server error"
                )
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    async def handle_client_coroutine(self, reader, writer):
        """
        Handle an incoming client connection asynchronously.
        """
        req = self.request
        resp = self.response

        addr = writer.get_extra_info("peername")
        print("[HttpAdapter] Invoke handle_client_coroutine connection {}".format(addr))

        try:
            try:
                raw = await reader.read(4096)
            except BlockingIOError:
                await asyncio.sleep(0.01)
                raw = await reader.read(4096)

            if not raw:
                return

            msg = raw.decode("utf-8", errors="ignore")
            req.prepare(msg, self.routes)

            if req.hook:
                response = await self._build_hook_response_async(req, resp, req.hook)
            else:
                response = resp.build_response(req)

            if response:
                writer.write(response)
                await writer.drain()

        except Exception as e:
            print("[HttpAdapter] handle_client_coroutine error: {}".format(e))
            try:
                writer.write(
                    b"HTTP/1.1 500 Internal Server Error\r\n"
                    b"Content-Type: text/plain\r\n"
                    b"Content-Length: 21\r\n"
                    b"\r\n"
                    b"internal server error"
                )
                await writer.drain()
            except Exception:
                pass

    # -------------------------------------------------
    # Optional helpers
    # -------------------------------------------------
    def extract_cookies(self, headers):
        """
        Extract cookies from headers into a CaseInsensitiveDict.
        """
        cookies = CaseInsensitiveDict()

        if isinstance(headers, dict):
            cookie_header = headers.get("Cookie") or headers.get("cookie")
            if not cookie_header:
                return cookies

            for pair in cookie_header.split(";"):
                if "=" in pair:
                    key, value = pair.strip().split("=", 1)
                    cookies[key] = value
            return cookies

        return cookies

    def add_headers(self, request):
        """
        Add headers to the request.
        This method is intended to be overridden by subclasses.
        """
        return None

    def build_proxy_headers(self, proxy):
        """
        Returns a dictionary of headers to add to any request sent through a proxy.
        """
        headers = {}
        username, password = ("user1", "password")

        if username:
            headers["Proxy-Authorization"] = (username, password)

        return headers