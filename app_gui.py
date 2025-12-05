import flet as ft
import threading
import os
import sys
from p2p_core import DiscoveryService, ChatService, FileTransferService, get_local_ip

# Global services
discovery_service = None
chat_service = None
file_service = None

def main(page: ft.Page):
    page.title = "P2P Transfer & Chat"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 800
    page.window_height = 600

    # State
    current_target_ip = None
    peers = set()
    
    # UI Elements
    chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
    peers_list = ft.ListView(expand=True, spacing=5)
    msg_input = ft.TextField(hint_text="Escribe un mensaje...", expand=True, on_submit=lambda e: send_message_click(e))
    send_btn = ft.IconButton(icon=ft.Icons.SEND, on_click=lambda e: send_message_click(e))
    file_btn = ft.IconButton(icon=ft.Icons.ATTACH_FILE, on_click=lambda _: file_picker.pick_files(allow_multiple=False))
    folder_btn = ft.IconButton(icon=ft.Icons.FOLDER, on_click=lambda _: folder_picker.get_directory_path())
    
    status_text = ft.Text(f"Tu IP: {get_local_ip()}", color=ft.Colors.GREEN)
    target_text = ft.Text("Selecciona un usuario", color=ft.Colors.GREY)

    def add_log(msg, color=ft.Colors.WHITE):
        chat_list.controls.append(ft.Text(msg, color=color))
        page.update()

    def on_peer_found(ip):
        if ip not in peers:
            peers.add(ip)
            peers_list.controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.COMPUTER),
                    title=ft.Text(ip),
                    on_click=lambda e: select_peer(ip)
                )
            )
            page.update()

    def select_peer(ip):
        nonlocal current_target_ip
        current_target_ip = ip
        target_text.value = f"Conectado a: {ip}"
        target_text.color = ft.Colors.BLUE
        page.update()

    def on_message_received(ip, msg):
        add_log(f"[{ip}]: {msg}", ft.Colors.CYAN)

    def on_file_progress(filename, sent, total):
        # Simple log for now, could be a progress bar
        if sent == total:
            add_log(f"Transferencia completada: {filename}", ft.Colors.GREEN)

    # Initialize Services
    global discovery_service, chat_service, file_service
    
    discovery_service = DiscoveryService(on_peer_found)
    chat_service = ChatService(on_message_received)
    file_service = FileTransferService(on_progress_callback=on_file_progress)

    discovery_service.start()
    chat_service.start_server()
    file_service.start_server()

    # Event Handlers
    def send_message_click(e):
        if not current_target_ip:
            add_log("Error: Selecciona un usuario primero", ft.Colors.RED)
            return
        if not msg_input.value: return
        
        msg = msg_input.value
        chat_service.send_message(current_target_ip, msg)
        add_log(f"Yo: {msg}", ft.Colors.WHITE)
        msg_input.value = ""
        page.update()

    def on_file_picked(e: ft.FilePickerResultEvent):
        if not current_target_ip:
            add_log("Error: Selecciona un usuario primero", ft.Colors.RED)
            return
        if e.files:
            filepath = e.files[0].path
            add_log(f"Enviando archivo: {filepath}...", ft.Colors.YELLOW)
            threading.Thread(target=file_service.send_file, args=(current_target_ip, filepath)).start()

    def on_folder_picked(e: ft.FilePickerResultEvent):
        if not current_target_ip:
            add_log("Error: Selecciona un usuario primero", ft.Colors.RED)
            return
        if e.path:
            folderpath = e.path
            add_log(f"Enviando carpeta: {folderpath}...", ft.Colors.YELLOW)
            threading.Thread(target=file_service.send_file, args=(current_target_ip, folderpath)).start()

    def pick_file_click(e):
        print("DEBUG: Click en botón archivo")
        if sys.platform == "darwin":
            try:
                import subprocess
                cmd = "osascript -e 'POSIX path of (choose file)'"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    path = result.stdout.strip()
                    if path:
                        add_log(f"Enviando archivo: {path}...", ft.Colors.YELLOW)
                        threading.Thread(target=file_service.send_file, args=(current_target_ip, path)).start()
            except Exception as e:
                print(f"Error macOS picker: {e}")
        else:
            file_picker.pick_files(allow_multiple=False)

    def pick_folder_click(e):
        print("DEBUG: Click en botón carpeta")
        if sys.platform == "darwin":
            try:
                import subprocess
                cmd = "osascript -e 'POSIX path of (choose folder)'"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    path = result.stdout.strip()
                    if path:
                        add_log(f"Enviando carpeta: {path}...", ft.Colors.YELLOW)
                        threading.Thread(target=file_service.send_file, args=(current_target_ip, path)).start()
            except Exception as e:
                print(f"Error macOS picker: {e}")
        else:
            folder_picker.get_directory_path()

    file_picker = ft.FilePicker(on_result=on_file_picked)
    folder_picker = ft.FilePicker(on_result=on_folder_picked)
    
    # Update buttons to use new handlers
    file_btn.on_click = pick_file_click
    folder_btn.on_click = pick_folder_click

    # Layout
    page.add(
        file_picker, 
        folder_picker,
        ft.Row([
            # Left Sidebar (Peers)
            ft.Container(
                width=200,
                bgcolor="#1AFFFFFF", # 10% White
                content=ft.Column([
                    ft.Text("Usuarios", size=20, weight=ft.FontWeight.BOLD),
                    status_text,
                    ft.Divider(),
                    peers_list
                ])
            ),
            # Main Content
            ft.Container(
                expand=True,
                content=ft.Column([
                    target_text,
                    ft.Divider(),
                    ft.Container(expand=True, content=chat_list, border=ft.border.all(1, ft.Colors.GREY_800), border_radius=10, padding=10),
                    ft.Row([
                        file_btn,
                        folder_btn,
                        msg_input,
                        send_btn
                    ])
                ])
            )
        ], expand=True)
    )
    
    page.update()


if __name__ == "__main__":
    ft.app(target=main)
