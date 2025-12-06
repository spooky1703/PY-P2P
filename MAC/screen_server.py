"""
Screen Share Server - Mac
Captura pantalla, codifica, transmite via WebSocket
Versión optimizada para macOS
"""

import os
import sys
import base64
import threading
import time
from datetime import datetime
import socket

# Cargar configuración desde .env si existe
def load_config():
    """Cargar configuración desde .env"""
    config = {
        'SERVER_HOST': '0.0.0.0',
        'SERVER_PORT': 5050,  # Changed from 5000 to avoid macOS AirPlay conflict
        'DEBUG': False,
        'CAPTURE_FPS': 15,
        'CAPTURE_QUALITY': 80,
        'RESOLUTION_SCALE': 0.75,  # Reducir para mejor rendimiento
        'MAX_CLIENTS': 5,
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
                        if key in ['SERVER_PORT', 'CAPTURE_FPS', 'CAPTURE_QUALITY', 'MAX_CLIENTS']:
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
    """Verificar que todas las dependencias están instaladas"""
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
        print("\n📦 Instala con:")
        print(f"   pip install {' '.join(missing)}")
        sys.exit(1)

check_dependencies()

from flask import Flask, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import mss
from PIL import Image
import io
import pyautogui

# Configurar pyautogui para Mac
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

app = Flask(__name__)
app.config['SECRET_KEY'] = 'screen-remote-mac-2025'
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25
)

# Estado global
server_state = {
    'capturing': False,
    'clients_connected': 0,
    'frame_count': 0,
    'start_time': None,
}

# Instancia de captura
sct = mss.mss()


def get_local_ip():
    """Obtener IP local del servidor"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def capture_and_encode_frame():
    """
    Captura pantalla usando mss y Pillow (sin OpenCV)
    Retorna frame encoded en base64
    """
    try:
        # Capturar pantalla principal
        monitor = sct.monitors[1]  # Monitor primario
        screenshot = sct.grab(monitor)
        
        # Convertir a PIL Image
        img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
        
        # Redimensionar si es necesario
        if CONFIG['RESOLUTION_SCALE'] < 1.0:
            new_size = (
                int(img.width * CONFIG['RESOLUTION_SCALE']),
                int(img.height * CONFIG['RESOLUTION_SCALE'])
            )
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Codificar como JPEG
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=CONFIG['CAPTURE_QUALITY'], optimize=True)
        
        # Convertir a base64
        encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        server_state['frame_count'] += 1
        return encoded
        
    except Exception as e:
        if CONFIG['DEBUG']:
            print(f"❌ Error capturando pantalla: {e}")
        return None


def capture_loop():
    """
    Loop de captura continua
    """
    frame_time = 1.0 / CONFIG['CAPTURE_FPS']
    
    print("▶️  Captura iniciada")
    
    while server_state['capturing'] and server_state['clients_connected'] > 0:
        start_time = time.time()
        
        # Capturar y enviar frame
        frame_data = capture_and_encode_frame()
        
        if frame_data:
            try:
                socketio.emit('frame', {
                    'data': frame_data,
                    'timestamp': datetime.now().isoformat(),
                    'frame_number': server_state['frame_count']
                }, room='screen-share-room')
            except Exception as e:
                if CONFIG['DEBUG']:
                    print(f"❌ Error enviando frame: {e}")
        
        # Esperar para mantener FPS
        elapsed = time.time() - start_time
        sleep_time = max(0, frame_time - elapsed)
        time.sleep(sleep_time)
    
    server_state['capturing'] = False
    print("⏹️  Captura detenida")


@socketio.on('connect')
def handle_connect():
    """Cliente conectado"""
    server_state['clients_connected'] += 1
    join_room('screen-share-room')
    print(f"✓ Cliente conectado. Total: {server_state['clients_connected']}")
    
    # Iniciar captura si no está corriendo
    if not server_state['capturing']:
        server_state['capturing'] = True
        server_state['start_time'] = datetime.now()
        thread = threading.Thread(target=capture_loop, daemon=True)
        thread.start()
    
    emit('server_info', {
        'status': 'connected',
        'fps': CONFIG['CAPTURE_FPS'],
        'quality': CONFIG['CAPTURE_QUALITY'],
        'timestamp': datetime.now().isoformat()
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Cliente desconectado"""
    server_state['clients_connected'] = max(0, server_state['clients_connected'] - 1)
    leave_room('screen-share-room')
    print(f"✗ Cliente desconectado. Total: {server_state['clients_connected']}")
    
    if server_state['clients_connected'] <= 0:
        server_state['capturing'] = False


@socketio.on('mouse_move')
def handle_mouse_move(data):
    """Controlar movimiento del mouse"""
    try:
        x = int(data['x'])
        y = int(data['y'])
        pyautogui.moveTo(x, y, duration=0)
    except Exception as e:
        if CONFIG['DEBUG']:
            print(f"❌ Error moviendo mouse: {e}")


@socketio.on('mouse_click')
def handle_mouse_click(data):
    """Click del mouse"""
    try:
        button = data.get('button', 'left')
        pyautogui.click(button=button)
        emit('command_executed', {'command': 'mouse_click', 'button': button})
    except Exception as e:
        print(f"❌ Error en click: {e}")
        emit('error', {'message': str(e)})


