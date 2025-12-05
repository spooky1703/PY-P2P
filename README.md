# PY-P2P 

Una aplicación moderna y robusta para la transferencia de archivos P2P y chat en red local (LAN), construida con Python y Flet.

## Características

- **Interfaz Moderna**: GUI oscura y elegante con tarjetas de usuario y burbujas de chat.
- **Auto-Descubrimiento**: Encuentra automáticamente otros dispositivos en tu red Wi-Fi sin necesidad de escribir IPs.
- **Transferencia de Archivos y Carpetas**:
  - Envía archivos individuales de cualquier tamaño.
  - Envía **carpetas completas** (se comprimen y descomprimen automáticamente).
  - **Drag & Drop**: Arrastra archivos directamente a la ventana para enviarlos.
- **Chat Integrado**: Comunícate con otros usuarios mientras transfieres archivos.
- **Barra de Progreso**: Visualiza el avance de tus transferencias en tiempo real.
- **Multiplataforma**: Funciona en **Windows** y **macOS** (con soporte nativo para diálogos de sistema en Mac).
- **Minimizar a Bandeja**: La aplicación sigue funcionando en segundo plano si cierras la ventana principal.

## Requisitos e Instalación

Necesitas tener **Python 3.x** instalado.

1.  Clona este repositorio:
    ```bash
    git clone https://github.com/spooky1703/PY-P2P.git
    cd PY-P2P
    ```

2.  Instala las dependencias (solo requiere `flet`):
    ```bash
    pip install flet
    ```

## Uso

1.  Asegúrate de que ambas computadoras estén conectadas a la **misma red Wi-Fi/Ethernet**.
2.  Ejecuta la aplicación en ambas máquinas:
    ```bash
    python main.py
    ```
3.  Espera unos segundos a que aparezca el otro usuario en la lista de la izquierda.
4.  Haz clic en el usuario para conectar.
5.  ¡Empieza a chatear o arrastra archivos para enviarlos!

## Solución de Problemas

- **No veo al otro usuario**:
    - Verifica que el **Firewall** de Windows/Mac no esté bloqueando Python.
    - Asegúrate de estar en la misma red (y no en una red de invitados que aísla dispositivos).
- **Error al abrir archivos en Mac**:
    - La app usa AppleScript para abrir el selector de archivos nativo. Si te pide permisos de automatización o acceso al disco, acéptalos.

## Licencia

Este proyecto es de código abierto. ¡Siéntete libre de contribuir!
