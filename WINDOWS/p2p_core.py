import socket
import os
import threading
import json
import time
import shutil
import struct

# Constants
FILE_PORT = 5001
DISCOVERY_PORT = 5002
CHAT_PORT = 5003
BUFFER_SIZE = 64 * 1024 # 64KB for better performance
SEPARATOR = "<SEPARATOR>"
BROADCAST_IP = "255.255.255.255"

# Message Types
MSG_TYPE_CHAT = 0
MSG_TYPE_CLIPBOARD = 1
MSG_TYPE_SCREEN_REQUEST = 2
MSG_TYPE_SCREEN_ACCEPT = 3
MSG_TYPE_SCREEN_REJECT = 4

def get_local_ip():
    """Retrieves the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class SettingsManager:
    def __init__(self, settings_file="settings.json"):
        self.settings_file = settings_file
        self.default_settings = {
            "nickname": f"User_{get_local_ip().split('.')[-1]}",
            "download_dir": "received_files",
            "avatar": "👤", # Default emoji avatar
            "clipboard_share": False
        }
        self.settings = self.load_settings()

    def load_settings(self):
        if not os.path.exists(self.settings_file):
            return self.default_settings.copy()
        try:
            with open(self.settings_file, "r") as f:
                return {**self.default_settings, **json.load(f)}
        except:
            return self.default_settings.copy()

    def save_settings(self, new_settings):
        self.settings.update(new_settings)
        try:
            with open(self.settings_file, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")
        return self.settings

    def get(self, key):
        return self.settings.get(key, self.default_settings.get(key))

class DiscoveryService:
    def __init__(self, settings_manager, on_peer_found_callback):
        self.settings_manager = settings_manager
        self.on_peer_found = on_peer_found_callback
        self.running = False
        self.found_peers = {} # IP -> Info dict

    def start(self):
        self.running = True
        threading.Thread(target=self._listen_broadcast, daemon=True).start()
        threading.Thread(target=self._send_broadcast, daemon=True).start()

    def stop(self):
        self.running = False

    def _listen_broadcast(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('', DISCOVERY_PORT))
        except Exception as e:
            print(f"Error binding discovery port: {e}")
            return

        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                try:
                    msg = json.loads(data.decode('utf-8'))
                    if msg.get('type') == 'discovery':
                        ip = msg.get('ip')
                        if ip != get_local_ip():
                            # Update peer info
                            self.found_peers[ip] = msg
                            self.on_peer_found(msg)
                except json.JSONDecodeError:
                    # Legacy or invalid message
                    pass
            except Exception:
                pass
        sock.close()

    def _send_broadcast(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self.running:
            try:
                msg = {
                    "type": "discovery",
                    "ip": get_local_ip(),
                    "nick": self.settings_manager.get("nickname"),
                    "avatar": self.settings_manager.get("avatar")
                }
                sock.sendto(json.dumps(msg).encode('utf-8'), (BROADCAST_IP, DISCOVERY_PORT))
            except Exception:
                pass
            time.sleep(3) # Broadcast every 3 seconds
        sock.close()

class ChatService:
    def __init__(self, on_message_callback, on_clipboard_callback=None, on_screen_callback=None):
        self.on_message = on_message_callback
        self.on_clipboard = on_clipboard_callback
        self.on_screen = on_screen_callback
        self.running = False
        self.sock = None

    def start_server(self):
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(('0.0.0.0', CHAT_PORT))
        self.sock.listen(5)
        threading.Thread(target=self._accept_clients, daemon=True).start()

    def _accept_clients(self):
        while self.running:
            try:
                client, addr = self.sock.accept()
                threading.Thread(target=self._handle_client, args=(client, addr), daemon=True).start()
            except Exception:
                break

    def _handle_client(self, client, addr):
        while self.running:
            try:
                # Protocol: Type (1 byte) + Length (4 bytes) + Content
                msg_type_bytes = client.recv(1)
                if not msg_type_bytes: break
                msg_type = msg_type_bytes[0]

                length_bytes = client.recv(4)
                if not length_bytes: break
                length = struct.unpack("!I", length_bytes)[0]
                
                content_bytes = client.recv(length)
                if not content_bytes: break
                content = content_bytes.decode('utf-8')

                if msg_type == MSG_TYPE_CHAT:
                    self.on_message(addr[0], content)
                elif msg_type == MSG_TYPE_CLIPBOARD:
                    if self.on_clipboard:
                        self.on_clipboard(addr[0], content)
                elif msg_type in (MSG_TYPE_SCREEN_REQUEST, MSG_TYPE_SCREEN_ACCEPT, MSG_TYPE_SCREEN_REJECT):
                    if self.on_screen:
                        self.on_screen(msg_type, addr[0], content)
            except Exception:
                break
        client.close()

    def _send_packet(self, target_ip, msg_type, content):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((target_ip, CHAT_PORT))
            
            type_byte = bytes([msg_type])
            content_bytes = content.encode('utf-8')
            length_bytes = struct.pack("!I", len(content_bytes))
            
            s.sendall(type_byte + length_bytes + content_bytes)
            s.close()
        except Exception as e:
            print(f"Error sending packet: {e}")

    def send_message(self, target_ip, message):
        self._send_packet(target_ip, MSG_TYPE_CHAT, message)

    def send_clipboard(self, target_ip, content):
        self._send_packet(target_ip, MSG_TYPE_CLIPBOARD, content)

class FileTransferService:
    def __init__(self, settings_manager, on_progress_callback=None):
        self.settings_manager = settings_manager
        self.on_progress = on_progress_callback
        self.running = False

    def start_server(self):
        self.running = True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('0.0.0.0', FILE_PORT))
        server.listen(5)
        threading.Thread(target=self._accept, args=(server,), daemon=True).start()

    def _accept(self, server):
        while self.running:
            try:
                client, addr = server.accept()
                threading.Thread(target=self._receive_file, args=(client,), daemon=True).start()
            except Exception:
                break

    def _receive_file(self, client):
        try:
            len_bytes = client.recv(4)
            meta_len = struct.unpack("!I", len_bytes)[0]
            meta_json = client.recv(meta_len).decode('utf-8')
            metadata = json.loads(meta_json)
            
            filename = metadata['filename']
            filesize = metadata['filesize']
            is_zip = metadata.get('is_zip', False)

            save_dir = self.settings_manager.get("download_dir")
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)

            save_path = os.path.join(save_dir, filename)
            
            received = 0
            with open(save_path, "wb") as f:
                while received < filesize:
                    chunk = client.recv(min(BUFFER_SIZE, filesize - received))
                    if not chunk: break
                    f.write(chunk)
                    received += len(chunk)
                    if self.on_progress:
                        self.on_progress(filename, received, filesize)

            if is_zip:
                extract_path = os.path.join(save_dir, os.path.splitext(filename)[0])
                shutil.unpack_archive(save_path, extract_path)
                os.remove(save_path)

        except Exception as e:
            print(f"Error receiving file: {e}")
        finally:
            client.close()

    def send_file(self, target_ip, filepath):
        if not os.path.exists(filepath): return

        is_folder = os.path.isdir(filepath)
        final_path = filepath
        
        if is_folder:
            shutil.make_archive(filepath, 'zip', filepath)
            final_path = filepath + ".zip"

        filesize = os.path.getsize(final_path)
        filename = os.path.basename(final_path)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((target_ip, FILE_PORT))

            metadata = {
                "filename": filename,
                "filesize": filesize,
                "is_zip": is_folder
            }
            meta_json = json.dumps(metadata).encode('utf-8')
            meta_len = struct.pack("!I", len(meta_json))

            s.sendall(meta_len + meta_json)

            with open(final_path, "rb") as f:
                sent = 0
                while True:
                    chunk = f.read(BUFFER_SIZE)
                    if not chunk: break
                    s.sendall(chunk)
                    sent += len(chunk)
                    if self.on_progress:
                        self.on_progress(filename, sent, filesize)

            s.close()
            
            if is_folder:
                os.remove(final_path)

        except Exception as e:
            print(f"Error sending file: {e}")
