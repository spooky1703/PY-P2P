import socket
import os
import threading

BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"

def get_local_ip():
    """Retrieves the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class FileReceiver:
    def __init__(self, port=5001, save_dir="received_files"):
        self.port = port
        self.save_dir = save_dir
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

    def start(self):
        """Starts the server to listen for incoming file transfers."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("0.0.0.0", self.port))
        server_socket.listen(5)
        print(f"[*] Escuchando en {get_local_ip()}:{self.port}")

        try:
            while True:
                client_socket, address = server_socket.accept()
                print(f"[+] Conexión aceptada de {address}")
                # Handle client in a separate thread to allow multiple transfers (optional for now but good practice)
                client_handler = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_handler.start()
        except KeyboardInterrupt:
            print("\n[*] Deteniendo servidor...")
        finally:
            server_socket.close()

    def handle_client(self, client_socket):
        """Handles the file reception from a connected client."""
        try:
            # Receive file info
            received = client_socket.recv(BUFFER_SIZE).decode()
            filename, filesize = received.split(SEPARATOR)
            filename = os.path.basename(filename) # Security check
            filesize = int(filesize)

            filepath = os.path.join(self.save_dir, filename)
            print(f"[*] Recibiendo {filename} ({filesize} bytes)...")

            with open(filepath, "wb") as f:
                bytes_read = 0
                while bytes_read < filesize:
                    # Read only what is needed
                    chunk_size = min(BUFFER_SIZE, filesize - bytes_read)
                    bytes_data = client_socket.recv(chunk_size)
                    if not bytes_data:
                        break
                    f.write(bytes_data)
                    bytes_read += len(bytes_data)

            print(f"[+] Archivo guardado en {filepath}")
        except Exception as e:
            print(f"[-] Error al recibir archivo: {e}")
        finally:
            client_socket.close()

class FileSender:
    def __init__(self):
        pass

    def send_file(self, host, port, filepath):
        """Sends a file to a specified host and port."""
        if not os.path.exists(filepath):
            print(f"[-] Archivo no encontrado: {filepath}")
            return

        filesize = os.path.getsize(filepath)
        filename = os.path.basename(filepath)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"[*] Conectando a {host}:{port}...")
        
        try:
            s.connect((host, port))
            print("[+] Conectado.")

            # Send file info
            s.send(f"{filename}{SEPARATOR}{filesize}".encode())
            
            # Simple wait to ensure header is processed (in a real app we'd wait for ACK)
            import time
            time.sleep(0.1) 

            print(f"[*] Enviando {filename}...")
            with open(filepath, "rb") as f:
                while True:
                    bytes_read = f.read(BUFFER_SIZE)
                    if not bytes_read:
                        break
                    s.sendall(bytes_read)
            
            print("[+] Archivo enviado exitosamente.")

        except Exception as e:
            print(f"[-] Error al enviar archivo: {e}")
        finally:
            s.close()
