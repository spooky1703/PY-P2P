"""
Screen Share Server - Windows
Captura pantalla, codifica, transmite via WebSocket
Version robusta con mejor manejo de errores
"""

import os
import io
import base64
import threading
import time
from datetime import datetime
import socket
import traceback

# Cargar configuración desde .env si existe
def load_config():
    config = {
        'SERVER_HOST': '0.0.0.0',
        'SERVER_PORT': 5000,
        'DEBUG': False,
        'CAPTURE_FPS': 20,        # 20 FPS para fluidez
        'CAPTURE_QUALITY': 65,    # Balance calidad/velocidad
        'RESOLUTION_SCALE': 0.6,  # 60% resolución
    }
    
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if key in config:
                        if key in ['SERVER_PORT', 'CAPTURE_FPS', 'CAPTURE_QUALITY']:
                            config[key] = int(value)
                        elif key == 'RESOLUTION_SCALE':
                            config[key] = float(value)
                        elif key == 'DEBUG':
                            config[key] = value.lower() == 'true'
                        else:
                            config[key] = value
    return config

CONFIG = load_config()

# Verificar dependencias
def check_dependencies():
    missing = []
    try:
        from flask import Flask
    except ImportError:
        missing.append('Flask')
    try:
        from flask_socketio import SocketIO
    except ImportError:
        missing.append('flask-socketio')
    try:
        import mss
    except ImportError:
        missing.append('mss')
    try:
        from PIL import Image
    except ImportError:
        missing.append('Pillow')
    try:
        import pyautogui
    except ImportError:
        missing.append('pyautogui')
    
    if missing:
        print("❌ Faltan dependencias:")
        for dep in missing:
            print(f"   - {dep}")
        print(f"\n📦 Instala con: pip install {' '.join(missing)}")
        import sys
        sys.exit(1)
    else:
        print("✅ Todas las dependencias están instaladas")

check_dependencies()

from flask import Flask, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import mss
import mss.tools
from PIL import Image
import pyautogui

# Configurar pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

app = Flask(__name__)
app.config['SECRET_KEY'] = 'screen-remote-secret-2025'

# Usar eventlet o threading
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=120,
    ping_interval=30,
    max_http_buffer_size=10 * 1024 * 1024  # 10MB buffer
)

# Estado global
server_state = {
    'capturing': False,
    'clients_connected': 0,
    'frame_count': 0,
    'errors': 0,
    'start_time': None,
}

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def capture_and_encode_frame():
    """Captura pantalla usando mss y Pillow (sin OpenCV)"""
    try:
        with mss.mss() as sct:
            # Capturar monitor primario
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            
            # Convertir a PIL Image
            img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
            
            # Redimensionar
            if CONFIG['RESOLUTION_SCALE'] < 1.0:
                new_size = (
                    int(img.width * CONFIG['RESOLUTION_SCALE']),
                    int(img.height * CONFIG['RESOLUTION_SCALE'])
                )
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Codificar como JPEG
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=CONFIG['CAPTURE_QUALITY'])
            
            # Convertir a base64
            encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            server_state['frame_count'] += 1
            return encoded
            
    except Exception as e:
        server_state['errors'] += 1
        print(f"❌ Error capturando: {e}")
        if CONFIG['DEBUG']:
            traceback.print_exc()
        return None


def capture_loop():
    """Loop de captura continua"""
    print("▶️  Iniciando loop de captura...")
    frame_time = 1.0 / CONFIG['CAPTURE_FPS']
    consecutive_errors = 0
    
    while server_state['capturing'] and server_state['clients_connected'] > 0:
        start_time = time.time()
        
        try:
            frame_data = capture_and_encode_frame()
            
            if frame_data:
                consecutive_errors = 0
                socketio.emit('frame', {
                    'data': frame_data,
                    'timestamp': datetime.now().isoformat(),
                    'frame_number': server_state['frame_count']
                }, room='screen-share-room')
                
                if CONFIG['DEBUG'] and server_state['frame_count'] % 30 == 0:
                    print(f"📤 Frame #{server_state['frame_count']} enviado ({len(frame_data)//1024}KB)")
            else:
                consecutive_errors += 1
                if consecutive_errors > 10:
                    print("⚠️  Muchos errores consecutivos, pausando...")
                    time.sleep(1)
                    consecutive_errors = 0
                    
        except Exception as e:
            print(f"❌ Error en loop: {e}")
            if CONFIG['DEBUG']:
                traceback.print_exc()
            time.sleep(0.5)
        
        # Mantener FPS
        elapsed = time.time() - start_time
        sleep_time = max(0, frame_time - elapsed)
        time.sleep(sleep_time)
    
    server_state['capturing'] = False
    print("⏹️  Captura detenida")


