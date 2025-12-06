"""
Screen Share Service Module
Integrates screen sharing with the P2P Transfer application.
Launches server/client as separate processes.
"""

import os
import sys
import subprocess
import threading
import socket
import time
import json
import struct

# Screen share port (must match MAC/server.py and windows/server.py)
SCREEN_PORT = 5000

# Message types for P2P negotiation
MSG_TYPE_SCREEN_REQUEST = 2
MSG_TYPE_SCREEN_ACCEPT = 3
MSG_TYPE_SCREEN_REJECT = 4


def get_base_path():
    """Get the base path of the application."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_local_ip():
    """Get local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


class ScreenShareManager:
    """
    Manages screen sharing sessions.
    - Launches server to share local screen
    - Launches client to view remote screen
    """
    
    def __init__(self, on_status_callback=None, on_request_callback=None):
        self.on_status = on_status_callback
        self.on_request = on_request_callback
        self.server_process = None
        self.client_process = None
        self.is_server_running = False
        self.is_client_running = False
        
    def _get_python_executable(self):
        """Get the Python executable path."""
        return sys.executable
    
    def _get_server_script(self):
        """Get path to server script (same directory)."""
        base = get_base_path()
        return os.path.join(base, "screen_server.py")
    
    def _get_client_script(self):
        """Get path to client script (same directory)."""
        base = get_base_path()
        return os.path.join(base, "screen_client.py")
    
    def start_server(self):
        """Start the screen share server to share local screen."""
        if self.is_server_running:
            self._notify("Server already running")
            return True
        
        script_path = self._get_server_script()
        if not os.path.exists(script_path):
            self._notify(f"Server script not found: {script_path}")
            return False
        
        try:
            # Launch server as separate process
            python = self._get_python_executable()
            env = os.environ.copy()
            
            # Don't pipe stdout/stderr - let it run independently
            # Use DEVNULL to prevent blocking
            self.server_process = subprocess.Popen(
                [python, script_path],
                env=env,
                cwd=os.path.dirname(script_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent
            )
            
            self.is_server_running = True
            self._notify(f"Screen server started on port {SCREEN_PORT}")
            
            # Monitor process in background
            threading.Thread(target=self._monitor_server, daemon=True).start()
            return True
            
        except Exception as e:
            self._notify(f"Failed to start server: {e}")
            return False
    
    def stop_server(self):
        """Stop the screen share server."""
        if self.server_process:
            self.server_process.terminate()
            self.server_process = None
        self.is_server_running = False
        self._notify("Screen server stopped")
    
    def connect_to_peer(self, host, port=SCREEN_PORT):
        """Launch client to view remote peer's screen."""
        if self.is_client_running:
            self._notify("Client already running")
            return True
        
        script_path = self._get_client_script()
        if not os.path.exists(script_path):
            self._notify(f"Client script not found: {script_path}")
            return False
        
        try:
            python = self._get_python_executable()
            env = os.environ.copy()
            env['SERVER_HOST'] = host
            env['SERVER_PORT'] = str(port)
            
            # Launch GUI app without piping - it needs its own window
            # On macOS, we need to ensure PyQt6 can open its window
            if sys.platform == "darwin":
                # Use open command to properly launch GUI app on macOS
                self.client_process = subprocess.Popen(
                    [python, script_path],
                    env=env,
                    cwd=os.path.dirname(script_path),
                    start_new_session=True
                )
            else:
                self.client_process = subprocess.Popen(
                    [python, script_path],
                    env=env,
                    cwd=os.path.dirname(script_path),
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
                )
            
            self.is_client_running = True
            self._notify(f"Connecting to {host}:{port}...")
            
            # Monitor process in background
            threading.Thread(target=self._monitor_client, daemon=True).start()
            return True
            
        except Exception as e:
            self._notify(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Close client connection."""
        if self.client_process:
            self.client_process.terminate()
            self.client_process = None
        self.is_client_running = False
        self._notify("Disconnected from remote screen")
    
    def _monitor_server(self):
        """Monitor server process."""
        if self.server_process:
            self.server_process.wait()
            self.is_server_running = False
            self._notify("Screen server stopped")
    
    def _monitor_client(self):
        """Monitor client process."""
        if self.client_process:
            self.client_process.wait()
            self.is_client_running = False
            self._notify("Screen viewer closed")
    
    def _notify(self, msg):
        """Send status notification."""
        print(f"[ScreenShare] {msg}")
        if self.on_status:
            self.on_status(msg)
    
    def cleanup(self):
        """Cleanup all processes."""
        self.stop_server()
        self.disconnect()


class ScreenShareProtocol:
    """
    Protocol handler for screen share negotiation over P2P chat.
    Extends the existing ChatService with screen share messages.
    """
    
    def __init__(self, chat_service, screen_manager, on_request_callback=None):
        self.chat_service = chat_service
        self.screen_manager = screen_manager
        self.on_request = on_request_callback
        self.pending_requests = {}  # IP -> timestamp
    
    def send_screen_request(self, target_ip):
        """Request to view target's screen."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((target_ip, 5003))  # CHAT_PORT
            
            msg_type = bytes([MSG_TYPE_SCREEN_REQUEST])
            content = json.dumps({
                "ip": get_local_ip(),
                "port": SCREEN_PORT,
                "action": "request"
            }).encode('utf-8')
            length = struct.pack("!I", len(content))
            
            s.sendall(msg_type + length + content)
            s.close()
            
            self.pending_requests[target_ip] = time.time()
            return True
        except Exception as e:
            print(f"Error sending screen request: {e}")
            return False
    
    def send_screen_accept(self, target_ip):
        """Accept screen share request - start server and notify requester."""
        # Start local server first
        if self.screen_manager.start_server():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((target_ip, 5003))
                
                msg_type = bytes([MSG_TYPE_SCREEN_ACCEPT])
                content = json.dumps({
                    "ip": get_local_ip(),
                    "port": SCREEN_PORT,
                    "action": "accept"
                }).encode('utf-8')
                length = struct.pack("!I", len(content))
                
                s.sendall(msg_type + length + content)
                s.close()
                return True
            except Exception as e:
                print(f"Error sending accept: {e}")
                self.screen_manager.stop_server()
        return False
    
    def send_screen_reject(self, target_ip):
        """Reject screen share request."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((target_ip, 5003))
            
            msg_type = bytes([MSG_TYPE_SCREEN_REJECT])
            content = json.dumps({
                "ip": get_local_ip(),
                "action": "reject"
            }).encode('utf-8')
            length = struct.pack("!I", len(content))
            
            s.sendall(msg_type + length + content)
            s.close()
            return True
        except Exception as e:
            print(f"Error sending reject: {e}")
            return False
    
    def handle_message(self, msg_type, sender_ip, content):
        """Handle incoming screen share protocol messages."""
        try:
            data = json.loads(content)
            
            if msg_type == MSG_TYPE_SCREEN_REQUEST:
                # Someone wants to see our screen
                if self.on_request:
                    self.on_request(sender_ip, data)
                    
            elif msg_type == MSG_TYPE_SCREEN_ACCEPT:
                # Our request was accepted, connect to their server
                host = data.get('ip', sender_ip)
                port = data.get('port', SCREEN_PORT)
                self.screen_manager.connect_to_peer(host, port)
                
            elif msg_type == MSG_TYPE_SCREEN_REJECT:
                # Our request was rejected
                if sender_ip in self.pending_requests:
                    del self.pending_requests[sender_ip]
                print(f"Screen share request rejected by {sender_ip}")
                
        except Exception as e:
            print(f"Error handling screen message: {e}")
