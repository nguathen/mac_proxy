#!/usr/bin/env python3
"""
HTTPS Proxy Wrapper - Chain local proxy to upstream ProtonVPN proxy
"""

import sys
import socket
import select
import threading
import argparse
import requests
from urllib.parse import urlparse

class ProxyHandler:
    def __init__(self, upstream_host, upstream_port, upstream_user, upstream_pass):
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.upstream_user = upstream_user
        self.upstream_pass = upstream_pass
        self.upstream_auth = f"{upstream_user}:{upstream_pass}"
    
    def handle_client(self, client_socket, client_address):
        try:
            # Read HTTP request
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = client_socket.recv(4096)
                if not chunk:
                    return
                request += chunk
            
            # Parse request
            lines = request.decode('utf-8', errors='ignore').split('\r\n')
            if not lines:
                client_socket.close()
                return
            
            request_line = lines[0]
            parts = request_line.split(' ')
            if len(parts) < 3:
                client_socket.close()
                return
            
            method, url, protocol = parts[0], parts[1], parts[2]
            
            print(f"Request: {method} {url}")
            
            # Connect to upstream proxy
            upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            upstream.settimeout(30)
            upstream.connect((self.upstream_host, self.upstream_port))
            
            # Add upstream proxy authentication
            import base64
            auth_string = base64.b64encode(self.upstream_auth.encode()).decode()
            
            # Forward request to upstream with authentication
            if method == 'CONNECT':
                # HTTPS CONNECT method
                new_request = f"{method} {url} {protocol}\r\n"
                new_request += f"Proxy-Authorization: Basic {auth_string}\r\n"
                new_request += "\r\n"
                
                upstream.sendall(new_request.encode())
                
                # Read response from upstream
                response = b""
                while b"\r\n\r\n" not in response:
                    chunk = upstream.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                
                # Forward response to client
                client_socket.sendall(response)
                
                # Check if connection established
                if b"200" in response:
                    # Bidirectional forwarding
                    self.forward_data(client_socket, upstream)
                else:
                    print(f"Upstream proxy rejected CONNECT: {response[:200]}")
            else:
                # Regular HTTP request
                headers = []
                for line in lines[1:]:
                    if line and not line.lower().startswith('proxy-authorization:'):
                        headers.append(line)
                
                headers.append(f"Proxy-Authorization: Basic {auth_string}")
                
                # Rebuild request
                new_request = f"{method} {url} {protocol}\r\n"
                new_request += "\r\n".join(headers)
                new_request += "\r\n\r\n"
                
                upstream.sendall(new_request.encode())
                
                # Bidirectional forwarding
                self.forward_data(client_socket, upstream)
            
        except Exception as e:
            print(f"Error handling client {client_address}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    def forward_data(self, client, upstream):
        """Forward data between client and upstream"""
        sockets = [client, upstream]
        
        while True:
            readable, _, exceptional = select.select(sockets, [], sockets, 60)
            
            if exceptional:
                break
            
            for sock in readable:
                try:
                    data = sock.recv(8192)
                    if not data:
                        return
                    
                    if sock is client:
                        upstream.send(data)
                    else:
                        client.send(data)
                except:
                    return

class ProxyServer:
    def __init__(self, listen_port, upstream_host, upstream_port, upstream_user, upstream_pass):
        self.listen_port = int(listen_port)
        self.handler = ProxyHandler(upstream_host, int(upstream_port), upstream_user, upstream_pass)
        self.server_socket = None
    
    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.listen_port))
        self.server_socket.listen(100)
        
        print(f"HTTPS Proxy listening on 0.0.0.0:{self.listen_port}")
        print(f"Upstream: {self.handler.upstream_host}:{self.handler.upstream_port}")
        
        while True:
            try:
                client_socket, client_address = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handler.handle_client,
                    args=(client_socket, client_address)
                )
                client_thread.daemon = True
                client_thread.start()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error accepting connection: {e}")
        
        self.server_socket.close()

def main():
    parser = argparse.ArgumentParser(description='HTTPS Proxy Wrapper')
    parser.add_argument('--port', type=int, required=True, help='Local listen port')
    parser.add_argument('--upstream-host', required=True, help='Upstream proxy host')
    parser.add_argument('--upstream-port', required=True, help='Upstream proxy port')
    parser.add_argument('--upstream-user', required=True, help='Upstream proxy username')
    parser.add_argument('--upstream-pass', required=True, help='Upstream proxy password')
    
    args = parser.parse_args()
    
    server = ProxyServer(
        args.port,
        args.upstream_host,
        args.upstream_port,
        args.upstream_user,
        args.upstream_pass
    )
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

