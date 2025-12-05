# P2P File Transfer App

Aplicación simple en Python para transferir archivos entre computadoras en la misma red local.

## Requisitos
- Python 3 instalado en ambas computadoras.
- Ambas computadoras deben estar conectadas a la misma red (Wi-Fi o Ethernet).
- Los archivos `main.py` y `p2p_core.py` deben estar en ambas computadoras.

## Instrucciones Paso a Paso

### 1. Preparación
Copia la carpeta del proyecto (o al menos `main.py` y `p2p_core.py`) a la segunda computadora.

### 2. En la computadora que RECIBIRÁ el archivo (Receptor)
1. Abre una terminal.
2. Navega a la carpeta del proyecto.
3. Ejecuta el programa:
   ```bash
   python main.py
   ```
4. Selecciona la opción **2** (`Recibir archivo`).
5. El programa te mostrará tu dirección IP (ej. `192.168.1.50`). **Anota esta IP**.
6. El programa se quedará esperando...

### 3. En la computadora que ENVIARÁ el archivo (Emisor)
1. Abre una terminal.
2. Navega a la carpeta del proyecto.
3. Ejecuta el programa:
   ```bash
   python main.py
   ```
4. Selecciona la opción **1** (`Enviar archivo`).
5. Cuando te pida la IP, escribe la **IP del Receptor** (la que anotaste en el paso anterior).
6. Cuando te pida la ruta del archivo, escribe la ruta o arrastra el archivo a la terminal.
   - Ejemplo: `/Users/usuario/Documentos/foto.jpg`
7. Presiona Enter.

### 4. Resultado
- El archivo se enviará inmediatamente.
- En la computadora del Receptor, el archivo aparecerá en una carpeta llamada `received_files`.

## Solución de Problemas
- **Conexión rechazada / Time out**: Verifica que el firewall de la computadora receptora no esté bloqueando el puerto 5001.
- **IP incorrecta**: Asegúrate de estar usando la IP local correcta (empieza usualmente con `192.168...` o `10...`).
# PY-P2P
