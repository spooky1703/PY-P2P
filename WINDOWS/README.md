# P2P Transfer + Screen Share - Windows

## Instalación

```cmd
pip install -r requirements.txt
```

## Uso

### Iniciar la aplicación P2P
```cmd
python main.py
```

### Screen Share (standalone)

**Servidor** (compartir tu pantalla):
```cmd
python screen_server.py
```

**Cliente** (ver pantalla remota):
```cmd
set SERVER_HOST=192.168.1.X
python screen_client.py
```

## Notas

- Asegúrate de permitir el puerto **5000** en el Firewall de Windows
- El P2P usa puertos **5001-5003**
