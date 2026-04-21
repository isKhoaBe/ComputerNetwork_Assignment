#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
app.sampleapp
~~~~~~~~~~~~~~~~~

"""

import sys
import os
import importlib.util
import json

from   daemon import AsynapRous

app = AsynapRous()
active_peers = {}
channel_messages =  {}

def build_http_response(json_data):
    body_str = json.dumps(json_data)
    response = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body_str)}\r\n"
        "\r\n"
        f"{body_str}"
    )
    return response.encode("utf-8")

#tracker logic(client-server)
@app.route('/submit-info', methods=['POST'])
def submit_info(headers="guest", body="anonymous"):
    print(f"[tracker] recieve sign-up information: {body}")
    try:
        peer_info = json.loads(body)
        username = peer_info.get("username")
        if username:
            active_peers[username] = {
                "ip": peer_info.get("ip"),
                "port": peer_info.get("port")
            }
            data = {"ok": True, "message":f"peer {username} registered"}
        else:
            data = {"status":"failed", "message":"no username"}
    except json.JSONDecodeError:
        data = {"status":"error", "message":"invalid JSON"}

    # Convert to JSON string and return
    # return  json.dumps(data).encode("utf-8")
    return build_http_response(data)

@app.route('/get-list', methods=['GET'])
def get_list(headers="guest", body="anonymous"):
    peer_list = [{"username": k, "ip": v["ip"], "port": v["port"]} for k,v in active_peers.items()]
    data = {
        "ok":True,
        "peers": peer_list,
        "channel": ["general", "team1"]
    }
    return build_http_response(data)

#chat logic- peer_to_peer
@app.route("/connect-peer", methods=["POST"])
def connect_peer(headers="guest", body="anonymous"):
    try:
        req = json.loads(body)
        sender = req.get("from")
        print(f"[P2P] connect accepted from: {sender}")
        data = {"status": "connected", "message":f"hello {sender}, I'm ready!"}
    except json.JSONDecodeError:
        data = {"status": "error", "message": "Invalid JSON format"}
    # return json.dumps(data).encode("utf-8")
    return build_http_response(data)


@app.route('/send-peer', methods=['POST'])
def send_peer(headers="guest", body="anonymous"):
    print(f">>> DEBUG BODY NHẬN ĐƯỢC: {body}")
    try:
        # Framework đã truyền đúng JSON body vào đây rồi
        msg_data = json.loads(body)

        sender = msg_data.get("sender")
        content = msg_data.get("message")

        print(f"\n[Direct message from {sender}]: {content}")
        data = {"status": "received", "message": "SUCESS!"}
    except Exception as e:
        data = {"status": "error", "message": f"ERROR: {str(e)}"}

    # Trả về bytes, Framework sẽ tự động đính kèm HTTP Header (200 OK)
    # return json.dumps(data).encode("utf-8")
    return build_http_response(data)


@app.route('/broadcast-peer', methods=['POST'])
def broadcast_peer(headers="guest", body="anonymous"):
    try:
        msg_data = json.loads(body)
        channel = msg_data.get("channel","general")
        sender  = msg_data.get("sender")
        content = msg_data.get("message")

        if channel not in channel_messages:
            channel_messages[channel] = []
        channel_messages[channel].append({"from": sender, "msg": content})

        print(f"\n[{channel}] {sender}: {content}")
        data = {"status": "broadcast_received"}
    except Exception:
        data = {"status": "error"}
        
    # return json.dumps(data).encode("utf-8")
    return build_http_response(data)

@app.route('/login', methods=['POST'])
def login(headers="guest", body="anonymous"):
    try:
        msg_data = json.loads(str(body))
        username = msg_data.get("username")
        password = msg_data.get("password")    

        if username and password:
            data = {
                "ok":True,
                "message": "login success",
                "username": username
            }
        else:
            data = {
                "ok":False,
                "error":"invalid username or password"
            }
    except Exception:
        data={"ok":False, "error": "invalid request"}
    return build_http_response(data)
    

#app launcher
def create_sampleapp(ip, port, mode="peer"):
    print("="*40)
    if mode == 'tracker':
        print(f"[*] STARTING TRACKER SERVER")
        print(f"[*] Managing P2P directory at: {ip}:{port}")
    else:
        print(f"[*] STARTING PEER NODE")
        print(f"[*] Listening for messages at: {ip}:{port}")
    print("="*40)
    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()


    """
    Handle user login via POST request.

    This route simulates a login process and prints the provided headers and body
    to the console.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or login payload.
    """


    """
    Handle greeting via PUT request.

    This route prints a greeting message to the console using the provided headers
    and body.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or message payload.
    """