@socketio.on('connect')
def handle_connect():
    server_state['clients_connected'] += 1
    join_room('screen-share-room')
    print(f"✓ Cliente conectado desde {request.remote_addr if 'request' in dir() else 'unknown'}")
    print(f"  Total clientes: {server_state['clients_connected']}")
    
    if not server_state['capturing']:
        server_state['capturing'] = True
        server_state['start_time'] = datetime.now()
        thread = threading.Thread(target=capture_loop, daemon=True)
        thread.start()
    
    emit('server_info', {
        'status': 'connected',
        'fps': CONFIG['CAPTURE_FPS'],
        'quality': CONFIG['CAPTURE_QUALITY'],
        'resolution_scale': CONFIG['RESOLUTION_SCALE'],
    })


@socketio.on('disconnect')
def handle_disconnect():
    server_state['clients_connected'] = max(0, server_state['clients_connected'] - 1)
    leave_room('screen-share-room')
    print(f"✗ Cliente desconectado. Restantes: {server_state['clients_connected']}")
    
    if server_state['clients_connected'] <= 0:
        server_state['capturing'] = False


@socketio.on('mouse_move')
def handle_mouse_move(data):
    try:
        x = int(data['x'])
        y = int(data['y'])
        # Ajustar por escala
        scale = CONFIG['RESOLUTION_SCALE']
        real_x = int(x / scale)
        real_y = int(y / scale)
        pyautogui.moveTo(real_x, real_y, duration=0)
    except Exception as e:
        if CONFIG['DEBUG']:
            print(f"Mouse error: {e}")


@socketio.on('mouse_click')
def handle_mouse_click(data):
    try:
        button = data.get('button', 'left')
        pyautogui.click(button=button)
    except Exception as e:
        print(f"Click error: {e}")


@socketio.on('mouse_double_click')
def handle_mouse_double_click(data):
    try:
        button = data.get('button', 'left')
        pyautogui.doubleClick(button=button)
    except Exception as e:
        print(f"Double click error: {e}")


@socketio.on('mouse_scroll')
def handle_mouse_scroll(data):
    try:
        direction = int(data.get('direction', 1))
        amount = int(data.get('amount', 3))
        pyautogui.scroll(direction * amount)
    except Exception as e:
        print(f"Scroll error: {e}")


@socketio.on('keyboard_press')
def handle_keyboard_press(data):
    try:
        key = data.get('key')
        keys = data.get('keys', [])
        if keys:
            pyautogui.hotkey(*keys)
        elif key:
            pyautogui.press(key)
    except Exception as e:
        print(f"Keyboard error: {e}")


@socketio.on('get_stats')
def handle_get_stats():
    emit('stats', {
        'frame_count': server_state['frame_count'],
        'clients': server_state['clients_connected'],
        'errors': server_state['errors'],
    })


@app.route('/')
def index():
    ip = get_local_ip()
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Screen Share Server</title>
        <style>
            body {{ font-family: Arial; background: #1a1a2e; color: white; padding: 40px; }}
            .card {{ background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; margin: 10px 0; }}
            h1 {{ color: #00ff88; }}
            .status {{ color: #00ff88; font-weight: bold; }}
            code {{ background: #333; padding: 5px 10px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h1>🖥️ Screen Share Server</h1>
        <div class="card">
            <p class="status">● RUNNING</p>
            <p>IP: <code>{ip}</code></p>
            <p>Puerto: <code>{CONFIG['SERVER_PORT']}</code></p>
            <p>FPS: {CONFIG['CAPTURE_FPS']} | Quality: {CONFIG['CAPTURE_QUALITY']}% | Scale: {CONFIG['RESOLUTION_SCALE']*100:.0f}%</p>
        </div>
        <div class="card">
            <p>Frames enviados: <span id="frames">0</span></p>
            <p>Clientes: <span id="clients">0</span></p>
        </div>
        <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
        <script>
            const socket = io();
            setInterval(() => socket.emit('get_stats'), 2000);
            socket.on('stats', d => {{
                document.getElementById('frames').textContent = d.frame_count;
                document.getElementById('clients').textContent = d.clients;
            }});
        </script>
    </body>
    </html>
    '''


if __name__ == '__main__':
    ip = get_local_ip()
    print(f"""
    ╔════════════════════════════════════════════════════════╗
    ║     🖥️  SCREEN SHARE SERVER - WINDOWS                  ║
    ╠════════════════════════════════════════════════════════╣
    ║  📡 IP:       {ip:>20}                      ║
    ║  🔌 Puerto:   {CONFIG['SERVER_PORT']:>20}                      ║
    ║  ⚙️  FPS:      {CONFIG['CAPTURE_FPS']:>20}                      ║
    ║  📊 Quality:  {CONFIG['CAPTURE_QUALITY']:>19}%                      ║
    ║  📐 Scale:    {CONFIG['RESOLUTION_SCALE']*100:>18.0f}%                      ║
    ╚════════════════════════════════════════════════════════╝
    
    🔗 Conéctate desde: http://{ip}:{CONFIG['SERVER_PORT']}
    
    ⚠️  Si no ves frames, verifica:
        1. Firewall permite puerto {CONFIG['SERVER_PORT']}
        2. Cliente tiene la IP correcta
    
    Presiona Ctrl+C para detener
    """)
    
    try:
        socketio.run(app, host='0.0.0.0', port=CONFIG['SERVER_PORT'], 
                    debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n✗ Servidor detenido")
