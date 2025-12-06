"""
Screen Share Client - Mac
Recibe frames, muestra en PyQt6, envía inputs
Version mejorada con reconexión automática y mejor manejo de errores
"""

import sys
import os
import base64
import threading
import time
from datetime import datetime

# Verificar dependencias antes de iniciar
def check_dependencies():
    """Verificar que todas las dependencias están instaladas"""
    missing = []
    
    try:
        import requests
    except ImportError:
        missing.append('requests')
    
    try:
        import socketio
    except ImportError:
        missing.append('python-socketio[client]')
    
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        missing.append('PyQt6')
    
    if missing:
        print("❌ Faltan dependencias:")
        for dep in missing:
            print(f"   - {dep}")
        print("\n📦 Instala con:")
        print("   pip install -r requirements.txt")
        print("   o")
        print(f"   pip install {' '.join(missing)}")
        sys.exit(1)

# Verificar dependencias al inicio
check_dependencies()

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QLabel, QStatusBar, QPushButton, QHBoxLayout,
    QLineEdit, QSpinBox, QGroupBox, QFormLayout,
    QMessageBox
)
from PyQt6.QtGui import QPixmap, QFont, QCursor
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from socketio import Client

# Cargar configuración desde .env si existe
def load_config():
    """Cargar configuración - prioridad: env vars > client.env > defaults"""
    config = {
        'SERVER_HOST': '192.168.100.130',  # IP de tu Windows
        'SERVER_PORT': 5050,  # Changed from 5000 to avoid macOS AirPlay conflict
        'WINDOW_WIDTH': 1200,
        'WINDOW_HEIGHT': 800,
        'DEBUG': False,
        'RECONNECT_DELAY': 3,
    }
    
    # 1. Leer de client.env si existe
    env_path = os.path.join(os.path.dirname(__file__), 'client.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key in config:
                        if key in ['SERVER_PORT', 'WINDOW_WIDTH', 'WINDOW_HEIGHT', 'RECONNECT_DELAY']:
                            config[key] = int(value)
                        elif key == 'DEBUG':
                            config[key] = value.lower() == 'true'
                        else:
                            config[key] = value
    
    # 2. Variables de entorno tienen prioridad sobre archivo
    if os.environ.get('SERVER_HOST'):
        config['SERVER_HOST'] = os.environ.get('SERVER_HOST')
    if os.environ.get('SERVER_PORT'):
        config['SERVER_PORT'] = int(os.environ.get('SERVER_PORT'))
    
    return config

CONFIG = load_config()


class SignalBridge(QObject):
    """Bridge para signals PyQt desde threads de socket.io"""
    frame_received = pyqtSignal(QPixmap)
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    error_occurred = pyqtSignal(str)
    connection_status = pyqtSignal(str)
    stats_received = pyqtSignal(dict)


class ScreenShareClient:
    def __init__(self, host, port):
        self.sio = Client(
            reconnection=True,
            reconnection_attempts=10,
            reconnection_delay=1,
            reconnection_delay_max=5,
            logger=CONFIG['DEBUG'],
            engineio_logger=CONFIG['DEBUG']
        )
        self.host = host
        self.port = port
        self.signals = SignalBridge()
        self._connected = False
        self._should_reconnect = True
        self.setup_socket_events()
    
    @property
    def connected(self):
        return self._connected and self.sio.connected
    
    def setup_socket_events(self):
        """Configurar eventos de socket.io"""
        
        @self.sio.event
        def connect():
            self._connected = True
            print("✓ Conectado al servidor")
            self.signals.connected.emit()
            self.signals.connection_status.emit("Conectado")
        
        @self.sio.event
        def disconnect():
            self._connected = False
            print("✗ Desconectado del servidor")
            self.signals.disconnected.emit()
            self.signals.connection_status.emit("Desconectado")
        
        @self.sio.event
        def connect_error(data):
            print(f"❌ Error de conexión: {data}")
            self.signals.error_occurred.emit(f"Error de conexión: {data}")
            self.signals.connection_status.emit(f"Error: {data}")
        
        @self.sio.on('frame')
        def on_frame(data):
            """Recibir frame codificado"""
            try:
                frame_data = data['data']
                
                # Decodificar base64
                image_bytes = base64.b64decode(frame_data)
                
                # Crear QPixmap
                pixmap = QPixmap()
                if pixmap.loadFromData(image_bytes):
                    self.signals.frame_received.emit(pixmap)
                else:
                    print("⚠️ No se pudo cargar el frame")
                
            except Exception as e:
                if CONFIG['DEBUG']:
                    print(f"❌ Error decodificando frame: {e}")
        
        @self.sio.on('server_info')
        def on_server_info(data):
            print(f"📊 Server Info: FPS={data.get('fps')}, Quality={data.get('quality')}%")
            self.signals.stats_received.emit(data)
        
        @self.sio.on('stats')
        def on_stats(data):
            self.signals.stats_received.emit(data)
        
        @self.sio.on('error')
        def on_error(data):
            msg = data.get('message', str(data))
            print(f"⚠️ Error del servidor: {msg}")
            self.signals.error_occurred.emit(msg)
        
        @self.sio.on('command_executed')
        def on_command_executed(data):
            if CONFIG['DEBUG']:
                print(f"✓ Comando ejecutado: {data.get('command')}")
    
    def connect(self):
        """Conectar al servidor"""
        try:
            url = f'http://{self.host}:{self.port}'
            print(f"🔌 Conectando a {url}...")
            self.signals.connection_status.emit(f"Conectando a {self.host}...")
            
            self.sio.connect(
                url,
                transports=['websocket', 'polling'],
                wait_timeout=10
            )
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error conectando: {error_msg}")
            self.signals.error_occurred.emit(error_msg)
            self.signals.connection_status.emit(f"Error: {error_msg[:50]}")
            return False
    
    def disconnect(self):
        """Desconectar"""
        self._should_reconnect = False
        if self.sio.connected:
            self.sio.disconnect()
        self._connected = False
    
    def send_mouse_move(self, x, y):
        """Enviar movimiento del mouse"""
        if self.connected:
            self.sio.emit('mouse_move', {'x': x, 'y': y})
    
    def send_mouse_click(self, button='left'):
        """Enviar click del mouse"""
        if self.connected:
            self.sio.emit('mouse_click', {'button': button})
    
    def send_mouse_double_click(self, button='left'):
        """Enviar doble click"""
        if self.connected:
            self.sio.emit('mouse_double_click', {'button': button})
    
    def send_scroll(self, direction=1, amount=3):
        """Enviar scroll"""
        if self.connected:
            self.sio.emit('mouse_scroll', {'direction': direction, 'amount': amount})
    
    def send_keyboard(self, key=None, keys=None):
        """Enviar tecla o combinación"""
        if self.connected:
            if keys:
                self.sio.emit('keyboard_press', {'keys': keys})
            else:
                self.sio.emit('keyboard_press', {'key': key})
    
    def request_stats(self):
        """Solicitar estadísticas del servidor"""
        if self.connected:
            self.sio.emit('get_stats')


class ScreenShareWindow(QMainWindow):
    def __init__(self, server_host, server_port):
        super().__init__()
        
        self.server_host = server_host
        self.server_port = server_port
        self.client = None
        self.remote_width = 1920
        self.remote_height = 1080
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.current_fps = 0
        
        self.setup_ui()
        self.setup_fps_timer()
    
    def setup_ui(self):
        """Configurar interfaz PyQt6"""
        self.setWindowTitle("🖥️ Screen Share Remote Control - Mac")
        self.setGeometry(100, 100, CONFIG['WINDOW_WIDTH'], CONFIG['WINDOW_HEIGHT'])
        self.setMinimumSize(800, 600)
        
        # Widget central
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # ===== Barra de conexión =====
        connection_group = QGroupBox("Conexión")
        connection_layout = QHBoxLayout()
        
        connection_layout.addWidget(QLabel("Host:"))
        self.host_input = QLineEdit(self.server_host)
        self.host_input.setMaximumWidth(150)
        connection_layout.addWidget(self.host_input)
        
        connection_layout.addWidget(QLabel("Puerto:"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(self.server_port)
        self.port_input.setMaximumWidth(80)
        connection_layout.addWidget(self.port_input)
        
        self.connect_btn = QPushButton("🔌 Conectar")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.connect_btn.setStyleSheet("QPushButton { padding: 8px 16px; font-weight: bold; }")
        connection_layout.addWidget(self.connect_btn)
        
        connection_layout.addStretch()
        
        self.status_label = QLabel("⚪ Desconectado")
        self.status_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        connection_layout.addWidget(self.status_label)
        
        connection_group.setLayout(connection_layout)
        main_layout.addWidget(connection_group)
        
        # ===== Label para mostrar la pantalla =====
        self.screen_label = QLabel()
        self.screen_label.setScaledContents(True)
        self.screen_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                border: 2px solid #16213e;
                border-radius: 8px;
            }
        """)
        self.screen_label.setMinimumHeight(500)
        self.screen_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screen_label.setText("Esperando conexión...")
        self.screen_label.setMouseTracking(True)
        main_layout.addWidget(self.screen_label, 1)  # stretch=1 para que ocupe espacio
        
        # ===== Barra de información =====
        info_layout = QHBoxLayout()
        
        self.fps_label = QLabel("FPS: --")
        info_layout.addWidget(self.fps_label)
        
        self.frames_label = QLabel("Frames: 0")
        info_layout.addWidget(self.frames_label)
        
        info_layout.addStretch()
        
        self.test_btn = QPushButton("🖱️ Test Mouse")
        self.test_btn.clicked.connect(self.test_mouse)
        self.test_btn.setEnabled(False)
        info_layout.addWidget(self.test_btn)
        
        main_layout.addLayout(info_layout)
        
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Barra de estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo para conectar")
        
        # Habilitar tracking del mouse
        self.setMouseTracking(True)
        central_widget.setMouseTracking(True)
    
    def setup_fps_timer(self):
        """Timer para calcular FPS"""
        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)  # Cada segundo
    
    def update_fps(self):
        """Actualizar contador de FPS"""
        self.current_fps = self.frame_count
        self.fps_label.setText(f"FPS: {self.current_fps}")
        self.frame_count = 0
    
    def create_client(self):
        """Crear cliente con configuración actual"""
        host = self.host_input.text().strip()
        port = self.port_input.value()
        
        self.client = ScreenShareClient(host, port)
        self.connect_signals()
    
    def connect_signals(self):
        """Conectar señales de socket.io a PyQt"""
        self.client.signals.frame_received.connect(self.display_frame)
        self.client.signals.connected.connect(self.on_connected)
        self.client.signals.disconnected.connect(self.on_disconnected)
        self.client.signals.error_occurred.connect(self.on_error)
        self.client.signals.connection_status.connect(self.on_status_change)
        self.client.signals.stats_received.connect(self.on_stats)
    
    def toggle_connection(self):
        """Alternar conexión"""
        if self.client and self.client.connected:
            self.disconnect_from_server()
        else:
            self.connect_to_server()
    
    def connect_to_server(self):
        """Conectar al servidor en thread separado"""
        self.create_client()
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("⏳ Conectando...")
        self.host_input.setEnabled(False)
        self.port_input.setEnabled(False)
        
        thread = threading.Thread(target=self._connect_thread, daemon=True)
        thread.start()
    
    def _connect_thread(self):
        """Thread de conexión"""
        success = self.client.connect()
        if not success:
            # Re-habilitar controles en caso de error
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText("🔌 Conectar")
            self.host_input.setEnabled(True)
            self.port_input.setEnabled(True)
    
    def on_connected(self):
        """Callback cuando se conecta"""
        self.status_label.setText("🟢 Conectado")
        self.status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        self.connect_btn.setText("🔴 Desconectar")
        self.connect_btn.setEnabled(True)
        self.test_btn.setEnabled(True)
        self.status_bar.showMessage("Conectado al servidor. Recibiendo pantalla...")
    
    def on_disconnected(self):
        """Callback cuando se desconecta"""
        self.status_label.setText("🔴 Desconectado")
        self.status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        self.connect_btn.setText("🔌 Conectar")
        self.connect_btn.setEnabled(True)
        self.host_input.setEnabled(True)
        self.port_input.setEnabled(True)
        self.test_btn.setEnabled(False)
        self.status_bar.showMessage("Desconectado del servidor")
        self.screen_label.setText("Desconectado")
    
    def on_error(self, error_msg):
        """Callback de error"""
        self.status_bar.showMessage(f"❌ Error: {error_msg}")
        self.connect_btn.setEnabled(True)
        self.host_input.setEnabled(True)
        self.port_input.setEnabled(True)
    
    def on_status_change(self, status):
        """Actualizar estado"""
        self.status_bar.showMessage(status)
    
    def on_stats(self, stats):
        """Recibir estadísticas del servidor"""
        self.frames_label.setText(f"Frames: {stats.get('frame_count', 0)}")
    
    def display_frame(self, pixmap):
        """Mostrar frame en la ventana"""
        if not pixmap.isNull():
            self.screen_label.setPixmap(pixmap)
            self.frame_count += 1
            
            # Actualizar dimensiones remotas
            self.remote_width = pixmap.width()
            self.remote_height = pixmap.height()
    
    def get_remote_coordinates(self, event):
        """Calcular coordenadas en pantalla remota"""
        # Obtener posición relativa en el label
        label_pos = self.screen_label.mapFromGlobal(event.globalPosition().toPoint())
        
        # Verificar que está dentro del label
        if (label_pos.x() < 0 or label_pos.y() < 0 or 
            label_pos.x() > self.screen_label.width() or 
            label_pos.y() > self.screen_label.height()):
            return None, None
        
        # Calcular posición en pantalla remota
        label_width = self.screen_label.width()
        label_height = self.screen_label.height()
        
        x = int(label_pos.x() * self.remote_width / label_width)
        y = int(label_pos.y() * self.remote_height / label_height)
        
        # Limitar a dimensiones válidas
        x = max(0, min(x, self.remote_width - 1))
        y = max(0, min(y, self.remote_height - 1))
        
        return x, y
    
    def mouseMoveEvent(self, event):
        """Capturar movimiento del mouse"""
        if self.client and self.client.connected:
            x, y = self.get_remote_coordinates(event)
            if x is not None:
                self.client.send_mouse_move(x, y)
        super().mouseMoveEvent(event)
    
    def mousePressEvent(self, event):
        """Click del mouse"""
        if self.client and self.client.connected:
            x, y = self.get_remote_coordinates(event)
            if x is not None:
                # Mover primero, luego click
                self.client.send_mouse_move(x, y)
                button = 'left' if event.button() == Qt.MouseButton.LeftButton else 'right'
                self.client.send_mouse_click(button)
        super().mousePressEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """Doble click"""
        if self.client and self.client.connected:
            x, y = self.get_remote_coordinates(event)
            if x is not None:
                self.client.send_mouse_move(x, y)
                button = 'left' if event.button() == Qt.MouseButton.LeftButton else 'right'
                self.client.send_mouse_double_click(button)
        super().mouseDoubleClickEvent(event)
    
    def wheelEvent(self, event):
        """Rueda del mouse"""
        if self.client and self.client.connected:
            delta = event.angleDelta().y()
            direction = 1 if delta > 0 else -1
            self.client.send_scroll(direction, 5)
        super().wheelEvent(event)
    
    def keyPressEvent(self, event):
        """Presionar tecla"""
        if self.client and self.client.connected and not event.isAutoRepeat():
            key = event.key()
            text = event.text()
            
            # Mapear teclas especiales
            key_map = {
                Qt.Key.Key_Return: 'enter',
                Qt.Key.Key_Enter: 'enter',
                Qt.Key.Key_Backspace: 'backspace',
                Qt.Key.Key_Tab: 'tab',
                Qt.Key.Key_Escape: 'escape',
                Qt.Key.Key_Space: 'space',
                Qt.Key.Key_Delete: 'delete',
                Qt.Key.Key_Up: 'up',
                Qt.Key.Key_Down: 'down',
                Qt.Key.Key_Left: 'left',
                Qt.Key.Key_Right: 'right',
                Qt.Key.Key_Home: 'home',
                Qt.Key.Key_End: 'end',
                Qt.Key.Key_PageUp: 'pageup',
                Qt.Key.Key_PageDown: 'pagedown',
            }
            
            if key in key_map:
                self.client.send_keyboard(key=key_map[key])
            elif text:
                self.client.send_keyboard(key=text)
        
        super().keyPressEvent(event)
    
    def test_mouse(self):
        """Test: mover mouse en pantalla remota"""
        if self.client and self.client.connected:
            self.client.send_mouse_move(500, 500)
            self.status_bar.showMessage("✓ Test: mouse movido a (500, 500)")
    
    def disconnect_from_server(self):
        """Desconectar"""
        if self.client:
            self.client.disconnect()
    
    def closeEvent(self, event):
        """Al cerrar la ventana"""
        self.disconnect_from_server()
        event.accept()


def main():
    print(f"""
    ╔════════════════════════════════════════════════════╗
    ║     🖥️  SCREEN SHARE CLIENT - MAC                  ║
    ║         Control Your Windows PC                   ║
    ╠════════════════════════════════════════════════════╣
    ║  Server: {CONFIG['SERVER_HOST']:>15}:{CONFIG['SERVER_PORT']:<5}              ║
    ╚════════════════════════════════════════════════════╝
    """)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = ScreenShareWindow(CONFIG['SERVER_HOST'], CONFIG['SERVER_PORT'])
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
