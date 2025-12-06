# P2P Transfer + Screen Share - Mac

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

### Iniciar la aplicación P2P
```bash
python3 main.py
```

### Screen Share (standalone)

**Servidor** (compartir tu pantalla):
```bash
python3 screen_server.py
```

**Cliente** (ver pantalla remota):
```bash
SERVER_HOST=192.168.1.X python3 screen_client.py
```

## Notas

- Requiere permisos de **Screen Recording** y **Accessibility** en macOS
- El screen share usa puerto **5000**
- El P2P usa puertos **5001-5003**
