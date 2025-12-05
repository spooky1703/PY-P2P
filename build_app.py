import PyInstaller.__main__
import os
import shutil
import sys

def build():
    print("🧹 Limpiando archivos antiguos...")
    if os.path.exists("dist"): shutil.rmtree("dist")
    if os.path.exists("build"): shutil.rmtree("build")
    if os.path.exists("P2P_Transfer.spec"): os.remove("P2P_Transfer.spec")

    print("🚀 Iniciando compilación con PyInstaller...")
    
    # Common options
    options = [
        'main.py',
        '--name=P2P_Transfer',
        '--noconsole', # Hide terminal
        '--clean',
    ]

    # OS specific options
    if sys.platform == "darwin":
        options.append('--windowed') # Required for .app bundle on Mac
        # options.append('--icon=assets/icon.icns') # Uncomment if you have an icon
    elif sys.platform == "win32":
        options.append('--onefile') # Single .exe is preferred on Windows
        # options.append('--icon=assets/icon.ico')

    PyInstaller.__main__.run(options)

    print("\n✅ ¡Compilación completada!")
    if sys.platform == "darwin":
        print("📁 Tu aplicación está en: dist/P2P_Transfer.app")
    else:
        print("📁 Tu ejecutable está en: dist/P2P_Transfer.exe")

if __name__ == "__main__":
    # Check if pyinstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("❌ Error: PyInstaller no está instalado.")
        print("Ejecuta: pip install pyinstaller")
        sys.exit(1)
        
    build()