@socketio.on('mouse_double_click')
def handle_mouse_double_click(data):
    """Doble click del mouse"""
    try:
        button = data.get('button', 'left')
        pyautogui.doubleClick(button=button)
        emit('command_executed', {'command': 'mouse_double_click', 'button': button})
    except Exception as e:
        print(f"❌ Error en doble click: {e}")


@socketio.on('mouse_scroll')
def handle_mouse_scroll(data):
    """Scroll del mouse"""
    try:
        direction = int(data.get('direction', 1))
        amount = int(data.get('amount', 3))
        pyautogui.scroll(direction * amount)
    except Exception as e:
        print(f"❌ Error en scroll: {e}")


@socketio.on('keyboard_press')
def handle_keyboard_press(data):
    """Presionar tecla o combinación"""
    try:
        key = data.get('key')
        keys = data.get('keys', [])
        
        if keys:
            pyautogui.hotkey(*keys)
        elif key:
            pyautogui.press(key)
    except Exception as e:
        print(f"❌ Error en keyboard: {e}")


@socketio.on('get_stats')
def handle_get_stats():
    """Obtener estadísticas del servidor"""
    uptime = 0
    if server_state['start_time']:
        uptime = (datetime.now() - server_state['start_time']).total_seconds()
    
    stats = {
        'frame_count': server_state['frame_count'],
        'clients': server_state['clients_connected'],
        'fps': CONFIG['CAPTURE_FPS'],
        'capturing': server_state['capturing'],
        'uptime_seconds': uptime,
    }
    emit('stats', stats)


@app.route('/')
def index():
    """Página de estado del servidor"""
    local_ip = get_local_ip()
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Screen Share Server - Mac</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: #fff;
                min-height: 100vh;
            }}
            .card {{
                background: rgba(255,255,255,0.1);
                padding: 20px;
                border-radius: 15px;
                margin-bottom: 20px;
                backdrop-filter: blur(10px);
            }}
            h1 {{ color: #00ff88; }}
            .status {{ 
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-weight: bold;
                background: #00ff88; 
                color: #000;
            }}
            .info {{ color: #aaa; margin: 5px 0; }}
            .highlight {{ color: #00ff88; font-weight: bold; }}
            code {{
                background: rgba(0,0,0,0.3);
                padding: 3px 8px;
                border-radius: 5px;
                font-family: 'SF Mono', Consolas, monospace;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🍎 Screen Share Server - Mac</h1>
            <p class="status">● RUNNING</p>
        </div>
        
        <div class="card">
            <h3>📡 Connection Info</h3>
            <p class="info">Local IP: <span class="highlight">{local_ip}</span></p>
            <p class="info">Port: <span class="highlight">{CONFIG['SERVER_PORT']}</span></p>
            <p class="info">Connect URL: <code>http://{local_ip}:{CONFIG['SERVER_PORT']}</code></p>
        </div>
        
        <div class="card">
            <h3>📊 Live Stats</h3>
            <p class="info">Clients: <span id="clients" class="highlight">0</span></p>
            <p class="info">Frames: <span id="frames" class="highlight">0</span></p>
        </div>
        
        <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
        <script>
            const socket = io();
            setInterval(() => socket.emit('get_stats'), 2000);
            socket.on('stats', (data) => {{
                document.getElementById('clients').textContent = data.clients;
                document.getElementById('frames').textContent = data.frame_count;
            }});
        </script>
    </body>
    </html>
    '''


@app.route('/api/status')
def api_status():
    return jsonify({
        'status': 'running',
        'clients': server_state['clients_connected'],
        'frame_count': server_state['frame_count'],
    })


if __name__ == '__main__':
    local_ip = get_local_ip()
    
    print(f"""
    ╔════════════════════════════════════════════════════════╗
    ║     🍎 SCREEN SHARE SERVER - MAC                       ║
    ║            Ready for connections                       ║
    ╠════════════════════════════════════════════════════════╣
    ║                                                        ║
    ║  📡 Local IP: {local_ip:>20}                      ║
    ║  🔌 Port:     {CONFIG['SERVER_PORT']:>20}                      ║
    ║  ⚙️  FPS:      {CONFIG['CAPTURE_FPS']:>20}                      ║
    ║  📊 Quality:  {CONFIG['CAPTURE_QUALITY']:>19}%                      ║
    ║                                                        ║
    ║  🌐 URL: http://{local_ip}:{CONFIG['SERVER_PORT']}                       ║
    ║                                                        ║
    ╚════════════════════════════════════════════════════════╝
    
    ⚠️  Para control remoto, MacOS pedirá permisos de:
        - Grabación de pantalla (Screen Recording)
        - Accesibilidad (Accessibility)
    
    Presiona Ctrl+C para detener
    """)
    
    try:
        socketio.run(
            app, 
            host=CONFIG['SERVER_HOST'], 
            port=CONFIG['SERVER_PORT'], 
            debug=CONFIG['DEBUG'],
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        print("\n✗ Servidor detenido")
        sys.exit(0)
