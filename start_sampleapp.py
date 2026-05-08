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
start_sampleapp
~~~~~~~~~~~~~~~~~

This module provides a sample RESTful web application using the AsynapRous framework.

It defines basic route handlers and launches a TCP-based backend server to serve
HTTP requests. The application includes a login endpoint and a greeting endpoint,
and can be configured via command-line arguments.
"""

import json
import socket
import argparse
import os

PORT = 8000  # Default port

if __name__ == "__main__":
    # Parse command-line arguments to configure server IP and port
    parser = argparse.ArgumentParser(prog='ChatApp', description='Hybrid P2P Chat Application') 
    parser.add_argument('--server-ip', default='127.0.0.1')
    parser.add_argument('--server-port', type=int, default=PORT)
    parser.add_argument('--p2p-port', type=int, default=9101)
    parser.add_argument('--mode', type=str, choices=['tracker','peer'], default = 'peer', help="choose node role:'tracker' or 'peer'(client chat) ")

    args = parser.parse_args()

    os.environ["APP_MODE"] = args.mode
    os.environ["APP_IP"] = args.server_ip
    os.environ["P2P_PORT"] = str(args.p2p_port)

    from apps.sampleapp import create_sampleapp  
    # Prepare and launch the RESTful application
    
    create_sampleapp(args.server_ip, args.server_port, args.mode)