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

from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

import asyncio
import base64
import json
import inspect
import uuid

SESSION_STORE = {}

USER_DB = {
            "admin": "admin123",
            "user1": "password",
        }

def create_session(username):
    token = str(uuid.uuid4())
    SESSION_STORE[token] = username
    return token


def destroy_session(token):
    SESSION_STORE.pop(token, None)

class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.

    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>` 
    and :class:`Response <Response>` objects for full request lifecycle management.

    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
        #--- Additionals ---#
        "user",
        "session_token",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        """
        Initialize a new HttpAdapter instance.

        :param ip (str): IP address of the client.
        :param port (int): Port number of the client.
        :param conn (socket): Active socket connection.
        :param connaddr (tuple): Address of the connected client.
        :param routes (dict): Mapping of route paths to handler functions.
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes
        #: Request
        self.request = Request()
        #: Response
        self.response = Response()

    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """

        # Connection handler.
        self.conn = conn        
        # Connection address.
        self.connaddr = addr
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        # Handle the request
        msg = conn.recv(4096).decode()
        req.prepare(msg, routes)
        print("[HttpAdapter] Invoke handle_client connection {}".format(addr))

        response = b""

        # Handle request hook
        if req.hook:
            auth_result = self.authenticate(req)

            if not auth_result["authenticated"]:
                response = self.build_auth_challenge()
            else:
                req.user = auth_result["username"]
                result = req.hook(req.headers, req.body)
                if inspect.isawaitable(result):
                    result = asyncio.run(result)
                response = self.build_json_response(req, result)
        else:
            #This is the response from object Response
            response = resp.build_response(req)

        #print("[HttpAdapter] Response content {}".format(response))
        conn.sendall(response if isinstance(response, bytes) else response.encode())
        conn.close()

    async def handle_client_coroutine(self, reader, writer):
        """
        Handle an incoming client connection using stream reader writer asynchronously.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        addr = writer.get_extra_info("peername")
        print("[HttpAdapter] Invoke handle_client_coroutine connection {}".format(addr))

        # TODO Handle the request asynchronously
        msg = await reader.read(1024)


        req.prepare(msg.decode("utf-8"), routes=self.routes)

        # Handle request hook
        if req.hook:
            auth_result = self.authenticate(req)
            if not auth_result["authenticated"]:
                response = self.build_auth_challenge()
            else:
                req.user = auth_result["username"]
                result = req.hook(req.headers, req.body)
                if inspect.isawaitable(result):
                    result = await result
                response = self.build_json_response(req, result)
        else:
            # Build response
            #print("[HttpAdapter] Start **ASYNC** build_response with type {}".format(type(req)))
            response = resp.build_response(req)

        # Send all the response asynchronously
        writer.write(response if isinstance(response, bytes) else response.encode("utf-8"))
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    @property
    def extract_cookies(self):
        """
        Build cookies from the :class:`Request <Request>` headers.

        :param req:(Request) The :class:`Request <Request>` object.
        :param resp: (Response) The res:class:`Response <Response>` object.
        :rtype: cookies - A dictionary of cookie key-value pairs.
        """
        cookies = {}

        headers = self.request.headers or {}
        if not isinstance(headers, CaseInsensitiveDict):
            headers = CaseInsensitiveDict(headers)

        cookie_header = headers.get("Cookie", "")
        if not cookie_header:
            return cookies
        for pair in cookie_header.split(";"):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                cookies[key.strip()] = value.strip()
        return cookies

    def build_response_object(self, req, resp):
        """Builds a :class:`Response <Response>` object.

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response()

        # Set encoding.
        response.encoding = None
        response.raw = resp
        response.reason = getattr(response.raw, "reason", None)

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Add new cookies from the server.
        response.cookies = self.extract_cookies

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response


    def build_response(self, req, resp):
        """Backward-compatible alias for build_response_object.

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The response object.
        :rtype: Response
        """
        return self.build_response_object(req, resp)

    def build_json_response(self, req, resp):
        """Builds a JSON HTTP response payload.

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: bytes
        """
        if isinstance(resp, bytes):
            body = resp
        elif isinstance(resp, str):
            body = resp.encode("utf-8")
        else:
            body = json.dumps(resp).encode("utf-8")

        header = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("utf-8")
        return header + body


    def build_auth_challenge(self):
        """Builds a 401 challenge response for unauthorized requests."""
        body = b'{"error": "Unauthorized"}'
        header = (
            "HTTP/1.1 401 Unauthorized\r\n"
            "WWW-Authenticate: Basic realm=\"AsynapRous\"\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("utf-8")
        return header + body


    # def get_connection(self, url, proxies=None):
        # """Returns a url connection for the given URL. 

        # :param url: The URL to connect to.
        # :param proxies: (optional) A Requests-style dictionary of proxies used on this request.
        # :rtype: int
        # """

        # proxy = select_proxy(url, proxies)

        # if proxy:
            # proxy = prepend_scheme_if_needed(proxy, "http")
            # proxy_url = parse_url(proxy)
            # if not proxy_url.host:
                # raise InvalidProxyURL(
                    # "Please check proxy URL. It is malformed "
                    # "and could be missing the host."
                # )
            # proxy_manager = self.proxy_manager_for(proxy)
            # conn = proxy_manager.connection_from_url(url)
        # else:
            # # Only scheme should be lower case
            # parsed = urlparse(url)
            # url = parsed.geturl()
            # conn = self.poolmanager.connection_from_url(url)

        # return conn


    def add_headers(self, request):
        """
        Add headers to the request.

        This method is intended to be overridden by subclasses to inject
        custom headers. It does nothing by default.

        
        :param request: :class:`Request <Request>` to add headers to.
        """
        pass

    def build_proxy_headers(self, proxy):
        """Returns a dictionary of the headers to add to any request sent
        through a proxy. 

        :class:`HttpAdapter <HttpAdapter>`.

        :param proxy: The url of the proxy being used for this request.
        :rtype: dict
        """
        headers = {}

        from .utils import get_auth_from_url
        username, password = get_auth_from_url(proxy)

        if username and password:
            credentials = f"{username}:{password}"
            encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
            headers["Proxy-Authorization"] = f"Basic {encoded}"

        return headers
    
    def authenticate(self, req):
        """
        Authenticate a request using either Cookie session or Basic Auth.
        Checks Cookie first, falls back to basic auth.
        :param req: Request object
        :rtype: dict - {"authenticated": bool, "username": str or None}
        """

        # --- Tries Cookies Auth first ---
        cookies = self.extract_cookies
        session_token = cookies.get("session", None)

        if session_token:
            username = SESSION_STORE.get(session_token)
            if username:
                return {"authenticated": True, "username": username}
            
        # --- Falls back to Basic Auth ---
        headers = req.headers or {}
        if not isinstance(headers, CaseInsensitiveDict):
            headers = CaseInsensitiveDict(headers)

        auth_header = headers.get("Authorization", "")

        if auth_header.startswith("Basic "):
            encoded = auth_header[len("Basic "):]
            try:
                decoded = base64.b64decode(encoded).decode("utf-8")
                username, password = decoded.split(":", 1)
                if self.validate_credentials(username, password):
                    return {"authenticated": True, "username": username}
            except Exception:
                pass
        return {"authenticated": False, "username": None}
    
    def register_user(username, password):
        """Register a new user into the user database.
        :param username: (str) The username to register.
        :param password: (str) The password to store.
        """
        USER_DB[username] = password




    def validate_credentials(self, username, password):
        """Validate username and password against the in-memory user database.

        :param username: (str) The username to check.
        :param password: (str) The password to check.
        :rtype: bool
        """
        return USER_DB.get(username) == password