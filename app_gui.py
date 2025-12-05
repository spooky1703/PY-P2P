import flet as ft
import threading
import os
import sys
import time
from p2p_core import DiscoveryService, ChatService, FileTransferService, SettingsManager, get_local_ip

# Global services
discovery_service = None
chat_service = None
file_service = None
settings_manager = None

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
    peers = {} # IP -> Peer Info
    last_clipboard_content = ""
    
    # Initialize Settings
    global settings_manager
    settings_manager = SettingsManager()

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
                    ft.Icon(ft.Icons.PERSON, color=ft.Colors.GREEN, size=16),
                    ft.Text(f"{settings_manager.get('nickname')}", color=ft.Colors.GREEN, size=14, weight=ft.FontWeight.BOLD)
                ]),
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREEN),
                padding=10,
                border_radius=8,
                on_click=lambda _: open_settings_modal()
            ),
            ft.Divider(color=ft.Colors.GREY_700),
            ft.Text("DISPONIBLES", size=12, color=ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
            peers_column,
            ft.Container(expand=True), # Spacer
            ft.ElevatedButton(
                "Configuración", 
                icon=ft.Icons.SETTINGS, 
                color=ft.Colors.GREY_400,
                bgcolor=ft.Colors.TRANSPARENT,
                on_click=lambda _: open_settings_modal()
            ),
            ft.ElevatedButton(
                "Salir", 
                icon=ft.Icons.EXIT_TO_APP, 
                color=ft.Colors.RED_400,
                bgcolor=ft.Colors.TRANSPARENT,
                on_click=lambda _: quit_app()
            )
        ])
    )

    def quit_app():
        # Force exit immediately without trying to update UI
        os._exit(0)


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

    # --- Settings Modal ---
    def open_settings_modal():
        nick_input = ft.TextField(label="Nickname", value=settings_manager.get("nickname"))
        download_path_text = ft.Text(settings_manager.get("download_dir"), size=12, color=ft.Colors.GREY_400)
        clipboard_switch = ft.Switch(label="Compartir Portapapeles", value=settings_manager.get("clipboard_share"))
        
        def save_settings(e):
            settings_manager.save_settings({
                "nickname": nick_input.value,
                "clipboard_share": clipboard_switch.value
            })
            page.close(dlg)
            add_system_msg("Configuración guardada.", ft.Colors.GREEN)

        def pick_download_dir(e):
            download_picker.get_directory_path()

        dlg = ft.AlertDialog(
            title=ft.Text("Configuración"),
            content=ft.Column([
                nick_input,
                ft.Text("Carpeta de Descargas:"),
                ft.Row([
                    download_path_text,
                    ft.IconButton(ft.Icons.FOLDER, on_click=pick_download_dir)
                ]),
                ft.Divider(),
                clipboard_switch,
                ft.Text("Si activas el portapapeles, lo que copies se enviará al usuario conectado.", size=12, color=ft.Colors.GREY_500)
            ], tight=True),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(dlg)),
                ft.TextButton("Guardar", on_click=save_settings),
            ],
        )
        page.open(dlg)

    def on_download_dir_picked(e: ft.FilePickerResultEvent):
        if e.path:
            settings_manager.save_settings({"download_dir": e.path})
            add_system_msg(f"Carpeta de descargas actualizada: {e.path}", ft.Colors.GREEN)

    download_picker = ft.FilePicker(on_result=on_download_dir_picked)
    page.add(download_picker)

    # --- Logic ---

    def add_chat_bubble(msg, is_me, sender_ip=""):
        align = ft.MainAxisAlignment.END if is_me else ft.MainAxisAlignment.START
        bg = COLOR_BUBBLE_ME if is_me else COLOR_BUBBLE_PEER
        
        sender_name = "Yo" if is_me else peers.get(sender_ip, {}).get("nick", sender_ip)

        bubble = ft.Container(
            content=ft.Column([
                ft.Text(sender_name, size=10, color=ft.Colors.GREY_400),
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
        nick = peers.get(ip, {}).get("nick", ip)
        target_header.value = f"Chat con {nick}"
        target_header.color = ft.Colors.WHITE
        
        # Update sidebar selection visual
        for control in peers_column.controls:
            if isinstance(control, ft.Container):
                control.bgcolor = COLOR_SIDEBAR # Reset
                if control.data == ip:
                    control.bgcolor = ft.Colors.with_opacity(0.2, COLOR_PRIMARY)
        
        page.update()

    def on_peer_found(peer_info):
        ip = peer_info['ip']
        nick = peer_info.get('nick', ip)
        avatar = peer_info.get('avatar', '👤')
        
        peers[ip] = peer_info
        
        found = False
        for control in peers_column.controls:
            if isinstance(control, ft.Container) and control.data == ip:
                control.content.controls[1].controls[0].value = nick
                found = True
                break
        
        if not found:
            card = ft.Container(
                data=ip,
                padding=10,
                border_radius=8,
                bgcolor=COLOR_SIDEBAR,
                on_click=lambda e: select_peer(ip),
                content=ft.Row([
                    ft.Text(avatar, size=24),
                    ft.Column([
                        ft.Text(nick, weight=ft.FontWeight.BOLD),
                        ft.Text(ip, size=10, color=ft.Colors.GREY_500)
                    ], spacing=2)
                ])
            )
            peers_column.controls.append(card)
        
        page.update()

    def on_message_received(ip, msg):
        add_chat_bubble(msg, is_me=False, sender_ip=ip)

    def on_clipboard_received(ip, content):
        if settings_manager.get("clipboard_share"):
            page.set_clipboard(content)
            add_system_msg(f"📋 Portapapeles actualizado desde {peers.get(ip, {}).get('nick', ip)}", ft.Colors.PURPLE)

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

    # --- Clipboard Polling ---
    def get_clipboard_content():
        try:
            if sys.platform == "darwin":
                return subprocess.check_output("pbpaste", text=True).strip()
            elif sys.platform == "win32":
                # PowerShell is slower, but works without dependencies
                cmd = "powershell -command Get-Clipboard"
                return subprocess.check_output(cmd, shell=True, text=True).strip()
        except:
            return ""
        return ""

    def clipboard_loop():
        nonlocal last_clipboard_content
        while True:
            if settings_manager.get("clipboard_share") and current_target_ip:
                try:
                    content = get_clipboard_content()
                    if content and content != last_clipboard_content:
                        last_clipboard_content = content
                        # Avoid sending if we just received it (loopback prevention could be added here)
                        # For now, just send.
                        chat_service.send_clipboard(current_target_ip, content)
                        # add_system_msg(f"📋 Portapapeles enviado", ft.Colors.GREY_500) # Optional log
                except Exception as e:
                    print(f"Clipboard error: {e}")
            time.sleep(2) # Poll every 2 seconds

    threading.Thread(target=clipboard_loop, daemon=True).start()
    
    # --- Drag & Drop ---
    def on_file_drop_handler(e: ft.FilePickerResultEvent):
        if not current_target_ip:
            add_system_msg("⚠️ Selecciona un usuario primero", ft.Colors.ORANGE)
            return
        
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
    
    discovery_service = DiscoveryService(settings_manager, on_peer_found)
    chat_service = ChatService(on_message_received, on_clipboard_received)
    file_service = FileTransferService(settings_manager, on_progress_callback=on_file_progress)

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
