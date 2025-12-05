import flet as ft
import threading
import os
import sys
from p2p_core import DiscoveryService, ChatService, FileTransferService, get_local_ip

# Global services
discovery_service = None
chat_service = None
file_service = None

# Custom Colors
COLOR_BG = "#0F172A"       # Slate 900
COLOR_SIDEBAR = "#1E293B"  # Slate 800
COLOR_PRIMARY = "#3B82F6"  # Blue 500
COLOR_ACCENT = "#10B981"   # Emerald 500
COLOR_TEXT = "#F8FAFC"     # Slate 50
COLOR_BUBBLE_ME = "#3B82F6"
COLOR_BUBBLE_PEER = "#334155" # Slate 700

def main(page: ft.Page):
    page.title = "P2P Transfer & Chat"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.window_width = 1000
    page.window_height = 700
    
    # System Tray / Minimize Logic
    page.window_prevent_close = True

    def window_event(e):
        if e.data == "close":
            page.window_visible = False
            page.update()

    page.on_window_event = window_event

    # State
    current_target_ip = None
    peers = set()
    
    # --- UI Components ---

    # 1. Sidebar (Peers)
    peers_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
    
    sidebar = ft.Container(
        width=280,
        bgcolor=COLOR_SIDEBAR,
        padding=20,
        content=ft.Column([
            ft.Text("P2P Transfer", size=24, weight=ft.FontWeight.BOLD, color=COLOR_PRIMARY),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.WIFI, color=ft.Colors.GREEN, size=16),
                    ft.Text(f"{get_local_ip()}", color=ft.Colors.GREEN, size=14)
                ]),
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREEN),
                padding=10,
                border_radius=8
            ),
            ft.Divider(color=ft.Colors.GREY_700),
            ft.Text("DISPONIBLES", size=12, color=ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
            peers_column,
            ft.Container(expand=True), # Spacer
            ft.ElevatedButton(
                "Salir", 
                icon=ft.Icons.EXIT_TO_APP, 
                color=ft.Colors.RED_400,
                bgcolor=ft.Colors.TRANSPARENT,
                on_click=lambda _: page.window_destroy()
            )
        ])
    )

    # 2. Chat Area
    chat_list = ft.ListView(expand=True, spacing=15, auto_scroll=True, padding=20)
    
    # 3. Input Area
    msg_input = ft.TextField(
        hint_text="Escribe un mensaje...",
        border_radius=20,
        bgcolor=ft.Colors.GREY_900,
        border_color=ft.Colors.TRANSPARENT,
        expand=True,
        on_submit=lambda e: send_message_click(e)
    )
    
    send_btn = ft.IconButton(
        icon=ft.Icons.SEND_ROUNDED, 
        icon_color=COLOR_PRIMARY,
        tooltip="Enviar Mensaje",
        on_click=lambda e: send_message_click(e)
    )

    file_btn = ft.IconButton(
        icon=ft.Icons.ATTACH_FILE, 
        icon_color=ft.Colors.GREY_400,
        tooltip="Enviar Archivo",
        on_click=lambda _: pick_file_click(None)
    )
    
    folder_btn = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN, 
        icon_color=ft.Colors.GREY_400,
        tooltip="Enviar Carpeta",
        on_click=lambda _: pick_folder_click(None)
    )

    input_bar = ft.Container(
        bgcolor=COLOR_SIDEBAR,
        padding=15,
        border_radius=ft.border_radius.only(top_left=15, top_right=15),
        content=ft.Row([
            file_btn,
            folder_btn,
            msg_input,
            send_btn
        ])
    )

    # 4. Header & Progress
    target_header = ft.Text("Selecciona un usuario para chatear", size=16, weight=ft.FontWeight.BOLD)
    progress_bar = ft.ProgressBar(width=None, color=COLOR_ACCENT, bgcolor=ft.Colors.GREY_800, value=0, visible=False)
    progress_text = ft.Text("", size=12, color=ft.Colors.GREY_400, visible=False)

    main_area = ft.Container(
        expand=True,
        bgcolor=COLOR_BG,
        content=ft.Column([
            ft.Container(
                padding=20,
                border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_800)),
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.PERSON, color=ft.Colors.GREY_400),
                        target_header
                    ]),
                    progress_text,
                    progress_bar
                ])
            ),
            ft.Container(expand=True, content=chat_list),
            input_bar
        ])
    )

    # --- Logic ---

    def add_chat_bubble(msg, is_me, sender_ip=""):
        align = ft.MainAxisAlignment.END if is_me else ft.MainAxisAlignment.START
        bg = COLOR_BUBBLE_ME if is_me else COLOR_BUBBLE_PEER
        
        bubble = ft.Container(
            content=ft.Column([
                ft.Text("Yo" if is_me else sender_ip, size=10, color=ft.Colors.GREY_400),
                ft.Text(msg, color=ft.Colors.WHITE)
            ], spacing=2),
            bgcolor=bg,
            padding=12,
            border_radius=ft.border_radius.only(
                top_left=12, top_right=12, 
                bottom_left=12 if is_me else 0,
                bottom_right=0 if is_me else 12
            ),
            width=None,
            constraints=ft.BoxConstraints(max_width=500)
        )
        
        chat_list.controls.append(ft.Row([bubble], alignment=align))
        page.update()

    def add_system_msg(msg, color=ft.Colors.YELLOW):
        chat_list.controls.append(
            ft.Row([
                ft.Container(
                    content=ft.Text(msg, size=12, color=color, italic=True),
                    bgcolor=ft.Colors.with_opacity(0.1, color),
                    padding=5,
                    border_radius=5
                )
            ], alignment=ft.MainAxisAlignment.CENTER)
        )
        page.update()

    def select_peer(ip):
        nonlocal current_target_ip
        current_target_ip = ip
        target_header.value = f"Chat con {ip}"
        target_header.color = ft.Colors.WHITE
        
        # Update sidebar selection visual
        for control in peers_column.controls:
            if isinstance(control, ft.Container):
                control.bgcolor = COLOR_SIDEBAR # Reset
                if control.data == ip:
                    control.bgcolor = ft.Colors.with_opacity(0.2, COLOR_PRIMARY)
        
        page.update()

    def on_peer_found(ip):
        if ip not in peers:
            peers.add(ip)
            
            card = ft.Container(
                data=ip,
                padding=10,
                border_radius=8,
                bgcolor=COLOR_SIDEBAR,
                on_click=lambda e: select_peer(ip),
                content=ft.Row([
                    ft.Icon(ft.Icons.COMPUTER, color=ft.Colors.BLUE_200),
                    ft.Column([
                        ft.Text(ip, weight=ft.FontWeight.BOLD),
                        ft.Text("En línea", size=10, color=ft.Colors.GREEN)
                    ], spacing=2)
                ])
            )
            peers_column.controls.append(card)
            page.update()

    def on_message_received(ip, msg):
        add_chat_bubble(msg, is_me=False, sender_ip=ip)

    def on_file_progress(filename, sent, total):
        progress = sent / total
        progress_bar.value = progress
        progress_bar.visible = True
        progress_text.value = f"Transfiriendo {filename}: {int(progress * 100)}%"
        progress_text.visible = True
        
        if sent == total:
            add_system_msg(f"Archivo recibido: {filename}", ft.Colors.GREEN)
            progress_bar.visible = False
            progress_text.visible = False
        
        page.update()

    # --- Drag & Drop ---
    def on_drop(e: ft.FilePickerResultEvent):
        if not current_target_ip:
            add_system_msg("Error: Selecciona un usuario antes de soltar archivos", ft.Colors.RED)
            return
        
        # Flet drop event returns a list of files
        # Note: e.files might be different depending on Flet version for drag&drop
        # For page.on_file_drop, e is FileDropEvent which has e.file_name (deprecated?) or e.files
        pass 

    def on_file_drop_handler(e: ft.FilePickerResultEvent):
        if not current_target_ip:
            add_system_msg("⚠️ Selecciona un usuario primero", ft.Colors.ORANGE)
            return
        
        # e.files is a list of FilePickerFile objects
        for f in e.files:
            path = f.path
            add_system_msg(f"Enviando: {f.name}...", ft.Colors.YELLOW)
            threading.Thread(target=file_service.send_file, args=(current_target_ip, path)).start()

    page.on_file_drop = on_file_drop_handler

    # --- Handlers ---
    def send_message_click(e):
        if not current_target_ip:
            add_system_msg("Selecciona un usuario primero", ft.Colors.RED)
            return
        if not msg_input.value: return
        
        msg = msg_input.value
        chat_service.send_message(current_target_ip, msg)
        add_chat_bubble(msg, is_me=True)
        msg_input.value = ""
        msg_input.focus()
        page.update()

    def on_file_picked(e: ft.FilePickerResultEvent):
        if not current_target_ip:
            add_system_msg("Selecciona un usuario primero", ft.Colors.RED)
            return
        if e.files:
            filepath = e.files[0].path
            add_system_msg(f"Enviando archivo: {os.path.basename(filepath)}...", ft.Colors.YELLOW)
            threading.Thread(target=file_service.send_file, args=(current_target_ip, filepath)).start()

    def on_folder_picked(e: ft.FilePickerResultEvent):
        if not current_target_ip:
            add_system_msg("Selecciona un usuario primero", ft.Colors.RED)
            return
        if e.path:
            folderpath = e.path
            add_system_msg(f"Enviando carpeta: {os.path.basename(folderpath)}...", ft.Colors.YELLOW)
            threading.Thread(target=file_service.send_file, args=(current_target_ip, folderpath)).start()

    # macOS Workaround Handlers
    def pick_file_click(e):
        if sys.platform == "darwin":
            try:
                import subprocess
                cmd = "osascript -e 'POSIX path of (choose file)'"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    path = result.stdout.strip()
                    if path:
                        add_system_msg(f"Enviando archivo: {os.path.basename(path)}...", ft.Colors.YELLOW)
                        threading.Thread(target=file_service.send_file, args=(current_target_ip, path)).start()
            except Exception as e:
                print(f"Error macOS picker: {e}")
        else:
            file_picker.pick_files(allow_multiple=False)

    def pick_folder_click(e):
        if sys.platform == "darwin":
            try:
                import subprocess
                cmd = "osascript -e 'POSIX path of (choose folder)'"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    path = result.stdout.strip()
                    if path:
                        add_system_msg(f"Enviando carpeta: {os.path.basename(path)}...", ft.Colors.YELLOW)
                        threading.Thread(target=file_service.send_file, args=(current_target_ip, path)).start()
            except Exception as e:
                print(f"Error macOS picker: {e}")
        else:
            folder_picker.get_directory_path()

    # Init Pickers
    file_picker = ft.FilePicker(on_result=on_file_picked)
    folder_picker = ft.FilePicker(on_result=on_folder_picked)


    # Init Services
    global discovery_service, chat_service, file_service
    discovery_service = DiscoveryService(on_peer_found)
    chat_service = ChatService(on_message_received)
    file_service = FileTransferService(on_progress_callback=on_file_progress)

    discovery_service.start()
    chat_service.start_server()
    file_service.start_server()

    # Final Layout
    page.add(
        file_picker,
        folder_picker,
        ft.Row([
            sidebar,
            main_area
        ], expand=True, spacing=0)
    )

if __name__ == "__main__":
    ft.app(target=main)
