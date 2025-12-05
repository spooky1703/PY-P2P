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
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"
BROADCAST_IP = "255.255.255.255"
DISCOVERY_MSG = b"P2P_DISCOVERY_V2"

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

class DiscoveryService:
    def __init__(self, on_peer_found_callback):
        self.on_peer_found = on_peer_found_callback
        self.running = False
        self.found_peers = set()

    def start(self):
        self.running = True
        threading.Thread(target=self._listen_broadcast, daemon=True).start()
        threading.Thread(target=self._send_broadcast, daemon=True).start()

    def stop(self):
        self.running = False

    def _listen_broadcast(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # On Windows, SO_REUSEPORT is not available/needed for this usually, but on Mac/Linux it might be.
        # We'll try to bind to 0.0.0.0
        try:
            sock.bind(('', DISCOVERY_PORT))
        except Exception as e:
            print(f"Error binding discovery port: {e}")
            return

        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                if data == DISCOVERY_MSG:
                    ip = addr[0]
                    if ip != get_local_ip() and ip not in self.found_peers:
                        self.found_peers.add(ip)
                        self.on_peer_found(ip)
            except Exception:
                pass
        sock.close()

    def _send_broadcast(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self.running:
            try:
                sock.sendto(DISCOVERY_MSG, (BROADCAST_IP, DISCOVERY_PORT))
            except Exception:
                pass
            time.sleep(5) # Broadcast every 5 seconds
        sock.close()

class ChatService:
    def __init__(self, on_message_callback):
        self.on_message = on_message_callback
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
                # Simple protocol: Length (4 bytes) + Message
                length_bytes = client.recv(4)
                if not length_bytes: break
                length = struct.unpack("!I", length_bytes)[0]
                msg_bytes = client.recv(length)
                if not msg_bytes: break
                message = msg_bytes.decode('utf-8')
                self.on_message(addr[0], message)
            except Exception:
                break
        client.close()

    def send_message(self, target_ip, message):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((target_ip, CHAT_PORT))
            msg_bytes = message.encode('utf-8')
            length_bytes = struct.pack("!I", len(msg_bytes))
            s.sendall(length_bytes + msg_bytes)
            s.close() # For now, one connection per message to keep it simple stateless
        except Exception as e:
            print(f"Error sending chat: {e}")

class FileTransferService:
    def __init__(self, save_dir="received_files", on_progress_callback=None):
        self.save_dir = save_dir
        self.on_progress = on_progress_callback
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
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
            # Protocol: JSON Metadata Length (4 bytes) + JSON Metadata + File Content
            len_bytes = client.recv(4)
            meta_len = struct.unpack("!I", len_bytes)[0]
            meta_json = client.recv(meta_len).decode('utf-8')
            metadata = json.loads(meta_json)
            
            filename = metadata['filename']
            filesize = metadata['filesize']
            is_zip = metadata.get('is_zip', False)

            save_path = os.path.join(self.save_dir, filename)
            
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
                # Unzip and remove
                extract_path = os.path.join(self.save_dir, os.path.splitext(filename)[0])
                shutil.unpack_archive(save_path, extract_path)
                os.remove(save_path)
                print(f"Folder unpacked to {extract_path}")

        except Exception as e:
            print(f"Error receiving file: {e}")
        finally:
            client.close()

    def send_file(self, target_ip, filepath):
        if not os.path.exists(filepath): return

        is_folder = os.path.isdir(filepath)
        final_path = filepath
        
        if is_folder:
            # Zip it
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
                os.remove(final_path) # Clean up generated zip

        except Exception as e:
            print(f"Error sending file: {e}")
